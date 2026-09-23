# Umsetzungsplan: Ideen als Bewegungen — die Oberfläche des Städtevergleichs

Stand: 22.09.2026, abends. Dieser Plan folgt auf
[`plan-cities-phase6.md`](plan-cities-phase6.md) und ist wie seine Vorgänger
geschrieben: **ohne das Gespräch dahinter ausführbar**. Jeder Abschnitt ist
ein Pull Request, nennt Dateien, Signaturen, Tests, Kosten und woran man
erkennt, dass er fertig ist. Wo etwas gemessen ist, steht die Zahl und in
Anhang C der Befehl, der sie liefert.

Wer das umsetzt, liest **vorher** vollständig: die Wurzel-`CLAUDE.md`,
`council/CLAUDE.md`, `council/cities/CLAUDE.md`, `web/backend/CLAUDE.md`,
**`web/frontend/CLAUDE.md` und `web/frontend/DESIGNSPRACHE.md`** (Pflicht vor
jeder UI-Arbeit), `ios/CLAUDE.md`, `tests/CLAUDE.md`, §0 der sechs
Vorgängerpläne (Regeln 1–27 gelten unverändert) und die Docstrings von
`council/cities/clusters.py::build_clusters`, `::check_clusters`,
`council/cities/store.py::rebuild_group_status`, `::ideas`,
`council/cities/fit.py::source_hash`, `::stichprobe` und
`scripts/cities_fit_fassung5.py`.

**Der Entwurf, auf den dieser Plan baut**, liegt als klickbare Seite mit
echten Daten vom 22.09.2026 vor:
<https://claude.ai/artifact/EhsWmWqqAvVSpXUBMeKPwj> (privat, Tims Konto).
Er ist ein Bild, kein Code — keine Zeile davon wird übernommen. Die
Designentscheidungen darin gelten erst, wenn Tim sie bestätigt hat (§7).


## 0. Die Richtung, die Tim vorgegeben hat

Am 14.09.2026, nach dem ersten Blick auf die Ideen-Seite:

> Gerade fehlt mir irgendwie eine gute Benutzbarkeit des neuen Features,
> bisher sind es nur lange Listen mit Ideen, die aber schlecht ausgeführt
> sind, also ich sehe nicht genau, was die Idee ist, warum sie vielleicht für
> Oldenburg interessant sein kann, UI ist auch nicht schön.

Am 22.09.2026:

> Ich würde gerne bald ein cooles UI/UX haben, um mit den Daten arbeiten zu
> können. — Schreib einen ausführlichen Plan mit den ganzen Schritten.

Und am 20.09.2026, zum Geld:

> Ich möchte monatlich nicht so viel Geld für Ratslotse ausgeben.

Dazu sechs Regeln, die seit Phase 6 gemessen wurden und ab jetzt gelten:

28. **Eine Stichprobe greift über die ganze Liste, nie in ihren Anfang.** Der
    `fit`-Bestandslauf ist dreimal abgebrochen, weil sein Wächter
    `offen[:30]` nahm — einen Block aus einem Gremium, in dem alle Beleg-Arme
    zufällig leer liefen (#1389). Gestreut und deterministisch, damit ein
    Befund nachstellbar bleibt.
29. **Die Fassung steckt im Quell-Hash.** `fit.source_hash` nimmt
    `ann.version` und die ersten 200 Zeichen des Prompts mit hinein. Wer
    Urteile in eine neue Fassung übernimmt, muss den Hash nachziehen — sonst
    beurteilt der nächste Lauf alles neu (#1414, gemessen: 1.766 Urteile für
    1,21 $, bevor es auffiel).
30. **Nach jeder neuen `fit`-Fassung wird `idea_group_status` neu
    gerechnet**, sonst findet die Ideen-Liste keine Gruppen-Zeile mehr:
    `peers` fällt überall auf 0, „auch in N Städten" verschwindet, und die
    Sortierung nach Städten ist ausgehebelt — ohne Fehler (§2.7).
31. **Laufkosten werden gemessen, nicht geschätzt** — Probe mit `limit=20`,
    daraus Kosten UND Dauer. Die Spalte `annotations.cost_usd` ist für Zeilen
    vor #1320 um rund Faktor 44 zu hoch und taugt für keine Hochrechnung.
32. **Daten liegen nie nur in einem Arbeitsbaum.** Die lokale
    `cities.sqlite` (2,4 GB) ging mit einem recycelten Worktree verloren,
    samt der Rohablage dreier Städte (§2.9).
33. **Ein Wächter aus einem Textmuster wird vor dem Bauen an einer
    Stichprobe geprüft.** Der naheliegende Filter „Status fehlt, Begründung
    sagt ‚Oldenburg hat kein …' — ausblenden" hätte **640** Urteile
    versteckt, fast alle echte Lücken (§2.6).


## 1. Zielbild

**Die Einheit der Oberfläche ist die IDEE, nicht die Vorlage.** Heute zeigt
die Seite je Karte eine fremde Vorlage, mit ihrem Aktennamen, und wer die
Idee sucht, muss sie sich aus Titel, Zusammenfassung und Urteil
zusammensetzen. Danach sieht man zuerst, **was sich durch mehrere Räte
bewegt**: eine Karte je Idee, mit den Städten, einer Zeitleiste der
Entscheidungen und **einem** Urteil darüber, wie weit Oldenburg ist.

Drei Flächen, auf Web und iOS gleich:

1. **Übersicht.** Oben eine Anzeigetafel „Gerade in Bewegung" mit den
   stärksten Ideen, die Oldenburg noch nicht vollständig hat. Darunter die
   Themenfelder als Umschalter, ein Filter nach dem Stand in Oldenburg, eine
   Suche und zwei Sortierungen. Dann die Bewegungen als Karten (Idee, Städte,
   Zeitleiste, Ergebnisse, Stand in Oldenburg). Darunter, klar abgesetzt,
   **„Einzelne Ideen"** — die Vorlagen, die bisher nur eine Stadt hatte.
2. **Ideen-Seite.** Je Stadt eine Zeile auf gemeinsamer Zeitachse, darunter
   alle Vorlagen der Reihe nach (Datum, Art, Fraktion, Ergebnis, Link ins
   Original). Daneben „Und in Oldenburg?" mit Belegen oder, wenn es fehlt,
   „Verwandtes aus Oldenburg"; „So haben die Räte entschieden"; wo vorhanden
   das Warum aus der Niederschrift; ähnliche Ideen.
3. **Einzelne Idee** (eine Stadt): bleibt die heutige Karte, bekommt aber die
   Überschrift aus `instrument` (seit #1355) und denselben Oldenburg-Block.

**Was sich NICHT ändert:** Der Schalter `ideen-anderswo` bleibt auf Prod aus,
bis Tim zwei Themenfelder durchgesehen hat (`fertig_wenn` in
`kern/features.py`). Die Urteile je Vorlage (`fit`) bleiben, wie sie sind;
das Urteil je Idee kommt **daneben**.


## 2. Was gemessen ist und den Plan trägt

Alle Zahlen aus einer vollständigen, geprüften Kopie des dev-Bestands vom
22.09.2026, 22:48 (`~/.cache/ratslotse/cities/cities-2026-09-22.sqlite`,
`PRAGMA quick_check` = ok). Befehle in Anhang C.

### 2.1 Der Bestand

| | |
|---|---:|
| Vorlagen im Städte-Speicher | 60.253 |
| `fit`-Urteile, Fassung 5 | 12.079 (von 12.307 Kandidaten; 228 laufen am 22.09. nach) |
| davon Ideen-Arten (Antrag, Beschlussvorlage, Anfrage, Änderungsantrag) | 8.321 |
| Verteilung Fassung 5 | fehlt 9.376 · vorhanden 1.483 · teilweise 1.198 · nicht anwendbar 22 |
| Kosten `fit`, gemessen | **$0,00112 je Urteil** (3 Stimmen), 11 Urteile je Minute lokal, 10 auf dev |

### 2.2 Wie viele Ideen sind Bewegungen?

Gruppen nach Zahl der Städte — nur belegte Gruppen (#1355), ohne die von
`cluster_check` ausgeschlossenen Mitglieder:

| Städte | Gruppen |
|---:|---:|
| 1 | 993 |
| 2 | 211 |
| 3 | 42 |
| 4 | 14 |
| 5 | 9 |
| 6 | 12 |
| 7 | 3 |
| 8 | 1 |

**Nur 924 der 8.321 Ideen-Vorlagen (11,1 %) liegen in einer Gruppe mit
mindestens zwei Städten.** Bewegungen ab drei Städten gibt es 81. Das ist der
wichtigste Befund für die Gestaltung: Die Bewegungen sind die Schlagzeile,
aber **neun von zehn Vorlagen sind Einzelideen**. Die Oberfläche braucht für
beide einen Ort — und für die Einzelideen einen, der nicht wie ein
Restposten aussieht.

### 2.3 Das Urteil über Oldenburg gibt es nur je Vorlage — und es widerspricht sich

`fit` urteilt je fremder Vorlage: „Hat Oldenburg DIESES Instrument?". Eine
Idee in sechs Städten hat damit sechs bis elf Urteile über dieselbe
Oldenburger Wirklichkeit. Gemessen an den 81 Bewegungen ab drei Städten:

| | Gruppen |
|---|---:|
| alle Urteile einig | 20 |
| **uneinig** | **61** |
| — davon alle drei Stufen gemischt | 34 |
| — fehlt + vorhanden | 14 |
| — fehlt + teilweise | 9 |
| — teilweise + vorhanden | 4 |

Beispiel *Hitzeaktionsplan aufstellen* (6 Städte, 11 Vorlagen): fünfmal
„fehlt", fünfmal „teilweise" (Oldenburgs „Hitze-Informationen" von 2023 und
der Zwischenstand zum Klimaanpassungskonzept), einmal „vorhanden" — und das
beruft sich auf die **Wärmeplanung**, die mit Hitze nichts zu tun hat. Die
richtige Antwort ist offensichtlich „teilweise"; keine Mehrheitsregel findet
sie zuverlässig (fünf gegen fünf).

`idea_group_status` hilft hier nicht: Er fasst die Urteile **einer Stadt je
Gruppe** zusammen, nicht die Gruppe als Ganzes. **Ein Urteil je Idee fehlt,
und es ist Voraussetzung für die ganze Oberfläche** (PR 48).

### 2.4 Beschriftung

| | Gruppen | mit Prüf-Label aus `cluster_check` |
|---|---:|---:|
| ab 2 Städten | 292 | 198 |
| ab 3 Mitgliedern | 372 | 365 |

`cluster_check` prüft erst ab drei Mitgliedern (`CHECK_AB_MITGLIEDERN`); eine
Zwei-Städte-Idee mit je einer Vorlage hat deshalb kein Label. Im Entwurf
stand für eine solche Gruppe ein leerer Titel. Das Label ist zudem ein
Kontrollwort („Parkgebühren anpassen"), keine Überschrift — es ist meist
brauchbar, aber nicht immer (§2.10).

### 2.5 Das Warum fehlt vollständig

| | |
|---|---:|
| `reason`-Annotationen im Bestand | **0** |
| Abschnitte aus Niederschriften (`protocol_sections`) | 6.962 |
| — Wolfsburg · Hildesheim · Münster · Magdeburg · Osnabrück · Braunschweig · Potsdam | 3.228 · 2.805 · 291 · 277 · 159 · 121 · 81 |
| Vorlagen mit einem solchen Abschnitt | 1.847 |
| — davon in einer Gruppe ab 2 Städten | **108** |

Probe mit `reasons.run(limit=20)` auf einer Wegwerf-Kopie: **20 Abschnitte,
4 mit Begründung, $0,0063, 145 s.** Hochgerechnet auf alle 6.962: rund
**$2,20** und — mit den sechs Arbeitern von `REASON_WORKERS` — rund
**14 Stunden**. Nur jeder fünfte Abschnitt trägt überhaupt ein Warum; für
Bewegungen blieben damit rund 20 Vorlagen mit einem Satz.

Die Ideen-Seite wird deshalb so gebaut, dass **das Warum die Ausnahme ist**:
ein Zitat, wo es eines gibt, sonst ein Hinweis mit festem Ort — kein leeres
Feld, das auf etwas wartet. Der Lauf selbst ist PR 51 und nachrangig.

### 2.6 Der Wächter, der nicht gebaut wird

Am 20.09.2026 lagen vier Urteile vor, die sich selbst widersprachen: Status
„fehlt", Begründung „Oldenburg hat keine Straßenbahn". Der naheliegende
Wächter — „Status fehlt UND die Begründung sagt ‚Oldenburg hat kein …': nicht
zeigen" — trifft **640** der 6.473 „fehlt"-Urteile. Zwölf zufällige davon:

> kein Konzept für einen Leistungssport-Campus · kein kostenfreies
> Schülerticket für alle Schüler · kein regelmäßiges Leerstandsmonitoring ·
> keinen Masterplan 100 % Klimaschutz · kein integriertes Flächenkonzept · …

Das sind genau die Lücken, die die Seite zeigen soll. **Der Wächter wird
nicht gebaut.** Die vier Straßenbahn-Fälle löst das Urteil je Idee (PR 48),
das alle Mitglieder zugleich sieht und die Voraussetzungsfrage einmal stellt.

### 2.7 Eine laufende Regression auf dev

`idea_group_status` enthält nur Zeilen für `fit_version = '3'` (1.499). Die
Ideen-Liste liest seit #1404 Fassung 5 und verbindet über
`g.fit_version = f.version` — findet also **keine** Gruppen-Zeile. Folgen,
alle stumm:

- `peers` ist überall 0, „auch in N anderen Städten" steht auf keiner Karte;
- die Sortierung `ORDER BY peers DESC` greift nicht mehr;
- der Gruppen-Status fällt auf das Einzelurteil zurück.

Behoben wird es im Betrieb, sobald der `fit`-Nachlauf fertig ist
(`rebuild_group_status(..., "5")`); gegen die Wiederholung steht PR 46.

### 2.8 Die Oberfläche heute

| | |
|---|---|
| Web | `web/frontend/app/(app)/council/ideen/view.tsx` — 631 Zeilen, Karte je Vorlage (`IdeenKarte`), Übersicht als Feld-Kacheln, Suche |
| iOS | `ios/Packages/RatslotseFeatures/Sources/RatslotseFeatures/IdeasView.swift` — 671 Zeilen, dieselbe Karte nachgebaut (`IdeaCard`) |
| Modelle iOS | `ios/Packages/RatslotseAPI/Sources/RatslotseAPI/Models.swift`: `Idea`, `IdeaEvidence`, `IdeaProtocol`, `IdeaSibling`, `IdeasResponse`, `IdeaFieldSummary`, `IdeaFields`, `IdeaSearchResponse` |
| Endpunkte | `GET /cities/ideas/fields`, `GET /cities/ideas?field=…`, `GET /cities/search`, `POST /cities/ideas/{paper_id}/feedback` |
| Schalter | `ideen-anderswo` (Seite, Navigation), `andere-staedte` (Block auf Beschluss-Seiten) |

Beide Clients bauen dieselbe Karte je Vorlage zweimal nach. Genau hier gehört
die Gruppierung in den Server (Tims Regel „Logik ins Backend", 30.08.2026):
Web und App bekommen die Idee fertig geliefert und stellen sie nur dar.

### 2.9 Wo die Daten liegen

- **dev** (`tk-dev:~/app/data/cities.sqlite`): der vollständige Bestand mit
  Fassung 5. Auf dev laufen keine Crons und kein Backup.
- **lokal** (`~/.cache/ratslotse/cities/cities-2026-09-22.sqlite[.gz]`): die
  geprüfte Kopie vom 22.09., außerhalb jedes Arbeitsbaums.
- **Prod**: eigener Bestand; der Städte-Cron ist seit 20.09. **pausiert**,
  nachdem der Sprung auf Fassung 4 einen Lauf von vierzehn Stunden auslöste
  und sechs Deploys blockierte (#1418). Fassung 5 und der Hash-Nachzug liegen
  bisher nur auf `dev`. **Liefe der Cron auf Prod mit Fassung 5 wieder an,
  beurteilte er alles neu** — rund $14 und über einen Tag Laufzeit.
- **Die Rohablage** (`cities-raw/<stadt>.sqlite`) von Hannover, Wolfsburg und
  Hildesheim lag nur im verlorenen Arbeitsbaum. Hannover und Wolfsburg lassen
  sich neu ernten; **Hildesheim nicht** (ALTCHA-Sperre seit ~13.09.). Die
  ausgewerteten Daten aller drei Städte sind vollständig.

### 2.10 Was der Entwurf gezeigt hat

Der Entwurf (Link oben) gruppiert die 7.556 Karten der dev-API nach Cluster
und zeigt die 40 stärksten Bewegungen. Drei Dinge fielen erst beim Bauen auf:

1. **„Nicht gefunden" über Oldenburger Belegen liest sich wie ein
   Widerspruch.** Bei *Kulturförderrichtlinie* standen zwei Oldenburger
   Förderbeschlüsse (2019, 2023) unter „In Oldenburg nicht gefunden". Sie sind
   verwandt, aber nicht dasselbe Instrument. Der Entwurf nennt sie
   „Verwandtes aus Oldenburg"; das Urteil je Idee (PR 48) trennt `evidence`
   (belegt den Stand) und `related` (verwandt, belegt nichts) ausdrücklich.
2. **Ohne gemeinsame Zeitachse ist eine Bewegung nicht lesbar.** Erst wenn
   alle Karten dieselbe Achse (2023–2026) haben, sieht man, dass *§ 5
   AsylbLG* eine Welle innerhalb von zwanzig Monaten war und
   *Kulturförderrichtlinie* ein langsamer Strom über drei Jahre.
3. **Die Ergebnis-Vokabeln sind überschaubar:** `accepted`, `amended`,
   `rejected`, `withdrawn`, `postponed`, `referred`, `noted`, `none`. Fünf
   Farbstufen genügen (beschlossen, abgelehnt, vertagt/überwiesen, zur
   Kenntnis, ohne Ergebnis — letzteres meist Anfragen, als hohler Punkt).


## 3. Die Reihenfolge, und warum

```
PR 46  Wächter: Gruppen-Status je fit-Fassung          (klein, sofort)
PR 47  Tabelle idea_groups — die Idee als Ganzes       (Daten)
PR 48  Das Urteil je Idee über Oldenburg               (Modell, ~$0,60)
PR 49  Überschriften für jede Idee                     (Daten, kein Modell)
PR 50  Endpunkte für Bewegungen                        (Backend, Vertrag)
PR 51  Das Warum aus den Niederschriften               (Modell, ~$2,20, nachrangig)
PR 52  Web: Übersicht                                  (UI, Bild vor Merge)
PR 53  Web: Ideen-Seite                                (UI, Bild vor Merge)
PR 54  iOS: beide Flächen                              (UI, Bild, TestFlight)
PR 55  Daten auf Prod und Freigabe                     (Betrieb, Tims Entscheidung)
```

Die Daten kommen vor der Oberfläche, weil der Entwurf gezeigt hat, dass die
Oberfläche an den Daten scheitert (§2.3, §2.4, §2.10) — nicht an der
Gestaltung. PR 51 ist unabhängig und darf jederzeit dazwischen laufen. PR 52
bis 54 dürfen erst beginnen, wenn Tim die offenen Fragen in §7 beantwortet
hat.


## PR 46 — Der Gruppen-Status gehört zur `fit`-Fassung

**Warum.** §2.7: Nach dem Sprung auf Fassung 5 findet die Ideen-Liste keine
Gruppen-Zeile mehr, und niemand merkt es. Dieselbe Falle öffnet sich bei jeder
künftigen Fassung.

**Was sich ändert.**

1. `council/cities/pruefung.py` bekommt einen Befund
   `gruppenstatus_fehlt`: Gibt es `fit`-Urteile der aktuellen Fassung
   (`get_annotator("fit").version`), aber keine einzige Zeile in
   `idea_group_status` mit dieser `fit_version`, ist das ein Befund — mit dem
   Befehl, der ihn behebt, in der Meldung.
2. `scripts/cities_backfill.py`: Die Stufe `fit` ruft am Ende
   `rebuild_group_status(EMBED_MODEL, CLUSTER_VERSION, ann.version)` —
   heute tut das nur der Cluster-Schritt und `check_cities.py`, ein Handlauf
   mit `--stage fit` lässt die Tabelle zurück.
3. Im Docstring von `rebuild_group_status` die Regel 30 mit den Zahlen aus
   §2.7.

**Test.** `tests/test_cities_gruppenstatus_fassung.py`: Urteile in Fassung
„9", Gruppen-Status nur für „8" → `pruefung` meldet den Befund; nach
`rebuild_group_status(…, "9")` nicht mehr. Und ein Quelltext-Wächter, dass
die `fit`-Stufe im Backfill `rebuild_group_status` aufruft.

**Betrieb (gehört dazu, kein Code).** Nach dem `fit`-Nachlauf auf dev einmal
`rebuild_group_status(EMBED_MODEL, "1", "5")`; danach zeigt die Liste wieder
„auch in N Städten".

**Messung.** `select fit_version, count(*) from idea_group_status` zeigt eine
Zeile für `'5'` (erwartet rund 1.500). `--pruefen` ohne Befund.

**Kosten.** Kein Modell. Zwei Stunden.


## PR 47 — `idea_groups`: die Idee als Ganzes

**Warum.** Die Oberfläche braucht je Idee: Städte, Mitglieder je Stadt,
Zeitraum, Ergebnisse, Themenfeld. Heute entsteht das nur in den Clients
(Entwurf: in JavaScript aus 7.556 Karten) — und in zwei Clients wäre es
zweimal falsch. Als lebende Abfrage wäre es zu teuer: Schon der Gruppen-Status
kostete so 0,65 s je Aufruf (Kommentar an `idea_group_status`).

**Was sich ändert.**

1. **Schema UND Migration** (`council/cities/schema.py`, Migration 9 —
   `council/CLAUDE.md`: zwei Stellen, sonst entsteht die Tabelle auf dev und
   Prod nie). Achtung, `cities.sqlite` migriert **beim ersten Öffnen**, nicht
   im Deploy (#1418); die Messung danach also erst nach einem Aufruf von
   `/api/council/cities/ideas/fields`.

   ```sql
   CREATE TABLE IF NOT EXISTS idea_groups (
       model        TEXT NOT NULL,
       version      TEXT NOT NULL,
       cluster_id   INTEGER NOT NULL,
       field        TEXT,              -- häufigstes Themenfeld der Mitglieder
       cities       INTEGER NOT NULL,  -- verschiedene Städte, Oldenburg ausgenommen
       members      INTEGER NOT NULL,  -- Ideen-Vorlagen nach Ausschluss
       first_date   TEXT,
       last_date    TEXT,
       outcomes     TEXT NOT NULL,     -- JSON {"accepted": 3, "rejected": 2, …}
       stable       INTEGER NOT NULL,  -- 0, wenn cluster_check uneins war (#1355)
       label        TEXT,              -- PR 49
       PRIMARY KEY (model, version, cluster_id)
   );
   CREATE INDEX IF NOT EXISTS idx_idea_groups_field ON idea_groups(field, cities);
   ```

   Mitglieder stehen NICHT darin — die liefert `idea_clusters` samt
   Ausschlussliste, wie heute.
2. `council/cities/store.py`:
   - `rebuild_idea_groups(model: str, version: str) -> int` — eine
     Anweisung, im Stil von `rebuild_group_status` (ganze statische SQL,
     `tests/test_sql_spalten.py`). Mitglieder nur Ideen-Arten
     (`motion`, `proposal`, `inquiry`, `amendment`), ohne
     `cluster_check`-Ausschlüsse. Das Ergebnis je Vorlage kommt aus
     derselben Quelle wie `outcome_for_paper` — nicht ein zweites Mal
     hergeleitet.
   - `idea_groups(field: str | None, min_cities: int, oldenburg: Sequence[str],
     q: str, sort: str, limit: int, offset: int) -> tuple[list[dict], int]` —
     filtert, sortiert, blättert, zählt **in SQL** (Tims Regel). `sort` ist
     `"staedte"` (cities DESC, members DESC) oder `"zuletzt"` (last_date DESC).
     `q` sucht in Label und Instrumenten der Mitglieder (über `papers_fts`,
     nicht `LIKE`).
   - `idea_group(cluster_id: int) -> dict | None` und
     `idea_group_members(cluster_id: int) -> list[dict]` (je Vorlage: Stadt,
     Datum, Art, Ergebnis, Einreicher, Titel, Link, Instrument,
     Zusammenfassung — sortiert nach Datum).
3. `council/cities/clusters.py::run`: sechster Schritt nach
   `rebuild_group_status` — `rebuild_idea_groups`. `check_cities.py` ruft ihn
   dort mit, wo es heute `rebuild_group_status` ruft.
4. `council/CLAUDE.md`-Register: nichts; `council/cities/CLAUDE.md` bekommt
   in „Die fünf Schichten" einen Satz, dass `idea_groups` abgeleitet ist wie
   `idea_group_status` und keine Meinung trägt.

**Test.** `tests/test_cities_idea_groups.py`:
- Drei Städte, fünf Vorlagen, eine davon ausgeschlossen → `cities=3`,
  `members=4`, Ausgeschlossene zählt nicht.
- Eine Antwort (`answer`) im Cluster zählt nicht mit.
- Eine unbelegte Gruppe (`stable=0`) steht mit `stable=0` da und fällt aus
  `idea_groups(min_cities=2)` heraus.
- Filter und Sortierung: zwei Themenfelder, zwei Zeiträume.
- Migrationsprobe gegen einen gewachsenen Stand
  (`tests/test_migration_bestand.py` deckt `cities.sqlite` ab — prüfen, sonst
  ergänzen).

**Messung.** Auf dem dev-Bestand: 292 Gruppen mit `cities >= 2`, 81 mit
`cities >= 3` (±2, §2.2). `idea_groups(None, 2, …, limit=30)` unter 50 ms.

**Kosten.** Kein Modell. Ein Tag.


## PR 48 — Das Urteil je Idee über Oldenburg

**Warum.** §2.3: 61 von 81 Bewegungen tragen widersprüchliche Urteile je
Vorlage, und keine Mehrheitsregel trifft den richtigen Stand. §2.6: Die
Voraussetzungsfrage („Könnte der Rat das beschließen?", #1404) muss einmal je
Idee gestellt werden, mit allen Mitgliedern im Blick — nicht elfmal einzeln.
§2.10: Beleg und Verwandtes müssen getrennt sein.

**Was sich ändert.**

1. **Neuer Annotator `idea_fit`** (`council/cities/annotators.py`),
   `applies_to=("cluster",)`, Kennung `<version>:<cluster_id>` wie
   `cluster_check`. Nutzlast:

   ```python
   class IdeaVerdict(BaseModel):
       status: Literal[FIT_STATUS]          # dieselben vier Stufen wie fit
       situation: str = Field(max_length=300)
       #   EIN Satz über die Lage in Oldenburg, neutral formuliert:
       #   „Oldenburg hat 2023 Hitze-Informationen veröffentlicht; ein
       #   Hitzeaktionsplan mit Maßnahmen liegt nicht vor." — NICHT
       #   „Kein Beleg zeigt …" (Prüfvermerk statt Auskunft).
       evidence: list[str] = Field(max_length=3)   # belegen den Status
       related: list[str] = Field(max_length=3)    # verwandt, belegen nichts
       confidence: Literal[CONFIDENCE_VALUES]
   ```

   Die Kennungen in `evidence` und `related` müssen aus der vorgelegten
   Beleg-Liste stammen (dieselbe Regel wie `fit`: Erfundenes fliegt raus,
   `hallucinated_evidence` bleibt bei null).
2. **Prompt** `cities_idea_fit_system` in `kern/prompts.py`. Vorgelegt
   werden: das Label, alle Mitglieder (Stadt, Datum, Art, Instrument,
   Zusammenfassung), die **Vereinigung** der Oldenburger Belege aller
   Mitglieder (dedupliziert, höchstens 12) und die Einzelurteile als
   Hinweis. Die Abgrenzung von `not_applicable` wird wörtlich aus dem
   `fit`-Prompt übernommen (#1404: „Könnte der Rat diese Voraussetzung
   beschließen?", mit Beispielen für beide Seiten). Zusätzlich: „Nennst du
   einen Beleg unter `evidence`, muss er den Status stützen. Was nur dasselbe
   Themenfeld berührt, gehört unter `related`."
3. **Drei Stimmen**, Mehrheit wie `fit.majority` — bei Gleichstand die
   schwächere Behauptung (`fit.STATUS_ORDNUNG`).
4. `council/cities/clusters.py::idea_fit_all(main, rats, model, limit)`:
   läuft über alle Gruppen mit `cities >= 2` aus `idea_groups`. Quell-Hash aus
   Mitgliedern, Beleg-Kennungen, `ann.version` und Prompt-Anfang — Regel 29.
   Wird als siebter Schritt in `clusters.run` eingehängt.
5. `idea_groups` bekommt **keine** Spalte für das Urteil (Schicht 1 trägt
   keine Meinung, `tests/test_cities_guards.py`); die Endpunkte lesen es aus
   `annotations`.

**Prüfstand.** `eval/cases_cities_idea_fit.json` mit 20 Gruppen, die **Tim**
beurteilt (§7, Frage 5) — darunter *Hitzeaktionsplan* (erwartet: teilweise),
*§ 5 AsylbLG* (fehlt), *Kommunale Wärmeplanung* (vorhanden),
*Verpackungssteuer* (fehlt), *Kulturförderrichtlinie* (fehlt, mit zwei
Einträgen unter `related`), eine Straßenbahn-Gruppe (nicht anwendbar).
`eval/run_cities_idea_fit.py` im Stil von `run_cities_reason.py`: Trefferquote
Status, `hallucinated_evidence == 0` als harte Schranke, `evidence`-Einträge,
die der Mensch als „nur verwandt" markiert, als eigene Fehlerklasse.

**Test.** `tests/test_cities_idea_fit.py`: Nutzlast lehnt fremde Kennungen ab;
Mehrheit bei Gleichstand; der Prompt enthält die Voraussetzungsfrage
(Wächter wie in `test_cities_fit_fassung5.py`); Quell-Hash hängt an der
Fassung.

**Messung vor dem Lauf (Regel 31).** `idea_fit_all(limit=20)` auf einer
Wegwerf-Kopie; daraus Kosten und Dauer für alle 292. Erwartung aus dem
`fit`-Takt (drei Stimmen, größere Vorlage): rund $0,002 je Gruppe, also
**etwa $0,60** — die Probe entscheidet, nicht diese Zeile.

**Messung nach dem Lauf.** Für *Hitzeaktionsplan* steht „teilweise", für die
vier Straßenbahn-Fälle aus §2.6 „nicht anwendbar" (oder die Gruppe enthält
sie nicht mehr). Stichprobe von 20 Urteilen gelesen (Regel „Lange Läufe:
ERGEBNISSE stichproben").

**Kosten.** Rund $0,60 Lauf, $0,05 Probe, zwei Tage Arbeit plus Tims
Prüfstand.


## PR 49 — Eine Überschrift für jede Idee

**Warum.** §2.4: 94 der 292 Bewegungen haben kein Label; das Label ist ein
Kontrollwort, keine Überschrift.

**Was sich ändert.** `rebuild_idea_groups` setzt `label` in dieser
Reihenfolge:

1. das Label aus `cluster_check`, wenn die Gruppe **stabil** ist und das Label
   in mindestens zwei Mitglieder-Instrumenten wortweise vorkommt (sonst ist es
   ein Oberbegriff, den keine Stadt so beschlossen hat);
2. sonst das `instrument` des **typischsten** Mitglieds — das mit dem höchsten
   `score` in `idea_clusters` (Nähe zum Gruppenmittel, genau dafür steht er
   da, s. `build_clusters`).

Kein Modellaufruf. Die Regel steht in einer Funktion
`idea_label(members, check_label) -> str` in `council/cities/clusters.py`,
damit sie testbar ist.

**Test.** Leeres Label → Instrument des typischsten; Label, das in keinem
Instrument vorkommt → Instrument; stabiles, belegtes Label → Label.

**Messung.** Jede Gruppe mit `cities >= 2` hat ein nicht-leeres `label`.
Zehn Labels gelesen und in den PR geschrieben.

**Kosten.** Kein Modell. Ein halber Tag.


## PR 50 — Endpunkte für Bewegungen

**Warum.** Web und iOS bekommen die Idee fertig geliefert (§2.8). Die
Einzelideen bleiben auf den heutigen Endpunkten.

**Was sich ändert.** `web/backend/app/routers/council.py`, Antwortformen in
`web/backend/app/antworten.py` (`web/backend/CLAUDE.md`), danach
`python scripts/openapi_schnitt.py` und `npm run api:typen`.

1. `GET /cities/movements` — Parameter `field`, `oldenburg`
   (`missing,partial,present,not_applicable`, Vorgabe `missing,partial`),
   `min_cities` (Vorgabe aus §7, Frage 1), `q`, `sort`, `page`, `per_page`
   (höchstens 50). Antwort `MovementsResponse`:

   ```python
   class MovementCity(TypedDict):
       city: str                 # Anzeigename
       first_date: str | None
       outcomes: dict[str, int]
   class Movement(TypedDict):
       cluster_id: int
       label: str
       field: str | None
       cities: list[MovementCity]   # je Stadt, nach erstem Datum
       members: int
       first_date: str | None
       last_date: str | None
       outcomes: dict[str, int]
       timeline: list[TimelinePoint]  # {city, date, outcome, kind} — die Punkte der Zeitleiste
       oldenburg: OldenburgVerdict | None  # aus idea_fit; None, solange nicht beurteilt
   class MovementsResponse(TypedDict):
       items: list[Movement]
       total: int
       axis: TimeAxis            # {"from": "2023-01-01", "to": "2027-01-01"} — EINE Achse für alle
   ```

   **Die Achse liefert der Server**, damit Web und App dieselbe zeichnen
   (§2.10, Punkt 2). Sie reicht vom Jahresanfang des frühesten bis zum
   Jahresende des spätesten Datums im ganzen Bestand, nicht nur der Seite —
   sonst springt sie beim Blättern.
2. `GET /cities/movements/detail?id=<cluster_id>` (Query-Parameter, nicht
   Pfadsegment — der statische Export braucht das, `web/frontend/CLAUDE.md`).
   Antwort `MovementDetail`: alles aus `Movement`, dazu `documents`
   (je Vorlage: Stadt, Datum, Art, Ergebnis, Einreicher, Titel, Link,
   Instrument, Zusammenfassung, `reason` aus PR 51 oder `None`), `evidence`
   und `related` aufgelöst wie heute `_belege_aufloesen` (mit
   `decision_id`, damit die Karte intern verlinkt), `similar` (drei Gruppen
   desselben Feldes, meiste Städte), `protocol_note` (warum kein Warum da ist:
   „nicht ausgewertet" / „Niederschriften nicht öffentlich" aus
   `protocols_public` / „keine Begründung im Abschnitt").
3. `GET /cities/ideas/fields` bekommt je Feld `movements` (Zahl der
   Bewegungen ab `min_cities`) — die Übersicht zählt damit, ohne zu laden.
4. Öffentlich wie die bestehenden Städte-Endpunkte (dieselben Ratsdokumente),
   hinter keinem Schalter — der Schalter sitzt an der Seite (§1).

**Test.** `tests/test_cities_router_movements.py` gegen einen kleinen
Bestand: Filter, Blättern, Achse unabhängig von der Seite, `oldenburg=None`
ohne Urteil, Detail mit aufgelösten Belegen, 404 für unbekannte Kennung.
`tests/test_api_vertrag.py` hält die neuen Formen. `scripts/rauchprobe.py`
ruft beide Endpunkte (öffentlich, ohne Modell) — Eintrag ergänzen.

**Messung.** `GET /cities/movements` auf dev unter 200 ms; `total` für
`min_cities=3` = 81 (±2).

**Kosten.** Kein Modell. Anderthalb Tage.


## PR 51 — Das Warum aus den Niederschriften (nachrangig)

**Warum.** §2.5. Es kostet wenig, bringt für Bewegungen aber nur rund zwanzig
Sätze. Es lohnt sich vor allem für die Einzelideen.

**Was sich ändert.** Kein Code, außer: `MovementDetail.documents[].reason`
füllt sich aus den `reason`-Annotationen (`grounded=true`), wie heute
`_protokoll` für die Einzelkarte.

**Betrieb.** Vor dem Lauf eine Kopie ziehen (Regel 32). Dann auf dev in
`tmux`: `reasons.run(main, limit=1000)` mit **frischem Prozess je Tranche**
(Lehre aus dem `fit`-Lauf). Die Schleife dafür gehört als
`scripts/cities_tranchen.sh` ins Repo — bisher liegt sie nur als
`~/app/fit4_schleife.sh` auf dev: je Durchgang ein neuer Python-Prozess,
Abbruch der Schleife bei einem Fehlercode statt blind weiterzuzahlen.
Vorher die Probe mit `limit=20` wiederholen.

**Messung.** Anteil `grounded` um 20 % (Probe: 4 von 20). Zehn Begründungen
gelesen — eine erfundene ist ein Abbruch (`council/cities/CLAUDE.md`: „Ein
Modell darf wiedergeben, was im Protokoll steht. Es darf nicht erschließen").

**Kosten.** Rund $2,20, rund 14 Stunden auf dev.


## PR 52 — Web: die Übersicht

**Voraussetzung:** PR 47–50 gemergt, §7 beantwortet.

**Was sich ändert.**

1. `web/frontend/components/ideen/zeitleiste.tsx` — die Zeitleiste als
   eigener Baustein: nimmt `axis` und `timeline`, zeichnet Punkte je Ergebnis
   (fünf Stufen, §2.10 Punkt 3), Jahreslinien gestrichelt, Beschriftung von
   Anfang und Ende. Farben aus den Semantik-Tints der Designsprache
   (§2 „Semantik"), nie Vollflächen. Punkte sind `title`-beschriftet
   (Stadt · Datum · Art · Ergebnis); die ganze Leiste hat ein `aria-label`,
   das die Folge in Worten nennt („6 Städte, 2023 bis 2026: zweimal
   beschlossen, dreimal abgelehnt").
2. `web/frontend/lib/zeitleiste.ts` — die reine Rechnung (Datum → Anteil
   auf der Achse, Jahresmarken, Ergebnis → Stufe) mit
   `lib/zeitleiste.test.ts` (vitest). Grenzfälle: ein einziges Datum,
   Datum auf der Jahresgrenze, `null`.
3. `web/frontend/components/ideen/bewegung-karte.tsx` — Karte je Idee:
   Kicker (Feld · Zeitraum), Titel in Bricolage, „N Städte: …", Zeitleiste,
   Zähler (Vorlagen, beschlossen, abgelehnt), Oldenburg-Pille mit
   Signal-Marker.
4. `view.tsx` wird zur Übersicht:
   - Kopf wie heute (Städteliste aus `bodies`, #1318).
   - **Anzeigetafel „Gerade in Bewegung"** (`.hh-tafel`, hell getönt, nie
     dunkel — Tims Regel „Keine dunklen Karten im Hellmodus"): drei Karten,
     `min_cities >= 5`, Oldenburg ≠ vorhanden, meiste Städte, dann zuletzt
     bewegt. Legende der Zeitleiste darunter.
   - Themenfeld-Chips mit Zahl (aus `movements` je Feld), Filter
     „Stand in Oldenburg" (Vorgabe „Noch offen" = fehlt + teilweise),
     Suche, Sortierung — alles als Query-Parameter an den Endpunkt, nichts
     clientseitig gefiltert.
   - Raster der Bewegungskarten, Blättern über `page`.
   - **„Einzelne Ideen"** darunter (§2.2) — die heutige Liste je Feld,
     `IdeenKarte` unverändert bis auf die Überschrift. Wie prominent: §7,
     Frage 2.
5. Leerzustände mit Lotti (Designsprache §1: Lotti nur in Empty States,
   Ladezuständen, „nichts gefunden"), Pose `search`.

**Test.** `lib/zeitleiste.test.ts`. Browsertest `tests/e2e/15-ideen.spec.ts`
mit **gemockten** Antworten (`page.route`) — die Ratsdatenbank ist in der CI
leer (`web/frontend/CLAUDE.md`): Tafel sichtbar, Feld-Umschalter ändert die
Anfrage, Klick auf eine Karte führt zur Ideen-Seite. `14-layout` muss die
Seite bei 390 und 320 px ohne Seitwärts-Scrollen bestehen (Chips laufen in
einem eigenen `overflow-x: auto`).

**Bild vor dem Merge** (Tims stehende Regel): Übersicht am Schreibtisch und
mobil, hell und dunkel, per `SendUserFile`; Gegenlesen abwarten.

**Kosten.** Kein Modell. Zwei Tage.


## PR 53 — Web: die Ideen-Seite

**Was sich ändert.** Neue Seite `web/frontend/app/(app)/council/ideen/bewegung/`
(`page.tsx`, `view.tsx`, `loading.tsx`), Adresse `?id=<cluster_id>`.

1. Kopf: Kicker Feld, Titel, Kennzahlen in Plex Mono (Städte, Vorlagen,
   Zeitraum).
2. **Bühne** (Tonfläche, Radius 18): „Wie die Idee durch die Räte lief" — je
   Stadt eine Zeile mit `Zeitleiste` auf der gemeinsamen Achse, Jahreszahlen
   darunter, Legende.
3. **Chronik**: alle Vorlagen nach Datum, je Eintrag Stadt, Datum,
   Ergebnis-Pille, Art · Einreicher (Plex Mono, `text-meta`), Titel als
   Link ins Original (extern markiert), Zusammenfassung (`text-lese`). Wo
   `reason` da ist: das Zitat kursiv ohne Anführungszeichen
   (Designsprache §1: Paraphrasen kursiv), mit Herkunft.
4. **Seitenspalte** (320–340 px, klebt; mobil darunter):
   - „Und in Oldenburg?" als Anzeigetafel: Pille, der Satz aus `situation`,
     `evidence` als Beleg-Liste mit internem Link auf den Beschluss,
     `related` darunter mit Überschrift **„Verwandtes aus Oldenburg"** —
     nie unter einem „nicht gefunden" als wären es Belege (§2.10).
   - „So haben die Räte entschieden": gestapelter Balken plus Liste.
   - Der Hinweis mit festem Ort (Designsprache §1, „Ehrlichkeit ist
     Designprinzip"): woher der Stand in Oldenburg kommt und warum ein Warum
     fehlt (`protocol_note`).
   - Rückmeldung „Stimmt das?" am Urteil je Idee — derselbe Baustein wie
     `Rueckmeldung`, mit `object_kind='cluster'` (Tabelle `feedback` kann
     das schon).
   - „Ähnliches Themenfeld": drei Links.
5. Navigation: Zurück zur Übersicht behält Feld, Filter und Suche
   (Query-Parameter, nicht Speicher).

**Test.** Browsertest mit gemockter Detail-Antwort: Zeilen je Stadt,
Chronik vollständig, „Verwandtes" erscheint nur unter `related`. `14-layout`.

**Bild vor dem Merge.** Eine Bewegung mit vielen Städten (*Kommunale
Wärmeplanung*, 8) und eine mit „Verwandtes" (*Kulturförderrichtlinie*), hell
und dunkel, Schreibtisch und mobil.

**Kosten.** Kein Modell. Zwei Tage.


## PR 54 — iOS: beide Flächen

**Was sich ändert.**

1. `Models.swift`: `Movement`, `MovementCity`, `TimelinePoint`, `TimeAxis`,
   `OldenburgVerdict`, `MovementsResponse`, `MovementDetail` — optionale
   Felder als Optionale (`ios/CLAUDE.md`, Decode-Fallen);
   `python3 scripts/ios_vertrag.py` grün.
2. `IdeasView.swift` bekommt die Übersicht: Tafel „Gerade in Bewegung" als
   `RatsWidget(board:)` (Anzeigetafel-Tönung, `RatsColor.board`), Feld-Chips,
   Filter, Suche, Karten; darunter „Einzelne Ideen" (die heutige `IdeaCard`).
3. `MovementDetailView.swift` (neu): Zeilen je Stadt mit einer
   `Zeitleiste`-View (Canvas oder `GeometryReader`, dieselbe Rechnung wie
   `lib/zeitleiste.ts` — **die Achse kommt vom Server**, gerechnet wird nur die
   Position), Chronik, „Und in Oldenburg?", Bilanz, Hinweis.
4. Dynamic Type und VoiceOver: jede Zeitleiste liest sich als Satz
   (Designsprache „Leserollen": kein Schrumpfen per `minimumScaleFactor`).
5. XcodeGen-Nachzug, falls neue Dateien (`ios/CLAUDE.md`).

**Test.** `ios_vertrag.py`; ein Snapshot-freier UI-Test, der die Übersicht
mit einer Fixture-Antwort lädt. Bild aus dem Simulator (eigenes Gerät per
`simctl create`, Memory „Simulator gehört fremder Sitzung"), hell und dunkel,
große Schrift.

**Freigabe.** TestFlight-Build; `APP_MIN_BUILD` bleibt, die neuen Endpunkte
brechen die ausgelieferte App nicht (sie ruft sie nicht).

**Kosten.** Kein Modell. Drei Tage.


## PR 55 — Daten auf Prod und Freigabe (Tims Entscheidung)

**Warum.** §2.9: Prod hat einen eigenen, älteren Bestand und einen pausierten
Cron. Fassung 5, `idea_groups`, `idea_fit` und die Hash-Nachzüge liegen nur
auf dev. Ein Release ohne Datenschritt zeigte auf Prod leere Bewegungen — und
ein wieder angeschalteter Cron beurteilte alles neu.

**Zwei Wege — Tim entscheidet (§7, Frage 4):**

- **A. Bestand von dev nach Prod kopieren.** `VACUUM INTO` auf dev,
  `gzip | ssh` (Regel: macOS-`rsync` kennt `--info=progress2` nicht), auf
  Prod neben die alte Datei legen, alte als `.vor-<datum>` behalten, Dienst
  neu starten (sonst hält er die alte Datei offen). Kein Modellaufruf. Danach
  ist Prod auf dem Stand von dev, einschließlich der 228 nachgeholten Urteile.
- **B. Auf Prod nachziehen.** `cities_fit_fassung5.py` samt `--hashes`,
  dann `rebuild_group_status`, `rebuild_idea_groups`, `idea_fit_all` — auf
  Prod mit dessen eigenem Bestand. Rund $1 und einige Stunden, der Cron bleibt
  währenddessen aus.

A ist billiger und macht beide Umgebungen gleich; B lässt Prods eigene Ernte
unangetastet. Die Empfehlung ist **A** — Prods Städte-Ernte ist seit dem
20.09. pausiert und hat seitdem nichts gesammelt, was dev nicht auch hätte.

**Danach, in dieser Reihenfolge:**

1. Release `dev` → `main` wie immer (Merge-Commit, Versionsschnitt,
   `ios_vertrag.py --ausgeliefert`).
2. `/api/council/cities/ideas/fields` einmal aufrufen (Migration 9 läuft
   beim ersten Öffnen, #1418), dann `idea_groups` zählen.
3. Tim sieht zwei Themenfelder durch (`fertig_wenn` von `ideen-anderswo`).
4. Erst dann `FEATURE_FLAGS=…,ideen-anderswo` in Prods `.env`.
5. Cron `check_cities` wieder an — erst nach einem Probelauf mit Messung
   (Regel 31), weil sein erster Lauf nach so langer Pause mehr zu tun hat.

**Kosten.** A: kein Modell. B: rund $1. Ein halber Tag Betrieb.


## Anhang A — Reihenfolge, Aufwand, Kosten

| PR | Was | Modell | gemessen / erwartet | Aufwand |
|---|---|---|---:|---|
| 46 | Gruppen-Status je Fassung | — | — | 2 h |
| 47 | `idea_groups` | — | — | 1 Tag |
| 48 | Urteil je Idee | `idea_fit` × 3 Stimmen | **≈ $0,60** (Probe entscheidet) | 2 Tage + Tims Prüfstand |
| 49 | Überschriften | — | — | ½ Tag |
| 50 | Endpunkte | — | — | 1½ Tage |
| 51 | Warum | `reason` | **$2,20**, 14 h (Probe: 20 → $0,0063) | Betrieb |
| 52 | Web: Übersicht | — | — | 2 Tage |
| 53 | Web: Ideen-Seite | — | — | 2 Tage |
| 54 | iOS | — | — | 3 Tage |
| 55 | Prod & Freigabe | — (A) / ≈ $1 (B) | — | ½ Tag |
| | **zusammen** | | **≈ $3 (A)** | **≈ 14 Tage** |

Laufende Kosten danach: Der Wochen-Cron fügt neue Vorlagen hinzu; `idea_fit`
läuft nur für Gruppen, deren Quell-Hash sich ändert. Bei einem gewöhnlichen
Sonntag (13.09.: $1,62 für alle Annotatoren) kommen einige Cent dazu.


## Anhang B — Was ausdrücklich NICHT in diesem Plan liegt

- **Ein Wächter aus dem Muster „Oldenburg hat kein …"** (§2.6) — gemessen
  falsch.
- **Ein „lohnt sich"-Urteil.** Das Modell traf es zu 46–58 % (Docstring
  `OldenburgStatus`); die Oberfläche zeigt Tatsachen, aus denen ein
  Ratsmitglied selbst schließt.
- **Ein Antragsentwurf aus einer Idee.** Naheliegend als nächster Schritt
  („Das könnte ich beantragen"), aber ein eigenes Feature mit eigener
  Ehrlichkeitsfrage — später, wenn die Seite genutzt wird.
- **Neue Städte** (Bonn, Darmstadt, `rubin.py`) — `plan-cities-phase5.md`,
  Stand-Abschnitt.
- **Hildesheim neu ernten** — gesperrt.
- **Pixelvergleiche** im Browsertest (`web/frontend/CLAUDE.md`: Gestaltung
  vor Tims Augen, Mechanik in Tests).
- **Die Stadtbezirks-Grenzfälle** (rund zehn Urteile „nicht anwendbar", weil
  Oldenburg keine Bezirksräte hat) — bleiben wie sie sind, bis Tim anders
  entscheidet (§7, Frage 6).


## Anhang C — Messbefehle

Alle gegen die lokale Kopie; für den aktuellen Stand vorher eine neue ziehen
(PR 55, Weg A, erster Schritt — nur bis zur Kopie).

```bash
# Kopie ziehen (dev → Mac), außerhalb jedes Arbeitsbaums
ssh tk-dev 'python3 -c "import sqlite3; sqlite3.connect(\"file:/home/tim/app/data/cities.sqlite?mode=ro\", uri=True).execute(\"VACUUM INTO \x27/home/tim/cities-kopie.sqlite\x27\")"'
ssh tk-dev 'gzip -c ~/cities-kopie.sqlite' > ~/.cache/ratslotse/cities/cities-$(date +%F).sqlite.gz
ssh tk-dev 'rm ~/cities-kopie.sqlite'
```

```python
# §2.2 und §2.3 — Gruppen nach Städten und Einigkeit des Oldenburg-Urteils
import sqlite3, json, collections
DB = "/Users/tim/.cache/ratslotse/cities/cities-2026-09-22.sqlite"
c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True); c.row_factory = sqlite3.Row
fit = {r["object_id"]: json.loads(r["payload"])["status"] for r in c.execute(
    "select object_id, payload from annotations where annotator='fit' and version='5'")}
body = {r["id"]: r["body_id"] for r in c.execute("select id, body_id from papers where body_id!='oldenburg'")}
drop, unbelegt = set(), set()
for r in c.execute("select object_id, payload from annotations where annotator='cluster_check'"):
    p = json.loads(r["payload"]); drop |= set(p.get("drop") or [])
    if p.get("stable") is False: unbelegt.add(int(r["object_id"].split(":")[1]))
g = collections.defaultdict(list)
for r in c.execute("select cluster_id, paper_id from idea_clusters where version='1'"):
    if r["paper_id"] in body and r["paper_id"] not in drop and r["cluster_id"] not in unbelegt:
        g[r["cluster_id"]].append(r["paper_id"])
print(collections.Counter(len({body[m] for m in ms}) for ms in g.values()))
ab3 = [ms for ms in g.values() if len({body[m] for m in ms}) >= 3]
print("uneinig:", sum(1 for ms in ab3 if len({fit[m] for m in ms if m in fit}) > 1), "von", len(ab3))
```

```python
# §2.5 — Kosten des Warum an 20 Abschnitten (auf einer WEGWERF-Kopie)
from council.cities.store import CitiesStore
from council.cities import reasons
with CitiesStore("/tmp/probe-cities.sqlite") as m:
    print(reasons.run(m, limit=20))   # → annotated, grounded, cost_usd, seconds
```

```sql
-- §2.7 — Gruppen-Status je fit-Fassung
select fit_version, count(*) from idea_group_status group by 1;
-- §2.5 — Niederschrift-Abschnitte je Stadt
select m.body_id, count(*) from protocol_sections s join meetings m on m.id = s.meeting_id group by 1;
```


## §7 — Offene Fragen an Tim, bevor PR 52 beginnt

Der Entwurf beantwortet sie vorläufig; bestätigt oder geändert werden sie
hier, nicht im Code.

1. **Ab wie vielen Städten ist eine Idee eine Bewegung?** Ab 2 wären es 292,
   ab 3 sind es 81. Der Entwurf zeigt ab 3. Vorschlag: Liste ab 2, Tafel ab 5.
2. **Wie prominent die Einzelideen?** Neun von zehn Vorlagen (§2.2). Vorschlag:
   eigener Abschnitt unter den Bewegungen, gleiche Filter, ohne Tafel.
3. **Wortlaut des Oldenburg-Standes.** Heute „In Oldenburg nicht gefunden /
   teilweise / Oldenburg hat das / Für Oldenburg nicht anwendbar". Alternative
   aus dem Brainstorming vom 14.09.: „anderswo beschlossen — hier noch nicht
   auf der Tagesordnung". Vorschlag: bleiben, weil sie ehrlich sagen, dass
   gesucht und nicht gefunden wurde.
4. **Daten auf Prod: Weg A (kopieren) oder B (nachziehen)?** Empfehlung A.
5. **Der Prüfstand für das Urteil je Idee:** 20 Gruppen, die Tim beurteilt
   (Status, und ob ein Beleg nur verwandt ist). Rund eine halbe Stunde.
6. **Die Bezirksrats-Fälle:** bei „nicht anwendbar" lassen (Oldenburg hat
   keine Stadtbezirke) oder als „fehlt" führen (die Stadt *könnte* sie nach
   NKomVG einrichten)?
7. **Gefällt der Entwurf?** Was bleibt, was fliegt — Tafel, Zeitleiste,
   Farben, Aufteilung der Ideen-Seite.


## Umsetzung und Bewertung (23.09.2026)

Tims Vorgaben (22.09.2026): Bewegungen ab **2** Städten (Tafel ab 5), Weg **A**,
die übrigen Vorschläge aus §7 wie vorgeschlagen.

### Stand

| PR | Was | Stand |
|---|---|---|
| 46 | Gruppen-Status je `fit`-Fassung | #1478, dev |
| 47+49 | `idea_groups`, Überschrift | #1480, dev |
| 48+50 | `idea_fit`, Endpunkte `/cities/movements…` | #1481, dev |
| 51 | Werkzeug `scripts/cities_tranchen.sh`, `--alle` | #1481, #1486; Lauf auf dev |
| — | Timeout 120 s für `fit`, `idea_fit`, `reason` | #1481, #1484 |
| 52–54 | Web, Ideen-Seite, iOS; Städtevergleich als Reiter „Andere Städte" der Analyse (Tims Wunsch 23.09.) | #1483, **wartet auf Tims Gegenlesen** |
| 55 | Weg A: dev-Datenbank nach Prod | **erledigt 23.09.**, alte als `cities.sqlite.vor-2026-09-23` |
| 55 | Release dev → main, Schalter auf Prod | Tims Entscheidung |

### Gemessen

- **Bewegungen:** 207 ab 2 Städten, 59 ab 3, 20 ab 5 (Oldenburg nicht
  mitgezählt, nur Ideen-Arten; die 292 aus §2.2 zählten beides mit).
  Aufbau 0,5 s, Listenabfrage 1 ms; Endpunkte lokal 34–110 ms.
- **`idea_fit`:** Probe 20 Ideen $0,053; alle 207 auf der Kopie $0,33, auf
  dev $0,46 (Wiederholungen nach Timeouts). 0 erfundene Kennungen im
  Ergebnis. Verteilung dev: 105 fehlt, 41 teilweise, 61 vorhanden, 0 nicht
  anwendbar.
- **Prüfstand** (`eval/run_cities_idea_fit.py`, 20 Fälle, **vorläufig von
  Claude gesetzt**): 17/20 streng, 19/20 nachsichtig, 0 erfunden, 0 falsches
  „vorhanden", 0 „nur verwandt" als Beleg; $0,034 je Lauf.
- **Reproduzierbarkeit:** Zwei unabhängige Läufe (Kopie und dev, leicht
  verschiedene Belege) geben bei 185 von 207 Ideen (89 %) denselben Stand.
  Die Abweichungen liegen fast alle an der Grenze zu „teilweise"; einer
  springt über zwei Stufen (Betriebskostenzuschüsse für Sportvereine).
- **`reason`:** Probe 20 Abschnitte $0,0067, 3 mit Begründung; Durchgang 1
  (995) $0,34, 42 mit Begründung. Alle gelesenen Begründungen stehen so im
  Abschnitt, keine nennt Personen.

### Befunde, die unterwegs behoben wurden

1. **Hängende Modellaufrufe.** Das SDK wartet ohne Angabe 600 s je Versuch;
   eine Probe stand über eine halbe Stunde still. Jetzt 120 s.
2. **`reason` hätte fast nichts bearbeitet.** Ohne Schalter nur Abschnitte
   mit Ideen-Gruppe — auf dev 157 von 6.962. Jetzt `--alle`.
3. **Dev fehlten 900 Niederschriften.** Prod hatte 1.164 gelesen und 22.048
   Abschnitte geschnitten, dev 278 und 6.962 (auf dev laufen keine Crons).
   Weg A hätte Prod diese Abschnitte genommen. Vor der Kopie wurden sie
   ergänzend von Prod nach dev übertragen (25.222 Abschnitte). §2.9 und
   PR 55 hatten angenommen, Prod habe nichts, was dev fehlt — das stimmte
   nicht.
4. **Belege doppelt** (Vorlage und ihr Beschluss) — jetzt einmal.
5. **Oberfläche nach den ersten Bildern:** Feld-Chips fehlten ohne Urteile,
   Tafel wiederholte den Listenanfang, Punkte stapelten oder wanderten in der
   Zeit, „Und in Oldenburg?" stand auf dem Handy unten, die Markierung einer
   gerollten Reiter-Leiste stand daneben.

### Vorschläge

1. **Globaler Timeout in `kern/llm.py`** statt je Aufrufer — betrifft auch
   die KI-Frage, deshalb nicht ohne Tim.
2. **Prüfstand von Tim beurteilen lassen** (§7, Frage 5); bis dahin misst er
   meinen Maßstab.
3. **Die Stufe „teilweise" schärfen**: bei uneinigen drei Stimmen zwei
   weitere einholen, oder im Prompt an Beispielen trennen, was „erste Stufe"
   und was „nur verwandt" ist.
4. **Gruppen nachschärfen:** „Jugendparlament einrichten" enthält Satzungen
   zum Jugendhilfeausschuss, die Wärmeplanung hängt an einem
   „Wärmewende-Beirat".
5. **dev-VM:** 2 GB im Swap, der API-Prozess belegt 2,5 GB.
6. **Die ~200 neueren Prod-Vorlagen** stehen nur in Prods Rohablage und
   kommen erst mit dem nächsten `check_cities`-Lauf zurück.
