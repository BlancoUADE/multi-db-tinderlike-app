import sys
from app.databases.postgres_conn import get_postgres_connection
from app.databases.mongo_conn import get_mongo_db
from app.databases.redis_conn import get_redis_client
from app.databases.cassandra_conn import get_cassandra_session
from app.databases.neo4j_conn import get_neo4j_driver
from app.cli.main_cli import TinderCLI

def verificar_conexiones():
    print("Verificando conexiones a las bases de datos...")
    
    try:
        conn = get_postgres_connection()
        cur = conn.cursor()
        cur.execute("SELECT 1;")
        cur.close()
        conn.close()
        print(" [OK] PostgreSQL conectado.")
    except Exception as e:
        print(f" [ERROR] PostgreSQL: {e}")
        return False

    try:
        db = get_mongo_db()
        db.client.admin.command('ping')
        print(" [OK] MongoDB conectado.")
    except Exception as e:
        print(f" [ERROR] MongoDB: {e}")
        return False

    try:
        r = get_redis_client()
        r.ping()
        print(" [OK] Redis conectado.")
    except Exception as e:
        print(f" [ERROR] Redis: {e}")
        return False

    try:
        cluster, session = get_cassandra_session()
        session.execute("SELECT now() FROM system.local;").one()
        print(" [OK] Cassandra conectado.")
    except Exception as e:
        print(f" [ERROR] Cassandra: {e}")
        return False

    try:
        driver = get_neo4j_driver()
        driver.verify_connectivity()
        driver.close()
        print(" [OK] Neo4j conectado.")
    except Exception as e:
        print(f" [ERROR] Neo4j: {e}")
        return False

    print("Todas las conexiones funcionan correctamente.\n")
    return True

if __name__ == "__main__":
    try:
        if not verificar_conexiones():
            print("\nError al iniciar: No se pudo conectar a una o más bases de datos.")
            sys.exit(1)
        cli = TinderCLI()
        cli.run()
    except KeyboardInterrupt:
        print("\n\nPrograma terminado por el usuario (KeyboardInterrupt). ¡Adiós!")
        sys.exit(0)
    except Exception as e:
        print(f"\nOcurrió un error inesperado al ejecutar la aplicación: {e}")
        sys.exit(1)
