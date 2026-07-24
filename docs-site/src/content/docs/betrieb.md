---
title: Betrieb
description: Deploy-Wege, Dev-Umgebung, geplante Jobs, manuelle Ops-Workflows, Backups, LLM-Kosten und die vollständige Env-Referenz.
---

Ratslotse läuft auf einer eigenen App-VM hinter einer Edge-VM. Ausgeliefert wird
ausschließlich über GitHub Actions; alles Wiederkehrende (Scraping,
LLM-Anreicherung, Backups) läuft als geplanter Job auf der App-VM. Diese Seite
beschreibt die Betriebsseite: was wann deployt, was wann läuft, was schiefgehen
kann und wie es gemeldet wird.

Konkrete Hosts, Benutzer und Serverpfade stehen bewusst **nicht** in dieser
Doku — sie liegen als GitHub-Secrets bzw. in der `.env` auf dem Server.

---

## Deploy-Wege

Fünf Workflows in `.github/workflows/`:

| Workflow | Trigger | Was passiert |
|---|---|---|
| `test.yml` | Push auf `main`, jeder Pull Request | Python 3.12, `requirements.txt` + `requirements-dev.txt`, dann `pytest tests/ -q`. |
| `deploy.yml` | `pull_request: types:[closed]` auf `main` mit `merged == true` | Test-Gate (derselbe Lauf wie `test.yml`, als harte `needs`-Abhängigkeit), dann Doku-Build, rsync des Codes auf die App-VM (SSH mit ProxyJump über die Edge-VM) und Neustart der beiden systemd-Services. |
| `deploy-dev.yml` | jeder Push auf `dev`, zusätzlich `workflow_dispatch` | Deployt auf die Dev-VM — ohne Test-Gate (siehe unten). |
| `docs.yml` | PR und Push auf `main`, nur bei Änderungen unter `docs-site/**` | Baut die Starlight-Doku und schlägt fehl, wenn sie nicht mehr baut (kaputte Links, Frontmatter, MDX). |
| `docs-review.yml` | PR `opened` / `reopened` / `ready_for_review`, keine Forks | KI-Review, das den Diff auf Doku-Drift prüft und **genau einen** PR-Kommentar postet. Nur `contents: read` — die Action kann nichts committen. `continue-on-error: true`, der Review ist also kein Qualitäts-Gate. |

**Der Prod-Deploy im Detail** (`deploy.yml`, in dieser Reihenfolge):

1. Testjob — schlägt er fehl, läuft der Deployjob gar nicht erst an.
2. `docs-site` mit Node 22 bauen (`npm ci && npm run build`).
3. `rsync -az --delete` des Repos auf die App-VM. Ausgespart bleiben `.env`,
   `data/`, `.venv/`, `.git/`, `web/frontend/node_modules/`,
   `web/frontend/.next/`, `web/frontend/public/docs/`, `docs-site/node_modules/`
   und `docs-site/dist/` — Datenbanken und Secrets überlebt jeder Deploy also
   unverändert.
4. Zweiter rsync: das gebaute `docs-site/dist/` in das `public/docs/`-Verzeichnis
   des Frontends. Next.js liefert die Doku damit unter `/docs` aus; die Edge
   braucht dafür keine eigene Konfiguration.
5. Per SSH auf der App-VM: Backend-Abhängigkeiten nachinstallieren (idempotent),
   `npm ci` + `next build` im Frontend, dann Neustart der Services für
   Backend-API und Frontend.

Warum der Umweg über den gemergten PR statt „Push auf `main` deployt": siehe
[ADR 0008](/docs/adr/0008-deploy-nur-bei-merge/). Kurz — ein direkter Push auf
`main` läuft nur durch die Tests und erreicht die Produktion nicht.

**Verwendete GitHub-Secrets:** `SSH_PRIVATE_KEY` (Deploy-Key), `VPS_HOST`,
`VPS_DEV_HOST`, `VPS_PROXY_HOST`, `VPS_USER`, `VPS_SSH_PORT` sowie
`ANTHROPIC_API_KEY` für `docs-review.yml`. Werte stehen ausschließlich in den
Repository-Secrets.

---

## Dev-Umgebung

Neben der Produktion läuft eine **eigene Dev-VM** mit eigenen Datenbanken und
eigenen Secrets. Sie unterscheidet sich bewusst von Prod:

- **Basic-Auth vor dem vhost** — die Umgebung ist nicht öffentlich erreichbar.
- **Kein Mailversand** — es ist kein Resend-Key hinterlegt, E-Mails werden im
  Code still übersprungen.
- **Keine Crons** — geplante Jobs laufen dort nicht mit; Dev ist zum Anschauen
  da, nicht zum Datensammeln.
- **Eigene Datenbanken und ein eigener OpenRouter-Key**, damit Testläufe weder
  Prod-Daten noch das Prod-Kostenbudget berühren.

Deployt wird auf **jeden Push auf den Branch `dev`**:

```bash
git push origin HEAD:dev --force
```

`dev` ist **kein Integrations-Branch**, sondern ein beweglicher Zeiger auf den
Stand, den man gerade ausprobieren will. Deshalb holt die VM den Stand per
`git fetch` + `git reset --hard <sha>` statt per Merge — Force-Pushes übersteht
sie damit problemlos. `.env`, `data/`, `.venv/` und `node_modules/` sind
untracked und bleiben unberührt.

Der Lauf hat **kein Test-Gate** (die Tests laufen ohnehin an jedem PR nach
`main`), ein `concurrency`-Block mit `cancel-in-progress: true` (bei schnell
aufeinanderfolgenden Pushes gewinnt der neueste), ein Kommando-Timeout von 30
Minuten für `npm ci` + `next build` und am Ende zwei Smoke-Checks gegen
Frontend und `/api/health`. Prod bleibt davon vollständig unberührt.

---

## Geplante Jobs (Cron)

Alle Jobs laufen auf der App-VM; maßgeblich ist die dort eingetragene Crontab.
Die Zeitpläne stehen als Docstring im jeweiligen Skript und in
`scripts/README.md`.

| Skript | Rhythmus | Aufgabe |
|---|---|---|
| `backup_db.py` | täglich `0 3 * * *` | SQLite-Backup beider Datenbanken, rotierend, optional off-site gespiegelt. |
| `check_committees.py` | täglich `0 7 * * *` | Gremienliste und Kalender (3 Monate voraus) auffrischen, Terminplan-Sitzungen ohne Tagesordnung mitschreiben, Tagesordnungen zusammenfassen und Ausschuss-Abonnent:innen benachrichtigen (auch bei *geänderter* Tagesordnung, erkannt über einen Agenda-Hash). |
| `check_council.py` | zweimal täglich `0 8,14 * * *` | Kommende Sitzungen gegen die Themen aller Nutzer:innen klassifizieren und Treffer per E-Mail/Push ausliefern. |
| `check_protocols.py` | täglich `0 9 * * *` | Neue Protokolle parsen — und alles Nachgelagerte gleich mit (siehe unten). |
| `weekly_enrich.py` | sonntags `0 3 * * 0` | LLM- und Embedding-Backfills in 13 Schritten (siehe unten). |

### Was der Protokoll-Lauf inline nachzieht

`check_protocols.py` ist längst mehr als ein Protokoll-Parser: Es ruft die
Sub-Steps direkt als Python-Funktionen auf, jeweils mit einer Obergrenze, damit
der Tageszuwachs abgedeckt ist, ohne dass ein einzelner Lauf entgleist. An
Tagen ohne neue Protokolle sind die LLM-Schritte ein No-op.

| Schritt | Modul | Limit je Lauf |
|---|---|---|
| Protokolle der letzten 90 Tage neu prüfen und parsen | `backfill_protocols.process_range` | Zeitfenster `LOOKBACK_DAYS = 90` |
| Themenfeld-Klassifikation aller noch unklassifizierten Beschlüsse | `classify_decisions.process` | kein Limit (idempotent) |
| Beschlüsse gegen die Stadtziele bewerten, inkrementell | `track_goals.process` | nur noch nicht verknüpfte Paare |
| €-Beträge extrahieren (Regex, kein LLM) | `extract_amounts.process` | nur fehlende |
| „Einfach erklärt"-Kurzfassungen | `generate_simple_summaries.process` | 60 |
| Gesprächswert (Interessantheit) | `rate_interest.process` | 200, 2 Worker |
| Tragweite | `rate_impact.process` | 200, 2 Worker |
| Vorlagen-Volltexte nachladen (Netz + pypdf, kein LLM) | `backfill_vorlagen.process_missing` | 300 |
| Anlagen/Anträge nachladen + jüngste Tagesordnungen erneut scannen | `backfill_anlagen` | 300 (+ Rescan) |
| Beratungsfolge nachziehen + bewegliche Stationen aktualisieren | `backfill_beratungen` | 300 (+ Rescan) |
| Wichtigkeits-Score neu berechnen (Heuristik, kein LLM) | `CouncilStore.backfill_importance` | alle |
| Volltext-Index neu bauen | `CouncilStore.rebuild_fts` | alle |

Die beiden LLM-Scores und die Vorlagen-Abrufe sortieren „neueste zuerst" — das
kleine Limit trifft also zuverlässig den Tageszuwachs. Den historischen Bestand
arbeiten die Wochentranchen ab. Der Wichtigkeits-Score wird bewusst *nach*
der frischen Tragweite gerechnet, damit die 50/50-Mischung sofort greift
(siehe [Bewertungs-Scores](/docs/bewertungen/)).

### Schrittfolge des Wochenlaufs

`weekly_enrich.py` startet seine Schritte als Subprozesse. Maßgeblich ist die
`STEPS`-Liste im Skript — sie hat inzwischen 13 Einträge, in dieser Reihenfolge:

1. **Entitäten (NER)** — `extract_entities.py`, baut `council_entities` neu auf.
2. **Beschreibungen** — `describe_entities.py`, füllt fehlende Entitäts-Texte (slug-basiert, überlebt den Rebuild).
3. **Geocoding** — `geocode_entities.py`, verortet neue Orts-Entitäten über Nominatim.
4. **Embeddings / Ähnliche** — `embed_decisions.py`, berechnet „Ähnliche Beschlüsse" neu ([ADR 0003](/docs/adr/0003-fastembed-statt-torch/)).
5. **Themen ↔ Beschlüsse** — `match_topics_decisions.py`, matcht Nutzer-Themen semantisch gegen Beschlüsse.
6. **Themenfeld-Rückblicke** — `generate_field_recaps.py`, erneuert nur veraltete Felder (faktisch ≈ monatlich je Feld).
7. **Einfach erklärt** — `generate_simple_summaries.py`, 500er-Tranche, neueste zuerst.
8. **Personen-Stammdaten** — `backfill_stammdaten.py`, Mandatsträger und Mitgliedschaften aus dem Ratsinfo (kein LLM).
9. **Tragweite** — `rate_impact.py --limit 500`, bewusst *vor* dem Wichtigkeits-Score.
10. **Wichtigkeits-Score** — `score_importance.py`, Heuristik über den Gesamtbestand.
11. **Quizfragen** — `generate_quiz.py`, füllt nur Gebiete unter der Ziel-Fragenzahl auf.
12. **Interessantheit** — `rate_interest.py --limit 500`, neueste zuerst.
13. **Fundstücke** — `generate_fundstuecke.py --days 21`, legt fehlende Kalendertage 21 Tage im Voraus an.

Jeder Schritt läuft **fehlertolerant**: Ein Fehlschlag wird protokolliert und
gemerkt, stoppt aber die übrigen Schritte nicht. Am Ende gibt der Lauf eine
Bilanz („n/13 ok") aus und setzt einen Exit-Code ungleich null, sobald
mindestens ein Schritt gescheitert ist — daraus wird für den Alarmweg eine
Exception erzeugt.

### Fehler-Alarme

Alle Cron-Einstiegspunkte laufen in `run_guarded` aus `nwz/alerts.py`. Stürzt
ein Job ab, passiert dreierlei: der Traceback landet im Log (journald bzw.
Cron-Log), eine Alarm-Mail geht an `ALERT_EMAIL` (Fallback `WEB_ADMIN_EMAIL`)
und die Exception wird erneut geworfen, damit Cron einen Exit-Code ungleich
null sieht. Der Mailweg ist strikt best-effort: ohne `RESEND_API_KEY` — oder
wenn der Versand selbst scheitert — bleibt der Alarm im Log, und der
Alarmpfad selbst wirft nie.

---

## Ops-Workflows (manuell auslösbar)

Fünf `ops-*`-Workflows, alle per `workflow_dispatch`, ohne Inputs und mit festen
Befehlen.
Sie nutzen denselben Deploy-Key und ProxyJump wie `deploy.yml` und führen die
Skripte direkt auf der App-VM aus — praktisch, wenn kein SSH-Zugang zur Hand
ist. Nur Collaborator können sie starten.

| Workflow | Wofür | Idempotent? |
|---|---|---|
| `ops-vorlagen-backfill.yml` | Holt alle fehlenden Vorlagen-Volltexte und Anlagen (inkl. Antragsteller-Erkennung) nach und baut anschließend den FTS-Index neu. Timeout 120 min. | Ja — nur Fehlendes; der Rebuild ist reproduzierbar. |
| `ops-stammdaten-backfill.yml` | Zieht Beratungsfolgen aller eingelesenen Vorlagen sowie Personen- und Gremien-Stammdaten aller Wahlperioden nach. Reines Netz-Parsing, kein LLM. Timeout 120 min. | Ja — die Mitarbeit wird je Person komplett ersetzt. |
| `ops-recaps-regenerieren.yml` | Erzeugt alle Themenfeld-Rückblicke neu (`--force`), sinnvoll nach Änderungen am admin-editierbaren Recap-Prompt statt bis Sonntag zu warten. Kostet ein paar Cent LLM. | Nein im engeren Sinn — `--force` überschreibt bewusst alle Rückblicke. |
| `ops-quiz-backfill.yml` | Generiert Quizfragen für alle Gebiete (Stadtteile + große Themen) bis zur Ziel-Fragenzahl (`--target 10`), inkl. Verify-Pass. Timeout 60 min. | Ja — nur Gebiete unter Ziel werden aufgefüllt. |
| `ops-tragweite-rollout.yml` | Schaltet den Tragweite-Score erstmals scharf: Voll-Backfill über alle Beschlüsse ohne `impact`, danach Neuberechnung des Wichtigkeits-Scores. | Ja — bewertet nur Beschlüsse ohne Score. |

**Das Golden-Set-Gate im Tragweite-Rollout:** Schritt 1 ist
`scripts/eval_impact.py --rate-missing`. Bestanden ist der Lauf nur bei
Spearman-Rangkorrelation ≥ 0,7 **und** Band-Trefferquote ≥ 70 %. Fällt das Gate
durch, endet es mit Exit 1 und der Workflow bricht ab — der Voll-Backfill
startet dann gar nicht erst, stattdessen ist der Prompt nachzuschärfen. Erst
nach bestandenem Gate startet Schritt 2 den Voll-Lauf; der läuft serverseitig
per `nohup` weiter, während der Workflow selbst schon fertig ist.

---

## Backups

`scripts/backup_db.py` läuft täglich um 03:00 und sichert **beide** Datenbanken
(`nwz.sqlite` und `council.sqlite`) mit der `sqlite3`-Backup-API — also
konsistent, ohne den laufenden Betrieb zu stoppen. Die Kopien landen unter
`data/backups/` mit Datum im Dateinamen.

- **Rotation:** `KEEP = 7` — je Datenbank bleiben die letzten sieben
  Generationen, ältere werden gelöscht.
- **Off-Site-Mirror (optional):** Ist `BACKUP_RSYNC_TARGET` gesetzt, wird das
  Backup-Verzeichnis anschließend per `rsync -az --delete` gespiegelt; das Ziel
  ist damit ein exaktes Abbild der 7-Tage-Rotation. Der SSH-Port kommt aus
  `BACKUP_RSYNC_SSH_PORT` (Default `22`), `BatchMode=yes` verhindert
  Passwort-Prompts im Cron. Fehler werfen und landen damit im Alarmweg.
- **Fehlt jede Datenbank**, wirft der Lauf bewusst eine Exception — ein
  stillschweigend leeres Backup gibt es nicht.

Die Datenbankdateien selbst werden vom Deploy **nicht** angefasst: `data/` steht
in der `--exclude`-Liste des rsync, genau wie `.env` und `.venv/`. Ein Deploy
kann den Datenbestand also nicht überschreiben.

---

## LLM-Kosten

Jeder LLM-Aufruf kann seinen Token-Verbrauch protokollieren. `nwz/llm.py`
akzeptiert dafür ein Schlüsselwort `_feature="…"`, das vor dem eigentlichen
API-Call herausgezogen wird; `nwz/usage.py` schreibt daraus eine Zeile in die
Tabelle `llm_usage` (`ts`, `feature`, `model`, `prompt_tokens`,
`completion_tokens`) in `nwz.sqlite`. Die Erfassung ist **best-effort**: Sie
fängt jede Exception ab, damit Tracking niemals einen LLM-Aufruf kaputt macht —
unter Schreib-Konkurrenz paralleler Backfills bedeutet eine verlorene Zeile
lediglich eine leicht zu niedrige Statistik. Auch der Streaming-Pfad
(`chat_stream`) erfasst mit, indem er den Usage-Chunk anfordert.

Gekennzeichnet sind unter anderem `protokoll_extraktion`,
`themen_klassifikation`, `committee_summary`, `ziel_bewertung`,
`entitaeten_ner`, `entitaeten_beschreibung`, `simple_summary`,
`interest_rating`, `impact_rating`, `fundstueck_story`,
`themenfeld_rueckblick`, `quiz_generation`, `quiz_verify`,
`qa_query_expansion` und `qa_antwort`.

Kosten stehen **nicht** in der Datenbank, sondern werden aus Tokens ×
hinterlegtem Modellpreis gerechnet. Die Preistabelle `PRICES` in `nwz/usage.py`
führt $ je 1 Mio. Tokens (Input, Output) je Modell und muss beim Wechsel auf ein
neues Modell ergänzt werden — ein unbekanntes Modell zählt mit 0,00 $.

Das Backend liefert das Ganze unter `GET /admin/llm-usage` (nur für Admins) aus
`usage.dashboard()`. Der Kosten-Tab im Admin-UI zeigt daraus:

| Kachel | Inhalt |
|---|---|
| Kosten diesen Monat | Summe vom Monatsersten bis heute, plus lineare Hochrechnung auf den vollen Monat |
| Budget-Ampel | Anteil am Monatsbudget in Prozent; `ok` < 80 %, `warn` ab 80 %, `over` ab 100 % |
| Täglicher Kostenverlauf | 30 Tage, lückenlos (Tage ohne Aufrufe erscheinen als 0) |
| Kostentreiber | Aggregat je Feature: Aufrufe, Tokens, geschätzte Kosten, verwendete Modelle, erster/letzter Aufruf — teuerste zuerst |

Das Budget kommt aus der Einstellung `llm_budget_monthly` (Default 40,0). Die
Ampel ist eine reine **Anzeigeschwelle** — sie drosselt nichts und schaltet
nichts ab.

---

## Umgebungsvariablen

Die `.env` liegt ausschließlich auf dem Server und wird vom Deploy nicht
überschrieben. Cron-Skripte laden sie beim Start per `load_dotenv`, das Backend
über `pydantic-settings`.

### LLM & OpenRouter

| Variable | Wofür | Pflicht | Default |
|---|---|---|---|
| `OPENROUTER_API_KEY` | Zugang zu allen LLM-Aufrufen ([ADR 0001](/docs/adr/0001-openrouter/)) | ja | — |
| `NWZ_OPENROUTER_ROUTING` | Provider-Routing (DSGVO) an/aus; `off` ist der Notausschalter ([ADR 0002](/docs/adr/0002-dsgvo-provider-routing/)) | nein | `on` |
| `NWZ_OPENROUTER_IGNORE` | Kommaliste ausgeschlossener Provider-Slugs | nein | `deepseek,baidu,streamlake,siliconflow,alibaba` |
| `NWZ_OPENROUTER_ZDR` | Zero-Data-Retention verlangen; `0`/`false`/`off`/`no` lockert das | nein | `1` |
| `NWZ_DEEPSEEK_MIN_MAX_TOKENS` | Untergrenze für `max_tokens` bei DeepSeek-Reasoning-Modellen | nein | `24000` |

### Modellwahl je Aufgabe

Alle optional — greift keine Variable, gilt der Default aus dem Code.

| Variable | Aufgabe | Default |
|---|---|---|
| `COUNCIL_PROTOCOL_MODEL` | Protokoll-/Beschluss-Extraktion | `deepseek/deepseek-v4-pro` |
| `COUNCIL_PROTOCOL_MAX_CHARS` | Zeichen-Obergrenze je Protokoll-Prompt | `60000` |
| `COUNCIL_TOPIC_MODEL` | Themen-Klassifikation | `deepseek/deepseek-v4-pro` |
| `COUNCIL_GOAL_MODEL` | Bewertung gegen die Stadtziele | `deepseek/deepseek-v4-pro` |
| `COUNCIL_ENTITY_MODEL` | Entitäten-NER und -Beschreibungen | `deepseek/deepseek-v4-pro` |
| `COUNCIL_SIMPLE_MODEL` | „Einfach erklärt"-Kurzfassungen | `deepseek/deepseek-v4-pro` |
| `COUNCIL_INTEREST_MODEL` | Gesprächswert-Score | `deepseek/deepseek-v4-pro` |
| `COUNCIL_IMPACT_MODEL` | Tragweite-Score | `deepseek/deepseek-v4-pro` |
| `COUNCIL_FUNDSTUECK_MODEL` | Story zum „Fundstück des Tages" | `deepseek/deepseek-v4-pro` |
| `COUNCIL_RECAP_MODEL` | Themenfeld-Rückblicke | `deepseek/deepseek-v4-pro` |
| `COUNCIL_QA_MODEL` | „Frag den Rat" (Antwort + Query-Expansion) | `deepseek/deepseek-v4-pro` |
| `COUNCIL_QUIZ_MODEL` | Quizfragen erzeugen | `deepseek/deepseek-v4-pro` |
| `COUNCIL_QUIZ_VERIFY_MODEL` | Verify-Pass über erzeugte Quizfragen | `openai/gpt-4o-mini` |
| `COUNCIL_EMBED_MODEL` | Embeddings (fastembed, lokal) | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` |
| `COUNCIL_RERANK_MODEL` | Reranker für die hybride Suche | `jinaai/jina-reranker-v2-base-multilingual` |

### Web-Backend

| Variable | Wofür | Pflicht | Default |
|---|---|---|---|
| `WEB_JWT_SECRET` | Signiergeheimnis der Session-Tokens | ja | `dev-insecure-change-me` — der Start **bricht ab**, solange der Default steht und `COOKIE_SECURE` an ist; bei ausgeschaltetem `COOKIE_SECURE` nur eine Warnung |
| `WEB_ADMIN_EMAIL` | Diese Adresse wird Admin, sobald sie registriert **und ihre E-Mail bestätigt** hat (nur solange es keinen Admin gibt; ohne Mail-Versand: `scripts/grant_admin.py <adresse>`); Fallback für Alarm- und Feedback-Mails | nein | leer |
| `COOKIE_SECURE` | Session-Cookies nur über HTTPS | nein | `true` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Laufzeit des Web-Cookie-Tokens | nein | `1440` (1 Tag) |
| `APP_ACCESS_TOKEN_EXPIRE_MINUTES` | Laufzeit des Tokens nativer Apps | nein | `129600` (90 Tage) |
| `CORS_ORIGINS` | Kommaliste erlaubter Web-Origins (in Prod läuft das Frontend same-origin) | nein | `http://localhost:3000` |
| `APP_CORS_ORIGINS` | Feste Origins der Capacitor-Apps, immer zusätzlich erlaubt | nein | `capacitor://localhost,https://localhost` |
| `APPLE_BUNDLE_ID` | Erlaubter `aud`-Wert von „Sign in with Apple" in der nativen App | nein | `de.ratslotse.app` |
| `APPLE_SERVICE_ID` | Services-ID für den Apple-Web-Flow; leer = Web-Flow aus | nein | leer |
| `LLM_BUDGET_MONTHLY` | Monatsbudget für die Budget-Ampel (reine Anzeige) | nein | `40.0` |
| `DISABLE_RATE_LIMIT` | `1` schaltet das Rate-Limiting ab (nur für Tests) | nein | nicht gesetzt |

### Datenbanken

| Variable | Wofür | Pflicht | Default |
|---|---|---|---|
| `NWZ_DB` | Pfad zur Konten-/Themen-Datenbank | nein | `data/nwz.sqlite` |
| `COUNCIL_DB` | Pfad zur Ratsdaten-Datenbank | nein | `data/council.sqlite` |
| `NWZ_SQLITE` | Abweichender Pfad für das Usage-Tracking (`nwz/usage.py`) | nein | `data/nwz.sqlite` |

### E-Mail & Benachrichtigung

| Variable | Wofür | Pflicht | Default |
|---|---|---|---|
| `RESEND_API_KEY` | Versand über Resend; fehlt er, wird E-Mail still übersprungen | nein | leer |
| `EMAIL_FROM` | Absender der Mails | nein | `Ratslotse <noreply@ratslotse.de>` |
| `APP_BASE_URL` | Basis-URL in Mail-Links | nein | `https://ratslotse.de` |
| `FEEDBACK_EMAIL` | Empfänger des Nutzer-Feedbacks | nein | leer → `WEB_ADMIN_EMAIL` |
| `ALERT_EMAIL` | Empfänger der Cron-Alarme | nein | nicht gesetzt → `WEB_ADMIN_EMAIL` |

### Push (APNs / FCM)

Push wird pro Plattform still übersprungen, solange deren Variablen unvollständig
sind.

| Variable | Wofür | Pflicht | Default |
|---|---|---|---|
| `APNS_KEY_P8` | APNs-Signaturschlüssel (p8) | für APNs alle vier | — |
| `APNS_KEY_ID` | Key-ID des p8-Schlüssels | für APNs alle vier | — |
| `APNS_TEAM_ID` | Apple-Team-ID | für APNs alle vier | — |
| `APNS_TOPIC` | Push-Topic (Bundle-ID der App) | für APNs alle vier | — |
| `APNS_USE_SANDBOX` | `1` spricht zuerst das Sandbox-Gateway an | nein | nicht gesetzt |
| `FCM_PROJECT_ID` | Firebase-Projekt für Android-Push | für FCM beide | — |
| `FCM_CREDENTIALS` | Pfad zur Service-Account-Datei | für FCM beide | — |

### Backup & Sonstiges

| Variable | Wofür | Pflicht | Default |
|---|---|---|---|
| `BACKUP_RSYNC_TARGET` | Ziel des Off-Site-Mirrors; leer = kein Mirror | nein | leer |
| `BACKUP_RSYNC_SSH_PORT` | SSH-Port des Backup-Ziels | nein | `22` |
| `FASTEMBED_CACHE_PATH` | Persistenter Modell-Cache von fastembed (ohne ihn liegt er im Temp-Verzeichnis und ist nach einem Neustart weg) — von der Bibliothek selbst gelesen, nicht vom Repo-Code | nein | Vorgabe der Bibliothek |

:::tip
Wer nur lokal entwickelt, braucht davon fast nichts: `OPENROUTER_API_KEY` für
echte LLM-Aufrufe, `WEB_JWT_SECRET` plus `COOKIE_SECURE=false` fürs Backend
über HTTP. Alles andere hat brauchbare Defaults.
:::
