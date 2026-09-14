# Wahlabend und Tippspiel für die nächste Wahl

**Stand 14.09.2026, abends.** PR 1–3 sind gemergt (#1328, #1329, #1331) — die
Stichwahl am 27.09. läuft ohne weiteren Deploy. Offen: PR 4–7.

Beides hat am 13.09. getragen: 539 Aufrufe / 117 Besuche
auf `/wahlabend`, 178/69 auf `/tipp`, dazu 181 Aufrufe auf der Beamer-Bühne —
zusammen rund das Neunfache eines normalen Tages, und fast alles davon anonym.
Das ist der Grund, es nicht als Einwegware stehen zu lassen.

Dieser Plan sagt, was heute an „Ratswahl Oldenburg, 13.09.2026" festgenagelt
ist, wie ein zweiter Wahltermin hineinkommt, und in welcher Reihenfolge.

> **Die nächste Wahl ist in dreizehn Tagen.** Keine Kandidatur hat am 13.09.
> die absolute Mehrheit erreicht (Prange 33,16 %, Rohr 30,54 %) — am
> **27.09.2026 ist OB-Stichwahl**. Sie ist der erste echte Kunde dieses
> Umbaus und zugleich sein Prüfstein: eine Wahl ohne Sitze, ohne Wahlbereiche,
> ohne Personenstimmen, mit genau zwei Namen. Was sie trägt, trägt auch die
> Landtagswahl 2027.

---

## 1. Was schon allgemein ist

Der Kern ist besser gebaut, als der Name „Wahlabend 2026" vermuten lässt.
Diese Teile brauchen **nichts**:

| Baustein | warum er trägt |
|---|---|
| `election/seats.py` | NKWG §§ 36/37 in ganzen Zahlen, gegen das amtliche Ergebnis 2021 geprüft (alle 50 Mandate). Reine Funktionen, kennt weder Jahr noch Stadt. |
| `election/register.py` | Liest Listen, Wahlbereiche, Sitzzahl aus `kommunalwahl/kandidaten.json` — Daten, nicht Code. Inklusive Notausgang `WAHLABEND_COLUMNS`. |
| `election/crosscheck.py` | Spaltenprobe gegen Klartextnamen und Kopfzeile — greift für jede Votemanager-Wahl. |
| `election/history.py` | Verlaufspunkte, Pfad über `WAHLABEND_HISTORY_FILE`. |
| `prediction/scoring.py` | Punkte-Formel als reine Funktionen (nur die `MAX_*`-Konstanten sind zahlgebunden). |
| `prediction/rounds.py` | Runden-Registry — genau das Muster, das dieser Plan auf Wahlen ausdehnt. |
| Die Rückfallstufen | „Der Abend darf an nichts sterben" (`service.live()`, `_actuals`) ist wahlunabhängig. |

## 2. Was fest verdrahtet ist

| Ort | Verdrahtung | Klasse |
|---|---|---|
| `votemanager.py:61` | `DEFAULT_BASE = ".../20260913/03403000"`, drei Dateinamen `…-Stadtratswahl-…` | Quelle |
| `votemanager.py:78` | `ELECTION_NIGHT_START = 13.09.2026 18:00` (steuert den Abruftakt) | Termin |
| `mayor.py:56` | `WAHL_ID = 2552`, `DEFAULT_CITY_ID`, zweite Basis-URL als Literal | Quelle |
| `reference.py:22` | `REFERENZ = kommunalwahl/referenz-2021`, Dateinamen `ratswahl-2021-*.csv` | Referenz |
| `antworten.py:3733` | Vertragsfelder `seats_2021`, `share_2021_pct` | Vertrag |
| `projection.py` | Hochrechnung setzt „Bezirke sind wie 2021 geschnitten" voraus | Methode |
| `register.py:38` | `KOMMUNALWAHL = <repo>/kommunalwahl` — ein Ordner, eine Wahl | Daten |
| `prediction/scoring.py:16` | `MAX_SEAT_POINTS = 16 * 5`, `MAX_MAYOR_POINTS = 9 * 6` | Regeln |
| `prediction/service.py:310` | Startverteilung liest `seats_2021` aus dem Wahlabend | Referenz |
| `kern/store.py:567` | `prediction_game` trennt **Runden**, kennt aber keine **Wahl** | Schema |
| `kern/features.py:89` | Schalter `wahlabend`/`tippspiel` sind Ein/Aus, nicht „welche Wahl" | Lebenszyklus |
| Frontend, ~30 Stellen | „Ratswahl Oldenburg · 13.09.2026", „52 Sitze", „2021", „Stichwahl am 27. September", `WAHLABEND_BEGINN_UTC` in `lib/wahlabend.ts:249`, Titel in beiden `layout.tsx` | Texte |
| `lib/wahl-flaechen.ts` | Wahlergebnis-Ebene der Stadtkarte hängt am Ratswahl-Schnitt | Anschluss |

Vier Umgebungsvariablen gibt es schon (`WAHLABEND_VOTEMANAGER_URL`,
`WAHLABEND_COLUMNS`, `WAHLABEND_HISTORY_FILE`, dazu die Feature-Schalter).
Sie sind Notausgänge für **eine** Wahl, keine Konfiguration für mehrere:
Zwei Wahlen gleichzeitig — Rückblick Ratswahl **und** laufende Stichwahl —
lassen sich damit nicht ausdrücken.

## 3. Zielbild

**Eine Wahl ist eine Zeile in einer Registry plus eine Datei mit ihren Daten.**
Genau wie eine Tipprunde (`prediction/rounds.py`) und wie ein Feature-Schalter
(`kern/features.py`): im Code sichtbar, im PR diffbar, ohne Verwaltungsoberfläche.

```
kommunalwahl/wahlen/
  ratswahl-2026.json        # Identität, Quelle, Referenz, Verweis auf kandidaten.json
  ob-2026.json
  ob-stichwahl-2026.json
  ratswahl-2021.json        # nur Referenz, kein Abruf
web/backend/app/election/
  elections.py              # die Registry: laden, auflösen, „welche ist aktiv?"
  sources/votemanager.py    # ein Adapter je Ergebnissystem (heute: KDO)
  types/nkwg.py             # Verhältniswahl mit Wahlbereichen (heute: seats.py)
  types/mehrheit.py         # Mehrheitswahl / Stichwahl (heute: mayor.py)
```

Drei Begriffe, die der Bestand vermischt:

1. **Wahl** (welche, wann, welche Quelle) — heute implizit.
2. **Wahltyp** (wie wird aus Stimmen ein Ergebnis) — heute nur NKWG, plus
   `mayor.py` als angehängter Sonderfall.
3. **Ergebnissystem** (woher die Zahlen) — heute nur Votemanager KDO.

Und eine Regel, die den Umbau billig hält: **`seats.py` wird nicht angefasst.**
Es ist der einzige Teil, der gegen ein amtliches Ergebnis verifiziert ist; es
umzubauen, um es allgemeiner zu machen, riskiert genau das, wofür es da ist.
Es bekommt nur einen anderen Aufrufer.

---

## 4. Die PRs

### PR 1 — Das Ergebnis 2026 einfrieren ✅ *(#1328, auf `dev`)*

**Warum zuerst:** Die Live-CSVs von `votemanager.kdo.de/20260913/…` antworten
heute noch. Erfahrungsgemäß wandern sie ins Archiv, und der Referenzordner für
die nächste Kommunalwahl entsteht dann aus einem 404. `referenz-2021/` ist der
Beweis, dass wir das brauchen werden.

- Skript `scripts/wahl_einfrieren.py <wahl-slug>`: holt Stadt-, Wahlbereichs-
  und Wahlbezirks-CSV sowie die Präsentations-JSONs der OB-Wahl, legt sie unter
  `kommunalwahl/referenz-2026/` ab und schreibt `ratswahl-2026.json` im Format
  von `ratswahl-2021.json` (amtliche Sitzverteilung, Spaltenindex → Slug).
- Dazu den Verlauf `data/wahlabend-verlauf.json` von Prod sichern — 13.09. ist
  darin nicht wiederholbar.
- **Abnahme:** `reference.load(REFERENZ_2026)` liefert 52 Sitze und dieselbe
  Sitzverteilung, die `/api/wahlabend` heute zeigt.
- **Wächter:** ein Test, der beide Referenzordner gegen dasselbe Schema hält.

### PR 2 — Wahl-Registry (Identität und Quelle) ✅ *(auf `dev`)*

**Abweichung mit Grund:** `reference` nennt einen **Ordner**, nicht den Slug
einer früheren Wahl. Eine Referenz ist ein Ordner mit CSVs; ihr einen
Registry-Eintrag zu geben hieße, eine Wahl zu erfinden, die wir nie ausliefern.
Ebenso trägt die Registry die **Sitzzahl** doppelt (sie steht auch im
Register) — damit `service._bare` sie kennt, wenn genau das Register nicht
lesbar ist; ein Wächter hält beide Zahlen gegeneinander.

- `kommunalwahl/wahlen/<slug>.json`: `slug`, `title`, `short_title`, `date`,
  `polls_close` (löst `ELECTION_NIGHT_START` ab), `type`, `source` (Adapter +
  Basis-URL + Dateinamen bzw. `wahl_id`), `register` (Pfad auf
  `kandidaten.json`), `reference` (Slug der Vorwahl), `status`.
- `election/elections.py`: `load(slug)`, `active()` (die Wahl, deren Abend
  läuft), `all()`. `WAHLABEND_ELECTION=<slug>` als Notausgang in der `.env` —
  dieselbe Begründung wie bei `WAHLABEND_COLUMNS`: umstellbar ohne Deploy.
- `votemanager.py`, `mayor.py`, `reference.py`, `register.py`, `history.py`
  nehmen die Wahl als Parameter statt aus Modulkonstanten. Die bestehenden
  Umgebungsvariablen bleiben als Überschreibung **je Wahl** gültig.
- Bestand wandert 1:1 in `ratswahl-2026.json` und `ob-2026.json`.
- **Abnahme:** `/api/wahlabend` liefert byte-gleich dieselbe Antwort wie vorher
  (Fixture-Vergleich gegen einen heute gezogenen Stand).
- **Wächter:** `tests/test_wahlregistry.py` — jede Registry-Datei validiert,
  jeder `reference`-Verweis existiert, keine zwei Wahlen mit `status: live`.

### PR 3 — Stichwahl 27.09.2026 ✅ *(der erste echte Kunde)*

- `election/types/mehrheit.py`: `mayor.py`, gelöst von der Ratswahl — eine
  Wahl mit Kandidaturen, Prozenten, Auszählungsstand, Verlauf und
  Gewählten-Satz. Stichwahl ist derselbe Typ mit zwei Kandidaturen.
- `ob-stichwahl-2026.json` mit `first_round: ob-2026` — der Vergleich ist
  „erster Wahlgang", nicht „2021".
- **Abweichung, gemessen:** Die Wahl-Id steht NICHT in der Datei. Am
  14.09.2026 kennt `termin.json` nur 913 und 2552; die Stichwahl-Id vergibt
  die Stadt erst. Sie wird deshalb zur Laufzeit am Titel gesucht
  (`source.discover`). Dass eine Stichwahl unter dem Termin der HAUPTWAHL
  läuft, ist an den Terminlisten der Stadt gemessen (2006 und 2021).
- **Zweite Abweichung:** eine **eigene Seite** `/wahlabend/stichwahl` statt
  eines Typ-Schalters auf `/wahlabend`. `active()` liefert weiter die Ratswahl
  (die Stichwahl ist `kind: mayor`), und genau so soll es sein: Am 27.09.
  suchen Leute unter `/wahlabend` immer noch das Ergebnis der Ratswahl.
  `wahl-flaechen.ts` bleibt unberührt.
- **Kein Verlauf und keine Teilen-Karte** in diesem Schritt — eine Stichwahl
  ist eine Zahl je Name, der Aufwand steht in keinem Verhältnis. Nachrüstbar.
- **Abnahme:** Generalprobe `?probe=ob-2026` zeigt den 13.09.-Stand auf zwei
  Namen zusammengezogen; am 27.09. ab 18 Uhr läuft die Seite ohne Deploy.
- **Wächter:** Fixture des Stichwahl-JSONs, Test auf „genau zwei Kandidaturen,
  Summe ≈ 100 %".

> **Terminrisiko erledigt:** PR 2 und PR 3 sind rechtzeitig fertig geworden;
> die Konstante als Notlösung wurde nicht gebraucht.
>
> **Offen bis zum 27.09.:** Sobald die Stadt die Stichwahl beim Votemanager
> anlegt, einmal `curl` auf `termin.json` und prüfen, dass der Titel wirklich
> „Stichwahl" enthält — findet die Suche ihn nicht, hilft ein Eintrag
> `presentation_id` in `ob-stichwahl-2026.json` (ein Fünf-Zeilen-PR).

### PR 4 — Vertrag ohne Jahreszahl

- `seats_2021` → `seats_previous`, `share_2021_pct` → `share_previous_pct`,
  dazu `previous_label` („2021" bzw. „1. Wahlgang") aus der Registry.
- Frontend: alle „2021"-Texte aus dem Vertrag speisen
  (`view.tsx`, `share.py`, `image.py`, `tippen.tsx`).
- **Falle:** Die ausgelieferte iOS-App liest den Vertrag nicht für diese
  Felder (kein `/wahlabend` in `ios/`) — vor dem Release trotzdem
  `scripts/ios_vertrag.py --ausgeliefert` laufen lassen.
- **Wächter:** `pruefe.py --nur vertrag`; ein Test, der im Frontend keine
  literale Jahreszahl neben einem Wahlwert mehr findet.

### PR 5 — Texte aus der Wahl statt aus dem Quelltext

- `/api/wahlabend` und `/api/tipp/setup` liefern `election`: `title`,
  `date_label`, `polls_close`, `kind`, `seats_total`, `status`.
- `layout.tsx` beider Seiten auf `generateMetadata()` umstellen — Titel,
  Beschreibung, OG-Bild aus der aktiven Wahl.
- `lib/wahlabend.ts:249` (`WAHLABEND_BEGINN_UTC`) und der Countdown lesen
  `polls_close`; `mehrheiten.tsx` nennt Stichwahl-Datum und Sitzzahl aus den
  Daten.
- **Abnahme:** Ein Wechsel der aktiven Wahl in der `.env` ändert Titel,
  Countdown, Sharebild-Fußzeile und Sitzzahl ohne Deploy.

### PR 6 — Tippspiel an eine Wahl binden

- `prediction_game` bekommt `election_slug` (Migration wie bei `slug`/`game_id`
  am 12.09., s. `kern/store.py:1592`) — Bestand auf `ratswahl-2026`.
- `prediction_result`-Zeilen bleiben je `(game_id, slug)`; `slug` heißt bei
  Mehrheitswahlen wie heute `ob:<name>`.
- **Tipp-Schema je Wahltyp:** `seats` (ganze Zahlen, Summe = Sitzzahl) oder
  `pct` (Prozent, Summe = 100). Heute steckt beides fest verdrahtet
  nebeneinander in `tippen.tsx`; künftig entscheidet der Typ, was das Formular
  zeigt und was `scoring` rechnet.
- `MAX_SEAT_POINTS`/`MAX_MAYOR_POINTS` aus Listenzahl und Kandidaturenzahl der
  Wahl rechnen statt aus `16 * 5` / `9 * 6`.
- `_check_auto_lock` hängt am Wahlabend **dieser** Wahl (heute an der Ratswahl).
- **Abnahme:** Eine Stichwahl-Runde („tippe die zwei Prozentwerte") lässt sich
  anlegen, ohne eine Zeile Punkte-Code anzufassen.
- **Wächter:** `tests/test_prediction_runden.py` erweitern: eine Runde je Typ,
  Punktehöchstwerte gegen die Registry.

### PR 7 — `/wahlen`: eine Übersicht, und `/wahl` zeigt immer auf die richtige

*Tims Idee vom 14.09.2026, nach dem Merge der Stichwahl. Umfang entschieden:
nur unsere eigenen Wahlen — was im Repo liegt, nicht was der Votemanager
sonst noch hat.*

Heute regelt der Feature-Schalter nur „Seite da / 404", und `/wahlabend` ist
der Name **eines Abends**. Für die 51 Wochen dazwischen stimmt er nicht, und
für einen Rückblick auch nicht.

**Drei Adressen, und keine davon bricht eine alte.**

| Adresse | Was |
|---|---|
| `/wahlen` | Die Übersicht: oben die nächste mit Countdown, darunter die vergangenen mit Ergebnis |
| `/wahlen/<slug>` | Eine Wahl, dauerhaft — `/wahlen/ratswahl-2026` ist auch 2031 noch abrufbar |
| `/wahl` | Kurz und sagbar („ratslotse.de/wahl"), zeigt immer die Wahl **im Fokus** |

`/wahlabend` **bleibt und zeigt dasselbe wie `/wahl`.** Das ist keine Höflichkeit
gegenüber alten Links: Die Adresse steht in der Fußzeile jedes Sharepics
(`election/image.py`, `share.py`), auf den QR-Codes des Tippspiels und in den
Verläufen der Leute, die am 13.09. dort waren. Sie darf nie 404 werden.

**Die Fokus-Regel** kommt aus der Registry, nicht aus einem Handschalter:

```
von  polls_close − 2 Tage
bis  polls_close + 3 Tage      → diese Wahl ist im Fokus
```

Danach fällt der Fokus auf die nächste anstehende Wahl; gibt es keine, zeigt
`/wahl` die Übersicht. Zwei Tage vorher ist früh genug, dass ein geteilter
Link am Wahlwochenende schon richtig führt, und spät genug, dass die Seite
nicht wochenlang einen Countdown zeigt. Die Zahlen gehören als Konstanten
neben `elections.active()`, nicht in eine Komponente — `tests/test_wahlkalender.py`
hält sie fest, samt der Fälle „zwei Wahlen am selben Tag" (13.09.: Ratswahl
und OB) und „keine kommt mehr".

**Der Lebenszyklus dahinter** (das war der alte PR-7-Text, er bleibt gültig):

- `status` in der Registry: `vorbereitung` (Countdown, Generalprobe), `live`
  (Abruftakt 60 s), `rueckblick` (**kein Abruf**, der eingefrorene Stand aus
  dem Referenzordner).
- Damit braucht `/wahlen/ratswahl-2026` den Votemanager nicht mehr — die
  Zahlen liegen seit PR 1 im Repo. Das ist der eigentliche Gewinn: Eine
  Rückblick-Seite, die von einer fremden Adresse abhängt, ist keine.
- Dasselbe Muster für `/tipp/<slug>`; die heutigen Adressen bleiben gültig
  (wie die Hauptrunde ohne `?runde=`).
- Die Feature-Schalter bekommen ein ehrliches `fertig_wenn`: Sie schalten
  künftig „gibt es Wahlseiten?", nicht „läuft dieser eine Abend?".

**Was auf der Übersicht steht** — vier Einträge, mehr haben wir nicht, und
mehr braucht sie nicht:

| Wahl | Woher die Zahlen |
|---|---|
| Stichwahl OB, 27.09.2026 | live bzw. Rückblick |
| Ratswahl, 13.09.2026 | `kommunalwahl/referenz-2026/` |
| OB-Wahl, 13.09.2026 | `kommunalwahl/referenz-2026/praesentation-ob.json` |
| Ratswahl, 12.09.2021 | `kommunalwahl/referenz-2021/` |

Je Zeile: Datum, Titel, das Ergebnis in einem Satz („Grüne 13 Sitze, SPD 12"
bzw. „Ulf Prange 52,1 %"), und der Weg zur Seite. Die 2021er Zeile ist der
Beweis, dass die Gattung trägt — sie kommt aus einem Ordner, den niemand
mehr anfasst.

**Abnahme.**

- `/wahlen/ratswahl-2026` zeigt den 13.09. mit abgeschaltetem Netz.
- `/wahl` führt am 25.09. auf die Stichwahl, am 20.09. auf die Übersicht und
  am 28.09. wieder auf die Stichwahl (dritter Tag danach).
- `/wahlabend` antwortet nie 404 — auch nicht, wenn gar keine Wahl ansteht.

**Wächter.** `tests/test_wahlkalender.py` für die Fokus-Regel; ein Test, der
jede Wahl der Registry auf `/wahlen/<slug>` erreichbar hält; und die
bestehende Positivliste in `kern/seitenaufrufe.py` um die neuen Pfade ergänzt
(sonst zählen sie als `/andere`).

**Bewusst nicht in diesem PR:** die übrigen Wahlen aus dem Archiv der Stadt.
Was dort maschinenlesbar ist, steht unter PR 8 — mit dem, was am 14.09.2026
gemessen wurde.

### PR 8 — Mehr Wahlen: das Archiv der Stadt *(erst wenn es jemand braucht)*

**Gemessen am 14.09.2026** (`votemanager.kdo.de/03403000/api/termine.json` und
je Termin `daten/api/termin.json`):

| Termin | maschinenlesbar? | was dazukäme |
|---|---|---|
| Bürgerentscheid Baumschutz, 22.02.2026 | ✅ | **fast geschenkt**: flache Tabelle „Ja 60,58 % / Nein 39,42 %" — dieselbe Form, die `mayor.py` schon liest; dazu ein `quoren`-Block |
| Bundestagswahl, 23.02.2025 | ✅ | der eine neue Begriff: **Stimmentyp**. Zwei Einträge mit derselben Wahl-Id (596), unterschieden nur durch Erst-/Zweitstimme |
| Europawahl, 09.06.2024 | ✅ | reine Listenwahl ohne Wahlbereiche |
| Landtagswahl 2022 und älter | ❌ | altes Votemanager-Format, kein `termin.json` |

Der Bürgerentscheid ist der billigste nächste Schritt und zugleich der Beweis,
dass „Mehrheitswahl" als Typ mehr trägt als OB-Wahlen: Ja und Nein sind zwei
Kandidaturen, das Quorum ist eine Zeile mehr.

Landtags- und Bundestagswahl brauchen darüber hinaus eine zweite Quelle, wenn
mehr als das Stadtgebiet interessiert — sie laufen über die Landeswahlleitung,
mit anderen Gebietsschnitten (Wahlkreise statt Wahlbereiche).

- `election/sources/`: ein Protokoll `Quelle` (`fetch() -> Snapshot`), heutiger
  Code als `sources/votemanager.py`. Muster: `council/cities/` — ein Adapter je
  System, Plausibilitätsprüfung nach jedem Abruf.
- **Nicht auf Vorrat bauen.** Das Protokoll entsteht mit dem zweiten Adapter,
  nicht davor — sonst schneidet es an der falschen Stelle.

---

## 5. Reihenfolge

```
PR 1 (einfrieren) ✅ ──┐
                       ├─→ PR 3 (Stichwahl) ✅ ──→ PR 4 ──→ PR 5 ──→ PR 6 ──→ PR 7
PR 2 (Registry)   ✅ ──┘
```

**PR 7 hängt an PR 5** (Texte aus der Wahl statt aus dem Quelltext): Eine
Übersicht, die jeden Titel und jedes Datum noch einmal im Frontend
buchstabiert, wäre die dritte Fassung derselben Angaben.

- **Diese Woche:** PR 1 und PR 2. PR 1 ist eilig, weil die Quelle verschwindet.
- **Bis 26.09.:** PR 3, plus eine Generalprobe am Vorabend wie am 12.09.
- **Danach in Ruhe:** PR 4–7. Sie haben keinen Termin; der nächste echte ist
  die Landtagswahl Niedersachsen im Herbst 2027.
- **PR 8** erst, wenn jemand die anderen Wahlen vermisst. Der Bürgerentscheid
  wäre der günstigste Einstieg.

## 6. Bewusst nicht

- **Keine Wahlverwaltung im Admin-Panel.** Dieselbe Begründung wie bei den
  Tipprunden: Eine Wahl kommt alle paar Jahre, und jede braucht ohnehin
  Handarbeit an den Kandidatendaten. Ein Fünf-Zeilen-PR ist billiger als eine
  Oberfläche, die am Wahlabend kaputtgehen kann.
- **Keine Automatik für Kandidatenlisten.** `kommunalwahl/kandidaten.py` zieht
  sie aus der amtlichen Bekanntmachung; das bleibt geprüfte Handarbeit. Was
  dazukommt, ist ein Schema-Test, nicht ein Scraper.
- **`seats.py` bleibt unangetastet** (s. o.).
- **Keine andere Stadt.** Das Register ist schon stadtunabhängig; ein zweiter
  Ort braucht aber Wahlbereichsdaten, Kartenflächen und eine Quelle — das ist
  ein eigener Plan, kein Nebenprodukt dieses hier.
- **Keine Vorratsabstraktion für Wahltypen.** Zwei Typen (NKWG, Mehrheitswahl)
  ergeben noch kein Interface für fünf. Der dritte schneidet es.

## 7. Was den Umbau prüft

Die Generalprobe ist schon da und ist der beste Wächter: `?probe=<referenz-slug>`
muss nach jedem PR dasselbe Bild ergeben wie vorher. Dazu:

- Ein Fixture-Vergleich gegen einen heute gezogenen Live-Stand (PR 2).
- `tests/test_wahlabend*.py` (zehn Dateien) laufen unverändert weiter — sie
  sind der Beweis, dass die Verallgemeinerung nichts gekostet hat.
- `scripts/rauchprobe.py` um `/api/wahlabend` erweitern, sobald die Seite
  dauerhaft (als Rückblick) steht.
