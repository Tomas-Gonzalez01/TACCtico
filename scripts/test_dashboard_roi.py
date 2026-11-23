import json
import re
import shutil
import subprocess
import sys
import unittest
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from data_release import verify_folder

TEMPLATE = ROOT / "n8n/python/tacctico_etl/templates/dashboard_kiara.html"
PUBLISHED = ROOT / "data_public/actual"


class DashboardRoiTests(unittest.TestCase):
    def test_template_and_published_dashboard_include_the_roi(self):
        for path in (TEMPLATE, PUBLISHED / "dashboard.html"):
            html = path.read_text(encoding="utf-8")
            with self.subTest(file=path.name):
                for element in ('id="r1"', 'id="r2"', 'id="r3"', 'id="roi"'):
                    self.assertIn(element, html)
                # El costo mensual en pesos fue reemplazado por el costo en dólares del ROI.
                self.assertNotIn('id="t6"', html)
                self.assertIn("ROI = (ahorro anual en compras", html)

    def test_published_dashboard_is_the_template_with_the_batch_data(self):
        template = TEMPLATE.read_text(encoding="utf-8")
        published = (PUBLISHED / "dashboard.html").read_text(encoding="utf-8")
        # Lo publicado solo puede diferir de la plantilla en los datos del lote (marcadores __TACCTICO_*__).
        parts = re.split(r"__TACCTICO_[A-Z]+__", template)
        self.assertGreater(len(parts), 1)
        self.assertTrue(published.startswith(parts[0]))
        self.assertTrue(published.endswith(parts[-1]))
        position = 0
        for part in parts:
            found = published.find(part, position)
            self.assertNotEqual(found, -1)
            position = found + len(part)

    def test_published_manifest_matches_the_dashboard(self):
        self.assertIsNotNone(verify_folder(PUBLISHED))

    def test_exported_assumptions_match_the_dashboard_reference(self):
        metrics = json.loads((PUBLISHED / "metricas.json").read_text(encoding="utf-8"))
        html = (PUBLISHED / "dashboard.html").read_text(encoding="utf-8")
        meta = json.loads(re.search(r"\bMETA\s*=\s*(\{.*?\});", html, re.DOTALL)[1])
        self.assertEqual(meta["roi"], metrics["supuestos"]["roi"])
        self.assertEqual(meta["id_lote"], metrics["lote"])
        self.assertFalse(meta["roi"]["incluye_tiempo"])
        self.assertEqual(metrics["catalogo"], 372)
        self.assertEqual(metrics["base_sin_atipicos"], 330)
        self.assertTrue(metrics["captura_hasta"].startswith("2026-11-14"))


@unittest.skipUnless(shutil.which("node"), "Node.js permite comprobar el cálculo JavaScript del dashboard.")
class DashboardRoiMathTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        html = TEMPLATE.read_text(encoding="utf-8")
        cls.function = html[html.index("function calcularROI(") : html.index("function mostrarROI(")]

    def calculate(self, cases):
        program = self.function + (
            "\nconst cases=JSON.parse(require('node:fs').readFileSync(0,'utf8'));\n"
            "process.stdout.write(JSON.stringify(cases.map(c=>calcularROI(...c))));"
        )
        completed = subprocess.run(
            [shutil.which("node"), "-e", program],
            input=json.dumps(cases, allow_nan=False),
            text=True,
            capture_output=True,
            check=True,
            timeout=10,
        )
        return json.loads(completed.stdout)

    def test_real_capture_cost_net_benefit_and_roi_match_independent_arithmetic(self):
        metrics = json.loads((PUBLISHED / "metricas.json").read_text(encoding="utf-8"))
        savings = [item["ah"] for item in metrics["lote_recetas"].values()]
        result = self.calculate([[savings, [40, 120, 300], 15, 12, 1701]])[0]
        self.assertEqual(result["costoUSD"], 180)
        self.assertEqual(result["costoARS"], 306180)
        average = sum(Decimal(str(value)) for value in savings) / len(savings)
        for index, batches in enumerate((40, 120, 300)):
            gross = average * batches * 12
            net = gross - Decimal(306180)
            self.assertAlmostEqual(result["beneficios"][index], float(gross), places=7)
            self.assertAlmostEqual(result["netos"][index], float(net), places=7)
            self.assertAlmostEqual(result["porcentajes"][index], float(net / 306180 * 100), places=7)

    def test_editing_cost_frequency_or_exchange_rate_recalculates_annual_cost(self):
        cases = [
            [[100], [40, 120, 300], *cost]
            for cost in ((15, 12, 1701), (10, 12, 1701), (15, 6, 1701), (15, 12, 1000))
        ]
        for result, expected in zip(self.calculate(cases), (306180, 204120, 153090, 180000)):
            self.assertEqual(result["costoARS"], expected)
            self.assertEqual(result["beneficios"], [48000, 144000, 360000])

    def test_zero_cost_reports_net_benefit_without_dividing_by_zero(self):
        for result in self.calculate(
            [
                [[100], [40, 120, 300], 0, 12, 1701],
                [[100], [40, 120, 300], 15, 0, 1701],
            ]
        ):
            self.assertEqual(result["costoARS"], 0)
            self.assertEqual(result["netos"], result["beneficios"])
            self.assertEqual(result["porcentajes"], [None, None, None])

    def test_missing_negative_or_invalid_cost_inputs_have_no_roi(self):
        inputs = (
            (None, 12, 1701),
            (15, None, 1701),
            (15, 12, None),
            (-1, 12, 1701),
            (15, -1, 1701),
            (15, 12, -1),
            (15, 12, 0),
            (15, 1.5, 1701),
        )
        for result in self.calculate([[[100], [40, 120, 300], *values] for values in inputs]):
            self.assertIsNone(result["costoARS"])
            self.assertEqual(result["netos"], [None, None, None])
            self.assertEqual(result["porcentajes"], [None, None, None])

    def test_missing_recipes_and_invalid_volumes_are_not_presented_as_zero_savings(self):
        missing, invalid = self.calculate(
            [
                [[], [40, 120, 300], 15, 12, 1701],
                [[100], [40, -1, 300], 15, 12, 1701],
            ]
        )
        self.assertEqual(missing["beneficios"], [None, None, None])
        self.assertEqual(missing["porcentajes"], [None, None, None])
        self.assertIsNone(invalid["beneficios"][1])
        self.assertIsNone(invalid["porcentajes"][1])
        self.assertEqual(invalid["beneficios"][0], 48000)

    def test_zero_or_insufficient_savings_can_produce_a_negative_roi(self):
        zero, loss = self.calculate(
            [
                [[0], [40, 120, 300], 10, 1, 100],
                [[1], [40, 120, 300], 10, 1, 100],
            ]
        )
        self.assertEqual(zero["porcentajes"], [-100, -100, -100])
        self.assertEqual(loss["netos"][0], -520)
        self.assertEqual(loss["porcentajes"][0], -52)

    def test_template_javascript_is_syntactically_valid(self):
        html = TEMPLATE.read_text(encoding="utf-8")
        scripts = "\n".join(re.findall(r"<script\b[^>]*>(.*?)</script>", html, re.DOTALL))
        subprocess.run(
            [shutil.which("node"), "--check"],
            input=scripts,
            text=True,
            capture_output=True,
            check=True,
            timeout=10,
        )


if __name__ == "__main__":
    unittest.main()
