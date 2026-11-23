import copy
import csv
import json
import sys
import unittest
from pathlib import Path

import joblib
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "n8n/python"))
from tacctico_etl.ml_model import (
    MODEL_DIR,
    anomaly_features,
    clean_record,
    infer_rows,
    load_model,
    predict_portable,
    reference_features,
)


class ModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with (ROOT / "data_public/actual/mercadolibre_validado.csv").open(encoding="utf-8", newline="") as f:
            cls.rows = list(csv.DictReader(f))
        cls.valid = next(r for r in cls.rows if clean_record(r)[0])

    def test_real_snapshot_and_determinism(self):
        first = infer_rows(self.rows)
        self.assertEqual(first, infer_rows(self.rows))
        self.assertEqual(first["publicaciones_evaluadas"], 335)
        self.assertEqual(first["sin_evaluar"], 37)
        self.assertEqual(len(first["predicciones"]), 372)
        for result in first["predicciones"].values():
            if result["estado"] == "evaluado":
                self.assertGreater(result["precio_referencia_kg"], 0)
                self.assertIsInstance(result["revisar"], bool)

    def test_ambiguous_weight_does_not_get_invented(self):
        result = infer_rows([{**self.valid, "revision_presentacion": "Peso por confirmar"}])
        self.assertEqual(result["publicaciones_evaluadas"], 0)
        self.assertNotIn("precio_referencia_kg", next(iter(result["predicciones"].values())))

    def test_invalid_values_unknown_categories_and_currency(self):
        for updates in (
            {"precio_publicado": "NaN"},
            {"precio_publicado": -1},
            {"precio_publicado": True},
            {"gramos_totales": 0},
            {"unidades": 1.2},
            {"insumo": "no_visto"},
            {"moneda": "USD"},
            {"peso_discrepa": True},
            {"gramos_unidad": 99999},
        ):
            with self.subTest(updates=updates):
                self.assertEqual(infer_rows([{**self.valid, **updates}])["publicaciones_evaluadas"], 0)

    def test_contract_rejects_empty_duplicate_and_excessive_batches(self):
        for value in ([], None, {}, [self.valid, self.valid], [self.valid] * 2001, [{"precio_publicado": 1}]):
            with self.assertRaises(ValueError):
                infer_rows(value)

    def test_model_and_report_have_disjoint_holdout_groups(self):
        _, metadata = load_model()
        report = json.loads((MODEL_DIR / "evaluacion.json").read_text(encoding="utf-8"))
        self.assertEqual(report["particion"]["grupos_compartidos"], 0)
        self.assertEqual(report["filas_elegibles"], 335)
        self.assertEqual(report["dataset_sha256"], metadata["dataset_sha256"])
        self.assertIsNone(report["anomalias"]["accuracy_real"])
        results = json.loads((MODEL_DIR / "prueba_reservada.json").read_text(encoding="utf-8"))
        actual_mae = sum(abs(r["real_kg"] - r["estimado_kg"]) for r in results) / len(results)
        self.assertAlmostEqual(actual_mae, report["referencia_precio"]["prueba_reservada"]["mae_ars_por_kg"])

    def test_inference_does_not_mutate_the_catalog_or_prices(self):
        before = copy.deepcopy(self.rows)
        infer_rows(self.rows)
        self.assertEqual(self.rows, before)

    def test_portable_model_matches_original_sklearn_predictions(self):
        model, metadata = load_model()
        import hashlib

        payload = (MODEL_DIR / "precios.joblib").read_bytes()
        self.assertEqual(hashlib.sha256(payload).hexdigest(), metadata["sha256_joblib"])
        original = joblib.load(MODEL_DIR / "precios.joblib")
        rows = [clean_record(r)[0] for r in self.rows if clean_record(r)[0] is not None]
        margins, prices = predict_portable(model, rows)
        np.testing.assert_allclose(
            prices, np.exp(original["reference"].predict(reference_features(rows))), rtol=1e-12
        )
        np.testing.assert_allclose(
            margins,
            original["isolation"].decision_function(anomaly_features(rows, original["centers"])),
            atol=1e-12,
        )


if __name__ == "__main__":
    unittest.main()
