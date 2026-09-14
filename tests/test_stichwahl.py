"""Die Stichwahl am 27.09.2026 — eine zweite Wahl unter demselben Termin.

Zwei Dinge machen sie schwierig, und beide prüft diese Datei:

1. **Ihre Wahl-Id gibt es noch nicht.** Gemessen am 14.09.2026 kennt
   ``termin.json`` nur 913 (Ratswahl) und 2552 (OB-Wahl). Die Stichwahl-Id
   vergibt die Stadt erst; sie zu raten wäre die Sorte Fehler, die am
   Wahlabend auffällt. Deshalb sucht ``mayor.resolve_ids`` den Eintrag am
   TITEL, und die Seite wartet, bis es ihn gibt.
2. **Sie darf den ersten Wahlgang nicht verdrängen.** Das Tippspiel vergleicht
   die getippten OB-Prozente gegen den 13.09.; würde ``mayor.fetch()`` am
   27.09. plötzlich die Stichwahl liefern, verschöben sich rückwirkend alle
   Punkte.

Dass eine Stichwahl unter dem Termin der HAUPTWAHL läuft (und nicht unter
einem eigenen), ist an den Terminlisten der Stadt gemessen — 2006 und 2021
beide unter der URL des Kommunalwahltermins.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL / "web" / "backend"))

from app.election import elections, mayor  # noqa: E402

REFERENZ = WURZEL / "kommunalwahl" / "referenz-2026"


@pytest.fixture(autouse=True)
def _sauber():
    mayor.reset()
    yield
    mayor.reset()


def test_die_stichwahl_steht_in_der_registry():
    w = elections.runoff()
    assert w is not None, "Ohne Eintrag in kommunalwahl/wahlen/ gibt es die Seite gar nicht."
    assert w.kind == "mayor" and w.date == "2026-09-27"
    assert w.first_round == "ob-2026"
    assert elections.get(w.first_round) is not None


def test_wahl_id_wird_gesucht_nicht_geraten():
    """Sie ist am 14.09.2026 noch nicht vergeben — eine Konstante wäre geraten."""
    w = elections.runoff()
    assert w is not None
    assert w.source.presentation_id is None
    assert (w.source.discover or {}).get("title_contains") == "Stichwahl"


def test_die_beiden_sind_die_aus_dem_ersten_wahlgang():
    """Gegenprobe gegen die eingefrorene Ergebnisdarstellung vom 13.09.:
    Der Votemanager nennt dort selbst, wer in die Stichwahl kommt."""
    w = elections.runoff()
    assert w is not None
    unsere = {c.slug for c in mayor.candidates(w)}
    assert len(unsere) == 2

    payload = json.loads((REFERENZ / "praesentation-ob.json").read_text(encoding="utf-8"))
    erster = mayor.parse(payload, mayor.candidates(elections.get("ob-2026")))
    assert erster is not None
    assert set(erster.runoff) == unsere, (
        "Die Registry nennt andere Namen als die Ergebnisdarstellung des ersten Wahlgangs.")


def test_ein_unbekannter_slug_in_only_ist_ein_fehler(tmp_path, monkeypatch):
    """Eine Stichwahl mit einer statt zwei Personen wäre keine — also lieber
    laut scheitern als still eine Karte weglassen."""
    quelle = json.loads((WURZEL / "kommunalwahl" / "wahlen" / "ob-stichwahl-2026.json").read_text(encoding="utf-8"))
    quelle["candidates"]["only"] = ["prange", "gibtsnicht"]
    ordner = tmp_path / "wahlen"
    ordner.mkdir()
    for datei in (WURZEL / "kommunalwahl" / "wahlen").glob("*.json"):
        (ordner / datei.name).write_text(datei.read_text(encoding="utf-8"), encoding="utf-8")
    (ordner / "ob-stichwahl-2026.json").write_text(json.dumps(quelle, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(elections, "WAHLEN", ordner)
    elections.reset()
    try:
        with pytest.raises(LookupError, match="gibtsnicht"):
            mayor.candidates(elections.runoff())
    finally:
        elections.reset()


def test_eintrag_wird_am_titel_gefunden():
    """Der Fall vom 27.09.: In ``termin.json`` steht plötzlich eine dritte Wahl."""
    w = elections.runoff()
    assert w is not None
    payload = {"wahleintraege": [
        {"wahl": {"id": 913, "titel": "Stadtratswahl - Stadt Oldenburg"},
         "gebiet_link": {"id": "ebene_-6361_id_10358"}},
        {"wahl": {"id": 2552, "titel": "Wahl der Oberbürgermeisterin / Wahl des Oberbürgermeisters - Stadt Oldenburg"},
         "gebiet_link": {"id": "ebene_-6360_id_10357"}},
        {"wahl": {"id": 2611, "titel": "Stichwahl des/der Oberbürgermeisters/in - Stadt Oldenburg"},
         "gebiet_link": {"id": "ebene_-6360_id_10999"}},
    ]}
    assert mayor._eintrag(payload, w.source) == (2611, "ebene_-6360_id_10999")


def test_ohne_eintrag_wird_nichts_erfunden():
    """Der Stand von heute: Die Stichwahl steht noch nicht drin."""
    w = elections.runoff()
    assert w is not None
    heute = json.loads((REFERENZ / "termin.json").read_text(encoding="utf-8"))
    assert mayor._eintrag(heute, w.source) is None


def test_die_ratswahl_zieht_weiter_ihre_eigene_id():
    """Die Suche am Titel gilt nur für Wahlen mit ``discover``; eine Wahl mit
    fester Id nimmt ihre, auch wenn ein Titel passen würde."""
    ob = elections.get("ob-2026")
    assert ob is not None
    heute = json.loads((REFERENZ / "termin.json").read_text(encoding="utf-8"))
    assert mayor._eintrag(heute, ob.source) == (2552, "ebene_-6360_id_10357")


def test_der_erste_wahlgang_bleibt_der_vergleich_des_tippspiels():
    """``mayor.wahl()`` ohne Argument ist der 13.09. — daran hängen die Punkte."""
    assert mayor.wahl().slug == "ob-2026"
    assert len(mayor.candidates()) == 9


def test_generalprobe_rechnet_den_ersten_wahlgang_auf_zwei_um():
    w = elections.runoff()
    assert w is not None
    voll = mayor.probe(133, w)
    assert [c.slug for c in voll.candidates] == [c.slug for c in mayor.candidates(w)]
    assert abs(sum(c.share_pct or 0 for c in voll.candidates) - 100) < 0.05
    assert voll.valid_votes == sum(c.votes or 0 for c in voll.candidates)
    assert voll.notes == (), (
        "Die sieben Ausgeschiedenen dürfen keine „passt zu keiner Kandidatur“-Hinweise erzeugen — "
        "live ist das ein Alarm, hier wäre es Rauschen.")
    assert voll.runoff == (), "Eine Stichwahl führt nicht zu einer weiteren Stichwahl."

    halb = mayor.probe(62, w)
    assert halb.phase == "counting" and halb.reports_received == 62
    assert all((c.votes or 0) < (v.votes or 0) for c, v in zip(halb.candidates, voll.candidates, strict=True))


def test_der_erste_wahlgang_probt_weiter_mit_2021():
    """Seine Probe ist die OB-Wahl 2021 — nicht er selbst."""
    stand = mayor.probe(133, elections.get("ob-2026"))
    assert stand.phase == "complete"
    assert len(stand.candidates) > 2


# ------------------------------------------------------------------ Wer steht in der Stichwahl?

@pytest.mark.parametrize("label,erwartet", [
    ("Ulf Prange (SPD)", "prange"),               # Form 2026: Vorname zuerst
    ("Krogmann, Jürgen (SPD)", "krogmann"),       # Form 2021: Nachname, Komma
    ("Fuhrhop, Daniel (GRÜNE)", "fuhrhop"),
    ("Jascha Rohr (GRÜNE)", "rohr"),
    ("Byanca Küßner", "kuessner"),                # ganz ohne Partei
    # Mehrteilige Nachnamen kürzt ``slug_of`` seit jeher auf das letzte Wort —
    # und zwar in BEIDEN Formen gleich, das ist hier der Punkt.
    ("von der Heide, Anna (CDU)", "heide"),
    ("Anna von der Heide (CDU)", "heide"),
])
def test_nachname_aus_beiden_schreibweisen(label: str, erwartet: str):
    """Die Ergebnisdarstellung schreibt Namen in zwei Formen.

    Bis 09/2026 wurde nur bis zum ersten Komma geschnitten — bei „Ulf Prange
    (SPD)" kam dadurch „(SPD)" heraus und daraus der Slug „spd". Prod
    antwortete am 14.09.2026 mit ``runoff: ["spd", "gruene"]``.
    """
    assert mayor.slug_of(mayor._nachname(label)) == erwartet


def test_runoff_nennt_die_beiden_menschen_nicht_ihre_parteien():
    payload = json.loads((REFERENZ / "praesentation-ob.json").read_text(encoding="utf-8"))
    stand = mayor.parse(payload, mayor.candidates(elections.get("ob-2026")))
    assert stand is not None
    assert set(stand.runoff) == {"prange", "rohr"}
