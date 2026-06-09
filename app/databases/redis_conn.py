import redis
from app.config import settings

_cached_client = None

def get_redis_client():
    """Returns a Redis client instance, reusing connection if available."""
    global _cached_client
    if _cached_client is None:
        _cached_client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            decode_responses=True
        )
    return _cached_client

