# Tinderlike App - CLI Multi-Base de Datos

Este proyecto consiste en una aplicación de citas online interactiva operada a través de la interfaz de línea de comandos (CLI). Su característica principal es el uso de una arquitectura **híbrida multi-base de datos** con modelos relacionales, documentales, de clave-valor, series temporales y grafos.

---

## 1. Arquitectura y Justificación de Bases de Datos

El sistema integra cinco motores de bases de datos diferentes, cada uno optimizado para una función específica:

| Base de Datos | Tipo | Rol en el Sistema | Justificación Técnica |
| :--- | :--- | :--- | :--- |
| **PostgreSQL** | Relacional | **Fuente de verdad transaccional** | Garantiza consistencia estricta (ACID) para registros de usuarios, configuraciones, autenticación, notificaciones, likes, coincidencias, bloqueos e historiales de citas. |
| **Redis** | Clave-Valor | **Sesiones, contadores, alertas rápidas y caché** | Proporciona lecturas y escrituras de latencia sub-milisegundo para tokens de sesión (`TTL` automático), contadores atómicos de notificaciones no leídas, listas de alertas rápidas y caché de recomendaciones para evitar repeticiones de consultas complejas. |
| **MongoDB** | Documental | **Perfiles públicos y Logs de auditoría** | Almacena los perfiles en formato JSON denormalizado (incluyendo arrays de fotos e intereses) para lectura rápida sin joins. Registra eventos clave en una colección de logs históricos de actividad importante. |
| **Cassandra** | Series de Tiempo | **Analíticas masivas y Métricas** | Diseñada para escritura ultra-rápida y consultas agregadas específicas sobre series temporales (swipes diarios, estadísticas de matches diarios, duración promedio conversación-cita). |
| **Neo4j** | Grafo | **Grafo Social y Recomendaciones** | Modela el mapa de interacciones sociales (`Usuario`, `Interes`, `Evento`) y resuelve de forma instantánea el algoritmo de perfiles sugeridos priorizando intereses en común y descartando bloqueos en red. |

---

## 2. Decisiones Centrales del Modelo y Cambios al DER Original

1.  **Eventos como Citas Sociales**: En el sistema **no existe una tabla llamada `citas`**. Una cita social entre dos usuarios se representa como un `evento` propuesto de forma unilateral por un organizador a su receptor en base a una coincidencia (`id_coincidencia` obligatoria). La respuesta de asistencia (`asistencia_eventos`) representa la aceptación o rechazo.
2.  **Validaciones Estrictas**:
    *   Una cita solo puede proponerse si existe una coincidencia previa y no existe un bloqueo activo.
    *   No se permiten múltiples citas pendientes simultáneas en la misma coincidencia.
    *   Se implementa una restricción de una sola foto principal por usuario en PostgreSQL mediante un índice parcial único.
    *   Se evita el auto-like, auto-bloqueo y la duplicación de matches/bloqueos activos.
3.  **PostgreSQL como Fuente de Verdad (Single Source of Truth)**: Todas las operaciones de escritura crítica (Likes, Mensajes, Bloqueos, Registro) escriben primero en PostgreSQL. Si la transacción relacional es exitosa, se propagan las actualizaciones en cascada a NoSQL de forma resiliente ante fallos.

---

## 3. Instrucciones de Despliegue y Ejecución

### 3.1. Requisitos Previos
*   Python 3.11 instalado.
*   Docker y Docker Compose instalados.

### 3.2. Levantar la Infraestructura
1. Levantar los contenedores de las bases de datos en segundo plano:
   ```bash
   docker compose up -d
   ```
2. Verificar que todos los servicios estén corriendo:
   ```bash
   docker ps
   ```

### 3.3. Instalar Dependencias
Instalar las dependencias de Python listadas en `requirements.txt`:
```bash
pip install -r requirements.txt
```

### 3.4. Configurar Variables de Entorno
El archivo `.env` ya se encuentra configurado por defecto para apuntar a los puertos locales mapeados por Docker Compose. Si necesitas modificar las credenciales, puedes guiarte por `.env.example`.

### 3.5. Ejecutar Migraciones
Crea las tablas de Postgres, índices en Mongo, tablas en Cassandra y restricciones en Neo4j:
```bash
python scripts/migrate.py
```

### 3.6. Cargar Semilla de Datos (Seeds)
Puebla las bases de datos con 11 usuarios de prueba completos y estadísticas históricas:
```bash
python scripts/seed.py
```

### 3.7. Ejecutar el CLI
Inicia el programa interactivo:
```bash
python main.py
```

---

## 4. Estructura de Reportes Analíticos

Los siete reportes de negocio requeridos se resuelven en las siguientes bases de datos:

1.  **Promedio de coincidencias por día** (Cassandra):
    *   *Estrategia*: Lee la tabla `estadisticas_coincidencias_por_dia` y promedia la cantidad de coincidencias diarias en Python.
2.  **Atributos más populares en perfiles** (MongoDB):
    *   *Estrategia*: Pipeline de agregación (`aggregate` con `$group`, `$unwind` y `$avg`) sobre la colección denormalizada `perfiles_publicos` para géneros, ubicaciones, edades, intereses comunes y cantidad de fotos.
3.  **Perfiles con más swipes a la derecha** (Redis):
    *   *Estrategia*: Ranking diario consultado en el Sorted Set de Redis (`top_swipes_dia`).
4.  **Cantidad promedio de mensajes antes de una cita** (Cassandra):
    *   *Estrategia*: Agrega la cantidad de mensajes antes de proponer la cita registradas en la tabla `mensajes_por_evento` y calcula su promedio general.
5.  **Intereses más comunes entre usuarios que coinciden** (Neo4j):
    *   *Estrategia*: Consulta en Cypher buscando parejas en relación `(:Usuario)-[:COINCIDIO_CON]-(:Usuario)` y contando las intersecciones en `[:TIENE_INTERES]`.
6.  **Perfiles con más de 10 fotos y al menos 3 intereses en común** (MongoDB + Neo4j):
    *   *Estrategia*: MongoDB filtra los usuarios con `cantidad_fotos > 10`. Luego, Neo4j recibe los IDs y calcula mediante Cypher cuáles tienen 3 o más intereses compartidos con el usuario logueado.
7.  **Coincidencias en fin de semana o feriados** (Cassandra + Postgres):
    *   *Estrategia*: Consulta `estadisticas_coincidencias_por_dia` en Cassandra para calcular los totales acumulados y porcentajes de coincidencia sobre días festivos y fines de semana.
