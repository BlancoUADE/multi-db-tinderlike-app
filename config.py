"""
Configuración centralizada de la aplicación
"""

import os


def get_int_env(name, default):
	"""Obtiene variable de entorno como integer."""
	value = os.getenv(name)
	return int(value) if value else default


# PostgreSQL
POSTGRES_CONFIG = {
	"host": os.getenv("PG_HOST", "127.0.0.1"),
	"port": get_int_env("PG_PORT", 5433),
	"dbname": os.getenv("PG_DB", "tinder_app"),
	"user": os.getenv("PG_USER", "tpo_user"),
	"password": os.getenv("PG_PASSWORD", "tpo_password"),
}

# MongoDB
MONGO_URI = os.getenv("MONGO_URI", "mongodb://tpo_user:tpo_password@localhost:27017/")
MONGO_DB = os.getenv("MONGO_DB", "tinder_app")

# Redis
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = get_int_env("REDIS_PORT", 6379)
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD")

# Cassandra
CASSANDRA_HOSTS = os.getenv("CASSANDRA_HOSTS", "localhost").split(",")
CASSANDRA_PORT = get_int_env("CASSANDRA_PORT", 9042)
CASSANDRA_KEYSPACE = os.getenv("CASSANDRA_KEYSPACE", "tinder_app")

# Neo4j
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "tpo_password")
