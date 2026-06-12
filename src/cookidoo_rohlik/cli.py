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

from .classify import Classifier, load_map_overrides
from .models import Ingredient
from .planner import plan_orders
from .render import render_markdown


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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cookidoo-rohlik")
    sub = parser.add_subparsers(dest="command", required=True)

    p_plan = sub.add_parser("plan", help="Plan the week's orders (dry-run)")
    p_plan.add_argument("--sample", type=Path, help="Offline JSON sample instead of live Cookidoo")
    p_plan.add_argument("--week", type=str, help="Any day of the target week, YYYY-MM-DD (default: today)")
    p_plan.add_argument("--config", type=Path, default=Path("config/config.yaml"))
    p_plan.add_argument("-v", "--verbose", action="store_true")

    p_order = sub.add_parser(
        "order", help="Resolve orders to Rohlik products (dry-run unless --execute)"
    )
    p_order.add_argument("--sample", type=Path, help="Offline JSON sample instead of live Cookidoo")
    p_order.add_argument("--week", type=str, help="Any day of the target week, YYYY-MM-DD")
    p_order.add_argument("--date", type=str, help="Only the order delivered on this date (YYYY-MM-DD)")
    p_order.add_argument("--execute", action="store_true",
                         help="Actually add matched items to the Rohlik cart")
    p_order.add_argument("--cache", type=Path, default=Path("config/product_map.yaml"),
                         help="Ingredient->product mapping cache, YAML (curatable)")
    p_order.add_argument("--config", type=Path, default=Path("config/config.yaml"))
    p_order.add_argument("-v", "--verbose", action="store_true")

    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(levelname)s %(name)s: %(message)s")

    cfg = _load_config(args.config)
    classifier = Classifier.from_config(cfg)
    map_path = getattr(args, "cache", None) or Path("config/product_map.yaml")
    classifier.overrides.update(load_map_overrides(Path(map_path)))
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

    if args.command == "plan":
        print(render_markdown(orders))
        return 0

    # command == "order": resolve against Rohlik
    if args.date:
        target = datetime.strptime(args.date, "%Y-%m-%d").date()
        orders = [o for o in orders if o.delivery_date == target]
        if not orders:
            print(f"ERROR: no planned order with delivery date {target}.", file=sys.stderr)
            return 1

    r_email = os.environ.get("ROHLIK_EMAIL")
    r_password = os.environ.get("ROHLIK_PASSWORD")
    if not r_email or not r_password:
        print("ERROR: set ROHLIK_EMAIL and ROHLIK_PASSWORD.", file=sys.stderr)
        return 2

    from .matching import ProductMatcher
    from .orchestrator import render_resolution, resolve_order
    from .rohlik_client import RohlikClient

    async def _run() -> int:
        matcher = ProductMatcher(cache_path=args.cache)
        async with RohlikClient(r_email, r_password) as client:
            for order in orders:
                res = await resolve_order(order, matcher, client, execute=args.execute)
                print(render_resolution(res))
                print()
            if args.execute:
                total, items = await client.get_cart()
                print(f"Košík: {len(items)} položek, celkem {total:.0f} CZK.")
                print("Dokonči objednávku v aplikaci/e-shopu Rohlík (checkout je vždy ruční).")
        return 0

    return asyncio.run(_run())


if __name__ == "__main__":
    raise SystemExit(main())
