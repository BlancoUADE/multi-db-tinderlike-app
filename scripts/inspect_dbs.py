import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from app.databases.postgres_conn import get_postgres_connection
from app.databases.cassandra_conn import get_cassandra_session
from app.databases.mongo_conn import get_mongo_db
from app.databases.redis_conn import get_redis_client
from app.databases.neo4j_conn import get_neo4j_driver

def inspect_postgres():
    conn = get_postgres_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM coincidencias;")
    matches_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM usuarios;")
    users_count = cur.fetchone()[0]
    print(f"PostgreSQL - Usuarios: {users_count}, Coincidencias: {matches_count}")
    cur.close()
    conn.close()

def inspect_cassandra():
    cluster, session = get_cassandra_session()
    rows = list(session.execute("SELECT * FROM estadisticas_coincidencias_por_dia;"))
    total_coincidencias = sum(r.cantidad_coincidencias for r in rows)
    print(f"Cassandra - Filas estadisticas: {len(rows)}, Total coincidencias: {total_coincidencias}")
    for r in rows:
        print(f"  Fecha: {r.fecha}, Coincidencias: {r.cantidad_coincidencias}, Fin de semana: {r.cantidad_fin_de_semana}, Feriado: {r.cantidad_feriado}")

if __name__ == "__main__":
    inspect_postgres()
    inspect_cassandra()
