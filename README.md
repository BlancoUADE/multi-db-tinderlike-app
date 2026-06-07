# Tinder-Like Polyglot Persistence CLI Application (TPO)

Este proyecto es una aplicación interactiva por consola (CLI) de simulación de Tinder diseñada para demostrar de forma académica la **arquitectura e integración real de 5 motores de bases de datos** trabajando de forma coordinada (Persistencia Políglota).

---

## 1. Arquitectura y Modelo Políglota de Datos

Cada base de datos tiene una responsabilidad única y justificada en base a su modelo de almacenamiento y acceso de datos:

| Base de Datos | Modelo de Datos | Rol en la Aplicación | Justificación Técnica |
| :--- | :--- | :--- | :--- |
| **PostgreSQL** | Relacional (SQL) | Identidades estructurales de Usuarios, Coincidencias oficiales, Eventos y Asistencia. | Garantiza **consistencia ACID** estricta y llaves foráneas para identidades principales, inscripciones y transacciones de negocio. |
| **MongoDB** | Documental (BSON) | Perfil flexible de usuarios (biografía, fotos, rasgos dinámicos), logs de eventos y notificaciones. | Excelente para **esquemas flexibles y arrays dinámicos** (fotos, características físicas variables) sin requerir costosas tablas puente o alteraciones de esquemas relacionales. |
| **Redis** | Clave-Valor (In-Memory) | Sesiones de login activas (TTL), set de usuarios conectados (`users:online`) y cola de recomendación de perfiles (`candidates:{id}`). | Provee **latencia de sub-milisegundo** en memoria RAM. Evita sobrecargar con I/O de disco las operaciones transitorias (validar sesión en cada swipe/mensaje). |
| **Cassandra** | Ancho de columna (Column Family) | Eventos históricos de swipes, estadísticas de matches diarios, log de actividades e historial de mensajes de chat. | Optimizado para **escritura masiva append-only** y series de tiempo estructuradas por clave de partición, idóneo para Big Data de logs históricos y mensajería en tiempo real. |
| **Neo4j** | Grafos (Property Graph) | Relaciones de likes, descartes, bloqueos, intereses de usuarios, nodos de eventos y asistencia. | Permite realizar **recorridos de red ultra-rápidos** en memoria (salto de aristas) para recomendaciones, reciprocidad de likes, intereses compartidos o exclusiones de bloqueos. |

---

## 2. Guía de Ejecución Paso a Paso

### 2.1 Levantar la Infraestructura con Docker
Asegúrate de tener Docker y Docker Desktop iniciados en tu equipo. Abre una terminal de PowerShell en la raíz del proyecto y ejecuta:
```powershell
docker-compose up -d
```
Este comando levantará los 5 contenedores en segundo plano:
*   PostgreSQL: puerto `5433`
*   MongoDB: puerto `27017`
*   Redis: puerto `6379`
*   Cassandra: puerto `9042`
*   Neo4j: puerto `7687` (Bolt) | `7474` (HTTP Console)

### 2.2 Instalar Dependencias del Proyecto
Para instalar los controladores y librerías necesarias de Python (especificadas en [requirements.txt](file:///s:/UADE/2026/Ingenieria%20de%20Datos%20II/TPO/Trabajo%20Practico%20Proceso/multi-db-tiderlike-app/requirements.txt)), ejecuta en tu entorno de desarrollo:
```powershell
pip install -r requirements.txt
```

### 2.3 Inicializar Esquemas y Estructuras
Antes de ejecutar la aplicación, debes crear los esquemas relacionales, colecciones de MongoDB, tablas Cassandra y restricciones de Neo4j. Corre el script de inicialización:
```powershell
python -m src.database.initialize
```

*(Opcional: Si deseas validar que la conectividad con las 5 bases de datos sea 100% correcta antes de avanzar, ejecuta [test_connections.py](file:///s:/UADE/2026/Ingenieria%20de%20Datos%20II/TPO/Trabajo%20Practico%20Proceso/multi-db-tiderlike-app/test_connections.py)):*
```powershell
python test_connections.py
```

### 2.4 Correr la Aplicación CLI
Inicia la consola interactiva ejecutando:
```powershell
python main.py
```

---

## 3. Checklist de Pruebas Funcionales y Reportes

Durante la exposición, puedes realizar las siguientes pruebas utilizando el menú de la aplicación:

### Checklist Funcional:
- [ ] **Registrar un Usuario nuevo**: Comprueba que se crea en la base relacional, documental y grafos.
- [ ] **Iniciar sesión**: Valida el inicio de sesión contra Postgres, la escritura de log en MongoDB y la sesión en Redis.
- [ ] **Buscar candidatos recomendados**: Filtra por edad, género y descarta usuarios bloqueados/likeados (Neo4j/Mongo) mostrando los que tienen intereses comunes ordenados de forma descendente.
- [ ] **Dar Like y generar Match**: Comprobar que Neo4j detecta la reciprocidad, PostgreSQL escribe el match, Cassandra guarda el log y MongoDB alerta en las notificaciones.
- [ ] **Enviar y leer Mensajes**: Interactuar en el chat del match, escribiendo y recuperando el historial desde Cassandra en tiempo real.
- [ ] **Bloquear a un Usuario**: Bloquear a un contacto y verificar que se rompen de forma inmediata las relaciones de Match en Neo4j y no vuelva a aparecer en búsquedas.
- [ ] **Crear e Inscribirse a Eventos**: Organizar un evento (PostgreSQL + Neo4j) e inscribir a otro usuario, verificando la notificación al organizador.

### Checklist de Reportes (Fase 6):
- [ ] **Reporte 1**: Promedio de coincidencias por día (datos leídos de Cassandra `matches_por_dia`).
- [ ] **Reporte 2**: Características físicas y rasgos más populares (agregación de MongoDB sobre `perfiles`).
- [ ] **Reporte 3**: Top de perfiles más populares (lectura de likes en Cassandra, ordenados en Python).
- [ ] **Reporte 4**: Duración promedio de conversaciones antes de una cita (PG + Cassandra).
- [ ] **Reporte 5**: Intereses comunes entre parejas matcheadas (consulta de caminos Cypher en Neo4j).
- [ ] **Reporte 6**: Usuarios hiperactivos con intereses comunes (MongoDB `size(fotos) > 10` + Neo4j).
- [ ] **Reporte 7**: Coincidencias en fines de semana o feriados (Cassandra + filtro Python).

---

## 4. Guía de Defensa ante el Profesor

### Preguntas Críticas de la Exposición y cómo responderlas:

#### 1. ¿Por qué no guardaron toda la información en PostgreSQL si es más fácil y soporta JSON?
*   **Respuesta**: Si bien PostgreSQL podría almacenar todo, esto degradaría severamente el rendimiento y la escalabilidad del sistema real. Escribir millones de logs de swipes o mensajes de chats en Postgres colisionaría con los índices relacionales operacionales. Resolver relaciones sociales de coincidencia, bloqueos e intereses compartidos mediante consultas SQL de múltiples JOINs recursivos es ineficiente y lento en comparación con un motor de grafos como Neo4j. Almacenar sesiones transitorias en disco saturaría el I/O del servidor de base de datos relacional.

#### 2. ¿Qué ventaja tiene usar Cassandra para los Swipes y Mensajes?
*   **Respuesta**: En Tinder se generan miles de swipes y mensajes por segundo. Cassandra es una base de datos distribuida optimizada para escrituras masivas *append-only* en disco sin bloqueos. Está diseñada para almacenar series de tiempo ordenadas físicamente según una clave de partición (ej. por `match_id` para chats o por `fecha` para swipes), permitiendo búsquedas instantáneas cronológicas y liberando a PostgreSQL de cargas analíticas de logs.

#### 3. ¿Por qué se usa Redis si MongoDB también puede guardar sesiones?
*   **Respuesta**: Redis opera enteramente en memoria RAM (latencia de sub-milisegundo) y ofrece expiración nativa por TTL. MongoDB, al ser documental en disco, requiere actualizar índices B-Tree y escribir archivos de diario, lo que implica un consumo de recursos innecesario para sesiones transitorias que expiran rápidamente.

---

## 5. Cómo demostrar la interacción entre bases durante la exposición

Para lucirte ante el docente, puedes ejecutar la opción **`8. Reportes Analíticos` ➔ `8. [DEMO] Poblar base de datos...`** e iniciar sesión como **`carlos@testseed.com`** (contraseña **`password123`**). A continuación, abre los clientes de bases de datos o consolas y explica los flujos paso a paso:

### Flujo A: Registro de Usuario (Coordinación Relacional-Documental-Grafos)
Cuando un usuario se registra en la consola, el [AppService.register_user](file:///s:/UADE/2026/Ingenieria%20de%20Datos%20II/TPO/Trabajo%20Practico%20Proceso/multi-db-tiderlike-app/src/services/app_service.py#L27) realiza las siguientes operaciones:
1.  **PostgreSQL**: Crea el usuario en la tabla `users` y devuelve su ID único autoincremental (`user_id`).
2.  **MongoDB**: Toma el `user_id` y crea un documento de perfil en la colección `perfiles` con su estructura de fotos y rasgos vacíos.
3.  **Neo4j**: Toma el `user_id` y crea el nodo de tipo `(:Usuario {id: user_id, nombre: nombre})`.
*   *Manejo de fallas*: Si Neo4j o MongoDB fallan, se ejecuta un rollback manual aplicando un `DELETE` sobre PostgreSQL para evitar estados huérfanos.

### Flujo B: Swipe con Match (Orquestación Políglota de Negocio)
Cuando un usuario da Like a un candidato compatible:
1.  **Redis**: El [AppService](file:///s:/UADE/2026/Ingenieria%20de%20Datos%20II/TPO/Trabajo%20Practico%20Proceso/multi-db-tiderlike-app/src/services/app_service.py#L15) valida la sesión activa en memoria para autorizar la petición.
2.  **Neo4j**: Crea la relación `(:Usuario {id: u_desde})-[:LE_DIO_LIKE]->(:Usuario {id: u_hacia})` e interroga al grafo sobre la existencia de reciprocidad (`(u_hacia)-[:LE_DIO_LIKE]->(u_desde)`).
3.  **Cassandra**: Registra el evento de swipe en las tablas históricas `swipes_por_dia` y `swipes_recibidos_por_perfil` para la posteridad.
4.  **En caso de MATCH (Detección de reciprocidad en Neo4j)**:
    *   **PostgreSQL**: Registra el match en la tabla transaccional `coincidencias_confirmadas` y genera el `match_id` oficial.
    *   **Cassandra**: Guarda el log del match en `matches_por_dia`.
    *   **Neo4j**: Asciende las relaciones a `MATCH_CON` bidireccionales y elimina los likes cruzados.
    *   **MongoDB**: Crea alertas de notificación de match en la colección `notificaciones` para ambos perfiles.

### Flujo C: Envío de Mensajes (Transaccionalidad + Serie de Tiempo)
Al chatear en el CLI:
1.  **Redis**: Autentica al emisor usando su token de sesión.
2.  **PostgreSQL**: Verifica que el `match_id` pertenezca al usuario emisor y sea un match confirmado activo.
3.  **Cassandra**: Guarda de forma cronológica el mensaje en la tabla `mensajes_por_conversacion` (gracias a Clustering Key `timestamp ASC`).
4.  **MongoDB**: Registra una notificación en la base documental para alertar al receptor sobre el nuevo mensaje recibido.

### Flujo D: Reporte Analítico Cruzado 6 (MongoDB + Neo4j)
Muestra cómo las bases colaboran para calcular información valiosa:
1.  **MongoDB**: Filtra todos los documentos de la colección `perfiles` cuyo array de fotos es mayor a 10 y extrae una lista de IDs.
2.  **Neo4j**: Toma esa lista de IDs en memoria de Python y ejecuta una consulta Cypher buscando qué combinaciones de usuarios de ese conjunto comparten 3 o más nodos de la entidad `(:Interes)`.
3.  *Exposición*: Esto demuestra la combinación de filtros documentales flexibles y lógica de redes en grafos sin requerir queries inmensas y costosas de SQL.

### Flujo E: Reporte Analítico Cruzado 4 (PostgreSQL + Cassandra)
1.  **PostgreSQL**: Ejecuta un JOIN entre la tabla de `coincidencias_confirmadas`, `asistencia_eventos` (para ambos usuarios participantes del match) y `events` para identificar parejas que asistieron juntos al mismo evento social ("cita").
2.  **Cassandra**: Para cada pareja detectada por Postgres, se consulta la tabla `mensajes_por_conversacion` para extraer el timestamp del primer mensaje enviado.
3.  *Exposición*: Esto demuestra la correlación entre bases operacionales (Postgres) y bases de series de tiempo históricas de mensajería (Cassandra).
