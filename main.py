import sys
from src.cli.menu import TinderCLI
from src.database.connection import close_cassandra_session

def main():
    try:
        cli = TinderCLI()
        cli.run()
    except KeyboardInterrupt:
        print("\nPrograma finalizado abruptamente por el usuario. ¡Hasta luego!")
    finally:
        close_cassandra_session()
        sys.exit(0)

if __name__ == "__main__":
    main()
