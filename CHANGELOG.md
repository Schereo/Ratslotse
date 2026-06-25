# Changelog

Alle nennenswerten Änderungen an diesem Projekt (Ratslotse) werden hier dokumentiert.

Das Format orientiert sich an [Keep a Changelog](https://keepachangelog.com/de/1.1.0/),
die Versionierung folgt [Semantic Versioning](https://semver.org/lang/de/).
Versionen vor `0.5.1` wurden nachträglich aus der Git- und PR-Historie rekonstruiert.

## [Unreleased]

### Geplant
- Weitere Features: Geld-Tracking, Auto-Rückblicke, Vorgangs-Dossiers

## [0.11.0] – 2026-06-25

### Hinzugefügt
- **News-Verknüpfung:** Beschlüsse werden mit den NWZ-Artikeln verknüpft, die sie berichten (Embeddings + Zeitfenster + lexikalischer Themen-Filter); die Detailseite zeigt „In der Presse". (#71, #74)
- **Ähnlichkeits-Score** je Treffer in „Frag den Rat" und „Ähnliche Beschlüsse" — transparentes Ranking. (#73)

### Geändert
- **Frag den Rat** deutlich besser: die Frage wird zuerst in Themen-Suchbegriffe expandiert (statt der rohen Frage, die generische Beschlüsse holte) — Treffer sind jetzt klar themenrelevant. (#73)
- **Ziel-Tracking** nutzt zusätzlich semantisches Retrieval (Keyword ∪ Embeddings) → besserer Recall (2.266 statt 1.658 Zuordnungen). (#70)

### Behoben
- **Abstimmungs-Leiste:** Farben folgen jetzt dem Ausgang — abgelehnte Beschlüsse zeigen rot-dominant statt grün (sah vorher aus wie angenommen). (#72)

## [0.10.1] – 2026-06-25

### Behoben
- „Frag den Rat": Mehrfach-Zitate wie `[3269, 3346]` wurden in den Quellen nicht erkannt (Regex nur für Einzel-IDs) — die Antwort verwies auf Beschlüsse, die unten nicht auftauchten. Zitat-Auflösung jetzt als getestete Funktion (Mehrfach-IDs + ungültige Zitate entfernt). (#68)

### Geändert
- „Frag den Rat" zeigt jetzt **alle gefundenen Beschlüsse** (semantisch top-30, Score ≥ 0.3) statt nur der zitierten — breite Fragen liefern deutlich mehr Treffer. (#68)
- Refactoring: gemeinsame `DecisionLinkCard` statt drei kopierter Karten (QA, Ähnliche, Ziele). (#69)

## [0.10.0] – 2026-06-25

### Geändert
- Parteien-Normalisierung an die **echte Ratsstruktur 2021–26** angepasst (recherchiert): Whitelist realer Fraktionen/Gruppen inkl. der Wechsel (BSW = ehem. Die Linke, FDP/Volt aufgelöst, Gruppe Für Oldenburg). Nicht-Parteien (BUND, NABU, ADFC, Fossil Free, Beiräte, Verwaltung, Einzelpersonen) sind jetzt aus der Partei-Analyse gefiltert. (#66)

### Hinzugefügt
- **Beschlüsse verknüpft:** Partei-Filter (Klick auf eine Partei in der Analyse → ihre Beschlüsse), klickbare Themenfeld-Badges → gefilterte Liste, „Antrag von"-Labels auf der Detailseite, und bei einstimmigen Beschlüssen die anwesenden Fraktionen als Zustimmung. Partei + Feld liegen in der URL (deep-linkbar). (#67)

## [0.9.0] – 2026-06-25

### Hinzugefügt
- **Ähnliche Beschlüsse** (semantische Embeddings): fastembed/ONNX bettet jeden Beschluss offline ein, die Detailseite zeigt die nächsten Nachbarn. (#64)
- **Semantische Suche für „Frag den Rat"**: die Frage wird eingebettet und gegen die Beschluss-Vektoren gesucht — findet Beschlüsse auch ohne Wort-Übereinstimmung, mit Keyword-Fallback (kein Crash ohne fastembed). (#65)

### Geändert
- Ziele auf Oldenburgs **echte Pläne** gegründet (Klimaschutzplan 2035, Mobilitätsplan 2030, Bündnis Wohnen, Innenstadt-/Digitalstrategie) — Labels, Beschreibungen und Keywords aus den Plänen. (#60)
- Ziel-Tracking läuft **inkrementell im täglichen Cron** (nur neue Beschlüsse). (#61)
- Kompaktere Council-Tab-Leiste (Icons + kurze Labels). (#62)

### Refactoring
- `useFetch`-Hook + URL-Helfer entkoppeln Daten-Lade-Boilerplate. (#63)

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

[Unreleased]: https://github.com/Schereo/kommunalwahl-scraper/compare/v0.11.0...HEAD
[0.11.0]: https://github.com/Schereo/kommunalwahl-scraper/compare/v0.10.1...v0.11.0
[0.10.1]: https://github.com/Schereo/kommunalwahl-scraper/compare/v0.10.0...v0.10.1
[0.10.0]: https://github.com/Schereo/kommunalwahl-scraper/compare/v0.9.0...v0.10.0
[0.9.0]: https://github.com/Schereo/kommunalwahl-scraper/compare/v0.8.0...v0.9.0
[0.8.0]: https://github.com/Schereo/kommunalwahl-scraper/compare/v0.7.0...v0.8.0
[0.7.0]: https://github.com/Schereo/kommunalwahl-scraper/compare/v0.6.0...v0.7.0
[0.6.0]: https://github.com/Schereo/kommunalwahl-scraper/compare/v0.5.1...v0.6.0
[0.5.1]: https://github.com/Schereo/kommunalwahl-scraper/compare/v0.5.0...v0.5.1
[0.5.0]: https://github.com/Schereo/kommunalwahl-scraper/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/Schereo/kommunalwahl-scraper/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/Schereo/kommunalwahl-scraper/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/Schereo/kommunalwahl-scraper/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/Schereo/kommunalwahl-scraper/releases/tag/v0.1.0
