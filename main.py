#!/usr/bin/env python3
"""
CLI Tinder Multi-DB - Entry Point
=================================
Aplicación de citas con arquitectura multi-base de datos consolidada.
"""

import sys
from psycopg2 import OperationalError

import database as db

# --- UTILS ---

def ask_text(prompt):
    while True:
        val = input(prompt).strip()
        if val:
            return val
        print("Este campo no puede estar vacío.")

def ask_int(prompt, minimum=None):
    while True:
        try:
            val = int(input(prompt).strip())
            if minimum is not None and val < minimum:
                print(f"El valor debe ser al menos {minimum}.")
                continue
            return val
        except ValueError:
            print("Por favor, ingresá un número válido.")

def ask_bool(prompt):
    while True:
        val = input(f"{prompt} (s/n): ").strip().lower()
        if val in ["s", "si", "y", "yes"]:
            return True
        if val in ["n", "no"]:
            return False
        print("Respondé 's' o 'n'.")

# --- HANDLERS ---

def register_user(conn, mongo_db, neo4j_driver):
    print("\nRegistro de usuario")
    nombre = ask_text("Nombre: ")
    edad = ask_int("Edad: ", minimum=1)
    genero = ask_text("Género: ")
    ubicacion = ask_text("Ubicación: ")
    biografia = ask_text("Biografía: ")
    pref_edad_min = ask_int("Preferencia de Edad Mínima: ", minimum=1)
    pref_edad_max = ask_int("Preferencia de Edad Máxima: ", minimum=pref_edad_min)

    user_id = db.register_user(conn, mongo_db, neo4j_driver, nombre, edad, genero, ubicacion, biografia, pref_edad_min, pref_edad_max)
    if user_id:
        print(f"Usuario registrado correctamente. ID asignado: {user_id}")

def create_interest(conn):
    print("\nCrear interés")
    nombre = ask_text("Nombre del interés: ")
    interest_id = db.create_interest(conn, nombre)
    print(f"Interés registrado. ID asignado: {interest_id}")

def assign_interest(conn, mongo_db):
    print("\nAsignar interés a usuario")
    user_id = ask_int("ID de usuario: ", minimum=1)
    interest_name = ask_text("Nombre del interés: ")
    db.assign_interest(conn, mongo_db, user_id, interest_name)
    print("Interés asignado correctamente.")

def add_photo(conn, mongo_db):
    print("\nAgregar foto")
    user_id = ask_int("ID de usuario: ", minimum=1)
    url = ask_text("URL de la foto: ")
    is_main = ask_bool("¿Es foto principal?")
    db.add_photo(conn, mongo_db, user_id, url, is_main)
    print("Foto agregada correctamente.")

def create_like(conn, redis_client, neo4j_driver):
    print("\nDar like")
    origin = ask_int("Tu ID de usuario: ", minimum=1)
    dest = ask_int("ID del usuario que te gustó: ", minimum=1)
    like_id = db.create_like(conn, redis_client, neo4j_driver, origin, dest)
    if like_id:
        print(f"Like registrado. ID: {like_id}")

def create_match_manual(conn, redis_client, neo4j_driver):
    print("\nForzar Match (Coincidencia)")
    u1 = ask_int("ID Usuario 1: ", minimum=1)
    u2 = ask_int("ID Usuario 2: ", minimum=1)
    match_id = db.create_match(conn, redis_client, neo4j_driver, u1, u2)
    if match_id:
        print(f"Coincidencia registrada. ID: {match_id}")

def send_message(conn, redis_client, cassandra_session):
    print("\nEnviar mensaje")
    match_id = ask_int("ID de la coincidencia: ", minimum=1)
    sender_id = ask_int("Tu ID de usuario: ", minimum=1)
    content = ask_text("Mensaje: ")
    db.send_message(conn, redis_client, cassandra_session, match_id, sender_id, content)
    print("Mensaje enviado.")

def list_current_users(conn):
    users = db.list_users(conn)
    if not users:
        print("No hay usuarios registrados.")
        return
    print("\nUsuarios registrados:")
    for user in users:
        print(f"- {user['id_usuario']}: {user['nombre']} ({user['edad']} años, {user['ubicacion']})")

def view_user_profile(conn):
    user_id = ask_int("ID del usuario a ver: ", minimum=1)
    db.view_user_profile(conn, user_id)

def view_likes(conn):
    print("\nVer likes")
    with conn.cursor(cursor_factory=db.RealDictCursor) as cur:
        cur.execute(
            """
            SELECT l.id_like, u_o.nombre AS origen, u_d.nombre AS destino, l.fecha_like
            FROM likes l
            JOIN usuarios u_o ON u_o.id_usuario = l.id_usuario_origen
            JOIN usuarios u_d ON u_d.id_usuario = l.id_usuario_destino
            ORDER BY l.fecha_like DESC
            LIMIT 20
            """
        )
        likes = cur.fetchall()

    if not likes:
        print("No hay likes registrados.")
        return

    print("\nÚltimos 20 likes:")
    for row in likes:
        print(f"[{row['id_like']}] {row['origen']} → {row['destino']} ({row['fecha_like']})")

def view_matches(conn):
    print("\nVer coincidencias (matches)")
    with conn.cursor(cursor_factory=db.RealDictCursor) as cur:
        cur.execute(
            """
            SELECT c.id_coincidencia, u1.nombre AS usuario1, u2.nombre AS usuario2, c.fecha_coincidencia
            FROM coincidencias c
            JOIN usuarios u1 ON u1.id_usuario = c.id_usuario1
            JOIN usuarios u2 ON u2.id_usuario = c.id_usuario2
            ORDER BY c.fecha_coincidencia DESC
            LIMIT 20
            """
        )
        matches = cur.fetchall()

    if not matches:
        print("No hay coincidencias registradas.")
        return

    print("\nÚltimas 20 coincidencias:")
    for row in matches:
        print(f"[{row['id_coincidencia']}] {row['usuario1']} ↔ {row['usuario2']} ({row['fecha_coincidencia']})")

def view_messages(conn, cassandra_session):
    print("\nVer mensajes")
    match_id = ask_int("ID de la coincidencia: ", minimum=1)
    messages = db.get_match_messages(conn, cassandra_session, match_id)

    if not messages:
        print("No hay mensajes en esta conversación.")
        return

    print(f"\nMensajes de la coincidencia {match_id}:")
    for msg in messages:
        print(f"{msg['emisor']}: {msg['contenido']} ({msg['fecha_envio']})")

def view_notifications(conn, redis_client):
    print("\nVer notificaciones")
    user_id = ask_int("Tu ID de usuario: ", minimum=1)
    
    unread_count = db.get_unread_count(redis_client, user_id)
    print(f"\nNotificaciones no leídas: {unread_count}")

    with conn.cursor(cursor_factory=db.RealDictCursor) as cur:
        cur.execute(
            """
            SELECT id_notificacion, tipo, fecha_creacion, leida
            FROM notificaciones
            WHERE id_usuario = %s
            ORDER BY fecha_creacion DESC
            LIMIT 20
            """,
            (user_id,),
        )
        notificaciones = cur.fetchall()

    if not notificaciones:
        print("No hay notificaciones.")
        return

    print("\nÚltimas 20 notificaciones:")
    for row in notificaciones:
        leida_tag = "(leída)" if row['leida'] else "(NO LEÍDA)"
        print(f"[{row['id_notificacion']}] {row['tipo']} {leida_tag} ({row['fecha_creacion']})")
        
    # Reset count
    redis_key = f"user:{user_id}:unread_notifications"
    redis_client.set(redis_key, 0)


def seed_demo_data(conn, mongo_db, neo4j_driver, redis_client, cassandra_session):
    print("\nCargando datos demo...")

    users = [
        ("Sofia", 25, "F", "Buenos Aires", "Amante del cine", 22, 30),
        ("Lucas", 28, "M", "Córdoba", "Viajes y música", 20, 30),
        ("Valentina", 27, "F", "Rosario", "Lectura y café", 24, 32),
        ("Mateo", 30, "M", "Mendoza", "Deportes extremos", 25, 35),
        ("Camila", 24, "F", "La Plata", "Arte y tecnología", 22, 29),
    ]
    intereses = ["cine", "viajes", "musica", "lectura", "deportes", "tecnologia", "arte"]

    user_ids = []
    with conn.cursor() as cur:
        for nombre, edad, genero, ubicacion, biografia, pref_min, pref_max in users:
            cur.execute(
                """
                INSERT INTO usuarios (
                    nombre, edad, genero, ubicacion, biografia, pref_edad_min, pref_edad_max
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id_usuario
                """,
                (nombre, edad, genero, ubicacion, biografia, pref_min, pref_max),
            )
            user_ids.append(cur.fetchone()[0])

        interest_ids = {}
        for interes in intereses:
            cur.execute(
                """
                INSERT INTO intereses (nombre)
                VALUES (%s)
                ON CONFLICT (nombre) DO UPDATE SET nombre = EXCLUDED.nombre
                RETURNING id_interes
                """,
                (interes,),
            )
            interest_ids[interes] = cur.fetchone()[0]

        assignments = {
            user_ids[0]: ["cine", "viajes", "arte"],
            user_ids[1]: ["viajes", "musica", "deportes"],
            user_ids[2]: ["lectura", "cine", "arte"],
            user_ids[3]: ["deportes", "viajes", "musica"],
            user_ids[4]: ["arte", "tecnologia", "cine"],
        }

        for user_id, user_intereses in assignments.items():
            for interes in user_intereses:
                cur.execute(
                    """
                    INSERT INTO usuario_intereses (id_usuario, id_interes)
                    VALUES (%s, %s)
                    ON CONFLICT DO NOTHING
                    """,
                    (user_id, interest_ids[interes]),
                )

        for idx, user_id in enumerate(user_ids):
            photo_count = 12 if idx == 0 else 3
            for photo_index in range(photo_count):
                cur.execute(
                    """
                    INSERT INTO fotos (id_usuario, url_archivo, es_principal)
                    VALUES (%s, %s, %s)
                    """,
                    (
                        user_id,
                        f"https://pics.example.com/{user_id}/{photo_index}.jpg",
                        photo_index == 0,
                    ),
                )

    conn.commit()

    # Sync to MongoDB
    for user_id in user_ids:
        try: db.sync_user_profile(conn, mongo_db, user_id)
        except: pass

    # Sync to Neo4j
    try:
        with neo4j_driver.session() as session:
            for user_id in user_ids:
                session.run("MERGE (u:User {id: $id})", id=user_id)
    except: pass

    # Create demo likes
    likes = [
        (user_ids[0], user_ids[1]),
        (user_ids[1], user_ids[0]),
        (user_ids[2], user_ids[0]),
        (user_ids[0], user_ids[2]),
        (user_ids[3], user_ids[4]),
    ]
    for origin, dest in likes:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO likes (id_usuario_origen, id_usuario_destino)
                VALUES (%s, %s)
                ON CONFLICT DO NOTHING
                RETURNING id_like
                """,
                (origin, dest),
            )
            row = cur.fetchone()
        if row:
            conn.commit()
            db.create_notification(conn, redis_client, dest, "like", id_like=row[0])
        else:
            conn.rollback()

    # Create match
    match_id = db.create_match(conn, redis_client, neo4j_driver, user_ids[0], user_ids[1])
    db.create_match(conn, redis_client, neo4j_driver, user_ids[0], user_ids[2])

    if match_id:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO mensajes (id_coincidencia, id_emisor, contenido)
                VALUES (%s, %s, %s)
                RETURNING id_mensaje, fecha_envio
                """,
                (match_id, user_ids[0], "Hola!"),
            )
            message_id, sent_at = cur.fetchone()
        conn.commit()
        try:
            db.ensure_cassandra_schema(cassandra_session)
            cassandra_session.set_keyspace(db.CASSANDRA_KEYSPACE)
            cassandra_session.execute(
                "INSERT INTO mensajes_por_coincidencia (id_coincidencia, fecha_envio, id_mensaje, id_emisor, contenido) VALUES (%s, %s, %s, %s, %s)",
                (match_id, sent_at, message_id, user_ids[0], "Hola!"),
            )
        except: pass
        
        db.create_notification(conn, redis_client, user_ids[1], "mensaje", id_mensaje=message_id)

    print("Datos demo cargados.")


def reset_all_databases(conn, mongo_db, redis_client, cassandra_session):
    db.reset_database(conn, mongo_db, redis_client, cassandra_session)

# --- MENU & ENTRY POINT ---

def check_environment():
    """Verifica que Python 3.11+ está disponible."""
    if sys.version_info < (3, 11):
        print("Advertencia: Este proyecto requiere Python 3.11+")
        print(f"Tu version: {sys.version}")
        sys.exit(1)

def main():
    try: conn = db.connect_postgres()
    except OperationalError as error:
        print("No se pudo conectar a Postgres."); return

    try:
        mongo_client = db.connect_mongo()
        mongo_db = mongo_client["tinder_app"]
    except Exception as error:
        print("No se pudo conectar a MongoDB."); return

    try: redis_client = db.connect_redis()
    except Exception as error:
        print("No se pudo conectar a Redis."); return

    try: cluster, cassandra_session = db.connect_cassandra()
    except Exception as error:
        print("No se pudo conectar a Cassandra."); return

    try: neo4j_driver = db.connect_neo4j()
    except Exception as error:
        print("No se pudo conectar a Neo4j."); return

    try:
        db.ensure_postgres_schema(conn)
        try: db.ensure_cassandra_schema(cassandra_session)
        except: pass

        while True:
            print("\n=== CLI Tinder Multi-DB (Consolidated) ===")
            print("\n--- Registrar ---")
            print("1. Registrar usuario")
            print("2. Crear interés")
            print("3. Asignar interés a usuario")
            print("4. Agregar foto")
            print("\n--- Interactuar ---")
            print("5. Dar like")
            print("6. Forzar Match")
            print("7. Enviar mensaje")
            print("\n--- Consultar ---")
            print("8. Listar usuarios")
            print("9. Ver perfil de usuario")
            print("10. Ver likes")
            print("11. Ver coincidencias (matches)")
            print("12. Ver mensajes de un match")
            print("13. Ver notificaciones")
            print("\n--- Demo ---")
            print("14. Cargar datos demo")
            print("15. Limpiar base de datos")
            print("16. Salir")

            option = input("Seleccione una opción: ").strip()

            if option == "1": register_user(conn, mongo_db, neo4j_driver)
            elif option == "2": create_interest(conn)
            elif option == "3": assign_interest(conn, mongo_db)
            elif option == "4": add_photo(conn, mongo_db)
            elif option == "5": create_like(conn, redis_client, neo4j_driver)
            elif option == "6": create_match_manual(conn, redis_client, neo4j_driver)
            elif option == "7": send_message(conn, redis_client, cassandra_session)
            elif option == "8": list_current_users(conn)
            elif option == "9": view_user_profile(conn)
            elif option == "10": view_likes(conn)
            elif option == "11": view_matches(conn)
            elif option == "12": view_messages(conn, cassandra_session)
            elif option == "13": view_notifications(conn, redis_client)
            elif option == "14": seed_demo_data(conn, mongo_db, neo4j_driver, redis_client, cassandra_session)
            elif option == "15": reset_all_databases(conn, mongo_db, redis_client, cassandra_session)
            elif option == "16":
                print("Hasta luego."); break
            else:
                print("Opción inválida.")
    except KeyboardInterrupt:
        print("\n\nHasta luego.")
        sys.exit(0)
    except Exception as e:
        print(f"Error fatal: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        conn.close()
        mongo_client.close()
        redis_client.close()
        cluster.shutdown()
        neo4j_driver.close()

if __name__ == "__main__":
    check_environment()
    main()
