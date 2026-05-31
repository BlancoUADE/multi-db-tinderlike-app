from psycopg2 import connect
from pymongo import MongoClient
import redis
from cassandra import DependencyException
from neo4j import GraphDatabase


def test_postgres():
    conn = connect(
        host="localhost",
        port=5433,
        dbname="tinder_app",
        user="tpo_user",
        password="tpo_password"
    )
    cur = conn.cursor()
    cur.execute("SELECT 'PostgreSQL OK';")
    print(cur.fetchone()[0])
    cur.close()
    conn.close()
    return True


def test_mongodb():
    client = MongoClient("mongodb://tpo_user:tpo_password@localhost:27017/")
    db = client["tinder_app"]
    db.test.insert_one({"mensaje": "MongoDB OK"})
    result = db.test.find_one({"mensaje": "MongoDB OK"})
    print(result["mensaje"])
    client.close()
    return True


def test_redis():
    r = redis.Redis(host="localhost", port=6379, decode_responses=True)
    r.set("test", "Redis OK")
    print(r.get("test"))
    return True


def test_cassandra():
    try:
        from cassandra.cluster import Cluster
    except DependencyException:
        print("Cassandra driver no es compatible con Python 3.12+ en Windows. Usa Python 3.11.")
        return False

    cluster = Cluster(["localhost"], port=9042)
    session = cluster.connect()
    session.execute("""
        CREATE KEYSPACE IF NOT EXISTS tinder_app
        WITH replication = {'class': 'SimpleStrategy', 'replication_factor': 1}
    """)
    session.set_keyspace("tinder_app")
    session.execute("""
        CREATE TABLE IF NOT EXISTS test (
            id int PRIMARY KEY,
            mensaje text
        )
    """)
    session.execute("INSERT INTO test (id, mensaje) VALUES (1, 'Cassandra OK')")
    row = session.execute("SELECT mensaje FROM test WHERE id = 1").one()
    print(row.mensaje)
    cluster.shutdown()
    return True


def test_neo4j():
    driver = GraphDatabase.driver(
        "bolt://localhost:7687",
        auth=("neo4j", "tpo_password")
    )

    with driver.session() as session:
        result = session.run("""
            MERGE (n:Test {mensaje: 'Neo4j OK'})
            RETURN n.mensaje AS mensaje
        """)
        print(result.single()["mensaje"])

    driver.close()
    return True


if __name__ == "__main__":
    results = {
        "PostgreSQL": test_postgres(),
        "MongoDB": test_mongodb(),
        "Redis": test_redis(),
        "Cassandra": test_cassandra(),
        "Neo4j": test_neo4j(),
    }

    pendientes = [name for name, ok in results.items() if not ok]
    if not pendientes:
        print("Todas las conexiones funcionan correctamente.")
    else:
        print(f"Conexiones pendientes: {', '.join(pendientes)}.")
