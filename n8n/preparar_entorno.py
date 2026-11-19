"""Crea la clave interna de los ejecutores sin sobrescribir una existente."""

from pathlib import Path
import secrets

path = Path(__file__).resolve().with_name(".env")
if path.exists():
    print("Se conserva el archivo .env existente.")
else:
    with path.open("x", encoding="utf-8") as file:
        file.write("N8N_RUNNERS_AUTH_TOKEN=" + secrets.token_hex(32) + "\n")
    print("Clave interna generada en .env. No se incluye en Git.")
