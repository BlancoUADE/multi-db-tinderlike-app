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
    def incrementar_notificaciones_cantidad_sin_leer(self, id_usuario):
        self.r.incr(f"notificaciones_cantidad_sin_leer:{id_usuario}")

    def resetear_notificaciones_cantidad_sin_leer(self, id_usuario):
        self.r.set(f"notificaciones_cantidad_sin_leer:{id_usuario}", 0)

    def obtener_notificaciones_cantidad_sin_leer_count(self, id_usuario):
        val = self.r.get(f"notificaciones_cantidad_sin_leer:{id_usuario}")
        return int(val) if val else 0

    # --- LISTA DE ÚLTIMAS NOTIFICACIONES POR TIPO ---
    def agregar_notificacion_tipo(self, id_usuario, notificacion_data):
        key = f"notificaciones_tipos:{id_usuario}"
        self.r.lpush(key, json.dumps(notificacion_data))
        self.r.ltrim(key, 0, 9)  # Guardar solo las últimas 10

    def obtener_notificaciones_tipos(self, id_usuario):
        key = f"notificaciones_tipos:{id_usuario}"
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

    # --- GEOLOCALIZACIÓN ---
    def indexar_ubicacion_usuario(self, id_usuario, longitud, latitud):
        if longitud is not None and latitud is not None:
            # redis-py geoadd format: geoadd(name, [longitude, latitude, member])
            self.r.geoadd("usuarios_ubicaciones", [float(longitud), float(latitud), str(id_usuario)])

    def obtener_usuarios_cercanos(self, id_usuario, radio_km):
        try:
            # Try GEOSEARCH (available in Redis 6.2+ and redis-py 4+)
            res = self.r.geosearch(
                "usuarios_ubicaciones",
                member=str(id_usuario),
                radius=float(radio_km),
                unit="km",
                withdist=True
            )
            # res is a list of [member, distance]
            return [(int(item[0]), float(item[1])) for item in res if int(item[0]) != int(id_usuario)]
        except Exception:
            # Fallback to GEORADIUSBYMEMBER for older Redis or older redis-py
            try:
                res = self.r.georadiusbymember(
                    "usuarios_ubicaciones",
                    str(id_usuario),
                    float(radio_km),
                    unit="km",
                    withdist=True
                )
                return [(int(item[0]), float(item[1])) for item in res if int(item[0]) != int(id_usuario)]
            except Exception as e:
                print(f"[REDIS ERROR] Geospatial query failed: {e}")
                return []
