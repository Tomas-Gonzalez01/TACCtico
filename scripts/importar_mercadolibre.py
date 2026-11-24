"""Importa CSV desde la consola usando las mismas reglas que el flujo de n8n."""

import argparse
import csv
from importlib.util import module_from_spec, spec_from_file_location
import os
from pathlib import Path
import tempfile


# El adaptador usa solo la biblioteca estándar. Cargarlo directamente evita
# exigir pandas y NumPy para esta herramienta de importación.
ADAPTER_PATH = Path(__file__).resolve().parents[1] / "n8n/python/tacctico_etl/app_adapter.py"
_spec = spec_from_file_location("tacctico_csv_adapter", ADAPTER_PATH)
_adapter = module_from_spec(_spec)
_spec.loader.exec_module(_adapter)
FIELDS = _adapter.FIELDS
UTIL_FIELDS = _adapter.UTIL_FIELDS
preparar_csv = _adapter.preparar_csv


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("entrada", type=Path)
    parser.add_argument("salida", type=Path)
    parser.add_argument(
        "--original", type=Path, help="CSV original del mismo lote para importar dataset_util.csv."
    )
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
