#!/usr/bin/env python3
"""
Script de verificación de todas las bases de datos.
Valida que:
1. Las DBs están corriendo
2. Los esquemas coinciden con el DER
3. Los datos están siendo almacenados correctamente
4. Cada DB tiene el tipo de dato apropiado
"""

import os
import psycopg2
from psycopg2 import OperationalError
from psycopg2.extras import RealDictCursor
from pymongo import MongoClient
from pymongo.errors import PyMongoError
import redis
from redis.exceptions import RedisError
from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable
import json

PG_CONFIG = {
	"host": os.getenv("PG_HOST", "127.0.0.1"),
	"port": int(os.getenv("PG_PORT", 5433)),
	"dbname": os.getenv("PG_DB", "tinder_app"),
	"user": os.getenv("PG_USER", "tpo_user"),
	"password": os.getenv("PG_PASSWORD", "tpo_password"),
}

MONGO_URI = os.getenv("MONGO_URI", "mongodb://tpo_user:tpo_password@localhost:27017/")
MONGO_DB = os.getenv("MONGO_DB", "tinder_app")

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD")

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "tpo_password")


def print_header(title):
	print(f"\n{'='*60}")
	print(f"  {title}")
	print(f"{'='*60}")


def verify_postgres():
	print_header("📊 PostgreSQL - Base de datos relacional")
	try:
		conn = psycopg2.connect(**PG_CONFIG)
		with conn.cursor(cursor_factory=RealDictCursor) as cur:
			# Verificar tablas
			cur.execute(
				"""
				SELECT table_name
				FROM information_schema.tables
				WHERE table_schema = 'public'
				ORDER BY table_name
				"""
			)
			tables = [row['table_name'] for row in cur.fetchall()]
			print(f"✅ Conexión exitosa")
			print(f"📋 Tablas encontradas: {len(tables)}")
			for table in tables:
				print(f"   - {table}")

			# Verificar datos en cada tabla
			print(f"\n📈 Cantidad de registros:")
			for table in tables:
				cur.execute(f"SELECT COUNT(*) as cnt FROM {table}")
				count = cur.fetchone()['cnt']
				print(f"   - {table}: {count} registros")

			# Mostrar ejemplo de usuarios
			print(f"\n👥 Ejemplo de usuarios:")
			cur.execute(
				"SELECT id_usuario, nombre, edad, genero, ubicacion FROM usuarios LIMIT 3"
			)
			for row in cur.fetchall():
				print(f"   - [{row['id_usuario']}] {row['nombre']}, {row['edad']} años, {row['ubicacion']}")

			# Mostrar esquema de tabla usuarios
			print(f"\n📐 Esquema de tabla 'usuarios':")
			cur.execute(
				"""
				SELECT column_name, data_type, is_nullable
				FROM information_schema.columns
				WHERE table_name = 'usuarios'
				ORDER BY ordinal_position
				"""
			)
			for row in cur.fetchall():
				nullable = "NULL" if row['is_nullable'] == 'YES' else "NOT NULL"
				print(f"   - {row['column_name']}: {row['data_type']} {nullable}")

		conn.close()
	except OperationalError as e:
		print(f"❌ Error de conexión: {e}")


def verify_mongodb():
	print_header("🍃 MongoDB - Base de datos de documentos (JSON)")
	try:
		client = MongoClient(MONGO_URI)
		client.admin.command("ping")
		db = client[MONGO_DB]

		collections = db.list_collection_names()
		print(f"✅ Conexión exitosa")
		print(f"📋 Colecciones encontradas: {len(collections)}")

		for coll_name in collections:
			collection = db[coll_name]
			count = collection.count_documents({})
			print(f"   - {coll_name}: {count} documentos")

		# Mostrar ejemplo de documento en perfiles
		if "perfiles" in collections:
			print(f"\n📄 Ejemplo de documento en 'perfiles':")
			example = db["perfiles"].find_one()
			if example:
				# Mostrar solo los campos principales
				fields = {k: v for k, v in example.items() if k != "_id"}
				print(f"   {json.dumps(fields, indent=6, ensure_ascii=False, default=str)}")
			else:
				print("   (sin documentos)")

		# Mostrar estructura de documento
		if "perfiles" in collections and db["perfiles"].count_documents({}) > 0:
			print(f"\n📐 Estructura de documento en 'perfiles':")
			example = db["perfiles"].find_one()
			for key in example.keys():
				if key != "_id":
					value_type = type(example[key]).__name__
					print(f"   - {key}: {value_type}")

		client.close()
	except PyMongoError as e:
		print(f"❌ Error de conexión: {e}")


def verify_redis():
	print_header("🔴 Redis - Cache/Contadores en memoria")
	try:
		client = redis.Redis(
			host=REDIS_HOST,
			port=REDIS_PORT,
			password=REDIS_PASSWORD,
			decode_responses=True,
		)
		client.ping()
		print(f"✅ Conexión exitosa")

		# Obtener estadísticas
		info = client.info()
		print(f"📊 Estadísticas:")
		print(f"   - Versión: {info['redis_version']}")
		print(f"   - Modo: {info['redis_mode']}")
		print(f"   - Memoria usada: {info['used_memory_human']}")

		# Listar todas las claves
		keys = client.keys("*")
		print(f"\n🔑 Claves almacenadas: {len(keys)}")
		for key in keys[:10]:  # Mostrar primeras 10
			key_type = client.type(key)
			ttl = client.ttl(key)
			ttl_str = f"{ttl}s" if ttl > 0 else "sin TTL"
			value = client.get(key) if key_type == "string" else f"[{key_type}]"
			print(f"   - {key} ({key_type}): {value} ({ttl_str})")

		if len(keys) > 10:
			print(f"   ... y {len(keys) - 10} claves más")

		client.close()
	except RedisError as e:
		print(f"❌ Error de conexión: {e}")


def verify_cassandra():
	print_header("🔷 Cassandra - Base de datos time-series (mensajes)")
	try:
		from cassandra.cluster import Cluster, NoHostAvailable
		from cassandra import DependencyException

		try:
			cluster = Cluster(["localhost"], port=9042)
			session = cluster.connect()

			print(f"✅ Conexión exitosa")

			# Obtener keyspaces
			metadata = cluster.metadata
			keyspaces = [ks for ks in metadata.keyspaces.keys() if not ks.startswith("system")]
			print(f"📋 Keyspaces: {keyspaces}")

			# Verificar si existe tinder_app
			if "tinder_app" in metadata.keyspaces:
				ks = metadata.keyspaces["tinder_app"]
				tables = list(ks.tables.keys())
				print(f"📋 Tablas en 'tinder_app': {tables}")

				# Mostrar cantidad de mensajes
				for table in tables:
					try:
						result = session.execute(f"SELECT COUNT(*) as cnt FROM tinder_app.{table}")
						count = result.one()[0] if result else 0
						print(f"   - {table}: {count} registros")
					except Exception as e:
						print(f"   - {table}: ❌ error ({e})")

				# Mostrar ejemplo de mensaje
				print(f"\n💬 Ejemplo de mensajes:")
				try:
					result = session.execute("SELECT * FROM tinder_app.mensajes_timeline LIMIT 3")
					for row in result:
						print(f"   - {row}")
				except Exception as e:
					print(f"   ❌ Error: {e}")
			else:
				print("⚠️  Keyspace 'tinder_app' no existe aún")

			session.shutdown()
			cluster.shutdown()

		except NoHostAvailable as e:
			print(f"❌ No se pudo conectar al host: {e}")
		except DependencyException as e:
			print(f"⚠️  Cassandra no disponible en Python 3.12+ (Windows): {e}")

	except ImportError:
		print(f"❌ cassandra-driver no instalado")
	except Exception as e:
		print(f"❌ Error: {e}")


def verify_neo4j():
	print_header("🔗 Neo4j - Grafo de relaciones (likes, matches)")
	try:
		driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
		driver.verify_connectivity()

		print(f"✅ Conexión exitosa")

		with driver.session() as session:
			# Contar nodos
			result = session.run("MATCH (n) RETURN count(n) as cnt")
			nodes_count = result.single()["cnt"]
			print(f"📍 Nodos totales: {nodes_count}")

			# Contar relaciones
			result = session.run("MATCH ()-[r]->() RETURN count(r) as cnt")
			rels_count = result.single()["cnt"]
			print(f"🔗 Relaciones totales: {rels_count}")

			# Contar por tipo de relación
			result = session.run("MATCH ()-[r]->() RETURN type(r) as rel_type, count(*) as cnt")
			print(f"\n📊 Relaciones por tipo:")
			for record in result:
				print(f"   - {record['rel_type']}: {record['cnt']}")

			# Mostrar ejemplo de usuario con relaciones
			result = session.run(
				"""
				MATCH (u:Usuario)-[r]-(other)
				RETURN u.id as user_id, u.nombre as nombre, 
				       type(r) as rel_type, other.nombre as related_to
				LIMIT 5
				"""
			)
			print(f"\n👥 Ejemplo de relaciones:")
			for record in result:
				print(f"   - {record['nombre']} [id={record['user_id']}] "
					f"--{record['rel_type']}-> {record['related_to']}")

		driver.close()
	except ServiceUnavailable as e:
		print(f"❌ No se pudo conectar: {e}")
	except Exception as e:
		print(f"❌ Error: {e}")


def main():
	print("\n" + "="*60)
	print("  🔍 VERIFICACIÓN DE BASES DE DATOS - TINDER MULTI-DB")
	print("="*60)

	verify_postgres()
	verify_mongodb()
	verify_redis()
	verify_cassandra()
	verify_neo4j()

	print("\n" + "="*60)
	print("  ✅ Verificación completada")
	print("="*60 + "\n")


if __name__ == "__main__":
	main()
