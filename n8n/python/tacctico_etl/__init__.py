"""Entrada del nodo Python de n8n para limpieza y análisis del lote real."""
from .pipeline import procesar
from .storage import guardar_lote, confirmar_publicacion
import hashlib
import json


def ejecutar(items, publicar=True):
    resultado = procesar([item["json"] for item in items])
    resumen = guardar_lote(resultado, publicar=publicar)
    contenido = resultado["archivos"]["mercadolibre_validado.csv"].encode("utf-8")
    archivos = []
    for kind, local, remote, mime in (
        ("csv", "mercadolibre_validado.csv", "mercadolibre_validado_" + resumen["lote"] + ".csv", "text/csv"),
        ("paquete", "paquete.zip", "tacctico_" + resumen["lote"] + ".zip", "application/zip"),
    ):
        value = resultado["archivos"][local]
        value = value.encode("utf-8") if isinstance(value, str) else value
        archivos.append({"tipo": kind, "lote": resumen["lote"], "nombre": remote, "mime": mime,
            "ruta": resumen["carpeta_salida"] + "/" + local, "bytes": len(value),
            "md5": hashlib.md5(value).hexdigest(), "sha256": hashlib.sha256(value).hexdigest()})
    return {
        **resumen,
        "modelo_id": json.loads(resultado["archivos"]["metricas.json"])["ml"]["modelo_id"],
        "archivo_sha256": hashlib.sha256(contenido).hexdigest(),
        "archivo_md5": hashlib.md5(contenido).hexdigest(),
        "archivo_bytes": len(contenido),
        "nombre_remoto": "mercadolibre_validado_" + resumen["lote"] + ".csv",
        "archivos_publicar": archivos,
    }
