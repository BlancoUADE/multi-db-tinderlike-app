import json
from app.databases.redis_conn import get_redis_client

class RedisRepository:
    def __init__(self):
        self.r = get_redis_client()

    # --- SESIONES ---
    def crear_sesion(self, token, id_usuario, ttl=3600):
        self.r.setex(f"session:{token}", ttl, str(id_usuario))

    def obtener_usuario_sesion(self, token):
        val = self.r.get(f"session:{token}")
        return int(val) if val else None

    def eliminar_sesion(self, token):
        self.r.delete(f"session:{token}")

    # --- CONTADOR DE NOTIFICACIONES ---
    def incrementar_notificaciones_no_leidas(self, id_usuario):
        self.r.incr(f"notificaciones_no_leidas:{id_usuario}")

    def resetear_notificaciones_no_leidas(self, id_usuario):
        self.r.set(f"notificaciones_no_leidas:{id_usuario}", 0)

    def obtener_notificaciones_no_leidas_count(self, id_usuario):
        val = self.r.get(f"notificaciones_no_leidas:{id_usuario}")
        return int(val) if val else 0

    # --- LISTA DE ÚLTIMAS NOTIFICACIONES PENDIENTES ---
    def agregar_notificacion_pendiente(self, id_usuario, notificacion_data):
        key = f"notificaciones_pendientes:{id_usuario}"
        self.r.lpush(key, json.dumps(notificacion_data))
        self.r.ltrim(key, 0, 9)  # Guardar solo las últimas 10

    def obtener_notificaciones_pendientes(self, id_usuario):
        key = f"notificaciones_pendientes:{id_usuario}"
        items = self.r.lrange(key, 0, -1)
        return [json.loads(item) for item in items]

    # --- RANKING DIARIO DE SWIPES ---
    def registrar_swipe_ranking(self, id_usuario_destino, fecha_str):
        # fecha_str should be YYYY-MM-DD
        key = f"top_swipes_dia:{fecha_str}"
        self.r.zincrby(key, 1, str(id_usuario_destino))
        self.r.expire(key, 86400 * 2)  # Mantener por 2 días

    def obtener_top_swipes_dia(self, fecha_str, limit=10):
        key = f"top_swipes_dia:{fecha_str}"
        # Returns list of tuples (member, score) sorted descending
        res = self.r.zrevrange(key, 0, limit - 1, withscores=True)
        return [(int(member), int(score)) for member, score in res]

    # --- CACHE DE RECOMENDACIONES ---
    def cachear_recomendaciones(self, id_usuario, recomendados_ids, ttl=300):
        key = f"recomendaciones:{id_usuario}"
        if recomendados_ids:
            self.r.delete(key)
            self.r.rpush(key, *[str(uid) for uid in recomendados_ids])
            self.r.expire(key, ttl)

    def obtener_recomendaciones_cacheadas(self, id_usuario):
        key = f"recomendaciones:{id_usuario}"
        items = self.r.lrange(key, 0, -1)
        return [int(uid) for uid in items]

    def eliminar_recomendaciones_cache(self, id_usuario):
        self.r.delete(f"recomendaciones:{id_usuario}")
