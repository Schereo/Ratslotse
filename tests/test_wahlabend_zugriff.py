"""Die Rangfolge der Wahlbereiche je Liste — und der „Zugriff" auf die Restsitze.

Tims Wunsch (14.09.2026): „Pro Partei die Rangfolge der Wahlbereiche
hervorheben und zwar bei den absoluten Stimmen der Partei im Wahlbereich."
Die Zahlen lagen längst in der Antwort, nur nach Wahlbereich sortiert — wer
„wo ist diese Liste stark?" fragte, musste sechs Karten durchsuchen.

Der zweite Teil ist der interessantere: § 37 Abs. 3 verteilt die Sitze einer
Partei nach Hare/Niemeyer auf ihre Wahlbereiche, und über den letzten Sitz
entscheidet der größte Rest. Diese Reste waren bis 09/2026 lokale Variablen
in ``hare_niemeyer``. Hier steht, dass sie stimmen — gegen den eingefrorenen
Stand von 2026, ohne Netz.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL / "web" / "backend"))

from app.election import archive  # noqa: E402
from app.election.seats import hare_niemeyer, hare_niemeyer_detail  # noqa: E402


@pytest.fixture(scope="module")
def nacht():
    n = archive.night("ratswahl-2026")
    assert n is not None
    return n


# ------------------------------------------------------------------ die Rechnung

def test_die_detail_fassung_rechnet_wie_die_verifizierte():
    """``hare_niemeyer`` steht an fünf Stellen der Zuteilung und ist gegen das
    amtliche Ergebnis 2021 verifiziert. Die Detail-Fassung darf sie erweitern,
    nicht ändern."""
    faelle = [
        ({"D1": 7300, "D2": 6700, "D3": 2400}, 20, None),
        ({1: 4200, 2: 3100}, 9, None),
        ({"a": 10, "b": 10, "c": 10}, 2, None),
        ({"A": 501, "B": 499}, 4, "A"),          # Mehrheitsklausel
        ({"a": 0, "b": 0}, 3, None),             # nichts zu verteilen
        ({"a": 5}, 0, None),
    ]
    for stimmen, sitze, first in faelle:
        assert hare_niemeyer(stimmen, sitze, first) == hare_niemeyer_detail(stimmen, sitze, first)[:2]


def test_die_reste_nennen_den_letzten_und_den_naechsten_sitz():
    # 32.800 Stimmen auf 20 Sitze: die ganzen Quoten ergeben 4+4+4+7 = 19,
    # ein Restsitz bleibt. Die Reste stehen dicht beieinander (D1 14.800,
    # D4 14.400) — genau der Fall, für den die Anzeige gebaut ist.
    sitze, _, rest = hare_niemeyer_detail({"D1": 7300, "D2": 6700, "D3": 6600, "D4": 12200}, 20)
    assert sitze == {"D1": 5, "D2": 4, "D3": 4, "D4": 7}
    assert sorted(rest.values, key=lambda k: -rest.values[k]) == ["D1", "D4", "D2", "D3"]
    assert rest.last == "D1" and rest.next == "D4"
    assert rest.quota == 32800


def test_ohne_restsitze_gibt_es_keinen_letzten():
    _, _, rest = hare_niemeyer_detail({"a": 50, "b": 50}, 2)
    assert rest.last is None
    # Der nächste Sitz ginge trotzdem irgendwohin — bei Gleichstand an den
    # ersten der Eingabe.
    assert rest.next == "a"


def test_die_mehrheitsklausel_zaehlt_als_letzter_sitz():
    """§ 36 Abs. 3 vergibt einen Restsitz vorab. Ist es der einzige, ist er
    auch der letzte — sonst stünde bei einer Mehrheit gar nichts."""
    _, _, rest = hare_niemeyer_detail({"A": 501, "B": 499}, 4, first="A")
    assert rest.last == "A"


# ------------------------------------------------------------------ in der Antwort

def test_jede_liste_traegt_ihre_wahlbereiche_in_rangfolge(nacht):
    for p in nacht["parties"]:
        zeilen = p["areas"]
        assert [z["rank"] for z in zeilen] == list(range(1, len(zeilen) + 1))
        stimmen = [z["votes"] or 0 for z in zeilen]
        assert stimmen == sorted(stimmen, reverse=True), p["short"]
        # Dieselben Zahlen wie in ``areas`` — nur andere Achse, nicht andere Werte.
        for z in zeilen:
            wb = next(a for a in nacht["areas"] if a["number"] == z["area"])
            eintrag = next(ap for ap in wb["parties"] if ap["slug"] == p["slug"])
            assert (z["votes"], z["share_pct"], z["seats"]) == (
                eintrag["votes"], eintrag["share_pct"], eintrag["seats"])


def test_rang_nach_stimmen_nicht_nach_prozent(nacht):
    """Die beiden Achsen fallen wirklich auseinander — sonst wäre der ganze
    Umbau Geschmackssache. Gemessen 2026 bei sieben der sechzehn Listen; bei
    der SPD liegt Wahlbereich III (9.296 Stimmen, 21,9 %) vor II (9.196
    Stimmen, 23,3 %): mehr Stimmen bei kleinerem Anteil, weil III mehr
    Wahlberechtigte hat. Die Sitze folgen den Stimmen (§ 37 Abs. 3)."""
    spd = next(p for p in nacht["parties"] if p["slug"] == "spd")
    dritter, vierter = spd["areas"][2], spd["areas"][3]
    assert (dritter["roman"], vierter["roman"]) == ("III", "II")
    assert dritter["votes"] > vierter["votes"]
    assert dritter["share_pct"] < vierter["share_pct"]
    # Und der stärkste Wahlbereich der SPD ist IV.
    assert spd["areas"][0]["roman"] == "IV" and spd["areas"][0]["votes"] == 12094


def test_der_letzte_und_der_naechste_sitz_stehen_genau_einmal(nacht):
    for p in nacht["parties"]:
        assert sum(1 for z in p["areas"] if z["took_last_seat"]) <= 1
        assert sum(1 for z in p["areas"] if z["next_seat"]) <= 1
        # Wo der letzte Sitz landete, muss auch einer sein.
        for z in p["areas"]:
            if z["took_last_seat"]:
                assert z["seats"] and z["seats"] > 0, p["short"]
    # Die Grünen holen ihren 13. Sitz in Wahlbereich I; der nächste ginge
    # nach III.
    gruene = next(p for p in nacht["parties"] if p["slug"] == "gruene")
    assert next(z["roman"] for z in gruene["areas"] if z["took_last_seat"]) == "I"
    assert next(z["roman"] for z in gruene["areas"] if z["next_seat"]) == "III"


def test_die_reste_teilen_einen_nenner_und_bleiben_darunter(nacht):
    for p in nacht["parties"]:
        reste = [z for z in p["areas"] if z["remainder"] is not None]
        if not reste:
            continue
        nenner = {z["remainder_quota"] for z in reste}
        assert len(nenner) == 1, p["short"]
        quote = reste[0]["remainder_quota"]
        assert quote and all(0 <= (z["remainder"] or 0) < quote for z in reste)


def test_eine_liste_ohne_sitze_hat_keine_reste(nacht):
    ohne = [p for p in nacht["parties"] if not p["seats"]]
    assert ohne, "Testannahme: 2026 sind nicht alle Listen eingezogen"
    for p in ohne:
        assert all(z["remainder"] is None for z in p["areas"])
        assert not any(z["took_last_seat"] or z["next_seat"] for z in p["areas"])


def test_eine_liste_erscheint_nur_in_ihren_wahlbereichen(nacht):
    """Nicht jede Liste tritt überall an — ``areas`` führt dann weniger als
    sechs Zeilen, und keine erfundene."""
    for p in nacht["parties"]:
        gestellt = {a["number"] for a in nacht["areas"]
                    if any(ap["slug"] == p["slug"] for ap in a["parties"])}
        assert {z["area"] for z in p["areas"]} == gestellt, p["short"]
