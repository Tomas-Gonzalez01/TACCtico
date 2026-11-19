import re
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from purchase_engine import Quote


ARGENTINE_SEPARATORS = str.maketrans(",.", ".,")
QUANTITY_FORMAT = re.compile(r"(?:[0-9]+|[0-9]{1,3}(?:\.[0-9]{3})+)(?:,[0-9]+)?")


def ars(amount):
    if amount is None:
        return "Sin confirmar"
    return f"ARS {money(amount):,.2f}".translate(ARGENTINE_SEPARATORS)


def money(amount):
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def parse_quantity(text, *, whole_units=False):
    text = text.strip()
    if not QUANTITY_FORMAT.fullmatch(text):
        raise ValueError("Ingresá una cantidad como 1, 1.000 o 1,5.")
    amount = Decimal(text.replace(".", "").replace(",", "."))
    if amount <= 0:
        raise ValueError("La cantidad debe ser mayor que cero.")
    if whole_units and amount != amount.to_integral_value():
        raise ValueError("Ingresá un número entero de unidades.")
    return amount


def quantity_number(amount):
    number = format(amount, ",f")
    if "." in number:
        number = number.rstrip("0").rstrip(".")
    return number.translate(ARGENTINE_SEPARATORS)


def quantity_label(amount, unit):
    label = "kg" if unit == "kg" else ("unidad" if amount == 1 else "unidades")
    return f"{quantity_number(amount)} {label}"


@dataclass(frozen=True)
class BudgetLine:
    quote: Quote
    tax_basis: str
    tax_rate: Decimal | None

    @property
    def merchandise(self):
        return money(self.quote.merchandise)

    @property
    def vat(self):
        if self.tax_rate is None:
            return None
        if self.tax_basis == "neto":
            return money(self.merchandise * self.tax_rate)
        if self.tax_basis == "incluido":
            return money(self.merchandise - self.merchandise / (1 + self.tax_rate))
        return None

    @property
    def added_vat(self):
        return self.vat if self.tax_basis == "neto" else None

    @property
    def tax_pending(self):
        return self.tax_basis == "pendiente" or (self.tax_basis == "neto" and self.tax_rate is None)

    @property
    def tax_label(self):
        if self.tax_pending:
            return "IVA sin confirmar"
        if self.tax_basis == "incluido":
            return "IVA incluido" if self.vat is None else f"IVA incluido · {ars(self.vat)}"
        return f"IVA a sumar · {ars(self.vat)}"

    @property
    def known(self):
        return self.merchandise + (self.added_vat or Decimal(0))


@dataclass(frozen=True)
class BudgetOrder:
    supplier: str
    lines: tuple[BudgetLine, ...]
    shipping: Decimal | None

    @property
    def merchandise(self):
        return sum(line.merchandise for line in self.lines)

    @property
    def added_vat(self):
        return sum((line.added_vat or Decimal(0) for line in self.lines), Decimal(0))

    @property
    def known(self):
        return self.merchandise + self.added_vat + (self.shipping or Decimal(0))

    @property
    def complete(self):
        return self.shipping is not None and all(not line.tax_pending for line in self.lines)


def budget_orders(lines, shipping_by_seller):
    by_seller = defaultdict(list)
    for line in lines:
        seller = line.quote.offer.supplier
        by_seller[seller.identifier or seller.name].append(line)
    return [
        BudgetOrder(
            items[0].quote.offer.supplier.name,
            tuple(items),
            shipping_by_seller.get(items[0].quote.offer.supplier.identifier),
        )
        for items in by_seller.values()
    ]
