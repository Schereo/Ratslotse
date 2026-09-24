"""Gescannte Jahresabschlüsse der Gesellschaften, gelesen über den OCR-Text.

``fixtures/gesellschaft_abschluss_ocr.json`` ist der Text, den das Sehmodell
des OCR-Laufs (``scripts/backfill_anlagen_ocr.py``) für neun gescannte
Bilanzen und GuVs gespeichert hat — VWG 2018, OTM 2019, BBGO 2019 und die
Weser-Ems Halle 2021. Die Sollwerte sind die, die ein anderes Dokument für
dasselbe Jahr nennt (Vorjahresspalte des Folgeabschlusses), soweit es eins
gibt; VWG 2018 und OTM 2019 hat nur der Scan.
"""
import json
from pathlib import Path

import pytest

from council import gesellschaft_abschluss as ga

FIX = json.loads((Path(__file__).parent / "fixtures" / "gesellschaft_abschluss_ocr.json")
                 .read_text(encoding="utf-8"))


def _werte(doc_id: str) -> dict:
    a = FIX[doc_id]
    lesung = ga.lies_ocr(a["text"], a["title"], a["label"], int(doc_id))
    return {(k.enterprise, k.year, k.metric): k.value for k in lesung.kennzahlen}


@pytest.mark.parametrize("doc_id, erwartet", [
    ("217001", {("bbgo", 2019, "bilanzsumme"): 2_814_450.98}),
    ("217002", {("bbgo", 2019, "jahresergebnis"): -2_853_938.60}),
    ("203301", {("vwg", 2018, "bilanzsumme"): 61_340_724.92}),
    ("203302", {("vwg", 2018, "jahresergebnis"): 0.0}),
    ("216642", {("otm", 2019, "bilanzsumme"): 652_170.56}),
    ("216643", {("otm", 2019, "jahresergebnis"): -907_203.67}),
    ("247727", {("weh_komplementaer", 2021, "jahresergebnis"): 1_129.40}),
])
def test_geschaeftsjahr_aus_dem_scan(doc_id, erwartet):
    assert _werte(doc_id) == erwartet


def test_bilanzsumme_ist_die_schlusszeile_nicht_der_groesste_betrag():
    """Weser-Ems Halle Beteiligungs-GmbH 2021: Das gezeichnete Kapital
    (25.000 €, zweimal gedruckt) ist größer als die Bilanzsumme."""
    assert _werte("247726") == {("weh_komplementaer", 2021, "bilanzsumme"): 18_320.66}


def test_kein_vorjahr_aus_dem_scan():
    """Die Vorjahresspalte der Weser-Ems Halle KG 2021 nennt 55.973.901,92 €,
    der eigene Abschluss 2020 55.973.936,40 € — aus dem Scan kommt nur 2021."""
    assert _werte("247713") == {("weh", 2021, "bilanzsumme"): 54_061_767.44}


def test_ohne_doppelte_schlusszeile_keine_zahl():
    text = "Bilanz zum 31. Dezember 2019\nA. Anlagevermögen\t1.000,00\nSumme\t2.000,00\n"
    lesung = ga.lies_ocr(text, "Verkehr und Wasser GmbH (VWG) Jahresabschluss 2019 - Beschluss",
                         "Bilanz", 1)
    assert lesung.kennzahlen == [] and "Schlusszeile" in lesung.hinweise[0]
