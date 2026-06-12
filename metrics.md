# Metrics — vývojová session 2026-06-12

Stav k 2026-06-12 15:15 CEST. Pokrývá jedinou konverzaci s Claude
(Fable 5, mobilní aplikace), ve které vznikl celý dosavadní projekt
(fáze 1–3, dokumentace, YAML product map). Dle uživatele v aktuálním
5h okně neproběhlo nic jiného.

## Tool cally (přesná čísla z konverzace)

| Nástroj | Počet | Použití |
|---|---|---|
| bash_tool | 33 | scaffolding, testy, git, introspekce API, push |
| create_file | 16 | moduly, testy, HA komponenta (1× selhal — existující README) |
| str_replace | 4 | opravy testu, regexu, rozšíření CLI |
| present_files | 2 | zip bundly fáze 1 a 2 |
| web_search | 2 | rešerše Rohlík MCP, cookidoo-api |
| web_fetch | 1 | kontrola GitHub repa |
| ask_user_input_v0 | 1 | volba architektury (checkout, runtime) |
| user_time_v0 | 2 | timestampy tohoto souboru |
| **Celkem** | **61** | (včetně commitu této aktualizace) |

## Konverzace

- 14 uživatelských zpráv (zadání → architektura → fáze 1–3 → push →
  README → metriky → YAML product map)
- 8 git commitů pushnutých na main, 20/20 testů
- 2× klonování referenčních repozitářů, 1× instalace HA do venv (import-check)

## Spotřeba — ověřená data z aplikace (Settings → Usage)

Plán: **Claude Max 5×**. Screenshot z 2026-06-12 15:06 CEST,
po dokončení fází 1–3 a dokumentace (pozdější drobné úpravy — YAML
mapa, aktualizace metrik — už v čísle nejsou):

| Limit | Spotřeba | Reset |
|---|---|---|
| Current session (5h okno) | **50 %** | za 3 h 54 min (~19:00) |
| Weekly limit (all models) | **3 %** | středa 20:00 |

Celý projekt tedy stál polovinu jednoho 5h okna plánu Max 5×.

## Spotřeba tokenů — pouze hrubý odhad

Aplikace ukazuje procenta limitu, ne absolutní tokeny; ty Claude
nevidí vůbec. Odhad vychází z délky konverzace a počtu kol:

| Metrika | Odhad (řádově) |
|---|---|
| Output tokeny (odpovědi + generované soubory) | ~40–60 tis. |
| Input tokeny kumulativně (kontext se přeposílá každé kolo; velké tool výstupy z webu a repozitářů) | ~600 tis. – 1,2 mil. |

Největší položky inputu: HTML z GitHub fetchů, výpisy zdrojáků
HA-RohlikCZ a opakované přeposílání rostoucího kontextu v ~55 koleích
nástrojů. Berte jako odhad ±2×.
