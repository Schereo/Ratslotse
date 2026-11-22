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
# Eine Regel statt zwei (council/evidence.py): Zitatvergleich und Seitensuche stehen dort.
from council.evidence import _PRINT_FOOTER, QUOTE_MAX, QUOTE_MIN_TIGHT, locate, tight  # noqa: F401
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
_NUMBER = re.compile(r"\d+(?:[.,]\d+)*")


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


def unsupported(statements: list[dict], model: str = MODEL, feature: str = "plan_key_points") -> tuple[dict[int, str], float]:
    """Zweite Lesung, die nur streichen kann: Welche Sätze trägt ihr Zitat NICHT? Zurück: Index → Grund,
    dazu die Kosten. Das Zitat steht dann zwar wörtlich in der Quelle, aber der Satz sagt mehr als es."""
    pairs = "\n\n".join(f"{n}. Satz: {st['text']}\n   Zitat: „{st['quote']}“" for n, st in enumerate(statements, 1))
    response = llm.chat_complete(model=model, _feature=feature, temperature=0,
                                 response_format={"type": "json_object"}, max_tokens=1500,
                                 messages=[{"role": "user", "content": _SUPPORT_PROMPT.format(pairs=pairs)}])
    out: dict[int, str] = {}
    for r in _json(response).get("results") or []:
        if isinstance(r, dict) and isinstance(r.get("n"), int) and r.get("supported") is False:
            out[r["n"] - 1] = str(r.get("missing") or "")
    return out, cost_usd(response, model)


# ── Von Hand gesetzt: die Zahl als Kachel, der Termin fürs Zeitband ────────
#
# Ein Kernpunkt kann zwei Zusätze tragen, die niemand errechnet, sondern jemand
# hinschreibt: ``figure`` (die eine Zahl des Satzes, groß gesetzt, mit einem
# kurzen Wort dazu) und ``due`` (der Termin, den der Plan selbst nennt — als
# Marke im Zeitband). Beides wird hier ohne Modell gegen das Zitat gehalten:
# Eine Zahl oder ein Jahr, das dort nicht steht, kommt nicht auf die Seite.

FIGURE_VALUE_MAX = 16
FIGURE_LABEL_MAX = 72
DUE_LABEL_MAX = 32
#: Zahlwörter, wie Pläne sie ausschreiben („mindestens drei Standorte“).
_NUMBER_WORDS = {"2": "zwei", "3": "drei", "4": "vier", "5": "fünf", "6": "sechs", "7": "sieben",
                 "8": "acht", "9": "neun", "10": "zehn", "11": "elf", "12": "zwölf", "20": "zwanzig"}
_DUE_DATE = re.compile(r"\d{4}(?:-\d{2}(?:-\d{2})?)?")


def _number_in_quote(number: str, quote: str) -> bool:
    word = _NUMBER_WORDS.get(number)
    return number in numbers(quote) or bool(word and re.search(rf"\b{word}", quote.lower()))


def check_extras(point: dict) -> list[str]:
    """Was an ``figure`` und ``due`` eines Kernpunkts nicht stimmt — leer, wenn alles belegt ist."""
    problems: list[str] = []
    quote = point.get("quote") or ""
    figure = point.get("figure")
    if figure is not None:
        value, label = str(figure.get("value") or ""), str(figure.get("label") or "")
        if not value or len(value) > FIGURE_VALUE_MAX:
            problems.append(f"Kachel-Zahl fehlt oder ist länger als {FIGURE_VALUE_MAX} Zeichen: „{value}“")
        if not label or len(label) > FIGURE_LABEL_MAX:
            problems.append(f"Kachel-Text fehlt oder ist länger als {FIGURE_LABEL_MAX} Zeichen: „{label}“")
        missing = sorted(n for n in numbers(f"{value} {label}") if not _number_in_quote(n, quote))
        if missing:
            problems.append(f"Kachel nennt eine Zahl, die nicht im Zitat steht ({', '.join(missing)})")
    due = point.get("due")
    if due is not None:
        date, label, at = str(due.get("date") or ""), str(due.get("label") or ""), due.get("at")
        if not _DUE_DATE.fullmatch(date):
            problems.append(f"Termin ist kein Datum (JJJJ, JJJJ-MM oder JJJJ-MM-TT): „{date}“")
        if len(date) < 10 and at not in ("start", "end"):
            problems.append("Termin ohne Tag braucht at: start oder end")
        if not label or len(label) > DUE_LABEL_MAX:
            problems.append(f"Termin-Text fehlt oder ist länger als {DUE_LABEL_MAX} Zeichen: „{label}“")
        years = set(re.findall(r"(?<!\d)(?:19|20)\d{2}(?!\d)", label))
        if date[:4] not in years:
            problems.append(f"Termin-Text nennt das Jahr {date[:4]} nicht")
        gone = sorted(y for y in years if y not in quote)
        if gone:
            problems.append(f"Termin nennt ein Jahr, das nicht im Zitat steht ({', '.join(gone)})")
    return problems


# ── Berichte in einem Satz, Neues im jüngsten Bericht ──────────────────────
#
# Die Berichtstitel im Ratsinformationssystem sagen nichts („Klimaschutz-
# Aktivitäten 3/2026 - Bericht“). Ein Modell schlägt je Bericht EINEN Satz vor,
# was die Verwaltung darin meldet, und nennt die Stelle. In die Datei
# (``council/plan_reports/<plan>.json``) kommt nur, was ohne Modell belegt ist:
# das Zitat steht wörtlich in der Vorlage, jede Zahl des Satzes im Zitat.
# Für „Neu im jüngsten Bericht“ zusätzlich: Das Zitat steht im vorigen
# Bericht derselben Reihe NICHT.
#
# Der Satz ist eine Selbstauskunft der Verwaltung und wird auf der Seite so
# gekennzeichnet (Plan § 3.4 Nr. 3). Er sagt nichts über Wirkung oder Güte.

REPORT_TEXT_MAX = 190
NEWS_MAX = 3
#: Berichte einer Reihe heißen fast gleich („… 2/2026 - Bericht“, „… 3/2026 - Bericht“).
SERIES_OVERLAP = 0.6

_REPORT_PROMPT = """Du liest einen Bericht der Verwaltung an den Rat der Stadt Oldenburg. Er gehört zum Plan \
„{plan}“.

Titel des Berichts: {title}
Im Rat: {date}

Schreibe für Bürgerinnen und Bürger in EINEM Satz auf, was die Verwaltung in diesem Bericht zum Plan \
meldet — das Konkreteste, was drinsteht: was erreicht ist, eine Zahl, was als Nächstes kommt.

Regeln:
1. Gib zwei Vorschläge (candidates), den besseren zuerst. Zu jedem das wörtliche Zitat aus dem Bericht, \
das den Satz ALLEIN trägt: Wer nur das Zitat liest, findet darin alles, was der Satz sagt.
2. Jede Zahl, jedes Datum und jeder Eigenname des Satzes steht im Zitat.
3. Der Satz gibt wieder, was im Bericht steht — keine Wertung, kein Lob („erfolgreich“, „gut“), keine \
Folgerung. Was der Bericht nur plant oder vorschlägt, heißt im Satz „geplant“, „soll“ oder „ist vorgesehen“.
4. Höchstens {limit} Zeichen, ein vollständiger Satz in einfachen Wörtern. Fang mit der Sache an, nicht \
mit „Der Bericht“, „Die Verwaltung berichtet“ oder „Laut Bericht“ — das steht auf der Seite schon dabei.
5. Das Zitat ist wörtlich und zusammenhängend aus dem Bericht kopiert, höchstens 400 Zeichen, nichts \
ausgelassen, nichts umgestellt.
6. Steht im Bericht nichts Konkretes zum Plan (nur Verfahren, nur ein Verweis auf eine Anlage): \
candidates bleibt leer.

Der Bericht:
{text}

Antworte nur mit JSON: {{"candidates": [{{"text": "...", "quote": "..."}}]}}"""


def _one_source(text: str) -> dict[str, dict]:
    return {"V1": {"id": "V1", "kind": "template", "text": text}}


def report_sentence(plan_title: str, title: str, date: str, text: str,
                    model: str = MODEL) -> tuple[list[dict], list[str], float]:
    """Ein Satz zu einem Bericht. Ein Modellaufruf; zurück kommen die Vorschläge, die die Prüfung ohne
    Modell überstehen (der bessere zuerst), was fiel und warum, und die Kosten."""
    prompt = _REPORT_PROMPT.format(plan=plan_title, title=title, date=date, limit=REPORT_TEXT_MAX, text=text)
    response = llm.chat_complete(model=model, _feature="plan_reports", temperature=0,
                                 response_format={"type": "json_object"}, max_tokens=900,
                                 messages=[{"role": "user", "content": prompt}])
    kept, dropped = checked_statements((_json(response).get("candidates") or [])[:3], text, REPORT_TEXT_MAX)
    return kept, dropped, cost_usd(response, model)


def checked_statements(raw: list, text: str, limit: int, absent_from: str | None = None) -> tuple[list[dict], list[str]]:
    """Sätze mit Zitat gegen EINEN Text gehalten, ohne Modell: Zitat wörtlich dort, jede Zahl des Satzes
    im Zitat, kein Zitat zweimal. ``absent_from``: Das Zitat darf in diesem Text NICHT stehen (der vorige
    Bericht — sonst ist es nicht neu)."""
    sources = _one_source(text)
    before = tight(absent_from) if absent_from else ""
    kept: list[dict] = []
    dropped: list[str] = []
    seen: set[str] = set()
    for entry in raw:
        candidate = {**entry, "source": "V1"} if isinstance(entry, dict) else entry
        statement, why = check_statement(candidate, sources, limit)
        if statement and tight(statement["quote"]) in seen:
            statement, why = None, "Zitat belegt schon einen anderen Satz"
        if statement and before and tight(statement["quote"]) in before:
            statement, why = None, "steht wörtlich schon im vorigen Bericht"
        if statement is None:
            shown = entry if isinstance(entry, dict) else {}
            dropped.append(f"{str(shown.get('text'))[:70]} — {why} · „{str(shown.get('quote'))[:90]}“")
            continue
        seen.add(tight(statement["quote"]))
        kept.append({"text": statement["text"], "quote": statement["quote"]})
    return kept, dropped


_NEWS_PROMPT = """Du vergleichst zwei Berichte der Verwaltung an den Rat der Stadt Oldenburg zum Plan \
„{plan}“: den vorigen (ALT, im Rat {old_date}) und den jüngsten (NEU, im Rat {new_date}).

Nenne bis zu {limit} Dinge, die im jüngsten Bericht NEU sind: ein Stand, der sich geändert hat, eine neue \
Zahl, ein Schritt, der im vorigen Bericht noch nicht stand.

Regeln:
1. Je ein Satz (höchstens {chars} Zeichen, einfache Wörter) und das wörtliche Zitat aus NEU, das den Satz \
ALLEIN trägt.
2. Jede Zahl, jedes Datum und jeder Eigenname des Satzes steht im Zitat. Nenne nur den neuen Stand, \
keinen Vergleich mit früher („statt 25“), wenn die frühere Zahl nicht im selben Zitat steht.
3. Nichts, was schon im vorigen Bericht stand — auch nicht in anderen Worten. Dieselbe Aussage mit \
neuer Zahl zählt als neu.
4. Keine Wertung, kein Lob, keine Folgerung. Geplantes heißt „geplant“ oder „soll“.
5. Das Zitat ist wörtlich und zusammenhängend aus NEU kopiert, höchstens 400 Zeichen.
6. Ist nichts wirklich neu: changes bleibt leer. Lieber ein belegter Punkt als drei dünne.

ALT:
{old}

NEU:
{new}

Antworte nur mit JSON: {{"changes": [{{"text": "...", "quote": "..."}}]}}"""


def report_news(plan_title: str, old: dict, new: dict, model: str = MODEL) -> tuple[list[dict], list[str], float]:
    """Was im jüngsten Bericht neu ist. ``old``/``new``: ``{"date", "text"}``. Zurück: bis zu
    ``NEWS_MAX`` Sätze, deren Zitat im neuen Bericht steht und im vorigen nicht."""
    prompt = _NEWS_PROMPT.format(plan=plan_title, old_date=old["date"], new_date=new["date"], limit=NEWS_MAX,
                                 chars=REPORT_TEXT_MAX, old=old["text"], new=new["text"])
    response = llm.chat_complete(model=model, _feature="plan_reports", temperature=0,
                                 response_format={"type": "json_object"}, max_tokens=1400,
                                 messages=[{"role": "user", "content": prompt}])
    kept, dropped = checked_statements((_json(response).get("changes") or [])[:NEWS_MAX + 2], new["text"],
                                       REPORT_TEXT_MAX, absent_from=old["text"])
    return kept, dropped, cost_usd(response, model)


def _title_words(title: str) -> set[str]:
    return set(re.sub(r"[\d/.\-–—()\"„“”]+", " ", title.lower()).split())


def same_series(a: str, b: str) -> bool:
    """Gehören zwei Berichte zur selben Reihe? Gleiche Titel bis auf Nummer und Jahr."""
    x, y = _title_words(a), _title_words(b)
    return bool(x | y) and len(x & y) / len(x | y) >= SERIES_OVERLAP


# ── Der Plan in einfacher Sprache, und drei Fragen dazu ────────────────────
#
# Lotti erklärt den Plan in drei Sätzen — NUR aus den belegten Kernpunkten
# (``council/plan_key_points/``), nicht aus den Dokumenten: Was dort nicht
# steht, kann hier nicht dazukommen. Ohne Modell geprüft wird, dass keine Zahl
# auftaucht, die die Kernpunkte nicht nennen; eine zweite Lesung des Modells
# streicht die Fassung, wenn ein Satz mehr sagt als die Punkte.

PLAIN_SENTENCES = 3
#: Was die Prüfung durchlässt. Dem Modell sagt der Auftrag weniger (``PLAIN_ASK``, ``QUESTION_ASK``):
#: Es zählt Zeichen schlecht, und ein Satz, der fünf Zeichen drüber liegt, ist kein Grund für einen neuen Lauf.
PLAIN_CHARS = 190
PLAIN_ASK = 140
QUESTION_COUNT = 3
QUESTION_CHARS = 120
QUESTION_ASK = 90
#: Fällt der erste Entwurf durch, bekommt das Modell die Gründe und einen zweiten Versuch.
PLAIN_ATTEMPTS = 2

_PLAIN_PROMPT = """Du bist Lotti, die Erklärerin von Ratslotse. Erkläre einen Plan der Stadt Oldenburg in \
klarer Alltagssprache — für Erwachsene ohne Verwaltungswissen. Keine Leichte Sprache: nicht kindlich, nicht \
belehrend.

Plan: {title}
{mode}

Das ist alles, was du über den Plan weißt (belegte Kernpunkte):
{points}

Aufgabe 1 — plain: genau {sentences} KURZE Sätze, die zusammen sagen, worum es im Plan geht und was er \
konkret vorsieht. Jeder Satz höchstens {chars} Zeichen: ein Hauptsatz, höchstens ein Nebensatz, keine \
Aufzählung mit mehr als drei Gliedern. Lieber weniger sagen als einen langen Satz bauen.
- Benutze NUR, was in den Kernpunkten steht. Keine Zahl, kein Datum, kein Ort, kein Akteur und keine \
Folge, die dort nicht steht.
- Vereinfache die Sprache, nie den Inhalt: „soll“ bleibt „soll“, aus einem Ziel wird keine Tatsache.
- Übersetze Fachwörter, statt sie zu wiederholen — aber mach aus einer Sache keine andere: \
„Photovoltaik“ bleibt Photovoltaik und wird nicht „Solaranlagen“, „Krippe“ wird nicht „Kita“.
- Keine Wertung, keine Meinung, kein „wichtig“.

Aufgabe 2 — questions: genau {questions} Fragen, die jemand dem Ratsarchiv zu diesem Plan stellen könnte.
{question_rules}

Antworte nur mit JSON: {{"plain": ["...", "...", "..."], "questions": ["...", "...", "..."]}}"""

#: Die Fragen laufen ins Ratsarchiv (Beschlüsse, Vorlagen, Berichte). Eine Frage, die dort ins Leere
#: läuft, wäre schlimmer als keine (components/frage-chips.tsx) — deshalb hängt jede an einem Kernpunkt
#: oder am Stand, und nach Geld fragt nur, wer einen Betrag vor sich hat.
_QUESTION_RULES = """- Die erste fragt nach dem Stand: was zuletzt zum Plan berichtet oder beschlossen wurde.
- Die zweite und dritte fragen je nach EINEM konkreten Kernpunkt — so, dass die Antwort in den \
Beschlüssen, Vorlagen und Berichten der Stadt stehen kann. Zwei verschiedene Kernpunkte.
- Keine Frage nach Kosten oder Geld, außer ein Kernpunkt nennt selbst einen Betrag.
- Jede Frage wird OHNE Zusammenhang gestellt: Sie nennt den Plan oder sein Thema beim Namen und \
„Oldenburg“, wo es sonst unklar wäre.
- Höchstens {qchars} Zeichen, endet mit „?“, Alltagssprache. Keine Unterstellung („Warum scheitert …“), \
keine Zahl, die nicht in den Kernpunkten steht."""

_QUESTIONS_PROMPT = """Zu einem Plan der Stadt Oldenburg sollen drei Fragen vorgeschlagen werden, die \
Bürgerinnen und Bürger dem Ratsarchiv stellen können.

Plan: {title}

Belegte Kernpunkte des Plans:
{points}

Schreibe genau {questions} Fragen.
{question_rules}

Antworte nur mit JSON: {{"questions": ["...", "...", "..."]}}"""

_PLAIN_MODES = {
    "adopted": "Der Rat hat den Plan beschlossen.",
    "noted": "Der Rat hat den Plan zur Kenntnis genommen, nicht beschlossen: Schreibe „der Plan sieht vor“, "
             "nicht „die Stadt hat beschlossen“.",
    "draft": "Der Plan ist ein Entwurf und noch nicht beschlossen: Schreibe „soll“ und „ist vorgesehen“.",
}


def key_point_lines(data: dict) -> list[str]:
    """Die Kernpunkte eines Plans als Zeilen — die einzige Quelle der einfachen Fassung."""
    return [data["purpose"]["text"], *(p["text"] for p in data["points"])]


def check_plain(sentences: list, questions: list, title: str, lines: list[str]) -> list[str]:
    """Was an der einfachen Fassung und den Fragen nicht stimmt — ohne Modell. Leer heißt: in Ordnung."""
    problems: list[str] = []
    allowed = numbers(" ".join([title, *lines]))
    if len(sentences) != PLAIN_SENTENCES or not all(isinstance(s, str) and s.strip() for s in sentences):
        return [f"einfache Fassung hat nicht genau {PLAIN_SENTENCES} Sätze"]
    if len(questions) != QUESTION_COUNT or not all(isinstance(q, str) and q.strip() for q in questions):
        return [f"nicht genau {QUESTION_COUNT} Fragen"]
    for s in sentences:
        if len(s) > PLAIN_CHARS:
            problems.append(f"Satz länger als {PLAIN_CHARS} Zeichen: {s[:50]}…")
        extra = sorted(n for n in numbers(s) if n not in allowed and _NUMBER_WORDS.get(n) is None)
        if extra:
            problems.append(f"Zahl, die kein Kernpunkt nennt ({', '.join(extra)}): {s[:50]}…")
    if len({squash(q).lower() for q in questions}) != len(questions):
        problems.append("zwei gleiche Fragen")
    for q in questions:
        if not q.rstrip().endswith("?") or len(q) > QUESTION_CHARS:
            problems.append(f"Frage ohne Fragezeichen oder länger als {QUESTION_CHARS} Zeichen: {q[:50]}…")
        extra = sorted(n for n in numbers(q) if n not in allowed)
        if extra:
            problems.append(f"Frage nennt eine Zahl, die kein Kernpunkt nennt ({', '.join(extra)}): {q[:50]}…")
    return problems


def plain_text(title: str, mode: str, lines: list[str], model: str = MODEL) -> tuple[dict | None, list[str], float]:
    """Die einfache Fassung und drei Fragen. Zwei Modellaufrufe (entwerfen, gegenlesen); zurück kommt
    ``{"plain", "questions"}`` oder ``None`` mit den Gründen, dazu die Kosten."""
    listed = "\n".join(f"- {line}" for line in lines)
    prompt = _PLAIN_PROMPT.format(title=title, mode=_PLAIN_MODES[mode], points=listed, sentences=PLAIN_SENTENCES,
                                  chars=PLAIN_ASK, questions=QUESTION_COUNT,
                                  question_rules=_QUESTION_RULES.format(qchars=QUESTION_ASK))
    messages = [{"role": "user", "content": prompt}]
    cost, problems = 0.0, ["kein Versuch"]
    for _attempt in range(PLAIN_ATTEMPTS):
        response = llm.chat_complete(model=model, _feature="plan_plain", temperature=0,
                                     response_format={"type": "json_object"}, max_tokens=900, messages=messages)
        answer = _json(response)
        cost += cost_usd(response, model)
        sentences = [squash(s) for s in answer.get("plain") or [] if isinstance(s, str)]
        questions = [squash(q) for q in answer.get("questions") or [] if isinstance(q, str)]
        problems = check_plain(sentences, questions, title, lines)
        if not problems:
            # Zweite Lesung: Trägt die Liste der Kernpunkte jeden Satz? Sie kann nur streichen — dann fällt die Fassung.
            weak, second = unsupported([{"text": s, "quote": " · ".join(lines)} for s in sentences], model,
                                       feature="plan_plain")
            cost += second
            problems = [f"Satz {i + 1} sagt mehr als die Kernpunkte ({why}): {sentences[i][:80]}"
                        for i, why in sorted(weak.items()) if i < len(sentences)]
        if not problems:
            return {"plain": sentences, "questions": questions}, [], cost
        messages = [*messages, {"role": "assistant", "content": json.dumps(answer, ensure_ascii=False)},
                    {"role": "user", "content": "Das fiel bei der Prüfung durch:\n- " + "\n- ".join(problems)
                     + "\nSchreib beides noch einmal und halte jede Regel ein. Antworte nur mit JSON."}]
    return None, problems, cost


def plan_questions(title: str, plain: list[str], lines: list[str], model: str = MODEL) -> tuple[list[str] | None, list[str], float]:
    """Nur die drei Fragen neu (die einfache Fassung bleibt, wie sie ist). Ein Modellaufruf, bei einem
    Fehlversuch ein zweiter mit den Gründen."""
    prompt = _QUESTIONS_PROMPT.format(title=title, points="\n".join(f"- {line}" for line in lines),
                                      questions=QUESTION_COUNT, question_rules=_QUESTION_RULES.format(qchars=QUESTION_ASK))
    messages = [{"role": "user", "content": prompt}]
    cost, problems = 0.0, ["kein Versuch"]
    for _attempt in range(PLAIN_ATTEMPTS):
        response = llm.chat_complete(model=model, _feature="plan_plain", temperature=0,
                                     response_format={"type": "json_object"}, max_tokens=500, messages=messages)
        answer = _json(response)
        cost += cost_usd(response, model)
        questions = [squash(q) for q in answer.get("questions") or [] if isinstance(q, str)]
        problems = check_plain(plain, questions, title, lines)
        if not problems:
            return questions, [], cost
        messages = [*messages, {"role": "assistant", "content": json.dumps(answer, ensure_ascii=False)},
                    {"role": "user", "content": "Das fiel bei der Prüfung durch:\n- " + "\n- ".join(problems)
                     + "\nSchreib die Fragen noch einmal. Antworte nur mit JSON."}]
    return None, problems, cost


def plain_basis(lines: list[str]) -> str:
    """Fingerabdruck der Kernpunkte, aus denen die einfache Fassung entstand. Ändert sich ein Kernpunkt,
    passt die Fassung nicht mehr dazu — die Seite zeigt sie dann nicht, der Wächter meldet es."""
    import hashlib
    return hashlib.sha256("\n".join(squash(line) for line in lines).encode("utf-8")).hexdigest()[:16]
