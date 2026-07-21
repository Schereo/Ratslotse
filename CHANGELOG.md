# Changelog

Alle nennenswerten Änderungen an diesem Projekt (Ratslotse) werden hier dokumentiert.

Das Format orientiert sich an [Keep a Changelog](https://keepachangelog.com/de/1.1.0/),
die Versionierung folgt [Semantic Versioning](https://semver.org/lang/de/).

## [Unreleased]

### Geändert
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

### Behoben
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

### Geändert
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

### Hinzugefügt
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

[Unreleased]: https://github.com/Schereo/Ratslotse/compare/v1.2.0...main
[1.2.0]: https://github.com/Schereo/Ratslotse/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/Schereo/Ratslotse/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/Schereo/Ratslotse/releases/tag/v1.0.0
