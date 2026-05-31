"""
Redis operations - In-memory counters and notifications
"""

from redis.exceptions import RedisError


def increment_unread_count(redis_client, user_id):
	"""Increment unread notifications counter"""
	try:
		redis_client.incr(f"user:{user_id}:notificaciones_no_leidas")
		return True
	except RedisError as error:
		print("No se pudo actualizar el contador de notificaciones en Redis.")
		print(error)
		return False


def get_unread_count(redis_client, user_id):
	"""Get unread notifications count"""
	try:
		count = redis_client.get(f"user:{user_id}:notificaciones_no_leidas")
		return int(count) if count else 0
	except RedisError as error:
		print("No se pudo obtener el contador de notificaciones.")
		print(error)
		return 0


def reset_unread_count(redis_client, user_id):
	"""Reset unread counter"""
	try:
		redis_client.delete(f"user:{user_id}:notificaciones_no_leidas")
		return True
	except RedisError as error:
		print("No se pudo resetear el contador.")
		print(error)
		return False
