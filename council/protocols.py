"""Extract structured data from public council session protocols (Niederschriften).

A past session carries a "Protokoll (öffentlich)" PDF. We download it, pull the
text (``pypdf``) and ask an LLM to return structured decisions + attendance in one
call. Topic-matching is NOT done here — that is per-owner and lives in a later
phase; this module produces owner-agnostic facts only.
"""
from __future__ import annotations

import io
import json
import logging
import os
import re
from types import SimpleNamespace

import requests
import pypdf
from bs4 import BeautifulSoup

from kern import llm

BASE = "https://buergerinfo.oldenburg.de"
MODEL = os.environ.get("COUNCIL_PROTOCOL_MODEL", "deepseek/deepseek-v4-pro")
# Protocols run long; cap the input we feed the model (chars ≈ 0.3 tokens).
MAX_INPUT_CHARS = int(os.environ.get("COUNCIL_PROTOCOL_MAX_CHARS", "60000"))

logger = logging.getLogger("council.protocols")

_session = requests.Session()
_session.headers["User-Agent"] = "Mozilla/5.0"


#: „nichtöffentlich" in allen Schreibweisen, die im Ratsinfo vorkommen —
#: zusammen, mit Bindestrich, mit Leerzeichen. Ein solches Protokoll wollen wir
#: nicht: Es steht öffentlich gar nicht zum Abruf, und was daraus zitiert würde,
#: gehörte nicht auf die Seite.
_NICHTOEFFENTLICH = re.compile(r"nicht[-\s]?öffentlich")


def is_public_protocol_label(label: str) -> bool:
    """Ist diese Datei-Beschriftung das öffentliche Protokoll einer Sitzung?

    Bis 09/2026 verlangte die Prüfung **beides**: das Wort „Protokoll"/
    „Niederschrift" UND das Wort „öffentlich". Das ist die übliche Oldenburger
    Beschriftung („Protokoll Rat 29.06.2026 öffentlich", „Protokoll KulturA
    16.06.2026 öffentlich") — aber eben nur die übliche.

    Der Ausschuss für Allgemeine Angelegenheiten beschriftet seine Dateien
    „Protokoll AAA 17.08.2026", ohne den Zusatz. Damit fiel jedes seiner
    Protokolle durch, ``find_protocol`` meldete „noch keins veröffentlicht",
    und der Ausschuss stand seit seiner ersten Sitzung (01.06.2026) dauerhaft
    auf null Beschlüssen — sichtbar auf der Abo-Seite als Gremium ohne jede
    Zahl. Kein Fehler schlug an: „kein Protokoll" ist der Normalfall für eine
    frische Sitzung, es sieht also nie nach einem Ausfall aus.

    Die Regel ist deshalb umgedreht: Ein Protokoll gilt als öffentlich, solange
    es sich nicht ausdrücklich als nichtöffentlich ausweist. Auf der
    öffentlichen Seite steht ohnehin nur, was die Stadt dort zeigen will; der
    Zusatz ist eine Beschriftung, keine Zugangskontrolle.
    """
    l = label.lower()
    if not re.search(r"protokoll|niederschrift", l):
        return False
    if _NICHTOEFFENTLICH.search(l):
        return False
    # „Genehmigung des Protokolls Nr. 07/26" ist eine Vorlage ÜBER ein
    # Protokoll, kein Protokoll — der Genitiv ist das Erkennungszeichen. Ohne
    # diese Schranke zöge die gelockerte Regel eine fremde Sitzung als
    # Niederschrift dieser Sitzung herein, und die Beschlüsse landeten am
    # falschen Tag. (Vorher hielt die Pflicht zum Wort „öffentlich" das ab.)
    if "genehmigung" in l or "protokolls" in l:
        return False
    return True


def find_protocol(ksinr: int) -> dict | None:
    """Return {url, document_id, label} for the public protocol PDF of a session,
    or None if none is published yet.

    Steht auf einer Seite mehr als ein Protokoll (Sitzungen, die die Fortsetzung
    einer vertagten Sitzung protokollieren), gewinnt das ausdrücklich als
    „öffentlich" beschriftete — sonst das erste, das ``is_public_protocol_label``
    durchlässt.
    """
    r = _session.get(f"{BASE}/si0057.php", params={"__ksinr": ksinr}, timeout=20)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    treffer: list[dict] = []
    for a in soup.find_all("a", href=True):
        if "getfile.php" not in a["href"]:
            continue
        # Nur Dateien der SITZUNG, nicht die Anlagen ihrer Tagesordnungspunkte.
        # SessionNet stellt die Sitzungsdateien (Aushang, Protokoll) über die
        # Tagesordnung; die Anlagen jedes TOP hängen in der Tabelle darunter,
        # also in einer Zelle. Ohne diese Trennung zog die gelockerte Regel
        # „Protokoll Bürgerinformationsveranstaltung" — die Anlage einer
        # Bauleitplan-Vorlage — als Niederschrift der Ratssitzung herein und
        # hätte deren Beschlüsse aus einem fremden Papier gelesen (gemessen am
        # Prod-Bestand, 03.09.2026: 5 solcher Fehlgriffe in 20 Sitzungen).
        if a.find_parent("td") is not None:
            continue
        text = a.get_text(" ", strip=True)
        label = text + " " + a.get("title", "")
        if not is_public_protocol_label(label):
            continue
        href = a["href"] if a["href"].startswith("http") else f"{BASE}/{a['href'].lstrip('/')}"
        m = re.search(r"id=(\d+)", href)
        treffer.append({
            "url": href,
            "document_id": int(m.group(1)) if m else None,
            "label": text,
            "_ausdruecklich": "öffentlich" in label.lower(),
        })
    if not treffer:
        return None
    gewaehlt = next((t for t in treffer if t["_ausdruecklich"]), treffer[0])
    return {k: v for k, v in gewaehlt.items() if not k.startswith("_")}


def page_offsets(seiten: list[str]) -> list[int]:
    """Zeichen-Offsets der Seitenanfänge im mit ``"\\n"`` verklebten Text —
    die Grundlage, um eine Fundstelle im ``raw_text`` einer PDF-Seite
    zuzuordnen (seitengenaue Protokoll-Links, Tims Wunsch 18.08.)."""
    offsets, pos = [], 0
    for s in seiten:
        offsets.append(pos)
        pos += len(s) + 1  # +1 für das "\n" des join
    return offsets


def extract_pdf_text(url: str) -> tuple[str, int, list[int]]:
    """Download a PDF and return (text, n_pages, page_offsets)."""
    r = _session.get(url, timeout=45)
    r.raise_for_status()
    reader = pypdf.PdfReader(io.BytesIO(r.content))
    seiten = [p.extract_text() or "" for p in reader.pages]
    return "\n".join(seiten), len(seiten), page_offsets(seiten)


_PROMPT = """Du extrahierst strukturierte Daten aus dem Protokoll einer Stadtrats- oder \
Ausschusssitzung in Oldenburg. Antworte mit NUR JSON in genau dieser Form:

{{
  "protocol_nr": "z.B. AFB 01/26 oder null",
  "session_start": "HH:MM oder null",
  "session_end": "HH:MM oder null",
  "attendance": [
    {{"name": "Vor- und Nachname", "party": "Fraktion oder Gruppe (z.B. SPD, CDU, Verwaltung)", "role": "chair|member|administration|minutes|guest", "note": "z.B. 'bis TOP 20.2' oder null"}}
  ],
  "decisions": [
    {{
      "item_number": "TOP-Nummer wie '9.4'",
      "title": "TOP-Titel",
      "official_text": "Wortlaut des gefassten Beschlusses (Endergebnis), sinngemäß gekürzt",
      "outcome": "accepted|rejected|postponed|noted|no_decision",
      "vote": "unanimous|majority oder null",
      "no_votes": Zahl oder null,
      "abstentions": Zahl oder null,
      "factions": ["Fraktionen, die zu diesem TOP Anträge/Änderungslisten stellten, sonst leer"],
      "template_number": "Vorlagennummer wie '26/0042' oder null",
      "raw_result": "der Original-Abstimmungssatz des Endergebnisses",
      "sub_votes": [
        {{
          "description": "WAS beantragt wurde — Antragsart, Fraktion UND inhaltliches Anliegen, \
z.B. 'Änderungsantrag der BSW-Fraktion: Streichung des Punktes 8 (Umweltzone)'",
          "outcome": "accepted|rejected|postponed",
          "vote": "unanimous|majority oder null",
          "no_votes": Zahl oder null,
          "factions": ["antragstellende Fraktion(en)"],
          "raw_result": "der Original-Abstimmungssatz dieser Teilabstimmung"
        }}
      ]
    }}
  ]
}}

Regeln:
- Nur Tagesordnungspunkte mit echtem Inhalt/Beschluss/Bericht aufnehmen. Reine \
Formalia (Feststellung der Beschlussfähigkeit, Genehmigung der Tagesordnung, \
Genehmigung von Protokollen) WEGLASSEN.
- "outcome" = "noted", wenn nur ein Bericht zur Kenntnis genommen wurde.
- "sub_votes": JEDE einzelne Teilabstimmung (z.B. über Änderungslisten/Anträge \
einzelner Fraktionen) als eigenen Eintrag. Wenn es keine Teilabstimmungen gab: leere Liste.
- "description" der sub_votes: Nenne das inhaltliche Anliegen, nicht nur die Antragsart. \
Steht im Protokoll, WAS der Antrag ändern/erreichen sollte, gehört das hinein (sinngemäß \
gekürzt). Nur wenn das Protokoll den Inhalt wirklich nicht nennt, reicht \
'Änderungsantrag der X-Fraktion'.
- Das Haupt-"outcome"/"vote"/"official_text" beschreibt das ENDergebnis des TOP, die \
sub_votes die einzelnen Abstimmungen davor.
- Zahlen als Zahl ausschreiben (z.B. "fünf" -> 5).
- Erfinde nichts; fehlende Werte = null.

PROTOKOLL:
{text}"""


def _strip_fences(content: str) -> str:
    """Strip a ```json … ``` markdown fence the model sometimes adds."""
    c = content.strip()
    if c.startswith("```"):
        c = c.strip("`").strip()
        if c.lower().startswith("json"):
            c = c[4:].strip()
    return c


# TOP-Kopfzeilen („TOP 9.4 …", „Ö 6.1 …", „14. …") — die sauberen Schnittstellen,
# wenn ein langes Protokoll für die Extraktion zerlegt werden muss.
_TOP_LINE_RE = re.compile(r"^[ \t]*(?:TOP\s+)?(?:Ö\s?|N\s?)?\d{1,2}(?:\.\d{1,2}){0,2}[.)]?\s+\S",
                          re.MULTILINE)


def _split_protocol(text: str, max_chars: int | None = None) -> list[str]:
    """Langen Protokolltext in extrahierbare Teile zerlegen, geschnitten an
    TOP-Kopfzeilen (Notnagel: harter Schnitt). Ersetzt die frühere stille
    Kappung bei MAX_INPUT_CHARS, die alle späteren TOPs verschluckte —
    Rats-Niederschriften überschreiten die Grenze regelmäßig."""
    max_chars = max_chars or MAX_INPUT_CHARS
    if len(text) <= max_chars:
        return [text]
    breaks = [m.start() for m in _TOP_LINE_RE.finditer(text)]
    parts, start = [], 0
    while start < len(text):
        end = start + max_chars
        if end >= len(text):
            parts.append(text[start:])
            break
        # Letzte TOP-Kopfzeile im Fenster — aber nicht im ersten Drittel, sonst
        # entstehen Mini-Teile, wenn direkt nach dem Start ein TOP beginnt.
        cut = max((b for b in breaks if start + max_chars // 3 <= b <= end), default=end)
        parts.append(text[start:cut])
        start = cut
    return parts


def _merge_parts(results: list[dict]) -> dict:
    """Teil-Extraktionen zu einem Protokoll zusammenführen: Kopfdaten aus dem
    ersten Teil, der sie kennt (Anwesenheit steht immer vorn), Sitzungsende aus
    dem letzten, Beschlüsse aneinandergereiht (Dubletten an den Schnittkanten
    über TOP-Nummer+Titel verworfen)."""
    merged = {
        "protocol_nr": next((r.get("protocol_nr") for r in results if r.get("protocol_nr")), None),
        "session_start": next((r.get("session_start") for r in results if r.get("session_start")), None),
        "session_end": next((r.get("session_end") for r in reversed(results) if r.get("session_end")), None),
        "attendance": next((r.get("attendance") for r in results if r.get("attendance")), []),
        "decisions": [],
    }
    seen: set[tuple] = set()
    for r in results:
        for d in r.get("decisions") or []:
            key = ((d.get("item_number") or "").strip(),
                   (d.get("title") or "").strip().lower()[:60])
            if key in seen:
                continue
            seen.add(key)
            merged["decisions"].append(d)
    return merged


def extract_protocol(text: str, model: str = MODEL):
    """Run the LLM extraction. Returns (data_dict, usage). Lange Protokolle
    werden an TOP-Grenzen zerlegt, je Teil extrahiert und zusammengeführt —
    vorher fielen alle TOPs jenseits von MAX_INPUT_CHARS stillschweigend weg."""
    parts = _split_protocol(text)
    if len(parts) > 1:
        logger.info("Protokoll (%d Zeichen) in %d Teile zerlegt", len(text), len(parts))
    results, tok_in, tok_out = [], 0, 0
    for part in parts:
        data, usage = _extract_one(part, model)
        results.append(data)
        tok_in += getattr(usage, "prompt_tokens", 0) or 0
        tok_out += getattr(usage, "completion_tokens", 0) or 0
    data = results[0] if len(results) == 1 else _merge_parts(results)
    return data, SimpleNamespace(prompt_tokens=tok_in, completion_tokens=tok_out)


def _extract_one(text: str, model: str = MODEL):
    """Ein LLM-Durchlauf über einen (Teil-)Text. Retries once on an
    empty/unparseable response (deepseek occasionally returns null content);
    raises if it still fails so the caller can mark the protocol failed."""
    extra: dict = {}
    if "deepseek" in model:
        # Reasoning tokens can starve the output budget and yield null content.
        extra = {"extra_body": {"reasoning": {"enabled": False}}}
    messages = [{"role": "user", "content": _PROMPT.format(text=text[:MAX_INPUT_CHARS])}]
    last_err: Exception = ValueError("no response")
    for _ in range(2):
        resp = llm.chat_complete(
            model=model, _feature="minutes_extraction", temperature=0, response_format={"type": "json_object"},
            max_tokens=8000, messages=messages, **extra,
        )
        content = _strip_fences(resp.choices[0].message.content or "")
        if content:
            try:
                return json.loads(content), resp.usage
            except json.JSONDecodeError as exc:
                last_err = exc
        else:
            last_err = ValueError("empty LLM response")
    raise last_err
