import re

with open('explicacion_proyecto.md', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace block 1
content = re.sub(r'```mermaid\s+graph TB.*?```', '''* **Aplicación Central (Python App)**: Se conecta directamente con las 5 bases de datos de forma paralela.
* **PostgreSQL (Relacional)**: Identidades, Matches oficiales, Eventos y Auditoría de bloqueos.
* **MongoDB (Documental)**: Perfiles flexibles, Fotos, Logs y Notificaciones.
* **Redis (Clave-Valor)**: Sesiones activas (TTL) y Caché de candidatos.
* **Cassandra (Columnar)**: Swipes históricos, Matches por día y Mensajes de chat.
* **Neo4j (Grafos)**: Likes, Matches sociales, Bloqueos, Intereses y Grafos de Eventos.''', content, flags=re.DOTALL)

# Replace block 2
content = re.sub(r'```mermaid\s+graph TD.*?```', '''* **Capa de Presentación**:
  * `src/cli/menu.py` (TinderCLI) interactúa con el usuario.
* **Capa de Servicio (Orquestador)**:
  * `src/services/app_service.py` (AppService)
  * `src/analytics/reports.py` (ReportService)
* **Capa de Repositorios (Acceso a Datos)**:
  * Repositorios individuales: `postgres_repo.py`, `mongo_repo.py`, `redis_repo.py`, `neo4j_repo.py`, `cassandra_repo.py`.
* **Capa de Conexión**:
  * `src/database/connection.py` y `src/database/initialize.py`.''', content, flags=re.DOTALL)

# Replace block 3 (Registro)
content = re.sub(r'```mermaid\s+sequenceDiagram\s+participant CLI.*?Registrado con ID 5\n```', '''**Pasos del flujo:**
1. **Usuario (CLI)** envía datos de registro a la App.
2. **App** consulta a PostgreSQL si el email existe.
3. **PostgreSQL** lo crea y devuelve un nuevo `user_id`.
4. **App** pide a MongoDB crear el documento de perfil.
5. **MongoDB** crea el documento vacío de perfil y fotos.
6. **App** pide a Neo4j crear el nodo del Usuario.
7. **Neo4j** confirma creación.
8. **App** avisa al usuario que el registro fue exitoso.''', content, flags=re.DOTALL)

# Replace block 4 (Login)
content = re.sub(r'```mermaid\s+sequenceDiagram\s+participant CLI as CLI\s+participant SVC as AppService\s+participant PG as PostgreSQL\s+participant MG as MongoDB\s+participant RD as Redis.*?Token de sesión\n```', '''**Pasos del flujo:**
1. **Usuario (CLI)** envía credenciales (email y password).
2. **App** consulta a PostgreSQL buscando al usuario.
3. **PostgreSQL** devuelve el hash de la contraseña.
4. **App** verifica el hash localmente.
5. **App** envía a MongoDB el registro (log) de intento de login.
6. **App** crea un Token y lo guarda en Redis con un TTL (tiempo de vida) de 1 hora.
7. **App** agrega el ID del usuario al SET de usuarios online en Redis.
8. **App** devuelve el Token al usuario.''', content, flags=re.DOTALL)

# Replace block 5 (Búsqueda)
content = re.sub(r'```mermaid\s+sequenceDiagram\s+participant CLI as CLI\s+participant SVC as AppService\s+participant RD as Redis\s+participant MG as MongoDB\s+participant N4 as Neo4j\s+participant PG as PostgreSQL.*?Perfil candidato completo\n```', '''**Pasos del flujo:**
1. **App** busca la caché de candidatos del usuario en Redis.
2. Si **no hay caché**, inicia la generación:
   * **App** obtiene las preferencias desde MongoDB (ej: edad 20-35).
   * **App** obtiene usuarios a excluir desde Neo4j (ya likeados, bloqueados).
   * **App** filtra demográficamente usando PostgreSQL.
   * **App** ordena la lista resultante usando Neo4j (según intereses en común).
   * **App** guarda la lista final ordenada en Redis (caché de 5 min).
3. **App** extrae (LPOP) el primer candidato de la caché de Redis.
4. **App** obtiene los datos relacionales de PostgreSQL y perfil completo desde MongoDB para ese candidato.
5. **App** devuelve el perfil completo al Usuario.''', content, flags=re.DOTALL)

# Replace block 6 (Swipe)
content = re.sub(r'```mermaid\s+sequenceDiagram\s+participant CLI as CLI\s+participant SVC as AppService\s+participant RD as Redis\s+participant N4 as Neo4j\s+participant CS as Cassandra\s+participant PG as PostgreSQL\s+participant MG as MongoDB.*?MATCH!!\n```', '''**Pasos del flujo:**
1. **App** registra el Like ("LE_DIO_LIKE") en Neo4j.
2. **App** guarda el Swipe como registro histórico en Cassandra.
3. **App** revisa en Neo4j si hay reciprocidad (¿el otro usuario también le dio Like?).
4. Si hay reciprocidad, ¡Es un MATCH!:
   * Se registra el Match oficial en PostgreSQL.
   * Se registra el log del Match en Cassandra por día.
   * Se crea la relación "MATCH_CON" en Neo4j.
   * Se envía notificación a ambos usuarios usando MongoDB.''', content, flags=re.DOTALL)

# Replace block 7 (Mensajes)
content = re.sub(r'```mermaid\s+sequenceDiagram\s+participant CLI as CLI\s+participant SVC as AppService\s+participant RD as Redis\s+participant PG as PostgreSQL\s+participant CS as Cassandra\s+participant MG as MongoDB.*?Mensaje enviado\n```', '''**Pasos del flujo:**
1. **App** valida que la sesión existe en Redis.
2. **App** verifica en PostgreSQL que el Match es válido.
3. **App** guarda el mensaje en Cassandra, agrupado por la conversación (`match_id`) y ordenado por fecha de envío.
4. **App** genera una notificación de nuevo mensaje para el receptor y la guarda en MongoDB.''', content, flags=re.DOTALL)

# Replace block 8 (Bloqueo)
content = re.sub(r'```mermaid\s+sequenceDiagram\s+participant SVC as AppService\s+participant N4 as Neo4j\s+participant PG as PostgreSQL\s+participant MG as MongoDB.*?log documental\)\n```', '''**Pasos del flujo:**
1. **App** registra en Neo4j la relación de "BLOQUEO" y automáticamente elimina los Likes o Matches previos que hubiera entre ambos.
2. **App** inserta el bloqueo en la tabla de auditoría legal de PostgreSQL.
3. **App** inserta un log en la colección de bloqueos de MongoDB para analíticas.''', content, flags=re.DOTALL)


with open('explicacion_proyecto.md', 'w', encoding='utf-8') as f:
    f.write(content)
