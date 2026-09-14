# Umsetzungsplan: die Stichwahl spannend — Hochrechnung je Wahlbezirk, Momente, Verlauf

Stand: 14.09.2026, spätabends. Die Stichwahl um das Oberbürgermeisteramt ist
am **27.09.2026**, die Seite `/wahlabend/stichwahl` steht seit v2.5.0 auf
Prod. Dieser Plan ist wie seine Vorgänger geschrieben: **ohne das Gespräch
dahinter ausführbar** — je PR Dateien, Signaturen, Tests, Fertig-Kriterium;
jede Zahl gemessen, Anhang C nennt den Befehl.

Wer das umsetzt, liest vorher: die Wurzel-`CLAUDE.md`, `web/backend/CLAUDE.md`,
`web/frontend/CLAUDE.md`, **DESIGNSPRACHE.md §7 „Bewegung"**, die Docstrings
von `web/backend/app/election/mayor.py`, `presentation.py`, `projection.py`,
`history.py` und `components/wahlabend/stichwahl.tsx`.

## 0. Was Tim gesagt hat (14.09.2026, abends)

> Was ich noch cool finden würde für die Stichwahl: dass das Ganze ein
> bisschen spannender wäre. Mit Animationen, dass da wirklich was hochgeht,
> wenn was neu ausgezählt wird. Dass eine Meldung kommt, wenn etwas neu
> ausgezählt worden ist. Statistisch kann man wahrscheinlich angeben, wenn
> x Prozent ausgezählt sind, wie wahrscheinlich es ist, dass einer der beiden
> tatsächlich Oberbürgermeister wird — **wenn man das statistisch verlässlich
> sagen kann.** Wir haben nur zwei Kandidierende, und das wird ausgezählt.

Die Bedingung im Fettdruck ist die Vorgabe für alles Statistische hier: Was
die Seite als Zahl zeigt, muss aus Zahlen kommen, die sie belegen kann, und
sagen, was es nicht ist.

## 1. Gemessen — was wir wirklich haben

### 1.1 Ein Abruf, 133 Wahlbezirke

Die Stichwahl hat keine Open-Data-CSV (die Seite sagt das in ihrer
Quellenzeile). Sie hat aber die **Ergebnisdarstellung**, und die liefert
mehr, als die Seite heute liest. Gemessen am ersten Wahlgang
(`wahl_2552`):

| Datei | Inhalt | Größe |
|---|---|---|
| `wahl.json` | `menu_links`: Stadt (`ergebnis`) und **„Wahlbezirke" (`uebersicht`, `ebene_6`)** | klein |
| `uebersicht_ebene_6_0.json` | **eine Zeile je Wahlbezirk** (133): `label` („101 Amt für Gebäudewirtschaft …"), `statusString` („eingegangen"), `statusProzent`, `felder` = Wahlberechtigte, Wahlbeteiligung, gültig, **je Kandidatur absolut + Prozent** | 222 KB |
| `ergebnis_<gebiet>_0.json` | dasselbe je Bezirk einzeln | je ~3 KB |

Das heißt: **Ein einziger Abruf pro Minute** trägt den Stand aller 133
Bezirke samt „schon eingegangen?". Heute liest `mayor.fetch` nur die
Stadtzeile. Die Bezirks-Ebene ist derselbe Dienst, dieselbe Cache-Frist,
dieselbe Höflichkeit (`kern/proxy` braucht es nicht, der Votemanager sperrt
Hetzner nicht).

### 1.2 Der erste Wahlgang je Wahlbezirk — die Streuung

Alle 133 Bezirke des ersten Wahlgangs gelesen (Anhang C). Prange-Anteil
unter den beiden Stichwahl-Kandidaturen, also Prange ÷ (Prange + Rohr):

| | Wert |
|---|---|
| Mittel über Bezirke (ungewichtet) | 52,7 % |
| **Streuung σ zwischen Bezirken** | **8,0 Punkte** |
| kleinster / größter Bezirk | 34,8 % / 72,8 % |
| gewichtet gesamt | 52,1 % |
| **Urne (91 Bezirke)** | **53,7 %** |
| **Briefwahl (42 Bezirke)** | **48,9 %** |
| Anteil der Briefwahl an den gültigen Stimmen | 32 % |
| gültige Stimmen je Bezirk | 343 – 957 |

Zwei Befunde, die den Rest des Plans bestimmen:

1. **Die Reihenfolge der Auszählung entscheidet über das Zwischenbild.** Bei
   σ = 8 Punkten und Bezirken von 35 % bis 73 % kann der Führende nach 30
   Bezirken der Verlierer nach 133 sein. „Wer führt gerade" ist ohne
   Hochrechnung keine Aussage über den Ausgang — das ist der Grund, sie zu
   bauen, und der Grund, sie ehrlich zu beschriften.
2. **Die Briefwahl liegt fast fünf Punkte anders als die Urne** und ist ein
   Drittel der Stimmen. Ein Modell, das beides in einen Topf wirft, ist um
   diese fünf Punkte falsch, sobald die Briefwahlbezirke gesammelt am Ende
   (oder gesammelt am Anfang) kommen. Die Hochrechnung rechnet deshalb
   Urne und Brief **getrennt**.

### 1.3 Was schon da ist

- `projection.py` rechnet für die Ratswahl genau das Prinzip: offener
  Bezirk = Vorwahl-Ergebnis, skaliert mit dem Trend der schon gezählten im
  selben Wahlbereich. Für zwei Kandidaturen ist es dasselbe mit einer
  Zahl je Bezirk.
- `history.py` schreibt den Minuten-Verlauf der Ratswahl in eine Datei und
  liefert ihn als `ElectionNight.history`; `verlauf.tsx` zeichnet ihn.
- `useTween` (Zahlen gleiten), `useFrisch` (kurzes Aufleuchten nach einem
  Anstieg), `staffel.tsx` (gestaffelter Einstieg), `gleit-marker` — die
  Bewegungs-Bausteine aus DESIGNSPRACHE §7.
- `Gebietskarte` (#1354): 91 Urnenbezirke als Flächen, tönbar je Wert.
- Lotti-Regungen (`mascot.tsx`): u. a. `hebt-pokal`, `staunt`, `winkt`.

### 1.4 Die Stichwahl 2021 — die Kalibrierung, die es gibt

Tim: „2021 gab es eine Stichwahl." Stimmt — Krogmann (SPD) gegen Fuhrhop
(GRÜNE) am 26.09.2021, und sie liegt beim Votemanager noch vollständig je
Wahlbezirk vor (alte API: `/20210912/03403000/api/praesentation/`, erster
Wahlgang `wahl_223`, Stichwahl `wahl_224`, 133 Bezirke wie 2026). Damit
lässt sich das Modell aus §3 gegen einen echten Abend halten, Bezirk für
Bezirk. Gemessen (Anhang C):

| | erster Wahlgang → Stichwahl | Schwung | σ(Stichwahl − erwartet) je Bezirk |
|---|---|---|---|
| alle 133 | 58,2 % → 54,1 % | −4,1 | 3,6 Punkte |
| Urne (91) | 59,0 % → 55,8 % | **−3,2** | 3,3 Punkte |
| Brief (42) | 56,4 % → 49,9 % | **−6,5** | 3,0 Punkte |

Drei Befunde:

1. **Ein Bezirk stimmt in der Stichwahl fast genau so ab wie im ersten
   Wahlgang, verschoben um EINEN Schwung.** Zwischen den Bezirken streut der
   Anteil um 11 Punkte, der Rest nach dem Schwung nur um 3 — das ist die
   Zusage, auf der die Hochrechnung steht.
2. **Der Schwung ist in der Briefwahl ein anderer** (−6,5 gegen −3,2): 2021
   drehte die Briefwahl in der Stichwahl auf 49,9 %, während die Urne bei
   55,8 % blieb. Wer beide Töpfe zusammenwirft, liegt um gut drei Punkte
   daneben — bei einer Wahl, die im ersten Wahlgang 52 : 48 stand, ist das
   der Unterschied zwischen richtig und falsch.
3. **Die Reihenfolge der Auszählung kann das naive Bild kippen.** 300
   zufällige Reihenfolgen nachgespielt: Kommt die Briefwahl zuerst, sagte
   „wer führt gerade" nach 10, 15 und 30 Bezirken in **54 % der Fälle den
   Falschen** — Fuhrhop führte, Krogmann gewann. Die Hochrechnung mit zwei
   Schwüngen lag nach 30 Bezirken in **100 %**, nach 15 in 96 % der Fälle
   richtig; in zufälliger Reihenfolge oder Urne-zuerst ab 10 Bezirken immer.
   Ihre Schwäche: Solange NUR die Briefwahl gezählt ist, leiht sie sich
   deren Schwung für die Urne — und war damit nach zehn Bezirken in 9 % der
   Fälle sicher und falsch. Deshalb der Topf-Term in §3 S2 Punkt 5.

Was 2021 nicht prüfen kann: einen knappen Ausgang. 6.544 Stimmen Vorsprung
sind 8 Punkte; das Modell war schnell sicher, weil es leicht war. Für 2026
(erster Wahlgang 52 : 48 unter den beiden) ist die Unsicherheit ehrlich zu
nennen — deshalb Sockel, Deckel und das Wort „Modell".

## 2. Die Reihenfolge — und warum

| PR | Was | Hängt an | Aufwand |
|---|---|---|---|
| **S1** | Die 133 Bezirke live lesen + den ersten Wahlgang je Bezirk einfrieren | — | mittel |
| **S2** | Hochrechnung, „rechnerisch entschieden", **Chance** (ehrlich beschriftet) | S1 | mittel |
| **S3** | Verlauf des Abends (Datei + Linie), Führungswechsel als Ereignis | S1 | klein |
| **S4** | Momente und Bewegung: „12 weitere Bezirke", Aufleuchten, Bühne „Entschieden" | S2, S3 | mittel |
| **S5** | Die Karte der Stichwahl: erster Wahlgang als Tönung, dann Bezirk für Bezirk live | S1 | klein |

S1 ist die Grundlage, ohne die nichts Statistisches ehrlich wäre. S2 ist
Tims eigentlicher Wunsch. S3 und S4 sind das „spannend". S5 ist fast
geschenkt, weil #1354 die Flächen schon hat. Alles muss **vor dem 27.09.**
auf Prod sein und am 27.09. ab 18 Uhr laufen — mit einer Generalprobe
(`?probe=1&counted=N`) am Tag davor.

## 3. Die Pull Requests

### PR S1 — Die Bezirke der Stichwahl live, der erste Wahlgang eingefroren

**Backend.**

- `mayor.py`: neuer Abruf `fetch_districts(session, base, api) -> tuple[MayorDistrict, ...]`
  aus `uebersicht_ebene_6_0.json`; die Ebenen-Id kommt aus `wahl.json`
  (`menu_links`, `type: uebersicht`, Titel „Wahlbezirke") wie
  `presentation.ids_of`. Je Zeile:

  ```python
  @dataclass(frozen=True)
  class MayorDistrict:
      number: int          # 101…966 aus dem Label (votemanager.district_number)
      name: str
      area: int            # Hunderter bzw. Zehner ab 900 (votemanager.area_of_district)
      postal: bool         # number >= 900
      counted: bool        # statusString == "eingegangen"
      eligible: int | None
      valid_votes: int | None
      votes: dict[str, int | None]   # slug -> Stimmen, nur die known-Kandidaturen
  ```

  Die Kandidaten-Spalten kommen aus `tabelle.header[].labelKurz` („Rohr,
  GRÜNE") → Nachname → `slug_of`, Zuordnung wie `_row_candidate`. Eine
  Spalte, die zu keiner bekannten Kandidatur passt, wird ignoriert und
  einmal geloggt — die Stichwahl hat genau zwei. **Falle, gemessen:**
  `felder` ist um ZWEI kürzer als `header` — „Wahlbezirk" und „Stand"
  stehen als `label`/`statusString` in der Zeile, nicht in `felder`. Spalte
  `i` des Kopfes ist `felder[i − 2]`; wer `i − 1` nimmt, liest die
  Wahlberechtigten als Wahlbeteiligung und bekommt lauter `None`. 2021 und
  2026 gleich.
- `MayorResult` bekommt `districts: tuple[MayorDistrict, ...]`; `fetch` holt
  sie im selben Lauf (ein Request mehr je Minute).
- **Eingefrorener erster Wahlgang je Bezirk**: `scripts/wahl_einfrieren.py`
  legt zusätzlich `kommunalwahl/referenz-2026/ob-2026-wahlbezirke.json` an —
  die 133 Zeilen in der Form oben, mit `votes` für alle neun Kandidaturen.
  Gehört ins Repo: Der Votemanager-Pfad trägt den Wahltag und wandert ins
  Archiv, und die Hochrechnung darf am 27.09. nicht davon abhängen, dass
  der 13.09. noch online ist.
- Neuer Endpunkt `GET /api/wahlabend/stichwahl/bezirke` → `MayorDistrictList`
  (Vertrag in `antworten.py`; die 133 Zeilen gehören nicht in
  `MayorNight`, die Seite braucht sie erst für Karte und Modell). Öffentlich
  wie die Stichwahl, hinter demselben Schalter, in
  `tests/test_endpunkt_schutz.py` eintragen.

**Tests.** `tests/test_stichwahl_bezirke.py` gegen ein eingecheckte Fixture
`tests/fixtures/wahlabend/uebersicht_ebene_6_2552.json` (der erste
Wahlgang, 222 KB — wie die 2021-Fixtures): 133 Zeilen, 91 Urne + 42 Brief,
Summe der Bezirks-Stimmen je Kandidatur = Stadtzeile (Prange 28.075? — die
Zahl beim Bauen aus `praesentation-ob.json` nehmen), `counted` aus
`statusString`. Und: Bezirke summieren sich je Wahlbereich zu den sechs
Bereichs-Ergebnissen.

- **2021 als zweites Fixture**: `tests/fixtures/wahlabend/stichwahl-2021/`
  mit beiden `uebersicht`-Dateien (223 und 224). Sie sind die Kalibrierung
  aus §1.4 und gehören ins Repo, bevor die alte API verschwindet.

**Fertig, wenn:** `curl /api/wahlabend/stichwahl/bezirke?probe=1` 133 Zeilen
liefert, der Wochenabruf im Log genau einen zusätzlichen Request je Minute
zeigt, und der eingefrorene erste Wahlgang im Repo liegt.

### PR S2 — Hochrechnung, „rechnerisch entschieden", Chance

Das Herz, und der Teil, bei dem Ehrlichkeit vor Spannung geht.

**Das Modell** (`web/backend/app/election/runoff_model.py`, reine Funktionen,
kein Netz):

1. **Vorwahl-Erwartung je Bezirk:** `p_i` = Prange ÷ (Prange + Rohr) im
   ersten Wahlgang, Bezirk *i*. Das ist die einzige Zahl, die den Bezirk
   charakterisiert; alle anderen Kandidaturen des ersten Wahlgangs fallen
   weg — wohin deren Stimmen gehen, weiß niemand, und das Modell tut nicht
   so.
2. **Zwei Schwünge, nicht einer:** Für die gezählten Urnenbezirke
   `s_U = Σ(ist − p_i·gültig_i) ÷ Σ gültig_i`, dasselbe getrennt für die
   gezählten Briefwahlbezirke `s_B`. Solange einer der beiden Töpfe leer ist,
   nimmt er den Schwung des anderen (mit dem Vermerk „Briefwahl noch ohne
   eigene Zahlen").
3. **Offene Bezirke:** erwartete Prange-Stimmen = `(p_i + s) · n_i · f`,
   mit `n_i` = Stimmen für die beiden im ersten Wahlgang und `f` = das
   Verhältnis der in den gezählten Bezirken beobachteten Zwei-Kandidaten-
   Stimmen zu denen des ersten Wahlgangs. 2021 lag `f` bei **1,57**: Die
   Stichwahl hatte 11 % mehr gültige Stimmen als der erste Wahlgang, und
   die Stimmen der ausgeschiedenen Kandidaturen verteilten sich auf die
   beiden. Das Modell misst `f`, es rät es nicht.
4. **Hochrechnung:** gezählte Ist-Stimmen + erwartete Stimmen der offenen
   Bezirke → Endstand in Prozent. Das ist dieselbe Logik wie
   `projection.py` für die Ratswahl und darf auch so heißen.
5. **Unsicherheit:** die Reste `r_i = ist_i − (p_i + s)·n_i·f` der
   gezählten Bezirke haben eine Streuung `σ_r` (in Stimmen). Der
   hochgerechnete Vorsprung hat dann die Streuung
   `σ² = Σ_offen (2·σ_r·n_i / n̄)²` — die Unsicherheit wächst mit Zahl und
   Größe der offenen Bezirke und schrumpft, je besser das Modell die
   gezählten trifft. **Dazu der Topf-Term:** Solange ein Topf (Urne oder
   Brief) noch ohne gezählten Bezirk ist, leiht er sich den Schwung des
   anderen — und der lag 2021 um **3,3 Punkte** daneben (§1.4). Für die
   offenen Stimmen dieses Topfes kommt deshalb `(2 · 0,04 · Σ n_i)²` zur
   Varianz dazu. Ohne diesen Term war das Modell in der Kalibrierung bei
   „Briefwahl zuerst" nach zehn Bezirken in 9 % der Fälle sicher — und
   falsch. Dazu ein **Sockel**: solange weniger als **15 Bezirke** gezählt
   sind, gibt es keine Chance-Zahl, nur die Hochrechnung mit dem Vermerk
   „zu früh für eine Wahrscheinlichkeit" — mit fünf Bezirken ist `σ_r`
   selbst Zufall.
6. **Chance:** `Φ(Vorsprung ÷ σ)`, gedeckelt auf **99 %**, solange nicht
   rechnerisch entschieden. Ausgegeben als ganze Zahl; unter 15 gezählten
   Bezirken `null`.
7. **Rechnerisch entschieden** (kein Modell, eine Schranke): Der Vorsprung
   in Stimmen übersteigt die **Obergrenze** der noch offenen Stimmen. Die
   Obergrenze ist nicht die erste Wahlgang-Zahl (die kann übertroffen
   werden), sondern die **Wahlberechtigten** der offenen Bezirke — die trägt
   jede Zeile der Übersicht. Mehr Stimmen als Wahlberechtigte gibt es nicht.
   Erst dann steht „Entschieden" ohne Modell-Vorbehalt.

**Antwort** (`MayorNight`, neue optionale Felder — die App liest den Typ,
Optionales bricht sie nicht):

```python
class RunoffProjection(TypedDict):
    #: Hochgerechneter Endstand je Slug in Prozent.
    shares: dict[str, float]
    #: Hochgerechneter Vorsprung des Führenden in Stimmen.
    lead_votes: int
    leader: str
    #: Chance des Führenden in Prozent (ganze Zahl), None unter 15 Bezirken
    #: oder wenn rechnerisch entschieden (dann ist es keine Chance mehr).
    chance_pct: int | None
    #: Wie viele Bezirke das Modell gesehen hat, getrennt nach Urne und Brief.
    counted_ballot: int
    counted_postal: int
    #: Der Vorsprung übersteigt die Wahlberechtigten der offenen Bezirke.
    decided: bool
    #: Obergrenze der noch offenen Stimmen.
    open_votes_max: int
    #: Menschentext: was das Modell annimmt und was nicht.
    caveats: list[str]

class MayorNight(TypedDict):
    ...
    projection: NotRequired[RunoffProjection]
```

**Frontend** (`stichwahl.tsx`):

- Unter der Tafel eine Karte **„Hochrechnung"**: zwei große Zahlen (der
  hochgerechnete Endstand), daneben klein „nach 47 von 133 Bezirken · Urne
  41, Brief 6". Dazu eine Zeile **„Chance: Prange 71 %"** mit dem Satz
  „Modell aus dem ersten Wahlgang je Bezirk — s. ⓘ" und dem Sockel-Text,
  wenn die Chance noch fehlt. **Nie ohne das Wort „Modell"**, nie ohne die
  Bezirkszahl daneben.
- Die Karten der beiden bekommen unter dem Ist-Anteil eine zweite, kleinere
  Zeile „Hochrechnung 51,8 %".
- **„Rechnerisch entschieden"** ersetzt die Chance, sobald `decided`:
  „Ulf Prange ist gewählt — der Vorsprung von 4.120 Stimmen ist größer als
  alle Stimmen, die noch offen sind (höchstens 3.900)." Das ist der Moment
  für S4.
- ⓘ öffnet die `caveats` in einem Bottom-Sheet: „Das Modell nimmt an, dass
  jeder offene Bezirk so abstimmt wie im ersten Wahlgang, verschoben um den
  Trend der schon gezählten Bezirke — Urne und Briefwahl getrennt. Es weiß
  nichts über Wähler*innen der ausgeschiedenen Kandidaturen. Die Chance
  ist eine Modellrechnung, keine Umfrage; unter 15 Bezirken zeigen wir sie
  nicht."

**Tests** (`tests/test_runoff_model.py`, alle ohne Netz, gegen das
eingefrorene Fixture aus S1):

- Vollständig gezählt → Hochrechnung == Ist, `decided`, `chance_pct is None`.
- Die ersten 15 Urnenbezirke gezählt, mit einem künstlichen Schwung von
  +3 Punkten → Hochrechnung trifft den Endstand auf ±1 Punkt, wenn der
  Schwung überall gleich ist (das ist die Zusage des Modells).
- Nur Briefwahl gezählt → Urnen-Schwung übernimmt, `caveats` sagt es.
- 14 Bezirke → `chance_pct is None`; 15 → Zahl.
- Der Vorsprung größer als `open_votes_max` → `decided`, sonst nicht — und
  `open_votes_max` = Summe der Wahlberechtigten der offenen Bezirke.
- **Die Kalibrierung von 2021 als Test** (`tests/test_runoff_model.py::test_2021`):
  aus den beiden Fixtures die 133 Bezirke; 200 feste Reihenfolgen (Seed),
  je „zufällig", „Urne zuerst", „Brief zuerst"; nach 30 Bezirken nennt die
  Hochrechnung in JEDER den Sieger, und die Chance des späteren Siegers
  liegt nach 15 Bezirken in keiner Reihenfolge unter 50 %. Fällt das,
  ist das Modell kaputt, nicht der Abend.
- **Die Generalprobe** (`?probe=1&counted=N`) muss dieselben Zeilen liefern
  wie live — sie spielt den ersten Wahlgang bezirksweise nach; Prüfung: bei
  `counted=133` gleich dem Endstand.

**Fertig, wenn:** die Generalprobe mit `counted=20/60/100` drei glaubwürdige
Stände zeigt, die Chance dabei von „zu früh" über eine Zahl bis 99 % läuft,
und Tim das Bild abgenickt hat.

### PR S3 — Der Verlauf des Abends

- `history.py` verallgemeinern: heute nimmt es `ElectionNight` und schreibt
  `data/wahlabend-verlauf-<slug>.json`. Ein zweiter Punkt-Typ
  `MayorHistoryPoint {at, reports_received, shares, projected_shares,
  chance_pct, leader}` und `record_mayor(night)` in dieselbe Datei-Logik
  (Pfad je Wahl-Slug ist schon da).
- `MayorNight.history: list[MayorHistoryPoint]`.
- `stichwahl.tsx`: eine Linie je Kandidatur über den Abend (Ist) und
  gestrichelt die Hochrechnung; Marker bei **Führungswechseln** (Slug des
  Führenden ändert sich zwischen zwei Punkten). `verlauf.tsx` der Ratswahl
  ist die Vorlage (SVG, kein d3).
- Tests wie `test_wahlabend_verlauf.py`: gleiche Punkte werden nicht
  doppelt geschrieben, Datei überlebt `reset`, Führungswechsel erkannt.

### PR S4 — Momente und Bewegung

Was Tim meinte mit „dass da wirklich was hochgeht". Alles nach DESIGNSPRACHE
§7: Bewegung erklärt einen Zusammenhang oder fällt weg, ≤ 300 ms je Schritt,
gestaffelt gedeckelt, `prefers-reduced-motion` legt alles still.

1. **„Neu ausgezählt"** — sobald `reports_received` steigt: eine Zeile oben
   unter der Tafel, die eingleitet (`Reveal`) und nach 8 s wieder geht:
   „18:42 · **12 weitere Bezirke** ausgezählt — Prange +312, Rohr +298".
   Die Differenzen kommen aus der Historie (S3), nicht aus dem Browser-
   Zustand — sonst zeigt ein frisch geladener Tab nichts.
2. **Die Karten leuchten auf** (`useFrisch` auf `reports_received`, wie die
   Wahlbereichs-Karten der Ratswahl: `ring-2 ring-primary/40`, 1,6 s), die
   Balken gleiten (`transition-[width]`, schon da), die Prozentzahl gleitet
   (`useTween`, schon da).
3. **Führungswechsel**: die beiden Karten **tauschen den Platz** (Grid mit
   `order`, Übergang 300 ms `ease-in-out-strong`) und der Kicker „Vorn"
   wandert mit; dazu die Zeile „Führungswechsel — Rohr liegt jetzt vorn".
4. **Rechnerisch entschieden**: eine Bühne über beiden Karten — Lotti
   `hebt-pokal`, „Ulf Prange ist gewählt", der Satz mit der Schranke, in
   Signal-Orange die Zahl des Vorsprungs. Kein Konfetti: Die Designsprache
   hat kein Feuerwerk, und eine gewonnene Wahl ist für die Hälfte der Stadt
   keins.
5. **Vor 18 Uhr**: Countdown aus `zeitlage` (steht schon) plus „Was ab
   18 Uhr passiert" in drei Sätzen, Lotti `staunt`.
6. **Meldung**: kein Push, keine Browser-Notification — beides braucht
   Erlaubnis und trifft am Wahlabend Leute, die die Seite gerade offen
   haben. Die Zeile aus (1) reicht; wer den Tab im Hintergrund hat, sieht
   den Titel: `document.title` bekommt den Stand („Prange 52,1 · Rohr 47,9
   — 47/133"), das ist die billigste Meldung, die es gibt.

**Browsertest:** `15-wahlabend.spec.ts` bekommt eine Stichwahl-Gruppe mit
zwei gemockten Ständen nacheinander (`page.route` tauscht die Antwort nach
dem ersten Aufruf): die Zeile „weitere Bezirke" erscheint, die Karten
tauschen bei Führungswechsel, „Gewählt" bei `decided`.

### PR S5 — Die Karte der Stichwahl

`Gebietskarte` aus #1354, zwei Zustände:

- **Vor und während der Auszählung**: die 91 Urnenbezirke getönt nach
  `p_i` des ersten Wahlgangs — „wo Prange, wo Rohr im ersten Wahlgang vorn
  lag" (zwei Farben ist hier ausnahmsweise die Frage: Designsprache erlaubt
  Parteifarben nur als Punkte — also **eine** Primärtönung für „Prange-
  Anteil", von hell (Rohr vorn) bis kräftig (Prange vorn), Legende dazu).
- **Live**: gezählte Bezirke bekommen ihre Ist-Tönung und einen festen
  Rand, offene bleiben blass und schraffiert — man SIEHT die Auszählung
  laufen. Antippen: Bezirkstafel mit erstem Wahlgang und Stichwahl
  nebeneinander.

Kein neuer Endpunkt: Die Ist-Zahlen kommen aus S1, der erste Wahlgang aus
der eingefrorenen Datei (als statisches Asset unter `public/geo/` oder über
den Bezirks-Endpunkt mitgeliefert — Letzteres, damit die App sie auch hat).

## Anhang A — Was NICHT gebaut wird, und warum

- **Eine „Wahrscheinlichkeit" ohne Bezirksdaten.** Aus Stadtzeile plus
  Fortschrittsbalken ließe sich eine Zahl basteln; sie wäre bei σ = 8
  Punkten zwischen den Bezirken eine Erfindung.
- **Eine Prognose, die mehr behauptet als die Kalibrierung hergibt.** Es
  gibt EINE geprüfte Stichwahl (2021, §1.4), und die war mit 54 : 46 nicht
  knapp. Dass das Modell dort in jeder Reihenfolge nach 30 Bezirken richtig
  lag, heißt nicht, dass es bei 50,5 : 49,5 richtig liegt. Die Seite sagt
  deshalb „Modell" und nennt die Bezirkszahl daneben — und die Chance ist
  bei 99 % gedeckelt, bis die Arithmetik entschieden hat.
- **Push oder Browser-Benachrichtigungen.** S4 (6).
- **Konfetti.** S4 (4).

## Anhang B — Zeit

Alles vor dem **27.09.**, mit Reserve: S1 + S2 bis 20.09., S3 + S4 bis
24.09., S5 danach, wenn es reicht. Am **26.09.** Generalprobe mit
`?probe=1&counted=20`, `60`, `133` und Bild an Tim.

## Anhang C — Die Befehle hinter den Zahlen

```bash
# Welche Ebenen die OB-Präsentation hat (wahl.json), und die 133 Bezirke in EINEM Abruf
B=https://votemanager.kdo.de/20260913/03403000/daten/api/wahl_2552
curl -s $B/wahl.json | python3 -c "import json,sys;print([(l['title'],l['type'],l['id']) for l in json.load(sys.stdin)['menu_links']])"
curl -s $B/uebersicht_ebene_6_0.json | python3 -c "
import json,sys;u=json.load(sys.stdin);t=u['tabelle'];print(len(t['zeilen']),'Zeilen');print([h['labelKurz'] for h in t['header']][:8]);print(json.dumps(t['zeilen'][0],ensure_ascii=False)[:400])"

# Streuung des ersten Wahlgangs je Bezirk (web/backend, mit venv)
../../.venv/bin/python - <<'EOF'
import requests, statistics
from app.election import presentation, crosscheck
B="https://votemanager.kdo.de/20260913/03403000/daten/api/wahl_2552"
s=requests.Session()
links=presentation.area_links(s.get(f"{B}/uebersicht_ebene_6_0.json").json())
w=[]
for label,gid in links:
    rows=presentation._rows(s.get(f"{B}/ergebnis_{gid}_0.json").json()["Komponente"]["tabelle"])
    d={crosscheck.label_of(z) or "": presentation.parse_number(z.get("zahl")) for z in rows if isinstance(z,dict)}
    pr=next(v for k,v in d.items() if "Prange" in k); ro=next(v for k,v in d.items() if "Rohr" in k)
    w.append((label,pr,ro))
z=[p/(p+r) for _,p,r in w]
print("σ %.1f min %.1f max %.1f" % (100*statistics.pstdev(z),100*min(z),100*max(z)))
for name,teil in (("Urne",[x for x in w if "Brief" not in x[0]]),("Brief",[x for x in w if "Brief" in x[0]])):
    print(name, len(teil), "%.1f" % (100*sum(p for _,p,_ in teil)/sum(p+r for _,p,r in teil)))
EOF
# → 133 Bezirke; σ 8,0; min 34,8; max 72,8; Urne 91 → 53,7 %; Brief 42 → 48,9 %

# Die Stichwahl 2021 (alte API): Ids aus termin.json, Bezirke aus der Übersicht
B21=https://votemanager.kdo.de/20210912/03403000/api/praesentation
curl -s $B21/termin.json | python3 -c "import json,sys,re;print(re.findall(r'\"id\": ?(\d+)[^}]*?\"titel\": ?\"([^\"]{0,60})', json.dumps(json.load(sys.stdin),ensure_ascii=False)))"
# → 223 „Wahl des/der Oberbürgermeisters/in", 224 „Stichwahl …", 222 Stadtratswahl
curl -s $B21/wahl_224/uebersicht_ebene_6_0.json | python3 -c "
import json,sys;t=json.load(sys.stdin)['tabelle'];print([h['labelKurz'] for h in t['header']]);z=[z for z in t['zeilen'] if z['label'][:1].isdigit()][0];print(len(z['felder']),'felder  ←  header hat',len(t['header']))"
# → ['Wahlbezirk','Stand','Wahlberechtigte','Wahlbeteiligung','gültig','Krogmann, SPD','Fuhrhop, GRÜNE']; 5 felder ← header hat 7
# Die Kalibrierung selbst (Schwünge, σ, 300 Reihenfolgen) steht als Skript im
# Verlauf dieses Plans (14.09.2026) und wird in PR S2 zum Test.
```
