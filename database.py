"""
Operaciones de persistencia para el CLI Tinder Multi-DB.

PostgreSQL es la fuente de verdad transaccional. MongoDB, Redis,
Cassandra y Neo4j se actualizan desde esos eventos para cubrir consultas
documentales, temporales, de cache/TTL y de grafo.
"""

import os
import uuid
from datetime import datetime, timezone

import psycopg2
from psycopg2.extras import RealDictCursor
from pymongo import MongoClient
import redis
from cassandra.cluster import Cluster
from neo4j import GraphDatabase


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
MONGO_PROFILE_COLLECTION = "perfiles_usuarios"
MONGO_LOGIN_COLLECTION = "sesiones_login"

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = get_int_env("REDIS_PORT", 6379)
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD")
SESSION_TTL_SECONDS = get_int_env("SESSION_TTL_SECONDS", 1800)

CASSANDRA_HOSTS = os.getenv("CASSANDRA_HOSTS", "localhost").split(",")
CASSANDRA_PORT = get_int_env("CASSANDRA_PORT", 9042)
CASSANDRA_KEYSPACE = os.getenv("CASSANDRA_KEYSPACE", "tinder_app")
CASSANDRA_MESSAGES_TABLE = "mensajes_por_coincidencia"

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "tpo_password")


def connect_postgres():
    return psycopg2.connect(**POSTGRES_CONFIG)


def connect_mongo():
    client = MongoClient(MONGO_URI)
    client.admin.command("ping")
    return client


def connect_redis():
    client = redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        password=REDIS_PASSWORD,
        decode_responses=True,
    )
    client.ping()
    return client


def connect_cassandra():
    cluster = Cluster(CASSANDRA_HOSTS, port=CASSANDRA_PORT)
    session = cluster.connect()
    return cluster, session


def connect_neo4j():
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    driver.verify_connectivity()
    return driver


def warn(service, error):
    print(f"[WARN] No se pudo sincronizar {service}: {error}")


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
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS intereses (
                id_interes SERIAL PRIMARY KEY,
                nombre TEXT NOT NULL UNIQUE
            );
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS usuario_intereses (
                id_usuario INTEGER NOT NULL REFERENCES usuarios(id_usuario) ON DELETE CASCADE,
                id_interes INTEGER NOT NULL REFERENCES intereses(id_interes) ON DELETE CASCADE,
                PRIMARY KEY (id_usuario, id_interes)
            );
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS fotos (
                id_foto SERIAL PRIMARY KEY,
                id_usuario INTEGER NOT NULL REFERENCES usuarios(id_usuario) ON DELETE CASCADE,
                url_archivo TEXT NOT NULL,
                es_principal BOOLEAN NOT NULL DEFAULT FALSE,
                fecha_subida TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS likes (
                id_like SERIAL PRIMARY KEY,
                id_usuario_origen INTEGER NOT NULL REFERENCES usuarios(id_usuario) ON DELETE CASCADE,
                id_usuario_destino INTEGER NOT NULL REFERENCES usuarios(id_usuario) ON DELETE CASCADE,
                fecha_like TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                UNIQUE (id_usuario_origen, id_usuario_destino),
                CHECK (id_usuario_origen <> id_usuario_destino)
            );
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS bloqueos (
                id_bloqueo SERIAL PRIMARY KEY,
                id_bloqueador INTEGER NOT NULL REFERENCES usuarios(id_usuario) ON DELETE CASCADE,
                id_bloqueado INTEGER NOT NULL REFERENCES usuarios(id_usuario) ON DELETE CASCADE,
                fecha_bloqueo TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                UNIQUE (id_bloqueador, id_bloqueado),
                CHECK (id_bloqueador <> id_bloqueado)
            );
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS coincidencias (
                id_coincidencia SERIAL PRIMARY KEY,
                id_usuario1 INTEGER NOT NULL REFERENCES usuarios(id_usuario) ON DELETE CASCADE,
                id_usuario2 INTEGER NOT NULL REFERENCES usuarios(id_usuario) ON DELETE CASCADE,
                fecha_coincidencia TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                UNIQUE (id_usuario1, id_usuario2),
                CHECK (id_usuario1 < id_usuario2)
            );
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS mensajes (
                id_mensaje SERIAL PRIMARY KEY,
                id_coincidencia INTEGER NOT NULL REFERENCES coincidencias(id_coincidencia) ON DELETE CASCADE,
                id_emisor INTEGER NOT NULL REFERENCES usuarios(id_usuario) ON DELETE CASCADE,
                contenido TEXT NOT NULL,
                fecha_envio TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS eventos (
                id_evento SERIAL PRIMARY KEY,
                nombre_evento TEXT NOT NULL,
                fecha TIMESTAMPTZ NOT NULL,
                ubicacion TEXT NOT NULL,
                id_organizador INTEGER NOT NULL REFERENCES usuarios(id_usuario) ON DELETE CASCADE
            );
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS asistencia_eventos (
                id_asistencia SERIAL PRIMARY KEY,
                id_usuario INTEGER NOT NULL REFERENCES usuarios(id_usuario) ON DELETE CASCADE,
                id_evento INTEGER NOT NULL REFERENCES eventos(id_evento) ON DELETE CASCADE,
                estado TEXT NOT NULL CHECK (estado IN ('interesado', 'confirmado', 'cancelado')),
                fecha_registro TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                UNIQUE (id_usuario, id_evento)
            );
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS notificaciones (
                id_notificacion SERIAL PRIMARY KEY,
                id_usuario INTEGER NOT NULL REFERENCES usuarios(id_usuario) ON DELETE CASCADE,
                tipo TEXT NOT NULL CHECK (tipo IN ('like', 'match', 'mensaje', 'evento')),
                id_like INTEGER REFERENCES likes(id_like) ON DELETE SET NULL,
                id_coincidencia INTEGER REFERENCES coincidencias(id_coincidencia) ON DELETE SET NULL,
                id_mensaje INTEGER REFERENCES mensajes(id_mensaje) ON DELETE SET NULL,
                id_evento INTEGER REFERENCES eventos(id_evento) ON DELETE SET NULL,
                leida BOOLEAN NOT NULL DEFAULT FALSE,
                fecha_creacion TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            """
        )
        cur.execute("ALTER TABLE notificaciones ADD COLUMN IF NOT EXISTS id_evento INTEGER REFERENCES eventos(id_evento) ON DELETE SET NULL;")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_likes_origen ON likes(id_usuario_origen);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_likes_destino ON likes(id_usuario_destino);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_mensajes_coincidencia ON mensajes(id_coincidencia, fecha_envio);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_fotos_usuario ON fotos(id_usuario);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_notificaciones_usuario ON notificaciones(id_usuario, leida);")
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
        f"""
        CREATE TABLE IF NOT EXISTS {CASSANDRA_MESSAGES_TABLE} (
            id_coincidencia int,
            fecha_envio timestamp,
            id_mensaje int,
            id_emisor int,
            contenido text,
            PRIMARY KEY (id_coincidencia, fecha_envio, id_mensaje)
        ) WITH CLUSTERING ORDER BY (fecha_envio ASC, id_mensaje ASC);
        """
    )


def ensure_neo4j_schema(driver):
    with driver.session() as session:
        session.run("CREATE CONSTRAINT usuario_id IF NOT EXISTS FOR (u:Usuario) REQUIRE u.id_usuario IS UNIQUE")
        session.run("CREATE CONSTRAINT interes_nombre IF NOT EXISTS FOR (i:Interes) REQUIRE i.nombre IS UNIQUE")
        session.run("CREATE CONSTRAINT evento_id IF NOT EXISTS FOR (e:Evento) REQUIRE e.id_evento IS UNIQUE")


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


def get_match(conn, match_id):
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT * FROM coincidencias WHERE id_coincidencia = %s", (match_id,))
        return cur.fetchone()


def user_is_blocked(conn, user1, user2):
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT 1
            FROM bloqueos
            WHERE (id_bloqueador = %s AND id_bloqueado = %s)
               OR (id_bloqueador = %s AND id_bloqueado = %s)
            """,
            (user1, user2, user2, user1),
        )
        return cur.fetchone() is not None


def view_user_profile(conn, user_id):
    if not ensure_user_exists(conn, user_id):
        return
    user = fetch_user(conn, user_id)
    print(f"\n=== Perfil de {user['nombre']} ===")
    print(f"ID: {user['id_usuario']} | Edad: {user['edad']} | Ubicacion: {user['ubicacion']}")
    print(f"Bio: {user['biografia']}")

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT i.nombre
            FROM usuario_intereses ui
            JOIN intereses i ON i.id_interes = ui.id_interes
            WHERE ui.id_usuario = %s
            ORDER BY i.nombre
            """,
            (user_id,),
        )
        intereses = cur.fetchall()
        cur.execute(
            """
            SELECT id_foto, url_archivo, es_principal
            FROM fotos
            WHERE id_usuario = %s
            ORDER BY es_principal DESC, fecha_subida
            """,
            (user_id,),
        )
        fotos = cur.fetchall()

    if intereses:
        print("Intereses:", ", ".join([row["nombre"] for row in intereses]))
    if fotos:
        print("Fotos:")
        for row in fotos:
            tag = " (principal)" if row["es_principal"] else ""
            print(f"  - {row['url_archivo']}{tag}")


def sync_user_profile(conn, mongo_db, user_id):
    user = fetch_user(conn, user_id)
    if not user:
        return

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT i.id_interes, i.nombre
            FROM usuario_intereses ui
            JOIN intereses i ON i.id_interes = ui.id_interes
            WHERE ui.id_usuario = %s
            ORDER BY i.nombre
            """,
            (user_id,),
        )
        intereses = [dict(row) for row in cur.fetchall()]
        cur.execute(
            """
            SELECT id_foto, url_archivo, es_principal, fecha_subida
            FROM fotos
            WHERE id_usuario = %s
            ORDER BY es_principal DESC, fecha_subida
            """,
            (user_id,),
        )
        fotos = [dict(row) for row in cur.fetchall()]

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
        "actualizado_en": datetime.now(timezone.utc),
    }
    mongo_db[MONGO_PROFILE_COLLECTION].update_one({"id_usuario": user_id}, {"$set": perfil}, upsert=True)


def sync_user_to_neo4j(driver, user):
    with driver.session() as session:
        session.run(
            """
            MERGE (u:Usuario {id_usuario: $id_usuario})
            SET u.nombre = $nombre,
                u.edad = $edad,
                u.genero = $genero,
                u.ubicacion = $ubicacion
            """,
            id_usuario=user["id_usuario"],
            nombre=user["nombre"],
            edad=user["edad"],
            genero=user["genero"],
            ubicacion=user["ubicacion"],
        )


def create_notification(conn, redis_client, user_id, notification_type, **kwargs):
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO notificaciones (
                id_usuario, tipo, id_like, id_coincidencia, id_mensaje, id_evento
            ) VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                user_id,
                notification_type,
                kwargs.get("id_like"),
                kwargs.get("id_coincidencia"),
                kwargs.get("id_mensaje"),
                kwargs.get("id_evento"),
            ),
        )
    conn.commit()
    redis_client.incr(f"user:{user_id}:unread_notifications")


def get_unread_count(redis_client, user_id):
    value = redis_client.get(f"user:{user_id}:unread_notifications")
    return int(value) if value else 0


def mark_notifications_read(conn, redis_client, user_id):
    with conn.cursor() as cur:
        cur.execute("UPDATE notificaciones SET leida = TRUE WHERE id_usuario = %s", (user_id,))
    conn.commit()
    redis_client.set(f"user:{user_id}:unread_notifications", 0)


def register_user(conn, mongo_db, neo4j_driver, name, age, gender, location, bio, pref_min, pref_max):
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            INSERT INTO usuarios (nombre, edad, genero, ubicacion, biografia, pref_edad_min, pref_edad_max)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (name, age, gender, location, bio, pref_min, pref_max),
        )
        user = cur.fetchone()
    conn.commit()

    try:
        sync_user_profile(conn, mongo_db, user["id_usuario"])
    except Exception as error:
        warn("MongoDB/perfil", error)

    try:
        sync_user_to_neo4j(neo4j_driver, user)
    except Exception as error:
        warn("Neo4j/usuario", error)

    return user["id_usuario"]


def create_interest(conn, name):
    normalized_name = name.strip().lower()
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO intereses (nombre)
            VALUES (%s)
            ON CONFLICT (nombre) DO UPDATE SET nombre = EXCLUDED.nombre
            RETURNING id_interes
            """,
            (normalized_name,),
        )
        interest_id = cur.fetchone()[0]
    conn.commit()
    return interest_id


def assign_interest(conn, mongo_db, neo4j_driver, user_id, interest_name):
    if not ensure_user_exists(conn, user_id):
        return None
    interest_id = create_interest(conn, interest_name)
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO usuario_intereses (id_usuario, id_interes)
            VALUES (%s, %s)
            ON CONFLICT DO NOTHING
            """,
            (user_id, interest_id),
        )
    conn.commit()

    try:
        sync_user_profile(conn, mongo_db, user_id)
    except Exception as error:
        warn("MongoDB/perfil", error)

    try:
        user = fetch_user(conn, user_id)
        with neo4j_driver.session() as session:
            session.run(
                """
                MERGE (u:Usuario {id_usuario: $id_usuario})
                SET u.nombre = $nombre
                MERGE (i:Interes {nombre: $interes})
                MERGE (u)-[:TIENE_INTERES]->(i)
                """,
                id_usuario=user_id,
                nombre=user["nombre"],
                interes=interest_name.strip().lower(),
            )
    except Exception as error:
        warn("Neo4j/interes", error)

    return interest_id


def add_photo(conn, mongo_db, user_id, url, is_main=False):
    if not ensure_user_exists(conn, user_id):
        return None
    with conn.cursor() as cur:
        if is_main:
            cur.execute("UPDATE fotos SET es_principal = FALSE WHERE id_usuario = %s", (user_id,))
        cur.execute(
            """
            INSERT INTO fotos (id_usuario, url_archivo, es_principal)
            VALUES (%s, %s, %s)
            RETURNING id_foto
            """,
            (user_id, url, is_main),
        )
        photo_id = cur.fetchone()[0]
    conn.commit()

    try:
        sync_user_profile(conn, mongo_db, user_id)
    except Exception as error:
        warn("MongoDB/perfil", error)

    return photo_id


def create_like(conn, redis_client, neo4j_driver, origin, dest):
    if origin == dest:
        print("No se puede dar like a uno mismo.")
        return None
    if not ensure_user_exists(conn, origin) or not ensure_user_exists(conn, dest):
        return None
    if user_is_blocked(conn, origin, dest):
        print("No se puede dar like: existe un bloqueo entre estos usuarios.")
        return None

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO likes (id_usuario_origen, id_usuario_destino)
                VALUES (%s, %s)
                RETURNING id_like
                """,
                (origin, dest),
            )
            like_id = cur.fetchone()[0]
        conn.commit()
    except psycopg2.IntegrityError:
        conn.rollback()
        print("El like ya existe.")
        return None

    try:
        with neo4j_driver.session() as session:
            session.run(
                """
                MATCH (a:Usuario {id_usuario: $origin})
                MATCH (b:Usuario {id_usuario: $dest})
                MERGE (a)-[r:DIO_LIKE]->(b)
                SET r.fecha = datetime()
                """,
                origin=origin,
                dest=dest,
            )
    except Exception as error:
        warn("Neo4j/like", error)

    create_notification(conn, redis_client, dest, "like", id_like=like_id)
    redis_client.incr(f"user:{origin}:likes_given")

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT 1
            FROM likes
            WHERE id_usuario_origen = %s AND id_usuario_destino = %s
            """,
            (dest, origin),
        )
        reciprocal = cur.fetchone() is not None

    match_id = None
    if reciprocal:
        match_id = create_match(conn, redis_client, neo4j_driver, origin, dest)

    return {"like_id": like_id, "match_id": match_id}


def create_match(conn, redis_client, neo4j_driver, user1, user2):
    if user1 == user2:
        print("No se puede crear un match de un usuario consigo mismo.")
        return None
    if not ensure_user_exists(conn, user1) or not ensure_user_exists(conn, user2):
        return None
    if user_is_blocked(conn, user1, user2):
        print("No se puede crear match: existe un bloqueo entre estos usuarios.")
        return None

    if user1 > user2:
        user1, user2 = user2, user1

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO coincidencias (id_usuario1, id_usuario2)
            VALUES (%s, %s)
            ON CONFLICT (id_usuario1, id_usuario2) DO NOTHING
            RETURNING id_coincidencia
            """,
            (user1, user2),
        )
        row = cur.fetchone()
        if row:
            match_id = row[0]
            created = True
        else:
            cur.execute(
                """
                SELECT id_coincidencia
                FROM coincidencias
                WHERE id_usuario1 = %s AND id_usuario2 = %s
                """,
                (user1, user2),
            )
            match_id = cur.fetchone()[0]
            created = False
    conn.commit()

    try:
        with neo4j_driver.session() as session:
            session.run(
                """
                MATCH (a:Usuario {id_usuario: $user1})
                MATCH (b:Usuario {id_usuario: $user2})
                MERGE (a)-[r:MATCH]->(b)
                SET r.fecha = datetime(), r.id_coincidencia = $match_id
                """,
                user1=user1,
                user2=user2,
                match_id=match_id,
            )
    except Exception as error:
        warn("Neo4j/match", error)

    if created:
        create_notification(conn, redis_client, user1, "match", id_coincidencia=match_id)
        create_notification(conn, redis_client, user2, "match", id_coincidencia=match_id)

    return match_id


def block_user(conn, neo4j_driver, blocker_id, blocked_id):
    if blocker_id == blocked_id:
        print("No se puede bloquear a uno mismo.")
        return None
    if not ensure_user_exists(conn, blocker_id) or not ensure_user_exists(conn, blocked_id):
        return None
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO bloqueos (id_bloqueador, id_bloqueado)
                VALUES (%s, %s)
                ON CONFLICT (id_bloqueador, id_bloqueado) DO NOTHING
                RETURNING id_bloqueo
                """,
                (blocker_id, blocked_id),
            )
            row = cur.fetchone()
        conn.commit()
    except psycopg2.IntegrityError:
        conn.rollback()
        print("No se pudo registrar el bloqueo.")
        return None

    try:
        with neo4j_driver.session() as session:
            session.run(
                """
                MATCH (a:Usuario {id_usuario: $blocker})
                MATCH (b:Usuario {id_usuario: $blocked})
                MERGE (a)-[r:BLOQUEO]->(b)
                SET r.fecha = datetime()
                """,
                blocker=blocker_id,
                blocked=blocked_id,
            )
    except Exception as error:
        warn("Neo4j/bloqueo", error)

    return row[0] if row else None


def send_message(conn, redis_client, cassandra_session, match_id, sender_id, content):
    match = get_match(conn, match_id)
    if not match:
        print("No existe una coincidencia con ese ID.")
        return None
    if sender_id not in (match["id_usuario1"], match["id_usuario2"]):
        print("El usuario emisor no pertenece a esta coincidencia.")
        return None

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO mensajes (id_coincidencia, id_emisor, contenido)
            VALUES (%s, %s, %s)
            RETURNING id_mensaje, fecha_envio
            """,
            (match_id, sender_id, content),
        )
        message_id, sent_at = cur.fetchone()
    conn.commit()

    try:
        cassandra_session.set_keyspace(CASSANDRA_KEYSPACE)
        cassandra_session.execute(
            f"""
            INSERT INTO {CASSANDRA_MESSAGES_TABLE}
            (id_coincidencia, fecha_envio, id_mensaje, id_emisor, contenido)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (match_id, sent_at, message_id, sender_id, content),
        )
    except Exception as error:
        warn("Cassandra/mensaje", error)

    recipient_id = match["id_usuario2"] if match["id_usuario1"] == sender_id else match["id_usuario1"]
    create_notification(conn, redis_client, recipient_id, "mensaje", id_mensaje=message_id)
    redis_client.incr(f"match:{match_id}:unread_messages:{recipient_id}")
    return message_id


def get_match_messages(conn, cassandra_session, match_id):
    try:
        cassandra_session.set_keyspace(CASSANDRA_KEYSPACE)
        result = cassandra_session.execute(
            f"""
            SELECT id_mensaje, id_emisor, contenido, fecha_envio
            FROM {CASSANDRA_MESSAGES_TABLE}
            WHERE id_coincidencia = %s
            ORDER BY fecha_envio ASC
            """,
            (match_id,),
        )
        messages = list(result)
        if messages:
            users_map = {row["id_usuario"]: row["nombre"] for row in list_users(conn)}
            return [
                {
                    "emisor": users_map.get(message.id_emisor, str(message.id_emisor)),
                    "contenido": message.contenido,
                    "fecha_envio": message.fecha_envio,
                    "origen": "Cassandra",
                }
                for message in messages
            ]
    except Exception as error:
        warn("Cassandra/lectura mensajes, usando fallback Postgres", error)

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT m.id_mensaje, u.nombre AS emisor, m.contenido, m.fecha_envio
            FROM mensajes m
            JOIN usuarios u ON u.id_usuario = m.id_emisor
            WHERE m.id_coincidencia = %s
            ORDER BY m.fecha_envio
            """,
            (match_id,),
        )
        return [dict(row, origen="PostgreSQL") for row in cur.fetchall()]


def create_session(conn, mongo_db, redis_client, user_id, device_name):
    user = fetch_user(conn, user_id)
    token = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    status = "success" if user else "failure"
    mongo_db[MONGO_LOGIN_COLLECTION].insert_one(
        {
            "id_usuario": user_id,
            "device_name": device_name,
            "status": status,
            "created_at": now,
        }
    )
    if not user:
        return None

    redis_key = f"session:{user_id}:{token}"
    redis_client.hset(
        redis_key,
        mapping={
            "id_usuario": user_id,
            "nombre": user["nombre"],
            "device_name": device_name,
            "created_at": now.isoformat(),
        },
    )
    redis_client.expire(redis_key, SESSION_TTL_SECONDS)
    return token


def get_session_ttl(redis_client, user_id, token):
    return redis_client.ttl(f"session:{user_id}:{token}")


def logout_session(redis_client, user_id, token):
    return redis_client.delete(f"session:{user_id}:{token}")


def reset_database(conn, mongo_db, redis_client, cassandra_session, neo4j_driver):
    conn.rollback()
    print("Borrando PostgreSQL...")
    tables = [
        "notificaciones",
        "asistencia_eventos",
        "eventos",
        "mensajes",
        "coincidencias",
        "bloqueos",
        "likes",
        "fotos",
        "usuario_intereses",
        "usuarios",
        "intereses",
    ]
    with conn.cursor() as cur:
        cur.execute(f"TRUNCATE TABLE {', '.join(tables)} RESTART IDENTITY CASCADE;")
    conn.commit()
    print("OK PostgreSQL limpiado")

    print("Borrando MongoDB...")
    mongo_db[MONGO_PROFILE_COLLECTION].delete_many({})
    mongo_db[MONGO_LOGIN_COLLECTION].delete_many({})
    print("OK MongoDB limpiado")

    print("Borrando Redis...")
    redis_client.flushdb()
    print("OK Redis limpiado")

    print("Borrando Cassandra...")
    cassandra_session.execute(f"DROP KEYSPACE IF EXISTS {CASSANDRA_KEYSPACE};")
    ensure_cassandra_schema(cassandra_session)
    print("OK Cassandra limpiado")

    print("Borrando Neo4j...")
    with neo4j_driver.session() as session:
        session.run("MATCH (n) DETACH DELETE n")
    ensure_neo4j_schema(neo4j_driver)
    print("OK Neo4j limpiado")


def seed_demo_data(conn, mongo_db, redis_client, cassandra_session, neo4j_driver):
    reset_database(conn, mongo_db, redis_client, cassandra_session, neo4j_driver)

    users = [
        ("Sofia Alvarez", 27, "F", "CABA", "Cafe, recitales chicos y caminatas por Palermo.", 25, 34),
        ("Mateo Ruiz", 29, "M", "CABA", "Programador, cocina casera y futbol de los sabados.", 24, 33),
        ("Valentina Perez", 25, "F", "La Plata", "Fotografia, viajes cortos y cine independiente.", 24, 31),
        ("Lucas Fernandez", 31, "M", "CABA", "Jazz, running y bares tranquilos.", 25, 36),
        ("Camila Torres", 28, "F", "Quilmes", "Diseno UX, plantas, sushi y museos.", 26, 35),
        ("Nicolas Gomez", 32, "M", "San Isidro", "Data engineer, trekking y charlas largas.", 27, 37),
    ]
    user_ids = [
        register_user(conn, mongo_db, neo4j_driver, name, age, gender, location, bio, pref_min, pref_max)
        for name, age, gender, location, bio, pref_min, pref_max in users
    ]

    interest_map = {
        user_ids[0]: ["musica", "cafe", "museos"],
        user_ids[1]: ["tecnologia", "cocina", "cine"],
        user_ids[2]: ["viajes", "fotografia", "cine"],
        user_ids[3]: ["musica", "running", "cine"],
        user_ids[4]: ["cocina", "museos", "plantas"],
        user_ids[5]: ["tecnologia", "viajes", "trekking"],
    }
    for user_id, interests in interest_map.items():
        for interest in interests:
            assign_interest(conn, mongo_db, neo4j_driver, user_id, interest)

    for user_id in user_ids:
        add_photo(conn, mongo_db, user_id, f"https://pics.example.com/{user_id}/principal.jpg", True)
        add_photo(conn, mongo_db, user_id, f"https://pics.example.com/{user_id}/extra.jpg", False)

    create_like(conn, redis_client, neo4j_driver, user_ids[0], user_ids[1])
    create_like(conn, redis_client, neo4j_driver, user_ids[1], user_ids[0])
    create_like(conn, redis_client, neo4j_driver, user_ids[2], user_ids[3])
    create_like(conn, redis_client, neo4j_driver, user_ids[3], user_ids[2])
    create_like(conn, redis_client, neo4j_driver, user_ids[4], user_ids[5])
    create_like(conn, redis_client, neo4j_driver, user_ids[5], user_ids[4])
    block_user(conn, neo4j_driver, user_ids[2], user_ids[5])

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO eventos (nombre_evento, fecha, ubicacion, id_organizador)
            VALUES
                ('After office de tecnologia', NOW() + INTERVAL '4 days', 'Palermo', %s),
                ('Caminata fotografica', NOW() + INTERVAL '7 days', 'La Plata', %s)
            RETURNING id_evento
            """,
            (user_ids[1], user_ids[2]),
        )
        event_ids = [row[0] for row in cur.fetchall()]
        cur.execute(
            """
            INSERT INTO asistencia_eventos (id_usuario, id_evento, estado)
            VALUES
                (%s, %s, 'confirmado'),
                (%s, %s, 'confirmado'),
                (%s, %s, 'interesado')
            """,
            (user_ids[0], event_ids[0], user_ids[1], event_ids[0], user_ids[3], event_ids[1]),
        )
    conn.commit()

    with neo4j_driver.session() as session:
        for event_id, event_name in zip(event_ids, ["After office de tecnologia", "Caminata fotografica"]):
            session.run(
                "MERGE (e:Evento {id_evento: $id_evento}) SET e.nombre = $nombre",
                id_evento=event_id,
                nombre=event_name,
            )
        session.run(
            """
            MATCH (u:Usuario {id_usuario: $u1}), (e:Evento {id_evento: $e1})
            MERGE (u)-[:ASISTE {estado: 'confirmado'}]->(e)
            """,
            u1=user_ids[0],
            e1=event_ids[0],
        )

    send_message(conn, redis_client, cassandra_session, 1, user_ids[0], "Hola Mateo! Vi que tambien te gusta cocinar.")
    send_message(conn, redis_client, cassandra_session, 1, user_ids[1], "Si, sobre todo pastas. Cafe esta semana?")

    create_session(conn, mongo_db, redis_client, user_ids[0], "notebook-demo")
