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
#: - ``budget``:  der Haushalts-Bereich (20 Seiten, 20 API-Routen)
#: - ``mandate``: ein Ratsmandat — Benachrichtigungen ab Werk vollständig
#:   (jede Tagesordnung jedes abonnierten Gremiums sofort; Tims Entscheidung
#:   06.09.2026: „Leute mit Ratsmitgliedsstatus kriegen per Default alle Abos")
#: - ``admin``:   das Admin-Panel samt allem darunter
#: - ``premium_models``: das größere Modell für die ausführliche Recherche
#:   (``COUNCIL_DEEP_PLUS_MODEL``, Vorgabe GPT-6 Sol). Tims Wunsch
#:   23.09.2026: „eine weitere Rolle, die größere Modelle für die
#:   ausgewählten Nutzer erlaubt“. Gemessen: Sol 0 statt 2 Modellfehler je
#:   Lauf über 55 Recherchen, 23 statt 30 s, aber 5,6 statt 0,42 ct je
#:   Bericht (docs/plan-modellwechsel.md, „Ausführliche Recherche“). Das
#:   Tageskontingent bleibt dasselbe — das Recht ändert das Modell, nicht
#:   die Menge.
#:
#: Dass ``budget`` und ``mandate`` **zwei** Rechte sind und nicht eines, ist
#: der Grund, warum es die Rolle *Fachpublikum* ohne einen einzigen weiteren
#: Handgriff geben kann: Sie nimmt das eine und lässt das andere liegen.
PERMISSIONS: tuple[str, ...] = ("budget", "mandate", "premium_models", "admin")


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
    "research_plus": Role(
        key="research_plus",
        label="Recherche Plus",
        description="Die ausführliche Recherche schreibt ihren Bericht mit einem größeren, "
                    "gründlicheren Modell. Wird zusätzlich zu einer anderen Rolle vergeben; "
                    "das Tageskontingent bleibt gleich.",
        # Bewusst NUR dieses eine Recht: Die Rolle ist ein Zusatz, keine
        # Stufe. Ein Ratsmitglied mit „Recherche Plus“ trägt beide Rollen —
        # ohne eine vierte, die beides bündelt.
        permissions=frozenset({"premium_models"}),
    ),
    "expert": Role(
        key="expert",
        label="Fachpublikum",
        description="Zusätzlich der Haushalts-Bereich mit allen Zahlen, Belegen und Auswertungen. "
                    "Benachrichtigungen bleiben die normalen — wer hier Tagesordnungen will, "
                    "schaltet sie selbst ein.",
        # Bewusst NUR `budget`. Wer den Haushalt braucht, aber nicht im Rat
        # sitzt — Verwaltung, Presse, sachkundige Bürger*innen,
        # Fraktionsmitarbeit — will die Zahlen, nicht die Tagesordnung jedes
        # abonnierten Gremiums am Tag ihrer Veröffentlichung. Tims Auftrag
        # 21.09.2026: „erweiterte Informationen wie den Haushalt, aber nicht
        # Updates über jeden abonnierten Ausschuss."
        permissions=frozenset({"budget"}),
    ),
    "council_member": Role(
        key="council_member",
        label="Ratsmitglied",
        description="Zusätzlich der Haushalts-Bereich mit allen Zahlen, Belegen und Auswertungen; "
                    "Benachrichtigungen ab Werk vollständig.",
        permissions=frozenset({"budget", "mandate"}),
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
#:
#: „Schwächste zuerst" heißt hier: nach Umfang der Rechte. *Fachpublikum*
#: trägt eine echte Teilmenge dessen, was *Ratsmitglied* trägt, und steht
#: deshalb davor — wer beide Rollen hat, erscheint als Ratsmitglied.
#:
#: *Recherche Plus* steht direkt nach dem Standard: Sie ist ein Zusatz, der
#: neben jeder anderen Rolle vergeben wird, und soll in der Alt-Spalte nie
#: eine davon verdrängen — ein Ratsmitglied mit Recherche Plus erscheint dort
#: als Ratsmitglied, ein Admin als Admin.
ROLE_ORDER: tuple[str, ...] = ("user", "research_plus", "expert", "council_member", "admin")


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
