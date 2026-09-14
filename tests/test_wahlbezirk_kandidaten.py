"""Der Wahlbezirk in der Kandidaten-Rangliste — als Filter und als Hochburg.

Tims Wunsch (15.09.2026): „ein fünfter Filter fürs Sortieren, der Wahlbezirk
heißt, wo man nach Wahlbezirk die Liste filtern kann? Oder dass auch in der
Liste überhaupt der Wahlbezirk mit angezeigt wird."

**Ein Wahlbezirk ist kein Merkmal einer Kandidatur.** Wer antritt, steht in
einem WAHLBEREICH und bekommt in jedem seiner 15 bis 24 Wahlbezirke Stimmen.
Als Spalte gäbe es also nicht einen Wert, sondern zwanzig. Deshalb zwei
Antworten auf dieselbe Frage:

1. **Als Filter** („wer lag in meinem Wahllokal vorn?") — dann sind Stimmen,
   Anteil und Rang die dieses Bezirks.
2. **Als Hochburg** je Zeile („↗ 214 GS Drielake · 292") — der Wahlbezirk, in
   dem diese Kandidatur am stärksten war. Das IST ein Merkmal der Kandidatur.

Beides rechnet gegen die Bezirksdatei, die je Liste eine Spalte pro
Listenplatz führt (``D<liste>_2_<platz>``). Die Zahlen prüft dieser Test
gegen den Wahlbereich, in den sie sich summieren müssen.
"""
from __future__ import annotations

import collections
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL / "web" / "backend"))

from app.election import archive, candidates, service  # noqa: E402
from app.routers import wahlabend as router  # noqa: E402


@pytest.fixture(autouse=True)
def _frei(monkeypatch):
    monkeypatch.setenv("FEATURE_FLAGS", "wahlabend")
    archive.reset()
    yield
    archive.reset()


@pytest.fixture(scope="module")
def stand():
    """Register, Snapshot und fertige Nacht der Ratswahl 2026 — ohne Netz."""
    teile = archive.snapshot("ratswahl-2026")
    assert teile is not None
    reg, snap = teile
    nacht = archive.night("ratswahl-2026")
    assert nacht is not None
    return reg, snap, nacht


# ------------------------------------------------------------------ die Zahlen

def test_die_bezirke_summieren_sich_zur_kandidatur(stand):
    """Die harte Zusage: Was ein Mensch in allen Wahlbezirken seines
    Wahlbereichs bekommen hat, ist genau das, was in der Wahlbereichs-Ansicht
    steht. Ohne sie zeigten Filter und Gesamtliste verschiedene Wahlen."""
    reg, snap, nacht = stand
    summe: collections.Counter[tuple[str, int, int]] = collections.Counter()
    for bezirk in service.district_refs(snap):
        detail = service.district_candidates(reg, snap, bezirk["number"])
        assert detail is not None
        for slug, eintrag in detail["lists"].items():
            for platz, stimmen in eintrag["candidates"].items():
                summe[(slug, platz, detail["area"])] += stimmen or 0

    geprueft = 0
    for area in nacht["areas"]:
        for ap in area["parties"]:
            for c in ap["candidates"]:
                if c["votes"] is None:
                    continue
                assert summe[(ap["slug"], c["position"], area["number"])] == c["votes"], (
                    ap["slug"], area["roman"], c["name"])
                geprueft += 1
    assert geprueft > 300, "Testannahme: die 2026er Kandidaturen tragen Personenstimmen"


def test_ein_wahlbezirk_kennt_sein_wahllokal_und_seinen_wahlbereich(stand):
    reg, snap, _ = stand
    d = service.district_candidates(reg, snap, 504)
    assert d is not None
    assert d["name"] == "504 Grundschule Bümmerstede" and d["area"] == 5 and d["postal"] is False
    assert d["valid_votes"] == 1718
    # Briefwahl gehört dazu — ein Drittel der Stimmen liegt dort.
    brief = service.district_candidates(reg, snap, 954)
    assert brief is not None and brief["postal"] is True and brief["area"] == 5
    assert service.district_candidates(reg, snap, 777) is None


# ------------------------------------------------------------------ der Filter

def test_der_filter_zeigt_die_kandidaturen_dieses_wahllokals(stand):
    reg, snap, nacht = stand
    d = service.district_candidates(reg, snap, 504)
    r = candidates.ranking(nacht, bezirk=d, bezirke=service.district_refs(snap))
    assert r["district"] == 504 and r["district_name"] == "504 Grundschule Bümmerstede"
    # Nur der Wahlbereich des Bezirks — andere standen dort nicht auf dem Zettel.
    assert r["area"] == 5 and {z["area"] for z in r["rows"]} == {5}
    assert r["shown"] == r["total"] < 383
    # Der Rang ist der DIESES Bezirks, nicht der stadtweite.
    erste = r["rows"][0]
    assert erste["rank"] == 1 and erste["name"].startswith("Oeljeschläger")
    stimmen = [z["votes"] or 0 for z in r["rows"]]
    assert stimmen == sorted(stimmen, reverse=True)
    # Und die Zahl ist die des Wahllokals, nicht die der Stadt.
    stadtweit = next(z for z in candidates.ranking(nacht)["rows"] if z["name"].startswith("Oeljeschläger"))
    assert erste["votes"] == 105 and stadtweit["votes"] == 1539


def test_der_anteil_rechnet_gegen_die_liste_im_bezirk(stand):
    reg, snap, nacht = stand
    d = service.district_candidates(reg, snap, 504)
    r = candidates.ranking(nacht, bezirk=d)
    for z in r["rows"]:
        gesamt = d["lists"][z["party"]]["total"]
        if z["votes"] and gesamt:
            assert z["party_share_pct"] == round(100 * z["votes"] / gesamt, 1), z["name"]


def test_der_abstand_zum_sitz_bleibt_im_bezirk_leer(stand):
    """Wie viele Stimmen bis zum Sitz fehlen, ist eine Rechnung über den
    ganzen Wahlbereich. Im Wahllokal wäre dieselbe Zahl eine Behauptung."""
    reg, snap, nacht = stand
    r = candidates.ranking(nacht, bezirk=service.district_candidates(reg, snap, 504))
    assert all(z["votes_to_seat"] is None for z in r["rows"])


def test_die_auswahlliste_faehrt_mit(stand):
    reg, snap, nacht = stand
    r = candidates.ranking(nacht, bezirke=service.district_refs(snap))
    assert len(r["districts"]) == 133
    assert r["districts"][0]["number"] == 101 and not r["districts"][0]["postal"]
    assert sum(1 for b in r["districts"] if b["postal"]) == 42
    nummern = [b["number"] for b in r["districts"]]
    assert nummern == sorted(nummern)


# ------------------------------------------------------------------ die Hochburg

def test_jede_kandidatur_mit_stimmen_hat_eine_hochburg(stand):
    reg, snap, nacht = stand
    r = candidates.ranking(nacht, hochburgen=service.top_districts(reg, snap))
    mit = [z for z in r["rows"] if z["votes"]]
    assert len(mit) > 300
    for z in mit:
        assert z["top_district"] is not None and z["top_district_name"], z["name"]
        # Die Hochburg liegt im eigenen Wahlbereich …
        erwartet = (z["top_district"] - 900) // 10 if z["top_district_postal"] else z["top_district"] // 100
        assert erwartet == z["area"], (z["name"], z["top_district"])
        # … und sie kann nicht mehr Stimmen haben als die Person insgesamt.
        assert 0 < (z["top_district_votes"] or 0) <= (z["votes"] or 0), z["name"]


def test_die_hochburg_ist_wirklich_die_staerkste(stand):
    """Gegen die Rohzahlen nachgerechnet, nicht gegen dieselbe Funktion."""
    reg, snap, nacht = stand
    r = candidates.ranking(nacht, hochburgen=service.top_districts(reg, snap))
    prange = next(z for z in r["rows"] if z["name"].startswith("Prange"))
    beste = max(
        ((service.district_candidates(reg, snap, b["number"]) or {}).get("lists", {})
         .get(prange["party"], {}).get("candidates", {}).get(prange["position"], 0), b["number"])
        for b in service.district_refs(snap) if b["area"] == prange["area"]
    )
    assert (prange["top_district_votes"], prange["top_district"]) == beste
    assert prange["top_district_name"] == "214 GS Drielake"


def test_eine_briefwahl_hochburg_sagt_dass_sie_eine_ist(stand):
    reg, snap, nacht = stand
    r = candidates.ranking(nacht, hochburgen=service.top_districts(reg, snap))
    brief = [z for z in r["rows"] if z["top_district_postal"]]
    assert brief, "Testannahme: mindestens eine Kandidatur ist in der Briefwahl am stärksten"
    for z in brief:
        assert z["top_district"] is not None and z["top_district"] >= 900
        assert "Briefwahl" in z["top_district_name"]


# ------------------------------------------------------------------ der Endpunkt

def test_der_endpunkt_filtert_und_weist_unbekanntes_ab():
    r = router.wahlabend_kandidaten(probe=None, counted=None, wahl="ratswahl-2026",
                                    sort="votes", party=None, area=None, district=504)
    assert r["district"] == 504 and r["area"] == 5 and len(r["districts"]) == 133

    with pytest.raises(HTTPException) as e:
        router.wahlabend_kandidaten(probe=None, counted=None, wahl="ratswahl-2026",
                                    sort="votes", party=None, area=None, district=777)
    assert e.value.status_code == 404

    # Ein Bezirk, der nicht in den gewählten Wahlbereich gehört, ist ein
    # Widerspruch — und keine leere Liste.
    with pytest.raises(HTTPException) as e:
        router.wahlabend_kandidaten(probe=None, counted=None, wahl="ratswahl-2026",
                                    sort="votes", party=None, area=1, district=504)
    assert e.value.status_code == 400


def test_liste_und_bezirk_lassen_sich_kombinieren():
    r = router.wahlabend_kandidaten(probe=None, counted=None, wahl="ratswahl-2026",
                                    sort="votes", party="afd", area=None, district=504)
    assert r["district"] == 504
    assert r["rows"] and all(z["party"] == "afd" for z in r["rows"])
    assert r["shown"] < r["total"]
