#!/usr/bin/env python3
"""
Smoke test de conectividad multi-DB.

No inserta datos de prueba sueltos; solo verifica conectividad y asegura los
esquemas administrados por la aplicacion.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import database as db


def test_postgres():
    conn = db.connect_postgres()
    try:
        db.ensure_postgres_schema(conn)
        with conn.cursor() as cur:
            cur.execute("SELECT 'PostgreSQL OK'")
            print(cur.fetchone()[0])
    finally:
        conn.close()


def test_mongodb():
    client = db.connect_mongo()
    try:
        client[db.MONGO_DB].command("ping")
        print("MongoDB OK")
    finally:
        client.close()


def test_redis():
    client = db.connect_redis()
    client.ping()
    client.close()
    print("Redis OK")


def test_cassandra():
    cluster, session = db.connect_cassandra()
    try:
        db.ensure_cassandra_schema(session)
        print("Cassandra OK")
    finally:
        cluster.shutdown()


def test_neo4j():
    driver = db.connect_neo4j()
    try:
        db.ensure_neo4j_schema(driver)
        print("Neo4j OK")
    finally:
        driver.close()


if __name__ == "__main__":
    test_postgres()
    test_mongodb()
    test_redis()
    test_cassandra()
    test_neo4j()
    print("Todas las conexiones funcionan correctamente.")
