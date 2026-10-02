"""Suche über Akten (Plan „Akte“, Phase 3, Schalter ``akten-suche``).

Die heutige Suche findet, was der Frage ÄHNLICH klingt. Was zu demselben
Vorgang GEHÖRT, aber anders klingt, fehlt: die Bürgschaft und der
Bebauungsplan zum Stadion, die Aussage der Verwaltung zum Schlossplatz unter
TOP „Spielleitplanung“, die EU-Genehmigung vom August. Hier wird die Suche
zum Einstieg: Ihre besten Treffer bestimmen die Akte
(``council.matters.akte_von``), und aus der Akte kommt zusätzlich, was die
Antwort braucht — ausgewählt, nicht alles: Eine Akte hat im Schnitt 28
Beschlüsse und 260 Wortbeiträge (eval/run_akten.py, 02.10.2026).

Was ausgewählt wird:

- **Beschlüsse**: die neuesten der Akte (Hauptbeschlüsse, keine
  Teilabstimmungen) — bei einer Stand-Frage ist die letzte Station die Antwort,
  und genau die verlor gegen ähnlicher klingende ältere Treffer.
- **Wortbeiträge**: die der Frage nächsten (Vektor, ohne Cross-Encoder) und
  dazu immer die jüngsten Aussagen der Verwaltung — Zusagen und
  Protokollnotizen sind kurz und nüchtern und verlieren jedes Ranking.
- **Pressemitteilungen**: die neuesten der Akte.

Die heutigen Kanäle bleiben; die Akte ERGÄNZT sie. Was sie ersetzt, kommt in
Phase 5 raus — erst nachdem es gemessen ist.
"""
from __future__ import annotations

import logging
from typing import Any

log = logging.getLogger("council.akte_suche")

#: Wie viele der besten Suchtreffer die Akte bestimmen.
EINSTIEG = 3
#: So viele Beschlüsse der Akte kommen höchstens zusätzlich in den Kontext.
BESCHLUESSE = 12
#: Wortbeiträge: die so vielen der Akte, deren Vektor der Frage am nächsten
#: liegt — OHNE Cross-Encoder. Gemessen an den Gold-Fällen (02.10.2026): 20
#: nach Vektor brachten 20 von 52 Debatten-Belegen in 17 ms; 40 nach Vektor
#: und dann 10 nach Cross-Encoder 21 von 52 in 573 ms, 200 Paare durch den
#: Cross-Encoder dauerten 9–11 s. Innerhalb einer Akte ist schon alles beim
#: Thema; dort trennt der Cross-Encoder kaum noch.
BEITRAEGE = 20
#: Dazu immer so viele jüngste Aussagen der Verwaltung.
VERWALTUNG = 4
PRESSE = 5


def _ist_verwaltung(w: dict) -> bool:
    sprecher = (w.get("speaker") or "").lower()
    return w.get("kind") == "pledge" or sprecher.startswith("verwaltung")


def _naechste(store: Any, frage: str, beitraege: list[dict]) -> list[dict]:
    """Die ``BEITRAEGE`` Beiträge, deren Vektor der Frage am nächsten liegt.

    Ohne Vektoren (Index fehlt, fastembed fehlt) die neuesten — die Liste kommt
    schon neueste zuerst.
    """
    if len(beitraege) <= BEITRAEGE:
        return beitraege
    try:
        from council import embeddings as emb

        ids, mat = emb._wb_matrix(store)
        zeile = {wid: i for i, wid in enumerate(ids)}
        mit = [w for w in beitraege if w["id"] in zeile]
        if not mit:
            return beitraege[:BEITRAEGE]
        qv = emb.embed([frage])[0]
        werte = mat[[zeile[w["id"]] for w in mit]] @ qv
        rang = sorted(range(len(mit)), key=lambda i: -float(werte[i]))[:BEITRAEGE]
        return [mit[i] for i in rang]
    except Exception:  # noqa: BLE001 — ohne Vektoren die neuesten
        return beitraege[:BEITRAEGE]


def material(store: Any, frage: str, candidates: list[dict]) -> dict:
    """Was die Akte zu den besten Treffern beisteuert.

    ``{"decisions": [...], "speeches": [...], "press": [...], "akte": {...}}``;
    Beschlüsse neueste zuerst (der Aufrufer nimmt, was noch nicht im Kontext
    steht), Wortbeiträge und Presse fertig ausgewählt. Leer, wenn es keine
    Grundakten gibt (Tabellen fehlen, Aufbau lief noch nicht) — dann bleibt
    alles beim heutigen Weg.
    """
    from council import matters

    leer: dict = {"decisions": [], "speeches": [], "press": [], "akte": {}}
    einstieg = [c["id"] for c in candidates[:EINSTIEG] if c.get("id")]
    if not einstieg:
        return leer
    try:
        akte = matters.akte_von(store, einstieg)
    except Exception as exc:  # noqa: BLE001 — ohne Grundakten der heutige Weg
        log.info("Akte nicht verfügbar: %s", exc)
        return leer
    ids: dict[str, list[int]] = {}
    for art, iid in akte["items"]:
        ids.setdefault(art, []).append(iid)

    decisions = store.get_decisions_by_ids(
        sorted(store.hauptbeschluesse(sorted(ids.get("beschluss", [])))))
    decisions.sort(key=lambda d: (str(d.get("session_date") or ""), d["id"]), reverse=True)

    beitraege = store.wortbeitraege_by_ids(sorted(ids.get("debatte", [])))
    beitraege.sort(key=lambda w: (str(w.get("session_date") or ""), w["id"]), reverse=True)
    gewaehlt = _naechste(store, frage, beitraege)
    # Die jüngsten Aussagen der Verwaltung, unabhängig vom Ranking — aus der
    # GANZEN Akte, nicht nur aus dem Feld vor dem Cross-Encoder.
    juengste = sorted({str(w.get("session_date") or "") for w in beitraege if _ist_verwaltung(w)},
                      reverse=True)[:2]
    verwaltung = [w for w in beitraege if _ist_verwaltung(w)
                  and str(w.get("session_date") or "") in juengste][:VERWALTUNG]
    schon = {w["id"] for w in gewaehlt}
    speeches = gewaehlt + [w for w in verwaltung if w["id"] not in schon]

    presse = store.presse_by_ids(sorted(ids.get("presse", [])))
    presse.sort(key=lambda p: str(p.get("date") or ""), reverse=True)

    return {"decisions": decisions, "speeches": speeches, "press": presse[:PRESSE],
            "akte": {"matters": len(akte["matters"]),
                     "entities": [e["name"] for e in akte["entities"]],
                     "decisions": len(decisions), "speeches": len(beitraege),
                     "press": len(presse)}}
