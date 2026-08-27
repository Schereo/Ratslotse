# Ratslotse

Macht die Arbeit des **Oldenburger Stadtrats** durchsuchbar, vergleichbar und
verständlich — über ein Web-Frontend ([ratslotse.de](https://ratslotse.de)) mit
Web-Push- und E-Mail-Benachrichtigungen. Aus dem amtlichen Ratsinformationssystem,
per LLM aufbereitet.

> Diese Datei ist die Kurz-Orientierung für Contributor*innen und Coding-Agents.
> Ausführliche Technik-Doku: [ratslotse.de/docs](https://ratslotse.de/docs)
> (Quelle in `docs-site/`).

## Repo-Struktur

| Pfad | Inhalt |
|------|--------|
| `council/` | Stadtrat-Scraper (SessionNet/Bürgerinfo), Protokoll-Parsing, LLM-Klassifikation, Watcher |
| `kern/` | Geteilte Infrastruktur: LLM-Client (`llm.py`), SQLite-Store (`store.py`), E-Mail, Push, Prompts |
| `scripts/` | Cron-Jobs & Ops-Tools (`check_*.py`, `weekly_enrich.py`, `backup_db.py`, …) |
| `web/backend/` | FastAPI-Backend (uvicorn) |
| `web/frontend/` | Next.js-Frontend (+ Capacitor für iOS/Android); **Designsprache: `web/frontend/DESIGNSPRACHE.md`** |
| `docs-site/` | Astro-Starlight-Technik-Doku |
| `changelog.d/` | Changelog-Fragmente: je PR eine Datei, beim Versionsschnitt eingesammelt (s. u. „Changelog-Pflicht") |
| `eval/` | Eval-Harness für die LLM-Qualität |
| `kommunalwahl/` | Wahlprogramm-Vergleich zur Ratswahl 13.09.2026: Programme, Auswertungen, Thesen-Positionen, fertige Vergleichsseite. Eigenständiger Datenbestand, **noch nicht** ins Backend/Frontend integriert — Einstieg: `kommunalwahl/README.md`, Schnittstelle: `kommunalwahl/data.json` |

## Woher „nwz" noch stammt

Das Paket hieß bis 08/2026 `nwz/` — ein Rest aus der Zeit, als hier ein
Zeitungs-Scraper lief. Der Inhalt hat damit nichts zu tun, deshalb heißt es
jetzt `kern/`.

Drei Stellen tragen den alten Namen bewusst weiter, weil ein Umbenennen dort
Daten oder Betrieb anfasst statt nur Text:

- **`data/nwz.sqlite`** und die Umgebungsvariable **`NWZ_DB`** — der Dateiname
  ist unsichtbar, ein Fehler beim Umstellen hieße „App startet mit leerer
  Datenbank".
- **die systemd-Units** `nwz-web-api` / `nwz-web-frontend` — Umbenennen braucht
  Root auf dem Server und einen Nachzug in `deploy.yml`.
- **`web/frontend/components/nwz-link.tsx`** — der ist kein Rest: Auf
  Beschluss-Seiten steht ein Link zur NWZonline-Suche nach dem jeweiligen Thema.

## Lokale Entwicklung

```bash
# Backend (FastAPI)
python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt -r web/backend/requirements.txt
cd web/backend && ../../.venv/bin/uvicorn app.main:app --reload --port 8000

# Frontend (Next.js)
cd web/frontend && npm install && npm run dev      # :3000, /api/* → Backend

# Technik-Doku (Astro Starlight, Node ≥ 22)
cd docs-site && npm install && npm run dev

# Tests
.venv/bin/pip install -r requirements-dev.txt && .venv/bin/python -m pytest tests/ -q
```

Zwei SQLite-DBs unter `data/` (gitignored): `nwz.sqlite` (Konten, Themen, Prompts)
und `council.sqlite` (Sitzungen, Beschlüsse). Beide werden lokal beim ersten Lauf
angelegt.

## Deployment & Branch-Modell

Gehostet auf einem eigenen VPS (privat). Seit 08/2026 gilt: **`main` ist der
Prod-Stand, `dev` der Integrations-Branch.**

| Was | Wohin | Wie |
|-----|-------|-----|
| **Neues Feature** | PR mit `--base dev` | Squash-Merge; jeder Push auf `dev` deployt auf dev.ratslotse.de |
| **Fix/Hotfix** | PR mit `--base main` | Squash-Merge; deployt sofort auf Prod. Danach `main` nach `dev` zurückmergen (s. u.) |
| **Release** | PR `dev` → `main` | **Merge-Commit, NICHT squashen** — sonst divergieren die Branches dauerhaft. Versionsschnitt (Changelog + Tag) gehört in diesen PR |

**Nur ein gemergter Pull Request nach `main`** löst den Prod-Deploy aus
(`.github/workflows/deploy.yml`, Trigger `pull_request: types:[closed]` +
`merged == true`) — ein direkter Push auf `main` deployt **nicht**. Die Action
baut die Doku, rsync't den Code auf den Server (via SSH-ProxyJump, Ziel-Hosts
als GitHub-Secrets) und startet die systemd-Services neu. Nicht überschrieben
werden `.env`, `data/`, `.venv/`.

**Rückmerge nach jedem Fix auf `main`** (hält den nächsten Release-PR
konfliktfrei, v. a. im Changelog):

```bash
git fetch origin && git checkout dev && git merge origin/main && git push origin dev
```

**Umgebungs-Gate:** Features, die (noch) nicht auf Prod sichtbar sein sollen,
prüfen `process.env.NEXT_PUBLIC_RATSLOTSE_ENV === "dev"` und liefern sonst
`notFound()`. Nur der Dev-Build (`deploy-dev.yml`) setzt die Variable — der
Code darf also gefahrlos mit einem Release nach `main` fahren, die Seite
bleibt dort ein 404.

**GitHub-Secrets:** `SSH_PRIVATE_KEY` (Deploy-Key), `VPS_HOST`, `VPS_DEV_HOST`,
`VPS_PROXY_HOST`, `VPS_USER`, `VPS_SSH_PORT`, `ANTHROPIC_API_KEY` (für `docs-review.yml`),
`CARTO_API_KEY` (Kartenkacheln, s. u.).

**Kartenkacheln brauchen einen Key.** Seit 08/2026 brennt CARTO ein
„API KEY REQUIRED"-Wasserzeichen in jede Kachel, die ohne Key abgerufen wird —
die Karte funktioniert weiter, sieht aber kaputt aus. Beide Deploy-Workflows
reichen `CARTO_API_KEY` als `NEXT_PUBLIC_CARTO_API_KEY` in den `npm run
build`; gebaut wird die URL zentral in
[`web/frontend/lib/basemap.ts`](web/frontend/lib/basemap.ts), **keine
Kachel-URL direkt in eine Komponente schreiben**. Zwei Fallen: Der Parameter
heißt `key`, nicht `api_key` — ein falscher Name liefert Status 200 samt
Wasserzeichen, der Fehler sieht also aus wie „Key wirkt nicht". Und weil
`NEXT_PUBLIC_` zur **Build-Zeit** einkompiliert wird, wirkt ein neuer Key erst
nach einem Neubau, nicht nach einem bloßen Service-Neustart. Lokal gehört der
Key in `web/frontend/.env.local` (gitignored) — ins Repo nie, das ist
öffentlich.

### Dev-Umgebung (dev.ratslotse.de)

Eigene VM neben Prod, mit eigenen Datenbanken/Secrets (Basic-Auth vorm vhost,
kein Mail-Versand, keine Crons). **Jeder Push auf den Branch `dev`** deployt
dorthin (`.github/workflows/deploy-dev.yml`, ohne Test-Gate — die Tests laufen
auf jedem PR). Die Dev-VM zieht per `git fetch` + `reset --hard`, baut
Frontend + Backend-Deps und startet ihre Services neu. Prod bleibt davon
komplett unberührt. **Kein Force-Push auf `dev`** — der Branch trägt seit dem
Umbau gemeinsame Historie; wer einen Wegwerf-Stand testen will, nimmt dafür
einen PR nach `dev` oder fragt Tim.

## `.env` (nur auf dem Server, nicht im Repo)

```
OPENROUTER_API_KEY=...
WEB_JWT_SECRET=...                   # Signiergeheimnis für Session-Tokens
WEB_ADMIN_EMAIL=...                  # wird Admin, sobald diese Adresse registriert *und bestätigt* ist
CORS_ORIGINS=https://ratslotse.de
RESEND_API_KEY=...                   # E-Mail-Versand (Resend), sending-only Key
EMAIL_FROM=Ratslotse <noreply@ratslotse.de>
APP_BASE_URL=https://ratslotse.de
FEEDBACK_EMAIL=...                   # Empfänger des Nutzer-Feedbacks
ALERT_EMAIL=...                      # Cron-Fehler-Alarme (Fallback: WEB_ADMIN_EMAIL)
FASTEMBED_CACHE_PATH=~/.cache/fastembed  # persistenter Modell-Cache (sonst /tmp → weg beim Reboot)
APPLE_BUNDLE_ID=de.ratslotse.app     # Sign in with Apple: aud der nativen App (Default passt)
APPLE_SERVICE_ID=de.ratslotse.web    # Sign in with Apple im Browser (Services ID; leer = Web-Flow aus)
BACKUP_RSYNC_TARGET=user@host:pfad/  # optional: Off-Site-Mirror der DB-Backups
BACKUP_RSYNC_SSH_PORT=22             # SSH-Port des Backup-Ziels
# Stadtrat-LLM (optional, Defaults greifen)
COUNCIL_PROTOCOL_MODEL=deepseek/deepseek-v4-pro
COUNCIL_TOPIC_MODEL=deepseek/deepseek-v4-pro
COUNCIL_GOAL_MODEL=deepseek/deepseek-v4-pro
COUNCIL_EMBED_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
COUNCIL_RECAP_MODEL=deepseek/deepseek-v4-pro
COUNCIL_QA_MODEL=google/gemini-2.5-flash          # Antwort-Modell der KI-Frage (schnell; Default passt)
COUNCIL_QA_EXPAND_MODEL=google/gemini-2.5-flash-lite  # Query-Expansion der KI-Frage (schnell; Default passt)
COUNCIL_RETRIEVAL_KLASSISCH=0        # "1" = Notausschalter: Retrieval-Stand vor dem Vorlagen-Chunk-Ausbau
# OpenRouter Provider-Routing (DSGVO) — schließt China-Anbieter aus, verlangt ZDR
NWZ_OPENROUTER_ROUTING=on            # "off" = Notausschalter
NWZ_OPENROUTER_IGNORE=deepseek,baidu,streamlake,siliconflow,alibaba
NWZ_OPENROUTER_ZDR=1                 # "0" lockert die Zero-Data-Retention-Pflicht
```

## Wissenswertes

- **Designsprache (Pflichtlektüre vor UI-Arbeit):**
  [`web/frontend/DESIGNSPRACHE.md`](web/frontend/DESIGNSPRACHE.md) — Farben,
  Typo, Abstände, wiederkehrende Bausteine, Interaktions-Grammatik und
  Anti-Patterns, destilliert aus den Design-Artboards. Wer einen neuen Screen
  oder eine neue Komponente baut, baut gegen diese Datei; Abweichungen dort
  nachziehen, nicht still danebenlegen.
- **Ersten Admin einrichten:** Die Registrierung vergibt **keine** Rollen (weder
  an `WEB_ADMIN_EMAIL` noch ans erste Konto einer leeren Tabelle) — sonst gehörte
  das Deployment dem, der die Adresse zuerst ins Formular tippt. Die Adresse aus
  `WEB_ADMIN_EMAIL` wird zum Admin, **sobald sie ihre E-Mail bestätigt hat**, und
  auch nur solange es noch gar keinen Admin gibt (ein bewusst degradiertes oder
  gesperrtes Konto holt sich die Rechte so nicht zurück). Ohne `RESEND_API_KEY`
  gibt es keinen Bestätigungslink — dann nach der Registrierung einmal auf dem
  Server: `.venv/bin/python scripts/grant_admin.py <adresse>` (befördert nur ein
  **vorhandenes** Konto). Beide Fälle stehen als WARNING im Log (`nwz-web-api`).
- **Changelog-Pflicht:** Jeder nutzerrelevante PR legt **eine Datei** an:
  `changelog.d/<slug>.md` — Frontmatter `kategorie: hinzugefuegt | geaendert |
  behoben`, darunter der Eintrag im gewohnten Stil (deutsch, fett beginnender
  Kernsatz), **ohne PR-Nummer**:

  ```markdown
  ---
  kategorie: hinzugefuegt
  ---

  **Kernsatz fett.** Dann der Fließtext.
  ```

  Ein Fragment je PR heißt: zwei parallele Zweige fassen nie dieselbe Datei an,
  der Merge kollidiert also nicht mehr im Changelog — und die Nummer muss
  niemand raten (sie existiert beim Schreiben ja noch gar nicht).
  Direkt in `## [Unreleased]` eingetragene Einträge bleiben gültig; beide Wege
  koexistieren, der Schnitt kommt mit beiden zurecht.
  **Versionsschnitt** (gehört in den Release-PR):
  `.venv/bin/python scripts/changelog_schnitt.py x.y.z [--trocken]` — hängt an
  jedes Fragment die PR-Nummer aus dem Squash-Commit, der es angelegt hat,
  sortiert es unter `## [x.y.z] – Datum` in seinen Abschnitt, löscht die
  Fragmente und zieht die Compare-Links am Dateiende nach. Danach annotierten
  Git-Tag `vx.y.z` setzen + pushen. Die Seite ratslotse.de/changelog rendert zur
  Build-Zeit `CHANGELOG.md` **plus** die offenen Fragmente (sie stehen dort
  unter „Unreleased") — für Leser*innen ändert sich dadurch nichts.
- **Keine fremden E-Mail-Adressen im Repo.** Das Repo ist öffentlich; die
  Adresse einer echten Person gehört dort nicht hin — auch nicht „nur als
  Beispiel" in einem Docstring. Für Beispiele und Testfixtures: `example.org`
  (RFC 2606, kann niemandem gehören). `scripts/lint_adressen.py` prüft das und
  läuft in der CI; lokal vorab per `git config core.hooksPath .githooks`.
  **Wird es erst nach dem Push bemerkt, reicht ein Revert nicht** — die Adresse
  bleibt über den alten Commit abrufbar. Dann hilft nur ein History-Rewrite
  (`git filter-repo --replace-text`, Force-Push aller Branches und Tags) **plus**
  eine Anfrage beim GitHub-Support, die Objekte und die betroffenen PR-Ansichten
  zu purgen — ohne diesen zweiten Schritt bleibt sie öffentlich. Der Rewrite
  entfernt außerdem alle GPG-Signaturen und ändert jeden Commit-Hash. Genau das
  ist am 12.08.2026 passiert; der Aufwand ist der Grund für diesen Absatz.
- **Cron-Jobs** (auf dem Server): `backup_db.py` (täglich, mit optionalem
  Off-Site-Mirror per `BACKUP_RSYNC_TARGET`), `check_committees.py`,
  `check_council.py`, `check_protocols.py` (Protokolle → Beschluss-Klassifikation;
  lädt außerdem Vorlagen-Volltexte nach — Sachverhalt/Begründung für
  Beschluss-Seiten, KI-Frage und FTS, `council/vorlagen.py` — erzeugt
  „Lotti erklärt's einfach"-Kurzfassungen für neue Beschlüsse (max. 60/Lauf)
  und bewertet Gesprächswert + Tragweite neuer Beschlüsse (je max. 200/Lauf,
  neueste zuerst) mit anschließender Wichtig-Neuberechnung — so tragen frische
  Beschlüsse ihre Scores tagesaktuell, die weekly-Tranchen bleiben Backstop),
  `weekly_enrich.py` (wöchentliche LLM-/Embedding-Backfills: Entitäten, Geocoding,
  Embeddings, Themen↔Beschlüsse, Themenfeld-Rückblicke, „Einfach erklärt"-
  Bestand in 500er-Tranchen neueste zuerst, Interessantheits-Scores
  (`rate_interest.py`, 500er-Tranchen), Tragweite-Scores (`rate_impact.py`,
  500er-Tranchen — mischt 50/50 in den Wichtig-Wert; Golden-Set-Prüfung:
  `eval_impact.py`) und „Fundstück des Tages"-Karten
  (`generate_fundstuecke.py`, 21 Tage Vorlauf)), `check_vorlage_follows.py`
  (täglich; holt die Beratungsfolge jeder Vorlage, der jemand folgt, und meldet
  neue Stationen bzw. nachgetragene Ergebnisse — Tabelle `vorlage_follows` in
  `nwz.sqlite`), `check_presse.py` (täglich 5:15; Stadt-Quellen: RSS-Abgleich
  der Pressemitteilungen für den „Aktuelles von der Stadt"-Block der KI-Frage
  samt Sofort-Embedding, plus laufende Bauleitplan-Beteiligungen von
  oldenburg.planungsbeteiligung.de für Frist-Banner und KI-Kontext),
  `remind_setup.py`
  (täglich; genau eine Service-Mail an Konten, die den Einrichtungs-
  Assistenten angefangen und seit 48 h nicht beendet haben). Alle laufen in
  `run_guarded` (`kern/alerts.py`): Ein Crash wird geloggt **und** per E-Mail an
  `ALERT_EMAIL`/`WEB_ADMIN_EMAIL` gemeldet. Außerdem protokolliert `run_guarded`
  jeden Lauf in `job_runs` (Dauer, Status, Kennzahlen aus dem Rückgabe-dict der
  `main()`); das Admin-Panel zeigt das unter *Statistik → Cron-Jobs*. Der
  erwartete Takt je Job steht in **`kern/jobs.py`** — wer die crontab ändert,
  zieht ihn dort nach, sonst schlägt die Überfällig-Ampel falsch an.
- **„Ähnliche Beschlüsse"** (`scripts/embed_decisions.py`): berechnet semantische
  Nachbarn per **fastembed** (ONNX, kein torch) — bewusst **nicht** in
  `requirements.txt`, damit Deploy + Web-Service unberührt bleiben.
- **Zustellung**: Nutzer wählen pro Konto `email` / `push` / `both` / `off`
  (`web_users.delivery_channel`). E-Mail über Resend (`kern/email.py`), Push über
  APNs/FCM (`kern/push.py`); ohne `RESEND_API_KEY` wird E-Mail still übersprungen.
  `off` greift in `kern.notify.gewuenscht()`, also **vor** der Warteschlange —
  wer einen neuen Meldeanlass baut, muss ihn über `notify.einreihen` schicken,
  sonst umgeht er Aus-Schalter, Nachtruhe und Tagesgrenze zugleich.
- **Prompts** liegen in `kern/prompts.py` (DB-Tabelle `prompts`) und sind über das
  Admin-UI live editierbar — Defaults greifen, solange kein Override existiert.
- **Sicherheit**: Der Reverse-Proxy setzt `X-Forwarded-For` selbst
  (verhindert Rate-Limit-Bypass via XFF-Spoofing).
