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

    def obtener_match_stats_por_fecha(self, fecha_date):
        query = "SELECT fecha, cantidad_coincidencias, cantidad_fin_de_semana, cantidad_feriado FROM estadisticas_coincidencias_por_dia WHERE fecha = %s"
        return self.session.execute(query, [fecha_date]).one()

    
    # --- MENSAJES POR EVENTO ---
    def registrar_mensajes_antes_de_evento(self, fecha_evento, id_evento, id_coincidencia, cantidad_mensajes):
        query = """
            INSERT INTO mensajes_por_evento (fecha_evento, id_evento, id_coincidencia, cantidad_mensajes)
            VALUES (%s, %s, %s, %s)
        """
        self.session.execute(query, [fecha_evento, id_evento, id_coincidencia, cantidad_mensajes])

    def obtener_todos_mensajes_por_evento(self):
        query = "SELECT fecha_evento, id_evento, id_coincidencia, cantidad_mensajes FROM mensajes_por_evento"
        return list(self.session.execute(query))
