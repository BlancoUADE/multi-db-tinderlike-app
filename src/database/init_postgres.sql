-- Create users table
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    edad INTEGER NOT NULL CHECK (edad >= 18),
    genero VARCHAR(50) NOT NULL,
    ubicacion VARCHAR(150) NOT NULL,
    biografia TEXT DEFAULT '',
    pref_edad_min INTEGER DEFAULT 18,
    pref_edad_max INTEGER DEFAULT 99,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Tabla fotos (DER)
CREATE TABLE IF NOT EXISTS fotos (
    id SERIAL PRIMARY KEY,
    id_usuario INTEGER REFERENCES users(id) ON DELETE CASCADE,
    url_archivo VARCHAR(500) NOT NULL,
    es_principal BOOLEAN DEFAULT FALSE,
    fecha_subida TIMESTAMPTZ DEFAULT NOW()
);

-- Create events table
CREATE TABLE IF NOT EXISTS events (
    id SERIAL PRIMARY KEY,
    organizador_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    titulo VARCHAR(150) NOT NULL,
    descripcion TEXT NOT NULL,
    ubicacion VARCHAR(150) NOT NULL,
    fecha_hora TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create event attendance table
CREATE TABLE IF NOT EXISTS asistencia_eventos (
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    evento_id INTEGER REFERENCES events(id) ON DELETE CASCADE,
    estado VARCHAR(50) DEFAULT 'confirmado',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (user_id, evento_id)
);

-- Create confirmed matches table
CREATE TABLE IF NOT EXISTS coincidencias_confirmadas (
    id SERIAL PRIMARY KEY,
    user_id_1 INTEGER REFERENCES users(id) ON DELETE CASCADE,
    user_id_2 INTEGER REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id_1, user_id_2),
    CHECK (user_id_1 < user_id_2)
);

-- Tabla likes (DER)
CREATE TABLE IF NOT EXISTS likes (
    id SERIAL PRIMARY KEY,
    id_usuario_origen INTEGER REFERENCES users(id) ON DELETE CASCADE,
    id_usuario_destino INTEGER REFERENCES users(id) ON DELETE CASCADE,
    tipo VARCHAR(20) NOT NULL DEFAULT 'like',  -- 'like' o 'dislike'
    fecha_like TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(id_usuario_origen, id_usuario_destino)
);

-- Tabla mensajes (DER)
CREATE TABLE IF NOT EXISTS mensajes (
    id SERIAL PRIMARY KEY,
    id_coincidencia INTEGER REFERENCES coincidencias_confirmadas(id) ON DELETE CASCADE,
    id_emisor INTEGER REFERENCES users(id) ON DELETE CASCADE,
    contenido TEXT NOT NULL,
    fecha_envio TIMESTAMPTZ DEFAULT NOW()
);

-- Tabla notificaciones (DER)
CREATE TABLE IF NOT EXISTS notificaciones (
    id SERIAL PRIMARY KEY,
    id_usuario INTEGER REFERENCES users(id) ON DELETE CASCADE,
    tipo VARCHAR(50) NOT NULL,
    id_like INTEGER REFERENCES likes(id) ON DELETE SET NULL,
    id_coincidencia INTEGER REFERENCES coincidencias_confirmadas(id) ON DELETE SET NULL,
    id_mensaje INTEGER REFERENCES mensajes(id) ON DELETE SET NULL,
    id_evento INTEGER REFERENCES events(id) ON DELETE SET NULL,
    leida BOOLEAN DEFAULT FALSE,
    fecha_creacion TIMESTAMPTZ DEFAULT NOW()
);

-- Tabla intereses (DER)
CREATE TABLE IF NOT EXISTS intereses (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(100) UNIQUE NOT NULL
);

-- Tabla usuario_intereses (DER)
CREATE TABLE IF NOT EXISTS usuario_intereses (
    id_usuario INTEGER REFERENCES users(id) ON DELETE CASCADE,
    id_interes INTEGER REFERENCES intereses(id) ON DELETE CASCADE,
    PRIMARY KEY (id_usuario, id_interes)
);

-- Create audit log table for blocks
CREATE TABLE IF NOT EXISTS bloqueos_auditoria (
    id SERIAL PRIMARY KEY,
    bloqueador_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    bloqueado_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    fecha TIMESTAMPTZ DEFAULT NOW()
);
