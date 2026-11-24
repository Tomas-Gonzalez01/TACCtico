import csv
import io
import json
import sqlite3
import subprocess
import sys
import unittest
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory

from importar_mercadolibre import UTIL_FIELDS, preparar_csv
from ingest import ingest


def encode_csv(row):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(row))
    writer.writeheader()
    writer.writerow(row)
    return stream.getvalue()


class IngestTest(unittest.TestCase):
    def test_import_command_works_without_installed_third_party_packages(self):
        row = {
            "idPublicacion": "MLA-TEST-CLI",
            "articuloTitulo": "Premezcla 500 g",
            "nuevoPrecio": "5000",
            "Moneda": "ARS",
            "zProductoLink": "https://articulo.mercadolibre.com.ar/MLA-TEST-CLI",
            "Tiempo": "2026-11-14T19:30:00-03:00",
        }
        with TemporaryDirectory() as temp:
            source = Path(temp) / "crudo.csv"
            destination = Path(temp) / "validado.csv"
            source.write_text(encode_csv(row), encoding="utf-8")
            subprocess.run(
                [
                    sys.executable,
                    "-B",
                    "-S",
                    str(Path(__file__).with_name("importar_mercadolibre.py")),
                    str(source),
                    str(destination),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            with destination.open(encoding="utf-8", newline="") as file:
                (cleaned,) = csv.DictReader(file)
            self.assertEqual(cleaned["id_publicacion"], row["idPublicacion"])
            self.assertEqual(cleaned["precio_publicado"], "5000")
            self.assertEqual(cleaned["capturado_en"], "2026-11-14T22:30:00+00:00")

    def test_curated_lot_keeps_the_original_capture(self):
        original = {
            "idPublicacion": "MLA-test",
            "articuloTitulo": "Premezcla 500 g",
            "nuevoPrecio": "5000",
            "Moneda": "ARS",
            "zProductoLink": "https://articulo.mercadolibre.com.ar/MLA-test",
            "Tiempo": "2026-11-14T19:30:00-03:00",
        }
        row = dict.fromkeys(UTIL_FIELDS, "")
        row.update(
            idPublicacion="MLA-test",
            titulo=original["articuloTitulo"],
            precio="5000.0",
            link=original["zProductoLink"],
            insumo="premezcla_pan",
            gramos_unidad="500",
            unidades="2",
            gramos_totales="1000",
            es_pack="False",
            peso_discrepa="True",
            outlier_precio="False",
            tiene_promo="False",
        )
        original_csv = encode_csv(original)
        with self.assertRaisesRegex(ValueError, "--original"):
            preparar_csv(encode_csv(row))
        with self.assertRaisesRegex(ValueError, "captura original"):
            preparar_csv(encode_csv(dict(row, precio="6000")), original_csv)
        with self.assertRaisesRegex(ValueError, "gramos_totales"):
            preparar_csv(encode_csv(dict(row, gramos_totales="501")), original_csv)

        cleaned = preparar_csv(encode_csv(row), original_csv)["csv_validado"]
        record = next(csv.DictReader(io.StringIO(cleaned)))
        self.assertEqual(record["capturado_en"], "2026-11-14T22:30:00+00:00")
        self.assertEqual(record["moneda"], "ARS")
        self.assertIn("Peso discrepante", record["revision_presentacion"])
        self.assertIn("Formato de pack inconsistente", record["revision_presentacion"])

        with TemporaryDirectory() as directory:
            root = Path(directory)
            snapshot = root / "lote.csv"
            database = root / "historial.sqlite3"
            snapshot.write_text(preparar_csv(original_csv)["csv_validado"], encoding="utf-8")
            self.assertEqual(ingest(snapshot, database), (1, 0))
            snapshot.write_text(cleaned, encoding="utf-8")
            self.assertEqual(ingest(snapshot, database), (0, 1))

    def test_csv_json_history_duplicates_and_rollback(self):
        sample = Path(__file__).resolve().parent / "fixtures" / "datos_mock.csv"
        with sample.open(encoding="utf-8", newline="") as file:
            rows = list(csv.DictReader(file))[:10]

        with TemporaryDirectory() as directory:
            folder = Path(directory)
            database = folder / "capturas.sqlite3"
            csv_path = folder / "muestra.csv"
            json_path = folder / "lote.json"
            with csv_path.open("w", encoding="utf-8", newline="") as file:
                writer = csv.DictWriter(file, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
            self.assertEqual(ingest(csv_path, database), (10, 0))
            self.assertEqual(ingest(csv_path, database), (0, 10))

            later = dict(rows[0], fecha="2026-11-15", precio=20900)
            json_path.write_text(json.dumps([later]), encoding="utf-8")
            self.assertEqual(ingest(json_path, database), (1, 0))
            self.assertEqual(ingest(json_path, database), (0, 1))

            for invalid in (dict(later, precio=21000), dict(later, fecha="inválida"), {"precio": 10}):
                json_path.write_text(
                    json.dumps([dict(later, fecha="2026-11-16"), invalid]),
                    encoding="utf-8",
                )
                with self.assertRaisesRegex(ValueError, "Registro 2"):
                    ingest(json_path, database)
            with closing(sqlite3.connect(database)) as connection:
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM capturas").fetchone()[0], 11)
                history = connection.execute(
                    "SELECT fecha, precio FROM capturas WHERE clave = "
                    "(SELECT clave FROM capturas WHERE fecha = ?) ORDER BY fecha",
                    ("2026-11-15",),
                ).fetchall()
                self.assertEqual(history, [("2026-11-14", "19800"), ("2026-11-15", "20900")])


if __name__ == "__main__":
    unittest.main()
