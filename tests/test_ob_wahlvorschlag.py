"""Der Name über einer OB-Kandidatur ist der WAHLVORSCHLAG, nicht das Parteibuch.

Tims Hinweis am 14.09.2026 vor der Stichwahl: „Jascha Rohr tritt zwar
offiziell für die Grünen an, steht also als Grüner auf dem Wahlzettel, betont
aber immer, dass er parteilos ist. Er tritt für die Grünen an, weil er von
Grünen und CDU unterstützt wird, man aber nur für eine Partei auf dem
Wahlzettel stehen kann."

Die Unterscheidung ist keine Feinheit: Auf dem Stimmzettel ist je Kandidatur
genau eine Liste zugelassen, und die Seite schrieb deren Kurznamen bisher
kommentarlos über den Namen. Wer das liest, liest ein Parteibuch.

**Die beiden Zusatzangaben stehen NICHT in der amtlichen Bekanntmachung**
(``kommunalwahl/wahl-fakten.json`` → ``quelle``), aus der alles andere
stammt. Sie brauchen deshalb ihre eigene Quelle, und ohne die zeigt das
Backend sie gar nicht — der letzte Test hält genau das fest.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL / "web" / "backend"))

from app.election import mayor  # noqa: E402

FAKTEN = WURZEL / "kommunalwahl" / "wahl-fakten.json"


def _roh() -> list[dict]:
    return json.loads(FAKTEN.read_text(encoding="utf-8"))["ob_kandidaten"]


def test_jede_kandidatur_nennt_ihren_wahlvorschlag_voll_und_kurz():
    for c in mayor.candidates():
        assert c.nominated_by, c.slug
        # Die Kurzform ist die Klammer des amtlichen Namens („… (GRÜNE)") —
        # oder „Einzelwahlvorschlag", der keine Partei ist.
        assert c.party, c.slug
        if c.party != "Einzelwahlvorschlag":
            assert c.party in c.nominated_by, (c.slug, c.party, c.nominated_by)


def test_rohr_steht_als_gruener_auf_dem_zettel_und_ist_parteilos():
    rohr = next(c for c in mayor.candidates() if c.slug == "rohr")
    # Was auf dem Stimmzettel steht — aus der amtlichen Bekanntmachung.
    assert rohr.party == "GRÜNE"
    assert rohr.nominated_by == "BÜNDNIS 90/DIE GRÜNEN (GRÜNE)"
    # Und was daneben gehört, damit daraus kein Parteibuch wird.
    assert rohr.independent is True
    assert rohr.supported_by == ("CDU",)
    assert rohr.note_source.startswith("https://")


def test_wer_nichts_dazu_gemeldet_hat_bekommt_auch_nichts_angedichtet():
    """``independent=False`` heißt „uns liegt nichts Belegtes vor", nicht
    „Mitglied". Deshalb steht bei allen anderen schlicht nichts."""
    for c in mayor.candidates():
        if c.slug == "rohr":
            continue
        assert c.independent is False and c.supported_by == () and c.note_source == "", c.slug


def test_ohne_quelle_keine_aussage(tmp_path, monkeypatch):
    """Die Probe aufs Exempel: Wer die Angabe ohne Beleg in die Datei
    schreibt, bekommt sie nicht ausgeliefert."""
    from app.election import elections

    daten = json.loads(FAKTEN.read_text(encoding="utf-8"))
    for k in daten["ob_kandidaten"]:
        k.pop("hinweis_quelle", None)
        if k["name"] == "Jascha Rohr":
            k["parteilos"] = True
            k["unterstuetzt_von"] = ["CDU"]
    datei = tmp_path / "wahl-fakten.json"
    datei.write_text(json.dumps(daten, ensure_ascii=False), encoding="utf-8")

    wahl = elections.get("ob-stichwahl-2026")
    assert wahl is not None
    ohne = mayor.candidates(_mit_datei(wahl, datei))
    rohr = next(c for c in ohne if c.slug == "rohr")
    assert rohr.independent is False and rohr.supported_by == () and rohr.note_source == ""
    # Der Wahlvorschlag selbst bleibt natürlich stehen — der IST amtlich.
    assert rohr.party == "GRÜNE"


def _mit_datei(wahl, datei: Path):
    """Dieselbe Wahl, aber mit einer anderen Fakten-Datei."""
    import dataclasses

    _, schluessel, nur = wahl.candidates
    return dataclasses.replace(wahl, candidates=(datei, schluessel, nur))


def test_die_datei_sagt_selbst_woher_die_zusatzangaben_stammen():
    """Der Dateikopf verspricht „alles aus der amtlichen Quelle". Seit es
    Angaben gibt, die dort NICHT stehen, muss er das sagen — sonst führt der
    Beleg-Apparat in die Irre."""
    quelle = json.loads(FAKTEN.read_text(encoding="utf-8"))["quelle"]
    assert "hinweis_quelle" in quelle["hinweis"]
    mit_zusatz = [k for k in _roh() if k.get("parteilos") or k.get("unterstuetzt_von")]
    assert mit_zusatz, "Testannahme: mindestens eine Kandidatur trägt eine Zusatzangabe"
    for k in mit_zusatz:
        assert k.get("hinweis_quelle", "").startswith("https://"), k["name"]
