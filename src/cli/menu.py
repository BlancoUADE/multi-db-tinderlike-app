"""
Menú principal de la aplicación CLI
"""

from psycopg2 import OperationalError
from pymongo.errors import PyMongoError
from redis.exceptions import RedisError
from cassandra import DependencyException
from neo4j.exceptions import ServiceUnavailable

from src.database.connections import (
	connect_postgres,
	connect_mongo,
	connect_redis,
	connect_cassandra,
	connect_neo4j,
)
from src.database.postgres import ensure_postgres_schema
from src.database.cassandra import ensure_cassandra_schema
from src.cli import handlers


def main():
	"""Función principal - inicia la aplicación."""
	try:
		conn = connect_postgres()
	except OperationalError as error:
		print("No se pudo conectar a Postgres.")
		print(error)
		return

	try:
		mongo_client = connect_mongo()
		mongo_client.admin.command("ping")
		mongo_db = mongo_client["tinder_app"]
	except PyMongoError as error:
		print("No se pudo conectar a MongoDB.")
		print(error)
		return

	try:
		redis_client = connect_redis()
		redis_client.ping()
	except RedisError as error:
		print("No se pudo conectar a Redis.")
		print(error)
		return

	try:
		cluster, cassandra_session = connect_cassandra()
	except RuntimeError as error:
		print(error)
		return

	try:
		neo4j_driver = connect_neo4j()
		neo4j_driver.verify_connectivity()
	except ServiceUnavailable as error:
		print("No se pudo conectar a Neo4j.")
		print(error)
		return

	try:
		# Inicializar esquemas
		ensure_postgres_schema(conn)
		ensure_cassandra_schema(cassandra_session)

		while True:
			print("\n=== CLI Tinder Multi-DB ===")
			print("\n--- Registrar ---")
			print("1. Registrar usuario")
			print("2. Crear interés")
			print("3. Asignar interés a usuario")
			print("4. Agregar foto")
			print("\n--- Interactuar ---")
			print("5. Dar like")
			print("6. Enviar mensaje")
			print("7. Bloquear usuario")
			print("8. Crear evento")
			print("9. Registrar asistencia a evento")
			print("\n--- Consultar ---")
			print("10. Listar usuarios")
			print("11. Ver perfil de usuario")
			print("12. Ver likes")
			print("13. Ver coincidencias (matches)")
			print("14. Ver mensajes de un match")
			print("15. Ver eventos")
			print("16. Ver notificaciones")
			print("\n--- Analíticas ---")
			print("17. Analíticas")
			print("18. Agregar feriado")
			print("\n--- Demo ---")
			print("19. Cargar datos demo")
			print("20. Limpiar todas las bases de datos")
			print("21. Salir")

			option = input("Seleccione una opción: ").strip()

			if option == "1":
				handlers.register_user(conn, mongo_db, neo4j_driver)
			elif option == "2":
				handlers.create_interest(conn)
			elif option == "3":
				handlers.assign_interest(conn, mongo_db)
			elif option == "4":
				handlers.add_photo(conn, mongo_db)
			elif option == "5":
				handlers.create_like(conn, redis_client, neo4j_driver)
			elif option == "6":
				handlers.send_message(conn, redis_client, cassandra_session)
			elif option == "7":
				handlers.block_user(conn)
			elif option == "8":
				handlers.create_event(conn, redis_client)
			elif option == "9":
				handlers.attend_event(conn, redis_client)
			elif option == "10":
				handlers.list_current_users(conn)
			elif option == "11":
				handlers.view_user_profile(conn, mongo_db)
			elif option == "12":
				handlers.view_likes(conn)
			elif option == "13":
				handlers.view_matches(conn)
			elif option == "14":
				handlers.view_messages(conn)
			elif option == "15":
				handlers.view_events(conn)
			elif option == "16":
				handlers.view_notifications(conn, redis_client)
			elif option == "17":
				handlers.run_analytics(conn)
			elif option == "18":
				handlers.add_holiday(conn)
			elif option == "19":
				handlers.seed_demo_data(conn, mongo_db, neo4j_driver, redis_client, cassandra_session)
			elif option == "20":
				handlers.reset_all_databases(conn, mongo_db, redis_client, cassandra_session)
			elif option == "21":
				print("Hasta luego.")
				break
			else:
				print("Opción inválida.")
	finally:
		conn.close()
		mongo_client.close()
		redis_client.close()
		cassandra_session.shutdown()
		cluster.shutdown()
		neo4j_driver.close()
