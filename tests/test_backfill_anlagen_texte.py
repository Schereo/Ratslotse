"""Der Text-Backfill: Glyphenseiten erkennen (scripts/backfill_anlagen_texte.py).

Der Stellenplan 2026 (Anlage 297432) trägt Teil A mit Zeichenzuordnung und
Teil B ohne. Das Dokument als Ganzes hat 20 % Buchstaben und fiel durch kein
Netz — Teil B fehlte von 10/2025 bis 09/2026. Diese Tests halten die
Seiten-Entscheidung fest, ohne Netz und ohne Modell."""
from __future__ import annotations

from scripts.backfill_anlagen_texte import hat_glyphstrecke, seite_braucht_ocr

GLYPHEN = "/0 /1 /2 /3 /3 /2 /4 /5 /3 /6 /4 /7 /7 /8 /7 /7 /i255 /0 /1 " * 120
LESBAR = ("Stellenplan 00100 Stadt Oldenburg Teil A: Beamtinnen und Beamte "
          "1 Oberbürgermeister/-in B 8 1,00 1,00 1,00 0,00 0,00 ") * 40


def test_glyphenseite_erkannt():
    assert seite_braucht_ocr(GLYPHEN)
    assert not seite_braucht_ocr(LESBAR)


def test_kurze_seiten_gelten_nicht_als_glyphen():
    """Deckblatt („1524"), Trennblatt — zu wenig Text für ein Urteil."""
    assert not seite_braucht_ocr("1524")
    assert not seite_braucht_ocr("")


def test_vorpruefung_findet_die_glyphstrecke_im_gespeicherten_text():
    """Teil A lesbar, Teil B Glyphen, Übersicht lesbar — die Vorprüfung sieht
    die Strecke, obwohl das Ganze über der Dokument-Schwelle liegt."""
    text = LESBAR + GLYPHEN + LESBAR
    assert hat_glyphstrecke(text)
    assert not hat_glyphstrecke(LESBAR * 3)
