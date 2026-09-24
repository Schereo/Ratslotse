"""Die Zuschüsse an Dritte aus Anlage 003 (council/uebersichten.py).

Die Fixtures sind die Wortrahmen echter Seiten, je Bauform eine:
2026 S. 3 und 5 (Dokument 297439, ungedreht), 2019 S. 6 (194219, die „44"
sechs Punkte über ihrer Zeile), 2025 S. 3 (282810, gekippt) und 2021 S. 11
(224266, gedreht; Beträge zwanzig Punkte unter ihrer Nummer)."""
from __future__ import annotations

import json
from pathlib import Path

from council import uebersichten as u
from council.store import CouncilStore

FX = json.loads((Path(__file__).parent / "fixtures" / "uebersichten_woerter.json").read_text())


def _seite(key):
    aus = u.Lesung()
    assert u.lies_seite([tuple(w) for w in FX[key]], aus)
    return aus


def _nr(aus, nr):
    return next(z for z in aus.zeilen if z.lfd_nr == nr)


def test_seite_2026_mit_summenprobe():
    aus = _seite("2026_s3_roh")
    assert aus.budget_year == 2026
    assert [z.lfd_nr for z in aus.zeilen] == list(range(1, 20))
    z = _nr(aus, 1)
    assert (z.sub_budget_no, z.amount_prior, z.amount) == (1, 4121.0, 5192.0)
    assert z.description == "Raummiete für Koordinierungsstelle \"Frauen und Wirtschaft\""
    assert _nr(aus, 4).note == "Förderung des Projektes \"Mädchen kicken mit\""
    # Die Summenzeile unter THH 01 und 02 — und die Zeilen ergeben sie.
    assert aus.summen[1] == (281241.0, 283400.0)
    u.pruefen(aus)
    # THH 03 geht auf der nächsten Seite weiter — seine Summe steht dort.
    assert aus.hinweise == ["ohne Summenzeile: THH [3]"]


def test_lange_erlaeuterung_bleibt_bei_ihrem_zuschuss():
    """Die Erläuterung zum Tierheim hat elf Zeilen und reicht bis dicht an
    die Nummer 46 — nach Nähe bekäme die Tieraufnahmestation ihre letzte."""
    aus = _seite("2026_s5_roh")
    assert _nr(aus, 45).note.startswith("Vertrag mit der Gemeinnützigen Trägergesellschaft")
    assert _nr(aus, 45).note.endswith("nachzuweisen.")
    assert _nr(aus, 46).note == "Anteilige Förderung der Tieraufnahmestation in Rastede"
    # „Haushalt und Controlling" ist ein Produkt, kein dritter Spaltenkopf.
    assert _nr(aus, 32).product_name == "Haushalt und Controlling"
    assert _nr(aus, 34).amount == 25_000_000.0


def test_nummer_ueber_ihrer_zeile_2019():
    aus = _seite("2019_s6_roh")
    assert aus.budget_year == 2019
    assert _nr(aus, 44).description == "Oldenburger Kinderbuchpreis"
    assert _nr(aus, 44).amount == 8000.0
    assert _nr(aus, 45).amount == 6_836_000.0   # Staatstheater
    assert _nr(aus, 45).cash is None             # 2019 gibt es die Spalte nicht


def test_gekippte_seite_2025():
    aus = _seite("2025_s3_gekippt")
    assert aus.budget_year == 2025
    assert aus.summen[1] == (272936.0, 276241.0)
    assert _nr(aus, 3).amount == 19530.0


def test_betraege_unter_der_nummer_2021():
    """Die Beträge stehen bis zu 20 Punkte unter der eigenen Nummer — näher
    an der nächsten. Die Reihenfolge ordnet sie richtig zu."""
    aus = _seite("2021_s11_gedreht")
    assert (_nr(aus, 145).amount_prior, _nr(aus, 145).amount) == (10000.0, 0.0)  # „-"
    assert (_nr(aus, 150).amount_prior, _nr(aus, 150).amount) == (75755.0, 77270.0)
    assert (_nr(aus, 153).description, _nr(aus, 153).amount) == ("Szeneplatz", 70000.0)


def _z(nr, thh, vor, plan):
    return u.Zuschuss(nr, thh, "", "", "x", vor, plan, "", True)


def test_probe_vorlage_summiert_falsch():
    """2020/2021 THH 08: drei vollständige Zeilen, Summenzeile 5.000 € —
    ein Fehler der Vorlage, der den Jahrgang nicht verwirft."""
    aus = u.Lesung(zeilen=[_z(1, 8, 4800, 4800), _z(2, 8, 5000, 5000), _z(3, 8, 8000, 8000)],
                   summen={8: (5000.0, 5000.0)})
    u.pruefen(aus)
    assert aus.bestanden
    assert "Summenzeile der Vorlage weicht ab" in aus.auffaellig[0]


def test_probe_fehlender_betrag_verwirft():
    aus = u.Lesung(zeilen=[_z(1, 8, 4800, None), _z(2, 8, 5000, 5000)],
                   summen={8: (9800.0, 9800.0)})
    u.pruefen(aus)
    assert not aus.bestanden


def test_doppelte_nummer_ist_auffaellig_nicht_falsch():
    aus = u.Lesung(zeilen=[_z(1, 6, 1, 1), _z(1, 6, 2, 2), _z(3, 6, 3, 3)],
                   summen={6: (6.0, 6.0)})
    u.pruefen(aus)
    assert aus.bestanden
    assert any("doppelt" in a for a in aus.auffaellig)
    assert any("übersprungen: [2]" in a for a in aus.auffaellig)


def test_speichern_und_lesen(tmp_path):
    from dataclasses import asdict

    from council import herkunft as h
    store = CouncilStore(tmp_path / "c.sqlite")
    aus = _seite("2026_s3_roh")
    zeilen = [asdict(z) for z in aus.zeilen]
    store.save_zuschuesse(2026, zeilen, h.Herkunft(
        kind="ris", probe=[u.PROBE_ZUSCHUESSE], document_id=297439, label="Übersichten",
        url="https://buergerinfo.oldenburg.de/getfile.php?id=297439&type=do"))
    store.save_zuschuesse(2026, zeilen, h.Herkunft(
        kind="ris", probe=[u.PROBE_ZUSCHUESSE], document_id=297439, label="Übersichten",
        url="https://buergerinfo.oldenburg.de/getfile.php?id=297439&type=do"))
    assert store.zuschuss_jahrgaenge() == [2026]
    thh1 = store.get_zuschuesse(2026, 1)
    assert len(thh1) == 11 and thh1[0]["seq"] == 1 and thh1[0]["cash"] == 0
    summen = {s["sub_budget_no"]: s for s in store.zuschuss_summen()}
    assert summen[1]["amount"] == 283400.0
    store.close()


# --- Schuldenstand und VE (dieselbe Anlage) ---------------------------------

FX2 = json.loads((Path(__file__).parent / "fixtures" / "uebersichten_schulden_ve.json").read_text())


def _seiten(key):
    return [[[tuple(w) for w in seite]] for seite in FX2[key]]


def test_schulden_2026_mit_eigenbetrieben():
    aus = u.lies_schulden(_seiten("2026_schulden"))
    assert aus.budget_year == 2026 and aus.bestanden
    posten = {(p[0], p[1]): p[3:] for p in aus.posten}
    assert posten[("Kernhaushalt", "1.2")] == (43691.0, 40803.0)
    assert posten[("Eigenbetrieb Bäder", "1.2")] == (42215.0, 117011.0)
    assert aus.summen["Eigenbetrieb Gebäudewirtschaft und Hochbau"] == (215316.0, 265946.0)
    # Die Seite bricht im Abfall-Block ab — ohne Summe nicht gespeichert.
    assert aus.ausgelassen == ["Abfallwirtschaftsbetrieb"]
    assert all(p[0] != "Abfallwirtschaftsbetrieb" for p in aus.posten)


def test_schulden_hafen_aufgeloest_und_randbemerkung():
    """2022: Neben dem Hafen-Block steht „Der Eigenbetrieb Hafen wurde
    aufgelöst …" — die Wörter landen nicht in den Bezeichnungen."""
    aus = u.lies_schulden(_seiten("2022_schulden"))
    assert aus.bestanden
    assert aus.ausgelassen == ["Eigenbetrieb Hafen"]
    assert {p[2] for p in aus.posten} <= set(u.SCHULDENARTEN.values())


def test_ve_gegen_satzung():
    aus = u.lies_ve(_seiten("2019_ve"))
    assert aus.budget_year == 2019
    eigene = [(f, b) for p, f, b in aus.zeilen if p == 2019]
    assert eigene == [(2020, 17362500.0), (2021, 8415200.0), (2022, 4080000.0)]
    assert u.pruefe_ve(aus, 29857700.0) == []           # § 3 Satzung 2019
    aus = u.lies_ve(_seiten("2026_ve"))
    # 2026 weichen Übersicht und Satzung um 30.000 € ab — vermerkt, nicht verworfen.
    assert u.pruefe_ve(aus, 41489000.0) == [
        "VE des Plans 2026: Übersicht 41,519,000 €, Haushaltssatzung 41,489,000 €"]
