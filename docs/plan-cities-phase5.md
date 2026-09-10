# Umsetzungsplan Phase 5: das „Warum" aus den Protokollen — und welche Stadt als Nächstes

Stand: 10.09.2026, abends. Dieser Plan folgt auf
[`plan-cities-phase4.md`](plan-cities-phase4.md) (PR 23–30, alle gemergt)
und ist wie seine Vorgänger geschrieben: **ohne das Gespräch dahinter
ausführbar**. Jeder Abschnitt ist ein Pull Request, nennt Dateien,
Signaturen, Tests, Kosten und woran man erkennt, dass er fertig ist. Wo etwas
gemessen ist, steht die Zahl und in Anhang C der Befehl, der sie liefert.

Wer das umsetzt, liest **vorher** vollständig: die Wurzel-`CLAUDE.md`,
`council/CLAUDE.md`, **`council/cities/CLAUDE.md`** (das Rezept für eine
neue Stadt und die Regel „ein Adapter je Ratsinformationssystem"),
`scripts/CLAUDE.md`, `tests/CLAUDE.md`, §0 der vier Vorgängerpläne (Regeln
1–20 gelten unverändert) und die Docstrings von `council/cities/adapters/
_common.py`, `pipeline.py`, `clusters.py` und `store.py`. Dazu die
Oldenburger Protokoll-Verarbeitung in `council/` (`check_protocols.py` und
was sie ruft) — Oldenburg hat das, was dieser Plan für die anderen Städte
baut, längst.

## 0. Die Richtung, die Tim vorgegeben hat

Am 10.09.2026, nach Phase 4:

> Ratsmitglieder erstmal ausklammern, die können wir noch nicht einbinden.
> Bei vielen anderen Städten würde ich erstmal keine Notifications bauen
> wollen. Es wäre super, wenn wir an die Beratungen und Protokolle
> herankommen könnten — gerade das *Warum* es irgendwo anders klappt oder
> nicht, ist für die Diskussion in Oldenburg wichtig. Bevor wir andere
> Städte hinzufügen, hätte ich gerne ein Ranking der Städte, die es sich am
> meisten lohnt hinzuzufügen: Vergleichbarkeit zu Oldenburg, Qualität und
> Menge der Daten, oder was dir sonst noch einfällt.

Daraus folgen drei Regeln, die zu 1–20 dazukommen:

21. **Kein PR dieses Plans baut Benachrichtigungen oder etwas, das
    Ratsmitglieder braucht.** Der Rückkanal bleibt, wie er ist; wer ihn
    liest, ist Phase 6.
22. **Das „Warum" kommt aus Dokumenten, nicht aus dem Modell.** Ein
    Annotator darf zusammenfassen, was in einer Niederschrift steht; er
    darf nicht erraten, warum ein Rat entschieden hat. Ohne Abschnitt im
    Protokoll gibt es kein „Warum" — dann steht das so da.
23. **Eine neue Stadt kommt erst, wenn das Ranking in §3 sie nennt und die
    Probe aus `council/cities/CLAUDE.md` bestanden ist.** Kein Adapter
    ohne Fixture aus echten Rohobjekten.

## 1. Zielbild

Heute sagt die Karte: *Vier Räte wollten die Verpackungssteuer, einer stellte
die Prüfung ein, Oldenburg hat sie nicht.* Sie sagt nicht, **warum** Magdeburg
die Prüfung einstellte, und nicht, was in Münster in der Debatte stand. Das
„Warum" ist das, was eine Ratsfraktion in Oldenburg für ihre eigene Sitzung
braucht — und gestern hieß es noch, die Schnittstellen gäben es nicht her.

Das stimmte nur für den Text **je Tagesordnungspunkt** (`resolutionText`:
null bei den fünf fremden Städten; Oldenburg hat ihn aus `council.sqlite`).
Je **Sitzung** liegen PDFs vor — und die Messung vom 10.09.2026 (§2) sagt,
dass sie brauchbar sind.

Am Ende dieses Plans:

```
  ┌────────────────────────────────┐ ┌────────────────────────────────┐
  │ A  Zu jeder Beratung in einer  │ │ B  Jede Idee auf der Karte     │
  │    fremden Stadt liegt der     │ │    trägt je Stadt einen        │
  │    ABSCHNITT der Niederschrift │ │    Absatz: was diskutiert,     │
  │    vor — wo es sie gibt        │ │    wie abgestimmt, warum       │
  │    (PR 31, 32)                 │ │    (PR 33) — aus dem Text,     │
  │                                │ │    nicht aus dem Modell        │
  └────────────────────────────────┘ └────────────────────────────────┘
  ┌────────────────────────────────┐ ┌────────────────────────────────┐
  │ C  Oldenburgs eigene Seite     │ │ D  Bonn ist die siebte Stadt — │
  │    liefert denselben Absatz,   │ │    die einzige mit Nieder-     │
  │    damit man vergleichen kann  │ │    schriften unter den         │
  │    (PR 34)                     │ │    Kandidaten (PR 35)          │
  └────────────────────────────────┘ └────────────────────────────────┘
```

## 2. Was gemessen ist und den Plan trägt

Alle Zahlen vom 10.09.2026, Befehle in Anhang C.

### 2.1 Die Protokolle, die es gibt

Je Stadt die Sitzungen in den Rohdaten (`data/cities-raw/<stadt>.sqlite`)
und welche Datei-Felder sie tragen:

| Stadt | Sitzungen | `resultsProtocol` | `verbatimProtocol` | Probe: drei Dateien |
|---|---:|---:|---:|---|
| Münster | 990 | **444 (45 %)** | — | 0,2 MB, 4–9 Seiten, **Text**, Marker „Punkt N der Tagesordnung", 8–12 je Dokument |
| Magdeburg | 1.936 | 606 (31 %) | — | **alle 404** — die Datei-URLs der Schnittstelle antworten nicht (bekannt aus der Registry) |
| Braunschweig | 868 | — | 218 (25 %) | 0,1–0,2 MB, 5–22 S., Text, gegliedert **numerisch** („1 Titel", „2.1 …"), kein „TOP" |
| Osnabrück | 637 | 8 | 273 (43 %) | 0,2–0,3 MB, 24–38 S., Text, numerisch; Kopf „P R O T O K O L L (öffentlicher Teil)" |
| Potsdam | 2.730 | — | 663 (24 %) | 0,1–0,2 MB, 4–13 S., Text, „Niederschrift", numerisch |
| Oldenburg | 869 | — | — | keine PDFs im Städte-Speicher, dafür Beschlusstext je Punkt (s. u.); die Niederschriften selbst hat `council.sqlite` (`check_protocols.py`) |

Was das heißt: **rund 1.600 lesbare Niederschriften in vier Städten, zusammen
etwa 0,2 GB.** Keine Scans (durchweg > 200 Zeichen je Seite). Was ALLRIS
`verbatimProtocol` nennt, ist keine Wortprotokoll-Abschrift, sondern die
Niederschrift — dieselbe Sache wie Münsters `resultsProtocol`, nur unter
einem anderen Feldnamen.

**Der Speicher kennt sie schon.** `model.FileRole.PROTOCOL` gibt es,
`adapters/_common.py::files_from` liest beide Felder, und in `files` liegen
**2.212 Zeilen mit `role='protocol'`** an ihren Sitzungen (`meeting_id`
gesetzt, `paper_id` leer) — **alle ohne Bytes**, weil
`pipeline.FETCH_ROLES = ("main",)` nur die Vorlage holt. Im Fenster der
letzten 24 Monate (`meetings.start >= 2024-09-01`):

| Stadt | Protokoll-Zeilen | davon ≤ 24 Monate |
|---|---:|---:|
| Münster | 444 | 318 |
| Braunschweig | 218 | 166 |
| Osnabrück | 281 | 106 |
| Potsdam | 663 | 356 |
| Magdeburg | 606 | 450 — **tot (404)** |

Also **946 Dateien**, die PR 31 holen muss. Kein Adapter-Umbau.

`agendaItem.resolutionText`: bei den fünf fremden Städten **null** —
`agenda_items.resolution_text` ist dort 0 von 97.570. **Oldenburg hat ihn**:
8.021 von 8.161 Punkten, weil `adapters/oldenburg.py` den Beschlusstext aus
`council_decisions.official_text` als `resolutionText` liefert; 481 davon seit
09/2024 mit mehr als 200 Zeichen. Für die fremden Städte muss der Text je
Punkt aus der Sitzungs-PDF **geschnitten** werden; das ist der Kern von PR 32
und je Dialekt eine eigene Regel. Für Oldenburg ist er da.

### 2.2 Die Städte, die warten

Gegen die Schnittstellen gemessen (lesend, je Stadt ein Aufruf auf `system`,
`body`, `paper?created_since=2024-01-01`, die ersten acht `meeting`):

| Stadt | Einw. | Land | RIS | OParl | Vorlagen seit 2024 | Beratung an Vorlage | Protokoll an Sitzung | Antwortzeit | Lizenz |
|---|---:|---|---|---|---:|---|---|---:|---|
| **Bonn** | 330 k | NW | ALLRIS 4 | 1.1 | Abfrage mit `created_since` bricht — Dialekt prüfen | ? | **6 von 8** | 2 s | Open Data (opendata.bonn.de) |
| Darmstadt | 165 k | HE | RUBIN | 1.0 | 20.596 (vermutlich Gesamtbestand) | 5/5 | 0/8 | 9 s | — |
| Leipzig | 620 k | SN | ALLRIS 4 | 1.1 | 9.268 | 4/5 | 2/8 | 4 s | CC BY 4.0 |
| Freiburg | 235 k | BW | RUBIN | 1.0 | 13.959 | 5/5 | 0/8 | 11 s | — |
| Köln | 1.100 k | NW | SessionNet | 1.1 | ≥ 25 je Seite | 5/5 | 0/8 | 2 s | — |
| Dresden | 560 k | SN | SessionNet | 1.1 | ≥ 10 je Seite | 5/5 | 0/8 | 8 s | DL-DE-Zero |
| Wuppertal | 360 k | NW | SessionNet | 1.1 | ≥ 100 je Seite | 5/5 | 0/8 | 12 s | — |
| Düsseldorf | 640 k | NW | SessionNet | 1.1 | ≥ 200 je Seite | 5/5 | 0/8 | 13 s | „Open" |

Zum Vergleich die sechs aktiven: Oldenburg 172 k (NI), Osnabrück 165 k (NI),
Braunschweig 250 k (NI), Münster 320 k (NW), Potsdam 185 k (BB),
Magdeburg 240 k (ST).

### 2.3 Niedersachsen: es gibt nichts zu holen

Tims erstes Kriterium ist Vergleichbarkeit — und die beste Vergleichbarkeit
wäre dieselbe Rechtslage, also Niedersachsen (NKomVG, Straßenausbaubeiträge,
Verpackungssteuer, alles im selben Landesrecht). Gemessen:

- Die offizielle Endpunktliste (`dev.oparl.org/api/endpoints`) kennt
  **127 Systeme**. Aus Niedersachsen: **nur Braunschweig.** Osnabrück steht
  gar nicht drin, obwohl es OParl spricht — die Liste ist für die
  `sitzung-online`- und `ratsinfomanagement`-Familien unvollständig.
- Deshalb 26 niedersächsische Städte (Hannover, Göttingen, Wolfsburg,
  Hildesheim, Salzgitter, Lüneburg, Celle, Emden, Delmenhorst,
  Wilhelmshaven, Cuxhaven, Lingen, Garbsen, Langenhagen, Nordhorn, Peine,
  Stade, Goslar, Hameln, Wolfenbüttel, Melle, Aurich, Verden, Nienburg,
  Gifhorn, Uelzen) gegen acht Adressmuster der vier Hersteller geprüft
  (`<stadt>.sitzung-online.de`, `ratsinfo.<stadt>.de`,
  `<stadt>.ratsinfomanagement.net`, SessionNet `bi/oparl/1.0/system.asp`,
  …): **0 Treffer.**

Vergleichbarkeit über das Landesrecht ist über OParl also **nicht** zu
haben. Was bleibt, ist Vergleichbarkeit über Größe und Typ (kreisfreie
Großstadt, Oberzentrum, Universitätsstadt) — und die eine Option in Anhang
B, die keinen OParl-Endpunkt braucht.

### 2.4 Was sonst noch gemessen wurde

- **Ein anderes Modell** (`deepseek/deepseek-v4.1-flash`, gleicher Tag,
  gleiche Handfälle): `fit`-Status 70 % gegen 65 % — innerhalb der Streuung
  eines Einzellaufs —, dafür **dreifache Kosten** ($2,21 gegen $0,74 je 1.000
  Urteile), doppelte Dauer, und eine neue Fehlerart: Das Modell denkt lange,
  und ist das Budget aufgebraucht, kommt **abgeschnittenes JSON mit Status
  200**. Bei `stance` schlicht schlechter (76 % gegen 87 %, vier harte
  Ausfälle). **Bleibt bei `v4-flash`.** Kein PR.
- **Die drei Restfehler** aus Phase 4 sind in PR #1262 — Mehrheit je Idee
  (14 Gruppen), Prüfaufträge (87 → 93 %), und die verkettete Gruppe wurde
  nach Messung **nicht** gefixt: strengere Verknüpfung zerlegt sie (72 → 6),
  aber genauso Wärmeplanung (33 → 13), Verpackungssteuer (25 → 14),
  Parkgebühren (50 → 8). Steht im Docstring von `build_clusters`.

## 3. Das Ranking

Fünf Kriterien, in der Reihenfolge, in der sie für Tims Frage zählen:

1. **Niederschriften erreichbar** — ohne sie gibt es kein „Warum", und das
   „Warum" ist der Auftrag dieser Phase.
2. **Beratungsfolge an der Vorlage** — ohne sie kein Ergebnis (Phase 4,
   PR 27: 5.224 Vorlagen hingen daran).
3. **Vergleichbarkeit** — Größe 150–350 k, kreisfrei, Oberzentrum. Das
   Landesrecht scheidet aus (§2.3).
4. **Adapter vorhanden** — ALLRIS 4 und SessionNet sind gebaut und an je
   zwei bis drei Städten bewährt; RUBIN (`adapters/rubin.py`, 90 Zeilen)
   hat noch nie eine echte Stadt gesehen.
5. **Lizenz und Tempo** — eine genannte Lizenz spart die Frage; 12 Sekunden
   je Aufruf machen aus einer Ernte einen Tag.

| Rang | Stadt | Warum | Was dagegen spricht |
|---|---|---|---|
| **1** | **Bonn** | Als **einziger Kandidat Niederschriften an 6 von 8 Sitzungen** (wie Münster). ALLRIS 4 — Adapter vorhanden, drei Städte bewährt. 330 k, kreisfrei, Bundesstadt. Open-Data-Lizenz. 2 s Antwortzeit. | Die Vorlagen-Abfrage mit `created_since` brach in der Probe — ein Dialekt-Detail, das die Probe aus `council/cities/CLAUDE.md` finden muss, bevor irgendetwas geerntet wird. |
| **2** | **Darmstadt** | **165 k — die Oldenburg ähnlichste Stadt** unter allen Kandidaten (Wissenschaftsstadt, kreisfrei). Beratung an 5 von 5 Vorlagen. | RUBIN, OParl 1.0: erster Ernstfall für `rubin.py`. Keine Niederschriften an den Sitzungen. Keine Lizenz genannt. 9 s. |
| 3 | Leipzig | CC BY 4.0, 9.268 Vorlagen seit 2024, ALLRIS 4, Protokolle an 2 von 8. | 620 k — dreieinhalbmal Oldenburg, Landeshauptstadt; Ideen skalieren nicht ohne Weiteres. |
| 4 | Freiburg | 235 k, Universitätsstadt, Beratung 5/5, 13.959 Vorlagen. | RUBIN (s. Darmstadt), keine Protokolle, keine Lizenz, 11 s. Erst nach Darmstadt, wenn `rubin.py` steht. |
| 5 | Köln | SessionNet (Adapter da), Beratung 5/5, 2 s. | 1,1 Mio. Einwohner. Keine Protokolle, keine Lizenz. |
| 6–8 | Dresden, Wuppertal, Düsseldorf | SessionNet, Beratung 5/5. | Keine Protokolle, 8–13 s je Aufruf, Größe 360–640 k. Dresden immerhin DL-DE-Zero. |

**Empfehlung: Bonn, dann Darmstadt.** Bonn, weil es das Einzige ist, was
diese Phase braucht und die anderen nicht haben. Darmstadt, weil es die
Frage „was macht eine Stadt wie unsere?" beantwortet — und weil es
`rubin.py` zum ersten Mal an einer echten Stadt prüft, was Freiburg dann
billig macht.

## PR 31 — Die Niederschriften holen

**Warum.** 946 Dateien im Fenster, 0,2 GB, lesbar, **schon modelliert** — der
Speicher hat sie bis heute nur nicht geholt, weil `FETCH_ROLES` die Vorlage
meint und sonst nichts. Das ist ein kleiner PR mit einer großen Wirkung.

**Was sich ändert.**

1. `council/cities/pipeline.py`: `FETCH_ROLES` bekommt `"protocol"` dazu —
   **aber nur für Sitzungen ab einem Datum** (Vorgabe: 24 Monate, der Zeitraum
   der Ideen auf der Karte). `store.files_without_bytes(body, roles, limit)`
   braucht dafür ein `since`, das über `meetings.start` filtert; für `main`
   bleibt das Verhalten unverändert. `--max-files` gilt weiter.
2. Magdeburg wird übersprungen, sobald die ersten drei Protokoll-Abrufe 404
   liefern — die Registry-Notiz sagt es, der Code soll es messen, nicht
   wissen. `client.get_file` gibt bei 404 schon `None` zurück
   (`test_get_file_ist_bei_404_kein_laufabbruch`); neu ist nur der Abbruch
   nach drei Nieten je Lauf und Stadt.
3. `pipeline.extract` extrahiert sie wie Vorlagen (`council/cities/text.py`,
   pypdf) nach `texts` — das tut sie vermutlich bereits, weil sie über
   `files` mit Bytes läuft; prüfen, nicht annehmen. Eine Kennzahl
   `protocols_with_text` in `stats()` und im Bericht von
   `cities_backfill.py`.

**Test.** `test_cities_pipeline.py`: `files_without_bytes` mit `since` lässt
eine alte Sitzung liegen und holt eine junge; drei 404 in Folge beenden die
Protokoll-Abrufe einer Stadt, die Vorlagen-Abrufe nicht.

**Messung.** Je Stadt: Protokoll-Zeilen im Fenster, davon mit Bytes, davon mit
Text. Fertig, wenn Münster, Braunschweig, Osnabrück und Potsdam zusammen
≥ 850 von 946 Protokollen mit Text tragen und Magdeburg nach drei Abrufen
schweigt.

**Kosten.** ~950 Abrufe (gedrosselt ~20 Minuten) und ~10 Minuten CPU. Kein
Modell.

## PR 32 — Die Niederschriften aufschneiden

**Warum.** Das „Warum" steht in einem Abschnitt von vier bis vierzig Seiten,
und der Abschnitt gehört zu **einem** Tagesordnungspunkt. Ein Modell, das
die ganze Sitzung liest, um einen Punkt zu finden, ist teuer und rät.
Schneiden ist Regelarbeit, je Dialekt eine eigene — und die Regel ist
messbar: Findet sie den Abschnitt zu dem Punkt, den ein Mensch findet?

**Was sich ändert.** Neues Modul `council/cities/protocol.py`:

```python
def split_protocol(text: str, dialect: str) -> list[Section]
    # Section(number: str, title: str, text: str, start: int, end: int)

def attach_sections(main: CitiesStore, meeting_id: str, sections) -> int
    # Abschnitt → agenda_item über NUMMER, sonst über normalisierten Titel
    # (dieselbe `normalize_title` wie `link_by_title`); Kennzahl je Sitzung
```

Zwei Regeln, gemessen an §2.1:

- **SessionNet (Münster):** `^Punkt (\d+(\.\d+)?) der Tagesordnung` beginnt
  einen Abschnitt; er endet am nächsten. Die Probe fand 8–12 Marker je
  Dokument bei 4–9 Seiten — das passt zu einer Tagesordnung.
- **ALLRIS 4 (Braunschweig, Osnabrück, Potsdam):** Gliederung numerisch am
  Zeilenanfang — `^(\d+(\.\d+)*)\s+[A-ZÄÖÜ]` — mit Titel dahinter. Die
  Probe fand 44 Treffer in sechs Seiten Braunschweig, 3–4 in Osnabrück und
  Potsdam (dort beginnt die Tagesordnung später; die ersten Seiten sind
  Anwesenheit). Der Abgleich läuft über die **Nummer** gegen
  `agenda_items.number` und, wo die fehlt, über den Titel — nur eindeutig,
  nur innerhalb DERSELBEN Sitzung (das ist die Lehre aus Phase 4, PR 27:
  Mehrdeutig ist, was mehrere Papiere derselben Stadt tragen; innerhalb
  einer Sitzung ist ein Titel fast nie mehrdeutig).

Speicher: Tabelle `protocol_sections (meeting_id, agenda_item_id, number,
title, text, source_hash)`, Schema 6 **und** Migration — `council/CLAUDE.md`,
zwei Stellen.

**Golden Set.** `eval/cases_cities_sections.json`: **20 Sitzungen** (fünf je
Stadt), je Sitzung von Hand: welcher Tagesordnungspunkt welchen Abschnitt
hat (Nummer, erste Zeile, letzte Zeile). Prüfstand
`eval/run_cities_sections.py`, ohne Modell: Anteil der Punkte mit richtig
begrenztem Abschnitt. **Schranke erst nach der ersten Messung** (Regel 15).
Das Golden Set legt an, wer den PR baut — es ist eine Tatsachenfrage („wo
beginnt Punkt 7?"), keine Wertung.

**Test.** Je Dialekt ein Fixture aus einer echten, gekürzten Niederschrift
(`tests/fixtures/cities/<stadt>_protokoll.txt`, **ohne Personennamen** —
Ratsmitglieder dürfen genannt werden, private Personen nicht; im Zweifel
schwärzen). Der Test prüft Anzahl und Grenzen der Abschnitte.

**Messung.** Anteil der Tagesordnungspunkte mit Protokoll, die einen
Abschnitt bekommen — je Stadt. Fertig, wenn der Prüfstand steht und der
Anteil je Stadt im PR-Text steht (Erwartung: Münster > 80 %, ALLRIS 50–70 %).

**Kosten.** Kein Modell.

## PR 33 — Das „Warum"

**Warum.** Das ist der Auftrag. Und er hat eine Grenze, die vor dem Bau
feststehen muss: Ein Modell darf **zusammenfassen**, was im Abschnitt steht.
Es darf nicht erraten, warum ein Rat entschieden hat (Regel 22). Ohne
Abschnitt gibt es kein „Warum", und dann sagt die Karte das.

**Was sich ändert.** Neuer Annotator `reason` (Fassung 1, `applies_to=
("agenda_item",)`), Nutzlast:

```python
class OutcomeReason(BaseModel):
    discussed: str = Field(max_length=400)   # worum die Debatte ging
    decided: str = Field(max_length=200)     # was beschlossen wurde, wörtlich nah
    vote: str | None                         # „einstimmig", „mehrheitlich", „12:8", …
    why: str = Field(max_length=300)         # die Begründung, WIE SIE IM TEXT STEHT
    grounded: bool                           # steht die Begründung wirklich da?
```

`grounded` ist die Sicherung gegen Regel 22: Das Modell muss sagen, ob es
eine Begründung **gefunden** hat oder nur das Ergebnis. Der Prüfstand zählt
`grounded=True` ohne Begründung im Text als schweren Fehler — dieselbe Klasse
wie „erfundene Belege" bei `fit`.

Kandidaten: nur Tagesordnungspunkte zu Vorlagen, die in einer Gruppe mit
≥ 2 Städten liegen (`idea_group_status.peers >= 1`) — gemessen sind das
rund 260 Vorlagen mit Ergebnis; mit Abschnitt vielleicht 150. Batch 1
(ein Abschnitt je Aufruf, wie `fit`), `input_chars` 6.000, `max_tokens`
4.000 (der Wächter in `test_cities_annotators.py` verlangt ≥ 4.000 — ein
knappes Budget liefert keine Fehlermeldung, sondern abgeschnittenes JSON).

Die Karte (Web **und** iOS, featuregleich, Bild vor dem Merge): unter jeder
fremden Vorlage mit Abschnitt ein aufklappbarer Absatz „In <Stadt>:
<decided> — <why>", mit `vote` als Etikett und dem Hinweis „aus der
Niederschrift vom <Datum>". Ohne Abschnitt: nichts. Kein Platzhalter.

**Golden Set.** `eval/cases_cities_reason.json`: **40 Abschnitte**, von
Hand: `decided`, `vote`, `why` (wörtlich nah), und ob eine Begründung
überhaupt da steht. Prüfstand `eval/run_cities_reason.py`; Schranken: `vote`
≥ 90 % (steht fast immer wörtlich da), `grounded` falsch-positiv **0**,
`why` nach Handdurchsicht ≥ 80 % „trifft die Begründung".

**Test.** Payload-Test; `test_alte_werte`; Router-Test für den Absatz;
`swift test`.

**Messung.** Anteil der Listeneinträge (§1 Phase 4: 69) mit einem „Warum".
Fertig, wenn der Prüfstand besteht und die Zahl im PR-Text steht.

**Kosten.** ~150–300 Aufrufe mit 6.000 Zeichen → **< $1**.

## PR 34 — Oldenburgs Seite

**Warum.** Die Karte vergleicht. Steht bei Münster „mit 24:18 beschlossen,
weil …" und bei Oldenburg nur „vertagt", ist der Vergleich schief.

**Was schon da ist — und was nicht.** Oldenburgs Beschlusstext liegt je
Tagesordnungspunkt in `agenda_items.resolution_text` (8.021 Punkte, aus
`council_decisions.official_text`; §2.1). Es braucht also **kein**
Aufschneiden und keinen Adapter-Umbau. Aber es ist der *Beschluss*text, nicht
die Debatte: „Der Rat beschließt …" ohne das Warum. Die Debatte hat
`council.sqlite` an anderer Stelle — die Wortbeiträge und das, was
`check_protocols.py` je Punkt aus der Niederschrift zieht. Vor dem Bau
**messen**, welche Spalte das Warum trägt (Kandidaten: `council_decisions`
und die Tabellen, die `council/protocols.py` schreibt), und wie oft sie seit
09/2024 gefüllt ist.

**Was sich ändert.** `reason` (PR 33) nimmt als Eingabe **entweder** einen
Abschnitt aus `protocol_sections` **oder** `resolution_text` — in dieser
Reihenfolge, nie beides gemischt; der Prompt sagt, was er bekommt. Für
Oldenburg liefert `adapters/oldenburg.py` zusätzlich den Debattentext je Punkt
als `protocol_sections`-Zeile, wenn die Messung eine Quelle findet; sonst
läuft `reason` über `resolution_text` und `grounded` bleibt bei den meisten
Punkten `False` — das ist dann das ehrliche Ergebnis, kein Fehler.

Zehn Oldenburger Fälle **kommen ins Golden Set von PR 33 dazu**, es wird nicht
ersetzt (Regel 16). Die Gegenrichtung („wie ging es anderswo aus?",
`cities_gegenrichtung.py`) zeigt damit auf beiden Seiten denselben Absatz.

**Test.** Adapter-Test gegen eine `council.sqlite`-Fixture mit einem Punkt,
der Beschluss- und Debattentext trägt.

**Messung.** Anteil der Oldenburger Punkte seit 09/2024 mit `grounded=True`.
Fertig, wenn die Zahl im PR-Text steht und neben der der besten fremden Stadt
nicht schlechter aussieht — sonst fehlt die Debatte, und die Quelle ist
vollständiger als jede OParl-Schnittstelle.

**Kosten.** ~500 Aufrufe → < $1.

## PR 35 — Bonn

**Warum.** §3. Und weil Bonn Niederschriften an sechs von acht Sitzungen hat
— PR 31–33 bekommen damit eine dritte Quelle neben Münster und den drei
ALLRIS-Städten.

**Was sich ändert.** Das Rezept aus `council/cities/CLAUDE.md`, Schritt für
Schritt, und **kein Schritt ausgelassen**:

1. Registry-Eintrag steht (`active=False`).
2. Ernte mit kurzem Fenster: `--run --body bonn --since 2025-01-01 --stage
   fetch --stage normalize`. **Vorher klären, warum `paper?created_since=…`
   in der Probe brach** — vermutlich ein anderer Parametername oder ein
   Datumsformat; `adapters/allris4.py` hat für Osnabrück und Braunschweig
   schon Sonderfälle, der Dialekt gehört dorthin, nie in eine
   `if body_id == "bonn"`-Bedingung.
3. `--pruefen` — die Plausibilitätsbänder und das unbekannte
   Ergebnis-Vokabular.
4. Vokabular in `model._OUTCOME_RULES` nachziehen, was ein Ergebnis ist.
5. Fixture `tests/fixtures/cities/bonn_papers.json` aus echten Rohobjekten,
   gekürzt, ohne Personen; Eintrag in `STAEDTE` in
   `tests/test_cities_adapters.py`.
6. Erst dann `active=True`, volle Historie, und die Stufen in der
   Reihenfolge, die `cities_backfill.py --stage fit` seit PR 25 erzwingt.

**Messung.** `cities_backfill.py --pruefen` ohne Befund; Anteil Vorlagen mit
Ergebnis ≥ 60 % (Osnabrück nach PR 27: 80 %, Braunschweig 47 %); Anteil
Sitzungen mit Protokoll-Text. Fertig, wenn Bonn in `cities_bilanz.py`
auftaucht und die Karte Ideen aus Bonn zeigt.

**Kosten.** classify ~$3 (rund 10.000 Vorlagen à $0,31/1.000), `fit` über
die übertragbaren ~$5, Index Stunden CPU. Zusammen **< $10**.

## PR 36 — Darmstadt, und damit `rubin.py`

**Warum.** Die Oldenburg ähnlichste Stadt, und der erste Ernstfall für den
vierten Adapter. Freiburg wird danach ein Registry-Eintrag.

**Was sich ändert.** Dasselbe Rezept wie PR 35. Dazu, weil OParl 1.0:
`rubin.py` gegen die Abweichungen von 1.1 prüfen (die Registry-Notiz zu
Freiburg sagt: „Volltext liegt im Dateiobjekt"). Erwartung aus der Probe:
Beratung an 5 von 5 Vorlagen, keine Protokolle — PR 31 liefert für Darmstadt
also nichts, und das ist in Ordnung.

**Messung.** Wie PR 35. Fertig, wenn `rubin.py` ein Fixture aus echten
Darmstädter Rohobjekten trägt und `--pruefen` schweigt.

**Kosten.** < $10.

## Anhang A — Reihenfolge, Aufwand, Kosten

| PR | Was | hängt an | Aufwand | Modellkosten |
|---|---|---|---|---:|
| 31 | Niederschriften holen | — | ½ Tag + Laufzeit | 0 |
| 32 | Niederschriften aufschneiden + Prüfstand | 31 | 2 Tage | 0 |
| 33 | Das „Warum" + Karte | 32 | 2 Tage | < $1 |
| 34 | Oldenburgs Seite | 33 | 1 Tag | < $1 |
| 35 | Bonn | — (parallel zu 31–34) | 1 Tag + Laufzeit | < $10 |
| 36 | Darmstadt / `rubin.py` | 35 | 1–2 Tage | < $10 |

31 → 32 → 33 → 34 ist die Kette, die das „Warum" liefert; sie hängt an
nichts anderem. 35 kann parallel laufen — und sollte es, denn Bonns
Niederschriften sind die vierte Quelle für 32. 36 erst nach 35.

Zusammen: sieben bis acht Arbeitstage, unter $25.

## Anhang B — Was ausdrücklich NICHT in diesem Plan liegt

- **Benachrichtigungen und alles für Ratsmitglieder** (Regel 21).
- **Ein „Warum" ohne Text.** Wo kein Abschnitt vorliegt — Magdeburg
  vollständig, Darmstadt, Freiburg, alle SessionNet-Kandidaten außer Münster
  — bleibt die Karte, wie sie ist. Kein Modell füllt die Lücke.
- **Niedersachsen über die Oberfläche ernten.** Hannover, Göttingen,
  Wolfsburg und die übrigen haben Ratsinformationssysteme, nur kein OParl.
  Oldenburg selbst wird genau so gelesen — SessionNet-HTML, `council/`. Ob
  dieser Scraper eine zweite SessionNet-Stadt in Niedersachsen lesen kann,
  ist eine **Probe von einem Nachmittag** (Adresse finden, drei Sitzungen
  holen, Trefferquote messen) und dann eine eigene Entscheidung: Es wäre der
  fünfte Adapter, und einer ohne Schnittstellen-Vertrag. Der einzige Weg zu
  echter Vergleichbarkeit über das Landesrecht — aber nicht dieser Plan.
- **Ein anderes Modell** — gemessen, abgelehnt (§2.4).
- **Der verkettete Cluster 1** — gemessen, abgelehnt (PR #1262).
- **Mehr Städte als Bonn und Darmstadt.** Leipzig und Freiburg sind
  Registry-Einträge, die auf 35/36 warten; Köln und die übrigen SessionNet-
  Städte bringen nichts, was diese Phase braucht.

## Anhang C — Messbefehle

Alle vom Repo-Root. **Nie, während ein Lauf schreibt.**

1. **Protokoll-Zeilen je Stadt** (Speicher, ohne Netz):
   ```bash
   sqlite3 data/cities.sqlite "SELECT m.body_id, COUNT(*), SUM(COALESCE(m.start,'') >= '2024-09-01'), SUM(f.sha256 IS NOT NULL) FROM files f JOIN meetings m ON m.id=f.meeting_id WHERE f.role='protocol' GROUP BY m.body_id"
   ```
   Die letzte Spalte ist heute überall 0 — das ist die Lücke, die PR 31
   schließt. Dazu `resolution_text` je Stadt:
   ```bash
   sqlite3 data/cities.sqlite "SELECT m.body_id, COUNT(*), SUM(a.resolution_text != '') FROM agenda_items a JOIN meetings m ON m.id=a.meeting_id GROUP BY m.body_id"
   ```
2. **Drei Protokolle je Stadt lesen** — lesbar? Marker? Der Befehl vom
   10.09. liegt als Vorlage in diesem Plan: PDF holen, `pypdf`, erste zwölf
   Seiten, Marker zählen (`Punkt \d+ der Tagesordnung` bzw.
   `^\d+(\.\d+)*\s+[A-ZÄÖÜ]`), 200 Zeichen je Seite als Scan-Grenze.
3. **Eine Kandidatenstadt prüfen** (lesend): `system` → `body` →
   `paper?created_since=2024-01-01T00:00:00` (`pagination.totalElements`)
   → erste fünf Vorlagen auf `consultation` → erste acht `meeting` auf
   `resultsProtocol`/`verbatimProtocol` → `license`. Antwortzeit messen.
4. **Die Prüfstände dieser Phase** (ab dem jeweiligen PR):
   ```bash
   python eval/run_cities_sections.py     # PR 32, ohne Modell
   python eval/run_cities_reason.py       # PR 33, ~$0,05
   ```
5. **Neue Stadt** — das Rezept aus `council/cities/CLAUDE.md`, und nach
   jeder Ernte:
   ```bash
   python scripts/cities_backfill.py --pruefen
   ```
