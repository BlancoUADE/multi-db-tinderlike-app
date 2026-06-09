# 🎯 Explicación Completa del Proyecto TPO - Tinder CLI con Persistencia Políglota

> [!NOTE]
> Este documento te explica **todo** el proyecto para que puedas exponerlo con confianza. Está basado en un análisis exhaustivo de cada archivo del código fuente.

---

## 1. ¿Qué es el proyecto?

Es una **aplicación de consola (CLI)** que simula Tinder. Permite:
- Registrar usuarios, iniciar sesión
- Editar perfiles (biografía, fotos, intereses, características físicas)
- Buscar candidatos compatibles ordenados por intereses comunes
- Dar Like/Dislike (swipe) y detectar Matches automáticamente
- Chatear en tiempo real con los matches
- Bloquear usuarios
- Crear y asistir a eventos sociales
- Generar 7 reportes analíticos cruzados

**El desafío principal**: en lugar de usar UNA sola base de datos (como haría una app típica), el proyecto usa **5 bases de datos distintas** trabajando juntas. Esto se llama **Persistencia Políglota** y es la parte central del TPO.

---

## 2. Las 5 Bases de Datos y Su Rol

* **Aplicación Central (Python App)**: Se conecta directamente con las 5 bases de datos de forma paralela.
* **PostgreSQL (Relacional)**: Identidades, Matches oficiales, Eventos y Auditoría de bloqueos.
* **MongoDB (Documental)**: Perfiles flexibles, Fotos, Logs y Notificaciones.
* **Redis (Clave-Valor)**: Sesiones activas (TTL) y Caché de candidatos.
* **Cassandra (Columnar)**: Swipes históricos, Matches por día y Mensajes de chat.
* **Neo4j (Grafos)**: Likes, Matches sociales, Bloqueos, Intereses y Grafos de Eventos.

### Detalle de cada base:

| Base | Modelo | Qué guarda | ¿Por qué esta y no otra? |
|------|--------|------------|--------------------------|
| **PostgreSQL** | Relacional (SQL) | Tabla `users` (id, nombre, email, password, edad, género, ubicación), tabla `coincidencias_confirmadas`, tabla `events`, tabla `asistencia_eventos`, tabla `bloqueos_auditoria` | Necesitamos **consistencia ACID**, llaves foráneas, constraints (`CHECK edad >= 18`), unicidad de email. Es la "fuente de verdad" para la identidad del usuario. |
| **MongoDB** | Documental (BSON) | Colección `perfiles` (biografía, fotos[], caracteristicas{}, preferencias{}), `historial_login`, `historial_cambios_perfil`, `notificaciones` | Los perfiles tienen **esquema variable** (un usuario puede tener signo zodiacal, otro no). Las fotos son un **array embebido** que evita JOINs. Las notificaciones son **polimórficas** (diferentes campos según el tipo). |
| **Redis** | Clave-Valor en RAM | Keys `session:{token}` → user_id (con TTL de 1 hora), Set `users:online`, List `candidates:{user_id}` (con TTL de 5 min) | Opera 100% en **memoria RAM** con latencia de sub-milisegundo. Cada acción (swipe, mensaje) necesita validar la sesión; si esto golpeara PostgreSQL, colapsaría con I/O innecesario. |
| **Cassandra** | Wide Column | Tablas `swipes_por_dia`, `swipes_recibidos_por_perfil`, `mensajes_por_conversacion`, `matches_por_dia`, `actividad_usuario_por_fecha` | Optimizada para **escrituras masivas append-only** sin bloqueos. Los mensajes y swipes son series de tiempo que se escriben constantemente. La mensajería se particiona por `match_id` y se ordena por `timestamp ASC`. |
| **Neo4j** | Grafos (Property Graph) | Nodos: `Usuario`, `Interes`, `Evento`. Relaciones: `LE_DIO_LIKE`, `DESCARTO`, `MATCH_CON`, `BLOQUEO`, `TIENE_INTERES`, `ORGANIZA`, `ASISTE_A` | Detectar reciprocidad de likes es un **recorrido de arista O(1)** en grafos, vs un costoso Self-JOIN en SQL. Calcular intereses compartidos es recorrer aristas, no hacer múltiples JOINs recursivos. |

---

## 3. Arquitectura de Capas del Código

* **Capa de Presentación**:
  * `src/cli/menu.py` (TinderCLI) interactúa con el usuario.
* **Capa de Servicio (Orquestador)**:
  * `src/services/app_service.py` (AppService)
  * `src/analytics/reports.py` (ReportService)
* **Capa de Repositorios (Acceso a Datos)**:
  * Repositorios individuales: `postgres_repo.py`, `mongo_repo.py`, `redis_repo.py`, `neo4j_repo.py`, `cassandra_repo.py`.
* **Capa de Conexión**:
  * `src/database/connection.py` y `src/database/initialize.py`.

### Archivos clave:

| Archivo | Líneas | Qué hace |
|---------|--------|----------|
| [main.py](file:///c:/Users/Bruno/Documents/Facu/multi-db-tinderlike-app/main.py) | 14 | Punto de entrada. Instancia `TinderCLI` y ejecuta `cli.run()` |
| [connection.py](file:///c:/Users/Bruno/Documents/Facu/multi-db-tinderlike-app/src/database/connection.py) | 104 | Funciones factory para conectarse a las 5 bases (lee `.env` con defaults) |
| [initialize.py](file:///c:/Users/Bruno/Documents/Facu/multi-db-tinderlike-app/src/database/initialize.py) | 137 | Crea los esquemas: tablas SQL, colecciones Mongo, tablas Cassandra, constraints Neo4j |
| [app_service.py](file:///c:/Users/Bruno/Documents/Facu/multi-db-tinderlike-app/src/services/app_service.py) | 693 | **El cerebro del proyecto.** Orquesta las 5 bases en cada operación de negocio |
| [menu.py](file:///c:/Users/Bruno/Documents/Facu/multi-db-tinderlike-app/src/cli/menu.py) | 550 | Interfaz CLI con menús, inputs, y visualización de datos |
| [reports.py](file:///c:/Users/Bruno/Documents/Facu/multi-db-tinderlike-app/src/analytics/reports.py) | 740 | 7 reportes analíticos + función de seeding de datos demo |
| [postgres_repo.py](file:///c:/Users/Bruno/Documents/Facu/multi-db-tinderlike-app/src/repositories/postgres_repo.py) | 352 | CRUD sobre las 5 tablas de PostgreSQL |
| [mongo_repo.py](file:///c:/Users/Bruno/Documents/Facu/multi-db-tinderlike-app/src/repositories/mongo_repo.py) | 116 | Perfiles, logs de login, historial de cambios, notificaciones |
| [redis_repo.py](file:///c:/Users/Bruno/Documents/Facu/multi-db-tinderlike-app/src/repositories/redis_repo.py) | 54 | Sesiones (con TTL), set de online, cola de candidatos |
| [neo4j_repo.py](file:///c:/Users/Bruno/Documents/Facu/multi-db-tinderlike-app/src/repositories/neo4j_repo.py) | 222 | Nodos, relaciones, exclusiones, reciprocidad, priorización |
| [cassandra_repo.py](file:///c:/Users/Bruno/Documents/Facu/multi-db-tinderlike-app/src/repositories/cassandra_repo.py) | 104 | Registro de swipes, matches, mensajes (series de tiempo) |

---

## 4. Los Flujos de Negocio Paso a Paso

Estos son los flujos que tenés que saber explicar. Cada uno muestra cómo interactúan las bases.

### 🔵 Flujo A: Registro de Usuario

**Pasos del flujo:**
1. **Usuario (CLI)** envía datos de registro a la App.
2. **App** consulta a PostgreSQL si el email existe.
3. **PostgreSQL** lo crea y devuelve un nuevo `user_id`.
4. **App** pide a MongoDB crear el documento de perfil.
5. **MongoDB** crea el documento vacío de perfil y fotos.
6. **App** pide a Neo4j crear el nodo del Usuario.
7. **Neo4j** confirma creación.
8. **App** avisa al usuario que el registro fue exitoso.

> **Rollback manual**: Si MongoDB falla → se borra el user de PostgreSQL. Si Neo4j falla → se borra el perfil de Mongo Y el user de Postgres. Esto es **compensación manual** (no hay transacciones distribuidas ACID).

**Código**: [register_user](file:///c:/Users/Bruno/Documents/Facu/multi-db-tinderlike-app/src/services/app_service.py#L27-L74)

---

### 🔵 Flujo B: Login

**Pasos del flujo:**
1. **Usuario (CLI)** envía credenciales (email y password).
2. **App** consulta a PostgreSQL buscando al usuario.
3. **PostgreSQL** devuelve el hash de la contraseña.
4. **App** verifica el hash localmente.
5. **App** envía a MongoDB el registro (log) de intento de login.
6. **App** crea un Token y lo guarda en Redis con un TTL (tiempo de vida) de 1 hora.
7. **App** agrega el ID del usuario al SET de usuarios online en Redis.
8. **App** devuelve el Token al usuario.

> **Tolerancia**: Si MongoDB falla al loguear el intento exitoso, se emite un warning pero el login continúa. Redis es obligatorio (sin sesión no hay app).

**Código**: [login_user](file:///c:/Users/Bruno/Documents/Facu/multi-db-tinderlike-app/src/services/app_service.py#L76-L134)

---

### 🔵 Flujo C: Búsqueda de Candidatos (con caché)

**Pasos del flujo:**
1. **App** busca la caché de candidatos del usuario en Redis.
2. Si **no hay caché**, inicia la generación:
   * **App** obtiene las preferencias desde MongoDB (ej: edad 20-35).
   * **App** obtiene usuarios a excluir desde Neo4j (ya likeados, bloqueados).
   * **App** filtra demográficamente usando PostgreSQL.
   * **App** ordena la lista resultante usando Neo4j (según intereses en común).
   * **App** guarda la lista final ordenada en Redis (caché de 5 min).
3. **App** extrae (LPOP) el primer candidato de la caché de Redis.
4. **App** obtiene los datos relacionales de PostgreSQL y perfil completo desde MongoDB para ese candidato.
5. **App** devuelve el perfil completo al Usuario.

> **Detalle importante**: La lista de candidatos se cachea en Redis por 5 minutos. Si la lista no está, se regenera consultando MongoDB (preferencias), Neo4j (exclusiones + ranking), y PostgreSQL (filtro demográfico).

**Código**: [get_next_candidate](file:///c:/Users/Bruno/Documents/Facu/multi-db-tinderlike-app/src/services/app_service.py#L230-L303)

---

### 🔵 Flujo D: Swipe con Match (el más complejo)

**Pasos del flujo:**
1. **App** registra el Like ("LE_DIO_LIKE") en Neo4j.
2. **App** guarda el Swipe como registro histórico en Cassandra.
3. **App** revisa en Neo4j si hay reciprocidad (¿el otro usuario también le dio Like?).
4. Si hay reciprocidad, ¡Es un MATCH!:
   * Se registra el Match oficial en PostgreSQL.
   * Se registra el log del Match en Cassandra por día.
   * Se crea la relación "MATCH_CON" en Neo4j.
   * Se envía notificación a ambos usuarios usando MongoDB.

> **Jerarquía de criticidad**:
> - PostgreSQL (match oficial) → **OBLIGATORIO**. Si falla, se hace rollback del like en Neo4j.
> - Neo4j (relación social) → **Importante** pero tolera consistencia eventual.
> - Cassandra (log histórico) → **Secundario**. Warning si falla.
> - MongoDB (notificación) → **Secundario**. Warning si falla.

**Código**: [hacer_swipe](file:///c:/Users/Bruno/Documents/Facu/multi-db-tinderlike-app/src/services/app_service.py#L316-L421)

---

### 🔵 Flujo E: Mensajería

**Pasos del flujo:**
1. **App** valida que la sesión existe en Redis.
2. **App** verifica en PostgreSQL que el Match es válido.
3. **App** guarda el mensaje en Cassandra, agrupado por la conversación (`match_id`) y ordenado por fecha de envío.
4. **App** genera una notificación de nuevo mensaje para el receptor y la guarda en MongoDB.

> Los mensajes se guardan en Cassandra particionados por `match_id` y ordenados físicamente por `timestamp ASC`. Esto permite recuperar un historial de chat completo en una sola lectura secuencial de disco, sin locks.

**Código**: [enviar_mensaje](file:///c:/Users/Bruno/Documents/Facu/multi-db-tinderlike-app/src/services/app_service.py#L443-L481)

---

### 🔵 Flujo F: Bloqueo de Usuario

**Pasos del flujo:**
1. **App** registra en Neo4j la relación de "BLOQUEO" y automáticamente elimina los Likes o Matches previos que hubiera entre ambos.
2. **App** inserta el bloqueo en la tabla de auditoría legal de PostgreSQL.
3. **App** inserta un log en la colección de bloqueos de MongoDB para analíticas.

**Código**: [bloquear_usuario](file:///c:/Users/Bruno/Documents/Facu/multi-db-tinderlike-app/src/services/app_service.py#L522-L551)

---

## 5. Los 7 Reportes Analíticos

Cada reporte demuestra cómo las bases colaboran para resolver consultas complejas:

| # | Reporte | Base(s) usada(s) | Técnica clave |
|---|---------|-------------------|---------------|
| 1 | Promedio de coincidencias por día | **Cassandra** | Lee `matches_por_dia` particionada por fecha |
| 2 | Características más populares | **MongoDB** | Aggregation pipeline: `$objectToArray` → `$unwind` → `$group` |
| 3 | Perfiles más populares (top likes) | **Cassandra** + PostgreSQL | Lee `swipes_recibidos_por_perfil`, ordena en Python, enriquece con nombres de PG |
| 4 | Duración promedio de chat antes de cita | **PostgreSQL** + **Cassandra** | PG: JOIN matches + asistencias + eventos. Cassandra: primer timestamp de mensaje |
| 5 | Intereses comunes en matches | **Neo4j** | Cypher: `MATCH (u1)-[:MATCH_CON]->(u2)` + `[:TIENE_INTERES]->(i)` compartido |
| 6 | Usuarios hiperactivos con intereses compartidos | **MongoDB** + **Neo4j** | Mongo: `$size(fotos) > 10` → IDs. Neo4j: filtra pares con ≥3 intereses comunes |
| 7 | Matches en fines de semana/feriados | **Cassandra** + Python | Cassandra: extrae fechas. Python: filtra por `weekday()` y lista de feriados argentinos |

**Código**: [reports.py](file:///c:/Users/Bruno/Documents/Facu/multi-db-tinderlike-app/src/analytics/reports.py)

---

## 6. Infraestructura (Docker)

El [docker-compose.yml](file:///c:/Users/Bruno/Documents/Facu/multi-db-tinderlike-app/docker-compose.yml) levanta 5 contenedores:

| Servicio | Imagen | Puerto externo |
|----------|--------|----------------|
| PostgreSQL | `postgres:16` | `5433` |
| MongoDB | `mongo:7` | `27017` |
| Redis | `redis:7` | `6379` |
| Cassandra | `cassandra:4.1` | `9042` |
| Neo4j | `neo4j:5` | `7474` (web) + `7687` (bolt) |

Cada uno tiene un volumen persistente para no perder datos al reiniciar.

---

## 7. Esquemas de Datos Detallados

### PostgreSQL (5 tablas)

```sql
-- Identidad del usuario (fuente de verdad)
users (id SERIAL PK, nombre, email UNIQUE, password_hash, edad CHECK(>=18), genero, ubicacion, created_at)

-- Matches confirmados (transacción ACID)
coincidencias_confirmadas (id SERIAL PK, user_id_1 FK, user_id_2 FK, created_at, UNIQUE(u1,u2), CHECK(u1<u2))

-- Eventos sociales
events (id SERIAL PK, organizador_id FK, titulo, descripcion, ubicacion, fecha_hora, created_at)

-- Asistencia a eventos
asistencia_eventos (user_id FK, evento_id FK, created_at, PK(user_id, evento_id))

-- Auditoría de bloqueos
bloqueos_auditoria (id SERIAL PK, bloqueador_id FK, bloqueado_id FK, fecha)
```

### MongoDB (4+ colecciones)

```json
// perfiles (índice único en user_id)
{
  "user_id": 5,
  "biografia": "...",
  "fotos": ["img1.jpg", "img2.jpg", ...],    // Array embebido
  "preferencias": {"edad_min": 20, "edad_max": 35, "genero_interes": "Femenino"},
  "caracteristicas": {"signo": "Escorpio", "altura": 178, "color_pelo": "Castaño"},
  "created_at": ..., "updated_at": ...
}

// notificaciones (polimórficas)
{"user_id": 5, "mensaje": "...", "tipo": "match|mensaje|evento|evento_asistencia", "leido": false, "timestamp": ...}

// historial_login
{"email": "...", "user_id": 5, "exito": true, "motivo": "Inicio exitoso", "ip": "...", "timestamp": ...}

// historial_cambios_perfil
{"user_id": 5, "campo_modificado": "biografia", "valor_anterior": "...", "valor_nuevo": "...", "timestamp": ...}
```

### Cassandra (5 tablas)

```sql
-- Swipes por día (Partition Key = fecha)
swipes_por_dia (fecha date, swipe_id uuid, user_from int, user_to int, tipo text, PK(fecha, swipe_id))

-- Swipes recibidos por perfil (para ranking)
swipes_recibidos_por_perfil (user_to int, tipo text, swipe_id uuid, user_from int, fecha timestamp, PK(user_to, tipo, swipe_id))

-- Mensajes por conversación (serie de tiempo)
mensajes_por_conversacion (match_id int, timestamp timestamp, message_id uuid, sender_id int, texto text, PK(match_id, timestamp)) CLUSTERING ORDER BY (timestamp ASC)

-- Matches por día
matches_por_dia (fecha date, match_id int, user_1 int, user_2 int, timestamp timestamp, PK(fecha, match_id))

-- Actividad del usuario
actividad_usuario_por_fecha (user_id int, fecha date, timestamp timestamp, actividad text, PK(user_id, fecha, timestamp)) CLUSTERING ORDER BY (fecha DESC, timestamp DESC)
```

### Neo4j (Nodos y Relaciones)

```
Nodos:
  (:Usuario {id, nombre})        → Constraint UNIQUE en id
  (:Interes {nombre})            → Constraint UNIQUE en nombre  
  (:Evento {id, titulo})         → Constraint UNIQUE en id

Relaciones:
  (Usuario)-[:LE_DIO_LIKE]->(Usuario)      → Like activo
  (Usuario)-[:DESCARTO]->(Usuario)          → Dislike (excluir de búsquedas)
  (Usuario)-[:MATCH_CON]->(Usuario)         → Match bidireccional
  (Usuario)-[:BLOQUEO]->(Usuario)           → Bloqueo unidireccional
  (Usuario)-[:TIENE_INTERES]->(Interes)     → Vínculo a intereses
  (Usuario)-[:ORGANIZA]->(Evento)           → Organizador del evento
  (Usuario)-[:ASISTE_A]->(Evento)           → Asistente inscripto
```

### Redis (Claves efímeras)

```
session:{uuid-token}    → user_id    (TTL: 3600 segundos = 1 hora)
users:online            → SET de user_ids conectados
candidates:{user_id}    → LIST de IDs de candidatos (TTL: 300 segundos = 5 min)
```

---

## 8. Estrategia de Consistencia (Punto Clave para Exposición)

> [!IMPORTANT]
> No existe un gestor global de transacciones ACID entre las 5 bases. El proyecto maneja esto con dos estrategias:

### Estrategia 1: Rollbacks Manuales (Compensación)
Para operaciones **críticas** donde la integridad es innegociable:
- **Registro**: Si MongoDB o Neo4j fallan, se ejecuta un `DELETE` en PostgreSQL para revertir el estado
- **Match**: Si PostgreSQL falla al crear el match, se borra el like de Neo4j

### Estrategia 2: Consistencia Eventual
Para operaciones **secundarias** cuyo fallo no justifica revertir la operación principal:
- **Notificaciones** (MongoDB): Si no se crea la notificación de match, el match sigue válido
- **Logs** (Cassandra): Si no se registra el swipe histórico, el like en Neo4j sigue existiendo
- **Relaciones** (Neo4j): Si `MATCH_CON` falla en Neo4j, el match existe en PostgreSQL (fuente de verdad)

---

## 9. Cómo Ejecutar la Demo

```powershell
# 1. Levantar los 5 contenedores
docker-compose up -d

# 2. Instalar dependencias Python
pip install -r requirements.txt

# 3. Inicializar esquemas en las 5 bases
python -m src.database.initialize

# 4. Ejecutar la app
python main.py

# 5. Dentro de la app: Opción 8 → 8 para poblar datos demo
# 6. Login como: carlos@testseed.com / password123
```

---

## 10. Preguntas Típicas del Profesor y Cómo Responderlas

### ❓ "¿Por qué no usaron solo PostgreSQL si soporta JSON?"
> PostgreSQL PUEDE hacer todo, pero degradaría el rendimiento en escala real. Millones de logs de swipes y mensajes saturarían los índices B-Tree. Las consultas de reciprocidad requieren Self-JOINs costosos que en Neo4j son O(1). Las sesiones en disco colapsarían el I/O vs Redis en RAM.

### ❓ "¿Qué pasa si una base se cae?"
> Depende de cuál. Si Redis se cae, nadie puede hacer login (es la que valida sesiones). Si Cassandra se cae, los swipes y mensajes se siguen registrando en Neo4j/PG pero se pierde el log histórico (warning). Si MongoDB se cae, no hay notificaciones pero los matches siguen funcionando. PostgreSQL es la fuente de verdad crítica.

### ❓ "¿Cómo manejan las transacciones distribuidas?"
> No usamos transacciones distribuidas (2PC/Saga formales). Usamos **compensación manual** para operaciones críticas (si falla la base secundaria, se revierte la primaria con un DELETE explícito) y **consistencia eventual** para operaciones secundarias (si falla una notificación o un log, no se revierte la operación principal).

### ❓ "¿Por qué Cassandra para mensajes y no PostgreSQL?"
> La mensajería es el caso canónico de series de tiempo: escrituras append-only constantes, lecturas secuenciales por conversación. En PostgreSQL, millones de inserts causarían *lock contention* y degradación de índices. Cassandra particiona por `match_id` y ordena físicamente por `timestamp`, permitiendo lecturas instantáneas y escalables sin bloqueos.

### ❓ "¿Cómo funciona la recomendación de candidatos?"
> Es un pipeline multi-base: MongoDB provee las preferencias del usuario, Neo4j provee la lista de exclusión (ya likeados/bloqueados/descartados) y luego ordena por intereses comunes, PostgreSQL filtra demográficamente (edad, género), y Redis cachea el resultado 5 minutos para evitar recalcular.

---

## 11. Dependencias Python

Archivo [requirements.txt](file:///c:/Users/Bruno/Documents/Facu/multi-db-tinderlike-app/requirements.txt):
- `psycopg2-binary` → Driver PostgreSQL
- `pymongo` → Driver MongoDB
- `redis` → Driver Redis
- `cassandra-driver` → Driver Cassandra
- `neo4j` → Driver Neo4j
- `python-dotenv` → Variables de entorno desde `.env`
