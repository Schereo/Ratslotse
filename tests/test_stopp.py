"""Ein langer Lauf, der freiwillig zur Seite tritt.

Am 20.09.2026 lief ``check_cities.py`` vierzehn Stunden — ein Versionssprung
des ``fit``-Annotators hatte 9.560 Urteile entwertet. Solange er lief, brach
JEDER Prod-Deploy in der Vorflug-Prüfung ab: sechs an einem Tag. Der Abbruch
war folgenlos, aber endlos, denn ein abgebrochener Deploy startet sich nicht
von selbst neu; Prod stand 33 Stunden auf dem Vortagsstand.

Die Wartungsbarriere half nicht: Sie sperrt NEUE Datenbank-Zugriffe, einen
bereits laufenden Prozess erreicht sie nicht. Also bittet der Deploy um Platz
(``data/.deploy-wartet``), und die langen Schleifen sehen an ihrer nächsten
Stapelgrenze nach.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest
import yaml

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL))

from kern.stopp import WARTET_NAME, Stopp, aus_umgebung  # noqa: E402


def test_ohne_argumente_wird_nie_aufgehoert():
    """Tests und Läufe von Hand sollen nichts wissen müssen."""
    assert Stopp().grund() is None


def test_ein_wartender_deploy_haelt_den_lauf_an(tmp_path):
    stopp = Stopp(tmp_path)
    assert stopp.grund() is None
    (tmp_path / WARTET_NAME).touch()
    grund = stopp.grund()
    assert grund is not None and grund.schluessel == "deploy"


def test_ein_liegengebliebener_marker_verfaellt(tmp_path):
    """Sonst wäre aus der Bitte ein Knebel geworden.

    Ein Deploy, der abbricht, bevor er aufräumt, ließe den Marker liegen —
    und jeder Wochenlauf danach träte sofort zur Seite und täte nie wieder
    etwas. Und zwar STILL: „ich mache gleich weiter" sieht von außen aus wie
    „alles erledigt". Dieselbe Überlegung wie ``LIMIT_SECONDS`` in
    ``scripts/ops_deploy_window.py``.
    """
    marker = tmp_path / WARTET_NAME
    marker.touch()
    alt = time.time() - 3600
    import os
    os.utime(marker, (alt, alt))
    assert Stopp(tmp_path).grund() is None


def test_die_frist_haelt_den_lauf_an(tmp_path):
    uhr = iter([0.0, 10.0, 100.0])
    stopp = Stopp(tmp_path, frist_sekunden=60, jetzt=lambda: next(uhr))
    assert stopp.grund() is None, "nach 10 von 60 Sekunden läuft er weiter"
    grund = stopp.grund()
    assert grund is not None and grund.schluessel == "frist"


def test_der_deploy_geht_der_frist_vor(tmp_path):
    """Er wartet auf eine Antwort, die Frist nicht — und die Kennzahl soll
    sagen, WARUM aufgehört wurde."""
    (tmp_path / WARTET_NAME).touch()
    uhr = iter([0.0, 1000.0])
    grund = Stopp(tmp_path, frist_sekunden=1, jetzt=lambda: next(uhr)).grund()
    assert grund is not None and grund.schluessel == "deploy"


@pytest.mark.parametrize("wert", ["keine-zahl", "-5", "0"])
def test_ein_kaputter_umgebungswert_heisst_keine_frist(tmp_path, monkeypatch, wert):
    """Ein Tippfehler in der ``.env`` darf einen Wochenlauf nicht
    stillschweigend auf null Sekunden setzen — „unlesbar" heißt „keine
    Frist", nicht „sofort aufhören"."""
    monkeypatch.setenv("CITIES_MAX_SECONDS", wert)
    uhr = iter([0.0, 10.0 ** 9])
    stopp = aus_umgebung(tmp_path, "CITIES_MAX_SECONDS", vorgabe_sekunden=60,
                         jetzt=lambda: next(uhr))
    assert stopp.grund() is None, "auch nach beliebig langer Zeit keine Frist"


def test_ohne_umgebungswert_gilt_die_vorgabe(tmp_path, monkeypatch):
    monkeypatch.delenv("CITIES_MAX_SECONDS", raising=False)
    uhr = iter([0.0, 61.0])
    stopp = aus_umgebung(tmp_path, "CITIES_MAX_SECONDS", vorgabe_sekunden=60,
                         jetzt=lambda: next(uhr))
    grund = stopp.grund()
    assert grund is not None and grund.schluessel == "frist"


def test_umgebungswert_schlaegt_die_vorgabe(tmp_path, monkeypatch):
    """Ein Nachlauf von Hand soll die Frist heben können, ohne Code zu ändern."""
    monkeypatch.setenv("CITIES_MAX_SECONDS", "120")
    uhr = iter([0.0, 119.0, 121.0])
    stopp = aus_umgebung(tmp_path, "CITIES_MAX_SECONDS", vorgabe_sekunden=60,
                         jetzt=lambda: next(uhr))
    assert stopp.grund() is None, "die Vorgabe von 60 s greift nicht mehr"
    grund = stopp.grund()
    assert grund is not None and grund.schluessel == "frist"


# ---- Der Deploy setzt und räumt ihn weg ----------------------------------

def test_deploy_bittet_um_platz_und_raeumt_wieder_auf():
    """Beides gehört zusammen: Wer bittet und nicht aufräumt, legt jeden
    folgenden Wochenlauf lahm."""
    wf = yaml.safe_load((WURZEL / ".github/workflows/deploy.yml").read_text())
    schritte = wf["jobs"]["deploy"]["steps"]
    namen = [s.get("name") for s in schritte]
    lauf = " ".join(str(s.get("run", "")) for s in schritte)
    assert f"data/{WARTET_NAME}" in lauf

    bitte = namen.index("Laufende Jobs um Platz bitten")
    # VOR allem, was etwas anfasst: Backup, Vorflug, Barriere, rsync.
    assert bitte < namen.index("Verify release runtime prerequisites")
    assert bitte < namen.index("Enter release maintenance barrier")

    aufraeumen = next(s for s in schritte if s.get("name") == "Platz-Bitte zurücknehmen")
    assert aufraeumen["if"] == "always()", (
        "auch nach einem Abbruch — sonst tritt jeder Cron danach sofort zur Seite")
    assert WARTET_NAME in aufraeumen["run"]


# ---- Die lange Schleife hört wirklich auf ---------------------------------

def _einordnungs_store(tmp_path):
    from council.cities.model import Batch, Body, File, FileRole, Paper
    from council.cities.store import CitiesStore

    s = CitiesStore(tmp_path / "cities.sqlite")
    s.upsert_body(Body("osnabrueck", "Osnabrück", "NI", "allris4"))
    s.upsert_batch(Batch(
        papers=[Paper(f"os:p:{n}", "osnabrueck", f"Vorlage {n}", date="2026-05-01",
                      paper_type_raw="Beschlussvorlage", kind="proposal")
                for n in range(1, 13)],
        files=[File(f"os:f:{n}", "osnabrueck", FileRole.MAIN, paper_id=f"os:p:{n}")
               for n in range(1, 13)]))
    for n in range(1, 13):
        s.put_text(f"os:f:{n}", "pypdf", "1", f"Sachverhalt {n}.", 1, "ok")
    return s


def test_annotate_hoert_an_der_stapelgrenze_auf_und_behaelt_das_geschriebene(
        tmp_path, monkeypatch):
    """Der Kern des Ganzen.

    ``pool.map`` reicht ALLE Stapel sofort ein; ohne ``cancel_futures``
    dauerte das Aufhören genauso lange wie das Weitermachen, und für einen
    wartenden Deploy wäre nichts gewonnen. Und was schon geschrieben ist,
    bleibt — genau deshalb schreibt die Pipeline stapelweise und nicht am
    Ende: Ein 14-Stunden-Lauf, der erst zum Schluss schreibt, wirft bei einem
    Abbruch einen ganzen Tag Modellkosten weg.
    """
    import json
    from types import SimpleNamespace

    from council.cities import annotate as annotate_modul
    from council.cities.annotators import get

    store = _einordnungs_store(tmp_path)
    ann = get("classify")
    marker = tmp_path / WARTET_NAME

    def antwort(**kw):
        # Der Deploy meldet sich, während der erste Stapel unterwegs ist.
        marker.touch()
        ids = [z.split()[1] for z in kw["messages"][1]["content"].splitlines()
               if z.startswith("id ")]
        nutzlast = [{"id": i, "field": "klima_umwelt", "transfer": "adaptable",
                     "competence": "council", "instrument": "Etwas",
                     "summary": "Zusammenfassung."} for i in ids]
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(
                content=json.dumps({"results": nutzlast})))],
            usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1, cost=0.0))

    monkeypatch.setattr(annotate_modul.llm, "chat_complete", antwort)
    try:
        stand = annotate_modul.run(store, ann, workers=1, stopp=Stopp(tmp_path))
        assert stand["abgebrochen_deploy"] == 1
        assert 0 < stand["annotated"] < 12, (
            "der erste Stapel ist geschrieben, der Rest liegt für nächstes Mal")
        # Und er ist wirklich in der Datenbank, nicht nur im Zähler.
        assert len(store.annotations_for(ann.key, ann.version)) == stand["annotated"]
    finally:
        store.close()


def test_ohne_stopp_laeuft_alles_durch(tmp_path, monkeypatch):
    """Die Gegenprobe: Der Abbruch darf nicht der Normalfall werden."""
    import json
    from types import SimpleNamespace

    from council.cities import annotate as annotate_modul
    from council.cities.annotators import get

    store = _einordnungs_store(tmp_path)
    ann = get("classify")

    def antwort(**kw):
        ids = [z.split()[1] for z in kw["messages"][1]["content"].splitlines()
               if z.startswith("id ")]
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(
                {"results": [{"id": i, "field": "klima_umwelt",
                              "transfer": "adaptable", "competence": "council",
                              "instrument": "Etwas", "summary": "Z."}
                             for i in ids]})))],
            usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1, cost=0.0))

    monkeypatch.setattr(annotate_modul.llm, "chat_complete", antwort)
    try:
        stand = annotate_modul.run(store, ann, workers=1, stopp=Stopp(tmp_path))
        assert stand["annotated"] == 12
        assert not any(k.startswith("abgebrochen_") for k in stand)
    finally:
        store.close()
