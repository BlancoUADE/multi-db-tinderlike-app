from src.database.connection import get_neo4j_driver

class Neo4jRepository:
    def __init__(self):
        self.driver = get_neo4j_driver()

    def close(self):
        self.driver.close()

    def create_user_node(self, user_id, nombre):
        """Create a user node in the graph."""
        query = """
        MERGE (u:Usuario {id: $user_id})
        ON CREATE SET u.nombre = $nombre
        ON MATCH SET u.nombre = $nombre
        RETURN u;
        """
        with self.driver.session() as session:
            session.run(query, user_id=user_id, nombre=nombre)

    def delete_user_node(self, user_id):
        """Delete user node (used for rollback or cleanup)."""
        query = """
        MATCH (u:Usuario {id: $user_id})
        DETACH DELETE u;
        """
        with self.driver.session() as session:
            session.run(query, user_id=user_id)

    def update_interests(self, user_id, interests):
        """Update a user's interests by deleting old relationships and merging new ones."""
        query = """
        MATCH (u:Usuario {id: $user_id})
        OPTIONAL MATCH (u)-[r:TIENE_INTERES]->()
        DELETE r
        WITH u
        UNWIND $interests AS interest_name
        MERGE (i:Interes {nombre: interest_name})
        MERGE (u)-[:TIENE_INTERES]->(i)
        """
        # If interests list is empty, we only clear relationships
        if not interests:
            query = """
            MATCH (u:Usuario {id: $user_id})
            OPTIONAL MATCH (u)-[r:TIENE_INTERES]->()
            DELETE r
            """
        with self.driver.session() as session:
            session.run(query, user_id=user_id, interests=interests)

    def get_excluded_user_ids(self, user_id):
        """Retrieve set of user IDs to exclude from search (likes, matches, blocks)."""
        query = """
        MATCH (u:Usuario {id: $user_id})
        OPTIONAL MATCH (u)-[:LE_DIO_LIKE|MATCH_CON|BLOQUEO|DESCARTO]->(other:Usuario)
        OPTIONAL MATCH (u)<-[:BLOQUEO]-(other2:Usuario)
        RETURN collect(DISTINCT other.id) + collect(DISTINCT other2.id) AS excluded_ids
        """
        with self.driver.session() as session:
            res = session.run(query, user_id=user_id).single()
            if res and res["excluded_ids"]:
                # Filter out None and return set of ints
                return {int(x) for x in res["excluded_ids"] if x is not None}
            return set()

    def sort_candidates_by_interests(self, user_id, candidate_ids):
        """Sort list of candidate IDs by count of shared interests in descending order."""
        if not candidate_ids:
            return []
        query = """
        MATCH (u:Usuario {id: $user_id})
        MATCH (c:Usuario) WHERE c.id IN $candidate_ids
        OPTIONAL MATCH (u)-[:TIENE_INTERES]->(i:Interes)<-[:TIENE_INTERES]-(c)
        WITH c, count(i) AS comunes
        RETURN c.id AS id
        ORDER BY comunes DESC
        """
        with self.driver.session() as session:
            res = session.run(query, user_id=user_id, candidate_ids=candidate_ids)
            return [row["id"] for row in res]

    def create_like(self, user_from, user_to):
        """Create a LE_DIO_LIKE relationship from user_from to user_to."""
        query = """
        MATCH (u1:Usuario {id: $user_from})
        MATCH (u2:Usuario {id: $user_to})
        MERGE (u1)-[:LE_DIO_LIKE]->(u2)
        """
        with self.driver.session() as session:
            session.run(query, user_from=user_from, user_to=user_to)

    def delete_like(self, user_from, user_to):
        """Delete LE_DIO_LIKE relationship (used for rollback)."""
        query = """
        MATCH (u1:Usuario {id: $user_from})-[r:LE_DIO_LIKE]->(u2:Usuario {id: $user_to})
        DELETE r
        """
        with self.driver.session() as session:
            session.run(query, user_from=user_from, user_to=user_to)

    def create_dislike(self, user_from, user_to):
        """Create a DESCARTO relationship from user_from to user_to."""
        query = """
        MATCH (u1:Usuario {id: $user_from})
        MATCH (u2:Usuario {id: $user_to})
        MERGE (u1)-[:DESCARTO]->(u2)
        """
        with self.driver.session() as session:
            session.run(query, user_from=user_from, user_to=user_to)

    def check_reciprocity(self, user_from, user_to):
        """Check if user_to has liked user_from."""
        query = """
        MATCH (u2:Usuario {id: $user_to})-[r:LE_DIO_LIKE]->(u1:Usuario {id: $user_from})
        RETURN count(r) > 0 AS reciprocal
        """
        with self.driver.session() as session:
            res = session.run(query, user_from=user_from, user_to=user_to).single()
            return res["reciprocal"] if res else False

    def create_match_relations(self, user_1, user_2):
        """Create bidirectional MATCH_CON relationships between user_1 and user_2 and clean up likes."""
        query = """
        MATCH (u1:Usuario {id: $user_1})
        MATCH (u2:Usuario {id: $user_2})
        MERGE (u1)-[:MATCH_CON]->(u2)
        MERGE (u2)-[:MATCH_CON]->(u1)
        WITH u1, u2
        OPTIONAL MATCH (u1)-[r1:LE_DIO_LIKE]->(u2)
        OPTIONAL MATCH (u2)-[r2:LE_DIO_LIKE]->(u1)
        DELETE r1, r2
        """
        with self.driver.session() as session:
            session.run(query, user_1=user_1, user_2=user_2)

    def delete_match_relations(self, user_1, user_2):
        """Delete MATCH_CON relationships (used for rollback)."""
        query = """
        MATCH (u1:Usuario {id: $user_1})-[r:MATCH_CON]-(u2:Usuario {id: $user_2})
        DELETE r
        """
        with self.driver.session() as session:
            session.run(query, user_1=user_1, user_2=user_2)

    def create_block(self, bloqueador_id, bloqueado_id):
        """Create a BLOQUEO relationship from bloqueador to bloqueado and remove existing likes or matches."""
        query = """
        MATCH (u1:Usuario {id: $bloqueador_id})
        MATCH (u2:Usuario {id: $bloqueado_id})
        MERGE (u1)-[:BLOQUEO]->(u2)
        WITH u1, u2
        OPTIONAL MATCH (u1)-[r1:LE_DIO_LIKE]->(u2)
        OPTIONAL MATCH (u2)-[r2:LE_DIO_LIKE]->(u1)
        OPTIONAL MATCH (u1)-[r3:MATCH_CON]-(u2)
        DELETE r1, r2, r3
        """
        with self.driver.session() as session:
            session.run(query, bloqueador_id=bloqueador_id, bloqueado_id=bloqueado_id)

    def create_event_node(self, event_id, titulo):
        """Create an Evento node in the graph."""
        query = """
        MERGE (e:Evento {id: $event_id})
        ON CREATE SET e.titulo = $titulo
        ON MATCH SET e.titulo = $titulo
        RETURN e;
        """
        with self.driver.session() as session:
            session.run(query, event_id=event_id, titulo=titulo)

    def delete_event_node(self, event_id):
        """Delete an Evento node and its relationships."""
        query = """
        MATCH (e:Evento {id: $event_id})
        DETACH DELETE e;
        """
        with self.driver.session() as session:
            session.run(query, event_id=event_id)

    def create_organizer_relation(self, organizador_id, event_id):
        """Create an ORGANIZA relationship from user to event."""
        query = """
        MATCH (u:Usuario {id: $organizador_id})
        MATCH (e:Evento {id: $event_id})
        MERGE (u)-[:ORGANIZA]->(e)
        """
        with self.driver.session() as session:
            session.run(query, organizador_id=organizador_id, event_id=event_id)

    def create_attendance_relation(self, user_id, event_id):
        """Create an ASISTE_A relationship from user to event."""
        query = """
        MATCH (u:Usuario {id: $user_id})
        MATCH (e:Evento {id: $event_id})
        MERGE (u)-[:ASISTE_A]->(e)
        """
        with self.driver.session() as session:
            session.run(query, user_id=user_id, event_id=event_id)

    def prioritize_events_by_interests(self, user_id, event_ids):
        """
        Prioritize event IDs based on the count of shared interests with attendees of those events.
        """
        if not event_ids:
            return []
        query = """
        MATCH (u:Usuario {id: $user_id})
        OPTIONAL MATCH (u)-[:TIENE_INTERES]->(i:Interes)
        WITH u, collect(i) AS user_interests
        MATCH (e:Evento) WHERE e.id IN $event_ids
        OPTIONAL MATCH (other:Usuario)-[:ASISTE_A]->(e)
        WHERE other.id <> $user_id
        OPTIONAL MATCH (other)-[:TIENE_INTERES]->(shared:Interes)
        WHERE shared IN user_interests
        WITH e, count(shared) AS score
        RETURN e.id AS id, score
        ORDER BY score DESC
        """
        with self.driver.session() as session:
            res = session.run(query, user_id=user_id, event_ids=event_ids)
            return [row["id"] for row in res]
