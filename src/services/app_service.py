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
        Flow for Registering a User:
        1. PG creates user.
        2. MongoDB creates empty profile document.
        3. Neo4j creates node.
        If MongoDB or Neo4j fails, compensation rollback is applied.
        """
        password_hash = self._hash_password(password)
        
        # 1. PostgreSQL creates user
        user_id = self.pg_repo.create_user(
            nombre=nombre,
            email=email,
            password_hash=password_hash,
            edad=edad,
            genero=genero,
            ubicacion=ubicacion
        )
        
        # 2. MongoDB creates profile document
        try:
            self.mongo_repo.create_profile(user_id)
        except Exception as e:
            logger.error(f"MongoDB profile creation failed: {e}. Executing Postgres rollback.")
            # Rollback PostgreSQL
            self.pg_repo.delete_user(user_id)
            raise RuntimeError(f"Registration failed: profile database error. PostgreSQL user rolled back.")

        # 3. Neo4j creates node
        try:
            self.neo4j_repo.create_user_node(user_id, nombre)
        except Exception as e:
            logger.error(f"Neo4j node creation failed: {e}. Executing MongoDB and Postgres rollback.")
            # Rollback MongoDB & PostgreSQL
            self.mongo_repo.delete_profile(user_id)
            self.pg_repo.delete_user(user_id)
            raise RuntimeError(f"Registration failed: graph database error. Databases rolled back.")

        return user_id

    def login_user(self, email, password, ip="127.0.0.1"):
        """
        Flow for Login:
        1. PostgreSQL validates credentials.
        2. MongoDB logs attempt.
        3. Redis creates session TTL and adds user to online set if successful.
        """
        # Fetch user
        user = self.pg_repo.get_user_by_email(email)
        
        if not user:
            # User doesn't exist, we don't have a user_id to log in MongoDB but we can log with -1
            self.mongo_repo.log_login_attempt(user_id=-1, success=False, ip=ip)
            return None
        
        # Check password hash
        input_hash = self._hash_password(password)
        if user["password_hash"] != input_hash:
            # Login failed
            self.mongo_repo.log_login_attempt(user_id=user["id"], success=False, ip=ip)
            return None

        # Login succeeded!
        user_id = user["id"]
        
        # 1. Log success in MongoDB
        try:
            self.mongo_repo.log_login_attempt(user_id=user_id, success=True, ip=ip)
        except Exception as e:
            logger.warning(f"Failed to log login success in MongoDB: {e}. Proceeding anyway.")

        # 2. Create session in Redis
        token = str(uuid.uuid4())
        try:
            # Session is active for 1 hour (3600 seconds)
            self.redis_repo.create_session(token, user_id, ttl=3600)
            self.redis_repo.add_user_online(user_id)
        except Exception as e:
            logger.error(f"Redis session creation failed: {e}")
            raise RuntimeError(f"Login failed: session service unavailable.")

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
        Flow for Updating Profile:
        1. Redis validates session.
        2. MongoDB updates profile and registers log.
        3. Neo4j updates interests.
        """
        user_id = self.get_current_user_id(token)
        if user_id is None:
            raise PermissionError("Sesión inválida o expirada.")
        
        # 1. MongoDB update
        self.mongo_repo.update_profile_fields(
            user_id=user_id,
            biografia=biografia,
            caracteristicas=caracteristicas,
            preferencias=preferencias
        )
        
        # 2. Neo4j update
        try:
            self.neo4j_repo.update_interests(user_id, intereses)
        except Exception as e:
            logger.error(f"Failed to update interests in Neo4j: {e}. Eventual consistency expected.")
            # We don't rollback MongoDB for this since it is a secondary relationship update, but we log the error.
            raise RuntimeError(f"Perfil guardado, pero hubo un problema al actualizar los intereses: {e}")

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

    def get_next_candidate(self, token):
        """
        Flow for Retrieving the Next Compatible Candidate:
        1. Redis validates session.
        2. Redis checks cached candidate IDs list.
        3. If cache miss, generate candidates:
            a. MongoDB gets preferences.
            b. Neo4j gets excluded IDs (likes, matches, blocks).
            c. PostgreSQL filters structural users matching preferences and excluding IDs.
            d. Neo4j sorts IDs by common interests.
            e. Redis saves IDs list with TTL.
        4. Pops next candidate ID from Redis.
        5. Merges structural (Postgres) and profile (MongoDB) details of candidate.
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
        Flow for Swiping:
        1. Redis validates session active and gets user_from_id.
        2. Neo4j registers Like or Dislike relation.
        3. Cassandra logs swipe event (tipo="like" or "dislike").
        4. Neo4j checks reciprocity (only if positive).
        5. If reciprocity (Match):
            a. PostgreSQL registers match and returns match_id.
            b. Cassandra logs match in matches_por_dia.
            c. Neo4j upgrades to MATCH_CON bilateral relations and cleans up likes.
            d. MongoDB generates notifications for both users.
        """
        user_from_id = self.get_current_user_id(token)
        if user_from_id is None:
            raise PermissionError("Sesión inválida o expirada.")

        # Always delete the user_to_id from candidates queue in Redis cache
        # (in case it wasn't popped by get_next_candidate, or to ensure clean cache)
        # (Though pop already removed it, doing this is safe)
        
        tipo = "like" if positive else "dislike"
        is_match = False
        match_id = None

        if positive:
            # 2. Neo4j create like relation
            self.neo4j_repo.create_like(user_from_id, user_to_id)
            
            # 3. Cassandra log swipe
            try:
                self.cassandra_repo.register_swipe(user_from_id, user_to_id, tipo)
            except Exception as e:
                logger.error(f"Failed to log swipe in Cassandra: {e}. Eventual consistency expected.")

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
                    logger.error(f"Cassandra match logging failed: {e}. Proceeding.")

                # 5c. Neo4j MATCH_CON upgrade
                try:
                    self.neo4j_repo.create_match_relations(user_from_id, user_to_id)
                except Exception as e:
                    logger.error(f"Neo4j MATCH_CON upgrade failed: {e}. Proceeding.")

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
                except Exception as e:
                    logger.error(f"MongoDB notification creation failed: {e}. Proceeding.")
        else:
            # Dislike flow
            # 2. Neo4j create dislike relation (to exclude from search)
            self.neo4j_repo.create_dislike(user_from_id, user_to_id)
            
            # 3. Cassandra log swipe
            try:
                self.cassandra_repo.register_swipe(user_from_id, user_to_id, tipo)
            except Exception as e:
                logger.error(f"Failed to log swipe in Cassandra: {e}. Eventual consistency expected.")

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
        Flow for Sending a Message:
        1. Redis validates session.
        2. PostgreSQL verifies that match exists and user is a participant.
        3. Cassandra stores the message chronologically.
        4. MongoDB generates a notification for the recipient.
        """
        sender_id = self.get_current_user_id(token)
        if sender_id is None:
            raise PermissionError("Sesión inválida o expirada.")

        # 2. PostgreSQL check match
        # Fetch user's matches and find the corresponding match_id
        matches = self.pg_repo.get_user_matches(sender_id)
        current_match = next((m for m in matches if m["id"] == match_id), None)
        if not current_match:
            raise PermissionError("No tienes un match activo con ese ID para enviar mensajes.")

        # 3. Cassandra save message
        self.cassandra_repo.send_message(match_id, sender_id, texto)

        # 4. MongoDB notify recipient
        try:
            receiver_id = current_match["user_id_2"] if current_match["user_id_1"] == sender_id else current_match["user_id_1"]
            sender_pg = self.pg_repo.get_user_by_id(sender_id)
            sender_name = sender_pg["nombre"] if sender_pg else "Alguien"
            
            # Message snippet for notification
            snippet = texto[:30] + "..." if len(texto) > 30 else texto
            msg = f"Nuevo mensaje de {sender_name}: '{snippet}'"
            self.mongo_repo.create_notification(receiver_id, msg, "mensaje")
        except Exception as e:
            logger.error(f"Failed to create message notification in MongoDB: {e}. Proceeding.")

    def obtener_mensajes(self, token, match_id):
        """
        Flow for Retrieving Messages:
        1. Redis validates session.
        2. PostgreSQL verifies match.
        3. Cassandra retrieves messages.
        """
        user_id = self.get_current_user_id(token)
        if user_id is None:
            raise PermissionError("Sesión inválida o expirada.")

        # 2. PostgreSQL check
        matches = self.pg_repo.get_user_matches(user_id)
        current_match = next((m for m in matches if m["id"] == match_id), None)
        if not current_match:
            raise PermissionError("No tienes acceso a este historial de conversación.")

        # 3. Cassandra query
        msgs = self.cassandra_repo.get_messages(match_id)
        
        # Merge with user names for friendly presentation
        u1_name = self.pg_repo.get_user_by_id(current_match["user_id_1"])["nombre"]
        u2_name = self.pg_repo.get_user_by_id(current_match["user_id_2"])["nombre"]
        names = {
            current_match["user_id_1"]: u1_name,
            current_match["user_id_2"]: u2_name
        }

        for m in msgs:
            m["sender_nombre"] = names.get(m["sender_id"], "Desconocido")
        return msgs

    def bloquear_usuario(self, token, bloqueado_id):
        """
        Flow for Blocking a User:
        1. Redis validates session active.
        2. Neo4j creates relationship BLOQUEO and removes likes/matches.
        3. PostgreSQL registers block audit log.
        4. MongoDB registers log event.
        """
        bloqueador_id = self.get_current_user_id(token)
        if bloqueador_id is None:
            raise PermissionError("Sesión inválida o expirada.")

        # 2. Neo4j block and delete links
        self.neo4j_repo.create_block(bloqueador_id, bloqueado_id)

        # 3. PostgreSQL audit
        try:
            self.pg_repo.create_block_audit(bloqueador_id, bloqueado_id)
        except Exception as e:
            logger.error(f"PostgreSQL block audit failed: {e}. Proceeding.")

        # 4. MongoDB log event
        try:
            self.mongo_repo.db.bloqueos.insert_one({
                "bloqueador_id": bloqueador_id,
                "bloqueado_id": bloqueado_id,
                "timestamp": datetime.utcnow()
            })
        except Exception as e:
            logger.error(f"MongoDB block logging failed: {e}. Proceeding.")

    def crear_evento(self, token, titulo, descripcion, ubicacion, fecha_hora_str):
        """
        Flow for Creating an Event:
        1. Redis validates session active.
        2. PostgreSQL creates event in events table.
        3. Neo4j creates Evento node and ORGANIZA relation.
        4. MongoDB logs event creation.
        """
        organizador_id = self.get_current_user_id(token)
        if organizador_id is None:
            raise PermissionError("Sesión inválida o expirada.")

        # Parse date
        try:
            fecha_hora = datetime.fromisoformat(fecha_hora_str)
        except ValueError:
            raise ValueError("Formato de fecha inválido. Utilice el formato ISO: AAAA-MM-DD HH:MM.")

        # 2. PostgreSQL create
        event_id = self.pg_repo.create_event(organizador_id, titulo, descripcion, ubicacion, fecha_hora)

        # 3. Neo4j create node and relation
        try:
            self.neo4j_repo.create_event_node(event_id, titulo)
            self.neo4j_repo.create_organizer_relation(organizador_id, event_id)
        except Exception as e:
            logger.error(f"Neo4j event creation failed: {e}. Executing PostgreSQL rollback.")
            # Rollback PG
            self.pg_repo.delete_event(event_id)
            raise RuntimeError(f"No se pudo crear el evento: error en la base de grafos. Rolled back PostgreSQL.")

        # 4. MongoDB log
        try:
            self.mongo_repo.db.eventos_logs.insert_one({
                "evento_id": event_id,
                "organizador_id": organizador_id,
                "titulo": titulo,
                "accion": "creacion",
                "timestamp": datetime.utcnow()
            })
            
            # Create notification for all other users
            all_ids = self.pg_repo.get_all_user_ids_except(organizador_id)
            for uid in all_ids:
                self.mongo_repo.create_notification(uid, f"Nuevo evento disponible: '{titulo}'", "evento")
        except Exception as e:
            logger.error(f"MongoDB event notification failed: {e}. Proceeding.")

        return event_id

    def obtener_eventos(self, token):
        """Retrieve list of all social events (requires active session)."""
        user_id = self.get_current_user_id(token)
        if user_id is None:
            raise PermissionError("Sesión inválida o expirada.")
        return self.pg_repo.get_events()

    def inscribirse_evento(self, token, event_id):
        """
        Flow for Registering to an Event:
        1. Redis validates session active.
        2. PostgreSQL registers attendance.
        3. Neo4j creates ASISTE_A relationship.
        4. MongoDB generates notification for the event organizer.
        """
        user_id = self.get_current_user_id(token)
        if user_id is None:
            raise PermissionError("Sesión inválida o expirada.")

        # Get event info to find the organizer
        event = self.pg_repo.get_event_by_id(event_id)
        if not event:
            raise ValueError("El evento especificado no existe.")
            
        organizador_id = event["organizador_id"]

        # 2. PostgreSQL register attendance
        self.pg_repo.register_attendance(user_id, event_id)

        # 3. Neo4j create relation
        try:
            self.neo4j_repo.create_attendance_relation(user_id, event_id)
        except Exception as e:
            logger.error(f"Neo4j attendance registration failed: {e}. Eventual consistency expected.")

        # 4. MongoDB notification to organizer
        try:
            user_pg = self.pg_repo.get_user_by_id(user_id)
            user_name = user_pg["nombre"] if user_pg else "Alguien"
            msg = f"{user_name} se inscribió a tu evento: '{event['titulo']}'"
            self.mongo_repo.create_notification(organizador_id, msg, "evento_asistencia")
        except Exception as e:
            logger.error(f"MongoDB organizer notification failed: {e}. Proceeding.")
