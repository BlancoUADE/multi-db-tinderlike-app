import os

import psycopg2
from psycopg2 import OperationalError
from psycopg2.extras import RealDictCursor


DB_CONFIG = {
	"host": os.getenv("POSTGRES_HOST", "localhost"),
	"port": os.getenv("POSTGRES_PORT", "5432"),
	"dbname": os.getenv("POSTGRES_DB", "tinder_app"),
	"user": os.getenv("POSTGRES_USER", "tpo_user"),
	"password": os.getenv("POSTGRES_PASSWORD", "tpo_password"),
}


def connect_db():
	return psycopg2.connect(**DB_CONFIG)


def ensure_schema(conn):
	with conn.cursor() as cur:
		cur.execute(
			"""
			CREATE TABLE IF NOT EXISTS users (
				id SERIAL PRIMARY KEY,
				nombre TEXT NOT NULL,
				edad INTEGER NOT NULL CHECK (edad > 0),
				genero TEXT NOT NULL,
				ubicacion TEXT NOT NULL,
				biografia TEXT NOT NULL,
				pref_edad_min INTEGER NOT NULL CHECK (pref_edad_min > 0),
				pref_edad_max INTEGER NOT NULL CHECK (pref_edad_max > 0),
				created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
				CHECK (pref_edad_min <= pref_edad_max)
			);
			"""
		)
	conn.commit()


def ask_text(prompt_text):
	while True:
		value = input(prompt_text).strip()
		if value:
			return value
		print("El valor no puede estar vacío.")


def ask_int(prompt_text, minimum=None):
	while True:
		raw_value = input(prompt_text).strip()
		try:
			value = int(raw_value)
		except ValueError:
			print("Ingrese un número entero válido.")
			continue

		if minimum is not None and value < minimum:
			print(f"El valor debe ser mayor o igual a {minimum}.")
			continue

		return value


def register_user(conn):
	print("\nRegistro de usuario")
	nombre = ask_text("Nombre: ")
	edad = ask_int("Edad: ", minimum=1)
	genero = ask_text("Genero: ")
	ubicacion = ask_text("Ubicacion: ")
	biografia = ask_text("Biografia: ")
	pref_edad_min = ask_int("Preferencia de Edad Minima: ", minimum=1)
	pref_edad_max = ask_int("Preferencia de Edad Maxima: ", minimum=pref_edad_min)

	with conn.cursor() as cur:
		cur.execute(
			"""
			INSERT INTO users (
				nombre,
				edad,
				genero,
				ubicacion,
				biografia,
				pref_edad_min,
				pref_edad_max
			) VALUES (%s, %s, %s, %s, %s, %s, %s)
			RETURNING id;
			""",
			(
				nombre,
				edad,
				genero,
				ubicacion,
				biografia,
				pref_edad_min,
				pref_edad_max,
			),
		)
		user_id = cur.fetchone()[0]

	conn.commit()
	print(f"Usuario registrado correctamente. ID asignado: {user_id}")


def format_user(user):
	return (
		f"ID: {user['id']}\n"
		f"Nombre: {user['nombre']}\n"
		f"Edad: {user['edad']}\n"
		f"Genero: {user['genero']}\n"
		f"Ubicacion: {user['ubicacion']}\n"
		f"Biografia: {user['biografia']}\n"
		f"Preferencia de Edad Minima: {user['pref_edad_min']}\n"
		f"Preferencia de Edad Maxima: {user['pref_edad_max']}"
	)


def login_user(conn):
	print("\nInicio de sesion")
	nombre = ask_text("Nombre: ")
	edad = ask_int("Edad: ", minimum=1)

	with conn.cursor(cursor_factory=RealDictCursor) as cur:
		cur.execute(
			"""
			SELECT id, nombre, edad, genero, ubicacion, biografia, pref_edad_min, pref_edad_max
			FROM users
			WHERE LOWER(nombre) = LOWER(%s) AND edad = %s
			ORDER BY id;
			""",
			(nombre, edad),
		)
		users = cur.fetchall()

	if not users:
		print("No se encontró un usuario con esos datos.")
		return

	if len(users) == 1:
		print("Sesion iniciada correctamente. Datos del usuario:")
		print(format_user(users[0]))
		return

	print("Se encontraron varios usuarios con esos datos básicos.")
	for user in users:
		print(f"- ID {user['id']}: {user['nombre']} ({user['ubicacion']})")

	selected_id = ask_int("Ingrese el ID para confirmar la sesion: ", minimum=1)
	selected_user = next((user for user in users if user["id"] == selected_id), None)

	if selected_user is None:
		print("El ID ingresado no coincide con los resultados encontrados.")
		return

	print("Sesion iniciada correctamente. Datos del usuario:")
	print(format_user(selected_user))


def main():
	try:
		conn = connect_db()
	except OperationalError as error:
		print("No se pudo conectar a Postgres.")
		print(error)
		return

	try:
		ensure_schema(conn)

		while True:
			print("\n=== CLI Tinder App ===")
			print("1. Registrar usuario")
			print("2. Iniciar sesion")
			print("3. Salir")

			option = input("Seleccione una opcion: ").strip()

			if option == "1":
				register_user(conn)
			elif option == "2":
				login_user(conn)
			elif option == "3":
				print("Hasta luego.")
				break
			else:
				print("Opcion invalida.")
	finally:
		conn.close()


if __name__ == "__main__":
	main()
