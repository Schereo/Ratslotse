"""Der Vorbericht des Haushaltsplans (council/vorbericht.py).

Fixtures: die Textblöcke echter Seiten — Inhaltsverzeichnis und die Abschnitte
zu Teilhaushalt 06 aus dem Vorbericht 2026 (Dokument 297437, Kapitelnummer vor
der Überschrift) und 2019 (194277, Kapitelnummer dahinter). Die übrigen Seiten
sind leer, deshalb meldet die Vollständigkeitsprobe die fehlenden Abschnitte —
genau das soll sie."""
from __future__ import annotations

import json
from pathlib import Path

from council import vorbericht as v

FX = json.loads((Path(__file__).parent / "fixtures" / "vorbericht_bloecke.json").read_text())


def _abschnitt(l, kind, thh):
    return next(a for a in l.abschnitte if a.kind == kind and a.sub_budget_no == thh)


def test_2026_wortlaut_ohne_grafik():
    l = v.lies(FX["2026"])
    assert l.budget_year == 2026
    a = _abschnitt(l, "result", 6)
    assert a.title == "Kultur, Museen, Sport"
    assert a.text.startswith("Der Teilhaushalt 06 bildet die Musikschule")
    assert "10.426.258 Euro" in a.text
    # Die Diagrammbeschriftungen („Ordentliche Erträge", Zahlenreihen) fliegen raus.
    assert "Ordentliche Erträge\n" not in a.text and "34,37" not in a.text
    assert "(Grafik" not in a.text


def test_absatz_ueber_den_seitenumbruch():
    i = _abschnitt(v.lies(FX["2026"]), "investments", 6)
    assert "Sporthalle am Osternburger Markt" in i.text


def test_2019_kapitel_aus_der_reihenfolge():
    l = v.lies(FX["2019"])
    assert l.budget_year == 2019
    assert _abschnitt(l, "result", 6).text.startswith("Der Teilhaushalt 06")
    # Das Inhaltsverzeichnis nennt 26 Abschnitte; die leeren Seiten fehlen.
    assert len(l.im_inhalt) == 26
    assert not l.bestanden and "ohne Abschnitt" in l.hinweise[0]


def test_ist_absatz():
    assert not v._ist_absatz("2,48\n1,66\n1,88")
    assert not v._ist_absatz("Ordentliche Aufwendungen")
    assert not v._ist_absatz("2024 Ist, ab 2025 Plan (Grafik 26)")
    assert v._ist_absatz("Die Personalaufwendungen steigen um rund 1,0 Millionen Euro.")
