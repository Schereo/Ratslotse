# Changelog

Alle nennenswerten Änderungen an diesem Projekt (Ratslotse) werden hier dokumentiert.

Das Format orientiert sich an [Keep a Changelog](https://keepachangelog.com/de/1.1.0/),
die Versionierung folgt [Semantic Versioning](https://semver.org/lang/de/).

## [Unreleased]

### Hinzugefügt
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

### Geändert
- **Zahlen, die eine Rechenprobe nicht bestehen, ersetzen keine vorhandenen
  mehr.** Liest ein Parser für einen bereits gespeicherten Jahrgang plötzlich
  nichts oder deutlich weniger — etwa weil die Stadt ihre Tabellen umbaut —,
  bleibt der alte Stand stehen und der Lauf meldet es, statt den Bestand gegen
  ein kaputtes Ergebnis zu tauschen. Beim Einlesen von Hand lässt sich das mit
  `--auch-schrumpfen` übergehen; ein leeres Ergebnis ersetzt auch dann nichts.
  Ein Jahrgang wird außerdem am Stück gespeichert — bricht ein Lauf mittendrin
  ab, steht hinterher der alte Stand da und kein halber neuer. (#511)

### Behoben
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

[Unreleased]: https://github.com/Schereo/Ratslotse/compare/v1.12.0...main
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
