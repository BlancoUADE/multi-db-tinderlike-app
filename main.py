import sys
from app.cli.main_cli import TinderCLI

if __name__ == "__main__":
    try:
        cli = TinderCLI()
        cli.run()
    except KeyboardInterrupt:
        print("\n\nPrograma terminado por el usuario (KeyboardInterrupt). ¡Adiós!")
        sys.exit(0)
    except Exception as e:
        print(f"\nOcurrió un error inesperado al ejecutar la aplicación: {e}")
        sys.exit(1)
