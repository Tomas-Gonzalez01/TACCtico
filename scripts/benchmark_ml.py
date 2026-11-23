"""Medición local real de inferencia; no confunde CPU con precio de Apify."""

import csv
import json
import platform
import statistics
import sys
import time
from pathlib import Path

import psutil

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "n8n/python"))
from tacctico_etl.ml_model import infer_rows


def benchmark():
    with (ROOT / "data_public/actual/mercadolibre_validado.csv").open(encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))
    process = psutil.Process()
    start = time.perf_counter()
    result = infer_rows(rows)
    cold = time.perf_counter() - start
    durations, rss = [], []
    cpu_before = sum(process.cpu_times()[:2])
    for _ in range(20):
        start = time.perf_counter()
        infer_rows(rows)
        durations.append(time.perf_counter() - start)
        rss.append(process.memory_info().rss / 1024**2)
    data = {
        "modelo_id": result["modelo_id"],
        "fecha": "2026-11-23",
        "entorno": "Windows local; no es una corrida de Apify",
        "publicaciones": len(rows),
        "evaluadas": result["publicaciones_evaluadas"],
        "repeticiones_calientes": len(durations),
        "segundos_carga_e_inferencia": cold,
        "mediana_segundos_inferencia": statistics.median(durations),
        "p95_segundos_inferencia": sorted(durations)[18],
        "cpu_segundos_20_repeticiones": sum(process.cpu_times()[:2]) - cpu_before,
        "rss_maximo_observado_mib": max(rss),
        "gpu": "No utilizada",
        "python": platform.python_version(),
        "cpu": platform.processor(),
        "costo_apify_real_usd": None,
        "nota": "RSS observado entre corridas, no pico garantizado. Costo local de equipo y electricidad no cuantificado.",
    }
    path = ROOT / "n8n/python/tacctico_etl/models/benchmark_local.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(data, ensure_ascii=False, indent=2))
    return data


if __name__ == "__main__":
    benchmark()
