# Umsetzungsplan Phase 5: das „Warum" aus den Protokollen — und welche Stadt als Nächstes

Stand: 10.09.2026, abends. Dieser Plan folgt auf
[`plan-cities-phase4.md`](plan-cities-phase4.md) (PR 23–30, alle gemergt)
und ist wie seine Vorgänger geschrieben: **ohne das Gespräch dahinter
ausführbar**. Jeder Abschnitt ist ein Pull Request, nennt Dateien,
Signaturen, Tests, Kosten und woran man erkennt, dass er fertig ist. Wo etwas
gemessen ist, steht die Zahl und in Anhang C der Befehl, der sie liefert.

**Nachtrag vom 10.09.2026, abends.** Tim hat nach dem ersten Entwurf gesagt,
er hätte gern **auch niedersächsische Städte** dabei — es gebe in
Niedersachsen ja ohnehin kaum große Städte wie Oldenburg. Daraufhin ist §2.3
neu gemessen worden, und der erste Befund („in Niedersachsen gibt es nichts
zu holen") hat sich als **falsch** herausgestellt: Er kam von einer Suche
über Adressmuster, die die tatsächlich benutzten Hosts nicht kannte. §2.3, §3
und die PRs 35–38 sind daraufhin neu geschrieben.

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
24. **Niedersachsen zuerst** (Tims Nachtrag vom selben Abend): *„Ich glaube,
    es würde sich lohnen, auch noch ein paar Städte aus Niedersachsen
    dazuzunehmen. Also in Niedersachsen gibt es ja gar nicht so viele andere
    große Städte wie Oldenburg. Wenn wir dann noch welche dazunehmen
    könnten, wäre das ganz super."* Bei gleichem Nutzen gewinnt die
    niedersächsische Stadt — gleiches Landesrecht heißt, die Entscheidung
    ist im Oldenburger Ratssaal zitierfähig.
25. **Mindestens die fünf größten niedersächsischen Städte** (Tim,
    10.09.2026, spät): *„Falls du meinst, dass Inhalte fehlen, also andere
    Städte, würde ich mir wünschen, mindestens die fünf größten Städte noch
    in Niedersachsen mit dazuzunehmen."* Nach Braunschweig, Oldenburg und
    Osnabrück sind das **Hannover, Göttingen, Wolfsburg, Salzgitter und
    Hildesheim**. Keine davon hat eine funktionierende Schnittstelle — §2.3
    und §3 sagen, was das je Stadt heißt. Der Wunsch ändert die Reihenfolge
    des Plans, nicht seine Regeln: kein Umweg um eine Sperre, kein Adapter
    ohne Fixture.

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
  │ C  Oldenburgs eigene Seite     │ │ D  Drei neue Städte in NIEDER- │
  │    liefert denselben Absatz,   │ │    SACHSEN — gleiches Recht,   │
  │    damit man vergleichen kann  │ │    zitierfähig im Ratssaal     │
  │    (PR 34)                     │ │    (PR 35, 36) + Bonn (37)     │
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

### 2.3 Niedersachsen — die erste Messung war zu pessimistisch

Tims erstes Kriterium ist Vergleichbarkeit, und die beste Vergleichbarkeit
ist dieselbe Rechtslage: Niedersachsen. NKomVG, Straßenausbaubeiträge,
Verpackungssteuer, Ortsräte, die Zuständigkeit des Verwaltungsausschusses —
alles im selben Landesrecht. Eine Kölner Entscheidung ist interessant, eine
Lüneburger ist im Ratssaal in Oldenburg **zitierfähig**.

Die erste Runde suchte über acht Adressmuster (`<stadt>.sitzung-online.de`,
`ratsinfo.<stadt>.de`, …) und fand null. Das war ein Fehler der Methode, nicht
der Wirklichkeit: Die Muster kannten die Hosts nicht, die die Städte
tatsächlich benutzen. Die zweite Runde ging deshalb über die **Rathaus-Seiten**
— erst den RIS-Link finden, dann dort OParl probieren. Ergebnis (10.09.2026,
31 niedersächsische Städte ab 28 k):

**A — OParl läuft und liefert:**

| Stadt | Einw. | RIS | Endpunkt | Vorlagen ≥ 2024 | Beratung | Protokoll | Lizenz |
|---|---:|---|---|---:|---|---|---|
| Braunschweig | 250 k | ALLRIS 4 | aktiv im Register | — | — | 218 | — |
| Osnabrück | 165 k | ALLRIS 4 | aktiv im Register | — | — | 281 | — |
| **Langenhagen** | 56 k | ALLRIS 4 | `www.langenhagen.sitzung-online.de/oparl/system` | 268 | **5/5** | **4/8** | **CC BY 4.0** |
| **Peine** | 50 k | ALLRIS 4 | `ratsinfo.stadt-peine.de/public/oparl/system` | 2.579 | 4/5 | 0/8 | **CC BY 4.0** |

Langenhagen antwortet in 1,2 s, führt 3.864 Sitzungen und trägt an vier von
acht geprüften Sitzungen eine Niederschrift — es ist damit **die einzige
niedersächsische Stadt außer Braunschweig und Osnabrück, die alles hat, was
diese Phase braucht.** Peine hat mehr Vorlagen, aber keine Protokolle.

**B — OParl ist da, antwortet aber nicht** (der Betreiber muss einen Schalter
umlegen; kein Code hilft):

| Stadt | Einw. | RIS | Befund |
|---|---:|---|---|
| Wolfsburg | 125 k | ALLRIS 4 | `/oparl/system` liefert sauberes JSON (CC BY 4.0) — `/oparl/bodies` und **jede** Liste dahinter: HTTP 500 |
| Lüneburg | 75 k | ALLRIS 4 | `/public/oparl/system` → HTTP 500 (die Route gibt es, sie stürzt ab) |
| Laatzen | 43 k | ALLRIS 4 | ebenso |
| Lingen | 58 k | SD.NET RIM 4 | `{"error":"Webservice \"OParl\" ist nicht aktiviert!","code":100}` |
| Nordhorn | 54 k | SD.NET RIM 4 | dieselbe Meldung |
| Cuxhaven | 48 k | SD.NET RIM 4 | dieselbe Meldung |
| Verden | 28 k | SD.NET RIM 4 | dieselbe Meldung |

Die SD.NET-Meldung ist wörtlich zitiert und der wichtigste Satz dieses
Abschnitts: **Der OParl-Dienst ist im Produkt eingebaut und lediglich
abgeschaltet.** Vier niedersächsische Städte sind eine Anfrage weit entfernt,
nicht einen Adapter. Bei den drei ALLRIS-4-Fällen sieht es nach einer
kaputten Konfiguration aus — Wolfsburg (125 k!) wäre der Fang.

**C — nur HTML, kein OParl:**

| Stadt | Einw. | RIS | Bemerkung |
|---|---:|---|---|
| Hannover | 535 k | SIM (Lotus Notes) | `e-government.hannover-stadt.de/lhhsimwebre.nsf` — eigene Welt |
| Göttingen | 120 k | ALLRIS classic | `ris.goettingen.de` hinter Cloudflare, antwortet uns mit 403 |
| Salzgitter | 105 k | ALLRIS net 3.9 | `sitzungsdienst.salzgitter.de/buergerinfo/si010.asp` |
| **Hildesheim** | 100 k | ALLRIS classic | `www.stadt-hildesheim.de/allris/si010_e.asp` — **gemessen lesbar**: 13 Sitzungen im Kalender, `to010.asp` liefert 8 Tagesordnungspunkte mit Vorlagen |
| Delmenhorst | 78 k | ALLRIS classic | `sitzungsdienst-delmenhorst.de/bi-r/si010_r.asp` — Kalender lesbar, `to010_r.asp` braucht die `_r`-Schreibweise |
| Celle | 70 k | ALLRIS classic | `www.celle.de/allris/` |
| Hameln | 58 k | SD.NET | `ris.hameln.de/ris` |
| Wilhelmshaven | 76 k | SD.NET (gehostet) | `ratsinfoservice.de/ris/wilhelmshaven` — von hier aus Zeitüberschreitung |
| Emden, Aurich, Nienburg | 50/42/32 k | **SessionNet** | dasselbe Produkt wie Oldenburg (`buergerinfo.oldenburg.de/info.php`) |

Für Garbsen, Wolfenbüttel, Goslar, Stade, Melle, Uelzen und Neustadt a. Rbge.
war auf der Rathaus-Seite kein RIS-Host zu finden; sie sind nicht geprüft,
nicht ausgeschlossen.

**D — die Vollerhebung, 340 Kommunen ab 5.000 Einwohnern** (10.09.2026,
spät). Jede einzeln über ihre Website nachgesehen — Startseite, bis zu zwanzig
Politik-Unterseiten, ein Dutzend direkter Adressen auf der eigenen Domain —
und jeder Fund einmal aufgerufen. Das Bild kippt gegenüber der
Domain-Suche:

| Befund | Kommunen | Einwohner |
|---|---:|---:|
| OParl antwortet | **11** | 355.000 |
| OParl da, aber abgeschaltet | 39 | 642.000 |
| keine Schnittstelle | 154 | 2.900.000 |
| kein System gefunden | 136 | 2.700.000 |

| Programm | Kommunen | davon OParl an |
|---|---:|---:|
| SessionNet (SOMACOS) | **140** | 5 |
| ALLRIS (CC e-gov) | 27 + 7 (ALLRIS 4) | 4 |
| SD.NET RIM (STERNBERG) | 21 | 2 |
| more! rubin, regisafe, Provox | 4 / 3 / 1 | — |
| SIM, Eigenbau auf Notes/Domino (nur Hannover) | 1 | — |

**145 von 203 Systemen laufen auf einer eigenen Domain der Kommune** — für
jede domainbasierte Suche unsichtbar. SessionNet beherrscht Niedersachsen mit
69 %, war in Gruppe A–C aber massiv unterzählt. Zwei regionale Betreiber, die
in keiner Herstellerliste stehen: **ITEBO Osnabrück** (`<gemeinde>ris.itebo.
de`, 12 Kommunen, zwei davon mit OParl an: Twist, Norderney) und **OWL-IT**
(7). Die elf mit funktionierendem OParl sind entweder schon im Vergleich oder
unter 56.000 Einwohnern.

**„Abgeschaltet" heißt nicht „gesperrt".** Nachgemessen an fünf Systemen
(Lingen, Nordhorn, Wolfsburg, Lüneburg, Laatzen): **kein einziges** schickt
eine Anmelde-Aufforderung (`WWW-Authenticate`). SD.NET antwortet HTTP 400 —
„ungültige Anfrage", nicht 401/403 — mit dem Satz, das Modul sei nicht
aktiviert; ALLRIS 4 antwortet HTTP 500, ein Serverfehler auf einer Route, die
es gibt. Ein Zugang würde nichts ändern, und er ist auch nicht vorgesehen:
OParl ist per Spezifikation *anonymer, lesender* Zugriff auf **öffentliche**
Inhalte. Was fehlt, ist eine Entscheidung der Kommune, das Modul beim
Hersteller freizuschalten — und was das kostet, sagen weder Sternberg noch das
OParl-Projekt öffentlich; dessen FAQ verweist auf die Verträge. Die Anfrage ist
also eine E-Mail, die Antwort kann ein Angebot sein.

**Was daraus folgt.** Vergleichbarkeit über das Landesrecht ist zu haben —
nur nicht geschenkt. Es gibt drei Wege, und dieser Plan geht zwei davon:
Langenhagen und Peine sofort (PR 35), einen HTML-Adapter für die
Größenklasse von Oldenburg (PR 36), und die Anfragen an die sieben Städte aus
Gruppe B sind eine Sache für Tim, nicht für Code (Anhang B).

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

Sechs Kriterien, in der Reihenfolge, in der sie für Tims Frage zählen:

1. **Dieselbe Rechtslage** — Niedersachsen. Tim am 10.09.: *„Ich glaube, es
   würde sich lohnen, auch noch ein paar Städte aus Niedersachsen
   dazuzunehmen. Es gibt ja gar nicht so viele andere große Städte wie
   Oldenburg."* Eine Entscheidung unter demselben NKomVG ist im Oldenburger
   Ratssaal zitierfähig; eine Kölner ist es nicht.
2. **Niederschriften erreichbar** — ohne sie kein „Warum", der Auftrag
   dieser Phase.
3. **Beratungsfolge an der Vorlage** — ohne sie kein Ergebnis (Phase 4,
   PR 27: 5.224 Vorlagen hingen daran).
4. **Größe und Typ** — 50–350 k, kreisfrei oder Oberzentrum.
5. **Adapter vorhanden** — ALLRIS 4 und SessionNet sind gebaut und je an
   zwei bis drei Städten bewährt; RUBIN (`adapters/rubin.py`, 90 Zeilen) hat
   noch nie eine echte Stadt gesehen, ALLRIS-**HTML** gibt es gar nicht.
6. **Lizenz und Tempo** — eine genannte Lizenz spart die Rückfrage;
   12 Sekunden je Aufruf machen aus einer Ernte einen Tag.

| Rang | Stadt | Land | Warum | Was dagegen spricht |
|---|---|---|---|---|
| **1** | **Langenhagen** | **NI** | Die einzige weitere niedersächsische Stadt mit **funktionierendem OParl UND Niederschriften** (4/8). Beratung 5/5, CC BY 4.0, 1,2 s, ALLRIS 4 — der Adapter steht. Kostet fast nichts. | 56 k — ein Drittel von Oldenburg, Umlandstadt von Hannover, kein Oberzentrum. |
| **2** | **Hildesheim** | **NI** | **100 k, kreisfrei, Oberzentrum — die Oldenburg ähnlichste Stadt in ganz Niedersachsen, die wir haben können.** ALLRIS-HTML ist gemessen lesbar. | Braucht den fünften Adapter (PR 36). Kein Vertrag, keine Lizenz, keine Zusage — HTML kann sich jederzeit ändern. |
| **3** | **Bonn** | NW | Als **einziger Nicht-NI-Kandidat Niederschriften an 6 von 8 Sitzungen** (wie Münster). ALLRIS 4, Open Data, 2 s, 330 k. Liefert PR 31–33 die dritte Protokollquelle. | Anderes Landesrecht. Die Abfrage mit `created_since` brach in der Probe — Dialekt-Detail, vor der Ernte klären. |
| **4** | **Peine** | **NI** | OParl läuft, 2.579 Vorlagen seit 2024, Beratung 4/5, CC BY 4.0, ALLRIS 4. Mitgenommen, solange PR 35 ohnehin läuft. | 50 k, Mittelstadt, **keine Protokolle** — trägt zum „Warum" nichts bei. |
| **5** | **Göttingen / Salzgitter / Delmenhorst** | **NI** | 120 / 105 / 78 k, alle drei ALLRIS classic — mit dem Adapter aus PR 36 kosten sie je einen Registry-Eintrag und eine Probe. | Göttingen sperrt uns per Cloudflare aus (403), Delmenhorst schreibt `_r` an jede Seite, Salzgitter antwortete von hier gar nicht. Je einzeln zu klären. |
| 6 | Darmstadt | HE | 165 k, exakt Oldenburgs Größe, Beratung 5/5, 20.596 Vorlagen. Prüft `rubin.py` zum ersten Mal an einer echten Stadt und macht Freiburg danach billig. | RUBIN/OParl 1.0, keine Protokolle, keine Lizenz, 9 s. Anderes Landesrecht. |
| 7 | Leipzig | SN | CC BY 4.0, 9.268 Vorlagen, ALLRIS 4, Protokolle 2/8. | 620 k, Landeshauptstadt-Maßstab. |
| 8 | Freiburg | BW | 235 k, Beratung 5/5, 13.959 Vorlagen. | RUBIN, keine Protokolle, keine Lizenz, 11 s. Erst nach Darmstadt. |
| 9–12 | Köln, Dresden, Wuppertal, Düsseldorf | NW/SN | SessionNet, Adapter vorhanden, Beratung 5/5. | Keine Protokolle, 360 k–1,1 Mio., 2–13 s. Bringen dieser Phase nichts. |

**Das Ziel ist mit Regel 25 gesetzt: die fünf größten niedersächsischen
Städte nach den dreien, die schon drin sind.** Keine von ihnen hat eine
funktionierende Schnittstelle, und deshalb ist jede ein anderer Weg:

| Stadt | Einw. | System | Schnittstelle | Weg |
|---|---:|---|---|---|
| **Hannover** | 548 k | Eigenbau, Notes/Domino | keine — aber RSS + iCal | **PR 39**: eigener Adapter, die Feeds als Einstieg |
| **Göttingen** | 131 k | ALLRIS classic (HTML) | keine; **sperrt uns per Cloudflare aus** | PR 36 — nur, wenn die Stadt die Sperre öffnet; sonst Anfrage (Anhang B) |
| **Wolfsburg** | 127 k | ALLRIS 4 | **da, kaputt** (HTTP 500 hinter `system`) | eine Nachricht an die Stadt (Anhang B); danach ein Registry-Eintrag |
| **Salzgitter** | 105 k | ALLRIS net 3.9 (HTML) | keine; **antwortete von hier nicht** | PR 36 — nach einer Probe von einem anderen Netz; sonst Anfrage |
| **Hildesheim** | 102 k | ALLRIS classic (HTML) | keine | **PR 36**, gemessen lesbar — die Stadt, an der der Adapter gebaut wird |

**Empfehlung, in dieser Reihenfolge:** Langenhagen und Peine (PR 35, ein
halber Tag, sie sind die einzigen mit funktionierendem OParl); dann
**Hildesheim über PR 36** und mit demselben Adapter Göttingen und Salzgitter,
sobald die beiden Sperren geklärt sind; parallel die Anfrage an Wolfsburg;
zuletzt **Hannover (PR 39)**, weil es die meiste eigene Arbeit ist und
zugleich die am wenigsten mit Oldenburg vergleichbare Stadt. Bonn (PR 37) und
Darmstadt (PR 38) bleiben im Plan, rücken aber hinter die fünf.

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

## PR 35 — Zwei niedersächsische Städte, die uns schon offenstehen

**Warum.** §3, Kriterium 1. Langenhagen und Peine sprechen OParl 1.1 über
ALLRIS 4 — **denselben Dialekt, den `adapters/allris4.py` für Osnabrück und
Braunschweig schon fährt.** Beide nennen CC BY 4.0. Langenhagen trägt
Niederschriften an vier von acht Sitzungen und ist damit die dritte Quelle
für PR 31–33 unter niedersächsischem Recht. Das ist der billigste Schritt in
diesem ganzen Plan.

**Was sich ändert.** Zwei Registry-Einträge in `council/cities/registry.py`
und sonst — wenn alles gut geht — nichts:

```python
"langenhagen": BodySpec("langenhagen", "Langenhagen", "NI", "allris4",
                        "https://www.langenhagen.sitzung-online.de/oparl/system"),
"peine":       BodySpec("peine", "Peine", "NI", "allris4",
                        "https://ratsinfo.stadt-peine.de/public/oparl/system"),
```

Dann Schritt für Schritt das Rezept aus `council/cities/CLAUDE.md`, **kein
Schritt ausgelassen**:

1. Eintrag mit `active=False`.
2. Kurzes Fenster ernten: `--run --body langenhagen --since 2025-01-01
   --stage fetch --stage normalize`.
3. `cities_backfill.py --pruefen` — Plausibilitätsbänder und unbekanntes
   Ergebnis-Vokabular.
4. Was das Vokabular meldet, nach `model._OUTCOME_RULES`. Peines
   Vorlagenarten sind noch ungemessen (die Probe bekam die Liste nicht
   vollständig); Langenhagen führt „Beschlussdrucksache",
   „Informationsdrucksache", „Antrag öffentlich", „Ratsanfrage" — der Abgleich
   mit `model.IDEA_KINDS` gehört in denselben Schritt.
5. Fixtures `tests/fixtures/cities/langenhagen_papers.json` und
   `peine_papers.json` aus echten Rohobjekten, gekürzt, ohne Personen;
   Eintrag in `STAEDTE` in `tests/test_cities_adapters.py`.
6. Erst dann `active=True`, volle Historie, Stufen in der Reihenfolge, die
   `cities_backfill.py --stage fit` seit PR 25 erzwingt.

**Wo es klemmen kann.** Peine liefert seine Vorlagenliste über
`/public/oparl/…`, Langenhagen ohne das `public`. Beide Male löst der Client
die Adressen aus `system` → `body` auf, es ist also kein Sonderfall — aber
falls doch: in `adapters/allris4.py`, nie in eine
`if body_id == "peine"`-Bedingung.

**Messung.** `--pruefen` ohne Befund; Anteil Vorlagen mit Ergebnis
(Osnabrück nach PR 27: 80 %, Braunschweig 47 %); für Langenhagen zusätzlich
Sitzungen mit Protokoll-Text aus PR 31. Fertig, wenn beide in
`cities_bilanz.py` stehen und die Karte niedersächsische Ideen zeigt, die
nicht aus Braunschweig oder Osnabrück kommen.

**Kosten.** Langenhagen 268 Vorlagen seit 2024, Peine 2.579 — zusammen
classify < $1, `fit` über die Übertragbaren < $2. **Unter $3.**

## PR 36 — Der fünfte Adapter: ALLRIS über die Oberfläche, gemessen an Hildesheim

**Warum.** Das ist der Preis für Tims eigentliche Frage. In Niedersachsen
gibt es außer Braunschweig, Osnabrück, Langenhagen und Peine **keine** Stadt
mit brauchbarem OParl — aber es gibt Hildesheim (100 k, kreisfrei,
Oberzentrum), Göttingen (120 k), Salzgitter (105 k), Delmenhorst (78 k) und
Celle (70 k), und alle fünf fahren **ALLRIS classic** mit denselben
`.asp`-Seiten. Ein Adapter, fünf Städte, alle unter demselben NKomVG.

Gemessen an Hildesheim (`www.stadt-hildesheim.de/allris/`, 10.09.2026):
`si010_e.asp` liefert den Sitzungskalender mit 13 Sitzungen,
`to010.asp?SILFDNR=…` die Tagesordnung mit 8 Punkten und den Vorlagen daran.
Die Seiten sind serverseitig gerendert, ohne JavaScript, in `windows-1252`.

**Was sich ändert.** Neues Modul `council/cities/adapters/allris_html.py`,
Dialekt `"allris_html"`. Es hat dieselbe Aufgabe wie die vier vorhandenen
Adapter und liefert dieselben Objekte (`Batch` aus `model.py`) — nur ist die
Quelle HTML statt JSON:

```python
def fetch(spec: BodySpec, client, since: str) -> None
    # si010_*.asp?YY=<jahr> → Sitzungen; to010*.asp?SILFDNR= → Tagesordnung
    # vo020*.asp?VOLFDNR=   → Vorlage samt Beratungsfolge
    # getfile.asp?id=…      → PDF; ROH ablegen wie jeder andere Adapter

def normalize(body_id: str, raw: CitiesStore) -> Batch
```

Drei Regeln, die aus der Messung kommen:

- **Die Schreibweise ist je Stadt anders.** Hildesheim `si010_e.asp` /
  `to010.asp`, Delmenhorst `si010_r.asp` / `to010_r.asp`. Das gehört als
  **Feld in den `BodySpec`** (`html_suffix: str = ""`), nicht in eine
  Bedingung im Code.
- **Rohobjekte bleiben roh.** Der Adapter legt die HTML-Seite als
  `raw_objects`-Zeile ab, genau wie ein OParl-Adapter sein JSON. Sonst ist
  ein zweiter Lauf nach einer Parser-Korrektur ein zweiter Abruf bei der
  Stadt — und die Erfahrung aus Phase 1 sagt, dass es mehrere Korrekturen
  gibt.
- **Kennungen sind Zahlen, keine URLs.** OParl-Städte haben stabile
  `id`-URLs; hier gibt es `VOLFDNR=19175`. Die Kennung wird
  `https://<host>/vo/<n>` — synthetisch, aber stabil und im selben Format wie
  überall sonst, damit `link_by_title` und die Clusterung nichts merken.

**Test.** `tests/fixtures/cities/hildesheim_si010.html` und
`hildesheim_to010.html` — echte, gekürzte Seiten **ohne Personennamen**
(Ratsmitglieder dürften genannt werden, Einwohnerfragestunden nicht; im
Zweifel schwärzen). Der Test prüft: Anzahl Sitzungen, Anzahl
Tagesordnungspunkte, die Zuordnung Punkt → Vorlage, und dass zwei Läufe
dasselbe ergeben (`test_normalize_ist_idempotent` als Vorbild).

**Wo es klemmen kann, und was dann gilt.** Göttingen antwortet uns mit
HTTP 403 (Cloudflare), Salzgitter und Wilhelmshaven von hier gar nicht.
Das ist **kein** Fall für einen Umweg über den Heim-Proxy und **kein** Fall
für einen anderen User-Agent: Wer eine Stadt gegen ihren Willen liest, hat
das Projekt beschädigt, nicht die Stadt. Wenn eine Stadt uns aussperrt,
steht sie in der Registry mit `active=False` und einer Notiz, und Tim
entscheidet, ob er anfragt.

**Messung.** Für Hildesheim: Sitzungen im Fenster, Tagesordnungspunkte je
Sitzung, Vorlagen mit Beratungsfolge, Vorlagen mit Ergebnis — jeweils gegen
eine **von Hand gezählte** Sitzung (Regel: kein Test gegen die eigene
Fixture). Fertig, wenn `--pruefen` schweigt und der Anteil Vorlagen mit
Ergebnis ≥ 60 % liegt.

**Göttingen und Salzgitter gehören dazu — mit einer Bedingung.** Beide
fahren ALLRIS classic und sind mit Regel 25 gesetzt; beide haben sich in der
Messung aber verweigert: Göttingen mit HTTP 403 (Cloudflare), Salzgitter mit
Zeitüberschreitungen. Bevor einer der beiden in die Registry kommt, braucht es
eine **Probe von einem anderen Netz** (die Sperre kann gegen das Netz gerichtet
sein, aus dem wir messen, nicht gegen uns). Antwortet die Stadt dann, ist sie
ein Registry-Eintrag mit `html_suffix` und eine Fixture. Antwortet sie nicht,
steht sie in Anhang B — als Anfrage, nicht als Umgehung.

**Kosten.** Der Adapter: zwei bis drei Tage. Hildesheim ernten und
klassifizieren: < $5. Göttingen und Salzgitter danach je ein halber Tag und
< $5, Delmenhorst und Celle ebenso — aber je einzeln zu entscheiden, in
eigenen PRs.

## PR 37 — Bonn

**Warum.** §3, Rang 3. Und weil Bonn Niederschriften an sechs von acht
Sitzungen hat — PR 31–33 bekommen damit eine weitere Quelle neben Münster,
den drei ALLRIS-Städten und Langenhagen.

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

## PR 38 — Darmstadt, und damit `rubin.py`

**Warum.** Oldenburgs Größe auf den Einwohner genau, und der erste Ernstfall
für den vierten Adapter. Freiburg wird danach ein Registry-Eintrag.

**Was sich ändert.** Dasselbe Rezept wie PR 37. Dazu, weil OParl 1.0:
`rubin.py` gegen die Abweichungen von 1.1 prüfen (die Registry-Notiz zu
Freiburg sagt: „Volltext liegt im Dateiobjekt"). Erwartung aus der Probe:
Beratung an 5 von 5 Vorlagen, keine Protokolle — PR 31 liefert für Darmstadt
also nichts, und das ist in Ordnung.

**Messung.** Wie PR 37. Fertig, wenn `rubin.py` ein Fixture aus echten
Darmstädter Rohobjekten trägt und `--pruefen` schweigt.

**Kosten.** < $10.

## PR 39 — Hannover, der Eigenbau

**Warum.** Regel 25, und weil Hannover mit 548.000 Einwohnern die Hälfte
aller Ratsvorlagen Niedersachsens beisteuern dürfte. Es fährt **keines der
vier Programme**, sondern ein eigenes „Sitzungsmanagement" (SIM) auf
Notes/Domino unter `e-government.hannover-stadt.de/lhhsimwebre.nsf`. Der
Website-Suche ist es komplett entgangen — `hannover.de` baut seine Verweise
per JavaScript, im ausgelieferten Quelltext steht kein Link darauf.

**Zwei Fallen, beide gemessen (10.09.2026).** Erstens: `/oparl/system`
antwortet dort mit **Status 200** — und liefert die Startseite der Stadt.
Eine weiche 404; wer nur den Statuscode prüft, zählt Hannover als
„Schnittstelle vorhanden". Nur die Prüfung auf `oparlVersion` im Rumpf
entlarvt das. Zweitens: Die Seiten tragen eine `SessionID` in der Adresse
(`TermineAktuell.xsp?SessionID=…`) — der Adapter darf sie nicht in Kennungen
übernehmen.

**Was Hannover hat, das sonst niemand hat.** Vier maschinenlesbare Feeds
ohne OParl, alle unter `…/lhhsimwebre.nsf/`:

| Feed | Inhalt | gemessen |
|---|---|---|
| `RSS_Sitzungen.xml` | Sitzungen mit Tagesordnung, rollendes Zwei-Wochen-Fenster | 5 kB |
| `RSS_Drucksachen_Rat.xml` | neue Vorlagen des Rates: Titel, Nummer, Einreicher, beratende Gremien | 7 Einträge |
| `RSS_Drucksachen_STBR.xml` | dasselbe für die 13 Stadtbezirksräte | — |
| `Sitzungen.ics` | alle Termine als iCal, je mit stabiler Dokumentadresse | **276 Termine**, 194 kB |

Die Dokumentschlüssel sind lesbar und stabil: `/TM/20260907_AGleich` ist die
Sitzung des Gleichstellungsausschusses vom 7.9.2026. Dazu die Seiten
`DrucksachenAktuell.xsp` (neue Vorlagen mit Nummer, Typ, Gremium),
`Ausschuesse.xsp`, `Kalender.xsp`, `Suche.xsp`.

**Was sich ändert.** Neues Modul `council/cities/adapters/sim_hannover.py`,
Dialekt `"sim"`. Der Einstieg sind die Feeds, nicht die Oberfläche: `Sitzungen.
ics` liefert die Sitzungen samt Dokumentadresse, `RSS_Drucksachen_*` die neuen
Vorlagen; von dort folgt der Adapter den Dokumentadressen und legt die
HTML-Seiten **roh** ab (dieselbe Regel wie in PR 36). Die Beratungsfolge steht
auf der Drucksachen-Seite („Gremien: Ausschuss für …, Sozialausschuss,
Verwaltungsausschuss") und muss gegen die Sitzungen aufgelöst werden — das ist
die Arbeit, die den Adapter von einem Feed-Leser unterscheidet.

**Was vorher zu klären ist.** Ob die Feeds auch den **Bestand** hergeben oder
nur das Neue: Der Sitzungs-RSS ist ein Zwei-Wochen-Fenster, das iCal führt 276
Termine — wie weit zurück, sagt die Messung noch nicht. Reicht es nicht,
braucht die Historie `Kalender.xsp` und `Suche.xsp`, und die sind XPages mit
Sitzungsstatus — der teuerste Teil. **Erst messen, dann bauen.**

**Test.** Fixture aus einem echten RSS-Eintrag und einer gekürzten
Drucksachen-Seite (ohne Personennamen; Einreicher sind Fraktionen, die
dürfen stehen). Der Test prüft die Auflösung „Gremien"-Zeile → Sitzungen.

**Messung.** Vorlagen mit Beratungsfolge, Vorlagen mit Ergebnis, Anteil
Sitzungen mit Protokoll — dieselben Größen wie überall, gegen eine von Hand
gezählte Sitzung. Fertig, wenn `--pruefen` schweigt und Hannover in
`cities_bilanz.py` steht.

**Kosten.** Drei bis vier Tage — der größte Einzelposten des Plans, für eine
Stadt. Ernte und Einordnung: rund 10.000 Vorlagen im Jahr, davon der Großteil
aus den Stadtbezirksräten → classify ~$3, `fit` < $10.

## Anhang A — Reihenfolge, Aufwand, Kosten

| PR | Was | hängt an | Aufwand | Modellkosten |
|---|---|---|---|---:|
| 31 | Niederschriften holen | — | ½ Tag + Laufzeit | 0 |
| 32 | Niederschriften aufschneiden + Prüfstand | 31 | 2 Tage | 0 |
| 33 | Das „Warum" + Karte | 32 | 2 Tage | < $1 |
| 34 | Oldenburgs Seite | 33 | 1 Tag | < $1 |
| **35** | **Langenhagen + Peine (NI, OParl)** | — (parallel) | **½ Tag + Laufzeit** | **< $3** |
| **36** | **Adapter `allris_html`, Hildesheim (NI)** | 35 | **2–3 Tage** | **< $5** |
| **36b** | **Göttingen, Salzgitter** (nach Probe von anderem Netz) | 36 | je ½ Tag | je < $5 |
| 37 | Bonn | — (parallel) | 1 Tag + Laufzeit | < $10 |
| 38 | Darmstadt / `rubin.py` | 37 | 1–2 Tage | < $10 |
| **39** | **Hannover, Eigenbau (Feeds + Domino-HTML)** | — | **3–4 Tage** | < $15 |

31 → 32 → 33 → 34 ist die Kette, die das „Warum" liefert. 35 und 37 hängen an
nichts und sollten parallel laufen: Beide bringen Protokollquellen, die 32
zum Messen braucht. 36 ist der einzige größere Brocken — und der einzige Weg
zu einer niedersächsischen Stadt in Oldenburgs Größe. 38 erst nach 37.

**Wenn die Zeit nicht für alles reicht**, ist die Reihenfolge nach Nutzen:
35 (ein halber Tag für zwei NI-Städte), dann 31–33 (das „Warum"), dann 36
(Hildesheim) und 36b, dann 39 (Hannover), dann 37/38. Die Anfrage an
Wolfsburg (Anhang B) kostet keine Entwicklungszeit und gehört an den Anfang.

Zusammen: fünfzehn bis achtzehn Arbeitstage, unter $50.

## Anhang B — Was NICHT in diesem Plan liegt, und was Tim selbst tun müsste

**Nicht im Plan:**

- **Benachrichtigungen und alles für Ratsmitglieder** (Regel 21).
- **Ein „Warum" ohne Text.** Wo kein Abschnitt vorliegt — Magdeburg
  vollständig, Peine, Darmstadt, Freiburg, alle SessionNet-Kandidaten außer
  Münster — bleibt die Karte, wie sie ist. Kein Modell füllt die Lücke.
- **Städte, die uns aussperren.** Göttingen antwortet mit HTTP 403
  (Cloudflare), Salzgitter und Wilhelmshaven gar nicht. Kein Umweg über den
  Heim-Proxy, kein getarnter User-Agent — siehe PR 36.
- **Ein anderes Modell** — gemessen, abgelehnt (§2.4).
- **Der verkettete Cluster 1** — gemessen, abgelehnt (PR #1262).
- **Emden, Aurich, Nienburg** (SessionNet, 50/42/32 k). Dasselbe Produkt wie
  Oldenburg, also gut lesbar — aber klein, und ein sechster Adapter. Nach
  PR 36 neu bewerten.

**Was nur Tim tun kann — Anfragen, keine Zugänge.** Die Messung in §2.3 hat
in Niedersachsen 39 Kommunen gefunden, bei denen der OParl-Dienst
**vorhanden, aber abgeschaltet oder kaputt** ist; sieben davon sind groß
genug für den Vergleich. Ein Zugang hilft nicht — keiner dieser Endpunkte
fordert einen an (kein `WWW-Authenticate`, HTTP 400 bzw. 500, nie 401), und
OParl kennt per Spezifikation keinen. Was hilft, ist eine E-Mail an die
richtige Stelle — mit der ehrlichen Erwartung, dass bei SD.NET ein
kostenpflichtiges Modul dahinterstehen kann. Für die Städte aus Regel 25
kommt dazu: Göttingen und Salzgitter um Freigabe unserer Abrufe bitten,
sollte die Probe aus einem anderen Netz ebenfalls scheitern.

| Stadt | Einw. | Was zu sagen wäre |
|---|---:|---|
| **Wolfsburg** | **125 k** | „Ihr OParl-System antwortet auf `/oparl/system` sauber, auf `/oparl/bodies` aber mit HTTP 500 — dadurch ist die Schnittstelle unbenutzbar." |
| Lüneburg | 75 k | dasselbe für `/public/oparl/system` |
| Laatzen | 43 k | dasselbe |
| Lingen | 58 k | „Ihr SD.NET RIM meldet: *Webservice „OParl" ist nicht aktiviert*. Könnten Sie ihn freischalten?" |
| Nordhorn | 54 k | dasselbe |
| Cuxhaven | 48 k | dasselbe |
| Verden | 28 k | dasselbe |

Wolfsburg allein wäre die zweitgrößte niedersächsische Stadt im Vergleich.
Käme auch nur die Hälfte, wäre das mehr, als PR 36 an Arbeit kostet — und
ohne einen einzigen HTML-Parser. Der Hebel ist unverhältnismäßig groß, und
er liegt nicht im Code.

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
6. **Eine Stadt ohne bekannten Endpunkt prüfen** — der Weg, an dem die erste
   Messung gescheitert ist (§2.3). **Nicht** Adressmuster raten, sondern:
   die Rathaus-Seite zum Stichwort „Ratsinformationssystem" holen, alle
   Links mit `ratsinfo|sessionnet|buergerinfo|allris|sitzung|rim|ris.` daraus
   ziehen, und auf **diesen** Hosts die OParl-Pfade probieren:
   `/oparl/system`, `/public/oparl/system`, `/webservice/oparl/v1.1/system`,
   `/bi/oparl/1.0/system.asp`. Drei Antworten sind je eine eigene Aussage:
   JSON mit `oparlVersion` = läuft; `{"error":"Webservice \"OParl\" ist
   nicht aktiviert!"}` = SD.NET, eine Anfrage entfernt; HTTP 500 auf einer
   Route, die es gibt = ALLRIS 4 kaputt konfiguriert, ebenfalls eine Anfrage
   entfernt. Nur 404 überall heißt wirklich „kein OParl".
