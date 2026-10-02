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

#: Wie viele der besten Suchtreffer die Akte bestimmen. Gemessen am Gold-Set
#: (Anteil der Belege in Suche + Akten-Auswahl, 02.10.2026): 3 → 63,0 %,
#: 5 → 64,8 % — der fünfte Treffer trifft öfter die Pressemitteilungen.
EINSTIEG = 5
#: So viele Beschlüsse der Akte kommen höchstens zusätzlich in den Kontext.
BESCHLUESSE = 12
#: Wortbeiträge: die so vielen der Akte, deren Vektor der Frage am nächsten
#: liegt — OHNE Cross-Encoder. Gemessen an den Gold-Fällen (02.10.2026): 20
#: nach Vektor brachten 20 von 52 Debatten-Belegen in 17 ms; 40 nach Vektor
#: und dann 10 nach Cross-Encoder 21 von 52 in 573 ms, 200 Paare durch den
#: Cross-Encoder dauerten 9–11 s. Innerhalb einer Akte ist schon alles beim
#: Thema; dort trennt der Cross-Encoder kaum noch. Mit Einstieg 5: 20 Beiträge
#: 64,8 %, 30 → 69,1 %, 40 → 72,1 % — 30 als Mitte, weil jeder Beitrag den
#: Prompt verlängert und die Antwort das Material ohnehin nicht ausschöpft
#: (Phase 4).
BEITRAEGE = 30
#: Dazu immer so viele jüngste Aussagen der Verwaltung.
VERWALTUNG = 4
PRESSE = 5
#: So viele angekündigte Stationen (Beratungsfolge nach dem letzten
#: protokollierten Beschluss) höchstens.
ANGEKUENDIGT = 6


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

    leer: dict = {"decisions": [], "speeches": [], "press": [], "announced": [], "akte": {}}
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

    # Angekündigt: Stationen der Beratungsfolge NACH dem jüngsten
    # protokollierten Beschluss der Akte. Das Ratsinformationssystem trägt das
    # Ergebnis erst mit dem Protokoll ein, und das kommt vier bis sieben Wochen
    # später (Plan „Akte“, Schritt 0.5) — bis dahin ist die Tagesordnung der
    # jüngste Stand (Klinikum: Bürgschaft im Rat am 28.09.2026).
    neuester = max((str(d.get("session_date") or "")[:10] for d in decisions), default="")
    stationen = [st for st in store.deliberations_by_ids(sorted(ids.get("station", [])))
                 if str(st.get("date") or "")[:10] > neuester]
    stationen.sort(key=lambda st: str(st.get("date") or ""))

    return {"decisions": decisions, "speeches": speeches, "press": presse[:PRESSE],
            "announced": stationen[:ANGEKUENDIGT],
            "akte": {"matters": len(akte["matters"]),
                     "entities": [e["name"] for e in akte["entities"]],
                     "decisions": len(decisions), "speeches": len(beitraege),
                     "press": len(presse)}}


# --------------------------------------------------------------------------- #
# Phase 4: die Akte als Zeitleiste im Prompt (Schalter ``akten-zeitleiste``)
# --------------------------------------------------------------------------- #
#
# Die Antwort bekam bis hierhin sieben Blöcke — Beschlüsse, Debatten, Presse,
# Anlagen … — und musste den Verlauf selbst puzzeln. Gemessen (Phase 3, lokal
# 02.10.2026): Mit der Akte stieg das Material im Kontext von 52 auf 67 %, die
# Abdeckung der Antwort aber nur von 38 auf 43 %. Beim Mobilitätsplan lag alles
# vor, und die Antwort nannte den Ausschussweg trotzdem nicht. Eine datierte
# Zeitleiste, älteste zuerst, nimmt dem Modell das Puzzeln ab.

AKTE_REGEL = (
    "\n\nZUM VORGANG IN DER AKTE: Erzähle ihn in zeitlicher Reihenfolge — welches "
    "Gremium hat wann (Monat und Jahr) was empfohlen, beschlossen, abgelehnt, vertagt "
    "oder als behandelt erklärt — und ENDE mit dem aktuellen Stand aus den letzten "
    "Zeilen der Akte, auch wenn er nur angekündigt (noch nicht protokolliert) oder nur "
    "aus einer Pressemitteilung bekannt ist. Für den Vorgang sind Monat und Jahr "
    "ausdrücklich erwünscht, und die Regel „neueste zuerst“ gilt für ihn nicht. "
    "Unterscheide klar: empfohlen (Ausschuss) ≠ beschlossen (Rat) ≠ angekündigt ≠ "
    "abgelehnt ≠ gilt als behandelt."
)
AKTE_REGEL_ENG = (
    "\n\nZUM VORGANG IN DER AKTE: Nutze die letzten Zeilen der Akte, um den AKTUELLEN "
    "Stand richtig zu nennen — auch wenn er nur angekündigt oder nur aus einer "
    "Pressemitteilung bekannt ist. Keine Vorgeschichte."
)


def _datum(wert: Any) -> str:
    from council import qa
    return qa._datum_de(str(wert)) if wert else "ohne Datum"


def _beitrag_art(w: dict) -> str:
    sprecher = (w.get("speaker") or "")
    if "protokollnotiz" in sprecher.lower():
        return "Protokollnotiz der Verwaltung"
    if w.get("kind") == "pledge":
        return "Zusage"
    return {"inquiry": "Anfrage", "citizen_question": "Einwohnerfrage"}.get(
        w.get("kind") or "", "Wortbeitrag")


def zeitleiste(beschluesse: list[dict], beitraege: list[dict], presse: list[dict],
               angekuendigt: list[dict]) -> str:
    """Der Block „AKTE“: alles zum Vorgang, älteste Zeile zuerst."""
    from council import qa

    zeilen: list[tuple[str, int, str]] = []
    for c in beschluesse:
        zeilen.append((str(c.get("session_date") or ""), 0, "- " + qa._build_context([c])))
    for w in beitraege:
        wer = w.get("speaker") or "?"
        if w.get("party"):
            wer += f" ({w['party']})"
        text = (w.get("text") or "").strip()[:600]
        if w.get("answer"):
            text += f" — Antwort der Verwaltung: {(w['answer'] or '').strip()[:400]}"
        zeilen.append((str(w.get("session_date") or ""), 1,
                       f"- {_datum(w.get('session_date'))} · {w.get('committee') or ''} · "
                       f"{_beitrag_art(w)} von {wer}: {text}"))
    for pm in presse:
        zeilen.append((str(pm.get("date") or ""), 2,
                       f"- {_datum(pm.get('date'))} · Pressemitteilung der Stadt: "
                       f"{pm.get('title') or ''} — {(pm.get('auszug') or '').strip()[:400]}"))
    for st in angekuendigt:
        art = f" ({st['result']})" if st.get("result") else ""
        zeilen.append((str(st.get("date") or ""), 3,
                       f"- {_datum(st.get('date'))} · {st.get('committee') or ''} · "
                       f"ANGEKÜNDIGT{art}: {st.get('title') or st.get('template_number') or ''} — "
                       f"steht auf der Tagesordnung, ein Ergebnis ist noch nicht protokolliert"))
    if not zeilen:
        return ""
    zeilen.sort(key=lambda z: (z[0][:10], z[1]))
    return ("\nAKTE DES VORGANGS (alles, was zu dieser Sache gehört, älteste Zeile zuerst — "
            "die letzten Zeilen sind der aktuelle Stand. Beschlüsse mit [id] zitieren; "
            "Wortbeiträge und Pressemitteilungen NIE mit [id], sondern „Laut Protokoll …“ "
            "bzw. „Laut Pressemitteilung vom …“):\n"
            + "\n".join(z[2] for z in zeilen) + "\n")


def letzte_station(beschluesse: list[dict], presse: list[dict],
                   angekuendigt: list[dict]) -> dict | None:
    """Die jüngste Station der Akte, die die Antwort nennen muss — Beschluss,
    Pressemitteilung oder angekündigter Termin (Wortbeiträge zählen nicht)."""
    kandidaten = ([{"art": "beschluss", "datum": str(c.get("session_date") or ""), "c": c}
                   for c in beschluesse]
                  + [{"art": "presse", "datum": str(p.get("date") or ""), "c": p} for p in presse]
                  + [{"art": "angekuendigt", "datum": str(st.get("date") or ""), "c": st}
                     for st in angekuendigt])
    kandidaten = [k for k in kandidaten if k["datum"]]
    return max(kandidaten, key=lambda k: k["datum"][:10]) if kandidaten else None


_MONATE = ("Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August",
           "September", "Oktober", "November", "Dezember")


def nennt(antwort: str, station: dict) -> bool:
    """Nennt die Antwort diese Station? Beschluss: seine [id]. Sonst: Monat und
    Jahr der Station (so schreibt die Antwort Daten) oder das Datum in Ziffern."""
    if station["art"] == "beschluss" and f"[{station['c']['id']}]" in antwort:
        return True
    try:
        jahr, monat, tag = (int(x) for x in station["datum"][:10].split("-"))
    except ValueError:
        return False
    return (f"{_MONATE[monat - 1]} {jahr}" in antwort
            or f"{tag:02d}.{monat:02d}.{jahr}" in antwort
            or f"{tag}.{monat}.{jahr}" in antwort)


def zuletzt_satz(station: dict) -> str:
    """Der Satz, den der Server anhängt, wenn die Antwort den Stand verschweigt."""
    c = station["c"]
    if station["art"] == "beschluss":
        from council import outcome_note
        ergebnis = outcome_note.LABEL.get(c.get("outcome") or "", "")
        zusatz = f" ({ergebnis.split(' — ')[0].lower()})" if ergebnis else ""
        return (f"\n\n**Zuletzt:** {_datum(station['datum'])}, {c.get('committee') or 'Rat'}: "
                f"{(c.get('title') or '').strip()}{zusatz} [{c['id']}].")
    if station["art"] == "presse":
        return (f"\n\n**Zuletzt:** Laut Pressemitteilung vom {_datum(station['datum'])}: "
                f"{(c.get('title') or '').strip()}.")
    return (f"\n\n**Zuletzt:** Am {_datum(station['datum'])} steht "
            f"„{(c.get('title') or c.get('template_number') or '').strip()}“ im Gremium "
            f"{c.get('committee') or ''} auf der Tagesordnung; ein Ergebnis ist noch nicht "
            f"protokolliert.")


# --------------------------------------------------------------------------- #
# Die Zeitleiste im Chat (Schalter ``akten-zeitleiste``)
# --------------------------------------------------------------------------- #
#
# Dieselbe Akte, die das Modell als Block „AKTE“ liest, steht unter der
# Antwort als Grafik: Station für Station, mit dem Abstand dazwischen und
# einem Link je Station. Gebaut wird sie HIER, fertig formuliert — Web und
# App stellen nur dar (Tims Regel: Logik ins Backend, zwei Frontends).

#: Ab so vielen Tagen zwischen zwei Stationen ist der Abstand eine Pause
#: (gestrichelt). Ein halbes Jahr ohne neue Station ist im Rat eine Aussage —
#: beim Mobilitätsplan lag zwischen Priorisierung und nächstem Bericht über ein
#: Jahr.
PAUSE_TAGE = 183
#: Aufeinanderfolgende Beratungen ohne Abstimmung („gilt als behandelt“, ohne
#: Beschluss) werden EINE Zeile, wenn sie höchstens so weit auseinanderliegen —
#: beim Mobilitätsplan behandelten vier Fachausschüsse den Plan binnen fünf
#: Wochen, ohne abzustimmen; vier Zeilen dafür wären Lärm.
GRUPPE_TAGE = 45
#: Höchstens so viele Beschlüsse (die neuesten) — eine verklebte Akte kann
#: groß werden; ein Verlauf über 60 Stationen liest niemand.
ZEITLEISTE_MAX = 60
_OHNE_ABSTIMMUNG = ("settled", "no_decision")


def abstand_text(tage: int) -> str:
    """„6 Tage“, „8 Wochen“, „5 Monate“, „1 Jahr, 1 Monat“ — wie man es sagt."""
    if tage <= 0:
        return "am selben Tag"
    if tage < 14:
        return "1 Tag" if tage == 1 else f"{tage} Tage"
    if tage < 63:
        w = round(tage / 7)
        return "1 Woche" if w == 1 else f"{w} Wochen"
    monate = round(tage / 30.4375)
    if monate < 12:
        return "1 Monat" if monate == 1 else f"{monate} Monate"
    j, m = divmod(monate, 12)
    jahre = "1 Jahr" if j == 1 else f"{j} Jahre"
    if not m:
        return jahre
    return f"{jahre}, " + ("1 Monat" if m == 1 else f"{m} Monate")


def _tag(wert: Any) -> str:
    return str(wert or "")[:10]


def _tage(von: str, bis: str) -> int:
    from datetime import date
    return (date.fromisoformat(bis) - date.fromisoformat(von)).days


def _stimmen_text(d: dict) -> str | None:
    """„mehrheitlich, 17 Gegenstimmen“ — nur, was belegt ist."""
    from council.ergebnisse import VOTE_WORT

    teile = []
    if d.get("vote"):
        teile.append(VOTE_WORT.get(str(d["vote"]), str(d["vote"])))
    nein, enth = d.get("no_votes"), d.get("abstentions")
    if nein:
        teile.append(f"{int(nein)} Gegenstimme" + ("n" if int(nein) != 1 else ""))
    if enth:
        teile.append(f"{int(enth)} Enthaltung" + ("en" if int(enth) != 1 else ""))
    return ", ".join(teile) or None


def zeitleiste_anzeige(beschluesse: list[dict], presse: list[dict],
                       angekuendigt: list[dict]) -> dict | None:
    """Die Zeitleiste für die Oberfläche — ``None`` unter zwei Stationen.

    ``{"span": "3 Jahre, 1 Monat", "count": 21, "stations": [...]}``, älteste
    Station zuerst. Jede Station: ``date`` (ISO), ``date_end`` (bei einer
    Gruppe), ``kind`` (decision | group | press | announced), ``outcome``,
    ``title``, ``committee``, ``detail``, ``decision_id``, ``url``,
    ``members`` (bei einer Gruppe), ``gap_days``/``gap_label``/``pause`` (der
    Abstand zur vorigen Station; bei der ersten ``None``).
    """
    roh: list[dict] = []
    for d in sorted((d for d in beschluesse if _tag(d.get("session_date"))),
                    key=lambda d: (_tag(d.get("session_date")), d["id"]))[-ZEITLEISTE_MAX:]:
        roh.append({"date": _tag(d.get("session_date")), "kind": "decision",
                    "outcome": d.get("outcome"),
                    "title": " ".join(str(d.get("title") or "").split()),
                    "committee": d.get("committee"), "detail": _stimmen_text(d),
                    "decision_id": d["id"], "url": None})
    for p in presse:
        if _tag(p.get("date")):
            roh.append({"date": _tag(p.get("date")), "kind": "press", "outcome": None,
                        "title": " ".join(str(p.get("title") or "").split()),
                        "committee": None, "detail": "Pressemitteilung der Stadt",
                        "decision_id": None, "url": p.get("url")})
    for st in angekuendigt:
        if _tag(st.get("date")):
            roh.append({"date": _tag(st.get("date")), "kind": "announced", "outcome": None,
                        "title": " ".join(str(st.get("title") or st.get("template_number")
                                              or "").split()),
                        "committee": st.get("committee"),
                        "detail": "steht auf der Tagesordnung, noch kein Ergebnis",
                        "decision_id": None, "url": None})
    roh.sort(key=lambda s: (s["date"], {"decision": 0, "press": 1, "announced": 2}[s["kind"]]))
    if len(roh) < 2:
        return None

    stationen: list[dict] = []
    for s in roh:
        vorige = stationen[-1] if stationen else None
        ohne = s["kind"] == "decision" and s["outcome"] in _OHNE_ABSTIMMUNG
        if (ohne and vorige and vorige.get("_ohne")
                and _tage(vorige.get("date_end") or vorige["date"], s["date"]) <= GRUPPE_TAGE):
            if vorige["kind"] != "group":
                erste = {k: vorige[k] for k in ("date", "committee", "decision_id", "title")}
                vorige.update({"kind": "group", "members": [erste], "decision_id": None,
                               "detail": None})
            vorige["members"].append({k: s[k] for k in ("date", "committee", "decision_id",
                                                         "title")})
            vorige["date_end"] = s["date"]
            continue
        stationen.append({**s, "date_end": None, "members": [], "_ohne": ohne})
    for g in stationen:
        if g["kind"] == "group":
            n = len(g["members"])
            g["title"] = f"{n} Beratungen ohne Abstimmung"
            g["detail"] = ", ".join(dict.fromkeys(m["committee"] or "" for m in g["members"]))
        g.pop("_ohne", None)

    ende_vorher: str | None = None
    for s in stationen:
        if ende_vorher is None:
            s.update({"gap_days": None, "gap_label": None, "pause": False})
        else:
            tage = _tage(ende_vorher, s["date"])
            s.update({"gap_days": tage, "gap_label": abstand_text(tage),
                      "pause": tage >= PAUSE_TAGE})
        ende_vorher = s["date_end"] or s["date"]
    erste, letzte = stationen[0]["date"], stationen[-1]["date_end"] or stationen[-1]["date"]
    return {"span": abstand_text(_tage(erste, letzte)), "count": len(roh),
            "stations": stationen}
