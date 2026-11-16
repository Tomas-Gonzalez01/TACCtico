import sys
import unittest
from dataclasses import replace
from decimal import Decimal as D
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from budget import BudgetLine, budget_orders, parse_quantity, quantity_label
from purchase_data import resolve_presentation
from purchase_engine import Discount, Offer, Supplier, best_purchase, candidate_quotes, order_total, supplier_options


PICKUP = Supplier("Retiro", D(0), D(0))
SMALL = Offer("Harina", PICKUP, D("1"), "kg", D("1200"), "final")
BULK = Offer(
    "Harina", Supplier("Mayorista", D(0), D(0)), D("20"), "kg", D("18000"), "final",
    discounts=(Discount(5, D("0.10")),),
)


class PurchaseTest(unittest.TestCase):
    def test_argentine_quantity_format(self):
        for text, expected in (("1", "1"), ("1000", "1000"), ("1.000", "1000"), ("1,250", "1.25")):
            self.assertEqual(parse_quantity(text), D(expected))
        self.assertEqual(quantity_label(D("1.000"), "kg"), "1 kg")
        self.assertEqual(quantity_label(D("1000.25"), "kg"), "1.000,25 kg")
        with self.assertRaisesRegex(ValueError, "entero"):
            parse_quantity("1,5", whole_units=True)
        with self.assertRaises(ValueError):
            parse_quantity("1.5")

    def test_quantity_changes_recommendation(self):
        for needed, supplier, total in ((1, "Retiro", 1200), (100, "Mayorista", 81000)):
            quotes = [quote for offer in (SMALL, BULK) for quote in candidate_quotes(offer, D(needed), "kg")]
            best = best_purchase(quotes)
            self.assertEqual((best.offer.supplier.name, best.total), (supplier, D(total)))

    def test_rounding_with_grams_and_units(self):
        offer = replace(SMALL, pack=D("500"), unit="g")
        exact = best_purchase(candidate_quotes(offer, D("1"), "kg"))
        rounded = best_purchase(candidate_quotes(offer, D("1.001"), "kg"))
        self.assertEqual((exact.boxes, exact.surplus), (2, D(0)))
        self.assertEqual((rounded.boxes, rounded.received, rounded.surplus), (3, D("1.5"), D("0.499")))
        units = replace(SMALL, pack=D(6), unit="unidad", price=D(2000))
        self.assertEqual(best_purchase(candidate_quotes(units, D(7), "unidad")).received, D(12))

    def test_minimum_boxes_and_order_minimum(self):
        offer = replace(SMALL, minimum_boxes=2, supplier=Supplier("Mínimo", D(10), D(3000)))
        quote = best_purchase(candidate_quotes(offer, D(1), "kg"))
        self.assertEqual((quote.boxes, quote.surplus, quote.total), (3, D(2), D(3610)))
        minimum_boxes = best_purchase(candidate_quotes(replace(offer, supplier=PICKUP), D(1), "kg"))
        self.assertEqual(minimum_boxes.boxes, 2)

    def test_tax_bases(self):
        net = replace(SMALL, price=D(100), basis="neto", vat_rate=D("0.21"))
        gross = replace(net, basis="final", price=D(121))
        for offer in (net, gross):
            quote = best_purchase(candidate_quotes(offer, D(1), "kg"))
            self.assertEqual((quote.vat, quote.total), (D(21), D(121)))
        unknown = next(candidate_quotes(replace(net, vat_rate=None), D(1), "kg"))
        self.assertIsNone(unknown.total)
        self.assertEqual(order_total([unknown]).known, D(100))

    def test_shipping_is_charged_once(self):
        supplier = Supplier("Mismo proveedor", D(200), D(2000))
        a = next(candidate_quotes(replace(SMALL, supplier=supplier), D(1), "kg", single_order=False))
        b = next(candidate_quotes(
            replace(SMALL, supplier=supplier, product="Otro producto"), D(1), "kg", single_order=False,
        ))
        self.assertIsNone(a.total)
        self.assertEqual(order_total([a, b]).total, D(2600))

    def test_volume_threshold_and_limits(self):
        minimum, suggested = supplier_options(candidate_quotes(BULK, D(80), "kg"), bounded=False)
        self.assertEqual((minimum.received, minimum.total, minimum.unit_cost), (D(80), D(72000), D(900)))
        self.assertEqual((suggested.received, suggested.total, suggested.unit_cost), (D(100), D(81000), D(810)))
        for caps in ({"budget": D(80000)}, {"max_quantity": D(99)}):
            _, best = supplier_options(candidate_quotes(BULK, D(80), "kg", **caps), bounded=True)
            self.assertEqual(best.boxes, 4)
        self.assertEqual(best_purchase(candidate_quotes(BULK, D(100), "kg", budget=D(81000))).total, D(81000))

    def test_cheaper_total_at_next_discount(self):
        offer = replace(SMALL, discounts=(Discount(2, D("0.6")),))
        best = best_purchase(candidate_quotes(offer, D(1), "kg"))
        self.assertEqual((best.boxes, best.total), (2, D(960)))

    def test_shipping_can_change_bounded_unit_cost(self):
        offer = replace(SMALL, supplier=Supplier("Envío fijo", D(1000), D(0)))
        _, best = supplier_options(
            candidate_quotes(offer, D(1), "kg", budget=D(5000), max_quantity=D(4)), bounded=True,
        )
        self.assertEqual((best.boxes, best.total), (3, D(4600)))

    def test_incomplete_and_incompatible_offers(self):
        unconfirmed = replace(SMALL, supplier=Supplier("Pendiente", None, D(0)), price=D(100))
        quotes = [*candidate_quotes(unconfirmed, D(1), "kg"), *candidate_quotes(SMALL, D(1), "kg")]
        self.assertEqual(best_purchase(quotes).total, D(1200))
        self.assertEqual(order_total([quotes[0]]).pending, ("envío sin confirmar",))
        with self.assertRaisesRegex(ValueError, "contenido del bulto"):
            list(candidate_quotes(replace(SMALL, pack=None), D(1), "kg"))
        with self.assertRaisesRegex(ValueError, "unidad incompatible"):
            list(candidate_quotes(SMALL, D(1), "unidad"))

    def test_pack_weight_uses_confirmed_unit_and_total_without_double_counting(self):
        specs = {"Formato de venta": "Pack", "Unidades por pack": "2", "Peso neto": "900 g"}
        self.assertEqual(resolve_presentation("Premezcla 450 g x2", specs), (2, D("0.9")))
        self.assertEqual(resolve_presentation("Premezcla pack x 2", specs), (2, None))
        self.assertEqual(resolve_presentation("Premezcla 450 g x3", specs), (None, None))
        self.assertEqual(
            resolve_presentation("Premezcla pack x 2 de 450 g", {"Formato de venta": "Unidad", "Peso neto": "450 g"}),
            (None, None),
        )

    def test_published_price_is_an_estimate_with_its_own_budget(self):
        offer = replace(BULK, basis="publicado", supplier=Supplier("Mercado Libre", None, None), discounts=())
        options = list(candidate_quotes(offer, D(25), "kg", budget=D(36000), published=True))
        best = best_purchase(options, published=True)
        self.assertEqual((best.received, best.merchandise, best.total), (D(40), D(36000), None))
        self.assertIsNone(best_purchase(options))
        self.assertFalse(list(candidate_quotes(offer, D(25), "kg", budget=D(35999), published=True)))

    def test_budget_adds_only_exclusive_vat_and_one_shipping_fee(self):
        quote = next(candidate_quotes(replace(SMALL, price=D("100")), D(1), "kg"))
        net = BudgetLine(quote, "neto", D("0.21"))
        included = BudgetLine(quote, "incluido", D("0.21"))
        order, = budget_orders([net, included], {"": D(150)})
        self.assertEqual((net.vat, included.vat), (D("21.00"), D("17.36")))
        self.assertEqual((order.merchandise, order.added_vat, order.known), (D(200), D(21), D(371)))
        self.assertTrue(order.complete)

    def test_budget_with_unconfirmed_tax_or_shipping_shows_known_amount(self):
        quote = next(candidate_quotes(SMALL, D(1), "kg"))
        line = BudgetLine(quote, "pendiente", None)
        order, = budget_orders([line], {})
        self.assertEqual(order.known, D(1200))
        self.assertFalse(order.complete)
        self.assertEqual(line.tax_label, "IVA sin confirmar")


if __name__ == "__main__":
    unittest.main()
