# CLI Tinder (Simplified)

Aplicación de citas con arquitectura simplificada basada únicamente en PostgreSQL.

## Estructura

```
├── main.py                 # Entry point y CLI
├── database.py             # Lógica de base de datos
├── docker-compose.yml      # Servicio de PostgreSQL
├── requirements.txt        # Dependencias Python
└── docs/                   # Documentación original
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

Ver documentación completa en `docs/README.md`
