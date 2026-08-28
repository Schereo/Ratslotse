# Feature-Unterschiede: native iOS-App und Website

Stand: 28.08.2026 nach der nativen Paritäts- und Oberflächenrunde.

## Bewusst nur auf der Website

| Bereich | Entscheidung |
|---|---|
| Haushalt | Kommt in einem späteren, eigenen Paket. |
| Kommunalwahl | War ein Entwicklungs-Fun-Feature und wird bewusst nicht in die App übernommen. |
| Admin-Bereich | Bleibt Betriebsoberfläche im Web; Admin-Konten erhalten in der App einen Link. |
| Landingpage, Changelog und Dokumentation | Bleiben öffentliche Web-Inhalte. |
| Öffentliche Antwort-Snapshots unter `/g` | Bleiben wegen Web-Sharing und Vorschau-Metadaten im Web; die App teilt diese URLs nativ. |
| Hilfe, Kontakt und Rechtstexte | Öffnen aus der App die gepflegten Web-Seiten. |

## Noch offen als native Erweiterung

| Bereich | Status |
|---|---|
| Home-/Lock-Screen-Widget | Die Wochenkarte ist die fachliche Grundlage; WidgetKit folgt später. |
| Live Activity / Dynamic Island | Das Live-Dashboard ist vorhanden, die Systemdarstellung folgt später. |
| App Intents / Siri | Noch nicht umgesetzt. |
| Spotlight und Handoff | Noch nicht umgesetzt. |
| Physischer Push-/Apple-/Distributionstest | Vor TestFlight mit Signierung und echtem Gerät erforderlich. |

## Funktionsgleich, aber plattformgerecht anders

| Website | Native App |
|---|---|
| Browser-Download und PDF-Tab | Quick Look für Anlagen. |
| Browser-Karte | MapKit mit Clustering und Ortsumrissen. |
| Kalenderdatei/Browseraktion | Direkter EventKit-Kalendereintrag. |
| Browser-Share und Druck | iOS Share Sheet; öffentliche Antwort bleibt als Web-Snapshot teilbar. |
| Desktop-Navigation | Hovernde Glasnavigation auf dem iPhone, vollständige Seitenleiste auf dem iPad. |
| Desktop-Spalten für Chatquellen | Quellen-/Belegspalte neben dem Chat im iPad-Querformat, kompakte Darstellung auf dem iPhone. |

Dashboard, Ratsgespräch inklusive gründlicher Recherche, Beschlüsse,
Sitzungen und Anlagen, Stadtkarte, Themen, Profile, Merkliste, Abos, alle vier
Quizmodi, eigene Quizkarten, vollständige Quizstatistik, Lotsen-Abzeichen,
Onboarding sowie Konto- und Gesprächseinstellungen sind nativ vorhanden.
