"""Verifica un lote terminado antes de instalarlo atómicamente en la demo local."""
import argparse
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import re
import sys
import tempfile

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "app"))
from purchase_data import load_publications


def verificar(storage):
    manifest = json.loads((storage / "vigente.json").read_text(encoding="utf-8"))
    batch = manifest["lote"]
    if not re.fullmatch("[a-f0-9]{64}", batch):
        raise ValueError("ID de lote inválido")
    folder = storage / "lotes" / batch
    expected = {"dataset_limpio.csv", "dataset_util.csv", "mercadolibre_validado.csv",
                "rechazados.csv", "calidad.json", "entrada_normalizada.csv"}
    allowed = expected | {"metricas.json", "dashboard.html", "paquete.zip"}
    if not expected <= set(manifest["sha256"]) or not set(manifest["sha256"]) <= allowed:
        raise ValueError("El manifiesto no tiene todos los archivos esperados")
    for name, digest in manifest["sha256"].items():
        if hashlib.sha256((folder / name).read_bytes()).hexdigest() != digest:
            raise ValueError(f"El archivo {name} no supera el control de integridad")
    summary = json.loads((folder / "calidad.json").read_text(encoding="utf-8"))
    if not summary["publicable"] or summary["lote"] != batch:
        raise ValueError("El lote no está aprobado por los controles")
    path = folder / "mercadolibre_validado.csv"
    groups = load_publications(path, None)
    publications = [item for group in groups.values() for _, item in group]
    if len(publications) != summary["publicaciones_tacctico"]:
        raise ValueError("La cantidad de publicaciones cargadas en TACCtico no coincide")
    if any(item.review and item.offer.pack is not None for item in publications):
        raise ValueError("Una presentación pendiente permite calcular peso")
    return path, summary


def aplicar(storage, destination):
    path, summary = verificar(storage)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        previous = destination.read_bytes()
        backup = ROOT / "backups" / ("antes-" + hashlib.sha256(previous).hexdigest() + ".csv")
        backup.parent.mkdir(exist_ok=True)
        if not backup.exists():
            backup.write_bytes(previous)
    descriptor, temporary = tempfile.mkstemp(dir=destination.parent, prefix=".nuevo-lote-")
    try:
        with os.fdopen(descriptor, "wb") as out:
            out.write(path.read_bytes())
            out.flush()
            os.fsync(out.fileno())
        os.replace(temporary, destination)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--aplicar", action="store_true", help="Actualizar la demo local después de validar")
    args = parser.parse_args()
    storage = ROOT / "storage"
    if args.aplicar:
        result = aplicar(storage, ROOT.parent / "data_real/mercadolibre_validado.csv")
    else:
        _, result = verificar(storage)
    print(json.dumps(result, ensure_ascii=False, indent=2))
