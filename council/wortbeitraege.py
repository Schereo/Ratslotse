"""Wortbeiträge aus Sitzungsprotokollen extrahieren (Task 16).

Die Substanz der Ratsdebatten — Redebeiträge, „Anfragen und Anregungen",
Einwohnerfragestunde, Zusagen der Verwaltung — steht NICHT in den
Beschlusstexten (dort oft nur „wird zur Kenntnis genommen"), sondern im
Fließtext der Protokolle. Ein LLM-Pass je Protokoll macht sie durchsuchbar;
der Fliegerhorst-Fall (14 einschlägige Beschlüsse, Substanz unauffindbar)
ist der Beleg, warum.

Kein Re-Download: Es wird der gespeicherte ``raw_text`` gelesen. Lange
Protokolle laufen in überlappenden Fenstern durch dasselbe Prompt; Dubletten
an den Nahtstellen werden über (sprecher, text-Anfang) zusammengelegt.
"""
from __future__ import annotations

import json
import os

from kern import llm, prompts
from council.protocols import _strip_fences

# Default Flash, nicht das Protokoll-Modell: im A/B auf ksinr 4066 lieferte
# gemini-2.5-flash MEHR Beiträge als deepseek-v4-pro (84 vs. 64, Fliegerhorst
# 12 vs. 5) bei 8× Tempo (58 s vs. 483 s) und geringeren Kosten.
MODEL = os.environ.get("COUNCIL_WORTBEITRAG_MODEL", "google/gemini-2.5-flash")

FENSTER = 48_000       # Zeichen je LLM-Fenster
UEBERLAPP = 3_000
ARTEN = {"rede", "anfrage", "einwohnerfrage", "zusage"}
# Ab dieser Fensterlänge ist ein leeres Ergebnis fast sicher ein Provider-
# Aussetzer (ein ganzes Sitzungsprotokoll ohne einen einzigen Wortbeitrag
# gibt es praktisch nicht) → einmal neu versuchen. Kleine Restfenster am
# Protokollende dürfen dagegen ehrlich leer sein.
LEER_VERDAECHTIG_AB = 20_000


def _fenster(text: str) -> list[str]:
    if len(text) <= FENSTER:
        return [text]
    teile = []
    start = 0
    while start < len(text):
        teile.append(text[start:start + FENSTER])
        start += FENSTER - UEBERLAPP
    return teile


def _array_bergen(content: str) -> list | None:
    """Abgeschnittenes JSON-Array bis zum letzten vollständigen Objekt retten
    (Modelle laufen bei langen Protokollen ins Token-Limit). None wenn nichts
    Brauchbares übrig bleibt."""
    cut = content.rfind("},")
    if cut == -1:
        return None
    try:
        data = json.loads(content[:cut + 1] + "]")
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, list) and data else None


def _ein_fenster(text: str, model: str) -> list[dict]:
    extra: dict = {}
    if "deepseek" in model:
        # Reasoning frisst dort das Output-Budget und liefert null content.
        # (Bei Gemini gemessen wirkungslos — Flag dort bewusst weggelassen.)
        extra = {"extra_body": {"reasoning": {"enabled": False}}}
    messages = [{"role": "user",
                 "content": prompts.render("wortbeitraege_extract", text=text)}]
    last_err: Exception = ValueError("no response")
    for versuch in range(2):
        resp = llm.chat_complete(
            model=model, _feature="wortbeitraege", temperature=0,
            max_tokens=16000, messages=messages, **extra,
        )
        # choices kann bei Provider-Fehlern/Content-Filter null sein — der
        # nackte [0]-Zugriff riss im Massenlauf aus der Retry-Schleife aus
        # (ksinr 4299/4301, 10.08.). Leer → normaler Retry-Pfad.
        choices = getattr(resp, "choices", None) or []
        content = _strip_fences(choices[0].message.content or "") if choices else ""
        if content:
            try:
                data = json.loads(content)
                # Manche Modelle wickeln das Array in ein Objekt.
                if isinstance(data, dict):
                    data = next((v for v in data.values() if isinstance(v, list)), [])
                if not isinstance(data, list):
                    data = []
                if not data and len(text) >= LEER_VERDAECHTIG_AB and versuch == 0:
                    # Valides [] auf ein volles Fenster: fast sicher ein
                    # Aussetzer (ksinr 4417 lieferte real 80 Beiträge).
                    last_err = ValueError("empty array for large window")
                    continue
                return data
            except json.JSONDecodeError as exc:
                if versuch == 1:
                    # Letzter Versuch abgeschnitten: lieber die vollständigen
                    # Objekte retten als das ganze Fenster zu verlieren.
                    gerettet = _array_bergen(content)
                    if gerettet is not None:
                        return gerettet
                last_err = exc
        else:
            last_err = ValueError("empty LLM response")
    raise last_err


def extract_wortbeitraege(raw_text: str, model: str = MODEL) -> list[dict]:
    """Alle Beiträge eines Protokolls, Fenster-übergreifend dedupliziert und
    auf das erwartete Schema geprüft (unbekannte Arten → 'rede')."""
    gesehen: set[tuple] = set()
    beitraege: list[dict] = []
    for teil in _fenster(raw_text or ""):
        for r in _ein_fenster(teil, model):
            if not isinstance(r, dict):
                continue
            text = str(r.get("text") or "").strip()
            if len(text) < 15:
                continue
            schluessel = (str(r.get("sprecher") or "").strip().lower(), text[:80].lower())
            if schluessel in gesehen:
                continue
            gesehen.add(schluessel)
            art = str(r.get("art") or "rede").strip().lower()

            def feld(name: str, max_len: int | None = None) -> str | None:
                wert = str(r.get(name) or "").strip()
                if max_len and len(wert) > max_len:
                    # NIE mitten im Wort abschneiden: Aus „Fraktion Bündnis
                    # Vernunft und Gerechtigkeit Oldenburg" wurde bei hartem
                    # Schnitt „…und Gerechtigk" — genau so stand es in einer
                    # KI-Antwort (Befund 12.08.). Lieber am letzten Leerzeichen
                    # kappen; die Grenzen sind ohnehin nur ein Schutz gegen
                    # Ausreißer, keine inhaltliche Vorgabe.
                    schnitt = wert[:max_len]
                    leer = schnitt.rfind(" ")
                    wert = (schnitt[:leer] if leer > max_len * 0.6 else schnitt).rstrip(" ,;-/")
                return wert or None

            beitraege.append({
                "art": art if art in ARTEN else "rede",
                "top": feld("top", 120),
                "sprecher": feld("sprecher", 80),
                # 40 war zu knapp: „BUND für Umwelt und Naturschutz
                # Deutschland, Kreisgruppe Stadt Oldenburg" hat 72 Zeichen.
                "partei": feld("partei", 120),
                "text": text,
                "antwort": feld("antwort"),
            })
    return beitraege
