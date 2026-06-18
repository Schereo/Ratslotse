# Modellvergleich: NWZ-Themen-Klassifizierung

*Aktualisiert: 2026-06-18 (nach Implementierung der Fixes) · Korpus: 30 NWZ-Ausgaben (19.05.-18.06.2026), 2.631 Artikel · 7 Themen von Nutzer 463107821 (ohne 'Stadtteile') · Ground Truth: 22 echte True Positives*

## Was sich geaendert hat (Fixes in `nwz/classify.py`)

Dieser Re-Run nutzt vier Verbesserungen ggue. dem ersten Vergleich:
1. **Text-Cap angehoben** (900->2400 / Verify 1500->3000) — vergrabene Meldungen nicht mehr abgeschnitten.
2. **Container-Split** — `Kurz notiert`/`Titelseite` werden an `<div class='h3'>` in Einzelmeldungen zerlegt, Treffer auf die Original-refid zurueckgemappt + dedupliziert.
3. **Robustes Themen-Mapping** — umformulierte Themennamen werden aufgeloest (exakt->normalisiert->Teilstring->fuzzy) statt als `topic_id=0` zu verwaisen.
4. **Rubrik-Filter** — klar nicht-lokale Rubriken (Sport, Welt, Bundespolitik, Lifestyle ...) werden vor der Klassifizierung uebersprungen (~52% der Artikel).

## Scorecard gegen die Ground Truth (NACH Fixes)

| Modell | Treffer | TP | FP | Precision | Recall | F1 |
|---|--:|--:|--:|--:|--:|--:|
| gpt-4o | 27 | 15 | 12 | 0.556 | 0.682 | 0.612 |
| deepseek-v4-pro | 35 | 16 | 19 | 0.457 | 0.727 | 0.561 |
| deepseek-v4-flash | 30 | 14 | 16 | 0.467 | 0.636 | 0.538 |

## Vorher -> Nachher (Effekt der Fixes)

| Modell | Treffer | Recall | F1 |
|---|---|---|---|
| gpt-4o | 9 -> 27 | 0.227 -> **0.682** | 0.323 -> **0.612** |
| deepseek-v4-pro | 19 -> 35 | 0.455 -> **0.727** | 0.488 -> **0.561** |
| deepseek-v4-flash | 16 -> 30 | 0.364 -> **0.636** | 0.421 -> **0.538** |

> Recall steigt bei allen Modellen stark (gpt-4o 0,23->0,68; pro 0,46->0,73; flash 0,36->0,64), Precision bleibt ~stabil. `topic_id=0`-Fehlablagen: 0 (vorher 1-2 je deepseek-Lauf).

## Robustheit

gpt-4o und flash verarbeiteten alle 30 Ausgaben. **deepseek-pro fiel auf Ausgabe 23.05. mit leerer Antwort aus** (Reasoning-Null-Content auf einem 169-Artikel-Heft) — dort liegen **5 Gold-Paare**. Auf den erreichbaren Ausgaben fand pro **16/17 (0,94)**; operativ kostete der Ausfall 5 moegliche Treffer. Das bleibt das wiederkehrende Zuverlaessigkeitsrisiko der deepseek-Modelle.

## Kosten (aktuelle OpenRouter-Preise) & Effizienz

| Modell | Kosten / 30 Ausg. | vorher | $ pro richtigem Treffer |
|---|--:|--:|--:|
| gpt-4o | $1.8281 | $1.6962 | $0.1219 |
| deepseek-v4-pro | $0.4338 | $0.3952 | $0.0271 |
| deepseek-v4-flash | $0.0850 | $0.0778 | $0.0061 |

## Token-Verbrauch (30 Ausgaben, nach Fixes)

| Modell | Prompt-Tok | Completion-Tok (inkl. Reasoning) | Verify-Tok |
|---|--:|--:|--:|
| gpt-4o | 700,787 | 6,996 | 40,049 |
| deepseek-v4-pro | 808,472 | 89,131 | 29,829 |
| deepseek-v4-flash | 808,185 | 41,715 | 30,621 |

## Echte True-Positive-Artikel pro Thema (Abdeckung nach Fixes)

Legende: x = gefunden, - = verpasst.


### Fliegerhorststraße - 2 TP

| Datum | Artikel | 4o | pro | flash |
|---|---|:--:|:--:|:--:|
| 2026-05-23 | Ludwig Freytag plant große Erweiterung | - | - | x |
| 2026-06-11 | Landvermessung für die neue Verbindungsstraße | x | x | - |

### Bebauungsplan 851 - 1 TP

| Datum | Artikel | 4o | pro | flash |
|---|---|:--:|:--:|:--:|
| 2026-05-23 | Weg frei für Wohnquartier | x | - | x |

### IQON - 2 TP

| Datum | Artikel | 4o | pro | flash |
|---|---|:--:|:--:|:--:|
| 2026-05-26 | Aus Zusammenarbeit entsteht Geschwindigkeit | x | x | x |
| 2026-06-03 | Bildungsangebote für die Stadtbevölkerung in der Innenstadt | - | - | - |

### Wohnheim Tegelbusch - 0 TP

*(keine echten Treffer im Korpus)*

### Die Grünen - 8 TP

| Datum | Artikel | 4o | pro | flash |
|---|---|:--:|:--:|:--:|
| 2026-05-23 | Ludwig Freytag plant große Erweiterung | - | - | x |
| 2026-05-23 | Weg frei für Wohnquartier | x | - | x |
| 2026-05-29 | Mehrheit für Stadionbau steht vor der Ratssitzung | x | x | x |
| 2026-06-02 | Stadion-Bau: Mehrheit votiert für Vergabe von Millionen-Auftrag | x | x | x |
| 2026-06-03 | Mit Handballergebnis zum Fußballstadion | x | x | x |
| 2026-06-11 | Landvermessung für die neue Verbindungsstraße | x | x | - |
| 2026-06-15 | Grüne stellen Kandidaten für Wahl auf | x | x | x |
| 2026-06-15 | Gesellschaft – Mitdenken, mitreden, mitgestalten | - | x | x |

### kommunalwahl 2026 - 4 TP

| Datum | Artikel | 4o | pro | flash |
|---|---|:--:|:--:|:--:|
| 2026-05-23 | 50 Menschen – 50 Visionen: Oldenburg denkt Zukunft neu | - | - | x |
| 2026-06-13 | Michael Stille kandidiert erneut | x | x | - |
| 2026-06-13 | (ohne Titel) | - | x | - |
| 2026-06-15 | Grüne stellen Kandidaten für Wahl auf | x | x | x |

### etwas über die Oberbürgermeisterkandidaten - 5 TP

| Datum | Artikel | 4o | pro | flash |
|---|---|:--:|:--:|:--:|
| 2026-05-28 | (ohne Titel) | x | x | x |
| 2026-06-12 | (ohne Titel) | x | x | x |
| 2026-06-13 | Michael Stille kandidiert erneut | x | x | - |
| 2026-06-13 | (ohne Titel) | - | x | - |
| 2026-06-16 | (ohne Titel) | x | x | - |

## Von ALLEN drei verpasst (1 von 22, vorher 12)

| Thema | Datum | Artikel |
|---|---|---|
| IQON | 2026-06-03 | Bildungsangebote für die Stadtbevölkerung in der Innenstadt |

## Kernbefunde (nach Fixes)

1. **Die Fixes wirken:** Recall-Verdopplung bei gpt-4o, deutliche Gewinne bei allen; Themen-Fehlablage eliminiert.
2. **gpt-4o** hat jetzt das beste F1 (0,61) und die beste Precision, ist aber weiter mit Abstand am teuersten (~$0,12/TP).
3. **deepseek-pro** hat den hoechsten Recall (0,73) trotz eines Ausgaben-Ausfalls, zu ~1/4 der Kosten von gpt-4o.
4. **deepseek-flash** liefert ~88% des gpt-4o-F1 zu ~1/20 der Kosten ($0,006/TP) — bestes Preis-Leistungs-Verhaeltnis.
5. **Verbleibendes Problem = Precision** (FP), v.a. das Keyword-Thema `Die Gruenen`. Naechster Hebel: Prompt schaerfen (Partei muss handelndes Subjekt sein).
6. **deepseek-Robustheit:** sporadische Null-Content-Antworten auf grossen Heften; vor Produktiveinsatz Retry/Fallback noetig.

---
*Ground Truth via Dual-Judge-Workflow (70 Agents). Hinweis: einzelne Gold-Urteile sind grosszuegige Grenzfaelle; Kernaussagen davon unabhaengig robust.*
