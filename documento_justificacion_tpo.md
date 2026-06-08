# Documento de Justificación Técnica
## TPO - Aplicación Tinder-like con Persistencia Políglota

**Materia:** Ingeniería de Datos 2  
**Integrantes:** Agustin Blanco, Bruno Roude, Felipe Urien, Jose  
**Fecha:** 7 de junio de 2026  

---

## 1. Introducción

El presente documento detalla y justifica las decisiones arquitectónicas y de diseño de datos tomadas durante el desarrollo del Trabajo Práctico Obligatorio (TPO) de la materia Ingeniería de Datos 2. 

El proyecto consistió en el desarrollo de una aplicación interactiva por consola (CLI) que simula la funcionalidad central de Tinder (una plataforma de citas en línea), incluyendo la gestión de perfiles, la acción de dar "me gusta" (swipes), el matcheo entre usuarios, el intercambio de mensajes en tiempo real, la posibilidad de bloquear contactos y la organización de eventos sociales.

El desafío principal del TPO fue migrar de un diseño monolítico tradicional (representado en un Diagrama Entidad-Relación inicial) hacia una arquitectura de **persistencia políglota**. Este enfoque implica la utilización coordinada de múltiples motores de bases de datos, seleccionando cada uno de ellos en función de las ventajas inherentes de su modelo de almacenamiento. El objetivo de este documento es explicar en detalle el *porqué* de cada elección, demostrando cómo la naturaleza de los datos determina la herramienta óptima para su gestión, garantizando así escalabilidad, rendimiento y mantenibilidad.

---

## 2. Arquitectura General y Roles de los Motores

Para soportar las distintas cargas de trabajo (operacionales, de lectura rápida, analíticas y de recorrido de redes), la aplicación distribuye su persistencia entre cinco motores especializados:

| Motor de Base de Datos | Modelo de Almacenamiento | Rol Asignado en la Aplicación |
| :--- | :--- | :--- |
| **PostgreSQL 16** | Relacional (SQL) | Identidades estructurales de usuarios, registro legal de eventos, asistencias, y auditoría de bloqueos. |
| **MongoDB 7** | Documental (BSON) | Perfiles extendidos y flexibles, arrays dinámicos (fotos), historiales y notificaciones. |
| **Redis 7** | Clave-Valor (In-Memory) | Sesiones de usuario (TTL), set de usuarios conectados y caché temporal de candidatos. |
| **Cassandra 4.1** | Familia de Columnas (Wide Column) | Series de tiempo para logs masivos: swipes históricos, matches diarios y mensajería de chat. |
| **Neo4j 5** | Grafos (Property Graph) | Red social profunda: likes, relaciones de coincidencia (matches), intereses, bloqueos y asistencias a eventos. |

---

## 3. Análisis del DER Original vs. Implementación Final

La consigna original partía de un modelo relacional monolítico. A continuación, justificamos cómo y por qué desensamblamos este modelo distribuyendo sus entidades a lo largo de nuestro ecosistema políglota.

### 3.1. Partición de la tabla `usuarios` (PostgreSQL + MongoDB)
*   **Modelo Original:** Una única tabla `usuarios` que contenía atributos estrictos (email, fecha de registro) mezclados con atributos variables y descriptivos (biografía, preferencias de edad).
*   **Nuestra Implementación:** La identidad estructural y las restricciones críticas se mantienen en **PostgreSQL**, mientras que los datos flexibles se migran a una colección `perfiles` en **MongoDB**.
*   **Justificación Técnica:** Los datos como la edad, el género y la ubicación son pivotes para la lógica de negocio y requieren validaciones estrictas (tipado estricto, unicidad de email, constraints como `edad >= 18`). Por otro lado, campos como la biografía o las características personales (ej. "signo zodiacal", "altura") varían inmensamente entre usuarios. Si mantuviéramos esto en PostgreSQL, sufriríamos de esquemas rígidos, columnas con altos índices de valores `NULL` o la necesidad de utilizar costosas tablas puente (Entity-Attribute-Value). MongoDB, con su esquema flexible, nos permite almacenar un documento rico y variable por cada usuario.

### 3.2. Eliminación de la tabla relacional `fotos` (Embebido en MongoDB)
*   **Modelo Original:** Una tabla `fotos` con una clave foránea hacia el usuario.
*   **Nuestra Implementación:** Las fotos se almacenan como un arreglo (`fotos[]`) directamente dentro del documento del perfil en MongoDB.
*   **Justificación Técnica:** En el dominio de nuestra aplicación, las fotos pertenecen exclusivamente a un usuario y siempre se consultan en el contexto de la visualización de su perfil. En un modelo relacional, esto exige un `JOIN` constante. Al embeber este arreglo dinámico dentro del documento BSON de MongoDB, obtenemos el perfil completo en una única operación de lectura a disco, optimizando dramáticamente la latencia de acceso.

### 3.3. Distribución de los `likes` (Neo4j + Cassandra)
*   **Modelo Original:** Una tabla transaccional de cruce entre `usuario_origen` y `usuario_destino`.
*   **Nuestra Implementación:** Los likes vivos operan en **Neo4j** como una arista (`LE_DIO_LIKE`), mientras que el log histórico de la acción se asienta en **Cassandra**.
*   **Justificación Técnica:** El "me gusta" tiene dos propósitos. Primero, detectar el *Match* (reciprocidad). En SQL, buscar si A le dio like a B y B le dio like a A requiere un costoso `Self-JOIN`. En Neo4j, esto se resuelve con un recorrido de red de orden O(1) comprobando la existencia de la arista inversa. El segundo propósito es el análisis masivo (ej. "cuántos likes se dieron hoy"). Como en una app tipo Tinder la escritura de swipes es masiva e incesante, Cassandra —optimizada para escrituras *append-only* masivas sin bloqueos en disco— es la herramienta perfecta para guardar este registro histórico.

### 3.4. Refinamiento de `coincidencias` (PostgreSQL + Neo4j + Cassandra)
*   **Modelo Original:** Tabla relacional `coincidencias`.
*   **Nuestra Implementación:** El registro formal (ACID) queda en **PostgreSQL**, la relación social en **Neo4j**, y el log analítico en **Cassandra**.
*   **Justificación Técnica:** Un match es una transacción oficial que habilita el chat; por ende, requiere consistencia fuerte (ACID) y llaves únicas, algo que PostgreSQL garantiza (`CHECK user_id_1 < user_id_2`). Simultáneamente, necesitamos que Neo4j sepa del match para no volver a sugerir a esa persona en la lista de candidatos (recorrido de exclusión). Finalmente, guardamos un registro de tiempo en Cassandra particionado por fecha, lo cual es vital para resolver eficientemente el requerimiento analítico de "matches generados por día".

### 3.5. Migración de `mensajes` (Cassandra)
*   **Modelo Original:** Tabla relacional con llaves foráneas a coincidencias y emisores.
*   **Nuestra Implementación:** Tabla `mensajes_por_conversacion` en Cassandra, usando `match_id` como clave de partición y `timestamp` como clave de agrupamiento (Clustering Key).
*   **Justificación Técnica:** La mensajería es el ejemplo canónico de series de tiempo. Los mensajes se escriben constantemente al final (append-only) y se leen secuencialmente para visualizar el chat. En PostgreSQL, insertar millones de mensajes causaría *lock contention* y degradación de índices B-Tree. Cassandra, particionando por conversación y ordenando físicamente en disco por fecha, permite insertar sin bloqueos y recuperar historiales enteros de manera instantánea y escalable. Reconocemos que en el contexto de un prototipo académico, la volumetría de datos no justifica por sí sola el uso de Cassandra frente a un motor relacional o documental. Sin embargo, su inclusión responde al objetivo pedagógico de experimentar con un motor de familia de columnas anchas (wide-column), comprendiendo su modelo de datos query-driven, la desnormalización intencional y las implicancias del teorema CAP (AP vs CP). Adicionalmente, el modelado query-driven de Cassandra nos obligó a diseñar tablas específicas para cada patrón de consulta (ej: `swipes_por_dia`, `swipes_recibidos_por_perfil`), lo cual demuestra un enfoque radicalmente distinto al diseño normalizado relacional y constituye un aprendizaje valioso. En un entorno de producción con millones de usuarios activos, este diseño escalaría horizontalmente sin modificaciones en la capa de datos.

### 3.6. Rediseño de `notificaciones` (MongoDB)
*   **Modelo Original:** Una tabla con múltiples foráneas opcionales (`id_like`, `id_mensaje`, etc.) que resultaban en columnas `NULL`.
*   **Nuestra Implementación:** Documentos polimórficos en MongoDB.
*   **Justificación Técnica:** El diseño original forzaba un esquema espaciado (sparse) donde cada fila dejaba vacías las claves foráneas que no correspondían a su tipo de evento. En MongoDB, creamos documentos que contienen exclusivamente los campos necesarios para cada tipo de notificación, evitando el desperdicio de espacio estructural y facilitando modificaciones futuras en los tipos de alertas.

### 3.7. Transformación de `intereses` (Neo4j)
*   **Modelo Original:** Tabla `intereses` y tabla puente `usuario_intereses`.
*   **Nuestra Implementación:** Nodos `(:Interes)` y aristas `(:Usuario)-[:TIENE_INTERES]->(:Interes)` en Neo4j.
*   **Justificación Técnica:** Calcular grados de afinidad (ej. "cuántos intereses comparten estos dos perfiles") en SQL implica unir la tabla de usuarios con la puente, luego con intereses, luego volver a la puente y al otro usuario, agrupando y contando (múltiples JOINs recursivos). En Neo4j, esta consulta (`MATCH (u1)-[:TIENE_INTERES]->(i)<-[:TIENE_INTERES]-(u2)`) se resuelve recorriendo directamente las aristas en memoria, ofreciendo un rendimiento inmensamente superior para los algoritmos de recomendación.

### 3.8. Manejo de `bloqueos` (Neo4j + PostgreSQL + MongoDB)
*   **Modelo Original:** Tabla relacional `bloqueos`.
*   **Nuestra Implementación:** Se inserta el nodo de bloqueo en Neo4j, se audita en PostgreSQL y se loguea en MongoDB.
*   **Justificación Técnica:** Cuando se bloquea a un usuario, la prioridad número uno es cortar la visibilidad inmediatamente. Neo4j nos permite, en una sola transacción Cypher, crear la arista `[:BLOQUEO]` y simultáneamente podar cualquier arista previa de `[:LE_DIO_LIKE]` o `[:MATCH_CON]`. Se mantiene PostgreSQL para tener un registro formal y auditable del evento.

### 3.9. Incorporación de Caché y Sesiones (Redis)
*   **Modelo Original:** Ausente.
*   **Nuestra Implementación:** Uso intensivo de Redis para tokens de sesión y colas pre-calculadas de candidatos.
*   **Justificación Técnica:** Para que el sistema sea realista, cada petición debe verificar si el usuario está autenticado. Si esta verificación golpeara PostgreSQL en cada swipe o envío de mensaje, colapsaría la base transaccional con I/O innecesario. Redis, al operar 100% en memoria RAM, provee validaciones en sub-milisegundos y permite la autodestrucción nativa de datos mediante TTL (Time-To-Live), ideal para sesiones expirables y cachés temporales de candidatos.

---

## 4. Flujos de Orquestación y Consistencia Eventual

En una arquitectura de bases de datos distribuidas heterogéneas, no existe un gestor global de transacciones ACID. Para abordar este desafío, adoptamos dos estrategias fundamentales:

1.  **Jerarquía de Criticidad y Rollbacks Manuales (Compensación):** 
    En flujos críticos como el *Registro de Usuario*, PostgreSQL es el árbitro principal. Si Postgres logra insertar la identidad, pero Neo4j o MongoDB fallan al instanciar el grafo o el perfil, la capa de servicios atrapa la excepción y ejecuta un comando explícito de compensación (un `DELETE` sobre Postgres) revirtiendo el sistema a un estado consistente.

2.  **Consistencia Eventual y Tolerancia a Fallos:** 
    Para operaciones secundarias, toleramos la eventualidad. Por ejemplo, al dar un "Like" que resulta en un "Match", la operación core es escribir el match en PostgreSQL y Neo4j. Si el guardado del log analítico en Cassandra, o la notificación push en MongoDB fallan, el sistema emite una advertencia al administrador de logs, pero **no** revierte el Match. Entendemos que perder una notificación no es lo suficientemente crítico como para invalidar una transacción de negocio socialmente valiosa para los usuarios.

---

## 5. Justificación de Motores para los Casos de Uso Analíticos

El trabajo exige la implementación de siete reportes complejos. Demostramos el valor de nuestra arquitectura resolviéndolos en las bases más aptas:

1.  **Promedio de coincidencias por día:**
    Se consulta la tabla `matches_por_dia` en **Cassandra**, que actúa como una serie de tiempo donde los datos ya están particionados eficientemente por fecha, evitando escaneos masivos (`FULL TABLE SCAN`) sobre tablas transaccionales.

2.  **Características más populares:**
    Se utiliza el marco de agregación de **MongoDB**. Al tener esquemas dinámicos, utilizamos operadores como `$objectToArray` para desanidar los diccionarios de características y agruparlos en memoria sin haber necesitado pre-definir columnas para cada rasgo posible.

3.  **Perfiles más populares (Top Swipes):**
    Consultamos la tabla `swipes_recibidos_por_perfil` en **Cassandra**, estructurada específicamente para contar acciones rápidas (Query-Driven Data Modeling) y eximir a la base relacional de métricas de vanidad.

4.  **Duración promedio de conversaciones antes de una cita:**
    Este reporte cruza información operacional legal (**PostgreSQL**: quiénes asistieron al mismo evento y si tenían un match) con la primera interacción conversacional histórica (**Cassandra**: extracción de la primera marca de tiempo del mensaje).

5.  **Intereses comunes entre parejas matcheadas:**
    Utilizamos la expresividad del lenguaje Cypher en **Neo4j** para buscar triángulos lógicos en el grafo: usuarios conectados por `MATCH_CON` que a su vez comparten caminos a nodos `Interes`.

6.  **Usuarios hiperactivos con intereses compartidos:**
    Combinamos filtros. Primero, **MongoDB** devuelve velozmente los IDs de usuarios con `$size(fotos) > 10`. Luego, le entregamos esos IDs en memoria a **Neo4j** para que filtre y ordene cuáles de ellos comparten más de 3 intereses, demostrando orquestación en la capa de aplicación.

7.  **Coincidencias en fines de semana o feriados:**
    Basándonos en la extracción de fechas pre-particionadas de **Cassandra**, el servidor Python procesa lógicamente el calendario (feriados argentinos y fines de semana), manteniendo la capa de base de datos concentrada estrictamente en la entrega masiva de datos y delegando la lógica de negocio temporal a la aplicación.

---

## 6. Conclusión

El pasaje de un esquema monolítico a un paradigma de persistencia políglota conlleva el desafío de la complejidad operativa y el manejo explícito de la consistencia en el código. Sin embargo, las ganancias en rendimiento, diseño guiado por el dominio y escalabilidad son abrumadoras. 

Al haber implementado este TPO distribuyendo responsabilidades, hemos logrado que las identidades se mantengan consistentes (PostgreSQL), los perfiles crezcan sin límites de estructura (MongoDB), la navegación por la red social sea instantánea (Neo4j), el registro de interacciones masivas soporte un alto flujo de escritura (Cassandra) y la gestión transitoria de sesiones libere recursos del sistema (Redis). Esta arquitectura resulta no solo adecuada para una aplicación del estilo de Tinder, sino que refleja los estándares técnicos utilizados por las empresas tecnológicas líderes en la actualidad.
