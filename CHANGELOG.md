# Changelog

Alle nennenswerten Änderungen an diesem Projekt (Ratslotse) werden hier dokumentiert.

Das Format orientiert sich an [Keep a Changelog](https://keepachangelog.com/de/1.1.0/),
die Versionierung folgt [Semantic Versioning](https://semver.org/lang/de/).

## [Unreleased]

### Geändert
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
