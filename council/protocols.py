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

import requests
import pypdf
from bs4 import BeautifulSoup

from nwz import llm

BASE = "https://buergerinfo.oldenburg.de"
MODEL = os.environ.get("COUNCIL_PROTOCOL_MODEL", "deepseek/deepseek-v4-pro")
# Protocols run long; cap the input we feed the model (chars ≈ 0.3 tokens).
MAX_INPUT_CHARS = int(os.environ.get("COUNCIL_PROTOCOL_MAX_CHARS", "60000"))

logger = logging.getLogger("council.protocols")

_session = requests.Session()
_session.headers["User-Agent"] = "Mozilla/5.0"


def find_protocol(ksinr: int) -> dict | None:
    """Return {url, document_id, label} for the public protocol PDF of a session,
    or None if none is published yet."""
    r = _session.get(f"{BASE}/si0057.php", params={"__ksinr": ksinr}, timeout=20)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    for a in soup.find_all("a", href=True):
        if "getfile.php" not in a["href"]:
            continue
        label = (a.get_text(" ", strip=True) + " " + a.get("title", "")).lower()
        if re.search(r"protokoll|niederschrift", label) and "öffentlich" in label:
            href = a["href"] if a["href"].startswith("http") else f"{BASE}/{a['href'].lstrip('/')}"
            m = re.search(r"id=(\d+)", href)
            return {
                "url": href,
                "document_id": int(m.group(1)) if m else None,
                "label": a.get_text(" ", strip=True),
            }
    return None


def extract_pdf_text(url: str) -> tuple[str, int]:
    """Download a PDF and return (text, n_pages)."""
    r = _session.get(url, timeout=45)
    r.raise_for_status()
    reader = pypdf.PdfReader(io.BytesIO(r.content))
    text = "\n".join(p.extract_text() or "" for p in reader.pages)
    return text, len(reader.pages)


_PROMPT = """Du extrahierst strukturierte Daten aus dem Protokoll einer Stadtrats- oder \
Ausschusssitzung in Oldenburg. Antworte mit NUR JSON in genau dieser Form:

{{
  "protocol_nr": "z.B. AFB 01/26 oder null",
  "session_start": "HH:MM oder null",
  "session_end": "HH:MM oder null",
  "attendance": [
    {{"name": "Vor- und Nachname", "party": "Fraktion oder Gruppe (z.B. SPD, CDU, Verwaltung)", "role": "vorsitz|mitglied|verwaltung|protokoll|gast", "note": "z.B. 'bis TOP 20.2' oder null"}}
  ],
  "decisions": [
    {{
      "item_number": "TOP-Nummer wie '9.4'",
      "title": "TOP-Titel",
      "beschluss": "Wortlaut des gefassten Beschlusses (Endergebnis), sinngemäß gekürzt",
      "outcome": "angenommen|abgelehnt|vertagt|zur_kenntnis|kein_beschluss",
      "vote": "einstimmig|mehrheitlich oder null",
      "gegenstimmen": Zahl oder null,
      "enthaltungen": Zahl oder null,
      "factions": ["Fraktionen, die zu diesem TOP Anträge/Änderungslisten stellten, sonst leer"],
      "vorlage_nr": "Vorlagennummer wie '26/0042' oder null",
      "raw_result": "der Original-Abstimmungssatz des Endergebnisses",
      "sub_votes": [
        {{
          "description": "WAS beantragt wurde — Antragsart, Fraktion UND inhaltliches Anliegen, \
z.B. 'Änderungsantrag der BSW-Fraktion: Streichung des Punktes 8 (Umweltzone)'",
          "outcome": "angenommen|abgelehnt|vertagt",
          "vote": "einstimmig|mehrheitlich oder null",
          "gegenstimmen": Zahl oder null,
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
- "outcome" = "zur_kenntnis", wenn nur ein Bericht zur Kenntnis genommen wurde.
- "sub_votes": JEDE einzelne Teilabstimmung (z.B. über Änderungslisten/Anträge \
einzelner Fraktionen) als eigenen Eintrag. Wenn es keine Teilabstimmungen gab: leere Liste.
- "description" der sub_votes: Nenne das inhaltliche Anliegen, nicht nur die Antragsart. \
Steht im Protokoll, WAS der Antrag ändern/erreichen sollte, gehört das hinein (sinngemäß \
gekürzt). Nur wenn das Protokoll den Inhalt wirklich nicht nennt, reicht \
'Änderungsantrag der X-Fraktion'.
- Das Haupt-"outcome"/"vote"/"beschluss" beschreibt das ENDergebnis des TOP, die \
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


def extract_protocol(text: str, model: str = MODEL):
    """Run the LLM extraction. Returns (data_dict, usage). Retries once on an
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
            model=model, _feature="protokoll_extraktion", temperature=0, response_format={"type": "json_object"},
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
