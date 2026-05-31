"""
PostgreSQL maintenance operations (reset).
"""

import psycopg2


def reset_all_databases(conn, mongo_db, redis_client, cassandra_session):
	"""Reset all tables (for demo purposes)"""
	conn.rollback()
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
		try:
			tables = ", ".join(tables_to_truncate)
			cur.execute(f"TRUNCATE TABLE {tables} RESTART IDENTITY CASCADE;")
			conn.commit()
			print("✓ PostgreSQL limpiado")
		except psycopg2.Error as e:
			conn.rollback()
			print(f"  ⚠️  No se pudo vaciar PostgreSQL: {e}")

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
