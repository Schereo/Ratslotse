"""Belegprüfung ohne Modell: Steht, was ein erzeugter Satz behauptet, wörtlich
in der Quelle? (docs/plan-vorlagen-aufbereiten.md, § 3.4, PR 8)

Eine Regel statt zwei: ``tight`` und ``locate`` stammen aus ``plan_judge``
(die Pläne der Stadt prüfen ihre Kernaussagen schon so) und stehen jetzt hier;
``plan_judge`` importiert sie von dort. Die Zahlenprüfung übernimmt die von
``kritiker`` (Zahlwörter, „9,5 Mio." gegen „9.500.000", Tausenderpunkte), denn
``plan_judge.numbers`` prüft nur Ziffern — und genau die Anträge schreiben
„von fünf auf vier".

Eine Aussage bleibt nur, wenn alles gilt:

1. Quelle bekannt (``V1``, ``A1`` …).
2. Zitat wörtlich, mindestens 30 Zeichen verdichtet; die Seite wird berichtigt.
3. Jede Mengenangabe des Satzes steht im Zitat (Jahre, Paragrafen,
   Ordnungszahlen frei).
4. Wertungs- und Ergebniswörter nur, wenn das Zitat sie trägt — anders als
   ``kritiker.pruefe`` (für Kartensätze gebaut), das „Risiken" oder „der Rat
   hat … beschlossen" pauschal verwirft und damit Vorgeschichte und
   Risikoabschnitte leerlaufen ließe.
5. Keine Aktenzeichen in Klammern, höchstens 220 Zeichen.
6. Keine Person mit Anrede, die nicht im Zitat steht.
7. Ausgabefilter: im Satz keine URL, kein ``@``, keine Telefonnummer — auch
   nicht in gesperrter Schrift („T e l e f o n"); Zitate werden maskiert.
"""
from __future__ import annotations

import re

from council import kontaktdaten
from council.kritiker import _AKTENZEICHEN_RE, _ERGEBNIS_RE, _WERTUNG_RE, _varianten, _zahlen

QUOTE_MAX = 420
#: Ein Zitat aus drei Wörtern belegt nichts.
QUOTE_MIN_TIGHT = 30
SATZ_MAX = 220

_TIGHT_DROP = re.compile("[\\s\\-­‐‑‒–—\"'„“”‚‘’»«›‹-]+")  # mit dem privaten Unicode-Bereich (PDF-Aufzählungszeichen)
_LIGATURES = {"ﬂ": "fl", "ﬀ": "ff", "ﬁ": "fi", "ﬃ": "ffi", "ﬄ": "ffl"}
#: Die Fußzeile jeder Seite eines Vorlagen-Ausdrucks — steht mitten im Satz, wo die Seite wechselt.
_PRINT_FOOTER = re.compile(r"Ausdruck vom:\s*\d{2}\.\d{2}\.\d{4}\s+Seite:\s*\d+/\d+")
_PRIVATE_USE = re.compile("[-]")


def squash(text: str) -> str:
    """Leerraum vereinheitlichen, Zeichen aus dem privaten Unicode-Bereich weg."""
    return re.sub(r"\s+", " ", _PRIVATE_USE.sub("", text or "")).strip()


def tight(text: str) -> str:
    """Für den Vergleich Zitat gegen Quelltext: ohne Leerraum, Trenn- und Gedankenstriche und
    Anführungszeichen, Ligaturen aufgelöst. Der PDF-Text bricht Zeilen mitten im Wort („Ver- pflegung“)
    und setzt typografische Zeichen, die ein Modell beim Abschreiben glättet — die Wörter und Zahlen
    müssen trotzdem Zeichen für Zeichen dieselben sein."""
    text = _PRINT_FOOTER.sub(" ", text or "")
    for old, new in _LIGATURES.items():
        text = text.replace(old, new)
    return _TIGHT_DROP.sub("", text)


def locate(quote: str, source: dict, page: int | None) -> tuple[bool, int | None]:
    """Steht das Zitat wörtlich in der Quelle? Bei Seiten: auf welcher — die Seitenangabe des
    Modells wird berichtigt, wenn das Zitat auf einer anderen steht; ein Zitat über einen Seitenwechsel
    zählt zur ersten der beiden Seiten. ``source`` trägt ``text`` und optional ``pages``."""
    needle = tight(quote)
    if len(needle) < QUOTE_MIN_TIGHT:
        return False, None
    pages = source.get("pages")
    if pages is None:
        return needle in tight(source["text"]), None
    packed = [tight(p) for p in pages]
    order = ([page - 1] if page and 0 < page <= len(packed) else []) + list(range(len(packed)))
    for i in order:
        if needle in packed[i]:
            return True, i + 1
    for i in order:
        if i + 1 < len(packed) and needle in packed[i] + packed[i + 1]:
            return True, i + 1
    return False, None


def pages_from_offsets(text: str, offsets: list[int] | None) -> list[str] | None:
    """Die Seiten eines gespeicherten Texts aus seinen Seitenanfängen
    (``council_documents.page_offsets``)."""
    if not offsets:
        return None
    grenzen = list(offsets) + [len(text)]
    return [text[grenzen[i]:grenzen[i + 1]] for i in range(len(offsets))]


# Folgen aus Einzelzeichen mit Leerzeichen („T e l e f o n 0 4 4 1") — so setzen
# Briefköpfe Kontaktdaten; ``kontaktdaten`` sieht sie erst zusammengezogen.
_GESPERRT_RE = re.compile(r"(?<!\S)(?:\S ){3,}\S(?!\S)")
_URL_RE = re.compile(r"https?://|www\.", re.I)
_TELEFON_RE = re.compile(r"(?:\+49|\b0)\s*\d{2,5}[\s/–-]*\d{3,}")
_ANREDE_RE = re.compile(r"\b(?:Herr|Frau|Herrn)\s+(?:Dr\.\s+)?([A-ZÄÖÜ][\wäöüß-]+)")


def zusammenziehen(text: str) -> str:
    return _GESPERRT_RE.sub(lambda m: m.group(0).replace(" ", ""), text or "")


def satz_sauber(text: str) -> str | None:
    """Grund, warum ein erzeugter Satz nicht nach außen darf — oder ``None``."""
    t = zusammenziehen(text)
    if _URL_RE.search(t) or "@" in t:
        return "Adresse im Satz"
    if _TELEFON_RE.search(t):
        return "Telefonnummer im Satz"
    return None


def check_statement(entry: dict, sources: dict[str, dict], *, limit: int = SATZ_MAX) -> tuple[dict | None, str | None]:
    """Eine Aussage ``{text, quote, source, page}`` gegen ihre Quellen — die
    geprüfte Aussage oder der Grund, warum sie fällt.

    ``sources``: ``{"V1": {"text": …, "pages": [...]?, "document_id": …}, "A1": …}``."""
    if not isinstance(entry, dict):
        return None, "keine Angabe"
    text, quote = squash(str(entry.get("text") or "")), squash(str(entry.get("quote") or ""))
    benannt = re.search(r"\b[VA]\d+\b", str(entry.get("source") or ""))
    quelle = sources.get(benannt.group(0)) if benannt else None
    if not text or len(text) > limit:
        return None, f"Satz fehlt oder ist länger als {limit} Zeichen"
    if quelle is None or benannt is None:
        return None, "unbekannte Quelle"
    if not quote or len(quote) > QUOTE_MAX:
        return None, "Zitat fehlt oder ist zu lang"
    seite = entry.get("page") if isinstance(entry.get("page"), int) else None
    gefunden, seite = locate(quote, quelle, seite)
    if not gefunden:
        return None, "Zitat steht nicht wörtlich in der Quelle"
    zitat_flach = quote.lower()
    fehlend = sorted(z for z in _zahlen(text) if not any(v.lower() in zitat_flach for v in _varianten(z)))
    if fehlend:
        return None, f"Zahl ohne Beleg im Zitat: {', '.join(fehlend)}"
    for muster, art in ((_WERTUNG_RE, "Wertung"), (_ERGEBNIS_RE, "Ergebnis")):
        for m in muster.finditer(text):
            if m.group(0).lower() not in zitat_flach:
                return None, f"{art} ohne Beleg im Zitat: {m.group(0)}"
    if _AKTENZEICHEN_RE.search(text):
        return None, "Aktenzeichen im Satz"
    for m in _ANREDE_RE.finditer(text):
        if m.group(1).lower() not in zitat_flach:
            return None, f"Person ohne Beleg im Zitat: {m.group(0)}"
    if grund := satz_sauber(text):
        return None, grund
    return {"text": text, "quote": kontaktdaten.maskieren(zusammenziehen(quote)),
            "source": benannt.group(0), "page": seite}, None


def check_list(entries: object, sources: dict[str, dict], dropped: list[dict], feld: str,
               *, limit: int = SATZ_MAX) -> list[dict]:
    """Eine Liste von Aussagen prüfen; Verworfenes landet mit Grund in ``dropped``."""
    out: list[dict] = []
    for e in entries if isinstance(entries, list) else []:
        ok, grund = check_statement(e, sources, limit=limit)
        if ok:
            out.append(ok)
        else:
            dropped.append({"field": feld, "reason": grund, "entry": e})
    return out
