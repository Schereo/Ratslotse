"""Was passiert, wenn ein Deploy folgenlos abbricht — und niemand es merkt.

Am 20.09.2026 wurden sechs PRs nach `main` gemergt und sechs Deploys brachen
ab. Fünf davon in den Vorflug-Prüfungen, also ohne Prod anzufassen; einer nach
dem API-Stopp. Alle sechs schickten dieselbe Mail. Prod lief 33 Stunden lang
auf dem Stand vom Vortag, und in keiner der sechs Mails stand das.

Seit der Alarm abgestuft ist (`scripts/alarm.py::betroffen`), mailen die fünf
harmlosen gar nicht mehr. Das ist richtig — macht aber ohne Gegenstück aus
einem lauten Stau einen stillen. `scripts/ops_deploy_rueckstand.py` ist dieses
Gegenstück: Es fragt, ob `main` dem letzten geglückten Deploy voraus ist, und
entscheidet zwischen nachholen, warten und melden.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL))

from scripts.ops_deploy_rueckstand import (  # noqa: E402
    AKTUELL, MELDEN, NACHHOLEN, WARTEN, bewerten,
)

JETZT = "2026-09-20T19:00:00Z"


def test_aktuell_wenn_der_letzte_deploy_juenger_ist():
    befund = bewerten(main_commit="2026-09-20T10:00:00Z",
                      letzter_erfolg="2026-09-20T10:12:00Z",
                      jetzt=JETZT, crons_frei=True)
    assert befund.aktion == AKTUELL


def test_nachholen_wenn_main_voraus_ist_und_nichts_blockiert():
    """Der Regelfall nach einem folgenlosen Abbruch: Der Cron ist durch, der
    Deploy kann sofort laufen — ohne dass jemand eine Mail dafür braucht."""
    befund = bewerten(main_commit="2026-09-20T18:01:00Z",
                      letzter_erfolg="2026-09-19T10:12:00Z",
                      jetzt=JETZT, crons_frei=True)
    assert befund.aktion == NACHHOLEN


def test_warten_solange_ein_cron_laeuft():
    """Sonntagvormittag: `check_cities.py` läuft seit 5 Uhr. Das ist kein
    Vorfall, das ist der Fahrplan — der nächste Takt fragt wieder."""
    befund = bewerten(main_commit="2026-09-20T17:00:00Z",
                      letzter_erfolg="2026-09-19T10:12:00Z",
                      jetzt="2026-09-20T18:00:00Z", crons_frei=False)
    assert befund.aktion == WARTEN


def test_melden_wenn_der_cron_zu_lange_blockiert():
    """Vierzehn Stunden waren es am 20.09.2026. Ab irgendwann ist Warten keine
    Erklärung mehr, sondern ein Stau."""
    befund = bewerten(main_commit="2026-09-20T05:00:00Z",
                      letzter_erfolg="2026-09-19T10:12:00Z",
                      jetzt=JETZT, crons_frei=False)
    assert befund.aktion == MELDEN
    assert "blockiert" in befund.grund


def test_ein_laufender_deploy_ist_kein_rueckstand():
    """Der Vorfall vom 21.09.2026: Der Deploy zu #1424 brauchte 26 Minuten
    (Docs-Build plus `next build`), der Wächter fragte nach 20 — und stieß
    denselben Commit ein zweites Mal an. Prod bekam eine zweite
    Wartungsbarriere und zwei Minuten 503 für nichts. Gemessen wird gegen den
    letzten GEGLÜCKTEN Lauf; der gerade laufende kam darin nicht vor."""
    befund = bewerten(main_commit="2026-09-20T18:40:00Z",
                      letzter_erfolg="2026-09-19T10:12:00Z",
                      jetzt=JETZT, crons_frei=True, deploy_laeuft=True)
    assert befund.aktion == WARTEN
    assert "Deploy-Lauf" in befund.grund


def test_laufender_deploy_meldet_auch_nach_fehlversuchen_nicht():
    """Solange ein Lauf offen ist, weiß niemand, ob er scheitert — ihn
    mitzuzählen hieße, einen Stau zu melden, den er gerade auflöst. Der
    nächste Takt sieht sein Ergebnis."""
    befund = bewerten(main_commit="2026-09-20T05:00:00Z",
                      letzter_erfolg="2026-09-19T10:12:00Z",
                      jetzt=JETZT, crons_frei=True, fehlversuche=9,
                      deploy_laeuft=True)
    assert befund.aktion == WARTEN


def test_ohne_laufenden_deploy_bleibt_alles_wie_vorher():
    """Die Gegenrichtung: Der neue Schalter darf den Regelfall nicht
    anfassen."""
    befund = bewerten(main_commit="2026-09-20T18:01:00Z",
                      letzter_erfolg="2026-09-19T10:12:00Z",
                      jetzt=JETZT, crons_frei=True, deploy_laeuft=False)
    assert befund.aktion == NACHHOLEN


def test_melden_statt_endlos_nachholen():
    """Ohne Obergrenze stieße ein Deploy, der aus einem ganz anderen Grund rot
    ist, sich alle dreißig Minuten selbst neu an — und die abgestufte Stille
    verschluckte einen echten Defekt für immer."""
    befund = bewerten(main_commit="2026-09-20T18:01:00Z",
                      letzter_erfolg="2026-09-19T10:12:00Z",
                      jetzt=JETZT, crons_frei=True, fehlversuche=3)
    assert befund.aktion == MELDEN
    assert "gescheitert" in befund.grund


def test_unbekannte_cron_lage_holt_nicht_blind_nach():
    """Antwortet der Server nicht, heißt das ausdrücklich NICHT „frei": In
    einen laufenden Job hineinzudeployen ist genau der Zustand, den die
    Vorflug-Prüfung verhindern soll."""
    befund = bewerten(main_commit="2026-09-20T18:01:00Z",
                      letzter_erfolg="2026-09-19T10:12:00Z",
                      jetzt=JETZT, crons_frei=None)
    assert befund.aktion != NACHHOLEN


@pytest.mark.parametrize("kaputt", ["", "gestern", "keiner"])
def test_unlesbarer_zeitstempel_meldet(kaputt):
    """Ein Fehler in diesem Pfad darf nicht in der Stille enden — dieselbe
    Regel wie in `ops_deploy_window.py`: positiver Nachweis, sonst Alarm."""
    assert bewerten(main_commit=kaputt, letzter_erfolg=None,
                    jetzt=JETZT, crons_frei=True).aktion == MELDEN


def test_noch_nie_deployt_gilt_als_rueckstand():
    befund = bewerten(main_commit="2026-09-20T18:01:00Z", letzter_erfolg=None,
                      jetzt=JETZT, crons_frei=True)
    assert befund.aktion == NACHHOLEN


def test_grund_ueberlebt_den_weg_durch_shell_und_actions():
    """Die Begründung geht über SSH durch eine einfach gequotete Shell-Zeile in
    die Alarm-Mail und vorher durch `$GITHUB_OUTPUT`. Ein Anführungszeichen
    zerlegte den Befehl, ein Zeilenumbruch das Ausgabeformat."""
    for befund in (
        bewerten(main_commit="2026-09-20T05:00:00Z", letzter_erfolg=None,
                 jetzt=JETZT, crons_frei=False),
        bewerten(main_commit="unfug", letzter_erfolg=None, jetzt=JETZT,
                 crons_frei=True),
    ):
        assert "'" not in befund.grund
        assert "\n" not in befund.grund


# ---- Der Workflow --------------------------------------------------------

def test_workflow_holt_nach_und_meldet_nur_den_stau():
    wf = yaml.safe_load(
        (WURZEL / ".github/workflows/ops-deploy-rueckstand.yml").read_text())
    ausloeser = wf.get("on") or wf.get(True)
    assert ausloeser["schedule"][0]["cron"], "ohne Takt holt niemand nach"
    # Den Deploy anzustoßen ist der ganze Zweck.
    assert wf["permissions"]["actions"] == "write"
    schritte = wf["jobs"]["rueckstand"]["steps"]
    lauf = " ".join(str(s.get("run", "")) for s in schritte)
    assert "gh workflow run deploy.yml --ref main" in lauf
    # Die Cron-Frage über den schlanken Blick, nicht über die volle Freigabe:
    # Eine fehlende .env darf den Nachhol-Wächter nicht lahmlegen.
    assert "--nur-crons" in lauf
    # Und die Frage, die am 21.09.2026 gefehlt hat: Läuft schon einer? Gefragt
    # wird nach allem, was nicht `completed` ist — ein an der
    # concurrency-Gruppe wartender Lauf steht auf `queued`.
    assert "--workflow deploy.yml --limit 10 --json status" in lauf
    assert "--laufend" in lauf
    # Gemeldet wird nur der Stau; „warten" bleibt grün, sonst läse die
    # Erster-Befund-Bremse den nächsten echten Stau als Wiederholung.
    nachholen = next(s for s in schritte if s.get("name") == "Deploy nachholen")
    assert nachholen["if"] == "steps.befund.outputs.aktion == 'nachholen'"
