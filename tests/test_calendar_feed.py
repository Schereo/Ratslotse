"""Kalender-Abo: Token im Konto, ICS-Feed, Router.

Der Feed ist für fremde Programme gedacht (Apple Kalender, Google, Outlook),
und die sind unnachsichtig: ein Komma ohne Backslash, eine Zeile über 75
Oktett, ein Termin ohne UID — und der ganze Kalender bleibt leer, ohne
Meldung. Deshalb prüfen die Tests die Bytes, nicht nur den Inhalt.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from council.store import CouncilStore
from kern.calendar_feed import _esc, _fold, build_feed, short_committee
from kern.store import Store


# ---- Bausteine ---------------------------------------------------------------

def test_escaping_nach_rfc5545():
    assert _esc("a,b;c\\d\ne") == "a\\,b\;c\\\\d\\ne"


def test_faltung_bricht_nie_mitten_im_zeichen():
    line = "DESCRIPTION:" + "ä" * 100
    parts = _fold(line)
    assert len(parts) > 1
    for part in parts:
        assert len(part.encode("utf-8")) <= 75
    assert all(p.startswith(" ") for p in parts[1:])
    # Zusammengesetzt ergibt sich das Original.
    assert parts[0] + "".join(p[1:] for p in parts[1:]) == line


@pytest.mark.parametrize("voll, kurz", [
    ("Ausschuss für Stadtgrün, Umwelt und Klima", "Stadtgrün, Umwelt & Klima"),
    ("Rat der Stadt Oldenburg", "Rat"),
    ("Umweltausschuss", "Umwelt"),
    ("Sozialausschuss", "Sozial"),
    ("Ausschuss für Finanzen", "Finanzen"),
])
def test_kurzname(voll, kurz):
    assert short_committee(voll) == kurz


# ---- Konto-Token -------------------------------------------------------------

@pytest.fixture
def store(tmp_path):
    s = Store(str(tmp_path / "konten.sqlite"))
    yield s
    s.close()


def _konto(store: Store, email: str = "kalender@example.org") -> int:
    return store.create_web_user(email, "hash", status="active", email_verified=True)


def test_token_wird_einmal_angelegt_und_bleibt(store):
    uid = _konto(store)
    assert store.calendar_token(uid, create=False) is None
    t1 = store.calendar_token(uid)
    assert t1 and len(t1) >= 24
    assert store.calendar_token(uid) == t1
    assert store.user_by_calendar_token(t1)["id"] == uid


def test_rotation_macht_altes_token_ungueltig(store):
    uid = _konto(store)
    alt = store.calendar_token(uid)
    neu = store.rotate_calendar_token(uid)
    assert neu != alt
    assert store.user_by_calendar_token(alt) is None
    assert store.user_by_calendar_token(neu)["id"] == uid
    assert store.user_by_calendar_token("") is None


def test_token_ist_je_konto_verschieden(store):
    a = store.calendar_token(_konto(store, "a@example.org"))
    b = store.calendar_token(_konto(store, "b@example.org"))
    assert a != b


# ---- Der Feed -----------------------------------------------------------------

def _council(tmp_path, heute: date) -> CouncilStore:
    c = CouncilStore(str(tmp_path / "council.sqlite"))
    from datetime import timedelta
    in_zwei = (heute + timedelta(days=2)).isoformat()
    vor_zehn = (heute - timedelta(days=10)).isoformat()
    vor_hundert = (heute - timedelta(days=100)).isoformat()
    with c._conn:
        c._conn.executemany(
            "INSERT INTO council_sessions (ksinr, committee, session_date, session_time, location, fetched_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            [
                (1, "Umweltausschuss", in_zwei, "17:00", "Rathaus, Raum 1", "2026-09-01T00:00:00"),
                (2, "Rat der Stadt Oldenburg", in_zwei, "18:00", "Ratssaal", "2026-09-01T00:00:00"),
                (3, "Sozialausschuss", vor_zehn, "", "PFL, Saal", "2026-09-01T00:00:00"),
                (4, "Sozialausschuss", vor_hundert, "16:00", "PFL", "2026-09-01T00:00:00"),
            ],
        )
        c._conn.executemany(
            "INSERT INTO council_agenda_items (ksinr, item_number, title, template_number, kvonr)"
            " VALUES (?, ?, ?, ?, ?)",
            [
                (1, "Ö 5", "Radweg Nadorster Straße; hier: Planung, Abschnitt 2", "26/0100", 100),
                (1, "Ö 6", "Mitteilungen", None, None),
                (2, "Ö 3", "Haushalt 2027", "26/0200", 200),
                (3, "Ö 2", "Kita-Gebühren", "26/0300", 300),
            ],
        )
        c._conn.execute(
            "INSERT INTO council_scheduled_sessions (committee, session_date, session_time, location, fetched_at)"
            " VALUES (?, ?, ?, ?, ?)",
            ("Kulturausschuss", (heute + timedelta(days=20)).isoformat(), "", "", "2026-09-01T00:00:00"),
        )
        c._conn.execute(
            "INSERT INTO council_decisions (ksinr, position, item_number, title, outcome)"
            " VALUES (?, ?, ?, ?, ?)",
            (3, 1, "Ö 2", "Kita-Gebühren", "accepted"),
        )
    return c


@pytest.fixture
def welt(tmp_path, store):
    heute = date(2026, 9, 5)
    council = _council(tmp_path, heute)
    uid = _konto(store)
    yield {"council": council, "store": store, "uid": uid, "heute": heute}
    council.close()


def _feed(w, **kw) -> str:
    user = {"id": w["uid"]}
    now = datetime(2026, 9, 5, 10, 0, tzinfo=timezone.utc)
    return build_feed(user=user, council=w["council"], ratslotse=w["store"],
                      base_url="https://ratslotse.de/", now=now, **kw)


def test_ohne_abos_kommt_alles_und_die_alte_sitzung_nicht(welt):
    text = _feed(welt)
    assert text.startswith("BEGIN:VCALENDAR\r\n")
    assert "\r\nX-WR-CALNAME:Ratslotse – Oldenburger Rat\r\n" in text
    assert "BEGIN:VTIMEZONE" in text
    assert "UID:sitzung-1@ratslotse.de" in text
    assert "UID:sitzung-2@ratslotse.de" in text
    assert "UID:sitzung-3@ratslotse.de" in text          # 10 Tage her: bleibt
    assert "UID:sitzung-4@ratslotse.de" not in text      # 100 Tage her: weg
    assert "UID:termin-kulturausschuss-2026-09-25@ratslotse.de" in text
    # Jede Zeile ≤ 75 Oktett, alle mit CRLF.
    for line in text.split("\r\n"):
        assert len(line.encode("utf-8")) <= 75, line
    assert "\n" not in text.replace("\r\n", "")


def test_zeit_ort_dauer_und_backlink(welt):
    text = _feed(welt).replace("\r\n ", "")
    assert "DTSTART;TZID=Europe/Berlin:20260907T170000" in text
    assert "DTEND;TZID=Europe/Berlin:20260907T200000" in text      # 3 h
    assert "DTEND;TZID=Europe/Berlin:20260907T220000" in text      # Rat: 4 h
    assert "LOCATION:Rathaus\\, Raum 1" in text
    assert "URL:https://ratslotse.de/council/sitzung?ksinr=1" in text
    assert "SUMMARY:Umwelt\r\n" in text
    assert "SUMMARY:Rat\r\n" in text
    # Ohne Uhrzeit: ganztägig.
    assert "DTSTART;VALUE=DATE:20260826" in text
    # Vergangen, mit Beschluss: der Termin sagt es.
    assert "1 Beschluss liegt vor" in text
    # Terminierte Sitzung ohne Tagesordnung.
    assert "STATUS:TENTATIVE" in text
    assert "Die Tagesordnung veröffentlicht das Ratsinfo" in text
    assert "Amtlicher Name: Rat der Stadt Oldenburg" in text


def test_abos_filtern_und_themen_treffer_kommen_trotzdem(welt):
    st, uid = welt["store"], welt["uid"]
    st.subscribe(uid, "Umweltausschuss")
    text = _feed(welt).replace("\r\n ", "")
    assert "UID:sitzung-1@ratslotse.de" in text
    assert "UID:sitzung-2@ratslotse.de" not in text
    assert "BEGIN:VALARM" not in text

    topic = st.add_topic(uid, "Kita", "Kita-Gebühren und Plätze")
    st.replace_agenda_matches(uid, 2, "hash", {topic.id: ["Ö 3"]})
    text = _feed(welt).replace("\r\n ", "")
    assert "UID:sitzung-2@ratslotse.de" in text
    assert "SUMMARY:Rat · dein Thema" in text
    assert "dein Thema: Kita" in text
    # Erinnerung am Vorabend, 18:00 Berlin = 16:00 UTC.
    assert "BEGIN:VALARM" in text
    assert "TRIGGER;VALUE=DATE-TIME:20260906T160000Z" in text
    assert "Morgen im Rat: Kita" in text
