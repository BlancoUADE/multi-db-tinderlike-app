from neo4j import GraphDatabase
from app.config import settings

def get_neo4j_driver():
    """Returns a Neo4j GraphDatabase driver instance."""
    return GraphDatabase.driver(
        settings.NEO4J_URI,
        auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
    )
