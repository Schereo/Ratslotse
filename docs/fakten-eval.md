# Fakten-Eval: Lotti und Frag den Rat

**Auftrag (Tim, 23.09.2026):** „Die Haushaltsfragen werden sehr, sehr wichtig
werden in nächster Zeit. […] Wenn wir im Kontext schon Mist haben, kann das
beste Modell ja nichts Gutes draus machen.“ Diese Eval misst deshalb je Fall
**zwei Dinge getrennt**, ohne ein Modell als Richter:

1. **Kontext:** Stand jeder Goldfakt im Prompt, den das Modell bekam — und
   zwar unter dem **richtigen Jahr** (und, wo angegeben, der richtigen
   Bezeichnung)? Fehlt er, ist der Fall ein **Kontextfehler**, egal was das
   Modell antwortet.
2. **Antwort:** Nennt die Antwort den Goldfakt (Rundung „rund 337 Mio.“
   zählt), ohne Verwechslung (Vorjahr, Plan statt Ist) und ohne erfundene
   Zahl? Nur wenn der Kontext stimmte, ist ein Fehler hier ein
   **Modellfehler**.

Fehlerarten: `kontext_fehlt`, `kontext_falsch_zugeordnet`,
`modell_ausgelassen`, `modell_falsch`, `modell_erfunden`,
`modell_verweigert_zu_unrecht`, `ok`. Die Regeln stehen in
`eval/fakten_abgleich.py` (Offline-Tests: `tests/test_fakten_abgleich.py`).

## Wie gemessen wird

- **Der echte Codepfad.** `eval/run_fakten.py` startet ein eigenes Backend
  (freier Port, eigene Konten-DB aus `scripts/saat_konten.py`,
  `DISABLE_RATE_LIMIT=1`, `FEATURE_FLAGS=*`), meldet sich als
  `ratsfrau@example.org` an (Bearer aus dem Cookie `access_token`) und fragt
  über `POST /api/council/explain` (Lotti, mit Route und Seitenüberschrift)
  bzw. `POST /api/council/ask`. Gibt Lotti an das Archiv ab, fragt der Lauf
  wie das Fenster bei `/ask` weiter.
- **Der echte Prompt.** `RATSLOTSE_PROMPT_MITSCHNITT=<ordner>` (Messschalter in
  `kern/llm.py`, nie in eine `.env`) schreibt je Aufruf `messages`, Modell und
  Antwort nach `<ordner>/<feature>.jsonl`. Geprüft wird der Prompt des
  antwortenden Aufrufs (`assistant_explain` bzw. `qa_answer`).
- **Das Modell ist nachgewiesen:** Der Lauf bricht ab, wenn der Mitschnitt ein
  anderes Modell zeigt als bestellt. Beide Kanäle laufen mit demselben Modell
  (`COUNCIL_ASSISTANT_MODEL` = `COUNCIL_QA_MODEL`); die Frage-Analyse
  (`COUNCIL_QA_EXPAND_MODEL`) bleibt beim heutigen Modell, weil sie zum
  Kontextaufbau gehört.
- **Goldwerte aus SQL**, nie aus einer Antwort: `eval/build_fakten_haushalt.py`
  zieht jeden Wert mit einer Abfrage, die als `quelle` am Fall steht.

```bash
python eval/build_fakten_haushalt.py                     # Goldwerte neu ziehen
python eval/run_fakten.py --modell openai/gpt-6-luna --ohne-zdr
python eval/run_fakten.py --modell google/gemini-2.5-flash
python eval/run_fakten.py nachwerten eval/results/fakten/<lauf>.json
python eval/run_fakten.py bericht                        # der Teil unten
python eval/pruefstand.py --suite fakten-haushalt --modell google/gemini-2.5-flash
```

`--ohne-zdr` setzt `NWZ_OPENROUTER_ZDR=0` nur im Mess-Backend: GPT-6 Luna hat
keinen ZDR-Anbieter (Tims Entscheidung vom 23.09. für Lotti und Frag den Rat).

**Die ausführliche Recherche** misst derselbe Läufer: `--kanal deep --auswahl
deep` stellt 55 Fälle als Recherche-Job, der Kontext sind die Prompts aller
Aufrufe des Jobs, `--aufwand` setzt den Denkaufwand. Die Läufe liegen in
`eval/results/fakten/deep/` (nicht in diesem Bericht), `bericht --kanal deep`
druckt die Vergleichstabelle; Ergebnis und Entscheidung in
`docs/plan-modellwechsel.md`, „Ausführliche Recherche“. **Teure Modelle
laufen erst als Stichprobe** (`eval/kostenbremse.py`).

**Grenzen der lokalen Messung.** Der lokale Datenabzug hat keine Embeddings;
Frag den Rat sucht lokal also nur über BM25. Kontextfehler bei den
**Ratsfragen** können deshalb teils Artefakte der lokalen Suche sein — bei
den **Haushaltsfragen** nicht: Deren Zahlen kommen aus den Geld-Facetten
(`qa.geld_kontext`), die keine Embeddings brauchen.

## Die Fälle

`eval/cases_fakten_haushalt.json` — 142 Haushaltsfälle, 86 Lotti (auf der
passenden Seite und auf unpassenden, z. B. eine Investitionsfrage auf
`/haushalt/schulden`) und 56 Frag den Rat, über alle Haushaltsseiten und
Facetten; Jahres-Fallen als `verboten` (Vorjahr, Rekordjahr, Plan statt Ist);
15 Fälle mit `antwort_in_daten: false` (Schulden anderer Städte, Jahre ohne
Daten, einzelne Steuerzahler). Zwei Erweiterungen des Fallformats:
`oder` (gleichwertige Antworten mit eigenem Jahr — „Kernhaushalt“ ist Bilanz
2024 ODER Kreditmarkt 2025) und `teile` (eine Summe, deren Summanden genügen —
Beamte + Beschäftigte im Stellenplan).

`eval/cases_fakten_rat.json` — die Ratsfragen (eigener PR,
`claude/fakten-eval-rat`); gemessen wurde mit dessen Stand.

## Stand 23.09.2026 — Kurzfassung

Gemessen gegen `dev` mit #1493 (Geld-Kontext: jede Zahl unter ihrem Jahr),
233 Fälle (142 Haushalt, 91 Rat), je ein Lauf; zum Vergleich ein Lauf mit
Gemini **vor** #1493. Laufkosten, vorher an 10 Fällen hochgerechnet
(0,10 ct je Fall mit GPT-6 Luna) und dann gemessen: **GPT-6 Luna 0,22 $**
für alle 233 Fälle (370 Aufrufe, davon 125 Frage-Analysen mit Flash Lite),
**Gemini 2.5 Flash 0,43 $**. GPT-6 Luna antwortet deutlich langsamer
(p50 7,8 s gegen 2,9 s).

| | Haushalt ok | Rat ok | Kontextfehler | Modellfehler | davon falsch/erfunden |
|---|---:|---:|---:|---:|---:|
| Gemini 2.5 Flash, vor #1493 | 101/142 (71 %) | 41/91 (45 %) | 64 | 27 | 2 |
| Gemini 2.5 Flash, nach #1493 | 105/142 (74 %) | 43/91 (47 %) | 59 | 26 | 2 |
| GPT-6 Luna, nach #1493 | 106/142 (75 %) | 37/91 (41 %) | 60 | 30 | **0** |

**Was die Zahlen sagen.**

- **Der Kontext ist der größere Hebel.** Rund ein Viertel aller Fälle
  scheitert, bevor das Modell etwas tun kann; Modellfehler sind es rund
  12 %. Bei den Haushaltsfällen: 29 Kontextfehler gegen 7 (Luna) bzw. 8
  (Gemini) Modellfehler.
- **#1493 wirkt, und die Eval sieht es:** Die drei Zuordnungsfehler aus dem
  Faktencheck (Schulden-„davon“ unter 2024, Investitions-Auszahlungsarten
  unter dem Rekordjahr 2020) waren vorher `kontext_falsch_zugeordnet` und
  sind nachher `ok`; ebenso die fehlenden Eigenbetriebs-Aufwendungen des AWB.
  Nach #1493 gibt es **keinen einzigen** falsch zugeordneten Wert mehr — was
  bleibt, fehlt ganz.
- **GPT-6 Luna macht keine harten Fehler:** 0 falsche, 0 erfundene Zahlen;
  14 der 15 Haushaltsfragen ohne Antwort in den Daten richtig verweigert
  (die fünfzehnte zählt als Kontextfall). Gemini beantwortet wieder „Ist das
  viel im Vergleich?“ (Schulden) mit der Steuerkraft, ohne zu sagen, dass es
  keine Schulden sind — der Befund aus dem Faktencheck, jetzt als Wächter.
  Lunas Fehler sind Auslassungen (28): knappe Antworten, die einen zweiten
  Goldfakt weglassen. Der zweite „falsche“ Gemini-Fall
  (`rat-kongresshalle-kosten`) ist ein Verbot der Ratsfälle, das die
  Ausfallbürgschaft von 79 Mio. € auch dann trifft, wenn sie richtig als
  Bürgschaft genannt wird.
- **Die Ratsfälle sind lokal schlechter als im Betrieb:** Der lokale Abzug hat
  keine Embeddings, Frag den Rat sucht hier nur über BM25. Ihre
  Kontextfehler (Beschluss nicht gefunden) sind deshalb zum Teil Messartefakt
  — die der Haushaltsfälle nicht. Viele Rats-Auslassungen sind außerdem
  Datumsgold („01.06.2026“), wo die Antwort „im Juni 2026“ sagt.

**Die Kontextfehler der Haushaltsfälle, nach Ursache** (Einzelheiten und je
ein Beispiel in der erzeugten Liste unten):

1. **Haushaltsvollzug kommt nicht an** (`council/geld/execution.py`, 4 Fälle):
   „Was erwartet die Verwaltung für das laufende Jahr?“, „Wie ist 2025
   ausgegangen?“ — die Prognose zum 30.06.2026 (−66,0 Mio. €) und das
   Ergebnis laut Bericht zum 31.12.2025 (−18,1 Mio. €) stehen in keinem Prompt.
2. **Investitionsplan 2026 fehlt** (`investitionen`, 2): Der Finanzhaushalt je
   Teilhaushalt endet in den Daten 2025; den Plan 2026 (70,3 Mio. € laut
   Vollzugsbericht, 69,1 Mio. € laut Satzung) liefert keine Facette —
   „Wie viel investiert die Stadt?“ bekommt den Plan 2025.
3. **Posten des Ergebnishaushalts** (`ansatz`, 3): Zinsaufwand (auf der
   Schulden-Seite!), Transferaufwendungen, öffentlich-rechtliche Entgelte
   („Wie viel Gebühren nimmt die Stadt ein?“) — der Ansatz feuert nicht.
4. **Haushaltssatzung** (`bylaw.py`, 2): Liquiditätskredit-Höchstbetrag
   (100 Mio. €) auf „Wie viel Kredit darf die Stadt aufnehmen?“, Tilgung.
5. **Rangfrage ohne Rangliste** (`plan`, 2): „Wofür gibt die Stadt am meisten
   aus?“ — Soziales und Gesundheit (283,1 Mio. €) steht nicht im Prompt.
6. **Städtevergleich nur für die Steuerkraft** (`vergleich`, 3): Hebesätze und
   Steuereinnahmekraft je Einwohner anderer Städte liegen in
   `council_city_comparison`, kommen aber nicht in den Prompt.
7. **Facette feuert nicht** (je 1): „Warum war 2024 besser als geplant?“
   (Frag den Rat: kein Haushaltsbaustein), „Wie viele Leute arbeiten bei der
   Stadt?“ (Stellenplan), „Wie viel Vermögen … pro Einwohner?“ (Kennzahlen;
   die Regex will „Vermögen pro Einwohner“ am Stück), Investitions-Ist auf der
   Schulden-Seite, Schuldenstand 2015 (die Reihe liefert nur jüngstes Jahr,
   Vorjahr, Rekord), Hebesatz bei „Einfluss auf die Steuern“.
8. **Begriffe treffen die Produkte nicht** (`produkte`, 2): „Stadtarchiv“ →
   Produkt „Archivierung“, „Sportförderung“ → nur der Teilhaushalt.
9. **Beteiligungen** (`companies.py`, `konzern`, 3): GSG-Jahresergebnis und
   GSG in der Konzernliste fehlen; der Bäderbetrieb hat eine Aufwandszahl im
   Gesamtabschluss (8,0 Mio. € 2024), sie kommt nicht mit.
10. **Steuer-Steckbrief ohne Steuer** (`/haushalt/steuer`): Das Fenster schickt
    `?art=` nicht mit (`ExplainRefs` kennt kein `art`), Lotti weiß auf dem
    Steckbrief nicht, welche Steuer gemeint ist.
11. **Einzelvorhaben** (`measures.py`): Das größte Vorhaben im
    Investitionsprogramm 2025 (Fliegerhorst Kampfmittelsondierung,
    35,9 Mio. €) steht nicht in der Auswahl.

**Datenbefund nebenbei:** `council_budget_bylaw.session_date` sagt für 2026
„15.12.2025“ — an dem Tag wurde vertagt (Beschluss 9283); beschlossen hat der
Rat am 09.02.2026 (8286). Beide Modelle antworteten deshalb, der Haushalt sei
noch nicht beschlossen.

**Was diese Messung nicht ist:** ein Urteil zwischen den Modellen. Je ein Lauf,
und der Unterschied liegt im Rauschen (Haushalt 105 gegen 106 ok). Belastbar
sind die Kontextfehler — sie hängen nicht am Modell und waren in beiden Läufen
dieselben.

## Nachzug K1 (23.09.2026) — die Arbeitsliste der Haushaltsfälle abgearbeitet

Alle elf Ursachen oben plus der Datenbefund, gemessen mit GPT-6 Luna nur an
den 142 Haushaltsfällen (Ratsfälle unverändert): ein Lauf **vor** dem Nachzug
auf demselben Stand und demselben Abzug, zwei **danach**.

| | ok | Kontextfehler | Modellfehler | davon falsch/erfunden | Prompt Lotti (Tokens, Mittel) | Prompt Frag den Rat |
|---|---:|---:|---:|---:|---:|---:|
| vor K1 | 104/142 (73 %) | 29 | 9 | 0 | 3.386 | 5.202 |
| nach K1, Lauf 1 | 134/142 (94 %) | **0** | 8 | 0 | 3.450 | 5.225 |
| nach K1, Lauf 2 | 131/142 (92 %) | **0** | 11 | 0 | 3.450 | 5.281 |

Was blieb, sind Auslassungen des Modells (knappe Antworten ohne den zweiten
Goldfakt), keine fehlenden oder falsch zugeordneten Zahlen. Der Prompt wuchs
im Mittel um knapp 2 % (Lotti) bzw. unter 2 % (Frag den Rat): Die neuen
Zeilen kommen über engere Auslösung und eine Vorrangregel (die Facetten der
FRAGE vor denen der Seite), nicht über einen größeren Deckel —
`GELD_MAX_CHARS` und `GELD_MAX` sind unverändert.

Zwei Regeln der Auswertung wurden dabei nachgezogen, beide mit Beleg:
Gerundet wird kaufmännisch (Pythons `round` rundete „35,9 Mio. €“ für
35.850.000 € als falsch), und „nicht einzeln ausgewiesen“ / „anhand der …
nicht möglich“ zählen als Absage. Die Arbeitsliste nimmt je Fall den
jüngsten Stand, der ihn gemessen hat (`run_fakten._stand`), damit ein
Teillauf behobene Fehler eines älteren Gesamtlaufs nicht stehen lässt.

<!-- fakten-eval:anfang -->
## Ergebnis

- **google/gemini-2.5-flash (vor #1493)** (20260923-080106, `eval/results/fakten/google-gemini-2.5-flash-20260923-080106.json`): 142/233 (61%) ok, Kontext stimmte in 169 Fällen, 27 Modellfehler (davon 0 erfunden), 64 Kontextfehler, 0 Ausfälle, p50 2874 ms, Kosten 0.44 $
- **openai/gpt-6-luna (vor K1)** (20260923-090851, `eval/results/fakten/openai-gpt-6-luna-20260923-090851.json`): 104/142 (73%) ok, Kontext stimmte in 113 Fällen, 9 Modellfehler (davon 0 erfunden), 29 Kontextfehler, 0 Ausfälle, p50 6672 ms, Kosten 0.13 $
- **google/gemini-2.5-flash (nach #1493)** (20260923-081455, `eval/results/fakten/google-gemini-2.5-flash-20260923-081455.json`): 148/233 (64%) ok, Kontext stimmte in 174 Fällen, 26 Modellfehler (davon 0 erfunden), 59 Kontextfehler, 0 Ausfälle, p50 2913 ms, Kosten 0.43 $
- **openai/gpt-6-luna (nach #1493)** (20260923-081458, `eval/results/fakten/openai-gpt-6-luna-20260923-081458.json`): 143/233 (61%) ok, Kontext stimmte in 173 Fällen, 30 Modellfehler (davon 0 erfunden), 60 Kontextfehler, 0 Ausfälle, p50 7826 ms, Kosten 0.22 $
- **openai/gpt-6-luna (nach K1, Lauf 1)** (20260923-100126, `eval/results/fakten/openai-gpt-6-luna-20260923-100126.json`): 134/142 (94%) ok, Kontext stimmte in 142 Fällen, 8 Modellfehler (davon 0 erfunden), 0 Kontextfehler, 0 Ausfälle, p50 7328 ms, Kosten 0.07 $
- **openai/gpt-6-luna (nach K1, Lauf 2)** (20260923-100157, `eval/results/fakten/openai-gpt-6-luna-20260923-100157.json`): 131/142 (92%) ok, Kontext stimmte in 142 Fällen, 11 Modellfehler (davon 0 erfunden), 0 Kontextfehler, 0 Ausfälle, p50 6960 ms, Kosten 0.10 $

### Je Fallsatz

| Lauf | Fallsatz | Fälle | ok | Kontextfehler | Modellfehler | davon falsch/erfunden |
|---|---|---:|---:|---:|---:|---:|
| google/gemini-2.5-flash (vor #1493) | Haushalt | 142 | 101/142 (71%) | 33 | 8 | 1 |
| google/gemini-2.5-flash (vor #1493) | Rat | 91 | 41/91 (45%) | 31 | 19 | 1 |
| openai/gpt-6-luna (vor K1) | Haushalt | 142 | 104/142 (73%) | 29 | 9 | 0 |
| google/gemini-2.5-flash (nach #1493) | Haushalt | 142 | 105/142 (74%) | 29 | 8 | 1 |
| google/gemini-2.5-flash (nach #1493) | Rat | 91 | 43/91 (47%) | 30 | 18 | 1 |
| openai/gpt-6-luna (nach #1493) | Haushalt | 142 | 106/142 (75%) | 29 | 7 | 0 |
| openai/gpt-6-luna (nach #1493) | Rat | 91 | 37/91 (41%) | 31 | 23 | 0 |
| openai/gpt-6-luna (nach K1, Lauf 1) | Haushalt | 142 | 134/142 (94%) | 0 | 8 | 0 |
| openai/gpt-6-luna (nach K1, Lauf 2) | Haushalt | 142 | 131/142 (92%) | 0 | 11 | 0 |

### Je Kanal und Fehlerart

| Modell | Kanal | Fälle | ok | Kontext ok | kontext_fehlt | kontext_falsch_zugeordnet | modell_ausgelassen | modell_falsch | modell_erfunden | modell_verweigert_zu_unrecht |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| google/gemini-2.5-flash (vor #1493) | lotti | 121 | 79/121 (65%) | 88 | 32 | 1 | 8 | 1 | 0 | 0 |
| google/gemini-2.5-flash (vor #1493) | rat | 112 | 63/112 (56%) | 81 | 28 | 3 | 16 | 1 | 0 | 1 |
| google/gemini-2.5-flash (vor #1493) | alle | 233 | 142/233 (61%) | 169 | 60 | 4 | 24 | 2 | 0 | 1 |
| openai/gpt-6-luna (vor K1) | lotti | 86 | 61/86 (71%) | 67 | 19 | 0 | 4 | 0 | 0 | 2 |
| openai/gpt-6-luna (vor K1) | rat | 56 | 43/56 (77%) | 46 | 10 | 0 | 3 | 0 | 0 | 0 |
| openai/gpt-6-luna (vor K1) | alle | 142 | 104/142 (73%) | 113 | 29 | 0 | 7 | 0 | 0 | 2 |
| google/gemini-2.5-flash (nach #1493) | lotti | 121 | 80/121 (66%) | 90 | 31 | 0 | 9 | 1 | 0 | 0 |
| google/gemini-2.5-flash (nach #1493) | rat | 112 | 68/112 (61%) | 84 | 28 | 0 | 15 | 1 | 0 | 0 |
| google/gemini-2.5-flash (nach #1493) | alle | 233 | 148/233 (64%) | 174 | 59 | 0 | 24 | 2 | 0 | 0 |
| openai/gpt-6-luna (nach #1493) | lotti | 121 | 80/121 (66%) | 89 | 32 | 0 | 8 | 0 | 0 | 1 |
| openai/gpt-6-luna (nach #1493) | rat | 112 | 63/112 (56%) | 84 | 28 | 0 | 20 | 0 | 0 | 1 |
| openai/gpt-6-luna (nach #1493) | alle | 233 | 143/233 (61%) | 173 | 60 | 0 | 28 | 0 | 0 | 2 |
| openai/gpt-6-luna (nach K1, Lauf 1) | lotti | 86 | 79/86 (92%) | 86 | 0 | 0 | 6 | 0 | 0 | 1 |
| openai/gpt-6-luna (nach K1, Lauf 1) | rat | 56 | 55/56 (98%) | 56 | 0 | 0 | 1 | 0 | 0 | 0 |
| openai/gpt-6-luna (nach K1, Lauf 1) | alle | 142 | 134/142 (94%) | 142 | 0 | 0 | 7 | 0 | 0 | 1 |
| openai/gpt-6-luna (nach K1, Lauf 2) | lotti | 86 | 77/86 (90%) | 86 | 0 | 0 | 8 | 0 | 0 | 1 |
| openai/gpt-6-luna (nach K1, Lauf 2) | rat | 56 | 54/56 (96%) | 56 | 0 | 0 | 2 | 0 | 0 | 0 |
| openai/gpt-6-luna (nach K1, Lauf 2) | alle | 142 | 131/142 (92%) | 142 | 0 | 0 | 10 | 0 | 0 | 1 |

### Je Kategorie

| Kategorie | Fälle | google/gemini-2.5-flash (vor #1493) ok | Kontextfehler | openai/gpt-6-luna (vor K1) ok | Kontextfehler | google/gemini-2.5-flash (nach #1493) ok | Kontextfehler | openai/gpt-6-luna (nach #1493) ok | Kontextfehler | openai/gpt-6-luna (nach K1, Lauf 1) ok | Kontextfehler | openai/gpt-6-luna (nach K1, Lauf 2) ok | Kontextfehler |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| beschluss/abstimmung | 0 | 3/6 (50%) | 2 | — | 0 | 3/6 (50%) | 2 | 2/6 (33%) | 3 | — | 0 | — | 0 |
| beschluss/ergebnis | 0 | 6/10 (60%) | 2 | — | 0 | 6/10 (60%) | 2 | 5/10 (50%) | 2 | — | 0 | — | 0 |
| beschluss/kosten | 0 | 4/9 (44%) | 5 | — | 0 | 4/9 (44%) | 5 | 4/9 (44%) | 5 | — | 0 | — | 0 |
| haushalt/begriffe | 1 | 1/1 (100%) | 0 | 1/1 (100%) | 0 | 1/1 (100%) | 0 | 1/1 (100%) | 0 | 1/1 (100%) | 0 | 1/1 (100%) | 0 |
| haushalt/eigenbetriebe | 7 | 6/7 (86%) | 1 | 6/7 (86%) | 1 | 6/7 (86%) | 1 | 6/7 (86%) | 1 | 6/7 (86%) | 0 | 6/7 (86%) | 0 |
| haushalt/gebuehren | 6 | 5/6 (83%) | 1 | 5/6 (83%) | 1 | 5/6 (83%) | 1 | 5/6 (83%) | 1 | 6/6 (100%) | 0 | 6/6 (100%) | 0 |
| haushalt/investitionen | 14 | 7/14 (50%) | 6 | 10/14 (71%) | 4 | 8/14 (57%) | 4 | 10/14 (71%) | 4 | 12/14 (86%) | 0 | 11/14 (79%) | 0 |
| haushalt/ist | 10 | 7/10 (70%) | 1 | 7/10 (70%) | 1 | 7/10 (70%) | 1 | 7/10 (70%) | 1 | 9/10 (90%) | 0 | 9/10 (90%) | 0 |
| haushalt/konzern | 7 | 5/7 (71%) | 2 | 5/7 (71%) | 2 | 5/7 (71%) | 2 | 5/7 (71%) | 2 | 6/7 (86%) | 0 | 6/7 (86%) | 0 |
| haushalt/mitreden | 3 | 3/3 (100%) | 0 | 3/3 (100%) | 0 | 3/3 (100%) | 0 | 3/3 (100%) | 0 | 3/3 (100%) | 0 | 3/3 (100%) | 0 |
| haushalt/nachbewilligungen | 1 | 1/1 (100%) | 0 | 1/1 (100%) | 0 | 1/1 (100%) | 0 | 1/1 (100%) | 0 | 1/1 (100%) | 0 | 1/1 (100%) | 0 |
| haushalt/nicht-in-daten | 15 | 13/15 (87%) | 1 | 14/15 (93%) | 1 | 13/15 (87%) | 1 | 14/15 (93%) | 1 | 15/15 (100%) | 0 | 15/15 (100%) | 0 |
| haushalt/plan | 12 | 8/12 (67%) | 3 | 9/12 (75%) | 3 | 9/12 (75%) | 3 | 9/12 (75%) | 3 | 12/12 (100%) | 0 | 12/12 (100%) | 0 |
| haushalt/produkte | 8 | 5/8 (62%) | 2 | 4/8 (50%) | 2 | 5/8 (62%) | 2 | 4/8 (50%) | 2 | 8/8 (100%) | 0 | 8/8 (100%) | 0 |
| haushalt/pruefung | 6 | 5/6 (83%) | 1 | 4/6 (67%) | 1 | 5/6 (83%) | 1 | 5/6 (83%) | 1 | 5/6 (83%) | 0 | 6/6 (100%) | 0 |
| haushalt/satzung | 5 | 3/5 (60%) | 1 | 2/5 (40%) | 1 | 3/5 (60%) | 1 | 2/5 (40%) | 1 | 5/5 (100%) | 0 | 3/5 (60%) | 0 |
| haushalt/schulden | 18 | 13/18 (72%) | 5 | 15/18 (83%) | 3 | 15/18 (83%) | 3 | 15/18 (83%) | 3 | 18/18 (100%) | 0 | 18/18 (100%) | 0 |
| haushalt/spenden | 1 | 1/1 (100%) | 0 | 1/1 (100%) | 0 | 1/1 (100%) | 0 | 1/1 (100%) | 0 | 1/1 (100%) | 0 | 1/1 (100%) | 0 |
| haushalt/stellenplan | 5 | 4/5 (80%) | 1 | 4/5 (80%) | 1 | 4/5 (80%) | 1 | 4/5 (80%) | 1 | 5/5 (100%) | 0 | 4/5 (80%) | 0 |
| haushalt/steuern | 15 | 13/15 (87%) | 2 | 12/15 (80%) | 2 | 13/15 (87%) | 2 | 13/15 (87%) | 2 | 14/15 (93%) | 0 | 14/15 (93%) | 0 |
| haushalt/vergleich | 5 | 1/5 (20%) | 3 | 1/5 (20%) | 3 | 1/5 (20%) | 3 | 1/5 (20%) | 3 | 4/5 (80%) | 0 | 4/5 (80%) | 0 |
| haushalt/vollzug | 3 | 0/3 (0%) | 3 | 0/3 (0%) | 3 | 0/3 (0%) | 3 | 0/3 (0%) | 3 | 3/3 (100%) | 0 | 3/3 (100%) | 0 |
| nicht-in-daten/abstimmung | 0 | 5/5 (100%) | 0 | — | 0 | 5/5 (100%) | 0 | 5/5 (100%) | 0 | — | 0 | — | 0 |
| nicht-in-daten/offen | 0 | 4/4 (100%) | 0 | — | 0 | 4/4 (100%) | 0 | 4/4 (100%) | 0 | — | 0 | — | 0 |
| nicht-in-daten/sonstiges | 0 | 2/2 (100%) | 0 | — | 0 | 2/2 (100%) | 0 | 2/2 (100%) | 0 | — | 0 | — | 0 |
| ort | 0 | 2/6 (33%) | 3 | — | 0 | 2/6 (33%) | 3 | 2/6 (33%) | 3 | — | 0 | — | 0 |
| person/ausschuss | 0 | 0/6 (0%) | 4 | — | 0 | 0/6 (0%) | 4 | 0/6 (0%) | 4 | — | 0 | — | 0 |
| person/fraktion | 0 | 2/4 (50%) | 2 | — | 0 | 2/4 (50%) | 2 | 2/4 (50%) | 2 | — | 0 | — | 0 |
| sitzung/beschluesse | 0 | 2/3 (67%) | 1 | — | 0 | 2/3 (67%) | 1 | 2/3 (67%) | 1 | — | 0 | — | 0 |
| sitzung/tagesordnung | 0 | 1/2 (50%) | 1 | — | 0 | 1/2 (50%) | 1 | 1/2 (50%) | 1 | — | 0 | — | 0 |
| sitzung/termin | 0 | 1/3 (33%) | 1 | — | 0 | 2/3 (67%) | 1 | 2/3 (67%) | 1 | — | 0 | — | 0 |
| verlauf/baumschutz | 0 | 0/1 (0%) | 1 | — | 0 | 0/1 (0%) | 1 | 0/1 (0%) | 1 | — | 0 | — | 0 |
| verlauf/fliegerhorst | 0 | 0/2 (0%) | 1 | — | 0 | 0/2 (0%) | 1 | 0/2 (0%) | 1 | — | 0 | — | 0 |
| verlauf/grundsteuer | 0 | 0/2 (0%) | 1 | — | 0 | 1/2 (50%) | 0 | 1/2 (50%) | 0 | — | 0 | — | 0 |
| verlauf/klima | 0 | 0/1 (0%) | 0 | — | 0 | 0/1 (0%) | 0 | 0/1 (0%) | 0 | — | 0 | — | 0 |
| verlauf/radverkehr | 0 | 0/3 (0%) | 1 | — | 0 | 0/3 (0%) | 1 | 0/3 (0%) | 1 | — | 0 | — | 0 |
| verlauf/schwimmbad | 0 | 0/1 (0%) | 1 | — | 0 | 0/1 (0%) | 1 | 0/1 (0%) | 1 | — | 0 | — | 0 |
| verlauf/stadion | 0 | 0/4 (0%) | 3 | — | 0 | 0/4 (0%) | 3 | 0/4 (0%) | 3 | — | 0 | — | 0 |
| verwechslung/abgelehnt-als-angenommen | 0 | 1/3 (33%) | 0 | — | 0 | 0/3 (0%) | 0 | 1/3 (33%) | 0 | — | 0 | — | 0 |
| verwechslung/fliegerhorst | 0 | 0/1 (0%) | 1 | — | 0 | 0/1 (0%) | 1 | 0/1 (0%) | 1 | — | 0 | — | 0 |
| verwechslung/grundsteuer | 0 | 2/2 (100%) | 0 | — | 0 | 2/2 (100%) | 0 | 1/2 (50%) | 0 | — | 0 | — | 0 |
| verwechslung/praemisse | 0 | 0/1 (0%) | 0 | — | 0 | 1/1 (100%) | 0 | 0/1 (0%) | 0 | — | 0 | — | 0 |
| verwechslung/radverkehr | 0 | 0/1 (0%) | 0 | — | 0 | 0/1 (0%) | 0 | 0/1 (0%) | 0 | — | 0 | — | 0 |
| verwechslung/schwimmbad | 0 | 0/1 (0%) | 1 | — | 0 | 0/1 (0%) | 1 | 0/1 (0%) | 1 | — | 0 | — | 0 |
| verwechslung/sechsfeldhalle | 0 | 0/1 (0%) | 0 | — | 0 | 0/1 (0%) | 0 | 0/1 (0%) | 0 | — | 0 | — | 0 |
| verwechslung/stadion | 0 | 2/2 (100%) | 0 | — | 0 | 2/2 (100%) | 0 | 1/2 (50%) | 0 | — | 0 | — | 0 |
| verwechslung/weser-ems-halle | 0 | 3/4 (75%) | 0 | — | 0 | 3/4 (75%) | 0 | 2/4 (50%) | 0 | — | 0 | — | 0 |
| verwechslung/zweckentfremdung | 0 | 1/1 (100%) | 0 | — | 0 | 1/1 (100%) | 0 | 0/1 (0%) | 0 | — | 0 | — | 0 |

## Kontextfehler — die Arbeitsliste

Gruppiert nach dem Codeteil, der den Fakt hätte liefern müssen. Je Eintrag: Frage, Goldfakt, und was im Prompt stand (bei „falsch zugeordnet“ die Zeile samt dem Jahr, unter dem sie steht; bei „fehlt“ die Bausteine, die da waren).

### `Lotti-Seitenblock (/council/sitzung)` — 6

- `lotti-sitzung-2809-wann-wo` (lotti `/council/sitzung`): „Wann und wo findet diese Sitzung statt?“ — Gold: PFL — fehlt: nicht da; Bausteine im Prompt: WAS DU WEISST, WAS DIE PERSON GERADE VOR SICH HAT, SO ANTWORTEST DU, WEITER, FRAGE
- `lotti-sitzung-2809-tagesordnung` (lotti `/council/sitzung`): „Welche Punkte stehen hier auf der Tagesordnung?“ — Gold: Klinikum — fehlt: nicht da; Bausteine im Prompt: WAS DU WEISST, WAS DIE PERSON GERADE VOR SICH HAT, SO ANTWORTEST DU, WEITER, FRAGE
- `lotti-sitzung-2809-tagesordnung` (lotti `/council/sitzung`): „Welche Punkte stehen hier auf der Tagesordnung?“ — Gold: überplanmäßige Bewilligung Teilhaushalt 10 : 9512500 — fehlt: nicht da; Bausteine im Prompt: WAS DU WEISST, WAS DIE PERSON GERADE VOR SICH HAT, SO ANTWORTEST DU, WEITER, FRAGE
- `lotti-sitzung-0106-stadion` (lotti `/council/sitzung`): „Was wurde hier in der Sitzung zum Stadion entschieden?“ — Gold: Beschluss 8677 — fehlt: nicht da; Bausteine im Prompt: WAS DU WEISST, WAS DIE PERSON GERADE VOR SICH HAT, SO ANTWORTEST DU, WEITER, FRAGE
- `lotti-sitzung-0106-stadion` (lotti `/council/sitzung`): „Was wurde hier in der Sitzung zum Stadion entschieden?“ — Gold: Beschluss 8679 — fehlt: nicht da; Bausteine im Prompt: WAS DU WEISST, WAS DIE PERSON GERADE VOR SICH HAT, SO ANTWORTEST DU, WEITER, FRAGE
- `lotti-sitzung-0106-stadion` (lotti `/council/sitzung`): „Was wurde hier in der Sitzung zum Stadion entschieden?“ — Gold: angenommen | beschlossen | zugestimmt | beschloss | Zustimmung | accepted — fehlt: nicht da; Bausteine im Prompt: WAS DU WEISST, WAS DIE PERSON GERADE VOR SICH HAT, SO ANTWORTEST DU, WEITER, FRAGE

### `Retrieval/Beschlusskontext (verlauf/stadion)` — 5

- `rat-stadion-was-beschlossen` (rat): „Was hat der Rat zum Stadion an der Maastrichter Straße beschlossen?“ — Gold: Eigenkapitalzuschuss der Stadt (bis zu) : 15000000 — fehlt: nicht da; Bausteine im Prompt: STAND DER AKTEN, BESCHLÜSSE, AUS DEN RATSDEBATTEN, FOLGEFRAGEN
- `rat-stadion-eu-genehmigung` (rat): „Hat die EU-Kommission die Finanzierung des Stadions genehmigt?“ — Gold: 12.08.2026 | 12.8.2026 | 12. August 2026 | 2026-08-12 — fehlt: nicht da; Bausteine im Prompt: DIESE FRAGE IST ENG GESTELLT, STAND DER AKTEN, BESCHLÜSSE, FOLGEFRAGEN
- `rat-stadion-eu-genehmigung` (rat): „Hat die EU-Kommission die Finanzierung des Stadions genehmigt?“ — Gold: genehmigte Beihilfen : 75000000 — fehlt: nicht da; Bausteine im Prompt: DIESE FRAGE IST ENG GESTELLT, STAND DER AKTEN, BESCHLÜSSE, FOLGEFRAGEN
- `rat-stadion-fertigstellung` (rat): „Wann soll das neue Stadion fertig sein?“ — Gold: 2028 + 2029 — fehlt: nicht da; Bausteine im Prompt: DIESE FRAGE IST ENG GESTELLT, STAND DER AKTEN, BESCHLÜSSE, FOLGEFRAGEN
- `rat-stadion-fertigstellung` (rat): „Wann soll das neue Stadion fertig sein?“ — Gold: 1. Juli 2027 | 01.07.2027 | Juli 2027 — fehlt: nicht da; Bausteine im Prompt: DIESE FRAGE IST ENG GESTELLT, STAND DER AKTEN, BESCHLÜSSE, FOLGEFRAGEN

### `Retrieval/Beschlusskontext (beschluss/kosten)` — 4

- `rat-stadion-kosten-wer-zahlt` (rat): „Wie viel kostet das neue Stadion und wer bezahlt es?“ — Gold: Baunebenkosten netto : 2360000 — fehlt: nicht da; Bausteine im Prompt: ZU DIESER FRAGE LIEGEN HAUSHALTSDATEN IM KONTEXT, STAND DER AKTEN, BESCHLÜSSE, AUFGABEN DER STADT MIT KOSTEN UND RECHTSGRUNDLAGE, STADTHAUSHALT, PASSEND ZUR FRAGE
- `rat-stadion-kosten-wer-zahlt` (rat): „Wie viel kostet das neue Stadion und wer bezahlt es?“ — Gold: Eigenkapitalzuschuss der Stadt (bis zu) : 15000000 — fehlt: nicht da; Bausteine im Prompt: ZU DIESER FRAGE LIEGEN HAUSHALTSDATEN IM KONTEXT, STAND DER AKTEN, BESCHLÜSSE, AUFGABEN DER STADT MIT KOSTEN UND RECHTSGRUNDLAGE, STADTHAUSHALT, PASSEND ZUR FRAGE
- `rat-grundsteuer-mehrertrag` (rat): „Wie viel Mehrertrag hätte die im Dezember 2025 abgelehnte Grundsteuer-Anhebung gebracht?“ — Gold: erwartete Mehrerträge ab 2026 2026: 4420000 — fehlt: nicht da; Bausteine im Prompt: DIESE FRAGE IST ENG GESTELLT, STAND DER AKTEN, BESCHLÜSSE, WAS DIE FACHWÖRTER BEDEUTEN, ÄNDERUNGSLISTEN ZUM HAUSHALT 2025, DER STREIT UM DEN HAUSHALT 2025
- `rat-sechsfeldhalle-kosten` (rat): „Was soll die Sechsfeldhalle an der Kennedystraße kosten?“ — Gold: erste Kostenschätzung : 31300000 — fehlt: nicht da; Bausteine im Prompt: DIESE FRAGE IST ENG GESTELLT, STAND DER AKTEN, BESCHLÜSSE, GEPLANT UND TATSÄCHLICH, AUFGABEN DER STADT MIT KOSTEN UND RECHTSGRUNDLAGE, STADTHAUSHALT

### `Lotti-Seitenblock (/council/person)` — 4

- `lotti-person-luekermann-partei` (lotti `/council/person`): „Für welche Partei sitzt er im Rat?“ — Gold: Volt — fehlt: nicht da; Bausteine im Prompt: WAS DU WEISST, WAS DIE PERSON GERADE VOR SICH HAT, SO ANTWORTEST DU, WEITER, FRAGE
- `lotti-person-druegemoeller-ausschuesse` (lotti `/council/person`): „In welchen Ausschüssen sitzt sie?“ — Gold: Gebäudewirtschaft + Stadtplanung + Finanzen — fehlt: nicht da; Bausteine im Prompt: WAS DU WEISST, WAS DIE PERSON GERADE VOR SICH HAT, SO ANTWORTEST DU, WEITER, FRAGE
- `lotti-person-adler-fraktion` (lotti `/council/person`): „Welcher Fraktion gehört er heute an?“ — Gold: BSW — fehlt: nicht da; Bausteine im Prompt: WAS DU WEISST, WAS DIE PERSON GERADE VOR SICH HAT, SO ANTWORTEST DU, WEITER, FRAGE
- `lotti-person-meerbothe-vorsitz` (lotti `/council/person`): „Welchen Ausschuss leitet er?“ — Gold: Verkehrsausschuss — fehlt: nicht da; Bausteine im Prompt: WAS DU WEISST, WAS DIE PERSON GERADE VOR SICH HAT, SO ANTWORTEST DU, WEITER, FRAGE

### `Lotti-Seitenblock (/council/ort)` — 3

- `lotti-ort-hallensichel` (lotti `/council/ort`): „Wie weit ist der Bebauungsplan hier?“ — Gold: 13.04.2026 | 13.4.2026 | 13. April 2026 | 2026-04-13 — fehlt: nicht da; Bausteine im Prompt: WAS DU WEISST, WAS DIE PERSON GERADE VOR SICH HAT, SO ANTWORTEST DU, WEITER, FRAGE
- `lotti-ort-alte-fleiwa` (lotti `/council/ort`): „Was wurde hier zuletzt beschlossen?“ — Gold: 01.06.2026 | 1.6.2026 | 1. Juni 2026 | 01. Juni 2026 | 2026-06-01 — fehlt: nicht da; Bausteine im Prompt: WAS DU WEISST, WAS DIE PERSON GERADE VOR SICH HAT, SO ANTWORTEST DU, WEITER, FRAGE
- `lotti-ort-alte-fleiwa` (lotti `/council/ort`): „Was wurde hier zuletzt beschlossen?“ — Gold: 855 — fehlt: nicht da; Bausteine im Prompt: WAS DU WEISST, WAS DIE PERSON GERADE VOR SICH HAT, SO ANTWORTEST DU, WEITER, FRAGE

### `Lotti-Seitenblock (/council/decision)` — 3

- `lotti-btb-betrag` (lotti `/council/decision`): „Wie viel Geld bekommt der BTB hier im Jahr 2027?“ — Gold: Zuschuss BTB-Bad (Maximalbetrag) 2027: 177500 — fehlt: nicht da; Bausteine im Prompt: WAS DU WEISST, WAS DIE PERSON GERADE VOR SICH HAT, SO ANTWORTEST DU, WEITER, FRAGE
- `lotti-sechsfeldhalle-kosten` (lotti `/council/decision`): „Was kostet die Halle, um die es hier geht?“ — Gold: erste Kostenschätzung : 31300000 — fehlt: nicht da; Bausteine im Prompt: WAS DU WEISST, WAS DIE PERSON GERADE VOR SICH HAT, SO ANTWORTEST DU, WEITER, FRAGE
- `lotti-schulbezirke-gegenstimmen` (lotti `/council/decision`): „Gab es hier Gegenstimmen?“ — Gold: Enthaltungen : 9 — fehlt: nicht da; Bausteine im Prompt: DER GEGENSTAND DER SEITE, WAS DIE PERSON GERADE AUF DEM BILDSCHIRM HAT, SCREEN, STAND DER AKTEN, BESCHLÜSSE, FOLGEFRAGEN

### `Retrieval/Beschlusskontext (beschluss/abstimmung)` — 2

- `rat-stadion-wer-dagegen` (rat): „Welche Fraktionen haben im Juni 2026 gegen die Stadion-Vergabe gestimmt?“ — Gold: Grüne | Grünen + Für Oldenburg — fehlt: nicht da; Bausteine im Prompt: DIESE FRAGE IST ENG GESTELLT, STAND DER AKTEN, BESCHLÜSSE, WAS DIE FACHWÖRTER BEDEUTEN, AUS DEN RATSDEBATTEN, FOLGEFRAGEN
- `rat-schulbezirke-abstimmung` (rat): „Wie wurde über die neuen Schulbezirke der Grundschulen abgestimmt?“ — Gold: Enthaltungen : 9 — fehlt: nicht da; Bausteine im Prompt: STAND DER AKTEN, BESCHLÜSSE, FOLGEFRAGEN

### `Retrieval/Beschlusskontext (beschluss/ergebnis)` — 2

- `rat-stadion-baufirma` (rat): „Welche Firma baut das neue Stadion?“ — Gold: Hellmich — fehlt: nicht da; Bausteine im Prompt: DIESE FRAGE IST ENG GESTELLT, STAND DER AKTEN, BESCHLÜSSE, AUS DEN RATSDEBATTEN, FOLGEFRAGEN
- `rat-lachgas-verbot` (rat): „Hat Oldenburg ein Lachgas-Verbot für Minderjährige beschlossen?“ — Gold: einstimmig — fehlt: nicht da; Bausteine im Prompt: DIESE FRAGE IST ENG GESTELLT, STAND DER AKTEN, BESCHLÜSSE, FOLGEFRAGEN

### `Retrieval/Beschlusskontext (verlauf/fliegerhorst)` — 2

- `rat-fliegerhorst-zuletzt` (rat): „Was hat der Rat zuletzt zum Fliegerhorst beschlossen?“ — Gold: 13.04.2026 | 13.4.2026 | 13. April 2026 | 2026-04-13 — fehlt: nicht da; keine Haushalts-Bausteine im Prompt
- `rat-fliegerhorst-zuletzt` (rat): „Was hat der Rat zuletzt zum Fliegerhorst beschlossen?“ — Gold: N-777 G | 777 G | 777G — fehlt: nicht da; keine Haushalts-Bausteine im Prompt

### `Retrieval/Beschlusskontext (verlauf/baumschutz)` — 2

- `rat-baumschutzsatzung` (rat): „Gilt die Baumschutzsatzung in Oldenburg noch?“ — Gold: bleibt bestehen | gilt weiterhin | weiterhin | bleibt in Kraft | gilt noch — fehlt: nicht da; Bausteine im Prompt: DIESE FRAGE IST ENG GESTELLT, STAND DER AKTEN, BESCHLÜSSE, FOLGEFRAGEN
- `rat-baumschutzsatzung` (rat): „Gilt die Baumschutzsatzung in Oldenburg noch?“ — Gold: 22.02.2026 | 22.2.2026 | 22. Februar 2026 | 2026-02-22 — fehlt: nicht da; Bausteine im Prompt: DIESE FRAGE IST ENG GESTELLT, STAND DER AKTEN, BESCHLÜSSE, FOLGEFRAGEN

### `Retrieval/Beschlusskontext (person/ausschuss)` — 2

- `rat-person-vorsitz-verkehr` (rat): „Wer ist Vorsitzender des Verkehrsausschusses?“ — Gold: Meerbothe — fehlt: nicht da; Bausteine im Prompt: DIESE FRAGE IST ENG GESTELLT, STAND DER AKTEN, BESCHLÜSSE, FOLGEFRAGEN
- `rat-person-vorsitz-umwelt` (rat): „Wer leitet den Ausschuss für Stadtgrün, Umwelt und Klima?“ — Gold: Rohde — fehlt: nicht da; Bausteine im Prompt: DIESE FRAGE IST ENG GESTELLT, STAND DER AKTEN, BESCHLÜSSE, WAS DIE FACHWÖRTER BEDEUTEN, FOLGEFRAGEN

### `Retrieval/Beschlusskontext (ort)` — 2

- `rat-ort-eversten-west` (rat): „Was ist zuletzt in Eversten-West beschlossen worden?“ — Gold: 24.06.2019 | 24.6.2019 | 24. Juni 2019 | 2019-06-24 — fehlt: nicht da; keine Haushalts-Bausteine im Prompt
- `rat-ort-eversten-west` (rat): „Was ist zuletzt in Eversten-West beschlossen worden?“ — Gold: 2019 — fehlt: nicht da; keine Haushalts-Bausteine im Prompt

### `Retrieval/Beschlusskontext (verwechslung/fliegerhorst)` — 1

- `rat-fliegerhorst-dreifeldhalle-kosten` (rat): „Was soll die Dreifeldhalle auf dem Fliegerhorst kosten?“ — Gold: orientierende Kosten Dreifeldhalle („knapp unter“) : 20000000 — fehlt: nicht da; Bausteine im Prompt: DIESE FRAGE IST ENG GESTELLT, ORTSFILTER, STAND DER AKTEN, BESCHLÜSSE, GEPLANT UND TATSÄCHLICH, AUFGABEN DER STADT MIT KOSTEN UND RECHTSGRUNDLAGE

### `Retrieval/Beschlusskontext (verlauf/schwimmbad)` — 1

- `rat-schwimmbad-zuletzt` (rat): „Was wurde zuletzt zum Thema Schwimmbad beschlossen?“ — Gold: einstimmig — fehlt: nicht da; Bausteine im Prompt: CHRONOLOGIE, STAND DER AKTEN, BESCHLÜSSE, AUS DEN RATSDEBATTEN, FOLGEFRAGEN

### `Retrieval/Beschlusskontext (verwechslung/schwimmbad)` — 1

- `rat-btb-zuschuss-2027` (rat): „Mit wie viel Geld unterstützt die Stadt das BTB-Schwimmbad im Jahr 2027?“ — Gold: Zuschuss BTB-Bad (Maximalbetrag) 2027: 177500 — fehlt: nicht da; Bausteine im Prompt: DIESE FRAGE IST ENG GESTELLT, STAND DER AKTEN, BESCHLÜSSE, STADTHAUSHALT, FOLGEFRAGEN

### `Lotti-Seitenblock (/council/thema)` — 1

- `lotti-thema-verkehr-zuletzt` (lotti `/council/thema`): „Was wurde hier im Verkehr zuletzt beschlossen?“ — Gold: 29.06.2026 | 29.6.2026 | 29. Juni 2026 | 2026-06-29 — fehlt: nicht da; Bausteine im Prompt: WAS DU WEISST, WAS DIE PERSON GERADE VOR SICH HAT, SO ANTWORTEST DU, WEITER, FRAGE
<!-- fakten-eval:ende -->

## Nachtrag: Lottis Seitenkontext auf den Rats-Seiten (23.09.2026)

Die Arbeitsliste oben (Stand vor dem Umbau) nannte 17 Kontextfehler in
`Lotti-Seitenblock (…)`: Auf Sitzungs-, Personen-, Orts- und Themenseiten
bekam Lotti einen Namen oder ein Datum, während die Seite Tagesordnung,
Ausschüsse und Beschlüsse zeigte. Seitdem schlägt `council/page_context.py`
über die Kennung nach, was die Seite selbst zeigt:

| Seite | vorher im Prompt | nachher zusätzlich |
|---|---|---|
| Beschluss | Titel, Abstimmung, Kurzfassung, Wortlaut (600 Z.) | Wortlaut bis 1.500 Z., Protokoll-Wortlaut zur Abstimmung (`raw_result`), finanzielle Auswirkungen der Vorlage |
| Sitzung | Gremium, Datum (ISO) | Uhrzeit, Sitzungsort, ob sie schon war, Vorsitz, öffentliche Tagesordnung mit Ergebnis und Nummer, Zahl der nichtöffentlichen Punkte |
| Person | Name | Fraktion (heute und im Verlauf), laufende und frühere Mitgliedschaften aus dem RIS, Zahl der Wortbeiträge |
| Ort | Name, Art, Beschreibung | Zahl der Beschlüsse, die jüngsten acht |
| Thema | nur ein Themenfeld-Schlüssel (die Seite zeigt aber Entitäten) | Entität mit Art, Beschreibung, erkannten Beträgen, jüngsten Beschlüssen; bei einem Feld-Schlüssel Rückblick und jüngste Beschlüsse |

Bewusst **nicht**: Pressemitteilungen auf der Beschluss-Seite (die Seite
zeigt keine, eine Verknüpfung gibt es nicht — `lotti-sechsfeldhalle-kosten`
und `lotti-stadion-wer-dagegen` bleiben Kontextfälle), Ergebnisse
nichtöffentlicher Punkte, Wortbeiträge im Wortlaut, der Haushalts-Anschluss
(Recht `budget`). Eine eigene Gremiums-Seite gibt es nicht.

Gemessen mit GPT-6 Luna über die 91 Ratsfälle, je zwei Läufe, beide Stände
mit demselben Abgleich gewertet:

| | Lotti ok | Lotti Kontextfehler | Frag den Rat ok | Kosten je Lauf |
|---|---:|---:|---:|---:|
| vorher (dev) | 19/35, 19/35 | 13, 12 | 19/56, 17/56 | 0,06 $, 0,08 $ |
| nachher | 31/35, 31/35 | 1, 2 | 18/56, 18/56 | 0,05 $, 0,04 $ |

Frag den Rat ist unverändert (derselbe Codepfad; die Schwankung ist
Rauschen). Weniger Aufrufe nachher (154 statt 170): Lotti reicht seltener ans
Archiv weiter, weil die Antwort auf der Seite steht.

Vier Abgleich-Regeln kamen dazu, alle mit Anlass aus echten Antworten
(`tests/test_fakten_abgleich.py`): `antwort_auch` (Monat und Jahr reichen in
der Antwort, wo die Frage nicht „wann“ fragt), `ausser_im_satz_mit` (die 79
Mio. € als Bürgschaft genannt sind keine Verwechslung mit dem Baupreis),
ausgeschriebene kleine Zahlen und ein geteiltes Vielfaches („von 50 auf 79
Millionen“) in Antworten. Neu gewertet ändert das am letzten Luna-Lauf oben
zwei Ratsfälle (beide Lotti, beide richtig beantwortet), keinen
Haushaltsfall.
