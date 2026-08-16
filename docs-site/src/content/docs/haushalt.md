---
title: Stadtfinanzen
description: Der Haushalts-Bereich — woher die Zahlen kommen, welche redaktionell sind, und was bewusst fehlt.
---

Der Haushalt ist der sperrigste Stoff, den Ratslotse zeigt: Doppik-Vokabular,
Millionenbeträge ohne Bezugsgröße, Zuständigkeiten quer über drei staatliche
Ebenen. Der Bereich unter `/haushalt` übersetzt ihn — und macht dabei an jeder
Stelle sichtbar, welche Zahl amtlich ist, welche wir gerechnet haben und
welche schlicht fehlt.

## Die Seiten

| Route | Inhalt |
|---|---|
| `/haushalt` | Übersicht: Kernzahlen, Rücklagen-Reichweite, Geldfluss (Balken oder 100-Euro-Ansicht), Zeitreihe, Bereichskarten |
| `/haushalt/bereich?name=<slug>` | Dossier je Teilhaushalt: Brutto/Netto, Kostendeckung, Brutto-gegen-Netto-Vergleich, Entwicklung |
| `/haushalt/einnahmen` | Alle Einnahmequellen mit Spielraum-Kodierung (frei / begrenzt / kein Einfluss) |
| `/haushalt/steuer?art=<slug>` | Steckbrief je Einnahmeart: „Wer entscheidet was", Ist-Kurve, Hebesatz, Ein-Punkt-Überschlag |
| `/haushalt/pflicht` | Muss oder kann — Teilhaushalte nach Gestaltungsspielraum |
| `/haushalt/labor` | Was-wäre-wenn: Hebesatz-Regler und Kürzungen, jede Bewegung in Mio., € je Einwohner und Anteil an der Lücke; dauerhaft sichtbare Gegenrechnung |

Query-Parameter statt dynamischer Segmente, weil der Capacitor-Export die
Slugs zur Bauzeit nicht kennt — dieselbe Konvention wie `/council/decision?id=`.

## Woher die Daten kommen

Alles läuft über **einen** Endpunkt: `GET /api/council/haushalt` liefert
Planjahre, Ist-Steuern, Steuerkraft und die Einwohnerzahl in einem Aufruf.

| Tabelle | Inhalt | Quelle | Ingest |
|---|---|---|---|
| `council_haushalt` | Ergebnishaushalt je Teilhaushalt, 2020–2026 (**Plan**) | Beschlossene Haushaltsplan-PDFs; 2024 aus dem Open-Data-CSV | `scripts/ingest_haushalt.py` |
| `council_steuern` | Steuereinnahmen je Art seit 1998 (**Ist**) | Open-Data-Portal, Datensatz 1104 | `scripts/ingest_finanzen_opendata.py` |
| `council_steuerkraft` | Steuerkraftmesszahl + Schlüsselzuweisungen seit 1992 | Open-Data-Portal, Datensatz 1106 | dito |
| `council_einwohner` | Einwohnerzahl je Jahr seit 2010 | Open-Data-Portal, Datensatz 1102 | dito |
| `council_ergebnisrechnung` | Ansatz, Plan **und** Ergebnis je Posten — gesamt und je Teilhaushalt, 2017–2024 | Jahresabschlüsse — **Anlagen im RIS** | `scripts/ingest_finanzberichte.py` |
| `council_abweichungsgruende` | Warum ein Posten vom Plan abwich (Abschnitt 6.3.1), 45 Einträge | dito | dito |
| `council_pruefbericht_quellen` | **Fundstelle** des RPA-Schlussberichts je Jahrgang (eine Zeile je Jahr) | dito | dito |
| `council_produkte` | Produktebene: was einzelne Aufgaben kosten | Teilhaushalts-Pläne — **Anlagen im RIS** | dito |

Beide Ingests sind idempotent und laufen **nicht** als Cron — einmal jährlich
von Hand reicht, wenn die Stadt einen neuen Jahrgang veröffentlicht.

:::caution[Plan ist nicht Ist]
`council_haushalt` enthält **Planwerte** (was der Rat beschlossen hat),
`council_steuern` **Ist-Werte** (was tatsächlich geflossen ist). Die beiden
dürfen nie in einem Satz vermischt werden — im Frontend stehen sie in
getrennten Bausteinen, und die Prompt-Bausteine der KI-Frage
(`_haushalt_block`, `_steuern_block`) sagen dem Modell ausdrücklich, was sie
sind.
:::

## Die redaktionelle Schicht

Drei Dinge liefert keine Datenquelle. Sie stehen als gepflegte Konstanten im
Frontend, damit sie überprüfbar bleiben:

- **`lib/haushalt-steuern.ts`** — je Einnahmeart: die Stufen „Wer entscheidet
  was", Spielraum-Einstufung, Rechenbeispiel, Lotti-Erklärung.
- **`lib/haushalt-pflicht.ts`** — Einordnung der Teilhaushalte in Pflicht /
  Pflicht mit Spielraum / überwiegend freiwillig. Eine Einschätzung auf Ebene
  ganzer Teilhaushalte; die Seite sagt das auch.
- **`lib/haushalt-quellen.ts`** — Fundstellen, Datenstände und Lizenzen.

## Quellen-System

Jede Zahl trägt einen Beleg-Chip, am Seitenende steht das Verzeichnis mit
Dokument, Fundstelle, Stand, Lizenz und Direktlink. Die Nummerierung läuft
**seitenweise** über `<Quellenkontext>` — global gezählt trüge eine Seite mit
zwei Quellen die Nummern 2 und 4.

Werte, die wir selbst bilden (Anteile, Differenzen, Rücklagen-Reichweite,
Pro-Kopf-Angaben, Ein-Punkt-Überschlag), sind an Ort und Stelle als
*„unsere Rechnung, keine amtliche Kennzahl"* gekennzeichnet.

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

### Vier Prüfungen, und keine davon ist optional

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

## Was bewusst fehlt

Der Bereich zeigt lieber eine Lücke als eine Schätzung:

- **Jahresabschlüsse 2017, 2018, 2020** — abweichendes Tabellenlayout, von
  den Parser-Prüfsummen zurückgewiesen.
- **Vollständige Produktebene** — für einige Teilhaushalte fehlen auslesbare
  Dokumente; die Abdeckung schwankt je Jahr zwischen 63 % und 82 %.
- Der Open-Data-Datensatz 1102 enthält abweichende Aufwendungen (2024: 764,7
  statt 728,2 Mio. €), ist aber weder als Ist noch als Nachtrag
  gekennzeichnet; genutzt wird daraus nur die Einwohnerspalte.
- **Grundsteuer A und B getrennt** — das Portal führt sie in einer Spalte.
  Deshalb eine gemeinsame Karte und im Labor kein Grundsteuer-Regler.
- **Gebühren und Beiträge** — in keinem der Datensätze enthalten.
- **Hebesatz-Zeitreihe und Städtevergleich** — kommen aus der
  Statistik-Schnittstelle des Landes, sobald sie angebunden ist.

## Befunde aus dem Datenabgleich

Beim Abgleich der Entwürfe mit den echten Zahlen fielen Annahmen durch, die
plausibel klangen:

- **Die Finanzkrise 2009 ist in Oldenburg nicht sichtbar.** Die Gewerbesteuer
  stieg 2009 von 58,9 auf 61,9 Mio. €. Die realen Einbrüche liegen 2000
  (−8,5) und 2003 (−7,8); Corona 2020 kostete nur 3,8 Mio. Die Ist-Kurve
  berechnet ihre Marker deshalb aus den Daten, statt Geschichte zu deuten.
- **Der Finanzausgleich dämpft, aber nicht mit festem Faktor.** 2023 → 2024
  stieg die Steuerkraft um 45,9 Mio. €, während die Zuweisungen um 30,4 Mio.
  fielen; 2024 → 2025 stiegen beide. Der Effekt ist systematisch real, seine
  Höhe hängt am Landestopf — das Labor beziffert ihn deshalb nicht, sondern
  benennt ihn mit den echten Jahreszahlen daneben.
- **Stiftungsvermögen ist keine freiwillige Leistung.** Es ist zweckgebunden
  und wird treuhänderisch verwaltet; als kürzbar geführt hätte das Labor eine
  Handlungsmöglichkeit behauptet, die es nicht gibt.
- **Bestätigt:** Alle überwiegend freiwilligen Bereiche zusammen kosten
  47,1 Mio. € — das geplante Defizit beträgt 71,1 Mio. Kürzen allein schließt
  es rechnerisch nicht.
