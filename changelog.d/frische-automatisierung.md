---
kategorie: geaendert
---

**Neue Haushaltsdokumente werden von allein eingelesen.** Der Datenstand-Cron hat vier Schichten aus dem Ratsinformationssystem bisher nur beobachtet und gemeldet, wenn ein Jahrgang ausblieb — Haushaltsvollzug, Haushaltssatzung, Gebührenbedarf und Wirtschaftspläne kamen erst, wenn jemand das Skript von Hand startete. Jetzt merkt sich der Cron je Schicht, welches Dokument ihr Skript zuletzt gesehen hat, und ruft es, sobald ein jüngeres im Bestand liegt. Ein gescheiterter Lauf wird gemeldet und beim nächsten Mal wiederholt.
