import hashlib
import uuid
from datetime import datetime, date
from app.repositories.postgres_repo import PostgresRepository, calcular_edad
from app.repositories.redis_repo import RedisRepository
from app.repositories.mongo_repo import MongoRepository
from app.repositories.neo4j_repo import Neo4jRepository

class AuthService:
    def __init__(self):
        self.pg_repo = PostgresRepository()
        self.redis_repo = RedisRepository()
        self.mongo_repo = MongoRepository()
        self.neo4j_repo = Neo4jRepository()

    def _hash_password(self, password):
        return hashlib.sha256(password.encode("utf-8")).hexdigest()

    def registrar_usuario(self, user_data):
        """
        Registers a user, writes to Postgres, syncs with Neo4j and MongoDB.
        """
        # Hash password
        user_data["password_hash"] = self._hash_password(user_data["password"])
        
        # Calculate age
        edad_calc = calcular_edad(user_data["fecha_nacimiento"])
        
        # 1. Write to PostgreSQL (source of truth)
        id_usuario = self.pg_repo.crear_usuario(user_data)
        
        # 2. Write to Neo4j Graph
        try:
            self.neo4j_repo.crear_usuario_nodo(
                id_usuario=id_usuario,
                nombre=user_data["nombre"],
                edad=edad_calc,
                genero=user_data["genero"],
                ubicacion=user_data["ubicacion"]
            )
        except Exception as e:
            print(f"[SYNC ERROR] Neo4j user node creation failed: {e}")

        # 3. Denormalize to MongoDB
        try:
            f_nac = user_data["fecha_nacimiento"]
            fecha_nac_str = f_nac.strftime("%Y-%m-%d") if isinstance(f_nac, (date, datetime)) else str(f_nac)
            
            perfil_denorm = {
                "nombre": user_data["nombre"],
                "fecha_nacimiento": fecha_nac_str,
                "edad": edad_calc,
                "genero": user_data["genero"],
                "ubicacion": user_data["ubicacion"],
                "latitud": user_data.get("latitud"),
                "longitud": user_data.get("longitud"),
                "biografia": user_data.get("biografia", ""),
                "intereses": [],
                "fotos": [],
                "cantidad_fotos": 0
            }
            self.mongo_repo.upsert_perfil_publico(id_usuario, perfil_denorm)
        except Exception as e:
            print(f"[SYNC ERROR] MongoDB public profile creation failed: {e}")

        # 4. Index location in Redis
        try:
            self.redis_repo.indexar_ubicacion_usuario(
                id_usuario, 
                user_data.get("longitud"), 
                user_data.get("latitud")
            )
        except Exception as e:
            print(f"[SYNC ERROR] Redis location indexing failed: {e}")

        # 5. Log Activity in MongoDB
        try:
            self.mongo_repo.registrar_actividad(
                tipo_evento="USUARIO_REGISTRADO",
                id_usuario=id_usuario,
                detalles={"nombre": user_data["nombre"], "email": user_data["email"]}
            )
        except Exception as e:
            print(f"[SYNC ERROR] MongoDB activity log failed: {e}")

        return id_usuario

    def iniciar_sesion(self, email, password):
        """
        Validates login and returns a session token if correct.
        """
        user = self.pg_repo.obtener_usuario_por_email(email)
        if not user or not user["activo"]:
            return None
        
        password_hash = self._hash_password(password)
        if user["password_hash"] == password_hash:
            # Generate Session Token
            token = str(uuid.uuid4())
            self.redis_repo.crear_sesion(token, user["id_usuario"])
            
            # Log login activity
            try:
                self.mongo_repo.registrar_actividad("INICIO_SESION", user["id_usuario"])
            except Exception:
                pass
                
            return token, user
        return None

    def cerrar_sesion(self, token, id_usuario):
        """
        Clears session from Redis.
        """
        self.redis_repo.eliminar_sesion(token)
        try:
            self.mongo_repo.registrar_actividad("CIERRE_SESION", id_usuario)
        except Exception:
            pass

    def validar_sesion(self, token):
        """
        Validates session and returns the user dict if valid.
        """
        id_usuario = self.redis_repo.obtener_usuario_sesion(token)
        if id_usuario:
            # Check if active user exists in Postgres
            user = self.pg_repo.obtener_usuario_por_id(id_usuario)
            if user and user["activo"]:
                return user
        return None
