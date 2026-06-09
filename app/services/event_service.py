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

    def proponer_cita(self, id_organizador, id_coincidencia, nombre_evento, fecha, ubicacion):
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
        
        # Validate date is future
        if fecha <= datetime.now():
            raise ValueError("La cita debe ser futura al momento de crearla.")
        
        # Validate no pending event already between the two users
        if self.pg_repo.existe_evento_pendiente(id_coincidencia):
            raise ValueError("Ya existe una propuesta de cita pendiente en esta coincidencia.")

        # 1. Write to PostgreSQL (source of truth)
        id_evento = self.pg_repo.crear_evento(nombre_evento, fecha, ubicacion, id_organizador, id_coincidencia)
        self.pg_repo.registrar_asistencia_evento(id_receptor, id_evento, estado='PENDIENTE')

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
            self.redis_repo.incrementar_notificaciones_no_leidas(id_receptor)
            user_organizador = self.pg_repo.obtener_usuario_por_id(id_organizador)
            self.redis_repo.agregar_notificacion_pendiente(id_receptor, {
                "id_notificacion": notif_id,
                "tipo": "EVENTO",
                "mensaje": f"{user_organizador['nombre']} te propuso una cita: {nombre_evento}",
                "fecha": datetime.now().isoformat()
            })
        except Exception as e:
            print(f"[SYNC ERROR] Redis event notification sync failed: {e}")

        # 5. MongoDB log
        try:
            self.mongo_repo.registrar_actividad(
                tipo_evento="EVENTO_PROPUESTO",
                id_usuario=id_organizador,
                detalles={"id_receptor": id_receptor, "id_evento": id_evento}
            )
        except Exception as e:
            print(f"[SYNC ERROR] MongoDB logging for proposed event failed: {e}")

        return id_evento

    def aceptar_cita(self, id_receptor, id_evento):
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
        
        now = datetime.now()

        # 1. Update in PostgreSQL
        self.pg_repo.actualizar_estado_evento(id_evento, 'ACEPTADA')
        self.pg_repo.actualizar_asistencia_evento(id_evento, 'ACEPTADA', now)

        # 2. Sync Neo4j Graph
        try:
            self.neo4j_repo.registrar_aceptacion_evento(id_receptor, id_evento)
        except Exception as e:
            print(f"[SYNC ERROR] Neo4j event acceptance failed: {e}")

        # 3. Update Cassandra duration metrics
        try:
            # Get first message date
            first_msg = self.pg_repo.obtener_primer_mensaje(id_coincidencia)
            if first_msg:
                fecha_primer_mensaje = first_msg["fecha_envio"]
            else:
                # Fallback to match date if no messages have been sent yet
                coincidencia = self.pg_repo.obtener_coincidencia_por_id(id_coincidencia)
                fecha_primer_mensaje = coincidencia["fecha_coincidencia"]
            
            self.cassandra_repo.registrar_duracion_conversacion_evento(
                id_evento=id_evento,
                id_coincidencia=id_coincidencia,
                fecha_primer_mensaje=fecha_primer_mensaje,
                fecha_evento_aceptado=now
            )
        except Exception as e:
            print(f"[SYNC ERROR] Cassandra duration metric sync failed: {e}")

        # 4. Create Notification in Postgres for Organizer
        notif_id = self.pg_repo.crear_notificacion(id_organizador, "EVENTO", id_evento=id_evento)

        # 5. Redis notify
        try:
            self.redis_repo.incrementar_notificaciones_no_leidas(id_organizador)
            user_receptor = self.pg_repo.obtener_usuario_por_id(id_receptor)
            self.redis_repo.agregar_notificacion_pendiente(id_organizador, {
                "id_notificacion": notif_id,
                "tipo": "EVENTO",
                "mensaje": f"{user_receptor['nombre']} aceptó tu cita: {evento['nombre_evento']}",
                "fecha": datetime.now().isoformat()
            })
        except Exception as e:
            print(f"[SYNC ERROR] Redis event notification sync failed: {e}")

        # 6. MongoDB log
        try:
            self.mongo_repo.registrar_actividad(
                tipo_evento="EVENTO_ACEPTADO",
                id_usuario=id_receptor,
                detalles={"id_organizador": id_organizador, "id_evento": id_evento}
            )
        except Exception as e:
            print(f"[SYNC ERROR] MongoDB logging for accepted event failed: {e}")

    def rechazar_cita(self, id_receptor, id_evento):
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

        now = datetime.now()

        # 1. Update in PostgreSQL
        self.pg_repo.actualizar_estado_evento(id_evento, 'RECHAZADA')
        self.pg_repo.actualizar_asistencia_evento(id_evento, 'RECHAZADA', now)

        # 2. Create Notification in Postgres for Organizer
        notif_id = self.pg_repo.crear_notificacion(id_organizador, "EVENTO", id_evento=id_evento)

        # 3. Redis notify
        try:
            self.redis_repo.incrementar_notificaciones_no_leidas(id_organizador)
            user_receptor = self.pg_repo.obtener_usuario_por_id(id_receptor)
            self.redis_repo.agregar_notificacion_pendiente(id_organizador, {
                "id_notificacion": notif_id,
                "tipo": "EVENTO",
                "mensaje": f"{user_receptor['nombre']} rechazó tu cita: {evento['nombre_evento']}",
                "fecha": datetime.now().isoformat()
            })
        except Exception as e:
            print(f"[SYNC ERROR] Redis event notification sync failed: {e}")

        # 4. MongoDB log
        try:
            self.mongo_repo.registrar_actividad(
                tipo_evento="EVENTO_RECHAZADO",
                id_usuario=id_receptor,
                detalles={"id_organizador": id_organizador, "id_evento": id_evento}
            )
        except Exception as e:
            print(f"[SYNC ERROR] MongoDB logging failed: {e}")

    def obtener_citas_propuestas(self, id_usuario):
        return self.pg_repo.obtener_eventos_propuestos_por_mi(id_usuario)

    def obtener_citas_pendientes_recibidas(self, id_usuario):
        return self.pg_repo.obtener_eventos_pendientes_recibidos(id_usuario)

    def obtener_citas_aceptadas(self, id_usuario):
        return self.pg_repo.obtener_eventos_aceptados(id_usuario)
