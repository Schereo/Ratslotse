# Changelog

Alle nennenswerten Änderungen an diesem Projekt (Ratslotse) werden hier dokumentiert.

Das Format orientiert sich an [Keep a Changelog](https://keepachangelog.com/de/1.1.0/),
die Versionierung folgt [Semantic Versioning](https://semver.org/lang/de/).
Versionen vor `0.5.1` wurden nachträglich aus der Git- und PR-Historie rekonstruiert.

## [Unreleased]

## [0.18.0] – 2026-06-26

### Geändert
- **Analyse-Tab mit Sub-Navigation:** der frühere eigenständige „Trends"-Tab ist jetzt eine Unterkategorie von **Analyse** (Parteien / Finanzen / Trends) — Trends sind ebenfalls Auswertungen. Alte `?tab=trends`-Links leiten automatisch auf `Analyse → Trends` um. (#99)

### Hinzugefügt
- **Finanzen-Auswertung „Wofür fließt das Geld?":** erkanntes Finanzvolumen je Themenfeld (dedupliziert, ohne Buchhaltungsdokumente), als Balken mit Summe und Beschluss-Anzahl, klickbar in die Beschlüsse des Felds — neben den „Größten Finanzbeschlüssen". (#99)
- **Erklärbare Trends:** die Quartals-Balken (Beschlüsse **und** Finanzvolumen) sind anklickbar und öffnen die Beschlüsse genau dieses Quartals; der Geld-Chart nennt den größten erkannten Einzelposten und zeigt je Quartal den größten Posten als Tooltip — eine faktische „Erklärung" der Ausschläge ohne KI-Raterei. (#99)

### Behoben
- **Finanzvolumen je Quartal** schließt jetzt Buchhaltungsdokumente (Haushaltsplan, Jahresabschluss, Wirtschaftsplan …) aus — vorher überdeckten deren Budget-Größenordnungen die tatsächlichen Ausgaben-Beschlüsse. Konsistent mit „Größte Finanzbeschlüsse" und „Wofür fließt das Geld?". (#99)

## [0.17.0] – 2026-06-25

### Hinzugefügt
- **Themen-Seiten (Entitäten):** ein LLM extrahiert wiederkehrende Eigennamen (Projekte, Orte, Organisationen) aus allen Beschlüssen; der neue **Themen-Tab** listet sie (1.008 Entitäten), und jede Themen-Seite bündelt alle zugehörigen Beschlüsse als Timeline plus erkanntes Finanzvolumen, beteiligte Fraktionen und Themenfeld-Verteilung (z. B. „Fliegerhorst": 164 Beschlüsse, 345 Mio. €). Beschluss-Detailseiten verlinken die genannten Entitäten. (#96, #97)

### Behoben
- **Themenfeld-Klassifikation:** Rechnungsdokumente (Jahresabschluss, Wirtschaftsplan, Haushaltsplan …) einer Fach-Einrichtung landen jetzt zuverlässig unter `finanzen` statt beim Fachthema; 115 Beschlüsse re-klassifiziert. Themenfeld-Genauigkeit im Gold-Eval 88 % → **93 %** (Gesamt → 90 %). (#94)

## [0.16.0] – 2026-06-25

### Hinzugefügt
- **Öffentliche Technik-Seite** (`/technik`): erklärt fortführbar die Verarbeitungskette (Extraktion → Klassifikation → Embeddings → Hybrid-Retrieval mit Reranker → RAG), Ziel-Tracking, News, Geld, Parteien, Qualitätsmessung und Grenzen — ohne Login erreichbar, von der Login-Seite verlinkt. (#92, #93)

### Geändert
- **Eval-Gold-Set 4,5× vergrößert** (43 → ~197 Fälle: 120 Themenfeld, 71 Ziel-Stance, 6 QA) per Doppel-Annotation (zwei unabhängige Durchläufe, nur Übereinstimmungen übernommen). Repräsentative Baseline jetzt **87 %** (Themenfeld 88 %, Ziel-Stance 83 % mit 0 Richtungsfehlern, Frag-den-Rat 100 % ohne Halluzinationen) — die vorherigen 95 % auf 19 leichten Fällen hatten die Leistung überschätzt. `eval_ai.py` batcht große Sets. (#92)

## [0.15.0] – 2026-06-25

### Hinzugefügt
- **Trend-Dashboard „Was bewegt den Rat?"** (neuer Trends-Tab): Beschlüsse je Quartal gestapelt nach den aktivsten Themenfeldern, erkanntes Finanzvolumen je Quartal, und die häufigsten (nicht-prozeduralen) Schlagworte der letzten zwei Quartale — klickbar in eine gefilterte Beschlussliste. Reine Aggregation der vorhandenen klassifizierten Daten, ohne neue Abhängigkeit. (#88, #91)

## [0.14.0] – 2026-06-25

### Hinzugefügt
- **Eval-Harness:** festes Gold-Set (`tests/eval/*.jsonl`) + `scripts/eval_ai.py`, das Klassifikation, Ziel-Stance und QA-Retrieval live dagegen scort — ein Regressions-Wächter gegen stille Qualitäts-Rückfälle. (#84)

### Geändert
- **Frag den Rat — Hybrid-Retrieval + Reranker (RAG-SOTA):** Volltext-Index (BM25, ß→ss + Diakritika-Folding) ∪ Vektoren auf der expandierten Frage, dann ein multilingualer Cross-Encoder (fastembed jina-reranker-v2) re-sortiert gegen die Originalfrage. QA-Treffer im Gold-Eval **83 % → 100 %** (Gesamt 95 % → 98 %); behebt keyword-lastige Ranking-Lücken (z. B. „Spielplätze"). Embedding-/Reranker-Modelle werden beim Service-Start vorgewärmt. (#85, #87)

## [0.13.0] – 2026-06-25

### Geändert
- **KI-Qualität nach Gold-Audit** (alle Features blind gegen Claude-Gold-Label geprüft): der **Themenfeld-Klassifikator** ordnet Gremien-/Ausschussbesetzungen jetzt `verwaltung_digital` zu (statt nach Themenwort) und Förderbeschlüsse nach Sachbereich statt `finanzen`; 76 betroffene Beschlüsse re-klassifiziert (119/119 Besetzungen jetzt korrekt). Das **Ziel-Tracking** wertet „zur Kenntnis genommene" Berichte und vertagte Punkte als `neutral` (außer konkretem Fortschritt); 286 Links re-bewertet, der überhöhte `voran`-Zähler korrigiert (984 → 705). (#82)
- **Ähnliche Beschlüsse** und **Größte Finanzbeschlüsse** fassen Quasi-Dubletten zusammen (gleiche Sache in Ausschuss/Rat, wiederkehrende Serien) — Dedup über Vorlage-Nr **und** normalisierten Titel. (#80, #81)
- Kleinere Politur: Betrag-Badge auch in der Beschlüsse-Liste, „1 Gegenstimme/Enthaltung" im Singular, Betrag-Badge ohne €-Dopplung. (#80)

### Behoben
- **Test-Suite verschickte echte E-Mails** über Resend: der Registrierungs-Test nutzte die Live-`RESEND_API_KEY` aus der lokalen `.env` und feuerte bei jedem Lauf echte Admin-Benachrichtigungen. Eine `conftest.py` erzwingt jetzt `RESEND_API_KEY=""`, sodass `send_email()` im Test garantiert ein No-op ist. (#83)

## [0.12.0] – 2026-06-25

### Hinzugefügt
- **Geld-Tracking:** der im Beschlusstext genannte Betrag wird heuristisch erkannt (€/EUR/Euro, Mio./Mrd.-Skalierung, Einheitspreise wie „275 €/m²" ausgeschlossen) und auf der Detailseite angezeigt. Neue Sektion **„Größte Finanzbeschlüsse"** in der Analyse-Tab (Top nach Betrag, Dubletten über Ausschuss/Rat zusammengefasst, ohne Bilanz-/Haushalts-/Treasury-Posten). Regex-Extraktion ohne LLM, läuft im täglichen Cron mit. (#76, #77, #78)

### Geändert
- **News-Verknüpfung** deutlich präziser: Artikel werden über ihren **Inhalt** eingebettet (nicht nur die Überschrift) und müssen ein themenspezifisches Wort mit dem Beschluss teilen — die vorherigen Fehltreffer (z. B. „Gesamtabschluss" ↔ „Oldenburg-Termine") sind weg, 157 belastbare statt 956 verrauschter Verknüpfungen. (#74, #75)

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

[Unreleased]: https://github.com/Schereo/kommunalwahl-scraper/compare/v0.17.0...HEAD
[0.17.0]: https://github.com/Schereo/kommunalwahl-scraper/compare/v0.16.0...v0.17.0
[0.16.0]: https://github.com/Schereo/kommunalwahl-scraper/compare/v0.15.0...v0.16.0
[0.15.0]: https://github.com/Schereo/kommunalwahl-scraper/compare/v0.14.0...v0.15.0
[0.14.0]: https://github.com/Schereo/kommunalwahl-scraper/compare/v0.13.0...v0.14.0
[0.13.0]: https://github.com/Schereo/kommunalwahl-scraper/compare/v0.12.0...v0.13.0
[0.12.0]: https://github.com/Schereo/kommunalwahl-scraper/compare/v0.11.0...v0.12.0
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
