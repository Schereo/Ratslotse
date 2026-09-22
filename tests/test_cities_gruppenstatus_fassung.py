"""Der Gruppen-Status gehört zur `fit`-Fassung (Regel 30).

Die Ideen-Liste verbindet `idea_group_status` über `fit_version`. Nach dem
Sprung auf Fassung 5 lag auf dev vom 20. bis 22.09.2026 kein einziger Eintrag
dafür vor: `peers` war überall 0, „auch in N anderen Städten" stand auf keiner
Karte, und die Sortierung nach Städten griff nicht — ohne jede Meldung.
"""
from __future__ import annotations

import inspect

from council.cities import pipeline, pruefung
from council.cities.annotators import get as get_annotator
from council.cities.model import Batch, Paper
from council.cities.store import CitiesStore


def _bestand(tmp_path, fassung: str, gruppen_fassung: str | None):
    s = CitiesStore(tmp_path / "c.sqlite")
    s.upsert_batch(Batch(papers=[Paper("p/1", "muenster", "Sache", date="2024-01-01",
                                       kind="motion")]))
    s.put_annotation("paper", "p/1", "fit", fassung,
                     {"status": "missing", "evidence": [], "reason": "",
                      "confidence": "high"}, "h", "m", 0.0)
    if gruppen_fassung:
        s._conn.execute(
            "INSERT INTO idea_group_status (model, version, body_id, cluster_id, "
            "fit_version, status, members, agreeing) VALUES ('m','1','muenster',1,?,"
            "'missing',1,1)", (gruppen_fassung,))
        s._conn.commit()
    return s


def test_fehlender_gruppenstatus_ist_ein_befund(tmp_path):
    aktuell = get_annotator("fit").version
    with _bestand(tmp_path, aktuell, "0") as s:
        befund = pruefung.gruppenstatus_fehlt(s)
    assert befund is not None and "0 Städten" in befund.text
    assert "rebuild_group_status" in befund.text, "Die Meldung nennt den Befehl, der sie behebt."


def test_mit_gruppenstatus_der_aktuellen_fassung_kein_befund(tmp_path):
    aktuell = get_annotator("fit").version
    with _bestand(tmp_path, aktuell, aktuell) as s:
        assert pruefung.gruppenstatus_fehlt(s) is None


def test_ohne_urteile_kein_befund(tmp_path):
    """Ein frischer Bestand ohne Urteile ist nicht kaputt, nur leer."""
    with CitiesStore(tmp_path / "c.sqlite") as s:
        assert pruefung.gruppenstatus_fehlt(s) is None


def test_der_fit_lauf_rechnet_den_gruppenstatus_nach():
    """Der Wächter: Jeder `fit`-Lauf über die Pipeline zieht ihn nach."""
    quelle = inspect.getsource(pipeline._fit)
    assert "rebuild_group_status" in quelle, (
        "pipeline._fit rechnet den Gruppen-Status nicht mehr nach — nach der "
        "nächsten neuen Fassung zeigt die Liste wieder „auch in 0 Städten“.")
