# Changelog

Alle nennenswerten Änderungen an diesem Projekt (Ratslotse) werden hier dokumentiert.

Das Format orientiert sich an [Keep a Changelog](https://keepachangelog.com/de/1.1.0/),
die Versionierung folgt [Semantic Versioning](https://semver.org/lang/de/).
Versionen vor `0.5.1` wurden nachträglich aus der Git- und PR-Historie rekonstruiert.

## [Unreleased]

## [0.37.0] – 2026-06-26

### Hinzugefügt
- **3D-Karte von Oldenburg im Landing-Hero:** eine gekippte, langsam rotierende MapLibre-Karte mit extrudierten 3D-Gebäuden (freie, schlüssellose OpenStreetMap-Tiles via OpenFreeMap), als Showcase neben dem Text (zweispaltig auf großen Viewports). Lädt nur clientseitig; bei Tile-Fehler greift das Partikel-Netzwerk als Fallback. CSP um `worker-src blob:` + die Tile-Domain erweitert. (#131)

## [0.36.2] – 2026-06-26

### Behoben
- **iOS-Mobile:** Eingabefelder (Input/Textarea/Select) haben auf dem Handy jetzt 16px Schrift, damit Safari beim Fokussieren nicht mehr automatisch hineinzoomt. Vorher blieb die Seite nach dem Login eingezoomt und die Bottom-Nav war erst nach manuellem Rauszoomen richtig sichtbar. (#129)

## [0.36.1] – 2026-06-26

### Geändert
- „Mein Konto": die Karten (Passwort / Zustellung / Telegram / Konto löschen) stehen bei großem Viewport nebeneinander (zweispaltiges Grid) statt in einer schmalen Spalte. (#128)

## [0.36.0] – 2026-06-26

### Hinzugefügt
- **Aufgewertete Landing Page:** animiertes Partikel-Netzwerk im Hero (leichtgewichtiges Canvas, kein three.js; respektiert „reduzierte Bewegung"), Scroll-Einblend-Animationen der Feature-Karten und **echte Live-Zahlen** (Beschlüsse/Sitzungen/Themen, hochzählend) über den neuen öffentlichen Endpoint `/api/council/public-stats`. (#127)

## [0.35.1] – 2026-06-26

### Behoben
- Der Footer (Impressum/Datenschutz) klebt jetzt am unteren Rand (Desktop sticky, mobil über der Bottom-Nav) statt bei wenig Inhalt mitten in der Seite zu schweben. (#126)

## [0.35.0] – 2026-06-26

### Hinzugefügt
- **Passwort vergessen / zurücksetzen** per E-Mail: Seiten `/forgot-password` + `/reset-password` (Link auf der Login-Seite). Einmal-gültige, **gehashte** Token mit 1-Stunde-Ablauf, **keine E-Mail-Enumeration**, Rate-Limit, Versand über Resend; nach dem Zurücksetzen werden alle bestehenden Sessions ungültig. (#125)
- **Konto löschen** (DSGVO – Recht auf Löschung): `DELETE /api/account` entfernt Konto + alle zugehörigen Daten (Themen, Treffer, Abos, Token); im Konto-Bereich mit Bestätigungsdialog, danach automatischer Logout. (#125)

### Geändert
- „Meine Themen": der Hinweistext referenziert nicht mehr die NWZ. (Hinweis: Themen matchen aktuell NWZ-Artikel; Beschlüsse/Ausschüsse werden separat über Ausschuss-Abos benachrichtigt.) (#125)

## [0.34.1] – 2026-06-26

### Geändert
- Die doppelte In-Page-Tableiste (Suche/Sitzungen/Themen/Analyse) im Ratsinfo entfällt — die Navigation läuft jetzt über die Sidebar; der Seitentitel wechselt stattdessen pro Ansicht (Beschlüsse/Sitzungen/Themen/Analyse). (#124)

## [0.34.0] – 2026-06-26

### Hinzugefügt
- **Öffentliche Landing Page** unter `/`: erklärt Ratslotse (Features, amtliche Quelle) und führt über einen Button oben rechts in die App — „Zum Dashboard" (eingeloggt) bzw. „Anmelden". Ersetzt den bisherigen Redirect und gibt der Startseite echten, indexierbaren Inhalt (SEO). (#123)

## [0.33.0] – 2026-06-26

### Hinzugefügt
- **SEO-Grundlage:** Root-Metadaten + OpenGraph/Twitter-Tags (schöne Link-Vorschauen), `robots.txt` und `sitemap.xml`. Indexiert die öffentlichen Marketing-/Rechtsseiten; die Ratsinhalte folgen mit dem Öffentlich-Gang. (#122)

### Geändert
- **Seitennavigation neu gegliedert:** Obertitel **Ratsinfo** mit den Unterseiten Beschlüsse/Sitzungen/Themen/Analyse direkt in der Nav, und **NWZ** (Artikelsuche) nur noch für freigeschaltete Nutzer bzw. Admins. „Mein Konto" ist ins E-Mail-Feld unten links integriert; eigener Menüpunkt entfällt. (#122)

## [0.32.0] – 2026-06-26

### Hinzugefügt
- **Stadtweite Karte** im Themen-Tab: Umschalter Liste/Karte zeigt alle verorteten Themen (Orte, Straßen, Projekte) als anklickbare Punkte auf einer Oldenburg-Karte — Punktgröße nach Zahl der Beschlüsse, Farbe nach Art, Klick öffnet das Thema. Neuer Endpoint `/council/entities-map` + `list_entities_geo()`. (#121)

## [0.31.1] – 2026-06-26

### Hinzugefügt
- Datenschutz-Hinweis unter dem „Frag den Rat"-Eingabefeld: bitte keine personenbezogenen/sensiblen Daten eingeben (Anfragen gehen an einen externen KI-Dienst). (#120)

## [0.31.0] – 2026-06-26

### Geändert
- **KI-Anfragen (OpenRouter) routen nicht mehr nach China.** `nwz/llm.py` setzt einen Provider-Routing-Block: China-basierte Anbieter (DeepSeek, Baidu, StreamLake, SiliconFlow, Alibaba) werden ausgeschlossen, und es werden nur Endpunkte ohne Daten-Speicherung/-Training genutzt (`zdr` + `data_collection=deny`). Dasselbe DeepSeek-Modell läuft damit bei einem westlichen Anbieter (verifiziert: Together, USA — DPF-gedeckt) — weiterhin günstig, kein China-Transfer. Per Env justierbar/abschaltbar (`NWZ_OPENROUTER_ROUTING/IGNORE/ZDR`). (#119)

## [0.30.0] – 2026-06-26

### Entfernt
- **NWZ-Zugangsdaten-Feature komplett entfernt.** Es werden keine NWZ-Logins mehr gespeichert (kein `nwz-credentials`-Endpoint, keine `nwz_verified`-Verifikation, `require_nwz_verified` weg). NWZ-Inhalte sind für angemeldete Nutzer als Überschriften + Links zugänglich; den Volltext schaltet ein Admin pro Nutzer frei (`nwz_fulltext_allowed`). Auch aus dem Onboarding entfernt. (#118)

### Geändert
- **Onboarding/Dashboard neu:** statt der NWZ-Verifizierung jetzt einladende „Erste Schritte" zum Kennenlernen der Plattform — Frag den Rat, Beschlüsse durchstöbern, Analyse, Themen-Seiten mit Karten, erstes Thema anlegen, Telegram verbinden. (#118)

## [0.29.2] – 2026-06-26

### Behoben
- Korrekte PLZ (26135) im Impressum + Datenschutz. (#117)

## [0.29.1] – 2026-06-26

### Geändert
- Admins sehen den NWZ-Volltext ohne separate Freischaltung (Admin-Bypass des `nwz_fulltext_allowed`-Gates) — die manuelle Freischaltung gilt für reguläre Nutzer. (#116)

## [0.29.0] – 2026-06-26

### Hinzugefügt
- **Impressum (`/impressum`) und Datenschutzerklärung (`/datenschutz`)** als öffentliche Seiten (vor Login erreichbar; im Footer von Login + eingeloggtem Bereich verlinkt). Pflichtangaben nach § 5 DDG / § 18 MStV bzw. Art. 13 DSGVO (Verarbeiter, KI-Drittland-Hinweis, „nur essenzielles Cookie"). Inhalte sind ein Entwurf und vor dem Öffentlich-gehen anwaltlich zu prüfen. (#115)

### Geändert
- **NWZ-Volltext nur noch für manuell freigeschaltete Nutzer.** Neues Flag `web_users.nwz_fulltext_allowed`; ein Admin schaltet es pro Nutzer im Admin-Bereich frei. Alle anderen sehen nur Überschrift + Metadaten (Suche ohne Text-Auszug, Artikel ohne Volltext) — als Reaktion auf die urheberrechtliche Bewertung. Das Gating wird serverseitig erzwungen; das Frontend zeigt einen Hinweis. (#115)

## [0.28.0] – 2026-06-26

### Geändert
- **Entitäts-Extraktion (`extract_entities`) jetzt inkrementell** statt Voll-Rebuild bei jedem Lauf. NER läuft nur noch über *neue* Beschlüsse; die Roh-Beobachtungen liegen in `council_entity_obs` (append-only, slug-keyed), `council_entity_scanned` merkt bereits gescannte Beschlüsse, und `council_entities`/-links werden daraus ohne LLM neu abgeleitet. Hält die Themen-Seiten/Karten mit neuen Beschlüssen frisch, ohne wöchentlich alles neu zu scannen — und löst das `min_n`-Problem korrekt (eine Entität, die einmal jetzt und einmal später auftaucht, überschreitet die Schwelle, weil die frühe Beobachtung erhalten bleibt). `--full` erzwingt einen kompletten Re-Scan. (#114)

## [0.27.1] – 2026-06-26

### Geändert
- **Anwesenheits-Badges jetzt auch in den Fraktionsfarben.** Auf den Beschluss- und Sitzungs-Detailseiten waren die Partei-Chips in der Anwesenheit noch grau (eigene Spans mit Rohnamen). Jetzt normalisiert („Bündnis 90/Die Grünen" → „Grüne") und brandfarbig wie überall sonst (geteilte `PartyAttendanceBadge`). (#113)

## [0.27.0] – 2026-06-26

### Geändert
- **Partei-Badges in den offiziellen Fraktionsfarben** statt neutraler grauer Chips — eine klare, markengenaue Partei-Identität überall (Personen, Beschlüsse, Analyse). Bewusst die Parteifarbe + das Kürzel, nicht die geschützte Logo-Grafik; lokale Gruppen ohne etablierte Markenfarbe behalten das neutrale Badge. (#112)

## [0.26.0] – 2026-06-26

### Behoben
- **Ratsmitglieder: Fraktionsfilter funktioniert wieder + keine Doppel-Einträge.** Personen wurden je Namens-Schreibweise getrennt geführt („Dr. Hans Hermann Schreier" ≠ „Hans Hermann Schreier"); da der Slug Titel entfernt, kollidierten React-Keys → die Liste filterte nicht mehr. Mandatsträger:innen werden jetzt **per Slug zusammengeführt** (Namensvarianten = eine Person, eindeutige Keys, Sitzungen/Gremien summiert). (#111)

### Geändert
- **FDP/Volt getrennt geführt:** die aufgelöste Gruppe „FDP/Volt" ist keine eigene Fraktion mehr — FDP und Volt erscheinen separat (Gruppen-Einträge zählen zur fortbestehenden FDP). (#111)
- **Disclaimer bei den Ratsmitgliedern:** Hinweis, dass nur Sitzungen ab 2018 erfasst sind. (#111)

## [0.25.0] – 2026-06-26

### Hinzugefügt
- **Admin: LLM-Kosten pro Feature.** Neuer Admin-Tab „LLM-Kosten" listet die Modell-Nutzung je Feature (Protokoll-Extraktion, Themenfeld-Klassifikation, Ziel-Bewertung, Entitäten-Erkennung, Themen-Beschreibungen, Frag-den-Rat …) mit Aufrufen, Input-/Output-Tokens und geschätzten Kosten. Jeder LLM-Aufruf wird best-effort mit einem Feature-Tag in `llm_usage` (nwz.sqlite) erfasst; Kosten aus Token × hinterlegten Modellpreisen. (#110)

## [0.24.1] – 2026-06-26

### Behoben
- **Doppelt gezählte Summen auf den Themen-Seiten:** das erkannte Finanzvolumen einer Entität summierte denselben Vorgang doppelt, wenn er in Ausschuss **und** Rat beschlossen wurde (z. B. Alexanderstraße 600k → fälschlich 1,2 Mio). Jetzt zählen Zwillinge (gleiche Vorlage/Titel) einmal und Buchhaltungsdokumente sind ausgeschlossen — konsistent mit „Größte Finanzbeschlüsse" und „Wofür fließt das Geld?". (#109)

## [0.24.0] – 2026-06-26

### Hinzugefügt
- **Ratsmitglieder-Profile (neuer „Personen"-Bereich in Analyse):** aus den Anwesenheitslisten der Protokolle — ein durchsuchbares Verzeichnis aller Mandatsträger:innen (Fraktion, Sitzungszahl, Gremien), und je Person eine Profilseite mit Fraktion, besuchten Sitzungen, aktivem Zeitraum, Gremien (mit Vorsitz-Kennzeichnung) und den letzten Sitzungen. „Wer vertritt mich?" als neuer Einstieg — gemessen wird die **Präsenz**, nicht das Stimmverhalten (Protokolle nennen namentliche Einzelstimmen selten). (#108)

## [0.23.1] – 2026-06-26

### Behoben
- **Themen-Seiten bleiben automatisch frisch:** die schwereren LLM-/Embedding-Backfills (Entitäten, Beschreibungen, Geocoding, Presse-Links, „Ähnliche Beschlüsse") liefen bisher nur manuell und wären mit neuen Beschlüssen veraltet. Neuer wöchentlicher Cron `weekly_enrich.py` zieht sie nach (So 03:00, jede Stufe unabhängig). (#107)

## [0.23.0] – 2026-06-26

### Geändert
- **Karten auf den Themen-Seiten deutlich aufgewertet:** minimalistische CARTO-Kacheln im Stil der Seite (hell/dunkel, wechseln live mit dem Theme) statt der bunten Standard-OSM-Kacheln; **Straßen werden vollständig** gezeichnet (alle Segmente via Overpass statt nur einem Teilstück von Nominatim); und die Ansicht zoomt bei kleinen Orten/Straßen nicht mehr zu nah heran (maxZoom gesenkt, retina-scharf). (#106)

## [0.22.0] – 2026-06-26

### Geändert
- **UI von 6 auf 4 Tabs konsolidiert.** Die KI-Fragensuche ist jetzt der **„KI-Frage"-Modus** des neuen ersten Tabs **Suche** (neben der Stichwort-Beschlusssuche — beide zeigen dieselben Beschluss-Karten, fühlt sich wie *eine* Suche an). **Ziele** ist eine Unterkategorie von **Analyse** (neben Parteien / Finanzen / Trends). Verbleibende Tabs: **Suche · Sitzungen · Themen · Analyse**, Suche als Standard-Einstieg. Alte Links (`?tab=ask`, `?tab=goals`, `?tab=trends`) leiten automatisch auf ihren neuen Ort um. (#105)

## [0.21.0] – 2026-06-26

### Hinzugefügt
- **Karte auf den Themen-Seiten:** Orte, Straßen und Gebiete werden über OpenStreetMap (Nominatim, auf die Oldenburger Bounding-Box begrenzt) geokodiert und als interaktive Karte gezeigt — mit **eingezeichneter Geometrie**, wo vorhanden (Straßen als Linie, Gebiete wie der Fliegerhorst als Fläche/Polygon), sonst als Punkt. Geo-Daten in `council_entity_meta`; schlanke Leaflet-Einbindung mit OSM-Kacheln (keine externen Skripte, CircleMarker statt Icon-Bildern), client-only geladen. Backfill `geocode_entities.py` (≤ 1 Anfrage/s, eigener User-Agent). (#104)

## [0.20.0] – 2026-06-26

### Hinzugefügt
- **Themen-Seiten mit KI-Beschreibung:** jede Themen-Seite (Fliegerhorst, Klinikum, Nadorster Straße …) bekommt einen kurzen, sachlichen Einführungstext — *was* das Thema ist und *warum* es den Stadtrat beschäftigt, streng aus den zugehörigen Beschlüssen + gesichertem Allgemeinwissen über Oldenburg erzeugt (der Prompt verbietet Spekulation und erfundene Zahlen). Gespeichert in `council_entity_meta` (slug-basiert, überlebt die Entitäten-Neuberechnung). (#103)

## [0.19.1] – 2026-06-26

### Behoben
- **Frag den Rat — Relevanz-Score realistischer kalibriert:** der Cross-Encoder (jina-reranker-v2) gibt negativ-zentrierte Logits aus, weshalb die rohe Sigmoid-Funktion auch klar relevante Treffer mit nur ~50 % zeigte. Ein fester Bias verschiebt das auf eine ehrliche, aber nicht mehr untertriebene Skala (Top-Treffer ~80–90 %). (#102)
- **Presse-Verknüpfung präziser:** ein Beschluss und ein Artikel gelten nur noch als verwandt, wenn sie ein *spezifisches* Kompositum (z. B. „Fliegerhorst", „Klävemann") oder **mindestens zwei** inhaltliche Wörter teilen — vorher reichte ein einzelnes generisches Wort, was thematisch fremde Treffer erzeugte (z. B. „Ausfallbürgschaft → Starkregen", „Wirtschaftsförderung → Trump"). Schwelle leicht angehoben (0,58 → 0,60); erfordert einen `link_news.py`-Neulauf. (#102)

## [0.19.0] – 2026-06-26

### Geändert
- **Frag den Rat — Antwort und Quellen streamen jetzt live (Server-Sent Events):** statt ~7 s Blank-Spinner zeigt die Suche Fortschritts-Schritte (Frage übersetzen → durchsuchen → antworten), blendet die **gefundenen Beschlüsse sofort nach dem Reranking ein** (~2 s) und schreibt die **Antwort Token für Token**. Puffert ein Proxy den Stream, rendert der Client denselben Endzustand am Stück. (#100)
- **Relevanz-Score absolut statt relativ:** der angezeigte Prozentwert ist jetzt die Sigmoid-Funktion des Reranker-Logits (echte Relevanz) statt einer Min-Max-Normalisierung — der schwächste Treffer wird nicht mehr künstlich auf „0 % passend" gedrückt. (#100)
- **Mehr Treffer:** die Fragensuche zeigt bis zu **40** statt 25 Beschlüsse (nahezu irrelevante Tail-Treffer < 10 % werden ausgefiltert). (#100)

### Hinzugefügt
- Live-Ladeindikator mit echtem Arbeitsschritt **und** rotierenden Status-Wörtern; vom Modell zitierte Quellen werden hervorgehoben. (#100)

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
