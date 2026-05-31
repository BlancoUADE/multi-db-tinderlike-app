"""
PostgreSQL user domain operations.
"""

from pymongo.errors import PyMongoError
from neo4j.exceptions import ServiceUnavailable

from .queries import ensure_user_exists


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
		from ..mongodb import sync_user_profile
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
		from ..mongodb import sync_user_profile
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
		from ..mongodb import sync_user_profile
		sync_user_profile(conn, mongo_db, user_id)
	except PyMongoError as error:
		print("No se pudo sincronizar el perfil en MongoDB.")
		print(error)

	return photo_id
