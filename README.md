# CLI Tinder Multi-DB

Aplicacion de citas estilo Tinder implementada con una arquitectura multi-base
de datos. El usuario interactua con un unico CLI; internamente el sistema
coordina cinco motores.

## Bases usadas

| Motor | Rol en el sistema |
| --- | --- |
| PostgreSQL | Fuente de verdad relacional: usuarios, intereses, fotos, likes, bloqueos, matches, eventos, mensajes y notificaciones. |
| MongoDB | Perfiles desnormalizados (`perfiles_usuarios`) y auditoria de logins (`sesiones_login`). |
| Redis | Contadores rapidos y sesiones activas con TTL. |
| Cassandra | Mensajes por coincidencia ordenados por tiempo (`mensajes_por_coincidencia`). |
| Neo4j | Grafo de relaciones: `Usuario`, `Interes`, `Evento`, `DIO_LIKE`, `MATCH`, `TIENE_INTERES`, `BLOQUEO`, `ASISTE`. |

## Levantar servicios

```powershell
docker compose up -d
```

## Entorno Python

Se recomienda Python 3.11 porque `cassandra-driver` puede fallar en Windows con
versiones mas nuevas.

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

## Ejecutar CLI

```powershell
python main.py
```

Al iniciar, el programa confirma la conexion a:

```text
PostgreSQL OK
MongoDB OK
Redis OK
Cassandra OK
Neo4j OK
```

## Demo sugerida

1. Ejecutar `python main.py`.
2. Entrar a `Sistema`.
3. Elegir `Cargar datos demo`.
4. Volver al menu principal y listar usuarios.
5. Iniciar sesion con un usuario.
6. Desde el menu de usuario, probar recomendaciones, likes, mensajes, notificaciones y TTL.
7. Correr `python tests\verify_databases.py` para mostrar datos por motor.

## Verificacion rapida

```powershell
python tests\test_connections.py
python tests\verify_databases.py
```

## Puertos

| Motor | Puerto local |
| --- | --- |
| PostgreSQL | `5433` |
| MongoDB | `27017` |
| Redis | `6379` |
| Cassandra | `9042` |
| Neo4j Browser | `7474` |
| Neo4j Bolt | `7687` |

Las interfaces web de administracion se dejan fuera del compose principal para
mantener el entorno de entrega simple.
