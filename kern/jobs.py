"""Registry der Cron-Jobs — was läuft, wie oft, und ab wann ist es überfällig.

Die Zeitpläne stehen in der crontab auf dem Server, nicht im Repo; diese Liste
ist ihre lesbare Entsprechung fürs Admin-Panel. Wer einen Cron-Eintrag ändert,
zieht ``schedule``/``max_age_h`` hier nach — sonst schlägt die Überfällig-Ampel
falsch an. ``max_age_h`` ist bewusst großzügiger als der Abstand zweier Läufe,
damit ein einzelner verspäteter Lauf nicht sofort Alarm auslöst.
"""
from __future__ import annotations

JOBS: list[dict] = [
    {
        "key": "check_committees",
        "label": "Gremien & Terminplan",
        "description": "Gremienliste, Sitzungskalender, Ausschuss-Benachrichtigungen und die Tragweite neuer Tagesordnungspunkte.",
        "schedule": "täglich 7 Uhr",
        "max_age_h": 30,
    },
    {
        "key": "check_council",
        "label": "Sitzungen & Themen-Alarme",
        "description": "Tagesordnungen der nächsten 3 Monate, Klassifikation und Benachrichtigungen zu eigenen Themen.",
        "schedule": "täglich 8 und 14 Uhr",
        "max_age_h": 26,
    },
    {
        "key": "check_protocols",
        "label": "Protokolle & Beschlüsse",
        "description": "Neue Protokolle, Beschluss-Klassifikation, Vorlagen-Volltexte, „Einfach erklärt“ und Scores.",
        "schedule": "täglich 9 Uhr",
        "max_age_h": 30,
    },
    {
        "key": "abendmeldungen",
        "label": "Abend-Anlässe (30a)",
        "description": "N5 Vorabend-Erinnerung (täglich) und N6 Wochenüberblick (sonntags).",
        "schedule": "täglich 18 Uhr",
        "max_age_h": 30,
    },
    {
        "key": "check_vorlage_follows",
        "label": "Verfolgte Vorgänge",
        "description": "Neue Beratungsstationen zu Vorlagen, denen jemand folgt.",
        "schedule": "täglich 9:30 Uhr",
        "max_age_h": 30,
    },
    {
        "key": "check_presse",
        "label": "Stadt-Quellen (Presse + Beteiligung)",
        "description": "RSS-Abgleich der städtischen Pressemitteilungen und der laufenden Bauleitplan-Beteiligungen.",
        "schedule": "täglich 5:15 Uhr",
        "max_age_h": 30,
    },
    {
        "key": "render_plaene",
        "label": "Planzeichnungen rendern",
        "description": "Neue Bauleitplan-Anlagen (Planzeichnung, Lageplan, …) als Bilder für die Beschluss-Seite.",
        "schedule": "sonntags 4:30 Uhr",
        "max_age_h": 8 * 24,
    },
    {
        "key": "check_finanzdaten",
        "label": "Haushaltsdaten",
        "description": "Neue Jahresabschlüsse, Teilhaushalts-Pläne und Prüfberichte aus dem Anlagenbestand — plus Hinweis, wenn ein Jahrgang ausbleibt.",
        # Bestandsgesteuert, nicht kalendergesteuert: Der Takt bestimmt nur,
        # wie schnell ein neuer Jahrgang auf der Seite steht (s. Skript-Kopf).
        #
        # Läuft vorerst NUR auf der Dev-VM: Der Haushalts-Bereich steht hinterm
        # Umgebungs-Gate (web/frontend/lib/haushalt-frei.ts), auf Prod bleiben
        # seine Tabellen leer. In der Cron-Übersicht erscheint der Job dort
        # deshalb als „unknown" (nie gelaufen) — nicht als überfällig; die
        # Ampel kennt „stale" nur für Jobs mit mindestens einem Lauf.
        "schedule": "alle zwei Wochen, sonntags 4:30 Uhr",
        "max_age_h": 16 * 24,
    },
    {
        "key": "check_beteiligungsbericht",
        "label": "Beteiligungsbericht",
        "description": "Lädt die Beteiligungsberichte von oldenburg.de und liest Gesellschaften, Aufsichtsorgane und Kennzahlen daraus.",
        # Der zweite Cron des Haushalts-Bereichs, und der einzige, der selbst
        # herunterlädt. Bestandsgesteuert wie check_finanzdaten — der Takt
        # bestimmt nur, wie schnell ein neuer Bericht auf der Seite steht, und
        # die Quelle erscheint einmal im Jahr.
        "schedule": "alle vier Wochen, sonntags 4:45 Uhr",
        "max_age_h": 30 * 24,
    },
    {
        "key": "archive_statistik",
        "label": "Statistik-Archiv",
        "description": "Sichert Jahrbuch-Tabellen, Open-Data-Dateien und die KFA-Tabellen des Landes versioniert unter data/archiv/ — bevor die nächste Ausgabe sie überschreibt.",
        # Täglich, obwohl sich täglich nichts ändert: Die Quellen aktualisieren
        # in Schüben (29 Open-Data-Datensätze am 19.06.2026, 20 am 14.07.2026),
        # und weil es kein Archiv gibt, ist Vorlauf der einzige Puffer. Ein Lauf
        # ohne Änderung kostet bedingte Abrufe und praktisch keine Bytes.
        "schedule": "täglich 4 Uhr",
        "max_age_h": 30,
    },
    {
        "key": "weekly_enrich",
        "label": "Wöchentliche Anreicherung",
        "description": "Entitäten, Geocoding, Embeddings, Rückblicke, Interessantheit und Tragweite in Tranchen.",
        "schedule": "sonntags 3 Uhr",
        "max_age_h": 8 * 24,
    },
    {
        "key": "remind_setup",
        "label": "Erinnerung an die Einrichtung",
        "description": "Einmalige Service-Mail an Konten, die den Einrichtungs-Assistenten angefangen und nicht beendet haben.",
        "schedule": "täglich 11 Uhr",
        "max_age_h": 30,
    },
    {
        "key": "backup_db",
        "label": "Datenbank-Backup",
        "description": "Nächtliche Sicherung beider SQLite-Dateien, optional gespiegelt auf die Storage Box.",
        "schedule": "täglich 3 Uhr",
        "max_age_h": 30,
    },
]

BY_KEY = {j["key"]: j for j in JOBS}
