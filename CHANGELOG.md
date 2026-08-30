# Changelog

Alle nennenswerten Änderungen an diesem Projekt (Ratslotse) werden hier dokumentiert.

Das Format orientiert sich an [Keep a Changelog](https://keepachangelog.com/de/1.1.0/),
die Versionierung folgt [Semantic Versioning](https://semver.org/lang/de/).

## [Unreleased]

## [1.15.0] – 2026-08-30

### Geändert
- **Die Abo-Seite ist jetzt eine Liste statt zweier.** Abonnierte und offene
  Gremien standen getrennt untereinander — wer etwas abonnierte, sah es nach
  oben springen, und alles darunter verrutschte. Jetzt stehen alle Gremien in
  einer Liste, sortiert nach Alltagsbezug; dass etwas abonniert ist, sagt der
  Knopf, und die Reihenfolge ändert sich durch einen Klick nie. Beim Abonnieren
  läutet kurz eine Glocke — sie zeigt, was das Abo zusagt. Wer weniger Bewegung
  eingestellt hat, sieht sie nicht. **Die Themen-Karte zählt jetzt ein halbes
  Jahr statt 30 Tagen.** „0 in 30 Tagen" stand bei fast jedem Thema, auch bei
  sehr lebendigen: Die Gremien tagen monatlich, im Sommer gar nicht, und
  Protokolle kommen mit Verzug. Sechs Monate umfassen mehrere Sitzungsrunden und
  trennen wirklich Laufendes von Ruhendem. (#826)
- **Die E-Mails von Ratslotse sehen jetzt nach Ratslotse aus.** Alle Mails — von
  der Bestätigung nach der Registrierung über Passwort-Reset und
  Einrichtungs-Erinnerung bis zu den Benachrichtigungen — teilen sich eine neue
  Hülle: weiße Karte auf hellem Grund, Hafenblau statt Fremdblau, und oben eine
  zum Anlass passende 3D-Lotti-Szene (winkende Lotti mit Küken zur Begrüßung,
  grübelnde Lotti unterm Fragezeichen beim Passwort, jubelnde Lotti mit Konfetti
  zur Freischaltung, lesende Lotti bei Neuigkeiten aus dem Rat …). (#827)

## [1.14.0] – 2026-08-28

### Hinzugefügt
- **Der Haushalts-Wegweiser hat jetzt ein Gedächtnis — und Etappen.** Die
  Liste der sechzehn Schritte auf der Haushalts-Übersicht war zur Wand
  geworden; jetzt sind es vier Etappen-Karten („Die Zahlen", „Die
  Gegenprobe", „Der Rahmen", „Mitreden"), auf dem Telefon ein Akkordeon, bei
  dem nur die aktuelle Etappe offen steht. Besuchte Seiten merkt sich der
  Browser (lokal, kein Konto nötig): Erledigte Etappen tragen ihr Häkchen,
  und ein Knopf „Weiter, wo du warst" springt zum ersten noch nicht
  gelesenen Schritt. Dazu vier Detail-Korrekturen aus dem Board-Review:
  Auf „Was steckt hinter den Namen?" sind Klartext und Zahlen jetzt EINE
  Zeile je Bereich (mit Balken, umschaltbarer Sortierung und nachgeschärften
  Erklärtexten — bei „Personal" steht jetzt dabei, dass dort nicht die
  Gehälter aller Beschäftigten stehen); auf „Muss oder kann?" tragen die
  Selbstauskunft der Stadt (◇) und unsere Zuordnung (●) je einen eigenen
  Marker, weil es zwei Quellen sind; die Produktsuche sagt bei null Treffern,
  was ähnlich klingt, und jedes Produkt trägt ein Abdeckungs-Badge („ohne
  2019–2020"), weil nicht jedes Jahr jeden Teilhaushalt deckt; und im
  Haushalts-Labor klebt das Ergebnis auf dem Telefon jetzt unten über der
  Tab-Leiste — die Wirkung steht direkt unterm Daumen, statt oben ein
  Drittel des Schirms zu belegen. (#580)
- **Vier weitere Formen im Grafik-Baukasten.** Der Gegenbalken (zwei
  100-%-Leisten, die sich eine einzige Basis teilen — der Maßstabsfehler,
  bei dem ein Defizit-Haushalt ausgeglichen aussieht, ist damit technisch
  nicht mehr baubar), der Kassenzettel (der Bon rechnet seine Rundungszeile
  selbst, trägt den Teiler sichtbar unter dem Zettel und reist nie ohne
  seinen „Was diese Zahl nicht ist"-Kasten), der Wasserfall (Abzüge hängen
  an der Laufsumme, eine eingebaute Summenprobe meldet Rechenfehler der
  Seite, und das Ergebnis wird nie rot — Zuschussbedarf ist Daseinsvorsorge)
  und das verallgemeinerte Flussbild (bewusst kein Sankey: alle Kurven enden
  in der EINEN Kasse). Die Haushalts-Seiten benutzen sie bereits; für Leser
  ändert sich das Bild kaum, aber jede künftige Seite komponiert nur noch,
  statt zu zeichnen. (#580)
- **Wer wollte den Haushalt ändern — und kam damit durch?** „Der Streit ums
  Geld" (`/haushalt/streit`) trägt jetzt eine Verhandlungsbilanz als
  tragendes Bild: je Fraktion ein Punkt pro Abstimmung über eine
  Änderungsliste, Finanzausschuss und Rat getrennt, gefüllt heißt „fand
  eine Mehrheit". Bewusst ohne Erfolgsquote — eingebracht und abgelehnt ist
  parlamentarischer Alltag der Opposition, kein Zeugnis; die Reihenfolge
  ist alphabetisch, die Punktgröße für alle gleich. Wortbeiträge ohne
  Fraktion (Namensvettern in der Anwesenheitsliste) stehen als eigene,
  gezählte Karte da — es wird keine geraten. (#578)
- **Ein Haushalt lebt länger als ein Jahr — der Strahl zeigt es.** „Wann
  der Haushalt entschieden wird" (`/haushalt/jahr`) ersetzt den Jahreskreis
  durch einen liegenden Zeitstrahl mit „Sie sind hier"-Pin: von der
  Einbringung über Ausschüsse und Ratsbeschluss bis zum Jahresabschluss,
  jede Station mit gezählter Angabe („in 7 von 8 Jahrgängen im Oktober")
  statt Behauptung. Auf dem Telefon kippt der Strahl senkrecht. Dazu eine
  Termin-Karte mit dem nächsten echten Termin von Finanzausschuss oder Rat
  aus dem Ratskalender — samt Kalender-Export und dem ehrlichen Hinweis,
  dass erst die Tagesordnung zeigt, ob dort der Haushalt aufgerufen
  wird. (#578)
- **4.459 Vorhaben, durchsuchbar.** „Was wird gebaut?"
  (`/haushalt/investitionen`) endete bisher bei einer Liste je Bereich —
  jetzt trägt eine Kachelfläche die Übersicht: Jede Kachel ist ein Vorhaben,
  ihre Fläche die Gesamtsumme, ein Quadratmillimeter ist überall gleich viel
  Geld. Die Masse der kleinen Vorhaben steht ehrlich als eigene Kachel da,
  Suchtreffer heben sich per Umriss hervor, Jahrgang und Bereich lassen sich
  filtern. Zwei Kästen stehen bewusst, wo man sie braucht: „Wo sind die
  Schulen?" **vor** den Ergebnissen (Schulgebäude laufen beim Eigenbetrieb,
  nicht in diesem Programm) und „Planzahlen, keine Beschlüsse" bei den
  Zahlen. Auf dem Telefon ersetzt eine Rangliste die Kacheln — gleiche
  Daten, gleiche Reihenfolge, lesbare Beschriftung. (#577)
- **Der Sprung bei der Grundsteuer, als Bild.** Auf „Steht Oldenburg besser
  da?" (`/haushalt/vergleich`) zeigt ein Vorher-nachher-Diagramm die
  Hebesätze aller acht kreisfreien Städte über die Reform 2025 hinweg —
  Oldenburg hervorgehoben, „unverändert" ausgeschrieben statt als flache
  Linie versteckt. Mitten im Bild steht der Bruch-Marker „ab 2025 neue
  Messbeträge": Über die Reform hinweg sind die Sätze nicht vergleichbar,
  und die Grafik sagt das selbst, statt es einer Fußnote zu überlassen. (#577)
- **Was der Schuldenstand im Jahr kostet.** Die Schuldenkurve
  (`/haushalt/schulden`) trägt jetzt die Zinslast als dünne, gestrichelte
  zweite Linie im selben Bild und auf derselben Skala — dass sie fast auf der
  Nulllinie klebt, ist die Auskunft. Der auffälligste Knick der Reihe erklärt
  sich direkt im Bild: „2010: 108,9 Mio. umgebucht" — Kredite wanderten an
  einen Eigenbetrieb, kein Tilgungswunder. Die Ablesezeile zeigt Summe und
  Zins gemeinsam. (#577)
- **Warum ein Bereich vom Plan abwich, steht jetzt an der Abweichung.** Auf
  „Geplant und geworden" (`/haushalt/plan-ist`) trägt jede Hantel-Zeile den
  Satz, mit dem der Jahresabschluss selbst die Abweichung erklärt —
  Wortlaut der Verwaltung, klar gekennzeichnet. Wo der Abschluss einen
  Bereich nicht erläutert, steht bewusst kein Satz: Erfunden wird nichts.
  Sortiert ist nach Größe der Abweichung, kleine Bereiche stehen hinter
  „alle zeigen", und die Achse sagt selbst, in welcher Einheit sie misst. (#577)
- **Aus „18 %" wird ein zählbares Bild.** Auf „Wer macht die Arbeit?"
  (`/haushalt/personal`) steht der Stellenplan jetzt als Waffel: Ein Quadrat
  sind zehn Stellen, die unbesetzten tragen einen orangenen Umriss — samt dem
  Stichtag, zu dem gezählt wurde, denn die Besetzung wird immer ein Jahr
  versetzt erhoben. Daneben je Jahrgang ein Balkenpaar aus vorgehaltenen und
  besetzten Stellen; verrechnet wird weiterhin nichts, weil beide Zahlen zu
  verschiedenen Zeitpunkten gehören. Der Tarif-Jahrgang 2026, den das PDF der
  Stadt nicht lesbar hergibt, bleibt als beschriftete Lücke sichtbar stehen.
  (#576)
- **22 Jahrgänge Bautätigkeit in einem Bild.** „Was wurde davon wirklich
  gebaut?" (`/haushalt/gebaut`) zeigte die zwei Rechnungswelten der Stadt
  bisher als zwei getrennte Diagramme — jetzt stehen alle Säulen von 2003 bis
  2025 nebeneinander, und der Systemwechsel 2009/2010 ist als gestrichelte
  Naht im Bild: links die kamerale, rechts die doppische Welt, jede in eigenen
  Farben, nichts wird über die Naht hinweg verrechnet. 2019 steht als
  beschriftete Lücke im Bild, weil die Quelltabelle sich dort selbst
  widerspricht. Jedes Jahr lässt sich zeigen, tippen oder mit den Pfeiltasten
  ablesen — nach allen Auszahlungsarten getrennt. (#576)
- **Ein Baukasten für alle Haushalts-Grafiken.** Bisher brachte jede Grafik
  des Haushalts-Bereichs ihre eigenen Bausteine mit; jetzt gibt es ein
  gemeinsames Fundament (`components/grafik/`), aus dem die kommenden
  Diagramme zusammengesetzt werden. Vier Teile stecken drin, weil sie überall
  gleich sein müssen: der Beleg-Chip an jeder Zahl, das Lücken-Feld („2019 —
  verworfen: 1,3 Mio. € Differenz im Dokument" — nie einklappbar), die
  Ableseleiste (zeigen, tippen oder Pfeiltasten; auf dem Telefon bleibt die
  Wertzeile jetzt beim Scrollen sichtbar) und die Einordnung — der Satz, der
  eine Zahl davor bewahrt, missverstanden zu werden, samt „Was diese Zahl
  nicht sagt". Die Geometrie rechnen ab jetzt vier kleine d3-Pakete, das
  Zeichnen bleibt eigenes SVG in unseren Farben. (#575)
- **Jede Haushaltszahl sagt jetzt auch, wer sie beschlossen hat.** Der kleine
  Beleg an einer Zahl nannte bisher das Dokument und die Stelle darin — „im
  Jahresabschluss 2024, Ergebnisrechnung der Kernverwaltung". Was fehlte, war
  der Schritt davor: Der Rat hat dieses Papier ja irgendwann beschlossen. Genau
  das steht nun daneben, mit Datum, Gremium und Vorlagennummer. Ausdrücklich
  auch dann, wenn noch **nichts** entschieden ist: Ein vertagter Vorgang ist
  keine Zahl ohne Beleg, sondern eine, bei der die Sache noch läuft — und das
  ist die interessantere Auskunft. Wo keine Vorlage im Bestand steht, bleibt
  die Zeile weg; ein erfundener Vorgang wäre der schlimmere Fehler. Das
  Ergebnis trägt keine Farbe, auch nicht bei „abgelehnt" — der Beleg-Apparat
  berichtet, er bewertet nicht. (#567)
- **Was wurde davon wirklich gebaut?** Der Haushalts-Bereich zeigte bisher nur
  die Bau- und Kaufpläne der Stadt — was am Jahresende tatsächlich abgeflossen
  ist, stand nirgends. Die neue Seite `/haushalt/gebaut` zeigt es für die Jahre
  2003 bis 2025, aufgeteilt danach, wofür das Geld ging: Baumaßnahmen,
  Grundstücke, Fahrzeuge und Geräte, Zuschüsse an Dritte. Zwei Dinge stehen
  dabei ausdrücklich dabei, weil die Zahl sonst mehr behauptet, als sie sagt.
  Erstens: Gezählt wird die Kernverwaltung — was der Eigenbetrieb
  Gebäudewirtschaft baut, und das ist seit 2010 ein großer Teil des
  städtischen Hochbaus, steht nicht darin. Zweitens: Für **2019 fehlt der
  Jahrgang**. Die Stadt weist dort eine Summe aus, die ihre eigenen
  Einzelposten um 1,3 Mio. € verfehlen, und welche Zahl danebenliegt, sagt die
  Tabelle nicht — also steht das Jahr gar nicht da statt in geschätzter Höhe.
  Bewusst **nicht** gezeigt wird eine „Umsetzungsquote" aus Plan und Ist:
  Beide Zahlen sind verschieden abgegrenzt, keine Veröffentlichung der Stadt
  stellt sie nebeneinander, und der Prozentsatz stünde in keinem Dokument.
  Die Seite verlinkt stattdessen den Investitionsplan und erklärt den
  Unterschied. Auch „Frag den Rat" kennt die neuen Zahlen — mit derselben
  Regel im Gepäck. (#566)
- **Der Haushalt sagt jetzt, welche Vorhaben hinter den Summen stehen.** „Was
  wird gebaut?" endete bisher bei „Verkehr und Straßenbau: 10,5 Mio. €" — und
  die Seite musste selbst zugeben, dass sie die naheliegende Anschlussfrage
  nicht beantwortet. Das Investitionsprogramm des Haushaltsplans führt jedes
  Vorhaben einzeln auf; es lag die ganze Zeit im eigenen Anlagenbestand. Statt
  „Kultur, Museen, Sport: 19,4 Mio. €" stehen dort jetzt das Post-SV-Gelände mit
  seiner Skatehalle, zwei Kunstrasenplätze und der Sportplatz am Schweriner Weg
  — 4.459 Vorhaben aus acht Haushaltsjahrgängen, durchsuchbar, und von der
  Summe je Bereich in beide Richtungen verlinkt. Angegeben sind die
  Gesamtkosten eines Vorhabens über alle Jahre; wie viel davon in welchem Jahr
  fließen soll, steht im Plan zwar daneben, ließ sich aus dem Dokument aber
  nicht verlässlich auslesen, und deshalb zeigen wir es nicht. Ein Befund gehört
  ausdrücklich dazu: **Schulgebäude stehen nicht darin.** Sanierung und Neubau
  verantwortet der Eigenbetrieb Gebäudewirtschaft und Hochbau mit einem eigenen
  Wirtschaftsplan — die Seite sagt das, statt eine Antwort anzudeuten, die sie
  nicht hat. (#565)
- **„Frag den Rat" kennt den Haushalt jetzt ganz — und beantwortet vier Fragen
  nicht mehr aus der falschen Quelle.** Der Haushalts-Bereich war auf dreizehn
  Datenschichten gewachsen, die KI-Frage kannte zehn davon. Die vier fehlenden
  wurden nicht etwa gar nicht beantwortet, sondern zum Teil falsch: „Wie viel
  Schulden hat Oldenburg?" bekam den Ergebnishaushalt — dabei sind Schulden
  ein Bestand am Stichtag und kommen dort überhaupt nicht vor. Investitions-
  fragen bekamen denselben Ergebnishaushalt, in dem keine einzige Investition
  steht (ein Schulneubau taucht dort nur als Abschreibung auf, verteilt über
  Jahrzehnte). Personalfragen bekamen Aufwendungen in Euro statt Stellen und
  Besetzungsgrad. Und „Wer wollte was am Haushalt ändern?" bekam nichts,
  obwohl 664 Änderungslisten im Bestand liegen. Jetzt zieht jede dieser Fragen
  ihre eigene Quelle — und nur die: Eine Schuldenfrage holt keinen Stellenplan
  mit. Jede Antwort bekommt dabei die Grenze mitgeliefert, ohne die die Zahl
  irreführt: bei den Schulden, was mitgezählt ist (Kernhaushalt und
  Eigenbetriebe, ohne die selbstständigen Beteiligungen); bei den
  Investitionen, dass Finanz- und Ergebnishaushalt zwei Zahlenwerke sind, die
  man nicht verrechnen darf; beim Stellenplan, dass sich die Besetzung auf das
  Vorjahr bezieht und „Stellen minus besetzt" zwei Stichtage mischt; und bei
  den Änderungslisten, dass die Ratsdaten sagen, **wer** etwas ändern wollte
  und ob es durchkam — nicht, was genau darin stand. Die „Gründliche
  Recherche" hing am alten Stand und bekommt jetzt denselben Kontext samt der
  Haushalts-Regeln, die ihr bislang ganz fehlten; umgekehrt zieht sie den
  Haushalt nicht mehr in jede Frage, die nur zufällig das Wort „Kosten" in
  ihren Suchbegriffen trug. (#563)
- **Ein Knopf, der die Finanzdaten sofort einliest, statt bis zu vierzehn Tage
  zu warten.** Der Haushalts-Bereich hält sich selbst aktuell, aber für einen
  frisch gebauten Parser ist der Zwei-Wochen-Takt die falsche Wartezeit: Die
  Seite steht, die Tabelle ist leer, und niemand sieht, ob der Parser auf dem
  echten Bestand trägt. Der neue Ops-Lauf zieht den Cron vor und meldet
  hinterher, wie viele Zeilen je Schicht dastehen — und ob eine davon ohne
  Herkunftsnachweis durchgerutscht ist. Er zielt bewusst nur auf die
  Dev-Umgebung. (#556)
- **„Der Streit ums Geld" — der Haushalt zeigt jetzt auch, worüber gestritten
  wurde.** Der Bereich führte bisher ausschließlich Zahlen: Plan, Ist,
  Produkte, Konzern, Prüfberichte. Dass über diese Zahlen politisch
  gerungen wurde, kam nicht vor — dabei ist ein Haushalt kein Rechenergebnis,
  sondern ein Kompromiss. Eine neue Seite zeigt je Haushaltsjahrgang 2019 bis
  2026 drei Dinge: welche Änderungslisten die Fraktionen und Gruppen einbrachten
  und wie darüber abgestimmt wurde (im Finanzausschuss und im Rat getrennt, weil
  dieselbe Liste dort verschieden ausgehen kann), die Wortbeiträge der Debatte
  im Wortlaut des Protokolls — 134 über alle Jahrgänge —, und wie am Ende über
  die Haushaltssatzung entschieden wurde. Die Fraktion einer Rednerin kommt aus
  der Anwesenheitsliste derselben Sitzung, nicht aus einer gepflegten Liste:
  Fraktionen wandern, wer 2023 für Die Linke sprach, saß 2025 für das BSW.
  Ratsgruppen bleiben Gruppen („FDP/Volt", „Für Oldenburg"), statt auf eine
  Partei zusammengezogen zu werden. Alle Beiträge stehen in der Reihenfolge des
  Protokolls und sind auf dieselbe Länge gekürzt — eine Auswahl „der wichtigsten
  Stellen" träfe sonst jemand. Was **nicht** dabei steht, sagt die Seite selbst:
  der Inhalt der Änderungslisten (er liegt in Anlagen-PDFs, die nicht als
  Volltext vorliegen), das Stimmverhalten Einzelner (das Ratsinformationssystem
  kennt keins) und die Fraktion bei Namensgleichheit im Rat — eine geratene wäre
  schlimmer als eine fehlende. (#558)
- **„Wie viel Schulden hat Oldenburg?" — dreißig Jahre Schuldenstand, mit der
  Angabe, was mitgezählt ist.** Eine der häufigsten Fragen an den Haushalt, und
  der Bereich konnte sie bisher nicht beantworten. Eine neue Seite zeigt die
  Zeitreihe seit 1995: Ende 2025 waren es 337,0 Mio. € oder 1.908 € je
  Einwohner\*in. Beides steht nebeneinander, weil es über dreißig Jahre in
  verschiedene Richtungen zeigt — insgesamt 35,5 Mio. € mehr als 1995, je
  Einwohner\*in 106 € weniger, denn die Stadt ist in derselben Zeit gewachsen.
  Direkt an der großen Zahl steht, **was** sie zählt: die Stadt als
  Rechtsträger, also mit ihren Eigenbetrieben und ohne die eigenständigen
  Gesellschaften. Bei Schulden ist das der Unterschied zwischen zwei Antworten,
  die beide „die Schulden der Stadt" heißen. Die zwei größten Sprünge der Reihe
  erklärt die Seite im Text, statt sie einer Farbe zu überlassen: 2001 fiel die
  Schuld um mehr als die Hälfte, weil die Stadtentwässerung samt Darlehen an
  einen Verband ging, und 2010 wechselten 108,9 Mio. € nur die Spalte, als die
  Stadt einen Eigenbetrieb gründete. Für 2022 fehlt die Aufteilung nach
  Schuldenarten — sie geht in der Quelle selbst nicht auf; die Gesamtschuld des
  Jahres steht trotzdem, weil sie sich gegen die Einwohnerzahlen der Stadt
  nachrechnen lässt. Quelle ist Tabelle 1108 des Statistischen Jahrbuchs. (#550)
- **„Wer macht die Arbeit?" — der Stellenplan im Haushalts-Bereich.** Personal
  ist der größte Ausgabenblock der Stadt, aber bisher zeigte der Bereich nur
  Euro und nicht, wie viele Menschen dahinterstehen. Eine neue Seite liest den
  Stellenplan aus, den der Rat mit jedem Haushalt beschließt: 2023 waren es 717
  Beamtenstellen, für 2026 sind es 815; dazu rund 1.700 Stellen für
  Tarifbeschäftigte. Die eigentliche Zahl steht daneben — **rund jede sechste
  bis fünfte Stelle war am Stichtag nicht besetzt** (18,1 % der Beamtenstellen
  zum 30. Juni 2025). Das erklärt eine Zeile, die im Jahresabschluss sonst wie
  ein Sparerfolg aussieht: Bleiben die Personalausgaben unter dem Plan, hat die
  Stadt das Geld nicht gespart, sondern die Leute nicht gefunden. Die Seite
  bewertet das nicht — sie sagt, was der Plan sagt, und wo seine Grenzen sind:
  Stellen sind keine Menschen, es ist nur die Kernverwaltung, und die Besetzung
  bezieht sich auf das Jahr vor dem Plan. Für 2026 fehlen die Tarifbeschäftigten
  und die Seite sagt auch das: Diese Seiten des PDFs geben keine Buchstaben aus,
  und geraten wird nicht. (#551)
- **„Was machen die eigentlich?" — die städtischen Gesellschaften einzeln.**
  Der Haushalts-Bereich zeigte bisher, wie viel Klinikum, Busse und Bäder
  bewegen, aber nicht, was sie tun. Eine neue Seite stellt jede städtische
  Gesellschaft vor: ihren Auftrag im Wortlaut, wem sie gehört, wer im
  Aufsichtsrat oder Betriebsausschuss sitzt, woran sie selbst beteiligt ist und
  was sie für den Haushalt bedeutet — dazu Jahresergebnis, Bilanzsumme und
  Eigenkapitalquote von 2017 bis 2024. Die Angaben stammen aus den
  Beteiligungsberichten der Stadt (§ 151 NKomVG), die ein neuer Cron seit jetzt
  selbst von oldenburg.de holt. Eine Kennzahl kommt nur in den Bestand, wenn
  der Bericht sie belegt: Die Bilanz muss aufgehen, die Gewinn- und
  Verlustrechnung dieselbe Zahl nennen, oder ein zweiter Bericht sie
  bestätigen — was keine Probe trägt, wird verworfen statt geschätzt. Die
  beschreibenden Abschnitte sind Text der Verwaltung und stehen ausdrücklich
  ungeprüft da. Was der Bericht **nicht** hergibt, steht als eigener Abschnitt
  auf der Seite: Er kommt zwei Jahre später, ein Jahresergebnis von 0 € heißt
  nicht „nichts verdient" (mehrere Betriebe führen ihr Ergebnis ab), und die
  Jahrgänge vor 2022 sind anders aufgebaut. (#555)
- **„Was wird gebaut?" — der Haushalts-Bereich zeigt jetzt auch die
  Investitionen.** Bisher stand dort ausschließlich der laufende Betrieb:
  Personal, Zuschüsse, Energie, Mieten. Neubauten, Fahrzeuge und Grundstücke
  haben einen eigenen Haushalt, und der kam schlicht nicht vor — ein Schulneubau
  tauchte nur als Abschreibung auf, verteilt über Jahrzehnte, lange nachdem
  gebaut wurde. Eine neue Seite zeigt für 2022 bis 2025, was die Stadt sich
  vorgenommen hat: 2025 sind das 80,8 Mio. € Auszahlungen, davon 39,7 Mio. €
  durch Zuschüsse, Verkäufe und Beiträge gedeckt — 9,5 % des gesamten
  Finanzhaushalts. Dazu, in welchen Bereichen das Geld liegt, und was
  zurückfließt. Übernommen wird ein Jahrgang nur, wenn die Rechnung der Datei
  aufgeht: Die Teilhaushalte müssen die Summenzeile ergeben, in beiden Spalten.
  Was diese Zahlen **nicht** sagen, steht als eigener Abschnitt auf der Seite —
  einzelne Vorhaben nennt die Quelle nicht („Verkehr und Straßenbau:
  10,5 Mio. €", nicht welche Straße), es sind Planzahlen, und sie enden 2025,
  weil die Stadt den Datensatz erst im Folgejahr veröffentlicht. (#547)
- **„Und ist das die ganze Stadt?" — der Haushalt zeigt jetzt auch, was neben
  ihm läuft.** Klinikum, Busse, Bäder und die städtischen Gebäude führen eigene
  Bücher; im Haushalt tauchen sie bestenfalls als Zuschusszeile auf. Eine neue
  Seite stellt beides nebeneinander: 2024 bewegt die Verwaltung 799 Mio. €, die
  Stadt mit allen Betrieben und Beteiligungen 1.242 Mio. € — der Haushalts-
  Bereich zeigte bis jetzt also rund zwei Drittel. Dazu über elf Jahre, wer wie
  viel beiträgt, und eine Erklärung, warum die Geschäfte der Betriebe
  untereinander wieder herausgerechnet werden. Die Zahlen stammen aus den
  geprüften Gesamtabschlüssen der Stadt; übernommen wird ein Jahrgang nur, wenn
  die Rechnungen des Dokuments aufgehen. Was der Vergleich **nicht** kann, steht
  als eigener Abschnitt auf der Seite: Ein Gesamtabschluss ist kein Haushalt,
  er kommt zwei Jahre später, und verrechnen lässt sich beides nicht. (#514)
- **Jede Haushalts-Zahl hält jetzt fest, woher sie stammt — auf den Abschnitt
  genau.** Bisher stand an einer gespeicherten Zahl bestenfalls eine URL, und
  bei einem 300-seitigen Jahresabschluss ist das zu wenig: Man sah nicht, an
  welcher Stelle des Dokuments sie steht und womit sie abgesichert ist. Zu
  jeder Zeile gehört jetzt ein Herkunfts-Eintrag mit dem Dokument, der
  Fundstelle darin („Abschnitt 6.3.1 — Erläuterungen zu den Abweichungen"),
  der bestandenen Rechenprobe samt Messwert („0,00 % Abweichung zur
  Gesamtrechnung") und dem Stichtag. Wo eine Quelle gar keine Rechenprobe
  mitbringt — die Steuer-Datensätze des Open-Data-Portals etwa —, steht das
  jetzt ausdrücklich da, statt offenzubleiben. Bestehende Zahlen ändern sich
  dadurch nicht; was der alte Bestand nicht festhielt, bleibt leer, statt
  geraten zu werden, und wird beim nächsten Einlesen nachgetragen. (#513)
- **Der Haushalts-Bereich hält sich ab jetzt selbst aktuell.** Bisher wurde
  jeder neue Jahrgang von Hand eingelesen — wer nicht daran dachte, ließ den
  ganzen Bereich still veralten. Ein neuer Job sieht alle zwei Wochen nach, ob
  für eine fehlende Jahreszahl inzwischen ein Dokument im
  Ratsinformationssystem liegt, und liest es ein: Jahresabschluss,
  Teilhaushalts-Pläne und die Berichte des Rechnungsprüfungsamts. Er richtet
  sich dabei nach dem Bestand, nicht nach dem Kalender — eine verspätete
  Veröffentlichung oder ein Nachtragshaushalt wird eingesammelt, sobald sie da
  ist. Bleibt ein erwarteter Jahrgang vier Wochen über seinen üblichen Monat
  hinaus aus, gibt es eine Nachricht statt eines stillen Stillstands — ebenso,
  wenn ein Dokument vorliegt, aber nicht gelesen werden kann. (#511)
- **Halbe Jahrgänge werden vollständig, sobald die Unterlagen da sind.** Die
  Zahlen eines Jahres kommen nicht auf einmal: Die Produktebene steckt in rund
  neun einzelnen Dokumenten, und die werden nacheinander lesbar. Wir tragen
  jetzt jedes Stück für sich nach, statt ein Jahr für erledigt zu halten,
  sobald das erste Dokument gelesen ist. Auf der Seite steht außerdem, wenn ein
  Jahrgang noch unvollständig ist („Für 2023 haben wir 6 von 9
  Teilhaushalten") — vorher sah ein halbes Jahr aus wie ein ganzes. (#511)
- **„Bis wann die Zahlen reichen" — der Datenstand steht jetzt auf der Seite.**
  Am Fuß von `/haushalt` steht, wie weit jede Datenschicht reicht und was als
  Nächstes erwartet wird: „Der Jahrgang 2025 wird üblicherweise im September
  2026 vorgelegt." Damit beantwortet sich die Frage „warum steht hier 2024 und
  nicht 2025?" an einer Stelle, statt auf neun Seiten einzeln. Der Grund liegt
  bei der Stadt: Den Plan legt sie im Herbst für das kommende Jahr vor, die
  Abrechnung erst ein knappes Jahr nach dessen Ende. (#511)

- **„Geplant und geworden" reicht jetzt bis 2017 — und sagt, warum.** Bisher
  waren fünf Jahrgänge zu sehen; 2017, 2018 und 2020 fehlten, weil ihre
  Tabellen im Jahresabschluss anders aufgebaut sind. Der Parser liest die
  Spalten jetzt aus dem Tabellenkopf statt aus einer festen Reihenfolge und
  schafft damit alle acht Jahrgänge; 2022 bekommt außerdem seine zwölf
  Teilhaushalte zurück. Neu ist auch das *Warum*: Zu jeder erheblichen
  Abweichung steht die Begründung der Verwaltung aus dem Jahresabschluss
  daneben — etwa, dass die Mehreinnahmen 2024 fast vollständig aus der
  Gewerbesteuer stammen und einen Einmaleffekt enthalten. Je Jahrgang gibt es
  dazu den Verweis auf den Schlussbericht des Rechnungsprüfungsamts. (#510)
- **Die Seite sagt jetzt, was „geplant" in einem Jahr bedeutet.** Das ist nicht
  überall dasselbe: 2020 vergleicht der Jahresabschluss mit dem Ansatz
  einschließlich Corona-Nachtrag, 2018 mit der Gesamtermächtigung. Bei den
  Ausgaben 2020 sind das 27 Mio. € Unterschied — also der Unterschied zwischen
  „21,5 Mio. weniger ausgegeben als geplant" und „5,7 Mio. mehr". Beide Werte
  stehen jetzt in der Datenbank, die Seite schreibt die Bezugsgröße an, und in
  der Mehrjahres-Kurve tragen die betroffenen Jahre eine Fußnote. (#510)
- **Das Flussbild: woher das Geld kommt, wohin es geht — und was dazwischen
  liegt.** Auf der Haushalts-Übersicht steht jetzt ein Bild, das links die
  Einnahmearten (Steuern, Zuwendungen, Gebühren …) und rechts die Bereiche
  zeigt. Dazwischen liegt ein einziger Knoten: die Stadtkasse. Kein Band führt
  von links nach rechts durch, und das ist der Punkt — im kommunalen Haushalt
  gehört keine Einnahme zu einer bestimmten Ausgabe, alles fließt erst
  zusammen und wird dann verteilt. Bandbreiten links und rechts liegen auf
  derselben Skala; ein Minus erscheint als eigenes Band „aus dem Ersparten",
  statt die kürzere Seite auf Länge zu ziehen. Kleine Posten sammeln sich in
  „weitere" und lassen sich aufklappen, alle Zahlen stehen unter „Zahlen
  anzeigen". Auf dem Handy werden daraus zwei Listen statt geschrumpfter
  Bänder. Für Jahre ohne Jahresabschluss sagt das Bild, welches Jahr es
  stattdessen zeigt — und wenn die Einzelposten die ausgewiesene Summe nicht
  tragen, erscheint gar keine Grafik, sondern der Hinweis darauf. (#505)
- **„Was kostet eigentlich …?" — der Haushalt, aufgeschlüsselt bis zur
  einzelnen Aufgabe.** Die häufigste Frage zum Haushalt ist keine nach
  Teilhaushalten, sondern nach einer konkreten Sache: dem Stadtarchiv, der
  Feuerwehr, dem Schwimmbad. Die neue Seite durchsucht 63 Aufgaben des
  Haushaltsjahres 2023 nach Name, Nummer, Amt und Beschreibung, filtert nach
  Amt und Spielraum und öffnet zu jeder einen Steckbrief: was sie kostet, was
  dahintersteckt, für wen sie da ist — und auf welchen Gesetzen sie beruht.
  Die Archivierung etwa kostet die Stadt 421 Tsd. € im Jahr und beruht unter
  anderem auf dem Bundesarchivgesetz und einem Vertrag mit dem Landesarchiv.
  Neu ist dabei vor allem die Selbstauskunft der Stadt, wie viel Spielraum sie
  bei einer Aufgabe überhaupt hat: Bei 35 der 63 Aufgaben ist es „kaum" — das
  macht aus einer Zahl eine Antwort darauf, worüber der Rat streiten kann und
  worüber nicht. Alle Angaben stammen wörtlich aus den Teilhaushaltsplänen;
  wo der Plan ein Feld leer lässt, steht auch bei uns nichts. (#504)
- **„Was das Rechnungsprüfungsamt beanstandet" — die Prüfung des Haushalts,
  zum ersten Mal lesbar.** Jeder Jahresabschluss der Stadt wird geprüft, und
  zwar von einer Stelle, die dem Rat berichtet und nicht der
  Verwaltungsspitze. Ihre Schlussberichte hängen als PDF an einer Ratsvorlage
  und werden dort nie wieder gelesen. Die neue Seite `/haushalt/pruefung`
  führt ihre 257 Feststellungen aus den Jahrgängen 2017–2023 einzeln auf — im
  Wortlaut, mit Textziffer, Seite und Deeplink ins Originaldokument. Die
  Randmarken des Berichts werden erklärt, nicht bewertet: Die große Mehrheit
  (166) sind Hinweise, 42 sind Beanstandungen, 37 wiederholte. Ein eigener
  Block zeigt, was über Jahre offen blieb — den Plan-Ist-Vergleich etwa
  beanstandet das Amt in allen sieben geprüften Jahren, zuletzt mit dem Satz
  „Dies widerspricht dem Grundsatz der Haushaltswahrheit". Wo die Verwaltung
  im Bericht direkt geantwortet hat, steht die Antwort daneben. Keine
  Bewertungsfarben, wie überall im Haushalts-Bereich. Für 2024 fehlt der
  Bericht: Sein PDF bringt keine Zeichenzuordnung mit, und eine zweite Kopie
  gibt es nicht — das steht auf der Seite, statt überspielt zu werden. (#509)
- **„Geplant und geworden" — was aus dem Haushalt wirklich wurde.** Ein
  Haushalt ist ein Plan; was am Jahresende zusammenkam, stand bisher nirgends.
  Die neue Seite stellt beides nebeneinander — für die Stadt insgesamt und für
  jeden Bereich einzeln. 2024 etwa nahm Oldenburg 799 Mio. € ein statt der
  geplanten 694, vor allem durch Steuern; aus einem geplanten Minus von 34
  Mio. wurde ein Überschuss von 35. Auf den Bereichsseiten steht die
  Entwicklung über alle abgeschlossenen Jahre. Farben bewerten dabei nichts:
  Mehr ausgegeben kann ein Tarifabschluss sein, weniger ausgegeben heißt oft,
  dass etwas nicht gebaut wurde. (#502)
- **„Steht Oldenburg besser da als Osnabrück?" — eine neue Seite beantwortet
  die Frage, so weit sie sich seriös beantworten lässt, und erklärt den Rest.**
  Bei der Steuerkraft geht es: Oldenburg liegt mit 1.974 € je Einwohnerin an
  der Spitze aller acht kreisfreien Städte Niedersachsens, vor Osnabrück
  (1.651), Braunschweig (1.518) und Delmenhorst (949). Dazu die Hebesätze — auf
  denselben Messbetrag zahlt man in Braunschweig 750 statt 539 Prozent — und
  die Steuereinnahmekraft über drei Jahre, an der sich zeigt, was eine hohe
  Gewerbesteuer kosten kann: In Wolfsburg fiel sie um 30 Prozent, während sie
  in Oldenburg um 22 Prozent stieg. Alle Zahlen kommen aus zwei Tabellen des
  Landesamts für Statistik, also für jede Gemeinde nach derselben Vorschrift
  gerechnet. **Ausgaben, Personal und Schulden je Einwohner stehen bewusst
  nicht dort**, und die Seite sagt auch, warum: Solche Zahlen messen zuerst,
  wie weit eine Stadt ausgelagert hat — in Oldenburgs Haushalt stehen rund 64
  Prozent dessen, was die Stadt insgesamt bewegt, in Osnabrücks knapp 48. Die
  Stadt Oldenburg hat diesen Vergleich 2018 auf Antrag der FDP-Fraktion selbst
  angestellt und im selben Dokument festgestellt, dass er nichts aussagt; die
  Seite zitiert sie wörtlich und verlinkt den Vorgang im Ratsinformationssystem.
  (#516)
- **Der abgelehnte Hebesatz-Vorschlag hat jetzt ein Bild.** Auf dem
  Steuer-Steckbrief der Gewerbesteuer stand bisher nur der Satz „Die Verwaltung
  schlug vor, die Hebesätze zu erhöhen. Der Rat lehnte ab." Daneben steht jetzt
  der geltende Hebesatz als Balken, und das Stück, das der Rat nicht beschlossen
  hat, hängt schraffiert hinten dran — mit der vorgeschlagenen Höhe aus § 5 der
  Haushaltssatzung und dem Überschlag, was es im Jahr gebracht hätte. Nennt die
  Satzung keinen abweichenden Satz, zeigt die Grafik keine Höhe und sagt das.
  (#710)
- **Gescannte Ratsunterlagen werden jetzt gelesen.** Rund 235 Anlagen im
  Ratsinformationssystem sind reine Scans — Bilder ohne Textebene, aus denen
  bisher nichts zu holen war. Darunter die Wirtschaftspläne des
  Abfallwirtschaftsbetriebs von 2019 bis 2021. Ein neuer Lauf schickt jede Seite
  an ein Sehmodell und legt den Text ab. Beim ersten Durchgang gingen 62 von 66
  Rechenproben auf den Cent auf; die vier übrigen wichen um genau einen Euro ab
  — ein zweites, unabhängiges Modell las dieselben Zahlen, der Rundungsfehler
  steht also im Dokument der Stadt. Der Text ist dabei bewusst **nicht** in die
  Suche aufgenommen: Ein Teil dieser Scans sind Förderanträge von Vereinen mit
  Namen, Anschriften und Unterschriften darauf. Sie liegen im Bürgerinfo zwar
  öffentlich, sollen durch uns aber nicht nebenbei durchsuchbar werden. (#669)
- **Was aus den Investitionen wird — und dass der Bestand trotzdem schrumpft.**
  Auf „Was gebaut wurde" steht jetzt neben dem, was die Stadt im Jahr zubaut,
  was im selben Jahr an Wert verloren geht. Beim Infrastrukturvermögen —
  Straßen, Brücken, Kanäle — kommen 2024 auf jeden zugebauten Euro 3,1 Euro
  Abschreibung. Allein die Straßen, Wege und Plätze sanken von 151,9 auf 133,3
  Millionen Euro; der Jahresabschluss nennt das selbst einen Substanzverlust.
  (#626)
- **Beschlüsse zeigen jetzt, wo sie im Haushalt wieder auftauchen.** Wer eine
  Nachbewilligung oder eine Bürgschaft aufschlägt, findet dort einen Weg zu der
  Stelle im Haushalts-Bereich, an der genau diese Entscheidung mitzählt. Der
  Verweis erscheint nur, wo eine echte Verknüpfung ihn deckt — nicht als Satz,
  der an jedem Beschluss gleich stünde. (#632)
- **Wer die städtischen Betriebe beaufsichtigt, steht jetzt mit seiner Funktion
  im Personenverzeichnis.** Die Aufsichtsorgane der städtischen Gesellschaften
  sind nicht nur Ratsmitglieder: In den Gemeinschaftsgesellschaften mit dem
  Landkreis sitzen Landrätin, Kreisrätin und Kreistagsmitglieder, in den
  Betrieben Beschäftigtenvertretungen, Betriebsräte und Vertretungen der
  Mitgesellschafter, Universität und Hochschule. 41 dieser Personen kamen in
  keiner Anwesenheitsliste des Stadtrats vor und standen deshalb namenlos da;
  sie tragen nun ihr Amt aus dem Beteiligungsbericht und die Berichtsjahrgänge,
  in denen sie vorkommen — mehr sagt die Quelle nicht, und mehr behaupten wir
  auch nicht. Keine Partei, kein Stimmverhalten, keine Gehälter. Zwei
  Ratsmitglieder finden dabei ihre Personen-Seite zurück: Der Bericht schreibt
  „Claudia Oeljeschleger" und „Jens Lükerman", das Verzeichnis kennt sie mit „ä"
  und mit zwei „n". Solche Druckfehler werden geheilt, wo der Bericht selbst
  „Ratsmitglied" sagt, der Vorname exakt stimmt und der Nachname um höchstens
  einen Buchstaben abweicht — und wo mehr als eine Person infrage kommt,
  ausdrücklich nicht. Umgekehrt führen sechs Namen im Beteiligungs-Steckbrief
  nicht mehr ins Leere: Verwaltungsleute haben keine Personen-Seite — auch der
  Oberbürgermeister nicht, der qua Amt in fast jedem Aufsichtsrat sitzt —, und
  ihre Namen wurden bis jetzt trotzdem verlinkt. (#588)
- **Was die Abfallgebühren tragen soll, steht jetzt im Bestand.** Neben dem
  Eigenbetrieb Gebäudewirtschaft liest der Haushalts-Bereich jetzt auch den
  Erfolgsplan des Abfallwirtschaftsbetriebs — den Plan also, aus dem die Stadt
  ihre Abfallgebühren kalkuliert: für 2026 rund 26,7 Millionen Euro Erträge und
  26,0 Millionen Euro Aufwendungen. Vier Jahrgänge (2023 bis 2026) sind gelesen
  und dreifach geprüft, unter anderem gegen einen Satz, den das Dokument unter
  seine eigene Tabelle setzt. Drei ältere Jahrgänge bleiben außen vor: Ihre
  Anlagen sind eingescannt und tragen keinen lesbaren Text — sie sind als solche
  vermerkt, falls sich das später ändern lässt. (#666)
- **Der Bäderbetrieb erklärt jetzt seine Null — und zeigt, was wirklich im Plan
  steht.** Auf „Der Haushalt neben dem Haushalt" stand bei ihm in jedem Jahrgang
  ein Jahresergebnis von 0,0 Mio. €, daneben zwei Striche und sonst nichts. Die
  Null stimmt: Alle sieben Beschlusstexte schreiben wörtlich „schließt mit einem
  geplanten Jahresfehlbetrag in Höhe von 0,00 EUR ab" — der Betrieb hat seit
  2005 kein operatives Geschäft mehr, sondern verpachtet sein Vermögen an die
  Bäderbetriebsgesellschaft, und die Pacht ist so angesetzt, dass sie die Kosten
  genau deckt. Nur sah man der Karte nicht an, dass das Absicht ist und keine
  fehlende Zahl. Jetzt steht der Satz dabei — und darunter die Summe, um die es
  in diesem Plan tatsächlich geht: 10,8 Mio. € Investitionen im Vermögensplan
  2026. Übernommen wird sie nur, wenn der Beschlusstext seine eigene Rechnung
  erfüllt (Kreditaufnahme plus eigene Mittel ergeben die Summe) — und
  ausdrücklich nicht aus Anpassungs-Vorlagen, die den *ursprünglichen* Plan
  zitieren, bevor sie ihn ändern. (#692)
- **Beschlüsse lassen sich nach ihrem Ortsbezug filtern.** Die Beschluss-Suche
  lässt sich nach dem geokodierten Oldenburger Ortsbereich eines Ortsbezugs
  filtern. Gefilterte Treffer zeigen den konkreten Ort und die zugrunde liegende
  Fundstelle, damit die Zuordnung direkt prüfbar ist. (#769)
- **Wer die städtischen Gesellschaften beaufsichtigt — und wem sie gehören.**
  Die Steckbriefe unter „Beteiligungen" kippten bisher fünf Rohtext-Abschnitte
  am Stück aus; zwei davon waren in Wahrheit Tabellen. Aufsichtsräte und
  Betriebsausschüsse stehen jetzt Person für Person da, mit Gremium, Vorsitz,
  Amtszeit und — wo das Personenverzeichnis die Person eindeutig kennt — einem
  Link auf ihre Seite. Daneben die Eigentümer mit Anteil in Euro und Prozent.
  Ein Amt steht nur dort, wo der Bericht es nachweislich der richtigen Person
  zuordnet: Führt er mehr Namen als Ämter, bleiben die Ämter dieser Gesellschaft
  leer, statt einer echten Person das falsche anzuhängen. (#587)
- **Beteiligungen als Konzernkarte, Prüfung als Wiederholungs-Matrix.** Die
  Konzernkarte zeigt, wer zur Stadt gehört und in welcher Rechtsform; die
  Gesellschafts-Karten tragen Kennzahl-Zeitreihen 2017–2024. Die Prüfungs-Seite
  zeigt, welche Feststellungen des Rechnungsprüfungsamts sich über Jahre
  wiederholen — 37 von 257, als Ketten sichtbar. (#581)
- **Wie viel einer Gesellschaft der Stadt gehört, steht jetzt dabei.** Auf der
  Konzernkarte und an jeder Gesellschafts-Karte erscheint der Anteil der Stadt
  Oldenburg — 100 % beim Klinikum, 74 % bei der VWG, 34,5 % bei der GSG. Wo die
  Stadt weniger als die Hälfte hält, trägt das Formzeichen einen offenen Ring.
  Nennt der Bericht für eine Einheit keine Anteilseigner, steht dort auch keine
  Zahl. (#595)
- **Die größte Verpflichtung der Stadt ist kein Kredit.** Die Schuldenseite
  zeigte bisher nur, was Oldenburg an Krediten aufgenommen hat — 43,7 Mio. € zum
  Jahresende 2024, wenig für eine Stadt dieser Größe. Die naheliegende
  Anschlussfrage („dann hat sie ja keine Schulden?") beantwortet erst die
  Bilanz, und die Antwort steht jetzt unter der Kurve: 311,8 Mio. € hat die
  Stadt für Pensionen und Beihilfe ihrer Beamt*innen zurückgestellt, das
  Siebenfache der Kredite. Das ist kein Missstand — genau dafür bildet man
  Rückstellungen —, es ist nur der größere Posten. Dazu die Bilanz als Ganzes:
  1.480,0 Mio. € zum 31.12.2024, aufgeteilt in „worin das Vermögen steckt" und
  „wem es zusteht". Neun Stichtage, 2016 bis 2024. Wo zwei Zahlen kursieren, die
  beide „die Pensionsrückstellungen" heißen, steht jetzt dabei, welche welche
  ist: 266,3 Mio. € sind die Pensionen allein, 45,5 Mio. € die Beihilfe,
  zusammen die 311,8. Und wo die Bilanz 2024 plötzlich 207,1 statt 84,4 Mio. €
  Schulden ausweist, steht der Grund im Wortlaut der Verwaltung daneben — eine
  Buchungsumstellung beim Cash-Pooling, keine neuen Schulden. (#602)
- **Wofür die Stadt geradesteht — neben dem, was sie schuldet.** Auf der
  Schulden-Seite steht jetzt der Bürgschaftsbestand aus den Jahresabschlüssen:
  Ende 2024 waren es 220,3 Millionen Euro, das Fünffache der eigenen Schulden
  von 43,7 Millionen. Eine Bürgschaft ist keine Schuld — die Stadt zahlt nur,
  wenn die verbürgte Gesellschaft es nicht kann; für diesen Fall stehen 1,3
  Millionen in der Bilanz. Der Sprung 2022 steht mit der Begründung der Stadt
  dabei: die Übernahme von Bürgschaften für das Klinikum über 135,9 Millionen
  Euro. Sechs Jahrgänge, jeder mit der Angabe, wie genau die Quelle ihn belegt.
  (#619)
- **Was der Rat zu den Bürgschaften beschlossen hat, jetzt als Liste.** Unter
  den Schulden steht die Chronologie der 21 Vorlagen — mit einem Vermerk an
  denen, die eine bestehende Bürgschaft nur verlängern oder anpassen. Bewusst
  ohne Beträge und ohne Summe: Diese Beschlüsse schreiben einander fort, statt
  sich zu addieren. (#632)
- **Warum man über Oldenburgs Schulden drei Zahlen hört — und alle drei
  stimmen.** 43,7 Millionen sind die Investitionskredite der Verwaltung selbst,
  294,9 Millionen die Stadt mit ihren Eigenbetrieben, 740,3 Millionen der ganze
  „Konzern Stadt" samt Beteiligungen. Die Schulden-Seite stellt sie jetzt
  nebeneinander und sagt zu jeder, was sie mitzählt. Bei der größten steht
  dabei, dass 59 Prozent davon aus Unternehmen stammen, an denen die Stadt
  weniger als die Hälfte hält — für deren Schulden haftet sie nicht. Und dass
  daraus keine Zeitreihe werden darf, weil sich der Kreis der mitgerechneten
  Unternehmen von Ausgabe zu Ausgabe ändert. (#619)
- **Woher das Geld im laufenden Haushaltsjahr kommen soll.** Für Jahre ohne
  Jahresabschluss ließ sich der Geldfluss bisher nicht zeigen — dort stand nur
  der Hinweis, dass ein vollständiges Bild fehlt. Jetzt steht dort die eine
  Seite, die es gibt: die Ertragsarten des Haushaltsplans als Rangliste, von den
  Steuern bis zu den Eigenleistungen. Sie gibt sich ausdrücklich als halbes Bild
  zu erkennen — die Ausgabenseite steht im Plan in einer anderen Rechnung, und
  ein Bild aus beiden würde zwei Stände vermischen. Dazu nennt der Block den
  Abstand zur Kernzahl oben auf derselben Seite und wo er herkommt: Die
  Rangliste zeigt den Entwurf der Verwaltung, die Anzeigetafel den beschlossenen
  Plan. (#662)
- **Neben dem Jahresergebnis steht jetzt, was wirklich geflossen ist.** Für 2024
  wies der Jahresabschluss einen Überschuss aus — und im selben Heft, dreißig
  Seiten weiter, 22,4 Mio. € weniger Geld in der Kasse als am Jahresanfang.
  Beides stimmt: Abschreibungen mindern das Ergebnis, ohne dass jemand etwas
  überweist, und ein Neubau kostet sofort Geld, im Ergebnis aber erst über die
  Jahre. Bisher zeigte „Geplant und geworden" nur die erste Zahl. Jetzt steht
  die Finanzrechnung der Kernverwaltung daneben, mit der Rechnung, die das
  Dokument selbst führt: was aus laufender Arbeit übrig blieb, was für
  Investitionen abfloss, was am Ende in der Kasse lag. Dazu die Ermächtigungen
  aus Vorjahren — 2024 waren das 58,8 Mio. € bewilligtes Geld für Vorhaben, die
  noch nicht fertig sind, und damit die Antwort auf die Frage, warum das
  Geplante nicht gebaut wird. Acht Jahrgänge, 2017 bis 2024; jede Zahl hängt an
  der Rechenkaskade, die die Tabelle selbst vorrechnet. (#600)
- **Neue Seite: Was Sie dafür zahlen.** Sie zeigt, wie die Abfall- und
  Straßenreinigungsgebühren zustande kommen — nicht nur das Ergebnis, sondern
  die ganze Rechnung: was der Bereich kostet, was davon Dritte tragen oder aus
  Vorjahren ausgeglichen wird, und was übrig bleibt, geteilt durch die
  Abfallmenge beziehungsweise die gebührenpflichtige Fläche. Dazu der Verlauf
  der letzten Jahre. Bei der Abfallsammlung steht ausdrücklich, dass es dort
  keine einzelne Gebühr gibt — sie wird über eine Grundgebühr und eine Gebühr je
  Liter abgerechnet. (#683)
- **Der Steckbrief „Gebühren und Beiträge" zeigt jetzt Zahlen.** Er sagte
  bisher, keiner der offenen Datensätze führe diese Einnahme — und das stimmte
  auch, für die Steuerreihen. Der Jahresabschluss führt sie sehr wohl: 25,9 Mio.
  € waren es 2024, gut 3 % aller ordentlichen Erträge. Dazu die Reihe seit 2017,
  in der man die Corona-Jahre sieht (2021 blieben fast 3 Mio. € hinter dem
  Ansatz), der Vergleich von Ansatz und Ergebnis je Jahr — und die
  Aufschlüsselung nach Bereichen, die die eigentliche Frage beantwortet: Wofür
  zahlen die Leute? Das meiste kommt aus Sicherheit und Ordnung (7,5 Mio. €),
  aus Verkehr und Straßenbau (6,0 Mio. €) und aus Jugend und Familie (5,9 Mio.
  €, dort stecken die Kita-Beiträge). Die Müllgebühr steht ausdrücklich
  **nicht** darin: Sie läuft über den Abfallwirtschaftsbetrieb, und den zählt
  der Abschluss der Kernverwaltung nicht mit — wo ihre Rechnung steht, sagt die
  Seite jetzt auch. Auf der Übersicht „Woher das Geld kommt" trug dieselbe Karte
  bis dahin „Betrag noch nicht eingelesen"; sie zeigt die Zahl nun ebenfalls.
  (#712)
- **Warum die Müllabfuhr kostet, was sie kostet.** Jedes Jahr legt der
  Abfallwirtschaftsbetrieb dem Rat vor, wie die Abfall- und
  Straßenreinigungsgebühren zustande kommen: was der Bereich insgesamt kostet,
  was davon Dritte tragen, was aus Vorjahren ausgeglichen wird — und was übrig
  bleibt, geteilt durch die Abfallmenge beziehungsweise die gebührenpflichtige
  Fläche. Vier Jahrgänge stehen jetzt im Bestand, jede Zahl doppelt
  nachgerechnet. Man sieht darin zum Beispiel, dass die Gebühr je Tonne Abfall
  von 123 € (2023) auf 151 € (2026) gestiegen ist — und woraus dieser Anstieg
  besteht. (#683)
- **Wo ein Gesetz genannt wird, führt jetzt ein Weg hin.** Auf den
  Steuer-Steckbriefen steht neben jeder Rechtsgrundlage ein kleines
  Waage-Zeichen. Ein Klick erklärt in zwei Sätzen, was dort geregelt ist — beim
  Hebesatz etwa, dass die Stadt ihn beschließen darf, aber für alle Betriebe
  gleich —, und führt von dort zum amtlichen Volltext: Bundesrecht beim
  Bundesamt für Justiz, Landesrecht im niedersächsischen
  Vorschrifteninformationssystem. Dabei steht auch, welche Ebene das Gesetz
  gemacht hat, denn davon hängt ab, wer es ändern könnte. (#736)
- **Wie viele Betriebe die Gewerbesteuer aufbringen, steht jetzt da.** Der Block
  „Wer zahlt das eigentlich" auf dem Steuer-Steckbrief erklärte bisher nur,
  warum niemand Namen nennen darf. Die Anschlussfrage beantwortet er jetzt mit
  Zahlen des Landesamts für Statistik: 8.421 Betriebe und Betriebsstätten sind
  in Oldenburg erfasst, 3.642 von ihnen zahlen überhaupt Gewerbesteuer — und 53
  % der Bemessungsgrundlage kommen von 879 Betriebsstätten größerer Firmen, die
  ihre Steuer nach Arbeitslöhnen auf mehrere Gemeinden aufteilen. Dass diese
  Statistik die Veranlagung zeigt und nicht das Geld in der Kasse, und dass sie
  rund fünf Jahre nachhinkt, steht ausdrücklich daneben. (#732)
- **Siebzehn neue Erklärungen im Glossar.** Bilanzsumme, Nettoposition,
  Sonderposten, Abschreibung, Buchwert, Bürgschaft, Rückstellung,
  Eigenkapitalquote und weitere Begriffe aus den Jahresabschlüssen erklären sich
  jetzt dort, wo sie stehen — mit Oldenburger Zahlen statt Lehrbuchsätzen.
  (#628)
- **Die KI-Antwort zeigt jetzt Diagramme.** Wer nach den Schulden oder einer
  Steuer fragt, bekommt unter der Antwort die Zeitreihe dazu — dieselbe Grafik
  wie im Haushalts-Bereich, mit Ableseleiste und aufklappbarer Werte-Tabelle.
  Die Reihe kommt aus unserer Datenbank, nicht aus der KI-Antwort: Das Modell
  kann sie weder erfinden noch verfälschen. (#635)
- **Fünf Wirtschaftspläne mehr, drei davon aus Scans.** Die Pläne des
  Abfallwirtschaftsbetriebs für 2019, 2020 und 2021 lagen im
  Ratsinformationssystem nur als Bild vor und fehlten deshalb. Sie sind jetzt
  gelesen und geprüft — in jedem der drei Jahrgänge geht die Rechnung in allen
  sechs Spalten auf den Cent auf. Dazu kommt der **Eigenbetrieb Hafen** mit
  seinen beiden einzigen Jahrgängen 2019 und 2020; mehr gibt es nicht, weil der
  Betrieb danach aufgelöst wurde. Beide Zahlen stehen im Beschlusstext *und* in
  der beigefügten Anlage. (#671)
- **Der Haushalt neben dem Haushalt.** Der Rat beschließt nicht nur den
  Stadthaushalt — daneben stehen die Wirtschaftspläne der Eigenbetriebe und
  städtischen Gesellschaften, in denselben Sitzungen entschieden. Die neue Seite
  *Stadtfinanzen → Der Haushalt neben dem Haushalt* zeigt sie erstmals: sechs
  Betriebe, 29 Jahrgänge von 2019 bis 2026, jede Zahl mit der Vorlage belegt,
  aus der sie stammt. Wo eine Quelle nur das Ergebnis nennt und keine Erträge,
  steht ein Strich mit dem Grund — keine Null, die es nicht gibt. Und bewusst
  keine Gesamtsumme: Der Eigenbetrieb Gebäudewirtschaft vermietet der Stadt ihre
  eigenen Gebäude, wer beides addiert, zählt dasselbe Geld zweimal. (#668)
- **Jede Haushalts-Schrittseite hat jetzt eine Bühne.** Elf der zwölf Schritte
  beginnen mit einer hellen Kopf-Fläche, auf der die eine gemessene Zahl der
  Seite groß steht — „Bei N von M Einnahmequellen kann der Rat wirklich drehen",
  „geplant 727,9 — geworden 764,4", „257 Feststellungen aus sieben Jahren" —
  daneben die verkleinerte Hauptform der Seite (Waffel, Treppe, Städte-Leiter
  …), die per Klick dorthin springt. Die Zahl zählt beim ersten Sichtkontakt
  hoch; wer Bewegung reduziert hat, sieht sofort den Endwert. Fehlt eine
  Datengrundlage, entfällt die Bühne, statt etwas zu behaupten. Das Labor bleibt
  bewusst ohne: Es ist Werkzeug, sein Kopf ist der eigene Regler-Stand. Auch der
  Steuer-Steckbrief trägt die Bühne — mit dem Hebesatz und seiner Treppe, wo
  eine Reihe vorliegt. Die Einstiegstexte stehen jetzt unter der Bühne, eine
  Stufe kleiner. **Die Zeichen-Kachel im Seitenkopf ist dem Schritt-Pfad
  gewichen.** Oben rechts stehen statt des großen Icons zwölf Punkte in den vier
  Etappen-Gruppen des Wegweisers: besuchte Schritte gefüllt, der aktuelle als
  Ring — derselbe lokale Lesestand, den der Wegweiser führt, und ein Klick führt
  zu ihm. (#749)
- **Der Rahmen um den Haushalt wird jetzt gelesen.** Die Haushaltssatzung legt
  jedes Jahr fest, wie viel die Stadt sich für Investitionen leihen darf, wie
  hoch ihr Dispo sein darf und welche Verpflichtungen sie für kommende Jahre
  eingehen darf. Drei Seiten je Jahrgang, die bisher niemand ausgewertet hat.
  Sieben Jahrgänge von 2019 bis 2026 stehen jetzt im Bestand, jeder an der
  eigenen Summenzeile der Satzung nachgerechnet. Zwei Befunde daraus: Die Stadt
  veranschlagt in keinem einzigen Jahr Investitionskredite — und ihr
  Dispo-Höchstbetrag ist von 60 auf 100 Millionen Euro gewachsen. Wichtig dabei:
  Im Ratsinformationssystem liegen ausschließlich Entwürfe der Verwaltung; die
  beschlossene Fassung erscheint im Amtsblatt. Jede Zahl ist entsprechend
  gekennzeichnet. (#674)
- **Die dreizehn Zahlen, auf die die Stadt ihren Abschluss selbst eindampft —
  und sieben stille Korrekturen.** Am Ende jedes Rechenschaftsberichts steht
  eine Anlage mit dreizehn Kennzahlen und, darunter, den Rechenwegen im
  Wortlaut. Die neue Seite zeigt beides für 2015 bis 2024. Weil jeder Bericht
  fünf Jahre druckt, stehen dieselben Jahrgänge mehrfach da — meistens mit
  derselben Zahl, an sieben Stellen aber nicht: Die Steuerquote 2021 war erst
  45,90 %, dann 49,05 %, dann wieder 45,92 %. Angesagt wurde das nirgends.
  (#627)
- **Die KI-Frage kennt jetzt auch Bilanz, Kassensicht, Nachbewilligungen und
  Kennzahlen.** Fragen nach dem Vermögen der Stadt, nach dem, was tatsächlich
  geflossen ist, nach nachträglich bewilligtem Geld oder nach der
  Eigenkapitalquote wurden bisher aus dem Haushaltsplan beantwortet — dort kommt
  nichts davon vor. Bei den Kennzahlen zitiert die Antwort den Rechenweg, den
  die Stadt danebendruckt, statt selbst eine Quote zu bilden. (#630)
- **Das Haushalts-Labor hat jetzt drei Werkbänke.** Aus zwei Reglern werden drei
  Arbeitsflächen mit je eigener Zielgröße: Bei den **Einnahmen** laufen beim
  Drehen am Gewerbesteuer-Hebesatz die kreisfreien Städte als Leiter mit, dazu
  kommen die eigene Hebesatz-Treppe seit 1980, der lange fehlende
  Grundsteuer-B-Regler (mit belegter Aufteilung aus dem Realsteuervergleich des
  Landes), die Hundesteuer als Größenordnungs-Probe und die Gebühren als
  absichtlich gesperrte Schraube. Die **Ausgaben**-Werkbank führt die
  freiwilligen Teilhaushalte weiter. Neu ist **Investitionen & Finanzierung**:
  einzelne Vorhaben aus dem Investitionsprogramm abwählen und sehen, warum das
  die Ergebnis-Lücke kaum bewegt — plus ein Kredit-Schalter, der mit den
  tatsächlich gezahlten Zinssätzen rechnet statt mit einer Annahme. Im Ergebnis
  zeigt eine Kurve über die Finanzplanungsjahre, in welchem Jahr die Rücklage
  rechnerisch kippt und wie das eigene Szenario den Punkt verschiebt; der
  Finanzausgleich steht als Spanne aus den echten Ausgleichsjahren daneben.
  (#721)
- **So viel gibt die Stadt aus — seit 1972.** Die Übersicht des
  Haushalts-Bereichs zeigt jetzt 54 Jahrgänge in einem Bild: bis 2009 die
  Ausgaben des Verwaltungshaushalts, ab 2010 die ordentlichen Aufwendungen des
  Ergebnishaushalts. Der Wechsel des Rechnungswesens zum 1. Januar 2010 steht
  als sichtbare Naht zwischen zwei Farbwelten im Bild — über sie hinweg wird
  keine Linie gezogen und nichts verrechnet, weil links und rechts etwas anderes
  gezählt wird. Die Beträge stehen in Euro des jeweiligen Jahres, die Teuerung
  ist nicht herausgerechnet; einen Betrag je Einwohner*in zeigt die Reihe
  bewusst nicht, weil die Einwohnerzahl zweimal durch einen Zensus springt.
  Nebenbei beantwortet die Reihe die Frage nach dem gerade abgelaufenen Jahr:
  Seine Gesamtsumme steht dort Monate, bevor der Jahresabschluss vorliegt. Für
  2021 nennen die beiden Veröffentlichungen der Stadt verschiedene Beträge —
  statt das still zu glätten, nennt die Seite beide Zahlen und sagt, welche der
  Jahresabschluss bestätigt. (#604)
- **Sitzungen, Tagesordnungspunkte und Beschlüsse lassen sich jetzt persönlich
  merken.** Die neue Merkliste bündelt offene und bereits entschiedene Punkte.
  Für einen noch offenen öffentlichen TOP kann zusätzlich eine Benachrichtigung
  eingeschaltet werden: Sobald ein Protokoll vorliegt, verknüpft Ratslotse den
  gemerkten TOP mit dem erkannten Beschluss und meldet das Ergebnis. Die
  Zuordnung bleibt auch erhalten, wenn sich die TOP-Nummer vor der Sitzung noch
  verschiebt. (#762)
- **Was beschlossen wurde, nachdem der Haushalt beschlossen war.** Ein Haushalt
  ist ein Plan — und wenn das Geld nicht reicht, braucht jede zusätzliche
  Ausgabe eine eigene Bewilligung (§ 117 NKomVG). Seit 2018 sind das 161
  Vorlagen, und auf *Geplant und geworden* stehen sie jetzt: mit Betrag, mit
  Jahr und mit einem Link auf ihre Beschluss-Seite. „Außerplanmäßig" heißt dabei
  nicht ungedeckt, sondern umgewidmet — jede dieser Vorlagen nennt, aus welchem
  anderen Posten das Geld kommt. Wichtiger als die Liste ist aber, was daneben
  steht. Der Rat ist nämlich nicht der einzige Weg: Der Rechenschaftsbericht der
  Stadt zählt vier — Ratsbeschluss, Entscheidung des Oberbürgermeisters,
  Haushaltsvermerk des Fachdienstes 200 und Eilentscheidung. Zusammen waren das
  2022 rund 26,7 Millionen Euro, 2024 schon 57,5. Der Anteil, über den der Rat
  selbst abgestimmt hat, ist im selben Zeitraum von 89 auf 73 Prozent gefallen.
  Wer nur die Ratsbeschlüsse zeigte, zeigte eine schrumpfende Teilmenge, als
  wäre sie das Ganze — deshalb steht die Gesamtsumme oben und die Liste
  darunter. Zwei der drei Berichte widersprechen sich dabei selbst: 2022 nennt
  der Fließtext 288.000 Euro mehr als seine eigene Tabelle, 2023 steht in einer
  Zeile eine Anzahl von null und trotzdem ein Betrag. Beides zeigen wir an,
  statt es glattzurechnen. Und wo unsere Zahl von der des Berichts abweicht,
  sagen wir warum: Wir nennen den Betrag, den die Vorlage beantragt hat, der
  Bericht den, der am Ende gebucht wurde. (#609)
- **Eine Übersicht, welche Zahlen es über Oldenburgs Finanzen noch gibt.** Die
  Technik-Doku hält jetzt fest, welche amtlichen Quellen wir auswerten, welche
  wir kennen und noch nicht nutzen — und welche wir geprüft und verworfen haben,
  mit Begründung. Für Leser*innen ändert sich nichts; für alle, die mitbauen
  wollen, steht dort, wo die Zahlen herkommen. (#598)
- **Drei neue Quizfragen aus dem Jahresabschluss.** Wie hoch die Schulden der
  Stadt sind (Antwort: alle drei genannten Zahlen, je nachdem was mitgezählt
  wird), für wie viele Millionen Euro sie bei Krediten ihrer Gesellschaften
  geradesteht, und wie viel Wert sich ihr Sachvermögen im Jahr abnutzt,
  verglichen mit dem, was neu dazukommt. (#631)
- **Auf der Schulden-Seite steht jetzt auch, was die Stadt aufnehmen dürfte.**
  Bisher zeigte sie nur, was die Stadt schuldet. Der neue Block darunter nennt
  die drei Grenzen aus der Haushaltssatzung: wie viel für Investitionen geliehen
  werden darf, wie hoch der Dispo sein darf und was in diesem Jahr bestellt
  werden darf, obwohl die Rechnung später kommt. Für das kommende Jahr steht bei
  den Investitionskrediten „nicht veranschlagt" — und zwar so und nicht als „0
  €", weil die Satzung genau diesen Satz schreibt. Der Block sagt außerdem dazu,
  dass es sich um den Entwurf der Verwaltung handelt und nicht um den
  Ratsbeschluss. (#676)
- - „Frag den Rat“ lässt das bestehende Frage-Analysemodell nun zusätzlich einen
  strukturierten Rechercheplan für Beschlüsse, Debatten, Haushalt, Presse,
  Sitzungen, kommende Beratungen, Orte und Dokumente entwerfen. Der Plan läuft
  zunächst im Shadow-Mode: Er verändert keine Antwort, wird aber zusammen mit
  anonymisierten Trefferzahlen protokolliert. Explizite Personen-, Orts-, Geld-
  und Sitzungsbezüge bleiben dabei verpflichtende deterministische Kanäle.
  (#793)
- **Gescannte Ratsunterlagen sind jetzt auch durchsuchbar.** Rund 230 Anlagen
  liegen im Ratsinformationssystem nur als Bild vor. Ihr per Texterkennung
  gelesener Inhalt steht nicht mehr nur in der Datenbank, sondern wird wie jeder
  andere Anlagentext gefunden — vom Wirtschaftsplan des
  Abfallwirtschaftsbetriebs bis zum Prüfbericht des Rechnungsprüfungsamts.
  (#679)
- **Änderungs-Meldungen einzeln abschaltbar.** Wer die Tagesordnung seiner
  Gremien bekommen, aber nicht über jede spätere Änderung informiert werden
  will, schaltet unter „Mein Konto" nur noch die neuen Änderungs-Meldungen ab.
  Der Schalter hängt an „Tagesordnung in meinen Gremien" und ist ohne ihn
  wirkungslos. (#747)
- **Von jedem Schritt direkt zum nächsten.** Am Fuß jeder der sechzehn
  Haushalts-Seiten steht jetzt, wo man im Weg ist („Schritt 5 von 16") und wohin
  es weitergeht — vorher führte der einzige Weg zum nächsten Schritt zurück über
  die Übersicht. Der letzte Schritt verabschiedet mit „Geschafft". Die
  Reihenfolge kommt aus derselben Quelle wie der Wegweiser selbst; die beiden
  Steckbriefe ohne eigenen Schritt bleiben bewusst ohne die Zeile. (#583)
- - Interne Schnittstelle für den Social-Media-Bot: liefert die Wochenvorschau
  neutral (ohne Konto-Bezug) und nimmt die gerenderten Karten entgegen, damit
  Instagram sie abholen kann. Ohne `SOCIAL_API_TOKEN` ist sie abgeschaltet.
  (#645)
- **Was Menschen und Firmen der Stadt schenken, steht jetzt unter den
  Einnahmen.** Acht- bis zwölfmal im Jahr beschließen Rat oder
  Verwaltungsausschuss, welche angebotenen Zuwendungen die Stadt annimmt —
  lückenlos seit Februar 2018, zuletzt 788.669 Euro im Jahr 2025. Diese Reihe
  weist sonst niemand aus: Weder die Ergebnisrechnung noch der Haushaltsplan
  führen Spenden getrennt. Aufgenommen ist nur, was in der Vorlage ein zweites
  Mal steht, im Abschnitt zu den finanziellen Auswirkungen — entweder als
  dieselbe Zahl oder zerlegt in Geld- und Sachzuwendungen, die sich auf den Cent
  aufaddieren müssen. 148 Vorlagen tragen diese Probe; sechs Beschlusszeilen
  tragen sie nicht und stehen mit dem Satz dabei, warum, statt ungeprüft
  mitgezählt zu werden. Bei einer davon hat der Rat die vorgeschlagene Liste
  geändert — er nahm 2.500 statt 22.500 Euro an, „ohne lfd. Nr. 2". Nebenbei
  erklärt der Block, wie Zuständigkeit funktioniert: Über eine einzelne
  Zuwendung bis 100 Euro entscheidet die Verwaltungsspitze allein, bis 2.000
  Euro der Verwaltungsausschuss, darüber der Rat. Beide Gremien behandeln
  ungefähr gleich viele Vorlagen — 80 der Rat, 68 der Verwaltungsausschuss —,
  aber 95 Prozent des Geldes laufen über den Rat. **Wer gespendet hat, zeigen
  wir nicht.** Die Namen stehen ausschließlich in der Anlage „Zuwendungsliste"
  zur jeweiligen Vorlage, und die lesen wir nicht ein. Der Ratsbeschluss macht
  die Summe öffentlich; die Liste dahinter bleibt es nicht, und dabei bleibt es
  auch hier. (#610)
- **Die Statistik der Stadt wird täglich gesichert, bevor sie verschwindet.**
  Die Stadt führt kein Archiv ihres Statistischen Jahrbuchs: Online steht immer
  nur die neueste Ausgabe jeder Tabelle, die vorherige Adresse ist danach ein
  Fehler 404, und das Internet Archive hat davon keinen einzigen Schnappschuss.
  Bei Tabellen mit nur drei Jahrgängen — etwa der über Steuern und Zuweisungen —
  war damit jedes Jahr ein Jahrgang endgültig weg. Ein neuer täglicher Lauf
  sichert jetzt alle Jahrbuch-Tabellen, alle Dateien des Open-Data-Portals und
  die Finanzausgleichs-Tabellen des Landes versioniert; verändert sich eine
  Datei, kommt die neue Fassung dazu, die alte bleibt. Wir laden dabei nur, was
  sich wirklich geändert hat. (#603)
- **Bei jeder Steuer steht jetzt, was geplant war — und was daraus wurde.** Der
  Steckbrief einer Steuerart (etwa der Gewerbesteuer) zeigt neben dem, was
  hereinkam, den Ansatz aus dem beschlossenen Haushalt. Bei der Gewerbesteuer
  liegen die beiden weit auseinander: 2023 kamen 42 Prozent mehr herein als
  geplant, 2024 sogar 52 Prozent. Das ist ein Befund und keine Note — wer eine
  Steuer vorsichtig ansetzt, die zwischen 43 und 222 Millionen Euro schwankt,
  vermeidet eine Lücke, die sich mitten im Jahr nicht mehr schließen lässt. Dazu
  kommt die Geschichte des Hebesatzes: 45 Jahre, neun Entscheidungen des Rats,
  als Treppe — denn ein Hebesatz gilt, bis er wieder geändert wird. Daneben
  steht jedes Mal, was im selben Jahr tatsächlich hereinkam. 2025 zeigt, warum
  das zusammengehört: Der Hebesatz der Grundsteuer B stieg um 21 Prozent, das
  Aufkommen sank trotzdem um 4,6 Prozent, weil die Grundsteuerreform
  gleichzeitig alle Messbeträge neu festsetzte. (#608)
- **Der Streit ums Geld zeigt jetzt, was in den Änderungslisten stand.** Bisher
  sagte die Seite „Mitreden" nur, wer eine Änderungsliste einbrachte und ob sie
  durchkam — der Inhalt lag als PDF ohne Volltext im Ratsinformationssystem.
  Jetzt liest Ratslotse die Listen selbst: je Dokument (Änderungslisten der
  Verwaltung I–III und die beschlossenen Änderungen des Finanzausschusses) alle
  Positionen mit Teilhaushalt, Bezeichnung und Betrag, dazu der Saldo und bis zu
  welchem Planjahr die Liste wirkt. Jede Liste ging beim Einlesen gegen ihre
  eigene Schlusssumme auf — was nicht aufgeht, wird nicht angezeigt. Von den
  Änderungslisten der Fraktionen, die als Tischvorlagen verteilt wurden und in
  keinem Dokument liegen, zeigt die Seite die einzige digitale Spur: ihre
  Summenzeile aus der Beschluss-Datei, mit dem Urheber daneben. (#739)
- **Die KI-Frage zeigt Tagesordnungen als eigene Karte.** Wer nach einer
  konkreten Sitzung fragt, zu der es noch keine Beschlüsse gibt — weil sie erst
  bevorsteht oder das Protokoll noch nicht veröffentlicht ist —, bekommt unter
  der Antwort jetzt eine Tagesordnungs-Karte: Gremium, Termin, die ersten Punkte
  der Tagesordnung und der Sprung zur Sitzungsseite. Die Karte kommt direkt aus
  dem Sitzungskalender, nicht vom Sprachmodell, und bleibt auch in gespeicherten
  Gesprächen erhalten. (#735)
- **Oberbürgermeister und Dezernent:innen bekommen jetzt einen eigenen
  Steckbrief.** Im Personenverzeichnis stehen unter „Stadtverwaltung" jetzt auch
  Amtsträger:innen mit erkanntem Amt (Oberbürgermeister/-in, Stadtkämmerer/-in,
  Stadtbaurat/-rätin, Stadtrat/-rätin) — mit Amt, Erwähnungszeitraum aus den
  Protokollen und ihren Wortbeiträgen. Ihr Badge im Antworttext der KI-Frage
  verlinkt jetzt ebenfalls dorthin. Ohne erkanntes Amt bleibt es beim bisherigen
  Badge ohne Link — die Datenbasis wäre für ein vertrauenswürdiges Profil zu
  dünn. (#654)
- **„Und welche Firmen zahlen das?" — der Steckbrief der Gewerbesteuer
  beantwortet jetzt die häufigste Rückfrage.** Nämlich damit, dass sie niemand
  beantworten darf: Was ein einzelnes Unternehmen zahlt, fällt unter das
  Steuergeheimnis, auch gegenüber dem Rat. Was die Zahlen trotzdem hergeben,
  steht daneben — die Gewerbesteuer schwankt von Jahr zu Jahr um ein Vielfaches
  dessen, was die Grundsteuer tut, und in keinem dieser Sprungjahre hatte der
  Rat den Hebesatz angefasst. Dazu der Weg, auf dem man sich der Frage nähern
  kann (die Gewerbesteuer folgt der Lohnsumme am Standort, nicht dem Sitz der
  Zentrale) und die drei Stellen, an denen dieser Weg bricht. Namen nennt die
  Seite keine. (#714)
- **Was die Bäder kosten sollen, steht jetzt im Bestand.** Der Haushalts-Bereich
  zeigt neben Gebäudewirtschaft und Abfallwirtschaft jetzt auch die
  Wirtschaftspläne der Bäderbetriebsgesellschaft, des Bäderbetriebs und der
  beiden Stadion-Gesellschaften — insgesamt 22 Jahrgänge. Für die
  Bäderbetriebsgesellschaft, die OLantis und die übrigen Bäder betreibt, ist für
  2026 ein Fehlbetrag von 10,1 Millionen Euro geplant; 2020 waren es 2,7
  Millionen. Belegt ist jede dieser Zahlen doppelt: Sie steht im Beschlusstext
  der Ratsvorlage und noch einmal in der beigefügten Anlage. Wo das nicht geht —
  weil ein Plan ausgeglichen ist oder die Anlage nur als Scan vorliegt — sagt
  der Beleg das ausdrücklich, statt Sicherheit vorzutäuschen. (#667)
- **Der Haushalt neben dem Haushalt.** Der Rat beschließt jedes Jahr nicht nur
  den Stadthaushalt, sondern auch die Wirtschaftspläne der Eigenbetriebe — und
  die waren im Haushalts-Bereich bisher unsichtbar. Der größte davon, der
  Eigenbetrieb Gebäudewirtschaft und Hochbau, plant für 2026 mit 82,8 Millionen
  Euro Erträgen und einem Vermögensplan über 51,1 Millionen; er baut und saniert
  die städtischen Gebäude, also auch die Schulen. Seine Eckwerte stehen jetzt
  für acht Jahrgänge (2019–2026) im Bestand, gelesen aus dem Beschlusstext der
  Ratsvorlage und geprüft an der Rechnung, die dort danebensteht. Die übrigen
  Betriebe nennen ihre Zahlen nur in einer Anlage — was fehlt, weist der Bereich
  als fehlend aus, statt eine ungeprüfte Zahl danebenzustellen. (#663)

### Geändert
- **Der Datenstand im Quellenverzeichnis rechnet sich selbst.** Am Fuß jeder
  Haushalts-Seite steht, welche Jahrgänge eine Quelle abdeckt
  („Jahresabschlüsse 2017–2024"). Diese Spannen wurden von Hand gepflegt,
  einundzwanzig Stück — und veralteten zuverlässig, sobald ein Ingest-Lauf
  einen Jahrgang nachzog: Die Angabe stand nicht neben den Daten, sondern in
  einer anderen Datei. Vierzehn davon fragen jetzt den Bestand. Die übrigen
  sieben bleiben von Hand, weil sie sich gar nicht ableiten lassen — ein
  Genehmigungsdatum, eine einzelne Ratsvorlage von 2018, die Ausgabe-Angaben
  der Landesstatistik —, und das steht jetzt begründet dabei. (#567)
- **Die Seite „Streit ums Geld" lädt spürbar schneller.** Sie zerlegte bei
  jedem Aufruf rund sechzehn vollständige Ratsprotokolle neu, um die
  Wortbeiträge herauszuholen — gut anderthalb Sekunden Rechenzeit für ein
  Ergebnis, das jedes Mal dasselbe war. Jetzt merkt sie sich die Zerlegung
  anhand des Protokoll-Inhalts. Die Zusage der Seite bleibt dabei unangetastet:
  Sie führt weiter keinen eigenen Datenbestand, kann also nicht veralten, und
  ein nachgetragenes Protokoll erscheint weiterhin sofort und ohne
  Nacharbeit. (#567)
- **Zwei weitere Seiten hören auf, ihre eigene Gründlichkeit vorzuführen.**
  „Was wird gebaut?" und „Wer macht die Arbeit?" zeigten unter jeder Zahl noch,
  gegen welche Rechenprobe wir sie geprüft haben — bis hin zum Messwert
  („Gemessen: 0,00 € Restbetrag"). Das sagt etwas über uns und nichts über den
  Haushalt; die übrigen Seiten hatten es schon abgelegt. Wo eine Zahl steht,
  steht weiterhin, **wo im Dokument** man sie findet — und was eine Quelle
  nicht hergibt, sagen die Seiten unverändert. Die Proben laufen weiter, nur
  ohne Publikum. (#554)
- **Der Haushalts-Bereich bleibt vorerst der Dev-Umgebung vorbehalten.** Die
  dreizehn Seiten unter `/haushalt` sind jetzt — wie der Wahlprogramm-Vergleich
  — an `NEXT_PUBLIC_RATSLOTSE_ENV` gebunden: Auf ratslotse.de rendern sie
  nicht, und die Anker dorthin (Seitenleiste, „Mehr"-Sheet, der Verweis auf den
  Beschluss-Seiten) verschwinden mit ihnen — ein Gate ohne seine Einstiege
  hinterließe Links, die ins Leere führen. Damit kann der Bereich weiterentwickelt
  werden, ohne den nächsten Release aufzuhalten. Ein Testwächter prüft künftig,
  dass kein neuer Verweis das Gate vergisst. (#546)
- **Kleinkram im Haushalts-Bereich, den sonst niemand bemerkt hätte.** Das
  Fußnotenzeichen im Städtevergleich ist jetzt ein Kreuz statt eines Sternchens
  — die Fußnote selbst endet auf „Einwohner*innen", und zwei Sternchen mit
  verschiedener Bedeutung nebeneinander liest niemand auseinander. Im
  Quellenverzeichnis stehen nicht mehr unsere Prüfverfahren, sondern nur noch,
  was eine Quelle hergibt und was nicht. Im Haushalts-Labor behauptet kein Satz
  mehr, wie sich ein Jahrgang entwickelt hat, den die Seite gar nicht zeigt.
  Dazu die Sternchenform in den letzten eigenen Dokumenten (Zitate aus
  Wahlprogrammen bleiben unangetastet) und eine ungenutzte Komponente weniger.
  (#549)
- **Zahlen, die eine Rechenprobe nicht bestehen, ersetzen keine vorhandenen
  mehr.** Liest ein Parser für einen bereits gespeicherten Jahrgang plötzlich
  nichts oder deutlich weniger — etwa weil die Stadt ihre Tabellen umbaut —,
  bleibt der alte Stand stehen und der Lauf meldet es, statt den Bestand gegen
  ein kaputtes Ergebnis zu tauschen. Beim Einlesen von Hand lässt sich das mit
  `--auch-schrumpfen` übergehen; ein leeres Ergebnis ersetzt auch dann nichts.
  Ein Jahrgang wird außerdem am Stück gespeichert — bricht ein Lauf mittendrin
  ab, steht hinterher der alte Stand da und kein halber neuer. (#511)
- **„Bis wann die Zahlen reichen" sagt es jetzt auch für den Städtevergleich.**
  Der Block am Fuß von `/haushalt` führte jede Datenschicht auf — außer den
  beiden Reihen, die den Vergleich mit den anderen kreisfreien Städten tragen.
  Wer `/haushalt/vergleich` las, erfuhr an keiner Stelle, bis wann sie reichen
  und wann der nächste Jahrgang kommt. Beide stehen jetzt dort, mit ihrem
  eigenen Takt: Die Steuerkraft-Reihe erscheint im April desselben Jahres, der
  Realsteuervergleich im November des Folgejahres. Und die Fußzeile nennt die
  Stelle beim Namen: Sie versprach bisher pauschal, die Zahlen „vom Portal der
  Stadt" zu holen — die beiden neuen Reihen kommen vom Landesamt für Statistik
  Niedersachsen. Bleibt ein Jahrgang aus, meldet das der zweiwöchentliche
  Prüflauf; geholt werden die Tabellen weiter von Hand, weil sie nur einmal im
  Jahr erscheinen. (#530)
- **Admin-Panel: Speicher-Einwilligung sichtbar, Tabs mobil scrollbar.** Das
  Nutzer-Detail zeigt jetzt, ob ein Konto „Gespräche speichern" für die KI-Frage
  angeschaltet hat (an, bewusst aus oder nie gefragt). Außerdem liefen die
  sieben Admin-Tabs auf schmalen Bildschirmen über den rechten Rand hinaus — die
  Leiste scrollt jetzt seitlich. (#733)
- **Man bleibt angemeldet.** Die Sitzung im Browser hielt einen Tag und wurde
  nie erneuert — wer Ratslotse gestern benutzt hat, stand heute wieder vor dem
  Login. Jetzt läuft sie 90 Tage und verlängert sich still, sobald man die Seite
  benutzt: Wer regelmäßig vorbeischaut, meldet sich nicht wieder an. Das gilt
  auch für reines Lesen öffentlicher Beschluss-Seiten. Die App macht dasselbe
  mit ihrem Token, das sich bei jedem Start erneuert. Abmelden, Passwortwechsel
  und Passwort-Reset beenden die Sitzung unverändert sofort — auf allen Geräten.
  (#706)
- **Die Bereichsseiten des Haushalts rechnen sichtbarer.** Die drei Kennzahlen
  standen klein in einer Eckkarte, und der Wasserfall darunter verlangte, dass
  man seine Leserichtung kennt. Jetzt trägt der Seitenkopf die Zahlen groß auf
  der Anzeigetafel, und darunter zeigen zwei Balken auf einer Skala, was
  rausgeht, was reinkommt — die Lücke dazwischen heißt sichtbar „trägt die
  Stadt". Dieselbe Darstellung wie auf der Haushalts-Übersicht. (#726)
- **Teilhaushalte und Aufgaben stehen jetzt auf einer Seite.** „Was steckt
  hinter den Namen?" und „Was kostet eigentlich …?" waren zwei Schritte, gehen
  aber denselben Baum hinunter: erst die zehn Teilhaushalte im Klartext, dann
  die einzelnen Aufgaben darin. Wer den zweiten ohne den ersten las, suchte
  Aufgaben in Bereichen, deren Namen ihm nichts sagen. Beides steht jetzt unter
  *ratslotse.de/haushalt/produkte*. Der Steckbrief eines einzelnen Teilhaushalts
  bleibt als dritte Ebene eine eigene Seite. (#702)
- **Beschlüsse bekommen nachvollziehbare Ortszuordnungen.** Einmalige Straßen
  bleiben erhalten, mehrere Orte je Beschluss sind möglich und jede Zuordnung
  speichert ihre Fundstelle und Qualität. Neue oder später vervollständigte
  Beschlüsse werden täglich nachgezogen. Eine reproduzierbare
  Qualitätsstichprobe und konservative Nachfilterung halten Organisationen,
  auswärtige Vergleichsorte und generische Platzbegriffe aus den Ortsbezügen
  heraus. (#765)
- **Der Steckbrief einer städtischen Gesellschaft zeigt jetzt Zahlen, Anteile
  und Personen statt fünf Textblöcken.** Jahresergebnis, Bilanzsumme und
  Eigenkapitalquote stehen mit ihrem jeweiligen Jahr oben, daneben der Verlauf.
  Wem die Gesellschaft gehört, ist ein Anteilsstreifen mit Betrag und Quote, wie
  sie im Bericht stehen; wer sie beaufsichtigt, sind Personen mit Partei und
  Link ins Personenverzeichnis, gebündelt nach dem Amt, das der Bericht ihnen
  gibt. Wo der Bericht Namen und Funktionen nicht sicher paaren lässt, stehen
  die Namen ohne Amt und die Seite sagt, warum. Der Unternehmensgegenstand steht
  mit seinem ersten Absatz da, der volle Wortlaut hinter einem Auslöser — und
  jede Angabe behält ihre Fundstelle mit Seitenzahl. (#586)
- **Der Eigenbetrieb Hafen steht jetzt mit auf der Seite.** Er ist der siebte
  Betrieb im „Haushalt neben dem Haushalt". Seine Reihe endet 2020, und das ist
  keine Datenlücke: Der Rat hat den Betrieb damals aufgelöst. Genau das steht
  jetzt auch an der Karte — sonst sähe ein Ende wie ein Loch aus. (#673)
- **Die Bürgschaften zeigen jetzt die Bewegung, nicht nur den Stichtag.** Was
  die Stadt selbst schuldet und wofür sie geradesteht, stehen im selben Bild und
  im selben Maßstab — und laufen sichtbar auseinander: Die eigenen Schulden sind
  seit 2019 um 27 Prozent gesunken, das verbürgte Volumen ist auf das 2,9-Fache
  gestiegen. Warum es 2022 sprang, steht an der Stelle, an der die Frage
  entsteht. (#620)
- **Changelog-Einträge entstehen jetzt als eigene Datei je Änderung.** Bisher
  schrieb jede Änderung ihren Eintrag in dieselben Zeilen unter „Unreleased" —
  liefen zwei parallel, kollidierten sie dort verlässlich. Jede Änderung legt
  stattdessen eine eigene kleine Datei unter `changelog.d/` an; erst beim
  Versionsschnitt wandern sie gesammelt in den Changelog, samt der Nummer, unter
  der die Änderung eingereicht wurde. Auf ratslotse.de/changelog ändert sich
  nichts: Was noch als Fragment vorliegt, steht dort weiterhin unter
  „Unreleased", nach Kategorie einsortiert. (#581)
- **Die Haushaltsdebatte liest sich jetzt wie ein Weg durch die Sitzung.** Die
  Wortbeiträge unter „Der Streit ums Geld" waren ein grauer Stapel: Name,
  kursiver Absatz, Knopf — einundzwanzigmal untereinander, die halbe Karte leer.
  Jetzt führt eine geschlungene Linie von Redner*in zu Redner*in, jede zweite
  Wortmeldung rückt ans andere Ufer, und der Punkt an der Linie trägt die
  Fraktionsfarbe — dieselbe Marke wie die Zähl-Chips am Kopf der Karte. Beim
  Scrollen zeichnet sich der Weg mit und die Beiträge treten nacheinander auf;
  die Pfeilspitze am Ende zeigt dorthin, wo die Debatte hinführt: zur
  Abstimmung. Der Wortlaut selbst steht nicht mehr kursiv — einundzwanzig Reden
  in Schrägschrift waren schlicht anstrengend zu lesen. Wer Animationen im
  System abgeschaltet hat, bekommt alles fertig gezeichnet und ohne Bewegung.
  (#709)
- **Im Haushalts-Bereich trägt jede Zahl ihre Einheit.** Auf der Anzeigetafel
  stand über den drei Summen nur „nimmt ein / gibt aus / fehlt" und darunter die
  nackte Zahl — wie groß 812,9 ist, musste man sich aus der Überschrift
  zusammenreimen. Jetzt steht hinter jedem Betrag „Mio. €": auf der Tafel, in
  der Legende des Gegenbalkens, in der Bereichstabelle, auf den Seiten „geplant
  gegen tatsächlich", „Woher kommt das Geld?", „Pflicht oder Kür" und im Labor.
  Wo bisher „Mio." ohne Währung stand, steht sie jetzt dabei; wo die Spalte zu
  schmal ist, trägt der Spaltenkopf die Einheit. (#708)
- **Die Haushalts-Übersicht lädt noch einmal deutlich weniger.** Der größte
  Datenblock — die Ergebnisrechnung mit ihren dreizehn Teilhaushalten — kommt
  jetzt nur noch in der Tiefe, die die jeweilige Seite zeichnet. Die Übersicht
  holt 178 statt 795 Kilobyte, das Haushalts-Labor 131. Zu sehen ist dasselbe:
  Das Flussbild zeigt unverändert alle Bereiche. (#625)
- **„Frag den Rat“ kann Ortsbezüge jetzt mit Geld-, Partei-, Verlaufs-,
  Personen- und Sitzungsfragen kombinieren.** Die Quellen zeigen außerdem den
  erkannten Ort und die konkrete Fundstelle der Zuordnung. (#789)
- **Ein Redebeitrag zeigt die Fraktion, unter der er gehalten wurde.** Vally
  Finke saß 2022 für die SPD und sitzt heute für „Für Oldenburg" — ihre Beiträge
  von damals trugen bisher entweder gar kein Abzeichen oder das von heute. Jetzt
  steht in der Quellenzeile „Finke ·SPD (heute Für Oldenburg)": das Abzeichen
  nennt die Zugehörigkeit zum Zeitpunkt der Aussage, der Halbsatz dahinter sagt,
  dass sie eine andere geworden ist. Der Wechsel zwischen Gruppen-Label und
  Einzelpartei („FDP/Volt" ↔ „FDP") gilt dabei nicht als Wechsel. Nebeneffekt:
  Beiträge, die wegen des scheinbaren Widerspruchs kein Abzeichen bekamen, haben
  jetzt eins — die Zuordnung bleibt belegt, denn gewertet wird nur, was in den
  Anwesenheitslisten steht. (#697)
- **Die ganze Stadt steht jetzt auf einer Seite — und der Bereich hat elf
  Schritte statt neunzehn.** Vier Seiten beantworteten dieselbe Frage: die Summe
  aus dem Gesamtabschluss, die städtischen Gesellschaften einzeln, ihre
  Wirtschaftspläne und die Gebühren, die daraus folgen. Das ist eine Kette — wer
  bei den Gebühren anfängt, liest eine Zahl ohne Herkunft; wer bei der Summe
  aufhört, weiß nicht, wer dahintersteckt. Alle vier stehen jetzt unter
  *ratslotse.de/haushalt/konzern* als Abschnitte mit einer Navigation am Kopf.
  Damit ist die Neuordnung des Haushalts-Bereichs abgeschlossen: Aus neunzehn
  Schritten sind elf geworden, ohne dass ein einziger Inhalt weggefallen ist.
  Alle alten Adressen leiten auf ihren Abschnitt weiter. (#703)
- **Halb leere Kästen im Haushalts-Bereich füllen jetzt ihre Fläche.** Auf
  breiten Bildschirmen endete der Text in manchen Karten nach knapp der Hälfte,
  und rechts blieben bis zu 870 Pixel leer. Der Grund war gut gemeint: Fließtext
  braucht eine begrenzte Zeilenlänge, sonst läuft er auf 120 Zeichen je Zeile.
  Nur saß die Begrenzung am Text statt am Kasten. Jetzt deckelt sich der
  Einschub „Lotti erklärt's einfach" selbst — er steht schmaler als der Fluss,
  und das ist bei einem Einschub genau richtig. Die Grenzen-Blöcke („Was diese
  Zahlen nicht hergeben") laufen auf breiten Karten in zwei Spalten: Fläche
  gefüllt, Zeile lesbar. Betroffen waren zwanzig Seiten, weil Lotti auf allen
  steht. (#694)
- **Die Bühnen-Grafiken erklären sich jetzt selbst.** Auf „Woher kommt das
  Geld?" stehen die drei Spielraum-Gruppen im Kopfbild als beschriftete Reihen —
  Name links, ein Quadrat je Quelle rechts daneben, alle an derselben Kante
  beginnend; die Erklärzeile darunter braucht es nicht mehr. Und auf „Mitreden"
  zeigt das Kopfbild statt vier stummer Punkte den Weg des laufenden Haushalts:
  Einbringung, Beratung in den Ausschüssen, Beschluss im Rat, laufendes
  Haushaltsjahr — jede Station mit Datum, und markiert ist die, in der wir
  gerade stecken. Die Überschrift dort spricht außerdem von den Ratsdebatten zum
  Haushalt statt vom „Streit ums Geld". (#760)
- **Lottis Erklärkarten lesen sich wieder wie Text, nicht wie eine Zeile.** Auf
  breiten Bildschirmen liefen sie über die volle Kartenbreite — deutlich länger
  als jeder andere Absatz derselben Seite. Jetzt enden sie dort, wo der Rest des
  Haushalts-Bereichs auch endet. Betrifft achtzehn Seiten. (#593)
- **Die Lücke von 2019 sagt jetzt, wie groß sie ist.** Auf „Was wurde davon
  wirklich gebaut?" fehlt der Jahrgang, weil die Auszahlungsarten im
  Statistischen Jahrbuch nicht die Summe daneben ergeben. Wie weit die beiden
  Zahlen auseinanderliegen, stand bisher nur im Protokoll des Einlese-Laufs —
  jetzt steht es an der Lücke: „verworfen: 1,3 Mio. € Differenz im Dokument".
  Der Betrag wird bei jedem Lauf neu gemessen und nirgends fest eingetragen;
  ohne Messung nennt die Seite die Lücke wie bisher ohne Zahl. Die Schuldenkurve
  wiederum zeichnet jetzt dieselbe Grafik wie der Rest des Bereichs — mit
  Zinslinie, 2010-Marke und den beiden größten Bewegungen wie gehabt, dazu allen
  Werten als Tabelle zum Abschreiben. Und die Zinslast über der Kurve nennt
  wieder die Kernverwaltung: Sie zeigte zuletzt die Zinsen eines einzelnen
  Teilhaushalts. (#597)
- **Die Haushalts-Seiten laden deutlich weniger Daten.** Bisher holte jede von
  ihnen denselben großen Datensatz — auch die, die daraus zwei Zahlen zeigt.
  Jetzt fordert jede Seite nur noch an, was sie tatsächlich darstellt: über neun
  Seiten zusammen 3,6 statt 13,7 Megabyte. Am deutlichsten auf dem Handy und in
  der App, wo diese Daten über Mobilfunk kommen. Zu sehen ist dieselbe Seite mit
  denselben Zahlen — sie ist nur schneller da. (#618)
- **Geteilte Links in den Haushalt führen wieder ans Ziel, und die Seiten
  dahinter sind aufgeräumter.** Ein Steckbrief-Link mit dem Klartextnamen — etwa
  `/haushalt/bereich?name=Finanzmanagement und Recht` — lief bisher auf „Diesen
  Bereich kennen wir nicht", obwohl der Bereich genau so heißt; jetzt findet ihn
  die Seite auch unter älteren Schreibweisen desselben Teilhaushalts, und
  dasselbe gilt für die Steckbriefe der Einnahmearten. Auf *Muss oder kann?*
  steht die Angabe der Stadt jetzt auf einer eigenen Fläche statt als zweiter
  Balken direkt unter dem ersten, „weicht ab" rückt neben den Bereichsnamen, und
  dieselbe Auskunft wird nicht mehr dreimal je Karte wiederholt. Der
  Schlusshinweis auf *Woher das Geld kommt* zerfällt in seine drei Aussagen,
  statt als ein Absatz von 550 Zeichen dazustehen. Und wo eine Zahl fehlt — bei
  „Gebühren und Beiträge" — sagt der Steckbrief das jetzt, statt die Kennzahl
  stillschweigend wegzulassen. (#590)
- **Drei Haushalts-Seiten sind lesbarer geworden — dort, wo bisher der Wortlaut
  der Quelle als Wand herunterlief.** Betroffen sind die Prüfungs-Seite,
  „Geplant und geworden" und die Produkt-Steckbriefe. Gekürzt wird an keiner
  Stelle etwas: Alle Wortlaute, Fundstellen und Deeplinks bleiben vollständig,
  sie stehen nur anders auf der Seite. Auf **„Was das Rechnungsprüfungsamt
  beanstandet"** war der Jahresbericht die textlastigste Fläche des ganzen
  Bereichs — für 2018 eine einzige Karte mit 49 Feststellungen am Stück. Jetzt
  trägt jeder Abschnitt des Schlussberichts ein eigenes Feld mit seiner
  Textziffer und der Zahl seiner Feststellungen, die Jahreswahl steht im
  Kartenkopf statt darüber, und ein Umschalter führt von der Zahl in der
  Überschrift zu den Einträgen: „Alle (49)" oder „Nur Beanstandungen (15)". Was
  der Umschalter gerade ausblendet, sagt eine Zeile darunter — und dass ein
  Hinweis etwas anderes ist als eine Beanstandung, steht weiterhin oben, nicht
  im Kleingedruckten. Auf **„Geplant und geworden"** stand in fünf von acht
  Jahrgängen ein ganzer Abschnitt des Jahresabschlusses mitten im Bild: bis zu
  7.176 Zeichen Einzelbeträge zwischen zwei Zeilen der Plan-Ist-Grafik. Solche
  Abschnitte stehen jetzt vollständig unter „Warum es anders kam", wo alle
  Erläuterungen der Verwaltung liegen; in der Grafik bleibt der Hinweis, dass es
  sie gibt. Und eine Erläuterung, die zwei Bereiche in einem Satz nennt, wird
  nicht mehr zweimal abgedruckt — der zweite Bereich verweist auf den ersten.
  Die **Produkt-Steckbriefe** geben endlich wieder, was der Haushaltsplan
  eigentlich aufzählt. „Was dahintersteckt" ist bei 60 von 507 Produkten eine
  Liste von Leistungen, die beim Auslesen zu einem Absatz verschmolzen war; sie
  steht wieder als Liste. Dasselbe gilt für „Für wen" und für „Worauf die
  Aufgabe beruht" — die Gesetze und Satzungen stehen einzeln statt in einer
  Zeile mit 442 Zeichen. Wo sich ein Text nicht verlustfrei zerlegen lässt,
  bleibt er unverändert ein Absatz; sehr lange Beschreibungen zeigen ihren
  ersten Absatz und den Rest auf Klick. (#591)
- **Der Streit ums Geld, das Haushaltsjahr und das Labor lesen sich jetzt wie
  der Rest des Haushalts.** Die Wortbeiträge aus den Haushaltsdebatten liefen
  über die ganze Kartenbreite — bei einem aufgeklappten Beitrag von 8.735
  Zeichen waren das rund 130 Zeichen je Zeile, kursiv, ohne einen einzigen
  Absatz. Sie stehen jetzt in derselben Lesespalte wie der übrige Fließtext des
  Bereichs; am Wortlaut, an der Reihenfolge und an der Vorschau ändert sich
  nichts. Wer wie oft zu Wort kam, steht als Chip-Reihe mit den gewohnten
  Fraktionspunkten statt als aneinandergereihte Wortkette. Im Haushalts-Labor
  sind „Wie verlässlich ist der Plan?" und „Was dagegen rechnet" aus der
  schmalen Seitenspalte unter die Regler gewandert — dort quetschten sie sich in
  330 Pixel, während daneben eine halbe Bildschirmbreite leer blieb. Auf der
  Jahres-Seite stehen die zehn Fachausschüsse als einzelne Marken statt als eine
  lange Zeile, und die Herkunftsangabe am Seitenende trägt endlich dieselbe
  Karte wie alle anderen Quellenhinweise. Beim Städtevergleich versprach die
  Überschrift „Grundsteuer B — der Sprung zur Reform" ein Vorher-Nachher, das
  die Seite gar nicht zeigen konnte: Die Hebesätze liegen uns bisher nur für ein
  Jahr vor. Jetzt sagt sie das, statt einen Vergleich anzukündigen, der nicht
  kommt. (#592)
- **Die Haushaltsübersicht erklärt Planwerte, Pro-Kopf-Zahlen und Diagramme
  jetzt verständlicher.** Fachbegriffe und wichtige Einschränkungen bleiben
  erhalten, während missverständliche Bilder und unnötig technische
  Formulierungen entfallen.
- **Die Unterseiten zum Oldenburger Haushalt erklären Fachbegriffe und Zahlen
  jetzt verständlicher.** Plan- und Istwerte, Ergebnis- und Finanzhaushalt sowie
  die Grenzen einzelner Vergleiche werden klarer voneinander unterschieden;
  unnötig bildhafte und selbstreferenzielle Formulierungen entfallen.
- **Der Weg durch den Haushalt ist jetzt eine große, animierte Route statt einer
  kleinen Linkliste.** Vier Etappen hängen an einem SVG-Pfad, der sich beim
  ersten Sichtkontakt zeichnet. Alle zwölf Fragen bleiben direkt anwählbar,
  besuchte Schritte werden weiterhin nur im eigenen Browser gemerkt und ein
  sichtbarer Knopf startet den Weg auch beim allerersten Besuch. Die Route steht
  nun direkt nach der kurzen Haushaltserklärung, bevor die Übersicht in ihre
  Detailgrafiken einsteigt. Auf kleinen Bildschirmen wird der geschlungene Pfad
  zu einer senkrechten Leselinie, ohne Etappen zu verstecken. (#791)
- **„Woher das Geld kommen soll" zeigt jetzt Flächen statt Balken.** Auf der
  Haushalts-Übersicht standen die zehn Ertragsarten des Planjahres als Balken
  auf einer Schiene von null bis zum größten Posten. Die beantwortete, wer
  größer ist als wer — nicht die Frage, die darüber steht: Steuern nahmen die
  volle Breite ein, weil sie der größte Posten sind, nicht weil sie fast die
  Hälfte der Erträge sind. Jetzt zerlegt eine Kachelfläche die Summe, jeder
  Posten in seiner eigenen Farbe: Fläche heißt Anteil, und wer eine Kachel
  überfährt, antippt oder mit Tab ansteuert, liest darunter Name, Langfassung,
  Betrag und Prozentwert. Die kleinsten Posten — 2026 sind das Auflösung von
  Sonderposten, Transfererträge und Eigenleistungen — stehen als ein
  schraffierter Sammelposten in der Fläche, damit kein Posten zum unlesbaren
  Farbfleck wird; ihre Namen und Beträge stehen in der Legende und erscheinen
  beim Überfahren des Sammelpostens. Auf dem Telefon bleibt es bei der Liste.
  Nebenbei sind zwei Anzeigefehler derselben Grafik weg: Auf den blassesten
  Kacheln des Investitionen-Explorers stand weißer Text auf fast weißem Grund,
  und lange Namen wie „Transfererträge" brachen mitten im Wort ab. (#711)
- **Bankverbindungen und Anschriften stehen gar nicht mehr in der Datenbank.**
  Bisher wurden sie nur aus der Suche herausgehalten. Jetzt werden sie schon
  beim Einlesen entfernt, und der vorhandene Bestand ist einmal durchgegangen
  worden: 81 Bankverbindungen und rund 1.450 Anschriften sind weg.
  Telefonnummern und E-Mail-Adressen bleiben gespeichert — sie helfen dabei,
  eine Fundstelle im Originaldokument wiederzufinden — und werden weiterhin aus
  der Suche herausgehalten. Straßennamen bleiben unangetastet, sonst verschwände
  die halbe Investitionsplanung. (#681)
- **Was gebaut wird und was daraus wurde, steht jetzt auf einer Seite.** Plan
  und Ist derselben Sache lagen bisher auf zwei Seiten in zwei verschiedenen
  Etappen — wer wissen wollte, was aus einem Vorhaben geworden ist, musste die
  Seite wechseln. Unter *ratslotse.de/haushalt/investitionen* stehen beide als
  Abschnitte untereinander. Wichtig dabei: Die beiden Summen zählen **nicht**
  dasselbe und lassen sich nicht voneinander abziehen — der Plan ist nach
  Teilhaushalten gegliedert, das Ist nach Auszahlungsarten. Dieser Einwand stand
  bisher am Seitenende; jetzt steht er **vor** den Ist-Zahlen, weil die
  Subtraktion dort naheliegt, wo beide Zahlen untereinander stehen. (#701)
- **Die Investitionsgrafik ist leichter zu lesen:** Eine einheitliche
  Balkenfarbe zeigt jetzt nur noch die geplanten Auszahlungen. Zuschüsse,
  Verkäufe und Beiträge stehen separat als Betrag und Anteil darunter.
- - Zeigt „Frag den Rat" mehrere „Worum geht es?"-Steckbriefe, stehen am Desktop
  jetzt Blätter-Pfeile neben den Indikator-Punkten — die Punkte allein waren mit
  der Maus schwer zu treffen. Ihre Klickfläche ist außerdem größer; auf dem
  Telefon bleibt Wischen der Weg. - Die Vorschlags-Pillen unter einer Antwort
  laufen am Desktop nicht mehr hart abgeschnitten in die Blätter-Pfeile: Die
  Pfeile schweben über den Zeilen-Enden, und die Pillen blenden dort weich aus.
  (#651)
- **Keine Mail, wenn sich nur die Nummern verschieben.** Fällt in einer
  Tagesordnung oben ein Punkt weg oder kommt einer dazu, rückt der ganze Rest
  geschlossen nach — gleiche Punkte, gleiche Reihenfolge, neue Nummern. Dafür
  geht jetzt keine Benachrichtigung mehr raus; auf der Sitzungsseite steht die
  Verschiebung weiterhin unter „Zuletzt geändert". Wandert ein Punkt dagegen
  wirklich an eine andere Stelle, oder kommt neben dem Versatz eine Vorlage,
  eine Anlage oder ein neuer Punkt dazu, wird wie bisher gemeldet. (#761)
- **Kleinigkeiten auf der Kennzahlen-Seite.** Der Hinweis „Eine Zahl antippen
  zeigt ihren Verlauf" stand dreimal untereinander und steht jetzt einmal; aus
  „aus 6 Berichten" wurde „aus sechs Berichten". (#633)
- **„Wie hoch sind die Schulden?" hat drei richtige Antworten — die KI-Frage
  nennt jetzt alle.** 43,7 Millionen Euro sind es im Kernhaushalt, 294,9
  Millionen für die Stadt samt Eigenbetrieben, 740,3 Millionen für den ganzen
  Konzern mit allen Beteiligungen. Bisher kam eine davon, und welche, entschied
  der Zufall. Dazu die 220,3 Millionen Euro, für die die Stadt zusätzlich bürgt
  — ausdrücklich als eigene Größe, denn eine Bürgschaft ist keine Schuld. (#630)
- **Kontonummern und Kontaktdaten kommen nicht mehr in die Suche.** In den
  Ratsunterlagen stehen Bankverbindungen, Telefonnummern, E-Mail-Adressen und
  Anschriften — bisher landeten sie mit dem übrigen Text im Suchindex und
  konnten in Antworten auftauchen. Sie werden jetzt herausgenommen, bevor der
  Text indiziert wird; gespeichert bleibt er unverändert, damit Belege weiter
  auf die richtige Stelle im Dokument zeigen. Namen bleiben stehen:
  Ratsmitglieder, Amtsleitungen und Antragstellende gehören zur Sache. Und
  Straßennamen bleiben selbstverständlich auch — sonst verschwände die halbe
  Investitionsplanung. (#679)
- **„Was dieser Vergleich nicht kann" nutzt die Breite.** Der Block auf der
  Konzern-Seite hielt seinen Text in einer schmalen Spalte, während daneben die
  halbe Karte leer blieb. Auf breiten Karten stehen die vier Punkte jetzt in
  zwei Spalten — die Fläche ist gefüllt, die Zeile bleibt lesbar. Über die volle
  Breite in einer Spalte wäre der falsche Tausch gewesen: Bei 1.400 Pixeln
  stünden dort 180 Zeichen je Zeile. (#693)
- **Die Labor-Regler laufen in beide Richtungen.** Freiwillige Leistungen lassen
  sich jetzt auch aufstocken statt nur kürzen, die Hundesteuer reicht von
  „abschaffen" bis „verdoppeln" — „heute" steht überall in der Mitte, wie bei
  den Hebesätzen. Wer mehr ausgibt oder auf Einnahmen verzichtet, sieht ehrlich
  „Das Minus wächst um …" statt eines leeren Balkens. (#728)
- **Das Haushalts-Labor ist wieder eine eigene Seite.** Es stand seit dem
  Zusammenlegen der Etappen als dritter Abschnitt auf „Mitreden" — jetzt hat es
  als Schritt 12 wieder eine eigene Adresse (`/haushalt/labor`), denn es soll
  deutlich mehr Stellschrauben bekommen. Anders als vor dem Umbau führen nun
  auch die Mitreden-Seite, der Steuer-Steckbrief und die Weiter-Navigation
  dorthin. (#707)
- **Das Haushalts-Labor bekommt mehr Spielraum — und seine Vorhaben erklären
  sich.** Die Hebesatz-Regler laufen jetzt ±100 statt ±50 Punkte: Damit ist auch
  Wolfsburgs Gewerbesteuer-Niveau (360 %) erreichbar, das vorher unterhalb des
  Reglers lag. Der Lücken-Balken läuft in beide Richtungen — wer den Hebesatz
  senkt oder aufstockt, sieht das gewachsene Minus als orangen Balken statt
  einer leeren Anzeige. Bei den Vorhaben aus dem Investitionsprogramm hat jeder
  Schalter einen Namen (die 14,8-Mio.-Zeile heißt „SG Kreyenbrück Nord" — der
  Name stand im Dokument nur an der Sachkonto-Zeile), generische Namen zeigen
  ihre Detailzeilen (der „Eigenkapitalzuschuss" geht an die Stadion-GmbH), jede
  Zeile führt per Lupe in die Beschluss-Suche, und ein Satz erklärt, warum das
  Programm so viel Fliegerhorst und keine Schulen einzeln nennt. Wer Vorhaben
  streicht, bekommt in der Ergebnis-Karte gesagt, warum sich das Minus dabei
  kaum bewegt: Investitionen wirken auf Kasse und Schuldenpfad, im
  Jahresergebnis stehen nur die Abschreibungen. (#757)
- **Lange Texte im Haushalts-Bereich füllen die Karte, statt rechts ein Loch zu
  lassen.** Wo ein Text der eigentliche Inhalt einer Karte ist — die „Was hier
  fehlt"-Listen, die Leistungen eines Produkts, die Herkunft der
  Beratungsstationen —, läuft er auf breiten Schirmen jetzt in zwei bis drei
  Spalten. Die Fläche ist damit gefüllt und die Zeile zugleich kürzer als vorher
  (rund 70 statt 95 Zeichen). Auf schmalen Karten und am Telefon ändert sich
  nichts. Vier Textblöcke liefen außerdem deutlich breiter, als sie sollten —
  bis zu 122 Zeichen je Zeile gegenüber 95 in ihrer Nachbarschaft. Ursache war
  eine verrechnete Einheit, kein Gestaltungswille; sie stehen jetzt so breit wie
  der Rest des Bereichs. (#746)
- **Die Änderungslisten erklären sich jetzt selbst.** Bisher stand unter „Was in
  den Listen stand" zehnmal „Beteiligungen" mit zehn Beträgen — was sich
  dahinter verbirgt, blieb im PDF. Jetzt liest Ratslotse auch die
  Erläuterungs-Spalte der Dokumente: An jeder Position steht der Text der
  Verwaltung, was diese Änderung ist („VWG: Der Entwurf des Wirtschaftsplans
  2026 weist einen Zuschussbedarf von 16.493.040 Euro aus …"). Die Zuordnung der
  oft mehrzeilig umbrochenen Texte folgt den gedruckten Tabellenlinien des
  Dokuments — Geometrie statt Schätzung; wo das nicht eindeutig ist, bleibt das
  Feld lieber leer. Über 99 % der Positionen aller Jahrgänge 2019–2026 tragen so
  ihre Erklärung. (#744)
- **Lotti auf der Startseite trägt jetzt die Jahreszeit.** Die 3D-Szene nutzt
  das überarbeitete Lotti-Modell (spitzer Schnabel, Augen mit Pupille,
  Kopf-Gelenk) und zeigt das Wetter der Saison: Schnee im Winter, Blüten im
  Frühjahr, Sonne im Sommer, treibende Blätter im Herbst — und Lotti ist passend
  angezogen, vom kühlen Winterschal mit Ohrenschützern bis zur Sonnenbrille.
  Dieselben Outfits und Farben wie beim gezeichneten Fallback. (#724)
- **Die Lücken-Hinweise bei den Zuwendungen wiederholen sich nicht mehr.** Vier
  der sechs Felder auf „Woher das Geld kommt" endeten wortgleich mit derselben
  Deutung — „entweder hat der Rat die Liste geändert oder eines der beiden
  Dokumente trägt einen Zahlendreher". Der Satz gilt für alle Fälle dieser Art
  und steht jetzt einmal über der Liste; in jedem Feld stehen nur noch die
  Zahlen, um die es dort geht. Vorgelesen wird dadurch weniger, gesagt wird
  dasselbe. (#725)
- **E-Mails sagen, warum sie kommen — und wo man das ändert.** Tagesordnungs-
  Mails nennen jetzt den Grund („weil du das Gremium … abonniert hast") und
  verlinken direkt auf die Stelle, an der sich das Abo oder der Schalter ändern
  lässt; die Ziel-Seite hebt den gemeinten Schalter kurz hervor, und der Link
  überlebt einen nötigen Login-Umweg. Auch die Fußzeile jeder E-Mail führt mit
  „Mein Konto" jetzt direkt zu den Zustellungs-Einstellungen. (#747)
- - Die interne Bild-Ablage des Social-Bots nimmt jetzt auch andere Kennungen
  als ein Datum entgegen — Fundstücke, Beschluss-Karten und Sitzungstag-Stories
  brauchen jeweils eigene. (#652)
- **Auch große Merklisten bleiben jetzt übersichtlich.** Gemerkte TOPs und
  Beschlüsse werden nach Sitzung gebündelt und zunächst kompakt dargestellt.
  Eine Suche und die Filter „Offen“, „Entschieden“ und „Sitzungen“ führen direkt
  zum gesuchten Eintrag. Unterschiedlich lange Karten richten ihren
  Benachrichtigungsbereich außerdem sauber am unteren Rand aus. (#767)
- **Gemerkte TOPs benennen die Wartephase nach einer Sitzung jetzt eindeutig.**
  Solange das öffentliche Protokoll noch nicht vorliegt, steht in der Merkliste
  „Sitzung vorbei · Protokoll ausstehend“ statt des ungenauen „Ergebnis folgt“.
  (#764)
- **„Mitreden" ist jetzt eine Seite statt dreier.** Der Haushalts-Bereich war
  auf neunzehn Schritte gewachsen, und mehrere davon waren entlang unserer
  Einlese-Geschichte geschnitten statt entlang der Frage, die jemand hat. Wann
  über den Haushalt entschieden wird, worüber die Fraktionen gestritten haben
  und was passiert, wenn man selbst an den Stellschrauben dreht — das ist eine
  Frage und steht jetzt unter *ratslotse.de/haushalt/mitreden* als drei
  Abschnitte mit einer Navigation am Kopf. Nichts ist weggefallen, alte Links
  leiten weiter. Nebenbei repariert: Der Gewerbesteuer-Hebesatz im
  Haushalts-Labor stand als feste Zahl im Code, obwohl die Seite die
  Hebesatz-Reihe als Quelle nannte — er kommt jetzt wirklich von dort und wird
  nicht mehr still veralten. (#698)
- **Beschlussorte werden auf der Stadtkarte sichtbar und prüfbar.** Ein Klick
  öffnet das Ortsprofil oder eine exakt auf Straße, Gebäude, Platz oder Gewässer
  gefilterte Beschlussliste. Im Admin-Bereich lassen sich häufige Ortskandidaten
  anhand von Beschluss-Stichproben als Katalogort freigeben, einem bestehenden
  Ort als Alias zuordnen, verwerfen oder erneut öffnen. Die offene Liste beginnt
  ab drei verschiedenen Beschlüssen; geprüfte Einträge bleiben immer sichtbar.
  Freigegebene Kandidaten und ihre Aliase verwenden Beschlusssuche, KI-Frage,
  Ortsprofile, Quiz und künftige Beschlussimporte über denselben
  Laufzeitkatalog. (#778)
- **Der Fraktions-Filter im Personen-Verzeichnis führt Fraktionen, keine
  Zusammenschlüsse.** „Mitglied der Gruppe FDP/Volt" ist niemand — man gehört
  der FDP an oder Volt. Wer ausschied, während es die Gruppe noch gab, blieb im
  Verzeichnis trotzdem für immer „FDP/Volt", und der Filter zeigte unter diesem
  Eintrag nur ihn statt aller FDP-Leute. Jetzt löst das Verzeichnis solche
  Gruppen-Label auf — belegt über die Ratsinfo-Stammdaten oder die eigene
  Anwesenheits-Historie, nicht geraten: Dr. Christiane Ratjen-Damerau und Benno
  Schulz stehen als FDP, Jens Lükermann als Volt. Wo sich nichts belegen lässt,
  bleibt das Gruppen-Label auf der Karte stehen, die Person erscheint im Filter
  aber unter beiden Parteien. Eigenständige Gruppen — „Für Oldenburg",
  „IBO/LiVe", „WFO-LKR" — bleiben, was sie sind. **Ein Verein ist keine
  Ratsgruppe.** „Gemeinsam für Oldenburg e.V." wurde als Ratsgruppe „Für
  Oldenburg" gelesen und machte einen Verbandsvertreter zum Gruppenmitglied.
  (#699)
- **Die Balken auf „Muss oder kann?" sind jetzt ablesbar.** Der Größen-Balken
  jedes Bereichs maß bisher den Anteil am größten Bereich — ein Maßstab, der
  nirgends auf der Seite stand. Jetzt zeigt er den Anteil an allen geplanten
  Ausgaben, und genau diese Zahl steht als Text an seinem Ende („32 % aller
  Ausgaben"). Der zweite Streifen, die Spielraum-Angabe der Stadt, war in 9 von
  10 Bereichen einfarbig und ohne Legende nicht zu entschlüsseln; er entfällt
  dort, wo der Satz dieselbe Auskunft trägt, und wird zur richtigen Grafik mit
  Legende und Beträgen, wo die Angaben sich wirklich über mehrere Stufen
  verteilen. (#722)
- **Die Produktkarte öffnet sich, statt eine zweite darunter zu setzen.** Beim
  Antippen klappte der Steckbrief bisher als eigene Karte unter der angetippten
  auf — zwei Kästen für eine Sache. Jetzt sind es einer: derselbe Rahmen um Kopf
  und Inhalt, eine Haarlinie dazwischen. (#629)
- **Prüfung und Kennzahlen stehen jetzt nebeneinander.** „Die Prüfung" und „Die
  dreizehn Zahlen" waren zwei Schritte, beantworten aber dieselbe Frage aus zwei
  Richtungen: Wie ist es gelaufen — von außen geprüft, von innen
  zusammengefasst. Unter *ratslotse.de/haushalt/pruefung* stehen beide als
  Abschnitte einer Seite. Nebeneinander sind sie mehr wert als hintereinander:
  Die Kennzahlen sagen, wie die Stadt dasteht, die Feststellungen, wie
  verlässlich diese Auskunft ist. (#700)
- **Die Beispielfragen in „Frag den Rat“ zeigen jetzt auch Stadtteil- und
  Projektrecherchen.** Im leeren Chat wechseln allgemeine Fragen zu Eversten,
  Osternburg und zum Innovationsquartier Alte Fleiwa sowie zum jüngsten
  Beschluss in Kreyenbrück durch den bestehenden Vorschlagspool. (#805)
- **Das Quellenverzeichnis zählt jetzt Papiere, nicht Kategorien.** Über sieben
  Wirtschaftsplänen aus sieben Eigenbetrieben stand „1 Quelle" — nach der alten
  Regel richtig gerechnet, denn nummeriert wurden Quellen*arten*. Trotzdem war
  es die falsche Auskunft: Wer die Zeile liest, soll sehen, worauf eine Seite
  ruht. Jetzt trägt jeder Betrieb seine eigene Ziffer, das Verzeichnis nennt
  sieben Quellen, und die Beschreibung der Quellenart steht weiterhin genau
  einmal darüber. Wo eine Aussage dagegen auf mehreren Papieren zusammen ruht —
  die Produktebene verteilt sich auf zehn Teilhaushalts-Anlagen —, bleibt es bei
  einer Nummer; eine davon herauszugreifen wäre weniger genau, nicht mehr.
  Außerdem behoben: Drei Belege auf zwei Seiten zeigten auf Quellen, die ihre
  Seite nie angemeldet hatte, und rendeten deshalb gar nichts — die Sätze
  endeten mit einer Fußnote, die es nicht gab. Umgekehrt führte die Prüfungs-
  Seite eine Quelle im Verzeichnis, von der keine einzige Zahl der Seite stammt.
  (#690)
- **Die Haushalts-Frage nach der Kostendeckung fragt jetzt nach Millionen.**
  Bisher war zu raten, welcher Bereich den größten Teil seiner Ausgaben durch
  eigene Einnahmen deckt — eine Quote, die ein Ziel behauptet, das es nicht
  gibt: Straßen, Kultur und Grünflächen sollen sich nicht selbst finanzieren.
  Gefragt wird stattdessen, welcher Bereich selbst am meisten einnimmt, in
  Millionen Euro; die Auflösung sagt dazu, was die Haushaltsübersicht offenlässt
  — nämlich wie viel davon von Bund und Land kommt und wie viel aus Gebühren.
  Die Diagramme der Quiz-Auflösung zeichnet außerdem derselbe Grafik-Baukasten
  wie den Haushalts-Bereich: Balken mit sichtbarer Skala statt schwebender
  Streifen, eine Zeitreihe mit Achse und Ablesehilfe statt einer nackten Linie,
  und der Anteil als Leiste statt als Kreis. (#584)
- - Der Rechercheplan verknüpft Informationsbedarfe mit den dafür notwendigen
  Ratslotse-Kanälen. Debatten, Presse und kommende Beratungen werden nur noch
  gesucht, wenn der gültige Plan sie braucht; bei einem ungültigen Plan bleibt
  das bisherige Verhalten als sicherer Fallback erhalten. „Aktuelle
  Informationen“ werden feiner in offizielle Veröffentlichungen und zukünftige
  Termine getrennt; eine reine Zukunftsfrage zieht dadurch keine Pressekarte
  mehr hinzu. (#796)
- **Die Sammel-Mail zeigt jetzt alles.** „n Neuigkeiten aus dem Rat" war bisher
  eine nackte Linkliste. Jetzt erklärt die Mail, warum gebündelt wird — damit
  das Postfach ruhig bleibt, statt vieler Einzel-Mails —, und jede Neuigkeit
  steht mit dem vollen Inhalt ihrer Einzel-Mail darin: Sitzungstermin und Ort,
  die Zusammenfassung der Tagesordnungspunkte und die Wege in die App. (#747)
- **Die Punkte im Kopf der Haushalts-Seiten führen jetzt irgendwohin.** Der
  Schritt-Pfad oben rechts zeigte bisher nur, wo im Weg man steht — angeklickt
  landete man immer beim Wegweiser, egal auf welchem Punkt. Jetzt ist jeder
  Punkt der Link auf seinen Schritt: Wer darauf zeigt, liest den Titel der Seite
  dahinter, und ein Klick geht direkt hin. Die Zeile darunter („Schritt 5 von 12
  · Die Zahlen") bleibt und führt weiter zur ganzen Liste. (#754)
- **Jeder Schritt des Haushalts-Wegs trägt jetzt ein eigenes Zeichen.** Es steht
  als Kachel oben auf der Seite, klein in den Zeilen des Wegweisers und im
  „Weiter"-Link am Seitenfuß — dieselbe Form an allen drei Stellen, damit man
  eine Seite wiedererkennt, statt zwölf Titel zu vergleichen. Nebenbei füllt die
  Kachel die leere Ecke rechts neben dem Einleitungstext, die auf breiten
  Schirmen bisher einfach frei blieb. (#723)
- **Die Schwankungs-Grafik sagt jetzt, was sie misst.** Über zwei Balken mit
  13,2 % und 2,8 % stand „Veränderung zum Vorjahr, im Mittel 1998–2025" — das
  ließ sich als „die Gewerbesteuer ist um 13,2 % gestiegen" lesen oder als „über
  den ganzen Zeitraum um 13,2 % gewachsen". Gemeint ist keins von beidem: Der
  Balken zeigt, wie weit das Aufkommen in einem durchschnittlichen Jahr
  ausschlägt, nach oben wie nach unten. Der Lesesatz steht jetzt über den Balken
  statt als Fußnote darunter, und was die Zahl nicht ist, steht ausdrücklich
  dabei. (#740)
- **Die KI-Frage kennt jetzt Sitzungen.** „Was hat der Jugendhilfeausschuss am
  17.06.2026 beschlossen?" beantwortete die Ähnlichkeitssuche bisher mit ihren
  besten Treffern — bei einer echten Nutzerfrage fehlte so die halbe
  Tagesordnung, darunter ein echter Beschluss. Nennt die Frage jetzt ein
  Sitzungsdatum oder die letzte/nächste Sitzung eines Gremiums, wird die Sitzung
  im Sitzungskalender aufgelöst und ihre Beschlüsse gehen vollständig und in
  Tagesordnungs-Reihenfolge in die Antwort ein. Steht die Sitzung noch bevor
  oder ist ihr Protokoll noch nicht ausgewertet, sagt die Antwort das ehrlich —
  samt Termin und Tagesordnung, statt Beschlüsse anderer Sitzungen
  unterzuschieben. Bei vergangenen Sitzungen erklärt sie dabei auch, dass die
  Stadt Protokolle in der Regel erst einige Wochen nach dem Termin
  veröffentlicht — das Fehlen ist der normale Ablauf, kein Fehler. (#730)
- **Der Sortier-Umschalter der Bereichslisten sagt, dass er sortiert.** „Nach
  Ausgaben" und „nach Kosten für die Stadt" klangen wie zwei Wörter für
  dasselbe, und der Schalter sah aus, als würde er die Ansicht wechseln — dabei
  ordnet er nur die Zeilen um. Jetzt steht „Reihenfolge" davor, und die Optionen
  sind ein Verb-Paar, das den Unterschied trägt: „was ein Bereich ausgibt" gegen
  „was die Stadt zuschießt". Die Balken-Legende spricht dieselbe Sprache — der
  dunkle Teil heißt „schießt die Stadt zu (allgemeiner Topf)", der helle „nimmt
  der Bereich selbst ein" — statt wie bisher denselben Wert dreimal anders zu
  benennen. (#718)
- **Das Ende des Steuer-Steckbriefs liest sich nicht mehr wie eine Textwüste.**
  Wo bisher zwei gleich aussehende gestrichelte Kästen untereinanderstanden —
  „Was brächte ein Punkt mehr?" und „Dazu hat der Rat entschieden" —, steht
  jetzt ein Block „Was hier (noch) nicht steht" mit zwei Einträgen, jeder mit
  eigenem Zeichen und Überschrift. Beide sagen dasselbe: was wir an dieser
  Stelle nicht belegen können. Das gehört zusammen und nicht zweimal
  hintereinander. (#713)
- **Die Tabellen im Streit-Abschnitt sind jetzt als Tabellen lesbar.** Bei „Was
  in den Listen stand" wanderte die Grenze zwischen Ertrag und Aufwand je nach
  Füllung der Zeile — jetzt ist es eine echte Tabelle mit einem Spaltenraster,
  Spaltenlinien und einem Kopf, der beim Scrollen langer Listen sichtbar bleibt;
  die Summe der Liste ankert die Spalten am Fuß. Pluswerte sind grün, Minuswerte
  orange — die Farbe zeigt die Richtung der Änderung, kein Urteil. Und die
  Verhandlungsbilanz erklärt ihre Zahlen selbst: Aus der kryptischen
  Doppelspalte „Ein · durch" wurden zwei beschriftete Spalten „Eingebracht" und
  „Mit Mehrheit", mit Linien dazwischen. (#745)
- **„Meine Themen" und die Ausschuss-Abos sind jetzt zwei Seiten.** Die Abos
  hingen als Block unter den Themen: Wer sie ändern wollte, musste an allen
  Themen vorbeiscrollen, und die Themen bekamen nur so viel Platz, wie darüber
  übrig blieb. Jetzt hat jede der beiden Arten, dem Rat zu folgen — ein Anliegen
  oder ein ganzes Gremium — ihre eigene Seite und ihren eigenen Weg in der
  Navigation. **Die Themen zeigen, was drinsteht.** Eine Themen-Karte trug
  bisher eine Zahl und einen einzigen Titel; wer wissen wollte, was sich getan
  hat, musste jedes Thema einzeln öffnen. Jetzt stehen die fünf jüngsten
  Beschlüsse direkt auf der Karte — mit Datum, Gremium und Ergebnis, die noch
  ungelesenen mit einem Punkt davor. Dazu eine Zeile, die sagt, ob ein Thema
  gerade läuft oder ruht („12 gesamt · 3 in 30 Tagen"), und ein Thema ohne
  Treffer nennt offen den Tag, seit dem es beobachtet wird. **Die Abo-Seite
  sagt, worauf man sich einlässt.** Neben jedem Gremium stehen die nächste
  Sitzung und die Zahl seiner Beschlüsse in diesem Jahr; abonniert und offen
  sind zwei getrennte Listen. Gremien ohne angekündigten Termin zeigen keinen —
  statt einen zu erfinden. (#821)
- **Ein neues Thema kennt seine Beschlüsse sofort.** Bisher zählte nur ein
  wöchentlicher Lauf, welche Beschlüsse zu einem Thema gehören — wer am Montag
  „Schulbegleitung" anlegte, sah bis Sonntag eine 0 und darunter den Satz „Noch
  keine Treffer, wir melden uns, sobald der Rat dazu entscheidet". Dabei hatte
  der Rat seit 2018 vierunddreißigmal dazu entschieden; es las sich, als sei das
  Thema erst mit dem Anlegen aufgekommen. Jetzt wird beim Anlegen und nach jeder
  Änderung der Beschreibung sofort gerechnet, mit demselben Maß wie bisher — die
  Zahl auf der Karte und die Liste hinter „alle ansehen" stimmen vom ersten
  Moment an überein. Der so gefundene Bestand gilt dabei ausdrücklich nicht als
  Neuigkeit: Er taucht weder als „n neu" auf dem Thema auf noch sonntags im
  Wochenüberblick. Und wenn die Rechnung einmal ausfällt, sagt die Karte
  „Treffer werden noch gezählt", statt eine 0 zu zeigen, die wie ein Befund
  aussieht. (#818)
- - Die Wochen-Vorschau wählt ihre Tagesordnungspunkte besser aus: Sie
  berücksichtigt jetzt, ob die Verwaltung etwas zur Entscheidung vorlegt oder
  nur berichtet. Bisher fielen echte Beschlüsse wie die Fahrpreis-Anpassung im
  Nahverkehr durch, während ein Bericht zum Umsatzsteuerrecht auf der Karte
  stand. - Mehrere Stationen desselben Vorhabens („Bauleitplanung Meerweg" mit
  Aufstellungsbeschluss und Grundzügen der Planung) belegen nur noch einen Platz
  statt drei. Sammel-Rubriken wie „Anträge der Fraktionen" bleiben getrennt —
  dort ist jeder Punkt ein eigenes Thema. - Die Vorschau nennt jetzt, wie viele
  Themen eine Sitzung insgesamt hat, nicht nur wie viele davon als besonders
  relevant gelten. (#647)
- **Nummern-Verschiebungen stehen nur noch einmal da.** Fällt in einer
  Tagesordnung oben ein Punkt weg oder kommt einer dazu, rutscht der ganze Rest
  um eine Nummer — „Zuletzt geändert" und die Änderungs-Mail trugen dafür bisher
  ein Dutzend gleichlautender Zeilen, zwischen denen die eigentliche Änderung
  unterging. Solche Kaskaden werden jetzt zu einer Zeile zusammengefasst („14
  Punkte rücken eine Nummer nach vorn — jetzt TOP Ö 21 bis Ö 33"). Punkte, die
  wirklich an eine andere Stelle wandern, behalten ihre eigene Zeile. (#756)
- **Ein Tipp aufs ⓘ zeigt, was dort passiert ist.** In den Zeitreihen des
  Haushalts-Bereichs erscheint die Erklärung zu einem markierten Jahr jetzt in
  der Wertzeile unter der Grafik, sobald man das Jahr antippt, überfährt oder
  mit den Pfeiltasten ansteuert — auf dem Handy bleibt sie beim Wischen
  sichtbar. Die doppelte Textliste unter jeder Grafik entfällt dafür. (#621)
- **Die Anmerkungen der Zeitreihen stehen jetzt als Chips über der Grafik.**
  Jede markierte Stelle trägt einen antippbaren Chip mit Jahr und Kurzfassung —
  auf jeder Bildschirmgröße lesbar, weil die Zeile umbricht statt im Bild zu
  kollidieren. Chip und ⓘ-Marke wählen beide das Jahr; der ganze Erklärsatz
  erscheint dann in der Wertzeile. (#622)
- **Der Zuwendungs-Block auf „Woher das Geld kommt" sagt jetzt zuerst, worum es
  überhaupt geht.** Neben der Summe steht, was eine Zuwendung ist — Spenden und
  Schenkungen an die Stadt, Geld ebenso wie Sachen, und warum jede einzelne
  davon ein Gremium beschließen muss. Dazu ein Absatz darüber, dass diese Summe
  sonst nirgends getrennt ausgewiesen wird. Die Erklärstücke stehen auf breiten
  Schirmen zweispaltig statt als schmale Textspalte in einer halb leeren Karte;
  die Jahreskurve steht unter ihrer Kennzahl statt über die halbe Seite gezogen.
  (#719)

### Verbessert
- **Das Flussbild zeigt wieder eine Grafik — und sagt dazu, von wann sie ist.**
  Für Jahre ohne Jahresabschluss stand zuletzt nur ein Hinweis und sonst
  nichts. Jetzt steht dort das jüngste Jahr, für das die Aufschlüsselung
  vorliegt, mit einer Ansage darüber: welches Jahr fehlt, warum, und wann es
  üblicherweise vorgelegt wird. Der Termin kommt aus denselben Daten wie der
  Datenstand am Seitenfuß — für den Jahresabschluss 2025 also „September
  2026". (#PR)

### Behoben
- **Aufräumen im Fundament des Haushalts-Bereichs**, ohne sichtbare Folgen,
  aber gegen Fehler, die sonst beim nächsten Ausbau entstanden wären: Die
  Einlese-Pipelines fragen ihre Datenart jetzt an einer Stelle statt an zweien
  (vorher konnte eine Änderung an der einen von der anderen still ignoriert
  werden); fünf Beschreibungen desselben Herkunfts-Formats sind zu einer
  geworden, nachdem drei von ihnen bereits auseinandergelaufen waren; und die
  Breitenmessung der Diagramme steht einmal statt viermal. (#567)
- **Ein Testwächter fiel, weil zwei Änderungen sich nicht kannten.** Der
  Wächter über den Haushalts-Bereich prüfte, dass die Geld-Abfragen der
  KI-Frage abgesichert laufen — und suchte sie an der Stelle, an der sie beim
  Schreiben standen. Parallel zog eine andere Änderung sie an einen besseren
  Ort. Die Absicherung war die ganze Zeit da, der Wächter schlug trotzdem an.
  Er prüft jetzt die Eigenschaft statt den Ort. Nebenbei stimmen die Angaben
  „elf Schritte, vierzehn Seiten" wieder mit dem überein, was der Bereich
  tatsächlich hat. (#552)
- **Vier weitere Stellen im Haushalts-Bereich ließen die halbe Breite leer.**
  Auf „Woher das Geld kommt", „Was kostet eigentlich …?" und im Städtevergleich
  standen je zwei Absätze untereinander, die Verschiedenes sagen — zusammen
  nutzten sie rund 600 von 1136 Pixeln, während Karten, Listen und Zitate
  direkt darunter die volle Breite nahmen. Dieselbe Karte behauptete damit zwei
  verschiedene Textbreiten. Sie stehen jetzt nebeneinander, sobald der Platz für
  zwei vollwertige Lesespalten reicht; im Städtevergleich rückt der Beleg aus
  dem Ratsinformationssystem neben das Argument, das ihn ankündigt, und die drei
  Vergleichsstädte stehen nebeneinander statt untereinander — sie sind der
  Vergleich, um den es dort geht. Die Zeilenlänge bleibt überall zwischen 62 und
  74 Zeichen: breiter zu setzen hätte den leeren Platz gefüllt und das Lesen
  verschlechtert. Ob zwei Spalten passen, entscheidet der Platz des Blocks
  selbst und nicht die Fensterbreite — am Desktop liegt er neben der
  Seitenleiste, auf dem Tablet nicht. Die übrigen elf durchgesehenen Seiten
  bleiben unverändert: Dort steht je ein einzelner Absatz über einer Grafik,
  und das ist die richtige Form. (#557)
- **Der Erklärblock zum Finanzausgleich ließ die halbe Karte leer.** Zwei
  Absätze, die Verschiedenes sagen, standen untereinander und brachen bei
  74 Zeichen um — daneben blieb Platz. Sie stehen jetzt auf breiten
  Bildschirmen nebeneinander. Die Zeilenlänge bleibt: breiter zu setzen wäre
  schlechter zu lesen, nicht besser. (#PR)
- **Der Kopf einer Bereichsseite ließ die halbe Breite leer.** Text und
  Kennzahlen standen untereinander, obwohl die drei Zahlen daneben Platz
  gehabt hätten. Ab großen Bildschirmen stehen sie jetzt nebeneinander. Die
  Absätze behalten ihre Zeilenlänge von 66 bis 68 Zeichen — längere Zeilen
  wären schwerer zu lesen, nicht besser. (#PR)
- **Was einzelne Aufgaben kosten, endete bei 2023 — obwohl die Pläne längst
  vorlagen.** Die Stadt hat mit dem Haushaltsplan 2025 zwei Zeilen in ihre
  Tabellen eingezogen: Zwischen „21. ordentliches Ergebnis" und den Zahlen
  stehen seitdem „Jahresüberschuss(+)" und „/Jahresfehlbetrag (-)". Der Parser
  suchte die Kolonne direkt hinter der Beschriftung, fand sie nicht mehr — und
  weil ohne diese Zeile die Rechenprobe *Erträge − Aufwendungen = Ergebnis*
  nicht aufgeht, fiel jedes einzelne Produkt der betroffenen Jahrgänge durch:
  0 von 78 und 0 von 89. Gesucht wird jetzt vorwärts bis zur Zahlenkolonne,
  aber nur bis zur nächsten Tabellenzeile — ist die eigene Zelle leer, bleibt
  sie leer, statt sich die Zahlen des Nachbarpostens zu borgen. Damit kommen
  die Jahrgänge 2024 und 2025 dazu (131 Produkte, 19 Teilhaushalte); an den
  Jahrgängen 2018–2023 ändert sich keine einzige Zahl. Der Job, der die Lücke
  gemeldet hat, meldet sie nicht mehr. (#548)
- **Der Nach-oben-Knopf saß auf dem Tablet hinter der Tab-Leiste.** Er rückte
  schon ab 768 Pixeln nach unten, obwohl die Leiste erst auf echten Desktops
  verschwindet — also auf jedem Tablet und jedem großen Touch-Gerät genau in
  ihren Bereich. Jetzt hängt seine Position am selben Punkt wie die Leiste
  selbst. (#PR)
- **Die Überschrift der Anzeigetafel brach mitten im Wort um.** „Oldenburg plant
  883,9 Mil-/lionen Euro" — dabei blieben rechts daneben rund 400 Pixel frei.
  Ursache war eine Breitenbegrenzung von 19 Zeichen, die noch aus einer engeren
  Fassung stammte; die Silbentrennung, die auf schmalen Geräten deutsche
  Komposita rettet, tat dann ihr Übriges. Der Satz steht jetzt in zwei
  ausgeglichenen Zeilen. (#539)
- **Der Kassenzettel erklärte etwas, das niemand erklärt bekommen muss.** „Keine
  Rechnung — niemand überweist diesen Betrag" stand im Kasten „Was diese Zahl
  nicht ist". Dass eine Pro-Kopf-Zahl keine Forderung ist, weiß jede Leserin;
  der Hinweis las sich belehrend. Geblieben sind die vier Punkte, die
  tatsächlich überraschen — wer mitgezählt wird, woher das Geld kommt, dass
  keine Investition darin steckt und warum Städtevergleiche hinken. (#532)
- **Der Herkunfts-Nachweis konnte eine ganze Datenschicht still verlieren.**
  Das Aufräumen der Herkunfts-Einträge und die Meldung fehlender Herkünfte
  gingen beide eine von Hand gepflegte Tabellenliste durch. Eine neue
  Datenschicht, die dort vergessen wird — der Eintrag ist ausdrücklich Schritt
  drei für einen neuen Parser —, war für beide unsichtbar: Ihre Herkünfte
  galten als verwaist und wurden gelöscht, während ihre Zeilen weiter auf
  deren Nummern zeigten, und die Lücken-Meldung schwieg dazu. Weil die Nummern
  danach neu vergeben werden, zeigte so eine Zeile am Ende nicht ins Leere —
  das wäre aufgefallen —, sondern auf ein **fremdes Dokument**. Beides fragt
  jetzt das Datenbankschema statt der Liste; eine vergessene Tabelle ist damit
  nicht mehr stillgestellt, sondern meldet sich. Aufgefallen ist es am
  Gesamtabschluss auf der Testumgebung, wo die Jahrgänge 2014–2020 als Quelle
  einen Teilhaushalts-Plan auswiesen; die Jahrgänge sind neu eingelesen und
  nennen wieder ihren Prüfbericht. (#537)
- **Die Vergleichsseite nannte den Jahresversatz noch als offene Frage.** Sie
  ist mit #516 beantwortet: Der offene Datensatz der Stadt beschriftete die
  Steuerkraft ein Jahr zu früh, nachgewiesen an den eigenen Büchern der Stadt.
  Beide Reihen tragen jetzt dieselbe Jahresangabe. Zusammengerechnet werden sie
  weiterhin nicht — sie stammen aus zwei Veröffentlichungen, die sich in
  Nachträgen um kleine Beträge unterscheiden können. (#526)
- **Steuerkraft und Schlüsselzuweisungen standen unter dem falschen Jahr.** Der
  offene Datensatz der Stadt, aus dem wir beide Reihen lesen, beschriftet seine
  Zeilen um ein Jahr zu früh — die Beträge selbst stimmen, nur die Jahreszahl
  daneben nicht. Damit nannte die KI-Frage zu einer richtigen Zahl das falsche
  Jahr, und auf der Seite „Woher kommt das Geld?" stand der Betrag des
  laufenden Ausgleichsjahres unter dem Vorjahr. Wir rücken die Jahreszahlen
  jetzt beim Einlesen zurecht. Belegt ist das doppelt: Die Tabellen des
  Landesamts für Statistik Niedersachsen führen dieselben Beträge auf den Euro
  genau, aber ein Jahr später (geprüft für die Ausgleichsjahre 2016 bis 2026),
  und die Haushaltspläne der Stadt weisen dieselben Summen als abgerechnetes
  Ergebnis des jeweils späteren Jahres aus. Die Pro-Kopf-Spalten des
  Datensatzes zeigen wir nicht mehr an — sie rechnen gegen die Einwohnerzahl
  des zu frühen Jahres. Im Quellenverzeichnis steht die Korrektur samt
  Begründung. (#516)
- **Bei doppelt veröffentlichten Teilhaushalts-Plänen stand die schlechtere
  Quellenangabe an der Zahl.** Sechs Teilhaushalte hängen an zwei Vorlagen —
  dieselbe Datei, ein zweites Mal unter einem anderen Tagesordnungspunkt
  hochgeladen. Welche der beiden Angaben an den Zahlen landete, entschied bis
  jetzt die Sortierreihenfolge, und sie fiel zugunsten der weniger
  brauchbaren aus: „TOP 5 - Anlage III - THH 08" sagt außerhalb seiner Sitzung
  nichts, und am Plan für 2018 stand „2019 THH 08" — die falsche Jahreszahl.
  Jetzt gilt ausdrücklich das zuerst veröffentlichte Dokument, also die Anlage
  der Haushaltsvorlage selbst. **Keine Zahl ändert sich dadurch** (die
  Dokumente sind Byte für Byte gleich, nachgemessen), nur die Angabe daneben.
  Tragen zwei Dokumente einmal wirklich verschiedene Zahlen — ein
  Nachtragshaushalt etwa —, wird das künftig gemeldet, statt still
  überschrieben zu werden. (#515)
- **„Geplant und geworden" behauptete einen Vergleich, den es nicht gab.** Wo
  ein Jahresabschluss keine Planwerte hergibt, machte die Seite aus der
  fehlenden Zahl eine Null und schrieb: „799,1 Mio. € eingenommen — geplant
  waren —, also 799,1 Mio. mehr." Darunter stand eine Überschrift samt Legende
  über einer leeren Grafik. Jetzt nennt die Seite die tatsächlichen Werte und
  sagt, dass die Bezugsgröße fehlt, statt eine Abweichung zu erfinden. (#512)
- **Deckungsgrad der Produktebene mit englischem Dezimalpunkt.** „81.7 %" statt
  „81,7 %" — mitten in einem Text, der sonst durchgehend Komma schreibt. (#512)
- **„Geplant und geworden": Die kleinen Bereiche waren nicht zu sehen.** Auch
  als Euro-Strecke blieben fünf der zwölf Bereiche kürzer als zwei Prozent der
  Breite — zwischen −0,7 und +20,5 Mio. liegt zu viel. Die Grafik misst jetzt
  wahlweise in Prozent des jeweiligen Plans; damit wird die mittlere Strecke
  fünfmal so lang und ein Bereich von 231 Mio. mit einem von 6 Mio.
  vergleichbar. Der Umschalter dreht dabei die Reihenfolge: nach Euro steht
  vorn, wo am meisten Geld anders floss, nach Prozent, wessen Plan am
  weitesten danebenlag. (#507)
- **„Geplant und geworden": Die Abweichung war nicht zu sehen.** Plan und
  Ergebnis lagen auf einer Skala, die bei null begann — bei einem Bereich mit
  6,2 Mio. geplant und 6,3 tatsächlich fielen beide Punkte aufeinander. Die
  Achse misst jetzt den Abstand zum Plan statt der Höhe des Betrags: Der
  Nullpunkt ist „wie geplant", die Strecke zeigt, wie weit es davon abwich.
  Dazu steht die Abweichung auch in Prozent, damit ein großer und ein kleiner
  Bereich vergleichbar sind. Die Beträge selbst stehen unverändert daneben.
  (#506)

- **Kostendeckungsgrad über 100 % wurde falsch erklärt.** Bei „Finanzmanagement
  und Recht" — dort verbucht die Stadt ihre Steuern — stand unter dem Wert von
  518 %, „der Rest" komme aus Steuern und Zuweisungen. Einen Rest gibt es dort
  nicht: Der Bereich nimmt mehr ein, als er ausgibt. Der Satz sagt das jetzt,
  samt Hinweis, dass darin keine besondere Sparsamkeit steckt, sondern die
  Zuordnung der Einnahmen. (#503)
- **Die Wertzeile unter den Grafiken ist auf dem Handy wieder lesbar.** Bei
  Reihen mit vielen langen Namen — etwa den sechs Investitionsarten — rutschten
  Name und Betrag auseinander, und das Euro-Zeichen landete allein auf der
  nächsten Zeile. Jetzt steht auf schmalen Schirmen jeder Eintrag auf einer
  eigenen Zeile, die Beträge untereinander und damit vergleichbar. (#626)
- **Die Abschnitts-Leiste der Haushalts-Seiten bleibt auf dem Handy sichtbar.**
  Auf Seiten mit mehreren Abschnitten (etwa „Mitreden" oder „Der Konzern Stadt")
  schob sich die klebende Abschnitts-Leiste beim Scrollen komplett hinter die
  App-Kopfzeile — am Rechner war sie da, auf dem Handy verschwand sie. Jetzt
  dockt sie unter der Kopfzeile an; die klebenden Tabellenköpfe und die
  Sprungziele der Abschnitte rücken entsprechend mit. (#755)
- **Die Begründungen zu den Haushaltsabweichungen hören da auf, wo sie
  aufhören.** Bei der jeweils letzten erläuterten Position lief der Text im
  Jahresabschluss weiter und nahm ganze Folgekapitel mit — bis zu 7.176 statt
  rund 600 Zeichen, mit Inhalten, die mit der Position nichts zu tun hatten.
  Betroffen war jeder der acht Jahrgänge. (#594)
- **Der Beleg-Hinweis passt jetzt auf den Bildschirm.** Wer einen Beleg
  antippte, bekam ein Fähnchen mit dem ganzen redaktionellen Absatz zur Quelle —
  auf dem Handy reichte es über den Bildschirmrand hinaus und ließ sich nicht zu
  Ende lesen. Jetzt steht dort nur noch, was die Frage beantwortet, wofür man
  angetippt hat: an welcher Stelle des Dokuments die Zahl steht, wann der Rat
  darüber entschieden hat, und der Link dorthin. Alles Weitere steht im
  Quellenverzeichnis, und ein Knopf führt hin. Außerdem richtet sich das
  Fähnchen am Fenster aus statt am Absatz: Es klappt nach unten, wenn oben kein
  Platz ist, und ragt nie mehr seitlich hinaus. (#693)
- **Beratende Ausschuss-Mitglieder werden nicht mehr als Ratsmitglieder
  geführt.** In den Ausschüssen sitzen neben den Ratsleuten Verbände, Beiräte
  und Fachleute mit Rederecht — Fridays for Future, Behindertenbeirat, NABU,
  Jägerschaft, Stadtsportbund, Jugendhilfe-Vertretung. Sie standen bisher im
  Personen-Verzeichnis und in den Badges als Ratsmitglieder, in Ermangelung
  einer Fraktion als „parteilos". Beides ist die falsche Kategorie: Sie gehören
  dem Rat nicht an und stimmen nicht mit ab. Das Verzeichnis führt sie jetzt in
  einem eigenen Abschnitt mit ihrer entsendenden Organisation, ihr Profil sagt
  „Beratendes Mitglied · Fridays for Future Oldenburg" statt „parteilos", und
  ihr Badge in Antworten heißt „beratend" statt „Rat". Unterschieden wird an den
  Anwesenheitslisten: Wer je in einer Ratssitzung als Mitglied geführt wurde,
  hat ein Mandat (87 Personen) — wer nur in Ausschüssen sitzt, berät (237).
  **Die Ratsgruppe WFO-LKR wird als solche erkannt.** Franz Norrenbrock und Dr.
  Hans Hermann Schreier sitzen im Rat, standen aber mangels bekanntem Label als
  „parteilos" im Verzeichnis. (#696)
- **Ein Tagesticket für einen Euro ist kein Beschluss über einen Euro.** Die
  automatische Betragserkennung nahm bisher jede Zahl neben einem Eurozeichen
  als das finanzielle Gewicht eines Beschlusses — auch dann, wenn die Zahl ein
  Preis war („Jahreskarte 324,00 €", „Spontanessen 3,90 €", „1
  Euro-Tagesticket") oder eine Meldeschwelle („Auszahlungen und Aufwendungen bis
  zu 50.000 Euro"). Bei einem Sammelbericht über hundert Kleinbeträge stand
  deshalb die Grenze da, ab der berichtet wird, und nicht das, worüber berichtet
  wird. Das war nie nur eine falsche Zahl auf einer Seite: Der Betrag speist
  auch den Wichtig-Wert und die Ranglisten der größten Finanzbeschlüsse. Die
  Muster unterscheiden jetzt am Fundort, ob eine Zahl je Einheit rechnet, und am
  Titel, ob der ganze Beschluss über Preise geht oder unterhalb einer
  Meldeschwelle berichtet. Gemessen am Bestand: 30 Fehlgriffe entfernt, **kein
  einziger echter Betrag verloren** und keiner verändert. Dass ein Zuschuss
  „jährlich 80.000 Euro" beträgt, macht ihn nicht zum Stückpreis, und ein
  Kaufpreis von 390.585 Euro ist sehr wohl das Volumen eines Beschlusses —
  beides hält jetzt je ein Test fest. Drei Fehlgriffe bleiben stehen, alle unter
  1.001 Euro und alle von derselben Sorte: Fördersätze aus Richtlinien, die wie
  ein Volumen formuliert sind. Sie zu jagen hätte auf „Förderung" oder „bis zu"
  filtern müssen — und das kostete gemessen zwölf echte Beträge, darunter eine
  Ausfallbürgschaft über bis zu 116,5 Millionen Euro. Sie bleiben deshalb da und
  stehen benannt im Code. (#610)
- **Kontaktdaten steckten noch in einer zweiten Kopie.** Der Suchindex hält den
  Text nicht nur als Verweis, sondern als eigene Textstücke — und die stammten
  teilweise noch aus der Zeit vor der Maskierung. Sie werden jetzt beim
  Bereinigen gelöscht und aus dem maskierten Text neu aufgebaut, statt bis zur
  nächsten zufälligen Neuberechnung stehen zu bleiben. (#685)
- **Die Beleg- und Gesetzes-Fähnchen gehen wieder zu, wenn man daneben tippt.**
  Bisher schloss sich das aufgeklappte Fähnchen nur, wenn man dasselbe Zeichen
  noch einmal traf — ein Tipp daneben, was die meisten zuerst versuchen, tat
  nichts. Jetzt schließt jeder Klick außerhalb, und die Escape-Taste tut es
  auch; ein Klick ins Fähnchen selbst lässt es offen, damit sich der Text darin
  markieren und der Link treffen lässt. (#740)
- **Was Oldenburg vom Land bekommt, war um 13 Prozent zu niedrig angegeben.**
  Der kommunale Finanzausgleich hat drei Teile: Zuweisungen für
  Gemeindeaufgaben, für Kreisaufgaben und für staatliche Aufgaben, die die Stadt
  miterledigt (Standesamt, Meldewesen, Bauaufsicht). Der Datensatz der Stadt
  führt nur die ersten beiden — der dritte steht ausschließlich beim Land, und
  uns fehlte er deshalb. Auf „Woher kommt das Geld?“ stehen die drei Teile jetzt
  einzeln nebeneinander, mit der vollständigen Summe darunter: für das
  Ausgleichsjahr 2026 sind das 93,4 statt 82,3 Millionen Euro. Die bisherige
  Zahl bleibt daneben stehen — sie ist nicht falsch, sie zählt nur weniger mit.
  Beide gehen gegen die Bücher der Stadt auf: Für 2023 und 2024 nennt das
  Statistische Jahrbuch auf das Tausend genau denselben Betrag. (#603)
- - Bei Fragen nach dem zuletzt gefassten Beschluss steht die jüngste
  tatsächliche Abstimmungsentscheidung jetzt als fester Antwortanker vor
  Berichten und Kenntnisnahmen. Das verhindert, dass ein älterer Titel mit
  wörtlichem Ortsnamen eine neuere, über Straße oder Einrichtung zugeordnete
  Entscheidung verdrängt. (#792)
- - „Frag den Rat“ verbindet Fragen nach einer Person und einem Ortsbereich nun
  über Sitzung und Tagesordnungspunkt. Belegte Wortbeiträge gehen dadurch beim
  Ortsfilter nicht mehr verloren. - Ausdrückliche Fragen nach den neuesten
  Beschlüssen eines Ortsbereichs zeigen die Quellen jetzt strikt chronologisch
  und unterscheiden echte Entscheidungen von Berichten und Kenntnisnahmen.
  (#790)
- - Unter der Gesprächs-Bühne auf „Fragen" stand am Desktop ein Streifen totes
  Weiß (gemessen 23 px): Die Bühne rechnete ihre Höhe mit einer festen Zahl, die
  den Seitenkopf noch mit seinem inzwischen gestrichenen Untertitel enthielt.
  Kopf und Bühne teilen sich die Seitenhöhe jetzt selbst auf, sodass die Bühne
  immer bis zum Seitenrand reicht. (#657)
- **Die Grundsteuer-Erklärung beschrieb das falsche Rechenmodell.** „Die
  Finanzämter berechnen für jedes Grundstück einen neuen Wert", stand dort, und
  die Messzahl komme „nach bundesweit gleichen Regeln" — beides gilt in
  Niedersachsen nicht. Das Land hat bei der Grundsteuerreform ein eigenes Gesetz
  beschlossen: Gerechnet wird mit der Fläche von Grundstück und Gebäude und
  einem Lage-Faktor, und die Messzahlen stehen im Landesgesetz. Der Steckbrief
  sagt das jetzt so. (#736)
- **Der Steuer-Steckbrief rechnet mit dem Hebesatz, der wirklich galt.** „Was
  brächte ein Punkt mehr?" teilte das Aufkommen bisher durch eine Zahl, die im
  Quelltext stand (439 für die Gewerbesteuer). Sie stimmte nur, weil der Rat den
  Satz seit 2015 nicht angefasst hat — der nächste Beschluss hätte den
  Überschlag still falsch gemacht, während die richtige Reihe seit dem Einlesen
  von Tabelle 1105 direkt daneben stand. Jetzt kommt der Satz aus den Daten, und
  zwar der, der im Jahr des Aufkommens galt; der ausgeschriebene Rechenweg nennt
  dieses Jahr jetzt mit. Ebenfalls behoben: Der Hinweis, dass der Rat die
  Erhöhung für 2026 abgelehnt hat, verschwindet künftig von selbst, sobald ein
  neueres Haushaltsjahr im Bestand steht — bisher hätte er auch 2027 noch
  „Haushalt 2026" behauptet. (#659)
- **Eine Zahl ohne Beleg meldet sich jetzt selbst.** Der Cron, der die
  Haushaltsdaten nachzieht, zählte schon immer die Zeilen mit, die in der
  Datenbank stehen, ohne zu sagen, woher sie kommen — geschrieben hat er den
  Befund aber nur ins Log, nie in die Hinweis-Mail. Damit blieb ausgerechnet die
  stillste Lücke stumm: Ein fehlender Jahrgang fällt in jeder Jahresliste auf,
  eine Zahl ohne Herkunft nicht. Sie steht auf der Seite wie jede andere, nur
  ohne Beleg hinter dem Chip. (#660)
- **„Tatsächliches Jahresergebnis" zeigte die falsche Zahl.** Auf der Seite
  „Geplant und geworden" stand dort das *ordentliche* Ergebnis — für 2024 also
  +34,6 statt +6,1 Millionen Euro. Die 28,5 Millionen dazwischen sind das
  außerordentliche Ergebnis, das die Kachel unterschlug. Jetzt steht dort die
  Zahl, die auch im Jahresabschluss unter „Jahresergebnis" steht. (#601)
- **Die Kacheln der Haushalts-Flächen zeigen keine Zeigerhand mehr, wo nichts zu
  klicken ist.** Über „Woher das Geld kommen soll" und über der Kachelfläche des
  Investitionen-Explorers wurde der Mauszeiger zur Hand — dem Zeichen, hinter
  dem eine andere Seite liegt. Dort lag keine: Was eine Kachel zu sagen hat,
  steht in der Zeile unter dem Bild, und die füllt sich schon beim Überfahren.
  Der Zeiger versprach damit ein Ziel, das es nicht gibt. Jetzt trägt die Hand
  nur noch die Kachel „+ n weitere Vorhaben", die tatsächlich irgendwohin führt:
  in die Suche. Am Ablesen selbst ändert sich nichts — Überfahren, Antippen und
  Tab zeigen Namen und Summe weiter wie bisher. (#720)
- - Die Wochen-Vorschau liefert die Kurzfassung und den Tragweite-Grund jetzt
  auch für die aufklappbaren Punkte mit. Bisher fehlten sie dort, sodass
  Instagram-Karten aus dieser Liste grundsätzlich ohne Erklärung standen. -
  Läuft eine Sitzung länger als eine Stunde, zeigt das Live-Banner Stunden statt
  Minuten. „seit 134 Minuten" brach die Zeile um und schob den Sitzungsort aus
  der Flucht. (#649)
- **Die Karten zeigen wieder einen sauberen Stadtplan.** Der Kachel-Anbieter
  CARTO verlangt seit Kurzem einen Zugangsschlüssel und legte sonst quer über
  jede Kachel den Schriftzug „API KEY REQUIRED" — auf der Stadtkarte, der
  Ortskarte unter Beschlüssen, der Karte unter KI-Antworten und in beiden
  Quiz-Karten. (#785)
- **Keine alten Debatten unter Zukunfts-Fragen.** Wer nach einer kommenden
  Sitzung fragte, bekam neben der Antwort den Block „Aus den Ratsdebatten" mit
  Wortbeiträgen aus früheren Jahren — zu einer Sitzung, die noch gar nicht
  stattgefunden hat, kann es aber keine Debatte geben. Bei Fragen zu Sitzungen
  ohne ausgewertetes Protokoll bleiben Debatten- und Parteien-Baustein jetzt
  weg; Fragen zu vergangenen Sitzungen behalten beides. (#742)
- **Die nächste Ratssitzung wird nicht mehr als mögliche Haushaltssitzung
  angekündigt.** Unter „Wann der Haushalt entschieden wird" stand bisher der
  nächste Termin von Rat oder Finanzausschuss aus dem Ratskalender — mit
  ehrlichem Kleingedruckten, aber die Schlagzeile versprach im
  Haushalts-Zusammenhang trotzdem eine Haushaltssitzung, die sie meistens nicht
  ist: Der Ratskalender kennt keine Tagesordnungen. An ihrer Stelle steht jetzt
  die Auskunft, die sich belegen lässt — in 7 von 8 Jahrgängen kam der nächste
  Entwurf im Oktober, und welche Sitzung ihn aufruft, steht erst mit deren
  Tagesordnung fest. Auch der Kalender-Pin auf dem Zeitstrahl ist weg; er hängte
  dieselbe beliebige Sitzung an den Haushalts-Weg. (#715)
- - Bei „Konto löschen" auf der Konto-Seite stand das Passwortfeld auf breiten
  Bildschirmen seltsam zum Erklärtext: Auf Ultrawide-Monitoren riss zwischen
  Text und Feld ein großer Leerraum auf, und weil sich beide an der Unterkante
  des Texts ausrichteten, sprang das Feld je nach Zeilenzahl an eine andere
  Stelle. Beides liegt jetzt fest nebeneinander auf Höhe der Überschrift. (#655)
- **E-Mail-Schrift repariert.** Ein Anführungszeichen mitten im Schriftarten-
  Stapel schnitt die Stil-Angaben der Mails ab — je nach Mail-Programm fielen
  damit auch Text- und Hintergrundfarbe weg. (#747)
- **Über Zeilen umbrochene Kontaktdaten rutschten durch.** Steht eine
  E-Mail-Adresse im Dokument über einen Trennstrich umbrochen, sah die
  Maskierung nur ihre erste Hälfte und ließ sie stehen — beim Aufbereiten für
  die Suche wurden die Zeilen dann wieder zusammengezogen, und die vollständige
  Adresse stand im Index. Dasselbe galt für Bankverbindungen, die mitten in der
  Ziffernfolge umbrechen. Beides wird jetzt vorher zusammengezogen und dann erst
  geprüft. (#686)
- - Die vom Social-Bot hochgeladenen Bilder werden jetzt auch ausgeliefert. Sie
  lagen im `public/`-Verzeichnis des Frontends, das Next.js aber nur beim Build
  einliest — der Upload lief, die Adresse gab trotzdem 404, und ein Beitrag wäre
  erst beim Veröffentlichen gescheitert. (#653)
- **Die Merkliste bietet nur noch konkrete Tagesordnungspunkte an.** Reine
  Gliederungs-Oberpunkte wie „Anträge der Fraktionen, Gruppen, Rats- und
  Ausschussmitglieder“ haben kein eigenes Abstimmungsergebnis und können deshalb
  nicht mehr neu gemerkt werden. Bereits vorhandene Merker bleiben sichtbar,
  werden als Sammelpunkt erklärt und lösen keine Ergebnis-Benachrichtigung aus.
  (#763)
- **Wer in den Protokollen unter zwei Namensformen steht, hat wieder ein
  Profil.** Bei drei Personen führen die Anwesenheitslisten zwei Schreibweisen —
  im Verzeichnis standen sie deshalb doppelt, jedes der beiden Profile mit einem
  Teil der Sitzungen, und in den KI-Antworten fiel ihr Badge aus, weil zwei
  gleichnamige Einträge nicht auseinanderzuhalten waren. Jetzt zählen Sitzungen,
  Gremien und Wortbeiträge wieder zusammen: Angezeigt wird die Schreibweise der
  jüngsten Sitzung, die Suche im Verzeichnis findet beide, und ältere Links
  führen weiterhin auf dasselbe Profil. (#589)
- - „Was wurde an diesem Ort zuletzt beschlossen?“ wird jetzt direkt aus Datum
  und Abstimmung beantwortet. Neuere Kenntnisnahmen werden klar als Berichte
  statt als Beschlüsse gekennzeichnet; ein älterer, ähnlich betitelter Vorgang
  kann die Antwort nicht mehr verdrängen. (#795)
- **Zwei gescannte Anlagen ließen sich nicht laden.** Beim ersten Lauf auf dem
  Server wies das Ratsinformationssystem zwei von acht Downloads ab — darunter
  den Wirtschaftsplan des Abfallwirtschaftsbetriebs für 2020, also einen ganzen
  Jahrgang, der dadurch still fehlte. Ursache war eine fehlende Kennung beim
  Abruf; außerdem wird ein abgewiesener Download jetzt bis zu viermal
  wiederholt, statt sofort aufzugeben. (#674)
- **Eine Anlage war zu groß zum Lesen.** Ein Scan von über 30 Megabyte wurde von
  der Texterkennung abgewiesen und blieb als einziger von 227 ungelesen. Solche
  Seiten werden jetzt vorher verkleinert — ohne dass ein Buchstabe verloren
  geht, denn die Vorlage hat ohnehin mehr Auflösung, als für die Erkennung nötig
  ist. (#685)
- **Ein Plan im Großformat brachte die Texterkennung zum Abbruch.** Die Anlage
  zur Verkehrsregelung am Johann-Justus-Weg ist über einen Meter breit; als Bild
  war sie zu groß für die Erkennung, und der Lauf endete jedes Mal mit einem
  Fehler. Solche Seiten werden jetzt schrittweise verkleinert, bis sie passen.
  Bei diesem Plan bleibt am Ende trotzdem kein lesbarer Text übrig — dafür sind
  die Straßenbeschriftungen zu klein —, aber aus einem Abbruch ist eine benannte
  Lücke geworden. (#687)
- **Bei manchen Dokumenten wurde das Briefkopf-Logo gelesen statt der Seite.**
  Wenn eine Seite genau ein Bild enthielt, galt dieses Bild als der Scan — bei
  einem Deckblatt mit Stadtwappen war das aber nur das Wappen. Zurück kamen ein
  paar Zeichen, die aussahen wie ein Ergebnis. Jetzt entscheidet die Auflösung:
  Ein Logo ist um ein Vielfaches kleiner als eine gescannte Seite. Betroffen war
  unter anderem der Schlussbericht des Rechnungsprüfungsamts zum Jahresabschluss
  2024 — das Dokument, für das die Texterkennung überhaupt gebaut wurde. Auch
  seine zweite Hürde ist weg: Sein Titel steht nach dem Briefkopf und nicht ganz
  am Anfang, woran die Erkennung bisher scheiterte. (#675)
- **Drei Dokumente galten als gelesen, ohne gelesen worden zu sein.** Konnte
  keine einzige Seite in ein Bild verwandelt werden, speicherte die
  Texterkennung trotzdem — und zwar den Platzhaltertext, der eigentlich nur
  markieren sollte, dass eine Seite fehlt. Für jeden späteren Lauf sahen diese
  Anlagen damit erledigt aus. Sie stehen jetzt wieder auf der Arbeitsliste und
  werden beim nächsten Durchgang richtig gelesen. (#677)
- **Der Ops-Lauf kennt die neuen Finanzdaten.** Die lange Ausgabenreihe und das
  Statistik-Archiv liefen bisher nur von Hand oder per Cron mit; jetzt zieht ein
  Ops-Lauf sie mit. Der Bestandsbericht am Ende zählt außerdem Finanzrechnung,
  Bilanz und Ausgabenreihe mit — eine Tabelle, die dort fehlt, fällt sonst erst
  auf, wenn jemand eine leere Seite meldet. (#605)
- **Der Ops-Lauf zieht die Wirtschaftspläne der Eigenbetriebe mit ein.** Seit
  sie gebaut wurde, ließ sich die Schicht nur von Hand über SSH füllen; ein Cron
  kommt für sie vorerst nicht in Frage, weil sie als einzige aus einer
  Ratsvorlage liest statt aus einer Anlage. Der Bestandsbericht am Ende zählt
  sie jetzt mit — eine Tabelle, die dort fehlt, fällt sonst erst auf, wenn
  jemand eine leere Seite meldet. Reißt eine der Rechenproben, endet der Lauf
  weiterhin mit einem Fehler, aber erst, nachdem Bericht und Archiv-Sicherung
  durchgelaufen sind. (#664)
- **Der Baustein „Aus den Ratsdebatten" bleibt beim Zurückwechseln stehen.** Wer
  von den Fragen weg und wieder zurück navigierte, sah die verdichteten
  Fraktions-Positionen von vorn laden — allerdings nur nach einer
  Anschlussfrage. Der Grund: Beim Antworten wird aus „Und was kostet das?" eine
  eigenständige Suchfrage verdichtet, und der Baustein merkt sich sein Ergebnis
  unter genau dieser Fassung. Gespeichert wurde bisher nur die Frage, wie sie
  gestellt wurde — das wiederhergestellte Gespräch suchte also unter einem
  anderen Schlüssel, lud neu und fragte dabei obendrein ohne den
  Gesprächskontext. Jetzt wandert die Suchfassung mit in den Gesprächs-Snapshot.
  Außerdem gehört die Zeile „Keine passenden Wortbeiträge gefunden von …" jetzt
  mit zum gemerkten Ergebnis. Sie lag vorher nur im Zustand der Komponente und
  fehlte deshalb selbst dann, wenn die Positionen aus dem Zwischenspeicher
  kamen. (#705)
- **„Das sagen die Parteien" steht jetzt auf allen Redebeiträgen, nicht auf
  einem.** Der Baustein suchte seine Beiträge allein nach Ähnlichkeit zur Frage
  und schnitt das Feld vorher global zusammen — bei der Baumschutzsatzung blieb
  davon je Fraktion ein einzelner Beitrag von 2019 oder 2021 übrig, während CDU,
  BSW und FDP als „keine passenden Wortbeiträge" ausgewiesen wurden, obwohl alle
  drei in der Satzungs-Debatte geredet hatten. Jetzt kommt die Aussprache zu den
  belegten Beschlüssen dazu, und die Auswahl je Fraktion läuft über das ganze
  Kandidatenfeld: aus 7 Fraktionen mit 1–2 Beiträgen wurden 13 mit bis zu 11.
  Schreibvarianten derselben Fraktion („SPD" / „SPD-Fraktion") zählen dabei
  zusammen statt doppelt zu erscheinen. **Personen-Badges in der Quellenspalte
  sitzen zuverlässiger — und doppeln die Fraktion nicht mehr.** Führt das
  Protokoll nur den Nachnamen und gibt es mehrere Personen dieses Namens,
  entscheidet jetzt die Fraktion der Zeile: „Behrens (SPD)" ist damit eindeutig
  Paul Behrens, „Schilling" je nach Fraktion Rita oder Michael. 1.505
  Wortbeiträge bekommen so ihr Badge. Steht die Partei schon auf dem Badge,
  fällt die Wiederholung in Klammern dahinter weg („Woltmann ·CDU (CDU)" →
  „Woltmann ·CDU"); trägt das Badge etwas anderes („ehem.", „Stadt"), bleibt die
  Fraktion sichtbar. (#691)
- **Zwei Ungenauigkeiten in „Frag den Rat" behoben.** Verwaltungsleute, die in
  Anwesenheitslisten mal mit, mal ohne Amtstitel im Namen stehen (z. B.
  „Stadtkämmerin Dr. Julia Figura" statt „Dr. Julia Figura"), bekamen ihr
  „Stadt"-Badge nur inkonsistent — je nachdem, ob im Text zufällig der volle
  Vorname stand. Außerdem hängte der „Wie es weitergeht"-Block bei Adress-Fragen
  manchmal themenfremde Termine an, weil das generische Wort „Straße" allein
  schon als Treffer zählte (z. B. Straßenwidmungen bei einer Stadion-Frage).
  (#650)
- **Dieselbe Person stand zweimal im Personen-Verzeichnis.** Wer in einer
  Anwesenheitsliste einmal anders geschrieben steht — „Klein" statt „Thomas
  Klein", „Georg Hess" statt „Hans-Georg Heß", „Christine Berta Wolff" statt
  „Christine Wolff", seit einer Namensänderung „Tim Ebbeke Harms" statt „Tim
  Harms" —, bekam bisher einen zweiten Eintrag mit eigener Personen-Seite, auf
  die sich die Redebeiträge aufteilten. Diese Schreibweisen zählen jetzt als ein
  Mensch (acht Fälle im Bestand); alte Links auf die weichende Schreibweise
  führen weiter zur selben Seite. Zusammengelegt wird nur bei gleichem
  Nachnamen, gleicher Fraktion und ineinander passenden Vornamen — echte
  Namensvettern wie Meike, Sarah und Thorsten Bruns bleiben getrennt.
  **Personen-Badges sitzen jetzt bei neun von zehn Wortbeiträgen.** Nennt eine
  Protokollzeile nur den Nachnamen, entscheidet neben der Fraktion nun auch das
  Sitzungsjahr, wer gemeint ist: Tanja Behrens saß 2018 eine Sitzung lang im
  Rat, ein „Behrens" von 2025 ist damit zwangsläufig Paul Behrens. Gruppen-Label
  und Einzelpartei gelten dabei als dieselbe Zugehörigkeit („FDP/Volt" trifft
  Daniela Pfeiffer/FDP). Widerspricht die Fraktion der Zeile allen Kandidaten,
  gibt es weiterhin bewusst kein Badge — geraten wird nicht. (#695)
- **Die Personen-Seite lädt wieder schnell.** Um für eine Person zu bestimmen,
  ob sie ein Ratsmandat hat oder beratend in Ausschüssen sitzt, hat die Seite
  seit dem letzten Update das komplette Personen-Verzeichnis mitberechnet — ein
  Scan über alle Anwesenheitszeilen für eine einzige Person. Jetzt zählt nur
  noch, was zu dieser Person gehört: gemessen 14 ms statt 102 ms je Aufruf an
  einem Bestand in Produktionsgröße. **Der Kopf der Personen-Seite nennt
  dieselbe Zugehörigkeit wie das Verzeichnis.** Wo ein Zusammenschluss-Label
  belegt aufgelöst werden kann, steht dort jetzt die Partei („FDP/Volt" → FDP)
  statt der Gruppe. Die Zeitleiste darunter bleibt unverändert quellentreu — sie
  zeigt weiterhin, was in den Protokollen der jeweiligen Zeit stand. (#704)
- **Ein Produkt zu öffnen wirft einen nicht mehr an den Seitenanfang.** Wer in
  der Produktliste weit unten etwas gesucht hatte, landete beim Antippen wieder
  ganz oben und musste seine Stelle neu suchen. Der Steckbrief klappt jetzt
  direkt unter der angetippten Karte auf — es wird gar nicht mehr gescrollt.
  (#628)
- **Ein unlesbares PDF gilt nicht mehr als gelesen.** Der Schlussbericht des
  Rechnungsprüfungsamts zum Jahresabschluss 2024 liefert beim Auslesen 460.000
  Zeichen und keinen einzigen Buchstaben — seiner Schrift fehlt die
  Zeichenzuordnung, herauskommen Glyph-Nummern. Solcher Text landete bisher in
  der Datenbank und damit in der Volltextsuche. Jetzt wird er als „kein Text"
  geführt, und die Prüfungs-Seite sagt weiterhin, dass für 2024 ein Bericht
  existiert, den niemand lesen kann. (#627)
- **Jede Zahl führt jetzt zu ihrem Papier, nicht zur Startseite.** Auf „Der
  Haushalt neben dem Haushalt" standen 33 Wirtschaftspläne aus sieben
  Eigenbetrieben unter einer einzigen Quellenangabe, und deren Link führte auf
  die Startseite des Ratsinformationssystems — zu keinem Dokument, zu keiner
  Suche. Jetzt trägt jeder Betrieb den Link auf seinen eigenen Plan, mit der
  Stelle darin, und das Quellenverzeichnis listet alle benutzten Papiere einzeln
  statt eines Sammelverweises. Dasselbe gilt für die Gebührenbedarfsberechnung,
  wo jeder Bereich seinen eigenen Abschnitt der Anlage nennt, und für den Block
  „Was der Rahmen erlaubt" auf der Schulden-Seite, der seine Zahlen bis dahin
  ganz ohne Beleg zeigte. Die Dokumente selbst heißen im Verzeichnis jetzt nach
  dem, was sie sind („Eigenbetrieb Gebäudewirtschaft: Wirtschaftsplan 2026")
  statt nach ihrem Aktenzeichen. Dazu ein Jahrgang mehr bei den Abfallgebühren:
  2020 liegt nur als Scan vor und schrieb „Gebührenbedarfsrechnung" statt
  „-berechnung" — zwei Silben, an denen das Einlesen scheiterte. (#689)
- **Die Quizfrage nach den Schulden nennt jetzt das Jahr an jeder Zahl.** Die
  drei Stände kommen aus drei Quellen, und die erscheinen zu verschiedenen
  Zeiten — nebeneinandergestellt ohne Jahresangabe war das angreifbar. (#634)
- - Auf „Fragen" sprang am Desktop die Breite von Antwort- und Quellen-Spalte,
  sobald die Antwort eintraf — das Raster richtete sich nach seinem Inhalt statt
  nach der Seite. Beide Spalten stehen jetzt unabhängig vom Inhalt immer an
  derselben Stelle. (#658)
- **Warum die Schulden je Einwohner*in 2023 sanken, obwohl sie stiegen.** In der
  Pro-Kopf-Ansicht der Schuldenkurve steckt ein Sprung, der nichts mit Schulden
  zu tun hat: Die Volkszählung 2022 zählte 4.079 Menschen mehr als bis dahin
  angenommen, und die Statistik rechnet ab da mit der neuen Zahl. Das Jahr sah
  nach Entspannung aus — die Gesamtsumme wuchs im selben Zeitraum. Steht jetzt
  dabei. (#599)
- **Zwei Stellen behaupten nicht mehr, was längst da ist.** Der Kassenzettel auf
  der Haushalts-Übersicht sagte, Neubauten und Fahrzeuge stünden „in einem
  eigenen Haushalt, den wir noch nicht eingelesen haben" — den zeigt „Was wird
  gebaut?" inzwischen samt der einzelnen Vorhaben; geblieben ist der Grund,
  warum sich beide nicht zusammenzählen lassen. Und wo für ein Planjahr kein
  Geldfluss-Bild steht, hieß es, uns lägen die Einnahmearten nicht vor. Sie
  liegen vor; was fehlt, ist die Ausgabenseite im selben Stand — und genau das
  steht dort jetzt. (#659)
- **„Morgen" ist jetzt ein Datum.** „Um was geht es im Bauausschuss morgen?"
  verstand die KI-Frage nicht als Sitzungsfrage — sie riet stattdessen aus alten
  Beschlüssen verschiedener Jahre, was „voraussichtlich" anstehen könnte. Jetzt
  werden „heute", „morgen", „übermorgen", „gestern" und „vorgestern" auf den
  Kalendertag aufgelöst, die Sitzung wird im Sitzungskalender gefunden und die
  Antwort kommt aus deren echter Tagesordnung. Zeitspannen („bis heute", „seit
  gestern") und der Gruß („Guten Morgen") lösen wie bisher nichts aus. (#738)
- **Eine Tabelle in Tausend Euro wird jetzt erkannt statt falsch gelesen.** Die
  Rechenprobe, mit der jede Zahl des Haushalts-Bereichs belegt wird, prüft
  *Erträge minus Aufwendungen gleich Ergebnis*. Läge eine ganze Spalte um den
  Faktor 1.000 daneben, weil über der Tabelle „in TEUR" steht, ginge die Probe
  trotzdem auf — der Faktor kürzt sich weg. Solche Tabellen werden jetzt gar
  nicht erst eingelesen. Lieber eine Lücke als eine Zahl, die tausendmal zu
  klein ist. (#671)
- **Zwei Quellenlinks im Haushalts-Bereich zeigten ins Leere.** Die Stadt hat
  ihre Finanzen-Seite eine Ebene höher gelegt, das Landesstatistikamt seinen
  Realsteuervergleich eine Ebene tiefer. Beide Adressen sind nachgezogen. (#632)
- - Die Tragweite-Bewertung neuer Tagesordnungspunkte lief seit dem 16.08. gar
  nicht mehr: Der tägliche Lauf schloss die Datenbank, bevor er sie dafür
  benutzte, verschluckte den Fehler und meldete sich trotzdem als erfolgreich.
  Die Wochen-Vorschau hob dadurch nach Stichwort-Regeln hervor statt nach
  Tragweite. Ein Lauf, der keinen einzigen offenen Punkt bewerten konnte,
  schlägt jetzt Alarm, statt still „0" zu melden. (#646)
- - Die Tragweite-Bewertung liest die Vorlage jetzt ab dem Sachverhalt statt ab
  dem Briefkopf. Bisher füllten Ausdruckdatum, Amt und Beratungsfolge die Hälfte
  des Auszugs — bei einem Bericht, der in der Sitzung gar nicht gehalten werden
  kann, stand der entscheidende Satz außerhalb und der Punkt galt als Bericht
  mit Ergebnissen. - Tagesordnungspunkte stehen auf der Wochen-Karte wieder in
  der Reihenfolge der Tagesordnung: „Ö 5" kam bisher hinter „Ö 16.4". (#648)
- **Bilanzsummen machen einen Beschluss nicht mehr wichtig.** Wenn der Rat einen
  Jahresabschluss feststellt, stand dort eine sehr große Zahl — bei einem
  Eigenbetrieb über 580 Millionen Euro. Der Wichtig-Wert las sie als Ausgabe und
  schob solche Formalbeschlüsse nach oben. Betroffen waren 259 Beschlüsse, 122
  davon über zehn Millionen. Was der Rat tatsächlich ausgibt, zählt weiter.
  (#596)
- **Die Wirtschaftspläne melden sich künftig selbst.** Die neue Schicht steht
  jetzt im Datenstand des Haushalts-Bereichs: Bleibt der Plan für ein
  Haushaltsjahr aus, sagt der Bereich das — samt dem Monat, in dem er
  üblicherweise eingebracht wird. Nebenbei findet der Volltext-Nachlauf damit
  auch die Anlagen der übrigen Eigenbetriebe, deren Zahlen bisher unerreichbar
  in ungelesenen PDFs lagen; wo ein Dokument nur ein Scan ist, wird es als
  solcher markiert statt stillschweigend übersprungen. (#665)
- **Die Wirtschaftsplan-Erkennung traf nie ein Dokument.** Sie führte drei
  Schreibweisen desselben Worts, verknüpfte sie aber mit UND statt mit ODER —
  ein Dokument hätte alle drei gleichzeitig tragen müssen. Sichtbar wurde das
  nie, weil bisher nur der Anlagen-Nachlader diese Muster las und sich seine
  Oder-Verknüpfung selbst baut. Ein Test geht jetzt für jede Datenart den
  normalen Weg und meldet, wenn eine ihre eigenen Dokumente nicht findet. (#669)
- **Wochenüberblick: Links funktionieren wieder.** Die sonntägliche
  Wochenüberblick-Mail verlinkte ihre Beschlüsse relativ — solche Links kann ein
  Mail-Programm nirgends auflösen, sie taten schlicht nichts. Jetzt führen sie
  als volle Adresse zur Beschluss-Seite; Beschluss-Titel mit Sonderzeichen
  werden dabei sauber dargestellt. (#748)
- **Kurven im Minus liefen aus dem Bild.** Eine Zeitreihe, deren Werte alle
  unter null liegen, zeichnete ihre Achse von 0 bis −3, während die Kurve bis
  −10 ging — sichtbar war nur ein Fragment am linken Rand. Dasselbe traf jede
  Reihe, die sowohl positive als auch negative Werte hat. Beides fiel bisher
  niemandem auf, weil alle Kurven des Haushalts-Bereichs im Plus lagen. Außerdem
  beschriftete die Achse ihre Linien immer ohne Nachkommastellen: Bei Beträgen
  unter einer Million standen dort dreimal „0" und zweimal „1" übereinander.
  (#668)

### Verbessert
- **Der Haushalts-Bereich einmal am Stück gelesen — mit den Augen von jemandem,
  der noch nie einen kommunalen Haushalt gesehen hat.** Die neun Seiten sind in
  zwei Wochen einzeln entstanden; diese Runde ändert keine Zahl und kein
  Feature, sondern das, was zwischen ihnen stand. Aus den sechs gleichrangigen
  Wegweiser-Karten wird ein Weg mit sechs nummerierten Schritten, der bei „Woher
  kommt das Geld?" beginnt und bei der Prüfung endet. Die Balkenleiste auf der
  Übersicht heißt nicht mehr „Woher das Geld kommt" — sie zeigt, welcher
  *Bereich* eine Einnahme verbucht, und weil Steuern zentral in der Kämmerei
  auflaufen, las man dort heraus, das meiste Geld komme aus der Verwaltung
  selbst. Die Einnahmen- und die Produktseite sagen jetzt oben, dass ihre Jahre
  nicht die der Übersicht sind, statt es unten nachzureichen. Zwei Seiten
  behaupteten weiterhin, die Produktebene werde „noch eingelesen" — sie ist seit
  Wochen da und jetzt von dort aus verlinkt. Große Beträge bekommen eine
  Bezugsgröße: die Rücklage steht auch je Einwohnerin und Einwohner, „169,2
  Ausgaben" heißt wieder „169,2 Mio. € Ausgaben". Und der Steuer-Verlauf sagt
  dazu, dass in „das 5,2-Fache" seit 1998 die Teuerung steckt. (#512)
- **Widersprüche zwischen zwei Seiten aufgelöst, statt sie zu übertünchen.**
  Der Steuer-Steckbrief rechnete aus, was ein Hebesatzpunkt Grundsteuer bringt —
  aus einem Betrag, der A und B zusammenfasst, geteilt durch den Hebesatz von
  nur B. Das Haushalts-Labor verweigert genau diese Zahl seit jeher mit
  derselben Begründung. Jetzt tun es beide: Der Steckbrief zeigt statt der Zahl,
  warum es sie nicht gibt. Ebenso heißt ein Minusbetrag im Bereichs-Dossier
  nicht mehr „bleibt der Stadt" (als bliebe ihr etwas übrig), sondern „trägt die
  Stadt" — dasselbe Wort, das die Übersicht dafür benutzt. (#512)
- **Kein Grün mehr im Haushalt.** Ein geplanter Überschuss trug den Erfolgs-Tint
  aus der Beschluss-Semantik und stand damit als gute Note neben dem
  orangefarbenen Minus. Für die Hantel-Grafik ist seit jeher begründet, warum es
  im Haushalt keine Bewertungsfarben gibt; das gilt jetzt auch für die
  Überschuss-Pille und die Ergebnis-Spalte der Zeitreihen-Tabelle. (#512)
- **Das Glossar erklärt die Wörter, über die man wirklich stolpert.** Neu sind
  unter anderem Ansatz, Gesamtermächtigung, Ertrags- und Aufwandsart,
  Ergebnisrechnung, ordentliches Ergebnis, Kernverwaltung, Textziffer und
  Rechnungsprüfungsamt — und das Quellenverzeichnis unter jeder Haushaltsseite
  erklärt sie jetzt an Ort und Stelle, statt sie nur zu benutzen. Die Erklärung
  zu „Erschließung" war dort, wo sie automatisch erschien, teils schlicht
  falsch: Im Steckbrief des Stadtarchivs meint das Wort das Ordnen von
  Beständen, nicht den Straßenbau. (#512)

- **Das Haushalts-Labor sagt jetzt, ob das viel ist.** Bisher bewegte man
  Regler und eine Zahl änderte sich — ohne Maßstab. Jetzt füllt jede Bewegung
  sichtbar einen Anteil der Lücke, und unter jedem Regler steht, was er
  bewirkt: in Millionen, in Euro je Einwohner und als Anteil am Minus. Am
  Hebesatz kommt dazu, was ein Betrieb mit 100.000 € Gewerbeertrag danach
  zahlt. Kürzungen werden in echte Aufgaben übersetzt („ungefähr so viel, wie
  die Kulturgutvermittlung im ganzen Jahr kostet") — aus den
  Teilhaushaltsplänen, immer aus demselben Bereich. Drei Szenarien zum
  Anklicken zeigen die Größenordnungen, „Alles auf Anschlag" auch die
  Obergrenze: Mehr als 39,4 Mio. € geben diese zwei Stellschrauben nicht her.
  Auf dem Handy bleibt das Ergebnis beim Drehen sichtbar.
- **Neu im Labor: „Wie verlässlich ist der Plan?"** Der Ansatz gegen das
  tatsächliche Ergebnis aus den Jahresabschlüssen — in allen fünf
  eingelesenen Jahren fiel es besser aus als geplant, zwischen 2,9 und
  38,1 Mio. €. Damit steht das geplante Minus zum ersten Mal in einem
  Verhältnis, ohne dass es dadurch unecht würde.

### Behoben
- **Zahlen übereinander im Steuer-Verlauf.** Auf dem Steuer-Steckbrief lagen die
  beiden Rückgangs-Marken der Ist-Kurve ineinander und über der Achsenzahl
  daneben — bei den meisten Steuerarten liegen die größten Einbrüche in
  benachbarten Jahren ganz links. Die Beschriftungen bleiben jetzt in der
  Zeichenfläche, weichen sich zeilenweise aus und tragen einen feinen
  Führungsstrich zu ihrem Punkt; Kurve und Fall-Linien schneiden nicht mehr
  durch die Ziffern.

### Verbessert
- **Die drei Wege in die Tiefe sind jetzt zu sehen.** „Woher kommt das Geld?",
  „Muss oder kann?" und das Haushalts-Labor standen als blasse Textkacheln
  zwischen zwei großen Diagrammen und gingen dort unter. Sie tragen jetzt ein
  Piktogramm, ihren Titel in der Display-Schrift und einen Pfeil, der beim
  Überfahren mitgeht — und stehen unter einer eigenen Zeile „Tiefer
  einsteigen".

### Hinzugefügt
- **Geplant und tatsächlich — der Haushalt bekommt seine zweite Hälfte.** Bis
  jetzt zeigte Ratslotse nur, was die Stadt ausgeben *wollte*. Aus den
  Jahresabschlüssen, die als Anlagen längst im Ratsinformationssystem lagen,
  lesen wir nun auch, was daraus geworden ist — für fünf Jahrgänge, samt
  Aufschlüsselung der Einnahmen nach Steuern, Zuweisungen und Gebühren. 2023
  etwa nahm die Stadt 733 Mio. € ein statt der geplanten 665. Dazu kommt die
  Produktebene aus den Teilhaushalts-Plänen: was einzelne Aufgaben kosten,
  von der Kindertagesbetreuung (71,1 Mio. €) bis zum Brandschutz — mit dem
  zuständigen Amt und einer ehrlichen Angabe, wie viel des Haushalts diese
  Liste abdeckt. (#500)

### Hinzugefügt
- **Der Haushalt erklärt sich jetzt selbst.** Vier neue Seiten machen aus
  Zahlenkolonnen eine Geschichte: **Woher kommt das Geld?** zeigt alle
  Einnahmequellen — und dass der Rat nur bei dreien von sieben überhaupt
  etwas zu entscheiden hat. Die **Steuer-Steckbriefe** beantworten die Frage,
  mit der die meisten kommen: Wer legt das eigentlich fest? Drei Stufen vom
  Bundesgesetz über die Messzahl bis zum Hebesatz, den der Rat beschließt,
  dazu ein Rechenbeispiel und die tatsächlichen Einnahmen seit 1998.
  **Muss oder kann?** sortiert die Bereiche nach Spielraum und rechnet vor,
  warum Kürzen allein das Defizit nicht schließt. Und im **Haushalts-Labor**
  kann man selbst am Hebesatz drehen — mit einer dauerhaft sichtbaren Spalte,
  was der Rechnung entgegensteht. Lotti übersetzt an den schweren Stellen,
  Fachwörter erklären sich beim Antippen, und jede Zahl trägt eine Fußnote
  mit Quelle, Fundstelle, Stand und Lizenz. (#493)

### Verbessert
- **Beschluss-Seiten sagen, was es kostet.** Steht in der Vorlage eine Angabe
  zu den finanziellen Auswirkungen, erscheint sie jetzt als „Was kostet das?"
  — im amtlichen Wortlaut, als Zitat der Verwaltung gekennzeichnet, mit dem
  Weg in den Haushalt. Rund 1.400 Vorlagen tragen dieses Feld. (#493)

### Verbessert
- **„Frag den Rat" rechnet jetzt mit echten Steuerzahlen.** Geldfragen bekamen
  bisher nur die Planzahlen des laufenden Haushaltsjahres mit. Jetzt kennt die
  Antwort auch, was die Stadt **tatsächlich eingenommen** hat — Gewerbesteuer,
  Grundsteuer, Einkommen- und Umsatzsteueranteil, jeweils mit dem Wert von vor
  zehn Jahren daneben —, wie sich ein Haushaltsbereich seit 2020 entwickelt
  hat, und bei Fragen nach Hebesätzen den Zusammenhang, den man leicht
  übersieht: Nimmt die Stadt mehr Steuern ein, kürzt das Land seine
  Zuweisungen. Plan- und Ist-Zahlen bleiben dabei streng getrennt und werden
  in der Antwort als solche benannt. (#492)

### Hinzugefügt
- **Neuer Bereich „Haushalt".** Wohin fließt das Geld der Stadt? Unter
  `/haushalt` steht der Ergebnishaushalt 2020–2026 zum ersten Mal lesbar da:
  drei Kernzahlen, das Ersparte der Stadt (und wie lange es beim aktuellen
  Minus noch reicht — als offene Rechnung, nicht als Prognose), zwei
  Geldfluss-Ansichten („Woher & wohin" als Balken, „Von 100 Euro der Stadt"
  als Raster), die Einnahmen-Ausgaben-Schere über die Jahre und alle 13
  Teilhaushalte als Karten — sortiert nach dem, was sie die Stadt unterm
  Strich kosten, nicht nach dem, was sie brutto ausgeben. Jeder Bereich hat
  eine eigene Seite mit Kostendeckung, Brutto-gegen-Netto-Vergleich und
  Entwicklung. Jede Zahl trägt ihre Quelle (Haushaltsplan-PDF bzw.
  Open-Data-CSV der Stadt); fehlende Daten erscheinen als ehrliche Lücke,
  nie geschätzt. (#491)

### Verbessert
- **Haushalts-Quiz ohne 2024-Lücke, Stadtfinanzen als Datenfundament.** Die
  Trend-Diagramme der Haushalts-Quizfragen übersprangen 2024 — das Plan-PDF
  dieses Jahrgangs ist technisch unlesbar. Der Jahrgang kommt jetzt aus dem
  Open-Data-Portal der Stadt (maschinenlesbar, Lizenz dl-de/by-2.0), die
  Reihe 2020–2026 ist vollständig. Dazu, als Fundament für den kommenden
  Stadtfinanzen-Bereich: Ist-Steuereinnahmen je Steuerart seit 1998 und
  Steuerkraft samt Schlüsselzuweisungen seit 1992, aus derselben Quelle. (#489)
- **Ein umbenannter Haushaltsbereich verliert nicht mehr seine Erklärung.** Die
  Stadt tauft ihre Teilhaushalte um, ohne den Zuschnitt zu ändern — „Umwelt,
  Bauordnung, Grün u. Friedhöfe" heißt im Haushalt 2026
  „Klima/Umwelt/Mobilität/Bau/Grün/Friedh.". Bisher war der Erklärtext an den
  Namen geknüpft und fiel bei jedem neuen Jahrgang still weg; jetzt hängt er am
  Bereich selbst, und alle 13 Teilhaushalte haben einen — vorher acht. Zwei
  davon waren zudem schief: Die Eingliederungshilfe ist bei Soziales der größte
  Block, und im Finanzmanagement liegen alle Steuern, aber nur die allgemeinen
  Zuweisungen des Landes. (#517)
- **„Muss oder kann?" sagt jetzt, was die Stadt selbst dazu sagt.** Die Seite
  beginnt mit einem Balken, der die geplanten Ausgaben in Pflicht, Pflicht mit
  Spielraum und Kür zerlegt und das geplante Minus als Marke daneben setzt —
  statt drei Filterklicks über einer Liste aus 13 Karten. Neu ist der
  Gegencheck: Die Stadt gibt in ihren Teilhaushaltsplänen zu jeder Aufgabe an,
  worauf sie beruht und wie viel Spielraum sie bei ihr sieht. Bei 6 von 9
  Bereichen, für die es diese Angabe gibt, deckt sich das mit unserer
  Einordnung — bei Jugend und Familie, Finanzmanagement und Recht sowie
  Stadtplanung nicht, und genau das steht jetzt da, statt geglättet zu werden.
  Dazu die Rechtsgrundlagen im Wortlaut des Plans und die Korrektur einer
  schiefen Rechnung: Das Freiwillige zu streichen spart nicht seine 47,1 Mio. €
  Aufwand, sondern seinen Zuschussbedarf von 43,0 Mio. — rund 60 % des
  geplanten Minus. (#521)
- **„Woher kommt das Geld?" sortiert jetzt nach Entscheidungsmacht — und sagt
  beim Finanzausgleich ehrlich, dass es die Zahl nicht gibt.** Die
  Einnahmequellen standen bisher nach Betrag sortiert nebeneinander, jede mit
  ihrem eigenen Spielraum-Zeichen; die eigentliche Aussage musste man sich aus
  sieben Karten zusammensuchen. Sie stehen jetzt in drei Gruppen: was der Rat
  selbst beschließt, was er nur innerhalb gesetzlicher Grenzen darf, und worauf
  er gar keinen Einfluss hat. Neu dazu ein Block über den Finanzausgleich —
  nimmt die Stadt mehr eigene Steuern ein, rechnet das Land in den
  Schlüsselzuweisungen dagegen. Wie stark, sagen wir bewusst **nicht**: Über
  die 33 Jahrespaare des Datensatzes streut dieser Wert so weit, dass jede
  einzelne Zahl in die Irre führte, und in 15 von 26 Jahren mit steigender
  Steuerkraft stieg die Zuweisung sogar mit. Der Block zeigt deshalb beide
  Reihen nebeneinander und zählt aus, statt einen Umrechnungskurs zu erfinden.
  Im Steuer-Steckbrief außerdem zwei Korrekturen: Der Überschlag „was brächte
  ein Hebesatzpunkt mehr" war als „brutto" bezeichnet, obwohl der Datensatz die
  Gewerbesteuer bereits nach Abzug der Umlage führt, und beim Hebesatz stand
  „bis 2025", obwohl wir genau einen einzigen Jahrgang kennen. (#519)
- **„Soziales", „Finanzmanagement" — was heißt das eigentlich? Der Haushalt hat
  jetzt ein Verzeichnis seiner Bereiche.** Unter `/haushalt/bereiche` stehen alle
  13 Teilhaushalte mit Betrag und einer Zeile Klartext, vorweg der schwierigste
  Fall: Bei „Finanzmanagement und Recht" geht der Löwenanteil aller Einnahmen
  ein, nicht weil die Kämmerei etwas erwirtschaftet, sondern weil dort alle
  Steuern und die allgemeinen Zuweisungen des Landes zentral verbucht werden —
  was da zusammenkommt, steht jetzt einzeln daneben. Die Bereichsseite selbst
  rechnet ihre Kernaussage neu vor: ein Wasserfall von den Ausgaben über die
  eigenen Einnahmen zu dem Betrag, den die Allgemeinheit trägt, in Millionen
  statt als Prozent-Ring. Dazu die tatsächliche Zusammensetzung der eigenen
  Einnahmen aus dem Jahresabschluss statt einer Schätzung, die teuersten
  Aufgaben des Bereichs aus der Produktebene mit Jahresstempel, und drei Reiter
  statt einer sehr langen Rolle. (#523)
- **Die Einnahmen-Ausgaben-Schere zeigt jetzt die Lücke selbst — und was
  tatsächlich daraus wurde.** Zwei Linien zwangen dazu, den Abstand mit dem
  Auge abzumessen; genau der Abstand ist aber die Aussage. Er ist jetzt eine
  Fläche mit einer Strebe an jedem Jahr, und der größte Abstand trägt seinen
  Betrag im Bild. Dazu der Wirklichkeitstest: Für die Jahre, für die ein
  Jahresabschluss vorliegt, steht als Raute daneben, was am Ende herauskam —
  2023 und 2024 plante die Stadt ein Minus und schloss mit einem Plus ab.
  Deshalb heißt die Überschrift jetzt „Seit 2023 *plant* Oldenburg mit mehr
  Ausgaben als Einnahmen", und sie wird aus den Daten gerechnet statt
  festgeschrieben. Wo ein Jahrgang seinen Plan an einer anderen Bezugsgröße
  misst (2020: Ansatz samt Nachtragshaushalt), steht ein Sternchen mit
  Fußnote. Farbe bewertet dabei weiterhin nichts: Signal-Orange heißt „hier
  ist die Differenz" — in den Plus- wie in den Minusjahren. (#522)
- **„Wann wird der Haushalt eigentlich entschieden?" — eine neue Seite zeigt
  den Weg durch den Rat.** Unter `/haushalt/jahr` steht für acht Haushaltsjahre
  jede Station mit Datum, Gremium und Ergebnis: Einbringung des Entwurfs,
  Teilhaushalte in den Fachausschüssen, Vorberatungen, Beschluss — jede Station
  verlinkt auf ihre Sitzung. Ein Jahreskreis zeigt, wo im Kalender die Runde
  liegt. Der Befund darin ist der eigentliche Grund für die Seite: Der Entwurf
  kommt verlässlich im Oktober, die Entscheidung wandert vom 16. Dezember bis
  zum 28. Februar — fünf der acht Haushalte wurden erst beschlossen, als das
  Jahr schon lief. Termine der laufenden Runde nennt die Seite bewusst nicht:
  Das Ratsinformationssystem veröffentlicht Tagesordnungen erst kurz vorher,
  und ein geratenes Datum wäre schlechter als keins. (#524)
- **Der Haushalt fängt jetzt mit einer Zahl an — und die Bereiche stehen als
  Tabelle statt als Kachelwand.** Ganz oben steht auf dunklem Grund, worum es
  geht („Oldenburg plant 883,9 Millionen Euro", daneben Einnahmen, Ausgaben und
  Differenz) samt dem Hinweis, dass Investitionen in einem eigenen Haushalt
  laufen und das Budget also größer ist. Darunter zeigt eine Tabelle für jeden
  Bereich in einem Balken, wie sich seine Ausgaben zusammensetzen — alle Balken
  auf einer Skala, sodass ohne Fußnote sichtbar wird, dass der längste
  Ausgabenposten nicht der ist, der die Stadt am meisten kostet (2026: Soziales
  und Gesundheit 283,1 Mio. Ausgaben gegen Jugend und Familie 169,2 Mio. — aber
  113,2 zu 129,9 Mio. Zuschussbedarf). Welche Bereiche in der Liste fehlen und
  warum, wird gerechnet statt behauptet. Und die Farbskalen der Balken hängen
  jetzt an der Fläche statt am Hell/Dunkel-Modus: Im hellen Modus wäre der
  größte Einnahmeposten auf dem dunklen Grund sonst fast unsichtbar. (#525)
- **„Woher, wohin" zeigt kein anderes Jahr mehr, wenn das gewählte fehlt.** Wer auf der Haushalts-Seite ein Planjahr wählte, bekam wortlos die Grafik des nächstgelegenen Jahres mit Jahresabschluss zu sehen; dass da ein anderes Jahr stand, verriet nur eine Zeile darüber. Jetzt sagt die Seite, was fehlt — die Einnahmearten liegen uns für dieses Jahr noch nicht vor — und bietet das jüngste vollständige Jahr zum Anklicken an, statt es ersatzweise anzuzeigen.
- **Der Haushalt als Kassenzettel: 883,9 Millionen sind 5.005 Euro je
  Einwohnerin und Einwohner.** Millionenbeträge lassen sich nicht fühlen, ein
  Kassenbon schon — er zeigt dieselben Bereiche in derselben Reihenfolge, nur
  geteilt durch die amtliche Einwohnerzahl: 1.603 € für Soziales und
  Gesundheit, 958 € für Jugend und Familie, 225 € für Kultur und Sport. Ganz
  unten steht die Zeile, um die es politisch geht — 402 € kommen aus dem
  Ersparten, von dem danach noch 702 € je Kopf übrig sind. Daneben steht, was
  die Zahl **nicht** ist: keine Rechnung, die jemand überweist; geteilt wird
  durch alle Menschen, nicht durch Steuerzahlende; und nichts davon baut etwas
  Neues, denn Investitionen laufen in einem eigenen Haushalt. Bezugsgröße sind
  176.614 Einwohnerinnen und Einwohner zum Stichtag 31.12.2024 — der steht mit
  an der Rechnung, weil eine Pro-Kopf-Angabe ohne Bezugsjahr nichts wert ist.
  (#528)
- **Woher das Geld kommt, steht jetzt auch für 2025 und 2026 da — und was nur
  Vorausschau ist, sagt es dazu.** Die Aufschlüsselung nach Steuern,
  Zuwendungen und Gebühren gab es bisher nur bis 2024, weil sie aus den
  Jahresabschlüssen stammt; für die laufenden Planjahre fehlte sie. Sie steht
  längst im Haushaltsplan selbst und ist jetzt für acht Planjahre (2019–2026)
  eingelesen. Der Plan nennt fünf Spalten „Ansatz", aufgestellt ist aber immer
  nur ein Jahr — die drei danach sind mittelfristige Finanzplanung, und die
  schreibt jeder neue Haushalt neu (von 23 Posten bleiben zwischen zwei Plänen
  0 bis 2 gleich). Beides wird deshalb getrennt gespeichert und getrennt
  beschriftet, damit später nirgends ein „Plan für 2029" behauptet wird, den
  es nicht gibt. Übernommen wird ein Jahrgang nur, wenn die Tabelle in allen
  sechs Spalten aufgeht und der Plan seine Ansatz-Spalte selbst markiert. Und
  weil die Zahlen aus der Vorlage stammen, mit der die Verwaltung den Haushalt
  einbringt, steht an jeder von ihnen, dass sie der Stand der Einbringung
  sind — was der Rat in den Beratungen noch ändert, waren zuletzt bis zu
  13 Mio. €. (#530)
- **Der Haushalt hat jetzt einen Weg statt einer Kachelwand — und drei Seiten
  sind überhaupt erst auffindbar.** „Wann wird der Haushalt entschieden?" und
  der Städtevergleich waren von keiner Seite aus verlinkt, das Verzeichnis der
  Teilhaushalte nur rückwärts über die Detailseite eines einzelnen Bereichs.
  Der Wegweiser auf der Übersicht führt jetzt durch alle zehn
  Vertiefungsseiten, und zwar in vier benannten Stufen statt als lange Liste:
  erst die Zahlen (woher das Geld kommt, was hinter den Bereichsnamen steckt,
  was fest ist, was einzelne Aufgaben kosten), dann die Gegenprobe (was
  daraus wurde, und was das Rechnungsprüfungsamt dazu sagt), dann der Rahmen
  (die Betriebe neben dem Haushalt, der Vergleich mit anderen Städten),
  zuletzt das Mitreden (wann entschieden wird, und was sich drehen ließe).
  Der Städtevergleich steht bewusst spät: Er beantwortet eine Frage, die sich
  erst stellt, wenn man die eigenen Zahlen kennt. Auf dem Handy braucht das
  trotz drei zusätzlicher Ziele kaum mehr Platz als vorher. (#529)
- **Ratslotse gendert jetzt durchgängig — mit Sternchen.** Aus „Nutzer" wird
  „Nutzer*innen", aus „je Einwohnerin und Einwohner" wird „je Einwohner*in";
  auch die Anweisungen an die KI sind mitgezogen, damit die Antworten nicht
  weiter in generischen Maskulina zurückschreiben. Namen und Rechtsbegriffe
  bleiben, wie sie heißen: Die „Einwohnerfragestunde" steht so im
  Kommunalverfassungsgesetz, „Bürgerinfo" heißt das Ratsinformationssystem der
  Stadt, und „Antragsteller" sind hier Fraktionen, keine Personen. (#533)
- **Die Anzeigetafel des Haushalts ist im Hellmodus hell — und die Tabelle,
  mit der die Konzern-Seite sich selbst bestätigte, ist weg.** Die Fläche mit
  „Oldenburg plant 883,9 Millionen Euro" war in beiden Farbmodi dunkel und
  stand im hellen Modus als schwarzblaues Feld über der halben Seite; sie
  folgt jetzt dem Modus und bleibt trotzdem vom Rest der Seite abgesetzt. Die
  Balken darauf wurden dafür neu gestuft, damit auch der kleinste Posten und
  die schraffierte Rücklagen-Marke sichtbar bleiben — im Hellmodus stehen sie
  jetzt weiter vom Grund ab als vorher im Dunkelmodus. Von der Konzern-Seite
  verschwunden ist der Block „Dieselbe Zahl, zwei Quellen": acht Zeilen, in
  denen jedes Jahr zweimal dieselbe Summe und daneben „unter 1 Tsd. €
  Unterschied" stand. Dass zwei Dokumente übereinstimmen, ist unsere
  Qualitätssicherung — sie läuft unverändert weiter, steht in der Technik-Doku
  und in Tests, aber nicht mehr auf der Seite. (#535)
- **Die Grafiken im Haushalt schreiben ihre Zahlen jetzt selbst an.** Unter der
  Zeitreihe auf `/haushalt`, der Steuerkurve auf `/haushalt/steuer` und den
  beiden Reihen des Finanzausgleichs steht eine Leiste, die immer ein Jahr mit
  allen seinen Werten zeigt — im Ruhezustand das jüngste. Überfahren, Antippen
  oder die Pfeiltasten wechseln das Jahr, und weil die Leiste echter Text ist,
  steht die Zahl auch im Screenshot, im Ausdruck und in der Vorlesehilfe; ein
  Tooltip wäre nur für die Maus da gewesen. In der 100-Euro-Ansicht hebt ein
  Bereich seine Felder im Raster hervor, egal ob man ihn in der Liste oder im
  Bild wählt. Die Zahlentabellen bleiben — 28 Werte nebeneinander kann kein
  Bild —, starten aber zugeklappt. (#536)

<!-- GEPARKT (nur dev.ratslotse.de, Umgebungs-Gate): Eintrag aktivieren,
     sobald der Kommunalwahl-Vergleich auf Prod freigeschaltet wird.
### Hinzugefügt
- **Wahlprogramm-Vergleich zur Ratswahl am 13. September.** Unter
  `/kommunalwahl` — öffentlich, ohne Konto — hat Ratslotse alle Programme
  gelesen: die acht Listen mit eigenem Kommunalwahlprogramm plus BSW (dessen
  Landesprogramm Oldenburg nirgends erwähnt und deshalb überall markiert ist),
  entlang von 44 Thesen. Zwölf Themenseiten stellen die Positionen nebeneinander,
  neun Profilseiten zeigen je ein Programm mit Kernpunkten und Auffälligkeiten,
  eine Nähe-Matrix rechnet aus, wer wem wie oft zustimmt — und jede einzelne
  Aussage trägt ein Belegzitat mit Seitenzahl, das direkt ins Original der
  Partei springt. Die sieben Listen ohne vergleichbares Programm fehlen nicht,
  sondern stehen mit Rechercheprotokoll dabei. Ausgewertet hat eine KI, keine
  Redaktion — das sagt die Seite an drei Stellen selbst und lädt zum Nachprüfen
  ein: Ratslotse hostet die Programme nicht, sondern prüft live, ob hinter dem
  Partei-Link noch genau die Datei steht, die ausgewertet wurde. Dazu vier
  Auswertungen, die es sonst nirgends gibt: eine Karte der Nähe (alle 36
  Paarabstände als Bild), „Steht allein da" (Positionen einer Liste gegen alle
  anderen), ein Themen-Fingerabdruck je Programm und „Wie dieses Programm
  redet" (Umfang, Satzlänge, typische Begriffe) — und der **Thesen-Check**:
  dieselben 44 Thesen selbst beantworten (Überspringen erlaubt, Wichtiges
  zählt mit ★ doppelt) und sehen, wie oft jede Liste übereinstimmt, Satz für
  Satz belegt. Kein Wahltipp, und die Antworten bleiben auf dem Gerät. (#356)
-->

- **„Dokument öffnen" öffnet jetzt das Dokument.** Im Quellenverzeichnis der Haushalts-Seiten führten sechs Quellen auf die Startseite des Ratsinformationssystems — man durfte das PDF selbst suchen. Der Link zeigt jetzt auf das Dokument des gerade gezeigten Jahres (wechselt das Jahr, wechselt das PDF), nennt die Fundstelle darin („Abschnitt 3.2"), und wo wir kein Dokument haben, verspricht er auch keines mehr. Der Knopf „Haushaltsplan als PDF" oben auf der Übersicht entfällt dafür: Er ließ eine von mehreren Quellen wie die einzige aussehen, seine jahresgenaue Adresse steckt jetzt im Beleg. Quellenverzeichnis und Datenstand stehen außerdem nicht mehr in der Kartenform des Inhalts, sondern zugeklappt als Apparat am Seitenfuß. (#538)
- **Fünf Stellen im Haushalt erklären wieder den Haushalt statt uns.** Unter den Zahlen auf „Der Konzern Stadt" und „Steht Oldenburg besser da als Osnabrück?" standen bisher unsere eigenen Rechenproben und darunter „Gemessen: 0,00 % Abweichung" — jetzt steht dort nur noch, in welchem Abschnitt des Dokuments die Zahl zu finden ist, was beim Nachschlagen im 300-Seiten-PDF hilft. Ebenso raus: „Es erscheinen nur Jahre, deren Zahlen unsere Prüfung bestehen" samt drei Rechenproben in Prosa („Plan gegen Wirklichkeit"), die Parser-Bedingung im Fuß der Prüfungs-Seite und der Betriebsablauf im Datenstand („geprüft wird alle zwei Wochen"). Auf „Muss oder kann?" entfällt die Quote, zu wie viel Prozent unsere Einordnung sich mit der Selbstauskunft der Stadt deckt; die **Abweichung** bleibt und steht jetzt vorn, denn wo beide sich widersprechen, ist das eine Auskunft über die Aufgabe. Was bleibt, ist das, was jemandem etwas sagt: die Quelle, der Hinweis auf eigene Rechnungen und echte Grenzen wie „für dieses Jahr liegt der Schlussbericht nicht in lesbarer Form vor". Die Prüfungen selbst laufen unverändert weiter — sie stehen in Tests und in der Technik-Doku. (#542)
- **„Frag den Rat" kennt jetzt den Haushalt.** Geldfragen sahen bisher nur Beschluss-Beträge, den Haushaltsplan und die Steuereinnahmen — Jahresabschlüsse, die 377 städtischen Aufgaben samt Rechtsgrundlage, die Feststellungen des Rechnungsprüfungsamts, der Konzern Stadt und der Städtevergleich blieben unsichtbar. Jetzt zieht jede Frage genau die Quellen, die sie beantworten: „Hat die Stadt 2024 mehr ausgegeben als geplant?" bekommt den Jahresabschluss samt Begründung der Verwaltung, „Muss die Stadt das Theater betreiben?" die Rechtsgrundlage der Aufgabe, „Was kostet die Stadt insgesamt?" den Konzern statt nur den Kernhaushalt. Jede Zahl kommt mit Jahr und Fundstelle, und Fragen ohne Geldbezug bekommen weiterhin nichts davon. (#543)
### Geändert
- **Ein gemeinsamer Ortskatalog für Suche, Quiz, Karten und KI-Frage.** Die 31
  bisher verteilten Oldenburger Gebietslisten sind jetzt als zentrale
  „Ratslotse-Ortsbereiche“ mit stabilen IDs, Schreibvarianten, Wahlbereichen und
  Quellenhinweisen gepflegt. Die Oberfläche bezeichnet sie bewusst nicht mehr
  als amtliche Stadtteile – denn eine solche amtliche Einteilung gibt es in
  Oldenburg nicht. Bestehende Zuordnungen, einschließlich Bornhorst, bleiben
  erhalten und werden nun in allen Funktionen gleich verwendet. Der Katalog
  umfasst nun außerdem erste belegte Quartiere, Parks, Schutz-, Wohn-,
  Sanierungs- und Entwicklungsgebiete. Beschlusssuche, Ortsprofile, Quiz und
  „Frag den Rat“ greifen über dieselben stabilen IDs, Aliase und Hierarchien
  darauf zu; neue Beschlüsse werden beim Einlesen automatisch verknüpft. Der
  Quiz-Backfill fordert dabei nur noch die bis zum Ziel fehlenden Fragen an und
  kürzt längere Erklärungen nicht mehr mitten im Satz.

## [1.13.2] – 2026-08-19

### Behoben
- **Kein iOS-Zoom mehr beim Antippen kleiner Eingabefelder.** Safari/WKWebView
  zoomt automatisch rein, sobald ein Eingabefeld eine Schriftgröße unter 16px
  hat — auf dem iPhone (und, weil `sm:` an der Fensterbreite statt am
  Eingabegerät hing, auch auf dem iPad) blieb dieser Zoom in Feldern wie
  „Gespräch umbenennen", „Neues Thema anlegen" oder der Admin-Suche oft hängen.
  Betroffene Felder zeigen jetzt überall mindestens 16px, sobald kein Mauszeiger
  vorhanden ist; am Desktop bleibt die kompaktere Schrift wie gewohnt. (#643)

## [1.13.1] – 2026-08-19

### Geändert
- **Zwei Feinheiten auf der Fragen-Seite für Touch-Geräte.** Die
  Scroll-Klickpfeile neben den Vorschlags-Pillen (Weiterfragen, „Einfacher
  erklären") erscheinen jetzt nur noch für eine Maus — auf iPhone und iPad
  reicht der Wisch, die Pfeile waren dort nur ein zusätzliches Element ohne
  Nutzen. Und der „Zuletzt gefragt"-Block auf dem leeren Fragen-Screen zeigt auf
  dem iPhone nur noch den letzten Chat statt zweier — der zweite kostete genau
  die Zeile, die den Screen knapp über den sichtbaren Bereich trieb. Ab
  Tablet-Breite bleiben es weiterhin zwei. (#641)
- **Der Gesprächs-Verlauf ist jetzt Inhalt, kein Icon (Design 15).** Wer schon
  Gespräche gespeichert hat, sieht die letzten zwei direkt auf der Fragen-Seite
  unter „Zuletzt gefragt" — bisher hing der Verlauf an einem namenlosen
  Uhr-Symbol, das kaum jemand als „Gespräche" las. Der Knopf oben rechts trägt
  jetzt immer sein Wort und zählt mit („Gespräche · 4"); im offenen Gespräch
  steht dessen Titel darin. Das Gespräche-Sheet gruppiert nach Heute · Gestern ·
  Älter mit Trennlinien, jede Zeile hat ein sichtbares ⋯-Menü für Umbenennen und
  Löschen (Wisch nach links bleibt als Abkürzung), einen Schließen-Knopf — und
  ab acht Gesprächen ein Suchfeld. Auch der Desktop nutzt dieses Sheet statt des
  schmaleren Klapp-Menüs, das nicht einmal umbenennen konnte. Aufgeräumt ist der
  leere Screen obendrein: ein Erklärsatz statt drei fast gleicher, „Neu" nur
  noch an wirklich frischen Beispielfragen, das Funkel-Icon einmal statt an
  jeder Zeile — und Eingabefeld, Recherche-Schalter und der kräftigere
  Senden-Knopf sind eine Karte. (#639)

## [1.13.0] – 2026-08-19

### Geändert
- **Die Vorabend-Erinnerung kommt jetzt immer am Vortag.** Sie teilte sich das
  Kontingent von zwei Meldungen am Tag mit allem anderen — und weil sie als
  letzte des Tages um 18 Uhr eingereiht wird, verlor sie diesen Wettlauf
  regelmäßig und kam erst am Sitzungstag selbst an. Termingebundene Meldungen
  haben jetzt ihren eigenen Vorrat: Die Erinnerung geht raus, egal wie viel an
  dem Tag schon kam, und sie nimmt umgekehrt keiner anderen Meldung den Platz.
  An einem Abend mit mehreren Sitzungen wird ab der dritten weiterhin
  gebündelt. (#585)
- **Auf sehr breiten Monitoren (21:9) nutzt die Fragen-Seite den Platz.** Ab
  1680 Pixeln Fensterbreite wächst der Seitenrahmen von 1280 auf 1600 Pixel: Die
  Gesprächs-Bühne wird etwas breiter, die Belege-Spalte deutlich (420 statt 320
  Pixel), die Abstände atmen. Die Lesebreite der Antworten bleibt dabei
  gedeckelt — mehr Platz heißt mehr Raum für die Quellen, keine endlosen
  Textzeilen. Unterhalb dieser Schwelle ändert sich nichts. (#614)
- **Der Protokoll-Link an Wortbeiträgen springt jetzt direkt zur Seite.** Wo
  sich die Fundstelle eindeutig bestimmen lässt, öffnet das Dokument-Symbol im
  Block „Aus den Ratsdebatten" das PDF gleich auf der richtigen Seite (in
  Chrome, Firefox und Edge; Safari öffnet das PDF wie bisher am Anfang). Der
  Anker ist der Sprecher-Name, der wörtlich im Protokoll steht; die markanten
  Wörter der Aussage entscheiden, wenn der Name mehrfach vorkommt — etwa in der
  Anwesenheitsliste. Ist die Stelle nicht eindeutig, bleibt es beim Link aufs
  ganze PDF: lieber kein Sprung als ein falscher. Für den Bestand rüstet ein
  einmaliger Lauf die Seitendaten nach; neue Protokolle tragen sie ab sofort von
  selbst. (#615)
- **Die Push zur Tagesordnungs-Änderung sagt jetzt kurz, was passiert ist — die
  Einzelheiten zeigt die Sitzungsseite.** Bisher stopfte die Mitteilung den
  ganzen Mail-Text in die Vorschau: Datum, Sitzungsort und dann erst die Sache.
  Jetzt steht dort nur noch der Änderungssatz („Ein Punkt ist neu und eine
  Vorlage wurde nachgereicht."), und ein Tipp darauf öffnet die Sitzung in der
  App — mit einem neuen Block „Zuletzt geändert", der die Änderungen einzeln
  aufführt: Neues grün, Geändertes gelb, Entferntes rot durchgestrichen, wie in
  der Mail. Auch die Push zur frisch veröffentlichten Tagesordnung beginnt nun
  mit den Inhalten statt mit dem Sitzungsort. (#612)
- **Die „Tagesordnung geändert"-Mail sagt jetzt in einem Satz, was passiert
  ist.** Über der farbmarkierten Liste steht die Art der Änderung — „Ein Punkt
  ist neu, eine Vorlage wurde nachgereicht und ein Punkt wurde von der
  Tagesordnung genommen." Neu erkannt werden dabei auch die **Anhänge** eines
  Tagesordnungspunkts: Kommt eine Änderungsliste oder Stellungnahme dazu oder
  verschwindet eine, nennt die Mail sie beim Namen — bisher lösten Anhänge gar
  keine Meldung aus. Und wo der frühere Stand zum Vergleich fehlt, sagt die Mail
  ehrlich, dass sie die vollständige aktuelle Tagesordnung zeigt, statt alles
  wie neu aussehen zu lassen. (#607)
- **Der Zähler an „Meine Themen" verstummt, sobald man nachgesehen hat.** Bisher
  blieb die orange Blase in der Navigation stehen, bis man jedes einzelne Thema
  geöffnet hatte — bei zehn Themen mit neuen Treffern ein zäher Weg. Jetzt
  reicht ein Blick auf die Themen-Übersicht: Die Blase zeigt danach nur noch,
  was seitdem dazugekommen ist. Welches Thema neue Beschlüsse hat, steht
  unverändert als „n neu" an den Themen selbst und verschwindet dort erst, wenn
  das Thema wirklich offen war. (#637)
- **„x weitere Punkte" klappt in der Wochen-Karte auf, statt wegzunavigieren.**
  Die Restzeile unter einer Sitzung führte bisher zur Tagesordnung — für drei
  Titel ein Seitenwechsel. Jetzt klappen die übrigen relevanten Punkte direkt in
  der Karte auf, mit Antragsteller-Punkt und Link auf den einzelnen
  Tagesordnungspunkt; zur vollen Tagesordnung führt weiterhin der Link im
  Sitzungskopf. Die Mobil-Ansicht konnte das schon — jetzt kann es auch die
  große Karte, und beide zeigen alle relevanten Punkte, nicht nur die bereits
  geladenen. (#616)

### Behoben
- **„Die Tagesordnung hat sich geändert" verriet nicht, was.** Wurde zu einem
  Punkt nur die Vorlage nachgereicht — Nummer und Titel blieben gleich —, fand
  der Vergleich nichts und die Mail behalf sich mit „Details einzelner Punkte
  wurden angepasst". Genau so ist es am 17.08. beim Ausschuss für Allgemeine
  Angelegenheiten passiert. Nachgereichte, getauschte und zurückgezogene
  Vorlagen stehen jetzt als eigene Zeile in der Änderungsliste („Vorlage
  nachgereicht · TOP Ö 5 — Vorlage 26/0019/9 liegt jetzt vor"), und der
  Vergleich sieht dieselben Punkte wie die Änderungserkennung, also auch die
  nichtöffentlichen. Bleibt am Ende doch nichts Nennbares übrig, kommt gar
  keine Mail mehr statt einer ohne Inhalt. (#582)
- **„Morgen, 16:45 Uhr" kam am Sitzungstag selbst.** Die Vorabend-Erinnerung
  wird um 18 Uhr eingereiht, geht aber erst raus, wenn die Grenzen es zulassen
  — waren an dem Tag schon zwei Meldungen draußen, wartet sie bis zum nächsten
  Morgen, und „morgen" war dann heute. Der Titel nennt jetzt den Tag statt
  eines Wortes, das vom Zustellzeitpunkt abhängt. (#582)
- **„Diese Woche: 119 Beschlüsse zu deinen Themen".** Der wöchentliche
  Abgleich Thema ↔ Beschluss legte alle Treffer neu an und stempelte sie dabei
  auf heute; der Wochenüberblick am selben Abend hielt deshalb den gesamten
  Bestand für die Neuigkeiten der Woche. Bekannte Treffer behalten jetzt ihr
  Datum, nur wirklich neue zählen — und ein Reparaturlauf nach einer
  Neu-Extraktion stempelt gar nichts als neu. (#582)
- **Gleichnamige Tagesordnungspunkte erzeugen keine erfundenen Verschiebungen
  mehr.** Nichtöffentliche Sitzungsteile führen reihenweise Punkte mit dem Titel
  „gesperrte Information" — die Änderungsmeldung ließ alle am ersten
  Namensvetter andocken und meldete dann Verschiebungen, die es nie gab
  („Verschoben · N 11 → N 12"). Jetzt binden sich erst die nummerntreuen Paare,
  der Rest der Reihe nach; und fällt einer von mehreren gleichnamigen Punkten
  weg, taucht das erstmals als „Entfernt" auf, statt unterzugehen. (#611)
- **Straßen-Widmungen gelten nicht mehr als „wichtig".** Die Widmung einer
  Straße macht einen längst bestehenden Zustand amtlich — trotzdem stand
  „Widmung der Straße ‚Im Technologiepark'" als wichtiger Punkt auf der
  Wochen-Karte. Straßenrechtliche Formalakte (Widmung, Einziehung, Umstufung)
  werden jetzt fest gedeckelt: in der Bewertung selbst, im Bewertungs-Prompt und
  beim Lesen — damit verschwinden auch schon gespeicherte Fehlbewertungen sofort
  von der Karte. Die Umwidmung von Geld ist davon ausdrücklich nicht betroffen.
  (#616)

### Hinzugefügt
- **Wortbeiträge in „Frag den Rat" verlinken jetzt ihr Protokoll.** Jede Aussage
  im Block „Aus den Ratsdebatten" trägt ein kleines Dokument-Symbol, das das
  Sitzungsprotokoll (PDF) im Ratsinformationssystem öffnet — in der
  Quellenspalte, in der mobilen Beleg-Ansicht, auf der geteilten Antwort-Seite
  und in der Gründlichen Recherche. Was der Rat gesagt haben soll, lässt sich
  damit im Original nachlesen statt nur glauben. (#606)

## [1.12.0] – 2026-08-16

### Behoben
- **Drei Zahlen für dieselbe Sache.** Ein Thema zeigte auf der Karte „40+
  Beschlüsse", im Blatt „Thema anpassen" 12 und in der Liste hinter „alle
  ansehen" 25. Die 12 war nie eine Trefferzahl, sondern die Länge des
  Prompt-Kontexts; die Liste filterte still auf Beschlüsse mit
  Abstimmungsergebnis und ließ alle Berichte weg. Jetzt gibt es eine Definition
  an einer Stelle, die Cron und Web gemeinsam benutzen — dieselbe Zahl auf der
  Karte, im Blatt und in der Liste, und wo wirklich gedeckelt wird, steht
  überall „40+". Die Vorschlags-Chips nennen ihre viel gröbere Zahl jetzt beim
  Namen („12 im letzten Jahr"). (#495)
- **Dialoge lagen scheinbar hinter der Navigation.** Der Abdunkler unter „Thema
  anpassen" war exakt die dunkle Seitenfarbe und dunkelte im Dunkelmodus nichts
  ab — Kopfzeile und Tab-Leiste behielten ihren Glas-Look und wirkten dadurch
  vor dem Dialog, der sie obendrein um wenige Pixel berührte. Es gibt jetzt
  einen einheitlichen Abdunkler und fünf benannte Ebenen; auf breiten Geräten
  hält der Dialog sichtbar Abstand zu Kopf und Leiste. (#495)
- **Text schien unter dem Eingabefeld durch.** Zwischen Composer und Tab-Leiste
  blieb ein Streifen offen, durch den die Antwort scrollte: Beide rechneten mit
  einer eigenen Zahl für die Höhe der Leiste, und die war je nach Gerät
  verschieden. Jetzt gibt es dafür eine gemeinsame Quelle. (#495)
- **Der Eingabe-Balken verdeckte auf dem iPad die halbe Breite.** Statt eines
  Riegels über den ganzen Bildschirm sitzt der Composer dort jetzt als Panel
  auf der Chat-Spalte — die Quellen daneben bleiben bis unten sichtbar. (#495)
- **Quellen liefen bei Folgefragen aus dem Bild.** Auf dem iPad läuft die
  Belege-Spalte jetzt mit und sagt ab der zweiten Frage dazu, zu welcher Frage
  sie gehört. (#495)
- **Konto-Seite ließ die halbe Fläche leer.** Neben der langen
  Benachrichtigungs-Karte stand ein Loch von fast 500 px Höhe, während links
  noch zu scrollen war. Die Karten stapeln jetzt in Spalten statt in Zeilen und
  nutzen die volle Breite — die Seite ist auf dem iPad quer ein Drittel kürzer.
  (#495)

## [1.11.0] – 2026-08-15

### Behoben
- **Das iPad bekommt endlich, was seine Breite hergibt.** Der Gespräche-Knopf
  fehlte dort im Seitenkopf, und die Quellen standen im Textfluss statt daneben.
  Beides war dasselbe Loch: Die mobile Fassung verschwand ab 768 px, die zweite
  hing an „Maus vorhanden" — dazwischen zeigte keine von beiden. Jetzt trennen
  drei Breakpoints, was zusammengehört: Platz (Spalten), Maus (Seitenleiste),
  breites Touch-Gerät. Quer stehen die Quellen als Spalte neben der Antwort,
  hochkant bleibt es einspaltig, das Eingabefeld bleibt in der Bildmitte. (#488)
- **Kein Weg zurück aus der Vollbild-Karte.** Die Stadtkarte im Vollbild lag
  unter Topbar und Tab-Leiste, der Schließen-Knopf war dahinter versteckt und
  vom Rest der Seite stachen Suchfeld und Stadtteil-Wähler durch die Karte. Ein
  überflüssiges `isolate` sperrte das Vollbild in einen eigenen Stapelkontext.
  (#488)
- **Die Stadtkarte war quer ein Briefschlitz.** Auf dem iPad lag ein 1114 × 310
  px flacher Rahmen über der halben Region — Bremen bis Cloppenburg, Oldenburg
  ein Klecks. Die Höhe hing allein am Bildschirm, nie an der Breite, und Leaflet
  rundete den Ausschnitt zusätzlich um eine volle Zoomstufe ab. Jetzt hat der
  Rahmen ein Seitenverhältnis und der Ausschnitt Zwischenstufen: sichtbar
  42,9 × 15,7 km statt 102,1 × 28,4 km. (#488)
- **Registrieren passte auf dem iPad nicht aufs Bild.** Die Karte war 793 px
  hoch, Lotti darüber wurde abgeschnitten (auch auf dem Desktop), der Fuß stand
  auf der Bildkante. Der Pflicht-Fuß steht jetzt unter der Karte auf dem
  Hintergrund und gilt damit für alle Anmelde-Seiten; die Karte wird auf breiten
  Geräten breiter und legt Name und E-Mail nebeneinander. Karte 793 → 578 px,
  quer wie hoch ohne Scrollen. (#488)
- **„Einfacher erklären" erklärte nicht einfacher.** Der Knopf schickte nur den
  Satz „Erkläre das bitte einfacher" als normale Frage — gegen zwei Dutzend
  Regeln für Präzision, Zitate und Langfassung, die ihn überstimmten. Jetzt
  schreibt ein eigener Prompt die vorliegende Antwort um, im Ton von „Lotti
  erklärt's einfach": kurze Sätze, kein Fachwort ohne Erklärung, gerundete
  Beträge — die Fußnoten bleiben. Gemessen an drei echten Antworten: halb so
  lang, längster Satz von 45 auf 18 Wörter, keine unerklärten Fachbegriffe mehr.
  Nebenbei lernt jede Antwort, Beträge lesbar zu schreiben („rund 45 Millionen
  Euro" statt „44,699 Millionen Euro"). (#488)
- **Themen-Treffer waren zu einem guten Teil Rauschen.** Jedes Thema zeigte
  exakt so viele Beschlüsse, wie der Lauf höchstens speichert — die Schwelle
  darunter hat nachweislich nie etwas verworfen, weil sich amtliche Kurztexte
  mit reiner Vektor-Ähnlichkeit nicht trennen lassen. „IQON" und „Wohnheim
  Tegelbusch" bekamen deshalb dieselben fremden Beschlüsse und ihre eigenen
  nicht. Gesucht wird jetzt wie bei der KI-Frage, bewertet wird mit demselben
  Modell, das dort schon entscheidet; wo wirklich gedeckelt wird, sagt die Karte
  „40+". Auch die falschen „dein Thema"-Marker in Tagesordnungen kommen daher —
  ohne Vorlagentext fiel die Gegenprüfung bisher komplett aus. (#488)
- **„25 neu" bei jedem Thema.** Beim Aufräumen verwaister Treffer blieben die
  Gelesen-Marken auf gelöschten Beschlüssen liegen; danach galt alles wieder als
  ungelesen. Sie werden jetzt mit aufgeräumt. (#488)
- **„Fragen" steht sofort komplett da.** Nach dem Tippen auf den Tab erschienen
  die unterste Beispielfrage und der Gespräche-Knopf oben rechts erst nach
  einer halben Sekunde. Zwei Ursachen: Die Seiten-Animation hob die neue Seite
  kurz an und riss dabei das Eingabefeld mit, das die dritte Beispielfrage
  verdeckte, bis die Animation endete — sie blendet jetzt nur noch ein. Und
  Beispielfragen wie Gespräche-Knopf hängen an Server-Antworten, die beim
  letzten Besuch dieselben waren: Der Stand von damals steht jetzt sofort,
  aufgefrischt wird im Hintergrund. Gemessen bei 600 ms Antwortzeit: alles ab
  dem ersten Bild an seinem Platz. (#486)
- **Kein Verschieben mehr beim Öffnen von „Fragen".** Die Frage „Soll ich mir
  deine Gespräche merken?" erschien erst, wenn der Server geantwortet hatte —
  und schob dann den halben Bildschirm nach unten. Die Einwilligung reist
  jetzt mit dem Konto, das ohnehin geladen ist; die Seite steht damit vom
  ersten Bild an richtig. Gemessen bei 600 ms Antwortzeit: vorher ein Sprung
  mit CLS 0,196, jetzt keiner. (#485)

### Verbessert
- **Wochentag im Sitzungstab.** Die Kachel nannte nur Monat und Tag — ob eine
  Sitzung auf einen Montag oder einen Samstag fällt, musste man selbst
  nachrechnen. Jetzt steht der Wochentag vor der Uhrzeit, bei nahen Terminen
  weiterhin „Heute" bzw. „Morgen". (#484)
- **„Worum geht es?" als Karussell.** Nennt eine Frage mehrere Orte oder
  Projekte, standen die Steckbriefe untereinander und schoben die eigentliche
  Antwort aus dem Bild. Jetzt liegen sie nebeneinander, werden gewischt und
  zeigen mit Punkten an, wie viele es sind. (#484)

### Behoben
- **„8 Beschlüsse" und die Suche fand nichts.** Die gespeicherten Treffer eines
  Themas zeigten auf Beschlüsse, die es nach einer Neu-Extraktion nicht mehr
  gab — auf dem Server waren das alle. Der Zähler auf der Themen-Karte zählt
  jetzt nur, was die Suche auch findet, verwaiste Verweise werden beim
  Abgleich entfernt, und es werden mehr Treffer je Thema gespeichert (25 statt
  8), damit die Karte nicht weniger zeigt als die Live-Prüfung beim
  Bearbeiten. (#483)
- **Tab-Leiste auf dem iPhone wieder normal hoch.** Mit der iPad-Runde wanderte
  die Hälfte der Sicherheitszone nach oben — auf dem iPhone wurde die Leiste
  dadurch rund 17 Punkte höher. Der Ausgleich gilt jetzt nur noch für breite
  Touch-Geräte. (#483)
- **Mehr Luft im Thema-Bearbeiten-Blatt**: Der Kasten „Passt gerade auf" klebte
  an den Knöpfen. (#483)

## [1.10.0] – 2026-08-15

### Verbessert
- **Keiner, einer oder zwei Schwerpunkte — je nachdem, was die Woche hergibt.**
  Bisher hob die Karte genau einen Punkt hervor, auch in Wochen, in denen der
  beste ein Bericht war — und deckelte auf einen, wenn gleich zwei große
  Entscheidungen anstanden. Jetzt wird hervorgehoben, was schwer wiegt: in
  ruhigen Wochen gar nichts, in dichten bis zu zwei. Zweimal dieselbe Sache
  (Bebauungsplan und Flächennutzungsplan zum selben Projekt) zählt dabei als
  einer. Ein Punkt zu einem eigenen Thema wird immer hervorgehoben. (#481)

### Verbessert
- **Der wichtigste Punkt der Woche wird jetzt erkannt, nicht geraten — und in
  Alltagssprache erklärt.** Die Auswahl kannte nur Verfahrenssignale und hielt
  deshalb wiederkehrende Routine für bedeutend: „Annahme von Zuwendungen"
  stand 101-mal auf einer Tagesordnung und trotzdem ganz oben. Jetzt zählt
  Ratslotse, wie oft dieselbe Formulierung schon dran war, liest den
  Beschlussvorschlag und den Kostenteil der Vorlage — und schreibt in zwei
  einfachen Sätzen dazu, worum es geht und wen es angeht. Statt „Annahme von
  Zuwendungen" steht dort jetzt etwa der Flächennutzungsplan fürs Stadion:
  „Damit werden die Weichen für ein neues Stadion gestellt." (#480)

### Verbessert
- **„Die Woche im Rat" hebt jetzt hervor, was Folgen hat.** Bisher entschied
  eine Heuristik aus Verfahrenssignalen, welcher Punkt oben steht — ein
  Bericht über das Stadtmuseum schlug damit eine Satzungsänderung. Jetzt
  bewertet dieselbe Tragweite-Rubrik wie bei den Beschlüssen (Betroffene,
  Geld, Bindungswirkung, Präzedenz), was hervorgehoben wird; die Regeln
  bleiben der Boden, wenn noch keine Bewertung vorliegt. In der Rückschau auf
  sechs vergangene Wochen wählt die Karte in fünf davon einen anderen — und
  einleuchtenderen — Spitzenpunkt, darunter der Stadionneubau statt eines
  Jahresabschlusses. (#479)

### Verbessert
- **„Die Woche im Rat": ehrlichere Abzeichen und weniger Rätsel.** Das
  Abzeichen sagte „2 für dich", auch wenn kein einziges eigenes Thema im Spiel
  war — gezählt wird jetzt getrennt: „für dich" nur bei echten Themen-Treffern,
  sonst „wichtig". Jede Sitzung führt zu ihrer Tagesordnung (nicht mehr nur die
  ohne hervorgehobene Punkte), der hervorgehobene Punkt sagt mit einer Zeile,
  warum er hervorgehoben ist, und der erklärende Fußtext samt Kalender-Link ist
  weg — jede Zeile führt ohnehin dorthin. Mobil steht jetzt jede Sitzung
  einzeln, und „1 weiterer Punkt" klappt auf, statt die Seite zu wechseln.
  (#478)

### Behoben
- **Grüne ohne Farbpunkt.** Steht die Fraktion als „Fraktion Bündnis 90/Die
  Grünen" in der Vorlage (Wort vorn statt hinten), blieb der Punkt vor dem
  Antragsteller leer. Jetzt trägt sie ihr Grün wie alle anderen. (#478)
- **Sprung auf einen Tagesordnungspunkt endete im Ungewissen.** Wer aus der
  Wochen-Karte „Öffnen" antippte, landete zwar an der richtigen Stelle, aber
  die Zeile sah aus wie jede andere. Sie wird jetzt kurz hervorgehoben. (#478)

### Behoben
- **iPad-Build ließ sich nicht hochladen.** Apple verlangt für das
  iPad-Multitasking alle vier Bildschirm-Ausrichtungen; die App meldete nur
  drei und wurde beim Upload abgewiesen. Auf dem iPhone bleibt der Kopfstand
  weiterhin aus — die Ausrichtungen sind jetzt pro Gerätetyp gesetzt. (#477)

## [1.9.0] – 2026-08-14

### Neu
- **Die App läuft jetzt auch auf dem iPad.** Bisher lief sie dort nur im
  iPhone-Fenster. Jetzt ist sie eine Universal-App für beide Ausrichtungen —
  und die Navigation richtet sich nach dem Eingabegerät statt nach der
  Fensterbreite: Maus oder Trackpad bekommen die Seitenleiste, der Finger die
  Tab-Leiste unten. Ein iPad ist quer 1366 Punkte breit und hätte die
  Seitenleiste sonst allein wegen seiner Breite bekommen, obwohl die
  Navigation dort an den Daumen gehört. Auf dem iPad sind die Symbole größer
  und rücken zu einer mittigen Gruppe zusammen, statt sich über die ganze
  Gerätebreite zu verteilen. (#475)
- **Erklärung zur Barrierefreiheit.** Unter `/barrierefreiheit` steht jetzt,
  was umgesetzt ist (Tastaturbedienung, Kontraste, „Bewegung reduzieren",
  Textvergrößerung), wo es noch hakt (Stadtkarte, Diagramme, fremde PDFs) und
  wie man eine Barriere meldet. Verlinkt aus allen Seiten-Füßen. (#473)
- **Datenschutz: Abschnitt zu den Ratsmitgliedern.** Die Erklärung beschrieb
  bisher nur Daten der Nutzer. Jetzt steht auch da, welche Angaben zu
  Ratsmitgliedern und Verwaltung aus den amtlichen Protokollen verarbeitet
  werden, woher sie stammen, auf welcher Grundlage — und wie Betroffene
  widersprechen oder eine Verwechslung korrigieren lassen (Art. 14 DSGVO). (#473)

### Behoben
- **Geteilte Antworten und die Fragen-Seite öffnen wieder die App.** Seit der
  Trennung von Fragen und Suche fehlten `/fragen` und die Teilen-Links `/g` in
  der Universal-Links-Datei — beide landeten im Browser statt in der
  installierten App. (#473)

### Verbessert
- **„Die Woche im Rat" zeigt auf jedem Gerät so viel, wie hineinpasst.** Die
  Karte hat jetzt drei Ausbaustufen und wählt sie nach ihrer eigenen
  Inhaltsbreite, nicht nach der Fensterbreite: auf dem Telefon Kurznamen der
  Gremien und Uhrzeit, auf dem Tablet zusätzlich Sitzungsort und Antragsteller,
  am Desktop dazu die volle Gremienbezeichnung und eine Kurzfassung des
  wichtigsten Punkts. Pro Karte wird genau ein Punkt hervorgehoben — der
  Server entscheidet welcher, statt dass jede Sitzung einen eigenen bekommt.
  Punkte, die zu deinen Themen passen, stehen oben und kommen auch dann durch,
  wenn sie für sich genommen unauffällig wären. Und der Parteipunkt neben einem
  Antrag stimmt wieder: „CDU-Fraktion" oder „SPD & Grüne" wurden vorher grau
  gezeichnet, weil nur exakte Parteinamen erkannt wurden. (#475)
- **Registrieren passt wieder auf den Bildschirm.** Auf dem iPhone sprang die
  Tastatur schon beim Laden auf und schob die Karte so weit nach oben, dass
  Lotti in der Dynamic Island verschwand. Ohne den automatischen Fokus bleibt
  der Screen stehen; die drei Fußzeilen-Blöcke sind außerdem zu einem
  zusammengefasst. (#475)
- **Die Karten auf „Heute" nutzen den Platz besser.** Drei Spalten gab es
  schon ab 1024 Pixeln — dort brach die Überschrift mitten im Wort um. Jetzt
  gilt: eine Spalte auf dem Telefon, zwei ab Tablet-Breite (die Wochen-Ausgabe
  über die volle Zeile, damit sie lesbar bleibt), drei erst auf breiten
  Schirmen — und dort bekommt die textreichste Karte auch die meiste Breite.
  Außerdem behält jede Karte ihre eigene Höhe, statt auf die längste gestreckt
  zu werden. Das Raster und die Karten darin richten sich jetzt nach dem Platz,
  den sie wirklich haben, statt nach der Fensterbreite: drei Spalten erst,
  wenn die dritte auch etwas trägt; die Sitzungs-Zeilen stapeln sich nur noch
  dort, wo es eng ist (vorher blieb vom Gremiennamen „K…" übrig); und die
  Wochen-Ausgabe legt ihre Punkte nebeneinander, sobald sie breit ist — sonst
  liefen die Zeilen quer über den ganzen Bildschirm.
- **Abgelaufene Bürgerbeteiligungen bleiben dokumentiert.** Das Portal der
  Stadt zeigt nur Verfahren, zu denen gerade eine Beteiligung möglich ist —
  abgeschlossene verschwinden dort spurlos. Ratslotse behält sie jetzt und
  markiert sie als beendet, statt sie beim nächsten Abgleich zu löschen. So
  entsteht mit der Zeit eine Übersicht, die es sonst nirgends gibt. (#471)
- **Ehrlichere Beschriftung der Beteiligungs-Karte.** „Bürgerbeteiligung
  läuft" stand auch dort, wo gar keine Frist mehr lief: Beim Schritt
  „Abwägungsergebnis" nennt die Quelle bewusst keinen Zeitraum. Jetzt steht
  dort, was wirklich gilt — laufende Frist, ausliegende Unterlagen ohne
  Frist, oder abgeschlossenes Verfahren mit Enddatum. (#471)

### Neu
- **Hilfe-Seite mit Kontaktformular.** Unter `/hilfe` steht jetzt ein
  Kontaktformular, das ohne Anmeldung funktioniert — wichtig für alle, die
  gerade nicht in ihr Konto kommen. Dazu Antworten auf die häufigsten Fragen
  (Konto löschen, Passwort vergessen, Benachrichtigungen, falsche Angaben).
  Verlinkt von Anmeldung, Registrierung, Startseite und beiden Seiten-Füßen;
  zugleich die Support-Adresse, die Apple für den App Store verlangt. (#471)

### Behoben
- **„Fragen" ruckelt beim Öffnen nicht mehr.** Die Beispielfragen wurden erst
  nach einem Moment durch tagesaktuelle ersetzt — und weil die länger sind,
  sprang der Inhalt darunter um 40 Pixel nach unten, besonders sichtbar in der
  iPhone-App. Jetzt stehen Platzhalter, solange geladen wird, und jede Zeile
  hat von vornherein die Höhe, die sie danach behält. (#472)
- **Ein Tagesordnungspunkt aus „Heute" öffnet die richtige Zeile.** Der Sprung
  landete auf der Sitzung, die Tagesordnung musste man selbst durchsuchen —
  und war sie bereits aufgeklappt, klappte der Link sie sogar zu. Das betraf
  auch die Sprünge aus Benachrichtigungen.
- **Die Lotti-Tour zeigt wieder dorthin, wo sie hinzeigt.** Seit der Trennung
  von Fragen und Suche stand die Station „Das Ratsinfo" auf dem Punkt
  „Fragen", und auf der Fragen-Seite lag der Scheinwerfer über der ganzen
  Seite statt auf etwas Bestimmtem. Die Tour hat jetzt eine eigene Station für
  „Frag den Rat" — mit einer Beispiel-Antwort samt Fußnote und Quelle, damit
  man vor der ersten eigenen Frage sieht, was herauskommt. Außerdem: keine
  Station springt mehr grundlos auf eine andere Seite, und wer die Tour über
  die Befehlspalette startet, sieht auch dann jede Station, wenn die
  „Erste Schritte"-Karte längst abgehakt ist. (#468)

### Verbessert
- **Ratslotse sagt jetzt, wessen Angebot es ist.** Impressum, Anmeldung,
  Registrierung, Konto-Fuß und Seiten-Fuß stellen ausdrücklich klar: ein
  privates Bürgerprojekt, kein Angebot der Stadt Oldenburg, keine Verbindung zu
  Verwaltung, Rat oder Parteien — verbindlich bleiben die amtlichen
  Originale. (#466)
- **Kurze Fragen bekommen kurze Antworten.** Wer nach einem Datum, einer Zahl
  oder einem Namen fragt („Wann wurde der Bebauungsplan 831 beschlossen?"),
  bekommt jetzt zwei Sätze statt einer Seite — inklusive Beleg, aber ohne
  Vorgeschichte und ohne Debatten-Absatz, nach dem niemand gefragt hat.
  Breite Fragen bleiben unverändert ausführlich. (#465)

### Behoben
- **Abgeschnittene Verbands- und Fraktionsnamen in Wortbeiträgen.** Namen
  wurden bei 40 Zeichen hart gekappt — in einer KI-Antwort stand deshalb
  „Fraktion Bündnis Vernunft und Gerechtigk". Neue Beiträge werden nicht mehr
  mitten im Wort abgeschnitten, und der Bestand ist repariert: Die vollen
  Namen stehen in den Anwesenheitslisten derselben Protokolle. (#463)

### Neu
- **Von der Antwort direkt auf die Stadtkarte.** Die Mini-Karte einer
  KI-Antwort führt jetzt mit „Auf der Stadtkarte öffnen" in die große Karte —
  vorgefiltert auf genau die Orte der zitierten Beschlüsse, sichtbar und
  abwählbar als Chip. (#462)
- **Personen-Badges auch in den Belegen.** Die Zugehörigkeit hinter einem
  Namen (Partei bzw. Verwaltung, mit Peek zu Rolle und Zeitraum) gab es nur
  im Antworttext; jetzt tragen auch die Sprecher der Ratsdebatten und die
  Kernaussagen der Parteien dasselbe Abzeichen. Bei Namensvettern bleibt es
  wie bisher aus, wenn der Vorname fehlt. (#462)
- **Die Lupe führt zur Suche.** In der Befehlspalette steht bei leerem Feld
  „Zur Beschluss-Suche" ganz oben, und wenn die Palette nichts findet, bietet
  sie an, den Begriff im Volltext aller Beschlüsse zu suchen. (#462)

### Verbessert
- **Datenschutz-Hinweis dort, wo er ankommt.** Der Satz zum externen
  KI-Dienst steht jetzt in der Frage-am-Anfang-Karte statt nur in den
  Einstellungen — genau einmal, vor der ersten Frage. (#462)
- **Der Gesprächs-Knopf sagt, wo du bist.** Statt „Gespräche" steht dort der
  Titel des aktuellen Gesprächs. (#462)
- **Geteilte Antworten sehen im Messenger nach etwas aus.** Vorschau mit der
  Frage als Titel, dem ersten ganzen Satz der Antwort und einem Ratslotse-
  Bild. (#462)

### Behoben
- **„Ab Mitternacht wieder" stimmt jetzt.** Das Tageskontingent der
  gründlichen Recherche sprang nach UTC um — im Sommer also erst um 2 Uhr
  nachts. Es zählt jetzt nach Oldenburger Zeit, passend zur Anzeige. (#462)

### Behoben
- **Weiterfragen-Vorschläge: Pfeil in beide Richtungen, nichts verdeckt.**
  Wer die Vorschläge einmal weitergeschoben hatte, kam nicht mehr zurück —
  ein Pfeil nach links fehlte. Und die Pfeile lagen auf den Vorschlägen; sie
  stehen jetzt neben der Zeile, wo sie strukturell nichts verdecken können.
  Der dunkle Verlauf darunter ist ersatzlos weg. (#460, #461)

### Behoben
- **App-Navigation: Suche wieder erreichbar, aktiver Tab wieder sichtbar.**
  In der App fehlte der Suche seit der Trennung von Fragen und Suche jeder
  Einstieg — sie steht jetzt zuoberst im „Mehr"-Menü. Außerdem war der
  Sitzungen-Tab nie blau hinterlegt: Die App hängt an jede Adresse einen
  Schrägstrich, woran mehrere Vergleiche scheiterten. Dieselbe Ursache ließ
  auf der Fragen-Seite den „Nach oben"-Pfeil erscheinen und hätte geteilte
  Antwort-Links in der App ins Leere laufen lassen. (#459)
- **Keine schwebenden Pfeile mehr im Gespräch.** „Nach oben" und „zum Ende"
  lagen über dem Senden-Knopf; beide sind weg. Der Eingabebereich ist jetzt
  deckend, dadurch scrollt der Antworttext nicht mehr sichtbar hinter die
  Weiterfragen-Pillen. (#459)
- **Personen-Peek bleibt im Bild.** Bei Personen am Zeilenende lief die
  Karte links aus dem Bildschirm — sie wird jetzt in beide Richtungen an den
  Rand geklemmt. (#459)
- **Scroll-Position überlebt auch auf dem Handy.** Der Tipp auf die Tab-Leiste
  galt fälschlich als „selbst gescrollt" und brach das Wiederherstellen ab;
  außerdem war die Wartezeit zu knapp für das langsamere Nachladen auf dem
  Gerät. (#459)

### Geändert
- **Weniger Ballast auf der Fragen-Seite.** Kürzerer Einleitungssatz, weniger
  Leerraum über Lotti, der Verlaufs-Knopf sitzt in der Titelzeile — und der
  Kontext-Chip über dem Eingabefeld entfällt: Ob eine Anschlussfrage zur
  vorherigen gehört, entscheidet die Suche ohnehin selbst. (#459)

### Behoben
- **Auch große Ratssitzungen bekommen Kurzfassungen.** Bei knapp 50
  Tagesordnungspunkten brach die Zusammenfassung mitten im Satz ab und fiel
  komplett aus — die Sitzung blieb ohne. Lange Tagesordnungen werden jetzt in
  Tranchen zusammengefasst; bricht eine ab, gibt es lieber gar keine
  Zusammenfassung als eine, der stillschweigend Punkte fehlen. (#458)

### Behoben
- **Blättern verschiebt die Seite nicht mehr.** Beim Klick auf die obere
  Seiten-Leiste rutschte die Ansicht bei jedem Wechsel ein Stück hoch und
  runter — der Sprung an den Listenanfang war für die untere Leiste gedacht,
  oben steht man ohnehin schon dort. (#457)

## [1.8.0] – 2026-08-12

### Geändert
- **Fragen und Suche sind jetzt zwei Seiten.** Die KI-Frage — das Herzstück
  von Ratslotse — hat mit /fragen eine eigene Adresse und einen eigenen
  Platz in der Navigation, statt als Modus hinter einem Umschalter der
  Suche zu wohnen. Die Suche konzentriert sich auf das Durchsuchen der
  Beschlüsse und behält eine Brücke ins Ratsgespräch („Fragen"-Knopf im
  Kopf, „Dazu fragen" an Treffern, Handoff bei null Treffern). Alte Links —
  aus Mails, geteilten Antworten und Lesezeichen — leiten automatisch auf
  die neue Seite weiter, samt vorbefüllter Frage bzw. geteiltem
  Gesprächs-Snapshot. (#455)

### Verbessert
- **Blättern ohne Ballast.** Die obere Seiten-Leiste in Suche und
  Sitzungsliste ist jetzt klein und sitzt rechts in der Trefferzeile statt
  als breiter Block über der Liste; der doppelte „Seite X von Y"-Text
  entfällt. Und der Kalender-Link bei Sitzungen ohne Tagesordnung steht in
  der Zeile der „Tagesordnung folgt"-Marke statt in einer eigenen Reihe —
  die Karten wirken wieder gleichmäßig. (#454)
- **Kurzfassungen auch für Sitzungen ohne Benachrichtigung.** Die Sätze unter
  den Tagesordnungspunkten entstanden bisher nur dort, wo jemand eine Meldung
  bekam. Ein Ops-Lauf trägt sie jetzt für alle kommenden Sitzungen und die
  letzten Wochen nach. (#451)
- **Die Sicherung umfasst jetzt wirklich alles.** Gesichert wurden bisher zwei
  fest eingetragene Datenbanken — eine dritte wäre still übersprungen worden.
  Jetzt kommt jede Datenbank mit, dazu die gerenderten Planzeichnungen und die
  Konfigurationsdatei mit den Zugangsdaten (abschaltbar). Ohne Letztere wäre
  nach einem Serververlust jede Anmeldung ungültig gewesen.

### Behoben
- **Reste des früheren Zeitungs-Teils entfernt.** Fünf Tabellen aus der Zeit
  vor dem Ratslotse wurden bei jedem Start neu angelegt, obwohl sie seit der
  Ausgliederung leer sind und niemand sie liest; drei zugehörige
  Daten-Umbauten liefen ebenfalls ins Leere. Alles raus — leere Tabellen
  werden auf bestehenden Installationen mit aufgeräumt, gefüllte bleiben
  vorsichtshalber stehen.

### Verbessert
- **„Dein Thema" prüft jetzt die Vorlage, nicht nur den Titel.** Ob ein
  Tagesordnungspunkt wirklich das eigene Thema betrifft, entscheidet nach der
  Titel-Zuordnung ein zweiter Blick in den Vorlagentext — „Sanierung
  Grundschule X" und „Neubau Sporthalle an der Grundschule X" klingen im Titel
  gleich nah, erst der Sachverhalt trennt sie. Punkte ohne Vorlage (etwa
  Fraktions-Anträge) bleiben beim Titel-Urteil, und fällt die Prüfung aus,
  bleibt die Zuordnung stehen. (#450)

### Behoben
- **Themen-Zuordnung würfelt nicht mehr.** Derselbe Tagesordnungspunkt wurde
  mal gemeldet, mal nicht — die Zuordnung lief mit zufälliger Streuung. Jetzt
  entscheidet sie deterministisch. Außerdem riss eine zu lange Antwort das
  Ergebnis mitten im Datensatz ab und hätte den ganzen nächtlichen Lauf
  beenden können; sie hat jetzt mehr Platz, und ein unbrauchbares Ergebnis
  überspringt nur diese eine Sitzung. (#450)

### Neu
- **Kurzfassung unter jedem Tagesordnungspunkt.** Ein Satz, worum es geht —
  dieselbe Zusammenfassung, die auch in der Tagesordnungs-Mail steht, jetzt
  direkt in der aufgeklappten Tagesordnung. Routine-Punkte
  (Beschlussfähigkeit, Protokollgenehmigung) bleiben bewusst ohne. (#449)

### Verbessert
- **Blättern geht jetzt auch oben.** Suche und Sitzungsliste haben ihre
  Seiten-Knöpfe zusätzlich über der Liste — bisher musste man nach jedem
  Seitenwechsel wieder ans Ende scrollen, um weiterzublättern. (#449)

### Behoben
- **Scrollbalken passen sich dem Dunkelmodus an.** Der Kanal blieb weiß und
  schnitt eine helle Spur durch die dunkle Oberfläche — jetzt färbt der
  Browser Scrollbalken, Auswahlfelder und andere native Bedienelemente
  passend zum Modus. (#448)

### Verbessert
- **Seiten behalten ihren Stand — wie man es von einer App erwartet.** Wer
  in der Sitzungsliste weit nach unten scrollt, kurz auf einen anderen Tab
  wechselt und zurückkommt, steht wieder an derselben Stelle statt am
  Listenanfang. Genauso überleben Suchtext, Ausschuss-Filter und Zeitraum
  den Abstecher. Scrollt man beim Zurückkommen selbst, bleibt die Hand am
  Steuer — dann springt nichts mehr. (#446)

### Verbessert
- **„Morgen" statt „Do., 13.08."** Sitzungen, die heute, morgen oder gestern
  sind, sagen das jetzt auch — im Dashboard und in der Sitzungsliste, das
  genaue Datum bleibt an der Kachel bzw. als Titel. Die Angabe kommt vom
  Gerät und stimmt auch, wenn die App über Mitternacht offen bleibt. (#445)

### Neu
- **Zusagen der Verwaltung werden sichtbar.** „Die Verwaltung sagt zu, den
  Zeitplan vorzulegen" — solche Selbstverpflichtungen stehen in den
  Protokollen, gingen in den Belegen aber unter: Sie sind kurz und nüchtern
  formuliert und verloren jedes Duell gegen ausführliche Reden. Sie haben
  jetzt einen eigenen Kanal, ein eigenes Abzeichen in den Belegen, und die
  Antwort nennt sie ausdrücklich mit Datum. Reine Verfahrens-Floskeln
  („sichert eine Antwort zu Protokoll zu") bleiben draußen.

### Verbessert
- **Wiederholte Fragen antworten fast sofort.** Die Bewertung der gefundenen
  Beschlüsse ist mit Abstand der teuerste Schritt der Suche; sie wird jetzt je
  Frage gemerkt. Wer eine Beispielfrage anklickt, einen Weiterfragen-Chip
  nutzt oder dieselbe Frage später erneut stellt, wartet dafür nicht noch
  einmal — gemessen 3,6 Sekunden auf 0,07 Sekunden bei unveränderter
  Reihenfolge der Treffer. Neue Fragen sind unberührt.
- **Ehrliche Zeitangabe bei der Gründlichen Recherche.** Sie versprach „1–2
  Minuten", brauchte real aber rund 30 Sekunden. Karte, Umschalter und Hinweis
  nennen jetzt den gemessenen Wert.
- **Erste Frage nach einem Neustart ist schneller.** Der Warmlauf lädt nun auch
  die Zusatzkanäle (Pressemitteilungen, Wortbeiträge) vor, statt sie die erste
  Frage bezahlen zu lassen.
- **Angemeldete landen direkt im Dashboard.** Wer eingeloggt ratslotse.de
  aufruft, sieht nicht mehr die Werbeseite, sondern seine Startseite mit
  Themen und Sitzungen. Die Startseite bleibt erreichbar: über „Startseite"
  im Menü-Fuß (bzw. ratslotse.de/?start=1) — dann bleibt sie für die ganze
  Sitzung stehen, auch beim Klick aufs Logo. Nach dem Abmelden erscheint sie
  ohnehin wieder. (#444)

### Neu
- **Tagesordnungen zeigen die Anhänge ihrer Punkte.** Jeder TOP verlinkt
  jetzt seine Dokumente aus dem Ratsinformationssystem — gerade
  Fraktions-Anträge ohne Vorlage hingen bisher nur dort und waren in der
  App unsichtbar. Die Anhänge füllen sich mit dem täglichen Abgleich für
  alle kommenden Sitzungen. (#443)

### Verbessert
- **„Tagesordnung geändert"-Meldungen zeigen nur noch die Unterschiede.**
  Statt der kompletten Liste steht in der Mail, was sich getan hat: neue
  Punkte grün, verschobene und umformulierte gelb (mit dem alten Wortlaut),
  gestrichene rot durchgestrichen. Ein eingeschobener Punkt färbt dabei
  nicht die halbe Liste um, nur weil sich Nummern verschieben — verglichen
  wird über den Titel. (#440)

### Behoben
- **Zurück von der Personen-Seite führt wieder in die Antwort.** Der Sprung
  aus dem Personen-Peek lud die Seite bisher komplett neu — beim
  Zurückkommen war das Gespräch weg und der leere Startbildschirm da. Der
  Link navigiert jetzt in der App, und das aktive gespeicherte Gespräch
  wird beim Zurückkommen automatisch wieder geladen. (#442)
- **Keine doppelte Partei mehr hinter Personennamen.** Nennt der
  Antworttext die Partei direkt hinter dem Namen in Klammern („Ulf Prange
  (SPD)"), ersetzt das Badge die Klammer — geschluckt wird nur das nackte
  Partei-Label derselben Partei, Zusätze wie „(FDP-Fraktion vom 28.07.)"
  bleiben stehen. (#441)
- **Der Personen-Peek bleibt im Bild.** Nahe dem rechten Rand oder der
  Oberkante lief die Info-Karte aus dem Text bzw. wurde abgeschnitten —
  sie richtet sich jetzt nach der verfügbaren Seite aus. (#439)
- **„dein Thema"-Markierungen sitzen am richtigen Tagesordnungspunkt.** Das
  Themen-Matching übernahm die TOP-Nummer ungeprüft vom Sprachmodell — das
  verrutscht bei Nummern-Listen gern um eins (Ö 14.6 trug ein
  Fliegerhorst-Label, gemeint war Ö 14.7). Jetzt liefert das Modell Nummer
  UND Titel; existiert die Nummer nicht oder widerspricht der Titel, gewinnt
  der eindeutige Titel-Treffer — und ist gar nichts auflösbar, gibt es keine
  Markierung statt einer falschen. (#438)
- **Personen-Badges verwechseln keine Namensvettern mehr.** Ein Gast im
  Ausschuss (etwa vom Wasserstraßen-Amt) trug im Text das Badge eines
  gleichnamigen Gremienmitglieds. Gäste, Protokollführung und beratende
  Mitglieder machen den kahlen Nachnamen jetzt mehrdeutig — und bei
  Mehrdeutigkeit entscheidet nur noch ein Vorname im Text, sonst gibt es
  gar kein Badge. (#437)

### Neu
- **Kleine Zugehörigkeits-Badges hinter Personennamen in KI-Antworten.**
  Erwähnt eine Antwort ein Ratsmitglied, steht bei der ersten Nennung ein
  kompakter Punkt in Parteifarbe mit Kürzel dahinter („Lükermann ·Volt");
  Verwaltungsleute tragen „Stadt", Ehemalige einen grauen „ehem."-Punkt —
  nie eine veraltete Rolle als aktuell. Antippen öffnet eine Karte mit
  vollem Namen, Amt bzw. Fraktion, belegtem Zeitraum aus den
  Anwesenheitslisten und dem Link zur Personen-Seite. Die Ämter der
  Verwaltungsspitze („Oberbürgermeister", „Stadtkämmerin") stammen aus den
  Protokollen selbst; bei mehrdeutigen Nachnamen erscheint lieber kein
  Badge als ein geratenes. Funktioniert im Gespräch, im Recherche-Bericht
  und auf geteilten Antworten. (#435)

### Verbessert
- **Der Fragen-Startbildschirm passt auf einen Handy-Bildschirm.** Kürzerer
  Untertitel, weniger Leerraum, mobil drei statt vier Beispielfragen (die
  vierte gibt es weiter am großen Bildschirm) — nichts verschwindet mehr
  hinter dem Eingabefeld. (#433)
- **Kein doppelter Einstieg mehr bei „Was ist …?"-Fragen.** Der Steckbrief
  „Worum geht es?" und die Antwort sagten dort dasselbe — bei einer reinen
  Definitionsfrage *ist* die Antwort die Definition. Die Karte entfällt jetzt
  genau dort; der Hintergrund fließt weiterhin in die Antwort ein, die ihn mit
  Quellen belegt. Bei Sachstands- und Themenfragen („Wie ist der Stand bei der
  Cäcilienbrücke?") bleibt beides stehen — dort ergänzen sich Steckbrief (was
  es ist) und Fazit (wo es steht).

### Behoben
- **Das Eingabefeld der KI-Frage sitzt jetzt wirklich auf der Tab-Leiste.**
  Der zweite Anlauf: `sticky` kann ein Element nur nach oben halten — auf
  kurzen Seiten blieb darunter eine Lücke. Jetzt ist der Composer auf dem
  Handy fest über der Tab-Leiste verankert, ein mitwachsender Platzhalter
  hält das Gesprächsende frei. Dabei eine tiefere Ursache behoben: Die
  Einstiegs-Animation jeder Seite hielt dauerhaft ein `transform` und
  kaperte damit jedes fest positionierte Element der Seite. (#431)

### Neu
- **„Worum geht es?" — Einordnung vor der Antwort.** Nennt eine Frage ein
  bekanntes Objekt (GSG, Cäcilienbrücke, Fliegerhorst), steht jetzt ein kurzer
  Steckbrief darüber: was das ist und was es mit der Stadt zu tun hat. Fragen
  wie „Was ist die GSG und was macht sie?" beantworten reine Beschluss-Zitate
  schlecht — die Beschreibung dazu lag längst in den Themen-Daten, wurde von
  der Frage-Antwort aber nie gezeigt.
- **Ausblick: „Wie es weitergeht" auch bei der schnellen Frage.** Steht das
  Thema demnächst auf einer Tagesordnung, nennt die Antwort Termin, Gremium und
  geplante Behandlung. Bisher blickte nur die Gründliche Recherche nach vorn —
  ausgerechnet bei „Wie ist der aktuelle Stand …?", der häufigsten Frage.

### Verbessert
- **Ehrlicher Hinweis, wenn die Beleglage dünn ist.** Findet die Suche zu einer
  Frage nur wenige und schwach passende Beschlüsse, sagt die Antwort das jetzt —
  statt im gleichen selbstbewussten Ton zu klingen wie bei gut belegten Themen.
  Dazu ein Knopf, der die Gründliche Recherche startet, die auch Gutachten und
  Protokolle liest.
- **Lange Antworten beginnen mit einem Fazit.** Umfangreiche Themen führen jetzt
  mit einer Zeile „Kurz gesagt: …", bevor die Gliederung kommt.
- **Die Aussprache zu einem Bericht steht jetzt auch in der Antwort.** Wenn
  „Frag den Rat" einen Bericht zitiert, kommen die Wortbeiträge aus genau
  diesem Tagesordnungspunkt mit dazu — bisher fand die Suche nur Beiträge,
  die zufällig dieselben Wörter benutzten wie die Frage. Bei der Frage nach
  dem Sondermüll auf dem Fliegerhorst fehlte deshalb die jüngste Debatte vom
  Februar 2026 über erhöhte Vinylchlorid-Werte; die Antwort endete mit einer
  beruhigenden Aussage von Juni 2025. Jetzt ist sie dabei.
- **Keine maschinellen Einschätzungen mehr als Aussage des Rates.** Ratslotse
  bewertet intern die Tragweite jedes Beschlusses. Diese Begründung konnte in
  einer Antwort landen und klang dort wie eine Feststellung aus dem Rathaus
  („Dieser Beschluss wird als weitreichend … eingestuft"). Sie steuert jetzt
  nur noch die Gewichtung und taucht im Text nicht mehr auf.
- **Aufgeräumter Fragen-Screen auf dem Handy.** Aus Tims TestFlight-Feedback:
  Die Gesprächs-Historie sitzt jetzt als Knopf oben rechts im Seitenkopf
  (statt als breite Zeile mitten im Screen), der KI-Datenschutz-Hinweis wohnt
  in den Einstellungen bei der Gespräche-Karte, und der „Gründlich
  recherchieren"-Schalter steht als Pill direkt über dem Eingabefeld. Der
  Composer klebt außerdem in jeder Scroll-Lage an der Tab-Leiste, statt sich
  beim Scrollen vom unteren Rand zu lösen, und der schwebende „Nach
  oben"-Pfeil erscheint im Ratsgespräch nicht mehr (er lag genau über dem
  Senden-Knopf). (#427)

### Behoben
- **Der Ausblick auf kommende Beratungen war immer leer.** Die Abfrage verlangte
  ein leeres Ergebnis-Feld — bei künftigen Terminen steht dort aber die geplante
  Behandlung („Vorberatung", „Kenntnisnahme"). Gemessen: 22 anstehende Termine,
  davon 0 gefunden. Betraf auch den Bericht der Gründlichen Recherche.
- **Lange Sprungmarken-Chips schieben die Seite nicht mehr seitlich weg.**
  Ein langer Abschnittstitel im Recherche-Bericht machte seinen Chip breiter
  als das Telefon — die ganze Seite hing dann angeschnitten in der Luft
  (Tims TestFlight-Screenshot). Jetzt wird der Chip-Text mit „…" gekürzt.
  (#427)
- **„###"-Überschriften in KI-Antworten werden als Überschriften gezeigt.**
  Bisher kannte die Antwort-Darstellung nur „##" — tiefere Ebenen standen
  als rohe Rauten im Text. (#427)
- **Die „Keine passenden Wortbeiträge von:"-Zeile nennt nur noch Parteien.**
  Vorher listete sie alle Anwesenheits-Labels der Protokolle — Verbände,
  Gremienrollen und kaputte Einzel-Label („ADFC", „Elternvertreter", „BSW
  Für RH Dr. Onken"); außerdem erschien „CDU-Fraktion" neben „CDU". Jetzt
  filtert eine kuratierte Ratsparteien-Liste, Schreibvarianten werden
  zusammengeführt. (#427)
- **Die Tagesordnungs-Mail spricht wieder über eine bevorstehende Sitzung.**
  Die Punkte standen in der Vergangenheit („Der GLOBE-Bericht wurde
  vorgestellt"), obwohl der Ausschuss erst noch tagt — das behauptete
  Ergebnisse, die es noch gar nicht gibt. Jetzt heißt es „Vorgestellt wird …"
  bzw. „Der Ausschuss berät über …". (#426)
- **Der Sitzungsort steht wieder in der Mail.** Unter dem Termin blieb eine
  Ortsmarke ohne Ort: Der Scraper suchte ihn in der Überschrift der
  Sitzungsseite, wo er nicht steht — er kommt aus dem Feld „Raum". Damit
  tragen auch die Sitzungslisten in der App wieder ihren Ort; fehlt er
  ausnahmsweise, entfällt die Zeile ganz statt leer dazustehen. (#426)

## [1.7.1] – 2026-08-10

### Behoben
- **Der Eingabe-Composer der KI-Frage liegt wieder über der Tab-Leiste.** Auf
  dem Handy verschwand das Eingabefeld hinter der neuen Tab-Bar-Navigation;
  jetzt klebt es sichtbar darüber. (#424)

## [1.7.0] – 2026-08-10

### Verbessert
- **Keine Anreden-Dubletten mehr im Ratsmitglieder-Verzeichnis.** „Herr Jens
  Freymuth" und „Jens Freymuth" waren zwei Einträge — Anreden (Herr/Frau/
  Ratsherr/Ratsfrau) werden jetzt beim Zusammenführen und in der Anzeige
  entfernt; Titel wie „Dr." bleiben Teil des Namens. (#419)
- **Alle Wortbeiträge einer Person — mit Gremien-Filter.** „Aus den
  Protokollen" zeigte nur die zehn jüngsten Beiträge; wer viel redet, kommt
  aber auf weit über tausend. Jetzt lädt die Liste seitenweise nach, nennt die
  Gesamtzahl und lässt sich auf ein Gremium eingrenzen (mit Anzahl je
  Ausschuss). Dabei behoben: Namensvettern wurden zusammengeworfen — trägt ein
  Protokolleintrag einen anderen Vornamen zum selben Nachnamen, gehört er
  nicht mehr auf die Seite. (#420)
- **Ehrlicher Hinweis auf den Ratsmitglieder-Seiten.** Unter den
  Wortbeiträgen steht jetzt, dass die Protokolle sinngemäß zusammenfassen
  und nicht jede Wortmeldung erfassen — die Liste ist ein Ausschnitt, kein
  vollständiges Redeprotokoll. (#418)

### Neu
- **Die Gründliche Recherche meldet sich, wenn sie fertig ist.** Wer sie in der
  App startet und das Handy weglegt, bekommt eine Mitteilung, sobald der
  Bericht steht — Antippen öffnet ihn. Auch ein Fehlschlag meldet sich, damit
  niemand auf einen Bericht wartet, der nicht mehr kommt; ein selbst
  abgebrochener Lauf bleibt still. Wer gerade zusieht, bekommt kein Banner über
  den eigenen Text. Die Meldung beantwortet eine eigene Handlung und wartet
  deshalb nicht auf das nächste Zustellfenster; nur wer Benachrichtigungen ganz
  abgeschaltet hat, hört auch hier nichts. (#413)
- **Kostenentwicklung bei Geld-Fragen.** Der Geld-Baustein zeigt die
  zitierten Beträge jetzt als „Beträge im Zeitverlauf" — chronologisch mit
  Datum, Balken und Fußnote. Ein „von X auf Y gestiegen"-Vergleich
  erscheint nur, wenn beide Beträge zur selben Vorlage gehören; Beträge
  verschiedener Vorlagen bleiben eine neutrale Zeitreihe (Planungskosten
  und Gesamtkosten wären sonst ein Äpfel-Birnen-Pfeil). Dazu sagt der
  Debatten-Block jetzt ehrlich, dass Protokolle Wortbeiträge sinngemäß
  zusammenfassen — ohne Anspruch auf Vollständigkeit. (#417)
- **Aufgeräumte Navigation auf dem Handy.** Statt drei gestapelter
  Nav-Ebenen (Burger-Menü, wischbare Ansichts-Pills, Modus-Schalter) gibt es
  jetzt eine feste Tab-Leiste unten: Start · Fragen · Sitzungen · Themen ·
  Mehr. Hinter „Mehr" liegen Stadtkarte, Analyse, Quiz, Konto, Feedback,
  Abmelden und die Pflicht-Links — als Liste mit Beschriftung, nicht als
  Icon-Gitter. Das Burger-Menü und die orangene Schwebe-Taste entfallen; der
  Kopf der App behält nur Logo und Suche.
- **Eine Gesprächs-Zeile statt zweier Schwebe-Icons.** Im Ratsgespräch zeigt
  auf dem Handy eine Zeile über dem Chat, in welchem Gespräch du bist, und
  öffnet die Gespräche-Liste als Bottom Sheet — „Neues Gespräch" ist dort
  die erste Aktion. Zeilen lassen sich nach links wischen: Umbenennen oder
  Löschen (Umbenennen ist neu, auch per API). Die Zeile erscheint nur, wenn
  Gespräche gespeichert werden und es etwas zu zeigen gibt; ohne Speichern
  steht stattdessen ein schlichter „Neues Gespräch"-Link über dem
  Eingabefeld. Am Rechner bleibt alles wie gewohnt.
- **„Was sagt Ratsfrau X dazu?" — Fragen zu Personen.** Nennt eine Frage
  ein Ratsmitglied, antwortet „Frag den Rat" aus dessen Wortbeiträgen
  („Laut Protokoll sagte …") statt nur aus Beschlüssen; der Belege-Block
  zeigt die Beiträge der Person. Auf den Ratsmitglieder-Seiten steht neu
  die Sektion „Aus den Protokollen" mit den jüngsten Wortbeiträgen. (#414)

### Verbessert
- **FDP und Volt getrennt statt als Gruppen-Eimer.** Die Protokolle führen
  nur die Ratsgruppe „FDP/Volt" — über die Personen-Stammdaten wird jeder
  Beitrag jetzt der Einzel-Partei des Sprechers zugeordnet: Der
  Parteien-Baustein führt FDP und Volt als eigene Zeilen (Volt mit eigener
  Farbe), und die Fußzeile benennt ehrlich, wenn eine der beiden nichts
  Passendes gesagt hat. „Für Oldenburg" bleibt als Gruppe stehen — mehr
  gibt das Ratsinformationssystem dort nicht her. (#414)
- **Wortbeiträge in voller Länge lesbar.** Die Debatten-Belege unter den
  Antworten waren auf 220 Zeichen gekappt — mitten im Satz. Jetzt lässt
  sich jeder Beitrag komplett aufklappen („Ganzen Beitrag anzeigen"), im
  Ratsgespräch wie auf den Ratsmitglieder-Seiten. Bei Personen-Fragen
  entfällt der Parteien-Baustein — die Frage zielt ja auf eine Person. (#414)

### Behoben
- **Der Fortschritt der Gründlichen Recherche läuft wieder mit.** Die Karte
  blieb beim ersten Schritt stehen und sprang dann unvermittelt zum fertigen
  Bericht: Der Browser fordert komprimierte Antworten an, und die Kompression
  sammelte den Ereignis-Strom der Recherche, statt ihn durchzulassen. Jetzt
  kommen Facetten, gelesene Dokumente und Phasen wieder in dem Takt an, in dem
  sie entstehen. (#413)
- **Vorschläge und Weiterfragen beachten den Recherche-Schalter.** Wer
  „Gründlich recherchieren" eingeschaltet und dann einen Beispiel-Vorschlag,
  einen Weiterfragen-Chip oder „Dazu fragen" angetippt hat, bekam wortlos die
  schnelle Antwort — den Schalter las bisher nur das Absenden im Eingabefeld.
  Jetzt starten auch diese Wege die gründliche Recherche. („Einfacher
  erklären", „Ausführlicher" und „stattdessen schnell fragen" bleiben
  bewusst schnell.) (#413)
- **Geteilte Antworten zeigen wieder alles.** Wer einen „Frag den Rat"-Link
  verschickte, teilte bisher nur Text und Beschlussliste: Die Ratsdebatten,
  der Parteien-Baustein, „Aus den Anlagen" und „Aktuelles von der Stadt"
  fehlten auf der geteilten Seite komplett. Sie wandern jetzt mit in den
  Link — auch für Eingeloggte, die ihn im Ratsgespräch öffnen. Außerdem
  setzte die geteilte Seite ganze Absätze fett, sobald sie mit einer
  Zwischenüberschrift begannen; sie benutzt jetzt dieselbe Darstellung wie
  das Gespräch (Überschriften, Listen, Fettdruck, klickbare Fußnoten).
  Bereits geteilte ältere Links behalten ihren bisherigen Umfang. (#421)
- **Datumsangaben in den Antworten stehen deutsch da.** In Sätzen wie „Laut
  Protokoll sagte Ratsherr Wenzel am 2026-06-01 …" rutschte das technische
  Datumsformat aus den Quellenangaben in den Antworttext. Der Kontext für
  die KI trägt die Daten jetzt durchgängig als „01.06.2026", und bereits
  gespeicherte Antworten werden beim Anzeigen umgeschrieben. (#421)
- **Gespeicherte Gespräche verlieren keine Bausteine mehr.** Beim Öffnen
  eines Gesprächs aus dem Verlauf fehlten bisher die Ratsdebatten, der
  Parteien-Baustein und „Aktuelles von der Stadt" — sie wurden schlicht
  nicht mitgespeichert. Jetzt wandern Debatten, Presse und bei Recherchen
  auch Anlagen, Termine und die Meta-Zahlen mit in den Gesprächs-Snapshot;
  ältere Gespräche bleiben ohne (dort wurden die Daten nie gesichert).
  Außerdem scrollt die Gespräche-Liste jetzt, statt bei vielen Einträgen
  über den Bildschirmrand zu wachsen, und jeder Eintrag zeigt neben dem
  Datum auch die Uhrzeit. (#412)
- **Die Bewertung einer Antwort lässt sich ändern.** Wer einmal „Daumen
  runter" gedrückt hatte, konnte das nicht mehr korrigieren — beide Daumen
  waren danach dauerhaft gesperrt. Jetzt bleiben sie anklickbar: ein Wechsel
  ersetzt die frühere Bewertung (samt hinfällig gewordener Begründung), ein
  erneuter Klick auf denselben Daumen ändert nichts. (#411)

### Verbessert
- **Gutachten und Konzepte sind im Recherche-Bericht belegt.** Die Anlagen
  einer Vorlage flossen zwar schon in die Gründliche Recherche ein, standen im
  Text aber nur als Nebensatz — ob der Bericht sie wirklich benutzt hat, war
  nicht zu erkennen. Jetzt tragen Aussagen aus einer Anlage eine eigene kleine
  Fußnote (a, b, c … statt der Zahlen der Beschlüsse); ein Klick springt zur
  passenden Karte unter „Aus den Anlagen". Anlagen, die gelesen, aber nicht
  belegt wurden, treten optisch zurück.
- **Die Quellen-Liste zeigt beim Ausklappen nur noch die übrigen Treffer.**
  „Alle 28" listete bisher auch die oben schon genannten Quellen ein zweites
  Mal auf, dort in Relevanz- statt Fußnoten-Reihenfolge — die Nummern wirkten
  durcheinandergewürfelt. Der Knopf heißt jetzt „N weitere" und öffnet
  ausschließlich das, was in der Antwort nicht zitiert wurde.
- **„Frag den Rat" schlägt wechselnde Beispielfragen vor.** Statt immer
  derselben zwei Klassiker rotieren die Vorschläge über einen kuratierten Pool
  von 22 Fragen — jede vorab durch das echte Retrieval geschickt und nur
  aufgenommen, wenn sie tatsächlich viele einschlägige Beschlüsse trifft
  (Themen ohne Substanz im Ratsinformationssystem bleiben draußen). Deckt ein
  frischer Vorschlag schon ein Thema ab, wird es nicht doppelt angeboten.
  Außerdem sind die frischen Vorschläge lesbarer: Firmierungen und
  Titel-Anhängsel des Ratsinformationssystems fallen weg, und abgeschnitten
  wird nur noch an der Wortgrenze — statt „Stadion Oldenburg GmbH & Co. KG:
  Stadionneubau Maastrichter " steht dort jetzt „Stadionneubau Maastrichter
  Straße". (#410)
- **Admins steuern die Frage-Limits je Konto.** Im Nutzer-Detail des
  Admin-Panels lässt sich das Tageskontingent der Gründlichen Recherche
  erhöhen oder ganz ausschalten (0 = unbegrenzt, leer = Standard 5) und ein
  Konto von den Rate-Limits der Frage-Endpoints befreien — etwa für
  Power-Nutzer oder Tests. (#409)
- **Die Suche wird akkurater — drei deterministische Signale neben der KI.**
  Erkennt die Frage ein benanntes Objekt (Cäcilienbrücke, Fliegerhorst — auch
  umgangssprachlich als „Cäci"), kommen dessen verknüpfte Beschlüsse gesetzt
  in die Auswahl; Sachstands-Fragen („Wie ist der Stand …?") bevorzugen im
  Ranking frischere Beschlüsse; und durchläuft dieselbe Vorlage mehrere
  Gremien, weist die Antwort ältere Stationen als überholt aus, statt sie als
  aktuellen Stand zu verkaufen. Die Kurzform-Aliasse pflegen wir in derselben
  Tabelle wie die Themen-Dubletten. (#408)

### Neu
- **Die Gründliche Recherche liest jetzt auch die Anlagen.** Gutachten,
  Konzepte und Stellungnahmen zu den Vorlagen (z. B. Schallgutachten und
  Verkehrskonzept zum Stadionneubau) sind als eigener Recherche-Kanal
  durchsuchbar; einschlägige Fundstellen fließen in den Bericht ein und
  erscheinen als Block „Aus den Anlagen" mit Link aufs Original-PDF.
  Die schnelle Frage bleibt davon unberührt (und genauso schnell). (#407)
- **„Gründliche Recherche" — der zweite Frage-Modus.** Ein Umschalter am
  Eingabefeld lässt den Rat gründlich recherchieren: Die Frage wird in
  Facetten zerlegt, deutlich mehr Beschlüsse samt Vorlagen-Volltexten werden
  gelesen, und heraus kommt ein gegliederter Bericht mit Sprungmarken,
  Debatten-Stimmen und einem „Wie es weitergeht"-Block aus dem
  Sitzungskalender. Die Recherche läuft auf dem Server weiter, auch wenn
  man den Tab wechselt, in der App weiternavigiert oder sie ganz schließt —
  der fertige Bericht wartet dann im Gespräch. Dauert 1–2 Minuten,
  5 Recherchen pro Tag; Abbruch (mit Teilbericht aus den fertigen Facetten)
  und Fehler kosten kein Kontingent. (#406)
- **Die KI-Suche kennt jetzt auch die Debatten.** Aus den Sitzungsprotokollen
  werden Redebeiträge, „Anfragen und Anregungen" samt Verwaltungsantwort,
  Einwohnerfragen und Zusagen der Verwaltung herausgelesen und durchsuchbar
  gemacht. Wer nach einem Thema fragt, bekommt neben den Beschlüssen einen
  Block „Aus den Ratsdebatten" — also auch das, was im Rat nur besprochen
  wurde und in keinem Beschlusstext steht (etwa der Streit um die
  Fliegerhorst-Altlasten). Die Antwort nennt solche Stellen ehrlich als
  „Laut Protokoll …", nie als Beschluss. (#387)

### Verbessert
- **Der Parteien-Baustein benennt fehlende Fraktionen.** Findet die Suche
  zu einer aktiven Ratsfraktion keine passenden Wortbeiträge, steht das
  jetzt ausdrücklich in der Fußzeile („Keine passenden Wortbeiträge
  gefunden von: …") — statt die Fraktion stillschweigend wegzulassen. (#405)

### Verbessert
- **Fraktions-Zeilen im Parteien-Baustein sind aufklappbar.** Ein Klick auf
  eine Fraktion zeigt die Original-Wortbeiträge, aus denen ihre Position
  verdichtet wurde — mit Sprecher, Datum und Gremium. (#404)

### Verbessert
- **Die Suche versteht Fragen jetzt aus mehreren Blickwinkeln.** Jede Frage
  wird intern zusätzlich umformuliert (etwa eine Stand-Frage auch als
  Finanzierungs- und Planungs-Frage) — dadurch hängt die Qualität der
  Treffer deutlich weniger davon ab, wie genau man das Thema benennt.
  Und bei Themen mit langer Beratungs-Historie wie dem Stadionneubau
  antwortet „Frag den Rat" jetzt ausführlich und gegliedert: mit
  Zwischenüberschriften, Listen und einem Überblick am Anfang, statt
  alles in vier Sätze zu pressen. (#403)

### Verbessert
- **Von geteilten Antworten direkt weiterfragen.** Wer angemeldet ist,
  springt von einer geteilten Antwort mit einem Klick ins Ratsgespräch —
  die geteilte Frage samt Antwort steht dort als Gesprächsbeginn, und
  Anschlussfragen knüpfen automatisch daran an. Ohne Konto zeigt die Seite
  „Kostenlos registrieren" und „Anmelden"; nach beidem geht es direkt im
  Gespräch weiter, nicht auf dem Dashboard. (#402)

### Verbessert
- **Geteilte Links zeigen eine echte Vorschau.** Wer einen „Frag den
  Rat"-Link in WhatsApp, Signal oder Slack teilt, sieht dort jetzt die
  Frage als Titel und den Anfang der Antwort als Beschreibung — statt
  einer generischen Ratslotse-Karte. Geteilte Antworten bleiben von
  Suchmaschinen ausgenommen. (#401)

### Verbessert
- **Teilen teilt jetzt die Antwort, nicht nur die Frage.** Der Teilen-Knopf
  unter einer Antwort erzeugt einen Link, der genau diese Antwort zeigt —
  mit Frage, Fußnoten und den zitierten Beschlüssen, öffentlich lesbar auch
  ohne Konto. Vorher enthielt der Link nur die Frage, und wer ihn öffnete,
  bekam eine neu berechnete, womöglich andere Antwort. Geteilte Antworten
  werden beim Löschen des Kontos mit entfernt. (#400)

### Verbessert
- **Der Parteien-Baustein zeigt Haltung und Datenbasis.** Jede Fraktion
  trägt jetzt ein kleines Label — „dafür", „dagegen" oder „Haltung
  gewandelt", wenn sich eine Position über die Jahre erkennbar geändert
  hat — und daneben steht, aus wie vielen Wortbeiträgen die Einschätzung
  verdichtet wurde. Die Positionen entstehen jetzt aus der Breite der
  Beiträge je Fraktion statt aus einer einzelnen Aussage, und einmal
  berechnete Einschätzungen werden wiederverwendet, bis neue Wortbeiträge
  zum Thema dazukommen — dann wird automatisch nachverdichtet. (#398)

### Neu
- **Baustein „Das sagen die Parteien".** Bei Themen mit echter Debatte zeigt
  „Frag den Rat" unter der Antwort die Positionen der Fraktionen: Farb-Punkt,
  Haltung in ein bis zwei Sätzen, dazu eine Kernaussage mit Sprecher und
  Datum — als Paraphrase aus den Sitzungsprotokollen, bewusst ohne
  Anführungszeichen. Widersprechen sich Beiträge derselben Fraktion, steht
  „uneinheitlich" daneben. Über „Dazu fragen" an jeder Zeile lässt sich die
  Position einer Fraktion direkt vertiefen. Der Baustein erscheint nur, wenn
  mindestens zwei Fraktionen substanziell zu Wort kamen. (#395)

### Verbessert
- **Antworten geben jetzt auch die Debatte wieder.** Bei Themen mit
  Wortbeiträgen und Pressemitteilungen fasst „Frag den Rat" nicht mehr nur
  die Beschlüsse zusammen, sondern webt das Meinungsbild aus dem Ratssaal
  („Laut Protokoll betonte …") und den Stand der Verwaltung („Laut
  Pressemitteilung vom …") in die Antwort ein — klar getrennt von den
  zitierten Beschlüssen. (#392)

### Verbessert
- **„Frag den Rat" statt „KI-Frage".** Das Frage-Feature tritt jetzt unter
  seinem eigenen Namen auf: Der Umschalter heißt „Suchen | Fragen", Knöpfe
  und Menüs sagen „Frag den Rat", und Kurzfassungen oder Einschätzungen
  heißen schlicht „automatisch" statt „KI". Dass im Hintergrund ein
  KI-Dienst arbeitet, steht weiterhin transparent im Datenschutzhinweis
  unterm Eingabefeld, in der Datenschutzerklärung und in der
  Technik-Doku — nur eben nicht mehr in jeder Überschrift. (#391)

### Verbessert
- **Drei Live-Befunde vom Morgen behoben.** Reißt die Verbindung zum
  KI-Dienst mitten in der Antwort ab, wird sie automatisch einmal neu
  erzeugt statt mitten im Wort stehenzubleiben. Die Bewertung (Daumen
  hoch/runter) steht jetzt unter jeder Antwort, nicht mehr nur unten in der
  Belege-Spalte. Und die Blöcke „Aktuelles von der Stadt" und „Aus den
  Ratsdebatten" zeigen nur noch wirklich einschlägige Treffer: Ein
  Präzisions-Prüfschritt sortiert Beifang wie Ampel-Wartungsmeldungen zur
  Straßenbau-Frage aus — im Zweifel bleibt der Block leer. (#389)

### Verbessert
- **Debatten-Nachschliff aus dem Review.** Findet die KI-Frage zwar keine
  Beschlüsse, aber Wortbeiträge aus den Ratsdebatten, sagt die Antwort das
  jetzt ehrlich, statt „nichts gefunden" neben sichtbaren Belegen zu
  behaupten. Intern: Protokolle ohne einen einzigen Wortbeitrag werden als
  erledigt markiert (statt jede Nacht erneut geprüft), und parallele
  Extraktionsläufe können sich keine verwaisten Suchindex-Einträge mehr
  hinterlassen. (#388)

### Verbessert
- **Die KI-Suche antwortet deutlich schneller.** Zwei Stellschrauben: Die
  Server-VM nutzt jetzt die modernen Vektorbefehle ihres Prozessors (die der
  Relevanz-Sortierung bisher vorenthalten waren), und die Textpaare für die
  Sortierung sind auf das Wesentliche gekürzt — bei unveränderter
  Trefferquote im Eval sinkt die Zeit bis zu den Quellen von gut zwanzig auf
  wenige Sekunden. Außerdem bleibt die Aktionszeile mit Teilen, Vorlesen und
  Bewertung in der Belege-Spalte jetzt immer sichtbar, statt hinter langen
  Quellenlisten zu verschwinden. (#386)

### Verbessert
- **Die Beschluss-Seite bleibt lesbar, auch mit den neuen Angaben.** „Vom
  Vorschlag abgewichen" und der Klima-Check stehen nicht mehr als Kästen in der
  Erzählspalte, sondern als ruhige Symbolzeilen unter „Auf einen Blick" — ein
  Klick öffnet die Erklärung, der Klima-Check trägt vorab ein „relevant"/„nicht
  relevant". Außerdem liest sich „Warum es dazu kam" endlich wie Fließtext: Die
  harten Zeilenumbrüche aus dem PDF werden zusammengezogen (Silbentrennungen
  inklusive), Überschriften und Aufzählungen bleiben stehen. Lange Klima-Texte
  brechen nicht mehr mitten im Wort ab. (#374)
- **Im Ratsgespräch stört weniger.** Der Hinweis auf den externen KI-Dienst
  steht nur noch vor der ersten Frage statt dauerhaft unter dem Eingabefeld,
  und Impressum, Datenschutz, Changelog und Technik-Doku sind vom mitlaufenden
  Seitenfuß in den Menü-Fuß gewandert — auf großen Bildschirmen in die
  Seitenleiste, mobil ins Burger-Menü. (#374)
- **Das Ratsgespräch ist aufgeräumter.** Das Eingabefeld klebt jetzt immer
  unten — auch vor der ersten Frage — und die vorgeschlagenen Weiterfragen
  liegen als Chips direkt darüber, sodass sie beim Lesen langer Antworten
  nicht mehr aus dem Blick geraten. Zitierte Quellen sind kompakte einzeilige
  Pills (Titel + Jahr), Teilen und Drucken sind stille Symbole statt Knöpfe,
  und am großen Bildschirm wandern Quellen, Pressemitteilungen und Aktionen
  in eine eigene Spalte neben dem Gespräch; ältere Antworten zeigen nur noch
  eine aufklappbare Kurzzeile. (#372)
- **Breite Fragen bekommen ausführlichere, strukturierte Antworten.** Die
  starre 2–5-Sätze-Regel ist Geschichte: Eine enge Frage bleibt knapp, aber
  „Was macht die Stadt alles für den Radverkehr?" darf jetzt die wichtigsten
  Vorhaben nacheinander nennen — mit dezentem Fettdruck auf den zentralen
  Projekten und echten Aufzählungen, damit das Auge Halt findet. (#371)
- **Die Weiterfragen-Chips klingen jetzt wie im Gespräch.** Da Anschlussfragen
  den Zusammenhang kennen, müssen die Vorschläge nicht mehr jedes Detail
  wiederholen — aus „Wer stimmte gegen den Ersatzneubau der Grundschule
  Wechloy?" wird ein natürliches „Wer stimmte dagegen?". (#369)

### Verbessert
- **Das Ratsgespräch bekommt seine Bühne.** Auf großen Bildschirmen fassen
  ein getöntes Panel und eine gleich hohe Belege-Karte das Gespräch zusammen:
  Das Eingabefeld klebt an der Panel-Unterkante statt irgendwo im Weiß zu
  schweben, der Verlauf scrollt im Panel, und die rechte Spalte ist nie mehr
  ein leeres Loch — vor der ersten Frage erklärt sie sich, während der Suche
  zeigt sie ein Skelett. Dazu: Der Zeitstrahl erscheint nur noch, wenn es
  wirklich einen Verlauf über mehrere Sitzungen gibt; die Vorlesestimme wählt
  jetzt die beste deutsche Stimme des Geräts statt der erstbesten; und einer
  der Beispiel-Vorschläge fragt konkret nach dem wichtigsten frischen
  Beschluss. Unter der Haube: 31 Feinschliffe aus einer systematischen
  Edge-Case-Prüfung aller Neuerungen dieses Tages — vom Rate-Limit für
  anonymes Feedback über die Planbild-Anzeige in der App bis zur sauberen
  Datums-Ernte aus Protokollköpfen. (#384)

### Hinzugefügt
- **Ratsgespräche lassen sich merken — wenn du willst.** Beim ersten Öffnen
  fragt Lotti einmalig, ob Verläufe im Konto gespeichert werden sollen; nur
  bei „Ja" landet jedes Gespräch unter dem neuen „Gespräche"-Knopf und lässt
  sich auf jedem Gerät weiterführen oder löschen. In den Konto-Einstellungen
  gibt es den Schalter samt der Frage, was beim Ausschalten mit den
  bestehenden Gesprächen passieren soll — und beim Löschen des Kontos
  verschwinden sie mit. (#382)
- **Antworten lassen sich vorlesen.** Ein Lautsprecher-Symbol an jeder
  KI-Antwort liest den Text mit deutscher Stimme vor — Fußnoten und
  Formatierung bleiben stumm, ein zweiter Tipp stoppt. Der Knopf erscheint
  nur, wenn das Gerät Sprachausgabe kann. (#381)
- **KI-Antworten zeigen ihre Orte auf einer Mini-Karte.** Zitiert die Antwort
  Beschlüsse zu konkreten Orten — einer Brücke, einem Baugebiet, einer
  Straße —, erscheint darunter eine kleine Karte mit nummerierten Pins;
  ein Tipp auf den Pin öffnet die Quellen-Vorschau, ein Link führt zur
  großen Stadtkarte. (#380)
- **Fußnoten zeigen erst eine Vorschau.** Ein Klick auf eine Zitat-Nummer in
  der KI-Antwort springt nicht mehr sofort weg, sondern öffnet eine kleine
  Karte: Titel, Gremium, Datum, Ergebnis und die Kurzfassung des Beschlusses —
  von dort geht es in den Beschluss oder zur Quellenliste. (#379)
- **KI-Antworten kann man jetzt bewerten.** Daumen hoch oder runter direkt an
  der Antwort — beim Daumen runter fragt Ratslotse optional, was gefehlt hat.
  Das ist der ehrlichste Qualitätsmesser, den es geben kann: echte Fragen
  echter Nutzer:innen statt Testfälle. Die Weiterfragen-Zeile bekommt außerdem
  einen kleinen Weiter-Pfeil — horizontales Wischen mit der Maus ist mühsam,
  ein Klick nicht. (#378)
- **Das Ratsgespräch denkt mit.** Fünf Ideen aus der Design-Werkstatt: Die
  Antwort sagt ehrlich, worauf sie fußt („stützt sich auf 12 Beschlüsse von
  2019 bis 2026"); ein Kontext-Chip über dem Eingabefeld zeigt, worauf sich
  Anschlussfragen beziehen (✕ beginnt ein frisches Gespräch); unter jeder
  Antwort laden „Einfacher erklären" und „Ausführlicher" zum Nachjustieren
  ein; die Beispielfragen beginnen mit frischen Anlässen aus den jüngsten
  Sitzungen („Neu"); und „Dazu fragen" führt das Gespräch direkt an einer
  Quelle oder einer Beschlusskarte der Suche weiter. Die Weiterfragen-Zeile
  läuft jetzt weich aus statt eine graue Scrollbar zu zeigen. (#377)
- **Bebauungsplan-Beschlüsse zeigen jetzt den Plan.** Die Planzeichnung aus
  der Vorlage — bisher nur ein PDF-Download unter „Anlagen" — steht als Bild
  direkt auf der Beschluss-Seite: antippen öffnet das volle Blatt mit
  Geltungsbereich, Festsetzungen und Planzeichenerklärung. Ein Beschluss zum
  B-Plan lebt vom Visuellen; rund 190 Beschlüsse bekommen so ihr Bild, neue
  Pläne werden wöchentlich nachgerendert. (#375)
- **Beschluss-Seiten zeigen mehr aus den amtlichen Dokumenten — ganz ohne KI.**
  Vier Informationen steckten schon immer in den Vorlagen und Protokollen und
  werden jetzt einfach herausgelesen: der **Klima-Check der Verwaltung**
  (Pflichtvermerk seit 2022, als eigener Kasten unter „Verlauf & Begründung"),
  das **federführende Amt** (in der Quellenzeile der Begründung), der
  **Sitzungsort** vergangener Sitzungen (bisher immer leer) — und ein Hinweis,
  wenn der Rat **deutlich vom Beschlussvorschlag der Verwaltung abgewichen**
  ist, also die Politik die Verwaltung korrigiert hat (rund 8 % aller
  angenommenen Beschlüsse). Auch „Frag den Rat" kennt diese Angaben jetzt.
  Nebenbei erkennt die Antragsteller-Erkennung Fraktionen auch dann, wenn sie
  in Antrags-PDFs erst nach einem langen Briefkopf genannt werden. (#373)
- **„Frag den Rat" ist jetzt ein Gespräch.** Der KI-Frage-Tab wird zum Chat:
  Fragen und Antworten bleiben untereinander stehen, Anschlussfragen („Und
  was kostet das?") verstehen den Zusammenhang, und die vorgeschlagenen
  Weiterfragen führen das Gespräch direkt fort. Die Quellen sind kompakter
  geworden — zitierte Beschlüsse stehen als antippbare Chips mit
  Fußnoten-Nummer direkt unter der Antwort, der Rest wartet hinter „Alle N
  Quellen". Je nach Frage baut die Antwort eigene Elemente ein: eine
  Zeitleiste der Beratungsstationen bei Verlaufsfragen, Beträge bei
  Geldfragen, Antragsteller-Kennzeichnung bei Fraktionsfragen — alles direkt
  aus den Beschlussdaten, nichts davon erfindet die KI. Pressemitteilungen
  erscheinen klar als externe Links, und wer nichts findet, kann die Frage
  mit einem Tipp als beobachtetes Thema anlegen. (#368)

### Hinzugefügt
- **Läuft zu einem Bebauungsplan gerade die Bürgerbeteiligung, steht das
  jetzt am Beschluss.** Ratslotse gleicht täglich die laufenden Planverfahren
  auf oldenburg.planungsbeteiligung.de ab und verbindet sie über die
  Plan-Nummer mit den passenden Beschlüssen: Auf der Beschluss-Seite
  erscheint ein Hinweis mit Verfahrensschritt und Stellungnahme-Frist samt
  Link zu den Planungsunterlagen — und auch die KI-Antwort weist darauf hin,
  wenn sie einen betroffenen Bebauungsplan zitiert. Beschlüsse sagen, was
  geplant ist; jetzt sieht man auch, wann man selbst dazu Stellung nehmen
  kann. (#367)

### Hinzugefügt
- **Die KI-Frage versteht jetzt Anschlussfragen.** Wer nachhakt („Und was
  kostet das?", „Wer ist dafür zuständig?"), bekommt eine Antwort im
  Gesprächskontext: Die Frage-Analyse löst Rückbezüge mit Hilfe der letzten
  Runden auf und macht daraus eine vollwertige Suchfrage — die Suche selbst
  bleibt dadurch genauso treffsicher wie bei einer ausformulierten Frage (im
  Messlauf: 100 % Trefferquote inklusive der neuen Ketten-Testfälle). Das ist
  der Unterbau für das kommende Chat-Interface; die heutige Oberfläche
  verhält sich unverändert. (#366)

### Hinzugefügt
- **„Aktuelles von der Stadt": Die KI-Frage kennt jetzt die Pressemitteilungen
  der Stadt Oldenburg.** Beschlüsse sagen, was entschieden wurde — die
  Pressemitteilungen sagen, was daraus geworden ist (Spatenstich, Eröffnung,
  Termine). Passt eine aktuelle Mitteilung zur Frage, erscheint sie als
  eigener Block unter den Quellen mit Link auf oldenburg.de, und die Antwort
  darf sie als „Laut Pressemitteilung vom …" einordnen — sauber getrennt von
  den zitierten Beschlüssen. Ein täglicher Abgleich holt neue Mitteilungen
  über den RSS-Feed der Stadt. (#365)
- **Die KI-Suche erkennt, was für eine Frage man stellt — und antwortet
  passend.** Verlaufsfragen („Wie ist der Stand bei …?", „Was wurde aus …?")
  bekommen eine chronologische Antwort mit Datumsangaben von der ersten
  Beratung bis zum aktuellen Stand, mit mehr Platz als die üblichen 2–5
  Sätze. Fragen nach einer Fraktion („Was hat die SPD zu … beantragt?")
  holen gezielt deren Anträge und Änderungsanträge in die Quellen — und die
  Antwort sagt ehrlich dazu, dass die Ratsprotokolle kein Stimmverhalten
  einzelner Fraktionen festhalten, statt eines zu erfinden. Bei Geldfragen
  („Wie teuer …?", „Wie hoch …?") stehen die Beträge aus den Beschlüssen in
  der Antwort. Die Erkennung kostet keinen zusätzlichen Wartezeit-Schritt —
  sie steckt im selben Aufruf, der die Frage in Suchbegriffe übersetzt. (#361)

### Verbessert
- **LLM-Kosten sind jetzt echte Zahlen statt Schätzungen.** Jeder KI-Aufruf
  holt die tatsächlichen Kosten vom Anbieter zurück (inklusive der
  datenschutzkonformen Anbieter-Wahl); die Admin-Statistik rechnet damit, und
  der Qualitäts-Messlauf der KI-Suche weist neben Trefferquote und Antwortzeit
  nun auch die Kosten pro Frage in Cent aus — Modellentscheidungen fallen
  damit immer über alle drei Größen: Qualität, Tempo, Preis. Für alte
  Einträge ohne Kostenwert bleibt die Preisliste als Schätz-Fallback. (#364)
- **Die KI-Antwort kommt jetzt in 1–2 Sekunden statt in 20.** Nach der
  Suchbegriffs-Übersetzung war die Antwort-Formulierung der letzte große
  Zeitfresser: Das bisherige Modell brauchte dafür über die
  datenschutzkonformen Anbieter-Routen 3–32 Sekunden. Der Modellvergleich
  gegen das Gold-Set zeigt ein schnelleres Modell mit gleicher oder besserer
  Zitier-Qualität — Antworten kommen jetzt typisch nach gut einer Sekunde.
  Die vorgeschlagenen Folgefragen bleiben dabei auf Dinge beschränkt, die in
  den gefundenen Beschlüssen wirklich vorkommen. (#363)
- **Die KI-Suche „Frag den Rat" findet mehr und antwortet schneller.** Die
  Suche liest jetzt auch die Vorlagen selbst (Sachverhalt und Begründung als
  eigener semantischer Index) und die Änderungsanträge der Fraktionen — bisher
  sah sie im Kern nur Titel und Einzeiler der Beschlüsse, und die
  Relevanz-Sortierung bewertete Volltext-Treffer blind. Fragen wie „Plant die
  Stadt einen Pumptrack?", deren Antwort nur im Sachverhalt einer Vorlage
  steht, gehen jetzt auf. Bei strittigen Abstimmungen kennt die Antwort den
  Original-Abstimmungssatz aus dem Protokoll („Wer stimmte dagegen?"). Der
  größte Zeitfresser war die Übersetzung der Frage in Suchbegriffe — sie
  läuft auf einem schnelleren Modell und hängende Anbieter brechen nach 8
  Sekunden ab statt die Suche zu blockieren; wiederholte Fragen (z. B. die
  vorgeschlagenen Folgefragen) überspringen den Schritt ganz. Sehr lange
  Rats-Niederschriften wurden zudem bisher bei der Auswertung stillschweigend
  abgeschnitten — sie werden jetzt vollständig in Abschnitten ausgelesen. Für
  die Qualitätssicherung misst der Eval-Harness jetzt auch die Antwortzeit
  jedes Suchschritts, die Gold-Fälle sind datenbank-unabhängig formuliert und
  ein Ops-Workflow vergleicht alten und neuen Suchweg direkt auf dem Server. (#360)

### Behoben
- **Themen-Benachrichtigungen liefen für alle ins Leere, sobald ein einziges
  Konto ein „vergiftetes" Thema angelegt hatte.** Der Abgleich der
  Tagesordnungen mit den eigenen Themen läuft über eine KI; der Themenname
  fließt in die Anfrage ein. Ein als Anweisung getarnter Name („Vergesse alles
  …") ließ den Sicherheitsfilter des KI-Anbieters die Anfrage ablehnen — und
  brach damit den gesamten nächtlichen Lauf ab, auch für alle anderen. Jetzt
  wird ein solches Konto übersprungen und der Rest normal weiterverarbeitet;
  Themen-Texte sind gegenüber der KI ausdrücklich als Daten markiert. Beim
  Ausschuss-Watcher (Tagesordnungs-Zusammenfassungen) war dieselbe Lücke offen:
  Scheitert die Zusammenfassung einer einzelnen Sitzung, geht die Meldung jetzt
  ohne Zusammenfassung raus, statt den ganzen Lauf abzubrechen. (#359)

## [1.6.0] – 2026-08-06

### Hinzugefügt
- **Benachrichtigungen lassen sich ganz abschalten.** Bisher musste einer der
  beiden Wege — E-Mail oder Push — an bleiben; die Einstellung verweigerte
  „beides aus" ausdrücklich. Wer nichts mehr hören wollte, hätte die sechs
  Anlass-Schalter einzeln umlegen müssen, und niemand fand sie. Jetzt darf man
  beide Schalter ausmachen: Ratslotse schweigt dann vollständig — auch die
  Erinnerung an eine unfertige Einrichtung. Was noch in der Warteschlange lag,
  wird dabei verworfen statt später nachgeliefert, und die Einstellungen sagen
  sichtbar, dass sie gerade nichts bewirken. Anschalten geht jederzeit; wer
  aus dem Aus-Zustand heraus Push erlaubt, bekommt Push — nicht zusätzlich
  wieder E-Mails.
- **Die Lotsen-Familie lebt.** Auf der Startseite ist aus der gezeichneten
  Familie eine gerechnete Szene geworden: Lotti und die drei Küken folgen dem
  Mauszeiger, blinzeln, atmen, hüpfen und winken, während Ratsdokumente durchs
  Bild treiben. Jede Bewegung bleibt klein — der Körper dreht sich höchstens
  25 Grad, das Hüpfen misst zwei Zentimeter. Das Maskottchen soll wärmen, nicht
  die Bühne übernehmen.
  Die Szene hält sich zurück, wo sie stört: Sie rechnet nicht, sobald sie
  weggescrollt oder der Tab im Hintergrund ist, respektiert „Bewegung
  reduzieren", deckelt sich auf 36 Bilder pro Sekunde und wird auf schmalen
  Fenstern gar nicht erst geladen. Wo sie ausbleibt, steht genau das, was vorher
  dort stand — dieselbe Familie als Zeichnung. Die Startseite wird dadurch nicht
  langsamer: Sie lädt weiter in derselben Größe, die 3D-Technik kommt erst
  danach und nur, wenn sie gebraucht wird.

### Geändert
- **Die Benachrichtigungs-Mails sehen aus wie Ratslotse.** Bisher stand oben nur
  „Ratslotse" als blauer Schriftzug — jetzt trägt die Mail die Bildmarke, klarere
  Abstände und einen richtigen Knopf. Die betroffenen **Tagesordnungspunkte
  stehen als Liste** statt als eine mit Semikolons verkettete Textwand, in der
  man den eigenen Punkt nicht wiederfand. (#352)
- **Der Hauptlink führt jetzt nach Ratslotse**, direkt auf die Sitzung mit
  aufgeklappter Tagesordnung. Das Ratsinformationssystem bleibt als kleiner
  Nebenlink erreichbar — es ist die Quelle, aber nicht der Ort zum Weiterlesen. (#352)
- **Geteilte Links lassen sich jetzt lesen, ohne sich anzumelden.** Wer einen
  Beschluss weiterreichte, schickte die Empfängerin bisher zuerst ins
  Registrierungsformular — bevor sie überhaupt gesehen hatte, worum es geht.
  Das schreckt genau die Leute ab, die man gewinnen will. **Beschluss, Thema
  und Person** — die drei Seiten mit Teilen-Knopf — öffnen sich jetzt für alle,
  mit einer freundlichen Einladung am Ende der Seite statt einer Hürde davor.
  Wer sich von dort aus anmeldet oder registriert, landet **wieder bei dem
  Beschluss**, wegen dem er gekommen ist. Alles Persönliche bleibt, wo es war:
  Stöbern, Suche, eigene Themen, Benachrichtigungen und der Verfolgen-Knopf
  verlangen weiterhin ein Konto.

### Behoben
- **Das Antippen einer Benachrichtigung führt jetzt wirklich zur Tagesordnung.**
  Wer „Dein Thema kommt auf den Tisch" oder „Tagesordnung ist da" antippte,
  landete auf der Startseite statt beim Vorgang. Die Meldung trug die Adresse
  des amtlichen Ratsinformationssystems als Ziel — und damit eine, die aus der
  App herausführt statt in sie hinein; die App tat daraufhin schlicht nichts.
  Beide Meldungen zeigen jetzt auf die Sitzung in der App. Der Link zum
  Ratsinfo steht weiterhin im Text der Nachricht.
- **Und sie führt bis zur gemeldeten Zeile.** Bisher öffnete sich die Sitzung
  am Kopf; der Punkt, um den es ging, stand weit darunter und musste selbst
  gesucht werden. Die Meldung nennt jetzt ihre Tagesordnungspunkte mit, und die
  App scrollt zu genau dieser Zeile. Auch das Aufklappen der Sitzung selbst
  sprang bisher nicht immer mit — beim Antippen einer Benachrichtigung wacht
  die App gerade erst auf, und der Sprung hing an einer Animation, die in
  diesem Moment ersatzlos ausfällt. Er wird jetzt nachgeprüft und notfalls
  hart nachgeholt.
- **Push blieb nach einem Abmelden und erneuten Anmelden stumm.** Wer sich
  abmeldete und ohne Neustart der App wieder anmeldete, hatte danach kein
  angemeldetes Gerät mehr — Benachrichtigungen kamen bis zum nächsten
  vollständigen App-Start nicht an.
- **Sammel-Nachrichten hatten tote Links.** Kommen an einem Tag mehr als zwei
  Meldungen zusammen, werden sie gebündelt — in dieser E-Mail führte kein
  Eintrag irgendwohin.
- **Die Meldung über neue Beschlüsse zu einem Thema stand außerhalb aller
  Regeln.** Sie ging als einzige direkt raus statt über die Warteschlange und
  kam deshalb auch dann an, wenn „Ergebnisse zu meinen Themen" abgeschaltet
  war; die zwei-am-Tag-Grenze und die Nachtruhe galten für sie ebenfalls nicht.
- **Die Meldung über neue Beschlüsse zu einem Thema enthielt keinen Link** —
  nur den Hinweis, man finde die Treffer unter „Meine Themen". Jetzt ist der
  führende Beschluss direkt anklickbar. (#352)
- Ein Thema mit Zeilenumbruch im Namen konnte die Betreffzeile zerlegen; lange
  Namen werden sauber gekürzt statt hart abgeschnitten. (#352)
- **Benachrichtigungen gehen nicht mehr verloren, wenn der Versand klemmt.**
  Fiel der Mailversand aus, galt die Meldung trotzdem als zugestellt — sie war
  damit für immer weg, und zwar genau die, wegen der man die App hat („dein
  Thema steht auf der Tagesordnung"). Jetzt bleibt sie liegen und wird beim
  nächsten Lauf erneut versucht. Außerdem konnte ein Fehler bei einem Konto
  allen dahinter die Post des Tages kosten; jedes Konto steht jetzt für sich.
- **Beim Löschen eines Kontos bleibt nichts mehr zurück.** In der zweiten
  Datenbank stand weiterhin, welche Sitzungen diesem Konto gemeldet worden
  waren.
- **Die Vorschaukarte geteilter Links bleibt lesbar.** Amtliche Beschlusstitel
  werden über 250 Zeichen lang und sprengten die Karte in Messengern; sie
  werden jetzt gekürzt — das Ergebnis („angenommen") bleibt dabei immer
  stehen. Fehlt der Beschlusstext, endete die Beschreibung mitten im Nichts.
- **„1 TOPs", „1 Fragen", „1 Beschlüsse"** — Einzahl wird jetzt als Einzahl
  geschrieben, auf dem Dashboard, in der Sitzungsleiste, bei Themen und Quiz.
- **Auf der „nicht gefunden"-Seite passte der Text nicht zum Gesuchten.** Bei
  einem Thema stand dort „Vielleicht wurde **er** zusammengeführt"; Gästen bot
  sie außerdem eine Suche an, die hinter der Anmeldung endete.
- **Nach dem Anmelden geht es dorthin zurück, wo man hinwollte** — nicht mehr
  stumpf aufs Dashboard.
- **Unsinnig große Zahlen in der Adresse** (`…/decision/99999999999999999999`)
  beantwortet der Server jetzt mit „nicht gefunden" statt mit einem Fehler.

## [1.5.0] – 2026-07-26

### Hinzugefügt
- **Zwei neue Anlässe, beide freiwillig.** **Erinnerung am Vorabend** meldet
  sich um 18 Uhr, wenn morgen eine Sitzung ansteht, die dich betrifft — für
  alle, die zuhören gehen oder vorher noch etwas an ihre Fraktion schreiben
  wollen. Der **Wochenüberblick** fasst sonntags um 18 Uhr die Beschlüsse der
  Woche zu deinen Themen in einer Nachricht zusammen; wer ihn einschaltet, kann
  die einzelnen Meldungen guten Gewissens abschalten. Beide sind **ab Werk
  aus**, und in einer Woche ohne Ratsbeschlüsse — Sommerpause zum Beispiel —
  bleibt es still.
- **Auch verfolgte Vorgänge halten sich an die Grenzen.** Die Meldung „neue
  Station" lief bisher an der Tagesgrenze und der Nachtruhe vorbei und ließ
  sich nicht abschalten. Jetzt beides.
- **Du erfährst jetzt auch, wie es ausgegangen ist.** Bisher meldete sich die App
  *vor* der Debatte und schwieg beim Beschluss — der Moment, auf den alles
  zulief, kam nie an. Neu: **„Es ist entschieden"** für die Tagesordnungspunkte,
  zu denen du vorher schon etwas gehört hast, mit Ergebnis und
  Abstimmungsverhältnis. Weil Beschlüsse erst mit dem Sitzungsprotokoll
  feststehen und das oft Wochen dauert, **nennt die Meldung das Sitzungsdatum**
  („Im Verkehrsausschuss am 8. Juni angenommen") statt Frische zu behaupten.
- **Du bestimmst, wovon du hörst.** „Mein Konto" zeigt jetzt erst **wo**
  (E-Mail, Push) und darunter **wofür** — sechs Anlässe, jeder einzeln
  abschaltbar: Tagesordnung in deinen Gremien, deine Themen auf einer
  Tagesordnung, Ergebnisse, verfolgte Vorgänge, Erinnerung am Vorabend und
  Wochenüberblick. Die letzten beiden sind ab Werk aus.

### Geändert
- **Höchstens zwei Mitteilungen am Tag — und nachts keine.** Bisher schickte
  jeder Anlass sofort los: Wer mehrere Ausschüsse abonniert und Themen pflegt,
  konnte an einem Morgen beliebig viele Mails bekommen, und ein Beschluss um
  22:40 Uhr klingelte um 22:40 Uhr. Jetzt gilt für **alle** Anlässe zusammen:
  höchstens zwei Zustellungen pro Tag — was darüber hinausgeht, kommt gebündelt
  in einer Nachricht statt einzeln — und **zwischen 21 und 7 Uhr nichts**.
  Ratssitzungen enden regelmäßig nach 22 Uhr; das Ergebnis wartet bis zum
  Morgen. Verloren geht dabei nichts.
- **Die Meldung zu einem eigenen Thema ist jetzt ein Satz.** Statt vier
  Emoji-Zeilen („🏛️ Stadtratssitzung – Ihr Thema wird diskutiert", „📅", „📍")
  steht dort, worum es geht: „TOP 4.1: Radweg Nadorster Straße —
  Verkehrsausschuss am 18. August, 17:00 Uhr."
- **Keine zwei Nachrichten zur selben Sitzung mehr.** Wer für eine Sitzung schon
  erfahren hat, *welcher* Tagesordnungspunkt sein Thema betrifft, bekommt nicht
  zusätzlich die allgemeine Meldung, dass das Gremium tagt.
- **Änderungen an einer Tagesordnung melden sich nur noch kurz vorher.** Bisher
  ging jede Änderung raus, auch drei Wochen vor der Sitzung. Jetzt nur noch
  innerhalb der letzten 48 Stunden — davor ist es Verwaltung, keine Nachricht.
- **Gesperrte und unbestätigte Konten bekommen keine Post mehr.**

### Behoben
- **Der Zähler an „Meine Themen" wurde man nicht mehr los.** Wer ein Thema
  löschte, behielt dessen Treffer als ungelesen — die orange Zahl in der
  Navigation zählte sie weiter, obwohl das Thema in keiner Liste mehr stand.
  Damit gab es keine Stelle mehr, an der man sie hätte ansehen können, und die
  Zahl blieb für immer stehen. Beim Löschen eines Themas verschwinden jetzt auch
  seine Treffer, und der Zähler ignoriert Reste gelöschter Themen grundsätzlich.
  Bestehende Altlasten sind aufgeräumt. (#340)
- **Rats-Gruppen werden nicht mehr als falsche Partei ausgewiesen.** Auf der
  Beschluss-Seite stand bei einstimmigen Beschlüssen, welche Fraktionen
  anwesend waren — dort wurde „FDP/Volt" zu **FDP** und
  „Gruppe DIE LINKE./Piratenpartei" zu **Die Linke**. Volt und die Piraten
  fielen jeweils weg, und Mitglieder standen unter einer Partei, der sie nie
  angehörten. Jetzt steht dort der Gruppenname.

## [1.4.0] – 2026-07-25

### Hinzugefügt
- **Der ganze Sitzungsbestand ist erreichbar — mit Seiten und Jahreszahlen.**
  Die Liste endete still bei 100 Einträgen, obwohl das Archiv bis Januar 2018
  zurückreicht: 855 Sitzungen, von denen man 755 nie zu sehen bekam. Jetzt steht
  über der Liste die **echte Gesamtzahl** samt Seitenangabe, und unten blättert
  man durch bis 2018. Weil die Datumskachel nur „JUN 29" zeigt, trennt ab sofort
  eine **Jahreszahl** die Gruppen — beim Scrollen ist damit klar, ob der Juni
  von diesem Jahr ist oder von 2021. Ein Seitenwechsel führt zurück an den
  Listenanfang, statt einen mitten in der neuen Seite stehen zu lassen. (#333)
- **Einen Vorgang verfolgen.** Themen und Ausschuss-Abos sind breite Netze —
  wer *eine* Vorlage auf ihrem Weg durch die Gremien begleiten will (die Schule
  im eigenen Viertel, das Stadion), musste bisher selbst regelmäßig nachsehen.
  Auf der Beschluss-Seite steht jetzt unter „Weg der Vorlage" ein
  **„Diesen Vorgang verfolgen"**. Danach gibt es eine Meldung, sobald eine neue
  Beratungsstation dazukommt oder ein Ergebnis nachgetragen wird — über den
  gewohnten Weg (E-Mail und/oder Mitteilung). Alles Verfolgte steht unter
  *Meine Themen* mit dem letzten und dem nächsten Halt, dort lässt es sich auch
  wieder abbestellen. Was beim Abonnieren schon dastand, gilt nicht als
  Neuigkeit. (#332)
- **Sitzung in den eigenen Kalender.** Jede Sitzung hat einen
  **Kalender**-Knopf, der einen Termin (`.ics`) mit Uhrzeit, Ort, Tagesordnung
  und Ratsinfo-Link erzeugt — im Browser als Download, in der App über das
  Teilen-Blatt. Besonders bei erst terminierten Sitzungen, deren Tagesordnung
  noch aussteht. (#332)
- **KI-Antworten teilen und drucken.** Unter einer fertigen Antwort stehen
  *Teilen* und *Drucken*; der geteilte Link nimmt die Frage mit, die Antwort
  entsteht beim Empfänger aus dessen Datenstand neu. Die Beschluss-Seite hat
  denselben Druck-Knopf — das Druck-Layout gab es längst, es fehlte der
  Auslöser. (#332)
- **Suchverlauf im großen Suchfeld.** Beim Antippen des leeren Feldes stehen
  die letzten fünf Suchen und Vorschläge aus dem, was gerade im Rat läuft —
  bisher hatte das nur die Befehlspalette (⌘K). (#332)
- **Erst begrüßen, dann registrieren.** Nach „Los geht's" geht es direkt zum
  Konto-Erstellen statt zum Anmelden — wer die App zum ersten Mal öffnet, hat in
  aller Regel noch kein Konto. Der Weg zurück steht als „Schon registriert?
  Anmelden" darunter.
- **Erst begrüßen, dann anmelden.** Der Willkommens-Auftakt läuft jetzt vor dem
  Login: Man sieht zuerst, worum es geht, und legt erst nach „Los geht's" ein
  Konto an. Der erreichte Schritt wird zusätzlich am Konto gespeichert, sodass
  eine angefangene Einrichtung eine Neuinstallation übersteht und auf jedem
  Gerät weitergeht.
- **Eine Erinnerung an die Einrichtung.** Wer die Einrichtung anfängt und
  liegen lässt, bekommt nach zwei Tagen **genau eine** freundliche Mail mit dem
  Hinweis, was noch offen ist — kein Newsletter, keine Wiederholung.
- **Name aus der Apple-Anmeldung.** „Mit Apple anmelden" fragt jetzt auch nach
  dem Namen und übernimmt ihn für neue Konten, sodass Lotti von Anfang an
  persönlich grüßt. Ein selbst gesetzter Name wird nie überschrieben.
- **Geführter Start in der App.** Statt drei Karten, die nur erzählen, was
  Ratslotse kann, richtet die App jetzt beim ersten Start mit dir ein, wovon
  sie lebt: **Gremien abonnieren** (jedes mit einem Satz, was dort verhandelt
  wird), **Themen anlegen** (Name genügt — die Beschreibung entsteht
  automatisch) und **Mitteilungen erlauben**. Jeder Schritt ist überspringbar,
  und wer mittendrin abbricht, macht beim nächsten Start dort weiter. (#314)
- **Themen beschreiben sich selbst.** Bisher musste man beim Anlegen eines
  Themas zwei Felder ausfüllen — und die Beschreibung entschied unsichtbar
  darüber, welche Beschlüsse einem später gemeldet werden. Jetzt reicht der
  **Name**: Ratslotse sucht die Beschlüsse dazu und formuliert daraus einen
  passenden Satz. Aus „Fahrradstraßen" wird so „Planung, Einrichtung und
  Unterhaltung von Fahrradstraßen in Oldenburg, u. a. Haareneschstraße und
  Katharinenstraße" — mit konkreten Orten statt Allgemeinplätzen, was die
  Zuordnung künftiger Beschlüsse deutlich treffsicherer macht. Der Text bleibt
  frei überschreibbar.
- **Hinweis, wenn der Rat mit einem Thema gar nichts zu tun hat.** Wer etwas
  einträgt, wozu es keine Ratsbeschlüsse gibt (Privates, Bundespolitik,
  Vertipptes), bekommt das jetzt gesagt — samt Begründung aus dem Datenbestand.
  Anlegen kann man es trotzdem. (#313)
- **Feedback landet jetzt auch im Admin-Bereich.** Rückmeldungen aus der App
  gingen bisher ausschließlich per E-Mail raus — wer sie übersah oder löschte,
  hatte sie verloren. Sie werden nun zusätzlich gespeichert und im Admin unter
  **„Feedback"** aufgelistet: neueste zuerst, mit Art, Absenderin und Zeitpunkt,
  filterbar auf Unerledigtes. Ein Eintrag lässt sich als erledigt abhaken und
  bei Bedarf wieder öffnen. Gibt es Offenes, trägt **„Admin" in der Navigation
  eine Zahl** — dasselbe Zeichen, das „Meine Themen" schon nutzt. Der
  Mailversand bleibt unverändert. (#311)
- **Doppelte Themen werden zusammengeführt.** Die Themen-Erkennung benannte
  dieselbe Sache je nach Beschluss unterschiedlich, sodass es den Bäderbetrieb
  unter vier Namen gab und die Gebäudewirtschaft unter drei — mit auf mehrere
  Seiten verteilten Beschlüssen und Beträgen. Ein neuer Lauf
  (`scripts/merge_entity_aliases.py`) findet solche Dubletten und führt die vom
  Sprachmodell bestätigten zusammen; alte Links landen weiterhin beim richtigen
  Thema. Im Admin-Panel unter „Themen-Dubletten“ lässt sich jede Zusammenführung
  einzeln nachvollziehen und wieder auflösen. Mehrstufige Zusammenführungen
  (A→B, wobei B später zu C wurde) landen dabei am richtigen Endthema und werden
  in der Admin-Liste auch dort einsortiert. (#302, #306)
- **„Hängt zusammen mit …" auf jeder Themen-Seite.** Unter den Kennzahlen stehen
  jetzt verwandte Themen zum Weiterklicken — oben die *belegten* (kommen
  gemeinsam in Beschlüssen vor, mit der Zahl der gemeinsamen Beschlüsse), darunter
  die *thematisch ähnlichen* aus den Embeddings. Beim Fliegerhorst führt das etwa
  direkt zu Entlastungsstraße, Alexanderstraße und Hallensichel-Ost. Die
  Nachbarschaften sind vorberechnet, die Seite wird dadurch nicht langsamer.
- **Verwandte Themen (Datengrundlage).** Neue Berechnung `council/related.py` mit
  Backfill `scripts/build_entity_relations.py` ermittelt je Thema die passenden
  Nachbarn — getrennt nach *belegt* (kommt gemeinsam in Beschlüssen vor, etwa
  Fliegerhorst ── Entlastungsstraße) und *ähnlich* (semantischer Nachbar aus den
  Embeddings, nur zum Auffüllen). Läuft ohne LLM-Aufruf im wöchentlichen
  `weekly_enrich` mit; Gremien und Namens-Dubletten werden herausgefiltert.
- **Geteilte Links erzählen jetzt selbst, worum es geht.** Wer einen Beschluss
  weiterschickte, verschickte bisher fünfmal dieselbe Kachel: In WhatsApp,
  Signal oder Mastodon stand unter jedem Link „Ratslotse — Oldenburger
  Ratsinformationen verständlich". Jetzt steht dort, was drinsteht — **Titel und
  Ergebnis** („Radwegeausbau Nadorster Straße — angenommen"), darunter
  **Gremium, Datum und die Kurzfassung**. Das gilt für Beschlüsse, Themen,
  Ratsmitglieder und Sitzungen; nebenbei bekommen auch Browser-Tabs und
  Lesezeichen sprechende Namen statt viermal „Ratslotse", und Suchmaschinen
  finden die Seiten überhaupt erst.

### Geändert
- **Höchstens ein Hinweis auf „Heute".** Sitzungspause, Live-Sitzung, erste
  Schritte und die Frage nach Mitteilungen konnten sich zu vier Kästen
  stapeln und den eigentlichen Inhalt unter die Falz schieben. Jetzt steht der
  dringlichste davon oben, der Rest hinter einer Pille, die sie auf Tippen
  zeigt. (#332)
- **Ausschuss-Abos lesen sich wie im Einrichtungs-Assistenten**: kurze Namen,
  ein Satz dazu, was das Gremium behandelt, und nach Alltagsbezug sortiert
  statt in amtlicher Reihenfolge. (#332)
- **Nur noch eine Lupe in der Seitenleiste.** Die Befehlspalette sitzt als
  ⌘-Knopf neben dem Logo; die Lupe gehört jetzt allein der Suche. (#332)
- **„Zahl der Woche" führt weiter** — die gezählten Beschlüsse lassen sich
  direkt ansehen; darunter steht „Zuletzt angesehen". (#332)
- Der Sitzungs-Umschalter heißt „Anstehend" statt „Kommend". (#332)
- **Ein verdientes Abzeichen wird jetzt richtig gefeiert.** Bisher blitzte nur
  eine graue Systemmeldung auf, während Konfetti über den ganzen Bildschirm
  regnete — man erfuhr nicht, *warum* man das Abzeichen bekommen hat, und wo es
  jetzt liegt schon gar nicht. An ihre Stelle tritt eine **Karte in den
  Ratslotse-Farben**, die unten über den laufenden Bildschirm fährt: goldene
  Medaille, der Name des Abzeichens, wofür es steht, wie viele von acht man
  gesammelt hat — dazu **„Sammlung ansehen"**, das direkt zur Abzeichen-Karte
  im Konto springt. Sie blockiert nichts, geht nach sechs Sekunden von selbst
  und lässt sich jederzeit wegtippen; mehrere Abzeichen auf einmal kommen
  nacheinander statt gestapelt. In der Sammlung trägt das frische Abzeichen
  danach ein **„NEU"**, bis man es einmal angesehen hat. Wer im System
  reduzierte Bewegung eingestellt hat, bekommt dieselbe Karte ohne Konfetti.
  (#322)
- **Weiterfragen: kompakter auf dem Telefon (Design 24a).** Nach einer Antwort
  standen die Vorschläge als umbrechende Chip-Reihe — auf schmalen Displays
  verdrängten sie damit einen guten Teil der Antwort. Jetzt sind es dort **zwei**
  Vorschläge in je einer Zeile (gekürzt, mit Pfeil), und „Eigene Frage" steht mit
  dem Hinweis in derselben Zeile. Das halbiert die Höhe des Blocks. Auf größeren
  Bildschirmen bleiben es drei Vorschläge mit vollem Text.
- Der Ladekreis beim App-Start sitzt jetzt mittig auf dem Bildschirm statt ganz
  oben halb hinter der Dynamic Island.
- Der Abzeichen-Toast hält sich während der Einrichtung zurück und meldet sich
  erst danach — vorher gratulierte er schon über dem Willkommens-Gruß.
- **Beschluss-Seite aufgeräumt.** Die Seite führte mit einer Wand Amtssprache
  und streute die Kennzahlen über sechs Karten in der Randspalte. Jetzt steht
  **„Lotti erklärt's einfach" ganz oben** — der amtliche Wortlaut folgt darunter
  und lässt sich zuklappen (verbindlich bleibt er, er ist nur nicht mehr das
  Erste, was einen erschlägt). Rechts bündelt eine Karte **„Auf einen Blick"**
  Betrag, Abstimmung, Antragsteller und Wichtigkeit; die Anlagen sind zu den
  **Dokumenten** gewandert, wo die übrigen Datei-Links stehen — aus sechs Karten
  werden drei. Anträge, Endergebnis und das Warum stehen unter einer gemeinsamen
  Überschrift **„Verlauf & Begründung"**, und bei den ähnlichen Beschlüssen sind
  zunächst die zwei relevantesten zu sehen. Reine Anordnung — es fehlt nichts,
  alles ist nur dort, wo man es sucht. (#305)
- **Beschluss-Seite: klarer, was aus dem Protokoll und was aus der Vorlage
  stammt.** „Beschlusstext" und „Aus der Vorlage · Beschlussvorlage" standen
  unkommentiert untereinander — die zweite Überschrift las sich, als stünde dort
  der Beschlussvorschlag, dabei steht dort die **Vorgeschichte**. Jetzt sagt eine
  Zeile unter jeder Überschrift, was man liest: **„Was beschlossen wurde —
  Wortlaut aus dem Sitzungsprotokoll"** bzw. die Überschrift **„Warum es dazu
  kam"** mit dem Zusatz „Sachverhalt und Begründung aus der Beschlussvorlage der
  Verwaltung". Die amtlichen Begriffe bleiben also sichtbar, sind aber nicht mehr
  der einzige Anhaltspunkt. Nebenbei entfällt in der Vorlagenart die
  RIS-Katalog-Klammer („Berichtsvorlage (bis 31.12.2022)" → „Berichtsvorlage").
  (#304)
- **KI-Frage: kürzere Trefferliste.** Unter der Antwort standen bisher **alle**
  gefundenen Beschlüsse — bis zu 40 Karten, obwohl davon meist nur eine Handvoll
  in der Antwort zitiert wird. Jetzt zeigt Ratslotse standardmäßig die **acht
  relevantesten plus alle zitierten** (die bleiben immer sichtbar, egal wie weit
  hinten sie stehen); der Rest kommt per **„Alle N anzeigen"**. Die Reihenfolge
  bleibt unverändert, und die Fußnoten in der Antwort springen weiterhin
  zuverlässig zur richtigen Quelle — auch wenn sie eingeklappt wäre. (#301)
- **Der App-Start zeigt die App, nicht ein Warterad.** Solange die Anmeldung
  geprüft wurde, ersetzte ein Kreisel auf leerer Fläche die ganze Oberfläche —
  jeder Start begann mit etwas, das nach hängender Seite aussah. Jetzt stehen
  Logo und Navigation sofort, nur der Inhalt füllt sich nach.
- **Analyse, Ziele, Mitglieder und Themen laden wie der Rest der App.** Statt
  eines Kreisels auf leerer Fläche steht dort jetzt die **Form** des Inhalts
  (Diagramm bzw. Tabelle) — man sieht sofort, was gleich kommt und wie viel,
  und nichts springt beim Eintreffen. Beim Seitenwechsel gibt es dieselbe
  Rückmeldung sofort. Für echte Momente — Karte, Speichern — bleibt der Kreisel.
- **Der Installieren-Dialog zeigt jetzt, worum es geht.** Beim Hinzufügen zum
  Startbildschirm gab es bislang nur Adresse und Symbol; jetzt liegen drei
  echte Bildschirmfotos bei (Telefon und Desktop). Außerdem passt die Farbe der
  Statusleiste jetzt exakt zur Kopfleiste — vorher lag darüber ein leicht
  hellerer Streifen.

### Entfernt
- **Rund 700 Zeilen toter Code raus** — nach Wochen Umbau hatte sich einiges
  angesammelt, das nichts mehr aufruft: die letzten Überreste des
  ausgegliederten Zeitungs-Scrapers (Artikel-Themen-Zuordnung, Ausgaben,
  Volltextsuche, Presse-Verknüpfungen zu Beschlüssen), drei nicht mehr
  eingebundene Oberflächen-Bausteine, zwei Rate-Limits ohne Endpunkt und drei
  API-Routen, die kein Client abruft. Für Nutzer:innen ändert sich dadurch
  nichts; die Tabellen zum Löschen alter Konten-Daten bleiben absichtlich
  erhalten. „In der Presse" auf der Beschluss-Seite war schon vorher auf die
  reine NWZonline-Suche umgestellt — der ungenutzte Vorschlags-Kanal daneben
  ist jetzt auch im Code weg.

### Behoben
- **Tagesordnungspunkte führen jetzt zum Beschluss.** In einer aufgeklappten
  Sitzung war jeder Punkt toter Text; auch der Ergebnis-Punkt daneben blieb
  unsichtbar, weil die Tagesordnung ihre Nummern mit Präfix führt („Ö 6.1") und
  das Protokoll ohne („6.1") — der Abgleich traf nie. Beide greifen jetzt. (#332)
- **„Zurück" führt nicht mehr aus der App.** Wer einen Beschluss über eine
  Mitteilung oder einen geteilten Link öffnete, landete beim Zurück-Tippen im
  Nichts. Jetzt geht es zur zugehörigen Sitzung. Zusätzlich lässt sich mit
  *Vorheriger/Nächster TOP* direkt durch die Beschlüsse einer Sitzung
  blättern. (#332)
- **„Alle ansehen" bei einem Thema öffnet die richtige Suche** — mit Filtern,
  Sortierung und teilbarer Adresse, statt eines Dialogs ohne all das. (#332)
- **Treffer werden vollständig hervorgehoben.** Bei mehreren Suchwörtern
  („radwege innenstadt") war vorher nichts markiert, weil nur die Eingabe als
  Ganzes gesucht wurde. Jetzt wird jedes Wort an jeder Fundstelle
  hervorgehoben. (#332)
- **Laufende KI-Antwort abbrechen.** Ein **Stopp** hält den bereits
  geschriebenen Text mit dem Vermerk „abgebrochen" und gibt die Eingabe sofort
  frei. (#332)
- **Sitzungen, Stadtkarte und Analyse sind auf dem Telefon wieder direkt
  erreichbar** — über eine Ansichtsleiste über der Seite statt nur über das
  Menü. (#332)
- **Die Erinnerung an eine offene Einrichtung ging nie raus.** Der zuständige
  tägliche Lauf stürzte bei jedem Start sofort ab (ein fehlender Datenbank-Pfad),
  noch bevor er überhaupt nach offenen Einrichtungen sah — und weil er zusätzlich
  die Server-Konfiguration nicht einlas, konnte nicht einmal die Fehlermeldung
  darüber verschickt werden. Beides behoben und mit Tests abgesichert.
- **Fehlgeschlagene Apple-Anmeldungen bleiben nicht mehr stumm.** Schlug die
  Anmeldung fehl, passierte sichtbar gar nichts — der Code behandelte jeden
  Fehler wie einen Abbruch durch die Nutzer:in. Jetzt wird nur ein echter
  Abbruch stillschweigend hingenommen; alles andere sagt Bescheid und landet im
  Fehlerprotokoll. (Der Auslöser diesmal: Die Seite war nicht erreichbar.)
- **Ins Beschreibungsfeld tippen zoomt nicht mehr hinein.** Beim Anpassen eines
  Themas sprang iOS beim Antippen in das Feld hinein, weil die Schrift kleiner
  als 16 Pixel war.
- **„Mit Apple anmelden" im Browser geht wieder.** Der Browser schickt eine
  andere Kennung als die App (Services ID statt Bundle-ID). Der Server kannte
  diese Kennung nur, wenn sie eigens als Umgebungsvariable hinterlegt war —
  fehlte sie, wurde jede Anmeldung über den Browser abgewiesen, während sie in
  der App weiter funktionierte. Beide Kennungen sind jetzt fest hinterlegt.
  Abgewiesene Anmeldungen nennen im Server-Log außerdem den Grund, sodass eine
  Fehlkonfiguration nicht mehr wie ein gefälschtes Token aussieht.
- **„Thema anpassen" (Einrichtung): mehr Platz, ruhigeres Laden.** Das
  Blatt von unten war zu niedrig — für die vollständige Beschreibung musste man
  fast immer scrollen, und beim Scrollen bewegte sich die Seite dahinter mit.
  Jetzt reicht es weiter nach oben, das Beschreibungsfeld zeigt sechs statt drei
  Zeilen, „Abbrechen"/„Speichern" bleiben immer sichtbar, und die Seite darunter
  hält still. Statt Spinner und „prüft…" zeigt die Treffer-Zeile beim Nachschauen
  angedeutete Platzhalterzeilen, sodass beim Eintreffen des Ergebnisses nichts
  mehr springt.
- **Mitteilungen wurden nach dem Einrichten nicht wirklich zugestellt.** Schritt 3
  holte zwar die Erlaubnis auf dem Gerät ein, stellte den Zustellweg des Kontos
  aber nicht um — es blieb auf „nur E-Mail". Zu erkennen war das nur daran, dass
  „Heute" danach weiter um Erlaubnis bat: zu Recht.
- Die Karte „Mitteilungen aktivieren" verschwand nicht mehr, wenn sie einmal
  sichtbar war — selbst nachdem Push längst an war.
- Der Tour-Hinweis zur Beschluss-Suche empfahl die Taste „/", die es auf dem
  Handy nicht gibt.
- **Themen werden jetzt wirklich geprüft.** Bisher konnte man beliebige Sätze —
  auch getarnte Anweisungen an die KI — als Thema anlegen: Der Hinweis erschien
  erst, nachdem gespeichert war. Jetzt gibt es drei Fälle statt zwei. Ein Thema
  mit Beschlüssen wird wie gehabt beschrieben. Eine Sache, die es in Oldenburg
  gibt, über die der Rat aber noch nicht entschieden hat — etwa eine bestimmte
  Grundschule —, lässt sich anlegen, mit dem ehrlichen Hinweis „darüber wurde
  noch nicht entschieden, Lotti meldet sich, sobald es so weit ist". Und was gar
  kein Ratsthema ist, wird mit Begründung abgelehnt statt still gespeichert.
- **Keine erfundenen Treffer mehr.** Unter „Grundschule Krusenbusch" standen
  „12 Beschlüsse passen dazu" — gemeint waren Beschlüsse über *andere* Schulen.
  Es wird nur noch gezählt, was wirklich zum Thema gehört.
- Beim ersten Start klappte auf dem iPhone die Tastatur über dem
  Willkommens-Gruß auf.
- Lotti ragte auf der Registrieren-Seite in die Dynamic Island.
- Der „Bitte bestätige deine E-Mail"-Hinweis erschien mitsamt Navigation und
  Suche, obwohl beides noch ins Leere führt — er steht jetzt für sich.
- Nach dem Klick auf den Bestätigungslink blieb die Seite stehen; wer die App
  wechselte, fand sie später ohne erkennbaren Grund wieder vor. Sie geht jetzt
  von selbst weiter.
- Mehrere Abzeichen-Meldungen stapelten sich beim ersten Login übereinander —
  jetzt fasst eine Meldung sie zusammen.
- Die „Erste Schritte"-Karte sagte gleich beim ersten Öffnen „Weitermachen" und
  sprang stumm auf die nächste Seite. Sie sagt jetzt „Tour starten" und startet
  die geführte Tour, in der Lotti erklärt.
- Beim ersten Start klappte auf dem iPhone sofort die Tastatur über dem
  Willkommens-Gruß auf — das Eingabefeld der darunterliegenden Anmelde-Seite
  hatte sich den Fokus geholt.
- Ungültige Eingaben in Formularen zeigten die rohe Fehlermeldung des Servers
  („[{\"type\":\"value_error\",\"loc\":…"). Jetzt steht dort ein Satz, z. B.
  „Diese E-Mail-Adresse ist ungültig."

- **Themen-Vorschläge sind nicht mehr zu breit.** Unter den vorgeschlagenen
  Themen konnten Gattungsbegriffe wie „Klima" oder „Bericht" auftauchen — als
  Abo hätten sie halb Oldenburg eingesammelt. Vorschläge durchlaufen jetzt
  dieselbe Vagheits-Prüfung wie selbst angelegte Themen; was sie nicht besteht,
  wird gar nicht erst angeboten. (#313)
- **Vagheits-Prüfung schlug Zeitungs-Formulierungen vor.** Ihre Verbesserungs-
  Vorschläge begannen mit „Artikel über …" — ein Überbleibsel aus der Zeit, als
  Ratslotse Zeitungsartikel filterte. Sie beschreiben jetzt die Sache selbst,
  passend dazu, dass Themen gegen Ratsbeschlüsse geprüft werden. (#313)
- **Personen-Seite: Ämter sind auf dem Handy wieder lesbar.** Die Zeitleiste der
  Ämter stand zweispaltig — Name links, Balken rechts. Auf schmalen Bildschirmen
  fraß die Namensspalte den Platz: Gremien standen abgeschnitten da
  („Wirtschaft & Dig…"), und junge Ämter schrumpften zu einem Punkt. Jetzt steht
  der **Name in voller Breite über dem Balken**, das Jahr („seit 2011") rechts
  daneben, und der Balken nutzt die ganze Zeile auf einer gemeinsamen Zeitskala —
  so bleiben Amtsdauern vergleichbar. Dasselbe gilt für „Präsenz je Gremium".
  Auf großen Bildschirmen bleibt die zweispaltige Zeitleiste. (#312)
- **Feedback-Dialog reißt kein Menü mehr auf.** Beim Öffnen von „Feedback geben"
  klappte auf dem iPhone sofort die Auswahlliste für die Art auf — noch bevor
  man den Dialog lesen konnte. Ursache war der automatische Fokus auf das erste
  Eingabefeld, was iOS als Aufforderung versteht, das Rad-Menü zu zeigen. Der
  Dialog fängt den Fokus jetzt selbst ab. (#310)
- **KI-Antworten nennen nicht mehr Datum und Tragweite mitten im Satz.** Die
  Antworten lasen sich stellenweise wie ein Aktenvermerk — „… beschlossen
  (2026-04-20, Tragweite: hoch)". Beides steht ohnehin bei den Quellen unter
  der Antwort. Die Tragweite bekommt die KI weiterhin mitgeteilt, aber nur noch
  zur Gewichtung, nicht zum Zitieren. Fragt jemand ausdrücklich nach dem
  Zeitpunkt, steht das Datum selbstverständlich weiter in der Antwort. (#309)
- **App: „Frag den Rat" scheiterte weiterhin mit „Load failed".** Der erste
  Anlauf hatte dem Streaming-Endpoint zwar Freigabe-Header für die App
  spendiert, die Liste war aber unvollständig: Sie nannte nur `Content-Type`
  und `Authorization`, während die App zusätzlich eine Client-Kennung
  mitschickt. Der Browser bricht solche Anfragen ab, **bevor** sie den Server
  erreichen — deshalb war im Log auch nichts zu sehen. Die Freigabe spiegelt
  jetzt die tatsächlich angefragten Header, statt eine Liste zu pflegen, die
  beim nächsten Zusatz wieder auseinanderläuft. Rein serverseitig — die
  bestehende App funktioniert nach dem Update ohne Neuinstallation. (#308)
- **KI-Frage: Quellenangaben werden wieder zuverlässig erkannt.** Hängte die KI
  Zusatzangaben in eine Quellenklammer („[8525, 20.04.2026, Tragweite: hoch]"),
  erkannte Ratslotse das nicht als Quellenangabe: Die Fußnote fehlte, und die
  rohe Klammer stand mitten im Antworttext. Jetzt zählt in solchen Fällen die
  erste Zahl als Quelle, der Rest verschwindet aus der Anzeige — und die KI wird
  ausdrücklich angewiesen, nur die Nummer in die Klammer zu setzen. (#301)
- **KI-Frage: Weiterfragen sind sofort sichtbar.** Die Anschlussfragen standen
  **hinter** der Liste der gefundenen Beschlüsse — bei einer breiten Frage sind
  das schnell Dutzende Karten, die man erst durchscrollen musste, bevor die
  Vorschläge überhaupt auftauchten. Jetzt stehen sie direkt unter der Antwort,
  die Trefferliste darunter. (#298)
- **Die Lotti-Tour hakt „Erste Schritte" jetzt wirklich ab.** Wer die Tour
  komplett durchlief, stand danach trotzdem bei **1/5**, und der Knopf lud weiter
  zum „Tour starten" ein. Grund: Die Tour führte Analyse und Stadtkarte gar nicht
  vor, und was sie zeigte, wurde nur zufällig abgehakt — nämlich dann, wenn eine
  Tour-Station zufällig genau der Kurs-Seite entsprach. Jetzt zeigt die Tour auch
  Analyse und Stadtkarte, und jede Station meldet den Bereich ausdrücklich als
  entdeckt. „Erstes Thema anlegen" ist als Punkt entfallen — er verlangte ein
  echtes Thema und war damit der einzige, den die Tour nicht abhaken konnte.
  Nach dem Durchlauf steht die Leiste damit auf **4/4** und feiert.
- **Themen bearbeiten: überall der gute Editor.** Für dieselbe Aufgabe gab es
  zwei verschiedene Masken — im Einrichtungs-Assistenten ein Blatt mit
  Beschriftungen, Live-Treffervorschau („Passt gerade auf") und
  „Neu generieren", auf der Themen-Seite ein karger Dialog mit zwei
  unbeschrifteten Feldern. Jetzt zeigen **beide Wege dasselbe Blatt**; auf der
  Themen-Seite lässt sich darin zusätzlich der Name ändern. Auf großen
  Bildschirmen erscheint es als mittiger Dialog statt in voller Breite.
- **Stadtkarte: Quellenangabe wieder lesbar.** Die Legende lag als Kästchen
  unten links auf der Karte — auf dem Telefon brach sie auf zwei Zeilen um und
  legte sich damit über den OpenStreetMap-Nachweis; beides war unleserlich.
  Sie steht jetzt unter der Karte.
- **Quiz: Kategorien nicht mehr hinter der Start-Leiste.** Ganz nach unten
  gescrollt verdeckte die schwebende „Quiz starten"-Leiste die
  Kategorie-Auswahl dauerhaft — man konnte sie nicht antippen.
- **Kein Hineinzoomen mehr in der Admin-Suche und im Quiz-Editor.** Die Felder
  standen unter 16 px, worauf iOS beim Antippen in die Seite zoomt.
- **Abgeschnittene Platzhalter.** „Frag den Stadtrat — z." (KI-Frage), „In
  Tagesordnungen suchen (z. B." (Sitzungen) und drei weitere brachen auf dem
  Telefon mitten im Wort ab. Jetzt passen sie.
- **Anzeigename ist jetzt auch im Formular freiwillig.** Der Server nimmt ihn
  seit jeher optional, „Mit Apple registrieren" liefert gar keinen — nur das
  Registrieren-Formular verlangte ihn und ließ sonst niemanden vorbei.
- **„Bitte Seite neu laden" ist weg.** Ging eine Abfrage schief, stand da ein
  roter Satz — die Bitte an dich, unsere Arbeit zu machen. Ein Funkloch in der
  Bahn reichte, und die Seite blieb kaputt. Jetzt steht dort eine Karte mit
  ratlosem Lotti und einem **„Nochmal versuchen"**-Knopf; der Rest der Seite
  bleibt stehen. Betrifft Themen und alle sechs Admin-Bereiche — die
  Cron-Übersicht verschwand bei einem Fehler bisher sogar spurlos.
- **Die Trefferzahl wird jetzt vorgelesen.** Beim Filtern oder Blättern wechselte
  die Ergebnisliste für Vorleseprogramme lautlos: Sehende sahen „34 Beschlüsse",
  alle anderen nichts. Jetzt wird die Änderung angesagt — samt Seitenzahl.
- **Eine abgelaufene Sitzung frisst deinen Text nicht mehr.** Wer zwei Minuten an
  einer KI-Frage oder einer Themen-Beschreibung geschrieben hatte und dabei
  abgemeldet wurde, fand danach ein leeres Feld. Jetzt wird der Entwurf
  gesichert, du landest nach dem Anmelden **wieder an derselben Stelle**, und
  der Text steht wieder da.
- **Nicht gefunden heißt nicht mehr rausgeworfen.** Wer einem alten Link folgte
  — etwa auf einen inzwischen zusammengeführten Beschluss —, landete auf einer
  nackten 404-Seite ohne Navigation und ohne Suche; der Browser-Pfeil war der
  einzige Weg zurück. Jetzt bleibt die App drumherum stehen, die Meldung nennt
  konkret, was fehlt („Diesen Beschluss finde ich nicht"), und darunter steht
  ein **Suchfeld**, das direkt weiterhilft.
- **Tastatur-Fokus im Menü und in den Filtern wieder sichtbar.** Das
  Seiten-Menü und die Filter-Auswahl hatten den Fokusrahmen abgeschaltet, ohne
  einen eigenen zu setzen — wer mit Tabulator arbeitet, stand auf dem
  Schließen-Knopf und sah nichts. Jetzt derselbe Ring wie in den Dialogen.

### Sicherheit
- **Admin-Rechte nur noch mit Adress-Nachweis.** Bisher wurde die Rolle direkt
  bei der Registrierung aus der eingetippten E-Mail abgeleitet: Wer die in
  `WEB_ADMIN_EMAIL` hinterlegte Adresse als Erster registrierte, bekam sofort ein
  aktives Admin-Konto — ohne je nachzuweisen, dass ihm dieses Postfach gehört.
  Zusätzlich wurde die erste Registrierung auf einer leeren Nutzertabelle
  ungefragt zum Admin (auch über „Mit Apple anmelden"). Beides ist weg: Die
  Registrierung vergibt keine Rolle mehr, Admin entsteht erst, wenn der
  Bestätigungslink an die konfigurierte Adresse eingelöst wurde und noch kein
  Admin existiert. **Für den Betrieb:** Auf einer frischen Installation muss die
  Admin-Adresse einmal den Bestätigungslink klicken; ohne `RESEND_API_KEY` (kein
  Mailversand) übernimmt das neue `scripts/grant_admin.py <adresse>` — worauf
  Registrierung und API-Start per Warnung im Log hinweisen.
- **Anmeldung verrät nicht mehr, welche Adressen ein Konto haben.** Der
  Passwort-Check lief nur, wenn das Konto existierte, ein unbekannter Login kam
  darum messbar schneller zurück (~6 ms gegenüber ~58 ms). Jetzt wird in beiden
  Fällen gleich viel gerechnet; die Antwortzeit gibt nichts mehr preis.
- **Fehlerhafte Suchausdrücke stürzen die Volltextsuche nicht mehr ab.** Eine
  Anfrage wie `hafen -markt` ist für SQLite-FTS5 ungültig und schlug bisher als
  unbehandelter Fehler durch; sie zählt jetzt als „nichts gefunden".

## [1.3.0] – 2026-07-23

### Hinzugefügt
- **KI-Frage: Weiterfragen statt Sackgasse.** Unter jeder Antwort stehen jetzt
  **drei Anschlussfragen**, die zur gerade gelesenen Antwort passen (z. B. „Wer
  stimmte gegen den Radverkehrsplan?") — ein Tipp darauf startet sofort die
  nächste Frage. Daneben führt **„Eigene Frage"** zurück ins Eingabefeld. Die
  Vorschläge entstehen ohne zusätzliche KI-Anfrage aus derselben Antwort; wenn
  das Modell keine liefert, leitet Ratslotse sie aus den gefundenen Beschlüssen
  ab, sodass jeder Vorschlag garantiert zu etwas führt. (#292)
- **App: Zurückwischen vom Bildschirmrand.** In der iOS-App kommst du jetzt wie
  gewohnt mit einer **Wischgeste vom linken Rand** eine Seite zurück (und vom
  rechten wieder vor) — passend zur Vor-/Zurück-Navigation der App. (#286)
- **Eigene Quizfragen:** Auf der Quiz-Seite kannst du jetzt **eigene Fragen
  anlegen und üben** — mit 2–4 Antworten, optionalem Ort (Stadtteil),
  Kategorie und Erklärung. Eine Übungsrunde mischt 10 deiner Fragen durch
  die normale Spiel-Ansicht, nie geübte und schwache zuerst; die Liste
  zeigt je Frage den Stand („3× geübt, 100 %"). Eigene Fragen sind privat
  und geben bewusst **keine Punkte** — sonst könnte man sich Punkte selbst
  schreiben. (#262)
- **Eigene Schätzfragen:** Wählt man beim Anlegen die Kategorie
  **„Schätzfrage"**, tritt an die Stelle der Antwortoptionen eine **Zahl mit
  Einheit** — beim Üben rät man sie dann auf einem Slider, je näher desto
  besser. Der Rate-Bereich entsteht automatisch aus der Zahl (0 bis ~2×,
  glatt gerundet), lässt sich aber von Hand anpassen. Bei der Einheit
  **„Jahr" / „Jahre"** wird der Bereich stattdessen ein **enges Fenster von
  ±50 Jahren** um die Zahl — sonst spannte der Slider bei einer Jahreszahl
  unbrauchbar von 0 bis ~4000. (#264, #265)
- **Der Gesprächswert arbeitet jetzt überall mit:** Die Beschluss-Suche kann
  nach **„Spannendste zuerst"** sortieren (kuriose, alltagsnahe Funde nach
  oben), die Übersicht zeigt Konten ohne aktuelle Themen-Treffer den
  **spannendsten Beschluss der Woche** samt Begründung, Themen-Mails führen
  mit dem folgenreichsten neuen Beschluss statt einer nackten Zählung, und
  „Ähnliche Beschlüsse" wie das Ratspolitik-Quiz bevorzugen bei Gleichstand
  die interessanteren Kandidaten. (#255)
- **„Wichtig" versteht jetzt Tragweite:** Neben der bisherigen Rechen-Logik
  (Geldbetrag, Umstrittenheit …) bewertet eine KI jeden Beschluss nach
  fester Rubrik — wie viele Menschen betroffen sind, wie bindend und
  wegweisend er ist. Beides fließt zu gleichen Teilen in den Wichtig-Wert;
  auf der Beschluss-Seite erklärt eine neue Zeile **„Warum wichtig: …"**
  den Messbalken in einem Satz. Kuriosität zählt hier ausdrücklich nicht —
  dafür gibt es das Fundstück. (#254)
- **Persönliche Ansprache:** Bei der Registrierung fragt Ratslotse jetzt nach
  einem **Anzeigenamen** — die Übersicht begrüßt dich damit („Moin, Tim!")
  und Benachrichtigungs-E-Mails sprechen dich persönlich an. Bestehende und
  Apple-Konten tragen den Namen jederzeit auf der Konto-Seite nach (oder
  lassen es — dann bleibt es beim neutralen „Moin!"). (#251)
- **Lotsen-Abzeichen:** Acht kleine Abzeichen belohnen das **Erkunden** —
  erste KI-Frage, erstes Thema, 5-Tage-Quiz-Serie, drei Orte auf der
  Stadtkarte, Analyse, Tagesordnung aufklappen, Push aktivieren und die
  Lotti-Tour. Verleihung mit **Konfetti und Toast**, die Sammlung wohnt auf
  der Konto-Seite („n von 8", mit Fortschritt und „Als Nächstes"-Tipp).
  Bewusst ohne Ranglisten oder Verlust-Serien: Einmal verdient bleibt
  verdient, nichts bestraft Abwesenheit. (#249)
- **Fundstück des Tages:** Die Übersicht zeigt jetzt jeden Tag **einen
  kuratierten Fund aus dem Ratsarchiv** — bevorzugt Jahrestage („Heute vor
  6 Jahren …") mit einem erzählenswerten Satz, Ergebnis und Absprung zum
  Beschluss, teilbar per Knopf. Dahinter steckt eine neue KI-Pipeline: Ein
  **Interessantheits-Score** bewertet den ganzen Beschluss-Bestand nach
  Gesprächswert (Kuriosität, Alltagsnähe — bewusst getrennt vom
  Wichtigkeits-Score), und ein wöchentlicher Lauf kuratiert daraus die
  Karten drei Wochen im Voraus. Ohne guten Fund bleibt der Tag einfach
  ohne Karte. (#248)
- **Live-Hinweis an Sitzungstagen:** Tagt gerade ein Gremium (Startzeit
  erreicht, bis 4 h danach), zeigt die Übersicht eine **rote Live-Karte**
  („tagt gerade · seit n Minuten", Ort, TOPs, deine Themen-Treffer) mit
  Absprung zur Tagesordnung — beim **Stadtrat zusätzlich der Link zum
  O1-Livestream** (oldenburg eins überträgt nur Ratssitzungen). Auch die
  Startseiten-Leiste kennt jetzt den Live-Zustand, und laufende Sitzungen
  tragen in den Listen einen **LIVE-Punkt**. Welcher Tagesordnungspunkt
  gerade dran ist, weiß das Ratsinfo nicht — Ergebnisse folgen wie gehabt
  mit dem Protokoll. (#247)
- **Feinschliff in Bewegung (M4, letztes Design-Paket):** Die orange
  Fragen-Taste **pulsiert** dezent, Seitenwechsel **gleiten sanft** herein,
  die Zahl der Woche **zählt hoch**, KI-Quellen erscheinen **nacheinander** —
  und in der App lädt **Ziehen-zum-Aktualisieren** mit einem kleinen Küken
  die Daten neu. Alles nur Transform/Deckkraft und komplett still, wenn das
  System „Bewegung reduzieren" wünscht. (#236)
- **Mit Apple anmelden — jetzt auch im Browser:** Auf ratslotse.de steht der
  Apple-Login nun auch auf Login und Registrierung im Web bereit (Popup,
  keine Passwort-Eingabe). Konten sind dieselben wie in der App — verknüpft
  über die bestätigte E-Mail-Adresse. (#234)
- **Offline & erster Start (M4):** Ohne Netz zeigt Ratslotse eine dezente
  **„Offline"-Pille** und in der App die zuletzt geladenen Inhalte (der
  Daten-Cache übersteht dort jetzt den Neustart, bis zu 24 h). Beim
  allerersten App-Start begrüßt dich außerdem ein **kurzes 3-Seiten-Intro**
  mit Lotti — einmal wischen, nie wieder. (#232)
- **App: neue Icons + Mitteilungs-Hinweis (M4):** Das App-Icon kommt jetzt in
  drei iOS-Varianten (hell, dunkel, getönt — je nachdem, wie der Homescreen
  eingestellt ist). Neu in der App außerdem ein freundlicher **Lotti-Hinweis
  zu Mitteilungen**: erst erklären, dann fragt iOS — wer „Später" wählt, wird
  eine Woche nicht wieder gefragt. Technisch vorbereitet: die App-Hülle kennt
  jetzt „Sign in with Apple". (#231)
- **Neue Anmelde-Seiten + Sign in with Apple (M3):** Login und Registrierung
  bekommen ein **zweispaltiges Marken-Layout** (Claim + Lotti-Familie links,
  Formular rechts, mobil unverändert kompakt) mit größeren Eingabefeldern.
  In der iOS-App kannst du dich künftig **mit Apple anmelden** — bestehende
  Konten werden über die gleiche E-Mail-Adresse verknüpft, neue sind sofort
  aktiv; Apple-Konten ohne Passwort löschen ihr Konto per frischer
  Apple-Bestätigung oder rüsten ein Passwort per E-Mail-Link nach. (#230)
- **„Lotti erklärt's einfach" (M3):** Beschluss-Seiten bekommen unter dem
  amtlichen Beschlusstext eine **2–3-Satz-Erklärung in einfacher Sprache** —
  ohne Verwaltungsdeutsch, mit klarem KI-Hinweis. Erzeugt automatisch für
  echte Beschlüsse mit substanziellem Beschlusstext; der Bestand seit 2018
  füllt sich wochenweise auf (neueste zuerst). Prompt im Admin-UI anpassbar. (#229)
- **„n TOPs zu deinen Themen" (M3):** Ratslotse zeigt dir jetzt direkt an,
  wenn eine kommende Sitzung Tagesordnungspunkte zu deinen Themen enthält —
  als oranger Hinweis auf der Sitzungs-Karte und im Heute-Briefing; im
  Aufklapp sind die passenden TOPs markiert („dein Thema · …"). Die
  Zuordnung merkt sich der Themen-Wächter jetzt dauerhaft und prüft je
  Konto nur noch geänderte Tagesordnungen. (#228)
- **„Neu"-Zähler für deine Themen (M3):** Ratslotse merkt sich jetzt, welche
  Beschluss-Treffer du schon gesehen hast. Ungesehene zählen als **oranger
  Zähler an „Meine Themen"** in der Seitenleiste (mobil als Punkt am
  Themen-Tab) und als **„n neu"-Abzeichen** auf der Themen-Karte. Öffnest du
  die Beschlussliste eines Themas, gilt alles als gesehen. (#226)
- **Sitzungspause-Hinweis auf der Übersicht:** Der Rat und seine Ausschüsse
  pausieren in den Schulferien (so hält es die Stadt grundsätzlich — und
  unsere Sitzungshistorie seit 2018 bestätigt es). Während einer Pause zeigt
  die Übersicht jetzt ein Banner mit dem Grund („Sommerpause · bis
  12. August"), wann es voraussichtlich weitergeht bzw. dem nächsten schon
  veröffentlichten Termin — damit sich niemand wundert, warum keine neuen
  Sitzungen erscheinen. 2026 erklärt es zusätzlich die Besonderheit
  **Kommunalwahl** (Wahltag 13. September, Ende der Wahlperiode 31. Oktober,
  Konstituierung des neuen Rats im November). Ferientermine: amtliche
  Niedersachsen-Daten bis Sommer 2027. (#215)
- **Haushalts-Quiz mit Diagrammen:** Neues Quiz-Thema **„Stadt-Haushalt"** mit
  zwölf Fragen direkt aus den **beschlossenen Haushaltsplänen** der Stadt
  (2020–2026, offizielle PDFs als Quelle verlinkt): Gesamtausgaben, Defizit,
  die großen Ausgabenblöcke, Erträge, Anteils- und Ranking-Fragen sowie
  **Zeitreihen** („Um wie viel sind die Ausgaben seit 2020 gewachsen?"). Die
  Auflösung zeigt je nach Frage ein animiertes **Balkendiagramm**, einen
  **Donut** (Anteil an den Gesamtausgaben) oder eine **Trendlinie** über die
  Haushaltsjahre — und erklärt die Zusammensetzung inklusive gesetzlich
  gebundener **Pflichtaufgaben** vs. frei gestaltbarer **freiwilliger
  Leistungen**. Dazu acht neue Glossar-Begriffe (Ergebnishaushalt,
  Teilhaushalt, Gewerbesteuer, Schlüsselzuweisung …). Komplett ohne KI
  erzeugt — jede Zahl 1:1 aus dem Plan. (#211)
- **Lotti spielt mit:** Im Quiz reagiert die Lotsenmöwe jetzt auf jede Antwort —
  sie jubelt bei richtig, winkt bei „nah dran" und schaut ratlos bei daneben,
  immer mit einem kurzen aufmunternden Spruch. Auch auf dem Ergebnis-Bildschirm
  (Fragen- und Karten-Quiz) feiert sie mit bzw. macht Mut für die nächste
  Runde. (#209)
- **Wichtige Beschlüsse erkennen:** Jeder Beschluss bekommt einen
  **Wichtigkeits-Score** (0–100) — geschätzt aus Geldbetrag, Umstrittenheit
  (Gegenstimmen / knappe Abstimmung), Verbindlichkeit & Gremien-Ebene (Satzung
  im Rat vs. Routine im Fachausschuss) und Länge des Beratungswegs. Bedeutende
  Beschlüsse tragen in den Listen ein **„Wichtig"**-Zeichen, lassen sich per
  **„Wichtigste zuerst"** sortieren, und die Beschluss-Seite schlüsselt
  transparent auf, welche Signale den Score treiben. Auch das Quiz zieht so
  bevorzugt wichtige statt beliebiger Beschlüsse heran. (#204)
- **Oldenburg-Quiz:** Ein neues Quiz zum spielerischen Kennenlernen der Stadt.
  Wähle einen **Wahlbereich**, **Stadtteil** oder ein großes stadtweites
  **Thema** und beantworte Multiple-Choice-Fragen aus fünf Kategorien
  (Geschichte, Orte & Wahrzeichen, Menschen, Ratspolitik, Schätzfragen). Die
  Fragen sind aus **Wikipedia**, der **Stadt-Website** und den **Ratsdaten**
  erzeugt und je mit Quelle belegt — nach jeder Antwort siehst du Lösung,
  Erklärung und Quellenlink und kannst die Frage bewerten (👍/👎), damit
  schwache Fragen später ersetzt werden. Deine **Punkte und Trefferquoten
  werden je Gebiet gespeichert**: Das Fortschritts-Dashboard zeigt deine
  schwächsten Gebiete zuerst und bietet gezieltes „Üben". (#198)
- **Quiz-Lernmodus & Motivation:** Dazu kommen eine **tägliche Challenge**
  (5 Fragen, jeden Tag neu und für alle gleich), ein **„Meine Fehler"-Stapel**
  zum gezielten Wiederholen zuletzt falsch beantworteter Fragen (spaced
  repetition, wie beim Führerschein-Lernen), **Serien** (🔥 Tage in Folge) und
  **Abzeichen** (Punkte-Meilensteine, Gebiets-„Kenner"). (#198)
- **Schätzfragen mit Slider:** Schätzfragen (Einwohner, Fläche, Beträge …) lassen
  sich per Schieberegler beantworten — je näher an der richtigen Zahl, desto mehr
  Punkte (statt vier fester Bereiche). (#198)
- **Karten-Quiz:** „Wo liegt Stadtteil X?" — die Oldenburg-Karte mit allen
  Stadtteilen; man tippt den gesuchten direkt auf der Karte an, die Auflösung
  färbt den richtigen Stadtteil grün. Rein geografisch erzeugt (ohne KI). (#199)
- **Grund beim Melden einer Quizfrage:** Wer eine Frage mit 👎 bewertet, kann
  jetzt optional (keine Pflicht) angeben, was daran schlecht ist — Admins sehen
  die Begründung in der Bewertungs-Liste. (#200)
- **Reichere Quiz-Antworten („Mehr dazu"):** Die Auflösung einer Frage kann jetzt
  optional eine **ausführlichere Erklärung**, eine kleine **Karte** (bei Orten,
  Straßen, Gebäuden) und ein **Foto** zeigen. Fotos kommen aus **Wikimedia
  Commons** — ausschließlich frei lizenziert und stets **mit Bildnachweis**
  (Autor, Lizenz, Quelle). (#201)
- **Fachbegriffe zum Nachschlagen:** In der Quiz-Auflösung sind Begriffe wie
  „Vergnügungsstätte", „Bebauungsplan" oder „Satzung" dezent unterstrichen — beim
  Überfahren (bzw. Antippen) erscheint eine kurze, allgemeinverständliche
  Erklärung. (#202)
- **Straßen als Linie auf der Antwort-Karte:** Geht es um eine konkrete Straße,
  zeichnet die kleine Karte in der Auflösung deren echten Verlauf ein (statt nur
  eines Punkts). Bewusst zurückhaltend: Bei mehrdeutigen oder weit verstreuten
  Straßennamen bleibt die Karte lieber leer, statt eine falsche Stelle zu zeigen.
  (#202)
- **Tipp bei kniffligen Fragen:** Schwerere Quizfragen können jetzt einen
  optionalen **Tipp** anbieten — ein Klick auf „Tipp anzeigen" gibt vor dem
  Auflösen einen Denkanstoß, ohne die Lösung zu verraten. (#203)
- **Ganze Gebiete auf der Antwort-Karte:** Geht eine Frage um einen Stadtteil
  (oder eine Person/Sache von dort), zeichnet die Auflösungs-Karte jetzt das
  **ganze Gebiet** als Fläche ein — zusätzlich zu den bisherigen Punkt- und
  Straßen-Markierungen (die Stadtteil-Grenzen kennen wir selbst, also immer
  verlässlich). (#203)
- **„Beschlüsse dazu" bei Quizfragen:** Geht es um ein Ratsthema (z. B. ein
  Bauprojekt), führt die Auflösung mit einem Klick zu den passenden **echten
  Ratsbeschlüssen** in der Beschluss-Suche — so kann man tiefer einsteigen,
  statt bei der Quizfrage stehenzubleiben. (#208)
- **Zoombare Antwort-Karten:** Die kleinen Karten in der Quiz-Auflösung lassen
  sich jetzt zoomen und verschieben (Zoom-Buttons, Doppelklick, Pinch); nur das
  Mausrad-Zoom bleibt aus, damit die Seite normal weiterscrollt. (#207)
- **Wahlbereiche auf der Themen-Karte:** Der Stadtteil-Filter kennt jetzt die
  6 Kommunalwahl-Wahlbereiche der Stadt Oldenburg — ein Klick wählt alle
  Stadtteile eines Wahlbereichs (Zuordnung geometrisch aus den offiziellen
  Wahlbereich-Polygonen, openGEOdata Stadt Oldenburg). (#194)
- **Kontrastreichere Stadtkarte:** Hell nutzt jetzt CARTO Voyager (Straßen,
  Grünflächen und Wasser klar erkennbar statt fast konturlos), Dunkel bekommt
  einen dezenten Helligkeits-/Sättigungs-Boost — Orientierung ohne Bruch im
  Design. (#194)
- **Themen-Karte rundum verbessert:** Nahe herangezoomt (oder gefiltert)
  stehen die Themen-Namen direkt an den Punkten — kein Antippen mehr nötig,
  um zu sehen, worum es geht. Die Karte merkt sich ihren Ausschnitt (Zurück
  vom Thema landet nicht mehr in der Gesamtansicht), lässt sich per Knopf im
  **Vollbild** anzeigen und nach **Stadtteilen filtern** — ausgewählte
  Stadtteile werden mit Grenze eingezeichnet und die Karte zoomt darauf
  (Grenzen: © OpenStreetMap-Mitwirkende). (#193)
- **Weg der Vorlage, offiziell:** Beschluss-Seiten zeigen die Beratungsfolge
  aus dem Ratsinfo — jede Station mit Gremium, Datum und Ergebnis, inklusive
  erst **geplanter künftiger** Beratungen. (#192)
- **Personen-Profile mit Geschichte:** Fraktions-Verlauf (wer wann in welcher
  Fraktion war, abgeleitet aus den Sitzungs-Anwesenheiten — das Ratsinfo
  selbst überschreibt Fraktionen rückwirkend) und die offiziellen
  Gremien-Mitgliedschaften mit Zeiträumen **zurück bis 2001**. Kontaktdaten
  der Ratsinfo-Personenseiten werden bewusst nicht übernommen. (#192)

### Geändert
- **„Wichtigste zuerst" zeigt jetzt Wichtiges aus der letzten Zeit.** Bisher
  sortierte die Beschluss-Suche stur nach dem Wichtigkeits-Wert — und der ist
  bei Haushaltsbeschlüssen strukturell am höchsten. Ergebnis: eine Liste voller
  Haushaltssatzungen, teils Jahre alt, während aktuelle Entscheidungen
  untergingen. Der Wert wird nun mit der **Aktualität** gewichtet (nach zwei
  Jahren zählt er halb, nach vier ein Drittel). Ein aktueller Haushalt steht
  weiterhin oben, ein fünf Jahre alter rutscht hinter das aktuelle Geschehen —
  ohne ganz zu verschwinden. Der Eintrag trägt jetzt ein Flammen-Zeichen und
  die Unterzeile „Wichtigkeit & Aktualität".
- **Sortierung „Spannendste zuerst" entfernt.** Nach dem Gesprächswert zu
  *suchen* ergab wenig Sinn — er lohnt sich zum Stöbern, nicht zum Finden. Er
  wirkt weiterhin im Hintergrund: beim „Fundstück des Tages", der Karte „Diese
  Woche im Rat" und als Stichentscheid bei gleichwertigen Treffern. (#295)
- **Technik-Doku auf den aktuellen Stand gebracht.** Die Doku unter
  [ratslotse.de/docs](https://ratslotse.de/docs) hing rund 80 Pull Requests
  hinterher. Neu dazugekommen sind drei Seiten: **Bewertungs-Scores** (wie
  Wichtigkeit, Tragweite und Gesprächswert entstehen und zusammenfließen —
  inklusive Rechenbeispiel), **App & Konten** (native iOS-App, Anmeldung samt
  Sign in with Apple, was am Konto hängt) und **Betrieb** (Deploy-Wege,
  Dev-Umgebung, Cronjobs, Backups, LLM-Kosten, komplette Env-Referenz).
  Korrigiert wurden außerdem sachlich falsche Stellen: Der Wichtigkeits-Score
  war noch als reine Heuristik „kein ML" beschrieben, obwohl die KI-Tragweite
  seit Längerem zur Hälfte einfließt; die Tabellenlisten beider Datenbanken
  waren unvollständig; eine dokumentierte Tabelle gab es gar nicht. (#293)
- **Die Zeitachse baut sich auf.** Öffnet man einen Beschluss, zeichnet sich
  „Anträge & Teilabstimmungen" in unter einer Sekunde auf: die Linie wächst nach
  unten, die Stationen erscheinen nacheinander und rasten mit einem kleinen
  Punkt ein — so liest man die **Reihenfolge** mit, erst die Anträge, dann der
  endgültige Beschluss. Wer im System weniger Bewegung eingestellt hat
  (`prefers-reduced-motion`), sieht die Zeitachse sofort fertig. (#294)
- **Änderungsanträge als Kontext statt loser Treffer (Design 23a).** Änderungs-
  anträge (Teilabstimmungen) tauchen in der Beschluss-Suche **nicht mehr als
  eigene Treffer** auf, sondern hängen als **Unterzeile am Ursprungsbeschluss**
  („1 Änderungsantrag · CDU · angenommen") — man sieht auf einen Blick, dass es
  einen gab, ohne dass die Liste zerfasert. Auf der **Beschluss-Seite** wird aus
  der flachen Antragsliste eine **Zeitachse**: der Änderungsantrag (mit „Was
  beantragt wurde") führt zum **endgültigen Beschluss**. Wer gezielt recherchiert,
  blendet die Anträge über den Filter **„Änderungsanträge einzeln zeigen"**
  wieder als eigene Treffer ein. (#285)
- **Beschluss-Karten in klaren Zonen (Design 22a).** Jede Karte in der Suche
  folgt jetzt einer festen Reihenfolge: **Statuszeile** (Ergebnis-Punkt +
  „Wichtig" zusammen, Pfeil rechts), darunter ruhig **Gremium · Datum · TOP**,
  dann **Titel + zweizeiliger Auszug**, und unten eine **Fußzeile** mit
  Abstimmung und Antragsteller links sowie dem **Betrag als betontem rechten
  Anker** („57,3 Mio. € · im Beschluss"). Fehlt ein Teil (kein Betrag, kein
  Auszug), fällt seine Zone einfach weg — nichts rutscht mehr durcheinander.
  Besonders auf dem Handy sind die Karten dadurch deutlich ruhiger. (#280)
- **Lange Ausschussnamen werden lesbar — überall.** Sperrige amtliche Namen wie
  „Ausschuss für Wirtschaftsförderung, Digitalisierung und internationale
  Zusammenarbeit" wurden in Karten, Chips und Dropdowns hart abgeschnitten
  („Ausschuss für Wirtschaf…") — nicht mehr zu unterscheiden. Jetzt zeigt eine
  zentrale **Kurzname-Funktion** eine knappe, sinntragende Form („Wirtschaft &
  Digitales"), und auf Karten/Zeilen steht der **volle Name als kleine Unterzeile**
  darunter (max. 2 Zeilen) — nichts geht verloren. In engen Slots (Chips,
  Dropdown-Trigger, Filter) reicht der Kurzname, der volle Name bleibt im Tooltip
  und für Screenreader. Greift auf Sitzungen, Übersicht, Personen-Profil,
  Beschluss-Karten/-Detail und allen Ausschuss-Filtern. (#272)
- **Ziele & Finanzen lesbarer.** In der Analyse zeigt jedes **Stadtziel** jetzt
  einen **Richtungs-Balken** (bremst ← rot | Konsens | grün → voran) statt
  dreier gleich langer Segmente, dazu ein **Netto-Chip** („überwiegend
  vorangebracht", „leicht …" oder „umkämpft", wenn beide Seiten stark sind) und
  ein Icon je Ziel — die Richtung ist auf einen Blick da. Die **Finanzen**-Seite
  bekommt über der Themenfeld-Liste eine **Summen-Headline** („≈ X Mio. € über
  N Beschlüsse"), die der Balkenliste einen Anker gibt. Gleiche Daten, nur
  klarer aufbereitet. (#270)
- **Themenfeld-Rückblicke: ganze Karte klickbar.** In der Analyse unter
  „Trends" klappt jetzt ein **Klick oder Tipp irgendwo auf die Karte** die
  Kernpunkte auf und wieder zu (nicht mehr nur der kleine Knopf) — auf dem
  Handy wie am Rechner. Der „Beschlüsse"-Link bleibt eigenständig, markierter
  Text wird nicht weggeklickt, und ein Chevron zeigt den Zustand. Nebenbei
  behoben: die Karten liefen auf schmalen Handys minimal über den Rand. (#269)
- **Personen-Profil zeigt die Ämter als Zeitleiste:** Die Seite eines
  Ratsmitglieds beginnt jetzt mit einem **Kopf aus Kürzel-Avatar (in
  Fraktionsfarbe), Name und Kennzahlen** (besuchte Sitzungen, aktiv seit,
  Vorsitze). Die **aktuellen Ämter** stehen als kleine **Gantt-Leiste** —
  Balkenlänge = Amtsdauer, **orange = (stellv.) Vorsitz** (mit Hammer-Symbol,
  nach oben sortiert), blau = Mitglied, mit Jahresachse bis „heute". **Frühere
  Ämter** klappen darunter zusammengefasst auf. Gleiche Daten wie zuvor
  (Anwesenheit + offizielle Gremien-Zeiträume), nur endlich auf einen Blick
  lesbar. (#268)
- **Analyse aufgeräumt:** Der vierzeilige Methodik-Kasten über den Analysen
  (Parteien, Personen, Ziele) ist jetzt **ein Satz mit der wichtigsten Zahl**;
  die Erläuterung, wie gezählt wird, wandert in ein **„Wie wird gezählt?"-
  Info-Popover**. Und die **Parteien-Heatmap** hat auf dem Handy endlich eine
  eigene Fassung: statt einer 12-Spalten-Tabelle im Seitwärts-Scroll zeigt
  jede Fraktion ihre **stärksten Themenfelder als Balken** („alle Felder"
  klappt den Rest auf). (#267)
- **Analyse → Trends: „Rückblick je Themenfeld" wird scanbar.** Die Karten
  zeigen jetzt standardmäßig nur die **Kernaussage + Zahl**; die vier
  Stichpunkte klappen per **„4 Kernpunkte anzeigen"** auf (Zustand je Feld
  gemerkt). Der Kern jedes Stichpunkts ist **gefettet**, eine **Filter-Chip-
  Zeile** setzt den Fokus auf ein Themenfeld, und **„Alle ausklappen"** öffnet
  alles auf einmal. Gleiche Infos, weniger Textwand — auf einen Blick
  erfassbar. (#266)
- **Quiz-Startseite mit klarer Hierarchie:** Statt fünf gleich aussehender
  Zeilen wandern die Kernzahlen (Punkte, Trefferquote, Serie) jetzt in den
  Seitenkopf, „Weiterspielen" wird zur **Hero-Karte** mit Lotti und der
  gemerkten Auswahl als Chips, und die vier Modi (Neues Spiel, Tägliche
  Challenge, Karten-Quiz, Eigene Fragen) sind **farbcodierte, ganz klickbare
  Kacheln** — die Challenge trägt ein „Heute offen"- bzw. „Erledigt"-Abzeichen.
  Ohne gemerkte Runde übernimmt „Neues Spiel" die Hero-Karte. Mobil: Hero
  volle Breite, Kacheln 2 × 2. (#263)
- **Quiz-Setup auf einer Seite statt vier Schritten:** Beim neuen Spiel
  wählen **Wahlbereich-Kacheln** ihre Stadtteile als Schnellwahl vor (und
  räumen beim Abwählen nur die eigenen wieder weg), die Stadtteil-Chips
  zeigen ihre Fragenzahl samt Suche, und die **Themen kennen jetzt ihren
  Ort**: gruppiert in „in deiner Auswahl", „stadtweit" und einklappbar
  „außerhalb" — gewählte Themen bleiben mit Orts-Hinweis sichtbar. Eine
  Live-Zeile fasst unten zusammen („13 Fragen in 3 Stadtteilen + 1 Thema"),
  bevor es losgeht. „Weiterspielen" und gemerkte Auswahlen funktionieren
  unverändert. (#261)
- **Neue Beschlüsse bekommen ihre Scores jetzt tagesaktuell:** Der tägliche
  Protokoll-Lauf bewertet frisch veröffentlichte Beschlüsse direkt mit
  Gesprächswert und Tragweite und rechnet den Wichtig-Wert sofort neu —
  „Warum wichtig", die Tragweite in der KI-Frage und „Spannendste zuerst"
  greifen damit ab dem ersten Tag statt erst nach dem Wochenlauf. (#259)
- Die **KI-Frage kennt jetzt die Tragweite**: Bei jedem als besonders
  folgenreich oder als Formalie eingestuften Beschluss bekommt die KI einen
  entsprechenden Hinweis (samt „Warum wichtig"-Begründung) mitgeliefert —
  Antworten führen dadurch mit den Beschlüssen, die wirklich etwas bewegen,
  und zählen Berufungen oder Kenntnisnahmen nicht mehr gleichwertig auf.
  Die Quellen-Auswahl selbst bleibt rein relevanz-basiert. (#258)
- Die Themen-Vorschläge zeigen **keine Fast-Duplikate** mehr: „Stadion
  Maastrichter Straße", „Stadionneubau Maastrichter Straße" und
  „Maastrichter Straße" gelten als ein Interesse — nur der aktivste
  Kandidat erscheint, und wer so ein Thema schon angelegt hat, bekommt
  auch keine Variante davon vorgeschlagen. (#253)
- **Themen-Vorschläge, die wirklich interessieren:** Die „Gerade aktuell im
  Rat"-Chips auf „Meine Themen" schlagen jetzt **konkrete Orte und Projekte**
  mit jüngster Ratsaktivität vor (Veloroute, Fliegerhorst, deine Straße …)
  statt Verwaltungsvokabeln wie „Bericht" oder „Annahme". Die KI-Beschreibung
  des Ortes wird dabei zur Themen-Beschreibung — dadurch trifft auch die
  Benachrichtigung genauer. (#252)
- **Breiteres Layout wie im Design:** Der Inhaltsbereich wächst von 1024 auf
  1280 Pixel — Karten und Listen füllen den Bildschirm statt schmal in viel
  Leerraum zu stehen; Text-Detailseiten behalten ihre Lesebreite. Außerdem
  klebt die **Impressum-Fußzeile mobil nicht mehr auf jeder Seite**: Auf
  Handy und in der App wohnen die Links jetzt unten auf der Konto-Seite
  (am Desktop bleibt die dezente Fußzeile). (#250)
- Der **Sitzungspause-Hinweis auf der Übersicht ist jetzt kompakt**: eine
  Zeile mit schlafender Lotti und „wieder ab"-Datum statt einer halben
  Bildschirmseite — die ausführliche Erklärung (Ferien, Kommunalwahl)
  klappt per Tipp auf „Mehr" aus. (#246)
- **Datenschutzerklärung aktualisiert:** Sie beschreibt jetzt die
  **Anmeldung mit Apple** (welche Daten Apple übermittelt, inklusive
  „E-Mail-Adresse verbergen") und die **lokale Speicherung** auf dem Gerät
  (Design-Einstellung, App-Anmeldung, 24-h-Offline-Zwischenspeicher).
  Weiterhin ohne Tracking und ohne Cookie-Banner. (#244)
- **Neuer Hell/Dunkel-Schalter mit Lotti:** Statt des Dreistufen-Icons gibt es
  jetzt einen kleinen **Himmel-Schalter** — tagsüber Sonne, nachts Mond und
  Sterne, und Lotti selbst ist der Schaltknauf (nachts schläft sie, mit „z").
  Er sitzt im Fuß der Desktop-Seitenleiste; die **⌘K-Palette** wechselt
  passend dazu nur noch Hell ↔ Dunkel. **Auf dem Handy** (Web wie App)
  wählst du das Design auf der Konto-Seite über die neue Karte
  **„Erscheinungsbild"** mit Vorschau-Kacheln — in der App zusätzlich mit
  „Automatisch" (folgt der iOS-Einstellung). Wer bisher „System" nutzte,
  bleibt dabei — bis zur ersten eigenen Wahl. (#243, #245)
- **KI-Frage bleibt beim Hin- und Herschalten erhalten:** Wer zwischen
  „Suchen" und „KI-Frage" wechselt, findet Antwort, Quellen und Eingabe
  unverändert wieder — auch die Scroll-Position je Modus bleibt. Nach einer
  Antwort schlagen jetzt **Anschlussfragen-Chips** die nächste Frage vor
  (plus „Neue Frage stellen"), und auf dem Handy lugt eine **Mini-Lotti**
  über die Antwort-Sprechblase, damit klar ist, wer da spricht. (#242)
- **Feinschliff aus dem UX-Review (Runde 2):** Suchfelder haben jetzt eine
  **Löschen-Taste** (✕) und die iPhone-Tastatur zeigt „Suchen" statt „Return";
  ein Seitenwechsel in der Beschlussliste springt **zurück zum Listenanfang**;
  ist Sitzungspause, erklärt der leere „Kommend"-Tab das jetzt selbst (mit
  schlafender Lotti und Absprung zu vergangenen Sitzungen); auf schmalen
  Handys wandert der **Geldbetrag** einer Beschluss-Karte unter den Titel
  statt ihn zusammenzuquetschen; die **Feature-Karten der Startseite sind
  klickbar**; das Logo auf Login/Registrieren führt **zurück zur Startseite**;
  und in der iPhone-App ist versehentliches **Rein-Zoomen jetzt ganz aus**
  (der iOS-Bedienungshilfen-Zoom funktioniert weiterhin). (#241)
- **Sitzungen als Kalender-Karten (Design 6a, M2):** Jede Sitzung trägt links
  eine **Datums-Kachel** (Monat + Tag), der Gremiumsname steht in der
  Markenschrift, und aufgeklappte Tagesordnungen bekommen eine saubere
  Nummern-Spalte; Ergebnisse erscheinen als Punkt + Wort. Oben weist der
  kompakte **Sitzungspause-Hinweis** mit schlafender Lotti auf Ferien hin —
  inklusive „wieder ab"-Datum, sobald ein Termin bekannt ist. (#225)
- **Konto-Seite mit Schaltern (Design 6a, M2):** Benachrichtigungen steuerst du
  jetzt über zwei **Schalter** — E-Mail und Push getrennt (mindestens einer
  bleibt an) — und kannst dir eine **Test-Benachrichtigung** schicken, um die
  Zustellung zu prüfen. Die Konto-löschen-Zone spannt rot markiert über die
  volle Breite. (#224)
- **Neue Startseite mit „Heute im Rat" (Design 2a, M2):** Unter dem Kopf der
  Landing läuft jetzt eine dezente **Live-Leiste**: Tagt heute ein Gremium,
  steht dort orange „HEUTE IM RAT" mit Uhrzeit und den ersten
  Tagesordnungspunkten; sonst der nächste Termin — und in den Ferien schlicht
  „Sitzungspause bis …". Der **Hero** zeigt rechts die **echte KI-Demo** (mit
  Lotti und „LIVE AUSPROBIEREN"-Badge) statt einer Illustration, links den
  großen Titel mit orangenem **„Kostenlos registrieren"** und den Kennzahlen
  als schlanker Belegzeile. Die Hafenszene mit der Lotsen-Familie wird zum
  ruhigen Band darunter. (#223)
- **Meine Themen aufgeräumt (Design 3a, M2):** Neues Thema legst du jetzt über
  den orangenen **„+ Neues Thema"**-Knopf im Kopf an (Dialog statt
  Dauerformular). Die Themen stehen als **Karten im Zweier-Raster** — mit
  Stift/Papierkorb-Symbolen, dem **jüngsten Treffer** als anklickbarer Zeile
  mit Orange-Punkt und „n Beschlüsse insgesamt · alle ansehen". Die
  **Ausschuss-Abos** schalten sich per **Schalter** (wie vom Handy gewohnt)
  statt über Abonnieren-Knöpfe. (#222)
- **Beschluss-Seite als Dokument (Design 3a, M2):** Oben eine kompakte
  **Statuszeile** (● Ergebnis · Gremium · Datum · TOP · Aktenzeichen ·
  „Wichtig"-Chip mit Punktzahl), der Titel groß in der Markenschrift, darunter
  zweispaltig: links der Vorgang (Beschlusstext, Anträge, Weg der Vorlage,
  Vorlagen-Auszug, Ähnliche), rechts eine **Meta-Spalte** mit Karten für
  Abstimmung, **Betrag** (groß in Orange), Antragsteller, **Dokumente** (alle
  Links gebündelt) und Anwesenheit. Fehlen Abstimmung oder Betrag, erklärt die
  Karte das Fehlen, statt zu verschwinden. Mobil bleibt alles einspaltig —
  erst der Text, dann die Meta-Daten. (#221)
- **KI-Frage-Zustände nach Design 6a/4a (M2):** Die Antwort kommt als
  Sprechblase neben Lotti, der Ladezustand wohnt in einem gestrichelten
  Container, und findet die KI **keine passenden Beschlüsse**, sagt sie das
  ehrlich — mit zwei direkten Auswegen: **„Als Thema anlegen"** (öffnet Meine
  Themen mit vorbefülltem Namen, damit du benachrichtigt wirst, sobald der Rat
  dazu entscheidet) und **„Frage umformulieren"**. (#220)
- **Suche mit Filter-Chips (Design 1a, M2):** Die Beschluss-Suche hat jetzt ein
  großes Suchfeld und darunter eine **Chip-Zeile** ([Beschlüsse ▾] · Themenfeld
  · Ausschuss · Ergebnis · Zeitraum, rechts die Sortierung) — aktive Filter
  füllen sich blau und lassen sich per ✕ direkt löschen; die Auswahl öffnet
  sich als leichtes Popover (mobil weiterhin als Bottom-Sheet). Der
  **„Suchen | KI-Frage"-Umschalter** sitzt jetzt oben im Seitenkopf. Findet
  die Suche nichts, bietet Lotti direkt **„KI-Frage stellen"** an — die Frage
  übernimmt den Suchtext. Alle Filter-Links (aus Analyse, Karten, Badges)
  funktionieren unverändert. (#219)
- **„Heute"-Briefing statt Übersicht (Design 2a, M2):** Die Startseite nach dem
  Login ist jetzt ein tägliches Briefing: Begrüßung mit Lotti und Datum,
  daneben die zentrale Aktion **„Frag den Rat"**, darunter drei Karten —
  **Nächste Sitzungen** (mit TOP-Zahl), **Neu zu deinen Themen** (die jüngsten
  Beschluss-Treffer deiner Themen) und die **Zahl der Woche** (größter
  beschlossener Betrag der letzten Tage, mit Link zum Beschluss). Die „Ersten
  Schritte" schrumpfen auf eine schlanke Leiste mit „Weitermachen"-Knopf. Das
  **Sitzungspause-Banner** bekommt die schönere Hülle: Wellen-Fläche,
  schlafende Lotti im Saison-Outfit und eine „Wieder ab …"-Kachel. (#218)
- **Design „Feinschliff 2a" — Fundament & Navigation (M1):** Erster Schritt des
  neuen Designs. Die **Seitenleiste** führt jetzt direkt zu *Heute, Suchen &
  Fragen, Sitzungen, Stadtkarte* (vorher „Themen"-Tab) *und Analyse*, darunter
  der Bereich *Persönlich*; aktive Einträge sind eine ruhige Fläche statt eines
  Balkens. Die **mobile Leiste** bekommt eine zentrale orangene
  **„Fragen"-Taste**, die direkt zur KI-Frage führt. **Ergebnisse in Listen**
  zeigen Punkt + Wort („● Angenommen") statt farbiger Kästen, **Beträge**
  stehen als fette Zahl rechts, und der **Beschlusstext** auf der Detailseite
  liegt auf einer ruhigen blauen Fläche mit Label. Seitentitel in der
  Markenschrift. (#217)
- **Karten-Quiz nutzt den Bildschirm:** Die „Wo liegt …?"-Karte wächst jetzt
  mit dem Fenster (bis ca. 900 × 720 Pixel auf großen Bildschirmen statt fix
  ~530 × 440) und zoomt das Stadtgebiet passgenauer ein. Bei Größenänderungen
  (Fenster, einklappende Mobil-Browserleiste) passt sich die Karte live an.
  (#214)
- **Quiz-Startseite aufgeräumt:** Statt einer einzigen überladenen Auswahlseite
  gibt es jetzt **„Weiterspielen"** (spielt die letzten Einstellungen weiter, mit
  einer kurzen Beschreibung, was das war) und **„Neues Spiel"** als
  **mehrstufigen Assistenten** (Wahlbereich → Themen → Stadtteile → Kategorien,
  Schritt für Schritt durchklicken). Die Statistik steht als **Kurzform oben**,
  die ausführliche Auswertung (Fortschritt je Gebiet, Serie, Abzeichen) auf einer
  **eigenen Seite** (`/quiz/stats`). (#205)
- **Relevantere & eindeutigere Quizfragen:** Die Fragen-Erzeugung meidet jetzt
  belangloses Verfahrens-Trivia (Workshop-Teilnehmerzahlen, Anzahl eingereichter
  Ideen, exakte Sitzungsdaten) und benennt das gemeinte Ding **konkret** (den
  Stadtteil/das Projekt ausschreiben statt „der neue Stadtteil"). Schätzfragen
  nur noch für sinnvolle Größen (Einwohner, Fläche, Bausummen …). Wirkt auf neu
  erzeugte Fragen. (#208)
- **Fairere, lehrreichere Quizfragen:** Die Fragen-Erzeugung zielt jetzt auf
  einen „Aha-Moment" beim Auflösen — mehrheitlich leichte bis mittlere Fragen
  (keine obskuren Randfiguren oder beliebigen Jahreszahlen), und die Erklärung
  vermittelt das *Warum*, statt nur die Antwort zu wiederholen. Wirkt auf neu
  erzeugte Fragen. (#203)
- **Grenzstadtteile in mehreren Wahlbereichen:** Stadtteile, die über eine
  Wahlbereichs-Grenze reichen, werden jetzt in **allen** zugehörigen
  Wahlbereichen gelistet statt nur im überwiegenden — z. B. Bürgerfelde (1 + 3),
  Osternburg (5 + 2), Haarentor (3 + 6). Ermittelt aus der Flächen-Überlappung
  der Stadtteil-Polygone mit den offiziellen Wahlbereich-Grenzen (≥ 10 %). Wirkt
  auf den Karten-Filter und die Quiz-Gebietsauswahl. (#199)
- **Bessere Karte im Dunkelmodus:** Die dunkle Stadtkarte ist jetzt ein
  gut lesbarer grauer Slate-Ton (invertierte Voyager-Basemap) statt fast
  schwarz — Straßen, Waldgebiete und Wasser sind zur Orientierung erkennbar.
  (#196)
- **Karten-Labels ohne Überlappung:** Die Themen-Namen auf der Karte werden
  jetzt mit Kollisionsvermeidung platziert — die wichtigsten Themen (nach
  Beschlusszahl) zuerst, was nicht frei steht, erscheint beim Heranzoomen.
  Labels sind klickbar wie ihre Punkte und heben sich beim Überfahren mit
  der Maus in den Vordergrund. (#195)
- **Ruhigere Sidebar:** Die Suche ist kein gedrungenes Eingabefeld mehr,
  sondern fügt sich als schlanke Zeile in die Navigation ein (⌘K wie gehabt).
  (#191)
- **Onboarding-Kurs merkt sich den Fortschritt am Konto:** „Erste Schritte mit
  Lotti" zählt jetzt geräteübergreifend — Schritte gelten als erledigt, sobald
  die jeweilige Seite besucht wird (nicht nur per Klick auf die Kurs-Kachel),
  und nach dem Abschluss verschwindet der Kurs vom Dashboard. Bisheriger
  Fortschritt wird automatisch übernommen. (#190)
- **Technik-Doku aufgeräumt:** interaktive Diagramme (Mermaid) für Architektur
  und KI-Pipeline, Betriebs-Interna (Zeitpläne, interne Funktionsnamen,
  To-do-Listen) entfernt, veraltete Formulierungen aus der Zeit vor dem
  Open-Source-Release bereinigt. Die Doku verlinkt jetzt zurück zur App und
  aufs GitHub-Repo. (#189)

### Behoben
- **Konto löschen entfernt jetzt wirklich alle Daten.** Beim Löschen eines
  Kontos blieben Daten zurück, die daran hingen: **Gerätetokens** für Push, alle
  Quiz-Daten (Antworten, Bewertungen, Tagesserie, eigene Fragen), die Merker für
  gesehene Themen-Treffer, die Treffer selbst sowie das Aktivitätsprotokoll.
  Gelöscht wurden nur sechs von sechzehn betroffenen Tabellen — der Rest war
  über die Zeit dazugekommen, ohne beim Löschen berücksichtigt zu werden. Jetzt
  wird alles abgeräumt. Damit das so bleibt, prüft ein Test die Liste gegen die
  Datenbank: Kommt künftig eine neue nutzerbezogene Tabelle dazu, schlägt er
  fehl, bis sie eingetragen ist. (#296)
- **Die Wichtigkeits-Karte rechnet jetzt vor, wie sie auf ihren Wert kommt.**
  Aufgeklappt erklärten die vier Balken (Geldbetrag, Umstrittenheit,
  Verbindlichkeit, Beratungsaufwand) nur die **halbe** Miete: Seit die KI die
  **Tragweite** bewertet, ist der angezeigte Wert das Mittel aus beidem — die
  Tragweite selbst war aber unsichtbar und im Erklärtext nicht mal erwähnt. Bei
  einem Beschluss mit „60/100" und zwei Balken auf „keine Daten" ging die
  Rechnung für Leser:innen schlicht nicht auf. Jetzt trägt jeder Balken seinen
  **Punkte-Beitrag** (z. B. „+52"), darunter stehen **„Aus den Ratsdaten"**,
  **„Tragweite (KI-Einschätzung)"** und das **Mittel aus beiden** — die Spalte
  addiert sich sichtbar zum Endwert. Ergänzt um den Hinweis, dass fehlende
  Angaben **nicht als null** zählen, sondern aus der Gewichtung fallen (deshalb
  kann ein Beschluss mit zwei fehlenden Signalen trotzdem hoch liegen).
  (#290)
- **Teilabstimmungen zeigen wieder, was beantragt wurde.** Auf der Beschluss-Seite
  stand unter „Anträge & Teilabstimmungen" nur, *wer* einen Änderungsantrag
  gestellt hat — nicht, *was* er ändern sollte. Der Antragstext wurde aus dem
  falschen Feld gelesen und blieb deshalb immer leer. Jetzt erscheint bei rund
  drei Vierteln der Teilabstimmungen der tatsächliche Inhalt (z. B. „Streichung
  des Punktes 8 ‚Einrichtung einer Umweltzone'"); nennt das Protokoll nur die
  antragstellende Fraktion, bleibt es wie bisher bei Antragsart und Ergebnis.
  Außerdem benennt die Zeile die **Antragsart** korrekt — Vertagungs-,
  Verweisungs- oder Geschäftsordnungsantrag hießen zuvor pauschal
  „Änderungsantrag". (#288)
- **App: Absturz beim Öffnen von „Meine Themen" behoben.** In der iOS-App
  führte das Antippen des Themen-Tabs zu „Etwas ist schiefgelaufen". Ursache
  war ein doppelt vergebener Daten-Schlüssel im App-Cache, unter dem die
  Ausschuss-Abos mal als Liste, mal als Objekt lagen. Beide Stellen nutzen
  jetzt dieselbe Form; ältere Zwischenspeicher werden beim Update verworfen. (#277)
- **App: „Frag den Rat" funktioniert wieder.** In der iOS-App scheiterte die
  KI-Frage mit „Load failed". Dem Streaming-Endpoint fehlten die Freigabe-
  Header für die App und die App-Anmeldung wurde nicht durchgereicht; beides
  ist ergänzt. Rein serverseitig — nach dem Update funktioniert es in der
  bestehenden App ohne Neuinstallation. (#281)
- **App: Impressum, Datenschutz und Changelog wieder verlassbar + Kopf unter
  der Dynamic Island.** Auf diesen Seiten fehlte in der App ein Zurück-Weg,
  und der Seitenkopf lag unter der Kamera-Insel des iPhones. Jetzt gibt es
  oben einen **Zurück-Knopf**, und der Kopf respektiert den sicheren
  Bereich. (#281)
- **Datumsauswahl: schneller ins Jahr, ruhigere Darstellung.** Im Datumsfilter
  führt ein Tipp auf die Kopfzeile („Juni 2025") jetzt direkt in die **Monats-
  und ein weiterer in die Jahresauswahl** — so springt man mit wenigen Tippern
  Jahre weit, statt sich Monat für Monat durchzuklicken. Außerdem behält der
  Kalender **immer dieselbe Höhe** (feste sechs Wochenzeilen): Bei Monaten mit
  weniger Zeilen verrutschte zuvor die Position der Navigationspfeile, wenn sich
  der Kalender nach oben öffnete (z. B. im mobilen Filter). (#283)
- **Mobiler Feinschliff (iPhone):** Im **Filter-Sheet** der Beschluss-Suche saß
  der Schließen-**„×"** über dem ersten Filter statt oben in der Kopfzeile (die
  Notch-Safe-Area galt fälschlich auch fürs Bottom-Sheet), und der
  **Datums-Kalender** lief unten aus dem Bild — er klappt jetzt nach oben (bzw.
  zur Seite), wenn kein Platz ist. In der **Parteien-Analyse** waren die
  Themenfeld-Namen abgeschnitten („Klima & U…"); die Beschriftung bekommt mehr
  Platz, die Balken sind entsprechend kürzer. Auf der **Übersicht** ist der
  „Frag den Rat"-Knopf mobil jetzt **volle Breite** (vorher links gequetscht mit
  viel Leerraum rechts). (#278)
- **Lotti-Tour: Sprechblase läuft auf schmalen iPhones nicht mehr über den Rand.**
  Im letzten Tour-Schritt („Leinen los!") ragte die Karte — samt „Erste Frage
  stellen"-Knopf — rechts aus dem Bildschirm, weil die breitere Button-Zeile die
  Karte nicht schrumpfen ließ. Die Karte darf jetzt bis in den verfügbaren Platz
  schrumpfen, und die Knopf-Zeile bricht bei Bedarf um. (#275)
- **Ausschuss-Filter (Beschluss-Suche) zeigt jetzt Kurznamen.** Im „Ausschuss"-
  Dropdown standen die langen amtlichen Namen und wurden mit „…" abgeschnitten;
  jetzt greift auch dort die Kurzname-Logik — Kurzname als Zeile, der volle Name
  als umbrechender Untertitel darunter. (#274)
- **Ratsgruppen werden nicht mehr als Partei verzerrt.** Wer in einer
  **Gruppe** sitzt (Zusammenschluss mehrerer Parteien/Parteiloser, z. B.
  „FDP/Volt" oder „Für Oldenburg"), erschien im Personen-Profil fälschlich
  unter einer einzelnen Partei — Jens Lükermann etwa als „FDP", obwohl er nie
  FDP-Mitglied war, sondern Volt in der Gruppe FDP/Volt. Der Verlauf heißt jetzt
  **„Zugehörigkeit im Zeitverlauf"** und zeigt **Fraktion, Gruppe und parteilos
  sauber getrennt**: eine Gruppe als eigene Kachel („Gruppe FDP/Volt" bzw. „Für
  Oldenburg") mit ihren Mitglieds-Parteien als Farbpunkte, dazwischen echte
  parteilose Phasen. Grundlage sind die Anwesenheits-Label der Protokolle (ein
  Gruppen-Mitglied trägt dort den Gruppennamen); erkannt über eine kuratierte
  Gruppenliste — ein „/" allein zählt nicht („Bündnis 90/Die Grünen" bleibt eine
  Partei). (#273)
- Die **Filter-Pillen der Beschluss-Suche zeigen jetzt ihre Auswahl**: Wer
  auf „Berichte" oder „Alle Vorgänge" umschaltet, sieht das direkt in der
  Pille (farblich gefüllt statt weiter „Beschlüsse"), und der
  Sortierung-Knopf trägt die gewählte Reihenfolge („Spannendste zuerst" …)
  statt stumm „Sortierung". (#257)
- Die Suche (Lupe bzw. ⌘K) **zoomt in der iPhone-App nicht mehr ungewollt
  hinein**: Das Eingabefeld der Befehls-Palette nutzt auf Mobilgeräten jetzt
  16 px Schriftgröße — darunter vergrößert iOS beim Antippen automatisch die
  ganze Ansicht. (#240)
- **Design-Audit umgesetzt:** Das Seiten-Menü und Hinweise respektieren jetzt
  die **iPhone-Aussparung** (nichts liegt mehr hinter Uhr/Dynamic Island),
  die Registrierung nennt die **Datenschutzerklärung** direkt am Knopf, und
  der Mitteilungs-Hinweis in der App erscheint erst, **wenn es etwas zu
  melden gäbe** (erstes Thema oder Abo). Dazu Feinschliff: Häkchen-Argumente
  auf der Anmelde-Seite, die „Heute im Rat"-Leiste verlinkt in jedem Zustand,
  Sitzungszeilen auf „Heute" springen **direkt zur aufgeklappten Sitzung**,
  Filter-Chips mit Druck-Feedback, aufgeräumte Login-Seite. (#238)
- **Terminplan sichtbar, sobald das RIS ihn veröffentlicht:** Das
  Ratsinformationssystem verlinkt Sitzungen erst, wenn ihre Tagesordnung
  online steht — frisch veröffentlichte Sitzungstermine (wie der Terminplan
  ab August) waren für Ratslotse deshalb wochenlang unsichtbar. Jetzt liest
  der Scraper zusätzlich die **Kalenderansicht und den RSS-Feed** des RIS und
  zeigt terminierte Sitzungen mit dem Hinweis **„Tagesordnung folgt"** auf
  der Sitzungen-Seite, im Heute-Briefing und in der Landing-Leiste; auch der
  Sitzungspause-Hinweis kennt damit das „wieder ab"-Datum. (#227)
- **Sitzungs-Benachrichtigungen überleben LLM-Aussetzer:** Lieferte das
  Sprachmodell für eine Tagesordnungs-Zusammenfassung kein gültiges JSON,
  brach bislang der komplette tägliche Ausschuss-Check ab — betroffene
  Benachrichtigungen gingen gar nicht raus (im Juli 11× passiert). Jetzt wird
  einmal neu versucht; klappt auch das nicht, kommt die Benachrichtigung
  ohne Zusammenfassung (mit Link zur Tagesordnung), und der nächste Lauf
  versucht die Zusammenfassung erneut statt ein falsches „nur Routine-TOPs"
  festzuschreiben. (#213)
- **Personen zeigen ihre letzte Fraktion:** Ratsmitglieder, die die Fraktion
  gewechselt haben (z. B. FDP → Volt oder Die Linke → BSW), wurden in der
  Personen-Liste und auf der Personen-Seite unter ihrer **häufigsten** statt
  ihrer **aktuellen** Fraktion geführt. Jetzt zählt die letzte aktive Fraktion
  (aus der jüngsten Sitzungs-Anwesenheit bzw. dem Ende des
  Fraktions-Verlaufs). (#212)
- **Quiz-Feinschliff aus dem Spielen:** Karten-Pins, die nur „Oldenburg" als
  Ganzes markierten (z. B. bei Fragen zu Bewegungen), entfallen — auch bei schon
  vorhandenen Fragen. Der **Fortschrittsbalken** zeigt jetzt die aktuelle Frage
  (bei „3/5" ist er 60 % voll). **Schätzfragen** starten den Slider bewusst
  außerhalb der Mitte (und die Spannen werden asymmetrisch erzeugt) — „gar nicht
  bewegen" ist keine Gewinnstrategie mehr. Neu im Glossar: die
  Krankenhaus-**Versorgungsstufen** (Maximal-/Schwerpunkt-/Grundversorgung,
  Fachkrankenhaus). (#210)
- **NWZonline-Link lädt nicht mehr endlos:** Bei sehr langen Beschlusstiteln
  (mit Klammer-Zusätzen, Datum, „- Bericht"-Anhang) hängte sich die NWZ-Suche
  in einer Dauer-Ladeschleife auf. Der Link „Bei NWZonline nach Berichten suchen"
  nutzt jetzt eine gekürzte, saubere Suchanfrage (Schlagworte statt kompletter
  Titel). (#200)
- **Quiz-Quelle verweist auf die richtige Seite:** Bei Fragen zu einer Person
  oder Sache verlinkt „Quelle: Wikipedia" jetzt deren **eigenen Artikel** (z. B.
  Hermann Lehmkuhl) statt der Stadtteil-Seite, aus der die Frage stammt. (#203)
- Der neue Stadtteil-Filter verschob auf dem Handy das ganze Themen-Layout
  seitlich (die Filter-Chips passten nicht mehr in eine Zeile) — sie brechen
  jetzt sauber um, und das Stadtteil-Menü öffnet als bildschirmfüllendes
  Auswahl-Feld statt halb aus dem Bild zu ragen. (#197)
- Auf dem Handy konnte die Stadtkarte über der Navigation und anderen
  Elementen liegen — die Karte bleibt jetzt unter Kopf- und Fußleiste. (#194)
- **Ratsgruppen zählen für alle beteiligten Parteien:** Anträge der früheren
  FDP/Volt-Gruppe werden jetzt sowohl FDP als auch Volt zugerechnet (nach der
  Trennung zählen neue Anträge automatisch nur für die jeweilige Fraktion, weil
  die Dokument-Labels die Zeit tragen). „WFO/LKR" war keine Partei und ist aus
  allen Auswertungen entfernt. (#187)

## [1.2.0] – 2026-07-03

Anträge, Themen-Karte & Feinschliff.

### Hinzugefügt
- **Fraktions-Anträge ausgewertet:** Die Original-Anträge der Fraktionen (Anlagen
  der Vorlagen) werden eingelesen — mit automatischer Antragsteller-Erkennung.
  Die Analyse zeigt echte **Erfolgsquoten je Fraktion** aus den eingereichten
  Dokumenten, Beschluss-Seiten ein **Anlagen-Dossier** (Anträge, Karten,
  Bilanzen) mit Direktlinks. (#174)
- **Technik-Doku live:** Die ausführliche Doku ist unter `/docs` erreichbar —
  inklusive Übersichtsgrafik „Welche Dokumente werten wir aus?". Sie ersetzt
  die bisherige Technik-Seite und ist im Footer verlinkt. (#175, #176, #186)
- **Themen-Vorschläge zum Anklicken:** „Meine Themen" schlägt die häufigsten
  Beschluss-Schlagworte der letzten sechs Monate vor — ein Klick legt das Thema
  mit fertiger Beschreibung an. (#184)
- **Glitzer-Hinweis auf die KI-Frage:** Der Umschalter funkelt dezent, bis die
  erste Frage gestellt wurde — danach ist Ruhe. (#182)

### Geändert
- **Themen-Seite neu:** Die Stadtkarte steht immer oben (kein verstecktes
  Toggle mehr), Filter-Chips nach Art (Orte/Organisationen/Projekte) filtern
  Karte und Liste gemeinsam, und die Top-Reihe priorisiert nach **Aktivität
  der letzten 12 Monate** statt nach Lebenszeit-Summe. (#181, #184)
- **Themenfeld-Rückblicke als Digest-Karten:** Kernaussage + Stichpunkte mit
  Feld-Icons statt langer Textblöcke; die Analyse öffnet jetzt standardmäßig
  auf **Trends**. (#183, #185)
- **Motion-Feinschliff nach Design-Engineering-Standards:** stärkere
  Easing-Kurven, Press-Feedback auf Buttons und Umschaltern, ⌘K öffnet ohne
  Animation, Karten-Hover feuert nicht mehr auf Touch. (#177)
- **Landing:** asymmetrisches Feature-Bento mit „Frag den Rat" als Hero-Karte,
  dezentes Filmkorn auf der Hafenszene, Glas-Effekt auf der mobilen Tab-Bar.
  (#178, #179)

### Behoben
- Die Technik-Doku unter `/docs` war seit jeher nicht erreichbar (fehlende
  Proxy-Route) — sie wird jetzt direkt von der App ausgeliefert. (#176)
- Der Feedback-Dialog verschwand auf dem Handy sofort wieder (er hing im
  Menü-Sheet und wurde mit ihm geschlossen). (#180)
- Die KI-Demo auf der Landing ließ die Seite beim Text-Streaming wachsen —
  die Karte reserviert jetzt von Anfang an ihre End-Höhe. (#181)
- Sporadische Serverfehler unter parallelen Anfragen behoben
  (SQLite-Verbindungen waren nicht threadfest). (#184)

### Betrieb
- Ops-Workflows per Knopfdruck: Vorlagen-/Anlagen-Backfill und
  Rückblick-Regeneration laufen über GitHub Actions. (#173, #185)

## [1.1.0] – 2026-07-02

Frag den Rat v2 & Vorlagen-Volltexte.

### Hinzugefügt
- **Vorlagen-Volltexte:** Sachverhalt und Begründung jeder Vorlage (~5.000
  Dokumente seit 2018) werden eingelesen — sichtbar auf den Beschluss-Seiten
  („Aus der Vorlage"), durchsuchbar und Teil des KI-Kontexts. (#172)
- **Klickbare Fußnoten in KI-Antworten:** Zitate erscheinen als nummerierte
  Chips; ein Klick springt zur Quelle, die Quellen tragen die Nummern. (#171)
- **KI-Prompts im Admin-UI editierbar** — Ton und Format der Antworten lassen
  sich ohne Deploy anpassen. (#171)

### Geändert
- **Konkretere KI-Antworten:** mehr Kontext je Beschluss (inkl. Gremium, Datum,
  Ergebnis), neueste Beschlüsse werden zuerst genannt. (#171)

### Betrieb
- Rate-Limit für die KI-Frage (10 Fragen / 10 Minuten), vollständiges
  Modell-Warm-up beim Start und persistenter Modell-Cache — die erste Frage
  nach einem Deploy ist so schnell wie jede andere. (#171)

## [1.0.0] – 2026-07-02

Open-Source-Go-Live von Ratslotse.

### Hinzugefügt
- **Lotti-Familie:** Maskottchen mit Küken, saisonalen Outfits und
  Feiertags-Spezials; neue Hafenszene auf der Landing. (#161)
- Social-Media-Vorschaubild (OG-Image) und Launch-Feinschliff. (#166)
- Konto-Löschung verlangt das Passwort und verabschiedet sich per E-Mail. (#167)

### Geändert
- **Keine Admin-Freischaltung mehr:** Neue Konten sind direkt nach der
  E-Mail-Bestätigung aktiv — niemand wartet mehr auf manuelle Freigabe.
  Admins können Konten weiterhin moderieren. (#163)
- KI-Frage und Suche teilen sich dasselbe Karten-Layout; die überzählige
  mobile Zwischen-Navigation ist entfernt. (#170)
- Robustheit im Web-UI: Fehler einzelner Seiten erhalten die App-Shell,
  defensives Rendering bei unerwarteten Daten. (#169)
- iOS-App: Privacy-Manifest, App-Store-Compliance, iPhone-only. (#168)

### Behoben
- Der „Demo"-Hinweis der Landing-KI-Demo wurde vom Fragen-Button verdeckt. (#162)

### Entfernt
- **Telegram-Bot entfernt:** Benachrichtigungen laufen ausschließlich über
  **Web-Push** (iOS/Android-App) und **E-Mail**; die Zustellkanäle sind
  `email` / `push` / `both`. Bestehende Telegram-Konten wurden serverseitig
  migriert. (#159)

### Betrieb
- **Cron-Alarme per E-Mail:** Schlägt ein Cron-Job fehl, geht zusätzlich zum
  Log eine E-Mail an die Betreiber-Adresse. (#165)
- **Off-Site-Backups:** Die tägliche Backup-Rotation kann per rsync auf einen
  zweiten Host gespiegelt werden. (#165)
- **Deploy nur mit grünen Tests:** Der Deploy-Workflow führt die Tests selbst
  aus und bricht bei Fehlern ab. (#164)

---

*Dieser Changelog beginnt mit dem Open-Source-Release von Ratslotse. Die
Entwicklungshistorie davor ist nicht Teil dieses Repositories.*

[Unreleased]: https://github.com/Schereo/Ratslotse/compare/v1.15.0...main
[1.15.0]: https://github.com/Schereo/Ratslotse/compare/v1.14.0...v1.15.0
[1.14.0]: https://github.com/Schereo/Ratslotse/compare/v1.13.2...v1.14.0
[1.13.2]: https://github.com/Schereo/Ratslotse/compare/v1.13.1...v1.13.2
[1.13.1]: https://github.com/Schereo/Ratslotse/compare/v1.13.0...v1.13.1
[1.13.0]: https://github.com/Schereo/Ratslotse/compare/v1.12.0...v1.13.0
[1.12.0]: https://github.com/Schereo/Ratslotse/compare/v1.11.0...v1.12.0
[1.11.0]: https://github.com/Schereo/Ratslotse/compare/v1.10.0...v1.11.0
[1.10.0]: https://github.com/Schereo/Ratslotse/compare/v1.9.0...v1.10.0
[1.9.0]: https://github.com/Schereo/Ratslotse/compare/v1.8.0...v1.9.0
[1.8.0]: https://github.com/Schereo/Ratslotse/compare/v1.7.1...v1.8.0
[1.7.1]: https://github.com/Schereo/Ratslotse/compare/v1.7.0...v1.7.1
[1.7.0]: https://github.com/Schereo/Ratslotse/compare/v1.6.0...v1.7.0
[1.6.0]: https://github.com/Schereo/Ratslotse/compare/v1.5.0...v1.6.0
[1.5.0]: https://github.com/Schereo/Ratslotse/compare/v1.4.0...v1.5.0
[1.4.0]: https://github.com/Schereo/Ratslotse/compare/v1.3.0...v1.4.0
[1.3.0]: https://github.com/Schereo/Ratslotse/compare/v1.2.0...v1.3.0
[1.2.0]: https://github.com/Schereo/Ratslotse/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/Schereo/Ratslotse/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/Schereo/Ratslotse/releases/tag/v1.0.0
