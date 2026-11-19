"""Lectura de lotes verificados. No carga ni necesita credenciales de n8n."""
import hashlib
import io
import json
import os
from pathlib import Path
import re
import tempfile
from urllib.request import Request, urlopen
import zipfile

FILES = {"mercadolibre_validado.csv", "metricas.json", "dashboard.html", "calidad.json"}


def verify_folder(folder):
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    batch = manifest.get("lote", "")
    if not re.fullmatch("[a-f0-9]{64}", batch):
        raise ValueError("El lote no tiene una identidad válida")
    entries = manifest.get("archivos")
    # The n8n local archive has the internal manifest format; the public bundle
    # has an allowlisted subset and its own public manifest.
    if entries is None:
        entries = {name: {"sha256": digest} for name, digest in manifest["sha256"].items() if name in FILES}
    if set(entries) != FILES:
        raise ValueError("Faltan archivos del lote")
    for name, meta in entries.items():
        if hashlib.sha256((folder / name).read_bytes()).hexdigest() != meta["sha256"]:
            raise ValueError("Un archivo no coincide con su lote")
    metrics = json.loads((folder / "metricas.json").read_text(encoding="utf-8"))
    quality = json.loads((folder / "calidad.json").read_text(encoding="utf-8"))
    if metrics["lote"] != batch or quality["lote"] != batch or not quality["publicable"]:
        raise ValueError("Los resultados no pertenecen a la misma ejecución")
    return {"lote": batch, "folder": str(folder), "metrics": metrics, "quality": quality}


def download_google(file_id, maximum):
    if not re.fullmatch(r"[A-Za-z0-9_-]{10,120}", file_id):
        raise ValueError("Referencia de Drive inválida")
    request = Request("https://drive.google.com/uc?export=download&id=" + file_id,
                      headers={"User-Agent": "TACCtico/1.0"})
    with urlopen(request, timeout=20) as response:
        content = response.read(maximum + 1)
    if len(content) > maximum:
        raise ValueError("El archivo supera el tamaño permitido")
    return content


def unpack(data, destination):
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        if len(archive.namelist()) != 5 or set(archive.namelist()) != FILES | {"manifest.json"}:
            raise ValueError("El paquete contiene archivos inesperados")
        if sum(x.file_size for x in archive.infolist()) > 30_000_000:
            raise ValueError("El paquete supera el tamaño permitido")
        destination.mkdir(parents=True, exist_ok=True)
        for name in archive.namelist():
            (destination / name).write_bytes(archive.read(name))
    return verify_folder(destination)


def load_remote(pointer_id):
    pointer = json.loads(download_google(pointer_id, 50_000).decode("utf-8"))
    batch = pointer.get("lote", "")
    if pointer.get("schema_version") != 1 or not re.fullmatch("[a-f0-9]{64}", batch):
        raise ValueError("No se pudo reconocer la actualización")
    target = pointer["archivos"]["paquete"]
    root = Path(tempfile.gettempdir()) / "tacctico-lotes" / batch
    if root.exists() and (root / ".paquete_sha256").is_file() and (root / ".paquete_sha256").read_text() == target["sha256"]:
        try:
            return verify_folder(root)
        except (OSError, ValueError, KeyError):
            pass
    data = download_google(target["drive_id"], 10_000_000)
    if len(data) != target["bytes"] or hashlib.sha256(data).hexdigest() != target["sha256"]:
        raise ValueError("La actualización no superó el control de integridad")
    release = unpack(data, root)
    if release["lote"] != batch:
        raise ValueError("El paquete no corresponde a la actualización indicada")
    (root / ".paquete_sha256").write_text(target["sha256"])
    return release


def load_local(root):
    storage = root / "n8n/storage"
    if (storage / "publicado.json").is_file():
        pointer = json.loads((storage / "publicado.json").read_text(encoding="utf-8"))
        batch = pointer.get("lote", "")
        if re.fullmatch("[a-f0-9]{64}", batch):
            return verify_folder(storage / "lotes" / batch)
    current = root / "data_public/actual"
    if (current / "manifest.json").is_file():
        return verify_folder(current)
    return None


def remote_id(root):
    configured = os.environ.get("TACCTICO_MANIFEST_ID", "").strip()
    path = root / "data_public/conexion.json"
    if not configured and path.is_file():
        configured = json.loads(path.read_text(encoding="utf-8")).get("manifest_id", "")
    return configured
