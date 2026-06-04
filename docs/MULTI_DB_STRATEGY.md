# Estrategia Multi-DB

## Decision general

El sistema usa PostgreSQL como fuente de verdad y cuatro bases NoSQL para
consultas o estados especializados. El CLI oculta esa distribucion: el usuario
opera acciones de negocio, no motores de base de datos.

## PostgreSQL

Rol: base relacional transaccional.

Tablas:

- `usuarios`
- `fotos`
- `intereses`
- `usuario_intereses`
- `likes`
- `bloqueos`
- `coincidencias`
- `mensajes`
- `eventos`
- `asistencia_eventos`
- `notificaciones`

Justificacion:

- Integridad referencial con FK.
- Reglas de unicidad para likes, matches y bloqueos.
- Fuente de verdad para usuarios y acciones principales.

## MongoDB

Rol: documentos desnormalizados y auditoria.

Colecciones:

- `perfiles_usuarios`: perfil completo de cada usuario, con intereses y fotos.
- `sesiones_login`: auditoria de intentos de login, exitosos o fallidos.

Justificacion:

- Lectura directa de perfiles sin joins.
- Registro flexible de eventos de autenticacion.
- Consistencia eventual a partir de PostgreSQL.

## Redis

Rol: estado temporal, TTL y contadores.

Claves principales:

- `session:{id_usuario}:{token}`: sesion activa con TTL.
- `user:{id_usuario}:unread_notifications`: contador de notificaciones.
- `user:{id_usuario}:likes_given`: contador rapido de likes enviados.
- `match:{id}:unread_messages:{id_usuario}`: contador de mensajes no leidos.

Justificacion:

- Expiracion automatica para sesiones.
- Contadores rapidos sin consultar tablas transaccionales.
- Logout elimina la clave de sesion.

## Cassandra

Rol: time-series de mensajes por match.

Keyspace:

- `tinder_app`

Tabla:

- `mensajes_por_coincidencia`

Clave:

- Partition key: `id_coincidencia`
- Clustering: `fecha_envio`, `id_mensaje`

Justificacion:

- Consulta natural: "traer mensajes de una coincidencia ordenados por tiempo".
- Escrituras append-only.
- PostgreSQL conserva la fuente de verdad y Cassandra optimiza el historial.

## Neo4j

Rol: grafo de relaciones y recomendaciones.

Nodos:

- `Usuario`
- `Interes`
- `Evento`

Relaciones:

- `DIO_LIKE`
- `MATCH`
- `TIENE_INTERES`
- `BLOQUEO`
- `ASISTE`

Justificacion:

- Likes, matches, intereses y bloqueos son relaciones naturales.
- Permite consultas de compatibilidad por intereses y caminos de relacion.
- Complementa PostgreSQL sin reemplazarlo.

## Flujos que demuestran integracion

### Registro de usuario

1. PostgreSQL inserta el usuario.
2. MongoDB crea/actualiza `perfiles_usuarios`.
3. Neo4j crea/actualiza nodo `Usuario`.

### Asignacion de interes

1. PostgreSQL inserta interes y relacion M:N.
2. MongoDB refresca el perfil desnormalizado.
3. Neo4j crea relacion `TIENE_INTERES`.

### Like reciproco

1. PostgreSQL inserta `likes`.
2. Neo4j crea `DIO_LIKE`.
3. Redis incrementa contador de likes y notificaciones.
4. Si existe like inverso, PostgreSQL crea `coincidencias`.
5. Neo4j crea `MATCH`.
6. Redis y PostgreSQL registran notificaciones de match.

### Mensaje

1. PostgreSQL guarda el mensaje.
2. Cassandra guarda el mensaje en `mensajes_por_coincidencia`.
3. Redis incrementa contadores de mensajes/no leidas.
4. PostgreSQL registra notificacion.

### Login y logout

1. MongoDB audita el intento en `sesiones_login`.
2. Si el usuario existe, Redis crea `session:{id_usuario}:{token}` con TTL.
3. Logout elimina esa clave Redis.

### Recomendacion de perfiles

1. Neo4j busca usuarios con intereses compartidos mediante `TIENE_INTERES`.
2. Neo4j excluye usuarios ya likeados, bloqueados o matcheados.
3. MongoDB trae `perfiles_usuarios` para esos candidatos.
4. El CLI muestra una tarjeta completa: nombre, edad, ubicacion, bio, intereses compartidos y foto principal.

Este flujo combina dos bases NoSQL en una misma consulta funcional: Neo4j decide
la relacion/relevancia y MongoDB resuelve la lectura documental del perfil.

## Criterio de defensa

El usuario no sabe de donde salen los datos. El CLI muestra acciones del dominio:
registrar, dar like, hacer match, enviar mensajes, iniciar sesion y consultar.
La distribucion entre bases es una decision interna de persistencia y acceso.
