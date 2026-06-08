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

### Menu principal

1. Registrar usuario
2. Iniciar sesion
3. Listar usuarios
4. Sistema
5. Salir

### Menu de usuario

Se abre despues de registrar usuario o iniciar sesion.

1. Ver mi perfil
2. Agregar foto
3. Agregar interes a mi perfil
4. Dar like
5. Recomendar perfiles
6. Enviar mensaje
7. Ver mensajes de un match
8. Ver notificaciones
9. Ver likes
10. Ver matches
11. Bloquear usuario
12. Ver TTL de mi sesion
13. Cerrar sesion
14. Volver al menu principal

### Sistema

1. Crear interes global
2. Forzar match
3. Cargar datos demo
4. Limpiar todas las bases
5. Volver

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
