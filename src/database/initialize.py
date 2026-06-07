import os
from src.database.connection import (
    get_postgres_connection,
    get_mongodb_database,
    get_cassandra_session,
    get_neo4j_driver
)

def init_postgres():
    print("Inicializando PostgreSQL...")
    conn = get_postgres_connection()
    try:
        # Read SQL file
        sql_path = os.path.join(os.path.dirname(__file__), "init_postgres.sql")
        with open(sql_path, "r", encoding="utf-8") as f:
            sql_script = f.read()
        
        with conn.cursor() as cur:
            cur.execute(sql_script)
        conn.commit()
        print("PostgreSQL inicializado correctamente.")
    except Exception as e:
        conn.rollback()
        print(f"Error al inicializar PostgreSQL: {e}")
        raise e
    finally:
        conn.close()

def init_mongodb():
    print("Inicializando MongoDB...")
    try:
        db = get_mongodb_database()
        # Create collections if they don't exist
        collections = ["perfiles", "historial_login", "historial_cambios_perfil", "notificaciones"]
        for col in collections:
            if col not in db.list_collection_names():
                db.create_collection(col)
        
        # Create unique index on user_id for perfiles
        db.perfiles.create_index("user_id", unique=True)
        print("MongoDB inicializado correctamente.")
    except Exception as e:
        print(f"Error al inicializar MongoDB: {e}")
        raise e

def init_cassandra():
    print("Inicializando Cassandra...")
    cluster, session = get_cassandra_session()
    try:
        # Create swipes_por_dia
        session.execute("""
            CREATE TABLE IF NOT EXISTS swipes_por_dia (
                fecha date,
                swipe_id uuid,
                user_from int,
                user_to int,
                tipo text,
                PRIMARY KEY (fecha, swipe_id)
            )
        """)
        # Create swipes_recibidos_por_perfil
        session.execute("""
            CREATE TABLE IF NOT EXISTS swipes_recibidos_por_perfil (
                user_to int,
                tipo text,
                swipe_id uuid,
                user_from int,
                fecha timestamp,
                PRIMARY KEY (user_to, tipo, swipe_id)
            )
        """)
        # Create mensajes_por_conversacion
        session.execute("""
            CREATE TABLE IF NOT EXISTS mensajes_por_conversacion (
                match_id int,
                timestamp timestamp,
                message_id uuid,
                sender_id int,
                texto text,
                PRIMARY KEY (match_id, timestamp)
            ) WITH CLUSTERING ORDER BY (timestamp ASC)
        """)
        # Create matches_por_dia
        session.execute("""
            CREATE TABLE IF NOT EXISTS matches_por_dia (
                fecha date,
                match_id int,
                user_1 int,
                user_2 int,
                timestamp timestamp,
                PRIMARY KEY (fecha, match_id)
            )
        """)
        # Create actividad_usuario_por_fecha
        session.execute("""
            CREATE TABLE IF NOT EXISTS actividad_usuario_por_fecha (
                user_id int,
                fecha date,
                timestamp timestamp,
                actividad text,
                PRIMARY KEY (user_id, fecha, timestamp)
            ) WITH CLUSTERING ORDER BY (fecha DESC, timestamp DESC)
        """)
        print("Cassandra inicializado correctamente.")
    except Exception as e:
        print(f"Error al inicializar Cassandra: {e}")
        raise e
    finally:
        cluster.shutdown()

def init_neo4j():
    print("Inicializando Neo4j...")
    driver = get_neo4j_driver()
    try:
        with driver.session() as session:
            # Neo4j 5 syntax for uniqueness constraint: CREATE CONSTRAINT FOR (u:Usuario) REQUIRE u.id IS UNIQUE
            session.run("CREATE CONSTRAINT unique_user_id IF NOT EXISTS FOR (u:Usuario) REQUIRE u.id IS UNIQUE")
            session.run("CREATE CONSTRAINT unique_interest_name IF NOT EXISTS FOR (i:Interes) REQUIRE i.nombre IS UNIQUE")
            session.run("CREATE CONSTRAINT unique_event_id IF NOT EXISTS FOR (e:Evento) REQUIRE e.id IS UNIQUE")
        print("Neo4j inicializado correctamente.")
    except Exception as e:
        print(f"Error al inicializar Neo4j: {e}")
        raise e
    finally:
        driver.close()

def run_all():
    print("=== INICIALIZANDO BASES DE DATOS ===")
    init_postgres()
    init_mongodb()
    init_cassandra()
    init_neo4j()
    print("=== TODAS LAS BASES DE DATOS INICIALIZADAS CON ÉXITO ===")

if __name__ == "__main__":
    run_all()
