from app.databases.mongo_conn import get_mongo_db
from datetime import datetime

class MongoRepository:
    def __init__(self):
        self.db = get_mongo_db()

    # --- PERFILES PÚBLICOS ---
    def upsert_perfil_publico(self, id_usuario, perfil_data):
        perfil_data["id_usuario"] = id_usuario
        perfil_data["fecha_actualizacion"] = datetime.utcnow()
        self.db.perfiles_publicos.update_one(
            {"id_usuario": id_usuario},
            {"$set": perfil_data},
            upsert=True
        )

    def obtener_perfil_publico(self, id_usuario):
        res = self.db.perfiles_publicos.find_one({"id_usuario": id_usuario})
        if res:
            res.pop("_id", None)
        return res

    def eliminar_perfil_publico(self, id_usuario):
        self.db.perfiles_publicos.delete_one({"id_usuario": id_usuario})

    # --- LOGS DE ACTIVIDAD IMPORTANTE ---
    def registrar_actividad(self, tipo_evento, id_usuario, detalles=None):
        log_entry = {
            "tipo_evento": tipo_evento,
            "id_usuario": id_usuario,
            "fecha": datetime.utcnow(),
            "detalles": detalles or {}
        }
        self.db.actividad_importante.insert_one(log_entry)

    # --- CONSULTAS DE REPORTES ---
    def obtener_distribucion_generos(self):
        pipeline = [
            {"$group": {"_id": "$genero", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]
        return list(self.db.perfiles_publicos.aggregate(pipeline))

    def obtener_distribucion_ubicaciones(self):
        pipeline = [
            {"$group": {"_id": "$ubicacion", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]
        return list(self.db.perfiles_publicos.aggregate(pipeline))

    def obtener_promedio_edad(self):
        pipeline = [
            {"$group": {
                "_id": None, 
                "avg_edad": {"$avg": "$edad"},
                "min_edad": {"$min": "$edad"},
                "max_edad": {"$max": "$edad"}
            }}
        ]
        res = list(self.db.perfiles_publicos.aggregate(pipeline))
        return res[0] if res else {"avg_edad": 0, "min_edad": 0, "max_edad": 0}

    def obtener_intereses_populares(self):
        pipeline = [
            {"$unwind": "$intereses"},
            {"$group": {"_id": "$intereses", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]
        return list(self.db.perfiles_publicos.aggregate(pipeline))

    def obtener_promedio_fotos(self):
        pipeline = [
            {"$group": {"_id": None, "avg_fotos": {"$avg": "$cantidad_fotos"}}}
        ]
        res = list(self.db.perfiles_publicos.aggregate(pipeline))
        return res[0]["avg_fotos"] if res else 0.0

    def obtener_usuarios_con_mas_de_10_fotos(self):
        # Returns list of user IDs
        cursor = self.db.perfiles_publicos.find(
            {"cantidad_fotos": {"$gt": 10}}, 
            {"id_usuario": 1}
        )
        return [doc["id_usuario"] for doc in cursor]
