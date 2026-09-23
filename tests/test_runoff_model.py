"""Die Hochrechnung der Stichwahl — geprüft an der einzigen Stichwahl, die es gibt.

2021, Krogmann (SPD) gegen Fuhrhop (GRÜNE), 133 Wahlbezirke, beide Wahlgänge
als eingefrorene Übersichten unter ``tests/fixtures/wahlabend/stichwahl-2021/``.
Das Modell (``runoff_model``) bekommt den ersten Wahlgang und einen
Teil der Stichwahl — und muss den Ausgang nennen, den es gab.

Was diese Tests halten (docs/plan-stichwahl-spannung.md, §1.4 und S2):

- Nach 30 gezählten Bezirken nennt die Hochrechnung in JEDER Reihenfolge
  den Sieger — zufällig, Urne zuerst, Briefwahl zuerst.
- Nach 15 Bezirken nennt das Modell in keiner Reihenfolge den Falschen als
  WAHRSCHEINLICH: Die Chance des späteren Siegers fällt nie unter 40 %.
  Das ist der Topf-Term: Ohne ihn war das Modell bei „Briefwahl zuerst"
  sicher und falsch. Gemessen: Mit nur 15 Briefwahlbezirken (die Urne ganz
  offen) lag die Hochrechnung 2021 in 1,5 % der Reihenfolgen bei Fuhrhop —
  mit einer Chance von höchstens 60 %, also „offen", nicht „sicher". Der
  Plan schrieb „nie unter 50 %"; seine eigene Messung (§1.4: 96 % richtig
  nach 15 Bezirken bei Brief zuerst) sagt, dass das zu viel verlangt ist.
  Nach 30 Bezirken gilt die 50-Prozent-Schwelle in jeder Reihenfolge.
- Vollständig gezählt ist die Hochrechnung das Ergebnis, „entschieden", und
  es gibt keine Chance mehr — die ist dann keine.

Fällt einer davon, ist das Modell kaputt, nicht der Abend.
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL / "web" / "backend"))

from app.election import mayor_districts, runoff_model  # noqa: E402
from app.election.mayor_districts import MayorDistrict  # noqa: E402

FIX = WURZEL / "tests" / "fixtures" / "wahlabend" / "stichwahl-2021"
SLUGS = ("krogmann", "fuhrhop")


def _lade(name: str) -> tuple[MayorDistrict, ...]:
    return mayor_districts.parse_overview(json.loads((FIX / name).read_text(encoding="utf-8")),
                                          {"krogmann": "", "fuhrhop": ""})


@pytest.fixture(scope="module")
def erster() -> tuple[MayorDistrict, ...]:
    return _lade("uebersicht-223-erster-wahlgang.json")


@pytest.fixture(scope="module")
def stichwahl() -> tuple[MayorDistrict, ...]:
    return _lade("uebersicht-224-stichwahl.json")


def _offen(d: MayorDistrict) -> MayorDistrict:
    from dataclasses import replace

    return replace(d, counted=False, valid_votes=None, voters=None, votes={k: None for k in d.votes})


def _stand(stichwahl, gemeldet: set[int]) -> tuple[MayorDistrict, ...]:
    return tuple(d if d.number in gemeldet else _offen(d) for d in stichwahl)


def _reihenfolgen(stichwahl, seed: int, n_je: int = 200):
    """200 Reihenfolgen je Art, mit festem Seed — der Test ist wiederholbar."""
    rnd = random.Random(seed)
    nummern = [d.number for d in stichwahl]
    brief = {d.number for d in stichwahl if d.postal}
    for art in ("zufällig", "urne-zuerst", "brief-zuerst"):
        for _ in range(n_je):
            r = nummern[:]
            rnd.shuffle(r)
            if art == "urne-zuerst":
                r = [n for n in r if n not in brief] + [n for n in r if n in brief]
            if art == "brief-zuerst":
                r = [n for n in r if n in brief] + [n for n in r if n not in brief]
            yield art, r


def test_vollstaendig_gezaehlt_ist_das_ergebnis(erster, stichwahl):
    p = runoff_model.project(stichwahl, erster, SLUGS)
    assert p is not None
    assert p.projected_votes == {"krogmann": 43493, "fuhrhop": 36949}
    assert p.leader == "krogmann" and p.lead_votes == 6544
    assert p.decided and p.chance_pct is None
    assert p.counted_ballot == 91 and p.counted_postal == 42 and p.open_ballot == p.open_postal == 0
    assert round(p.shares["krogmann"] + p.shares["fuhrhop"], 1) == 100.0


def test_ohne_gezaehlten_bezirk_gibt_es_keine_hochrechnung(erster, stichwahl):
    assert runoff_model.project(_stand(stichwahl, set()), erster, SLUGS) is None


def test_nach_30_bezirken_stimmt_der_sieger_in_jeder_reihenfolge(erster, stichwahl):
    falsch = []
    for art, r in _reihenfolgen(stichwahl, seed=7):
        p = runoff_model.project(_stand(stichwahl, set(r[:30])), erster, SLUGS)
        assert p is not None
        if p.leader != "krogmann":
            falsch.append((art, r[:30]))
    assert not falsch, f"{len(falsch)} Reihenfolgen mit falschem Sieger, z. B. {falsch[0][0]}"


def _chance_des_siegers(p: runoff_model.RunoffProjection) -> int:
    assert p.chance_pct is not None
    return p.chance_pct if p.leader == "krogmann" else 100 - p.chance_pct


def test_nach_15_bezirken_nennt_das_modell_nie_den_falschen_als_wahrscheinlich(erster, stichwahl):
    """Der Topf-Term in Zahlen: Kommt nur die Briefwahl zuerst, führte 2021
    Fuhrhop — und das Modell darf daraus keine Sicherheit machen. Es darf
    ihn vorn sehen (die Urne ist ganz offen, ihr Schwung geliehen), aber nur
    als Münzwurf: Die Chance des späteren Siegers bleibt über 40 %."""
    unter = []
    for art, r in _reihenfolgen(stichwahl, seed=11):
        p = runoff_model.project(_stand(stichwahl, set(r[:15])), erster, SLUGS)
        assert p is not None
        c = _chance_des_siegers(p)
        if c < 40:
            unter.append((art, c))
    assert not unter, f"{len(unter)} Reihenfolgen mit Chance des Siegers unter 40 %: {unter[:3]}"


def test_nach_30_bezirken_liegt_die_chance_des_siegers_nie_unter_50(erster, stichwahl):
    unter = []
    for art, r in _reihenfolgen(stichwahl, seed=13):
        p = runoff_model.project(_stand(stichwahl, set(r[:30])), erster, SLUGS)
        assert p is not None
        if p.decided:
            continue
        c = _chance_des_siegers(p)
        if c < 50:
            unter.append((art, c))
    assert not unter, f"{len(unter)} Reihenfolgen mit Chance des Siegers unter 50 %: {unter[:3]}"


def test_bei_gleichem_schwung_ueberall_trifft_die_hochrechnung_auf_einen_punkt(erster):
    """Die Zusage des Modells, ohne Rauschen geprüft: Eine künstliche
    Stichwahl, in der jeder Bezirk um +3 Punkte schwingt und die Stimmen um
    den Faktor 1,5 wachsen. Nach den ersten 15 Urnenbezirken liegt die
    Hochrechnung auf ±1 Punkt beim Endstand — mehr darf ein Modell, das
    genau diese Annahme macht, nicht danebenliegen."""
    from dataclasses import replace

    synth = []
    for d in erster:
        a, b = d.votes["krogmann"] or 0, d.votes["fuhrhop"] or 0
        n = int(round((a + b) * 1.5))
        share = min(1.0, a / (a + b) + 0.03) if a + b else 0.5
        ka = int(round(share * n))
        synth.append(replace(d, votes={"krogmann": ka, "fuhrhop": n - ka}, valid_votes=n, voters=n))
    voll = runoff_model.project(synth, erster, SLUGS)
    assert voll is not None
    urne = [d.number for d in synth if not d.postal][:15]
    p = runoff_model.project(_stand(tuple(synth), set(urne)), erster, SLUGS)
    assert p is not None
    assert abs(p.shares["krogmann"] - voll.shares["krogmann"]) <= 1.0, (p.shares, voll.shares)
    assert p.counted_ballot == 15 and p.counted_postal == 0


def test_der_naive_blick_haette_2021_bei_briefwahl_zuerst_geirrt(erster, stichwahl):
    """Nicht das Modell, sondern der Grund für das Modell: Wer nur „wer führt"
    liest, hätte 2021 mit den ersten 15 Briefwahlbezirken meist Fuhrhop vorn
    gesehen. Das hält fest, dass die Hochrechnung keinen Zierrat darstellt."""
    naiv_falsch = 0
    laeufe = 0
    for art, r in _reihenfolgen(stichwahl, seed=3):
        if art != "brief-zuerst":
            continue
        laeufe += 1
        p = runoff_model.project(_stand(stichwahl, set(r[:15])), erster, SLUGS)
        assert p is not None
        if p.actual_leader != "krogmann":
            naiv_falsch += 1
    assert laeufe == 200
    assert naiv_falsch / laeufe > 0.3, "Testannahme: die Briefwahl 2021 lag anders als die Urne"


def test_unter_15_bezirken_keine_chance_aber_eine_hochrechnung(erster, stichwahl):
    r = [d.number for d in stichwahl][:14]
    p = runoff_model.project(_stand(stichwahl, set(r)), erster, SLUGS)
    assert p is not None and p.chance_pct is None
    assert any("zu früh" in c for c in p.caveats)
    assert p.shares["krogmann"] > 0
    p15 = runoff_model.project(_stand(stichwahl, set([d.number for d in stichwahl][:15])), erster, SLUGS)
    assert p15 is not None and p15.chance_pct is not None
    assert 0 <= p15.chance_pct <= runoff_model.CHANCE_CAP


def test_entschieden_heisst_der_vorsprung_schlaegt_alles_was_offen_ist(erster, stichwahl):
    """Die Schranke ist Arithmetik: Urnen-Wahlberechtigte plus das 1,6-Fache
    der Briefwahl-Stimmen des ersten Wahlgangs. Wenn sie bricht, ist sie
    falsch — ein Modellrest darf hier nichts zu sagen haben."""
    nummern = [d.number for d in stichwahl]
    # Alles gezählt bis auf einen kleinen Urnenbezirk: entschieden.
    letzter = next(d for d in stichwahl if not d.postal)
    p = runoff_model.project(_stand(stichwahl, set(nummern) - {letzter.number}), erster, SLUGS)
    assert p is not None and p.decided
    assert p.open_votes_max == letzter.eligible
    assert p.actual_lead_votes > p.open_votes_max
    # Nur die Hälfte gezählt: nicht entschieden, aber die Schranke ist die
    # Summe über die offenen Bezirke — Urne nach Wahlberechtigten, Brief
    # nach 1,6 × gültig im ersten Wahlgang.
    halb = set(nummern[::2])
    p2 = runoff_model.project(_stand(stichwahl, halb), erster, SLUGS)
    assert p2 is not None and not p2.decided
    vorher = {d.number: d for d in erster}
    erwartet = 0
    for d in stichwahl:
        if d.number in halb:
            continue
        if d.postal:
            erwartet += int(round(runoff_model.POSTAL_GROWTH_CAP * (vorher[d.number].valid_votes or 0)))
        else:
            erwartet += d.eligible or 0
    assert p2.open_votes_max == erwartet


def test_der_geliehene_schwung_steht_in_den_caveats(erster, stichwahl):
    nur_brief = {d.number for d in stichwahl if d.postal}
    p = runoff_model.project(_stand(stichwahl, nur_brief), erster, SLUGS)
    assert p is not None
    assert any("kein Urnenbezirk" in c for c in p.caveats)
    assert p.counted_ballot == 0 and p.counted_postal == 42
    nur_urne = {d.number for d in stichwahl if not d.postal}
    p2 = runoff_model.project(_stand(stichwahl, nur_urne), erster, SLUGS)
    assert p2 is not None and any("kein Briefwahlbezirk" in c for c in p2.caveats)


def test_die_hochrechnung_trifft_nach_30_bezirken_auf_zwei_punkte(erster, stichwahl):
    """Nicht nur der Sieger, auch die Zahl: 2021 endete es bei 54,1 %. Über
    200 zufällige Reihenfolgen liegt die Hochrechnung nach 30 Bezirken im
    Mittel höchstens zwei Punkte daneben."""
    fehler = []
    for art, r in _reihenfolgen(stichwahl, seed=5):
        if art != "zufällig":
            continue
        p = runoff_model.project(_stand(stichwahl, set(r[:30])), erster, SLUGS)
        assert p is not None
        fehler.append(abs(p.shares["krogmann"] - 54.1))
    assert sum(fehler) / len(fehler) <= 2.0, sum(fehler) / len(fehler)


def test_die_chance_ist_in_knappen_rennen_ehrlich(erster, stichwahl):
    """Kalibrierung: Wie oft stimmt „Chance 9x %"?

    2021 war mit 54 : 46 nicht knapp — fast jede Chance war dort richtig,
    egal wie falsch sie gerechnet war. Deshalb werden die Anteile JEDES
    Bezirks um denselben Betrag verschoben, bis der Endstand zwischen 48
    und 51 % liegt. Die echte Struktur (Streuung zwischen den Bezirken, der
    Unterschied zwischen Urne und Brief) bleibt dabei erhalten.

    Bis 09/2026 fehlte dem Modell die Unsicherheit des Schwungs selbst:
    Dort lag „99 %" in 12 von 100 Fällen daneben, „90–98 %" in 19. Wer
    die Chance anzeigt, darf sie nicht so viel zu sicher anzeigen."""
    from dataclasses import replace

    rnd = random.Random(23)
    oben = [0, 0]      # „99 %": [Anzahl, richtig]
    neunzig = [0, 0]   # 90–98 %
    for delta in (0.030, 0.040, 0.045, 0.055, 0.060):
        wahr = []
        for d in stichwahl:
            n = (d.votes["krogmann"] or 0) + (d.votes["fuhrhop"] or 0)
            a = int(round(max(0, min(n, (d.votes["krogmann"] or 0) - delta * n))))
            wahr.append(replace(d, votes={"krogmann": a, "fuhrhop": n - a}))
        sieger = "krogmann" if sum(d.votes["krogmann"] for d in wahr) > sum(d.votes["fuhrhop"] for d in wahr) else "fuhrhop"
        nummern = [d.number for d in wahr]
        for _ in range(30):
            r = nummern[:]
            rnd.shuffle(r)
            for k in (15, 20, 30, 50, 80, 110):
                p = runoff_model.project(_stand(tuple(wahr), set(r[:k])), erster, SLUGS)
                assert p is not None
                if p.chance_pct is None:
                    continue
                topf = oben if p.chance_pct >= 99 else neunzig if p.chance_pct >= 90 else None
                if topf is not None:
                    topf[0] += 1
                    topf[1] += p.leader == sieger
    assert oben[0] > 50 and neunzig[0] > 50, (oben, neunzig)
    assert oben[1] / oben[0] >= 0.98, f'„99 %" nur in {oben[1]}/{oben[0]} Fällen richtig'
    assert neunzig[1] / neunzig[0] >= 0.85, f'„90–98 %" nur in {neunzig[1]}/{neunzig[0]} Fällen richtig'


# ---------------------------------------------------------------- der Endpunkt

@pytest.fixture
def _frei(monkeypatch):
    from app.election import mayor

    monkeypatch.setenv("FEATURE_FLAGS", "wahlabend")
    mayor.reset()
    yield
    mayor.reset()


def test_die_stichwahl_antwort_traegt_die_hochrechnung(_frei):
    """``GET /api/wahlabend/stichwahl?probe=1&counted=N``: ab dem ersten
    gemeldeten Bezirk steht ``projection`` in der Antwort; bei 133 ist sie
    das Ergebnis und entschieden; unter 15 ohne Chance."""
    from app.routers import wahlabend as router

    ohne = router.stichwahl(probe="1", counted=0)
    assert "projection" not in ohne
    frueh = router.stichwahl(probe="1", counted=10)
    p = frueh["projection"]
    assert p["chance_pct"] is None and not p["decided"]
    assert p["counted_ballot"] + p["counted_postal"] == 10
    assert set(p["shares"]) == {"prange", "rohr"}
    assert any("zu früh" in c for c in p["caveats"]) and any("Modell" in c for c in p["caveats"])
    mitte = router.stichwahl(probe="1", counted=60)
    q = mitte["projection"]
    assert q["chance_pct"] is not None and 0 <= q["chance_pct"] <= 99
    assert q["open_votes_max"] > 0
    voll = router.stichwahl(probe="1", counted=133)
    v = voll["projection"]
    assert v["decided"] and v["chance_pct"] is None
    stimmen = {c["slug"]: c["votes"] for c in voll["candidates"]}
    assert v["projected_votes"] == stimmen
    assert v["leader"] == v["actual_leader"] == "prange"
    # Der erste Wahlgang (keine Stichwahl) trägt keine Hochrechnung.
    assert "projection" not in router.ob_wahl(probe="1", counted=None)


def test_die_aufholrechnung_geht_auf(erster, stichwahl):
    """„Fuhrhop bräuchte 58 % der offenen Stimmen" — geprüft, indem man es
    ausrechnet: Mit genau diesem Anteil an den erwarteten offenen Stimmen
    stünde es am Ende gleich. Entschieden oder fertig gibt es sie nicht."""
    r = [d.number for d in stichwahl]
    p = runoff_model.project(_stand(stichwahl, set(r[:40])), erster, SLUGS)
    assert p is not None and p.trailing is not None and p.needed_share_pct is not None
    vorn = p.actual_leader
    assert p.trailing != vorn
    n = p.open_votes_expected
    aufgeholt = p.needed_share_pct / 100 * n - (1 - p.needed_share_pct / 100) * n
    assert abs(aufgeholt - p.actual_lead_votes) <= 0.001 * n + 1
    assert p.trailing_expected_share_pct is not None and 0 < p.trailing_expected_share_pct < 100
    voll = runoff_model.project(stichwahl, erster, SLUGS)
    assert voll is not None and voll.trailing is None and voll.needed_share_pct is None
