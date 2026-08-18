---
title: Release-Dossier v1.13.0
description: Was ein Release von dev nach main mitbringen würde — beschrieben, nicht ausgeführt.
---

Dieses Dossier beschreibt, **was passieren würde**, wenn `dev` nach `main`
ginge. Es führt nichts aus: Der Versionsschnitt und der Tag gehören in den
Release-PR, und ob und wann der kommt, entscheidet Tim.

Stand: 18.08.2026 · letzter Tag `v1.12.0` · **153 Commits** auf `dev`, die
`main` nicht hat · **57 offene Changelog-Fragmente** (23 hinzugefügt,
20 geändert, 14 behoben).

## Die kurze Antwort für Ungeduldige

Ein Release wäre **sicher, aber weitgehend unsichtbar**. Der größte Teil der
153 Commits liegt im Haushalts-Bereich, und der ist auf Prod durch das
Umgebungs-Gate ein 404 (`lib/haushalt-frei.ts`, Tims Entscheidung vom
16.08.2026). Sichtbar würde vor allem, was **außerhalb** von `/haushalt`
liegt.

## Was auf Prod tatsächlich sichtbar würde

| Was | Wo | Woran man es merkt |
|---|---|---|
| Anschlussstelle vom Beschluss in den Haushalt | Beschluss-Seiten | **Nichts** — die Karte hängt an `HAUSHALT_FREI` und bleibt auf Prod aus |
| Drei neue Quizfragen | Quiz | Ja — aber erst nach dem Backfill (s. u.) |
| Siebzehn neue Glossar-Begriffe | überall, wo Text sie trifft | Ja, sofort |
| KI-Frage: drei Schuldenzahlen, Bilanz, Kassensicht, Nachbewilligungen, Kennzahlen | Frag den Rat | **Nein** — die Tabellen entstehen auf Prod leer (s. u.) |
| Produkt-Steckbrief öffnet an der Karte | `/haushalt/produkte` | Nein (gegated) |
| Grafik-Baukasten: Reihenbruch, Annotations-Chips, Ableseleiste | alle Grafiken | Ja, wo Grafiken außerhalb `/haushalt` stehen |

## Die drei Dinge, die vor einem Release geklärt sein müssen

### 1. Auf Prod laufen keine Haushalts-Ingests

Die neuen Tabellen (`council_kennzahlen`, `council_kennzahl_formeln`,
`council_anlagenspiegel`, `council_vermoegensgruppen`,
`council_buergschaften`, `council_integrierte_schulden`) werden beim ersten
Start **angelegt und bleiben leer** — Prod hat weder die Ingest-Skripte im
Cron noch `check_finanzdaten`. Das ist so gewollt und kein Fehler; die
API-Routen antworten entsprechend leer statt falsch.

**Folge für die KI-Frage:** Die neuen Facetten greifen auf Prod ins Leere.
Eine Frage nach dem Eigenkapital bekommt dort keinen Bilanz-Block — sie
bekommt aber auch keinen falschen. `_sicher()` fängt das ab.

### 2. Die drei Quizfragen brauchen einen Backfill

`build_abschluss_questions` liefert nur, was belegt ist. Auf einer Prod-DB
ohne Jahresabschluss-Daten kommt **nichts** zurück, und das Quiz bleibt wie
es ist. Sollen die Fragen dort erscheinen, braucht Prod die Daten — also
entweder den Ingest oder einen Übertrag. **Das ist eine Entscheidung, keine
Aufgabe:** Sie hängt daran, ob der Haushalts-Bereich auf Prod überhaupt
kommen soll.

### 3. Der Versionsschnitt selbst

```bash
.venv/bin/python scripts/changelog_schnitt.py 1.13.0 --trocken   # erst schauen
.venv/bin/python scripts/changelog_schnitt.py 1.13.0
git tag -a v1.13.0 -m "…" && git push origin v1.13.0
```

Der Schnitt hängt an jedes der 57 Fragmente die PR-Nummer aus dem
Squash-Commit, der es angelegt hat, sortiert sie unter `## [1.13.0] – Datum`
und löscht die Fragmente. **Das gehört in den Release-PR**, nicht davor.

## Was der Release am Server verändert

Nachgemessen gegen `v1.12.0`, nicht angenommen — die erste Fassung dieses
Abschnitts behauptete „keine neuen Abhängigkeiten, kein ALTER, kein DROP" und
lag bei beidem daneben.

**Ein DROP, und er ist gewollt.** `council_ergebnisrechnung` bekam mit den
Teil-Ergebnisrechnungen `thh_nr` in den Primärschlüssel, und SQLite kann einen
Primärschlüssel nicht per `ALTER TABLE` erweitern. `_migrate()` prüft deshalb
auf die fehlende Spalte und legt die Tabelle **neu an**. Das ist gefahrlos,
aber es muss jemand wissen: Der Inhalt stammt vollständig aus
`council_anlagen` und wird vom Ingest in Sekunden wiederhergestellt — **auf
Prod passiert dabei nichts, weil die Tabelle dort leer ist.** Die übrigen
Schema-Änderungen sind `ALTER TABLE … ADD COLUMN` und `CREATE TABLE IF NOT
EXISTS`, beides ohne Datenverlust.

**Acht neue Frontend-Pakete**, alle aus derselben Familie: `d3-array`,
`d3-hierarchy`, `d3-scale`, `d3-shape` und ihre vier `@types`-Pakete. Sie sind
die Rechen-Hälfte des Grafik-Baukastens (Skalen, Pfade, Baumkarten) —
**Renderer bringt keines davon mit**, gezeichnet wird weiter mit eigenem JSX.
Der Deploy installiert sie über `npm ci` von selbst.

`requirements-dev.txt` hat `ruff` dazubekommen; die Laufzeit-Abhängigkeiten
des Backends sind unverändert.

Nicht dabei: **keine neuen Umgebungsvariablen** (die `.env` auf dem Server
bleibt unberührt) und **kein neuer Cron** — `check_finanzdaten` deckt die neue
Schicht automatisch ab, weil sie in `finanzquellen.REIHENFOLGE` steht.

## Der Weg, wenn es losgeht

1. PR `dev` → `main` mit **Merge-Commit, nicht squashen** (sonst divergieren
   die Branches dauerhaft).
2. Versionsschnitt + Tag **in diesem PR**.
3. Nach dem Merge deployt `deploy.yml` von selbst; `.env`, `data/` und
   `.venv/` bleiben unberührt.
4. Danach: TestFlight-Build koppeln (die iOS-App zieht dieselbe API).

## Offene Entscheidungen, die niemand außer Tim treffen kann

- Kommt der Haushalts-Bereich auf Prod, oder bleibt das Gate?
- Wenn ja: Bekommt Prod die Ingests als Cron, oder wird die Datenbank
  übertragen?
- Sollen die drei neuen Quizfragen auf Prod erscheinen (setzt Punkt 2 voraus)?
