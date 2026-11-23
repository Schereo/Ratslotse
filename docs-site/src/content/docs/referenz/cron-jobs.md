---
title: "Referenz: Cron-Jobs"
description: Alle geplanten Jobs mit Takt und Überfällig-Schwelle, erzeugt aus kern/jobs.py.
sidebar:
  label: "Cron-Jobs"
---

<!-- Erzeugt von scripts/docs_reference.py — nicht von Hand ändern. -->

Diese Seite entsteht aus `kern/jobs.py` (`python scripts/docs_reference.py`). Wer sie von Hand ändert, verliert die Änderung beim nächsten Lauf; `tests/test_docs_current.py` hält sie gegen das Register.

Die Zeitpläne selbst stehen in der crontab des Servers, nicht im Repo. Das Register ist ihre lesbare Entsprechung: Es speist die Überfällig-Ampel im Admin-Panel (*Statistik → Cron-Jobs*) und den täglichen Herzschlag, der schweigende Jobs meldet. Wie die Jobs zusammenhängen, steht unter [Betrieb](/docs/betrieb/#geplante-jobs-cron).

| Job | Was er tut | Takt | Überfällig nach |
|---|---|---|---|
| `scripts/check_committees.py` | **Gremien & Terminplan.** Gremienliste, Sitzungskalender, Ausschuss-Benachrichtigungen und die Tragweite neuer Tagesordnungspunkte. | täglich 7 Uhr | 30 h |
| `scripts/check_council.py` | **Sitzungen & Themen-Alarme.** Tagesordnungen der nächsten 3 Monate, Klassifikation und Benachrichtigungen zu eigenen Themen. | täglich 8 und 14 Uhr | 26 h |
| `scripts/check_protocols.py` | **Protokolle & Beschlüsse.** Neue Protokolle, Beschluss-Klassifikation, Vorlagen-Volltexte, „Einfach erklärt“ und Scores. | täglich 9 Uhr | 30 h |
| `scripts/check_council_videos.py` | **Video-Ergebnisse (vorläufig).** Abstimmungsergebnisse aus der O1-Aufzeichnung der Ratssitzung — als vorläufiger Stand, bis das Protokoll kommt. | täglich 10:30 Uhr | 30 h |
| `scripts/record_council_livestream.py` | **Livestream-Mitschnitt (Rat).** Schneidet die Ratssitzung live aus dem O1-Stream mit, verfolgt dabei, welcher TOP gerade läuft und wer spricht (Live-Karte), und liest die Abstimmungsergebnisse noch am Sitzungsabend — an Tagen ohne Ratssitzung ein Leerlauf. | täglich 13 Uhr UTC (14/15 Uhr lokal) | 30 h |
| `scripts/abendmeldungen.py` | **Abend-Anlässe (30a).** N5 Vorabend-Erinnerung (täglich) und N6 Wochenüberblick (sonntags). | täglich 18 Uhr | 30 h |
| `scripts/check_vorlage_follows.py` | **Verfolgte Vorgänge.** Neue Beratungsstationen zu Vorlagen, denen jemand folgt. | täglich 9:30 Uhr | 30 h |
| `scripts/vorlagen_dossiers.py` | **Dossiers der Vorlagen.** Aus den Unterlagen: holt nachgetragene Vorlagen und Punkt-Texte, dann Dossiers für die Vorlagen von drei Tagen zurück bis 21 Tage voraus (belegt, Kostengrenze je Lauf). | täglich 10 und 15 Uhr | 30 h |
| `scripts/antraege_nachzuegler.py` | **Änderungsanträge (Nachzügler).** An Sitzungstagen und am Tag davor: Tagesordnung neu lesen, neue Anträge laden und lesen. | täglich 11, 13, 16, 18 Uhr | 30 h |
| `scripts/check_presse.py` | **Stadt-Quellen (Presse + Beteiligung).** RSS-Abgleich der städtischen Pressemitteilungen und der laufenden Bauleitplan-Beteiligungen. | täglich 5:15 Uhr | 30 h |
| `scripts/check_cities.py` | **Andere Städte.** Werktags Oldenburg aus der eigenen Rats-Datenbank übernehmen und einbetten (ohne Netz und Modell) — daraus entsteht „Anderswo“ unter neuen Beschlüssen. Sonntags zusätzlich Vorlagen, Sitzungen und Ergebnisse der Vergleichsstädte, Einordnung, Ideen-Gruppen und die Urteile über Oldenburg, gedeckelt auf CITIES_MAX_USD. | werktags 10:15 Uhr (nur Oldenburg), sonntags 5 Uhr (alles) | 30 h |
| `scripts/social_kartentexte.py` | **Kartentexte (Tagesordnung).** Ein erklärender Satz je inhaltlichem Tagesordnungspunkt der nächsten drei Wochen — der einzige Text, der die ganze Vorlage samt Anlagen liest. Kostet LLM, schreibt nie zweimal dasselbe. | täglich 7:45 Uhr | 30 h |
| `scripts/render_plaene.py` | **Planzeichnungen rendern.** Neue Bauleitplan-Anlagen (Planzeichnung, Lageplan, …) als Bilder für die Beschluss-Seite. | sonntags 4:30 Uhr | 192 h |
| `scripts/check_finanzdaten.py` | **Haushaltsdaten.** Neue Jahresabschlüsse, Teilhaushalts-Pläne und Prüfberichte aus dem Anlagenbestand; ruft die Ingest-Skripte von Vollzug, Satzung, Gebühren und Wirtschaftsplänen, sobald ein neues Dokument da ist — plus Hinweis, wenn ein Jahrgang ausbleibt. | sonntags 6:00 Uhr | 192 h |
| `scripts/check_beteiligungsbericht.py` | **Beteiligungsbericht.** Lädt die Beteiligungsberichte von oldenburg.de und liest Gesellschaften, Aufsichtsorgane und Kennzahlen daraus. | sonntags 6:30 Uhr | 192 h |
| `scripts/archive_statistik.py` | **Statistik-Archiv.** Sichert Jahrbuch-Tabellen, Open-Data-Dateien und die KFA-Tabellen des Landes versioniert unter data/archiv/ — bevor die nächste Ausgabe sie überschreibt. | täglich 4 Uhr | 30 h |
| `scripts/weekly_enrich.py` | **Wöchentliche Anreicherung.** Entitäten, Geocoding, Embeddings, Rückblicke, Interessantheit und Tragweite in Tranchen. | sonntags 3 Uhr | 192 h |
| `scripts/remind_setup.py` | **Erinnerung an die Einrichtung.** Einmalige Service-Mail an Konten, die den Einrichtungs-Assistenten angefangen und nicht beendet haben. | täglich 11 Uhr | 30 h |
| `scripts/backup_db.py` | **Datenbank-Backup.** Nächtliche Sicherung aller Datenbanken, der .env, der crontab und unersetzlicher Dateien, gespiegelt auf die Storage Box. | täglich 3 Uhr | 30 h |
| `scripts/speicherfristen.py` | **Speicherfristen.** Löscht Recherchen von Konten ohne Einwilligung ins Speichern sieben Tage nach ihrem letzten Stand (Datenschutzerklärung, Store.DEEP_JOB_FRIST_TAGE). | täglich 4:40 Uhr | 30 h |
| `scripts/check_wahltermine.py` | **Wahltermine der Stadt.** Vergleicht den Terminkalender des Votemanagers mit kommunalwahl/wahlen/ — meldet eine Wahl, die wir nicht kennen, und eine Wahl-Id, die endlich da ist (oder kurz vor dem Wahltag immer noch fehlt). | täglich 6:15 Uhr | 30 h |
| `scripts/check_herzschlag.py` | **Herzschlag.** Meldet Jobs, die nicht mehr laufen, einen vollen Datenträger, auffällige Registrierungen und Verstöße gegen die Datenregeln (council/datenpruefung.py). Ein Job, der gar nicht startet, stürzt auch nicht ab — und Konten, die ihre Adresse nie bestätigen, lösen keine einzige Mail aus. | täglich 6:30 Uhr | 30 h |

22 Jobs. „Überfällig nach“ ist bewusst großzügiger als der Abstand zweier Läufe, damit ein einzelner verspäteter Lauf keinen Alarm auslöst. Ein pausierter Job darf schweigen: keine Ampel, keine Mail.
