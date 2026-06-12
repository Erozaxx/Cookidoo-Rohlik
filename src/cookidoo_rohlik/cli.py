"""CLI: dry-run the week planner.

Usage:
  # offline, from a JSON sample (no credentials needed)
  python -m cookidoo_rohlik.cli plan --sample tests/sample_week.json

  # live against Cookidoo (reads COOKIDOO_EMAIL / COOKIDOO_PASSWORD)
  python -m cookidoo_rohlik.cli plan --week 2026-06-15

Sample JSON format:
  [{"day": "2026-06-15", "recipe": "Kuře na paprice",
    "ingredients": [{"name": "kuřecí stehna", "quantity": "600 g"}, ...]}, ...]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import date, datetime
from pathlib import Path

import yaml

from .classify import Classifier
from .models import Ingredient, OrderKind, PlannedOrder
from .planner import plan_orders


def _load_sample(path: Path) -> list[Ingredient]:
    data = json.loads(path.read_text(encoding="utf-8"))
    out: list[Ingredient] = []
    for entry in data:
        day = datetime.strptime(entry["day"], "%Y-%m-%d").date()
        for ing in entry["ingredients"]:
            out.append(
                Ingredient(
                    name=ing["name"],
                    quantity=ing.get("quantity", ""),
                    recipe_name=entry["recipe"],
                    needed_on=day,
                )
            )
    return out


def _load_config(path: Path | None) -> dict:
    if path is None or not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def render_markdown(orders: list[PlannedOrder]) -> str:
    lines: list[str] = []
    kind_label = {
        OrderKind.WEEKLY_DURABLE: "TÝDENNÍ (trvanlivé, auto-checkout)",
        OrderKind.FRESH: "ČERSTVÉ (košík + potvrzení)",
    }
    for order in orders:
        days = ", ".join(d.isoformat() for d in order.covers_days)
        lines.append(f"## {order.delivery_date.isoformat()} — {kind_label[order.kind]}")
        lines.append(f"Pokrývá dny vaření: {days}")
        lines.append("")
        lines.append("| Ingredience | Množství | Recepty |")
        lines.append("|---|---|---|")
        for item in order.items:
            qty = " + ".join(item.quantities) if item.quantities else "-"
            recipes = ", ".join(item.recipes)
            lines.append(f"| {item.name} | {qty} | {recipes} |")
        lines.append("")
    if not orders:
        lines.append("Žádné objednávky — prázdný plán.")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cookidoo-rohlik")
    sub = parser.add_subparsers(dest="command", required=True)

    p_plan = sub.add_parser("plan", help="Plan the week's orders (dry-run)")
    p_plan.add_argument("--sample", type=Path, help="Offline JSON sample instead of live Cookidoo")
    p_plan.add_argument("--week", type=str, help="Any day of the target week, YYYY-MM-DD (default: today)")
    p_plan.add_argument("--config", type=Path, default=Path("config/config.yaml"))
    p_plan.add_argument("-v", "--verbose", action="store_true")

    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(levelname)s %(name)s: %(message)s")

    cfg = _load_config(args.config)
    classifier = Classifier.from_config(cfg)
    planner_cfg = cfg.get("planner", {}) or {}
    horizon = int(planner_cfg.get("fresh_horizon_days", 2))

    if args.sample:
        ingredients = _load_sample(args.sample)
    else:
        email = os.environ.get("COOKIDOO_EMAIL")
        password = os.environ.get("COOKIDOO_PASSWORD")
        if not email or not password:
            print("ERROR: set COOKIDOO_EMAIL and COOKIDOO_PASSWORD (or use --sample).",
                  file=sys.stderr)
            return 2
        from .cookidoo_client import CookidooWeekClient  # lazy: needs cookidoo-api

        week = (datetime.strptime(args.week, "%Y-%m-%d").date()
                if args.week else date.today())
        client = CookidooWeekClient(email, password)
        _, ingredients = asyncio.run(client.fetch_week_ingredients(week))

    orders = plan_orders(ingredients, classifier, fresh_horizon_days=horizon)
    print(render_markdown(orders))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
