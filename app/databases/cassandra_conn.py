from cassandra.cluster import Cluster
from app.config import settings

_cached_cluster = None
_cached_session = None

def get_cassandra_session():
    """Returns a Cassandra session initialized with the keyspace, reusing the connection if available."""
    global _cached_cluster, _cached_session
    if _cached_session is None:
        _cached_cluster = Cluster([settings.CASSANDRA_HOST], port=settings.CASSANDRA_PORT)
        session = _cached_cluster.connect()
        
        # Ensure keyspace exists
        session.execute(f"""
            CREATE KEYSPACE IF NOT EXISTS {settings.CASSANDRA_KEYSPACE}
            WITH replication = {{'class': 'SimpleStrategy', 'replication_factor': 1}}
        """)
        session.set_keyspace(settings.CASSANDRA_KEYSPACE)
        _cached_session = session
        
    return _cached_cluster, _cached_session

