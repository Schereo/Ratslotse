---
title: "Referenz: Rollen und Rechte"
description: Alle Rollen und die Rechte, die sie bündeln, erzeugt aus kern/roles.py.
sidebar:
  label: "Rollen und Rechte"
---

<!-- Erzeugt von scripts/docs_reference.py — nicht von Hand ändern. -->

Diese Seite entsteht aus `kern/roles.py` (`python scripts/docs_reference.py`). Wer sie von Hand ändert, verliert die Änderung beim nächsten Lauf; `tests/test_docs_current.py` hält sie gegen das Register.

Ein Konto trägt mehrere Rollen (Tabelle `web_user_roles`), jede Rolle bündelt Rechte. Geprüft wird immer gegen ein **Recht**, nie gegen einen Rollennamen: im Backend über `Depends(require_permission("…"))`, im Web über `lib/rechte.ts`, in der App über `User.can(_:)`. Eine neue Rolle ist damit ein Eintrag im Register, ohne Frontend-Release und ohne App-Update.

## Rollen

| Rolle | Was sie darf | Rechte |
|---|---|---|
| **Nutzer\*in** (`user`) | Der Standard: Ratsinhalte, eigene Themen, Benachrichtigungen, KI-Frage und der Haushalts-Bereich. Jedes Konto hat sie; im Admin-Panel wird sie nicht vergeben. | `budget` |
| **Recherche Plus** (`research_plus`) | Die ausführliche Recherche schreibt ihren Bericht mit einem größeren, gründlicheren Modell. Wird zusätzlich zu einer anderen Rolle vergeben; das Tageskontingent bleibt gleich. | `premium_models` |
| **MCP-Zugang** (`mcp_access`) | Darf persönliche Schlüssel für den MCP-Server ausstellen und damit einen eigenen Agenten (Claude, ChatGPT, Cursor …) an die Ratsdaten anschließen — lesend, ohne Haushalt. Wird zusätzlich zu einer anderen Rolle vergeben. | `mcp` |
| **Fachpublikum** (`expert`) | Zusätzlich der Haushalts-Bereich mit allen Zahlen, Belegen und Auswertungen. Benachrichtigungen bleiben die normalen — wer hier Tagesordnungen will, schaltet sie selbst ein. | `budget` |
| **Ratsmitglied** (`council_member`) | Zusätzlich der Haushalts-Bereich mit allen Zahlen, Belegen und Auswertungen, die Werkzeuge für die Ratsarbeit (etwa der Mehrheitsrechner); Benachrichtigungen ab Werk vollständig. | `budget`, `mandate`, `council_tools` |
| **Admin** (`admin`) | Das Admin-Panel und jedes andere Recht — Admins sehen alles. | `budget`, `mandate`, `premium_models`, `mcp`, `council_tools`, `admin` |

## Rechte

| Recht | Rollen, die es tragen |
|---|---|
| `budget` | Nutzer\*in, Fachpublikum, Ratsmitglied, Admin |
| `mandate` | Ratsmitglied, Admin |
| `premium_models` | Recherche Plus, Admin |
| `mcp` | MCP-Zugang, Admin |
| `council_tools` | Ratsmitglied, Admin |
| `admin` | Admin |

Die Rolle `user` hat jedes Konto, auch ohne Zeile in `web_user_roles`; ihre Rechte gelten damit für alle. Admins erben jedes Recht, auch später hinzukommende. `web_users.role` ist nur noch ein abgeleitetes Schaufenster für ältere App-Builds und nie die Grundlage einer Rechteprüfung.
