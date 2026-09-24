"""Die beschlossene Haushaltssatzung aus dem Amtsblatt (council/amtsblatt.py).

Die Texte in ``fixtures/amtsblatt_satzung_texte.json`` sind echte Lesungen der
Ausgaben 5/2021, 4/2023 und 8/2026 durch das Sehmodell (gemessen 24.09.2026).
Die Zahlen, gegen die geprüft wird, stehen so im Amtsblatt.
"""
import json
from pathlib import Path

import pytest

from council import amtsblatt
from council.budget_bylaw import SatzungFehler

TEXTE = json.loads((Path(__file__).parent / "fixtures" / "amtsblatt_satzung_texte.json")
                   .read_text(encoding="utf-8"))


@pytest.mark.parametrize("jahr,sitzung,bekannt,ve,liquiditaet", [
    ("2021", "2021-01-25", "2021-03-05", 29_465_500, 95_000_000),
    ("2023", "2022-12-19", "2023-02-17", 33_053_800, 60_000_000),
    ("2026", "2026-02-09", "2026-04-17", 46_293_000, 100_000_000),
])
def test_die_beschlossene_fassung_wird_gelesen(jahr, sitzung, bekannt, ve, liquiditaet):
    v = amtsblatt.lies(TEXTE[jahr])
    assert v.satzung.year == int(jahr)
    assert v.session_date == sitzung
    assert v.published_on == bekannt
    assert v.satzung.commitment_authorizations == ve
    assert v.satzung.liquidity_loans == liquiditaet
    assert v.satzung.investment_loans == 0
    assert v.satzung.trade_tax_rate == 439


def _vor_der_unterschrift(text: str, satz: str) -> str:
    i = text.rfind("Der Oberbürgermeister")
    return text[:i] + "\n" + satz + "\n\n" + text[i:]


def test_eine_fremde_genehmigung_ist_kein_vermerk_der_satzung():
    """Ausgabe 5/2021 trägt auf derselben Seite die Genehmigung der Änderung 78
    des Flächennutzungsplans („mit Verfügung vom 19. Februar 2021 …
    genehmigt"). Die gehört nicht zur Satzung — erfunden wird kein Vermerk."""
    assert amtsblatt.lies(TEXTE["2021"]).approval_note is None
    fremd = ("Das Amt für regionale Landesentwicklung Weser-Ems hat mit Verfügung vom "
             "19. Februar 2021 die Änderung Nummer 78 des Flächennutzungsplanes 1996 genehmigt.")
    assert amtsblatt.lies(_vor_der_unterschrift(TEXTE["2021"], fremd)).approval_note is None


def test_eine_genehmigung_der_kommunalaufsicht_wird_uebernommen():
    satz = ("Die nach § 120 Abs. 2 NKomVG erforderliche Genehmigung hat das Niedersächsische "
            "Ministerium für Inneres und Sport am 1. März 2021 erteilt.")
    assert amtsblatt.lies(_vor_der_unterschrift(TEXTE["2021"], satz)).approval_note == satz


def test_das_inhaltsverzeichnis_ist_nicht_der_anfang():
    """Die Überschrift steht zuerst im Inhaltsverzeichnis. Beginnt der Leser
    dort, reicht der Abschnitt über fremde Bekanntmachungen."""
    kopf = "Inhalt\nHaushaltssatzung der Stadt Oldenburg (Oldb) für das Haushaltsjahr 2023 ....... 1\n"
    assert amtsblatt.lies(kopf + TEXTE["2023"]).satzung.commitment_authorizations == 33_053_800


def test_silbentrennung_am_zeilenende_wird_zusammengezogen():
    t = TEXTE["2023"].replace("Verpflichtungsermächtigungen", "Verpflichtungs-\nermächtigungen", 1)
    assert amtsblatt.lies(t).satzung.commitment_authorizations == 33_053_800


def test_ohne_satzung_wird_nichts_geraten():
    with pytest.raises(SatzungFehler):
        amtsblatt.lies("Bekanntmachung über die Widmung einer Straße. Aufgrund des § 6 …")


def test_eine_verstellte_zahl_faellt_durch_die_summenprobe():
    t = TEXTE["2023"]
    v = amtsblatt.lies(t)
    zahl = f"{v.satzung.out_capital:,.0f}".replace(",", ".")
    assert zahl in t
    with pytest.raises(SatzungFehler):
        amtsblatt.lies(t.replace(zahl, zahl[:-1] + ("1" if zahl[-1] != "1" else "2"), 1))


def test_nachtragssatzung_zaehlt_nicht():
    assert amtsblatt.hat_satzung("Haushaltssatzung der Stadt Oldenburg (Oldb) für 2024")
    assert not amtsblatt.hat_satzung("1. Nachtragshaushaltssatzung der Stadt Oldenburg (Oldb)")
    assert not amtsblatt.hat_satzung("Satzung über die Straßenreinigung")


def test_beide_schreibweisen_der_ausgaben():
    html = ('<a href="/portal/Amtsblatt/2020/4-2020.pdf">Nr. 4</a>'
            '<a href="/portal/Amtsblatt/2026/2026-8.pdf">Nr. 8</a>'
            '<a href="/portal/Amtsblatt/2026/2026-8.pdf">doppelt</a>'
            '<a href="/portal/Amtsblatt/2021/12a-2021.pdf">Nr. 12a</a>'
            '<a href="/portal/anderes/4-2020.pdf">fremd</a>')
    aus = amtsblatt.ausgaben(html)
    assert [(a.year, a.nr) for a in aus] == [(2020, "4"), (2021, "12a"), (2026, "8")]
    assert aus[0].url == "https://www.oldenburg.de/portal/Amtsblatt/2020/4-2020.pdf"


def test_abweichungen_nennen_was_der_rat_geaendert_hat():
    v = amtsblatt.lies(TEXTE["2023"])
    entwurf = {f: getattr(v.satzung, f) for f in amtsblatt.FELDER}
    assert amtsblatt.abweichungen(entwurf, v.satzung) == []
    entwurf["commitment_authorizations"] = 31_318_800
    assert amtsblatt.abweichungen(entwurf, v.satzung) == ["commitment_authorizations"]
    assert amtsblatt.abweichungen(None, v.satzung) == []


def test_speichern_mit_herkunft(tmp_path):
    from council import herkunft
    from council.store import CouncilStore

    store = CouncilStore(tmp_path / "c.sqlite")
    try:
        v = amtsblatt.lies(TEXTE["2023"])
        url = "https://www.oldenburg.de/portal/Amtsblatt/2023/2023-4.pdf"
        h = herkunft.Herkunft(kind="city", probe=[amtsblatt.PROBE_VEROEFFENTLICHT], url=url,
                              label="Amtsblatt Nr. 4/2023")
        for _ in range(2):
            store.save_satzung_veroeffentlicht(v, issue_nr="4", url=url, herkunft=h)
        zeilen = store.get_satzungen_veroeffentlicht()
        assert len(zeilen) == 1
        z = zeilen[0]
        assert (z["year"], z["issue_nr"], z["published_on"]) == (2023, "4", "2023-02-17")
        assert z["commitment_authorizations"] == 33_053_800
        assert z["herkunft_id"] is not None
        assert "council_budget_bylaw_published" not in store.herkunft_luecken()

        store.amtsblatt_merken(url, 2023, "4", True, "ocr")
        store.amtsblatt_merken(url, 2023, "4", True, "ocr")
        assert store.amtsblatt_gesehen()[url]["has_bylaw"] == 1
    finally:
        store.close()
