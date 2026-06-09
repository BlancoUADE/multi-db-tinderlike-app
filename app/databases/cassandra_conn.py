from cassandra.cluster import Cluster
from app.config import settings

def get_cassandra_session():
    """Returns a Cassandra session initialized with the keyspace."""
    cluster = Cluster([settings.CASSANDRA_HOST], port=settings.CASSANDRA_PORT)
    session = cluster.connect()
    
    # Ensure keyspace exists
    session.execute(f"""
        CREATE KEYSPACE IF NOT EXISTS {settings.CASSANDRA_KEYSPACE}
        WITH replication = {{'class': 'SimpleStrategy', 'replication_factor': 1}}
    """)
    session.set_keyspace(settings.CASSANDRA_KEYSPACE)
    return cluster, session
