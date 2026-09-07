"""Der Wahlabend hält jede Meldung aus — Zufallsfälle, Szenarien, Rückfallstufen.

``tests/test_wahlabend.py`` hält fest, dass die Rechnung STIMMT (das amtliche
Ergebnis 2021, alle 50 Mandate). Diese Datei hält fest, dass sie überhaupt
ANTWORTET: Am 13.09.2026 liest der Endpunkt alle 60 Sekunden drei CSVs, die
niemandem hier gehören. Eine Spalte ist leer, eine Zahl negativ, die
Bezirksdatei läuft der Wahlbereichsdatei voraus, eine Liste taucht auf, die es
im Register nicht gibt — und um 18:03 Uhr sehen ein paar tausend Leute zu. Ein
500er wäre an diesem Abend die einzige Antwort, die niemand gebrauchen kann.

Drei Fragen also:

* **Wirft ``compose`` je?** Ein paar tausend zufällige Stände, aus den
  Bausteinen des Parsers gebaut (``AreaRow``/``ListRow``, nicht über CSV-Text),
  mit jeder Zelle in jeder Form, die eine CSV hergibt.
* **Bleibt die Antwort eine Antwort?** 52 Sitze, Anteile in [0, 100], Abstände
  ohne negative Zahlen — auch dann, wenn die Zahlen dahinter Unsinn sind.
* **Greifen die Rückfallstufen?** ``live()`` darf nie werfen: volles Bild →
  Bild ohne Hochrechnung und Abstände → letzter guter Stand mit Vermerk →
  leeres Bild mit Fehlertext.

Was der Zufallslauf gefunden hat, steht als eigener Test darunter — ein
Befund, der einmal aufgetreten ist, soll nicht davon abhängen, dass ein
Zufallszahlengenerator ihn wieder trifft.
"""
from __future__ import annotations

import random
import re
import sys
import threading
import time
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL / "web" / "backend"))
# Wegwerf-Datenbanken und die übrigen Testwerte kommen aus
# `tests/conftest.py` — dort EINMAL je Prozess gesetzt, damit sie nicht an
# der Import-Reihenfolge der Module hängen (siehe die Begründung dort).

from app.election import reference, register, service, votemanager  # noqa: E402
from app.election.votemanager import AreaRow, ListRow, Snapshot  # noqa: E402

FIXTURES = WURZEL / "tests" / "fixtures" / "wahlabend"
REG = register.load()
REF = reference.load()
INDICES = [p.index for p in REG.parties]
#: Die 133 Wahlbezirksnummern von 2026 (dieselben wie 2021).
NUMMERN = sorted(
    n for n in (
        votemanager.district_number(r.name, None)
        for r in votemanager.parse((FIXTURES / "2026-wahlbezirk.csv").read_text(encoding="utf-8"))
    ) if n is not None
)
#: Nummern, die es 2021 nicht gab — die Hochrechnung hat für sie kein Gegenstück.
OHNE_2021 = [701, 750, 899, 999]
UNBESETZT = re.compile(r"^(\d+) Sitz\(e\) bleiben unbesetzt")


# ------------------------------------------------------------------ Bausteine

def _zahl(rnd: random.Random) -> int | None:
    """Eine Zelle, wie sie kommen kann: leer, null, klein, riesig, negativ.

    „Leer heißt nicht null" ist die Grundregel des Parsers; die anderen Formen
    sind Meldefehler, die es am Wahlabend gibt (ein Zahlendreher, ein
    Vorzeichen, eine Spalte, in der die Gesamtsumme der Stadt steht)."""
    w = rnd.random()
    if w < 0.25:
        return None
    if w < 0.35:
        return 0
    if w < 0.82:
        return rnd.randint(0, 3000)
    if w < 0.92:
        return rnd.randint(10**6, 10**12)
    if w < 0.95:
        return 10**18
    return -rnd.randint(1, 5000)


def _liste(rnd: random.Random, index: int, mit_kandidaten: bool) -> ListRow:
    total = _zahl(rnd)
    list_votes = _zahl(rnd) if rnd.random() < 0.7 else None
    cands: dict[int, int] | None = None
    if mit_kandidaten and rnd.random() < 0.6:
        # Auch mehr Plätze, als die Liste im Register hat.
        cands = {k: (_zahl(rnd) or 0) for k in range(1, rnd.randint(1, 14) + 1)}
    candidate_sum = sum(cands.values()) if cands else _zahl(rnd)
    return ListRow(index, total, list_votes, candidate_sum, cands)


def _zeile(rnd: random.Random, name: str, nummer: int | None, erwartet: int,
           indices: list[int], mit_kandidaten: bool, gemeldet: int | None = None) -> AreaRow:
    return AreaRow(
        name=name, number=nummer, reports_expected=erwartet,
        reports_received=rnd.randint(0, max(erwartet, 0) + 1) if gemeldet is None else gemeldet,
        eligible=_zahl(rnd), voters=_zahl(rnd), invalid_ballots=_zahl(rnd),
        valid_ballots=_zahl(rnd), valid_votes=_zahl(rnd),
        lists={} if rnd.random() < 0.05 else {i: _liste(rnd, i, mit_kandidaten) for i in indices},
    )


def _zufallsstand(rnd: random.Random) -> Snapshot:
    """Ein Stand, wie ihn der Votemanager melden könnte — und wie nicht."""
    indices = list(INDICES)
    if rnd.random() < 0.2:
        indices.append(17)  # eine Liste, die im Register nicht antritt
    if rnd.random() < 0.2:
        indices.remove(rnd.choice(indices))  # eine Liste fehlt in der Datei
    mit_kandidaten = rnd.random() < 0.6
    phase = rnd.random()

    areas: list[AreaRow] = []
    for a in REG.areas:
        if rnd.random() < 0.1:
            continue  # dieser Wahlbereich fehlt in der Datei
        nummer = a.number if rnd.random() > 0.05 else rnd.choice([0, 7, 99])
        erwartet = rnd.choice([rnd.randint(0, 24), -3])
        gemeldet = 0 if phase < 0.1 else (max(erwartet, 0) if phase > 0.85 else None)
        areas.append(_zeile(rnd, f"Wahlbereich {a.number}", nummer, erwartet, indices,
                            mit_kandidaten, gemeldet))

    districts: list[AreaRow] = []
    for n in rnd.sample(NUMMERN, rnd.randint(0, len(NUMMERN))):
        districts.append(_zeile(rnd, f"{n} Wahllokal", None, 1, indices, mit_kandidaten))
    for _ in range(rnd.randint(0, 3)):
        n = rnd.choice(OHNE_2021)
        districts.append(_zeile(rnd, f"{n} Nachtrag", None, 1, indices, mit_kandidaten))

    city = [] if rnd.random() < 0.25 else [_zeile(rnd, "Stadt Oldenburg", None, 133, indices, mit_kandidaten)]
    return Snapshot(city, areas, districts, datetime.now(timezone.utc), None, rnd.random() < 0.9, None)


# ------------------------------------------------------------------ Zusicherungen

def _unbesetzt(night) -> int:
    for note in night["notes"]:
        m = UNBESETZT.match(note)
        if m:
            return int(m.group(1))
    return 0


def _im_bereich(wert, hinweis: str) -> None:
    assert wert is None or 0 <= wert <= 100, hinweis


def _pruefe(night) -> None:
    """Was jede Antwort halten muss, egal welche Zahlen hineingingen."""
    assert night["phase"] in ("before", "counting", "complete")
    assert night["progress"]["districts_counted"] >= 0 and night["progress"]["districts_total"] >= 0
    _im_bereich(night["totals"]["turnout_pct"], "Wahlbeteiligung außerhalb 0…100")

    sitze = [p["seats"] for p in night["parties"]]
    unbesetzt = _unbesetzt(night)
    if night["phase"] != "before" and any(s is not None for s in sitze):
        # Stufe 1 verteilt ALLE Sitze; was auf dem Weg nach unten niemanden
        # findet, ist ausdrücklich unbesetzt (§ 36 Abs. 7) und steht in notes.
        assert sum(s or 0 for s in sitze) == REG.seats
        je_liste = sum(ap["seats"] or 0 for a in night["areas"] for ap in a["parties"])
        assert je_liste + unbesetzt == REG.seats
        assert len(night["mandates"]) == REG.seats - unbesetzt
    else:
        assert night["mandates"] == []

    hochgerechnet = [p["projected_seats"] for p in night["parties"]]
    if any(x is not None for x in hochgerechnet):
        assert sum(x or 0 for x in hochgerechnet) == REG.seats

    for p in night["parties"]:
        _im_bereich(p["share_pct"], f"Anteil außerhalb 0…100: {p['slug']}")
        for feld in ("votes_to_next_seat", "votes_to_lose_seat"):
            assert p[feld] is None or p[feld] >= 0, (p["slug"], feld, p[feld])
    for a in night["areas"]:
        _im_bereich(a["totals"]["turnout_pct"], f"Wahlbeteiligung {a['number']}")
        for ap in a["parties"]:
            _im_bereich(ap["share_pct"], f"Anteil {a['number']}/{ap['slug']}")
            for c in ap["candidates"]:
                assert c["votes_to_seat"] is None or c["votes_to_seat"] >= 0
    for m in night["mandates"] + night["projected_mandates"]:
        assert m["kind"] in ("direct", "list", "transfer", "unknown")
    assert all(isinstance(n, str) and n for n in night["notes"])


# ------------------------------------------------------------------ Zufallslauf

def test_compose_haelt_zweitausend_zufaellige_staende_aus():
    """Der eigentliche Zufallslauf. ``margins=False``, weil die Abstände je
    Kandidat*in eine Binärsuche über die ganze Zuteilung sind — für die Masse
    zu teuer; sie bekommen ihre eigene, kleinere Stichprobe."""
    for seed in range(2000):
        snap = _zufallsstand(random.Random(seed))
        try:
            night = service.compose(REG, REF, snap, "live", margins=False)
        except Exception as exc:  # pragma: no cover - der Befund ist der Zweck
            raise AssertionError(f"compose wirft bei seed={seed}: {type(exc).__name__}: {exc}") from exc
        try:
            _pruefe(night)
        except AssertionError as exc:  # pragma: no cover
            raise AssertionError(f"seed={seed}: {exc}") from exc


def test_die_abstaende_halten_die_zufallsfaelle_auch_aus():
    """Dieselben Stände mit Abständen — kleinere Stichprobe, kleinere
    Suchgrenzen (die Grenze sagt nur, ab wann etwas „außer Reichweite" ist)."""
    grenze_partei, grenze_person = service.CAP_PARTY, service.CAP_CANDIDATE
    service.CAP_PARTY = service.CAP_CANDIDATE = 400
    try:
        for seed in range(3000, 3060):
            snap = _zufallsstand(random.Random(seed))
            night = service.compose(REG, REF, snap, "live")
            _pruefe(night)
    finally:
        service.CAP_PARTY, service.CAP_CANDIDATE = grenze_partei, grenze_person


def test_sitze_verschwinden_nicht_bei_widerspruechlicher_meldung():
    """Der Befund des Zufallslaufs (seed 54): Gesamtspalte gefüllt, Listen-
    und Personenspalten auf null.

    Stufe 3 teilt die Sitze einer Wahlbereichsliste im Verhältnis
    Listenstimmen zu Personenstimmen auf (§ 36 Abs. 4). Sind beide null, hatte
    Hare/Niemeyer nichts zu verteilen und gab null zurück — die Sitze der
    Liste waren weg: nicht als Mandat, nicht als unbesetzter Sitz, einfach
    weg. In der Antwort standen 51 von 52 Mandaten, ohne ein Wort dazu.
    Jetzt gehen sie nach Listenreihenfolge (§ 36 Abs. 6) und, wo niemand mehr
    steht, den Weg des Überhangs."""
    from app.election.seats import DistrictList, allocate

    lists = [
        DistrictList("A", 1, 1000, 0, {1: 0, 2: 0, 3: 0}, 3),
        DistrictList("B", 1, 500, 500, {1: 0, 2: 0, 3: 0}, 3),
    ]
    a = allocate(lists, 6)
    assert a.seats_by_party == {"A": 4, "B": 2}
    assert len(a.mandates) + a.vacant == 6
    assert [m.position for m in a.mandates if m.party == "A"] == [1, 2, 3]
    assert a.vacant == 1  # A bekommt vier Sitze und hat drei Bewerber*innen

    # Und dasselbe eine Ebene höher, in der fertigen Antwort.
    snap = _nur_summen(_probe(None), list_votes=False, candidates=False)
    kaputt = _abwandeln(snap, lambda lr: ListRow(lr.index, lr.total, 0, 0, {1: 0}))
    night = service.compose(REG, REF, kaputt, "live", margins=False)
    _pruefe(night)
    assert sum(p["seats"] or 0 for p in night["parties"]) == 52


def test_ein_anteil_von_dreihundert_prozent_ist_keiner():
    """Zwei Dateien, zwei Stände: Die Stimmen einer Liste können größer sein
    als die gültigen Stimmen, die daneben stehen. „380 %" sähe aus wie ein
    Ergebnis; unbekannt ist ehrlicher."""
    assert service._pct(50, 200) == 25.0
    assert service._pct(300, 200) is None
    assert service._pct(-5, 200) is None
    assert service._pct(5, -200) is None
    assert service._pct(5, 0) is None
    assert service._pct(None, 200) is None
    assert service._pct(10**400, 1) is None


def test_ausgezaehlt_aber_ohne_stimmen_ist_keine_sitzverteilung():
    """Eine Schnellmeldung ist gezählt, die Stimmspalten sind leer. „0 Sitze
    für alle" sähe aus wie ein Ergebnis — die Sitze bleiben offen, und die
    Antwort sagt warum."""
    snap = _probe(None)
    leer = _abwandeln(snap, lambda lr: ListRow(lr.index, None, None, None, None))
    night = service.compose(REG, REF, leer, "live", margins=False)
    assert night["phase"] != "before"
    assert all(p["seats"] is None for p in night["parties"])
    assert night["mandates"] == [] and night["projected_mandates"] == []
    assert any("noch keine Stimmen gemeldet" in n for n in night["notes"])
    _pruefe(night)


# ------------------------------------------------------------------ Szenarien

def _probe(counted: int | None) -> Snapshot:
    return service.probe_snapshot(REG, REF, counted)


def _abwandeln(snap: Snapshot, um) -> Snapshot:
    """Denselben Stand mit umgeformten Listen-Zeilen."""
    def zeile(row: AreaRow) -> AreaRow:
        return replace(row, lists={i: um(lr) for i, lr in row.lists.items()})

    return Snapshot([zeile(r) for r in snap.city], [zeile(r) for r in snap.areas],
                    [zeile(r) for r in snap.districts], snap.fetched_at,
                    snap.last_modified, snap.ok, snap.error)


def _nur_summen(snap: Snapshot, *, list_votes: bool, candidates: bool) -> Snapshot:
    """Der Stand mit weggelassenen Spalten — so, wie der Votemanager am
    Sonntag zuerst nur ``D<n>_4`` meldet und die Feinheiten nachreicht."""
    return _abwandeln(snap, lambda lr: ListRow(
        lr.index, lr.total,
        lr.list_votes if list_votes else None,
        lr.candidate_sum if candidates else None,
        lr.candidates if candidates else None,
    ))


def test_sonntag_nur_summen_je_liste():
    """Der erste Stand des Abends: je Liste nur die Gesamtstimmen. Sitze je
    Liste und Wahlbereich ja, Namen nein."""
    night = service.compose(REG, REF, _nur_summen(_probe(None), list_votes=False, candidates=False),
                            "live", margins=False)
    _pruefe(night)
    assert night["phase"] == "complete" and night["person_votes_available"] is False
    assert sum(p["seats"] or 0 for p in night["parties"]) == 52
    assert all(m["kind"] == "unknown" and m["position"] is None and m["name"] is None
               for m in night["mandates"])
    assert any("Personenstimmen liegen noch nicht vor" in n for n in night["notes"])
    # Die Sitze stehen trotzdem bei den Wahlbereichen.
    assert sum(ap["seats"] or 0 for a in night["areas"] for ap in a["parties"]) + _unbesetzt(night) == 52


def test_listenstimmen_ohne_kandidatenspalten_sind_keine_personenstimmen():
    """Regel 3. Kämen die Listenstimmen als Beweis durch, stünde jede*r
    Bewerber*in bei 0 Personenstimmen — die Sitze gingen nach § 36 Abs. 6 der
    Reihe nach an die Liste, mit Namen und allem. Das sähe aus wie ein
    Ergebnis und wäre keins."""
    ohne = service.compose(REG, REF, _nur_summen(_probe(None), list_votes=True, candidates=False),
                           "live", margins=False)
    nur_summen = service.compose(REG, REF, _nur_summen(_probe(None), list_votes=False, candidates=False),
                                 "live", margins=False)
    assert ohne["person_votes_available"] is False
    assert all(m["kind"] == "unknown" for m in ohne["mandates"])
    assert ohne["mandates"] == nur_summen["mandates"]
    for a in ohne["areas"]:
        for ap in a["parties"]:
            assert all(c["votes"] is None and c["elected"] is None for c in ap["candidates"])
    _pruefe(ohne)


def test_kandidatenspalten_ohne_listenstimmen_ergeben_namen():
    """Umgekehrt: Sind die Personenstimmen da, ergeben sich die Listenstimmen
    aus Gesamt − Σ Personen. Dann gibt es Namen."""
    night = service.compose(REG, REF, _nur_summen(_probe(None), list_votes=False, candidates=True),
                            "live", margins=False)
    _pruefe(night)
    assert night["person_votes_available"] is True
    assert len(night["mandates"]) + _unbesetzt(night) == 52
    assert all(m["name"] and m["position"] for m in night["mandates"])
    assert {m["kind"] for m in night["mandates"]} <= {"direct", "list", "transfer"}


def test_stadtdatei_leer_die_wahlbereiche_voll():
    """Die Stadtzeile kommt zuletzt. Bis dahin summieren die sechs
    Wahlbereiche — sonst stünde die Stadt auf null, während ihre Teile
    ausgezählt sind."""
    voll = _probe(None)
    ohne_stadt = Snapshot([], voll.areas, voll.districts, voll.fetched_at,
                          voll.last_modified, voll.ok, voll.error)
    a = service.compose(REG, REF, voll, "live", margins=False)
    b = service.compose(REG, REF, ohne_stadt, "live", margins=False)
    _pruefe(b)
    assert any("Stadtzeile" in n for n in b["notes"])
    assert b["totals"] == a["totals"]
    assert [p["votes"] for p in b["parties"]] == [p["votes"] for p in a["parties"]]
    assert [p["share_pct"] for p in b["parties"]] == [p["share_pct"] for p in a["parties"]]


def test_wahlbereich_wird_aus_seinen_bezirken_summiert():
    """Die Bezirksdatei kann der Wahlbereichsdatei vorauslaufen. Dann wird der
    Wahlbereich aus seinen Bezirken summiert, statt auf null zu stehen."""
    voll = _probe(60)
    hinkend = Snapshot(voll.city, [service._blank(r) if r.number == 3 else r for r in voll.areas],
                       voll.districts, voll.fetched_at, voll.last_modified, voll.ok, voll.error)
    a = service.compose(REG, REF, voll, "live", margins=False)
    b = service.compose(REG, REF, hinkend, "live", margins=False)
    _pruefe(b)
    assert any("Wahlbereich III aus den Bezirken summiert" in n for n in b["notes"])
    drei_a = next(x for x in a["areas"] if x["number"] == 3)
    drei_b = next(x for x in b["areas"] if x["number"] == 3)
    assert drei_b["totals"] == drei_a["totals"]
    assert drei_b["districts_total"] == drei_a["districts_total"] == 21
    assert [p["votes"] for p in drei_b["parties"]] == [p["votes"] for p in drei_a["parties"]]


def test_ohne_bezirksdatei_zaehlt_es_weiter_nur_ohne_hochrechnung():
    """Der umgekehrte Fall: Die Wahlbereiche sind da, die Bezirksdatei fehlt.
    Die Hochrechnung braucht die Bezirke (sie skaliert jeden offenen mit
    seinem Ergebnis von 2021) — die Zählung braucht sie nicht."""
    voll = _probe(60)
    ohne = Snapshot(voll.city, voll.areas, [], voll.fetched_at, voll.last_modified, voll.ok, voll.error)
    night = service.compose(REG, REF, ohne, "live", margins=False)
    _pruefe(night)
    assert night["phase"] == "counting"
    assert sum(p["seats"] or 0 for p in night["parties"]) == 52
    assert all(p["projected_seats"] is None for p in night["parties"])
    assert night["projected_mandates"] == []


def test_ein_wahlbereich_gemeldet_fuenf_nicht():
    """Ein Wahlbereich ist durch, die anderen fünf haben nichts. Die Sitze
    rechnen trotzdem, und die Hochrechnung nimmt für die stillen Wahlbereiche
    den stadtweiten Swing (``projection.py``)."""
    voll = _probe(None)
    areas = [r if r.number == 1 else service._blank(r) for r in voll.areas]
    districts = [d if votemanager.area_of_district(votemanager.district_number(d.name, None) or 0) == 1
                 else service._blank(d) for d in voll.districts]
    snap = Snapshot([], areas, districts, voll.fetched_at, voll.last_modified, voll.ok, voll.error)
    night = service.compose(REG, REF, snap, "live", margins=False)
    _pruefe(night)
    assert night["phase"] == "counting"
    assert sum(p["seats"] or 0 for p in night["parties"]) == 52
    assert sum(p["projected_seats"] or 0 for p in night["parties"]) == 52
    eins = next(a for a in night["areas"] if a["number"] == 1)
    assert eins["districts_counted"] == eins["districts_total"] == 22
    assert all(a["districts_counted"] == 0 for a in night["areas"] if a["number"] != 1)


# ------------------------------------------------------------------ Rückfallstufen

def _stand(counted: int | None = 60):
    snap = _probe(counted)

    def hol(force: bool = False) -> Snapshot:
        return snap

    return hol


@pytest.fixture(autouse=True)
def _sauber():
    service.reset()
    yield
    service.reset()


def test_stufe_b_bild_ohne_hochrechnung_und_abstaende(monkeypatch):
    """Bricht im vollen Bild etwas, kommt dasselbe ohne Hochrechnung und ohne
    Abstände — und sagt es in ``notes``. Die ausgezählten Zahlen stimmen."""
    monkeypatch.setattr(votemanager, "fetch", _stand())

    def bumm(*a, **k):
        raise ZeroDivisionError("Abstand geplatzt")

    monkeypatch.setattr(service, "party_seat_margins", bumm)
    night = service.live()
    _pruefe(night)
    assert service.NOTE_REDUCED in night["notes"]
    assert sum(p["seats"] or 0 for p in night["parties"]) == 52
    assert all(p["votes_to_next_seat"] is None and p["projected_seats"] is None
               for p in night["parties"])
    assert night["source"]["ok"] is True  # der Abruf war ja in Ordnung


def test_stufe_c_haelt_den_letzten_guten_stand_mit_vermerk(monkeypatch):
    """Fällt der Abruf aus, bleibt der letzte gute Stand stehen — aber mit
    ``source.error`` und einem Vermerk. Ein eingefrorener Stand ohne Hinweis
    sähe aus wie einer, der sich nur nicht mehr ändert."""
    monkeypatch.setattr(votemanager, "fetch", _stand())
    gut = service.live()
    assert gut["source"]["ok"] is True and service.NOTE_STALE not in gut["notes"]

    def bumm(force: bool = False):
        raise RuntimeError("Votemanager weg")

    monkeypatch.setattr(votemanager, "fetch", bumm)
    service._refresh()  # das tut sonst der Hintergrund-Thread
    assert service._building is False
    night = service.live()
    _pruefe(night)
    assert night["source"]["ok"] is False and "Votemanager weg" in (night["source"]["error"] or "")
    assert service.NOTE_STALE in night["notes"]
    assert [p["seats"] for p in night["parties"]] == [p["seats"] for p in gut["parties"]]

    service._refresh()  # zweimal denselben Vermerk gibt es nicht
    assert service.live()["notes"].count(service.NOTE_STALE) == 1


def test_stufe_d_ohne_jeden_stand_ein_bild_vor_der_auszaehlung(monkeypatch):
    """Gibt es noch keinen guten Stand, kommt das Bild der Phase „before" —
    mit Listen, Namen und Farben aus dem Register und dem Fehler im Kopf."""
    def bumm(force: bool = False):
        raise RuntimeError("Votemanager weg")

    monkeypatch.setattr(votemanager, "fetch", bumm)
    night = service.live()
    _pruefe(night)
    assert night["phase"] == "before" and night["source"]["ok"] is False
    assert "Votemanager weg" in (night["source"]["error"] or "")
    assert service.NOTE_EMPTY in night["notes"]
    assert len(night["parties"]) == 16 and len(night["areas"]) == 6
    assert night["mandates"] == [] and night["history"] == []


def test_letzte_reissleine_auch_ohne_register(monkeypatch):
    """Selbst wenn das Register nicht lesbar ist, kommt eine gültige Antwort.
    Leere Listen sind wenig — ein 500er wäre weniger."""
    def bumm(*a, **k):
        raise OSError("kandidaten.json weg")

    monkeypatch.setattr(votemanager, "fetch", bumm)
    monkeypatch.setattr(service, "load_register", bumm)
    night = service.live()
    _pruefe(night)
    assert night["parties"] == [] and night["areas"] == []
    assert night["election"]["seats"] == 52 and night["phase"] == "before"
    assert service.NOTE_EMPTY in night["notes"] and night["source"]["ok"] is False


def test_ansturm_beim_ersten_aufruf_baut_nur_einmal(monkeypatch):
    """Cache leer, Schalter frisch umgelegt, viele Zuschauer: Ohne Wartezimmer
    bauen alle gleichzeitig dasselbe Bild. Genau einer baut, die anderen
    warten auf sein Ergebnis."""
    monkeypatch.setattr(votemanager, "fetch", _stand())
    laeufe: list[float] = []
    echt = service.compose

    def langsam(*a, **k):
        laeufe.append(time.monotonic())
        time.sleep(0.3)
        return echt(*a, **k)

    monkeypatch.setattr(service, "compose", langsam)
    ergebnisse: list[dict] = []
    threads = [threading.Thread(target=lambda: ergebnisse.append(service.live())) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    assert len(laeufe) == 1, f"{len(laeufe)} Bauläufe statt einem"
    assert len(ergebnisse) == 8
    assert all(e is ergebnisse[0] for e in ergebnisse)


def test_wartezimmer_gibt_nach_der_frist_ein_leeres_bild(monkeypatch):
    """Wartet der erste Aufruf zu lange, wird nicht doppelt gebaut, sondern
    Stufe (d) ausgeliefert — die Seite antwortet lieber leer als gar nicht."""
    monkeypatch.setattr(service, "BUILD_WAIT_SECONDS", 0.2)
    haenger = threading.Event()
    laeuft = threading.Event()

    def langsam(force: bool = False):
        laeuft.set()
        haenger.wait(5)
        return _probe(60)

    monkeypatch.setattr(votemanager, "fetch", langsam)
    bauer = threading.Thread(target=service.live)
    bauer.start()
    try:
        assert laeuft.wait(10), "der Bauer ist nicht losgelaufen"
        night = service.live()
        _pruefe(night)
        assert night["phase"] == "before" and service.NOTE_EMPTY in night["notes"]
    finally:
        haenger.set()
        bauer.join(timeout=30)


# ------------------------------------------------------------------ Endpunkt

@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    service.reset()
    yield TestClient(app)
    service.reset()


def test_der_endpunkt_antwortet_auf_jeden_zufallsstand_mit_200(client, monkeypatch):
    """Dieselben Zufallsstände durch FastAPI: Ein Pflichtfeld, das ``None``
    wird, ist dort kein leeres Feld, sondern ein 500er."""
    monkeypatch.setenv("FEATURE_FLAGS", "wahlabend")
    grenze_partei, grenze_person = service.CAP_PARTY, service.CAP_CANDIDATE
    service.CAP_PARTY = service.CAP_CANDIDATE = 300
    try:
        for seed in range(4000, 4030):
            snap = _zufallsstand(random.Random(seed))
            monkeypatch.setattr(votemanager, "fetch", lambda force=False, s=snap: s)
            service.reset()
            r = client.get("/api/wahlabend")
            assert r.status_code == 200, (seed, r.text[:400])
            _pruefe(r.json())
    finally:
        service.CAP_PARTY, service.CAP_CANDIDATE = grenze_partei, grenze_person


def test_der_endpunkt_antwortet_auch_wenn_gar_nichts_geht(client, monkeypatch):
    monkeypatch.setenv("FEATURE_FLAGS", "wahlabend")

    def bumm(*a, **k):
        raise RuntimeError("alles weg")

    monkeypatch.setattr(votemanager, "fetch", bumm)
    monkeypatch.setattr(service, "load_register", bumm)
    r = client.get("/api/wahlabend")
    assert r.status_code == 200, r.text[:400]
    assert r.json()["source"]["ok"] is False
