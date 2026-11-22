---
title: Sitzung & Tagesordnungspunkt
description: Die Seite einer Sitzung als Kurs, die Seite je Tagesordnungspunkt mit Dossier, Anträgen und Argumenten, Mitlesen und die Live-Verfolgung der Ratssitzung.
---

Eine Sitzung hat drei Zustände: Sie steht bevor, sie läuft, sie ist vorbei.
Die Seiten dazu zeigen jeweils dieselbe Tagesordnung, aber mit dem, was in
diesem Moment bekannt ist: vorher die Unterlagen, währenddessen der laufende
Punkt, nachher die Ergebnisse. Diese Seite beschreibt, woraus das entsteht.

Alles hier liegt hinter [Feature-Schaltern](/docs/referenz/feature-schalter/).
Der Abschnitt nennt jeweils den Schalter; ohne ihn zeigt die Oberfläche die
ältere Fassung oder die Karte nicht.

| Teil | Schalter | Wo im Code |
|---|---|---|
| Sitzungsseite als Kurs | `sitzung-kurs` | `council/course.py`, `CouncilStore.session_course` |
| Seite je Tagesordnungspunkt | `punkt-seite` | `GET /api/council/session/{ksinr}/item` |
| Dossier aus den Unterlagen | `aus-den-unterlagen`, `folgetexte-aus-dossier` | `council/template_dossier.py`, `council/evidence.py` |
| Änderungsanträge | `aenderungsantraege` | `council/motions.py` |
| Argumente und Fraktionen | `punkt-argumente` | `council/arguments.py` |
| Kasten „Im Haushalt“ | `haushalt-am-punkt` | `council/punkt_haushalt.py` |
| Fachwörter aus der Vorlage | `begriffe-aus-vorlage` | `council/vorlage_begriffe.py` |
| Umfeld: Ort, Ähnliches, Video, Beteiligung | `punkt-umfeld` | `council/punkt_umfeld.py` |
| Wahlprogramme zum Punkt | `wahlprogramm-am-punkt` | `council/programm_bezug.py` |
| Mitlesen und eigener Mitschrieb | `mitlesen`, `mitschrieb` | `app/(app)/council/sitzung/mitlesen/` |

## Kurs der Sitzung

Die Sitzungsseite (`/council/sitzung`) zeigt eine Sitzung als Linie mit Bojen:
jede Boje ein Tagesordnungspunkt, jedes Band eine Etappe. Was davon gilt,
entscheidet der Server. `council/course.py` ist rein: Eingabe sind die Zeilen
der Tagesordnung und ein paar vorberechnete Angaben aus dem Store, Ausgabe ein
Wörterbuch in der Form von `SessionCourse` (`web/backend/app/antworten.py`).
Web und App zeichnen nur.

**Nur Rubriken eröffnen eine Etappe.** Der erste Entwurf machte aus jedem
Oberpunkt ohne Vorlage eine Etappe. Der Bauausschuss vom 27.08.2026 trägt
aber elf Überschriften der Art „Bauleitplanung Meerweg“ mit je zwei
Unterpunkten; daraus wären elf Etappen mit zwei Bojen geworden. Solche
Überschriften benennen ein Vorhaben. Ihre Punkte bleiben in „Beschlüsse und
Berichte“ und tragen die Gruppe als Feld. Eine Etappe eröffnen nur Rubriken
wie „Anträge der Fraktionen“ oder die Ausschuss-Abschnitte im Rat.

**Lottis Satz zur Sitzung.** Den Kopf der Seite trägt ein Satz, der sagt, was
ansteht. Es gibt ihn zweimal: gerechnet (`course.py::summary_sentence`,
zuverlässig, klingt aber wie ein Formular) und von einem Modell geschrieben
(`council/session_summary.py`), aus genau denselben Angaben: Titel, Art,
„wichtig“ samt Grund, Kurzfassung je Punkt und nach dem Protokoll das
Ergebnis. Der geschriebene Satz entsteht beim Eintreffen der Tagesordnung und
noch einmal mit dem Protokoll. Die Seite zeigt ihn, solange er zum Stand der
Tagesordnung passt, sonst den gerechneten.

**Wann das Protokoll kommt.** Nach der Sitzung nennt die Seite eine Schätzung
(`council/protokoll_erwartung.py`). Ein Protokoll wird in der nächsten Sitzung
desselben Gremiums genehmigt und erscheint meist wenige Tage danach: Von 20
Protokollen mit echtem Eingangsdatum kamen 17 ein bis vier Tage nach der
nächsten Sitzung (gemessen am 12.11.2026). Ferien stecken damit schon im
Kalender. Steht die nächste Sitzung noch nicht fest, schätzt der Code ihren
Abstand aus derselben Jahreszeit früherer Jahre.

## Die Punkt-Seite

Jeder Tagesordnungspunkt hat eine eigene Seite (`/council/punkt`) mit
Kurzfassung, Vorgeschichte, Unterlagen und „Frag den Rat“ zu genau diesem
Punkt. Die Karten der Sitzungsseite führen dorthin. Die folgenden Abschnitte
sind die Bausteine dieser Seite. Sie haben eine gemeinsame Regel: Was ein
Modell schreibt, wird im Code gegen die Quelle geprüft, und was sich nicht
belegen lässt, erscheint nicht.

### Aus den Unterlagen: das Dossier

Ziel ist, dass man die Unterlagen nur noch zum Gegenlesen braucht. Je Vorlage
schreibt **ein** Modellaufruf alle Abschnitte: Beschlussvorschlag in einfachen
Worten, Kosten, Änderungen, Betroffene, Kennzahlen, Haltung der Verwaltung,
was danach passiert, dazu einen Inhaltssatz je Unterlage. Ein Aufruf statt
mehrerer ist rund 70 % günstiger.

Davor steht eine Vor-Ernte ohne Modell (`council/dossier_harvest.py`):

- die **Form** der Vorlage aus Vorlagenart, Titelendung und den Typen der
  Anlagen. Das Modell bekommt nur das Schema seiner Form.
- **Kandidaten mit Seite**: Beträge, Daten, Paragrafen. Sie stehen als feste
  Fakten im Prompt, und ein Betrag oder Datum im Dossier muss unter ihnen sein.

Danach prüft `council/evidence.py` jede Aussage, ebenfalls ohne Modell. Eine
Aussage bleibt nur, wenn alles gilt:

1. Die Quelle ist bekannt (`V1`, `A1` …).
2. Das Zitat steht wörtlich in der Quelle, mindestens 30 Zeichen lang. Die
   Seitenzahl wird aus der Fundstelle berichtigt, nicht vom Modell übernommen.
3. Jede Mengenangabe des Satzes steht im Zitat.
4. Wertungs- und Ergebniswörter nur, wenn das Zitat sie trägt.
5. Keine Aktenzeichen in Klammern, höchstens 220 Zeichen.
6. Keine Person mit Anrede, die nicht im Zitat steht.
7. Im Satz keine Adresse, kein `@`, keine Telefonnummer.

Ein Abschnitt, dessen Aussagen alle fallen, steht auf `unsupported` und nie
auf „steht nicht drin“. Das ist ein Unterschied: Das eine heißt „wir konnten
es nicht belegen“, das andere wäre eine Behauptung über die Vorlage.

Gespeichert wird je Quellenlage eine Zeile in `template_dossiers`
(Schlüssel: Gegenstand plus Hash der Quellen). Kommt eine Anlage dazu,
entsteht eine neue Fassung, die alte bleibt als Geschichte stehen.

Der Cron `scripts/vorlagen_dossiers.py` baut die Dossiers für die Vorlagen der
nächsten 21 Tage, mit einer Kostengrenze je Lauf (`DOSSIER_MAX_USD`). Mit dem
Schalter `folgetexte-aus-dossier` lesen auch Kartentext und Tragweite die
belegten Dossier-Zeilen statt des Rohtexts der Vorlage.

### Änderungsanträge

`council/motions.py` liest je Antrag, was er an welcher Stelle will: alt
gegen neu, mit Belegen. Ein Modellaufruf je Antrag, sobald er eintrifft. Die
Basis, gegen die geändert wird, löst der Code auf, wo er kann:

- **Paragraf als Anker.** Nennt der Antrag „§ 24 Absatz 2“ und liegt das
  Regelwerk am Punkt, holt der Code den geltenden Wortlaut selbst. Das „alt“
  ist dann kein Modelltext, und der Wortvergleich zeigt die Änderung Wort für
  Wort („zwei Tage“ wird „eine Woche“).
- **Beschlussvorschlag.** Ersetzt der Antrag ihn, steht er als Quelle daneben.
- **Andere Fassung.** Nennt der Antrag eine andere Vorlagennummer als die des
  Punkts, ist sie die Basis, und das Ergebnis sagt das.

Jede Aussage des Modells geht durch dieselbe Belegprüfung wie das Dossier.
Lieber ein leeres Feld als ein falsches Alt-neu-Paar.

Anträge kommen oft erst kurz vor der Sitzung. Der Cron
`scripts/antraege_nachzuegler.py` liest deshalb an Sitzungstagen und am Tag
davor die Tagesordnung viermal neu und lädt, was dazugekommen ist. Nach dem
Protokoll trägt die Seite das Ergebnis je Antrag nach.

### Argumente und Fraktionen

Zwei Reiter, mit Absicht verschieden gebaut (`council/arguments.py`):

- **Fraktionen entstehen ohne Modell.** Die Wortbeiträge in `council_speeches`
  sind schon Paraphrasen aus dem Protokoll. Sie werden nur nach Fraktion
  geordnet. Was das Protokoll keiner Fraktion zuordnet, steht unter „Fraktion
  im Protokoll nicht genannt“.
- **Argumente ordnet ein Modell** zu Streitpunkten mit Dafür und Dagegen. Es
  bekommt nummerierte Quellen und muss zu jeder Aussage die Kennung nennen.
  Wer etwas gesagt hat, entscheidet nicht das Modell, sondern die Quelle:
  Person, Fraktion, Gremium, Datum und Seite werden nach dem Parsen aus dem
  Wortbeitrag übernommen. Eine Aussage ohne gültige Kennung fällt weg, ein
  Streitpunkt ohne beide Seiten auch.

Rund die Hälfte der Wortbeiträge trägt im Protokoll keine Partei. Steht die
Person eindeutig in der Anwesenheitsliste derselben Sitzung und sitzt dort für
eine Fraktion, kommt die Zuordnung von dort (`fill_factions`), ohne Modell.

### Im Haushalt

Der Kasten zeigt Zahlenreihen aus dem [Haushalts-Bestand](/docs/haushalt/) zu
dem, was die Vorlage nennt, damit ein Betrag eine Größenordnung bekommt:
481.300 Euro mehr für den Rettungsdienst stehen dann neben 65 Millionen im
Teilhaushalt. Von 983 öffentlichen Punkten mit Vorlage seit 11/2025 nennt
rund jeder sechste etwas, wozu es eine Reihe gibt.

`council/punkt_haushalt.py` arbeitet ohne Modell und ordnet nur zu, was die
Vorlage ausdrücklich nennt:

- die Nummer eines Teilhaushalts oder Produkts, aber nicht aus dem Satz zur
  Deckung („gedeckt durch Mehrerträge im Teilhaushalt 04“ ist die Quelle des
  Geldes, nicht der Gegenstand),
- den Namen eines städtischen Betriebs zusammen mit einem Finanzwort,
- eine Steuer, die Schulden oder den Haushalt als Ganzes im Titel.

Der Kasten ist für alle sichtbar, nicht nur mit dem Recht `budget`.

### Fachwörter aus der Vorlage

Das geprüfte Glossar (`kern/glossar.py`) deckt, was oft vorkommt. Was nur in
einer Vorlage steht („Rotor-out-Planung“, „Komplementärin“), steht dort nie.
`council/vorlage_begriffe.py` ergänzt das je Vorlage mit zwei Modellen, weil
eines nicht reicht. Gemessen an 20 Vorlagen mit 49 Begriffen: Das kleine
Modell findet die richtigen Wörter, aber jede 25. Erklärung ist falsch und
jeder neunte Begriff allgemein bekannt. Also schlägt das kleine vor
(`COUNCIL_TERMS_MODEL`), und ein größeres (`COUNCIL_TERMS_VERIFY_MODEL`) lässt
nur durch, was fachlich stimmt und erklärungsbedürftig ist. Dazwischen prüft
Code: Das Wort steht wörtlich in den Lesetexten, das Zitat wörtlich in der
Vorlage.

Gespeichert wird je Vorlage in `template_terms`, neu nur bei geänderter
Quellenlage. Die Seite kennzeichnet diese Erklärungen als KI-erzeugt. Kosten:
rund 0,004 $ je Vorlage, gedeckelt je Cron-Lauf über `TERMS_MAX_USD`.

### Das Umfeld

Vier Angaben aus Daten, die es schon gibt (`council/punkt_umfeld.py`, ohne
Modell):

- **Ort mit Karte**: die belegten Orte der Beschlüsse zu dieser Vorlage. Gibt
  es noch keinen Beschluss, ein Straßenname aus dem Titel, aber nur ganze
  Namen mit Straßen-Endung, damit „Markt“ nicht jede Marktgebühr verortet.
- **Ähnliche frühere Beschlüsse**: die vorberechneten Nachbarn
  (`council_similar`), nur frühere.
- **Sprung in die Aufzeichnung**: die Fundstelle aus `council_video_results`.
  Die gibt es nur für Ratssitzungen, andere Gremien werden nicht übertragen.
- **Laufende Bürgerbeteiligung**: über die Plan-Nummer im Titel, wie auf der
  Beschluss-Seite.

### Was die Wahlprogramme dazu sagen

Je Liste im Rat höchstens eine Einordnung: Ihr Programm zur Ratswahl 2026
spricht für oder gegen das Anliegen des Punkts, mit der wörtlichen Stelle und
der Seitenzahl. Keine Wahrscheinlichkeit, keine Vorhersage einer Abstimmung.
Die ließe sich nicht belegen, das Zitat schon. Schweigt ein Programm, steht
die Liste unter „keine Aussage“.

Ein Zitat einer Partei ist ein Urteil über sie, deshalb vier Stufen
(`council/programm_bezug.py`):

1. **Suchen ohne Modell**: je Liste die Abschnitte, die dem Punkt am nächsten
   sind (Einbettungen), plus solche, die ein markantes Wort des Titels
   wörtlich tragen.
2. **Einordnen** mit dem kleinen Modell (`COUNCIL_PROGRAM_MODEL`): dafür,
   dagegen oder keine Aussage, je mit wörtlicher Stelle.
3. **Prüfen im Code**: Das Zitat steht wörtlich im Programm dieser Liste. Die
   Seitenzahl kommt aus der Fundstelle.
4. **Prüfen mit dem größeren Modell** (`COUNCIL_PROGRAM_VERIFY_MODEL`): Trägt
   die Stelle die Einordnung, und meint sie dieselbe Maßnahme?

Stufe 4 gibt es wegen einer Messung an zwölf Punkten: Zu „Preiswerte
Wohnungen“ fand Stufe 2 bei acht von neun Listen ein „dafür“, weil jedes
Programm günstigen Wohnraum will. Das ist keine Aussage zu dieser Maßnahme.
Die Kosten je Cron-Lauf deckelt `PROGRAM_MAX_USD`.

### Frag den Rat am Punkt

Auf Punkt- und Beschluss-Seite entsteht die Antwort an Ort und Stelle, mit
dem Punkt als Gegenstand, statt auf die Fragen-Seite zu springen. Die
Vorschlagsfragen darunter schreibt ein Modell passend zu genau diesem
Gegenstand. Beides steht unter
[Frag den Rat](/docs/frag-den-rat/#auf-der-seite-eines-beschlusses-oder-punkts).

## Mitlesen

Die Ansicht `/council/sitzung/mitlesen` geht die Sitzung Punkt für Punkt
durch: der Kurs oben, darunter der aktuelle Punkt, Zurück und Weiter. Im Rat
folgt die Seite der Übertragung, also dem Punkt, den die
[Live-Verfolgung](#live-verfolgung-der-ratssitzung) gerade meldet.

**Mein Mitschrieb** (Schalter `mitschrieb`) hält je Punkt die eigene
Einschätzung fest, was passiert ist, und einen freien Text. Er ist auf dem
Gerät verschlüsselt wie die
[Notizen](/docs/app-und-konten/#notizen-auf-dem-gerät-verschlüsselt): Der
Server speichert nur Geheimtext. Die Einschätzung färbt die Bojen, aber nur
im eigenen Kurs.

## Live-Verfolgung der Ratssitzung

Nur der Rat wird übertragen (oldenburg eins, O1). Daraus entstehen zwei
Dinge: während der Sitzung die Live-Karte („Welcher Punkt läuft, wer
spricht?“) und noch am selben Abend vorläufige Abstimmungsergebnisse. Das
amtliche Protokoll braucht ein bis zwei Monate.

```
O1-Stream (HLS) ──► Transkript ──► Live-Verfolgung ──► council_live_state ──► Live-Karte
                        │
                        └────────► Ergebnis-Extraktion ──► council_video_results (vorläufig)
```

**Mitschnitt.** `scripts/record_council_livestream.py` startet täglich und
nimmt auf, wenn eine Ratssitzung läuft. Der Stream ist selbst gehostetes HLS
und vom Server frei abrufbar. Es gibt zwei Wege zum Text:

- **Streaming** (`council/stream_stt.py`): Das Audio läuft als Strom an einen
  Transkriptionsdienst in der EU-Region (Gladia, `GLADIA_API_KEY`). Eine
  fertige Äußerung kommt im Median 5,2 Sekunden nach ihrem Ende zurück.
- **Audio-Stücke** (`council/livestream.py`): Ohne den Schlüssel schneidet
  ffmpeg Stücke von `COUNCIL_CHUNK_SECONDS` Länge, die ein Modell mit
  Audio-Eingang transkribiert (`COUNCIL_STT_MODEL`). Der Verzug ist dann
  mindestens die Stücklänge.

Zwei Fallen der Audio-Transkription sind als Code festgehalten. Mit
`temperature=0` gerät das Modell bei Audio in Wiederholungsschleifen, deshalb
0,3 und ein Schleifen-Wächter. Und enthält ein Stück keine Rede zur Sache
(Warteschleife, Musik), erfindet das Modell eine komplette Sitzung bis ans
Token-Limit. Dagegen stehen zwei mechanische Wächter: Mehr als rund 25 Zeichen
je Audio-Sekunde ist keine Transkription, und Zeitmarken hinter dem Ende des
Stücks sind Fortschreibung, dort wird gekappt.

Die Aufnahme endet mit der Schlussformel der Sitzungsleitung, spätestens an
der Kappe (`COUNCIL_RECORD_MAX_HOURS`).

**Verfolgung.** `council/livetracker.py` bekommt das Transkript in Fenstern
(`COUNCIL_LIVE_WINDOW_SECONDS`, dazu sofort, wenn ein Punkt aufgerufen oder
das Wort erteilt wird), zusammen mit der Tagesordnung, dem
Sprecher-Verzeichnis und dem letzten Stand. Ein schnelles Modell
(`COUNCIL_LIVE_TRACKER_MODEL`) antwortet, welcher Punkt am Ende des Fensters
läuft, in welcher Phase, und wer das Wort hat. Das Ergebnis ist eine Zeile je
Sitzung in `council_live_state`. Gemessen an der Ratssitzung vom 31.08.2026
(3 h 49 min): Ein Aufruf steht rund sieben Sekunden nach dem Satz auf der
Karte, die Verfolgung kostete 1,06 $ für die ganze Sitzung. Die Grenze ist
die Zeitauflösung: Formalien, die im Block in einer Minute durchlaufen,
erscheinen nicht einzeln. Die Karte sagt dann „TOP 9.4–9.8“.

Wer spricht, liest das Modell nicht aus der Stimme, sondern aus der Ansage
der Sitzungsleitung („Herr Ellberg, dann Herr Paul“). Ohne Verzeichnis riet es
die Fraktion in rund 30 % der Fälle falsch; mit der Anwesenheitsliste der
vorigen Ratssitzung und einem unscharfen Abgleich der Nachnamen stehen Name
und Fraktion.

**Nur eine Ratssitzung wird verfolgt.** Am 28.09.2026 fiel die Übertragung
aus, der Sender zeigte sechs Stunden Ersatzprogramm, und der Tracker machte
aus den Publikumsfragen einer Kinder-Uni die Einwohnerfragestunde. Seitdem
gelten drei Regeln:

- Das Modell beurteilt je Fenster, ob überhaupt eine Ratssitzung läuft.
- Ein Wechsel des Punkts braucht einen **Aufruf**: ein wörtliches Zitat aus
  dem Fenster, das den Punkt beim Namen nennt (Nummer oder ein Wort aus dem
  Titel). Ein Thema, das zum Titel passt, reicht nicht.
- Gezeigt wird erst ab dem ersten solchen Aufruf. Läuft eine Weile etwas
  anderes, wird der Stand zurückgezogen. Bleibt es dabei, gilt die Sitzung
  als beendet, und der Mitschnitt hört auf.

**Vorläufige Ergebnisse.** `council/videos.py` liest aus dem Transkript die
Abstimmungsergebnisse in die Tabelle `council_video_results`, ausdrücklich als
vorläufig. Gemessen gegen 120 protokollierte Hauptabstimmungen aus sechs
Sitzungen: 111 als gesichert ausgegeben, 111 davon richtig. Der Preis sind
drei Sicherungen:

1. Der Prompt darf schweigen und muss jedes Ergebnis mit einem wörtlichen
   Zitat belegen.
2. Jeder Beleg wird mechanisch im Transkript wiedergefunden. Was nicht
   dasteht, ist erfunden und fliegt raus.
3. Zwei Durchläufe mit versetzten Schnittkanten. Nur wo beide dasselbe
   Ergebnis nennen, gilt es als gesichert.

Beim Zusatz „einstimmig“ oder „mehrheitlich“ gilt: nur behaupten, was der
Wortlaut trägt. Gegenstimmen werden per Handzeichen gezählt und fast nie
ausgesprochen. Das Feld bleibt deshalb leer, wo weder eine gezählte
Gegenstimme noch das Wort „einstimmig“ im Beleg steht.

Die Ergebnisse aus dem Livestream tragen noch keinen Sprung ins Video. Tags
darauf steht die Aufzeichnung online; `scripts/check_council_videos.py` liest
sie mit demselben Verfahren und ersetzt die Zeilen samt echten Zeitmarken.
Kommt später das Protokoll, ersetzt sein Ergebnis beides.
