"""
PostgreSQL consolidated database operations.
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2 import OperationalError

# --- CONNECTION ---

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

def connect_postgres():
    return psycopg2.connect(**POSTGRES_CONFIG)

# --- SCHEMA ---

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
                CHECK (id_usuario_origen != id_usuario_destino)
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
        cur.execute("CREATE INDEX IF NOT EXISTS idx_likes_destino ON likes(id_usuario_destino);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_mensajes_coincidencia ON mensajes(id_coincidencia);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_fotos_usuario ON fotos(id_usuario);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_usuario_intereses_interes ON usuario_intereses(id_interes);")
    conn.commit()

# --- QUERIES ---

def fetch_user(conn, user_id):
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT * FROM usuarios WHERE id_usuario = %s", (user_id,))
        return cur.fetchone()

def list_users(conn):
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT id_usuario, nombre, edad, genero, ubicacion
            FROM usuarios
            ORDER BY id_usuario
            """
        )
        return cur.fetchall()

def ensure_user_exists(conn, user_id):
    if not fetch_user(conn, user_id):
        print("No existe un usuario con ese ID.")
        return False
    return True

def view_user_profile(conn, user_id):
    if not ensure_user_exists(conn, user_id):
        return

    user = fetch_user(conn, user_id)

    print(f"\n=== Perfil de {user['nombre']} ===")
    print(f"ID: {user['id_usuario']}")
    print(f"Edad: {user['edad']}")
    print(f"Género: {user['genero']}")
    print(f"Ubicación: {user['ubicacion']}")
    print(f"Biografía: {user['biografia']}")
    print(f"Preferencias de edad: {user['pref_edad_min']}-{user['pref_edad_max']}")

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

    if intereses:
        print("Intereses:")
        for row in intereses:
            print(f"  - {row['nombre']}")
    else:
        print("Sin intereses registrados.")

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT id_foto, url_archivo, es_principal
            FROM fotos
            WHERE id_usuario = %s
            ORDER BY fecha_subida
            """,
            (user_id,),
        )
        fotos = cur.fetchall()

    if fotos:
        print("Fotos:")
        for row in fotos:
            principal_tag = " (principal)" if row["es_principal"] else ""
            print(f"  - {row['url_archivo']}{principal_tag}")
    else:
        print("Sin fotos registradas.")

def get_match_messages(conn, match_id):
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
        return cur.fetchall()

# --- USERS & DOMAIN ---

def register_user(conn, name, age, gender, location, bio, pref_min, pref_max):
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO usuarios (
                nombre, edad, genero, ubicacion, biografia, pref_edad_min, pref_edad_max
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id_usuario
            """,
            (name, age, gender, location, bio, pref_min, pref_max),
        )
        user_id = cur.fetchone()[0]
    conn.commit()
    return user_id

def create_interest(conn, name):
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO intereses (nombre)
            VALUES (%s)
            ON CONFLICT (nombre) DO UPDATE SET nombre = EXCLUDED.nombre
            RETURNING id_interes
            """,
            (name,),
        )
        interest_id = cur.fetchone()[0]
    conn.commit()
    return interest_id

def assign_interest(conn, user_id, interest_name):
    if not ensure_user_exists(conn, user_id):
        return None

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO intereses (nombre)
            VALUES (%s)
            ON CONFLICT (nombre) DO UPDATE SET nombre = EXCLUDED.nombre
            RETURNING id_interes
            """,
            (interest_name,),
        )
        interest_id = cur.fetchone()[0]
        cur.execute(
            """
            INSERT INTO usuario_intereses (id_usuario, id_interes)
            VALUES (%s, %s)
            ON CONFLICT DO NOTHING
            """,
            (user_id, interest_id),
        )
    conn.commit()
    return interest_id

def add_photo(conn, user_id, url, is_main=False):
    if not ensure_user_exists(conn, user_id):
        return None

    with conn.cursor() as cur:
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
    return photo_id

# --- INTERACTIONS ---

def create_like(conn, origin, dest):
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
        return like_id
    except psycopg2.IntegrityError:
        conn.rollback()
        print("El like ya existe.")
        return None

def create_match(conn, user1, user2):
    if user1 > user2:
        user1, user2 = user2, user1

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO coincidencias (id_usuario1, id_usuario2)
                VALUES (%s, %s)
                RETURNING id_coincidencia
                """,
                (user1, user2),
            )
            match_id = cur.fetchone()[0]
        conn.commit()
        return match_id
    except psycopg2.IntegrityError:
        conn.rollback()
        return None

def send_message(conn, match_id, sender_id, content):
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
    return message_id

# --- MAINTENANCE ---

def reset_database(conn):
    conn.rollback()
    print("Borrando PostgreSQL...")
    tables_to_truncate = [
        "mensajes",
        "coincidencias",
        "likes",
        "fotos",
        "usuario_intereses",
        "usuarios",
        "intereses",
    ]

    with conn.cursor() as cur:
        try:
            tables = ", ".join(tables_to_truncate)
            cur.execute(f"TRUNCATE TABLE {tables} RESTART IDENTITY CASCADE;")
            conn.commit()
            print("✓ PostgreSQL limpiado")
        except psycopg2.Error as e:
            conn.rollback()
            print(f"  ⚠️  No se pudo vaciar PostgreSQL: {e}")
    print("\n✅ Base de datos limpiada.")
