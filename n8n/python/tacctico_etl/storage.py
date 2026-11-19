"""Lotes inmutables y puntero vigente actualizado después de todos los archivos."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile


def guardar_lote(result, root=Path("/files"), publicar=True):
    root = Path(root)
    batches = root / "lotes"
    batches.mkdir(parents=True, exist_ok=True)
    summary, files = result["resumen"], result["archivos"]
    batch = batches / summary["lote"]
    files = {name: value.encode("utf-8") if isinstance(value, str) else value for name, value in files.items()}
    checksums = {name: hashlib.sha256(value).hexdigest() for name, value in files.items()}
    manifest = {"lote": summary["lote"], "version_reglas": summary["version_reglas"], "sha256": checksums}
    if not batch.exists():
        stage = Path(tempfile.mkdtemp(prefix=".preparando-", dir=batches))
        try:
            for name, value in files.items():
                (stage / name).write_bytes(value)
            (stage / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
            try:
                stage.rename(batch)
            except OSError:
                if not batch.is_dir():
                    raise
        finally:
            if stage.exists():
                shutil.rmtree(stage)
    for name, checksum in checksums.items():
        if hashlib.sha256((batch / name).read_bytes()).hexdigest() != checksum:
            raise ValueError("El lote guardado no coincide con su contenido; vigente conservado")
    if summary["publicable"] and publicar:
        descriptor, temporary = tempfile.mkstemp(prefix=".vigente-", dir=root)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as out:
                out.write(json.dumps(manifest, indent=2) + "\n")
                out.flush()
                os.fsync(out.fileno())
            os.replace(temporary, root / "vigente.json")
        finally:
            Path(temporary).unlink(missing_ok=True)
    return {**summary, "carpeta_salida": str(batch), "estado": "listo" if summary["publicable"] else "requiere_revision"}


def confirmar_publicacion(publication, root=Path("/files")):
    import re
    root = Path(root)
    batch = publication.get("lote", "")
    if not re.fullmatch(r"[a-f0-9]{64}", batch):
        raise ValueError("Identificador de lote inválido")
    folder = root / "lotes" / batch
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    quality = json.loads((folder / "calidad.json").read_text(encoding="utf-8"))
    if manifest["lote"] != batch or quality["lote"] != batch or not quality["publicable"]:
        raise ValueError("El lote no está aprobado por los controles de calidad")
    for kind, name in (("csv", "mercadolibre_validado.csv"), ("paquete", "paquete.zip")):
        remote = publication["archivos"][kind]
        actual = hashlib.sha256((folder / name).read_bytes()).hexdigest()
        if not remote.get("drive_id") or remote["sha256"] != actual or manifest["sha256"][name] != actual:
            raise ValueError("La publicación no coincide con el lote local")
    for filename, value in (("publicado.json", publication), ("vigente.json", manifest)):
        descriptor, temp = tempfile.mkstemp(prefix=".confirmar-", dir=root)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as out:
                json.dump(value, out, ensure_ascii=False, indent=2)
                out.flush()
                os.fsync(out.fileno())
            os.replace(temp, root / filename)
        finally:
            Path(temp).unlink(missing_ok=True)
    return {**publication, "estado": "listo", "publicaciones": publication["publicaciones"]}
