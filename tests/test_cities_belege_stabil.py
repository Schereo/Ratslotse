"""Beschluss-Belege über Sitzung und Punkt — nicht über die Zeilennummer.

Am 03.10.2026 gemessen: Alle 1.294 Beschluss-Belege der Städte-Urteile
trugen eine Zeilennummer der dev-Datenbank (322 bis 9.441). Prod zählt ab
10.983 — keiner löste dort auf, 48 von 207 Ideen standen ohne Beleg da.
Diese Tests halten die drei Teile der Reparatur fest: die Kennung, die
Auflösung (alte Form weiter lesbar) und das Umschlüsseln OHNE Neu-Urteile.
"""
from __future__ import annotations

import pytest

from council.cities import evidence as ev
from council.cities import fit as fit_modul
from council.cities.annotators import get
from council.cities.evidence import (BESCHLUSS_PRAEFIX, beschluss_kennung, beschluss_zu,
                                     vorlage_hinter)
from tests import test_cities_fit as _fit
from tests.test_cities_fit import MODELL, _antwort

# Dieselben Fixtures wie bei `fit`: ein Oldenburger Wärmeplan-Beschluss
# (Sitzung 7, Punkt 4) und eine Osnabrücker Vorlage, die ihn als Beleg findet.
rats = _fit.rats
cities = _fit.cities
fester_vektor = _fit.fester_vektor
feste_suchbegriffe = _fit.feste_suchbegriffe


def _beschluss(rats, id_, ksinr, position, item, titel, kvonr=None, kind="decision"):
    with rats._conn:
        rats._conn.execute(
            "INSERT INTO council_decisions (id, ksinr, position, kind, item_number, title, "
            "  outcome, kvonr) VALUES (?, ?, ?, ?, ?, ?, 'accepted', ?)",
            (id_, ksinr, position, kind, item, titel, kvonr))


# ------------------------------------------------------------------ Kennung

def test_die_kennung_kommt_aus_sitzung_und_punkt(rats):
    b = rats.get_decision(1)
    assert beschluss_kennung(b, rats.get_decisions(7)) == "oldenburg:decision:7:4"


def test_zwei_beschluesse_eines_punkts_werden_durchgezaehlt(rats):
    """41 von 8.674 Punkten auf Prod tragen zwei Beschlüsse."""
    _beschluss(rats, 2, 7, 2, "4", "Wärmeplanung — Änderungsantrag")
    alle = rats.get_decisions(7)
    assert beschluss_kennung(rats.get_decision(1), alle) == "oldenburg:decision:7:4"
    assert beschluss_kennung(rats.get_decision(2), alle) == "oldenburg:decision:7:4#2"
    assert beschluss_zu(rats, "oldenburg:decision:7:4#2")["id"] == 2


def test_die_zeilennummer_ist_egal(rats):
    """Derselbe Beschluss unter einer anderen Zeile — so steht er auf Prod."""
    with rats._conn:
        rats._conn.execute("UPDATE council_decisions SET id = 12001 WHERE id = 1")
    assert beschluss_zu(rats, "oldenburg:decision:7:4")["id"] == 12001


def test_die_alte_form_bleibt_lesbar(rats):
    """Bis der Bestand umgeschlüsselt ist (und in der Datenbank, aus der sie stammt)."""
    assert beschluss_zu(rats, "oldenburg:decision:1")["title"] == "Kommunale Wärmeplanung"
    assert beschluss_zu(rats, "oldenburg:decision:999999") is None


def test_eine_andere_schreibweise_des_punkts_findet_ihn(rats):
    assert beschluss_zu(rats, "oldenburg:decision:7:Ö 4")["id"] == 1


def test_fehlt_der_beschluss_traegt_die_vorlage_des_punkts(rats):
    """32 von 863 Belegen fanden auf Prod keinen Beschluss — die Tagesordnung
    kennt den Punkt aber, samt Vorlage (das Protokoll wurde anders gelesen)."""
    with rats._conn:
        rats._conn.execute(
            "INSERT INTO council_agenda_items (ksinr, item_number, title, kvonr) "
            "VALUES (7, 'Ö 11.1', 'Radverkehr - Bericht', 4711)")
    kennung = "oldenburg:decision:7:11.1"
    assert beschluss_zu(rats, kennung) is None
    assert vorlage_hinter(rats, kennung) == (4711, "Radverkehr - Bericht")
    beleg = ev._aus_beschluss(rats, kennung, None)
    assert beleg.id == kennung, "das Urteil muss den Beleg unter seiner Kennung wiederfinden"
    assert beleg.title and beleg.outcome == "accepted"


def test_die_karte_loest_beide_formen_auf(rats):
    """Der Endpunkt der Ideen-Karte — dieselbe Auflösung wie im Cron."""
    import sys
    from pathlib import Path

    backend = Path(__file__).resolve().parents[1] / "web" / "backend"
    if str(backend) not in sys.path:
        sys.path.insert(0, str(backend))
    from app.routers.council import _belege_aufloesen

    with rats._conn:
        rats._conn.execute("UPDATE council_decisions SET id = 12001 WHERE id = 1")
    belege = _belege_aufloesen(rats, ["oldenburg:decision:7:4"])
    assert [b["decision_id"] for b in belege] == [12001]
    assert belege[0]["title"] == "Kommunale Wärmeplanung"
    # Die alte dev-Zeilennummer gibt es auf Prod nicht: keine Zeile, kein Fehler.
    assert _belege_aufloesen(rats, ["oldenburg:decision:1"]) == []


# ------------------------------------------------------- Belege im Cron-Lauf

@pytest.fixture()
def beschluss_arm(rats, monkeypatch):
    """Der Beschluss-Arm findet den Oldenburger Wärmeplan-Beschluss."""
    with rats._conn:
        rats._conn.execute("UPDATE council_decisions SET simple_summary = "
                           "'Der Rat beschließt Wärmenetz und Wärmeplan.' WHERE id = 1")
    monkeypatch.setattr(rats, "search_decisions_fts", lambda q, limit=40: [(1, 1.0, "")])
    return rats


def test_der_beschluss_arm_vergibt_die_stabile_kennung(cities, beschluss_arm):
    klasse = cities.annotations_for("classify", "2")["os:p:1"]
    belege = ev.evidence_for(cities, beschluss_arm, cities.paper("os:p:1"), klasse, MODELL)
    beschluesse = [b.id for b in belege if b.kind == "decision"]
    assert beschluesse == ["oldenburg:decision:7:4"]


def test_umschluesseln_loest_keine_neu_urteile_aus(cities, beschluss_arm, monkeypatch):
    """Die Kostenfalle: Der Quell-Hash von `fit` trägt die Beleg-Kennungen.

    Ein Bestand, dessen Urteile unter der alten Kennung entstanden sind, sieht
    nach dem Umschlüsseln für einen Bestandslauf aus wie „Belege geändert" —
    auf Prod rund 12.000 Urteile, 14 $. Der Wochenlauf (`schlank`) fragt gar
    nicht erst; ein Bestandslauf erst nach `nur_hashes`.
    """
    aufrufe: list[int] = []
    ann = get("fit")

    # 1. Der Stand von vorher: Urteil unter der Zeilennummer.
    echt = ev.beschluss_kennung
    monkeypatch.setattr(ev, "beschluss_kennung",
                        lambda b, geschwister=None: f"{BESCHLUSS_PRAEFIX}{b['id']}")
    monkeypatch.setattr(fit_modul.llm, "chat_complete", lambda **kw: (
        aufrufe.append(1), _antwort({"status": "present", "confidence": "high",
                                     "evidence": ["oldenburg:decision:1"],
                                     "reason": "Beschlossen."}))[1])
    assert fit_modul.run(cities, beschluss_arm, ann, MODELL, workers=1)["annotated"] == 1
    monkeypatch.setattr(ev, "beschluss_kennung", echt)

    # 2. Umschlüsseln.
    stand = cities.rekey_evidence({"oldenburg:decision:1": "oldenburg:decision:7:4"})
    assert stand == {"rows": 1, "keys": 1, "unknown": 0}
    assert cities.rekey_evidence({"oldenburg:decision:1": "oldenburg:decision:7:4"})["rows"] == 0
    urteil = cities.annotation("paper", "os:p:1", "fit", ann.version)["payload"]
    assert urteil["evidence"] == ["oldenburg:decision:7:4"]

    vorher = len(aufrufe)
    # 3. Der Wochenlauf urteilt nicht neu — der Beleg-Pool allein öffnet nichts.
    assert fit_modul.run(cities, beschluss_arm, ann, MODELL, workers=1,
                         schlank=True)["annotated"] == 0
    # 4. Die Hashes übernehmen — ohne einen einzigen Urteils-Aufruf …
    assert fit_modul.run(cities, beschluss_arm, ann, MODELL, workers=1,
                         nur_hashes=True)["hashes_adopted"] == 1
    # 5. … und danach findet auch ein Bestandslauf nichts mehr.
    assert fit_modul.run(cities, beschluss_arm, ann, MODELL, workers=1)["annotated"] == 0
    assert len(aufrufe) == vorher, "Umschlüsseln darf kein Urteil neu fällen"
    assert cities.annotation("paper", "os:p:1", "fit", ann.version)["payload"]["status"] \
        == "present"


def test_ohne_embedding_uebernimmt_nur_hashes_nichts(cities, beschluss_arm, monkeypatch):
    """Die Hashes stehen auf den gerade gesammelten Belegen. Fehlt das
    Embedding-Modell, sind das verarmte Belege — übernommen sähe danach jedes
    Urteil „aktuell" aus. Also Abbruch statt Übernahme."""
    ann = get("fit")
    monkeypatch.setattr(fit_modul.llm, "chat_complete", lambda **kw: _antwort(
        {"status": "missing", "confidence": "high", "evidence": [], "reason": "."}))
    fit_modul.run(cities, beschluss_arm, ann, MODELL, workers=1)
    vorher = cities.source_hashes("paper", "fit", ann.version)

    def kaputt(text):
        raise RuntimeError("fastembed: Modell fehlt")

    monkeypatch.setattr(ev, "_embed_eins", kaputt)
    with pytest.raises(fit_modul.LaufAbbruch, match="neighbor"):
        fit_modul.run(cities, beschluss_arm, ann, MODELL, workers=1, nur_hashes=True)
    assert cities.source_hashes("paper", "fit", ann.version) == vorher


def test_ohne_hash_uebernahme_wuerde_ein_bestandslauf_neu_urteilen(cities, beschluss_arm,
                                                                   monkeypatch):
    """Die Gegenprobe zum Test oben: Ohne `nur_hashes` IST es die Falle."""
    ann = get("fit")
    echt = ev.beschluss_kennung
    monkeypatch.setattr(ev, "beschluss_kennung",
                        lambda b, geschwister=None: f"{BESCHLUSS_PRAEFIX}{b['id']}")
    monkeypatch.setattr(fit_modul.llm, "chat_complete", lambda **kw: _antwort(
        {"status": "missing", "confidence": "high", "evidence": [], "reason": "."}))
    fit_modul.run(cities, beschluss_arm, ann, MODELL, workers=1)
    monkeypatch.setattr(ev, "beschluss_kennung", echt)
    assert fit_modul.run(cities, beschluss_arm, ann, MODELL, workers=1)["annotated"] == 1


def test_der_schlanke_lauf_urteilt_ueber_neue_vorlagen(cities, rats, monkeypatch):
    """Was kein Urteil hat, bekommt eins — sonst wäre `schlank` ein Stillstand."""
    monkeypatch.setattr(fit_modul.llm, "chat_complete", lambda **kw: _antwort(
        {"status": "missing", "confidence": "high", "evidence": [], "reason": "."}))
    assert fit_modul.run(cities, rats, get("fit"), MODELL, workers=1,
                         schlank=True)["annotated"] == 1


def test_eine_neue_einordnung_oeffnet_das_urteil_im_schlanken_lauf(cities, rats, monkeypatch):
    """Neuer Text, neues Instrument: Das ist neuer Inhalt, kein neuer Beleg-Pool."""
    monkeypatch.setattr(fit_modul.llm, "chat_complete", lambda **kw: _antwort(
        {"status": "missing", "confidence": "high", "evidence": [], "reason": "."}))
    fit_modul.run(cities, rats, get("fit"), MODELL, workers=1, schlank=True)
    with cities._conn:
        cities._conn.execute("UPDATE annotations SET created_at = '2000-01-01' "
                             "WHERE annotator = 'fit'")
    assert cities.annotations_newer_than("classify", "2", "fit") == ["os:p:1"]
    assert fit_modul.run(cities, rats, get("fit"), MODELL, workers=1,
                         schlank=True)["annotated"] == 1


def test_das_abbild_ist_eindeutig_und_vollstaendig():
    """Das Abbild kommt mit dem Code: dev-Zeile → Sitzung und Punkt."""
    import json
    from pathlib import Path

    daten = json.loads(Path("council/cities/beschluss_abbild.json").read_text())
    abbild = daten["abbild"]
    assert len(abbild) >= 863
    for alt, neu in abbild.items():
        assert alt[len(BESCHLUSS_PRAEFIX):].isdigit(), alt
        ksinr, trenner, _top = neu[len(BESCHLUSS_PRAEFIX):].partition(":")
        # Der Punkt kann leer sein (4 von 9.524 Beschlüssen ohne TOP-Nummer).
        assert ksinr.isdigit() and trenner == ":", neu


def test_hashes_erst_nach_dem_oldenburg_lauf(cities, rats):
    """Runbook-Reihenfolge (#1651): `--hashes-ideen` übernimmt die Hashes auf
    dem Beleg-Pool, der gerade im Speicher liegt. Fehlen dort Oldenburger
    Vorlagen, die der erste `check_cities --nur-oldenburg` erst holt, beurteilt
    der erste Sonntag trotzdem alles neu. Das Skript zählt den Rückstand."""
    import importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location(
        "umschluesseln_test", Path("scripts/cities_belege_umschluesseln.py"))
    modul = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(modul)

    def beratung(kvonr, datum):
        with rats._conn:
            rats._conn.execute(
                "INSERT INTO council_deliberations (kvonr, date, committee, fetched_at) "
                "VALUES (?, ?, 'Rat', '2026-01-01')", (kvonr, datum))

    # Der Speicher kennt die Wärmeplanung vom 20.11.2025 — nichts fehlt.
    beratung(4711, "2025-11-20")
    assert modul.oldenburg_rueckstand(cities, rats) == 0
    # Eine Vorlage, die erst danach beraten wurde, kennt er nicht.
    beratung(4712, "2026-01-10")
    beratung(4712, "2026-02-01")
    assert modul.oldenburg_rueckstand(cities, rats) == 1
