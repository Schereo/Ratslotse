"""Der Betriebsalarm: Bricht der Deploy ab, muss jemand es ERFAHREN.

Am 07.09.2026 lag die Prod-API 74 Minuten still. Der Deploy war rot (die
Rauchprobe fiel über einen datenabhängigen 500er), die fail-closed
Wartungsbarriere blieb korrekt stehen — und genau deshalb war die Seite unten.
Gemeldet hat es nichts: Ein Cron-Alarm setzt einen laufenden Cron voraus,
`kern/fehler.py` einen laufenden Prozess, und ein roter Actions-Lauf ist kein
Alarm, sondern ein Eintrag in einer Liste. Gemerkt wurde es, als eine Anmeldung
500 lieferte.

Zwei Dinge hält dieser Test fest: dass der Deploy-Workflow im Fehlerfall
überhaupt alarmiert, und dass das Skript dabei die .env lädt — ohne sie ist
unter SSH kein RESEND_API_KEY gesetzt, und `notify_admin` loggt still vor sich
hin, statt zu mailen. Genau daran ist `remind_setup.py` schon einmal
gescheitert (s. tests/test_remind_setup.py).
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL))

from scripts import alarm  # noqa: E402


def test_alarm_laedt_die_env_bevor_er_mailt():
    """Ohne load_dotenv ist unter SSH/Cron kein RESEND_API_KEY gesetzt — die
    Mail entfiele still, und der Alarm wäre genau dann stumm, wenn er zählt."""
    quelltext = (WURZEL / "scripts" / "alarm.py").read_text()
    assert "load_dotenv" in quelltext


def test_zustand_nennt_die_stehende_barriere(tmp_path):
    """Die Barriere ist der Unterschied zwischen „ein Deploy ist rot" und
    „die Seite ist unten". Sie gehört deshalb in die erste Zeile der Mail."""
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / ".release-maintenance").write_text("abc123\n")
    with patch.object(alarm, "_dienst", return_value="inactive"):
        text = alarm.zustand(tmp_path)
    assert "Wartungsbarriere steht" in text
    assert "abc123" in text
    assert "nwz-web-api" in text and "inactive" in text


def test_zustand_ohne_barriere_sagt_das_auch(tmp_path):
    """Der ruhige Fall muss genauso deutlich sein: Ein Deploy kann auch aus
    einem Grund abbrechen, der die Seite gar nicht anfasst."""
    (tmp_path / "data").mkdir()
    with patch.object(alarm, "_dienst", return_value="active"):
        text = alarm.zustand(tmp_path)
    assert "liegt nicht" in text


def test_main_reicht_betreff_und_zustand_an_notify_admin(tmp_path, monkeypatch):
    """Der ganze Weg einmal echt — nur der Mailversand ist abgefangen."""
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / ".release-maintenance").write_text("deadbeef\n")
    (tmp_path / ".env").write_text("")
    gesehen = {}

    def _fake(text, betreff="", fusszeile=""):
        gesehen["text"], gesehen["betreff"] = text, betreff

    monkeypatch.setitem(sys.modules, "kern.alerts", type(sys)("kern.alerts"))
    sys.modules["kern.alerts"].notify_admin = _fake
    with patch.object(alarm, "_dienst", return_value="inactive"):
        rc = alarm.main(["--root", str(tmp_path), "--betreff", "Deploy abgebrochen",
                         "--text", "Der Prod-Deploy ist abgebrochen.", "--zustand"])
    assert rc == 0
    assert gesehen["betreff"] == "Deploy abgebrochen"
    assert "Der Prod-Deploy ist abgebrochen." in gesehen["text"]
    assert "deadbeef" in gesehen["text"], "der Zustand hängt mit dran"


# ---- Die Workflows selbst ------------------------------------------------

def _workflow(name: str) -> dict:
    return yaml.safe_load((WURZEL / ".github" / "workflows" / name).read_text())


def test_deploy_alarmiert_wenn_er_abbricht():
    """Ein abgebrochener Deploy lässt Barriere und API-Stopp bewusst stehen.
    Das ist richtig — aber dann MUSS es jemand erfahren."""
    schritte = _workflow("deploy.yml")["jobs"]["deploy"]["steps"]
    alarme = [s for s in schritte if s.get("if") == "failure()"]
    assert alarme, "der deploy-Job braucht einen Schritt mit if: failure()"
    lauf = " ".join(str(s.get("run", "")) for s in alarme)
    assert "scripts/alarm.py" in lauf
    # Der Alarm darf den roten Lauf nicht überdecken, wenn er selbst scheitert.
    assert all(s.get("continue-on-error") for s in alarme)


def test_erreichbarkeit_prueft_von_aussen_und_regelmaessig():
    """Die Prüfung, die `check_herzschlag.py` in seinem Docstring als fehlend
    beschreibt: von außerhalb der Maschine, nach einem Takt, ohne Cron."""
    wf = _workflow("ops-erreichbarkeit.yml")
    # `on:` ist in YAML das Schlüsselwort True — deshalb der Umweg.
    ausloeser = wf.get("on") or wf.get(True)
    assert "schedule" in ausloeser, "ohne Takt prüft niemand"
    assert ausloeser["schedule"][0]["cron"]
    schritte = wf["jobs"]["probe"]["steps"]
    probe = " ".join(str(s.get("run", "")) for s in schritte)
    assert "/api/health" in probe, "genau der Endpunkt, den die Barriere auf 503 zieht"
    # Mehrfach prüfen, bevor Alarm geschlagen wird: ein Aussetzer ist Netz.
    assert "for versuch in" in probe


def test_deploy_bricht_nur_am_kern_ab():
    """Die Vorprobe war alles-oder-nichts, und das hat am 07.09.2026 die Seite
    gekostet: Eine einzelne Kachel war rot, der Deploy brach ab, die Barriere
    blieb stehen. Jetzt unterscheidet er — Rückgabewert 1 blockiert, 2 läuft
    weiter und meldet."""
    schritte = _workflow("deploy.yml")["jobs"]["deploy"]["steps"]
    neustart = next(s for s in schritte
                    if s.get("name") == "Restart services and rebuild web")
    lauf = str(neustart["with"]["script"])
    assert "probe_rc" in lauf, "der Rückgabewert wird ausgewertet"
    assert 'probe_rc" = "2"' in lauf, "der Rand-Fall wird eigens behandelt"
    assert "rand_rot" in lauf
    assert "scripts/alarm.py" in lauf, "ein durchgelassener Randbefund MUSS melden"


def test_erreichbarkeit_meldet_zuerst_ueber_den_server():
    """Der Server trägt RESEND_API_KEY und ALERT_EMAIL längst in seiner .env.
    Der Weg über ihn braucht deshalb kein neues Repository-Secret — nur den
    Deploy-Schlüssel, den es ohnehin gibt. Die Secrets sind der Notausgang für
    den Fall, dass die MASCHINE stumm ist."""
    schritte = _workflow("ops-erreichbarkeit.yml")["jobs"]["probe"]["steps"]
    namen = [s.get("name", "") for s in schritte]
    assert namen.index("Alarm über den Server") < namen.index("Alarm am Server vorbei")
    ueber = next(s for s in schritte if s.get("name") == "Alarm über den Server")
    assert "scripts/alarm.py" in str(ueber["run"])
    vorbei = next(s for s in schritte if s.get("name") == "Alarm am Server vorbei")
    # Der Notausgang greift nur, wenn der Weg über den Server NICHT ging.
    assert "steps.ueber_server.outcome != 'success'" in vorbei["if"]
    # Und er scheitert nicht, wenn die optionalen Secrets fehlen.
    assert "bleibt GitHubs eigene Benachrichtigung" in str(vorbei["run"])


@pytest.mark.parametrize("datei", ["deploy.yml", "ops-erreichbarkeit.yml"])
def test_workflows_sind_wohlgeformt(datei):
    assert _workflow(datei)["jobs"]
