import sys
from pathlib import Path
from unittest.mock import patch
import unittest

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
import release_view
from data_release import load_local


class ReleaseViewTests(unittest.TestCase):
    def test_refresh_failure_retains_the_cart_and_lot(self):
        current = {"lote": "a" * 64, "metrics": {"captura_hasta": "2026-11-14"}}
        state = {"lote_datos": current, "lista_compras": {"pan": "oferta"}}
        with (
            patch.object(release_view.st, "session_state", state),
            patch.object(release_view.st.sidebar, "button", return_value=True),
            patch.object(release_view.st.sidebar, "caption"),
            patch.object(release_view.st.sidebar, "warning"),
            patch.object(release_view, "remote_id", return_value="prueba"),
            patch.object(release_view, "load_remote", side_effect=ValueError("integridad")),
        ):
            self.assertEqual(release_view.choose_release(ROOT), current)
        self.assertEqual(state["lista_compras"], {"pan": "oferta"})

    def test_new_release_clears_old_quotes_but_same_release_keeps_them(self):
        current = {"lote": "a" * 64, "metrics": {"captura_hasta": "2026-11-14"}}
        state = {"lote_datos": current, "lista_compras": {"pan": "oferta"}, "seccion": "Catálogo"}
        new = {**current, "lote": "b" * 64}
        with (
            patch.object(release_view.st, "session_state", state),
            patch.object(release_view.st.sidebar, "button", return_value=True),
            patch.object(release_view.st.sidebar, "caption"),
            patch.object(release_view.st.sidebar, "info"),
            patch.object(release_view.st.sidebar, "success"),
            patch.object(release_view, "remote_id", return_value=""),
            patch.object(release_view, "load_local", side_effect=[current, new]),
        ):
            release_view.choose_release(ROOT)
            self.assertIn("lista_compras", state)
            self.assertEqual(release_view.choose_release(ROOT), new)
        self.assertNotIn("lista_compras", state)
        self.assertEqual(state["seccion"], "Catálogo")

    def test_catalog_and_dashboard_share_the_verified_real_batch(self):
        release = load_local(ROOT)
        self.assertIsNotNone(release)
        app = AppTest.from_file(str(ROOT / "app/streamlit_app.py"), default_timeout=20).run()
        self.assertFalse(app.error or app.exception)
        self.assertEqual(int(app.metric[0].value), release["metrics"]["catalogo"])
        app.radio(key="seccion").set_value("Dashboard").run()
        self.assertFalse(app.error or app.exception)
        self.assertEqual(app.session_state["lote_datos"]["lote"], release["lote"])
        self.assertIn("Análisis de abastecimiento", [x.value for x in app.header])


if __name__ == "__main__":
    unittest.main()
