from dataclasses import dataclass, replace
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR


ZERO = Decimal(0)


@dataclass(frozen=True)
class Supplier:
    name: str
    shipping: Decimal | None
    minimum_order: Decimal | None  # Total de mercadería con IVA, antes de envío.
    identifier: str = ""


@dataclass(frozen=True)
class Discount:
    boxes: int
    rate: Decimal


@dataclass(frozen=True)
class Offer:
    product: str
    supplier: Supplier
    pack: Decimal | None
    unit: str
    price: Decimal
    basis: str
    vat_rate: Decimal | None = None
    minimum_boxes: int = 1
    discounts: tuple[Discount, ...] = ()
    listing: str = ""
    url: str = ""
    shipping_note: str = ""
    promotion: str = ""
    category: str = ""
    captured: str = ""
    units_per_pack: int | None = None
    outlier_price: bool = False


@dataclass(frozen=True)
class Quote:
    offer: Offer
    required: Decimal
    boxes: int
    discount_rate: Decimal

    @property
    def received(self):
        return self.offer.pack * self.boxes

    @property
    def surplus(self):
        return self.received - self.required

    @property
    def subtotal(self):
        return self.offer.price * self.boxes

    @property
    def discount(self):
        return self.subtotal * self.discount_rate

    @property
    def merchandise(self):
        return self.subtotal - self.discount

    @property
    def vat(self):
        rate = self.offer.vat_rate
        if rate is None:
            return None
        if self.offer.basis == "neto":
            return self.merchandise * rate
        if self.offer.basis == "final":
            return self.merchandise - self.merchandise / (1 + rate)
        return None

    @property
    def merchandise_with_vat(self):
        if self.offer.basis == "final":
            return self.merchandise
        if self.offer.basis == "neto" and self.vat is not None:
            return self.merchandise + self.vat
        return None

    @property
    def total(self):
        return order_total([self]).total

    @property
    def unit_cost(self):
        total = self.total
        return total / self.received if total is not None else None


@dataclass(frozen=True)
class OrderTotal:
    known: Decimal
    total: Decimal | None
    pending: tuple[str, ...]


def order_total(quotes):
    supplier = quotes[0].offer.supplier
    if any(quote.offer.supplier != supplier for quote in quotes):
        raise ValueError("El pedido debe incluir ofertas de un solo proveedor.")
    merchandise = [quote.merchandise_with_vat for quote in quotes]
    known = sum(
        (gross if gross is not None else quote.merchandise for gross, quote in zip(merchandise, quotes)),
        ZERO,
    )
    pending = []
    if any(gross is None for gross in merchandise):
        pending.append("IVA o base del precio")
    if supplier.minimum_order is None:
        pending.append("mínimo del pedido desconocido")
    elif supplier.minimum_order > 0:
        if any(gross is None for gross in merchandise):
            pending.append("mínimo del pedido por verificar")
        elif known < supplier.minimum_order:
            pending.append("mínimo del pedido sin alcanzar")
    if supplier.shipping is None:
        pending.append("envío sin confirmar")
    else:
        known += supplier.shipping
    return OrderTotal(known, None if pending else known, tuple(pending))


def quantity_in_unit(quantity, requested_unit, offer_unit):
    if not quantity.is_finite() or quantity <= 0:
        raise ValueError("La cantidad debe ser mayor que cero.")
    if requested_unit == offer_unit:
        return quantity
    if requested_unit == "g" and offer_unit == "kg":
        return quantity / 1000
    if requested_unit == "kg" and offer_unit == "g":
        return quantity * 1000
    raise ValueError("La oferta usa una unidad incompatible.")


def candidate_quotes(
    offer,
    quantity,
    unit,
    *,
    budget=None,
    max_quantity=None,
    single_order=True,
    published=False,
):
    """Evalúa los extremos pertinentes de cada tramo de precio por bulto."""
    if offer.pack is None or not offer.pack.is_finite() or offer.pack <= 0:
        raise ValueError("Falta confirmar el contenido del bulto.")
    if not offer.price.is_finite() or offer.price <= 0 or offer.minimum_boxes < 1:
        raise ValueError("Precio o mínimo por oferta inválido.")
    if any(
        tier.boxes < 1 or not tier.rate.is_finite() or not ZERO <= tier.rate < 1 for tier in offer.discounts
    ):
        raise ValueError("Descuento por volumen inválido.")
    terms = (offer.vat_rate, offer.supplier.shipping, offer.supplier.minimum_order)
    if any(value is not None and (not value.is_finite() or value < 0) for value in terms):
        raise ValueError("IVA, envío o mínimo del pedido inválido.")
    quantity_in_unit(quantity, unit, unit)
    if unit == "unidad" and quantity != quantity.to_integral_value():
        raise ValueError("La cantidad en unidades debe ser entera.")
    if offer.unit != unit:
        offer = replace(offer, pack=quantity_in_unit(offer.pack, offer.unit, unit), unit=unit)
    required = quantity
    floor = max(offer.minimum_boxes, int((required / offer.pack).to_integral_value(ROUND_CEILING)))
    thresholds = {floor, *(tier.boxes for tier in offer.discounts if tier.boxes > floor)}
    starts = sorted(thresholds)
    limit = None
    if max_quantity is not None:
        allowed = quantity_in_unit(max_quantity, unit, unit)
        limit = int((allowed / offer.pack).to_integral_value(ROUND_FLOOR))
    for index, start in enumerate(starts):
        end = starts[index + 1] - 1 if index + 1 < len(starts) else None
        if limit is not None:
            end = min(end, limit) if end is not None else limit
        rate = max((tier.rate for tier in offer.discounts if tier.boxes <= start), default=ZERO)
        unit_gross = Quote(offer, required, 1, rate).merchandise_with_vat
        supplier = offer.supplier
        first = start
        if single_order and supplier.minimum_order and unit_gross is not None:
            minimum_boxes = (supplier.minimum_order / unit_gross).to_integral_value(ROUND_CEILING)
            first = max(first, int(minimum_boxes))
        if budget is not None:
            per_box = offer.price * (1 - rate) if published else unit_gross
            shipping = ZERO if published else supplier.shipping
            if per_box is None or shipping is None:
                continue
            affordable = int(((budget - shipping) / per_box).to_integral_value(ROUND_FLOOR))
            end = min(end, affordable) if end is not None else affordable
        if end is not None and first > end:
            continue
        yield Quote(offer, required, first, rate)
        if end is not None and end > first and supplier.shipping and not published:
            yield Quote(offer, required, end, rate)


def cost_for_comparison(quote, published):
    return quote.merchandise if published else quote.total


def best_purchase(quotes, *, published=False):
    return min(
        (quote for quote in quotes if cost_for_comparison(quote, published) is not None),
        key=lambda quote: (cost_for_comparison(quote, published), quote.surplus),
        default=None,
    )


def supplier_options(quotes, *, bounded, published=False):
    confirmed = sorted(
        (quote for quote in quotes if cost_for_comparison(quote, published) is not None),
        key=lambda quote: (quote.received, cost_for_comparison(quote, published)),
    )
    if not confirmed:
        return None, None
    minimum = confirmed[0]

    def unit_cost(quote):
        return cost_for_comparison(quote, published) / quote.received

    if bounded:
        best = min(
            confirmed,
            key=lambda quote: (unit_cost(quote), cost_for_comparison(quote, published), quote.surplus),
        )
    else:
        better = (quote for quote in confirmed[1:] if unit_cost(quote) < unit_cost(minimum))
        best = next(better, minimum)
    return minimum, best
