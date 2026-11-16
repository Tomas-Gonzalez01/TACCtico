import argparse
import csv
import io
import os
import tempfile
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import urlsplit


FIELDS = {
    "idPublicacion": "id_publicacion",
    "articuloTitulo": "titulo",
    "nuevoPrecio": "precio_publicado",
    "Moneda": "moneda",
    "zProductoLink": "url",
    "Tiempo": "capturado_en",
}
UTIL_FIELDS = (
    "insumo", "marca", "vendedor", "tipo_vendedor", "gramos_unidad", "unidades",
    "es_pack", "gramos_totales", "precio_100g", "fuente_peso", "peso_discrepa",
    "outlier_precio", "tiene_promo", "descuento_pct", "precio_anterior",
)
DETAIL_FIELDS = {
    "sellerID": "vendedor_id",
    "produtoCategoryID": "categoria",
    "Envio": "envio",
    "promociones": "promocion",
}
SPEC_FIELDS = {
    "Nombre": "nombre_ficha", "Línea": "linea", "Sabor": "sabor",
    "Número de inscripción de producto (RNPA)": "rnpa",
}


def csv_reader(csv_text, required):
    reader = csv.DictReader(io.StringIO(csv_text.removeprefix("\ufeff"), newline=""), strict=True)
    headers = reader.fieldnames or []
    missing = set(required) - set(headers)
    if missing:
        raise ValueError(f"Faltan columnas: {', '.join(sorted(missing))}")
    if len(headers) != len(set(headers)):
        raise ValueError("El CSV tiene encabezados repetidos.")
    return reader


def find_original(row, originals):
    matches = [
        original for original in originals.get(row["idPublicacion"], [])
        if row["titulo"] == original["articuloTitulo"].strip()
        and row["link"] == original["zProductoLink"].strip()
        and Decimal(row["precio"]) == Decimal(original["nuevoPrecio"])
    ]
    if len(matches) != 1:
        raise ValueError("No se encontró una sola captura original que coincida en ID, título, URL y precio.")
    return matches[0]


def curated_item(row, originals):
    row = {key: value.strip() for key, value in row.items()}
    original = find_original(row, originals)
    item = {target: original[source].strip() for source, target in FIELDS.items()}
    item.update({key: row[key] for key in UTIL_FIELDS})
    item.update({target: original.get(source, "").strip() for source, target in DETAIL_FIELDS.items()})
    specs = {
        original[key].strip(): original.get(key.removesuffix("/name") + "/value", "").strip()
        for key in original if key.startswith("caracteristicas/") and key.endswith("/name")
    }
    item.update({target: specs.get(source, "") for source, target in SPEC_FIELDS.items()})

    grams, units, total = (Decimal(row[key]) for key in ("gramos_unidad", "unidades", "gramos_totales"))
    if not all(value.is_finite() and value > 0 for value in (grams, units, total)):
        raise ValueError("El peso y las unidades deben ser positivos.")
    if units % 1 or grams * units != total:
        raise ValueError("gramos_totales debe coincidir con gramos_unidad × unidades enteras.")
    for flag in ("es_pack", "peso_discrepa", "outlier_precio", "tiene_promo"):
        item[flag] = row[flag].lower()
        if item[flag] not in {"true", "false"}:
            raise ValueError(f"{flag} debe indicar true o false.")
    if not row["insumo"]:
        raise ValueError("Falta el insumo.")
    item["unidades"] = str(int(units))
    issues = []
    if item["peso_discrepa"] == "true":
        issues.append("Peso discrepante")
    if (item["es_pack"] == "true") != (units > 1):
        issues.append("Formato de pack inconsistente")
    item["revision_presentacion"] = " · ".join(issues)
    return item


def preparar_csv(csv_text, original_csv_text=None):
    headers = csv_reader(csv_text, ()).fieldnames or []
    curated = "insumo" in headers
    columns = [*FIELDS.values(), "fuente"]
    originals = {}
    if curated:
        if original_csv_text is None:
            raise ValueError("Usá --original con el dataset_final.csv del mismo lote para recuperar la fecha y la moneda.")
        for row in csv_reader(original_csv_text, FIELDS):
            if None in row or any(value is None for value in row.values()):
                raise ValueError("El archivo de capturas originales contiene una fila incompleta.")
            originals.setdefault(row["idPublicacion"].strip(), []).append(row)
        reader = csv_reader(csv_text, ("idPublicacion", "titulo", "precio", "link", *UTIL_FIELDS))
        columns.extend((*UTIL_FIELDS, *DETAIL_FIELDS.values(), *SPEC_FIELDS.values(), "revision_presentacion"))
    else:
        reader = csv_reader(csv_text, FIELDS)

    records = {}
    duplicates = 0
    for row in reader:
        try:
            if None in row or any(value is None for value in row.values()):
                raise ValueError
            item = curated_item(row, originals) if curated else {
                target: row[source].strip() for source, target in FIELDS.items()
            }
            price = Decimal(item["precio_publicado"])
            captured = datetime.fromisoformat(item["capturado_en"])
            url = urlsplit(item["url"])
            if (
                not item["id_publicacion"] or not item["titulo"]
                or item["moneda"] != "ARS" or not price.is_finite() or price <= 0
                or captured.utcoffset() is None or url.scheme != "https"
                or url.hostname != "articulo.mercadolibre.com.ar"
            ):
                raise ValueError
        except (ValueError, InvalidOperation) as error:
            detail = f" {error}" if curated and isinstance(error, ValueError) and str(error) else ""
            raise ValueError(f"Fila inválida cerca de la línea {reader.line_num}.{detail}") from None
        item["capturado_en"] = captured.astimezone(timezone.utc).isoformat()
        item["fuente"] = "Mercado Libre Argentina"
        key = item["id_publicacion"]
        previous = records.get(key)
        if previous:
            duplicates += 1
            if item["capturado_en"] == previous["capturado_en"] and item != previous:
                raise ValueError(f"Duplicado con valores distintos cerca de la línea {reader.line_num}.")
            if item["capturado_en"] <= previous["capturado_en"]:
                continue
        records[key] = item
    if not records:
        raise ValueError("El CSV no contiene publicaciones.")

    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=columns)
    writer.writeheader()
    writer.writerows(records.values())
    return {"csv_validado": buffer.getvalue(), "filas": len(records), "duplicados": duplicates}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("entrada", type=Path)
    parser.add_argument("salida", type=Path)
    parser.add_argument("--original", type=Path, help="CSV original del mismo lote para importar dataset_util.csv.")
    args = parser.parse_args()
    if args.entrada.resolve() == args.salida.resolve():
        parser.error("Elegí una ruta distinta para el CSV validado.")
    if args.original is not None and args.original.resolve() == args.salida.resolve():
        parser.error("Elegí una ruta de salida distinta de la captura original.")
    try:
        original = args.original.read_text(encoding="utf-8-sig") if args.original else None
        result = preparar_csv(args.entrada.read_text(encoding="utf-8-sig"), original)
        args.salida.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            dir=args.salida.parent, delete=False, mode="w", encoding="utf-8", newline=""
        ) as temp:
            temp_path = Path(temp.name)
            try:
                temp.write(result["csv_validado"])
                temp.close()
                os.replace(temp_path, args.salida)
            finally:
                temp_path.unlink(missing_ok=True)
    except (OSError, ValueError, csv.Error) as error:
        parser.exit(1, f"Importación rechazada: {error}\n")
    print(f"Publicaciones guardadas: {result['filas']}. Duplicados: {result['duplicados']}.")


if __name__ == "__main__":
    main()
