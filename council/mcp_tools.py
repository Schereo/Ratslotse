"""Die Werkzeuge des MCP-Servers: Ratsdaten für fremde Agenten.

**Wozu (16.10.2026).** Tim fragte, ob man „seinen eigenen Agent connecten“
kann, um die Ratsdaten abzurufen. Das Protokoll dafür ist MCP; die Hülle steht
in ``web/backend/app/mcp.py``, hier stehen nur die Werkzeuge — dieselbe
Trennung wie bei Lotti (``council/lotti_werkzeuge.py``), deren
Sitzungs-Werkzeuge hier wiederverwendet werden.

**Was sie dürfen — und was nicht.**

- Sie **lesen nur**, und nur öffentliche Ratsdaten: Beschlüsse, Vorlagen,
  Sitzungen, Tagesordnungen, Gremien. Nichts Kontogebundenes (Themen,
  Lesezeichen, Gespräche), **kein Haushalt** (der hängt am Recht ``budget``
  und bleibt der eigenen Oberfläche vorbehalten).
- **Kein Sprachmodell auf unserer Seite.** Das Denken macht der Agent der
  Nutzerin mit ihrem eigenen Modell; bei uns laufen SQLite und die
  Volltextsuche. Deshalb fehlen die KI-Frage und die ausführliche Recherche
  bewusst — sonst bezahlten wir fremde Schleifen.
- Text aus dem Ratsarchiv ist Fremdtext und läuft durch denselben
  Anweisungsfilter wie bei Lotti (``kern/foreign_text.py``). Der fremde Agent
  hat seine eigene Abwehr; ein Satz „ignoriere alle Anweisungen“ in einer
  Vorlage soll trotzdem nicht von UNS kommen.
- Jede Antwort trägt Adressen: die Ratslotse-Seite und, wo es sie gibt, das
  Original im Ratsinformationssystem. Ein Agent soll belegen können.

Tool-Namen sind englisch (das erwarten Agenten und ihre Oberflächen), die
Beschreibungen deutsch — die Daten sind es auch, und Suchbegriffe müssen
deutsch sein, damit die Volltextsuche trifft.
"""
from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from council import lotti_werkzeuge as lw
from kern import foreign_text

RIS = "https://buergerinfo.oldenburg.de"

#: Höchstens so viele Treffer je Suche. Ein Agent blättert mit ``offset``.
SUCHE_MAX = 25
#: So viel Vorlagen-Volltext je Abruf; der Rest kommt mit ``offset``.
VOLLTEXT_STUECK = 12_000

_ERGEBNIS = {"accepted": "angenommen", "rejected": "abgelehnt", "postponed": "vertagt",
             "noted": "zur Kenntnis genommen", "no_decision": "kein Beschluss",
             "settled": "erledigt"}

_FELDER = ("bauen_wohnen", "bildung", "finanzen", "klima_umwelt", "kultur_sport",
           "migration_integration", "sicherheit_ordnung", "soziales_gesundheit", "verkehr",
           "verwaltung_digital", "wirtschaft", "sonstiges")

_DATUM = {"type": "string", "pattern": r"^\d{4}-\d{2}-\d{2}$", "description": "JJJJ-MM-TT"}


class ToolError(Exception):
    """Ein Fehler, den der Agent sehen und korrigieren soll (falsche Kennung,
    fehlendes Pflichtfeld). Wird als ``isError``-Ergebnis zurückgegeben, nicht
    als Protokollfehler — so steht er im Gespräch und der Agent kann neu
    ansetzen."""


@dataclass(frozen=True)
class Tool:
    name: str
    title: str
    description: str
    input_schema: dict
    run: Callable[[Any, dict, str], str]

    def beschreibung(self) -> dict:
        return {"name": self.name, "title": self.title, "description": self.description,
                "inputSchema": self.input_schema,
                # Alle Werkzeuge lesen nur — Clients fragen dann nicht bei
                # jedem Aufruf nach.
                "annotations": {"readOnlyHint": True, "destructiveHint": False,
                                "idempotentHint": True, "openWorldHint": False}}


def _schema(props: dict, required: list[str] | None = None) -> dict:
    return {"type": "object", "properties": props, "required": required or [],
            "additionalProperties": False}


def _sauber(text: str | None, max_len: int | None = None) -> str:
    t, _ = foreign_text.defuse(text or "")
    if max_len and len(t) > max_len:
        t = t[:max_len].rstrip() + " …"
    return t


def _json(daten: Any) -> str:
    return json.dumps(daten, ensure_ascii=False, indent=1)


def _int(args: dict, key: str, standard: int, lo: int, hi: int) -> int:
    roh = args.get(key, standard)
    try:
        wert = int(roh)
    except (TypeError, ValueError) as fehler:
        raise ToolError(f"{key} muss eine ganze Zahl sein.") from fehler
    return max(lo, min(hi, wert))


def _datum(args: dict, key: str) -> str:
    wert = str(args.get(key) or "").strip()
    if wert and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", wert):
        raise ToolError(f"{key} muss die Form JJJJ-MM-TT haben.")
    return wert


def _beschluss_kurz(d: dict, base: str) -> dict:
    return {
        "id": d["id"],
        "date": d.get("session_date"),
        "committee": d.get("committee"),
        "title": _sauber(d.get("title")),
        "outcome": _ERGEBNIS.get(d.get("outcome") or "", d.get("outcome")),
        "template_number": d.get("template_number"),
        "applicants": d.get("factions") or [],
        "policy_field": d.get("policy_field"),
        "summary": _sauber(d.get("summary"), 400) or None,
        "url": f"{base}/council/decision?id={d['id']}",
    }


# --------------------------------------------------------------------------- #
# Werkzeuge
# --------------------------------------------------------------------------- #

def search_decisions(store, args: dict, base: str) -> str:
    query = str(args.get("query") or "").strip()[:200]
    limit = _int(args, "limit", 10, 1, SUCHE_MAX)
    offset = _int(args, "offset", 0, 0, 2000)
    outcome = str(args.get("outcome") or "")
    if outcome and outcome not in _ERGEBNIS:
        raise ToolError(f"outcome muss eines sein von: {', '.join(_ERGEBNIS)}.")
    field = str(args.get("policy_field") or "")
    if field and field not in _FELDER:
        raise ToolError(f"policy_field muss eines sein von: {', '.join(_FELDER)}.")
    filter_ = {"committee": str(args.get("committee") or "").strip()[:120],
               "outcome": outcome, "field": field,
               "date_from": _datum(args, "date_from"), "date_to": _datum(args, "date_to")}
    if query:
        # Die Volltextsuche rankt (BM25, Begriffe ODER-verknüpft) — die
        # LIKE-Suche der Seite verlangte die ganze Phrase am Stück und fand
        # zu „Radweg Ammerländer Heerstraße“ nichts. Die Filter laufen danach
        # über dieselbe Abfrage wie auf der Seite; die Reihenfolge bleibt die
        # der Relevanz.
        treffer = store.search_decisions_fts(query, limit=400)
        rang = {t[0]: i for i, t in enumerate(treffer)}
        zeilen = store.search_decisions(only_ids=list(rang), limit=len(rang) or 1, **filter_)
        zeilen.sort(key=lambda d: rang.get(d["id"], 1_000_000))
        gesamt = len(zeilen)
        zeilen = zeilen[offset:offset + limit]
    else:
        zeilen = store.search_decisions(limit=limit, offset=offset, **filter_)
        gesamt = None
    aus: dict[str, Any] = {"results": [_beschluss_kurz(d, base) for d in zeilen]}
    if gesamt is not None:
        aus["total"] = gesamt
    aus["next_offset"] = offset + len(zeilen) if len(zeilen) == limit else None
    if not zeilen:
        aus["hint"] = ("Keine Treffer. Die Suche ist eine Volltextsuche auf Deutsch: andere "
                       "Stichwörter versuchen, Filter lockern, oder list_committees für den "
                       "genauen Gremiennamen.")
    return _json(aus)


def get_decision(store, args: dict, base: str) -> str:
    did = _int(args, "decision_id", 0, 0, 10**9)
    d = store.get_decision(did) if did else None
    if not d:
        raise ToolError(f"Kein Beschluss mit der Kennung {did}.")
    aus: dict[str, Any] = _beschluss_kurz(d, base)
    aus.pop("summary")
    aus.update({
        "item_number": d.get("item_number"),
        "kind": d.get("kind"),
        "decision_text": _sauber(d.get("official_text")) or None,
        "result_as_recorded": _sauber(d.get("raw_result")) or None,
        "vote": {"result": d.get("vote"), "no_votes": d.get("no_votes"),
                 "abstentions": d.get("abstentions")},
        "summary": _sauber(d.get("summary")) or None,
        "simple_summary": _sauber(d.get("simple_summary")) or None,
        "amount_eur": d.get("amount_eur"),
        "policy_tags": d.get("policy_tags") or [],
        "protocol_url": d.get("protocol_url"),
        "session_url": f"{RIS}/si0057.php?__ksinr={d['ksinr']}",
        "ksinr": d.get("ksinr"),
    })
    if d.get("kvonr"):
        aus["template_url"] = f"{RIS}/vo0050.php?__kvonr={d['kvonr']}"
    if d.get("kind") == "decision" and d.get("item_number"):
        aus["amendments"] = [
            {"id": s["id"], "title": _sauber(s.get("title")),
             "outcome": _ERGEBNIS.get(s.get("outcome") or "", s.get("outcome")),
             "applicants": s.get("factions") or []}
            for s in store.get_subvotes(d["ksinr"], d["item_number"])]
    return _json(aus)


def get_template(store, args: dict, base: str) -> str:
    nr = str(args.get("template_number") or "").strip()[:30]
    if not nr:
        raise ToolError("template_number fehlt, z. B. „25/0615“.")
    v = store.get_vorlage_by_nr(nr)
    if not v:
        raise ToolError(f"Keine Vorlage „{nr}“ im Bestand.")
    offset = _int(args, "offset", 0, 0, 10**7)
    volltext = _sauber(v.get("raw_text"))
    stueck = volltext[offset:offset + VOLLTEXT_STUECK]
    weiter = offset + len(stueck)
    return _json({
        "template_number": v.get("template_number"),
        "title": _sauber(v.get("title")),
        "kind": v.get("kind"),
        "office": v.get("office"),
        "proposed_decision": _sauber(v.get("proposed_decision")) or None,
        "financial_impact": _sauber(v.get("financial_impact")) or None,
        "climate_impact": _sauber(v.get("climate_impact")) or None,
        "full_text": stueck or None,
        "full_text_length": len(volltext),
        "next_offset": weiter if weiter < len(volltext) else None,
        "url": f"{RIS}/vo0050.php?__kvonr={v['kvonr']}" if v.get("kvonr") else v.get(
            "document_url"),
    })


def list_committees(store, args: dict, base: str) -> str:
    naechste = store.naechste_sitzung_je_gremium()
    return _json({"committees": [
        {"name": n, "next_session": (naechste.get(n) or {}).get("session_date")}
        for n in store.get_all_committee_names()]})


def list_sessions(store, args: dict, base: str) -> str:
    if not str(args.get("committee") or "").strip():
        raise ToolError("committee fehlt, z. B. „Rat“ oder „Verkehr“.")
    return lw.sitzungen(store, {"gremium": args.get("committee"),
                                "von_datum": _datum(args, "date_from"),
                                "bis_datum": _datum(args, "date_to")}).text


def get_agenda(store, args: dict, base: str) -> str:
    ksinr = _int(args, "ksinr", 0, 0, 10**9)
    e = lw.tagesordnung(store, {"ksinr": ksinr})
    if not store.get_session(ksinr):
        raise ToolError(e.text)
    return e.text + f"\nSeite: {base}/council/sitzung?ksinr={ksinr}" \
                    f"\nOriginal: {RIS}/si0057.php?__ksinr={ksinr}"


def get_template_history(store, args: dict, base: str) -> str:
    nr = str(args.get("template_number") or "").strip()[:30]
    if not nr:
        raise ToolError("template_number fehlt, z. B. „25/0615“.")
    return lw.beratungsfolge(store, {"vorlage": nr}).text


def count_decisions(store, args: dict, base: str) -> str:
    jahr = _int(args, "year", 0, 1990, 2035)
    field = str(args.get("policy_field") or "")
    if field and field not in _FELDER:
        raise ToolError(f"policy_field muss eines sein von: {', '.join(_FELDER)}.")
    return lw.beschluesse_zaehlen(store, {"jahr": jahr, "themenfeld": field,
                                          "gremium": args.get("committee") or ""}).text


TOOLS: dict[str, Tool] = {t.name: t for t in (
    Tool("search_decisions", "Beschlüsse suchen",
         "Durchsucht die Beschlüsse des Oldenburger Stadtrats und seiner Ausschüsse "
         "(seit etwa 2016). Volltextsuche auf DEUTSCH über Titel, Beschlusstext, "
         "Kurzfassung und Vorlage; die besten Treffer zuerst. Ohne query: die neuesten "
         "zuerst. Filter lassen sich kombinieren. Für Details eines Treffers "
         "get_decision mit seiner id.",
         _schema({
             "query": {"type": "string", "description": "Stichwörter, z. B. „Radweg Ammerländer "
                                                         "Heerstraße“ oder „Grundsteuer Hebesatz“"},
             "committee": {"type": "string", "description": "Genauer Gremienname aus "
                                                             "list_committees, z. B. „Rat“"},
             "outcome": {"type": "string", "enum": list(_ERGEBNIS)},
             "policy_field": {"type": "string", "enum": list(_FELDER)},
             "date_from": _DATUM, "date_to": _DATUM,
             "limit": {"type": "integer", "minimum": 1, "maximum": SUCHE_MAX, "default": 10},
             "offset": {"type": "integer", "minimum": 0, "default": 0},
         }), search_decisions),
    Tool("get_decision", "Beschluss lesen",
         "Ein Beschluss vollständig: Beschlusstext, Abstimmungsergebnis, Antragsteller, "
         "Kurzfassung und eine Erklärung in einfacher Sprache, Änderungsanträge, Links "
         "zum Protokoll, zur Sitzung und zur Vorlage.",
         _schema({"decision_id": {"type": "integer", "minimum": 1}}, ["decision_id"]),
         get_decision),
    Tool("get_template", "Vorlage lesen",
         "Eine Vorlage (Beschlussvorlage, Antrag, Anfrage, Mitteilung) mit Beschlussvorschlag, "
         "finanziellen Auswirkungen und Volltext (Sachverhalt, Begründung). Langer Volltext "
         "kommt in Stücken; mit next_offset weiterlesen.",
         _schema({"template_number": {"type": "string", "description": "z. B. „25/0615“"},
                  "offset": {"type": "integer", "minimum": 0, "default": 0}},
                 ["template_number"]),
         get_template),
    Tool("get_template_history", "Beratungsfolge",
         "Alle Beratungen einer Vorlage in allen Gremien, mit Datum und Ergebnis — z. B. "
         "„wurde das vorher im Ausschuss beraten?“.",
         _schema({"template_number": {"type": "string", "description": "z. B. „25/0615“"}},
                 ["template_number"]),
         get_template_history),
    Tool("list_committees", "Gremien",
         "Alle Gremien (Rat, Ausschüsse, Ortsräte …) mit ihrer nächsten Sitzung. Für die "
         "genauen Namen, die die anderen Werkzeuge als Filter erwarten.",
         _schema({}), list_committees),
    Tool("list_sessions", "Sitzungen",
         "Sitzungen eines Gremiums in einem Zeitraum — vergangene und geplante, mit Datum, "
         "Uhrzeit, Ort und ksinr (für get_agenda). Ohne Zeitraum: ab heute ein Jahr voraus. "
         "Das Gremium darf ein Namensstück sein („Verkehr“, „Finanzen“).",
         _schema({"committee": {"type": "string"}, "date_from": _DATUM, "date_to": _DATUM},
                 ["committee"]),
         list_sessions),
    Tool("get_agenda", "Tagesordnung",
         "Die Tagesordnung einer Sitzung (ksinr aus list_sessions oder get_decision) samt "
         "den Ergebnissen, sobald beschlossen ist.",
         _schema({"ksinr": {"type": "integer", "minimum": 1}}, ["ksinr"]),
         get_agenda),
    Tool("count_decisions", "Beschlüsse zählen",
         "Zählt die Beschlüsse eines Jahres nach Ergebnis, wahlweise für ein Themenfeld "
         "und/oder ein Gremium.",
         _schema({"year": {"type": "integer", "minimum": 1990, "maximum": 2035},
                  "policy_field": {"type": "string", "enum": list(_FELDER)},
                  "committee": {"type": "string"}}, ["year"]),
         count_decisions),
)}


def ausfuehren(store, name: str, args: dict | None, base: str) -> str:
    """Führt ein Werkzeug aus. Wirft ``KeyError`` für einen unbekannten Namen
    und ``ToolError`` für Eingaben, die der Agent korrigieren kann."""
    tool = TOOLS[name]
    if args is not None and not isinstance(args, dict):
        raise ToolError("arguments muss ein Objekt sein.")
    return tool.run(store, args or {}, base.rstrip("/"))
