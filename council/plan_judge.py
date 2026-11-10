"""Was nur ein Sprachmodell aus den Texten der Stadt heraussuchen kann (Plan „Pläne der Stadt“).

Drei Aufgaben, alle über öffentliche Ratsdokumente, keine mit Nutzereingabe:

- :func:`measure_status` — der Stand je Maßnahme aus einem Fließtext-Bericht
  (Mobilitätsplan, § 1.3 Form d).
- :func:`judge_links` — ob eine Vorlage, die einen Plan beim Namen nennt, ihn
  umsetzt oder nur erwähnt (Phase 4, Teil 2).
- :func:`classify_mandates` und :func:`find_follow_up` — die Gegenprobe für
  „Ratsauftrag ohne Folge“ (§ 3.5, Art 2).

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

from council import plans as register
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


# ── Vorlagen, die einen Plan beim Namen nennen (Phase 4, Teil 2) ───────────

#: Woran eine Vorlage den Plan beim Namen nennt. Von Hand gesetzt — und bewusst
#: nur für Pläne, deren Name eindeutig genug ist. „ISEK“ heißt in Oldenburg auch
#: das Entwicklungskonzept eines Sanierungsgebiets; das Modell kennt den Fall („none“).
NAME_PATTERNS: dict[str, str] = {
    "klimaschutzplan_2035": r"Klimaschutzplan",
    "mobilitaetsplan_2030": r"Mobilitätsplan|Teilkonzept Radverkehr",
    "waermeplan": r"Wärmeplan(?!ung)|[Kk]ommunale[nr]? Wärmeplanung",
    "ernaehrungsstrategie": r"Ernährungsstrategie",
    "isek_2035": r"\bISEK\b|Integrierte[sn]? Stadtentwicklungskonzept",
    "eek": r"Einzelhandelsentwicklungskonzept|\bEEKs?\b",
    "laermaktionsplan": r"Lärmaktionsplan",
    "masterplan_stadtgruen": r"Masterplan Stadtgrün",
    "digitalisierungsstrategie": r"Digitalisierungsstrategie",
}
RELATIONS = ("implements", "motion", "mentions", "none")
#: So viele Vorlagen prüft ein Aufruf.
BATCH = 8


def passages(text: str, pattern: str, width: int = 350, limit: int = 2) -> list[str]:
    """Die Stellen, an denen der Text den Plan nennt — die erste und die letzte, je ``width`` Zeichen Umfeld."""
    text = squash(text)
    hits = [m.span() for m in re.finditer(pattern, text)]
    if not hits:
        return []
    chosen = [hits[0]] + ([hits[-1]] if len(hits) > 1 and hits[-1][0] - hits[0][1] > width else [])
    return [text[max(0, a - width): b + width] for a, b in chosen[:limit]]


_LINK_PROMPT = """Du prüfst, in welcher Beziehung Vorlagen des Oldenburger Rats zu einem Plan der Stadt stehen.

Plan: {title}

Zu jeder Vorlage stehen unten ihr Titel und die Textstellen, die den Plan nennen.

Antworte nur mit JSON: {{"results": [{{"id": 1, "relation": "…", "quote": "…"}}]}}

relation ist genau eines von:
- "implements": Die Vorlage selbst setzt etwas aus dem Plan um oder dient ausdrücklich seiner Umsetzung — ein Förderprogramm, eine Satzung, ein Bau- oder Planungsbeschluss, Personal oder Geld dafür — und der Text SAGT das („dient der Umsetzung“, „setzt … um“, „Ziel ist …“).
- "motion": ein Antrag oder eine Anfrage aus dem Rat, die sich auf den Plan bezieht.
- "mentions": Der Plan wird nur genannt — als Hintergrund, Begründung, Rahmenplanung, in einer Aufzählung oder weil das Vorhaben ihm „entspricht“. Ein Bebauungsplan, der den Plan unter „Konzepten und Rahmenplanungen“ aufführt, ist immer "mentions". Ein Bericht über den Stand ist "mentions".
- "none": Gemeint ist etwas anderes als dieser Plan (gleiches Wort, anderes Konzept).

Im Zweifel "mentions": Eine Nennung ist keine Umsetzung. Wendungen wie „im Sinne von“, „trägt bei zu“, \
„unterstützt die Ziele“, „wie im Plan beschrieben“ oder „passt zu den Fokusthemen“ sind "mentions" — \
"implements" verlangt, dass die Vorlage eine KONKRETE Maßnahme oder Festlegung des Plans ausführt.
quote: nur bei "implements" — der wörtliche Satz oder Satzteil aus der Textstelle (höchstens 300 Zeichen), der die Umsetzung belegt. Sonst "".

Vorlagen:
{items}"""


def judge_links(plan_key: str, candidates: list[dict], model: str = MODEL) -> tuple[list[dict], float]:
    """Urteil je Vorlage (``{"template", "title", "passages"}``). Zurück: je Vorlage Beziehung und —
    bei „implements“ — das wörtliche Zitat.

    „implements“ zählt nur mit Beleg, den man ohne Modell prüfen kann: Das Zitat steht wörtlich in
    der Textstelle UND nennt den Plan selbst beim Namen. Sonst bleibt es eine Erwähnung. Die zweite
    Bedingung kam aus der Durchsicht aller Treffer von Hand (27, 09.11.2026): Die beiden unklaren
    waren genau die, deren Zitat den Plan nicht nannte („Diese werden … umgesetzt“)."""
    plan = register.PLANS[plan_key]
    name = re.compile(NAME_PATTERNS[plan_key])
    out: list[dict] = []
    spent = 0.0
    for start in range(0, len(candidates), BATCH):
        batch = candidates[start:start + BATCH]
        items = "\n\n".join(
            f"[{i}] {c['title']}\n" + "\n".join(f"   … {p} …" for p in c["passages"])
            for i, c in enumerate(batch, start=1))
        response = llm.chat_complete(model=model, _feature="plan_link_judgement", temperature=0,
                                     response_format={"type": "json_object"}, max_tokens=4000,
                                     messages=[{"role": "user", "content": _LINK_PROMPT.format(title=plan.title, items=items)}])
        spent += cost_usd(response, model)
        by_id = {r.get("id"): r for r in _json(response).get("results") or [] if isinstance(r, dict)}
        for i, c in enumerate(batch, start=1):
            relation, quote = checked_relation(by_id.get(i) or {}, c["passages"], name)
            out.append({"template": c["template"], "relation": relation, "quote": quote})
    return out, spent


def checked_relation(answer: dict, passages: list[str], name: re.Pattern) -> tuple[str, str]:
    """Das Urteil des Modells, soweit es sich ohne Modell belegen lässt: (Beziehung, Zitat).
    Unbekanntes wird zur Erwähnung; „implements“ ohne wörtliches Zitat, das den Plan nennt, auch."""
    said = answer.get("relation")
    relation = said if isinstance(said, str) and said in RELATIONS else "mentions"
    quote = squash(str(answer.get("quote") or ""))
    if relation != "implements":
        return relation, ""
    if not (quote and len(quote) <= 320 and name.search(quote) and any(quote in p for p in passages)):
        return "mentions", ""
    return relation, quote


# ── Ratsaufträge: Art des Auftrags und Folge im Rat (§ 3.5, Art 2) ─────────

MANDATE_TYPES = ("report_back", "execute")

_MANDATE_PROMPT = """Der Oldenburger Rat hat die Verwaltung in den Beschlüssen unten beauftragt. Ordne jeden Auftrag ein.

Antworte nur mit JSON: {{"results": [{{"id": 1, "type": "…", "subject": ["…", "…"]}}]}}

type ist genau eines von:
- "report_back": Die Verwaltung soll dem Rat oder einem Ausschuss etwas VORLEGEN — einen Bericht, ein Prüfergebnis, ein Konzept, eine Richtlinie, einen Zeitplan, Beschlussvorschläge. Im Rat ist also eine Folge zu erwarten.
- "execute": Die Verwaltung soll etwas TUN — einen Antrag stellen, einen Vertrag schließen, bauen, umbenennen, etwas sicherstellen oder weiterführen. Darauf muss im Rat nichts folgen.
Im Zweifel "execute".

subject: drei bis fünf Suchwörter für eine spätere Folge im Rat — Eigennamen, Orte und die Sache selbst („Park-and-Ride“, „Haarenesch“, „Wärmeversorgungsleitlinie“), je ein Wort oder fester Begriff, so wie er in einem Titel stünde. Keine allgemeinen Wörter wie „Konzept“, „Verwaltung“, „Stadt“.

Beschlüsse:
{items}"""


def classify_mandates(mandates: list[dict], model: str = MODEL) -> tuple[list[dict], float]:
    """Art jedes Auftrags (``{"stem", "title", "quote"}``) und Suchwörter für seine Folge."""
    out: list[dict] = []
    spent = 0.0
    for start in range(0, len(mandates), BATCH):
        batch = mandates[start:start + BATCH]
        items = "\n\n".join(f"[{i}] {m['title']}\n   „{m['quote']}“" for i, m in enumerate(batch, start=1))
        response = llm.chat_complete(model=model, _feature="plan_mandate_check", temperature=0,
                                     response_format={"type": "json_object"}, max_tokens=4000,
                                     messages=[{"role": "user", "content": _MANDATE_PROMPT.format(items=items)}])
        spent += cost_usd(response, model)
        by_id = {r.get("id"): r for r in _json(response).get("results") or [] if isinstance(r, dict)}
        for i, m in enumerate(batch, start=1):
            r = by_id.get(i) or {}
            kind = r.get("type")
            words = [squash(str(w)) for w in (r.get("subject") or []) if isinstance(w, str) and len(squash(w)) >= 4]
            out.append({"stem": m["stem"], "type": kind if isinstance(kind, str) and kind in MANDATE_TYPES else "execute",
                        "subject": words[:5]})
    return out, spent


_FOLLOW_PROMPT = """Der Oldenburger Rat hat die Verwaltung beauftragt:

Beschluss vom {since}: {title}
„{quote}“

Unten stehen spätere Tagesordnungspunkte aus Rat und Ausschüssen. Ist einer davon die FOLGE dieses Auftrags — also der Bericht, das Prüfergebnis, das Konzept oder die Vorlage, die der Auftrag verlangt, oder eine spätere Beratung genau dieser Sache?

Antworte nur mit JSON: {{"follow_up": <Nummer oder null>, "reason": "…"}}

Sei großzügig mit „ja“: Wenn ein späterer Punkt dieselbe Sache behandelt, ist der Auftrag nicht ohne Folge geblieben — auch wenn der Titel anders lautet. Nur wenn KEINER der Punkte die Sache betrifft, null.

Spätere Tagesordnungspunkte:
{items}"""


def find_follow_up(mandate: dict, candidates: list[dict], model: str = MODEL) -> tuple[int | None, float]:
    """Index des Kandidaten, der die Folge des Auftrags ist — oder ``None``. Ohne Kandidaten kein Aufruf."""
    if not candidates:
        return None, 0.0
    items = "\n".join(f"[{i}] {c['date']} · {c['committee'] or '—'} · {c['title']}" for i, c in enumerate(candidates, start=1))
    response = llm.chat_complete(model=model, _feature="plan_mandate_check", temperature=0,
                                 response_format={"type": "json_object"}, max_tokens=600,
                                 messages=[{"role": "user", "content": _FOLLOW_PROMPT.format(
                                     since=mandate["since"], title=mandate["title"], quote=mandate["quote"], items=items)}])
    answer = _json(response).get("follow_up")
    index = answer - 1 if isinstance(answer, int) and 1 <= answer <= len(candidates) else None
    return index, cost_usd(response, model)


# ── Was im Plan steht: Zweck und Kernpunkte ────────────────────────────────

#: Wovon ein Kernpunkt handelt. Nur zur Einordnung; die Seite zeigt es nicht als Wertung.
POINT_KINDS = ("goal", "standard", "figure", "responsibility", "deadline", "measure")
POINTS_MIN, POINTS_MAX = 3, 6
#: So viele Vorschläge darf das Modell machen; es bleiben die ersten ``POINTS_MAX``, die sich belegen lassen.
POINT_CANDIDATES = 8
QUOTE_MAX = 420
#: Ein Zitat aus drei Wörtern belegt nichts.
QUOTE_MIN_TIGHT = 30

_TIGHT_DROP = re.compile("[\\s\\-­‐‑‒–—\"'„“”‚‘’»«›‹-]+")
_LIGATURES = {"ﬂ": "fl", "ﬀ": "ff", "ﬁ": "fi", "ﬃ": "ffi", "ﬄ": "ffl"}
_NUMBER = re.compile(r"\d+(?:[.,]\d+)*")
#: Die Fußzeile jeder Seite eines Vorlagen-Ausdrucks — steht mitten im Satz, wo die Seite wechselt.
_PRINT_FOOTER = re.compile(r"Ausdruck vom:\s*\d{2}\.\d{2}\.\d{4}\s+Seite:\s*\d+/\d+")


def tight(text: str) -> str:
    """Für den Vergleich Zitat gegen Quelltext: ohne Leerraum, Trenn- und Gedankenstriche und
    Anführungszeichen, Ligaturen aufgelöst. Der PDF-Text bricht Zeilen mitten im Wort („Ver- pflegung“)
    und setzt typografische Zeichen, die ein Modell beim Abschreiben glättet — die Wörter und Zahlen
    müssen trotzdem Zeichen für Zeichen dieselben sein."""
    text = _PRINT_FOOTER.sub(" ", text or "")
    for old, new in _LIGATURES.items():
        text = text.replace(old, new)
    return _TIGHT_DROP.sub("", text)


def _plain_number(token: str) -> str:
    """„2.000“ → „2000“, „100,00“ → „100“, „3,50“ → „3,5“: dieselbe Zahl in einer Schreibweise."""
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+(?:,\d+)?", token):
        token = token.replace(".", "")
    if "," in token:
        token = token.rstrip("0").rstrip(",")
    return token.rstrip(".,")


def numbers(text: str) -> set[str]:
    """Die Zahlen eines Textes, je in einer Schreibweise („3,50“ und „3,5“ sind dieselbe, „2.000“ und
    „2000“ auch). Ein Datum zerfällt in seine Teile."""
    return {_plain_number(n) for n in _NUMBER.findall(text or "")}


_KEY_POINTS_PROMPT = """Du liest einen Plan der Stadt Oldenburg und die Beschlüsse dazu. Schreibe für \
Bürgerinnen und Bürger auf, was im Plan steht — so, dass man ihn in 20 Sekunden versteht, ohne die \
Dokumente zu lesen.

Plan: {title}
{mode}

Quellen, älteste zuerst. Jede beginnt mit ihrer Kennung in eckigen Klammern; Anlagen sind nach Seiten \
geteilt („— Seite 5 —“).

{sources}

Antworte nur mit JSON:
{{"purposes": [{{"text": "…", "source": "…", "page": null, "quote": "…"}}],
  "points": [{{"text": "…", "kind": "…", "source": "…", "page": null, "quote": "…"}}]}}

Regeln:
1. purposes: ZWEI Fassungen desselben Satzes mit verschiedenen Belegen, die bessere zuerst. Je EIN vollständiger Satz, höchstens 180 Zeichen, wozu es den Plan gibt und für wen oder was er gilt. Beginne mit dem Gattungswort („Der Plan …“, „Das Konzept …“, „Die Strategie …“), nicht mit dem vollen Namen.
2. points: fünf bis {candidates} Kernpunkte — was der Plan FESTLEGT: Ziele, Standards, Zahlen, Zuständigkeiten, \
Fristen. Je Punkt ein Satz, höchstens 170 Zeichen, konkret und in einfachen Worten, mit den Begriffen \
des Zitats. Die wichtigsten zuerst. Kein Punkt doppelt, kein Zitat zweimal, kein Punkt wiederholt den Zweck. Ein Kernpunkt sagt etwas Greifbares: WAS gilt, \
WIE VIEL, FÜR WEN oder BIS WANN. Einzelne Maßnahmen nur, wenn der Plan sie selbst als Schwerpunkt oder \
Priorität heraushebt — eine beliebige Auswahl aus einer Maßnahmenliste ist kein Kernpunkt. Findest du \
weniger greifbare Punkte, gib weniger zurück.
3. Nicht aufnehmen: wie der Plan entstanden ist (Beteiligung, Gutachter, Verfahren), allgemeine \
Absichten ohne Inhalt („die Nachhaltigkeit stärken“), Lob, Rechtsgrundlagen, Kosten der Erarbeitung, \
und alles, was nur vorgeschlagen, geprüft oder beantragt, aber nicht Teil des Plans ist.
4. Jeder Punkt und jede Fassung des Zwecks brauchen einen Beleg: source = Kennung der Quelle, page = Seitenzahl bei \
Anlagen (sonst null), quote = eine wörtliche, zusammenhängende Stelle aus genau dieser Quelle, \
höchstens 300 Zeichen. Schreibe sie Zeichen für Zeichen ab, nichts ändern, nichts auslassen, nichts \
zusammenziehen. Das Zitat muss den Satz ALLEIN tragen: Wer nur das Zitat liest, muss alles wiederfinden, \
was der Satz behauptet. Nimm ganze Sätze oder eine ganze Tabellenzeile samt ihrer Überschrift, keine \
bloße Reihe von Überschriften.
5. Jede Zahl im Satz (Mengen, Anteile, Preise, Jahre) muss genau so im Zitat stehen. Steht sie dort \
nicht, lass die Zahl weg oder nimm den Punkt nicht auf.
6. Spätere Beschlüsse gehen vor. Stehen unter den Quellen Beschlüsse NACH dem ursprünglichen Plan, dann \
sind sie der wichtigste Hinweis darauf, was heute gilt: Mindestens ein Punkt nennt, was sie geändert oder \
ergänzt haben (einen Anteil, einen Preis, eine Frist, eine Liste) — und zwar den HEUTE geltenden Stand im \
Ganzen, belegt mit dem jüngsten Beschluss oder seiner Vorlage, nicht mit dem ursprünglichen Plan. Nicht „X \
kommt dazu“, sondern wofür die Regel jetzt insgesamt gilt. Was überholt ist, kommt nicht vor.
7. Schreibe nur, was in den Quellen steht. Lieber drei sichere Punkte als sechs, von denen einer \
schief ist: Ein Punkt, der den Plan falsch wiedergibt, ist schlimmer als ein fehlender.
8. kind: goal (Ziel) · standard (Regel, Vorgabe) · figure (Zahl, Menge, Preis) · responsibility (wer \
zuständig ist) · deadline (Frist, Zeitplan) · measure (Vorhaben)."""

_MODE_NOTES = {
    "adopted": "Der Rat hat den Plan beschlossen.",
    "noted": "Der Rat hat den Plan nur zur Kenntnis genommen, nicht beschlossen. Schreibe deshalb "
             "„Der Plan sieht vor …“ oder „Der Plan empfiehlt …“, nicht „Die Stadt wird …“.",
    "draft": "Der Plan ist ein Entwurf und noch nicht beschlossen. Schreibe „Der Entwurf sieht vor …“.",
}


def render_sources(sources: list[dict]) -> str:
    """Die Quellen so, wie das Modell sie liest. ``sources``: je ``id``, ``heading`` und entweder
    ``text`` oder ``pages`` (Liste, Seite 1 zuerst)."""
    parts = []
    for s in sources:
        if s.get("pages") is not None:
            body = "\n".join(f"— Seite {n} —\n{squash(page)}" for n, page in enumerate(s["pages"], 1) if page.strip())
        else:
            body = squash(_PRINT_FOOTER.sub(" ", s["text"]))
        parts.append(f"[{s['id']}] {s['heading']}\n<<<\n{body}\n>>>")
    return "\n\n".join(parts)


def key_points(title: str, mode: str, sources: list[dict], model: str = MODEL) -> tuple[dict, float]:
    """Zweck und Kernpunkte eines Plans. Genau ein Modellaufruf; zurück kommt, was
    :func:`verified_key_points` übersteht — Vorschläge, mehr als gebraucht —, dazu die Kosten in US-Dollar."""
    prompt = _KEY_POINTS_PROMPT.format(title=title, mode=_MODE_NOTES[mode], sources=render_sources(sources),
                                       candidates=POINT_CANDIDATES)
    response = llm.chat_complete(model=model, _feature="plan_key_points", temperature=0,
                                 response_format={"type": "json_object"}, max_tokens=4000,
                                 messages=[{"role": "user", "content": prompt}])
    return verified_key_points(_json(response), sources), cost_usd(response, model)


def locate(quote: str, source: dict, page: int | None) -> tuple[bool, int | None]:
    """Steht das Zitat wörtlich in der Quelle? Bei Anlagen: auf welcher Seite — die Seitenangabe des
    Modells wird berichtigt, wenn das Zitat auf einer anderen steht; ein Zitat über einen Seitenwechsel
    zählt zur ersten der beiden Seiten."""
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


def check_statement(entry: dict, sources: dict[str, dict], limit: int) -> tuple[dict | None, str | None]:
    """Ein Satz mit Beleg — oder der Grund, warum er fällt. Geprüft wird ohne Modell: bekannte Quelle,
    Zitat wörtlich dort, jede Zahl des Satzes im Zitat."""
    if not isinstance(entry, dict):
        return None, "keine Angabe"
    text, quote = squash(str(entry.get("text") or "")), squash(str(entry.get("quote") or ""))
    named = re.search(r"[BVA]\d+", str(entry.get("source") or ""))
    source = sources.get(named.group(0)) if named else None
    if not text or len(text) > limit:
        return None, f"Satz fehlt oder ist länger als {limit} Zeichen"
    if source is None:
        return None, "unbekannte Quelle"
    if not quote or len(quote) > QUOTE_MAX:
        return None, "Zitat fehlt oder ist zu lang"
    page = entry.get("page") if isinstance(entry.get("page"), int) else None
    found, page = locate(quote, source, page)
    if not found:
        return None, "Zitat steht nicht wörtlich in der Quelle"
    have = numbers(quote)
    missing = sorted({n for n in _NUMBER.findall(text) if _plain_number(n) not in have})
    if missing:
        return None, f"Zahl ohne Beleg im Zitat: {', '.join(missing)}"
    return {"text": text, "quote": quote, "source": source["id"], "page": page}, None


def verified_key_points(answer: dict, sources: list[dict]) -> dict:
    """Nur was sich ohne Modell belegen lässt. ``dropped`` nennt, was fiel und warum — für den Lauf,
    nicht für die Datei."""
    by_id = {s["id"]: s for s in sources}
    dropped: list[str] = []

    def keep(raw, limit: int, what: str) -> dict | None:
        statement, why = check_statement(raw, by_id, limit)
        if statement is None:
            shown = raw if isinstance(raw, dict) else {}
            dropped.append(f"{what}{str(shown.get('text'))[:70]} — {why} · „{str(shown.get('quote'))[:90]}“")
        return statement

    purposes = [p for raw in (answer.get("purposes") or [])[:3] if (p := keep(raw, 200, "Zweck: "))]
    points, seen = [], {tight(p["quote"]) for p in purposes}
    for raw in (answer.get("points") or [])[:POINT_CANDIDATES]:
        point = keep(raw, 190, "")
        # Ein Zitat belegt einen Satz: Wer dasselbe zweimal belegt, sagt dasselbe zweimal.
        if point is None or tight(point["quote"]) in seen:
            continue
        seen.add(tight(point["quote"]))
        kind = raw.get("kind")
        points.append({**point, "kind": kind if kind in POINT_KINDS else "goal"})
    return {"purposes": purposes, "points": points, "dropped": dropped}


_SUPPORT_PROMPT = """Unten stehen Sätze über einen Plan der Stadt Oldenburg, jeder mit dem Zitat, das ihn \
belegen soll. Prüfe jeden Satz NUR gegen sein Zitat.

{pairs}

Antworte nur mit JSON: {{"results": [{{"n": 1, "supported": true, "missing": ""}}]}}

Dass es um einen Plan der Stadt Oldenburg geht, ist gegeben: Rahmenwörter wie „Der Plan“, „Das Konzept“, \
„Der Entwurf sieht vor“, „laut Plan“, „die Stadt“ oder „in Oldenburg“ müssen NICHT im Zitat stehen und \
sind kein Grund für false.

supported = true, wenn alles Sachliche, was der Satz behauptet, im Zitat steht oder sich unmittelbar \
daraus ergibt. Andere Worte, einfachere Sprache, Kürzen und sinngleiche Wendungen sind in Ordnung \
(„Senkung“ für „Reduzierung“, „gilt ab“ für „wird umgesetzt zum“, „der Plan schafft die Grundlage“ für \
„soll als Grundlage dienen“); der Satz darf auch weniger sagen als das Zitat. supported = false nur bei \
einem sachlichen Mehr oder Anders: eine Zahl, ein Zeitpunkt, ein Ort, ein Akteur, ein Gegenstand, ein \
Geltungsbereich oder eine Verbindlichkeit („muss“ statt „soll“, „beschlossen“ statt „vorgeschlagen“), \
die das Zitat nicht hergibt. missing: in wenigen Worten, was im Zitat fehlt (sonst leer)."""


def unsupported(statements: list[dict], model: str = MODEL) -> tuple[dict[int, str], float]:
    """Zweite Lesung, die nur streichen kann: Welche Sätze trägt ihr Zitat NICHT? Zurück: Index → Grund,
    dazu die Kosten. Das Zitat steht dann zwar wörtlich in der Quelle, aber der Satz sagt mehr als es."""
    pairs = "\n\n".join(f"{n}. Satz: {st['text']}\n   Zitat: „{st['quote']}“" for n, st in enumerate(statements, 1))
    response = llm.chat_complete(model=model, _feature="plan_key_points", temperature=0,
                                 response_format={"type": "json_object"}, max_tokens=1500,
                                 messages=[{"role": "user", "content": _SUPPORT_PROMPT.format(pairs=pairs)}])
    out: dict[int, str] = {}
    for r in _json(response).get("results") or []:
        if isinstance(r, dict) and isinstance(r.get("n"), int) and r.get("supported") is False:
            out[r["n"] - 1] = str(r.get("missing") or "")
    return out, cost_usd(response, model)
