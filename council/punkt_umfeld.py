"""Das Umfeld eines Tagesordnungspunkts: wo es ist, was ähnlich schon
beschlossen wurde, wo man es im Video sieht, ob gerade eine Beteiligung läuft.

Tim, 13.11.2026, zu den Vorschlägen für die Punkt-Seite: Ort und Karte „sehr
sinnvoll“, Sprung ins Video „natürlich nur Ratssitzungen“, ähnliche frühere
Beschlüsse „finde ich auch gut“, Beteiligungsfristen „wenn es die gibt“.

Alles aus Daten, die es schon gibt — ohne Modell:

- **Orte**: die belegten Orte der Beschlüsse zu DIESER Vorlage (ihr Weg durch
  die Gremien, ``council_decision_locations``). Für einen Punkt, zu dem es
  noch keinen Beschluss gibt, ein Straßenname aus dem Titel — nur ganze
  Namen mit Straßen-Endung, damit „Markt“ nicht jede Marktgebühr verortet.
- **Ähnliche Beschlüsse**: die vorberechneten Nachbarn eines Beschlusses zu
  dieser Vorlage (``council_similar``), nur frühere.
- **Video**: die Fundstelle aus ``council_video_results`` — die gibt es nur
  für Ratssitzungen, andere Gremien werden nicht übertragen.
- **Beteiligung**: dieselbe Zuordnung über die Plan-Nummer im Titel wie auf
  der Beschluss-Seite.
"""
from __future__ import annotations

import re

MAX_ORTE = 3
MAX_AEHNLICHE = 3
#: Kosinus-Ähnlichkeit, ab der ein Nachbar als ähnlich gilt. Gemessen an 271
#: Paaren (13.11.2026, ein Modell urteilte „gehört der Beschluss in die
#: Liste?"): unter 0,80 passen rund 40 %, 0,80–0,90 drei Viertel, ab 0,90 alle.
#: Ab 0,85 passen gut 95 % — dafür bekommt nur etwa jede fünfte Vorlage eine
#: Liste. Lieber seltener als daneben.
MIN_AEHNLICHKEIT = 0.85
#: Unter dieser Sicherheit ist ein Ort eine Vermutung der Zuordnung, kein Beleg.
MIN_ORT_SICHERHEIT = 0.6
_BUCHSTABE = r"[^\W\d_]"
_STRASSE_ENDUNG = re.compile(r"(?:stra(?:ß|ss)e|weg|platz|allee|ring|damm|chaussee|ufer|gang|kamp|esch|wall|markt)$",
                             re.IGNORECASE)


def _nummer(item_number: str | None) -> str:
    return re.sub(r"^\D+", "", item_number or "").strip()


def _anker(punkt: dict) -> list[int]:
    """Die Beschlüsse zu dieser Vorlage, der eigene zuerst, dann die jüngsten Stationen."""
    ids = [punkt.get("decision_id")]
    ids += [s.get("decision_id") for s in reversed(punkt.get("history") or [])]
    return list(dict.fromkeys(i for i in ids if i))


def _ort(zeile: dict, source: str) -> dict:
    return {"slug": zeile["slug"], "name": zeile["name"], "kind": zeile.get("kind") or "other",
            "lat": zeile["lat"], "lon": zeile["lon"], "district": zeile.get("district") or None, "source": source}


def _strassen_im_titel(store, titel: str) -> list[dict]:
    klein = titel.lower()
    treffer = []
    for s in store.street_locations():
        name = s["name"]
        if len(name) < 7 or not _STRASSE_ENDUNG.search(name) or name.lower() not in klein:
            continue
        if re.search(rf"(?<!{_BUCHSTABE}){re.escape(name)}(?!{_BUCHSTABE})", titel, re.IGNORECASE):
            treffer.append(s)
    # Der längste Name gewinnt: „Alter Postweg" vor „Postweg".
    treffer.sort(key=lambda s: -len(s["name"]))
    aus: list[dict] = []
    for s in treffer:
        if not any(s["name"].lower() in a["name"].lower() for a in aus):
            aus.append(s)
    return aus


def places(store, punkt: dict) -> list[dict]:
    aus: list[dict] = []
    gesehen: set[str] = set()
    for decision_id in _anker(punkt):
        for z in store.decision_locations(decision_id):
            if z["lat"] is None or z["lon"] is None or z["slug"] in gesehen or (z.get("confidence") or 0) < MIN_ORT_SICHERHEIT:
                continue
            gesehen.add(z["slug"])
            aus.append(_ort(z, "decision"))
    if not aus:
        for z in _strassen_im_titel(store, (punkt.get("item") or {}).get("title") or ""):
            if z["slug"] not in gesehen:
                gesehen.add(z["slug"])
                aus.append(_ort(z, "title"))
    return aus[:MAX_ORTE]


def _titel_kern(titel: str | None) -> str:
    """Der Titel ohne Anhängsel („- Beschluss“, Datum eines Workshops) — zwei
    Beschlüsse mit demselben Kern sind für die Liste derselbe."""
    t = re.sub(r"\s+[-–—]\s+(?:Beschluss|Bericht|mündlicher Bericht|Beschlussantrag|Berichtsantrag)\b.*$", "", titel or "",
               flags=re.IGNORECASE)
    return re.sub(r"\d{1,2}\.\d{1,2}\.\d{2,4}|\s+", " ", t).strip().lower()


def similar(store, punkt: dict) -> list[dict]:
    """Frühere Beschlüsse zu einem ähnlichen Gegenstand — nicht die Stationen
    dieser Vorlage selbst (die stehen in der Vorgeschichte).

    Die Nachbarn sind vorberechnet (``council_similar``) und messen Ähnlichkeit
    des Wortlauts, nicht der Sache. Drei Filter, jeder aus der Stichprobe vom
    13.11.2026: (1) eine Mindestähnlichkeit (``MIN_AEHNLICHKEIT``) — darunter
    standen neben der „Drogenhilfestrategie“ die Stadttauben; (2) dasselbe
    Themenfeld; (3) bei
    Bebauungsplänen nur DERSELBE Plan — sonst sind die Nachbarn fremde Pläne
    im selben Verfahrensschritt („Beschluss zur Veröffentlichung“, 0,94)."""
    from council import beteiligung  # noqa: PLC0415

    datum = punkt.get("session_date") or ""
    eigene = set(_anker(punkt))
    plaene = set(beteiligung.plan_nummern((punkt.get("item") or {}).get("title") or ""))
    for decision_id in _anker(punkt):
        feld = (store.get_decision(decision_id) or {}).get("policy_field")
        aus: list[dict] = []
        kerne: set[str] = set()
        for n in store.get_similar(decision_id, limit=MAX_AEHNLICHE * 3):
            if n["id"] in eigene or (n.get("session_date") or "") > datum or n["score"] < MIN_AEHNLICHKEIT:
                continue
            if feld and n.get("policy_field") and n["policy_field"] != feld:
                continue
            fremde = set(beteiligung.plan_nummern(n.get("title") or ""))
            if (plaene or fremde) and not (plaene & fremde):
                continue
            kern = _titel_kern(n.get("title"))
            if kern in kerne:
                continue
            kerne.add(kern)
            aus.append({"id": n["id"], "title": n["title"], "outcome": n.get("outcome"),
                        "session_date": n.get("session_date"), "committee": n.get("committee") or "",
                        "summary": n.get("summary")})
            if len(aus) >= MAX_AEHNLICHE:
                break
        if aus:
            return aus
    return []


def video(store, punkt: dict) -> dict | None:
    if punkt.get("committee") != "Rat":
        return None
    nr = _nummer((punkt.get("item") or {}).get("item_number"))
    for r in store.get_video_results(punkt["ksinr"]):
        if _nummer(r["item_number"]) == nr and r.get("video_id"):
            return {"video_id": r["video_id"], "seconds": r.get("video_seconds")}
    return None


def participation(store, punkt: dict) -> dict | None:
    from council import beteiligung  # noqa: PLC0415

    titel = (punkt.get("item") or {}).get("title") or ""
    for b in store.list_beteiligungen(nur_laufende=False):
        if beteiligung.passt_zu_titel(b["plan_nrs"], titel):
            return {"title": b["title"], "step": b["schritt"], "valid_from": b["valid_from"],
                    "valid_until": b["valid_until"], "url": b["url"], "status": b.get("status") or "laufend",
                    "ended_at": b.get("beendet_am")}
    return None


def item_surroundings(store, punkt: dict) -> dict | None:
    aus = {"places": places(store, punkt), "similar": similar(store, punkt),
           "video": video(store, punkt), "participation": participation(store, punkt)}
    return aus if any(aus.values()) else None
