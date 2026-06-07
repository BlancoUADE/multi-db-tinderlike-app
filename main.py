import sys
from src.cli.menu import TinderCLI

def main():
    try:
        cli = TinderCLI()
        cli.run()
    except KeyboardInterrupt:
        print("\nPrograma finalizado abruptamente por el usuario. ¡Hasta luego!")
        sys.exit(0)

if __name__ == "__main__":
    main()
