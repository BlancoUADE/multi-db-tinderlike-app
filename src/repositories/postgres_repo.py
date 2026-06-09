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
                    SELECT id, nombre, email, password_hash, edad, genero, ubicacion,
                           biografia, pref_edad_min, pref_edad_max, created_at
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
                        "biografia": row[7],
                        "pref_edad_min": row[8],
                        "pref_edad_max": row[9],
                        "created_at": row[10]
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
                    SELECT id, nombre, email, password_hash, edad, genero, ubicacion,
                           biografia, pref_edad_min, pref_edad_max, created_at
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
                        "biografia": row[7],
                        "pref_edad_min": row[8],
                        "pref_edad_max": row[9],
                        "created_at": row[10]
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
            
            query = """
                SELECT id FROM users
                WHERE id <> ALL(%s)
                  AND edad BETWEEN %s AND %s
            """
            params = [ex_list, edad_min, edad_max]
            
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

    def register_block_and_delete_match(self, bloqueador_id, bloqueado_id):
        """
        Register a block audit and remove the official confirmed match in one
        PostgreSQL transaction.
        """
        u1, u2 = min(bloqueador_id, bloqueado_id), max(bloqueador_id, bloqueado_id)
        conn = get_postgres_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    DELETE FROM coincidencias_confirmadas
                    WHERE user_id_1 = %s AND user_id_2 = %s
                    RETURNING id;
                    """,
                    (u1, u2)
                )
                row = cur.fetchone()
                deleted_match_id = row[0] if row else None

                cur.execute(
                    """
                    INSERT INTO bloqueos_auditoria (bloqueador_id, bloqueado_id)
                    VALUES (%s, %s);
                    """,
                    (bloqueador_id, bloqueado_id)
                )
            conn.commit()
            return deleted_match_id
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

    def update_user_profile_fields(self, user_id, biografia, pref_edad_min, pref_edad_max):
        """Update user profile fields in PostgreSQL."""
        conn = get_postgres_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE users 
                    SET biografia = %s, pref_edad_min = %s, pref_edad_max = %s
                    WHERE id = %s;
                    """,
                    (biografia, pref_edad_min, pref_edad_max, user_id)
                )
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def create_like(self, user_from, user_to, tipo="like"):
        """Create a like or dislike in PostgreSQL."""
        conn = get_postgres_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO likes (id_usuario_origen, id_usuario_destino, tipo)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (id_usuario_origen, id_usuario_destino) DO UPDATE 
                      SET tipo = EXCLUDED.tipo, fecha_like = NOW()
                    RETURNING id;
                    """,
                    (user_from, user_to, tipo)
                )
                like_id = cur.fetchone()[0]
            conn.commit()
            return like_id
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def get_excluded_user_ids(self, user_id):
        """Retrieve user IDs excluded by canonical PostgreSQL likes, matches and blocks."""
        conn = get_postgres_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id_usuario_destino
                    FROM likes
                    WHERE id_usuario_origen = %s

                    UNION

                    SELECT CASE
                        WHEN user_id_1 = %s THEN user_id_2
                        ELSE user_id_1
                    END
                    FROM coincidencias_confirmadas
                    WHERE user_id_1 = %s OR user_id_2 = %s

                    UNION

                    SELECT bloqueado_id
                    FROM bloqueos_auditoria
                    WHERE bloqueador_id = %s

                    UNION

                    SELECT bloqueador_id
                    FROM bloqueos_auditoria
                    WHERE bloqueado_id = %s;
                    """,
                    (user_id, user_id, user_id, user_id, user_id, user_id)
                )
                return {row[0] for row in cur.fetchall() if row[0] is not None}
        finally:
            conn.close()

    def has_like(self, user_from, user_to):
        """Return True if user_from has an active like for user_to in PostgreSQL."""
        conn = get_postgres_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT 1
                    FROM likes
                    WHERE id_usuario_origen = %s
                      AND id_usuario_destino = %s
                      AND tipo = 'like';
                    """,
                    (user_from, user_to)
                )
                return cur.fetchone() is not None
        finally:
            conn.close()

    def add_photo(self, user_id, url_archivo, es_principal=False):
        """Add a photo for a user in PostgreSQL."""
        conn = get_postgres_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO fotos (id_usuario, url_archivo, es_principal)
                    VALUES (%s, %s, %s)
                    RETURNING id;
                    """,
                    (user_id, url_archivo, es_principal)
                )
                photo_id = cur.fetchone()[0]
            conn.commit()
            return photo_id
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def get_user_photos(self, user_id):
        """Retrieve a user's photos from PostgreSQL ordered by principal first."""
        conn = get_postgres_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT url_archivo
                    FROM fotos
                    WHERE id_usuario = %s
                    ORDER BY es_principal DESC, fecha_subida ASC, id ASC;
                    """,
                    (user_id,)
                )
                return [row[0] for row in cur.fetchall()]
        finally:
            conn.close()

    def create_message(self, match_id, sender_id, contenido):
        """Create a message in PostgreSQL."""
        conn = get_postgres_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO mensajes (id_coincidencia, id_emisor, contenido)
                    VALUES (%s, %s, %s)
                    RETURNING id;
                    """,
                    (match_id, sender_id, contenido)
                )
                msg_id = cur.fetchone()[0]
            conn.commit()
            return msg_id
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def get_messages_by_match(self, match_id):
        """Retrieve messages for a specific match from PostgreSQL."""
        conn = get_postgres_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, id_emisor, contenido, fecha_envio
                    FROM mensajes
                    WHERE id_coincidencia = %s
                    ORDER BY fecha_envio ASC;
                    """,
                    (match_id,)
                )
                rows = cur.fetchall()
                results = []
                for row in rows:
                    results.append({
                        "id": row[0],
                        "id_emisor": row[1],
                        "contenido": row[2],
                        "fecha_envio": row[3]
                    })
                return results
        finally:
            conn.close()

    def create_notification(self, user_id, tipo, id_like=None, id_coincidencia=None, id_mensaje=None, id_evento=None):
        """Create a notification in PostgreSQL."""
        conn = get_postgres_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO notificaciones (id_usuario, tipo, id_like, id_coincidencia, id_mensaje, id_evento)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING id;
                    """,
                    (user_id, tipo, id_like, id_coincidencia, id_mensaje, id_evento)
                )
                notif_id = cur.fetchone()[0]
            conn.commit()
            return notif_id
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def upsert_interest(self, nombre):
        """Insert interest if not exists, return its ID."""
        conn = get_postgres_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO intereses (nombre)
                    VALUES (%s)
                    ON CONFLICT (nombre) DO NOTHING
                    RETURNING id;
                    """,
                    (nombre,)
                )
                row = cur.fetchone()
                if row:
                    interest_id = row[0]
                else:
                    cur.execute("SELECT id FROM intereses WHERE nombre = %s;", (nombre,))
                    interest_id = cur.fetchone()[0]
            conn.commit()
            return interest_id
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def update_user_interests(self, user_id, interest_names):
        """Update user's interests in PostgreSQL."""
        conn = get_postgres_connection()
        try:
            with conn.cursor() as cur:
                # Delete existing relations
                cur.execute("DELETE FROM usuario_intereses WHERE id_usuario = %s;", (user_id,))
                
                # Insert new ones
                for name in interest_names:
                    # First ensure interest exists (upsert)
                    cur.execute(
                        """
                        INSERT INTO intereses (nombre)
                        VALUES (%s)
                        ON CONFLICT (nombre) DO NOTHING
                        RETURNING id;
                        """,
                        (name,)
                    )
                    row = cur.fetchone()
                    if row:
                        interest_id = row[0]
                    else:
                        cur.execute("SELECT id FROM intereses WHERE nombre = %s;", (name,))
                        interest_id = cur.fetchone()[0]
                        
                    # Link to user
                    cur.execute(
                        """
                        INSERT INTO usuario_intereses (id_usuario, id_interes)
                        VALUES (%s, %s);
                        """,
                        (user_id, interest_id)
                    )
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def get_user_interests(self, user_id):
        """Retrieve a user's interest names from PostgreSQL."""
        conn = get_postgres_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT i.nombre
                    FROM usuario_intereses ui
                    JOIN intereses i ON i.id = ui.id_interes
                    WHERE ui.id_usuario = %s
                    ORDER BY i.nombre;
                    """,
                    (user_id,)
                )
                return [row[0] for row in cur.fetchall()]
        finally:
            conn.close()
