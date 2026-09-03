"""Der Starter des lokalen Servers — die Teile, die ohne Server prüfbar sind.

Ein echter Start gehört nicht in die Suite: Er bräuchte die Datenbanken aus
dem Abzug und eine halbe Minute. Prüfbar ist die Mechanik, an der es
tatsächlich gescheitert ist — dass ein belegter Port als belegt erkannt wird
und ein toter Eintrag nicht als laufender Server durchgeht.
"""
from __future__ import annotations

import json
import socket
import subprocess
import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL))

from scripts import dev  # noqa: E402


def test_ein_belegter_port_gilt_als_belegt():
    """Der Kern des Ganzen: Am 02.09.2026 lag ein fremder Server auf dem Port,
    der eigene startete gar nicht, und gemessen wurde zwanzig Minuten lang der
    fremde."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        s.listen(1)
        port = s.getsockname()[1]
        assert dev.belegt_von(port) is not None


def test_ein_freier_port_gilt_als_frei():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    # Socket zu, Port wieder frei.
    assert dev.belegt_von(port) is None


def test_freier_port_liegt_im_eigenen_bereich():
    port = dev.freier_port()
    assert port is None or dev.PORT_VON <= port <= dev.PORT_BIS


def test_toter_eintrag_gilt_nicht_als_laufender_server(tmp_path, monkeypatch):
    stand = tmp_path / "stand.json"
    # PID 1 lebt, ist aber nicht unserer; deshalb eine, die es sicher nicht
    # gibt. Die höchste PID ist auf keinem System 2**31 - 1.
    stand.write_text(json.dumps({"pid": 2**31 - 1, "port": 8600, "basis": "x", "seit": "y"}))
    monkeypatch.setattr(dev, "STAND", stand)
    assert dev.lies_stand() is None
    assert not stand.exists(), "der tote Eintrag muss weg sein"


def test_der_arbeitsstand_ist_nicht_eingecheckt():
    """Sonst schmuggelt sich der Port einer Sitzung in einen fremden PR —
    genau der Grund, aus dem `.claude/launch.json` nicht mehr getrackt ist."""
    for datei in (".dev-server.json", "dev-server.log"):
        ergebnis = subprocess.run(["git", "check-ignore", datei], cwd=WURZEL,
                                  capture_output=True, text=True)
        assert ergebnis.returncode == 0, f"{datei} ist nicht ignoriert"


def test_hilfe_laeuft():
    ergebnis = subprocess.run([sys.executable, "scripts/dev.py", "--help"],
                              cwd=WURZEL, capture_output=True, text=True)
    assert ergebnis.returncode == 0, ergebnis.stderr
    assert "start" in ergebnis.stdout and "stop" in ergebnis.stdout
