# Umsetzungsplan Phase 4: von 6.908 „fehlt" zu den 42 Ideen, die es sind

Stand: 09.09.2026, abends. Dieser Plan folgt auf
[`plan-cities-phase3.md`](plan-cities-phase3.md) (PR 16–22, alle gemergt)
und auf die fünf Punkte vom selben Tag (#1226, #1227, #1230, #1231, #1233).
Er ist wie seine Vorgänger geschrieben: **ohne das Gespräch dahinter
ausführbar.** Jeder Abschnitt ist ein Pull Request, nennt Dateien,
Signaturen, Tests, Kosten und woran man erkennt, dass er fertig ist. Wo etwas
gemessen ist, steht die Zahl, und in Anhang C der Befehl, der sie liefert.

Wer das umsetzt, liest **vorher** vollständig: die Wurzel-`CLAUDE.md`,
`council/CLAUDE.md`, **`council/cities/CLAUDE.md`**, `scripts/CLAUDE.md`,
`tests/CLAUDE.md`, §0 der drei Vorgängerpläne (Regeln 1–17 gelten
unverändert) und die Docstrings von `council/cities/evidence.py`, `fit.py`,
`clusters.py`, `annotators.py` und `store.py`. Dazu `scripts/cities_bilanz.py`
— das ist das Messgerät dieses Plans.

## 0. Was am 09.09.2026 passiert ist, und was daraus folgt

Der Bestandslauf von `fit` über alle übertragbaren Vorlagen lief **zweimal**.
Der erste Lauf ($15,40) entstand auf einem halben Unterbau: Nur Oldenburg
war indiziert, die Cluster-Schicht kannte 16 % der Ideen, zwei von fünf
Beleg-Armen waren leer. Der zweite Lauf ($15,57) lief nach der Reparatur —
Index über alle 30.673 Vorlagen, 1.180 Cluster statt 536, Nachbar-Arm gegen
Oldenburgs Matrix statt gegen eine stadtblinde Tabelle, zwanzig statt zwölf
Beleg-Plätze. Vier Fehler dabei waren **stumm**: kein Absturz, kein roter
Test, nur schlechtere Daten (#1231, #1233; Einzelheiten in
`council/cities/CLAUDE.md` und den Commit-Texten).

Drei Regeln kommen deshalb zu 1–17 dazu:

18. **Die Reihenfolge `classify → index → cluster → fit` ist Pflicht**, und
    sie steht ab PR 25 als Wächter im Code, nicht als Satz in einem Plan.
    Ein `fit`-Lauf auf Vorlagen ohne Vektor ist ein Lauf mit toten Armen.
19. **Bei jedem Lauf über Minuten wird nach der ersten Tranche gemessen** —
    und zwar am Mechanismus („tragen die Arme bei?"), nicht am Ergebnis
    („hat sich die Verteilung bewegt?"). Die Verteilung darf gleich bleiben,
    wenn sie wahr ist; ein stummer Arm darf es nicht. Tims Anweisung vom
    09.09.: „bitte überprüfe bei langen jobs zwischendurch die ergebnisse".
20. **Ein Maßstab, der über verschiedene Mengen mittelt, ist kaputt.** Der
    Prüfstand maß den mittleren Rang über die *gefundenen* Fälle; mehr
    Treffer ließen ihn steigen, obwohl kein Fall schlechter stand. Bevor
    eine Prompt- oder Parameteränderung an einer Schranke scheitert, wird
    zuerst geprüft, ob die Schranke misst, was sie zu messen behauptet.

## 1. Zielbild

Heute beantwortet `scripts/cities_bilanz.py` die Frage aus Phase 3 mit einer
Zahl: Von 9.484 übertragbaren Vorlagen fehlen Oldenburg **6.908** (73 %),
davon liegen **262** in mindestens zwei anderen Räten. Das ist die Liste, die
die Karte „Ideen aus anderen Städten" zeigt.

Und diese Liste ist **noch nicht die, um die es geht.** Gemessen am
09.09.2026 gegen den Bestand (Anhang C, Befehl 2):

| Schritt | Einträge | Was herausfällt |
|---|---:|---|
| Ausgang: fehlt + 2+ andere Städte | **262** | — |
| Dubletten je Stadt und Cluster zusammengezogen | **120** | 195 Einträge in 53 Paaren — Potsdam steht mit *drei* Vorlagen zum selben Denkmalpflege-Konzept auf der Liste |
| nur, was jemand **vorgeschlagen** hat (Antrag, Vorlage, Anfrage, Änderungsantrag) | **73** | 47 Antworten, Mitteilungen und Berichte — die Verwaltung *reagiert*, das ist keine Idee |
| ohne Routine-Muster im Titel (Wahlordnung anpassen, Benutzungsordnung, …) | **64** | 9 Verwaltungsvorgänge, die jede Kommune führt |
| … und dahinter stehen | **42 Ideen** (Cluster) | |

Zehn zufällige der 64 lesen sich so:

> Verpackungssteuersatzung erlassen (5 Städte) · Nächtliches
> Mähroboter-Verbot prüfen (3) · Integrationsbudget aufstocken (2) ·
> Strafanträge bei Schwarzfahren unterlassen (2) · Integrierte
> Sportentwicklungsplanung (2) · Verkehrssicherheit an Haltestellenzugängen
> prüfen (5) · Arbeitsgelegenheiten nach §5 AsylbLG umsetzen (3) ·
> Evaluierung Klimabeirat umsetzen (2) · Prioritätenliste Bauleitplanung
> beschließen (2) · **Verpackungssteuer-Prüfung einstellen (5)**

Das ist eine Liste, mit der ein Ratsmitglied etwas anfangen kann — bis auf
den letzten Eintrag, der das Gegenteil des ersten will und trotzdem als
„fehlende Idee" zählt. Und **jeder dieser Schritte ist eine Tatsache, kein
Werturteil.** Kein Modell wird gefragt; drei der vier Schritte brauchen
nicht einmal einen neuen Annotator.

Am Ende dieses Plans:

```
  ┌────────────────────────────────┐ ┌────────────────────────────────┐
  │ A  Die Liste zählt IDEEN,      │ │ B  Jede Idee trägt ihre        │
  │    nicht Vorlagen: eine Zeile  │ │    RICHTUNG und ihr ERGEBNIS:  │
  │    je Cluster, mit den Städten │ │    „3 Räte führen ein, 1 stellt│
  │    dahinter. (PR 23, 24)       │ │    die Prüfung ein; 2× beschl.,│
  │                                │ │    1× abgelehnt" (PR 26, 27)   │
  └────────────────────────────────┘ └────────────────────────────────┘
  ┌────────────────────────────────┐ ┌────────────────────────────────┐
  │ C  Die Liste hat einen         │ │ D  Der Unterbau kann nicht     │
  │    eigenen Prüfstand:          │ │    mehr in falscher Reihenfolge│
  │    Präzision@20 gegen ein      │ │    laufen, und jeder Lauf misst│
  │    Golden Set von Tim (PR 28)  │ │    sich selbst (PR 25)         │
  └────────────────────────────────┘ └────────────────────────────────┘
```

Erst danach (PR 29) sieht die Karte anders aus. Tims Richtung von Phase 3
gilt weiter: erst die Daten, dann die Oberfläche.

## 2. Was gemessen ist und den Plan trägt

Alle Zahlen vom 09.09.2026, Befehle in Anhang C.

**Der Bestand.** 30.673 Vorlagen aus sechs Städten, 30.642 eingeordnet,
alle mit Vektor (85.256 Textabschnitte, 240.601 Nachbarschaften). 11.510
übertragbare Ideen in 1.180 Clustern über 3.641 Vorlagen; `cluster_check`
hat 395 Gruppen geprüft und 80 Mitglieder entfernt.

**Das Urteil.** `fit` v3, drei Stimmen je Vorlage, `deepseek-v4-flash`:
9.484 Urteile, 25.537 Stimmen, 74 unvollständig (0,3 %), 147 Drei-Wege-
Spaltungen, 17 verworfene Mehrheiten. Kosten $15,57, Dauer 59 Minuten bei
96 Arbeitern. Der Prüfstand gegen die vierzig Handfälle: Status 65–70 %,
falsche „vorhanden" 0, erfundene Belege 0.

**Die Belege.** `eval/run_cities_evidence.py`: 22 von 23 erwarteten Belegen
gefunden, Median-Rang 1,0, zwei Arme einig bei 91 % der „vorhanden"-Fälle
und 14 % der „fehlt"-Fälle. Beleg-Arten in 30 zufälligen Vorlagen des
Bestandslaufs: fts 189, decision 126, neighbor 74, chunk 49, cluster 9.

**Die Liste.** Die Tabelle in §1. Dazu: Von den 64 verbleibenden Einträgen
haben **33 kein Ergebnis** in ihrer eigenen Stadt (`outcome = none`) — die
Hälfte. Und `feedback` hat 0 Zeilen: Der Rückkanal aus Punkt 5 ist gebaut,
aber niemand mit Mandat sieht die Karte.

**Was die Zahlen NICHT sagen.** Ob die 42 Ideen *gute* Ideen sind, weiß
niemand — dafür gibt es keinen Maßstab, und PR 28 baut ihn. Und ob 73 %
„fehlt" zu hoch ist, lässt sich am Prüfstand nicht ablesen: Der misst
vierzig Fälle, die ich ausgesucht habe, nicht die Grundgesamtheit.

## PR 23 — Die Liste zählt Ideen, nicht Vorlagen

**Warum.** 195 der 262 Einträge sind Dubletten: dieselbe Stadt, derselbe
Cluster. Potsdam hat das Denkmalpflege-Konzept dreimal beantragt, Münster
den Jugendrat zweimal — auf der Liste sind das drei bzw. zwei „Ideen, die
Oldenburg fehlen". Nach dem Zusammenziehen bleiben 120.

**Was sich ändert.** Die Ideen-Abfragen in `council/cities/store.py`
(`_IDEEN_ZEILEN`, `_IDEEN_ZAEHLER`, `_IDEEN_GESAMT` — alle drei, Regel aus
`_ideen_args`) gruppieren nach `(body_id, cluster_id)`, wo ein Cluster
existiert, und nach `paper_id`, wo keiner existiert. Je Gruppe bleibt die
**jüngste** Vorlage als Vertreterin; die übrigen kommen als
`siblings: list[{id, name, date}]` mit.

Die Wahl der Jüngsten ist bewusst: Wer eine Idee dreimal beantragt hat,
hat sie beim dritten Mal am besten formuliert, und das Datum sagt, ob die
Sache noch läuft.

```python
# council/cities/store.py — neue Spalten in _IDEEN_ZEILEN
"       (SELECT json_group_array(json_object('id', p3.id, 'name', p3.name, "
"                                            'date', p3.date)) "
"        FROM idea_clusters k3 JOIN papers p3 ON p3.id = k3.paper_id "
"        WHERE k3.cluster_id = k.cluster_id AND k3.version = k.version "
"          AND p3.body_id = p.body_id AND p3.id != p.id) AS siblings_json "
```

und die Gruppierung als `WHERE NOT EXISTS (jüngere Schwester derselben
Stadt im selben Cluster)` — eine ganze statische Anweisung, kein
zusammengesetztes SQL (`tests/test_sql_spalten.py`).

**Antwortform.** `antworten.py::CitiesIdea` bekommt `siblings:
list[CitiesIdeaSibling]` (id, name, date). Vertrag neu schneiden
(`scripts/pruefe.py --nur vertrag,typen`), iOS-Modell nachziehen
(`Models.swift`, `pruefe.py --nur ios` **und** `swift test` in
`ios/Packages/RatslotseAPI` — der Wächter prüft Modelle, nicht Tests).
Die Oberfläche zeigt `siblings` in diesem PR **nicht** — nur die Zahl
ändert sich, und das ist die Messung.

**Test.** `tests/test_cities_store.py::test_ideen_liste_zieht_dubletten_je_stadt_zusammen`:
drei Potsdamer Vorlagen im selben Cluster → eine Zeile, `siblings` hat zwei
Einträge, die Vertreterin ist die jüngste. Und die Gegenrichtung: zwei
Vorlagen verschiedener Städte im selben Cluster bleiben zwei Zeilen.

**Messung.** `cities_bilanz.py` bekommt `--ideen` und zählt dann Gruppen
statt Vorlagen; die Tabelle in §1 ist das Vorher. Fertig, wenn die Zahl für
„fehlt + 2+ Städte" von 262 auf 120 fällt und `cities_ideas` denselben Wert
liefert.

**Kosten.** Keine.

## PR 24 — Nur, was jemand vorgeschlagen hat

**Warum.** 47 der 120 verbleibenden Einträge sind Antworten auf Anfragen,
Mitteilungsvorlagen und Berichte (`kind` in `answer`, `notice`, `report`).
Eine Antwort der Verwaltung auf eine Kleine Anfrage ist keine Idee, die
Oldenburg fehlt — sie ist die Reaktion auf eine. Die Idee steht in der
Anfrage, und die ist meistens selbst im Cluster.

Dazu 9 Einträge, deren Titel oder Instrument ein Routine-Muster trifft
(„Wahlordnung anpassen", „Benutzungsordnung Sportstätten", „Neufassung der
Gebührenordnung"). Fünf Räte behandeln so etwas, weil jede Kommune es
behandelt — das Signal „in fünf Städten" misst hier Alltäglichkeit.

**Was sich ändert.**

1. `council/cities/model.py`: `IDEA_KINDS = ("motion", "proposal",
   "inquiry", "amendment")` mit Docstring, warum `answer`/`notice`/`report`
   fehlen. Die drei Ideen-Abfragen filtern `p.kind IN (…)` — als
   Platzhalterliste über `_ideen_args`, nicht als String-Verkettung.
2. Die Routine-Frage wird **erst gemessen, dann entschieden.** Der Regex aus
   Anhang C (Befehl 2) trifft 32 der 262 Ausgangseinträge. Bevor er in den
   Code kommt, gehen diese 32 einmal von Hand durch (eine halbe Stunde) und
   bekommen je einen Satz: Routine oder Idee? Sind ≥ 80 % Routine, kommt der
   Regex als `ROUTINE_RE` nach `model.py` und in die Abfrage. Sind es
   weniger, bleibt er draußen, und die Frage geht als Feld `routine: bool`
   in `classify` Fassung 3 — dann aber mit Golden Set und Prüfstand, nicht
   aus dem Bauch.

   Die Handdurchsicht wird eingecheckt: `eval/routine_32.md`, ein Eintrag
   je Vorlage. Sie ist der Beleg für die Entscheidung, welche auch immer
   fällt.

**Test.** `test_ideen_liste_zeigt_keine_antworten`: eine Antwort und ein
Antrag im selben Cluster → nur der Antrag auf der Liste. Wächter in
`test_cities_guards.py`: `IDEA_KINDS` ist eine Teilmenge von
`model.Kind`-Werten (ein Tippfehler dort filtert sonst still alles weg).

**Messung.** 120 → 73 (→ 64 mit Regex). Fertig, wenn `cities_bilanz.py
--ideen` das zeigt und die zehn zufälligen Einträge aus §1 sich nicht
verschlechtert haben — dafür steht in Anhang C ein fester Seed.

**Kosten.** Keine (Weg 1). Weg 2, falls nötig: classify v3 über 9.632
übertragbare Vorlagen, 0,26 $/1.000 → ~$2,50.

## PR 25 — Die Stufe `fit` im Backfill, mit Wächter und Stichprobe

**Warum.** Der Bestandslauf lief am 09.09. aus einem Skript in `/tmp`, weil
`cities_backfill.py` die Stufe `fit` nicht kennt — und deshalb gab es
nichts, was die Reihenfolge geprüft hätte. Der Cron
(`scripts/check_cities.py`) macht es richtig; der Mensch mit `--stage` hat
keine Sicherung. $15,40 sind der Preis dieser Lücke.

**Was sich ändert.** `scripts/cities_backfill.py`:

```python
p.add_argument("--stage", choices=(…, "cluster", "fit"))
```

Vor `fit` läuft `_unterbau_pruefen(main_store)`, und die **weigert sich**:

```python
def _unterbau_pruefen(main: CitiesStore) -> list[str]:
    """Was vor `fit` wahr sein muss — sonst urteilt das Modell mit toten Armen.

    Gemessen am 09.09.2026: 21.700 fremde Vorlagen ohne Vektor, Cluster über
    16 % der Ideen, zwei von fünf Beleg-Armen leer, $15,40 für nichts.
    """
    befunde = []
    stand = main.stats(EMBED_MODEL)
    ohne_vektor = sum(z["papers_unembedded"] for z in stand)
    if ohne_vektor:
        befunde.append(f"{ohne_vektor} Vorlagen ohne Vektor — erst --stage index")
    if main.clusters_older_than_embeddings(EMBED_MODEL, CLUSTER_VERSION):
        befunde.append("Cluster älter als der jüngste Vektor — erst --stage cluster")
    return befunde
```

`clusters_older_than_embeddings` ist eine neue Store-Methode: vergleicht
`MAX(created_at)` beider Tabellen. `--trotzdem` überstimmt den Wächter mit
einer Zeile im Log, warum.

Und die **Stichprobe** (Regel 19): `fit.run()` bekommt `probe_after: int =
300`. Nach so vielen Urteilen ruft es `evidence.arm_census(main, rats,
kandidaten[:30], …)` — eine neue Funktion, die für dreißig Vorlagen die
Beleg-Arten zählt, ohne Modell — und loggt sie als eine Zeile. Fehlt eine
Art, die es im Bestand geben muss (`neighbor` bei > 0 Oldenburger Vektoren,
`cluster` bei > 0 Clustern mit Oldenburger Mitglied), **bricht der Lauf
ab**, statt weiterzubezahlen. Was `arm_census` liefert, steht ohnehin in
`stand` und damit in `job_runs`.

**Test.** `test_cities_backfill.py::test_fit_weigert_sich_ohne_vektoren`;
`test_cities_fit.py::test_stichprobe_bricht_bei_totem_arm_ab` (Matrix leer,
aber `object_embeddings` gefüllt → Abbruch nach `probe_after`).

**Messung.** Keine Zahl — ein Wächter. Fertig, wenn beide Tests rot werden,
sobald man die Prüfung entfernt (gegenprüfen, wie in #1231).

**Kosten.** Keine.

## PR 26 — Die Richtung einer Idee

**Warum.** „Verpackungssteuersatzung erlassen" (Braunschweig) und
„Verpackungssteuer-Prüfung einstellen" (Magdeburg) liegen im selben Cluster
— zu Recht, es ist dieselbe Sache — und beide stehen als fehlende Idee auf
der Liste. `cluster_check` hat das gesehen und ausdrücklich *behalten*: Die
Gruppe ist richtig, die Richtung ist verschieden. Was fehlt, ist ein Feld,
das die Richtung trägt.

**Was sich ändert.** Neuer Annotator `stance`, Fassung 1, nur für Vorlagen
in einem Cluster mit ≥ 2 Städten (`needs_index=True`, eigener
`candidates_for` in `clusters.py`):

```python
STANCE_VALUES = ("introduce", "expand", "restrict", "stop", "review")

class IdeaStance(BaseModel):
    stance: Literal[STANCE_VALUES]
    reason: str = Field(max_length=200)
```

`review` ist die Prüfbitte („prüfen, ob …"), `stop` das Einstellen oder
Abschaffen, `restrict` das Einschränken. Prompt `cities_stance_user` in
`kern/prompts.py`, Batch 6 wie `classify` (kein Kontext nötig, die Frage
steht im Titel), Modell wie `classify`.

Die Ideen-Zeile bekommt `stances: {introduce: 3, stop: 1}` je Cluster — als
Spalte in `_IDEEN_ZEILEN`, gezählt über die Mitglieder anderer Städte,
ausgeschlossene (`cluster_check.drop`) nicht mitgezählt. Die Liste selbst
filtert **nicht** danach: Dass Magdeburg die Prüfung eingestellt hat, ist
für Oldenburg eine Information, keine Disqualifikation. Nur die
Sortierung ändert sich: `introduce + expand` zählen als Stimmen dafür, die
übrigen nicht.

**Golden Set.** `eval/cases_cities_stance.json`, 40 Fälle aus Clustern mit
≥ 3 Städten, von Hand: id, name, stance, ein Satz. Prüfstand
`eval/run_cities_stance.py` nach dem Muster von `run_cities_effort.py`
(Nachlauf für ausgelassene Fälle, Weigerung bei unvollständigem Lauf —
Lehre aus PR 18). Schranke: 85 % (die Klassen sind trennscharf, `review` ist
die einzige strittige).

**Test.** Payload-Test wie für `IdeaEffort`; `test_alte_werte` kennt die
neuen Werte; Store-Test für die Zählung mit einem ausgeschlossenen Mitglied.

**Messung.** Wie oft steht ein `stop`/`restrict` neben einem `introduce` im
selben Cluster? Gemessen wird das erst nach dem Lauf, aber die Zahl gehört
in den PR-Text. Fertig, wenn der Prüfstand besteht und die Verpackungssteuer
auf der Liste als „4 Räte führen ein, 1 stellt die Prüfung ein" erscheint.

**Kosten.** ~3.641 Vorlagen in Batches von 6, ~600 Aufrufe → **< $1**.

## PR 27 — Die Hälfte der Liste hat kein Ergebnis

**Warum.** Von den 64 Einträgen nach PR 23/24 tragen 33 `outcome = none`.
Für die Frage aus Phase 3 („wie ging es dort aus?") ist das die halbe
Antwort, die fehlt — und für die Sortierung der Liste (PR 26: beschlossen
zählt mehr als beantragt) ebenso.

Die Ursachen sind bekannt, aber nicht für *diese* Vorlagen gemessen: fehlende
Beratungsfolge (PR 16 hat vier Ernte-Fehler behoben, nicht alle Städte
liefern `consultation`), unbekanntes Ergebnis-Vokabular
(`pruefung.unbekanntes_vokabular`), oder die Sache ist schlicht noch offen.

**Was sich ändert.** Erst messen: `scripts/cities_bilanz.py --ergebnisse`
zählt für die Listeneinträge ohne Ergebnis, woran es liegt — keine
Beratung / Beratung ohne `result_raw` / `result_raw` unbekannt / jüngste
Beratung in der Zukunft. Die Tabelle steht im PR-Text.

Dann, je nach Befund:

- **Unbekanntes Vokabular** → Regel in `model._OUTCOME_RULES`, mit Test
  (das Muster aus PR 16: „nicht empfohlen", „ohne Beschlussfassung
  geschoben").
- **Keine Beratung** → prüfen, ob die Stadt `consultation` liefert und der
  Adapter sie liest. Osnabrück und Braunschweig (ALLRIS) tun es; für
  SessionNet-Städte gilt `link_within_meeting`.
- **Noch offen** → nichts zu tun; die Zeile trägt „läuft seit <Datum>".

**Test.** Je gefundener Regel ein Fall in `test_cities_model.py`.

**Messung.** Anteil der Listeneinträge mit Ergebnis, vorher 31 von 64
(48 %). Fertig, wenn ≥ 80 % — oder wenn die Tabelle zeigt, dass der Rest
wirklich offen ist.

**Kosten.** Keine (kein Modell; ggf. eine Nachernte je Stadt).

## PR 28 — Ein Prüfstand für die Liste

**Warum.** Alle Prüfstände messen **Einzelurteile**: Ist der Status richtig,
der Beleg gefunden, die Aufwandsklasse getroffen? Keiner misst die
**Liste**: Sind die zwanzig obersten Einträge zwanzig, die ein Ratsmitglied
sehen will? Genau das ist die Frage, an der Phase 3 und die fünf Punkte
gearbeitet haben, und sie hat keinen Maßstab.

**Was sich ändert.** `eval/cases_cities_list.json`: die **obersten 100**
nach PR 23/24 (Sortierung wie `_IDEEN_ZEILEN`), je Eintrag `id`, `name`,
`cities`, und von Hand `on_list: bool`, `why: str`. Das füllt **Tim** — es
ist dasselbe Gegenlesen wie bei den vierzig Handfällen, nur mit einer
anderen Frage: nicht „stimmt das Urteil?", sondern „gehört das auf die
Liste?". Ein Vormittag.

`eval/run_cities_list.py` rechnet Präzision@20 und @50 gegen die aktuelle
Sortierung, **ohne Modell**, in Sekunden. Zwei Schranken, beide erst nach
der ersten Messung festgelegt (Regel 15: erst messen, dann die Zahl):
P@20 und der Anteil `on_list: false`-Einträge unter den ersten fünfzig.

Der Prüfstand ist der Maßstab für **alles Weitere** — jede Sortierung, jeder
Filter, jede neue Annotation muss ihn halten oder heben. Ohne ihn ist jede
Änderung an der Liste eine Meinung.

**Test.** Kein Wächter; die Datei selbst ist der Test. `test_cities_guards`
prüft nur, dass jede `id` im Bestand existiert (eine gelöschte Vorlage
sähe sonst aus wie ein Fehltreffer).

**Messung.** Die erste P@20. Fertig, wenn die Zahl im PR-Text steht und die
Schranken daraus abgeleitet sind.

**Kosten.** Tims Zeit. Sonst keine.

## PR 29 — Die Karte zeigt Ideen (Web + iOS)

**Warum.** Erst jetzt. Die Karte aus Phase 2 zeigt Vorlagen; nach PR 23–27
trägt jede Zeile Geschwister, Richtungen und Ergebnisse, und die Karte
weiß nichts davon.

**Was sich ändert.** `web/frontend/app/(app)/council/ideen/view.tsx` und
`ios/…/IdeasView.swift`, featuregleich:

- Kopf: Instrument, dann die Städte als Chips — je Chip die Richtung als
  Präfix (▲ einführen, ▼ einstellen, ? prüfen) und das Ergebnis als Ton
  (beschlossen / abgelehnt / offen; **Anzeigetafel-Tönung, kein Dunkel im
  Hellen**).
- „Potsdam · 3 Vorlagen 2024–2025" statt drei Zeilen; aufklappbar auf die
  Geschwister.
- Der Rückkanal (`Rueckmeldung`) bleibt an der Zeile, gilt jetzt für die
  Idee, nicht die Vorlage — `feedback.paper_id` bleibt die Vertreterin,
  keine Migration.

Keine neue Logik im Frontend: Zählen, Sortieren, Filtern kommt aus PR 23–27.
**Bild per `SendUserFile` vor dem Merge, Tims Gegenlesen abwarten.**

**Test.** Vertragstest beider Clients; `swift test`; Browsertest für das
Aufklappen.

**Messung.** Keine Zahl. Fertig nach Tims Gegenlesen.

**Kosten.** Keine.

## PR 30 — Betrieb: dev-VM, Prod-Schalter, Rückkanal in Betrieb

**Warum.** `feedback` hat 0 Zeilen, weil die Karte nur lokal jemand sieht.
Der Rückkanal ist das billigste Golden Set (Phase 3, Anhang B) — und er
liefert nichts, solange niemand mit Mandat davorsitzt.

**Was sich ändert.**

1. **Backfill auf der dev-VM** in der richtigen Reihenfolge, mit dem
   Wächter aus PR 25: `cities_backfill.py --run --stage annotate --stage
   index --stage cluster --stage fit`. Nach jeder Stufe `--pruefen`. Dauer
   auf 2 Kernen: Index ~2 h, `fit` mit `CITIES_FIT_WORKERS=32` ~3 h, ~$16.
   Die VM hat dieselben Rohdaten wie lokal; die Annotationen könnten auch
   kopiert werden — aber ein Lauf auf der VM ist der Beweis, dass der Cron
   sie ab dann selbst nachzieht.
2. **`andere-staedte` und `ideen-anderswo` auf Prod** — Tims Wort. Erst
   nach PR 29 und nach dem Backfill dort (gleiche Schritte, gleiche Kosten).
3. **Rückmeldungen auswerten**: `scripts/cities_bilanz.py --rueckmeldungen`
   zeigt je Urteil Ja/Nein-Zähler und die zehn umstrittensten. Ab 50
   Rückmeldungen wandern die in `eval/cases_cities_fit.json` — das Golden
   Set wächst (Regel 16).

**Test.** Keine Codeänderung außer dem Bericht.

**Messung.** Zahl der Rückmeldungen nach zwei Wochen auf Prod. Fertig, wenn
die erste Handvoll drin ist und die Auswertung sie zeigt.

**Kosten.** ~$16 dev-VM, ~$16 Prod, einmalig.

## Anhang A — Reihenfolge, Aufwand, Kosten

| PR | Was | hängt an | Aufwand | Modellkosten |
|---|---|---|---|---:|
| 25 | Wächter + Stichprobe im Backfill | — | ½ Tag | 0 |
| 23 | Ideen statt Vorlagen | — | 1 Tag | 0 |
| 24 | nur Vorgeschlagenes; Routine gemessen | 23 | ½ Tag + ½ h Handdurchsicht | 0 (ggf. $2,50) |
| 28 | Prüfstand für die Liste | 23, 24; **Tim** | ½ Tag + Tims Vormittag | 0 |
| 26 | Richtung der Idee | 23 | 1 Tag | < $1 |
| 27 | Ergebnisse für die Liste | 23, 24 | ½–1 Tag | 0 |
| 29 | Karte Web + iOS | 23–27; **Tims Bild** | 1 Tag | 0 |
| 30 | dev-VM, Prod, Rückkanal | 25, 29; **Tims Wort** | ½ Tag + Laufzeit | ~$32 |

PR 25 zuerst, weil er billig ist und den teuersten Fehler dieses Tages
unmöglich macht. 23 und 24 sind die Messung aus §1 als Code. 28 kann
parallel zu 26/27 laufen — Tims Teil davon braucht nur die Liste nach 24.
Nichts davon ist gestapelt: jeder PR von `dev`, jeder für sich mergebar.

Gesamt: rund sechs Arbeitstage, unter $40, davon $32 Betrieb.

## Anhang B — Was ausdrücklich NICHT in diesem Plan liegt

- **„Lohnt sich" zurückholen.** Nein. Gemessen über drei Fassungen 46–58 %
  mit 20 Punkten Streuung, verschärft 32 %. Was dieser Plan stattdessen
  tut — Dubletten, Vorlagenart, Richtung, Ergebnis, Prüfstand für die Liste
  — ersetzt das Werturteil durch fünf Tatsachen. Sollte P@20 aus PR 28
  danach unter 50 % liegen, ist die Frage neu zu stellen; vorher nicht.
- **Neue Städte.** Unverändert Registry-Eintrag plus Backfill, jetzt mit
  dem Wächter aus PR 25 — kein PR.
- **Antragsentwürfe.** Unverändert: eine Stufe über dem, was gesichert ist.
  Nach PR 28 gibt es zum ersten Mal eine Zahl, die sagt, ob die Liste die
  Grundlage dafür wäre.
- **Ein anderes Modell für `fit`.** Der Prüfstand steht, der Vergleich ist
  ein Nachmittag (`scripts/cities_modellvergleich.py`). Aber der Engpass
  ist nicht mehr das Urteil, sondern die Liste — erst 28, dann die Frage.
- **Die Nachbartabelle stadtweise umbauen.** `neighbors` hält 8 je Objekt
  über alle Städte; der Beleg-Arm braucht sie nicht mehr (#1233). Wer sie
  für die freie Suche (`search_ideas`) stadtweise braucht, misst erst, ob
  die Suche darunter leidet.

## Anhang C — Messbefehle

Alle vom Repo-Root, gegen `data/cities.sqlite` und `data/council.sqlite`.
**Nie, während ein Lauf schreibt** (ein Schreiber je Datei).

1. **Die Bilanz** — Verteilung, Staffelung, Themenfelder, Aufwand:
   ```bash
   python scripts/cities_bilanz.py
   python scripts/cities_bilanz.py --ab 3 --zeigen 40
   ```
2. **Die Liste vermessen** (die Tabelle aus §1). Bis PR 23/24 die Filter in
   den Store bringen, liegt die Messung als Skript bei; danach ist es
   `cities_bilanz.py --ideen`:
   ```bash
   python scripts/cities_bilanz.py --ideen        # ab PR 23
   ```
   Fester Seed für die zehn Stichproben: `random.seed(3)`.
3. **Unterbau prüfen** (ab PR 25 automatisch vor `fit`):
   ```bash
   python scripts/cities_backfill.py              # Spalten „o. Einordn.", „o. Vektor"
   python scripts/cities_backfill.py --pruefen    # Plausibilität, Vokabular
   ```
4. **Beleg-Arme lebendig?** (Regel 19, ohne Modell, 30 Sekunden):
   ```bash
   python eval/run_cities_evidence.py             # 22/23, Median 1,0, einig 91 %/14 %
   ```
5. **Die Prüfstände**, die dieser Plan halten muss:
   ```bash
   python eval/run_cities_fit.py                  # ~$0,03, 40 Fälle, 3 Stimmen
   python eval/run_cities_effort.py               # ~$0,01
   python eval/run_cities_stance.py               # ab PR 26
   python eval/run_cities_list.py                 # ab PR 28, ohne Modell
   ```
6. **Bestandslauf `fit`**, wenn er je wieder nötig ist (nach PR 25):
   ```bash
   CITIES_TERM_WORKERS=24 CITIES_FIT_WORKERS=96 \
     python scripts/cities_backfill.py --run --stage fit --verbose
   ```
   Erwartung: Belege ~20/s (7 min), Urteile ~2,2/s (~60 min), ~$16. Nach
   300 Urteilen steht die Stichprobe im Log; fehlt dort `neighbor`, ist der
   Lauf abgebrochen, und der Grund steht darüber.
