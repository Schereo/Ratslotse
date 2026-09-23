"""Wächter für ``eval/cases_fakten_rat.json`` — die Fakten-Eval außerhalb des Haushalts.

Die Fälle sind Daten, keine Logik; kaputt gehen sie trotzdem, und zwar still:
Ein Goldwert ohne Quelle lässt sich nicht nachprüfen, eine Zahl als Zeichenkette
fällt im Abgleich nie auf, eine Lotti-Frage, die Lotti sofort ans Archiv
weiterreicht, misst gar nichts. Die Formatregeln stehen in der Spezifikation
(Fallformat für ``cases_fakten_haushalt.json`` und ``cases_fakten_rat.json``);
der Baukasten ist ``eval/build_fakten_rat.py``.

Die Tests gegen die Datenbank laufen nur, wenn ``data/council.sqlite`` da ist
(lokal nach ``scripts/lokale_daten.py setz``) — die CI hat keine Ratsdaten.
"""
from __future__ import annotations

import json
import sqlite3
from collections import Counter
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parents[1]
FAELLE_DATEI = WURZEL / "eval" / "cases_fakten_rat.json"
DB = WURZEL / "data" / "council.sqlite"
NEU_BAUEN = "python eval/build_fakten_rat.py --stichtag <tag>"

FAELLE: list[dict] = json.loads(FAELLE_DATEI.read_text(encoding="utf-8"))

PFLICHT = ("id", "kanal", "frage", "kategorie", "antwort_in_daten", "gold", "verboten", "notiz")
KANAELE = {"lotti", "rat"}
LOTTI_ROUTEN = {"/council/decision", "/council/sitzung", "/council/person",
                "/council/ort", "/council/thema"}
REF_SCHLUESSEL = {"decision_id", "ksinr", "slug", "place_id", "year", "area"}
#: Welche Kennung eine Seite trägt — dieselbe Zuordnung wie im Web-Client.
REF_JE_ROUTE = {"/council/decision": "decision_id", "/council/sitzung": "ksinr",
                "/council/person": "slug", "/council/ort": "place_id", "/council/thema": "slug"}


def _ist_zahl(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _fall_ids(pred) -> list[str]:
    return [f.get("id", "?") for f in FAELLE if pred(f)]


def test_pflichtfelder_und_eindeutige_ids():
    fehlend = [(f.get("id", "?"), k) for f in FAELLE for k in PFLICHT if k not in f]
    assert not fehlend, f"Pflichtfelder fehlen: {fehlend} — {NEU_BAUEN}"
    doppelt = [i for i, n in Counter(f["id"] for f in FAELLE).items() if n > 1]
    assert not doppelt, f"doppelte Fall-IDs: {doppelt}"
    leer = _fall_ids(lambda f: not str(f["frage"]).strip() or not str(f["kategorie"]).strip())
    assert not leer, f"leere Frage oder Kategorie: {leer}"
    assert not _fall_ids(lambda f: f["kanal"] not in KANAELE), "kanal muss lotti oder rat sein"
    assert not _fall_ids(lambda f: not isinstance(f["antwort_in_daten"], bool))


def test_lotti_faelle_tragen_route_und_passende_kennung():
    """Eine Lotti-Frage ohne Kennung erklärt die SEITE, nicht den Gegenstand."""
    kaputt = []
    for f in FAELLE:
        if f["kanal"] == "rat":
            if "route" in f or "refs" in f:
                kaputt.append((f["id"], "route/refs nur bei lotti"))
            continue
        if f.get("route") not in LOTTI_ROUTEN:
            kaputt.append((f["id"], f"route {f.get('route')!r}"))
            continue
        refs = f.get("refs") or {}
        if set(refs) - REF_SCHLUESSEL:
            kaputt.append((f["id"], f"unbekannte refs {sorted(set(refs) - REF_SCHLUESSEL)}"))
        if REF_JE_ROUTE[f["route"]] not in refs:
            kaputt.append((f["id"], f"{f['route']} braucht {REF_JE_ROUTE[f['route']]}"))
    assert not kaputt, kaputt


def test_gold_und_verboten_sind_wohlgeformt():
    """Jede Quelle gesetzt, jede Zahl eine Zahl, jedes Textstück nicht leer."""
    kaputt = []
    for f in FAELLE:
        for g in f["gold"]:
            wo = (f["id"], g.get("art"))
            if not str(g.get("quelle") or "").strip():
                kaputt.append((*wo, "quelle fehlt"))
            if g.get("art") in ("zahl", "id"):
                if not _ist_zahl(g.get("wert")):
                    kaputt.append((*wo, f"wert {g.get('wert')!r} ist keine Zahl"))
                if g["art"] == "id" and not isinstance(g.get("wert"), int):
                    kaputt.append((*wo, "Beschluss-ID muss ganzzahlig sein"))
                if g["art"] == "zahl":
                    if not str(g.get("einheit") or "").strip():
                        kaputt.append((*wo, "einheit fehlt"))
                    tol = g.get("toleranz", 0)
                    if not _ist_zahl(tol) or not 0 <= tol < 0.2:
                        kaputt.append((*wo, f"toleranz {tol!r} (relativ, 0 ≤ t < 0,2)"))
                    if "jahr" in g and not isinstance(g["jahr"], int):
                        kaputt.append((*wo, "jahr muss ganzzahlig sein"))
            elif g.get("art") == "text":
                muss = g.get("muss")
                if not isinstance(muss, list) or not muss:
                    kaputt.append((*wo, "muss ist leer"))
                    continue
                for stueck in muss:
                    alternativen = stueck if isinstance(stueck, list) else [stueck]
                    if not alternativen or not all(isinstance(a, str) and a.strip()
                                                   for a in alternativen):
                        kaputt.append((*wo, f"leeres Textstück {stueck!r}"))
            else:
                kaputt.append((*wo, "art muss zahl, text oder id sein"))
        for v in f["verboten"]:
            if not str(v.get("grund") or "").strip():
                kaputt.append((f["id"], "verboten", "grund fehlt"))
            if v.get("art") == "zahl" and not _ist_zahl(v.get("wert")):
                kaputt.append((f["id"], "verboten", f"wert {v.get('wert')!r} ist keine Zahl"))
    assert not kaputt, kaputt


def test_verbotene_zahl_ist_nie_zugleich_gold():
    """Sonst wäre der Fall in sich unerfüllbar."""
    widerspruch = [f["id"] for f in FAELLE
                   if {g["wert"] for g in f["gold"] if g["art"] == "zahl"}
                   & {v["wert"] for v in f["verboten"] if v.get("art") == "zahl"}]
    assert not widerspruch, widerspruch


def test_antwort_in_daten_und_gold_passen_zusammen():
    """Mit Antwort: Gold nötig. Ohne: kein Gold — richtig ist die Absage.

    Die Notiz ist bei Fällen ohne Antwort Pflicht: Sie sagt, wogegen die Lücke
    geprüft wurde. Ohne sie ist eine Absage nicht von einem übersehenen Beleg
    zu unterscheiden.
    """
    ohne_gold = _fall_ids(lambda f: f["antwort_in_daten"] and not f["gold"])
    assert not ohne_gold, f"antwort_in_daten=true ohne Gold: {ohne_gold}"
    mit_gold = _fall_ids(lambda f: not f["antwort_in_daten"] and f["gold"])
    assert not mit_gold, f"antwort_in_daten=false mit Gold: {mit_gold}"
    ohne_notiz = _fall_ids(lambda f: not f["antwort_in_daten"] and not f["notiz"].strip())
    assert not ohne_notiz, f"Absage-Fälle ohne Begründung: {ohne_notiz}"


def test_mischung_wie_bestellt():
    """~80 Fälle, rund 40 % Lotti, etwa ein Dutzend ohne Antwort, Verwechslungen dabei."""
    n = len(FAELLE)
    lotti = sum(f["kanal"] == "lotti" for f in FAELLE)
    offen = sum(not f["antwort_in_daten"] for f in FAELLE)
    verwechslung = sum(f["kategorie"].startswith("verwechslung/") for f in FAELLE)
    assert 70 <= n <= 110, n
    assert 0.3 <= lotti / n <= 0.5, (lotti, n)
    assert offen >= 10, offen
    assert verwechslung >= 5, verwechslung


def test_lotti_fragen_erreichen_das_modell():
    """Eine Lotti-Frage, die nie beim Modell ankommt, misst nichts.

    Zwei Wege überspringen es: eine generische Frage („Was sehe ich hier?")
    beantwortet Lotti aus dem Haus, und eine Archivfrage ohne „hier" reicht sie
    sofort an Frag den Rat weiter (``archiv_sofort``). Die Fälle sollen den
    Lotti-Kontext messen — also keiner von beiden.
    """
    from council.assistant import archiv_sofort, generische_frage

    lotti = [f for f in FAELLE if f["kanal"] == "lotti"]
    weiter = [f["id"] for f in lotti if archiv_sofort(f["frage"])]
    assert not weiter, f"gehen sofort ins Archiv (ein „hier“ fehlt): {weiter}"
    generisch = [f["id"] for f in lotti if generische_frage(f["frage"])]
    assert not generisch, f"beantwortet Lotti ohne Modell: {generisch}"


# --------------------------------------------------------------------------- #
# Gegen die echten Daten — nur lokal
# --------------------------------------------------------------------------- #

braucht_daten = pytest.mark.skipif(
    not DB.exists(), reason="data/council.sqlite fehlt — scripts/lokale_daten.py hol && setz")


@braucht_daten
def test_kennungen_existieren_in_der_datenbank():
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    beschluesse = {r[0] for r in conn.execute("SELECT id FROM council_decisions")}
    sitzungen = {r[0] for r in conn.execute("SELECT ksinr FROM council_sessions")}
    fehlt = []
    for f in FAELLE:
        for g in f["gold"]:
            if g["art"] == "id" and g["wert"] not in beschluesse:
                fehlt.append((f["id"], "gold id", g["wert"]))
        refs = f.get("refs") or {}
        if "decision_id" in refs and refs["decision_id"] not in beschluesse:
            fehlt.append((f["id"], "refs.decision_id", refs["decision_id"]))
        if "ksinr" in refs and refs["ksinr"] not in sitzungen:
            fehlt.append((f["id"], "refs.ksinr", refs["ksinr"]))
    assert not fehlt, (f"{fehlt} — die IDs stammen aus einem anderen Abzug? "
                       f"{NEU_BAUEN} löst sie über natürliche Schlüssel neu auf")


@braucht_daten
def test_seiten_kennungen_loesen_auf(tmp_path):
    """Personen-Slug und Orts-ID so, wie Lottis Gegenstands-Block sie auflöst.

    Auf einer Kopie: ``CouncilStore`` migriert beim Öffnen, und die echte
    Datei unter data/ fasst die Suite nicht schreibend an (conftest.py)."""
    from council.store import CouncilStore

    kopie = tmp_path / "council.sqlite"
    quelle = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    ziel = sqlite3.connect(kopie)
    quelle.backup(ziel)
    quelle.close()
    ziel.close()
    store = CouncilStore(kopie)
    kaputt = []
    for f in FAELLE:
        refs, route = f.get("refs") or {}, f.get("route")
        if route == "/council/person" and not store.member_name(refs["slug"]):
            kaputt.append((f["id"], refs["slug"]))
        if route == "/council/ort" and not store.resolve_place(refs["place_id"]):
            kaputt.append((f["id"], refs["place_id"]))
        if route == "/council/thema":
            from council.topics import POLICY_FIELDS
            if refs["slug"] not in POLICY_FIELDS:
                kaputt.append((f["id"], refs["slug"]))
    assert not kaputt, kaputt
