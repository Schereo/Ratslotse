---
title: Frag den Rat
description: Frageanalyse, hybride Suche, Akten, Antworten mit Quellen und ausführliche Recherche in „Frag den Rat“.
---

„Frag den Rat“ beantwortet Fragen aus dem Bestand: Beschlüsse, Vorlagen,
Wortbeiträge, Pressemitteilungen der Stadt, laufende Beteiligungen und bei
Geldfragen der Haushalt. Die Antwort entsteht nur aus dem, was die Suche
gefunden hat, und nennt ihre Belege. Findet die Suche nichts Tragfähiges,
sagt die Antwort das.

Die Seite ist `/fragen`, der Endpunkt `POST /api/council/ask`. Er antwortet
als Ereignis-Strom: Schritte (`step`), die Quellen (`sources`), der Text in
Stücken (`token`), Folgefragen (`suggestions`) und am Ende `done` mit den
zitierten Beschlüssen. Web und App lesen denselben Strom.

**Der Suchweg** (seit 11/2026): Jeder Schritt meldet, was gerade passiert und
was dabei herauskam: „Beschlüsse durchsuchen“ und darunter „40 Beschlüsse
gefunden: …“, dann Lücken, Anlagen, Presse, Wortbeiträge, Akte, Haushalt, je
nachdem, welche Kanäle die Frage braucht. Die Texte baut der Server
(`council/search_trail.py`) und schickt sie im gewohnten `step`-Rahmen:
`text` öffnet einen Eintrag, `detail` ohne `text` ist das Ergebnis des
zuletzt geöffneten. `step` bleibt eine der drei Phasen `expand`, `search`,
`answer`, die ausgelieferte App liest also weiter nur die Phase. Das Web
zeigt die Liste in der Ladekarte und danach zugeklappt über der Antwort
(`components/suchweg.tsx`). Vorbild war der Ratsinformations-Chatbot der
Stadt Potsdam (siehe [Alternativen](/docs/alternativen/#ris-bot-potsdam)).

Einzelne Aspekte haben eigene Abschnitte auf der Seite
[KI-Pipeline](/docs/ki-pipeline/): die
[Rückfrage bei Fragen ohne Gegenstand](/docs/ki-pipeline/#frag-den-rat-wenn-die-frage-keinen-gegenstand-nennt),
die [Fachwörter](/docs/ki-pipeline/#frag-den-rat-die-fachwörter), die
[Geschäftsordnung](/docs/ki-pipeline/#frag-den-rat-die-geschäftsordnung) und
die [Quellen einer Geldfrage](/docs/ki-pipeline/#frag-den-rat-welche-quelle-eine-geldfrage-zieht).

## Der Weg einer Frage

```
Frage ─► Analyse ─► Suche ─► Zusatzquellen ─► Kontext ─► Antwort ─► Belege
            │                                              ▲
            └─ kein Gegenstand genannt ─► Rückfrage        └─ nur aus dem Kontext
```

**1. Analyse.** Ein kleines Modell (`COUNCIL_QA_EXPAND_MODEL`) macht aus der
Frage, bei Anschlussfragen samt Gesprächsverlauf, eine eigenständige Fassung
und liefert Suchbegriffe, den Fragetyp, eine gegebenenfalls genannte Partei
und die Einschätzung, ob die Frage einen Gegenstand nennt
(`council/qa.py::analyse_query`). Parallel erkennt die Anwendung ohne
Modell eine Ratsperson (`finde_person`), einen Ort aus dem
[Ortskatalog](/docs/adr/0009-zentraler-ortskatalog/) (`finde_ort`), eine
bestimmte Sitzung (`finde_sitzungen`) und bekannte Themen
(`finde_entitaeten`). Diese Erkennung hat Vorrang vor dem Modell.
Nennt die Frage einen Ort aus dem Katalog, beschränkt die Suche die
Treffer auf diesen Ort. Vektor- und Volltextsuche holen dann die besten
Treffer **im** Ort, nicht die besten der ganzen Stadt, die zufällig auch dort
liegen.

Nennt die Frage außer dem Ort kein Thema („Was plant die Stadt für die
Innenstadt?“, „Welche Projekte gibt es in Osternburg?“), ist sie ein
**Ortsüberblick** (`place_overview_question`). Dann ordnet kein Reranker:
Eine Frage ohne Thema ähnelt am meisten den Titeln, die den Ortsnamen tragen,
und das waren bei der Innenstadt vier Beratungen eines Programms von 2021.
`select_place_overview` fasst die Beschlüsse des Orts zu Vorgängen zusammen
(Grundakte, Vorlage, Titelkopf oder Projekt-Entität) und wählt die zwölf
gewichtigsten nach Wichtig-Wert und Frische, je Vorgang höchstens zwei
Beschlüsse. Die Akte entfällt: Sie vertieft einen Vorgang, der Überblick
braucht viele.

**2. Suche.** `council/embeddings.py::hybrid_search` vereinigt drei
Kandidatenmengen:

- Vektor-Treffer zur erweiterten Frage über die Beschlüsse,
- Treffer in den Textstücken der Vorlagen (Sachverhalt und Begründung),
  abgebildet auf deren Beschlüsse,
- Volltext-Treffer (BM25 über SQLite FTS5, siehe
  [ADR 0005](/docs/adr/0005-sqlite-fts5/)).

Ein Cross-Encoder (`COUNCIL_RERANK_MODEL`) ordnet sie gegen die
**ursprüngliche** Frage. Die Paare, die er bewertet, enthalten neben Titel und
Kurzfassung auch Beschlusstext und Vorlagen-Auszug. Vorher bewertete er
Volltexttreffer ohne den zugehörigen Vorlagentext, auch wenn nur dieser mit
der Frage übereinstimmte. Anschließend gewichtet die Anwendung bei Fragen
zum aktuellen Stand jüngere Treffer stärker (`recency_boost`) und begrenzt
Serien wortgleicher Beschlüsse desselben Gremiums (`serien_deckel`).

Embeddings und Reranker laufen lokal (fastembed, ONNX; siehe
[ADR 0003](/docs/adr/0003-fastembed-statt-torch/)). Fehlt der Reranker,
verwendet die Suche die Reihenfolge der Vektortreffer. Ist fastembed nicht
verfügbar, dient die Stichwortsuche als Fallback.
`COUNCIL_RETRIEVAL_KLASSISCH=1` stellt die Suche ohne Vorlagenabschnitte
wieder her. Die Einstellung wirkt ohne Neustart.

**3. Zusatzquellen.** Je nach Frage kommen dazu: Wortbeiträge aus den
Protokollen, Zusagen der Verwaltung, Pressemitteilungen der Stadt, Anlagen
(Gutachten, Konzepte), laufende Bauleitplan-Beteiligungen, die
Geschäftsordnung bei Verfahrensfragen, der Haushalts-Bestand bei Geldfragen
und, hinter dem Schalter `andere-staedte`, Funde aus dem
[Städte-Speicher](/docs/andere-staedte/). Welche Haushalts-Quelle eine
Geldfrage zieht, entscheidet der Wortlaut der Frage und nicht der Fragetyp
des Modells.

**4. Kontext.** Vor dem Antwort-Modell steht, was der Code über den Fund
weiß: wie tragfähig er ist (`beleglage`), wie alt der jüngste Beleg ist und ob
der Rat seitdem getagt hat (`aktenstand`), welche Station einer Vorlage von
einer neueren überholt wurde (`markiere_veraltete`) und was nach dem jüngsten
Beschluss noch auf Tagesordnungen stand (`seither_block`). Der Anlass war
eine echte Frage zu einem Baugebiet: Die Antwort erzählte einen Stand von
Oktober 2018 als Gegenwart, weil der Prompt zwar das heutige Datum kannte,
aber nicht das Alter seiner Belege.

**5. Antwort.** Das Antwortmodell (`COUNCIL_QA_MODEL`) streamt den Text
und zitiert Beschlüsse mit ihrer Kennung. `resolve_citations` löst die
Kennungen auf und verwirft jede, die nicht im Kontext stand. Grafiken zu
Zahlen entstehen aus Rohreihen des Stores (`geld_grafik`), nie aus dem Modell.
Bricht der Stream ab, erzeugt der Fallback die Antwort in einem Stück.

Manche Fragen brauchen kein Modell: „Was wurde zuletzt beschlossen?“ zu einem
Ort (`latest_place_answer`) oder eine Sitzung, zu der es noch kein Protokoll
gibt (`sitzungs_leer_text`), beantwortet der Code.

## Stufen hinter Schaltern

Änderungen an der Suche gelangen mit einem
[Feature-Schalter](/docs/referenz/feature-schalter/) in die
Produktionsumgebung. Dort prüft Ratslotse sie anhand des Gold-Sets, bevor
sie als Standard aktiviert werden. Die Bedingung steht pro Schalter im
Register.

### Themen als Suchhinweis

Schalter `suche-ausbau`. Die Analyse wählt Themen auch dann, wenn die Frage
sie nicht wörtlich nennt (`qa.themen_kandidaten`). Die Beschlüsse dieser
Themen gehen als Hinweis in die Suche. Ein wörtlich genannter Ort filtert zusätzlich auf die
Beschlüsse des gleichnamigen Themas.

### Nachrecherche

Schalter `nachrecherche`. Nach der ersten Suche sieht ein kleines Modell auf
die Titel der Treffer und fragt: Fehlt etwas, wonach die Frage fragt? Dann
sucht der Code bis zu dreimal gezielt nach (`qa.nachrecherche_anfragen`,
`embeddings.nachsuche`) und sortiert die Funde nach ihrem Wert in die erste
Liste ein. Nicht bei Sitzungsfragen: Dort ist die Sitzung aufgelöst, nicht
gesucht.

### Debatten im Prompt: wenige und die richtigen

Schalter `kontext-diaet`. Ohne ihn bekommt das Antwort-Modell alle gefundenen
Wortbeiträge, 50 bis 98 je Frage. Mit ihm höchstens 24, und die Aussprache zu
den Beschlüssen im Prompt zuerst (`qa.debatten_diaet`). Gemessen wird am
Gold-Set, wie oft etwas „im Prompt, aber weggelassen“ war.

## Die Akte

Eine Frage betrifft fast immer einen Vorgang über Jahre: Antrag, Vorberatung,
Ratsbeschluss, Bericht, Protokollnotiz. Die Suche nach ähnlichem Text findet
davon nur, was der Frage ähnlich **klingt**. Die Aussage der Verwaltung zum
Spielplatz am Schlossplatz stand unter dem Tagesordnungspunkt
„Spielleitplanung“ und lag auf Vektor-Rang 310.

**Grundakten** (`council/matters.py`) halten fest, was zusammengehört,
unabhängig davon, wie es klingt. Sie entstehen ohne Sprachmodell, nur über
harte Schlüssel:

1. **Vorlagennummer.** `26/0396`, `26/0396/1` und `26/0396/12` sind eine Akte,
   samt den Beschlüssen aller Gremien, der Beratungsfolge, den
   Tagesordnungspunkten und dem Vorlagen-Text.
2. **Titelkern.** Anträge ohne Vorlagennummer und ihr späterer Bericht tragen
   denselben Kern und landen zusammen.
3. **Teilabstimmungen** gehören zum Beschluss ihres Tagesordnungspunkts.
4. **Wortbeiträge und Protokollnotizen** hängen über Sitzung und Punkt an
   ihrem Beschluss.
5. **Verweise** einer Vorlage auf eine andere werden als Kante gespeichert,
   nicht zusammengelegt. „vgl. 22/1006“ kann Fortsetzung oder Seitenblick sein.

Formalien und Sammelpunkte bekommen keine Akte.

### Akten-Suche

Schalter `akten-suche`. Die besten Treffer der Suche bestimmen die Akte, und
aus ihr kommt zusätzlich, was die Antwort braucht (`council/akte_suche.py`).
Ausgewählt, nicht alles: Eine Akte hat im Schnitt 28 Beschlüsse und 260
Wortbeiträge.

- **Beschlüsse:** die neuesten der Akte. Bei einer Frage nach dem Stand ist
  die letzte Station die Antwort, und genau die verlor gegen ähnlicher
  klingende ältere Treffer.
- **Wortbeiträge:** die der Frage nächsten und dazu immer die jüngsten
  Aussagen der Verwaltung. Zusagen und Protokollnotizen sind kurz und
  nüchtern und verlieren jedes Ranking.
- **Pressemitteilungen:** die neuesten der Akte.

Die Akte ergänzt die bisherigen Kanäle, sie ersetzt sie nicht. Sie bleibt
aus, wenn die Frage eine Sitzung, eine Ratsperson oder das Verfahren meint:
Dort ist nicht nach einem Vorgang gefragt.

### Zeitleiste

Schalter `akten-zeitleiste`, wirkt nur zusammen mit `akten-suche`. Das
Antwort-Modell bekommt den Vorgang als datierte Zeitleiste samt angekündigter
Stationen, erzählt ihn in zeitlicher Folge und nennt den aktuellen Stand.
Lässt die Antwort den Stand aus, hängt der Server ihn an. Unter der Antwort
stehen der Verlauf und die Eckdaten: Abstimmung, Betrag, Stand, nächster
Termin.

`council/datenpruefung.py` prüft die Akten täglich auf Konsistenz.
Verstöße meldet der tägliche Überwachungsjob
([Herzschlag](/docs/betrieb/#der-herzschlag)).

## Ausführliche Recherche

Für Fragen, die mehrere Seiten brauchen, gibt es den Bericht
(`web/backend/app/deepresearch.py`, Endpunkte unter
`/api/council/deep-research`). Der Unterschied zur normalen Frage: Die
Recherche läuft in einem Hintergrund-Thread **weiter**, wenn die Verbindung
abbricht, etwa beim Tabwechsel oder beim Zuklappen des Laptops. Beim erneuten
Verbinden erhält der Client alle bisherigen Stream-Ereignisse erneut.
`deep_research_jobs` speichert den fertigen Bericht über einen Neustart des
Servers hinweg.

Ein Job zerlegt die Frage in drei bis fünf Teilfragen (`qa.deep_zerlege`).
Für jede Teilfrage sucht und liest er zuerst die Zusatzquellen je Kanal und
dann die vollständigen Vorlagenauszüge. Er streamt den Bericht. Jedes Ereignis
enthält die Laufzeit, Fortschrittsereignisse zusätzlich eine geschätzte
Restzeit. „Abbrechen“ wirkt vor dem nächsten Such- oder Modellschritt.
Ergebnisse fertiger Teilfragen bleiben für einen Teilbericht verfügbar.

Das Tageslimit beträgt fünf Recherchen pro Konto. Ratslotse rechnet eine
Recherche an, sobald es den ersten Berichtstext sendet. Ein davor
gescheiterter Versuch zählt nicht. Für den Bericht gilt
`COUNCIL_DEEP_MODEL`. Bleibt die Einstellung leer, verwendet Ratslotse
das Modell für die normale Antwort. Für Konten mit dem Recht
`premium_models` nutzt Ratslotse `COUNCIL_DEEP_PLUS_MODEL`. Das Tageslimit
gilt für beide Modelle
(siehe [Rollen und Rechte](/docs/referenz/rollen-rechte/)). Ohne Einwilligung
ins Speichern löscht `scripts/speicherfristen.py` eine Recherche sieben Tage
nach ihrem letzten Stand.

## Auf der Seite eines Beschlusses oder Punkts

Schalter `beschluss-chat` (Beschluss-Seite) und `punkt-seite`
([Punkt-Seite](/docs/sitzungen/#die-punkt-seite)). Die Antwort entsteht an
Ort und Stelle. Der Client schickt mit, was die Person vor sich hat; daraus
wird ein Block im Prompt (`qa.screen_block`) und eine Zeile für die Analyse
(`qa.seiten_gegenstand`). Der Beschluss hinter der Kennung wird
nachgeschlagen und nie aus dem mitgeschickten Text übernommen
(`qa.screen_decision`). Er steht im Kontext vorn, dazu und nicht statt der
Suche (`qa.mit_gegenstand_zuerst`).

**Vorschlagsfragen** (Schalter `vorschlagsfragen`): Bis 11/2026 standen unter
dem Eingabefeld feste Fragen wie „Was kostet das?“, bei einer
Geschäftsordnung wenig sinnvoll. Jetzt schlägt ein Modell drei Fragen vor,
die zu genau diesem Gegenstand passen und sich aus seinen Unterlagen
beantworten lassen (`council/vorschlagsfragen.py`,
`GET /api/council/page-questions`). Erzeugt wird beim ersten Aufruf der Seite
und dann gespeichert (`page_questions`), neu nur bei geänderten Unterlagen.
Ein Aufruf kostet rund 0,0005 $. Die feste erste Frage „Worum geht es dabei in
einfachen Worten?“ bleibt.

## Modelle und Datenschutz

| Aufgabe | Variable | Vorgabe |
|---|---|---|
| Frage-Analyse, Suchbegriffe, Zerlegen | `COUNCIL_QA_EXPAND_MODEL` | `openai/gpt-5.6-luna` |
| Antwort | `COUNCIL_QA_MODEL` | `openai/gpt-6-luna` |
| Bericht der ausführlichen Recherche | `COUNCIL_DEEP_MODEL` | wie die Antwort |
| derselbe Bericht mit `premium_models` | `COUNCIL_DEEP_PLUS_MODEL` | `openai/gpt-6-sol` |
| Embeddings (lokal) | `COUNCIL_EMBED_MODEL` | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` |
| Reranker (lokal) | `COUNCIL_RERANK_MODEL` | `jinaai/jina-reranker-v2-base-multilingual` |

Eine Frage ist eine Nutzereingabe. Für sie gilt in `kern/llm.py`: kein
Anbieter, der mit den Daten trainiert, kein Anbieter aus China, nie
Stapel- oder Flex-Verarbeitung, und der erste Versuch geht an einen Endpunkt
in der EU. Die Einzelheiten und ihre Geschichte stehen in
[ADR 0002](/docs/adr/0002-dsgvo-provider-routing/).

Text aus dem Bestand ist Fremdtext: Vorlagen und Anträge haben Dritte
geschrieben. `kern/foreign_text.py` entfernt Anweisungen an ein KI-System,
bevor ein Modell den Text sieht.

## Rückmeldungen und Messung

Unter jeder Antwort stehen Daumen und Gründe
(`POST /api/council/qa-feedback`, `council/store_rueckmeldungen.py`).

Gemessen wird gegen ein Gold-Set aus echten Fragen mit geprüften
Soll-Angaben (`scripts/eval_ask_gold.py`, Verlauf in `docs/gold-messbuch.md`),
dazu das Routing der Fragetypen (`eval/run_qa_routing.py`) und die Akten
(`eval/run_akten.py`). Was die Eval-Läufe sonst abdecken, steht unter
[Eval-Harness](/docs/eval/).
