"""Markdown rendering of planned orders (shared by CLI and HA notifications)."""

from __future__ import annotations

from .models import OrderKind, PlannedOrder

KIND_LABEL = {
    OrderKind.WEEKLY_DURABLE: "TÝDENNÍ (trvanlivé)",
    OrderKind.FRESH: "ČERSTVÉ",
}


def render_markdown(orders: list[PlannedOrder]) -> str:
    lines: list[str] = []
    for order in orders:
        days = ", ".join(d.isoformat() for d in order.covers_days)
        lines.append(f"## {order.delivery_date.isoformat()} — {KIND_LABEL[order.kind]}")
        lines.append(f"Pokrývá dny vaření: {days}")
        lines.append("")
        lines.append("| Ingredience | Množství | Recepty |")
        lines.append("|---|---|---|")
        for item in order.items:
            qty = " + ".join(item.quantities) if item.quantities else "-"
            lines.append(f"| {item.name} | {qty} | {', '.join(item.recipes)} |")
        lines.append("")
    if not orders:
        lines.append("Žádné objednávky — prázdný plán.")
    return "\n".join(lines)
