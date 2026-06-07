from src.database.connection import get_postgres_connection

class PostgresRepository:
    def create_user(self, nombre, email, password_hash, edad, genero, ubicacion):
        """Insert user into database and return the generated user_id."""
        conn = get_postgres_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO users (nombre, email, password_hash, edad, genero, ubicacion)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING id;
                    """,
                    (nombre, email, password_hash, edad, genero, ubicacion)
                )
                user_id = cur.fetchone()[0]
            conn.commit()
            return user_id
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def delete_user(self, user_id):
        """Delete user from database (used for rollback)."""
        conn = get_postgres_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM users WHERE id = %s;", (user_id,))
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def get_user_by_email(self, email):
        """Retrieve user details by email."""
        conn = get_postgres_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, nombre, email, password_hash, edad, genero, ubicacion, created_at
                    FROM users
                    WHERE LOWER(email) = LOWER(%s);
                    """,
                    (email,)
                )
                row = cur.fetchone()
                if row:
                    return {
                        "id": row[0],
                        "nombre": row[1],
                        "email": row[2],
                        "password_hash": row[3],
                        "edad": row[4],
                        "genero": row[5],
                        "ubicacion": row[6],
                        "created_at": row[7]
                    }
                return None
        finally:
            conn.close()

    def get_user_by_id(self, user_id):
        """Retrieve user details by ID."""
        conn = get_postgres_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, nombre, email, password_hash, edad, genero, ubicacion, created_at
                    FROM users
                    WHERE id = %s;
                    """,
                    (user_id,)
                )
                row = cur.fetchone()
                if row:
                    return {
                        "id": row[0],
                        "nombre": row[1],
                        "email": row[2],
                        "password_hash": row[3],
                        "edad": row[4],
                        "genero": row[5],
                        "ubicacion": row[6],
                        "created_at": row[7]
                    }
                return None
        finally:
            conn.close()

    def get_users_by_filter(self, exclude_ids, gender_interest, edad_min, edad_max, current_user_id):
        """Find users matching the filters who are not in the excluded list."""
        conn = get_postgres_connection()
        try:
            # Prepare exclude IDs list
            # Always exclude current_user_id
            ex_list = list(exclude_ids) if exclude_ids else []
            ex_list.append(current_user_id)
            
            # Format query for in-list
            query = """
                SELECT id FROM users
                WHERE id NOT IN %s
                  AND edad BETWEEN %s AND %s
            """
            params = [tuple(ex_list), edad_min, edad_max]
            
            if gender_interest and gender_interest.lower() != "cualquiera":
                query += " AND LOWER(genero) = LOWER(%s)"
                params.append(gender_interest)
                
            query += " ORDER BY id;"
            
            with conn.cursor() as cur:
                cur.execute(query, params)
                rows = cur.fetchall()
                return [row[0] for row in rows]
        finally:
            conn.close()

    def create_match(self, user_a, user_b):
        """Create a confirmed match between user_a and user_b, returning the match_id."""
        # Enforce ordering to respect check constraint user_id_1 < user_id_2
        u1, u2 = min(user_a, user_b), max(user_a, user_b)
        conn = get_postgres_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO coincidencias_confirmadas (user_id_1, user_id_2)
                    VALUES (%s, %s)
                    ON CONFLICT (user_id_1, user_id_2) DO UPDATE 
                      SET created_at = NOW() -- if already existed (e.g. re-created)
                    RETURNING id;
                    """,
                    (u1, u2)
                )
                match_id = cur.fetchone()[0]
            conn.commit()
            return match_id
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def delete_match(self, match_id):
        """Delete confirmed match (used for rollback)."""
        conn = get_postgres_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM coincidencias_confirmadas WHERE id = %s;", (match_id,))
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def get_match_between_users(self, user_a, user_b):
        """Retrieve match details between user_a and user_b if it exists."""
        u1, u2 = min(user_a, user_b), max(user_a, user_b)
        conn = get_postgres_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, user_id_1, user_id_2, created_at
                    FROM coincidencias_confirmadas
                    WHERE user_id_1 = %s AND user_id_2 = %s;
                    """,
                    (u1, u2)
                )
                row = cur.fetchone()
                if row:
                    return {"id": row[0], "user_id_1": row[1], "user_id_2": row[2], "created_at": row[3]}
                return None
        finally:
            conn.close()

    def get_user_matches(self, user_id):
        """Retrieve list of all confirmed matches for a user."""
        conn = get_postgres_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, user_id_1, user_id_2, created_at
                    FROM coincidencias_confirmadas
                    WHERE user_id_1 = %s OR user_id_2 = %s;
                    """,
                    (user_id, user_id)
                )
                rows = cur.fetchall()
                results = []
                for row in rows:
                    results.append({
                        "id": row[0],
                        "user_id_1": row[1],
                        "user_id_2": row[2],
                        "created_at": row[3]
                    })
                return results
        finally:
            conn.close()

    def create_block_audit(self, bloqueador_id, bloqueado_id):
        """Insert block audit log into PostgreSQL."""
        conn = get_postgres_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO bloqueos_auditoria (bloqueador_id, bloqueado_id)
                    VALUES (%s, %s);
                    """,
                    (bloqueador_id, bloqueado_id)
                )
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def create_event(self, organizador_id, titulo, descripcion, ubicacion, fecha_hora):
        """Create a new social event and return the event ID."""
        conn = get_postgres_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO events (organizador_id, titulo, descripcion, ubicacion, fecha_hora)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id;
                    """,
                    (organizador_id, titulo, descripcion, ubicacion, fecha_hora)
                )
                event_id = cur.fetchone()[0]
            conn.commit()
            return event_id
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def delete_event(self, event_id):
        """Delete an event (used for rollback)."""
        conn = get_postgres_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM events WHERE id = %s;", (event_id,))
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def register_attendance(self, user_id, event_id):
        """Register user attendance/registration to a social event."""
        conn = get_postgres_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO asistencia_eventos (user_id, evento_id)
                    VALUES (%s, %s);
                    """,
                    (user_id, event_id)
                )
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def get_events(self):
        """Retrieve list of all social events."""
        conn = get_postgres_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT e.id, e.organizador_id, e.titulo, e.descripcion, e.ubicacion, e.fecha_hora, u.nombre
                    FROM events e
                    JOIN users u ON e.organizador_id = u.id
                    ORDER BY e.fecha_hora ASC;
                    """
                )
                rows = cur.fetchall()
                results = []
                for row in rows:
                    results.append({
                        "id": row[0],
                        "organizador_id": row[1],
                        "titulo": row[2],
                        "descripcion": row[3],
                        "ubicacion": row[4],
                        "fecha_hora": row[5],
                        "organizador_nombre": row[6]
                    })
                return results
        finally:
            conn.close()

    def get_event_by_id(self, event_id):
        """Retrieve details of a specific event."""
        conn = get_postgres_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, organizador_id, titulo, descripcion, ubicacion, fecha_hora
                    FROM events
                    WHERE id = %s;
                    """,
                    (event_id,)
                )
                row = cur.fetchone()
                if row:
                    return {
                        "id": row[0],
                        "organizador_id": row[1],
                        "titulo": row[2],
                        "descripcion": row[3],
                        "ubicacion": row[4],
                        "fecha_hora": row[5]
                    }
                return None
        finally:
            conn.close()

    def get_all_user_ids_except(self, exclude_id):
        """Retrieve list of all user IDs except the excluded one."""
        conn = get_postgres_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM users WHERE id != %s;", (exclude_id,))
                rows = cur.fetchall()
                return [row[0] for row in rows]
        finally:
            conn.close()
