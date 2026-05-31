"""
Cassandra operations - Time-series messages optimized by timestamp
"""


def ensure_cassandra_schema(session):
	"""Create Cassandra keyspace and tables"""
	from config import CASSANDRA_KEYSPACE

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


def save_message_to_cassandra(session, match_id, sent_at, message_id, sender_id, content):
	"""Save message to Cassandra time-series table"""
	from config import CASSANDRA_KEYSPACE

	session.set_keyspace(CASSANDRA_KEYSPACE)
	session.execute(
		"""
		INSERT INTO mensajes_por_coincidencia (
			id_coincidencia, fecha_envio, id_mensaje, id_emisor, contenido
		) VALUES (%s, %s, %s, %s, %s)
		""",
		(match_id, sent_at, message_id, sender_id, content),
	)


def get_messages_by_match(session, match_id):
	"""Get all messages for a match (time-series query)"""
	from config import CASSANDRA_KEYSPACE

	session.set_keyspace(CASSANDRA_KEYSPACE)
	result = session.execute(
		"""
		SELECT id_mensaje, id_emisor, contenido, fecha_envio
		FROM mensajes_por_coincidencia
		WHERE id_coincidencia = %s
		ORDER BY fecha_envio ASC
		""",
		(match_id,),
	)
	return result
