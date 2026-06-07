-- Create users table
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    edad INTEGER NOT NULL CHECK (edad >= 18),
    genero VARCHAR(50) NOT NULL,
    ubicacion VARCHAR(150) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
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

-- Create audit log table for blocks
CREATE TABLE IF NOT EXISTS bloqueos_auditoria (
    id SERIAL PRIMARY KEY,
    bloqueador_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    bloqueado_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    fecha TIMESTAMPTZ DEFAULT NOW()
);
