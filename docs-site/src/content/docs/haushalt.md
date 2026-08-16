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
| `/haushalt/produkte[?nr=<produkt_nr>]` | „Was kostet eigentlich …?" — Produktsuche mit Filtern (Amt, Spielraum); `nr` öffnet den Steckbrief |
| `/haushalt/pflicht` | Muss oder kann — Teilhaushalte nach Gestaltungsspielraum |
| `/haushalt/labor` | Was-wäre-wenn: Hebesatz-Regler und Kürzungen, jede Bewegung in Mio., € je Einwohner und Anteil an der Lücke; dauerhaft sichtbare Gegenrechnung |
| `/haushalt/pruefung` | Was das Rechnungsprüfungsamt beanstandet: alle Feststellungen der Schlussberichte im Wortlaut, mit Textziffer, Seite und Deeplink; dazu die Ketten über die Jahrgänge |

Query-Parameter statt dynamischer Segmente, weil der Capacitor-Export die
Slugs zur Bauzeit nicht kennt — dieselbe Konvention wie `/council/decision?id=`.

## Woher die Daten kommen

Fast alles läuft über **einen** Endpunkt: `GET /api/council/haushalt` liefert
Planjahre, Ist-Steuern, Steuerkraft und die Einwohnerzahl in einem Aufruf.
Nur die Prüfungsfeststellungen hängen an einem eigenen
(`GET /api/council/haushalt/pruefberichte`) — sie sind eine Viertel-Megabyte
Prosa und haben auf Seiten, die sie nicht zeigen, nichts zu suchen.

| Tabelle | Inhalt | Quelle | Ingest |
|---|---|---|---|
| `council_haushalt` | Ergebnishaushalt je Teilhaushalt, 2020–2026 (**Plan**) | Beschlossene Haushaltsplan-PDFs; 2024 aus dem Open-Data-CSV | `scripts/ingest_haushalt.py` |
| `council_steuern` | Steuereinnahmen je Art seit 1998 (**Ist**) | Open-Data-Portal, Datensatz 1104 | `scripts/ingest_finanzen_opendata.py` |
| `council_steuerkraft` | Steuerkraftmesszahl + Schlüsselzuweisungen seit 1992 | Open-Data-Portal, Datensatz 1106 | dito |
| `council_einwohner` | Einwohnerzahl je Jahr seit 2010 | Open-Data-Portal, Datensatz 1102 | dito |
| `council_ergebnisrechnung` | Ansatz, Plan **und** Ergebnis je Posten — gesamt und je Teilhaushalt, 2017–2024 | Jahresabschlüsse — **Anlagen im RIS** | `scripts/ingest_finanzberichte.py` |
| `council_abweichungsgruende` | Warum ein Posten vom Plan abwich (Abschnitt 6.3.1), 45 Einträge | dito | dito |
| `council_pruefbericht_quellen` | **Fundstelle** des RPA-Schlussberichts je Jahrgang (eine Zeile je Jahr) | dito | dito |
| `council_produkte` | Produktebene: was einzelne Aufgaben kosten — plus Steckbrief (Kurzbeschreibung, Auftragsgrundlage, Beeinflussbarkeit, Wirkungskreis, Zielgruppe) | Teilhaushalts-Pläne — **Anlagen im RIS** | dito |
| `council_pruefberichte` | Prüfungsfeststellungen 2017–2023, eine Zeile je Randmarke | Schlussberichte des Rechnungsprüfungsamts — **Anlagen im RIS** | `scripts/ingest_pruefberichte.py` |

:::note[Zwei Tabellen zu denselben Berichten]
`council_pruefbericht_quellen` hält die **Fundstelle** des Schlussberichts
(eine Zeile je Jahrgang, für den Verweis „geprüft → Schlussbericht"),
`council_pruefberichte` die **einzelnen Feststellungen** daraus (eine Zeile je
Randmarke). Zwei Ebenen, zwei Tabellen — die Namen halten sie auseinander.
:::

Alle Ingests sind idempotent. Die vier Schichten aus dem **Ratsinformations-
system** zieht seit 08/2026 ein Cron von allein nach (siehe unten); die
Ingest-Skripte bleiben der Weg von Hand, wenn ein verbesserter Parser über den
**Bestand** laufen soll. Die Plan- und Open-Data-Schichten (`council_haushalt`,
`council_steuern`, `council_steuerkraft`, `council_einwohner`) kommen per
Download von oldenburg.de und bleiben Handarbeit.

:::caution[Plan ist nicht Ist]
`council_haushalt` enthält **Planwerte** (was der Rat beschlossen hat),
`council_steuern` **Ist-Werte** (was tatsächlich geflossen ist). Die beiden
dürfen nie in einem Satz vermischt werden — im Frontend stehen sie in
getrennten Bausteinen, und die Prompt-Bausteine der KI-Frage
(`_haushalt_block`, `_steuern_block`) sagen dem Modell ausdrücklich, was sie
sind.
:::

## Der Bereich hält sich selbst aktuell

Fünf Datenschichten, jede einmal von Hand eingelesen — ohne Cron veraltet der
ganze Bereich still, sobald niemand mehr daran denkt. `check_finanzdaten.py`
(alle zwei Wochen) nimmt das ab.

**Bestandsgesteuert, nicht kalendergesteuert.** Der Job fragt nicht „ist es
September?", sondern *„welcher Jahrgang fehlt mir, und liegt inzwischen ein
Dokument dafür vor?"*. Ein Job, der im September nach dem Jahresabschluss
sucht, bricht in dem Jahr, in dem die Stadt später dran ist. So ist der Takt
egal: Verspätungen, Nachtragshaushalte und nachgereichte Prüfberichte sind
automatisch abgedeckt, und der Job darf beliebig oft laufen.

Aus acht Jahrgängen Sitzungsdaten (`council_sessions.session_date` über
`council_agenda_items`) ergibt sich der Rhythmus der Stadt:

| Was | Wann im Rat | Ausnahmen |
|---|---|---|
| Jahresabschluss + RPA-Schlussbericht + Rechenschaftsbericht | **Anfang September** | 1× August |
| Haushaltsplan mit Gesamtergebnishaushalt und Teilhaushalten | **Anfang Oktober** | 1× November |

Der Monat steuert **nicht** die Suche, sondern nur die Meldung: Bleibt ein
Jahrgang länger als vier Wochen über seinen üblichen Monat hinaus aus, geht ein
Hinweis an `ALERT_EMAIL` — kein Fehler, sondern die Frage, ob die Stadt spät
dran ist oder ein Erkennungsmuster nicht mehr greift. Die Mail unterscheidet
beides: Liegt ein passendes Dokument vor und wird trotzdem nichts übernommen,
steht das ausdrücklich drin. Gemeldet wird nur, wenn sich die Liste gegenüber
dem letzten Lauf geändert hat (Vergleich über `job_runs`) — alle vierzehn Tage
dieselbe Mail wäre eine, die niemand mehr liest.

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
3. **Er ergänzt nur, was fehlt.** Ein vorhandener Jahrgang wird nicht angefasst.
   Zweimal hintereinander laufen ändert beim zweiten Mal keine einzige Zeile.

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
| Haushaltsplan | *(kein Anlagen-Muster — Download)* | `council_haushalt` | Oktober, Jahrgang − 1 |

### Der Datenstand ist sichtbar

`GET /api/council/haushalt/datenstand` liefert diese Matrix live aus dem
Bestand; der Block **„Bis wann die Zahlen reichen"** am Fuß von `/haushalt`
(`components/haushalt/datenstand.tsx`) zeigt sie.

Das ist kein Entwickler-Feature. Auf `/haushalt` steht der Plan für 2026, auf
`/haushalt/plan-ist` die Abrechnung für 2024, auf `/haushalt/pruefung`
Feststellungen bis 2023 — die Frage „warum steht hier 2024 und nicht 2025?"
müsste sonst auf neun Seiten einzeln beantwortet werden. Die Ursache ist immer
dieselbe und liegt bei der Stadt. Wo ein Jahrgang erwartet wird, aber noch
fehlt, steht das ausdrücklich da: *„Der Jahrgang 2025 wird üblicherweise im
September 2026 vorgelegt."* Das Wort „fehlt" kommt nicht vor — was die Stadt
noch nicht veröffentlicht hat, fehlt uns nicht.

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

## Der Produkt-Steckbrief

Zu jedem Produkt führen die Pläne einen Steckbrief: **Kurzbeschreibung**
(was die Aufgabe umfasst), **Auftragsgrundlage** (die Gesetze, Satzungen und
Verträge dahinter), **Grad der Beeinflussbarkeit**, **Wirkungskreis** und
**Zielgruppe**. Das beantwortet die häufigste Bürgerfrage zum Haushalt — „was
kostet eigentlich das Stadtarchiv?" — und belegt die Pflicht/Kür-Einordnung,
die auf `/haushalt/pflicht` bisher nur geschätzt ist.

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

## Was bewusst fehlt

Der Bereich zeigt lieber eine Lücke als eine Schätzung:

- **Produktebene 2024 und 2025** — die Teilhaushalts-Pläne liegen als Anlage
  vor, aber ihr Tabellenlayout hat sich geändert: Zwischen „21. ordentliches
  Ergebnis" und den Zahlen stehen jetzt zwei Beschriftungszeilen
  („Jahresüberschuss(+) / Jahresfehlbetrag (-)"), und die Prüfsumme
  *Erträge − Aufwendungen = Ergebnis* greift ins Leere. Der Bestand bleibt
  deshalb bei 2023 stehen. Genau dieser Fall ist der Grund für den Hinweis aus
  `check_finanzdaten.py`: „Dokument liegt vor, wird aber nicht übernommen".
- **Der Schlussbericht 2024** — sein PDF bringt keine Zeichenzuordnung mit,
  der Volltext besteht aus Glyphen-Nummern (`/12 /8 /6 □ /13 …`) und läuft in
  die 400.000-Zeichen-Kappung. Eine zweite Kopie gibt es nicht; ein neuer
  Versuch bräuchte OCR. Der Jahrgang scheitert schon an der
  Textanfang-Erkennung, ganz ohne Sonderfall — und die Seite sagt das, statt
  es zu überspielen.
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
