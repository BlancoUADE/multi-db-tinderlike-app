import sys
from src.database.connection import (
    get_postgres_connection,
    get_mongodb_client,
    get_mongodb_database,
    get_redis_client,
    get_cassandra_session,
    get_neo4j_driver
)


def test_postgres():
    try:
        conn = get_postgres_connection()
        cur = conn.cursor()
        cur.execute("SELECT 'PostgreSQL OK';")
        res = cur.fetchone()[0]
        cur.close()
        conn.close()
        print(res)
    except Exception as e:
        print(f"PostgreSQL ERROR: {e}")
        sys.exit(1)


def test_mongodb():
    try:
        db = get_mongodb_database()
        # Ping the server
        db.command("ping")
        print("MongoDB OK")
    except Exception as e:
        print(f"MongoDB ERROR: {e}")
        sys.exit(1)


def test_redis():
    try:
        r = get_redis_client()
        r.ping()
        print("Redis OK")
    except Exception as e:
        print(f"Redis ERROR: {e}")
        sys.exit(1)


def test_cassandra():
    try:
        session = get_cassandra_session()
        # Simple query
        session.execute("SELECT release_version FROM system.local").one()
        print("Cassandra OK")
    except Exception as e:
        print(f"Cassandra ERROR: {e}")
        sys.exit(1)


def test_neo4j():
    try:
        driver = get_neo4j_driver()
        with driver.session() as session:
            session.run("RETURN 1")
        driver.close()
        print("Neo4j OK")
    except Exception as e:
        print(f"Neo4j ERROR: {e}")
        sys.exit(1)


def main():
    print("Iniciando validación de conexiones a las 5 bases de datos...")
    test_postgres()
    test_mongodb()
    test_redis()
    test_cassandra()
    test_neo4j()
    print("\nTodas las conexiones se realizaron con éxito.")


if __name__ == "__main__":
    main()