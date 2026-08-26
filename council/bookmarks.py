"""Persönliche Merkliste über den beiden getrennten Ratslotse-Datenbanken.

Die Eigentümerschaft lebt in ``nwz.sqlite``; Sitzungen, TOPs und Beschlüsse
liegen in ``council.sqlite``. Dieses Modul löst die gespeicherten Snapshots
gegen den aktuellen Ratsbestand auf. Besonders wichtig ist der Fallback über
Vorlage und Titel: TOP-Nummern können sich bis zur Sitzung verschieben.
"""
from __future__ import annotations

import re
from datetime import date


def top_number(value: str | None) -> str:
    m = re.search(r"\d+(?:\.\d+)*", str(value or ""))
    return m.group(0) if m else ""


def normalized_title(value: str | None) -> str:
    text = " ".join(str(value or "").split()).lower().replace("ß", "ss")
    # Die Tagesordnungsseite hängt den später nachgetragenen Status teilweise
    # an den Titel ("Beschluss: geändert beschlossen"). Er ist keine Identität.
    text = re.split(r"\s+beschluss:\s*", text, maxsplit=1)[0]
    text = re.sub(r"\s*[-–]\s*(bericht|beschluss|antrag|sachstand)\s*$", "", text)
    return re.sub(r"[^0-9a-zäöü]+", " ", text).strip()


def _same_title(a: str | None, b: str | None) -> bool:
    na, nb = normalized_title(a), normalized_title(b)
    if not na or not nb:
        return False
    return na == nb or (min(len(na), len(nb)) >= 24 and (na in nb or nb in na))


def _same_vorlage(a: str | None, b: str | None) -> bool:
    aa, bb = str(a or "").strip(), str(b or "").strip()
    if not aa or not bb:
        return False
    return aa == bb or aa.startswith(bb + "/") or bb.startswith(aa + "/")


def _find_agenda_item(bookmark: dict, items: list[dict]) -> dict | None:
    kvonr = bookmark.get("kvonr")
    if kvonr:
        found = next((i for i in items if i.get("kvonr") == kvonr), None)
        if found:
            return found
    found = next((i for i in items if _same_vorlage(i.get("vorlage_nr"),
                                                    bookmark.get("vorlage_nr"))), None)
    if found:
        return found
    found = next((i for i in items if _same_title(i.get("title"), bookmark.get("title"))), None)
    if found:
        return found
    nr = top_number(bookmark.get("item_number"))
    return next((i for i in items if top_number(i.get("item_number")) == nr), None) if nr else None


def _find_decision(bookmark: dict, decisions: list[dict], item: dict | None = None) -> dict | None:
    rows = [d for d in decisions if d.get("kind") != "subvote"]
    wanted = item or bookmark
    kvonr = wanted.get("kvonr") or bookmark.get("kvonr")
    if kvonr:
        found = next((d for d in rows if d.get("kvonr") == kvonr), None)
        if found:
            return found
    vorlage = wanted.get("vorlage_nr") or bookmark.get("vorlage_nr")
    found = next((d for d in rows if _same_vorlage(d.get("vorlage_nr"), vorlage)), None)
    if found:
        return found
    nr = top_number(wanted.get("item_number"))
    found = next((d for d in rows if nr and top_number(d.get("item_number")) == nr), None)
    if found:
        return found
    title = wanted.get("title") or bookmark.get("title")
    return next((d for d in rows if _same_title(d.get("title"), title)), None)


def resolve_bookmark(bookmark: dict, council) -> dict:
    """Snapshot gegen den aktuellen Ratsbestand auflösen.

    Rückgabe enthält immer ``bookmark`` sowie, soweit vorhanden, ``session``,
    ``agenda_item`` und ``decision``.
    """
    kind = bookmark.get("kind")
    ksinr = bookmark.get("ksinr")
    session = council.get_session(int(ksinr)) if ksinr else None
    item = None
    decision = None

    if kind == "session":
        pass
    elif kind == "agenda_item" and ksinr:
        item = _find_agenda_item(bookmark, council.agenda_items(int(ksinr)))
        decision = _find_decision(bookmark, council.get_decisions(int(ksinr)), item)
    elif kind == "decision":
        if bookmark.get("decision_id"):
            decision = council.get_decision(int(bookmark["decision_id"]))
        if decision is None and ksinr:
            decision = _find_decision(bookmark, council.get_decisions(int(ksinr)))

    return {"bookmark": bookmark, "session": session,
            "agenda_item": item, "decision": decision}


def bookmark_url(resolved: dict) -> str:
    b, d, item = (resolved["bookmark"], resolved.get("decision"),
                  resolved.get("agenda_item"))
    if d:
        return f"/council/decision?id={d['id']}"
    if b.get("ksinr"):
        url = f"/council?tab=sessions&ksinr={b['ksinr']}"
        top = (item or b).get("item_number")
        if top:
            from urllib.parse import quote
            url += "&top=" + quote(str(top))
        return url
    return "/bookmarks"


def serialize_bookmark(resolved: dict) -> dict:
    b = resolved["bookmark"]
    session = resolved.get("session")
    item = resolved.get("agenda_item")
    decision = resolved.get("decision")
    kind = b["kind"]

    if kind == "session":
        title = (session or {}).get("committee") or b.get("title") or "Sitzung"
        state = "upcoming" if session and session.get("session_date", "") >= date.today().isoformat() else "saved"
    elif kind == "agenda_item":
        title = (item or {}).get("title") or (decision or {}).get("title") or b.get("title") or "Tagesordnungspunkt"
        if decision:
            state = "decided"
        elif b.get("ksinr") and getattr(resolved.get("council"), "has_protocol", lambda _k: False)(b["ksinr"]):
            state = "protocol"
        elif session and session.get("session_date", "") >= date.today().isoformat():
            state = "upcoming"
        else:
            state = "waiting"
    else:
        title = (decision or {}).get("title") or b.get("title") or "Beschluss"
        state = "decided" if decision else "unavailable"

    return {
        "id": b["id"], "kind": kind, "target_key": b["target_key"],
        "title": title, "subtitle": b.get("subtitle") or "",
        "created_at": b["created_at"], "notify_result": bool(b.get("notify_result")),
        "result_notified_at": b.get("result_notified_at"), "state": state,
        "url": bookmark_url(resolved), "ksinr": b.get("ksinr"),
        "item_number": (item or {}).get("item_number") or b.get("item_number"),
        "session": session, "agenda_item": item, "decision": decision,
    }


def enrich_bookmark(bookmark: dict, council) -> dict:
    resolved = resolve_bookmark(bookmark, council)
    resolved["council"] = council
    return serialize_bookmark(resolved)
