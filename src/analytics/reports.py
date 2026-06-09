import datetime
import uuid
import logging
from src.database.connection import (
    get_postgres_connection,
    get_mongodb_database,
    get_cassandra_session,
    get_neo4j_driver
)

logger = logging.getLogger(__name__)

# Hardcoded holidays in Argentina for Report 7
FERIADOS_ARG = {
    datetime.date(2026, 1, 1),    # Año Nuevo
    datetime.date(2026, 3, 24),   # Memoria
    datetime.date(2026, 4, 2),    # Malvinas
    datetime.date(2026, 5, 1),    # Día del Trabajador
    datetime.date(2026, 5, 25),   # Revolución de Mayo
    datetime.date(2026, 6, 20),   # Belgrano
    datetime.date(2026, 7, 9),    # Independencia
    datetime.date(2026, 12, 8),   # Inmaculada Concepción
    datetime.date(2026, 12, 25)   # Navidad
}

class ReportService:
    def __init__(self):
        pass

    # REPORT 1: Promedio de coincidencias por día
    def get_avg_matches_per_day(self, fecha_desde=None, fecha_hasta=None):
        """
        Cassandra: matches_por_dia
        Query: SELECT fecha FROM matches_por_dia WHERE fecha IN ?;
        """
        if fecha_hasta is None:
            fecha_hasta = datetime.date.today()
        if fecha_desde is None:
            fecha_desde = fecha_hasta - datetime.timedelta(days=90)
            
        fechas = [fecha_desde + datetime.timedelta(days=i) for i in range((fecha_hasta - fecha_desde).days + 1)]
        
        session = get_cassandra_session()
        stmt = session.prepare("SELECT fecha FROM matches_por_dia WHERE fecha IN ?;")
        rows = session.execute(stmt, [fechas])
        matches_by_day = {}
        for row in rows:
            fecha_str = str(row.fecha)
            matches_by_day[fecha_str] = matches_by_day.get(fecha_str, 0) + 1
        
        if not matches_by_day:
            return 0.0, {}
        
        avg = sum(matches_by_day.values()) / len(matches_by_day)
        return avg, matches_by_day

    # REPORT 2: Características más populares de los perfiles
    def get_popular_characteristics(self):
        """
        MongoDB: agregación sobre perfiles.caracteristicas
        Query: Mongo pipeline to project subdocument fields into an array, unwind, and group.
        """
        db = get_mongodb_database()
        pipeline = [
            {"$project": {"carac": {"$objectToArray": "$caracteristicas"}}},
            {"$unwind": "$carac"},
            {"$group": {
                "_id": {"clave": "$carac.k", "valor": "$carac.v"},
                "cantidad": {"$sum": 1}
            }},
            {"$sort": {"cantidad": -1}},
            {"$limit": 10}
        ]
        results = list(db.perfiles.aggregate(pipeline))
        formatted = []
        for r in results:
            formatted.append({
                "clave": r["_id"]["clave"],
                "valor": r["_id"]["valor"],
                "cantidad": r["cantidad"]
            })
        return formatted

    # REPORT 3: Perfiles que reciben más swipes a la derecha (Likes)
    def get_most_liked_profiles(self, user_ids=None):
        """
        Cassandra: swipes_recibidos_por_perfil
        Query: SELECT tipo FROM swipes_recibidos_por_perfil WHERE user_to = ? AND tipo = 'like';
        """
        if not user_ids:
            conn = get_postgres_connection()
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT id FROM users;")
                    user_ids = [row[0] for row in cur.fetchall()]
            finally:
                conn.close()

        session = get_cassandra_session()
        likes_count = {}
        stmt = session.prepare("SELECT tipo FROM swipes_recibidos_por_perfil WHERE user_to = ? AND tipo = 'like';")
        for u_id in user_ids:
            rows = session.execute(stmt, [u_id])
            count = sum(1 for _ in rows)
            if count > 0:
                likes_count[u_id] = count

        # Sort in Python (academic requirement)
        sorted_likes = sorted(likes_count.items(), key=lambda x: x[1], reverse=True)

        # Merge with PostgreSQL names for friendly output
        conn = get_postgres_connection()
        results = []
        try:
            with conn.cursor() as cur:
                for user_id, count in sorted_likes[:10]:
                    cur.execute("SELECT nombre FROM users WHERE id = %s;", (user_id,))
                    row = cur.fetchone()
                    nombre = row[0] if row else "Desconocido"
                    results.append({
                        "user_id": user_id,
                        "nombre": nombre,
                        "likes": count
                    })
        finally:
            conn.close()
        return results

    # REPORT 4: Duración promedio de conversaciones antes de una cita
    def get_avg_chat_duration_before_event(self):
        """
        PostgreSQL: matches and attendance to events.
        Cassandra: messages first timestamp.
        """
        pg_conn = get_postgres_connection()
        citas = []
        try:
            with pg_conn.cursor() as cur:
                cur.execute("""
                    SELECT c.id AS match_id, c.user_id_1, c.user_id_2, e.fecha_hora AS fecha_evento, e.titulo AS titulo_evento
                    FROM coincidencias_confirmadas c
                    JOIN asistencia_eventos a1 ON c.user_id_1 = a1.user_id
                    JOIN asistencia_eventos a2 ON c.user_id_2 = a2.user_id AND a1.evento_id = a2.evento_id
                    JOIN events e ON a1.evento_id = e.id;
                """)
                citas = cur.fetchall()
        finally:
            pg_conn.close()

        if not citas:
            return 0.0, []

        session = get_cassandra_session()
        durations = []
        details = []
        for match_id, u1, u2, fecha_evento, titulo_evento in citas:
            # Query first message in Cassandra
            stmt = session.prepare("SELECT timestamp FROM mensajes_por_conversacion WHERE match_id = ? LIMIT 1;")
            row = session.execute(stmt, [match_id]).one()
            if row:
                first_msg_time = row.timestamp
                # Convert both to offset-naive datetimes for safe comparison
                fe_naive = fecha_evento.replace(tzinfo=None) if fecha_evento.tzinfo else fecha_evento
                fmt_naive = first_msg_time.replace(tzinfo=None) if first_msg_time.tzinfo else first_msg_time
                if fe_naive > fmt_naive:
                    diff = (fe_naive - fmt_naive).total_seconds() / 3600.0  # hours
                    durations.append(diff)
                    details.append({
                        "match_id": match_id,
                        "user_1": u1,
                        "user_2": u2,
                        "evento": titulo_evento,
                        "primera_conve": first_msg_time,
                        "fecha_cita": fecha_evento,
                        "diferencia_horas": round(diff, 1)
                    })

        avg = sum(durations) / len(durations) if durations else 0.0
        return avg, details

    # REPORT 5: Intereses más comunes entre usuarios que hacen match
    def get_common_interests_in_matches(self):
        """
        Neo4j: MATCH_CON + TIENE_INTERES
        Query: Find mutual interests between matched users in graph.
        """
        query = """
        MATCH (u1:Usuario)-[:MATCH_CON]->(u2:Usuario)
        WHERE u1.id < u2.id
        MATCH (u1)-[:TIENE_INTERES]->(i:Interes)<-[:TIENE_INTERES]-(u2)
        RETURN i.nombre AS interes, count(*) AS cantidad
        ORDER BY cantidad DESC
        LIMIT 10;
        """
        driver = get_neo4j_driver()
        results = []
        try:
            with driver.session() as session:
                res = session.run(query)
                for row in res:
                    results.append({
                        "interes": row["interes"],
                        "cantidad": row["cantidad"]
                    })
        finally:
            driver.close()
        return results

    # REPORT 6: Usuarios con más de 10 fotos y al menos 3 intereses en común
    def get_rich_profiles_with_shared_interests(self):
        """
        MongoDB: filter perfiles with size(fotos) > 10
        Neo4j: calculate common interests among these user IDs
        """
        # 1. MongoDB
        db = get_mongodb_database()
        cursor = db.perfiles.find(
            {"$expr": {"$gt": [{"$size": "$fotos"}, 10]}},
            {"user_id": 1}
        )
        user_ids = [doc["user_id"] for doc in cursor]

        if len(user_ids) < 2:
            return []

        # 2. Neo4j
        query = """
        MATCH (u1:Usuario)-[:TIENE_INTERES]->(i:Interes)<-[:TIENE_INTERES]-(u2:Usuario)
        WHERE u1.id IN $user_ids AND u2.id IN $user_ids AND u1.id < u2.id
        WITH u1, u2, collect(i.nombre) AS comunes, count(i) AS cantidad
        WHERE cantidad >= 3
        RETURN u1.id AS id_1, u1.nombre AS nombre_1, u2.id AS id_2, u2.nombre AS nombre_2, comunes, cantidad
        ORDER BY cantidad DESC;
        """
        driver = get_neo4j_driver()
        results = []
        try:
            with driver.session() as session:
                res = session.run(query, user_ids=user_ids)
                for row in res:
                    results.append({
                        "id_1": row["id_1"],
                        "nombre_1": row["nombre_1"],
                        "id_2": row["id_2"],
                        "nombre_2": row["nombre_2"],
                        "comunes": row["comunes"],
                        "cantidad": row["cantidad"]
                    })
        finally:
            driver.close()
        return results

    # REPORT 7: Coincidencias ocurridas durante fines de semana o feriados
    def get_holiday_matches(self, fecha_desde=None, fecha_hasta=None):
        """
        Cassandra: matches_por_dia
        Python: filter Saturdays (5), Sundays (6) and hardcoded holidays
        """
        if fecha_hasta is None:
            fecha_hasta = datetime.date.today()
        if fecha_desde is None:
            fecha_desde = fecha_hasta - datetime.timedelta(days=90)
            
        fechas = [fecha_desde + datetime.timedelta(days=i) for i in range((fecha_hasta - fecha_desde).days + 1)]
        fechas_filtradas = [f for f in fechas if f.weekday() in (5, 6) or f in FERIADOS_ARG]

        if not fechas_filtradas:
            return []

        session = get_cassandra_session()
        raw_matches = []
        stmt = session.prepare("SELECT fecha, match_id, user_1, user_2 FROM matches_por_dia WHERE fecha IN ?;")
        rows = session.execute(stmt, [fechas_filtradas])
        for row in rows:
            raw_matches.append({
                "fecha": row.fecha,
                "match_id": row.match_id,
                "user_1": row.user_1,
                "user_2": row.user_2
            })

        filtered = []
        conn = get_postgres_connection()
        try:
            with conn.cursor() as cur:
                for m in raw_matches:
                    f = m["fecha"]  # date object
                    # Ensure f is a standard datetime.date object
                    if isinstance(f, datetime.datetime):
                        f = f.date()
                    elif hasattr(f, "date"):
                        f = f.date()
                    # Check weekend or holiday
                    is_weekend = f.weekday() in (5, 6)
                    is_holiday = f in FERIADOS_ARG
                    
                    if is_weekend or is_holiday:
                        # Fetch names
                        cur.execute("SELECT nombre FROM users WHERE id = %s;", (m["user_1"],))
                        row_1 = cur.fetchone()
                        name_1 = row_1[0] if row_1 else "Desconocido"

                        cur.execute("SELECT nombre FROM users WHERE id = %s;", (m["user_2"],))
                        row_2 = cur.fetchone()
                        name_2 = row_2[0] if row_2 else "Desconocido"

                        m_type = "Fin de Semana" if is_weekend else "Feriado"
                        if is_weekend and is_holiday:
                            m_type = "Fin de Semana + Feriado"

                        filtered.append({
                            "fecha": f,
                            "match_id": m["match_id"],
                            "user_1": m["user_1"],
                            "nombre_1": name_1,
                            "user_2": m["user_2"],
                            "nombre_2": name_2,
                            "tipo_dia": m_type
                        })
        finally:
            conn.close()

        return filtered

    # SEED DEMO DATA
    def seed_demo_data(self):
        """
        Seed mock users, likes, matches, messages, events, attendances across all 5 databases.
        Uses clean transaction flows to set up perfect relationships.
        """
        import hashlib
        
        # 1. Clean up existing test seed data to ensure idempotency
        # Seed users have emails like: * @testseed.com
        logger.info("Eliminando datos semilla previos...")
        pg_conn = get_postgres_connection()
        try:
            with pg_conn.cursor() as cur:
                # Get seed user IDs
                cur.execute("SELECT id FROM users WHERE email LIKE '%@testseed.com';")
                seed_ids = [row[0] for row in cur.fetchall()]
                
                if seed_ids:
                    # Cascade deletions via Postgres
                    cur.execute("DELETE FROM users WHERE id IN %s;", (tuple(seed_ids),))
                    pg_conn.commit()
        finally:
            pg_conn.close()

        # Clean Mongo
        mongo_db = get_mongodb_database()
        mongo_db.perfiles.delete_many({"user_id": {"$in": seed_ids} if seed_ids else {"$exists": True}}) # Delete seed perfiles
        mongo_db.notificaciones.delete_many({})
        mongo_db.bloqueos.delete_many({})
        mongo_db.eventos_logs.delete_many({})

        # Clean Neo4j
        neo4j_driver = get_neo4j_driver()
        try:
            with neo4j_driver.session() as session:
                session.run("MATCH (u:Usuario) WHERE u.id IN $seed_ids DETACH DELETE u;", seed_ids=seed_ids)
                session.run("MATCH (e:Evento) DETACH DELETE e;")
        finally:
            neo4j_driver.close()

        # Clean Cassandra (Truncate keyspace tables for demo simplicity)
        session = get_cassandra_session()
        try:
            session.execute("TRUNCATE swipes_por_dia;")
            session.execute("TRUNCATE swipes_recibidos_por_perfil;")
            session.execute("TRUNCATE matches_por_dia;")
            session.execute("TRUNCATE mensajes_por_conversacion;")
            session.execute("TRUNCATE actividad_usuario_por_fecha;")
        except Exception as e:
            logger.warning(f"Error truncating Cassandra tables: {e}")

        # 2. Insert new mock users into PostgreSQL
        logger.info("Creando nuevos usuarios semilla...")
        seed_users = [
            ("Carlos", "carlos@testseed.com", 28, "Masculino", "Buenos Aires"),
            ("Sofia", "sofia@testseed.com", 26, "Femenino", "Buenos Aires"),
            ("Mateo", "mateo@testseed.com", 29, "Masculino", "Buenos Aires"),
            ("Valentina", "valentina@testseed.com", 27, "Femenino", "Buenos Aires"),
            ("Lucia", "lucia@testseed.com", 25, "Femenino", "Buenos Aires"),
            ("Diego", "diego@testseed.com", 30, "Masculino", "Buenos Aires"),
            ("Camila", "camila@testseed.com", 24, "Femenino", "Buenos Aires"),
            ("Nicolas", "nicolas@testseed.com", 31, "Masculino", "Buenos Aires")
        ]
        
        pg_conn = get_postgres_connection()
        user_ids = {}
        pass_hash = hashlib.sha256("password123".encode("utf-8")).hexdigest()
        
        # Characteristics map
        chars_map = {
            "Carlos": {"signo": "Escorpio", "altura": 178, "color_pelo": "Castaño"},
            "Sofia": {"signo": "Piscis", "altura": 165, "color_pelo": "Rubio"},
            "Mateo": {"signo": "Escorpio", "altura": 182, "color_pelo": "Castaño"},
            "Valentina": {"signo": "Escorpio", "altura": 170, "color_pelo": "Castaño"},
            "Lucia": {"signo": "Aries", "altura": 160, "color_pelo": "Rubio"},
            "Diego": {"signo": "Tauro", "altura": 180, "color_pelo": "Castaño"},
            "Camila": {"signo": "Virgo", "altura": 168, "color_pelo": "Negro"},
            "Nicolas": {"signo": "Escorpio", "altura": 175, "color_pelo": "Negro"}
        }
        
        try:
            with pg_conn.cursor() as cur:
                for nombre, email, edad, genero, ubicacion in seed_users:
                    # Also set biografia and preferences in Postgres
                    bio = f"Hola, soy {nombre} y busco conocer gente."
                    cur.execute(
                        """
                        INSERT INTO users (nombre, email, password_hash, edad, genero, ubicacion, biografia, pref_edad_min, pref_edad_max)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING id;
                        """,
                        (nombre, email, pass_hash, edad, genero, ubicacion, bio, 20, 35)
                    )
                    user_ids[nombre] = cur.fetchone()[0]
            pg_conn.commit()
        finally:
            pg_conn.close()

        # 3. Create MongoDB Profiles
        logger.info("Creando perfiles documentales en MongoDB...")
        # Number of photos per user (Carlos, Sofia and Valentina have > 10 photos!)
        photos_map = {
            "Carlos": [f"carlos_img_{i}.jpg" for i in range(11)],
            "Sofia": [f"sofia_img_{i}.jpg" for i in range(12)],
            "Mateo": ["mateo1.jpg", "mateo2.jpg"],
            "Valentina": [f"valen_img_{i}.jpg" for i in range(13)],
            "Lucia": ["lucia.jpg"],
            "Diego": ["diego.jpg"],
            "Camila": ["camila.jpg"],
            "Nicolas": ["nicolas.jpg"]
        }
        
        # Sincronizar Fotos en PostgreSQL
        pg_conn = get_postgres_connection()
        try:
            with pg_conn.cursor() as cur:
                for nombre, photos in photos_map.items():
                    u_id = user_ids[nombre]
                    for idx, photo in enumerate(photos):
                        es_principal = (idx == 0)
                        cur.execute(
                            "INSERT INTO fotos (id_usuario, url_archivo, es_principal) VALUES (%s, %s, %s)",
                            (u_id, photo, es_principal)
                        )
            pg_conn.commit()
        finally:
            pg_conn.close()

        db = get_mongodb_database()
        for nombre, u_id in user_ids.items():
            db.perfiles.insert_one({
                "user_id": u_id,
                "biografia": f"Hola, soy {nombre} y busco conocer gente.",
                "fotos": photos_map.get(nombre, []),
                "preferencias": {
                    "edad_min": 20,
                    "edad_max": 35,
                    "genero_interes": "Cualquiera"
                },
                "caracteristicas": chars_map.get(nombre, {}),
                "created_at": datetime.datetime.utcnow(),
                "updated_at": datetime.datetime.utcnow()
            })

        # 4. Create Neo4j Nodes and Interests Relationships
        logger.info("Creando nodos y relaciones de intereses en Neo4j...")
        # Interests list
        interests_map = {
            "Carlos": ["Cine", "Rock", "Cocina", "Fútbol"],
            "Sofia": ["Cine", "Rock", "Cocina", "Viajes"],
            "Mateo": ["Viajes", "Fútbol", "Cine"],
            "Valentina": ["Cine", "Rock", "Cocina", "Lectura", "Running"],
            "Lucia": ["Lectura", "Cine", "Pop"],
            "Diego": ["Fútbol", "Rock", "Asado"],
            "Camila": ["Viajes", "Pop", "Running"],
            "Nicolas": ["Rock", "Fútbol", "Motos"]
        }

        neo4j_driver = get_neo4j_driver()
        pg_conn = get_postgres_connection()
        try:
            # Sync Intereses in PG
            with pg_conn.cursor() as cur:
                for nombre, interests in interests_map.items():
                    u_id = user_ids[nombre]
                    for it_name in interests:
                        # Upsert interest
                        cur.execute("INSERT INTO intereses (nombre) VALUES (%s) ON CONFLICT DO NOTHING RETURNING id;", (it_name,))
                        row = cur.fetchone()
                        if row:
                            interest_id = row[0]
                        else:
                            cur.execute("SELECT id FROM intereses WHERE nombre = %s;", (it_name,))
                            interest_id = cur.fetchone()[0]
                            
                        # Link to user
                        cur.execute("INSERT INTO usuario_intereses (id_usuario, id_interes) VALUES (%s, %s) ON CONFLICT DO NOTHING;", (u_id, interest_id))
            pg_conn.commit()

            with neo4j_driver.session() as session:
                # Create Usuario nodes
                for nombre, u_id in user_ids.items():
                    session.run("MERGE (u:Usuario {id: $u_id}) SET u.nombre = $nombre;", u_id=u_id, nombre=nombre)
                
                # Create TIENE_INTERES relationships
                for nombre, interests in interests_map.items():
                    u_id = user_ids[nombre]
                    for it_name in interests:
                        session.run("""
                            MERGE (i:Interes {nombre: $it_name})
                            WITH i
                            MATCH (u:Usuario {id: $u_id})
                            MERGE (u)-[:TIENE_INTERES]->(i);
                        """, u_id=u_id, it_name=it_name)
        finally:
            neo4j_driver.close()
            pg_conn.close()

        # 5. Create confirmed matches and Neo4j MATCH_CON edges
        logger.info("Generando matches y relaciones MATCH_CON...")
        matches_to_create = [
            # Carlos (1) and Sofia (2) -> Match on Sunday (Weekend!)
            ("Carlos", "Sofia", datetime.date(2026, 6, 7), datetime.datetime(2026, 6, 7, 10, 0, 0)),
            # Mateo (3) and Valentina (4) -> Match on Friday
            ("Mateo", "Valentina", datetime.date(2026, 6, 5), datetime.datetime(2026, 6, 5, 15, 0, 0)),
            # Carlos (1) and Valentina (4) -> Match on Thursday
            ("Carlos", "Valentina", datetime.date(2026, 6, 4), datetime.datetime(2026, 6, 4, 18, 0, 0)),
            # Diego (6) and Lucia (5) -> Match on May 1st (Argentine holiday!)
            ("Diego", "Lucia", datetime.date(2026, 5, 1), datetime.datetime(2026, 5, 1, 9, 0, 0))
        ]

        pg_conn = get_postgres_connection()
        created_matches = [] # list of (match_id, u1_id, u2_id, date, timestamp)
        try:
            with pg_conn.cursor() as cur:
                for name_a, name_b, m_date, m_ts in matches_to_create:
                    id_a = user_ids[name_a]
                    id_b = user_ids[name_b]
                    u1, u2 = min(id_a, id_b), max(id_a, id_b)
                    
                    cur.execute(
                        """
                        INSERT INTO coincidencias_confirmadas (user_id_1, user_id_2, created_at)
                        VALUES (%s, %s, %s)
                        RETURNING id;
                        """,
                        (u1, u2, m_ts)
                    )
                    match_id = cur.fetchone()[0]
                    created_matches.append((match_id, id_a, id_b, m_date, m_ts))
            pg_conn.commit()
        finally:
            pg_conn.close()

        # Neo4j MATCH_CON upgrade
        neo4j_driver = get_neo4j_driver()
        try:
            with neo4j_driver.session() as session:
                for _, id_a, id_b, _, _ in created_matches:
                    session.run("""
                        MATCH (u1:Usuario {id: $id_a})
                        MATCH (u2:Usuario {id: $id_b})
                        MERGE (u1)-[:MATCH_CON]->(u2)
                        MERGE (u2)-[:MATCH_CON]->(u1);
                    """, id_a=id_a, id_b=id_b)
        finally:
            neo4j_driver.close()

        # 6. Seed Cassandra logs
        logger.info("Registrando eventos históricos de swipes y matches en Cassandra...")
        cassandra_session = get_cassandra_session()
        # Seed matches in Cassandra
        insert_match_c = cassandra_session.prepare("""
            INSERT INTO matches_por_dia (fecha, match_id, user_1, user_2, timestamp)
            VALUES (?, ?, ?, ?, ?);
        """)
        for m_id, id_a, id_b, m_date, m_ts in created_matches:
            cassandra_session.execute(insert_match_c, [m_date, m_id, id_a, id_b, m_ts])

        # Seed Swipes in Cassandra (Sofia received 3 likes, Carlos received 2)
        # Sofia (User 2) received:
        # - Carlos (1)
        # - Mateo (3)
        # - Diego (6)
        # Carlos (User 1) received:
        # - Sofia (2)
        # - Valentina (4)
        swipes = [
            (user_ids["Carlos"], user_ids["Sofia"], "like"),
            (user_ids["Mateo"], user_ids["Sofia"], "like"),
            (user_ids["Diego"], user_ids["Sofia"], "like"),
            (user_ids["Sofia"], user_ids["Carlos"], "like"),
            (user_ids["Valentina"], user_ids["Carlos"], "like"),
            (user_ids["Nicolas"], user_ids["Lucia"], "dislike")
        ]

        insert_swipe_c = cassandra_session.prepare("""
            INSERT INTO swipes_recibidos_por_perfil (user_to, tipo, swipe_id, user_from, fecha)
            VALUES (?, ?, ?, ?, ?);
        """)
        
        pg_conn = get_postgres_connection()
        with pg_conn.cursor() as cur:
            for u_from, u_to, s_type in swipes:
                cassandra_session.execute(insert_swipe_c, [u_to, s_type, uuid.uuid4(), u_from, datetime.datetime.utcnow()])
                # Sincronizar Like en PostgreSQL
                cur.execute(
                    "INSERT INTO likes (id_usuario_origen, id_usuario_destino, tipo) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING;",
                    (u_from, u_to, s_type)
                )
        pg_conn.commit()
        pg_conn.close()

        # Seed Messages in Cassandra (First messages for Report 4)
        insert_msg_c = cassandra_session.prepare("""
            INSERT INTO mensajes_por_conversacion (match_id, timestamp, message_id, sender_id, texto)
            VALUES (?, ?, ?, ?, ?);
        """)
        
        pg_conn = get_postgres_connection()
        with pg_conn.cursor() as cur:
            for m_id, id_a, id_b, _, m_ts in created_matches:
                # Add first message exactly at the match timestamp
                cassandra_session.execute(insert_msg_c, [m_id, m_ts, uuid.uuid4(), id_a, "¡Hola! ¿Cómo estás?"])
                cur.execute("INSERT INTO mensajes (id_coincidencia, id_emisor, contenido) VALUES (%s, %s, %s);", (m_id, id_a, "¡Hola! ¿Cómo estás?"))
                
                # Add a reply 5 minutes later
                reply_ts = m_ts + datetime.timedelta(minutes=5)
                cassandra_session.execute(insert_msg_c, [m_id, reply_ts, uuid.uuid4(), id_b, "¡Hola! Todo bien por suerte, ¿vos?"])
                cur.execute("INSERT INTO mensajes (id_coincidencia, id_emisor, contenido) VALUES (%s, %s, %s);", (m_id, id_b, "¡Hola! Todo bien por suerte, ¿vos?"))
        pg_conn.commit()
        pg_conn.close()

        # 7. Create Events and Attendances in PostgreSQL & Neo4j
        logger.info("Creando eventos sociales y registros de asistencia...")
        # Carlos organizes Tango & Wine on Sunday, June 7 at 20:00.
        # Sofia registers to attend this event.
        # Match time: 2026-06-07 10:00:00
        # Event time: 2026-06-07 20:00:00
        # Time difference: 10 hours!
        
        # Diego organizes Rock Festival on Saturday, June 6 at 21:00.
        # Lucia registers to attend this event.
        # Match time: 2026-05-01 09:00:00
        # Event time: 2026-06-06 21:00:00
        # Time difference: 36 days and 12 hours (876 hours)
        
        events_to_create = [
            ("Carlos", "Tango & Wine", "Una noche de baile y buen vino", "Palermo", datetime.datetime(2026, 6, 7, 20, 0, 0)),
            ("Diego", "Rock Festival", "Bandas en vivo y cerveza artesanal", "San Telmo", datetime.datetime(2026, 6, 6, 21, 0, 0))
        ]

        pg_conn = get_postgres_connection()
        created_events = [] # list of (event_id, organizer_id, title, date)
        try:
            with pg_conn.cursor() as cur:
                for org_name, title, desc, loc, ev_dt in events_to_create:
                    org_id = user_ids[org_name]
                    cur.execute(
                        """
                        INSERT INTO events (organizador_id, titulo, descripcion, ubicacion, fecha_hora)
                        VALUES (%s, %s, %s, %s, %s)
                        RETURNING id;
                        """,
                        (org_id, title, desc, loc, ev_dt)
                    )
                    ev_id = cur.fetchone()[0]
                    created_events.append((ev_id, org_id, title, ev_dt))
            pg_conn.commit()
        finally:
            pg_conn.close()

        # Neo4j organizer and event nodes
        neo4j_driver = get_neo4j_driver()
        try:
            with neo4j_driver.session() as session:
                for ev_id, org_id, title, _ in created_events:
                    session.run("MERGE (e:Evento {id: $ev_id}) SET e.titulo = $title;", ev_id=ev_id, title=title)
                    session.run("""
                        MATCH (u:Usuario {id: $org_id})
                        MATCH (e:Evento {id: $ev_id})
                        MERGE (u)-[:ORGANIZA]->(e);
                    """, org_id=org_id, ev_id=ev_id)
        finally:
            neo4j_driver.close()

        # Seed Attendances
        attendances = [
            # Event 1: Carlos is organizer (Carlos attends by default, but let's register Sofia)
            ("Sofia", "Tango & Wine"),
            ("Carlos", "Tango & Wine"),
            # Event 2: Diego is organizer, Lucia registers
            ("Lucia", "Rock Festival"),
            ("Diego", "Rock Festival")
        ]

        # Find event ID helper
        event_ids_map = {title: ev_id for ev_id, _, title, _ in created_events}

        pg_conn = get_postgres_connection()
        try:
            with pg_conn.cursor() as cur:
                for attendee_name, event_title in attendances:
                    u_id = user_ids[attendee_name]
                    e_id = event_ids_map[event_title]
                    cur.execute(
                        """
                        INSERT INTO asistencia_eventos (user_id, evento_id)
                        VALUES (%s, %s)
                        ON CONFLICT DO NOTHING;
                        """,
                        (u_id, e_id)
                    )
            pg_conn.commit()
        finally:
            pg_conn.close()

        # Neo4j ASISTE_A relations
        neo4j_driver = get_neo4j_driver()
        try:
            with neo4j_driver.session() as session:
                for attendee_name, event_title in attendances:
                    u_id = user_ids[attendee_name]
                    e_id = event_ids_map[event_title]
                    session.run("""
                        MATCH (u:Usuario {id: $u_id})
                        MATCH (e:Evento {id: $e_id})
                        MERGE (u)-[:ASISTE_A]->(e);
                    """, u_id=u_id, e_id=e_id)
        finally:
            neo4j_driver.close()

        # 8. Seed Blocks (Camila blocks Nicolas)
        logger.info("Creando relaciones de bloqueo de prueba...")
        id_camila = user_ids["Camila"]
        id_nicolas = user_ids["Nicolas"]

        # Neo4j block relationship
        neo4j_driver = get_neo4j_driver()
        try:
            with neo4j_driver.session() as session:
                session.run("""
                    MATCH (u1:Usuario {id: $id_camila})
                    MATCH (u2:Usuario {id: $id_nicolas})
                    MERGE (u1)-[:BLOQUEO]->(u2);
                """, id_camila=id_camila, id_nicolas=id_nicolas)
        finally:
            neo4j_driver.close()

        # PostgreSQL block audit
        pg_conn = get_postgres_connection()
        try:
            with pg_conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO bloqueos_auditoria (bloqueador_id, bloqueado_id, fecha)
                    VALUES (%s, %s, NOW());
                    """,
                    (id_camila, id_nicolas)
                )
            pg_conn.commit()
        finally:
            pg_conn.close()

        # MongoDB block document
        db = get_mongodb_database()
        db.bloqueos.insert_one({
            "bloqueador_id": id_camila,
            "bloqueado_id": id_nicolas,
            "timestamp": datetime.datetime.utcnow()
        })

        # 9. Seed Notifications in MongoDB
        logger.info("Creando notificaciones de prueba...")
        id_carlos = user_ids["Carlos"]
        id_diego = user_ids["Diego"]
        id_lucia = user_ids["Lucia"]

        db.notificaciones.insert_many([
            {
                "user_id": id_carlos,
                "mensaje": "Sofia se inscribió a tu evento: 'Tango & Wine'",
                "tipo": "evento_asistencia",
                "leido": False,
                "timestamp": datetime.datetime.utcnow()
            },
            {
                "user_id": id_diego,
                "mensaje": "¡Tienes un nuevo match con Lucia!",
                "tipo": "match",
                "leido": False,
                "timestamp": datetime.datetime.utcnow()
            },
            {
                "user_id": id_lucia,
                "mensaje": "Nuevo mensaje de Diego: '¡Hola! ¿Cómo estás?'",
                "tipo": "mensaje",
                "leido": False,
                "timestamp": datetime.datetime.utcnow()
            }
        ])

        # Sincronizar notificaciones en PostgreSQL
        pg_conn = get_postgres_connection()
        try:
            with pg_conn.cursor() as cur:
                cur.execute("INSERT INTO notificaciones (id_usuario, tipo) VALUES (%s, %s)", (id_carlos, "evento_asistencia"))
                cur.execute("INSERT INTO notificaciones (id_usuario, tipo) VALUES (%s, %s)", (id_diego, "match"))
                cur.execute("INSERT INTO notificaciones (id_usuario, tipo) VALUES (%s, %s)", (id_lucia, "mensaje"))
            pg_conn.commit()
        finally:
            pg_conn.close()

        logger.info("=== BASE DE DATOS POBLADA EXITOSAMENTE CON DATOS DEMO ===")
