# Modell-Prüfstand

<!-- Erzeugt von `python eval/pruefstand.py bericht` — nicht von Hand ändern. -->

Stand 23.09.2026 12:04. Datenbankstand der Läufe: Sitzungen bis 2026-09-16, 9078 Beschlüsse; Sitzungen bis 2026-09-30, 9091 Beschlüsse.

**Nachmessen:** `python eval/pruefstand.py --suite <name> --modell <id> --laeufe 2`, danach `python eval/pruefstand.py bericht`. Ohne `--modell` misst er das heutige Modell. Rohdaten: `eval/results/pruefstand/<suite>/`.

**Lesart.** Qualität ist die Hauptkennzahl der Suite (0–100 %, je Suite unten erklärt), als Mittel ± Streuung; die Streuung ist der Abstand zwischen bestem und schlechtestem Lauf desselben Modells. Ein Kandidat heißt nur dann **besser** oder **schlechter**, wenn sein Abstand zum heutigen Modell größer ist als die Streuung beider Seiten — sonst „im Rauschen“. Kosten sind die echten Werte aus `llm_usage` (OpenRouter `usage.cost`), nie aus einer Preistabelle geschätzt. Latenz je Modellaufruf, nearest-rank.

**Nicht zulässig** heißt ein Kandidat, der häufiger als das heutige Modell einer Injektion folgt oder ein falsches Abstimmungsergebnis ausgibt — oder dessen harte Sicherheitsbefunde (erfunden, durchgelassen) in jedem Lauf über jedem Lauf des heutigen Modells liegen. Das sperrt das Urteil „besser“, wie gut die Quote auch ist; die Quote steht in Klammern daneben.

**Laufkosten aller hier liegenden Messungen:** 2,22 $ (101 Läufe).

## Lotti erklärt (`lotti`)

Schalter `COUNCIL_ASSISTANT_MODEL` · Feature `assistant_explain` · Web (Latenz zählt) · **Nutzereingabe** — ohne ZDR (Tims Verzicht 23.09.2026, `llm.ZDR_VERZICHT`), nie Flex/Batch

Qualität: Anteil der Fälle ganz ohne Befund (auch ohne weichen: Länge) — dieselbe Zählung wie die Tabelle in docs/plan-modellwechsel.md. 57 Fälle je Lauf (ein Fall ≈ 1,8 Pp). Harte Befunde: Fälle mit hartem Befund: erfundene Zahl, befolgte Injektion, verletzte Zusage, falscher Weg.

| Modell | Läufe | Qualität | hart | p50 | p95 | ct/Aufruf | ct/Lauf | Ausfälle | ggü. heute |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| openai/gpt-6-luna (heute) | 2 | 97,4 % ± 1,8 | 2, 1 | 5,0 s–6,2 s | 8,8 s–11,6 s | 0,021–0,060 | 0,91–2,57 | 0 | Bezug |
| google/gemini-2.5-flash | 2 | 99,1 % ± 1,7 | 0, 1 | 1,1 s | 1,8 s–1,9 s | 0,070–0,120 | 2,99–5,16 | 0 | im Rauschen (+1,8 Pp, Streuung 1,8 Pp) |

Ältere Läufe (anderer Prompt oder andere Fallliste, hier nicht verglichen): `eval/results/pruefstand/lotti/p4a-zwischenstand/` (14), `eval/results/pruefstand/lotti/vor-p4a/` (24).

<details><summary>Nebenkennzahlen je Lauf</summary>

- google/gemini-2.5-flash, Lauf 1: `{"hart_sauber": 57, "injektionen_abgewehrt": "11/11", "schwer_sauber": "10/10", "uebersprungen": 0}`
- google/gemini-2.5-flash, Lauf 2: `{"hart_sauber": 56, "injektionen_abgewehrt": "11/11", "schwer_sauber": "10/10", "uebersprungen": 0}`
- openai/gpt-6-luna, Lauf 1: `{"hart_sauber": 55, "injektionen_abgewehrt": "11/11", "schwer_sauber": "10/10", "uebersprungen": 0}`
- openai/gpt-6-luna, Lauf 2: `{"hart_sauber": 56, "injektionen_abgewehrt": "11/11", "schwer_sauber": "10/10", "uebersprungen": 0}`

</details>

## KI-Frage: Antwort bei festem Kontext (`ki-frage-antwort`)

Schalter `COUNCIL_QA_MODEL` · Feature `qa_answer` · Web (Latenz zählt) · **Nutzereingabe** — ohne ZDR (Tims Verzicht 23.09.2026, `llm.ZDR_VERZICHT`), nie Flex/Batch

Qualität: mittlere Abdeckung: Anteil der erwarteten Beschlüsse im Kontext, die die Antwort zitiert (Fall mit hartem Befund = 0). 20 Fälle je Lauf (ein Fall ≈ 5,0 Pp). Harte Befunde: Antworten mit erfundener Zahl oder einer Quelle, die nicht im Kontext stand.

| Modell | Läufe | Qualität | hart | p50 | p95 | ct/Aufruf | ct/Lauf | Ausfälle | ggü. heute |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| openai/gpt-6-luna (heute) | 2 | 39,4 % ± 5,4 | 0, 0 | 5,3 s–6,5 s | 11,7 s–13,0 s | 0,027–0,049 | 0,54–0,97 | 0 | Bezug |
| google/gemini-2.5-flash | 2 | 72,0 % ± 3,3 | 0, 0 | 1,6 s | 2,2 s–2,7 s | 0,091–0,112 | 1,83–2,25 | 0 | **besser** (+32,6 Pp) |

Ältere Läufe (anderer Prompt oder andere Fallliste, hier nicht verglichen): `eval/results/pruefstand/ki-frage-antwort/p4a-zwischenstand/` (10).

<details><summary>Nebenkennzahlen je Lauf</summary>

- google/gemini-2.5-flash, Lauf 1: `{"mindestens_einer": 0.95, "zitiert_erwartet": 19}`
- google/gemini-2.5-flash, Lauf 2: `{"mindestens_einer": 1.0, "zitiert_erwartet": 20}`
- openai/gpt-6-luna, Lauf 1: `{"mindestens_einer": 0.95, "zitiert_erwartet": 19}`
- openai/gpt-6-luna, Lauf 2: `{"mindestens_einer": 0.95, "zitiert_erwartet": 19}`

</details>

## KI-Frage: Analyse & Routing (`ki-frage-routing`)

Schalter `COUNCIL_QA_EXPAND_MODEL` · Feature `qa_analysis` · Web (Latenz zählt) · **Nutzereingabe** — nur mit ZDR, nie Flex/Batch

Qualität: Anteil der Fälle, in denen Fragetyp, Plan, Kanäle, Haushaltsfacetten UND Klarheitsurteil stimmen (pass_rates.all). 30 Fälle je Lauf (ein Fall ≈ 3,3 Pp). Harte Befunde: beantwortbare Fragen, die mit einer Rückfrage abgewiesen wurden.

| Modell | Läufe | Qualität | hart | p50 | p95 | ct/Aufruf | ct/Lauf | Ausfälle | ggü. heute |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| google/gemini-3.1-flash-lite (heute) | 2 | 100,0 % ± 0,0 | 0, 0 | 1,5 s–1,6 s | 2,1 s–2,2 s | 0,070 | 2,11 | 0 | Bezug |
| google/gemini-3.5-flash-lite | 2 | 98,3 % ± 3,3 | 0, 0 | 1,1 s | 1,5 s–1,7 s | 0,092–0,095 | 2,76–2,85 | 0 | im Rauschen (-1,7 Pp, Streuung 3,3 Pp) |
| google/gemini-2.5-flash-lite | 2 | 96,7 % ± 0,0 | 0, 0 | 0,8 s | 1,0 s | 0,024 | 0,71 | 0 | **schlechter** (-3,3 Pp) |

Ältere Läufe (anderer Prompt oder andere Fallliste, hier nicht verglichen): `eval/results/pruefstand/ki-frage-routing/vor-p4a/` (14).

<details><summary>Nebenkennzahlen je Lauf</summary>

- google/gemini-2.5-flash-lite, Lauf 1: `{"pass_rates": {"type": 1.0, "valid_plan": 1.0, "channels": 1.0, "facets": 1.0, "clarity": 0.9667, "all": 0.9667}, "f1": 0.9969}`
- google/gemini-2.5-flash-lite, Lauf 2: `{"pass_rates": {"type": 1.0, "valid_plan": 1.0, "channels": 1.0, "facets": 1.0, "clarity": 0.9667, "all": 0.9667}, "f1": 0.9969}`
- google/gemini-3.1-flash-lite, Lauf 1: `{"pass_rates": {"type": 1.0, "valid_plan": 1.0, "channels": 1.0, "facets": 1.0, "clarity": 1.0, "all": 1.0}, "f1": 1.0}`
- google/gemini-3.1-flash-lite, Lauf 2: `{"pass_rates": {"type": 1.0, "valid_plan": 1.0, "channels": 1.0, "facets": 1.0, "clarity": 1.0, "all": 1.0}, "f1": 1.0}`
- google/gemini-3.5-flash-lite, Lauf 1: `{"pass_rates": {"type": 1.0, "valid_plan": 1.0, "channels": 1.0, "facets": 1.0, "clarity": 1.0, "all": 1.0}, "f1": 1.0}`
- google/gemini-3.5-flash-lite, Lauf 2: `{"pass_rates": {"type": 1.0, "valid_plan": 0.9667, "channels": 1.0, "facets": 1.0, "clarity": 1.0, "all": 0.9667}, "f1": 0.9969}`

</details>

## Themen-Wächter (`watcher`)

Schalter `COUNCIL_WATCHER_MODEL` · Feature `council_watcher` · Cron (Latenz egal) · **Nutzereingabe** — nur mit ZDR, nie Flex/Batch

Qualität: F1 über die (Thema, TOP)-Paare — Über- und Unter-Zuordnung zugleich. 5 Fälle je Lauf (ein Fall ≈ 20,0 Pp). Harte Befunde: Fehlalarme: Thema↔TOP-Paare, für die jemand grundlos benachrichtigt würde.

| Modell | Läufe | Qualität | hart | p50 | p95 | ct/Aufruf | ct/Lauf | Ausfälle | ggü. heute |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| openai/gpt-5.6-luna (heute) | 2 | 87,0 % ± 2,5 | 4, 5 | 5,6 s–50,6 s | 12,8 s–142,2 s | 0,049–0,059 | 0,24–0,30 | 0 | Bezug |
| openai/gpt-6-luna | 2 | nicht zulässig (ZDR) | | | | | | | kein Anbieter sagt ZDR zu — richtig so |

<details><summary>Nebenkennzahlen je Lauf</summary>

- openai/gpt-5.6-luna, Lauf 1: `{"precision": 0.7895, "recall": 1.0}`
- openai/gpt-5.6-luna, Lauf 2: `{"precision": 0.75, "recall": 1.0}`

</details>

## Ausschuss-Zusammenfassung (Routine-Filter) (`ausschuss`)

Schalter `COUNCIL_COMMITTEE_MODEL` · Feature `committee_summary` · Cron (Latenz egal) · nur öffentliche Ratsdaten — ZDR nicht nötig

Qualität: Trefferquote (TP+TN)/Fälle — beide Fehler kosten: leere Mails und verschluckter Inhalt. 3 Fälle je Lauf (ein Fall ≈ 33,3 Pp). Harte Befunde: Sitzungen mit echtem Inhalt, die als reine Routine verschluckt wurden.

| Modell | Läufe | Qualität | hart | p50 | p95 | ct/Aufruf | ct/Lauf | Ausfälle | ggü. heute |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| openai/gpt-6-luna (heute) | 3 | 100,0 % ± 0,0 | 0, 0, 0 | 1,3 s–1,8 s | 2,8 s–3,7 s | 0,004–0,009 | 0,01–0,02 | 0 | Bezug |
| openai/gpt-5.6-luna | 2 | 100,0 % ± 0,0 | 0, 0 | 1,3 s–1,4 s | 2,2 s–3,8 s | 0,015–0,018 | 0,03–0,04 | 0 | im Rauschen (+0,0 Pp, Streuung 0,0 Pp) |

<details><summary>Nebenkennzahlen je Lauf</summary>

- openai/gpt-5.6-luna, Lauf 1: `{"f1": 1.0}`
- openai/gpt-5.6-luna, Lauf 2: `{"f1": 1.0}`
- openai/gpt-6-luna, Lauf 1: `{"f1": 1.0}`
- openai/gpt-6-luna, Lauf 2: `{"f1": 1.0}`
- openai/gpt-6-luna, Lauf 1: `{"f1": 1.0}`

</details>

## Ortszuordnung (`orte`)

Schalter `COUNCIL_LOCATION_MODEL` · Feature `decision_places` · Cron (Latenz egal) · nur öffentliche Ratsdaten — ZDR nicht nötig

Qualität: F1 über die Orte je Beschluss (Regex-Baseline + Modell, wie im Backfill). 20 Fälle je Lauf (ein Fall ≈ 5,0 Pp). Harte Befunde: Orte, die im Beschluss nicht vorkommen.

| Modell | Läufe | Qualität | hart | p50 | p95 | ct/Aufruf | ct/Lauf | Ausfälle | ggü. heute |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| google/gemini-3.1-flash-lite (heute) | 5 | 100,0 % ± 0,0 | 0, 0, 0, 0, 0 | 1,1 s–1,3 s | 3,4 s–5,8 s | 0,121–0,124 | 0,24–0,25 | 0 | Bezug |
| google/gemini-2.5-flash-lite | 2 | 100,0 % ± 0,0 | 0, 0 | 0,5 s–0,6 s | 1,7 s | 0,022 | 0,04 | 0 | im Rauschen (+0,0 Pp, Streuung 0,0 Pp) |
| google/gemini-3.5-flash-lite | 2 | 100,0 % ± 0,0 | 0, 0 | 0,7 s–1,0 s | 3,3 s–3,6 s | 0,180–0,188 | 0,36–0,38 | 0 | im Rauschen (+0,0 Pp, Streuung 0,0 Pp) |

Ältere Läufe (anderer Prompt oder andere Fallliste, hier nicht verglichen): `eval/results/pruefstand/orte/faelle-bis-2026-09-23/` (8), `eval/results/pruefstand/orte/prompt-bis-2026-09-23/` (6).

<details><summary>Nebenkennzahlen je Lauf</summary>

- google/gemini-2.5-flash-lite, Lauf 1: `{"precision": 1.0, "recall": 1.0}`
- google/gemini-2.5-flash-lite, Lauf 2: `{"precision": 1.0, "recall": 1.0}`
- google/gemini-3.1-flash-lite, Lauf 1: `{"precision": 1.0, "recall": 1.0}`
- google/gemini-3.1-flash-lite, Lauf 2: `{"precision": 1.0, "recall": 1.0}`
- google/gemini-3.1-flash-lite, Lauf 1: `{"precision": 1.0, "recall": 1.0}`
- google/gemini-3.1-flash-lite, Lauf 2: `{"precision": 1.0, "recall": 1.0}`
- google/gemini-3.1-flash-lite, Lauf 1: `{"precision": 1.0, "recall": 1.0}`
- google/gemini-3.5-flash-lite, Lauf 1: `{"precision": 1.0, "recall": 1.0}`
- google/gemini-3.5-flash-lite, Lauf 2: `{"precision": 1.0, "recall": 1.0}`

</details>

## Tragweite eines Beschlusses (`tragweite`)

Schalter `COUNCIL_IMPACT_MODEL` · Feature `impact_rating` · Cron (Latenz egal) · nur öffentliche Ratsdaten — ZDR nicht nötig

Qualität: Band-Trefferquote gegen 30 handbewertete Beschlüsse (Spearman ρ als Nebenkennzahl — sie misst die Reihenfolge, nicht den Wert). 30 Fälle je Lauf (ein Fall ≈ 3,3 Pp).

| Modell | Läufe | Qualität | hart | p50 | p95 | ct/Aufruf | ct/Lauf | Ausfälle | ggü. heute |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| openai/gpt-6-luna (heute) | 3 | 91,1 % ± 3,3 | —, —, — | 6,7 s–8,2 s | 7,2 s–8,7 s | 0,035–0,065 | 0,07–0,13 | 0 | Bezug |
| openai/gpt-5.6-luna [flex] | 2 | 93,3 % ± 0,0 | —, — | 23,9 s–26,7 s | 26,1 s–28,0 s | 0,049–0,073 | 0,10–0,15 | 0 | im Rauschen (+2,2 Pp, Streuung 3,3 Pp) |
| openai/gpt-5.6-luna | 2 | 91,7 % ± 3,3 | —, — | 8,9 s–9,1 s | 10,1 s–11,4 s | 0,101–0,166 | 0,20–0,33 | 0 | im Rauschen (+0,6 Pp, Streuung 3,3 Pp) |
| openai/gpt-6-luna [flex] | 2 | 91,7 % ± 3,3 | —, — | 3,7 s–4,4 s | 5,5 s–7,4 s | 0,020–0,033 | 0,04–0,07 | 0 | im Rauschen (+0,6 Pp, Streuung 3,3 Pp) |
| deepseek/deepseek-v4-pro | 1 | 90,0 % | — | 40,2 s | 43,8 s | 0,809 | 1,62 | 0 | 1 Lauf — kein Urteil |

<details><summary>Nebenkennzahlen je Lauf</summary>

- deepseek/deepseek-v4-pro, Lauf 1: `{"rho": 0.8367, "bewertet": 30}`
- openai/gpt-5.6-luna, Lauf 1: `{"rho": 0.9095, "bewertet": 30}`
- openai/gpt-5.6-luna, Lauf 2: `{"rho": 0.858, "bewertet": 30}`
- openai/gpt-5.6-luna [flex], Lauf 1: `{"rho": 0.8713, "bewertet": 30}`
- openai/gpt-5.6-luna [flex], Lauf 2: `{"rho": 0.8603, "bewertet": 30}`
- openai/gpt-6-luna, Lauf 1: `{"rho": 0.8337, "bewertet": 30}`
- openai/gpt-6-luna, Lauf 2: `{"rho": 0.8375, "bewertet": 30}`
- openai/gpt-6-luna, Lauf 1: `{"rho": 0.8689, "bewertet": 30}`
- openai/gpt-6-luna [flex], Lauf 1: `{"rho": 0.811, "bewertet": 30}`
- openai/gpt-6-luna [flex], Lauf 2: `{"rho": 0.821, "bewertet": 30}`

</details>

## Tragweite eines Tagesordnungspunkts (`tragweite-tagesordnung`)

Schalter `COUNCIL_IMPACT_MODEL` · Feature `impact_rating_agenda` · Cron (Latenz egal) · nur öffentliche Ratsdaten — ZDR nicht nötig

Qualität: KEINE — die Suite hat keine Goldwerte. Sie misst Kosten und Latenz an echten Wochen und zeigt die Spitzenpunkte zum Nebeneinanderlegen. 265 Fälle je Lauf.

| Modell | Läufe | Qualität | hart | p50 | p95 | ct/Aufruf | ct/Lauf | Ausfälle | ggü. heute |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| openai/gpt-5.6-luna | 2 | — | —, — | 9,4 s–9,6 s | 12,1 s–14,2 s | 0,108–0,197 | 1,73–3,14 | 0 | heutiges Modell nicht gemessen |

<details><summary>Nebenkennzahlen je Lauf</summary>

- openai/gpt-5.6-luna, Lauf 1: `{"wochen": 5, "bewertet": 265, "spitze_wie_regeln": 0}`
- openai/gpt-5.6-luna, Lauf 2: `{"wochen": 5, "bewertet": 265, "spitze_wie_regeln": 1}`

</details>

## Städtevergleich: taugt die Vorlage? (`cities-einordnung`)

Schalter `CITIES_CLASSIFY_MODEL` · Feature `cities_classify` · Cron (Latenz egal) · nur öffentliche Ratsdaten — ZDR nicht nötig

Qualität: „taugt / taugt nicht“ richtig — die eine Entscheidung, die das Produkt trifft. 45 Fälle je Lauf (ein Fall ≈ 2,2 Pp).

| Modell | Läufe | Qualität | hart | p50 | p95 | ct/Aufruf | ct/Lauf | Ausfälle | ggü. heute |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| deepseek/deepseek-v4-flash (heute) | 2 | 87,3 % ± 2,6 | —, — | 35,5 s–47,1 s | 341,7 s–773,2 s | 0,171–0,200 | 1,37–1,60 | 0 | Bezug |

<details><summary>Nebenkennzahlen je Lauf</summary>

- deepseek/deepseek-v4-flash, Lauf 1: `{"geliefert": 44, "transfer": 77.3, "feld": 86.4}`
- deepseek/deepseek-v4-flash, Lauf 2: `{"geliefert": 43, "transfer": 69.8, "feld": 76.7}`

</details>

## Städtevergleich: hat Oldenburg das schon? (`cities-fit`)

Schalter `CITIES_FIT_MODEL` · Feature `cities_fit` · Cron (Latenz egal) · nur öffentliche Ratsdaten — ZDR nicht nötig

Qualität: Status (drei Klassen) richtig. 40 Fälle je Lauf (ein Fall ≈ 2,5 Pp). Harte Befunde: erfundene Beleg-Kennungen + „vorhanden“ für etwas, das fehlt.

| Modell | Läufe | Qualität | hart | p50 | p95 | ct/Aufruf | ct/Lauf | Ausfälle | ggü. heute |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| deepseek/deepseek-v4-flash (heute) | 2 | 65,0 % ± 10,0 | 0, 0 | 9,9 s–10,1 s | 40,5 s–82,9 s | 0,044–0,059 | 1,76–2,36 | 0 | Bezug |

<details><summary>Nebenkennzahlen je Lauf</summary>

- deepseek/deepseek-v4-flash, Lauf 1: `{"geliefert": 40, "beleg_disziplin": 100.0}`
- deepseek/deepseek-v4-flash, Lauf 2: `{"geliefert": 40, "beleg_disziplin": 100.0}`

</details>

## Städtevergleich: was kostet die Idee? (`cities-aufwand`)

Schalter `CITIES_EFFORT_MODEL` · Feature `cities_effort` · Cron (Latenz egal) · nur öffentliche Ratsdaten — ZDR nicht nötig

Qualität: Aufwandsklasse richtig. 40 Fälle je Lauf (ein Fall ≈ 2,5 Pp). Harte Befunde: Adressat genannt, wo die Stadt selbst entscheidet.

| Modell | Läufe | Qualität | hart | p50 | p95 | ct/Aufruf | ct/Lauf | Ausfälle | ggü. heute |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| deepseek/deepseek-v4-flash (heute) | 2 | 87,5 % ± 10,0 | 0, 0 | 22,8 s–25,0 s | 108,0 s–880,8 s | 0,069–0,138 | 0,62–2,07 | 0 | Bezug |

<details><summary>Nebenkennzahlen je Lauf</summary>

- deepseek/deepseek-v4-flash, Lauf 1: `{"geliefert": 40, "adressat": 97.5}`
- deepseek/deepseek-v4-flash, Lauf 2: `{"geliefert": 40, "adressat": 97.5}`

</details>

## Städtevergleich: wollte der Rat die Idee? (`cities-richtung`)

Schalter `CITIES_STANCE_MODEL` · Feature `cities_stance` · Cron (Latenz egal) · nur öffentliche Ratsdaten — ZDR nicht nötig

Qualität: Richtung (for/against/review) richtig. 46 Fälle je Lauf (ein Fall ≈ 2,2 Pp). Harte Befunde: verfehlte `against`-Fälle — für sie gibt es den Annotator.

| Modell | Läufe | Qualität | hart | p50 | p95 | ct/Aufruf | ct/Lauf | Ausfälle | ggü. heute |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| deepseek/deepseek-v4-flash (heute) | 2 | 92,4 % ± 2,2 | 0, 0 | 7,1 s–10,3 s | 73,4 s–89,5 s | 0,021–0,025 | 0,99–1,15 | 0 | Bezug |

## Städtevergleich: warum ging es so aus? (`cities-begruendung`)

Schalter `CITIES_REASON_MODEL` · Feature `cities_reason` · Cron (Latenz egal) · nur öffentliche Ratsdaten — ZDR nicht nötig

Qualität: Abstimmungsergebnis richtig wiedergegeben (das `why` prüft nur eine Handdurchsicht). 36 Fälle je Lauf (ein Fall ≈ 2,8 Pp). Harte Befunde: erfundene Begründungen + Personennamen in der Ausgabe.

| Modell | Läufe | Qualität | hart | p50 | p95 | ct/Aufruf | ct/Lauf | Ausfälle | ggü. heute |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| deepseek/deepseek-v4-flash (heute) | 2 | 93,3 % ± 0,0 | 0, 0 | 14,2 s–18,0 s | 166,6 s–265,1 s | 0,047–0,092 | 1,70–3,32 | 0 | Bezug |

<details><summary>Nebenkennzahlen je Lauf</summary>

- deepseek/deepseek-v4-flash, Lauf 1: `{"fehlgeschlagen": 1, "begruendung_gefunden": 3}`
- deepseek/deepseek-v4-flash, Lauf 2: `{"fehlgeschlagen": 1, "begruendung_gefunden": 4}`

</details>

## Wortbeiträge aus Niederschriften (`wortbeitraege`)

Schalter `COUNCIL_WORTBEITRAG_MODEL` · Feature `speeches` · Cron (Latenz egal) · nur öffentliche Ratsdaten — ZDR nicht nötig

Qualität: F1 über die Beiträge je Person (Name UND Anzahl, gegen Protokoll-Muster und gespeicherte Extraktion; eval/run_speeches.py). 16 Fälle je Lauf (ein Fall ≈ 6,2 Pp). Harte Befunde: Redner*innen, deren Name im Abschnitt gar nicht vorkommt.

| Modell | Läufe | Qualität | hart | p50 | p95 | ct/Aufruf | ct/Lauf | Ausfälle | ggü. heute |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| google/gemini-3.5-flash-lite (heute) | 3 | 99,3 % ± 0,6 | 0, 0, 0 | 5,5 s–6,0 s | 7,4 s–10,5 s | 0,499–0,534 | 8,24–8,55 | 0 | Bezug |
| google/gemini-2.5-flash | 2 | 99,6 % ± 0,0 | 0, 0 | 9,2 s–9,6 s | 12,4 s–13,2 s | 0,563–0,570 | 9,01–9,12 | 0 | im Rauschen (+0,3 Pp, Streuung 0,6 Pp) |
| google/gemini-3.1-flash-lite | 2 | 99,1 % ± 0,2 | 0, 0 | 5,3 s–5,7 s | 10,9 s–11,3 s | 0,301–0,302 | 4,82–4,83 | 0 | im Rauschen (-0,2 Pp, Streuung 0,6 Pp) |
| google/gemini-3-flash-preview | 2 | 98,5 % ± 0,0 | 0, 0 | 10,9 s–11,5 s | 14,9 s–15,4 s | 0,635 | 10,16 | 0 | **schlechter** (-0,8 Pp) |

Ältere Läufe (anderer Prompt oder andere Fallliste, hier nicht verglichen): `eval/results/pruefstand/wortbeitraege/prompt-bis-2026-09-23/` (8).

<details><summary>Nebenkennzahlen je Lauf</summary>

- google/gemini-2.5-flash, Lauf 1: `{"precision": 0.9922, "recall": 1.0, "top_richtig": 1.0, "partei_ohne_beleg": 0, "fehlgeschlagen": 0}`
- google/gemini-2.5-flash, Lauf 2: `{"precision": 0.9922, "recall": 1.0, "top_richtig": 1.0, "partei_ohne_beleg": 0, "fehlgeschlagen": 0}`
- google/gemini-3-flash-preview, Lauf 1: `{"precision": 0.9733, "recall": 0.9961, "top_richtig": 1.0, "partei_ohne_beleg": 0, "fehlgeschlagen": 0}`
- google/gemini-3-flash-preview, Lauf 2: `{"precision": 0.9733, "recall": 0.9961, "top_richtig": 1.0, "partei_ohne_beleg": 0, "fehlgeschlagen": 0}`
- google/gemini-3.1-flash-lite, Lauf 1: `{"precision": 0.9882, "recall": 0.996, "top_richtig": 1.0, "partei_ohne_beleg": 0, "fehlgeschlagen": 0}`
- google/gemini-3.1-flash-lite, Lauf 2: `{"precision": 0.9882, "recall": 0.9921, "top_richtig": 1.0, "partei_ohne_beleg": 0, "fehlgeschlagen": 0}`
- google/gemini-3.5-flash-lite, Lauf 1: `{"precision": 0.9922, "recall": 1.0, "top_richtig": 0.9151, "partei_ohne_beleg": 0, "fehlgeschlagen": 0}`
- google/gemini-3.5-flash-lite, Lauf 2: `{"precision": 0.9808, "recall": 1.0, "top_richtig": 0.9318, "partei_ohne_beleg": 0, "fehlgeschlagen": 0}`
- google/gemini-3.5-flash-lite, Lauf 1: `{"precision": 0.9882, "recall": 0.996, "top_richtig": 0.9059, "partei_ohne_beleg": 0, "fehlgeschlagen": 0}`

</details>

## Live-Verfolgung: welcher TOP läuft (`live-verfolgung`)

Schalter `COUNCIL_LIVE_TRACKER_MODEL` · Feature `live_top_tracker` · live im Mitschnitt (Latenz = Verzug) · nur öffentliche Ratsdaten — ZDR nicht nötig

Qualität: Anteil der Fenster mit richtigem TOP am Fensterende — Aufruf, Block, Aussprache; von Hand gelesen (eval/run_live_tracker.py). 30 Fälle je Lauf (ein Fall ≈ 3,3 Pp). Harte Befunde: ein TOP, den es auf der Tagesordnung nicht gibt.

| Modell | Läufe | Qualität | hart | p50 | p95 | ct/Aufruf | ct/Lauf | Ausfälle | ggü. heute |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| google/gemini-3.5-flash-lite (heute) | 5 | 100,0 % ± 0,0 | 0, 0, 0, 0, 0 | 1,1 s–1,3 s | 1,6 s–2,2 s | 0,159–0,163 | 4,78–4,89 | 0 | Bezug |
| google/gemini-2.5-flash | 2 | 100,0 % ± 0,0 | 0, 0 | 1,8 s–1,9 s | 2,9 s | 0,163–0,177 | 4,90–5,31 | 0 | im Rauschen (+0,0 Pp, Streuung 0,0 Pp) |
| google/gemini-3-flash-preview | 2 | 100,0 % ± 0,0 | 0, 0 | 2,8 s–3,0 s | 4,7 s–4,9 s | 0,295–0,312 | 8,86–9,35 | 0 | im Rauschen (+0,0 Pp, Streuung 0,0 Pp) |
| google/gemini-3.1-flash-lite | 2 | 98,3 % ± 3,3 | 0, 0 | 2,2 s | 3,5 s–3,6 s | 0,126–0,131 | 3,79–3,92 | 0 | im Rauschen (-1,7 Pp, Streuung 3,3 Pp) |

<details><summary>Nebenkennzahlen je Lauf</summary>

- google/gemini-2.5-flash, Lauf 1: `{"je_art": {"aufruf": "11/11", "aussprache": "8/8", "block": "11/11"}}`
- google/gemini-2.5-flash, Lauf 2: `{"je_art": {"aufruf": "11/11", "aussprache": "8/8", "block": "11/11"}}`
- google/gemini-3-flash-preview, Lauf 1: `{"je_art": {"aufruf": "11/11", "aussprache": "8/8", "block": "11/11"}}`
- google/gemini-3-flash-preview, Lauf 2: `{"je_art": {"aufruf": "11/11", "aussprache": "8/8", "block": "11/11"}}`
- google/gemini-3.1-flash-lite, Lauf 1: `{"je_art": {"aufruf": "10/11", "aussprache": "8/8", "block": "11/11"}}`
- google/gemini-3.1-flash-lite, Lauf 2: `{"je_art": {"aufruf": "11/11", "aussprache": "8/8", "block": "11/11"}}`
- google/gemini-3.5-flash-lite, Lauf 1: `{"je_art": {"aufruf": "11/11", "aussprache": "8/8", "block": "11/11"}}`
- google/gemini-3.5-flash-lite, Lauf 2: `{"je_art": {"aufruf": "11/11", "aussprache": "8/8", "block": "11/11"}}`
- google/gemini-3.5-flash-lite, Lauf 1: `{"je_art": {"aufruf": "11/11", "aussprache": "8/8", "block": "11/11"}}`
- google/gemini-3.5-flash-lite, Lauf 2: `{"je_art": {"aufruf": "11/11", "aussprache": "8/8", "block": "11/11"}}`
- google/gemini-3.5-flash-lite, Lauf 1: `{"je_art": {"aufruf": "11/11", "aussprache": "8/8", "block": "11/11"}}`

</details>

## Abstimmungsergebnisse aus dem Sitzungsvideo (`video-ergebnisse`)

Schalter `COUNCIL_VIDEO_MODEL` · Feature `video_results` · Cron (Latenz egal) · nur öffentliche Ratsdaten — ZDR nicht nötig

Qualität: Anteil der protokollierten Ergebnisse, die der ganze strenge Weg (zwei Durchläufe, Beleg, Konsens) richtig ausgibt — gegen die Niederschrift. 61 Fälle je Lauf (ein Fall ≈ 1,6 Pp). Harte Befunde: falsche Ergebnisse und falsche Zusätze („einstimmig“ statt „mehrheitlich“).

| Modell | Läufe | Qualität | hart | p50 | p95 | ct/Aufruf | ct/Lauf | Ausfälle | ggü. heute |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| openai/gpt-5.6-luna (heute) | 2 | 89,3 % ± 1,6 | 0, 0 | 6,6 s | 20,3 s–22,6 s | 0,115–0,117 | 3,44–3,53 | 0 | Bezug |
| openai/gpt-6-luna [flex] | 2 | 88,5 % ± 0,0 | 0, 0 | 10,4 s–12,8 s | 37,6 s–46,3 s | 0,034–0,086 | 1,02–2,57 | 0 | im Rauschen (-0,8 Pp, Streuung 1,6 Pp) |
| openai/gpt-6-luna | 2 | 85,2 % ± 3,3 | 0, 0 | 6,8 s–7,7 s | 21,0 s–22,3 s | 0,068–0,172 | 2,05–5,16 | 0 | **schlechter** (-4,1 Pp) |

<details><summary>Nebenkennzahlen je Lauf</summary>

- openai/gpt-5.6-luna, Lauf 1: `{"verpasst": 7, "ungeprueft": 9, "zusatz_falsch": []}`
- openai/gpt-5.6-luna, Lauf 2: `{"verpasst": 6, "ungeprueft": 9, "zusatz_falsch": []}`
- openai/gpt-6-luna, Lauf 1: `{"verpasst": 10, "ungeprueft": 8, "zusatz_falsch": []}`
- openai/gpt-6-luna, Lauf 2: `{"verpasst": 8, "ungeprueft": 9, "zusatz_falsch": []}`
- openai/gpt-6-luna [flex], Lauf 1: `{"verpasst": 7, "ungeprueft": 9, "zusatz_falsch": []}`
- openai/gpt-6-luna [flex], Lauf 2: `{"verpasst": 7, "ungeprueft": 9, "zusatz_falsch": []}`

</details>

## Social-Kartentext (`social-text`)

Schalter `COUNCIL_SOCIAL_MODEL` · Feature `social_card_text` · Cron (Latenz egal) · nur öffentliche Ratsdaten — ZDR nicht nötig

Qualität: Anteil der Punkte, deren ERSTER Entwurf die Netze des Betriebs besteht (keine Zahl ohne Beleg, keine Wertung, kein Ergebnis, Länge, JSON). 20 Fälle je Lauf (ein Fall ≈ 5,0 Pp). Harte Befunde: inhaltliche Mängel: Zahl ohne Beleg, Wertung, vorweggenommenes Ergebnis.

| Modell | Läufe | Qualität | hart | p50 | p95 | ct/Aufruf | ct/Lauf | Ausfälle | ggü. heute |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| openai/gpt-6-luna (heute) | 3 | 91,5 % ± 4,4 | 2, 1, 1 | 4,7 s–5,8 s | 11,8 s–16,5 s | 0,025–0,073 | 0,45–1,46 | 0 | Bezug |
| openai/gpt-6-luna [flex] | 2 | 92,5 % ± 5,0 | 1, 1 | 9,8 s–10,1 s | 24,8 s–35,3 s | 0,018–0,036 | 0,36–0,72 | 0 | im Rauschen (+1,0 Pp, Streuung 5,0 Pp) |
| openai/gpt-5.6-luna | 2 | 90,0 % ± 10,0 | 1, 3 | 6,0 s–6,4 s | 8,7 s–11,7 s | 0,075–0,089 | 1,51–1,78 | 0 | im Rauschen (-1,5 Pp, Streuung 10,0 Pp) |

<details><summary>Nebenkennzahlen je Lauf</summary>

- openai/gpt-5.6-luna, Lauf 1: `{"zu_lang": 0, "fehlgeschlagen": 0}`
- openai/gpt-5.6-luna, Lauf 2: `{"zu_lang": 0, "fehlgeschlagen": 0}`
- openai/gpt-6-luna, Lauf 1: `{"zu_lang": 0, "fehlgeschlagen": 0}`
- openai/gpt-6-luna, Lauf 2: `{"zu_lang": 1, "fehlgeschlagen": 0}`
- openai/gpt-6-luna, Lauf 1: `{"zu_lang": 0, "fehlgeschlagen": 0}`
- openai/gpt-6-luna [flex], Lauf 1: `{"zu_lang": 0, "fehlgeschlagen": 0}`
- openai/gpt-6-luna [flex], Lauf 2: `{"zu_lang": 1, "fehlgeschlagen": 0}`

</details>

## Kritiker der Social-Karten (`kritiker`)

Schalter `COUNCIL_KRITIKER_MODEL` · Feature `social_critic` · Cron (Latenz egal) · nur öffentliche Ratsdaten — ZDR nicht nötig

Qualität: Anteil richtig: gedeckt / nicht gedeckt, an 9 belegten und 9 gezielt verfälschten Sätzen. 18 Fälle je Lauf (ein Fall ≈ 5,6 Pp). Harte Befunde: verfälschte Sätze, die als gedeckt durchgehen.

| Modell | Läufe | Qualität | hart | p50 | p95 | ct/Aufruf | ct/Lauf | Ausfälle | ggü. heute |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| openai/gpt-6-luna (heute) | 3 | 96,3 % ± 5,6 | 0, 0, 0 | 3,1 s–4,7 s | 6,3 s–13,0 s | 0,022–0,047 | 0,30–0,85 | 0 | Bezug |
| openai/gpt-6-luna [flex] | 2 | 100,0 % ± 0,0 | 0, 0 | 3,6 s–3,9 s | 8,0 s–8,4 s | 0,013–0,023 | 0,24–0,42 | 0 | im Rauschen (+3,7 Pp, Streuung 5,6 Pp) |
| openai/gpt-5.6-luna | 2 | 94,4 % ± 11,1 | 1, 0 | 4,4 s–4,9 s | 8,5 s–9,7 s | 0,051–0,061 | 0,93–1,10 | 0 | im Rauschen (-1,8 Pp, Streuung 11,1 Pp) |

<details><summary>Nebenkennzahlen je Lauf</summary>

- openai/gpt-5.6-luna, Lauf 1: `{"zu_unrecht_verworfen": 1, "ausfaelle": 0}`
- openai/gpt-5.6-luna, Lauf 2: `{"zu_unrecht_verworfen": 0, "ausfaelle": 0}`
- openai/gpt-6-luna, Lauf 1: `{"zu_unrecht_verworfen": 1, "ausfaelle": 0}`
- openai/gpt-6-luna, Lauf 2: `{"zu_unrecht_verworfen": 1, "ausfaelle": 0}`
- openai/gpt-6-luna, Lauf 1: `{"zu_unrecht_verworfen": 0, "ausfaelle": 0}`
- openai/gpt-6-luna [flex], Lauf 1: `{"zu_unrecht_verworfen": 0, "ausfaelle": 0}`
- openai/gpt-6-luna [flex], Lauf 2: `{"zu_unrecht_verworfen": 0, "ausfaelle": 0}`

</details>

## Mein Viertel: liegt der Beschluss hier? (`viertel`)

Schalter `COUNCIL_DISTRICT_MODEL` · Feature `district_projects` · Cron (Latenz egal) · nur öffentliche Ratsdaten — ZDR nicht nötig

Qualität: Anteil richtig „im Viertel ja/nein“ (Richter-Stufe). Erwartung = gespeichertes Urteil von GPT-5.6 Luna, jeder Fall von Hand nachgelesen, Widersprüche raus. 30 Fälle je Lauf (ein Fall ≈ 3,3 Pp). Harte Befunde: „im Viertel“ für einen Beschluss, der woanders liegt oder stadtweit gilt.

| Modell | Läufe | Qualität | hart | p50 | p95 | ct/Aufruf | ct/Lauf | Ausfälle | ggü. heute |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| openai/gpt-6-luna (heute) | 3 | 92,2 % ± 3,3 | 0, 0, 1 | 3,7 s–7,7 s | 8,2 s–10,6 s | 0,036–0,054 | 0,25–0,38 | 0 | Bezug |
| openai/gpt-5.6-luna | 2 | 95,0 % ± 3,3 | 0, 0 | 7,9 s–8,9 s | 12,8 s | 0,090–0,132 | 0,63–0,93 | 0 | im Rauschen (+2,8 Pp, Streuung 3,3 Pp) |
| openai/gpt-6-luna [flex] | 2 | 95,0 % ± 3,3 | 0, 0 | 11,8 s–15,0 s | 16,0 s–18,5 s | 0,017–0,028 | 0,12–0,19 | 0 | im Rauschen (+2,8 Pp, Streuung 3,3 Pp) |

<details><summary>Nebenkennzahlen je Lauf</summary>

- openai/gpt-5.6-luna, Lauf 1: `{"verpasst": 1, "ohne_urteil": 0, "fehler": []}`
- openai/gpt-5.6-luna, Lauf 2: `{"verpasst": 2, "ohne_urteil": 0, "fehler": []}`
- openai/gpt-6-luna, Lauf 1: `{"verpasst": 2, "ohne_urteil": 0, "fehler": []}`
- openai/gpt-6-luna, Lauf 2: `{"verpasst": 2, "ohne_urteil": 0, "fehler": []}`
- openai/gpt-6-luna, Lauf 1: `{"verpasst": 2, "ohne_urteil": 0, "fehler": []}`
- openai/gpt-6-luna [flex], Lauf 1: `{"verpasst": 1, "ohne_urteil": 0, "fehler": []}`
- openai/gpt-6-luna [flex], Lauf 2: `{"verpasst": 2, "ohne_urteil": 0, "fehler": []}`

</details>

## Nicht lokal gemessen

- `ki-frage`: nur Server: braucht die Embeddings der Ratsdatenbank (lokal 0 Zeilen in council_embeddings)
- `transkription`: kein Sitzungs-Audio: braucht Stücke <name>.mp3 mit Referenz <name>.txt in /Users/tim/.cache/ratslotse/stt/<ksinr>/ — die Aufbewahrung (council/stt_retain.py) legt sie erst nach der nächsten Ratssitzung mit Livestream an, die Referenz kommt danach aus `python eval/stt_referenz.py <ksinr>` (s. eval/run_stt.py)

## Features ohne Suite

Diese Feature-Namen rufen ein Modell, haben aber keine Eval — ein Modellwechsel dort ist ungemessen (Plan P2):

`attachment_ocr`, `cities_cluster_check`, `cities_evidence_terms`, `cities_idea_fit`, `daily_find_story`, `deep_decomposition`, `deep_report`, `entity_description`, `entity_duplicates`, `entity_ner`, `field_recap`, `goal_rating`, `interest_rating`, `minutes_extraction`, `party_opinions`, `qa_query_expansion`, `qa_simple`, `quality_judge`, `quiz_generation`, `quiz_verify`, `simple_summary`, `topic_auto_description`, `topic_classification`, `vagueness_check`
