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

## Branch-Modell

Seit 08/2026 ist **`main` der Prod-Stand und `dev` der Integrations-Branch**:

- **Features** gehen per Pull Request nach `dev` (Squash-Merge). Jeder Push
  auf `dev` deployt automatisch auf die Dev-VM — dort reift ein Release-Paket.
- **Fixes** gehen weiterhin einzeln per Pull Request nach `main` (Squash-Merge)
  und erreichen Prod sofort. Danach wird `main` nach `dev` zurückgemergt,
  damit der nächste Release-PR konfliktfrei bleibt:
  `git checkout dev && git merge origin/main && git push origin dev`.
- **Ein Release** ist ein Pull Request `dev` → `main` mit **Merge-Commit**
  (nicht squashen — sonst divergieren die Branches dauerhaft). Der
  Versionsschnitt im Changelog und der Git-Tag gehören in diesen PR
  (siehe [Changelog](#changelog)).
- **Umgebungs-Gate:** Der Dev-Build setzt `NEXT_PUBLIC_RATSLOTSE_ENV=dev`
  (der Prod-Build nicht). Features, die nur auf der Dev-Umgebung sichtbar
  sein sollen, prüfen diese Variable und liefern auf Prod `notFound()` —
  der Code kann so gefahrlos mit einem Release nach `main` fahren.
- **Kein Force-Push auf `dev`:** Der Branch trägt gemeinsame Historie. (Bis
  08/2026 war `dev` ein beweglicher Zeiger, auf den man beliebige Stände
  force-pushen konnte — das gilt nicht mehr.)

## Changelog

Jeder nutzerrelevante Pull Request legt **eine Datei** unter `changelog.d/` an,
statt in `CHANGELOG.md` zu schreiben:

```markdown
---
kategorie: hinzugefuegt   # oder: geaendert | behoben
---

**Kernsatz fett.** Danach der Fließtext, deutsch, ohne PR-Nummer.
```

Der Grund ist ein rein mechanischer: Alle PRs schrieben bisher in dieselben
Zeilen unter `## [Unreleased]`, also kollidierte bei parallelen Zweigen
zuverlässig *jeder* Merge an derselben Stelle. Eine Datei je PR kollidiert nie.
Dazu kommt, dass die PR-Nummer beim Schreiben des Eintrags noch gar nicht
existiert — geraten wurde sie prompt falsch.

**Beim Versionsschnitt** (im Release-PR `dev` → `main`) sammelt
`scripts/changelog_schnitt.py` die Fragmente ein:

```bash
.venv/bin/python scripts/changelog_schnitt.py 1.13.0 --trocken   # anschauen
.venv/bin/python scripts/changelog_schnitt.py 1.13.0             # schreiben
```

Das Skript hängt an jedes Fragment die Nummer des Squash-Commits, der die Datei
angelegt hat (`git log --diff-filter=A`; findet es keine, warnt es und lässt den
Eintrag ohne Nummer), sortiert es unter `## [x.y.z] – Datum` in seinen
Abschnitt, löscht die Fragmente und zieht die Compare-Links am Dateiende nach.

**Nach dem Merge des Release-PRs** wird der annotierte Tag gesetzt — und aus ihm
das GitHub-Release:

```bash
git tag -a v1.13.0 -m "Ratslotse 1.13.0" && git push origin v1.13.0
.venv/bin/python scripts/changelog_schnitt.py 1.13.0 --release \
    --titel "v1.13.0 — Belege bis zur Protokollseite"
```

Der zweite Schritt war bis 09/2026 Handarbeit und fiel dreimal aus: v1.14.0,
v1.15.0 und v2.0.0 lagen als Tags im Repository, ohne dass jemand ein Release
daraus machte — GitHub führt einen bloßen Tag nur unter „Tags", die
Release-Seite zeigte deshalb wochenlang v1.13.2 als neuesten Stand. `--release`
liest den fertigen Abschnitt aus `CHANGELOG.md`, prüft, dass der Tag wirklich
bei `origin` liegt und das Release noch nicht existiert, und legt es über `gh`
an. Zwei Feinheiten: Ist ein Jahrgang zu umfangreich für einen Release-Text —
GitHub nimmt 125.000 Zeichen, der Abschnitt zu 1.14.0 hat 181.451 — gehen statt
eines Fehlers nur die Kernsätze aller Einträge raus, darüber der Verweis auf den
vollständigen Text. Und `--latest` setzt das Skript nur, wenn die Version im
Changelog obenauf steht, damit ein nachgereichtes Release für einen alten Tag
den aktuellen Stand nicht verdrängt.

Von Hand direkt unter `## [Unreleased]` eingetragene Einträge bleiben gültig —
sie wandern beim Schnitt unverändert mit unter die neue Version. `/changelog`
rendert zur Build-Zeit `CHANGELOG.md` **und** die noch offenen Fragmente; für
Leser\*innen sind beide Wege nicht unterscheidbar. Ob alle Fragmente lesbar
sind, prüfen `tests/test_changelog_fragmente.py` und
`scripts/changelog_schnitt.py --pruefen`.

---

## Deploy-Wege

Sechs Workflows in `.github/workflows/`:

| Workflow | Trigger | Was passiert |
|---|---|---|
| `test.yml` | Push auf `main`, jeder Pull Request | Python 3.12, `requirements.txt` + `requirements-dev.txt`, dann `pytest tests/ -q`. |
| `deploy.yml` | `pull_request: types:[closed]` auf `main` mit `merged == true`, zusätzlich `workflow_dispatch` | Test-Gate (derselbe Lauf wie `test.yml`, als harte `needs`-Abhängigkeit), dann Doku-Build, rsync des Codes auf die App-VM (SSH mit ProxyJump über die Edge-VM) und Neustart der beiden systemd-Services. |
| `deploy-dev.yml` | jeder Push auf `dev`, zusätzlich `workflow_dispatch` | Deployt auf die Dev-VM — ohne Test-Gate (siehe unten). |
| `deploy-feature.yml` | jeder Push auf `feature`, zusätzlich `workflow_dispatch` | Deployt auf die **zweite Instanz auf derselben Dev-VM** (eigenes Verzeichnis, eigene Ports, eigene Datenbanken) — ebenfalls ohne Test-Gate. |
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

**Wenn der Merge keinen Deploy auslöst:** Der Workflow lässt sich in der
Actions-UI von Hand starten („Deploy to VPS" → *Run workflow*, Ref `main`) — mit
demselben Test-Gate davor. Der Notausgang stammt vom 26.08.2026: Während einer
GitHub-Actions-Störung fiel das `closed`-Ereignis zweier gemergter PRs ersatzlos
aus, `main` trug den neuen Stand und Prod nicht. Einen Lauf, den es nie gegeben
hat, kann man nicht neu starten; erkennbar ist der Fall daran, dass zum
Merge-Commit gar kein Workflow-Lauf existiert
(`gh api repos/<owner>/<repo>/actions/runs?head_sha=<sha>` bleibt leer).

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

Deployt wird auf **jeden Push auf den Branch `dev`** — im Regelfall also bei
jedem gemergten Feature-PR und bei jedem Rückmerge von `main` (siehe
[Branch-Modell](#branch-modell)). Die VM holt den Stand per `git fetch` +
`git reset --hard <sha>` statt per Merge — robust gegen jede Art von
Branch-Umbau. `.env`, `data/`, `.venv/` und `node_modules/` sind untracked
und bleiben unberührt.

Der Frontend-Build läuft mit `NEXT_PUBLIC_RATSLOTSE_ENV=dev` — das ist das
Umgebungs-Gate, mit dem einzelne Seiten nur auf der Dev-Umgebung sichtbar
sind (der Prod-Build setzt die Variable nicht, dort liefern solche Seiten
`notFound()`). Da `NEXT_PUBLIC_`-Variablen zur Build-Zeit einkompiliert
werden, braucht die Dev-VM dafür keinen `.env`-Eintrag.

Der Lauf hat **kein Test-Gate** (die Tests laufen ohnehin an jedem PR), ein
Kommando-Timeout von 30 Minuten für `npm ci` + `next build` und am Ende zwei
Smoke-Checks gegen Frontend und `/api/health` plus die Rauchprobe. Prod bleibt
davon vollständig unberührt.

Der `concurrency`-Block teilt sich die Gruppe mit dem Feature-Deploy (siehe
[Feature-Umgebung](#feature-umgebung)) und steht auf `cancel-in-progress:
false`. Beide Instanzen liegen auf derselben VM; zwei gleichzeitige
`next build` passen dort nicht nebeneinander, und der OOM-Killer trifft dann
den *laufenden* Dienst der anderen Instanz. Sie bauen deshalb nacheinander,
und keiner der beiden Läufe wird abgebrochen — ein abgebrochener Deploy
hinterließe eine Umgebung auf altem Stand, ohne dass es jemandem auffällt.

---

## Feature-Umgebung

Auf **derselben VM** wie die Dev-Umgebung läuft eine zweite, vollständig
getrennte Instanz für den Branch `feature`. Sie hat ein eigenes
Arbeitsverzeichnis, eigene systemd-Units, eigene Ports, eine eigene `.env`
und **eigene Datenbanken** — dev und feature teilen sich nur die Maschine.

Wozu: `dev` trägt den Stand, der als nächstes nach `main` fährt. Wer etwas
Größeres oder Wackeliges vorzeigen will, ohne diesen Stand anzufassen, mergt
es nach `feature` und zeigt es unter der eigenen Subdomain.

- **Eigene Datenbanken sind der Kern der Trennung.** Ein Feature-Branch
  bringt typischerweise Migrationen mit. Teilte er die Dateien mit dev, zöge
  die erste Migration die Dev-Umgebung mit um — und zurück käme man nur über
  ein Backup. Der Bestand wurde einmalig als konsistenter
  `sqlite3`-Backup-Schnappschuss aus der Dev-Datenbank kopiert.
- **Gleiches Umgebungs-Gate wie dev** (`NEXT_PUBLIC_RATSLOTSE_ENV=dev`) —
  sonst wäre die Instanz für genau die Features blind, für die man sie baut.
- **Basic-Auth vor dem vhost**, kein Mailversand, keine Crons.
- **Kein Force-Push nötig, aber erlaubt:** `feature` ist ein Wegwerf-Zweig.
  Der Deploy holt den Stand per `git fetch` + `git reset --hard <sha>` und
  kommt mit jedem Umbau der Historie zurecht.

Frisch halten heißt: `dev` nach `feature` mergen (nicht umgekehrt). Fertige
Arbeit geht wie immer per Pull Request nach `dev`.

---

## Geplante Jobs (Cron)

Alle Jobs laufen auf der App-VM; maßgeblich ist die dort eingetragene Crontab.
Die Zeitpläne stehen als Docstring im jeweiligen Skript und in
`scripts/README.md`.

| Skript | Rhythmus | Aufgabe |
|---|---|---|
| `backup_db.py` | täglich `0 3 * * *` | SQLite-Backup beider Datenbanken, rotierend, optional off-site gespiegelt. |
| `check_committees.py` | täglich `0 7 * * *` | Gremienliste und Kalender (3 Monate voraus) auffrischen, Terminplan-Sitzungen ohne Tagesordnung mitschreiben, Tagesordnungen zusammenfassen und Ausschuss-Abonnent*innen benachrichtigen (auch bei *geänderter* Tagesordnung, erkannt über einen Agenda-Hash). |
| `check_council.py` | zweimal täglich `0 8,14 * * *` | Kommende Sitzungen gegen die Themen aller Nutzer*innen klassifizieren und Treffer per E-Mail/Push ausliefern. |
| `check_protocols.py` | täglich `0 9 * * *` | Neue Protokolle parsen — und alles Nachgelagerte gleich mit (siehe unten). |
| `weekly_enrich.py` | sonntags `0 3 * * 0` | LLM- und Embedding-Backfills in 14 Schritten (siehe unten). |
| `remind_setup.py` | täglich `0 11 * * *` | Genau eine Service-Mail an Konten, die den Einrichtungs-Assistenten angefangen und seit 48 h nicht beendet haben. |
| `abendmeldungen.py` | täglich `0 18 * * *` | Abend-Anlässe aus Design 30a: N5 Vorabend-Erinnerung täglich, N6 Wochenüberblick nur sonntags. Beide standardmäßig aus — sie erreichen nur, wer sie im Konto einschaltet. |
| `check_finanzdaten.py`&nbsp;¹ | sonntags `0 6 * * 0` | Neue Haushalts-Jahrgänge aus dem Anlagenbestand einlesen (Jahresabschluss, Teilhaushalts-Pläne, Prüfberichte) und melden, wenn ein erwarteter Jahrgang ausbleibt. Lädt nichts herunter, ergänzt nur Fehlendes — siehe [Stadtfinanzen](/docs/haushalt/#der-bereich-hält-sich-selbst-aktuell). |
| `check_beteiligungsbericht.py` | sonntags `30 6 * * 0` | Lädt die Beteiligungsberichte von oldenburg.de und liest Gesellschaften, Aufsichtsorgane und Kennzahlen daraus. Der einzige Haushalts-Cron, der selbst herunterlädt. |
| `archive_statistik.py` | täglich `0 4 * * *` | Sichert die amtlichen Statistik-Quellen versioniert unter `data/archiv/` — siehe unten. |

¹ **Nur auf Prod** — und das ist seit 09/2026 die richtige Seite. Der
Haushalts-Bereich hing bis dahin an einem Umgebungs-Gate und war auf
ratslotse.de unsichtbar; hier stand deshalb das Gegenteil („nur auf der
Dev-VM"). Seit dem Rollen-Umbau hängt er am Recht `budget` und ist dort für
Ratsmitglieder sichtbar (`kern/roles.py`), die Daten sind eingelesen. Auf der
Dev-VM gibt es beide Jobs **nicht**; dort zieht `ops-finanzdaten-ingest.yml`
den Bestand von Hand nach.

Am 03.09.2026 auf dem Server nachgesehen, nachdem hier und in `kern/jobs.py`
jahrelang eine Angabe stand, die nie gestimmt hat: Beide Takte sind
**wöchentlich**, nicht 14-tägig. Was in dieser Tabelle steht, ist eine Kopie
der crontab — und eine Kopie wird nur dann nicht zur Lüge, wenn jemand
nachsieht statt abzuschreiben.

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
`STEPS`-Liste im Skript — sie hat inzwischen 14 Einträge, in dieser Reihenfolge:

1. **Entitäten (NER)** — `extract_entities.py`, baut `council_entities` neu auf.
2. **Beschreibungen** — `describe_entities.py`, füllt fehlende Entitäts-Texte (slug-basiert, überlebt den Rebuild).
3. **Geocoding** — `geocode_entities.py`, verortet neue Orts-Entitäten über Nominatim.
4. **Embeddings / Ähnliche** — `embed_decisions.py`, berechnet „Ähnliche Beschlüsse" neu ([ADR 0003](/docs/adr/0003-fastembed-statt-torch/)).
5. **Verwandte Themen** — `build_entity_relations.py`, berechnet „Hängt zusammen mit …" je Thema (kein LLM). Braucht Schritt 1 und 4.
6. **Themen ↔ Beschlüsse** — `match_topics_decisions.py`, matcht Nutzer-Themen semantisch gegen Beschlüsse.
7. **Themenfeld-Rückblicke** — `generate_field_recaps.py`, erneuert nur veraltete Felder (faktisch ≈ monatlich je Feld).
8. **Einfach erklärt** — `generate_simple_summaries.py`, 500er-Tranche, neueste zuerst.
9. **Personen-Stammdaten** — `backfill_stammdaten.py`, Mandatsträger und Mitgliedschaften aus dem Ratsinfo (kein LLM).
10. **Tragweite** — `rate_impact.py --limit 500`, bewusst *vor* dem Wichtigkeits-Score.
11. **Wichtigkeits-Score** — `score_importance.py`, Heuristik über den Gesamtbestand.
12. **Quizfragen** — `generate_quiz.py`, füllt nur Gebiete unter der Ziel-Fragenzahl auf.
13. **Interessantheit** — `rate_interest.py --limit 500`, neueste zuerst.
14. **Fundstücke** — `generate_fundstuecke.py --days 21`, legt fehlende Kalendertage 21 Tage im Voraus an.

Jeder Schritt läuft **fehlertolerant**: Ein Fehlschlag wird protokolliert und
gemerkt, stoppt aber die übrigen Schritte nicht. Am Ende gibt der Lauf eine
Bilanz („n/14 ok") aus und setzt einen Exit-Code ungleich null, sobald
mindestens ein Schritt gescheitert ist — daraus wird für den Alarmweg eine
Exception erzeugt.

### Fehler-Alarme

Alle Cron-Einstiegspunkte laufen in `run_guarded` aus `kern/alerts.py`. Stürzt
ein Job ab, passiert dreierlei: der Traceback landet im Log (journald bzw.
Cron-Log), eine Alarm-Mail geht an `ALERT_EMAIL` (Fallback `WEB_ADMIN_EMAIL`)
und die Exception wird erneut geworfen, damit Cron einen Exit-Code ungleich
null sieht. Der Mailweg ist strikt best-effort: ohne `RESEND_API_KEY` — oder
wenn der Versand selbst scheitert — bleibt der Alarm im Log, und der
Alarmpfad selbst wirft nie.

---

## Ops-Workflows (manuell auslösbar)

Sechs `ops-*`-Workflows, alle per `workflow_dispatch`. Fünf laufen ohne Inputs mit
festen Befehlen; `ops-entity-dubletten.yml` hat zwei Schalter (siehe Tabelle).
Sie nutzen denselben Deploy-Key und ProxyJump wie `deploy.yml` und führen die
Skripte direkt auf der App-VM aus — praktisch, wenn kein SSH-Zugang zur Hand
ist. Nur Collaborator können sie starten.

| Workflow | Wofür | Idempotent? |
|---|---|---|
| `ops-vorlagen-backfill.yml` | Holt alle fehlenden Vorlagen-Volltexte und Anlagen (inkl. Antragsteller-Erkennung) nach und baut anschließend den FTS-Index neu. Timeout 120 min. | Ja — nur Fehlendes; der Rebuild ist reproduzierbar. |
| `ops-stammdaten-backfill.yml` | Zieht Beratungsfolgen aller eingelesenen Vorlagen sowie Personen- und Gremien-Stammdaten aller Wahlperioden nach. Reines Netz-Parsing, kein LLM. Timeout 120 min. | Ja — die Mitarbeit wird je Person komplett ersetzt. |
| `ops-recaps-regenerieren.yml` | Erzeugt alle Themenfeld-Rückblicke neu (`--force`), sinnvoll nach einer Änderung am Recap-Prompt in `kern/prompts.py` statt bis Sonntag zu warten. Kostet ein paar Cent LLM. | Nein im engeren Sinn — `--force` überschreibt bewusst alle Rückblicke. |
| `ops-quiz-backfill.yml` | Generiert Quizfragen für alle Gebiete (Stadtteile + große Themen) bis zur Ziel-Fragenzahl (`--target 10`), inkl. Verify-Pass. Timeout 60 min. | Ja — nur Gebiete unter Ziel werden aufgefüllt. |
| `ops-tragweite-rollout.yml` | Schaltet den Tragweite-Score erstmals scharf: Voll-Backfill über alle Beschlüsse ohne `impact`, danach Neuberechnung des Wichtigkeits-Scores. | Ja — bewertet nur Beschlüsse ohne Score. |
| `ops-entity-dubletten.yml` | Sucht doppelte Themen (dieselbe Sache unter mehreren Namen) und führt die vom LLM bestätigten zusammen. **Zwei Inputs:** `nur_bericht` (Default `true` → zeigt nur an, schreibt nichts) und `trocken` (mit LLM-Prüfung, ohne zu speichern). Timeout 40 min. | Ja — jede Zusammenführung ist im Admin-Panel einzeln wieder auflösbar. |

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
(`ratslotse.sqlite` und `council.sqlite`) mit der `sqlite3`-Backup-API — also
konsistent, ohne den laufenden Betrieb zu stoppen. Die Kopien landen unter
`data/backups/` mit Datum im Dateinamen.

- **Rotation:** zwei Stufen, `TAEGLICH = 7` und `WOECHENTLICH = 4`. Es bleiben
  die sieben jüngsten Sicherungen, dazu aus jeder der vier Kalenderwochen
  **vor** diesem Fenster die jüngste — zusammen 29 bis 35 Tage Abdeckung.
  Sieben Tage feinkörnig decken „gestern war es noch gut" ab, die Wochenmarken
  alles, was erst später auffällt. Der Zusatz „vor dem Fenster" ist nicht
  kosmetisch: Reicht das Tagesfenster in die Vorwoche hinein, läge deren Marke
  einen Tag neben einem Tagesstand und gewänne keinen Abstand — der Bestand
  endete dann schon nach 22 Tagen.
- **Handkopien bleiben liegen.** Gezählt wird nur, was `<stamm>_JJJJ-MM-TT.sqlite`
  heißt. Eine von Hand gezogene `council_vor_release_v2.0.0.sqlite` fällt aus der
  Rotation heraus: Sie wird nie gelöscht und kostet auch keinen Platz im Bestand.
  Vorher war beides falsch herum — gelöscht wurde `sorted(...)[:-7]`, und weil
  `council_pre_…` alphabetisch hinter `council_2026-…` steht, warfen zwei
  Handkopien vom August zwei Tagesstände hinaus (am 03.09.2026 lagen deshalb nur
  fünf Tagesstände von `council` vor, aber sieben von `nwz`).
- **Off-Site-Mirror (optional):** Ist `BACKUP_RSYNC_TARGET` gesetzt, wird das
  Backup-Verzeichnis anschließend per `rsync -az --delete` gespiegelt; das Ziel
  ist damit ein exaktes Abbild der lokalen Rotation. Eine Kopie gegen
  Serververlust, aber kein Archiv: Was lokal gelöscht wird, ist beim nächsten
  Lauf auch dort weg. Der SSH-Port kommt aus
  `BACKUP_RSYNC_SSH_PORT` (Default `22`), `BatchMode=yes` verhindert
  Passwort-Prompts im Cron. Fehler werfen und landen damit im Alarmweg.
- **Fehlt jede Datenbank**, wirft der Lauf bewusst eine Exception — ein
  stillschweigend leeres Backup gibt es nicht.

Die Datenbankdateien selbst werden vom Deploy **nicht** angefasst: `data/` steht
in der `--exclude`-Liste des rsync, genau wie `.env` und `.venv/`. Ein Deploy
kann den Datenbestand also nicht überschreiben.

**Was noch mitgesichert wird:** Nicht alles unter `data/` steht in einer
Datenbank. `dateien_spiegeln()` legt zwei Ordner per `rsync` in
`data/backups/` und damit in den Off-Site-Spiegel:

| Ordner | Inhalt | Wiederherstellbar? |
|---|---|---|
| `data/plaene/` | gerenderte Planzeichnungen | ja, aber nur über einen Stapellauf über 600 Anlagen |
| `data/archiv/` | Statistik-Archiv (s. u.) | **nein** — die Quellen sind überschrieben |

---

## Statistik-Archiv (`archive_statistik.py`)

**Das Problem:** Die Stadt führt kein Jahrbuch-Archiv. Auf der Übersichtsseite
steht immer nur die *jeweils neueste* Ausgabe jeder Tabelle, der Dateiname
trägt den Jahrgang (`1103-2025-AZ.pdf`), und sobald die nächste Ausgabe
erscheint, ist die alte Adresse ein 404 — nachgemessen am 17.08.2026 an
`1102-2024`, `1103-2024`, `1108-2023`, `1108-2024` und `STJB2024_DS`: alle
weg. Das Internet Archive hat vom Statistik-Verzeichnis der Stadt **null**
Schnappschüsse. Für Tabellen mit nur drei Jahrgängen (1103 Steuern und
Finanzzuweisungen, 0803 Sozialhilfe) ist damit jedes Jahr ein Jahrgang
endgültig verloren. Beim Open-Data-Portal ist es dasselbe, nur leiser: Die
Adressen sind stabil, der Inhalt wird überschrieben.

**Was der Job tut:** Er sichert, er parst nichts. Drei Quellen:

| Bereich | Woher | Umfang (17.08.2026) |
|---|---|---|
| `opendata` | `opendata.oldenburg.de/data.json` und alle darin verlinkten Dateien | 186 Dateien, 10 MB |
| `jahrbuch` | die Übersichtsseite des Statistischen Jahrbuchs, alle Tabellen-PDFs daraus | 246 PDFs, 56 MB |
| `kfa` | die Übersichtsseite des Kommunalen Finanzausgleichs beim LSN | 14 Mappen, 3 MB |

**Keine festen Adresslisten.** Eine feste Liste zeigte nach dem nächsten
Erscheinen auf 404-Adressen und **fände die neue Ausgabe nicht** — sie
versagte genau in dem Moment, für den es den Job gibt. Stabil sind die
Übersichtsseiten, nicht die Dateinamen.

**Wie versioniert wird:**

```
data/archiv/jahrbuch/1103-2025-AZ.pdf/2026-08-17_9f3c1a2b4d5e.pdf
                     └ Ordner heißt wie die Datei ┘ └ Tag ┘└ Hash ┘
```

Datum **und** Hash: Der Hash allein sagte nicht, wann eine Fassung zuerst
auftauchte; das Datum allein legte dieselben Bytes erneut ab, sobald ein
Server seinen `ETag` ohne Inhaltsänderung neu vergibt. Entschieden wird über
den **Inhalts-Hash** — liegt er im Ordner, passiert nichts. Daran hängt die
Idempotenz: Ein zweiter Lauf am selben oder an einem späteren Tag legt nichts
doppelt ab.

`data/archiv/manifest.json` hält je Adresse ETag, `Last-Modified`, Hash, Pfad,
Erst- und Letztsichtung sowie den letzten Fehler. Es liegt bewusst **im
Archiv** statt in der Datenbank: Ein Archiv, dessen Inhaltsverzeichnis
woanders liegt, ist nach einer Wiederherstellung ein Haufen Hashes.

**Warum täglich, wenn sich selten etwas ändert:** Weil die Änderungen in
Schüben kommen (29 Open-Data-Datensätze am 19.06.2026, 20 am 14.07.2026) und
Vorlauf bei einer Quelle ohne Archiv der einzige Puffer ist. Der Preis ist
klein — gemessen:

| Lauf | geladen | Dauer |
|---|---|---|
| erster | 72,4 MB (447 Dateien) | 2:49 min |
| jeder weitere ohne Änderung | 0,0 MB | 34 s |

Möglich macht das ein dreistufiges Sieb: das `modified`-Feld des
Open-Data-Katalogs (kein Abruf), danach `If-None-Match`/`If-Modified-Since`
(304, keine Bytes), zuletzt der Hash. Die LSN-Adressen schicken **weder ETag
noch Last-Modified**; dort greift stattdessen, dass eine Download-Nummer
unveränderlich ist — eine neue Ausgabe bekommt eine neue Nummer, auch eine
Korrektur (KFA 2023 steht als „endgültig Korrektur" neben dem Original).
`--ohne-vorpruefung` schaltet beide Abkürzungen ab, falls sich eine der
Annahmen als falsch erweist.

**Ein 404 beendet den Lauf nicht.** Er wird gezählt, ins Manifest geschrieben
(mit Datum) und einmalig an `ALERT_EMAIL` gemeldet — nicht jeden Tag erneut.
Ein 404 auf eine Jahrbuch-Adresse ist am Erscheinungstag der neuen Ausgabe der
Normalfall; auf eine Open-Data-Adresse ist er es nicht.

---

## LLM-Kosten

Jeder LLM-Aufruf kann seinen Token-Verbrauch protokollieren. `kern/llm.py`
akzeptiert dafür ein Schlüsselwort `_feature="…"`, das vor dem eigentlichen
API-Call herausgezogen wird; `kern/usage.py` schreibt daraus eine Zeile in die
Tabelle `llm_usage` (`ts`, `feature`, `model`, `prompt_tokens`,
`completion_tokens`) in `ratslotse.sqlite`. Die Erfassung ist **best-effort**: Sie
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
hinterlegtem Modellpreis gerechnet. Die Preistabelle `PRICES` in `kern/usage.py`
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
| `COUNCIL_ALIAS_MODEL` | Prüft Themen-Dubletten (`council/aliases.py`) | `deepseek/deepseek-v4-pro` |
| `TOPIC_INTEL_MODEL` | Themen-Beschreibung und Relevanzprüfung (`council/topic_intel.py`) — bricht die `COUNCIL_`-Namenskonvention | `deepseek/deepseek-v4-pro` |

### Web-Backend

| Variable | Wofür | Pflicht | Default |
|---|---|---|---|
| `WEB_JWT_SECRET` | Signiergeheimnis der Session-Tokens | ja | `dev-insecure-change-me` — der Start **bricht ab**, solange der Default steht und `COOKIE_SECURE` an ist; bei ausgeschaltetem `COOKIE_SECURE` nur eine Warnung |
| `WEB_ADMIN_EMAIL` | Diese Adresse wird Admin, sobald sie registriert **und ihre E-Mail bestätigt** hat (nur solange es keinen Admin gibt; ohne Mail-Versand: `scripts/grant_admin.py <adresse>`); Fallback für Alarm- und Feedback-Mails | nein | leer |
| `COOKIE_SECURE` | Session-Cookies nur über HTTPS | nein | `true` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Laufzeit des Web-Cookie-Tokens | nein | `129600` (90 Tage) |
| `SESSION_RENEW_WITHIN_MINUTES` | Ab welcher Restlaufzeit die Sitzung sich still verlängert; `0` schaltet die Verlängerung ab | nein | `64800` (45 Tage) |
| `APP_ACCESS_TOKEN_EXPIRE_MINUTES` | Laufzeit des Tokens nativer Apps | nein | `129600` (90 Tage) |
| `APP_MIN_BUILD` | Kleinste noch zugelassene iOS-Buildnummer; `GET /api/app-config` liefert sie beim App-Start aus | nein | `0` (keine Sperre) |
| `APP_UPDATE_NOTICE` | Optionaler Hinweistext für native Builds, z. B. zu einem empfohlenen Update | nein | leer |
| `CORS_ORIGINS` | Kommaliste erlaubter Web-Origins (in Prod läuft das Frontend same-origin) | nein | `http://localhost:3000` |
| `APP_CORS_ORIGINS` | Feste Origins der Capacitor-Apps, immer zusätzlich erlaubt | nein | `capacitor://localhost,https://localhost` |
| `APPLE_BUNDLE_ID` | Erlaubter `aud`-Wert von „Sign in with Apple" in der nativen App | nein | `de.ratslotse.app` |
| `APPLE_SERVICE_ID` | Services-ID für den Apple-Web-Flow (`aud` des Browser-Tokens). **Leeren schaltet den Web-Login ab** — genau das war der Fehler, den #328 behoben hat. | nein | `de.ratslotse.web` |
| `APPLE_TEAM_ID` | Apple Developer Team-ID; für den Token-Widerruf bei Kontolöschung erforderlich | für App Store | – |
| `APPLE_KEY_ID` | Key-ID des „Sign in with Apple“-Schlüssels | für App Store | – |
| `APPLE_PRIVATE_KEY` | Inhalt des privaten `.p8`-Schlüssels als PEM; escaped `\\n` werden akzeptiert | für App Store | – |
| `LLM_BUDGET_MONTHLY` | Monatsbudget für die Budget-Ampel (reine Anzeige) | nein | `40.0` |
| `DISABLE_RATE_LIMIT` | `1` schaltet das Rate-Limiting ab (nur für Tests) | nein | nicht gesetzt |

### Datenbanken

| Variable | Wofür | Pflicht | Default |
|---|---|---|---|
| `RATSLOTSE_DB` | Pfad zur Konten-/Themen-Datenbank | nein | `data/ratslotse.sqlite` |
| `COUNCIL_DB` | Pfad zur Ratsdaten-Datenbank | nein | `data/council.sqlite` |
| `RATSLOTSE_SQLITE` | Abweichender Pfad für das Usage-Tracking (`kern/usage.py`). **Achtung:** `kern/usage.py` liest ausschließlich diese Variable, der ganze Rest des Projekts `RATSLOTSE_DB`. Wer die Datenbank per `RATSLOTSE_DB` verschiebt, nimmt das Kosten-Tracking **nicht** mit — es schreibt still am alten Ort weiter. Beide zusammen setzen. | nein | `data/ratslotse.sqlite` |
| `SETUP_REMIND_AFTER_HOURS` | Wartezeit, bevor `remind_setup.py` an eine offene Einrichtung erinnert | nein | `48` |

### E-Mail & Benachrichtigung

| Variable | Wofür | Pflicht | Default |
|---|---|---|---|
| `RESEND_API_KEY` | Versand über Resend; fehlt er, wird E-Mail still übersprungen | nein | leer |
| `EMAIL_FROM` | Absender der Mails | nein | `Ratslotse <noreply@ratslotse.de>` |
| `APP_BASE_URL` | Basis-URL in Mail-Links | nein | `https://ratslotse.de` |
| `FEEDBACK_EMAIL` | Empfänger*in des Nutzer-Feedbacks | nein | leer → `WEB_ADMIN_EMAIL` |
| `ALERT_EMAIL` | Empfänger*in der Cron-Alarme | nein | nicht gesetzt → `WEB_ADMIN_EMAIL` |

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
