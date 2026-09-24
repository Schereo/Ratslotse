# Lottis Selbstprüfung — Kalibrierung

Stand 24.09.2026. Code: `council/self_check.py`, Schalter `lotti-selbstpruefung`
(`kern/features.py`), Kalibrierung: `eval/run_selbstpruefung.py`, Ende-zu-Ende:
`eval/run_fakten.py --nur lotti --selbstpruefung`.

**Ergebnis: Der Schalter bleibt auf Prod aus.** Stufe 1 (ohne Modell) ist
sauber, aber sie findet in den heutigen Antworten nichts — GPT-6 Luna erfindet
keine Zahlen. Der Prüfer (Stufe 2) findet die bekannten Mängel nicht: Er hält
die „zu vorsichtigen“ Antworten für richtig, weil Lottis Regeln sie verlangen
(„Erkläre NUR, was oben steht“), und die Auslassungen der Fakten-Eval für
Nebensache. Ein Lauf der Fakten-Eval mit Selbstprüfung hat keine einzige
Antwort ersetzt.

## Die Sätze

- **Fakten-Eval, Lottis Fälle** — `ok` gilt als gut, `modell_*` als mangelhaft;
  Kontextfehler bleiben draußen (der Prüfer sieht nur den Prompt).
- **36 Laienfragen** (Befund 24.09.2026, `eval/cases_selbstpruefung_laien.json`):
  17 gut, 7 „zu vorsichtig“ (B — hier SOLL der Prüfer anschlagen), 9 „Daten
  fehlten im Kontext“ (A — der Prüfer kann es nicht wissen; gezählt wird nur,
  wie oft er anschlägt), 3 ohne Urteil.

## Stufe 1 (ohne Modell)

Jede Zahl steht im Kontext (`council/fakten_abgleich.py`, dieselbe Logik wie
die Eval), unter ihrem Jahr; keine Wertung in eigener Stimme; kein Prompt-Rest.

| Satz | Antworten | angeschlagen |
|---|---:|---:|
| Fakten-Eval 23.09., `ok` | 101 | 0 |
| Fakten-Eval 23.09., `modell_*` | 15 | 0 |
| Laienfragen, beide Läufe | 72 | 0 |

Kein Fehlalarm — aber auch kein Treffer: Die Modellfehler von heute sind
Auslassungen, keine erfundenen Zahlen.

## Stufe 2 (Prüfer)

Trefferquote = bekannte Mängel, die er beanstandet; Fehlalarme = gute
Antworten, die er beanstandet. „Nur unverständlich“ löst seit der Kalibrierung
kein Neuschreiben aus (`NOTE_ONLY`) und zählt hier als gut.

| Prüfer | Prompt | Satz | Treffer | Fehlalarme | A beanstandet | p50 | je Prüfung |
|---|---|---|---:|---:|---:|---:|---:|
| Gemini 3.5 Flash Lite | 1 | Laien (33) | 0/7 | 1/17 | 0/9 | 0,8 s | 0,14 ct |
| Gemini 3 Flash | 1 | Laien (33) | 4/7 | 2/17 | 4/9 | 1,5 s | 0,23 ct |
| Gemini 3 Flash | 1 | Fakten (115) | 0/14 | 1/101 | — | 1,4 s | 0,24 ct |
| Gemini 3 Flash | **2** | Laien (33) | 1/7 | 1/17 | 2/9 | 1,4 s | 0,23 ct |
| Gemini 3.5 Flash | 2 | Stichprobe Laien (15) | 1/7 | 1/8 | — | 8,2 s | 1,88 ct |
| Gemini 3.5 Flash | 2 | Stichprobe Fakten (15) | 0/8 | 0/7 | — | 7,6 s | 1,75 ct |
| Gemini 3.8 Flash | 2 | Stichprobe Laien (15) | 0/7 | 0/8 | — | 4,6 s | 0,50 ct |
| Gemini 3.8 Flash | 2 | Stichprobe Fakten (15) | 0/8 | 0/7 | — | 3,9 s | 0,48 ct |

Prompt 1 → 2: Die Fehlalarme von Prompt 1 hatten zwei Ursachen, die Prompt 2
ausräumt — der Prüfer vermisste die Zeile `WEITER: …` (die Ratslotse vor der
Anzeige entfernt) und beanstandete Stilfragen (ein Satz zu viel,
Nachkommastellen). Dafür fand er danach auch weniger. Gemini 3.5 und 3.8
Flash liefen nach Tims Regel nur als Stichprobe: Sie fanden nicht mehr und
sind zwei- bis achtmal teurer und drei- bis sechsmal langsamer.

## Ende zu Ende (Fakten-Eval, 121 Lotti-Fälle, zwei Läufe gleichzeitig)

| | ohne | mit Selbstprüfung |
|---|---:|---:|
| ok | 104 (86,0 %) | 110 (90,9 %) |
| geprüft / beanstandet / ersetzt | — | 116 / 0 / 0 |
| p50 / p95 (nur Erklärungen) | 3,7 s / 8,8 s | 5,5 s / 10,5 s |
| Kosten je Antwort | 0,07 ct | 0,26 ct |

**Die sechs Punkte ok-Quote sind Streuung, kein Gewinn:** Keine Antwort wurde
ersetzt, der Unterschied kommt allein daher, dass GPT-6 Luna in zwei Läufen
verschieden antwortet. Die Selbstprüfung kostete hier +1,8 s im Median und
knapp das Vierfache je Antwort, ohne eine einzige Antwort zu ändern.

## Was hilft stattdessen

Die bekannten Schwächen liegen vor dem Modell: Daten, die nicht in den Kontext
kommen (Befund A), und Regeln, die eine Einordnung verbieten (Befund B). Ein
Prüfer, der an denselben Kontext und dieselben Regeln gebunden ist, kann beides
nicht sehen. Wieder messen, wenn die Kontext- und Regel-Arbeit (L1/L2) gemergt
ist; die Befehle stehen oben.

## Datenschutz

Der Prüfer läuft bei Google über OpenRouter **mit** Zero Data Retention
(`assistant_check` steht nicht in `ZDR_VERZICHT`, `tests/test_self_check.py`).
Gespeichert wird je geprüfter Antwort in `assistant_checks` (Konten-Datenbank,
mit dem Konto gelöscht): Urteil, Stufe, Kategorien, kurze Gründe ohne Zitat der
Frage, Seite, Modell, ob neu geschrieben wurde, Dauer, Kosten. Frage und beide
Fassungen nur mit der Einwilligung in die Gesprächsspeicherung.

Die Datenschutzerklärung ist **nicht** geändert: Solange der Schalter auf Prod
aus ist, findet die Verarbeitung dort nicht statt. Vor dem Einschalten braucht
sie einen Satz — Vorschlag für den Absatz „KI-Verarbeitung (OpenRouter)“:

> Ist die Qualitätsprüfung eingeschaltet, prüft ein Modell von Google
> Lottis Antwort vor der Anzeige (ebenfalls nur bei Anbietern mit
> Zero-Data-Retention-Zusage). Das Ergebnis der Prüfung speichern wir an
> deinem Konto — ohne deine Frage, es sei denn, du hast dem Speichern deiner
> Gespräche zugestimmt.
