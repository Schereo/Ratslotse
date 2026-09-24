"""Oldenburg im Bundesvergleich (council/bundesvergleich.py).

``fixtures/wegweiser_export.json`` sind echte Exporte des Wegweisers Kommune
vom 24.09.2026: zwölf Städte in einer Datei, Finanzen und Demografie, dazu
ein Auszug der Regionenliste.
"""
import json
import sys
from pathlib import Path

import pytest

from council import bundesvergleich as bv

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "web" / "backend"))

EXPORT = json.loads((Path(__file__).parent / "fixtures" / "wegweiser_export.json")
                    .read_text(encoding="utf-8"))
NAMEN = {r["friendlyUrl"]: r["name"] for r in EXPORT["regionen"]}
KOEPFE = list(bv.INDIKATOREN.values())


def _finanzen():
    return bv.lies_export(EXPORT["finanzen"], EXPORT["slugs"], NAMEN, KOEPFE)


def test_export_wird_nach_reihenfolge_und_name_zugeordnet():
    w = _finanzen()
    assert w[("oldenburg-oldenburg", bv.INDIKATOREN["income_tax"], 2023)] == 527
    assert w[("oldenburg-oldenburg", bv.INDIKATOREN["property_tax_b"], 2019)] == 194
    assert w[("osnabrueck", bv.INDIKATOREN["liquidity_loans"], 2019)] == 574
    assert {j for (_, _, j) in w} == {2019, 2020, 2021, 2022, 2023}
    assert {s for (s, _, _) in w} == set(EXPORT["slugs"])


def test_verschobene_spalten_fallen_auf():
    """Eine andere Reihenfolge als angefragt: Der Name in der Spalte passt
    nicht mehr — dann wird nichts gelesen, statt Werte zu vertauschen."""
    verdreht = EXPORT["slugs"][1:] + EXPORT["slugs"][:1]
    with pytest.raises(bv.VergleichFehler):
        bv.lies_export(EXPORT["finanzen"], verdreht, NAMEN, KOEPFE)


def test_gruppe_nach_einwohnern_plus_niedersachsen():
    demo = bv.lies_export(EXPORT["demografie"], EXPORT["slugs"], NAMEN, [bv.BEVOELKERUNG])
    ew = {s: w for (s, _, j), w in demo.items() if j == 2023}
    assert ew["oldenburg-oldenburg"] == 174_629
    ew |= {"berlin": 3_700_000, "emden": 50_659, "suhl": 36_986}
    g = {x["slug"]: x for x in bv.gruppe(EXPORT["regionen"], ew)}
    assert "oldenburg-oldenburg" in g and g["oldenburg-oldenburg"]["ags"] == "03403000"
    assert "emden" in g            # zu klein, aber in Niedersachsen
    assert "berlin" not in g and "suhl" not in g


def _eigene(**abweichung):
    ew = {2019: 169_077, 2023: 174_629}
    return ew, {
        "income_tax": {2019: 491 * ew[2019], 2023: 527 * ew[2023] * abweichung.get("income", 1)},
        "property_tax_b": {2019: 194 * ew[2019] * 1.01},
        "liquidity_year_end": {2019: 70_100_000, 2023: -5_000_000},
    }


def test_probe_gegen_die_eigenen_reihen():
    ew, eigene = _eigene()
    werte = {("income_tax", 2019): 491, ("income_tax", 2023): 527,
             ("property_tax_b", 2019): 194, ("property_tax_b", 2023): 195,
             ("liquidity_loans", 2019): 0, ("liquidity_loans", 2023): 0}
    p = bv.pruefe_oldenburg(werte, ew, eigene)
    assert ("income_tax", 2023) in p.bestanden
    assert ("property_tax_b", 2019) in p.bestanden          # 1 % Abstand
    assert ("property_tax_b", 2023) not in p.bestanden      # keine eigene Reihe
    assert ("liquidity_loans", 2019) in p.bestanden         # Stand positiv, Wert 0
    assert ("liquidity_loans", 2023) not in p.bestanden     # Stand negativ, Wert 0 passt nicht
    assert len(p.hinweise) == 2


def test_abweichung_ueber_der_toleranz_faellt_heraus():
    ew, eigene = _eigene(income=1.13)                      # wie die Gewerbesteuer 2023
    p = bv.pruefe_oldenburg({("income_tax", 2023): 527}, ew, eigene)
    assert not p.bestanden and "eigene Reihe" in p.hinweise[0]


def test_kennwerte():
    k = bv.kennwerte([0, 0, 0, 10, 20])
    assert (k["n"], k["zero"], k["min"], k["median"], k["max"]) == (5, 3, 0, 0, 20)
    assert k["p75"] == 10
    assert bv.kennwerte([4.0, 1.0, 3.0, 2.0])["median"] == 2.5
    assert bv.kennwerte([])["median"] is None


def test_endpunkt_rechnet_verteilung_ohne_rang(tmp_path):
    from council import herkunft
    from council.store import CouncilStore
    from app.routers.council import haushalt_bundesvergleich, haushalt_vergleich

    store = CouncilStore(tmp_path / "c.sqlite")
    try:
        w = _finanzen()
        ags = {r["friendlyUrl"]: r["ags"][:8] for r in EXPORT["regionen"]}
        von = {v: k for k, v in bv.INDIKATOREN.items()}
        zeilen = [{"year": j, "key": ags[s], "city": NAMEN[s], "indicator": von[kopf],
                   "value": v, "unit": "eur_je_ew"} for (s, kopf, j), v in w.items()]
        store.save_staedtevergleich(bv.SERIES, zeilen, herkunft.Herkunft(
            kind="wegweiser", probe=[bv.PROBE], url=bv.DATEN_SEITE, label="Wegweiser"))
        a = haushalt_bundesvergleich(_user={}, store=store)
        einkommen = next(k for k in a["indicators"] if k["key"] == "income_tax")
        j = next(y for y in einkommen["years"] if y["year"] == 2023)
        assert j["oldenburg"] == 527 and j["stats"]["n"] == 12
        assert j["stats"]["min"] <= j["stats"]["median"] <= j["stats"]["max"]
        assert [c["city"] for c in j["cities"]] == sorted(c["city"] for c in j["cities"])
        assert sum(c["is_oldenburg"] for c in j["cities"]) == 1
        assert a["group"]["lower_saxony"] == 2               # Oldenburg und Osnabrück
        assert not any("rank" in k or "platz" in k for k in j)
        # Die Seite der acht Städte sieht die neue Reihe nicht.
        assert all(v["series"] != bv.SERIES for v in haushalt_vergleich(_user={}, store=store)["values"])
    finally:
        store.close()
