from pymongo import MongoClient
from app.config import settings

_cached_client = None

def get_mongo_client():
    """Returns a MongoDB client instance, reusing connection if available."""
    global _cached_client
    if _cached_client is None:
        _cached_client = MongoClient(settings.MONGO_URI)
    return _cached_client

def get_mongo_db():
    """Returns the MongoDB database instance."""
    client = get_mongo_client()
    return client[settings.MONGO_DB]

