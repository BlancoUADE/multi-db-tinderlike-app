from neo4j import GraphDatabase
from app.config import settings

_cached_driver = None

def get_neo4j_driver():
    """Returns a Neo4j GraphDatabase driver instance, reusing the connection if available."""
    global _cached_driver
    if _cached_driver is None:
        _cached_driver = GraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
        )
    return _cached_driver

