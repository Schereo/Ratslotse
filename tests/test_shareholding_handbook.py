"""Das Handbuch Beteiligungen in KI-Frage und Lotti (council/shareholding_handbook.py).

Drei Dinge halten diese Tests fest:

1. **Die Auslöser** — in beide Richtungen. Die Regelfragen ziehen die
   richtige Regel; die Nachbarfragen („Beteiligung der Öffentlichkeit",
   „Ist die Ratssitzung öffentlich?") ziehen nichts.
2. **Die Belege** — jede Regel nennt Seiten, die es in der Broschüre gibt,
   und der Baustein sagt, dass er kein Prüfergebnis ist.
3. **Die Ratsperiode** — eine Besetzung aus dem Bericht 2024 ist seit dem
   01.11.2026 die der vorigen Periode.
"""
from __future__ import annotations

import re
from datetime import date

import pytest

from council import assistant, qa, shareholding_handbook as hb
from council.geld import handbook as facette

# ---------------------------------------------------------------------------
# 1. Auslöser
# ---------------------------------------------------------------------------

#: Frage → die Regel, die zuerst kommen muss.
ZIEHT = [
    ("Was macht ein Aufsichtsrat?", "supervisory_board"),
    ("Darf der Rat dem Aufsichtsrat der VWG etwas vorschreiben?", "supervisory_board"),
    ("Wer sitzt im Aufsichtsrat der GSG?", "appointment"),
    ("Wer entsendet die Mitglieder in die Gesellschafterversammlung?", "appointment"),
    ("Was bekommt man als Aufsichtsrat bei der Weser-Ems Halle?", "compensation"),
    ("Wie hoch ist die Vergütung der Geschäftsführung beim Klinikum?", "compensation"),
    ("Wer bestimmt eigentlich beim Klinikum?", "governance"),
    ("Welchen Einfluss hat die Stadt auf die VWG?", "governance"),
    ("Was ist die Gesellschafterversammlung?", "governance"),
    ("Wann muss der Beteiligungsbericht erscheinen?", "reporting"),
    ("Wie oft berichtet die VWG über ihren Wirtschaftsplan?", "reporting"),
    ("Was ist ein Quartalsbericht?", "reporting"),
    ("Wer prüft den Jahresabschluss der Bäderbetriebsgesellschaft?", "audit"),
    ("Was ist ein Feststellungsvermerk?", "audit"),
    ("Sind die Sitzungen der GSG öffentlich?", "transparency"),
    ("Was ist der Corporate Governance Kodex der Stadt?", "scope"),
    ("Was macht das Beteiligungsmanagement?", "holding_management"),
    ("Wer bestellt die Geschäftsführung der OTM?", "management_board"),
    ("Was passiert bei einem Interessenkonflikt im Aufsichtsrat?", "conflicts"),
]

#: Die Nachbarfragen, an denen die Wörter am ehesten fehlfeuern.
ZIEHT_NICHT = [
    "Ist die Ratssitzung am Montag öffentlich?",
    "Wie läuft die Beteiligung der Öffentlichkeit zum Bebauungsplan 831?",
    "Wann erscheint der nächste Haushaltsplan?",
    "Wie viel verdient der Oberbürgermeister?",
    "Wie ist der Stand beim Stadion?",
    "Wer prüft die Bauanträge?",
    "Wie hoch war die Hochrechnung am Wahlabend?",
    "Gibt es einen Interessenkonflikt bei Ratsmitglied Müller?",
]


@pytest.mark.parametrize("frage,erste", ZIEHT)
def test_regelfragen_ziehen_ihre_regel(frage, erste):
    regeln = hb.find(frage)
    assert regeln and regeln[0].key == erste, (frage, [r.key for r in regeln])


@pytest.mark.parametrize("frage", ZIEHT_NICHT)
def test_nachbarfragen_ziehen_nichts(frage):
    assert hb.find(frage) == [], (frage, [r.key for r in hb.find(frage)])


@pytest.mark.parametrize("frage,erste", ZIEHT)
def test_facette_kommt_ueber_geld_kontext(frage, erste):
    """Über ``qa.geld_facetten`` erreicht das Handbuch KI-Frage, Lotti,
    Lottis Werkzeuge, MCP und Recherche zugleich."""
    assert "handbook" in qa.geld_facetten(frage, "topic"), frage


def test_lotti_darf_das_handbuch_auch_ausserhalb_des_haushalts():
    assert "handbook" in assistant.GELD_AUSSERHALB


def test_hoechstens_zwei_regeln_je_frage():
    frage = ("Wer sitzt im Aufsichtsrat der GSG, was verdient man da, und ist das "
             "öffentlich?")
    assert len(hb.find(frage)) == hb.MAX_RULES


def test_facette_waehlt_an_der_rohen_frage():
    """Die Expansion streut fremde Wörter ein; die Facette bekommt deshalb
    die Wörter der ROHEN Frage (``qa.geld_kontext``)."""
    daten = qa.geld_kontext(_KeinStore(), "Was macht ein Aufsichtsrat?",
                            "Aufsichtsrat Vergütung Aufwandsentschädigung Sitzungsgeld")
    assert [r["key"] for r in daten["handbook"]["rules"]][0] == "supervisory_board"


class _KeinStore:
    """Ein Store, der für jede andere Facette nichts liefert."""

    def __getattr__(self, name):
        if name == "handbook_context":
            return lambda terms, year=None: hb.context(" ".join(terms))
        return lambda *a, **k: None


# ---------------------------------------------------------------------------
# 2. Belege und Grenzen
# ---------------------------------------------------------------------------

#: Die Seiten der Broschüre, auf denen Text steht (40 S., „Eigene Notizen"
#: und Trennseiten abgezogen).
_TEXTSEITEN = set(range(6, 9)) | {10} | set(range(13, 29)) | set(range(31, 36)) | {38}


@pytest.mark.parametrize("regel", hb.RULES, ids=lambda r: r.key)
def test_jede_regel_nennt_seiten_mit_text(regel):
    seiten: set[int] = set()
    for von, bis in re.findall(r"(\d+)(?:–(\d+))?", regel.pages):
        seiten |= set(range(int(von), int(bis or von) + 1))
    assert seiten and seiten <= _TEXTSEITEN, (regel.key, regel.pages)


@pytest.mark.parametrize("regel", hb.RULES, ids=lambda r: r.key)
def test_jede_regel_hat_einen_ausloeser(regel):
    assert regel.trigger or regel.trigger_with_company


def test_keine_selbstauskunft_in_den_texten():
    for regel in hb.RULES:
        assert "Ratslotse" not in regel.text, regel.key


def test_baustein_sagt_was_er_nicht_ist_und_bleibt_unter_der_grenze():
    laengster = 0
    for a in hb.RULES:
        for b in hb.RULES:
            if a is b:
                continue
            daten = {"rules": [{"key": r.key, "title": r.title, "text": r.text,
                                "pages": r.pages} for r in (a, b)],
                     "beleg": hb.source()}
            laengster = max(laengster, len(facette.block(daten)))
    assert laengster <= facette.FACETTE.grenze, laengster
    text = facette.block(hb.context("Was macht ein Aufsichtsrat?"))
    assert "keine Prüfergebnisse" in text and "unterstelle niemandem" in text
    assert "Handbuch Beteiligungen der Stadt Oldenburg" in text


def test_beleg_traegt_den_ratsbeschluss_und_die_adresse():
    b = hb.source()
    assert b["url"].startswith("https://www.oldenburg.de/") and b["url"].endswith(".pdf")
    assert hb.ADOPTED_TEMPLATE in b["citation"]
    belege = qa.geld_belege({"handbook": hb.context("Was macht ein Aufsichtsrat?")})
    assert belege and belege[0]["url"] == hb.SOURCE_URL


# ---------------------------------------------------------------------------
# 3. Ratsperiode
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("tag,beginn,ende", [
    (date(2024, 12, 31), date(2021, 11, 1), date(2026, 10, 31)),
    (date(2026, 10, 31), date(2021, 11, 1), date(2026, 10, 31)),
    (date(2026, 11, 1), date(2026, 11, 1), date(2031, 10, 31)),
    (date(2019, 5, 1), date(2016, 11, 1), date(2021, 10, 31)),
])
def test_ratsperiode(tag, beginn, ende):
    assert hb.council_term(tag) == (beginn, ende)


def test_besetzung_2024_ist_seit_november_2026_die_der_vorigen_periode():
    vorher = hb.board_term_note(2024, today=date(2026, 10, 31))
    nachher = hb.board_term_note(2024, today=date(2026, 11, 23))
    assert vorher["term_label"] == nachher["term_label"] == "2021–2026"
    assert not vorher["term_ended"] and nachher["term_ended"]
