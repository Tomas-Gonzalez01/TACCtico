import csv
import io
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

sys.path.insert(0, str(Path(__file__).parent / "python"))
from tacctico_etl import procesar, guardar_lote


def publication(**updates):
    row = {
        "idPublicacion": "MLA-TEST",
        "articuloTitulo": "Premezcla para pan 500g",
        "nuevoPrecio": "5000",
        "Moneda": "ARS",
        "zProductoLink": "https://articulo.mercadolibre.com.ar/MLA-TEST",
        "Tiempo": "2026-11-14T20:00:00-03:00",
        "esTiendaOficial": "False",
    }
    return {**row, **updates}


def output(result, filename="mercadolibre_validado.csv"):
    return list(csv.DictReader(io.StringIO(result["archivos"][filename])))


class PipelineTests(unittest.TestCase):
    def test_capture_currency_and_false_flag(self):
        result = procesar([publication()])
        row = output(result)[0]
        self.assertEqual(row["capturado_en"], "2026-11-14T23:00:00+00:00")
        self.assertEqual(row["moneda"], "ARS")
        self.assertEqual(row["tipo_vendedor"], "sin_dato")
        self.assertEqual(row["gramos_totales"], "500.0")

    def test_pack_math_and_total_weight(self):
        for title in ("Premezcla para pan 2 x 500g", "Premezcla para pan 500g x2"):
            row = output(procesar([publication(articuloTitulo=title)]))[0]
            self.assertEqual(row["unidades"], "2")
            self.assertEqual(row["gramos_totales"], "1000.0")
            self.assertEqual(float(row["precio_100g"]), 500)
        row = output(procesar([publication(articuloTitulo="Chips chocolate caja x3kg")]))[0]
        self.assertEqual(row["gramos_totales"], "3000.0")

    def test_ambiguous_pack_stays_in_catalog_without_comparison(self):
        ambiguous = publication(
            idPublicacion="MLA-PACK",
            articuloTitulo="Premezcla para pan pack x2",
            **{"caracteristicas/0/name": "Peso neto", "caracteristicas/0/value": "500 g"},
        )
        result = procesar([publication(), ambiguous])
        row = next(r for r in output(result) if r["id_publicacion"] == "MLA-PACK")
        self.assertEqual(row["revision_presentacion"], "Presentación sin confirmar")
        self.assertEqual(row["precio_100g"], "")
        self.assertEqual(len(output(result, "dataset_util.csv")), 1)

    def test_conflicting_weight_blocks_comparison(self):
        row = output(
            procesar(
                [
                    publication(
                        **{
                            "caracteristicas/0/name": "Peso neto",
                            "caracteristicas/0/value": "250 g",
                        }
                    )
                ]
            )
        )[0]
        self.assertIn("Peso discrepante", row["revision_presentacion"])
        self.assertEqual(row["precio_100g"], "")

    def test_historical_capture_retained_and_latest_selected(self):
        later = publication(nuevoPrecio="6000", Tiempo="2026-11-15T23:00:00Z")
        result = procesar([publication(), later])
        self.assertEqual(result["resumen"]["capturas_historicas"], 1)
        self.assertEqual(len(output(result, "dataset_limpio.csv")), 2)
        self.assertEqual(Decimal(output(result)[0]["precio_publicado"]), Decimal("6000"))

    def test_exact_duplicate_and_conflict(self):
        result = procesar([publication(), publication()])
        self.assertEqual(result["resumen"]["duplicados_exactos"], 1)
        self.assertEqual(len(output(result)), 1)
        with self.assertRaisesRegex(ValueError, "valores distintos"):
            procesar([publication(), publication(nuevoPrecio="6000")])

    def test_bad_schema_and_empty_result(self):
        for rows in (
            [],
            [{"titulo": "no es el esquema crudo"}],
            [publication(nuevoPrecio="NaN")],
            [publication(Tiempo="2026-11-14")],
            [publication(Moneda="USD")],
        ):
            with self.assertRaises(ValueError):
                procesar(rows)

    def test_idempotency_and_bad_batch_preserves_current(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            good = procesar([publication()])
            first = guardar_lote(good, root)
            pointer = (root / "vigente.json").read_bytes()
            self.assertEqual(first, guardar_lote(procesar([publication()]), root))
            self.assertEqual(len(list((root / "lotes").iterdir())), 1)
            bad = procesar([publication(), publication(idPublicacion="MLA-BAD", nuevoPrecio="-1")])
            self.assertEqual(guardar_lote(bad, root)["estado"], "requiere_revision")
            self.assertEqual(pointer, (root / "vigente.json").read_bytes())
            (root / "lotes" / first["lote"] / "mercadolibre_validado.csv").write_text("corrupto")
            with self.assertRaisesRegex(ValueError, "no coincide"):
                guardar_lote(good, root)
            self.assertEqual(pointer, (root / "vigente.json").read_bytes())


from decimal import Decimal

if __name__ == "__main__":
    unittest.main()
