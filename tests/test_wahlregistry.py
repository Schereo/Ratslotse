"""Die Wahl-Registry: eine Datei je Wahl, und alles darin muss es geben.

`kommunalwahl/wahlen/` beantwortet die Frage „welche Wahl zeigt die Seite?"
(`web/backend/app/election/elections.py`). Vorher stand die Antwort in acht
Modulkonstanten; ein Tippfehler war dort ein Syntaxfehler oder ein 404 beim
Abruf. In einer JSON-Datei ist er beides nicht — er ist eine leere Seite am
Wahlabend. Deshalb diese Wächter.

Sie prüfen beide Richtungen: dass jede Datei vollständig ist UND dass keine
Angabe doppelt und widersprüchlich im Baum liegt (Sitzzahl hier wie im
Register, Referenzordner hier wie in `kommunalwahl/`).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL / "web" / "backend"))

from app.election import elections, reference, register  # noqa: E402

DATEIEN = sorted((WURZEL / "kommunalwahl" / "wahlen").glob("*.json"))
ALLE = sorted(elections.all().values(), key=lambda w: w.slug)


def test_es_gibt_wahlen():
    assert DATEIEN, "kommunalwahl/wahlen/ ist leer — dann zeigt /api/wahlabend gar nichts."
    assert len(ALLE) == len(DATEIEN)


@pytest.mark.parametrize("wahl", ALLE, ids=lambda w: w.slug)
def test_pflichtangaben(wahl: elections.Election):
    assert wahl.kind in elections.KINDS, f"„{wahl.kind}“ ist keine bekannte Wahlart"
    assert wahl.status in elections.STATUS
    assert wahl.title and wahl.short_title
    assert wahl.date == wahl.polls_close.date().isoformat(), (
        "„date“ und der Tag von „polls_close“ müssen derselbe sein — sonst zeigt der "
        "Countdown auf einen anderen Tag als die Überschrift.")
    assert wahl.polls_close.tzinfo is not None, (
        "„polls_close“ ohne Zeitzone: Der Abruftakt schaltete dann um 18 Uhr UTC um, "
        "also zwei Stunden zu spät.")
    assert wahl.source.base.startswith("https://"), "Die Quelle wird über TLS geholt."
    assert not wahl.source.base.endswith("/")


@pytest.mark.parametrize("wahl", ALLE, ids=lambda w: w.slug)
def test_ratswahl_traegt_register_referenz_und_dateien(wahl: elections.Election):
    if wahl.kind != "council":
        return
    assert wahl.register_path and wahl.register_path.is_file(), f"{wahl.slug}: „register“ zeigt ins Leere"
    assert wahl.reference_folder and wahl.reference_folder.is_dir(), f"{wahl.slug}: „reference“ zeigt ins Leere"
    reference.meta_path(wahl.reference_folder)  # wirft, wenn der Ordner keiner ist
    assert set(wahl.source.files) == {"city", "areas", "districts"}, (
        "Eine Ratswahl braucht alle drei Open-Data-Dateien; eine fehlende sähe aus wie "
        "„noch nicht ausgezählt“.")
    assert wahl.seats > 0
    assert elections.mayor_of(wahl) is not None, (
        f"{wahl.slug}: kein „mayor“ — dann steht auf der Seite keine OB-Zahl.")


@pytest.mark.parametrize("wahl", ALLE, ids=lambda w: w.slug)
def test_ob_wahl_traegt_ihre_kandidaturen(wahl: elections.Election):
    if wahl.kind != "mayor":
        return
    assert wahl.candidates is not None, f"{wahl.slug}: „candidates“ fehlt"
    datei, schluessel = wahl.candidates
    assert datei.is_file(), f"{wahl.slug}: {datei} gibt es nicht"
    roh = json.loads(datei.read_text(encoding="utf-8"))
    assert roh.get(schluessel), f"{wahl.slug}: „{schluessel}“ fehlt in {datei.name} oder ist leer"
    assert wahl.source.presentation_id, "Ohne Wahl-Id ist die OB-Wahl nicht abrufbar (sie hat keine CSV)."


def test_sitzzahl_steht_nicht_widersprüchlich_doppelt():
    """Die Sitzzahl steht in der Registry UND im Register.

    Das ist Absicht — ``service._bare`` greift, wenn genau das Register nicht
    lesbar ist. Eine doppelte Angabe ohne Wächter wäre aber eine Falle: Wer
    ``kandidaten.json`` neu erzeugt und die Registry vergisst, bekäme in der
    Reißleine eine falsche Zahl und merkte es nie.
    """
    for wahl in ALLE:
        if wahl.kind != "council" or not wahl.register_path:
            continue
        reg = register.load(wahl.register_path)
        assert wahl.seats == reg.seats, (
            f"{wahl.slug}: Registry sagt {wahl.seats} Sitze, {wahl.register_path.name} sagt {reg.seats}")
        assert wahl.title == reg.title, f"{wahl.slug}: Titel weicht von {wahl.register_path.name} ab"
        assert wahl.date == reg.date, f"{wahl.slug}: Datum weicht von {wahl.register_path.name} ab"


def test_slug_und_dateiname_sind_dasselbe():
    for datei in DATEIEN:
        roh = json.loads(datei.read_text(encoding="utf-8"))
        assert roh["slug"] == datei.stem


def test_active_ist_eindeutig_und_eine_ratswahl():
    wahl = elections.active()
    assert wahl.kind == "council"
    assert wahl.status != "entwurf"
    # Zweimal gefragt, zweimal dasselbe — die Vorgabe darf nicht von der
    # Reihenfolge im Dateisystem abhängen.
    assert elections.active().slug == wahl.slug
    juengste = max(w.date for w in ALLE if w.kind == "council" and w.status != "entwurf")
    assert wahl.date == juengste


def test_wahlabend_election_setzt_um_und_faellt_sauber_zurueck(monkeypatch, caplog):
    """Der Notausgang aus der ``.env`` — und was ein Tippfehler darin tut."""
    vorgabe = elections.active().slug
    monkeypatch.setenv("WAHLABEND_ELECTION", vorgabe)
    assert elections.active().slug == vorgabe

    # Eine OB-Wahl ist keine Ratswahl: Die Seite rechnet Sitze.
    monkeypatch.setenv("WAHLABEND_ELECTION", "ob-2026")
    assert elections.active().slug == vorgabe

    monkeypatch.setenv("WAHLABEND_ELECTION", "gibts-nicht")
    with caplog.at_level("WARNING"):
        assert elections.active().slug == vorgabe
    assert any("gibts-nicht" in r.getMessage() for r in caplog.records), (
        "Ein unbekannter Wert muss sich im Log melden — sonst sieht eine wirkungslose "
        ".env-Zeile aus wie eine wirksame.")


def test_registry_kennt_die_wahl_von_2026():
    """Der Bestand, 1:1 aus den Modulkonstanten übernommen (PR „Wahl-Registry“).

    Weicht hier etwas ab, ist es kein Tippfehler in einem Test, sondern die
    Frage, ob die Seite noch dieselbe Wahl zeigt.
    """
    wahl = elections.get("ratswahl-2026")
    assert wahl is not None
    assert wahl.seats == 52 and wahl.date == "2026-09-13"
    assert wahl.source.base == "https://votemanager.kdo.de/20260913/03403000"
    assert wahl.source.api_path == "/daten/api/wahl_913"
    assert wahl.source.files["city"].endswith("Stadtratswahl-Stadt.csv")
    ob = elections.mayor_of(wahl)
    assert ob is not None and ob.source.api_path == "/daten/api/wahl_2552"
    assert ob.source.city_id == "ebene_-6360_id_10357"


# ------------------------------------------------------------------ Verlauf je Wahl

def test_verlauf_zieht_von_der_namenlosen_datei_um(tmp_path, monkeypatch):
    """Prod trägt den Abend als ``wahlabend-verlauf.json``; seit die Datei den
    Wahl-Slug im Namen hat, muss sie mitkommen — sonst zeigt die Seite nach
    dem Deploy eine leere Kurve, ohne dass irgendetwas fehlschlägt."""
    from app.election import history

    alt = tmp_path / "wahlabend-verlauf.json"
    alt.write_text(json.dumps([{"at": "2026-09-13T20:00:00+00:00", "districts_counted": 7,
                                "shares": {"spd": 20.0}, "seats": {"spd": 10}}]), encoding="utf-8")
    neu = tmp_path / "wahlabend-verlauf-ratswahl-2026.json"
    monkeypatch.setenv("WAHLABEND_HISTORY_FILE", str(neu))
    history.reset()

    assert len(history.points()) == 1, "Der Verlauf des Wahlabends ist verloren gegangen."
    assert neu.is_file() and not alt.exists()

    # Zweimal laufen darf nichts kaputt machen.
    history.reset()
    assert len(history.points()) == 1


def test_verlauf_heisst_nach_der_wahl(monkeypatch):
    from app.election import history

    monkeypatch.delenv("WAHLABEND_HISTORY_FILE", raising=False)
    assert history.path().name == f"wahlabend-verlauf-{elections.active().slug}.json", (
        "Zwei Wahlabende in derselben Datei ergäben eine Kurve, die mitten in der Nacht "
        "auf null zurückspringt.")
