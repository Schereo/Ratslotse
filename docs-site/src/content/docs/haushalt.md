---
title: Stadtfinanzen
description: Der Haushalts-Bereich — woher die Zahlen kommen, welche redaktionell sind, und was bewusst fehlt.
---

Der Haushalt ist der sperrigste Stoff, den Ratslotse zeigt: Doppik-Vokabular,
Millionenbeträge ohne Bezugsgröße, Zuständigkeiten quer über drei staatliche
Ebenen. Der Bereich unter `/haushalt` übersetzt ihn — und macht dabei an jeder
Stelle sichtbar, welche Zahl amtlich ist, welche wir gerechnet haben und
welche schlicht fehlt.

:::note[Vorerst nur auf dev.ratslotse.de]
Der Bereich liegt hinter dem Umgebungs-Gate: `web/frontend/lib/haushalt-frei.ts`
prüft `NEXT_PUBLIC_RATSLOTSE_ENV`, das nur der Dev-Build setzt. Auf
ratslotse.de rendert keine seiner Seiten, und die Anker dorthin
(Seitenleiste, „Mehr"-Sheet, der Verweis auf den Beschluss-Seiten) fehlen
ebenfalls — ein Gate ohne seine Einstiege hinterließe Links ins Leere.

Zwei Dinge, die daraus folgen: Auf Prod laufen weder die Ingest-Skripte noch
der Cron `check_finanzdaten`, die Haushalts-Tabellen entstehen dort leer und
bleiben es (die Geld-Bausteine der KI-Frage vertragen das — **jeder** von
ihnen liefert bei leeren Daten einen Leerstring, und jede Abfrage steht in
`qa._sicher`, kann die Antwort also nicht blockieren; `tests/test_haushalt_gate.py`
prüft beides über alle Bausteine automatisch, nicht über eine Aufzählung).
Und: Weil `app/(app)/` ein Client-Layout ist, kommt die
Antwort mit HTTP 200 statt 404 — ein „Soft 404". Inhaltlich folgenlos,
weshalb `/haushalt` auch nicht in der Sitemap steht. `tests/test_haushalt_gate.py`
wacht darüber, dass kein neuer Verweis das Gate vergisst.
:::

## Die Seiten

Der Einstieg trägt einen **Wegweiser** (`components/haushalt/wegweiser.tsx`),
und der ist keine Linkliste, sondern die Leserichtung des ganzen Bereichs:
neunzehn Schritte in vier Stufen (6 · 4 · 6 · 3). Die Tabelle steht deshalb in
genau dieser Reihenfolge.

| Route | Inhalt |
|---|---|
| `/haushalt` | Einstieg: Anzeigetafel mit der Kernzahl, Gegenbalken (umschaltbar auf die 100-Euro-Ansicht), Rücklagen-Reichweite, Bereichstabelle, Geldfluss (für Planjahre nur die Herkunftsseite, s. u.), Zeitreihe, Datenstand |
| **Die Zahlen** | |
| `/haushalt/einnahmen` | Schritt 1 — alle Einnahmequellen, **nach Entscheidungsmacht gruppiert** statt nach Betrag sortiert |
| `/haushalt/pflicht` | Schritt 2 — muss oder kann: Ausgaben nach Gestaltungsspielraum, gegen die Selbstauskunft der Stadt gehalten |
| `/haushalt/produkte[?nr=<produkt_nr>]` | Schritt 3 — „Was kostet eigentlich …?", zwei Abschnitte: `#bereiche` die zehn Teilhaushalte im Klartext (ihre Namen stammen aus der Verwaltungs­gliederung und sagen, wer zuständig ist, nicht worum es geht), `#produkte` die einzelnen Produkte mit Kosten, durchsuchbar. Die dritte Ebene — der Steckbrief eines Teilhaushalts — bleibt `/haushalt/bereich` |
| `/haushalt/personal` | Schritt 4 — „Wer macht die Arbeit?“: der Stellenplan je Amtsbezeichnung, mit besetzten und unbesetzten Stellen zum Stichtag |
| `/haushalt/investitionen[?jahr=<jahr>&thh=<nr>]` | Schritt 5 — „Was gebaut wird — und was daraus wurde", zwei Abschnitte: `#plan` der Finanzhaushalt je Teilhaushalt mit dem Investitionsprogramm (Vorhaben einzeln, durchsuchbar), `#gebaut` was am Jahresende tatsächlich abgeflossen ist — seit 2003, nach Auszahlungsart |
| **Die Gegenprobe** | |
| `/haushalt/plan-ist[?jahr=<jahr>]` | Schritt 6 — geplant gegen tatsächlich, je Teilhaushalt, mit den Abweichungsgründen der Verwaltung im Wortlaut |
| `/haushalt/pruefung[?jahr=<jahr>]` | Schritt 7 — „Geprüft und zusammengefasst", zwei Abschnitte: `#feststellungen` die Feststellungen des Rechnungsprüfungsamts im Wortlaut, je Jahrgang und als Wiederholungskette, `#kennzahlen` die dreizehn Kennzahlen, auf die die Stadt ihren Abschluss selbst eindampft, mit den gedruckten Rechenwegen |
| **Der Rahmen** | |
| `/haushalt/konzern[?g=<gesellschaft>]` | Schritt 8 — „Und ist das die ganze Stadt?", vier Abschnitte: `#summe` Kernverwaltung gegen Gesamtabschluss mit der Konsolidierung, `#gesellschaften` jede städtische Gesellschaft mit Auftrag, Eigentümern, Aufsicht und Kennzahlen-Zeitreihe (`g` öffnet den Steckbrief IM Abschnitt), `#betriebe` die Wirtschaftspläne der Eigenbetriebe je Betrieb und Jahrgang, `#gebuehren` die Gebührenbedarfsberechnung für Abfall und Straßenreinigung |
| `/haushalt/vergleich` | Schritt 9 — Steuerkraft, Hebesätze und Steuereinnahmekraft der acht kreisfreien Städte aus der amtlichen Statistik — und die Erklärung, warum Ausgaben und Personal **nicht** verglichen werden |
| `/haushalt/schulden` | Schritt 10 — dreißig Jahre Schuldenstand aus Tabelle 1108 des Statistischen Jahrbuchs, mit der Angabe, was mitgezählt ist |
| **Mitreden** | |
| `/haushalt/mitreden[?jahr=<jahr>]` | Schritt 11 — „Mitreden", zwei Abschnitte auf einer Seite: `#termine` wann der Haushalt entschieden wird (jede Station im Rat, aus acht Jahrgängen, mit Link auf die Sitzung), `#streit` je Jahrgang die Änderungslisten mit Abstimmungsergebnis, ihr Inhalt Position für Position („Was in den Listen stand", aus `council_haushalt_aenderungen`), die Wortbeiträge im Protokollwortlaut und die Schlussabstimmung |
| `/haushalt/labor` | Schritt 12 — das Haushalts-Labor, drei Werkbänke mit je eigener Zielgröße: **Einnahmen** (Gewerbesteuer-Hebesatz mit mitlaufender Städte-Leiter und eigener Treppe seit 1980, Grundsteuer B mit belegter LSN-Aufteilung, Hundesteuer, Gebühren als absichtlich gesperrte Schraube), **Ausgaben** (freiwillige Teilhaushalte), **Investitionen & Finanzierung** (Vorhaben-Schalter aus Anlage 004, Kredit-Schalter mit gezahlter Zins-Spanne). Ergebnis-Spalte mit Lücken-Balken, Rücklagen-Pfad über die Finanzplanungsjahre samt Kipp-Jahr und Finanzausgleichs-Spanne aus den echten Ausgleichsjahren |
| **Steckbriefe (ohne Schritt)** | |
| `/haushalt/bereich?name=<slug>` | Dossier je Teilhaushalt: Wasserfall Brutto → eigene Erträge → Zuschussbedarf, Entwicklung seit 2020, Produkte des Bereichs |
| `/haushalt/steuer?art=<slug>` | Steckbrief je Einnahmeart: „Wer entscheidet was", Ist-Kurve, Hebesatz, Ein-Punkt-Überschlag |

Die beiden Steckbriefe tragen keinen Schritt, weil sie einen Bereich bzw. eine
Einnahmeart brauchen, über die man sie aufruft — als eigener Schritt stünde
dort ein beliebiger Einzelfall. Man erreicht sie aus Schritt 1 und 2 sowie aus
der Bereichstabelle des Einstiegs.

:::caution[Die Reihenfolge steht an zwei Stellen]
Der Wegweiser (`components/haushalt/wegweiser.tsx`) zählt die Ziele seiner
vier Stufen durch — das ist die Reihenfolge. Die Tabelle oben ist die zweite
Stelle, an der dieselben Nummern stehen, und die einzige außerhalb des Codes.
`tests/test_haushalt_schritte.py` gleicht beide ab.

**Bis zum 21.08.2026 gab es eine dritte:** Acht Seiten schrieben ihre Nummer
selbst in den Kicker („Stadtfinanzen Oldenburg · Schritt N"), dazu zwei
Verweis-Karten im Fließtext. Sobald eine Seite dazukam, rutschte alles
Nachfolgende um eins — am 16.08. viermal an einem Tag, und jedes Mal blieb
mindestens ein Kicker auf dem alten Stand. Auffallen konnte das niemandem:
Der Wegweiser zeigte die richtige Nummer, die Seite die falsche, und beide
sahen für sich stimmig aus.

Beim Zusammenlegen der Etappen wäre es viermal mehr geworden — jede
Zusammenlegung verschiebt ebenfalls alles danach. Statt den Widerspruch
weiter zu bewachen, ist er abgeschafft: `<SchrittKicker href="…" />` und
`schrittNummer(href)` (beide in `components/haushalt/schritt-weiter.tsx`)
schlagen die Zahl in derselben Liste nach, die der Wegweiser zählt. Kennt
die Liste den Pfad nicht — Steckbriefe wie `/haushalt/bereich` haben bewusst
keinen Schritt —, steht nur „Stadtfinanzen Oldenburg" da.

Wer eine Seite einfügt oder zusammenlegt, zieht also nur noch **diese
Tabelle** nach.
:::

Query-Parameter statt dynamischer Segmente, weil der Capacitor-Export die
Slugs zur Bauzeit nicht kennt — dieselbe Konvention wie `/council/decision?id=`.

## Woher die Daten kommen

Das Fundament liefert **ein** Endpunkt: `GET /api/council/haushalt` gibt
Planjahre, Ergebnisrechnung, Ist-Steuern, Steuerkraft und die Einwohnerzahl in
einem Aufruf — er trägt den Einstieg und die meisten Vertiefungsseiten. Einen
**eigenen** Endpunkt bekommt nur, was groß genug ist, um Seiten zu belasten,
die es nicht zeigen:

| Endpunkt | Wofür | Warum getrennt |
|---|---|---|
| `…/haushalt/pruefberichte` | `/haushalt/pruefung`, Prüfungs-Karte auf `/haushalt/plan-ist` | eine Viertel-Megabyte Prosa |
| `…/haushalt/produkte` | `/haushalt/produkte`, `/haushalt/pflicht`, `/haushalt/bereich`, Labor | mehrere hundert Zeichen Steckbrief je Zeile; gesucht und gefiltert wird serverseitig |
| `…/haushalt/konzern` | `/haushalt/konzern` | eigene Tabellen, eigene Jahrgangsreihe |
| `…/haushalt/stellenplan` | `/haushalt/personal` | rund 190 Zeilen je Jahrgang; die Einzelposten kommen nur für den angefragten Jahrgang mit |
| `…/haushalt/vergleich` | `/haushalt/vergleich` | eigene Tabelle (LSN), acht Städte × Jahrgänge |
| `…/haushalt/investitionen` | `/haushalt/investitionen` | eigene Tabelle, **anderer Haushalt** (Finanz- statt Ergebnishaushalt) — nicht mit den übrigen Zahlen verrechenbar |
| `…/haushalt/gebaut` | `/haushalt/investitionen#gebaut` | eigene Tabellen; **Ist statt Plan** und nach Auszahlungsart statt nach Teilhaushalt — bewusst nicht mit `…/haushalt/investitionen` zusammengelegt, damit die beiden Summen nicht als „geplant gegen gebaut" gelesen und voneinander abgezogen werden. Seit 21.08.2026 stehen sie als zwei ABSCHNITTE einer Seite; die Datenwege bleiben getrennt, und der Einwand („Warum hier keine Umsetzungsquote steht") steht seither VOR den Ist-Zahlen statt dahinter |
| `…/haushalt/schulden` | `/haushalt/schulden` | eigene Tabelle, eigene Jahrgangsreihe (bis 1995 zurück) |
| `…/haushalt/weg` | `/haushalt/mitreden#termine` | Ratsdaten statt Finanzdokumenten (Beratungsfolge, Sitzungen) |
| `…/haushalt/datenstand` | Block „Bis wann die Zahlen reichen" | rechnet über den Bestand, nicht über Inhalte |
| `…/haushalt/dokumente` | Quellenverzeichnis **jeder** Haushalts-Seite | je Quelle und Jahrgang das Dokument — die Angabe, die die statische Quellenliste nicht haben kann |

| Tabelle | Inhalt | Quelle | Ingest |
|---|---|---|---|
| `council_haushalt` | Ergebnishaushalt je Teilhaushalt, 2020–2026 (**Plan**) | Beschlossene Haushaltsplan-PDFs; 2024 aus dem Open-Data-CSV | `scripts/ingest_haushalt.py` |
| `council_steuern` | Steuereinnahmen je Art seit 1998 (**Ist**) | Open-Data-Portal, Datensatz 1104 | `scripts/ingest_finanzen_opendata.py` |
| `council_steuerkraft` | Steuerkraftmesszahl + Schlüsselzuweisungen je Ausgleichsjahr seit 1993 (Jahreszahl beim Einlesen korrigiert, s. u.) | Open-Data-Portal, Datensatz 1106 | dito |
| `council_einwohner` | Einwohnerzahl je Jahr seit 2010 | Open-Data-Portal, Datensatz 1102 | dito |
| `council_investitionen` | Investitionen des **Finanz**haushalts je Teilhaushalt, 2022–2025 (**Plan**) — Ein- und Auszahlungen, dazu die Summenzeile und der Gesamtbetrag des Finanzhaushalts als Bezugsgröße | Open-Data-Portal, Datensatz 1101, Tabellenblatt „Finanzhaushalt" | dito |
| `council_investitionsmassnahmen` | **Einzelne Vorhaben** je Teilhaushalt, 2019–2026 (**Plan**) — IPSP-Element, Bezeichnung und Gesamtinvestitionssumme; `ebene` (`massnahme` / `teilhaushalt` / `gesamt`). Ohne Jahresraten, s. u. | Investitionsprogramm (Anlage 004 des Haushaltsplans) — **Anlagen im RIS** | `scripts/ingest_finanzberichte.py` |
| `council_ergebnisrechnung` | Ansatz, Plan **und** Ergebnis je Posten — gesamt und je Teilhaushalt, 2017–2024 | Jahresabschlüsse — **Anlagen im RIS** | `scripts/ingest_finanzberichte.py` |
| `council_ergebnishaushalt` | Dieselben Posten für Jahre **ohne** Abschluss, 2019–2026 — je Zeile `art` (`ansatz` / `finanzplanung`) und `plan_jahrgang` | Gesamtergebnishaushalt (Anlage 005 des Haushaltsplans) — **Anlagen im RIS** | dito |
| `council_abweichungsgruende` | Warum ein Posten vom Plan abwich (Abschnitt 6.3.1), 45 Einträge | dito | dito |
| `council_pruefbericht_quellen` | **Fundstelle** des RPA-Schlussberichts je Jahrgang (eine Zeile je Jahr) | dito | dito |
| `council_produkte` | Produktebene: was einzelne Aufgaben kosten — plus Steckbrief (Kurzbeschreibung, Auftragsgrundlage, Beeinflussbarkeit, Wirkungskreis, Zielgruppe) | Teilhaushalts-Pläne — **Anlagen im RIS** | dito |
| `council_stellenplan` | Stellen je Amtsbezeichnung, 2023–2026 — `teil` A (Beamt\*innen) / B (Tarifbeschäftigte), `art` (`posten` / `gruppe` / `gesamt`), dazu Besetzung und unbesetzte Stellen zum Stichtag | Stellenplan (Anlage 21/22 des Haushaltsplans) — **Anlagen im RIS** | dito |
| `council_pruefberichte` | Prüfungsfeststellungen 2017–2023, eine Zeile je Randmarke | Schlussberichte des Rechnungsprüfungsamts — **Anlagen im RIS** | `scripts/ingest_pruefberichte.py` |
| `council_konzern_posten` | Gesamtergebnisrechnung des **Konzerns** je Posten, 2014–2024 | Konsolidierte Gesamtabschlüsse — **Anlagen im RIS** | `scripts/ingest_konzernabschluss.py` |
| `council_konzern_traeger` | Dieselben Summen je Aufgabenträger (Kernverwaltung, Klinikum, Eigenbetriebe …), 2017–2024, in **TEUR** | dito | dito |
| `council_staedtevergleich` | Steuerkraft, Hebesätze und Steuereinnahmekraft der acht kreisfreien Städte je Jahrgang — Reihen `steuerkraft`, `realsteuern` und `finanzausgleich` (die drei Komponenten der Landeszuweisung, in TEUR) | Landesamt für Statistik Niedersachsen (Kommunaler Finanzausgleich, Realsteuervergleich) | `scripts/ingest_staedtevergleich.py` |
| `council_investitionen_ist` | Tatsächliche Investitions-Auszahlungen je Jahr seit 2003 (**Ist**) — Summe und `regelwerk` (`kameral` bis 2009, `doppik` ab 2010) | Statistisches Jahrbuch der Stadt, Tabellen 1107 und 1107-1 (PDF von oldenburg.de) | `scripts/ingest_investitionen_ist.py` |
| `council_investitionen_ist_arten` | Dieselben Jahrgänge nach Auszahlungsart, mit der Überschrift der Quelle — vier Arten je kameralem, sechs je doppischem Jahrgang | dito | dito |
| `council_investitionen_ist_verworfen` | Die Jahrgänge, die die Zeilensumme **nicht** bestanden haben: Grund und gemessene `differenz` in Euro. Damit die Seite ihre Lücke beziffern kann, statt sie nur zu behaupten | dito | dito |
| `council_schulden` | Schuldenstand je Jahr seit 1995 — vier Schuldenarten, Summe und Betrag je Einwohner\*in | Statistisches Jahrbuch der Stadt, Tabelle 1108 (PDF von oldenburg.de) | `scripts/ingest_schulden.py` |
| `council_ausgabenreihe` | Ausgaben je Jahr seit **1972** (**Ist**) — `regelwerk` (`kameral` bis 2009, `doppik` ab 2010), die bestandenen `proben` je Zeile und, wo die beiden Quellen sich widersprechen, der `konflikt_betrag` der unterlegenen. **Ohne Einwohnerzahl**, s. u. | Datensatz 1102 — Statistisches Jahrbuch, Tabelle 1102 (PDF) **und** Open-Data-Portal (zwei CSV) | `scripts/ingest_ausgabenreihe.py` |
| `council_steuerplan` | Je Steuerart und Jahr der **Ansatz des Haushaltsplans** neben dem **Rechnungsergebnis**; `vorlaeufig` ist die Angabe der Quelle über sich selbst. `art` trägt dieselbe Schreibweise wie `council_steuern` — daran hängt die Prüfung der Jahresbeschriftung | Statistisches Jahrbuch, Tabelle 1103 (PDF von oldenburg.de), **alle im Archiv gesicherten Ausgaben** | `scripts/ingest_steuertabellen.py` |
| `council_wirtschaftsplaene` | Eckwerte der **Wirtschaftspläne** je Eigenbetrieb und Haushaltsjahr — Erfolgsplan (Erträge, Aufwendungen, steuerliche Aufwendungen, Ergebnis), Vermögensplan und Verpflichtungsermächtigungen, dazu der Stand des Verwaltungsentwurfs. Bisher nur der Eigenbetrieb Gebäudewirtschaft und Hochbau, 2019–2026 — als einziger nennt er sie im Beschlusstext | **Die Ratsvorlage selbst** (Beschlussvorschlag), nicht eine Anlage | `scripts/ingest_wirtschaftsplaene.py` |
| `council_hebesaetze` | Die Realsteuer-Hebesätze je **Änderungsjahr** seit 1980 — Grundsteuer A, Grundsteuer B, Gewerbesteuer, dazu der `vorheriger` Satz. Neun Änderungsjahre (27 Zeilen) decken 45 Jahre — zuletzt 2025, als die Grundsteuerreform A auf 500 und B auf 539 Punkte hob | Statistisches Jahrbuch, Tabelle 1105 (auf demselben Blatt wie 1104) | dito |

:::note[Zwei Tabellen zu denselben Berichten]
`council_pruefbericht_quellen` hält die **Fundstelle** des Schlussberichts
(eine Zeile je Jahrgang, für den Verweis „geprüft → Schlussbericht"),
`council_pruefberichte` die **einzelnen Feststellungen** daraus (eine Zeile je
Randmarke). Zwei Ebenen, zwei Tabellen — die Namen halten sie auseinander.
:::

Alle Ingests sind idempotent. Die neun Schichten, die der Cron aus dem **Ratsinformations-
system** von allein nachzieht, tut er seit 08/2026 (siehe unten); die
Ingest-Skripte bleiben der Weg von Hand, wenn ein verbesserter Parser über den
**Bestand** laufen soll. Die Plan- und Open-Data-Schichten (`council_haushalt`,
`council_steuern`, `council_steuerkraft`, `council_einwohner`) kommen per
Download von oldenburg.de und bleiben Handarbeit, ebenso der Städtevergleich
(LSN, einmal jährlich — siehe [unten](#kein-neues-paket-kein-cron)) und die
Schuldenzeitreihe, die Ist-Investitionen und die lange Ausgabenreihe (alle drei
Statistisches Jahrbuch, einmal jährlich).

### Die lange Ausgabenreihe (Datensatz 1102, seit 1972)

Die längste Reihe des Bereichs — 54 Jahrgänge — und die einzige, die aus
**zwei Veröffentlichungen zugleich** kommt: dem Statistischen Jahrbuch
(Tabelle 1102 als PDF, ab 2002) und dem Open-Data-Portal (zwei CSV-Dateien,
ab 1972). Genau diese Doppelung macht sie prüfbar.

**Drei gestaffelte Proben**, und welche ein Jahrgang bestanden hat, steht an
seiner Zeile (`proben`):

1. **Pro-Kopf-Rechnung der Quelle** — beide Dateien führen neben dem Betrag
   eine Einwohnerzahl und einen Betrag je Einwohner\*in; Betrag ÷ Einwohnerzahl
   muss den ausgewiesenen Wert ergeben. Trägt jede der 54 Zeilen, auch die
   dreißig, für die es keine zweite Quelle gibt. Sie entscheidet nebenbei eine
   Einheitenfrage: Die ältere CSV beschriftet ihre Spalte „in Euro" und meint
   Tausend Euro — die Probe geht nur in Tausend Euro auf, und zwar in allen 38
   Zeilen.
2. **Jahrbuch gegen Open-Data-Portal** — in den 24 gemeinsamen Jahren müssen
   beide denselben Betrag nennen. Sie tun es 23-mal.
3. **Abgleich mit dem Jahresabschluss** — für die Jahre mit Abschluss gegen
   Posten 20 der Ergebnisrechnung.

**Warum der Abgleich eine Toleranz hat und keine Gleichheit.** Die Statistik
liegt in jedem geprüften Jahrgang zwischen 0,03 und 0,05 % über
`council_ergebnisrechnung` — 2017 um 166.253 €, 2024 um 328.936 €. Das ist
kein Rundungsrest, sondern eine Abgrenzung: Der Jahresabschluss führt die
Tabelle zweimal, als *Ergebnisrechnung der Kernverwaltung* (Abschnitt 3.1, das
ist, was wir parsen) und als *Gesamtergebnisrechnung* (3.2 — im
Rechenschaftsbericht ausgeschrieben als „Kernhaushalt und nicht rechtsfähige
Stiftungen"). Die Statistik nimmt die zweite. Der Bericht rechnet den
Unterschied selbst vor: „ordentliche Aufwendungen gemäß Haushaltsplan
728.170.348,30 abzüglich Aufwendungen der nicht rechtsfähigen Stiftungen
−286.683,03". Gegen die Gesamtergebnisrechnung stimmt die Statistik auf den
Tausender genau (2024: 764.745.383,29 € → 764.745 T€).

**Die Naht 2009/2010** ist dieselbe wie bei den Ist-Investitionen und stammt
aus derselben Fußnote: Umstellung auf das Neue Kommunale Rechnungswesen zum
1. Januar 2010. Links steht das *Anordnungssoll des Verwaltungshaushalts*,
rechts sind es die *ordentlichen Aufwendungen der Gesamtergebnisrechnung*.
Über den Schnitt zieht kein Lesepfad eine Linie, und das Modul stellt bewusst
keine Summen-, Wachstums- oder Mittelwertfunktion bereit.

**2021: zwei amtliche Quellen, zwei Beträge.** Das CSV nennt 613.572 T€, das
PDF 608.910 T€ — 4,662 Mio. € Unterschied, der einzige Widerspruch in 24
gemeinsamen Jahren. Auflösbar ist er, weil beide ihre Pro-Kopf-Spalte
mitbringen: Die PDF-Zeile geht auf (608.910.000 ÷ 169.605 = 3.590,17 gegen
ausgewiesene 3.590), die CSV-Zeile nicht (3.617,65 gegen 3.611) — sie
widerspricht sich selbst. Der Jahresabschluss 2021 bestätigt das PDF und zeigt
zugleich, was passiert ist: 613.571.622,10 € ist auf den Tausender genau der
**Ansatz** des Jahres, der in der Tabelle eine Spalte links vom Ergebnis steht.
Übernommen wird der PDF-Wert; der abweichende steht als `konflikt_betrag`
daneben im Bestand, und die Seite nennt beide Zahlen. Ohne das PDF fällt der
Jahrgang ganz heraus, statt still die falsche Zahl zu übernehmen.

**Ohne Einwohnerzahl, und das mit Absicht.** Beide Quellen führen den Divisor,
und die Probe braucht ihn — gespeichert wird er trotzdem nicht. Läge er in der
Tabelle, wäre die naheliegendste Grafik „Ausgaben pro Kopf seit 1972", und die
wäre falsch: Die Einwohnerreihe hat zwei Zensus-Brüche (2011 und 2022), an
denen ein Pro-Kopf-Wert springt, ohne dass sich etwas verändert hätte. Was die
API nicht liefern kann, kann das Frontend nicht versehentlich zeichnen.

**Der Nebengewinn:** Die Reihe führt das gerade abgelaufene Jahr, Monate bevor
sein Jahresabschluss vorliegt (2025: 850,17 Mio. €). Diese Jahrgänge tragen
die dritte Probe nicht — und behaupten sie auch nicht.

### Die Steuertabellen 1103 und 1105 — und der erste Parser, der aus dem Archiv liest

Zwei Tabellen desselben Jahrbuch-Kapitels, beide für den Steuer-Steckbrief
(`council/steuertabellen.py`):

- **1103** stellt je Steuerart den **Haushaltsplan neben das
  Rechnungsergebnis**. Das ist die einzige Stelle, an der wir die Plan-Seite je
  Steuerart bekommen: Weder `council_ergebnishaushalt` noch
  `council_ergebnisrechnung` schlüsseln Steuern auf, beide führen nur „Steuern
  und ähnliche Abgaben" als eine Summe. Der Befund: Die Gewerbesteuer wurde
  drei Jahre in Folge um über 40 % unterschätzt (2023 +42,3 %, 2024 +52,1 %,
  2025 +42,8 %).
- **1105** führt die **Realsteuer-Hebesätze seit 1980**, aber nur die
  Änderungsjahre — neun Zeilen für 45 Jahre. Ein Satz gilt bis zur nächsten
  Änderung: eine **Treppe, keine Kurve**, und dazwischen wird nichts
  interpoliert (`<Zeitreihe treppe>`, GB-01).

#### Warum dieser Parser das Archiv liest

**Tabelle 1103 führt nur drei Jahrgänge.** Erscheint die Ausgabe 2026, fällt
2023 heraus — und die Stadt hält keine alten Ausgaben online
(`1103-2024-AZ.pdf`: 404, nachgemessen am 17.08.2026; das Internet Archive hat
vom Statistik-Verzeichnis null Schnappschüsse). Wer nur die Live-Datei liest,
hat für immer drei Jahre.

Seit #603 sichert `scripts/archive_statistik.py` täglich jede Ausgabe. Weil der
Dateiname den Jahrgang trägt, ist jede Ausgabe ein eigener Ordner — die alten
bleiben stehen. `council/archiv.neueste_je_datei()` holt **je Ausgabe** ihre
zuletzt gesicherte Fassung, älteste zuerst; bei gleichem Jahrgang gewinnt die
jüngere (sie trägt das abgerechnete Ergebnis, wo die ältere ein vorläufiges
auswies). Die Reihe wächst damit um einen Jahrgang pro Jahr.

Mit `council/archiv.py` steht der **Aufbau** des Archivs an einer Stelle;
`scripts/archive_statistik.py` importiert ihn von dort, statt ihn selbst zu
definieren. Es schreibt weiterhin allein — es tut es nur nicht mehr nach
eigenen Regeln.

#### Die Jahresbeschriftung: die Lehre aus Datensatz 1106

Datensatz 1106 war um ein Jahr zu früh beschriftet, und es fiel jahrelang
niemandem auf, weil jede einzelne Zahl für sich plausibel aussah. Beide
Tabellen hier werden deshalb gegen eine zweite Quelle gehalten, **bevor** etwas
gespeichert wird:

- **1103** — jedes Rechnungsergebnis steht ein zweites Mal in Tabelle 1104, die
  ihre Jahre einzeln beschriftet (`council_steuern`, 1998–2025). Für 2023, 2024
  und 2025 nennen beide in **allen sechs** Steuerarten denselben Betrag. Das ist
  zugleich das Aufnahmekriterium: **Ein Jahrgang ohne diese Zweitquelle kommt
  nicht herein** (`istabgleich`).
- **1105** hat keine Tabelle mit denselben Zahlen. Geprüft wird deshalb der
  **Zeitpunkt der Wirkung** (`sprungjahrprobe`): Wo der Grundsteuer-Hebesatz
  stieg, muss das Aufkommen im *genannten* Jahr stärker steigen als im Jahr
  danach.

  | Änderungsjahr | Hebesatz B | Aufkommen im Jahr | im Jahr danach |
  |---|---|---|---|
  | 2002 | 360 → 410 | +14,55 % | +1,71 % |
  | 2011 | 410 → 430 | +9,31 % | −0,64 % |
  | 2015 | 430 → 445 | +8,48 % | +0,19 % |

  Und die Gegenprobe: Unterstellt man die Änderung ein Jahr später, reißt die
  Rechnung in allen drei Fällen (+1,71 gegen +1,73 · −0,64 gegen +0,56 · +0,19
  gegen +0,81). Beide Richtungen des Versatzes sind damit ausgeschlossen, nicht
  bloß unplausibel.

  Drei der acht Änderungen sind so prüfbar. Die fünf von 1984 bis 1997 liegen
  vor dem Beginn der Aufkommensreihe (1998), und **2025 ist es nicht** — dort
  hat die Grundsteuerreform die Bemessungsgrundlage mitverändert
  (`BEMESSUNG_NEU`). Das steht als Ausnahme im Code, damit der Lauf nicht in
  dem Moment bricht, in dem 2026 in der Ist-Reihe steht.

#### Der Pflicht-Kontext: Hebesatz nie ohne Aufkommen

2025 stieg der Grundsteuer-B-Hebesatz von 445 auf 539 (+21 %). „Grundsteuer
+21 %" allein wäre falsch verstanden: Das **Aufkommen sank** im selben Jahr von
34,17 auf 32,59 Mio. € (−4,6 %), weil die Reform gleichzeitig alle Messbeträge
umstellte. Ein höherer Satz auf eine kleinere Grundlage ist nicht mehr Geld.

Deshalb liefert der Endpunkt `bemessung_neu` mit, und die Seite stellt zu
**jeder** Änderung das Aufkommen desselben Jahres daneben — nicht als Fußnote,
sondern in derselben Zeile. Wo es keines gibt (vor 1998), steht das da.

## Herkunft: woher jede einzelne Zahl stammt

Jede Zeile der Tabellen oben trägt eine `herkunft_id`. Sie zeigt auf
**`council_herkunft`** — einen Datensatz je Dokument-und-Abschnitt mit:

| Feld | Was drinsteht | Beispiel |
|---|---|---|
| `art` | `ris` · `opendata` · `stadt` · `lsn` | `ris` |
| `dokument_id` | `council_anlagen.document_id` — der **stabile Anker** | `280863` |
| `label` / `url` | wie das Dokument heißt und wo es liegt | „Jahresabschluss 2024 …" |
| `fundstelle` | wo **im** Dokument gelesen wurde | „Abschnitt 6.3.1 — Erläuterungen …" |
| `seite` | Seitenzahl, wo das Dokument eine trägt | `161` |
| `probe` | die bestandene(n) Rechenprobe(n) | `strukturprobe,vorjahreskette` |
| `probe_ergebnis` | ihr Messwert | „0.00 % Abweichung zur Gesamtrechnung" |
| `stand` | Stichtag des **Inhalts**, nicht des Abrufs | „Jahresabschluss 2024" |
| `fetched_at` | zuletzt bestätigt (wandert nur vorwärts) | |

Warum eine eigene Tabelle statt Spalten je Zieltabelle — die Begründung steht
ausführlich im Modulkopf von `council/herkunft.py`, kurz:

1. **Eine Zieltabelle trägt Zeilen aus mehreren Dokumenten.** Bei den
   Beteiligungen ist das der Normalfall: dieselbe Kennzahl im
   Konzernabschluss, im Einzelabschluss der Gesellschaft und im
   Beteiligungsbericht, mit verschiedenen Stichtagen und
   Konsolidierungsstufen. Verschiedene Dokumente heißen automatisch
   verschiedene Herkunfts-Datensätze — ohne dass eine Tabelle dafür etwas
   wissen muss.
2. **Ein neues Herkunftsfeld darf nicht zwölf `ALTER TABLE` kosten.** So viele
   Tabellen stehen inzwischen in `HERKUNFT_TABELLEN`, und es werden mehr.
3. **Wiederholung.** Ein Jahresabschluss-Jahrgang schreibt rund 200 Zeilen aus
   demselben Abschnitt hinter derselben Probe.

Die alten Spalten (`quelle_label`, `quelle_url`, `source_url`) **bleiben** und
werden weiter aus derselben Angabe gefüllt. Sie zu entfernen hieße, neun der
zwölf Tabellen neu zu schreiben, darunter vier, deren Inhalt nur über einen
Download von oldenburg.de wiederzubeschaffen wäre — kosmetischer Gewinn,
echtes Risiko. Die drei jüngsten (beide Konzern-Tabellen und der
Städtevergleich) sind erst mit der Herkunft entstanden und tragen gar keine
Altspalten; im Nachrüst-Weg stehen sie trotzdem, weil ein Eintrag „nichts
nachzutragen" billiger ist als eine Ausnahme (`_HERKUNFT_ALTFELDER`).

`GET /api/council/haushalt` liefert die Datensätze als `herkunft`, nach ID
nachschlagbar, samt eines Erklärsatzes je Probe für die Oberfläche.

:::note[Was die Seite davon zeigt — und was seit 16.08. nicht mehr]
Der Block „Woher diese Zahlen kommen" auf `/haushalt/konzern` und
`/haushalt/vergleich` zeigt **`fundstelle` und `stand`**, sonst nichts. Das
ist die Angabe, mit der man eine Zahl in einem 300-Seiten-PDF wiederfindet —
sie hat einen Adressaten außerhalb dieses Projekts.

`proben` und `probe_ergebnis` standen bis dahin daneben, auf der
Vergleichsseite dreimal je Seite: die Erklärsätze aus `herkunft.PROBEN` und
darunter „Gemessen: 0,00 % Abweichung". Das war dieselbe
Selbstvergewisserung wie die Gegenproben-Tabelle einen Abschnitt weiter
unten — es sagt etwas über uns, nichts über den Haushalt
(`DESIGNSPRACHE.md` § 7). **Die Felder bleiben** in der Tabelle, in der API
und in `herkunft.PROBEN`: Sie sind der Weg, auf dem sich Jahre später
nachvollziehen lässt, woran ein Jahrgang gemessen wurde. Wer eine neue Probe
baut, trägt ihren Erklärsatz weiter dort ein — er wird nur nicht mehr
ausgestellt.
:::

### Vom Beleg zum Dokument

Das Quellenverzeichnis am Fuß jeder Haushalts-Seite beschreibt eine Quelle
**über alle Jahrgänge hinweg** („Die Jahresabschlüsse 2017–2024"). Das ist
Absicht — es ist eine redaktionelle Zusammenfassung, keine Angabe, die aus
einer Zeile fällt. Genau daran scheiterte aber sein Link: Eine Adresse, die
für acht Jahrgänge zugleich stimmt, ist bei sechs Quellen die **Startseite**
des Ratsinformationssystems gewesen. Wer dort landete, durfte selbst suchen.

`GET /api/council/haushalt/dokumente` liefert die fehlende Ebene: je
Quellenschlüssel eine Liste `{jahr, url, label, fundstelle, seite}`. Die
Zuordnung Quelle → Tabelle steht in `CouncilStore._DOKUMENT_QUELLEN`; sie ist
die einzige Stelle, an der Backend-Code die Schlüssel des Frontend-
Verzeichnisses kennt, und das mit Grund: Welche Zeile aus welchem Dokument
stammt, weiß nur die Datenbank.

Drei Regeln, die die Oberfläche daraus ableitet
(`web/frontend/lib/haushalt-dokumente.ts`):

1. **Der Link folgt dem gezeigten Jahr.** Wechselt der Jahr-Umschalter, führt
   derselbe Beleg auf ein anderes PDF.
2. **Kein Jahrgang wird verschwiegen.** Hat die Seite kein Jahr, oder liegt
   für ihres kein Dokument vor, nimmt sie das jüngste und **schreibt den
   Jahrgang an** („Jahrgang 2024").
3. **Kein Link verspricht mehr, als er hält.** Fehlt ein Dokument, bleibt die
   statische Adresse — aber der Linktext wird aus ihr abgeleitet und heißt
   dann „Im Ratsinformationssystem suchen" statt „Dokument öffnen".

Ein Jahrgang darf mehrere Dokumente tragen: Die Produktebene verteilt sich auf
rund neun Teilhaushalts-Anlagen. Die API nennt alle; das Verzeichnis listet
sie, der Beleg-Chip verweist auf die Langfassung.

:::note[Was der Altbestand mitbringt — und was nicht]
Das Nachrüsten übernimmt aus den alten Feldern Label und URL und löst über die
URL zusätzlich die `document_id` in `council_anlagen` auf. **Fundstelle und
Probe bleiben leer bzw. tragen `unbekannt`:** Der Altbestand hält nicht fest,
an welchem Abschnitt er gelesen wurde und welche Probe er bestanden hat. Das
zu erfinden — „steht schon meistens in Abschnitt 6.3.1" — wäre genau die Sorte
Angabe, die diese Umstellung abschaffen soll. Der nächste Einlese-Lauf trägt
beides nach, weil er den Jahrgang ohnehin ersetzt; `herkunft_aufraeumen()`
räumt die abgelösten Datensätze weg.
:::

### Gesetze sind keine Belege

Neben den Rechtsgrundlagen der Steuer-Steckbriefe steht seit 08/2026 ein
zweiter Chip: eine **Waage** statt einer Ziffer. Ein Klick erklärt die Stelle
in zwei Sätzen und führt zum amtlichen Volltext — Bundesrecht beim Bundesamt
für Justiz, Landesrecht im niedersächsischen Vorschrifteninformationssystem
(VORIS). Register: `web/frontend/lib/gesetze.ts`, Chip:
`components/haushalt/gesetz.tsx`.

**Warum er nicht mitgezählt wird.** Der Beleg-Apparat beantwortet genau eine
Frage: „Woher kommt diese *Zahl*?" Jede Ziffer im Verzeichnis zeigt auf ein
Papier, aus dem wir gelesen haben. Aus einem Gesetz haben wir keine Zahl
gelesen — es sagt, warum es die Zahl überhaupt gibt. Beides in eine
Nummernfolge zu werfen hieße, das Verzeichnis um eine zweite Bedeutung zu
erweitern, die niemand ansagt. Deshalb: dasselbe Fähnchen (`useFaehnchenLage`
ist aus `quelle.tsx` exportiert, nicht nachgebaut), dieselbe Bedienung,
anderes Zeichen, außerhalb der Nummerierung.

Im Fähnchen steht außerdem, ob **Bund oder Land** die Vorschrift gemacht hat.
Das ist keine Deko, sondern die Anschlussfrage: Wer könnte das ändern? Beim
Hebesatz ist die Antwort „der Rat", beim Steuergeheimnis „der Bundestag" —
dazwischen liegt der Unterschied zwischen einer politischen und einer
rechtlichen Grenze.

:::caution[Nicht das nächstliegende Bundesgesetz nehmen]
Niedersachsen hat bei der Grundsteuerreform die Öffnungsklausel genutzt und
ein eigenes Gesetz beschlossen (NGrStG, Flächen-Lage-Modell). Ein Link auf
§ 15 und § 25 GrStG hätte auf Vorschriften gezeigt, nach denen in Oldenburg
**niemand** zahlt. Beim Eintragen fiel dabei auf, dass auch die Erklärung
selbst das Bundesmodell beschrieb („für jedes Grundstück einen neuen Wert",
Messzahl „nach bundesweit gleichen Regeln") — beides korrigiert. Wer eine
Vorschrift ergänzt, sieht deshalb je Steuerart nach, statt vom Bundesrecht
auszugehen.

Praktische Folge für die Adressen: Bundesrecht liegt unter sprechenden Pfaden
(`gesetze-im-internet.de/gewstg/__16.html`), VORIS vergibt UUIDs. Die lassen
sich nicht raten — dort suchen und die Adresse kopieren.
:::

Stufen ohne einzelne Vorschrift tragen **keinen** Chip. „Der Rat beschließt
die Satzung und die Sätze" beruht auf keiner Norm, die man aufschlagen könnte;
ein Link auf irgendein nahes Gesetz wäre schlechter als keiner.

### Was ein neuer Parser tun muss

Drei Schritte, mehr nicht:

1. **Eine `Herkunft` bauen.** `art` und `probe` sind Pflicht — eine Herkunft
   ohne Probe lässt sich nicht konstruieren (`ValueError`). Trägt die Quelle
   wirklich keine Rechenprobe, ist das ausdrücklich zu sagen:
   `probe=herkunft.UNGEPRUEFT`. Dazu mindestens ein Verweis (`dokument_id`
   oder `url`), und so viel von `fundstelle`, `seite`, `probe_ergebnis`,
   `stand`, wie das Dokument hergibt. Leer ist erlaubt, geraten nicht.
2. **Sie an die `save_*`-Methode geben** — sie steht dort, wo früher
   `label, url` bzw. `source_url` standen. Der Store trägt sie ein
   (`merke_herkunft`, idempotent über einen Fingerabdruck der Inhaltsfelder)
   und verknüpft die Zeilen.
3. **Die Zieltabelle in `herkunft.HERKUNFT_TABELLEN` eintragen.** Damit
   bekommt sie ihre `herkunft_id`-Spalte beim nächsten Öffnen und wird beim
   Nachrüsten aus den Altfeldern mitversorgt.

   **Geprüft und aufgeräumt wird aber nicht nach dieser Liste, sondern nach
   dem Schema** (`store._herkunft_verweistabellen()` sucht jede Tabelle mit
   einer `herkunft_id`-Spalte). Der Grund ist genau dieser Schritt 3: Er ist
   der, den man vergisst — und wer seine Tabelle mit `herkunft_id` schon im
   `CREATE TABLE` anlegt (so die neueren), merkt davon beim Anlegen nichts.
   Ginge das Aufräumen nach der Liste, hätte eine vergessene Tabelle aus
   dessen Sicht keine Verweise: Ihre Herkünfte gälten als verwaist und fielen
   weg, während ihre Zeilen weiter auf deren Nummern zeigen. Weil die Nummern
   neu vergeben werden, zeigte so eine Zeile am Ende nicht ins Leere, sondern
   auf ein **fremdes Dokument** — und `herkunft_luecken()` schwiege dazu, weil
   auch sie nur die Liste durchginge.

   So gemeldet wird jede Zeile ohne Herkunft, auch aus einer Tabelle, die die
   Liste nicht kennt. Die Ingest-Skripte geben das nach jedem Lauf aus; leer
   ist der Sollzustand.

Eine **neue Rechenprobe** braucht einen Eintrag in `herkunft.PROBEN` — Name
plus einen Satz für Leserinnen, denn der Satz landet über die API im Beleg und
beantwortet dort „warum soll ich das glauben?". Ein unbekannter Probenname
fliegt beim Bauen der `Herkunft` auf, nicht erst in der Datenbank.

:::tip[Herkunft ist dokumentweit — was je Zeile schwankt, bleibt je Zeile]
Die Prüfungsfeststellungen führen ihre **Textziffer** und ihre **Seite**
selbst; das ist ihre Fundstelle, und sie ist für jede Feststellung eine
andere. Die Herkunft beschreibt das Dokument und den Abschnitt, aus dem ein
Lauf gelesen hat — nicht die Zeile darin. Wer beides vermischt, bekommt so
viele Herkunfts-Datensätze wie Datenzeilen und hat nichts gewonnen.
:::

:::tip[Eine Einheit wird einmal versorgt — und zwar vom ersten Dokument]
Dieselbe Zeile kann in **zwei** Anlagen stehen: Sechs (Jahrgang,
Teilhaushalt)-Paare hängen an zwei Vorlagen — dieselbe PDF-Datei, ein zweites
Mal unter einem anderen Tagesordnungspunkt hochgeladen. Da die `save_*`-
Methoden bei gleichem Schlüssel die ganze Zeile ersetzen, gewinnt sonst das
zuletzt gelesene Dokument, und welches das ist, entscheidet die Sortierung der
Kandidaten. Das ist keine Kosmetik: Es steht danach in der Zeile, und
„TOP 5 - Anlage III - THH 08“ sagt außerhalb seiner Sitzung nichts.

`lies_teilhaushalte` überspringt deshalb, was schon versorgt ist; maßgeblich
ist das Dokument mit der **kleinsten `document_id`** — die getfile-Nummer des
Ratsinformationssystems steigt mit jedem Upload, das erste Dokument ist also
die Anlage der Haushaltsvorlage selbst. Weichen die Zahlen des zweiten
Dokuments ab, wird **gemeldet statt überschrieben**: Ein Nachtragshaushalt,
der einen Ansatz wirklich ändert, ist eine Entscheidung für einen Menschen,
nicht für einen unbeaufsichtigten Lauf.
:::

:::caution[Plan ist nicht Ist]
`council_haushalt` enthält **Planwerte** (was der Rat beschlossen hat),
`council_steuern` **Ist-Werte** (was tatsächlich geflossen ist). Die beiden
dürfen nie in einem Satz vermischt werden — im Frontend stehen sie in
getrennten Bausteinen, und die Prompt-Bausteine der KI-Frage
(`_haushalt_block`, `_steuern_block`) sagen dem Modell ausdrücklich, was sie
sind. Seit `council_ergebnisrechnung` dazukam, gilt dasselbe für den
Jahresabschluss (`_ist_block`): Er ist die einzige Quelle, die **beides**
führt, und benennt deshalb je Zahl, ob sie geplant oder abgerechnet ist.
:::

:::note[Der ganze Bestand hängt an der KI-Frage]
Alle Tabellen dieser Seite sind auch Quellen von „Frag den Rat". Welche eine
Frage zieht, entscheidet `qa.geld_facetten` am Frage-Wortlaut — die Tabelle
dazu steht unter
[KI-Pipeline → Frag den Rat](/docs/ki-pipeline/#frag-den-rat-welche-quelle-eine-geldfrage-zieht).
Wer hier eine Tabelle hinzufügt, hat sie damit **noch nicht** in der KI-Frage:
Dazu gehören eine Facette, eine Methode im Store (`*_fuer_begriffe`, wenn die
Suchbegriffe die Auswahl steuern, sonst `*_kontext`), ein Prompt-Baustein und
eine Zeile im Korpus `tests/test_qa_geldquellen.py`.

Am 17.08. hing genau das an vier Schichten nach: Schulden, Investitionen,
Stellenplan und Änderungslisten waren im Bereich längst da und in der KI-Frage
unsichtbar. Drei davon wurden sogar **falsch** beantwortet, weil ihre Wörter
im Muster einer anderen Facette standen — „Wie viel Schulden hat Oldenburg?"
zog den Ergebnishaushalt, in dem der Schuldenstand gar nicht vorkommt. Wer die
nächste Tabelle anbindet, prüft deshalb nicht nur, ob seine Facette feuert,
sondern auch, ob sie einer anderen etwas wegnimmt oder ihr etwas anhängt.
:::

## Der Bereich hält sich selbst aktuell

**Neunzehn** Datenschichten, jede einmal von Hand eingelesen — ohne Cron
veraltet der ganze Bereich still, sobald niemand mehr daran denkt.
`check_finanzdaten.py` (alle zwei Wochen) nimmt das ab: **Neun** liest er
selbst nach (sie liegen als Anlage im Ratsinformationssystem), die **zehn**
übrigen werden nur beobachtet — er meldet, dass ein Jahrgang fällig wäre, und
nennt Quelle und Skript. Sieben davon kommen von außerhalb, drei liegen zwar
im Ratsinformationssystem, haben aber eigene Einlese-Skripte. „Lädt nichts herunter" ist
die Regel, an der dieser Job hängt. Maßgeblich ist `finanzquellen.REIHENFOLGE`;
diese Doku zählt nach, sie legt nichts fest.

**Bestandsgesteuert, nicht kalendergesteuert.** Der Job fragt nicht „ist es
September?", sondern *„welche Einheit fehlt mir, und liegt inzwischen ein
Dokument dafür vor?"*. Ein Job, der im September nach dem Jahresabschluss
sucht, bricht in dem Jahr, in dem die Stadt später dran ist. So ist der Takt
egal: Verspätungen, Nachtragshaushalte und nachgereichte Prüfberichte sind
automatisch abgedeckt, und der Job darf beliebig oft laufen.

:::danger[Einheit, nicht Jahrgang]
Die kleinste Einheit ist **nicht** der Jahrgang, sondern das Dokument
beziehungsweise die Ebene: Ein Produkt-Jahrgang verteilt sich auf rund neun
Teilhaushalts-Anlagen, ein Jahresabschluss auf zwei Ebenen (Gesamtrechnung und
Teil-Ergebnisrechnungen). **„Jahr ist da" heißt nicht „Jahr ist vollständig".**

Und die Teile kommen nicht gleichzeitig. `check_protocols.py` legt eine Anlage
zunächst ohne Volltext an (`n_pages = 0`, `status = 'listed'`); den Text holt
`backfill_anlagen_texte.py` später und in Tranchen. Zwischen zwei Läufen liegt
also regelmäßig ein Jahrgang, von dem die Hälfte lesbar ist — kein Sonderfall,
sondern Normalbetrieb. Ein Bestand je Jahrgang sperrt ihn nach dem ersten
Dokument und verliert die übrigen acht **dauerhaft**, ohne dass etwas auffällt:
Das Jahr steht in der Tabelle, ist also nicht überfällig, und keine Meldung
schlägt an.

Deshalb führt `council/finanzquellen.py` den Bestand als Menge von Einheiten —
Tupel, deren erstes Element immer der Jahrgang ist:

| Datenart | Einheit | Beispiel |
|---|---|---|
| Jahresabschluss | Ebene | `(2024, "gesamt")`, `(2024, "teilhaushalte")` |
| Teilhaushalts-Pläne | Teilhaushalt | `(2024, 7)` |
| Schlussbericht, Prüfungsfeststellungen, Gesamtabschluss, Haushaltsplan | der Jahrgang selbst | `(2024,)` |

Den Schlüssel eines Teilhaushalts-Plans liefern Textkopf und Label zusammen:
der Jahrgang aus der ersten Ansatzspalte, die Nummer aus `THH\s*0*(\d+)` im
Label. Gegen alle 79 Teilhaushalts-Anlagen des Bestands geprüft — das Paar
trifft immer genau das, was `parse_teilergebnishaushalt` am Ende vergibt.
:::

Aus acht Jahrgängen Sitzungsdaten (`council_sessions.session_date` über
`council_agenda_items`) ergibt sich der Rhythmus der Stadt:

| Was | Wann im Rat | Versatz zum Jahrgang | Ausnahmen |
|---|---|---|---|
| Jahresabschluss + RPA-Schlussbericht + Rechenschaftsbericht | **Anfang September** | + 1 Jahr | 1× August |
| Haushaltsplan mit Gesamtergebnishaushalt, Teilhaushalten und Stellenplan | **Anfang Oktober** | Plan und Stellenplan: − 1 Jahr · Teilhaushalte: ± 0 | 1× November |
| Konsolidierter Gesamtabschluss (Prüfbericht des RPA) | **Februar** | + 2 Jahre | Juni bis Februar |

Der dritte Takt kam mit dem Konzern-Bereich dazu und ist der langsamste: Ein
Gesamtabschluss entsteht erst, wenn alle einbezogenen Betriebe geprüft sind,
und liegt damit rund zwei Jahre hinter seinem Haushaltsjahr. Deshalb steht auf
`/haushalt` der Plan für das kommende Jahr und auf `/haushalt/konzern` eine
Rechnung von vorgestern — beides richtig, beides erklärt der Datenstand-Block.

Der Monat steuert **nicht** die Suche, sondern nur die Meldung: Bleibt ein
Jahrgang länger als vier Wochen über seinen üblichen Monat hinaus aus, geht ein
Hinweis an `ALERT_EMAIL` — kein Fehler, sondern die Frage, ob die Stadt spät
dran ist oder ein Erkennungsmuster nicht mehr greift. Die Mail unterscheidet
beides: Liegt ein passendes Dokument vor und wird trotzdem nichts übernommen,
steht das ausdrücklich drin. Gemeldet wird nur, wenn sich die Liste gegenüber
dem letzten Lauf geändert hat (Vergleich über `job_runs`) — alle vierzehn Tage
dieselbe Mail wäre eine, die niemand mehr liest.

Dieselbe Mail trägt seit dem 20.08.2026 einen dritten Block: **Zeilen, die
dastehen, ohne zu sagen, woher sie kommen** (`store.herkunft_luecken()`). Der
Befund wurde vorher nur ins Cron-Log geschrieben und als Kennzahl ins
Admin-Panel gereicht — er stand nicht in `ausbleibend` und löste deshalb nie
eine Mail aus. Das war die stillste der drei Lagen: Ein fehlender Jahrgang
fällt in jeder Jahresliste auf, eine Zahl ohne Beleg nicht — der Jahrgang steht
da, die Zahl steht da, und erst wer auf den Herkunfts-Chip tippt, merkt etwas.

Wichtig für die Einschätzung, wann dieser Block überhaupt erscheint: Bei den
neun Schichten, die der Job selbst einliest, **heilt** er eine solche Lücke
beim nächsten Lauf — die Einheit gilt als offen und wird samt frischer Herkunft
neu geschrieben. Liegen bleibt sie nur dort, wo niemand automatisch nachzieht,
also in den sechs Schichten von außerhalb. Der Wiederholungs-Schlüssel führt
die **Zahl** mit (`herkunft:<tabelle>:<n>`): Wächst die Lücke von einer Zeile
auf dreihundert, ist das eine neue Nachricht und keine Wiederholung.

:::note[Woher der Jahrgang kommt]
`council_anlagen.fetched_at` trägt bei **allen** Finanzdokumenten den
10.08.2026 — den Tag des Volltext-Backfills. Als Veröffentlichungsdatum ist das
Feld wertlos. Der Jahrgang kommt deshalb aus dem Dokument selbst: aus dem Label
(Jahresabschluss), dem Textanfang (Prüfberichte) oder der ersten Ansatzspalte
im Tabellenkopf (Teilhaushalts-Pläne).

Bei den Teilhaushalts-Plänen ist das nicht dasselbe wie die Jahreszahl im
Dateinamen: „2024 007 IVw THH01" ist der Haushaltsplan **2024**, seine erste
Ansatzspalte trägt **2023** — und genau die übernimmt der Parser (alles danach
ist mittelfristige Finanzplanung). Wer hier das Label läse, suchte einen
Jahrgang, den die Tabelle nie zurückgibt.
:::

### Drei Regeln, die ihn unbeaufsichtigt tragen

1. **Er lädt nichts herunter.** Die Anlagen kommen über `check_protocols.py`
   ins System; der Job liest nur aus, was schon in `council_anlagen` liegt.
   Zwei Wege zu denselben Daten wären einer zu viel. Deshalb deckt er
   `council_haushalt` und die Open-Data-Schichten **nicht** ab — ihr Ausbleiben
   meldet er trotzdem, damit `ingest_haushalt.py` nicht vergessen wird.
2. **Er senkt keine Prüfschwelle.** Summenprobe, Strukturprobe, Vorjahres-Kette
   und die Rechenprobe der Erläuterungen gelten unverändert. Was sie reißt,
   kommt nicht in die Datenbank, wird gezählt und gemeldet. Ein unbeaufsichtigter
   Lauf ist der Grund, warum es diese Proben gibt — nicht der Anlass, sie zu
   lockern.
3. **Er ergänzt nur, was fehlt — Einheit für Einheit.** Eine vorhandene Einheit
   wird nicht angefasst. Zweimal hintereinander laufen ändert beim zweiten Mal
   keine einzige Zeile.

Und was ein Jahrgang bekommt, bekommt er in **einer** Transaktion
(`store.transaktion()`, verschachtelbar). Ohne die Klammer braucht ein
Jahresabschluss 1 + n + 1 Transaktionen — Gesamtrechnung, je Teilhaushalt eine,
Erläuterungen. Ein Abbruch dazwischen ließe den Jahrgang halb in der Datenbank,
und halb sieht für den nächsten Lauf aus wie fertig.

:::danger[Ein leeres Ergebnis ersetzt nie einen gefüllten Bestand]
Alle Speicherwege ersetzen einen Jahrgang: Sie löschen ihn und schreiben ihn
neu. Solange ein Mensch danebensteht, ist das richtig. Alle zwei Wochen
unbeaufsichtigt kippt die Rechnung — ändert die Stadt ihr Tabellenlayout,
liefert ein Parser irgendwann null oder halb so viele Zeilen, und wer das
speichert, tauscht einen gefüllten Bestand gegen ein kaputtes Ergebnis. Bemerkt
würde es erst, wenn die Seite leer ist.

`finanzquellen.bestandsschutz()` steht vor jedem ersetzenden Schreibvorgang:
**0 Zeilen ersetzen nie etwas**, weniger als 80 % des bisherigen Standes auch
nicht — beides wird gemeldet statt stillschweigend vollzogen. Verglichen wird
auf der Ebene, die ein Dokument abdeckt: bei den Produkten je Teilhaushalt,
nicht je Jahr, sonst sähe jedes einzelne THH-Dokument wie ein Einbruch aus.
Anlass war ein Beinahe-Unfall am 16.08.2026, bei dem ein Übertragungsskript
257 Prüfungsfeststellungen gelöscht hätte, weil die Quelltabelle leer war.

Das ist die Gegenrichtung zu den Pflicht-Proben: Die halten falsche Daten
draußen, diese Regel hält richtige drin.

**Der Schutz gilt dem unbeaufsichtigten Weg, nicht dem bewussten Handgriff.**
Wer einen verbesserten Parser über den Bestand zieht, will einen kleineren
Jahrgang oft genau so — ein früherer Lauf war zu großzügig. Ein Schutz, der das
blockiert, macht den einzigen Weg unbenutzbar, auf dem sich ein Parser-Fehler je
korrigieren ließe. Die Ingest-Skripte haben dafür `--auch-schrumpfen`: Der
Schrumpf wird deutlich gemeldet und dann vollzogen. Ein **leeres** Ergebnis
bleibt auch damit tabu — null Zeilen sind nie eine Absicht.
:::

### Eine Quelle für die Erkennung

Woran ein Dokument erkannt wird — Label-Muster, Mindestseitenzahl, Ausschlüsse,
Parser, Zieltabelle, erwarteter Monat — steht in **`council/finanzquellen.py`**,
je Datenart einmal. Die Ingest-Skripte und der Cron benutzen dieselbe
Definition; auf die Frage „ist das ein Jahresabschluss?" gibt es sonst zwei
Antworten, und eine davon veraltet still.

| Datenart | Erkennung | Zieltabelle | Erwartet |
|---|---|---|---|
| Jahresabschluss | Label `%Jahresabschluss%`, > 100 Seiten, **ohne** `%Rechenschaft%` / `%Schlussbericht%` | `council_ergebnisrechnung` (+ `council_abweichungsgruende`) | September, Jahrgang + 1 |
| Schlussbericht des RPA (Fundstelle) | Label `%chlussbericht%` **oder** Text beginnt mit `Schlussbericht`; entschieden am Textanfang | `council_pruefbericht_quellen` | September, Jahrgang + 1 |
| Prüfungsfeststellungen | Text `%Rechnungsprüfungsamtes%`, > 30 Seiten; entschieden am Textanfang | `council_pruefberichte` | September, Jahrgang + 1 |
| Teilhaushalts-Pläne | Label `%THH%`, > 40 Seiten | `council_produkte` | Oktober, Jahrgang + 0 |
| Gesamtergebnishaushalt | Label `%Gesamtergebnishaushalt%`, > 10 Seiten; Jahrgang aus dem **Tabellenkopf** (vier der acht Dokumente tragen keine Jahreszahl im Label) | `council_ergebnishaushalt` | Oktober, Jahrgang − 1 |
| Stellenplan | Label `%Stellenplan%`, > 10 Seiten, **ohne** `%eändert%`; Jahrgang aus dem **Tabellenkopf** (drei Schreibweisen im Label, eine mit zwei Jahreszahlen) | `council_stellenplan` | Oktober, Jahrgang − 1 |
| Konsolidierter Gesamtabschluss | **nur** Text (`konzernabschluss.TEXT_MUSTER`), > 40 Seiten — die Labels dieser Reihe sind wertlos | `council_konzern_posten` (+ `council_konzern_traeger`) | Februar, Jahrgang + 2 |
| Haushaltsplan | *(kein Anlagen-Muster — Download)* | `council_haushalt` | Oktober, Jahrgang − 1 |
| Steuerkraft im Städtevergleich | *(kein Anlagen-Muster — Download beim LSN)* | `council_staedtevergleich`, Reihe `steuerkraft` | April, Jahrgang + 0 |
| Realsteuervergleich (Hebesätze, Steuereinnahmekraft) | *(kein Anlagen-Muster — Download beim LSN)* | `council_staedtevergleich`, Reihe `realsteuern` | November, Jahrgang + 1 |

:::note[Warum der Städtevergleich zwei Zeilen bekommt]
Beide Reihen liegen in derselben Tabelle, aber ihre Jahresangaben bedeuten
Verschiedenes: Beim Finanzausgleich ist es das **Ausgleichsjahr** (es läuft dem
Kalender voraus — „KFA 2026" erscheint im März 2026), beim Realsteuervergleich
das **Berichtsjahr** (es hinkt nach — der Bericht 2025 erschien im Juli 2026).
Als eine Zeile ergäbe das die Spanne „2023–2026", in der zwei Jahresangaben
dasselbe zu meinen scheinen. Genau diese Verwechslung ist der Grund, warum der
Städtevergleich überhaupt eine eigene Tabelle hat.

Die Monate sind an den Dateien nachgesehen, nicht geschätzt: Die
**endgültigen** KFA-Tabellen tragen den Stand 25.04.2023, 02.04.2024,
25.03.2025 und 26.03.2026; die Realsteuervergleiche erschienen im Juni 2022,
August 2023, November 2024, November 2025 und Juli 2026. Als Schwelle steht
jeweils der **späteste** gemessene Monat — zu früh gemeldet wäre der teurere
Fehler. Und beim Finanzausgleich zählt ausdrücklich die endgültige Fassung: Die
vorläufige erscheint schon im November davor, enthält aber gar kein Blatt
`ST_KR_MESS_VGL` und kann die Schicht deshalb nicht füllen.
:::

Der Städtevergleich (`council_staedtevergleich`) steht **nicht** in dieser
Tabelle: Seine Quellen sind Tabellenmappen des Landesamts, keine Anlagen im
Ratsinformationssystem, und sie erscheinen einmal jährlich. Er hat deshalb
weder Erkennung noch Cron — und taucht folgerichtig auch im Datenstand-Block
nicht auf.

### Der Datenstand ist sichtbar

`GET /api/council/haushalt/datenstand` liefert diese Matrix live aus dem
Bestand; der Block **„Bis wann die Zahlen reichen"** am Fuß von `/haushalt`
(`components/haushalt/datenstand.tsx`) zeigt sie.

Das ist kein Entwickler-Feature. Auf `/haushalt` steht der Plan für 2026, auf
`/haushalt/plan-ist` die Abrechnung für 2024, auf `/haushalt/pruefung`
Feststellungen bis 2023, auf `/haushalt/konzern` eine Rechnung bis 2024 — die
Frage „warum steht hier 2024 und nicht 2025?" müsste sonst auf jeder der zwölf
Unterseiten einzeln beantwortet werden. Die Ursache ist immer
dieselbe und liegt bei der Stadt. Wo ein Jahrgang erwartet wird, aber noch
fehlt, steht das ausdrücklich da: *„Der Jahrgang 2025 wird üblicherweise im
September 2026 vorgelegt."* Das Wort „fehlt" kommt nicht vor — was die Stadt
noch nicht veröffentlicht hat, fehlt uns nicht.

**Ein halber Jahrgang gibt sich zu erkennen.** Sonst stünde er in derselben
Jahresspanne wie ein vollständiger und sähe aus wie einer: *„Für 2023 haben wir
6 von 9 Teilhaushalten."* / *„Für 2024 fehlt noch die Aufteilung auf die
einzelnen Bereiche."* Der Maßstab ist der bestbelegte Jahrgang desselben
Bestands — mehr wissen wir nicht, und weniger zu behaupten wäre falsche
Bescheidenheit.

Auch die Fußzeile verspricht nur, was sie halten kann. „Wir tragen neue
Jahrgänge automatisch nach" galt pauschal für die ganze Liste — deren erste und
prominenteste Zeile aber der Haushaltsplan ist, den der Cron gar nicht anfasst.
Jetzt nennt sie die Schichten, die **nicht** automatisch nachkommen, beim
Namen, und zieht die Liste aus den Daten: `automatisch === false`.

**Auch die Stelle dahinter kommt aus den Daten.** Der Satz endete bis 08/2026
auf „— die Zahlen dafür holen wir vom Portal der Stadt", was stimmte, solange
der Haushaltsplan die einzige Schicht von Hand war. Mit dem Städtevergleich
kamen zwei Reihen einer **Landesbehörde** dazu; der feste Satz hätte das
Landesamt für Statistik zur Stadtverwaltung erklärt. Die Fußzeile gruppiert die
Schichten deshalb nach ihrer Quelle (`quelle`, aus `finanzquellen.STELLEN`) und
nennt sie in Klammern. Dieselbe Falle steckte in der Cron-Meldung, die pauschal
zu `scripts/ingest_haushalt.py` schickte — welches Skript zuständig ist, steht
jetzt bei der Schicht (`Finanzquelle.nachschub`).

**Und sonst steht dort nichts mehr.** Zwei Sätze sind am 16.08. aus der
Fußzeile gefallen, beide über unseren Betriebsablauf statt über den
Datenstand: der Takt, in dem der Cron nachsieht („geprüft wird alle zwei
Wochen" — er steht in `finanzquellen.REIHENFOLGE` und weiter oben in diesem
Kapitel), und die Rechenprobe als Türsteher („Zahlen, die eine Rechenprobe des
Dokuments nicht bestehen, bleiben draußen" — Kapitel „Vier Prüfungen"). Beides
läuft unverändert weiter. Für die Frage, die dieser Block beantwortet — *bis
wann reichen die Zahlen?* — war es keine Antwort: Wo ein Jahrgang wirklich
fehlt, sagt das die Zeile darüber aus `luecken`, am richtigen Ort und ohne
Prüfzeugnis (`DESIGNSPRACHE.md` § 7).

Der Städtevergleich ist überhaupt der Fall, für den der Ausblick gebaut ist: Es
gibt kein Dokument im Ratsinformationssystem, an dem ein Cron merken könnte,
dass ein Jahrgang vorliegt, und geholt wird nur **einmal im Jahr** von Hand. An
eine Handreichung, die zwölf Monate zurückliegt, erinnert sich niemand von
selbst — die Meldung „Der Jahrgang 2026 wäre seit November 2027 zu erwarten"
ist der einzige Wecker, den diese Schicht hat.

## Die redaktionelle Schicht

Fünf Dinge liefert keine Datenquelle. Sie stehen als gepflegte Konstanten im
Frontend, damit sie überprüfbar bleiben:

- **`lib/haushalt-bereiche.ts`** — das Bereichs-Wörterbuch: je Teilhaushalt ein
  kanonischer Schlüssel, die Alias-Liste **jeder im Bestand vorkommenden**
  Schreibweise (gegen `council_haushalt`, `council_ergebnisrechnung` und
  `council_produkte` geprüft), ein Kurzname fürs Balkensegment und die eine
  Zeile Klartext, die `/haushalt/bereiche` trägt.
  Der Grund ist eine Wartungsfalle: Die Stadt benennt Teilhaushalte um,
  ohne den Zuschnitt zu ändern — Teilhaushalt 9 hat vier Schreibweisen in
  sieben Jahrgängen. Jede Map auf den exakten Namen verliert beim nächsten
  Jahrgang stillschweigend Zeilen. `bereichKanon()` gibt deshalb **immer** etwas
  zurück; ein unbekannter Name fällt auf sich selbst zurück (`bekannt: false`),
  statt zu verschwinden.
- **`lib/haushalt-steuern.ts`** — je Einnahmeart: die Stufen „Wer entscheidet
  was", Spielraum-Einstufung, Rechenbeispiel, Lotti-Erklärung.
- **`lib/haushalt-pflicht.ts`** — Einordnung der Teilhaushalte in Pflicht /
  Pflicht mit Spielraum / überwiegend freiwillig. Eine Einschätzung auf Ebene
  ganzer Teilhaushalte; die Seite sagt das auch — und hält sie seit 08/2026
  gegen die Selbstauskunft der Stadt (s. u.).
- **`lib/haushalt-vergleich.ts`** — was auf `/haushalt/vergleich` nicht aus der
  Landesstatistik kommt: die Ausgliederungs-Übersicht der sieben Städte aus
  Vorlage 18/0911 und das wörtliche Zitat der Verwaltung dazu.
- **`lib/haushalt-quellen.ts`** — Fundstellen, Datenstände und Lizenzen.

Nicht redaktionell, aber leicht damit zu verwechseln: `lib/haushalt-jahr.ts`,
`lib/haushalt-konzern.ts` und `lib/haushalt-pruefung.ts` halten **Rechenwege**
zu ihren Endpunkten, keine gepflegten Inhalte. Sie liegen im Frontend, weil es
Aussagen *über* die Jahrgänge sind („der Entwurf kam siebenmal im Oktober") und
sich mitverändern müssen, wenn ein Jahrgang dazukommt — genau das, was die
Regel „keine jahresabhängige Rechenaussage als fester Text" verlangt.

## Quellen-System

Jede Zahl trägt einen Beleg-Chip, am Seitenende steht das Verzeichnis mit
Dokument, Fundstelle, Stand, Lizenz und Direktlink. Die Nummerierung läuft
**seitenweise** über `<Quellenkontext>` — global gezählt trüge eine Seite mit
zwei Quellen die Nummern 2 und 4.

Werte, die wir selbst bilden (Anteile, Differenzen, Rücklagen-Reichweite,
Pro-Kopf-Angaben, Ein-Punkt-Überschlag), sind an Ort und Stelle als
*„unsere Rechnung, keine amtliche Kennzahl"* gekennzeichnet.

`lib/haushalt-quellen.ts` fasst die Quelle einer ganzen **Seite** in einem
Absatz zusammen. Je einzelner Datenzeile weiß es die Datenbank genauer:
`council_herkunft` (siehe [oben](#herkunft-woher-jede-einzelne-zahl-stammt))
führt Fundstelle, Probe und Anker je Dokument-und-Abschnitt.

## Jahresabschlüsse und Produktebene aus dem eigenen Bestand

Beide Dokumenttypen mussten nirgends beschafft werden: Sie hängen als Anlagen
an Ratsvorlagen und liegen mit Volltext in `council_anlagen`.

**Jahresabschluss** (300+ Seiten je Jahrgang) → die Ergebnisrechnung der
Kernverwaltung führt **Ansatz und Ergebnis nebeneinander**. Damit gibt es
„geplant gegen tatsächlich" und die Aufschlüsselung der Erträge nach Arten
(Steuern, Zuwendungen, Entgelte, Kostenerstattungen). Eingelesen sind alle
acht Jahrgänge **2017–2024**, je mit zwölf Teilhaushalten.

Dass 2017, 2018 und 2020 lange fehlten, lag nie am Text, sondern an drei
verschiedenen Spaltenlayouts: 2017 steht das Ergebnis **vor** dem Ansatz,
2018 hat elf Spalten mit sechs möglichen Leerfeldern, 2019–2024 tragen eine
meist leere Nachtragsspalte. `_spalten_zuordnen()` liest die Anordnung
deshalb aus dem **Tabellenkopf** statt aus einer festen Reihenfolge. Zwei
Kleinigkeiten kamen dazu: 2017 schreibt die Summenzeilen als „12.= Summe"
ohne Leerzeichen, und im Abschluss 2022 fällt bei THH09 ein Zeilenumbruch
mitten in die Überschrift („A. Teil\n-Ergebnisrechnung THH09") — ohne ihn im
Muster fand der Parser dort nur die Fortsetzungsseite und verwarf über die
Summenprobe die ganze Teilhaushalts-Ebene.

:::danger[„Plan" heißt nicht in jedem Jahrgang dasselbe]
Die Ergebnisrechnung vergleicht das Ist mit dem Wert, den das Dokument selbst
als Bezug führt — und der wechselt:

| Jahrgang | Bezugsgröße (`plan_art`) |
|---|---|
| 2018 | Gesamtermächtigung (Ansatz + Nachtrag + Übertragungen) |
| 2020 | Ansatz einschließlich Nachtragshaushalt |
| alle übrigen | nackter Haushaltsansatz |

Bei den Ausgaben 2020 sind das **27,2 Mio. € Unterschied** — also der
Unterschied zwischen „21,5 Mio. weniger ausgegeben als geplant" und
„5,7 Mio. mehr". Beide Werte stehen in derselben Zeile, deshalb speichert der
Parser beide: `ansatz` den ursprünglichen Haushaltsansatz, `plan` die
Bezugsgröße der Abweichung, `plan_art` welche davon. Die Oberfläche schreibt
die Bezugsgröße an (Kasten „Was ‚geplant' in diesem Jahr heißt", Fußnote in
der Mehrjahres-Kurve). Eine Kurve, die 2018 die Gesamtermächtigung und 2021
den nackten Ansatz gegen das Ist stellt, ohne das zu sagen, wäre still
falsch — und still falsch ist hier der schlechteste Ausgang.

Bestätigt wird die Zuordnung aus dem Dokument selbst: Die Prozentsätze in
Abschnitt 6.3.1 rechnen 2018 gegen die Gesamtermächtigung (3 von 3 Posten,
gegen den Ansatz nur 1 von 3) und 2020 gegen Ansatz + Nachtrag (4 von 4).
:::

### Das „Warum" zu den Abweichungen

Abschnitt **6.3.1** des Jahresabschlusses begründet jede Abweichung ab 20 %
gegenüber dem Plan, je Posten und in den Worten der Verwaltung — etwa, dass
die Mehrerträge 2024 „nahezu auf den Bereich der Gewerbesteuer" entfallen und
„unter anderem aus einem Einmaleffekt" stammen. Der Abschnitt existiert in
allen acht Jahrgängen (45 Posten, ~37.000 Zeichen).

Die Eintrittskarte ist hart: Die Überschrift nennt die Abweichung **doppelt**,
als Betrag und als Prozentsatz („+75,1 Millionen Euro, +24,82 %"). Beides muss
zu der Zeile passen, die der Tabellen-Parser für denselben Posten gelesen hat
(`pruefe_abweichungsgruende`) — damit prüft sich das Dokument an einer zweiten
Stelle selbst. 45 von 45 bestehen; was nicht passt, wird verworfen statt
angezeigt. Angezeigt wird der Wortlaut, nicht eine Zusammenfassung: nur
Silbentrennung am Zeilenende und eingestreute Seitenfüße („JA 161") werden
entfernt.

**Schlussberichte des Rechnungsprüfungsamts** werden nur **verlinkt**, nicht
ausgewertet — sie sagen selbst, dass die Plan-Ist-Abweichungen „im Anhang und
im Rechenschaftsbericht erläutert" werden. Erkannt werden sie an der
Eingangsformel, nicht am Label („Schlussbericht JA 2017" ist der Bericht zum
Eigenbetrieb Gebäudewirtschaft, weitere Treffer betreffen Stiftungen). Achtung:
Der Volltext ist umbrochen, ein `LIKE` auf die Formel findet **nichts** —
`pruefbericht_aus_anlage()` normalisiert vorher. Der Jahrgang **2024** ist ein
kaputter Textextrakt (Glyphen-Indizes statt Zeichen, Buchstabenanteil 0,00
gegen 0,71–0,76 bei den übrigen); er wird als `lesbar = 0` gespeichert und auf
der Seite so benannt, statt überspielt zu werden.

**Teilhaushalts-Pläne** (THH01–13) → die Produktebene: was einzelne Aufgaben
kosten, mit Produktnummer und zuständigem Amt (2023 etwa
„Kindertagesbetreuung" mit 71,1 Mio. € Aufwand und 58,6 Mio. €
Zuschussbedarf). Die Abdeckung ist unvollständig — für 2023 erklären die
gefundenen Produkte rund 82 % der geplanten Aufwendungen. Der Endpunkt
liefert diese Quote als `abdeckung_prozent` mit, damit die Oberfläche die
Liste nicht als Vollbild ausgeben kann.

### Die Kassensicht: Abschnitt 4.1 desselben Dokuments

Die Ergebnisrechnung **bucht**. Für 2024 weist sie ein Jahresergebnis von
+6,1 Mio. € aus. Dreißig Seiten weiter, in Abschnitt 4.1 desselben Berichts,
steht die **Finanzrechnung der Kernverwaltung** — und die **zahlt**: Am
Jahresende lagen 118,0 Mio. € in der Kasse, am Jahresanfang 143,1 Mio. €.
Beides stimmt. Abschreibungen mindern das Ergebnis, ohne dass jemand etwas
überweist; ein Neubau kostet sofort Geld, im Ergebnis aber erst über die
Jahre. Wer nur die erste Zahl sieht, bekommt einen falschen Eindruck — und für
einen Bereich, dessen Anspruch Ehrlichkeit ist, war das die unangenehmste
Lücke. Eingelesen sind alle acht Jahrgänge **2017–2024**
(`council_finanzrechnung`, Parser `parse_finanzrechnung`).

Die Tabelle hat dieselbe Grammatik wie die Ergebnisrechnung, also liest sie
derselbe Spaltenapparat (`_tabellenkopf`, `_fenster`, `_spalten_zuordnen`).
Vier Dinge sind anders, und jedes davon ist beim Bauen aufgelaufen:

**1. Die Postennummern verschieben sich.** 2017–2020 hat die Tabelle 42
Zeilen, 2021–2024 nur 41: Die Einzahlungsart „Veräußerung geringwertiger
Vermögensgegenstände" fällt weg, und alles ab Posten 08 rutscht um eins. Der
Finanzmittelsaldo ist 2019 die Zeile **33** und 2024 die Zeile **32**. Ein
fester Nummern-Katalog wie `ERGEBNIS_POSTEN` ginge für die Hälfte der
Jahrgänge daneben. Deshalb kommt die Bezeichnung aus dem Dokument und die
Bedeutung aus `finanzberichte.ROLLEN` — das Dokument benennt seine Zeilen
selbst („= Summe der Auszahlungen aus Investitionstätigkeit"). Frontend und
Proben hängen an der **Rolle**, nie an der Nummer.

**2. Die Zeilen verweisen aufeinander.** „18. Saldo aus laufender
Verwaltungstätigkeit (Zeile 10 abzüglich Zeile 17)" — ein Zeilensplit an
zweistelligen Zahlen schneidet mitten in diesen Verweis und lässt die
Zahlenkolonne dahinter liegen. Ohne `_VERWEIS` kamen die Posten 18, 33, 36,
37 und 40 in **keinem** Jahrgang an.

**3. Der Seitenfuß „JA 29" sieht aus wie ein Posten.** Er steht am Ende der
ersten Tabellenseite, also **vor** dem echten Posten 29 auf der zweiten. Wer
ihn stehen lässt, verliert „29. Sonstige Investitionstätigkeit" (2024:
27,6 Mio. €) und reißt damit die Summenprobe.

**4. Es gibt eine Spalte mehr:** die Ermächtigungen aus Haushaltsvorjahren.
2024 stehen dort **58,8 Mio. €** neben 96,4 Mio. € tatsächlichen
Investitions-Auszahlungen — bewilligtes Geld für Vorhaben, die noch nicht
fertig sind. Das ist die Antwort auf „warum wird das Geplante nicht gebaut?".
Gelesen wird sie nur, wenn der Tabellenkopf sie **hinter** dem Ergebnis
führt: 2018 steht sie als sechste von elf Spalten davor, und hinter der
Abweichung steht dort „Zu Spalte 5: Davon bisher nicht bewilligte …" mit
0,00 € in jeder Zeile — ungeprüft hätte der Jahrgang 2018 lauter
Ermächtigungen von 0,00 € getragen.

#### Neun Proben, drei Schicksale

Das Dokument rechnet sich selbst vor, und jede Stufe hängt an der vorigen
(`finanzprobe`). Was welche Probe kostet, ist bewusst abgestuft:

| Probe | Was sie prüft | Reißt sie, … |
|---|---|---|
| Summenzeilen (4×) | Einzahlungs- und Auszahlungsarten ergeben ihre Summe — je Block, im Ist **und** im Ansatz | … fällt der ganze Jahrgang |
| Salden (3×) | Einzahlungen − Auszahlungen = Saldo, und beide Salden = Finanzmittelsaldo | … fällt der ganze Jahrgang |
| Ermächtigungen | dieselbe Blocksumme für die übertragenen Beträge | … fällt die **Spalte** |
| Tilgungskette | Finanzmittelsaldo + Saldo Finanzierung = Finanzmittelveränderung | … fallen diese zwei Zeilen |
| Bestandskette | Anfangsbestand + Veränderung + haushaltsunwirksam = Endbestand | … fallen die drei Bestandszeilen |
| Kassen-Kette | Endbestand steht im **Folgejahrgang** als Anfangsbestand | … fällt die Finanzrechnung beider Jahrgänge |

Eine **fehlende** Einzelzeile zählt in den Summen als Null. Das ist kein Loch
im Beweis, sondern der Beweis: Fehlt sie, weil das Dokument sie leer lässt
(„12. Versorgungsauszahlungen" trägt 2024 nur den Vorjahreswert), geht die
Summe auf — fehlt sie, weil wir sie falsch gelesen haben, geht sie nicht auf.

Die Abstufung ist der Grund, warum trotz zweier echter Quellendefekte alle
acht Jahrgänge im Bestand sind: **2022** verliert nur seine
Ermächtigungsspalte, weil der PDF-Extrakt dort Leerzeichen mitten in die
Beträge setzt („3.912. 463,20"), und die optionalen Bestandszeilen sind laut
Fußnote des Dokuments ohnehin freiwillig („Die Zeilen 37 bis 41 können
optional ergänzt werden").

:::note[Die Bestandszeilen tragen keinen Ansatz]
Ein Kassenbestand wird nicht veranschlagt; das Dokument lässt die
Ansatzspalte dort leer. Was der Spaltenapparat dort findet, ist die
Vorjahresspalte — im Jahrgang 2018 ergab das einen „Ansatz" von 61,7 Mio. €
für den Anfangsbestand, den nie jemand beschlossen hat. Für diese drei Rollen
wird deshalb nur das Ist gespeichert (`OHNE_ANSATZ_ROLLEN`).
:::

Was der Parser **nicht** tut: aus Jahresergebnis und Kassenveränderung eine
Differenz bilden. Diese Zahl steht in keiner Quelle und hieße nichts —
dieselbe Regel, an der der „Kostendeckungsgrad" gescheitert ist.

### Die Vermögensseite: Abschnitt 2.1 desselben Dokuments

Ergebnis- und Finanzrechnung zählen ein **Jahr**. Die Bilanz zählt einen
**Stichtag**: was die Stadt am 31. Dezember hat, und wem es zusteht. Sie ist
die Antwort auf die naheliegendste Anschlussfrage der Schuldenseite —
„Oldenburg hat kaum Kredite, also keine Schulden?". Zum 31.12.2024 stehen
**43,69 Mio. €** Kredite bei Banken neben **311,79 Mio. €** Zusagen für
Pensionen und Beihilfe. Eingelesen sind neun Stichtage **2016–2024**
(`council_bilanz`, Parser `parse_bilanz` in `council/bilanz.py`); der älteste
hat kein eigenes Dokument, er stammt aus der Vorjahresspalte des Abschlusses
2017 und wird nur übernommen, wenn diese Spalte für sich ausgeglichen ist.

#### Zwei Zahlen, die beide „die Pensionsrückstellungen" heißen

Der Bilanzauszug 2024 schreibt untereinander:

```
3.      Rückstellungen                     329.095.270,90  337.210.902,05
3.1     Pensionsrückstellungen und
        ähnliche Verpflichtungen 1)        290.925.292,00  311.789.660,00
3.1.1   Pensionsrückstellungen             249.721.281,00  266.259.316,00
3.1.2   Beihilferückstellungen              41.204.011,00   45.530.344,00
```

**Beide Zahlen stimmen, sie messen nur Verschiedenes.** 311,79 Mio. € ist die
Oberposition 3.1 einschließlich der Beihilfe, 266,26 Mio. € die Pension allein
(3.1.1); die Differenz ist Position 3.1.2 und geht in jedem Jahrgang auf den
Cent auf. Der Rechenschaftsbericht bestätigt es in Worten („für die
Beihilferückstellungen wurden 17,10 % der Pensionsrückstellungen angesetzt" —
45.530.344 / 266.259.316 = 17,10 %). Wer eine der beiden Zahlen zeigt, muss
sagen welche: Deshalb heißen die Rollen `pensionen_gesamt` und
`pensionsrueckstellungen` und nicht beide „Pension", und deshalb trägt jede
Zeile ihren Wortlaut aus dem Dokument mit.

#### Das Layout wechselt zweimal, und nicht an derselben Stelle

Naheliegend wäre „bis 2020 so, ab 2021 anders". Am Bestand nachgesehen sind es
**zwei** Änderungen in **zwei verschiedenen Jahren**:

| Jahrgang | Nummerierung | Anordnung |
|---|---|---|
| 2017–2019 | römisch (I.–V.) | erst der ganze Aktiva-Block, dann Passiva |
| 2020 | römisch (I.–V.) | zweispaltig ineinander verschränkt |
| 2021–2024 | arabisch (1.–5.) | zweispaltig ineinander verschränkt |

2020 ist damit der Jahrgang, den eine Fallunterscheidung „römisch =
Blocksatz" falsch liest — und zwar lautlos, weil die Hälfte der Zeilen
trotzdem ankommt. Verschränkt heißt: Beide Seiten teilen sich die Textzeile,
und die rechte Spalte fängt **mitten in der Zeile** an, direkt hinter den
Beträgen der linken:

```
1.2.3  Rücklagen aus Investitions-
zuwendungen für nicht abnutzbare
Vermögensgegenstände
4.372.861,06 4.439.504,15 2.   Sachvermögen 1) 608.118.677,60 605.573.107,06
                          └─ hier beginnt die Aktivseite wieder
```

Ein Parser, der Zeilen an `^` trennt, verliert damit jeden zweiten
Hauptposten. Die Positionserkennung verankert deshalb nicht am Zeilenanfang,
sondern an „steht hinter Leerraum und vor einem Buchstaben" — Beträge fangen
nie mit einem Buchstaben an, Gliederungsnummern immer.

Und die **Nummer ist als Schlüssel wertlos**: „1." gibt es ab 2021 auf beiden
Seiten (Aktiva: Immaterielles Vermögen, Passiva: Nettoposition), und bis 2020
war sie römisch. Erkannt werden die Zeilen deshalb wie in der Finanzrechnung
am **Namen, den das Dokument ihnen selbst gibt** (`bilanz.ROLLEN`). Alle drei
Layouts lesen sich damit ohne eine einzige Fallunterscheidung.

#### Fünf Proben, und die letzte ist die stärkste im Bereich

| Probe | Was sie prüft | Reißt sie, … |
|---|---|---|
| `bilanz_ausgleich` | Aktiva = Passiva, auf den Cent | … fällt der ganze Stichtag |
| `bilanzsumme_gedruckt` | die unter die Tabelle gedruckte Summe (nur 2017–2020) | … fällt nur diese Probe |
| `rueckstellungs_gliederung` | 3.1.1 + 3.1.2 = 3.1 | … fällt nur diese Probe |
| `bilanz_vorjahreskette` | jeder Hauptposten steht im **Folgejahrgang** noch einmal als Vorjahr | … fällt die Bilanz beider Stichtage |
| `bilanz_kassenprobe` | „Liquide Mittel" = „Endbestand an Zahlungsmitteln" der Finanzrechnung | … fällt dieser Stichtag |

Die Kreuzprobe ist die stärkste, die der Bereich hat: Beide Tabellen stehen im
selben Heft, aber dreißig Seiten auseinander, in verschiedenen Layouts, und
werden von **zwei getrennt geschriebenen Parsern** gelesen
(`council/finanzberichte.py` und `council/bilanz.py`). Wenn beide dieselbe Zahl
herausbekommen, hat sich keiner von beiden verlesen. Am Bestand: acht von acht
Jahrgängen, jedes Mal auf den Cent (2024: 118.001.891,26 €). Die
Vorjahres-Kette trägt sieben Übergänge à neun Pflichtposten ohne einen Riss.

Eine Fundstellen-Falle steckt schon in der Auswahl: Weiter hinten im selben
Heft stehen die Bilanzen der neun **nicht rechtsfähigen Stiftungen**. Sie haben
dieselbe Gliederung, dieselben Zeilennamen und gehen genauso auf — nur um
Bilanzsummen von rund 300.000 € statt 1,48 Mrd. €. Ein Parser, der die
erwischt, merkt es an **keiner** Rechenprobe. Genommen wird deshalb die
Fundstelle mit den meisten Beträgen dahinter; das Inhaltsverzeichnis und die
Stiftungen fallen beide über dieselbe Regel weg.

:::caution[Die 207,1 Mio. € dürfen ohne ihren Erklärtext nicht erscheinen]
Die Bilanz weist 2024 **Schulden von 207,1 Mio. €** aus, nach 84,4 Mio. € im
Vorjahr. Wer das als Zahl hinschreibt, behauptet eine Verdreifachung — und die
hat es nicht gegeben: Die Stadt ist seit 2024 zugleich Cashpool-Einheit und
Cashpool-Führer und muss dieselben Mittel auf **beiden** Bilanzseiten
ausweisen. Das ergibt eine Bilanzverlängerung von 138,2 Mio. € mit
Gegenposten im Finanzvermögen (Position 3.8 Privatrechtliche Forderungen).
Ohne den Sondereffekt sind die Schulden um 15,5 Mio. € **gesunken**.

Der Jahresabschluss erklärt das in Abschnitt 6.2.7 selbst. Genau deshalb ist
`council_bilanz_erlaeuterungen` keine Zugabe, sondern eine Auflage: Die
Oberfläche zeigt den Schuldenwert nur, wenn sie den Wortlaut dazu hat — kein
Text, keine Zahl. Dieselbe Bauart wie `council_abweichungsgruende` für die
Ergebnisrechnung.
:::

Der Anhang erläutert die Bilanz Position für Position: 6.2.1 Immaterielles
Vermögen bis 6.2.9 Passive Rechnungsabgrenzung — genau die neun Hauptposten,
in genau deren Reihenfolge. Ein Text lässt sich nicht nachrechnen, seine
**Zuordnung** schon, und die ist hier auch das einzige Risiko: Eine Erläuterung
unter der falschen Bilanzposition wäre eine Falschaussage, die keine
Rechenprobe je bemerkte. `erlaeuterungsprobe` prüft deshalb, dass die
Überschrift von 6.2.N auf das `ROLLEN`-Muster des N-ten Hauptpostens passt —
mit demselben Muster, mit dem der Parser oben seine Bilanzzeile erkennt.
Besteht sie nicht, wird **kein** Text gespeichert.

Was hier **nicht** gelesen wird: die über hundert Unterpositionen jenseits von
`ROLLEN` (eine Zeile ohne Rollen-Marke ließe sich im Layout ab 2021 keiner
Seite sicher zuordnen, und eine Bilanzzeile auf der falschen Seite wäre
schlimmer als eine fehlende) und die Anlagen zum Anhang — Anlagen-,
Forderungs-, Schulden- und Rückstellungsübersicht. Sie liegen jenseits der
Textmenge, die `scripts/backfill_anlagen_texte.py` aus den PDFs übernimmt, und
stehen in **keinem** Jahrgang im Volltext.

## Der Produkt-Steckbrief

Zu jedem Produkt führen die Pläne einen Steckbrief: **Kurzbeschreibung**
(was die Aufgabe umfasst), **Auftragsgrundlage** (die Gesetze, Satzungen und
Verträge dahinter), **Grad der Beeinflussbarkeit**, **Wirkungskreis** und
**Zielgruppe**. Das beantwortet die häufigste Bürgerfrage zum Haushalt — „was
kostet eigentlich das Stadtarchiv?" — und gibt der Pflicht/Kür-Einordnung auf
`/haushalt/pflicht` einen Boden.

:::note[Die Einordnung ist redaktionell — aber nicht mehr ungeprüft]
Bis 08/2026 stand hier und im Kopf von `lib/haushalt-pflicht.ts`, es gebe
**keine** Datenquelle, die Teilhaushalte in Pflicht und Kür einteilt. Der erste
Halbsatz gilt weiter: Eine amtliche Einteilung **ganzer** Teilhaushalte gibt es
nicht und wird es nicht geben, weil in jedem beides steckt. Der Rest stimmt
nicht mehr — die Produktebene trägt zu jeder einzelnen Aufgabe zwei Angaben der
Stadt selbst: `auftragsgrundlage` (377 von 377 Zeilen) und `beeinflussbarkeit`,
also wie viel Spielraum die **Stadt** sieht (371 von 377).

`spielraumBefunde()` fasst beides je Teilhaushalt **nach Aufwand gewichtet**
zusammen (nicht nach Kopfzahl — sonst zöge ein 200.000-€-Produkt so schwer wie
ein 70-Mio.-€-Produkt), `abgleich()` hält es gegen unsere Stufe. Ergebnis:
**Bei 6 von 9 Teilhaushalten mit Produktdaten (Stand 2023) deckt es sich.** Bei
drei nicht — bei „Jugend und Familie" sagen wir „Pflicht mit Spielraum", die
Stadt sieht für 95 % des Geldes kaum welchen; bei „Finanzmanagement und Recht"
und „Stadtplanung" ist es umgekehrt. Vier Teilhaushalte haben gar keine
Produktebene und zählen als **offen**, nicht als Übereinstimmung.

Die Abweichung wird ausgewiesen, nicht geglättet: Die redaktionelle Stufe
bleibt stehen, die Zeile bekommt eine Marke, die Zahl steht als Befund über der
Liste. Das ist die interessanteste Auskunft, die die Seite hat — sie
verschwände, wenn wir uns der Selbstauskunft anpassten.

**Ausgewiesen wird seit 16.08. nur noch die Abweichung.** Der Befund über der
Liste nannte beide Hälften, und die Übereinstimmungs-Hälfte („Bei 6 von 9
Bereichen deckt sich das mit unserer Einordnung") war Selbstbestätigung: Sie
sagt etwas über die Güte unserer Redaktion, nichts über die Aufgabe, um die es
geht (`DESIGNSPRACHE.md` § 7). Die Abweichung ist das genaue Gegenteil und
steht weiter da, mitsamt ihrer Bezugsgröße — „bei 3 von 9" ohne Nenner wäre
eine Zahl ohne Maßstab. `abgleich()` rechnet beide Richtungen unverändert;
`deckt` ist damit nur noch das, was es sein sollte: die Gegenprobe im Code,
nicht die Schlagzeile auf der Seite.

**Zwei Jahre, nicht eins.** Der Plan reicht bis ins Kopfjahr der Seite, die
Produktebene endet 2023. Jede Aussage aus ihr trägt deshalb ihren eigenen
Jahresstempel (`SpielraumBefund.jahr`). Vermischen wäre die stillste Art, hier
falsch zu liegen.
:::

Der Bestand (377 Produkte, 2018–2023): Auftragsgrundlage und Wirkungskreis
tragen 100 %, Kurzbeschreibung, Beeinflussbarkeit und Zielgruppe je 98,4 %.
Die sechs Lücken sind echt — „Personalzuweisung an das Jobcenter" führt den
Plan ohne Beschreibungstext. Der Lauf von `ingest_finanzberichte.py` weist
die Quote je Feld aus, die Seite nennt sie ebenfalls.

:::caution[Die Label stehen NACH ihrem Inhalt]
Im PDF sitzt „Kurzbeschreibung:" als Spaltenüberschrift **links neben** dem
Absatz. Die Textextraktion schiebt sie dahinter, die Reihenfolge im Text ist
also: Absatz — `Kurzbeschreibung:` — Rechtsgrundlagen-Absatz —
`Auftragsgrundlage:`. Wer vorwärts liest, bekommt jedes Feld um eines
verschoben; die Kurzbeschreibung wäre dann das Gesetz. Kurze Werte passen im
PDF neben ihr Label und stehen deshalb **dahinter** („Grad der
Beeinflussbarkeit: mittel"). `_STECKBRIEF_FELDER` markiert beide Fälle
ausdrücklich, statt sie zu erraten.

Zwei Folgefehler, die dabei auffielen und je einen eigenen Schutz haben:
- **Jede Leistung trägt einen eigenen Steckbrief.** Ein Produkt zerfällt in
  Leistungen (`P10.111023.001`) mit denselben Feldern. Der Produktblock wird
  deshalb vor der ersten Leistungs-Überschrift abgeschnitten.
- **Die Grunddaten-Tabelle steht mitten drin.** Ihr Label steht ausnahmsweise
  vor ihrem Inhalt, die Tabelle liegt also zwischen `Wirkungskreis:` und
  `Zielgruppe(n):` — ungefiltert stand eine Zahlenwüste („Einheit · Ist 2021 ·
  Plan 2022 …") als Zielgruppe auf der Seite. Übernommen wird nur der
  zusammenhängende Fließtext-Block unmittelbar vor dem Label.
:::

`beeinflussbarkeit` ist normalisiert (`niedrig` / `mittel` / `hoch`; die Pläne
schreiben mal „niedrig", mal „gering", mal groß). Der Wortlaut bleibt in
`beeinflussbarkeit_roh` erhalten — Mischformen wie „niedrig/mittel bei
Gesundheitsförderung und Prävention" bekommen **keine** Stufe zugewiesen,
weil jede Wahl eine Behauptung wäre; die Seite zeigt dann den Rohwert.

Gesucht und gefiltert wird **serverseitig** (`q`, `amt`, `spielraum` am
Endpunkt): Mit dem Steckbrief trägt jede Zeile mehrere hundert Zeichen
Fließtext. `nr` holt zusätzlich ein einzelnes Produkt, damit der Steckbrief
auch dann lädt, wenn ein Filter es aus der Liste nähme. `facetten` liefert
Ämter und Spielraum-Stufen mit Anzahl sowie die Abdeckung je Feld.

Verwaltungsdeutsch wird nicht ungefiltert durchgereicht: „übertragender
Wirkungskreis", „Grad der Beeinflussbarkeit" und „Produkt" stehen im Glossar
(`lib/glossary.ts`), die drei Stufen werden in `SPIELRAUM_TEXT` zu Sätzen
übersetzt. Eingefärbt wird nichts — ein teures Produkt ist keine schlechte
Note, und „kaum Spielraum" kein Missstand.

## Planjahre: „Ansatz" heißt fünfmal etwas anderes

`council_ergebnisrechnung` kann die Einnahmearten nur für **abgeschlossene**
Jahre zeigen — 2025 und 2026 haben keinen Jahresabschluss. Die Zahlen stehen
aber längst im Haushaltsplan selbst: Anlage 005, der *Gesamtergebnishaushalt*,
führt dieselben Posten 01–24 auf 16 bis 18 Seiten. Acht Dokumente decken die
Planjahre 2019–2026 ab (`council/ergebnishaushalt.py`).

Der Tabellenkopf sieht harmlos aus und ist die eigentliche Gefahr:

```
Ergebnis 2024 | Ansatz 2025 | Ansatz 2026 | Ansatz 2027 | Ansatz 2028 | Ansatz 2029
```

Fünfmal „Ansatz" — beschlossen ist genau **eins** davon (hier 2026). 2027–2029
sind mittelfristige Finanzplanung nach § 8 NKomVG, 2025 ist der
*fortgeschriebene* Vorjahresansatz. Gespeichert wird deshalb nur, was sich
belegen lässt, und jede Zeile sagt, was sie ist:

| Spalte | Was sie ist | Wird gespeichert? |
|---|---|---|
| 1 — `Ergebnis JJJJ` | Ist des Vorvorjahres, **Gesamtebene** (mit den nicht rechtsfähigen Stiftungen) | nein — Gegenprobe |
| 2 — `Ansatz JJJJ+1` | fortgeschriebener Vorjahresansatz | nein (s. u.) |
| 3 — `Ansatz JJJJ+2` | **beschlossener Haushaltsansatz** | ja, `art='ansatz'` |
| 4–6 | mittelfristige Finanzplanung | ja, `art='finanzplanung'` |

**Warum Spalte 2 draußen bleibt:** Sie widerspricht dem, was der Plan des
Vorjahres für dasselbe Jahr beschlossen hat — über sieben Jahrgangspaare
stimmen nur 7 bis 11 von 23 Posten überein (Nachträge, Umschichtungen). Zwei
Zeilen für dasselbe Jahr mit verschiedenen Beträgen und keine Regel, welche
gilt: das wäre eine Lücke, die aussieht wie ein Bestand.

**Warum `plan_jahrgang` im Schlüssel steht:** Dasselbe Jahr kommt in mehreren
Plänen vor — 2027 ist im Haushalt 2026 die erste Finanzplanungsstufe und im
Haushalt 2027 der Ansatz. Und die Finanzplanung wird jedes Jahr neu
geschrieben: Zwischen zwei aufeinanderfolgenden Plänen stimmen für dasselbe
Finanzplanungsjahr **0 bis 2 von 23** Posten überein. Ohne `plan_jahrgang`
überschriebe der jüngste Plan stumm den älteren.

:::caution[Es ist der Entwurf, nicht der Beschluss]
Anlage 005 hängt an der Vorlage, mit der die Verwaltung den Haushalt
**einbringt**; vier der acht Dokumente sagen das im Titel („Haushalt 2026
Verwaltungsentwurf"). Über die sechs Jahre mit Jahresabschluss liegt der
Ansatz dieser Tabelle bei den ordentlichen Erträgen 0,7 bis 13,1 Mio. €
**unter** dem Ansatz, den der Abschluss desselben Jahres als Bezugsgröße
führt — deutlich mehr, als die Stiftungen erklären. Jede Zeile trägt deshalb
`stand = "Haushaltsplan JJJJ, Anlage 005 — Stand der Einbringung"`. Wer die
Zahl zeigt, zeigt den Vorschlag der Verwaltung und sollte das anschreiben.
:::

:::caution[Was diese Schicht **nicht** liefert]
Eine Aufteilung nach Teilhaushalten. Der Jahresabschluss führt sie in
Abschnitt 5 („Teil-Ergebnisrechnung THH01…"), der Gesamtergebnishaushalt
nicht: In allen acht Dokumenten kommt „THH" kein einziges Mal vor. Für ein
Bild, das Herkunft und Verwendung gegenüberstellt, liefert sie also nur die
Herkunftsseite. `council_produkte` deckt nur 8 bis 10 der 13 Teilhaushalte ab
(17–36 % unter der Summenzeile), `council_haushalt` ist vollständig, aber eine
andere Gliederung (2026: 812,9 statt 788,6 Mio. € Erträge). Beides ist
brauchbar — aber nur, wenn die Seite den Unterschied benennt.
:::

## Vier Prüfungen, und keine davon ist optional

Aus PDF-Text extrahierte Tabellen verschmelzen Zahlen („355.188334.704") und
kleben Seitenzahlen an Werte. Ein Jahrgang kommt deshalb nur in die Datenbank,
wenn er **alle** folgenden Proben besteht:

| Probe | Was sie prüft | Wo |
|---|---|---|
| **Zeilenprobe** | `Abweichung = Ergebnis − Plan`, wobei als Plan nur zugelassen ist, was der Tabellenkopf als Spalte nennt | `_spalten_zuordnen` |
| **Summenprobe** | Die zwölf Teilhaushalte ergeben die Gesamtrechnung — in **Plan und Ist**, Zeilen 12 und 20 | `summenprobe` |
| **Strukturprobe** | `12 − 20 = 21` innerhalb der Tabelle, in Plan und Ist | `strukturprobe` |
| **Vorjahres-Kette** | Das Ist eines Jahres taucht im Folgejahrgang als Vorjahresspalte wieder auf | `vorjahreskette` |

Stand heute: Summenprobe 0,0000 % in allen acht Jahrgängen, Strukturprobe 8/8,
Vorjahres-Kette 14/14 Glieder.

**Diese Tabelle ist der Ort dafür.** Die drei letzten Proben standen bis
16.08. auch als Fließtext unter `/haushalt/plan-ist` („nur Jahre, deren Zahlen
unsere Prüfung bestehen: Die Summe der Teilhaushalte muss die Gesamtrechnung
ergeben …"). Sie sind dort raus — was bleibt, ist die Grenze, die eine Leserin
angeht: Es erscheinen nur Jahre, für die überhaupt ein Jahresabschluss
vorliegt. Dass ein Jahrgang an einer Probe scheitert, ist kein Seiteninhalt,
sondern ein Betriebsvorgang; er steht hier und im Lauf-Protokoll
(`DESIGNSPRACHE.md` § 7).

Für die Planjahre (`council/ergebnishaushalt.py`) gelten zwei eigene, und beide
sind Pflicht:

| Probe | Was sie prüft | Wo |
|---|---|---|
| **Summenzeilen** | `01–11 = 12`, `13–19 = 20` und `12 − 20 = 21` — in **allen sechs** Jahresspalten, also achtzehnmal je Dokument | `summenprobe` |
| **Planspalte** | Die hervorgehobene Planjahr-Spalte steht in jeder Zeile ein zweites Mal am Zeilenende und zeigt auf dieselbe Spalte wie der Kopf | `planspaltenprobe` |

Die zweite trägt die Trennlinie zwischen Ansatz und Finanzplanung: Ohne sie
wäre „dritte Spalte = beschlossener Ansatz" eine Reihenfolgeannahme. Stand
heute in 8/8 Dokumenten aufgegangen, 23 von 23 Zeilen je Dokument.

### Der Stellenplan: vier Proben, und eine davon absichtlich kein Gate

Der Stellenplan (`council/stellenplan.py`) ist die einzige Schicht des
Bereichs, die nicht in Euro rechnet. Er hat zwei Teile — A für Beamtinnen und
Beamte (neun Spalten), B für Tarifbeschäftigte (acht) — und jeder Teil kommt
**einzeln** durch seine Proben. Deshalb ist die Einheit der Teil und nicht der
Jahrgang: Im Stellenplan 2026 gibt der Textextrakt für Teil B Glyphen-Nummern
statt Buchstaben aus, Teil A steht sauber da.

| Probe | Was sie prüft | Wo |
|---|---|---|
| **Spaltenprobe** | Die Tabelle nummeriert ihre Spalten selbst (`1 2 3 … 9`), auf jeder Seite neu und überall gleich | `_spaltenzeile` |
| **Gruppensummen** | Die Einzelzeilen zwischen zwei Summenzeilen ergeben die Summenzeile — in **jeder** Wertespalte | `gruppenprobe` |
| **Besetzungsprobe** | `besetzt + nicht besetzt = Stellen im Vorjahr`, geprüft auf den Summenzeilen | `besetzungsprobe` |
| **Gesamtsumme** | Die Gruppensummen ergeben die Gesamtzeile; Teil A führt sie zweimal, beide müssen stimmen | `gesamtprobe` |

Teil B trägt die vierte nicht: Er hat eine Gruppe, deren Summe zugleich die
Gesamtsumme ist — sie wiederholte dort nur die zweite unter neuem Namen.

:::caution[Die Besetzung gehört zur Vorjahresspalte]
Der Plan 2026 sieht 815 Stellen vor **und** sagt daneben, wie es am 30.6.2025
aussah: 796 Stellen, davon 143,71 nicht besetzt. Geplant wird vorwärts,
gezählt werden kann nur rückwärts. `815 − 652,31 = 162,69` mischt zwei
Stichtage und steht in keinem Dokument; `lib/haushalt-stellenplan.ts` hat
deshalb gar keine Funktion, die Plan und Besetzung verrechnet.
:::

**Warum die Besetzungsprobe auf Summenzeilen läuft und nicht auf jeder
Einzelzeile.** Der Stellenplan 2023 widerspricht sich in Teil B in genau zwei
Zeilen: Bei „Dipl.-Ingenieur/-in E 11" ist die Besetzung um eine Stelle zu
hoch, bei „Verw.-Angest. E 11" um eine zu niedrig — die Stadt hat eine Stelle
in der falschen Zeile verbucht. In der Gruppensumme heben sich beide auf, und
alle vier Spalten stimmen auf 0,00. Als Gate über jede Einzelzeile fiele dafür
ein Teil mit 140 Zeilen und 1.643 Stellen. Die beiden Zeilen werden deshalb
**gekennzeichnet statt verworfen** (Spalte `stimmig`), gezählt und im
Lauf-Protokoll namentlich gemeldet. Was ein Zeilen-Gate abfangen sollte — eine
verrutschte Spalte — fangen die Spaltenvergleiche ohnehin ab.

Die Toleranz der Besetzungsprobe **wächst mit der Zeilenzahl** (`0,01 ×
Zeilen`, mindestens 0,05). Das ist keine Nachgiebigkeit, sondern eine
Ableitung: Der Plan rundet jede Zeile auf zwei Nachkommastellen (eine halbe
Stelle im Schichtdienst steht als `0,88` und `0,13`), je Zeile bleiben
höchstens 0,01 übrig, und diese Reste addieren sich in die Summenzeile. Ein
fester Wert wäre genau falsch herum streng — er ginge bei vier Zeilen durch
und schlüge bei 143 zu.

Stand heute: Sieben von acht möglichen Teilen im Bestand (2023–2026 Teil A,
2023–2025 Teil B), 611 Zeilen, alle Summenproben auf 0,00 aufgegangen, zwei
gekennzeichnete Zeilen. Die Jahrgänge 2019–2022 gibt es nicht — dort endet das
Anlagenverzeichnis des Haushaltsplans bei „021 Wirtschaftsplan EGH".

**Gegenprobe, keine Probe:** Die Ist-Spalte des Vorvorjahres lässt sich gegen
`council_ergebnisrechnung` halten — aber sie ist die *Gesamt*ebene (mit den
nicht rechtsfähigen Stiftungen), der gespeicherte Abschluss die
Kernverwaltung. Deckungsgleich sind 6 bis 8 von 23 Posten, der größte Abstand
liegt bei 0,075 % der Ertragssumme. Gegen die *Gesamt*ergebnisrechnung
desselben Abschlusses trifft sie dagegen auf den Cent: **184 von 184 Posten in
allen acht Jahrgängen**. Der Lauf misst den Abstand und meldet ihn ab 0,5 % —
verwerfen darf er deswegen nichts, sonst flöge irgendwann ein richtiger
Jahrgang wegen einer anderen Konsolidierungsstufe raus.

**Welche Probe eine gespeicherte Zeile bestanden hat, steht seit 08/2026 an
der Zeile** — über ihre `herkunft_id` in `council_herkunft.probe`, mitsamt dem
Messwert (`probe_ergebnis`, etwa „0.00 % Abweichung zur Gesamtrechnung"). Bis
dahin lief die Probe zwar, aber nur das Lauf-Protokoll wusste davon, und das
ist nach dem Lauf weg. Jede Probe hier braucht deshalb einen Eintrag in
`herkunft.PROBEN` — Name plus einen Satz für Leserinnen.

Zwei Details, die teuer erkauft sind:

- Die Summenprobe prüfte früher nur den Ansatz. Das genügt nicht — ein
  Fehlgriff, der zufällig denselben Ansatz trägt, käme durch. Sie prüft
  deshalb **Plan und Ist**. (Im Abschluss 2022 wurde THH09 einmal mit 0,1
  statt 26,8 Mio. € gelesen; erst die Summe machte es sichtbar.)
- Gesucht wird das **letzte** passende Fenster in der Zahlenfolge einer Zeile,
  denn der Kopf ordnet von rechts: Abweichung, davor Ergebnis, davor die
  Bezugsgröße. Damit dabei nicht die Zeile *unter* Posten 24 mitgelesen wird —
  „Jahresergebnis" trägt keine Nummer und rutscht in dieselbe Zeile —, wird die
  Zeile vorher an diesem Wort abgeschnitten. Ohne den Schnitt ergäbe sich für
  Posten 24 ein zweites, in sich stimmiges Tripel (2024: 34,6 + −28,5 = 6,1).

:::caution[Vorzeichen nur auf den Cent reparieren]
Fehlt im Dokument ein Minuszeichen, darf der Parser es ergänzen — aber nur,
wenn der Betrag **exakt** passt (1 Cent Toleranz statt 1 Euro) und alle drei
Werte des Tripels von null verschieden sind. Ohne die zweite Bedingung erfüllt
jedes „X | 0,00 | X" diese Probe: Im Abschluss 2018 hätte das für THH11 ein
Ist von 0,00 € eingetragen, richtig sind 105,0 Mio. €. Der Fall wird gezählt
und geloggt (`vorzeichen_repariert`); in den acht Jahresabschlüssen tritt er
derzeit **null**-mal auf.
:::

Ein Nebenertrag: Die Ansätze aus den Jahresabschlüssen bestätigen die Werte,
die wir aus den Plan-PDFs lesen. `council_haushalt` minus der Zeile „nicht
rechtsfähige Stiftungen" trifft den **ursprünglichen** Ansatz auf den Cent —
2020 also 588.539.108,34 € (vor Nachtrag), nicht die 591,3 Mio. € des
fortgeschriebenen Plans. Genau dafür gibt es die beiden Felder.

## Die Prüfung: was das Rechnungsprüfungsamt beanstandet

Der Jahresabschluss ist die Abrechnung — der **Schlussbericht des
Rechnungsprüfungsamts** ist die einzige regelmäßige, förmliche Kontrolle
davon durch eine Stelle, die dem Rat berichtet und nicht der
Verwaltungsspitze. Auch er hängt als PDF an einer Ratsvorlage und wird dort
nie wieder gelesen.

Greifbar ist er, weil er seine Befunde mit **Randmarken** auszeichnet und
deren Bedeutung selbst in den Vorbemerkungen erklärt: `B` Beanstandung,
`WB` Wiederholte Beanstandung, `H` Hinweis, `K` Korrektur/Klärung. Für
2017–2023 stehen so **257 Feststellungen** im Bestand — 166 Hinweise,
42 Beanstandungen, 37 wiederholte, 12 Korrekturen.

Jede trägt Jahr, Textziffer, Seite und einen Deeplink auf das Quelldokument.
Die Marken werden auf der Seite **erklärt, nicht bewertet**, und zwar mit dem
Wortlaut aus der Legende des jeweiligen Jahrgangs — die ändert sich (der
Bericht 2023 führt kein `K` mehr). Bewertungsfarben gibt es keine: Rot für
„Beanstandung" machte aus einer Aufbereitung eine Anklage, mit einem Mittel,
das dem Bericht selbst fremd ist.

:::note[Der Konsistenz-Check statt einer Rechenprobe]
Prosa lässt sich nicht nachrechnen — das Dokument liefert aber eine eigene
Klammer, und `council/pruefberichte.py` macht sie zum Pflicht-Gate:

1. Es muss eine Legende geben, und **nur die dort erklärten Marken** zählen.
2. Jede Marke muss unter einer **Textziffer aus dem Inhaltsverzeichnis**
   stehen (das Verzeichnis überschreibt seine erste Spalte selbst mit
   „Textziffer").
3. Der Textblock endet an der nächsten Marke oder der nächsten
   Abschnittsüberschrift — nie „so viele Zeichen".

Was die Klammer nicht erfüllt, wird verworfen und **gezählt**. Der Ingest
weist die Zahl je Jahrgang aus; sie ist derzeit 0 und bleibt es, solange das
Dokumentformat hält. Steigt sie, hat sich etwas geändert — dann gehört ein
Blick in den Bericht, keine gelockerte Regel.

Die Regeln 1 und 2 standen bis 16.08. als erster Satz im Fußabsatz von
`/haushalt/pruefung` („Es erscheinen nur Jahrgänge, deren Schlussbericht die
Prüfung besteht: …"). Sie stehen jetzt nur noch hier. Der **Rest** des
Absatzes ist geblieben, und der Unterschied ist genau der, um den es geht:
dass für einen Jahrgang der Schlussbericht nicht in lesbarer Form vorliegt,
ist eine Auskunft über die Datenlage, die jemand kennen muss — dass unser
Parser eine Marke nur hinter einer Textziffer akzeptiert, ist es nicht
(`DESIGNSPRACHE.md` § 7).
:::

Zwei Fallen, die dabei teuer waren und als Test festgehalten sind:

- **Die Legende schreibt die Marken genau wie der Fließtext** (` B  Beanstandung`).
  Wer vor dem Berichtsanfang zu zählen beginnt, zählt für 2019–2023 jede Marke
  einmal zu oft.
- **Am Berichtsende steht der Name der Amtsleitung in gesperrter Schrift**
  („K R U P K E"). Mit nur einem Leerzeichen hinter der Marke ginge er als
  `K`-Marke durch. Deshalb verlangt das Muster **zwei** Leerzeichen — den
  Abstand der Randspalte.

**Zuordnung und Dedup.** Welcher Bericht zu welchem Jahresabschluss gehört,
entscheidet der **Textanfang**, nicht das Label: „Schlussbericht JA 2017"
(`document_id` 192039) ist der Bericht zum Eigenbetrieb Gebäudewirtschaft,
und jedes Jahr kommen die formgleichen Berichte zu Klävemann-Stiftung, VOSS,
AWB und EGH dazu. Der Titel steht im Extrakt über vier Zeilen — ein
`LIKE 'Schlussbericht des …'` in SQL findet deshalb **keinen einzigen**
Bericht; erst nach Whitespace-Normalisierung greift der Vergleich.

**Die Ketten.** Eine „wiederholte Beanstandung" sagt von selbst, dass ein
Mangel schon einmal dastand — sie sagt nur nicht, seit wann. Über den
Abschnittstitel (ohne Klammerzusätze, weil „Internes Kontrollsystem (IKS)" ab
2020 nur noch „Internes Kontrollsystem" heißt) finden dieselben Sachen über
die Jahrgänge zusammen. Die Textziffer taugt dafür **nicht**, sie verschiebt
sich. Längste Kette: **Plan-Ist-Vergleich**, in allen sieben geprüften Jahren
als `WB` ausgewiesen — zuletzt mit dem Satz „Dies widerspricht dem Grundsatz
der Haushaltswahrheit". Deshalb steht der Hinweis auf die Prüfung auch auf
`/haushalt/plan-ist`, im Wortlaut und mit Link.

**Was daneben steht.** Der Absatz, der im Bericht direkt auf eine Marke
folgt, wird als `folgeabsatz` getrennt geführt und getrennt angezeigt. Dort
steht oft die Gegenseite („Die Verwaltung hat hierzu erklärt, dass eine
entsprechende Umsetzung bis 31.12.2024 erfolgen soll."). Getrennt, weil sonst
als Beanstandung gälte, was der Bericht gar nicht so gemeint hat — 97 der 257
Feststellungen haben einen, 23 davon mit Bezug auf die Verwaltung.

Eine **regelmäßige** Rückmeldung der Verwaltung gibt es nicht: Im ganzen
Bestand liegen dazu drei Dokumente — die „Nacharbeiten-Übersicht" zum
Prüfbericht 2020 (`council_anlagen` 243109, Vorlage 21/0944) und je eine
Stellungnahme des Oberbürgermeisters zu den Berichten 2019 und 2021. Die
Nacharbeiten-Übersicht war beim Bau die beste Gegenprobe: Sie nennt zu jeder
Feststellung Ziffer **und** Seite, und beide stimmen mit dem Geparsten
überein (3.1.1 → Seite 18, 3.1.3 → 20, 3.2 → 22).

## Woran das Labor seine Zahlen misst

Ein Regler, der eine Zahl verändert, sagt nichts darüber, ob das viel ist.
Deshalb hängt an jeder Bewegung ein Bezug, und alle drei kommen aus Daten:

- **Anteil an der Lücke** — der Balken im Ergebnis füllt sich, Einnahmen und
  Kürzungen getrennt eingefärbt.
- **Euro je Einwohner** — Bezugsgröße ist `council_einwohner` (jüngstes Jahr).
- **Der Beispielbetrieb am Hebesatz** — 100.000 € Gewerbeertrag × Messzahl
  3,5 % (§ 11 GewStG) × Hebesatz. Dieselbe Rechnung wie im Steuer-Steckbrief,
  damit beide Seiten dieselbe Zahl nennen.
- **Vergleichsgrößen aus der Produktebene** — „ungefähr so viel, wie
  *Kulturgutvermittlung* im ganzen Jahr kostet". Verglichen wird nur
  **innerhalb desselben Teilhaushalts**: Eine Kultur-Kürzung neben eine
  Sozialleistung zu stellen legt nahe, man könne die stattdessen streichen.
  Wo für einen Bereich keine Produkte vorliegen, entfällt der Vergleich.
- **„Wie verlässlich ist der Plan?"** — der Ansatz gegen das Ergebnis aus den
  Jahresabschlüssen. In allen fünf eingelesenen Jahren fiel das Ergebnis
  besser aus als geplant (zwischen +2,9 und +38,1 Mio. €). Der Block sagt
  ausdrücklich dazu, dass das Minus damit nicht unecht wird — ein Plan preist
  Vorsicht ein.

:::caution[Produktzahlen sind Vergleich, nicht Rechengrundlage]
Die Simulation rechnet mit dem aktuellen Planjahr, die Produktebene stammt aus
dem jüngsten auslesbaren Teilhaushaltsplan (2023). Beides zu verrechnen ergäbe
eine Zahl, die in keinem Dokument steht. Die Produkte stehen deshalb nur
daneben — als Größenordnung, nie als Summand.
:::

## Der Konzern Stadt: was der Kernhaushalt nicht zeigt

Alles bisher Beschriebene ist die **Kernverwaltung**. Das ist nicht die ganze
Stadt: Klinikum, Verkehr und Wasser, Abfallwirtschaftsbetrieb, Bäderbetrieb,
Weser-Ems Halle und der Eigenbetrieb Gebäudewirtschaft führen eigene Bücher
und tauchen im Haushalt bestenfalls als Zuschusszeile auf. 2024 stehen
799,1 Mio. € Kernverwaltung gegen 1.241,5 Mio. € Konzern — der Haushalts-
Bereich zeigte bis dahin rund **64 %** dessen, was die Stadt bewegt.

Die Quelle ist der **konsolidierte Gesamtabschluss** nach § 128 NKomVG, genauer
der Prüfbericht, den das Rechnungsprüfungsamt dazu vorlegt (`council_anlagen`,
zwölf Jahrgänge 2013–2024). Parser: `council/konzernabschluss.py`.

**Die Labels dieser Reihe sind wertlos.** Der Gesamtabschluss 2016 heißt im
Bürgerinfo schlicht „Anlage", 2013 ebenso; „Prüfbericht GA 2021" trifft nur
drei von zwölf. Erkannt wird deshalb am **Textanfang** — und zwar erst nach
dem Glätten des Zeilenumbruchs, denn im Rohtext steht der Titel über fünf
Zeilen verteilt. Ein `raw_text LIKE 'Bericht über die Prüfung des
konsolidierten Gesamtabschlusses zum 31.12.2016%'` fände **nichts**.

### Zwei Tabellen, sechs Proben

| Abschnitt | Tabelle | Proben |
|---|---|---|
| 3.2 Gesamtergebnisrechnung | `council_konzern_posten` | `Erträge − Aufwendungen = ordentliches Ergebnis`; dasselbe für die außerordentlichen Posten; beide zusammen = Gesamtjahresergebnis |
| 4.1.1 Trägeraufstellung | `council_konzern_traeger` | je Zeile `Jahr − Vorjahr = Veränderung`; Träger + Konsolidierung = ausgewiesene Summe; diese Summe = Summenposten aus 3.2 |

Dazu die **Vorjahres-Kette** über Dokumentgrenzen: 39 von 39 Gliedern schließen.
Sie ist bewusst **kein** Ausschlussgrund, sondern eine Meldung — sie prüft zwei
Jahrgänge gegeneinander, und wer bei Streit beide wegwirft, verliert einen
guten wegen eines schlechten.

Stand heute: **11 von 12 Jahrgängen** gespeichert (2014–2024), 289 Posten,
135 Trägerzeilen.

### Drei Fallen, an denen ein naiver Parser scheitert

- **Die Postennummern wechseln.** Bis 2018 ist Posten 15 die Summe der
  ordentlichen Erträge, ab 2019 ist es Posten 13. Wer weiter 15 liest, bekommt
  ab 2019 „Versorgungsaufwendungen" — 8,4 Mio. statt 1,14 Mrd., und keine
  Zeile im Log. Gespeichert wird deshalb eine **Rolle**
  (`ertraege_summe`, `zinsaufwand`, …), erkannt an der Beschriftung; die
  Nummer steht nur noch als Fundstelle daneben.
- **Die Vorjahresspalte ist nicht immer in Euro.** 2014–2016 führt der
  Tabellenkopf `EUR EUR TEUR`. Wer das übersieht, liest einen Konzern, der
  über Nacht auf ein Tausendstel schrumpft. Die Einheit kommt aus dem Kopf.
- **2019 hat keine Zeilenumbrüche.** Der Extrakt setzt die ganze Tabelle in
  eine Zeile, und die nächste Postennummer klebt am Vorjahreswert
  (`269.835.099,832. Zuwendungen`). Auflösbar, weil ein deutscher Betrag immer
  genau zwei Nachkommastellen hat — mehr macht `entzerren()` nicht, und die
  drei Proben entscheiden anschließend wie bei jedem anderen Jahrgang.

Dazu kommt eine Eigenheit, die keine Falle, sondern eine Grenze ist: In den
Jahrgängen bis 2017 stehen **Leerzeichen mitten in Beträgen**
(`105.667.339, 23`, `160.026.568 ,55`). Solche Zeilen fallen weg, statt eine
geratene Zahl zu liefern — der erste *saubere* Betrag einer Zeile ist sonst
nicht mehr der des Haushaltsjahres, sondern der des Vorjahres. Die
Beschriftung darf deshalb keine Ziffernfolge enthalten; tut sie es, ist die
Zeile zerschossen.

### Die Gegenprobe — die stärkste Bestätigung im ganzen Bereich

Der Gesamtabschluss führt die Kernverwaltung als eigene Trägerzeile. Diese
Zeile muss den Ist-Wert wiedergeben, den `council_ergebnisrechnung` aus einem
**anderen** Dokument eines **anderen** Jahres trägt. Sie tut es in **10 von 10**
vergleichbaren Fällen (5 Jahrgänge × Erträge und Aufwendungen), jeweils auf
die Rundung eines Tausend genau — 2024 etwa 799.057 TEUR gegen
799.057.202,86 €. Zwei getrennt eingelesene Quellen, dieselbe Zahl.

Die API rechnet den Abgleich weiter (`gegenprobe` in
`web/backend/app/routers/council.py`), festgehalten ist er in
`tests/test_konzernabschluss.py::test_gegenprobe_gegen_die_kernverwaltung` und
`tests/test_backend_api.py::test_haushalt_konzern_liefert_luecke_und_gegenprobe`.
**Die Seite zeigt ihn seit 16.08. nicht mehr**: Acht Zeilen, in denen dieselbe
Zahl zweimal steht und daneben „unter 1 Tsd. € Unterschied", waren
Selbstvergewisserung, keine Information für Leserinnen. Der Beleg dafür, dass
wir den Zahlen trauen können, gehört hierher und in die Tests — nicht auf die
Seite.

### Was der Gesamtabschluss nicht hergibt

- **Die Liste der einbezogenen Gesellschaften.** In den jüngeren Jahrgängen ist
  der Konsolidierungskreis eine **Grafik ohne Textebene** („Aus der
  nachfolgenden Grafik ist ersichtlich, welche Aufgabenträger …") — dieselbe
  Sackgasse wie bei der Schuldenübersicht. Wer dazugehört, sagt stattdessen die
  Trägeraufstellung, und die trägt Zahlen. Beteiligungsquoten stehen nirgends.
- **Der Schuldenstand.** Die Gesamtschuldenübersicht ist Pflichtanlage, aber
  ihre Seiten tragen im PDF keinen Text. Ohne OCR ist dort nichts zu holen, und
  ein aus Diagrammbeschriftungen zusammengerechneter Schuldenstand wäre still
  falsch.
- **Der Jahrgang 2013** (`document_id` 188333): 74 Seiten, aber nur 38.000
  Zeichen Volltext — die Tabellenseiten kommen ohne Textebene. Keine der drei
  Proben ist überhaupt rechenbar, der Jahrgang fällt durch.
- **Die Aufwendungsseite der Trägeraufstellung 2018.** Ihre Konsolidierungs-
  zeile (−80.462 TEUR) passt nicht zur eigenen Summenzeile; der Bericht des
  Folgejahres führt für dasselbe Jahr −80.398. Die Spaltenprobe schlägt mit
  64 TEUR an, die Aufstellung wird verworfen — die Ertragsseite desselben
  Jahrgangs und seine Postentabelle bleiben. **Das ist der Gate im Betrieb**,
  nicht die Theorie dazu.

:::caution[Ein Gesamtabschluss ist kein Haushalt]
Er wird rund zwei Jahre später aufgestellt, folgt handelsrechtlichen Regeln und
ist mit den Planzahlen auf `/haushalt` **nicht verrechenbar** — auch nicht
durch Subtraktion. Die API liefert deshalb keine gemischten Summen, sondern
beide Reihen getrennt, und die Seite sagt es in einem eigenen Block statt im
Kleingedruckten.
:::

## Beteiligungsbericht: was die Gesellschaften tun

Der Gesamtabschluss sagt, **wie viel** die städtischen Betriebe bewegen. Was
sie damit *tun*, steht dort nicht — nur ihre Beiträge zur Ergebnisrechnung.
Das sagt der **Beteiligungsbericht nach § 151 NKomVG**: einmal im Jahr, rund
200 Seiten, je Gesellschaft acht Abschnitte (Gegenstand, Beteiligungs-
verhältnisse, Aufsichtsorgane, eigene Beteiligungen, Geschäftsverlauf, Bilanz
und Kennzahlen, öffentlicher Zweck, Auswirkungen auf den Haushalt).

Parser: `council/beteiligungsbericht.py`. Seite: `/haushalt/beteiligungen`
(Schritt 9), Steckbrief über `?g=<gesellschaft>`.

### Ein zweiter Cron-Typ: der erste, der herunterlädt

`check_finanzdaten` **lädt nichts herunter**. Das ist seine erste Regel, und
sie ist richtig: Seine Dokumente hängen als Anlagen an Ratsvorlagen und werden
vom Protokoll-Scraper ohnehin geholt; ein zweiter Weg dorthin wäre Doppelarbeit
mit doppelter Fehlerquelle.

Der Beteiligungsbericht hängt an keiner Vorlage. Er liegt auf oldenburg.de.
Ihn im bestehenden Job mitzuholen hieße, dessen klarste Regel aufzuweichen —
deshalb `scripts/check_beteiligungsbericht.py` als **eigener Job** mit eigenem
Takt (alle vier Wochen; die Quelle erscheint einmal im Jahr) und
`council/stadtdownload.py` als eigener, geprüfter Netzweg. Der hält vier
Dinge ein, die ein Abruf auf fremden Servern einhalten muss:

- **Er sagt, wer er ist** — ein `User-Agent` mit Namen, Adresse und Zweck.
- **Er fragt erst, ob es sich lohnt** — `If-Modified-Since` / `If-None-Match`;
  bei `304` wird nichts übertragen. Sieben Berichte sind zusammen 25 MB.
- **Er wartet zwischen den Abrufen** und nimmt nur, was er erwartet: PDF laut
  `Content-Type`, `%PDF` am Anfang, höchstens 40 MB. Eine Fehlerseite mit
  `200 OK` ist bei CMS-Systemen der Normalfall.
- **Er hält die Regeln der Seite ein.** `robots.txt` erlaubt `User-agent: *`
  mit `Allow: /`; gesperrt sind TYPO3-Innereien und `cHash`-Adressen. Die
  Berichts-PDFs unter `/fileadmin/oldenburg/…` sind frei (nachgesehen
  16.08.2026).

Die Adressen der PDFs werden **aus der Übersichtsseite gelesen**, nicht
geraten: Der Dateiname wechselt von Jahrgang zu Jahrgang
(`Beteiligungsbericht_2021.pdf` gegen `Beteiligungsbericht_2024_kombiniert_final.pdf`).

Im Datenstand steht die Schicht mit `automatisch = false` — `check_finanzdaten`
beobachtet sie mit und meldet, wenn ein Jahrgang ausbleibt, lädt aber selbst
nichts.

### Warum nur drei von sieben Jahrgängen

Auf oldenburg.de stehen sieben Berichte (2018–2024). Gelesen werden **2022,
2023 und 2024**. Der Grund ist ein Formatbruch, kein Aufwand:

| | 2018–2021 | ab 2022 |
|---|---|---|
| Gliederung je Gesellschaft | frei betextet | acht nummerierte Abschnitte `1)`–`8)` |
| Bilanz | Aktiva und Passiva **nebeneinander** | einspaltig, `BILANZSUMME` auf beiden Seiten |
| Kennzahlen | keine Tabelle | „Kennzahlen im Zeitverlauf", 4–5 Jahre |

Gemessen am Bestand: „Kennzahlen im Zeitverlauf" kommt in den Jahrgängen
2018–2021 **null**-mal vor, ab 2022 je 14–16-mal. `BILANZSUMME` ebenso: null
gegen 28–32. Die zweispaltige Bilanz der alten Jahrgänge verschränkt pypdf zu
Zeilen, in denen Aktiv- und Passivbeträge abwechselnd stehen.

**Der Verzicht kostet keine Zahlen.** Jeder Bericht führt vier bis fünf Jahre
mit; der Bestand deckt deshalb **2017–2024**. Was fehlt, ist der Fließtext der
Jahre 2018–2021 — und „was macht die GSG eigentlich?" beantwortet ohnehin der
jüngste Bericht.

### Die Zuordnung Abschnitt → Gesellschaft

Der eigentliche Fallstrick bei 200 Seiten. Der Bericht beantwortet ihn selbst
**zweimal**: Das Inhaltsverzeichnis nennt für jede Gesellschaft ihre
Gliederungsnummer und ihre Anfangsseite, und auf genau dieser Seite steht eine
Trennseite mit derselben Nummer. Stimmen beide nicht überein, ist die Zuordnung
nicht gesichert und der Abschnitt fällt weg. In den drei gelesenen Jahrgängen
gehen **45 von 45** Zuordnungen auf; das ist die Probe
`beteiligung_seitenprobe`.

### Drei Proben für die Kennzahlen — und keine für den Text

| Probe | Was sie zeigt |
|---|---|
| `beteiligung_bilanzprobe` | Die Bilanz weist ihre Summe zweimal aus (Aktiva, Passiva), die Kennzahlen-Tabelle ein drittes Mal |
| `beteiligung_ergebnisprobe` | Die Gewinn- und Verlustrechnung schließt mit dem Jahresergebnis der Kennzahlen-Tabelle |
| `beteiligung_ueberlappung` | Dasselbe Jahr steht in bis zu drei Berichten — verschiedene Veröffentlichungen, dieselbe Zahl |

Gemessen über die drei Jahrgänge: **246 von 246 Dokumentproben bestanden**,
**202 Werte** durch die Überlappung bestätigt, **kein einziger Widerspruch**.
Von 286 gelesenen Werten tragen 230 eine Probe; die übrigen 56 werden
**verworfen statt geschätzt** — es trifft die älteste Spalte des ältesten
Berichts (keine Bilanz daneben, kein zweiter Bericht) und die
Eigenkapitalquote des jüngsten Jahres, die das Dokument nirgends vorrechnet.

**Die beschreibenden Abschnitte tragen `herkunft.UNGEPRUEFT`**, und das ist die
ehrliche Angabe: Gegen Fließtext lässt sich nichts rechnen. Er steht trotzdem
mit Dokument, Abschnitt und Seite da — „keine Probe" ist etwas anderes als
„keine Quelle".

### Fünf Eigenheiten, an denen ein naiver Parser scheitert

- **Die Jahresspalten wechseln die Richtung.** Der Eigenbetrieb
  Gebäudewirtschaft führt 2024 → 2020, der Abfallwirtschaftsbetrieb zwei
  Seiten weiter 2020 → 2024. Gelesen wird die Kopfzeile, nie die Reihenfolge.
- **Der Berichtsjahrgang steht nicht immer in der Tabelle.** Die Großleitstelle
  führt noch im Bericht für 2024 die Jahre 2017–2021.
- **Beträge tragen Leerzeichen mitten drin** — `650 .289,04`,
  `23.439 .654,83`, `2.103.265, 69`. Dieselbe Sorte Schaden wie im
  Gesamtabschluss (`105.667.339, 23`).
- **Die Beschriftung schwankt:** `Eigenkapitalquote`, `Eigenkapitaquote`
  (Tippfehler im Bericht 2022), `Eigenkapital-\nquote`,
  `Eigenkapital -\nQuote in Prozent`.
- **Manche Zahl ist im Dokument falsch gesetzt.** Der Bericht 2022 führt für
  die GSG ein Jahresergebnis `5.698.082.44` — Punkt statt Komma. Die Zeile wird
  verworfen, nicht zurechtgebogen; im Bericht 2024 beginnt dieselbe Reihe erst
  2020 und geht durch.

### Zwei der fünf Abschnitte sind gar kein Fließtext

„Beteiligungsverhältnisse" und „Besetzung der Aufsichtsorgane" sehen im
Extrakt aus wie Prosa und sind Tabellen. Sie stehen deshalb zusätzlich
zerlegt im Bestand — `council_gesellschaft_eigentuemer` und
`council_gesellschaft_personen` —, während der Rohtext daneben stehen bleibt.

**Die Aufsichtsorgane sind zweispaltig, und pypdf liest spaltenweise:** erst
alle fünfzehn Namen untereinander, dann alle fünfzehn Ämter. Was auf der
gedruckten Seite nebeneinander steht, liegt im Extrakt fünfzehn Zeilen
auseinander. Zusammenführen lässt sich das nur über die Position — der n-te
Name zum n-ten Amt —, und das ist genau dann richtig, wenn **beide Listen
gleich lang sind**.

:::caution[Die Rechenprobe, die hier gilt]
Zahl der Namen ≠ Zahl der Ämter → **alle** Ämter dieser Gesellschaft bleiben
leer, `funktionen_zuordenbar` ist `false`. Kein „best effort", kein
Verschieben. Eine Liste, die um einen Platz verrutscht ist, hängt einer
namentlich genannten Person ein Amt an, das sie nie hatte — das ist keine
Ungenauigkeit, sondern eine Falschaussage über einen Menschen.
:::

Gemessen über die 45 Abschnitte: **44 von 45** halten die Probe
(`beteiligung_spaltenprobe`, 502 Namen). Der eine Ausreißer ist der
Abfallwirtschaftsbetrieb 2023 — dort nennt der Bericht selbst acht Personen
und sieben Ämter. Drei weitere Abschnitte (TGO Besitz GmbH & Co. KG,
2022–2024) führen gar keine Funktionsspalte, sondern Entsendungsrechte
(„Vertreter/in der Landessparkasse"); dort gibt es nichts zuzuordnen, und
das ist kein Befund.

**Bei den Eigentümern ist die Stammkapital-Zeile die Probe, kein
Gesellschafter.** Sie sieht im Extrakt aus wie einer (Name, Betrag, Prozent),
ist aber die Summenzeile: `beteiligung_anteilsprobe` verlangt, dass die
Anteile genau dieses Stammkapital ergeben **und** zusammen 100 % (Toleranz
0,5 Prozentpunkte — sechs Anteile zu je 16,67 % sind 100,02 %). Auch hier:
**44 von 45**. Der Ausreißer ist die Stadion Oldenburg GmbH & Co. KG 2024,
deren Anteile 5.000 € ergeben, während die Summenzeile 25.000 € nennt. Welche
Zahl stimmt, verrät das Dokument nicht — also kommt keine halbe
Eigentümerliste heraus, sondern keine, und der Rohtext bleibt stehen.

### Die Personen-Verlinkung entsteht beim Lesen, nicht beim Einlesen

Ob „Ruth Regina Drügemöller" im Aufsichtsrat dieselbe ist wie die
Ratsfrau auf `/council/person`, entscheidet die **API**
(`_lexikon_zuordnung`) gegen `store.personen_lexikon()` — nicht die Datenbank.
Das Lexikon wächst mit jedem Protokoll, der Beteiligungsbericht wird alle vier
Wochen eingelesen; als Fremdschlüssel eingefroren zeigte ein Steckbrief bald
auf eine Person, die inzwischen anders geführt wird.

Zugeordnet wird über Vor- **und** Nachnamen, und nur bei genau einem Treffer.
Der Bäderbetrieb führt 2024 „Dr. Sebastian Rohe" und „Dr. Georg Rohe"
nebeneinander; wer auf den Nachnamen zuordnet, hängt einem der beiden die
Personen-Seite des anderen an. Gemessen: **129 von 179** Namen des Berichts
2024 bekommen einen Link (72 %). Die übrigen sind zum großen Teil gar keine
Ratspersonen — Aufsichtsräte entsenden auch Banken, Hochschulen und
Mitgesellschafter.

### Der Abgleich mit dem Gesamtabschluss — nachgerechnet, aber keine Probe

Dieselben Gesellschaften stehen auch in `council_konzern_traeger`, dort mit
ihren ordentlichen Erträgen und Aufwendungen. Deren Differenz ist die einzige
Größe, die sich mit dem Jahresergebnis vergleichen lässt. Nachgerechnet für
2024 (in TEUR):

| Gesellschaft | Konzern E−A | Jahresergebnis | Differenz |
|---|---:|---:|---:|
| Klinikum Oldenburg AöR | −27.132 | −27.132 | 0 |
| Weser-Ems Halle | −4.378 | −4.378 | 0 |
| Bäderbetriebsgesellschaft | −5.699 | −5.709 | 10 |
| Eigenbetrieb Gebäudewirtschaft | −2.701 | −2.726 | 25 |
| Abfallwirtschaftsbetrieb | 231 | 294 | −63 |
| Bäderbetrieb | 233 | 0 | 233 |
| Verkehr und Wasser GmbH | −77 | 0 | −77 |

Zwei stimmen auf die Tausenderstelle, drei liegen dicht daneben, zwei weichen
deutlich ab — und **alle drei Befunde sind richtig**: Der Gesamtabschluss zählt
nur die *ordentlichen* Posten (daher die kleinen Abweichungen), und Bäderbetrieb
wie Verkehr und Wasser weisen 0,00 € aus, weil ihr Ergebnis abgeführt
beziehungsweise ausgeglichen wird.

:::caution[Deshalb ist das keine Probe]
Eine Toleranz, die 233 TEUR durchgehen ließe, prüfte bei der
Bäderbetriebsgesellschaft nichts mehr; eine engere verwürfe genau die beiden
Betriebe, bei denen die Quelle nachweislich recht hat. Der Abgleich wird
trotzdem bei jedem Lauf gerechnet (`beteiligungsbericht.konzernvergleich`) und
steht im Cron-Protokoll sowie auf der Seite — als **Einordnung**, nicht als
Urteil. Springt eine Abweichung, die jahrelang null war, auf Millionen, ist das
den Blick wert.
:::

## Städtevergleich: was sich vergleichen lässt — und was nicht

`/haushalt/vergleich` ist aus einer Absage entstanden. Der Entwurf sah einen
breiten Städtevergleich vor (Ausgaben, Personal, Schulden je Einwohner). Der
wurde **nicht** gebaut, und zwar nicht wegen fehlender Daten: Ein Vergleich
von Kernhaushalten misst zuerst, wie weit eine Stadt ausgelagert hat.

Oldenburgs Kernhaushalt zeigt rund **64 %** dessen, was der Konzern bewegt;
Osnabrücks knapp **48 %**, weil dort die Stadtwerke dazugehören. Dieselbe
Kennzahl, dieselbe Stadt, dasselbe Jahr — Kern gegen Konzern — unterscheidet
sich bei der Pro-Kopf-Verschuldung um **Faktor 2,53** (2024) und **6,04**
(2023). Wer eine Kernhaushaltszahl aus Stadt A gegen eine Konzernzahl aus
Stadt B stellt, kennt nicht einmal die Größenordnung des Fehlers.

:::note[Die beste Quelle zum Fallstrick liegt im eigenen Bestand]
Die Stadt Oldenburg hat genau diesen Vergleich 2018 auf Antrag der
FDP-Fraktion angestellt (Vorlage **18/0911**, `kvonr` 17170) — sieben Städte,
neun Jahrgänge — und ihn im selben Dokument entwertet: *„Die heterogenen
Strukturen der verschiedenen Städte lassen einen aussagefähigen Vergleich in
dem Sinne nicht zu, dass eine niedrigere Quote ‚besser' als eine höhere Quote
ist."* Danach listet sie je Stadt auf, was im Kernhaushalt steckt und was
nicht. Antrag: `document_id` **196000**, Antwort: **196525**.

Dieselbe Warnung kommt vom Nds. Innenministerium (Runderlass 13.12.2017) und
vom Statistischen Bundesamt. Die Seite zitiert die Verwaltung wörtlich und
verlinkt den Vorgang in unserem Bestand — die Vorlage wurde als Bericht **zur
Kenntnis genommen**, es gibt also einen `council_decisions`-Eintrag. Aufgelöst
wird er über die **Vorlagennummer**, nicht über die gespeicherte id: Die
Nummer ist auf jeder Kopie der Datenbank dieselbe.
:::

### Was trotzdem trägt

Robust gegen die Auslagerungsfrage ist, was die Stadt als Hoheitsträger
festlegt oder was das Land für alle gleich berechnet — es wandert nicht mit,
wenn ein Aufgabenblock in einen Eigenbetrieb zieht:

| Reihe | Kennzahlen | Quelle |
|---|---|---|
| `steuerkraft` | Steuerkraftmesszahl (TEUR), Einwohnerzahl | LSN, Kommunaler Finanzausgleich, Blatt `ST_KR_MESS_VGL` |
| `realsteuern` | Hebesätze Grundsteuer A/B und Gewerbesteuer, Ist-Aufkommen je Einwohner, Steuereinnahmekraft je Einwohner | LSN, Realsteuervergleich, Blätter `2_1` und `5_1` |

Die Steuerkraftmesszahl rechnet § 11 NFAG mit **Nivellierungshebesätzen**, also
für alle Gemeinden mit denselben fiktiven Sätzen; sie misst die Steuerbasis,
nicht die Hebesatzpolitik. Und Steuern erhebt nie ein Eigenbetrieb — der
Auslagerungseffekt existiert hier schlicht nicht.

**Die Steuerkraft je Einwohnerin wird nicht gespeichert.** Das Landesamt weist
sie nicht aus; die Division ist unsere und steht auf der Seite als solche
gekennzeichnet. Gespeichert werden Messzahl und Einwohnerzahl getrennt, sonst
ließe sich später nicht mehr unterscheiden, was amtlich ist und was gerechnet.

### Drei Proben, und eine davon prüft zwei Dokumente gegeneinander

- **`lsn_zweijahresueberlappung`** — Jede KFA-Ausgabe nennt zwei Ausgleichsjahre
  nebeneinander. Das ältere muss die Hauptspalte der Vorjahresausgabe
  wiederholen, **für jede der 403 Gemeinden**. Das ist die stärkste Probe des
  Bereichs: Sie prüft nicht eine Rechnung innerhalb eines Dokuments, sondern
  zwei Veröffentlichungen gegeneinander. Gemessen: 403 von 403 identisch.
- **`lsn_hebesatzprobe`** — `Grundbetrag × Hebesatz = Ist-Aufkommen`, die
  Definition einer Realsteuer. Bei der Gewerbesteuer zusätzlich
  `brutto − Umlage = netto`.
- **`lsn_dreijahresmittel`** — Der ausgewiesene Dreijahresdurchschnitt ist das
  Mittel der drei Jahreswerte, und geteilt durch die mitgelieferte
  durchschnittliche Einwohnerzahl ergibt er den Pro-Kopf-Wert der Zeile.

:::caution[Die Toleranz folgt der Rundung, nicht dem Gefühl]
Das LSN rundet Grundbetrag und Ist-Aufkommen auf volle Tausend Euro. Ein
Rundungsfehler von ±0,5 T€ im Grundbetrag wird mit dem Hebesatz
multipliziert — bei 500 % sind das ±2,5 T€. Eine feste Prozentschranke
verwürfe deshalb ausgerechnet die **Grundsteuer A**, deren Beträge so klein
sind (13–44 T€), dass die Rundung dort 1–3 % ausmacht. Die Schranke ist
darum `0,5 × Hebesatz/100 + 0,5`.

Und die Gewerbesteuer wird gegen **brutto** geprüft, nicht gegen netto: Die
erste Fassung prüfte gegen netto und verwarf alle acht Städte — die
Abweichung war jedes Mal auf die Tausend Euro genau die Gewerbesteuerumlage.
:::

### Drei Fallen im Dateiformat

1. **Der Städtename ist nicht stabil.** KFA 2025 schreibt `Oldenburg (Oldb),
   Stadt`, KFA 2026 `Oldenburg (Oldenburg), Stadt`; `Bad Zwischenahn` bekommt
   zwischendurch ein `*`. Verbunden wird über die **Schlüsselnummer**.
2. **Die Schlüsselnummer hat zwei Schreibweisen** — sechsstellig im
   Finanzausgleich (`403000`), dreistellig im Realsteuervergleich (`403`).
   `schluessel_normalisieren()` gleicht das an; ohne sie fänden die beiden
   Reihen einander nie, und der Fehler wäre still.
3. **Die Spaltenposition ist keine Zusage.** Gelesen wird über den
   ausgeschriebenen Tabellenkopf, den das LSN als Vorlesehilfe für
   Screenreader mitliefert — und **wo** er steht, sagt die Datei in ihren
   ersten Zeilen selbst („Der Tabellenkopf für Vorlesehilfen befindet sich in
   Zeile 14"). Fehlt der Hinweis, bricht der Parser ab, statt zu raten.

### Kein neues Paket, kein Cron

XLSX ist ein ZIP mit XML darin; `council/staedtevergleich.py` liest beides mit
der Standardbibliothek. Ein Extra-Paket nur für einen jährlichen Ingest käme in
`requirements.txt` und damit auf den Server — dieselbe Überlegung, aus der
`fastembed` draußen steht. Eine Dokumenttyp-Deklaration lehnt der Leser ab
(eine echte Tabellenmappe hat keine), womit die Entity-Expansion-Lücke der
Standardbibliothek zu ist.

Beide Quellen erscheinen **einmal jährlich**, deshalb kein Cron. Die
Download-Adressen des LSN tragen undurchsichtige Nummern (`/download/227086`),
die sich nicht hochzählen lassen; sie stehen auf der Übersichtsseite und
werden beim jährlichen Lauf mitgegeben:

```bash
python scripts/ingest_staedtevergleich.py \
  --kfa <KFA N, Datei oder Adresse> \
  --kfa-vorjahr <KFA N−1> \
  --realsteuer <Realsteuervergleich> \
  --jahrbuch-1103 2025:79787          # optionale Gegenprobe, s. u.
```

Der Lauf **schreibt nichts**, wenn die Zwei-Jahres-Überlappung scheitert; eine
einzelne Stadt, deren Hebesatzprobe nicht aufgeht, fällt mit Begründung heraus,
ohne den Jahrgang mitzunehmen.

### Die dritte Komponente des Finanzausgleichs

Dieselbe Datei, zweites Blatt (`9a`), gelesen von `council/steuerkraft.py`.
Sie schließt eine Lücke, die vorher niemandem auffiel, weil sie eine Zahl
nicht falsch, sondern **zu klein** machte.

Der Open-Data-Datensatz 1106 der Stadt führt eine Spalte
„Schluesselzuweisungen, Anordnungssoll". Nachgemessen enthält sie **exakt zwei
von drei** Komponenten des kommunalen Finanzausgleichs:

| Ausgleichsjahr | Gemeindeaufgaben | Kreisaufgaben | = Datensatz 1106 | + übertragener Wirkungskreis | = Nettobetrag |
|---|---|---|---|---|---|
| 2025 | 51.653 | 17.557 | 69.210 ✓ | 10.575 | **79.785** |
| 2026 | 62.654 | 19.624 | 82.278 ✓ | 11.160 | **93.438** |

(TEUR. Die dritte Komponente ist Geld dafür, dass die Stadt staatliche
Aufgaben miterledigt — Standesamt, Melde- und Ausländerwesen, Bauaufsicht —
und an diese Aufgaben gebunden.)

**Zwei Proben:**

1. `kfa_komponentenprobe` — im Dokument: Die drei Komponenten minus
   Finanzausgleichsumlage ergeben den ausgewiesenen Nettobetrag. Geprüft für
   alle acht kreisfreien Städte und beide Jahre, die eine Ausgabe führt;
   8/8 in den Ausgaben 2023, 2025 und 2026.
2. `kfa_jahrbuchabgleich` — gegen die Bücher der Stadt: Tabelle 1103 des
   Statistischen Jahrbuchs nennt unter „Finanzzuweisungen" für **2023
   110.049** und für **2024 109.498** TEUR — beides auf das Tausend genau der
   Nettobetrag des Landes. Für **2025** stehen 79.785 (Land) gegen 79.787
   (Jahrbuch); dort ist das Rechnungsergebnis der Stadt noch vorläufig.
   Toleranz `JAHRBUCH_TOLERANZ = 0,5 %` — eng genug, dass eine vergessene
   Komponente (13 % der Summe) sie zwangsläufig reißt.

**Die Falle:** Der Kopftext der Netto-Spalte lautet „… abzüglich der
**Finanzausgleichsumlage** im Jahr 2026)" und enthält damit den Namen einer
Komponente. Wer die Komponenten zuerst matcht, hält die Netto-Spalte für die
Umlage und meldet danach eine Datei ohne Nettobetrag. Zwischen den Ausgaben
wechseln außerdem die Schreibweise der Schlüsselnummer (`403000` gegen `403`)
und die Reihenfolge in „Euro je Einwohner/Einwohnerin"; gelesen wird deshalb
ausschließlich über den ausgeschriebenen Tabellenkopf.

**Wo es steht:** `/haushalt/einnahmen`, direkt unter der Finanzausgleichs-Kurve
(`components/haushalt/zuweisung-dreiteilig.tsx`). Die bisherige Zahl bleibt —
sie ist nicht falsch, sondern enger, und „Schlüsselzuweisungen" heißen genau
die ersten beiden Teile. Der Block stellt die vollständige daneben und sagt,
dass sie größer ist. Die Pro-Kopf-Spalte des Blattes bleibt draußen: Für das
Ausgleichsjahr 2025 nennt die Ausgabe 2025 „452,46 € je Ew.", die Ausgabe 2026
„452,27 €" — derselbe Nettobetrag, revidierte Einwohnerzahl.

:::danger[Nicht mit `council_steuerkraft` mischen]
Beide Tabellen führen Steuerkraftmesszahlen. **Der Jahresversatz ist seit
#516 entschieden** — nicht an einer Definition, sondern an den Büchern der
Stadt: Der Open-Data-Datensatz 1106 beschriftete seine Zeilen ein Jahr zu früh,
`parse_steuerkraft` rückt sie aufs Ausgleichsjahr (Begründung
[unten](#der-datensatz-1106-ist-um-ein-jahr-verschoben)). Beide Reihen tragen
damit dieselbe Jahresangabe; der frühere Satz „welche Angabe stimmt, ist offen"
gilt nicht mehr.

**Zusammengerechnet werden sie trotzdem nicht.** Der Grund ist jetzt ein
anderer, aber es bleibt einer: Es sind zwei Veröffentlichungen — die CSV der
Stadt und der Bericht des Landesamts —, und die können sich durch Nachträge und
Revisionen um kleine Beträge unterscheiden. Die LSN-Werte liegen deshalb in
einer **eigenen Tabelle** (`council_staedtevergleich`), kein Lesepfad legt die
Reihen zusammen, und `/haushalt/vergleich` sagt das in seinem Grenzen-Block.

Offen ist nur noch die Meldung an die Quelle: Ansprechpartner laut Katalog ist
die Statistikstelle der Stadt Oldenburg.
:::

## Gewerbesteuer: wie viele Betriebe sie aufbringen

Der Steuer-Steckbrief erklärt im Block „Wer zahlt das eigentlich", warum
**Namen** nicht genannt werden dürfen (§ 30 AO, Steuergeheimnis). Die
Anschlussfrage — *wie viele* Betriebe sind es denn? — blieb bis 08/2026 offen.
Diese Zahl ist, anders als der einzelne Betrag, amtlich veröffentlicht:
in der **Gewerbesteuerstatistik** (EVAS 735 11) des Landesamts für Statistik
Niedersachsen, Statistischer Bericht L IV 13.

Gelesen wird sie von `council/gewerbesteuerstatistik.py` in die Tabelle
`council_gewerbesteuerstatistik`; eingelesen wird von Hand
(`scripts/ingest_gewerbesteuerstatistik.py`), weil die Statistik einmal
jährlich erscheint.

**Was je Gemeinde drinsteht** (Blätter 6.1 und 6.2 des Berichts):

| Merkmal | Oldenburg, Erhebungsjahr 2021 |
|---|---|
| Betriebe und Betriebsstätten | 8.421 |
| davon mit positivem Steuermessbetrag | 3.642 (43,2 %) |
| Summe der Steuermessbeträge | 30.015.356 € |
| davon aus reiner Festsetzung | 14.103.549 € (2.763 Betriebe) |
| davon aus Zerlegung | 15.911.807 € (879 Betriebsstätten) |
| Hebesatz (nachrichtlich) | 439 % |

Im Bestand stehen die Erhebungsjahre 2017–2021 und alle acht kreisfreien
Städte — dieselbe Menge wie beim Städtevergleich, weil es derselbe
Schleifendurchlauf und dieselbe Probe ist.

### Drei Proben, und eine verlässt das Haus

1. **Summenprobe** — reine Festsetzungen + Zerlegungen = insgesamt, und zwar
   dreimal je Stadt (Fälle, zahlende Fälle, Messbetrag). Das ist nicht eine
   Kontrollrechnung neben der Tabelle, sondern ihr Aufbau: Jeder Fall ist
   entweder das eine oder das andere.
2. **Blattprobe** — Blatt 6.2 (alle Gemeinden) nennt für jede kreisfreie Stadt
   dieselben drei Zahlen wie Blatt 6.1 (kreisfreie Städte und Landkreise).
   Zwei verschieden gebaute Tabellen desselben Berichts, getrennt gelesen.
3. **Hebesatzprobe** — der Hebesatz, den das Landesamt seiner Gemeindetabelle
   nachrichtlich beilegt, steht auch in Tabelle 1105 des Statistischen
   Jahrbuchs der Stadt (`council_hebesaetze`). Zwei Häuser, dieselbe Zahl.
   Sie liest die **Treppe**, nicht das Jahr: Für 2021 gibt es keine Zeile in
   1105, es gilt der Satz der letzten Änderung davor (2015 → 439 %).

Reißt Probe 1 für eine Stadt, kommt diese Stadt nicht herein; reißen Probe 2
oder 3, kommt der **ganze Jahrgang** nicht herein.

### „g" ist kein Nullwert

Wo ein einzelner Zahler eine Gemeinde dominiert, sperrt das Landesamt den
Betrag und druckt `g` — 2021 bei Salzgitter und Wolfsburg, 2020 dort sogar in
allen neun Spalten. Der Parser unterscheidet deshalb drei Zustände, und die
Datenbank auch:

- eine Zahl → der Wert;
- `g` → `messbetrag_eur IS NULL` **plus** `gesperrt = 1`. Die Anzahlen daneben
  stehen weiter und sind die eigentliche Auskunft. Ein Parser, der `g` zu 0
  machte, behauptete, dort werde keine Gewerbesteuer gezahlt;
- alle neun Spalten gesperrt → die Stadt kommt gar nicht herein, und im
  Protokoll steht **„Geheimhaltung"**, nicht „Probe gerissen". Der Unterschied
  ist wichtig: Nichts widerspricht sich, es steht nur nichts da.

Oldenburg ist in keinem der fünf eingelesenen Jahrgänge gesperrt.

### Zwei Fallen im Dateiformat

- **Die Spaltenköpfe sind umformuliert worden.** 2017–2019 heißt eine Spalte
  „Betrag der Festsetzungen und Zerlegungen … mit positivem Steuermessbetrag
  in €", 2020/2021 „Festsetzungen und Zerlegungen …; darunter mit positivem
  Steuermessbetrag in Euro"; die Schlüsselspalte wechselte von „Regionale
  Gliederung nach AGS" zu „Amtlicher Gemeindeschlüssel". Eingeordnet wird
  deshalb über **Block und Rolle** (`spaltenzuordnung`), nicht über den
  Kopftext. Und die Einheit taugt nicht als Merkmal: Blatt 6.2 nennt sie im
  Jahrgang 2017 gar nicht.
- **Der Städtename wandert** („Oldenburg (Oldenburg), Stadt" → „Oldenburg
  (Oldb), Stadt"), und die Schlüsselnummer steht in 6.1 dreistellig, in 6.2
  sechsstellig. Verbunden wird über `schluessel_normalisieren` aus
  `council/staedtevergleich.py`; gespeichert wird **unser** Name, sonst sähe
  die Reihe nach zwei Städten aus.

### Was die Statistik nicht hergibt

Der ursprüngliche Wunsch war eine Konzentrationsaussage: „x % der Betriebe
tragen y % des Messbetrags". **Die gibt es je Gemeinde nicht.** Größenklassen
des Gewerbeertrags veröffentlicht die Statistik nur für das Land und den Bund;
die einzige Städte-Tabelle des Bundes führt die 50 Städte mit den höchsten
Steuermessbeträgen, und Oldenburg liegt mit 30,0 Mio. € knapp unter Platz 50
(35,7 Mio. €). An Oldenburger Größenklassen käme man nur über die Einzeldaten
des Forschungsdatenzentrums — Gastwissenschaftsarbeitsplatz oder kontrollierte
Datenfernverarbeitung, für wissenschaftliche Vorhaben, mit Antrag.

Belegen lässt sich die Konzentration trotzdem, nur anders: über die
Aufteilung, die je Gemeinde **doch** veröffentlicht wird. 2021 trugen 879
zerlegte Betriebsstätten — 10,4 % aller erfassten Fälle — 53,0 % des
Steuermessbetrags, je zahlendem Fall das 3,5-Fache einer rein örtlichen Firma.
Genau der Weg über die Arbeitslöhne (§ 29 GewStG), den der Block bis dahin nur
beschreiben konnte.

:::danger[Messbetrag ist nicht Aufkommen]
Der Steuermessbetrag ist die **Veranlagung** eines Erhebungsjahres
(Gewerbeertrag × 3,5 %). Das Aufkommen in `council_steuern` ist etwas
anderes, und der Hebesatz schließt die Lücke nicht. Messbetrag × 439 % gegen
das kassenmäßige Ist-Aufkommen brutto des Realsteuervergleichs:

| Jahr | Messbetrag × 439 % | Ist brutto | Abstand |
|---|---|---|---|
| 2019 | 136.458 T€ | 132.607 T€ | +2,9 % |
| 2020 | 144.391 T€ | 113.469 T€ | +27,3 % |
| 2021 | 131.767 T€ | 150.968 T€ | −12,7 % |

Der Abstand wechselt das Vorzeichen, weil Vorauszahlungen, Abschlusszahlungen
und Berichtigungen nach Betriebsprüfungen sich um Jahre verschieben. Selbst
die beiden **Aufkommens**reihen weichen voneinander ab — das doppische
Rechnungsergebnis der Stadt (Tabelle 1104) und das kassenmäßige Netto des
Landes lagen 2021 um 16,4 % auseinander.

Deshalb: keine gemeinsame Kurve, und aus einem Messbetrag wird kein „das wären
dann xxx Mio. €". Was die Schicht liefert, ist ein **Nenner**.
:::

### Der Verzug gehört an die Zahl

Eine Veranlagung ist erst nach den Betriebsprüfungen endgültig; der Bericht
erscheint rund **fünf Jahre** nach dem Erhebungsjahr (2019 → August 2024,
2020 → September 2025, 2021 → März 2026). Neben einer Aufkommenskurve bis 2025
steht also ein Nenner von 2021. Der Block schreibt das Erhebungsjahr deshalb
sichtbar an, und `ABGRENZUNG` reist als Text **mit den Daten** aus der API —
nicht als Satz im Frontend, der gegen die Zahlen driften könnte.

Jahrgänge vor 2017 gibt es nur als PDF (für 2013 nachgesehen: die
Gemeindetabelle ist da, aber im PDF-Satz). Sie brauchten einen zweiten Parser
und stehen deshalb nicht im Bestand.

## Investitionen: der zweite Haushalt

Bis 08/2026 zeigte der Bereich ausschließlich den **Ergebnis**haushalt —
laufende Erträge und Aufwendungen. Darin steht keine einzige Investition. Ein
Schulneubau taucht dort nur als Abschreibung auf, verteilt über Jahrzehnte,
lange nachdem gebaut wurde. Die häufigste Bürgerfrage überhaupt („was wird
eigentlich gebaut?") war damit unbeantwortbar, und zwar nicht aus Nachlässigkeit:
Die Zahl stand in keiner Tabelle.

Sie steht im **Finanz**haushalt, der zweiten Hälfte jedes Haushaltsplans. Ein-
und Auszahlungen statt Erträgen und Aufwendungen — das ist der Unterschied
zwischen „was verbraucht die Stadt in diesem Jahr?" und „was legt sie in
diesem Jahr an?".

### Die Quelle rechnet sich selbst vor

Datensatz 1101 des Open-Data-Portals, dasselbe Paket wie beim
Plan-Ergebnishaushalt, nur das zweite Tabellenblatt. Je Jahrgang eine Datei mit
15 Zeilen:

```
Teilhaushalt;Bezeichnung;Einzahlungen [Euro];Auszahlungen [Euro]
THH01;Verwaltungsfuehrung;0;44500
…
THH13;Nicht rechtsfaehige Stiftungen;27900;0
Finanzhaushalt Gesamtinvestitionen;;39672063;80781520
Gesamtbetrag des Finanzhaushaltes;;743796496;850520503
```

Das macht sie zur **einzigen Portal-CSV des Bereichs mit einer Rechenprobe im
Dokument selbst**: Die 13 Teilhaushalts-Zeilen müssen die Zeile *Finanzhaushalt
Gesamtinvestitionen* ergeben, in beiden Spalten. Die drei anderen Portal-CSVs
(Steuern, Steuerkraft, Einwohner) tragen ausdrücklich keine und stehen mit
`herkunft.UNGEPRUEFT` in der Datenbank. Über die vier verfügbaren Jahrgänge
(2022–2025) geht die Probe auf den Euro genau auf — acht Proben, Restbetrag
jeweils 0 €.

:::caution[Die Toleranz ist kleiner als ein Euro, und das ist der Punkt]
Die Datei führt volle Euro ohne Nachkommastellen. Die kleinste Abweichung, die
es hier überhaupt geben kann, ist damit 1 € — eine Toleranz von 1 € ließe genau
diesen Fall durch und wäre für den einzigen Fehler blind, den die Probe sehen
könnte. `investitionen.TOLERANZ_EUR` steht deshalb auf **0,5**. Aufgefallen
beim Schreiben von `tests/test_investitionen.py`, wo der manipulierte Jahrgang
zunächst bestand.
:::

### Eine Zahl in der Datei ist nicht gedeckt — und wird als solche geführt

Die zweite Summenzeile, *Gesamtbetrag des Finanzhaushaltes*, zählt auch die
laufende Verwaltungstätigkeit mit (Personal, Zuschüsse, Steuern) und ist rund
zehnmal so groß wie die Investitionssumme. **Nichts in der Datei summiert sich
auf sie.** Sie wird trotzdem übernommen, weil sie die Bezugsgröße ist, die aus
„80,8 Mio. €" erst eine Aussage macht (2025: 9,5 % aller Auszahlungen) — aber
mit einer **eigenen** `herkunft_id` und `herkunft.UNGEPRUEFT`. Käme sie unter
derselben Herkunft wie die geprüften Zeilen, behauptete die Seite eine Probe,
die es für diese Zahl nicht gibt. `save_investitionen` nimmt die zweite
Herkunft deshalb als eigenes Argument.

### Drei Eigenheiten der Quelle

1. **Das Jahr steht nicht in der Datei.** Keine Spalte, keine Kopfzeile. Es
   steht im Dateinamen (`…_2025_Finanzhaushalt.csv`) und im Titel des
   Datensatzes. Der Jahrgang kommt deshalb aus der URL
   (`investitionen.jahrgang_aus_url`), und die Herkunft nennt den Dateinamen
   ausdrücklich als Fundstelle des Jahrgangs. Das ist die schwächste Stelle
   dieser Schicht; sie wird ausgewiesen statt weggelassen.
2. **Die Schreibweisen schwanken zwischen den Jahrgängen.** 2022 steht dort
   „Verkehr und Straßenbau" und „Gruen u Friedhoefe", 2025 „Strassenbau" und
   „Gruen und Friedhoefe"; 2022 hat außerdem „Sicherheit  und Ordnung" mit
   doppeltem Leerzeichen und als einziger die Kopfzeile „Einzahlungen in Euro"
   statt „[Euro]". `investitionen.NAMEN` führt die bekannten Formen zusammen —
   sonst stünden in jeder Zeitreihe zwei Bereiche, wo einer ist. Unbekannte
   Namen laufen unverändert durch: Ein neuer Teilhaushalts-Zuschnitt soll den
   Import nicht stoppen. Der Schlüssel ist ohnehin `thh_nr`, nicht der Name.
3. **Der Jahrgang erscheint erst im Folgejahr.** Gemessen an den vier
   Lieferungen: 2023 → 19.06.2024, 2024 → 16.06.2025, 2025 → 14.07.2026 (2022
   kam am 24.04.2024 als Nachzügler). `Finanzquelle.erwarteter_monat` steht
   deshalb auf **Juli**, dem spätesten gemessenen Monat — mit Juni meldete der
   Cron den Jahrgang 2025 drei Wochen lang als überfällig, obwohl das Portal
   nur seinem üblichen Takt folgte.

### Was die Seite sagen muss

`/haushalt/investitionen` trägt einen eigenen Block „Was diese Zahlen nicht
sagen", und er steht nicht am Ende, sondern als Abschnitt. Drei Sätze müssen
hängen bleiben:

- **Schulgebäude stehen nicht darin** — siehe den Abschnitt zum
  Investitionsprogramm unten.
- **Plan, nicht Ist.** Was am Jahresende wirklich verbaut wurde, steht nicht
  darin. Bei Investitionen ist der Abstand notorisch groß.
- **Die Zahlen enden 2025**, weil das Portal erst im Folgejahr liefert.
- **Die beiden Summen der Seite zählen Verschiedenes** — auch das unten.

Der Anteil am Finanzhaushalt ist **unsere** Division und steht auf der Seite als
solche gekennzeichnet; die beiden Beträge darin stehen so in der Quelle.

## Investitionsprogramm: die einzelne Maßnahme

Die Ebene unter `council_investitionen`, auf derselben Seite: nicht „Schule und
Bildung: 8,3 Mio. €", sondern „BBS Haarentor: Ausstattung". Quelle ist **Anlage
004 des Haushaltsplans**, seit acht Jahrgängen (2019–2026) im Anlagenbestand —
kein Download nötig, der Cron liest sie wie den Gesamtergebnishaushalt und den
Stellenplan aus `council_anlagen` (`council/investitionsprogramm.py`).

Gemessen über alle acht Jahrgänge: **4.459 Vorhaben**, 102 Teilhaushalts-Summen,
kein verworfener Jahrgang.

### Drei Proben, und die mittlere ist die stärkste

Das Dokument rechnet sich selbst vor, auf drei Ebenen. Alle drei gehen in allen
acht Jahrgängen **auf den Euro** auf:

1. **`investitionsprogramm_abschnitt`** — die Vorhaben eines Teilhaushalts
   ergeben die `Gesamtsumme` seines Abschnitts.
2. **`investitionsprogramm_wiederholung`** — diese Summe steht ein zweites Mal
   im Dokument, rund siebzig Seiten früher, in der Übersicht
   „Investitionssummen je Teilhaushalt". Zwei unabhängig gesetzte Stellen, die
   übereinstimmen müssen. Verglichen wird über den **Betrag**, nicht über den
   Namen: Die Übersicht schreibt „Klima/Umwelt/Mobilität/Bau/Grün/Fri edh.", der
   Abschnittskopf „…/Friedh." — über den Namen verglichen scheiterte die Probe
   an einem Zeilenumbruch statt an einer Zahl.
3. **`investitionsprogramm_kopftabelle`** — in dieser Übersicht ergeben die
   Teilhaushalte die ausgewiesene Gesamtsumme (2026: 170.140.918 €).

Reißt eine, fällt der ganze Jahrgang; halbe Maßnahmen kommen nicht herein.

### Nur eine Spalte — und warum das die richtige Entscheidung ist

Die Tabelle führt neun Spalten: Gesamtinvestitionssumme, bisher bereitgestellt,
und je Planjahr Ansatz und Verpflichtungsermächtigung. Übernommen wird **nur die
erste**.

Grund ist der Textextrakt: Leere Zellen fallen darin ersatzlos weg. Eine Zeile
mit sechs Zahlen kann die Spalten 1, 2, 3, 4, 6, 8 meinen oder 1, 2, 5, 7, 8, 9
— welche, steht nirgends. Zu retten wären sie nur über die x-Koordinaten des
PDFs, und die trägt `council_anlagen.raw_text` nicht. Die **erste** Zahl einer
Zeile ist dagegen immer die Gesamtinvestitionssumme: Sie ist die linke Spalte,
und links kann nichts wegfallen. Eine Spalte, die trägt, ist mehr wert als fünf
geratene — die Seite sagt, dass die Jahresaufteilung fehlt.

### Drei Fallen, jede real aufgetreten

1. **Jede Maßnahme steht zweimal da** — als IPSP-Element (`I10.090126`) und als
   Sachkonto-Detailzeile (`I10.090126.525`) mit denselben Beträgen; 31
   Elternelemente haben mehrere Kinder. Gezählt wird nur das Elternelement.
2. **Namen brechen um**, und der Rest landet mal auf einer eigenen Zeile
   („Inklusion, Baukosten," / „2026" / „0 0"), mal **vor den Beträgen derselben
   Zeile** („Erwerb Sportgeräte," / „2027 110.000 110.000"). Die zweite Form
   kostete THH06, weil das führende Jahr als Betrag gelesen wurde.
3. **Ziffern im Namen sind keine Beträge.** Fachdienst-Nummern
   („…, FD 102, 2026 135.000 135.000"), Bebauungsplan-Nummern („BPL 823") und
   die Seitenzahl am Blattfuß sehen wie Zahlen aus. Die erste Fassung suchte vom
   Zeilenanfang nach der ersten Zahl und las 102 statt 135.000 — dem
   Teilhaushalt 02 fehlten 134.898 €, und Probe 1 hat es gefunden.

Gelesen wird deshalb vom **Zeilenende** her, solange die Token Tausenderpunkte
tragen oder Null sind; besteht eine Zeile ganz aus Zahlen (mindestens zwei,
mindestens eine mit Punkt), gilt der erste Token mit Punkt. Das deckt auch
Beträge unter 1.000 ab, die es gibt („6.100 4.000 700 700 700").

### Was das Programm nicht hergibt

- **Keine Schulgebäude.** Der Teilhaushalt „Schule und Bildung" führt
  Ausstattung und die berufsbildenden Schulen namentlich (BBS Haarentor, BBS
  Maastrichter Str., BBS Wechloy, BZTG); die allgemeinbildenden Schulen stehen
  nur als Sammelposten. Sanierung und Neubau der Gebäude liegen beim
  **Eigenbetrieb Gebäudewirtschaft und Hochbau** mit eigenem Wirtschaftsplan,
  den dieses Dokument nur referenziert. Die Frage „wird MEINE Schule saniert?"
  ist damit auch hier nicht beantwortet, und die Seite sagt das.
- **Plan, und zwar der Entwurf.** Die Anlage hängt an der Einbringungs-Vorlage;
  was der Rat in den Beratungen ändert, steht nicht darin (das steht in der
  Herkunft als `stand`).
- **Negative Beträge sind normal**, keine Fehler: Tilgungen, Zuschüsse von Land
  und Bund, Grundstücksverkäufe. „Finanzmanagement und Recht" ist 2026 in der
  Summe −121,4 Mio. €. Sie bekommen kein Rot (keine Bewertungsfarben) und dürfen
  nicht weggelassen werden — ohne sie ginge keine Probe auf.

### Kein Abgleich mit `council_investitionen` — und warum das keine Lücke ist

Naheliegend wäre, die Teilhaushalts-Summen des Programms gegen die
Investitionen aus Datensatz 1101 zu halten. Das wäre **keine Probe, sondern ein
Fehlschluss**: Das Dokument sagt in einer Fußnote der Übersicht selbst an, dass
seine Gesamtsumme von der Zeile 31 „Saldo aus Investitionstätigkeit" des
Gesamtfinanzhaushaltes abweicht — zu aktivierende Eigenleistungen gehören ins
Investitionsprogramm, sind aber nicht zahlungswirksam und stehen deshalb nicht
im Finanzhaushalt. Dazu kommt: Das Programm führt die **Gesamtkosten über alle
Jahre**, der Finanzhaushalt die **Zahlungen eines Jahres**.

Beide Zahlen stimmen und zählen Verschiedenes. Auf der Seite steht das als
Erklärung, die Verbindung zwischen den beiden Blöcken ist **Navigation**
(„welche Vorhaben stecken in diesem Bereich?") und nirgends eine Differenz.

## Gebaut: das Ist zum Investitionsplan

`/haushalt/gebaut` beantwortet die Frage, die der Abschnitt darüber offen
lässt: Was ist von dem Geplanten wirklich abgeflossen? Die Quelle ist das
**Statistische Jahrbuch der Stadt**, Kapitel 11 — dieselbe Veröffentlichung,
aus der auch die Schuldenzeitreihe kommt.

### Zwei Tabellen, zwei Rechnungswesen

Die Stadt liefert beide in **einer** PDF-Datei, aber als **zwei** Tabellen, und
sie begründet den Schnitt selbst in einer Fußnote:

> Einführung Neues Komunales Rechnungswesens (NKR) zum 01. Januar 2010.

- **1107 (2003–2009)** heißt „**Ausgaben** der Stadt Oldenburg für eigene
  Investitionen" und führt vier Arten, darunter „Gewährung von Darlehen".
- **1107-1 (2010–2025)** heißt „**Auszahlungen** der Stadt Oldenburg für
  Investitionstätigkeiten" und führt sechs Arten, nach den Positionen, die
  § 3 GemHKVO für die Finanzrechnung vorgibt. Der Untertitel nennt zusätzlich
  die Abgrenzung: „Rechnungsergebnisse laut Finanzrechnung der
  **Kernverwaltung**".

Deshalb trägt jeder Jahrgang seine Spalte `regelwerk`, deshalb hat jedes
Regelwerk **eigene** Feldnamen (auch wo sich zwei Überschriften ähneln), und
deshalb zeichnet die Seite zwei getrennte Diagramme statt einer Achse. Wer die
beiden Reihen verbindet, behauptet eine Vergleichbarkeit, die das Dokument mit
seiner Fußnote gerade bestreitet.

### Eine Probe, und warum es keine zweite gibt

`investitionen_ist.zeilensumme` ist die Probe des Dokuments: Die
Auszahlungsarten einer Zeile ergeben die Summe, die dieselbe Zeile daneben
ausweist. Sie greift in **22 von 23** Jahrgängen.

**2019 reißt sie**, im Dokument selbst: Die sechs Arten ergeben 66.595 T€,
ausgewiesen sind 67.899 T€ — 1,304 Mio. € Unterschied. Welche der sieben
Zahlen danebenliegt, sagt die Tabelle nicht.

Bei den Schulden rettete an dieser Stelle eine zweite, unabhängige Probe den
Jahrgang (Fall 2022, siehe unten): Die Summe hing an der Pro-Kopf-Gegenprobe,
also kam sie herein und nur die Aufteilung fiel. Für 1107-1 wurde dieselbe
zweite Probe gesucht und **nicht gefunden**:

| Gesucht | Befund |
|---|---|
| Pro-Kopf-Spalte in der Tabelle | Es gibt keine. Eine eigene Division wäre unsere Rechnung und könnte einen Übertragungsfehler nicht aufdecken. |
| Zweite Ausgabe des Jahrbuchs (Überlappungsprobe) | Die Übersichtsseite führt Tabellen aus zwei Jahrgängen, für Kapitel 11 aber nur den von 2025. Die Vorjahresdatei ist nicht mehr abrufbar. |
| Spiegel im Open-Data-Portal | Das Portal führt 91 Datensätze, darunter die kameralen Ausgaben bis 2009 und die ordentlichen Aufwendungen seit 2010 — die Investitions-Ist-Zahlen sind nicht dabei. |
| Der Plan als Gegenprobe | Andere Abgrenzung, siehe unten — keine Probe, sondern eine andere Größe. |

Also gilt die Grundregel ohne Rettungsanker: **2019 wird ganz verworfen**, mit
allen sieben Zahlen — anders als 2022 bei den Schulden ist hier auch die Summe
durch nichts gedeckt. Die Seite zeichnet für das Jahr einen schraffierten
Platzhalter mit gestricheltem Rahmen und benennt die Lücke im Text; der
Endpunkt liefert sie als `fehlend`.

**Mit ihrer Weite.** Der Ingest-Lauf schreibt die verworfenen Jahrgänge nach
`council_investitionen_ist_verworfen` — Grund als Satz, `differenz` als Zahl
(Arten minus ausgewiesene Summe, in Euro). `fehlend` trägt sie je Lücke mit,
und die Seite macht daraus „verworfen: 1,3 Mio. € Differenz im Dokument".
Dieselbe Rolle wie `aufteilung_verworfen` bei den Schulden, nur eine Tabelle
weiter: Dort trägt die gerettete Zeile ihre Lücke selbst, hier gibt es keine
Zeile, die sie tragen könnte. Wo der Bestand keine Messung führt, kommt
`differenz: null` — dann nennt die Seite die Lücke **ohne** Betrag. Der Betrag
steht an keiner Stelle im Frontend; er wird mit dem nächsten Jahrbuch neu
gemessen oder verschwindet.

### Warum die Seite keine „Umsetzungsquote" zeigt

Die naheliegende Zahl wäre `Ist ÷ Plan`. Gerechnet ergäbe sie für 2022–2025
Werte zwischen 41 % und 75 %. Sie steht auf keiner Seite, und das ist kein
Übersehen:

- Der **Plan** (`council_investitionen`, Datensatz 1101) ist nach
  **Teilhaushalten** gegliedert — nach Organisation.
- Das **Ist** (`council_investitionen_ist`) stammt aus der Finanzrechnung der
  **Kernverwaltung** und ist nach **Auszahlungsarten** gegliedert.

Keine der beiden Quellen nennt die andere, keine weist eine Differenz aus, und
keine sagt, dass ihre Gesamtsumme dieselbe Menge zählt. Die Quote wäre die
meistgelesene Zahl der Seite und die einzige, die in keinem Dokument steht.
Beide Seiten stehen deshalb nebeneinander und verlinken einander; die
Begründung steht auf `/haushalt/gebaut` als eigener Block, nicht als Fußnote.

Dieselbe Regel gilt im Prompt der KI-Frage: `qa._gebaut_block` trägt sie im
Klartext, und die Facetten `investitionen` und `gebaut` stehen in
`GELD_FACETTEN` **nebeneinander**, damit nicht eine von beiden am
Zeichenbudget herausfällt und die Warnung an einer Zahl hinge, die gar nicht
im Kontext steht.

### Die Falle im Textextrakt

Wie bei Tabelle 1108 klebt eine Fußnotenziffer an einer Zahl — hier aber im
**Titel** und nicht an den Beträgen: Aus „in Tausend Euro 2010 bis 2025" mit
Fußnote 1 wird im Extrakt `2010 bis 20251`. Die Erkennung nimmt die Ziffer
ausdrücklich als Marke an (Jahreszahlen haben vier Stellen). In den
Datenzeilen selbst trägt heute kein Betrag eine Marke — geprüft an allen 23
Zeilen mit einem Positions-Dump des PDFs; die Zellen-Regel bringt sie
trotzdem mit, weil sie nichts kostet.

### Was die Zahlen nicht sagen

- **Nicht die ganze Bautätigkeit.** Gezählt wird die Kernverwaltung. Was der
  Eigenbetrieb Gebäudewirtschaft und Hochbau baut — seit 2010 ein großer Teil
  des städtischen Hochbaus —, steht nicht darin.
- **Kein einzelnes Vorhaben.** „Baumaßnahmen: 16,2 Mio. €" sagt nicht, welche
  Straße. Die Vorhaben-Ebene gibt es nur auf der **Plan**-Seite
  (`council_investitionsmassnahmen`, Abschnitt darüber) — und auch dort ohne
  die Schulgebäude, die beim Eigenbetrieb liegen. Ein Ist je Vorhaben führt
  keine der beiden Quellen.
- **„Sonstige Investitionstätigkeit" bleibt unaufgeschlüsselt** und ist in den
  jüngeren Jahrgängen einer der größten Posten (2018 sprang er von 123.000 €
  auf 19 Mio. €). Das Jahrbuch sagt nicht, was darin steckt, und die Seite
  vermutet es nicht.
- **Ein Abfluss, kein Baufortschritt.** Eine Abschlagszahlung im Dezember
  zählt für das alte Jahr, auch wenn der Bagger im März kommt.

## Schulden: eine Zahl, die es zweimal gibt

`/haushalt/schulden` beantwortet die häufigste offene Frage an den Bereich —
und die Antwort hängt vollständig daran, **was** gezählt wird. Bei
Kommunalschulden gibt es zwei Werte, die beide „die Schulden der Stadt" heißen
und sich um ein Vielfaches unterscheiden.

Quelle ist **Tabelle 1108 des Statistischen Jahrbuchs** (`council/schulden.py`,
`scripts/ingest_schulden.py`): eine Seite, dreißig Jahre, je Jahr vier
Schuldenarten, ihre Summe und der Betrag je Einwohner\*in.

### Die Abgrenzung, und woran sie festgemacht ist

Gezählt wird die **Stadt als Rechtsträger**: Kernhaushalt *und* Eigenbetriebe,
ohne die rechtlich selbstständigen Beteiligungen. Das steht nicht als Satz in
der Tabelle, sondern in ihren Spalten und Fußnoten:

1. Die vierte Spalte heißt „Schulden der Eigenbetriebe einschließlich Kliniken
   und innere Darlehen" — Eigenbetriebe haben keine eigene
   Rechtspersönlichkeit, ihre Schulden sind rechtlich die der Stadt.
2. Fußnote 1: „Ab 1999 ohne Kliniken, die jetzt als Klinikum Oldenburg AöR
   geführt werden." Sobald eine Einheit eine eigene Rechtsform bekommt, fällt
   sie aus der Reihe. Das Kriterium ist damit benannt: Rechtsträgerschaft,
   nicht Eigentum.
3. Fußnote 3 sagt es ausdrücklich (Weser-Ems-Halle): „Die Schulden des
   Eigenbetriebs verbleiben rechtlich bei der Stadt. Wirtschaftlich werden die
   Darlehen der WEH GmbH & Co. KG zugerechnet." Die Tabelle folgt der
   rechtlichen Zurechnung.

Der Wortlaut steht als `schulden.ABGRENZUNG` **im Backend** und kommt über das
Feld `abgrenzung` des Endpunkts auf die Seite — zwei Formulierungen für
dieselbe Grenze wären zwei Grenzen.

### Zwei Proben, und 2022 braucht beide

- **`schulden_summenzeile`** (intern): Die vier Schuldenarten müssen die Summe
  ergeben, die die Tabelle daneben ausweist. Ohne Toleranz — die Quelle rundet
  auf volle Tausend und geht in 30 von 31 Jahrgängen auf den Euro auf.
- **`schulden_prokopf`** (unabhängig, und damit die stärkere): Die
  ausgewiesene Gesamtschuld, geteilt durch die Einwohnerzahl aus
  `council_einwohner` (Datensatz 1102), muss den Pro-Kopf-Betrag derselben
  Zeile ergeben. Beide Seiten stammen aus **verschiedenen Veröffentlichungen**
  der Stadt, und die Stichtage decken sich exakt (1108 im Kopf:
  „Bevölkerungsstand: 31. Dezember des Vorjahres"; 1102 in der Spaltenüberschrift:
  „Einwohner am 31.12. des Vorjahres"). Ergebnis: **16 von 16** prüfbaren
  Jahrgängen gehen auf.

**2022 ist der Fall, für den beide gebaut sind.** Dort ergeben die
Schuldenarten 282.535 T€, ausgewiesen sind 281.457 T€ — 1,078 Mio. €
Unterschied, im Dokument selbst. Die Summenprobe reißt. Die Pro-Kopf-Probe
entscheidet den Jahrgang: 281.457.000 € / 170.389 = 1.651,85 €, und genau
1.652 € nennt die Tabelle. Also kommt die **Summe** herein und die
**Aufteilung** nicht (die vier Artenspalten stehen auf `NULL`,
`aufteilung_verworfen` hält die Lücke fest). Welche Spalte danebenliegt, sagt
das Dokument nicht, und geraten wird nicht. Die Seite benennt die Lücke, statt
einen leeren Balken zu zeichnen.

Weil die Probenlage nicht für alle Jahrgänge gleich ist, schreibt der Ingest
**drei** Herkünfte statt einer: 1995–2009 (nur Summenprobe, davor gibt es keine
Einwohnerzahlen), 2010–2025 ohne 2022 (beide), 2022 (nur Pro-Kopf). Der Beleg
auf der Seite soll für *die jeweilige* Zahl gelten.

### Die Falle im Textextrakt

Fußnotenziffern kleben an den Beträgen: `26.5981` ist 26.598 mit Fußnote 1,
nicht 265.981. Ein Parser, der bloß die Tausenderpunkte entfernt, liest dort
das Zehnfache und meldet nichts. Auflösbar ist das, weil deutsche
Tausendergruppen **genau drei** Ziffern haben — was hinter der letzten
vollständigen Gruppe steht, gehört nicht mehr zur Zahl. Dasselbe gilt für das
`r` revidierter Werte (`251.160r`), das als Angabe erhalten bleibt. Vier
Jahrgänge tragen solche Marken (1999, 2001, 2008, 2010), und die Summenprobe
schließt in allen vieren — sie prüft damit nicht nur die Quelle, sondern auch
den Entzerrer.

### Was die Kurve nicht bewertet

Die beiden größten Sprünge der Reihe sind **keine Politik**, und die Seite sagt
das im Text statt es der Farbe zu überlassen (Bewertungsfarben sind im ganzen
Bereich ausgeschlossen, s. `components/grafik/hantel.tsx`):

- **2001, −139,1 Mio. €:** Die Stadtentwässerung ging an den
  Oldenburgisch-Ostfriesischen Wasserverband, der dabei Darlehen über
  139,5 Mio. € übernahm (Fußnote 2). Kein Abbau, sondern ein Übergang mit der
  Aufgabe.
- **2010, 108,9 Mio. € Spaltenwechsel bei nahezu gleicher Summe:** Gründung des
  Eigenbetriebs Gebäudewirtschaft und Hochbau (Fußnote 4). Die
  Kreditmarkt-Spalte fällt von 130,8 auf 30,5 Mio., die Eigenbetriebs-Spalte
  steigt von 18,6 auf 123,5 Mio., die Summe bewegt sich von 149,5 auf
  154,0 Mio. Wer nur die erste Spalte zeigte, verkündete einen Schuldenabbau um
  drei Viertel, den es nie gab — der Grund, warum die Spalten einzeln
  gespeichert werden.

Aus demselben Grund trägt die Seite **zwei Ansichten**: Über dreißig Jahre sind
die Schulden absolut um 35,5 Mio. € gestiegen und je Einwohner\*in um 106 €
gesunken, weil die Stadt in derselben Zeit gewachsen ist. Nur die absolute
Reihe zu zeigen läse Bevölkerungswachstum als Schuldenaufbau.

## Nachbewilligungen: was am Plan vorbei beschlossen wurde

`council/nachbewilligungen.py` · Tabellen `council_nachbewilligungen`,
`council_nachbewilligung_jahre`, `council_nachbewilligung_kanaele` · Ingest
`scripts/ingest_nachbewilligungen.py` · Seite `/haushalt/plan-ist`

Nach § 117 NKomVG braucht jede Ausgabe, die im beschlossenen Haushalt nicht
oder nicht in dieser Höhe steht, eine eigene Bewilligung. Im
Ratsinformationssystem sind das seit 2018 **161 Vorlagen**.

### Zwei Quellen, zwei verschiedene Fragen

| Quelle | Was sie beantwortet | Zeitraum |
|---|---|---|
| Vorlagen im RIS | Was hat der Rat beschlossen? Mit Betrag und Beschluss-Seite | seit 2018 |
| Rechenschaftsbericht, Kapitel 3 | Wie viel wurde **insgesamt** nachbewilligt, auf welchem der vier Wege? | 2022–2024 |

Der zweite Bestand ist der Grund, warum es den ersten nicht allein tun darf:
Die Gesamtsumme stieg von 26,68 (2022) über 40,24 (2023) auf **57,49 Mio. €**
(2024), der Anteil mit Ratsbeschluss fiel von 89 auf **73 %**. Die vier Wege
sind Rat, Oberbürgermeister, Fachdienst 200 per Haushaltsvermerk und
Eilentscheidung.

### Die zweistufige Extraktion

Stufe 1 ist der Titel, Stufe 2 der Beschlussvorschlag der Vorlage. Gemessen
am Bestand vom 18.08.2026: **145 von 152 Einzelvorlagen (95,4 %) tragen ihren
Betrag im Titel**, die restlichen sieben schließt der Beschlussvorschlag
vollständig — zweistufig also **152 von 152**.

Die Ausreißer, an denen ein naiver Regex scheitert, stehen alle als Fixture
in `tests/test_nachbewilligungen.py`: „1 Million EUR" ausgeschrieben,
„341.000 **EU**" als Tippfehler der Stadt, „450.000,00 €" mit Cent und
Eurozeichen, „insgesamt 500.000 Euro", und die umgedrehte Wortstellung
(„Stadion Marschweg … – Außerplanmäßige Verpflichtungsermächtigung …").

Zwei Dinge, die im Bestand anders liegen, als man erwartet:

- **`council_decisions.kvonr` ist durchgehend `NULL`** (8.369 von 8.369). Der
  Join auf `council_vorlagen` läuft ausschließlich über den Text
  `vorlage_nr`; ein Join über `kvonr` liefert schweigend null Treffer.
- **`council_vorlagen.beschlussvorschlag` ist fast leer** (7 von 5.019
  Zeilen). Die zweite Stufe erntet den Vorschlag deshalb aus `raw_text` — mit
  derselben Funktion, die auch die Spalte füllt (`council/ernte.py`).

### Die drei Proben

1. **`nachbewilligung_volltext`** (intern) — der Titelbetrag steht im
   Volltext derselben Vorlage noch einmal: **145 von 145**.
2. **`nachbewilligung_ratsabgleich`** (extern, die härteste im Bereich) — der
   Rechenschaftsbericht nennt dieselben Fälle **mit Vorlagen-Nummern**.
3. **`nachbewilligung_tabellenprobe`** (im Dokument) — die vier Wege ergeben
   die Summenzeile, beide Spalten zusammen die Gesamtsumme des Fließtextes.

| Jahr | unsere Summe | Bericht (Rat) | Abweichung | Fallliste |
|---|---|---|---|---|
| 2022 | 23.956.742,00 | 23.825.742,00 | +0,55 % | 11 von 12 |
| 2023 | 33.871.800,00 | 33.871.700,00 | +100 € | 26 von 26 |
| 2024 | 43.096.100,00 | 42.171.646,29 | +2,19 % | 21 von 21 |

**Die 2024er Abweichung ist auf den Cent aufgelöst** und keine Unschärfe,
sondern eine Definitionsdifferenz: Drei Vorlagen wurden niedriger gebucht als
beantragt — 24/0411 (190.000 → 51.500), 24/0678 (430.000 → 230.000) und
24/0648 (11.232.400 → 10.646.446,29, „Reduzierung aufgrund fehlender
Erträge"). Zusammen exakt 924.453,71 €. **Wir zählen, was die Vorlage
beantragt; der Bericht zählt, was gebucht wurde** — deshalb endet seine Zahl
auf ,29 und unsere sind glatt. Die 2022er Differenz ist eine einzige Vorlage
(22/0914, 131.000 €), die der Bericht in seinem Kapitel nicht führt; sie ist
zugleich der einzige Rest beim Nummern-Abgleich, Fallliste und Summe zeigen
also auf denselben Fall.

### Zwei Dokument-Widersprüche, beide angezeigt statt geglättet

- **2022:** Der Fließtext nennt 26.969.523,30 €, seine eigene Tabelle ergibt
  26.681.523,30 € — **288.000 € Unterschied**. Der Fließtext widerspricht
  dabei sich selbst: Seine beiden Teilbeträge ergeben die Tabellensumme, nicht
  seine Gesamtzahl.
- **2023:** In der Zeile „Fachdienst 200" steht investiv **Anzahl 0 und
  trotzdem ein Betrag von 1.051.184,65 €** — auf den Cent derselbe Wert wie
  im Vorjahr an derselben Stelle. Die Summenzeile rechnet ihn nicht mit
  (8.470.300,00 + 365.007,05 = 8.835.307,05 genau), der Fließtext auch nicht.
  Drei unabhängige Signale sprechen für einen Übernahmerest aus der
  Vorjahrestabelle; repariert wird trotzdem nichts.

2024 geht beides auf den Cent auf — der Jahrgang ist die Gegenprobe dafür,
dass die Probe nicht grundsätzlich meckert.

### Drei Fallen, alle vermessen

1. **Verpflichtungsermächtigungen gehören nicht in die Summe.** Sie binden
   künftige Jahre, fließen aber nicht in diesem; der Bericht zählt sie
   ausdrücklich getrennt. 19 Vorlagen im Bestand.
2. **Sitzungsdatum ≠ Haushaltsjahr.** Maßgeblich ist der Jahrgang der
   Vorlagen-Nummer: Das Kapitel für 2022 führt die Vorlage 23/0010, das für
   2023 die 24/0029, das für 2024 die 25/0002. Naiv nach Sitzungsjahr
   summiert liegt man 20 bis 27 % daneben.
3. **Die Sammelberichte tragen Schwellenwerte, keine Beträge.** „… bis zu
   50.000 Euro" ist die Grenze, unter der der Rat gar nicht entscheidet. Neun
   solche Vorlagen; sie bekommen `art='schwelle'` und **keinen** Betrag.

### „Im Rat beschlossen" heißt mehr, als es klingt

Der Rechenschaftsbericht bucht auch das unter „Beschluss des Rates", was der
**Ausschuss für Finanzen und Beteiligungen abschließend** entscheidet. 2024
haben **8 von 21 Fällen keine Plenarsitzung mehr gesehen** — der Rat tagte am
16.12.2024 als Haushaltssitzung mit 21 Punkten, keiner davon eine
Nachbewilligung. Wer den Rats-Anteil aus dem Gremiennamen rechnet,
veröffentlicht für 2024 30.896.100 statt 43.096.100 €, also **28 % zu wenig**
— ausgerechnet für die Kennzahl „der Rats-Anteil sinkt". Deshalb trägt
`Bewilligung` zwei Eigenschaften: `im_rat` (das Plenum hat abgestimmt, eine
Auskunft für Leser\*innen) und `ratsentscheidung` (die Definition des
Berichts, die einzige, die in eine Summe darf).

### Die Zähleinheit ist die Vorlage

287 Beschlusszeilen stehen über 156 Vorlagen — **131 Dubletten**, weil
Finanzausschuss und Rat über dieselbe Sache abstimmen. Je Zeile gezählt wäre
fast jeder Betrag doppelt in der Summe. Fünf Vorlagen tragen gar keine
Beschlusszeile; beantragt ist nicht bewilligt, sie zählen nicht mit.

### Betrieb

Der Ingest lädt nichts nach, aber er braucht Vorlauf: Die drei
Rechenschaftsberichte (Dokumente 265441, 280862, 295295) liegen mit
`status='listed'` und **leerem** `raw_text` im Bestand. Ohne
`backfill_anlagen_texte.py --nur-finanz` bleibt Kapitel 3 leer — und übrig
bliebe genau die halbe Wahrheit, gegen die dieser Block gebaut ist. Der
Ops-Workflow hält die Reihenfolge ein.

Die fünf älteren Berichte (2017–2021: 192336, 205649, 219465, 238770, 250437)
liegen ebenfalls als Anlage vor. Seit dem 18.08.2026 tragen sie auch Volltext —
das Label-Muster der Finanzquellen kannte „Rechenschaftsbericht" bis dahin
nicht. Sie kommen trotzdem **nicht** in `BERICHTE` dazu: Gegen `kapitel3`
gehalten findet der Parser dort nur einen bis drei der vier Entscheidungswege,
und die Spaltenprobe reißt in jedem der fünf Jahrgänge (investiv 0,55 bis
0,92 Mio. €). Das Kapitel gibt es, sein Tabellenlayout ist ein anderes. Die
Reihe bleibt bei 2022–2024, statt Zahlen zu zeigen, die ihre eigene Probe
nicht bestehen.

### Der Nebenbefund

In acht Jahren wurde **keine einzige** Nachbewilligung abgelehnt. Das steht
auf der Seite als Befund, nicht als Vorwurf: Die Vorlagen sind vorher im
Fachausschuss beraten, und was dort keine Mehrheit findet, erreicht den Rat
meist gar nicht erst.

## Die dreizehn Kennzahlen: die Zusammenfassung der Stadt selbst

Am Ende jedes Rechenschaftsberichts steht die Anlage „Kennzahlenübersicht und
Berechnungsmethoden": dreizehn Zahlen, auf die die Stadt ihren ganzen
Jahresabschluss eindampft — Eigenkapitalquote, Anlagenintensität, Steuerquote,
Verschuldung je Kopf. Parser: `council/kennzahlen.py`, Tabellen
`council_kennzahlen` und `council_kennzahl_formeln`, Seite
`/haushalt/kennzahlen`.

Der Grund, diese Schicht überhaupt zu bauen, steht **unter** der Tabelle: die
gedruckten Rechenwege. „Ermittlung: Sachvermögen \* 100 / Bilanzsumme" ist ein
Zitat, keine Definition von uns — und damit die einzige Stelle im Bereich, an
der eine Kennzahl gezeigt werden darf, ohne dass wir sie erfunden hätten.

### Ein Bericht sind fünf Jahre, und die Berichte widersprechen sich

Jeder Bericht druckt fünf Jahrgänge. Sechs Berichte (2019–2024) decken so
**2015–2024** ab, und die mittleren Jahre stehen mehrfach da. Von 240
doppelt gedruckten Zellen stimmen 221 exakt überein. Die übrigen sind der
Ertrag dieser Schicht:

| Kennzahl | Jahr | alt | neu |
|---|---|---|---|
| Steuerquote | 2021 | 45,90 % (Bericht 2021) | 49,05 % (2022), dann 45,92 % (2023) |
| Steuerquote | 2022 | 46,16 % (Bericht 2022) | 44,00 % (2023) |
| Verschuldung je Einwohner\*in (mit Rückstellungen) | 2021 | 2.340,30 € | 2.224,11 € |
| Netto-Neuinvestitionen je Einwohner\*in | 2021 | 120,45 € | 151,81 € |

Die Steuerquote 2021 geht hoch und wieder zurück: Der Bericht 2022 hat diese
Zeile verrechnet, der Bericht 2023 hat sie ohne Anmerkung geradegezogen.
Deshalb steht `bericht_jahr` **im Primärschlüssel** — ohne ihn überschriebe der
jüngere Stand den älteren still, und die Korrektur wäre weg.

### Rechenwegwechsel: drei gedruckte, einer echt

Drei Kennzahlen haben zwischen 2019 und 2024 ihre gedruckte Formel geändert.
Ob das etwas bedeutet, wird **gemessen**, nicht angenommen — ein geänderter
Rechenweg schaltet den Wertvergleich nicht ab:

- **Personalintensität** — „Aufwand für Personal (inklusive Versorgung)" wurde
  „Aufwendungen für aktives Personal". Die Werte springen (2020: 26,03 % →
  25,09 %). Ein echter Definitionswechsel; über die Stelle läuft auf der Seite
  keine Linie (`JahrWert.bruchDavor`, GB-00).
- **Verschuldung je Einwohner\*in** — „Gesamtschulden" wurde „Schulden".
- **Vermögen je Einwohner\*in** — „Gesamtvermögen (inklusive liquide Mittel)"
  wurde „Aktiva (ohne aktive Rechnungsabgrenzung)".

Bei den letzten beiden bleiben die Werte über den Wechsel hinweg auf den Cent
gleich: umformuliert, nicht umgerechnet. Ohne den Vergleich hätte man sie
zusammen mit der Personalintensität als Brüche behandelt — drei Reihen
zerschnitten, wo eine es verdient.

### Drei Proben, und die dritte ist die schärfste

1. **`kennzahlen_gegen_bilanz`** — Anlagenintensität, Infrastrukturquote und
   Eigenkapitalquote II lassen sich aus `council_bilanz` nachrechnen. 87
   Nachrechnungen über 2016–2024, keine Abweichung über der gedruckten
   Genauigkeit.
2. **`kennzahlen_ueberlappung`** — die 240 doppelten Zellen (s. o.).
3. **`kennzahlen_vermoegensprobe`** — „Vermögen je Einwohner\*in" mal „Anzahl
   der Einwohnenden", zwei Zeilen derselben Tabelle, ergibt die Bilanzsumme
   ohne aktive Rechnungsabgrenzung. Vier unabhängige Größen, 20 Jahrgang-
   Bericht-Paare, Abweichung unter einem Tausendstel Prozent. Die Toleranz ist
   gerechnet: Ein je-Kopf-Wert mit zwei Nachkommastellen darf um einen halben
   Cent danebenliegen, mal 176.068 Einwohnenden also um rund 880 €.

### Die Genauigkeit reist mit

`stellen` hält fest, wie viele Nachkommastellen **gedruckt** waren: 2019 stand
„48%", ab 2021 „53,15%". Ein stumpfer Vergleich meldete deshalb reihenweise
Abweichungen, die nur Rundung sind; die Toleranz der Überlappungsprobe kommt
aus der gröberen der beiden Angaben. Auf der Seite hängt daran auch die
Vorjahresdifferenz: Von 54,62 % auf 50,11 % sind 4,51 **Prozentpunkte**, nicht
4,51 % — die Grafik hat dafür ein eigenes Format (`differenzFormat`).

### Zwei Berichte ohne Tabelle

2017 und 2018 zeigen dieselben Kennzahlen nur als Diagramm: Die Werte stehen
als Balkenbeschriftung zwischen den Achsenwerten, und der „Ermittlung:"-Satz
steht dort *vor* seinem Diagramm statt darunter. Das wäre geraten — und es
wäre umsonst, denn die Jahrgänge 2015–2018 stehen als Tabelle im Bericht 2019.

### Betrieb

Die Berichte 2017–2021 lagen bis zum 18.08.2026 **ohne Volltext** im Bestand,
und zwar aus einem Ein-Buchstaben-Grund: Das Label-Muster der Finanzquellen
kannte `%chlussbericht%` (für die Schlussberichte des Rechnungsprüfungsamts),
und „Rechenschaftsbericht" endet auf *-chaftsbericht*. Die Berichte ab 2022
rutschten nur durch, weil ihr Titel zusätzlich „Jahresabschluss" enthält. Die
Quelle `kennzahlen` bringt das Muster jetzt selbst mit; ausgeschlossen werden
die Stiftungs-Berichte **namentlich** und nicht über „Stiftung", denn der
städtische Bericht heißt selbst „… der Kernverwaltung und ihrer nicht
rechtsfähigen Stiftungen".

## Der Haushalt neben dem Haushalt: die Wirtschaftspläne

Der Kernhaushalt ist nicht alles, was der Rat beschließt. Daneben stehen die
**Wirtschaftspläne** der Eigenbetriebe und Gesellschaften — eigene Erfolgs- und
Vermögenspläne, in derselben Sitzung entschieden. Der größte ist der
Eigenbetrieb Gebäudewirtschaft und Hochbau (EGH): 2026 rund 82,8 Mio. € Erträge
und Aufwendungen, dazu ein Vermögensplan über 51,1 Mio. €. Er baut und saniert
die städtischen Gebäude — also auch die Schulen, die im Investitionsprogramm des
Kernhaushalts ausdrücklich fehlen.

Was `/haushalt/konzern` und `/haushalt/beteiligungen` von diesen Betrieben
zeigen, ist ihr **Ist**, aus Gesamtabschluss und Beteiligungsbericht, und beides
hinkt rund zwei Jahre hinterher. Was sie für das laufende Jahr vorhaben, stand
bis 08/2026 nirgends.

### Die einzige Schicht, deren Quelle eine Vorlage ist

Nicht eine Anlage, sondern der **Beschlussvorschlag der Ratsvorlage**:

```
im Erfolgsplan

mit Erträgen von 82.815.150 Euro
mit Aufwendungen von 82.824.771 Euro
mit steuerlichen Aufwendungen von                6.000 Euro
und einem Jahresergebnis von              -    15.621 Euro

und im Vermögensplan

mit Einzahlungen und Auszahlungen von je 51.134.100 Euro
und Verpflichtungsermächtigungen von 104.980.000 Euro
```

Das ist der Text, über den abgestimmt wird — keine Zusammenfassung und keine
Anlage, die später ausgetauscht werden könnte. `council_vorlagen` führt ihn
längst als Volltext; es brauchte nur niemand.

### Zwei Proben, und die erste steht im Text

1. **`wirtschaftsplan_erfolgsplan`** — *Erträge − Aufwendungen − steuerliche
   Aufwendungen = Jahresergebnis*. Vier Zahlen, von denen die vierte aus den
   ersten dreien folgt. Über **alle acht Jahrgänge** (2019–2026) geht sie auf
   den **Cent** auf. Die Toleranz steht deshalb auf 0,005 € und nicht auf 1 €:
   Die Quelle führt volle Euro, eine Ein-Euro-Toleranz ließe genau den einen
   Fehler durch, den die Probe sehen könnte (dieselbe Überlegung wie bei
   `investitionen.TOLERANZ_EUR`).
2. **`wirtschaftsplan_jahr`** — Das Haushaltsjahr steht im Fließtext *und* im
   Titel der Vorlage, beide müssen dasselbe sagen. Das ist die wichtigere
   Probe für den wahrscheinlicheren Fehler: Eine Vorlage **vom Oktober 2025**
   beschließt das Jahr **2026**. Wer das Jahr aus dem Vorlagen-Datum nähme,
   verschöbe die ganze Reihe um eins.

### Nur der EGH — und das ist der Befund

Von **46** Wirtschaftsplan-Vorlagen im Bestand (2018–2026) tragen **acht**
diesen Block, alle acht vom EGH. Die übrigen 38 nennen im Beschlusstext keine
Zahl:

| Betrieb | Vorlagen | im Beschlusstext |
|---|---|---|
| Gebäudewirtschaft und Hochbau | 8 | **vollständige Eckwerte** |
| Bäderbetrieb (BBO) | 12 | „wird in der als Anlage beigefügten Fassung zugestimmt" |
| Bäderbetriebsgesellschaft (BBGO) | 10 | eine Zahl (Jahresfehlbetrag), ohne Gegenrechnung |
| Abfallwirtschaftsbetrieb | 8 | Zustimmung zur Anlage |
| Stadion | 5 | eine Zahl (maximaler Fehlbetrag) |
| Eigenbetrieb Hafen | 2 | Zustimmung zur Anlage |

Gelesen wird deshalb **nur, was sich prüfen lässt**. Bei der BBGO stünde eine
Zahl im Fließtext („Jahresfehlbetrag von −10.128.335 Euro") — sie zu übernehmen
hieße, eine Angabe ohne Gegenprobe in dieselbe Tabelle zu schreiben, in der
daneben lauter cent-genau geprüfte stehen. Die Herkunft sagte „ungeprüft", und
auf der Seite sähe die Zahl aus wie der Rest. Was fehlt, fehlt gezählt
(`wirtschaftsplan.ohne_eckwerte`, der Ingest-Lauf listet es nach Betrieb).

:::caution[Nicht mit dem Kernhaushalt addieren]
Der EGH vermietet der Stadt ihre eigenen Gebäude; seine Erträge sind zu großen
Teilen Aufwand des Kernhaushalts. Wer beide Summen nebeneinanderstellt und
addiert, zählt dasselbe Geld zweimal. Genau diese Verflechtung rechnet der
**Gesamtabschluss** heraus — das ist seine Aufgabe, und deshalb ersetzt diese
Schicht ihn nicht, sondern steht daneben. `wirtschaftsplan.ABGRENZUNG` reist
mit den Daten mit, damit der Satz nicht nur im Frontend steht.
:::

Und es ist der **Verwaltungsentwurf**, nicht der Beschluss — der Text sagt das
selbst („in der Fassung des Verwaltungsentwurfes vom 01.10.2025"). Das Datum
wird mitgelesen und gehört an jede Anzeige, dieselbe Vorsicht wie beim
Gesamtergebnishaushalt. Der Jahrgang 2024 schreibt „des **I.**
Verwaltungsentwurfes"; die Ordnungszahl zählt die Fassung und wird zugelassen,
aber nicht ausgewertet.

### Welche Dokumente geprüft wurden — und was daraus wurde

Damit im nächsten Oktober niemand bei null anfängt: Das hier ist der Befund je
Betrieb, mit Stand 20.08.2026. Die Spalte „Anlage" nennt die
`council_anlagen.document_id` — der Anker, der Label- und URL-Wechsel
überlebt.

| Betrieb | Vorlagen | Eckwerte im Beschlusstext | Anlage lesbar? |
|---|---|---|---|
| Gebäudewirtschaft und Hochbau (EGH) | 8 (2019–2026) | **ja, alle acht** — eingelesen | nicht nötig |
| Abfallwirtschaftsbetrieb (AWB) | 8 | nein | **teils** — s. u. |
| Bäderbetrieb (BBO) | 12 | nein | ja (Text vorhanden) |
| Bäderbetriebsgesellschaft (BBGO) | 10 | nein | ja |
| Stadion / Stadionplanungsges. | 5 | nein | ja |
| Eigenbetrieb Hafen | 2 (2019–2020) | nein — aber die **Kernzahl** steht drin | ja, und sie belegt sie |

**Der AWB im Detail** (geprüft an den heruntergeladenen PDFs):

| Jahrgang | Anlage | Befund |
|---|---|---|
| 2019 | 193959 | **Scan** — keine Textebene |
| 2020 | 208461 | **Scan** |
| 2021 | 224533 | **Scan** |
| 2023 | 252313 | Text, Layout A (Posten je Bereich) |
| 2024 | 269051 | Text, Layout A |
| 2025 | 283481 | Text, Layout A |
| 2025 (Anpassung) | 292139 | Text, Layout A |
| 2026 | 299038 | Text, **Layout B** (Positionsnummern, „Summe Erträge") |

Zwei Layouts, drei Scans — der AWB ist also nicht der einfache Fall, als der er
zuerst aussah. Layout A gliedert jeden Posten nach den vier Betriebszweigen
(Straßenreinigung · Abfallsammlung · Abfallbehandlungsanlagen · Werkstatt) und
setzt darunter eine unbeschriftete Summenzeile; die vier ergeben sie exakt
(5.153.245 + 15.492.551 + 680.984 = 21.326.780). Layout B nummeriert die Posten
nach § 275 HGB und schreibt „Summe Erträge" aus, rundet dabei aber je Position:
23.824.312 + 17.812 + 378.352 = 24.220.4**76** gegen ausgewiesene 24.220.4**75**.
Eine Toleranz von 2 € ist hier Pflicht, cent-genau wie beim EGH geht nicht.

:::note[Scans werden nicht vergessen — sie tragen eine Marke]
Ein PDF ohne Textebene ist im Bestand **nicht** dasselbe wie ein ungelesenes:
`backfill_anlagen_texte.py` setzt `council_anlagen.status = 'empty'`, sobald
ein Dokument weniger als 200 Zeichen hergibt (`MIN_TEXT`). 231 Anlagen tragen
diese Marke bereits.

Diese Marke ist die Arbeitsliste, und seit dem 20.08.2026 arbeitet sie jemand
ab: `scripts/backfill_anlagen_ocr.py` schickt jede Seite als Bild an ein
Sehmodell (`council/ocr.py`). Damit die Schicht überhaupt in der Liste landet,
ist sie in `finanzquellen.QUELLEN` mit einer `erkennung` eingetragen, obwohl
der Cron sie gar nicht liest: Beide Backfills ziehen ihre Label-Muster aus
genau dieser Registry (`finanz_muster()`).
:::

### OCR: gelesen ist gelesen — maskiert wird an der Index-Grenze

Der OCR-Lauf schreibt `status = 'ok'` und vermerkt in `ocr_modell`, welches
Sehmodell den Text gelesen hat. Ein gescannter Wirtschaftsplan ist damit so
durchsuchbar wie ein getippter.

:::caution[Ein Umweg, der erst falsch war]
Vom 20.08.2026 bis zum selben Abend schrieb der Lauf `status = 'ocr'` und hielt
damit **jeden** gelesenen Scan aus der Suche. Das war der falsche Ort für die
Sperre: Sie traf die *Herkunft* des Textes statt dessen, was darin steht — und
sperrte den AWB-Wirtschaftsplan, den RPA-Schlussbericht und das
Investitionsprogramm gleich mit aus, auf denen keine Privatperson steht.

Der Wert existiert nicht mehr; eine Migration in `store.py` hebt Altstände beim
Öffnen der Datenbank auf `'ok'`. Gehoben und nicht neu gelesen: Der Text war in
Ordnung, nur sein Status war es nicht.
:::

**Zwei Stufen** (`council/kontaktdaten.py`), und der Unterschied ist wichtig:

| | was | wo |
|---|---|---|
| `entfernen()` | **IBAN, BIC, vollständige Anschrift** | schon beim **Speichern** — sie kommen gar nicht erst in den Bestand |
| `maskieren()` | zusätzlich **Telefon, Fax, E-Mail** | an der **Index-Grenze** — im Bestand bleiben sie |

`entfernen()` ist **ohne erneutes Laden des PDF unumkehrbar**. Deshalb steht
dort nur, was nachweislich kein Parser braucht: Eine Kontonummer ist nie eine
Haushaltszahl, und eine vollständige Postanschrift auch nicht — der Straßenname
allein bleibt ja stehen, und der ist das Einzige, was das Investitionsprogramm
daraus braucht.

Telefon und E-Mail bleiben bewusst im Bestand: Eine Rufnummer der Verwaltung
kann der Anker sein, an dem jemand eine Fundstelle im PDF wiederfindet. Am
Index fallen sie trotzdem — `store.anlagen_missing_embeddings()` und
`store.rebuild_fts()` schicken ihren Text durch `maskieren()`.

`scripts/bereinige_kontaktdaten.py` holt nach, was vor dem 20.08.2026
hereinkam: **81 IBAN, 42 BIC und 1.453 Anschriften** in 607 Dokumenten. Der
Lauf ist idempotent und hängt im Ops-Workflow.

**Das ist kein OCR-Thema.** Gemessen am Prod-Stand vom 16.08.2026 tragen **606
Anlagen** Kontaktdaten — 1.382 Anschriften, 1.024 Telefon- und Faxnummern, 533
E-Mail-Adressen, 81 IBAN, 42 BIC — und sie standen längst im Suchindex, ganz
ohne Texterkennung. Der Textverlust durch die Maskierung liegt bei **0,22 %**.

**Was bewusst NICHT maskiert wird:**

- **Namen.** Der Bestand nennt 1.271 Ratsmitglieder namentlich, Protokolle
  führen jede Wortmeldung mit Namen, Vorlagen nennen Amtsleitungen. Namen
  herauszunehmen hieße, das halbe System unbrauchbar zu machen.
- **Straßennamen ohne Postleitzahl dahinter.** Das ist die gefährlichste Falle
  dieses Moduls: „Ausbau Bümmersteder Tredde", „Sanierung Butjadinger Straße
  61" — der halbe Investitionsbereich besteht aus Straßennamen. Erkannt wird
  eine Anschrift deshalb nur **am Stück** (Straße, Hausnummer, Postleitzahl,
  Ort) oder als **eigene Zeile** (`26122 Oldenburg`).

Ein erstes Muster nahm jede fünfstellige Zahl vor einem großgeschriebenen Wort
für eine Postleitzahl — und traf damit „Produkt **11101
Verwaltungssteuerung**". Der eigene Test hat das gefunden, nicht der Betrieb.

**Drei Entscheidungen, die vorher gemessen wurden** (an zwei echten AWB-Seiten,
300 dpi gerade und 200 dpi quer, bewertet gegen die Rechenprobe dieses
Bereichs):

1. **Wir rastern selbst, statt das PDF hochzuladen.** OpenRouters
   `file-parser`-Plugin läuft über OpenRouters *eigenen* Mistral-Schlüssel —
   unser `provider`-Block aus `kern.llm` steuert nur die Modell-Endpunkte. Der
   OCR-Schritt liefe damit still an `NWZ_OPENROUTER_ROUTING` vorbei, also an
   der Anbieter-Sperre und der Zero-Data-Retention-Pflicht.
2. **Wir brauchen dafür keinen Renderer.** Jede Seite dieser Scans ist genau
   *ein* eingebettetes JPEG, das `pypdf` unverändert herausgibt — keine neue
   Abhängigkeit im Deployment. Nur Vektorseiten (der Schlussbericht des
   Rechnungsprüfungsamts) bräuchten einen; der ist optional, und fehlt er,
   bleibt die Seite ungelesen statt falsch gelesen.
3. **Die Lage-Metadaten lügen.** Von drei AWB-Jahrgängen tragen zwei `/Rotate`
   passend zum Inhalt, einer nicht. Wir folgen ihm gar nicht — auf der um 90°
   liegenden Seite gingen alle 24 Rechenproben auf. Die Modelle kommen mit der
   Drehung zurecht, unsere Metadaten nicht.

**Die Lücke, die dabei aufging — und seit dem 20.08. geschlossen ist.** Die
Spaltenprobe ist **skaleninvariant**: Steht `in TEUR` über der Tabelle und liest
jemand die Angabe nicht mit, liegt die ganze Spalte um den Faktor 1.000 daneben
— und `Erträge − Aufwendungen = Ergebnis` geht trotzdem auf, weil sich der
Faktor auf beiden Seiten wegkürzt. `TOLERANZ_EUR` kann das prinzipiell nicht
sehen.

`spaltenproben()` bricht deshalb ab, wenn `einheit_an_der_kopfzeile()` eine
Angabe findet, die nicht volle Euro meint. **Umgerechnet wird bewusst nicht:**
Eine Tabelle in TEUR gibt es im Bestand bisher nicht, und einen Umrechner zu
bauen, den niemand an einem echten Dokument geprüft hat, hieße raten. Wer den
ersten solchen Jahrgang findet, trägt die Umrechnung ein und prüft sie an ihm.

Das Fenster ist eng — vier Zeilen über der Kopfzeile —, und das ist der Punkt:
Jeder Vorbericht redet irgendwo von „Mio. €" (beim AWB rund 140 Zeilen früher
von „ca. 20,3 Mio. €"). Wer im ganzen Dokument sucht, kann keine einzige
Tabelle mehr lesen.

Ebenso gilt: Vollständigkeit ist keine Richtigkeit — fehlt eine Zeile, prüft
die Probe *weniger* und geht auf. Deshalb zählt `ocr.Lesung` mit, wie viele
Seiten wirklich gelesen wurden.

**Was der erste Lauf ergab** (Dokument 193959, AWB-Wirtschaftsplan 2019, sechs
Seiten): 62 von 66 Spaltenproben gehen **cent-genau** auf, vier sind um exakt
1 € daneben. Ein Zweitleser (Claude Sonnet 4.6) las dieselbe Seite unabhängig
und lieferte **zeichengleiche** Zahlen — der Riss steht also im Dokument der
Stadt, nicht im OCR. Genau der Fall, für den `TOLERANZ_EUR = 2.0` kalibriert
wurde.

**Die drei fehlenden Jahrgänge lesen sich ohne jede Parser-Erweiterung.**
Kurz sah es anders aus: Ein erster Lauf über sechs Seiten fand keine
Summenzeile, und der Schluss lag nahe, das Layout 2019–2021 sei ein anderes.
Er war falsch. `Gesamtertrag` / `Gesamtaufwendungen` / `Gesamtergebnis` stehen
dort sehr wohl — nur auf **Seite fünf** der Tabelle, hinter den elf nach Sparten
gegliederten Positionsblöcken. Der Befund war ein Artefakt des abgeschnittenen
Textes, kein Befund über das Dokument. Vollständig gelesen (36 Seiten je
Jahrgang) gehen alle drei durch, je **6 von 6 Spalten**:

| Jahrgang | Vorlage | Erträge | Aufwendungen | Ergebnis |
|---|---|---|---|---|
| 2019 | 18/0691 | 20.280.001 € | 19.989.470 € | 290.531 € |
| 2020 | 19/0778 | 20.747.250 € | 20.317.670 € | 429.580 € |
| 2021 | 20/0636 | 21.254.400 € | 20.807.750 € | 446.650 € |

Eine Falle trägt das alte Layout allerdings, dieselbe wie Layout B mit anderem
Wort: Unter dem `Gesamtergebnis` (2019: 290.531 €) steht weiter unten noch ein
`Jahresergebnis` (93.031 €). Die Differenz ist die Eigenkapitalverzinsung, die
der Betrieb an den städtischen Haushalt abführt. Wer die Zeile nimmt, die am
besten klingt, speichert die falsche.

## Die Gebührenbedarfsberechnung: was im Portemonnaie ankommt

Von allen Zahlen des Haushalts landet keine so direkt bei den Leuten wie die
Abfall- und Straßenreinigungsgebühr. Wie sie zustande kommt, legt der
Abfallwirtschaftsbetrieb jedes Jahr als Anlage zur Ratsvorlage vor — und diese
Anlage ist das **am besten prüfbare Dokument des ganzen Bestands**
(`council/gebuehren.py`, `scripts/ingest_gebuehren.py`,
`council_gebuehren`).

Drei Bereiche je Jahrgang, jeder mit eigener Bezugsgröße:

| Anlage | Bereich | Gebühr bemessen nach |
|---|---|---|
| 1 | Abfallbehandlungsanlagen | Tonne (Mg) angelieferter Abfall |
| 2 | Abfallsammlung | Behältervolumen in Litern |
| 3 | Straßenreinigung | Meter Quadratwurzel gebührenpflichtiger Fläche |

**Zwei Proben je Block, beide aus dem Dokument selbst:**

```
Kostenkalkulation 2025                    11.661.361 €
  − von Dritten erstattet                 −3.668.314 €
  − Erlöse nach § 2                           −5.000 €
  − aus der Nachsorge-Rückstellung          −240.000 €
  − Über-/Unterdeckung aus Vorjahren        −361.777 €
= durch Gebühren zu decken                 7.386.270 €   ← Kaskade
  ÷ 52.845 Mg
= Gebühr je Mg                               139,772 €   ← Division
```

Die Kaskade rechnet nach, was die Zwischenzeilen des Dokuments behaupten. Die
Division ist davon **unabhängig**: Menge und Gebühr stehen im
Gebührenermittlungs-Block, nicht in der Kaskade. Über alle zwölf geprüften
Blöcke gehen beide auf — neunmal cent-genau, zweimal um genau 1 € (dieselbe
Rundungs-Signatur wie beim Erfolgsplan, `TOLERANZ_EUR = 2.0`).

**Was der Bestand zeigt:**

| Jahrgang | Abfallbehandlung | Straßenreinigung |
|---|---|---|
| 2023 | 123,284 €/Mg | 3,660 €/m |
| 2024 | 134,709 €/Mg | 3,665 €/m |
| 2025 | 139,772 €/Mg | 3,744 €/m |
| 2026 | 151,214 €/Mg | 4,039 €/m |

**Vier Eigenheiten, die der Parser kennen muss:**

1. **Zahlen zerreißen an Leerzeichen.** `-295. 000 €` (2026) — dort *ist*
   entscheidbar, dass die Zahl weitergeht: davor eine Ziffer und ein Punkt,
   dahinter genau drei Ziffern. Bei `7 71.000` (Straßenreinigung 2026) ist es
   das **nicht**. Die Bezugsmenge wird deshalb nicht geraten, sondern **an der
   Division erkannt**: Von allen Kandidaten gilt die, die zusammen mit den zu
   deckenden Kosten die gedruckte Gebühr ergibt.
2. **Der Jahrgang 2024 legt erst alle Beträge ab und danach erst ihre
   Beschriftungen.** Ein Muster, das die Zahl neben ihrem Namen sucht, findet
   dort nichts. Die Zuordnung kommt aus der Reihenfolge — und gilt nur, weil
   sie die Kaskade erfüllt.
3. **Die errechnete Gebühr hat drei Nachkommastellen, der Vorschlag an den Rat
   zwei** (134,709 gegen 134,70). Wer den Vorschlag nimmt, speichert eine Zahl,
   die die Division nicht erfüllt — geprüft wird deshalb gegen die
   dreistellige, und beide werden gespeichert.
4. **Die Abfallsammlung hat gar keine einzelne Gebühr.** Sie erhebt eine
   Grundgebühr **und** eine Gebühr je Liter Behältervolumen; eine Division
   „Kosten ÷ Menge" gibt es dort nicht. Der Jahrgang wird trotzdem gespeichert
   — seine Kaskade ist geprüft —, aber `gebuehr` und `bezugsmenge` bleiben
   leer, und `proben` sagt, dass nur eine der beiden Proben lief.

**Was fehlt:** der Jahrgang **2020** (nur als Scan; `backfill_anlagen_ocr.py`
macht ihn lesbar) und die **Gebührensätze selbst**. Anlage 4 jedes Dokuments
führt sie als Zeitreihe über zwölf Jahre und zwölf Gebührenarten —
Grundgebühr, Litergebühr, Sperrmüllkarte, Grüngutanlieferung —, jede Zeile mit
einer eigenen Prozentprobe (`139,70 → 151,21 = +8,24 %`, gedruckt +8,24 %).
Das ist eine eigene Schicht, die auf dieser hier aufbaut.

## Die Haushaltssatzung: der Rahmen um den Plan

Der Haushaltsplan sagt, wofür das Geld ausgegeben werden soll. Die
**Haushaltssatzung** sagt, in welchem Rahmen — auf drei Seiten, je Jahrgang,
und bis zum 20.08.2026 las sie niemand. Sie füllt `council_haushaltssatzung`
(`council/haushaltssatzung.py`, `scripts/ingest_haushaltssatzung.py`).

| § | Was dort steht | Warum es fehlte |
|---|---|---|
| **§ 1.1** | Ergebnishaushalt: ordentliche und außerordentliche Erträge/Aufwendungen | teilweise über `council_ergebnishaushalt` da |
| **§ 1.2** | Finanzhaushalt: sechs Beträge plus zwei Summen | der Bereich las daraus **nur die Investitionen** |
| **§ 2** | Kredite für Investitionen | **stand nirgends** |
| **§ 3** | Verpflichtungsermächtigungen | **stand nirgends** |
| **§ 4** | Höchstbetrag für Liquiditätskredite — der Dispo der Stadt | **stand nirgends** |
| **§ 5** | Hebesätze | über Tabelle 1105 da, hier als Gegenprobe |

:::caution[Was hier steht, ist nicht beschlossen]
Alle neun Satzungen im Ratsinformationssystem tragen auf dem Deckblatt
**„Verwaltungsentwurf"**, und ihr Text nennt als Sitzungsdatum „xx.xx.20xx" —
eine Vorlage, kein Beschluss. Die beschlossene Fassung erscheint im **Amtsblatt**,
nicht im Ratsinformationssystem.

Jede Zeile trägt deshalb `fassung='entwurf'`, und die Herkunft schreibt es in
den *Stand*, nicht in eine Fußnote. Was der Rat daraus macht, steht auf
`/haushalt/mitreden#streit`.

Der Jahrgang 2026 ist die einzige Satzung mit einem echten Datum (15.12.2025) —
aber auch ihr Deckblatt sagt „Verwaltungsentwurf". Das Datum ist die *geplante*
Sitzung, nicht ihr Ergebnis. Ein Parser, der es als Beleg nähme, machte aus
einem Vorschlag einen Beschluss; deshalb heißt der Wert ohne Entwurfs-Vermerk
`unbekannt` und nie `beschlossen`.
:::

**Die Satzung prüft sich selbst.** Unter § 1 stehen die drei Einzahlungs- und
die drei Auszahlungszeilen des Finanzhaushalts einzeln — und darunter noch
einmal ihre Summe („Nachrichtlich: Gesamtbetrag der Einzahlungen des
Finanzhaushaltes …"). Über alle sieben eingelesenen Jahrgänge geht diese Probe
**cent-genau** auf. Sie ist der Grund, dass diese Schicht ohne Zweitquelle
auskommt, und `TOLERANZ_EUR` steht deshalb auf 0,005 € und nicht höher: Die
Satzung führt volle Euro, eine Toleranz wäre hier kein Schutz, sondern ein
blinder Fleck.

**Was der Bestand zeigt.** Die Kreditermächtigung lautet in **jedem** gelesenen
Jahrgang „werden nicht veranschlagt" — die Stadt nimmt keine
Investitionskredite auf. Der Dispo dagegen wächst: 60 Mio. € (2019/2020) → 95
Mio. (2021) → 60 Mio. (2023) → 100 Mio. (ab 2024).

**Drei Fallen:**

1. **`EUR` statt `Euro`.** Die Jahrgänge 2019 und 2020 schreiben die Einheit
   durchgängig aus. Dieselbe Falle wie beim Eigenbetrieb Hafen, und genauso
   lautlos: Ein Muster, das nur „Euro" kennt, findet dort nichts und meldet
   keinen Fehler, sondern eine fehlende Zeile.
2. **Der Nachtrag trägt dasselbe Wort im Label.** Die
   Nachtragshaushaltssatzung 2020 führt eine ganz andere Tabelle (*bisher /
   erhöht um / vermindert um / Gesamtbetrag*) — und in ihrem Textextrakt steht
   eine Zahl mit einem Leerzeichen mitten drin (`609.717 .785`). Sie wird
   bewusst **nicht** gelesen; der Parser weist sie am Wort ab, die
   `erkennung` schließt sie zusätzlich aus.
3. **Ab 2025 fehlt die Grundsteuer in § 5.** Die Satzung nennt nur noch die
   Gewerbesteuer und verweist für die Grundsteuer auf eine eigene Satzung. Die
   beiden Felder sind dann leer — das ist die Auskunft, keine Lücke im
   Einlesen.

**Was fehlt:** der Jahrgang **2022** (keine Satzung im Bestand) und die
Nachträge. 2021 liegt doppelt (Anlagen 229865 und 230043, gleicher Inhalt); der
Primärschlüssel `(jahr, nachtrag)` fängt das.

### Der zweite Weg: der Erfolgsplan aus der Anlage

Seit 08/2026 liest der Bereich auch die Betriebe, die im Beschlusstext **keine**
Zahl nennen — aus dem Erfolgsplan ihrer Anlage
(`council/wirtschaftsplan_tabelle.py`). Den Anfang macht der
Abfallwirtschaftsbetrieb, und zwar aus einem Grund: Aus seinem Erfolgsplan
werden die **Abfallgebühren** kalkuliert. Von allen Betrieben ist er der, dessen
Zahlen jeder Haushalt direkt bezahlt.

**Zwei Layouts, dieselbe Aussage.** Der AWB hat zwischen 2025 und 2026
gewechselt:

| | Layout A (2023–2025) | Layout B (ab 2026) |
|---|---|---|
| Erträge | `Gesamtertrag` | `Summe Erträge` |
| Aufwendungen | `Gesamtaufwendungen` | `Summe Aufwendungen` |
| Ergebnis | `Gesamtergebnis` | `11. Ergebnis nach Steuern` |

Ein Layout-Schalter ist deshalb nicht nötig: Das Vokabular führt beide
Schreibweisen, und welche gegriffen hat, hält die Herkunft fest. Beide Male
gilt *Erträge − Aufwendungen = Ergebnis*, und beide Male steht das Ergebnis
unmittelbar unter seinen Summanden.

:::caution[Nicht die Zeile nehmen, die „Jahresüberschuss" heißt]
In Layout B folgen darunter noch „12. Sonstige Steuern" und „13.
Jahresüberschuss"; in Layout A stecken die sonstigen Steuern schon in den
Aufwendungen. Gelesen wird deshalb die Zeile **direkt unter den beiden
Summen** — nicht die mit dem passendsten Namen. Nur so bleibt
*Erträge − Aufwendungen − Steuern = Ergebnis* in **jeder** Zeile der Tabelle
wahr, egal ob sie aus einem Beschlusstext oder aus einer Anlage stammt.
:::

**Drei Proben, alle aus dem Dokument:**

1. `wirtschaftsplan_spalten` — die Rechnung gilt in **jeder** Spalte, nicht nur
   in der gespeicherten. Ein Dokument führt sechs (ein Ist- und fünf
   Planjahre); über die fünf lesbaren Jahrgänge sind das 30 Proben, von denen
   29 auf den Cent aufgehen und eine um 1 € daneben liegt. Die Quelle rundet je
   Position, deshalb steht die Toleranz auf 2 € statt auf 0,005 € wie beim
   Beschlusstext.
2. `wirtschaftsplan_prosa` — Unter der Tabelle steht ein Satz, der die beiden
   Summen des Planjahres wiederholt („Der Erfolgsplan 2025 umfasst … Erträge in
   Höhe von insgesamt 25.197.796 € und … Aufwendungen … 24.570.285 €"). Zwei
   unabhängig gesetzte Stellen desselben Dokuments. **Weich**: Fehlt der Satz,
   fällt der Jahrgang nicht — widerspricht er, schon.
3. `wirtschaftsplan_bereiche` — Die Ertragszeile kommt **fünfmal** vor: einmal
   für alle Bereiche und je einmal in den vier Anlagen (Abfallbehandlung,
   Abfallsammlung, Straßenreinigung, Werkstatt). Die vier ergeben die erste.
   Damit ist „die erste Zeile ist die Gesamtrechnung" gemessen und nicht
   angenommen — ein versehentlich gegriffener Betriebszweig wäre fünf- bis
   zwölfmal kleiner und fiele sofort durch.

**Welche Spalte der Plan ist**, entscheidet die Kopfzeile: gesucht wird das
Haushaltsjahr der Vorlage, nicht eine Position. Die Spaltenzahl schwankt, und
2026 schreibt „Ergebnis 2024" statt „Ist 2024". Findet sich das Jahr nicht,
wird nichts gespeichert. Die Finanzplanungsjahre werden geprüft, aber **nicht**
gespeichert — dieselbe Begründung wie beim Gesamtergebnishaushalt.

:::note[Ein Widerspruch im Jahrgang 2025 — gemessen, nicht geglättet]
Im Wirtschaftsplan 2025 ergeben die vier Betriebszweige in der **Planspalte**
447.001 € mehr als die ausgewiesene Gesamtzeile (1,77 %). In allen anderen
Spalten und allen anderen Jahrgängen stimmt es auf ±1 €.

Der Jahrgang bleibt trotzdem im Bestand, und das ist kein Nachlassen: Die
gespeicherte Zahl ist durch **zwei** unabhängige Proben gedeckt — die
Spaltenrechnung und den Prosa-Satz, der exakt dieselben 25.197.796 € nennt.
Dieselbe Lage wie 2022 bei den Schulden: Die Summe trägt, die Aufteilung nicht,
und dann fällt die Aufteilung und nicht die Summe. Der Abstand wird gemessen
und reist in der Herkunft mit.
:::

**Die drei AWB-Scans sind seit dem 20.08.2026 gelesen.** 2019 bis 2021 lagen
nur als Bild vor; `scripts/backfill_anlagen_ocr.py` hat sie lesbar gemacht (je
36 Seiten, vollständig), und sie gehen **ohne jede Parser-Erweiterung** durch —
je 6 von 6 Spalten, größte Abweichung 0,00 €. Ihre Herkunft sagt es dazu:
*„Erfolgsplan der Anlage (per OCR gelesen)"*, mit dem Namen des Modells.

Für Bäderbetrieb, Bäderbetriebsgesellschaft und Stadion ist weiterhin **kein
Vokabular** hinterlegt: Ein geratenes fände irgendeine Zeile, und ihre Zahlen
stünden dann unter einem Namen, den nie jemand nachgeschlagen hat. Sie kommen
über den dritten Weg.

### Der dritte Weg: die Kernzahl, belegt durch zwei Dokumente

Für Bäderbetriebsgesellschaft, Stadion, Bäderbetrieb und den Hafen trägt
keiner der beiden Wege — und der Grund ist der lehrreichste Befund dieser
Schicht.

**Der Eigenbetrieb Hafen sagt „Verlust".** Er ist der einzige Betrieb, der
weder „Fehlbetrag" noch „Überschuss" schreibt: *„Für das Wirtschaftsjahr 2019
ist … ein Verlust von 273.950 EUR ermittelt worden"* — und die Einheit heißt
dort `EUR`, nicht `€` oder `Euro`. Beides kannte das Muster bis zum 20.08.2026
nicht, und das Ausbleiben war lautlos: Die Vorlage wurde schlicht nie erkannt,
es gab nie einen Fehler zu sehen. Seine beiden Jahrgänge (2019 und 2020) sind
jetzt drin, **beide zweifach belegt** — dieselbe Zahl steht im Beschlusstext
und in der Anlage.

Zwei Jahrgänge sind dabei **keine Lücke, sondern der ganze Bestand**: Der
Eigenbetrieb wurde aufgelöst (Vorlage 20/0322 Rechtsformwechsel, 20/0809
Auflösungssatzung). Es gibt keinen dritten Wirtschaftsplan, den man vermissen
könnte.

**Gleiches Vokabular, andere Bedeutung.** Ihre Erfolgspläne führen dieselben
Zeilennamen wie der Abfallwirtschaftsbetrieb: `Gesamtleistung`,
`Gesamtkosten`, `Gesamtergebnis`. Die Probe *Gesamtleistung − Gesamtkosten =
Gesamtergebnis* geht aber auf:

| Betrieb | Spalten, in denen die Rechnung aufgeht |
|---|---|
| Stadion | 5 von 5 |
| Bäderbetrieb | **0** von 11 · 0 von 6 |
| Bäderbetriebsgesellschaft | **1** von 24 · 2 von 15 |

Bei den beiden Bäder-Gesellschaften stehen zwischen `Gesamtkosten` und
`Gesamtergebnis` noch Abschreibungen, Zinsen und neutrale Posten —
`Gesamtkosten` ist dort **nicht** der Gesamtaufwand. Ein Parser, der dem
Zeilennamen glaubt, hätte plausible und falsche Zahlen geliefert. Genau dafür
gibt es Rechenproben.

**Was stattdessen trägt**, ist der Beschlusstext der Vorlage:

> …wird in der anliegenden Fassung mit einem für die Gesellschaft
> ausgewiesenen **Jahresfehlbetrag von −10.128.335 Euro** beschlossen.

Und dieselbe Zahl steht in der Anlage. Zwei getrennte Dokumente, unabhängig
gesetzt — die einzige Probe des Bereichs, die nicht davon abhängt, eine
Tabellenzeile richtig zu deuten (`wirtschaftsplan_kernzahl`).

:::caution[Das Wort trägt das Vorzeichen, nicht die Ziffernfolge]
„maximalen Fehlbetrag in Höhe von **651.500 Euro**" ist **minus** 651.500 €.
Mal steht das Minus zusätzlich davor („Jahresfehlbetrag von −10.128.335
Euro"), mal nicht. Wer beides gleich liest, macht aus dem größten Verlust der
Stadtgesellschaften einen Gewinn. Ein „Fehlbetrag" kann deshalb nie positiv
gespeichert werden, ein „Überschuss" nie negativ — und ein Dokument, das beides
gegeneinander schreibt, wirft, statt still umgedreht zu werden.
:::

**Drei Beleglagen, auseinandergehalten**, weil die eine sich später auflöst und
die andere nie:

| Lage | Bedeutung | Zahl |
|---|---|---|
| `belegt` | dieselbe Zahl steht in der Anlage | 11 |
| `ausgeglichen` | Ergebnis 0 — die Ziffer 0 steht in jeder Anlage hundertfach, daran ändert auch OCR nichts | 8 |
| `ohne_anlage` | die Anlage trägt (noch) keinen lesbaren Text | 3 |

**Nur das Ergebnis.** Diese Route liefert kein Erträge/Aufwendungen-Paar; die
einzige zweifach belegte Zahl dieser Dokumente ist das Jahresergebnis. Darum
sind `ertraege` und `aufwendungen` in `council_wirtschaftsplaene` seit dem
20.08.2026 **nullbar** — ein `NULL` sagt „diese Quelle nennt es nicht", eine 0
wäre eine Behauptung. Der Umbau erkennt Altbestände am Schema selbst
(`PRAGMA table_info`), kopiert spaltenweise um und bricht ab, wenn die
Zeilenzahl nicht stimmt.

:::note[Zwei Stadion-Gesellschaften, nicht eine]
Die **Stadionplanungsgesellschaft mbH** und die **Stadion Oldenburg GmbH & Co.
KG** legen eigene Wirtschaftspläne vor — 2024 von beiden einen, über
−152.000 € und −190.000 €. Ein gemeinsames Erkennungsmuster „Stadion" schrieb
den einen Betrag unter den Namen der anderen, und weil `(betrieb, jahr)` der
Schlüssel ist, hätte die zweite Zeile die erste stillschweigend überschrieben.
Beide stehen jetzt getrennt in `BETRIEBE`.
:::

### Im Register, damit der nächste Jahrgang sich meldet

Die Schicht steht als **manuelle** Quelle in `finanzquellen.REIHENFOLGE`:
`erwarteter_monat=11`, `versatz=-1`. Beides ist gemessen und nicht geschätzt —
die acht Entwurfsdaten im Bestand reichen vom 04.09. bis zum 22.11., und die
Schwelle steht auf dem **spätesten** (zu früh gemeldet wäre der teurere
Fehler). Der Plan *für* 2027 ist damit ab dem 01.11.2026 fällig; bleibt er aus,
nennt die Cron-Mail die Schicht samt Skript.

### Kein Cron — noch nicht

`check_finanzdaten` ist auf `council_anlagen` gebaut: `Finanzquelle.erkennung`
sucht ein Anlagen-Label. Diese Schicht wäre die erste, deren Einheit eine
**Vorlage** ist — ein eigener Umbau. Bis dahin ist
`scripts/ingest_wirtschaftsplaene.py` der Weg, und weil die Quelle im Haus
liegt (kein Download), ist er auch der richtige, wenn ein verbesserter Parser
über den Bestand laufen soll.

Von Hand über SSH muss er dafür nicht mehr laufen: Der Ops-Workflow
*„Finanzdaten einlesen (dev)"* ruft ihn mit auf, und sein Bestandsbericht zählt
`council_wirtschaftsplaene` mit. Sein Exit-Code wird dort bis ans Ende
aufgehoben — eine gerissene Rechenprobe färbt den Lauf rot, reißt aber nicht
den Bericht und die Archiv-Sicherung mit sich, die nach ihm kommen.

## Was bewusst fehlt

Der Bereich zeigt lieber eine Lücke als eine Schätzung:

- **Die Fraktions-Änderungslisten selbst — es gibt sie nicht.** Geplant war,
  aus den Änderungslisten zum Haushaltsentwurf zu zeigen, was die Fraktionen
  ändern wollten. Der Ladetest am 18.08.2026 hat die Prämisse widerlegt: Die
  Listen im Bestand heißen „Verwaltung I", „II" oder „III" — Nachträge der
  Verwaltung zu ihrem eigenen Entwurf. Die Listen der Fraktionen wurden als
  **Tischvorlagen** verteilt und liegen in keinem Dokument des
  Ratsinformationssystems.

  Seit dem 26.08.2026 liest `council/aenderungslisten.py` diese Dokumente
  trotzdem — Verwaltungslisten und die „beschlossenen Änderungen" des
  Finanzausschusses, Position für Position, jede Liste beim Einlesen gegen
  ihre eigene „Zusammenstellung der Veränderungen" bewiesen (Tabellen
  `council_haushalt_aenderungen`/`…_summen`, Ingest
  `scripts/ingest_aenderungslisten.py`, Anzeige auf
  `/haushalt/mitreden#streit` als „Was in den Listen stand"). Auch die
  **Erläuterungs-Spalte** wird gelesen: der Text der Verwaltung, was jede
  Änderung ist. Text hat keine Schlusssumme, gegen die man ihn beweisen
  könnte — an die Stelle der Rechenprobe tritt Geometrie: Alle Dokumente
  zeichnen ihre Tabellen als Linienraster, und die waagerechten Linien
  ordnen die mehrzeilig umbrochenen Texte ihrer Zeile eindeutig zu
  (Silbentrennung wird nur am gemessenen Umbruch zusammengezogen). Ohne
  eindeutiges Band bleibt das Feld leer; über 99 % der Positionen tragen
  ihren Text, die restlichen Zellen sind im Original leer. Von den
  Fraktionslisten existiert dort genau eine digitale Spur: ihre
  **Summenzeile** in der Beschluss-Datei, mit dem Urheber daneben
  („SPD/ CDU/ FDP …"). Genau so — Summe mit Urheber, nicht mehr — zeigt die
  Seite sie an. Die frühen Beschluss-Dateien (2020/2021) nennen den Urheber
  je Position („Vorschlag von"); diese Spalte ist der dokumentierte nächste
  Ausbauschritt.

- **Der Schlussbericht 2024** — sein PDF bringt keine Zeichenzuordnung mit,
  der Volltext besteht aus Glyphen-Nummern (`/12 /8 /6 □ /13 …`), sein
  Buchstabenanteil ist **0,000**. Eine zweite Kopie gibt es nicht.

  Seit dem 20.08.2026 führt ein Weg dorthin: `backfill_anlagen_texte.py`
  setzt ihn wegen `MIN_BUCHSTABEN` auf `status='empty'`, und
  `backfill_anlagen_ocr.py` liest von dort. Sein Label trifft zwei
  Finanz-Muster (`%Jahresabschluss%`, `%chlussbericht%`), er steht also in der
  `--nur-finanz`-Liste. Und er ist der **leichteste** Fall dieser Klasse, nicht
  der schwerste: Er ist born-digital, randscharf, ohne Rauschen und ohne
  Schräglage — beim Probelauf las das Modell Seite 33 cent-genau
  (`Summe Eigenbetriebe 273.295.915,34 €`, geprüft gegen die gedruckte Summe).

  **Zwei Dinge standen ihm noch im Weg, beide seit dem 20.08.2026 behoben:**

  Erstens hielt `ocr.seite_als_bild()` sein **Briefkopf-Logo** für die Seite —
  die Regel lautete „genau ein eingebettetes Bild = der Scan", und eine
  Vektorseite mit Logo erfüllt das auch. Zurück kamen 62 Zeichen, die aussahen
  wie ein Ergebnis. Jetzt entscheidet die Auflösung: Das Logo liegt bei 64 dpi
  auf der A4-Fläche, ein echter Scan bei 300 (`MIN_DPI = 100`).

  Zweitens verlangte `pruefberichte.erkenne_jahrgang()` den Titel an
  **Position 0**. Das ging gut, solange der PDF-Textextrakt mit ihm begann;
  per OCR steht davor, was auf dem Papier auch davorsteht. Der `^`-Anker hat
  die eigentliche Arbeit ohnehin nie gemacht — die leistet „**der Stadt
  Oldenburg**" am Titelende, an dem die Stiftungs- und Eigenbetriebsberichte
  („…zum 31. Dezember") durchfallen. Genau das bleibt streng.

  **Was noch fehlt:** ein Renderer auf der Maschine. Seine Seiten tragen kein
  Bild, sondern Vektoren — `pypdfium2` (BSD, ein Wheel mit gebündeltem pdfium)
  zieht der Ops-Workflow bei Bedarf nach. Erst danach ist der Jahrgang wirklich
  im Bestand; bis dahin sagt die Seite es weiter, statt es zu überspielen.
- **Vollständige Produktebene** — für einige Teilhaushalte fehlen auslesbare
  Dokumente: Im Bestand stehen 9 der 13 Teilhaushalte (2025: 10). Gemessen an
  den Aufwendungen, die der Endpunkt als `abdeckung_prozent` ausweist, deckt
  die Produktebene je Jahrgang **71 % bis 87 %** (2020–2025; für 2018/2019
  fehlt die Bezugsgröße in `council_haushalt`, für 2026 die Produktebene).
  Deshalb trägt jedes Produkt ein Abdeckungs-Badge — eine Reihe, die nur die
  vorhandenen Jahre zeigt, sähe sonst durchgehend aus.
- Der Open-Data-Datensatz 1102 enthält abweichende Aufwendungen (2024: 764,7
  statt 728,2 Mio. €), ist aber weder als Ist noch als Nachtrag
  gekennzeichnet; genutzt wird daraus nur die Einwohnerspalte.
- **Grundsteuer-*Aufkommen* für A und B getrennt** — die **Hebesätze** liegen
  seit 08/2026 getrennt vor (`council_hebesaetze` führt „Grundsteuer A" und
  „Grundsteuer B" als eigene Zeilen, 1980–2025). Das **Aufkommen** nicht: Der
  Open-Data-Datensatz führt es als eine Spalte, und `council_steuern` wie
  `council_steuerplan` tragen die Art deshalb als `Grundsteuer A+B`. Daran
  hängt, dass es im Labor keinen Grundsteuer-Regler gibt: Ein Regler braucht
  beides, sonst rechnet er einen Satz gegen ein Aufkommen, das zur Hälfte
  einer anderen Steuer gehört.
- **Gebühren und Beiträge nach Art** — als *Summe* stehen sie längst da: Posten
  05 „öffentlich-rechtliche Entgelte" (2026 im Ansatz 26,6 Mio. €) trägt sie in
  `council_ergebnishaushalt` wie in `council_ergebnisrechnung`, und im
  Flussbild heißt das Band „Gebühren und Beiträge". Was fehlt, ist die
  Aufschlüsselung **je Gebührenart** — welcher Betrag aus Kita-Beiträgen kommt
  und welcher aus Abfallgebühren, sagt keiner der Datensätze. Darum führt
  `/haushalt/einnahmen` sie nicht als eigene Karte, sondern nennt sie im Text
  als das, was dort nicht steht.
- **Verschuldung pro Einwohner im Städtevergleich** — Anlage 2 der
  Gesamtabschlüsse führt sie über acht Jahrgänge samt Osnabrück, Braunschweig
  und Hannover, und die Vorjahres-Kette schließt dort 4/4. Nicht gebaut, weil
  die Vergleichsstädte **nicht aktuell** sind (Braunschweig 2016 gegen
  Oldenburg 2024, vom Dokument selbst markiert) — eine Grafik ohne Jahr an
  jedem Balken wäre still falsch, und das gehört sorgfältig gemacht statt
  nebenbei.
- **Der Schuldenstand aus dem Vorbericht des Haushaltsplans** — er stünde als
  zweite, aktuellere Quelle neben Tabelle 1108 zur Verfügung, steht dort aber
  in einem **Diagramm**. Im Textextrakt sind die Achsenbeschriftungen nicht von
  den Datenwerten zu unterscheiden: keine Summenzeile, keine zweite Spalte,
  nichts, woran sich prüfen ließe, ob eine gelesene Zahl ein Datenpunkt oder
  eine Gitterlinie ist. **Keine Probe möglich, also nicht eingelesen** — auch
  nicht „mit Vorsicht". Tabelle 1108 deckt dieselbe Frage ab und bringt ihre
  Proben mit.
- **Ist je Vorhaben — keine der drei Investitions-Schichten führt es.** Das
  Investitionsprogramm (`council_investitionsmassnahmen`, Anlage 004,
  Abschnitt „Investitionsprogramm: die einzelne Maßnahme" weiter oben) führt
  seit 08/2026 4.459 einzelne **geplante** Vorhaben namentlich, durchsuchbar
  auf `/haushalt/investitionen` — „welche Straße, welche Schule" ist damit
  zur Hälfte beantwortet. Was am Jahresende wirklich abfloss, kennt seither
  der Anlagenspiegel (`council_investitionen_ist`, Abschnitt „Gebaut: das Ist
  zum Investitionsplan" weiter oben) — aber nur nach Auszahlungsart summiert,
  nicht nach Vorhaben. Keine der beiden Quellen führt die Gliederung der
  anderen mit; ein Ist je Vorhaben bräuchte eine dritte Quelle, die bisher
  nicht bekannt ist.
- **Schulgebäude fehlen in allen drei Investitions-Schichten** — im
  Finanzhaushalt (`council_investitionen`) so wenig wie im
  Investitionsprogramm oder im Anlagenspiegel. Sanierung und Neubau liegen
  beim Eigenbetrieb Gebäudewirtschaft und Hochbau mit eigenem Wirtschaftsplan,
  den keine der drei Quellen enthält.
- **Erträge je Teilhaushalt nach Herkunft — für Planjahre.** Die
  Ertragsarten der Planjahre sind seit #530 eingelesen
  (`council_ergebnishaushalt`, 2019–2026); was fehlt, ist ihre Aufteilung
  **je Teilhaushalt**, und die ist auch nicht nachrüstbar:

  `council_haushalt` kennt je Bereich nur **eine** Ertragssumme. Wer sie in
  Bund, Land und Gebühren aufteilen will, braucht `council_ergebnisrechnung` —
  die löst die Posten 01–11 je Teilhaushalt auf, endet aber mit dem letzten
  Jahresabschluss (2024). Der Gesamtergebnishaushalt reicht bis 2026, führt
  aber **keine** Teilhaushalte: In allen acht Dokumenten kommt „THH" kein
  einziges Mal vor.

  Beide zu mischen scheitert an den Ständen. Für 2026 weist
  `council_haushalt` 812,9 Mio. € Erträge aus, `council_ergebnishaushalt`
  788,6 Mio. € — **24,3 Mio. € Abstand**, weil das eine der beschlossene Plan
  ist und das andere Anlage 005 der Einbringungs-Vorlage, also der Entwurf.
  Das Flussbild rechnet mit einer Toleranz von 0,05 Mio. €; eine Grafik, die
  ihre linke Seite aus dem Entwurf und ihre rechte aus dem Beschluss nimmt,
  wäre um das Fünfhundertfache daneben, ohne dass man es ihr ansieht.

  Darum heißt die Leiste auf `/haushalt` „Wo das Geld eingeht" und nicht
  „Woher das Geld kommt": Im Plan 2026 stehen 529,3 der 812,9 Mio. € Erträge
  bei „Finanzmanagement und Recht", weil dort die Kämmerei bucht — das ist ein
  Buchungsort, keine Geldquelle. Aus demselben Grund heißt die zweite Spalte
  der Bereichstabelle „eigene Erträge des Bereichs" und nicht „von Bund, Land
  oder über Gebühren". Was es bräuchte, wäre ein Dokument, das beide Seiten in
  **einem** Stand führt — im Bestand ist keines.

  **Was daraus wurde (20.08.2026):** Für Planjahre zeigt `/haushalt` an der
  Stelle des Flussbilds seitdem die **eine** Seite, die es gibt — die
  Ertragsarten aus dem Gesamtergebnishaushalt, als Rangliste, ohne
  Gegenstück. Das halbe Bild ist mehr wert als gar keines, solange es sich
  als halbes zu erkennen gibt: Der Block heißt „Woher das Geld kommen soll",
  nennt den Plan-Jahrgang und sagt, dass es der Entwurf der Einbringung ist.

  Und er beziffert den Abstand zur Anzeigetafel derselben Seite, weil die
  eine andere Ertragssumme nennt: 2026 sind es 24,3 Mio. €, 2025 sogar
  26,2 Mio. € — einmal liegt der Entwurf darunter, einmal darüber. Gerechnet,
  nicht geschrieben (`einnahmearten().tafel`), damit die Zahl beim nächsten
  Jahrgang nicht still falsch wird. Zwei Zahlen auf einer Seite, die dasselbe
  zu meinen scheinen, sind schlimmer als eine Lücke.

## Befunde aus dem Datenabgleich

Beim Abgleich der Entwürfe mit den echten Zahlen fielen Annahmen durch, die
plausibel klangen:

- **Die Finanzkrise 2009 ist in Oldenburg nicht sichtbar.** Die Gewerbesteuer
  stieg 2009 von 58,9 auf 61,9 Mio. €. Die realen Einbrüche liegen 2000
  (−8,5) und 2003 (−7,8); Corona 2020 kostete nur 3,8 Mio. Die Ist-Kurve
  berechnet ihre Marker deshalb aus den Daten, statt Geschichte zu deuten.
- **Der Finanzausgleich dämpft, aber nicht mit festem Faktor.** Ausgleichs-
  jahr 2024 → 2025 stieg die Steuerkraft um 45,9 Mio. €, während die
  Zuweisungen um 30,4 Mio. fielen; 2025 → 2026 stiegen beide. Der Effekt ist
  systematisch real, seine Höhe hängt am Landestopf — das Labor beziffert ihn
  deshalb nicht, sondern benennt ihn mit den echten Jahreszahlen daneben.
- **Stiftungsvermögen ist keine freiwillige Leistung.** Es ist zweckgebunden
  und wird treuhänderisch verwaltet; als kürzbar geführt hätte das Labor eine
  Handlungsmöglichkeit behauptet, die es nicht gibt.
- **Bestätigt:** Alle überwiegend freiwilligen Bereiche zusammen kosten
  47,1 Mio. € — das geplante Defizit beträgt 71,1 Mio. Kürzen allein schließt
  es rechnerisch nicht.

### Der Datensatz 1106 ist um ein Jahr verschoben

Der einzige Fall bisher, in dem wir eine Quelle **korrigieren** statt sie zu
übernehmen — und der einzige, der eine so lange Begründung verdient.

Der Open-Data-Datensatz 1106 („Steuerkraftmesszahlen und Schlüsselzuweisungen")
führt seine Spalte als `Ausgleichsjahr`, beschriftet die Zeilen aber um ein
Jahr zu früh. Geprüft am 16.08.2026, an drei unabhängigen Strängen:

1. **Das Landesamt für Statistik Niedersachsen (LSN)** — die Stelle, die den
   Begriff definiert und die Zahlen liefert. Seine KFA-Tabellen (Blatt
   `ST_KR_MESS_VGL`, Schlüssel-Nr. 403000) tragen dieselben Beträge auf den
   Euro genau, nur ein Jahr später: **12 von 12** Steuerkraftmesszahlen aus
   den Jahrgängen KFA 2016–2026 decken sich mit der CSV-Zeile `Jahr−1`,
   **keine einzige** mit der gleichnamigen. Für die Schlüsselzuweisungen
   (Blatt `9a`) gilt dasselbe; die Ausreißer sind durchweg vorläufige Stände,
   die das LSN später selbst korrigiert hat.
2. **Die Bücher der Stadt** — und das entscheidet die Frage, weil es kein
   Beschriftungs-, sondern ein Kassenfakt ist. Der Haushaltsplan 2026 weist
   als **Ist 2024** 99.569.132 € Schlüsselzuweisungen aus (Konten 31111000 +
   31112000), der Haushaltsplan 2025 als **Ist 2023** 100.319.768 € — beide
   stehen in der CSV eine Zeile zu früh. Der Jahresabschluss 2024 nennt im
   Fließtext „rund 109,5 Millionen Euro" und trifft damit den LSN-Nettobetrag
   des Ausgleichsjahrs 2024.
3. **Die Metadaten widersprechen sich selbst.** Die Spalte heißt
   „Ausgleichsjahr", die Datensatzbeschreibung spricht von „für jedes
   Haushaltsjahr". Der Widerspruch ist im Portal nicht aufgelöst.

**Was wir daraus machen:** `haushalt.parse_steuerkraft` rückt jede Jahreszahl
um eins nach vorn; `council_steuerkraft.jahr` ist damit das Ausgleichsjahr,
wie es die Tabelle ohnehin immer behauptet hat. Die beiden Pro-Kopf-Spalten
des Datensatzes bleiben liegen — die Stadt rechnet sie gegen die
Einwohnerzahl ihrer eigenen, verschobenen Jahresangabe (16 von 16 Mal von
2010 bis 2025 nachgerechnet), nach dem Rücken stünde eine
Ausgleichsjahr-Zahl über einem Nenner aus dem Vorjahr.

**Was offen bleibt:** Direkt belegt ist der Versatz für die CSV-Jahre
2015–2025; weiter zurück stellt das LSN nichts mehr online. Dass die Reihe
durchgehend derselben Konvention folgt, zeigt die Pro-Kopf-Probe oben auch
für die Jahre davor — ein Bruch mitten in der Reihe müsste sich dort zeigen
und tut es nicht.

**Gemeldet am 16.08.2026** an die Stadt Oldenburg (Ansprechpartner laut
Katalog: die Statistikstelle). Damit liegt der Befund bei der Stelle, die ihn
beheben kann — die Korrektur in `haushalt.parse_steuerkraft` bleibt bis dahin
und darüber hinaus bestehen: Sie greift am Bestand, nicht an der Quelle, und
ein stillschweigend korrigiertes Portal würde sie sonst doppelt anwenden. Wer
eine neue Lieferung einliest, prüft deshalb zuerst die Pro-Kopf-Probe.
