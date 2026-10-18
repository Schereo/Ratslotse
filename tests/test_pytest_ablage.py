"""Die Suite lässt nur die Ablagen fehlgeschlagener Tests liegen.

Einige Messtests kopieren die echte Rats-Datenbank (~250 MB) je
Parametrisierung nach ``tmp_path``. Mit der Vorgabe von pytest (alles der
letzten drei Läufe behalten) blieben so je Lauf 1–5 GB in
``$TMPDIR/pytest-of-*/`` liegen — am 05.10.2026 Teil eines vollen Datenträgers.
"""
from __future__ import annotations


def test_gruene_tests_raeumen_ihre_ablage_weg(pytestconfig):
    assert pytestconfig.getini("tmp_path_retention_policy") == "failed", (
        "pytest.ini im Repo-Wurzelverzeichnis muss "
        "`tmp_path_retention_policy = failed` setzen.")
