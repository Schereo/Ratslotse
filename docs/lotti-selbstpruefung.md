# Lottis Selbstprüfung — Kalibrierung und Entscheidung

Stand 24.09.2026, nach L1 (#1547, Alltagssprache) und L2 (#1542,
Erklärtexte). Code: `council/self_check.py`, Schalter `lotti-selbstpruefung`
(`kern/features.py`), Anteil `COUNCIL_ASSISTANT_PRUEFER_ANTEIL` (Vorgabe 0,1).

**Entscheidung: eine stille Stichprobe.** Ein Zehntel der Erklärungen wird
NACH der Antwort geprüft: eine Hintergrund-Aufgabe der Antwort, der Strom ist
dann schon zu. Niemand wartet, nichts wird angezeigt, nichts ersetzt. Das
Urteil landet in `assistant_checks` und im Admin-Reiter „Lotti“ (Anteil
beanstandet je Seite, häufigste Gründe).

Die erste Fassung prüfte VOR der Anzeige, schrieb bei einem Mangel einmal neu
und zeigte „Warum neu?“ im Fenster. Sie steht in Commit `ca759f9c` und ist
gemessen worden. Sie hob die ok-Quote nicht (Tabelle unten), deshalb Tims
zweite Regel: die Stichprobe.

## Stufe 1 (ohne Modell)

Jede Zahl steht im Kontext (`council/fakten_abgleich.py`, dieselbe Logik wie
die Fakten-Eval), unter ihrem Jahr; keine Wertung in eigener Stimme; kein
Prompt-Rest.

| Satz | Antworten | angeschlagen |
|---|---:|---:|
| Fakten-Eval 23.09., `ok` | 101 | 0 |
| Fakten-Eval 23.09., `modell_*` | 15 | 0 |
| Laienfragen 24.09. (vor L1/L2), beide Läufe | 72 | 0 |
| Fakten-Eval 24.09. nach L1+L2, Lotti-Fälle (inkl. `hh-laien-*`) | 120 | 0 |

Kein Fehlalarm, aber auch kein Treffer: GPT-6 Luna erfindet keine Zahlen, sie
lässt eher etwas weg.

## Stufe 2 (Prüfer)

Die Treffer-Spalte zählt bekannte Mängel, die der Prüfer beanstandet; die
Fehlalarm-Spalte gute Antworten, die er beanstandet. „Nur unverständlich“ zählt
als gut (`NOTE_ONLY`). Die Gegenprobe „Absage“ setzt in jeden guten Fall, dessen
Goldfakt im Kontext steht, die Antwort „Das geht aus den Angaben hier nicht
hervor.“ — die MUSS er beanstanden (`eval/run_selbstpruefung.py absage`).

**Vor L1+L2** (Fakten-Lauf 23.09., 36 Laienfragen vom Befund):

| Prüfer | Prompt | Satz | Treffer | Fehlalarme | p50 | je Prüfung |
|---|---|---|---:|---:|---:|---:|
| Gemini 3.5 Flash Lite | 1 | Laien, „zu vorsichtig“ | 0/7 | 1/17 | 0,8 s | 0,14 ct |
| Gemini 3 Flash | 1 | Laien | 4/7 | 2/17 | 1,5 s | 0,23 ct |
| Gemini 3 Flash | 1 | Fakten | 0/14 | 1/101 | 1,4 s | 0,24 ct |
| Gemini 3 Flash | 2 | Laien | 1/7 | 1/17 | 1,4 s | 0,23 ct |
| Gemini 3.5 Flash | 2 | Stichprobe 15+15 | 1/15 | 1/15 | 7,6–8,2 s | 1,8 ct |
| Gemini 3.8 Flash | 2 | Stichprobe 15+15 | 0/15 | 0/15 | 3,9–4,6 s | 0,5 ct |

**Nach L1+L2** (Fakten-Lauf 24.09., 178 Haushaltsfälle; Lotti-Fälle ohne
Kontextfehler, darunter `hh-laien-01…36`), immer Gemini 3 Flash:

| Prompt | Treffer | Fehlalarme | davon Laienfragen | Absage-Gegenprobe | p50 | je Prüfung |
|---|---:|---:|---:|---:|---:|---:|
| 2 | 1/9 | 8/111 | 5/33 | 102/103 | 1,6 s | 0,30 ct |
| 3 | 0/9 | 3/111 | – | 102/103 | 1,5 s | 0,29 ct |
| **3, final** (Satz zur Rolle angepasst) | 0/9 | 5/111 | 3/33 | 102/103 | 1,4 s | 0,29 ct |

Prompt 2 → 3: „Beantwortet die Antwort die Frage schon mit einer belegten
Zahl, ist eine WEITERE Zahl (ein anderes Jahr, eine andere Zählweise, Plan
statt Ergebnis) kein Mangel.“ Nach L1 trägt der Kontext mehr Zahlen, und der
Prüfer vermisste jede davon. Die Frage, ob er „geht nicht hervor“-Antworten
durchgehen lässt, obwohl der Kontext die Zahl trägt, beantwortet die
Gegenprobe: **nein, 102 von 103 beanstandet.** Die 9 „bekannten Mängel“ nach
L1+L2 sind dagegen fast alle Feinheiten der Eval-Regeln (ein Wort wie
„Schule“ statt „Schul-Hardware“, eine zweite Goldzahl) — dort widerspricht
der Prüfer zu Recht.

## Ende zu Ende (Fakten-Eval, 178 Haushaltsfälle, je ein Lauf, Fassung MIT Anzeige)

| | ohne | mit Prüfung vor der Anzeige |
|---|---:|---:|
| ok | 163 (91,6 %) | 163 (91,6 %) |
| Lotti geprüft / beanstandet / ersetzt | – | 121 / 4 / 4 |
| davon besser / gleich / schlechter | – | 1 / 3 / 0 |
| p50 / p95 (Lottis Erklärungen) | 5,0 s / 8,4 s | 6,7 s / 13,1 s |
| Kosten des Laufs | 0,20 $ | 0,49 $ |
| Prüfer je Erklärung | – | 0,28 ct |

Vor L1+L2 (121 Lotti-Fälle): 116 geprüft, 0 beanstandet, 0 ersetzt; ok 104
gegen 110 — reine Streuung zwischen zwei Luna-Läufen.

**Tims Schwelle** war: mindestens 3 Fälle besser, keiner schlechter, Latenz
vertretbar. Erreicht: 1 besser (`hh-vergleich-steuerkraft-lotti`), bei
+1,7 s im Median, +4,7 s im p95 und dem 2,5-Fachen der Kosten. Deshalb die
Stichprobe.

## Was die Stichprobe kostet

Bei 10 % rund 0,03 Cent je Erklärung im Mittel (0,28 Cent je geprüfter). Die
Person wartet nicht: Der Strom ist beim Client, bevor die Prüfung beginnt
(gemessen: `done` und Stromende bei 5,72 s, die Prüfung danach 1,4–3,3 s).

## Nachmessen

```bash
python eval/run_fakten.py --modell openai/gpt-6-luna --faelle eval/cases_fakten_haushalt.json
python eval/run_selbstpruefung.py fakten ~/.cache/ratslotse/fakten-mitschnitt/<lauf>
python eval/run_selbstpruefung.py absage ~/.cache/ratslotse/fakten-mitschnitt/<lauf>
```

Die Fakten-Eval schaltet die Stichprobe in ihrem Mess-Backend ab; sie ändert
an den Antworten nichts und kostete nur.

## Datenschutz

Der Prüfer läuft bei Google über OpenRouter **mit** Zero Data Retention
(`assistant_check` steht nicht in `ZDR_VERZICHT`, `tests/test_self_check.py`).
Gespeichert wird je geprüfter Antwort in `assistant_checks` (Konten-Datenbank,
mit dem Konto gelöscht): Urteil, Stufe, Kategorien, kurze Gründe ohne Zitat der
Frage, Seite, Modell, Dauer, Kosten. Frage und Antwort nur mit der
Einwilligung in die Gesprächsspeicherung.

Die Datenschutzerklärung ist **nicht** geändert: Solange der Schalter auf Prod
aus ist, findet die Verarbeitung dort nicht statt. Vor dem Einschalten braucht
sie einen Satz — Vorschlag für den Absatz „KI-Verarbeitung (OpenRouter)“:

> Einen Teil der Antworten von Lotti prüft danach ein Modell von Google auf
> ihre Qualität (ebenfalls nur bei Anbietern mit Zero-Data-Retention-Zusage).
> Das Ergebnis speichern wir an deinem Konto — ohne deine Frage, es sei denn,
> du hast dem Speichern deiner Gespräche zugestimmt.
