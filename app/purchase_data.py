import csv
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlsplit

from purchase_engine import Offer, Supplier


def market_csv(root: Path) -> Path:
    from data_release import load_local
    try:
        release = load_local(root)
        if release:
            return Path(release["folder"]) / "mercadolibre_validado.csv"
    except (OSError, ValueError, KeyError, TypeError):
        pass
    local = root / "data_real" / "mercadolibre_validado.csv"
    if local.is_file():
        return local
    return root / "data_public" / "mercadolibre_validado_2026-11-14.csv"


WEIGHT = r"(\d+(?:[.,]\d+)?)\s*(kg|grs?|g)\b"
PACK_BEFORE = re.compile(r"\b(\d+)\s*[x×]\s*" + WEIGHT, re.IGNORECASE)
PACK_AFTER = re.compile(WEIGHT + r"\s*[x×]\s*(\d+)\b(?!\s*(?:[.,]\d|kg|g(?:r|rs)?\b))", re.IGNORECASE)
PACK_COUNT = re.compile(
    r"\b(?:pack|bulto|caja|combo)\s*(?:de|x|×)?\s*(\d+)|\b(\d+)\s*u(?:n(?:idades?)?)?\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Publication:
    offer: Offer
    units: int | None
    insumo: str = ""
    review: str = ""
    brand: str = ""


def kilograms(value, unit):
    amount = Decimal(value.replace(",", "."))
    return amount if unit.casefold() == "kg" else amount / 1000


def resolve_presentation(title, specs):
    format_name = specs.get("Formato de venta", "").strip().casefold()
    match = re.fullmatch(WEIGHT, specs.get("Peso neto", "").strip(), re.IGNORECASE)
    weight = kilograms(*match.groups()) if match else None
    counts = {
        int(specs[name]) for name in ("Unidades por pack", "Cantidad de unidades", "Cantidad de envases")
        if specs.get(name, "").strip().isdigit()
    }
    multiplications = [(int(n), kilograms(w, u)) for n, w, u in PACK_BEFORE.findall(title)]
    multiplications.extend((int(n), kilograms(w, u)) for w, u, n in PACK_AFTER.findall(title))
    title_counts = {count for count, _ in multiplications}
    title_counts.update(int(first or second) for first, second in PACK_COUNT.findall(title))

    if format_name == "unidad":
        if counts - {1} or title_counts - {1} or re.search(r"\b(pack|bulto|combo|caja)\b", title, re.IGNORECASE):
            return None, None
        title_weights = {kilograms(w, u) for w, u in re.findall(WEIGHT, title, re.IGNORECASE)}
        return 1, weight if not title_weights or title_weights == {weight} else None

    if format_name != "pack" or len(counts) != 1:
        return None, None
    count = counts.pop()
    if count < 2 or title_counts - {count}:
        return None, None
    unit_weights = {amount for n, amount in multiplications if n == count and amount > 0}
    if len(unit_weights) == 1:
        unit_weight = unit_weights.pop()
        if weight in (unit_weight, unit_weight * count):
            return count, unit_weight * count
    return count, None


def read_csv(path):
    try:
        with path.open(encoding="utf-8-sig", newline="") as file:
            return list(csv.DictReader(file, strict=True))
    except csv.Error as error:
        raise ValueError(f"El archivo {path.name} tiene un formato CSV inválido.") from error


def details_index(path):
    if path is None:
        return {}
    rows = read_csv(path)
    return {
        (row["idPublicacion"].strip(), datetime.fromisoformat(row["Tiempo"])): row
        for row in rows if row.get("idPublicacion") and row.get("Tiempo")
    }


def load_publications(snapshot, original):
    rows = read_csv(snapshot)
    curated = bool(rows and "insumo" in rows[0])
    if rows and not curated and original is None:
        raise ValueError("El lote anterior requiere dataset_final.csv para recuperar las presentaciones.")
    details = {} if curated else details_index(original)
    sellers = {}
    groups = defaultdict(list)
    for row in rows:
        listing = row["id_publicacion"].strip()
        title = row["titulo"].strip()
        url = row["url"]
        parsed = urlsplit(url)
        price = Decimal(row["precio_publicado"])
        if (
            not listing or not title or row["moneda"] != "ARS" or not price.is_finite() or price <= 0
            or parsed.scheme != "https" or parsed.netloc != "articulo.mercadolibre.com.ar"
        ):
            raise ValueError("El CSV validado contiene una publicación con datos inválidos.")
        insumo = row.get("insumo", "")
        review = row.get("revision_presentacion", "")
        if curated:
            units, kg = (None, None) if review else (
                int(row["unidades"]), Decimal(row["gramos_totales"]) / 1000,
            )
            seller_id, seller_name = row["vendedor_id"], row["vendedor"]
            parts = [row[key] for key in ("marca", "nombre_ficha", "linea", "sabor")]
            registration = row["rnpa"]
            shipping, promotion, category = (row[key] for key in ("envio", "promocion", "categoria"))
        else:
            detail = details.get((listing, datetime.fromisoformat(row["capturado_en"])), {})
            specs = {
                detail[key]: detail.get(key.removesuffix("/name") + "/value", "")
                for key in detail if key.startswith("caracteristicas/") and key.endswith("/name") and detail[key]
            }
            units, kg = resolve_presentation(title, specs)
            seller_id = detail.get("sellerID", "").strip()
            seller_name = detail.get("Vendedor", "").strip()
            parts = [specs.get(name, "").strip() for name in ("Marca", "Nombre", "Línea", "Sabor")]
            registration = specs.get("Número de inscripción de producto (RNPA)", "").strip()
            shipping, promotion, category = (
                detail.get(key, "").strip() for key in ("Envio", "promociones", "produtoCategoryID")
            )
        seller_key = seller_id or f"publicación:{listing}"
        seller = sellers.setdefault(
            seller_key, Supplier(seller_name or "Vendedor sin confirmar", None, None, seller_key)
        )

        if all(parts[:2]) and kg and units:
            presentation = f"{kg / units:g} kg c/u"
            name = " · ".join(part for part in (*parts, presentation, registration) if part)
            identity = (insumo, *parts, registration, presentation)
        else:
            name = title
            identity = (title, listing)
        key = tuple(part.casefold().strip() for part in identity)
        groups[key].append((name, Publication(Offer(
            product=title,
            supplier=seller,
            pack=kg,
            unit="kg",
            price=price,
            basis="publicado",
            listing=listing,
            url=url,
            shipping_note=shipping,
            promotion=promotion,
            category=category,
            captured=row["capturado_en"],
            units_per_pack=units,
            outlier_price=row.get("outlier_precio") == "true",
        ), units, insumo, review, parts[0])))
    return groups
