"""Der Suchweg von „Frag den Rat": jeder Schritt mit Text und Ergebnis.

Anlass: Potsdams Ratsinformations-Chatbot zeigt beim Warten jeden Schritt
samt Fund („Suche: „Fahrradwege“ ↳ 12 Drucksachen gefunden“); Ratslotse
zeigte eine Zeile für die laufende Phase. Die Texte entstehen im Backend
(``council/search_trail.py``), damit Web und App sie ohne eigenes Wissen
anzeigen.

Zwei Zusagen halten die Tests fest: Der Rahmen bleibt ``step`` mit einer der
drei alten Phasen — die ausgelieferte App kennt keine andere —, und ein
Ergebnis-Rahmen folgt immer einem Text-Rahmen derselben Phase.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

_BACKEND = Path(__file__).resolve().parents[1] / "web" / "backend"
sys.path.insert(0, str(_BACKEND))

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402
from council import search_trail as trail  # noqa: E402
from scripts.grant_admin import grant_admin  # noqa: E402

RATSLOTSE_DB = os.environ["RATSLOTSE_DB"]
COUNCIL_DB = os.environ["COUNCIL_DB"]

#: Die Phasen, die die ausgelieferte iOS-App und ältere Web-Stände kennen.
ALTE_PHASEN = {"expand", "search", "answer"}


# ---- Die Texte --------------------------------------------------------------

def test_gefundene_beschluesse_mit_titeln_und_rest():
    funde = [{"title": f"Radweg Nr. {i}"} for i in range(12)]
    assert trail.found_detail(funde) == (
        "12 Beschlüsse gefunden: Radweg Nr. 0 · Radweg Nr. 1 und 10 weitere")


def test_ein_einzelner_fund_ohne_rest():
    assert trail.found_detail([{"title": "Fahrradstraße Lindenallee"}]) == (
        "1 Beschluss gefunden: Fahrradstraße Lindenallee")


def test_nichts_gefunden_sagt_das():
    assert trail.found_detail([]) == "Keine passenden Beschlüsse gefunden"


def test_lange_titel_werden_an_einer_wortgrenze_gekuerzt():
    titel = "Bebauungsplan N-777 G (Donnerschwee, ehemalige Kaserne) – Satzungsbeschluss und Abwägung"
    kurz = trail.found_detail([{"title": titel}]).split(": ", 1)[1]
    assert kurz.endswith(" …")
    assert len(kurz) <= trail.TITLE_MAX + 2
    assert kurz[:-2] in titel


def test_suchbegriffe_nur_wenn_die_analyse_eigene_hat():
    """Beim Providerfehler sind die Begriffe die Frage selbst — die noch
    einmal Wort für Wort zu zeigen, sagt nichts."""
    frage = "Was wurde zu Radwegen beschlossen?"
    assert trail.analysis_detail(terms=frage, question=frage) is None
    assert trail.analysis_detail(terms="Radweg Fahrradstraße", question=frage) == (
        "Suchbegriffe: Radweg, Fahrradstraße")


def test_einordnung_nennt_ort_person_sitzung_und_geschaeftsordnung():
    zeile = trail.analysis_detail(
        terms="", question="x", place={"name": "Donnerschwee"}, person={"name": "Erika Muster"},
        sessions=[{"committee": "Rat", "session_date": "2026-11-24"}], procedure=True)
    assert zeile == ("Ort: Donnerschwee · Person: Erika Muster · Sitzung: Rat 24.11.2026"
                     " · Geschäftsordnung")


@pytest.mark.parametrize("n,erwartet", [(0, "keine Wortbeiträge"), (1, "1 Wortbeitrag"),
                                        (7, "7 Wortbeiträge")])
def test_mengen_stehen_als_zahl_da(n, erwartet):
    assert trail.count(n, "Wortbeitrag", "Wortbeiträge") == erwartet


def test_nachrecherche_nennt_ihre_anfragen():
    assert trail.follow_up_detail([], 0) == "Keine Lücke gefunden"
    assert trail.follow_up_detail(["Radverkehrskonzept"], 2) == (
        "2 weitere Beschlüsse · nachgesucht: „Radverkehrskonzept“")
    assert trail.follow_up_detail(["Radverkehrskonzept"], 0) == (
        "Nichts Neues · nachgesucht: „Radverkehrskonzept“")


def test_suchtext_folgt_dem_weg_der_auswahl():
    ort = {"name": "Kreyenbrück"}
    assert trail.search_text(latest_place=True, overview=False, place=ort) == (
        "Neueste Beschlüsse zu Kreyenbrück laden")
    assert trail.search_text(latest_place=False, overview=True, place=ort) == (
        "Beschlüsse zu Kreyenbrück sichten")
    assert trail.search_text(latest_place=False, overview=False, place=None) == (
        "Beschlüsse durchsuchen")


# ---- Durch den Strom --------------------------------------------------------

@pytest.fixture(autouse=True)
def fresh_dbs():
    for base in (RATSLOTSE_DB, COUNCIL_DB):
        for suffix in ("", "-wal", "-shm"):
            Path(base + suffix).unlink(missing_ok=True)
    yield


@pytest.fixture
def client():
    c = TestClient(app)
    c.post("/api/auth/register", json={"display_name": "Testkonto", "email": "admin@example.org",
                                       "password": "password123"})
    grant_admin("admin@example.org", RATSLOTSE_DB)
    return c


FUNDE = [
    {"id": 101, "title": "Fahrradstraße Lindenallee", "score": 0.91,
     "session_date": "2026-10-20", "committee": "Verkehrsausschuss"},
    {"id": 102, "title": "Radweg Ammerländer Heerstraße", "score": 0.84,
     "session_date": "2026-06-02", "committee": "Rat"},
]


def _schritte(client, monkeypatch) -> list[dict]:
    from app.routers import council as council_router
    from council import qa as qa_mod

    frage = "Was wurde zuletzt zu Fahrradwegen beschlossen?"
    monkeypatch.setattr(qa_mod, "analyse_query", lambda *a, **k: {
        "question": frage, "terms": "Radweg Fahrradstraße Radverkehr", "kind": "topic",
        "party": None, "variants": [], "eng": False})
    monkeypatch.setattr(council_router, "_qa_retrieve",
                        lambda *a, **k: ([dict(f) for f in FUNDE], "semantisch"))
    with client.stream("POST", "/api/council/ask", json={"question": frage}) as antwort:
        assert antwort.status_code == 200
        roh = "".join(antwort.iter_text())
    rahmen = [json.loads(z[6:]) for z in roh.splitlines() if z.startswith("data: ")]
    return [r for r in rahmen if r["type"] == "step"]


def test_der_strom_meldet_einordnung_fund_und_antwort(client, monkeypatch):
    schritte = _schritte(client, monkeypatch)
    texte = [s.get("text") for s in schritte if s.get("text")]
    ergebnisse = [s.get("detail") for s in schritte if s.get("detail")]

    assert texte[0] == "Frage einordnen"
    assert "Beschlüsse durchsuchen" in texte
    assert texte[-1] == "Antwort schreiben"
    assert "Suchbegriffe: Radweg, Fahrradstraße, Radverkehr" in ergebnisse
    assert ("2 Beschlüsse gefunden: Fahrradstraße Lindenallee · "
            "Radweg Ammerländer Heerstraße") in ergebnisse


def test_nur_die_alten_phasen_und_jedes_ergebnis_hat_seinen_schritt(client, monkeypatch):
    """Die App im Store wurde gegen die drei Phasen gebaut; ein Ergebnis ohne
    vorangehenden Text hinge im Web an einem fremden Schritt."""
    schritte = _schritte(client, monkeypatch)
    assert {s["step"] for s in schritte} <= ALTE_PHASEN
    offen = None
    for s in schritte:
        assert s.get("text") or s.get("detail"), s
        if s.get("text"):
            offen = s["step"]
        else:
            assert offen == s["step"], f"Ergebnis ohne passenden Schritt: {s}"
