# Ratslotse

**Was entscheidet die Stadt — und was bedeutet das für dich?**

Ratslotse macht die Kommunalpolitik in Oldenburg zugänglich. Die Anwendung
erschließt Tagesordnungen, Vorlagen und Beschlüsse aus dem öffentlichen
Ratsinformationssystem. Du kannst Themen verfolgen, Entscheidungen nachlesen
und Fragen stellen, ohne dich durch einzelne Protokolle arbeiten zu müssen.

[Anwendung öffnen](https://ratslotse.de) ·
[Dokumentation](https://ratslotse.de/docs/) ·
[Neuigkeiten](https://ratslotse.de/changelog)

[![Tests](https://github.com/Schereo/Ratslotse/actions/workflows/test.yml/badge.svg?branch=main)](https://github.com/Schereo/Ratslotse/actions/workflows/test.yml)
[![Lizenz: AGPL-3.0](https://img.shields.io/badge/Lizenz-AGPL--3.0-blue.svg)](LICENSE)

## Was du mit Ratslotse machen kannst

- **Beschlüsse recherchieren.** Suche nach Stichworten und Themen, filtere
  Ergebnisse und lies die zugehörigen Vorlagen und Protokolle nach.
- **Fragen zur Ratsarbeit stellen.** Lotti, die KI in Ratslotse, beantwortet Fragen
  anhand der verfügbaren Ratsunterlagen und verweist auf ihre Quellen.
  Für ausführlichere Fragen gibt es eine gründliche Recherche.
- **Sitzungen verfolgen.** Sieh nach, was im Rat und seinen Ausschüssen ansteht,
  öffne Tagesordnungen und verfolge unterstützte Ratssitzungen live.
- **Bei deinen Themen auf dem Laufenden bleiben.** Abonniere Gremien und Themen
  oder merke dir einzelne Vorlagen. Benachrichtigungen kommen per E-Mail oder
  als Push-Mitteilung in der App.
- **Zusammenhänge erkunden.** Personen- und Fraktionsprofile, Themenübersichten
  und die Stadtkarte helfen, Entscheidungen einzuordnen. Im Quiz kannst du
  dein Wissen über Oldenburg ausprobieren.

Ratslotse gibt es als Website und als native SwiftUI-App für iPhone und iPad.
Der Haushaltsbereich im Web ist für Konten mit entsprechender Berechtigung
verfügbar. Ein Android-Gerüst liegt im Repository, ist aber noch nicht
veröffentlicht.

## Daten und Quellen

Grundlage sind die öffentlich zugänglichen Informationen der Stadt Oldenburg.
Ratslotse ist ein unabhängiges Projekt und kein offizielles Angebot der Stadt.
KI hilft beim Aufbereiten, Suchen und Erklären. Ihre Antworten können Fehler
enthalten; für den genauen Wortlaut führt der Weg deshalb immer zur Quelle.
Fehlende oder noch nicht veröffentlichte Protokolle begrenzen die Auswertung.

## Am Projekt mitarbeiten

Fehler, unverständliche Texte und Ideen kannst du über die
[Issues](https://github.com/Schereo/Ratslotse/issues) melden. Für Code- und
Dokumentationsbeiträge erklärt der [Beitragsleitfaden](CONTRIBUTING.md) die
lokale Einrichtung, Prüfungen und den Weg zum Pull Request.

| Einstieg | Inhalt |
| --- | --- |
| [Webanwendung](web/README.md) | Backend, Frontend und lokale Entwicklung |
| [iOS-App](ios/README.md) | SwiftUI-Projekt, Tests und Builds |
| [Technische Dokumentation](https://ratslotse.de/docs/) | Architektur, Datenverarbeitung und Betrieb |
| [Entwicklungsrezepte](REZEPTE.md) | Wiederkehrende Änderungen mit den zugehörigen Dateien |
| [Projektregeln](CLAUDE.md) | Arbeitsablauf und technische Vorgaben; auch über `AGENTS.md` erreichbar |
| [Änderungsverlauf](CHANGELOG.md) | Veröffentlichte Änderungen |

### Aufbau des Repositorys

| Verzeichnis | Inhalt |
| --- | --- |
| `council/` | Ratsdaten abrufen, verarbeiten und durchsuchen |
| `kern/` | Gemeinsame Datenhaltung, KI-Anbindung und Benachrichtigungen |
| `web/` | FastAPI-Backend und Next.js-Frontend |
| `ios/` | Native App für iPhone und iPad |
| `api/` | OpenAPI-Vertrag für die Schnittstelle |
| `scripts/` | Entwicklung, Datenpflege und Betrieb |
| `tests/`, `eval/` | Automatisierte Tests und Auswertung der KI-Qualität |
| `kommunalwahl/` | Wahlprogramme, Kandidatenregister und Daten für den Wahlabend |
| `docs-site/` | Quellen der technischen Dokumentation |
| `docs/archiv/` | Historische Planungsunterlagen |

Der technische Kern besteht aus Python, SQLite mit FTS5, FastAPI und Next.js.
Sprachmodelle werden über OpenRouter angebunden; die iOS-App nutzt SwiftUI.

## Sicherheit und Zusammenarbeit

Sicherheitslücken bitte [vertraulich melden](SECURITY.md).
Für die Zusammenarbeit gilt unser [Verhaltenskodex](CODE_OF_CONDUCT.md).

## Lizenz

Der Quellcode steht unter der [GNU AGPL-3.0](LICENSE).
