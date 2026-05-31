import os
from datetime import datetime

import psycopg2
from psycopg2 import OperationalError
from psycopg2.extras import RealDictCursor
from pymongo import MongoClient
from pymongo.errors import PyMongoError
import redis
from redis.exceptions import RedisError
from cassandra import DependencyException, DriverException
from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable


def get_int_env(name, default):
	value = os.getenv(name)
	return int(value) if value else default


PG_CONFIG = {
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
	return psycopg2.connect(**PG_CONFIG)


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
	try:
		from cassandra.cluster import Cluster, NoHostAvailable
	except DependencyException as error:
		raise RuntimeError(
			"Cassandra driver no es compatible con Python 3.12+ en Windows. "
			"Usá Python 3.11 para ejecutar la demo."
		) from error

	cluster = Cluster(CASSANDRA_HOSTS, port=CASSANDRA_PORT)
	try:
		session = cluster.connect()
	except NoHostAvailable as error:
		raise RuntimeError(
			"No se pudo conectar a Cassandra. Verificá que el contenedor esté levantado."
		) from error

	return cluster, session


def connect_neo4j():
	return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))


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
				UNIQUE (id_usuario_origen, id_usuario_destino)
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
				CHECK (id_usuario1 < id_usuario2),
				UNIQUE (id_usuario1, id_usuario2)
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
			CREATE TABLE IF NOT EXISTS bloqueos (
				id_bloqueo SERIAL PRIMARY KEY,
				id_bloqueador INTEGER NOT NULL REFERENCES usuarios(id_usuario) ON DELETE CASCADE,
				id_bloqueado INTEGER NOT NULL REFERENCES usuarios(id_usuario) ON DELETE CASCADE,
				fecha_bloqueo TIMESTAMPTZ NOT NULL DEFAULT NOW(),
				UNIQUE (id_bloqueador, id_bloqueado)
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
				estado TEXT NOT NULL,
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
				tipo TEXT NOT NULL,
				id_like INTEGER REFERENCES likes(id_like) ON DELETE SET NULL,
				id_coincidencia INTEGER REFERENCES coincidencias(id_coincidencia) ON DELETE SET NULL,
				id_mensaje INTEGER REFERENCES mensajes(id_mensaje) ON DELETE SET NULL,
				id_evento INTEGER REFERENCES eventos(id_evento) ON DELETE SET NULL,
				leida BOOLEAN NOT NULL DEFAULT FALSE,
				fecha_creacion TIMESTAMPTZ NOT NULL DEFAULT NOW()
			);
			"""
		)
		cur.execute(
			"""
			CREATE TABLE IF NOT EXISTS dias_festivos (
				fecha DATE PRIMARY KEY,
				descripcion TEXT NOT NULL
			);
			"""
		)
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


def ensure_neo4j_schema(driver):
	with driver.session() as session:
		session.run(
			"""
			CREATE CONSTRAINT user_id IF NOT EXISTS
			FOR (u:User) REQUIRE u.id IS UNIQUE
			"""
		)


def ask_text(prompt_text):
	while True:
		value = input(prompt_text).strip()
		if value:
			return value
		print("El valor no puede estar vacío.")


def ask_int(prompt_text, minimum=None):
	while True:
		raw_value = input(prompt_text).strip()
		try:
			value = int(raw_value)
		except ValueError:
			print("Ingrese un número entero válido.")
			continue

		if minimum is not None and value < minimum:
			print(f"El valor debe ser mayor o igual a {minimum}.")
			continue

		return value


def ask_bool(prompt_text):
	while True:
		value = input(f"{prompt_text} (s/n): ").strip().lower()
		if value in ("s", "si", "sí"):
			return True
		if value in ("n", "no"):
			return False
		print("Responda s o n.")


def ask_timestamp(prompt_text):
	while True:
		raw_value = input(prompt_text).strip()
		try:
			return datetime.strptime(raw_value, "%Y-%m-%d %H:%M")
		except ValueError:
			print("Formato inválido. Use YYYY-MM-DD HH:MM.")


def ask_date(prompt_text):
	while True:
		raw_value = input(prompt_text).strip()
		try:
			return datetime.strptime(raw_value, "%Y-%m-%d").date()
		except ValueError:
			print("Formato inválido. Use YYYY-MM-DD.")


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


def sync_user_profile(conn, mongo_db, user_id):
	user = fetch_user(conn, user_id)
	if not user:
		return

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
		intereses = [row["nombre"] for row in cur.fetchall()]
		cur.execute(
			"""
			SELECT url_archivo, es_principal, fecha_subida
			FROM fotos
			WHERE id_usuario = %s
			ORDER BY fecha_subida
			""",
			(user_id,),
		)
		fotos = cur.fetchall()

	perfil = {
		"_id": user["id_usuario"],
		"nombre": user["nombre"],
		"edad": user["edad"],
		"genero": user["genero"],
		"ubicacion": user["ubicacion"],
		"biografia": user["biografia"],
		"preferencias": {
			"edad_min": user["pref_edad_min"],
			"edad_max": user["pref_edad_max"],
		},
		"intereses": intereses,
		"fotos": fotos,
		"fecha_registro": user["fecha_registro"],
	}

	mongo_db.perfiles.replace_one({"_id": user_id}, perfil, upsert=True)


def ensure_user_exists(conn, user_id):
	if not fetch_user(conn, user_id):
		print("No existe un usuario con ese ID.")
		return False
	return True


def ensure_event_exists(conn, event_id):
	with conn.cursor(cursor_factory=RealDictCursor) as cur:
		cur.execute("SELECT * FROM eventos WHERE id_evento = %s", (event_id,))
		evento = cur.fetchone()
	if not evento:
		print("No existe un evento con ese ID.")
	return evento


def is_blocked(conn, user_a, user_b):
	with conn.cursor() as cur:
		cur.execute(
			"""
			SELECT 1
			FROM bloqueos
			WHERE (id_bloqueador = %s AND id_bloqueado = %s)
			   OR (id_bloqueador = %s AND id_bloqueado = %s)
			""",
			(user_a, user_b, user_b, user_a),
		)
		return cur.fetchone() is not None


def create_notification(conn, redis_client, user_id, tipo, id_like=None, id_coincidencia=None, id_mensaje=None, id_evento=None):
	with conn.cursor() as cur:
		cur.execute(
			"""
			INSERT INTO notificaciones (
				id_usuario, tipo, id_like, id_coincidencia, id_mensaje, id_evento
			) VALUES (%s, %s, %s, %s, %s, %s)
			RETURNING id_notificacion
			""",
			(user_id, tipo, id_like, id_coincidencia, id_mensaje, id_evento),
		)
		notification_id = cur.fetchone()[0]

	conn.commit()

	try:
		redis_client.incr(f"user:{user_id}:notificaciones_no_leidas")
	except RedisError as error:
		print("No se pudo actualizar el contador de notificaciones en Redis.")
		print(error)

	return notification_id


def register_user(conn, mongo_db, neo4j_driver):
	print("\nRegistro de usuario")
	nombre = ask_text("Nombre: ")
	edad = ask_int("Edad: ", minimum=1)
	genero = ask_text("Genero: ")
	ubicacion = ask_text("Ubicacion: ")
	biografia = ask_text("Biografia: ")
	pref_edad_min = ask_int("Preferencia de Edad Minima: ", minimum=1)
	pref_edad_max = ask_int("Preferencia de Edad Maxima: ", minimum=pref_edad_min)

	with conn.cursor() as cur:
		cur.execute(
			"""
			INSERT INTO usuarios (
				nombre, edad, genero, ubicacion, biografia, pref_edad_min, pref_edad_max
			) VALUES (%s, %s, %s, %s, %s, %s, %s)
			RETURNING id_usuario
			""",
			(
				nombre,
				edad,
				genero,
				ubicacion,
				biografia,
				pref_edad_min,
				pref_edad_max,
			),
		)
		user_id = cur.fetchone()[0]

	conn.commit()

	try:
		sync_user_profile(conn, mongo_db, user_id)
	except PyMongoError as error:
		print("No se pudo sincronizar el perfil en MongoDB.")
		print(error)

	try:
		with neo4j_driver.session() as session:
			session.run(
				"MERGE (u:User {id: $id}) SET u.nombre = $nombre",
				id=user_id,
				nombre=nombre,
			)
	except ServiceUnavailable as error:
		print("No se pudo registrar el usuario en Neo4j.")
		print(error)

	print(f"Usuario registrado correctamente. ID asignado: {user_id}")


def create_interest(conn):
	print("\nCrear interés")
	nombre = ask_text("Nombre del interés: ")

	with conn.cursor() as cur:
		cur.execute(
			"""
			INSERT INTO intereses (nombre)
			VALUES (%s)
			ON CONFLICT (nombre) DO UPDATE SET nombre = EXCLUDED.nombre
			RETURNING id_interes
			""",
			(nombre,),
		)
		interest_id = cur.fetchone()[0]

	conn.commit()
	print(f"Interés registrado. ID asignado: {interest_id}")


def assign_interest(conn, mongo_db):
	print("\nAsignar interés a usuario")
	user_id = ask_int("ID de usuario: ", minimum=1)
	if not ensure_user_exists(conn, user_id):
		return

	interest_name = ask_text("Nombre del interés: ")

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

	try:
		sync_user_profile(conn, mongo_db, user_id)
	except PyMongoError as error:
		print("No se pudo sincronizar el perfil en MongoDB.")
		print(error)

	print("Interés asignado correctamente.")


def add_photo(conn, mongo_db):
	print("\nAgregar foto")
	user_id = ask_int("ID de usuario: ", minimum=1)
	if not ensure_user_exists(conn, user_id):
		return

	url_archivo = ask_text("URL de la foto: ")
	es_principal = ask_bool("¿Es foto principal?")

	with conn.cursor() as cur:
		if es_principal:
			cur.execute(
				"UPDATE fotos SET es_principal = FALSE WHERE id_usuario = %s",
				(user_id,),
			)
		cur.execute(
			"""
			INSERT INTO fotos (id_usuario, url_archivo, es_principal)
			VALUES (%s, %s, %s)
			RETURNING id_foto
			""",
			(user_id, url_archivo, es_principal),
		)
		photo_id = cur.fetchone()[0]

	conn.commit()

	try:
		sync_user_profile(conn, mongo_db, user_id)
	except PyMongoError as error:
		print("No se pudo sincronizar el perfil en MongoDB.")
		print(error)

	print(f"Foto registrada correctamente. ID asignado: {photo_id}")


def create_like(conn, redis_client, neo4j_driver):
	print("\nDar like")
	origin_id = ask_int("ID usuario origen: ", minimum=1)
	dest_id = ask_int("ID usuario destino: ", minimum=1)

	if origin_id == dest_id:
		print("No puedes darte like a ti mismo.")
		return

	if not ensure_user_exists(conn, origin_id) or not ensure_user_exists(conn, dest_id):
		return

	if is_blocked(conn, origin_id, dest_id):
		print("No se puede dar like porque hay un bloqueo entre usuarios.")
		return

	with conn.cursor() as cur:
		cur.execute(
			"""
			INSERT INTO likes (id_usuario_origen, id_usuario_destino)
			VALUES (%s, %s)
			ON CONFLICT DO NOTHING
			RETURNING id_like
			""",
			(origin_id, dest_id),
		)
		row = cur.fetchone()

	if not row:
		print("Ya existe un like registrado entre esos usuarios.")
		conn.rollback()
		return

	like_id = row[0]
	conn.commit()

	create_notification(conn, redis_client, dest_id, "like", id_like=like_id)

	try:
		with neo4j_driver.session() as session:
			session.run(
				"""
				MERGE (o:User {id: $origin})
				MERGE (d:User {id: $dest})
				MERGE (o)-[:LIKES]->(d)
				""",
				origin=origin_id,
				dest=dest_id,
			)
	except ServiceUnavailable as error:
		print("No se pudo registrar el like en Neo4j.")
		print(error)

	with conn.cursor() as cur:
		cur.execute(
			"""
			SELECT id_like
			FROM likes
			WHERE id_usuario_origen = %s AND id_usuario_destino = %s
			""",
			(dest_id, origin_id),
		)
		reciprocal = cur.fetchone()

	if reciprocal:
		match_id = create_match(conn, redis_client, neo4j_driver, origin_id, dest_id)
		if match_id:
			print(f"¡Coincidencia creada! ID de coincidencia: {match_id}")
			return

	print("Like registrado correctamente.")


def create_match(conn, redis_client, neo4j_driver, user_a, user_b):
	user1, user2 = sorted([user_a, user_b])

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

	if not row:
		conn.rollback()
		return None

	match_id = row[0]
	conn.commit()

	create_notification(conn, redis_client, user1, "match", id_coincidencia=match_id)
	create_notification(conn, redis_client, user2, "match", id_coincidencia=match_id)

	try:
		with neo4j_driver.session() as session:
			session.run(
				"""
				MERGE (u1:User {id: $u1})
				MERGE (u2:User {id: $u2})
				MERGE (u1)-[:MATCHES]-(u2)
				""",
				u1=user1,
				u2=user2,
			)
	except ServiceUnavailable as error:
		print("No se pudo registrar la coincidencia en Neo4j.")
		print(error)

	return match_id


def send_message(conn, redis_client, cassandra_session):
	print("\nEnviar mensaje")
	match_id = ask_int("ID de coincidencia: ", minimum=1)
	sender_id = ask_int("ID usuario emisor: ", minimum=1)

	with conn.cursor(cursor_factory=RealDictCursor) as cur:
		cur.execute(
			"SELECT * FROM coincidencias WHERE id_coincidencia = %s",
			(match_id,),
		)
		match = cur.fetchone()

	if not match:
		print("No existe una coincidencia con ese ID.")
		return

	if sender_id not in (match["id_usuario1"], match["id_usuario2"]):
		print("El usuario no pertenece a la coincidencia.")
		return

	receiver_id = match["id_usuario2"] if sender_id == match["id_usuario1"] else match["id_usuario1"]

	if is_blocked(conn, sender_id, receiver_id):
		print("No se puede enviar mensaje porque hay un bloqueo entre usuarios.")
		return

	contenido = ask_text("Mensaje: ")

	with conn.cursor() as cur:
		cur.execute(
			"""
			INSERT INTO mensajes (id_coincidencia, id_emisor, contenido)
			VALUES (%s, %s, %s)
			RETURNING id_mensaje, fecha_envio
			""",
			(match_id, sender_id, contenido),
		)
		message_id, sent_at = cur.fetchone()

	conn.commit()

	try:
		cassandra_session.execute(
			"""
			INSERT INTO mensajes_por_coincidencia (
				id_coincidencia, fecha_envio, id_mensaje, id_emisor, contenido
			) VALUES (%s, %s, %s, %s, %s)
			""",
			(match_id, sent_at, message_id, sender_id, contenido),
		)
	except DriverException as error:
		print("No se pudo registrar el mensaje en Cassandra.")
		print(error)

	create_notification(conn, redis_client, receiver_id, "mensaje", id_mensaje=message_id)

	print(f"Mensaje enviado. ID asignado: {message_id}")


def block_user(conn):
	print("\nBloquear usuario")
	blocker_id = ask_int("ID usuario que bloquea: ", minimum=1)
	blocked_id = ask_int("ID usuario bloqueado: ", minimum=1)

	if blocker_id == blocked_id:
		print("No puedes bloquearte a ti mismo.")
		return

	if not ensure_user_exists(conn, blocker_id) or not ensure_user_exists(conn, blocked_id):
		return

	with conn.cursor() as cur:
		cur.execute(
			"""
			INSERT INTO bloqueos (id_bloqueador, id_bloqueado)
			VALUES (%s, %s)
			ON CONFLICT DO NOTHING
			RETURNING id_bloqueo
			""",
			(blocker_id, blocked_id),
		)
		row = cur.fetchone()

	if not row:
		conn.rollback()
		print("Ya existe un bloqueo entre esos usuarios.")
		return

	conn.commit()
	print("Bloqueo registrado correctamente.")


def create_event(conn, redis_client):
	print("\nCrear evento")
	name = ask_text("Nombre del evento: ")
	event_datetime = ask_timestamp("Fecha y hora (YYYY-MM-DD HH:MM): ")
	location = ask_text("Ubicación: ")
	organizer_id = ask_int("ID usuario organizador: ", minimum=1)

	if not ensure_user_exists(conn, organizer_id):
		return

	with conn.cursor() as cur:
		cur.execute(
			"""
			INSERT INTO eventos (nombre_evento, fecha, ubicacion, id_organizador)
			VALUES (%s, %s, %s, %s)
			RETURNING id_evento
			""",
			(name, event_datetime, location, organizer_id),
		)
		event_id = cur.fetchone()[0]

	conn.commit()
	create_notification(conn, redis_client, organizer_id, "evento", id_evento=event_id)
	print(f"Evento creado. ID asignado: {event_id}")


def attend_event(conn, redis_client):
	print("\nRegistrar asistencia a evento")
	event_id = ask_int("ID evento: ", minimum=1)
	evento = ensure_event_exists(conn, event_id)
	if not evento:
		return

	user_id = ask_int("ID usuario: ", minimum=1)
	if not ensure_user_exists(conn, user_id):
		return

	estado = ask_text("Estado (ej: registrado, asistio, cancelado): ")

	with conn.cursor() as cur:
		cur.execute(
			"""
			INSERT INTO asistencia_eventos (id_usuario, id_evento, estado)
			VALUES (%s, %s, %s)
			ON CONFLICT (id_usuario, id_evento) DO UPDATE SET estado = EXCLUDED.estado
			RETURNING id_asistencia
			""",
			(user_id, event_id, estado),
		)
		attendance_id = cur.fetchone()[0]

	conn.commit()

	if user_id != evento["id_organizador"]:
		create_notification(conn, redis_client, evento["id_organizador"], "evento", id_evento=event_id)

	print(f"Asistencia registrada. ID asignado: {attendance_id}")


def view_notifications(conn, redis_client):
	print("\nNotificaciones")
	user_id = ask_int("ID usuario: ", minimum=1)
	if not ensure_user_exists(conn, user_id):
		return

	with conn.cursor(cursor_factory=RealDictCursor) as cur:
		cur.execute(
			"""
			SELECT id_notificacion, tipo, leida, fecha_creacion, id_like, id_coincidencia, id_mensaje, id_evento
			FROM notificaciones
			WHERE id_usuario = %s
			ORDER BY fecha_creacion DESC
			""",
			(user_id,),
		)
		rows = cur.fetchall()

	if not rows:
		print("No hay notificaciones.")
		return

	for row in rows:
		estado = "Leída" if row["leida"] else "No leída"
		print(
			f"[{row['id_notificacion']}] {row['tipo']} - {estado} - {row['fecha_creacion']}"
			f" (like: {row['id_like']}, match: {row['id_coincidencia']},"
			f" mensaje: {row['id_mensaje']}, evento: {row['id_evento']})"
		)

	try:
		unread = redis_client.get(f"user:{user_id}:notificaciones_no_leidas") or "0"
		print(f"Contador Redis: {unread} no leídas.")
	except RedisError as error:
		print("No se pudo leer el contador de Redis.")
		print(error)

	if ask_bool("¿Marcar todas como leídas?"):
		with conn.cursor() as cur:
			cur.execute(
				"UPDATE notificaciones SET leida = TRUE WHERE id_usuario = %s",
				(user_id,),
			)
		conn.commit()
		try:
			redis_client.set(f"user:{user_id}:notificaciones_no_leidas", 0)
		except RedisError as error:
			print("No se pudo actualizar el contador de Redis.")
			print(error)


def add_holiday(conn):
	print("\nAgregar feriado")
	fecha = ask_date("Fecha (YYYY-MM-DD): ")
	descripcion = ask_text("Descripción: ")

	with conn.cursor() as cur:
		cur.execute(
			"""
			INSERT INTO dias_festivos (fecha, descripcion)
			VALUES (%s, %s)
			ON CONFLICT (fecha) DO UPDATE SET descripcion = EXCLUDED.descripcion
			""",
			(fecha, descripcion),
		)

	conn.commit()
	print("Feriado registrado.")


def reset_all_databases(conn, mongo_db, redis_client, cassandra_session):
	"""Limpia todas las bases de datos para permitir recargar datos demo."""
	confirm = ask_text(
		"⚠️  Esto borrará TODOS los datos en todas las bases de datos. ¿Estás seguro? (sí/no): "
	)
	if confirm.lower() not in ("sí", "si", "yes"):
		print("Cancelado.")
		return

	# PostgreSQL: TRUNCATE todas las tablas (una por una)
	tables = [
		"asistencia_eventos",
		"eventos",
		"bloqueos",
		"notificaciones",
		"mensajes",
		"coincidencias",
		"likes",
		"fotos",
		"usuario_intereses",
		"usuarios",
		"intereses",
		"dias_festivos",
	]
	pg_success = False
	try:
		for table in tables:
			try:
				with conn.cursor() as cur:
					cur.execute(f"TRUNCATE TABLE {table} CASCADE;")
				conn.commit()
			except Exception as table_error:
				conn.rollback()
				print(f"  ⚠️  No se pudo vaciar {table}: {table_error}")
		pg_success = True
		print("✓ PostgreSQL limpiado")
	except Exception as e:
		print(f"✗ Error general en PostgreSQL: {e}")
		conn.rollback()

	try:
		# MongoDB: Eliminar todas las colecciones
		for collection_name in mongo_db.list_collection_names():
			mongo_db[collection_name].drop()
		print("✓ MongoDB limpiado")
	except Exception as e:
		print(f"✗ Error en MongoDB: {e}")

	try:
		# Redis: Limpiar todos los keys
		redis_client.flushdb()
		print("✓ Redis limpiado")
	except Exception as e:
		print(f"✗ Error en Redis: {e}")

	try:
		# Cassandra: DROP keyspace y recrear
		cassandra_session.execute("DROP KEYSPACE IF EXISTS tinder_app;")
		print("✓ Cassandra limpiado")
	except Exception as e:
		print(f"✗ Error en Cassandra: {e}")

	print("\n✅ Todas las bases de datos han sido limpiadas.")
	print("   Ahora puedes cargar datos demo nuevamente (opción 19).")


def analytics_average_matches(conn):
	with conn.cursor() as cur:
		cur.execute(
			"""
			SELECT AVG(cnt)::numeric(10,2)
			FROM (
				SELECT DATE(fecha_coincidencia) AS dia, COUNT(*) AS cnt
				FROM coincidencias
				GROUP BY DATE(fecha_coincidencia)
			) sub;
			"""
		)
		row = cur.fetchone()
	avg_value = row[0] if row and row[0] is not None else 0
	print(f"Promedio de coincidencias por día: {avg_value}")


def analytics_popular_interests(conn):
	with conn.cursor() as cur:
		cur.execute(
			"""
			SELECT i.nombre, COUNT(*) AS cantidad
			FROM usuario_intereses ui
			JOIN intereses i ON i.id_interes = ui.id_interes
			GROUP BY i.nombre
			ORDER BY cantidad DESC
			LIMIT 10;
			"""
		)
		rows = cur.fetchall()

	if not rows:
		print("No hay intereses registrados.")
		return

	print("Intereses más populares:")
	for nombre, cantidad in rows:
		print(f"- {nombre}: {cantidad}")


def analytics_top_swipes(conn):
	with conn.cursor() as cur:
		cur.execute(
			"""
			SELECT u.id_usuario, u.nombre, COUNT(l.id_like) AS likes_recibidos
			FROM likes l
			JOIN usuarios u ON u.id_usuario = l.id_usuario_destino
			GROUP BY u.id_usuario, u.nombre
			ORDER BY likes_recibidos DESC
			LIMIT 10;
			"""
		)
		rows = cur.fetchall()

	if not rows:
		print("No hay likes registrados.")
		return

	print("Perfiles con más swipes a la derecha:")
	for user_id, nombre, total in rows:
		print(f"- {user_id} {nombre}: {total}")


def analytics_avg_conversation_duration(conn):
	with conn.cursor() as cur:
		cur.execute(
			"""
			SELECT AVG(duracion_horas)::numeric(10,2)
			FROM (
				SELECT id_coincidencia,
					   EXTRACT(EPOCH FROM (MAX(fecha_envio) - MIN(fecha_envio))) / 3600 AS duracion_horas
				FROM mensajes
				GROUP BY id_coincidencia
				HAVING COUNT(*) > 1
			) sub;
			"""
		)
		row = cur.fetchone()
	avg_value = row[0] if row and row[0] is not None else 0
	print(f"Duración promedio de conversaciones (horas): {avg_value}")


def analytics_common_interests_in_matches(conn):
	with conn.cursor() as cur:
		cur.execute(
			"""
			SELECT i.nombre, COUNT(*) AS veces
			FROM coincidencias c
			JOIN usuario_intereses ui1 ON ui1.id_usuario = c.id_usuario1
			JOIN usuario_intereses ui2
			  ON ui2.id_usuario = c.id_usuario2 AND ui2.id_interes = ui1.id_interes
			JOIN intereses i ON i.id_interes = ui1.id_interes
			GROUP BY i.nombre
			ORDER BY veces DESC
			LIMIT 10;
			"""
		)
		rows = cur.fetchall()

	if not rows:
		print("No hay coincidencias con intereses en común.")
		return

	print("Intereses más comunes entre coincidencias:")
	for nombre, total in rows:
		print(f"- {nombre}: {total}")


def analytics_profiles_with_photos_and_common_interests(conn):
	with conn.cursor() as cur:
		cur.execute(
			"""
			WITH fotos_ok AS (
				SELECT id_usuario
				FROM fotos
				GROUP BY id_usuario
				HAVING COUNT(*) > 10
			),
			intereses_comunes AS (
				SELECT ui1.id_usuario AS usuario1,
					   ui2.id_usuario AS usuario2,
					   COUNT(*) AS comunes
				FROM usuario_intereses ui1
				JOIN usuario_intereses ui2
				  ON ui1.id_interes = ui2.id_interes
				 AND ui1.id_usuario < ui2.id_usuario
				GROUP BY ui1.id_usuario, ui2.id_usuario
				HAVING COUNT(*) >= 3
			)
			SELECT ic.usuario1, u1.nombre, ic.usuario2, u2.nombre, ic.comunes
			FROM intereses_comunes ic
			JOIN fotos_ok f1 ON f1.id_usuario = ic.usuario1
			JOIN fotos_ok f2 ON f2.id_usuario = ic.usuario2
			JOIN usuarios u1 ON u1.id_usuario = ic.usuario1
			JOIN usuarios u2 ON u2.id_usuario = ic.usuario2
			ORDER BY ic.comunes DESC;
			"""
		)
		rows = cur.fetchall()

	if not rows:
		print("No hay pares de perfiles que cumplan la condición.")
		return

	print("Pares de perfiles con >10 fotos y >=3 intereses en común:")
	for u1_id, u1_name, u2_id, u2_name, comunes in rows:
		print(f"- {u1_id} {u1_name} / {u2_id} {u2_name}: {comunes} intereses")


def analytics_weekend_or_holiday_matches(conn):
	with conn.cursor() as cur:
		cur.execute(
			"""
			SELECT COUNT(*) AS total
			FROM coincidencias c
			LEFT JOIN dias_festivos df ON DATE(c.fecha_coincidencia) = df.fecha
			WHERE EXTRACT(DOW FROM c.fecha_coincidencia) IN (0, 6)
			   OR df.fecha IS NOT NULL;
			"""
		)
		total = cur.fetchone()[0]

	print(f"Coincidencias en fin de semana o feriados: {total}")


def run_analytics(conn):
	while True:
		print("\n=== Analíticas ===")
		print("1. Promedio de coincidencias por día")
		print("2. Características más populares (intereses)")
		print("3. Perfiles con más swipes a la derecha")
		print("4. Duración promedio de conversaciones")
		print("5. Intereses más comunes entre coincidencias")
		print("6. Perfiles con >10 fotos y >=3 intereses en común")
		print("7. Coincidencias en fin de semana o feriados")
		print("8. Volver")

		option = input("Seleccione una opción: ").strip()

		if option == "1":
			analytics_average_matches(conn)
		elif option == "2":
			analytics_popular_interests(conn)
		elif option == "3":
			analytics_top_swipes(conn)
		elif option == "4":
			analytics_avg_conversation_duration(conn)
		elif option == "5":
			analytics_common_interests_in_matches(conn)
		elif option == "6":
			analytics_profiles_with_photos_and_common_interests(conn)
		elif option == "7":
			analytics_weekend_or_holiday_matches(conn)
		elif option == "8":
			break
		else:
			print("Opción inválida.")


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
				INSERT INTO usuarios (nombre, edad, genero, ubicacion, biografia, pref_edad_min, pref_edad_max)
				VALUES (%s, %s, %s, %s, %s, %s, %s)
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

	for user_id in user_ids:
		try:
			sync_user_profile(conn, mongo_db, user_id)
		except PyMongoError as error:
			print("No se pudo sincronizar un perfil demo en MongoDB.")
			print(error)

	try:
		with neo4j_driver.session() as session:
			for user_id in user_ids:
				session.run("MERGE (u:User {id: $id})", id=user_id)
	except ServiceUnavailable as error:
		print("No se pudo sincronizar usuarios demo en Neo4j.")
		print(error)

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
			create_notification(conn, redis_client, dest, "like", id_like=row[0])
		else:
			conn.rollback()

	create_match(conn, redis_client, neo4j_driver, user_ids[0], user_ids[1])
	match_id = create_match(conn, redis_client, neo4j_driver, user_ids[0], user_ids[2])

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
			cassandra_session.execute(
				"""
				INSERT INTO mensajes_por_coincidencia (
					id_coincidencia, fecha_envio, id_mensaje, id_emisor, contenido
				) VALUES (%s, %s, %s, %s, %s)
				""",
				(match_id, sent_at, message_id, user_ids[0], "Hola!"),
			)
		except DriverException as error:
			print("No se pudo registrar el mensaje demo en Cassandra.")
			print(error)
		create_notification(conn, redis_client, user_ids[2], "mensaje", id_mensaje=message_id)

	with conn.cursor() as cur:
		cur.execute(
			"""
			INSERT INTO eventos (nombre_evento, fecha, ubicacion, id_organizador)
			VALUES (%s, %s, %s, %s)
			RETURNING id_evento
			""",
			("After office", datetime.now(), "Palermo", user_ids[0]),
		)
		event_id = cur.fetchone()[0]
	conn.commit()
	create_notification(conn, redis_client, user_ids[0], "evento", id_evento=event_id)

	print("Datos demo cargados.")


def list_current_users(conn):
	users = list_users(conn)
	if not users:
		print("No hay usuarios registrados.")
		return
	for user in users:
		print(
			f"- {user['id_usuario']}: {user['nombre']} ({user['edad']} años, {user['ubicacion']})"
		)


def view_user_profile(conn, mongo_db):
	print("\nVer perfil de usuario")
	user_id = ask_int("ID de usuario: ", minimum=1)
	user = fetch_user(conn, user_id)
	if not user:
		return

	print(f"\n--- Perfil: {user['nombre']} ---")
	print(f"ID: {user['id_usuario']}")
	print(f"Edad: {user['edad']}")
	print(f"Género: {user['genero']}")
	print(f"Ubicación: {user['ubicacion']}")
	print(f"Biografía: {user['biografia']}")
	print(f"Preferencia de edad: {user['pref_edad_min']} - {user['pref_edad_max']}")
	print(f"Fecha de registro: {user['fecha_registro']}")

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
			principal_tag = " (principal)" if row['es_principal'] else ""
			print(f"  - {row['url_archivo']}{principal_tag}")
	else:
		print("Sin fotos registradas.")


def view_likes(conn):
	print("\nVer likes")
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
	print("\nVer coincidencias (matches)")
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
	print("\nVer mensajes")
	match_id = ask_int("ID de coincidencia: ", minimum=1)

	with conn.cursor(cursor_factory=RealDictCursor) as cur:
		cur.execute(
			"""
			SELECT c.id_usuario1, c.id_usuario2, u1.nombre AS usuario1, u2.nombre AS usuario2
			FROM coincidencias c
			JOIN usuarios u1 ON u1.id_usuario = c.id_usuario1
			JOIN usuarios u2 ON u2.id_usuario = c.id_usuario2
			WHERE c.id_coincidencia = %s
			""",
			(match_id,),
		)
		match_info = cur.fetchone()

	if not match_info:
		print("No existe esa coincidencia.")
		return

	print(f"\nMensajes entre {match_info['usuario1']} y {match_info['usuario2']}:")

	with conn.cursor(cursor_factory=RealDictCursor) as cur:
		cur.execute(
			"""
			SELECT m.id_mensaje, m.id_emisor, u.nombre, m.contenido, m.fecha_envio
			FROM mensajes m
			JOIN usuarios u ON u.id_usuario = m.id_emisor
			WHERE m.id_coincidencia = %s
			ORDER BY m.fecha_envio ASC
			""",
			(match_id,),
		)
		mensajes = cur.fetchall()

	if not mensajes:
		print("No hay mensajes en esta conversación.")
		return

	for row in mensajes:
		print(f"[{row['fecha_envio']}] {row['nombre']}: {row['contenido']}")


def view_events(conn):
	print("\nVer eventos")
	with conn.cursor(cursor_factory=RealDictCursor) as cur:
		cur.execute(
			"""
			SELECT e.id_evento, e.nombre_evento, u.nombre AS organizador, e.fecha, e.ubicacion
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
		print(f"[{row['id_evento']}] {row['nombre_evento']} - {row['organizador']} ({row['fecha']}, {row['ubicacion']})")


def main():
	try:
		conn = connect_postgres()
	except OperationalError as error:
		print("No se pudo conectar a Postgres.")
		print(error)
		return

	try:
		mongo_client = connect_mongo()
		mongo_client.admin.command("ping")
		mongo_db = mongo_client[MONGO_DB]
	except PyMongoError as error:
		print("No se pudo conectar a MongoDB.")
		print(error)
		return

	try:
		redis_client = connect_redis()
		redis_client.ping()
	except RedisError as error:
		print("No se pudo conectar a Redis.")
		print(error)
		return

	try:
		cluster, cassandra_session = connect_cassandra()
	except RuntimeError as error:
		print(error)
		return

	try:
		neo4j_driver = connect_neo4j()
		neo4j_driver.verify_connectivity()
	except ServiceUnavailable as error:
		print("No se pudo conectar a Neo4j.")
		print(error)
		return

	try:
		ensure_postgres_schema(conn)
		ensure_cassandra_schema(cassandra_session)
		ensure_neo4j_schema(neo4j_driver)

		while True:
			print("\n=== CLI Tinder Multi-DB ===")
			print("\n--- Registrar ---")
			print("1. Registrar usuario")
			print("2. Crear interés")
			print("3. Asignar interés a usuario")
			print("4. Agregar foto")
			print("\n--- Interactuar ---")
			print("5. Dar like")
			print("6. Enviar mensaje")
			print("7. Bloquear usuario")
			print("8. Crear evento")
			print("9. Registrar asistencia a evento")
			print("\n--- Consultar ---")
			print("10. Listar usuarios")
			print("11. Ver perfil de usuario")
			print("12. Ver likes")
			print("13. Ver coincidencias (matches)")
			print("14. Ver mensajes de un match")
			print("15. Ver eventos")
			print("16. Ver notificaciones")
			print("\n--- Analíticas ---")
			print("17. Analíticas")
			print("18. Agregar feriado")
			print("\n--- Demo ---")
			print("19. Cargar datos demo")
			print("20. Limpiar todas las bases de datos")
			print("21. Salir")

			option = input("Seleccione una opción: ").strip()

			if option == "1":
				register_user(conn, mongo_db, neo4j_driver)
			elif option == "2":
				create_interest(conn)
			elif option == "3":
				assign_interest(conn, mongo_db)
			elif option == "4":
				add_photo(conn, mongo_db)
			elif option == "5":
				create_like(conn, redis_client, neo4j_driver)
			elif option == "6":
				send_message(conn, redis_client, cassandra_session)
			elif option == "7":
				block_user(conn)
			elif option == "8":
				create_event(conn, redis_client)
			elif option == "9":
				attend_event(conn, redis_client)
			elif option == "10":
				list_current_users(conn)
			elif option == "11":
				view_user_profile(conn, mongo_db)
			elif option == "12":
				view_likes(conn)
			elif option == "13":
				view_matches(conn)
			elif option == "14":
				view_messages(conn)
			elif option == "15":
				view_events(conn)
			elif option == "16":
				view_notifications(conn, redis_client)
			elif option == "17":
				run_analytics(conn)
			elif option == "18":
				add_holiday(conn)
			elif option == "19":
				seed_demo_data(conn, mongo_db, neo4j_driver, redis_client, cassandra_session)
			elif option == "20":
				reset_all_databases(conn, mongo_db, redis_client, cassandra_session)
			elif option == "21":
				print("Hasta luego.")
				break
			else:
				print("Opción inválida.")
	finally:
		conn.close()
		mongo_client.close()
		redis_client.close()
		cassandra_session.shutdown()
		cluster.shutdown()
		neo4j_driver.close()


if __name__ == "__main__":
	main()
