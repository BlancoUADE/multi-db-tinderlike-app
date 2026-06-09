import sys
import hashlib
import json
from datetime import datetime, date, timedelta
from app.databases.postgres_conn import get_postgres_connection
from app.databases.redis_conn import get_redis_client
from app.databases.mongo_conn import get_mongo_db
from app.databases.cassandra_conn import get_cassandra_session
from app.databases.neo4j_conn import get_neo4j_driver

class Seeder:
    def __init__(self):
        pass

    def wipe_databases(self):
        print("Limpiando bases de datos para seed...")
        
        # 1. PostgreSQL
        conn = get_postgres_connection()
        cur = conn.cursor()
        cur.execute("""
            TRUNCATE TABLE 
                usuarios, intereses, usuario_intereses, fotos, likes, 
                coincidencias, mensajes, bloqueos, eventos, 
                asistencia_eventos, notificaciones, feriados 
            RESTART IDENTITY CASCADE;
        """)
        conn.commit()
        cur.close()
        conn.close()
        print("- PostgreSQL limpia.")

        # 2. Redis
        r = get_redis_client()
        r.flushall()
        print("- Redis limpia.")

        # 3. MongoDB
        db = get_mongo_db()
        db.perfiles_publicos.delete_many({})
        db.actividad_importante.delete_many({})
        print("- MongoDB limpia.")

        # 4. Cassandra
        cluster, session = get_cassandra_session()
        session.execute("TRUNCATE estadisticas_coincidencias_por_dia;")
        session.execute("TRUNCATE mensajes_por_evento;")
        print("- Cassandra limpia.")

        # 5. Neo4j
        driver = get_neo4j_driver()
        with driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
        driver.close()
        print("- Neo4j limpia.")

    def hash_password(self, password):
        return hashlib.sha256(password.encode("utf-8")).hexdigest()

    def run(self):
        self.wipe_databases()
        print("Iniciando carga de datos...")

        # Setup base timestamps relative to today
        today = date.today()
        today_dt = datetime.now()
        
        day_0 = today
        day_1_ago = today - timedelta(days=1)
        day_2_ago = today - timedelta(days=2)
        day_3_ago = today - timedelta(days=3)
        day_4_ago = today - timedelta(days=4)
        day_5_ago = today - timedelta(days=5)

        # -------------------------------------------------------------
        # 1. POBLAR FUENTE DE VERDAD: POSTGRESQL
        # -------------------------------------------------------------
        print("Poblando PostgreSQL...")
        pg_conn = get_postgres_connection()
        pg_cur = pg_conn.cursor()

        # 1.1 Feriados
        feriados = [
            (day_1_ago.strftime("%Y-%m-%d"), "Feriado Histórico"),
            ("2026-01-01", "Año Nuevo"),
            ("2026-05-25", "Revolución de Mayo"),
            ("2026-07-09", "Día de la Independencia"),
            ("2026-12-25", "Navidad")
        ]
        for f_date, desc in feriados:
            pg_cur.execute("""
                INSERT INTO feriados (fecha, descripcion) VALUES (%s, %s)
                ON CONFLICT (fecha) DO UPDATE SET descripcion = %s
            """, (f_date, desc, desc))

        # 1.2 Usuarios (Registrados en el Día -5)
        usuarios_data = [
            {"nombre": "Martina", "edad": 26, "genero": "F", "ubicacion": "CABA", "biografia": "Me gusta el cine y viajar", "pref_edad_min": 22, "pref_edad_max": 30, "email": "martina@example.com", "password": "password123", "foto": "martina_perfil.jpg", "intereses": "cine,viajar,musica,fotografia"},
            {"nombre": "Sofia", "edad": 28, "genero": "F", "ubicacion": "CABA", "biografia": "Lectura y buen café", "pref_edad_min": 24, "pref_edad_max": 32, "email": "sofia@example.com", "password": "password123", "foto": "sofia_perfil.jpg", "intereses": "lectura,musica,arte"},
            {"nombre": "Juan", "edad": 27, "genero": "M", "ubicacion": "CABA", "biografia": "Fan de los deportes y cocinar", "pref_edad_min": 23, "pref_edad_max": 30, "email": "juan@example.com", "password": "password123", "foto": "juan_perfil.jpg", "intereses": "deportes,gastronomia,musica,cine"},
            {"nombre": "Mateo", "edad": 25, "genero": "M", "ubicacion": "GBA", "biografia": "Programador y melómano", "pref_edad_min": 20, "pref_edad_max": 28, "email": "mateo@example.com", "password": "password123", "foto": "mateo_perfil.jpg", "intereses": "musica,tecnologia,viajar"},
            {"nombre": "Camila", "edad": 23, "genero": "F", "ubicacion": "Rosario", "biografia": "Amo la fotografía y los animales", "pref_edad_min": 21, "pref_edad_max": 30, "email": "camila@example.com", "password": "password123", "foto": "camila_perfil.jpg", "intereses": "fotografia,arte,viajar"},
            {"nombre": "Nicolas", "edad": 31, "genero": "M", "ubicacion": "CABA", "biografia": "Apasionado por la tecnología", "pref_edad_min": 26, "pref_edad_max": 35, "email": "nicolas@example.com", "password": "password123", "foto": "nicolas_perfil.jpg", "intereses": "tecnologia,deportes,cine"},
            {"nombre": "Valentina", "edad": 24, "genero": "F", "ubicacion": "GBA", "biografia": "Estudiante de arte", "pref_edad_min": 22, "pref_edad_max": 29, "email": "valentina@example.com", "password": "password123", "foto": "valentina_perfil.jpg", "intereses": "arte,fotografia,lectura,cine"},
            {"nombre": "Lucas", "edad": 29, "genero": "M", "ubicacion": "Rosario", "biografia": "Viajero frecuente", "pref_edad_min": 22, "pref_edad_max": 33, "email": "lucas@example.com", "password": "password123", "foto": "lucas_perfil.jpg", "intereses": "viajar,gastronomia,deportes"},
            {"nombre": "Agustina", "edad": 32, "genero": "F", "ubicacion": "CABA", "biografia": "Amo la gastronomía gourmet", "pref_edad_min": 28, "pref_edad_max": 36, "email": "agustina@example.com", "password": "password123", "foto": "agustina_perfil.jpg", "intereses": "gastronomia,viajar,arte"},
            {"nombre": "Joaquin", "edad": 30, "genero": "M", "ubicacion": "CABA", "biografia": "Música clásica e historia", "pref_edad_min": 25, "pref_edad_max": 33, "email": "joaquin@example.com", "password": "password123", "foto": "joaquin_perfil.jpg", "intereses": "musica,lectura,cine"},
            {"nombre": "Diego", "edad": 25, "genero": "M", "ubicacion": "CABA", "biografia": "Amante de la fotografía y trekking", "pref_edad_min": 20, "pref_edad_max": 30, "email": "diego@example.com", "password": "password123", "foto": "diego_foto_1.jpg", "intereses": "fotografia,viajar,cine,deportes,musica"}
        ]
        
        # Setup specific registration dates per user to give realistic scheduling variations
        user_reg_dates = {
            "Nicolas": datetime.combine(day_5_ago, datetime.min.time()) + timedelta(hours=8, minutes=32, seconds=15),
            "Sofia": datetime.combine(day_5_ago, datetime.min.time()) + timedelta(hours=9, minutes=45, seconds=10),
            "Mateo": datetime.combine(day_5_ago, datetime.min.time()) + timedelta(hours=14, minutes=10, seconds=0),
            "Martina": datetime.combine(day_4_ago, datetime.min.time()) + timedelta(hours=10, minutes=15, seconds=30),
            "Juan": datetime.combine(day_4_ago, datetime.min.time()) + timedelta(hours=11, minutes=22, seconds=45),
            "Camila": datetime.combine(day_3_ago, datetime.min.time()) + timedelta(hours=14, minutes=5, seconds=12),
            "Lucas": datetime.combine(day_3_ago, datetime.min.time()) + timedelta(hours=15, minutes=40, seconds=55),
            "Valentina": datetime.combine(day_2_ago, datetime.min.time()) + timedelta(hours=9, minutes=12, seconds=40),
            "Diego": datetime.combine(day_2_ago, datetime.min.time()) + timedelta(hours=12, minutes=50, seconds=20),
            "Agustina": datetime.combine(day_1_ago, datetime.min.time()) + timedelta(hours=8, minutes=20, seconds=11),
            "Joaquin": datetime.combine(day_1_ago, datetime.min.time()) + timedelta(hours=16, minutes=35, seconds=48)
        }

        # Sort users chronologically by registration date/time to make database IDs chronological
        usuarios_data.sort(key=lambda u: user_reg_dates[u["nombre"]])

        name_to_id = {}
        for u in usuarios_data:
            pw_hash = self.hash_password(u["password"])
            fecha_reg = user_reg_dates[u["nombre"]]
            pg_cur.execute("""
                INSERT INTO usuarios (nombre, edad, genero, ubicacion, biografia, pref_edad_min, pref_edad_max, email, password_hash, fecha_registro)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id_usuario;
            """, (u["nombre"], u["edad"], u["genero"], u["ubicacion"], u["biografia"], u["pref_edad_min"], u["pref_edad_max"], u["email"], pw_hash, fecha_reg))
            uid = pg_cur.fetchone()[0]
            name_to_id[u["nombre"]] = uid

        # 1.3 Intereses
        unique_interests = set()
        for u in usuarios_data:
            for i in u["intereses"].split(","):
                unique_interests.add(i.strip().lower())
                
        interest_to_id = {}
        for interest_name in unique_interests:
            pg_cur.execute("""
                INSERT INTO intereses (nombre) VALUES (%s)
                ON CONFLICT (nombre) DO UPDATE SET nombre = EXCLUDED.nombre
                RETURNING id_interes;
            """, (interest_name,))
            interest_to_id[interest_name] = pg_cur.fetchone()[0]

        # 1.4 Mapear intereses a usuarios
        for u in usuarios_data:
            uid = name_to_id[u["nombre"]]
            for i in u["intereses"].split(","):
                i_clean = i.strip().lower()
                iid = interest_to_id[i_clean]
                pg_cur.execute("""
                    INSERT INTO usuario_intereses (id_usuario, id_interes) VALUES (%s, %s)
                    ON CONFLICT DO NOTHING;
                """, (uid, iid))

        # 1.5 Fotos (con fecha de subida relativa a la fecha de registro individual)
        for u in usuarios_data:
            uid = name_to_id[u["nombre"]]
            fecha_reg = user_reg_dates[u["nombre"]]
            fecha_foto = fecha_reg + timedelta(minutes=12, seconds=30)
            # Principal
            pg_cur.execute("""
                INSERT INTO fotos (id_usuario, url_archivo, es_principal, fecha_subida)
                VALUES (%s, %s, TRUE, %s);
            """, (uid, u["foto"], fecha_foto))
            
            # Adicionales
            if u["nombre"] == "Diego":
                for idx in range(2, 12):
                    pg_cur.execute("""
                        INSERT INTO fotos (id_usuario, url_archivo, es_principal, fecha_subida)
                        VALUES (%s, %s, FALSE, %s);
                    """, (uid, f"diego_foto_{idx}.jpg", fecha_foto))
            else:
                pg_cur.execute("""
                    INSERT INTO fotos (id_usuario, url_archivo, es_principal, fecha_subida)
                    VALUES (%s, %s, FALSE, %s);
                """, (uid, f"{u['nombre'].lower()}_adicional.jpg", fecha_foto))

        # 1.6 Likes y Coincidencias
        # Nicolas <-> Sofia (Día -1 - Lunes - Feriado)
        dt_nic_like = datetime.combine(day_1_ago, datetime.min.time()) + timedelta(hours=10, minutes=5, seconds=10)
        dt_sof_like = dt_nic_like + timedelta(minutes=24, seconds=45)
        pg_cur.execute("INSERT INTO likes (id_usuario_origen, id_usuario_destino, fecha_like) VALUES (%s, %s, %s);", (name_to_id["Nicolas"], name_to_id["Sofia"], dt_nic_like))
        pg_cur.execute("INSERT INTO likes (id_usuario_origen, id_usuario_destino, fecha_like) VALUES (%s, %s, %s);", (name_to_id["Sofia"], name_to_id["Nicolas"], dt_sof_like))
        pg_cur.execute("""
            INSERT INTO coincidencias (id_usuario1, id_usuario2, fecha_coincidencia, fecha_feriado)
            VALUES (%s, %s, %s, %s) RETURNING id_coincidencia;
        """, (min(name_to_id["Nicolas"], name_to_id["Sofia"]), max(name_to_id["Nicolas"], name_to_id["Sofia"]), dt_sof_like, day_1_ago))
        coin_nic_sof = pg_cur.fetchone()[0]

        # Juan <-> Martina (Día -1 - Lunes - Feriado)
        dt_jua_like = datetime.combine(day_1_ago, datetime.min.time()) + timedelta(hours=14, minutes=12, seconds=30)
        dt_mar_like = dt_jua_like + timedelta(minutes=8, seconds=15)
        pg_cur.execute("INSERT INTO likes (id_usuario_origen, id_usuario_destino, fecha_like) VALUES (%s, %s, %s);", (name_to_id["Juan"], name_to_id["Martina"], dt_jua_like))
        pg_cur.execute("INSERT INTO likes (id_usuario_origen, id_usuario_destino, fecha_like) VALUES (%s, %s, %s);", (name_to_id["Martina"], name_to_id["Juan"], dt_mar_like))
        pg_cur.execute("""
            INSERT INTO coincidencias (id_usuario1, id_usuario2, fecha_coincidencia, fecha_feriado)
            VALUES (%s, %s, %s, %s) RETURNING id_coincidencia;
        """, (min(name_to_id["Juan"], name_to_id["Martina"]), max(name_to_id["Juan"], name_to_id["Martina"]), dt_mar_like, day_1_ago))
        coin_jua_mar = pg_cur.fetchone()[0]

        # Lucas <-> Camila (Día -1 - Lunes - Feriado)
        dt_luc_like = datetime.combine(day_1_ago, datetime.min.time()) + timedelta(hours=18, minutes=22, seconds=40)
        dt_cam_like = dt_luc_like + timedelta(minutes=11, seconds=10)
        pg_cur.execute("INSERT INTO likes (id_usuario_origen, id_usuario_destino, fecha_like) VALUES (%s, %s, %s);", (name_to_id["Lucas"], name_to_id["Camila"], dt_luc_like))
        pg_cur.execute("INSERT INTO likes (id_usuario_origen, id_usuario_destino, fecha_like) VALUES (%s, %s, %s);", (name_to_id["Camila"], name_to_id["Lucas"], dt_cam_like))
        pg_cur.execute("""
            INSERT INTO coincidencias (id_usuario1, id_usuario2, fecha_coincidencia, fecha_feriado)
            VALUES (%s, %s, %s, %s) RETURNING id_coincidencia;
        """, (min(name_to_id["Lucas"], name_to_id["Camila"]), max(name_to_id["Lucas"], name_to_id["Camila"]), dt_cam_like, day_1_ago))
        coin_luc_cam = pg_cur.fetchone()[0]

        # Diego <-> Valentina (Día 0 - Martes - Sin Feriado)
        dt_die_like = datetime.combine(day_0, datetime.min.time()) + timedelta(hours=11, minutes=5, seconds=0)
        dt_val_like = dt_die_like + timedelta(minutes=6, seconds=35)
        pg_cur.execute("INSERT INTO likes (id_usuario_origen, id_usuario_destino, fecha_like) VALUES (%s, %s, %s);", (name_to_id["Diego"], name_to_id["Valentina"], dt_die_like))
        pg_cur.execute("INSERT INTO likes (id_usuario_origen, id_usuario_destino, fecha_like) VALUES (%s, %s, %s);", (name_to_id["Valentina"], name_to_id["Diego"], dt_val_like))
        pg_cur.execute("""
            INSERT INTO coincidencias (id_usuario1, id_usuario2, fecha_coincidencia)
            VALUES (%s, %s, %s) RETURNING id_coincidencia;
        """, (min(name_to_id["Diego"], name_to_id["Valentina"]), max(name_to_id["Diego"], name_to_id["Valentina"]), dt_val_like))
        coin_die_val = pg_cur.fetchone()[0]

        # Joaquin <-> Agustina (Día 0 - Martes - Sin Feriado)
        dt_joa_like = datetime.combine(day_0, datetime.min.time()) + timedelta(hours=12, minutes=45, seconds=15)
        dt_agu_like = dt_joa_like + timedelta(minutes=9, seconds=50)
        pg_cur.execute("INSERT INTO likes (id_usuario_origen, id_usuario_destino, fecha_like) VALUES (%s, %s, %s);", (name_to_id["Joaquin"], name_to_id["Agustina"], dt_joa_like))
        pg_cur.execute("INSERT INTO likes (id_usuario_origen, id_usuario_destino, fecha_like) VALUES (%s, %s, %s);", (name_to_id["Agustina"], name_to_id["Joaquin"], dt_agu_like))
        pg_cur.execute("""
            INSERT INTO coincidencias (id_usuario1, id_usuario2, fecha_coincidencia)
            VALUES (%s, %s, %s) RETURNING id_coincidencia;
        """, (min(name_to_id["Joaquin"], name_to_id["Agustina"]), max(name_to_id["Joaquin"], name_to_id["Agustina"]), dt_agu_like))
        coin_joa_agu = pg_cur.fetchone()[0]

        # Likes unilaterales de Mateo (Día 0 - Hoy)
        dt_mat_like1 = datetime.combine(day_0, datetime.min.time()) + timedelta(hours=13, minutes=18, seconds=22)
        dt_mat_like2 = dt_mat_like1 + timedelta(minutes=4, seconds=15)
        dt_mat_like3 = dt_mat_like1 + timedelta(minutes=8, seconds=50)
        pg_cur.execute("INSERT INTO likes (id_usuario_origen, id_usuario_destino, fecha_like) VALUES (%s, %s, %s);", (name_to_id["Mateo"], name_to_id["Sofia"], dt_mat_like1))
        pg_cur.execute("INSERT INTO likes (id_usuario_origen, id_usuario_destino, fecha_like) VALUES (%s, %s, %s);", (name_to_id["Mateo"], name_to_id["Martina"], dt_mat_like2))
        pg_cur.execute("INSERT INTO likes (id_usuario_origen, id_usuario_destino, fecha_like) VALUES (%s, %s, %s);", (name_to_id["Mateo"], name_to_id["Valentina"], dt_mat_like3))

        # 1.7 Mensajes
        # Nicolas <-> Sofia
        dt_msg_nic1 = dt_sof_like + timedelta(hours=1, minutes=15, seconds=30)
        dt_msg_sof1 = dt_sof_like + timedelta(hours=1, minutes=38, seconds=45)
        pg_cur.execute("INSERT INTO mensajes (id_coincidencia, id_emisor, contenido, fecha_envio) VALUES (%s, %s, %s, %s);", (coin_nic_sof, name_to_id["Nicolas"], "Hola Sofia, ¿qué estás leyendo hoy?", dt_msg_nic1))
        pg_cur.execute("INSERT INTO mensajes (id_coincidencia, id_emisor, contenido, fecha_envio) VALUES (%s, %s, %s, %s);", (coin_nic_sof, name_to_id["Sofia"], "Hola Nico, estoy leyendo una novela de ciencia ficción.", dt_msg_sof1))

        # Juan <-> Martina
        dt_msg_jua1 = dt_mar_like + timedelta(minutes=12, seconds=40)
        dt_msg_mar1 = dt_mar_like + timedelta(minutes=22, seconds=15)
        dt_msg_jua2 = dt_mar_like + timedelta(minutes=35, seconds=50)
        pg_cur.execute("INSERT INTO mensajes (id_coincidencia, id_emisor, contenido, fecha_envio) VALUES (%s, %s, %s, %s);", (coin_jua_mar, name_to_id["Juan"], "¡Hola Martina! ¿Cómo estás?", dt_msg_jua1))
        pg_cur.execute("INSERT INTO mensajes (id_coincidencia, id_emisor, contenido, fecha_envio) VALUES (%s, %s, %s, %s);", (coin_jua_mar, name_to_id["Martina"], "Hola Juan, ¡bien y vos! Vi que nos gusta el cine.", dt_msg_mar1))
        pg_cur.execute("INSERT INTO mensajes (id_coincidencia, id_emisor, contenido, fecha_envio) VALUES (%s, %s, %s, %s);", (coin_jua_mar, name_to_id["Juan"], "Sí, ¡totalmente! Me encanta el cine clásico.", dt_msg_jua2))

        # Lucas <-> Camila
        dt_msg_luc1 = dt_cam_like + timedelta(minutes=25, seconds=10)
        dt_msg_cam1 = dt_cam_like + timedelta(minutes=41, seconds=35)
        pg_cur.execute("INSERT INTO mensajes (id_coincidencia, id_emisor, contenido, fecha_envio) VALUES (%s, %s, %s, %s);", (coin_luc_cam, name_to_id["Lucas"], "¡Hola Camila! Qué buenas fotos tenés.", dt_msg_luc1))
        pg_cur.execute("INSERT INTO mensajes (id_coincidencia, id_emisor, contenido, fecha_envio) VALUES (%s, %s, %s, %s);", (coin_luc_cam, name_to_id["Camila"], "Hola Lucas, ¡gracias! Son de mis viajes.", dt_msg_cam1))

        # 1.8 Eventos y Asistencias
        # Nicolas propuesta a Sofia
        dt_ev_nic_sof = dt_msg_sof1 + timedelta(hours=1, minutes=5, seconds=12)
        fecha_cita = datetime.combine(day_0 + timedelta(days=2), datetime.min.time()) + timedelta(hours=20, minutes=30)
        pg_cur.execute("""
            INSERT INTO eventos (nombre_evento, fecha, ubicacion, id_organizador, id_coincidencia, estado, fecha_creacion)
            VALUES (%s, %s, %s, %s, %s, 'PENDIENTE', %s) RETURNING id_evento;
        """, ("Café y charla de libros", fecha_cita, "Café Tortoni, CABA", name_to_id["Nicolas"], coin_nic_sof, dt_ev_nic_sof))
        ev_nic_sof = pg_cur.fetchone()[0]
        pg_cur.execute("INSERT INTO asistencia_eventos (id_usuario, id_evento, estado, fecha_registro) VALUES (%s, %s, 'PENDIENTE', %s);", (name_to_id["Sofia"], ev_nic_sof, dt_ev_nic_sof))

        # Juan propuesta a Martina
        dt_ev_jua_mar = dt_msg_jua2 + timedelta(hours=1, minutes=14, seconds=45)
        pg_cur.execute("""
            INSERT INTO eventos (nombre_evento, fecha, ubicacion, id_organizador, id_coincidencia, estado, fecha_creacion)
            VALUES (%s, %s, %s, %s, %s, 'ACEPTADA', %s) RETURNING id_evento;
        """, ("Cena y Cine de clásicos", fecha_cita, "Cine Lorca, CABA", name_to_id["Juan"], coin_jua_mar, dt_ev_jua_mar))
        ev_jua_mar = pg_cur.fetchone()[0]
        pg_cur.execute("""
            INSERT INTO asistencia_eventos (id_usuario, id_evento, estado, fecha_registro, fecha_respuesta) 
            VALUES (%s, %s, 'ACEPTADA', %s, %s);
        """, (name_to_id["Martina"], ev_jua_mar, dt_ev_jua_mar, dt_ev_jua_mar + timedelta(minutes=15, seconds=30)))

        # Lucas propuesta a Camila
        dt_ev_luc_cam = dt_msg_cam1 + timedelta(hours=1, minutes=8, seconds=10)
        pg_cur.execute("""
            INSERT INTO eventos (nombre_evento, fecha, ubicacion, id_organizador, id_coincidencia, estado, fecha_creacion)
            VALUES (%s, %s, %s, %s, %s, 'RECHAZADA', %s) RETURNING id_evento;
        """, ("Paseo por la costanera", fecha_cita, "Costanera Rosario", name_to_id["Lucas"], coin_luc_cam, dt_ev_luc_cam))
        ev_luc_cam = pg_cur.fetchone()[0]
        pg_cur.execute("""
            INSERT INTO asistencia_eventos (id_usuario, id_evento, estado, fecha_registro, fecha_respuesta) 
            VALUES (%s, %s, 'RECHAZADA', %s, %s);
        """, (name_to_id["Camila"], ev_luc_cam, dt_ev_luc_cam, dt_ev_luc_cam + timedelta(minutes=24, seconds=15)))

        # 1.9 Bloqueos
        # Nicolas bloquea a Juan (activo)
        dt_blk_nic_jua = datetime.combine(day_0, datetime.min.time()) + timedelta(hours=15, minutes=10, seconds=45)
        pg_cur.execute("""
            INSERT INTO bloqueos (id_bloqueador, id_bloqueado, fecha_bloqueo, activo)
            VALUES (%s, %s, %s, TRUE);
        """, (name_to_id["Nicolas"], name_to_id["Juan"], dt_blk_nic_jua))

        # Juan bloquea a Mateo, luego lo desbloquea
        dt_blk_jua_mat = datetime.combine(day_0, datetime.min.time()) + timedelta(hours=16, minutes=20, seconds=0)
        dt_unblk_jua_mat = dt_blk_jua_mat + timedelta(minutes=5, seconds=15)
        pg_cur.execute("""
            INSERT INTO bloqueos (id_bloqueador, id_bloqueado, fecha_bloqueo, fecha_desbloqueo, activo)
            VALUES (%s, %s, %s, %s, FALSE);
        """, (name_to_id["Juan"], name_to_id["Mateo"], dt_blk_jua_mat, dt_unblk_jua_mat))

        # 1.10 Poblar notificaciones en PostgreSQL
        print("Poblando notificaciones en PostgreSQL...")
        
        # We need the last action time for each user to decide if notification is read/unread
        user_actions = {}
        
        # Likes
        pg_cur.execute("SELECT id_usuario_origen, fecha_like FROM likes;")
        for row in pg_cur.fetchall():
            user_actions.setdefault(row[0], []).append(row[1])
            
        # Messages
        pg_cur.execute("SELECT id_emisor, fecha_envio FROM mensajes;")
        for row in pg_cur.fetchall():
            user_actions.setdefault(row[0], []).append(row[1])
            
        # Events proposed
        pg_cur.execute("SELECT id_organizador, fecha_creacion FROM eventos;")
        for row in pg_cur.fetchall():
            user_actions.setdefault(row[0], []).append(row[1])
            
        # Event responses
        pg_cur.execute("SELECT id_usuario, fecha_respuesta FROM asistencia_eventos WHERE fecha_respuesta IS NOT NULL;")
        for row in pg_cur.fetchall():
            user_actions.setdefault(row[0], []).append(row[1])
            
        # Blocks
        pg_cur.execute("SELECT id_bloqueador, fecha_bloqueo FROM bloqueos;")
        for row in pg_cur.fetchall():
            user_actions.setdefault(row[0], []).append(row[1])
            
        # Unblocks
        pg_cur.execute("SELECT id_bloqueador, fecha_desbloqueo FROM bloqueos WHERE fecha_desbloqueo IS NOT NULL;")
        for row in pg_cur.fetchall():
            user_actions.setdefault(row[0], []).append(row[1])
            
        user_last_action = {uid: max(times) for uid, times in user_actions.items() if times}

        notifs_to_insert = []
        
        # 1. Likes & Matches notifications
        pg_cur.execute("SELECT id_like, id_usuario_origen, id_usuario_destino, fecha_like FROM likes ORDER BY fecha_like ASC;")
        likes_rows = pg_cur.fetchall()
        
        pg_cur.execute("SELECT id_coincidencia, id_usuario1, id_usuario2 FROM coincidencias;")
        matches_map = {}
        for row in pg_cur.fetchall():
            key = (min(row[1], row[2]), max(row[1], row[2]))
            matches_map[key] = row[0]
            
        swiped_pairs = set()
        for id_like, uid_origen, uid_destino, fecha_like in likes_rows:
            if (uid_destino, uid_origen) in swiped_pairs:
                # Match notifications for both
                key = (min(uid_origen, uid_destino), max(uid_origen, uid_destino))
                match_id = matches_map.get(key)
                
                notifs_to_insert.append({
                    "id_usuario": uid_origen,
                    "tipo": "COINCIDENCIA",
                    "id_coincidencia": match_id,
                    "fecha": fecha_like
                })
                notifs_to_insert.append({
                    "id_usuario": uid_destino,
                    "tipo": "COINCIDENCIA",
                    "id_coincidencia": match_id,
                    "fecha": fecha_like
                })
            else:
                # Unilateral like notification to destination
                notifs_to_insert.append({
                    "id_usuario": uid_destino,
                    "tipo": "LIKE",
                    "id_like": id_like,
                    "fecha": fecha_like
                })
            swiped_pairs.add((uid_origen, uid_destino))
            
        # 2. Message notifications
        pg_cur.execute("""
            SELECT m.id_mensaje, m.id_coincidencia, m.id_emisor, m.fecha_envio, c.id_usuario1, c.id_usuario2
            FROM mensajes m
            JOIN coincidencias c ON m.id_coincidencia = c.id_coincidencia;
        """)
        for row in pg_cur.fetchall():
            msg_id, coin_id, emisor_id, send_date, u1, u2 = row
            receptor_id = u2 if emisor_id == u1 else u1
            notifs_to_insert.append({
                "id_usuario": receptor_id,
                "tipo": "MENSAJE",
                "id_mensaje": msg_id,
                "fecha": send_date
            })
            
        # 3. Event proposal notifications
        pg_cur.execute("SELECT id_evento, id_organizador, id_coincidencia, fecha_creacion FROM eventos;")
        for row in pg_cur.fetchall():
            ev_id, organizer_id, coin_id, ev_creation = row
            pg_cur.execute("SELECT id_usuario1, id_usuario2 FROM coincidencias WHERE id_coincidencia = %s;", (coin_id,))
            c_row = pg_cur.fetchone()
            invitee_id = c_row[1] if organizer_id == c_row[0] else c_row[0]
            notifs_to_insert.append({
                "id_usuario": invitee_id,
                "tipo": "EVENTO",
                "id_evento": ev_id,
                "fecha": ev_creation
            })
            
        # 4. Event response notifications (accepted / rejected)
        pg_cur.execute("SELECT id_evento, id_usuario, estado, fecha_respuesta FROM asistencia_eventos WHERE estado IN ('ACEPTADA', 'RECHAZADA');")
        for row in pg_cur.fetchall():
            event_id, guest_id, state, resp_date = row
            pg_cur.execute("SELECT id_organizador FROM eventos WHERE id_evento = %s;", (event_id,))
            org_id = pg_cur.fetchone()[0]
            notifs_to_insert.append({
                "id_usuario": org_id,
                "tipo": "EVENTO",
                "id_evento": event_id,
                "fecha": resp_date
            })
            
        # Insert them into Postgres
        for n in notifs_to_insert:
            uid = n["id_usuario"]
            tipo = n["tipo"]
            fecha = n["fecha"]
            id_like = n.get("id_like")
            id_coin = n.get("id_coincidencia")
            id_msg = n.get("id_mensaje")
            id_ev = n.get("id_evento")
            
            last_act = user_last_action.get(uid)
            leida = False
            if last_act and fecha <= last_act:
                leida = True
                
            pg_cur.execute("""
                INSERT INTO notificaciones (id_usuario, tipo, id_like, id_coincidencia, id_mensaje, id_evento, leida, fecha_creacion)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
            """, (uid, tipo, id_like, id_coin, id_msg, id_ev, leida, fecha))

        pg_conn.commit()
        pg_cur.close()
        pg_conn.close()
        print("PostgreSQL poblado con éxito.")

        # -------------------------------------------------------------
        # 2. SINCRONIZAR GRAFO: NEO4J
        # -------------------------------------------------------------
        print("Sincronizando Neo4j...")
        neo_driver = get_neo4j_driver()
        with neo_driver.session() as neo_session:
            # 2.1 Crear nodos de usuarios
            neo_session.run("""
                UNWIND $users AS u
                MERGE (n:Usuario {id_usuario: u.id})
                SET n.id = u.id, n.nombre = u.nombre, n.edad = u.edad, n.genero = u.genero, n.ubicacion = u.ubicacion
            """, users=[{"id": uid, "nombre": name, "edad": data["edad"], "genero": data["genero"], "ubicacion": data["ubicacion"]} for name, uid in name_to_id.items() for data in usuarios_data if data["nombre"] == name])

            # 2.2 Crear nodos de intereses y relacionar
            pg_conn = get_postgres_connection()
            pg_cur = pg_conn.cursor()
            pg_cur.execute("SELECT ui.id_usuario, i.nombre FROM usuario_intereses ui JOIN intereses i ON ui.id_interes = i.id_interes;")
            user_ints = pg_cur.fetchall()
            neo_session.run("""
                UNWIND $relations AS r
                MATCH (u:Usuario {id_usuario: r.uid})
                MERGE (i:Interes {nombre: r.interest})
                MERGE (u)-[:TIENE_INTERES]->(i)
            """, relations=[{"uid": row[0], "interest": row[1]} for row in user_ints])

            # 2.3 Relaciones de Likes
            pg_cur.execute("SELECT id_usuario_origen, id_usuario_destino, fecha_like FROM likes;")
            likes_list = pg_cur.fetchall()
            neo_session.run("""
                UNWIND $likes AS l
                MATCH (u1:Usuario {id_usuario: l.from_uid})
                MATCH (u2:Usuario {id_usuario: l.to_uid})
                MERGE (u1)-[:DIO_LIKE {fecha: datetime(l.fecha)}]->(u2)
            """, likes=[{"from_uid": row[0], "to_uid": row[1], "fecha": row[2].isoformat()} for row in likes_list])

            # 2.4 Relaciones de Coincidencias
            pg_cur.execute("SELECT id_usuario1, id_usuario2, fecha_coincidencia FROM coincidencias;")
            coins_list = pg_cur.fetchall()
            neo_session.run("""
                UNWIND $coins AS c
                MATCH (u1:Usuario {id_usuario: c.uid1})
                MATCH (u2:Usuario {id_usuario: c.uid2})
                MERGE (u1)-[:COINCIDIO_CON {fecha: datetime(c.fecha)}]->(u2)
            """, coins=[{"uid1": row[0], "uid2": row[1], "fecha": row[2].isoformat()} for row in coins_list])

            # 2.5 Nodos de Eventos y Relaciones
            pg_cur.execute("SELECT id_evento, nombre_evento, id_organizador, id_coincidencia FROM eventos;")
            events_list = pg_cur.fetchall()
            for ev in events_list:
                ev_id, ev_name, organizer_id, coin_id = ev
                # Find the guest (the other user in the match)
                pg_cur.execute("SELECT id_usuario1, id_usuario2 FROM coincidencias WHERE id_coincidencia = %s;", (coin_id,))
                c_row = pg_cur.fetchone()
                guest_id = c_row[1] if organizer_id == c_row[0] else c_row[0]
                
                neo_session.run("""
                    MERGE (e:Evento {id_evento: $ev_id})
                    SET e.nombre = $ev_name
                """, ev_id=ev_id, ev_name=ev_name)
                
                neo_session.run("""
                    MATCH (u:Usuario {id_usuario: $uid})
                    MATCH (e:Evento {id_evento: $ev_id})
                    MERGE (u)-[:ORGANIZO]->(e)
                """, uid=organizer_id, ev_id=ev_id)
                
                neo_session.run("""
                    MATCH (u:Usuario {id_usuario: $uid})
                    MATCH (e:Evento {id_evento: $ev_id})
                    MERGE (u)-[:INVITADO_A]->(e)
                """, uid=guest_id, ev_id=ev_id)

            # 2.6 Aceptaciones de Eventos
            pg_cur.execute("SELECT id_usuario, id_evento, fecha_respuesta FROM asistencia_eventos WHERE estado = 'ACEPTADA';")
            acceptances = pg_cur.fetchall()
            neo_session.run("""
                UNWIND $accepts AS a
                MATCH (u:Usuario {id_usuario: a.uid})
                MATCH (e:Evento {id_evento: a.ev_id})
                MERGE (u)-[:ACEPTO_EVENTO {fecha: datetime(a.fecha)}]->(e)
            """, accepts=[{"uid": row[0], "ev_id": row[1], "fecha": row[2].isoformat()} for row in acceptances])

            # 2.7 Bloqueos activos
            pg_cur.execute("SELECT id_bloqueador, id_bloqueado, fecha_bloqueo FROM bloqueos WHERE activo = TRUE;")
            active_blocks = pg_cur.fetchall()
            neo_session.run("""
                UNWIND $blocks AS b
                MATCH (u1:Usuario {id_usuario: b.from_uid})
                MATCH (u2:Usuario {id_usuario: b.to_uid})
                MERGE (u1)-[:BLOQUEO {fecha: datetime(b.fecha)}]->(u2)
            """, blocks=[{"from_uid": row[0], "to_uid": row[1], "fecha": row[2].isoformat()} for row in active_blocks])

            pg_cur.close()
            pg_conn.close()
        neo_driver.close()
        print("Neo4j sincronizado con éxito.")

        # -------------------------------------------------------------
        # 3. SINCRONIZAR DOCUMENTOS Y LOGS: MONGODB
        # -------------------------------------------------------------
        print("Sincronizando MongoDB...")
        mongo_db = get_mongo_db()
        pg_conn = get_postgres_connection()
        pg_cur = pg_conn.cursor()

        # 3.1 Perfiles públicos denormalizados
        pg_cur.execute("SELECT id_usuario, nombre, edad, genero, ubicacion, biografia FROM usuarios;")
        users_rows = pg_cur.fetchall()
        for u_row in users_rows:
            uid, nombre, edad, genero, ubicacion, biografia = u_row
            
            # Fetch interests
            pg_cur.execute("SELECT i.nombre FROM usuario_intereses ui JOIN intereses i ON ui.id_interes = i.id_interes WHERE ui.id_usuario = %s;", (uid,))
            ints = [r[0] for r in pg_cur.fetchall()]
            
            # Fetch photos
            pg_cur.execute("SELECT url_archivo, es_principal FROM fotos WHERE id_usuario = %s ORDER BY es_principal DESC, id_foto ASC;", (uid,))
            photos_rows = pg_cur.fetchall()
            photos_list = [{"url": p[0], "principal": p[1]} for p in photos_rows]
            
            perfil_denorm = {
                "id_usuario": uid,
                "nombre": nombre,
                "edad": edad,
                "genero": genero,
                "ubicacion": ubicacion,
                "biografia": biografia or "",
                "intereses": ints,
                "fotos": photos_list,
                "cantidad_fotos": len(photos_list),
                "fecha_actualizacion": datetime.utcnow()
            }
            mongo_db.perfiles_publicos.update_one(
                {"id_usuario": uid},
                {"$set": perfil_denorm},
                upsert=True
            )

        # 3.2 Logs de actividad
        logs = []
        
        # User registrations
        pg_cur.execute("SELECT id_usuario, nombre, email, fecha_registro FROM usuarios;")
        for row in pg_cur.fetchall():
            logs.append({
                "tipo_evento": "USUARIO_REGISTRADO",
                "id_usuario": row[0],
                "fecha": row[3],
                "detalles": {"nombre": row[1], "email": row[2]}
            })

        # Likes & Matches reconstruction from likes table chronologically
        pg_cur.execute("SELECT id_usuario_origen, id_usuario_destino, fecha_like FROM likes ORDER BY fecha_like ASC;")
        likes_rows = pg_cur.fetchall()
        
        pg_cur.execute("SELECT id_coincidencia, id_usuario1, id_usuario2 FROM coincidencias;")
        matches_map = {}
        for row in pg_cur.fetchall():
            key = (min(row[1], row[2]), max(row[1], row[2]))
            matches_map[key] = row[0]
            
        swiped_pairs = set()
        for uid_origen, uid_destino, fecha_like in likes_rows:
            # Check if there is already a reverse like (which means this like creates a match!)
            if (uid_destino, uid_origen) in swiped_pairs:
                key = (min(uid_origen, uid_destino), max(uid_origen, uid_destino))
                match_id = matches_map.get(key)
                logs.append({
                    "tipo_evento": "MATCH_GENERADO",
                    "id_usuario": uid_origen,
                    "fecha": fecha_like,
                    "detalles": {"id_usuario_destino": uid_destino, "id_coincidencia": match_id}
                })
                logs.append({
                    "tipo_evento": "MATCH_GENERADO",
                    "id_usuario": uid_destino,
                    "fecha": fecha_like,
                    "detalles": {"id_usuario_destino": uid_origen, "id_coincidencia": match_id}
                })
            else:
                # Unilateral like
                logs.append({
                    "tipo_evento": "LIKE_REALIZADO",
                    "id_usuario": uid_origen,
                    "fecha": fecha_like,
                    "detalles": {"id_usuario_destino": uid_destino}
                })
            swiped_pairs.add((uid_origen, uid_destino))

        # Messages
        pg_cur.execute("""
            SELECT m.id_mensaje, m.id_coincidencia, m.id_emisor, m.fecha_envio, c.id_usuario1, c.id_usuario2
            FROM mensajes m
            JOIN coincidencias c ON m.id_coincidencia = c.id_coincidencia
            ORDER BY m.fecha_envio ASC;
        """)
        for row in pg_cur.fetchall():
            msg_id, coin_id, emisor_id, send_date, u1, u2 = row
            receptor_id = u2 if emisor_id == u1 else u1
            logs.append({
                "tipo_evento": "MENSAJE_ENVIADO",
                "id_usuario": emisor_id,
                "fecha": send_date,
                "detalles": {"id_receptor": receptor_id, "id_mensaje": msg_id}
            })

        # Events proposed
        pg_cur.execute("SELECT id_evento, id_organizador, id_coincidencia, fecha_creacion FROM eventos;")
        for row in pg_cur.fetchall():
            ev_id, organizer_id, coin_id, ev_creation = row
            pg_cur.execute("SELECT id_usuario1, id_usuario2 FROM coincidencias WHERE id_coincidencia = %s;", (coin_id,))
            c_row = pg_cur.fetchone()
            invitee_id = c_row[1] if organizer_id == c_row[0] else c_row[0]
            
            logs.append({
                "tipo_evento": "EVENTO_PROPUESTO",
                "id_usuario": organizer_id,
                "fecha": ev_creation,
                "detalles": {"id_receptor": invitee_id, "id_evento": ev_id}
            })

        # Events accepted / rejected
        pg_cur.execute("SELECT id_evento, id_usuario, estado, fecha_respuesta FROM asistencia_eventos WHERE estado IN ('ACEPTADA', 'RECHAZADA');")
        for row in pg_cur.fetchall():
            event_id, guest_id, state, resp_date = row
            pg_cur.execute("SELECT id_organizador FROM eventos WHERE id_evento = %s;", (event_id,))
            org_id = pg_cur.fetchone()[0]
            
            logs.append({
                "tipo_evento": "EVENTO_ACEPTADO" if state == 'ACEPTADA' else "EVENTO_RECHAZADO",
                "id_usuario": guest_id,
                "fecha": resp_date,
                "detalles": {"id_organizador": org_id, "id_evento": event_id}
            })

        # Blocks
        pg_cur.execute("SELECT id_bloqueo, id_bloqueador, id_bloqueado, fecha_bloqueo, fecha_desbloqueo, activo FROM bloqueos;")
        for row in pg_cur.fetchall():
            block_id, blocker_id, blocked_id, block_date, unblock_date, active = row
            logs.append({
                "tipo_evento": "USUARIO_BLOQUEADO",
                "id_usuario": blocker_id,
                "fecha": block_date,
                "detalles": {"id_bloqueado": blocked_id, "id_bloqueo": block_id}
            })
            if not active and unblock_date:
                logs.append({
                    "tipo_evento": "USUARIO_DESBLOQUEADO",
                    "id_usuario": blocker_id,
                    "fecha": unblock_date,
                    "detalles": {"id_bloqueado": blocked_id}
                })

        # Reconstruct session logins/logouts chronologically based on when actions occurred
        user_actions = {}
        
        # Get registration date for each user to enforce safety boundary
        pg_cur.execute("SELECT id_usuario, fecha_registro FROM usuarios;")
        user_reg_bounds = {row[0]: row[1] for row in pg_cur.fetchall()}
            
        # 1. Likes
        pg_cur.execute("SELECT id_usuario_origen, fecha_like FROM likes;")
        for row in pg_cur.fetchall():
            user_actions.setdefault(row[0], []).append(row[1])
            
        # 2. Messages
        pg_cur.execute("SELECT id_emisor, fecha_envio FROM mensajes;")
        for row in pg_cur.fetchall():
            user_actions.setdefault(row[0], []).append(row[1])
            
        # 3. Events proposed
        pg_cur.execute("SELECT id_organizador, fecha_creacion FROM eventos;")
        for row in pg_cur.fetchall():
            user_actions.setdefault(row[0], []).append(row[1])
            
        # 4. Event responses
        pg_cur.execute("SELECT id_usuario, fecha_respuesta FROM asistencia_eventos WHERE fecha_respuesta IS NOT NULL;")
        for row in pg_cur.fetchall():
            user_actions.setdefault(row[0], []).append(row[1])
            
        # 5. Blocks
        pg_cur.execute("SELECT id_bloqueador, fecha_bloqueo FROM bloqueos;")
        for row in pg_cur.fetchall():
            user_actions.setdefault(row[0], []).append(row[1])
            
        # 6. Unblocks
        pg_cur.execute("SELECT id_bloqueador, fecha_desbloqueo FROM bloqueos WHERE fecha_desbloqueo IS NOT NULL;")
        for row in pg_cur.fetchall():
            user_actions.setdefault(row[0], []).append(row[1])
            
        # Group actions into sessions (max gap: 2 hours) and generate logs
        for uid, times in user_actions.items():
            sorted_times = sorted(times)
            if not sorted_times:
                continue
                
            sessions = []
            current_start = sorted_times[0] - timedelta(minutes=5)
            current_last = sorted_times[0]
            
            for t in sorted_times[1:]:
                if t - current_last <= timedelta(hours=2):
                    current_last = t
                else:
                    sessions.append((current_start, current_last + timedelta(minutes=15)))
                    current_start = t - timedelta(minutes=5)
                    current_last = t
            sessions.append((current_start, current_last + timedelta(minutes=15)))
            
            reg_date = user_reg_bounds.get(uid)
            for start_t, end_t in sessions:
                # Enforce that session start cannot be before registration date
                if reg_date:
                    start_t = max(start_t, reg_date)
                    
                logs.append({
                    "tipo_evento": "INICIO_SESION",
                    "id_usuario": uid,
                    "fecha": start_t,
                    "detalles": {}
                })
                logs.append({
                    "tipo_evento": "CIERRE_SESION",
                    "id_usuario": uid,
                    "fecha": end_t,
                    "detalles": {}
                })

        # Sort logs chronologically by fecha
        logs.sort(key=lambda x: x["fecha"])

        if logs:
            mongo_db.actividad_importante.insert_many(logs)

        pg_cur.close()
        pg_conn.close()
        print("MongoDB sincronizado con éxito.")

        # -------------------------------------------------------------
        # 4. SINCRONIZAR AGREGADOS Y MÉTRICAS: CASSANDRA
        # -------------------------------------------------------------
        print("Sincronizando Cassandra...")
        cass_cluster, cass_session = get_cassandra_session()
        pg_conn = get_postgres_connection()
        pg_cur = pg_conn.cursor()

        # 4.1 estadisticas_coincidencias_por_dia
        pg_cur.execute("SELECT date(fecha_coincidencia), count(*), fecha_feriado FROM coincidencias GROUP BY date(fecha_coincidencia), fecha_feriado;")
        matches_by_day = pg_cur.fetchall()
        for row in matches_by_day:
            f_date, count, feriado_date = row
            es_fds = f_date.weekday() >= 5
            es_fer = feriado_date is not None
            
            cant_fds = count if es_fds else 0
            cant_fer = count if es_fer else 0
            
            cass_session.execute("""
                INSERT INTO estadisticas_coincidencias_por_dia (fecha, cantidad_coincidencias, cantidad_fin_de_semana, cantidad_feriado)
                VALUES (%s, %s, %s, %s);
            """, [f_date, count, cant_fds, cant_fer])

        # 4.4 mensajes_por_evento
        pg_cur.execute("SELECT id_evento, id_coincidencia, fecha, fecha_creacion FROM eventos;")
        events = pg_cur.fetchall()
        for row in events:
            ev_id, coin_id, ev_date, ev_creation = row
            
            # Query number of messages in this match sent before event creation
            pg_cur.execute("SELECT count(*) FROM mensajes WHERE id_coincidencia = %s AND fecha_envio <= %s;", (coin_id, ev_creation))
            msg_count = pg_cur.fetchone()[0]
            
            cass_session.execute("""
                INSERT INTO mensajes_por_evento (fecha_evento, id_evento, id_coincidencia, cantidad_mensajes)
                VALUES (%s, %s, %s, %s);
            """, [ev_date.date(), ev_id, coin_id, msg_count])

        pg_cur.close()
        pg_conn.close()
        cass_cluster.shutdown()
        print("Cassandra sincronizado con éxito.")

        # -------------------------------------------------------------
        # 5. SINCRONIZAR REDIS
        # -------------------------------------------------------------
        print("Sincronizando Redis...")
        r_client = get_redis_client()
        r_client.set("app_status", "initialized")
        
        # Populate Redis sorted set swipes rank for today
        pg_conn = get_postgres_connection()
        pg_cur = pg_conn.cursor()
        pg_cur.execute("SELECT id_usuario_destino, count(*) FROM likes WHERE date(fecha_like) = %s GROUP BY id_usuario_destino;", (today,))
        for row in pg_cur.fetchall():
            dest_id, count = row
            r_client.zadd(f"top_swipes_dia:{today.strftime('%Y-%m-%d')}", {str(dest_id): count})
            
        # Sync unread count and latest 10 notifications for each user in Redis
        pg_cur.execute("""
            SELECT id_usuario, count(*)
            FROM notificaciones
            WHERE leida = FALSE
            GROUP BY id_usuario;
        """)
        unread_counts = {row[0]: row[1] for row in pg_cur.fetchall()}
        
        pg_cur.execute("SELECT id_usuario FROM usuarios;")
        user_ids = [r[0] for r in pg_cur.fetchall()]
        
        for uid in user_ids:
            # Set unread count (reset to 0 if not found)
            count = unread_counts.get(uid, 0)
            r_client.set(f"notificaciones_cantidad:{uid}", count)
            
            # Fetch the last 10 notifications for this user, sorted oldest first (ASC) for LPUSH
            pg_cur.execute("""
                SELECT id_notificacion, tipo, id_like, id_coincidencia, id_mensaje, id_evento, fecha_creacion
                FROM notificaciones
                WHERE id_usuario = %s
                ORDER BY fecha_creacion DESC
                LIMIT 10;
            """, (uid,))
            notifs_desc = pg_cur.fetchall()
            notifs_asc = list(reversed(notifs_desc))
            
            key = f"notificaciones_tipos:{uid}"
            r_client.delete(key) # Clear first
            
            for row in notifs_asc:
                notif_id, tipo, id_like, id_coin, id_msg, id_ev, fecha = row
                
                mensaje_text = "Nueva notificación"
                if tipo == "LIKE":
                    mensaje_text = "A alguien le gustó tu perfil"
                elif tipo == "COINCIDENCIA":
                    pg_cur.execute("SELECT id_usuario1, id_usuario2 FROM coincidencias WHERE id_coincidencia = %s;", (id_coin,))
                    coin_row = pg_cur.fetchone()
                    other_uid = coin_row[1] if coin_row[0] == uid else coin_row[0]
                    pg_cur.execute("SELECT nombre FROM usuarios WHERE id_usuario = %s;", (other_uid,))
                    other_name = pg_cur.fetchone()[0]
                    mensaje_text = f"¡Tuviste una coincidencia con {other_name}!"
                elif tipo == "MENSAJE":
                    pg_cur.execute("""
                        SELECT u.nombre, m.contenido
                        FROM mensajes m
                        JOIN usuarios u ON m.id_emisor = u.id_usuario
                        WHERE m.id_mensaje = %s;
                    """, (id_msg,))
                    msg_row = pg_cur.fetchone()
                    sender_name, content = msg_row
                    mensaje_text = f"Nuevo mensaje de {sender_name}: {content[:20]}..."
                elif tipo == "EVENTO":
                    pg_cur.execute("SELECT nombre_evento, id_organizador FROM eventos WHERE id_evento = %s;", (id_ev,))
                    ev_row = pg_cur.fetchone()
                    nombre_evento, organizer_id = ev_row
                    
                    if organizer_id == uid:
                        pg_cur.execute("SELECT id_usuario, estado FROM asistencia_eventos WHERE id_evento = %s;", (id_ev,))
                        asist_row = pg_cur.fetchone()
                        guest_id, estado = asist_row
                        pg_cur.execute("SELECT nombre FROM usuarios WHERE id_usuario = %s;", (guest_id,))
                        guest_name = pg_cur.fetchone()[0]
                        
                        if estado == 'ACEPTADA':
                            mensaje_text = f"{guest_name} aceptó tu cita: {nombre_evento}"
                        else:
                            mensaje_text = f"{guest_name} rechazó tu cita: {nombre_evento}"
                    else:
                        pg_cur.execute("SELECT nombre FROM usuarios WHERE id_usuario = %s;", (organizer_id,))
                        org_name = pg_cur.fetchone()[0]
                        mensaje_text = f"{org_name} te propuso una cita: {nombre_evento}"
                
                notif_payload = {
                    "id_notificacion": notif_id,
                    "tipo": tipo,
                    "mensaje": mensaje_text,
                    "fecha": fecha.isoformat()
                }
                r_client.lpush(key, json.dumps(notif_payload))
                r_client.ltrim(key, 0, 9)
            
        pg_cur.close()
        pg_conn.close()
        print("Redis sincronizado con éxito.")
        
        print("¡El seeder finalizó con éxito!")

if __name__ == "__main__":
    seeder = Seeder()
    seeder.run()
