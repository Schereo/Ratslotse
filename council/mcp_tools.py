"""Die Werkzeuge des MCP-Servers: Ratsdaten für fremde Agenten.

**Wozu (16.10.2026).** Tim fragte, ob man „seinen eigenen Agent connecten“
kann, um die Ratsdaten abzurufen. Das Protokoll dafür ist MCP; die Hülle steht
in ``web/backend/app/mcp.py``, hier stehen nur die Werkzeuge — dieselbe
Trennung wie bei Lotti (``council/lotti_werkzeuge.py``), deren
Sitzungs-Werkzeuge hier wiederverwendet werden.

**Was sie dürfen — und was nicht.**

- Sie **lesen nur**, und nur öffentliche Ratsdaten: Beschlüsse, Vorlagen,
  Sitzungen, Tagesordnungen, Gremien. Nichts Kontogebundenes (Themen,
  Lesezeichen, Gespräche). **Den Haushalt nur mit dem Recht ``budget``**
  (seit 21.10.2026, s. ``Tool.recht``): Konten ohne das Recht sehen die
  Haushaltswerkzeuge gar nicht.
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
import logging
import re
import threading
import time
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from council import anlagentext
from council import lotti_werkzeuge as lw
from council import vorlagen
from council.haushaltsdebatte import saeubern, top_abschnitt
from council.kontaktdaten import maskieren
from kern import foreign_text

logger = logging.getLogger("council.mcp_tools")

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
    #: Greift das Werkzeug über unseren Bestand hinaus (lädt ein PDF aus dem
    #: Ratsinformationssystem)? Das sagt der Client der Nutzerin.
    open_world: bool = False
    #: Das Recht, das ein Konto für dieses Werkzeug braucht (``kern/roles.py``).
    #: ``None`` = jedes Konto mit MCP-Zugang. Ohne das Recht steht das Werkzeug
    #: gar nicht erst in ``tools/list``.
    recht: str | None = None

    def beschreibung(self) -> dict:
        return {"name": self.name, "title": self.title, "description": self.description,
                "inputSchema": self.input_schema,
                # Alle Werkzeuge lesen nur — Clients fragen dann nicht bei
                # jedem Aufruf nach. Dass ``get_attachment`` dabei einen Text
                # in unseren Bestand nachträgt, ändert für den Agenten nichts.
                "annotations": {"readOnlyHint": True, "destructiveHint": False,
                                "idempotentHint": True, "openWorldHint": self.open_world}}


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


#: Eine Zeile aus Buchstaben mit Leerzeichen dazwischen — so setzt das
#: PDF-Textlayer die gesperrte Unterschrift („D r . S v e n U h r h a n“).
_GESPERRT = re.compile(r"^(?:\S{1,2}\s+){4,}\S{1,2}$")


def _entsperren(zeile: str) -> str:
    """„D r .  S v e n  U h r h a n“ → „Dr. Sven Uhrhan“. Die Sperrung ist je
    Vorlage verschieden breit (ein, zwei, drei Leerzeichen je Buchstabe): Die
    HÄUFIGSTE Lücke der Zeile trennt Buchstaben, jede breitere Wörter — nicht
    die schmalste, denn einzelne Paare stehen enger („G  a  b  r  i  e  l e“).
    Sind alle gleich breit, trennt der Wechsel von klein zu groß."""
    einzeln = [t for t in zeile.split() if len(t) == 1]
    # Mehrheitlich Buchstaben: Tabellenzeilen („7 4 % 7 6 % …“) sind auch
    # gesperrt gesetzt, zusammengeschoben aber unlesbarer als vorher.
    if (not _GESPERRT.match(zeile) or len(einzeln) < 4
            or sum(t.isalpha() for t in einzeln) < 0.75 * len(einzeln)):
        return zeile
    luecke = Counter(len(x) for x in re.findall(r"\s+", zeile)).most_common(1)[0][0]
    woerter = [re.sub(r"(?<=[a-zäöüß])(?=[A-ZÄÖÜ])", " ", re.sub(r"\s+", "", t))
               for t in re.split(rf"\s{{{luecke + 1},}}", zeile)]
    return re.sub(r"\s*\.(?=\S)", ". ", " ".join(woerter))


#: Kopf- und Fußzeilen, die der Textlayer an jeder Seitengrenze einstreut —
#: Oldenburger Protokolle „Seite: 10/34“ (auch „S eite“, s.
#: ``haushaltsdebatte._SEITE``), Vorlagen „Ausdruck vom: …“ samt Seitenzahl.
_SEITENZEILE = re.compile(
    r"^[ \t]*(?:S[ \t]?eite:?[ \t]*\d+[ \t]*/[ \t]*\d+|Ausdruck vom:.*)[ \t]*$")
#: Woran ein Absatz wirklich endet. Steht davor etwas anderes, lief der Satz
#: über die Seite weiter.
_SATZENDE = re.compile(r"[.!?:;“”\"»«)]\s*$")


def _seitenwechsel_heilen(roh: str) -> str:
    """Kopf- und Fußzeilen raus — und den Absatz, den sie zerrissen haben,
    wieder zusammensetzen.

    Gemessen am Stadion-Protokoll (17.10.2026): „Zwischenzeitlich habe der
    VfB“ / ``Seite: 10/34`` / Leerzeile / „den Aufstieg in die 3. Liga …“.
    Die Fußzeile stand zwischen Leerzeilen; strich man sie, blieb eine
    Leerzeile, und die gilt jedem Absatzschnitt als Absatzende. Ein Agent las
    dann zwei Absätze, deren erster mitten im Satz aufhört.

    Die Regel: Über eine Seitengrenze hinweg wird verbunden, wenn die Zeile
    davor nicht mit einem Satzzeichen endet ODER die Zeile danach klein
    beginnt. Sonst bleibt der Absatzwechsel stehen — ein Absatz kann ja
    wirklich am Seitenende aufhören. Verbunden wird mit EINEM Zeilenumbruch,
    damit die Silbentrennung dahinter (``saeubern``, ``_entzeilen``) auch über
    die Seite greift („Auszah-“ / „lung“)."""
    zeilen = (roh or "").split("\n")
    aus: list[str] = []
    i = 0
    while i < len(zeilen):
        if not _SEITENZEILE.match(zeilen[i]):
            aus.append(zeilen[i])
            i += 1
            continue
        # Die Seitengrenze samt aller Leer- und Kopfzeilen drumherum.
        while aus and not aus[-1].strip():
            aus.pop()
        while i < len(zeilen) and (not zeilen[i].strip() or _SEITENZEILE.match(zeilen[i])):
            i += 1
        davor = aus[-1] if aus else ""
        danach = zeilen[i].lstrip() if i < len(zeilen) else ""
        weiter = bool(davor) and bool(danach) and (
            not _SATZENDE.search(davor) or danach[:1].islower())
        if aus and danach and not weiter:
            aus.append("")
    return "\n".join(aus)


def _volltext(roh: str | None) -> str:
    """Der Vorlagen-Volltext ohne die Spuren des PDF-Textlayers: keine
    Seitenköpfe („Ausdruck vom … Seite 1/2“), Zeilen innerhalb eines Absatzes
    zu Fließtext verbunden, Silbentrennung geheilt, gesperrte Unterschrift
    lesbar. Anders als ``vorlagen.excerpt`` bleibt ALLES stehen — Kopf,
    Unterschrift und angehängte Anlagen —, denn ein Agent soll den ganzen
    Text lesen können, nicht unseren Auszug davon."""
    absaetze = []
    for block in re.split(r"\n\s*\n", _seitenwechsel_heilen(roh or "")):
        zeilen = [_entsperren(z.strip()) for z in block.splitlines()]
        zeilen = [z for z in zeilen if z and not vorlagen._NOISE_RE.match(z)]  # noqa: SLF001
        if zeilen:
            absaetze.append("\n".join(vorlagen._entzeilen(zeilen)))  # noqa: SLF001
    return re.sub(r"[ \t]+", " ", "\n\n".join(absaetze)).strip()


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
    volltext = _sauber(_volltext(v.get("raw_text")))
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
        "attachments": _anlagen(store, v.get("kvonr")),
    })


#: Was ``text`` an einer Anlage heißt — der Agent entscheidet daran, ob sich
#: ``get_attachment`` lohnt.
_ANLAGE_TEXT = {"ok": "available", "empty": "scan", "failed": "failed"}


def _anlagen(store, kvonr: int | None) -> list[dict]:
    if not kvonr:
        return []
    return [{"attachment_id": r[0], "label": _sauber(r[1]), "pages": r[2],
             # Alles außer ok/empty/failed (``listed``) ist noch nicht
             # geladen — get_attachment holt es beim ersten Abruf.
             "text": _ANLAGE_TEXT.get(r[3] or "", "on_demand") if r[6] or r[3] != "ok"
             else "on_demand",
             "is_motion": bool(r[4]), "url": r[5]}
            for r in store._conn.execute(  # noqa: SLF001
                "SELECT document_id, label, n_pages, status, is_motion, url, "
                "raw_text IS NOT NULL AND raw_text != '' "
                "FROM council_attachments WHERE kvonr = ? ORDER BY is_motion DESC, label",
                (kvonr,))]


# --------------------------------------------------------------------------- #
# Anlagen auf Zuruf
# --------------------------------------------------------------------------- #

#: Mindestabstand zwischen zwei Downloads aus dem Ratsinformationssystem —
#: über ALLE Agenten, nicht je Schlüssel. Dieselbe Höflichkeit wie bei
#: fremden Systemen (min. 1 s); hier ist es das Haus, aus dem alle Daten
#: kommen, und eine Sperre träfe den ganzen Ingest.
LADE_ABSTAND_S = 1.0
#: Höchstens so viele Downloads je Stunde, wieder über alle. Danach bleibt
#: der Bestand lesbar, nur Neues wartet. Ein Agent, der eine Vorlage
#: durcharbeitet, braucht eine Handvoll; 120 hält auch mehrere davon aus.
LADE_JE_STUNDE = 120

_lade_sperre = threading.Lock()
_lade_zeiten: list[float] = []


def _laden_erlaubt() -> None:
    """Wartet den Mindestabstand ab und zählt den Download — oder wirft, wenn
    das Stundenkontingent aufgebraucht ist."""
    with _lade_sperre:
        jetzt = time.monotonic()
        while _lade_zeiten and jetzt - _lade_zeiten[0] > 3600:
            _lade_zeiten.pop(0)
        if len(_lade_zeiten) >= LADE_JE_STUNDE:
            raise ToolError("Gerade werden zu viele Anlagen nachgeladen. Bereits geladene "
                            "Anlagen sind weiter lesbar; diese bitte später erneut versuchen "
                            "oder direkt unter url öffnen.")
        if _lade_zeiten and jetzt - _lade_zeiten[-1] < LADE_ABSTAND_S:
            time.sleep(LADE_ABSTAND_S - (jetzt - _lade_zeiten[-1]))
        _lade_zeiten.append(time.monotonic())


def lade_kontingent_vergessen() -> None:
    """Für Tests."""
    with _lade_sperre:
        _lade_zeiten.clear()


_DOKUMENT_ID = re.compile(r"[?&]id=(\d+)")


def _dokument_id(url: str | None) -> int | None:
    """Die Dokumentnummer des Ratsinformationssystems aus ``getfile.php?id=…``
    — die gemeinsame Kennung für Vorlagen- und TOP-Anlagen."""
    m = _DOKUMENT_ID.search(url or "")
    return int(m.group(1)) if m else None


def _top_anlagen(store, ksinr: int, mit_vorlage: set[str]) -> dict[str, list[dict]]:
    """TOP-Nummer → die Anlagen, die es NUR am Punkt gibt.

    Bei einem Punkt mit Vorlage wiederholt das Ratsinformationssystem am Punkt
    die Vorlage selbst („Vorlage“) und ihre Anlagen. Die kennt ``get_template``
    schon, samt Lesestand — hier noch einmal aufgeführt, stünden sie als
    ``on_demand`` da, obwohl ihr Text längst im Bestand liegt."""
    roh = [(a, _dokument_id(a["url"])) for a in store.top_anlagen(ksinr)]
    ids = [d for _, d in roh if d]
    bekannt = {r[0] for r in store._conn.execute(  # noqa: SLF001
        f"SELECT document_id FROM council_attachments WHERE document_id IN "
        f"({','.join('?' * len(ids))})", ids)} if ids else set()
    je_top: dict[str, list[dict]] = {}
    for a, did in roh:
        if not did or did in bekannt:
            continue
        if a["item_number"] in mit_vorlage and (a["label"] or "").strip() == "Vorlage":
            continue
        je_top.setdefault(a["item_number"], []).append({
            "attachment_id": did, "label": _sauber(a["label"]),
            "text": ("on_demand" if a["raw_text"] is None
                     else "available" if a["raw_text"] else "scan"),
            "url": a["url"]})
    return je_top


def _pdf_laden(did: int, url: str, extraktor: str = anlagentext.PYMUPDF) -> tuple[str, int]:
    """Ein PDF aus dem Ratsinformationssystem lesen, gedeckelt und beurteilt."""
    _laden_erlaubt()
    try:
        roh, seiten = vorlagen._pdf_text(url, extraktor)  # noqa: SLF001
    except Exception as fehler:  # noqa: BLE001 — ein PDF, keine Störung des Servers
        logger.warning("Anlage %s nicht geladen: %s", did, fehler)
        raise ToolError("Die Anlage ließ sich gerade nicht laden. Später erneut "
                        "versuchen oder direkt unter url öffnen.") from fehler
    return anlagentext.beurteilen(roh), seiten


def get_attachment(store, args: dict, base: str) -> str:
    did = _int(args, "attachment_id", 0, 0, 10**9)
    zeile = store._conn.execute(  # noqa: SLF001
        "SELECT a.document_id, a.label, a.url, a.status, a.raw_text, a.n_pages, "
        "t.template_number, t.title FROM council_attachments a "
        "LEFT JOIN council_templates t ON t.kvonr = a.kvonr WHERE a.document_id = ?",
        (did,)).fetchone() if did else None
    if zeile:
        did, label, url, status, text, seiten, vorlage, vorlagentitel = tuple(zeile)
        aus: dict[str, Any] = {"attachment_id": did, "label": _sauber(label),
                               "template_number": vorlage, "url": url}
        # ``failed`` darf es noch einmal versuchen: Meist war es ein
        # Netzaussetzer. ``ok`` ohne Text ebenso — so steht es in jedem lokalen
        # Abzug, der die Anlagentexte abspeckt (scripts/lokale_daten.py).
        if status != "empty" and not (status == "ok" and text) and url:
            # Derselbe Extraktor wie im Backfill: Was eine Haushalts-Schicht
            # füllen könnte, liest pypdf (``anlagentext.extraktor_fuer``).
            text, seiten = _pdf_laden(did, url, anlagentext.extraktor_fuer(label, vorlagentitel))
            store.anlagentext_nachtragen(did, text, seiten)
            aus["loaded_now"] = True
        aus["pages"] = seiten
    else:
        # Keine Vorlagen-Anlage — vielleicht eine, die direkt am
        # Tagesordnungspunkt hängt (Dringlichkeitsantrag, Konzept zu einem
        # Fraktionsantrag). Viele davon haben gar keine Vorlage.
        top = store.top_anlage_zu_dokument(did) if did else None
        if not top or str(top["item_number"] or "").upper().startswith("N"):
            raise ToolError(f"Keine Anlage mit der Kennung {did}. get_template und "
                            "get_agenda nennen die Anlagen samt attachment_id.")
        url, text = top["url"], top["raw_text"]
        aus = {"attachment_id": did, "label": _sauber(top["label"]),
               "ksinr": top["ksinr"], "item_number": top["item_number"], "url": url}
        if text is None:
            text, seiten = _pdf_laden(did, url)
            store.top_anlage_text_ablegen(url, text)
            aus["loaded_now"] = True
            aus["pages"] = seiten
    if not text:
        aus["text"] = None
        aus["hint"] = ("Dieses PDF hat keine lesbare Textebene (Scan oder Plan). "
                       "Es lässt sich nur als Datei unter url öffnen.")
        return _json(aus)
    # Telefon und E-Mail bleiben im Bestand, gehen aber nicht hinaus — wie
    # beim Suchindex (``council/kontaktdaten.py``).
    volltext = _sauber(_volltext(maskieren(text)))
    offset = _int(args, "offset", 0, 0, 10**7)
    stueck = volltext[offset:offset + VOLLTEXT_STUECK]
    weiter = offset + len(stueck)
    aus.update({"text": stueck or None, "text_length": len(volltext),
                "next_offset": weiter if weiter < len(volltext) else None})
    return _json(aus)


# --------------------------------------------------------------------------- #
# Protokoll
# --------------------------------------------------------------------------- #

def get_protocol_section(store, args: dict, base: str) -> str:
    """Was im Protokoll zu einem Tagesordnungspunkt steht — die Debatte, also
    das „Warum“, das der Beschlusstext nicht enthält."""
    did = _int(args, "decision_id", 0, 0, 10**9)
    if did:
        d = store.get_decision(did)
        if not d:
            raise ToolError(f"Kein Beschluss mit der Kennung {did}.")
        ksinr, nr = d.get("ksinr"), str(d.get("item_number") or "")
    else:
        ksinr = _int(args, "ksinr", 0, 0, 10**9)
        nr = str(args.get("item_number") or "").strip()[:20]
        if not ksinr or not nr:
            raise ToolError("decision_id angeben — oder ksinr und item_number "
                            "(z. B. „Ö 7.2“ aus get_agenda).")
    # Das veröffentlichte Protokoll ist das öffentliche; einen nichtöffentlichen
    # Punkt gibt es darin nicht — und wo der Schnitt doch etwas fände, soll es
    # nicht hinaus.
    if nr.upper().startswith("N"):
        raise ToolError("Das ist ein nichtöffentlicher Tagesordnungspunkt; dazu gibt es "
                        "kein veröffentlichtes Protokoll.")
    top = re.sub(r"^Ö\s*", "", nr).strip()
    aus: dict[str, Any] = {"ksinr": ksinr, "item_number": nr,
                           "protocol_url": store.protokoll_urls_fuer([ksinr]).get(ksinr)}
    roh = store.protocol_raw_text(ksinr) if ksinr else None
    if not roh:
        aus["text"] = None
        aus["hint"] = ("Zu dieser Sitzung liegt noch kein Protokoll vor. Protokolle "
                       "erscheinen meist einige Wochen nach der Sitzung.")
        return _json(aus)
    # ZUERST die Seitengrenzen heilen: ``saeubern`` streicht die Fußzeile
    # ebenfalls, lässt dabei aber die Leerzeile stehen — danach wäre der
    # zerrissene Absatz von einem echten nicht mehr zu unterscheiden.
    abschnitt = top_abschnitt(saeubern(_seitenwechsel_heilen(roh)), top) if top else ""
    if not abschnitt.strip():
        aus["text"] = None
        aus["hint"] = ("Im Protokoll ließ sich der Abschnitt zu diesem Punkt nicht "
                       "abgrenzen. Das ganze Protokoll steht unter protocol_url.")
        return _json(aus)
    text = _sauber(_volltext(maskieren(abschnitt)))
    offset = _int(args, "offset", 0, 0, 10**7)
    stueck = text[offset:offset + VOLLTEXT_STUECK]
    weiter = offset + len(stueck)
    aus.update({"text": stueck, "text_length": len(text),
                "next_offset": weiter if weiter < len(text) else None})
    return _json(aus)


def list_committees(store, args: dict, base: str) -> str:
    naechste = store.naechste_sitzung_je_gremium()
    return _json({"committees": [
        {"name": n, "next_session": (naechste.get(n) or {}).get("session_date")}
        for n in store.get_all_committee_names()]})


#: Höchstens so viele Sitzungen je Abruf; ein engerer Zeitraum holt den Rest.
SITZUNGEN_MAX = 100


def _sitzung(z: tuple, heute: str, base: str) -> dict:
    ksinr, gremium, tag, zeit, ort, n = z
    tag = str(tag)[:10]
    aus: dict[str, Any] = {
        "date": tag, "time": zeit or None, "committee": gremium, "location": ort or None,
        "status": "today" if tag == heute else ("upcoming" if tag > heute else "past"),
        "ksinr": ksinr,
        # Ohne ksinr steht der Termin nur im Kalender — eine Tagesordnung
        # gibt es dann noch nicht.
        "agenda_items": n if ksinr else None,
    }
    if ksinr:
        aus["url"] = f"{base}/council/sitzung?ksinr={ksinr}"
    return aus


def list_sessions(store, args: dict, base: str) -> str:
    gremium = str(args.get("committee") or "").strip()[:80]
    if not gremium:
        raise ToolError("committee fehlt, z. B. „Rat“ oder „Verkehr“.")
    d = lw.sitzungen_daten(store, gremium, _datum(args, "date_from"), _datum(args, "date_to"))
    aus: dict[str, Any] = {
        "today": d["heute"], "date_from": d["von"], "date_to": d["bis"],
        # Die nächste Sitzung ab heute steht IMMER dabei, auch bei einem
        # Zeitraum in der Vergangenheit (s. ``lw.sitzungen_daten``).
        "next_session": _sitzung(d["naechste"], d["heute"], base) if d["naechste"] else None,
        "sessions": [_sitzung(z, d["heute"], base) for z in d["zeilen"][:SITZUNGEN_MAX]],
    }
    if len(d["zeilen"]) > SITZUNGEN_MAX:
        aus["truncated"] = len(d["zeilen"]) - SITZUNGEN_MAX
    if not d["zeilen"]:
        aus["hint"] = ("Keine Sitzung in diesem Zeitraum. Zeitraum weiter fassen, oder "
                       "list_committees für den genauen Gremiennamen.")
    return _json(aus)


def get_agenda(store, args: dict, base: str) -> str:
    ksinr = _int(args, "ksinr", 0, 0, 10**9)
    daten = lw.tagesordnung_daten(store, ksinr)
    if not daten:
        raise ToolError(f"Keine Sitzung mit ksinr {ksinr}. list_sessions nennt die Kennungen.")
    sitzung, tops = daten
    anlagen = _top_anlagen(store, ksinr, {nr for nr, _t, _o, v in tops if v})
    return _json({
        "ksinr": ksinr,
        "committee": sitzung.get("committee"),
        "date": sitzung.get("session_date"),
        "items": [{"number": nr,
                   # „N 11“ ist nichtöffentlich; der Titel ist dann
                   # „gesperrte Information“, mehr gibt es dazu nicht.
                   "public": not str(nr or "").startswith("N"),
                   "title": titel,
                   "outcome": _ERGEBNIS.get(o or "", o),
                   # Für get_template: was am Punkt zur Abstimmung steht.
                   "template_number": vorlage or None,
                   # Was direkt am Punkt hängt, oft OHNE Vorlage — für
                   # get_attachment. Nichtöffentliche Punkte tragen nichts.
                   "attachments": anlagen.get(nr, []) if not str(nr or "").startswith("N")
                   else []}
                  for nr, titel, o, vorlage in tops],
        "url": f"{base}/council/sitzung?ksinr={ksinr}",
        "original_url": f"{RIS}/si0057.php?__ksinr={ksinr}",
    })


_STIMME = {"unanimous": "einstimmig", "majority": "mehrheitlich"}


def get_template_history(store, args: dict, base: str) -> str:
    nr = str(args.get("template_number") or "").strip()[:30]
    if not nr:
        raise ToolError("template_number fehlt, z. B. „25/0615“.")
    if not lw.VORLAGEN_NR.fullmatch(nr):
        raise ToolError(f"„{nr}“ ist keine Vorlagennummer; sie hat die Form „25/0615“.")
    beraten, offen = lw.beratungsfolge_daten(store, nr)
    aus: dict[str, Any] = {
        "template_number": nr,
        "consultations": [
            {"date": tag, "committee": gremium,
             "outcome": _ERGEBNIS.get(erg or "", erg),
             "vote": _STIMME.get(stimme or "", stimme),
             # Eine Ergänzung („25/0615/1“) zählt zur Vorlage dazu.
             "template_number": vnr}
            for gremium, tag, erg, stimme, vnr in beraten],
        "pending": [{"date": tag, "committee": gremium} for gremium, tag in offen],
    }
    if not beraten and not offen:
        aus["hint"] = "Zu dieser Vorlage ist keine Beratung verzeichnet."
    return _json(aus)


def count_decisions(store, args: dict, base: str) -> str:
    jahr = _int(args, "year", 0, 1990, 2035)
    field = str(args.get("policy_field") or "")
    if field and field not in _FELDER:
        raise ToolError(f"policy_field muss eines sein von: {', '.join(_FELDER)}.")
    gremium = str(args.get("committee") or "").strip()[:80]
    zeilen = sorted(lw.beschluesse_zaehlen_daten(store, jahr, field, gremium),
                    key=lambda z: -z[1])
    return _json({
        "year": jahr, "policy_field": field or None, "committee": gremium or None,
        "total": sum(n for _, n in zeilen),
        "by_outcome": {_ERGEBNIS.get(o or "", o or "ohne Ergebnis"): n for o, n in zeilen},
        # Gezählt hat die Datenbank, nicht ein Modell — die Zahl ist exakt.
        "counted_by": "ratslotse",
    })


# --------------------------------------------------------------------------- #
# Haushalt — nur mit dem Recht ``budget`` (21.10.2026)
# --------------------------------------------------------------------------- #
#
# Dieselben Abfragen wie Lottis Haushaltswerkzeuge (``lw.*_daten``), hier als
# Daten mit Beleg je Wert. Bis 10/2026 stand im Modulkopf „kein Haushalt“: Der
# Bereich hing an ``budget`` und war der eigenen Oberfläche vorbehalten. Tims
# Entscheidung 21.10.: Konten MIT diesem Recht (Ratsmitglieder, Fachpublikum)
# bekommen ihn auch im Agenten; alle anderen sehen die Werkzeuge nicht einmal.
# ``rechnen`` und ``seite_lesen`` fehlen bewusst: Rechnen kann der Agent
# selbst, und die Seiten sind Oberfläche, keine Daten.

BUDGET = "budget"


class _Quellen:
    """Sammelt die Belege einer Antwort; jeder Wert verweist mit ``source``
    auf einen Eintrag in ``sources`` — so steht dieselbe Fundstelle nicht
    bei jedem Jahr noch einmal da."""

    def __init__(self, store) -> None:
        self._store = store
        self._index: dict[int, int] = {}
        self.liste: list[dict] = []

    def nr(self, herkunft_id: int | None) -> int | None:
        if herkunft_id is None:
            return None
        if herkunft_id not in self._index:
            b = self._store._beleg(herkunft_id)  # noqa: SLF001 — derselbe Beleg wie bei Lotti
            if not b or not b.get("url"):
                return None
            self._index[herkunft_id] = len(self.liste)
            self.liste.append({"label": _sauber(b.get("label")), "citation": b.get("citation"),
                               "page": b.get("page"), "as_of": b.get("as_of"), "url": b["url"]})
        return self._index[herkunft_id]


def _jahre(args: dict) -> tuple[int, int]:
    von = _int(args, "year_from", 2015, 1990, 2035)
    bis = _int(args, "year_to", 2035, 1990, 2035)
    return (von, bis) if von <= bis else (bis, von)


def _betrag(v: Any) -> float | None:
    return None if v is None else round(float(v), 2)


def budget_search(store, args: dict, base: str) -> str:
    from council import qa
    begriffe = str(args.get("query") or "").strip()[:200]
    if not begriffe:
        raise ToolError("query fehlt, z. B. „Kindertagesbetreuung 2024“ oder "
                        "„Gewerbesteuer Plan 2026“.")
    geld = qa.geld_kontext(store, begriffe, begriffe, "money")
    text = qa.geld_block(geld, max_chars=lw.BLOCK_MAX) if geld else ""
    aus: dict[str, Any] = {
        "query": begriffe,
        # Der Block ist derselbe, den die KI-Frage bekommt: jede Zahl unter
        # ihrem eigenen Jahr, Plan und Ist ausdrücklich getrennt.
        "text": _sauber(text) or None,
        "sources": [{"label": _sauber(b.get("label")), "year": b.get("year"), "url": b["url"]}
                    for b in (qa.geld_belege(geld, max_chars=lw.BLOCK_MAX, max_n=10)
                              if geld else [])],
        "related_series": [k for k, woerter in lw._REIHEN_WOERTER.items()  # noqa: SLF001
                           if any(w in begriffe.lower() for w in woerter)],
    }
    if not text:
        aus["hint"] = ("Dazu steht in den Haushaltsdaten nichts. Andere Stichwörter "
                       "versuchen, budget_series für Kennzahlen über Jahre, oder "
                       "search_decisions, wenn die Zahl in einem Ratsbeschluss steht.")
    return _json(aus)


def budget_series(store, args: dict, base: str) -> str:
    reihe = str(args.get("series") or "")
    if reihe not in lw.REIHEN:
        raise ToolError(f"series muss eines sein von: {', '.join(sorted(lw.REIHEN))}.")
    titel, _sql, einheit = lw.REIHEN[reihe]
    von, bis = _jahre(args)
    alle, treffer = lw.zeitreihe_daten(store, reihe, von, bis)
    q = _Quellen(store)
    aus: dict[str, Any] = {
        "series": reihe, "label": titel,
        "unit": {"€": "EUR", "%": "percent"}.get(einheit, "count"),
        "values": [{"year": int(j), "value": _betrag(w), "source": q.nr(h)}
                   for j, w, h in treffer if w is not None],
        "available_years": [int(alle[0][0]), int(alle[-1][0])] if alle else None,
    }
    aus["sources"] = q.liste
    return _json(aus)


def budget_product(store, args: dict, base: str) -> str:
    name = str(args.get("product") or "").strip()[:120]
    if not name:
        raise ToolError("product fehlt, z. B. „Kindertagesbetreuung“.")
    von, bis = _jahre(args)
    zeilen = lw.produkt_daten(store, name, von, bis)
    namen = sorted({z[1] for z in zeilen})
    if len(namen) > 4:
        return _json({"product": name, "matches": namen[:30],
                      "hint": "Mehrere Produkte passen — mit einem dieser Namen erneut fragen."})
    q = _Quellen(store)
    aus = {"product": name, "kind": "Plan (Haushaltsplan des jeweiligen Jahres)", "unit": "EUR",
           "values": [{"year": int(j), "product": p, "expenses": _betrag(a),
                       "revenues": _betrag(e), "source": q.nr(h)}
                      for j, p, a, e, h in zeilen],
           "sources": q.liste}
    if not zeilen:
        aus["hint"] = "Kein passendes Produkt im Zeitraum. Teilwort oder budget_search versuchen."
    return _json(aus)


def enterprise_plans(store, args: dict, base: str) -> str:
    name = str(args.get("enterprise") or "").strip()[:80]
    if not name:
        raise ToolError("enterprise fehlt, z. B. „awb“, „Bäder“ oder „Stadion“.")
    von, bis = _jahre(args)
    q = _Quellen(store)
    zeilen = lw.betrieb_daten(store, name, von, bis)
    aus = {"enterprise": name, "kind": "Plan (Wirtschaftsplan des jeweiligen Jahres)",
           "unit": "EUR",
           "values": [{"year": int(j), "enterprise": b, "revenues": _betrag(e),
                       "expenses": _betrag(a), "planned_result": _betrag(r), "source": q.nr(h)}
                      for b, j, e, a, r, h in zeilen],
           "sources": q.liste}
    if not zeilen:
        aus["hint"] = ("Kein Wirtschaftsplan dazu. Betriebe: awb, bbgo, bbo, egh, Hafen, "
                       "Stadion, Stadionplanung.")
    return _json(aus)


def fee_calculations(store, args: dict, base: str) -> str:
    name = str(args.get("area") or "").strip()[:80]
    if not name:
        raise ToolError("area fehlt, z. B. „Straßenreinigung“ oder „Abfall“.")
    von, bis = _jahre(args)
    q = _Quellen(store)
    zeilen = lw.gebuehren_daten(store, name, von, bis)
    aus = {"area": name, "kind": "Gebührenbedarfsberechnung des jeweiligen Jahres",
           "values": [{"year": int(j), "area": b, "costs_to_cover_eur": _betrag(k),
                       "fee_eur": _betrag(f), "per": e or None, "source": q.nr(h)}
                      for b, j, k, f, e, h in zeilen],
           "sources": q.liste}
    if not zeilen:
        aus["hint"] = ("Keine Kalkulation dazu. Bereiche: Straßenreinigung, Abfallsammlung, "
                       "Abfallbehandlungsanlagen.")
    return _json(aus)


_MONAT = re.compile(r"\d{4}-\d{2}")


def cash_position(store, args: dict, base: str) -> str:
    von = str(args.get("month_from") or "").strip()[:7]
    bis = str(args.get("month_to") or "").strip()[:7]
    if not (_MONAT.fullmatch(von) and _MONAT.fullmatch(bis)):
        raise ToolError("month_from und month_to in der Form JJJJ-MM angeben.")
    q = _Quellen(store)
    zeilen = lw.kassenstand_daten(store, von, bis)[:60]
    aus = {"label": "Kassenstand (Liquidität) am Monatsende", "unit": "EUR",
           "values": [{"month": m, "amount": _betrag(b), "source": q.nr(h)}
                      for m, b, h in zeilen],
           "sources": q.liste}
    if not zeilen:
        aus["hint"] = "Für diesen Zeitraum ist kein Kassenstand erfasst."
    return _json(aus)


_JAHR = {"type": "integer", "minimum": 1990, "maximum": 2035}
_JAHRE = {"year_from": _JAHR, "year_to": _JAHR}


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
         "kommt in Stücken; mit next_offset weiterlesen. Dazu die Liste der Anlagen "
         "(Gutachten, Pläne, Anträge) mit attachment_id für get_attachment.",
         _schema({"template_number": {"type": "string", "description": "z. B. „25/0615“"},
                  "offset": {"type": "integer", "minimum": 0, "default": 0}},
                 ["template_number"]),
         get_template),
    Tool("get_attachment", "Anlage lesen",
         "Der Text einer Anlage (attachment_id aus get_template oder get_agenda). Noch "
         "nicht geladene Anlagen holt Ratslotse beim ersten Abruf aus dem "
         "Ratsinformationssystem. Langer Text kommt in Stücken; mit next_offset "
         "weiterlesen. Scans ohne Textebene gibt es nur als PDF unter url.",
         _schema({"attachment_id": {"type": "integer", "minimum": 1},
                  "offset": {"type": "integer", "minimum": 0, "default": 0}},
                 ["attachment_id"]),
         get_attachment, open_world=True),
    Tool("get_protocol_section", "Protokollabschnitt",
         "Was im Sitzungsprotokoll zu einem Tagesordnungspunkt steht: die Debatte mit "
         "Wortbeiträgen und die Abstimmung — also das „Warum“ hinter einem Beschluss. "
         "decision_id aus search_decisions/get_decision, oder ksinr und item_number "
         "aus get_agenda. Lange Abschnitte kommen in Stücken; mit next_offset weiterlesen.",
         _schema({"decision_id": {"type": "integer", "minimum": 1},
                  "ksinr": {"type": "integer", "minimum": 1},
                  "item_number": {"type": "string", "description": "z. B. „Ö 7.2“"},
                  "offset": {"type": "integer", "minimum": 0, "default": 0}}),
         get_protocol_section),
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
         "den Ergebnissen, sobald beschlossen ist, der Vorlagennummer je Punkt (für "
         "get_template) und den Anlagen, die direkt am Punkt hängen — Dringlichkeits- und "
         "Änderungsanträge haben oft keine Vorlage (für get_attachment).",
         _schema({"ksinr": {"type": "integer", "minimum": 1}}, ["ksinr"]),
         get_agenda),
    Tool("count_decisions", "Beschlüsse zählen",
         "Zählt die Beschlüsse eines Jahres nach Ergebnis, wahlweise für ein Themenfeld "
         "und/oder ein Gremium.",
         _schema({"year": {"type": "integer", "minimum": 1990, "maximum": 2035},
                  "policy_field": {"type": "string", "enum": list(_FELDER)},
                  "committee": {"type": "string"}}, ["year"]),
         count_decisions),
    Tool("budget_search", "Haushalt durchsuchen",
         "Schlägt in den geprüften Haushaltsdaten der Stadt Oldenburg nach — Haushaltsplan, "
         "Jahresabschlüsse, Teilhaushalte, Produkte, Investitionen, Steuern, Schulden, "
         "Wirtschaftspläne, Gebühren. Stichwörter auf DEUTSCH, gern mit Jahr: "
         "„Kindertagesbetreuung 2024“, „Gewerbesteuer Plan 2026“, „Investitionen "
         "Fliegerhorst“. Jede Zahl steht unter ihrem Jahr, Plan und Ist sind getrennt; "
         "dazu die Belege. Für Kennzahlen über viele Jahre: budget_series.",
         _schema({"query": {"type": "string"}}, ["query"]), budget_search, recht=BUDGET),
    Tool("budget_series", "Haushalts-Kennzahl über Jahre",
         "Eine Kennzahl des Stadthaushalts über mehrere Jahre, jeder Wert mit Beleg "
         "(Schulden, Steuereinnahmen, Investitionen, Personalaufwand, Ergebnis, "
         "Einwohner, Stellen, Hebesätze …). Plan- und Ist-Reihen sind getrennt benannt.",
         _schema({"series": {"type": "string", "enum": sorted(lw.REIHEN)}, **_JAHRE},
                 ["series"]), budget_series, recht=BUDGET),
    Tool("budget_product", "Haushalts-Produkt über Jahre",
         "Geplante Aufwendungen und Erträge einer Aufgabe des Haushalts (Produkt, z. B. "
         "„Kindertagesbetreuung“, „Brand- und Katastrophenschutz“) über mehrere Planjahre.",
         _schema({"product": {"type": "string"}, **_JAHRE}, ["product"]),
         budget_product, recht=BUDGET),
    Tool("enterprise_plans", "Wirtschaftspläne der Betriebe",
         "Wirtschaftspläne städtischer Betriebe über die Jahre: Erträge, Aufwendungen, "
         "geplantes Ergebnis (negativ = Verlust). Betriebe: Abfallwirtschaftsbetrieb (awb), "
         "Bäderbetriebsgesellschaft (bbgo), Bäderbetrieb (bbo), Gebäudewirtschaft und "
         "Hochbau (egh), Hafen, Stadion, Stadionplanung.",
         _schema({"enterprise": {"type": "string"}, **_JAHRE}, ["enterprise"]),
         enterprise_plans, recht=BUDGET),
    Tool("fee_calculations", "Gebührenkalkulationen",
         "Gebührenbedarfsberechnungen über die Jahre: zu deckende Kosten und Gebührensatz. "
         "Bereiche: Straßenreinigung, Abfallsammlung, Abfallbehandlungsanlagen.",
         _schema({"area": {"type": "string"}, **_JAHRE}, ["area"]),
         fee_calculations, recht=BUDGET),
    Tool("cash_position", "Kassenstand",
         "Der Kassenstand (Liquidität) der Stadt je Monatsende.",
         _schema({"month_from": {"type": "string", "pattern": r"^\d{4}-\d{2}$",
                                 "description": "JJJJ-MM"},
                  "month_to": {"type": "string", "pattern": r"^\d{4}-\d{2}$",
                               "description": "JJJJ-MM"}}, ["month_from", "month_to"]),
         cash_position, recht=BUDGET),
)}


def erlaubt(rechte: frozenset[str] | set[str]) -> list[Tool]:
    """Die Werkzeuge, die ein Konto mit diesen Rechten sieht und rufen darf."""
    return [t for t in TOOLS.values() if t.recht is None or t.recht in rechte]


def ausfuehren(store, name: str, args: dict | None, base: str,
               rechte: frozenset[str] | set[str] = frozenset()) -> str:
    """Führt ein Werkzeug aus. Wirft ``KeyError`` für einen unbekannten Namen —
    auch für eines, das dem Konto nicht zusteht (es soll nicht einmal erfahren,
    dass es das gibt) — und ``ToolError`` für Eingaben, die der Agent
    korrigieren kann."""
    tool = TOOLS[name]
    if tool.recht is not None and tool.recht not in rechte:
        raise KeyError(name)
    if args is not None and not isinstance(args, dict):
        raise ToolError("arguments muss ein Objekt sein.")
    return tool.run(store, args or {}, base.rstrip("/"))
