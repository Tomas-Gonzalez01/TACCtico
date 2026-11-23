"""Plan de compra por presupuesto para una receta.

Dado un presupuesto, calcula cuántos lotes de una receta se pueden cubrir comprando presentaciones
enteras. Para cada cantidad de lotes elige, por insumo, la oferta que cubre los gramos necesarios al
menor importe publicado, y devuelve la mayor cantidad de lotes que entra en el presupuesto.

El módulo no depende de Streamlit: usa los tipos del motor de compras y `Decimal`.
"""

from dataclasses import dataclass
from decimal import Decimal

from purchase_engine import ZERO, Offer, Quote, best_purchase, candidate_quotes


# Compra accesible: mismo tope de 5 kg por presentación que usa el análisis de precios.
MAX_PACK_KG = Decimal(5)
# Límite de planificación editable; el dataset no contiene fechas de vencimiento.
DEFAULT_MAX_BATCHES = 20


@dataclass(frozen=True)
class RecipeItem:
    insumo: str
    grams: Decimal  # Gramos del insumo por lote.


# Ejemplos editables de los insumos que cubre el catálogo, no recetas completas validadas.
# Verificar la etiqueta de cada premezcla y sumar por separado los ingredientes no incluidos aquí.
RECIPES = {
    "Pan": (
        RecipeItem("premezcla_pan", Decimal(500)),
        RecipeItem("levadura", Decimal(10)),
    ),
    "Pizza": (RecipeItem("premezcla_pizza", Decimal(250)),),
    "Budín": (
        RecipeItem("premezcla_budin", Decimal(250)),
        RecipeItem("chips_chocolate", Decimal(50)),
    ),
}


@dataclass(frozen=True)
class BatchPlan:
    batches: int  # Lotes que entran en el presupuesto; 0 si no alcanza ni para uno.
    quotes: tuple[Quote, ...]  # Compra recomendada, o la mínima de un lote si `batches` es 0.
    budget: Decimal

    @property
    def spend(self):
        return sum((quote.merchandise for quote in self.quotes), ZERO)

    @property
    def remaining(self):
        return self.budget - self.spend

    @property
    def cost_per_batch(self):
        return self.spend / self.batches if self.batches else None


def eligible_offers(publications, insumo, max_pack_kg=MAX_PACK_KG):
    """Ofertas comparables: presentación confirmada, sin alerta de precio y dentro del tope."""
    return [
        item.offer
        for item in publications
        if item.insumo == insumo
        and not item.review
        and not item.offer.outlier_price
        and item.offer.unit == "kg"
        and item.offer.pack is not None
        and item.offer.pack.is_finite()
        and 0 < item.offer.pack <= max_pack_kg
        and item.offer.price.is_finite()
        and item.offer.price > 0
    ]


def _quotes(offer: Offer, required_kg):
    try:
        return list(candidate_quotes(offer, required_kg, "kg", published=True))
    except ValueError:
        return []


def _required_kg(item, batches):
    return item.grams * batches / 1000


def cheapest_cover(offers, required_kg):
    """Presentaciones enteras de una sola oferta que cubren `required_kg` al menor importe."""
    return best_purchase([quote for offer in offers for quote in _quotes(offer, required_kg)], published=True)


def _cheapest_purchase(offers_by_insumo, recipe, batches):
    quotes = [cheapest_cover(offers_by_insumo[item.insumo], _required_kg(item, batches)) for item in recipe]
    return None if None in quotes else tuple(quotes)


def _total(quotes):
    return sum((quote.merchandise for quote in quotes), ZERO)


def _validate_request(recipe, budget, max_batches):
    if not budget.is_finite() or budget < 0:
        raise ValueError("El presupuesto debe ser un importe mayor o igual a cero.")
    if type(max_batches) is not int or max_batches < 1:
        raise ValueError("El tope de lotes debe ser un entero mayor o igual a 1.")
    if not recipe or any(
        not item.insumo.strip() or not item.grams.is_finite() or item.grams <= 0 for item in recipe
    ):
        raise ValueError("La receta debe incluir insumos con una cantidad de gramos mayor que cero.")
    if len({item.insumo for item in recipe}) != len(recipe):
        raise ValueError("Cada insumo debe aparecer una sola vez en la receta.")


def _affordable_plan(quotes_for_batches, budget, max_batches):
    """Busca sin recorrer cada lote: el costo mínimo no disminuye al pedir más gramos."""
    minimum = quotes_for_batches(1)
    if minimum is None:
        return None
    batches, quotes = (1, minimum) if _total(minimum) <= budget else (0, minimum)
    lower, upper = 2, max_batches
    if not batches:
        return BatchPlan(0, minimum, budget)
    while lower <= upper:
        middle = (lower + upper) // 2
        candidate = quotes_for_batches(middle)
        if candidate is None:
            return None
        if _total(candidate) <= budget:
            batches, quotes = middle, candidate
            lower = middle + 1
        else:
            upper = middle - 1
    return BatchPlan(batches, quotes, budget)


def plan_for_budget(publications, recipe, budget, *, max_batches=DEFAULT_MAX_BATCHES):
    """Mayor cantidad de lotes dentro del monto y del tope; una publicación por insumo."""
    _validate_request(recipe, budget, max_batches)
    offers = {item.insumo: eligible_offers(publications, item.insumo) for item in recipe}
    if not all(offers.values()):
        return None
    return _affordable_plan(lambda batches: _cheapest_purchase(offers, recipe, batches), budget, max_batches)


def _price_per_kg(offer):
    return offer.price / offer.pack


def typical_offers(publications, recipe):
    """Oferta central por precio/kg de cada insumo; referencia estadística, no compra observada.

    Con una cantidad par de ofertas se toma la oferta central inferior.
    """
    typical = {}
    for item in recipe:
        ordered = sorted(
            eligible_offers(publications, item.insumo),
            key=lambda offer: (_price_per_kg(offer), offer.listing),
        )
        if not ordered:
            return None
        typical[item.insumo] = ordered[(len(ordered) - 1) // 2]
    return typical


def typical_batches(publications, recipe, budget, *, max_batches=DEFAULT_MAX_BATCHES):
    """Lotes que alcanzan con `budget` comprando la oferta mediana de cada insumo; None sin ofertas."""
    _validate_request(recipe, budget, max_batches)
    typical = typical_offers(publications, recipe)
    if typical is None:
        return None

    def quotes_for_batches(batches):
        quotes = [
            best_purchase(_quotes(typical[item.insumo], _required_kg(item, batches)), published=True)
            for item in recipe
        ]
        return None if None in quotes else tuple(quotes)

    plan = _affordable_plan(quotes_for_batches, budget, max_batches)
    return None if plan is None else plan.batches
