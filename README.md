# Cookidoo → Rohlík

Integrace, která vezme týdenní jídelníček z Cookidoo (Thermomix) a objedná
ingredience z Rohlik.cz — trvanlivé jednou týdně automaticky, čerstvé
„just-in-time" tak, aby ráno dorazily suroviny na daný den (max 2 dny dopředu).

## Stav (fáze 1 hotová)

- [x] Cookidoo klient (neoficiální `cookidoo-api`): týdenní plán → ingredience po dnech
- [x] Klasifikace čerstvé / trvanlivé / spíž (CZ keyword defaults + overrides v configu)
- [x] Plánovač objednávek: 1× týdenní trvanlivá (auto-checkout) + čerstvé okna max 2 dny
- [x] CLI dry-run (offline sample i živé Cookidoo)
- [x] Fáze 2: Rohlík klient (login, search, košík, sloty), parsování množství,
      matcher ingredience→produkt s perzistentní cache (`config/product_map.json`),
      orchestrátor + CLI `order` (dry-run / `--execute` naplní košík)
- [x] Fáze 3: Home Assistant custom integrace (`custom_components/cookidoo_rohlik`):
      config flow + options, služby `plan_week` a `prepare_orders`, persistent
      notifikace, event `cookidoo_rohlik_orders_prepared` pro actionable
      notifikace na mobil (příklady v `examples/ha_automations.yaml`)

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

# napárování na produkty Rohlíku (dry-run, jen čte)
export ROHLIK_EMAIL=...
export ROHLIK_PASSWORD=...
python -m cookidoo_rohlik.cli order --week 2026-06-15

# reálně naplnit košík pro konkrétní objednávku (checkout dokončíš v aplikaci)
python -m cookidoo_rohlik.cli order --week 2026-06-15 --date 2026-06-15 --execute
```

## Důležité zjištění ke checkoutu

Žádný veřejný reverse-engineered projekt neimplementuje dokončení objednávky —
flow proto končí naplněným košíkem (+ do budoucna notifikace z HA). To je
v souladu i s podmínkami oficiálního Rohlík MCP. "Hybrid" tedy zatím znamená:
trvanlivá objednávka se připraví automaticky do košíku, čerstvé taky,
checkout potvrzuješ v aplikaci Rohlík (jeden tap navíc).

## Mapování ingredience → produkt

`config/product_map.json` je perzistentní cache; první match se učí
z vyhledávání (token overlap, levnější vyhrává), pod 50 % shody se položka
nahlásí jako nenalezená. Soubor můžeš ručně kurátorovat — pevně přiřadit
přesný produkt (product_id) k ingredienci.

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


## Home Assistant

1. Zkopíruj `custom_components/cookidoo_rohlik/` do HA `config/custom_components/`
   (nebo přidej repo jako HACS custom repository) a restartuj HA.
2. Nastavení → Zařízení a služby → Přidat integraci → "Cookidoo → Rohlík"
   (4 přihlašovací údaje; Rohlík se ověří hned, Cookidoo při prvním plánu).
3. V možnostech integrace: horizont čerstvých, auto-plnění košíku, overrides.
4. Převezmi automatizace z `examples/ha_automations.yaml` (neděle plán,
   denně 19:30 příprava košíku na zítřek, mobilní notifikace s deeplinkem).

Mapping cache žije v `config/cookidoo_rohlik_product_map.json` a lze ji
ručně kurátorovat. Core knihovna je do komponenty vendorovaná —
po změně v `src/` spusť `scripts/sync_core.sh`.
