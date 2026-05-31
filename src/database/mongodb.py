"""
MongoDB operations - Denormalized user profiles for fast reads
"""

from psycopg2.extras import RealDictCursor


def sync_user_profile(conn, mongo_db, user_id):
	"""Sync user profile from PostgreSQL to MongoDB"""
	from .postgres import fetch_user

	user = fetch_user(conn, user_id)
	if not user:
		return

	# Get interests
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

		# Get photos
		cur.execute(
			"""
			SELECT url_archivo, es_principal
			FROM fotos
			WHERE id_usuario = %s
			ORDER BY fecha_subida
			""",
			(user_id,),
		)
		fotos = cur.fetchall()

	# Create denormalized profile document
	perfil = {
		"id_usuario": user["id_usuario"],
		"nombre": user["nombre"],
		"edad": user["edad"],
		"genero": user["genero"],
		"ubicacion": user["ubicacion"],
		"biografia": user["biografia"],
		"pref_edad_min": user["pref_edad_min"],
		"pref_edad_max": user["pref_edad_max"],
		"intereses": intereses,
		"fotos": [
			{
				"url": foto["url_archivo"],
				"es_principal": foto["es_principal"],
			}
			for foto in fotos
		],
		"fecha_registro": user["fecha_registro"],
	}

	# Upsert into MongoDB
	mongo_db["perfiles_usuarios"].update_one(
		{"id_usuario": user_id},
		{"$set": perfil},
		upsert=True,
	)
