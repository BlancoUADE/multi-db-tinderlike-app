from app.repositories.postgres_repo import PostgresRepository
from app.repositories.mongo_repo import MongoRepository
from app.repositories.neo4j_repo import Neo4jRepository
from app.repositories.redis_repo import RedisRepository

class ProfileService:
    def __init__(self):
        self.pg_repo = PostgresRepository()
        self.mongo_repo = MongoRepository()
        self.neo4j_repo = Neo4jRepository()
        self.redis_repo = RedisRepository()

    def sincronizar_perfil_publico(self, id_usuario):
        """
        Gathers data from PostgreSQL and updates the denormalized representation in MongoDB.
        """
        try:
            user = self.pg_repo.obtener_usuario_por_id(id_usuario)
            if not user or not user["activo"]:
                self.mongo_repo.eliminar_perfil_publico(id_usuario)
                return
            
            interests = self.pg_repo.obtener_intereses_usuario(id_usuario)
            interest_names = [i["nombre"] for i in interests]
            
            photos = self.pg_repo.obtener_fotos_usuario(id_usuario)
            photos_list = [{"url": p["url_archivo"], "principal": p["es_principal"]} for p in photos]
            
            perfil_denorm = {
                "nombre": user["nombre"],
                "edad": user["edad"],
                "genero": user["genero"],
                "ubicacion": user["ubicacion"],
                "biografia": user.get("biografia") or "",
                "intereses": interest_names,
                "fotos": photos_list,
                "cantidad_fotos": len(photos_list)
            }
            self.mongo_repo.upsert_perfil_publico(id_usuario, perfil_denorm)
        except Exception as e:
            print(f"[SYNC ERROR] Failed to sync denormalized profile to MongoDB for user {id_usuario}: {e}")

    def obtener_perfil(self, id_usuario):
        """
        Tries to read the denormalized profile from MongoDB. Falls back to PostgreSQL if not found.
        """
        perfil = self.mongo_repo.obtener_perfil_publico(id_usuario)
        if not perfil:
            # Re-sync and try again
            self.sincronizar_perfil_publico(id_usuario)
            perfil = self.mongo_repo.obtener_perfil_publico(id_usuario)
            if not perfil:
                # Falls back to postgres data
                user = self.pg_repo.obtener_usuario_por_id(id_usuario)
                if not user:
                    return None
                interests = self.pg_repo.obtener_intereses_usuario(id_usuario)
                photos = self.pg_repo.obtener_fotos_usuario(id_usuario)
                perfil = {
                    "id_usuario": id_usuario,
                    "nombre": user["nombre"],
                    "edad": user["edad"],
                    "genero": user["genero"],
                    "ubicacion": user["ubicacion"],
                    "biografia": user["biografia"] or "",
                    "intereses": [i["nombre"] for i in interests],
                    "fotos": [{"url": p["url_archivo"], "principal": p["es_principal"]} for p in photos],
                    "cantidad_fotos": len(photos)
                }
        return perfil

    def actualizar_datos_personales(self, id_usuario, update_data):
        # 1. Update in PostgreSQL
        self.pg_repo.actualizar_usuario(id_usuario, update_data)

        # 2. Sync Neo4j Node
        try:
            self.neo4j_repo.crear_usuario_nodo(
                id_usuario=id_usuario,
                nombre=update_data["nombre"],
                edad=update_data["edad"],
                genero=update_data["genero"],
                ubicacion=update_data["ubicacion"]
            )
        except Exception as e:
            print(f"[SYNC ERROR] Failed to sync profile updates to Neo4j: {e}")

        # 3. Synchronize MongoDB public profile
        self.sincronizar_perfil_publico(id_usuario)

        # 4. Clear Recommendations Cache
        self.redis_repo.eliminar_recomendaciones_cache(id_usuario)

        # 5. Log Activity in MongoDB
        try:
            self.mongo_repo.registrar_actividad("PERFIL_ACTUALIZADO", id_usuario)
        except Exception:
            pass

    # --- FOTOS ---
    def agregar_foto(self, id_usuario, url_archivo, es_principal=False):
        self.pg_repo.agregar_foto(id_usuario, url_archivo, es_principal)
        self.sincronizar_perfil_publico(id_usuario)
        
        try:
            self.mongo_repo.registrar_actividad(
                tipo_evento="FOTO_AGREGADA",
                id_usuario=id_usuario,
                detalles={"url": url_archivo, "es_principal": es_principal}
            )
        except Exception:
            pass

    def marcar_foto_principal(self, id_usuario, id_foto):
        self.pg_repo.marcar_foto_principal(id_usuario, id_foto)
        self.sincronizar_perfil_publico(id_usuario)
        
        try:
            self.mongo_repo.registrar_actividad("PERFIL_ACTUALIZADO", id_usuario, {"cambio": "foto_principal"})
        except Exception:
            pass

    def eliminar_foto(self, id_usuario, id_foto):
        self.pg_repo.eliminar_foto(id_usuario, id_foto)
        self.sincronizar_perfil_publico(id_usuario)
        
        try:
            self.mongo_repo.registrar_actividad("FOTO_ELIMINADA", id_usuario, {"id_foto": id_foto})
        except Exception:
            pass

    def obtener_fotos(self, id_usuario):
        return self.pg_repo.obtener_fotos_usuario(id_usuario)

    # --- INTERESES ---
    def obtener_intereses(self, id_usuario):
        return self.pg_repo.obtener_intereses_usuario(id_usuario)

    def agregar_interes(self, id_usuario, nombre_interes):
        # 1. Postgres catalog update
        id_interes = self.pg_repo.obtener_o_crear_interes(nombre_interes)
        self.pg_repo.asociar_interes_usuario(id_usuario, id_interes)

        # 2. Neo4j Graph sync
        try:
            self.neo4j_repo.asociar_interes_usuario(id_usuario, nombre_interes)
        except Exception as e:
            print(f"[SYNC ERROR] Neo4j interest link failed: {e}")

        # 3. MongoDB denorm profile sync
        self.sincronizar_perfil_publico(id_usuario)

        # 4. Clear Recommendations Cache
        self.redis_repo.eliminar_recomendaciones_cache(id_usuario)

        # 5. Log Activity in MongoDB
        try:
            self.mongo_repo.registrar_actividad("INTERES_AGREGADO", id_usuario, {"interes": nombre_interes})
        except Exception:
            pass

    def quitar_interes(self, id_usuario, id_interes, nombre_interes):
        # 1. Postgres catalog update
        self.pg_repo.desasociar_interes_usuario(id_usuario, id_interes)

        # 2. Neo4j Graph sync
        try:
            self.neo4j_repo.desasociar_interes_usuario(id_usuario, nombre_interes)
        except Exception as e:
            print(f"[SYNC ERROR] Neo4j interest unlink failed: {e}")

        # 3. MongoDB denorm profile sync
        self.sincronizar_perfil_publico(id_usuario)

        # 4. Clear Recommendations Cache
        self.redis_repo.eliminar_recomendaciones_cache(id_usuario)

        # 5. Log Activity in MongoDB
        try:
            self.mongo_repo.registrar_actividad("INTERES_QUITADO", id_usuario, {"interes": nombre_interes})
        except Exception:
            pass
