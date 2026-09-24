"""Fördermittel von EU und Bund (council/foerdermittel.py).

Die Zeilen in ``fixtures/foerdermittel_listen.json`` sind echte Zeilen der
Listen vom 24.09.2026: Kopf, die ersten städtischen Vorhaben und ein paar
fremde Empfänger, die NICHT übernommen werden dürfen.
"""
import json
import sys
from pathlib import Path

import pytest

from council import foerdermittel as fm

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "web" / "backend"))

LISTEN = json.loads((Path(__file__).parent / "fixtures" / "foerdermittel_listen.json")
                    .read_text(encoding="utf-8"))


def test_eu_2014_liest_nur_die_stadt_und_ihre_gesellschaften():
    l = fm.lies_eu(LISTEN["efre_2014"], fonds="efre", periode="2014-2020")
    assert l.stand == "2024-09-30"
    assert l.vorhaben, "keine städtischen Vorhaben gelesen"
    assert {v.recipient_key for v in l.vorhaben} <= set(fm.EMPFAENGER)
    # Zweckverbände und die „Bäderbetriebe Rinteln" stehen in der Datei,
    # gehören aber nicht zur Stadt.
    assert not any("Rinteln" in v.recipient or "Zweckverband" in v.recipient for v in l.vorhaben)
    assert l.zeilen > len(l.vorhaben)
    for v in l.vorhaben:
        assert v.funder == "EU" and v.period == "2014-2020"
        assert v.start and v.amount_granted and v.amount_granted <= (v.amount_total or 0) + 1
        assert v.source_id.startswith("h")  # 2014–2020 führt keinen Code


def test_eu_2021_erkennt_die_spalten_am_kopf():
    """Die Periode 2021–2027 ordnet die Spalten anders (Begünstigter zuletzt)."""
    l = fm.lies_eu(LISTEN["esf_2021"], fonds="esf", periode="2021-2027")
    assert l.stand == "2026-01-31"
    pace = [v for v in l.vorhaben if "Pro-Aktiv-Center" in v.title]
    assert pace and pace[0].recipient_key == "city"
    assert pace[0].source_id.startswith("Nds_")
    assert pace[0].end and pace[0].end > pace[0].start
    assert all(v.summary for v in l.vorhaben)


def test_ohne_kopf_wird_nichts_gelesen():
    with pytest.raises(fm.FoerderFehler):
        fm.lies_eu([("irgendwas",), ("Stadt Oldenburg", "x")], fonds="efre", periode="2021-2027")


def test_foekat_filtert_nach_namen_und_gemeindekennziffer():
    text = LISTEN["foekat_csv"]
    zeilen = text.count("\n") - 1
    l = fm.lies_foekat(text, zeilen)
    assert l.zeilen == zeilen
    schluessel = {v.recipient_key for v in l.vorhaben}
    assert "city" in schluessel
    # GSG ENERGIE (Tochter, nicht im Beteiligungsbericht) und der Zweckverband
    # KDO stehen in der Datei und bleiben draußen.
    assert not any("ENERGIE" in v.recipient or "KDO" in v.recipient for v in l.vorhaben)
    assert len(l.vorhaben) < zeilen
    for v in l.vorhaben:
        assert v.funder.startswith("BM") and v.amount_granted and v.amount_granted > 0
        assert v.source_id and v.start


def test_foekat_abgeschnittener_export_faellt_durch():
    text = LISTEN["foekat_csv"]
    with pytest.raises(fm.FoerderFehler, match="Zeilen"):
        fm.lies_foekat(text, text.count("\n") + 5)


def test_andere_gemeinde_gleichen_namens_zaehlt_nicht():
    text = LISTEN["foekat_csv"]
    kopf, *zeilen = text.strip().split("\n")
    stadt = next(z for z in zeilen if '="Stadt Oldenburg";="03403000"' in z)
    fremd = stadt.replace('="03403000"', '="01055033"', 1)
    l = fm.lies_foekat(kopf + "\n" + fremd + "\n", 1)
    assert l.vorhaben == []


def test_namen_nur_exakt():
    assert fm.empfaenger_schluessel("  Stadt   Oldenburg ") == "city"
    assert fm.empfaenger_schluessel("Stadt Oldenburg in Holstein") is None
    assert fm.empfaenger_schluessel("GSG ENERGIE GmbH") is None


def test_treffer_aus_der_suchseite():
    assert fm.treffer_aus_seite("Suchergebnis &nbsp;(1.295&nbsp;Treffer)") == 1295
    assert fm.treffer_aus_seite("Die Suche liefert keine Ergebnisse, bitte …") == 0
    assert fm.treffer_aus_seite("Wartungsarbeiten") is None


def test_dubletten_zwischen_eu_und_bund():
    eu = fm.Vorhaben("efre", "a", "Stadt Oldenburg", "city", "Radweg X", "EU", None,
                     100.0, 50.0, "2022-01-01", None)
    bund = fm.Vorhaben("foekat", "b", "Stadt Oldenburg", "city", "Radweg  x", "BMV", None,
                       None, 20.0, "2022-01-01", None)
    anders = fm.Vorhaben("foekat", "c", "Stadt Oldenburg", "city", "Radweg X", "BMV", None,
                         None, 20.0, "2023-01-01", None)
    assert fm.dubletten([eu, bund, anders]) == [(eu, bund)]


def test_links_der_uebersichtsseite():
    html = ('<a href="https://x/download/1/Liste_der_Vorhaben_EFRE_Stand_31.01.2026.xlsx">a</a>'
            '<a href="https://x/download/2/Liste_der_Vorhaben_ESF_2014-2020_Stand_30.09.2024.xlsx">b</a>'
            '<a href="https://x/download/1/Liste_der_Vorhaben_EFRE_Stand_31.01.2026.xlsx">doppelt</a>'
            '<a href="https://x/download/3/Programm.xlsx">c</a>')
    assert fm.eu_listen(html) == [
        ("https://x/download/1/Liste_der_Vorhaben_EFRE_Stand_31.01.2026.xlsx", "efre", "2021-2027"),
        ("https://x/download/2/Liste_der_Vorhaben_ESF_2014-2020_Stand_30.09.2024.xlsx", "esf", "2014-2020"),
    ]


def test_speichern_ersetzt_je_liste_und_der_endpunkt_summiert(tmp_path):
    from council import herkunft
    from council.store import CouncilStore
    from app.routers.council import haushalt_foerdermittel

    store = CouncilStore(tmp_path / "c.sqlite")
    try:
        eu = fm.lies_eu(LISTEN["efre_2014"], fonds="efre", periode="2014-2020")
        bund = fm.lies_foekat(LISTEN["foekat_csv"], LISTEN["foekat_csv"].count("\n") - 1)
        h_eu = herkunft.Herkunft(kind="eu", probe=[fm.PROBE_EU], url="https://x/efre.xlsx", label="EFRE")
        h_bund = herkunft.Herkunft(kind="bund", probe=[fm.PROBE_FOEKAT], url="https://x/foekat", label="FöKat")
        for _ in range(2):
            store.save_foerdermittel("efre", "2014-2020", eu.vorhaben, list_as_of=eu.stand,
                                     list_url="https://x/efre.xlsx", herkunft=h_eu)
        store.save_foerdermittel("foekat", None, bund.vorhaben, list_as_of=None,
                                 list_url="https://x/foekat", herkunft=h_bund)
        assert len(store.get_foerdermittel()) == len(eu.vorhaben) + len(bund.vorhaben)
        assert "council_grants_received" not in store.herkunft_luecken()

        antwort = haushalt_foerdermittel(_user={}, store=store)
        summen = {t["group"]: t for t in antwort["totals"]}
        assert summen["eu"]["n"] == len(eu.vorhaben)
        assert summen["bund"]["amount"] == pytest.approx(sum(v.amount_granted for v in bund.vorhaben))
        assert antwort["recipients"]["city"] == "Stadt Oldenburg"
        assert {l["source"] for l in antwort["lists"]} == {"efre", "foekat"}
        assert all(str(z["herkunft_id"]) in antwort["provenance"] for z in antwort["rows"])

        # Ein neuer Stand der Liste ersetzt die alten Zeilen — auch wenn ein
        # Vorhaben aus der Liste gefallen ist.
        store.save_foerdermittel("efre", "2014-2020", eu.vorhaben[:1], list_as_of=eu.stand,
                                 list_url="https://x/efre.xlsx", herkunft=h_eu)
        assert len([z for z in store.get_foerdermittel() if z["source"] == "efre"]) == 1
    finally:
        store.close()
