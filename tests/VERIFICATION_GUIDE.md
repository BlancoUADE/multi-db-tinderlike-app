# Guía de Verificación - ¿Cómo cerciorarme que todo funciona?

## 🎯 3 Scripts de Verificación

### 1. `test_connections.py` - Verifica que las DBs estén levantadas

```bash
python test_connections.py
```

**Salida esperada:**
```
✅ PostgreSQL: conectado
✅ MongoDB: conectado  
✅ Redis: conectado
⚠️  Cassandra: pendiente (normal en Python 3.12+)
✅ Neo4j: conectado
```

Si ves ❌, el contenedor correspondiente no está corriendo.

---

### 2. `verify_databases.py` - Verifica esquemas Y datos almacenados

```bash
python verify_databases.py
```

**Salida esperada:**
```
============================================================
  📊 PostgreSQL - Base de datos relacional
============================================================
✅ Conexión exitosa
📋 Tablas encontradas: 12
   - usuarios
   - intereses
   - usuario_intereses
   - fotos
   - likes
   - coincidencias
   - mensajes
   - bloqueos
   - eventos
   - asistencia_eventos
   - notificaciones
   - dias_festivos

📈 Cantidad de registros:
   - usuarios: 5
   - intereses: 8
   - usuario_intereses: 12
   - ... (etc)

👥 Ejemplo de usuarios:
   - [1] Juan, 28 años, CABA
   - [2] María, 25 años, La Plata
   - [3] Carlos, 30 años, Quilmes

📐 Esquema de tabla 'usuarios':
   - id_usuario: integer NOT NULL
   - nombre: text NOT NULL
   - edad: integer NOT NULL
   - genero: text NOT NULL
   - ... (etc)

============================================================
  🍃 MongoDB - Base de datos de documentos (JSON)
============================================================
✅ Conexión exitosa
📋 Colecciones encontradas: 1
   - perfiles: 5 documentos

📄 Ejemplo de documento en 'perfiles':
   {
      "id_usuario": 1,
      "nombre": "Juan",
      "edad": 28,
      "intereses": [
         { "id": 1, "nombre": "Fútbol" },
         { "id": 5, "nombre": "Viajes" }
      ],
      "fotos": [
         {
            "id": 101,
            "url": "s3://...",
            "es_principal": true
         }
      ]
   }

📐 Estructura de documento en 'perfiles':
   - id_usuario: int
   - nombre: str
   - edad: int
   - genero: str
   - intereses: list
   - fotos: list

============================================================
  🔴 Redis - Cache/Contadores en memoria
============================================================
✅ Conexión exitosa
📊 Estadísticas:
   - Versión: 7.0.0
   - Modo: standalone
   - Memoria usada: 2.5M

🔑 Claves almacenadas: 8
   - notificaciones:sin_leer:1 (string): 3 (sin TTL)
   - likes:contador:2 (string): 15 (sin TTL)
   - sesion:1:token123 (string): [datos] (7200s)
   - cooldown:like:1:2 (string): 1 (86400s)
   ... y 4 claves más

============================================================
  🔷 Cassandra - Base de datos time-series (mensajes)
============================================================
✅ Conexión exitosa
📋 Keyspaces: ['tinder_app', ...]
📋 Tablas en 'tinder_app': ['mensajes_timeline']
   - mensajes_timeline: 23 registros

💬 Ejemplo de mensajes:
   - Row(id_coincidencia=1, fecha_envio=2024-01-20 10:00, id_emisor=1, contenido='Hola!')
   - Row(id_coincidencia=1, fecha_envio=2024-01-20 10:05, id_emisor=2, contenido='¿Qué tal?')

============================================================
  🔗 Neo4j - Grafo de relaciones (likes, matches)
============================================================
✅ Conexión exitosa
📍 Nodos totales: 5
🔗 Relaciones totales: 8

📊 Relaciones por tipo:
   - DIO_LIKE: 6
   - MATCH: 2

👥 Ejemplo de relaciones:
   - Juan [id=1] --DIO_LIKE-> María
   - María [id=2] --DIO_LIKE-> Juan
   - Juan [id=1] --MATCH-> María
   - Juan [id=1] --BLOQUEÓ-> Carlos

============================================================
  ✅ Verificación completada
============================================================
```

**¿Qué significa cada DB?**

| DB | Datos | Tipo |
|---|---|---|
| **PostgreSQL** | 12 tablas con relaciones | Relacional |
| **MongoDB** | Perfiles desnormalizados | Documentos JSON |
| **Redis** | Claves: notificaciones, contadores | Clave-valor |
| **Cassandra** | Timeline de mensajes | Time-series |
| **Neo4j** | Nodos: Usuarios, Relaciones: likes/matches | Grafo |

---

### 3. `main.py` - Flujo interactivo para ver datos en vivo

```bash
python main.py
```

**Pasos:**
```
1. Opción 19: Cargar datos demo
   → Crea 5 usuarios, 8 intereses, likes, matches, etc.

2. Opción 10: Listar usuarios
   → Muestra usuarios desde PostgreSQL
   
3. Opción 11: Ver perfil de usuario
   → Ingresa ID 1
   → Muestra: nombre, edad, intereses, fotos
   
4. Opción 12: Ver likes
   → Muestra últimos 20 likes
   
5. Opción 13: Ver coincidencias (matches)
   → Muestra matches creados
   
6. Opción 14: Ver mensajes
   → Ingresa ID de coincidencia (1)
   → Muestra conversación completa
   
7. Opción 15: Ver eventos
   → Muestra eventos creados
   
8. Opción 17: Analíticas
   → Ejecuta 7 queries de análisis
```

---

## 📋 Checklist: ¿Está todo corriendo?

### ✅ Conexiones
- [ ] `python test_connections.py` → 5 DBs conectadas

### ✅ Esquemas
- [ ] `python verify_databases.py` → 12 tablas en PostgreSQL
- [ ] 1 colección en MongoDB
- [ ] Keyspace en Cassandra
- [ ] Nodos en Neo4j

### ✅ Datos
- [ ] Cargar demo (opción 19)
- [ ] `verify_databases.py` muestra registros en cada tabla
- [ ] Consultar usuarios (opción 10) → No vacío

### ✅ Sincronización Multi-DB
- [ ] PostgreSQL: 5 usuarios
- [ ] MongoDB: 5 documentos en "perfiles"
- [ ] Redis: claves de notificaciones
- [ ] Cassandra: mensajes en timeline
- [ ] Neo4j: 5 nodos + relaciones

### ✅ Integridad DER
- [ ] Usuarios con intereses (M:N)
- [ ] Likes con validación UNIQUE (no duplicados)
- [ ] Matches cuando hay like mutuo
- [ ] Mensajes asociados a coincidencia
- [ ] Fotos asociadas a usuario

---

## 🔍 Respectar el DER

**El DER que te pasaste tiene estas entidades:**

```
USUARIOS
├── Intereses (M:N) → USUARIO_INTERESES
├── Fotos (1:N)
├── Likes (1:N) → LIKES
├── Coincidencias (M:M) → COINCIDENCIAS
├── Eventos (1:N) → EVENTOS
│   └── Asistencias (M:N) → ASISTENCIA_EVENTOS
├── Mensajes (1:N) → MENSAJES
├── Bloqueos (1:N) → BLOQUEOS
└── Notificaciones (1:N) → NOTIFICACIONES
```

**Validar que cada relación existe:**
```sql
-- PostgreSQL
SELECT * FROM information_schema.table_constraints WHERE table_schema='public';
```

Deberías ver:
- `usuarios_pkey` (PK)
- `usuario_intereses_fkey` (FK)
- `fotos_id_usuario_fkey` (FK)
- `likes_id_usuario_origen_fkey` (FK)
- etc.

---

## 📚 Documentación Importante

- **`MULTI_DB_STRATEGY.md`**: Explica POR QUÉ cada dato va en cada DB
- **`main.py`**: CLI con todas las operaciones
- **`verify_databases.py`**: Script de verificación completo
- **`test_connections.py`**: Verificar conexiones básicas

---

## 🎬 Flujo Recomendado

```
1. Levantar Docker
   docker compose up -d

2. Verificar conexiones
   python test_connections.py

3. Ejecutar CLI con demo
   python main.py
   → Opción 19: Cargar demo

4. Verificar todo completo
   python verify_databases.py

5. Explorar datos
   python main.py
   → Opción 10-17: Consultar

6. Limpiar cuando termines
   python main.py
   → Opción 20: Limpiar bases
```

---

## ⚠️ Troubleshooting

### "Cassandra pending"
Normal en Python 3.12+ Windows. Usa Python 3.11 si quieres Cassandra.

### "No se pudo conectar a PostgreSQL"
```bash
docker compose ps  # Ver si el contenedor está UP
docker logs postgres  # Ver logs
```

### "No hay datos después de cargar demo"
```bash
python main.py
→ Opción 20: Limpiar bases (con rollback)
→ Opción 19: Cargar demo
```

### "Transaction is aborted"
Ya está fijado. Si ves error, ejecuta:
```bash
python main.py
→ Opción 20: Limpiar
→ Opción 19: Cargar demo
```
