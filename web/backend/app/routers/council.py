"""Ratsinformationssystem: browse and search sessions, agenda items, committees."""
from __future__ import annotations

import json
import logging
import math
import time
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

from council.store import CouncilStore
from council.topics import POLICY_FIELDS
from council.goals import GOALS
from council.parties import faction_label, normalize_party, order_key
from council import qa
from council import ernte
from council import importance
from council import sitzungspause as pause_mod
from council import vorlagen as vorlagen_mod

from nwz.store import Store

from ..deps import get_council_store, get_store, optional_user, require_active
from ..ratelimit import qa_limiter

router = APIRouter(prefix="/api/council", tags=["council"])

_log = logging.getLogger(__name__)

BASE_URL = "https://buergerinfo.oldenburg.de"


def _ratsinfo_url(ksinr: int) -> str:
    return f"{BASE_URL}/si0057.php?__ksinr={ksinr}"


def _vorlage_url(kvonr: int) -> str:
    return f"{BASE_URL}/vo0050.php?__kvonr={kvonr}"


@router.get("/committees")
def committees(_user: dict = Depends(require_active), store: CouncilStore = Depends(get_council_store)) -> dict:
    return {"committees": store.get_all_committee_names()}


@router.get("/fields")
def fields(_user: dict = Depends(require_active), store: CouncilStore = Depends(get_council_store)) -> dict:
    """Policy fields that have at least one classified decision, with label + count."""
    counts = {r["field"]: r["count"] for r in store.policy_field_stats()}
    out = [
        {"key": key, "label": POLICY_FIELDS[key][0], "count": counts[key]}
        for key in POLICY_FIELDS if counts.get(key)
    ]
    out.sort(key=lambda f: f["count"], reverse=True)
    return {"fields": out}


@router.get("/sessions")
def sessions(
    q: str = "",
    committee: str = "",
    date_from: str = "",
    date_to: str = "",
    scope: str = Query("all", pattern="^(all|upcoming|recent)$"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: dict = Depends(require_active),
    store: CouncilStore = Depends(get_council_store),
    nwz: Store = Depends(get_store),
) -> dict:
    # `total` ist die GESAMTZAHL der passenden Sitzungen, `count` nur die dieser
    # Seite. Vorher gab es nur count — die Liste endete deshalb still bei der
    # Obergrenze, ohne dass irgendwo stand, dass es weitergeht (der Bestand
    # reicht bis 2018 zurück).
    if scope == "upcoming":
        rows = store.upcoming_sessions(limit=limit, offset=offset)
        total = store.count_upcoming_sessions()
    elif scope == "recent":
        rows = store.recent_sessions(limit=limit, offset=offset)
        total = store.count_recent_sessions()
    else:
        rows = store.search_sessions(q, committee, date_from, date_to, limit=limit, offset=offset)
        total = store.count_sessions(q, committee, date_from, date_to)

    # RL-902: „n TOPs zu deinen Themen" — Treffer der Tagesordnungs-
    # Klassifikation für die eingeloggte Nutzer:in (eine Batch-Abfrage).
    ksinrs = [r["ksinr"] for r in rows if r.get("ksinr")]
    mine = nwz.agenda_matches_for_owner(user["id"], ksinrs)
    for r in rows:
        matches = mine.get(r.get("ksinr") or 0)
        if matches:
            r["my_topic_items"] = matches

    return {"count": len(rows), "total": total, "sessions": rows}


@router.get("/sitzungspause")
def sitzungspause(
    _user: dict = Depends(require_active),
    store: CouncilStore = Depends(get_council_store),
) -> dict:
    """Läuft gerade eine Sitzungspause (Schulferien / Wahl-Übergang)?

    Der Rat pausiert laut Stadt in den Schulferien; die Übersicht zeigt dann
    ein Banner, damit sich niemand über ausbleibende neue Sitzungen wundert.
    """
    upcoming = store.upcoming_sessions(limit=1)
    next_date: date | None = None
    if upcoming:
        try:
            next_date = date.fromisoformat(str(upcoming[0]["session_date"])[:10])
        except ValueError:
            next_date = None
    return pause_mod.sitzungspause(date.today(), next_date)


# 15-Minuten-Cache für die öffentliche Heute-Leiste (RL-901) — ein Dict statt
# Infrastruktur: der Endpoint ist public und würde sonst je Landing-Aufruf
# Agenda-Zeilen lesen.
_HEUTE_CACHE: dict = {"at": 0.0, "data": None}


@router.get("/heute")
def heute(store: CouncilStore = Depends(get_council_store)) -> dict:
    """RL-901: „Heute im Rat" für die Landing — public (wie public-stats).
    Drei Zustände: Sitzung heute (mit 2 Top-TOPs + Restzähler) · nächste
    Sitzung · Sitzungspause. Cache 15 min."""
    import time
    now = time.time()
    if _HEUTE_CACHE["data"] is not None and now - _HEUTE_CACHE["at"] < 900:
        return _HEUTE_CACHE["data"]

    today = date.today().isoformat()
    upcoming = store.upcoming_sessions(limit=10)
    sessions_today = [s for s in upcoming if str(s["session_date"])[:10] == today]
    if sessions_today:
        s = sessions_today[0]
        # Terminierte Sitzungen (aus dem Kalender) haben noch keinen ksinr.
        items = [i for i in store.agenda_items(s["ksinr"]) if i.get("is_public")] if s.get("ksinr") else []
        data = {
            "state": "heute",
            "committee": s["committee"],
            "session_time": s.get("session_time") or "",
            "tops": [str(i.get("title") or "")[:90] for i in items[:2]],
            "rest": max(len(items) - 2, 0),
            "n_sessions_today": len(sessions_today),
        }
    elif upcoming:
        s = upcoming[0]
        data = {
            "state": "naechste",
            "committee": s["committee"],
            "session_date": s["session_date"],
            "session_time": s.get("session_time") or "",
        }
    else:
        p = pause_mod.sitzungspause(date.today(), None)
        data = {"state": "pause", "label": p["label"], "until": p["until"]}

    _HEUTE_CACHE.update(at=now, data=data)
    return data


@router.get("/diese-woche")
def diese_woche(
    _user: dict = Depends(require_active),
    store: CouncilStore = Depends(get_council_store),
) -> dict:
    """RL-U15 (13a-A): interessantester Beschluss der letzten 7 Tage — die
    „Diese Woche im Rat"-Karte, wenn es keine persönlichen Treffer gibt.
    Der interest_reason-Satz ist die „Warum spannend"-Zeile."""
    d = store.most_interesting_recent(days_back=7)
    if not d:
        return {"found": False}
    return {
        "found": True,
        "decision_id": d["id"],
        "title": d["title"],
        "outcome": d["outcome"],
        "committee": d["committee"],
        "session_date": d["session_date"],
        "interest_reason": d.get("interest_reason") or "",
    }


@router.get("/fundstueck")
def fundstueck(
    _user: dict = Depends(require_active),
    store: CouncilStore = Depends(get_council_store),
) -> dict:
    """RL-U11: Fundstück des Tages — kuratierter Archiv-Fund für die Übersicht
    (Pipeline: scripts/rate_interest.py + scripts/generate_fundstuecke.py).
    {"found": false} statt 404: ohne Karte des Tages lässt das Frontend die
    Kachel schlicht weg."""
    f = store.get_fundstueck(date.today().isoformat())
    if not f:
        return {"found": False}
    return {
        "found": True,
        "kicker": f["kicker"],
        "story": f["story"],
        "decision_id": f["decision_id"],
        "title": f["title"],
        "outcome": f["outcome"],
        "vote": f["vote"],
        "committee": f["committee"],
        "session_date": f["session_date"],
    }


@router.get("/zahl-der-woche")
def zahl_der_woche(
    _user: dict = Depends(require_active),
    store: CouncilStore = Depends(get_council_store),
) -> dict:
    """RL-905: größter Beschluss-Betrag der letzten 7 Tage (Fallback 30);
    ganz ohne Treffer zählt die Karte die Beschlüsse der Woche. Die Satz-
    Formulierung übernimmt das Frontend — hier nur Rohdaten."""
    from datetime import timedelta
    today = date.today()
    for days in (7, 30):
        top = store.top_amount_since((today - timedelta(days=days)).isoformat())
        if top:
            return {"kind": "betrag", "amount_eur": top["amount_eur"],
                    "decision_id": top["id"], "title": top["title"],
                    "session_date": top["session_date"], "window_days": days}
    return {"kind": "anzahl",
            "count": store.count_decisions_since((today - timedelta(days=7)).isoformat()),
            "window_days": 7}


# Ohne Anmeldung lesbar (s. `decision_detail`) — die Beschluss-Seite zieht die
# Sitzung nach, um Gremium und Datum zu benennen.
@router.get("/session/{ksinr}")
def session_detail(
    ksinr: int,
    store: CouncilStore = Depends(get_council_store),
) -> dict:
    session = store.get_session(ksinr)
    if not session:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Sitzung nicht gefunden.")
    session["agenda_items"] = store.agenda_items(ksinr)
    # Past sessions may have a parsed protocol → enrich with decisions + attendance.
    session["decisions"] = store.get_decisions(ksinr)
    session["attendance"] = store.get_attendance(ksinr)
    session["has_protocol"] = store.has_protocol(ksinr)
    session["url"] = _ratsinfo_url(ksinr)
    return session


@router.get("/decisions")
def decisions(
    q: str = "",
    committee: str = "",
    outcome: str = Query("", pattern="^(|angenommen|abgelehnt|vertagt|zur_kenntnis|kein_beschluss)$"),
    faction: str = "",
    date_from: str = "",
    date_to: str = "",
    kind: str = Query("", pattern="^(|decision|subvote)$"),
    category: str = Query("", pattern="^(|vote|report)$"),
    sort: str = Query("date_desc", pattern="^(date_desc|date_asc|faction|importance|interest)$"),
    field: str = "",
    party: str = "",
    # Design 23a: Standard blendet Änderungsanträge (subvotes) aus der Trefferliste
    # aus — sie hängen als Kontext am Ursprungsbeschluss. Rechercheure können sie
    # per Filter „Änderungsanträge einzeln zeigen" wieder einblenden.
    include_subvotes: bool = Query(False),
    # Design 28a/S4: Auf die Treffer EINES eigenen Themas einschränken. Damit
    # ersetzt die richtige Suchseite (Filter, Sortierung, Seiten, teilbare URL)
    # den früheren Trefferdialog, der nichts davon konnte.
    topic: int | None = Query(None, ge=1),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: dict = Depends(require_active),
    store: CouncilStore = Depends(get_council_store),
    nwz: Store = Depends(get_store),
) -> dict:
    only_ids: list[int] | None = None
    if topic is not None:
        # Nur eigene Themen — sonst ließe sich über eine fremde id deren
        # Trefferliste abfragen.
        if not nwz.get_topic_for_owner(user["id"], topic):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Thema nicht gefunden.")
        only_ids = [m["decision_id"] for m in nwz.get_topic_decision_matches(topic)]
    total = store.count_decisions(q, committee, outcome, faction, date_from, date_to, kind, category, field, party,
                                  include_subvotes=include_subvotes, only_ids=only_ids)
    rows = store.search_decisions(q, committee, outcome, faction, date_from, date_to, kind, category,
                                  sort=sort, field=field, party=party, limit=limit, offset=offset,
                                  include_subvotes=include_subvotes, only_ids=only_ids)
    # Design 23a: je Beschluss die kompakte Änderungsantrags-Zusammenfassung
    # anhängen (Anzahl · Fraktion · Ergebnis) für die Karten-Unterzeile.
    pairs = [(r["ksinr"], r["item_number"]) for r in rows
             if r.get("kind") == "decision" and r.get("item_number")]
    summaries = store.subvote_summaries(pairs)
    for r in rows:
        s = summaries.get((r.get("ksinr"), r.get("item_number")))
        if s:
            r["subvote_summary"] = s
    return {"total": total, "decisions": rows}


@router.get("/decision/{decision_id}")
def decision_detail(
    decision_id: int,
    user: dict | None = Depends(optional_user),
    store: CouncilStore = Depends(get_council_store),
    nwz: Store = Depends(get_store),
) -> dict:
    """Ein Beschluss mit allem Drum und Dran — **ohne Anmeldung lesbar**.

    Teilen ist die Kernhandlung der App, aber wer einen weitergereichten Link
    öffnete, sah zuerst das Registrierungsformular. Das schreckt genau die
    Leute ab, die man gewinnen will: Sie haben noch gar nicht gesehen, wofür
    sich ein Konto lohnen würde.

    Was hier steht, stammt vollständig aus dem amtlichen
    Ratsinformationssystem und ist dort ohnehin für alle einsehbar — es
    entsteht keine neue Öffentlichkeit, nur eine lesbare (dieselbe Abwägung
    wie bei `preview`). Persönliches bleibt draußen: ``follow`` kommt nur
    dazu, wenn wirklich jemand angemeldet ist.
    """
    d = store.get_decision(decision_id)
    if not d:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Beschluss nicht gefunden.")
    attendance = store.get_attendance(d["ksinr"])
    # Anwesende Stimmberechtigte — für den Hinweis „einstimmig → diese
    # Fraktionen waren da". `faction_label` statt `normalize_party`: Letzteres
    # kollabiert Rats-GRUPPEN auf eine ihrer Parteien und behauptet damit etwas
    # Falsches über reale Personen — „FDP/Volt" wurde zu „FDP" (Volt fiel weg),
    # „Gruppe DIE LINKE./Piratenpartei" zu „Die Linke" (Piraten fielen weg).
    present = {faction_label(a["party"]) for a in attendance
               if (a.get("role") or "mitglied") in ("vorsitz", "mitglied")}
    present.discard("parteilos")   # keine Fraktion, gehört nicht in die Reihe
    out: dict = {
        "decision": d,
        "attendance": attendance,
        "present_parties": sorted((p for p in present if p), key=order_key),
        "ratsinfo_url": _ratsinfo_url(d["ksinr"]),
        "sub_votes": [],
        "vorlage_journey": [],
        "similar": store.get_similar(decision_id, limit=5),
        "entities": store.entities_for_decision(decision_id),
    }
    # Läuft zu diesem Bauleitplan GERADE eine Beteiligung? Dann gehört der
    # Hinweis samt Frist an den Beschluss — Stellungnahme ist eine der wenigen
    # Handlungen, die Bürger:innen JETZT offenstehen (Stufe 3b).
    try:
        from council import beteiligung as bet_mod
        out["beteiligung"] = next(
            ({"titel": b["titel"], "schritt": b["schritt"], "von": b["von"],
              "bis": b["bis"], "url": b["url"]}
             for b in store.list_beteiligungen()
             if bet_mod.passt_zu_titel(b["plan_nrs"], d.get("title") or "")), None)
    except Exception:  # noqa: BLE001 — Zusatzinfo, nie Blocker
        out["beteiligung"] = None
    # Wichtigkeits-Aufschlüsselung (welche Signale trieben den Score) — erklärt
    # transparent, warum ein Beschluss als wichtig gilt.
    n_ber = len(store.get_beratungen(d["kvonr"])) if d.get("kvonr") else None
    out["importance_breakdown"] = importance.importance_breakdown(d, n_beratungen=n_ber)
    # RL-U16: gleiche 50/50-Mischung wie beim persistierten Wichtig-Wert —
    # sonst zeigten Liste (DB) und Detail (Live-Heuristik) verschiedene Zahlen.
    # `base_score` (Heuristik) und `impact` bleiben einzeln erhalten, damit die
    # Beschluss-Seite die Rechnung offenlegen kann: die vier Signal-Balken
    # erklären nur die Heuristik-Hälfte, nicht den gemischten Endwert.
    # impact_reason erklärt die Tragweite („Warum wichtig: …", Design 13a-B).
    bd = out["importance_breakdown"]
    bd["base_score"] = bd["score"]
    if d.get("impact") is not None:
        bd["impact"] = int(d["impact"])
        bd["score"] = round((bd["base_score"] + bd["impact"]) / 2)
        if d.get("impact_reason"):
            bd["impact_reason"] = d["impact_reason"]
    if d.get("kind") == "decision" and d.get("item_number"):
        out["sub_votes"] = store.get_subvotes(d["ksinr"], d["item_number"])
    if d.get("vorlage_nr"):
        out["vorlage_journey"] = store.vorlage_journey(d["vorlage_nr"])
        out["vorlage_url"] = _vorlage_url(d["kvonr"]) if d.get("kvonr") else None
        # Ingested Vorlage text (Sachverhalt/Begründung) — the why behind the
        # decision. Also our only kvonr source: protocols never carry one.
        v = store.get_vorlage_by_nr(d["vorlage_nr"])
        if v:
            out["vorlage"] = {
                "vorlage_nr": v.get("vorlage_nr"), "title": v.get("title"),
                "art": v.get("art"), "document_url": v.get("document_url"),
                "n_pages": v.get("n_pages"),
                "excerpt": vorlagen_mod.excerpt(v.get("raw_text") or "", 2600) or None,
                # Regex-Ernte: federführendes Amt + Klima-Check der Verwaltung.
                "amt": v.get("amt"),
                "klima_check": v.get("klima_check"),
                "klima_relevant": ernte.klima_relevant(v.get("klima_check")),
            }
            if not out["vorlage_url"] and v.get("kvonr"):
                out["vorlage_url"] = _vorlage_url(v["kvonr"])
        out["anlagen"] = store.anlagen_for_vorlage_nr(d["vorlage_nr"])
        # P1: gerenderte Planzeichnung (scripts/render_plaene.py) — B-Plan-
        # Beschlüsse leben vom Bild, nicht vom Anlagen-Download.
        out["plan_bild"] = next(
            (a["document_id"] for a in out["anlagen"] if a.get("bild") == 1), None)
        # Offizielle Beratungsfolge aus dem Ratsinfo — reicher als die aus
        # unseren Tagesordnungen abgeleitete Journey (Ergebnis je Station,
        # geplante künftige Beratungen). Die Journey bleibt der Fallback.
        kv = d.get("kvonr") or (v.get("kvonr") if v else None)
        if kv:
            today = date.today().isoformat()
            out["beratungsfolge"] = [
                {**b, "future": bool(b["datum"] and b["datum"] > today)}
                for b in store.get_beratungen(kv)
            ]
            # Design 28a/W1: Folgt dieses Konto dem Vorgang schon? Die kvonr
            # gehört zur Antwort, weil nur sie den Vorgang eindeutig benennt —
            # die Vorlagen-Nummer wird im Ratsinfo wiederverwendet.
            # Ohne Anmeldung fehlt der Schlüssel ganz: Das Frontend blendet den
            # Verfolgen-Knopf über `data.follow &&` aus, ohne etwas zu wissen.
            if user:
                out["follow"] = {"kvonr": kv, "following": nwz.is_following_vorlage(user["id"], kv)}
    return out


@router.get("/qa-beispiele")
def qa_beispiele(store: CouncilStore = Depends(get_council_store)) -> dict:
    """Frische Beispiel-Anlässe für den Empty State der KI-Frage (5a/I-07):
    die jüngsten Sitzungen mit Beschlüssen — das Frontend formuliert daraus
    „Was hat der <Ausschuss> am <Datum> beschlossen?"."""
    return {"sitzungen": store.juengste_sitzungen_mit_beschluessen(limit=2)}


@router.get("/plan-bild/{document_id}")
def plan_bild(document_id: int, thumb: bool = False) -> FileResponse:
    """Gerenderte Planzeichnung einer Anlage (P1) — öffentlich wie die
    Beschluss-Seite selbst; das PDF dahinter ist ohnehin frei abrufbar.
    Dateien schreibt scripts/render_plaene.py nach ``data/plaene/``."""
    from pathlib import Path

    from ..config import get_settings

    name = f"{int(document_id)}{'.thumb' if thumb else ''}.jpg"
    pfad = Path(get_settings().council_db).parent / "plaene" / name
    if not pfad.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Kein Bild zu dieser Anlage.")
    # Ein gerendertes Blatt ändert sich nie — aggressiv cachen.
    return FileResponse(pfad, media_type="image/jpeg",
                        headers={"Cache-Control": "public, max-age=2592000, immutable"})


# ---- Vorgänge verfolgen (Design 28a/W1) ----

def _stations_signature(rows: list[dict]) -> str:
    """Vergleichbarer Fingerabdruck der Beratungsfolge.

    Datum, Gremium und Ergebnis — mehr braucht der Vergleich nicht, und weniger
    wäre zu grob: Eine Station gilt auch dann als neu, wenn nur das Ergebnis
    nachgetragen wurde. Genau das ist die Nachricht, auf die man wartet.
    """
    return json.dumps(
        [f"{r.get('datum') or ''}|{r.get('gremium') or ''}|{r.get('ergebnis') or ''}" for r in rows],
        ensure_ascii=False,
    )


@router.get("/follows")
def list_follows(
    user: dict = Depends(require_active),
    store: CouncilStore = Depends(get_council_store),
    nwz: Store = Depends(get_store),
) -> dict:
    """Verfolgte Vorgänge mit ihrem aktuellen Stand — die Beratungsfolge liegt
    in der anderen Datenbank, deshalb hier je Follow eine Abfrage (die Zahl
    ist nutzergemacht und klein)."""
    today = date.today().isoformat()
    out = []
    for f in nwz.get_vorlage_follows(user["id"]):
        stations = store.get_beratungen(f["kvonr"])
        naechste = next((b for b in stations if b.get("datum") and b["datum"] > today), None)
        letzte = next((b for b in reversed(stations) if b.get("datum") and b["datum"] <= today), None)
        out.append({
            **f,
            "url": _vorlage_url(f["kvonr"]),
            "n_stationen": len(stations),
            "naechste": naechste,
            "letzte": letzte,
        })
    return {"follows": out}


@router.post("/vorlage/{kvonr}/follow", status_code=status.HTTP_201_CREATED)
def follow_vorlage(
    kvonr: int,
    user: dict = Depends(require_active),
    store: CouncilStore = Depends(get_council_store),
    nwz: Store = Depends(get_store),
) -> dict:
    v = store.get_vorlage(kvonr)
    if not v:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Vorlage nicht gefunden.")
    # Den heutigen Stand mitschreiben: Was schon dasteht, ist keine Neuigkeit.
    nwz.follow_vorlage(
        user["id"], kvonr,
        vorlage_nr=v.get("vorlage_nr") or "", title=v.get("title") or "",
        stations=_stations_signature(store.get_beratungen(kvonr)),
    )
    return {"kvonr": kvonr, "following": True}


@router.delete("/vorlage/{kvonr}/follow")
def unfollow_vorlage(
    kvonr: int,
    user: dict = Depends(require_active),
    nwz: Store = Depends(get_store),
) -> dict:
    nwz.unfollow_vorlage(user["id"], kvonr)
    return {"kvonr": kvonr, "following": False}


@router.get("/analysis")
def analysis(_user: dict = Depends(require_active), store: CouncilStore = Depends(get_council_store)) -> dict:
    """Party behaviour: topic heatmap, success rates, contention, alliances —
    plus Erfolgsquoten der eingereichten Fraktions-Anträge (aus den Anlagen)."""
    data = store.party_analysis()
    data["field_labels"] = {k: POLICY_FIELDS[k][0] for k in data["topic_matrix"]["fields"]}
    data["antrag_stats"] = store.antrag_stats()
    return data


@router.get("/finance")
def finance(_user: dict = Depends(require_active), store: CouncilStore = Depends(get_council_store)) -> dict:
    """Largest € decisions + recognised volume per policy field (excl. accounting reports)."""
    by_field = store.money_by_field()
    return {
        "decisions": store.largest_financial_decisions(limit=25),
        "by_field": by_field,
        "field_labels": {r["field"]: POLICY_FIELDS[r["field"]][0] for r in by_field},
    }


@router.get("/trends")
def trends(_user: dict = Depends(require_active), store: CouncilStore = Depends(get_council_store)) -> dict:
    """Council activity over time: decisions + € volume per quarter by field, emerging tags."""
    data = store.activity_trends()
    data["field_labels"] = {k: POLICY_FIELDS[k][0] for k in data["fields"]}
    return data


@router.get("/field-recaps")
def field_recaps(_user: dict = Depends(require_active), store: CouncilStore = Depends(get_council_store)) -> dict:
    """Auto-generated plain-language recaps per policy field ("Was bewegte den Rat im Bereich X?")."""
    recaps = store.get_field_recaps()
    for r in recaps:
        r["field_label"] = POLICY_FIELDS.get(r["policy_field"], (r["policy_field"],))[0]
    return {"recaps": recaps}


@router.get("/entities")
def entities_list(kind: str = "", _user: dict = Depends(require_active),
                  store: CouncilStore = Depends(get_council_store)) -> dict:
    """Directory of named entities (projects/places/organizations), most-referenced first."""
    return {"entities": store.list_entities(limit=400, kind=kind)}


@router.get("/entities-map")
def entities_map(_user: dict = Depends(require_active),
                 store: CouncilStore = Depends(get_council_store)) -> dict:
    """All geocoded entities (points) for the city-wide map."""
    return {"entities": store.list_entities_geo()}


@router.get("/public-stats")
def public_stats(store: CouncilStore = Depends(get_council_store)) -> dict:
    """Aggregate headline counts for the public landing page — no auth, no content."""
    return store.public_stats()


# ---- Link-Vorschau (Design 29a, P1) ----
# Wortlaut der Ergebnisse für die eine Zeile, die WhatsApp & Co. anzeigen.
_PREVIEW_OUTCOME = {
    "angenommen": "angenommen",
    "abgelehnt": "abgelehnt",
    "vertagt": "vertagt",
    "zur_kenntnis": "zur Kenntnis genommen",
    "kein_beschluss": "ohne Beschluss",
}


def _preview_datum(iso: str | None) -> str:
    """„2026-06-01" → „01.06.2026"; leer bleibt leer."""
    teile = str(iso or "")[:10].split("-")
    return f"{teile[2]}.{teile[1]}.{teile[0]}" if len(teile) == 3 else ""


def _kuerzen(text: str, grenze: int) -> str:
    """Auf Wortgrenze kürzen, mit Auslassungszeichen.

    Beschlusstitel aus dem Ratsinformationssystem werden sehr lang — der volle
    Amtstitel eines Bebauungsplans kommt auf über 250 Zeichen. Messenger und
    Suchmaschinen zeigen aber nur die ersten rund 60–90; ungekürzt sieht die
    Vorschaukarte aus wie ein Fehler.
    """
    text = text.strip()
    if len(text) <= grenze:
        return text
    schnitt = text[:grenze].rsplit(" ", 1)[0].rstrip(" ,;:–-")
    return f"{schnitt or text[:grenze].rstrip()}…"


@router.get("/preview/{kind}/{key:path}")
def preview(kind: str, key: str, store: CouncilStore = Depends(get_council_store)) -> dict:
    """Titel + Kurzfassung für die Link-Vorschau — **ohne Anmeldung**.

    Teilen ist die Kernhandlung der App, aber bislang zeigte jeder geteilte Link
    denselben Werbetext: In einer Elterngruppe landeten fünf Beschlüsse als fünf
    identische Kacheln. Die Vorschau baut `generateMetadata` im Frontend aus
    diesen zwei Feldern.

    Bewusst öffentlich und bewusst schmal: Zurückgegeben wird genau die Zeile,
    die Messenger und Suchmaschinen ohnehin anzeigen — Titel, Ergebnis, Gremium,
    Datum. Alles davon steht so im amtlichen Ratsinformationssystem; es entsteht
    keine neue Öffentlichkeit, nur eine lesbare. Persönliche Daten (Themen,
    Fortschritt, Konten) sind hier prinzipiell nicht erreichbar.
    """
    if kind == "decision":
        d = store.get_decision(int(key)) if key.isdigit() else None
        if not d:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Beschluss nicht gefunden.")
        titel = (d.get("title") or "Beschluss des Oldenburger Stadtrats").strip()
        ergebnis = _PREVIEW_OUTCOME.get(d.get("outcome") or "")
        kopf = " · ".join(x for x in (d.get("committee"), _preview_datum(d.get("session_date"))) if x)
        satz = (d.get("simple_summary") or d.get("summary") or d.get("beschluss") or "").strip()
        # Erst kürzen, dann das Ergebnis anhängen: Es ist die wertvollste
        # Information der Karte und darf nie dem Rotstift zum Opfer fallen.
        titel = _kuerzen(titel, 90)
        # Ohne Beschlusstext blieb hier „Gremium · Datum." stehen — ein Satz,
        # der mitten im Nichts endet. Dann lieber sagen, was die Seite bietet.
        if not satz:
            satz = "Tagesordnungspunkt, Ergebnis und Zusammenhang im Ratslotse."
        return {
            "title": f"{titel} — {ergebnis}" if ergebnis else titel,
            "description": " ".join(x for x in (f"{kopf}." if kopf else "", satz) if x)[:300],
        }

    if kind == "person":
        p = store.member_detail(key)
        if not p:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Ratsmitglied nicht gefunden.")
        partei = p.get("party")
        gremien = len(p.get("committees") or [])
        return {
            "title": f"{p['name']} ({partei})" if partei else p["name"],
            "description": (
                f"Ratsmitglied in Oldenburg · {p.get('sessions', 0)} Sitzungen"
                + (f" · {gremien} Gremien" if gremien else "")
                + ". Anwesenheit und Beschlüsse im Ratslotse."
            ),
        }

    if kind == "thema":
        e = store.entity_detail(key)
        if not e:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Thema nicht gefunden.")
        ent = e["entity"]
        n = ent.get("n") or 0
        return {
            "title": f"{ent['name']} — {n} {'Beschluss' if n == 1 else 'Beschlüsse'}",
            "description": (
                f"Was der Oldenburger Stadtrat zu „{ent['name']}“ entschieden hat — "
                "alle Beschlüsse auf einer Seite, verständlich zusammengefasst."
            ),
        }

    if kind == "sitzung":
        s = store.get_session(int(key)) if key.isdigit() else None
        if not s:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Sitzung nicht gefunden.")
        datum = _preview_datum(s.get("session_date"))
        return {
            "title": f"{s['committee']} am {datum}" if datum else s["committee"],
            "description": (
                f"Tagesordnung und Beschlüsse der Sitzung"
                + (f" am {datum}" if datum else "")
                + f" ({s['committee']}) — im Ratslotse verständlich aufbereitet."
            ),
        }

    raise HTTPException(status.HTTP_404_NOT_FOUND, "Unbekannte Vorschau-Art.")


@router.get("/entity/{slug}")
def entity(slug: str, store: CouncilStore = Depends(get_council_store)) -> dict:
    """An entity ('Themen-') page: all its decisions plus money/parties/field aggregates.

    Ohne Anmeldung lesbar — es ist eine der geteilten Detailseiten, und alles
    hier ist eine Aggregation öffentlicher Ratsdaten (s. `decision_detail`).
    """
    data = store.entity_detail(slug)
    if not data:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Thema nicht gefunden.")
    data["field_labels"] = {f["field"]: POLICY_FIELDS[f["field"]][0]
                            for f in data["fields"] if f["field"] in POLICY_FIELDS}
    # Verwandte Themen (council.related, vorberechnet). Nach dem kanonischen Slug
    # nachschlagen — bei einem zusammengeführten Alias hängen die Nachbarn am Kanon.
    data["related"] = store.related_entities(data["entity"]["slug"])
    return data


@router.get("/members")
def members(_user: dict = Depends(require_active),
            store: CouncilStore = Depends(get_council_store)) -> dict:
    """Directory of council members (from attendance): party, sessions, committees."""
    return {"members": store.list_members()}


@router.get("/person/{slug}")
def person(slug: str, store: CouncilStore = Depends(get_council_store)) -> dict:
    """A council member's profile: party, sessions, active span, committees, recent sessions.

    Ohne Anmeldung lesbar (s. `decision_detail`). Es geht ausschließlich um
    Mandatsträger:innen in ihrer öffentlichen Funktion, und die Angaben stammen
    aus den Anwesenheitslisten der amtlichen Protokolle — keine Privatperson
    wird hier auffindbar, die es nicht ohnehin schon ist.
    """
    data = store.member_detail(slug)
    if not data:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ratsmitglied nicht gefunden.")
    return data


_EMPTY_GOAL = {"voran": 0, "bremst": 0, "neutral": 0, "total": 0}


@router.get("/goals")
def goals(_user: dict = Depends(require_active), store: CouncilStore = Depends(get_council_store)) -> dict:
    """City goals with how many decisions advance / hinder / are neutral toward them."""
    summary = store.goal_summary()
    out = [{"key": key, "label": g["label"], "description": g["description"],
            **summary.get(key, _EMPTY_GOAL)} for key, g in GOALS.items()]
    return {"goals": out}


@router.get("/goal/{key}")
def goal_detail(key: str, _user: dict = Depends(require_active),
                store: CouncilStore = Depends(get_council_store)) -> dict:
    g = GOALS.get(key)
    if not g:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ziel nicht gefunden.")
    return {
        "key": key, "label": g["label"], "description": g["description"],
        "summary": store.goal_summary().get(key, _EMPTY_GOAL),
        "decisions": store.goal_detail(key),
    }


class AskRunde(BaseModel):
    """Eine frühere Gesprächsrunde (Chat): Frage + gekürzte Antwort."""
    frage: str = Field(max_length=300)
    antwort: str = Field(default="", max_length=600)


class AskBody(BaseModel):
    question: str
    # Chat-Modus (Paket A): die letzten Runden erlauben Anschlussfragen wie
    # „Und was kostet das?" — die Analyse kondensiert daraus eine eigenständige
    # Suchfrage. Ohne Verlauf verhält sich /ask exakt wie bisher.
    verlauf: list[AskRunde] = Field(default_factory=list, max_length=4)


# Q&A sizing: show up to QA_TOP_K reranked decisions as sources, feed the most
# relevant QA_ANSWER_N to the LLM for a focused, cited answer. QA_MIN_SCORE drops
# the near-irrelevant tail from the displayed sources (sigmoid relevance).
QA_TOP_K = 40
QA_ANSWER_N = 20
QA_MIN_SCORE = 0.2
# jina-reranker-v2 logits are negative-centred (a clearly relevant match still scores
# below 0), so a raw sigmoid under-sells good hits (~50 % for the top result). Shift by
# a fixed bias so a relevant decision reads as a high-but-honest relevance.
QA_RERANK_BIAS = 1.5


def _qa_retrieve(store: CouncilStore, q: str, expanded: str,
                 timings: dict | None = None) -> tuple[list[dict], str]:
    """Hybrid retrieval + cross-encoder rerank → candidates in relevance order, each
    with an *absolute* relevance score: the sigmoid of the reranker logit, NOT a
    min-max normalisation (which forced the weakest hit to a misleading 0 %). Falls
    back to keyword retrieval when embeddings/the reranker are unavailable."""
    try:
        from council import embeddings as emb
        hits = emb.hybrid_search(store, q, expanded, top_k=QA_TOP_K, pool=55, timings=timings)
        if hits:
            candidates = store.get_decisions_by_ids([h[0] for h in hits])  # preserves order
            score = {h[0]: h[1] for h in hits}
            for c in candidates:
                logit = score.get(c["id"])
                c["score"] = round(1.0 / (1.0 + math.exp(-(logit + QA_RERANK_BIAS))), 3) if logit is not None else None
            return [c for c in candidates if (c.get("score") or 0) >= QA_MIN_SCORE] or candidates, "semantisch"
    except Exception:  # noqa: BLE001 — fastembed missing/any failure → keyword fallback
        pass
    cands = store.get_goal_candidates(qa.extract_keywords(q), limit=QA_TOP_K)
    return store.get_decisions_by_ids([c["id"] for c in cands]), "keyword"


def _sse(obj: dict) -> str:
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


def _qa_source(c: dict) -> dict:
    # amount_eur + factions tragen die Fragetyp-Bausteine des Ratsgesprächs
    # (Geld-Betrag, Antragsteller-Tag) — deterministisch aus den Quellen,
    # nie vom Sprachmodell (Design RG-04/RG-05).
    return {
        "id": c["id"], "title": c.get("title"), "summary": c.get("summary"),
        "policy_field": c.get("policy_field"), "outcome": c.get("outcome"),
        "session_date": c.get("session_date"), "committee": c.get("committee"),
        "score": c.get("score"), "amount_eur": c.get("amount_eur"),
        "factions": qa._factions_of(c),
    }


@router.post("/ask")
def ask(body: AskBody, request: Request, user: dict = Depends(require_active),
        store: CouncilStore = Depends(get_council_store),
        nwz: Store = Depends(get_store)) -> StreamingResponse:
    """Answer a free-text question from the decisions, streamed as Server-Sent Events:
    progress steps → the ranked source decisions (the moment retrieval+rerank finish)
    → the answer token-by-token → a final event with the cited ids. Streaming makes
    the wait feel far shorter (sources show in ~2 s) and degrades gracefully if a
    proxy buffers it (the client then renders the same final state at once)."""
    qa_limiter.check(request)  # LLM-Kosten pro Aufruf — nicht unbegrenzt feuern lassen
    nwz.record_activity(user["id"], "ki_frage")  # Admin-Statistik (20a)
    q = body.question.strip()
    if len(q) < 4:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Bitte eine etwas längere Frage stellen.")

    def gen():
        try:
            # Latenz je Schritt (ms) — geloggt und im done-Event mitgeschickt,
            # damit Prod-Fragen dieselben Kennzahlen liefern wie eval/run_qa.py.
            # (expand_ms misst seit dem Fragetyp-Routing den EINEN Analyse-Call
            # — Begriffe + Typ —, der Schlüssel bleibt für Vergleichbarkeit.)
            zeiten: dict = {}
            verlauf = [r.model_dump() for r in body.verlauf]
            yield _sse({"type": "step", "step": "expand"})
            t0 = time.perf_counter()
            analyse = qa.analyse_query(q, verlauf=verlauf)
            expanded, typ = analyse["begriffe"], analyse["typ"]
            # Retrieval + Reranker arbeiten mit der EIGENSTÄNDIGEN Fassung der
            # Frage — „Und was kostet das?" sucht sonst nach nichts.
            q_suche = analyse["frage"]
            zeiten["expand_ms"] = round((time.perf_counter() - t0) * 1000)
            yield _sse({"type": "step", "step": "search"})
            t0 = time.perf_counter()
            candidates, mode = _qa_retrieve(store, q_suche, expanded, timings=zeiten)
            partei_ids: set[int] = set()
            if typ == "partei" and analyse.get("partei"):
                # Anträge der gefragten Fraktion zum Thema in den Pool — die
                # semantische Suche kennt den Antragsteller-Filter nicht.
                try:
                    extra_ids = store.antrag_decision_ids(analyse["partei"], expanded)
                    partei_ids = set(extra_ids)
                    have = {c["id"] for c in candidates}
                    candidates += store.get_decisions_by_ids([i for i in extra_ids if i not in have])
                except Exception:  # noqa: BLE001 — Anreicherung ist best-effort
                    pass
            presse_rows: list[dict] = []
            try:
                # Eigener Kanal neben den Beschlüssen: „Aktuelles von der Stadt"
                # (Pressemitteilungen) — strenge Schwelle, oft leer.
                from council import embeddings as emb
                hits_p = emb.search_presse(store, q_suche, expanded)
                presse_rows = store.presse_by_ids([pid for pid, _ in hits_p])
            except Exception:  # noqa: BLE001 — Presse ist Zusatz, nie Blocker
                pass
            zeiten["retrieve_ms"] = round((time.perf_counter() - t0) * 1000)
            # 5a/I-06: die kondensierte Frage mitschicken — der Kontext-Chip im
            # Frontend zeigt, worauf sich Anschlussfragen beziehen.
            yield _sse({"type": "sources", "mode": mode, "qtype": typ,
                        "frage": q_suche,
                        "sources": [_qa_source(c) for c in candidates],
                        "presse": [{"titel": p.get("titel"), "url": p.get("url"),
                                    "datum": p.get("datum")} for p in presse_rows]})
            yield _sse({"type": "step", "step": "answer"})
            if not candidates:
                yield _sse({"type": "token", "text": "Dazu habe ich keine passenden Beschlüsse gefunden."})
                yield _sse({"type": "done", "cited": []})
                return
            ctx = candidates[:QA_ANSWER_N]
            if partei_ids:
                # Mindestens die besten Partei-Anträge in den Antwort-Kontext,
                # auch wenn sie im Relevanz-Ranking hinter Platz 20 liegen.
                fehlend = [c for c in candidates[QA_ANSWER_N:] if c["id"] in partei_ids][:6]
                if fehlend:
                    ctx = ctx[:QA_ANSWER_N - len(fehlend)] + fehlend
            if typ == "verlauf":
                ctx = qa.sort_verlauf(ctx)
            haushalt_zeilen: list[dict] = []
            if typ == "geld":
                try:  # Plan-Zahlen aus dem Stadthaushalt als Zusatzkontext
                    haushalt_zeilen = store.haushalt_fuer_begriffe(expanded.split())
                except Exception:  # noqa: BLE001 — Zusatz, nie Blocker
                    pass
            try:  # Vorlagen-Auszüge (Sachverhalt) beilegen — best-effort
                texts = store.vorlage_texts_for([c.get("vorlage_nr") or "" for c in ctx])
                for c in ctx:
                    t = texts.get((c.get("vorlage_nr") or "").strip())
                    if t:
                        c["vorlage_excerpt"] = vorlagen_mod.excerpt(t, 350)
            except Exception:  # noqa: BLE001
                pass
            try:  # Läuft zu einem Kandidaten gerade eine Bauleitplan-Beteiligung?
                from council import beteiligung as bet_mod
                bets = store.list_beteiligungen()
                for c in ctx if bets else []:
                    b = next((b for b in bets
                              if bet_mod.passt_zu_titel(b["plan_nrs"], c.get("title") or "")), None)
                    if b:
                        frist = f" bis {b['bis']}" if b.get("bis") else ""
                        c["beteiligung"] = f"{b['schritt']}{frist}"
            except Exception:  # noqa: BLE001 — Zusatzsignal, nie Blocker
                pass
            # Der Antworttext wird live gestreamt, die angehängten Folgefragen
            # (24a) dürfen dabei NICHT als Text erscheinen. Deshalb halten wir
            # stets die letzten len(MARKER) Zeichen zurück: so kann ein über
            # mehrere Deltas verteilter Marker nie durchrutschen.
            marker = qa.FOLLOWUP_MARKER
            buf, sent = "", 0
            t0 = time.perf_counter()
            try:
                for delta in qa.answer_stream(q, ctx, typ=typ, presse=presse_rows, verlauf=verlauf, haushalt=haushalt_zeilen):
                    if not buf and delta:
                        zeiten["ttft_ms"] = round((time.perf_counter() - t0) * 1000)
                    buf += delta
                    cut = buf.find(marker)
                    # Vor dem Marker: senden. Ab dem Marker: nur noch sammeln
                    # (die Vorschläge stehen dahinter — nicht abbrechen).
                    limit = cut if cut != -1 else max(0, len(buf) - len(marker))
                    if limit > sent:
                        yield _sse({"type": "token", "text": buf[sent:limit]})
                        sent = limit
                # Ohne Marker bleibt der zurückgehaltene Rest übrig.
                if marker not in buf and len(buf) > sent:
                    yield _sse({"type": "token", "text": buf[sent:]})
                    sent = len(buf)
            except Exception:  # noqa: BLE001 — streaming failed mid-way → one-shot fallback
                if not buf:
                    ans, _ = qa.answer_question(q, ctx, typ=typ, presse=presse_rows, verlauf=verlauf, haushalt=haushalt_zeilen)
                    buf = ans
                    yield _sse({"type": "token", "text": ans})
                    sent = len(ans)
            answer_text, followups = qa.split_followups(buf)
            if not followups:
                followups = qa.fallback_followups(ctx)
            if followups:
                yield _sse({"type": "suggestions", "questions": followups})
            _, cited = qa.resolve_citations(answer_text, {c["id"] for c in candidates})
            zeiten["antwort_ms"] = round((time.perf_counter() - t0) * 1000)
            zeiten["total_ms"] = (zeiten.get("expand_ms", 0) + zeiten.get("retrieve_ms", 0)
                                  + zeiten.get("antwort_ms", 0))
            _log.info("qa_timings mode=%s typ=%s %s", mode, typ,
                      " ".join(f"{k}={v}" for k, v in sorted(zeiten.items())))
            yield _sse({"type": "done", "cited": cited, "timings": zeiten})
        except Exception:  # noqa: BLE001 — surface a terminal error to the client
            _log.exception("KI-Frage fehlgeschlagen")
            yield _sse({"type": "error", "message": "Frage fehlgeschlagen."})

    return StreamingResponse(
        gen(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
