from pymongo import MongoClient
from app.config import settings

def get_mongo_client():
    """Returns a MongoDB client instance."""
    return MongoClient(settings.MONGO_URI)

def get_mongo_db():
    """Returns the MongoDB database instance."""
    client = get_mongo_client()
    return client[settings.MONGO_DB]
