"""Limpieza reproducible de Kiara y contrato de consumo de TACCtico."""
import csv
import hashlib
import io
import json
import math
import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import urlsplit

import numpy as np
import pandas as pd

from . import kiara_etl as k
from .app_adapter import FIELDS, UTIL_FIELDS, DETAIL_FIELDS, SPEC_FIELDS, preparar_csv
from .analytics import analizar, paquete_publicable

VERSION = "kiara-etl-1-tacctico-2-analisis"
RULES_SHA = hashlib.sha256(b"".join(
    (Path(__file__).parent / name).read_bytes()
    for name in ("kiara_etl.py", "app_adapter.py", "pipeline.py", "analytics.py", "templates/dashboard_kiara.html")
)).hexdigest()
OPTIONAL = ["precioAnterior", "precioDiscount", "cantidadVendida", "Vendedor",
            "productoMarca", "reputacionVendedor", "estadoVendedorPotente",
            "promociones", "esTiendaOficial", "busqueda"]


def text(value):
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    return str(value).strip()


def boolean(value):
    return text(value).casefold() in {"true", "1", "sí", "si"}


def csv_text(rows, fields):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({name: text(row.get(name)) for name in fields})
    return stream.getvalue()


def validate_raw(row):
    if not all(text(row.get(name)) for name in FIELDS):
        raise ValueError("Falta ID, título, precio, moneda, URL o fecha de captura")
    try:
        price = Decimal(text(row["nuevoPrecio"]))
        date = datetime.fromisoformat(text(row["Tiempo"]))
        url = urlsplit(text(row["zProductoLink"]))
        if not price.is_finite() or price <= 0:
            raise ValueError("Precio no positivo o no finito")
        if date.utcoffset() is None:
            raise ValueError("La captura no tiene zona horaria")
        if text(row["Moneda"]) != "ARS":
            raise ValueError("Moneda distinta de ARS")
        if url.scheme != "https" or url.netloc != "articulo.mercadolibre.com.ar" or re.search(r"\s", url.geturl()):
            raise ValueError("URL de publicación inválida")
    except (InvalidOperation, OverflowError):
        raise ValueError("Precio o fecha inválidos") from None
    return date.astimezone(timezone.utc).isoformat()


def procesar(rows):
    if not rows or len(rows) > 50000:
        raise ValueError("El lote debe contener entre 1 y 50.000 publicaciones")
    missing = set(FIELDS) - set().union(*(row.keys() for row in rows))
    if missing:
        raise ValueError("Faltan columnas: " + ", ".join(sorted(missing)))
    # All values arrive as CSV scalars; objects must never silently become text.
    if any(isinstance(v, (dict, list)) for r in rows for v in r.values()):
        raise ValueError("Se esperaba una fila CSV con valores simples")
    raw = [{key: text(value) for key, value in row.items()} for row in rows]
    canonical = json.dumps(raw, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    sha = hashlib.sha256((VERSION + "\n" + RULES_SHA + "\n" + canonical).encode()).hexdigest()
    rejects, valid, seen = [], [], {}
    exact_duplicates = 0
    for index, row in enumerate(raw, 2):
        try:
            captured = validate_raw(row)
        except (ValueError, TypeError) as error:
            rejects.append({"linea": index, "id_publicacion": row.get("idPublicacion", ""), "motivo": str(error)})
            continue
        row["Tiempo"] = captured
        key = (row["idPublicacion"], captured)
        if key in seen:
            if row != seen[key]:
                raise ValueError("Dos registros del mismo ID y captura tienen valores distintos; lote rechazado")
            exact_duplicates += 1
            continue
        seen[key] = row
        valid.append(row)
    if not valid:
        raise ValueError("Ninguna publicación supera la validación básica")
    # Missing optional fields have the same semantics as pd.read_csv in Colab.
    df = pd.DataFrame(valid)
    df = df.where(df.ne(""), np.nan)
    for field in OPTIONAL:
        if field not in df:
            df[field] = np.nan
    # CSV extraction can produce 'False' strings: bool('False') must not be True.
    df["esTiendaOficial"] = df["esTiendaOficial"].map(boolean)
    for field in ("articuloTitulo", "precioDiscount", "Vendedor"):
        df[field] = df[field].astype("string")
    # Pandas nullable string pd.NA is incompatible with NumPy select in the notebook.
    df = df.astype(object).where(df.notna(), np.nan)
    for transform in (k.aplanar_caracteristicas, k.limpiar_basico, k.detectar_pack,
                      k.extraer_gramos, k.gramos_totales, k.precio_por_100g,
                      k.clasificar_insumo, k.tipo_vendedor):
        df = transform(df)
    # Historical captures stay in dataset_limpio. Only the latest capture of each
    # publication participates in same-snapshot duplicates and price flags.
    latest = df.sort_values(["Tiempo", "idPublicacion"], kind="stable").drop_duplicates("idPublicacion", keep="last")
    # Preserve the original CSV order for Kiara's keep='first' duplicate rule.
    latest = latest.sort_index()
    latest = k.marcar_outliers(k.marcar_duplicados(latest))
    df["duplicado_titulo_vendedor"] = False
    df["outlier_precio"] = False
    for col in ("duplicado_titulo_vendedor", "outlier_precio"):
        df.loc[latest.index, col] = latest[col]
    _, useful = k.calidad(latest)
    util = latest.loc[useful].copy()
    if util.empty:
        raise ValueError("No hay insumos con presentación calculable; se conserva el lote vigente")
    source_fields = sorted(set().union(*(row.keys() for row in valid)))
    original = csv_text(valid, source_fields)
    util_csv = csv_text(util.to_dict("records"), k.COLUMNAS_SALIDA)
    # Existing app adapter validates prices, captures, pack math and boolean flags.
    validated = preparar_csv(util_csv, original)["csv_validado"]
    reader = csv.DictReader(io.StringIO(validated))
    app_fields = list(reader.fieldnames)
    app_rows = list(reader)
    # Retain relevant but ambiguous presentations for consultation. The app uses
    # revision_presentacion to block quantities and price-per-weight comparisons.
    unresolved = latest.loc[latest["en_receta"] & ~latest["duplicado_titulo_vendedor"] & ~useful]
    for _, row in unresolved.iterrows():
        item = {target: text(row[source]) for source, target in FIELDS.items()}
        item.update({name: text(row[name]) for name in UTIL_FIELDS})
        item.update({target: text(row.get(source)) for source, target in DETAIL_FIELDS.items()})
        specs = {text(row.get(key)): text(row.get(key[:-5] + "/value")) for key in row.index
                 if key.startswith("caracteristicas/") and key.endswith("/name")}
        item.update({target: specs.get(source, "") for source, target in SPEC_FIELDS.items()})
        item.update(fuente="Mercado Libre Argentina", revision_presentacion="Presentación sin confirmar")
        for flag in ("es_pack", "peso_discrepa", "outlier_precio", "tiene_promo"):
            item[flag] = str(boolean(item[flag])).lower()
        item["precio_100g"] = ""
        app_rows.append(item)
    app_rows.sort(key=lambda row: row["id_publicacion"])
    for row in app_rows:
        if row["revision_presentacion"]:
            row["precio_100g"] = ""
    if len({row["id_publicacion"] for row in app_rows}) != len(app_rows):
        raise ValueError("La salida contiene IDs duplicados")
    # A partial upload must not silently replace the current business dataset.
    summary = {
        "version_reglas": VERSION, "sha256_reglas": RULES_SHA, "lote": sha, "entrada": len(raw),
        "capturas_validas": len(valid), "filas_rechazadas": len(rejects),
        "duplicados_exactos": exact_duplicates,
        "capturas_historicas": len(df) - len(latest),
        "duplicados_titulo_vendedor": int(latest["duplicado_titulo_vendedor"].sum()),
        "filas_utiles_kiara": len(util), "publicaciones_tacctico": len(app_rows),
        "presentaciones_por_revisar": sum(bool(row["revision_presentacion"]) for row in app_rows),
        "publicable": not rejects,
    }
    fields_clean = list(dict.fromkeys([*k.COLUMNAS_SALIDA, "Moneda", "Tiempo", "sellerID"]))
    files = {
        "dataset_limpio.csv": csv_text(df.to_dict("records"), fields_clean),
        "dataset_util.csv": util_csv,
        "mercadolibre_validado.csv": csv_text(app_rows, app_fields),
        "rechazados.csv": csv_text(rejects, ["linea", "id_publicacion", "motivo"]),
        "calidad.json": json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        "entrada_normalizada.csv": csv_text(raw, sorted(set().union(*(r.keys() for r in raw)))),
    }
    files.update(analizar(util, summary))
    result = {"resumen": summary, "archivos": files}
    files["paquete.zip"] = paquete_publicable(result)
    return result
