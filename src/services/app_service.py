import hashlib
import uuid
import logging
from datetime import datetime
from src.repositories.postgres_repo import PostgresRepository
from src.repositories.mongo_repo import MongoRepository
from src.repositories.redis_repo import RedisRepository
from src.repositories.neo4j_repo import Neo4jRepository
from src.repositories.cassandra_repo import CassandraRepository

# Set up simple logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AppService:
    def __init__(self):
        self.pg_repo = PostgresRepository()
        self.mongo_repo = MongoRepository()
        self.redis_repo = RedisRepository()
        self.neo4j_repo = Neo4jRepository()
        self.cassandra_repo = CassandraRepository()

    def _hash_password(self, password):
        """Hash password using SHA-256 for simple academic storage."""
        return hashlib.sha256(password.encode("utf-8")).hexdigest()

    def register_user(self, nombre, email, password, edad, genero, ubicacion):
        """
        Flujo de Registro de Usuario:
        1. PostgreSQL valida que el email no exista.
        2. PostgreSQL crea el usuario estructural y devuelve user_id (fuente de identidad).
        3. MongoDB consume ese user_id y crea un perfil vacío asociado (perfil flexible).
        4. MongoDB registra opcionalmente un log de creación de perfil (realizado dentro de create_profile).
        5. Neo4j consume el mismo user_id y crea el nodo Usuario (habilita relaciones sociales).
        6. Si falla MongoDB, eliminar el usuario creado en PostgreSQL (compensación manual).
        7. Si falla Neo4j, eliminar el perfil en MongoDB y el usuario en PostgreSQL (compensación manual).
        """
        # 1. PostgreSQL valida que el email no exista
        existing = self.pg_repo.get_user_by_email(email)
        if existing:
            raise ValueError(f"El email '{email}' ya se encuentra registrado en el sistema.")

        password_hash = self._hash_password(password)
        
        # 2. PostgreSQL crea el usuario estructural y devuelve user_id
        user_id = self.pg_repo.create_user(
            nombre=nombre,
            email=email,
            password_hash=password_hash,
            edad=edad,
            genero=genero,
            ubicacion=ubicacion
        )
        
        # 3. MongoDB crea el perfil vacío (y registra el log de creación)
        try:
            self.mongo_repo.create_profile(user_id)
        except Exception as e:
            logger.error(f"Fallo en MongoDB al crear perfil: {e}. Aplicando compensación manual sobre PostgreSQL.")
            # 6. Compensación manual: eliminar el usuario creado en PostgreSQL
            self.pg_repo.delete_user(user_id)
            raise RuntimeError("Registro fallido debido a error en base documental. Usuario eliminado de PostgreSQL (compensación manual).")

        # 5. Neo4j crea el nodo Usuario
        try:
            self.neo4j_repo.create_user_node(user_id, nombre)
        except Exception as e:
            logger.error(f"Fallo en Neo4j al crear nodo de usuario: {e}. Aplicando compensación manual sobre MongoDB y PostgreSQL.")
            # 7. Compensación manual: eliminar el perfil en MongoDB y el usuario en PostgreSQL
            self.mongo_repo.delete_profile(user_id)
            self.pg_repo.delete_user(user_id)
            raise RuntimeError("Registro fallido debido a error en base de grafos. Datos eliminados de MongoDB y PostgreSQL (compensación manual).")

        return user_id

    def login_user(self, email, password, ip="127.0.0.1"):
        """
        Flujo de Inicio de Sesión (Login):
        1. PostgreSQL valida existencia del usuario y contraseña.
        2. MongoDB registra SIEMPRE el intento de login (exito, email, user_id/null, timestamp, motivo).
        3. Si MongoDB falla al registrar un intento exitoso, se permite continuar con un log de advertencia.
        4. Si el login fue exitoso, Redis crea la sesión temporal (session:token -> user_id con TTL) y agrega el usuario a users:online.
        5. Si el login falló, Redis no crea la sesión.
        """
        # Fetch user from PostgreSQL
        user = self.pg_repo.get_user_by_email(email)
        
        if not user:
            # User doesn't exist
            try:
                self.mongo_repo.log_login_attempt(email=email, user_id=None, success=False, motivo="Usuario inexistente", ip=ip)
            except Exception as e:
                logger.error(f"Fallo al registrar intento fallido en MongoDB: {e}")
            return None
        
        # Check password hash
        input_hash = self._hash_password(password)
        if user["password_hash"] != input_hash:
            # Login failed - incorrect password
            try:
                self.mongo_repo.log_login_attempt(email=email, user_id=user["id"], success=False, motivo="Contraseña incorrecta", ip=ip)
            except Exception as e:
                logger.error(f"Fallo al registrar intento fallido en MongoDB: {e}")
            return None

        # Login succeeded!
        user_id = user["id"]
        
        # 2. Log success in MongoDB
        try:
            self.mongo_repo.log_login_attempt(email=email, user_id=user_id, success=True, motivo="Inicio exitoso", ip=ip)
        except Exception as e:
            # Si MongoDB falla al registrar un intento exitoso, permitimos continuar registrando un warning
            logger.warning(f"Fallo al registrar intento exitoso en MongoDB: {e}. Continuando con el inicio de sesión.")

        # 3. Create session in Redis
        token = str(uuid.uuid4())
        try:
            # Session is active for 1 hour (3600 seconds)
            self.redis_repo.create_session(token, user_id, ttl=3600)
            self.redis_repo.add_user_online(user_id)
        except Exception as e:
            logger.error(f"Redis session creation failed: {e}")
            raise RuntimeError("Fallo al iniciar sesión: servicio de sesiones no disponible.")

        return {
            "token": token,
            "user_id": user_id,
            "nombre": user["nombre"],
            "email": user["email"],
            "genero": user["genero"],
            "edad": user["edad"],
            "ubicacion": user["ubicacion"]
        }

    def logout_user(self, token):
        """
        Flow for Logout:
        1. Redis deletes session.
        2. Redis removes user from online set.
        """
        user_id = self.redis_repo.get_user_id_by_token(token)
        if user_id is None:
            return False
        
        try:
            self.redis_repo.delete_session(token)
            self.redis_repo.remove_user_online(user_id)
            return True
        except Exception as e:
            logger.error(f"Redis session deletion failed: {e}")
            raise RuntimeError("Logout failed: session service error.")
            
    def get_current_user_id(self, token):
        """Retrieve the user_id of the active session token."""
        return self.redis_repo.get_user_id_by_token(token)

    def get_user_profile(self, token):
        """Get the profile document of the currently logged-in user, merging PG and Neo4j data."""
        user_id = self.get_current_user_id(token)
        if user_id is None:
            raise PermissionError("Sesión inválida o expirada.")
        
        profile = self.mongo_repo.get_profile(user_id)
        if not profile:
            profile = {}
        
        # Add basic user structural data from Postgres
        user_info = self.pg_repo.get_user_by_id(user_id)
        if user_info:
            profile["nombre"] = user_info["nombre"]
            profile["edad"] = user_info["edad"]
            profile["genero"] = user_info["genero"]
            profile["ubicacion"] = user_info["ubicacion"]
            
        # Add interests from Neo4j
        try:
            query = "MATCH (u:Usuario {id: $user_id})-[:TIENE_INTERES]->(i:Interes) RETURN i.nombre AS interes"
            with self.neo4j_repo.driver.session() as session:
                res = session.run(query, user_id=user_id)
                profile["intereses"] = [row["interes"] for row in res]
        except Exception as e:
            logger.error(f"Failed to fetch user interests from Neo4j: {e}")
            profile["intereses"] = []
            
        return profile

    def update_profile(self, token, biografia, caracteristicas, preferencias, intereses):
        """
        Flujo de Actualización de Perfil:
        1. Redis valida el token de sesión y devuelve el user_id.
        2. MongoDB actualiza el perfil extendido (biografia, preferencias, caracteristicas, intereses).
        3. MongoDB registra el historial de cambios en historial_cambios_perfil.
        4. Neo4j actualiza las relaciones de intereses (Usuario)-[:TIENE_INTERES]->(Interes).
        5. Si Neo4j falla, se registra un warning de consistencia eventual sin aplicar rollback complejo.
        """
        # 1. Redis valida sesión y devuelve user_id
        user_id = self.get_current_user_id(token)
        if user_id is None:
            raise PermissionError("Sesión inválida o expirada.")
        
        # 2. MongoDB actualiza el perfil extendido e historial de cambios
        self.mongo_repo.update_profile_fields(
            user_id=user_id,
            biografia=biografia,
            caracteristicas=caracteristicas,
            preferencias=preferencias,
            intereses=intereses
        )
        
        # 3. Neo4j actualiza las relaciones de intereses
        try:
            self.neo4j_repo.update_interests(user_id, intereses)
        except Exception as e:
            # Registrar warning y continuar asumiendo consistencia eventual
            logger.warning(f"No se pudieron actualizar los intereses en Neo4j: {e}. Consistencia eventual asumida.")
            
        # 4. PostgreSQL: Sincronizar campos principales de perfil e intereses
        try:
            pref_edad_min = preferencias.get('edad_min', 18)
            pref_edad_max = preferencias.get('edad_max', 99)
            self.pg_repo.update_user_profile_fields(user_id, biografia, pref_edad_min, pref_edad_max)
            self.pg_repo.update_user_interests(user_id, intereses)
        except Exception as e:
            logger.warning(f"No se pudo sincronizar perfil/intereses en PostgreSQL: {e}.")

    def add_user_photo(self, token, photo_url):
        """
        Flow for Adding a Photo:
        1. Redis validates session.
        2. MongoDB appends photo and logs change.
        """
        user_id = self.get_current_user_id(token)
        if user_id is None:
            raise PermissionError("Sesión inválida o expirada.")
        
        self.mongo_repo.add_photo(user_id, photo_url)
        
        # Sincronizar foto en PostgreSQL
        try:
            self.pg_repo.add_photo(user_id, photo_url)
        except Exception as e:
            logger.warning(f"No se pudo sincronizar foto en PostgreSQL: {e}")

    def get_next_candidate(self, token):
        """
        Flujo de Búsqueda de Perfiles y Candidatos Recomendados:
        1. La CLI llama a AppService.get_next_candidate().
        2. Redis valida sesión activa y obtiene user_id.
        3. Redis revisa si existe la lista candidates:{user_id}.
        4. Si existe, obtiene el siguiente candidate_id con LPOP.
        5. Si no existe (Cache Miss):
           - MongoDB obtiene las preferencias del usuario (preferencias de edad y género).
           - Neo4j obtiene usuarios excluidos (ya likeados, descartados, bloqueados en ambos sentidos y con match existente).
           - PostgreSQL filtra candidatos por edad, género y ubicación.
             * Justificación: Edad, género y ubicación se filtran desde PostgreSQL por tratarse de datos operacionales estructurales
               de la identidad del usuario, donde la consistencia y validez de tipo son críticas.
           - Neo4j ordena o prioriza candidatos por cantidad de intereses comunes.
           - Redis guarda la lista candidates:{user_id} con un TTL (300 segundos).
        6. MongoDB obtiene el perfil completo del candidato final (para visualización flexible de biografía, fotos y características).
        7. La CLI muestra el perfil.
        """
        user_id = self.get_current_user_id(token)
        if user_id is None:
            raise PermissionError("Sesión inválida o expirada.")
        
        # Check Redis cache
        cached_count = self.redis_repo.get_candidates_count(user_id)
        if cached_count == 0:
            logger.info(f"Cache miss for candidates of user {user_id}. Generating list...")
            # 1. Get current preferences from MongoDB
            profile = self.mongo_repo.get_profile(user_id)
            prefs = profile.get("preferencias", {})
            edad_min = prefs.get("edad_min", 18)
            edad_max = prefs.get("edad_max", 99)
            genero_interes = prefs.get("genero_interes", "Cualquiera")
            
            # 2. Get exclusions from Neo4j
            exclude_ids = self.neo4j_repo.get_excluded_user_ids(user_id)
            
            # 3. Query Postgres for compatible users
            compatible_ids = self.pg_repo.get_users_by_filter(
                exclude_ids=exclude_ids,
                gender_interest=genero_interes,
                edad_min=edad_min,
                edad_max=edad_max,
                current_user_id=user_id
            )
            
            # 4. Sort compatible IDs by shared interests in Neo4j
            sorted_ids = self.neo4j_repo.sort_candidates_by_interests(user_id, compatible_ids)
            
            # 5. Push to Redis list with 300s TTL
            self.redis_repo.push_candidates(user_id, sorted_ids, ttl=300)
            
        # Pop next candidate
        candidate_id = self.redis_repo.pop_candidate(user_id)
        if not candidate_id:
            return None
            
        # Get details
        candidate_pg = self.pg_repo.get_user_by_id(candidate_id)
        candidate_mongo = self.mongo_repo.get_profile(candidate_id)
        
        # Get shared interests names from Neo4j
        shared_interests = self.get_shared_interests(user_id, candidate_id)
        
        return {
            "user_id": candidate_id,
            "nombre": candidate_pg["nombre"] if candidate_pg else "Usuario Desconocido",
            "edad": candidate_pg["edad"] if candidate_pg else 0,
            "genero": candidate_pg["genero"] if candidate_pg else "Desconocido",
            "ubicacion": candidate_pg["ubicacion"] if candidate_pg else "Desconocido",
            "biografia": candidate_mongo.get("biografia", "") if candidate_mongo else "",
            "fotos": candidate_mongo.get("fotos", []) if candidate_mongo else [],
            "caracteristicas": candidate_mongo.get("caracteristicas", {}) if candidate_mongo else {},
            "intereses_comunes": shared_interests
        }

    def get_shared_interests(self, current_id, other_id):
        """Retrieve shared interest names between two users from Neo4j."""
        query = """
        MATCH (u1:Usuario {id: $current_id})-[r1:TIENE_INTERES]->(i:Interes)<-[r2:TIENE_INTERES]-(u2:Usuario {id: $other_id})
        RETURN i.nombre AS interes
        """
        driver = self.neo4j_repo.driver
        with driver.session() as session:
            res = session.run(query, current_id=current_id, other_id=other_id)
            return [row["interes"] for row in res]

    def hacer_swipe(self, token, user_to_id, positive):
        """
        Orquestación de Swipe y Match con Consistencia Eventual:
        1. La CLI llama a AppService.hacer_swipe().
        2. Redis valida sesión activa y obtiene user_from_id.
        
        CASO 1: Dislike
        3. Neo4j registra relación DESCARTO para evitar volver a mostrar ese perfil.
        4. Cassandra registra el evento histórico del swipe con tipo = dislike.
           - Si Cassandra falla, se informa un warning, pero la operación principal continúa.
        5. CLI informa que el perfil fue descartado.

        CASO 2: Like sin match
        3. Neo4j crea la relación (Usuario)-[:LE_DIO_LIKE]->(Usuario).
        4. Cassandra registra el evento histórico del swipe con tipo = like.
           - Si Cassandra falla, se informa un warning, pero la operación principal continúa.
        5. Neo4j verifica reciprocidad. Si no existe, se retorna para informar "like registrado".

        CASO 3: Like con match
        3. Neo4j crea relación LE_DIO_LIKE y Cassandra registra el swipe histórico.
        4. Neo4j verifica reciprocidad.
        5. Si hay reciprocidad:
           - PostgreSQL crea la coincidencia oficial (normalizando el orden de user_id_1 y user_id_2) y devuelve match_id.
           - Cassandra registra el match en matches_por_dia (warning si falla, pero continúa).
           - Neo4j crea la relación MATCH_CON bidireccional y limpia los likes (warning si falla, consistencia eventual).
           - MongoDB crea la notificación persistente para ambos (si falla, no se revierte el match).
        6. CLI informa "nuevo match generado".
        """
        user_from_id = self.get_current_user_id(token)
        if user_from_id is None:
            raise PermissionError("Sesión inválida o expirada.")

        tipo = "like" if positive else "dislike"
        is_match = False
        match_id = None

        if positive:
            # 1b. Sincronizar Like en PostgreSQL
            try:
                self.pg_repo.create_like(user_from_id, user_to_id, tipo="like")
            except Exception as e:
                logger.warning(f"No se pudo sincronizar like en PostgreSQL: {e}")

            # 2. Neo4j create like relation
            self.neo4j_repo.create_like(user_from_id, user_to_id)
            
            # 3. Cassandra log swipe
            try:
                self.cassandra_repo.register_swipe(user_from_id, user_to_id, tipo)
            except Exception as e:
                logger.warning(f"Advertencia: No se pudo registrar el swipe en Cassandra: {e}. La operación principal continuará.")

            # 4. Check reciprocity
            reciprocal = self.neo4j_repo.check_reciprocity(user_from_id, user_to_id)
            
            if reciprocal:
                is_match = True
                # 5a. PG registers match
                try:
                    match_id = self.pg_repo.create_match(user_from_id, user_to_id)
                except Exception as e:
                    logger.error(f"PostgreSQL match registration failed: {e}. Executing Neo4j rollback.")
                    # Rollback Neo4j like
                    self.neo4j_repo.delete_like(user_from_id, user_to_id)
                    raise RuntimeError(f"No se pudo registrar el match en base relacional: {e}")

                # 5b. Cassandra log match
                try:
                    self.cassandra_repo.register_match(match_id, user_from_id, user_to_id)
                except Exception as e:
                    logger.warning(f"Advertencia: No se pudo registrar el match en Cassandra: {e}. La operación principal continuará.")

                # 5c. Neo4j MATCH_CON upgrade
                try:
                    self.neo4j_repo.create_match_relations(user_from_id, user_to_id)
                except Exception as e:
                    logger.warning(f"Advertencia: No se pudieron actualizar las relaciones en Neo4j: {e}. Consistencia eventual asumida.")

                # 5d. MongoDB notification
                try:
                    u_from = self.pg_repo.get_user_by_id(user_from_id)
                    u_to = self.pg_repo.get_user_by_id(user_to_id)
                    name_from = u_from["nombre"] if u_from else "Alguien"
                    name_to = u_to["nombre"] if u_to else "Alguien"
                    
                    self.mongo_repo.create_notification(
                        user_id=user_from_id,
                        message=f"¡Tienes un nuevo match con {name_to}!",
                        notification_type="match"
                    )
                    self.mongo_repo.create_notification(
                        user_id=user_to_id,
                        message=f"¡Tienes un nuevo match con {name_from}!",
                        notification_type="match"
                    )
                    
                    # 5e. Sincronizar notificación en PostgreSQL
                    try:
                        self.pg_repo.create_notification(user_from_id, "match", id_coincidencia=match_id)
                        self.pg_repo.create_notification(user_to_id, "match", id_coincidencia=match_id)
                    except Exception as e:
                        logger.warning(f"No se pudo sincronizar notificaciones de match en PostgreSQL: {e}")
                        
                except Exception as e:
                    logger.warning(f"Advertencia: No se pudieron crear las notificaciones en MongoDB: {e}. No se revierte el match.")
        else:
            # Dislike flow
            # 1b. Sincronizar Dislike en PostgreSQL
            try:
                self.pg_repo.create_like(user_from_id, user_to_id, tipo="dislike")
            except Exception as e:
                logger.warning(f"No se pudo sincronizar dislike en PostgreSQL: {e}")

            # 2. Neo4j create dislike relation (to exclude from search)
            self.neo4j_repo.create_dislike(user_from_id, user_to_id)
            
            # 3. Cassandra log swipe
            try:
                self.cassandra_repo.register_swipe(user_from_id, user_to_id, tipo)
            except Exception as e:
                logger.warning(f"Advertencia: No se pudo registrar el swipe en Cassandra: {e}. La operación principal continuará.")

        return {
            "match": is_match,
            "match_id": match_id
        }

    def obtener_mis_matches(self, token):
        """Retrieve all confirmed matches for the logged-in user with details."""
        user_id = self.get_current_user_id(token)
        if user_id is None:
            raise PermissionError("Sesión inválida o expirada.")

        matches = self.pg_repo.get_user_matches(user_id)
        results = []
        for m in matches:
            # Determine the other user's ID
            other_id = m["user_id_2"] if m["user_id_1"] == user_id else m["user_id_1"]
            other_pg = self.pg_repo.get_user_by_id(other_id)
            results.append({
                "match_id": m["id"],
                "user_id": other_id,
                "nombre": other_pg["nombre"] if other_pg else "Usuario Desconocido",
                "fecha_match": m["created_at"]
            })
        return results

    def enviar_mensaje(self, token, match_id, texto):
        """
        Flujo de Envío de Mensaje:
        1. CLI llama a AppService.enviar_mensaje().
        2. Redis valida sesión activa y devuelve sender_id.
        3. PostgreSQL verifica que exista una coincidencia confirmada entre sender_id y receiver_id.
        4. PostgreSQL devuelve match_id.
        5. Cassandra guarda el mensaje en mensajes_por_conversacion usando match_id como clave de partición.
        6. MongoDB crea notificación para el receptor.
           - Si MongoDB falla al notificar, no se revierte el mensaje (se emite una advertencia).
        7. CLI informa “mensaje enviado”.
        """
        # 2. Redis valida sesión activa y devuelve sender_id
        sender_id = self.get_current_user_id(token)
        if sender_id is None:
            raise PermissionError("Sesión inválida o expirada.")

        # 3. PostgreSQL verifica que exista una coincidencia confirmada
        # Obtenemos los matches del usuario para verificar la existencia del match_id
        matches = self.pg_repo.get_user_matches(sender_id)
        current_match = next((m for m in matches if m["id"] == match_id), None)
        if not current_match:
            raise PermissionError("No existe una coincidencia confirmada en PostgreSQL para este chat.")

        # 4. PostgreSQL devuelve match_id (confirmado por la existencia de match_id e id de participante)
        receiver_id = current_match["user_id_2"] if current_match["user_id_1"] == sender_id else current_match["user_id_1"]

        # 5. Cassandra guarda el mensaje
        self.cassandra_repo.send_message(match_id, sender_id, texto)
        
        # 5b. Sincronizar mensaje en PostgreSQL
        msg_id = None
        try:
            msg_id = self.pg_repo.create_message(match_id, sender_id, texto)
        except Exception as e:
            logger.warning(f"No se pudo sincronizar mensaje en PostgreSQL: {e}")

        # 6. MongoDB crea notificación para el receptor
        try:
            sender_pg = self.pg_repo.get_user_by_id(sender_id)
            sender_name = sender_pg["nombre"] if sender_pg else "Alguien"
            snippet = texto[:30] + "..." if len(texto) > 30 else texto
            msg = f"Nuevo mensaje de {sender_name}: '{snippet}'"
            self.mongo_repo.create_notification(receiver_id, msg, "mensaje")
            
            # Sincronizar notificación en PostgreSQL
            try:
                self.pg_repo.create_notification(receiver_id, "mensaje", id_mensaje=msg_id)
            except Exception as e:
                logger.warning(f"No se pudo sincronizar notificación de mensaje en PostgreSQL: {e}")
                
        except Exception as e:
            logger.warning(f"Advertencia: No se pudo crear la notificación de mensaje en MongoDB: {e}. Se continúa.")

    def ver_conversacion(self, token, match_id):
        """
        Flujo de Consulta de Conversación:
        1. CLI llama a AppService.ver_conversacion().
        2. Redis valida sesión activa y devuelve user_id.
        3. PostgreSQL verifica que el usuario pertenece al match_id solicitado.
        4. Cassandra consulta mensajes_por_conversacion por match_id, ordenados cronológicamente.
        5. CLI muestra el historial.
        """
        # 2. Redis valida sesión activa y devuelve user_id
        user_id = self.get_current_user_id(token)
        if user_id is None:
            raise PermissionError("Sesión inválida o expirada.")

        # 3. PostgreSQL verifica que el usuario pertenece al match_id solicitado
        matches = self.pg_repo.get_user_matches(user_id)
        current_match = next((m for m in matches if m["id"] == match_id), None)
        if not current_match:
            raise PermissionError("El usuario no pertenece al match especificado o no existe en PostgreSQL.")

        # 4. Cassandra consulta mensajes_por_conversacion por match_id (ordenados cronológicamente por clustering order)
        msgs = self.cassandra_repo.get_messages(match_id)
        
        # Combinar con nombres de usuarios para presentación en CLI
        u1_name = self.pg_repo.get_user_by_id(current_match["user_id_1"])["nombre"]
        u2_name = self.pg_repo.get_user_by_id(current_match["user_id_2"])["nombre"]
        names = {
            current_match["user_id_1"]: u1_name,
            current_match["user_id_2"]: u2_name
        }

        for m in msgs:
            m["sender_nombre"] = names.get(m["sender_id"], "Desconocido")
        return msgs

    def obtener_mensajes(self, token, match_id):
        """Alias para ver_conversacion que mantiene compatibilidad de tests."""
        return self.ver_conversacion(token, match_id)

    def bloquear_usuario(self, token, bloqueado_id):
        """
        Flow for Blocking a User:
        1. Redis validates session active.
        2. Neo4j creates relationship BLOQUEO and removes likes/matches.
        3. PostgreSQL registers block audit log and removes the official match, if any.
        4. MongoDB registers log event.
        """
        bloqueador_id = self.get_current_user_id(token)
        if bloqueador_id is None:
            raise PermissionError("Sesión inválida o expirada.")

        if bloqueador_id == bloqueado_id:
            raise ValueError("No puedes bloquearte a ti mismo.")

        # 2. Neo4j block and delete links
        self.neo4j_repo.create_block(bloqueador_id, bloqueado_id)

        # 3. PostgreSQL audit and official match removal
        try:
            deleted_match_id = self.pg_repo.register_block_and_delete_match(bloqueador_id, bloqueado_id)
        except Exception as e:
            logger.error(f"PostgreSQL block registration failed: {e}.")
            raise RuntimeError("No se pudo registrar el bloqueo en PostgreSQL. La operacion quedo incompleta y requiere revision.")

        # 4. MongoDB log event
        try:
            self.mongo_repo.db.bloqueos.insert_one({
                "bloqueador_id": bloqueador_id,
                "bloqueado_id": bloqueado_id,
                "match_eliminado_id": deleted_match_id,
                "timestamp": datetime.utcnow()
            })
        except Exception as e:
            logger.error(f"MongoDB block logging failed: {e}. Proceeding.")

        return {
            "bloqueador_id": bloqueador_id,
            "bloqueado_id": bloqueado_id,
            "match_eliminado_id": deleted_match_id
        }

    def crear_evento(self, token, titulo, descripcion, ubicacion, fecha_hora_str):
        """
        Flujo de Creación de Evento (Caso 1):
        1. CLI llama a AppService.crear_evento().
        2. Redis valida sesión activa y devuelve organizador_id.
        3. PostgreSQL crea el evento oficial: nombre, descripción, fecha, ubicación, organizador_id.
        4. PostgreSQL devuelve evento_id.
        5. Neo4j crea nodo: (Evento {id: evento_id, nombre: nombre}).
        6. Neo4j crea relación: (Usuario)-[:ORGANIZA]->(Evento).
           - Si Neo4j falla, se aplica compensación simple eliminando el evento en PostgreSQL.
        7. MongoDB registra notificación o log documental (se captura error sin revertir).
        8. CLI informa evento creado.
        """
        # 2. Redis valida sesión activa y devuelve organizador_id
        organizador_id = self.get_current_user_id(token)
        if organizador_id is None:
            raise PermissionError("Sesión inválida o expirada.")

        # Parse date
        try:
            fecha_hora = datetime.fromisoformat(fecha_hora_str)
        except ValueError:
            raise ValueError("Formato de fecha inválido. Utilice el formato ISO: AAAA-MM-DD HH:MM.")

        # 3. PostgreSQL crea el evento oficial
        # 4. PostgreSQL devuelve evento_id
        event_id = self.pg_repo.create_event(organizador_id, titulo, descripcion, ubicacion, fecha_hora)

        # 5. Neo4j crea nodo e 6. Neo4j crea relación ORGANIZA
        try:
            self.neo4j_repo.create_event_node(event_id, titulo)
            self.neo4j_repo.create_organizer_relation(organizador_id, event_id)
        except Exception as e:
            logger.error(f"Fallo en Neo4j al crear relaciones de evento: {e}. Aplicando compensación simple sobre PostgreSQL.")
            # Compensación: eliminar evento de PostgreSQL
            self.pg_repo.delete_event(event_id)
            raise RuntimeError("Creación de evento fallida debido a error en base de grafos. Evento revertido en PostgreSQL.")

        # 7. MongoDB registra log y crea notificaciones
        try:
            self.mongo_repo.db.eventos_logs.insert_one({
                "evento_id": event_id,
                "organizador_id": organizador_id,
                "titulo": titulo,
                "accion": "creacion",
                "timestamp": datetime.utcnow()
            })
            
            # Notificaciones en MongoDB (tolerancia a fallos)
            all_ids = self.pg_repo.get_all_user_ids_except(organizador_id)
            for uid in all_ids:
                self.mongo_repo.create_notification(uid, f"Nuevo evento disponible: '{titulo}'", "evento")
                
                # Sincronizar notificación en PostgreSQL
                try:
                    self.pg_repo.create_notification(uid, "evento", id_evento=event_id)
                except Exception as e:
                    logger.warning(f"No se pudo sincronizar notificación de evento en PostgreSQL: {e}")
                    
        except Exception as e:
            logger.warning(f"Advertencia: No se pudo registrar el log/notificación en MongoDB: {e}. Se continúa.")

        return event_id

    def obtener_eventos(self, token):
        """
        Flujo de Visualización de Eventos (Opción Mejorada):
        1. Redis valida sesión.
        2. PostgreSQL lista eventos futuros.
        3. Neo4j prioriza eventos donde haya asistentes con intereses comunes.
        4. CLI muestra eventos recomendados.
        """
        # 1. Redis valida sesión
        user_id = self.get_current_user_id(token)
        if user_id is None:
            raise PermissionError("Sesión inválida o expirada.")
            
        # 2. PostgreSQL lista eventos futuros
        events = self.pg_repo.get_events()
        if not events:
            return []
            
        # 3. Neo4j prioriza eventos según compatibilidad de intereses con asistentes
        try:
            event_ids = [e["id"] for e in events]
            prioritized_ids = self.neo4j_repo.prioritize_events_by_interests(user_id, event_ids)
            
            # Reordenar los eventos respetando el ranking de Neo4j
            events_map = {e["id"]: e for e in events}
            reordered_events = []
            seen_ids = set()
            for eid in prioritized_ids:
                if eid in events_map:
                    reordered_events.append(events_map[eid])
                    seen_ids.add(eid)
            # Agregar al final cualquier evento no rankeado
            for e in events:
                if e["id"] not in seen_ids:
                    reordered_events.append(e)
            return reordered_events
        except Exception as e:
            logger.warning(f"Advertencia: No se pudieron priorizar los eventos en Neo4j: {e}. Se retorna el orden por defecto.")
            return events

    def inscribirse_evento(self, token, event_id):
        """
        Flujo de Inscripción a Evento (Caso 2):
        1. CLI llama a AppService.inscribirse_evento().
        2. Redis valida sesión activa y devuelve user_id.
        3. PostgreSQL verifica que el evento exista.
        4. PostgreSQL registra asistencia_eventos con clave única user_id + evento_id.
        5. Neo4j crea relación: (Usuario)-[:ASISTE_A]->(Evento).
           - Decisión de Fallo: Si Neo4j falla al registrar la arista, se acepta consistencia eventual.
             Justificación: PostgreSQL es la fuente de verdad definitiva y legal del registro/asistencia al evento.
             Un fallo transitorio en el grafo de recomendaciones no debe anular la inscripción oficial del usuario.
        6. MongoDB notifica al organizador o registra log (consistencia eventual).
        7. CLI informa inscripción confirmada.
        """
        # 2. Redis valida sesión activa y devuelve user_id
        user_id = self.get_current_user_id(token)
        if user_id is None:
            raise PermissionError("Sesión inválida o expirada.")

        # 3. PostgreSQL verifica que el evento exista
        event = self.pg_repo.get_event_by_id(event_id)
        if not event:
            raise ValueError("El evento especificado no existe en PostgreSQL.")
            
        organizador_id = event["organizador_id"]

        # 4. PostgreSQL registra asistencia_eventos (la clave única/primaria de la tabla valida la no duplicación)
        self.pg_repo.register_attendance(user_id, event_id)

        # 5. Neo4j crea relación ASISTE_A (consistencia eventual con advertencia)
        try:
            self.neo4j_repo.create_attendance_relation(user_id, event_id)
        except Exception as e:
            logger.warning(f"Advertencia: No se pudo registrar la relación de asistencia en Neo4j: {e}. Consistencia eventual asumida.")

        # 6. MongoDB notifica al organizador (consistencia eventual)
        try:
            user_pg = self.pg_repo.get_user_by_id(user_id)
            user_name = user_pg["nombre"] if user_pg else "Alguien"
            msg = f"{user_name} se inscribió a tu evento: '{event['titulo']}'"
            self.mongo_repo.create_notification(organizador_id, msg, "evento_asistencia")
            
            # Sincronizar notificación en PostgreSQL
            try:
                self.pg_repo.create_notification(organizador_id, "evento_asistencia", id_evento=event_id)
            except Exception as e:
                logger.warning(f"No se pudo sincronizar notificación de inscripción a evento en PostgreSQL: {e}")
                
        except Exception as e:
            logger.warning(f"Advertencia: No se pudo crear la notificación de inscripción en MongoDB: {e}. Se continúa.")
