---
title: Bewertungs-Scores
description: Wie Ratslotse Beschlüsse gewichtet — Wichtigkeit (Heuristik), Tragweite (LLM) und Gesprächswert, und wie sie zusammenfließen.
---

Über 7.700 Beschlüsse seit 2018 lassen sich nicht chronologisch lesen. Ratslotse
gewichtet sie deshalb mit **drei getrennten Scores**, die bewusst
Verschiedenes messen: eine billige, nachrechenbare **Heuristik**, eine
LLM-Einschätzung der **Tragweite** und eine LLM-Einschätzung des
**Gesprächswerts**. Nur die ersten beiden fließen zusammen — der dritte bleibt
strikt daneben.

| Score | Spalte in `council_decisions` | Herkunft | Skala | Treibt |
|-------|------------------------------|----------|-------|--------|
| **Wichtigkeit** | `importance` | Heuristik, kein LLM (`council/importance.py`) | 0–100 | „Wichtig"-Chip, „Wichtigste zuerst", Wichtigkeits-Karte |
| **Tragweite** | `impact`, `impact_reason` | LLM nach fester Rubrik (`council/impact.py`) | 0–100 | mischt 50/50 in die Wichtigkeit, Kontext der KI-Frage |
| **Gesprächswert** | `interest`, `interest_reason` | LLM (`council/interest.py`) | 0–100 | „Fundstück des Tages", „Diese Woche im Rat", Tie-Breaks |

Alle drei sind **optional**: Ein Beschluss ohne LLM-Bewertung (`NULL`) verliert
nichts, er sortiert nur hinter den bewerteten. Datenmodell und Herkunft der
Rohdaten: [Ratsdokumente & Beschlüsse](/docs/beschluesse/).

## 1. Wichtigkeit — die Heuristik

`council/importance.py` verrechnet **vier Signale** aus bereits gescrapten
Daten. Kein LLM, kein Netz — der Score ist beliebig oft neu berechenbar und
lässt sich Zeile für Zeile nachrechnen.

| Signal | Gewicht | Rohwert 0–1 aus |
|--------|---------|-----------------|
| `geld` (`_W_MONEY`) | 0,34 | größter €-Betrag im Text (`amount_eur`), log-skaliert |
| `umstritten` (`_W_CONTENTION`) | 0,24 | Gegenstimmen / Enthaltungen, sonst das `vote`-Feld |
| `verbindlich` (`_W_BINDING`) | 0,22 | Titel-Schlagworte + Gremien-Ebene + Subvote-Abschlag |
| `aufwand` (`_W_EFFORT`) | 0,20 | Anzahl Stationen der Beratungsfolge |

### Geld

```
signal = min(1, log10(betrag + 1) / log10(50_000_000))
```

`_MONEY_CAP` = 50 Mio € ergibt den Vollausschlag; die Log-Skala staucht die
Spanne zwischen Kleinbeträgen und Großprojekten:

| Betrag | 5.000 € | 50.000 € | 500.000 € | 5 Mio € | ≥ 50 Mio € |
|--------|---------|----------|-----------|---------|------------|
| Signal | 0,48 | 0,61 | 0,74 | 0,87 | 1,0 |

Ohne erkannten Betrag (oder bei ≤ 0) **fehlt** das Signal — es zählt nicht als 0.

### Umstrittenheit

Nur aussagekräftig, wenn tatsächlich abgestimmt wurde: Bei `outcome` `NULL`,
`kein_beschluss` oder `zur_kenntnis` fehlt das Signal.

```
gegenstimmen g > 0 oder enthaltungen e > 0
    → min(1, 0.45 + 0.55 * min(1, (g + 0.5 * e) / 10))
sonst vote == "mehrheitlich"  → 0.6     (Gegenstimmen gab es, nur nicht als Zahl)
      vote == "einstimmig"    → 0.12
      sonst                   → Signal fehlt
```

Zehn Gegenstimmen (Enthaltungen zählen halb) schlagen den Deckel aus. Die
Ratsgröße kennen wir nicht zuverlässig, die Kappung ist daher heuristisch.

### Verbindlichkeit & Ebene

Das einzige Signal, das **immer** vorhanden ist — so hat jeder Beschluss
mindestens einen Beitrag.

| Titel enthält | Basiswert |
|---------------|-----------|
| `satzung`, `bebauungsplan`, `flächennutzungsplan`, `haushalt`, `doppelhaushalt`, `gebühren`, `verordnung`, `änderungssatzung` | 0,9 |
| `kenntnisnahme`, `kenntnis genommen`, `niederschrift`, `mitteilung`, `anfrage`, `einwohnerfrage`, `einwohnerfragestunde`, `resolution` | 0,1 |
| sonst (normaler Sachbeschluss) | 0,35 |

Danach zwei Korrekturen: **+0,25**, wenn der Beschluss auf Rats-Ebene fiel
(exakter Abgleich gegen `rat`, `rat der stadt oldenburg`, `verwaltungsausschuss`
— ein Teilstring-Abgleich verböte sich, weil „Beirat" und „Ortsrat" ebenfalls
„rat" enthalten), gedeckelt bei 1,0; und **×0,7** für `kind = "subvote"`, also
die Teil-Abstimmung eines größeren Punkts.

### Beratungsaufwand

```
n Stationen der Beratungsfolge ≤ 1 → Signal fehlt
sonst min(1, (n - 1) / 5)          → 6+ Stationen = Vollausschlag
```

Gezählt werden die Zeilen in `council_beratungen` zum `kvonr` des Beschlusses.

### Fehlende Signale fallen aus der Gewichtung

Der Kern der Heuristik: Ein fehlender Rohwert zählt **nicht als 0**. Die
vorhandenen Signale werden auf ihr Restgewicht **neu normiert**:

```
score = round(100 * Σ(gewicht × signal) / Σ(gewicht der vorhandenen Signale))
```

Die Konsequenz ist groß. Ein Beschluss ohne €-Betrag, ohne Abstimmungsdaten und
ohne gescrapte Beratungsfolge hat nur die Verbindlichkeit (Wert 0,6):

```
mit Normierung:   100 × (0,22 × 0,6) / 0,22  = 60
0 statt „fehlt":  100 × (0,22 × 0,6) / 1,00  = 13
```

Ohne Normierung würde jeder Beschluss dafür bestraft, dass ein Datum fehlt —
und die Rangfolge spiegelte vor allem die Vollständigkeit unserer Daten wider,
nicht die Bedeutung des Beschlusses.

### Aufschlüsselung (`importance_breakdown`)

`importance_breakdown()` liefert neben `score` und den Roh-`signals` (auf drei
Nachkommastellen gerundet, fehlende als `null`) auch `contributions`: den
**gewichteten Punkte-Beitrag je Signal**, dessen Summe exakt dem Score
entspricht. Weil die UI diese Zahlen sichtbar addiert, wird der Rundungsrest
nach dem **Größte-Reste-Verfahren** verteilt statt jeden Beitrag einzeln zu
runden — sonst ergäbe die angezeigte Spalte mal 80, mal 82 statt 81. Das speist
die aufklappbare Wichtigkeits-Karte auf der Beschluss-Seite.

## 2. Tragweite — LLM nach fester Rubrik

`council/impact.py` lässt ein LLM bewerten, **wie folgenreich** ein Beschluss
für die Stadt ist. Der Prompt (`impact_bewertung_system` in `nwz/prompts.py`,
über das Admin-UI editierbar) gibt vier Rubriken zu je 0–25 Punkten vor, die
addiert werden:

| Rubrik | Frage |
|--------|-------|
| ① Betroffene | Wie viele Menschen, wie direkt? (ganze Stadt > Quartier > Einzelfall) |
| ② Geld | absolut und relativ zum städtischen Haushalt |
| ③ Bindungswirkung | Satzung/Grundsatzbeschluss/Vertrag mit langer Laufzeit > einmalige Maßnahme > bloße Kenntnisnahme |
| ④ Präzedenz/Strategie | Stellt der Beschluss Weichen für viele Folgeentscheidungen? |

Kuriosität, lustige Namen, Unterhaltungswert und Medienecho sind **ausdrücklich
ausgenommen** — dafür gibt es den Gesprächswert. Zur Kalibrierung nennt der
Prompt Anker-Gesamtwerte: Formalie/Gremienbesetzung ≈ 5, Kenntnisnahme eines
Berichts ≈ 20, Maßnahme an einer einzelnen Straße ≈ 35, Bebauungsplan für ein
Quartier ≈ 70, Haushaltssatzung oder stadtweite Grundsatzentscheidung ≈ 95.

Neben Titel und Beschlusstext-Auszug (600 Zeichen) bekommt das Modell
**Struktur-Signale** mit: Art, Ergebnis, Gremium, Betrag und die Länge des
Beschlusstexts. Bewertet wird in Batches von 20 (`BATCH_SIZE`), im JSON-Mode,
bei `temperature=0.1`. Zurück kommen je Beschluss ein `score` und ein `grund` —
**ein Satz**, der die stärkste Rubrik benennt. Halluzinierte IDs und Werte
außerhalb 0–100 verwirft der Parser; `save_impact` klemmt zusätzlich auf 0–100
und schneidet die Begründung bei 300 Zeichen ab. Der Satz erscheint als
„Warum wichtig: …" auf der Beschluss-Seite.

Modell: `COUNCIL_IMPACT_MODEL` (Default `deepseek/deepseek-v4-pro`), wie alle
LLM-Aufrufe über OpenRouter ([ADR 0001](/docs/adr/0001-openrouter/)).

## 3. Gesprächswert — bewusst nicht Wichtigkeit

`council/interest.py` misst etwas ganz anderes: Wie **erzählenswert** ist ein
Beschluss für normale Stadtbewohner:innen? Der Prompt
(`interest_bewertung_system`) fragt nach Gesprächswert („Würde man es beim
Abendessen erzählen?"), Alltagsnähe, Kuriosität/Überraschung und Konkretheit
(ein Ort, ein Ding, ein Datum) und staffelt die Skala:

| Band | Bedeutung |
|------|-----------|
| 0–25 | Geschäftsordnung, Gremienbesetzung, Satzungs-Formalien, reine Kenntnisnahmen |
| 30–55 | solide Sachbeschlüsse ohne Erzählwert |
| 60–85 | konkret, alltagsnah, erzählbar |
| 90–100 | kurios oder stadtbekannt |

Auch hier: Batches von 20, JSON-Mode, `temperature=0.2`, Auszug 500 Zeichen,
Modell über `COUNCIL_INTEREST_MODEL`. Der Score wird **nie** in die Wichtigkeit
gemischt — schräge Straßennamen sollen oben landen dürfen, ohne als Priorität
durchzugehen. Genau diese Erfahrung aus dem Interest-Lauf war der Anlass für die
Tragweite mit ihrer festen Rubrik.

### Fundstück des Tages

`council/fundstueck.py` kuratiert daraus je Kalendertag **einen** Archiv-Fund
(Tabelle `council_fundstuecke`, ein Datensatz je Tag mit Kicker und
1-Satz-Story):

- **Jahrestage gewinnen**: gleicher Kalendertag, früheres Jahr, `interest ≥ 45`
  (`MIN_INTEREST_ANNIVERSARY`) → Kicker „Heute vor N Jahren".
- Sonst ein Archiv-Fund mit `interest ≥ 60` (`MIN_INTEREST_ARCHIVE`) → Kicker
  „Aus dem Archiv". Unter den Top-10-Kandidaten wählt ein **Hash des Datums**
  (kein Zufall) — Läufe sind wiederholbar und Resume-sicher.
- Zuletzt gezeigte Beschlüsse sind 180 Tage gesperrt (`REUSE_BLOCK_DAYS`).
- Ein LLM schreibt die Story (ein Satz, ≤ 200 Zeichen laut Prompt, > 260 Zeichen
  werden verworfen). Ohne brauchbare Story bleibt der Tag leer — das Frontend
  lässt die Karte dann ersatzlos weg.

## Die Mischung: 50/50 — an zwei Stellen

Wichtigkeit und Tragweite werden zu gleichen Teilen gemittelt. Der Code steht
**zweimal** da, absichtlich:

```python
# council/store.py — backfill_importance(), schreibt council_decisions.importance
if d.get("impact") is not None:
    score = round((score + int(d["impact"])) / 2)
```

```python
# web/backend/app/routers/council.py — decision_detail(), Read-Layer
bd["base_score"] = bd["score"]
if d.get("impact") is not None:
    bd["impact"] = int(d["impact"])
    bd["score"] = round((bd["base_score"] + bd["impact"]) / 2)
```

Der Grund: Die **Liste** liest den persistierten Wert aus der Spalte
`importance`, die **Detailseite** rechnet die Heuristik live neu (nur so
entstehen die Signal-Aufschlüsselung und die Beitragszahlen). Ohne die zweite,
identische Mischung zeigten beide Ansichten verschiedene Zahlen für denselben
Beschluss. Die API behält `base_score` (Heuristik) und `impact` einzeln, damit
die Beschluss-Seite die Rechnung offenlegen kann — die vier Signal-Balken
erklären ja nur die Heuristik-Hälfte, nicht den gemischten Endwert.

Solange `impact` `NULL` ist, greift die Mischung **nicht**: Vor dem ersten
`rate_impact`-Lauf bleibt alles exakt die reine Heuristik. Das macht den Rollout
gefahrlos.

## Beispiel: Beschluss 7070

„Zukunft der Fahrradstraßen Haareneschstraße" zeigt alle drei Mechanismen auf
einmal — fehlende Signale, Normierung, Mischung:

```
Signale
  geld          fehlt      (kein €-Betrag im Text)
  umstritten    1,00       (Gegenstimmen ausreichend für den Vollausschlag)
  verbindlich   0,60       (0,35 normaler Sachbeschluss + 0,25 Rats-Ebene)
  aufwand       fehlt      (keine mehrstufige Beratungsfolge)

Gewichte der vorhandenen Signale: 0,24 + 0,22 = 0,46  → neu normiert

Beiträge (contributions)
  Umstrittenheit           52
  Verbindlichkeit & Ebene  29
                          ───
  Heuristik (base_score)   81

Tragweite (LLM)            38
  „Konkrete Einzelmaßnahmen für ein Quartier (Fahrradstraßen),
   Effekte lokal begrenzt."

Angezeigte Wichtigkeit  (81 + 38) / 2 = 60
```

Lesart: Weil zwei von vier Signalen fehlen, tragen Umstrittenheit und
Verbindlichkeit das volle Gewicht — die Heuristik landet bei 81 und wirkt damit
auf Rang eines Großprojekts. Die Tragweite korrigiert das auf 38 (ein Quartier,
keine stadtweite Wirkung), und der angezeigte Wert von 60 liegt genau
dazwischen. Genau dafür gibt es die zweite Meinung.

## Betrieb

| Skript | Rechnet | Täglich in `check_protocols.py` | Wöchentlich in `weekly_enrich.py` |
|--------|---------|--------------------------------|-----------------------------------|
| `scripts/rate_interest.py` | Gesprächswert (LLM) | `limit=200, workers=2` | `--limit 500` |
| `scripts/rate_impact.py` | Tragweite (LLM) | `limit=200, workers=2` | `--limit 500` |
| `scripts/score_importance.py` | Wichtigkeit + Mischung | ja, als direkter `backfill_importance()`-Aufruf ohne Limit | ja, voller Lauf |
| `scripts/generate_fundstuecke.py` | Fundstück-Karten | — | `--days 21` |

- **Reihenfolge zählt:** Tragweite läuft in beiden Jobs **vor** dem
  Wichtigkeits-Score, damit die 50/50-Mischung frische Werte sieht.
- **Täglich klein, wöchentlich als Backstop:** Beide LLM-Queries liefern
  „neueste zuerst", das Tageslimit von 200 trifft also den Tageszuwachs. An
  Tagen ohne neue Protokolle ist der Schritt ein No-op (0 LLM-Aufrufe). Den
  Alt-Bestand seit 2018 arbeiten die 500er-Wochentranchen ab.
- **Auswahlkriterien:** `decisions_needing_interest` nimmt nur
  `kind = 'decision'`, `decisions_needing_impact` auch `subvote`; beide
  verlangen einen Titel ab 8 Zeichen und überspringen bereits bewertete Zeilen.
- Die Wichtigkeits-Neuberechnung ist reine Heuristik (kein LLM, kein Netz) und
  läuft deshalb täglich über den **kompletten** Bestand — so tragen frische
  Beschlüsse ihre Scores tagesaktuell.
- Alle Cron-Jobs laufen in `run_guarded` (`nwz/alerts.py`): Ein Crash wird
  geloggt und per E-Mail gemeldet.

## Qualitätssicherung: das Golden-Set-Gate

Die Tragweite ist der einzige Score, der in einen angezeigten Wert
hineinmischt — sie bekommt darum ein Gate vor dem Rollout.
`scripts/eval_impact.py` hält **30 handbewertete Beschlüsse**
(`scripts/golden_impact.json`) gegen die LLM-Bewertung. Jeder Eintrag trägt ein
Erwartungs-**Band** (z. B. `[0, 15]` für eine Formalie) und eine Klasse; die
Zuordnung läuft über einen Titel-`LIKE`.

Bestanden gilt bei **beidem**:

| Kriterium | Schwelle | Konstante |
|-----------|----------|-----------|
| Spearman-Rangkorrelation (Band-Mitte gegen LLM-Score) | ≥ 0,7 | `RHO_MIN` |
| Band-Trefferquote (Score liegt im erwarteten Band) | ≥ 70 % | `HIT_MIN` |

Liegen weniger als 20 bewertete Golden-Beschlüsse vor, bricht das Skript
ebenfalls mit Exit 1 ab — zu wenig für ein Urteil. `--rate-missing` bewertet
vorab nur die Golden-Beschlüsse (zwei LLM-Batches, entsprechend billig), sodass
die Prüfung dem großen Backfill vorausgehen kann.

Der Ops-Workflow `.github/workflows/ops-tragweite-rollout.yml`
(`workflow_dispatch`, keine Inputs) macht daraus die Rollout-Reihenfolge: erst
`eval_impact.py --rate-missing`, und **nur bei Bestehen** startet der
Voll-Backfill (`rate_impact.py` über alle Beschlüsse ohne `impact`) mit
anschließendem `score_importance.py`. Der Voll-Lauf läuft per `nohup`
serverseitig weiter. Fällt das Gate durch, bricht der Workflow ab — Prompt
nachschärfen statt einhängen. Das restliche Eval-Harness beschreibt
[Eval-Harness](/docs/eval/).

## Wo die Scores in der App auftauchen

- **„Wichtig"-Chip** in Beschluss-Listen: ab **55** sichtbar, ab 70 kräftiger
  gefärbt; bei Subvotes nie. Der Tooltip erklärt die Zusammensetzung.
- **Wichtigkeits-Karte** auf der Beschluss-Seite: Score + Balken immer sichtbar,
  auf Klick die Aufschlüsselung — Stärke je Signal als Balken, der Beitrag als
  Zahl (`+52`), fehlende Signale als „keine Daten", darunter die offene
  Rechnung „Aus den Ratsdaten / Tragweite (KI-Einschätzung) / Wichtigkeit ·
  Mittel aus beiden". Die Kopfzeile trägt zusätzlich einen
  „Wichtig · N/100"-Chip ab 55.
- **Sortierung** „Wichtigste zuerst" (`sort=importance`) auf `/council`. Sie
  gewichtet den Wert mit der **Aktualität**: `importance / (1 + Alter/2 Jahre)`.
  Ohne diese Dämpfung bestand die Liste praktisch nur aus Haushaltsbeschlüssen —
  die tragen strukturell die höchste Tragweite und verdrängten alles Aktuelle.
  Bewusst hyperbolisch statt exponentiell, damit historische Großbeschlüsse nach
  hinten rutschen, aber auffindbar bleiben. Noch nicht bewertete Beschlüsse
  landen am Ende. Der Gesprächswert hat **keine** eigene Sortierung mehr — als
  Suchkriterium war er wenig sinnvoll; er wirkt weiter über das Fundstück, die
  Wochenkarte und Tie-Breaks. Der API-Wert `sort=interest` bleibt bestehen,
  damit ältere geteilte Links nicht brechen.
- **Fundstück des Tages** auf der Übersicht (`GET /council/fundstueck`) sowie
  die Karte „Diese Woche im Rat" (`GET /council/diese-woche`), die den
  interessantesten Beschluss der letzten 7 Tage samt `interest_reason`-Satz
  zeigt, wenn es keine persönlichen Treffer gibt.
- **KI-Frage** (`council/qa.py`): Die Tragweite geht nur an den **Enden der
  Skala** in den Kontext — ab **70** als „Tragweite: hoch" samt Begründung, bei
  **≤ 15** als „Tragweite: gering (Formalie)". Das Relevanz-Ranking der
  Kandidaten bleibt davon unberührt; der Hinweis steuert nur, womit die Antwort
  führt und was sie überspringt.
- **Quiz**: Bei den „ratspolitik"-Fragen werden Beschlüsse mit `interest ≥ 60`
  zuerst gezogen, innerhalb dessen nach Wichtigkeit — so drehen sich die Fragen
  um bedeutsame *und* interessante Beschlüsse statt um Formalien.

Wie diese Scores in die übrigen LLM-Schritte eingebettet sind, zeigt die
[KI-Pipeline](/docs/ki-pipeline/).
