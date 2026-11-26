---
title: Betrieb
description: Deploys, Dev-Umgebung, Cron-Jobs, manuelle Betriebsworkflows, Backups, LLM-Kosten und Umgebungsvariablen.
---

Ratslotse läuft auf einer eigenen App-VM hinter einer Edge-VM. GitHub Actions
übernimmt alle Deploys. Wiederkehrende Aufgaben wie Scraping, LLM-Anreicherung
und Backups laufen als geplante Jobs auf der App-VM.

Konkrete Hosts, Benutzer und Serverpfade stehen in den GitHub-Secrets oder
in der `.env` auf dem Server.

---

## Branch-Modell

Seit 08/2026 ist **`main` der Prod-Stand und `dev` der Integrations-Branch**:

- **Features** gehen per Pull Request nach `dev` (Squash-Merge). Jeder Push
  auf `dev` startet einen Deploy auf die Dev-VM. Dort werden die Änderungen
  für den nächsten Release integriert.
- **Fixes** gehen weiterhin einzeln per Pull Request nach `main` (Squash-Merge)
  und lösen sofort einen Deploy in die Produktionsumgebung aus. Der Rückmerge
  von `main` nach `dev` beugt Konflikten im nächsten Release-PR vor.
  `git checkout dev && git merge origin/main && git push origin dev`.
- **Ein Release** ist ein Pull Request `dev` → `main` mit **Merge-Commit**
  (ein Squash-Merge würde die Branches dauerhaft auseinanderlaufen lassen). Der
  Versionsschnitt im Changelog und der Git-Tag gehören in diesen PR
  (siehe [Changelog](#changelog)).
- **Umgebungs-Gate:** Der Dev-Build setzt `NEXT_PUBLIC_RATSLOTSE_ENV=dev`
  (der Prod-Build nicht). Features, die nur auf der Dev-Umgebung sichtbar
  sein sollen, prüfen diese Variable und liefern in der Produktionsumgebung
  `notFound()`. Ihr Code kann daher bereits mit einem Release nach `main`
  gelangen.
- **Kein Force-Push auf `dev`:** Der Branch hat eine gemeinsame Historie.
  Bis 08/2026 waren Force-Pushes auf beliebige Stände von `dev` möglich.

## Changelog

Jeder nutzerrelevante Pull Request legt **eine Datei** unter `changelog.d/` an,
statt in `CHANGELOG.md` zu schreiben:

```markdown
---
kategorie: hinzugefuegt   # oder: geaendert | behoben
---

**Kernsatz fett.** Danach der Fließtext, deutsch, ohne PR-Nummer.
```

Früher änderten alle PRs dieselben Zeilen unter `## [Unreleased]`. Das
führte bei parallelen Zweigen zu Merge-Konflikten. Separate Dateien pro
PR vermeiden diese Konflikte. Die PR-Nummer steht beim Schreiben des
Eintrags noch nicht fest und wurde früher deshalb teils falsch angegeben.

**Beim Versionsschnitt** (im Release-PR `dev` → `main`) sammelt
`scripts/changelog_schnitt.py` die Fragmente ein:

```bash
.venv/bin/python scripts/changelog_schnitt.py 1.13.0 --trocken   # anschauen
.venv/bin/python scripts/changelog_schnitt.py 1.13.0             # schreiben
```

Das Skript ermittelt für jedes Fragment die Nummer aus dem Squash-Commit, der
die Datei angelegt hat (`git log --diff-filter=A`). Fehlt die Nummer, gibt
es eine Warnung aus und übernimmt den Eintrag ohne Nummer. Anschließend
ordnet es die Einträge unter `## [x.y.z] – Datum` ihren Abschnitten zu,
löscht die Fragmente und aktualisiert die Compare-Links am Dateiende.

**Nach dem Merge des Release-PRs** setzt du den annotierten Tag und erstellst
daraus das GitHub-Release.

```bash
git tag -a v1.13.0 -m "Ratslotse 1.13.0" && git push origin v1.13.0
.venv/bin/python scripts/changelog_schnitt.py 1.13.0 --release \
    --titel "v1.13.0 — Belege bis zur Protokollseite"
```

Bis 09/2026 war der zweite Schritt manuell. Für v1.14.0, v1.15.0 und v2.0.0
gab es Tags ohne Releases. GitHub führt solche Tags nur unter „Tags", sodass die
Release-Seite wochenlang v1.13.2 als neuesten Stand zeigte. `--release`
liest den Abschnitt aus `CHANGELOG.md`, prüft, ob der Tag bei `origin`
vorliegt und ob das Release noch fehlt, und legt es über `gh` an.
GitHub akzeptiert bis zu 125.000 Zeichen. Der Abschnitt zu 1.14.0 umfasst
181.451 Zeichen. In solchen Fällen übernimmt das Skript die Kernsätze aller
Einträge und stellt einen Link zum vollständigen Text voran. `--latest`
setzt es nur für die oberste Version im Changelog. Nachträglich angelegte
Releases für ältere Tags ändern so den angezeigten aktuellen Stand nicht.

Manuelle Einträge unter `## [Unreleased]` bleiben gültig. Beim
Versionsschnitt übernimmt das Skript sie unverändert in die neue Version.
`/changelog` rendert zur Build-Zeit sowohl `CHANGELOG.md` als auch die
offenen Fragmente in derselben Darstellung. Ob alle Fragmente lesbar
sind, prüfen `tests/test_changelog_fragmente.py` und
`scripts/changelog_schnitt.py --pruefen`.

---

## Deploy-Wege

Die wichtigsten Workflows in `.github/workflows/`:

| Workflow | Trigger | Was passiert |
|---|---|---|
| `test.yml` | Push auf `main`, jeder Pull Request | Python 3.12, `requirements.txt` + `requirements-dev.txt`, dann `pytest tests/ -q`. |
| `deploy.yml` | `pull_request: types:[closed]` auf `main` mit `merged == true`, zusätzlich `workflow_dispatch` | Test-Gate (derselbe Lauf wie `test.yml`, als harte `needs`-Abhängigkeit), dann Doku-Build, rsync des Codes auf die App-VM (SSH mit ProxyJump über die Edge-VM) und Neustart der beiden systemd-Services. |
| `deploy-dev.yml` | jeder Push auf `dev`, zusätzlich `workflow_dispatch` | Deployt auf die Dev-VM — ohne Test-Gate (siehe unten). |
| `docs.yml` | PR und Push auf `main`, nur bei Änderungen unter `docs-site/**` | Baut die Starlight-Doku und schlägt fehl, wenn sie nicht mehr baut (kaputte Links, Frontmatter, MDX). |
| `docs-review.yml` | PR `opened` / `reopened` / `ready_for_review`, keine Forks | KI-Review, das den Diff auf Doku-Drift prüft und **genau einen** PR-Kommentar postet. Nur `contents: read` — die Action kann nichts committen. `continue-on-error: true`, der Review ist also kein Qualitäts-Gate. |
| `claude.yml` | `@claude` in einem PR-Kommentar, Review oder Zeilenkommentar — nur von Konten mit Schreibrecht | Code-Review auf Zuruf: Claude liest den Diff und antwortet mit Inline-Kommentaren und einer Zusammenfassung. Bezahlt aus dem Claude-Abo (`CLAUDE_CODE_OAUTH_TOKEN`), nicht über die API. Nur `contents: read` — Claude kann nicht pushen. |

Der **Produktionsdeploy** läuft in `deploy.yml` in der folgenden Reihenfolge.

1. Der Deploy-Job startet nur, wenn der Testjob erfolgreich war.
2. `docs-site` mit Node 22 bauen (`npm ci && npm run build`).
3. `rsync -az --delete` des Repos auf die App-VM. Ausgespart bleiben `.env`,
   `data/`, `.venv/`, `.git/`, `web/frontend/node_modules/`,
   `web/frontend/.next/` (samt `.next-build/` und `.next-alt/`, s. Schritt 5),
   `web/frontend/public/docs/`, `docs-site/node_modules/` und `docs-site/dist/`. Die Ausschlussliste schützt Datenbanken und Secrets beim Deploy.
4. Zweiter rsync: das gebaute `docs-site/dist/` in das `public/docs/`-Verzeichnis
   des Frontends. Next.js liefert die Doku damit unter `/docs` aus; die Edge
   braucht dafür keine eigene Konfiguration.
5. Per SSH auf der App-VM: Backend-Abhängigkeiten nachinstallieren (idempotent),
   `npm ci` + `next build` im Frontend, dann Neustart der Services für
   Backend-API und Frontend.

**Das Frontend wird neben dem laufenden Server gebaut** (seit 11/2026, in
beiden Deploys gleich). `next build` leert zuerst sein Ausgabeverzeichnis.
Bei einem Build direkt in `.next` fehlten dem laufenden `next start`
vorübergehend CSS und Skripte. Bis zum Neustart wurden die Seiten rund
eine Minute lang ohne Gestaltung ausgeliefert. Der Deploy verwendet
deshalb ein separates Build-Verzeichnis.

1. `rm -rf .next-build`, dann `NEXT_DIST_DIR=.next-build npm run build`
   (`next.config.mjs` nimmt die Variable nur in der Build-Phase). Jeder Build
   beginnt leer, **ohne Webpack-Cache**: Der Cache führte zweimal zu inkonsistenten
   Build-Ergebnissen und spart auf der Dev-VM nur 10–25 Sekunden.
2. `scripts/pruefe_build_chunks.py web/frontend/.next-build` prüft, ob
   alle verlinkten Dateien existieren und ob das verlinkte CSS jede
   next/font-Klasse des Elements `<html>` definiert. Schlägt die
   Prüfung fehl, bleibt `.next` unverändert.
3. Unmittelbar vor dem Neustart des Frontends: `.next` → `.next-alt`,
   `.next-build` → `.next`, `systemctl restart`, dann `.next-alt` löschen.

In der Produktionsumgebung folgt Schritt 3 auf Migration und Vorprobe.
Bricht der Deploy vorher ab, läuft das Frontend mit dem bisherigen Build
weiter. Den neuen Build mit der Markierung `.geprueft` kann
`ops-wartungsbarriere.yml` über die Aktion `frontend-restart` aktivieren.

[ADR 0008](/docs/adr/0008-deploy-nur-bei-merge/) begründet, warum ein
gemergter PR nach `main` den Deploy auslöst. Ein direkter Push auf
`main` startet nur die Tests.

**Wenn der Merge keinen Deploy auslöst:** Der Workflow lässt sich in der
Actions-UI von Hand starten („Deploy to VPS" → *Run workflow*, Ref `main`) — mit
derselben vorgeschalteten Testprüfung. Der manuelle Start ist seit 26.08.2026
möglich. Während einer GitHub-Actions-Störung fehlte das `closed`-Ereignis
zweier gemergter PRs. `main` war dadurch aktueller als die
Produktionsumgebung. In diesem Fall existiert zum Merge-Commit kein
Workflow-Lauf, den du erneut starten könntest
(`gh api repos/<owner>/<repo>/actions/runs?head_sha=<sha>` bleibt leer).

**Verwendete GitHub-Secrets:** `SSH_PRIVATE_KEY` (Deploy-Key), `VPS_HOST`,
`VPS_DEV_HOST`, `VPS_PROXY_HOST`, `VPS_PROXY_USER`, `VPS_USER`, `VPS_SSH_PORT`,
`VPS_KNOWN_HOSTS` (Host-Schlüssel, s. Ops-Workflows) sowie
`ANTHROPIC_API_KEY` für `docs-review.yml` und `CLAUDE_CODE_OAUTH_TOKEN`
(aus `claude setup-token`, ein Jahr gültig) für `claude.yml`. Werte stehen ausschließlich in den
Repository-Secrets.

---

## Dev-Umgebung

Neben der Produktion läuft eine **eigene Dev-VM** mit eigenen Datenbanken und
eigenen Secrets. Sie unterscheidet sich bewusst von Prod:

- **Öffentlich erreichbar seit 10/2026.** Die Dev-Umgebung verlangt keine
  Basic-Auth. Für die reguläre Registrierung setzt Dev
  `SIGNUP_REQUIRES_APPROVAL=1`. Neue Konten aus diesem Registrierungsweg
  bleiben bis zur Freischaltung im Admin-Panel gesperrt. Der Dev-Build
  sperrt Crawling über `robots.ts`. Caddy setzt zusätzlich
  `X-Robots-Tag: noindex`.
- **Kein Mailversand.** Ohne Resend-Key überspringt Ratslotse die Zustellung
  ohne Fehlermeldung.
- **Keine Cron-Jobs.** Die Dev-Umgebung dient der Vorschau und erfasst keine
  neuen Daten über geplante Jobs.
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

Der `concurrency`-Block setzt `cancel-in-progress: false`. Damit laufen
Deploys nacheinander bis zum Ende. Ein Abbruch zwischen Build und Neustart
könnte unbemerkt eine nur teilweise aktualisierte Umgebung hinterlassen.

Bis 11/2026 lief auf derselben VM eine zweite Instanz für den Branch
`feature` (feature.ratslotse.de) und ein Datenbank-Betrachter
(db.dev.ratslotse.de). Beide sind abgebaut; was auf Prod noch nicht sichtbar
sein soll, liegt hinter einem Feature-Schalter.

---

## Geplante Jobs (Cron)

Alle Jobs laufen auf der App-VM; maßgeblich ist die dort eingetragene Crontab.
Die Statusanzeige im Admin-Panel und `check_herzschlag.py` nutzen die
Intervalle aus `kern/jobs.py`. Aus derselben Datei entsteht die
[Referenz: Cron-Jobs](/docs/referenz/cron-jobs/). Die Tabelle unten enthält
zusätzlich die Crontab-Einträge und weitere Details. `tests/test_docs_current.py`
prüft, ob jeder Job in der Tabelle steht.

| Skript | Rhythmus | Aufgabe |
|---|---|---|
| `backup_db.py` | täglich `0 3 * * *` | SQLite-Backup aller Datenbanken samt `.env`, crontab und unersetzlicher Dateien, rotierend, off-site gespiegelt. |
| `check_committees.py` | täglich `0 7 * * *` | Gremienliste und Kalender (3 Monate voraus) auffrischen, Terminplan-Sitzungen ohne Tagesordnung mitschreiben, Tagesordnungen zusammenfassen und Ausschuss-Abonnent*innen benachrichtigen (auch bei *geänderter* Tagesordnung, erkannt über einen Agenda-Hash). |
| `check_council.py` | zweimal täglich `0 8,14 * * *` | Kommende Sitzungen gegen die Themen aller Nutzer*innen klassifizieren und Treffer per E-Mail/Push ausliefern. |
| `check_protocols.py` | täglich `0 9 * * *` | Neue Protokolle parsen — und alles Nachgelagerte gleich mit (siehe unten). |
| `weekly_enrich.py` | sonntags `0 3 * * 0` | Nachläufe mit und ohne Modell in 23 Schritten (siehe unten). |
| `remind_setup.py` | täglich `0 11 * * *` | Genau eine Service-Mail an Konten, die den Einrichtungs-Assistenten angefangen und seit 48 h nicht beendet haben. |
| `abendmeldungen.py` | täglich `0 18 * * *` | Abend-Anlässe aus Design 30a: N5 Vorabend-Erinnerung täglich, N6 Wochenüberblick nur sonntags. N5 ist standardmäßig aus, N6 seit 09/2026 für neue Konten an. |
| `check_finanzdaten.py`&nbsp;¹ | sonntags `0 6 * * 0` | Neue Haushalts-Jahrgänge aus dem Anlagenbestand einlesen (Jahresabschluss, Teilhaushalts-Pläne, Prüfberichte) und melden, wenn ein erwarteter Jahrgang ausbleibt. Lädt nichts herunter, ergänzt nur Fehlendes — siehe [Stadtfinanzen](/docs/haushalt/#aktualisierung-der-haushaltsdaten). |
| `check_beteiligungsbericht.py` | sonntags `30 6 * * 0` | Lädt die Beteiligungsberichte von oldenburg.de und liest Gesellschaften, Aufsichtsorgane und Kennzahlen daraus. Der einzige Haushalts-Cron, der selbst herunterlädt. |
| `archive_statistik.py` | täglich `0 4 * * *` | Sichert die amtlichen Statistik-Quellen versioniert unter `data/archiv/` — siehe unten. |
| `check_vorlage_follows.py` | täglich `30 9 * * *` | Neue Beratungsstationen und nachgetragene Ergebnisse zu Vorlagen, denen jemand folgt. |
| `vorlagen_dossiers.py` | zweimal täglich `0 10,15 * * *` | Dossiers für die Vorlagen der nächsten 21 Tage: ein Modellaufruf je Vorlage, jede Aussage gegen die Quelle geprüft ([Sitzung & Tagesordnungspunkt](/docs/sitzungen/#aus-den-unterlagen-das-dossier)). Mit den Schaltern dazu auch Fachwörter und Wahlprogramm-Einordnungen. Je Teil eine Kostengrenze je Lauf. |
| `antraege_nachzuegler.py` | viermal täglich `0 11,13,16,18 * * *` | An Sitzungstagen und am Tag davor: Tagesordnung neu lesen, neue Änderungsanträge laden und lesen. An anderen Tagen tut er nichts. |
| `check_council_videos.py` | täglich `30 10 * * *` | Abstimmungsergebnisse aus der O1-Aufzeichnung der Ratssitzung — als vorläufiger Stand, bis das Protokoll kommt. |
| `record_council_livestream.py` | täglich `0 13 * * *` (UTC) | Schneidet die Ratssitzung live aus dem O1-Stream mit, verfolgt den laufenden TOP und liest die Ergebnisse noch am Abend; an Tagen ohne Ratssitzung ein Leerlauf. |
| `check_presse.py` | täglich `15 5 * * *` | RSS-Abgleich der städtischen Pressemitteilungen und der laufenden Bauleitplan-Beteiligungen. |
| `social_kartentexte.py` | täglich `45 7 * * *` | Ein erklärender Satz je inhaltlichem Tagesordnungspunkt der nächsten drei Wochen (LLM, schreibt nie zweimal dasselbe). |
| `zahl_der_woche.py` | täglich `30 11 * * *` | Zahl der Woche für „Heute“: wählt aus Beschluss-Beträgen und Zahl der Beschlüsse eine Zahl und schreibt sie in Alltagssprache (LLM nur bei neuem Kandidaten). |
| `render_plaene.py` | sonntags `30 4 * * 0` | Neue Bauleitplan-Anlagen (Planzeichnung, Lageplan) als Bilder für die Beschluss-Seite. |
| `speicherfristen.py` | täglich `40 4 * * *` | Löscht Recherchen von Konten ohne Einwilligung ins Speichern sieben Tage nach ihrem letzten Stand (dieselbe Frist greift zusätzlich bei jedem Start des Backends). |
| `check_wahltermine.py` | täglich `15 6 * * *` | Vergleicht den Terminkalender des Votemanagers mit `kommunalwahl/wahlen/` — meldet eine unbekannte Wahl und eine Wahl-Id, die endlich da ist oder kurz vor dem Wahltag noch fehlt. Legt nichts an. |
| `check_herzschlag.py` | täglich `30 6 * * *` | Meldet Jobs, die gegen ihren Takt aus `kern/jobs.py` schweigen, einen vollen Datenträger, auffällige Registrierungen, Verstöße gegen die Datenregeln und ein Ratsinformationssystem, das nicht wie erwartet antwortet. Zieht außerdem wöchentlich die Wegwerf-Liste nach. |
| `check_cities.py` | werktags `15 10 * * 1-6` mit `--nur-oldenburg`, sonntags `0 5 * * 0` | Städte-Speicher: werktags nur Oldenburg übernehmen und einbetten (ohne Netz und Modell — daraus entsteht „Anderswo" unter neuen Beschlüssen), sonntags zusätzlich die Vergleichsstädte, Einordnung, Ideen-Gruppen und Urteile. Kostengrenze je Lauf `CITIES_MAX_USD` (Vorgabe 2 $), Frist `CITIES_MAX_SECONDS`. |

¹ **Nur auf Prod** — und das ist seit 09/2026 die richtige Seite. Der
Haushalts-Bereich hing bis dahin an einem Umgebungs-Gate und war auf
ratslotse.de unsichtbar; hier stand deshalb das Gegenteil („nur auf der
Dev-VM"). Seit dem Rollen-Umbau hängt er am Recht `budget` und ist dort für
Ratsmitglieder sichtbar (`kern/roles.py`), die Daten sind eingelesen. Auf der
Dev-VM gibt es beide Jobs **nicht**; dort zieht `ops-finanzdaten-ingest.yml`
den Bestand von Hand nach.

Ein Abgleich mit der Crontab auf dem Server am 03.09.2026 ergab für beide
Jobs ein **wöchentliches** Intervall. In dieser Tabelle und in `kern/jobs.py`
stand zuvor fälschlich ein 14-tägiges Intervall. Bei Änderungen am Zeitplan
ist die Crontab des Servers die maßgebliche Quelle.

### Was der Protokoll-Lauf inline nachzieht

`check_protocols.py` ruft nach dem Parsen die nachgelagerten
Python-Funktionen direkt auf. Für jeden Schritt gilt eine Obergrenze,
die den Tageszuwachs abdeckt und den Arbeitsumfang pro Lauf begrenzt. An
Tagen ohne neue Protokolle fallen keine LLM-Aufrufe an.

| Schritt | Modul | Limit je Lauf |
|---|---|---|
| Protokolle der letzten 90 Tage neu prüfen und parsen | `backfill_protocols.process_range` | Zeitfenster `LOOKBACK_DAYS = 90` |
| Themenfeld-Klassifikation aller noch unklassifizierten Beschlüsse | `classify_decisions.process` | kein Limit (idempotent) |
| Beschlüsse gegen die Stadtziele bewerten, inkrementell | `track_goals.process` | nur noch nicht verknüpfte Paare |
| €-Beträge extrahieren (Regex, kein LLM) | `extract_amounts.process` | nur fehlende |
| „Einfach erklärt"-Kurzfassungen | `generate_simple_summaries.process` | 60 |
| Gesprächswert (Interessantheit) | `rate_interest.process` | 200, 2 Worker |
| Tragweite | `rate_impact.process` | 200, 2 Worker |
| Vorlagen-Volltexte nachladen (Netz + PDF-Text, kein LLM) | `backfill_vorlagen.process_missing` | 300 |
| Anlagen/Anträge nachladen + jüngste Tagesordnungen erneut scannen | `backfill_anlagen` | 300 (+ Rescan) |
| Beratungsfolge nachziehen + bewegliche Stationen aktualisieren | `backfill_beratungen` | 300 (+ Rescan) |
| Wichtigkeits-Score neu berechnen (Heuristik, kein LLM) | `CouncilStore.backfill_importance` | alle |
| Volltext-Index neu bauen | `CouncilStore.rebuild_fts` | alle |

Bei beiden LLM-Scores und beim Abruf der Vorlagen verarbeitet das Skript die
neuesten Einträge zuerst. So deckt es den Tageszuwachs auch mit einem kleinen
Limit ab. Der Wochenlauf verarbeitet den historischen Bestand in Batches.
Das Skript berechnet den Wichtigkeits-Score nach der Tragweite, damit deren
neuer Wert sofort in die 50/50-Gewichtung eingeht
(siehe [Bewertungs-Scores](/docs/bewertungen/)).

### Schrittfolge des Wochenlaufs

`weekly_enrich.py` startet seine Schritte als Unterprozesse. Maßgeblich ist die
`STEPS`-Liste im Skript. Sie hat 23 Einträge, in dieser Reihenfolge:

1. **Regex-Ernte** — `ernte_backfill.py`, ohne Modell und ohne Netz. Sie steht vorn, weil jede Verbesserung an den Mustern in `council/ernte.py` erst durch diesen Schritt auf die schon gespeicherten Vorlagen wirkt.
2. **Sitzungs-Nachlauf** — `nachlauf_sitzungen.py --monate 24`, holt Sitzungen nach, die der tägliche Kalenderlauf verpasst hat (sein Rückblick reicht drei Monate).
3. **Entitäten** — `extract_entities.py`, baut `council_entities` neu auf.
4. **Beschreibungen** — `describe_entities.py`, füllt fehlende Texte zu Entitäten.
5. **Vagheits-Urteile** — `warm_topic_vagueness.py`, rechnet die Urteile über Themen-Vorschläge vor, damit der Einrichtungs-Assistent sie nicht in der Anfrage holen muss.
6. **Geocoding** — `geocode_entities.py`, verortet neue Orts-Entitäten.
7. **Straßen-Geometrie** — `strassen_snapshot.py aktualisieren`: **ein** Abruf holt alle benannten Wege der Stadt, der Abgleich läuft danach ohne Netz. Einzelabfragen je Straße scheitern am Limit des Dienstes.
8. **Embeddings und Ähnliche** — `embed_decisions.py`, berechnet „Ähnliche Beschlüsse“ neu ([ADR 0003](/docs/adr/0003-fastembed-statt-torch/)).
9. **Anlagen-Texte** — `backfill_anlagen_texte.py --limit 300`, lädt Volltexte neuer Anlagen nach (ohne Modell).
10. **Anlagen-Embeddings** — `embed_anlagen.py`, schreibt ihre Vektoren für die ausführliche Recherche.
11. **Verwandte Themen** — `build_entity_relations.py`, berechnet „Hängt zusammen mit …“ je Thema (ohne Modell). Braucht die Schritte 3 und 8.
12. **Themen ↔ Beschlüsse** — `match_topics_decisions.py`, gleicht die Themen der Nutzer*innen semantisch mit Beschlüssen ab.
13. **Themenfeld-Rückblicke** — `generate_field_recaps.py`, erneuert nur veraltete Felder.
14. **Einfach erklärt** — `generate_simple_summaries.py`, 500er-Tranche, neueste zuerst.
15. **Personen-Stammdaten** — `backfill_stammdaten.py`, Mandatsträger und Mitgliedschaften aus dem Ratsinformationssystem (ohne Modell).
16. **Tragweite** — `rate_impact.py --limit 500`, bewusst vor dem Wichtigkeits-Score.
17. **Wichtigkeits-Score** — `score_importance.py`, Heuristik über den Gesamtbestand.
18. **Bebauungsplan-Flächen** — `fetch_bplan_outlines.py`, ein Abruf beim Geoportal der Stadt (über den [Heim-Proxy](#heim-proxy-gegen-adress-sperren)).
19. **Mein Viertel** — `build_district_projects.py`, Richter-Urteil je neuem verorteten Beschluss und Bündelung zu Vorhaben ([Mein Viertel](/docs/mein-viertel/#das-register-der-vorhaben)).
20. **Quizfragen** — `generate_quiz.py`, füllt nur Gebiete unter der Ziel-Fragenzahl auf.
21. **Quiz aus Daten** — `build_quiz_formats.py`, Fragen aus Anträgen und Haushaltsprodukten (ohne Modell).
22. **Interessantheit** — `rate_interest.py --limit 500`, neueste zuerst.
23. **Fundstücke** — `generate_fundstuecke.py --days 21`, legt fehlende Kalendertage 21 Tage im Voraus an.

Jeder Schritt läuft **fehlertolerant**: Ein Fehlschlag wird protokolliert und
gemerkt, stoppt aber die übrigen Schritte nicht. Am Ende gibt der Lauf eine
Bilanz aus und setzt einen Exit-Code ungleich null, sobald mindestens ein
Schritt gescheitert ist; daraus wird für den Alarmweg eine Ausnahme.

Das Skript beendet einen Schritt nach `WEEKLY_STEP_MAX_SECONDS` (Standardwert
drei Stunden) und zählt ihn als fehlgeschlagen. Zwischen zwei Schritten prüft
es, ob ein Deploy ansteht, und beendet in diesem Fall den Wochenlauf. Der
nächste Sonntagslauf verarbeitet die noch fehlenden Einträge.

### Fehler-Alarme

Alle Cron-Einstiegspunkte laufen in `run_guarded` aus `kern/alerts.py`. Stürzt
ein Job ab, passiert dreierlei: der Traceback landet im Log (journald bzw.
Cron-Log), eine Alarm-Mail geht an `ALERT_EMAIL` (Fallback `WEB_ADMIN_EMAIL`)
und die Exception wird erneut geworfen, damit Cron einen Exit-Code ungleich
null sieht. Der Mailweg ist strikt best-effort: ohne `RESEND_API_KEY` — oder
wenn der Versand selbst scheitert — bleibt der Alarm im Log, und der
Alarmpfad selbst wirft nie.

### Der Herzschlag

`check_herzschlag.py` (täglich `30 6 * * *`) erkennt auch Jobs, die gar
nicht starten. Es gleicht die Läufe mit den Intervallen aus `kern/jobs.py`
ab, prüft den freien Speicherplatz und zählt die Registrierungen des
letzten Tages. Das Skript versendet höchstens eine E-Mail am Tag.

Seit 11/2026 fragt derselbe Lauf das **Ratsinformationssystem** von außen ab
(`council/ris.py::probe`): Kalender des laufenden Monats und RSS-Feed, dazu
ein Abgleich der dort verlinkten Sitzungen gegen den Bestand. Anlass war der
Umzug der Stadt von `buergerinfo.oldenburg.de` nach
`ratsinfo.oldenburg.de/bi`: Der alte Host leitete jede Adresse auf die
Startseite um, die Parser fanden nichts, und „nichts gefunden“ war kein
Fehler. Ein solcher Befund steht in der Mail an erster Stelle und gibt ihr
den Betreff *Ratsinfo liefert nicht*. Unabhängig davon werfen die Abrufe
selbst einen `RisError` (dauerhafte Weiterleitung, fremder Host, keine
SessionNet-Seite, vier Monate leerer Kalender) — der betroffene Cron stürzt
ab und meldet sich über `run_guarded` schon beim ersten Lauf.
`RATSLOTSE_RIS_PROBE=0` schaltet die Tagesprobe ab.

Seit 11/2026 hält derselbe Lauf die **Wegwerf-Liste** frisch
(`kern/disposable_email.py`): Ist sie eine Woche alt, holt er den Stand des
öffentlichen Projekts, prüft ihn (keine kaputten Zeilen, höchstens zehn
Prozent Schwund, kein geschützter Anbieter) und schreibt ihn nach
`data/disposable_email_domains.txt` — dorthin, weil der Deploy `data/` nicht
überschreibt. Gelesen wird die neuere Fassung von Kopie und Repo-Datei nach
ihrem `# Stand:`-Kopf, ohne Neustart des Dienstes. Gemeldet wird erst, wenn
das Nachziehen einen Monat lang scheitert. `RATSLOTSE_WEGWERF_NACHZIEHEN=0`
schaltet es ab. Anlass: Die Liste stand von September bis November still, und
am 23.11.2026 kam ein Konto über einen Anbieter herein, den sie upstream
längst führte.

Seit 10/2026 prüft derselbe Lauf auch den **Rats-Bestand**
(`council/datenpruefung.py`). Datenfehler können auch bei erfolgreichen
Jobs bestehen bleiben. So lagen Antworten der Verwaltung wochenlang im Feld
für Ratsbeiträge. Der Fehler fiel erst in einer ausgegebenen Antwort auf.

| Regel | Art | Behebung |
|---|---|---|
| Ergebnis widerspricht dem Abstimmungssatz („gilt als behandelt“ als angenommen) | Bestand | `ops-settled-ergebnis.yml` |
| Kurzfassung eines nicht gefassten Beschlusses nennt das Ergebnis nicht (120 Tage) | Bestand | `ops-settled-ergebnis.yml modus=kurzfassungen` |
| Ratsbeitrag mit Antwort im eigenen Feld | neu extrahiert | Extraktion prüfen |
| eine Person, zwei Parteien in einer Sitzung | neu extrahiert | Protokoll nachsehen |
| Protokoll fehlt nach 10 Wochen | einmal je Sitzung | bei der Stadt nachsehen |
| Grundakten älter als 36 Stunden, Hauptpunkt ohne Akte, über 40 % der Beiträge ohne Akte | Bestand (90 Tage) | `scripts/build_matters.py` |

**Bestandsregeln** erwarten null Verstöße im gesamten Bestand und melden
jeden Verstoß, solange er besteht. Die übrigen Regeln prüfen nur Zugänge
seit dem letzten Überwachungsjob. Das verhindert Meldungen über dieselben
Einträge an mehreren Tagen. Die Kennzahlen
(`daten_…`) stehen auch ohne Meldung unter *Statistik → Cron-Jobs*.

---

## Ops-Workflows (manuell auslösbar)

Die vollständige Liste mit Auslöser und Zweck entsteht aus den
Workflow-Dateien. [Referenz: Workflows](/docs/referenz/workflows/). Dieser Abschnitt
erklärt die Werkzeuge, die im Betrieb am häufigsten gebraucht werden.

Die `ops-*`-Workflows starten per `workflow_dispatch`; zwei laufen zusätzlich
nach Zeitplan (`ops-erreichbarkeit.yml`, `ops-deploy-rueckstand.yml`). Die
Tabelle unten beschreibt sechs davon ausführlicher.
Sie nutzen denselben Deploy-Key und ProxyJump wie `deploy.yml` und führen die
Skripte direkt auf der App-VM aus — praktisch, wenn kein SSH-Zugang zur Hand
ist. Nur Collaborator können sie starten.

**Verbunden wird über die eigene Action `.github/actions/ssh`** (seit
11/2026), nicht mehr über `appleboy/ssh-action`. Die bekam den Deploy-Key und
lud das Programm, das ihn benutzt, zur Laufzeit ohne Prüfsumme nach; die
eigene Action nutzt nur das OpenSSH des Runners. Die Eingaben heißen wie
früher (`host`, `key`, `proxy_*`, `script`, `envs`, `command_timeout`, für
Dateien `source`/`target`). Ein neuer Ops-Workflow braucht davor einen
Checkout (`sparse-checkout: .github/actions` genügt). Das Skript geht über
stdin hinüber, die `envs` stehen also nicht in der Prozessliste der VM.
`tests/test_ssh_action.py` prüft die Action und meldet einen Schritt ohne
Checkout, eine unbekannte Eingabe, eine nicht gesetzte `envs`-Variable und
jeden Workflow, der den Deploy-Key an eine fremde Action reicht.

Schritte, die selbst `ssh`, `scp` oder `rsync` aufrufen (`deploy.yml`,
`ops-erreichbarkeit`, `ops-deploy-rueckstand`, `ops-haushalt-vergleich`,
`ops-wartungsbarriere`), holen sich ihre `~/.ssh/config` von
**`.github/actions/ssh-config`**: Sprungrechner als `edge`, je Ziel eine Zeile
`<name> <host>`. Bis 11/2026 stand dieser Block fünfmal von Hand in den
Workflows, jedes Mal mit `StrictHostKeyChecking no`. Der Deploy-Key geht an
nichts anderes als an diese beiden Actions, auch an kein eigenes `run:`-Skript.

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

### Host-Schlüssel (`VPS_KNOWN_HOSTS`)

Beide Actions prüfen die Host-Schlüssel von Sprungrechner, Prod und Dev gegen
das Secret `VPS_KNOWN_HOSTS`. Es steht seit dem 12.11.2026, mit je einer
ed25519-Zeile für die drei Rechner. **Fehlt es oder ist es leer, bricht jeder
SSH-Schritt ab, bevor er verbindet.** Bis 11/2026 nahmen die Actions in dem
Fall den ersten Schlüssel an, mit einer Warnung im Lauf. Weil jeder Lauf auf
einem frischen Runner beginnt, hieß das: jeden Schlüssel, auch den eines
Rechners, der sich als Server ausgibt. Ein gelöschtes Secret hätte die Prüfung
so still abgeschaltet.

**Bekommt ein Server einen neuen Schlüssel** (Neuinstallation, Umzug), scheitert
jeder Lauf dorthin mit „Host key verification failed“, bis das Secret
nachgezogen ist. Das ist gewollt: Genau so sähe auch ein Angriff aus.

**Nachziehen.** Jede Zeile muss den Rechner so nennen, wie das Secret ihn
schreibt: `[host]:port`, bei Port 22 nur `host`. Steht im Secret eine IP,
braucht die Zeile die IP, nicht den Namen. Der Sprungrechner lässt keine
Befehle zu, er reicht nur durch (`This account is currently not available`).
Die Schlüssel von Prod und Dev liest man deshalb über ihn auf dem Ziel selbst:

```bash
PORT=…; SPRUNG=…; PROD=…; DEV=…   # Werte der gleichnamigen Secrets
LOGIN=…                            # dein Login auf Sprungrechner und Zielen
name() { if [ "$PORT" = 22 ]; then echo "$1"; else echo "[$1]:$PORT"; fi; }
ssh-keyscan -t ed25519 -p "$PORT" "$SPRUNG" > known_hosts_ci
for h in "$PROD" "$DEV"; do
  echo "$(name "$h") $(ssh -J "$LOGIN@$SPRUNG:$PORT" -p "$PORT" "$LOGIN@$h" \
    cat /etc/ssh/ssh_host_ed25519_key.pub | cut -d' ' -f1,2)" >> known_hosts_ci
done
ssh-keygen -lf known_hosts_ci        # drei Zeilen, je ein Fingerabdruck
gh secret set VPS_KNOWN_HOSTS < known_hosts_ci
```

Nur der `ssh-keyscan` ist für sich ungeprüft; die beiden anderen Schlüssel
kommen über Verbindungen, die das eigene `known_hosts` schon prüft. Den
Fingerabdruck des Sprungrechners deshalb dagegen halten:
`ssh-keygen -lF "[$SPRUNG]:$PORT"` (bei Port 22 nur `"$SPRUNG"`).

Am 12.11.2026 lief es ohne die Werte von Hand: Ein Wegwerf-Workflow las die
Schlüssel mit genau den Werten aus den Secrets ein und gab sie nur
verschlüsselt ins öffentliche Log. Lokal entschlüsselt, stimmten alle drei
Fingerabdrücke mit dem `known_hosts` eines Admin-Rechners überein.

Danach einmal ohne Folgen ausprobieren, bevor der nächste Deploy es tut:

```bash
gh workflow run ops-modelle.yml --ref dev -f umgebung=dev            # Sprungrechner + Dev
gh workflow run ops-wartungsbarriere.yml --ref dev -f aktion=status  # Sprungrechner + Prod, liest nur
```

---

## Städte-Speicher: der einmalige Backfill

`data/cities.sqlite` (Ratsdokumente der Vergleichsstädte, `council/cities`)
entsteht **nicht** allein aus dem Cron. `check_cities.py` schaut sonntags je
Stadt 60 Tage zurück — das hält den Bestand aktuell, baut ihn aber nie auf.
Der Aufbau ist ein einmaliger Lauf je Stadt:

```bash
# Oldenburg: kein Netz, Minuten — der Adapter liest council.sqlite
python scripts/cities_backfill.py --run --body oldenburg
# Die fünf mit OParl: je Stadt Stunden, ein Abruf je Sekunde je Host
for stadt in osnabrueck braunschweig muenster potsdam magdeburg; do
  python scripts/cities_backfill.py --run --body "$stadt" --since 2023-01-01
done
```

Danach einordnen und indizieren (beides über `check_cities.py` oder von Hand
über `council.cities.pipeline`). Die Einordnung kostet rund 0,31 $ je 1.000
Vorlagen; `CITIES_ANNOTATE_MAX` deckelt sie je Lauf, damit ein Rückstand über
mehrere Wochen abgebaut wird statt an einem Sonntag teuer zu werden.

**Reihenfolge beachten**, und sie ist seit 09/2026 länger:

```bash
python scripts/cities_backfill.py --run --stage annotate   # classify + effort
python scripts/cities_backfill.py --run --stage index      # Chunks, Vektoren, FTS, Nachbarn
python scripts/cities_backfill.py --run --stage cluster    # Ideen-Cluster über Städte
# fit läuft nur im Cron — es braucht Index UND Cluster
```

Jede Stufe braucht die vorige: Die Einordnung sagt, was eine *Idee* ist; der
Index rechnet Nachbarschaften über alle Städte; die Cluster fassen zusammen,
was dieselbe Idee ist; und `fit` urteilt erst, wenn es beides hat.

**Die Niederschriften laufen daneben her.** Seit 09/2026 holt `fetch` auch die
Sitzungsprotokolle (`role='protocol'`, nur Sitzungen der letzten 24 Monate),
`pipeline.split_protocols` schneidet sie in ihre Tagesordnungspunkte, und
`council.cities.reasons.run` liest daraus, warum ein Rat so entschieden hat —
gedeckelt über `CITIES_REASON_MAX` (Vorgabe 400 Abschnitte je Lauf, unter
0,10 $). Gefragt werden nur Punkte, deren Idee mindestens eine andere Stadt
teilt; nur dort zeigt die Karte das „Warum" überhaupt.

Eine Stadt, die Protokoll-Adressen nennt, aber keine ausliefert, wird nach
drei Fehlversuchen übersprungen — Magdeburg nennt 606 Adressen, von denen
jede einzelne mit 404 antwortet.

**Nach jedem Abruf folgt eine Plausibilitätsprüfung.** Am 08.09.2026
enthielt der Bestand vier Fehler aus der Datenerhebung, die weder
Abstürze oder Testfehler noch auffällige Kennzahlen verursachten.

```bash
python scripts/cities_backfill.py --pruefen
```

Vier Bänder je Stadt (Vorlagen je Sitzung, Anteil mit Ergebnis, mit Text, mit
Beratung), aus dem Bestand gemessen. Dazu die Ergebnistexte, die die Zuordnung
nicht kennt — das ist die Liste, mit der man eine neue Stadt anschließt. Die
Einzelheiten stehen in `council/cities/CLAUDE.md`, die Prüfung läuft auch im
Wochen-Cron und schreibt `implausibel` in die Kennzahlen.

**Was der Bestand hergibt**, sobald er steht:

```bash
python scripts/cities_cluster_bericht.py --ohne-oldenburg   # Ideen, die Oldenburg fehlen
python scripts/cities_gegenrichtung.py --offen              # wie ging es anderswo aus?
```

**Platz:** Der Speicher wächst mit der Historie; drei Jahre über fünf Städte
plus Oldenburg seit 2018 sind rund 600 MB. `check_herzschlag.py` schaut auf
den freien Platz, aber vor dem ersten Lauf lohnt ein Blick.

**Pro Datenbankdatei darf nur ein Prozess schreiben.** Mit `--parallel`
kann der Backfill Daten mehrerer Städte gleichzeitig in getrennte Rohdateien
schreiben. Konkurrieren zwei Prozesse um einen Schreibzugriff auf
`cities.sqlite`, meldet SQLite `database is locked`. Beim Probelauf endete
der zweite Thread ohne weitere Meldung.

**Ein anderes Einbettungs-Modell probieren.** Der Speicher hält Vektoren und
Nachbarschaften je Modell getrennt, ein neues liegt also neben dem alten und
löscht nichts:

```bash
python scripts/cities_modellvergleich.py --einbetten --modell <name>
python scripts/cities_modellvergleich.py --modell <name>
```

Gemessen am 08.09.2026 über 16.585 Papiere: Das größere
`paraphrase-multilingual-mpnet-base-v2` (768 Dimensionen) fand **weniger** von
dem, was ein Mensch als richtigen Beleg bezeichnet hat (12 von 23 gegen 19 von
23), und drängte fast alle Kanten ins obere Band — 20.523 über 0,85, wo das
heutige Modell 233 hat. Die Schwellen der Anzeige sind auf dieses Band geeicht;
wer das Modell wechselt, misst sie neu.

**Kennzahlen des Wochenlaufs:** `papers_total` und `papers_oldenburg` stehen
im Admin-Panel unter *Statistik → Cron-Jobs*. Oldenburg eigens, weil es die
Stadt ist, gegen die alles verglichen wird: Fällt die Zahl, fehlt dem
Vergleich die eine Seite — und zwar still, weil die anderen Städte
weiterlaufen.

### Der Weg auf Prod

Beide Schalter des Städtevergleichs sind vorübergehend. In
`kern/features.py` steht unter `fertig_wenn` jeweils die Bedingung für
das Entfernen. Die Aktivierung setzt eine fachliche Entscheidung voraus.
Die folgende Reihenfolge beschreibt den technischen Ablauf.

| # | Schritt | Bedingung |
|---|---|---|
| 1 | `cities.sqlite` auf der Dev-VM aufbauen (Backfill oben, Stunden) | keine — ohne sie zeigt dev nichts |
| 2 | `andere-staedte` in `FEATURE_FLAGS` auf Prod | Der Block lag vier Wochen auf dev, und zwei Mandatsträger*innen haben die Treffer als brauchbar bestätigt |
| 3 | `cities.sqlite` auf der Prod-VM aufbauen und den Wochen-Cron eintragen | vor Schritt 2, sonst zeigt der Block dort nichts |
| 4 | `ideen-anderswo` in `FEATURE_FLAGS` auf Prod | Tim hat zwei Themenfelder durchgesehen und die Urteile für tragfähig erklärt |
| 5 | Beide Schalter aus der Registry nehmen | wenn sie auf Prod stehen und niemand sie mehr umlegt |

**Ein Schritt liegt quer dazu: die Fassung des Urteils.** Die Oberfläche zeigt
`fit`/1; Fassung 2 (Ideen-Cluster, Aufwandsklasse, drei Stimmen) liegt
daneben und ist noch nicht umgestellt. Der Grund steht als `gut_wenn` am
Annotator und ist eine Zahl, keine Meinung:

> Fassung 2 ist reif, wenn der Bestand einmal damit gerechnet ist und der
> Anteil „fehlt + lohnt sich" unter 30 % liegt. Fassung 1 liegt bei 50 %
> (649 von 1.290 Urteilen) — eine Liste, auf der jede zweite Zeile ein
> Volltreffer ist, ist kein Vorschlag, sondern ein Katalog.

Umgestellt wird an genau einer Stelle: `CitiesStore.IDEEN_FIT`. Danach der
Aufräumlauf, der Fassung 1 löscht — aber erst dann.

**Auf dev steht `FEATURE_FLAGS=*`**, dort sind beide also schon an — sichtbar
wird trotzdem erst etwas, wenn Schritt 1 gelaufen ist.

**Schritt 5 ist kein Aufräumen, sondern Teil der Sache.** Ein Schalter, den
niemand mehr umlegt, ist eine Verzweigung, die jeder mitliest und niemand
braucht; `tests/test_features.py` meldet einen, den keine Oberfläche mehr
abfragt.

**Was der Rollout NICHT braucht:** einen App-Store-Build. Beide Oberflächen
holen ihre Schalter über `/api/app-config`; die ausgelieferte App bekommt die
Seite in dem Moment, in dem der Schalter auf Prod steht.

**Lokal zum Arbeiten:** `python scripts/lokale_daten.py hol --mit-staedten`
und `setz --mit-staedten` nehmen den Speicher vom Server mit. Ohne den
Schalter bleibt alles wie bisher; 600 MB will nicht jede*r auf dem Notebook.
Eine Abspeckung wie bei der Rats-Datenbank braucht es fast nicht — es stehen
öffentliche Ratsdokumente anderer Städte darin. Die eine Ausnahme sind die
Rückmeldungen zu den Urteilen („Stimmt das?", mit Konto-Nummer und
Freitext): `hol` leert sie, bevor die Datei an ihren Platz rückt, und die
Konto-Löschung räumt sie wie die übrigen Kontodaten
(`CITIES_USER_OWNED_TABLES` in `council/cities/store.py`).

### Runbook 3.0.0: Belege umschlüsseln, Cron wieder an

Der einmalige Weg, den #1651 für den Prod-Speicher mitbringt — **in dieser
Reihenfolge**. Gegenüber dem PR-Text von #1651 ist ein Schritt gewandert:
Die Quell-Hashes der Ideen werden erst übernommen, **nachdem** der erste
Oldenburg-Lauf die neuen Oldenburger Vorlagen geholt hat. Andersherum stehen
die Hashes auf dem alten Beleg-Pool, und der erste Sonntag beurteilt trotzdem
alle rund 200 Ideen neu (~0,9 $, Stunden). Das Skript prüft das inzwischen
selbst und bricht ab, solange der Speicher hinterherhinkt
(`oldenburg_rueckstand`, übergehen nur mit `--trotzdem`).

Alles in `~/app`, der Dienst muss nicht neu starten; der Cron bleibt bis
Schritt 8 aus — kein zweiter Schreiber auf `cities.sqlite`.

| # | Befehl | Erwartung |
|---|---|---|
| 1 | `sqlite3 data/cities.sqlite ".backup data/cities.sqlite.vor-3.0.0"` | Sicherung (Handkopie, fällt aus der Rotation) |
| 2 | `.venv/bin/python scripts/cities_belege_umschluesseln.py` | „863 alte Kennungen im Bestand, 863 davon im Abbild" |
| 3 | `… --schreiben` | `{"rows": 3242, "keys": 3917, "unknown": 0}`; zweiter Aufruf ist ein No-op |
| 4 | `… --gruppen` | feste Nummern, ~19 Gruppen vereint, `idea_groups` neu, keine leeren Zeitleisten-Titel |
| 5 | `… --links` und `… --neu-einordnen "https://e-government.hannover-stadt.de/lhhsimwebre.nsf/DS/0832-2023"` | Links für Magdeburg/Münster; die Tippfehler-Vorlage wird am Sonntag neu eingeordnet |
| 6 | `.venv/bin/python scripts/check_cities.py --nur-oldenburg` | Minuten, 0 $, `papers_new` ≈ Oldenburger Vorlagen seit 10.09.; endet **rot**, wenn eine Stufe scheitert (seit 10/2026) |
| 7 | `… cities_belege_umschluesseln.py --hashes-ideen` | Minuten, Cent-Bereich; bricht mit Hinweis ab, wenn Schritt 6 fehlt, und mit `LaufAbbruch`, wenn ein Vektor-Arm stumm ist (Embedding-Modell fehlt) |
| 8 | crontab scharf: werktags 10:15 `--nur-oldenburg`, sonntags 5 Uhr alles | |
| 9 | vor dem ersten Sonntag: `check_cities.py --trocken` | Rückstau und Kosten; Stückkosten seit 10/2026 auf der Messung aus #1651 |

**Warum Schritt 7 abbrechen kann.** `_Vektor.hol` schluckt einen
Embedding-Fehler bewusst (ein Arm darf den Lauf nicht kippen). Damit lieferten
die Vektor-Arme ohne fastembed-Modell still nichts, und `--hashes-ideen`
übernahm am 03.10.2026 lokal 199 Hashes in 38 s — auf verarmten Belegen.
`idea_fit.run` und `fit.run(nur_hashes=True)` zählen deshalb vorher, welche
Arme Treffer liefern; fehlt einer, dessen Matrix im Bestand liegt, bricht der
Lauf ab, statt zu urteilen oder Hashes zu übernehmen.

---

## Backups

`scripts/backup_db.py` läuft täglich um 03:00 und sichert **jede** Datenbank
unter `data/` (heute `ratslotse.sqlite`, `council.sqlite` und `cities.sqlite`)
mit der `sqlite3`-Backup-API — also konsistent, ohne den laufenden Betrieb zu
stoppen. Die Kopien landen unter `data/backups/` mit Datum
im Dateinamen, im Journal-Modus `DELETE`: Mit dem WAL-Modus der Quelle ließ jedes
spätere Öffnen `-wal`/`-shm` daneben liegen (am 23.11.2026 waren es 218).

- **Erst prüfen, dann ablegen (seit 10/2026):** Die Backup-API schreibt in
  eine Zwischendatei (`.<name>.tmp`), `PRAGMA integrity_check` (ab 500 MB
  `quick_check`) muss „ok" sagen, erst dann wird sie per `os.replace` zum
  datierten Stand. Vorher ging es direkt in die Zieldatei — bei voller Platte
  blieb eine halbe Datei unter gültigem Namen liegen und verdrängte in der
  Rotation einen guten Stand.
- **Der Städte-Speicher hat eine eigene Rotation:** zwei Tagesstände, keine
  Wochenmarken (`ROTATION_JE_STAMM`). Mit 7 + 4 Ständen lagen von den 2,4 GB
  rund 27 GB im Sicherungsordner; der Inhalt ist aus öffentlichen Quellen
  wiederherstellbar.
- **Rotation:** zwei Stufen, `TAEGLICH = 7` und `WOECHENTLICH = 4`. Es bleiben
  die sieben jüngsten Sicherungen, dazu aus jeder der vier Kalenderwochen
  **vor** diesem Fenster die jüngste — zusammen 29 bis 35 Tage Abdeckung.
  Sieben Tage feinkörnig decken „gestern war es noch gut" ab, die Wochenmarken
  alles, was erst später auffällt. Der Zusatz „vor dem Fenster" ist nicht
  kosmetisch: Reicht das Tagesfenster in die Vorwoche hinein, läge deren Marke
  einen Tag neben einem Tagesstand und gewänne keinen Abstand — der Bestand
  endete dann schon nach 22 Tagen.
- **Handkopien unter `data/` werden nicht gesichert (seit 11/2026).** Eine
  Datenbank mit Punkt im Stamm (`council.vor-pymupdf-2026-10-18.sqlite`) ist
  selbst schon eine Sicherung. Bis dahin lief sie als eigene Datenbank durch
  die Rotation — elf Stände zu 800 MB, 8,8 GB lokal und noch einmal off-site.
  Der Lauf nennt sie und zählt sie unter „Handkopien übersprungen".
- **Handkopien im Sicherungsordner bleiben liegen.** Gezählt wird nur, was `<stamm>_JJJJ-MM-TT.sqlite`
  heißt. Eine von Hand gezogene `council_vor_release_v2.0.0.sqlite` fällt aus der
  Rotation heraus: Sie wird nie gelöscht und kostet auch keinen Platz im Bestand.
  Vorher war beides falsch herum — gelöscht wurde `sorted(...)[:-7]`, und weil
  `council_pre_…` alphabetisch hinter `council_2026-…` steht, warfen zwei
  Handkopien vom August zwei Tagesstände hinaus (am 03.09.2026 lagen deshalb nur
  fünf Tagesstände von `council` vor, aber sieben von `nwz`).
- **Off-Site-Mirror (optional):** Ist `BACKUP_RSYNC_TARGET` gesetzt, wird das
  Backup-Verzeichnis anschließend per `rsync -az --fuzzy --delete-after`
  gespiegelt; das Ziel ist damit ein exaktes Abbild der lokalen Rotation.
  `--fuzzy` nimmt den Vortagesstand im Ziel als Vorlage für den
  Delta-Abgleich — ohne ihn ging jeder neu benannte Stand ganz über die
  Leitung, beim Städte-Speicher 2,4 GB je Nacht. Eine Kopie gegen
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
Datenbank. `dateien_spiegeln()` legt Ordner per `rsync` in `data/backups/` und
damit in den Off-Site-Spiegel, `einzeldateien_sichern()` dazu einzelne Dateien
nach `data/backups/einzeldateien/` (Liste `EINZELDATEIEN` — bewusst kein „alle
`.json`", dort liegen auch Fortschrittsmarken):

| Was | Inhalt | Wiederherstellbar? |
|---|---|---|
| `data/plaene/` | gerenderte Planzeichnungen | ja, aber nur über einen Stapellauf über 600 Anlagen |
| `data/archiv/` | Statistik-Archiv (s. u.) | **nein** — die Quellen sind überschrieben |
| `data/transkripte/` | Transkripte der Sitzungs-Mitschnitte | **nein** — der Livestream ist danach weg |
| `data/eval_gold/` | Ergebnisse der Gold-Läufe | **nein** — die Vergleichsbasis jeder Messung |
| `wahlabend-verlauf-*.json` | Verlauf der Wahlabende, Stand je Abruf | **nein** |
| `strassen-snapshot.json` | Straßenbestand aus dem GIS der Stadt | nur über den Heim-Proxy |
| `wahltermine-*.json` | was der Wahltermin-Abgleich schon gemeldet hat | ja, mit Doppelmeldungen |
| crontab | `crontab -l` → `backups/crontab.backup` (0600) | nur aus Skript-Köpfen und `kern/jobs.py` |

Bewusst **nicht** dabei ist die Rohernte der fremden Städte (`cities-raw`,
`cities-files`): öffentliche Dokumente, die sich aus deren RIS neu holen lassen.

**Die Storage Box ist ein Spiegel, kein Archiv.** Was lokal aus der Rotation
fällt oder gelöscht wird, ist nach dem nächsten Lauf auch dort weg — eine
versehentlich gelöschte oder zerschriebene Datei ebenso. Gegen diesen Fall
helfen nur die Schnappschüsse der Storage Box selbst (Hetzner Robot →
Storage Box → Snapshots), die außerhalb des Repos eingerichtet werden.

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

Der Job archiviert Dateien aus drei Quellen ohne weitere Auswertung.

| Bereich | Woher | Umfang (17.08.2026) |
|---|---|---|
| `opendata` | `opendata.oldenburg.de/data.json` und alle darin verlinkten Dateien | 186 Dateien, 10 MB |
| `jahrbuch` | die Übersichtsseite des Statistischen Jahrbuchs, alle Tabellen-PDFs daraus | 246 PDFs, 56 MB |
| `kfa` | die Übersichtsseite des Kommunalen Finanzausgleichs beim LSN | 14 Mappen, 3 MB |

**Download-Links aus den Übersichtsseiten.** Die Übersichtsseiten behalten
ihre Adressen, während die Dateinamen mit neuen Ausgaben wechseln. Eine
feste Liste würde nach Erscheinen neuer Ausgaben weiterhin die alten
Dateien anfragen und Status 404 erhalten.

**Wie versioniert wird:**

```
data/archiv/jahrbuch/1103-2025-AZ.pdf/2026-08-17_9f3c1a2b4d5e.pdf
                     └ Ordner heißt wie die Datei ┘ └ Tag ┘└ Hash ┘
```

Der Dateiname enthält das Datum der ersten Sichtung und den Inhalts-Hash.
Der Job prüft anhand des Hashs, ob der Inhalt bereits vorliegt. Auch ein
neuer `ETag` ohne Inhaltsänderung erzeugt so keine neue Kopie. Wiederholte
Läufe am selben oder an einem späteren Tag legen denselben Inhalt nur
einmal ab.

`data/archiv/manifest.json` hält je Adresse ETag, `Last-Modified`, Hash, Pfad,
Erst- und Letztsichtung sowie den letzten Fehler. Es liegt bewusst **im
Archiv** statt in der Datenbank: Ein Archiv, dessen Inhaltsverzeichnis
woanders liegt, ist nach einer Wiederherstellung ein Haufen Hashes.

**Tägliche Sicherung.** Die Quellen ändern sich in unregelmäßigen
Abständen, teils in mehreren Datensätzen zugleich (29 Open-Data-Datensätze
am 19.06.2026, 20 am 14.07.2026). Der tägliche Lauf sichert die Fassungen
zeitnah, bevor die Quelle sie überschreibt. Die Messung zeigt den
Aufwand pro Lauf.

| Lauf | geladen | Dauer |
|---|---|---|
| erster | 72,4 MB (447 Dateien) | 2:49 min |
| jeder weitere ohne Änderung | 0,0 MB | 34 s |

Der Job prüft zuerst das Feld `modified` des Open-Data-Katalogs und kann
damit auf den Dateiabruf verzichten. Falls nötig, stellt er einen
bedingten Request mit `If-None-Match` oder `If-Modified-Since` (304
ohne Antwortbody). Bei heruntergeladenen Dateien vergleicht er zuletzt
den Inhalts-Hash. Die LSN-Adressen schicken **weder ETag
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

Ratslotse berechnet die Kosten aus der gespeicherten Tokenzahl und dem
hinterlegten Modellpreis. Die Preistabelle `PRICES` in `kern/usage.py`
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

Die Einstellung `llm_budget_monthly` gibt das Budget vor (Standardwert
40,0). Der Schwellenwert ändert nur die Statusanzeige. Modellaufrufe bleiben
möglich und laufen unverändert weiter.

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
| `NWZ_OPENROUTER_ZDR` | ZDR-Vorgabe für Aufrufe mit ZDR-Pflicht, einschließlich des regulären EU-Routings. `0`/`false`/`off`/`no` deaktivieren die Vorgabe für alle Aufrufe. Für ausschließlich öffentliche Daten (`kern/llm.py::OHNE_NUTZEREINGABE`) gilt keine ZDR-Pflicht. | nein | `1` |
| `NWZ_DEEPSEEK_MIN_MAX_TOKENS` | Untergrenze für `max_tokens` bei DeepSeek-Reasoning-Modellen | nein | `24000` |
| `NWZ_GPT56_MIN_MAX_TOKENS` | Untergrenze für `max_tokens` bei den GPT-5.6-Modellen; sonst endet eine Antwort still mit `finish_reason='length'` | nein | `16000` |
| `NWZ_GEMINI_DENK_MIN_MAX_TOKENS` | Dieselbe Untergrenze für Gemini-Modelle, die vor der Antwort denken | nein | `4000` |
| `RATSLOTSE_KI_AUSSERHALB_EU` | Notausgang: `1` lässt Nutzereingaben bei einem Ausfall wieder außerhalb der EU laufen (`kern/llm.py::EU_ZUERST`); sonst nur EU | nein | nicht gesetzt |

### Modellwahl je Aufgabe

Alle Variablen sind optional. Ohne Angabe gilt der Standardwert aus dem Code.

| Variable | Aufgabe | Default |
|---|---|---|
| `COUNCIL_PROTOCOL_MODEL` | Protokoll-/Beschluss-Extraktion | `deepseek/deepseek-v4-pro` |
| `COUNCIL_PROTOCOL_MAX_CHARS` | Zeichen-Obergrenze je Protokoll-Prompt | `60000` |
| `COUNCIL_TOPIC_MODEL` | Themen-Klassifikation | `deepseek/deepseek-v4-pro` |
| `COUNCIL_GOAL_MODEL` | Bewertung gegen die Stadtziele | `deepseek/deepseek-v4-pro` |
| `COUNCIL_ENTITY_MODEL` | Entitäten-NER und -Beschreibungen | `deepseek/deepseek-v4-pro` |
| `COUNCIL_SIMPLE_MODEL` | „Einfach erklärt"-Kurzfassungen | `deepseek/deepseek-v4-pro` |
| `COUNCIL_INTEREST_MODEL` | Gesprächswert-Score | `deepseek/deepseek-v4-pro` |
| `COUNCIL_IMPACT_MODEL` | Tragweite-Score | `openai/gpt-6-luna` (Flex-Tarif) |
| `COUNCIL_FUNDSTUECK_MODEL` | Story zum „Fundstück des Tages" | `deepseek/deepseek-v4-pro` |
| `COUNCIL_RECAP_MODEL` | Themenfeld-Rückblicke | `deepseek/deepseek-v4-pro` |
| `COUNCIL_QA_MODEL` | Antwort und vereinfachte Antwort von „Frag den Rat", Bericht der ausführlichen Recherche und Parteipositionen. Standardmäßig EU mit ZDR. Beim aktivierten Fallback außerhalb der EU entfällt die ZDR-Vorgabe (`llm.ZDR_VERZICHT`). | `openai/gpt-6-luna` (Denkaufwand: `low` für die Antwort, sonst Vorgabe des Anbieters; `llm.WEB_DENKAUFWAND`) |
| `COUNCIL_QA_EXPAND_MODEL` | „Frag den Rat": Frage-Analyse vor der Suche (Azure EU, mit ZDR); auch die Städte-Suchbegriffe | `openai/gpt-5.6-luna` |
| `COUNCIL_ASSISTANT_MODEL` | Lottis Erklärungen. Standardmäßig EU mit ZDR. Beim aktivierten Fallback außerhalb der EU entfällt die ZDR-Vorgabe (`llm.ZDR_VERZICHT`). | `openai/gpt-6-luna` (Denkaufwand: Vorgabe des Anbieters) |
| `COUNCIL_ASSISTANT_PRUEFER_MODEL` | Lottis Selbstprüfung: Prüfer-Modell einer anderen Familie, in der EU (`council/self_check.py`, Schalter `lotti-selbstpruefung`) | `anthropic/claude-haiku-5.5` |
| `COUNCIL_ASSISTANT_PRUEFER_ANTEIL` | Anteil der Erklärungen, die nachträglich geprüft werden (0–1) | `0.1` |
| `COUNCIL_DISTRICT_MODEL` | „Mein Viertel": Vorhaben aus Beschlüssen bündeln und einordnen (`council/viertel.py`) | `openai/gpt-6-luna` |
| `COUNCIL_QUIZ_MODEL` | Quizfragen erzeugen | `deepseek/deepseek-v4-pro` |
| `COUNCIL_QUIZ_VERIFY_MODEL` | Verify-Pass über erzeugte Quizfragen | `openai/gpt-4o-mini` |
| `COUNCIL_QUIZ_APPEAL_MODEL` | Richter: benotet, wie reizvoll eine Quizfrage ist | wie `COUNCIL_QUIZ_VERIFY_MODEL` |
| `COUNCIL_EMBED_MODEL` | Embeddings (fastembed, lokal) | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` |
| `COUNCIL_RERANK_MODEL` | Reranker für die hybride Suche | `jinaai/jina-reranker-v2-base-multilingual` |
| `COUNCIL_ALIAS_MODEL` | Prüft Themen-Dubletten (`council/aliases.py`) | `deepseek/deepseek-v4-pro` |
| `TOPIC_INTEL_MODEL` | Themen-Beschreibung und Relevanzprüfung (`council/topic_intel.py`, Azure EU) — bricht die `COUNCIL_`-Namenskonvention | `openai/gpt-5.6-luna` |
| `COUNCIL_WATCHER_MODEL` | Themen-Zuordnung des Watchers (`council/watcher.py`) | `openai/gpt-5.6-luna` |
| `COUNCIL_COMMITTEE_MODEL` | Ausschuss-Zusammenfassungen und Kurzfassungen je Tagesordnungspunkt (`council/committee_summary.py`) | `openai/gpt-6-luna` |
| `COUNCIL_SESSION_SUMMARY_MODEL` | Lottis Satz zur Sitzung (`council/session_summary.py`) | `openai/gpt-6-luna` |
| `COUNCIL_LOCATION_MODEL` | Ortsbezüge aus Beschlüssen (`council/locations.py`) | `google/gemini-3.1-flash-lite` |
| `COUNCIL_WORTBEITRAG_MODEL` | Wortbeiträge aus den Protokollen (`council/wortbeitraege.py`) | `openai/gpt-6-luna` |
| `COUNCIL_KRITIKER_MODEL` | Prüft jeden Kartentext, bevor er gespeichert wird (`council/kritiker.py`) | `openai/gpt-6-luna` |
| `COUNCIL_SOCIAL_MODEL` | Kartentext für Social Media (`council/social_text.py`) | `openai/gpt-6-luna` |
| `COUNCIL_DOSSIER_MODEL` | Dossier einer Vorlage (`council/template_dossier.py`) | `openai/gpt-6-luna` |
| `COUNCIL_MOTIONS_MODEL` | Änderungsanträge lesen (`council/motions.py`) | `openai/gpt-6-luna` |
| `COUNCIL_ARGUMENTS_MODEL` | Argumente zu einem Vorgang (`council/arguments.py`) | `openai/gpt-6-luna` |
| `COUNCIL_TERMS_MODEL` | Fachwörter aus der Vorlage vorschlagen (`council/vorlage_begriffe.py`) | `openai/gpt-6-luna` |
| `COUNCIL_TERMS_VERIFY_MODEL` | … und jede Erklärung prüfen; nur was besteht, erscheint | `openai/gpt-6-sol` |
| `COUNCIL_PROGRAM_MODEL` | Wahlprogramme zum Punkt einordnen (`council/programm_bezug.py`) | `openai/gpt-6-luna` |
| `COUNCIL_PROGRAM_VERIFY_MODEL` | … und jede Einordnung bestätigen | `openai/gpt-6-sol` |
| `COUNCIL_FINDINGS_MODEL` | Befunde aus den Grafiken des Vorberichts zum Haushaltsentwurf vorschlagen (`council/budget_findings.py`) | `openai/gpt-6-luna` |
| `COUNCIL_FINDINGS_VERIFY_MODEL` | … und jede Deutung prüfen; nur was besteht, erscheint | `openai/gpt-6-sol` |
| `COUNCIL_WEEK_NUMBER_MODEL` | Zahl der Woche für „Heute“ wählen und in Alltagssprache schreiben (`council/week_number.py`) | `openai/gpt-6-sol` |
| `COUNCIL_PAGE_QUESTIONS_MODEL` | Vorschlagsfragen auf Punkt- und Beschluss-Seite (`council/vorschlagsfragen.py`) | `openai/gpt-6-luna` |
| `COUNCIL_PLAN_MODEL` | Pläne der Stadt: Stand je Maßnahme, Umsetzung oder Erwähnung (`council/plan_judge.py`) | `openai/gpt-6-luna` |
| `COUNCIL_DEEP_MODEL` | Bericht der ausführlichen Recherche; leer heißt wie `COUNCIL_QA_MODEL` | leer |
| `COUNCIL_DEEP_PLUS_MODEL` | derselbe Bericht für Konten mit dem Recht `premium_models` | `openai/gpt-6-sol` |
| `COUNCIL_VIDEO_MODEL` | Abstimmungsergebnisse aus Sitzungs-Transkripten (`council/videos.py`) | `openai/gpt-5.6-luna` |
| `COUNCIL_STT_MODEL` | Transkription der Audio-Stücke, wenn kein Streaming-Schlüssel gesetzt ist (`council/livestream.py`) | `google/gemini-3.1-flash-lite` |
| `COUNCIL_LIVE_TRACKER_MODEL` | Live-Verfolgung: welcher Punkt läuft, wer spricht (`council/livetracker.py`) | `google/gemini-3.5-flash-lite` |
| `COUNCIL_OCR_MODEL` | Gescannte Anlagen lesen, Seite als Bild (`council/ocr.py`) | `google/gemini-3.1-flash-lite` |
| `COUNCIL_OCR_MODEL_ZWEIT` | Zweitleser für dieselbe Seite; Uneinigkeit ist ein Prüffall, kein Mittelwert | `anthropic/claude-sonnet-4.6` |
| `COUNCIL_QUIZ_MOTION_MODEL` | Quizfragen aus Anträgen (`council/quiz_formats.py`) | `openai/gpt-4o-mini` |

### Suche von „Frag den Rat“

Stellschrauben der hybriden Suche (`council/embeddings.py`). Sie sind gemessen
gesetzt; wer sie ändert, misst gegen das Gold-Set
([Frag den Rat](/docs/frag-den-rat/#rückmeldungen-und-messung)).

| Variable | Wofür | Default |
|---|---|---|
| `COUNCIL_RETRIEVAL_KLASSISCH` | `1` stellt die Suche ohne Vorlagenabschnitte wieder her. Wirkt ohne Neustart. | nicht gesetzt |
| `COUNCIL_PAIR_MAX_CHARS` | Zeichen-Deckel je Paar für den Reranker | `260` |
| `COUNCIL_KONTEXT_PAIR_MAX` | derselbe Deckel für die Zusatzkanäle (Presse, Wortbeiträge, Anlagen) | `150` |
| `COUNCIL_KONTEXT_RERANK_MIN` | Mindestwert des Rerankers, damit ein Zusatzkanal-Treffer in den Kontext kommt | `-1.5` |
| `COUNCIL_ZUSAGE_RERANK_MIN` | strengerer Mindestwert für Zusagen der Verwaltung | `-0.5` |
| `COUNCIL_RERANK_MAX` | Obergrenze der Reranker-Paare; `0` heißt keine. Nur für Notfälle | `0` |
| `COUNCIL_SERIE_MAX` | so viele Beschlüsse mit wortgleichem Titel bleiben vorn | `3` |
| `COUNCIL_WB_FRAKTION_POOL` | Kandidaten-Wortbeiträge für den Baustein „Das sagen die Parteien“ | `600` |
| `COUNCIL_WB_FRAKTION_LABELS` | Deckel auf die Zahl der Fraktions-Töpfe darin; mehr kostet Wartezeit | `20` |
| `COUNCIL_QA_PLAN_HASH_SALT` | Salz für den Hash, unter dem der Rechercheplan einer Frage protokolliert wird, damit das Log keine Frage im Klartext trägt | leer |

### Vorlagen aufbereiten: Kostengrenzen

| Variable | Wofür | Default |
|---|---|---|
| `DOSSIER_MAX_USD` | Kostengrenze der Dossiers je Lauf von `vorlagen_dossiers.py` | `0.5` |
| `DOSSIER_ABRUF_MAX_USD` | Tagesdeckel für Dossiers, die beim ersten Aufruf einer Seite nachgeholt werden | `0.2` |
| `TERMS_MAX_USD` | Kostengrenze der Fachwörter je Lauf (Schalter `begriffe-aus-vorlage`) | `0.25` |
| `PROGRAM_MAX_USD` | Kostengrenze der Wahlprogramm-Einordnungen je Lauf (Schalter `wahlprogramm-am-punkt`) | `0.25` |
| `FINDINGS_MAX_USD` | Kostengrenze der Befunde aus dem Vorbericht zum Haushaltsentwurf je Lauf (Schalter `haushaltsentwurf-befunde`) | `0.5` |

### Livestream und Live-Verfolgung

| Variable | Wofür | Default |
|---|---|---|
| `COUNCIL_STREAM_URL` | HLS-Adresse der Übertragung | `https://cdn.oeins.de/sd480/index.m3u8` |
| `COUNCIL_RECORD_MAX_HOURS` | Kappe des Sitzungs-Mitschnitts in Stunden | `6` |
| `COUNCIL_CHUNK_SECONDS` | Länge der Audio-Stücke ohne Streaming | `30` |
| `COUNCIL_CLOSING_MIN_SECONDS` | Frühestens nach so vielen Sekunden beendet die Schlussformel die Aufnahme; davor wäre es eine Wiederholung im Vorprogramm | 1.200 (20 Minuten) |
| `GLADIA_API_KEY` | Schlüssel für die Streaming-Transkription (`council/stream_stt.py`); leer heißt Audio-Stücke | leer |
| `GLADIA_REGION` | Region des Transkriptionsdienstes | `eu-west` |
| `COUNCIL_LIVE_WINDOW_SECONDS` | Takt der Live-Verfolgung beim Streaming | `15` |
| `COUNCIL_STT_BEHALTEN` | So viele Audio-Stücke je Sitzung bleiben als Referenz für die Transkriptions-Eval erhalten; `0` schaltet das ab | `20` |
| `RATSLOTSE_STT_AUDIO` | Ablageordner dieser Stücke | unter `data/` |

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
| `APPLE_BUNDLE_ID` | Erlaubter `aud`-Wert von „Sign in with Apple" in der nativen App | nein | `de.ratslotse.app` |
| `APPLE_SERVICE_ID` | Services-ID für den Apple-Web-Flow (`aud` des Browser-Tokens). **Leeren schaltet den Web-Login ab** — genau das war der Fehler, den #328 behoben hat. | nein | `de.ratslotse.web` |
| `APPLE_TEAM_ID` | Apple Developer Team-ID; für den Token-Widerruf bei Kontolöschung erforderlich | für App Store | – |
| `APPLE_KEY_ID` | Key-ID des „Sign in with Apple“-Schlüssels | für App Store | – |
| `APPLE_PRIVATE_KEY` | Inhalt des privaten `.p8`-Schlüssels als PEM; escaped `\\n` werden akzeptiert | für App Store | – |
| `LLM_BUDGET_MONTHLY` | Monatsbudget für die Budget-Ampel (reine Anzeige) | nein | `40.0` |
| `DISABLE_RATE_LIMIT` | `1` schaltet das Rate-Limiting ab (nur für Tests) | nein | nicht gesetzt |
| `SIGNUP_REQUIRES_APPROVAL` | `1`: Neue Konten beginnen gesperrt und werden im Admin-Panel freigeschaltet. So steht es auf dev, wo ohne Mailversand sonst jedes Konto sofort aktiv wäre | nein | aus |
| `FEATURE_FLAGS` | Kommaliste der eingeschalteten [Feature-Schalter](/docs/referenz/feature-schalter/); `*` schaltet alle an (so steht es auf dev) | nein | leer |
| `STATS_EXCLUDE_DOMAINS` | Kommaliste von Mail-Domains, deren Konten aus der Nutzungsstatistik fallen (eigene Testkonten) | nein | leer |
| `SOCIAL_API_TOKEN` | Token für die Schnittstelle des Social-Media-Bots (`routers/social.py`); ohne Token sind die Endpunkte aus | nein | leer |
| `SOCIAL_MEDIA_DIR` / `SOCIAL_MEDIA_BASE_URL` | Verzeichnis für Social-Media-Bilder und öffentliche Basis-URL. Der Upload legt das Verzeichnis bei Bedarf an. | nein | `web/frontend/public/social`, `https://ratslotse.de/social` |
| `BACKEND_URL` | Adresse des Backends für die Server-Routen des Frontends (`app/api/council/ask/route.ts`) | nein | `http://localhost:8000` |
| `NEXT_PUBLIC_CARTO_API_KEY` | Schlüssel der Kartenkacheln, zur **Bauzeit** des Frontends einkompiliert (`lib/basemap.ts`); ohne ihn tragen die Kacheln ein Wasserzeichen | nein | nicht gesetzt |
| `GEO_BUNDLE_VERSION` / `LOTTI_BUNDLE_VERSION` | Versionsmarken, die der Frontend-Build an die Adressen der Geodaten und der Lotti-Grafiken hängt, damit der Browser sie lange halten darf (`lib/asset-paths.ts`) | nein | nicht gesetzt |

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
| `FEEDBACK_EMAIL` | Empfänger*in des Nutzer-Feedbacks; zugleich die Antwortadresse der Rückmeldungen an die absendende Person | nein | leer → `WEB_ADMIN_EMAIL` |
| `EMAIL_REPLY_TO` | Antwortadresse aller Mails; ohne sie ginge eine Antwort an die Absenderadresse ohne Postfach | nein | leer |
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
| `BACKUP_ENV` | `0` nimmt die `.env` mit den Geheimnissen aus der Sicherung | nein | `1` |
| `RATSLOTSE_WEGWERF_NACHZIEHEN` | `0` hält den Herzschlag davon ab, die Wegwerf-Liste wöchentlich nachzuziehen (Tests, Rechner ohne Netz) | nein | `1` |
| `LLM_TAGESKOSTEN_ALARM_USD` | Der tägliche Überwachungsjob meldet Modellkosten des Vortags oberhalb dieses Schwellenwerts per E-Mail. `0` deaktiviert den Alarm. | nein | 5 $ |
| `WEEKLY_STEP_MAX_SECONDS` | Höchstdauer eines Schritts im Wochenlauf; ein Schritt darüber wird beendet und zählt als Fehlschlag, der Lauf geht weiter. `0` hebt sie auf | nein | 10.800 (3 h) |
| `WEEKLY_ENRICH_MAX_SECONDS` | Frist für den ganzen Wochenlauf; ein wartender Deploy beendet ihn ohnehin | nein | keine |
| `RATSLOTSE_RELEASE_MAINTENANCE` | `1` lässt genau einen Prozess durch die Wartungssperre des Prod-Deploys (`kern/maintenance.py`). Setzt nur `scripts/prepare_release_databases.py` für sich selbst; in eine `.env` gehört sie nicht | nein | nicht gesetzt |
| `ARCHIV_DIR` | Ordner des Archivs der gesicherten Quelldateien (`council/archiv.py`) | nein | `data/archiv` |
| `REGIONALSTATISTIK_USER` / `REGIONALSTATISTIK_PASSWORD` | Konto bei der Regionalstatistik für `scripts/ingest_regionalstatistik.py` | nur für diesen Ingest | — |
| `FASTEMBED_CACHE_PATH` | Persistenter Modell-Cache von fastembed (ohne ihn liegt er im Temp-Verzeichnis und ist nach einem Neustart weg) — von der Bibliothek selbst gelesen, nicht vom Repo-Code | nein | Vorgabe der Bibliothek |

### Wahlen

| Variable | Wofür | Pflicht | Default |
|---|---|---|---|
| `WAHLKAMPF_TOKEN` | Geheimer Link-Teil der Wahlkampf-Auswertung (`scripts/stichwahl_potenzial.py --link`); mindestens 16 Zeichen, sonst wird er aus `WEB_JWT_SECRET` abgeleitet | nein | abgeleitet |
| `WAHLTERMINE_URL` | Terminkalender des Votemanagers für `check_wahltermine.py`; leer = aus der Basis-URL der aktiven Wahl abgeleitet | nein | abgeleitet |
| `WAHLABEND_ELECTION` | Welche Wahl `/wahlabend` zeigt (Ordnername unter `kommunalwahl/wahlen/`); leer heißt die jüngste, die kein Entwurf mehr ist | nein | leer |

### Städte-Speicher (`check_cities.py`)

| Variable | Wofür | Pflicht | Default |
|---|---|---|---|
| `CITIES_DB` | Pfad zur Städte-Datenbank | nein | `data/cities.sqlite` |
| `CITIES_FILES_DIR` / `CITIES_RAW_DIR` | Ablage der geladenen Dokumente bzw. Rohantworten | nein | `data/cities-files`, `data/cities-raw` |
| `CITIES_MAX_USD` | Kostengrenze für den ganzen Lauf über alle Stufen; `0` hebt sie auf | nein | `2.0` |
| `CITIES_MAX_SECONDS` | Frist je Lauf in Sekunden; `0` hebt sie auf (Nachlauf von Hand) | nein | `14400` (4 h) |
| `CITIES_ANNOTATE_MAX` | Stückzahl je Lauf für die Einordnung (Deckel gegen den Rückstau) | nein | `3000` |
| `CITIES_REASON_MAX` | Abschnitte je Lauf für die Begründungen | nein | `400` |
| `CITIES_SINCE_DAYS` | Wie weit ein Lauf zurückschaut | nein | `60` |
| `CITIES_RATE_SECONDS` | Abstand zwischen zwei Abrufen bei einem fremden Ratsinformationssystem (mindestens 1 s) | nein | `1.0` |
| `CITIES_FIT_WORKERS`, `CITIES_TERM_WORKERS`, `CITIES_IDEA_FIT_WORKERS`, `CITIES_STANCE_WORKERS` | Gleichzeitige Urteile je Stufe — mehr ist schneller, nicht teurer | nein | `8`, `16`, `4`, `12` |
| `CITIES_FIT_VOTES` / `CITIES_FIT_PROBE` | Stimmen je Urteil bzw. Stichprobengröße der Selbstkontrolle | nein | `3` / `300` |
| `CITIES_CLASSIFY_MODEL`, `CITIES_FIT_MODEL`, `CITIES_CLUSTER_MODEL`, `CITIES_STANCE_MODEL`, `CITIES_REASON_MODEL`, `CITIES_EFFORT_MODEL`, `CITIES_IDEA_FIT_MODEL` | Modell je Stufe | nein | `deepseek/deepseek-v4-flash` |
| `CITIES_LLM_TIMEOUT` | Zeitgrenze je Modellaufruf in Sekunden | nein | `120` |

### Messläufe und Werkzeuge

Nur für Eval-Läufe und Werkzeuge von Hand; kein Dienst liest sie.

| Variable | Wofür | Default |
|---|---|---|
| `COUNCIL_GOLD_JUDGE_MODEL` | Richter-Modell der Gold-Läufe (`scripts/eval_deep_gold.py`) | `anthropic/claude-opus-5.5` |
| `GOLD_OHNE_RICHTER` | `true` lässt den Gold-Lauf von „Frag den Rat“ ohne Richter laufen | nicht gesetzt |
| `COUNCIL_QUALITY_JUDGE_MODEL` | Richter der Qualitäts-Suite (`eval/quality_qa.py`) | `google/gemini-3.5-flash` |
| `RATSLOTSE_TRANSKRIPTE` | Ordner der Referenz-Transkripte für die Transkriptions-Eval | unter `data/` |
| `VIERTEL_POC_MODEL` | Modell des Probe-Skripts `scripts/viertel_poc.py` | `openai/gpt-5.6-luna` |
| `LOTTI_STUDIO` | Checkout des Grafik-Studios, nur zum Rendern der Mail-Bilder (`scripts/mail_helden/bauen.py`) | im Heimatordner |
| `RATSLOTSE_SOCIAL` | Checkout von `ratslotse-social`, aus dem `scripts/brand_icons.py` App-Icon, Favicons, Mail-Logo und Vorschaubilder setzt (auch `ios/scripts/make_splash.py`) | neben diesem Repo |

:::tip
Wer nur lokal entwickelt, braucht davon fast nichts: `OPENROUTER_API_KEY` für
echte LLM-Aufrufe, `WEB_JWT_SECRET` plus `COOKIE_SECURE=false` fürs Backend
über HTTP. Alles andere hat brauchbare Defaults.
:::

## Heim-Proxy gegen Adress-Sperren

Manche Ziele sperren den ganzen Hetzner-Adressbereich: das Geoportal der
Stadt (`gisportal4ol.oldenburg.de`) schließt Verbindungen ohne Antwort,
YouTube blockt Rechenzentrums-Bereiche generell. Beides trifft jeden
Hetzner-Kunden, nicht diesen Server, und beides löst sich, sobald die
Anfrage von einem Privatanschluss kommt.

Dafür hängen Prod und Dev seit 09/2026 in einem Tailscale-Netz zusammen mit
einem Synology-NAS, auf dem ein SOCKS5-Proxy als Container läuft — erreichbar
nur über das Tailnet, nicht aus dem Internet. Zwei Variablen in der `.env`
schalten den Umweg ein:

```
RATSLOTSE_PROXY_URL=socks5h://nutzer:passwort@100.118.52.13:1080
RATSLOTSE_PROXY_HOSTS=gisportal4ol.oldenburg.de,youtube.com
```

Nur Anfragen an die genannten Hosts und deren Subdomains laufen über den
Proxy (`kern/proxy.py`). Andere Anfragen laufen direkt. Ohne die Variablen
verbindet sich Ratslotse mit allen Zielen direkt. Fällt der konfigurierte
Proxy aus, scheitert der Abruf ohne direkten Fallback und der Wochenlauf
meldet den Fehler.

Wer den Umweg braucht: `scripts/fetch_bplan_outlines.py` (Bebauungsplan-
Umringe, wöchentlich) und der Video-Abruf per yt-dlp in `council/videos.py`.
Ein neues Ziel kommt in `RATSLOTSE_PROXY_HOSTS` und ruft an der Aufrufstelle
`proxies_for(url)` (requests) bzw. `proxy_for(url)` (Kommandozeile) auf.

Fallen: Der Geräteschlüssel eines Tailscale-Geräts läuft nach 180 Tagen ab —
in der Tailscale-Verwaltung für jedes Gerät „Disable key expiry" setzen. Das
NAS war genau daran vier Wochen lang aus dem Netz gefallen. Die Tailscale-
Paketoberfläche auf dem NAS ist über QuickConnect gesperrt; Neuanmelden geht
über den Aufgabenplaner als root mit `tailscale up --reset --authkey=…`.
