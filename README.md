# Cookidoo → Rohlík

Integrace, která vezme týdenní jídelníček z Cookidoo (Thermomix) a objedná
ingredience z Rohlik.cz — trvanlivé jednou týdně automaticky, čerstvé
„just-in-time" tak, aby ráno dorazily suroviny na daný den (max 2 dny dopředu).

## Stav (fáze 1 hotová)

- [x] Cookidoo klient (neoficiální `cookidoo-api`): týdenní plán → ingredience po dnech
- [x] Klasifikace čerstvé / trvanlivé / spíž (CZ keyword defaults + overrides v configu)
- [x] Plánovač objednávek: 1× týdenní trvanlivá (auto-checkout) + čerstvé okna max 2 dny
- [x] CLI dry-run (offline sample i živé Cookidoo)
- [ ] Fáze 2: Rohlík klient (search, mapování ingredience→produkt, košík, sloty, checkout)
- [ ] Fáze 3: Home Assistant custom integrace (config flow, notifikace s potvrzením čerstvé objednávky)

## Rychlý start

```bash
pip install -e ".[dev]"
pytest

# offline dry-run na ukázkových datech
python -m cookidoo_rohlik.cli plan --sample tests/sample_week.json

# živě proti Cookidoo
export COOKIDOO_EMAIL=...   # nikdy necommitovat
export COOKIDOO_PASSWORD=...
python -m cookidoo_rohlik.cli plan --week 2026-06-15
```

## Konfigurace

`cp config/config.example.yaml config/config.yaml` (je v .gitignore).
Klasifikaci dolaďuj přes `classification.overrides` — např. „rajčatový protlak"
defaultně spadne do čerstvých (keyword `rajc`), správně patří do trvanlivých:

```yaml
classification:
  overrides:
    "rajčatový protlak": durable
```

## Disclaimer

Používá neoficiální Cookidoo API (`cookidoo-api`) — může se kdykoliv rozbít.
Rohlík část (fáze 2): oficiální MCP server umožňuje jen plnění košíku
(objednávku dokončuje zákazník v e-shopu); automatický checkout trvanlivé
objednávky vyžaduje neoficiální API. Jen pro osobní použití.
