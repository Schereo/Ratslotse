"""Lottis Selbstprüfung — eine stille Stichprobe über ihre Antworten.

**Tims Idee (24.09.2026):** „Einen zweiten LLM-Pass, der die Antwort bewertet
… ist das eine gute Antwort auf die Frage, und falls nicht, anmerkt, warum …“
Gebaut war sie zuerst als Prüfung VOR der Anzeige, mit Neuschreiben und
„Warum neu?“ im Fenster (Commit ca759f9c). Gemessen an der Fakten-Eval
(178 Fälle, nach L1+L2) änderte das an der ok-Quote nichts: 4 Antworten
ersetzt, 1 davon besser, 163 → 163 ok — bei +1,7 s im Median und dem
2,5-Fachen der Kosten (``docs/lotti-selbstpruefung.md``). Tims Regel für
diesen Fall: eine stille Stichprobe.

**Was sie jetzt tut.** Für einen Anteil der Erklärungen
(:data:`ANTEIL`, ``COUNCIL_ASSISTANT_PRUEFER_ANTEIL``, Vorgabe 10 %) prüft
der Server NACH der Antwort — die Person wartet nicht, sieht nichts, und
nichts wird ersetzt. Das Urteil landet in ``assistant_checks`` und im
Admin-Reiter „Lotti“: Anteil beanstandet je Seite und die häufigsten Gründe.

**Zwei Stufen, die billige zuerst.**

1. :func:`rule_findings` — ohne Modell: Jede Zahl der Antwort steht im
   Kontext (dieselbe Logik wie die Fakten-Eval, :mod:`council.fakten_abgleich`),
   unter dem Jahr, unter dem sie dort steht; keine Wertung in eigener Stimme;
   kein Rest aus dem Prompt. Ein Befund hier IST das Urteil.
2. :func:`judge` — ein Prüfer-Modell aus einer ANDEREN Familie als die
   Antwort (Gemini gegen GPT-6 Luna), damit es nicht den eigenen Stil
   bevorzugt. Es bekommt denselben Prompt, den Lotti bekam, samt Frage und
   Antwort, und urteilt als JSON.

**Fremdtext bleibt Daten.** Der Kontext, den der Prüfer liest, ist der fertige
Prompt aus :func:`council.assistant.explain_messages` — Element-Text und
Markierung stehen dort zwischen Marken und sind durch
:func:`kern.foreign_text.defuse` gelaufen; der Prüfer-Prompt rahmt alles
noch einmal als Daten.
"""
from __future__ import annotations

import json
import os
import random
import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from council import fakten_abgleich as fa
from kern import llm, prompts

#: Welcher Anteil der Erklärungen mit Modell geprüft wird (0 bis 1). Eine
#: Prüfung kostet rund 0,28 Cent — das Dreifache der Antwort selbst (Messung
#: 24.09.2026); jede zehnte reicht für „wo hakt es?“ je Seite.
ANTEIL = float(os.environ.get("COUNCIL_ASSISTANT_PRUEFER_ANTEIL", "0.1"))

#: Das Prüfer-Modell. Bewusst eine andere Familie als die Antwort (GPT-6
#: Luna, ``COUNCIL_ASSISTANT_MODEL``). Kalibrierung vom 24.09.2026
#: (``eval/run_selbstpruefung.py``, Tabelle in ``docs/lotti-selbstpruefung.md``):
#: Gemini 3 Flash ist das einzige, das an beiden Sätzen VOLL gemessen ist —
#: p50 1,4 s, 0,24 Cent je Prüfung. Gemini 3.5 Flash (im Entwurf genannt)
#: kostete 1,8 Cent und brauchte p50 7,6–8,2 s, und fand in der Stichprobe
#: (15 + 15 Fälle) nicht mehr: 1 von 15 bekannten Mängeln. Gemini 3.5 Flash
#: Lite fand von 7 zu vorsichtigen Antworten keine.
MODEL = os.environ.get("COUNCIL_ASSISTANT_PRUEFER_MODEL", "google/gemini-3-flash-preview")
#: Unter diesem Namen stehen die Prüfer-Aufrufe in ``llm_usage`` (Admin →
#: Kosten). Trägt Nutzereingaben (die Frage), also gilt ZDR — Gemini hat
#: ZDR-Anbieter, anders als GPT-6 Luna (``kern/llm.py::ZDR_VERZICHT``).
FEATURE = "assistant_check"
#: Das Urteil ist kurz (ein JSON mit höchstens drei Gründen). Denkende
#: Modelle bekommen ihren Boden aus ``llm.MODEL_PARAMS``.
MAX_TOKENS = 500
#: Länger wartet eine Antwort nicht auf ihr Urteil. Danach gilt sie
#: ungeprüft — die Person hat den Text da schon gelesen.
TIMEOUT_S = 20.0

#: Die Kategorien, die der Prüfer vergeben darf, und die Stufe-1-Befunde.
#: Eine Liste, weil die Statistik im Admin-Panel danach zählt.
JUDGE_CATEGORIES = ("frage_verfehlt", "kontext_ungenutzt", "zu_vorsichtig",
                    "unverstaendlich", "wertung", "falsche_angabe")
RULE_CATEGORIES = ("zahl_ohne_beleg", "jahr_vertauscht", "wertung", "technischer_rest")
#: Kategorien, die allein KEIN Neuschreiben auslösen — sie werden nur
#: gezählt. Gemessen am 24.09.2026 an 101 guten Antworten der Fakten-Eval:
#: 10 der 13 Fehlalarme von Gemini 3 Flash waren „unverständlich“ — Antworten
#: mit „Aufwendungen“ oder „Zuschussbedarf“, die das Wort im selben Satz
#: erklärten. Ohne diese Kategorie als Auslöser: 1 Fehlalarm von 101.
NOTE_ONLY = frozenset({"unverstaendlich"})

#: Wie viele Gründe höchstens gespeichert und weitergereicht werden, und wie
#: lang jeder sein darf. Der Prüfer soll kurz sein; der Deckel ist die
#: zweite Bremse, damit kein Absatz Kontext in der Tabelle landet.
REASONS_MAX = 3
REASON_CHARS = 160


@dataclass
class Finding:
    """Ein Befund aus Stufe 1."""

    category: str
    detail: str


@dataclass
class Verdict:
    """Das Urteil — aus Stufe 1 (``stage="rules"``) oder vom Prüfer (``"model"``)."""

    verdict: str  # good | poor | unknown
    stage: str
    categories: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    understandable: bool | None = None
    model: str | None = None
    cost_usd: float | None = None
    ms: int = 0


# --------------------------------------------------------------------------- #
# Stufe 1 — ohne Modell
# --------------------------------------------------------------------------- #

#: Wertung in Lottis EIGENER Stimme. Nicht „empfiehlt“ allein: „Die
#: Verwaltung empfiehlt, …“ ist Inhalt, den Lotti wiedergeben soll.
_WERTUNG = re.compile(
    r"\bich (?:empfehle|finde|meine|würde (?:empfehlen|raten))\b"
    r"|\bmeiner (?:meinung|ansicht) nach\b"
    r"|\b(?:zum glück|glücklicherweise|erfreulicherweise|bedauerlicherweise)\b"
    r"|\b(?:die stadt|der rat|oldenburg|man) (?:sollte|müsste)\b"
    r"|\bdas ist (?:gut|schlecht|richtig|falsch|vernünftig|besorgniserregend|bedenklich|"
    r"skandalös|vorbildlich|lobenswert)\b",
    re.IGNORECASE)

#: Was aus dem Prompt in die Antwort gerutscht sein kann. Die Marke
#: „WEITER:“ nimmt ``split_next`` nur als LETZTE Zeile heraus; steht sie
#: mittendrin, bliebe sie stehen.
_REST = re.compile(
    r"WEITER:|FOLGEFRAGEN:|<<<|^(?:ELEMENT|FRAGE|MARKIERUNG|KONTEXT)\s*$"
    r"|\[Anweisung an ein KI-System|\[\d{1,5}\]",
    re.MULTILINE)

#: Unterhalb davon prüft Stufe 1 keine Jahreszuordnung: Kleine Beträge
#: („4,04 € je Einwohner“) stehen im Kontext oft ohne eigenes Jahr, und ein
#: Fehlalarm kostet einen ganzen zweiten Antwortversuch.
_JAHR_AB_EURO = 100_000


def _year_mismatches(answer: str, context: str) -> list[str]:
    """Beträge, die die Antwort einem Jahr zuordnet, unter dem sie im Kontext NIE steht.

    Zählt nur, wenn jede Fundstelle im Kontext ein Jahr trägt — steht die Zahl
    irgendwo ohne Jahr, lässt sich nichts sagen. Das ist genau der Fehler aus
    dem Faktencheck vom 23.09.2026: die Schuldenarten 2025, als 2024 gelesen.
    """
    kz = [z for z in fa.zahlen(context) if z.art == "€"]
    if not kz:
        return []
    kl = fa.zeilen(context)
    al = fa.zeilen(answer)
    aus = []
    for z in fa.zahlen(answer):
        if z.art != "€" or abs(z.wert) < _JAHR_AB_EURO:
            continue
        jahre_a = fa.jahre_der_zahl(al, z, satz=True)
        if not jahre_a:
            continue
        treffer = [k for k in kz if fa.passt(z, k.wert)]
        if not treffer:
            continue  # das meldet `zahl_ohne_beleg`
        jahre_k = [fa.jahre_der_zahl(kl, k) for k in treffer]
        if any(not j for j in jahre_k) or any(j & jahre_a for j in jahre_k):
            continue
        alle: set[int] = set().union(*jahre_k)
        aus.append(f"{z.text} steht bei {', '.join(map(str, sorted(jahre_a)))}, "
                   f"im Kontext bei {', '.join(map(str, sorted(alle)))}")
    return aus


def rule_findings(answer: str, context: str, question: str = "") -> list[Finding]:
    """Stufe 1: was sich ohne Modell an der Antwort feststellen lässt."""
    aus: list[Finding] = []
    for z in fa.erfundene_zahlen(answer, context, question):
        aus.append(Finding("zahl_ohne_beleg", f"{z} steht nicht im Kontext"))
    for text in _year_mismatches(answer, context):
        aus.append(Finding("jahr_vertauscht", text))
    m = _WERTUNG.search(answer)
    if m:
        aus.append(Finding("wertung", f"„{m.group(0)}“ ist eine Wertung"))
    m = _REST.search(answer)
    if m:
        aus.append(Finding("technischer_rest", f"„{m.group(0).strip()}“ gehört nicht in die Antwort"))
    return aus


# --------------------------------------------------------------------------- #
# Stufe 2 — der Prüfer
# --------------------------------------------------------------------------- #

def _kurz(texte: Any, question: str) -> list[str]:
    """Gründe säubern: kurze Zeichenketten, ohne Zitat der Frage.

    **Warum die Frage herausfällt:** Die Gründe landen im Admin-Panel auch
    für Konten OHNE Einwilligung in die Gesprächsspeicherung. Der Prompt
    verbietet das Zitieren; das hier ist der Riegel, falls das Modell es
    trotzdem tut — drei Wörter der Frage am Stück werden zu „…“.
    """
    if not isinstance(texte, list):
        texte = [texte] if isinstance(texte, str) else []
    worte = re.findall(r"[\wäöüß]+", (question or "").lower())
    fenster = {tuple(worte[i:i + 3]) for i in range(len(worte) - 2)}
    aus = []
    for t in texte[:REASONS_MAX]:
        if not isinstance(t, str) or not t.strip():
            continue
        s = " ".join(t.split())
        for f in fenster:
            s = re.sub(r"\b" + r"\W+".join(map(re.escape, f)) + r"\b", "…", s,
                       flags=re.IGNORECASE)
        aus.append(s[:REASON_CHARS])
    return aus


def parse_verdict(roh: str, question: str = "") -> Verdict | None:
    """Das JSON des Prüfers — ``None``, wenn es sich nicht lesen lässt."""
    m = re.search(r"\{.*\}", roh or "", re.S)
    if not m:
        return None
    try:
        d = json.loads(m.group(0))
    except ValueError:
        return None
    if not isinstance(d, dict):
        return None
    urteil = str(d.get("urteil", "")).strip().lower()
    if urteil not in ("gut", "mangelhaft"):
        return None
    roh_k = d.get("kategorien")
    kategorien = [k for k in (roh_k if isinstance(roh_k, list) else []) if k in JUDGE_CATEGORIES]
    verstaendlich = str(d.get("verstaendlich", "")).strip().lower()
    if urteil == "gut":
        return Verdict("good", "model", understandable={"ja": True, "nein": False}.get(verstaendlich))
    if kategorien and set(kategorien) <= NOTE_ONLY:
        # Nur „unverständlich“: gezählt, nicht neu geschrieben (NOTE_ONLY).
        return Verdict("good", "model", categories=list(dict.fromkeys(kategorien)),
                       reasons=_kurz(d.get("gruende"), question),
                       understandable={"ja": True, "nein": False}.get(verstaendlich))
    if not kategorien:
        # Ein Urteil ohne Kategorie lässt sich weder zählen noch Laien
        # erklären. Dann trägt es die allgemeinste: an der Frage vorbei.
        kategorien = ["frage_verfehlt"]
    return Verdict(
        verdict="poor", stage="model", categories=list(dict.fromkeys(kategorien)),
        reasons=_kurz(d.get("gruende"), question), missing=_kurz(d.get("fehlt"), question),
        understandable={"ja": True, "nein": False}.get(verstaendlich),
    )


def _kosten(resp: Any) -> float | None:
    try:
        roh = getattr(getattr(resp, "usage", None), "cost", None)
        return float(roh) if roh is not None else None
    except (TypeError, ValueError):
        return None


def judge(question: str, context: str, answer: str, *, model: str | None = None) -> Verdict:
    """Stufe 2: das Urteil des Prüfers. Wirft nie — im Zweifel ``unknown``."""
    model = model or MODEL
    t0 = time.perf_counter()
    prompt = prompts.render("assistant_check", context=context,
                            question=question or "(keine eigene Frage — erklär das Gezeigte)",
                            answer=answer)
    try:
        resp = llm.chat_complete(
            model=model, _feature="assistant_check", temperature=0, max_tokens=MAX_TOKENS,
            response_format={"type": "json_object"}, timeout=TIMEOUT_S,
            messages=[{"role": "user", "content": prompt}])
        roh = (resp.choices[0].message.content or "").strip()
        kosten = _kosten(resp)
    except Exception:  # noqa: BLE001 — ein Prüfer-Ausfall ist kein Antwort-Ausfall
        return Verdict("unknown", "model", model=model,
                       ms=round((time.perf_counter() - t0) * 1000))
    v = parse_verdict(roh, question) or Verdict("unknown", "model")
    v.model, v.cost_usd = model, kosten
    v.ms = round((time.perf_counter() - t0) * 1000)
    return v


# --------------------------------------------------------------------------- #
# Die Stichprobe
# --------------------------------------------------------------------------- #

def gezogen(anteil: float | None = None, zufall: Callable[[], float] = random.random) -> bool:
    """Fällt diese Antwort in die Stichprobe?"""
    a = ANTEIL if anteil is None else anteil
    return a > 0 and zufall() < a


def check(question: str, context: str, answer: str, *, skip_judge: bool = False,
          judge_model: str | None = None) -> Verdict:
    """Stufe 1, und nur ohne Befund dort der Prüfer. Wirft nie.

    ``skip_judge``: Antworten, die ins Archiv weiterreichen, sind absichtlich
    kurz — das Archiv antwortet gleich darunter. Dort nur Stufe 1.
    """
    t0 = time.perf_counter()
    try:
        befunde = rule_findings(answer, context, question)
    except Exception:  # noqa: BLE001 — eine Regel, die an einem Text scheitert, ist kein Urteil
        befunde = []
    if befunde:
        return Verdict("poor", "rules",
                       categories=list(dict.fromkeys(f.category for f in befunde)),
                       reasons=[f.detail[:REASON_CHARS] for f in befunde[:REASONS_MAX]],
                       ms=round((time.perf_counter() - t0) * 1000))
    if skip_judge:
        return Verdict("good", "rules", ms=round((time.perf_counter() - t0) * 1000))
    return judge(question, context, answer, model=judge_model)
