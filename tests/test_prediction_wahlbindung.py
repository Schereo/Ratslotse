"""Eine Tipprunde gehört zu EINER Wahl — und weiß, was sie tippen lässt.

Bis 14.09.2026 verglich das Tippspiel gegen „den Wahlabend": die aktive
Ratswahl, wer immer das gerade war. Zwei Folgen, beide still:

* Eine Runde von 2026 hätte 2031 gegen die neuen Zahlen gepunktet und jeden
  Rang rückwirkend verschoben.
* Die Höchstpunktzahl stand als ``16 * 5`` und ``9 * 6`` im Code — die Listen-
  und Kandidaturenzahl von 2026, eingemauert.

Der Abnahmetest des Plans steht unten: Eine Runde auf eine **Mehrheitswahl**
(OB- oder Stichwahl) lässt sich anlegen, ohne eine Zeile Punkte-Code
anzufassen.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL / "web" / "backend"))

from kern.store import Store  # noqa: E402

from app.election import elections  # noqa: E402
from app.election import mayor as mayor_module  # noqa: E402
from app.election import service as election_service  # noqa: E402
from app.prediction import rounds, scoring, service  # noqa: E402


@pytest.fixture
def store(tmp_path, monkeypatch):
    """Eine leere Datenbank und ein Wahlabend ohne Zahlen — das Spiel selbst
    ist hier die Sache, nicht der Auszählungsstand."""
    monkeypatch.setenv("FEATURE_FLAGS", "tippspiel,wahlabend")
    monkeypatch.setattr(election_service, "live", lambda: election_service.probe(0))
    monkeypatch.setattr(mayor_module, "fetch", lambda force=False, w=None: mayor_module.probe(0, w))
    # Die Uhr steht VOR der Schließung der Wahllokale (13.09.2026, 18 Uhr):
    # Seit 19.09.2026 sperrt sich eine Runde um 18 Uhr am Wahltag von selbst —
    # mit der echten Uhr wäre die Ratswahl-Runde hier sofort zu.
    monkeypatch.setattr(service, "_jetzt",
                        lambda: datetime(2026, 9, 13, 10, 0, tzinfo=timezone.utc))
    st = Store(tmp_path / "tipp.sqlite")
    service.reset()
    yield st
    st.close()
    service.reset()


# ------------------------------------------------------------------ Die Bindung

def test_hoechstpunktzahl_kommt_aus_der_wahl():
    """134 Punkte sind 16 Listen und 9 Kandidaturen — nicht eine Konstante.
    Seit 19.09.2026 kommen 6 für die Wahlbeteiligung dazu (jede Wahlart)."""
    assert scoring.max_points(16, 9, turnout=False) == 134
    assert scoring.max_points(16, 9) == 140
    # Eine Stichwahl: zwei Kandidaturen, keine Listen — plus Wahlbeteiligung.
    assert scoring.max_points(0, 2, turnout=False) == 12
    assert scoring.max_points(0, 2) == 18
    assert scoring.max_points(0, 0, turnout=False) == 0


def test_eine_runde_ohne_eintrag_meint_die_aktive_ratswahl():
    """Bestandsrunden tragen ``election_slug = NULL`` (die Migration schreibt
    dort bewusst nichts hin) — sie müssen weiter dasselbe meinen wie vorher."""
    wahl = service.wahl_der_runde({"slug": "ratswahl", "election_slug": None})
    assert wahl.slug == elections.active().slug


def test_ein_eintrag_in_der_zeile_schlaegt_die_registry():
    """Die Zeile ist die Zusage: Was beim Anlegen galt, gilt weiter — auch
    wenn die Registry später eine andere Wahl aktiv nennt."""
    wahl = service.wahl_der_runde({"slug": "ratswahl", "election_slug": "ob-stichwahl-2026"})
    assert wahl.slug == "ob-stichwahl-2026"


def test_ein_unbekannter_slug_faellt_nicht_ins_leere():
    """Eine gelöschte Registry-Datei darf keine Runde umbringen."""
    wahl = service.wahl_der_runde({"slug": "ratswahl", "election_slug": "gibtsnicht"})
    assert wahl.slug == elections.active().slug


def test_jede_runde_der_registry_nennt_eine_bekannte_wahl():
    for runde in rounds.ROUNDS.values():
        if runde.election is not None:
            assert elections.get(runde.election) is not None, (
                f"Runde „{runde.slug}“ nennt die Wahl „{runde.election}“ — die gibt es nicht.")


# ------------------------------------------------------------------ Der Abnahmetest

@pytest.fixture
def stichwahl_runde(monkeypatch, store):
    """Eine Runde auf die Stichwahl — angelegt wie jede andere, fünf Zeilen."""
    monkeypatch.setitem(rounds.ROUNDS, "stichwahl",
                        rounds.Round(slug="stichwahl", title="Tippspiel zur Stichwahl",
                                     listed=False, election="ob-stichwahl-2026"))
    runde = rounds.ROUNDS["stichwahl"]
    zeile = store.prediction_game_by_slug(runde.slug, runde.title, runde.election)
    return zeile["id"]


def test_eine_prozent_runde_braucht_keine_zeile_punkte_code(store, stichwahl_runde):
    """Der Abnahmetest aus docs/plan-wahlen-generalisieren.md, PR 6."""
    aufbau = service.setup(store, stichwahl_runde)

    assert aufbau["election_slug"] == "ob-stichwahl-2026"
    assert aufbau["tip_kind"] == "pct", "Bei einer Mehrheitswahl wird auf Prozente getippt."
    assert aufbau["parties"] == [], "Eine Stichwahl hat keine Listen — und keine Sitze zu verteilen."
    assert aufbau["seats_total"] == 0
    assert [c["slug"] for c in aufbau["mayor_candidates"]] == ["rohr", "prange"]
    assert aufbau["election_title"] == "OB-Stichwahl Oldenburg"

    # Und die Punkte rechnen sich ohne jede Sonderbehandlung.
    punkte = scoring.score({}, {"prange": 52.0, "rohr": 48.0},
                           {}, {"prange": 52.1, "rohr": 47.9})
    assert punkte.total == 12 == scoring.max_points(0, len(aufbau["mayor_candidates"]), turnout=False)


def test_die_hauptrunde_bleibt_eine_sitzwahl(store):
    zeile = store.prediction_game_by_slug("ratswahl", "Tippspiel zur Ratswahl", "ratswahl-2026")
    aufbau = service.setup(store, zeile["id"])
    assert aufbau["tip_kind"] == "seats"
    assert aufbau["seats_total"] == 52
    assert len(aufbau["parties"]) == 16
    assert len(aufbau["mayor_candidates"]) == 9


def test_der_tipp_schluss_einer_fremden_wahl_greift_nicht(store, stichwahl_runde, monkeypatch):
    """Die erste Hochrechnung der RATSWAHL darf eine Stichwahl-Runde nicht
    zumachen — sonst schlösse am 13.09. ein Spiel, das erst am 27.09. läuft."""
    from app.antworten import ElectionNight

    nacht: ElectionNight = {  # type: ignore[typeddict-item]
        "parties": [{"seats": 3, "projected_seats": 3}],
    }
    service._check_auto_lock(store, stichwahl_runde, nacht)  # type: ignore[arg-type]
    assert store.prediction_game(stichwahl_runde)["phase"] == "open"
