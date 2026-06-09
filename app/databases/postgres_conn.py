import psycopg2
from app.config import settings

def get_postgres_connection():
    """Returns a connection to PostgreSQL."""
    return psycopg2.connect(
        host=settings.PG_HOST,
        port=settings.PG_PORT,
        dbname=settings.PG_DB,
        user=settings.PG_USER,
        password=settings.PG_PASSWORD
    )
