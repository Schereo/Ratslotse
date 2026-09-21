# Umsetzungsplan: Die KI-Frage bekommt einen Zeitbezug

Stand: 21.09.2026. Dieser Plan ist wie seine Vorgänger geschrieben: **ohne das
Gespräch dahinter ausführbar**. Jeder Abschnitt ist ein Pull Request, nennt
Dateien, Signaturen, Tests, Kosten und woran man erkennt, dass er fertig ist.
Wo eine Zahl steht, steht in Anhang C der Befehl, der sie liefert — jede Zahl
in diesem Plan ist am 21.09.2026 **gegen Prod** gemessen, nicht geschätzt.

Wer das umsetzt, liest vorher: die Wurzel-[`CLAUDE.md`](../CLAUDE.md),
[`council/CLAUDE.md`](../council/CLAUDE.md),
[`web/backend/CLAUDE.md`](../web/backend/CLAUDE.md),
[`tests/CLAUDE.md`](../tests/CLAUDE.md) und den Abschnittskopf von
`council/qa.py` (die Fragetyp-Registry und warum sie so aussieht). Dazu
[`REZEPTE.md`](../REZEPTE.md) — PR 1 schneidet den Ereignis-Vertrag neu, und
das Rezept dafür steht dort.

## 0. Der Anlass

Am 21.09.2026 hat Torge (Konto 37, Ratsmitglied, Thema „Donnerschwee")
fünfmal nach **Neu-Donnerschwee** gefragt und fünfmal „Frage fehlgeschlagen."
bekommen. Das war ein `KeyError: 'slug'` und ist mit
[#1424](https://github.com/Schereo/Ratslotse/pull/1424) behoben.

Danach ist dieselbe Frage auf Prod noch einmal gestellt worden, um zu sehen,
was er eigentlich bekommen hätte. Die Antwort ist **belegtechnisch sauber** —
jede Fußnote geprüft, keine erfunden — und **inhaltlich acht Jahre alt**:

> **Kurz gesagt:** Für Neu-Donnerschwee ist vor allem die Entwicklung des
> ehemaligen Kasernengeländes zu einem Wohnquartier **geplant** […]
> Ein zentraler Schritt hierfür war der Satzungsbeschluss für den
> vorhabenbezogenen Bebauungsplan Nr. 58 im **Oktober 2018** […]

Das Quartier steht. Der jüngste Beleg der ganzen Antwort ist von **Februar
2023**. Kein Satz sagt das.

Dieser Plan behebt nicht „das Modell hat sich geirrt" — es hat korrekt
referiert, was im Kontext stand. Er behebt, dass **die Zeit im Kontext nicht
vorkommt**: Das Datum steht zwar an jedem Beschluss, aber nirgends steht,
welcher Tag heute ist, wie alt der jüngste Treffer ist und ob der Rat
überhaupt noch getagt hat. Ein Sprachmodell, das das nicht weiß, schreibt
Vergangenes im Präsens.

## 1. Zielbild

```
  HEUTE                                   NACH DIESEM PLAN
  ─────                                   ────────────────
  „Für Neu-Donnerschwee ist die           „Zu Neu-Donnerschwee hat der Rat
   Entwicklung … geplant."                 seit Februar 2023 nichts mehr
   (Beleg: Oktober 2018)                   entschieden. Was damals geplant
                                           wurde, ist inzwischen gebaut: …"

  „Was ist in Donnerschwee zuletzt        „Die jüngste Abstimmungs-
   beschlossen worden?" → freie            entscheidung mit Ortsbezug
   Modellantwort, führt mit dem            Donnerschwee war am 1. Juni 2026:
   Stadion, nennt den Ort nie              Stadionneubau Maastrichter
                                           Straße [20947]."
                                           (der deterministische Weg, den es
                                            längst gibt — er wurde nur nicht
                                            erreicht)
```

Drei Regeln, die für jeden PR dieses Plans gelten:

1. **Die Zeit ist deterministisch, nie geraten.** Alter, letzte Sitzung,
   nächste Sitzung kommen aus der Datenbank in den Kontext. Das Modell darf
   formulieren, nicht rechnen — dieselbe Trennung wie bei `geld_grafik` und
   `latest_place_answer`.
2. **Kein neuer LLM-Aufruf.** Alle vier PRs kommen ohne zusätzlichen Call aus;
   die Kosten ändern sich um die Prompt-Tokens der neuen Zeilen (< 100 je
   Frage, s. §5).
3. **Jeder PR bringt seinen Wächter mit**, und der Wächter muss gegen den
   Stand *vor* dem PR rot sein. Der Nachweis gehört in die PR-Beschreibung.

## 2. Was gemessen ist

### 2.1 Der Prompt kennt das heutige Datum nicht

`kern/prompts.py::qa_antwort` bekommt `{question}`, `{context}`, `{presse}`,
`{steckbrief}`, `{extra_regeln}` — **kein Datum**. `grep -n "Heute ist\|date.today"
kern/prompts.py` ist leer; `date.today()` kommt in `council/qa.py` genau
zweimal vor, beides in der Sitzungs-Auflösung (`_finde_sitzungen`), nie im
Antwort-Prompt.

Was der Prompt heute an Zeit-Regeln hat:

| Regel | Was sie leistet | Was sie nicht leistet |
|---|---|---|
| „Passen mehrere Beschlüsse, nenne die neuesten zuerst." | Reihenfolge | sagt nichts über Alter |
| „⚠ ÄLTERE STATION … die neuere gilt als aktueller Stand" | überholte Stationen **derselben Vorlage** | greift nicht, wenn es gar keine neuere Station gibt |
| `EXTRA_REGELN["place"]`: „ist der Bestand dünn, sage das ausdrücklich" | Menge | „dünn" ≠ „alt" |

Das Muster für die Lösung steht schon im Haus, in `geld_regeln(eng=True)`:

> „Die Haushaltszahl im Kontext bekommt IMMER ihr Jahr und ihre Quelle mit
> (‚laut Jahresabschluss 2024') — sonst behauptet der eine Satz eine
> Aktualität, die die Daten nicht haben."

Genau dieser Satz fehlt für Beschlüsse.

### 2.2 Die kleinen Orte sind die alten Orte

Jüngster Beschluss je Katalogort (Prod, 21.09.2026, Befehl in Anhang C):

| Ortsart | Orte | jüngster Beschluss |
|---|---:|---|
| die 31 flächendeckenden Ortsbereiche | 31 | 30× 2026, 1× 2024 (Nordmoslesfehn) |
| die 9 benannten Quartiere/Gebiete | 9 | **6× vor 2026** |

Im Einzelnen, und das ist der Kern des Problems:

| Ort | Beschlüsse | jüngster |
|---|---:|---|
| Eversten-West | 20 | **14.10.2021** |
| Bornhorster Huntewiesen | 9 | 25.11.2024 |
| Hundsmühler Höhe | 10 | 28.04.2025 |
| Eversten Holz | 12 | 05.06.2025 |
| Osternburger Utkiek | 6 | 12.11.2025 |
| Neu-Donnerschwee | 25 | 12.02.2026, davor 09.02.2023 |
| Technologiepark Oldenburg | 13 | 19.02.2026 |
| Alte Fleiwa | 16 | 01.06.2026 |
| Nördliche Innenstadt | 25 | 18.06.2026 |

**Das sind exakt die Orte, die einen Steckbrief haben** — also die, die jemand
beim Namen nennt, weil er dort wohnt. Wer „Eversten-West" fragt, bekommt heute
eine Antwort im Präsens über einen Stand von 2021, ohne Hinweis.

### 2.3 Der Rat tagt gerade nicht

| Frage | Antwort aus der Prod-DB |
|---|---|
| jüngste Sitzung **mit Beschlüssen** | 29.06.2026 |
| nächste Sitzung überhaupt | 21.09.2026 (Verkehrsausschuss) |
| Lücke | **fast drei Monate** (Sommerferien + Kommunalwahl) |

`council/sitzungspause.py` erklärt genau das — fertig formuliert, mit
Ferienkalender bis 2027 und dem Sonderfall Kommunalwahl 2026. Die KI-Frage
liest dieses Modul **nicht** (`grep -rn "sitzungspause" council/qa.py` ist
leer); nur die Übersichtsseite tut es. „Seit Juni hat der Rat nichts
entschieden" ist damit für JEDE Frage im September die halbe Antwort — und
steht in keiner.

### 2.4 „zuletzt" + Ort erreicht seinen eigenen Weg nicht

Es gibt bereits eine deterministische Antwort für genau diesen Fragetyp:
`qa.latest_place_answer` (nutzt `latest_real_decision`, überspringt also
Kenntnisnahmen und Vertagungen). Sie wird nur erreicht, wenn im Router

```python
latest_place = bool(ort and typ == "place"
                    and (qa.latest_intent(q_suche) or qa.latest_intent(q)))
```

**alle drei** Teile wahr sind. Gemessen an der echten Frage:

| Frage | `ort` | `latest_intent` | `typ` (vom Analysemodell) | `latest_place` |
|---|---|---|---|---|
| „Was ist in Donnerschwee zuletzt beschlossen worden?" | Donnerschwee | **True** | **`history`** | **False** |

`typ` ist das einzige Glied, das kippt — und es kommt aus einem Sprachmodell.
Die Frage ist gleichzeitig eine Verlaufsfrage und eine Ortsfrage; beide
Einordnungen sind vertretbar. Der deterministische Weg darf nicht an dieser
Münze hängen.

Folge in der Praxis: Die Antwort führte mit dem **Stadionneubau Maastrichter
Straße** und nannte Donnerschwee in der Kurzfassung mit keinem Wort. Das ist
nicht falsch — `council_locations` führt Maastrichter Straße und
Weser-Ems-Halle mit `district='Donnerschwee'`, der Ortsfilter hat korrekt
gearbeitet —, liest sich aber wie die Antwort auf eine Stadionfrage.

### 2.5 Der Nachbarort im selben Satz

Der Kontext zu Beschluss 15159, wörtlich wie das Modell ihn sah:

```
[15159] Straßenbenennung nach Rosa Lazarus (Rat · 28.09.2020 · accepted):
Die Benennung einer Straße nach Rosa Lazarus im zukünftigen Wohnbereich des
ehemaligen Fliegerhorstes wird beschlossen. — Federführung: … —
Ortsbezug: Neu-Donnerschwee; Fundstelle: Gelände in Neu-Donnerschwee
```

Die Zusammenfassung sagt **Fliegerhorst**, der belegte Ortsbezug sagt
**Neu-Donnerschwee**. Das Modell hat die Zusammenfassung genommen und in eine
Neu-Donnerschwee-Antwort geschrieben — für die lesende Person sieht das wie
ein Fehler aus, obwohl die Verknüpfung stimmt (die Vorlage benennt mehrere
Straßen). Der Widerspruch steht in EINER Zeile, und keine Regel sagt, welche
Hälfte für den Ort zuständig ist.

## 3. Die Pull Requests

Reihenfolge ist Absicht: PR 1 legt die Datenbasis, auf die PR 3 aufsetzt.
PR 2 und PR 4 sind unabhängig und können parallel laufen.

### PR 1 — Der Stand der Akten (die Kernarbeit)

**Ziel:** Jede Antwort weiß, wie alt ihr jüngster Beleg ist und ob der Rat
seitdem überhaupt getagt hat.

**Neu in `council/qa.py`**, unter den anderen deterministischen Helfern
(neben `beleglage`, das dieselbe Rolle für die Belegmenge spielt):

```python
def aktenstand(store, candidates: list[dict], heute: date | None = None) -> dict:
    """Wie alt ist der jüngste Beleg — und hat der Rat seitdem getagt?

    Deterministisch aus den Kandidaten und dem Sitzungskalender. Leer bei
    Fehlern: Der Zeitbezug ist Zusatz, nie Blocker (wie `steckbriefe_fuer`).

    {"juengster": "2023-02-09", "monate": 31, "stufe": "alt",
     "letzte_sitzung": "2026-06-29", "naechste_sitzung": "2026-09-21",
     "pause": "Sommerpause"}   # pause aus council.sitzungspause, sonst None
    """
```

Stufen — die Schwellen sind an §2.2 gemessen, nicht geraten:

| Stufe | Bedingung | Begründung |
|---|---|---|
| `frisch` | jüngster Beleg < 6 Monate | innerhalb einer Sitzungsrunde |
| `ruhig` | 6–18 Monate | ein Verfahren darf ruhen, das ist normal |
| `alt` | > 18 Monate | hier kippt „ist geplant" in „war geplant" |

Dazu ein Block im Kontext, gebaut wie `_steckbrief_block`:

```python
def _aktenstand_block(stand: dict) -> str:
    """STAND DER AKTEN: … — eine Zeile, die dem Modell die Zeit gibt."""
```

Beispielausgabe für die Anlassfrage:

```
STAND DER AKTEN (deterministisch, nicht aus den Beschlüssen geschlossen):
Heute ist der 21. September 2026. Der jüngste Beschluss in diesem Kontext ist
vom 9. Februar 2023, also 31 Monate alt. Der Rat hat zuletzt am 29. Juni 2026
Beschlüsse gefasst, die nächste Sitzung ist am 21. September 2026.
```

**Prompt-Regel** in `kern/prompts.py::qa_antwort`, direkt nach der
ÄLTERE-STATION-Regel (die inhaltlich benachbart ist):

> Der STAND DER AKTEN oben ist gemessen, nicht geschätzt. Ist der jüngste
> Beschluss älter als anderthalb Jahre, sage das im ERSTEN Satz („Zuletzt
> entschieden hat der Rat dazu im Februar 2023") und schreibe nichts davon im
> Präsens oder Futur: Was 2018 beschlossen wurde, ist heute kein Plan mehr,
> sondern ein Beschluss von 2018 — ob er umgesetzt ist, steht nicht in den
> Akten, also behaupte es nicht in keine Richtung. Hat der Rat seit dem
> jüngsten Beleg gar nicht getagt, gehört auch das in den Satz.

**Dateien:** `council/qa.py` — Helfer + Block + neues Schlüsselwort `stand` in
`_answer_messages` (dem gemeinsamen Prompt-Bauer) und durchgereicht von
`answer_stream` und `answer_question`; `kern/prompts.py` (Regel + Platzhalter);
`web/backend/app/routers/council.py` (`stand = qa.aktenstand(store, candidates)`
neben `lage = qa.beleglage(candidates)`, ins `sources`-Ereignis und an beide
Antwort-Aufrufe); `council/sitzungspause.py` wird unverändert benutzt.

**Sichtbar machen:** `stand` gehört ins `sources`-Ereignis, damit über der
Antwort „Stand: Februar 2023" stehen kann — dieselbe Stelle, an der die
Beleglage schon hängt. Das ist eine Vertragsänderung: `api/openapi.json` neu
schneiden, `lib/vertrag.ts` generieren, `scripts/pruefe.py --nur vertrag,typen,strom`
grün bekommen, und `scripts/ios_vertrag.py --ausgeliefert` prüfen (neues
**optionales** Feld, die App im Store darf es nicht sehen müssen).
Frontend-Anzeige: `components/council-qa.tsx`, dezent neben der Beleglage —
**Bild an Tim vor dem Merge** (Regel aus der Wurzel-`CLAUDE.md`).

**Tests** (`tests/test_qa_zeitbezug.py`, neu):
- `aktenstand` mit Kandidaten von 2018 → `stufe == "alt"`, `monate` stimmt
  gegen ein festes `heute` (kein `date.today()` im Test).
- leere Kandidaten → `{}`, kein Block, keine Ausnahme.
- Store wirft → `{}` (der Zusatz-nie-Blocker-Pfad).
- Ende-zu-Ende über `/api/council/ask` wie
  `test_ask_ortssteckbrief_traegt_slug_und_verdraengt_die_dublette`: alte
  Kandidaten → das `sources`-Ereignis trägt `stand.stufe == "alt"`, und der an
  `answer_stream` übergebene Prompt enthält „STAND DER AKTEN".

**Fertig, wenn:** Die Anlassfrage auf dev mit einem ersten Satz antwortet, der
Februar 2023 nennt. Messbefehl in Anhang C, Vorher-Antwort in Anhang B.

**Kosten:** +1 Kontextzeile (~60 Tokens) je Frage. Bei
`COUNCIL_QA_MODEL=google/gemini-2.5-flash` unter 0,01 ¢.

---

### PR 2 — „zuletzt" + Ort hängt nicht mehr am Fragetyp

**Ziel:** Der deterministische Weg, den es gibt, wird auch erreicht.

**Änderung** in `web/backend/app/routers/council.py` (eine Zeile plus
Begründung):

```python
# Der Fragetyp kommt aus einem Sprachmodell, „zuletzt" aus einer Regex.
# „Was ist in Donnerschwee zuletzt beschlossen worden?" wurde am 21.09.2026
# als `history` eingeordnet — vertretbar, aber damit fiel die Frage aus dem
# deterministischen Weg heraus und wurde frei beantwortet. Ausgenommen
# bleiben die Typen, für die das Datum NICHT die Antwort ist.
latest_place = bool(ort and typ not in ("money", "person", "party", "session")
                    and (qa.latest_intent(q_suche) or qa.latest_intent(q)))
```

**Dazu** nennt `qa.latest_place_answer` den Ort beim Namen (neues Argument
`ort_name: str | None = None`): „Die jüngste Abstimmungsentscheidung **mit
Ortsbezug Donnerschwee** war am 1. Juni 2026: …". Ohne den Ort liest sich die
knappe Antwort wie eine allgemeine.

**Tests** (`tests/test_backend_api.py`): Frage mit „zuletzt" + Ort, Analyse
gemockt auf `typ="history"` → die Antwort ist die deterministische (erkennbar
daran, dass `qa_mod.answer_stream` **nicht** gerufen wurde) und enthält den
Ortsnamen. Zweiter Test: dieselbe Frage mit `typ="money"` → weiterhin der
freie Weg, denn „Was wurde zuletzt für X ausgegeben?" braucht die Beträge.

**Fertig, wenn:** beide Tests grün und die Frage aus §2.4 auf dev mit einem
Datum und dem Ortsnamen im ersten Satz antwortet.

**Kosten:** negativ — der deterministische Weg spart den Antwort-Call.

---

### PR 3 — Eine Zukunftsfrage ohne Zukunft sagt das

**Ziel:** „Was ist geplant?" beantwortet nicht mehr mit acht Jahre alten
Beschlüssen, ohne den Unterschied zu benennen.

**Gemessen:** Für die Anlassfrage liefern **beide** Zukunftswege leer —
`store.geplante_beratungen_fuer([…16 kvonr…]) == []` und
`store.kommende_beratungen(["Neu-Donnerschwee", "Donnerschwee", "Kaserne"]) == []`.
Der Ausblick-Block war also leer, und die Antwort hat trotzdem im Futur
erzählt.

**Änderung:** Wo der Router heute `planungen` füllt, kommt der Gegenfall dazu.
Deterministischer Auslöser statt Modell-Bedarf (`future_dates` kommt aus der
Analyse und ist damit dieselbe Münze wie in PR 2) — neue Regex in
`council/qa.py` neben `_LATEST_RE`:

```python
#: „geplant", „soll entstehen", „wird gebaut", „wie geht es weiter", „Zukunft".
#: NICHT „war geplant" — das ist eine Frage nach der Vergangenheit.
_ZUKUNFT_RE = re.compile(...)

def zukunftsfrage(question: str) -> bool: ...
```

Ist `zukunftsfrage(q_suche)` wahr und `planungen` leer, hängt der Router eine
Regel an den Antwort-Aufruf (denselben Weg wie `duenn`/`eng`, die schon so
durchgereicht werden):

> Diese Frage zielt auf die ZUKUNFT, und im Kontext steht keine einzige
> kommende Beratung. Sage das ausdrücklich im ersten Satz und schreibe die
> vorhandenen Beschlüsse in der Vergangenheit. Ein Beschluss ist kein Plan —
> er sagt, was der Rat entschieden hat, nicht, was als Nächstes passiert.

Mit PR 1 zusammen ergibt das den Satz, der heute fehlt: *„Eine anstehende
Beratung zu Neu-Donnerschwee gibt es nicht; zuletzt entschieden hat der Rat
dazu im Februar 2023."*

**Tests** (`tests/test_qa_zeitbezug.py`): `zukunftsfrage` gegen eine
Beispielliste (je 6 wahr/falsch, „war geplant" muss falsch sein); Ende-zu-Ende
mit leerem `planungen` → die Regel steht im Prompt, mit gefülltem → sie steht
nicht drin.

**Fertig, wenn:** die Anlassfrage auf dev nicht mehr „ist geplant" über den
B-Plan 58 schreibt. Gegenprobe mit einer echten Zukunftsfrage (Anhang C), bei
der `kommende_beratungen` etwas liefert — dort darf die Regel nicht auslösen.

**Kosten:** +~50 Tokens, nur im ausgelösten Fall.

---

### PR 4 — Der Ortsbezug gewinnt gegen den Nachbarort

**Ziel:** Kein fremder Ortsname mehr als Ort des Vorhabens, wenn die
Fundstelle einen anderen belegt.

**Änderung:** eine Ergänzung in `EXTRA_REGELN["place"]`
(`council/qa.py`) — die Regel gibt es, sie ist nur unvollständig:

> Steht im Beschlusstext ein ANDERER Ortsname als der gefragte, gilt für die
> Ortsangabe die „Fundstelle" hinter dem Ortsbezug, nicht der Text. Eine
> Vorlage kann mehrere Orte betreffen; schreibe dann, was sie für den
> GEFRAGTEN Ort besagt, und nenne den anderen Ort nicht als Ort des Vorhabens.

**Warum das reicht** und warum hier kein Code entsteht: Der Kontext trägt die
richtige Information bereits (`location_matches_for_decisions(district=ort["id"])`
liefert nur Orte innerhalb des gefragten Ortes, nach Konfidenz sortiert, und
`_build_context` schreibt sie als „Ortsbezug … Fundstelle …" an die Zeile). Es
fehlt allein die Anweisung, welche Hälfte bei einem Widerspruch zählt.

**Test** (`tests/test_qa_zeitbezug.py` oder `test_akkuratheit.py`, wo die
verwandten Regeln liegen): Kandidat mit widersprüchlicher Zusammenfassung und
`location_matches` → die Regel steht im Prompt. Ein Modelltest ist das nicht
und soll es nicht sein; die Wirkung wird von Hand gemessen (Anhang C, Frage 3).

**Fertig, wenn:** Die Neu-Donnerschwee-Antwort auf dev den Rosa-Lazarus-Satz
entweder weglässt oder ihn über die Fundstelle erzählt, nicht über den
Fliegerhorst.

**Kosten:** +~45 Tokens bei Ortsfragen.

## 4. Was dieser Plan NICHT baut

- **Keine Umsetzungs-Recherche.** „Ist der B-Plan 58 gebaut?" steht in keiner
  Ratsunterlage. Die Antwort darf sagen, was entschieden wurde und wann — nicht,
  was daraus geworden ist. Wer das will, braucht eine andere Quelle
  (Pressemitteilungen, Bauakten) und einen eigenen Plan.
- **Keine Änderung am Retrieval.** Die Kandidaten bleiben, wie sie sind; es
  geht um das, was die Antwort über sie sagt. Die Rangfolge hat am 20.09. schon
  drei PRs bekommen (#1408, #1415, #1417).
- **Kein zweiter Modellaufruf** für eine „Aktualitätsprüfung". Das Datum ist
  eine Subtraktion.
- **Keine Änderung an `council_locations`.** Maastrichter Straße gehört zu
  Donnerschwee — geprüft, das ist keine Fehlzuordnung.

## 5. Kosten und Risiko

| | |
|---|---|
| Zusätzliche LLM-Aufrufe | **keine** |
| Zusätzliche Prompt-Tokens | ~60 (PR 1) + ~50 (PR 3, nur ausgelöst) + ~45 (PR 4, nur Ortsfragen) |
| Gesparte Aufrufe | PR 2 spart den Antwort-Call bei „zuletzt"-Ortsfragen |
| Größtes Risiko | PR 1 macht Antworten **vorsichtiger**. Eine frische Frage darf davon nichts merken — deshalb die Stufe `frisch` ohne jede Regel, und deshalb die Gegenprobe in Anhang C mit einer Frage auf Material von 2026. |
| Zweitgrößtes Risiko | PR 2 schickt mehr Fragen auf den knappen deterministischen Weg. Die Ausnahmeliste (`money`, `person`, `party`, `session`) ist die Bremse; wer sie ändert, misst die vier Fragen aus Anhang C. |

## Anhang A — Die Dateien, in der Reihenfolge, in der man sie anfasst

| PR | Dateien |
|---|---|
| 1 | `council/qa.py` → `kern/prompts.py` → `web/backend/app/routers/council.py` → `api/openapi.json` (neu schneiden) → `web/frontend/lib/vertrag.ts` (generiert) → `web/frontend/components/council-qa.tsx` → `tests/test_qa_zeitbezug.py` |
| 2 | `web/backend/app/routers/council.py` → `council/qa.py` (`latest_place_answer`) → `tests/test_backend_api.py` |
| 3 | `council/qa.py` (`_ZUKUNFT_RE`, `zukunftsfrage`) → `web/backend/app/routers/council.py` → `tests/test_qa_zeitbezug.py` |
| 4 | `council/qa.py` (`EXTRA_REGELN["place"]`) → `tests/test_qa_zeitbezug.py` |

Je PR ein `changelog.d/<slug>.md` (`kategorie: geaendert` für 1–3, `behoben`
für 4). PR 1 und 2 gehen gegen `dev`; erst wenn beide auf dev gemessen sind,
gehört der Stapel in einen Release nach `main`.

## Anhang B — Die Antworten von heute (Vorher-Stand, Prod 21.09.2026)

**Frage 1: „Was ist für Neu-Donnerschwee geplant?"** (7,7 s · 25 Quellen · 14
zitiert) — Kurzfassung im Präsens über den B-Plan 58 (Satzungsbeschluss
22.10.2018), Belege bis Februar 2023, kein Wort zum Alter. Alle Fußnoten
geprüft: keine erfunden, „Urban Gardening" [16276] und die Kranbergstraße
[15176] haben echte Ortsbelege.

**Frage 2: „Was ist in Donnerschwee zuletzt beschlossen worden?"** (5,8 s · 21
Quellen · 12 zitiert) — führt mit dem Stadionneubau Maastrichter Straße
(01.06.2026, korrekt in Donnerschwee), nennt Donnerschwee in der Kurzfassung
nicht. Fünf der 21 Quellen sind Stadion-Beschlüsse.

**Frage 3: der Rosa-Lazarus-Satz** — s. §2.5.

## Anhang C — Die Messbefehle

Alle gegen Prod (`ssh tk-nwz`, Login-Shell ist **zsh**), Skripte über eine
Heredoc-Datei statt `python -c` (Anführungszeichen überleben den SSH-Aufruf
nicht):

```bash
# Die Frage stellen, wie eine angemeldete Person sie stellt (Token wie die
# Rauchprobe, fünf Minuten gültig, nichts gespeichert):
ssh tk-nwz 'cd ~/app && .venv/bin/python scripts/frage_probe.py \
  "Was ist für Neu-Donnerschwee geplant?"'

# Vier Fragen für die Gegenproben dieses Plans:
#   1 alt      „Was ist für Neu-Donnerschwee geplant?"          → PR 1, PR 3
#   2 zuletzt  „Was ist in Donnerschwee zuletzt beschlossen worden?" → PR 2
#   3 nachbar  „Was ist in Neu-Donnerschwee zur Erinnerungskultur beschlossen worden?" → PR 4
#   4 frisch   „Was hat der Rat zum Stadion beschlossen?"       → darf sich NICHT ändern
ssh tk-nwz 'cd ~/app && .venv/bin/python scripts/frage_probe.py --datei /tmp/fragen.txt'
```

Jüngster Beschluss je Katalogort (die Tabelle aus §2.2):

```python
# /tmp/orte.py auf tk-nwz, dann: cd ~/app && .venv/bin/python /tmp/orte.py
import sys; sys.path.insert(0, "/home/tim/app")
from council.store import CouncilStore
from council import places
s = CouncilStore("/home/tim/app/data/council.sqlite")
for p in places.all_places():
    ids = s.decision_ids_for_place(p.id, limit=None)
    if not ids:
        continue
    ph = ",".join("?" * len(ids))
    juengster = s._conn.execute(
        "select max(cs.session_date) m from council_decisions d "
        "join council_sessions cs on cs.ksinr=d.ksinr where d.id in (%s)" % ph, ids).fetchone()["m"]
    print(f"{p.name[:32]:32s} | {len(ids):5d} | {juengster}")
```

Sitzungslücke (§2.3) und die beiden Zukunftswege (§3, PR 3) stehen im selben
Muster; `store.geplante_beratungen_fuer(kvonrs)` und
`store.kommende_beratungen(begriffe)` je einmal aufrufen und die leere Liste
zeigen.

**Falle, die eine halbe Stunde kostet:** Ein Deploy kann die
Wartungsbarriere (`data/.release-maintenance`) gesetzt haben — dann wirft
**jeder** `CouncilStore(...)` sofort `RuntimeError: Release-Wartung aktiv`,
und das sieht aus wie ein kaputtes Skript. `ls -l ~/app/data/.release-maintenance`
sagt es in einer Zeile; abwarten, nicht löschen.
