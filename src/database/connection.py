import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# PostgreSQL config
PG_HOST = os.getenv("PG_HOST", "localhost")
PG_PORT = int(os.getenv("PG_PORT", 5433))
PG_DB = os.getenv("PG_DB", "tinder_app")
PG_USER = os.getenv("PG_USER", "tpo_user")
PG_PASSWORD = os.getenv("PG_PASSWORD", "tpo_password")

# MongoDB config
MONGO_URI = os.getenv("MONGO_URI", "mongodb://tpo_user:tpo_password@localhost:27017/")
MONGO_DB = os.getenv("MONGO_DB", "tinder_app")

# Redis config
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))

# Cassandra config
CASSANDRA_HOST = os.getenv("CASSANDRA_HOST", "localhost")
CASSANDRA_PORT = int(os.getenv("CASSANDRA_PORT", 9042))
CASSANDRA_KEYSPACE = os.getenv("CASSANDRA_KEYSPACE", "tinder_app")

# Neo4j config
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "tpo_password")


def get_postgres_connection():
    """Establish and return a connection to PostgreSQL."""
    import psycopg2
    return psycopg2.connect(
        host=PG_HOST,
        port=PG_PORT,
        dbname=PG_DB,
        user=PG_USER,
        password=PG_PASSWORD
    )


def get_mongodb_client():
    """Establish and return a MongoClient."""
    from pymongo import MongoClient
    return MongoClient(MONGO_URI)


def get_mongodb_database():
    """Establish and return the specific MongoDB database database object."""
    client = get_mongodb_client()
    return client[MONGO_DB]


def get_redis_client():
    """Establish and return a connection to Redis."""
    import redis
    return redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        decode_responses=True
    )


_cassandra_cluster = None
_cassandra_session = None

def get_cassandra_cluster():
    """Establish and return a Cassandra Cluster object."""
    import logging
    # Suppress verbose Cassandra driver warnings and logging
    logging.getLogger('cassandra').setLevel(logging.ERROR)

    from cassandra.cluster import Cluster
    from cassandra.policies import DCAwareRoundRobinPolicy

    return Cluster(
        contact_points=[CASSANDRA_HOST],
        port=CASSANDRA_PORT,
        protocol_version=5,
        load_balancing_policy=DCAwareRoundRobinPolicy(local_dc='datacenter1')
    )

def get_cassandra_session():
    """Establish a Cassandra Cluster, connect, set keyspace, and return session as a singleton."""
    global _cassandra_cluster, _cassandra_session
    if _cassandra_session is None or _cassandra_session.is_shutdown:
        _cassandra_cluster = get_cassandra_cluster()
        _cassandra_session = _cassandra_cluster.connect()
        # We create the keyspace if not exists for convenience
        _cassandra_session.execute(f"""
            CREATE KEYSPACE IF NOT EXISTS {CASSANDRA_KEYSPACE}
            WITH replication = {{'class': 'SimpleStrategy', 'replication_factor': 1}}
        """)
        _cassandra_session.set_keyspace(CASSANDRA_KEYSPACE)
    return _cassandra_session

def close_cassandra_session():
    """Close the Cassandra cluster and session cleanly."""
    global _cassandra_cluster, _cassandra_session
    if _cassandra_cluster:
        _cassandra_cluster.shutdown()
        _cassandra_cluster = None
        _cassandra_session = None


def get_neo4j_driver():
    """Establish and return a Neo4j GraphDatabase driver."""
    from neo4j import GraphDatabase
    return GraphDatabase.driver(
        NEO4J_URI,
        auth=(NEO4J_USER, NEO4J_PASSWORD)
    )
