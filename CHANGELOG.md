# Changelog

Alle nennenswerten Änderungen an diesem Projekt (Ratslotse) werden hier dokumentiert.

Das Format orientiert sich an [Keep a Changelog](https://keepachangelog.com/de/1.1.0/),
die Versionierung folgt [Semantic Versioning](https://semver.org/lang/de/).

## [Unreleased]

### Hinzugefügt
- **Feedback landet jetzt auch im Admin-Bereich.** Rückmeldungen aus der App
  gingen bisher ausschließlich per E-Mail raus — wer sie übersah oder löschte,
  hatte sie verloren. Sie werden nun zusätzlich gespeichert und im Admin unter
  **„Feedback"** aufgelistet: neueste zuerst, mit Art, Absenderin und Zeitpunkt,
  filterbar auf Unerledigtes. Ein Eintrag lässt sich als erledigt abhaken und
  bei Bedarf wieder öffnen. Gibt es Offenes, trägt **„Admin" in der Navigation
  eine Zahl** — dasselbe Zeichen, das „Meine Themen" schon nutzt. Der
  Mailversand bleibt unverändert. (#311)

### Behoben
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

### Hinzugefügt
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

### Geändert
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

[Unreleased]: https://github.com/Schereo/Ratslotse/compare/v1.3.0...main
[1.3.0]: https://github.com/Schereo/Ratslotse/compare/v1.2.0...v1.3.0
[1.2.0]: https://github.com/Schereo/Ratslotse/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/Schereo/Ratslotse/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/Schereo/Ratslotse/releases/tag/v1.0.0
