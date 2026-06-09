from app.databases.postgres_conn import get_postgres_connection
import psycopg2.extras
from datetime import datetime, date

class PostgresRepository:
    def __init__(self):
        pass

    def _execute(self, query, params=(), commit=True, fetch_one=False, fetch_all=False, return_id=False):
        conn = get_postgres_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        try:
            cur.execute(query, params)
            result = None
            if return_id:
                result = cur.fetchone()[0]
            elif fetch_one:
                row = cur.fetchone()
                result = dict(row) if row else None
            elif fetch_all:
                rows = cur.fetchall()
                result = [dict(row) for row in rows]
            if commit:
                conn.commit()
            return result
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cur.close()
            conn.close()

    # --- USUARIOS ---
    def crear_usuario(self, user_data):
        query = """
            INSERT INTO usuarios (nombre, edad, genero, ubicacion, biografia, pref_edad_min, pref_edad_max, email, password_hash)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id_usuario;
        """
        params = (
            user_data["nombre"], user_data["edad"], user_data["genero"], user_data["ubicacion"],
            user_data.get("biografia", ""), user_data["pref_edad_min"], user_data["pref_edad_max"],
            user_data["email"], user_data["password_hash"]
        )
        return self._execute(query, params, return_id=True)

    def obtener_usuario_por_id(self, id_usuario):
        return self._execute("SELECT * FROM usuarios WHERE id_usuario = %s", (id_usuario,), fetch_one=True)

    def obtener_usuario_por_email(self, email):
        return self._execute("SELECT * FROM usuarios WHERE email = %s", (email,), fetch_one=True)

    def actualizar_usuario(self, id_usuario, update_data):
        query = """
            UPDATE usuarios
            SET nombre = %s, edad = %s, genero = %s, ubicacion = %s, biografia = %s,
                pref_edad_min = %s, pref_edad_max = %s, email = %s
            WHERE id_usuario = %s
        """
        params = (
            update_data["nombre"], update_data["edad"], update_data["genero"], update_data["ubicacion"],
            update_data.get("biografia", ""), update_data["pref_edad_min"], update_data["pref_edad_max"],
            update_data["email"], id_usuario
        )
        self._execute(query, params)

    # --- FOTOS ---
    def agregar_foto(self, id_usuario, url_archivo, es_principal=False):
        # If marked as principal, we must unmark other principal photos first
        if es_principal:
            self._execute("UPDATE fotos SET es_principal = FALSE WHERE id_usuario = %s", (id_usuario,))
        
        query = """
            INSERT INTO fotos (id_usuario, url_archivo, es_principal)
            VALUES (%s, %s, %s)
            RETURNING id_foto;
        """
        return self._execute(query, (id_usuario, url_archivo, es_principal), return_id=True)

    def marcar_foto_principal(self, id_usuario, id_foto):
        self._execute("UPDATE fotos SET es_principal = FALSE WHERE id_usuario = %s", (id_usuario,))
        query = "UPDATE fotos SET es_principal = TRUE WHERE id_usuario = %s AND id_foto = %s"
        self._execute(query, (id_usuario, id_foto))

    def eliminar_foto(self, id_usuario, id_foto):
        self._execute("DELETE FROM fotos WHERE id_usuario = %s AND id_foto = %s", (id_usuario, id_foto))

    def obtener_fotos_usuario(self, id_usuario):
        return self._execute("SELECT * FROM fotos WHERE id_usuario = %s ORDER BY id_foto", (id_usuario,), fetch_all=True)

    # --- INTERESES ---
    def obtener_o_crear_interes(self, nombre):
        nombre = nombre.strip().lower()
        res = self._execute("SELECT id_interes FROM intereses WHERE nombre = %s", (nombre,), fetch_one=True)
        if res:
            return res["id_interes"]
        
        query = "INSERT INTO intereses (nombre) VALUES (%s) RETURNING id_interes"
        try:
            return self._execute(query, (nombre,), return_id=True)
        except Exception:
            # Handle potential concurrent write
            res = self._execute("SELECT id_interes FROM intereses WHERE nombre = %s", (nombre,), fetch_one=True)
            return res["id_interes"]

    def asociar_interes_usuario(self, id_usuario, id_interes):
        self._execute("""
            INSERT INTO usuario_intereses (id_usuario, id_interes)
            VALUES (%s, %s)
            ON CONFLICT DO NOTHING
        """, (id_usuario, id_interes))

    def desasociar_interes_usuario(self, id_usuario, id_interes):
        self._execute("DELETE FROM usuario_intereses WHERE id_usuario = %s AND id_interes = %s", (id_usuario, id_interes))

    def obtener_intereses_usuario(self, id_usuario):
        query = """
            SELECT i.* FROM intereses i
            JOIN usuario_intereses ui ON i.id_interes = ui.id_interes
            WHERE ui.id_usuario = %s
        """
        return self._execute(query, (id_usuario,), fetch_all=True)

    # --- LIKES ---
    def registrar_like(self, id_usuario_origen, id_usuario_destino):
        query = """
            INSERT INTO likes (id_usuario_origen, id_usuario_destino)
            VALUES (%s, %s)
            RETURNING id_like;
        """
        return self._execute(query, (id_usuario_origen, id_usuario_destino), return_id=True)

    def existe_like(self, id_usuario_origen, id_usuario_destino):
        res = self._execute("""
            SELECT id_like FROM likes
            WHERE id_usuario_origen = %s AND id_usuario_destino = %s
        """, (id_usuario_origen, id_usuario_destino), fetch_one=True)
        return res is not None

    # --- COINCIDENCIAS (MATCHES) ---
    def crear_coincidencia(self, id_usuario1, id_usuario2, fecha_feriado=None):
        u1, u2 = min(id_usuario1, id_usuario2), max(id_usuario1, id_usuario2)
        query = """
            INSERT INTO coincidencias (id_usuario1, id_usuario2, fecha_feriado)
            VALUES (%s, %s, %s)
            ON CONFLICT (id_usuario1, id_usuario2) DO UPDATE SET fecha_coincidencia = CURRENT_TIMESTAMP
            RETURNING id_coincidencia;
        """
        return self._execute(query, (u1, u2, fecha_feriado), return_id=True)

    def obtener_coincidencia(self, id_usuario1, id_usuario2):
        u1, u2 = min(id_usuario1, id_usuario2), max(id_usuario1, id_usuario2)
        return self._execute("""
            SELECT * FROM coincidencias
            WHERE id_usuario1 = %s AND id_usuario2 = %s
        """, (u1, u2), fetch_one=True)

    def obtener_coincidencia_por_id(self, id_coincidencia):
        return self._execute("SELECT * FROM coincidencias WHERE id_coincidencia = %s", (id_coincidencia,), fetch_one=True)

    def obtener_coincidencias_usuario(self, id_usuario):
        query = """
            SELECT c.*, 
                   u.nombre AS otro_nombre,
                   u.id_usuario AS otro_id,
                   (SELECT contenido FROM mensajes WHERE id_coincidencia = c.id_coincidencia ORDER BY fecha_envio DESC LIMIT 1) AS ultimo_mensaje
            FROM coincidencias c
            JOIN usuarios u ON (u.id_usuario = CASE WHEN c.id_usuario1 = %s THEN c.id_usuario2 ELSE c.id_usuario1 END)
            WHERE c.id_usuario1 = %s OR c.id_usuario2 = %s
            ORDER BY c.fecha_coincidencia DESC
        """
        return self._execute(query, (id_usuario, id_usuario, id_usuario), fetch_all=True)

    # --- MENSAJES ---
    def guardar_mensaje(self, id_coincidencia, id_emisor, contenido):
        query = """
            INSERT INTO mensajes (id_coincidencia, id_emisor, contenido)
            VALUES (%s, %s, %s)
            RETURNING id_mensaje;
        """
        return self._execute(query, (id_coincidencia, id_emisor, contenido), return_id=True)

    def obtener_mensajes_conversacion(self, id_coincidencia):
        query = """
            SELECT m.*, u.nombre AS emisor_nombre
            FROM mensajes m
            JOIN usuarios u ON m.id_emisor = u.id_usuario
            WHERE m.id_coincidencia = %s
            ORDER BY m.fecha_envio ASC
        """
        return self._execute(query, (id_coincidencia,), fetch_all=True)

    def obtener_primer_mensaje(self, id_coincidencia):
        query = """
            SELECT * FROM mensajes
            WHERE id_coincidencia = %s
            ORDER BY fecha_envio ASC
            LIMIT 1
        """
        return self._execute(query, (id_coincidencia,), fetch_one=True)

    # --- BLOQUEOS ---
    def registrar_bloqueo(self, id_bloqueador, id_bloqueado):
        query = """
            INSERT INTO bloqueos (id_bloqueador, id_bloqueado, activo)
            VALUES (%s, %s, TRUE)
            ON CONFLICT (id_bloqueador, id_bloqueado) DO UPDATE SET activo = TRUE, fecha_bloqueo = CURRENT_TIMESTAMP, fecha_desbloqueo = NULL
            RETURNING id_bloqueo;
        """
        return self._execute(query, (id_bloqueador, id_bloqueado), return_id=True)

    def desactivar_bloqueo(self, id_bloqueador, id_bloqueado):
        query = """
            UPDATE bloqueos
            SET activo = FALSE, fecha_desbloqueo = CURRENT_TIMESTAMP
            WHERE id_bloqueador = %s AND id_bloqueado = %s AND activo = TRUE
        """
        self._execute(query, (id_bloqueador, id_bloqueado))

    def existe_bloqueo_activo(self, id_usuario1, id_usuario2):
        # Bidirectional check: returns true if either blocked the other active
        res = self._execute("""
            SELECT id_bloqueo FROM bloqueos
            WHERE ((id_bloqueador = %s AND id_bloqueado = %s) OR (id_bloqueador = %s AND id_bloqueado = %s))
              AND activo = TRUE
        """, (id_usuario1, id_usuario2, id_usuario2, id_usuario1), fetch_one=True)
        return res is not None

    def obtener_bloqueados_activos(self, id_usuario):
        query = """
            SELECT b.*, u.nombre AS nombre_bloqueado
            FROM bloqueos b
            JOIN usuarios u ON b.id_bloqueado = u.id_usuario
            WHERE b.id_bloqueador = %s AND b.activo = TRUE
            ORDER BY b.fecha_bloqueo DESC
        """
        return self._execute(query, (id_usuario,), fetch_all=True)

    # --- EVENTOS (CITAS) ---
    def crear_evento(self, nombre_evento, fecha, ubicacion, id_organizador, id_coincidencia):
        query = """
            INSERT INTO eventos (nombre_evento, fecha, ubicacion, id_organizador, id_coincidencia, estado)
            VALUES (%s, %s, %s, %s, %s, 'PENDIENTE')
            RETURNING id_evento;
        """
        return self._execute(query, (nombre_evento, fecha, ubicacion, id_organizador, id_coincidencia), return_id=True)

    def existe_evento_pendiente(self, id_coincidencia):
        res = self._execute("""
            SELECT id_evento FROM eventos
            WHERE id_coincidencia = %s AND estado = 'PENDIENTE'
        """, (id_coincidencia,), fetch_one=True)
        return res is not None

    def obtener_evento_por_id(self, id_evento):
        return self._execute("SELECT * FROM eventos WHERE id_evento = %s", (id_evento,), fetch_one=True)

    def actualizar_estado_evento(self, id_evento, estado):
        self._execute("UPDATE eventos SET estado = %s WHERE id_evento = %s", (estado, id_evento))

    def registrar_asistencia_evento(self, id_usuario, id_evento, estado='PENDIENTE'):
        query = """
            INSERT INTO asistencia_eventos (id_usuario, id_evento, estado)
            VALUES (%s, %s, %s)
            RETURNING id_asistencia;
        """
        return self._execute(query, (id_usuario, id_evento, estado), return_id=True)

    def obtener_asistencia_evento_por_evento(self, id_evento):
        return self._execute("SELECT * FROM asistencia_eventos WHERE id_evento = %s", (id_evento,), fetch_one=True)

    def actualizar_asistencia_evento(self, id_evento, estado, fecha_respuesta=None):
        if fecha_respuesta is None and estado in ('ACEPTADA', 'RECHAZADA'):
            fecha_respuesta = datetime.now()
        
        query = """
            UPDATE asistencia_eventos
            SET estado = %s, fecha_respuesta = %s
            WHERE id_evento = %s
        """
        self._execute(query, (estado, fecha_respuesta, id_evento))

    def obtener_eventos_propuestos_por_mi(self, id_usuario):
        query = """
            SELECT e.*, ae.estado AS asistencia_estado, u.nombre AS invitado_nombre
            FROM eventos e
            JOIN asistencia_eventos ae ON e.id_evento = ae.id_evento
            JOIN usuarios u ON ae.id_usuario = u.id_usuario
            WHERE e.id_organizador = %s
            ORDER BY e.fecha DESC
        """
        return self._execute(query, (id_usuario,), fetch_all=True)

    def obtener_eventos_pendientes_recibidos(self, id_usuario):
        query = """
            SELECT ae.*, e.nombre_evento, e.fecha, e.ubicacion, u.nombre AS organizador_nombre
            FROM asistencia_eventos ae
            JOIN eventos e ON ae.id_evento = e.id_evento
            JOIN usuarios u ON e.id_organizador = u.id_usuario
            WHERE ae.id_usuario = %s AND ae.estado = 'PENDIENTE'
            ORDER BY e.fecha ASC
        """
        return self._execute(query, (id_usuario,), fetch_all=True)

    def obtener_eventos_aceptados(self, id_usuario):
        query = """
            SELECT e.*, 
                   u.nombre AS otro_nombre, 
                   ae.fecha_respuesta
            FROM eventos e
            JOIN asistencia_eventos ae ON e.id_evento = ae.id_evento
            JOIN usuarios u ON (u.id_usuario = CASE WHEN e.id_organizador = %s THEN ae.id_usuario ELSE e.id_organizador END)
            WHERE (e.id_organizador = %s OR ae.id_usuario = %s) AND e.estado = 'ACEPTADA'
            ORDER BY e.fecha ASC
        """
        return self._execute(query, (id_usuario, id_usuario, id_usuario), fetch_all=True)

    # --- NOTIFICACIONES ---
    def crear_notificacion(self, id_usuario, tipo, id_like=None, id_coincidencia=None, id_mensaje=None, id_evento=None):
        query = """
            INSERT INTO notificaciones (id_usuario, tipo, id_like, id_coincidencia, id_mensaje, id_evento)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id_notificacion;
        """
        return self._execute(query, (id_usuario, tipo, id_like, id_coincidencia, id_mensaje, id_evento), return_id=True)

    def marcar_notificaciones_como_leidas(self, id_usuario):
        self._execute("UPDATE notificaciones SET leida = TRUE WHERE id_usuario = %s AND leida = FALSE", (id_usuario,))

    def marcar_notificacion_por_id_como_leida(self, id_usuario, id_notificacion):
        self._execute("UPDATE notificaciones SET leida = TRUE WHERE id_usuario = %s AND id_notificacion = %s", (id_usuario, id_notificacion))

    def obtener_notificaciones_no_leidas(self, id_usuario):
        query = """
            SELECT * FROM notificaciones
            WHERE id_usuario = %s AND leida = FALSE
            ORDER BY fecha_creacion DESC
        """
        return self._execute(query, (id_usuario,), fetch_all=True)

    def obtener_todas_notificaciones(self, id_usuario):
        query = """
            SELECT * FROM notificaciones
            WHERE id_usuario = %s
            ORDER BY fecha_creacion DESC
        """
        return self._execute(query, (id_usuario,), fetch_all=True)

    # --- FERIADOS ---
    def obtener_feriado(self, fecha):
        # fecha can be date or string
        return self._execute("SELECT * FROM feriados WHERE fecha = %s", (fecha,), fetch_one=True)

    def registrar_feriado(self, fecha, descripcion):
        self._execute("""
            INSERT INTO feriados (fecha, descripcion)
            VALUES (%s, %s)
            ON CONFLICT (fecha) DO UPDATE SET descripcion = %s
        """, (fecha, descripcion, descripcion))
