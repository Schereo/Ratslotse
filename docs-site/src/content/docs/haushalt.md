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
| `council_ergebnisrechnung` | Ansatz **und** Ergebnis je Posten — gesamt (5 Jahrgänge) und je Teilhaushalt (4) | Jahresabschlüsse — **Anlagen im RIS** | `scripts/ingest_finanzberichte.py` |
| `council_produkte` | Produktebene: was einzelne Aufgaben kosten — plus Steckbrief (Kurzbeschreibung, Auftragsgrundlage, Beeinflussbarkeit, Wirkungskreis, Zielgruppe) | Teilhaushalts-Pläne — **Anlagen im RIS** | dito |
| `council_pruefberichte` | Prüfungsfeststellungen 2017–2023, eine Zeile je Randmarke | Schlussberichte des Rechnungsprüfungsamts — **Anlagen im RIS** | `scripts/ingest_pruefberichte.py` |

Alle Ingests sind idempotent und laufen **nicht** als Cron — einmal jährlich
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
(Steuern, Zuwendungen, Entgelte, Kostenerstattungen). Eingelesen sind 2019
und 2021–2024; 2017, 2018 und 2020 haben ein abweichendes Tabellenlayout und
werden übersprungen, statt geraten zu werden.

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

:::note[Die dritte Prüfung: die Summe über alle Teilhaushalte]
Der Jahresabschluss führt dieselbe Ergebnisrechnung noch einmal je
Teilhaushalt. Die zeilenweise Prüfung greift dort zu kurz: Wird für einen
Teilhaushalt versehentlich eine andere, in sich stimmige Tabelle gelesen,
sind die Zahlen konsistent — aber falsch. Im Abschluss 2022 wurde THH09 so
mit 0,1 statt 26,8 Mio. € gelesen. Erst die Summe über alle Teilhaushalte
machte es sichtbar. `finanzberichte.summenprobe()` verlangt deshalb, dass
diese Summe die Gesamtrechnung ergibt (±1 %); 2022 fällt dadurch für die
Teilhaushalts-Ebene aus, die vier übrigen Jahrgänge stimmen auf 0,00 %.
:::

:::note[Zwei Prüfsummen aus den Dokumenten selbst]
Aus PDF-Text extrahierte Tabellen verschmelzen Zahlen („355.188334.704") und
kleben Seitenzahlen an Werte. Beide Parser übernehmen deshalb nur Zeilen, die
eine im Dokument dokumentierte Rechenbeziehung erfüllen: beim Jahresabschluss
`Abweichung = Ergebnis − Ansatz` (Fußnote 4 der Tabelle), beim Teilhaushalt
`Erträge − Aufwendungen = ordentliches Ergebnis`. Was durchfällt, fehlt —
lieber eine Lücke als eine Zahl, die niemand nachrechnen kann.
:::

Ein Nebenertrag: Die Ansätze aus den Jahresabschlüssen bestätigen die Werte,
die wir aus den Plan-PDFs lesen (2023: 664,6 gegen 664,9 Mio. €; 2024: 693,6
gegen 693,9). Zwei unabhängige Wege zur selben Zahl.

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

- **Jahresabschlüsse 2017, 2018, 2020** — abweichendes Tabellenlayout, von
  den Parser-Prüfsummen zurückgewiesen.
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
