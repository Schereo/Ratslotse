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

from kern import notify
from kern.store import Store

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
    monkeypatch.setattr("kern.delivery.deliver_message",
                        lambda *a, **k: pytest.fail("in der Nachtruhe darf nichts rausgehen"))
    notify.einreihen(store, owner, notify.N3_ERGEBNIS, "Beschlossen", "<p>x</p>",
                     "/council/decision?id=1", jetzt=_zeit("2026-08-18", 22, 40))
    assert notify.zustellen(store, jetzt=_zeit("2026-08-18", 23, 10)) == 0


def test_am_morgen_kommt_das_von_nachts_an(store, monkeypatch):
    owner = _konto(store)
    raus: list[str] = []
    monkeypatch.setattr("kern.delivery.deliver_message",
                        lambda o, html, email_subject, push_url="/", push_text=None: (raus.append(email_subject), ["email"])[1])
    notify.einreihen(store, owner, notify.N3_ERGEBNIS, "Radwege: angenommen", "<p>x</p>",
                     "/council/decision?id=1", jetzt=_zeit("2026-08-18", 22, 40))
    assert notify.zustellen(store, jetzt=_zeit("2026-08-19", 7, 0)) == 1
    assert raus == ["Radwege: angenommen"]


def test_push_kurztext_reist_bis_zur_zustellung(store, monkeypatch):
    """Tims Wunsch 18.08.: Die Push-Vorschau soll die Sache nennen, nicht den
    plattgeklopften Mail-Kopf. Der Kurztext wandert mit durch die Warteschlange
    — aber nur bei Einzelzustellung; ein Bündel baut seinen eigenen Text."""
    owner = _konto(store)
    gesehen: list[str | None] = []
    monkeypatch.setattr(
        "kern.delivery.deliver_message",
        lambda o, html, email_subject, push_url="/", push_text=None:
            (gesehen.append(push_text), ["email"])[1])
    jetzt = _zeit("2026-08-18", 9)
    notify.einreihen(store, owner, notify.N1_TAGESORDNUNG, "X: Tagesordnung geändert",
                     "<p>lange Mail</p>", "/council?ksinr=1", jetzt=jetzt,
                     push_text="Ein Punkt ist neu.")
    notify.einreihen(store, owner, notify.N1_TAGESORDNUNG, "Y: Tagesordnung ist da",
                     "<p>lange Mail</p>", "/council?ksinr=2", jetzt=jetzt)
    assert notify.zustellen(store, jetzt=jetzt) == 2
    assert gesehen == ["Ein Punkt ist neu.", None]


def test_buendel_traegt_keinen_einzel_kurztext(store, monkeypatch):
    """Drei Meldungen mit Kurztext → die dritte geht im Bündel auf, und das
    Bündel darf nicht den Kurztext EINER Meldung als Push-Text tragen — es
    nennt stattdessen die Titel aller gebündelten Posten."""
    owner = _konto(store)
    gesehen: list[str | None] = []
    monkeypatch.setattr(
        "kern.delivery.deliver_message",
        lambda o, html, email_subject, push_url="/", push_text=None:
            (gesehen.append(push_text), ["email"])[1])
    jetzt = _zeit("2026-08-18", 9)
    for i in range(3):
        notify.einreihen(store, owner, notify.N1_TAGESORDNUNG, f"M {i}",
                         f"<p>{i}</p>", f"/council?ksinr={i}", jetzt=jetzt,
                         push_text=f"Kurz {i}")
    assert notify.zustellen(store, jetzt=jetzt) == 2  # 1 einzeln + 1 Bündel
    assert gesehen[0] == "Kurz 0"
    assert gesehen[1] == "M 1 · M 2"


def test_buendel_traegt_volle_inhalte(store, monkeypatch):
    """Die Bündel-Mail ist keine Linkliste: Sie erklärt, warum gebündelt wird,
    und jeder Posten steht mit dem vollen Inhalt seiner Einzel-Mail darin."""
    owner = _konto(store)
    raus: list[str] = []
    monkeypatch.setattr(
        "kern.delivery.deliver_message",
        lambda o, html, email_subject, push_url="/", push_text=None:
            (raus.append(html), ["email"])[1])
    jetzt = _zeit("2026-08-18", 9)
    for i in range(3):
        notify.einreihen(store, owner, notify.N1_TAGESORDNUNG, f"M {i}",
                         f"<p>Inhalt der Meldung {i}</p>", f"/council?ksinr={i}",
                         jetzt=jetzt)
    notify.zustellen(store, jetzt=jetzt)

    buendel = raus[-1]
    assert "Damit dein Postfach ruhig bleibt" in buendel
    for i in (1, 2):
        assert f"M {i}" in buendel                        # Titel als Überschrift …
        assert f"<p>Inhalt der Meldung {i}</p>" in buendel  # … samt vollem Körper


# ---- Tagesgrenze ------------------------------------------------------------

def _einreihen(store, owner, n: int, jetzt):
    for i in range(n):
        notify.einreihen(store, owner, notify.N1_TAGESORDNUNG, f"Meldung {i + 1}",
                         f"<p>{i + 1}</p>", f"/council?ksinr={i}", jetzt=jetzt)


def test_zwei_gehen_einzeln_raus(store, monkeypatch):
    owner = _konto(store)
    raus: list[str] = []
    monkeypatch.setattr("kern.delivery.deliver_message",
                        lambda o, html, email_subject, push_url="/", push_text=None: (raus.append(email_subject), ["email"])[1])
    jetzt = _zeit("2026-08-18", 9)
    _einreihen(store, owner, 2, jetzt)
    assert notify.zustellen(store, jetzt=jetzt) == 2
    assert raus == ["Meldung 1", "Meldung 2"]


def test_ab_der_dritten_wird_gebuendelt(store, monkeypatch):
    """Fünf Anlässe an einem Tag → zwei Zustellungen: eine einzeln, eine als Bündel."""
    owner = _konto(store)
    raus: list[tuple[str, str]] = []
    monkeypatch.setattr("kern.delivery.deliver_message",
                        lambda o, html, email_subject, push_url="/", push_text=None: (raus.append((email_subject, html)), ["email"])[1])
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
    monkeypatch.setattr("kern.delivery.deliver_message",
                        lambda o, html, email_subject, push_url="/", push_text=None: (raus.append(email_subject), ["email"])[1])
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
    monkeypatch.setattr("kern.delivery.deliver_message",
                        lambda o, html, email_subject, push_url="/", push_text=None: (raus.append(o["owner_id"]), ["email"])[1])
    jetzt = _zeit("2026-08-18", 9)
    _einreihen(store, a, 2, jetzt)
    _einreihen(store, b, 2, jetzt)
    assert notify.zustellen(store, jetzt=jetzt) == 4
    assert raus.count(a) == 2 and raus.count(b) == 2


def test_ein_buendel_zaehlt_als_eine_zustellung(store, monkeypatch):
    """Sonst wäre die Grenze nach dem ersten Bündel für immer erschöpft."""
    owner = _konto(store)
    monkeypatch.setattr("kern.delivery.deliver_message", lambda *a, **k: ["email"])
    _einreihen(store, owner, 5, _zeit("2026-08-18", 9))
    notify.zustellen(store, jetzt=_zeit("2026-08-18", 9))
    assert store.notifications_sent_on(owner, "2026-08-18") == 2


# ---- Termingebundene Meldungen haben ihr eigenes Kontingent -----------------

def _vorabend_einreihen(store, owner, jetzt, titel="18. August, 16:45 Uhr: Rat tagt"):
    return notify.einreihen(store, owner, notify.N5_VORABEND, titel, "<p>x</p>",
                            "/council?tab=sessions&ksinr=1", jetzt=jetzt)


def test_die_vorabend_erinnerung_kommt_trotz_erschoepfter_grenze(store, monkeypatch):
    """Tims Wunsch 17.08.2026. Der echte Fall: Am 16.08. waren die zwei
    Meldungen schon um 7 Uhr draußen, die Erinnerung lag ab 18 Uhr fertig da —
    und ging erst am Sitzungstag selbst raus."""
    owner = _konto(store)
    store.set_notify_prefs(owner, {notify.N5_VORABEND: True})   # Vorgabe ist AUS
    raus: list[str] = []
    monkeypatch.setattr("kern.delivery.deliver_message",
                        lambda o, html, email_subject, push_url="/", push_text=None: (raus.append(email_subject), ["email"])[1])

    _einreihen(store, owner, 2, _zeit("2026-08-17", 7))
    assert notify.zustellen(store, jetzt=_zeit("2026-08-17", 7)) == 2

    _vorabend_einreihen(store, owner, _zeit("2026-08-17", 18))
    assert notify.zustellen(store, jetzt=_zeit("2026-08-17", 18)) == 1
    assert raus[-1] == "18. August, 16:45 Uhr: Rat tagt"
    assert store.due_notifications(owner, "2999-01-01") == []


def test_die_erinnerung_nimmt_keiner_anderen_meldung_den_platz(store, monkeypatch):
    """Die Umkehrung: Ein eigenes Kontingent heißt auch, dass die Erinnerung
    das der übrigen Meldungen nicht anknabbert."""
    owner = _konto(store)
    store.set_notify_prefs(owner, {notify.N5_VORABEND: True})
    raus: list[str] = []
    monkeypatch.setattr("kern.delivery.deliver_message",
                        lambda o, html, email_subject, push_url="/", push_text=None: (raus.append(email_subject), ["email"])[1])

    jetzt = _zeit("2026-08-17", 18)
    _vorabend_einreihen(store, owner, jetzt)
    _einreihen(store, owner, 2, jetzt)
    assert notify.zustellen(store, jetzt=jetzt) == 3          # 1 termingebunden + 2 übrige
    assert raus[0] == "18. August, 16:45 Uhr: Rat tagt"       # der Termin geht vor
    assert raus[1:] == ["Meldung 1", "Meldung 2"]


def test_auch_termingebundenes_wird_ab_der_dritten_gebuendelt(store, monkeypatch):
    """Kein Freifahrtschein: Ein Abend mit vier Sitzungen schickt nicht vier
    Erinnerungen einzeln."""
    owner = _konto(store)
    store.set_notify_prefs(owner, {notify.N5_VORABEND: True})
    raus: list[str] = []
    monkeypatch.setattr("kern.delivery.deliver_message",
                        lambda o, html, email_subject, push_url="/", push_text=None: (raus.append(email_subject), ["email"])[1])
    jetzt = _zeit("2026-08-17", 18)
    for i in range(4):
        _vorabend_einreihen(store, owner, jetzt, f"Gremium {i + 1} tagt")
    assert notify.zustellen(store, jetzt=jetzt) == 2
    assert raus == ["Gremium 1 tagt", "3 Neuigkeiten aus dem Rat"]


def test_zwei_erinnerungen_am_tag_sind_das_ende(store, monkeypatch):
    """Das eigene Kontingent ist eines, keine Ausnahme von allem: Die dritte
    Erinnerung eines Tages wartet auf morgen wie jede andere Meldung."""
    owner = _konto(store)
    store.set_notify_prefs(owner, {notify.N5_VORABEND: True})
    monkeypatch.setattr("kern.delivery.deliver_message", lambda *a, **k: ["email"])
    _vorabend_einreihen(store, owner, _zeit("2026-08-17", 8), "erste")
    assert notify.zustellen(store, jetzt=_zeit("2026-08-17", 8)) == 1
    _vorabend_einreihen(store, owner, _zeit("2026-08-17", 12), "zweite")
    assert notify.zustellen(store, jetzt=_zeit("2026-08-17", 12)) == 1
    _vorabend_einreihen(store, owner, _zeit("2026-08-17", 18), "dritte")
    assert notify.zustellen(store, jetzt=_zeit("2026-08-17", 18)) == 0
    assert [p["title"] for p in store.due_notifications(owner, "2999-01-01")] == ["dritte"]


def test_die_kontingente_zaehlen_getrennt(store, monkeypatch):
    owner = _konto(store)
    store.set_notify_prefs(owner, {notify.N5_VORABEND: True})
    monkeypatch.setattr("kern.delivery.deliver_message", lambda *a, **k: ["email"])
    jetzt = _zeit("2026-08-17", 18)
    _vorabend_einreihen(store, owner, jetzt)
    _einreihen(store, owner, 3, jetzt)
    notify.zustellen(store, jetzt=jetzt)

    tag = "2026-08-17"
    assert store.notifications_sent_on(owner, tag) == 3            # alles zusammen
    assert store.notifications_sent_on(owner, tag, notify.TERMINGEBUNDEN) == 1
    assert store.notifications_sent_on(owner, tag, notify.TERMINGEBUNDEN, ohne=True) == 2


# ---- Grenze 4: jede Meldung hat ein Ziel -----------------------------------

def test_ohne_ziel_wird_nichts_eingereiht(store):
    owner = _konto(store)
    with pytest.raises(ValueError):
        notify.einreihen(store, owner, notify.N1_TAGESORDNUNG, "ohne Ziel", "<p>x</p>", "")


def test_gesperrtes_konto_bekommt_nichts(store, monkeypatch):
    owner = _konto(store)
    store.set_web_user_status(owner, "pending")
    monkeypatch.setattr("kern.delivery.deliver_message",
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


# ---- Die Schalter (30a/E) ---------------------------------------------------

def test_abgeschalteter_anlass_wird_gar_nicht_erst_eingereiht(store, monkeypatch):
    """Sonst zählte er gegen die Tagesgrenze, ohne je zugestellt zu werden."""
    owner = _konto(store)
    store.set_notify_prefs(owner, {notify.N1_TAGESORDNUNG: False})
    monkeypatch.setattr("kern.delivery.deliver_message", lambda *a, **k: ["email"])

    assert notify.einreihen(store, owner, notify.N1_TAGESORDNUNG, "x", "<p>x</p>",
                            "/council", jetzt=_zeit("2026-08-18", 9)) == 0
    # Ein anderer Anlass bleibt unberührt.
    assert notify.einreihen(store, owner, notify.N3_ERGEBNIS, "y", "<p>y</p>",
                            "/council/decision?id=1", jetzt=_zeit("2026-08-18", 9)) > 0
    assert [p["kind"] for p in store.due_notifications(owner, "2999-01-01")] == ["n3_ergebnis"]


def test_vorgaben_aus_dem_artboard():
    """Vier an (samt der N1-Unter-Option „Änderungen"), N5/N6 bewusst aus."""
    an = {k for k, v in notify.NOTIFY_DEFAULTS.items() if v}
    aus = {k for k, v in notify.NOTIFY_DEFAULTS.items() if not v}
    assert an == {notify.N1_TAGESORDNUNG, notify.N1_AENDERUNG, notify.N2_THEMA,
                  notify.N3_ERGEBNIS, notify.N4_VORGANG}
    assert aus == {notify.N5_VORABEND, notify.N6_WOCHE}
    # Jede Art hat eine Beschriftung — sonst fehlte sie stumm in den Einstellungen.
    assert set(notify.NOTIFY_LABELS) == set(notify.NOTIFY_DEFAULTS)
    # Und jede Unter-Option zeigt auf einen Anlass, den es gibt.
    for kind, eltern in notify.NOTIFY_PARENT.items():
        assert kind in notify.NOTIFY_DEFAULTS and eltern in notify.NOTIFY_DEFAULTS


def test_unbekannte_schalter_landen_nicht_in_der_datenbank(store):
    owner = _konto(store)
    store.set_notify_prefs(owner, {notify.N5_VORABEND: True, "beliebig": True})
    assert store.get_notify_prefs(owner) == {notify.N5_VORABEND: True}


# ---- N3: die Ergebnis-Meldung ----------------------------------------------

def test_ergebnis_meldung_nennt_das_sitzungsdatum(store, monkeypatch, tmp_path):
    """Sie kommt Wochen nach der Sitzung — der Text darf keine Frische behaupten."""
    from council.ergebnisse import melde_ergebnisse
    from council.scraper import AgendaItem, CouncilSession
    from council.store import CouncilStore

    owner = _konto(store)
    thema = store.add_topic(owner, "Radwege", "Ausbau von Radwegen")
    store.replace_agenda_matches(owner, 4652, "h1", {thema.id: ["Ö 6"]})

    council = CouncilStore(tmp_path / "council.sqlite")
    council.save_session(CouncilSession(4652, "Verkehrsausschuss", "2026-06-08", "17:00", "Fleiwa",
                                        agenda_items=[AgendaItem("Ö 6", "Radweg Nadorster Straße")]))
    with council._conn:
        council._insert_decision(4652, 0, "decision", None, "Ö 6", "Radweg Nadorster Straße",
                                 "Wird ausgebaut.", "angenommen", "mehrheitlich", 11, 0,
                                 ["SPD"], None, None, None)

    assert melde_ergebnisse(council, store, [4652]) == 1
    posten = store.due_notifications(owner, "2999-01-01")
    assert len(posten) == 1
    p = posten[0]
    assert p["kind"] == "n3_ergebnis"
    assert p["title"] == "Radweg Nadorster Straße: angenommen"
    assert "Verkehrsausschuss am 8. Juni" in p["body_html"]      # Datum steht drin
    assert "mehrheitlich" in p["body_html"] and "11 dagegen" in p["body_html"]
    assert p["url"].startswith("/council/decision?id=")           # Grenze 4

    # Zweiter Lauf meldet nichts nach.
    assert melde_ergebnisse(council, store, [4652]) == 0
    council.close()


def test_ohne_vorherige_meldung_kein_ergebnis(store, tmp_path):
    """Wer nie etwas zu dieser Sitzung gehört hat, wird nicht nachträglich behelligt."""
    from council.ergebnisse import melde_ergebnisse
    from council.scraper import CouncilSession
    from council.store import CouncilStore

    _konto(store)
    council = CouncilStore(tmp_path / "council.sqlite")
    council.save_session(CouncilSession(4652, "Verkehrsausschuss", "2026-06-08", "17:00", "Fleiwa"))
    with council._conn:
        council._insert_decision(4652, 0, "decision", None, "Ö 6", "Radweg", "x",
                                 "angenommen", None, None, None, [], None, None, None)
    assert melde_ergebnisse(council, store, [4652]) == 0
    council.close()


# ---- N5 Vorabend + N6 Wochenüberblick (30a, Stufe 3) -----------------------

def _council(tmp_path):
    from council.store import CouncilStore
    return CouncilStore(tmp_path / "council.sqlite")


def test_vorabend_erinnert_an_die_sitzung_von_morgen(store, tmp_path):
    from datetime import date, timedelta
    from council.abendmeldungen import vorabend
    from council.scraper import AgendaItem, CouncilSession

    owner = _konto(store)
    thema = store.add_topic(owner, "Radwege", "Ausbau von Radwegen")
    store.set_notify_prefs(owner, {notify.N5_VORABEND: True})   # Vorgabe ist AUS
    store.replace_agenda_matches(owner, 4652, "h1", {thema.id: ["Ö 6"]})

    heute = date(2026, 8, 17)
    council = _council(tmp_path)
    council.save_session(CouncilSession(4652, "Verkehrsausschuss", "2026-08-18", "17:00", "Fleiwa",
                                        agenda_items=[AgendaItem("Ö 6", "Radweg")]))

    assert vorabend(council, store, heute) == 1
    p = store.due_notifications(owner, "2999-01-01")[0]
    assert p["kind"] == "n5_vorabend"
    # Der Titel nennt den Tag, nicht „Morgen": Eingereiht wird am Vorabend,
    # zugestellt aber ggf. erst am nächsten Morgen (Tagesgrenze) — dann wäre
    # „Morgen" der Sitzungstag selbst. Tims Befund 17.08.2026.
    assert "18. August, 17:00 Uhr" in p["title"] and "Radwege" in p["title"]
    assert "Morgen" not in p["title"]
    assert "Ö 6" in p["body_html"] and "Fleiwa" in p["body_html"]
    assert p["url"] == "/council?tab=sessions&ksinr=4652"

    # Übermorgen ist nicht morgen.
    assert vorabend(council, store, heute - timedelta(days=1)) == 0
    council.close()


def test_vorabend_ist_ab_werk_aus(store, tmp_path):
    from datetime import date
    from council.abendmeldungen import vorabend
    from council.scraper import CouncilSession

    owner = _konto(store)
    thema = store.add_topic(owner, "Radwege", "Ausbau")
    store.replace_agenda_matches(owner, 4652, "h1", {thema.id: ["Ö 6"]})
    council = _council(tmp_path)
    council.save_session(CouncilSession(4652, "Verkehrsausschuss", "2026-08-18", "17:00", "Fleiwa"))
    assert vorabend(council, store, date(2026, 8, 17)) == 0     # N5 steht auf aus
    council.close()


def test_wochenueberblick_fasst_die_woche_zusammen(store, tmp_path):
    from datetime import date
    from council.abendmeldungen import wochenueberblick
    from council.scraper import CouncilSession

    owner = _konto(store)
    thema = store.add_topic(owner, "Radwege", "Ausbau")
    store.set_notify_prefs(owner, {notify.N6_WOCHE: True})

    council = _council(tmp_path)
    council.save_session(CouncilSession(88, "Rat", "2026-08-14", "18:00", "Rathaus"))
    with council._conn:
        council._insert_decision(88, 0, "decision", None, "Ö 1", "Radweg A", "x",
                                 "angenommen", None, None, None, [], None, None, None)
        council._insert_decision(88, 1, "decision", None, "Ö 2", "Radweg B", "x",
                                 "abgelehnt", None, None, None, [], None, None, None)
    ids = [r[0] for r in council._conn.execute("SELECT id FROM council_decisions ORDER BY id")]
    store.save_topic_decision_matches(thema.id, owner, [(i, 0.9) for i in ids])

    assert wochenueberblick(council, store, date.today()) == 1
    p = store.due_notifications(owner, "2999-01-01")[0]
    assert p["kind"] == "n6_woche"
    assert p["title"] == "Diese Woche: 2 Beschlüsse zu deinen Themen"
    assert "angenommen" in p["body_html"] and "abgelehnt" in p["body_html"]
    council.close()


def _zwei_beschluesse(council, ksinr: int = 88):
    from council.scraper import CouncilSession

    council.save_session(CouncilSession(ksinr, "Rat", "2026-08-14", "18:00", "Rathaus"))
    with council._conn:
        council._insert_decision(ksinr, 0, "decision", None, "Ö 1", "Radweg A", "x",
                                 "angenommen", None, None, None, [], None, None, None)
        council._insert_decision(ksinr, 1, "decision", None, "Ö 2", "Radweg B", "x",
                                 "abgelehnt", None, None, None, [], None, None, None)
    return [r[0] for r in council._conn.execute(
        "SELECT id FROM council_decisions ORDER BY id")]


def test_der_matching_lauf_datiert_bekannte_treffer_nicht_um(store, tmp_path):
    """Der wöchentliche Lauf legt dieselben Treffer neu ab. Setzte er dabei
    ``matched_at`` zurück, meldete der Wochenüberblick am selben Abend den
    kompletten Bestand als Neuigkeit der Woche — Tims Befund 17.08.2026,
    „Diese Woche: 119 Beschlüsse zu deinen Themen" (in der Prod-DB trugen
    danach alle 919 Trefferzeilen dasselbe Datum)."""
    from datetime import date
    from council.abendmeldungen import wochenueberblick

    owner = _konto(store)
    thema = store.add_topic(owner, "Radwege", "Ausbau")
    store.set_notify_prefs(owner, {notify.N6_WOCHE: True})
    council = _council(tmp_path)
    ids = _zwei_beschluesse(council)

    store.save_topic_decision_matches(thema.id, owner, [(i, 0.9) for i in ids])
    with store._conn:      # so sähe es eine Woche später aus
        store._conn.execute("UPDATE council_topic_matches SET matched_at = '2026-01-01T00:00:00'")

    # Derselbe Lauf noch einmal, mit neuen Scores.
    store.save_topic_decision_matches(thema.id, owner, [(i, 0.95) for i in ids])
    rows = list(store._conn.execute(
        "SELECT matched_at, score FROM council_topic_matches ORDER BY decision_id"))
    assert [r[0] for r in rows] == ["2026-01-01T00:00:00"] * 2   # Datum bleibt
    assert [r[1] for r in rows] == [0.95, 0.95]                  # Score zieht nach
    assert wochenueberblick(council, store, date.today()) == 0   # nichts Neues
    council.close()


def test_wirklich_neue_treffer_zaehlen_weiter(store, tmp_path):
    """Die Gegenprobe: Ein Beschluss, der vorher nicht dabei war, ist neu —
    und Weggefallenes verschwindet."""
    owner = _konto(store)
    thema = store.add_topic(owner, "Radwege", "Ausbau")
    council = _council(tmp_path)
    a, b = _zwei_beschluesse(council)

    store.save_topic_decision_matches(thema.id, owner, [(a, 0.9)])
    with store._conn:
        store._conn.execute("UPDATE council_topic_matches SET matched_at = '2026-01-01T00:00:00'")
    store.save_topic_decision_matches(thema.id, owner, [(a, 0.9), (b, 0.8)])

    stand = dict(store._conn.execute(
        "SELECT decision_id, matched_at FROM council_topic_matches").fetchall())
    assert stand[a] == "2026-01-01T00:00:00"
    assert stand[b] > "2026-01-01T00:00:00"      # frisch gestempelt

    store.save_topic_decision_matches(thema.id, owner, [(b, 0.8)])
    assert [r[0] for r in store._conn.execute(
        "SELECT decision_id FROM council_topic_matches")] == [b]
    council.close()


def test_reparaturlauf_stempelt_nichts_als_neu(store, tmp_path):
    """``--ohne-meldungen`` nach einer Neu-Extraktion: Dieselben Beschlüsse
    tragen neue IDs, also sind formal alle Treffer neu. Sie dürfen trotzdem
    nicht als Neuigkeit der Woche gelten."""
    from datetime import date
    from council.abendmeldungen import wochenueberblick

    owner = _konto(store)
    thema = store.add_topic(owner, "Radwege", "Ausbau")
    store.set_notify_prefs(owner, {notify.N6_WOCHE: True})
    council = _council(tmp_path)
    ids = _zwei_beschluesse(council)

    store.save_topic_decision_matches(thema.id, owner, [(i, 0.9) for i in ids], als_neu=False)
    assert [r[0] for r in store._conn.execute(
        "SELECT matched_at FROM council_topic_matches")] == ["", ""]
    assert wochenueberblick(council, store, date.today()) == 0
    council.close()


def test_altbestand_wird_einmalig_entstempelt(store, tmp_path):
    """Die Reparatur beim Öffnen: Der Bestand aus der Zeit vor dem Fix trägt
    lauter frische Daten. Ohne sie käme die 119er-Meldung noch ein zweites Mal
    — der Fehler behoben, die Meldung trotzdem da."""
    from kern.store import Store

    owner = _konto(store)
    thema = store.add_topic(owner, "Radwege", "Ausbau")
    council = _council(tmp_path)
    ids = _zwei_beschluesse(council)
    store.save_topic_decision_matches(thema.id, owner, [(i, 0.9) for i in ids])
    with store._conn:      # so sah der Bestand am 17.08. aus …
        store._conn.execute("UPDATE council_topic_matches SET matched_at = '2026-08-16T03:09:00'")
        store._conn.execute("PRAGMA user_version = 0")
    pfad = store.path
    store.close()

    zweiter = Store(pfad)
    assert [r[0] for r in zweiter._conn.execute(
        "SELECT matched_at FROM council_topic_matches")] == ["", ""]

    # … und beim nächsten Öffnen bleibt ein echtes Datum stehen.
    with zweiter._conn:
        zweiter._conn.execute("UPDATE council_topic_matches SET matched_at = '2026-09-01T00:00:00'")
    zweiter.close()
    dritter = Store(pfad)
    assert [r[0] for r in dritter._conn.execute(
        "SELECT matched_at FROM council_topic_matches")] == ["2026-09-01T00:00:00"] * 2
    dritter.close()
    council.close()


def test_ohne_beschluesse_schweigt_der_wochenueberblick(store, tmp_path):
    """30a, Grenze 3: nie ohne Ereignis — Sommerpause inklusive."""
    from datetime import date
    from council.abendmeldungen import wochenueberblick

    owner = _konto(store)
    store.add_topic(owner, "Radwege", "Ausbau")
    store.set_notify_prefs(owner, {notify.N6_WOCHE: True})
    council = _council(tmp_path)
    assert wochenueberblick(council, store, date.today()) == 0
    council.close()


# ---- Was passiert, wenn der Versand klemmt? ----

def test_erfolglose_zustellung_bleibt_in_der_warteschlange(store, monkeypatch):
    """Ein Ausfall beim Versand darf keine Meldung verschlucken.

    ``deliver_message`` fängt Fehler selbst ab und meldet über den Rückgabewert,
    welche Kanäle bedient wurden — leer heißt: nichts ist rausgegangen. Vorher
    wurde trotzdem ``sent_at`` gesetzt; ein Resend-Ausfall ließ die Meldung
    lautlos für immer verschwinden, und zwar genau die, wegen der jemand die App
    installiert hat.
    """
    owner = _konto(store)
    monkeypatch.setattr("kern.delivery.deliver_message", lambda *a, **k: [])
    notify.einreihen(store, owner, notify.N2_THEMA, "Radweg", "<p>x</p>",
                     "/council/decision?id=1", jetzt=_zeit("2026-08-18", 9))

    assert notify.zustellen(store, jetzt=_zeit("2026-08-18", 9)) == 0
    offen = store.due_notifications(owner, _zeit("2026-08-18", 10).isoformat(timespec="seconds"))
    assert len(offen) == 1, "die Meldung muss liegen bleiben"

    # Und sie geht raus, sobald der Versand wieder läuft.
    raus: list[str] = []
    monkeypatch.setattr("kern.delivery.deliver_message",
                        lambda o, html, email_subject, push_url="/", push_text=None: (raus.append(email_subject), ["email"])[1])
    assert notify.zustellen(store, jetzt=_zeit("2026-08-19", 9)) == 1
    assert raus == ["Radweg"]


def test_dauerhaft_unzustellbares_gibt_irgendwann_auf(store, monkeypatch):
    """Sonst beschäftigt eine tote Adresse jeden Lauf aufs Neue."""
    owner = _konto(store)
    monkeypatch.setattr("kern.delivery.deliver_message", lambda *a, **k: [])
    notify.einreihen(store, owner, notify.N2_THEMA, "x", "<p>x</p>", "/council",
                     jetzt=_zeit("2026-08-18", 9))

    for tag in range(18, 18 + Store.MAX_ZUSTELLVERSUCHE):
        notify.zustellen(store, jetzt=_zeit(f"2026-08-{tag}", 9))

    assert store.due_notifications(owner, _zeit("2026-09-01", 9).isoformat(timespec="seconds")) == []
    aufgegeben = store.undeliverable_notifications()
    assert len(aufgegeben) == 1 and aufgegeben[0]["attempts"] == Store.MAX_ZUSTELLVERSUCHE


def test_ein_kaputtes_konto_reisst_die_anderen_nicht_mit(store, monkeypatch):
    """Vorher brach der ganze Lauf ab — alle nachfolgenden Konten gingen leer aus."""
    a = _konto(store, "a@b.de")
    b = _konto(store, "b@b.de")
    notify.einreihen(store, a, notify.N2_THEMA, "für A", "<p>a</p>", "/x", jetzt=_zeit("2026-08-18", 9))
    notify.einreihen(store, b, notify.N2_THEMA, "für B", "<p>b</p>", "/y", jetzt=_zeit("2026-08-18", 9))

    def kaputt_fuer_a(o, html, email_subject, push_url="/", push_text=None):
        if o["owner_id"] == a:
            raise RuntimeError("Gateway weg")
        return ["email"]

    monkeypatch.setattr("kern.delivery.deliver_message", kaputt_fuer_a)
    assert notify.zustellen(store, jetzt=_zeit("2026-08-18", 9)) == 1, "B muss trotzdem Post bekommen"
    assert len(store.due_notifications(a, _zeit("2026-08-18", 10).isoformat(timespec="seconds"))) == 1
    assert store.due_notifications(b, _zeit("2026-08-18", 10).isoformat(timespec="seconds")) == []


# ---- Wohin ein Antippen führt ----

def test_ziel_muss_ein_app_pfad_sein(store):
    """Aus einem echten Fehlerbericht: „Fliegerhorst kommt auf den Tisch"
    angetippt — und die App stand auf der Startseite.

    Ursache: N1 und N2 übergaben die Ratsinfo-Adresse
    (`https://buergerinfo.oldenburg.de/...`) als Tap-Ziel. Der Handler in
    `lib/push.ts` navigiert aber nur zu Zielen, die mit `/` beginnen — bei
    allem anderen tut er wortlos nichts. Die Meldung kam an, führte aber
    nirgendwohin.

    Deshalb weist die Warteschlange externe Adressen jetzt beim Einreihen ab,
    statt sie bis aufs Gerät durchzureichen.
    """
    owner = _konto(store)
    for schlecht in ("https://buergerinfo.oldenburg.de/si0057.php?__ksinr=42",
                     "//fremde.example/pfad",
                     "council/decision?id=1"):
        with pytest.raises(ValueError, match="App-Pfad"):
            notify.einreihen(store, owner, notify.N2_THEMA, "x", "<p>x</p>", schlecht)

    # Der leere Fall bleibt, wie er war (Grenze 4).
    with pytest.raises(ValueError, match="Ziel"):
        notify.einreihen(store, owner, notify.N2_THEMA, "x", "<p>x</p>", "")

    # Und App-Pfade gehen durch.
    assert notify.einreihen(store, owner, notify.N2_THEMA, "x", "<p>x</p>",
                            "/council?tab=sessions&ksinr=42") > 0


def test_buendel_verlinkt_absolut(store, monkeypatch):
    """In der Warteschlange stehen App-Pfade — in einer E-Mail ist ein
    relativer Link tot, es gibt dort keine Basis dafür."""
    owner = _konto(store)
    raus: list[str] = []
    monkeypatch.setattr("kern.delivery.deliver_message",
                        lambda o, html, email_subject, push_url="/", push_text=None: (raus.append(html), ["email"])[1])
    for i in range(3):
        notify.einreihen(store, owner, notify.N2_THEMA, f"Meldung {i}", "<p>x</p>",
                         f"/council/decision?id={i}", jetzt=_zeit("2026-08-18", 9))
    notify.zustellen(store, jetzt=_zeit("2026-08-18", 9))

    buendel = raus[-1]
    assert 'href="https://' in buendel, "Bündel-Links müssen absolut sein"
    assert 'href="/council' not in buendel


def test_tagesordnungs_meldung_nennt_den_punkt(store):
    """Die Meldung soll nicht nur zur Sitzung führen, sondern zur Zeile.

    Der Sprung landete am Sitzungskopf; die Tagesordnung steht weiter unten in
    der aufgeklappten Karte und musste selbst gesucht werden.
    """
    from council.ergebnisse import sitzung_href

    assert sitzung_href(4666) == "/council?tab=sessions&ksinr=4666"
    # Die VOLLE Nummer geht mit: „Ö 6" und „N 6" sind verschiedene Punkte.
    assert sitzung_href(4666, ["Ö 6"]) == "/council?tab=sessions&ksinr=4666&top=%C3%96%206"
    assert sitzung_href(4666, ["Ö 4", "Ö 6"]).endswith("&top=%C3%96%204%2C%C3%96%206")
    # Leeres und Leerraum fallen raus, statt einen sinnlosen Parameter zu bauen.
    assert sitzung_href(4666, []) == sitzung_href(4666)
    assert sitzung_href(4666, ["", "  "]) == sitzung_href(4666)

    # Und das Ergebnis bleibt ein App-Pfad — sonst griffe die Schranke aus
    # `einreihen` und die Meldung käme gar nicht erst in die Warteschlange.
    owner = _konto(store)
    assert notify.einreihen(store, owner, notify.N2_THEMA, "x", "<p>x</p>",
                            sitzung_href(4666, ["Ö 6"])) > 0


# ---- Ganz abschalten (Zustellweg „off") --------------------------------------
#
# Bis hierher musste immer ein Kanal an bleiben: Die Oberfläche verweigerte
# beides-aus, und das Backend kannte keinen anderen Wert. Wer nichts mehr hören
# wollte, hätte die sechs Anlass-Schalter einzeln umlegen müssen. Diese Tests
# halten fest, dass „aus" jetzt an genau einer Stelle greift — beim Einreihen —
# und dass die Warteschlange dabei nicht zum Zwischenlager wird.

def test_abgeschaltet_reiht_gar_nichts_ein(store):
    """Nicht erst die Zustellung schweigt, sondern schon die Warteschlange.

    Sonst zählten unzustellbare Meldungen gegen die Tagesgrenze — und beim
    Wiedereinschalten käme eine Nachlieferung aus genau der Zeit, in der
    jemand ausdrücklich nichts wollte.
    """
    owner = _konto(store)
    store.set_delivery_channel(owner, "off")
    for art in (notify.N1_TAGESORDNUNG, notify.N2_THEMA, notify.N3_ERGEBNIS,
                notify.N4_VORGANG):
        assert notify.einreihen(store, owner, art, "x", "<p>x</p>", "/council") == 0
    assert store.due_notifications(owner, "2999-01-01") == []


def test_abgeschaltet_gilt_auch_gegen_die_vorgaben(store):
    """N1–N4 sind ab Werk AN. „off" schlägt die Vorgabe, nicht umgekehrt."""
    owner = _konto(store)
    store.set_delivery_channel(owner, "off")
    assert notify.gewuenscht(store, owner, notify.N1_TAGESORDNUNG) is False
    store.set_delivery_channel(owner, "email")
    assert notify.gewuenscht(store, owner, notify.N1_TAGESORDNUNG) is True


def test_unteroption_haengt_am_elternteil(store):
    """„Änderungen an Tagesordnungen" ist eine Unter-Option von N1 (Tims Wunsch
    26.08.2026): Abo behalten, nur die Änderungs-Meldungen loswerden — und wer
    N1 ganz abschaltet, bekommt auch keine Änderungs-Meldungen, egal wie der
    Unter-Schalter steht."""
    owner = _konto(store)
    # Ab Werk: beides an.
    assert notify.gewuenscht(store, owner, notify.N1_AENDERUNG) is True

    # Nur die Änderungs-Meldungen abschalten — die Tagesordnung kommt weiter.
    store.set_notify_prefs(owner, {notify.N1_AENDERUNG: False})
    assert notify.gewuenscht(store, owner, notify.N1_TAGESORDNUNG) is True
    assert notify.gewuenscht(store, owner, notify.N1_AENDERUNG) is False

    # N1 aus schlägt durch, auch wenn die Unter-Option selbst an ist.
    store.set_notify_prefs(owner, {notify.N1_TAGESORDNUNG: False,
                                   notify.N1_AENDERUNG: True})
    assert notify.gewuenscht(store, owner, notify.N1_AENDERUNG) is False
    assert notify.einreihen(store, owner, notify.N1_AENDERUNG,
                            "x", "<p>x</p>", "/council") == 0


def test_abschalten_verwirft_was_noch_wartet(store, monkeypatch):
    """Vor dem Abschalten Eingereihtes wird nicht später doch noch zugestellt."""
    owner = _konto(store)
    notify.einreihen(store, owner, notify.N2_THEMA, "Radweg", "<p>x</p>", "/council",
                     jetzt=_zeit("2026-08-18", 9))
    assert len(store.due_notifications(owner, "2999-01-01")) == 1

    store.set_delivery_channel(owner, "off")
    monkeypatch.setattr("kern.delivery.deliver_message",
                        lambda *a, **k: pytest.fail("abgeschaltet — nichts darf rausgehen"))
    assert notify.zustellen(store, jetzt=_zeit("2026-08-18", 10)) == 0
    # Und zwar verworfen, nicht bloß übersprungen: Sonst läge es noch da, wenn
    # kurz darauf wieder eingeschaltet wird.
    assert store.due_notifications(owner, "2999-01-01") == []


def test_abschalten_laesst_die_anderen_konten_in_ruhe(store, monkeypatch):
    a, b = _konto(store, "a@b.de"), _konto(store, "b@b.de")
    store.set_delivery_channel(a, "off")
    for owner_id in (a, b):
        notify.einreihen(store, owner_id, notify.N2_THEMA, "x", "<p>x</p>", "/council",
                         jetzt=_zeit("2026-08-18", 9))
    empfaenger: list[int] = []
    monkeypatch.setattr(
        "kern.delivery.deliver_message",
        lambda o, *a, **k: (empfaenger.append(o["owner_id"]), ["email"])[1])
    assert notify.zustellen(store, jetzt=_zeit("2026-08-18", 10)) == 1
    assert empfaenger == [b]


def test_wieder_einschalten_faengt_bei_null_an(store, monkeypatch):
    """Nach dem Wiedereinschalten kommt Neues an — aber nichts Nachgeholtes."""
    owner = _konto(store)
    notify.einreihen(store, owner, notify.N2_THEMA, "vor dem Abschalten", "<p>alt</p>",
                     "/council", jetzt=_zeit("2026-08-18", 9))
    store.set_delivery_channel(owner, "off")
    notify.zustellen(store, jetzt=_zeit("2026-08-18", 10))   # räumt die Warteschlange

    store.set_delivery_channel(owner, "email")
    notify.einreihen(store, owner, notify.N2_THEMA, "danach", "<p>neu</p>", "/council",
                     jetzt=_zeit("2026-08-19", 9))
    titel: list[str] = []
    monkeypatch.setattr(
        "kern.delivery.deliver_message",
        lambda o, html, email_subject, push_url="/", push_text=None: (titel.append(email_subject), ["email"])[1])
    assert notify.zustellen(store, jetzt=_zeit("2026-08-19", 10)) == 1
    assert titel == ["danach"]


def test_abgeschaltet_bekommt_keine_einrichtungs_erinnerung(store):
    """Auch die freundlich gemeinte Erinnerung schweigt — sonst wäre der
    Aus-Schalter nur eine Bitte."""
    from datetime import timedelta

    def _halb_eingerichtet(email: str) -> int:
        uid = _konto(store, email)
        alt = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat(timespec="seconds")
        with store._conn:
            store._conn.execute(
                "UPDATE web_users SET setup_started_at = ?, setup_updated_at = ?, "
                "setup_step = 2, email_verified = 1 WHERE id = ?", (alt, alt, uid))
        return uid

    still = _halb_eingerichtet("still@b.de")
    laut = _halb_eingerichtet("laut@b.de")
    store.set_delivery_channel(still, "off")

    kandidaten = [u["id"] for u in store.setups_to_remind(older_than_hours=48)]
    assert laut in kandidaten
    assert still not in kandidaten
