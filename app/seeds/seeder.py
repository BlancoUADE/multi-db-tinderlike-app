import sys
import hashlib
from datetime import datetime, date, timedelta
from app.databases.postgres_conn import get_postgres_connection
from app.databases.redis_conn import get_redis_client
from app.databases.mongo_conn import get_mongo_db
from app.databases.cassandra_conn import get_cassandra_session
from app.databases.neo4j_conn import get_neo4j_driver
from app.services.auth_service import AuthService
from app.services.profile_service import ProfileService
from app.services.match_service import MatchService
from app.services.event_service import EventService
from app.services.block_service import BlockService

class Seeder:
    def __init__(self):
        self.auth_service = AuthService()
        self.profile_service = ProfileService()
        self.match_service = MatchService()
        self.event_service = EventService()
        self.block_service = BlockService()

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
        session.execute("TRUNCATE match_stats_by_day;")
        session.execute("TRUNCATE profile_swipes_by_day;")
        session.execute("TRUNCATE profile_swipes_total;")
        session.execute("TRUNCATE conversation_to_event_duration;")
        cluster.shutdown()
        print("- Cassandra limpia.")

        # 5. Neo4j
        driver = get_neo4j_driver()
        with driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
        driver.close()
        print("- Neo4j limpia.")

    def run(self):
        self.wipe_databases()
        print("Iniciando carga de datos...")

        # 1. Cargar feriados
        conn = get_postgres_connection()
        cur = conn.cursor()
        feriados_list = [
            ("2026-01-01", "Año Nuevo"),
            ("2026-05-25", "Revolución de Mayo"),
            ("2026-07-09", "Día de la Independencia"),
            ("2026-12-25", "Navidad")
        ]
        for f_date, desc in feriados_list:
            cur.execute("INSERT INTO feriados (fecha, descripcion) VALUES (%s, %s)", (f_date, desc))
        conn.commit()
        cur.close()
        conn.close()
        print("Feriados insertados.")

        # 2. Registrar 11 usuarios
        usuarios_data = [
            {"nombre": "Martina", "edad": 26, "genero": "F", "ubicacion": "CABA", "biografia": "Me gusta el cine y viajar", "pref_edad_min": 22, "pref_edad_max": 30, "email": "martina@example.com", "password": "password123"},
            {"nombre": "Sofia", "edad": 28, "genero": "F", "ubicacion": "CABA", "biografia": "Lectura y buen café", "pref_edad_min": 24, "pref_edad_max": 32, "email": "sofia@example.com", "password": "password123"},
            {"nombre": "Juan", "edad": 27, "genero": "M", "ubicacion": "CABA", "biografia": "Fan de los deportes y cocinar", "pref_edad_min": 23, "pref_edad_max": 30, "email": "juan@example.com", "password": "password123"},
            {"nombre": "Mateo", "edad": 25, "genero": "M", "ubicacion": "GBA", "biografia": "Programador y melómano", "pref_edad_min": 20, "pref_edad_max": 28, "email": "mateo@example.com", "password": "password123"},
            {"nombre": "Camila", "edad": 23, "genero": "F", "ubicacion": "Rosario", "biografia": "Amo la fotografía y los animales", "pref_edad_min": 21, "pref_edad_max": 27, "email": "camila@example.com", "password": "password123"},
            {"nombre": "Nicolas", "edad": 31, "genero": "M", "ubicacion": "CABA", "biografia": "Apasionado por la tecnología", "pref_edad_min": 26, "pref_edad_max": 35, "email": "nicolas@example.com", "password": "password123"},
            {"nombre": "Valentina", "edad": 24, "genero": "F", "ubicacion": "GBA", "biografia": "Estudiante de arte", "pref_edad_min": 22, "pref_edad_max": 29, "email": "valentina@example.com", "password": "password123"},
            {"nombre": "Lucas", "edad": 29, "genero": "M", "ubicacion": "Rosario", "biografia": "Viajero frecuente", "pref_edad_min": 25, "pref_edad_max": 33, "email": "lucas@example.com", "password": "password123"},
            {"nombre": "Agustina", "edad": 32, "genero": "F", "ubicacion": "CABA", "biografia": "Amo la gastronomía gourmet", "pref_edad_min": 28, "pref_edad_max": 36, "email": "agustina@example.com", "password": "password123"},
            {"nombre": "Joaquin", "edad": 30, "genero": "M", "ubicacion": "CABA", "biografia": "Música clásica e historia", "pref_edad_min": 25, "pref_edad_max": 33, "email": "joaquin@example.com", "password": "password123"},
            # Diego tendrá más de 10 fotos para Reporte 6
            {"nombre": "Diego", "edad": 25, "genero": "M", "ubicacion": "CABA", "biografia": "Amante de la fotografía y trekking", "pref_edad_min": 20, "pref_edad_max": 30, "email": "diego@example.com", "password": "password123"},
        ]

        user_ids = {}
        for u in usuarios_data:
            uid = self.auth_service.registrar_usuario(u)
            user_ids[u["nombre"]] = uid
        print("Usuarios registrados.")

        # 3. Cargar Intereses y asociarlos
        intereses_por_usuario = {
            "Martina": ["cine", "viajar", "musica", "fotografia"],
            "Sofia": ["lectura", "musica", "arte"],
            "Juan": ["deportes", "gastronomia", "musica", "cine"],
            "Mateo": ["musica", "tecnologia", "viajar"],
            "Camila": ["fotografia", "arte", "viajar"],
            "Nicolas": ["tecnologia", "deportes", "cine"],
            "Valentina": ["arte", "fotografia", "lectura", "cine"],
            "Lucas": ["viajar", "gastronomia", "deportes"],
            "Agustina": ["gastronomia", "viajar", "arte"],
            "Joaquin": ["musica", "lectura", "cine"],
            "Diego": ["fotografia", "viajar", "cine", "deportes", "musica"]
        }

        for nombre, intereses in intereses_por_usuario.items():
            uid = user_ids[nombre]
            for inte in intereses:
                self.profile_service.agregar_interes(uid, inte)
        print("Intereses agregados.")

        # 4. Fotos por usuario (Diego tendrá 11 fotos)
        for nombre, uid in user_ids.items():
            if nombre == "Diego":
                # Agregar 11 fotos
                for i in range(1, 12):
                    es_p = (i == 1)
                    self.profile_service.agregar_foto(uid, f"diego_foto_{i}.jpg", es_p)
            else:
                self.profile_service.agregar_foto(uid, f"{nombre.lower()}_perfil.jpg", True)
                self.profile_service.agregar_foto(uid, f"{nombre.lower()}_adicional.jpg", False)
        print("Fotos cargadas.")

        # 5. Cargar Likes y Generar Matches
        # Martina (1) <-> Juan (3) -> Match
        # Sofia (2) <-> Nicolas (6) -> Match
        # Camila (5) <-> Lucas (8) -> Match
        # Agustina (9) <-> Joaquin (10) -> Match
        # Valentina (7) <-> Diego (11) -> Match
        # Mateos da likes unilaterales
        likes_data = [
            ("Juan", "Martina"), ("Martina", "Juan"),
            ("Nicolas", "Sofia"), ("Sofia", "Nicolas"),
            ("Lucas", "Camila"), ("Camila", "Lucas"),
            ("Joaquin", "Agustina"), ("Agustina", "Joaquin"),
            ("Diego", "Valentina"), ("Valentina", "Diego"),
            ("Mateo", "Sofia"), ("Mateo", "Martina"), ("Mateo", "Valentina")
        ]

        matches = {} # (userA, userB) -> id_coincidencia
        for orig, dest in likes_data:
            id_orig = user_ids[orig]
            id_dest = user_ids[dest]
            es_match, id_coincidencia = self.match_service.dar_like(id_orig, id_dest)
            if es_match:
                u_min, u_max = min(id_orig, id_dest), max(id_orig, id_dest)
                matches[(u_min, u_max)] = id_coincidencia
        print("Likes y matches generados.")

        # 6. Mensajes en los Matches
        # Juan y Martina conversan
        id_coin_jm = matches[tuple(sorted([user_ids["Juan"], user_ids["Martina"]]))]
        self.match_service.enviar_mensaje(id_coin_jm, user_ids["Juan"], "¡Hola Martina! ¿Cómo estás?")
        self.match_service.enviar_mensaje(id_coin_jm, user_ids["Martina"], "Hola Juan, ¡bien y vos! Vi que nos gusta el cine a ambos.")
        self.match_service.enviar_mensaje(id_coin_jm, user_ids["Juan"], "Sí, ¡totalmente! Me encanta el cine clásico.")

        # Nicolas y Sofia conversan
        id_coin_ns = matches[tuple(sorted([user_ids["Nicolas"], user_ids["Sofia"]]))]
        self.match_service.enviar_mensaje(id_coin_ns, user_ids["Nicolas"], "Hola Sofia, ¿qué estás leyendo hoy?")
        
        # Lucas y Camila conversan
        id_coin_lc = matches[tuple(sorted([user_ids["Lucas"], user_ids["Camila"]]))]
        self.match_service.enviar_mensaje(id_coin_lc, user_ids["Lucas"], "¡Hola Camila! Qué buenas fotos de paisajes tenés.")
        print("Mensajes enviados.")

        # 7. Bloqueos
        # Nicolas bloquea a Juan (activo)
        self.block_service.bloquear_usuario(user_ids["Nicolas"], user_ids["Juan"])
        
        # Juan bloquea a Mateo, luego lo desbloquea (inactivo)
        self.block_service.bloquear_usuario(user_ids["Juan"], user_ids["Mateo"])
        self.block_service.desbloquear_usuario(user_ids["Juan"], user_ids["Mateo"])
        print("Bloqueos registrados.")

        # 8. Eventos (Citas)
        # Cita 1: Juan y Martina. Cita Aceptada.
        # Crearemos la cita para mañana
        fecha_cita = datetime.now() + timedelta(days=1)
        id_ev1 = self.event_service.proponer_cita(
            id_organizador=user_ids["Juan"],
            id_coincidencia=id_coin_jm,
            nombre_evento="Cena y Cine de clásicos",
            fecha=fecha_cita,
            ubicacion="Cine Lorca, CABA"
        )
        self.event_service.aceptar_cita(user_ids["Martina"], id_ev1)

        # Cita 2: Nicolas y Sofia. Cita Pendiente.
        id_ev2 = self.event_service.proponer_cita(
            id_organizador=user_ids["Nicolas"],
            id_coincidencia=id_coin_ns,
            nombre_evento="Café y charla de libros",
            fecha=fecha_cita,
            ubicacion="Café Tortoni, CABA"
        )

        # Cita 3: Lucas y Camila. Cita Rechazada.
        id_ev3 = self.event_service.proponer_cita(
            id_organizador=user_ids["Lucas"],
            id_coincidencia=id_coin_lc,
            nombre_evento="Paseo por la costanera",
            fecha=fecha_cita,
            ubicacion="Costanera Rosario"
        )
        self.event_service.rechazar_cita(user_ids["Camila"], id_ev3)
        print("Eventos y citas sociales programados.")

        # 9. Agregar datos históricos a Cassandra para reportes analíticos
        # Vamos a poblar match_stats_by_day para los últimos días
        cluster, session = get_cassandra_session()
        
        # Stats de matches por día
        stats_data = [
            (date.today() - timedelta(days=3), 4, 2, 0), # Hace 3 días: 4 matches, 2 fds, 0 feriado
            (date.today() - timedelta(days=2), 5, 0, 1), # Hace 2 días: 5 matches, 0 fds, 1 feriado
            (date.today() - timedelta(days=1), 3, 0, 0), # Ayer: 3 matches, 0 fds, 0 feriado
        ]
        for f, cant, fds, fer in stats_data:
            session.execute("""
                INSERT INTO match_stats_by_day (fecha, cantidad_coincidencias, cantidad_fin_de_semana, cantidad_feriado)
                VALUES (%s, %s, %s, %s)
            """, [f, cant, fds, fer])

        # Stats de swipes por día
        swipes_data = [
            (date.today() - timedelta(days=1), user_ids["Martina"], 10),
            (date.today() - timedelta(days=1), user_ids["Sofia"], 8),
            (date.today() - timedelta(days=1), user_ids["Juan"], 6),
            (date.today() - timedelta(days=1), user_ids["Diego"], 4),
        ]
        for f, dest, cant in swipes_data:
            session.execute("""
                INSERT INTO profile_swipes_by_day (fecha, id_usuario_destino, cantidad_likes)
                VALUES (%s, %s, %s)
            """, [f, dest, cant])

        # Duración promedio de citas previas
        durations_data = [
            (99, 10, datetime.now() - timedelta(hours=24), datetime.now() - timedelta(hours=22), 2.0),
            (100, 11, datetime.now() - timedelta(hours=48), datetime.now() - timedelta(hours=42), 6.0),
            (101, 12, datetime.now() - timedelta(hours=10), datetime.now() - timedelta(hours=9), 1.0),
        ]
        for ev_id, coin_id, f_msg, f_ac, dur in durations_data:
            session.execute("""
                INSERT INTO conversation_to_event_duration (id_evento, id_coincidencia, fecha_primer_mensaje, fecha_evento_aceptado, duracion_horas)
                VALUES (%s, %s, %s, %s, %s)
            """, [ev_id, coin_id, f_msg, f_ac, dur])

        cluster.shutdown()
        print("Datos históricos insertados en Cassandra.")
        print("¡El seeder finalizó con éxito!")

if __name__ == "__main__":
    seeder = Seeder()
    seeder.run()
