"""Die harten Grenzen für Benachrichtigungen (Design 30a/C).

Zwei davon leben in nwz/notify.py und sind hier festgehalten:

* **Nachtruhe 21–7 Uhr** — was ein Abendbeschluss auslöst, wartet bis 7 Uhr.
  Ratssitzungen enden regelmäßig nach 22 Uhr; nichts im Rat ist so dringend,
  dass es jemanden weckt.
* **Höchstens zwei am Tag** — pro Person, nicht pro Anlass. Ab der dritten wird
  gebündelt statt gestapelt, und nichts geht dabei verloren.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from nwz import notify
from nwz.store import Store

BERLIN = notify.ZONE


def _zeit(tag: str, stunde: int, minute: int = 0) -> datetime:
    """Ortszeit → UTC, so wie die App rechnet."""
    j, m, t = (int(x) for x in tag.split("-"))
    return datetime(j, m, t, stunde, minute, tzinfo=BERLIN).astimezone(timezone.utc)


def _konto(store: Store, email: str = "a@b.de") -> int:
    return store.create_web_user(email=email, password_hash="x", role="user",
                                 status="active", display_name=None)


@pytest.fixture()
def store(tmp_path):
    s = Store(tmp_path / "nwz.sqlite")
    yield s
    s.close()


# ---- Nachtruhe --------------------------------------------------------------

@pytest.mark.parametrize("stunde, ruht", [
    (7, False), (12, False), (20, False),   # Tag
    (21, True), (23, True), (0, True), (6, True),   # Nacht
])
def test_nachtruhe_fenster(stunde, ruht):
    assert notify.ist_nachtruhe(_zeit("2026-08-18", stunde)) is ruht


def test_abendbeschluss_wartet_bis_sieben():
    """Der Fall aus dem Artboard: beschlossen um 22:40, zugestellt um 7:00."""
    fenster = notify.naechstes_fenster(_zeit("2026-08-18", 22, 40)).astimezone(BERLIN)
    assert (fenster.day, fenster.hour, fenster.minute) == (19, 7, 0)


def test_frueher_morgen_wartet_auf_denselben_tag():
    fenster = notify.naechstes_fenster(_zeit("2026-08-18", 3)).astimezone(BERLIN)
    assert (fenster.day, fenster.hour) == (18, 7)


def test_am_tag_geht_es_sofort():
    jetzt = _zeit("2026-08-18", 14)
    assert notify.naechstes_fenster(jetzt) == jetzt


def test_in_der_nachtruhe_wird_nichts_zugestellt(store, monkeypatch):
    owner = _konto(store)
    monkeypatch.setattr("nwz.delivery.deliver_message",
                        lambda *a, **k: pytest.fail("in der Nachtruhe darf nichts rausgehen"))
    notify.einreihen(store, owner, notify.N3_ERGEBNIS, "Beschlossen", "<p>x</p>",
                     "/council/decision?id=1", jetzt=_zeit("2026-08-18", 22, 40))
    assert notify.zustellen(store, jetzt=_zeit("2026-08-18", 23, 10)) == 0


def test_am_morgen_kommt_das_von_nachts_an(store, monkeypatch):
    owner = _konto(store)
    raus: list[str] = []
    monkeypatch.setattr("nwz.delivery.deliver_message",
                        lambda o, html, email_subject, push_url="/": raus.append(email_subject))
    notify.einreihen(store, owner, notify.N3_ERGEBNIS, "Radwege: angenommen", "<p>x</p>",
                     "/council/decision?id=1", jetzt=_zeit("2026-08-18", 22, 40))
    assert notify.zustellen(store, jetzt=_zeit("2026-08-19", 7, 0)) == 1
    assert raus == ["Radwege: angenommen"]


# ---- Tagesgrenze ------------------------------------------------------------

def _einreihen(store, owner, n: int, jetzt):
    for i in range(n):
        notify.einreihen(store, owner, notify.N1_TAGESORDNUNG, f"Meldung {i + 1}",
                         f"<p>{i + 1}</p>", f"/council?ksinr={i}", jetzt=jetzt)


def test_zwei_gehen_einzeln_raus(store, monkeypatch):
    owner = _konto(store)
    raus: list[str] = []
    monkeypatch.setattr("nwz.delivery.deliver_message",
                        lambda o, html, email_subject, push_url="/": raus.append(email_subject))
    jetzt = _zeit("2026-08-18", 9)
    _einreihen(store, owner, 2, jetzt)
    assert notify.zustellen(store, jetzt=jetzt) == 2
    assert raus == ["Meldung 1", "Meldung 2"]


def test_ab_der_dritten_wird_gebuendelt(store, monkeypatch):
    """Fünf Anlässe an einem Tag → zwei Zustellungen: eine einzeln, eine als Bündel."""
    owner = _konto(store)
    raus: list[tuple[str, str]] = []
    monkeypatch.setattr("nwz.delivery.deliver_message",
                        lambda o, html, email_subject, push_url="/": raus.append((email_subject, html)))
    jetzt = _zeit("2026-08-18", 9)
    _einreihen(store, owner, 5, jetzt)

    assert notify.zustellen(store, jetzt=jetzt) == 2
    assert raus[0][0] == "Meldung 1"
    assert raus[1][0] == "4 Neuigkeiten aus dem Rat"
    # Nichts geht verloren: die restlichen vier stehen im Bündel.
    for i in (2, 3, 4, 5):
        assert f"Meldung {i}" in raus[1][1]
    # Und nichts bleibt offen liegen.
    assert store.due_notifications(owner, "2999-01-01") == []


def test_die_grenze_gilt_ueber_den_ganzen_tag(store, monkeypatch):
    """Zwei am Morgen, dann kommt mittags etwas nach: das wartet auf morgen."""
    owner = _konto(store)
    raus: list[str] = []
    monkeypatch.setattr("nwz.delivery.deliver_message",
                        lambda o, html, email_subject, push_url="/": raus.append(email_subject))
    _einreihen(store, owner, 2, _zeit("2026-08-18", 8))
    assert notify.zustellen(store, jetzt=_zeit("2026-08-18", 8)) == 2

    notify.einreihen(store, owner, notify.N3_ERGEBNIS, "Nachzügler", "<p>x</p>",
                     "/council/decision?id=9", jetzt=_zeit("2026-08-18", 13))
    assert notify.zustellen(store, jetzt=_zeit("2026-08-18", 13)) == 0
    assert raus == ["Meldung 1", "Meldung 2"]

    # Am nächsten Tag ist die Grenze wieder frei — und der Nachzügler kommt an.
    assert notify.zustellen(store, jetzt=_zeit("2026-08-19", 9)) == 1
    assert raus[-1] == "Nachzügler"


def test_die_grenze_gilt_pro_person(store, monkeypatch):
    a, b = _konto(store, "a@x.de"), _konto(store, "b@x.de")
    raus: list[int] = []
    monkeypatch.setattr("nwz.delivery.deliver_message",
                        lambda o, html, email_subject, push_url="/": raus.append(o["owner_id"]))
    jetzt = _zeit("2026-08-18", 9)
    _einreihen(store, a, 2, jetzt)
    _einreihen(store, b, 2, jetzt)
    assert notify.zustellen(store, jetzt=jetzt) == 4
    assert raus.count(a) == 2 and raus.count(b) == 2


def test_ein_buendel_zaehlt_als_eine_zustellung(store, monkeypatch):
    """Sonst wäre die Grenze nach dem ersten Bündel für immer erschöpft."""
    owner = _konto(store)
    monkeypatch.setattr("nwz.delivery.deliver_message", lambda *a, **k: None)
    _einreihen(store, owner, 5, _zeit("2026-08-18", 9))
    notify.zustellen(store, jetzt=_zeit("2026-08-18", 9))
    assert store.notifications_sent_on(owner, "2026-08-18") == 2


# ---- Grenze 4: jede Meldung hat ein Ziel -----------------------------------

def test_ohne_ziel_wird_nichts_eingereiht(store):
    owner = _konto(store)
    with pytest.raises(ValueError):
        notify.einreihen(store, owner, notify.N1_TAGESORDNUNG, "ohne Ziel", "<p>x</p>", "")


def test_gesperrtes_konto_bekommt_nichts(store, monkeypatch):
    owner = _konto(store)
    store.set_web_user_status(owner, "pending")
    monkeypatch.setattr("nwz.delivery.deliver_message",
                        lambda *a, **k: pytest.fail("gesperrte Konten bekommen keine Post"))
    notify.einreihen(store, owner, notify.N1_TAGESORDNUNG, "x", "<p>x</p>", "/council",
                     jetzt=_zeit("2026-08-18", 9))
    assert notify.zustellen(store, jetzt=_zeit("2026-08-18", 9)) == 0


# ---- Die zwei neuen Entscheidungen in check_committees ----------------------

def test_themen_treffer_gewinnt(store):
    """30a: Wer schon weiß, WELCHER TOP ihn betrifft, braucht daneben nicht die
    Meldung, dass das Gremium überhaupt tagt."""
    owner = _konto(store)
    thema = store.add_topic(owner, "Radwege", "Ausbau von Radwegen")
    assert store.has_agenda_match(owner, 42) is False
    store.replace_agenda_matches(owner, 42, "h1", {thema.id: ["Ö 6"]})
    assert store.has_agenda_match(owner, 42) is True
    assert store.has_agenda_match(owner, 43) is False       # andere Sitzung
    assert store.has_agenda_match(owner + 1, 42) is False   # anderes Konto


def test_aenderungsmeldung_nur_kurz_vor_der_sitzung():
    """Ändert sich eine Tagesordnung drei Wochen vorher, ist das Verwaltung,
    keine Nachricht. Das 48-Stunden-Fenster entscheidet darüber."""
    import importlib.util
    from datetime import date, timedelta
    from pathlib import Path

    pfad = Path(__file__).resolve().parent.parent / "scripts" / "check_committees.py"
    spec = importlib.util.spec_from_file_location("check_committees", pfad)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)

    morgen = (date.today() + timedelta(days=1)).isoformat()
    in_drei_wochen = (date.today() + timedelta(days=21)).isoformat()
    gestern = (date.today() - timedelta(days=1)).isoformat()

    assert modul._stunden_bis(morgen, "17:00") <= 48
    assert modul._stunden_bis(in_drei_wochen, "17:00") > 48
    assert modul._stunden_bis(gestern, "17:00") < 0
    # Unbrauchbare Angaben blockieren nicht: lieber melden als schweigen.
    assert modul._stunden_bis("", "") == 0.0
    assert modul._stunden_bis(in_drei_wochen, "kaputt") > 48   # 18-Uhr-Annahme
