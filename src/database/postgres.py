"""
PostgreSQL database operations - Source of truth for all data
"""

from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor
from pymongo.errors import PyMongoError
from neo4j.exceptions import ServiceUnavailable


def ensure_postgres_schema(conn):
	"""Create all PostgreSQL tables with proper constraints"""
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
		cur.execute(
			"""
			CREATE TABLE IF NOT EXISTS bloqueos (
				id_bloqueo SERIAL PRIMARY KEY,
				id_bloqueador INTEGER NOT NULL REFERENCES usuarios(id_usuario) ON DELETE CASCADE,
				id_bloqueado INTEGER NOT NULL REFERENCES usuarios(id_usuario) ON DELETE CASCADE,
				fecha_bloqueo TIMESTAMPTZ NOT NULL DEFAULT NOW(),
				UNIQUE (id_bloqueador, id_bloqueado),
				CHECK (id_bloqueador != id_bloqueado)
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
				id_organizador INTEGER NOT NULL REFERENCES usuarios(id_usuario) ON DELETE CASCADE,
				fecha_creacion TIMESTAMPTZ NOT NULL DEFAULT NOW()
			);
			"""
		)
		cur.execute(
			"""
			CREATE TABLE IF NOT EXISTS asistencia_eventos (
				id_asistencia SERIAL PRIMARY KEY,
				id_evento INTEGER NOT NULL REFERENCES eventos(id_evento) ON DELETE CASCADE,
				id_usuario INTEGER NOT NULL REFERENCES usuarios(id_usuario) ON DELETE CASCADE,
				fecha_asistencia TIMESTAMPTZ NOT NULL DEFAULT NOW(),
				UNIQUE (id_evento, id_usuario)
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


def fetch_user(conn, user_id):
	"""Fetch a single user by ID"""
	with conn.cursor(cursor_factory=RealDictCursor) as cur:
		cur.execute("SELECT * FROM usuarios WHERE id_usuario = %s", (user_id,))
		return cur.fetchone()


def list_users(conn):
	"""List all users"""
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
	"""Verify user exists"""
	if not fetch_user(conn, user_id):
		print("No existe un usuario con ese ID.")
		return False
	return True


def ensure_event_exists(conn, event_id):
	"""Verify event exists"""
	with conn.cursor(cursor_factory=RealDictCursor) as cur:
		cur.execute("SELECT * FROM eventos WHERE id_evento = %s", (event_id,))
		evento = cur.fetchone()
	if not evento:
		print("No existe un evento con ese ID.")
	return evento


def is_blocked(conn, user_a, user_b):
	"""Check if users are blocked"""
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


def register_user(conn, mongo_db, neo4j_driver, name, age, gender, location, bio, pref_min, pref_max):
	"""Register a new user in PostgreSQL and sync to other DBs"""
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

	# Sync to MongoDB
	try:
		from .mongodb import sync_user_profile
		sync_user_profile(conn, mongo_db, user_id)
	except PyMongoError as error:
		print("No se pudo sincronizar el perfil en MongoDB.")
		print(error)

	# Sync to Neo4j
	try:
		with neo4j_driver.session() as session:
			session.run(
				"MERGE (u:User {id: $id}) SET u.nombre = $nombre",
				id=user_id,
				nombre=name,
			)
	except ServiceUnavailable as error:
		print("No se pudo registrar el usuario en Neo4j.")
		print(error)

	return user_id


def create_interest(conn, name):
	"""Create a new interest"""
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


def assign_interest(conn, mongo_db, user_id, interest_name):
	"""Assign an interest to a user"""
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

	# Sync to MongoDB
	try:
		from .mongodb import sync_user_profile
		sync_user_profile(conn, mongo_db, user_id)
	except PyMongoError as error:
		print("No se pudo sincronizar el perfil en MongoDB.")
		print(error)

	return interest_id


def add_photo(conn, mongo_db, user_id, url, is_main=False):
	"""Add a photo to a user"""
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

	# Sync to MongoDB
	try:
		from .mongodb import sync_user_profile
		sync_user_profile(conn, mongo_db, user_id)
	except PyMongoError as error:
		print("No se pudo sincronizar el perfil en MongoDB.")
		print(error)

	return photo_id


def create_like(conn, redis_client, neo4j_driver, origin, dest):
	"""Create a like (swipe right)"""
	if is_blocked(conn, origin, dest):
		print("No se puede interactuar con este usuario.")
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

		# Sync to Neo4j
		try:
			with neo4j_driver.session() as session:
				session.run(
					"MATCH (a:User {id: $id_a}), (b:User {id: $id_b}) MERGE (a)-[:LIKES]->(b)",
					id_a=origin,
					id_b=dest,
				)
		except ServiceUnavailable as error:
			print("No se pudo registrar el like en Neo4j.")
			print(error)

		# Create notification
		from .notifications import create_notification
		create_notification(conn, redis_client, dest, "like", id_like=like_id)

		return like_id
	except psycopg2.IntegrityError:
		conn.rollback()
		print("El like ya existe.")
		return None


def block_user(conn, blocker, blocked):
	"""Block a user"""
	if blocker == blocked:
		print("No te podes bloquear a vos mismo.")
		return None

	try:
		with conn.cursor() as cur:
			cur.execute(
				"""
				INSERT INTO bloqueos (id_bloqueador, id_bloqueado)
				VALUES (%s, %s)
				RETURNING id_bloqueo
				""",
				(blocker, blocked),
			)
			block_id = cur.fetchone()[0]

		conn.commit()
		return block_id
	except psycopg2.IntegrityError:
		conn.rollback()
		print("Este usuario ya estaba bloqueado.")
		return None


def create_match(conn, redis_client, neo4j_driver, user1, user2):
	"""Create a match (mutual like)"""
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

		# Sync to Neo4j
		try:
			with neo4j_driver.session() as session:
				session.run(
					"MATCH (a:User {id: $id_a}), (b:User {id: $id_b}) MERGE (a)-[:MATCHES]->(b)",
					id_a=user1,
					id_b=user2,
				)
		except ServiceUnavailable as error:
			print("No se pudo registrar el match en Neo4j.")
			print(error)

		# Create notifications
		from .notifications import create_notification
		create_notification(conn, redis_client, user1, "coincidencia", id_coincidencia=match_id)
		create_notification(conn, redis_client, user2, "coincidencia", id_coincidencia=match_id)

		return match_id
	except psycopg2.IntegrityError:
		conn.rollback()
		return None


def send_message(conn, redis_client, cassandra_session, match_id, sender_id, content):
	"""Send a message in a match"""
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

	# Sync to Cassandra
	try:
		from .cassandra import save_message_to_cassandra
		save_message_to_cassandra(cassandra_session, match_id, sent_at, message_id, sender_id, content)
	except Exception as error:
		print("No se pudo registrar el mensaje en Cassandra.")
		print(error)

	# Create notification
	try:
		from .notifications import create_notification
		# Get recipient ID
		with conn.cursor() as cur:
			cur.execute(
				"""
				SELECT id_usuario1, id_usuario2 FROM coincidencias WHERE id_coincidencia = %s
				""",
				(match_id,),
			)
			u1, u2 = cur.fetchone()
			recipient_id = u2 if u1 == sender_id else u1

		create_notification(conn, redis_client, recipient_id, "mensaje", id_mensaje=message_id)
	except Exception as error:
		print("Error al crear notificación de mensaje.")
		print(error)

	return message_id


def create_event(conn, redis_client, name, event_date, location, organizer_id):
	"""Create an event"""
	if not ensure_user_exists(conn, organizer_id):
		return None

	with conn.cursor() as cur:
		cur.execute(
			"""
			INSERT INTO eventos (nombre_evento, fecha, ubicacion, id_organizador)
			VALUES (%s, %s, %s, %s)
			RETURNING id_evento
			""",
			(name, event_date, location, organizer_id),
		)
		event_id = cur.fetchone()[0]

	conn.commit()

	# Create notification
	from .notifications import create_notification
	create_notification(conn, redis_client, organizer_id, "evento", id_evento=event_id)

	return event_id


def attend_event(conn, redis_client, event_id, user_id):
	"""Register attendance at an event"""
	if not ensure_user_exists(conn, user_id):
		return None
	if not ensure_event_exists(conn, event_id):
		return None

	try:
		with conn.cursor() as cur:
			cur.execute(
				"""
				INSERT INTO asistencia_eventos (id_evento, id_usuario)
				VALUES (%s, %s)
				RETURNING id_asistencia
				""",
				(event_id, user_id),
			)
			attendance_id = cur.fetchone()[0]

		conn.commit()

		# Create notification
		from .notifications import create_notification
		create_notification(conn, redis_client, user_id, "evento", id_evento=event_id)

		return attendance_id
	except psycopg2.IntegrityError:
		conn.rollback()
		print("El usuario ya está registrado en este evento.")
		return None


def add_holiday(conn, holiday_date, description):
	"""Add a holiday to the calendar"""
	try:
		with conn.cursor() as cur:
			cur.execute(
				"""
				INSERT INTO dias_festivos (fecha, descripcion)
				VALUES (%s, %s)
				""",
				(holiday_date, description),
			)

		conn.commit()
		return True
	except psycopg2.IntegrityError:
		conn.rollback()
		print("Esta fecha ya está registrada como feriado.")
		return False


def reset_all_databases(conn, mongo_db, redis_client, cassandra_session):
	"""Reset all tables (for demo purposes)"""
	print("Borrando PostgreSQL...")
	tables_to_truncate = [
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

	with conn.cursor() as cur:
		for table in tables_to_truncate:
			try:
				cur.execute(f"TRUNCATE TABLE {table} CASCADE;")
				conn.commit()
			except psycopg2.Error as e:
				conn.rollback()
				print(f"  ⚠️  No se pudo vaciar {table}: {e}")

	# Clear MongoDB
	print("Borrando MongoDB...")
	try:
		mongo_db["perfiles_usuarios"].delete_many({})
		print("✓ MongoDB limpiado")
	except Exception as error:
		print(f"  ⚠️  No se pudo limpiar MongoDB: {error}")

	# Clear Redis
	print("Borrando Redis...")
	try:
		redis_client.flushdb()
		print("✓ Redis limpiado")
	except Exception as error:
		print(f"  ⚠️  No se pudo limpiar Redis: {error}")

	# Clear Cassandra
	print("Borrando Cassandra...")
	try:
		cassandra_session.execute("DROP KEYSPACE IF EXISTS tinder_app;")
		print("✓ Cassandra limpiado")
	except Exception as error:
		print(f"  ⚠️  No se pudo limpiar Cassandra: {error}")

	print("\n✅ Todas las bases de datos han sido limpiadas.")
	print("   Ahora puedes cargar datos demo nuevamente (opción 19).")


def view_user_profile(conn, mongo_db, user_id):
	"""View user profile with interests and photos"""
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
			principal_tag = " (principal)" if row['es_principal'] else ""
			print(f"  - {row['url_archivo']}{principal_tag}")
	else:
		print("Sin fotos registradas.")


def get_match_messages(conn, match_id):
	"""Get all messages in a match"""
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
