"""
Analytics queries - 7 business intelligence queries
"""

from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta


def query_users_by_age_range(conn, min_age, max_age):
	"""Analytics 1: Users grouped by age range"""
	with conn.cursor(cursor_factory=RealDictCursor) as cur:
		cur.execute(
			"""
			SELECT 
				EXTRACT(YEAR FROM AGE(fecha_registro)) as age_at_registration,
				COUNT(*) as total_users,
				AVG(edad) as avg_age,
				MAX(edad) as max_age,
				MIN(edad) as min_age
			FROM usuarios
			WHERE edad BETWEEN %s AND %s
			GROUP BY age_at_registration
			ORDER BY age_at_registration
			""",
			(min_age, max_age),
		)
		return cur.fetchall()


def query_most_popular_interests(conn):
	"""Analytics 2: Most popular interests"""
	with conn.cursor(cursor_factory=RealDictCursor) as cur:
		cur.execute(
			"""
			SELECT 
				i.nombre,
				COUNT(ui.id_usuario) as usuarios_con_interes,
				ROUND(100.0 * COUNT(ui.id_usuario) / (SELECT COUNT(*) FROM usuarios), 2) as porcentaje
			FROM intereses i
			LEFT JOIN usuario_intereses ui ON i.id_interes = ui.id_interes
			GROUP BY i.id_interes, i.nombre
			ORDER BY usuarios_con_interes DESC
			"""
		)
		return cur.fetchall()


def query_users_with_most_likes(conn):
	"""Analytics 3: Users with most likes received"""
	with conn.cursor(cursor_factory=RealDictCursor) as cur:
		cur.execute(
			"""
			SELECT 
				u.id_usuario,
				u.nombre,
				COUNT(l.id_like) as likes_recibidos,
				u.edad,
				u.ubicacion
			FROM usuarios u
			LEFT JOIN likes l ON u.id_usuario = l.id_usuario_destino
			GROUP BY u.id_usuario, u.nombre, u.edad, u.ubicacion
			ORDER BY likes_recibidos DESC
			LIMIT 10
			"""
		)
		return cur.fetchall()


def query_avg_messages_per_user(conn):
	"""Analytics 4: Average messages per user in matches"""
	with conn.cursor(cursor_factory=RealDictCursor) as cur:
		cur.execute(
			"""
			SELECT 
				COALESCE(u.id_usuario, 0) as id_usuario,
				COALESCE(u.nombre, 'N/A') as nombre,
				COUNT(m.id_mensaje) as total_mensajes,
				AVG(CHAR_LENGTH(m.contenido)) as largo_promedio_mensaje
			FROM usuarios u
			LEFT JOIN mensajes m ON u.id_usuario = m.id_emisor
			GROUP BY u.id_usuario, u.nombre
			ORDER BY total_mensajes DESC
			"""
		)
		return cur.fetchall()


def query_common_interests(conn):
	"""Analytics 5: Common interests between matched users"""
	with conn.cursor(cursor_factory=RealDictCursor) as cur:
		cur.execute(
			"""
			SELECT 
				c.id_coincidencia,
				u1.nombre as usuario1,
				u2.nombre as usuario2,
				string_agg(i.nombre, ', ') as intereses_comunes,
				COUNT(i.id_interes) as cantidad_intereses_comunes
			FROM coincidencias c
			JOIN usuarios u1 ON c.id_usuario1 = u1.id_usuario
			JOIN usuarios u2 ON c.id_usuario2 = u2.id_usuario
			JOIN usuario_intereses ui1 ON u1.id_usuario = ui1.id_usuario
			JOIN usuario_intereses ui2 ON u2.id_usuario = ui2.id_usuario
			JOIN intereses i ON ui1.id_interes = i.id_interes AND ui2.id_interes = i.id_interes
			GROUP BY c.id_coincidencia, u1.nombre, u2.nombre
			ORDER BY cantidad_intereses_comunes DESC
			"""
		)
		return cur.fetchall()


def query_power_profiles(conn):
	"""Analytics 6: Power profiles (10+ photos AND 3+ interests)"""
	with conn.cursor(cursor_factory=RealDictCursor) as cur:
		cur.execute(
			"""
			SELECT 
				u.id_usuario,
				u.nombre,
				COUNT(DISTINCT f.id_foto) as total_fotos,
				COUNT(DISTINCT ui.id_interes) as total_intereses,
				u.edad,
				u.ubicacion
			FROM usuarios u
			LEFT JOIN fotos f ON u.id_usuario = f.id_usuario
			LEFT JOIN usuario_intereses ui ON u.id_usuario = ui.id_usuario
			GROUP BY u.id_usuario, u.nombre, u.edad, u.ubicacion
			HAVING COUNT(DISTINCT f.id_foto) >= 10 AND COUNT(DISTINCT ui.id_interes) >= 3
			ORDER BY total_fotos DESC
			"""
		)
		return cur.fetchall()


def query_weekend_matches(conn):
	"""Analytics 7: Matches on weekends and holidays"""
	with conn.cursor(cursor_factory=RealDictCursor) as cur:
		cur.execute(
			"""
			SELECT 
				c.id_coincidencia,
				u1.nombre as usuario1,
				u2.nombre as usuario2,
				DATE(c.fecha_coincidencia) as fecha,
				TO_CHAR(c.fecha_coincidencia, 'Day') as dia_semana,
				CASE 
					WHEN EXTRACT(DOW FROM c.fecha_coincidencia) IN (0, 6) THEN 'Fin de semana'
					WHEN df.fecha IS NOT NULL THEN 'Feriado'
					ELSE 'Día laboral'
				END as tipo_dia
			FROM coincidencias c
			JOIN usuarios u1 ON c.id_usuario1 = u1.id_usuario
			JOIN usuarios u2 ON c.id_usuario2 = u2.id_usuario
			LEFT JOIN dias_festivos df ON DATE(c.fecha_coincidencia) = df.fecha
			WHERE EXTRACT(DOW FROM c.fecha_coincidencia) IN (0, 6) 
				OR df.fecha IS NOT NULL
			ORDER BY c.fecha_coincidencia DESC
			"""
		)
		return cur.fetchall()


def run_all_analytics(conn):
	"""Run all 7 analytics and display results"""
	print("\n=== ANALÍTICAS ===")

	# 1. Users by age
	print("\n1. Usuarios por rango de edad (18-40 años):")
	results = query_users_by_age_range(conn, 18, 40)
	if results:
		for row in results:
			print(f"   Edad promedio al registrarse: {row['age_at_registration']}, Total usuarios: {row['total_users']}, Edad promedio: {row['avg_age']}")
	else:
		print("   Sin datos")

	# 2. Most popular interests
	print("\n2. Intereses más populares:")
	results = query_most_popular_interests(conn)
	if results:
		for row in results:
			print(f"   {row['nombre']}: {row['usuarios_con_interes']} usuarios ({row['porcentaje']}%)")
	else:
		print("   Sin datos")

	# 3. Users with most likes
	print("\n3. Usuarios con más likes recibidos:")
	results = query_users_with_most_likes(conn)
	if results:
		for row in results:
			print(f"   {row['nombre']} ({row['edad']} años, {row['ubicacion']}): {row['likes_recibidos']} likes")
	else:
		print("   Sin datos")

	# 4. Average messages
	print("\n4. Promedio de mensajes por usuario:")
	results = query_avg_messages_per_user(conn)
	if results:
		for row in results:
			if row['nombre'] != 'N/A':
				print(f"   {row['nombre']}: {row['total_mensajes']} mensajes, promedio {row['largo_promedio_mensaje']:.0f} caracteres")
	else:
		print("   Sin datos")

	# 5. Common interests in matches
	print("\n5. Intereses comunes en coincidencias:")
	results = query_common_interests(conn)
	if results:
		for row in results:
			print(f"   {row['usuario1']} ↔ {row['usuario2']}: {row['intereses_comunes']} ({row['cantidad_intereses_comunes']} comunes)")
	else:
		print("   Sin datos")

	# 6. Power profiles
	print("\n6. Perfiles con 10+ fotos Y 3+ intereses:")
	results = query_power_profiles(conn)
	if results:
		for row in results:
			print(f"   {row['nombre']}: {row['total_fotos']} fotos, {row['total_intereses']} intereses")
	else:
		print("   Sin datos")

	# 7. Weekend/Holiday matches
	print("\n7. Coincidencias en fines de semana y feriados:")
	results = query_weekend_matches(conn)
	if results:
		for row in results:
			print(f"   {row['usuario1']} ↔ {row['usuario2']} ({row['dia_semana']}, {row['tipo_dia']})")
	else:
		print("   Sin datos")
