"""Belegprüfung ohne Modell (council/evidence.py, Plan Vorlagen aufbereiten § 3.4).

Hält fest, was eine erzeugte Aussage über eine Vorlage braucht, um die Seite
zu verlassen — und dass die Prüfung nicht zu streng ist: Risiken, Vorgeschichte
(„beschlossen") und Zahlwörter müssen durchgehen, wenn das Zitat sie trägt."""
from __future__ import annotations

from council import evidence, plan_judge

VORLAGE = ("Beschlussvorschlag: Den folgenden Ausschüssen gehört die nachfolgende Anzahl an beratenden "
           "Mitgliedern an: Ausschuss für Gesundheit und Soziales 5. Die Ausschussmitglieder erhalten ein "
           "Sitzungsgeld in Höhe von 35,00 Euro pro Sitzung. Der Rat hat am 01.11.2021 beschlossen, die "
           "Zahl auf fünf festzulegen. Es bestehen Risiken für die Arbeitsfähigkeit kleiner Ausschüsse.")
ANTRAG = ("Fraktion Bündnis 90/Die Grünen\nÄnderungsantrag zu TOP 13.2\nDie Zahl der beratenden "
          "Mitglieder wird von fünf auf vier reduziert. T e l e f o n 0 4 4 1 – 2 3 5 4 4 3 2")
_S2 = VORLAGE.index("Die Ausschussmitglieder")
QUELLEN = {"V1": {"text": VORLAGE, "pages": [VORLAGE[:_S2], VORLAGE[_S2:]], "document_id": 315090},
           "A1": {"text": ANTRAG, "document_id": 315835}}


def _pruefe(text, quote, source="V1", page=None):
    return evidence.check_statement({"text": text, "quote": quote, "source": source, "page": page}, QUELLEN)


def test_gueltige_aussage_mit_seitenberichtigung():
    ok, grund = _pruefe("Je Sitzung gibt es 35 Euro Sitzungsgeld.",
                        "Sitzungsgeld in Höhe von 35,00 Euro pro Sitzung", page=1)
    assert grund is None and ok["page"] == 2 and ok["source"] == "V1"


def test_zahlwort_gegen_ziffer_und_umgekehrt():
    ok, _ = _pruefe("Statt 5 sollen es 4 beratende Mitglieder sein.",
                    "Mitglieder wird von fünf auf vier reduziert", source="A1")
    assert ok is not None
    nein, grund = _pruefe("Statt fünf sollen es drei sein.",
                          "Mitglieder wird von fünf auf vier reduziert", source="A1")
    assert nein is None and "drei" in grund


def test_wertung_und_ergebnis_nur_mit_beleg():
    assert _pruefe("Es gibt Risiken für kleine Ausschüsse.",
                   "Es bestehen Risiken für die Arbeitsfähigkeit kleiner Ausschüsse")[0] is not None
    assert _pruefe("Der Rat hat die Zahl 2021 schon einmal beschlossen.",
                   "Der Rat hat am 01.11.2021 beschlossen, die Zahl auf fünf festzulegen")[0] is not None
    nein, grund = _pruefe("Das ist erheblich weniger für die Ausschüsse.",
                          "Den folgenden Ausschüssen gehört die nachfolgende Anzahl an beratenden")
    assert nein is None and "Wertung" in grund


def test_erfundenes_zitat_unbekannte_quelle_zu_kurz():
    assert _pruefe("Satz.", "Dieser Wortlaut steht nirgends in der Vorlage, kein Wort davon")[1].startswith("Zitat steht nicht")
    assert _pruefe("Satz.", "Sitzungsgeld in Höhe von 35,00 Euro pro Sitzung", source="A7")[1] == "unbekannte Quelle"
    assert _pruefe("Satz.", "35,00 Euro")[1].startswith("Zitat steht nicht")


def test_ausgabefilter_auch_in_gesperrter_schrift():
    nein, grund = _pruefe("Erreichbar unter T e l e f o n 0 4 4 1 – 2 3 5 4 4 3 2.",
                          "Die Zahl der beratenden Mitglieder wird von fünf auf vier reduziert", source="A1")
    assert nein is None
    assert evidence.satz_sauber("Mehr unter www.example.org") == "Adresse im Satz"
    assert evidence.zusammenziehen("T e l e f o n") == "Telefon"


def test_person_nur_mit_beleg():
    nein, grund = _pruefe("Frau Müller lehnt das ab.", "Den folgenden Ausschüssen gehört die nachfolgende Anzahl")
    assert nein is None


def test_eine_regel_fuer_plaene_und_dossier():
    assert plan_judge.tight is evidence.tight
    assert plan_judge.locate is evidence.locate


def test_verworfenes_landet_mit_grund():
    dropped: list[dict] = []
    out = evidence.check_list([{"text": "x", "quote": "y", "source": "V1"},
                               {"text": "Je Sitzung 35 Euro.", "quote": "Sitzungsgeld in Höhe von 35,00 Euro pro Sitzung",
                                "source": "V1"}], QUELLEN, dropped, "costs")
    assert len(out) == 1 and dropped[0]["field"] == "costs" and dropped[0]["reason"]


def test_seiten_aus_offsets():
    assert evidence.pages_from_offsets("aaaabbbb", [0, 4]) == ["aaaa", "bbbb"]
    assert evidence.pages_from_offsets("x", None) is None


def test_ligatur_ohne_zeichen_und_aufzaehlungspunkt():
    """Quartalsbericht 30.09.2026, Seite 4: Die Ligatur „ti" trägt dort gar kein
    Zeichen („bestägt"). Das Modell schreibt ab, was im PDF zu sehen ist, und
    setzt „•", wo der Text ein Zeichen aus dem privaten Bereich trägt."""
    quelle = {"text": "", "pages": [
        "Die aktuelle Hochrechnung bestägt im Ergebnis den Wirtscha)splan 2026.",
        "Berichtet wird über die Eigenbetriebe:  Abfallwirtschaftsbetrieb  Bäderbetrieb"]}
    assert evidence.locate("Die aktuelle Hochrechnung bestätigt im Ergebnis", quelle, None) == (True, 1)
    assert evidence.locate("Berichtet wird über die Eigenbetriebe: • Abfallwirtschaftsbetrieb • Bäderbetrieb",
                           quelle, 1) == (True, 2)
    # Ziffern bleiben streng: Eine andere Zahl ist kein Beleg.
    assert evidence.locate("Die aktuelle Hochrechnung bestätigt im Ergebnis den Wirtschaftsplan 2025", quelle, None)[0] is False
    # Ohne Seiten genauso.
    assert evidence.locate("Die aktuelle Hochrechnung bestätigt im Ergebnis", {"text": quelle["pages"][0]}, None) == (True, None)
