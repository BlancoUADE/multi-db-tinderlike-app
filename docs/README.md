# Documentacion del TPO Tinder Multi-DB

Este proyecto modela una aplicacion de citas usando una base relacional y
cuatro bases NoSQL. El objetivo principal no es la interfaz, sino demostrar
como interactuan los motores entre si manteniendo consistencia funcional.

## Comandos principales

```powershell
docker compose up -d
py -3.11 -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

## Menu actual del CLI

1. Registrar usuario
2. Crear interes
3. Asignar interes a usuario
4. Agregar foto
5. Dar like, creando match automatico si el like es reciproco
6. Forzar match
7. Bloquear usuario
8. Enviar mensaje
9. Login con sesion Redis TTL
10. Ver TTL de sesion
11. Logout
12. Listar usuarios
13. Ver perfil de usuario
14. Ver likes
15. Ver matches
16. Ver mensajes
17. Ver notificaciones
18. Cargar datos demo
19. Limpiar todas las bases
20. Salir

## Scripts de verificacion

```powershell
python tests\test_connections.py
python tests\verify_databases.py
```

`test_connections.py` valida conectividad y asegura esquemas basicos.
`verify_databases.py` muestra tablas, colecciones, claves, keyspaces, nodos y
relaciones con los nombres reales del proyecto.

## Documentos

- `MULTI_DB_STRATEGY.md`: justificacion de cada motor y flujos de sincronizacion.
- `COMO_VERIFICAR.txt`: guia operativa de chequeo.
- `tests/VERIFICATION_GUIDE.md`: ejemplos de consultas para verificar datos.
