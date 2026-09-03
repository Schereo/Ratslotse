"""Rollen und Rechte eines Kontos — die eine Quelle für beide Frontends.

Ein Konto trägt **mehrere** Rollen (Tabelle ``web_user_roles``); jede Rolle
bündelt eine Menge von **Rechten**. Geprüft wird immer gegen ein Recht, nie
gegen einen Rollennamen:

    if "budget" in permissions_for(user["roles"]): ...

Der Unterschied ist der ganze Zweck dieser Datei. Ein ``role == "admin"``
verstreut über Router und zwei Frontends heißt, dass jede neue Rolle an
dreißig Stellen nachgezogen werden muss — und die Stelle, die man vergisst,
meldet sich nicht, sie lässt einfach jemanden rein oder sperrt ihn aus. Ein
Recht dagegen wird einmal hier vergeben; wer es hat, ergibt sich.

Deshalb schickt ``/auth/me`` auch die **Rechte** mit und nicht nur die Rollen:
Die Clients sollen `hatRecht(user, "budget")` fragen können, ohne zu wissen,
welche Rollen es überhaupt gibt. Eine neue Rolle ist damit ein Eintrag in
``ROLES`` — ohne Frontend-Release, ohne App-Update im Store.
"""
from __future__ import annotations

from dataclasses import dataclass, field

#: Alle Rechte, die es gibt. Die Liste ist bewusst kurz und grob: Ein Recht
#: beschreibt einen ganzen Bereich, keinen einzelnen Endpunkt. Feiner
#: geschnitten wird erst, wenn sich zwei Rollen innerhalb eines Bereichs
#: wirklich unterscheiden — vorher ist es Verwaltung ohne Nutzen.
#:
#: - ``budget``: der Haushalts-Bereich (20 Seiten, 20 API-Routen)
#: - ``admin``:  das Admin-Panel samt allem darunter
PERMISSIONS: tuple[str, ...] = ("budget", "admin")


@dataclass(frozen=True)
class Role:
    key: str
    #: Anzeigename — steht so im Admin-Panel und in der App.
    label: str
    #: Ein Satz, der erklärt, was die Rolle darf. Menschentext, kein Bezeichner.
    description: str
    permissions: frozenset[str] = field(default_factory=frozenset)
    #: Rollen, die jedes Konto ohnehin hat, tauchen in der Verwaltung nicht als
    #: vergebbare Kästchen auf.
    assignable: bool = True


#: Die Rolle, die jedes Konto hat — auch ohne Zeile in ``web_user_roles``.
#: Sie trägt bewusst KEINE Rechte: Was alle dürfen, hängt an ``require_active``
#: und braucht kein Recht. Sie steht hier, damit „Nutzer*in" ein Name mit
#: Bedeutung ist und nicht die Abwesenheit von Rollen.
DEFAULT_ROLE = "user"

ROLES: dict[str, Role] = {
    "user": Role(
        key="user",
        label="Nutzer*in",
        description="Der Standard: Ratsinhalte, eigene Themen, Benachrichtigungen, KI-Frage.",
        permissions=frozenset(),
        assignable=False,
    ),
    "council_member": Role(
        key="council_member",
        label="Ratsmitglied",
        description="Zusätzlich der Haushalts-Bereich mit allen Zahlen, Belegen und Auswertungen.",
        permissions=frozenset({"budget"}),
    ),
    "admin": Role(
        key="admin",
        label="Admin",
        description="Das Admin-Panel und jedes andere Recht — Admins sehen alles.",
        # Admin erbt ALLE Rechte, auch später hinzukommende. Eine Aufzählung
        # hier wäre eine zweite Liste, die beim nächsten Recht vergessen wird
        # und dann still einen Admin aussperrt.
        permissions=frozenset(PERMISSIONS),
    ),
}

#: Die Reihenfolge, in der Rollen angezeigt und in die Kompatibilitäts-Spalte
#: `web_users.role` geschrieben werden — schwächste zuerst.
ROLE_ORDER: tuple[str, ...] = ("user", "council_member", "admin")


def known_roles(roles) -> list[str]:
    """Aus einer beliebigen Menge die bekannten Rollen, in fester Reihenfolge.

    Unbekannte Werte fliegen raus statt zu werfen: In einer gewachsenen
    Datenbank kann eine abgeschaffte Rolle stehen, und ein 500er beim Anmelden
    wäre der schlechteste denkbare Umgang damit.
    """
    vorhanden = {str(r) for r in (roles or [])}
    return [k for k in ROLE_ORDER if k in vorhanden]


def permissions_for(roles) -> frozenset[str]:
    """Die Vereinigung der Rechte aller (bekannten) Rollen."""
    aus: set[str] = set()
    for key in known_roles(roles):
        aus |= ROLES[key].permissions
    return frozenset(aus)


def primary_role(roles) -> str:
    """Die stärkste Rolle — für die Alt-Spalte `web_users.role` und für die
    ausgelieferte iOS-App, die `role` als Pflichtfeld liest und `isAdmin`
    daraus ableitet. Ohne bekannte Rolle: der Standard."""
    bekannt = known_roles(roles)
    return bekannt[-1] if bekannt else DEFAULT_ROLE


def catalog() -> list[dict]:
    """Der Rollen-Katalog für das Admin-Panel. Beide Frontends bauen ihre
    Auswahl daraus, statt Rollennamen abzutippen — eine neue Rolle erscheint
    dort dann ohne Frontend-Änderung."""
    return [
        {
            "key": r.key,
            "label": r.label,
            "description": r.description,
            "permissions": sorted(r.permissions),
            "assignable": r.assignable,
        }
        for r in (ROLES[k] for k in ROLE_ORDER)
    ]
