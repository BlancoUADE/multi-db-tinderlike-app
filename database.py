"""
Multi-DB consolidated database operations.
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2 import OperationalError

from pymongo import MongoClient
from pymongo.errors import PyMongoError

import redis
from redis.exceptions import RedisError

from cassandra.cluster import Cluster, NoHostAvailable
from cassandra import DependencyException, DriverException

from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable

# --- CONNECTIONS ---

def get_int_env(name, default):
    value = os.getenv(name)
    return int(value) if value else default

POSTGRES_CONFIG = {
    "host": os.getenv("PG_HOST", "127.0.0.1"),
    "port": get_int_env("PG_PORT", 5433),
    "dbname": os.getenv("PG_DB", "tinder_app"),
    "user": os.getenv("PG_USER", "tpo_user"),
    "password": os.getenv("PG_PASSWORD", "tpo_password"),
}
MONGO_URI = os.getenv("MONGO_URI", "mongodb://tpo_user:tpo_password@localhost:27017/")
MONGO_DB = os.getenv("MONGO_DB", "tinder_app")

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = get_int_env("REDIS_PORT", 6379)
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD")

CASSANDRA_HOSTS = os.getenv("CASSANDRA_HOSTS", "localhost").split(",")
CASSANDRA_PORT = get_int_env("CASSANDRA_PORT", 9042)
CASSANDRA_KEYSPACE = os.getenv("CASSANDRA_KEYSPACE", "tinder_app")

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "tpo_password")


def connect_postgres():
    return psycopg2.connect(**POSTGRES_CONFIG)

def connect_mongo():
    return MongoClient(MONGO_URI)

def connect_redis():
    return redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        password=REDIS_PASSWORD,
        decode_responses=True,
    )

def connect_cassandra():
    cluster = Cluster(CASSANDRA_HOSTS, port=CASSANDRA_PORT)
    session = cluster.connect()
    return cluster, session

def connect_neo4j():
    return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

# --- SCHEMAS ---

def ensure_postgres_schema(conn):
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS usuarios (
                id_usuario SERIAL PRIMARY KEY,
                nombre TEXT NOT NULL,
                edad INTEGER NOT NULL CHECK (edad > 0),
                genero TEXT NOT NULL,
                ubicacion TEXT NOT NULL,
                biografia TEXT NOT NULL,
                pref_edad_min INTEGER NOT NULL CHECK (pref_edad_min > 0),
                pref_edad_max INTEGER NOT NULL CHECK (pref_edad_max > 0),
                fecha_registro TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                CHECK (pref_edad_min <= pref_edad_max)
            );
            """
        )
        cur.execute("CREATE TABLE IF NOT EXISTS intereses (id_interes SERIAL PRIMARY KEY, nombre TEXT NOT NULL UNIQUE);")
        cur.execute("CREATE TABLE IF NOT EXISTS usuario_intereses (id_usuario INTEGER NOT NULL REFERENCES usuarios(id_usuario) ON DELETE CASCADE, id_interes INTEGER NOT NULL REFERENCES intereses(id_interes) ON DELETE CASCADE, PRIMARY KEY (id_usuario, id_interes));")
        cur.execute("CREATE TABLE IF NOT EXISTS fotos (id_foto SERIAL PRIMARY KEY, id_usuario INTEGER NOT NULL REFERENCES usuarios(id_usuario) ON DELETE CASCADE, url_archivo TEXT NOT NULL, es_principal BOOLEAN NOT NULL DEFAULT FALSE, fecha_subida TIMESTAMPTZ NOT NULL DEFAULT NOW());")
        cur.execute("CREATE TABLE IF NOT EXISTS likes (id_like SERIAL PRIMARY KEY, id_usuario_origen INTEGER NOT NULL REFERENCES usuarios(id_usuario) ON DELETE CASCADE, id_usuario_destino INTEGER NOT NULL REFERENCES usuarios(id_usuario) ON DELETE CASCADE, fecha_like TIMESTAMPTZ NOT NULL DEFAULT NOW(), UNIQUE (id_usuario_origen, id_usuario_destino), CHECK (id_usuario_origen != id_usuario_destino));")
        cur.execute("CREATE TABLE IF NOT EXISTS coincidencias (id_coincidencia SERIAL PRIMARY KEY, id_usuario1 INTEGER NOT NULL REFERENCES usuarios(id_usuario) ON DELETE CASCADE, id_usuario2 INTEGER NOT NULL REFERENCES usuarios(id_usuario) ON DELETE CASCADE, fecha_coincidencia TIMESTAMPTZ NOT NULL DEFAULT NOW(), UNIQUE (id_usuario1, id_usuario2), CHECK (id_usuario1 < id_usuario2));")
        cur.execute("CREATE TABLE IF NOT EXISTS mensajes (id_mensaje SERIAL PRIMARY KEY, id_coincidencia INTEGER NOT NULL REFERENCES coincidencias(id_coincidencia) ON DELETE CASCADE, id_emisor INTEGER NOT NULL REFERENCES usuarios(id_usuario) ON DELETE CASCADE, contenido TEXT NOT NULL, fecha_envio TIMESTAMPTZ NOT NULL DEFAULT NOW());")
        cur.execute("CREATE TABLE IF NOT EXISTS notificaciones (id_notificacion SERIAL PRIMARY KEY, id_usuario INTEGER NOT NULL REFERENCES usuarios(id_usuario) ON DELETE CASCADE, tipo TEXT NOT NULL, id_like INTEGER REFERENCES likes(id_like) ON DELETE SET NULL, id_coincidencia INTEGER REFERENCES coincidencias(id_coincidencia) ON DELETE SET NULL, id_mensaje INTEGER REFERENCES mensajes(id_mensaje) ON DELETE SET NULL, leida BOOLEAN NOT NULL DEFAULT FALSE, fecha_creacion TIMESTAMPTZ NOT NULL DEFAULT NOW());")
        
        cur.execute("CREATE INDEX IF NOT EXISTS idx_likes_destino ON likes(id_usuario_destino);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_mensajes_coincidencia ON mensajes(id_coincidencia);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_fotos_usuario ON fotos(id_usuario);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_usuario_intereses_interes ON usuario_intereses(id_interes);")
    conn.commit()

def ensure_cassandra_schema(session):
    session.execute(
        f"""
        CREATE KEYSPACE IF NOT EXISTS {CASSANDRA_KEYSPACE}
        WITH replication = {{'class': 'SimpleStrategy', 'replication_factor': 1}}
        """
    )
    session.set_keyspace(CASSANDRA_KEYSPACE)
    session.execute(
        """
        CREATE TABLE IF NOT EXISTS mensajes_por_coincidencia (
            id_coincidencia int,
            fecha_envio timestamp,
            id_mensaje int,
            id_emisor int,
            contenido text,
            PRIMARY KEY (id_coincidencia, fecha_envio, id_mensaje)
        ) WITH CLUSTERING ORDER BY (fecha_envio ASC, id_mensaje ASC);
        """
    )

# --- READ QUERIES (Postgres) ---

def fetch_user(conn, user_id):
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT * FROM usuarios WHERE id_usuario = %s", (user_id,))
        return cur.fetchone()

def list_users(conn):
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT id_usuario, nombre, edad, genero, ubicacion FROM usuarios ORDER BY id_usuario")
        return cur.fetchall()

def ensure_user_exists(conn, user_id):
    if not fetch_user(conn, user_id):
        print("No existe un usuario con ese ID.")
        return False
    return True

def view_user_profile(conn, user_id):
    if not ensure_user_exists(conn, user_id): return
    user = fetch_user(conn, user_id)
    print(f"\n=== Perfil de {user['nombre']} ===")
    print(f"ID: {user['id_usuario']} | Edad: {user['edad']} | Ubicación: {user['ubicacion']}")
    
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT i.nombre FROM usuario_intereses ui JOIN intereses i ON i.id_interes = ui.id_interes WHERE ui.id_usuario = %s", (user_id,))
        intereses = cur.fetchall()
        cur.execute("SELECT id_foto, url_archivo, es_principal FROM fotos WHERE id_usuario = %s ORDER BY fecha_subida", (user_id,))
        fotos = cur.fetchall()

    if intereses:
        print("Intereses:", ", ".join([r['nombre'] for r in intereses]))
    if fotos:
        print("Fotos:")
        for r in fotos:
            print(f"  - {r['url_archivo']} {'(principal)' if r['es_principal'] else ''}")

# --- SYNC / WRITE OPERATIONS ---

def sync_user_profile(conn, mongo_db, user_id):
    user = fetch_user(conn, user_id)
    if not user: return

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT i.nombre FROM usuario_intereses ui JOIN intereses i ON i.id_interes = ui.id_interes WHERE ui.id_usuario = %s", (user_id,))
        intereses = [row["nombre"] for row in cur.fetchall()]
        cur.execute("SELECT url_archivo, es_principal FROM fotos WHERE id_usuario = %s", (user_id,))
        fotos = [{"url": f["url_archivo"], "es_principal": f["es_principal"]} for f in cur.fetchall()]

    perfil = {
        "id_usuario": user["id_usuario"],
        "nombre": user["nombre"],
        "edad": user["edad"],
        "genero": user["genero"],
        "ubicacion": user["ubicacion"],
        "biografia": user["biografia"],
        "pref_edad_min": user["pref_edad_min"],
        "pref_edad_max": user["pref_edad_max"],
        "intereses": intereses,
        "fotos": fotos,
        "fecha_registro": user["fecha_registro"],
    }
    mongo_db["perfiles_usuarios"].update_one({"id_usuario": user_id}, {"$set": perfil}, upsert=True)

def create_notification(conn, redis_client, user_id, notification_type, **kwargs):
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO notificaciones (id_usuario, tipo, id_like, id_coincidencia, id_mensaje)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                user_id,
                notification_type,
                kwargs.get("id_like"),
                kwargs.get("id_coincidencia"),
                kwargs.get("id_mensaje"),
            ),
        )
    conn.commit()
    redis_key = f"user:{user_id}:unread_notifications"
    redis_client.incr(redis_key)

def get_unread_count(redis_client, user_id):
    redis_key = f"user:{user_id}:unread_notifications"
    val = redis_client.get(redis_key)
    return int(val) if val else 0

def register_user(conn, mongo_db, neo4j_driver, name, age, gender, location, bio, pref_min, pref_max):
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO usuarios (nombre, edad, genero, ubicacion, biografia, pref_edad_min, pref_edad_max)
            VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id_usuario
            """,
            (name, age, gender, location, bio, pref_min, pref_max),
        )
        user_id = cur.fetchone()[0]
    conn.commit()

    try: sync_user_profile(conn, mongo_db, user_id)
    except: pass

    try:
        with neo4j_driver.session() as session:
            session.run("MERGE (u:User {id: $id}) SET u.nombre = $nombre", id=user_id, nombre=name)
    except: pass

    return user_id

def create_interest(conn, name):
    with conn.cursor() as cur:
        cur.execute("INSERT INTO intereses (nombre) VALUES (%s) ON CONFLICT (nombre) DO UPDATE SET nombre = EXCLUDED.nombre RETURNING id_interes", (name,))
        interest_id = cur.fetchone()[0]
    conn.commit()
    return interest_id

def assign_interest(conn, mongo_db, user_id, interest_name):
    if not ensure_user_exists(conn, user_id): return None
    with conn.cursor() as cur:
        cur.execute("INSERT INTO intereses (nombre) VALUES (%s) ON CONFLICT (nombre) DO UPDATE SET nombre = EXCLUDED.nombre RETURNING id_interes", (interest_name,))
        interest_id = cur.fetchone()[0]
        cur.execute("INSERT INTO usuario_intereses (id_usuario, id_interes) VALUES (%s, %s) ON CONFLICT DO NOTHING", (user_id, interest_id))
    conn.commit()
    try: sync_user_profile(conn, mongo_db, user_id)
    except: pass
    return interest_id

def add_photo(conn, mongo_db, user_id, url, is_main=False):
    if not ensure_user_exists(conn, user_id): return None
    with conn.cursor() as cur:
        cur.execute("INSERT INTO fotos (id_usuario, url_archivo, es_principal) VALUES (%s, %s, %s) RETURNING id_foto", (user_id, url, is_main))
        photo_id = cur.fetchone()[0]
    conn.commit()
    try: sync_user_profile(conn, mongo_db, user_id)
    except: pass
    return photo_id

def create_like(conn, redis_client, neo4j_driver, origin, dest):
    try:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO likes (id_usuario_origen, id_usuario_destino) VALUES (%s, %s) RETURNING id_like", (origin, dest))
            like_id = cur.fetchone()[0]
        conn.commit()
        
        try:
            with neo4j_driver.session() as session:
                session.run("MATCH (a:User {id: $id_a}), (b:User {id: $id_b}) MERGE (a)-[:LIKES]->(b)", id_a=origin, id_b=dest)
        except: pass
        
        create_notification(conn, redis_client, dest, "like", id_like=like_id)
        return like_id
    except psycopg2.IntegrityError:
        conn.rollback()
        print("El like ya existe.")
        return None

def create_match(conn, redis_client, neo4j_driver, user1, user2):
    if user1 > user2: user1, user2 = user2, user1
    try:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO coincidencias (id_usuario1, id_usuario2) VALUES (%s, %s) RETURNING id_coincidencia", (user1, user2))
            match_id = cur.fetchone()[0]
        conn.commit()

        try:
            with neo4j_driver.session() as session:
                session.run("MATCH (a:User {id: $id_a}), (b:User {id: $id_b}) MERGE (a)-[:MATCHES]->(b)", id_a=user1, id_b=user2)
        except: pass

        create_notification(conn, redis_client, user1, "coincidencia", id_coincidencia=match_id)
        create_notification(conn, redis_client, user2, "coincidencia", id_coincidencia=match_id)
        return match_id
    except psycopg2.IntegrityError:
        conn.rollback()
        return None

def send_message(conn, redis_client, cassandra_session, match_id, sender_id, content):
    with conn.cursor() as cur:
        cur.execute("INSERT INTO mensajes (id_coincidencia, id_emisor, contenido) VALUES (%s, %s, %s) RETURNING id_mensaje, fecha_envio", (match_id, sender_id, content))
        message_id, sent_at = cur.fetchone()
    conn.commit()

    try:
        cassandra_session.set_keyspace(CASSANDRA_KEYSPACE)
        cassandra_session.execute(
            "INSERT INTO mensajes_por_coincidencia (id_coincidencia, fecha_envio, id_mensaje, id_emisor, contenido) VALUES (%s, %s, %s, %s, %s)",
            (match_id, sent_at, message_id, sender_id, content),
        )
    except: pass

    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id_usuario1, id_usuario2 FROM coincidencias WHERE id_coincidencia = %s", (match_id,))
            u1, u2 = cur.fetchone()
            recipient_id = u2 if u1 == sender_id else u1
        create_notification(conn, redis_client, recipient_id, "mensaje", id_mensaje=message_id)
    except: pass

    return message_id

def get_match_messages(conn, cassandra_session, match_id):
    try:
        cassandra_session.set_keyspace(CASSANDRA_KEYSPACE)
        result = cassandra_session.execute(
            "SELECT id_mensaje, id_emisor, contenido, fecha_envio FROM mensajes_por_coincidencia WHERE id_coincidencia = %s ORDER BY fecha_envio ASC",
            (match_id,)
        )
        msgs = list(result)
        if msgs:
            users_map = {}
            for row in list_users(conn): users_map[row["id_usuario"]] = row["nombre"]
            return [{"emisor": users_map.get(m.id_emisor, str(m.id_emisor)), "contenido": m.contenido, "fecha_envio": m.fecha_envio} for m in msgs]
    except Exception as e:
        print("Cassandra error, fallback a Postgres", e)

    # Fallback Postgres
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT m.id_mensaje, u.nombre AS emisor, m.contenido, m.fecha_envio FROM mensajes m JOIN usuarios u ON u.id_usuario = m.id_emisor WHERE m.id_coincidencia = %s ORDER BY m.fecha_envio", (match_id,))
        return cur.fetchall()

def reset_database(conn, mongo_db, redis_client, cassandra_session):
    conn.rollback()
    print("Borrando PostgreSQL...")
    tables_to_truncate = ["notificaciones", "mensajes", "coincidencias", "likes", "fotos", "usuario_intereses", "usuarios", "intereses"]
    with conn.cursor() as cur:
        try:
            cur.execute(f"TRUNCATE TABLE {', '.join(tables_to_truncate)} RESTART IDENTITY CASCADE;")
            conn.commit()
            print("✓ PostgreSQL limpiado")
        except psycopg2.Error as e:
            conn.rollback()

    print("Borrando MongoDB...")
    try: mongo_db["perfiles_usuarios"].delete_many({}); print("✓ MongoDB limpiado")
    except: pass

    print("Borrando Redis...")
    try: redis_client.flushdb(); print("✓ Redis limpiado")
    except: pass

    print("Borrando Cassandra...")
    try: cassandra_session.execute(f"DROP KEYSPACE IF EXISTS {CASSANDRA_KEYSPACE};"); print("✓ Cassandra limpiado")
    except: pass

    print("\n✅ Todas las bases de datos limpiadas.")
