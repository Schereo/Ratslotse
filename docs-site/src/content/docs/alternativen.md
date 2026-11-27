---
title: Alternativen
description: Andere Werkzeuge, die Ratsinformationen mit KI erschließen, wie weit sie Ratslotse ähneln und welche davon offenen Code haben.
---

Ratslotse ist nicht das einzige Projekt, das Ratsinformationen mit KI
zugänglich macht. Diese Seite hält fest, wer was anbietet, wo es sich mit
Ratslotse überschneidet und wo nicht, und welcher Code offen liegt.

**Stand: 27.11.2026.** Jede Angabe stützt sich auf die verlinkte Quelle,
meist die Seite des Anbieters selbst. Was dort nicht steht, steht hier auch
nicht. Wer Neueres weiß, zieht die Seite nach.

## Woran sich die Angebote unterscheiden

Vier Fragen trennen die Angebote:

- **Für wen?** Öffentlich für Bürger\*innen, oder intern für Verwaltung und
  Rat.
- **Welche Daten?** Eine Stadt, tief aufbereitet. Viele Städte über die
  OParl-Schnittstelle, meist nur die Dokumente. Oder gar keine eigenen, nur
  was Nutzer\*innen hochladen.
- **Wie tief?** Suche mit Chat über Dokumente, oder auch Protokolle,
  Wortbeiträge, Abstimmungen und Haushalt.
- **Meldet es sich?** Abos und Benachrichtigungen, oder nur Suche auf
  Anfrage.

Ratslotse beantwortet sie so: öffentlich, eine Stadt (Oldenburg), tief.
Beschlüsse, Vorlagen mit Anlagen, Protokolle mit Wortbeiträgen und
Abstimmungen, Pressemitteilungen der Stadt, für Konten mit dem Recht
`budget` auch der Haushalt. Dazu [Frag den Rat](/docs/frag-den-rat/) mit
Belegen, Benachrichtigungen per Mail und Push, die
[Live-Verfolgung der Ratssitzung](/docs/sitzungen/#live-verfolgung-der-ratssitzung),
Web, iOS-App und ein [MCP-Server](/docs/mcp/). Andere Städte kommen nur im
[Vergleich](/docs/andere-staedte/) vor. Der Code steht unter AGPL-3.0.

## Übersicht

| Angebot | Für wen | Kern | Code offen | Überschneidung mit Ratslotse |
|---|---|---|---|---|
| [RISKI](#riski-münchen) (München) | Bürger\*innen, Verwaltung | KI-Suche über Anträge, Vorlagen, Beschlüsse | ja, MIT | Frag den Rat |
| [mandari](#mandari-münster) (Münster) | Sitzungsdienst, Fraktionen, Bürger\*innen | komplettes RIS mit Bürgerportal für 40 Kommunen | ja, AGPL-3.0 | Abos, Karte, Kurzfassungen |
| [OpenCouncil](#opencouncil-griechenland) (Griechenland) | Bürger\*innen | Sitzungen transkribiert, zusammengefasst, abonnierbar | ja, AGPL-3.0 | Wortbeiträge, Abos, Chat, MCP |
| [Council Data Project](#council-data-project-usa) (USA) | Presse, Bürger\*innen | durchsuchbare Sitzungstranskripte | ja, MPL-2.0 | Wortbeiträge |
| [RIS-Bot Potsdam](#ris-bot-potsdam) | Bürger\*innen, Stadtverordnete | Chat über Drucksachen und Protokolle | angekündigt für 2027 | Frag den Rat |
| [neurapolis](#neurapolis-neuraflow) (neuraflow) | Verwaltung, Rat (intern) | semantische RIS-Suche über OParl | nein | Frag den Rat |
| [Albert](#albert-ulm) (Ulm) | Gemeinderat | Chat über Gemeinderatsvorlagen | nein | Frag den Rat |
| [RIS-Tiefenanalyse-Cockpit](#ris-tiefenanalyse-cockpit-locello) (Locello) | Verwaltung, Rat | Recherche und Vorlagen-Entwürfe | nein | Frag den Rat |
| [Poliscope](#poliscope) | Vertrieb, Planung, Redaktionen | über 4.500 RIS, Alerts, Chat, API | nein | Themen-Benachrichtigungen, MCP |

## Mit offenem Code

### RISKI (München)

Die KI-Suche im Ratsinformationssystem der Landeshauptstadt München, gebaut
vom IT-Referat (it@M), seit März 2026 als Beta unter
[riski.muenchen.de](https://riski.muenchen.de). Sie beantwortet Fragen über
Stadtratsanträge, Beschlussvorlagen und Beschlüsse der Wahlperiode 2020 bis
2026. Protokolle, Sitzungen, Stadtratsmitglieder und Fraktionen kennt sie
nicht. Die semantische Suche holt die zehn passendsten Dokumente, das
Sprachmodell prüft jedes einzeln auf Relevanz und begründet das kurz, dann
erst entsteht die Antwort. Modelle: GPT-4.1 für die Antwort,
text-embeddings-3-large für die Suche, Mistral Document AI für die
Texterkennung.

- **Ähnlich:** Frage in Alltagssprache, Antwort mit den gefundenen
  Dokumenten.
- **Anders:** keine Protokolle, keine Abstimmungen, keine Abos; nur die
  laufende Wahlperiode.
- **Code:** [github.com/it-at-m/riski](https://github.com/it-at-m/riski),
  MIT. Python, FastAPI, LangGraph, Vue, Postgres, Kafka.
- **Quelle:** [ki.muenchen.de](https://ki.muenchen.de/ki-systeme/riski),
  [Meldung der Stadt](https://stadt.muenchen.de/news/ris-ki--suchsystem.html)

### mandari (Münster)

Ein vollständiges Ratsinformationssystem aus drei Teilen: Session für den
Sitzungsdienst (Pilotphase), Work für Fraktionen (offene Beta) und Insight,
ein öffentliches Bürgerportal (im Einsatz). Insight liest bestehende
Ratsinformationssysteme über OParl ein und macht nach eigener Angabe
Vorgänge und Sitzungen aus 40 Kommunen durchsuchbar, ohne Anmeldung.
Beschlüsse lassen sich abonnieren, Vorgänge stehen auf der Karte, Vorlagen
gibt es als KI-Kurzfassung in einfacher Sprache, gekennzeichnet als
KI-erstellt. Einen Chat über die Dokumente nennt die Seite nicht. Anbieter
ist topixmedia, eine Einzelfirma in Münster; Version 1.0 ist für 2027
geplant.

- **Ähnlich:** öffentliches Bürgerportal mit Abos, Karte und Kurzfassungen.
- **Anders:** in die Breite (viele Kommunen, auch Sitzungsdienst und
  Fraktionsarbeit) statt in die Tiefe einer Stadt; keine Frage-Antwort,
  keine Protokoll-Auswertung.
- **Code:** [github.com/mandariOSS/mandari](https://github.com/mandariOSS/mandari),
  AGPL-3.0-or-later. Django, PostgreSQL, Elasticsearch, HTMX. Die
  eingelesenen Daten gibt mandari selbst wieder als OParl 1.1 aus.
- **Quelle:** [mandari.de/produkte](https://mandari.de/produkte/)

### OpenCouncil (Griechenland)

Eine Plattform der gemeinnützigen Schema Labs für griechische Gemeinden. Sie
transkribiert Ratssitzungen Wort für Wort mit Sprechererkennung (über
Stimmabdrücke), fasst die Redebeiträge zusammen, ordnet Themen zu und hat
einen KI-Chat über die Sitzungen. Bürger\*innen bekommen persönliche
Benachrichtigungen; alle Daten gibt es über eine öffentliche API, die Seite
hat einen MCP-Zugang. Beschlüsse sind mit ihrer amtlichen Veröffentlichung
im Transparenzportal Diavgeia verknüpft.

- **Ähnlich:** von allen Einträgen die größte Überschneidung: Wortbeiträge,
  Zusammenfassungen, Abos, Chat, MCP.
- **Anders:** geht vom Sitzungsvideo aus, nicht von Vorlagen und
  Protokollen; eine Instanz für viele Gemeinden.
- **Code:** [github.com/schemalabz/opencouncil](https://github.com/schemalabz/opencouncil),
  AGPL-3.0. Next.js, PostgreSQL/PostGIS, Prisma; Transkription und KI in
  einem eigenen Dienst
  ([opencouncil-tasks](https://github.com/schemalabz/opencouncil-tasks)).
- **Quelle:** [README](https://github.com/schemalabz/opencouncil),
  [opencouncil.gr](https://opencouncil.gr/)

### Council Data Project (USA)

Eine „Suchmaschine für Kommunalpolitik“: Transkripte von Ratssitzungen aus
US-Städten, durchsuchbar. Jede Stadt bekommt eine eigene Instanz aus einer
Vorlage; die Organisation listet 18 davon und warnt selbst, dass einige
keine neuen Daten mehr sammeln. Für die Sprechererkennung gibt es eine
eigene Bibliothek (speakerbox).

- **Ähnlich:** Wortbeiträge aus Sitzungen, öffentlich.
- **Anders:** keine Vorlagen-Aufbereitung, keine Abos auf den gelesenen
  Seiten; teils eingeschlafen.
- **Code:** [github.com/CouncilDataProject](https://github.com/CouncilDataProject),
  MPL-2.0. Python, TypeScript.
- **Quelle:** [GitHub-Organisation](https://github.com/CouncilDataProject),
  [University of Washington](https://ischool.uw.edu/news/2023/01/researchers-shed-light-city-governments-data)

### RIS-Bot Potsdam

Seit dem 17.11.2026 öffentlich unter
[risbot.potsdam.de](https://risbot.potsdam.de/). Der Chatbot sucht passende
Drucksachen und Sitzungsprotokolle, fasst sie zusammen und verweist auf die
Quellen; Anlagen, Antworten der Verwaltung und der Beratungsstand fließen
ein. Er bleibt bewusst bei den öffentlichen Unterlagen und sucht nicht im
Internet. Teil des Modellprojekts Smart City, vom Bund mit knapp 62.000 €
gefördert. Den Dienstleister nennt die Stadt nicht.

- **Ähnlich:** Frag den Rat für eine Stadt, für Bürger\*innen wie
  Stadtverordnete.
- **Anders:** nur der Chat; Abos oder eine App nennt die Stadt nicht.
- **Code:** laut Förderbedingungen ab 2027 als Open Source für andere
  Kommunen; noch kein Repository.
- **Quelle:** [Pressemitteilung der Stadt](https://www.potsdam.de/de/515-ki-gestuetzte-suche-im-ratsinformationssystem-geht-online)

## Kommerziell

### neurapolis (neuraflow)

Von der neuraflow GmbH (Bremerhaven). Erschließt die öffentlichen Dokumente
eines Ratsinformationssystems über OParl: Beschlüsse, Vorlagen und
Protokolle, jede Antwort mit Quelle zum Originaldokument, dazu Entwürfe für
Ratsvorlagen, Infobriefe und Social Media. Betrieb in der StackIT-Cloud.
Das Werkzeug ist „vor externen Zugängen geschützt“, also für Verwaltung und
Rat, nicht für die Öffentlichkeit. In Freiburg seit März 2026 über mehr als
90.000 Dokumente, mit einem Wissensgraphen, der Treffer Beschluss, Sitzung
und Gremium zuordnet; weitere Referenzen u. a. Bonn.

- **Ähnlich:** Frage-Antwort über Ratsdokumente mit Belegen.
- **Anders:** intern statt öffentlich; Schreibhilfe für die Verwaltung.
- **Quelle:** [neuraflow.de](https://www.neuraflow.de/loesungen/neurapolis),
  [Kommune21 zu Freiburg](https://www.kommune21.de/k21-meldungen/ris-intelligent-erschliessen/)

### Albert (Ulm)

Teil der „Ulmer Chatbot-Familie“ der Stadt Ulm, gebaut mit YOUniquehorns
(Software BotBucket). Albert ist für den Gemeinderat: Er kennt die
Gemeinderatsvorlagen, fasst sie zusammen und hilft beim Schreiben neuer. Die
Antworten nennen ihre Quellen, gespeichert wird in Frankfurt. Stand der
Quelle: Januar 2025.

- **Ähnlich:** Chat über die Vorlagen einer Stadt mit Quellen.
- **Anders:** für Ratsmitglieder, nicht öffentlich.
- **Quelle:** [Vortrag beim Digi-Lunch der Digitalakademie BW](https://digitalakademie-bw.de/wp-content/uploads/2025/01/22.-Digi-Lunch_Ulmer-Chatbots.pdf)

### RIS-Tiefenanalyse-Cockpit (Locello)

Ein Angebot von Locello (Marke „Bürger-Chat“) für Verwaltung und Rat:
Fachfragen mit Antworten samt Seitenzahl im PDF, Chronologien zu einem
Thema über viele Sitzungen und das Füllen kommunaler Mustervorlagen mit
Fakten aus dem RIS, Export nach Word. Gehostet in Frankfurt.

- **Ähnlich:** Fragen mit Belegen, Verlauf eines Themas.
- **Anders:** ein Arbeitswerkzeug für die Verwaltung; Schwerpunkt auf neuen
  Vorlagen.
- **Quelle:** [Datenblatt](https://www.die-netzwerkstatt.de/wp-content/uploads/2026/07/RIS-Tiefenanalyse-Cockpit-Datenblatt-fuer-Kommunen.pdf),
  [buerger-chat.de](https://buerger-chat.de/)

### Poliscope

Von der Poliscope GmbH (Lüneburg). Erfasst Sitzungen, Tagesordnungen und
Dokumente aus über 4.500 Ratsinformationssystemen in Deutschland. Suche,
KI-Chat, gespeicherte Suchen mit Benachrichtigung (wöchentlich bis täglich),
REST-API und eine Anbindung an ChatGPT und andere über MCP. Ab 49 € im Monat
zuzüglich Umsatzsteuer; die Tarife richten sich an Vertrieb und Planung,
für NGO, Journalismus, Forschung und Verwaltung gibt es Rabatt.

- **Ähnlich:** Themen-Benachrichtigungen, Chat, MCP.
- **Anders:** ganz Deutschland, aber nur die Dokumente; bezahlt; für
  Unternehmen und Redaktionen, nicht für Bürger\*innen.
- **Quelle:** [poliscope.de](https://poliscope.de/),
  [Preise](https://poliscope.de/preise)

## Angekündigt, noch nicht zu sehen

Karlsruhe hat 2025 einen Antrag für Chatbots im Ratsinformationssystem
behandelt. Die Stellungnahme der Verwaltung nennt zwei weitere Wege, von
denen öffentlich noch nichts zu sehen ist: eine Anfrage beim Hersteller
Somacos (SessionNet, auch das System der Stadt Oldenburg) und Überlegungen
bei Komm.ONE, dem kommunalen IT-Dienstleister in Baden-Württemberg, eine
KI-Auswertung von Gemeinderatsdokumenten zu bauen.

- **Quelle:** [Stellungnahme zu Vorlage 2025/0526](https://web1.karlsruhe.de/ris/oparl/bodies/0001/downloadfiles/a/00668231.pdf)

## Allgemeine Verwaltungs-KI

Oft im selben Atemzug genannt, aber kein Ersatz: Assistenten für
Beschäftigte der Verwaltung, ohne eigenen Bestand an Ratsdaten.

- **F13**: Open Source (MPL-2.0) aus Baden-Württemberg, nach eigener Angabe
  mit über 160.000 Zugängen in fünf Bundesländern und in Österreich. Agent,
  Recherche in hochgeladenen Dokumenten, Zusammenfassung, Transkription,
  Übersetzung. Konnektoren für WebDAV und SharePoint, keiner für ein
  Ratsinformationssystem. Die Kommunale Datenverarbeitung Oldenburg (KDO)
  betreibt darauf „moinGPT“. F13 2.0 bindet Werkzeuge über MCP an; der
  MCP-Server von Ratslotse ließe sich dort einhängen (nicht ausprobiert).
  Quelle: [f13-os.de](https://f13-os.de/kennenlernen),
  [Community](https://f13-os.de/community)
- **LLMoin**: von Dataport für Hamburg gebaut, inzwischen auch in
  Niedersachsen und für Kommunen. Texterstellung, Zusammenfassung,
  Recherche. Quelle:
  [Senatskanzlei Hamburg](https://www.hamburg.de/politik-und-verwaltung/behoerden/senatskanzlei/aktuelles/pressemeldungen/hamburg-etabliert-ki-assistenten-llmoin-als-bundesweit-nutzbares-erfolgsmodell-1127988)

## Vorläufer ohne KI

Zwei offene Projekte haben Ratsinformationen schon vor der KI für
Bürger\*innen aufbereitet und werden nicht mehr gepflegt:
[Meine Stadt Transparent](https://github.com/meine-stadt-transparent/meine-stadt-transparent)
(MIT, 2023 archiviert) und
[Politik bei uns](https://github.com/politik-bei-uns/politik-bei-uns-web-old)
(BSD-3-Clause, letzte Änderung 2017).

## Was sich abschauen ließe

- **RISKI:** die Relevanzprüfung je Dokument mit kurzer Begründung, bevor
  die Antwort entsteht. Zum Vergleich mit dem
  [Weg einer Frage](/docs/frag-den-rat/#der-weg-einer-frage) bei Frag den
  Rat ist das das nächste Gegenstück mit offenem Code.
- **mandari:** der OParl-Abgleich für 40 Kommunen und die Wiederausgabe als
  OParl. Beides betrifft den [Städte-Speicher](/docs/andere-staedte/), der
  heute einen Adapter je Ratsinformationssystem braucht.
- **OpenCouncil:** Sprechererkennung, kurze Ausschnitte aus Sitzungen
  („Highlights“) und die Benachrichtigungen; alles nah an der
  [Live-Verfolgung](/docs/sitzungen/#live-verfolgung-der-ratssitzung).
- **RIS-Bot Potsdam:** ansehen, sobald 2027 der Code erscheint.
