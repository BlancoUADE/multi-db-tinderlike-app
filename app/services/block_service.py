from app.repositories.postgres_repo import PostgresRepository
from app.repositories.neo4j_repo import Neo4jRepository
from app.repositories.mongo_repo import MongoRepository
from app.repositories.redis_repo import RedisRepository

class BlockService:
    def __init__(self):
        self.pg_repo = PostgresRepository()
        self.neo4j_repo = Neo4jRepository()
        self.mongo_repo = MongoRepository()
        self.redis_repo = RedisRepository()

    def bloquear_usuario(self, id_bloqueador, id_bloqueado):
        if id_bloqueador == id_bloqueado:
            raise ValueError("No podés bloquearte a vos mismo.")
        
        # 1. Write to PostgreSQL (source of truth)
        id_bloqueo = self.pg_repo.registrar_bloqueo(id_bloqueador, id_bloqueado)

        # 2. Sync Neo4j Graph
        try:
            self.neo4j_repo.registrar_bloqueo_relacion(id_bloqueador, id_bloqueado)
        except Exception as e:
            print(f"[SYNC ERROR] Neo4j block relationship creation failed: {e}")

        # 3. Clear Recommendation Caches
        try:
            self.redis_repo.eliminar_recomendaciones_cache(id_bloqueador)
            self.redis_repo.eliminar_recomendaciones_cache(id_bloqueado)
        except Exception:
            pass

        # 4. Log Activity in MongoDB
        try:
            self.mongo_repo.registrar_actividad(
                tipo_evento="USUARIO_BLOQUEADO",
                id_usuario=id_bloqueador,
                detalles={"id_bloqueado": id_bloqueado, "id_bloqueo": id_bloqueo}
            )
        except Exception as e:
            print(f"[SYNC ERROR] MongoDB logging for block failed: {e}")

    def desbloquear_usuario(self, id_bloqueador, id_bloqueado):
        # 1. Write to PostgreSQL
        self.pg_repo.desactivar_bloqueo(id_bloqueador, id_bloqueado)

        # 2. Sync Neo4j Graph
        try:
            self.neo4j_repo.eliminar_bloqueo_relacion(id_bloqueador, id_bloqueado)
        except Exception as e:
            print(f"[SYNC ERROR] Neo4j block relationship deletion failed: {e}")

        # 3. Clear Recommendation Caches
        try:
            self.redis_repo.eliminar_recomendaciones_cache(id_bloqueador)
            self.redis_repo.eliminar_recomendaciones_cache(id_bloqueado)
        except Exception:
            pass

        # 4. Log Activity in MongoDB
        try:
            self.mongo_repo.registrar_actividad(
                tipo_evento="USUARIO_DESBLOQUEADO",
                id_usuario=id_bloqueador,
                detalles={"id_bloqueado": id_bloqueado}
            )
        except Exception as e:
            print(f"[SYNC ERROR] MongoDB logging for unlock failed: {e}")

    def obtener_bloqueados_activos(self, id_usuario):
        return self.pg_repo.obtener_bloqueados_activos(id_usuario)
