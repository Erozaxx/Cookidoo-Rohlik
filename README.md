# Cookidoo → Rohlík 🍳🛒

**Naplánuj si v Cookidoo jídelníček na týden — o nákup se postará integrace.**

Trvanlivé potraviny ti přijedou jednou na začátku týdne. Čerstvé (maso, ryby,
mléčné výrobky, bylinky…) se objednávají postupně tak, aby ti **ráno dorazily
suroviny na ten daný den** — nikdy ne víc než na 2 dny dopředu. Žádná zvadlá
bazalka ve čtvrtek.

## Jak to vypadá v praxi

Naplánuješ si v Cookidoo třeba: pondělí kuře na paprice, úterý těstoviny,
čtvrtek losos, sobota guláš. Integrace pak:

| Kdy | Co se stane |
|---|---|
| neděle večer | 📋 notifikace s plánem objednávek na celý týden |
| neděle večer | 🛒 připraví košík: **týdenní trvanlivé** (těstoviny, brambory…) + čerstvé na po+út |
| ty: 1 tap | ✅ potvrdíš objednávku v aplikaci Rohlík, vybereš ranní slot |
| pondělí ráno | 🚚 doručení — vaříš z čerstvého |
| středa večer | 🛒 košík s čerstvým na čtvrtek (losos, kopr) → tap → čtvrtek ráno doručeno |
| pátek večer | 🛒 košík na sobotní guláš → tap → sobota ráno doručeno |

Ingredience, které máš doma (sůl, olej, koření…), se neobjednávají vůbec.

## Jak to funguje uvnitř

1. **Cookidoo** — stáhne týdenní kalendář a ingredience receptů
   (neoficiální [cookidoo-api](https://github.com/miaucl/cookidoo-api)).
2. **Klasifikace** — každá ingredience je *čerstvá* / *trvanlivá* / *spíž*
   (česká klíčová slova + tvoje vlastní výjimky).
3. **Plánovač** — rozdělí týden na objednávky: 1× trvanlivá + čerstvá „okna"
   max 2 dny (nastavitelné 1–4).
4. **Párování** — najde produkty na Rohlíku, spočítá počet balení podle
   gramáže a učí se: jednou nalezené mapování ingredience → produkt si
   pamatuje v čitelném `product_map.yaml`, který můžeš ručně upravovat
   (ukázka v `config/product_map.example.yaml`).
5. **Košík + notifikace** — naplní košík na Rohlíku a pošle ti report
   s cenou a případnými nenalezenými položkami. **Checkout dokončuješ
   jedním tapem v aplikaci Rohlík** — automatické dokončení objednávky
   neexistuje (žádné veřejné API ho neumí a podmínky Rohlíku ho přes
   automatizaci nepovolují).

## Současný stav

| Část | Stav |
|---|---|
| Plánovač, klasifikace, parsování množství | ✅ hotovo, pokryto testy (19/19) |
| Cookidoo klient | ✅ napsáno proti reálnému API v0.17 — ⚠️ čeká na živý test |
| Rohlík klient (login, hledání, košík, sloty) | ✅ napsáno dle ověřených endpointů — ⚠️ čeká na živý test |
| Párování ingredience → produkt | ✅ hotovo (token overlap + cache) — kvalitu doladíme po živém testu |
| CLI (dry-run i ostré plnění košíku) | ✅ hotovo |
| Home Assistant integrace | ✅ napsáno, import-checknuto proti HA 2025.1 — ⚠️ neběželo v reálném HA |
| Automatický checkout | ❌ záměrně ne — vždy 1 tap v aplikaci Rohlík |
| Výběr ranního slotu, kontrola min. hodnoty objednávky | 🔜 roadmap |

⚠️ = funkční kód, který zatím nebyl spuštěn proti živým účtům. Než to
pustíš naostro, projdi checklist níže.

## Rychlý start (CLI)

```bash
pip install -e ".[dev]"
pytest                                                  # 1) offline testy

# 2) živé Cookidoo — jen čte
export COOKIDOO_EMAIL=...   # nikdy necommitovat
export COOKIDOO_PASSWORD=...
python -m cookidoo_rohlik.cli plan --week 2026-06-15

# 3) párování na Rohlík — dry-run, jen čte
export ROHLIK_EMAIL=...
export ROHLIK_PASSWORD=...
python -m cookidoo_rohlik.cli order --week 2026-06-15

# 4) ostrý běh — naplní košík (checkout dokončíš v aplikaci)
python -m cookidoo_rohlik.cli order --week 2026-06-15 --date 2026-06-15 --execute
```

Offline ukázka bez účtů: `python -m cookidoo_rohlik.cli plan --sample tests/sample_week.json`

## Home Assistant

1. Zkopíruj `custom_components/cookidoo_rohlik/` do HA `config/custom_components/`
   (nebo přidej repo jako HACS custom repository) a restartuj HA.
2. Nastavení → Zařízení a služby → Přidat integraci → **Cookidoo → Rohlík**
   (4 přihlašovací údaje; Rohlík se ověří hned, Cookidoo při prvním plánu).
3. V možnostech integrace: horizont čerstvých (1–4 dny), auto-plnění košíku,
   klasifikační výjimky.
4. Převezmi automatizace z [`examples/ha_automations.yaml`](examples/ha_automations.yaml):
   neděle plán, denně 19:30 příprava košíku na zítřek, mobilní notifikace
   s cenou a proklikem do Rohlíku.

Služby: `cookidoo_rohlik.plan_week` a `cookidoo_rohlik.prepare_orders`
(jdou volat i ručně z Vývojářských nástrojů). Po přípravě košíku se vyšle
event `cookidoo_rohlik_orders_prepared` — na něj navěsíš vlastní notifikace.

## Doladění klasifikace a párování

- **Klasifikace**: defaultní česká klíčová slova občas netrefí —
  např. „rajčatový protlak" spadne do čerstvých (klíčové slovo `rajc`).
  Oprava jedním řádkem v configu / HA options:

  ```yaml
  classification:
    overrides:
      "rajčatový protlak": durable
  ```

- **Párování**: `config/product_map.yaml` (v HA
  `config/cookidoo_rohlik_product_map.yaml`) si pamatuje naučená mapování
  v čitelném YAML — klíčem je název ingredience, jak ho znáš z receptu:

  ```yaml
  kuřecí stehna:
    product_id: 1294352          # z URL produktu na rohlik.cz
    product_name: Vodňanské kuřecí stehna chlazená
    textual_amount: 600 g        # velikost balení -> výpočet počtu kusů
  ```

  Když matcher vybere blbost, přepiš `product_id` na správný produkt —
  příště už se nezmýlí; smazáním záznamu ho necháš hledat znovu. Položky
  pod 50% shodou se nehádají a objeví se v notifikaci jako „nenalezeno".
  Starší `product_map.json` se při prvním běhu automaticky zmigruje.

## Roadmap

- Výběr ranního doručovacího slotu (endpoint už klient umí číst)
- Kontrola minimální hodnoty objednávky před naplněním košíku
- HA senzor s nenapárovanými položkami, reauth flow
- Chytřejší párování (preference biokvalita/značka/cena, případně LLM)

## Vývoj

Zdroj pravdy core logiky je `src/cookidoo_rohlik/`; do HA komponenty se
vendoruje přes `scripts/sync_core.sh` (po každé změně core spustit).
Testy: `pytest`.

## Disclaimer

Neoficiální integrace pro osobní použití. Používá reverse-engineered API
Cookidoo i Rohlíku — obojí se může kdykoliv změnit a rozbít. Nijak
nesouvisí s Vorwerk/Cookidoo ani VELKÁ PECKA s.r.o. (Rohlik.cz).
Objednávky vždy potvrzuješ sám v aplikaci Rohlík; před potvrzením
zkontroluj obsah košíku.
