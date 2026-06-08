#!/usr/bin/env python3
"""
CLI Tinder Multi-DB.

Menu principal compacto, menu de usuario con sesion activa y menu de sistema
para configuracion/demo. El usuario no necesita saber que motor resuelve cada
operacion.
"""

import sys

import psycopg2
from psycopg2.extras import RealDictCursor

import database as db


def ask_text(prompt):
    while True:
        value = input(prompt).strip()
        if value:
            return value
        print("Este campo no puede estar vacio.")


def ask_int(prompt, minimum=None):
    while True:
        try:
            value = int(input(prompt).strip())
        except ValueError:
            print("Ingrese un numero entero valido.")
            continue
        if minimum is not None and value < minimum:
            print(f"El valor debe ser al menos {minimum}.")
            continue
        return value


def ask_bool(prompt):
    while True:
        value = input(f"{prompt} (s/n): ").strip().lower()
        if value in {"s", "si", "y", "yes"}:
            return True
        if value in {"n", "no"}:
            return False
        print("Responda 's' o 'n'.")


def register_user(conn, mongo_db, neo4j_driver, redis_client):
    print("\nRegistro de usuario")
    name = ask_text("Nombre: ")
    age = ask_int("Edad: ", minimum=1)
    gender = ask_text("Genero: ")
    location = ask_text("Ubicacion: ")
    bio = ask_text("Biografia: ")
    pref_min = ask_int("Preferencia de edad minima: ", minimum=1)
    pref_max = ask_int("Preferencia de edad maxima: ", minimum=pref_min)
    user_id = db.register_user(conn, mongo_db, neo4j_driver, name, age, gender, location, bio, pref_min, pref_max)
    token = db.create_session(conn, mongo_db, redis_client, user_id, "registro-cli")
    print(f"Usuario registrado correctamente. ID asignado: {user_id}")
    print(f"Sesion iniciada. Token: {token}")
    return {"user_id": user_id, "token": token}


def login_user(conn, mongo_db, redis_client):
    print("\nIniciar sesion")
    user_id = ask_int("ID de usuario: ", minimum=1)
    device_name = ask_text("Dispositivo: ")
    token = db.create_session(conn, mongo_db, redis_client, user_id, device_name)
    if not token:
        print("Login fallido. Quedo auditado en MongoDB.")
        return None
    ttl = db.get_session_ttl(redis_client, user_id, token)
    print("Login exitoso. Quedo auditado en MongoDB y activo en Redis.")
    print(f"Token: {token}")
    print(f"TTL: {ttl} segundos")
    return {"user_id": user_id, "token": token}


def logout_user(redis_client, session_state):
    deleted = db.logout_session(redis_client, session_state["user_id"], session_state["token"])
    print("Sesion cerrada." if deleted else "La sesion ya no estaba activa.")


def list_current_users(conn):
    users = db.list_users(conn)
    if not users:
        print("No hay usuarios registrados.")
        return
    print("\nUsuarios registrados:")
    for user in users:
        print(f"- {user['id_usuario']}: {user['nombre']} ({user['edad']} anios, {user['ubicacion']})")


def view_my_profile(conn, session_state):
    db.view_user_profile(conn, session_state["user_id"])


def add_my_photo(conn, mongo_db, session_state):
    print("\nAgregar foto")
    url = ask_text("URL de la foto: ")
    is_main = ask_bool("Es foto principal?")
    photo_id = db.add_photo(conn, mongo_db, session_state["user_id"], url, is_main)
    if photo_id:
        print(f"Foto agregada y perfil MongoDB actualizado. ID: {photo_id}")


def assign_my_interest(conn, mongo_db, neo4j_driver, session_state):
    print("\nAsignar interes a mi perfil")
    interest_name = ask_text("Nombre del interes: ")
    interest_id = db.assign_interest(conn, mongo_db, neo4j_driver, session_state["user_id"], interest_name)
    if interest_id:
        print("Interes asignado y sincronizado con MongoDB/Neo4j.")


def create_like(conn, redis_client, neo4j_driver, session_state):
    print("\nDar like")
    dest = ask_int("ID del usuario destino: ", minimum=1)
    result = db.create_like(conn, redis_client, neo4j_driver, session_state["user_id"], dest)
    if not result:
        return
    print(f"Like registrado. ID: {result['like_id']}")
    if result["match_id"]:
        print(f"Like reciproco detectado. Match creado/confirmado. ID: {result['match_id']}")


def block_user(conn, neo4j_driver, session_state):
    print("\nBloquear usuario")
    blocked_id = ask_int("ID del usuario a bloquear: ", minimum=1)
    block_id = db.block_user(conn, neo4j_driver, session_state["user_id"], blocked_id)
    if block_id:
        print(f"Bloqueo registrado. ID: {block_id}")
    else:
        print("El bloqueo ya existia o no pudo registrarse.")


def send_message(conn, redis_client, cassandra_session, session_state):
    print("\nEnviar mensaje")
    match_id = ask_int("ID de coincidencia: ", minimum=1)
    content = ask_text("Mensaje: ")
    message_id = db.send_message(conn, redis_client, cassandra_session, match_id, session_state["user_id"], content)
    if message_id:
        print(f"Mensaje guardado en PostgreSQL y Cassandra. ID: {message_id}")


def view_likes(conn):
    print("\nUltimos likes")
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
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
        rows = cur.fetchall()
    if not rows:
        print("No hay likes registrados.")
        return
    for row in rows:
        print(f"[{row['id_like']}] {row['origen']} -> {row['destino']} ({row['fecha_like']})")


def view_matches(conn):
    print("\nUltimas coincidencias")
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
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
        rows = cur.fetchall()
    if not rows:
        print("No hay coincidencias registradas.")
        return
    for row in rows:
        print(f"[{row['id_coincidencia']}] {row['usuario1']} <-> {row['usuario2']} ({row['fecha_coincidencia']})")


def view_messages(conn, cassandra_session):
    print("\nMensajes de una coincidencia")
    match_id = ask_int("ID de coincidencia: ", minimum=1)
    messages = db.get_match_messages(conn, cassandra_session, match_id)
    if not messages:
        print("No hay mensajes en esta conversacion.")
        return
    for message in messages:
        print(f"{message['emisor']}: {message['contenido']} ({message['fecha_envio']}, {message['origen']})")


def view_notifications(conn, redis_client, session_state):
    print("\nNotificaciones")
    user_id = session_state["user_id"]
    unread_count = db.get_unread_count(redis_client, user_id)
    print(f"Contador Redis de no leidas: {unread_count}")
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
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
        rows = cur.fetchall()
    if not rows:
        print("No hay notificaciones.")
        return
    for row in rows:
        status = "leida" if row["leida"] else "NO LEIDA"
        print(f"[{row['id_notificacion']}] {row['tipo']} ({status}) {row['fecha_creacion']}")
    if ask_bool("Marcar todas como leidas?"):
        db.mark_notifications_read(conn, redis_client, user_id)
        print("Notificaciones marcadas como leidas y contador Redis reiniciado.")


def recommend_profiles(conn, mongo_db, neo4j_driver, session_state):
    print("\nRecomendar perfiles")
    limit = ask_int("Cantidad maxima de recomendaciones: ", minimum=1)
    recommendations = db.recommend_profiles(conn, mongo_db, neo4j_driver, session_state["user_id"], limit)
    if not recommendations:
        print("No hay recomendaciones disponibles para ese usuario.")
        return

    print("\nRecomendaciones generadas con Neo4j y perfiles leidos desde MongoDB:")
    for item in recommendations:
        profile = item["perfil"]
        main_photo = next((photo for photo in profile.get("fotos", []) if photo.get("es_principal")), None)
        shared = ", ".join(item["intereses_compartidos"])
        print("\n---")
        print(f"ID: {profile['id_usuario']}")
        print(f"Nombre: {profile['nombre']} ({profile['edad']} anios, {profile['ubicacion']})")
        print(f"Bio: {profile['biografia']}")
        print(f"Intereses compartidos ({item['intereses_en_comun']}): {shared}")
        if main_photo:
            print(f"Foto principal: {main_photo['url_archivo']}")


def view_session_ttl(redis_client, session_state):
    ttl = db.get_session_ttl(redis_client, session_state["user_id"], session_state["token"])
    if ttl == -2:
        print("La sesion no existe o ya expiro.")
    elif ttl == -1:
        print("La sesion existe sin TTL.")
    else:
        print(f"TTL restante: {ttl} segundos")


def create_interest(conn):
    print("\nCrear interes global")
    name = ask_text("Nombre del interes: ")
    interest_id = db.create_interest(conn, name)
    print(f"Interes registrado. ID asignado: {interest_id}")


def create_match_manual(conn, redis_client, neo4j_driver):
    print("\nForzar match")
    user1 = ask_int("ID usuario 1: ", minimum=1)
    user2 = ask_int("ID usuario 2: ", minimum=1)
    match_id = db.create_match(conn, redis_client, neo4j_driver, user1, user2)
    if match_id:
        print(f"Coincidencia registrada/sincronizada. ID: {match_id}")


def seed_demo_data(conn, mongo_db, redis_client, cassandra_session, neo4j_driver):
    print("\nCargando datos demo. Esto limpia las bases antes de cargar.")
    db.seed_demo_data(conn, mongo_db, redis_client, cassandra_session, neo4j_driver)
    print("Datos demo cargados en PostgreSQL, MongoDB, Redis, Cassandra y Neo4j.")


def reset_all_databases(conn, mongo_db, redis_client, cassandra_session, neo4j_driver):
    db.reset_database(conn, mongo_db, redis_client, cassandra_session, neo4j_driver)
    print("Todas las bases quedaron limpias.")


def show_user_menu(resources, session_state):
    conn = resources["conn"]
    mongo_db = resources["mongo_db"]
    redis_client = resources["redis_client"]
    cassandra_session = resources["cassandra_session"]
    neo4j_driver = resources["neo4j_driver"]
    user = db.fetch_user(conn, session_state["user_id"])
    title_name = user["nombre"] if user else f"Usuario {session_state['user_id']}"

    while True:
        print(f"\n=== Menu Usuario: {title_name} ===")
        print("1. Ver mi perfil")
        print("2. Agregar foto")
        print("3. Agregar interes a mi perfil")
        print("4. Dar like")
        print("5. Recomendar perfiles")
        print("6. Enviar mensaje")
        print("7. Ver mensajes de un match")
        print("8. Ver notificaciones")
        print("9. Ver likes")
        print("10. Ver matches")
        print("11. Bloquear usuario")
        print("12. Ver TTL de mi sesion")
        print("13. Cerrar sesion")
        print("14. Volver al menu principal")

        option = input("Seleccione una opcion: ").strip()

        if option == "1":
            view_my_profile(conn, session_state)
        elif option == "2":
            add_my_photo(conn, mongo_db, session_state)
        elif option == "3":
            assign_my_interest(conn, mongo_db, neo4j_driver, session_state)
        elif option == "4":
            create_like(conn, redis_client, neo4j_driver, session_state)
        elif option == "5":
            recommend_profiles(conn, mongo_db, neo4j_driver, session_state)
        elif option == "6":
            send_message(conn, redis_client, cassandra_session, session_state)
        elif option == "7":
            view_messages(conn, cassandra_session)
        elif option == "8":
            view_notifications(conn, redis_client, session_state)
        elif option == "9":
            view_likes(conn)
        elif option == "10":
            view_matches(conn)
        elif option == "11":
            block_user(conn, neo4j_driver, session_state)
        elif option == "12":
            view_session_ttl(redis_client, session_state)
        elif option == "13":
            logout_user(redis_client, session_state)
            return None
        elif option == "14":
            return session_state
        else:
            print("Opcion invalida.")


def show_system_menu(resources):
    conn = resources["conn"]
    mongo_db = resources["mongo_db"]
    redis_client = resources["redis_client"]
    cassandra_session = resources["cassandra_session"]
    neo4j_driver = resources["neo4j_driver"]

    while True:
        print("\n=== Sistema ===")
        print("1. Crear interes global")
        print("2. Forzar match")
        print("3. Cargar datos demo")
        print("4. Limpiar todas las bases")
        print("5. Volver")

        option = input("Seleccione una opcion: ").strip()

        if option == "1":
            create_interest(conn)
        elif option == "2":
            create_match_manual(conn, redis_client, neo4j_driver)
        elif option == "3":
            seed_demo_data(conn, mongo_db, redis_client, cassandra_session, neo4j_driver)
        elif option == "4":
            if ask_bool("Seguro que queres limpiar todas las bases?"):
                reset_all_databases(conn, mongo_db, redis_client, cassandra_session, neo4j_driver)
        elif option == "5":
            return
        else:
            print("Opcion invalida.")


def check_environment():
    if sys.version_info < (3, 11):
        print("Este proyecto requiere Python 3.11+.")
        print(f"Version actual: {sys.version}")
        sys.exit(1)


def connect_all():
    resources = {}
    try:
        resources["conn"] = db.connect_postgres()
        print("PostgreSQL OK")
        resources["mongo_client"] = db.connect_mongo()
        resources["mongo_db"] = resources["mongo_client"][db.MONGO_DB]
        print("MongoDB OK")
        resources["redis_client"] = db.connect_redis()
        print("Redis OK")
        resources["cluster"], resources["cassandra_session"] = db.connect_cassandra()
        print("Cassandra OK")
        resources["neo4j_driver"] = db.connect_neo4j()
        print("Neo4j OK")
        return resources
    except Exception:
        close_all(resources)
        raise


def close_all(resources):
    if resources.get("conn"):
        resources["conn"].close()
    if resources.get("mongo_client"):
        resources["mongo_client"].close()
    if resources.get("redis_client"):
        resources["redis_client"].close()
    if resources.get("cluster"):
        resources["cluster"].shutdown()
    if resources.get("neo4j_driver"):
        resources["neo4j_driver"].close()


def main():
    try:
        resources = connect_all()
    except Exception as error:
        print(f"No se pudo inicializar el entorno multi-DB: {error}")
        return

    conn = resources["conn"]
    mongo_db = resources["mongo_db"]
    redis_client = resources["redis_client"]
    cassandra_session = resources["cassandra_session"]
    neo4j_driver = resources["neo4j_driver"]
    session_state = None

    try:
        db.ensure_postgres_schema(conn)
        db.ensure_cassandra_schema(cassandra_session)
        db.ensure_neo4j_schema(neo4j_driver)

        while True:
            print("\n=== CLI Tinder Multi-DB ===")
            print("1. Registrar usuario")
            print("2. Iniciar sesion")
            print("3. Listar usuarios")
            print("4. Sistema")
            print("5. Salir")

            option = input("Seleccione una opcion: ").strip()

            if option == "1":
                session_state = register_user(conn, mongo_db, neo4j_driver, redis_client)
                if session_state:
                    session_state = show_user_menu(resources, session_state)
            elif option == "2":
                session_state = login_user(conn, mongo_db, redis_client)
                if session_state:
                    session_state = show_user_menu(resources, session_state)
            elif option == "3":
                list_current_users(conn)
            elif option == "4":
                show_system_menu(resources)
            elif option == "5":
                if session_state and ask_bool("Hay una sesion activa. Cerrar antes de salir?"):
                    logout_user(redis_client, session_state)
                print("Hasta luego.")
                break
            else:
                print("Opcion invalida.")
    except KeyboardInterrupt:
        print("\nHasta luego.")
    except (psycopg2.Error, Exception) as error:
        print(f"Error fatal: {error}")
        raise
    finally:
        close_all(resources)


if __name__ == "__main__":
    check_environment()
    main()
