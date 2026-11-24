---
title: Sitzung & Tagesordnungspunkt
description: Sitzungsübersicht, Dossiers, Anträge und Argumente je Tagesordnungspunkt sowie Mitlesen und Live-Verfolgung der Ratssitzung.
---

Die Sitzungsseite zeigt dieselbe Tagesordnung in drei Phasen. Vor der
Sitzung stehen die Unterlagen bereit, währenddessen hebt die Seite den
laufenden Tagesordnungspunkt hervor und nach der Sitzung zeigt sie
die Ergebnisse.

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
Jede Boje steht für einen Tagesordnungspunkt, jedes Band für eine Etappe.
Der Server berechnet die Zuordnung. `council/course.py` bildet die Zeilen
der Tagesordnung und vorberechnete Angaben aus dem Store ohne Seiteneffekte
auf ein Dictionary gemäß `SessionCourse` (`web/backend/app/antworten.py`) ab.
Web und App übernehmen die Darstellung.

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
Punkt. Die Karten der Sitzungsseite führen dorthin.

Die Lesespalte steht in Reitern: Überblick (Kurzfassung, Dossier, Haushalt,
Wahlprogramme, Ähnliches), Argumente, Fraktionen, Vorgeschichte, Unterlagen
und, hinter dem Schalter `notizen`, Meine Notiz. „Frag den Rat“ bleibt in der
Seitenspalte. So stehen Notiz und Chat nebeneinander, und die Notiz bleibt
beim Scrollen neben einem langen Chat stehen. Nur der Notiz-Reiter wird
gemerkt (`sessionStorage`): Wer eine Sitzung Punkt für Punkt mitschreibt,
landet mit „Weiter“ wieder in der Notiz. Die folgenden Abschnitte sind die
Bausteine dieser Seite. Sie haben eine gemeinsame Regel: Was ein
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
  Anlagen. Sie steht als feste Tatsache im Prompt; Berichte und Anfragen (F7)
  bekommen dazu einen eigenen Auftrag (s. u.).
- **Kandidaten mit Seite**: Beträge, Daten, Paragrafen. Sie stehen als feste
  Fakten im Prompt, und ein Betrag oder Datum im Dossier muss unter ihnen sein.

Danach prüft `council/evidence.py` jede Aussage, ebenfalls ohne Modell. Eine
Aussage bleibt nur, wenn alles gilt:

1. Die Quelle ist bekannt (`V1`, `A1` …).
2. Das Zitat steht wörtlich in der Quelle, mindestens 30 Zeichen lang. Die
   Seitenzahl wird aus der Fundstelle berichtigt, nicht vom Modell übernommen.
   Verglichen wird ohne Leerraum, Trennstriche, Anführungs- und
   Aufzählungszeichen, Ligaturen aufgelöst. Trägt eine Ligatur im PDF gar kein
   Zeichen („bestägt“), gilt im zweiten Versuch ein Zitat, das bis auf die
   Ligatur-Paare (`ti`, `tt`, `ft` …) stimmt; Ziffern müssen weiter genau
   stimmen.
3. Jede Mengenangabe des Satzes steht im Zitat.
4. Wertungs- und Ergebniswörter nur, wenn das Zitat sie trägt.
5. Keine Aktenzeichen in Klammern, höchstens 220 Zeichen.
6. Keine Person mit Anrede, die nicht im Zitat steht.
7. Im Satz keine Adresse, kein `@`, keine Telefonnummer.

Ein Abschnitt, dessen Aussagen alle fallen, steht auf `unsupported` und nie
auf „steht nicht drin“. Das ist ein Unterschied: Das eine heißt „wir konnten
es nicht belegen“, das andere wäre eine Behauptung über die Vorlage.

**Berichte (Form F7).** Ein Bericht beschließt nichts, sein Inhalt sind seine
Befunde. Ohne eigenen Auftrag hatte er im Schema keinen Ort dafür: „Zahlen“
schloss Geld aus, „Kosten“ meint nur den Beschluss. Beim Quartalsbericht der
Beteiligungen (26/0818) standen deshalb drei Zahlen und Sätze über den
Vorgang da, wo elf Gesellschaften und Betriebe mit Plan und Hochrechnung
berichten. Seit 11/2026 hängt an der Eingabe einer F7-Vorlage der Zusatz
`template_dossier_report` (`kern/prompts.py`): unter „Was berichtet wird“
(bis 8) erst der Auftrag, dann das Gesamtergebnis, dann die Kernbefunde mit
ihrer Zahl; Folgen und Ursachen unter „Was sich daraus ergibt“; unter „Zahlen“
auch Geld (bis 10); Termine einer Terminliste (bis 8, `GRENZEN_FORM`). Die
Kandidaten einer Anlage reichen bei Berichten bis 80 je Art statt 25 — vorher
endete die Liste des Quartalsberichts auf Seite 4 von 14. Nur die Prüfsumme der
F7-Dossiers ändert sich (`BERICHT_VERSION`), der übrige Bestand läuft nicht neu.

Gemessen am 23.11.2026 an 25 Berichten, je zwei Läufe alt und neu, blind
verglichen von Gutachter-Agenten gegen die Quelltexte: neu besser in 37 von 50
Vergleichen, alt in 12; Kernabdeckung im Mittel 2,2 → 2,9 von 5, Füllstoff
3,2 → 2,3. Bei Finanz- und Quartalsberichten gewann neu alle 14 Vergleiche.
Der Preis: mehr Aussagen, mehr Fehler — bestätigt 10 gegen 5, fast immer eine
Zahl, die einem Teil gehört und dem Ganzen zugeschrieben wird.

**Viele Anlagen: Vorrang statt reihum.** Das Lesebudget (110.000 Zeichen) geht
reihum an die Lese-Anlagen, die kürzeste zuerst. Beim Haushaltsentwurf 2027
(26/0835: 30 Anlagen, 2,2 Mio. Zeichen, 20 davon Lesestoff) bekamen so die
kleinen Änderungslisten ihren Anteil und der Vorbericht nichts. Reicht das
Budget nicht für `ANLAGE_MIN` je Anlage, lesen seit 11/2026 nur die mit dem
höchsten `vorrang` — Label (Vorbericht, Zusammenfassung, Konzept,
Änderungsliste …) plus Anteil an Fließtext; Teilhaushalte sind Tabellen —,
so viele, dass jede `ANLAGE_KNAPP` (15.000) bekommt. Die übrigen stehen mit
ihrem Kopf im Belegmaterial. Ergebnis am Haushaltsentwurf: Fehlbedarf
170.145.721 € aus dem Vorbericht statt Randzahlen aus den Teilhaushalten.

**Inhaltssätze für jede Anlage mit Text**, auch fürs Belegmaterial (aus dem
Kopf). Belegt werden dürfen sie mit dem Titel der Titelseite
(`GIST_QUOTE_MIN`, 15 statt 30 Zeichen). Die Gegenlese-Liste zeigt sie unter
dem Namen der Unterlage, mit KI-Stern. `max_tokens` wächst mit der Zahl der
Unterlagen (je 150, höchstens 16.000).

**Eine leere Antwort ist kein Dossier.** Trägt die Antwort keinen einzigen
Abschnitt (leer oder kein JSON), endet der Aufruf mit `LeeresDossier` und die
Zeile auf `failed`; der nächste Lauf holt sie nach. Bis 11/2026 entstand
daraus ein Dossier aus lauter „steht nicht drin“ (im Messlauf 3 von 50
Antworten).

**Vergangene Stationen.** Eine Sitzung, die vorbei ist, zeigt das Dossier
zum Sitzungstag — keine Unterlage, die erst danach kam. Wurde dasselbe Material
später nur neu gelesen (gleiche Dokumente, neuer Auftrag oder reparierter
Text), gilt die neuere Lesung (`item_dossier_view`).

Gespeichert wird je Quellenlage eine Zeile in `template_dossiers`
(Schlüssel: Gegenstand plus Hash der Quellen). Kommt eine Anlage dazu,
entsteht eine neue Fassung, die alte bleibt als Geschichte stehen.

Der Cron `scripts/vorlagen_dossiers.py` baut die Dossiers für die Vorlagen von
drei Tagen zurück bis 21 Tage voraus, mit einer Kostengrenze je Lauf
(`DOSSIER_MAX_USD`). Vorher holt er Vorlagen und Punkt-Texte nach, die erst
nach dem Morgenlauf auf die Tagesordnung kamen: Der Haushaltsentwurf 2027
(26/0835) wurde am Sitzungstag nachgetragen, die Vorlage holte nur
`check_protocols` am nächsten Morgen — dann lag die Sitzung schon außerhalb
des Fensters, und es entstand nie ein Dossier. Mit dem
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
  Nach dem Parsen übernimmt Ratslotse Person, Fraktion, Gremium, Datum und
  Seite direkt aus dem Wortbeitrag. Aussagen ohne gültige Kennung und
  Streitpunkte ohne beide Seiten entfallen.

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

### Was der Haushaltsentwurf zeigt

Am Punkt zum Haushaltsentwurf steht zuerst ein Abriss: wozu es einen Haushalt
gibt (fester Text), ein Satz aus dem Vorbericht, der über allem steht —
bisher die Haushaltssicherung, wörtlich und ohne Modell gesucht
(`notice`) —, dann das Gesamtbild in drei bis fünf Sätzen, jeder mit
wörtlichem Zitat, und drei, vier Eckzahlen. Darunter bis zu zehn Befunde aus
den Grafiken des Vorberichts: je ein Titel, die eine Zahl, ein Satz, die neu
gezeichnete Grafik und der Weg zur Seite im PDF. Säulen tragen ihre Art sichtbar (Ist
voll, Prognose schraffiert, Plan mit Rand, Finanzplanung hell), damit ein
Planwert für 2030 nicht wie ein Ergebnis aussieht.

Drei Stufen, jede kann einen Befund kippen:

1. **Lesen ohne Modell** (`council/budget_charts.py`): Jede „Grafik n-m“
   des Vorberichts wird zu Daten. Tabellen liest PyMuPDF zellgenau; bei
   Diagrammen gehört jeder beschriftete Wert zu der Kategorie, über der er
   steht — die Textebene führt die Werte nicht in Jahresfolge. Diagramme ohne
   Wertbeschriftung und Bilder bleiben Lücken.
2. **Vorschlagen** mit dem kleinen Modell (`COUNCIL_FINDINGS_MODEL`) und
   **prüfen im Code**: Jede Zahl in Titel, Satz, Kennzahl und Grafik steht in
   der genannten Grafik (auch in Mio. € umgerechnet), im wörtlichen Zitat,
   oder ist Summe bzw. Differenz von Werten derselben Grafik. Die Art jeder
   Säule setzt der Code aus Kopf und Bildunterschrift.
3. **Prüfen mit dem größeren Modell** (`COUNCIL_FINDINGS_VERIFY_MODEL`):
   Trägt die Grafik die Deutung? Das Gesamtbild prüft es in einem Aufruf,
   Satz für Satz gegen die zitierten Seiten. Im Prototyp hielten 20 von 40 Funden nicht
   stand, fast immer wegen der Deutung, nicht der Zahl — etwa eine Teilzahl,
   die dem ganzen Haushalt zugeschrieben wurde.

Gespeichert wird je Vorbericht (`budget_draft_findings`, Schlüssel ist die
Dokumentnummer); er hängt oft an mehreren Punkten. Erzeugt werden die
Befunde im Lauf `vorlagen_dossiers` für Vorberichte an Punkten im selben
Fenster wie die Dossiers, gedeckelt von `FINDINGS_MAX_USD`. Für den Bestand:
`scripts/vorlagen_dossiers.py --bestand --haushaltsentwurf [--schreiben]`.

### Frag den Rat am Punkt

Auf Punkt- und Beschluss-Seite entsteht die Antwort an Ort und Stelle, mit
dem Punkt als Gegenstand, statt auf die Fragen-Seite zu springen. Die
Vorschlagsfragen darunter schreibt ein Modell passend zu genau diesem
Gegenstand. Beides steht unter
[Frag den Rat](/docs/frag-den-rat/#auf-der-seite-eines-beschlusses-oder-punkts).

Fragt jemand aus einem Verweis in der eigenen Notiz („Im Chat fragen“), steht
über dem Feld ein Bezug auf eine Unterlage und Seite. Die Frage trägt dann
`refs.document_id` und `page`; der Server schlägt den Text der Seite nach und
gibt ihn dem Modell als feste Stelle mit (`qa.stelle_block`). Fehlt der Text
(Scan, noch nicht geladen), sagt die Antwort das, statt ihn zu erraten. Den
Weg in der Notiz beschreibt
[Notizen](/docs/app-und-konten/#notizen-auf-dem-gerät-verschlüsselt).

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

Bei `temperature=0` gerät das Modell bei Audio in Wiederholungsschleifen.
Die Transkription verwendet daher 0,3 und prüft zusätzlich auf Schleifen.
Bei Audio ohne Sitzungsbeiträge, etwa Musik in einer Warteschleife, kann das
Modell eine Sitzung bis zum Token-Limit erfinden. Die Pipeline prüft deshalb
die Länge des Texts (höchstens rund 25 Zeichen je Audiosekunde) und
schneidet Text mit Zeitmarken hinter dem Ende des Audioabschnitts ab.

Die Aufnahme endet mit der Schlussformel der Sitzungsleitung, spätestens
nach der konfigurierten Höchstdauer (`COUNCIL_RECORD_MAX_HOURS`).

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
