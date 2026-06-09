from app.databases.neo4j_conn import get_neo4j_driver
from datetime import datetime

class Neo4jRepository:
    def __init__(self):
        self.driver = get_neo4j_driver()

    def close(self):
        self.driver.close()

    # --- NODOS ---
    def crear_usuario_nodo(self, id_usuario, nombre, edad, genero, ubicacion):
        query = """
            MERGE (u:Usuario {id_usuario: $id_usuario})
            SET u.nombre = $nombre, u.edad = $edad, u.genero = $genero, u.ubicacion = $ubicacion
            RETURN u
        """
        with self.driver.session() as session:
            session.run(query, id_usuario=id_usuario, nombre=nombre, edad=edad, genero=genero, ubicacion=ubicacion)

    def crear_interes_nodo(self, nombre):
        query = """
            MERGE (i:Interes {nombre: $nombre})
            RETURN i
        """
        with self.driver.session() as session:
            session.run(query, nombre=nombre.strip().lower())

    def asociar_interes_usuario(self, id_usuario, nombre_interes):
        query = """
            MATCH (u:Usuario {id_usuario: $id_usuario})
            MERGE (i:Interes {nombre: $nombre_interes})
            MERGE (u)-[:TIENE_INTERES]->(i)
        """
        with self.driver.session() as session:
            session.run(query, id_usuario=id_usuario, nombre_interes=nombre_interes.strip().lower())

    def desasociar_interes_usuario(self, id_usuario, nombre_interes):
        query = """
            MATCH (u:Usuario {id_usuario: $id_usuario})-[r:TIENE_INTERES]->(i:Interes {nombre: $nombre_interes})
            DELETE r
        """
        with self.driver.session() as session:
            session.run(query, id_usuario=id_usuario, nombre_interes=nombre_interes.strip().lower())

    def crear_evento_nodo(self, id_evento, nombre_evento):
        query = """
            MERGE (e:Evento {id_evento: $id_evento})
            SET e.nombre = $nombre_evento
            RETURN e
        """
        with self.driver.session() as session:
            session.run(query, id_evento=id_evento, nombre_evento=nombre_evento)

    # --- RELACIONES ---
    def registrar_like_relacion(self, id_usuario_origen, id_usuario_destino):
        query = """
            MATCH (u1:Usuario {id_usuario: $id1})
            MATCH (u2:Usuario {id_usuario: $id2})
            MERGE (u1)-[:DIO_LIKE {fecha: datetime()}]->(u2)
        """
        with self.driver.session() as session:
            session.run(query, id1=id_usuario_origen, id2=id_usuario_destino)

    def registrar_coincidencia_relacion(self, id_usuario1, id_usuario2):
        query = """
            MATCH (u1:Usuario {id_usuario: $id1})
            MATCH (u2:Usuario {id_usuario: $id2})
            MERGE (u1)-[:COINCIDIO_CON {fecha: datetime()}]->(u2)
        """
        with self.driver.session() as session:
            session.run(query, id1=id_usuario1, id2=id_usuario2)

    def registrar_bloqueo_relacion(self, id_bloqueador, id_bloqueado):
        query = """
            MATCH (u1:Usuario {id_usuario: $id1})
            MATCH (u2:Usuario {id_usuario: $id2})
            MERGE (u1)-[:BLOQUEO {fecha: datetime()}]->(u2)
        """
        with self.driver.session() as session:
            session.run(query, id1=id_bloqueador, id2=id_bloqueado)

    def eliminar_bloqueo_relacion(self, id_bloqueador, id_bloqueado):
        query = """
            MATCH (u1:Usuario {id_usuario: $id1})-[r:BLOQUEO]->(u2:Usuario {id_usuario: $id2})
            DELETE r
        """
        with self.driver.session() as session:
            session.run(query, id1=id_bloqueador, id2=id_bloqueado)

    def registrar_organizador_evento(self, id_usuario, id_evento):
        query = """
            MATCH (u:Usuario {id_usuario: $id_usuario})
            MATCH (e:Evento {id_evento: $id_evento})
            MERGE (u)-[:ORGANIZO]->(e)
        """
        with self.driver.session() as session:
            session.run(query, id_usuario=id_usuario, id_evento=id_evento)

    def registrar_invitado_evento(self, id_usuario, id_evento):
        query = """
            MATCH (u:Usuario {id_usuario: $id_usuario})
            MATCH (e:Evento {id_evento: $id_evento})
            MERGE (u)-[:INVITADO_A]->(e)
        """
        with self.driver.session() as session:
            session.run(query, id_usuario=id_usuario, id_evento=id_evento)

    def registrar_aceptacion_evento(self, id_usuario, id_evento):
        query = """
            MATCH (u:Usuario {id_usuario: $id_usuario})
            MATCH (e:Evento {id_evento: $id_evento})
            MERGE (u)-[:ACEPTO_EVENTO {fecha: datetime()}]->(e)
        """
        with self.driver.session() as session:
            session.run(query, id_usuario=id_usuario, id_evento=id_evento)

    # --- RECOMENDACIONES ---
    def buscar_usuarios_compatibles(self, id_usuario, pref_edad_min, pref_edad_max, generos_permitidos):
        # generos_permitidos can be a list e.g. ["M", "F", "Otro"] or ["F"]
        # Prioritize users with most common interests.
        query = """
            MATCH (u:Usuario {id_usuario: $uid})
            MATCH (target:Usuario)
            WHERE target.id_usuario <> $uid
              AND target.genero IN $generos
              AND target.edad >= $age_min AND target.edad <= $age_max
              AND NOT (u)-[:BLOQUEO]-(target)
              AND NOT (u)-[:DIO_LIKE]->(target)
              AND NOT (u)-[:COINCIDIO_CON]-(target)
            OPTIONAL MATCH (u)-[:TIENE_INTERES]->(i:Interes)<-[:TIENE_INTERES]-(target)
            WITH target, count(i) as common_interests_count
            RETURN target.id_usuario as id_usuario, common_interests_count
            ORDER BY common_interests_count DESC, target.id_usuario ASC
        """
        with self.driver.session() as session:
            result = session.run(
                query, 
                uid=id_usuario, 
                age_min=pref_edad_min, 
                age_max=pref_edad_max, 
                generos=generos_permitidos
            )
            return [record["id_usuario"] for record in result]

    # --- REPORTES ---
    def obtener_intereses_comunes_coincidencias(self):
        query = """
            MATCH (u1:Usuario)-[:COINCIDIO_CON]-(u2:Usuario)
            WHERE u1.id_usuario < u2.id_usuario
            MATCH (u1)-[:TIENE_INTERES]->(i:Interes)<-[:TIENE_INTERES]-(u2)
            RETURN i.nombre as interes, count(i) as coincidencias_compartidas
            ORDER BY coincidencias_compartidas DESC
        """
        with self.driver.session() as session:
            result = session.run(query)
            return [dict(record) for record in result]

    def obtener_usuarios_intereses_en_comun(self, id_usuario, target_ids):
        query = """
            MATCH (u:Usuario {id_usuario: $uid})
            MATCH (target:Usuario)
            WHERE target.id_usuario IN $target_ids
            MATCH (u)-[:TIENE_INTERES]->(i:Interes)<-[:TIENE_INTERES]-(target)
            WITH target, count(i) as common_count
            WHERE common_count >= 3
            RETURN target.id_usuario as id_usuario, common_count
            ORDER BY common_count DESC
        """
        with self.driver.session() as session:
            result = session.run(query, uid=id_usuario, target_ids=target_ids)
            return [dict(record) for record in result]
