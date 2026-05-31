#!/usr/bin/env python3
"""
CLI Tinder Multi-DB - Entry Point
========================================
Aplicación de citas con arquitectura multi-base de datos.
Soporta: PostgreSQL, MongoDB, Redis, Cassandra, Neo4j
"""

import sys


def check_environment():
    """Verifica que Python 3.11+ está disponible."""
    if sys.version_info < (3, 11):
        print("Advertencia: Este proyecto requiere Python 3.11+")
        print(f"Tu version: {sys.version}")
        sys.exit(1)


def main():
    """Punto de entrada principal."""
    from src.cli.menu import main as cli_main
    
    try:
        cli_main()
    except KeyboardInterrupt:
        print("\n\nHasta luego.")
        sys.exit(0)
    except Exception as e:
        print(f"Error fatal: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    check_environment()
    main()
