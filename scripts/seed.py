import sys
from pathlib import Path

# Add root folder to python path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from app.seeds.seeder import Seeder

if __name__ == "__main__":
    print("Iniciando script de población de datos (Seed)...")
    try:
        seeder = Seeder()
        seeder.run()
        print("¡Población finalizada exitosamente!")
    except Exception as e:
        print(f"Error en seed: {e}", file=sys.stderr)
        sys.exit(1)
