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
        view.add_to_cart(self.first)
        self.assertEqual(list(self.state[view.CART].values()), [self.first])
        view.show_notice()
        self.toast.assert_called_once_with(
            "Producto agregado a tu lista.",
            icon=":material/check_circle:",
            duration="short",
        )
        view.show_notice()
        self.toast.assert_called_once()

    def test_repeated_click_does_not_duplicate_or_replay_the_notice(self):
        view.add_to_cart(self.first)
        view.show_notice()
        view.add_to_cart(self.first)
        view.show_notice()
        self.assertEqual(len(self.state[view.CART]), 1)
        self.toast.assert_called_once()

    def test_two_offers_of_the_same_ingredient_coexist(self):
        view.add_to_cart(self.first)
        view.add_to_cart(self.second)
        self.assertEqual(len(self.state[view.CART]), 2)
        self.assertEqual(
            {quote.offer.listing for quote in self.state[view.CART].values()},
            {self.first.offer.listing, self.second.offer.listing},
        )

    def test_the_picker_receives_a_new_revision_for_each_action(self):
        view.acknowledge_offer_event()
        first_revision = self.state[view.OFFER_REVISION]
        view.acknowledge_offer_event()
        self.assertGreater(self.state[view.OFFER_REVISION], first_revision)
        self.assertNotIn(view.NOTICE, self.state)

    def test_a_new_quantity_updates_the_same_product(self):
        view.add_to_cart(self.first)
        view.show_notice()
        view.add_to_cart(self.updated)
        self.assertEqual(next(iter(self.state[view.CART].values())).required, Decimal(2))
        self.assertEqual(len(self.state[view.CART]), 1)
        self.assertEqual(self.state[view.NOTICE], "Cantidad actualizada en tu lista.")

    def test_updating_one_publication_keeps_the_other_unchanged(self):
        view.add_to_cart(self.first)
        view.add_to_cart(self.second)
        view.add_to_cart(self.updated)
        self.assertEqual(len(self.state[view.CART]), 2)
        self.assertEqual(
            {quote.offer.listing: quote.required for quote in self.state[view.CART].values()},
            {self.first.offer.listing: Decimal(2), self.second.offer.listing: Decimal(1)},
        )

    def test_removing_one_publication_keeps_the_other(self):
        view.add_to_cart(self.first)
        view.add_to_cart(self.second)
        first_key = next(
            key
            for key, quote in self.state[view.CART].items()
            if quote.offer.listing == self.first.offer.listing
        )
        view.remove_offer(first_key)
        self.assertEqual(list(self.state[view.CART].values()), [self.second])
        self.assertEqual(self.state[view.NOTICE], "Producto quitado de tu lista.")

    def test_an_open_list_keeps_its_existing_keys_and_input_values(self):
        self.state[view.CART] = {self.product: self.first}
        widget = f"{self.product}/{self.first.offer.listing}/{self.first.offer.unit}/{self.first.required}/{self.first.boxes}"
        entered = {f"pedido_{widget}": "3", f"iva_modo_{widget}": "neto", f"iva_tasa_{widget}": 21.0}
        self.state.update(entered)
        view.add_to_cart(self.second)
        self.assertEqual(self.state[view.CART][self.product], self.first)
        self.assertEqual(len(self.state[view.CART]), 2)
        self.assertTrue(all(self.state[key] == value for key, value in entered.items()))

    def test_an_old_pending_offer_becomes_an_additional_line_once(self):
        self.state[view.CART] = {self.product: self.first}
        self.state[view.LEGACY_PENDING] = (self.product, self.second)
        view.restore_pending_offer()
        view.restore_pending_offer()
        self.assertEqual(len(self.state[view.CART]), 2)
        self.assertEqual(self.state[view.CART][self.product], self.first)
        self.assertIn(self.second, self.state[view.CART].values())
        self.assertNotIn(view.LEGACY_PENDING, self.state)

    def test_clearing_resets_only_the_budget_and_keeps_comparison_filters(self):
        view.add_to_cart(self.first)
        view.add_to_cart(self.second)
        self.state.update(
            {
                "pedido_linea": "5",
                "iva_modo_linea": "neto",
                "iva_tasa_linea": 21.0,
                "envio_proveedor": 1500.0,
                view.LEGACY_PENDING: (self.product, self.first),
                "seccion": "Arma tu presupuesto",
                "insumo": "chips_chocolate",
                view.OFFER_REVISION: 4,
            }
        )
        view.clear_cart()
        self.assertEqual(self.state[view.CART], {})
        self.assertFalse(
            any(key.startswith(("pedido_", "iva_modo_", "iva_tasa_", "envio_")) for key in self.state)
        )
        self.assertNotIn(view.LEGACY_PENDING, self.state)
        self.assertEqual(self.state["seccion"], "Arma tu presupuesto")
        self.assertEqual(self.state["insumo"], "chips_chocolate")
        self.assertEqual(self.state[view.OFFER_REVISION], 4)
        self.assertEqual(self.state[view.NOTICE], "Lista de compras vaciada.")
        view.add_to_cart(self.first)
        self.assertEqual(list(self.state[view.CART].values()), [self.first])


class BudgetScreenTest(unittest.TestCase):
    def test_clear_requires_confirmation_and_cancel_preserves_the_budget(self):
        BudgetInteractionsTest.setUpClass()
        first, second = BudgetInteractionsTest.first, BudgetInteractionsTest.second
        app = AppTest.from_file(str(ROOT / "app/streamlit_app.py"), default_timeout=20).run()
        with patch.object(view, "OFFER_PICKER", return_value=SimpleNamespace(add_offer=None)):
            app.radio(key="seccion").set_value("Arma tu presupuesto").run()
            self.assertFalse(any(button.key == "vaciar_lista" for button in app.button))
            app.session_state[view.CART] = {"primera": first, "segunda": second}
            app.run()
            quantity_key = next(field.key for field in app.text_input if field.key.startswith("pedido_"))
            app.text_input(key=quantity_key).set_value("3").run()
            total = app.metric[-1].value
            app.button(key="vaciar_lista").click().run()
            self.assertFalse(app.exception or app.error)
            self.assertEqual(len(app.session_state[view.CART]), 2)
            self.assertEqual(app.metric[-1].value, total)
            self.assertEqual(app.text_input(key=quantity_key).value, "3")
            self.assertIn("¿Querés continuar?", [text.value for text in app.markdown])
            app.button(key="cancelar_vaciado").click().run()
            self.assertFalse(app.exception or app.error)
            self.assertEqual(len(app.session_state[view.CART]), 2)
            self.assertEqual(app.metric[-1].value, total)
            self.assertEqual(app.text_input(key=quantity_key).value, "3")
            self.assertFalse(any(button.key == "confirmar_vaciado" for button in app.button))
            app.button(key="vaciar_lista").click().run()
            app.button(key="confirmar_vaciado").click().run()
            self.assertFalse(app.exception or app.error)
            self.assertEqual(app.session_state[view.CART], {})
            self.assertFalse(any(field.key.startswith("pedido_") for field in app.text_input))
            self.assertFalse(any(button.key == "vaciar_lista" for button in app.button))
            self.assertFalse(
                any(
                    metric.label in {"Importe conocido", "Total estimado del pedido"} for metric in app.metric
                )
            )
            self.assertIn(
                "Agregá una oferta desde la comparación para empezar tu presupuesto.",
                [info.value for info in app.info],
            )
            app.session_state[view.CART] = {"primera": first}
            app.run()
            self.assertFalse(app.exception or app.error)
            self.assertEqual(app.text_input(key=quantity_key).value, "1")
            self.assertEqual(app.metric[-1].value, view.ars(first.merchandise))

    def test_same_ingredient_lines_have_independent_quantities_and_totals(self):
        BudgetInteractionsTest.setUpClass()
        first, second = BudgetInteractionsTest.first, BudgetInteractionsTest.second
        app = AppTest.from_file(str(ROOT / "app/streamlit_app.py"), default_timeout=20).run()
        with patch.object(view, "OFFER_PICKER", return_value=SimpleNamespace(add_offer=None)):
            app.radio(key="seccion").set_value("Arma tu presupuesto").run()
            app.session_state[view.CART] = {"primera": first, "segunda": second}
            app.run()
            self.assertFalse(app.exception or app.error)
            quantities = [field for field in app.text_input if field.key.startswith("pedido_")]
            self.assertEqual(len(quantities), 2)
            self.assertEqual(app.metric[-1].value, view.ars(first.merchandise + second.merchandise))
            quantities[0].set_value("2").run()
            self.assertFalse(app.exception or app.error)
            edited = next(candidate_quotes(first.offer, Decimal(2), "kg", published=True))
            self.assertEqual(app.metric[-1].value, view.ars(edited.merchandise + second.merchandise))
            quantities = [field for field in app.text_input if field.key.startswith("pedido_")]
            self.assertEqual([field.value for field in quantities], ["2", "1"])

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
