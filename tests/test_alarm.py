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

from scripts import alarm, ops_deploy_window  # noqa: E402


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


# ---- Das Deploy-Fenster --------------------------------------------------
#
# Am 10.09.2026 fiel die Probe in einen laufenden Release-Deploy: Barriere um
# 20:15:21 gesetzt, alle drei Versuche sahen `/api/health` 503, um 20:16:49
# lief die Seite wieder — 85 Sekunden, Vor- und Rauchprobe je 49/49 grün. Von
# außen sieht das aus wie der 07.09. (74 Minuten Ausfall). Der Unterschied ist
# das ALTER der Barriere, und daraus muss eine Entscheidung werden, die man
# prüfen kann.

def test_frische_barriere_unterdrueckt_den_alarm():
    """Der Fall vom 10.09.2026: 88 Sekunden alt, also deployt es gerade."""
    unterdrueckt, grund = ops_deploy_window.evaluate("88", " /api/health:503")
    assert unterdrueckt
    assert "Deploy läuft" in grund


def test_alte_barriere_meldet_weiterhin():
    """Der Fall vom 07.09.2026. Genau dafür ist der Anpinger gebaut — er darf
    daran nicht scheitern, nur weil es formal dieselbe Barriere ist."""
    unterdrueckt, grund = ops_deploy_window.evaluate("4500", " /api/health:503")
    assert not unterdrueckt
    assert "hängt" in grund


@pytest.mark.parametrize("alter", ["keine", "unerreichbar", "", "kaputt", "-5"])
def test_ohne_nachweis_wird_gemeldet(alter):
    """Unterdrückt wird nur mit positivem Nachweis. Kein Marker, kein SSH,
    unverständliche Antwort — jeder dieser Wege endet im Alarm, nicht in der
    Stille. Ein Fehler hier kostet eine überflüssige Mail, nicht eine
    fehlende."""
    unterdrueckt, _ = ops_deploy_window.evaluate(alter, " /:502")
    assert not unterdrueckt


def test_die_unterdrueckung_hat_eine_obergrenze():
    """Ohne Kappe wäre aus der Bremse ein Knebel geworden: Eine hängende
    Barriere meldete sich nie wieder. Der Ausfall vom 07.09. dauerte 74
    Minuten — die Grenze muss deutlich darunter liegen."""
    assert 0 < ops_deploy_window.LIMIT_SECONDS <= 900


def test_begruendung_ueberlebt_die_ssh_zeile(tmp_path, monkeypatch):
    """Der Grund wird in der Alarm-Mail über eine einfach gequotete
    Shell-Zeile durchgereicht und als `key=value` an GitHub Actions gegeben.
    Ein Anführungszeichen zerlegte das eine, ein Zeilenumbruch das andere."""
    ziel = tmp_path / "github_output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(ziel))
    rc = ops_deploy_window.main(["--age", "kaputt('x')\nzweite Zeile",
                                 "--findings", " /api/health:503"])
    assert rc == 0
    zeilen = ziel.read_text(encoding="utf-8").splitlines()
    assert "suppressed=0" in zeilen
    grund = next(z for z in zeilen if z.startswith("reason="))
    assert "'" not in grund, "sonst zerbricht die SSH-Zeile der Alarm-Mail"
    assert len(zeilen) == 2, "eine Zeile je Ausgabe, sonst zerbricht das Format"


def test_erreichbarkeit_fragt_vor_dem_alarm_nach_dem_deploy():
    """Die Reihenfolge ist der Punkt: erst fragen, ob gerade deployt wird,
    dann melden. Und die Frage braucht den SSH-Zugang vor sich."""
    schritte = _workflow("ops-erreichbarkeit.yml")["jobs"]["probe"]["steps"]
    namen = [s.get("name", "") for s in schritte]
    assert namen.index("Configure deployment SSH") < namen.index("Läuft gerade ein Deploy?")
    assert namen.index("Läuft gerade ein Deploy?") < namen.index("Alarm über den Server")
    fenster = next(s for s in schritte if s.get("name") == "Läuft gerade ein Deploy?")
    lauf = str(fenster["run"])
    assert "scripts/ops_deploy_window.py" in lauf, "die Entscheidung hat einen Test"
    assert ".release-maintenance" in lauf
    # Auf dem SERVER gerechnet — sonst ginge die Uhrendifferenz zwischen
    # Runner und VPS in das Alter ein.
    assert "date +%s" in lauf and "stat -c %Y" in lauf
    # Der Schritt darf den Lauf nicht abbrechen: Dann fiele die Meldung aus.
    assert fenster.get("continue-on-error")


def test_alarm_meldet_ausser_es_ist_nachweislich_ein_deploy():
    """Fail-safe in die richtige Richtung: Die Alarm-Schritte hängen an einem
    NEGATIVEN Test (`suppressed != '1'`). Ein übersprungener, abgestürzter oder
    fehlerhafter Fenster-Schritt lässt das Feld leer — und dann wird gemeldet
    wie vor diesem Riegel. Andersherum (`== '0'`) wäre jeder Aussetzer ein
    stiller Ausfall."""
    schritte = _workflow("ops-erreichbarkeit.yml")["jobs"]["probe"]["steps"]
    for name in ("Erster Fehlschlag?", "Alarm über den Server", "Alarm am Server vorbei"):
        bedingung = next(s for s in schritte if s.get("name") == name)["if"]
        assert "steps.fenster.outputs.suppressed != '1'" in bedingung, name


def test_unterdruecktes_fenster_bleibt_gruen():
    """Ein grüner Lauf ist hier kein Schönheitsfehler, sondern Bedingung: Die
    Mail-Bremse („nur beim ERSTEN Fehlschlag") liest die Farbe des vorherigen
    Laufs. Wäre ein Deploy-Fenster rot, gälte ein echter Ausfall zehn Minuten
    später als Wiederholung — und bliebe stumm."""
    schritte = _workflow("ops-erreichbarkeit.yml")["jobs"]["probe"]["steps"]
    befund = next(s for s in schritte if s.get("name") == "Befund")
    lauf = str(befund["run"])
    assert "exit 0" in lauf and "exit 1" in lauf
    assert 'steps.fenster.outputs.suppressed }}" = "1"' in lauf
    # Und der Anping-Schritt selbst färbt den Lauf nicht mehr rot — sonst käme
    # der Befund-Schritt gar nicht mehr dazu, ihn grün zu lassen.
    probe = next(s for s in schritte if s.get("name") == "Prod anpingen")
    assert "exit 1" not in str(probe["run"])
