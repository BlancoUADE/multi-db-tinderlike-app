from app.databases.cassandra_conn import get_cassandra_session
from datetime import datetime, date

class CassandraRepository:
    def __init__(self):
        # We get cluster and session
        self.cluster, self.session = get_cassandra_session()

    def close(self):
        self.cluster.shutdown()

    # --- MATCH STATS BY DAY ---
    def registrar_coincidencia_stats(self, fecha_date, es_fin_de_semana, es_feriado):
        # fecha_date is a datetime.date object
        query_select = "SELECT cantidad_coincidencias, cantidad_fin_de_semana, cantidad_feriado FROM match_stats_by_day WHERE fecha = %s"
        row = self.session.execute(query_select, [fecha_date]).one()
        
        cant_coincidencias = 1
        cant_fin_de_semana = 1 if es_fin_de_semana else 0
        cant_feriado = 1 if es_feriado else 0
        
        if row:
            cant_coincidencias += row.cantidad_coincidencias
            cant_fin_de_semana += row.cantidad_fin_de_semana
            cant_feriado += row.cantidad_feriado
            
        query_upsert = """
            INSERT INTO match_stats_by_day (fecha, cantidad_coincidencias, cantidad_fin_de_semana, cantidad_feriado)
            VALUES (%s, %s, %s, %s)
        """
        self.session.execute(query_upsert, [fecha_date, cant_coincidencias, cant_fin_de_semana, cant_feriado])

    def obtener_todas_match_stats(self):
        query = "SELECT fecha, cantidad_coincidencias, cantidad_fin_de_semana, cantidad_feriado FROM match_stats_by_day"
        return list(self.session.execute(query))

    # --- PROFILE SWIPES (LIKES) ---
    def registrar_like_stats(self, fecha_date, id_usuario_destino):
        # 1. Update daily swipes
        query_select_day = "SELECT cantidad_likes FROM profile_swipes_by_day WHERE fecha = %s AND id_usuario_destino = %s"
        row_day = self.session.execute(query_select_day, [fecha_date, id_usuario_destino]).one()
        cant_likes_day = 1 + (row_day.cantidad_likes if row_day else 0)
        
        query_insert_day = """
            INSERT INTO profile_swipes_by_day (fecha, id_usuario_destino, cantidad_likes)
            VALUES (%s, %s, %s)
        """
        self.session.execute(query_insert_day, [fecha_date, id_usuario_destino, cant_likes_day])

        # 2. Update total swipes
        query_select_tot = "SELECT cantidad_likes_total FROM profile_swipes_total WHERE id_usuario_destino = %s"
        row_tot = self.session.execute(query_select_tot, [id_usuario_destino]).one()
        cant_likes_tot = 1 + (row_tot.cantidad_likes_total if row_tot else 0)
        
        query_insert_tot = """
            INSERT INTO profile_swipes_total (id_usuario_destino, cantidad_likes_total)
            VALUES (%s, %s)
        """
        self.session.execute(query_insert_tot, [id_usuario_destino, cant_likes_tot])

    def obtener_top_swipes_historico(self, limit=10):
        # We pull all items and sort in Python because Cassandra does not support global sorting easily without clustering keys.
        query = "SELECT id_usuario_destino, cantidad_likes_total FROM profile_swipes_total"
        rows = list(self.session.execute(query))
        rows.sort(key=lambda x: x.cantidad_likes_total, reverse=True)
        return [(r.id_usuario_destino, r.cantidad_likes_total) for r in rows[:limit]]

    # --- CONVERSATION TO EVENT DURATION ---
    def registrar_duracion_conversacion_evento(self, id_evento, id_coincidencia, fecha_primer_mensaje, fecha_evento_aceptado):
        # Calcular duración en horas
        diff = fecha_evento_aceptado - fecha_primer_mensaje
        duracion_horas = diff.total_seconds() / 3600.0
        
        query = """
            INSERT INTO conversation_to_event_duration (id_evento, id_coincidencia, fecha_primer_mensaje, fecha_evento_aceptado, duracion_horas)
            VALUES (%s, %s, %s, %s, %s)
        """
        self.session.execute(query, [id_evento, id_coincidencia, fecha_primer_mensaje, fecha_evento_aceptado, duracion_horas])

    def obtener_todas_duraciones(self):
        query = "SELECT id_evento, duracion_horas FROM conversation_to_event_duration"
        return list(self.session.execute(query))
