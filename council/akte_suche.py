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
import math
import re
from datetime import date
from typing import Any

log = logging.getLogger("council.akte_suche")

#: Wie viele der besten Suchtreffer die Akte bestimmen. Gemessen am Gold-Set
#: (Anteil der Belege in Suche + Akten-Auswahl, 02.10.2026): 3 → 63,0 %,
#: 5 → 64,8 % — der fünfte Treffer trifft öfter die Pressemitteilungen.
EINSTIEG = 5
#: So viele Beschlüsse der Akte kommen höchstens zusätzlich in den Kontext.
#:
#: **Gemessen ohne Sprachmodell** (``eval/run_akten.py --methode auswahl``,
#: Prod-Abzug, 02.10.2026): Die Akte enthält 86,7 % der Gold-Belege, die
#: Auswahl gab mit 12/30/5 nur 66,7 % weiter — am meisten gingen Wortbeiträge
#: verloren (29 von 50 in der Akte). 16/50/8 gibt 77,0 % weiter. Eine bessere
#: RANGFOLGE half kaum (Deckel je Sitzung +0,6 Pp, Pressemitteilungen nach
#: Vektor-Nähe sogar schlechter als nach Datum: 16 statt 18 von 34). Am Ende
#: der Kette, blind gerichtet an den neun Fällen, deren Auswahl sich ändert:
#: Abdeckung 51,7 → 56,1 %, keine Verstöße. Preis: rund 2.400 Tokens mehr.
BESCHLUESSE = 16
#: Wortbeiträge: die so vielen der Akte, deren Vektor der Frage am nächsten
#: liegt — OHNE Cross-Encoder. Gemessen an den Gold-Fällen (02.10.2026): 20
#: nach Vektor brachten 20 von 52 Debatten-Belegen in 17 ms; 40 nach Vektor
#: und dann 10 nach Cross-Encoder 21 von 52 in 573 ms, 200 Paare durch den
#: Cross-Encoder dauerten 9–11 s. Innerhalb einer Akte ist schon alles beim
#: Thema; dort trennt der Cross-Encoder kaum noch. Mit Einstieg 5: 20 Beiträge
#: 64,8 %, 30 → 69,1 %, 40 → 72,1 % — 30 als Mitte, weil jeder Beitrag den
#: Prompt verlängert und die Antwort das Material ohnehin nicht ausschöpft
#: (Phase 4). Seit 02.10.2026 50 (Messung bei ``BESCHLUESSE``).
BEITRAEGE = 50
#: Bonus auf die Vektor-Nähe eines Beitrags, je jünger, desto mehr
#: (``frische``). Gemessen ohne Sprachmodell (``eval/run_akten.py --methode
#: auswahl``, 03.10.2026): Alle 12 Debatten-Belege, die die Auswahl verlor,
#: stammten aus 2025/26 — in einer Akte mit 250 Beiträgen über Jahre gewinnt
#: nach reiner Nähe oft der ältere. Debatten-Belege 40 → 45 von 52 bei 0,3
#: (0,5 gleich, 1,0 → 43, 3,0 — praktisch „die neuesten“ — wieder 40). Die
#: Mischung macht es; 0,3 ist der kleinste Wert mit dem vollen Gewinn.
FRISCH = 0.3
#: Dazu immer so viele jüngste Aussagen der Verwaltung.
VERWALTUNG = 4
#: Die neuesten — nach Vektor-Nähe gewählt wurde es schlechter (s. ``BESCHLUESSE``).
PRESSE = 8
#: Dazu höchstens so viele Mitteilungen, deren Titel die Frage trägt.
#: Gemessen (03.10.2026, ohne Sprachmodell): Presse-Belege 22 → 27 von 34
#: (Grundsteuer +3, Stadion +2: „Bürgerbegehren“, „nächste Hürde“). Ein Treffer
#: kann daneben liegen („Verbindungsstraße zum Klinikum“) — der Titel trägt
#: dann nur das eine seltene Wort.
PRESSE_TITEL = 4
#: So viele angekündigte Stationen (Beratungsfolge nach dem letzten
#: protokollierten Beschluss) höchstens.
ANGEKUENDIGT = 6


def _ist_verwaltung(w: dict) -> bool:
    sprecher = (w.get("speaker") or "").lower()
    return w.get("kind") == "pledge" or sprecher.startswith("verwaltung")


def frische(w: dict, heute: date) -> float:
    """Der Bonus für einen jungen Beitrag: ``FRISCH`` am Sitzungstag, nach
    einem Jahr gut ein Drittel davon (e^-1), ohne Datum nichts."""
    try:
        alter = (heute - date.fromisoformat(str(w.get("session_date") or "")[:10])).days
    except ValueError:
        return 0.0
    return FRISCH * math.exp(-max(alter, 0) / 365.0)


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
        heute = date.today()
        werte = [float(werte[i]) + frische(mit[i], heute) for i in range(len(mit))]
        rang = sorted(range(len(mit)), key=lambda i: -werte[i])[:BEITRAEGE]
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
    # Dazu Mitteilungen, deren Titel jedes seltene Wort der Frage trägt: Sie
    # gehören zur Sache, auch wenn keine Themen-Erwähnung sie anklebt — die
    # Grundsteuer-Akte hatte keine einzige, „Keine höheren Grundsteuern in
    # Oldenburg“ fehlte. Mit eigenem Deckel, damit sie die neuesten der Akte
    # nicht verdrängen (``PRESSE_TITEL``).
    from council import qa
    titel = store.presse_by_ids(qa.press_title_ids(store, frage))
    titel.sort(key=lambda p: str(p.get("date") or ""), reverse=True)
    schon = {p["id"] for p in presse[:PRESSE]}
    presse = presse[:PRESSE] + [p for p in titel if p["id"] not in schon][:PRESSE_TITEL]

    # Angekündigt: Stationen der Beratungsfolge NACH dem jüngsten
    # protokollierten Beschluss der Akte. Das Ratsinformationssystem trägt das
    # Ergebnis erst mit dem Protokoll ein, und das kommt vier bis sieben Wochen
    # später (Plan „Akte“, Schritt 0.5) — bis dahin ist die Tagesordnung der
    # jüngste Stand (Klinikum: Bürgschaft im Rat am 28.09.2026).
    neuester = max((str(d.get("session_date") or "")[:10] for d in decisions), default="")
    stationen = [st for st in store.deliberations_by_ids(sorted(ids.get("station", [])))
                 if str(st.get("date") or "")[:10] > neuester]
    stationen.sort(key=lambda st: str(st.get("date") or ""))

    return {"decisions": decisions, "speeches": speeches,
            "press": presse[:PRESSE + PRESSE_TITEL],
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


_MONAT_JAHR_RE = re.compile(r"(" + "|".join(_MONATE) + r") (\d{4})")
_DATUM_RE = re.compile(r"\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b")


def _juengster_monat(antwort: str) -> tuple[int, int] | None:
    """Der späteste Monat, den die Antwort nennt — (Jahr, Monat)."""
    werte = [(int(j), _MONATE.index(m) + 1) for m, j in _MONAT_JAHR_RE.findall(antwort)]
    werte += [(int(j), int(m)) for _, m, j in _DATUM_RE.findall(antwort) if 1 <= int(m) <= 12]
    return max(werte) if werte else None


def nennt(antwort: str, station: dict) -> bool:
    """Nennt die Antwort diese Station — oder schon etwas Späteres?

    Beschluss: seine [id]. Sonst Monat und Jahr der Station (so schreibt die
    Antwort Daten), Tag und Monat oder das Datum in Ziffern. Nennt die Antwort einen
    SPÄTEREN Monat, ist sie schon weiter als die Station: Beim Schlossplatz
    hätte „Zuletzt: Dezember 2025“ unter einer Antwort gestanden, die mit
    April 2026 endete.
    """
    if station["art"] == "beschluss" and f"[{station['c']['id']}]" in antwort:
        return True
    try:
        jahr, monat, tag = (int(x) for x in station["datum"][:10].split("-"))
    except ValueError:
        return False
    if (f"{_MONATE[monat - 1]} {jahr}" in antwort
            or f"{tag:02d}.{monat:02d}.{jahr}" in antwort
            or f"{tag}.{monat}.{jahr}" in antwort
            # „… laut Pressemitteilung vom 12. August hat die EU …“: Tag und
            # Monat ohne Jahr — das Jahr steht ein paar Sätze vorher.
            or re.search(rf"\b{tag}\. {_MONATE[monat - 1]}\b", antwort)):
        return True
    spaetester = _juengster_monat(antwort)
    return spaetester is not None and spaetester > (jahr, monat)


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


def _vote_parts(d: dict) -> tuple[str | None, list[str]]:
    """(„mehrheitlich“, ["17 Gegenstimmen", "2 Enthaltungen"]) — nur, was belegt ist."""
    from council.ergebnisse import VOTE_WORT

    label = VOTE_WORT.get(str(d["vote"]), str(d["vote"])) if d.get("vote") else None
    counts = []
    nein, enth = d.get("no_votes"), d.get("abstentions")
    if nein:
        counts.append(f"{int(nein)} Gegenstimme" + ("n" if int(nein) != 1 else ""))
    if enth:
        counts.append(f"{int(enth)} Enthaltung" + ("en" if int(enth) != 1 else ""))
    return label, counts


def _stimmen_text(d: dict) -> str | None:
    """„mehrheitlich, 17 Gegenstimmen“ — nur, was belegt ist."""
    label, counts = _vote_parts(d)
    return ", ".join(([label] if label else []) + counts) or None


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


# --------------------------------------------------------------------------- #
# Die Akte der ZITIERTEN Beschlüsse — für „Zuletzt“ und die Zeitleiste
# --------------------------------------------------------------------------- #
#
# Die Akte des Sucheinstiegs ist für den Prompt gedacht: lieber etwas zu viel
# Stoff als zu wenig. Für das, was der Server SELBST unter die Antwort setzt —
# den Satz „Zuletzt: …“ und die Zeitleiste —, ist sie zu breit. Gemessen am
# 02.10.2026 (60 Gold-Antworten): Jede sechste bekam einen sachfremden
# „Zuletzt“-Satz — das Stadionsingen unter der Stadion-Frage, „Ersatz
# beschädigter Mülltonnen“ unter den Trinkwasserspendern, die Sportanlage in
# Ofenerdiek unter dem Bahnübergang. Ursache: Ein unscharfer Suchtreffer im
# Einstieg zieht seine ganze Akte mit, und Pressemitteilungen hängen über
# Themen-Erwähnungen an, nicht über Vorlagen.
#
# Deshalb hier: die Akte der Beschlüsse, die die Antwort tatsächlich ZITIERT,
# und Pressemitteilungen nur, wenn ihr Titel ein Sachwort mit diesen
# Beschlüssen teilt.

#: Wörter, die in fast jedem Titel stehen und nichts über die Sache sagen.
_AMTSWOERTER = frozenset("""
beschluss beschlüsse bericht berichte berichtsantrag antrag anträge sachstand
sachstandsbericht oldenburg oldenburger stadt städtische städtischen verwaltung
zustimmung änderung änderungen fraktion ratsfraktion gruppe ausschuss vorlage
umsetzung planung planungen weiteres weitere vorgehen entwurf förderung maßnahme
maßnahmen information informationen mitteilung neubau sanierung erweiterung
sitzung termin projekt projekte konzept strategie richtlinie überplanmäßige
außerplanmäßige bewilligung haushalt haushaltsjahr wirtschaftsplan jahresabschluss
gemeinsam gemeinsame gemeinsamer gemeinsamen gemeinsames aktuelle aktuellen aktueller
neuen neuer neues weiterer weiteren erste ersten zweite zweiten künftige künftigen
stand steht stehen wurde wurden kommen kommt geworden passiert entschieden
beschlossen gesagt beantragt kostet kosten
""".split())
#: ^ Die letzte Zeile sind Fragewörter: „Wie ist der STAND …“ steckt sonst in
#: jedem „Sachstandsbericht“, „beschlossen“ in jedem „beschlossenen“.
_WORT_RE = re.compile(r"[a-zäöüß]{5,}")


def _sachwoerter(text: str, orte: set[str]) -> set[str]:
    return {w for w in _WORT_RE.findall((text or "").lower())
            if w not in _AMTSWOERTER and w not in orte}


_FALTEN = str.maketrans({"ä": "a", "ö": "o", "ü": "u", "ß": "ss"})


def _verwandt(a: str, b: str) -> bool:
    """Teilen zwei Wörter einen Stamm? Komposita zählen („stadion“ in
    „stadionfinanzierung“), sonst ein gemeinsamer Anfang von 7 Buchstaben.
    Umlaute zählen wie ihr Grundlaut — „Hebesatz“ steckt in „Hebesätze“."""
    a, b = a.translate(_FALTEN), b.translate(_FALTEN)
    if a in b or b in a:
        return True
    return len(a) >= 7 and len(b) >= 7 and a[:7] == b[:7]


#: Rohe Zeilenarten der Grundakten → die Namen aus ``matters.ART``.
ART_ROH = {"decision": "beschluss", "deliberation": "station", "speech": "debatte",
           "template": "vorlage", "agenda_item": "beratung"}


def gehoert_zum_vorgang(titel: str, sachwoerter: set[str], orte: set[str]) -> bool:
    """Teilt der Titel einer Pressemitteilung ein Sachwort mit dem Vorgang?"""
    return any(_verwandt(w, s) for w in _sachwoerter(titel, orte) for s in sachwoerter)


def kern(store: Any, zitiert: list[int], frage: str) -> dict:
    """Die Akte der zitierten Beschlüsse: ``{"decisions", "press", "announced"}``.

    Die Grundakten der zitierten Beschlüsse gehören ganz dazu. Was nur über
    ein Thema daran klebt, kommt hinzu, wenn sein Titel ein Sachwort mit der
    FRAGE teilt — beim Stadion trugen zwei zitierte Beschlüsse (Grundstücke,
    Parkplatz) die Weser-Ems-Halle, und deren Bürgschaft stand als „Zuletzt“
    unter der Stadion-Antwort. Pressemitteilungen gelten immer als geklebt.
    Leer, wenn nichts zitiert ist.
    """
    from council import matters

    leer: dict = {"decisions": [], "press": [], "announced": []}
    haupt = store.hauptbeschluesse(list(dict.fromkeys(zitiert)))
    if not haupt:
        return leer
    try:
        akte = matters.akte_von(store, haupt)
        start = store.matters_of_decisions(haupt)
        eigen = {(ART_ROH.get(t, t), i) for t, i in store.items_of_matters(sorted(start))}
    except Exception as exc:  # noqa: BLE001 — ohne Grundakten nichts anhängen
        log.info("Kern-Akte nicht verfügbar: %s", exc)
        return leer
    orte = store.ortsnamen()
    sach = _sachwoerter(frage, orte)

    def passt(art: str, iid: int, titel: str | None) -> bool:
        return (art, iid) in eigen or gehoert_zum_vorgang(titel or "", sach, orte)

    ids: dict[str, list[int]] = {}
    for art, iid in akte["items"]:
        ids.setdefault(art, []).append(iid)
    decisions = [d for d in store.get_decisions_by_ids(
        sorted(store.hauptbeschluesse(sorted(ids.get("beschluss", [])))))
        if passt("beschluss", d["id"], d.get("title"))]
    decisions.sort(key=lambda d: (str(d.get("session_date") or ""), d["id"]), reverse=True)
    presse = [p for p in store.presse_by_ids(sorted(ids.get("presse", [])))
              if gehoert_zum_vorgang(p.get("title") or "", sach, orte)]
    presse.sort(key=lambda p: str(p.get("date") or ""), reverse=True)
    neuester = max((str(d.get("session_date") or "")[:10] for d in decisions), default="")
    stationen = [st for st in store.deliberations_by_ids(sorted(ids.get("station", [])))
                 if str(st.get("date") or "")[:10] > neuester
                 and passt("station", st["id"], st.get("title"))]
    stationen.sort(key=lambda st: str(st.get("date") or ""))
    return {"decisions": decisions, "press": presse[:PRESSE], "announced": stationen[:ANGEKUENDIGT]}


# --------------------------------------------------------------------------- #
# Eckdaten unter der Antwort (Schalter ``akten-zeitleiste``)
# --------------------------------------------------------------------------- #
#
# Was das Modell weglässt, steht im Protokoll ausdrücklich: Von den verfehlten
# Pflichtfakten der Gold-Runde vom 02.10.2026 hatten 30 % ihren Beleg im
# Kontext — fast immer Stimmen, Beträge und Daten. Eine feste Gliederung und
# mehr Denkaufwand bewegten das um keinen Punkt. Deshalb zeigt der Server sie
# selbst, direkt aus den Daten: den jüngsten zitierten Beschluss mit seiner
# Abstimmung, den Betrag, den er nennt, was danach kam und was als Nächstes
# ansteht. Kein Modell, also auch keine Zahl, die das Modell sich ausdenkt.

#: Ergebnisse, über die abgestimmt wurde. „Zur Kenntnis“, „vertagt“ und „gilt
#: als behandelt“ sind Stationen, aber kein Beschluss in der Sache.
DECISIVE = ("accepted", "rejected")
#: Höchstens so viele Beträge — derselben Sitzung wie der Beschluss.
KEY_AMOUNTS_MAX = 2
#: Routine, die an fast jedem Vorgang einer Gesellschaft hängt. Zur Frage nach
#: dem Stand des Stadionneubaus zitierte die Antwort einmal den
#: „Jahresabschluss 2025“ der Stadion-GmbH — als jüngster Beschluss führte er
#: die Karte an, mit 781.489 € als Betrag. Er zählt nur, wenn die Frage nach ihm
#: fragt oder sonst nichts da ist.
_ROUTINE = ("jahresabschluss", "wirtschaftsplan", "entlastung")


def _names_date(answer: str, iso: str) -> bool:
    """Nennt die Antwort dieses Datum — „10. Juli 2026“ oder „10.07.2026“?"""
    try:
        year, month, day = (int(x) for x in iso[:10].split("-"))
    except ValueError:
        return False
    return (f"{day}. {_MONATE[month - 1]} {year}" in answer
            or f"{day:02d}.{month:02d}.{year}" in answer
            or f"{day}.{month}.{year}" in answer)


def press_named(answer: str, press: list[dict]) -> list[dict]:
    """Die Pressemitteilungen, auf die sich die Antwort beruft („Laut
    Pressemitteilung vom 10.07.2026“). Sie gehören zum Vorgang, auch wenn die
    Akte sie nicht kennt — bei der Cäcilienbrücke stand die Freigabe der
    Bundesmittel nur dort."""
    if "Pressemitteilung" not in answer:
        return []
    return [p for p in press if _tag(p.get("date")) and _names_date(answer, _tag(p.get("date")))]


def _key_station(kind: str, row: dict) -> dict:
    if kind == "decision":
        return {"kind": "decision", "date": _tag(row.get("session_date")),
                "title": " ".join(str(row.get("title") or "").split()),
                "committee": row.get("committee"), "outcome": row.get("outcome"),
                "decision_id": row["id"], "url": None}
    if kind == "press":
        return {"kind": "press", "date": _tag(row.get("date")),
                "title": " ".join(str(row.get("title") or "").split()),
                "committee": None, "outcome": None, "decision_id": None, "url": row.get("url")}
    return {"kind": "announced", "date": _tag(row.get("date")),
            "title": " ".join(str(row.get("title") or row.get("template_number") or "").split()),
            "committee": row.get("committee"), "outcome": None, "decision_id": None, "url": None}


_ART_KIND = {"beschluss": "decision", "presse": "press", "angekuendigt": "announced"}


def without_station(facts: dict | None, station: dict | None) -> dict | None:
    """Die Eckdaten ohne die Station, die der Server schon als „Zuletzt:“
    an die Antwort gehängt hat — dieselbe Zeile zweimal untereinander, einmal
    im Text und einmal in der Karte, sähe nach einem Versehen aus."""
    if not facts or not station:
        return facts
    kind, day = _ART_KIND.get(station["art"]), str(station.get("datum") or "")[:10]
    return {**facts, **{k: None for k in ("latest", "next")
                        if facts.get(k) and facts[k]["kind"] == kind and facts[k]["date"] == day}}


def key_facts(cited: list[dict], decisions: list[dict], press: list[dict],
              announced: list[dict], today: str, question: str = "") -> dict | None:
    """Die Eckdaten zur Antwort — ``None`` ohne zitierten Beschluss mit Abstimmung.

    ``cited``: die Beschlüsse, die die Antwort zitiert, in der Reihenfolge des
    ersten Zitats (volle Zeilen mit Abstimmung und Betrag). ``decisions``,
    ``press``, ``announced``: was als spätere Station infrage kommt — dieselbe
    Auswahl wie beim Satz „Zuletzt“.

    - ``decision``: der jüngste zitierte Beschluss mit Abstimmung (angenommen
      oder abgelehnt); am selben Tag ein angenommener vor einem abgelehnten,
      sonst der, den die Antwort zuerst zitiert. Die Abstimmung in zwei
      Teilen, weil die Karte sie zweistufig setzt: ``vote_label``
      („mehrheitlich“) und ``vote_counts`` (["18 Gegenstimmen",
      "2 Enthaltungen"] — als Liste, damit keine Angabe mitten im Wort umbricht).
    - ``amounts``: die Beträge angenommener zitierter Beschlüsse derselben
      Sitzung, der Beschluss selbst zuerst. Ein abgelehnter Betrag ist der
      Vorschlag, nicht das, was gilt — er steht nicht da.
    - ``latest``: die jüngste Station NACH dem Beschluss — ein Beschluss, eine
      Pressemitteilung oder ein Termin ohne protokolliertes Ergebnis.
    - ``next``: der nächste angekündigte Termin ab ``today``.

    Beschlüsse und Termine zählen nur, wenn ihr Titel ein Sachwort mit der
    ``question`` teilt: Die Antwort auf „Wann kommen öffentliche
    Trinkwasserspender?“ zitierte am Rand die „Unterstützung Schwimmbad
    BTB“ — als jüngster Beschluss mit Abstimmung hätte er die Eckdaten
    angeführt. Ortsnamen zählen hier als Sachwort (anders als in ``kern``):
    Die Titel stammen aus zitierten Beschlüssen, nicht aus einem Thema, an
    dem halb Oldenburg klebt — und beim Schlossplatz trägt nur der Ort den
    Sachstandsbericht („Spielbereich Schlossplatz“). Pressemitteilungen
    ebenso, auch die, die die Antwort selbst nennt: Zur Stadion-Frage nannte
    sie den Vorverkauf des Stadionsingens („Im Spätsommer bereits an den
    Advent denken“) — als „Zuletzt“ unter dem Stadionneubau.
    """
    words = _sachwoerter(question, set())

    def relevant(title: Any) -> bool:
        return not words or gehoert_zum_vorgang(str(title or ""), words, set())

    q = (question or "").lower()

    def routine(d: dict) -> bool:
        title = str(d.get("title") or "").lower()
        return any(w in title and w not in q for w in _ROUTINE)

    order = [d for d in {d["id"]: d for d in cited}.values() if relevant(d.get("title"))]
    if any(not routine(d) for d in order):
        order = [d for d in order if not routine(d)]
    decisions = [d for d in decisions if relevant(d.get("title")) and not routine(d)]
    press = [p for p in press if relevant(p.get("title"))]
    announced = [a for a in announced if relevant(a.get("title") or a.get("template_number"))]
    voted = [(n, d) for n, d in enumerate(order)
             if d.get("outcome") in DECISIVE and _tag(d.get("session_date"))]
    if not voted:
        return None
    # Am selben Tag: erst das Angenommene — ein abgelehnter Gegenantrag (FO:
    # „erst nach EU-Zusage beauftragen“) ist nicht der Stand —, dann das
    # zuerst Zitierte.
    _, main = max(voted, key=lambda nd: (_tag(nd[1].get("session_date")),
                                         nd[1].get("outcome") == "accepted", -nd[0]))
    day = _tag(main.get("session_date"))

    def same_session(d: dict) -> bool:
        if main.get("ksinr") is not None and d.get("ksinr") is not None:
            return d["ksinr"] == main["ksinr"]
        return _tag(d.get("session_date")) == day and d.get("committee") == main.get("committee")

    amounts = [{"amount_eur": float(d["amount_eur"]), "decision_id": d["id"],
                "title": " ".join(str(d.get("title") or "").split())}
               for d in sorted(order, key=lambda d: d["id"] != main["id"])
               if d.get("outcome") == "accepted" and (d.get("amount_eur") or 0) > 0
               and same_session(d)][:KEY_AMOUNTS_MAX]

    later = ([_key_station("decision", d) for d in {x["id"]: x for x in [*order, *decisions]}.values()]
             + [_key_station("press", p) for p in press]
             + [_key_station("announced", a) for a in announced if _tag(a.get("date")) < today])
    later = [s for s in later if s["date"] > day]
    rank = {"decision": 0, "press": 1, "announced": 2}
    latest = max(later, key=lambda s: (s["date"], -rank[s["kind"]])) if later else None

    upcoming = sorted((a for a in announced if _tag(a.get("date")) >= today),
                      key=lambda a: _tag(a.get("date")))
    nxt = _key_station("announced", upcoming[0]) if upcoming else None

    vote_label, vote_counts = _vote_parts(main)
    return {"decision": {"decision_id": main["id"], "date": day,
                         "committee": main.get("committee"), "outcome": main.get("outcome"),
                         "vote_label": vote_label,
                         "vote_counts": vote_counts,
                         "title": " ".join(str(main.get("title") or "").split())},
            "amounts": amounts, "latest": latest, "next": nxt}


# --------------------------------------------------------------------------- #
# Die Gründliche Recherche anbieten, wo sie mehr herausholt
# --------------------------------------------------------------------------- #

#: Ab so vielen Stationen im Verlauf bietet die Antwort die Gründliche
#: Recherche an. Gemessen am Gold-Set (02./03.10.2026, Prod-Abzug, Richter
#: Claude): Bei denselben Vorgangsfragen nennt die Recherche mit Akte 63,7 %
#: der Pflichtfakten, „Frag den Rat“ rund 51–56 %; von den Fakten, deren Beleg
#: im Kontext steht, schreibt die Recherche gut 70 % hin, die kurze Antwort gut
#: die Hälfte. Der Abstand ist am größten, wo viel Stoff liegt — ein langer
#: Vorgang. Sechs Stationen sind ein Vorgang mit Geschichte, nicht ein
#: Beschluss mit Vorberatung.
RECHERCHE_AB = 6


def research_offer(timeline: dict | None) -> dict | None:
    """``{"stations": 21, "span": "3 Jahre, 2 Monate"}`` für einen langen
    Vorgang — sonst ``None``. Die Oberfläche bietet damit die Gründliche
    Recherche an; ob jemand annimmt, zählt die Nutzungsstatistik
    (``research_offer_shown`` / ``research_offer_taken``)."""
    if not timeline or int(timeline.get("count") or 0) < RECHERCHE_AB:
        return None
    return {"stations": int(timeline["count"]), "span": str(timeline.get("span") or "")}
