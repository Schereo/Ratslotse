"""Änderungsanträge lesen (council/motions.py) — ohne Netz, Modell gemockt."""
from __future__ import annotations

from council import motions

GO = ("Inhalt\n§ 24\nEinberufung und Ladung\n§ 25\nÖffentlichkeit\n\n"
      "§ 24\nEinberufung und Ladung\n \n(1)\nDer Verwaltungsausschuss wird nach Bedarf einberufen.\n \n"
      "(2) \nDie Ladungsfrist beträgt zwei Tage. In dringenden Fällen kann sie auf sechs Stunden\n"
      "abgekürzt werden.\n \n(3) \nDie Tagesordnung stellt die Oberbürgermeisterin auf.\n \n§ 25\nÖffentlichkeit\n(1)\nText")
VOLT = ("Volt-Fraktion\nÄnderungsantrag zur konstituierenden Ratssitzung\n"
        "§ 24 Absatz 2 der Geschäftsordnung für den Rat wird wie folgt neu gefasst:\n(2)\n"
        "Die Ladungsfrist beträgt eine Woche. In dringenden Fällen kann sie auf sechs\nStunden abgekürzt werden.\n"
        "Begründung\nDie bisherige Frist von zwei Tagen erschwert die Vorbereitung.")


def test_paragrafenanker_findet_den_absatz_hinter_dem_inhaltsverzeichnis():
    assert motions.paragraph_refs("§ 24 Absatz 2 und § 18 (4) sowie § 18 Abs. 4") == [("24", "2"), ("18", "4")]
    t = motions.paragraph_text(GO, "24", "2")
    assert t.startswith("Die Ladungsfrist beträgt zwei Tage") and "Tagesordnung" not in t


def test_wortdiff_zeigt_nur_die_aenderung():
    alt = motions.paragraph_text(GO, "24", "2")
    neu = motions.neufassung(VOLT, "Die Ladungsfrist beträgt eine Woche.")
    assert neu.startswith("Die Ladungsfrist beträgt eine Woche") and "Begründung" not in neu
    assert [d for d in motions.word_diff(alt, neu) if d[0] != "="] == [["-", "zwei Tage."], ["+", "eine Woche."]]


def test_fassungsbezug():
    assert motions.base_reference("Änderungsantrag für die Beschlussvorlage 26/0351/1 zur Studie", "26/0714") == "26/0351/1"
    assert motions.base_reference("Antrag zu TOP 9 der Vorlage 26/0792", "26/0792") is None


def _material():
    motion = {"document_id": 315834, "label": "Antrag Volt", "text": VOLT, "pages": None}
    statutes = [{"document_id": 315818, "label": "Anlage Geschäftsordnung", "text": GO, "pages": None}]
    return motion, statutes


def test_pruefung_haelt_belegtes_und_wirft_erfundenes(monkeypatch):
    motion, statutes = _material()
    _, quellen, anchor = motions.build_input(motion, None, statutes)
    payload = {"target": "§ 24 Abs. 2 GO", "pattern": "rewrite",
               "after": {"text": "x", "quote": "Die Ladungsfrist beträgt eine Woche. In dringenden Fällen kann sie auf sechs",
                         "source": "A1"},
               "meaning": "Die Ladungsfrist steigt von zwei Tagen auf eine Woche.",
               "reason": {"text": "Die Frist erschwere die Vorbereitung.",
                          "quote": "Die bisherige Frist von zwei Tagen erschwert die Vorbereitung", "source": "A1"},
               "before": {"text": "erfunden", "quote": "Die Ladungsfrist beträgt drei Tage und mehr", "source": "A2"}}
    out = motions.verify(payload, quellen, anchor, motion, None)
    assert out["applicants"] == ["Volt"]
    assert out["before"]["quote"].startswith("Die Ladungsfrist beträgt zwei Tage")   # der Code, nicht das Modell
    assert out["meaning"] and "Woche" in out["meaning"]["text"]                       # Zahlen aus alt UND neu
    assert [d for d in out["diff"] if d[0] != "="] == [["-", "zwei Tage."], ["+", "eine Woche."]]


def test_alt_gleich_neu_ist_kein_paar():
    motion = {"document_id": 1, "label": "Änderungsantrag Grüne FDP",
              "text": "In §1 Absatz 1 wird jeweils „18. Lebensjahr“ durch „21. Lebensjahr“ ersetzt. Begründung: …", "pages": None}
    _, quellen, anchor = motions.build_input(motion, None, [])
    q = "In §1 Absatz 1 wird jeweils „18. Lebensjahr“ durch „21. Lebensjahr“ ersetzt."
    out = motions.verify({"pattern": "replace", "before": {"quote": q, "source": "A1"}, "after": {"quote": q, "source": "A1"}},
                         quellen, anchor, motion, None)
    assert out["before"] is None and out["after"] is not None


def test_zuordnung_nur_eindeutig():
    subs = [{"id": 1, "title": "Änderungsantrag der Fraktion Bündnis 90/Die Grünen: soziales Deutschlandticket", "factions": []},
            {"id": 2, "title": "Geschäftsordnungsantrag der CDU-Fraktion: Vertagung", "factions": ["CDU"]}]
    assert motions.match_subvote({"applicants": ["Grüne"], "label": "Änderungsantrag VBN"}, subs) == 1
    assert motions.match_subvote({"applicants": ["CDU"], "label": "Änderungsantrag CDU"}, subs) is None
    zwei = [{"id": 3, "title": "Änderungsantrag der SPD-Fraktion: Zuschuss Ratsvorsitz", "factions": ["SPD"]},
            {"id": 4, "title": "Änderungsantrag der SPD-Fraktion: Sitzungsgeld", "factions": ["SPD"]}]
    assert motions.match_subvote({"applicants": ["SPD"], "label": "Antrag SPD"}, zwei) is None


def test_zuordnung_ohne_verfahrensantraege_und_einzelpersonen():
    """Fehlzuordnungen vom 13.11.2026 (eval/run_zuordnung.py): Vertagungsanträge
    hingen an Hauptanträgen, und bei „Änderungsantrag von Ratsherr …" galten die
    Fraktionen, die abgestimmt hatten, als Antragsteller."""
    vertagung = {"id": 1, "title": "Antrag auf Vertagung, gestellt von Ratsfrau Unruh", "factions": ["CDU"]}
    assert motions.match_subvote({"applicants": ["CDU"], "label": "Antrag CDU"}, [vertagung]) is None
    einzeln = {"id": 2, "title": "Änderungsantrag von Ratsherr Baak (Anlage 1)", "factions": ["CDU", "SPD"]}
    assert motions.match_subvote({"applicants": ["CDU"], "label": "Antrag CDU Controlling"}, [einzeln]) is None
    fraktion = {"id": 3, "title": "Änderungsantrag der SPD-Fraktion", "factions": ["SPD"]}
    assert motions.match_subvote({"applicants": ["SPD"], "label": "zu TOP 5 Änderungsantrag SPD-Fraktion"},
                                 [vertagung, fraktion]) == 3
