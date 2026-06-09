import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from app.repositories.neo4j_repo import Neo4jRepository
from app.databases.neo4j_conn import get_neo4j_driver

def test():
    repo = Neo4jRepository()
    uid = 6  # Nicolas
    generos = ["F"]
    age_min = 26
    age_max = 35
    
    print(f"Querying compatibles for uid={uid}, age_min={age_min}, age_max={age_max}, generos={generos}")
    res = repo.buscar_usuarios_compatibles(uid, age_min, age_max, generos)
    print(f"Result: {res}")

if __name__ == "__main__":
    test()
