# Prüfbericht — Datenbestand Wahlprogramm-Vergleich

Vollständige Nachprüfung des Bestands aus PR #356, Stand `63f5f8f`.
Geprüft wurden: Struktur, alle abgeleiteten Zahlen, jedes Belegzitat gegen den Programmtext,
jede Seitenzahl, der Thesenkatalog auf Überschneidung und Doppeldeutigkeit, die
Positionszuordnung auf Konsistenz zwischen den Listen, und die Rahmendaten gegen die amtliche
Bekanntmachung.

Die Prüfskripte liegen im Scratchpad (`pruef_struktur.py`, `pruef_zitate.py`, `pruef_seiten.py`,
`pruef_methode.py`, `pruef_konsistenz.py`, `pruef_besonderes.py`).

**Gesamteindruck: der Bestand ist handwerklich gut.** Kein einziges erfundenes Zitat, keine
falsche Seitenzahl, alle Rechenwege stimmen. Was zu korrigieren ist, sind sieben inhaltliche
Einstufungen, zwei überholte Thesen und drei Sachen an der Methode, die die Anzeige betreffen.

---

## 1 Was nachweislich stimmt

| Prüfung | Umfang | Ergebnis |
|---|---|---|
| Struktur der Positionsdateien | 16 Dateien × 44 Thesen | 0 Fehler. Alle IDs vorhanden, `pos` gültig, `beleg`/`seite` genau dann gesetzt, wenn sie es sein müssen |
| `data.json` gegen die Einzeldateien | 704 Positionen | identisch, kein Drift |
| Paarähnlichkeiten nachgerechnet | 120 Paare × (1 Gesamt- + 12 Themenwerte) | **alle 1 560 Zahlen exakt reproduziert** |
| `thesen_stat`, `abdeckung` nachgerechnet | 44 + 192 Einträge | exakt |
| Belegzitate im Volltext | 137 prüfbare Zitate | 114 wörtlich, 23 nachverfolgt — **kein einziges erfunden** |
| Seitenzahlen | 87 exakt lokalisierbare Positionen | **0 falsch** |
| Rahmendaten gegen die amtliche Bekanntmachung | 383 Kandidierende, 16 Listen, 9 OB-Kandidaturen | Kandidatenzahl und Wahlbereiche **je Liste exakt** |
| Gegenprobe „keine Aussage" | B2 (Kita-Gebühren), D2 (Open Data) | Schweigen ist echt — die anderen Programme sagen dazu wirklich nichts |
| „Fällt auf"- und Kernpunkte | 129 Aussagen | im Text verankert |

Die 23 nicht-wörtlichen Zitate sind **keine Erfindungen**, sondern zwei harmlose Effekte:

- **Flexion**: Quelle „Sofortiger kostenloser Busverkehr", Beleg „sofortigen kostenlosen
  Busverkehr" (an den Satzbau angepasst).
- **Extraktionsschmutz**: die Volltexte trennen Wörter mitten drin — `Aug\nenhöhe`,
  `part eipolitisches`, `Kita - und`, `wa ndeln`, `Tempo 30 Zonen` ohne Bindestriche. Der Beleg
  ist dann korrekter als der extrahierte Text.

> **Folge für die Anzeige:** Die Belege dürfen **nicht** als „Zitat" mit Anführungszeichen
> ausgezeichnet werden — rund ein Sechstel würde ein Versprechen brechen, das wir gar nicht
> einlösen müssen. „Beleg" oder „Fundstelle" ist ehrlich und genauso stark.
> Aus demselben Grund taugen die `.txt`-Dateien nicht für Volltextsuche oder Textstellen-Anker
> auf der Seite. Seitengenau verlinken reicht und funktioniert.

---

## 2 Sieben Einstufungen, die korrigiert gehören

### 2.1 C1 Stadion — Grüne und Bürger Bündnis sagen dasselbe, stehen aber maximal weit auseinander ⚠️

These: *„Ein Stadion-Neubau soll **nicht** aus Steuermitteln finanziert werden."*

| | eingestuft | was im Programm steht |
|---|---|---|
| **Grüne** | **−1 (Ablehnung)** | „anteilige, gedeckelte Finanzierung", „verbindliche Beteiligung des VfB Oldenburg und von Sponsoren"; dazu S. 29: „Statt einseitig Millionen in Bau und Betrieb für Jahrzehnte zu binden, wollen wir vorrangig in die Sanierung … städtischer Sportstätten investieren." |
| **BB-OL** | **+1 (Zustimmung)** | „ein reines Steuergeldprojekt dieser Größenordnung nicht vertretbar", „keine Defizit-Übernahme durch die Stadt, stattdessen Beteiligung des Nutzers und privater Investoren, verbindliche Kostenobergrenze sowie Exit-Klausel" |

Beide lehnen die **reine** Steuerfinanzierung ab und verlangen Deckelung plus private
Beteiligung. Sie bekommen die beiden entgegengesetzten Extremwerte.

**Korrektur: Grüne −1 → 0.** Das ist der folgenreichste Fund: C1 ist mit `streit = 0.6` unter
den fünf Top-Streitpunkten und stünde damit prominent auf der Überblicksseite — mit einer
Gegenüberstellung, die es so nicht gibt.

### 2.2 W3 Leerstand — gleiche Substanz, verschiedene Note

These bündelt drei Instrumente (Zweckentfremdungssatzung, Leerstandsabgabe, Enteignung).

- **SPD → 0**: „Nur die Zweckentfremdungssatzung wird genannt; Leerstandsabgabe oder Enteignung
  kommen nicht vor."
- **BSW → +1**: „Durch die Einführung kommunaler Zweckentfremdungssatzungen können Städte und
  Gemeinden wirksam gegen Leerstand … vorgehen."

Beide nennen genau ein Instrument von dreien. **Korrektur: BSW +1 → 0** (oder SPD hoch, aber
die SPD-Begründung ist die sauberere).

Am selben Punkt hängt die **AfD mit −1**: begründet mit „fordert erleichtertes Bauen *anstatt
enteignen* und erwähnt weder Zweckentfremdungssatzung noch Leerstandsabgabe". Die Ablehnung
**eines** der drei Instrumente plus Schweigen zu den anderen ist keine Ablehnung des Bündels.
Vertretbar, aber dünn.

### 2.3 BSW intern widersprüchlich: B1 gegen W3

Beide Belege haben dieselbe Bauform „alle Kommunen / Städte und Gemeinden sollen X":

- **B1 → 0**: „Allgemein sollen *alle Kommunen … ausreichend Plätze in Integrierten
  Gesamtschulen bereitstellen*; eine vierte IGS für Oldenburg wird nicht konkret gefordert."
- **W3 → +1**: „*Städte und Gemeinden* können wirksam gegen Leerstand vorgehen."

Dieselbe Verallgemeinerungsstufe, einmal abgewertet, einmal voll gewertet.

### 2.4 Volt M3 Parkgebühren — nicht belegt ⚠️

These: *„Die Parkgebühren sollen gesenkt oder zumindest nicht weiter erhöht werden."*
Volt steht auf **−1**, begründet mit „Umwidmung kostenloser Parkplätze; Park-and-Ride-Plätze in
Innenstadtnähe sollen schließen".

Im Volt-Programm steht dazu: „Wir fördern **Parkplätze außerhalb des Stadtzentrums** sowie die
Umwidmung kostenloser Parkplätze"; „Anwohner\*innen werden bevorzugt einen Stellplatz zu
**attraktiven Konditionen** in den Parkhäusern erhalten"; und S. 10 „Dafür wollen wir **mehr**
Stellplätze und Park-and-Ride-Flächen am Rand der Stadt".

Zwei Probleme: Es geht um Stellplätze, nicht um Gebührenhöhe — und die Behauptung, P+R in
Innenstadtnähe solle schließen, findet sich im Programm nicht; Volt will P+R *ausbauen*.
**Korrektur: −1 → null.**

### 2.5 CDU I4 Geflüchtete — Schluss, den der Text nicht hergibt

CDU steht auf **−1**, begründet mit „Fordert, dass Bund und Land die Kosten … vollständig
übernehmen, **statt dass** sich die Stadt über gesetzliche Pflichten hinaus engagiert."

Das „statt dass" ist die Folgerung der Auswertung, nicht die Aussage der CDU. Eine Forderung
nach Kostenerstattung ist keine Absage an eigenes Engagement. Zum Vergleich: AfD („lehnt
freiwillige Aufnahme ab") und BSW („gesamtstaatliche Aufgabe") sagen es ausdrücklich — die CDU
nicht. **Korrektur: −1 → null**, sofern sich keine ausdrückliche Aussage findet.

### 2.6 SPD P2 Jugendparlament — Note über dem Beleg

These verlangt drei konkrete Rechte: Rede-, Antragsrecht, eigenes Budget.

- **Grüne +1**: nennt alle drei ✓ · **Linke +1**: „echte Entscheidungsrechte" + Budgets ✓ ·
  **BSW +1**: „eigene Budgets und Mitsprache" ✓
- **SPD +1**: „verbindliche und transparente Mitbestimmung" — nennt **keines** der drei
- **CDU 0 / Volt 0 / BB-OL 0**: für vergleichbar unbestimmte Formulierungen

**Korrektur: SPD +1 → 0.**

### 2.7 SPD C3 Kultur — Rückschau statt Zusage

**+1**, begründet mit „Vergnügungssteuer abgeschafft, Beauftragte eingeführt, MachIWerk
fortgesetzt und *bei Bedarf* ausgeweitet" — überwiegend Erreichtes plus eine Konditionalzusage.
Volt bekommt für „dauerhaft gesicherte Förderprogramme" eine 0. **Grenzfall, eher 0.**

### 2.8 Kleinkram

- **BB-OL M4 und P2 ohne Seitenzahl**, obwohl beide auf **S. 11** stehen und die Quelle ein PDF
  mit Seitenbezug ist. Zwei fehlende Tiefenlinks.
- **SPD `besonderes`**: „Wiederaufstellung von Warnsirenen … **erstmals seit über 30 Jahren**".
  Der Zusatz steht nicht im Programm („wieder Sirenen aufstellen"). Ausgeschmückt, würde aber
  als Tatsache angezeigt.

---

## 3 Zwei Thesen mit überholter Prämisse

### 3.1 W1 — die zweite Wohnungsgesellschaft gibt es schon ⚠️

These: *„Oldenburg soll neben der bestehenden GSG eine zusätzliche städtische
Wohnungsbaugesellschaft gründen."*

Aus den Programmen selbst:

- **BB-OL**: „Die Gründung einer städtischen Wohngesellschaft, **die der Stadtrat 2025
  beschlossen hat**, begrüßen wir ausdrücklich."
- **SPD**: „haben wir … in der vergangenen Ratsperiode die Gründung … **initiiert**"
- **Grüne**: „**Die neue** städtische Wohnungsgesellschaft wird zum Motor …"
- **CDU**: „lehnen wir **weiterhin** ab"

Die Gründung ist beschlossen. Die offene Frage ist „ausbauen oder zurückdrehen", nicht
„gründen oder nicht". Der bestehende `hinweis` sagt das nicht. Wer die These liest, hält eine
entschiedene Sache für offen. **→ `hinweis` ergänzen.**

### 3.2 B2 — Kita-Gebühren sind in Niedersachsen weitgehend Landesrecht

These: *„Kita- und Betreuungsgebühren sollen gesenkt oder abgeschafft werden."* — nur **2 von
9** Listen äußern sich, und die Gegenprobe zeigt: die anderen sieben schweigen wirklich.

Der Grund ist vermutlich, dass der Kindergartenbeitrag ab 3 Jahren in Niedersachsen
landesrechtlich beitragsfrei ist; übrig bleibt die Krippe — genau das, wozu das BSW sich äußert
(„Auch Krippenplätze sollten kostenfrei sein"). **Vor Veröffentlichung gegen die geltende
Rechtslage prüfen und als `hinweis` ergänzen**, sonst liest sich das Schweigen als
Desinteresse.

### 3.3 Thesen, die zwei oder drei Fragen auf einmal stellen

W2 (zwei Quoten × zwei Handlungen) · W3 (drei Instrumente) · P3 (drei Instrumente) ·
I1 (drei) · S3 (drei) · O4 (zwei Achsen).

Genau hier sind oben die Inkonsistenzen aufgetreten — das ist kein Zufall: Ein Wert kann eine
Bündelfrage nicht beantworten. Für 2026 nicht mehr aufzudröseln; die Anzeige muss stattdessen
den **Beleg** so nah an die Ampel stellen, dass der Unterschied sichtbar wird.

### 3.4 Umgedrehte Thesen — Anzeigefalle

**K4, B3, C1, F3, I2, W4, O4** sind so formuliert, dass Zustimmung in die *entgegengesetzte*
Richtung zeigt wie bei den Nachbarthesen. Auf der Klima-Seite steht dieselbe Partei bei K1 auf
Grün und bei K4 auf Rot — beides korrekt.

> **Daraus folgt hart: es darf keine aggregierte „Ampel-Bilanz" je Partei geben** (kein
> „7× dafür, 3× dagegen"-Streifen, kein Fortschrittsbalken). Die Glyphe ist nur zusammen mit
> dem Thesentext lesbar.

### 3.5 I3 hat genau eine Position

*„Die Stadtverwaltung soll geschlechtergerechte Sprache verwenden"* — nur die FDP äußert sich.
`streit` ist `null`. Damit vergleicht die These nichts. **43 der 44 Thesen tragen tatsächlich
einen Vergleich**; fünf weitere (B2, B3, O2, D2, B1, S2) beruhen auf zwei oder drei Positionen.

---

## 4 Drei methodische Befunde, die die Anzeige umbauen

### 4.1 `thesen_stat` zählt über alle 16 Listen, nicht über die 9 verglichenen ⚠️

M5 wird mit `n = 10` ausgewiesen, obwohl im Vergleichsset nur 9 Listen stehen — die
Zusatzposition stammt von einer Liste ohne Programm. **Jede angezeigte Zahl (`n`, `dafuer`,
`teils`, `dagegen`, `streit`) muss über die Vergleichsmenge neu gerechnet werden.**
Das ist derselbe Fehler wie bei `themen_rang` und trifft direkt die Blöcke „Darüber streiten
sie" und „Darüber sind sie sich einig".

### 4.2 Beidseitiges „teils/teils" treibt die Ähnlichkeit um bis zu 14 Punkte hoch ⚠️

Wenn zwei Listen zur selben These beide `0` haben, zählt das als **volle Übereinstimmung**
(`1 − |0−0|/2 = 1`). Zwei Listen, die beide vage bleiben, gelten also als einig.

| Paar | ausgewiesen | ohne die 0–0-Thesen | Differenz |
|---|---:|---:|---:|
| Grüne – FDP | 38 % | 23 % | **−14** |
| CDU – Volt | 50 % | 38 % | **−12** |
| Volt – BSW | 67 % | 56 % | −10 |
| SPD – BSW | 75 % | 68 % | −7 |
| SPD – Volt | 76 % | 70 % | −6 |

11 % aller gewerteten Vergleiche sind 0–0-Paarungen. Das ist keine Schlamperei, sondern liegt
in der Wahl-O-Mat-Formel — aber es gehört auf die Methodikseite, und der Paar-Detailansicht
täte eine zweite Zahl gut („davon X Thesen, zu denen sich beide nur unbestimmt äußern").

Erfreulich dagegen: **die Gesamtwerte sind stabil.** Lässt man jede einzelne These einmal weg,
bewegt sich der Wert im Median um 3,4 Punkte, maximal um 6,4. Kein Paarwert hängt an einer
einzelnen These.

### 4.3 Die Themen-Teilwerte tragen fast nichts ⚠️

Die 12 Themen-Ampeln je Paar (36 Paare × 12 = 432 Zellen):

| gemeinsame Thesen im Themenfeld | Zellen |
|---|---:|
| 0 (kein Vergleichspunkt) | 81 |
| **1 (eine einzige These)** | **118** |
| 2 | 139 |
| 3 | 71 |
| 4–5 | 23 |

Mit der eigenen Schranke `min_n_thema = 2` sind **199 von 432 Zellen (46 %) nicht belastbar**.
Eine „Wohnen: 0 %"-Ampel, die auf einer einzigen These steht, ist Rauschen mit Prozentzeichen.

> **Konsequenz für den Bauplan:** Der Punkt „die 12 Themen-Ampeln im Paar-Detail" (§4.4.3)
> fällt in dieser Form weg. Sinnvoller: pro Paar die Thesen mit **voller Übereinstimmung** und
> mit **klarem Dissens** namentlich auflisten — dieselbe Information, ohne Scheingenauigkeit.

### 4.4 Sehr unterschiedliche Auskunftsdichte

| Liste | Positionen von 44 | | Liste | Positionen von 44 |
|---|---:|---|---|---:|
| SPD | 34 (77 %) | | AfD | 23 (52 %) |
| CDU | 33 (75 %) | | FDP | 24 (55 %) |
| Volt | 33 (75 %) | | BSW | 27 (61 %) |
| Grüne | 31 (70 %) | | **BB-OL** | **19 (43 %)** |
| Linke | 30 (68 %) | | | |

Die Paar-`n` reichen dadurch von 12 (FDP–BB-OL) bis 29 (SPD–Volt). Ein 71-%-Wert auf 12 Thesen
und ein 76-%-Wert auf 29 sind nicht dasselbe. **`n` muss neben jedem Wert stehen** — die
README fordert das bereits, die Umsetzung muss es einlösen.

---

## 5 BSW: das Landesprogramm-Problem ist größer als gedacht

**Das BSW-Programm nennt Oldenburg an keiner einzigen Stelle** — nachgeprüft, `grep` findet
das Wort nicht. Von 27 Positionen stützen sich **7 ausdrücklich** auf Aussagen über „alle
Kommunen", „Städte und Gemeinden" oder die Landesebene:

- **K3 (−1)** entsteht aus der Kritik an einer **Landesvorgabe** (2,2 % Windkraftfläche) —
  gewertet als Position zu „*Die Stadt* soll mehr Flächen ausweisen".
- **S2 (+1)**, **P2 (+1)**, **W3 (+1)**, **C2 (+1)** aus „in den Kommunen"-Forderungen.
- **B1 (0)** und **I4 (−1)** ebenso.

Meine Empfehlung aus dem Bauplan (BSW mitnehmen, dauerhaft markiert) bleibt — aber die
Markierung muss **an jeder einzelnen BSW-Position** hängen, nicht nur an der Parteikarte, und
der Methodiktext muss sagen, dass diese Positionen aus einem Text abgeleitet sind, der
Oldenburg nicht kennt. Wer das für zu weich hält, hat ein gutes Argument, BSW ganz
herauszunehmen; dann bleiben 8 Listen und 28 Paare.

---

## 6 Nebenbefund: Bürgerentscheid Baumschutz

`ja + nein = 37 242`, ausgewiesene Beteiligung `37 295` — Differenz **53 ungültige Stimmen**.
Die Prozentwerte (60,58 % Ja) sind korrekt auf die gültigen Stimmen gerechnet. Kein Fehler,
aber die Zahlen gehen für Leser:innen sonst nicht auf: **„53 ungültig" mit ausweisen.**

---

## 7 Was jetzt zu tun ist

**Vor dem Frontend (Daten):**

1. C1 Grüne `−1 → 0` · W3 BSW `+1 → 0` · Volt M3 `−1 → null` · CDU I4 `−1 → null` ·
   SPD P2 `+1 → 0` · SPD C3 `+1 → 0` (Grenzfall) · BSW B1/W3 angleichen
2. BB-OL M4 und P2: Seitenzahl 11 nachtragen
3. SPD-`besonderes`: „erstmals seit über 30 Jahren" streichen
4. `hinweis` für W1 (Gründung 2025 beschlossen) und B2 (Landesrecht) ergänzen
5. `analyse.py`: `thesen_stat` **und** `themen_rang` über die Vergleichsmenge rechnen;
   `belastbar`-Flag (n ≥ 5) mitschreiben; `data.json` neu erzeugen
6. Danach `pruef_struktur.py` erneut laufen lassen — die Paarwerte ändern sich durch 1.

**Im Frontend:**

7. Belege als „Beleg"/„Fundstelle" auszeichnen, nicht als „Zitat"
8. Keine aggregierte Ampel-Bilanz je Partei (§3.4)
9. Themen-Ampeln im Paar-Detail durch namentliche Übereinstimmungs-/Dissens-Listen ersetzen (§4.3)
10. `n` neben jedem Prozentwert; 0–0-Anteil im Paar-Detail nennen
11. BSW-Markierung an jeder Position, nicht nur auf der Karte
12. Bürgerentscheid: 53 ungültige Stimmen ausweisen

**Als Test einfrieren:** `pruef_struktur.py` und `pruef_zitate.py` gehören nach `tests/` — sie
haben diesen Durchgang getragen und würden jede spätere Datenauffrischung genauso absichern.


---

## 8 Schwarm-Prüfung vom 08.08.2026

Auf Tims Wunsch lief nach dem Frontend-Bau eine zweite, unabhängige Prüfrunde:
**28 Sonnet-Finder** (9 Listen × Positionen / Programm-Porträt / Forderungs-Bullets, plus
Klartext-Einzeiler), jeder Fund anschließend von einem **Skeptiker-Agenten** adversarial
gegengeprüft. 52 Agenten, 1 574 Werkzeug-Aufrufe, **1 227 geprüfte Aussagen**.

Ergebnis: **12 bestätigte Befunde** (kein kritischer), 12 verworfen. Die Korrekturen stehen
in `pruefungen/korrekturen_2026_08_08.py` (idempotent, angewendet):

| Befund | Korrektur |
|---|---|
| AfD P1 `+1` trotz „Bürgerbefragung statt Bürgerentscheid" (Volt bekam für dieselbe Abstufung `0`) | `+1 → 0`, Beleg präzisiert |
| AfD V1: Seite 12 deckte nur den „Genehmigungsturbo", Bau-Turbo + Genehmigungsfiktion stehen auf S. 36 | Hauptseite 36, beide Fundstellen im Beleg |
| AfD C3: „soziokulturelle" statt der im Text stehenden „queeren Aktivismus-Workshops" | wortgetreu korrigiert |
| BB-OL Kultursommer (3 Stellen): „drei bis vier Wochen" war die *frühere* Dauer — gefordert sind drei Wochen | Zieldauer in Position, `besonderes` und Themen-Bullet korrigiert |
| Grüne S3: Streetworker-Fundstelle (S. 19) unter Seitenangabe 31 | beide Seiten im Beleg ausgewiesen |
| Grüne „größte Arbeitgeberin" — Text sagt „eine der größten" | Superlativ zurückgenommen |
| FDP-Bullet nannte die GSG „städtische Gesellschaft" — Text: „an der die Stadt beteiligt ist" | Formulierung korrigiert |
| 7 Themenfeld-Seitenlisten deckten einzelne Bullet-Fundstellen nicht ab | Seiten ergänzt (gruene, linke ×4, volt, spd) |

Durch die AfD-P1-Korrektur ändern sich Paarwerte leicht (Spitze jetzt FDP–AfD 92 %);
Streit-Top-5, Einigkeit und Alleinstellungen bleiben unverändert. Alle Prüfskripte laufen
danach grün.
