"""
PostgreSQL event domain operations.
"""

import psycopg2
from psycopg2.extras import RealDictCursor

from .queries import ensure_user_exists


def ensure_event_exists(conn, event_id):
	"""Verify event exists"""
	with conn.cursor(cursor_factory=RealDictCursor) as cur:
		cur.execute("SELECT * FROM eventos WHERE id_evento = %s", (event_id,))
		evento = cur.fetchone()
	if not evento:
		print("No existe un evento con ese ID.")
	return evento


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
	from ..notifications import create_notification
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
		from ..notifications import create_notification
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
