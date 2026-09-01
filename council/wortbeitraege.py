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
import re
import os

from kern import llm, prompts
from council.protocols import _strip_fences

# Default Flash, nicht das Protokoll-Modell: im A/B auf ksinr 4066 lieferte
# gemini-2.5-flash MEHR Beiträge als deepseek-v4-pro (84 vs. 64, Fliegerhorst
# 12 vs. 5) bei 8× Tempo (58 s vs. 483 s) und geringeren Kosten.
MODEL = os.environ.get("COUNCIL_WORTBEITRAG_MODEL", "google/gemini-2.5-flash")

FENSTER = 48_000       # Zeichen je LLM-Fenster
UEBERLAPP = 3_000
ARTEN = {"speech", "inquiry", "citizen_question", "pledge"}
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
                 "content": prompts.render("speeches_extract", text=text)}]
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
    for part in _fenster(raw_text or ""):
        for r in _ein_fenster(part, model):
            if not isinstance(r, dict):
                continue
            text = str(r.get("text") or "").strip()
            if len(text) < 15:
                continue
            key = (str(r.get("speaker") or "").strip().lower(), text[:80].lower())
            if key in gesehen:
                continue
            gesehen.add(key)
            art = str(r.get("kind") or "speech").strip().lower()

            def field(name: str, max_len: int | None = None) -> str | None:
                value = str(r.get(name) or "").strip()
                if max_len and len(value) > max_len:
                    # NIE mitten im Wort abschneiden: Aus „Fraktion Bündnis
                    # Vernunft und Gerechtigkeit Oldenburg" wurde bei hartem
                    # Schnitt „…und Gerechtigk" — genau so stand es in einer
                    # KI-Antwort (Befund 12.08.). Lieber am letzten Leerzeichen
                    # kappen; die Grenzen sind ohnehin nur ein Schutz gegen
                    # Ausreißer, keine inhaltliche Vorgabe.
                    schnitt = value[:max_len]
                    leer = schnitt.rfind(" ")
                    value = (schnitt[:leer] if leer > max_len * 0.6 else schnitt).rstrip(" ,;-/")
                return value or None

            beitraege.append({
                "kind": art if art in ARTEN else "speech",
                "top": field("top", 120),
                "speaker": field("speaker", 80),
                # 40 war zu knapp: „BUND für Umwelt und Naturschutz
                # Deutschland, Kreisgruppe Stadt Oldenburg" hat 72 Zeichen.
                "party": field("party", 120),
                "text": text,
                "answer": field("answer"),
            })
    return beitraege


# ---- Seitengenaue Fundstellen (Tims Wunsch 18.08.) -------------------------
# Die Extraktion paraphrasiert („dicht am Wortlaut", aber kein Zitat) — der
# TEXT eines Beitrags lässt sich im PDF nicht wörtlich wiederfinden. Der
# SPRECHER schon: Namen stehen exakt wie im Protokoll. Der Name ist deshalb
# der Anker, markante Wörter der Paraphrase entscheiden zwischen mehreren
# Anker-Seiten (der Name steht auch in der Anwesenheitsliste). Gefaltet wird
# auf [a-z0-9äöüß] — das macht das Matching immun gegen die Trennungs-
# Artefakte der PDF-Textschicht („Ratjen -Damerau", „Neua u s-richtung").


#: Mindest-Zahl gemeinsamer Wörter, damit eine Anker-Seite als Fundstelle
#: gilt — darunter (und bei Gleichstand) lieber kein #page als ein falsches.
_SEITE_MIN_TREFFER = 2


def _seiten_falte(s: str) -> str:
    return re.sub(r"[^a-z0-9äöüß]", "", (s or "").lower())


def _anker(speaker: str | None) -> str | None:
    """Der Nachname als Suchanker — das letzte Namenswort ohne Titel/Anrede,
    gefaltet. Zu kurze Namen (< 4 Zeichen) ankern nicht zuverlässig."""
    toks = [t for t in re.split(r"[^0-9A-Za-zÄÖÜäöüß]+", speaker or "")
            if t and t.lower() not in {"dr", "prof", "dipl", "ing", "med",
                                       "herr", "frau", "ratsherr", "ratsfrau"}]
    if not toks:
        return None
    kandidat = _seiten_falte(toks[-1])
    return kandidat if len(kandidat) >= 4 else None


def _beste_seite(speaker: str | None, text: str, seiten_norm: list[str]) -> int | None:
    """1-basierte PDF-Seite des Beitrags — oder None, wenn nicht eindeutig."""
    anker = _anker(speaker)
    if not anker:
        return None
    kandidaten = [i for i, s in enumerate(seiten_norm) if anker in s]
    if not kandidaten:
        return None
    if len(kandidaten) == 1:
        return kandidaten[0] + 1
    # Mehrere Seiten nennen den Namen (Anwesenheitsliste!) — die markanten
    # Wörter der Paraphrase entscheiden. Die Folgeseite zählt halb mit, weil
    # Beiträge über den Seitenumbruch laufen.
    woerter = list(dict.fromkeys(
        w for w in re.findall(r"[0-9a-zäöüß]{5,}", (text or "").lower())))[:30]
    if not woerter:
        return None
    scores: list[tuple[float, int]] = []
    for i in kandidaten:
        naechste = seiten_norm[i + 1] if i + 1 < len(seiten_norm) else ""
        s = sum(1.0 for w in woerter if _seiten_falte(w) in seiten_norm[i])
        s += sum(0.5 for w in woerter if _seiten_falte(w) in naechste)
        scores.append((s, i))
    scores.sort(reverse=True)
    best_score, best_i = scores[0]
    if best_score < _SEITE_MIN_TREFFER:
        return None
    if len(scores) > 1 and scores[1][0] == best_score:
        return None  # Gleichstand — lieber kein Sprung als ein falscher
    return best_i + 1


def seiten_aufloesen(store, ksinr: int) -> int:
    """Fundstellen-Seiten für alle Beiträge eines Protokolls nachtragen.
    Läuft nach der Extraktion (und im Backfill); ohne gespeicherte
    Seiten-Offsets (Altbestand) passiert schlicht nichts."""
    grundlage = store.protokoll_seiten_grundlage(ksinr)
    if grundlage is None:
        return 0
    raw, offsets = grundlage
    seiten_norm = [_seiten_falte(raw[offsets[i]: offsets[i + 1] if i + 1 < len(offsets) else len(raw)])
                   for i in range(len(offsets))]
    gesetzt = 0
    for wb in store.wortbeitraege_ohne_seite(ksinr):
        page = _beste_seite(wb.get("speaker"), wb.get("text") or "", seiten_norm)
        if page is not None:
            store.set_wortbeitrag_seite(wb["id"], page)
            gesetzt += 1
    return gesetzt
