from app.repositories.postgres_repo import PostgresRepository
from app.repositories.redis_repo import RedisRepository
from app.repositories.mongo_repo import MongoRepository
from app.repositories.cassandra_repo import CassandraRepository
from app.repositories.neo4j_repo import Neo4jRepository
from datetime import datetime, date

class MatchService:
    def __init__(self):
        self.pg_repo = PostgresRepository()
        self.redis_repo = RedisRepository()
        self.mongo_repo = MongoRepository()
        self.cassandra_repo = CassandraRepository()
        self.neo4j_repo = Neo4jRepository()

    def dar_like(self, id_usuario_origen, id_usuario_destino, fecha=None):
        """
        Gives a like. If mutual, generates a match (coincidencia).
        Synchronizes with Neo4j, Cassandra, Redis, and MongoDB.
        """
        if id_usuario_origen == id_usuario_destino:
            raise ValueError("No podés darte like a vos mismo.")
        
        # Check active block
        if self.pg_repo.existe_bloqueo_activo(id_usuario_origen, id_usuario_destino):
            raise ValueError("Existe un bloqueo activo entre estos usuarios.")

        # Check duplicate like
        if self.pg_repo.existe_like(id_usuario_origen, id_usuario_destino):
            raise ValueError("Ya le diste like a este usuario.")

        # Parse or default date
        if fecha is None:
            today_date = date.today()
            today_dt = datetime.now()
        elif isinstance(fecha, datetime):
            today_date = fecha.date()
            today_dt = fecha
        elif isinstance(fecha, date):
            today_date = fecha
            today_dt = datetime.combine(fecha, datetime.min.time())
        else:
            try:
                today_dt = datetime.strptime(fecha, "%Y-%m-%d %H:%M")
                today_date = today_dt.date()
            except Exception:
                try:
                    today_dt = datetime.strptime(fecha, "%Y-%m-%d")
                    today_date = today_dt.date()
                except Exception:
                    today_date = date.today()
                    today_dt = datetime.now()

        # 1. Write to PostgreSQL (source of truth)
        id_like = self.pg_repo.registrar_like(id_usuario_origen, id_usuario_destino, fecha_like=today_dt)
        
        # Check if inverse like exists
        es_match = self.pg_repo.existe_like(id_usuario_destino, id_usuario_origen)
        id_coincidencia = None
                
        today_str = today_date.strftime("%Y-%m-%d")
        
        if es_match:
            # Check if holiday
            feriado = self.pg_repo.obtener_feriado(today_date)
            fecha_feriado = today_date if feriado else None
            
            # Create match in PostgreSQL
            id_coincidencia = self.pg_repo.crear_coincidencia(id_usuario_origen, id_usuario_destino, fecha_feriado, fecha_coincidencia=today_dt)
        
        # --- SYNCHRONIZATION PHASE ---
        
        # 2. Neo4j Sync
        try:
            self.neo4j_repo.registrar_like_relacion(id_usuario_origen, id_usuario_destino)
            if es_match:
                self.neo4j_repo.registrar_coincidencia_relacion(id_usuario_origen, id_usuario_destino)
        except Exception as e:
            print(f"[SYNC ERROR] Neo4j likes/match sync failed: {e}")

        # 3. Cassandra Sync
        try:
            self.cassandra_repo.registrar_like_stats(today_date, id_usuario_destino)
            if es_match:
                # Check weekend
                es_fin_de_semana = today_date.weekday() >= 5 # 5=Sat, 6=Sun
                es_feriado = fecha_feriado is not None
                self.cassandra_repo.registrar_coincidencia_stats(today_date, es_fin_de_semana, es_feriado)
        except Exception as e:
            print(f"[SYNC ERROR] Cassandra swipes/match metrics sync failed: {e}")

        # 4. Redis Sync
        try:
            self.redis_repo.registrar_swipe_ranking(id_usuario_destino, today_str)
        except Exception as e:
            print(f"[SYNC ERROR] Redis swipe ranking sync failed: {e}")

        # 5. MongoDB Logs & Notification Sync
        try:
            if es_match:
                # Log match
                self.mongo_repo.db.actividad_importante.insert_one({
                    "tipo_evento": "MATCH_GENERADO",
                    "id_usuario": id_usuario_origen,
                    "fecha": today_dt,
                    "detalles": {"id_usuario_destino": id_usuario_destino, "id_coincidencia": id_coincidencia}
                })
                self.mongo_repo.db.actividad_importante.insert_one({
                    "tipo_evento": "MATCH_GENERADO",
                    "id_usuario": id_usuario_destino,
                    "fecha": today_dt,
                    "detalles": {"id_usuario_destino": id_usuario_origen, "id_coincidencia": id_coincidencia}
                })
                
                # Create match notification in Postgres for BOTH users
                notif_origen = self.pg_repo.crear_notificacion(id_usuario_origen, "COINCIDENCIA", id_coincidencia=id_coincidencia)
                notif_destino = self.pg_repo.crear_notificacion(id_usuario_destino, "COINCIDENCIA", id_coincidencia=id_coincidencia)
                
                # Notify both in Redis
                self.redis_repo.incrementar_notificaciones_no_leidas(id_usuario_origen)
                self.redis_repo.incrementar_notificaciones_no_leidas(id_usuario_destino)
                
                user_origen = self.pg_repo.obtener_usuario_por_id(id_usuario_origen)
                user_destino = self.pg_repo.obtener_usuario_por_id(id_usuario_destino)
                
                self.redis_repo.agregar_notificacion_pendiente(id_usuario_origen, {
                    "id_notificacion": notif_origen,
                    "tipo": "COINCIDENCIA",
                    "mensaje": f"¡Tuviste una coincidencia con {user_destino['nombre']}!",
                    "fecha": today_dt.isoformat()
                })
                self.redis_repo.agregar_notificacion_pendiente(id_usuario_destino, {
                    "id_notificacion": notif_destino,
                    "tipo": "COINCIDENCIA",
                    "mensaje": f"¡Tuviste una coincidencia con {user_origen['nombre']}!",
                    "fecha": today_dt.isoformat()
                })
            else:
                # Log like
                self.mongo_repo.db.actividad_importante.insert_one({
                    "tipo_evento": "LIKE_REALIZADO",
                    "id_usuario": id_usuario_origen,
                    "fecha": today_dt,
                    "detalles": {"id_usuario_destino": id_usuario_destino}
                })
                
                # Create like notification in Postgres
                notif_id = self.pg_repo.crear_notificacion(id_usuario_destino, "LIKE", id_like=id_like)
                
                self.redis_repo.incrementar_notificaciones_no_leidas(id_usuario_destino)
                self.redis_repo.agregar_notificacion_pendiente(id_usuario_destino, {
                    "id_notificacion": notif_id,
                    "tipo": "LIKE",
                    "mensaje": f"A alguien le gustó tu perfil",
                    "fecha": today_dt.isoformat()
                })
        except Exception as e:
            print(f"[SYNC ERROR] MongoDB/Redis activity logging failed: {e}")

        # Clear cache for origin recommendations
        try:
            self.redis_repo.eliminar_recomendaciones_cache(id_usuario_origen)
        except Exception:
            pass

        return es_match, id_coincidencia

    def enviar_mensaje(self, id_coincidencia, id_emisor, contenido, fecha=None):
        """
        Sends a message inside a match. Validates blocks and match presence.
        """
        coincidencia = self.pg_repo.obtener_coincidencia_por_id(id_coincidencia)
        if not coincidencia:
            raise ValueError("No existe la coincidencia especificada.")
        
        id_usuario1 = coincidencia["id_usuario1"]
        id_usuario2 = coincidencia["id_usuario2"]
        id_receptor = id_usuario2 if id_emisor == id_usuario1 else id_usuario1
        
        # Check active block
        if self.pg_repo.existe_bloqueo_activo(id_emisor, id_receptor):
            raise ValueError("No se pueden enviar mensajes porque existe un bloqueo activo.")

        # Parse date
        if fecha is None:
            today_dt = datetime.now()
        elif isinstance(fecha, datetime):
            today_dt = fecha
        elif isinstance(fecha, date):
            today_dt = datetime.combine(fecha, datetime.min.time())
        else:
            try:
                today_dt = datetime.strptime(fecha, "%Y-%m-%d %H:%M")
            except Exception:
                try:
                    today_dt = datetime.strptime(fecha, "%Y-%m-%d")
                except Exception:
                    today_dt = datetime.now()

        # 1. Save message to PostgreSQL
        id_mensaje = self.pg_repo.guardar_mensaje(id_coincidencia, id_emisor, contenido, fecha_envio=today_dt)
        
        # 2. Create notification in PostgreSQL
        notif_id = self.pg_repo.crear_notificacion(id_receptor, "MENSAJE", id_mensaje=id_mensaje)
        
        # 3. Redis update for receptor
        try:
            self.redis_repo.incrementar_notificaciones_no_leidas(id_receptor)
            user_emisor = self.pg_repo.obtener_usuario_por_id(id_emisor)
            self.redis_repo.agregar_notificacion_pendiente(id_receptor, {
                "id_notificacion": notif_id,
                "tipo": "MENSAJE",
                "mensaje": f"Nuevo mensaje de {user_emisor['nombre']}: {contenido[:20]}...",
                "fecha": today_dt.isoformat()
            })
        except Exception as e:
            print(f"[SYNC ERROR] Redis message notification sync failed: {e}")

        # 4. MongoDB activity log
        try:
            self.mongo_repo.db.actividad_importante.insert_one({
                "tipo_evento": "MENSAJE_ENVIADO",
                "id_usuario": id_emisor,
                "fecha": today_dt,
                "detalles": {"id_receptor": id_receptor, "id_mensaje": id_mensaje}
            })
        except Exception as e:
            print(f"[SYNC ERROR] MongoDB activity logging failed: {e}")

        return id_mensaje

    def obtener_conversacion(self, id_coincidencia, id_usuario):
        # Validate that the user is part of the match
        coincidencia = self.pg_repo.obtener_coincidencia_por_id(id_coincidencia)
        if not coincidencia:
            raise ValueError("No existe la coincidencia.")
        if id_usuario not in (coincidencia["id_usuario1"], coincidencia["id_usuario2"]):
            raise ValueError("No estás autorizado para ver esta conversación.")
        
        return self.pg_repo.obtener_mensajes_conversacion(id_coincidencia)

    def obtener_coincidencias(self, id_usuario):
        return self.pg_repo.obtener_coincidencias_usuario(id_usuario)

    # --- NOTIFICACIONES ---
    def obtener_notificaciones(self, id_usuario, solo_no_leidas=False):
        if solo_no_leidas:
            return self.pg_repo.obtener_notificaciones_no_leidas(id_usuario)
        return self.pg_repo.obtener_todas_notificaciones(id_usuario)

    def marcar_notificaciones_leidas(self, id_usuario):
        # 1. Postgres update
        self.pg_repo.marcar_notificaciones_como_leidas(id_usuario)
        
        # 2. Redis Reset
        try:
            self.redis_repo.resetear_notificaciones_no_leidas(id_usuario)
        except Exception as e:
            print(f"[SYNC ERROR] Redis notifications reset failed: {e}")

    def obtener_contador_no_leidas(self, id_usuario):
        try:
            return self.redis_repo.obtener_notificaciones_no_leidas_count(id_usuario)
        except Exception:
            # Fallback to Postgres count
            notifs = self.pg_repo.obtener_notificaciones_no_leidas(id_usuario)
            return len(notifs)
