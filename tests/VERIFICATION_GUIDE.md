# Verification Guide

## Scripts

```powershell
python tests\test_connections.py
python tests\verify_databases.py
```

## Estado esperado despues de cargar demo

PostgreSQL:

- 6 usuarios
- intereses asignados
- likes reciprocos
- 3 coincidencias
- mensajes
- eventos y asistencia
- notificaciones

MongoDB:

- `perfiles_usuarios` con perfiles desnormalizados.
- `sesiones_login` con auditoria de login.

Redis:

- contadores de notificaciones
- contadores de likes
- al menos una clave `session:{id_usuario}:{token}` con TTL

Cassandra:

- keyspace `tinder_app`
- tabla `mensajes_por_coincidencia`
- mensajes de la coincidencia `1`

Neo4j:

- nodos `Usuario`, `Interes`, `Evento`
- relaciones `TIENE_INTERES`, `DIO_LIKE`, `MATCH`, `BLOQUEO`, `ASISTE`

## Consultas utiles

PostgreSQL:

```sql
SELECT u.nombre, COUNT(l.id_like) AS likes_dados
FROM usuarios u
LEFT JOIN likes l ON l.id_usuario_origen = u.id_usuario
GROUP BY u.id_usuario, u.nombre
ORDER BY u.id_usuario;
```

Cassandra:

```sql
USE tinder_app;
SELECT * FROM mensajes_por_coincidencia WHERE id_coincidencia = 1;
```

Neo4j:

```cypher
MATCH (u:Usuario)-[r]->(x)
RETURN u, r, x
LIMIT 100;
```

Redis:

```powershell
docker exec -it tpo_redis redis-cli KEYS *
```
