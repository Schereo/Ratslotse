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
        "description": "Gremienliste, Sitzungskalender und Ausschuss-Benachrichtigungen.",
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
        "key": "weekly_enrich",
        "label": "Wöchentliche Anreicherung",
        "description": "Entitäten, Geocoding, Embeddings, Rückblicke, Interessantheit und Tragweite in Tranchen.",
        "schedule": "sonntags 3 Uhr",
        "max_age_h": 8 * 24,
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
