import sys
import builtins
import inspect
from datetime import datetime, date, timedelta
from app.databases.postgres_conn import get_postgres_connection
from app.databases.redis_conn import get_redis_client
from app.databases.mongo_conn import get_mongo_db
from app.databases.cassandra_conn import get_cassandra_session
from app.databases.neo4j_conn import get_neo4j_driver
from app.cli.main_cli import TinderCLI

# Save original builtin input and exit
_original_input = builtins.input
_original_exit = sys.exit

# Global mock queues and active search action
_simulated_inputs = []
active_search_action = None

# Custom simulated datetimes subclasses to bypass Python's isinstance check
class SimulatedDateTime(datetime):
    current_time = None

    @classmethod
    def now(cls, tz=None):
        if cls.current_time is not None:
            return cls.current_time
        return datetime.now(tz)

    @classmethod
    def utcnow(cls):
        if cls.current_time is not None:
            return cls.current_time
        return datetime.utcnow()

class SimulatedDate(date):
    current_date = None

    @classmethod
    def today(cls):
        if cls.current_date is not None:
            return cls.current_date
        return date.today()

# Helper action class for recommend swipes
class SearchAction:
    def __init__(self, target_name, action="1"):
        self.target_name = target_name
        self.action = action
        self.done = False

    def __call__(self, perfil_name):
        if self.done:
            return "5" # Volver
        
        if perfil_name == self.target_name:
            self.done = True
            return self.action
        else:
            return "2" # Saltar Perfil (Skip)

def get_caller_perfil_name():
    for frame_info in inspect.stack():
        if frame_info.function == 'buscar_perfiles':
            locals_dict = frame_info.frame.f_locals
            if 'perfil' in locals_dict and locals_dict['perfil']:
                return locals_dict['perfil']['nombre']
    return None

def simulated_input(prompt=""):
    global active_search_action
    
    # 0. Global handling for ENTER prompts
    if "presione enter" in prompt.lower():
        active_search_action = None
        print(f"[MOCK INPUT] {prompt.strip()} -> <ENTER>")
        return ""
        
    # 1. Check if we are inside buscar_perfiles function
    in_search = False
    for frame_info in inspect.stack():
        if frame_info.function == 'buscar_perfiles':
            in_search = True
            break
            
    if in_search:
        if active_search_action is None:
            if _simulated_inputs and isinstance(_simulated_inputs[0], SearchAction):
                active_search_action = _simulated_inputs.pop(0)
            else:
                print(f"[MOCK INPUT] {prompt.strip()} (No active SearchAction) -> 5")
                return "5" # Volver
                
        perfil_name = get_caller_perfil_name()
        res = active_search_action(perfil_name)
        if res == "5":
            active_search_action = None
        print(f"[MOCK INPUT] {prompt.strip()} (Search: {perfil_name}) -> {res}")
        return res

    # 2. General queue consumption
    if _simulated_inputs:
        val = _simulated_inputs.pop(0)
        if callable(val):
            val = val()
        print(f"[MOCK INPUT] {prompt.strip()} -> {val}")
        return val
    return ""

def mock_exit(code=0):
    raise SystemExit(code)

def get_pending_event_id():
    for frame_info in inspect.stack():
        locals_dict = frame_info.frame.f_locals
        if 'recibidas' in locals_dict:
            recibidas = locals_dict['recibidas']
            if recibidas:
                return str(recibidas[0]['id_evento'])
    return ""

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
        session.execute("TRUNCATE swipes_perfil_por_dia;")
        session.execute("TRUNCATE swipes_perfil_total;")
        session.execute("TRUNCATE duracion_conversacion_a_evento;")
        print("- Cassandra limpia.")

        # 5. Neo4j
        driver = get_neo4j_driver()
        with driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
        driver.close()
        print("- Neo4j limpia.")

    def run(self):
        self.wipe_databases()
        print("Iniciando simulación de carga a través del CLI...")

        # Setup mocks and monkeypatches
        builtins.input = simulated_input
        sys.exit = mock_exit

        # Import modules to patch
        import app.services.auth_service
        import app.services.profile_service
        import app.services.match_service
        import app.services.event_service
        import app.services.block_service
        import app.services.report_service
        import app.cli.main_cli
        import app.repositories.postgres_repo
        import app.repositories.cassandra_repo
        import app.repositories.redis_repo
        import app.repositories.mongo_repo
        import app.repositories.neo4j_repo

        # Apply mock datetime classes to imported references
        modules_to_patch = [
            app.services.auth_service,
            app.services.profile_service,
            app.services.match_service,
            app.services.event_service,
            app.services.block_service,
            app.services.report_service,
            app.cli.main_cli,
            app.repositories.postgres_repo,
            app.repositories.cassandra_repo,
            app.repositories.redis_repo,
            app.repositories.mongo_repo,
            app.repositories.neo4j_repo
        ]
        for mod in modules_to_patch:
            if hasattr(mod, 'datetime'):
                mod.datetime = SimulatedDateTime
            if hasattr(mod, 'date'):
                mod.date = SimulatedDate

        try:
            # 1. Cargar feriados
            today = date.today()
            conn = get_postgres_connection()
            cur = conn.cursor()
            feriados_list = [
                (today.strftime("%Y-%m-%d"), "Día del Seeder Especial"),
                ((today - timedelta(days=2)).strftime("%Y-%m-%d"), "Feriado Histórico"),
                ("2026-01-01", "Año Nuevo"),
                ("2026-05-25", "Revolución de Mayo"),
                ("2026-07-09", "Día de la Independencia"),
                ("2026-12-25", "Navidad")
            ]
            for f_date, desc in feriados_list:
                cur.execute("""
                    INSERT INTO feriados (fecha, descripcion) VALUES (%s, %s)
                    ON CONFLICT (fecha) DO UPDATE SET descripcion = %s
                """, (f_date, desc, desc))
            conn.commit()
            cur.close()
            conn.close()
            print("Feriados registrados.")

            # 2. Registrar 11 usuarios (hace 5 días)
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

            fecha_reg = datetime.now() - timedelta(days=5)
            SimulatedDateTime.current_time = fecha_reg
            SimulatedDate.current_date = fecha_reg.date()

            # Execute registrations
            for u in usuarios_data:
                global _simulated_inputs
                _simulated_inputs = [
                    "1", # Registrarse
                    u["nombre"],
                    str(u["edad"]),
                    u["genero"],
                    u["ubicacion"],
                    u["biografia"],
                    str(u["pref_edad_min"]),
                    str(u["pref_edad_max"]),
                    u["email"],
                    u["password"],
                    u["foto"],
                    u["intereses"],
                    "3" # Salir
                ]
                try:
                    cli = TinderCLI()
                    cli.run()
                except SystemExit:
                    pass

            print("Usuarios registrados a través de la CLI simulada.")

            # Load user IDs from Postgres
            conn = get_postgres_connection()
            cur = conn.cursor()
            cur.execute("SELECT id_usuario, nombre FROM usuarios;")
            name_to_id = {row[1]: row[0] for row in cur.fetchall()}
            cur.close()
            conn.close()

            # 3. Fotos adicionales (hace 5 días)
            for u in usuarios_data:
                _simulated_inputs = [
                    "2", # Iniciar sesión
                    u["email"],
                    u["password"],
                    "1", # Mi perfil
                    "4", # Gestionar fotos
                ]
                if u["nombre"] == "Diego":
                    for i in range(2, 12):
                        _simulated_inputs += [
                            "2",
                            f"diego_foto_{i}.jpg",
                            "N"
                        ]
                else:
                    _simulated_inputs += [
                        "2",
                        f"{u['nombre'].lower()}_adicional.jpg",
                        "N"
                    ]
                _simulated_inputs += [
                    "5", "6", "7", "3"
                ]
                try:
                    cli = TinderCLI()
                    cli.run()
                except SystemExit:
                    pass

            print("Fotos adicionales agregadas por cada usuario a través de la CLI.")

            # 4. Día -3: Nicolas <-> Sofia
            fecha_3_dias = datetime.now() - timedelta(days=3)
            
            # Nicolas likes Sofia
            SimulatedDateTime.current_time = fecha_3_dias
            SimulatedDate.current_date = fecha_3_dias.date()
            _simulated_inputs = [
                "2", "nicolas@example.com", "password123",
                "2", SearchAction("Sofia", "1"),
                "7", "3"
            ]
            try:
                cli = TinderCLI()
                cli.run()
            except SystemExit:
                pass

            # Sofia likes Nicolas (Match)
            SimulatedDateTime.current_time = fecha_3_dias + timedelta(minutes=30)
            SimulatedDate.current_date = fecha_3_dias.date()
            _simulated_inputs = [
                "2", "sofia@example.com", "password123",
                "2", SearchAction("Nicolas", "1"),
                "7", "3"
            ]
            try:
                cli = TinderCLI()
                cli.run()
            except SystemExit:
                pass

            # Nicolas envía mensaje
            SimulatedDateTime.current_time = fecha_3_dias + timedelta(hours=1)
            _simulated_inputs = [
                "2", "nicolas@example.com", "password123",
                "3", "2", lambda: str(name_to_id["Sofia"]), "Hola Sofia, ¿qué estás leyendo hoy?",
                "7", "7", "3"
            ]
            try:
                cli = TinderCLI()
                cli.run()
            except SystemExit:
                pass

            # Sofia responde
            SimulatedDateTime.current_time = fecha_3_dias + timedelta(hours=2)
            _simulated_inputs = [
                "2", "sofia@example.com", "password123",
                "3", "2", lambda: str(name_to_id["Nicolas"]), "Hola Nico, estoy leyendo una novela de ciencia ficción.",
                "7", "7", "3"
            ]
            try:
                cli = TinderCLI()
                cli.run()
            except SystemExit:
                pass

            # Nicolas propone cita
            SimulatedDateTime.current_time = fecha_3_dias + timedelta(hours=3)
            fecha_cita = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d 20:30")
            _simulated_inputs = [
                "2", "nicolas@example.com", "password123",
                "3", "3", lambda: str(name_to_id["Sofia"]), "Café y charla de libros", fecha_cita, "Café Tortoni, CABA",
                "7", "7", "3"
            ]
            try:
                cli = TinderCLI()
                cli.run()
            except SystemExit:
                pass

            print("Interacciones del Día -3 (Nicolas <-> Sofia) simuladas.")

            # 5. Día -2: Juan <-> Martina
            fecha_2_dias = datetime.now() - timedelta(days=2) # Feriado Histórico

            # Juan likes Martina
            SimulatedDateTime.current_time = fecha_2_dias
            SimulatedDate.current_date = fecha_2_dias.date()
            _simulated_inputs = [
                "2", "juan@example.com", "password123",
                "2", SearchAction("Martina", "1"),
                "7", "3"
            ]
            try:
                cli = TinderCLI()
                cli.run()
            except SystemExit:
                pass

            # Martina likes Juan (Match)
            SimulatedDateTime.current_time = fecha_2_dias + timedelta(minutes=5)
            _simulated_inputs = [
                "2", "martina@example.com", "password123",
                "2", SearchAction("Juan", "1"),
                "7", "3"
            ]
            try:
                cli = TinderCLI()
                cli.run()
            except SystemExit:
                pass

            # Juan envía primer mensaje
            SimulatedDateTime.current_time = fecha_2_dias + timedelta(minutes=10)
            _simulated_inputs = [
                "2", "juan@example.com", "password123",
                "3", "2", lambda: str(name_to_id["Martina"]), "¡Hola Martina! ¿Cómo estás?",
                "7", "7", "3"
            ]
            try:
                cli = TinderCLI()
                cli.run()
            except SystemExit:
                pass

            # Martina responde
            SimulatedDateTime.current_time = fecha_2_dias + timedelta(minutes=15)
            _simulated_inputs = [
                "2", "martina@example.com", "password123",
                "3", "2", lambda: str(name_to_id["Juan"]), "Hola Juan, ¡bien y vos! Vi que nos gusta el cine.",
                "7", "7", "3"
            ]
            try:
                cli = TinderCLI()
                cli.run()
            except SystemExit:
                pass

            # Juan responde y propone cita
            SimulatedDateTime.current_time = fecha_2_dias + timedelta(minutes=20)
            _simulated_inputs = [
                "2", "juan@example.com", "password123",
                "3", "2", lambda: str(name_to_id["Martina"]), "Sí, ¡totalmente! Me encanta el cine clásico.",
                "3", lambda: str(name_to_id["Martina"]), "Cena y Cine de clásicos", fecha_cita, "Cine Lorca, CABA",
                "7", "7", "3"
            ]
            try:
                cli = TinderCLI()
                cli.run()
            except SystemExit:
                pass

            # Martina acepta la cita
            SimulatedDateTime.current_time = fecha_2_dias + timedelta(hours=3)
            _simulated_inputs = [
                "2", "martina@example.com", "password123",
                "3", "5", get_pending_event_id, "A",
                "7", "7", "3"
            ]
            try:
                cli = TinderCLI()
                cli.run()
            except SystemExit:
                pass

            print("Interacciones del Día -2 (Juan <-> Martina) simuladas.")

            # 6. Día -1: Lucas <-> Camila
            fecha_1_dia = datetime.now() - timedelta(days=1)

            # Lucas likes Camila
            SimulatedDateTime.current_time = fecha_1_dia
            SimulatedDate.current_date = fecha_1_dia.date()
            _simulated_inputs = [
                "2", "lucas@example.com", "password123",
                "2", SearchAction("Camila", "1"),
                "7", "3"
            ]
            try:
                cli = TinderCLI()
                cli.run()
            except SystemExit:
                pass

            # Camila likes Lucas (Match)
            SimulatedDateTime.current_time = fecha_1_dia + timedelta(minutes=10)
            _simulated_inputs = [
                "2", "camila@example.com", "password123",
                "2", SearchAction("Lucas", "1"),
                "7", "3"
            ]
            try:
                cli = TinderCLI()
                cli.run()
            except SystemExit:
                pass

            # Lucas envía mensaje
            SimulatedDateTime.current_time = fecha_1_dia + timedelta(minutes=20)
            _simulated_inputs = [
                "2", "lucas@example.com", "password123",
                "3", "2", lambda: str(name_to_id["Camila"]), "¡Hola Camila! Qué buenas fotos tenés.",
                "7", "7", "3"
            ]
            try:
                cli = TinderCLI()
                cli.run()
            except SystemExit:
                pass

            # Camila responde
            SimulatedDateTime.current_time = fecha_1_dia + timedelta(minutes=30)
            _simulated_inputs = [
                "2", "camila@example.com", "password123",
                "3", "2", lambda: str(name_to_id["Lucas"]), "Hola Lucas, ¡gracias! Son de mis viajes.",
                "7", "7", "3"
            ]
            try:
                cli = TinderCLI()
                cli.run()
            except SystemExit:
                pass

            # Lucas propone cita
            SimulatedDateTime.current_time = fecha_1_dia + timedelta(hours=1)
            _simulated_inputs = [
                "2", "lucas@example.com", "password123",
                "3", "3", lambda: str(name_to_id["Camila"]), "Paseo por la costanera", fecha_cita, "Costanera Rosario",
                "7", "7", "3"
            ]
            try:
                cli = TinderCLI()
                cli.run()
            except SystemExit:
                pass

            # Camila rechaza la cita
            SimulatedDateTime.current_time = fecha_1_dia + timedelta(hours=2)
            _simulated_inputs = [
                "2", "camila@example.com", "password123",
                "3", "5", get_pending_event_id, "R",
                "7", "7", "3"
            ]
            try:
                cli = TinderCLI()
                cli.run()
            except SystemExit:
                pass

            print("Interacciones del Día -1 (Lucas <-> Camila) simuladas.")

            # 7. Día 0 (Hoy)
            fecha_hoy = datetime.now()
            SimulatedDateTime.current_time = fecha_hoy
            SimulatedDate.current_date = fecha_hoy.date()

            # Diego likes Valentina
            _simulated_inputs = [
                "2", "diego@example.com", "password123",
                "2", SearchAction("Valentina", "1"),
                "7", "3"
            ]
            try:
                cli = TinderCLI()
                cli.run()
            except SystemExit:
                pass

            # Valentina likes Diego (Match)
            _simulated_inputs = [
                "2", "valentina@example.com", "password123",
                "2", SearchAction("Diego", "1"),
                "7", "3"
            ]
            try:
                cli = TinderCLI()
                cli.run()
            except SystemExit:
                pass

            # Joaquin likes Agustina
            _simulated_inputs = [
                "2", "joaquin@example.com", "password123",
                "2", SearchAction("Agustina", "1"),
                "7", "3"
            ]
            try:
                cli = TinderCLI()
                cli.run()
            except SystemExit:
                pass

            # Agustina likes Joaquin (Match)
            _simulated_inputs = [
                "2", "agustina@example.com", "password123",
                "2", SearchAction("Joaquin", "1"),
                "7", "3"
            ]
            try:
                cli = TinderCLI()
                cli.run()
            except SystemExit:
                pass

            # Mateo likes Sofia, Martina, Valentina
            _simulated_inputs = [
                "2", "mateo@example.com", "password123",
                "2", SearchAction("Sofia", "1"),
                "2", SearchAction("Martina", "1"),
                "2", SearchAction("Valentina", "1"),
                "7", "3"
            ]
            try:
                cli = TinderCLI()
                cli.run()
            except SystemExit:
                pass

            print("Likes e interacciones del Día 0 (Hoy) simuladas.")

            # 8. Bloqueos
            # Nicolas bloquea a Juan (activo)
            _simulated_inputs = [
                "2", "nicolas@example.com", "password123",
                "4", "2", lambda: str(name_to_id["Juan"]), "4",
                "7", "3"
            ]
            try:
                cli = TinderCLI()
                cli.run()
            except SystemExit:
                pass

            # Juan bloquea a Mateo, luego lo desbloquea
            _simulated_inputs = [
                "2", "juan@example.com", "password123",
                "4",
                "2", lambda: str(name_to_id["Mateo"]),
                "3", lambda: str(name_to_id["Mateo"]),
                "4",
                "7", "3"
            ]
            try:
                cli = TinderCLI()
                cli.run()
            except SystemExit:
                pass

            print("Bloqueos y desbloqueos del Día 0 (Hoy) simulados.")

        finally:
            # Restore inputs and exits
            builtins.input = _original_input
            sys.exit = _original_exit
            
            # Reset simulated date values
            SimulatedDateTime.current_time = None
            SimulatedDate.current_date = None

            # Restore original datetime and date in modules
            for mod in modules_to_patch:
                if hasattr(mod, 'datetime'):
                    mod.datetime = datetime
                if hasattr(mod, 'date'):
                    mod.date = date

        print("¡El seeder finalizó con éxito!")

if __name__ == "__main__":
    seeder = Seeder()
    seeder.run()
