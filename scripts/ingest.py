import argparse
import csv
import json
import sqlite3
from contextlib import closing
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import urlsplit

from importar_mercadolibre import FIELDS


MOCK_FIELDS = (
    "proveedor", "producto", "marca", "categoria", "cantidad", "unidad",
    "precio", "iva", "bulto", "promocion", "fecha", "fuente",
)
MARKET_FIELDS = (*FIELDS.values(), "fuente")
COLUMNS = (
    "fuente", "clave", "fecha", "proveedor", "producto", "marca", "categoria",
    "cantidad", "unidad", "precio", "moneda", "iva", "bulto", "promocion",
    "tipo_precio", "url",
)
SCHEMA = """
CREATE TABLE IF NOT EXISTS capturas (
    fuente TEXT NOT NULL,
    clave TEXT NOT NULL,
    fecha TEXT NOT NULL,
    proveedor TEXT,
    producto TEXT NOT NULL,
    marca TEXT,
    categoria TEXT,
    cantidad TEXT,
    unidad TEXT,
    precio TEXT NOT NULL,
    moneda TEXT NOT NULL,
    iva TEXT,
    bulto INTEGER,
    promocion TEXT,
    tipo_precio TEXT NOT NULL,
    url TEXT,
    PRIMARY KEY (fuente, clave, fecha)
) WITHOUT ROWID
"""


def read_records(path):
    with path.open(encoding="utf-8-sig", newline="") as file:
        if path.suffix.lower() == ".json":
            rows = json.load(file, parse_float=Decimal)
            if not isinstance(rows, list):
                raise ValueError("El JSON debe contener una lista de objetos.")
            yield from rows
            return
        if path.suffix.lower() != ".csv":
            raise ValueError("Usá un archivo .csv o .json.")
        reader = csv.DictReader(file, strict=True)
        if not reader.fieldnames or len(set(reader.fieldnames)) != len(reader.fieldnames):
            raise ValueError("El CSV tiene encabezados vacíos o repetidos.")
        yield from reader


def required_text(row, field):
    value = row[field]
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} debe contener texto.")
    return value.strip()


def decimal_value(row, field, *, allow_zero=False):
    try:
        value = Decimal(str(row[field]))
    except InvalidOperation:
        raise ValueError(f"{field} debe ser numérico.") from None
    if not value.is_finite() or value < 0 or (not allow_zero and value == 0):
        raise ValueError(f"{field} está fuera de rango.")
    if value == 0:
        return "0"
    plain = format(value, "f")
    return plain.rstrip("0").rstrip(".") if "." in plain else plain


def normalize(row):
    if not isinstance(row, dict) or None in row or any(value is None for value in row.values()):
        raise ValueError("La fila no coincide con la estructura de entrada.")
    if set(MARKET_FIELDS) <= row.keys():
        fields = {key: required_text(row, key) for key in MARKET_FIELDS if key != "precio_publicado"}
        captured = datetime.fromisoformat(fields["capturado_en"])
        url = urlsplit(fields["url"])
        if (
            captured.utcoffset() is None or fields["moneda"] != "ARS"
            or fields["fuente"] != "Mercado Libre Argentina"
            or url.scheme != "https" or url.netloc != "articulo.mercadolibre.com.ar" or not url.path.strip("/")
        ):
            raise ValueError("Captura, moneda, fuente o URL de Mercado Libre inválida.")
        return {
            "fuente": fields["fuente"], "clave": fields["id_publicacion"],
            "fecha": captured.astimezone(timezone.utc).isoformat(timespec="microseconds"),
            "producto": fields["titulo"], "precio": decimal_value(row, "precio_publicado"),
            "moneda": fields["moneda"], "tipo_precio": "publicado", "url": fields["url"],
        }
    if set(MOCK_FIELDS) <= row.keys():
        fields = {
            key: required_text(row, key)
            for key in MOCK_FIELDS if key not in ("cantidad", "precio", "iva", "bulto")
        }
        if fields["fuente"] != "MOCK_FICTICIO":
            raise ValueError("La entrada con esquema de la muestra debe usar la fuente MOCK_FICTICIO.")
        fields["fecha"] = date.fromisoformat(fields["fecha"]).isoformat()
        fields["cantidad"] = decimal_value(row, "cantidad")
        fields["precio"] = decimal_value(row, "precio")
        fields["iva"] = decimal_value(row, "iva", allow_zero=True)
        fields["bulto"] = int(decimal_value(row, "bulto"))
        identity = ("proveedor", "producto", "marca", "cantidad", "unidad", "bulto")
        fields["clave"] = json.dumps([fields[key] for key in identity], ensure_ascii=False)
        fields.update(moneda="ARS", tipo_precio="neto_por_bulto")
        return fields
    raise ValueError("Se requiere el esquema de Mercado Libre validado o el de la muestra ficticia.")


def ingest(path, database):
    if path.resolve() == database.resolve():
        raise ValueError("La entrada y la base deben tener rutas distintas.")
    database.parent.mkdir(parents=True, exist_ok=True)
    inserted = duplicates = 0
    placeholders = ", ".join("?" for _ in COLUMNS)
    insert = f"INSERT INTO capturas ({', '.join(COLUMNS)}) VALUES ({placeholders}) ON CONFLICT DO NOTHING"
    select = f"SELECT {', '.join(COLUMNS)} FROM capturas WHERE fuente = ? AND clave = ? AND fecha = ?"
    with closing(sqlite3.connect(database)) as connection, connection:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(SCHEMA)
        for number, row in enumerate(read_records(path), start=1):
            try:
                item = normalize(row)
                values = tuple(item.get(column) for column in COLUMNS)
                if connection.execute(insert, values).rowcount:
                    inserted += 1
                elif connection.execute(select, values[:3]).fetchone() == values:
                    duplicates += 1
                else:
                    raise ValueError("La captura ya existe con valores distintos.")
            except ValueError as error:
                raise ValueError(f"Registro {number}: {error}") from error
        if not (inserted or duplicates):
            raise ValueError("El archivo no contiene registros.")
    return inserted, duplicates


def main():
    parser = argparse.ArgumentParser(description="Importar capturas de TACCtico a SQLite.")
    parser.add_argument("entrada", type=Path)
    parser.add_argument("--db", type=Path, default=Path("data_real/capturas.sqlite3"))
    args = parser.parse_args()
    try:
        inserted, duplicates = ingest(args.entrada, args.db)
    except (OSError, ValueError, csv.Error, sqlite3.Error) as error:
        parser.exit(1, f"Ingesta rechazada: {error}\n")
    print(f"Capturas nuevas: {inserted}. Duplicados omitidos: {duplicates}.")


if __name__ == "__main__":
    main()
