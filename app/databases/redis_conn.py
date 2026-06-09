import redis
from app.config import settings

def get_redis_client():
    """Returns a Redis client instance with decode_responses=True."""
    return redis.Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        decode_responses=True
    )
