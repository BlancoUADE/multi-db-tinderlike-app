import sys
import os
from pathlib import Path

# Add root folder to python path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from app.databases.postgres_conn import get_postgres_connection
from app.databases.mongo_conn import get_mongo_db
from app.databases.redis_conn import get_redis_client
from app.databases.cassandra_conn import get_cassandra_session
from app.databases.neo4j_conn import get_neo4j_driver

def migrate_postgres():
    print("Migrando PostgreSQL...")
    conn = get_postgres_connection()
    cur = conn.cursor()
    
    # Drop existing tables to ensure constraints are recreated properly
    cur.execute("""
        DROP TABLE IF EXISTS 
            notificaciones, asistencia_eventos, eventos, bloqueos, 
            mensajes, coincidencias, likes, fotos, usuario_intereses, 
            intereses, usuarios, feriados 
        CASCADE;
    """)
    
    # 1. Feriados
    cur.execute("""
        CREATE TABLE IF NOT EXISTS feriados (
            fecha DATE PRIMARY KEY,
            descripcion VARCHAR(255) NOT NULL
        );
    """)
    
    # 2. Usuarios
    cur.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id_usuario SERIAL PRIMARY KEY,
            nombre VARCHAR(100) NOT NULL,
            edad INT NOT NULL,
            genero VARCHAR(10) NOT NULL,
            ubicacion VARCHAR(100) NOT NULL,
            biografia TEXT,
            pref_edad_min INT NOT NULL,
            pref_edad_max INT NOT NULL,
            fecha_registro TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            email VARCHAR(255) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            activo BOOLEAN NOT NULL DEFAULT TRUE
        );
    """)
    
    # 3. Intereses
    cur.execute("""
        CREATE TABLE IF NOT EXISTS intereses (
            id_interes SERIAL PRIMARY KEY,
            nombre VARCHAR(100) UNIQUE NOT NULL
        );
    """)
    
    # 4. Usuario_intereses
    cur.execute("""
        CREATE TABLE IF NOT EXISTS usuario_intereses (
            id_usuario INT REFERENCES usuarios(id_usuario) ON DELETE CASCADE,
            id_interes INT REFERENCES intereses(id_interes) ON DELETE CASCADE,
            PRIMARY KEY (id_usuario, id_interes)
        );
    """)
    
    # 5. Fotos
    cur.execute("""
        CREATE TABLE IF NOT EXISTS fotos (
            id_foto SERIAL PRIMARY KEY,
            id_usuario INT REFERENCES usuarios(id_usuario) ON DELETE CASCADE,
            url_archivo VARCHAR(255) NOT NULL,
            es_principal BOOLEAN NOT NULL DEFAULT FALSE,
            fecha_subida TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
    """)
    
    # 6. Likes
    cur.execute("""
        CREATE TABLE IF NOT EXISTS likes (
            id_like SERIAL PRIMARY KEY,
            id_usuario_origen INT REFERENCES usuarios(id_usuario) ON DELETE CASCADE,
            id_usuario_destino INT REFERENCES usuarios(id_usuario) ON DELETE CASCADE,
            fecha_like TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT chk_no_self_like CHECK (id_usuario_origen <> id_usuario_destino),
            CONSTRAINT uq_likes UNIQUE (id_usuario_origen, id_usuario_destino)
        );
    """)
    
    # 7. Coincidencias
    cur.execute("""
        CREATE TABLE IF NOT EXISTS coincidencias (
            id_coincidencia SERIAL PRIMARY KEY,
            id_usuario1 INT REFERENCES usuarios(id_usuario) ON DELETE CASCADE,
            id_usuario2 INT REFERENCES usuarios(id_usuario) ON DELETE CASCADE,
            fecha_coincidencia TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            fecha_feriado DATE REFERENCES feriados(fecha) ON DELETE SET NULL,
            CONSTRAINT chk_sorted_users CHECK (id_usuario1 < id_usuario2),
            CONSTRAINT uq_coincidencias UNIQUE (id_usuario1, id_usuario2)
        );
    """)
    
    # 8. Mensajes
    cur.execute("""
        CREATE TABLE IF NOT EXISTS mensajes (
            id_mensaje SERIAL PRIMARY KEY,
            id_coincidencia INT REFERENCES coincidencias(id_coincidencia) ON DELETE CASCADE,
            id_emisor INT REFERENCES usuarios(id_usuario) ON DELETE CASCADE,
            contenido TEXT NOT NULL,
            fecha_envio TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
    """)
    
    # 9. Bloqueos
    cur.execute("""
        CREATE TABLE IF NOT EXISTS bloqueos (
            id_bloqueo SERIAL PRIMARY KEY,
            id_bloqueador INT REFERENCES usuarios(id_usuario) ON DELETE CASCADE,
            id_bloqueado INT REFERENCES usuarios(id_usuario) ON DELETE CASCADE,
            fecha_bloqueo TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            fecha_desbloqueo TIMESTAMP NULL,
            activo BOOLEAN NOT NULL DEFAULT TRUE,
            CONSTRAINT chk_no_self_block CHECK (id_bloqueador <> id_bloqueado),
            CONSTRAINT uq_bloqueos UNIQUE (id_bloqueador, id_bloqueado)
        );
    """)
    
    # 10. Eventos (Citas)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS eventos (
            id_evento SERIAL PRIMARY KEY,
            nombre_evento VARCHAR(150) NOT NULL,
            fecha TIMESTAMP NOT NULL,
            ubicacion VARCHAR(255) NOT NULL,
            id_organizador INT REFERENCES usuarios(id_usuario) ON DELETE CASCADE,
            id_coincidencia INT REFERENCES coincidencias(id_coincidencia) ON DELETE CASCADE,
            estado VARCHAR(20) NOT NULL DEFAULT 'PENDIENTE',
            fecha_creacion TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
    """)
    
    # 11. Asistencia_eventos
    cur.execute("""
        CREATE TABLE IF NOT EXISTS asistencia_eventos (
            id_asistencia SERIAL PRIMARY KEY,
            id_usuario INT REFERENCES usuarios(id_usuario) ON DELETE CASCADE,
            id_evento INT REFERENCES eventos(id_evento) ON DELETE CASCADE,
            estado VARCHAR(20) NOT NULL DEFAULT 'PENDIENTE',
            fecha_registro TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            fecha_respuesta TIMESTAMP NULL,
            CONSTRAINT uq_asistencia_evento UNIQUE (id_evento)
        );
    """)
    
    # 12. Notificaciones
    cur.execute("""
        CREATE TABLE IF NOT EXISTS notificaciones (
            id_notificacion SERIAL PRIMARY KEY,
            id_usuario INT REFERENCES usuarios(id_usuario) ON DELETE CASCADE,
            tipo VARCHAR(20) NOT NULL,
            id_like INT REFERENCES likes(id_like) ON DELETE CASCADE NULL,
            id_coincidencia INT REFERENCES coincidencias(id_coincidencia) ON DELETE CASCADE NULL,
            id_mensaje INT REFERENCES mensajes(id_mensaje) ON DELETE CASCADE NULL,
            id_evento INT REFERENCES eventos(id_evento) ON DELETE CASCADE NULL,
            leida BOOLEAN NOT NULL DEFAULT FALSE,
            fecha_creacion TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
    """)
    
    # 13. Partial Indexes
    cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_fotos_principal_unica ON fotos(id_usuario) WHERE (es_principal = TRUE);")
    cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_bloqueo_activo_unico ON bloqueos(id_bloqueador, id_bloqueado) WHERE (activo = TRUE);")
    cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_evento_pendiente_unico ON eventos(id_coincidencia) WHERE (estado = 'PENDIENTE');")
    
    conn.commit()
    cur.close()
    conn.close()
    print("PostgreSQL migrado con éxito.")

def migrate_mongodb():
    print("Migrando MongoDB...")
    db = get_mongo_db()
    # Create indexes
    db.perfiles_publicos.create_index("id_usuario", unique=True)
    db.actividad_importante.create_index("fecha")
    print("MongoDB migrado con éxito.")

def migrate_redis():
    print("Migrando Redis...")
    r = get_redis_client()
    r.set("app_status", "initialized")
    print("Redis migrado con éxito.")

def migrate_cassandra():
    print("Migrando Cassandra...")
    cluster, session = get_cassandra_session()
    
    # Drop old tables if they exist to clean keyspace
    session.execute("DROP TABLE IF EXISTS match_stats_by_day;")
    session.execute("DROP TABLE IF EXISTS profile_swipes_by_day;")
    session.execute("DROP TABLE IF EXISTS profile_swipes_total;")
    session.execute("DROP TABLE IF EXISTS conversation_to_event_duration;")
    
    # Drop Spanish tables if they exist for clean rebuild
    session.execute("DROP TABLE IF EXISTS estadisticas_coincidencias_por_dia;")
    session.execute("DROP TABLE IF EXISTS swipes_perfil_por_dia;")
    session.execute("DROP TABLE IF EXISTS swipes_perfil_total;")
    session.execute("DROP TABLE IF EXISTS duracion_conversacion_a_evento;")
    
    # 1. estadisticas_coincidencias_por_dia
    session.execute("""
        CREATE TABLE IF NOT EXISTS estadisticas_coincidencias_por_dia (
            fecha date PRIMARY KEY,
            cantidad_coincidencias int,
            cantidad_fin_de_semana int,
            cantidad_feriado int
        )
    """)
    
    # 2. swipes_perfil_por_dia
    session.execute("""
        CREATE TABLE IF NOT EXISTS swipes_perfil_por_dia (
            fecha date,
            id_usuario_destino int,
            cantidad_likes int,
            PRIMARY KEY (fecha, id_usuario_destino)
        )
    """)
    
    # 3. swipes_perfil_total
    session.execute("""
        CREATE TABLE IF NOT EXISTS swipes_perfil_total (
            id_usuario_destino int PRIMARY KEY,
            cantidad_likes_total int
        )
    """)
    
    # 4. duracion_conversacion_a_evento
    session.execute("""
        CREATE TABLE IF NOT EXISTS duracion_conversacion_a_evento (
            id_evento int PRIMARY KEY,
            id_coincidencia int,
            cantidad_mensajes int
        )
    """)
    
    cluster.shutdown()
    print("Cassandra migrado con éxito.")

def migrate_neo4j():
    print("Migrando Neo4j...")
    driver = get_neo4j_driver()
    with driver.session() as session:
        # Constraints in Neo4j (using CREATE CONSTRAINT IF NOT EXISTS)
        session.run("CREATE CONSTRAINT idx_usuario_id IF NOT EXISTS FOR (u:Usuario) REQUIRE u.id_usuario IS UNIQUE")
        session.run("CREATE CONSTRAINT idx_interes_nombre IF NOT EXISTS FOR (i:Interes) REQUIRE i.nombre IS UNIQUE")
        session.run("CREATE CONSTRAINT idx_evento_id IF NOT EXISTS FOR (e:Evento) REQUIRE e.id_evento IS UNIQUE")
    driver.close()
    print("Neo4j migrado con éxito.")

if __name__ == "__main__":
    print("Iniciando migraciones de bases de datos...")
    try:
        migrate_postgres()
        migrate_mongodb()
        migrate_redis()
        migrate_cassandra()
        migrate_neo4j()
        print("Todas las migraciones se completaron con éxito.")
    except Exception as e:
        print(f"Error en migraciones: {e}", file=sys.stderr)
        sys.exit(1)
