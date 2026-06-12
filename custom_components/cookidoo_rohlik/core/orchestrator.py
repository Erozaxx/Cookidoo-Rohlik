"""Resolve planned orders to Rohlik products and fill the cart.

Dry-run by default: produces an `OrderResolution` report. With
execute=True it also adds matched items to the Rohlik cart. Checkout is
always manual (see RohlikClient.checkout docstring).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from .matching import MatchResult, ProductMatcher
from .models import PlannedOrder
from .rohlik_client import RohlikClient

logger = logging.getLogger(__name__)


@dataclass
class OrderResolution:
    order: PlannedOrder
    matched: list[MatchResult] = field(default_factory=list)
    unmatched: list[MatchResult] = field(default_factory=list)
    executed: bool = False

    @property
    def estimated_price(self) -> float:
        return sum(m.product.price * m.packages for m in self.matched if m.product)


async def resolve_order(
    order: PlannedOrder,
    matcher: ProductMatcher,
    client: RohlikClient,
    execute: bool = False,
) -> OrderResolution:
    """Match all items of one order; optionally add them to the cart."""
    resolution = OrderResolution(order=order)
    for item in order.items:
        result = await matcher.match(item, client)
        (resolution.matched if result.matched else resolution.unmatched).append(result)

    if execute:
        for m in resolution.matched:
            assert m.product is not None
            await client.add_to_cart(m.product.id, m.packages)
            logger.info("Added %dx %s", m.packages, m.product.name)
        resolution.executed = True

    matcher.save_cache()
    return resolution


def render_resolution(res: OrderResolution) -> str:
    """Human-readable (Markdown) report of one resolved order."""
    lines: list[str] = []
    o = res.order
    state = "PŘIDÁNO DO KOŠÍKU" if res.executed else "DRY-RUN"
    lines.append(
        f"## Objednávka {o.delivery_date.isoformat()} ({o.kind.value}) — {state}"
    )
    lines.append("")
    lines.append("| Ingredience | Produkt | Balení | Cena | Zdroj |")
    lines.append("|---|---|---|---|---|")
    for m in res.matched:
        assert m.product is not None
        src = "cache" if m.from_cache else f"search {m.score:.0%}"
        lines.append(
            f"| {m.item.name} | {m.product.name} ({m.product.textual_amount}) "
            f"| {m.packages}x | {m.product.price * m.packages:.0f} {m.product.currency} | {src} |"
        )
    lines.append("")
    lines.append(f"Odhad celkem: **{res.estimated_price:.0f} CZK**")
    if res.unmatched:
        lines.append("")
        lines.append("⚠️ Nenalezeno (vyřeš ručně nebo doplň do mapping cache):")
        for m in res.unmatched:
            lines.append(f"- {m.item.name} ({' + '.join(m.item.quantities) or '?'})")
    return "\n".join(lines)
