"""Mismo modelo y contrato que n8n, ejecutado como actor de Apify."""

import asyncio
import csv
import platform
import time
from pathlib import Path

import psutil
from tacctico_etl.ml_model import infer_rows


def read_dataset():
    path = Path("data.csv")
    if not path.is_file():
        path = Path("data_public/actual/mercadolibre_validado.csv")
    with path.open(encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


from apify import Actor


async def main():
    async with Actor:
        config = await Actor.get_input() or {}
        rows = config.get("publicaciones")
        if rows is None and config.get("usar_dataset_incluido", True):
            rows = await asyncio.to_thread(read_dataset)
        process = psutil.Process()
        cpu_before = sum(process.cpu_times()[:2])
        started = time.perf_counter()
        result = await asyncio.to_thread(infer_rows, rows)
        result["ejecucion"] = {
            "segundos_inferencia": time.perf_counter() - started,
            "cpu_segundos": sum(process.cpu_times()[:2]) - cpu_before,
            "rss_proceso_mib": process.memory_info().rss / 1024**2,
            "gpu": "No utilizada",
            "cpu_logicas_disponibles": psutil.cpu_count(),
            "plataforma": platform.system(),
            "costo_apify_usd": None,
            "nota_costo": "El costo real se consulta en usageTotalUsd de esta ejecución, no se estima desde el gasto histórico.",
        }
        await Actor.set_value("OUTPUT", result)
        await Actor.push_data(
            [
                {"id_publicacion": key, "modelo_id": result["modelo_id"], **value}
                for key, value in result["predicciones"].items()
            ]
        )
        Actor.log.info(
            f"Evaluadas {result['publicaciones_evaluadas']}; para revisar {result['para_revisar']}; sin evaluar {result['sin_evaluar']}."
        )
