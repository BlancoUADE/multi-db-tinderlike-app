# multi-db-tinderlike-app
Sistema de aplicación de citas basado en múltiples bases de datos (PostgreSQL, MongoDB, Redis, Cassandra y Neo4j), enfocado en persistencia, analíticas e integración multi-modelo.

## Requisitos
- Python 3.11 (en Windows, Cassandra no soporta Python 3.12+)
- Docker / Docker Compose

## Puesta en marcha
1. Levantar los servicios:
   ```
   docker compose up -d
   ```
2. (Windows) Crear entorno con Python 3.11:
   ```
   py -3.11 -m venv .venv
   .\.venv\Scripts\activate
   ```
3. Instalar dependencias:
   ```
   pip install -r requirements.txt
   ```
4. Ejecutar el CLI:
   ```
   python main.py
   ```

Opcional: verificar conexiones a los 5 motores:
```
python test_connections.py
```

**Verificar que las bases de datos están corriendo Y tienen datos:**
```
python verify_databases.py
```

Este script muestra:
- ✅ Conexión exitosa a cada DB
- 📋 Tablas/Colecciones creadas
- 📈 Cantidad de registros en cada tabla
- 👥 Ejemplos de datos almacenados
- 📐 Esquema de estructuras
- 🔗 Relaciones entre datos

## Menú del CLI

El CLI proporciona las siguientes categorías de operaciones:

### Registrar
- Registrar usuario
- Crear interés
- Asignar interés a usuario
- Agregar foto

### Interactuar
- Dar like
- Enviar mensaje
- Bloquear usuario
- Crear evento
- Registrar asistencia a evento

### Consultar (✨ Nueva funcionalidad)
- **Listar usuarios** — Muestra todos los usuarios registrados
- **Ver perfil de usuario** — Muestra datos completos, intereses y fotos de un usuario
- **Ver likes** — Lista los últimos 20 likes registrados
- **Ver coincidencias (matches)** — Lista los últimos 20 matches
- **Ver mensajes de un match** — Muestra la conversación entre dos usuarios
- **Ver eventos** — Lista los últimos 20 eventos

### Analíticas
- Ejecuta los 7 casos de uso del enunciado:
  - Promedio de coincidencias por día
  - Intereses más populares
  - Usuarios con más swipes
  - Duración promedio de conversaciones
  - Intereses comunes entre usuarios
  - Perfiles con más de 10 fotos y ≥3 intereses comunes
  - Coincidencias en fines de semana y feriados

### Demo
- **Cargar datos demo** — Genera usuarios de prueba, intereses, likes, matches, mensajes y un evento
- **Limpiar todas las bases de datos** — Borra todos los datos de Postgres, MongoDB, Redis y Cassandra para empezar de cero

## Arquitectura Multi-DB

El proyecto utiliza 5 bases de datos especializadas:

- **🐘 PostgreSQL**: Base relacional (fuente de verdad) — Usuarios, intereses, fotos, likes, matches, mensajes, eventos
- **🍃 MongoDB**: Documentos desnormalizados — Perfiles completos para lectura rápida
- **🔴 Redis**: Cache en memoria — Contadores, notificaciones, sesiones
- **🔷 Cassandra**: Time-series — Timeline de mensajes optimizada por tiempo
- **🔗 Neo4j**: Grafo de relaciones — Likes, matches, relaciones entre usuarios

Cada DB es especialista en su tipo de datos y acceso. **Lee `MULTI_DB_STRATEGY.md` para detalles completos.**

## Flujo rápido de prueba
1. Ejecutar `python main.py`
2. Cargar datos demo (opción 19)
3. Consultar datos:
   - Opción 10: Listar usuarios
   - Opción 11: Ver perfiles detallados
   - Opción 12-15: Ver likes, matches, mensajes
   - Opción 17: Ejecutar analíticas
4. Para limpiar y volver a probar:
   - Opción 20: Limpiar todas las bases de datos
   - Opción 19: Cargar datos demo nuevamente
