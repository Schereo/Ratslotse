<p align="center">
  <a href="https://ratslotse.de">
    <img src="web/frontend/public/lotti/standbild-hebt-hand.png" alt="Lotti, die Lotsenmöwe von Ratslotse, winkt zur Begrüßung" width="220" height="220">
  </a>
</p>

<h1 align="center">Ratslotse</h1>

<p align="center">
  <strong>Was entscheidet die Stadt — und was bedeutet das für dich?</strong><br>
  Kommunalpolitik in Oldenburg. Verständlich, durchsuchbar und mit Quellen.
</p>

<p align="center">
  <a href="https://ratslotse.de"><strong>Ratslotse öffnen →</strong></a>
  &nbsp; · &nbsp;
  <a href="https://ratslotse.de/docs">Dokumentation</a>
  &nbsp; · &nbsp;
  <a href="https://ratslotse.de/changelog">Neuigkeiten</a>
</p>

<p align="center">
  <a href="https://github.com/Schereo/Ratslotse/actions/workflows/test.yml"><img src="https://github.com/Schereo/Ratslotse/actions/workflows/test.yml/badge.svg?branch=main" alt="Tests auf main"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/Lizenz-AGPL--3.0-0764a6" alt="Lizenz: AGPL-3.0"></a>
</p>

---

Ratslotse erschließt Tagesordnungen, Vorlagen und Beschlüsse aus dem öffentlichen
Ratsinformationssystem. Du kannst Themen verfolgen, Entscheidungen nachlesen
und Fragen stellen, ohne dich durch einzelne Protokolle arbeiten zu müssen.
Lotti, unsere Lotsenmöwe, begleitet dich dabei durch die Anwendung.

## Dein Zugang zur Stadtpolitik

<table>
  <tr>
    <td width="50%" valign="top">
      <h3>🔎 Beschlüsse recherchieren</h3>
      <p>Suche nach Stichworten und Themen, filtere Ergebnisse und lies die zugehörigen Vorlagen und Protokolle nach.</p>
    </td>
    <td width="50%" valign="top">
      <h3>💬 Fragen stellen</h3>
      <p>Erhalte KI-gestützte Antworten mit Verweisen auf die Ratsunterlagen. Für ausführlichere Fragen gibt es eine gründliche Recherche.</p>
    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">
      <h3>📅 Sitzungen verfolgen</h3>
      <p>Sieh nach, was im Rat und seinen Ausschüssen ansteht, öffne Tagesordnungen und verfolge unterstützte Ratssitzungen live.</p>
    </td>
    <td width="50%" valign="top">
      <h3>🔔 Themen im Blick behalten</h3>
      <p>Abonniere Gremien und Themen oder merke dir Vorlagen. Benachrichtigungen kommen per E-Mail oder als Push-Mitteilung in der App.</p>
    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">
      <h3>🗺️ Zusammenhänge erkennen</h3>
      <p>Personen- und Fraktionsprofile, Themenübersichten und die Stadtkarte helfen dir, Entscheidungen einzuordnen.</p>
    </td>
    <td width="50%" valign="top">
      <h3>💡 Oldenburg besser kennen</h3>
      <p>Teste im Quiz dein Wissen über die Stadt und entdecke neue Seiten der Oldenburger Kommunalpolitik.</p>
    </td>
  </tr>
</table>

Ratslotse gibt es als Website und als native SwiftUI-App für iPhone und iPad.
Der Haushaltsbereich im Web ist für Konten mit entsprechender Berechtigung
verfügbar. Ein Android-Gerüst liegt im Repository, ist aber noch nicht
veröffentlicht.

## Mit Quellen, zum Nachlesen

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

<details>
<summary><strong>Für die Entwicklung: Aufbau des Repositorys</strong></summary>

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

</details>

Der technische Kern besteht aus Python, SQLite mit FTS5, FastAPI und Next.js.
Sprachmodelle werden über OpenRouter angebunden; die iOS-App nutzt SwiftUI.

---

[Sicherheitslücke melden](SECURITY.md) ·
[Verhaltenskodex](CODE_OF_CONDUCT.md) ·
[GNU AGPL-3.0](LICENSE)
