# Changelog

Alle nennenswerten Änderungen an diesem Projekt (Ratslotse) werden hier dokumentiert.

Das Format orientiert sich an [Keep a Changelog](https://keepachangelog.com/de/1.1.0/),
die Versionierung folgt [Semantic Versioning](https://semver.org/lang/de/).
Versionen vor `0.5.1` wurden nachträglich aus der Git- und PR-Historie rekonstruiert.

## [Unreleased]

### Geplant
- Semantische **Embeddings** statt Keyword-Retrieval (bessere Treffer für Ziel-Tracking und „Frag den Rat", Clustering, verwandte Beschlüsse)
- Weitere Querverbindungen: Vorgangs-Dossiers, Geld-Tracking, News-Verknüpfung, Auto-Rückblicke

## [0.8.0] – 2026-06-25

### Hinzugefügt
- **Frag den Stadtrat** (Schritt 4 der KI-Roadmap): KI-Q&A über die Beschlüsse. Freitextfrage → Keyword-Retrieval → LLM-Antwort, die nur aus den gefundenen Beschlüssen zitiert (mit verlinkten Quellen) und ehrlich sagt, wenn nichts passt. (#59)

## [0.7.0] – 2026-06-25

### Hinzugefügt
- **Ziel-Tracking** (Schritt 3): neue „Ziele"-Tab zeigt je Stadtziel (Klimaneutralität 2035, Verkehrswende, Wohnungsbau, Kita/Schule, Innenstadt, Digitalisierung), wie viele Beschlüsse es voranbringen / bremsen / neutral berühren, mit aufklappbarer Beschlussliste. LLM-Bewertung über keyword-retrievte Kandidaten. (#58)

## [0.6.0] – 2026-06-25

### Hinzugefügt
- **Parteien-Profil** (Schritt 2): neue „Parteien & Analyse"-Tab — Themen-Heatmap (Partei × Themenfeld), Erfolgsquoten der Anträge, Streitgrad je Themenfeld, häufige Allianzen. Fraktionsnamen werden normalisiert. (#57)

## [0.5.1] – 2026-06-25

### Behoben
- `CouncilStore`-Init crashte auf Bestandsdatenbanken: der `policy_field`-Index lag im statischen SCHEMA und lief via `executescript` **vor** der Migration, die die Spalte erst anlegt (`no such column: policy_field`) — betraf authentifizierte Council-Endpunkte und den täglichen Cron auf prod. Index in die Migration verschoben; Regressionstests für die Migration-von-alt ergänzt. (#56)

## [0.5.0] – 2026-06-25

### Hinzugefügt
- KI-Klassifikation aller Beschlüsse/Berichte in 12 Themenfelder + feine Tags + Ein-Satz-Zusammenfassung per LLM (`council/topics.py`); der tägliche Cron klassifiziert neue Beschlüsse automatisch mit.
- Themenfeld-Filter in der Beschlüsse-Liste, `/council/fields`-Endpoint (Felder mit Anzahl), Feld-Badges auf Karten und Detailseite. Fundament für Parteien-Profil und Ziel-Tracking. (#55)

## [0.4.0] – 2026-06-24

### Hinzugefügt
- Stadtrats-Beschlüsse: Extraktion strukturierter Beschlüsse, Abstimmungen, Teilabstimmungen und Anwesenheit aus den Sitzungsprotokollen (PDF → LLM). (#48)
- Beschlüsse-Ansicht mit Suche, Filtern und Pagination sowie Detailseite je Beschluss (Volltext, aggregierte Abstimmungs-Leiste, Weg der Vorlage durch die Gremien). (#49, #51, #52)

### Geändert
- Beschluss-Liste: Tab-Status in der URL, Aufteilung Beschlüsse/Berichte, Sortierung und klarere visuelle Filter-Hierarchie. (#53, #54)
- Protokoll-Backfill parallelisiert (ThreadPoolExecutor, DB-Writes im Main-Thread). (#50)

## [0.3.0] – 2026-06-22

### Hinzugefügt
- Öffentlicher Launch als **ratslotse.de** (Caddy/TLS auf der Edge-VM, Deploy-Härtung, Logo). (#33, #34)
- **E-Mail-Zustellung** als Digest-Kanal über Resend; Telegram von der Identität entkoppelt (`owner_id`), Kanalwahl je Konto (telegram/email/beide). (#42)
- Admin-Statistiken; Admin-Benachrichtigung bei neuer Registrierung; Link zum Artikel-Volltext im Nachbericht; NWZ-Archiv-Backfill für Ausgaben älter als 30 Tage. (#41, #45, #44, #43)
- Stadtrats-Tagesordnungen inline mit Suche; NWZ-Pagination, Artikel-Volltext, Themen-Bearbeitung. (#46, #38, #39, #23)

### Behoben
- PWA: Safe-Area-/Mobil-Layout; diverse Frontend-Politur; Artikel-refid mit Slash. (#47, #36, #35)

## [0.2.0] – 2026-06-19

### Geändert
- Klassifikator-Reife: Split + Themen-Mapping, per-Modell-Parameter, schärfere Verify-Prompts, Eval-Framework. (#27, #28, #29, #31, #21)

## [0.1.0] – 2026-06-18

### Hinzugefügt
- Grundlage: NWZ-Scraper, OpenRouter-basierter Klassifikator, Telegram-Bot und erstes Web-Frontend (FastAPI-Backend + Next.js-Frontend). (#24, #17)

[Unreleased]: https://github.com/Schereo/kommunalwahl-scraper/compare/v0.8.0...HEAD
[0.8.0]: https://github.com/Schereo/kommunalwahl-scraper/compare/v0.7.0...v0.8.0
[0.7.0]: https://github.com/Schereo/kommunalwahl-scraper/compare/v0.6.0...v0.7.0
[0.6.0]: https://github.com/Schereo/kommunalwahl-scraper/compare/v0.5.1...v0.6.0
[0.5.1]: https://github.com/Schereo/kommunalwahl-scraper/compare/v0.5.0...v0.5.1
[0.5.0]: https://github.com/Schereo/kommunalwahl-scraper/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/Schereo/kommunalwahl-scraper/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/Schereo/kommunalwahl-scraper/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/Schereo/kommunalwahl-scraper/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/Schereo/kommunalwahl-scraper/releases/tag/v0.1.0
