from app.repositories.postgres_repo import PostgresRepository
from app.repositories.redis_repo import RedisRepository
from app.repositories.mongo_repo import MongoRepository
from app.repositories.cassandra_repo import CassandraRepository
from app.repositories.neo4j_repo import Neo4jRepository
from datetime import date

class ReportService:
    def __init__(self):
        self.pg_repo = PostgresRepository()
        self.redis_repo = RedisRepository()
        self.mongo_repo = MongoRepository()
        self.cassandra_repo = CassandraRepository()
        self.neo4j_repo = Neo4jRepository()

    # --- REPORTE 1: Promedio de coincidencias por día (Cassandra) ---
    def reporte_promedio_coincidencias_por_dia(self):
        stats = self.cassandra_repo.obtener_todas_match_stats()
        if not stats:
            return 0.0, 0
        total_coincidencias = sum(row.cantidad_coincidencias for row in stats)
        total_dias = len(stats)
        promedio = total_coincidencias / total_dias if total_dias > 0 else 0.0
        return promedio, total_coincidencias

    # --- REPORTE 2: Atributos más populares en perfiles (MongoDB) ---
    def reporte_atributos_mas_populares(self):
        generos = self.mongo_repo.obtener_distribucion_generos()
        ubicaciones = self.mongo_repo.obtener_distribucion_ubicaciones()
        edad_stats = self.mongo_repo.obtener_promedio_edad()
        intereses = self.mongo_repo.obtener_intereses_populares()[:10]
        prom_fotos = self.mongo_repo.obtener_promedio_fotos()
        
        return {
            "distribucion_generos": [{"genero": g["_id"], "cantidad": g["count"]} for g in generos],
            "distribucion_ubicaciones": [{"ubicacion": u["_id"], "cantidad": u["count"]} for u in ubicaciones],
            "edad_promedio": round(edad_stats.get("avg_edad", 0) or 0, 1),
            "edad_minima": edad_stats.get("min_edad", 0),
            "edad_maxima": edad_stats.get("max_edad", 0),
            "intereses_populares": [{"interes": i["_id"], "cantidad": i["count"]} for i in intereses],
            "promedio_fotos": round(prom_fotos, 1)
        }

    # --- REPORTE 3: Perfiles con más swipes a la derecha (Redis + Cassandra) ---
    def reporte_top_swipes(self, limit=10):
        # 1. Daily swipes ranking from Redis ZSET
        today_str = date.today().strftime("%Y-%m-%d")
        redis_top = self.redis_repo.obtener_top_swipes_dia(today_str, limit)
        top_diario = []
        for uid, score in redis_top:
            user = self.pg_repo.obtener_usuario_por_id(uid)
            nombre = user["nombre"] if user else f"Usuario #{uid}"
            top_diario.append({"id_usuario": uid, "nombre": nombre, "swipes": score})

        # 2. Historical swipes ranking from Cassandra
        cass_top = self.cassandra_repo.obtener_top_swipes_historico(limit)
        top_historico = []
        for uid, score in cass_top:
            user = self.pg_repo.obtener_usuario_por_id(uid)
            nombre = user["nombre"] if user else f"Usuario #{uid}"
            top_historico.append({"id_usuario": uid, "nombre": nombre, "swipes": score})

        return {
            "top_diario": top_diario,
            "top_historico": top_historico
        }

    # --- REPORTE 4: Duración promedio de conversaciones antes de una cita (Cassandra) ---
    def reporte_duracion_promedio_conversacion_cita(self):
        duraciones = self.cassandra_repo.obtener_todas_duraciones()
        if not duraciones:
            return 0.0, 0
        total_horas = sum(row.duracion_hours for row in duraciones)
        cantidad_citas = len(duraciones)
        promedio = total_horas / cantidad_citas if cantidad_citas > 0 else 0.0
        return promedio, cantidad_citas

    # --- REPORTE 5: Intereses más comunes entre usuarios que coinciden (Neo4j) ---
    def reporte_intereses_comunes_coincidencias(self):
        res = self.neo4j_repo.obtener_intereses_comunes_coincidencias()
        return [{"interes": r["interes"], "cantidad": r["coincidencias_compartidas"]} for r in res]

    # --- REPORTE 6: Perfiles +10 fotos y +3 intereses en común (MongoDB + Neo4j) ---
    def reporte_perfiles_mas_diez_fotos_intereses_comunes(self, id_usuario_actual):
        # 1. MongoDB filters users with > 10 photos
        target_ids = self.mongo_repo.obtener_usuarios_con_mas_de_10_fotos()
        
        # Avoid recommending the user themselves
        if id_usuario_actual in target_ids:
            target_ids.remove(id_usuario_actual)
            
        if not target_ids:
            return []
            
        # 2. Neo4j calculates users sharing at least 3 interests with current user
        compatibles = self.neo4j_repo.obtener_usuarios_intereses_en_comun(id_usuario_actual, target_ids)
        
        resultado = []
        for c in compatibles:
            uid = c["id_usuario"]
            user = self.pg_repo.obtener_usuario_por_id(uid)
            if user:
                resultado.append({
                    "id_usuario": uid,
                    "nombre": user["nombre"],
                    "edad": user["edad"],
                    "ubicacion": user["ubicacion"],
                    "intereses_en_comun": c["common_count"]
                })
        return resultado

    # --- REPORTE 7: Coincidencias en fin de semana / feriados (Cassandra) ---
    def reporte_coincidencias_fin_de_semana_feriados(self):
        stats = self.cassandra_repo.obtener_todas_match_stats()
        if not stats:
            return {
                "total_coincidencias": 0,
                "coincidencias_fin_de_semana": 0,
                "coincidencias_feriados": 0,
                "porcentaje_fin_de_semana": 0.0,
                "porcentaje_feriados": 0.0
            }
        
        total = sum(row.cantidad_coincidencias for row in stats)
        fin_de_semana = sum(row.cantidad_fin_de_semana for row in stats)
        feriados = sum(row.cantidad_feriado for row in stats)
        
        porc_fds = (fin_de_semana / total * 100) if total > 0 else 0.0
        porc_fer = (feriados / total * 100) if total > 0 else 0.0
        
        return {
            "total_coincidencias": total,
            "coincidencias_fin_de_semana": fin_de_semana,
            "coincidencias_feriados": feriados,
            "porcentaje_fin_de_semana": round(porc_fds, 1),
            "porcentaje_feriados": round(porc_fer, 1)
        }
