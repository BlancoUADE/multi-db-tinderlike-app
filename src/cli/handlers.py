"""
CLI menu handlers - All 20 menu options
"""

from datetime import datetime
from src.cli.utils import ask_text, ask_int, ask_bool, ask_timestamp, ask_date
from src.database.postgres import (
	register_user as db_register_user,
	create_interest as db_create_interest,
	assign_interest as db_assign_interest,
	add_photo as db_add_photo,
	create_like as db_create_like,
	block_user as db_block_user,
	create_match as db_create_match,
	send_message as db_send_message,
	create_event as db_create_event,
	attend_event as db_attend_event,
	add_holiday as db_add_holiday,
	list_users as db_list_users,
	view_user_profile as db_view_user_profile,
	reset_all_databases as db_reset_all_databases,
	get_match_messages,
)
from src.database.cassandra import ensure_cassandra_schema
from src.analytics.queries import run_all_analytics


def register_user(conn, mongo_db, neo4j_driver):
	"""Option 1: Register user"""
	print("\nRegistro de usuario")
	nombre = ask_text("Nombre: ")
	edad = ask_int("Edad: ", minimum=1)
	genero = ask_text("Genero: ")
	ubicacion = ask_text("Ubicacion: ")
	biografia = ask_text("Biografia: ")
	pref_edad_min = ask_int("Preferencia de Edad Minima: ", minimum=1)
	pref_edad_max = ask_int("Preferencia de Edad Maxima: ", minimum=pref_edad_min)

	user_id = db_register_user(conn, mongo_db, neo4j_driver, nombre, edad, genero, ubicacion, biografia, pref_edad_min, pref_edad_max)
	if user_id:
		print(f"Usuario registrado correctamente. ID asignado: {user_id}")


def create_interest(conn):
	"""Option 2: Create interest"""
	print("\nCrear interés")
	nombre = ask_text("Nombre del interés: ")
	interest_id = db_create_interest(conn, nombre)
	print(f"Interés registrado. ID asignado: {interest_id}")


def assign_interest(conn, mongo_db):
	"""Option 3: Assign interest to user"""
	print("\nAsignar interés a usuario")
	user_id = ask_int("ID de usuario: ", minimum=1)
	interest_name = ask_text("Nombre del interés: ")
	db_assign_interest(conn, mongo_db, user_id, interest_name)
	print("Interés asignado correctamente.")


def add_photo(conn, mongo_db):
	"""Option 4: Add photo"""
	print("\nAgregar foto")
	user_id = ask_int("ID de usuario: ", minimum=1)
	url = ask_text("URL de la foto: ")
	is_main = ask_bool("¿Es foto principal?")
	db_add_photo(conn, mongo_db, user_id, url, is_main)
	print("Foto agregada correctamente.")


def create_like(conn, redis_client, neo4j_driver):
	"""Option 5: Create like"""
	print("\nDar like")
	origin = ask_int("Tu ID de usuario: ", minimum=1)
	dest = ask_int("ID del usuario que te gustó: ", minimum=1)
	like_id = db_create_like(conn, redis_client, neo4j_driver, origin, dest)
	if like_id:
		print(f"Like registrado. ID: {like_id}")


def send_message(conn, redis_client, cassandra_session):
	"""Option 6: Send message"""
	print("\nEnviar mensaje")
	match_id = ask_int("ID de la coincidencia: ", minimum=1)
	sender_id = ask_int("Tu ID de usuario: ", minimum=1)
	content = ask_text("Mensaje: ")
	db_send_message(conn, redis_client, cassandra_session, match_id, sender_id, content)
	print("Mensaje enviado.")


def block_user(conn):
	"""Option 7: Block user"""
	print("\nBloquear usuario")
	blocker = ask_int("Tu ID de usuario: ", minimum=1)
	blocked = ask_int("ID del usuario a bloquear: ", minimum=1)
	db_block_user(conn, blocker, blocked)
	print("Usuario bloqueado.")


def create_event(conn, redis_client):
	"""Option 8: Create event"""
	print("\nCrear evento")
	name = ask_text("Nombre del evento: ")
	date_str = ask_text("Fecha (YYYY-MM-DD HH:MM): ")
	try:
		event_date = datetime.strptime(date_str, "%Y-%m-%d %H:%M")
	except ValueError:
		print("Formato de fecha inválido.")
		return
	location = ask_text("Ubicación: ")
	organizer_id = ask_int("Tu ID de usuario: ", minimum=1)
	db_create_event(conn, redis_client, name, event_date, location, organizer_id)
	print("Evento creado correctamente.")


def attend_event(conn, redis_client):
	"""Option 9: Attend event"""
	print("\nRegistrarse en evento")
	event_id = ask_int("ID del evento: ", minimum=1)
	user_id = ask_int("Tu ID de usuario: ", minimum=1)
	db_attend_event(conn, redis_client, event_id, user_id)
	print("Asistencia registrada.")


def list_current_users(conn):
	"""Option 10: List users"""
	users = db_list_users(conn)
	if not users:
		print("No hay usuarios registrados.")
		return
	print("\nUsuarios registrados:")
	for user in users:
		print(f"- {user['id_usuario']}: {user['nombre']} ({user['edad']} años, {user['ubicacion']})")


def view_user_profile(conn, mongo_db):
	"""Option 11: View user profile"""
	user_id = ask_int("ID del usuario a ver: ", minimum=1)
	db_view_user_profile(conn, mongo_db, user_id)


def view_likes(conn):
	"""Option 12: View likes"""
	print("\nVer likes")
	from psycopg2.extras import RealDictCursor
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
		likes = cur.fetchall()

	if not likes:
		print("No hay likes registrados.")
		return

	print("\nÚltimos 20 likes:")
	for row in likes:
		print(f"[{row['id_like']}] {row['origen']} → {row['destino']} ({row['fecha_like']})")


def view_matches(conn):
	"""Option 13: View matches"""
	print("\nVer coincidencias (matches)")
	from psycopg2.extras import RealDictCursor
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
		matches = cur.fetchall()

	if not matches:
		print("No hay coincidencias registradas.")
		return

	print("\nÚltimas 20 coincidencias:")
	for row in matches:
		print(f"[{row['id_coincidencia']}] {row['usuario1']} ↔ {row['usuario2']} ({row['fecha_coincidencia']})")


def view_messages(conn):
	"""Option 14: View messages"""
	print("\nVer mensajes")
	match_id = ask_int("ID de la coincidencia: ", minimum=1)
	messages = get_match_messages(conn, match_id)

	if not messages:
		print("No hay mensajes en esta conversación.")
		return

	print(f"\nMensajes de la coincidencia {match_id}:")
	for msg in messages:
		print(f"{msg['emisor']}: {msg['contenido']} ({msg['fecha_envio']})")


def view_events(conn):
	"""Option 15: View events"""
	print("\nVer eventos")
	from psycopg2.extras import RealDictCursor
	with conn.cursor(cursor_factory=RealDictCursor) as cur:
		cur.execute(
			"""
			SELECT e.id_evento, e.nombre_evento, e.fecha, e.ubicacion, u.nombre AS organizador
			FROM eventos e
			JOIN usuarios u ON u.id_usuario = e.id_organizador
			ORDER BY e.fecha DESC
			LIMIT 20
			"""
		)
		eventos = cur.fetchall()

	if not eventos:
		print("No hay eventos registrados.")
		return

	print("\nÚltimos 20 eventos:")
	for row in eventos:
		print(f"[{row['id_evento']}] {row['nombre_evento']} ({row['fecha']}) en {row['ubicacion']} - Organizador: {row['organizador']}")


def view_notifications(conn, redis_client):
	"""Option 16: View notifications"""
	user_id = ask_int("Tu ID de usuario: ", minimum=1)
	from src.database.redis import get_unread_count
	from psycopg2.extras import RealDictCursor

	unread_count = get_unread_count(redis_client, user_id)
	print(f"\nNotificaciones no leídas: {unread_count}")

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
		notificaciones = cur.fetchall()

	if not notificaciones:
		print("No hay notificaciones.")
		return

	print("\nÚltimas 20 notificaciones:")
	for row in notificaciones:
		leida_tag = "(leída)" if row['leida'] else "(NO LEÍDA)"
		print(f"[{row['id_notificacion']}] {row['tipo']} {leida_tag} ({row['fecha_creacion']})")


def run_analytics(conn):
	"""Option 17: Run analytics"""
	run_all_analytics(conn)


def add_holiday(conn):
	"""Option 18: Add holiday"""
	print("\nAgregar feriado")
	date_str = ask_text("Fecha del feriado (YYYY-MM-DD): ")
	try:
		holiday_date = datetime.strptime(date_str, "%Y-%m-%d").date()
	except ValueError:
		print("Formato de fecha inválido.")
		return
	description = ask_text("Descripción: ")
	db_add_holiday(conn, holiday_date, description)
	print("Feriado registrado.")


def seed_demo_data(conn, mongo_db, neo4j_driver, redis_client, cassandra_session):
	"""Option 19: Seed demo data"""
	print("\nCargando datos demo...")
	from datetime import datetime as dt

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
		try:
			from src.database.mongodb import sync_user_profile
			sync_user_profile(conn, mongo_db, user_id)
		except Exception as error:
			print("No se pudo sincronizar un perfil demo en MongoDB.")
			print(error)

	# Sync to Neo4j
	try:
		with neo4j_driver.session() as session:
			for user_id in user_ids:
				session.run("MERGE (u:User {id: $id})", id=user_id)
	except Exception as error:
		print("No se pudo sincronizar usuarios demo en Neo4j.")
		print(error)

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
			from src.database.notifications import create_notification
			create_notification(conn, redis_client, dest, "like", id_like=row[0])
		else:
			conn.rollback()

	# Create match
	match_id = db_create_match(conn, redis_client, neo4j_driver, user_ids[0], user_ids[1])
	match_id = db_create_match(conn, redis_client, neo4j_driver, user_ids[0], user_ids[2])

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
			# Recreate keyspace if missing (after database reset)
			from src.database.cassandra import ensure_cassandra_schema, save_message_to_cassandra
			ensure_cassandra_schema(cassandra_session)
			save_message_to_cassandra(cassandra_session, match_id, sent_at, message_id, user_ids[0], "Hola!")
		except Exception as error:
			print("No se pudo registrar el mensaje demo en Cassandra.")
			print(error)
		from src.database.notifications import create_notification
		create_notification(conn, redis_client, user_ids[2], "mensaje", id_mensaje=message_id)

	with conn.cursor() as cur:
		cur.execute(
			"""
			INSERT INTO eventos (nombre_evento, fecha, ubicacion, id_organizador)
			VALUES (%s, %s, %s, %s)
			RETURNING id_evento
			""",
			("After office", dt.now(), "Palermo", user_ids[0]),
		)
		event_id = cur.fetchone()[0]
	conn.commit()
	from src.database.notifications import create_notification
	create_notification(conn, redis_client, user_ids[0], "evento", id_evento=event_id)

	print("Datos demo cargados.")


def reset_all_databases(conn, mongo_db, redis_client, cassandra_session):
	"""Option 20: Reset all databases"""
	db_reset_all_databases(conn, mongo_db, redis_client, cassandra_session)
