"""
Funciones de conexión a todas las bases de datos
"""

import psycopg2
from psycopg2 import OperationalError
from pymongo import MongoClient
from pymongo.errors import PyMongoError
import redis
from redis.exceptions import RedisError
from cassandra import DependencyException, DriverException
from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable

from config import (
	POSTGRES_CONFIG,
	MONGO_URI,
	MONGO_DB,
	REDIS_HOST,
	REDIS_PORT,
	REDIS_PASSWORD,
	CASSANDRA_HOSTS,
	CASSANDRA_PORT,
	NEO4J_URI,
	NEO4J_USER,
	NEO4J_PASSWORD,
)


def connect_postgres():
	"""Conecta a PostgreSQL."""
	return psycopg2.connect(**POSTGRES_CONFIG)


def connect_mongo():
	"""Conecta a MongoDB."""
	return MongoClient(MONGO_URI)


def connect_redis():
	"""Conecta a Redis."""
	return redis.Redis(
		host=REDIS_HOST,
		port=REDIS_PORT,
		password=REDIS_PASSWORD,
		decode_responses=True,
	)


def connect_cassandra():
	"""Conecta a Cassandra."""
	try:
		from cassandra.cluster import Cluster, NoHostAvailable
	except DependencyException as error:
		raise RuntimeError(
			"Cassandra driver no es compatible con Python 3.12+ en Windows. "
			"Usá Python 3.11 para ejecutar la demo."
		) from error

	cluster = Cluster(CASSANDRA_HOSTS, port=CASSANDRA_PORT)
	try:
		session = cluster.connect()
	except NoHostAvailable as error:
		raise RuntimeError(
			"No se pudo conectar a Cassandra. Verificá que el contenedor esté levantado."
		) from error

	return cluster, session


def connect_neo4j():
	"""Conecta a Neo4j."""
	return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
