"""Wegwerf-Adressen: erkennen, still behandeln, im Admin-Panel markieren.

Anlass (12./13.09.2026, Prod): zwei Konten mit Tastatur-Namen auf 94an.com
und airhemp.com, beide mit bestätigter Adresse — die Bestätigungs-Mail hält
Wegwerf-Postfächer nicht ab. Am 23.11.2026 kam ein drittes über kranove.com,
weil die Liste zwei Monate nicht nachgezogen war; seit dem 24.11. wird nicht
mehr abgewiesen, sondern still keine Mail geschickt. Diese Datei hält fest:

* die Erkennung samt Eltern-Domains und Schreibweise,
* dass echte Anbieter (und Apples „E-Mail verbergen") nie erwischt werden —
  auch nicht, wenn ein Nachziehen der Liste sie hereinschwemmen sollte,
* dass die Liste im Repo sauber ist (Form, Dubletten, Umfang),
* welche Fassung gilt (Repo-Datei oder nachgezogene Kopie) und das Nachziehen,
* die Endpunkte: Registrierung, „Erneut senden" und Adresswechsel antworten
  wie immer, verschicken aber nichts; ``send_email`` lässt jede Mail an eine
  Wegwerf-Adresse fallen (sonst bestätigte „Passwort vergessen" das Konto),
* das Abzeichen im Admin-Panel.
"""
from __future__ import annotations

import os
import re
import sys
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

_BACKEND = Path(__file__).resolve().parents[1] / "web" / "backend"
sys.path.insert(0, str(_BACKEND))

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402
from kern import disposable_email as de  # noqa: E402

RATSLOTSE_DB = os.environ["RATSLOTSE_DB"]
COUNCIL_DB = os.environ["COUNCIL_DB"]
PASSWORT = "password123"


@pytest.fixture(autouse=True)
def fresh_dbs():
    for base in (RATSLOTSE_DB, COUNCIL_DB):
        for suffix in ("", "-wal", "-shm"):
            Path(base + suffix).unlink(missing_ok=True)
    yield


@pytest.fixture
def client():
    return TestClient(app)


# --- Erkennung ---------------------------------------------------------------
#
# Die Tests nennen nur DOMAINS und setzen die Adresse zur Laufzeit zusammen:
# `scripts/lint_adressen.py` lässt im Repo nur Adressen auf eigenen Domains
# zu, und eine Prüfung fremder Anbieter braucht nun einmal fremde Domains.

def _adresse(domain: str, lokal: str = "x") -> str:
    return f"{lokal}@{domain}"


@pytest.mark.parametrize("domain", [
    "94an.com",                     # die beiden Konten vom 12./13.09.2026
    "airhemp.com",
    "mail.94an.com",                # Eltern-Domain zählt
    "mailinator.com",
])
def test_wegwerf_adressen_werden_erkannt(domain):
    assert de.is_disposable(_adresse(domain))
    assert de.is_disposable(f"  {_adresse(domain.upper(), 'X')}  ")   # Schreibweise und Rand egal


@pytest.mark.parametrize("domain", [
    "example.org",
    "ratslotse.de",
    "privaterelay.appleid.com",     # Apples „E-Mail verbergen"
    "web.de", "gmx.de", "t-online.de", "hotmail.de", "gmail.com",
    "stadt.oldenburg.de",           # Unter-Domain eines geschützten Anbieters
])
def test_echte_anbieter_bleiben_frei(domain):
    assert not de.is_disposable(_adresse(domain))


@pytest.mark.parametrize("kaputt", ["kein-at", "", "@", "x@"])
def test_ohne_domain_keine_wegwerf_adresse(kaputt):
    """Die Formprüfung ist Sache von ``EmailStr`` — hier nur nicht stolpern."""
    assert not de.is_disposable(kaputt)


def test_geschuetzte_anbieter_gewinnen_gegen_die_liste(monkeypatch):
    """Sollte ein Nachziehen einen echten Anbieter hereinschwemmen, gewinnt
    ``PROTECTED_DOMAINS`` — der Riegel darf nie ganze Postfach-Anbieter sperren."""
    monkeypatch.setattr(de, "blocked_domains", lambda: frozenset({"gmail.com", "94an.com"}))
    assert not de.is_disposable(_adresse("gmail.com"))
    assert de.is_disposable(_adresse("94an.com"))


def test_domain_of():
    assert de.domain_of("A@Example.ORG") == "example.org"
    assert de.domain_of("a@b@example.org") == "example.org"
    assert de.domain_of("ohne") == ""


# --- Die Liste im Repo ---------------------------------------------------------

def test_liste_ist_sauber():
    zeilen = [z for z in de.LIST_PATH.read_text(encoding="utf-8").splitlines()
              if z.strip() and not z.startswith("#")]
    domain = re.compile(r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)+$")
    kaputt = [z for z in zeilen if not domain.match(z)]
    assert not kaputt, kaputt[:5]
    assert len(zeilen) == len(set(zeilen)), "Dubletten in der Liste"
    assert len(zeilen) > 5000, "Liste unerwartet klein — Nachziehen schiefgegangen?"
    assert de.LIST_PATH.read_text(encoding="utf-8").startswith("# "), "Kopf mit Quelle/Lizenz fehlt"


def test_kein_geschuetzter_anbieter_steht_in_der_liste():
    """Nicht, weil er dann gesperrt wäre (die Menge gewinnt) — sondern weil ein
    solcher Eintrag heißt, dass die Liste jemanden Echtes erwischt hat."""
    assert not (de.blocked_domains() & de.PROTECTED_DOMAINS)


def test_liste_wird_nur_einmal_gelesen():
    assert de.blocked_domains() is de.blocked_domains()


# --- Welche Fassung gilt -----------------------------------------------------
#
# Die Tests legen die Kopie in ein eigenes Verzeichnis (``RATSLOTSE_DB`` auf
# ``tmp_path``): Sie folgt der Datenbank, und eine Kopie im gemeinsamen
# Verzeichnis des Testprozesses wirkte auf jeden späteren Test darin.

@pytest.fixture
def eigene_kopie(tmp_path, monkeypatch):
    monkeypatch.setenv("RATSLOTSE_DB", str(tmp_path / "ratslotse.sqlite"))
    return tmp_path / de.KOPIE_NAME


def test_ohne_kopie_gilt_die_repo_datei(eigene_kopie):
    assert not eigene_kopie.exists()
    assert de.blocked_domains() == de.parse_list(de.LIST_PATH.read_text(encoding="utf-8"))


def test_eine_neuere_kopie_gewinnt(eigene_kopie):
    """Auch eine Domain, die upstream wieder herausgenommen wurde, muss wirken
    — deshalb die neuere Fassung und keine Vereinigung beider."""
    eigene_kopie.write_text(de.render(frozenset({"nur-in-der-kopie.example"}), date(2099, 1, 1)),
                            encoding="utf-8")
    assert de.is_disposable(_adresse("nur-in-der-kopie.example"))
    assert not de.is_disposable(_adresse("94an.com"))
    assert de.stand() == date(2099, 1, 1)


def test_eine_aeltere_kopie_verliert_gegen_den_commit(eigene_kopie):
    eigene_kopie.write_text(de.render(frozenset({"nur-in-der-kopie.example"}), date(2000, 1, 1)),
                            encoding="utf-8")
    assert not de.is_disposable(_adresse("nur-in-der-kopie.example"))
    assert de.is_disposable(_adresse("94an.com"))


def test_eine_kopie_ohne_stand_wird_ueberlesen(eigene_kopie):
    eigene_kopie.write_text("nur-in-der-kopie.example\n", encoding="utf-8")
    assert not de.is_disposable(_adresse("nur-in-der-kopie.example"))


def test_der_dienst_sieht_eine_neue_kopie_ohne_neustart(eigene_kopie):
    vorher = de.blocked_domains()
    eigene_kopie.write_text(de.render(frozenset({"frisch.example"}), date(2099, 1, 1)),
                            encoding="utf-8")
    assert de.blocked_domains() != vorher
    assert de.is_disposable(_adresse("frisch.example"))


def _upstream(*domains: str) -> str:
    return "\n".join(domains) + "\n"


def test_nachziehen_schreibt_die_kopie(eigene_kopie):
    alt = de.blocked_domains()
    neu = sorted(alt)[: int(len(alt) * 0.95)] + ["ganz-neu.example"]
    ergebnis = de.nachziehen(date(2099, 1, 1), abruf=lambda: _upstream(*neu))
    assert ergebnis["dazu"] == 1 and ergebnis["eintraege"] == len(neu)
    assert de.stand_von(eigene_kopie.read_text(encoding="utf-8")) == date(2099, 1, 1)
    assert de.is_disposable(_adresse("ganz-neu.example"))
    assert not eigene_kopie.with_suffix(".tmp").exists()


@pytest.mark.parametrize("upstream,grund", [
    (lambda alt: ["94an.com"], "geschrumpft"),
    (lambda alt: sorted(alt) + ["gmail.com"], "geschützte"),
    (lambda alt: sorted(alt) + ["<html>"], "keine Domain"),
])
def test_nachziehen_uebernimmt_keine_verdaechtige_liste(eigene_kopie, upstream, grund):
    ergebnis = de.nachziehen(date(2099, 1, 1),
                             abruf=lambda: _upstream(*upstream(de.blocked_domains())))
    assert any(grund in g for g in ergebnis["gruende"]), ergebnis
    assert not eigene_kopie.exists()


# --- Der Versand ---------------------------------------------------------------

class _Antwort:
    def raise_for_status(self):
        pass

    def json(self):
        return {"id": "m1"}


def test_send_email_laesst_wegwerf_adressen_fallen():
    """Die eigentliche Sperre: an eine Wegwerf-Adresse geht nichts raus."""
    with patch("kern.email.requests.post", return_value=_Antwort()) as post:
        from kern.email import send_email
        assert send_email(_adresse("94an.com"), "Betreff", "<p>x</p>", api_key="k") is None
        post.assert_not_called()
        # Gemischte Empfänger: nur die Wegwerf-Adresse fällt heraus.
        assert send_email(["echt@example.org", _adresse("airhemp.com")], "B", "<p>x</p>",
                          api_key="k") == "m1"
        assert post.call_args.kwargs["json"]["to"] == ["echt@example.org"]


# --- Die Endpunkte -----------------------------------------------------------

def _register(client, email, name="Testkonto"):
    return client.post("/api/auth/register",
                       json={"display_name": name, "email": email, "password": PASSWORT})


def _mit_mailversand(postfach: list):
    """Settings mit Resend-Schlüssel und abgefangener Versand (wie in
    ``test_email_aendern.py``): Beide Router lesen ihre Settings selbst, die
    Mail-Funktionen stehen in ``auth.py``."""
    einstellungen = SimpleNamespace(
        resend_api_key="x", app_base_url="https://ratslotse.de",
        email_from="Ratslotse <f@example.org>", feedback_email="",
        web_admin_email="", cookie_secure=False,
        access_token_expire_minutes=60, app_access_token_expire_minutes=60,
        ratslotse_db=str(RATSLOTSE_DB), apple_bundle_id="de.ratslotse.app",
    )

    def fake_send(to, subject, html, **kw):
        postfach.append(to)
        return "id"

    return (patch("app.routers.auth.send_email", side_effect=fake_send),
            patch("app.routers.auth.get_settings", return_value=einstellungen),
            patch("app.routers.account.get_settings", return_value=einstellungen))


def test_registrierung_mit_wegwerf_adresse_sieht_aus_wie_jede_andere(client):
    """Tims Vorgabe (24.11.2026): nicht zeigen, dass etwas gesperrt ist — die
    Mail kommt einfach nicht an. Also 201 wie sonst, ein unbestätigtes Konto
    und keine Mail."""
    from kern.store import Store

    postfach: list = []
    versand, s_auth, s_account = _mit_mailversand(postfach)
    wegwerf = _adresse("94an.com")
    with versand, s_auth, s_account:
        echt = _register(TestClient(app), "echt@example.org")
        r = _register(client, wegwerf)
    assert r.status_code == echt.status_code == 201, r.text
    assert set(r.json()) == set(echt.json()), "Die Antwort darf sich nicht unterscheiden"
    assert r.json()["status"] == "pending" and not r.json()["email_verified"]
    assert postfach == ["echt@example.org"], "An die Wegwerf-Adresse darf nichts gehen"

    store = Store(RATSLOTSE_DB)
    try:
        assert store.signup_rejections_since("2000-01-01").get("disposable_email") == 1
        konto = store.get_web_user_by_email(wegwerf)
        assert konto is not None
        assert store.mails_fuer_konto(int(konto["id"])) == [], (
            "Eine Zeile „Bestätigung verschickt“ behauptete etwas, das nicht geschah")
    finally:
        store.close()
    # Hinein kommt das Konto nicht: Alles hinter `require_active` bleibt zu.
    assert client.get("/api/topics").status_code == 403


def test_ohne_mailversand_bleibt_eine_wegwerf_adresse_unbestaetigt(client):
    """Ohne Resend-Schlüssel gilt sonst jedes Konto sofort als bestätigt (es gäbe
    keinen Link). Eine Wegwerf-Adresse nie — sonst wäre sie lokal und auf jedem
    Server ohne Mail-Versand ein aktives Konto."""
    r = _register(client, _adresse("airhemp.com"))
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "pending" and not r.json()["email_verified"]
    assert _register(TestClient(app), "echt@example.org").json()["status"] == "active"


def test_erneut_senden_schickt_nichts_an_eine_wegwerf_adresse(client):
    postfach: list = []
    versand, s_auth, s_account = _mit_mailversand(postfach)
    with versand, s_auth, s_account:
        assert _register(client, _adresse("94an.com")).status_code == 201
        r = client.post("/api/auth/resend-verification")
    assert r.status_code == 200 and r.json() == {"ok": True}
    assert postfach == []


def test_passwort_vergessen_erreicht_keine_wegwerf_adresse(client):
    """Der Grund, warum die Sperre am Versand sitzt: Der Reset bestätigt die
    Adresse mit. Hier läuft der ECHTE ``send_email`` — nur das Netz ist ersetzt."""
    from app.config import get_settings

    wegwerf = _adresse("94an.com")
    assert _register(client, wegwerf).status_code == 201
    assert _register(TestClient(app), "echt@example.org").status_code == 201
    einstellungen = get_settings().model_copy(update={"resend_api_key": "x"})
    with patch("app.routers.auth.get_settings", return_value=einstellungen), \
         patch("kern.email.requests.post", return_value=_Antwort()) as post:
        r = TestClient(app).post("/api/auth/forgot-password", json={"email": wegwerf})
        assert r.status_code == 200, r.text
        post.assert_not_called()
        # Gegenprobe, damit der Test nicht nur das Netz-Ersatzstück prüft.
        TestClient(app).post("/api/auth/forgot-password", json={"email": "echt@example.org"})
        assert post.call_count == 1


def test_adresswechsel_auf_wegwerf_adresse_schickt_keinen_link(client):
    """Sonst wäre der Wechsel der Umweg um die Sperre. Der Wechsel schwebt wie
    jeder andere — er wird nur nie bestätigt."""
    postfach: list = []
    versand, s_auth, s_account = _mit_mailversand(postfach)
    neu = _adresse("airhemp.com")
    with versand, s_auth, s_account:
        assert _register(client, "echt@example.org").status_code == 201
        from kern.store import Store
        store = Store(RATSLOTSE_DB)
        try:
            konto = store.get_web_user_by_email("echt@example.org")
            assert konto is not None
            store.set_email_verified(int(konto["id"]), True)
            store.set_web_user_status(int(konto["id"]), "active")
        finally:
            store.close()
        postfach.clear()
        r = client.post("/api/account/change-email",
                        json={"new_email": neu, "current_password": PASSWORT})
        assert r.status_code == 200, r.text
        assert r.json()["pending_email"] == neu
        assert neu not in postfach, "Der Link darf nicht an die Wegwerf-Adresse gehen"
        assert postfach == ["echt@example.org"], "Die Warnung an die alte Adresse bleibt"
        postfach.clear()
        assert client.post("/api/auth/resend-verification").json() == {"ok": True}
        assert postfach == []
    assert client.get("/api/auth/me").json()["email"] == "echt@example.org"


def test_ohne_mailversand_gilt_ein_wechsel_auf_wegwerf_nicht_sofort(client):
    assert _register(client, "echt@example.org").status_code == 201
    r = client.post("/api/account/change-email",
                    json={"new_email": _adresse("airhemp.com"), "current_password": PASSWORT})
    assert r.status_code == 200, r.text
    assert client.get("/api/auth/me").json()["email"] == "echt@example.org"


def test_registrierung_mit_dauerhafter_adresse_geht_weiter(client):
    r = _register(client, "echt@example.org")
    assert r.status_code == 201, r.text
    assert r.json()["email"] == "echt@example.org"


# --- Das Admin-Panel -----------------------------------------------------------

def test_admin_panel_markiert_wegwerf_konten(client):
    from tests.test_backend_api import _register as admin_registrieren

    assert admin_registrieren(client).status_code == 201
    TestClient(app).post("/api/auth/register", json={
        "display_name": "Jjhh", "email": _adresse("kranove.com"), "password": PASSWORT})
    zeilen = {u["email"]: u for u in client.get("/api/admin/users").json()}
    assert zeilen[_adresse("kranove.com")]["disposable_email"] is True
    assert zeilen["admin@test.de"]["disposable_email"] is False
    detail = client.get(f"/api/admin/users/{zeilen[_adresse('kranove.com')]['id']}").json()
    assert detail["disposable_email"] is True
