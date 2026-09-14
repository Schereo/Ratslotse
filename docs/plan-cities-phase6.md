# Umsetzungsplan Phase 6: Niedersachsen auswerten — und was der Vergleich noch braucht

Stand: 12.09.2026, abends. Dieser Plan folgt auf
[`plan-cities-phase5.md`](plan-cities-phase5.md) und ist wie seine Vorgänger
geschrieben: **ohne das Gespräch dahinter ausführbar**. Jeder Abschnitt ist
ein Pull Request, nennt Dateien, Signaturen, Tests, Kosten und woran man
erkennt, dass er fertig ist. Wo etwas gemessen ist, steht die Zahl und in
Anhang C der Befehl, der sie liefert.

Wer das umsetzt, liest **vorher** vollständig: die Wurzel-`CLAUDE.md`,
`council/CLAUDE.md`, **`council/cities/CLAUDE.md`** (Rezept für eine neue
Stadt, „ein Adapter je Ratsinformationssystem", die Hannover- und
Hildesheim-Abschnitte), `scripts/CLAUDE.md`, `tests/CLAUDE.md`, §0 der fünf
Vorgängerpläne (Regeln 1–23 gelten unverändert) und die Docstrings von
`council/cities/store.py::raw_objects`, `pipeline.py::extract_inline`,
`adapters/allris4_html.py`, `adapters/allris_classic.py`,
`adapters/hannover_sim.py` sowie `tests/test_cities_extract_inline_dispatch.py`
und `tests/test_cities_store_wal.py` — die beiden Wächter dieser Woche.

## 0. Die Richtung, die Tim vorgegeben hat

Am 12.09.2026, nach der Ernte der drei niedersächsischen Städte:

> Hildesheim können wir erstmal ausklammern, das wird wahrscheinlich noch ein
> bisschen dauern, bis das System wieder zurück ist. Wie kommen wir jetzt mit
> den Daten weiter, die wir bisher haben? Fehlen Daten, die wir abrufen
> müssen? Sollten wir noch den Adapter verbessern, was da vorgeschlagen ist?
> Wie können wir die Daten weiter auswerten, was fehlt uns noch? Und
> Vorschläge, wie wir das ganze Feature besser machen können.

Dazu vier Regeln, die diese Woche gemessen wurden und ab jetzt gelten:

24. **Ein Dialekt mit `inline_texts` steht an ZWEI Stellen** — in seiner
    Adapter-Datei und im Dispatcher von `pipeline.extract_inline`. Zwei
    gemergte Adapter hatten diesen Eintrag nie; 25.729 Vorlagen standen ohne
    einen Satz Text da, ohne Fehler (#1289). Der Wächter
    `test_cities_extract_inline_dispatch.py` hält das jetzt, in beide
    Richtungen.
25. **Kein Cursor bleibt über die Aufrufer-Schleife offen.** Ein Leser hält
    in WAL-Modus einen Snapshot, solange der steht, wird nicht eingecheckt —
    362 MB WAL, Durchsatz von 343 auf 8 Vorlagen je Stunde, ohne Fehler
    (#1300, #1301). Wer eine Abfrage als Generator schreibt, liest erst die
    Kennungen mit `fetchall()` und holt dann je Zeile.
26. **Ein „hängt"-Befund gilt erst mit einem Timeout, der LÄNGER ist als die
    Geduld der Gegenstelle.** Ein 12-Sekunden-`curl` machte aus einem
    gewöhnlichen `502 Proxy Error` (nach 30 s) eine „gezielte Sperre gegen
    unsere Kennung". Die Gegenprobe aus einem fremden Netz (Tims Browser)
    entschied es in einer Zeile.
27. **Vor jedem Bestandslauf stehen Fenster, Kandidatenzahl und Kosten
    schriftlich da.** Hannover trägt 24.654 Kandidaten seit 2017; die fünf
    OParl-Städte beginnen 2023. Ungefenstert kostete Hannover allein rund
    $75 und verglich acht Jahre gegen drei.

## 1. Zielbild

Nach dieser Phase liegen **Hannover** (535 k Einwohner) und **Wolfsburg**
(125 k) im Vergleich wie die fünf OParl-Städte: klassifiziert, indiziert,
geclustert, mit `fit`-Urteil, auf der Ideen-Liste und im Block „Anderswo
beschlossen". Wolfsburgs 3.228 Protokoll-Abschnitte tragen — wenn der
`reason`-Prüfstand es zulässt — das „Warum". Hildesheim folgt, sobald sein
ALLRIS wieder antwortet; die Ernte setzt dann auf 5.369 bereits gespeicherten
Rohobjekten auf, nicht bei null. Die Rohablage hat einen Wächter, der eine
sterbende Ernte nach Minuten meldet statt nach elf Stunden.

Was sich für Nutzer*innen ändert: Die Liste „Ideen aus anderen Städten"
zeigt zum ersten Mal, was **die größte niedersächsische Stadt** beschlossen
hat und Oldenburg fehlt — unter demselben Landesrecht, mit demselben
Instrumentenkasten (Drucksache, Antrag, Anfrage) wie Oldenburg selbst.

## 2. Was gemessen ist und den Plan trägt

Alle Zahlen vom 12.09.2026 gegen `data/cities.sqlite` (Anhang C).

### 2.1 Stand je Stadt — die drei Neuen sind geerntet, aber nicht ausgewertet

| Stadt | Dialekt | Vorlagen | m. Text | m. Ergebnis | Abschnitte | Annotationen | aktiv |
|---|---|---:|---:|---:|---:|---:|---|
| Oldenburg | oldenburg | 5.945 | 86 % | 81 % | — | 6.134 | an |
| Braunschweig | allris4 | 6.024 | 100 % | 48 % | 121 | 14.247 | an |
| Osnabrück | allris4 | 2.996 | 100 % | 80 % | 159 | 4.561 | an |
| Potsdam | allris4 | 6.010 | 100 % | 38 % | 81 | 15.163 | an |
| Münster | session | 3.011 | 92 % | 64 % | 291 | 7.024 | an |
| Magdeburg | session | 6.782 | 100 % | 67 % | 277 | 16.788 | an |
| **Hannover** | hannover_sim | **25.729** | **100 %** | 58 % | 0 | **0** | aus |
| **Wolfsburg** | allris4_html | 1.570 | 72 % | 93 % | **3.228** | **0** | aus |
| **Hildesheim** | allris_classic | 1.078 (Teil) | 100 % | 96 % | **2.805** | **0** | aus |
| Langenhagen | allris4 | 708 | 0 % | 58 % | — | 0 | aus |
| Peine | allris4 | 399 | 0 % | 21 % | — | 0 | aus |

Die Auswertungsstufen (`annotate` → `index` → `cluster` → `fit`) sind für
die drei niedersächsischen Städte **nie gelaufen** — `cities_backfill.py`
und `check_cities.py` nehmen nur `active_bodies()`. Das ist richtig so (kein
bezahlter Lauf ohne Entscheidung), heißt aber: Auf der Karte und in der
Liste existiert Niedersachsen außer Oldenburg heute nicht.

### 2.2 Hannover: viel, sauber, und zwei Eigenheiten, die man kennen muss

**25.729 Vorlagen, alle mit Text** (nach #1289), 2.603 Sitzungen, 41.082
Beratungen, 47 Gremien. Die Ergebnisquote von 58 % täuscht:

| Art | Vorlagen | mit Ergebnis |
|---|---:|---:|
| motion (Antrag) | 11.576 | 74 % |
| inquiry (Anfrage) | 6.483 | **1 %** |
| proposal (Drucksache) | 4.473 | 83 % |
| amendment | 2.122 | 70 % |
| report | 1.075 | 93 % |

Anfragen werden in Hannover beantwortet, nicht beschlossen — die 1 % sind
kein Fehler, sondern die Sache selbst. **Ohne Anfragen liegt Hannover bei
77 %**, zwischen Münster und Osnabrück. Die Liste filtert `inquiry` ohnehin
nicht als Idee (PR 24, „nur Vorgeschlagenes"); nichts zu reparieren, aber
eine Zahl, die man sonst falsch liest.

**4.840 Beratungen ohne Sitzung** — das ist der Verwaltungsausschuss, der
keine Sitzungsseite veröffentlicht (`council/cities/CLAUDE.md`). Datum und
Ergebnis liegen vor, Sitzung und Gremium bewusst nicht.

**Das Fenster:** Hannover trägt Vorlagen seit 2017 (`since=2018-01-01` in der
Registry, plus 42 Nachzügler), die fünf OParl-Städte seit 2023. Kandidaten
für `fit` (motion/proposal/inquiry/amendment): **24.654 gesamt, 9.277 ab
2023.** Die Auswertungsstufen kennen heute **kein** Datumsfenster — `since`
wirkt nur auf `fetch` (`pipeline.py:101`, `cities_backfill.py:165`). Ohne PR
39 liefe der Bestandslauf über alle 24.654 und verglichene acht Jahre
Hannover mit drei Jahren Braunschweig.

**Kein „Warum"** für Hannover, und das bleibt so: Die Niederschriften liegen
hinter den TOPS-Seiten, die die Stadt selbst als vertraulich kennzeichnet
(Regel in `council/cities/CLAUDE.md`). Ergebnisse kommen aus der
Beratungsfolge; das ist ehrlich und reicht für Liste und Block.

### 2.3 Wolfsburg: zwei Adapter-Fehler, beide stumm, beide in der Rohablage heilbar

`allris4_html` wurde an **Laatzen** gebaut und gemessen (Fixtures
`laatzen_to010.html`, `laatzen_vo020.html`); Wolfsburg hat **kein
Fixture** — gegen Regel 23 und Schritt 5 des Rezepts. Die Ernte lief trotzdem
und legte 1.570 Vorlagen ab. Zwei Dinge daran sind falsch:

1. **883 von 1.570 Vorlagen (56 %) sind „other"**, und ihr `paper_type_raw`
   ist ein 400-Zeichen-Blob: „Vorlage Federführende Organisationseinheit:
   Geschäftsbereich Finanzen Beteiligte Organisationseinheit: … Beratungsfolge
   …". Ursache in `_kopf()` (`allris4_html.py:113`): Die Feldgrenzen kennen
   `Federführend:` — Wolfsburg schreibt `Federführende Organisationseinheit:`
   und `Beteiligte Organisationseinheit:`. Der Wert von `Vorlageart` läuft
   bis zur nächsten bekannten Grenze weiter, also bis zum Seitenende.
   **Dieselbe Falle wie Hildesheims `Verfasser:`** — ein Feld, das man nicht
   will, muss trotzdem als Grenze in der Regel stehen.
2. **1.570 von 1.570 Vorlagen ohne Datum.** Die Beratungsfolge rendert
   Wolfsburg in englischem Datumsformat („Sep 28, 2023", „May 13, 2026");
   `_iso()` (`allris4_html.py:123`) kennt nur `TT.MM.JJJJ`. Ohne Datum
   greift kein Fenster, und die Karte zeigt „undatiert".

Beides steht in der **Rohablage bereits richtig** — es ist ein
Normalisierungsfehler, kein Ernte-Fehler. Nach dem Fix genügt
`--stage normalize`, kein einziger Abruf.

Was Wolfsburg wertvoll macht: **3.228 Protokoll-Abschnitte** aus 369
Niederschriften (`split_protocols`, PR 32) — mehr als alle fünf OParl-Städte
zusammen (929), und **1.464 von 1.570 Vorlagen mit Ergebnis (93 %)**.

### 2.4 Hildesheim: geparkt, aber nicht verloren

Die Ernte lief am 11.09. elf Stunden und brach nicht ab — sie wurde durch den
WAL-Fehler (Regel 25) immer langsamer, und um 16:13 fiel ALLRIS selbst aus.
Stand 12.09. 18:00: `502 Proxy Error` nach 30 s auf jeder `/allris/`-Adresse,
auch im Browser, während `stadt-hildesheim.de` in 0,2 s antwortet. **Nicht
unsere Kennung, nicht unser Code** — die Anwendung hinter dem Proxy ist tot.

In der Rohablage liegen **49 Gremien, 1.089 Sitzungen, 1.078 Vorlagen, 3.153
Auszüge**; normalisiert und extrahiert am 12.09.: 1.076 von 1.078 mit Text,
1.034 mit Ergebnis, 2.805 Abschnitte, Plausibilitätsprüfung ohne Befund.
Der Kalender reicht bis 2007; wie viele Vorlagen noch fehlen, weiß niemand
— die Ernte lief rückwärts durch die Historie und war bei den Vorlagen der
Jahre 2022–2024, als sie ausfiel.

**Wiederaufnahme** (Anhang C, Befehl 6): erst ein einzelner Abruf mit
`-m 90`, dann derselbe `--run`-Befehl wie am 11.09. — `put_raw_object` legt
nur Neues an, die 5.369 bleiben. Danach `--stage normalize --stage extract`
und `--pruefen`.

Zwei der 1.078 Vorlagen haben keinen Text, obwohl er in der Seite steht:
`_sachverhalt()` (`allris_classic.py:683`) sucht wörtlich `"Sachverhalt:"`,
die beiden schreiben `Sachverhalt` ohne Doppelpunkt bzw. `Sachverhalt :`.
Gemessen: 1.076 strikt, je 1 pro Abweichung — 0,2 %. Klein für Hildesheim,
aber die Regel gilt für jede ALLRIS-classic-Stadt.

### 2.5 Das „Warum": der größte ungenutzte Bestand liegt in Niedersachsen

| Stadt | Abschnitte in `protocol_sections` |
|---|---:|
| Wolfsburg | 3.228 |
| Hildesheim | 2.805 |
| Münster | 291 |
| Magdeburg | 277 |
| Osnabrück | 159 |
| Braunschweig | 121 |
| Potsdam | 81 |

**6.033 gegen 929.** Der Annotator `reason` (PR 33) steht auf
`active=False`. Das Golden Set, das ihm fehlte, **existiert inzwischen**:
`eval/cases_cities_reason.json`, 36 Abschnitte, alle `geprueft=True`, 11 mit
Begründung. Der Prüfstand am 12.09. (`deepseek-v4-flash`, $0,012):

| Schranke | gemessen | Schwelle |
|---|---|---|
| Erfundene Begründungen (`grounded=true` ohne Text) | **1** | 0 |
| Abstimmungsergebnis richtig | **80 %** von 15 | 90 % |
| Personennamen | 0 | 0 |
| Begründung gefunden | 5 von 11 | (kein Kriterium) |

**Nicht bestanden — aber die Abweichungen sehen nach dem Prüfstand aus,
nicht nach dem Modell:** Drei der `vote`-Fehler sind Formatvergleiche
(„mit 6 Ja-, 34 Neinstimmen und 5 Enthaltungen" gegen „6 Ja, 34 Nein, 5
Enthaltungen (Änderungsantrag); 7 Ja, 3 …" — dieselben Zahlen, zwei
Abstimmungen im Abschnitt), einer ist echt („0 Ja, 42 Nein" gegen „41 Ja,
0 Nein" — vermutlich ein falsch geschnittener Abschnitt), einer vergleicht
gegen `None`. Der eine „erfundene" Fall ist am 10.09. schon einmal als
Prüfstand-Fehler entlarvt worden. **Regel 22 bleibt:** Erst wenn der Maßstab
stimmt und das Modell ihn hält, läuft `reason` — dann aber über 6.033
Abschnitte für rund $3.

### 2.6 Kosten, gemessen an `llm_usage` (12.09.)

| Aufruf | Modell | $ je 1.000 Aufrufe | je Vorlage |
|---|---|---:|---|
| `cities_classify` | deepseek-v4-flash | 1,15 | 1 Aufruf je Vorlage |
| `cities_effort` | deepseek-v4-flash | 0,82 | 1 je Kandidat |
| `cities_fit` | deepseek-v4-flash | 0,58 | **3** je Kandidat (Mehrheit) |
| `cities_evidence_terms` | gemini-2.5-flash-lite | 0,03 | 1 je Kandidat |
| `cities_stance` | deepseek-v4-flash | 0,31 | 1 je Idee mit Cluster |
| `cities_cluster_check` | deepseek-v4-flash | 0,31 | 1 je Cluster |
| `cities_reason` | deepseek-v4-flash | 0,48 | 1 je Abschnitt |

Daraus für den Bestandslauf (PR 40), **mit** Fenster ab 2023:

| Stadt | Vorlagen (Fenster) | Kandidaten | classify | effort + terms | fit | Summe |
|---|---:|---:|---:|---:|---:|---:|
| Hannover | 9.725 | 9.277 | $11 | $8 | $16 | **≈ $35** |
| Wolfsburg | ≈ 1.570 (nach PR 37 datiert) | ≈ 330 | $2 | $0,3 | $0,6 | **≈ $3** |
| Hildesheim (Teil) | 993 | 839 | $1 | $0,7 | $1,5 | **≈ $3** |

Ohne Fenster läge Hannover bei ≈ $75 (25.729 classify, 24.654 × 3 fit).
Embeddings (`index`) laufen lokal mit fastembed: Hannover ≈ 3–4 h CPU
(30.673 Vorlagen brauchten 34 Minuten für 85.256 Chunk-Vektoren; Hannover
verdoppelt den Bestand), kein Geld.

### 2.7 Was sonst gemessen ist

- **Das Golden Set für die Liste** (`eval/cases_cities_list.json`) hat 100
  Fälle und **null Urteile** (`on_list` überall `None`). Es ist der einzige
  Maßstab, den sich das Modell nicht selbst schreiben darf, und der
  Feature-Schalter `ideen-anderswo` nennt genau das als `fertig_wenn`.
- **Potsdams 38 % Ergebnisquote** sind strukturell: 2.808 Vorlagen ohne
  Beratung sind `answer` (1.422) und `inquiry` (1.386). Keine Lücke.
- **Langenhagen und Peine** haben 0 % Text, weil je 4 Dateien geholt wurden
  (`files` mit Bytes: 4 von 705 bzw. 4 von 285) — die Ernte lief ohne
  Dateien. 1.100 Abrufe, kein Adapter-Problem.
- **dev.ratslotse.de** trägt den Stand vom 10.09. (30.673 Vorlagen); die drei
  niedersächsischen Städte gibt es nur lokal. **Prod** fährt den Sonntags-Cron
  über `active_bodies()` — solange niemand aktiviert, passiert dort nichts
  Neues.
- `--pruefen` prüft **alle** Städte in der Datenbank, nicht nur aktive
  (`pruefung.py:105` über `main.stats()`); Hildesheim und Wolfsburg wurden
  also mitgeprüft, ohne Befund.

## 3. Die Reihenfolge, und warum

1. **Erst die Adapter (PR 37, 38), dann das Fenster (39), dann der
   Bestandslauf (40).** Wolfsburg ohne Datum und mit 56 % „other" durch
   `classify` zu schicken, hieße $2 für Urteile über Vorlagen, deren Art der
   Adapter nicht kennt — und anschließend ein zweiter Lauf. Das Fenster
   entscheidet über $35 oder $75.
2. **Der Ernte-Wächter (41) vor der nächsten langen Ernte** — also vor
   Hildesheims Wiederaufnahme und vor dem ersten Cron-Lauf über Hannover.
3. **`reason` (42) parallel dazu**, es hängt an nichts: Der Prüfstand ist
   eine Handdurchsicht plus ein Vergleich, der Zahlen statt Zeichenketten
   vergleicht.
4. **Die Karte (43) zuletzt**, wenn feststeht, was sie zeigen kann.
5. **Tims Urteile (44) jederzeit** — sie blockieren keinen PR, aber den
   Schalter.

## PR 37 — Wolfsburg: Feldgrenzen, englische Daten, ein echtes Fixture

**Warum.** 56 % „other", 100 % undatiert, beides in der Rohablage heilbar
(§2.3). Und ein Adapter, der an einer Stadt gebaut und an einer anderen
betrieben wird, braucht von beiden ein Fixture.

**Was sich ändert.**

1. `council/cities/adapters/allris4_html.py::_kopf`: Die Feldliste bekommt
   `Federführende Organisationseinheit` und `Beteiligte Organisationseinheit`
   als **Grenzen** (sie werden nicht gespeichert, wie `Verfasser`). Der
   Kommentar dort nennt die Falle beim Namen — dieselbe wie `_GRENZEN` in
   `allris_classic.py`, und der Grund, warum eine Grenze auch ohne Wert in
   der Regel stehen muss.
2. `_iso()` versteht zusätzlich `Mon D, YYYY` (englische Monatsnamen, wie
   Wolfsburgs Beratungsfolge sie rendert). Kein Locale-Umschalten — eine
   zweite Regex, die vor der deutschen probiert wird oder danach; die
   deutsche Form bleibt Vorgabe.
3. `tests/fixtures/cities/wolfsburg_vo020.html`: ein **gekürzter, sonst
   unveränderter** Abzug einer echten Vorlagenseite (ohne Personen), dazu
   `wolfsburg_to010.html`, wenn die Sitzungsseite eine eigene Form hat.
   Rezept Schritt 5: „Ein selbstgebautes Beispiel hätte genau die Eigenheiten
   nicht, an denen der Probelauf scheitert."
4. Danach lokal `python scripts/cities_backfill.py --run --body wolfsburg
   --stage normalize --stage extract` — **kein `fetch`**.

**Test.** `tests/test_cities_allris4_html.py`: Wolfsburgs Vorlage bekommt
`kind != "other"` und ein ISO-Datum aus „Sep 28, 2023"; Laatzens Fixture
bleibt unverändert grün (das ist die Gegenprobe, dass die neue Grenze nichts
Bestehendes verschluckt).

**Messung.** `kind='other'` in Wolfsburg von 883 auf **unter 160** (10 %);
`date IS NULL` von 1.570 auf **unter 20**. `--pruefen` ohne neuen Befund.

**Kosten.** Kein Modell, kein Abruf. Ein halber Tag.

## PR 38 — Hildesheim: der Sachverhalt ohne Doppelpunkt

**Warum.** 0,2 % bei Hildesheim, aber `_sachverhalt()` gilt für jede
ALLRIS-classic-Stadt, und die nächste schreibt vielleicht öfter so.

**Was sich ändert.** `council/cities/adapters/allris_classic.py::_sachverhalt`
sucht **erst** die strikte Form `Sachverhalt:` (wie heute); nur bei
Fehlanzeige eine lockere `\bSachverhalt\s*:?\s` am Zeilen- oder
Blockanfang. Die Reihenfolge ist der Schutz: Das Wort kommt im Fließtext vor
(„zum Sachverhalt befragt"), die strikte Form gewinnt immer, wenn sie da ist.

**Test.** Zwei Fixtures aus den beiden echten Fällen (22/395, 24/019 — beide
Mitteilungsvorlagen ohne Personen im Sachverhalt), gekürzt; plus der
Negativfall: ein Text, in dem „Sachverhalt" nur im Satz steht und die
strikte Form später folgt — die strikte gewinnt.

**Messung.** Hildesheim 1.076 → **1.078** von 1.078 mit Text.

**Kosten.** Kein Modell. Zwei Stunden. Kann mit PR 37 in einem Zweig
gehen, wenn derselbe Mensch beides baut — es sind zwei Dialekte, aber eine
Sorte Fehler.

## PR 39 — Ein Fenster für die Auswertung, nicht nur für die Ernte

**Warum.** Regel 27. `since` in der Registry wirkt auf `fetch`; die
Auswertungsstufen laufen über alles, was da ist. Hannover: 24.654 gegen
9.277 Kandidaten, $75 gegen $35 — und ein Vergleich über ungleiche
Zeiträume.

**Was sich ändert.**

1. `council/cities/registry.py::BodySpec` bekommt `compare_since: str`
   (Vorgabe `"2023-01-01"`). Oldenburg behält sein volles Fenster — es ist
   die Bezugsstadt, gegen die `fit` vergleicht; die 2018er Oldenburger
   Beschlüsse sind der Grund, warum eine Idee „hat Oldenburg schon" bekommt.
   Hannover und Hildesheim (`since=2018`) bekommen `compare_since=2023`.
2. `pipeline.annotate`, `index_all`, `cluster_all` und `fit` wählen ihre
   Kandidaten über `papers.date >= compare_since` der jeweiligen Stadt.
   `store.py` bekommt dafür die Bedingung in genau den Abfragen, die heute
   `papers_unclassified`/`papers_unembedded` liefern — **als ganze statische
   Anweisungen**, `tests/test_sql_spalten.py` verlangt das.
3. `cities_backfill.py` zeigt das Fenster je Stadt in der Tabelle
   („Fenster ab") und nennt vor `annotate`/`fit` die Kandidatenzahl **und die
   geschätzten Kosten** aus §2.6 — das ist Regel 27 als Code, nicht als
   Prosa. Der Wächter vor `fit` (#1238) prüft zusätzlich, dass `index` und
   `cluster` für dieselbe Menge gelaufen sind.
4. Vorlagen **ohne Datum** fallen aus dem Fenster heraus und werden
   gezählt (nach PR 37 sind das in Wolfsburg unter 20, in Hannover 3).

**Test.** `tests/test_cities_pipeline.py`: eine Stadt mit zwei Vorlagen (2021,
2024) und `compare_since=2023` — `annotate` sieht eine; Oldenburg mit
demselben Datum sieht beide. Ein Wächter in `test_cities_guards.py` hält
fest, dass keine der vier Stufen ohne das Fenster wählt (Quelltext-Lesen,
wie `test_cities_extract_inline_dispatch.py`).

**Messung.** `cities_backfill.py` nennt für Hannover **9.277 Kandidaten**,
für Braunschweig unverändert 3.322 (dort war schon alles ab 2023).

**Kosten.** Kein Modell. Ein Tag.

## PR 40 — Der Bestandslauf Niedersachsen

**Warum.** Das ist der Schritt, der Hannover und Wolfsburg auf die Karte
bringt. Alles davor ist Vorbereitung.

**Was läuft, in dieser Reihenfolge und nie anders** (Falle aus Phase 4:
`fit` ohne Index war $15 für zwei tote Beleg-Arme):

```bash
python scripts/cities_backfill.py --run --body hannover --body wolfsburg --body hildesheim \
    --stage annotate            # classify + effort, ≈ $14 + $2 + $1
python scripts/cities_backfill.py --run --body hannover --body wolfsburg --body hildesheim \
    --stage index               # fastembed, lokal, Stunden
python scripts/cities_backfill.py --run --stage cluster        # über ALLE Städte — Cluster sind stadtübergreifend
python scripts/cities_backfill.py --run --body hannover --body wolfsburg --body hildesheim \
    --stage fit                 # ≈ $16 + $0,6 + $1,5
python scripts/cities_backfill.py --pruefen
```

`cluster` läuft absichtlich über alle: Ein Cluster „Verpackungssteuer" muss
Hannovers Antrag neben Braunschweigs finden. Danach `cluster_check` ($0,06
beim letzten Mal) und `stance` (hängt an `annotate` im Cron-Pfad, #1257).

**Zwischenprüfung, nicht Fortschrittsbalken** (Tims Regel vom 09.09.): nach
den ersten 200 `fit`-Urteilen die Verteilung (`fehlt`/`teilweise`/`hat`) und
die Beleg-Arme zählen — alle fünf müssen vorkommen. Bei Hannover ist eine
Sache neu: Die `search_terms` fragen „wie hieße das in Oldenburg?" — bei
einer Stadt mit demselben Landesrecht sollte die Umformulierung seltener
nötig sein; die Trefferquote des `fts`-Arms im Vergleich zu Braunschweig ist
die Zahl, die das zeigt.

**Danach:**

1. `--pruefen` ohne Befund; das Ergebnis-Vokabular je Stadt durchgehen
   (Hannover tauchte bisher in der Unbekannt-Liste nicht auf — nach 25.729
   Vorlagen erneut ansehen).
2. `python scripts/lokale_daten.py schieb --staedte --nach dev` (5,5 min beim
   letzten Mal; die Datenbank wächst um ≈ 60 %).
3. `active=True` für **Hannover und Wolfsburg** in `registry.py` — damit der
   Sonntags-Cron sie fortschreibt. **Vorher messen, was ein Wochenlauf
   kostet:** `check_cities.py` erntet im Fenster (`fenster` in Zeile 81);
   Hannover mit 28.381 Abrufen für die Vollernte braucht für eine Woche
   vermutlich wenige hundert — das ist eine Zahl aus einem Probelauf mit
   `--since <letzter Sonntag>`, nicht aus dem Bauch.
   **Hildesheim bleibt `active=False`**, bis die Vollernte durch ist.

**Test.** Keiner neu — die Wächter vor `fit` und der Plausibilitätsprüfung
tun ihre Arbeit. Der Lauf selbst ist die Messung.

**Messung.** Hannover ≥ 9.000 `fit`-Urteile (v3), Verteilung in der Nähe
der anderen Städte (73/12/15); Ideen-Liste zeigt Hannover unter mindestens
zehn Themenfeldern; „Anderswo beschlossen" auf einer Oldenburger
Beschluss-Seite nennt einen Hannoveraner Antrag.

**Kosten.** ≈ **$41** Modell, ≈ 4–5 Stunden Rechenzeit lokal, ein Tag
Aufmerksamkeit.

## PR 41 — Ein Wächter für die Ernte: langsam ist auch kaputt

**Warum.** Die Hildesheim-Ernte lief elf Stunden, und niemand — kein Log,
keine Kennzahl, kein Test — hat gemeldet, dass sie von 343 auf 8 Vorlagen je
Stunde gefallen war. Hätte der Server um 16:13 nicht selbst aufgegeben,
liefe sie noch. Der WAL-Fehler ist behoben; **die Blindheit nicht.**

**Was sich ändert.**

1. `council/cities/oparl.py::OParlClient` zählt je Lauf: Abrufe, Fehler,
   und ein gleitendes Fenster der Antwortzeiten (die letzten 50). Das ist
   billig — ein `deque`, kein Store-Zugriff.
2. `pipeline.fetch` fragt den Client alle N Abrufe (Vorgabe 200) und bricht
   ab, wenn **eine** von zwei Schranken reißt:
   - Median-Antwortzeit über 15 s (Hildesheim gesund: ~1 s; der Proxy gibt
     nach 30 s auf) — der Server stirbt, wir hören auf, ihn zu treten.
   - Kein einziger neuer Rohsatz in den letzten 30 Minuten — wir hängen.
   Der Abbruch ist eine **ordentliche Rückkehr** mit `zahlen["abgebrochen"]
   = <Grund>`, nicht eine Exception: Die Rohablage bleibt konsistent, der
   nächste Lauf setzt auf.
3. `cities_backfill.py` loggt **je Stunde** die Objekte je Art (die Tabelle
   aus §2.4 war Handarbeit; sie gehört ins Log) und die WAL-Größe der
   Rohdatei — ein zweiter, unabhängiger Kanarienvogel für Regel 25.
4. `scripts/check_cities.py` reicht `abgebrochen` in die `job_runs`-Kennzahlen
   und damit ins Admin-Panel; `kern/jobs.py` bleibt unverändert.
5. `council/cities/CLAUDE.md`: der Abschnitt „Wiederaufnahme einer
   abgebrochenen Ernte" (Anhang C, 6) — er stand bisher nirgends.

**Test.** `tests/test_cities_pipeline.py`: ein gefälschter Client, dessen
Antwortzeiten nach 200 Abrufen auf 20 s springen — `fetch` kehrt mit
`abgebrochen="langsam"` zurück und hat die 200 gespeichert. Ein zweiter
Fall: 200 Abrufe, alle liefern Bekanntes (`put_raw_object` → `False`) — kein
Abbruch, denn „nichts Neues" ist bei einer Wochen-Ernte normal; erst „nichts
Neues UND keine Antwort" ist der Hänger.

**Messung.** Gegen die Hildesheim-Rohablage nachgestellt (Antwortzeiten aus
den `fetched_at`-Abständen): Der Wächter hätte am 11.09. gegen **10:30**
abgebrochen, nicht um 16:13.

**Kosten.** Kein Modell. Ein Tag.

## PR 42 — `reason`: den Maßstab reparieren, dann das Modell messen

**Warum.** 6.033 Abschnitte in zwei niedersächsischen Städten, ein
Annotator, der in allen durchgesehenen Antworten sauber arbeitet (§2.5,
Kommentar in `annotators.py:547`), und ein Prüfstand, der an Zeichenketten
scheitert. Regel 22 verlangt den Prüfstand — nicht diesen.

**Was sich ändert.**

1. `eval/run_cities_reason.py`: `vote` wird als **Zahlentripel** verglichen
   (Ja/Nein/Enthaltung, mit Regex aus beiden Seiten gezogen), nicht als
   Text. Ein Abschnitt mit **zwei** Abstimmungen (Änderungsantrag, dann
   Hauptantrag) gilt als getroffen, wenn das Tripel der **letzten**
   vorkommt — das ist der Beschluss. `None` gegen einen Wert ist ein Fehler
   des Golden Sets, nicht des Modells, und wird als solcher gemeldet.
2. Den einen „erfundenen" Fall **ganz lesen** (Anhang C, 5) und das Label
   von Hand entscheiden. Am 10.09. war es der Prüfstand. Ist es diesmal das
   Modell, bleibt `reason` aus, und der Fall wird zur ersten Zeile im
   Prompt („Ohne Begründung im Text: `grounded=false`").
3. Den Fall „0 Ja, 42 Nein" gegen „41 Ja, 0 Nein" auf den **Schnitt** prüfen
   (`protocol_sections` für diesen Punkt): Steht im Abschnitt die Abstimmung
   des Nachbarpunkts, ist es ein Fehler aus PR 32, und dort gehört er hin.
4. Erst wenn alle drei Schranken halten (0 erfunden, ≥ 90 % `vote`, 0
   Namen): `active=True`, und der Bestandslauf über Wolfsburg und Hildesheim
   (`--stage annotate` nach PR 40 nimmt ihn mit, weil `check_cities.py:171`
   auf `get_annotator("reason").active` prüft).

**Test.** `tests/test_cities_reason_eval.py`: die Tripel-Erkennung an den
fünf Schreibweisen aus dem Lauf vom 12.09. („mit 6 Ja-, 34 Neinstimmen und 5
Enthaltungen", „6 Ja, 34 Nein, 5 Enthaltungen (Änderungsantrag); 7 Ja, 3
Nein", „Einstimmig angenommen" → kein Tripel, aber auch kein Fehler).

**Messung.** Der Prüfstand druckt vier Zahlen, alle drei Schranken grün.
Dann 6.033 Abschnitte × $0,48/1.000 ≈ **$3**, und auf der Karte einer
Wolfsburger Idee steht ein „Warum" mit Zitat.

**Kosten.** Prüfstand < $0,10 je Lauf, Bestandslauf ≈ $3. Ein bis zwei Tage,
davon ein halber für die Handdurchsicht.

## PR 43 — Die Karte sagt, woher sie es weiß

**Warum.** Nach dieser Phase stehen auf der Karte Städte mit **verschiedenen
Fenstern** (Oldenburg 2018, alle anderen 2023), eine Stadt **ohne
Niederschriften aus Prinzip** (Hannover), und Ideen mit und ohne „Warum".
Heute erklärt die Karte keins davon. Wer „Hannover — kein Warum" liest,
soll erfahren, dass es nicht am Modell liegt.

**Was sich ändert.**

1. `web/backend/app/routers/council.py` (`/cities/ideas`): je Idee die
   Felder `window_since` (aus `compare_since`) und `reason_available`
   (`bool`: Stadt hat Abschnitte **und** `reason` ist aktiv). Antwortform in
   `antworten.py`, Vertrag neu schneiden (`web/backend/CLAUDE.md`).
2. Web (`app/(app)/council/ideen`) und iOS: eine Zeile unter der Stadt —
   „Beschlüsse seit 2023 · Niederschriften: ja/nein/nicht öffentlich". Kein
   neues Bauteil, die Kartenanatomie bleibt (Designsprache). Keine dunkle
   Kachel im Hellen.
3. Der Block „Anderswo beschlossen" auf der Beschluss-Seite zeigt dieselbe
   Zeile.

**Test.** Vertragstest (`tests/test_api_vertrag.py` läuft ohnehin), ein
Frontend-Test auf die drei Zustände der Zeile, `ios_vertrag.py`.

**Bild vor dem Merge.** Screenshot per `SendUserFile`, Gegenlesen abwarten —
Tims Regel für jeden UI-PR.

**Kosten.** Kein Modell. Ein Tag, plus Gegenlesen.

## PR 44 — Tims hundert Urteile (kein Code)

**Warum.** `eval/cases_cities_list.json` hat 100 Fälle und null Urteile.
`eval/run_cities_list.py` rechnet P@20 — gegen nichts. Der Schalter
`ideen-anderswo` nennt als `fertig_wenn` genau diese Durchsicht. Und nach
PR 40 hat die Liste zum ersten Mal Hannoveraner Einträge — die 100 Fälle
sollten **nach** PR 40 neu gezogen werden (`eval/build_cities_list_cases.py`),
sonst bewertet Tim eine Liste ohne Niedersachsen.

**Was zu tun ist.** `on_list: true/false` je Fall, dazu bei `false` ein
Wort in `why`. Etwa zwei Stunden. Danach `python eval/run_cities_list.py`,
und die Zahl steht — sie ist der Maßstab für alles, was an der Liste noch
geändert wird.

## PR 45 — Langenhagen und Peine (optional, klein)

Beide sind ALLRIS 4 mit OParl, beide geerntet, beide **ohne Dateien** (je 4
von ~700/~285 geholt). `--run --body langenhagen --body peine --stage fetch`
holt ≈ 1.100 Dateien in ≈ 40 Minuten; danach `extract`, `--pruefen`, und
sie könnten mit in PR 40. 1.107 Vorlagen aus dem Umland Hannovers sind für
den Vergleich kein Gewicht, aber sie kosten fast nichts. Entscheidung: Tim.

## Anhang A — Reihenfolge, Aufwand, Kosten

| PR | Was | hängt an | Aufwand | Modell |
|---|---|---|---|---|
| 37 | Wolfsburg-Adapter + Fixture | — | ½ Tag | 0 |
| 38 | Hildesheim Sachverhalt-Rückfall | — | 2 h | 0 |
| 39 | Fenster für die Auswertung | — | 1 Tag | 0 |
| 40 | Bestandslauf Niedersachsen | 37, 39 | 1 Tag + 4–5 h Rechenzeit | **≈ $41** |
| 41 | Ernte-Wächter | — | 1 Tag | 0 |
| 42 | `reason`-Prüfstand + Lauf | — | 1–2 Tage | < $0,10 + ≈ $3 |
| 43 | Karte: Fenster und Warum-Verfügbarkeit | 39, (42) | 1 Tag + Gegenlesen | 0 |
| 44 | Tims Urteile | 40 | 2 h Tim | 0 |
| 45 | Langenhagen/Peine | — | ½ Tag + 40 min | ≈ $2 |

Parallelisierbar: 37+38 gegen 39 gegen 41 gegen 42. Der kritische Pfad ist
37 → 39 → 40 → 43.

## Anhang B — Was ausdrücklich NICHT in diesem Plan liegt

- **Hildesheim weiterernten, solange ALLRIS `502` liefert.** Einmal täglich
  ein einzelner Abruf mit `-m 90` (Anhang C, 6) ist in Ordnung; ein
  `--run` gegen einen toten Server ist Zeit für nichts und Last für die
  Stadt. Ist er zurück: Wiederaufnahme wie beschrieben, **nach** PR 41.
- **Die Kennung ändern, um irgendetwas zu umgehen.** Der User-Agent trägt
  absichtlich Kontaktdaten. Göttingen (Cloudflare), `ris.hannit.de`
  (ALTCHA) und Salzgitter (antwortet nicht) bleiben, was sie sind.
- **Hannovers TOPS-Seiten lesen.** Sie tragen den Vertraulichkeitshinweis;
  Tims Einwand („dann ist der Satz ein Fehler") ist notiert, die Regel
  bleibt, bis die Stadt es anders sagt.
- **Bonn und Darmstadt** (PR 35/36 aus Phase 5) — unverändert offen, aber
  nicht vor Niedersachsen.
- **Benachrichtigungen, Ratsmitglieder** (Regel 21).
- **Ein „Warum" ohne Text** (Regel 22) — für Hannover heißt das: nie.
- **Ein anderes Modell.** Gemessen 10.09. (v4.1-flash: 3× Kosten, +5 Punkte
  im Rauschen) und 11.09. (kostenlose OpenRouter-Modelle: keins hält die
  Drosselung, mehrere ohne JSON-Modus; Produktion bleibt bei
  Zero-Data-Retention — Tims Entscheidung).

## Anhang C — Messbefehle

Alle vom Repo-Root, mit `.venv/bin/python`. **Nie, während ein Lauf
schreibt** — `cities.sqlite` hat einen Schreiber.

1. **Stand je Stadt, auch inaktive** (die Tabelle in §2.1):
   ```python
   from council.cities.store import CitiesStore
   for r in CitiesStore("data/cities.sqlite").stats():
       print(r["id"], r["papers"], r["papers_with_text"], r["papers_with_outcome"],
             r["papers_unclassified"], r["papers_unembedded"], r["annotations"])
   ```
   `cities_backfill.py` ohne `--run` zeigt nur `active_bodies()`.
2. **Ergebnisquote je Art und Jahr** (§2.2) — das Ergebnis hängt am
   Tagesordnungspunkt, nicht an der Beratung:
   ```sql
   SELECT p.kind, COUNT(*),
     SUM(EXISTS(SELECT 1 FROM consultations c JOIN agenda_items a ON a.id=c.agenda_item_id
                WHERE c.paper_id=p.id AND a.outcome NOT IN ('', 'none')))
   FROM papers p WHERE p.body_id='hannover' GROUP BY 1;
   ```
3. **Wolfsburgs zwei Fehler** (§2.3):
   ```sql
   SELECT COUNT(*), SUM(date IS NULL), SUM(kind='other') FROM papers WHERE body_id='wolfsburg';
   SELECT substr(paper_type_raw,1,80), COUNT(*) FROM papers
     WHERE body_id='wolfsburg' AND kind='other' GROUP BY 1 ORDER BY 2 DESC LIMIT 5;
   ```
   Vorher 1570 / 1570 / 883. Fertig, wenn die zweite und dritte Zahl unter
   20 und 160 liegen.
4. **Kandidaten und Kosten je Stadt** (§2.6, vor jedem Bestandslauf):
   ```sql
   SELECT body_id, COUNT(*), SUM(date >= '2023-01-01'),
     SUM(kind IN ('motion','proposal','inquiry','amendment') AND date >= '2023-01-01')
   FROM papers GROUP BY 1;
   ```
   Kosten: `SELECT feature, model, COUNT(*), SUM(cost_usd) FROM llm_usage
   WHERE feature LIKE 'cities_%' GROUP BY 1,2` in `data/ratslotse.sqlite`.
5. **Der `reason`-Prüfstand** und der eine Fall:
   ```bash
   .venv/bin/python eval/run_cities_reason.py > /tmp/reason.txt 2>&1   # ≈ $0,01, 2–10 min
   sed -n '/ERFUNDEN/,/Abstimmungsergebnis daneben/p' /tmp/reason.txt
   ```
   Den Abschnitt dazu: `SELECT text FROM protocol_sections WHERE
   agenda_item_id=?` — **ganz lesen**, nicht die ersten Zeilen.
6. **Ist Hildesheim zurück, und die Wiederaufnahme:**
   ```bash
   curl -sS -m 90 -o /dev/null -w "%{http_code} %{time_total}s\n" \
     -A "Mozilla/5.0" "https://www.stadt-hildesheim.de/allris/si010_e.asp?YY=2026&MM=09"
   # 502 nach ~30 s = noch tot. 200 in < 2 s = zurück. NIE mit -m 12 messen (Regel 26).
   CITIES_RATE_SECONDS=0.3 .venv/bin/python scripts/cities_backfill.py --run --body hildesheim \
     --stage fetch --stage normalize --stage extract      # setzt auf 5.369 Rohobjekten auf
   .venv/bin/python scripts/cities_backfill.py --pruefen
   ```
   Während des Laufs die Stundentabelle aus §2.4 (bis PR 41 sie loggt):
   `SELECT substr(fetched_at,1,13), kind, COUNT(*) FROM raw_objects GROUP BY 1,2`
   gegen `data/cities-raw/hildesheim.sqlite` — und die WAL-Größe daneben.
7. **Was der Wochen-Cron für Hannover kostet** (vor `active=True` in PR 40):
   `--run --body hannover --stage fetch --since <letzter Sonntag>` mit
   Stoppuhr; `zahlen["requests"]` ist die Zahl.
