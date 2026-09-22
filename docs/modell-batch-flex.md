# P3 — Batch und Flex, gemessen

Teil des Modellwechsel-Plans (`docs/plan-modellwechsel.md`, lag bei diesem
PR noch nicht auf `dev` — deshalb eine eigene Datei). Frage von Tim: *„Batch
sollten wir auf jeden Fall prüfen, ob das die Kosten günstiger macht, ohne die
Leistungen zu mindern.“*

**Kurz:** Beide Tarife kosten die Hälfte, und die Qualität bleibt gleich.
**Flex** ist dabei der bessere Weg: Er antwortet so schnell wie der normale
Tarif und hängt am vorhandenen Aufrufweg. **Batch** bringt keinen weiteren
Rabatt. Dafür muss man bis zu 24 Stunden auf das Ergebnis warten, kann einen
laufenden Stapel nicht abbrechen, verliert die China-Sperre im Routing, und
die Eingaben liegen 30 Tage bei OpenRouter. Gebaut wurde deshalb nur Flex
(`llm.chat_complete(_tarif="flex")`). Kein Cron ist umgestellt.

Alle Zahlen stammen vom 22.09.2026 (Abend, UTC 20–21 Uhr).

## Gemessen: Golden Set Tragweite

Gemessen am Aufbau von `scripts/eval_impact.py`: 30 handbewertete Beschlüsse
aus `scripts/golden_impact.json`, der Prompt aus `council/impact.py`
(`impact_rating_*`, `reasoning.effort=low`, `temperature=0.1`), in zwei
Stapeln zu 20 und 10 Beschlüssen wie in Produktion. Es gibt also **zwei
Aufrufe je Lauf**. Ausgewertet wird wie im Skript: Spearman ρ über die
Band-Mitten und die Band-Treffer. In `council.sqlite` wird nichts
geschrieben. Die Kosten sind die echten Werte, die OpenRouter liefert
(`usage.cost`, bei Batch das `usage.cost` des Stapels). Sie wurden über
`kern/usage.py` in eine eigene Mess-Datenbank geschrieben.

- **normal** heißt: das Routing, das heute in Produktion läuft (ZDR,
  `data_collection: deny`, China-Liste). Für GPT-6 Luna geht das nicht, weil
  das Modell **keinen ZDR-Endpunkt hat** (404 „No endpoints found matching
  your data policy (Zero data retention)“). Dort bedeutet normal: ohne ZDR,
  der Flex-Endpunkt ist ausgeschlossen.
- **flex** heißt: `service_tier: "flex"` und dasselbe Routing, nur ohne `zdr`.
- **batch** heißt: `POST /api/v1/batches` mit beiden Stapeln als zwei
  Anfragen eines Auftrags.
- **Ausfälle** zählt gescheiterte Anläufe **nach** den vier schnellen Retries
  von `llm._create`. Danach folgt eine Pause von 30 s, dann der nächste
  Versuch. Verloren ging kein Stapel.
- **Listenpreis** heißt: Tokens × Preisliste. Der Unterschied zu den echten
  Kosten ist der Prompt-Cache, denn ab dem zweiten Lauf ist derselbe Prompt
  teils zwischengespeichert.

| Modell | Tarif | Lauf | ρ | Band-Treffer | Dauer | Ausfälle | echte Kosten je Aufruf | Listenpreis je Aufruf |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `openai/gpt-5.6-luna` | normal | 1 | 0.865 | 28/30 | 36 s | 0 | 0.128 ct | 0.149 ct |
| `openai/gpt-5.6-luna` | normal | 2 | 0.858 | 28/30 | 68 s | 1 | 0.104 ct | 0.147 ct |
| `openai/gpt-5.6-luna` | normal | 3 | 0.824 | 25/30 | 28 s | 0 | 0.098 ct | 0.142 ct |
| `openai/gpt-5.6-luna` | normal | 4 | 0.810 | 28/30 | 33 s | 0 | 0.091 ct | 0.134 ct |
| `openai/gpt-5.6-luna` | flex | 1 | 0.888 | 28/30 | 34 s | 0 | 0.076 ct | 0.070 ct |
| `openai/gpt-5.6-luna` | flex | 2 | 0.888 | 28/30 | 32 s | 0 | 0.051 ct | 0.072 ct |
| `openai/gpt-5.6-luna` | flex | 3 | 0.852 | 28/30 | 32 s | 0 | 0.050 ct | 0.072 ct |
| `openai/gpt-5.6-luna` | flex | 4 | 0.842 | 28/30 | 29 s | 0 | 0.048 ct | 0.070 ct |
| `openai/gpt-5.6-luna` | flex | 5 | 0.862 | 27/30 | 29 s | 0 | 0.051 ct | 0.073 ct |
| `openai/gpt-5.6-luna` | batch | 2 | 0.862 | 27/30 | 79 s | 0 | 0.074 ct | 0.074 ct |
| `openai/gpt-6-luna` | normal | 1 | 0.861 | 28/30 | 15 s | 0 | 0.073 ct | 0.067 ct |
| `openai/gpt-6-luna` | normal | 2 | 0.756 | 25/30 | 15 s | 0 | 0.040 ct | 0.062 ct |
| `openai/gpt-6-luna` | normal | 3 | 0.824 | 26/30 | 14 s | 0 | 0.038 ct | 0.060 ct |
| `openai/gpt-6-luna` | normal | 4 | 0.799 | 27/30 | 14 s | 0 | 0.040 ct | 0.062 ct |
| `openai/gpt-6-luna` | flex | 1 | 0.835 | 25/30 | 12 s | 0 | 0.035 ct | 0.032 ct |
| `openai/gpt-6-luna` | flex | 2 | 0.862 | 28/30 | 11 s | 0 | 0.019 ct | 0.030 ct |
| `openai/gpt-6-luna` | flex | 3 | 0.861 | 26/30 | 18 s | 0 | 0.018 ct | 0.029 ct |
| `openai/gpt-6-luna` | flex | 4 | 0.860 | 28/30 | 9 s | 0 | 0.019 ct | 0.030 ct |
| `openai/gpt-6-luna` | flex | 5 | 0.856 | 27/30 | 11 s | 0 | 0.022 ct | 0.033 ct |
| `openai/gpt-6-luna` | batch | 1 | 0.863 | 25/30 | 8.5 min | 0 | 0.027 ct | 0.027 ct |
| `openai/gpt-6-luna` | batch | 2 | 0.775 | 24/30 | 63 s | 0 | 0.019 ct | 0.029 ct |
| `google/gemini-2.5-flash` | normal | 1 | 0.838 | 25/30 | 12 s | 0 | 0.398 ct | 0.398 ct |
| `google/gemini-2.5-flash` | normal | 2 | 0.825 | 26/30 | 12 s | 0 | 0.327 ct | 0.394 ct |
| `google/gemini-2.5-flash` | flex | 1 | 0.822 | 26/30 | 11 s | 0 | 0.196 ct | 0.196 ct |
| `google/gemini-2.5-flash` | flex | 2 | 0.819 | 26/30 | 12 s | 0 | 0.185 ct | 0.198 ct |

„ct“ steht für US-Cent je Aufruf, also je Stapel von 20 bzw. 10 Beschlüssen.

**Mittelwerte:**

| Modell | Tarif | Läufe | ⌀ ρ | ⌀ Treffer | ⌀ echte Kosten/Aufruf | ⌀ Listenpreis/Aufruf | Ausfälle |
|---|---|---:|---:|---:|---:|---:|---:|
| `google/gemini-2.5-flash` | normal | 2 | 0.831 | 25.5/30 | 0.362 ct | 0.396 ct | 0 |
| `google/gemini-2.5-flash` | flex | 2 | 0.821 | 26.0/30 | 0.190 ct | 0.197 ct | 0 |
| `openai/gpt-5.6-luna` | normal | 4 | 0.839 | 27.2/30 | 0.105 ct | 0.143 ct | 1 |
| `openai/gpt-5.6-luna` | flex | 5 | 0.866 | 27.8/30 | 0.055 ct | 0.071 ct | 0 |
| `openai/gpt-5.6-luna` | batch | 1 | 0.862 | 27.0/30 | 0.074 ct | 0.074 ct | 0 |
| `openai/gpt-6-luna` | normal | 4 | 0.810 | 26.5/30 | 0.048 ct | 0.063 ct | 0 |
| `openai/gpt-6-luna` | flex | 5 | 0.855 | 26.8/30 | 0.023 ct | 0.031 ct | 0 |
| `openai/gpt-6-luna` | batch | 2 | 0.819 | 24.5/30 | 0.023 ct | 0.028 ct | 0 |

Gemini 2.5 Flash ist das erste Ersatzmodell von Luna (`llm.ERSATZ`). Auch
dafür gibt es einen Flex-Endpunkt: Google AI Studio antwortete mit
`service_tier: flex` zum halben Preis.

**Was die Tabelle sagt:**

- **Qualität:** Flex liegt bei beiden Luna-Modellen gleichauf mit normal,
  im Mittel sogar leicht vorn. Es ist dasselbe Modell, nur mit anderer
  Warteschlange, und die Unterschiede liegen im Rauschen der Einzelläufe
  (GPT-6 normal: ρ zwischen 0,756 und 0,861). Batch liegt im selben Band.
- **Preis:** Flex und Batch haben **denselben** Listenpreis, beide genau die
  Hälfte. Nachgerechnet an einer Einzelprobe mit identischen Tokens: 4,3e-6
  statt 8,6e-6 $ (Luna 5.6), 1,9e-6 $ (GPT-6 Luna, Flex). Beim Batch mit 100
  Anfragen stimmten 0,00031275 $ auf die sechste Stelle mit Tokens × halbem
  Listenpreis überein. Der Prompt-Cache senkt beide weiter. Einen Vorsprung
  hat Batch nicht.
- **Dauer:** Flex ist nicht langsamer als normal. Luna 5.6 lief im Mittel
  31 s gegen 41 s, GPT-6 Luna 12 s gegen 15 s.
- **Ausfälle:** Flex wurde in **0 von 24 Aufrufen** am Golden Set abgewiesen
  (5 + 5 Läufe Luna, 2 Läufe Gemini, je zwei Aufrufe), dazu 0 von 10
  Einzelproben. Der normale Luna-5.6-Pfad (Azure, ZDR) lief
  dagegen zweimal in „429 temporarily rate-limited upstream“, einmal im
  Vorlauf und einmal in Lauf 2. Das ist die bekannte Welle aus
  `llm.GEDULD_PAUSEN`. Eine Flex-Abweisung ließ sich nicht provozieren. Wie sie
  aussieht, ist deshalb **nicht gemessen**. Der Rückfall ist nur durch Tests
  abgesichert.

## Was die Batch-Schnittstelle kann und was nicht

Quellen sind die Doku ([Batch API Quickstart](https://openrouter.ai/docs/batch-quickstart),
[Ankündigung](https://openrouter.ai/blog/announcements/batch-api/)) und eigene
Probeaufrufe.

| Frage | Befund | Beleg |
|---|---|---|
| Endpunkt, Format | `POST /api/v1/batches` mit `{"endpoint": "/v1/chat/completions", "model", "requests": [{"custom_id", "body"}]}` als Liste im Body. Ein JSONL-Upload entfällt. Antwort: 202, `status: validating` | Doku; Probe: 202 für 1, 10, 100 Anfragen |
| `:batch`-Slug? | Nein. Der Stapel nennt das **normale** Modell, und OpenRouter wählt die `:batch`-Variante selbst (Antwort: `openai/gpt-6-luna-20260922`). Über `chat/completions` antwortet ein `:batch`-Slug mit 404 (Befund aus dem Plan) | Probe |
| Abholen | `GET /api/v1/batches/{id}`, Ergebnisse stehen **inline** im Objekt, sobald `status: completed`. Es gibt keinen eigenen Download | Doku; Probe |
| Dauer | 1 Anfrage: 7,9 min · 10 Anfragen: 9,2 min · 100 Anfragen: 9,5 min (alle GPT-6 Luna) · Golden Set (2 Anfragen): 8,5 min und 63 s (GPT-6), 79 s und über 17 min (Stand bei Redaktionsschluss noch in Arbeit) (Luna 5.6) · Gemini 3.1 Flash Lite (Vertex), 10 Anfragen: über 19 min (noch in Arbeit). OpenRouter selbst nennt über 230.000 Stapel: Median 7 min, p90 1 h, p99 10,3 h, Frist 24 h (die einzige erlaubte) | Probe; Blog |
| Anbieter dahinter | Für Luna **OpenAI** selbst (`provider: OpenAI`, `service_tier: default` im Ergebnis). Ein Stapel läuft immer bei genau einem Anbieter; genannt werden OpenAI, Anthropic, xAI, Mistral, Google Vertex, Google AI Studio, Together, Parasail, DeepInfra und Fireworks. 71 `:batch`-Varianten, darunter **keine** für `deepseek-v4-pro` (nur `deepseek-v4.1-flash:batch`) | Probe; Doku; `/api/v1/models` |
| Routing / DSGVO | **Nur `provider.only`** wird angenommen. `data_collection`, `ignore` und `zdr` weist die Schnittstelle mit 400 ab („provider: Unrecognized keys: "data_collection", "ignore", "zdr"“). Die China-Liste lässt sich also nur über eine **Positivliste** ausdrücken. Laut Doku greifen die Datenschutz-Einstellungen **des Kontos** | Probe; Doku: „after applying your account's provider allowlist, data policy, and BYOK settings“ |
| Speicherung | OpenRouter legt Eingaben und Ergebnisse als JSONL in Google Cloud Storage ab und löscht sie nach **30 Tagen**, oder sofort per `DELETE`. Beim Löschen meldete OpenRouter `"openrouter": "deleted"`, beim Anbieter aber `"upstream": {"provider": "OpenAI", "status": "unsupported"}`, das heißt: bei OpenAI bleibt es liegen | Doku; Probe |
| Kosten je Anfrage | **Fehlen.** Jedes Ergebnis trägt Tokens (`usage.prompt_tokens`, `completion_tokens`, `cached_tokens`), aber kein `cost`. Nur der Stapel als Ganzes trägt `usage.cost` | Probe |
| Abbrechen | **Geht nicht.** `DELETE` auf einen laufenden Stapel liefert 409 („Only completed, failed, expired, or cancelled batches can be deleted“), `POST …/cancel` liefert 404. Ein Stapel, den ein Deploy (`kern/stopp.py`) unterbricht, läuft also weiter und wird bezahlt | Probe; Doku: „It is not cancellation: an in-flight batch returns 409“ |
| Fehler je Anfrage | Jede Anfrage kommt einzeln zurück (`response` oder `error`), ein schlechter Eintrag reißt den Stapel nicht | Doku; Probe: 0 Fehler in 117 Anfragen |

## Was gebaut ist

- **`llm.chat_complete(_tarif="flex")`** in `kern/llm.py`. Der Parameter setzt
  `service_tier: "flex"` und nimmt `zdr` aus dem Routing-Block. Der Grund:
  Mit `zdr: true` ignoriert OpenRouter den Tarif **still**. Luna 5.6 ging
  dann an Azure, mit `service_tier: default` und vollem Preis, und GPT-6
  Luna bekam 404. `data_collection: deny` und die China-Liste bleiben.
  - Für ein Feature, für das `llm.zdr_pflicht(feature)` gilt, wirft der
    Aufruf `FlexNichtErlaubt` und fällt nicht still in den normalen Tarif
    zurück.
  - Weist der Anbieter ab (jeder Fehler außer einem Inhaltsfilter-Treffer),
    läuft derselbe Aufruf noch einmal im normalen Tarif und mit dessen
    Routing. `_geduld` und `_ersatz` greifen danach wie bisher.
  - Modelle ohne Flex-Endpunkt beantwortet OpenRouter im normalen Tarif,
    ohne Fehler. Gemessen an `deepseek-v4-flash`: `service_tier: null`.
- **`llm.zdr_pflicht`** ist vorerst ein **Platzhalter**, der für jedes
  Feature `True` zurückgibt. Die Freigabeliste `OHNE_NUTZEREINGABE` kommt in
  einem eigenen PR. Bis dahin ist Flex **nirgends** erlaubt, und das ist die
  sichere Seite. Beim Zusammenführen gewinnt die Fassung mit der Liste.
- `openai/gpt-6-luna` steht jetzt in `MODEL_PARAMS`, mit demselben Token-Boden
  wie die 5.6-Familie.
- Tests: `tests/test_llm.py` (Flex-Block, Fehler bei ZDR-Pflicht, Rückfall,
  kein Rückfall bei Inhaltsfilter, unbekannter Tarif).

## Was bewusst nicht gebaut ist

- **Kein `kern/llm_batch.py`.** Batch ist genauso teuer wie Flex. Dazu
  kommen Nachteile, die Flex nicht hat:
  - Wartezeit von Minuten bis Stunden statt Sekunden.
  - Kein Abbruch, was nicht zu `kern/stopp.py` passt.
  - Kein `ignore`/`data_collection` im Routing.
  - 30 Tage Speicherung bei OpenRouter, bei OpenAI ohne Löschweg.
  - Keine Kosten je Anfrage.

  Das Modul hätte nur einen Nutzen für Modelle, die einen `:batch`-Endpunkt
  haben, aber keinen Flex-Endpunkt. Unter den Modellen, die hier laufen, ist
  keins so: DeepSeek v4 Pro, der teuerste Posten der Protokoll-Pipeline, hat
  **weder** Flex noch Batch.
- Kein Cron ist umgestellt, kein Modell gewechselt, keine `.env` geändert.
  Kein Nutzerpfad ist angefasst (KI-Frage, Deep, Lotti, Themen, Watcher):
  Diese Pfade haben ZDR-Pflicht, und Flex wirft dort einen Fehler.

## Empfehlung

Flex bietet sich für die Crons an, die heute Luna nutzen und nur öffentliche
Ratsdaten sehen:

- die Tragweite in `check_protocols` und `weekly_enrich` (`impact_rating`,
  `impact_rating_agenda`), hier direkt gemessen
- die Ausschuss-Rückblicke (`committee_summary`)
- die Video-Ergebnisse (`video_results`)
- die Viertel-Projekte (`district_projects`)
- die Social-Texte (`social_card_text`, `social_critic`)

Dasselbe gilt für die Gemini-2.5-Flash-Wortbeiträge (`speeches`). Das spart
dort die Hälfte, und nach dieser Messung verliert die Qualität nichts.
Voraussetzung ist, dass `OHNE_NUTZEREINGABE` diese Features freigibt. Danach
genügt je Aufrufstelle `_tarif="flex"`. Für die Flash-Lite-Modelle (OCR,
Orte) ist nicht geprüft, ob es einen Flex-Endpunkt gibt. Ohne einen solchen
Endpunkt läuft der Aufruf einfach normal. Die Tragweite ist für den Anfang
der sicherste Fall, weil nur für sie ein Golden Set existiert.

Batch lohnt erst, wenn ein teures Modell ohne Flex, aber mit `:batch` in
einen wöchentlichen Nachlauf kommt. Dann gilt das Wochenfenster von
`weekly_enrich` mit `max_age_h` aus `kern/jobs.py`, und Batch darf nur für
öffentliche Daten mit Positivliste im Routing laufen.

**Offen:** Welchen Anteil die Luna- und Gemini-Features an den Modellkosten
haben, zeigt nur das Admin-Panel auf Prod (*Statistik → LLM-Kosten*). Lokal
fehlt `llm_usage`. Erst daraus ergibt sich, was die Hälfte in Euro ausmacht.
Die DeepSeek-Pipelines (Protokolle, Themen) erreicht keiner der beiden Tarife.
