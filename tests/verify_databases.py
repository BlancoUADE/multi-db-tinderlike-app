#!/usr/bin/env python3
"""
Verificacion del entorno Tinder Multi-DB.

El script no es un test unitario: es una ayuda de demo para mostrar que las
cinco bases estan disponibles y que los datos esperados existen con nombres
coherentes.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import database as db


EXPECTED_POSTGRES_TABLES = {
    "usuarios",
    "fotos",
    "intereses",
    "usuario_intereses",
    "likes",
    "bloqueos",
    "coincidencias",
    "mensajes",
    "eventos",
    "asistencia_eventos",
    "notificaciones",
}


def print_header(title):
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


def verify_postgres():
    print_header("PostgreSQL - fuente de verdad relacional")
    conn = db.connect_postgres()
    try:
        db.ensure_postgres_schema(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                ORDER BY table_name
                """
            )
            tables = [row[0] for row in cur.fetchall()]
            missing = sorted(EXPECTED_POSTGRES_TABLES - set(tables))
            print("Conexion OK")
            print(f"Tablas: {', '.join(tables)}")
            print(f"Faltantes esperadas: {', '.join(missing) if missing else 'ninguna'}")
            print("\nRegistros:")
            for table in sorted(EXPECTED_POSTGRES_TABLES):
                cur.execute(f"SELECT COUNT(*) FROM {table}")
                print(f"- {table}: {cur.fetchone()[0]}")
    finally:
        conn.close()


def verify_mongodb():
    print_header("MongoDB - perfiles desnormalizados y auditoria")
    client = db.connect_mongo()
    try:
        mongo_db = client[db.MONGO_DB]
        collections = mongo_db.list_collection_names()
        print("Conexion OK")
        print(f"Colecciones: {', '.join(collections) if collections else '(sin colecciones)'}")
        for collection in [db.MONGO_PROFILE_COLLECTION, db.MONGO_LOGIN_COLLECTION]:
            count = mongo_db[collection].count_documents({})
            print(f"- {collection}: {count} documentos")
        example = mongo_db[db.MONGO_PROFILE_COLLECTION].find_one({}, {"_id": 0})
        if example:
            print("\nEjemplo perfil:")
            print(example)
    finally:
        client.close()


def verify_redis():
    print_header("Redis - contadores y sesiones con TTL")
    client = db.connect_redis()
    print("Conexion OK")
    keys = sorted(client.keys("*"))
    print(f"Claves: {len(keys)}")
    for key in keys[:20]:
        key_type = client.type(key)
        ttl = client.ttl(key)
        value = client.hgetall(key) if key_type == "hash" else client.get(key)
        print(f"- {key} ({key_type}, ttl={ttl}): {value}")
    client.close()


def verify_cassandra():
    print_header("Cassandra - mensajes por coincidencia")
    cluster, session = db.connect_cassandra()
    try:
        db.ensure_cassandra_schema(session)
        metadata = cluster.metadata.keyspaces[db.CASSANDRA_KEYSPACE]
        tables = sorted(metadata.tables.keys())
        print("Conexion OK")
        print(f"Keyspace: {db.CASSANDRA_KEYSPACE}")
        print(f"Tablas: {', '.join(tables)}")
        result = session.execute(
            f"SELECT COUNT(*) FROM {db.CASSANDRA_KEYSPACE}.{db.CASSANDRA_MESSAGES_TABLE}"
        )
        print(f"- {db.CASSANDRA_MESSAGES_TABLE}: {result.one()[0]} registros")
        rows = session.execute(
            f"SELECT * FROM {db.CASSANDRA_KEYSPACE}.{db.CASSANDRA_MESSAGES_TABLE} LIMIT 5"
        )
        for row in rows:
            print(f"  {row}")
    finally:
        cluster.shutdown()


def verify_neo4j():
    print_header("Neo4j - grafo de usuarios, intereses, likes y matches")
    driver = db.connect_neo4j()
    try:
        db.ensure_neo4j_schema(driver)
        with driver.session() as session:
            print("Conexion OK")
            labels = session.run(
                "MATCH (n) RETURN labels(n) AS labels, count(*) AS total ORDER BY labels"
            )
            print("Nodos:")
            for record in labels:
                print(f"- {record['labels']}: {record['total']}")
            rels = session.run(
                "MATCH ()-[r]->() RETURN type(r) AS tipo, count(*) AS total ORDER BY tipo"
            )
            print("Relaciones:")
            for record in rels:
                print(f"- {record['tipo']}: {record['total']}")
            sample = session.run(
                """
                MATCH (u:Usuario)-[r]->(x)
                RETURN u.nombre AS usuario, type(r) AS relacion, labels(x) AS destino_labels,
                       coalesce(x.nombre, x.id_evento, x.id_usuario) AS destino
                LIMIT 5
                """
            )
            print("Ejemplos:")
            for record in sample:
                print(f"- {record['usuario']} -[{record['relacion']}]-> {record['destino_labels']} {record['destino']}")
    finally:
        driver.close()


def main():
    verify_postgres()
    verify_mongodb()
    verify_redis()
    verify_cassandra()
    verify_neo4j()
    print("\nVerificacion completa.")


if __name__ == "__main__":
    main()
