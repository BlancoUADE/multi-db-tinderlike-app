"""
PostgreSQL schema setup.
"""


def ensure_postgres_schema(conn):
	"""Create all PostgreSQL tables with proper constraints"""
	with conn.cursor() as cur:
		cur.execute(
			"""
			CREATE TABLE IF NOT EXISTS usuarios (
				id_usuario SERIAL PRIMARY KEY,
				nombre TEXT NOT NULL,
				edad INTEGER NOT NULL CHECK (edad > 0),
				genero TEXT NOT NULL,
				ubicacion TEXT NOT NULL,
				biografia TEXT NOT NULL,
				pref_edad_min INTEGER NOT NULL CHECK (pref_edad_min > 0),
				pref_edad_max INTEGER NOT NULL CHECK (pref_edad_max > 0),
				fecha_registro TIMESTAMPTZ NOT NULL DEFAULT NOW(),
				CHECK (pref_edad_min <= pref_edad_max)
			);
			"""
		)
		cur.execute(
			"""
			CREATE TABLE IF NOT EXISTS intereses (
				id_interes SERIAL PRIMARY KEY,
				nombre TEXT NOT NULL UNIQUE
			);
			"""
		)
		cur.execute(
			"""
			CREATE TABLE IF NOT EXISTS usuario_intereses (
				id_usuario INTEGER NOT NULL REFERENCES usuarios(id_usuario) ON DELETE CASCADE,
				id_interes INTEGER NOT NULL REFERENCES intereses(id_interes) ON DELETE CASCADE,
				PRIMARY KEY (id_usuario, id_interes)
			);
			"""
		)
		cur.execute(
			"""
			CREATE TABLE IF NOT EXISTS fotos (
				id_foto SERIAL PRIMARY KEY,
				id_usuario INTEGER NOT NULL REFERENCES usuarios(id_usuario) ON DELETE CASCADE,
				url_archivo TEXT NOT NULL,
				es_principal BOOLEAN NOT NULL DEFAULT FALSE,
				fecha_subida TIMESTAMPTZ NOT NULL DEFAULT NOW()
			);
			"""
		)
		cur.execute(
			"""
			CREATE TABLE IF NOT EXISTS likes (
				id_like SERIAL PRIMARY KEY,
				id_usuario_origen INTEGER NOT NULL REFERENCES usuarios(id_usuario) ON DELETE CASCADE,
				id_usuario_destino INTEGER NOT NULL REFERENCES usuarios(id_usuario) ON DELETE CASCADE,
				fecha_like TIMESTAMPTZ NOT NULL DEFAULT NOW(),
				UNIQUE (id_usuario_origen, id_usuario_destino),
				CHECK (id_usuario_origen != id_usuario_destino)
			);
			"""
		)
		cur.execute(
			"""
			CREATE TABLE IF NOT EXISTS coincidencias (
				id_coincidencia SERIAL PRIMARY KEY,
				id_usuario1 INTEGER NOT NULL REFERENCES usuarios(id_usuario) ON DELETE CASCADE,
				id_usuario2 INTEGER NOT NULL REFERENCES usuarios(id_usuario) ON DELETE CASCADE,
				fecha_coincidencia TIMESTAMPTZ NOT NULL DEFAULT NOW(),
				UNIQUE (id_usuario1, id_usuario2),
				CHECK (id_usuario1 < id_usuario2)
			);
			"""
		)
		cur.execute(
			"""
			CREATE TABLE IF NOT EXISTS mensajes (
				id_mensaje SERIAL PRIMARY KEY,
				id_coincidencia INTEGER NOT NULL REFERENCES coincidencias(id_coincidencia) ON DELETE CASCADE,
				id_emisor INTEGER NOT NULL REFERENCES usuarios(id_usuario) ON DELETE CASCADE,
				contenido TEXT NOT NULL,
				fecha_envio TIMESTAMPTZ NOT NULL DEFAULT NOW()
			);
			"""
		)
		cur.execute(
			"""
			CREATE TABLE IF NOT EXISTS bloqueos (
				id_bloqueo SERIAL PRIMARY KEY,
				id_bloqueador INTEGER NOT NULL REFERENCES usuarios(id_usuario) ON DELETE CASCADE,
				id_bloqueado INTEGER NOT NULL REFERENCES usuarios(id_usuario) ON DELETE CASCADE,
				fecha_bloqueo TIMESTAMPTZ NOT NULL DEFAULT NOW(),
				UNIQUE (id_bloqueador, id_bloqueado),
				CHECK (id_bloqueador != id_bloqueado)
			);
			"""
		)
		cur.execute(
			"""
			CREATE TABLE IF NOT EXISTS eventos (
				id_evento SERIAL PRIMARY KEY,
				nombre_evento TEXT NOT NULL,
				fecha TIMESTAMPTZ NOT NULL,
				ubicacion TEXT NOT NULL,
				id_organizador INTEGER NOT NULL REFERENCES usuarios(id_usuario) ON DELETE CASCADE,
				fecha_creacion TIMESTAMPTZ NOT NULL DEFAULT NOW()
			);
			"""
		)
		cur.execute(
			"""
			CREATE TABLE IF NOT EXISTS asistencia_eventos (
				id_asistencia SERIAL PRIMARY KEY,
				id_evento INTEGER NOT NULL REFERENCES eventos(id_evento) ON DELETE CASCADE,
				id_usuario INTEGER NOT NULL REFERENCES usuarios(id_usuario) ON DELETE CASCADE,
				fecha_asistencia TIMESTAMPTZ NOT NULL DEFAULT NOW(),
				UNIQUE (id_evento, id_usuario)
			);
			"""
		)
		cur.execute(
			"""
			CREATE TABLE IF NOT EXISTS notificaciones (
				id_notificacion SERIAL PRIMARY KEY,
				id_usuario INTEGER NOT NULL REFERENCES usuarios(id_usuario) ON DELETE CASCADE,
				tipo TEXT NOT NULL,
				id_like INTEGER REFERENCES likes(id_like) ON DELETE SET NULL,
				id_coincidencia INTEGER REFERENCES coincidencias(id_coincidencia) ON DELETE SET NULL,
				id_mensaje INTEGER REFERENCES mensajes(id_mensaje) ON DELETE SET NULL,
				id_evento INTEGER REFERENCES eventos(id_evento) ON DELETE SET NULL,
				leida BOOLEAN NOT NULL DEFAULT FALSE,
				fecha_creacion TIMESTAMPTZ NOT NULL DEFAULT NOW()
			);
			"""
		)
		cur.execute(
			"""
			CREATE TABLE IF NOT EXISTS dias_festivos (
				fecha DATE PRIMARY KEY,
				descripcion TEXT NOT NULL
			);
			"""
		)
		cur.execute("CREATE INDEX IF NOT EXISTS idx_likes_destino ON likes(id_usuario_destino);")
		cur.execute("CREATE INDEX IF NOT EXISTS idx_mensajes_coincidencia ON mensajes(id_coincidencia);")
		cur.execute("CREATE INDEX IF NOT EXISTS idx_fotos_usuario ON fotos(id_usuario);")
		cur.execute("CREATE INDEX IF NOT EXISTS idx_usuario_intereses_interes ON usuario_intereses(id_interes);")

	conn.commit()
