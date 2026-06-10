import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from app.databases.neo4j_conn import get_neo4j_driver
from app.databases.postgres_conn import get_postgres_connection

def test_neo4j():
    driver = get_neo4j_driver()
    with driver.session() as session:
        res = list(session.run("MATCH (n:Usuario) RETURN n.nombre as nombre, n.id_usuario as id_usuario, n.edad as edad"))
        print(f"Neo4j Usuario nodes count: {len(res)}")
        for r in res:
            print(f"  {r['nombre']} (ID: {r['id_usuario']}, Edad: {r['edad']})")

        res_rels = list(session.run("MATCH ()-[r]->() RETURN type(r) as t, count(r) as c"))
        print(f"Neo4j relationships: {res_rels}")

def test_postgres():
    conn = get_postgres_connection()
    cur = conn.cursor()
    cur.execute("SELECT id_usuario, nombre, fecha_nacimiento, email FROM usuarios;")
    rows = cur.fetchall()
    print(f"Postgres usuarios count: {len(rows)}")
    for r in rows:
        print(f"  {r[1]} (ID: {r[0]}, Fecha Nacimiento: {r[2]}, Email: {r[3]})")
    
    cur.execute("SELECT id_usuario_origen, id_usuario_destino FROM likes;")
    likes = cur.fetchall()
    print(f"Postgres likes count: {len(likes)}")
    for l in likes:
        print(f"  {l[0]} -> {l[1]}")

    cur.close()
    conn.close()

if __name__ == "__main__":
    test_postgres()
    test_neo4j()
