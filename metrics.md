# Metrics — vývojová session 2026-06-12

Stav k 2026-06-12 15:57 CEST. Pokrývá jedinou konverzaci s Claude
(Fable 5, mobilní aplikace), ve které vznikl celý dosavadní projekt
(fáze 1–3, dokumentace, YAML product map vč. klasifikačních overrides).
Dle uživatele v aktuálním 5h okně neproběhlo nic jiného.

## Tool cally (přesná čísla z konverzace)

| Nástroj | Počet | Použití |
|---|---|---|
| bash_tool | 36 | scaffolding, testy, git, introspekce API, push |
| create_file | 16 | moduly, testy, HA komponenta (1× selhal — existující README) |
| str_replace | 4 | opravy testu, regexu, rozšíření CLI |
| present_files | 2 | zip bundly fáze 1 a 2 |
| web_search | 2 | rešerše Rohlík MCP, cookidoo-api |
| web_fetch | 1 | kontrola GitHub repa |
| ask_user_input_v0 | 1 | volba architektury (checkout, runtime) |
| user_time_v0 | 3 | timestampy tohoto souboru |
| **Celkem** | **65** | (včetně commitu této aktualizace) |

## Konverzace

- 17 uživatelských zpráv (zadání → architektura → fáze 1–3 → push →
  README → metriky → YAML product map → class overrides v mapě)
- 10 git commitů pushnutých na main, 22/22 testů
- 2× klonování referenčních repozitářů, 1× instalace HA do venv (import-check)

## Spotřeba — ověřená data z aplikace (Settings → Usage)

Plán: **Claude Max 5×**, dva ověřené odečty ze screenshotů:

| Čas | Stav projektu | 5h okno | Weekly (all models) |
|---|---|---|---|
| 15:06 | po fázích 1–3 + dokumentace | **50 %** | 3 % |
| 15:58 | + YAML mapa, class overrides, aktualizace metrik | **65 %** | 4 % |

Reset okna ~19:00, weekly reset středa ~20:00. Hlavní vývoj (fáze 1–3)
stál polovinu jednoho 5h okna; následné iterace nad mapováním
a dokumentací dalších ~15 p. b. — pozdější úpravy jsou relativně
dražší, protože každé kolo přeposílá celý narostlý kontext konverzace.

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
