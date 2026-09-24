"""Lotti prüft ihre Antwort, bevor sie gilt — die Selbstprüfung.

**Tims Idee (24.09.2026):** „Einen zweiten LLM-Pass, der die Antwort bewertet
… ist das eine gute Antwort auf die Frage, und falls nicht, anmerkt, warum …
und im besten Fall die Antwort korrigiert.“ Anlass war ein Befund an 36
Laienfragen zum Haushalt: keine falsche Zahl, aber rund die Hälfte der
Antworten half zu wenig — sie endeten mit „geht aus den Angaben nicht
hervor“, wo der Kontext wenigstens eine Einordnung erlaubt hätte.

**Zwei Stufen, die billige zuerst.**

1. :func:`rule_findings` — ohne Modell, in Millisekunden: Jede Zahl der
   Antwort steht im Kontext (dieselbe Logik wie die Fakten-Eval,
   :mod:`council.fakten_abgleich`), unter dem Jahr, unter dem sie dort steht;
   keine Wertung in der ersten Person; kein technischer Rest aus dem Prompt.
   Ein Befund hier heißt: neu schreiben, ohne erst ein zweites Modell zu
   fragen — die Regel IST das Urteil.
2. :func:`judge` — ein Prüfer-Modell aus einer ANDEREN Familie als die
   Antwort (Gemini gegen GPT-6 Luna), damit es nicht den eigenen Stil
   bevorzugt. Es bekommt denselben Prompt, den Lotti bekam, samt Frage und
   Antwort, und urteilt als JSON. Es schreibt nichts um.

**Genau ein zweiter Versuch** (:func:`revise`). Das Antwortmodell bekommt
seinen ersten Versuch und die Gründe und schreibt neu. Der zweite Versuch
durchläuft nur noch Stufe 1 — keine Schleife, keine zweite Prüferrunde. Hat
er dort MEHR Befunde als der erste, bleibt der erste (:func:`choose`).

**Fremdtext bleibt Daten.** Der Kontext, den der Prüfer liest, ist der fertige
Prompt aus :func:`council.assistant.explain_messages` — Element-Text und
Markierung stehen dort schon zwischen Marken und sind durch
:func:`kern.foreign_text.defuse` gelaufen. Die Gründe des Prüfers gehen
ihrerseits noch einmal durch den Filter, bevor sie im Prompt des zweiten
Versuchs stehen: Ein Prüfer, den eine Injektion im Kontext erreicht hat,
soll sie nicht als „Anmerkung“ weiterreichen können.

**Was Nutzer*innen davon sehen, kommt NICHT vom Modell.** Die Sätze unter
„Warum neu?“ stehen hier als Code (:data:`LAY_REASONS`), je Kategorie einer.
Die Begründung des Prüfers ist für das Antwortmodell geschrieben, nicht für
Laien — und sie könnte die Frage zitieren, die im Admin-Panel nicht stehen
soll.
"""
from __future__ import annotations

import json
import os
import re
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import Any

from council import fakten_abgleich as fa
from kern import llm, prompts
from kern.foreign_text import defuse

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

#: Was unter „Warum neu?“ steht — für Laien, ohne ein Wort vom Modell.
LAY_REASONS: dict[str, str] = {
    "frage_verfehlt": "Die erste Fassung ging an deiner Frage vorbei.",
    "kontext_ungenutzt": "Mir lagen Angaben dazu vor, die in der ersten Fassung fehlten.",
    "zu_vorsichtig": "Die erste Fassung hat abgewunken, obwohl ich mehr dazu sagen kann.",
    "unverstaendlich": "Die erste Fassung war zu sehr Amtsdeutsch.",
    "wertung": "Die erste Fassung hat bewertet — das ist nicht meine Aufgabe.",
    "falsche_angabe": "In der ersten Fassung stand eine Angabe, die ich nicht belegen kann.",
    "zahl_ohne_beleg": "In der ersten Fassung stand eine Zahl, die ich nicht belegen kann.",
    "jahr_vertauscht": "In der ersten Fassung stand eine Zahl beim falschen Jahr.",
    "technischer_rest": "In der ersten Fassung stand ein technischer Rest.",
}

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


@dataclass
class Result:
    """Was am Ende gilt — und was über den Weg dahin gespeichert wird."""

    answer_raw: str
    verdict: Verdict
    #: ``none`` (nichts neu geschrieben) | ``replaced`` | ``kept`` (der zweite
    #: Versuch war in Stufe 1 schlechter oder kam nicht, der erste bleibt).
    revision: str = "none"
    first_raw: str = ""
    second_raw: str | None = None
    cost_usd: float | None = None
    ms: int = 0

    @property
    def lay_reasons(self) -> list[str]:
        return lay_reasons(self.verdict.categories)


def lay_reasons(categories: list[str]) -> list[str]:
    """Die Sätze für „Warum neu?“, ohne Dubletten („wertung“ gibt es in beiden Stufen)."""
    aus: list[str] = []
    for k in categories:
        satz = LAY_REASONS.get(k)
        if satz and satz not in aus:
            aus.append(satz)
    return aus


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
# Neu schreiben
# --------------------------------------------------------------------------- #

def notes_for_revision(v: Verdict, findings: list[Finding]) -> str:
    """Die Gründe für den zweiten Versuch — durch den Fremdtext-Filter."""
    zeilen = [f"- {f.detail}" for f in findings]
    zeilen += [f"- {g}" for g in v.reasons]
    zeilen += [f"- Im Kontext steht dazu: {g}" for g in v.missing]
    if not zeilen:
        zeilen = [f"- {LAY_REASONS.get(k, k)}" for k in v.categories]
    return defuse("\n".join(zeilen))[0]


def revise(messages: list[dict], first_raw: str, notes: str, *,
           model: str, extra: dict | None = None, max_tokens: int = 350
           ) -> tuple[str, float | None]:
    """Der zweite Versuch mit dem Antwortmodell — ``(Text, Kosten)``.

    Als Fortsetzung desselben Gesprächs: Das Modell sieht seinen Prompt, seine
    erste Antwort und die Anmerkungen. Unter demselben Feature wie die erste
    Antwort (``assistant_explain``) — nur dafür gilt der EU-Weg von GPT-6
    Luna (``kern/llm.py::EU_ZUERST``), und es IST dieselbe Aufgabe.
    """
    folge = [*messages, {"role": "assistant", "content": first_raw},
             {"role": "user", "content": prompts.render("assistant_revision", notes=notes)}]
    resp = llm.chat_complete(model=model, _feature="assistant_explain", temperature=0.2,
                             max_tokens=max_tokens, messages=folge, **(extra or {}))
    return (resp.choices[0].message.content or "").strip(), _kosten(resp)


def _gleich(s: str) -> str:
    return s


def choose(first: str, second: str | None, context: str, question: str,
           strip: Callable[[str], str] = _gleich) -> str:
    """``replaced`` oder ``kept`` — bleibt der erste Versuch?

    Der zweite gilt, wenn er da ist und in Stufe 1 nicht MEHR Befunde hat als
    der erste. Gleich viele reichen: Der Prüfer hatte einen Grund, den Stufe 1
    nicht sieht.
    """
    if not second or not strip(second).strip():
        return "kept"
    vorher = len(rule_findings(strip(first), context, question))
    nachher = len(rule_findings(strip(second), context, question))
    return "kept" if nachher > vorher else "replaced"


def _summe(*werte: float | None) -> float | None:
    da = [w for w in werte if w is not None]
    return round(sum(da), 6) if da else None


def run(messages: list[dict], first_raw: str, *, question: str, answer_model: str,
        extra: dict | None = None, skip_judge: bool = False,
        strip: Callable[[str], str] = _gleich, judge_model: str | None = None,
        ) -> Iterator[dict]:
    """Der ganze Ablauf als Folge von Ereignissen — für Router UND Eval.

    Ereignisse (``event``): ``verdict`` (mit ``verdict``), ``revision_running``
    und zuletzt ``result`` (mit ``result``). Der Router macht daraus
    SSE-Rahmen, die Eval liest nur das letzte. Ein gemeinsamer Ablauf, weil
    zwei Fassungen derselben Reihenfolge auseinanderliefen.

    ``strip`` macht aus dem Rohtext den gezeigten (``split_next`` ohne die
    ``WEITER``-Zeile); geprüft wird immer der gezeigte. ``skip_judge``:
    Stufe 1 ja, Prüfer nein — für Antworten, die ohnehin ins Archiv
    weiterreichen.
    """
    t0 = time.perf_counter()
    context = messages[0]["content"] if messages else ""
    first = strip(first_raw)
    befunde = rule_findings(first, context, question)
    if befunde:
        v = Verdict("poor", "rules",
                    categories=list(dict.fromkeys(f.category for f in befunde)),
                    reasons=[f.detail[:REASON_CHARS] for f in befunde[:REASONS_MAX]])
    elif skip_judge:
        v = Verdict("good", "rules")
    else:
        v = judge(question, context, first, model=judge_model)
    yield {"event": "verdict", "verdict": v}
    if v.verdict != "poor":
        yield {"event": "result", "result": Result(
            first_raw, v, first_raw=first_raw, cost_usd=v.cost_usd,
            ms=round((time.perf_counter() - t0) * 1000))}
        return
    yield {"event": "revision_running"}
    try:
        second, kosten = revise(messages, first_raw, notes_for_revision(v, befunde),
                                model=answer_model, extra=extra)
    except Exception:  # noqa: BLE001 — dann bleibt die erste Antwort
        second, kosten = None, None
    wahl = choose(first_raw, second, context, question, strip)
    yield {"event": "result", "result": Result(
        second if wahl == "replaced" and second else first_raw, v, revision=wahl,
        first_raw=first_raw, second_raw=second, cost_usd=_summe(v.cost_usd, kosten),
        ms=round((time.perf_counter() - t0) * 1000))}
