# CLI Tinder Multi-DB

Aplicación de citas con arquitectura multi-base de datos (PostgreSQL, MongoDB, Redis, Cassandra, Neo4j).

## Estructura

```
├── main.py                 # Entry point (36 líneas)
├── config.py              # Configuración centralizada
├── docker-compose.yml     # Servicios de BD
├── requirements.txt       # Dependencias Python
├── .env.example          # Variables de entorno
│
├── src/                   # Código fuente
│   ├── database/          # Conexiones a BD
│   ├── cli/              # Interfaz de usuario
│   ├── models/           # Entidades
│   └── analytics/        # Analíticas
│
├── scripts/              # Utilidades
│   ├── main_monolithic.py    # Código original
│   ├── verify_databases.py   # Verificar BD
│   └── test_connections.py   # Probar conexiones
│
└── docs/                 # Documentación
```

## Instalación

```bash
# 1. Levantar servicios
docker compose up -d

# 2. Crear entorno (Python 3.11)
py -3.11 -m venv .venv
.\.venv\Scripts\activate

# 3. Instalar dependencias
pip install -r requirements.txt
```

## Uso

```bash
python main.py
```

## Utilidades

```bash
python scripts/test_connections.py      # Verificar conexiones
python scripts/verify_databases.py       # Ver esquemas y datos
```

Ver documentación completa en `docs/README.md`
