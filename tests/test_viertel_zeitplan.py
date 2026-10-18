"""„Mein Viertel": abgelaufene Zeiträume (council/viertel_zeitplan.py).

Die Formulierungen stammen aus dem Register (Prod-Abzug 01.10.2026) — genau
so schreibt sie der Richter in ``when_text``. Wer den Parser anfasst, hält ihn
gegen diese Liste.
"""
from __future__ import annotations

from datetime import date

import pytest

from council.viertel_zeitplan import schedule_state, zeitraum_ende

HEUTE = date(2026, 10, 3)


@pytest.mark.parametrize("text, ende", [
    # Die vier abgelaufenen Highlights vom 03.10.2026:
    ("bis 31. Januar 2026", date(2026, 1, 31)),          # Skateanlage Eversten
    ("4. Quartal 2025", date(2025, 12, 31)),             # IGS-Sporthalle Kreyenbrück
    ("2024–2025", date(2025, 12, 31)),                   # Sandweg
    ("Ende 2025", date(2025, 12, 31)),                   # Mädchenhaus Ehnernstraße
    # Jahre, Spannen, Quartale
    ("2026", date(2026, 12, 31)),
    ("2025–2026", date(2026, 12, 31)),
    ("2027–2030", date(2030, 12, 31)),
    ("2025 (Entwurf veröffentlicht)", date(2025, 12, 31)),
    ("bis 2036", date(2036, 12, 31)),
    ("bis Ende 2032", date(2032, 12, 31)),
    ("Ende 2024", date(2024, 12, 31)),
    ("3. Quartal 2026", date(2026, 9, 30)),
    ("erstes Quartal 2026", date(2026, 3, 31)),
    ("im vierten Quartal 2025", date(2025, 12, 31)),
    ("von 2025 bis 2027", date(2027, 12, 31)),
    # Monate und Tage
    ("Ende September 2025", date(2025, 9, 30)),
    ("Juni 2025", date(2025, 6, 30)),
    ("Dezember 2026", date(2026, 12, 31)),
    ("April 2027", date(2027, 4, 30)),
    ("6. Juni 2026", date(2026, 6, 6)),
    ("18. September 2025", date(2025, 9, 18)),
    ("bis 12. September 2027", date(2027, 9, 12)),
    ("bis 31.03.2025", date(2025, 3, 31)),
    ("bis 12.09.2027", date(2027, 9, 12)),
    ("bis 30. Dezember 2030", date(2030, 12, 30)),
    ("vor September 2026", date(2026, 9, 30)),
    ("Mitte Juni 2025 bis Januar 2026", date(2026, 1, 31)),
    # Ungefähres: im Zweifel das spätere Ende
    ("Sommer 2026", date(2026, 9, 30)),
    ("Mitte 2025", date(2025, 8, 31)),
    ("Anfang 2026", date(2026, 4, 30)),
    ("Frühjahr 2027", date(2027, 5, 31)),
    ("Herbst 2026", date(2026, 11, 30)),
    ("zweites Halbjahr 2026", date(2026, 12, 31)),
    ("1. Halbjahr 2026", date(2026, 6, 30)),
    # Schul- und Kita-Jahre enden am 31. Juli ihres zweiten Jahres
    ("Schuljahr 2025/2026", date(2026, 7, 31)),
    ("Schuljahr 2029/2030", date(2030, 7, 31)),
    ("Kindergartenjahr 2026/2027", date(2027, 7, 31)),
    ("Kita-Jahr 2026/2027", date(2027, 7, 31)),
    ("Schuljahr 2025/26", date(2026, 7, 31)),
    ("Sommer 2026; Schuljahr 2029/2030", date(2030, 7, 31)),
    # Beginn und Ende gemischt: das Ende zählt
    ("voraussichtlich ab September 2025, bis 31. Juli 2063", date(2063, 7, 31)),
    ("ab Mai 2025; Vermarktung der Wohnbaugrundstücke 2026", date(2026, 12, 31)),
    ("bis Ende 2026 (Grundstücksübertragungen)", date(2026, 12, 31)),
])
def test_zeitraum_ende(text, ende):
    assert zeitraum_ende(text) == ende


@pytest.mark.parametrize("text", [
    None, "", "zwei Jahre", "in den nächsten Kita-Jahren",
    # Nur ein Beginn: sagt nichts darüber, ob etwas vorbei ist.
    "ab März 2026", "ab September 2025", "ab 01.08.2026", "ab Herbst 2026", "ab Dezember 2025", "ab 2026",
    "ab Schuljahr 2025/2026; Ausbau ab Schuljahr 2027", "seit 2020", "Baubeginn 2026",
])
def test_kein_ende(text):
    assert zeitraum_ende(text) is None


def test_im_bau_und_zeitraum_vorbei_heisst_vermutlich_abgeschlossen():
    s = schedule_state("building", "bis 31. Januar 2026", "2025-03-01", HEUTE)
    assert s["schedule"] == "likely_done"
    assert "bis 31. Januar 2026" in s["schedule_note"]
    assert s["when_end"] == "2026-01-31"


@pytest.mark.parametrize("stage", ["idea", "planning", "decided"])
def test_planung_und_zeitraum_vorbei_heisst_ueberschritten(stage):
    s = schedule_state(stage, "Ende 2025", "2025-06-01", HEUTE)
    assert s["schedule"] == "overdue"
    assert "Zeitplan überschritten" in s["schedule_note"]


def test_zeitraum_laeuft_noch():
    assert schedule_state("building", "Kindergartenjahr 2026/2027", "2025-11-19", HEUTE)["schedule"] is None
    # Ein Ende, das heute ist, ist noch nicht vorbei.
    assert schedule_state("building", "3. Oktober 2026", "2025-01-01", HEUTE)["schedule"] is None


def test_ohne_ende_und_lange_still_ist_quiet():
    s = schedule_state("building", None, "2025-08-27", HEUTE)
    assert s["schedule"] == "quiet"
    assert "August 2025" in s["schedule_note"]
    # Elf Monate sind noch frisch genug.
    assert schedule_state("planning", None, "2025-11-04", HEUTE)["schedule"] is None
    # Ein Beginn ist kein Ende — still bleibt still.
    assert schedule_state("decided", "ab März 2024", "2024-03-01", HEUTE)["schedule"] == "quiet"


def test_ende_in_der_zukunft_ist_nie_still():
    # Ein Plan bis 2030 mit einem Beschluss von 2024 ist langfristig, nicht veraltet.
    assert schedule_state("planning", "2027–2030", "2024-02-01", HEUTE)["schedule"] is None


@pytest.mark.parametrize("stage", ["done", "rejected", None])
def test_fertig_und_abgelehnt_bekommen_keinen_zustand(stage):
    s = schedule_state(stage, "Ende 2024", "2023-01-01", HEUTE)
    assert s["schedule"] is None and s["schedule_note"] is None
