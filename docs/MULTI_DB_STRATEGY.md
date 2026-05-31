# Estrategia Multi-DB de Tinder - Mapeo de Datos

## 📋 Resumen de Datos por Base de Datos

Este documento explica **QUÉ datos van en CADA base de datos y POR QUÉ**.

---

## 1. 🐘 PostgreSQL - Base Relacional (Fuente de Verdad)

### ¿Por qué?
- **ACID**: Garantiza consistencia de datos críticos
- **Relaciones**: Las reglas de negocio (likes → matches) necesitan integridad referencial
- **Consultas complejas**: Analíticas con agregaciones

### Tablas (DER)
```
usuarios
├── id_usuario (PK)
├── nombre, edad, género, ubicación, biografía
├── pref_edad_min, pref_edad_max
└── fecha_registro

intereses
├── id_interes (PK)
└── nombre

usuario_intereses (M:N)
├── id_usuario (FK)
├── id_interes (FK)

fotos
├── id_foto (PK)
├── id_usuario (FK)
├── url_archivo, es_principal
└── fecha_subida

likes
├── id_like (PK)
├── id_usuario_origen (FK)
├── id_usuario_destino (FK)
├── fecha_like
└── UNIQUE(origen, destino) ← Evita duplicados

coincidencias (matches)
├── id_coincidencia (PK)
├── id_usuario1, id_usuario2 (FK)
├── fecha_coincidencia
├── CHECK(id_usuario1 < id_usuario2)
└── UNIQUE(usuario1, usuario2) ← Evita duplicados

mensajes
├── id_mensaje (PK)
├── id_coincidencia (FK)
├── id_emisor (FK)
├── contenido
└── fecha_envio

bloqueos
├── id_bloqueo (PK)
├── id_bloqueador (FK)
├── id_bloqueado (FK)
└── UNIQUE(bloqueador, bloqueado)

eventos
├── id_evento (PK)
├── nombre_evento, fecha, ubicación
├── id_organizador (FK)

asistencia_eventos
├── id_asistencia (PK)
├── id_usuario (FK)
├── id_evento (FK)
├── estado
└── fecha_registro

notificaciones
├── id_notificacion (PK)
├── id_usuario (FK)
├── tipo, mensaje
├── leída, fecha_creacion

dias_festivos
├── fecha (PK)
└── descripción
```

### Características
- ✅ Datos completos y normalizados
- ✅ Integridad referencial (FK, UNIQUE, CHECK)
- ✅ Consultas OLAP (analíticas)
- ✅ Fuente de verdad

---

## 2. 🍃 MongoDB - Documentos Denormalizados

### ¿Por qué?
- **Lectura rápida**: Perfiles completos sin JOINs
- **Flexibilidad**: Agregar campos sin migrations
- **Escalabilidad horizontal**: Si hay muchos perfiles

### Colecciones

#### `perfiles` (Perfil desnormalizado)
```javascript
{
  _id: ObjectId,
  id_usuario: 1,           // referencia a Postgres
  nombre: "Juan",
  edad: 28,
  género: "M",
  ubicación: "CABA",
  biografía: "Ingeniero...",
  pref_edad_min: 20,
  pref_edad_max: 35,
  intereses: [             // denormalizado (sacado de usuario_intereses)
    { id: 1, nombre: "Fútbol" },
    { id: 5, nombre: "Viajes" }
  ],
  fotos: [                 // denormalizado (sacado de fotos)
    {
      id: 101,
      url: "s3://...",
      es_principal: true,
      fecha_subida: ISODate("2024-01-15")
    }
  ],
  fecha_registro: ISODate("2024-01-01"),
  actualizado_en: ISODate("2024-01-20")
}
```

### Características
- ✅ Lectura ultra-rápida (sin JOINs)
- ✅ Datos desnormalizados para cache
- ✅ Flexible para nuevos campos
- ⚠️ Duplica datos de PostgreSQL (eventual consistency)

---

## 3. 🔴 Redis - Cache y Contadores en Memoria

### ¿Por qué?
- **Velocidad extrema**: Contadores sin hacer SELECT
- **Sesiones**: Notificaciones no leídas
- **TTL**: Datos que expiran (ej: cooldowns)

### Claves

```
# Contadores de notificaciones (actualizado en tiempo real)
notificaciones:sin_leer:{usuario_id}  → "3"          (Count)

# Contador de likes no procesados (para estadísticas rápidas)
likes:contador:{usuario_id}           → "42"          (Count)

# Sesiones activas
sesion:{usuario_id}:{token}           → "datos"       (String con TTL)

# Cooldowns de acciones
cooldown:like:{usuario1}:{usuario2}   → "1"           (String con TTL: 24h)

# Rankings en vivo (Sorted Set)
top:usuarios:swipes                   → {user_id: score} (Leaderboard)

# Mensajes no leídos por match
mensajes:sin_leer:{coincidencia_id}   → "5"           (Count)
```

### Características
- ✅ Velocidad O(1)
- ✅ Ideal para contadores
- ✅ TTL automático (expiración)
- ✅ Estructuras: String, Hash, List, Set, SortedSet
- ⚠️ Datos volátiles (si se reinicia, se pierden)

---

## 4. 🔷 Cassandra - Time-Series (Mensajes)

### ¿Por qué?
- **Optimizado para escritura**: Alta velocidad de INSERT
- **Time-series**: Logs ordenados por tiempo
- **Escalabilidad**: Distribuido por naturaleza
- **Retención**: Políticas de borrado automático

### Keyspace y Tablas

```
keyspace: tinder_app
├── replication_factor: 3
└── consistency_level: QUORUM

tabla: mensajes_timeline
├── id_coincidencia (Partition Key) ← Agrupa mensajes del match
├── fecha_envio (Clustering Key)    ← Orden temporal
├── id_mensaje
├── id_emisor
├── contenido
└── (Índices en: id_emisor, estado)
```

### Estructura de Datos
```
Coincidencia 42:
[
  { fecha: 2024-01-20T10:00, emisor: 1, contenido: "Hola!" },
  { fecha: 2024-01-20T10:05, emisor: 2, contenido: "¿Qué tal?" },
  { fecha: 2024-01-20T10:10, emisor: 1, contenido: "Bien, ¿y vos?" }
]
```

### Características
- ✅ Lecturas de rango temporal ultra-rápidas
- ✅ Escalable horizontalmente
- ✅ Replicación automática
- ⚠️ Complejo (puede haber demoras en Cassandra)

---

## 5. 🔗 Neo4j - Grafo de Relaciones

### ¿Por qué?
- **Relaciones complejas**: like → like mutuo → match
- **Consultas de grafo**: Amigos de amigos, recomendaciones
- **Rendimiento**: Traversals sin JOINs masivos

### Nodos

```
(:Usuario {
  id: 1,
  nombre: "Juan",
  edad: 28
})

(:Usuario {
  id: 2,
  nombre: "María",
  edad: 25
})
```

### Relaciones

```
(juan:Usuario)-[:DIO_LIKE {fecha: 2024-01-20}]->(maría:Usuario)
(maría:Usuario)-[:DIO_LIKE {fecha: 2024-01-21}]->(juan:Usuario)
(juan:Usuario)-[:MATCH {fecha: 2024-01-21}]->(maría:Usuario)
(juan:Usuario)-[:ENVIÓ_MENSAJE {fecha: 2024-01-21}]->(maría:Usuario)
(juan:Usuario)-[:BLOQUEÓ {fecha: 2024-01-20}]->(carlos:Usuario)
```

### Consultas Típicas
```cypher
// ¿Quién le dio like a María?
MATCH (u:Usuario)-[:DIO_LIKE]->(maria:Usuario {id: 2})
RETURN u.nombre, u.edad

// ¿María tiene match con alguien?
MATCH (maria:Usuario {id: 2})-[:MATCH]-(otro:Usuario)
RETURN otro.nombre

// ¿A quién le dio like María que también le dio like a ella?
MATCH (maria:Usuario {id: 2})-[:DIO_LIKE]->(otro)
WHERE (otro)-[:DIO_LIKE]->(maria)
RETURN otro.nombre  // ← Esto es un MATCH!
```

### Características
- ✅ Relaciones ultra-rápidas
- ✅ Recomendaciones: "amigos de amigos"
- ✅ Análisis de redes
- ⚠️ Duplica la estructura de datos

---

## 📊 Flujo de Sincronización

```
┌─────────────────┐
│    CLI          │
│  (Usuario)      │
└────────┬────────┘
         │ 1. Registra usuario
         ▼
┌─────────────────────────────────────────┐
│  PostgreSQL (Postgres)                  │
│  Inserta usuario + integridad referencial
└────┬────────────────────────────────────┘
     │ 2. Sincroniza a...
     ├──▶ 🍃 MongoDB (perfil denormalizado)
     ├──▶ 🔴 Redis (contador inicial 0)
     ├──▶ 🔗 Neo4j (nodo Usuario)
     └──▶ 🔷 Cassandra (crea tabla si no existe)

Cuando da LIKE:
┌─────────────────────────────────┐
│  PostgreSQL                     │
│  INSERT INTO likes (...)        │
└────┬────────────────────────────┘
     │ Chequea if like mutuo
     ├──▶ SI: INSERT coincidencias
     ├──▶ NEO4J: CREATE (:LIKE) (:MATCH)
     ├──▶ REDIS: +1 al contador
     └──▶ CASSANDRA: ready para mensajes
```

---

## 🔍 Verificación: Script `verify_databases.py`

Ejecuta esto para verificar:

```bash
python verify_databases.py
```

Mostrará:
- ✅ Conexión a cada DB
- 📋 Tablas/Colecciones/Keyspaces
- 📈 Cantidad de registros por tabla
- 👥 Ejemplos de datos
- 📐 Esquema de tablas
- 🔗 Relaciones en grafo

---

## ✅ Checklist de Validación

- [ ] PostgreSQL: 12 tablas creadas ✓
- [ ] PostgreSQL: Integridad referencial (FK, UNIQUE, CHECK) ✓
- [ ] MongoDB: Colección "perfiles" con documentos desnormalizados ✓
- [ ] Redis: Claves de notificaciones/contadores ✓
- [ ] Cassandra: Keyspace "tinder_app" con tabla "mensajes_timeline" ✓
- [ ] Neo4j: Nodos :Usuario y relaciones :DIO_LIKE, :MATCH ✓
- [ ] Sincronización: Datos consistentes en las 5 DBs ✓

---

## 🎯 Resumen: Por qué cada DB

| DB | Tipo | Razón | Datos |
|---|---|---|---|
| **PostgreSQL** | Relacional | Fuente de verdad, ACID, integridad | Todas las tablas DER |
| **MongoDB** | Documentos | Cache, perfil desnormalizado | Perfiles completos |
| **Redis** | Cache | Contadores ultra-rápidos | Notificaciones, likes count |
| **Cassandra** | Time-series | Mensajes optimizados por tiempo | Timeline de mensajes |
| **Neo4j** | Grafo | Relaciones, recomendaciones | Likes, matches, amigos |

Cada DB es especialista en su tipo de datos y acceso.
