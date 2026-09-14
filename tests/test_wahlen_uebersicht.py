"""Die Übersicht unter ``/wahlen`` — und der Rückblick ohne Netz.

Zwei Zusagen stehen hier:

1. **Ein Rückblick braucht den Votemanager nicht.** Seine Adressen tragen den
   Wahltag im Pfad (``/20260913/…``) und wandern irgendwann ins Archiv. Die
   Zahlen liegen deshalb im Repo (``scripts/wahl_einfrieren.py``), und
   ``archive.night`` rechnet sie mit demselben Code nach, der am Wahlabend
   lief. Der Test dafür fasst kein Netz an — er kann es gar nicht.
2. **Eine Wahl ohne eigenes Register bekommt keine Seite.** Von der Ratswahl
   2021 gibt es die Zahlen, aber nicht die Kandidatenlisten. Mit dem Register
   von heute gerechnet kämen 52 Sitze auf 16 Listen heraus statt 50 auf elf:
   richtige Zahlen unter falschen Namen. Sie steht in der Übersicht mit ihrem
   Ergebnis und ohne Link.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL / "web" / "backend"))

from app.election import archive, elections  # noqa: E402
from app.routers import wahlabend as router  # noqa: E402


@pytest.fixture(autouse=True)
def _frei(monkeypatch):
    monkeypatch.setenv("FEATURE_FLAGS", "wahlabend")
    archive.reset()
    yield
    archive.reset()


def _zeilen():
    return {z["slug"]: z for z in router.wahlen()["elections"]}


def test_die_uebersicht_zeigt_alle_vier_wahlen():
    zeilen = _zeilen()
    assert set(zeilen) == {"ratswahl-2026", "ob-2026", "ob-stichwahl-2026", "ratswahl-2021"}
    # Neueste zuerst — die Übersicht wächst nach unten.
    daten = [z["date"] for z in router.wahlen()["elections"]]
    assert daten == sorted(daten, reverse=True)


def test_genau_eine_zeile_ist_im_fokus():
    zeilen = router.wahlen()["elections"]
    assert sum(1 for z in zeilen if z["focus"]) == 1
    fokus = next(z for z in zeilen if z["focus"])
    assert fokus["slug"] == elections.focus().slug


def test_jede_zeile_sagt_ihr_ergebnis_in_einem_satz():
    zeilen = _zeilen()
    assert zeilen["ratswahl-2026"]["summary"] == "Grüne 13, SPD 12, CDU 7, Linke 7 — 52 Sitze"
    assert zeilen["ratswahl-2021"]["summary"] == "GRÜNE 16, SPD 15, CDU 9, DIE LINKE. 4 — 50 Sitze"
    assert zeilen["ob-2026"]["summary"] == "Ulf Prange 33,2 % · Stichwahl"
    # Die Stichwahl hat noch keine Zahlen — und behauptet auch keine.
    assert zeilen["ob-stichwahl-2026"]["summary"] is None


def test_eine_wahl_ohne_register_bekommt_keinen_link():
    zeilen = _zeilen()
    assert zeilen["ratswahl-2021"]["path"] == "", (
        "Ein Link auf eine Seite, die es nicht gibt, ist schlechter als kein Link.")
    assert zeilen["ratswahl-2026"]["path"] == "/wahlabend"
    assert zeilen["ob-stichwahl-2026"]["path"] == "/wahlabend/stichwahl"


# ------------------------------------------------------------------ Rückblick

def test_der_rueckblick_rechnet_dasselbe_wie_der_wahlabend():
    """52 Mandate aus dem Repo — ohne einen einzigen Abruf."""
    bild = archive.night("ratswahl-2026")
    assert bild is not None
    assert bild["dataset"] == "archive" and bild["phase"] == "complete"
    assert bild["progress"]["districts_counted"] == bild["progress"]["districts_total"] == 133
    assert sum(p["seats"] or 0 for p in bild["parties"]) == 52
    assert len(bild["mandates"]) == 52
    assert all(m["name"] for m in bild["mandates"])

    # Gegenprobe gegen die Meta-Datei, die scripts/wahl_einfrieren.py beim
    # Einfrieren gegen den Votemanager gehalten hat.
    import json

    from app.election import reference

    ordner = WURZEL / "kommunalwahl" / "referenz-2026"
    meta = json.loads((ordner / "ratswahl-2026.json").read_text(encoding="utf-8"))
    gerechnet = {p["slug"]: p["seats"] for p in bild["parties"] if p["seats"]}
    assert gerechnet == meta["sitze_votemanager"]
    reference.reset()


def test_ein_rueckblick_ohne_register_wird_abgelehnt():
    assert archive.night("ratswahl-2021") is None
    assert not archive.verfuegbar(elections.get("ratswahl-2021"))


def test_ein_unbekannter_slug_ergibt_nichts():
    assert archive.night("gibtsnicht") is None


def test_der_endpunkt_liefert_den_rueckblick_und_sonst_404():
    bild = router.wahlabend(probe=None, counted=None, wahl="ratswahl-2026")
    assert bild["dataset"] == "archive"
    with pytest.raises(Exception) as fehler:
        router.wahlabend(probe=None, counted=None, wahl="ratswahl-2021")
    assert getattr(fehler.value, "status_code", None) == 404


def test_alles_haengt_am_schalter(monkeypatch):
    monkeypatch.delenv("FEATURE_FLAGS", raising=False)
    for aufruf in (lambda: router.wahlen(),
                   lambda: router.wahlabend(probe=None, counted=None, wahl="ratswahl-2026")):
        with pytest.raises(Exception) as fehler:
            aufruf()
        assert getattr(fehler.value, "status_code", None) == 404
