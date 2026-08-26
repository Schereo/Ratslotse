"""Ratsinformationssystem: browse and search sessions, agenda items, committees."""
from __future__ import annotations

import json
import logging
import math
import time
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field, field_validator

from council.store import CouncilStore
from council.topics import POLICY_FIELDS
from council.goals import GOALS
from council.parties import faction_label, normalize_party, order_key
from council import qa
from council import ernte
from council import importance
from council import sitzungspause as pause_mod
from council import vorlagen as vorlagen_mod

from kern.store import Store

from .. import deepresearch
from ..config import get_settings
from ..deps import get_council_store, get_store, optional_user, require_active
from ..ratelimit import partei_meinungen_limiter, qa_feedback_limiter, qa_limiter, qa_share_limiter

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


@router.get("/wochenvorschau")
def wochenvorschau(
    user: dict = Depends(require_active),
    store: CouncilStore = Depends(get_council_store),
    nwz: Store = Depends(get_store),
) -> dict:
    """„Die Woche im Rat" (Design 14, davor 11d/12) — als VORSCHAU auf die
    kommenden Sitzungen, nicht als Rückblick auf Beschlüsse.

    Der Entwurf führt beide Blickrichtungen (Punkt 1 kündigt an, Punkt 4 blickt
    zurück); tragfähig ist nur die vordere: Beschlüsse erreichen uns erst mit
    dem Protokoll, im Median 119 Tage nach der Sitzung. Tagesordnungen liegen
    dagegen vor dem Termin vor.

    Seit Design 14 trägt die Antwort **jede** Sitzung der Woche und dazu die
    relevanten Punkte je Sitzung — die Karte ersetzt damit auch „Nächste
    Sitzungen". Die Themen-Treffer liegen in der anderen Datenbank (Konten und
    Themen), deshalb werden sie hier geholt und hineingereicht.
    """
    vorschau_ksinrs = [s["ksinr"] for s in store.sitzungen_im_fenster()]
    meine = nwz.agenda_matches_for_owner(user["id"], vorschau_ksinrs)
    return store.wochenvorschau(meine=meine)


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
    # „Zuletzt geändert" (Tims Wunsch 18.08.): Die Push zur Änderungsmeldung
    # sagt nur noch den Satz — die Einzelheiten stehen hier, aus der Chronik.
    session["aenderungen"] = _agenda_aenderungen(store, ksinr)
    return session


def _agenda_aenderungen(store: CouncilStore, ksinr: int) -> list[dict]:
    from council.agenda_diff import diff_satz, diff_zeilen

    out: list[dict] = []
    try:
        for c in store.agenda_changes(ksinr, limit=3):
            zeilen = diff_zeilen(c["diff"])
            if zeilen:
                out.append({"changed_at": c["changed_at"],
                            "satz": diff_satz(c["diff"]), "zeilen": zeilen})
    except Exception:  # noqa: BLE001 — Chronik ist Zusatz, nie 404/500 der Sitzung
        _log.exception("agenda_aenderungen fehlgeschlagen für %s", ksinr)
    return out


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
              "bis": b["bis"], "url": b["url"], "status": b.get("status") or "laufend",
              "beendet_am": b.get("beendet_am")}
             # Auch beendete: Sie sind der einzige Ort, an dem eine
             # abgelaufene Beteiligung überhaupt noch dokumentiert ist.
             for b in store.list_beteiligungen(nur_laufende=False)
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
        # Beschlüsse leben vom Bild, nicht vom Anlagen-Download. Echte
        # Planzeichnungen vor Mischdokumenten: „Begründung mit Leitplan" hat
        # auch bild=1, zeigt auf Seite 1 aber Begründungstext — alphabetisch
        # gewann „B…" vor „P…" (Review-Befund P3, kvonr 16438/17168).
        def _plan_rang(a: dict) -> int:
            label = (a.get("label") or "").lower()
            return 0 if ("planzeichnung" in label or "plandarstellung" in label) else 1

        bilder = sorted((a for a in out["anlagen"] if a.get("bild") == 1), key=_plan_rang)
        out["plan_bild"] = bilder[0]["document_id"] if bilder else None
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


# ---- „Meine Gespräche" (5a/I-04 + Design 6a) --------------------------------


class GespraechEinstellungBody(BaseModel):
    an: bool


@router.get("/gespraeche")
def gespraeche_liste(user: dict = Depends(require_active),
                     nwz: Store = Depends(get_store)) -> dict:
    """Einwilligungs-Stand + gespeicherte Gespräche des Kontos. `einstellung`
    ist null, solange die Erstnutzungs-Frage (6a①) nie beantwortet wurde."""
    return {"einstellung": nwz.get_qa_speichern(user["id"]),
            "gespraeche": nwz.qa_gespraeche(user["id"])}


@router.post("/gespraeche/einstellung")
def gespraeche_einstellung(body: GespraechEinstellungBody,
                           user: dict = Depends(require_active),
                           nwz: Store = Depends(get_store)) -> dict:
    """6a②: Schalter setzen. Löscht nichts — das entscheidet der Dialog
    über DELETE /gespraeche getrennt."""
    nwz.set_qa_speichern(user["id"], body.an)
    return {"einstellung": 1 if body.an else 0}


@router.get("/gespraeche/{gespraech_id}")
def gespraech_detail(gespraech_id: int, user: dict = Depends(require_active),
                     nwz: Store = Depends(get_store)) -> dict:
    g = nwz.qa_gespraech(gespraech_id, user["id"])
    if not g:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Gespräch nicht gefunden.")
    for t in g["turns"]:
        try:
            t["quellen"] = json.loads(t["quellen"]) if t["quellen"] else None
        except ValueError:
            t["quellen"] = None
    return g


class GespraechUmbenennenBody(BaseModel):
    titel: str = Field(min_length=1, max_length=120)


@router.patch("/gespraeche/{gespraech_id}")
def gespraech_umbenennen(gespraech_id: int, body: GespraechUmbenennenBody,
                         user: dict = Depends(require_active),
                         nwz: Store = Depends(get_store)) -> dict:
    """Design 9a②: Umbenennen aus dem Gespräche-Sheet (Wisch nach links)."""
    if not nwz.qa_gespraech_umbenennen(gespraech_id, user["id"], body.titel):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Gespräch nicht gefunden.")
    return {"ok": True}


@router.delete("/gespraeche/{gespraech_id}")
def gespraech_loeschen(gespraech_id: int, user: dict = Depends(require_active),
                       nwz: Store = Depends(get_store)) -> dict:
    if not nwz.qa_gespraech_loeschen(gespraech_id, user["id"]):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Gespräch nicht gefunden.")
    return {"ok": True}


@router.delete("/gespraeche")
def gespraeche_alle_loeschen(user: dict = Depends(require_active),
                             nwz: Store = Depends(get_store)) -> dict:
    return {"geloescht": nwz.qa_gespraeche_loeschen(user["id"])}


class QaFeedbackBody(BaseModel):
    frage: str = Field(min_length=1, max_length=300)
    antwort_auszug: str | None = Field(default=None, max_length=500)
    bewertung: str = Field(pattern="^(up|down)$")
    grund: str | None = Field(default=None, max_length=500)


@router.post("/qa-feedback", status_code=status.HTTP_201_CREATED)
def qa_feedback(
    body: QaFeedbackBody,
    request: Request,
    user: dict | None = Depends(optional_user),
    store: CouncilStore = Depends(get_council_store),
) -> dict:
    """Daumen hoch/runter zu einer KI-Antwort (5a/I-03) — der einzige
    Qualitätsmesser außerhalb der Eval-Gold-Fälle. Anonym erlaubt (die
    KI-Frage selbst ist es auch); die Feldlängen begrenzt das Schema, das
    Rate-Limit hält Skript-Flutung von Tabelle und Backups fern."""
    qa_feedback_limiter.check(request)
    store.save_qa_feedback(body.frage, body.antwort_auszug, body.bewertung,
                           body.grund, user_id=(user or {}).get("id"))
    return {"ok": True}


class ParteiMeinungenBody(BaseModel):
    frage: str = Field(min_length=3, max_length=300)
    #: Die Beschlüsse, auf denen die Antwort steht (Reihenfolge = Relevanz).
    #: Über sie kommt die Aussprache dazu, die ZU diesen Stationen gehört —
    #: siehe Kommentar im Endpoint. Leer (ältere Clients) → nur Vektor-Kanal.
    beschluss_ids: list[int] = Field(default_factory=list, max_length=20)


@router.post("/partei-meinungen")
def partei_meinungen_endpoint(
    body: ParteiMeinungenBody,
    request: Request,
    user: dict = Depends(require_active),
    store: CouncilStore = Depends(get_council_store),
) -> dict:
    """Baustein „Das sagen die Parteien" (Task 30): Wird vom Frontend NACH der
    gestreamten Antwort geladen (kostet die Hauptantwort keine Latenz). Sammelt
    aus ZWEI Kanälen — fraktions-bewusste Ähnlichkeitssuche (Cross-Encoder-
    geprüft) und die Aussprache zu den belegten Beschlüssen — und verdichtet
    das per LLM je Fraktion. Leer ({parteien: []}), wenn die Datenlage zu dünn
    ist — der Baustein erscheint dann nicht."""
    if not user.get("limits_frei"):
        partei_meinungen_limiter.check(request)
    try:
        import hashlib

        from council import embeddings as emb
        # Fraktions-bewusst sammeln (je Fraktion bis 5 Beiträge) — das globale
        # Top-24 bestand zur Hälfte aus Verwaltungs-Beiträgen ohne Fraktion,
        # die „Parteimeinung" war real eine Einzel-Paraphrase (Befund 10.08.).
        hits = emb.search_wortbeitraege_je_fraktion(store, body.frage, body.frage)
        # ZWEITER KANAL: die Aussprache, die zu den belegten Beschlüssen GEHÖRT.
        # Der Vektor-Kanal sucht nach Ähnlichkeit zur Frage und findet damit
        # das Wortfeld — nicht zwingend die Debatte zur Sache. Auf „Was ist die
        # Baumschutzsatzung …?" zeigte die Quellenspalte (die diesen Kanal
        # schon hatte) neun CDU- und zehn SPD-Beiträge, während der Baustein
        # daneben „keine passenden Wortbeiträge von CDU" behauptete (Tims
        # Befund 21.08.2026). Zugehörigkeit ist hier das bessere Signal als
        # Ähnlichkeit — deshalb OHNE Torwächter: Die Station ist ja belegt.
        anker: list[dict] = []
        if body.beschluss_ids:
            try:
                anker = store.wortbeitraege_zu_beschluessen(
                    store.get_decisions_by_ids(body.beschluss_ids[:10]),
                    max_gesamt=60, max_je_top=12)
            except Exception:  # noqa: BLE001 — Anker ist Zusatz, nie Blocker
                anker = []
        # Cache über den Hash der Beitrags-IDs: verschieden formulierte Fragen
        # zum selben Thema (Stadion!) sammeln dieselben Beiträge ein → Treffer
        # ohne LLM-Call; ein neuer Beitrag ändert den Hash → Nachverdichtung.
        # „v3": seit dem Beschluss-Anker — die alten Einträge kennen nur den
        # Vektor-Kanal und sollen nicht 14 Tage weiterleben.
        alle_ids = sorted({wid for wid, _ in hits} | {r["id"] for r in anker})
        schluessel = "v3:" + hashlib.sha1(
            ",".join(str(wid) for wid in alle_ids).encode()).hexdigest()
        meinungen = store.partei_meinungen_cache_get(schluessel) if alle_ids else None
        if meinungen is None and alle_ids:
            vektor = store.wortbeitraege_by_ids([wid for wid, _ in hits])
            schon = {r["id"] for r in vektor}
            rows = vektor + [r for r in anker if r["id"] not in schon]
            # FDP/Volt über die Personen-Stammdaten in Einzel-Parteien
            # auflösen (Tims Standing-Punkt) — der Baustein führt die beiden
            # danach getrennt, statt sie in einen Gruppen-Eimer zu werfen.
            qa.parteien_aufloesen(store, rows)
            meinungen = qa.partei_meinungen(body.frage, rows)
            if meinungen:
                store.partei_meinungen_cache_set(schluessel, body.frage, meinungen)
        # Vollständigkeits-Ehrlichkeit (Tims Direktive 10.08.): Fraktionen, die
        # im Rat aktiv sind, aber ohne passende Wortbeiträge zum Thema — der
        # Baustein sagt das, statt sie stillschweigend wegzulassen. Die
        # FDP/Volt-Gruppe zählt dabei als ihre beiden Einzel-Parteien.
        ohne: list[str] = []
        if meinungen:
            # Beide Seiten durch dieselbe Kanonisierung: Die Anwesenheits-
            # Labels führen auch Verbände, Rollen und kaputte Einzel-Label als
            # „Partei" („ADFC", „Elternvertreter", „BSW Für RH Dr. Onken") —
            # in der Ehrlichkeits-Zeile stehen nur echte Ratsparteien (Tims
            # TestFlight-Feedback 11.08.), und „CDU-Fraktion" dedupliziert
            # gegen „CDU" statt daneben zu erscheinen.
            vertreten = {qa.ratspartei_label(e["partei"]) or qa._fraktions_label(e["partei"])
                         for e in meinungen}
            aktive: list[str] = []
            for x in store.aktive_fraktionen():
                label = qa.ratspartei_label(x)
                # FDP und Volt sitzen diese Ratsperiode als EINE Gruppe: taucht
                # eine der beiden (oder das Gruppen-Label) auf, sind beide
                # aktiv — die Protokolle labeln uneinheitlich mal Gruppe, mal
                # Einzelpartei, und Volt fiele sonst still aus der
                # Ehrlichkeits-Zeile.
                if label in ("FDP/Volt", "FDP", "Volt"):
                    aktive += ["FDP", "Volt"]
                elif label:
                    aktive.append(label)
            gesehen_aktiv: set[str] = set()
            aktive = [f for f in aktive if not (f in gesehen_aktiv or gesehen_aktiv.add(f))]
            ohne = [f for f in aktive if f not in vertreten]
    except Exception:  # noqa: BLE001 — Zusatzbaustein, nie 500 im Gespräch
        _log.exception("partei_meinungen fehlgeschlagen")
        meinungen = None
        ohne = []
    return {"parteien": meinungen or [], "ohne_beitraege": ohne}


class QaShareQuelle(BaseModel):
    id: int
    title: str = Field(max_length=300)
    session_date: str | None = Field(default=None, max_length=10)
    committee: str | None = Field(default=None, max_length=120)
    outcome: str | None = Field(default=None, max_length=40)


class QaShareDebatte(BaseModel):
    sprecher: str | None = Field(default=None, max_length=120)
    partei: str | None = Field(default=None, max_length=60)
    art: str = Field(default="rede", max_length=30)
    top: str | None = Field(default=None, max_length=300)
    auszug: str = Field(default="", max_length=2000)
    committee: str | None = Field(default=None, max_length=120)
    datum: str | None = Field(default=None, max_length=10)
    protokoll_url: str | None = Field(default=None, max_length=500)
    protokoll_seite: int | None = Field(default=None, ge=1, le=9999)

    @field_validator("protokoll_url")
    @classmethod
    def _nur_ratsinfo(cls, v: str | None) -> str | None:
        # Der Snapshot ist öffentlich und der Client liefert die URL mit —
        # als „Protokoll" verlinken wir deshalb ausschließlich das
        # Ratsinfo-System, sonst ließe sich hier Beliebiges unterschieben.
        if v and not v.startswith(f"{BASE_URL}/"):
            return None
        return v


class QaSharePresse(BaseModel):
    titel: str = Field(max_length=300)
    url: str = Field(max_length=500)
    datum: str | None = Field(default=None, max_length=10)


class QaShareAnlage(BaseModel):
    # Beleg-Nummer des Recherche-Berichts („[A1]") — ohne sie findet der
    # Marker im geteilten Text seine Anlage nicht.
    nr: int | None = Field(default=None, ge=1, le=99)
    label: str | None = Field(default=None, max_length=300)
    url: str | None = Field(default=None, max_length=500)
    vorlage_nr: str | None = Field(default=None, max_length=60)
    vorlage_titel: str | None = Field(default=None, max_length=300)
    auszug: str = Field(default="", max_length=600)


class QaShareKernaussage(BaseModel):
    text: str = Field(default="", max_length=600)
    sprecher: str | None = Field(default=None, max_length=120)
    datum: str | None = Field(default=None, max_length=10)


class QaSharePartei(BaseModel):
    partei: str = Field(max_length=60)
    haltung: str | None = Field(default=None, max_length=20)
    position: str = Field(default="", max_length=800)
    einig: bool = True
    hinweis: str | None = Field(default=None, max_length=300)
    kernaussage: QaShareKernaussage | None = None
    beitraege: int = Field(default=0, ge=0)


class QaShareBody(BaseModel):
    frage: str = Field(min_length=1, max_length=300)
    antwort: str = Field(min_length=1, max_length=8000)
    quellen: list[QaShareQuelle] = Field(default_factory=list, max_length=40)
    # Bausteine neben den Beschlüssen: ohne sie zeigte die geteilte Seite
    # weniger als das Gespräch, aus dem sie stammt (Tims Befund 10.08.).
    debatten: list[QaShareDebatte] = Field(default_factory=list, max_length=20)
    presse: list[QaSharePresse] = Field(default_factory=list, max_length=10)
    anlagen: list[QaShareAnlage] = Field(default_factory=list, max_length=10)
    parteien: list[QaSharePartei] = Field(default_factory=list, max_length=12)


@router.post("/qa-share", status_code=status.HTTP_201_CREATED)
def qa_share_anlegen(
    body: QaShareBody,
    request: Request,
    user: dict = Depends(require_active),
    nwz: Store = Depends(get_store),
) -> dict:
    """Teilen mit Substanz (Task 31): speichert die KONKRETE Antwort als
    Snapshot — der alte ?q=-Link ließ Empfänger die Frage neu würfeln und
    eine andere Antwort sehen. Bewusste Einzel-Veröffentlichung per Klick."""
    if not user.get("limits_frei"):
        qa_share_limiter.check(request)
    extras = {
        "debatten": [d.model_dump() for d in body.debatten],
        "presse": [p.model_dump() for p in body.presse],
        "anlagen": [a.model_dump() for a in body.anlagen],
        "parteien": [p.model_dump() for p in body.parteien],
    }
    token = nwz.qa_share_anlegen(user["id"], body.frage, body.antwort,
                                 [q.model_dump() for q in body.quellen],
                                 extras if any(extras.values()) else None)
    return {"token": token}


@router.get("/qa-share/{token}")
def qa_share_lesen(token: str, nwz: Store = Depends(get_store)) -> dict:
    """Öffentliche Snapshot-Ansicht — bewusst OHNE Login (der Link soll auch
    Menschen ohne Konto erreichen); enthält nie Konto-Daten."""
    if len(token) > 64:
        raise HTTPException(status_code=404, detail="Nicht gefunden.")
    share = nwz.qa_share_get(token)
    if not share:
        raise HTTPException(status_code=404, detail="Nicht gefunden.")
    return share


# ---- „Gründliche Recherche" (RG-10, Task 34) -------------------------------
# Kein Request-gebundener Stream wie /ask: der Job läuft in einem Backend-
# Thread weiter, wenn der Client wegnavigiert (Tims Kernanforderung). POST
# startet, GET …/events klemmt sich an (Replay + live), GET …/{id} liefert
# den persistierten Endzustand — auch nach App- oder Server-Neustart.


class DeepResearchBody(BaseModel):
    frage: str = Field(min_length=4, max_length=300)
    # „Meine Gespräche": läuft ein Gespräch, wird der fertige Bericht dort
    # angehängt — auch wenn die App längst zu ist.
    gespraech_id: int | None = Field(default=None, ge=1)


def _deep_limit(user: dict) -> int | None:
    """Tageslimit des Kontos: Admin-Override aus web_users.deep_limit —
    None = unbegrenzt (Wert 0), sonst eigener Wert bzw. Standard."""
    override = user.get("deep_limit")
    if override == 0:
        return None
    return override if override is not None else deepresearch.TAGES_KONTINGENT


def _deep_frei(nwz: Store, user: dict) -> int | None:
    limit = _deep_limit(user)
    if limit is None:
        return None  # unbegrenzt — der Client zeigt dann keinen Zähler
    return max(0, limit - nwz.deep_jobs_heute(user["id"]))


@router.post("/deep-research", status_code=status.HTTP_201_CREATED)
def deep_research_start(body: DeepResearchBody, user: dict = Depends(require_active),
                        nwz: Store = Depends(get_store)) -> dict:
    """Recherche-Job starten. Kontingent: 5/Tag je KONTO aus der DB (nicht
    IP — übersteht Neustarts, und Abbruch/Fehler kosten laut Design nichts,
    was ein Fenster-Zähler nicht abbilden kann). Admins können das Limit je
    Konto erhöhen oder ausschalten (web_users.deep_limit)."""
    limit = _deep_limit(user)
    if limit is not None and nwz.deep_jobs_heute(user["id"]) >= limit:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS,
                            "Deine Recherchen für heute sind aufgebraucht — ab morgen geht es weiter.")
    if deepresearch.laufende_jobs(user["id"]) >= 1:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "Es läuft bereits eine Recherche — warte kurz, bis sie fertig ist.")
    if deepresearch.laufende_jobs() >= deepresearch.MAX_PARALLEL:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                            "Gerade laufen viele Recherchen — bitte versuche es gleich nochmal.")
    nwz.record_activity(user["id"], "recherche")
    frage = body.frage.strip()
    job_id = nwz.deep_job_anlegen(user["id"], frage)
    settings = get_settings()
    job = deepresearch.DeepJob(id=job_id, user_id=user["id"], frage=frage,
                               gespraech_id=body.gespraech_id)
    deepresearch.start_job(job, settings.nwz_db, settings.council_db)
    return {"job_id": job_id, "frei": _deep_frei(nwz, user)}


@router.get("/deep-research/aktuell")
def deep_research_aktuell(user: dict = Depends(require_active),
                          nwz: Store = Depends(get_store)) -> dict:
    """Der jüngste Job des Kontos + Rest-Kontingent — damit der Client nach
    Navigation/App-Neustart einen laufenden Job oder ungesehenen Bericht
    wiederfindet, ohne sich die ID gemerkt zu haben."""
    return {"job": nwz.deep_job_aktuell(user["id"]),
            "frei": _deep_frei(nwz, user)}


@router.get("/deep-research/{job_id}")
def deep_research_snapshot(job_id: str, user: dict = Depends(require_active),
                           nwz: Store = Depends(get_store)) -> dict:
    """Persistierter Stand des Jobs (Bericht + Quellen bei fertig/teilbericht)."""
    if len(job_id) > 64:
        raise HTTPException(status_code=404, detail="Nicht gefunden.")
    row = nwz.deep_job_get(job_id, user["id"])
    if not row:
        raise HTTPException(status_code=404, detail="Nicht gefunden.")
    # Läuft laut DB, aber kein Thread mehr da (Server-Neustart, Deploy):
    # ehrlich als Fehler ausweisen, sonst wartete der Client ewig.
    if row["status"] == "laeuft" and deepresearch.get_job(job_id) is None:
        nwz.deep_job_update(job_id, "fehler")
        row["status"] = "fehler"
    try:
        row["quellen"] = json.loads(row["quellen"]) if row.get("quellen") else None
    except (ValueError, TypeError):
        row["quellen"] = None
    return row


@router.get("/deep-research/{job_id}/events")
def deep_research_events(job_id: str, ab: int = Query(default=0, ge=0),
                         user: dict = Depends(require_active),
                         nwz: Store = Depends(get_store)) -> StreamingResponse:
    """SSE-Anschluss an einen laufenden Job: Replay aller Events ab ``ab``,
    dann live weiter. Ein Verbindungsabriss ist folgenlos — der Job läuft
    im Backend weiter, der Client verbindet sich einfach neu."""
    row = nwz.deep_job_get(job_id, user["id"])
    if not row:
        raise HTTPException(status_code=404, detail="Nicht gefunden.")
    job = deepresearch.get_job(job_id)
    if job is None:
        # Kein lebender Job (fertig + aus dem Speicher geräumt, oder Neustart)
        # → der Client holt den Endzustand über den Snapshot-Endpoint.
        raise HTTPException(status.HTTP_410_GONE, "Recherche nicht mehr aktiv — Snapshot laden.")
    return StreamingResponse(
        deepresearch.sse_events(job, ab=ab), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/deep-research/{job_id}/stop")
def deep_research_stop(job_id: str, user: dict = Depends(require_active),
                       nwz: Store = Depends(get_store)) -> dict:
    """Abbrechen (Design 8c⑥): stoppt vor dem nächsten Such-/LLM-Schritt.
    Fertige Facetten bleiben als Material — die Antwort sagt, ob sich ein
    Teilbericht lohnt. Kostet kein Kontingent."""
    if not nwz.deep_job_get(job_id, user["id"]):
        raise HTTPException(status_code=404, detail="Nicht gefunden.")
    job = deepresearch.get_job(job_id)
    if job is None or job.done:
        raise HTTPException(status.HTTP_409_CONFLICT, "Recherche läuft nicht mehr.")
    job.stop.set()
    with job.cond:
        job.cond.notify_all()
    return {"facetten_fertig": job.facetten_fertig,
            "facetten_gesamt": job.facetten_gesamt,
            "teilbericht_moeglich": bool(job.material and job.material.get("candidates"))}


@router.post("/deep-research/{job_id}/teilbericht")
def deep_research_teilbericht(job_id: str, user: dict = Depends(require_active),
                              nwz: Store = Depends(get_store)) -> dict:
    """Nach einem Stopp: aus den fertigen Facetten doch noch einen Bericht
    schreiben („Teilbericht zeigen"). Zählt nicht gegen das Kontingent."""
    row = nwz.deep_job_get(job_id, user["id"])
    if not row:
        raise HTTPException(status_code=404, detail="Nicht gefunden.")
    job = deepresearch.get_job(job_id)
    if job is None or row["status"] != "gestoppt":
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "Kein Teilbericht möglich — die Recherche ist nicht gestoppt.")
    if not (job.material and job.material.get("candidates")):
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "Kein Material gesichert — bitte neu recherchieren.")
    # Status VOR dem Thread-Start zurück auf laeuft — andersherum könnte der
    # (schnelle) Thread sein „teilbericht" schreiben und würde überschrieben.
    nwz.deep_job_update(job_id, "laeuft")
    settings = get_settings()
    deepresearch.teilbericht_starten(job, settings.nwz_db, settings.council_db)
    return {"ok": True}


@router.post("/deep-research/{job_id}/gesehen")
def deep_research_gesehen(job_id: str, user: dict = Depends(require_active),
                          nwz: Store = Depends(get_store)) -> dict:
    """Client hat den fertigen Bericht gerendert — nicht erneut einblenden."""
    nwz.deep_job_gesehen(job_id, user["id"])
    return {"ok": True}


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


# Personen-Lexikon für die Badges im Antwort-Text (Tims Wunsch 12.08.).
# Public wie public-stats: Die geteilten Antwort-Seiten (app/g) brauchen es
# ohne Konto, und der Inhalt sind amtliche RIS-Daten. Prozess-Cache mit
# Tages-TTL — die Quelle ändert sich höchstens mit dem täglichen Import.
_PERSONEN_LEXIKON_CACHE: dict = {"stand": 0.0, "daten": None}


@router.get("/personen-lexikon")
def personen_lexikon(response: Response,
                     store: CouncilStore = Depends(get_council_store)) -> dict:
    import time as _time
    if _PERSONEN_LEXIKON_CACHE["daten"] is None or \
            _time.time() - _PERSONEN_LEXIKON_CACHE["stand"] > 6 * 3600:
        _PERSONEN_LEXIKON_CACHE["daten"] = store.personen_lexikon()
        _PERSONEN_LEXIKON_CACHE["stand"] = _time.time()
    response.headers["Cache-Control"] = "public, max-age=21600"
    return {"personen": _PERSONEN_LEXIKON_CACHE["daten"]}


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


@router.get("/person/{slug}/wortbeitraege")
def person_wortbeitraege(slug: str, gremium: str | None = None,
                         offset: int = Query(default=0, ge=0),
                         limit: int = Query(default=20, ge=1, le=100),
                         store: CouncilStore = Depends(get_council_store)) -> dict:
    """Wortbeiträge einer Person, seitenweise und nach Gremium filterbar.

    Öffentlich wie die Personen-Seite selbst — es ist derselbe Bestand, nur
    vollständig statt auf die jüngsten zehn gekürzt.
    """
    name = store.member_name(slug)
    if not name:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ratsmitglied nicht gefunden.")
    return store.wortbeitraege_person(name, gremium=gremium, offset=offset, limit=limit)


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
    # „Meine Gespräche" (6a): laufendes Gespräch, an das der Turn gehängt wird —
    # nur wirksam, wenn das Konto qa_speichern = 1 gesetzt hat.
    gespraech_id: int | None = Field(default=None, ge=1)
    # „Einfacher erklären": die zuletzt angezeigte Antwort im VOLLTEXT — genau
    # die soll umgeschrieben werden. Der `verlauf` taugt dafür nicht, dort ist
    # jede Antwort auf 600 Zeichen gekappt (er dient dem Auflösen von
    # Rückbezügen, nicht dem Zitieren). Wird nur benutzt, wenn die Frage
    # tatsächlich um eine einfachere Fassung bittet; alte App-Versionen senden
    # das Feld nicht und bekommen die einfache Fassung aus den Beschlüssen.
    vorherige_antwort: str = Field(default="", max_length=8000)


# Q&A sizing: show up to QA_TOP_K reranked decisions as sources, feed the most
# relevant QA_ANSWER_N to the LLM for a focused, cited answer. QA_MIN_SCORE drops
# the near-irrelevant tail from the displayed sources (sigmoid relevance).
QA_TOP_K = 40
QA_ANSWER_N = 20
QA_MIN_SCORE = 0.2
# Sitzungs-Fragetyp: der Antwort-Kontext trägt die GANZE Sitzung — der Deckel
# schützt nur vor Ausreißern (größte Rats-Tagesordnung im Bestand: 47 TOPs).
QA_SITZUNG_N = 60
# jina-reranker-v2 logits are negative-centred (a clearly relevant match still scores
# below 0), so a raw sigmoid under-sells good hits (~50 % for the top result). Shift by
# a fixed bias so a relevant decision reads as a high-but-honest relevance.
QA_RERANK_BIAS = 1.5


def _qa_retrieve(store: CouncilStore, q: str, expanded: str,
                 timings: dict | None = None,
                 varianten: list[str] | None = None) -> tuple[list[dict], str]:
    """Hybrid retrieval + cross-encoder rerank → candidates in relevance order, each
    with an *absolute* relevance score: the sigmoid of the reranker logit, NOT a
    min-max normalisation (which forced the weakest hit to a misleading 0 %). Falls
    back to keyword retrieval when embeddings/the reranker are unavailable."""
    try:
        from council import embeddings as emb
        # Akkuratheits-Paket: deterministische Signale neben der Semantik —
        # Entitäts-Anker (benannte Objekte der Frage) in den Rerank-Pool,
        # Frische-Bonus bei Sachstands-Formulierungen.
        hits = emb.hybrid_search(store, q, expanded, top_k=QA_TOP_K, pool=55, timings=timings,
                                 varianten=varianten,
                                 anker_ids=qa.anker_ids_fuer(store, q),
                                 recency=qa.recency_intent(q))
        if hits:
            candidates = store.get_decisions_by_ids([h[0] for h in hits])  # preserves order
            score = {h[0]: h[1] for h in hits}
            for c in candidates:
                logit = score.get(c["id"])
                c["score"] = round(1.0 / (1.0 + math.exp(-(logit + QA_RERANK_BIAS))), 3) if logit is not None else None
            # „Ältere Station"-Marker: überholte Zwischenstände derselben
            # Vorlage werden im Kontext als solche ausgewiesen.
            qa.markiere_veraltete(store, candidates)
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
        # Kostenentwicklung (10.08.26): Familien-Erkennung (gleiche Vorlage)
        # für das ehrliche Delta im Geld-Baustein — nur dort ist „gestiegen
        # von X auf Y" belegbar, alles andere wäre ein Äpfel/Birnen-Vergleich.
        "vorlage_nr": c.get("vorlage_nr"),
        "factions": qa._factions_of(c),
        # 5a/I-10: verortete Entität für die Mini-Karte unter der Antwort.
        "ort_name": c.get("ort_name"), "lat": c.get("lat"), "lon": c.get("lon"),
    }


def _presse_kompakt(rows: list[dict]) -> list[dict]:
    """Anzeige-Form der Presse-Treffer — identisch im sources-Event und im
    Gesprächs-Snapshot, damit ein geladenes Gespräch nichts verliert."""
    return [{"titel": p.get("titel"), "url": p.get("url"),
             "datum": p.get("datum")} for p in rows]


def _debatten_kompakt(rows: list[dict]) -> list[dict]:
    return [{"sprecher": d.get("sprecher"), "partei": d.get("partei"),
             "art": d.get("art"), "top": d.get("top"),
             "auszug": (d.get("text") or "")[:2000],
             "committee": d.get("committee"),
             "datum": d.get("session_date"),
             "protokoll_url": d.get("protokoll_url"),
             # PDF-Seite der Fundstelle (Sprecher-Anker); None = Link ohne #page.
             "protokoll_seite": d.get("seite")} for d in rows]


def _turn_speichern(nwz: Store, user: dict, body: AskBody, q_suche: str,
                    answer_text: str, candidates: list[dict],
                    cited: list[int],
                    presse_rows: list[dict] | None = None,
                    debatten_rows: list[dict] | None = None,
                    planungen: list[dict] | None = None) -> int | None:
    """„Meine Gespräche" (6a): Turn ins laufende Gespräch hängen (oder eines
    eröffnen) — nur mit ausdrücklicher Einwilligung, nie als Blocker.

    Nur wenn der Client das Feld ``gespraech_id`` überhaupt kennt: Alte
    App-Versionen senden es nie und können die zurückgegebene id nicht
    weiterreichen — jede Frage würde sonst ein 1-Turn-Fragment eröffnen und
    die Gespräche-Liste fluten (Review-Befund B5). Ein frisch eröffnetes
    Gespräch wird wieder gelöscht, wenn der Turn-Insert scheitert — sonst
    bliebe ein leerer Eintrag in der Liste zurück (Befund B2)."""
    try:
        if "gespraech_id" not in body.model_fields_set:
            return None
        if not answer_text.strip() or nwz.get_qa_speichern(user["id"]) != 1:
            return None
        gespraech_id = body.gespraech_id
        neu = gespraech_id is None
        if neu:
            gespraech_id = nwz.qa_gespraech_start(user["id"], q_suche or body.question)
            if gespraech_id is None:
                return None
        zitiert = set(cited)
        # Presse + Debatten gehören MIT in den Snapshot: Ohne sie öffnete ein
        # gespeichertes Gespräch ohne den „Aktuelles von der Stadt"-Block und
        # ohne Debatten — und damit auch ohne den Parteien-Baustein, der am
        # Debatten-Gate hängt (Tims Befund 10.08.).
        quellen_json = json.dumps(
            {"sources": [_qa_source(c) for c in candidates if c["id"] in zitiert],
             "cited": cited,
             # Die KONDENSIERTE Frage mit in den Snapshot: „Und was kostet
             # das?" wird beim Antworten zu einer eigenständigen Frage
             # verdichtet, und Bausteine, die danach nachladen (der
             # Parteien-Baustein), schlüsseln darauf. Ohne sie baute ein
             # wiederhergestelltes Gespräch den Turn mit der Originalfrage auf
             # — anderer Schlüssel, also lud der Baustein beim Zurückwechseln
             # auf den Fragen-Tab komplett neu und fragte dabei mit der
             # kontextlosen Frage (Tims Befund 21.08.2026).
             "kontext": q_suche,
             "presse": _presse_kompakt(presse_rows or []),
             "debatten": _debatten_kompakt(debatten_rows or []),
             # Der Ausblick gehört wie Presse und Debatten in den Snapshot,
             # sonst öffnet ein gespeichertes Gespräch ohne „Wie es weitergeht".
             "planungen": planungen or []}, ensure_ascii=False)
        if not nwz.qa_turn_speichern(gespraech_id, user["id"],
                                     body.question, answer_text, quellen_json):
            if neu:
                nwz.qa_gespraech_loeschen(gespraech_id, user["id"])
            return None
        return gespraech_id
    except Exception:  # noqa: BLE001 — Speichern ist Zusatz, nie Blocker
        return None


@router.post("/ask")
def ask(body: AskBody, request: Request, user: dict = Depends(require_active),
        store: CouncilStore = Depends(get_council_store),
        nwz: Store = Depends(get_store)) -> StreamingResponse:
    """Answer a free-text question from the decisions, streamed as Server-Sent Events:
    progress steps → the ranked source decisions (the moment retrieval+rerank finish)
    → the answer token-by-token → a final event with the cited ids. Streaming makes
    the wait feel far shorter (sources show in ~2 s) and degrades gracefully if a
    proxy buffers it (the client then renders the same final state at once)."""
    if not user.get("limits_frei"):  # Admin kann Konten befreien (web_users.limits_frei)
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
            # Punktfrage (Datum/Zahl/Name)? Dann antwortet das Modell knapp —
            # der Befund kam aus einer echten Nutzer-Frage, der nach dem
            # gesuchten Datum noch fünf Redebeiträge folgten (12.08.).
            eng = bool(analyse.get("eng"))
            # „Einfacher erklären" (Befund Build 11): Der Wunsch nach einfacher
            # Sprache ist KEINE neue Frage — er verlangt dieselbe Auskunft in
            # anderer Sprache. Deshalb ein eigener Prompt statt einer weiteren
            # Zeile im Antwort-Prompt, wo er gegen zwei Dutzend Präzisions-
            # Regeln verlor. Erkennung am ROHEN Fragetext: die kondensierte
            # Fassung aus der Analyse hat den Wunsch schon wegübersetzt.
            einfach = qa.will_vereinfachung(q)
            if einfach:
                eng = False  # „kurz und knapp" und „einfach" sind zwei Register
            # Retrieval + Reranker arbeiten mit der EIGENSTÄNDIGEN Fassung der
            # Frage — „Und was kostet das?" sucht sonst nach nichts.
            q_suche = analyse["frage"]
            zeiten["expand_ms"] = round((time.perf_counter() - t0) * 1000)
            # Personen-Fragetyp (10.08.26): nennt die Frage eine Ratsperson,
            # antworten wir aus DEREN Wortbeiträgen — deterministisch erkannt,
            # schlägt thema/verlauf (nicht aber partei/geld).
            person = qa.finde_person(store, q_suche)
            if person and typ not in ("partei", "geld"):
                typ = "person"
            # Sitzungs-Fragetyp (25.08.26): Nennt die Frage ein konkretes
            # Sitzungsdatum oder die letzte/nächste Sitzung eines Gremiums,
            # wird die Sitzung deterministisch aufgelöst und ihre Beschlüsse
            # kommen VOLLSTÄNDIG in den Kontext. Die Ähnlichkeitssuche allein
            # ließ beim Rückblick auf den Jugendhilfeausschuss vom 17.06.2026
            # drei der sechs TOPs weg, darunter einen echten Beschluss (echte
            # Nutzerfrage 25.08.). partei/geld/person behalten Vorrang.
            # Erkennung auf der kondensierten UND der rohen Frage: Die Analyse
            # schreibt „im Bauausschuss morgen" gern zu „am morgigen Tag" um —
            # was die Kondensierung an Signalwörtern verschluckt, trägt die
            # Original-Frage noch (Tims Befund 26.08., zweiter Anlauf).
            sitzungen = [] if person else (qa.finde_sitzungen(store, q_suche)
                                           or qa.finde_sitzungen(store, q))
            sitzung_ids = [i for s in sitzungen for i in s.get("beschluss_ids") or []]
            if sitzungen and typ not in ("partei", "geld"):
                typ = "sitzung"
            yield _sse({"type": "step", "step": "search"})
            t0 = time.perf_counter()
            candidates, mode = _qa_retrieve(store, q_suche, expanded, timings=zeiten,
                                            varianten=analyse.get("varianten"))
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
            if sitzung_ids:
                # Die aufgelöste Sitzung VOLLSTÄNDIG in den Kandidatenpool —
                # beim Sitzungs-Fragetyp in Tagesordnungs-Reihenfolge nach
                # vorn, denn daran hängen das Aussprache-Nachladen
                # (candidates[:8]) und der Antwort-Kontext.
                have = {c["id"] for c in candidates}
                nachgeladen = store.get_decisions_by_ids(
                    [i for i in sitzung_ids if i not in have])
                if typ == "sitzung":
                    pos = {i: n for n, i in enumerate(sitzung_ids)}
                    eigene = sorted(
                        [c for c in candidates if c["id"] in pos] + nachgeladen,
                        key=lambda c: pos[c["id"]])
                    candidates = eigene + [c for c in candidates if c["id"] not in pos]
                else:
                    candidates += nachgeladen
            # Beim Vereinfachen zählen die Belege der VORIGEN Antwort: Ihre ids
            # müssen im Kandidatenset stehen, sonst streicht resolve_citations
            # genau die Fußnoten weg, die die einfache Fassung übernehmen soll —
            # die Antwort verlöre beim Vereinfachen ihre Quellen.
            vorher_ids: list[int] = []
            if einfach and body.vorherige_antwort.strip():
                try:
                    zitiert = qa.zitierte_ids(body.vorherige_antwort)
                    have = {c["id"] for c in candidates}
                    fehlend = [i for i in zitiert if i not in have]
                    if fehlend:
                        candidates += store.get_decisions_by_ids(fehlend)
                        have = {c["id"] for c in candidates}
                    vorher_ids = [i for i in zitiert if i in have]
                except Exception:  # noqa: BLE001 — Nachladen ist Zusatz, nie Blocker
                    vorher_ids = []
            presse_rows: list[dict] = []
            try:
                # Eigener Kanal neben den Beschlüssen: „Aktuelles von der Stadt"
                # (Pressemitteilungen) — strenge Schwelle, oft leer.
                from council import embeddings as emb
                hits_p = emb.search_presse(store, q_suche, expanded)
                presse_rows = store.presse_by_ids([pid for pid, _ in hits_p])
            except Exception:  # noqa: BLE001 — Presse ist Zusatz, nie Blocker
                pass
            debatten_rows: list[dict] = []
            try:
                # Task 16: Wortbeiträge aus den Protokollen (Reden, Anfragen,
                # Einwohnerfragen, Zusagen) — die Substanz, die nicht in den
                # Beschlusstexten steht. Strenge Schwelle, oft leer. Beim
                # Personen-Fragetyp stattdessen die Beiträge DIESER Person.
                from council import embeddings as emb
                if person:
                    debatten_rows = emb.search_wortbeitraege_von_person(
                        store, q_suche, person["nachname"])
                else:
                    hits_w = emb.search_wortbeitraege(store, q_suche, expanded)
                    debatten_rows = store.wortbeitraege_by_ids([wid for wid, _ in hits_w])
                    # … plus die Aussprache ZU den gefundenen Beschlüssen:
                    # Fachsprache (Vinylchlorid, Messpunkte) liegt außerhalb
                    # des Frage-Wortfelds und fällt durch die Ähnlichkeits-
                    # suche — Zugehörigkeit trägt hier weiter (Befund 10.08.).
                    have = {d["id"] for d in debatten_rows}
                    debatten_rows += [w for w in store.wortbeitraege_zu_beschluessen(
                        candidates[:8]) if w["id"] not in have]
                # Zusagen der Verwaltung als EIGENER Kanal: Im allgemeinen
                # Debatten-Ranking gingen sie unter (1 von 19 Belegen; selbst
                # auf „Was hat die Verwaltung zugesagt?" kam keine), weil sie
                # kurz und nüchtern formuliert sind. Dabei sind sie der
                # besondere Stoff — eine Selbstverpflichtung mit Datum.
                if not person:
                    try:
                        hits_z = emb.search_zusagen(store, q_suche, expanded)
                        schon = {r["id"] for r in debatten_rows}
                        debatten_rows += [r for r in store.wortbeitraege_by_ids(
                            [wid for wid, _ in hits_z]) if r["id"] not in schon]
                    except Exception:  # noqa: BLE001 — Zusatz, nie Blocker
                        pass
                # FDP/Volt-Beiträge in die Einzel-Partei auflösen (Stammdaten).
                qa.parteien_aufloesen(store, debatten_rows)
            except Exception:  # noqa: BLE001 — Debatten sind Zusatz, nie Blocker
                pass
            # Beleg nachlesbar machen: jeder Beitrag bekommt die PDF-URL
            # seines Protokolls (Tims Wunsch 18.08.).
            qa.protokolle_verlinken(store, debatten_rows)
            # 5a/I-10: Orts-Pins für die Mini-Karte — deterministisch aus den
            # geocodierten Entitäten, nie vom Sprachmodell.
            try:
                orte = store.orte_fuer_decisions([c["id"] for c in candidates])
                for c in candidates:
                    c.update(orte.get(c["id"], {}))
            except Exception:  # noqa: BLE001 — Karte ist Zusatz, nie Blocker
                pass
            # „Wie es weitergeht" (Paket 1): künftige Beratungsstationen der
            # gefundenen Vorlagen. Bisher gab es den Blick nach vorn NUR in der
            # Gründlichen Recherche — dabei sind Sachstands-Fragen („Wie ist
            # der aktuelle Stand zum Stadion?") der häufigste Fragetyp
            # überhaupt, und die Termine stehen längst gepflegt in der DB.
            planungen: list[dict] = []
            try:
                planungen = store.geplante_beratungen_fuer(
                    [c.get("kvonr") for c in candidates[:20]])
                # Zweiter Weg, weil der erste systematisch leer läuft: Auf der
                # Tagesordnung stehen die noch NICHT entschiedenen Vorlagen —
                # die Suche findet aber Beschlüsse. Titel-Abgleich gegen die
                # Suchbegriffe holt das Kommende zum Thema dazu.
                gesehen = {p["kvonr"] for p in planungen}
                planungen += [p for p in store.kommende_beratungen(expanded.split())
                              if p["kvonr"] not in gesehen]
            except Exception:  # noqa: BLE001 — Ausblick ist Zusatz, nie Blocker
                pass
            # Hintergrund zu den genannten Objekten („Was ist die GSG?").
            steckbriefe = qa.steckbriefe_fuer(store, q_suche)
            # Wie tragfähig ist der Fund? Deterministisch aus den Scores.
            lage = qa.beleglage(candidates)
            if typ == "sitzung" and sitzung_ids:
                # Die Sitzung ist deterministisch aufgelöst, kein Ähnlichkeits-
                # Raten — die Dünn-Regel hätte hier nichts zu bremsen.
                lage = "solide"
            zeiten["retrieve_ms"] = round((time.perf_counter() - t0) * 1000)
            # 5a/I-06: die kondensierte Frage mitschicken — der Kontext-Chip im
            # Frontend zeigt, worauf sich Anschlussfragen beziehen.
            yield _sse({"type": "sources", "mode": mode, "qtype": typ,
                        "frage": q_suche,
                        "sources": [_qa_source(c) for c in candidates],
                        "presse": _presse_kompakt(presse_rows),
                        "debatten": _debatten_kompakt(debatten_rows),
                        "planungen": planungen,
                        "beleglage": lage,
                        # Der Hintergrund geht IMMER in die Antwort; als eigene
                        # Karte erscheint er nur, wenn die Antwort ihn nicht
                        # ohnehin wiederholt (Definitionsfragen, Tims Befund).
                        "steckbriefe": [{"name": s["name"], "slug": s["slug"],
                                         "beschreibung": s["description"]}
                                        for s in steckbriefe]
                        if qa.steckbrief_karte_zeigen(q_suche) else []})
            yield _sse({"type": "step", "step": "answer"})
            if not candidates:
                leer_text = "Dazu habe ich keine passenden Beschlüsse gefunden."
                if sitzungen:
                    # Die gefragte Sitzung IST aufgelöst — sie hat nur (noch)
                    # keine Beschlüsse: künftiger Termin oder Protokoll-Verzug.
                    # Das pauschale „nichts gefunden" wäre hier die falsche
                    # Auskunft.
                    leer_text = qa.sitzungs_leer_text(sitzungen)
                elif debatten_rows:
                    # Die Debatten-Treffer stehen bereits sichtbar in den
                    # Belegen — ein hartes „nichts gefunden" daneben wäre
                    # gelogen (Review-Befund zu #387).
                    leer_text = ("Dazu habe ich keine passenden Beschlüsse gefunden — "
                                 "aber Wortbeiträge aus den Ratsdebatten, siehe Belege.")
                yield _sse({"type": "token", "text": leer_text})
                # Auch der Kein-Treffer-Turn gehört ins gespeicherte Gespräch —
                # sonst klafft im Transkript eine Lücke (Review-Befund B4).
                gespraech_id = _turn_speichern(nwz, user, body, q_suche, leer_text, [], [],
                                               debatten_rows=debatten_rows)
                yield _sse({"type": "done", "cited": [], "gespraech_id": gespraech_id})
                return
            # Task 32: Themengröße deterministisch — viele Treffer über eine
            # lange Zeitspanne (Stadion: 8 Jahre) heißt lange Historie, die
            # Antwort darf dann ausführlich gegliedert sein (GROSS_REGEL).
            daten = sorted(str(c.get("session_date") or "")[:4]
                           for c in candidates[:20] if c.get("session_date"))
            spanne = (int(daten[-1]) - int(daten[0])) if len(daten) >= 2 and daten[0].isdigit() else 0
            # Beim Vereinfachen NIE die Langfassungs-Regel: „umfangreiches Thema"
            # verlangt ~500 Wörter mit Zwischenüberschriften — das ist das
            # Gegenteil von dem, was der Knopf verspricht.
            gross = (len(candidates) >= 25 or spanne >= 3) and not einfach
            if typ == "sitzung":
                # Länge nach Sitzungsgröße statt Kandidatenzahl — die zählt
                # nach dem Voll-Merge der Sitzung immer hoch.
                gross = len(sitzung_ids) >= 12 and not einfach
            ctx = candidates[:QA_ANSWER_N]
            if vorher_ids:
                # Beim Vereinfachen sieht das Modell NUR die Beschlüsse, die die
                # vorige Antwort belegt haben. Das ist keine Sparmaßnahme,
                # sondern die Fußnoten-Garantie: Mit den übrigen 30 Kandidaten
                # im Kontext hängte das Modell im Test eine fremde Nummer an ein
                # Debatten-Zitat, das in der Ausgangsantwort bewusst ohne Beleg
                # stand. Was es nicht sieht, kann es nicht danebensetzen.
                ctx = [c for c in candidates if c["id"] in set(vorher_ids)][:QA_ANSWER_N]
            if partei_ids and not einfach:
                # Mindestens die besten Partei-Anträge in den Antwort-Kontext,
                # auch wenn sie im Relevanz-Ranking hinter Platz 20 liegen.
                fehlend = [c for c in candidates[QA_ANSWER_N:] if c["id"] in partei_ids][:6]
                if fehlend:
                    ctx = ctx[:QA_ANSWER_N - len(fehlend)] + fehlend
            if typ == "verlauf":
                ctx = qa.sort_verlauf(ctx)
            if typ == "sitzung" and sitzung_ids and not einfach:
                # ALLE Beschlüsse der Sitzung in den Antwort-Kontext — der
                # QA_ANSWER_N-Deckel würde große Sitzungen wieder anschneiden,
                # und genau das Anschneiden ist der Anlass dieses Fragetyps.
                im_set = set(sitzung_ids)
                ctx = [c for c in candidates if c["id"] in im_set][:QA_SITZUNG_N]
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
            # Worum es ging, steht in der kondensierten Fassung der Analyse.
            # Fällt die aus, ist q_suche der Knopftext selbst — dann trägt die
            # letzte echte Frage aus dem Verlauf das Thema.
            frage_thema = q_suche
            if einfach and frage_thema.strip() == q and verlauf:
                frage_thema = verlauf[-1].get("frage") or q
            strom = (qa.vereinfachen_stream(frage_thema, body.vorherige_antwort, ctx) if einfach
                     else qa.answer_stream(q, ctx, typ=typ, presse=presse_rows, verlauf=verlauf,
                                           haushalt=haushalt_zeilen, debatten=debatten_rows,
                                           gross=gross, steckbriefe=steckbriefe,
                                           duenn=(lage == "duenn"), eng=eng,
                                           sitzungen=sitzungen))
            try:
                for delta in strom:
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
            except Exception:  # noqa: BLE001 — Stream riss mitten in der Antwort
                # Vorher wurde der Fehler nur bei LEEREM Puffer repariert — ein
                # Abriss nach den ersten Sätzen ließ still einen Antwort-Torso
                # stehen (Tims „mitten im Wort zu Ende"-Befund 10.08.). Jetzt:
                # immer einmal komplett neu generieren; der Client ersetzt den
                # Torso per replace-Event. Scheitert auch das, wird der Turn
                # ehrlich als abgebrochen markiert.
                _log.warning("answer_stream brach nach %d Zeichen ab — one-shot Ersatz",
                             len(buf), exc_info=True)
                try:
                    ans, _ = (qa.vereinfachen_question(frage_thema, body.vorherige_antwort, ctx)
                              if einfach else
                              qa.answer_question(q, ctx, typ=typ, presse=presse_rows, verlauf=verlauf,
                                                 haushalt=haushalt_zeilen, debatten=debatten_rows,
                                                 gross=gross, steckbriefe=steckbriefe,
                                                 duenn=(lage == "duenn"), eng=eng,
                                                 sitzungen=sitzungen))
                    buf = ans
                    yield _sse({"type": "replace", "text": qa.split_followups(ans)[0]})
                    sent = len(ans)
                except Exception:  # noqa: BLE001
                    _log.exception("one-shot Ersatz scheiterte ebenfalls")
                    if not buf:
                        raise  # nichts gesendet → Netz-Fehlerpfad des Clients
                    yield _sse({"type": "abbruch"})
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
            gespraech_id = _turn_speichern(nwz, user, body, q_suche, answer_text,
                                           candidates, cited,
                                           presse_rows=presse_rows,
                                           debatten_rows=debatten_rows,
                                           planungen=planungen)
            yield _sse({"type": "done", "cited": cited, "timings": zeiten,
                        "gespraech_id": gespraech_id})
        except Exception:  # noqa: BLE001 — surface a terminal error to the client
            _log.exception("KI-Frage fehlgeschlagen")
            yield _sse({"type": "error", "message": "Frage fehlgeschlagen."})

    return StreamingResponse(
        gen(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
