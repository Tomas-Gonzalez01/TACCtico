"""La presentación de importes no cambia orden, filtros, presupuestos ni el dashboard."""
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import pandas as pd
import pyarrow as pa
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
import budget_view


class CatalogPresentationTests(unittest.TestCase):
    def test_argentine_prices_keep_numeric_sort_and_filter(self):
        app = AppTest.from_file(str(ROOT / "app/streamlit_app.py"), default_timeout=20).run()
        self.assertFalse(app.exception or app.error)
        grid = app.dataframe[0]
        self.assertTrue(pd.api.types.is_numeric_dtype(grid.value["precio_publicado"]))
        displayed = pa.ipc.open_stream(grid.proto.styler.display_values).read_all().to_pandas()
        self.assertEqual(displayed.iloc[0]["precio_publicado"], "ARS 3.500,00")
        self.assertEqual(displayed.iloc[0]["precio_100g"], "Sin dato")
        self.assertIn("Polvo de hornear", set(grid.value["insumo"]))
        app.number_input(key="precio_minimo").set_value(3600).run()
        self.assertFalse(app.exception or app.error)
        self.assertTrue(app.dataframe[0].value["precio_publicado"].ge(3600).all())

    def test_dashboard_body_is_preserved_without_the_general_banner(self):
        app = AppTest.from_file(str(ROOT / "app/streamlit_app.py"), default_timeout=20).run()
        self.assertTrue(any('class="tacctico-header"' in element.proto.body for element in app.get("html")))
        app.radio(key="seccion").set_value("Dashboard").run()
        self.assertFalse(app.exception or app.error)
        self.assertFalse(any('class="tacctico-header"' in element.proto.body for element in app.get("html")))
        expected = (Path(app.session_state["lote_datos"]["folder"]) / "dashboard.html").read_text(encoding="utf-8")
        self.assertEqual(app.get("iframe")[0].proto.srcdoc, expected)

    def test_mobile_summary_uses_the_same_amount_as_the_budget(self):
        app = AppTest.from_file(str(ROOT / "app/streamlit_app.py"), default_timeout=20).run()
        with patch.object(budget_view, "OFFER_PICKER", return_value=SimpleNamespace(add_offer=None)):
            app.radio(key="seccion").set_value("Arma tu presupuesto").run()
            from purchase_data import load_publications, market_csv
            from purchase_engine import candidate_quotes
            from decimal import Decimal
            products = load_publications(market_csv(ROOT), None)
            offer = next(item.offer for group in products.values() for _, item in group
                         if item.offer.pack and not item.offer.outlier_price)
            quote = next(candidate_quotes(offer, Decimal(1), "kg", published=True))
            app.session_state["lista_compras"] = {("insumo_por_peso", "prueba"): quote}
            app.run()
            self.assertFalse(app.exception or app.error)
            bar = next(element.proto.body for element in app.get("html") if 'class="mobile-budget"' in element.proto.body)
            self.assertIn(app.metric[-1].value, bar)
            self.assertIn("Importe conocido", bar)
            self.assertIn("Hay cargos por confirmar", bar)
            self.assertIn('href="#lista-de-compras"', bar)


if __name__ == "__main__":
    unittest.main()
