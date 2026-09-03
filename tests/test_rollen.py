"""Wächter für das Rollen- und Rechtesystem (`kern/roles.py`).

Die drei Fehler, gegen die hier geprüft wird, haben eines gemeinsam: Keiner
von ihnen macht irgendetwas kaputt, das auffällt. Ein Endpunkt ohne
Rechteprüfung antwortet fröhlich weiter, nur eben allen. Eine Rolle, die im
Vertrag fehlt, lässt die iOS-App still am Konto scheitern. Eine Migration, die
nicht greift, sperrt einen Admin aus, und zwar erst auf dem Server.
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

WURZEL = ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "web" / "backend"))

from kern import roles  # noqa: E402
from kern.store import Store  # noqa: E402


# --------------------------------------------------------------- die Registry

def test_admin_traegt_jedes_recht():
    """Auch jedes, das erst morgen dazukommt.

    Die Rechte des Admins stehen als ``frozenset(PERMISSIONS)`` da und nicht
    als Aufzählung — genau damit ein neues Recht ihn nicht aussperrt. Der Test
    hält die Eigenschaft fest, falls jemand die Aufzählung „der Klarheit
    halber" ausschreibt.
    """
    assert roles.permissions_for(["admin"]) == frozenset(roles.PERMISSIONS)


def test_die_standardrolle_traegt_keine_rechte():
    """Was alle dürfen, hängt an `require_active` und braucht kein Recht.
    Gäbe die Standardrolle eines, hätte es jedes Konto — und die Prüfung wäre
    eine Prüfung, die nie etwas verhindert."""
    assert roles.permissions_for([roles.DEFAULT_ROLE]) == frozenset()
    assert roles.permissions_for([]) == frozenset()


def test_ratsmitglied_darf_den_haushalt_und_sonst_nichts_besonderes():
    assert roles.permissions_for(["council_member"]) == frozenset({"budget"})
    assert "admin" not in roles.permissions_for(["council_member"])


def test_jede_rolle_steht_in_der_reihenfolge_und_umgekehrt():
    """Eine Rolle, die in ROLE_ORDER fehlt, ist unsichtbar: `known_roles`
    filtert sie weg, das Konto verliert seine Rechte, und nichts meldet sich."""
    assert set(roles.ROLE_ORDER) == set(roles.ROLES)
    assert [r.key for r in map(roles.ROLES.get, roles.ROLE_ORDER)] == list(roles.ROLE_ORDER)


def test_jedes_vergebene_recht_ist_ein_bekanntes_recht():
    for rolle in roles.ROLES.values():
        unbekannt = rolle.permissions - set(roles.PERMISSIONS)
        assert not unbekannt, (
            f"Rolle {rolle.key!r} trägt das unbekannte Recht {unbekannt} — "
            f"entweder Tippfehler oder in PERMISSIONS nachtragen.")


def test_unbekannte_rollen_fliegen_raus_statt_zu_werfen():
    """Eine gewachsene Datenbank kann eine abgeschaffte Rolle tragen. Ein
    500er beim Anmelden wäre der schlechteste Umgang damit."""
    assert roles.known_roles(["admin", "hausmeister", None]) == ["admin"]
    assert roles.permissions_for(["hausmeister"]) == frozenset()


def test_staerkste_rolle_gewinnt_fuer_die_alt_spalte():
    """`web_users.role` trägt genau einen Wert — die App liest ihn. Welcher
    das ist, darf nicht von der Sortierung einer Menge abhängen."""
    assert roles.primary_role(["council_member", "admin"]) == "admin"
    assert roles.primary_role(["admin", "council_member"]) == "admin"
    assert roles.primary_role([]) == roles.DEFAULT_ROLE


# ------------------------------------------------------------------ der Vertrag

def test_vertrag_kennt_genau_die_rollen_und_rechte_der_registry():
    """Beide Richtungen, wie jeder Wächter hier.

    Ein Literal, das eine Rolle verschweigt, ist kein Schönheitsfehler: Der
    Swift-Generator baut daraus ein enum, und ein unbekannter Wert lässt die
    App beim Decodieren des KONTOS abbrechen — sie zeigt dann gar nichts mehr.
    """
    from app.schemas import Recht, Rolle
    from typing import get_args

    assert set(get_args(Rolle)) == set(roles.ROLES)
    assert set(get_args(Recht)) == set(roles.PERMISSIONS)


# ------------------------------------------------------- die Endpunkte selbst

def _alle_endpunkte():
    """Der Routen-Läufer aus dem Schwester-Wächter — bewusst geliehen statt
    nachgebaut. Er kennt die Eigenheit, dass FastAPI eingebundene Router
    hinter `_IncludedRouter` ablegt, und er prüft sich gegen das OpenAPI-Schema
    selbst nach. Ein zweiter, eigener Läufer hier wäre eine zweite Gelegenheit,
    still zu wenig zu sehen."""
    from tests.test_endpunkt_schutz import _endpunkte

    return _endpunkte()


def _budget_endpunkte():
    return [(m, p, n) for m, p, n in _alle_endpunkte()
            if p.startswith("/api/council/budget")]


def test_jede_haushalts_route_verlangt_das_haushalts_recht():
    """DER Wächter dieses Umbaus.

    Der Haushalt ist Ratsmitgliedern vorbehalten, und das hängt an einer
    Dependency je Route. Eine vergessene Route fällt durch kein anderes Netz:
    Sie antwortet weiter, nur eben jedem angemeldeten Konto, und kein Test
    wird davon rot (`web/backend/CLAUDE.md`, „Schutz vergisst sich lautlos").
    """
    endpunkte = _budget_endpunkte()
    assert endpunkte, ("Keine einzige /budget-Route gefunden — dann prüft dieser "
                       "Wächter nichts mehr. `_endpunkte()` nachziehen.")
    ohne = sorted(f"{m.upper()} {p}" for m, p, namen in endpunkte
                  if "require_permission_budget" not in namen)
    assert not ohne, (
        "Diese Haushalts-Routen prüfen das Recht 'budget' nicht und sind damit "
        "für JEDES angemeldete Konto offen:\n  " + "\n  ".join(ohne) +
        "\n\nBeheben: `_user: dict = Depends(require_budget)` statt "
        "`Depends(require_active)` (die Konstante steht oben in "
        "web/backend/app/routers/council.py).")


def test_das_haushalts_recht_haengt_an_keiner_fremden_route():
    """Die Gegenrichtung: Eine Ausnahmeliste, die nur wächst, ist kaputt — und
    ein Recht, das versehentlich an einer Ratsinhalts-Route hängt, sperrt
    reguläre Nutzer*innen aus einem Bereich aus, der ihnen gehört."""
    fremd = sorted(f"{m.upper()} {p}" for m, p, namen in _alle_endpunkte()
                   if "require_permission_budget" in namen
                   and not p.startswith("/api/council/budget"))
    assert not fremd, ("Diese Routen liegen außerhalb des Haushalts, verlangen "
                       "aber das Haushalts-Recht:\n  " + "\n  ".join(fremd))


def test_ein_tippfehler_im_rechtenamen_faellt_sofort_auf():
    """Sonst entstünde eine Dependency, die NIEMAND erfüllt — ein für alle
    gesperrter Endpunkt, der beim Start kein Wort sagt."""
    from app.deps import require_permission

    with pytest.raises(ValueError, match="Unbekanntes Recht"):
        require_permission("haushalt")  # deutsch statt 'budget'


# --------------------------------------------------------------- Speicherung

@pytest.fixture
def store(tmp_path):
    s = Store(str(tmp_path / "ratslotse.sqlite"))
    yield s
    s.close()


def test_rollen_und_alt_spalte_bleiben_beieinander(store):
    """Die Spalte ist abgeleitet. Zwei Wahrheiten wären hier genau die stille
    Sorte Fehler: Das Panel zeigte einen Admin, die Rechteprüfung sähe keinen."""
    uid = store.create_web_user("a@example.org", "x")
    assert store.get_web_user_roles(uid) == []
    assert store.get_web_user_by_id(uid)["role"] == "user"

    store.set_web_user_roles(uid, ["council_member", "admin"])
    assert store.get_web_user_roles(uid) == ["council_member", "admin"]
    assert store.get_web_user_by_id(uid)["role"] == "admin"

    store.set_web_user_roles(uid, [])
    assert store.get_web_user_roles(uid) == []
    assert store.get_web_user_by_id(uid)["role"] == "user"


def test_ergaenzen_nimmt_nichts_weg(store):
    """`grant_admin.py` befördert jemanden — es soll ihm dabei nicht sein
    Ratsmandat abnehmen."""
    uid = store.create_web_user("b@example.org", "x")
    store.set_web_user_roles(uid, ["council_member"])
    store.add_web_user_role(uid, "admin")
    assert store.get_web_user_roles(uid) == ["council_member", "admin"]
    store.remove_web_user_role(uid, "admin")
    assert store.get_web_user_roles(uid) == ["council_member"]


def test_der_alt_weg_zieht_die_tabelle_mit(store):
    """`set_web_user_role` ist der Aufruf der ausgelieferten iOS-App. Schriebe
    er nur die Spalte, hätte ein dort beförderter Admin keine Rechte."""
    uid = store.create_web_user("c@example.org", "x")
    store.set_web_user_role(uid, "admin")
    assert store.get_web_user_roles(uid) == ["admin"]
    store.set_web_user_role(uid, "user")
    assert store.get_web_user_roles(uid) == []


def test_ein_konto_mit_rolle_bringt_seine_zeile_gleich_mit(store):
    """Der Apple-Weg legt die konfigurierte Admin-Adresse direkt mit Rolle an."""
    uid = store.create_web_user("d@example.org", "x", "admin", "active")
    assert store.get_web_user_roles(uid) == ["admin"]


def test_jeder_ladeweg_traegt_die_rollen(store):
    """Ein Ladeweg ohne `roles` wäre eine Rechteprüfung, die still „darf
    nichts" sagt — oder ein KeyError mitten im Request."""
    uid = store.create_web_user("e@example.org", "x")
    store.set_web_user_roles(uid, ["council_member"])
    store.link_apple_sub(uid, "apple-sub-123")
    for konto in (store.get_web_user_by_id(uid),
                  store.get_web_user_by_email("e@example.org"),
                  store.get_web_user_by_apple_sub("apple-sub-123")):
        assert konto["roles"] == ["council_member"]
    assert store.admin_user_detail(uid)["roles"] == ["council_member"]
    assert [z for z in store.admin_user_rows() if z["id"] == uid][0]["roles"] == ["council_member"]
    assert [z for z in store.list_web_users() if z["id"] == uid][0]["roles"] == ["council_member"]


def test_die_rollenliste_haelt_ihre_reihenfolge(store):
    """Sonst hinge die Anzeige an der Einfüge-Reihenfolge und ein Konto sähe
    je nach Klick-Reihenfolge anders aus."""
    uid = store.create_web_user("f@example.org", "x")
    store.set_web_user_roles(uid, ["admin", "council_member"])
    assert store.get_web_user_roles(uid) == ["council_member", "admin"]


# --------------------------------------------------------------- Migration

def _gewachsene_datenbank(pfad: Path) -> None:
    """Eine Datenbank im Stand VOR dem Rollen-Umbau — der ECHTE Prod-Stand.

    Nicht ein von Hand getipptes Mini-Schema: Die Migration läuft durch
    Dutzende Schritte, von denen mehrere Tabellen voraussetzen, die eine
    Handschrift nicht hat. Der Auszug in `tests/schema_staende/` trägt genau
    die Form, aus der auf dem Server heraus migriert wird (die Begründung
    steht ausführlich in `tests/test_migration_bestand.py`).
    """
    ddl = (WURZEL / "tests" / "schema_staende" / "prod-ratslotse.sql").read_text()
    conn = sqlite3.connect(pfad)
    try:
        conn.executescript(ddl)
        # Der Auszug ist reines DDL. Die Zeilen, um die es hier geht, kommen
        # von Hand dazu — und `web_user_roles` wird bewusst NICHT angelegt:
        # Genau diesen Zustand hat der Server vor dem Deploy.
        conn.execute("DROP TABLE IF EXISTS web_user_roles")
        for email, rolle in (("chef@example.org", "admin"),
                             ("wer@example.org", "user"),
                             ("alt@example.org", "hausmeister")):
            conn.execute(
                "INSERT INTO web_users (email, password_hash, role, status, created_at) "
                "VALUES (?, 'x', ?, 'active', '2026-01-01T00:00:00')", (email, rolle))
        conn.commit()
    finally:
        conn.close()


def test_migration_holt_die_admins_aus_der_spalte(tmp_path):
    """Ohne diesen Schritt stünde nach dem Deploy jeder Admin ohne Rechte da —
    und zwar erst auf dem Server, wo die DB gewachsen ist statt frisch (die
    Lücke, die `tests/CLAUDE.md` beschreibt)."""
    pfad = tmp_path / "ratslotse.sqlite"
    _gewachsene_datenbank(pfad)
    s = Store(str(pfad))
    try:
        chef = s.get_web_user_by_email("chef@example.org")
        assert s.get_web_user_roles(chef["id"]) == ["admin"]
        # Die Standardrolle bekommt bewusst KEINE Zeile.
        wer = s.get_web_user_by_email("wer@example.org")
        assert s.get_web_user_roles(wer["id"]) == []
        # Eine unbekannte Rolle wird nicht übernommen (und vorher geloggt).
        alt = s.get_web_user_by_email("alt@example.org")
        assert s.get_web_user_roles(alt["id"]) == []
    finally:
        s.close()


def test_migration_stolpert_beim_zweiten_lauf_nicht(tmp_path):
    """Eine Migration, die beim zweiten Öffnen etwas anderes tut, bricht den
    nächsten Deploy — und der Store wird je Request neu geöffnet."""
    pfad = tmp_path / "ratslotse.sqlite"
    _gewachsene_datenbank(pfad)
    for _ in range(3):
        Store(str(pfad)).close()
    s = Store(str(pfad))
    try:
        chef = s.get_web_user_by_email("chef@example.org")
        assert s.get_web_user_roles(chef["id"]) == ["admin"]
    finally:
        s.close()


def test_migration_holt_eine_entzogene_rolle_nicht_zurueck(tmp_path):
    """Der Fall, an dem eine „selbstheilende" Migration gefährlich würde: Ein
    Admin nimmt jemandem die Rechte, der nächste Request öffnet den Store neu
    — und die Migration gäbe sie zurück."""
    pfad = tmp_path / "ratslotse.sqlite"
    _gewachsene_datenbank(pfad)
    s = Store(str(pfad))
    chef_id = s.get_web_user_by_email("chef@example.org")["id"]
    s.set_web_user_roles(chef_id, [])
    s.close()

    s = Store(str(pfad))
    try:
        assert s.get_web_user_roles(chef_id) == []
    finally:
        s.close()


# Die zwei End-zu-Ende-Proben (403 für reguläre Konten, 200 fürs Ratsmitglied)
# stehen in `test_backend_api.py`: Dort hängen die Fixtures, die je Test frische
# Datenbanken und einen sauberen Client herstellen. Hierher kopiert wären sie
# eine zweite, halb funktionierende Version davon.
