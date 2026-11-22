"""Werkzeuge für die Ratsarbeit: Gremienbesetzung, Mehrheitsrechner, Rechteschutz.

Drei Dinge, deren Bruch still bliebe:

- **Der Parser** liest die Mitgliederseiten des Ratsinfos. Ändert sich dort
  etwas, darf der Abruf keinen leeren Rat speichern (``fetch_all`` wirft).
- **Die Rechnung** entscheidet, welche Kombinationen eine Mehrheit haben. Ein
  Fehler in der Minimalitäts-Regel zeigte Bündnisse mit überflüssigen Partnern
  oder verschwiege echte.
- **Die Sperre**: Jede Route unter ``/api/tools`` verlangt ``council_tools``.
  Eine vergessene Dependency fiele durch kein anderes Netz.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

_BACKEND = Path(__file__).resolve().parents[1] / "web" / "backend"
sys.path.insert(0, str(_BACKEND))

from fastapi.testclient import TestClient  # noqa: E402
from app import majorities  # noqa: E402
from app.main import app  # noqa: E402
from council import committee_seats as cs  # noqa: E402
from council.store import CouncilStore  # noqa: E402
from kern.store import Store  # noqa: E402

RATSLOTSE_DB = os.environ["RATSLOTSE_DB"]
COUNCIL_DB = os.environ["COUNCIL_DB"]


# ------------------------------------------------------------------ Parser

def _zeile(name: str, partei: str, rolle: str, kpenr: int | None) -> str:
    person = (f'<a href="pe0051.asp?__kpenr={kpenr}" title="Details">{name}</a>'
              if kpenr else name)
    return (f'<tr><td data-label="Name" class="pename">{person}</td>'
            f'<td data-label="Mitgliedschaft">{partei}</td>'
            f'<td data-label="Mitgliedschaft">{partei} {rolle}</td>'
            f'<td data-label="Mitarbeit">{rolle}</td></tr>')


def _ueberschrift(text: str) -> str:
    return f'<tr><td data-label="Personenüberschrift" colspan="3">{text}</td></tr>'


SCHULAUSSCHUSS = "<table>" + "".join([
    # Die Überschrift steht absichtlich falsch: Maßgeblich ist die Rolle.
    _ueberschrift("Vorsitzende/r"),
    _zeile("Anna Beispiel", "SPD", "Ausschussvorsitzende/r", 1),
    _zeile("Ben Beispiel", "Bündnis 90/ Die Grünen", "Ausschussmitglied", 2),
    _zeile("Cem Beispiel", "Bündnis 90/Die Grünen", "Stellv. Ausschussvorsitzende/r", 3),
    _zeile("Dora Beispiel", "FDP", "Grundmandatsinhaber", 4),
    _zeile("Eva Beispiel", "CDU", "Vertreter/in", 5),
    _ueberschrift("Elternvertreter"),
    _zeile("Privatperson", "Elternvertreter", "Stimmberechtigtes Mitglied", None),
]) + "</table>"


def test_mitgliederseite_ergibt_stimmen_beratung_und_keine_vertretung():
    rows = cs.parse_committee_members(SCHULAUSSCHUSS, "Schulausschuss", 38)
    by = {r["name"]: r for r in rows}
    assert set(by) == {"Anna Beispiel", "Ben Beispiel", "Cem Beispiel", "Dora Beispiel",
                       "Elternvertreter"}
    assert by["Anna Beispiel"]["voting"] and by["Cem Beispiel"]["voting"]
    assert not by["Dora Beispiel"]["voting"]          # Grundmandat: beratend
    # Zwei Schreibweisen derselben Fraktion werden eine.
    assert by["Ben Beispiel"]["faction"] == by["Cem Beispiel"]["faction"] == "Bündnis 90/Die Grünen"
    # Ohne Ratsmandat: die Funktion statt des Namens, keine Fraktion.
    ext = by["Elternvertreter"]
    assert ext["kpenr"] is None and ext["faction"] is None and ext["voting"]
    assert "Privatperson" not in {r["name"] for r in rows}


def test_beendete_mitarbeit_faellt_aus_der_personenseite():
    seite = ("<table>"
             '<tr><td data-label="Gremium">Verwaltungsausschuss</td>'
             '<td data-label="Mitgliedschaft">SPD</td><td data-label="Mitarbeit">Beigeordnete/r</td>'
             '<td data-label="Beginn Ende">von 02.11.2026</td></tr>'
             '<tr><td data-label="Gremium">Sportausschuss</td>'
             '<td data-label="Mitgliedschaft">SPD</td><td data-label="Mitarbeit">Ausschussmitglied</td>'
             '<td data-label="Beginn Ende">von 02.11.2026 bis 04.11.2026</td></tr>'
             "</table>")
    assert [r["committee"] for r in cs.parse_person_committees(seite)] == ["Verwaltungsausschuss"]


class _FakeRis:
    def __init__(self, pages: dict[str, str]):
        self.pages = pages

    def get(self, path: str, **params) -> str:
        key = path + "".join(f"?{k}={v}" for k, v in params.items())
        return self.pages.get(key, "<html></html>")


def test_ein_leerer_rat_ersetzt_den_gespeicherten_stand_nicht():
    """Das Ratsinfo ist im 11/2026 schon einmal umgezogen; der alte Host gab
    danach Seiten ohne einen Treffer zurück, keinen Fehler. Genau dieser Fall
    darf nicht als „der Rat hat null Sitze“ gespeichert werden."""
    with pytest.raises(RuntimeError, match="NICHT ersetzt"):
        cs.fetch_all(_FakeRis({}), log=lambda _m: None)  # type: ignore[arg-type]


def test_abruf_setzt_rat_ob_und_verwaltungsausschuss_zusammen():
    rat = "<table>" + "".join(
        _zeile(f"Person {i}", "SPD" if i < 12 else "CDU", "Ratsmitglied", 100 + i) for i in range(21)
    ) + "</table>"
    holders = "<table>" + "".join(
        _zeile(f"Person {i}", "SPD" if i < 12 else "CDU", "", 100 + i) for i in range(21)
    ) + _zeile("Oberbürgermeister Max Muster", "", "", 999) + "</table>"
    va = ('<table><tr><td data-label="Gremium">Verwaltungsausschuss</td>'
          '<td data-label="Mitgliedschaft">SPD</td><td data-label="Mitarbeit">Beigeordnete/r</td>'
          '<td data-label="Beginn Ende">von 02.11.2026</td></tr></table>')
    ob = ('<table><tr><td data-label="Gremium">Verwaltungsausschuss</td>'
          '<td data-label="Mitgliedschaft"></td><td data-label="Mitarbeit">Ausschussvorsitzende/r</td>'
          '<td data-label="Beginn Ende">von 02.11.2026</td></tr></table>')
    pages = {
        "gr0040.asp": '<a href="kp0040.asp?__kgrnr=22&">Rat</a>',
        "kp0040.asp?__kgrnr=22": rat,
        "kp0041.asp": holders,
        "kp0050.asp?__kpenr=100": va,
        "kp0050.asp?__kpenr=999": ob,
    }
    seats = cs.fetch_all(_FakeRis(pages), log=lambda _m: None)  # type: ignore[arg-type]
    rat_stimmen = [s for s in seats if s["committee"] == "Rat" and s["voting"]]
    assert len(rat_stimmen) == 22                       # 21 Ratsmitglieder + OB
    assert any(s["role"] == "Oberbürgermeister/in" for s in rat_stimmen)
    va_sitze = [s for s in seats if s["committee"] == "Verwaltungsausschuss"]
    assert {s["name"] for s in va_sitze} == {"Person 0", "Oberbürgermeister Max Muster"}


def test_wer_eine_personenseite_hat_aber_kein_mandat_ist_keine_fraktion():
    """Gemessen am 22.11.2026: Eine Beschäftigtenvertreterin hat im Ratsinfo
    eine Personenseite. Ohne den Abgleich mit den Mandatsträgern stand sie mit
    Namen als wählbarer Block „Beschäftigtenvertreterin“ im Rechner."""
    rat = "<table>" + "".join(
        _zeile(f"Person {i}", "SPD", "Ratsmitglied", 100 + i) for i in range(21)) + "</table>"
    holders = "<table>" + "".join(_zeile(f"Person {i}", "SPD", "", 100 + i) for i in range(21)) + "</table>"
    betrieb = "<table>" + _zeile("Person 1", "SPD", "Ausschussmitglied", 101) \
        + _zeile("Erika Beispiel", "Beschäftigtenvertreterin", "Stimmberechtigtes Mitglied", 7777) + "</table>"
    pages = {
        "gr0040.asp": '<a href="kp0040.asp?__kgrnr=22&">Rat</a><a href="kp0040.asp?__kgrnr=55&">Betriebsausschuss</a>',
        "kp0040.asp?__kgrnr=22": rat, "kp0040.asp?__kgrnr=55": betrieb, "kp0041.asp": holders,
    }
    seats = cs.fetch_all(_FakeRis(pages), log=lambda _m: None)  # type: ignore[arg-type]
    extern = [s for s in seats if s["committee"] == "Betriebsausschuss" and s["kpenr"] is None]
    assert [(s["name"], s["faction"], s["voting"]) for s in extern] == [("Beschäftigtenvertreterin", None, True)]
    assert "Erika Beispiel" not in {s["name"] for s in seats}


# ---------------------------------------------------------------- Rechnung

def _rat() -> list[dict]:
    """Der Rat 2026 im Kleinen: 52 Ratsmitglieder und der OB."""
    verteilung = [("Bündnis 90/Die Grünen", 13), ("SPD", 12), ("Die Linke", 7), ("CDU", 6),
                  ("AfD", 5), ("Zukunft Oldenburg", 3), ("FDP", 2), ("Volt", 2), ("BSW", 1),
                  ("OBM", 1)]
    rows, n = [], 0
    for fraktion, sitze in verteilung:
        for _ in range(sitze):
            rows.append({"committee": "Rat", "kgrnr": 22, "position": n, "kpenr": n + 1,
                         "name": f"Person {n}", "faction": fraktion, "role": "Ratsmitglied",
                         "voting": 1, "fetched_at": "2026-11-22T12:00:00"})
            n += 1
    rows.append({"committee": "Rat", "kgrnr": 22, "position": n, "kpenr": 999,
                 "name": "Oberbürgermeister Max Muster", "faction": None,
                 "role": "Oberbürgermeister/in", "voting": 1, "fetched_at": "2026-11-22T12:00:00"})
    return rows


def test_mehrheit_ist_mehr_als_die_haelfte_aller_stimmen():
    assert majorities.majority(53) == 27
    assert majorities.majority(11) == 6
    assert majorities.majority(16) == 9
    out = majorities.calculate(_rat(), None, [], [])
    assert out["body"] is not None
    assert (out["body"]["votes"], out["body"]["majority"]) == (53, 27)
    blocks = {b["key"]: b for b in out["blocks"]}
    assert blocks["gruene"]["seats"] == 13 and blocks["ob"]["kind"] == "mayor"
    assert blocks["zukunft-oldenburg"]["kind"] == "group"
    assert blocks["bsw"]["kind"] == "single" and blocks["volt"]["kind"] == "faction"


def test_jede_kombination_ist_minimal_und_hat_die_mehrheit():
    out = majorities.calculate(_rat(), "rat", [], [])
    seats = {b["key"]: b["seats"] for b in out["blocks"]}
    assert out["coalitions"]
    for c in out["coalitions"]:
        total = sum(seats[k] for k in c["blocks"])
        assert total == c["seats"] >= 27
        assert all(total - seats[k] < 27 for k in c["blocks"]), c
    gesehen = {tuple(c["blocks"]) for c in out["coalitions"]}
    assert ("gruene", "spd", "linke") in gesehen
    assert ("gruene", "spd", "fdp") in gesehen
    # Grüne + SPD + Linke + CDU hätte einen überflüssigen Partner.
    assert ("gruene", "spd", "linke", "cdu") not in gesehen


def test_ohne_schliesst_aus_und_dabei_bleibt_drin():
    out = majorities.calculate(_rat(), "rat", ["cdu"], ["afd"])
    assert out["selection"]["include"] == ["cdu"]
    assert out["selection"]["missing"] == 21
    for c in out["coalitions"]:
        assert "cdu" in c["blocks"] and "afd" not in c["blocks"]
        assert "cdu" not in c["added"]


def test_reicht_die_auswahl_schon_gibt_es_genau_diese_eine():
    out = majorities.calculate(_rat(), "rat", ["gruene", "spd", "linke"], [])
    assert out["selection"]["has_majority"]
    assert [c["blocks"] for c in out["coalitions"]] == [["gruene", "spd", "linke"]]


def test_ohne_moegliche_mehrheit_bleibt_die_liste_leer():
    out = majorities.calculate(_rat(), "rat", [], ["gruene", "spd", "linke"])
    assert not out["selection"]["possible"]
    assert out["selection"]["max_seats"] == 21
    assert out["coalitions"] == []


def test_stimmberechtigte_ohne_ratsmandat_sind_kein_partner():
    """Ein Gremium OHNE Eintrag in ``committee_rules`` rechnet mit dem, was das
    Ratsinfo führt — auch mit dessen Stimmberechtigten ohne Ratsmandat."""
    rows = [{"committee": "Beirat für Beispiele", "kgrnr": 99, "position": i, "kpenr": i + 1,
             "name": f"P{i}", "faction": f, "role": "Ausschussmitglied", "voting": 1,
             "fetched_at": None}
            for i, f in enumerate(["SPD"] * 5 + ["CDU"] * 4)]
    rows += [{"committee": "Beirat für Beispiele", "kgrnr": 99, "position": 20 + i, "kpenr": None,
              "name": "Elternvertreter", "faction": None, "role": "Stimmberechtigtes Mitglied",
              "voting": 1, "fetched_at": None} for i in range(4)]
    out = majorities.calculate(rows, "beirat-fuer-beispiele", ["weitere"], [])
    assert out["body"] is not None and out["body"]["votes"] == 13
    ext = next(b for b in out["blocks"] if b["key"] == "weitere")
    assert not ext["selectable"] and ext["members"] == []
    assert out["selection"]["include"] == []
    # SPD allein (5) reicht nicht für 7 von 13 — erst mit der CDU.
    assert [c["blocks"] for c in out["coalitions"]] == [["spd", "cdu"]]
    assert any("ohne Ratsmandat" in n for n in out["body"]["notes"])


# ------------------------------------- die beschlossene Zusammensetzung

def _ausschuss(name: str, verteilung: list[tuple[str, int]], weitere: int = 0) -> list[dict]:
    """Ein Ausschuss, wie das Ratsinfo ihn führt — samt dem Rat, aus dem sich
    die Fraktionsstärken ergeben."""
    rows, n = _rat(), 0
    for fraktion, sitze in verteilung:
        for _ in range(sitze):
            rows.append({"committee": name, "kgrnr": 7, "position": n, "kpenr": 500 + n,
                         "name": f"{fraktion} {n}", "faction": fraktion,
                         "role": "Ausschussmitglied", "voting": 1, "fetched_at": None})
            n += 1
    for _ in range(weitere):
        rows.append({"committee": name, "kgrnr": 7, "position": n, "kpenr": None,
                     "name": "Beschäftigtenvertreter", "faction": None,
                     "role": "Stimmberechtigtes Mitglied", "voting": 1, "fetched_at": None})
        n += 1
    return rows


ELF = [("Bündnis 90/Die Grünen", 3), ("SPD", 3), ("Die Linke", 2), ("CDU", 1), ("AfD", 1),
       ("Zukunft Oldenburg", 1)]
SECHS = [("Bündnis 90/Die Grünen", 2), ("SPD", 1), ("Die Linke", 1), ("CDU", 1), ("AfD", 1)]


def test_sainte_lague_ergibt_die_verteilung_des_rats_von_2026():
    """Gegen die Vorlagen der konstituierenden Sitzung vom 02.11.2026: elf
    Sitze 3/3/2/1/1/1, sechs Sitze 2/1/1/1/1, zehn Beigeordnete 3/3/1/1/1/1.
    Beim zwölften Sitz stehen CDU, FDP und Volt gleich — das Los entscheidet."""
    from council.committee_rules import sainte_lague

    rat = {"gruene": 13, "spd": 12, "linke": 7, "cdu": 6, "afd": 5, "zo": 3, "fdp": 2, "volt": 2}
    assert sainte_lague(rat, 11) == (
        {"gruene": 3, "spd": 3, "linke": 2, "cdu": 1, "afd": 1, "zo": 1}, (), 0)
    assert sainte_lague(rat, 6)[0] == {"gruene": 2, "spd": 1, "linke": 1, "cdu": 1, "afd": 1}
    assert sainte_lague(rat, 10)[0] == {"gruene": 3, "spd": 3, "linke": 1, "cdu": 1, "afd": 1, "zo": 1}
    sicher, gleich, offen = sainte_lague(rat, 12)
    assert sum(sicher.values()) == 11 and set(gleich) == {"cdu", "fdp", "volt"} and offen == 1


def test_jugendhilfeausschuss_hat_fuenfzehn_stimmen_nicht_sechs():
    """Das Ratsinfo führt nur die sechs Ratsmitglieder. Mit 4 von 6 als
    Mehrheit stünde dort eine Mehrheit, die es nicht gibt: Es braucht 8 von 15,
    und die Fraktionen haben zusammen sechs (Vorlage 26/0784)."""
    out = majorities.calculate(_ausschuss("Jugendhilfeausschuss", SECHS), "jugendhilfeausschuss",
                               ["gruene", "spd", "linke"], [])
    body = out["body"]
    assert body is not None
    assert (body["votes"], body["majority"], body["reachable"]) == (15, 8, False)
    assert next(b for b in out["blocks"] if b["key"] == "weitere")["seats"] == 9
    assert not out["selection"]["has_majority"] and out["coalitions"] == [] and out["partners"] == []


def test_betriebsausschuss_zaehlt_drei_beschaeftigte_auch_wenn_das_ratsinfo_zwei_fuehrt():
    """Gebäudewirtschaft: 11 + 3 = 14, Mehrheit 8. Mit den zwei aus dem
    Ratsinfo wären es 7 von 13 — Grüne + SPD + Zukunft Oldenburg (7) hätten
    dann fälschlich eine Mehrheit."""
    name = "Betriebsausschuss Eigenbetrieb Gebäudewirtschaft und Hochbau"
    out = majorities.calculate(_ausschuss(name, ELF, weitere=2), majorities.slug(name),
                               ["gruene", "spd", "zukunft-oldenburg"], [])
    assert out["body"] is not None
    assert (out["body"]["votes"], out["body"]["majority"]) == (14, 8)
    assert out["selection"]["seats"] == 7 and not out["selection"]["has_majority"]


def test_schulausschuss_siebzehn_stimmen_und_der_hinweis_auf_die_berufsbildenden():
    out = majorities.calculate(_ausschuss("Schulausschuss", ELF, weitere=5), "schulausschuss", [], [])
    assert out["body"] is not None
    assert (out["body"]["votes"], out["body"]["majority"]) == (17, 9)
    assert any("19 Stimmen, Mehrheit ab 10" in n for n in out["body"]["notes"])


def test_ein_eintrag_zu_viel_im_ratsinfo_wird_auf_die_sitzverteilung_gekuerzt():
    """Sportausschuss am 22.11.2026: vier SPD-Mitglieder im Ratsinfo, drei
    Sitze laut Ratsbeschluss. Mit zwölf Stimmen läge die Schwelle bei 7 —
    Grüne + Linke + CDU (6) hätten dann fälschlich KEINE Mehrheit."""
    vier = [(f, 4 if f == "SPD" else n) for f, n in ELF]
    out = majorities.calculate(_ausschuss("Sportausschuss", vier), "sportausschuss",
                               ["gruene", "linke", "cdu"], [])
    assert out["body"] is not None
    assert (out["body"]["votes"], out["body"]["majority"]) == (11, 6)
    spd = next(b for b in out["blocks"] if b["key"] == "spd")
    assert spd["seats"] == 3 and len(spd["members"]) == 4      # Namen bleiben, wie das Ratsinfo sie führt
    assert out["selection"]["has_majority"]
    assert any("führt 4 Mitglieder" in n and "3 Sitze" in n for n in out["body"]["notes"])


def test_stimmt_das_ratsinfo_mit_dem_beschluss_bleibt_es_ohne_hinweis():
    out = majorities.calculate(_ausschuss("Verkehrsausschuss", ELF), "verkehrsausschuss", [], [])
    assert out["body"] is not None
    assert (out["body"]["votes"], out["body"]["majority"], out["body"]["notes"]) == (11, 6, [])


def test_jedes_gremium_im_register_kennt_seine_vorlage():
    """Ein Eintrag ohne Quelle wäre eine Behauptung. Der Rat steht im Gesetz."""
    from council.committee_rules import COMPOSITION

    for name, c in COMPOSITION.items():
        assert c.council_seats > 0, name
        assert name == "Rat" or c.source.startswith("Vorlage"), name
        assert bool(c.conditional) == bool(c.conditional_when), name


def test_partner_sind_die_die_fuer_die_mehrheit_in_frage_kommen():
    """Grüne + SPD haben 25 von 27: Jeder Block ab zwei Stimmen reicht allein,
    die drei Einzelstimmen nur zu zweit — und wer auf „ohne“ steht, nie."""
    out = majorities.calculate(_rat(), "rat", ["gruene", "spd"], ["afd"])
    by = {p["key"]: p for p in out["partners"]}
    assert set(by) == {"linke", "cdu", "zukunft-oldenburg", "fdp", "volt", "bsw", "obm", "ob"}
    assert all(by[k]["completes"] for k in ("linke", "cdu", "zukunft-oldenburg", "fdp", "volt"))
    assert not any(by[k]["completes"] for k in ("bsw", "obm", "ob"))
    assert by["linke"]["total"] == 32 and by["bsw"]["total"] == 26
    # Wer allein reicht, steht vorn.
    reicht = [p["completes"] for p in out["partners"]]
    assert reicht == sorted(reicht, reverse=True)


def test_ein_entbehrlicher_block_kommt_nicht_in_frage():
    """A (3) braucht 5 von 9: Mit B (5) reicht es, C (1) hilft allein nicht und
    wäre neben B überflüssig — C ist kein Vorschlag."""
    rows = [{"committee": "Rat", "kgrnr": 22, "position": i, "kpenr": i + 1, "name": f"P{i}",
             "faction": f, "role": "Ratsmitglied", "voting": 1, "fetched_at": None}
            for i, f in enumerate(["SPD"] * 3 + ["CDU"] * 5 + ["BSW"])]
    out = majorities.calculate(rows, "rat", ["spd"], [])
    assert [p["key"] for p in out["partners"]] == ["cdu"]


def test_ohne_auswahl_oder_mit_mehrheit_gibt_es_keine_vorschlaege():
    assert majorities.calculate(_rat(), "rat", [], [])["partners"] == []
    assert majorities.calculate(_rat(), "rat", ["gruene", "spd", "linke"], [])["partners"] == []
    assert majorities.calculate(_rat(), "rat", ["fdp"], ["gruene", "spd", "linke"])["partners"] == []


def test_die_uebersicht_rechnet_dieselbe_auswahl_in_jedem_gremium():
    rows = _rat()
    rows += [{"committee": "Verkehrsausschuss", "kgrnr": 35, "position": i, "kpenr": i + 1,
              "name": f"P{i}", "faction": f, "role": "Ausschussmitglied", "voting": 1,
              "fetched_at": None}
             for i, f in enumerate(["Bündnis 90/Die Grünen"] * 3 + ["SPD"] * 3 + ["Die Linke"] * 2
                                   + ["CDU", "AfD", "Zukunft Oldenburg"])]
    out = majorities.calculate(rows, "verkehrsausschuss", ["gruene", "spd"], ["afd"])
    by = {o["key"]: o for o in out["overview"]}
    assert [o["key"] for o in out["overview"]] == [b["key"] for b in out["bodies"]]
    assert (by["rat"]["seats"], by["rat"]["majority"], by["rat"]["has_majority"]) == (25, 27, False)
    assert by["rat"]["missing"] == 2
    assert (by["verkehrsausschuss"]["seats"], by["verkehrsausschuss"]["has_majority"]) == (6, True)


def test_ohne_abruf_gibt_es_kein_gremium():
    out = majorities.calculate([], None, [], [])
    assert out["body"] is None and out["bodies"] == []


# --------------------------------------------------------------- Speicher

def test_besetzung_wird_als_ganzes_ersetzt(tmp_path):
    store = CouncilStore(str(tmp_path / "council.sqlite"))
    try:
        assert store.committee_seats() == []
        store.replace_committee_seats(_rat())
        store.replace_committee_seats(_rat()[:30])
        rows = store.committee_seats()
        assert len(rows) == 30 and rows[0]["voting"] == 1 and rows[0]["fetched_at"]
    finally:
        store.close()


# ------------------------------------------------------------------ Sperre

def test_jede_werkzeug_route_verlangt_das_recht():
    """Wie beim Haushalt: Eine Route ohne die Dependency antwortet jedem
    angemeldeten Konto, und kein anderer Test wird davon rot."""
    from tests.test_endpunkt_schutz import _endpunkte

    routen = [(m, p, n) for m, p, n in _endpunkte() if p.startswith("/api/tools")]
    assert routen, "Keine /api/tools-Route gefunden — dann prüft dieser Wächter nichts."
    ohne = sorted(f"{m.upper()} {p}" for m, p, n in routen
                  if "require_permission_council_tools" not in n)
    assert not ohne, ("Diese Werkzeug-Routen prüfen das Recht 'council_tools' nicht:\n  "
                      + "\n  ".join(ohne) + "\nBeheben: `Depends(require_tools)` aus "
                      "web/backend/app/routers/tools.py.")


@pytest.fixture
def client():
    for base in (RATSLOTSE_DB, COUNCIL_DB):
        for suffix in ("", "-wal", "-shm"):
            Path(base + suffix).unlink(missing_ok=True)
    return TestClient(app)


def test_nur_ratsmitglieder_bekommen_den_rechner(client):
    r = client.post("/api/auth/register", json={"display_name": "Test", "email": "rat@example.org",
                                                "password": "password123"})
    assert r.status_code == 201
    assert client.get("/api/tools/majorities").status_code == 403

    store = Store(RATSLOTSE_DB)
    try:
        store.set_web_user_roles(store.get_web_user_by_email("rat@example.org")["id"],
                                 ["council_member"])
    finally:
        store.close()
    council = CouncilStore(COUNCIL_DB)
    try:
        council.replace_committee_seats(_rat())
    finally:
        council.close()

    out = client.get("/api/tools/majorities", params={"include": "spd", "exclude": "afd,unbekannt"})
    assert out.status_code == 200
    body = out.json()
    assert body["body"]["majority"] == 27
    assert body["selection"]["include"] == ["spd"] and body["selection"]["exclude"] == ["afd"]
    assert all("spd" in c["blocks"] for c in body["coalitions"])
