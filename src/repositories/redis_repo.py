from src.database.connection import get_redis_client

class RedisRepository:
    def __init__(self):
        self.r = get_redis_client()

    def create_session(self, token, user_id, ttl=3600):
        """Create session with TTL and store user_id."""
        key = f"session:{token}"
        self.r.set(key, str(user_id), ex=ttl)

    def get_user_id_by_token(self, token):
        """Get user_id associated with token, or None if expired/not found."""
        key = f"session:{token}"
        val = self.r.get(key)
        return int(val) if val else None

    def delete_session(self, token):
        """Delete session key."""
        key = f"session:{token}"
        self.r.delete(key)

    def add_user_online(self, user_id):
        """Add user_id to the set of online users."""
        self.r.sadd("users:online", str(user_id))

    def remove_user_online(self, user_id):
        """Remove user_id from the set of online users."""
        self.r.srem("users:online", str(user_id))

    def is_user_online(self, user_id):
        """Check if user_id is online."""
        return self.r.sismember("users:online", str(user_id))

    def push_candidates(self, user_id, candidate_ids, ttl=300):
        """Push a list of candidate user IDs to Redis list and set TTL."""
        key = f"candidates:{user_id}"
        self.r.delete(key)  # clear any old list
        if candidate_ids:
            # Redis lpush accepts multiple values
            self.r.lpush(key, *[str(cid) for cid in reversed(candidate_ids)])
            self.r.expire(key, ttl)

    def pop_candidate(self, user_id):
        """Pop and return the next candidate user ID, or None if empty."""
        key = f"candidates:{user_id}"
        val = self.r.lpop(key)
        return int(val) if val else None

    def get_candidates_count(self, user_id):
        """Get number of candidates currently cached."""
        key = f"candidates:{user_id}"
        return self.r.llen(key)
