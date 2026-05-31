"""
Notifications - Combined PostgreSQL + Redis operations
"""


def create_notification(conn, redis_client, user_id, tipo, id_like=None, id_coincidencia=None, id_mensaje=None, id_evento=None):
	"""Create notification in PostgreSQL and update counter in Redis"""
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

	# Increment counter in Redis
	from .redis import increment_unread_count
	increment_unread_count(redis_client, user_id)

	return notification_id
