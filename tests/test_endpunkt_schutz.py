"""Jeder Endpunkt ist angemeldet — oder steht mit Begründung in der Liste.

**Warum das ein Test ist.** Der Schutz eines Endpunkts hängt an einer einzigen
Zeile: ``user=Depends(require_active)``. Wer sie beim Anlegen vergisst,
bekommt einen offenen Endpunkt — und die Suite bleibt grün, weil es bis
09/2026 nur endpunkt-eigene Tests gab und keinen, der über alle Routen läuft.
Ein versehentlich offener Endpunkt fiel damit durch **kein** Netz.

Der Test dreht die Beweislast um: Nicht der Schutz muss begründet werden,
sondern seine Abwesenheit. Wer einen Endpunkt öffentlich haben will, trägt ihn
unten ein — das ist eine Zeile im Diff, über die jemand im Review stolpert.

**Der Wächter darf nicht stumm aufhören zu wachen.** Wie FastAPI seine Routen
intern ablegt, hat sich schon einmal geändert (in 0.137 hängen die
eingebundenen Router hinter ``_IncludedRouter``). Ein Zähler-Abgleich gegen
das OpenAPI-Schema stellt deshalb sicher, dass der Läufer wirklich jeden
Endpunkt gesehen hat; findet er weniger, wird er rot statt grün.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "web" / "backend"))
os.environ.setdefault("WEB_JWT_SECRET", "test-secret")

#: Abhängigkeiten, die einen Endpunkt als geschützt ausweisen.
#:
#: ``optional_user`` steht bewusst dabei: Er ist kein Schutz, sondern die
#: ausdrückliche Entscheidung „öffentlich, aber mit persönlichem Zusatz" —
#: und er prüft dieselbe Schwelle wie ``require_active``, damit er kein
#: Seiteneingang an der Sperre vorbei wird.
SCHUTZ = {
    "get_current_user",
    "require_active",
    "require_admin",
    "optional_user",
    "bot_token",
}

#: Endpunkte, die ohne Anmeldung erreichbar sein MÜSSEN.
#:
#: Jede Zeile ist eine Entscheidung. Wer hier etwas hinzufügt, öffnet einen
#: Endpunkt fürs offene Netz; wer einen Endpunkt nachträglich schützt,
#: streicht seine Zeile (sonst meldet der zweite Test sie als veraltet).
OEFFENTLICH = {
    # Betrieb: Der Health-Check ist das Deploy-Gate, die App-Konfiguration
    # sagt einer alten App-Fassung, dass sie zu alt ist — beides muss ohne
    # Konto gehen, sonst kann sich niemand mehr anmelden.
    ("get", "/api/health"),
    ("get", "/api/app-config"),

    # Anmeldung selbst. Ein Konto zu verlangen, um sich anzumelden, ginge
    # schlecht.
    ("post", "/api/auth/register"),
    ("post", "/api/auth/login"),
    ("post", "/api/auth/logout"),
    ("post", "/api/auth/apple"),
    ("post", "/api/auth/verify-email"),
    ("post", "/api/auth/forgot-password"),
    ("post", "/api/auth/reset-password"),

    # Öffentliche Ratsinhalte: Beschluss-, Personen- und Ortsseiten sind ohne
    # Konto lesbar, weil die Arbeit des Rats öffentlich ist. Die Sitzung
    # hängt daran (die Beschluss-Seite zieht Gremium und Datum nach).
    ("get", "/api/council/session/{ksinr}"),
    ("get", "/api/council/entity/{slug}"),
    ("get", "/api/council/person/{slug}"),
    ("get", "/api/council/person/{slug}/speeches"),
    ("get", "/api/council/people-directory"),
    ("get", "/api/council/place/{place_id}"),
    ("get", "/api/council/heute"),
    ("get", "/api/council/public-stats"),
    ("get", "/api/council/qa-beispiele"),

    # Geteilte Antworten: Der Token IST der Zugang — wer den Link hat, darf
    # lesen und melden. Ein Konto zu verlangen machte das Teilen sinnlos.
    ("get", "/api/council/qa-share/{token}"),
    ("post", "/api/council/qa-share/{token}/report"),

    # Vorschaubilder und Planzeichnungen holen sich Messenger und soziale
    # Netze beim Auspacken eines Links; sie haben kein Konto.
    ("get", "/api/council/preview/{kind}/{key:path}"),
    ("get", "/api/council/plan-bild/{document_id}"),

    # Wahlprogramm-Quellen: Belege einer öffentlichen Vergleichsseite.
    ("get", "/api/kommunalwahl/source/{slug}"),

    # Kontaktformular — der einzige Schreibpfad ohne Konto. Er ist deshalb
    # eigens ratenbegrenzt.
    ("post", "/api/feedback/contact"),
}


def _namen(dependant) -> set[str]:
    """Alle Abhängigkeitsfunktionen eines Endpunkts, rekursiv."""
    gefunden: set[str] = set()
    for d in dependant.dependencies:
        if d.call is not None:
            gefunden.add(getattr(d.call, "__name__", str(d.call)))
        gefunden |= _namen(d)
    return gefunden


def _endpunkte():
    """``[(methode, pfad, {abhängigkeiten}), …]`` über alle eingebundenen Router.

    FastAPI hängt eingebundene Router seit 0.137 hinter ``_IncludedRouter``;
    deren ``effective_route_contexts()`` kennt auch die Abhängigkeiten, die am
    Router selbst hängen (so schützt sich der Bot-Router). Der ältere Weg über
    ``.routes`` bleibt als Rückfall stehen.
    """
    from fastapi.routing import APIRoute

    from app.main import app

    def laufen(routen):
        for r in routen:
            if isinstance(r, APIRoute):
                yield r.path, r.methods, r.dependant, []
            elif hasattr(r, "effective_route_contexts"):
                for ctx in r.effective_route_contexts():
                    yield ctx.path, ctx.methods, ctx.dependant, list(ctx.dependencies)
            elif hasattr(r, "routes"):
                yield from laufen(r.routes)

    aus = []
    for pfad, methoden, dependant, extra in laufen(app.routes):
        namen = _namen(dependant)
        for d in extra:
            call = getattr(d, "dependency", None) or getattr(d, "call", None)
            if call is not None:
                namen.add(getattr(call, "__name__", str(call)))
        for m in sorted(set(methoden) - {"HEAD", "OPTIONS"}):
            aus.append((m.lower(), pfad, namen))
    return aus


@pytest.fixture(scope="module")
def endpunkte():
    return _endpunkte()


def test_der_waechter_sieht_wirklich_jeden_endpunkt(endpunkte):
    """Zähler-Abgleich gegen das OpenAPI-Schema.

    Ohne ihn wäre der Preis einer FastAPI-Umstellung ein Test, der nichts
    mehr prüft und trotzdem grün ist — die schlechteste aller Lagen.
    """
    from app.main import app

    im_schema = sum(
        1
        for ops in app.openapi()["paths"].values()
        for m in ops
        if m in ("get", "post", "put", "patch", "delete")
    )
    assert len(endpunkte) == im_schema, (
        f"Der Läufer hat {len(endpunkte)} Endpunkte gefunden, das Schema kennt "
        f"{im_schema}. Wahrscheinlich legt FastAPI seine Routen inzwischen "
        f"anders ab — `_endpunkte()` in dieser Datei nachziehen. Solange das "
        f"nicht stimmt, prüft der Schutz-Wächter unten zu wenig."
    )


def test_kein_endpunkt_ist_versehentlich_offen(endpunkte):
    offen = sorted(
        f"{m.upper()} {p}"
        for m, p, namen in endpunkte
        if not (namen & SCHUTZ) and (m, p) not in OEFFENTLICH
    )
    assert not offen, (
        "Diese Endpunkte verlangen keine Anmeldung:\n  "
        + "\n  ".join(offen)
        + "\n\nEntweder `user=Depends(require_active)` (bzw. `require_admin`, "
          "`optional_user`) ergänzen — oder, wenn der Endpunkt wirklich "
          "öffentlich sein soll, mit Begründung in OEFFENTLICH eintragen."
    )


def test_die_liste_der_offenen_endpunkte_ist_aktuell(endpunkte):
    """Eine Ausnahmeliste, die nur wächst, ist keine Liste, sondern ein Rest."""
    vorhanden = {(m, p) for m, p, _ in endpunkte}
    geschuetzt = {(m, p) for m, p, namen in endpunkte if namen & SCHUTZ}

    verschwunden = sorted(f"{m.upper()} {p}" for m, p in OEFFENTLICH - vorhanden)
    assert not verschwunden, (
        "Diese Einträge in OEFFENTLICH gibt es als Endpunkt nicht (mehr):\n  "
        + "\n  ".join(verschwunden)
    )
    inzwischen = sorted(f"{m.upper()} {p}" for m, p in OEFFENTLICH & geschuetzt)
    assert not inzwischen, (
        "Diese Endpunkte stehen in OEFFENTLICH, verlangen aber inzwischen eine "
        "Anmeldung — bitte aus der Liste streichen:\n  " + "\n  ".join(inzwischen)
    )
