"""Was nur ein Sprachmodell aus den Texten der Stadt heraussuchen kann (Plan „Pläne der Stadt“).

Drei Aufgaben, alle über öffentliche Ratsdokumente, keine mit Nutzereingabe:

- :func:`measure_status` — der Stand je Maßnahme aus einem Fließtext-Bericht
  (Mobilitätsplan, § 1.3 Form d).

Das Modell **sucht heraus, es urteilt nicht frei**: Jede Angabe trägt ein
wörtliches Zitat, und :func:`verified` wirft alles weg, dessen Zitat nicht
genau so im Text steht. Was übrig bleibt, wird als geprüfte Datei eingecheckt
(``scripts/plan_modell.py``) — auf dev laufen keine Crons, und so bleibt das
Ergebnis im PR sichtbar und ohne Modell nachprüfbar.
"""
from __future__ import annotations

import json
import os
import re

from kern import llm, usage

#: Luna: günstig, und für Dokumente ohne Nutzereingabe zulässig (``llm.OHNE_NUTZEREINGABE``).
MODEL = os.environ.get("COUNCIL_PLAN_MODEL") or "openai/gpt-6-luna"
STATUS = ("open", "started", "in_progress", "done", "paused")


_PRIVATE_USE = re.compile("[\ue000-\uf8ff]")


def squash(text: str) -> str:
    """Leerraum vereinheitlichen — das Zitat des Modells muss danach WÖRTLICH im Text stehen.
    Aufzählungszeichen aus dem privaten Unicode-Bereich (PDF-Schriften) fallen weg: Sie sind
    kein Wort der Stadt und stünden im Zitat als leeres Kästchen."""
    return " ".join(_PRIVATE_USE.sub(" ", text or "").split())


def cost_usd(response, model: str) -> float:
    """Kosten eines Aufrufs aus den gezählten Tokens und der Preisliste (``kern.usage.PRICES``)."""
    counted = getattr(response, "usage", None)
    price_in, price_out = usage.PRICES.get(model, (0.0, 0.0))
    return ((getattr(counted, "prompt_tokens", 0) or 0) * price_in
            + (getattr(counted, "completion_tokens", 0) or 0) * price_out) / 1_000_000


def _json(response) -> dict:
    content = (response.choices[0].message.content or "").strip()
    content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content)
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


_STATUS_PROMPT = """Du liest einen Sachstandsbericht der Stadtverwaltung Oldenburg zu einem Plan und suchst \
heraus, was er über einzelne Maßnahmen des Plans sagt.

Maßnahmen (Kennung: Titel):
{measures}

Bericht:
<<<
{report}
>>>

Antworte nur mit JSON: {{"results": [{{"code": "…", "quote": "…", "status_words": "…", "status": "…"}}]}}

Regeln:
1. Nimm eine Maßnahme nur auf, wenn der Bericht ausdrücklich etwas über GENAU diese Maßnahme sagt — \
über ihren Namen, ihren Ort oder eine eindeutige Bezeichnung. Im Zweifel weglassen: Eine fehlende \
Angabe ist richtig, eine falsche Zuordnung ist ein Fehler.
2. quote: ein wörtlicher, zusammenhängender Ausschnitt aus dem Bericht, höchstens 300 Zeichen, der den \
Stand dieser Maßnahme belegt. Nichts ändern, nichts auslassen, nichts ergänzen.
3. status_words: höchstens sechs aufeinanderfolgende Wörter AUS dem Zitat, die den Stand benennen \
(zum Beispiel „umgesetzt“ oder „Vergabe von Planungsaufträgen“).
4. status: open = noch nicht begonnen · started = geplant, vorbereitet, in Abstimmung, vorgesehen · \
in_progress = wird umgesetzt oder ist teilweise umgesetzt · done = umgesetzt, abgeschlossen · \
paused = zurückgestellt oder eingestellt.
5. Eine Aussage über ein ganzes Teilkonzept gilt nur für die Maßnahme, die dieses Teilkonzept IST."""


def measure_status(measures: list[dict], report: str, model: str = MODEL) -> tuple[list[dict], float]:
    """Stand je Maßnahme aus einem Fließtext-Bericht. Genau ein Modellaufruf; zurück kommt nur,
    was :func:`verified` übersteht, dazu die Kosten des Aufrufs in US-Dollar."""
    text = squash(report)
    prompt = _STATUS_PROMPT.format(measures="\n".join(f"{m['code']}: {m['title']}" for m in measures), report=text)
    response = llm.chat_complete(model=model, _feature="plan_measure_status", temperature=0,
                                 response_format={"type": "json_object"}, max_tokens=6000,
                                 messages=[{"role": "user", "content": prompt}])
    return verified(_json(response).get("results") or [], text, {m["code"] for m in measures}), cost_usd(response, model)


def verified(results: list, text: str, codes: set[str]) -> list[dict]:
    """Nur was sich ohne Modell belegen lässt: bekannte Kennung, bekannte Stufe, das Zitat steht
    wörtlich im Bericht, die Statuswörter stehen im Zitat. Je Kennung die erste Angabe."""
    out: dict[str, dict] = {}
    for r in results:
        if not isinstance(r, dict):
            continue
        code, quote = str(r.get("code") or ""), squash(str(r.get("quote") or ""))
        words, status = squash(str(r.get("status_words") or "")), r.get("status")
        if code not in codes or code in out or status not in STATUS:
            continue
        if not quote or len(quote) > 320 or quote not in text or not words or words not in quote or len(words.split()) > 6:
            continue
        out[code] = {"code": code, "status_raw": words, "status_norm": status, "quote": quote}
    return [out[c] for c in sorted(out)]
