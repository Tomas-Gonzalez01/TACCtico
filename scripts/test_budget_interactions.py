"""Comprueba los cambios de la lista y sus avisos con ofertas del CSV real."""

import sys
import unittest
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

import budget_view as view
from purchase_data import load_publications, market_csv
from purchase_engine import candidate_quotes


class BudgetInteractionsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        products = load_publications(market_csv(ROOT), None)
        for key, group in products.items():
            offers = [item.offer for _, item in group if item.offer.pack and not item.offer.outlier_price]
            if len({offer.listing for offer in offers}) >= 2:
                cls.product = key
                cls.first = next(candidate_quotes(offers[0], Decimal(1), "kg", published=True))
                alternative = next(offer for offer in offers if offer.listing != offers[0].listing)
                cls.second = next(candidate_quotes(alternative, Decimal(1), "kg", published=True))
                cls.updated = next(candidate_quotes(offers[0], Decimal(2), "kg", published=True))
                break
        else:
            raise AssertionError("Se necesitan dos publicaciones reales comparables para esta prueba.")

    def setUp(self):
        self.state = {}
        self.enterContext(patch.object(view.st, "session_state", self.state))
        self.toast = self.enterContext(patch.object(view.st, "toast"))

    def test_add_is_confirmed_once_after_the_cart_changes(self):
        view.add_to_cart(self.product, self.first)
        self.assertEqual(self.state[view.CART][self.product], self.first)
        view.show_notice()
        self.toast.assert_called_once_with(
            "Producto agregado a tu lista.", icon=":material/check_circle:", duration="short",
        )
        view.show_notice()
        self.toast.assert_called_once()

    def test_repeated_click_does_not_duplicate_or_replay_the_notice(self):
        view.add_to_cart(self.product, self.first)
        view.show_notice()
        view.add_to_cart(self.product, self.first)
        view.show_notice()
        self.assertEqual(len(self.state[view.CART]), 1)
        self.toast.assert_called_once()

    def test_the_picker_receives_a_new_revision_for_each_action(self):
        view.acknowledge_offer_event()
        first_revision = self.state[view.OFFER_REVISION]
        view.acknowledge_offer_event()
        self.assertGreater(self.state[view.OFFER_REVISION], first_revision)
        self.assertNotIn(view.NOTICE, self.state)

    def test_a_new_quantity_updates_the_same_product(self):
        view.add_to_cart(self.product, self.first)
        view.show_notice()
        view.add_to_cart(self.product, self.updated)
        self.assertEqual(self.state[view.CART][self.product].required, Decimal(2))
        self.assertEqual(len(self.state[view.CART]), 1)
        self.assertEqual(self.state[view.NOTICE], "Cantidad actualizada en tu lista.")

    def test_an_alternative_waits_for_confirmation_and_can_be_kept(self):
        view.add_to_cart(self.product, self.first)
        view.show_notice()
        view.add_to_cart(self.product, self.second)
        self.assertEqual(self.state[view.CART][self.product], self.first)
        self.assertEqual(self.state[view.PENDING], (self.product, self.second))
        self.assertNotIn(view.NOTICE, self.state)
        view.keep_offer()
        self.assertNotIn(view.PENDING, self.state)
        self.assertEqual(self.state[view.CART][self.product], self.first)

    def test_replacement_and_removal_confirm_the_completed_action(self):
        view.add_to_cart(self.product, self.first)
        view.show_notice()
        view.add_to_cart(self.product, self.second)
        view.replace_offer(self.product, self.second)
        self.assertEqual(self.state[view.CART][self.product], self.second)
        self.assertNotIn(view.PENDING, self.state)
        self.assertEqual(self.state[view.NOTICE], "Oferta reemplazada en tu lista.")
        view.show_notice()
        view.remove_offer(self.product)
        self.assertFalse(self.state[view.CART])
        self.assertEqual(self.state[view.NOTICE], "Producto quitado de tu lista.")


class BudgetScreenTest(unittest.TestCase):
    def test_quantity_edits_do_not_show_an_internal_widget_warning(self):
        app = AppTest.from_string(
            "from decimal import Decimal\n"
            "import streamlit as st\n"
            "from budget_view import quantity_field\n"
            "amount = quantity_field('Cantidad', 'cantidad', default=Decimal(1))\n"
            "st.write(str(amount))\n"
        ).run()
        self.assertFalse(app.exception or app.warning)
        app.text_input(key="cantidad").set_value("2").run()
        self.assertFalse(app.exception or app.warning)
        self.assertEqual(app.markdown[0].value, "2")

    def test_the_budget_section_opens_with_its_new_name(self):
        app = AppTest.from_file(str(ROOT / "app/streamlit_app.py"), default_timeout=20).run()
        # AppTest does not provide the registry used by custom components v2.
        # The real picker is exercised in the browser; keep the rest of the app here.
        with patch.object(view, "OFFER_PICKER", return_value=SimpleNamespace(add_offer=None)):
            app.radio(key="seccion").set_value("Arma tu presupuesto").run()
        self.assertFalse(app.exception or app.error)
        self.assertIn("Arma tu presupuesto", [header.value for header in app.header])


if __name__ == "__main__":
    unittest.main()
