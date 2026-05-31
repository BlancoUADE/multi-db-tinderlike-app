"""
PostgreSQL interaction domain operations (likes, matches, messages, blocks).
"""

import psycopg2
from neo4j.exceptions import ServiceUnavailable


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
		from ..notifications import create_notification
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
		from ..notifications import create_notification
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
		from ..cassandra import save_message_to_cassandra
		save_message_to_cassandra(cassandra_session, match_id, sent_at, message_id, sender_id, content)
	except Exception as error:
		print("No se pudo registrar el mensaje en Cassandra.")
		print(error)

	# Create notification
	try:
		from ..notifications import create_notification
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


