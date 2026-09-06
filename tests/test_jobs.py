"""Cron-Protokoll: run_guarded schreibt jeden Lauf in job_runs (kern/alerts.py)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL))

from kern.alerts import run_guarded  # noqa: E402
from kern.jobs import BY_KEY, JOBS  # noqa: E402
from kern.store import Store  # noqa: E402


@pytest.fixture()
def db(tmp_path, monkeypatch):
    """Temporäre ratslotse.sqlite — run_guarded findet sie über RATSLOTSE_DB."""
    path = tmp_path / "ratslotse.sqlite"
    Store(path).close()
    monkeypatch.setenv("RATSLOTSE_DB", str(path))
    return path


def test_erfolgreicher_lauf_wird_mit_kennzahlen_protokolliert(db):
    run_guarded("check_council", lambda: {"Benachrichtigungen": 3})

    store = Store(db)
    runs = store.job_runs()
    store.close()

    assert len(runs) == 1
    run = runs[0]
    assert run["job"] == "check_council"
    assert run["status"] == "ok"
    assert run["stats"] == {"Benachrichtigungen": 3}
    assert run["error"] is None
    assert run["duration_s"] >= 0
    assert run["finished_at"] >= run["started_at"]


def test_lauf_ohne_rueckgabe_wird_ohne_kennzahlen_protokolliert(db):
    run_guarded("backup_db", lambda: None)

    store = Store(db)
    runs = store.job_runs()
    store.close()
    assert runs[0]["status"] == "ok" and runs[0]["stats"] is None


def test_absturz_wird_protokolliert_und_weitergereicht(db, monkeypatch):
    # Ohne Mail-Konfiguration bleibt der Alarm ein Log-Eintrag; der Crash muss
    # trotzdem als Fehlerlauf in der Historie landen und weiterfliegen.
    monkeypatch.delenv("ALERT_EMAIL", raising=False)
    monkeypatch.delenv("WEB_ADMIN_EMAIL", raising=False)

    def boom():
        raise RuntimeError("Ratsinfo nicht erreichbar")

    with pytest.raises(RuntimeError):
        run_guarded("check_protocols", boom)

    store = Store(db)
    runs = store.job_runs()
    store.close()
    assert runs[0]["status"] == "error"
    assert "Ratsinfo nicht erreichbar" in runs[0]["error"]
    assert runs[0]["stats"] is None


def test_job_runs_filtert_nach_job_und_sortiert_neueste_zuerst(db):
    run_guarded("check_council", lambda: {"n": 1})
    run_guarded("backup_db", lambda: None)
    run_guarded("check_council", lambda: {"n": 2})

    store = Store(db)
    council = store.job_runs(job="check_council")
    store.close()

    assert [r["stats"]["n"] for r in council] == [2, 1]


def test_registry_deckt_die_cron_eintraege_ab():
    """Die Übersicht kann nur zeigen, was in der Registry steht — jeder Job aus
    der crontab braucht dort einen Eintrag mit Takt und Toleranz."""
    assert {j["key"] for j in JOBS} == {
        "check_council", "check_committees", "check_protocols", "weekly_enrich",
        # Vorläufige Ergebnisse aus der O1-Aufzeichnung der Ratssitzung, täglich.
        "check_council_videos",
        # Live-Mitschnitt des O1-Streams an Sitzungstagen, 13 Uhr UTC.
        "record_council_livestream",
        "check_vorlage_follows", "remind_setup", "backup_db",
        "abendmeldungen",   # Design 30a: N5 täglich 18 Uhr, N6 sonntags
        "check_presse",     # Stufe 3a: Stadt-Pressemitteilungen, täglich 5:15
        "social_kartentexte",  # ein Satz je Tagesordnungspunkt (LLM), täglich 7:45
        "render_plaene",    # P1: Planzeichnungen als Bilder, sonntags 4:30
        "check_finanzdaten",  # neue Haushalts-Jahrgänge, alle zwei Wochen
        # Der einzige Job, der selbst herunterlädt (oldenburg.de), alle vier
        # Wochen — die Quelle erscheint einmal im Jahr.
        "check_beteiligungsbericht",
        # Sichert die Statistik-Quellen versioniert, täglich: Die Stadt führt
        # kein Jahrbuch-Archiv, überschriebene Ausgaben sind endgültig weg.
        "archive_statistik",
        # Merkt, wenn ein Job aufhört zu laufen — und wenn die Platte
        # vollläuft. Ein Job, der gar nicht startet, stürzt nicht ab.
        "check_herzschlag",
    }
    for job in JOBS:
        assert BY_KEY[job["key"]] is job
        assert job["max_age_h"] > 0 and job["label"] and job["schedule"]


#: Skripte, die ``run_guarded`` benutzen, aber KEIN eigener Cron sind: Sie
#: werden von einem Elternjob gerufen (``weekly_enrich``, ``check_finanzdaten``)
#: oder von Hand. Sie schreiben trotzdem eigene ``job_runs``-Zeilen — das ist
#: gewollt, denn nur so verrät ein einzelner Schritt, dass er es war.
UNTERSCHRITTE = {
    # von weekly_enrich
    "backfill_anlagen_texte", "embed_anlagen",
    # von check_finanzdaten, sobald ein neues Dokument da ist
    "ingest_haushaltsvollzug", "ingest_haushaltssatzung", "ingest_gebuehren",
    "ingest_eigenbetriebe_abschluss", "ingest_nachbewilligungen",
    # Einmal-/Ops-Läufe von Hand, kein Takt
    "backfill_anlagen_ocr", "backfill_protokoll_seiten", "extract_wortbeitraege",
    "bereinige_kontaktdaten",
}


def _run_guarded_schluessel() -> dict[str, str]:
    """Jedes ``run_guarded`` in ``scripts/`` samt Datei — aus dem Syntaxbaum.

    Nicht per Import: Die Skripte ziehen beim Laden `.env`, Netz und Modelle
    nach. Der Baum reicht, weil der Schlüssel immer ein Literal ist oder eine
    Modul-Konstante (``JOB = "…"``).
    """
    import ast

    aus: dict[str, str] = {}
    for pfad in sorted((WURZEL / "scripts").glob("*.py")):
        baum = ast.parse(pfad.read_text(encoding="utf-8"))
        konstanten = {n.targets[0].id: n.value.value for n in ast.walk(baum)
                      if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name)
                      and isinstance(n.value, ast.Constant)}
        for knoten in ast.walk(baum):
            if (isinstance(knoten, ast.Call)
                    and getattr(knoten.func, "id", "") == "run_guarded" and knoten.args):
                erstes = knoten.args[0]
                schluessel = (erstes.value if isinstance(erstes, ast.Constant)
                              else konstanten.get(getattr(erstes, "id", "")))
                if schluessel:
                    aus[schluessel] = pfad.name
    return aus


def test_jeder_bewachte_lauf_ist_eingeordnet():
    """Wer in ``job_runs`` schreibt, gehört ins Register ODER in UNTERSCHRITTE.

    **Wogegen das steht.** Der Test darüber hält das Register gegen eine von
    Hand abgeschriebene Liste — er prüft also nur, dass zwei Listen im selben
    Repo übereinstimmen, und hat elf Wochen lang nicht bemerkt, dass
    ``social_kartentexte`` täglich auf Prod lief, ohne Register-Eintrag und
    ohne ``run_guarded``. Dieser hier misst gegen den QUELLTEXT: Ein neues
    Skript mit ``run_guarded`` muss eine Heimat bekommen, bevor es grün wird.
    """
    fremd = sorted(set(_run_guarded_schluessel()) - {j["key"] for j in JOBS} - UNTERSCHRITTE)
    assert not fremd, (
        f"{fremd} schreiben nach job_runs, stehen aber weder in kern/jobs.py "
        f"noch in UNTERSCHRITTE. Ist es ein Cron: Eintrag in kern/jobs.py "
        f"(Takt + max_age_h), sonst hier eintragen.")


def test_unterschritte_liste_hat_keine_leichen():
    """Andere Richtung: Ein Eintrag, den es nicht mehr gibt, muss auffallen."""
    schluessel = set(_run_guarded_schluessel())
    tot = sorted(UNTERSCHRITTE - schluessel)
    assert not tot, (f"{tot} stehen in UNTERSCHRITTE, benutzen aber kein "
                     f"run_guarded mehr — Eintrag entfernen.")


def test_registrierter_job_hat_auch_run_guarded():
    """Ein Register-Eintrag ohne ``run_guarded`` bliebe im Panel ewig auf
    „noch kein Lauf erfasst" stehen, ohne dass jemand den Grund sieht."""
    schluessel = set(_run_guarded_schluessel())
    ohne = sorted({j["key"] for j in JOBS} - schluessel)
    assert not ohne, (
        f"{ohne} stehen im Register, aber kein Skript ruft run_guarded damit — "
        f"das Panel zeigte sie dauerhaft als „noch kein Lauf erfasst“.")
def test_kennzahlen_ueberleben_einen_fehlschlag(tmp_path, monkeypatch):
    """Ein gescheiterter Lauf behält seine Bilanz — sonst fehlt sie genau dann,
    wenn sie gebraucht wird.

    ``run_guarded`` schrieb bei jeder Exception ``stats = None``. Ein
    ``weekly_enrich``, das einen von 18 Schritten verliert, hinterließ damit
    „error" und einen Traceback — welcher Schritt es war, stand nur im Log auf
    dem Server. ``JobFehler`` trägt die Kennzahlen mit.
    """
    from kern.alerts import JobFehler

    monkeypatch.setenv("RATSLOTSE_DB", str(tmp_path / "ratslotse.sqlite"))

    def kaputt():
        raise JobFehler("ein Schritt hat nicht geliefert",
                        {"Schritte gesamt": 3, "davon fehlgeschlagen": 1})

    with pytest.raises(JobFehler):
        run_guarded("weekly_enrich", kaputt)

    store = Store(tmp_path / "ratslotse.sqlite")
    lauf = store.job_runs("weekly_enrich")[0]
    store.close()
    assert lauf["status"] == "error"
    assert lauf["stats"] == {"Schritte gesamt": 3, "davon fehlgeschlagen": 1}
    assert "ein Schritt hat nicht geliefert" in lauf["error"]


def test_gewoehnlicher_absturz_bleibt_ohne_kennzahlen(tmp_path, monkeypatch):
    """Die Gegenprobe: Ein Job, der einfach fliegt, hat nichts zu berichten —
    und darf keine erfundenen Zahlen erzeugen."""
    monkeypatch.setenv("RATSLOTSE_DB", str(tmp_path / "ratslotse.sqlite"))

    with pytest.raises(ValueError):
        run_guarded("check_council", lambda: (_ for _ in ()).throw(ValueError("bumm")))

    store = Store(tmp_path / "ratslotse.sqlite")
    lauf = store.job_runs("check_council")[0]
    store.close()
    assert lauf["status"] == "error" and lauf["stats"] is None


def test_weekly_enrich_protokolliert_jeden_schritt(monkeypatch):
    """Die Schritt-Bilanz entsteht im Lauf selbst — 16 der 18 Schritte rufen
    kein ``run_guarded`` und haben deshalb keine eigene ``job_runs``-Zeile."""
    import subprocess

    from kern.alerts import SCHRITTE_SCHLUESSEL
    from scripts import weekly_enrich as we

    monkeypatch.setattr(we, "STEPS", [("Erster", "a.py"), ("Zweiter", "b.py --limit 5")])

    class Ergebnis:
        def __init__(self, code): self.returncode = code

    monkeypatch.setattr(subprocess, "run",
                        lambda befehl, **kw: Ergebnis(0 if befehl[1].endswith("a.py") else 1))
    with pytest.raises(Exception) as fehler:
        we._guarded_main()

    schritte = fehler.value.kennzahlen[SCHRITTE_SCHLUESSEL]
    assert [(s["name"], s["status"]) for s in schritte] == [("Erster", "ok"), ("Zweiter", "error")]
    # Das Argument gehört zum Schritt, nicht zum Namen — es steht mit im
    # Protokoll, damit „--limit 500" nachvollziehbar bleibt.
    assert schritte[1]["script"] == "b.py --limit 5"
    assert all(s["duration_s"] is not None for s in schritte)
    # Und NUR die Liste: Eine abgeleitete Zahl daneben wäre eine zweite
    # Darstellung derselben Tatsache — gezählt wird beim Anzeigen.
    assert set(fehler.value.kennzahlen) == {SCHRITTE_SCHLUESSEL}
