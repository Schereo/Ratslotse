"""Was die Vorlage eines Tagesordnungspunkts schon trägt — ohne Modell.

Stufe 0 aus ``docs/plan-vorlagen-aufbereiten.md`` (PR 4): amtlicher
Beschlussvorschlag, Kostenangabe mit Status, Klima-Check, federführendes Amt
und die Anträge mit Antragsteller. Alles steht seit der Ernte in
``council_templates`` und ``council_attachments`` — gezeigt wurde es bis
11/2026 nur auf der Beschluss-Seite, also erst nach dem Protokoll.

Amtlicher Wortlaut bleibt Wortlaut: Die Seite zeigt ihn als Zitat, nicht als
erzeugten Text, und deshalb ohne KI-Stern.
"""
from __future__ import annotations

import re
from typing import Literal, TypedDict

from council import ernte
from council.vorlagen import ist_antrag

RIS = "https://buergerinfo.oldenburg.de"

# Ein Betrag in der Kostenangabe: „20.000 Euro", „1,2 Mio. €", „350.000 EUR".
_BETRAG_RE = re.compile(r"\d[\d.]*(?:,\d+)?\s*(?:€|Euro|EUR|Mio\.?|Millionen|T€|Tsd\.?)", re.IGNORECASE)
# „Keine", „Es entstehen keine Kosten", „Keine finanziellen Auswirkungen."
_KEINE_RE = re.compile(r"^(?:es\s+entstehen\s+)?keine\b|^entfällt|^nein\b", re.IGNORECASE)


class Cost(TypedDict):
    text: str
    #: ``amount``: die Vorlage nennt einen Betrag; ``none``: laut Vorlage keine
    #: Kosten; ``text``: eine Angabe ohne Betrag (z. B. „im Rahmen des Budgets").
    status: Literal["amount", "none", "text"]


class Climate(TypedDict):
    text: str
    relevant: bool | None


class Motion(TypedDict):
    label: str
    applicants: list[str]
    url: str | None


class TemplateFields(TypedDict):
    template_number: str | None
    document_url: str | None
    office: str | None
    proposed_decision: str | None
    cost: Cost | None
    climate: Climate | None
    motions: list[Motion]


def cost_status(text: str | None) -> Literal["amount", "none", "text"] | None:
    t = (text or "").strip()
    if not t:
        return None
    if _BETRAG_RE.search(t):
        return "amount"
    if _KEINE_RE.search(t):
        return "none"
    return "text"


def build(vorlage: dict | None, vorlage_anlagen: list[dict], punkt_anlagen: list[dict]) -> TemplateFields | None:
    """``None`` ohne Vorlage und ohne Antrag — dann gibt es nichts zu zeigen."""
    antraege: list[Motion] = []
    gesehen: set[str] = set()
    for a in vorlage_anlagen:
        if not a.get("is_motion"):
            continue
        schluessel = a.get("url") or a.get("label") or ""
        gesehen.add(schluessel)
        antraege.append({"label": a.get("label") or "Antrag", "applicants": list(a.get("applicants") or []),
                         "url": a.get("url")})
    for a in punkt_anlagen:
        schluessel = a.get("url") or a.get("label") or ""
        if schluessel in gesehen or not ist_antrag(a.get("label"), a.get("raw_text")):
            continue
        gesehen.add(schluessel)
        from council.parties import parties_in_text  # noqa: PLC0415
        antraege.append({"label": a.get("label") or "Antrag",
                         "applicants": parties_in_text(a.get("label")) or parties_in_text((a.get("raw_text") or "")[:4000]),
                         "url": a.get("url")})
    if not vorlage and not antraege:
        return None
    v = vorlage or {}
    fin = (v.get("financial_impact") or "").strip() or None
    kli = (v.get("climate_impact") or "").strip() or None
    status = cost_status(fin)
    return {
        "template_number": v.get("template_number"),
        "document_url": v.get("document_url"),
        "office": v.get("office"),
        "proposed_decision": v.get("proposed_decision"),
        "cost": {"text": fin, "status": status} if fin and status else None,
        "climate": {"text": kli, "relevant": ernte.klima_relevant(kli)} if kli else None,
        "motions": antraege,
    }
