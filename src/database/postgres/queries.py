"""
PostgreSQL read queries for users, profiles, and messages.
"""

from psycopg2.extras import RealDictCursor


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
			principal_tag = " (principal)" if row["es_principal"] else ""
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
