import sys
import unittest
from decimal import Decimal as D, ROUND_CEILING
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
from purchase_data import Publication, load_publications
from purchase_engine import Offer, Supplier
from recipe_plan import (
    RECIPES,
    RecipeItem,
    eligible_offers,
    plan_for_budget,
    typical_batches,
    typical_offers,
)


SELLER = Supplier("Vendedor", None, None, "vendedor-1")
RECIPE = (RecipeItem("harina", D(500)), RecipeItem("levadura", D(10)))
MARKET_CSV = ROOT / "data_public" / "actual" / "mercadolibre_validado.csv"


def publication(insumo, listing, kg, price, *, outlier=False, review=""):
    offer = Offer(
        product=f"{insumo} {listing}",
        supplier=SELLER,
        pack=None if kg is None else D(kg),
        unit="kg",
        price=D(price),
        basis="publicado",
        listing=listing,
        outlier_price=outlier,
    )
    return Publication(offer, 1, insumo, review)


PUBLICATIONS = [
    publication("harina", "h-500", "0.5", "4400"),
    publication("harina", "h-1500", "1.5", "10400"),
    publication("harina", "h-atipica", "0.5", "1000", outlier=True),
    publication("harina", "h-bulto", "25", "90000"),
    publication("harina", "h-sin-peso", None, "3000"),
    publication("harina", "h-revision", "0.5", "900", review="Formato de pack inconsistente"),
    publication("levadura", "l-125", "0.125", "6100"),
    publication("levadura", "l-500", "0.5", "8100"),
    publication("levadura", "l-20", "0.02", "3800", outlier=True),
    publication("otro", "x-1", "1", "1"),
]


def brute_force_batches(budget, max_batches=20):
    """Referencia independiente: prueba cada cantidad de lotes con las ofertas comparables."""
    best = 0
    for batches in range(1, max_batches + 1):
        total = D(0)
        for item in RECIPE:
            need = item.grams * batches / 1000
            costs = [
                ((need / offer.pack).to_integral_value(ROUND_CEILING)) * offer.price
                for offer in eligible_offers(PUBLICATIONS, item.insumo)
            ]
            total += min(costs)
        if total <= budget:
            best = batches
    return best


class RecipePlanTest(unittest.TestCase):
    def test_only_comparable_offers_are_used(self):
        harina = {offer.listing for offer in eligible_offers(PUBLICATIONS, "harina")}
        levadura = {offer.listing for offer in eligible_offers(PUBLICATIONS, "levadura")}
        self.assertEqual(harina, {"h-500", "h-1500"})
        self.assertEqual(levadura, {"l-125", "l-500"})

    def test_budget_below_one_batch_reports_the_minimum_purchase(self):
        plan = plan_for_budget(PUBLICATIONS, RECIPE, D("10000"))
        self.assertEqual(plan.batches, 0)
        self.assertEqual(plan.spend, D("10500"))
        self.assertIsNone(plan.cost_per_batch)

    def test_chooses_the_largest_affordable_number_of_batches(self):
        for budget, batches, spend in (
            ("10500", 1, "10500"),
            ("14899", 1, "10500"),
            ("14900", 2, "14900"),
            ("16499", 2, "14900"),
            ("16500", 3, "16500"),
        ):
            with self.subTest(budget=budget):
                plan = plan_for_budget(PUBLICATIONS, RECIPE, D(budget))
                self.assertEqual(plan.batches, batches)
                self.assertEqual(plan.spend, D(spend))
                self.assertEqual(plan.remaining, D(budget) - D(spend))

    def test_buys_whole_presentations_and_reports_the_surplus(self):
        plan = plan_for_budget(PUBLICATIONS, RECIPE, D("16500"))
        flour, yeast = plan.quotes
        self.assertEqual((flour.offer.listing, flour.boxes, flour.surplus), ("h-1500", 1, D(0)))
        self.assertEqual((yeast.offer.listing, yeast.boxes, yeast.surplus), ("l-125", 1, D("0.095")))
        self.assertEqual(plan.cost_per_batch, D("5500"))

    def test_matches_an_independent_brute_force_search(self):
        for budget in range(0, 300001, 500):
            with self.subTest(budget=budget):
                plan = plan_for_budget(PUBLICATIONS, RECIPE, D(budget))
                self.assertEqual(plan.batches, brute_force_batches(D(budget)))

    def test_never_exceeds_the_budget_and_always_covers_the_recipe(self):
        previous = 0
        for budget in range(0, 200001, 1000):
            plan = plan_for_budget(PUBLICATIONS, RECIPE, D(budget))
            self.assertGreaterEqual(plan.batches, previous)
            previous = plan.batches
            for quote, item in zip(plan.quotes, RECIPE):
                self.assertGreaterEqual(quote.surplus, 0)
                self.assertEqual(quote.required, item.grams * max(plan.batches, 1) / 1000)
            if plan.batches:
                self.assertLessEqual(plan.spend, budget)

    def test_caps_the_number_of_batches(self):
        plan = plan_for_budget(PUBLICATIONS, RECIPE, D("1000000"), max_batches=5)
        self.assertEqual(plan.batches, 5)

    def test_missing_ingredient_has_no_plan(self):
        without_yeast = [item for item in PUBLICATIONS if item.insumo != "levadura"]
        self.assertIsNone(plan_for_budget(without_yeast, RECIPE, D("50000")))
        self.assertIsNone(typical_batches(without_yeast, RECIPE, D("50000")))

    def test_rejects_invalid_arguments(self):
        with self.assertRaises(ValueError):
            plan_for_budget(PUBLICATIONS, RECIPE, D("-1"))
        with self.assertRaises(ValueError):
            plan_for_budget(PUBLICATIONS, RECIPE, D("NaN"))
        with self.assertRaises(ValueError):
            plan_for_budget(PUBLICATIONS, RECIPE, D("1000"), max_batches=0)

    def test_rejects_empty_duplicate_or_invalid_recipe_items(self):
        recipes = (
            (),
            (RECIPE[0], RECIPE[0]),
            (RecipeItem("harina", D(0)),),
            (RecipeItem("harina", D(-1)),),
            (RecipeItem("harina", D("NaN")),),
            (RecipeItem("harina", D("Infinity")),),
            (RecipeItem("", D(500)),),
        )
        for recipe in recipes:
            for calculate in (plan_for_budget, typical_batches):
                with self.subTest(recipe=recipe, calculate=calculate.__name__):
                    with self.assertRaises(ValueError):
                        calculate(PUBLICATIONS, recipe, D(40000))
        for maximum in (True, 2.5, -1):
            with self.subTest(maximum=maximum):
                with self.assertRaises(ValueError):
                    plan_for_budget(PUBLICATIONS, RECIPE, D(40000), max_batches=maximum)

    def test_non_finite_weights_and_invalid_prices_are_not_used(self):
        invalid = [
            publication("harina", "h-nan", "NaN", "1"),
            publication("harina", "h-infinity", "Infinity", "1"),
            publication("harina", "h-price-nan", "0.5", "NaN"),
            publication("harina", "h-price-zero", "0.5", "0"),
            publication("harina", "h-price-negative", "0.5", "-1"),
        ]
        self.assertEqual(eligible_offers(invalid, "harina"), [])

    def test_a_large_limit_does_not_require_checking_every_batch(self):
        import recipe_plan

        with patch.object(recipe_plan, "_cheapest_purchase", wraps=recipe_plan._cheapest_purchase) as quotes:
            plan = plan_for_budget(PUBLICATIONS, RECIPE, D(16500), max_batches=1000000)
        self.assertEqual(plan.batches, 3)
        self.assertLessEqual(quotes.call_count, 22)

    def test_comparing_never_gives_fewer_batches_than_buying_the_typical_offer(self):
        typical = typical_offers(PUBLICATIONS, RECIPE)
        # Con dos ofertas se toma la mediana inferior: la de menor precio por kg.
        self.assertEqual(typical["harina"].listing, "h-1500")
        for budget in range(0, 200001, 1000):
            plan = plan_for_budget(PUBLICATIONS, RECIPE, D(budget))
            self.assertLessEqual(typical_batches(PUBLICATIONS, RECIPE, D(budget)), plan.batches)

    def test_recipes_are_well_defined(self):
        self.assertEqual(list(RECIPES), ["Pan", "Pizza", "Budín"])
        for name, recipe in RECIPES.items():
            with self.subTest(recipe=name):
                insumos = [item.insumo for item in recipe]
                self.assertTrue(recipe)
                self.assertEqual(len(insumos), len(set(insumos)))
                self.assertTrue(all(item.grams > 0 for item in recipe))

    @unittest.skipUnless(MARKET_CSV.is_file(), "No está el CSV publicado.")
    def test_the_documented_examples_match_the_real_capture(self):
        groups = load_publications(MARKET_CSV, None)
        publications = [item for group in groups.values() for _, item in group]
        for name, budget, batches, spend in (
            ("Pan", 40000, 9, 37285),
            ("Pan", 8000, 0, 10495),
            ("Pizza", 20000, 9, 18815),
            ("Budín", 20000, 6, 19649),
        ):
            with self.subTest(recipe=name, budget=budget):
                plan = plan_for_budget(publications, RECIPES[name], D(budget))
                self.assertEqual((plan.batches, plan.spend), (batches, D(spend)))
        self.assertEqual(typical_batches(publications, RECIPES["Pan"], D(40000)), 4)

    @unittest.skipUnless(MARKET_CSV.is_file(), "No está el CSV publicado.")
    def test_every_recipe_has_a_plan_with_the_published_dataset(self):
        groups = load_publications(MARKET_CSV, None)
        publications = [item for group in groups.values() for _, item in group]
        insumo_by_listing = {item.offer.listing: item.insumo for item in publications}
        for name, recipe in RECIPES.items():
            with self.subTest(recipe=name):
                for item in recipe:
                    self.assertTrue(eligible_offers(publications, item.insumo), item.insumo)
                plan = plan_for_budget(publications, recipe, D("60000"))
                self.assertGreaterEqual(plan.batches, 1)
                self.assertLessEqual(plan.spend, D("60000"))
                self.assertEqual(
                    [insumo_by_listing[quote.offer.listing] for quote in plan.quotes],
                    [item.insumo for item in recipe],
                )
                self.assertTrue(all(not quote.offer.outlier_price for quote in plan.quotes))
                self.assertGreaterEqual(plan.batches, typical_batches(publications, recipe, D("60000")))


@unittest.skipUnless(MARKET_CSV.is_file(), "No está el CSV publicado.")
class RecipeScreenTest(unittest.TestCase):
    def start_app(self):
        return AppTest.from_string(
            "from pathlib import Path\n"
            "from purchase_data import load_publications\n"
            "from purchase_view import show_recipe_plan\n"
            "from budget_view import show_budget\n"
            f"products = load_publications(Path({str(MARKET_CSV)!r}), None)\n"
            "show_recipe_plan(products)\n"
            "show_budget()\n",
            default_timeout=20,
        ).run()

    def test_plan_goes_to_the_cart_and_does_not_duplicate_on_repeated_clicks(self):
        from budget import BudgetLine, budget_orders
        from budget_pdf import create_pdf

        app = self.start_app()
        self.assertFalse(app.exception or app.error)
        self.assertFalse(any(button.key == "agregar_plan_receta" for button in app.button))
        app.number_input(key="presupuesto_receta").set_value(40000.0).run()
        self.assertFalse(app.exception or app.error)
        self.assertEqual(app.metric[0].value, "9")
        app.button(key="agregar_plan_receta").click().run()
        cart = app.session_state["lista_compras"]
        self.assertEqual(len(cart), 2)
        self.assertEqual(sum(quote.merchandise for quote in cart.values()), D(37285))
        self.assertEqual(app.metric[-1].value, "ARS 37.285,00")
        app.button(key="agregar_plan_receta").click().run()
        self.assertEqual(len(app.session_state["lista_compras"]), 2)
        orders = budget_orders([BudgetLine(quote, "pendiente", None) for quote in cart.values()], {})
        self.assertEqual(sum(order.known for order in orders), D(37285))
        from datetime import datetime, timezone

        pdf = create_pdf(orders, datetime(2026, 11, 23, tzinfo=timezone.utc))
        self.assertTrue(pdf.startswith(b"%PDF-"))
        self.assertFalse(app.exception or app.error)

    def test_insufficient_budget_cannot_add_a_purchase(self):
        app = self.start_app()
        app.number_input(key="presupuesto_receta").set_value(8000.0).run()
        self.assertFalse(app.exception or app.error)
        self.assertTrue(any("ARS 10.495,00" in item.value for item in app.info))
        self.assertFalse(any(button.key == "agregar_plan_receta" for button in app.button))
        self.assertEqual(app.session_state["lista_compras"], {})

    def test_recipe_amounts_and_planning_limit_can_be_changed(self):
        app = self.start_app()
        app.number_input(key="presupuesto_receta").set_value(40000.0).run()
        app.number_input(key="receta_0_premezcla_pan").set_value(1000.0).run()
        app.number_input(key="receta_tope_lotes").set_value(2).run()
        self.assertFalse(app.exception or app.error)
        self.assertEqual(app.metric[0].value, "2")
        app.button(key="agregar_plan_receta").click().run()
        requirements = sorted(quote.required for quote in app.session_state["lista_compras"].values())
        self.assertEqual(requirements, [D("0.02"), D(2)])


if __name__ == "__main__":
    unittest.main()
