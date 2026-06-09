from app.databases.cassandra_conn import get_cassandra_session
from datetime import datetime, date

class CassandraRepository:
    def __init__(self):
        # We get cluster and session
        self.cluster, self.session = get_cassandra_session()

    def close(self):
        # Connection is managed as a singleton in databases/cassandra_conn.py
        pass

    # --- ESTADÍSTICAS COINCIDENCIAS POR DÍA ---
    def registrar_coincidencia_stats(self, fecha_date, es_fin_de_semana, es_feriado):
        # fecha_date is a datetime.date object
        query_select = "SELECT cantidad_coincidencias, cantidad_fin_de_semana, cantidad_feriado FROM estadisticas_coincidencias_por_dia WHERE fecha = %s"
        row = self.session.execute(query_select, [fecha_date]).one()
        
        cant_coincidencias = 1
        cant_fin_de_semana = 1 if es_fin_de_semana else 0
        cant_feriado = 1 if es_feriado else 0
        
        if row:
            cant_coincidencias += row.cantidad_coincidencias
            cant_fin_de_semana += row.cantidad_fin_de_semana
            cant_feriado += row.cantidad_feriado
            
        query_upsert = """
            INSERT INTO estadisticas_coincidencias_por_dia (fecha, cantidad_coincidencias, cantidad_fin_de_semana, cantidad_feriado)
            VALUES (%s, %s, %s, %s)
        """
        self.session.execute(query_upsert, [fecha_date, cant_coincidencias, cant_fin_de_semana, cant_feriado])

    def obtener_todas_match_stats(self):
        query = "SELECT fecha, cantidad_coincidencias, cantidad_fin_de_semana, cantidad_feriado FROM estadisticas_coincidencias_por_dia"
        return list(self.session.execute(query))

    # --- SWIPES PERFIL POR DIA ---
    def registrar_like_stats(self, fecha_date, id_usuario_destino):
        # 1. Update daily swipes
        query_select_day = "SELECT cantidad_likes FROM swipes_perfil_por_dia WHERE fecha = %s AND id_usuario_destino = %s"
        row_day = self.session.execute(query_select_day, [fecha_date, id_usuario_destino]).one()
        cant_likes_day = 1 + (row_day.cantidad_likes if row_day else 0)
        
        query_insert_day = """
            INSERT INTO swipes_perfil_por_dia (fecha, id_usuario_destino, cantidad_likes)
            VALUES (%s, %s, %s)
        """
        self.session.execute(query_insert_day, [fecha_date, id_usuario_destino, cant_likes_day])

        # 2. Update total swipes
        query_select_tot = "SELECT cantidad_likes_total FROM swipes_perfil_total WHERE id_usuario_destino = %s"
        row_tot = self.session.execute(query_select_tot, [id_usuario_destino]).one()
        cant_likes_tot = 1 + (row_tot.cantidad_likes_total if row_tot else 0)
        
        query_insert_tot = """
            INSERT INTO swipes_perfil_total (id_usuario_destino, cantidad_likes_total)
            VALUES (%s, %s)
        """
        self.session.execute(query_insert_tot, [id_usuario_destino, cant_likes_tot])

    def obtener_top_swipes_historico(self, limit=10):
        # We pull all items and sort in Python because Cassandra does not support global sorting easily without clustering keys.
        query = "SELECT id_usuario_destino, cantidad_likes_total FROM swipes_perfil_total"
        rows = list(self.session.execute(query))
        rows.sort(key=lambda x: x.cantidad_likes_total, reverse=True)
        return [(r.id_usuario_destino, r.cantidad_likes_total) for r in rows[:limit]]

    # --- DURACIÓN CONVERSACIÓN A EVENTO ---
    def registrar_mensajes_antes_de_evento(self, id_evento, id_coincidencia, cantidad_mensajes):
        query = """
            INSERT INTO duracion_conversacion_a_evento (id_evento, id_coincidencia, cantidad_mensajes)
            VALUES (%s, %s, %s)
        """
        self.session.execute(query, [id_evento, id_coincidencia, cantidad_mensajes])

    def obtener_todas_duraciones(self):
        query = "SELECT id_evento, id_coincidencia, cantidad_mensajes FROM duracion_conversacion_a_evento"
        return list(self.session.execute(query))
