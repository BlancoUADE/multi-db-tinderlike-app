from app.repositories.postgres_repo import PostgresRepository
from app.repositories.neo4j_repo import Neo4jRepository
from app.repositories.mongo_repo import MongoRepository
from app.repositories.redis_repo import RedisRepository
from app.repositories.cassandra_repo import CassandraRepository
from datetime import datetime

class EventService:
    def __init__(self):
        self.pg_repo = PostgresRepository()
        self.neo4j_repo = Neo4jRepository()
        self.mongo_repo = MongoRepository()
        self.redis_repo = RedisRepository()
        self.cassandra_repo = CassandraRepository()

    def proponer_cita(self, id_organizador, id_coincidencia, nombre_evento, fecha, ubicacion, fecha_creacion=None):
        """
        Creates a proposed event (cita) in Postgres, maps relationships in Neo4j, 
        logs in Mongo, and notifies the invitee in Redis.
        """
        coincidencia = self.pg_repo.obtener_coincidencia_por_id(id_coincidencia)
        if not coincidencia:
            raise ValueError("No existe la coincidencia especificada.")
        
        # Verify organizer is part of the match
        u1, u2 = coincidencia["id_usuario1"], coincidencia["id_usuario2"]
        if id_organizador not in (u1, u2):
            raise ValueError("No estás autorizado para proponer citas en esta coincidencia.")
        
        id_receptor = u2 if id_organizador == u1 else u1
        
        # Check active block
        if self.pg_repo.existe_bloqueo_activo(id_organizador, id_receptor):
            raise ValueError("No se puede proponer una cita porque existe un bloqueo activo.")
        
        # Parse dates
        if fecha_creacion is None:
            fecha_creacion_dt = datetime.now()
        elif isinstance(fecha_creacion, datetime):
            fecha_creacion_dt = fecha_creacion
        else:
            try:
                fecha_creacion_dt = datetime.strptime(fecha_creacion, "%Y-%m-%d %H:%M")
            except Exception:
                try:
                    fecha_creacion_dt = datetime.strptime(fecha_creacion, "%Y-%m-%d")
                except Exception:
                    fecha_creacion_dt = datetime.now()

        # Validate date is future compared to creation date
        if fecha <= fecha_creacion_dt:
            raise ValueError("La cita debe ser futura al momento de crearla.")
        
        # Validate no pending event already between the two users
        if self.pg_repo.existe_evento_pendiente(id_coincidencia):
            raise ValueError("Ya existe una propuesta de cita pendiente en esta coincidencia.")

        # 1. Write to PostgreSQL (source of truth)
        id_evento = self.pg_repo.crear_evento(nombre_evento, fecha, ubicacion, id_organizador, id_coincidencia, fecha_creacion=fecha_creacion_dt)
        self.pg_repo.registrar_asistencia_evento(id_receptor, id_evento, estado='PENDIENTE', fecha_registro=fecha_creacion_dt)

        # 2. Sync Neo4j Graph
        try:
            self.neo4j_repo.crear_evento_nodo(id_evento, nombre_evento)
            self.neo4j_repo.registrar_organizador_evento(id_organizador, id_evento)
            self.neo4j_repo.registrar_invitado_evento(id_receptor, id_evento)
        except Exception as e:
            print(f"[SYNC ERROR] Neo4j event sync failed: {e}")

        # 3. Create Notification in PostgreSQL
        notif_id = self.pg_repo.crear_notificacion(id_receptor, "EVENTO", id_evento=id_evento)

        # 4. Redis update for receptor
        try:
            self.redis_repo.incrementar_notificaciones_cantidad_sin_leer(id_receptor)
            user_organizador = self.pg_repo.obtener_usuario_por_id(id_organizador)
            self.redis_repo.agregar_notificacion_tipo(id_receptor, {
                "id_notificacion": notif_id,
                "tipo": "EVENTO",
                "mensaje": f"{user_organizador['nombre']} te propuso una cita: {nombre_evento}",
                "fecha": fecha_creacion_dt.isoformat()
            })
        except Exception as e:
            print(f"[SYNC ERROR] Redis event notification sync failed: {e}")

        # 5. MongoDB log
        try:
            self.mongo_repo.db.actividad_importante.insert_one({
                "tipo_evento": "EVENTO_PROPUESTO",
                "id_usuario": id_organizador,
                "fecha": fecha_creacion_dt,
                "detalles": {"id_receptor": id_receptor, "id_evento": id_evento}
            })
        except Exception as e:
            print(f"[SYNC ERROR] MongoDB logging for proposed event failed: {e}")

        # 6. Update Cassandra messages-before-event metric
        try:
            cnt_mensajes = self.pg_repo.obtener_conteo_mensajes_antes_de(id_coincidencia, fecha_creacion_dt)
            fecha_evento = fecha.date() if hasattr(fecha, 'date') else fecha
            self.cassandra_repo.registrar_mensajes_antes_de_evento(fecha_evento, id_evento, id_coincidencia, cnt_mensajes)
        except Exception as e:
            print(f"[SYNC ERROR] Cassandra message count metrics sync failed: {e}")

        return id_evento

    def aceptar_cita(self, id_receptor, id_evento, fecha_respuesta=None):
        """
        Accepts a proposed event.
        Updates Postgres, Neo4j graph, Mongo log, and calculates duration metrics in Cassandra.
        """
        asistencia = self.pg_repo.obtener_asistencia_evento_por_evento(id_evento)
        if not asistencia or asistencia["id_usuario"] != id_receptor:
            raise ValueError("No tenés invitaciones para este evento.")
        if asistencia["estado"] != 'PENDIENTE':
            raise ValueError(f"Esta invitación ya fue contestada o cancelada (Estado actual: {asistencia['estado']}).")

        evento = self.pg_repo.obtener_evento_por_id(id_evento)
        id_organizador = evento["id_organizador"]
        id_coincidencia = evento["id_coincidencia"]
        
        # Parse date
        if fecha_respuesta is None:
            now = datetime.now()
        elif isinstance(fecha_respuesta, datetime):
            now = fecha_respuesta
        else:
            try:
                now = datetime.strptime(fecha_respuesta, "%Y-%m-%d %H:%M")
            except Exception:
                try:
                    now = datetime.strptime(fecha_respuesta, "%Y-%m-%d")
                except Exception:
                    now = datetime.now()

        # 1. Update in PostgreSQL
        self.pg_repo.actualizar_estado_evento(id_evento, 'ACEPTADA')
        self.pg_repo.actualizar_asistencia_evento(id_evento, 'ACEPTADA', now)

        # 2. Sync Neo4j Graph
        try:
            self.neo4j_repo.registrar_aceptacion_evento(id_receptor, id_evento)
        except Exception as e:
            print(f"[SYNC ERROR] Neo4j event acceptance failed: {e}")

        # 3. Create Notification in Postgres for Organizer
        notif_id = self.pg_repo.crear_notificacion(id_organizador, "EVENTO", id_evento=id_evento)

        # 5. Redis notify
        try:
            self.redis_repo.incrementar_notificaciones_cantidad_sin_leer(id_organizador)
            user_receptor = self.pg_repo.obtener_usuario_por_id(id_receptor)
            self.redis_repo.agregar_notificacion_tipo(id_organizador, {
                "id_notificacion": notif_id,
                "tipo": "EVENTO",
                "mensaje": f"{user_receptor['nombre']} aceptó tu cita: {evento['nombre_evento']}",
                "fecha": now.isoformat()
            })
        except Exception as e:
            print(f"[SYNC ERROR] Redis event notification sync failed: {e}")

        # 6. MongoDB log
        try:
            self.mongo_repo.db.actividad_importante.insert_one({
                "tipo_evento": "EVENTO_ACEPTADO",
                "id_usuario": id_receptor,
                "fecha": now,
                "detalles": {"id_organizador": id_organizador, "id_evento": id_evento}
            })
        except Exception as e:
            print(f"[SYNC ERROR] MongoDB logging for accepted event failed: {e}")

    def rechazar_cita(self, id_receptor, id_evento, fecha_respuesta=None):
        """
        Rejects a proposed event. Updates Postgres, Mongo logs, and notifies organizer.
        """
        asistencia = self.pg_repo.obtener_asistencia_evento_por_evento(id_evento)
        if not asistencia or asistencia["id_usuario"] != id_receptor:
            raise ValueError("No tenés invitaciones para este evento.")
        if asistencia["estado"] != 'PENDIENTE':
            raise ValueError(f"Esta invitación ya fue contestada o cancelada (Estado actual: {asistencia['estado']}).")

        evento = self.pg_repo.obtener_evento_por_id(id_evento)
        id_organizador = evento["id_organizador"]

        # Parse date
        if fecha_respuesta is None:
            now = datetime.now()
        elif isinstance(fecha_respuesta, datetime):
            now = fecha_respuesta
        else:
            try:
                now = datetime.strptime(fecha_respuesta, "%Y-%m-%d %H:%M")
            except Exception:
                try:
                    now = datetime.strptime(fecha_respuesta, "%Y-%m-%d")
                except Exception:
                    now = datetime.now()

        # 1. Update in PostgreSQL
        self.pg_repo.actualizar_estado_evento(id_evento, 'RECHAZADA')
        self.pg_repo.actualizar_asistencia_evento(id_evento, 'RECHAZADA', now)

        # 2. Create Notification in Postgres for Organizer
        notif_id = self.pg_repo.crear_notificacion(id_organizador, "EVENTO", id_evento=id_evento)

        # 3. Redis notify
        try:
            self.redis_repo.incrementar_notificaciones_cantidad_sin_leer(id_organizador)
            user_receptor = self.pg_repo.obtener_usuario_por_id(id_receptor)
            self.redis_repo.agregar_notificacion_tipo(id_organizador, {
                "id_notificacion": notif_id,
                "tipo": "EVENTO",
                "mensaje": f"{user_receptor['nombre']} rechazó tu cita: {evento['nombre_evento']}",
                "fecha": now.isoformat()
            })
        except Exception as e:
            print(f"[SYNC ERROR] Redis event notification sync failed: {e}")

        # 4. MongoDB log
        try:
            self.mongo_repo.db.actividad_importante.insert_one({
                "tipo_evento": "EVENTO_RECHAZADO",
                "id_usuario": id_receptor,
                "fecha": now,
                "detalles": {"id_organizador": id_organizador, "id_evento": id_evento}
            })
        except Exception as e:
            print(f"[SYNC ERROR] MongoDB logging failed: {e}")

    def obtener_citas_propuestas(self, id_usuario):
        return self.pg_repo.obtener_eventos_propuestos_por_mi(id_usuario)

    def obtener_citas_pendientes_recibidas(self, id_usuario):
        return self.pg_repo.obtener_eventos_pendientes_recibidos(id_usuario)

    def obtener_citas_aceptadas(self, id_usuario):
        return self.pg_repo.obtener_eventos_aceptados(id_usuario)
