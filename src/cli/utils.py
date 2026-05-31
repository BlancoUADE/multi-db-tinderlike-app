"""
Utilidades de entrada de datos para el CLI
"""

from datetime import datetime


def ask_text(prompt_text):
	"""Solicita un texto no vacío."""
	while True:
		value = input(prompt_text).strip()
		if value:
			return value
		print("El valor no puede estar vacío.")


def ask_int(prompt_text, minimum=None):
	"""Solicita un entero con validación opcional de mínimo."""
	while True:
		raw_value = input(prompt_text).strip()
		try:
			value = int(raw_value)
		except ValueError:
			print("Debe ser un número entero.")
			continue

		if minimum is not None and value < minimum:
			print(f"El valor debe ser >= {minimum}.")
			continue

		return value


def ask_bool(prompt_text):
	"""Solicita un sí/no."""
	while True:
		value = input(f"{prompt_text} (s/n): ").strip().lower()
		if value in ("s", "si", "sí"):
			return True
		if value in ("n", "no"):
			return False
		print("Ingresa 's' para sí o 'n' para no.")


def ask_timestamp(prompt_text):
	"""Solicita un timestamp en formato YYYY-MM-DD HH:MM."""
	while True:
		raw_value = input(prompt_text).strip()
		try:
			return datetime.strptime(raw_value, "%Y-%m-%d %H:%M")
		except ValueError:
			print("Formato incorrecto. Usa: YYYY-MM-DD HH:MM (ejemplo: 2024-01-15 14:30)")


def ask_date(prompt_text):
	"""Solicita una fecha en formato YYYY-MM-DD."""
	while True:
		raw_value = input(prompt_text).strip()
		try:
			return datetime.strptime(raw_value, "%Y-%m-%d").date()
		except ValueError:
			print("Formato incorrecto. Usa: YYYY-MM-DD (ejemplo: 2024-01-15)")
