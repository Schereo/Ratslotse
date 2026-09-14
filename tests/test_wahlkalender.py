"""Welche Wahl zeigt eine Seite gerade — und woher sie ihre Texte nimmt.

Zwei Fragen, ein Ort: ``election.elections``. Bis 09/2026 beantwortete das
Frontend beide selbst — mit ``WAHLABEND_BEGINN_UTC`` als Konstante und mit
„Ratswahl Oldenburg · 13. September 2026" an acht Stellen als Literal.

Der Fokus (``focus``) ist absichtlich HIER und nicht in einer Seite: Ihn
brauchen ``/api/app-config`` (Countdown auf Startseite und Heute-Karte) und
später die Übersicht unter ``/wahlen``. Zwei Fassungen liefen unweigerlich
auseinander — dieselbe Begründung wie bei ``jobs.zustand``.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL / "web" / "backend"))

from app.election import elections, service  # noqa: E402


def _zeit(text: str) -> datetime:
    return datetime.fromisoformat(text).replace(tzinfo=timezone.utc)


@pytest.mark.parametrize("wann,erwartet,pfad", [
    # Lange vor allem: die nächste anstehende Wahl.
    ("2026-08-01T09:00", "ratswahl-2026", "/wahlabend"),
    # Zwei Tage vorher beginnt das Fenster.
    ("2026-09-11T09:00", "ratswahl-2026", "/wahlabend"),
    # Am Abend selbst — und zwar die RATSWAHL, nicht die OB-Wahl desselben
    # Tages: Sie ist die, nach der Leute suchen.
    ("2026-09-13T19:00", "ratswahl-2026", "/wahlabend"),
    # Drei Tage danach ist noch Nachlesezeit.
    ("2026-09-16T09:00", "ratswahl-2026", "/wahlabend"),
    # Danach zeigt alles auf die Stichwahl.
    ("2026-09-17T09:00", "ob-stichwahl-2026", "/wahlabend/stichwahl"),
    ("2026-09-25T09:00", "ob-stichwahl-2026", "/wahlabend/stichwahl"),
    ("2026-09-27T19:00", "ob-stichwahl-2026", "/wahlabend/stichwahl"),
    ("2026-09-30T09:00", "ob-stichwahl-2026", "/wahlabend/stichwahl"),
    # Ist alles vorbei, bleibt die zuletzt gelaufene Ratswahl stehen.
    ("2026-10-05T09:00", "ratswahl-2026", "/wahlabend"),
])
def test_fokus_ueber_den_kalender(wann: str, erwartet: str, pfad: str):
    wahl = elections.focus(_zeit(wann))
    assert wahl.slug == erwartet, f"{wann}: erwartet {erwartet}, bekommen {wahl.slug}"
    assert elections.path_of(wahl) == pfad


def test_fokus_haengt_nicht_an_der_reihenfolge():
    """Zweimal gefragt, zweimal dasselbe — sonst hinge die Antwort am
    Dateisystem."""
    t = _zeit("2026-09-20T09:00")
    assert elections.focus(t).slug == elections.focus(t).slug


def test_entwuerfe_kommen_nie_in_den_fokus():
    for wahl in elections.all().values():
        assert wahl.status != "entwurf" or elections.focus(_zeit("2026-09-20T09:00")).slug != wahl.slug


def test_der_notausgang_steuert_auch_den_fokus(monkeypatch):
    """``WAHLABEND_ELECTION`` schaltet die GANZE Seite um.

    Ohne diese Zeile zeigte /api/wahlabend die gewählte Wahl und der
    Countdown auf der Startseite weiter die aus dem Kalender — beim ersten
    Einsatz am Wahlabend genau die Verwirrung, gegen die der Notausgang
    gebaut ist."""
    monkeypatch.setenv("WAHLABEND_ELECTION", "ob-stichwahl-2026")
    assert elections.focus(_zeit("2026-09-13T19:00")).slug == "ob-stichwahl-2026"
    monkeypatch.setenv("WAHLABEND_ELECTION", "gibtsnicht")
    assert elections.focus(_zeit("2026-09-13T19:00")).slug == "ratswahl-2026"


def test_datum_und_wahlschluss_stammen_aus_derselben_quelle():
    """Sie kamen kurz aus zwei Quellen — Datum aus dem Register, Wahlschluss
    aus der Registry. Zwei richtige Quellen, eine falsche Antwort."""
    w = service.probe(0)["election"]
    assert w["polls_close"].startswith(w["date"]), (
        f"„{w['date']}“ und „{w['polls_close']}“ meinen verschiedene Tage")


def test_die_antwort_traegt_die_identitaet_der_wahl():
    """Alles, was im Frontend als Überschrift steht, muss von hier kommen."""
    daten = service.probe(0)
    w = daten["election"]
    assert set(w) >= {"slug", "date", "seats", "title", "short_title", "polls_close",
                      "status", "presentation_url", "previous_label"}
    aktiv = elections.active()
    assert w["slug"] == aktiv.slug
    assert w["short_title"] == aktiv.short_title
    assert w["polls_close"] == aktiv.polls_close.isoformat()
    assert w["status"] == aktiv.status


def test_eine_andere_wahl_aendert_die_antwort(monkeypatch):
    """Die Abnahme aus dem Plan: Ein Wechsel in der ``.env`` ändert Titel,
    Termin und Sitzzahl — ohne Deploy, ohne Codeänderung.

    Geprüft wird gegen eine zweite Ratswahl, die es im Baum gar nicht gibt;
    sie entsteht für diesen Test und verschwindet mit ihm.
    """
    import json
    from app.election import register

    ordner = WURZEL / "kommunalwahl" / "wahlen"
    vorlage = json.loads((ordner / "ratswahl-2026.json").read_text(encoding="utf-8"))
    zweite = {**vorlage, "slug": "ratswahl-2031", "date": "2031-09-14",
              "polls_close": "2031-09-14T18:00:00+02:00", "seats": 54,
              "short_title": "Ratswahl Oldenburg", "reference": "kommunalwahl/referenz-2026",
              "previous_label": "2026"}
    datei = ordner / "ratswahl-2031.json"
    datei.write_text(json.dumps(zweite, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("WAHLABEND_ELECTION", "ratswahl-2031")
    elections.reset()
    register.reset()
    try:
        wahl = elections.active()
        assert wahl.slug == "ratswahl-2031"
        assert wahl.seats == 54 and wahl.previous_label == "2026"
        assert wahl.reference_folder is not None and wahl.reference_folder.name == "referenz-2026"
        assert elections.focus(_zeit("2031-09-14T19:00")).slug == "ratswahl-2031"
    finally:
        datei.unlink()
        elections.reset()
        register.reset()
