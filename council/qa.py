"""Question answering over council decisions ("Frag den Stadtrat").

Retrieval is keyword-based (German nouns from the question), then the LLM answers
*only* from the retrieved decisions and cites them by id. Honest by construction:
if the retrieved decisions don't answer the question, the model says so. Semantic
embedding retrieval is the planned upgrade (see council-ai-roadmap).
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re

from kern import llm, prompts
from council import ernte
from council.topics import _strip_fences  # noqa: F401  (kept for symmetry / future use)

# Antwort-Modell: gemini-2.5-flash antwortet in ~1,2–1,8 s, wo deepseek übers
# DSGVO-Provider-Routing 3–32 s brauchte — bei gleicher oder besserer
# Zitier-Qualität im Eval (eval/results/qa/, Modellvergleich 09.08.2026).
MODEL = os.environ.get("COUNCIL_QA_MODEL", "google/gemini-2.5-flash")
# Die Query-Expansion ist ein Mini-Prompt (60 Tokens Output) auf dem kritischen
# Pfad JEDER Frage. Default ist ein schnelles Modell: gemini-2.5-flash-lite
# expandiert in ~0,5 s, wo deepseek übers DSGVO-Provider-Routing 2–12 s brauchte
# — bei identischer Retrieval-Trefferquote im Eval (eval/results/qa/, 09.08.2026).
EXPAND_MODEL = os.environ.get("COUNCIL_QA_EXPAND_MODEL", "google/gemini-2.5-flash-lite")

_STOP = {
    "wurde", "wurden", "wird", "werden", "beschlossen", "beschluss", "stadt", "stadtrat",
    "oldenburg", "welche", "welcher", "welches", "wann", "warum", "wieso", "wofür",
    "haben", "hat", "gibt", "über", "zum", "zur", "eine", "einen", "einer", "nicht",
}


def extract_keywords(question: str) -> list[str]:
    """German nouns (capitalised words) are the best query terms; fall back to long words.
    Hyphenated compounds are also split so "Photovoltaik-Projekte" still matches "Photovoltaik"."""
    nouns = re.findall(r"\b[A-ZÄÖÜ][A-Za-zÄÖÜäöüß-]{3,}\b", question)
    terms = [w.lower() for w in nouns] if nouns else re.findall(r"[a-zäöüß-]{4,}", question.lower())
    out: list[str] = []
    for t in terms:
        for part in [t, *t.split("-")]:
            if len(part) >= 4 and part not in _STOP and part not in out:
                out.append(part)
    return out[:8]


# Die Prompt-Templates leben in kern/prompts.py („qa_antwort" / „qa_suchbegriffe")
# und sind — wie alle anderen — über das Admin-UI live editierbar.


# Erfolgreiche Expansionen je Prozess merken: Folgefragen-Chips und die
# Beispielfragen stellen wortgleiche Fragen immer wieder — der Cache spart dann
# den LLM-Roundtrip (typisch 0,5–1,5 s) auf dem kritischen Pfad. Fehlschläge
# werden nie gecacht (ein LLM-Aussetzer soll keine schlechte Expansion festnageln).
_EXPAND_CACHE: dict[str, str] = {}
_EXPAND_CACHE_MAX = 256

# --- Frage-Analyse (Stufe 2: Fragetyp-Routing) ------------------------------
# EIN LLM-Call vor der Suche liefert Suchbegriffe UND Fragetyp (+ ggf. die
# gefragte Fraktion) — kein zweiter Roundtrip gegenüber der reinen Expansion.
# „person" und „sitzung" liefert die LLM-Analyse nie — die Typen werden
# deterministisch gesetzt, wenn finde_person eine Ratsperson bzw.
# finde_sitzungen eine konkrete Sitzung in der Frage erkennt (Router).
QUERY_TYPES = ("topic", "history", "party", "money", "person", "session", "place")
_ANALYSE_CACHE: dict[str, dict] = {}

# Rechercheplaner im Shadow-Mode: Diese Kanäle existieren heute bereits oder
# sind als klar begrenzte Ratslotse-Schnittstelle vorgesehen. Das Modell darf
# nur aus dieser Liste wählen; ausgeführt wird der Plan zunächst ausdrücklich
# NICHT. So messen wir seine Vorschläge, ohne Antworten unbemerkt zu verändern.
RESEARCH_CHANNELS = (
    "decisions", "debates", "budget", "press", "sessions",
    "future_agenda", "places", "documents",
)
RESEARCH_INTENTS = (
    "fact", "overview", "status", "timeline", "money", "position", "session",
)
RESEARCH_SORTS = ("relevance", "newest", "chronological")
RESEARCH_NEEDS = (
    "amounts", "statements", "dates", "votes", "locations", "documents", "current_info",
    "official_updates", "future_dates",
)
_PLAN_HASH_KEY = ((os.environ.get("WEB_JWT_SECRET") or
                   os.environ.get("COUNCIL_QA_PLAN_HASH_SALT") or "").encode("utf-8")
                  or os.urandom(32))


# Wie viel Gespräch die Analyse/Antwort sieht: die letzten Runden reichen —
# ältere Bezüge löst niemand mehr per „dazu" auf.
VERLAUF_MAX_RUNDEN = 3
_VERLAUF_FRAGE_MAX = 250
_VERLAUF_ANTWORT_MAX = 400


def _verlauf_zeilen(verlauf: list[dict] | None) -> str:
    """Gesprächsverlauf als kompakte Zeilen (leer ohne Verlauf)."""
    zeilen = []
    for runde in (verlauf or [])[-VERLAUF_MAX_RUNDEN:]:
        question = " ".join(str(runde.get("question") or "").split())[:_VERLAUF_FRAGE_MAX]
        answer = " ".join(str(runde.get("answer") or "").split())[:_VERLAUF_ANTWORT_MAX]
        if question:
            zeilen.append(f"- Frage: {question}" + (f" — Antwort (gekürzt): {answer}" if answer else ""))
    return "\n".join(zeilen)


def _research_plan(data: dict) -> dict:
    """Streng validierter LLM-Plan für den Shadow-Mode.

    Freitext, unbekannte Kanäle und falsche Typen kommen nie bis zum Executor.
    ``decisions`` bleibt als sicherer Basiskanal immer enthalten. ``valid``
    zeigt, ob das Modell überhaupt ein strukturell brauchbares Planobjekt
    geliefert hat — alte Admin-Prompt-Overrides fallen dadurch sichtbar, aber
    folgenlos auf den Basiskanal zurück.
    """
    raw = data.get("rechercheplan")
    valid = isinstance(raw, dict)
    raw = raw if valid else {}
    raw_channels = raw.get("channels") if isinstance(raw.get("channels"), list) else []
    channels = [c for c in raw_channels
                if isinstance(c, str) and c in RESEARCH_CHANNELS]
    channels = list(dict.fromkeys(["decisions", *channels]))
    intent = raw.get("intent") if raw.get("intent") in RESEARCH_INTENTS else "overview"
    sort = raw.get("sort") if raw.get("sort") in RESEARCH_SORTS else "relevance"
    raw_needs = raw.get("needs") if isinstance(raw.get("needs"), list) else []
    needs = list(dict.fromkeys(
        n for n in raw_needs
        if isinstance(n, str) and n in RESEARCH_NEEDS
    ))
    return {"intent": intent, "channels": channels, "sort": sort,
            "needs": needs, "valid": valid}


_OFFICIAL_UPDATE_WORDS_RE = re.compile(
    r"\b(?:pressemitteilung(?:en)?|presseerkl(?:ä|ae)rung(?:en)?|"
    r"ver(?:ö|oe)ffentlicht(?:e|en)?|mitgeteilt|meldet|gemeldet|informiert(?:e|en)?)\b",
    re.IGNORECASE,
)
_OFFICIAL_SOURCE_RE = re.compile(
    r"\b(?:stadt(?:verwaltung)?|verwaltung|oberb(?:ü|ue)rgermeister(?:in)?)\b",
    re.IGNORECASE,
)
_EXPLICIT_DOCUMENT_RE = re.compile(
    r"(?:\bvorlage\b|\banlage\b|\b\w*(?:gutachten|studie|konzept)\b|"
    r"\bstellungnahme\b|\bbegr(?:ü|ue)nd\w*|"
    r"alternative\w*|technisch\w*|ausf(?:ü|ue)hrung|risik\w*|kriteri\w*|"
    r"umweltfolg\w*|wirtschaftlichkeits\w*|kostenannahm\w*|sachverhalt|"
    r"detail\w*|inhalt\w*|r(?:ä|ae)um\w*|umsetz\w*|untersuch\w*)\b",
    re.IGNORECASE,
)
_DECISION_METADATA_RE = re.compile(
    r"^\s*(?:wurde\b|was\s+wurde\b|wann\b|wer\b|welch(?:er|es)\s+(?:ausschuss|gremium)\b|"
    r"wie\s+lautete\s+das\s+abstimmungsergebnis\b|was\s+wurde\s+zuletzt\b|"
    r"welche\s+(?:beschl(?:ü|ue)sse|entscheidungen)\b|"
    r"was\s+hat\b.{0,100}\bbeschlossen\b)",
    re.IGNORECASE,
)
_EXPLICIT_DEBATE_RE = re.compile(
    r"(?:\b\w*debatte\b|\bdiskussion\b|\bwortbeitr(?:ag|äge|aeg)\b|"
    r"\bargument(?:e|ation)?\b|\bposition\b|\bhaltung\b|\bwas\s+sagte\b|"
    r"\bwer\s+sagte\b|\bwie\s+begr(?:ü|ue)ndete\b)",
    re.IGNORECASE,
)


def research_plan_with_mandatory(plan: dict, *, typ: str, question: str = "",
                                 person: bool = False,
                                 place: bool = False, sessions: bool = False,
                                 latest_decision: bool = False) -> dict:
    """LLM-Auswahl konsistent und mit harten Entitätskanälen machen.

    Das ist die zentrale Hybrid-Leitplanke: Ein expliziter Ort, eine Person
    oder Sitzung darf vom Modell nie weggeplant werden. Außerdem muss ein vom
    Modell erkannter Informationsbedarf technisch ausführbar sein: Wer Beträge
    braucht, braucht den Haushalt; wer Aussagen braucht, die Debatten usw.

    Umgekehrt sind Debatten bei einer engen Frage nach der neuesten
    Entscheidung nur Rauschen und werden dort entfernt. Im Shadow-Mode wird
    protokolliert, wo diese Konsistenzschicht eingegriffen hätte.
    """
    model_channels = list(dict.fromkeys(
        c for c in (plan.get("channels") or []) if c in RESEARCH_CHANNELS))
    mandatory = ["decisions"]
    # Manche klaren Finanzfragen klassifiziert das Modell sinnvoll als
    # ``topic`` (Prüfbericht, Pflichtaufgabe, Gebühren). Der deterministische
    # Quellenrouter erkennt sie trotzdem; der Rechercheplan muss dazu passen.
    finance_facets = geld_facetten(question, typ)
    if typ == "money" or finance_facets:
        mandatory.append("budget")
    if typ in ("person", "party") or person:
        mandatory.append("debates")
    if place:
        mandatory.append("places")
    if typ == "session" or sessions:
        mandatory.append("sessions")
    mandatory = list(dict.fromkeys(mandatory))

    need_channels = {
        "amounts": ("budget",),
        "statements": ("debates",),
        "locations": ("places",),
        "documents": ("documents",),
        # ``current_info`` allein sagt noch nicht, WO der aktuelle Stand
        # steckt. Die feineren Bedarfe verhindern, dass Presse und kommende
        # Beratungen bei jeder Aktualitätsfrage gemeinsam auflaufen.
        "official_updates": ("press",),
        "future_dates": ("future_agenda",),
    }
    model_needs = list(plan.get("needs") or [])
    inferred_needs: list[str] = []
    if (_OFFICIAL_UPDATE_WORDS_RE.search(question or "")
            and ("presse" in (question or "").lower()
                 or _OFFICIAL_SOURCE_RE.search(question or ""))
            and "official_updates" not in model_needs):
        # Kleine semantische Leitplanke für eindeutige Formulierungen. In der
        # Produktionsprobe ließ das Analysemodell „Was hat die Stadt zuletzt …
        # mitgeteilt?“ trotz klarer Quellenart ohne Pressekanal durch.
        inferred_needs.append("official_updates")
    needs = list(dict.fromkeys([*model_needs, *inferred_needs]))
    consistent = list(dict.fromkeys(
        channel
        for need in needs
        for channel in need_channels.get(need, ())
    ))
    selected = list(dict.fromkeys([*mandatory, *model_channels, *consistent]))

    suppressed: list[str] = []
    definition_only = bool(question and _DEFINITIONSFRAGE.match(question)
                           and not _EIGENES_PRAEDIKAT.search(question))
    if ("debates" in selected and "debates" not in mandatory
            and (latest_decision or definition_only
                 or (finance_facets and not _EXPLICIT_DEBATE_RE.search(question or "")))):
        selected.remove("debates")
        suppressed.append("debates")
    need_set = set(needs)
    if ("future_dates" in need_set and "official_updates" not in need_set
            and "press" in selected):
        # Eine kommende Beratung ist noch keine Verwaltungsneuigkeit. Das
        # Analysemodell wählte in 3/5 reinen Zukunftsfragen zusätzlich Presse,
        # obwohl es den feineren Bedarf ``future_dates`` korrekt erkannt hatte.
        selected.remove("press")
        suppressed.append("press")
    if "documents" not in need_set and "documents" in selected:
        # Kanal und Bedarf müssen bei Dokumenten bewusst zusammenpassen. Das
        # Modell setzte den Kanal in der Produktionsmatrix oft vorsorglich bei
        # einfachen Datums-/Abstimmungsfragen, ohne selbst einen Bedarf an
        # Dokumentinhalten zu erkennen.
        selected.remove("documents")
        suppressed.append("documents")
    elif ("documents" in selected and question
          and not _EXPLICIT_DOCUMENT_RE.search(question)
          and (typ in ("person", "party", "session")
               or latest_decision or definition_only or finance_facets
               or _DECISION_METADATA_RE.search(question))):
        # Das Analysemodell schwankt bei Metadatenfragen trotz klarer Prompt-
        # Regel: In wiederholten Produktionsläufen kamen „welcher Ausschuss?",
        # „welche Beschlüsse bisher?“ und ein konkreter Sitzungsrückblick mit
        # documents zurück. Solche Antworten stehen vollständig in Beschluss-
        # und Sitzungsdaten. Explizite Fachinhalte oben schützen echte
        # Dokumentfragen vor dieser Negativregel.
        selected.remove("documents")
        suppressed.append("documents")
    added = [c for c in selected if c not in model_channels]
    return {**plan, "channels": selected, "needs": needs,
            "model_channels": model_channels, "inferred_needs": inferred_needs,
            "mandatory_channels": mandatory, "consistency_added": added,
            "suppressed_channels": suppressed}


def research_channel_enabled(plan: dict, channel: str, *, fallback: bool = True) -> bool:
    """Darf ein einzelner Recherchekanal laut validiertem Plan laufen?

    Die Kanäle werden bewusst einzeln aktiviert. Ein ungültiger oder fehlender
    LLM-Plan behält mit ``fallback=True`` das bisherige Verhalten, damit ein
    Providerfehler keine Quellen verschwinden lässt.
    """
    if not plan.get("valid"):
        return fallback
    return channel in (plan.get("channels") or [])


def research_plan_log_record(question: str, plan: dict, typ: str,
                             observed: dict[str, int | bool]) -> dict:
    """Kompakter, auswertbarer und datensparsamer Shadow-Logeintrag.

    Der Fragetext wird bewusst NICHT geloggt: Gespräche speichert Ratslotse nur
    mit Einwilligung. Ein stabiler Kurz-Hash reicht, um wiederholte Fragen und
    Cache-Effekte zu erkennen.
    """
    normalized = " ".join((question or "").lower().split())
    fingerprint = hmac.new(_PLAN_HASH_KEY, normalized.encode("utf-8"),
                           hashlib.sha256).hexdigest()[:16]
    return {"event": "qa_research_plan_shadow", "question_hash": fingerprint,
            "qtype": typ, "plan": plan, "observed": observed}


def analyse_query(question: str, model: str = EXPAND_MODEL,
                  verlauf: list[dict] | None = None) -> dict:
    """{"question", "terms", "kind", "party"} zur Frage. ``question`` ist die
    EIGENSTÄNDIGE Fassung: Bei mitgegebenem Gesprächsverlauf (Chat) löst die
    Analyse Rückbezüge auf („Und was kostet das?" → „Was kostet der Neubau der
    Cäcilienbrücke?"), sonst bleibt sie die Original-Frage. Retrieval UND
    Reranker arbeiten mit dieser Fassung. Robust: bei kaputtem JSON oder
    LLM-Fehler kommt das Verhalten von vor dem Routing zurück."""
    fallback = {"question": question, "terms": question, "kind": "topic", "party": None,
                "variants": [], "eng": False, "rechercheplan": _research_plan({})}
    vtext = _verlauf_zeilen(verlauf)
    key = f"{model}|{hash(vtext)}|{' '.join(question.split()).lower()[:300]}"
    hit = _ANALYSE_CACHE.get(key)
    if hit is not None:
        return dict(hit)
    extra = {"extra_body": {"reasoning": {"enabled": False}}} if "deepseek" in model else {}
    try:
        block = f"\nBisheriges Gespräch (für Rückbezüge):\n{vtext}\n" if vtext else ""
        prompt = prompts.render("qa_analyse", question=question.strip()[:300], verlauf=block)
        resp = llm.chat_complete(
            model=model, _feature="qa_analysis", temperature=0, max_tokens=480,
            timeout=8.0, response_format={"type": "json_object"},
            messages=[{"role": "user", "content": prompt}], **extra,
        )
        data = json.loads(_strip_fences(resp.choices[0].message.content or ""))
        umgeschrieben = " ".join(str(data.get("question") or "").split())[:300]
        begriffe = " ".join(str(data.get("terms") or "").split())
        typ = str(data.get("kind") or "").strip().lower()
        party = (str(data.get("party")).strip() or None) if data.get("party") else None
        # Multi-Query (Task 32): Perspektiv-Umformulierungen füllen Lücken,
        # die die eine Expansion verfehlt („Wie ist der Stand?" findet keine
        # Finanzierungs-Beschlüsse). Kandidaten-Union passiert in hybrid_search.
        varianten = [" ".join(str(v).split())[:120]
                     for v in (data.get("variants") or []) if isinstance(v, str) and str(v).strip()][:2]
        # Punktfrage? („Wann wurde X beschlossen?") — dann antwortet das Modell
        # knapp statt mit Verlauf + Debatten-Absatz. Reist im ohnehin laufenden
        # Analyse-Call mit, kostet also keine zusätzliche Latenz.
        eng = bool(data.get("eng") is True)
        if typ not in QUERY_TYPES or typ in ("person", "session", "place"):
            # „person"/„session"/„place" setzt ausschließlich der Router
            # (deterministische Erkennung) — behauptet das Modell den Typ,
            # fehlt die Person bzw. die aufgelöste Sitzung.
            typ = "topic"
        if typ != "party":
            party = None
        out = {"question": umgeschrieben or question, "terms": begriffe or question,
               "kind": typ, "party": party, "variants": varianten, "eng": eng,
               "rechercheplan": _research_plan(data)}
        if begriffe:  # nur brauchbare Analysen cachen
            if len(_ANALYSE_CACHE) >= _EXPAND_CACHE_MAX:
                _ANALYSE_CACHE.pop(next(iter(_ANALYSE_CACHE)))
            _ANALYSE_CACHE[key] = dict(out)
        return out
    except Exception:  # noqa: BLE001
        return fallback


def sort_verlauf(candidates: list[dict]) -> list[dict]:
    """Chronik-Reihenfolge für Verlaufsfragen: älteste zuerst, damit die
    Antwort den Werdegang erzählen kann (das Relevanz-Ranking bleibt in der
    Quellen-Leiste sichtbar, nur der LLM-Kontext wird umsortiert)."""
    return sorted(candidates, key=lambda c: (c.get("session_date") or "", c.get("id") or 0))


# Typ-spezifische Zusatzregeln für das Antwort-Prompt (qa_antwort hat dafür
# den {extra_regeln}-Slot; alte Admin-Overrides ohne den Slot ignorieren den
# Parameter einfach — format() stört sich nicht an überzähligen kwargs).
# Punktfragen („Wann wurde X beschlossen?") bekommen eine knappe Antwort:
# Tims Befund 12.08. an einer echten Nutzer-Frage — dort folgten dem gesuchten
# Datum noch fünf Redebeiträge, nach denen niemand gefragt hatte. Die Regel
# ersetzt die Debatten-Pflicht (die im Debatten-Block steht) ausdrücklich.
ENG_REGEL = (
    "\n\nDIESE FRAGE IST ENG GESTELLT: Sie verlangt EINE Tatsache (Datum, Zahl, "
    "Name, Ja/Nein). Antworte in HÖCHSTENS 3 Sätzen, ohne Überschriften und ohne "
    "Aufzählung. Der ERSTE Satz beantwortet die Frage direkt; gibt es mehrere "
    "Stationen (Aufstellung, Entwurf, Satzung), nenne die MASSGEBLICHE zuerst — "
    "das ist der endgültige Beschluss, nicht ein Zwischenschritt. "
    "Nenne die Tatsache mit Beleg [id] und, wenn es zum Verständnis "
    "nötig ist, den einen wichtigsten Bezug (etwa die Bestätigung im Rat). "
    "KEIN Absatz zur Debatte, KEINE Vorgeschichte, KEINE Aufzählung weiterer "
    "Beschlüsse — auch dann nicht, wenn der Kontext mehr hergibt. Fehlt die "
    "Tatsache in den Quellen, sage das in einem Satz."
)

EXTRA_REGELN = {
    "topic": "",
    "history": (
        "Diese Frage zielt auf den VERLAUF: Erzähle chronologisch (die Beschlüsse "
        "stehen bereits älteste zuerst), nenne zu jeder Station das Datum — die "
        "Datums-Regel oben gilt für diese Frage NICHT — und ende mit dem aktuellen "
        "Stand. 4–8 Sätze sind hier angemessen."
    ),
    "party": (
        "Diese Frage zielt auf eine Fraktion/Gruppe: Stütze dich auf deren Anträge "
        "und Änderungsanträge (im Kontext als „Antrag von: …“ markiert) und auf "
        "ausdrücklich protokollierte Abstimmungssätze. WICHTIG: Das Ratsinfo kennt "
        "kein Stimmverhalten einzelner Fraktionen — behaupte NIE, wie eine Fraktion "
        "gestimmt hat, wenn es nicht wörtlich im Abstimmungssatz steht; sage dann, "
        "dass die Protokolle das nicht hergeben."
    ),
    # ACHTUNG, wer hier etwas ändert: Diese Regel ist für BESCHLUSS-Beträge
    # gebaut („Was hat Vorhaben X gekostet?"). Alles, was aus dem
    # Haushalts-Bestand kommt (Plan, Ist, Produkte, Prüfberichte, Konzern),
    # bekommt seine Regeln aus `geld_regeln()` — dynamisch, je nach dem, was
    # tatsächlich im Kontext steht. Die beiden Wege sind absichtlich getrennt:
    # Eine Frage kann Beschluss-Beträge wollen, Haushaltszahlen, oder beides.
    "money": (
        "Diese Frage zielt auf Beträge: Nenne die konkreten Summen aus den "
        "Beschlüssen (im Kontext als „Volumen: …“ markiert), gerundet und mit "
        "Einordnung, wofür das Geld ist. Tauchen zum selben Vorhaben mehrere "
        "Summen aus verschiedenen Jahren auf, benenne die Entwicklung mit "
        "Ausgangs- und Endwert samt Datum und zitiere beide Beschlüsse."
    ),
    "place": (
        "Diese Frage zielt auf EINEN KONKRETEN ORT aus dem Ratslotse-Ortskatalog. "
        "Im Kontext stehen nur Beschlüsse mit belegtem Bezug zu diesem Ort. "
        "Unterscheide den Ort von seinem größeren Ortsbereich und behaupte nicht, "
        "dass jeder Beschluss des Elternbereichs auch den kleineren Ort betrifft. "
        "Nenne bei einem Überblick die wichtigsten Vorgänge mit Datum und Ergebnis; "
        "ist der Bestand dünn, sage das ausdrücklich."
    ),
    # Personen-Fragetyp (10.08.26): deterministisch gesetzt, wenn die Frage
    # eine Ratsperson nennt — die Debatten-Zeilen sind dann deren Beiträge.
    "person": (
        "Diese Frage zielt auf EINE RATSPERSON: Stütze die Antwort vorrangig "
        "auf die Wortbeiträge dieser Person im Abschnitt AUS DEN RATSDEBATTEN "
        "(als „Laut Protokoll sagte …“, mit Datum und Gremium; nie mit [id]). "
        "Nenne beim ersten Mal die Fraktion, wie sie bei den Beiträgen steht. "
        "Beschlüsse dienen nur als Rahmen. Gibt es keine passenden Beiträge "
        "der Person, sage das ehrlich — erfinde keine Positionen."
    ),
    # Sitzungs-Fragetyp (25.08.26): deterministisch gesetzt, wenn die Frage
    # eine konkrete Sitzung nennt — deren Beschlüsse stehen dann vollständig
    # und in Sitzungs-Reihenfolge vorn im Kontext (Router).
    "session": (
        "Diese Frage zielt auf EINE KONKRETE SITZUNG (siehe Abschnitt ZUR "
        "GEFRAGTEN SITZUNG): Ihre Tagesordnungspunkte stehen — soweit ein "
        "Protokoll ausgewertet ist — VOLLSTÄNDIG und in Sitzungs-Reihenfolge "
        "am Anfang des Kontexts. Fragt die Frage allgemein, was beschlossen "
        "wurde: Gehe ALLE Punkte dieser Sitzung durch — jeden echten Beschluss "
        "mit einem Satz Inhalt und Ergebnis [id]; bloße Kenntnisnahmen und "
        "Berichte knapp, gern gesammelt in einem Absatz am Ende. Lass KEINEN "
        "Punkt der Sitzung weg — Vollständigkeit geht hier vor Auswahl. Fragt "
        "die Frage nach einem Aspekt (dem wichtigsten Beschluss, einem Thema, "
        "einer Abstimmung), beantworte gezielt nur ihn — du siehst die ganze "
        "Sitzung, es fehlt nichts. Beschlüsse aus ANDEREN Sitzungen gehören "
        "höchstens als knapper Bezug in die Antwort."
    ),
}


def expand_query(question: str, model: str = EXPAND_MODEL) -> str:
    """Turn a question into focused topical search terms. The raw question's
    boilerplate ("Was wurde zum … beschlossen?") dilutes the topic and retrieves
    generic decisions; expanded terms (e.g. "Radverkehr Fahrrad Radweg Fahrradstraße")
    retrieve far better. Falls back to the question on any error."""
    key = f"{model}|{' '.join(question.split()).lower()[:300]}"
    hit = _EXPAND_CACHE.get(key)
    if hit is not None:
        return hit
    extra = {"extra_body": {"reasoning": {"enabled": False}}} if "deepseek" in model else {}
    try:
        prompt = prompts.render("qa_suchbegriffe", question=question.strip()[:300])
        # timeout: Die Expansion steht auf dem kritischen Pfad VOR den Quellen —
        # ein hängender Provider darf nicht den SDK-Default (600 s!) ausreizen;
        # nach 8 s je Versuch ist die rohe Frage als Query der bessere Deal.
        resp = llm.chat_complete(
            model=model, _feature="qa_query_expansion", temperature=0, max_tokens=60,
            timeout=8.0, messages=[{"role": "user", "content": prompt}], **extra,
        )
        terms = " ".join((resp.choices[0].message.content or "").split())
        if terms:
            if len(_EXPAND_CACHE) >= _EXPAND_CACHE_MAX:
                _EXPAND_CACHE.pop(next(iter(_EXPAND_CACHE)))
            _EXPAND_CACHE[key] = terms
        return terms or question
    except Exception:  # noqa: BLE001
        return question


# ---- Akkuratheits-Paket (10.08.26): deterministische Signale neben der ----
# ---- Semantik — Entitäts-Anker, Recency-Intent, „ältere Station"-Marker ----

_RECENCY_RE = re.compile(
    r"\b(stand|aktuell\w*|derzeit\w*|momentan\w*|inzwischen|zurzeit|"
    r"jetzt|heute|zuletzt|neuest\w*|j[üu]ngst\w*)\b", re.IGNORECASE)
_HISTORISCH_RE = re.compile(r"\b(19|20)\d{2}\b")
_LATEST_RE = re.compile(
    r"\b(zuletzt|neueste[nmrs]?|j[üu]ngste[nmrs]?|letzte[nsr]?\s+beschl(?:uss|[üu]sse))\b",
    re.IGNORECASE,
)


def recency_intent(question: str) -> bool:
    """Fragt jemand nach dem HEUTIGEN Stand? Wortliste statt LLM-Feld —
    deterministisch, kostenlos, testbar. Eine konkrete Jahreszahl in der
    Frage schaltet den Bonus ab (wer nach 2019 fragt, will 2019)."""
    return bool(_RECENCY_RE.search(question)) and not _HISTORISCH_RE.search(question)


def latest_intent(question: str) -> bool:
    """Will die Frage ausdrücklich die zeitlich neuesten Entscheidungen?

    Enger als :func:`recency_intent`: Ein allgemeiner „aktueller Stand“ braucht
    weiterhin die fachlich relevantesten Stationen. Bei „zuletzt beschlossen“
    ist dagegen das Datum die eigentliche Antwort und darf nicht gegen den
    semantisch ähnlichsten älteren Titel verlieren.
    """
    return bool(_LATEST_RE.search(question or "")) and not _HISTORISCH_RE.search(question or "")


def latest_real_decision(candidates: list[dict]) -> dict | None:
    """Neueste tatsächliche Abstimmungsentscheidung im bereits chronologisch
    sortierten Ortsbestand.

    Berichte/Kenntnisnahmen und Vertagungen sind zwar Ratsvorgänge, beantworten
    aber nicht die Frage „Was wurde zuletzt beschlossen?“. Auch eine Ablehnung
    ist eine echte Entscheidung — die Antwort muss dann nur klar sagen, dass
    der Antrag gerade nicht beschlossen wurde.
    """
    return next((c for c in candidates
                 if c.get("outcome") in ("accepted", "rejected")), None)


def latest_place_answer(candidates: list[dict]) -> str:
    """Kurze, deterministische Antwort auf „zuletzt beschlossen“.

    Bei diesem engen Fragetyp ist das Datum selbst die gesuchte Information.
    Ein Sprachmodell darf deshalb weder einen älteren, wörtlich ähnlich
    betitelten Beschluss bevorzugen noch eine Kenntnisnahme als Beschluss
    ausgeben. ``candidates`` kommt aus dem Ortsindex und ist neueste zuerst.
    """
    if not candidates:
        return "Dazu habe ich keine Ratsvorgänge mit belegtem Ortsbezug gefunden."

    from council import ergebnisse   # spät: ergebnisse zieht kern.notify

    decision = latest_real_decision(candidates)
    if not decision:
        latest = candidates[0]
        date = _datum_de(latest.get("session_date"))
        title = " ".join(str(latest.get("title") or "Unbenannter Vorgang").split())[:300]
        return (
            "Einen angenommenen oder abgelehnten Beschluss habe ich dazu nicht gefunden. "
            f"Der jüngste Ratsvorgang war am {date}: „{title}“ "
            f"(Ergebnis: {ergebnisse.ERGEBNIS_WORT.get(latest.get('outcome') or '', 'nicht angegeben')})"
            f" [{latest['id']}]."
        )

    date = _datum_de(decision.get("session_date"))
    title = " ".join(str(decision.get("title") or "Unbenannter Beschluss").split())[:300]
    if decision.get("outcome") == "rejected":
        answer = (
            f"Die jüngste Abstimmungsentscheidung war am {date}: „{title}“ wurde "
            f"abgelehnt, also nicht beschlossen [{decision['id']}]."
        )
    else:
        answer = f"Am {date} wurde „{title}“ beschlossen [{decision['id']}]."

    # Ein neuerer Bericht ist nützlich, darf aber nie als neuerer „Beschluss“
    # erscheinen. Höchstens einen nennen, damit die Antwort kurz bleibt.
    newer = next((c for c in candidates
                  if c.get("id") != decision.get("id")
                  and (c.get("session_date") or "") > (decision.get("session_date") or "")), None)
    if newer:
        neuer_datum = _datum_de(newer.get("session_date"))
        neuer_titel = " ".join(str(newer.get("title") or "Unbenannter Vorgang").split())[:300]
        if newer.get("outcome") == "noted":
            answer += (
                f" Danach wurde am {neuer_datum} noch „{neuer_titel}“ zur Kenntnis "
                f"genommen [{newer['id']}]; das war kein neuer Beschluss."
            )
    return answer


def _falte(text: str) -> str:
    """Suchnormalisierung: Kleinschreibung, Umlaute ausgeschrieben, alles
    Nicht-Alphanumerische zu Leerzeichen — macht „Cäcilienbrücke",
    „Caecilienbruecke" und den Alias-Slug „caeci" vergleichbar."""
    text = text.lower()
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        text = text.replace(a, b)
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


# Namen, die in fast jeder Frage stecken und als Anker nur Rauschen wären.
_ANKER_STOPP = {"stadt", "oldenburg", "stadt oldenburg", "rat", "stadtrat"}


def finde_entitaeten(store, question: str, max_n: int = 2) -> list[dict]:
    """Deterministischer Frage-Anker: welche bekannten Entitäten (Themen-
    Seiten) nennt die Frage wörtlich? Matcht ganze Wörter auf gefalteten
    Namen UND den kuratierten Glossar-Aliassen (council_entity_aliases,
    source='glossar' — dieselbe Tabelle wie die Themen-Dubletten). Längere
    (spezifischere) Treffer zuerst, dann nach Beschlusszahl."""
    frage_f = f" {_falte(question)} "
    treffer: dict[int, tuple[int, int, str]] = {}
    for eid, name, n in store.entity_suchindex():
        name_f = _falte(name)
        # Mindestlänge 3 lässt kuratierte Kürzel („uni", „hbf") zu; generische
        # Kurzwörter fängt die Stoppliste.
        if len(name_f) < 3 or name_f in _ANKER_STOPP:
            continue
        if f" {name_f} " in frage_f:
            alt = treffer.get(eid)
            if alt is None or len(name_f) > alt[0]:
                treffer[eid] = (len(name_f), n, name)
    geordnet = sorted(treffer.items(), key=lambda kv: (-kv[1][0], -kv[1][1]))
    return [{"id": eid, "name": name} for eid, (_l, _n, name) in geordnet[:max_n]]


# Gruppen-Labels, die sich über die Personen-Stammdaten in Einzel-Parteien
# auflösen lassen. BEWUSST NUR FDP/Volt: „Für Oldenburg" führt das RIS selbst
# nur als Gruppe (Finke/Sander stehen so in den Stammdaten), und
# „Bündnis 90/Die Grünen" ist trotz Slash EINE Partei.
_AUFLOESBARE_GRUPPEN = {"FDP/Volt"}


def _nachname_gefaltet(name: str) -> str | None:
    """Letztes Namens-Token ohne Titel/Anreden — der kollisionsfreie Schlüssel
    (unter den 51 Ratspersonen gibt es keine doppelten Nachnamen)."""
    toks = [t for t in _falte(name).split()
            if t not in {"dr", "prof", "dipl", "ing", "med", "herr", "frau",
                         "ratsherr", "ratsfrau"}]
    return toks[-1] if toks else None


def parteien_aufloesen(store, rows: list[dict]) -> None:
    """FDP/Volt-Beiträge über den Sprecher in die EINZEL-Partei auflösen
    (Tims Standing-Punkt): Das Protokoll labelt nur die Gruppe, die
    Stammdaten kennen die Partei. Mutiert ``party`` in-place; ohne
    Stammdaten-Treffer bleibt das quellentreue Gruppen-Label stehen.
    Zeitlich bleibt alles korrekt — die Protokoll-Labels selbst sind die
    zeitrichtige Quelle (Höpken stand damals als Linke im Protokoll), hier
    wird nur INNERHALB einer bestehenden Gruppe verfeinert."""
    betroffen = [r for r in rows
                 if _fraktions_label(r.get("party")) in _AUFLOESBARE_GRUPPEN]
    if not betroffen:
        return
    try:
        mapping = {}
        for name, party in store.personen_suchindex():
            nn = _nachname_gefaltet(name)
            if nn:
                mapping[nn] = party
    except Exception:  # noqa: BLE001 — Auflösung ist Zusatz, nie Blocker
        return
    for r in betroffen:
        toks = _falte(r.get("speaker") or "").split()
        party = next((mapping[t] for t in reversed(toks) if t in mapping), None)
        if party:
            r["party"] = party


def protokolle_verlinken(store, rows: list[dict]) -> None:
    """Wortbeitrags-Zeilen um ``protokoll_url`` ergänzen (ksinr → getfile-URL
    des Protokoll-PDFs), damit der Beleg im Frontend nachlesbar wird. Mutiert
    in-place wie ``parteien_aufloesen``. Eine Seitenzahl gibt es bewusst
    nicht: Der gespeicherte Volltext kennt keine Seitengrenzen, und die
    Extraktion paraphrasiert — ein „#page=N" wäre geraten, nicht belegt."""
    try:
        urls = store.protokoll_urls_fuer([r.get("ksinr") for r in rows])
    except Exception:  # noqa: BLE001 — Verlinkung ist Zusatz, nie Blocker
        return
    for r in rows:
        r["protokoll_url"] = urls.get(r.get("ksinr"))


def finde_person(store, question: str) -> dict | None:
    """Personen-Fragetyp: Nennt die Frage eine Ratsperson (Voll- oder
    Nachname, umlaut-gefaltet, ganze Wörter)? Liefert
    {name, partei, nachname} — deterministisch, kostenlos."""
    try:
        index = store.personen_suchindex()
    except Exception:  # noqa: BLE001
        return None
    frage_f = f" {_falte(question)} "
    treffer: list[tuple[int, dict]] = []
    for name, party in index:
        name_f = _falte(name)
        nachname_f = _nachname_gefaltet(name)
        if not nachname_f or len(nachname_f) < 4:
            continue
        if f" {name_f} " in frage_f:
            laenge = len(name_f)
        elif f" {nachname_f} " in frage_f:
            laenge = len(nachname_f)
        else:
            continue
        # nachname im ORIGINAL (mit Umlauten): die Wortbeitrags-Suche macht
        # damit ihr LIKE — der gefaltete Schlüssel würde „Lükermann" im
        # Sprecher-Feld nie treffen (Faltung kennt keinen Rückweg).
        original = next((t for t in reversed(name.replace(".", " ").split())
                         if _falte(t) == nachname_f), name.split()[-1])
        treffer.append((laenge, {"name": name, "party": party, "nachname": original}))
    if not treffer:
        return None
    return max(treffer, key=lambda t: t[0])[1]


def finde_ort(question: str, store=None) -> dict | None:
    """Katalogort in einer Frage deterministisch erkennen.

    Längere Aliase gewinnen, sodass „Neu-Donnerschwee“ nicht zusätzlich als
    allgemeines „Donnerschwee“ behandelt wird.
    """
    from council import places

    catalog_places = store.all_places() if store is not None else None
    found = places.find_mentions(question, max_n=1, catalog_places=catalog_places)
    if not found:
        return None
    place = found[0]
    return {"id": place.id, "name": place.name, "kind": place.kind,
            "kind_label": places.kind_label(place.kind),
            "description": place.description}


def anker_ids_fuer(store, question: str) -> list[int]:
    """Bequemer Einzeiler für alle Aufrufer (Router, Deep-Research, Evals):
    erkannte Entitäten → deren Beschluss-ids, neueste zuerst. Leer bei
    Fehlern — der Anker ist Zusatz, nie Blocker."""
    try:
        ent = finde_entitaeten(store, question)
        return store.decision_ids_for_entities([e["id"] for e in ent]) if ent else []
    except Exception:  # noqa: BLE001
        return []


def steckbriefe_fuer(store, question: str, max_n: int = 2) -> list[dict]:
    """Kurzbeschreibungen der in der Frage genannten Entitäten.

    „Was ist die GSG, was macht sie?" (echte Nutzerfrage 11.08.) lässt sich aus
    Beschlüssen kaum beantworten — die dokumentieren Entscheidungen, nicht
    Hintergrund. Die Beschreibung dazu liegt fertig in ``council_entity_meta``.
    Leer bei Fehlern: Hintergrund ist Zusatz, nie Blocker.
    """
    try:
        ent = finde_entitaeten(store, question, max_n=max_n)
        return store.entity_steckbriefe([e["id"] for e in ent]) if ent else []
    except Exception:  # noqa: BLE001
        return []


# ---- Sitzungs-Fragetyp (25.08.26) ------------------------------------------
# „Was hat der Jugendhilfeausschuss am 17.06.2026 beschlossen?" lief bisher
# rein über die Ähnlichkeitssuche — die fand die drei Kita-TOPs und ließ die
# halbe Tagesordnung weg, darunter einen echten Beschluss (echte Nutzerfrage,
# 25.08.26). Nennt die Frage ein konkretes Sitzungsdatum oder die
# letzte/nächste Sitzung eines Gremiums, wird die Sitzung deterministisch
# über die Sitzungstabelle aufgelöst und ihre Beschlüsse kommen VOLLSTÄNDIG
# in den Kontext — nach dem Muster des Haushalts-Blocks (erkennen → gezielt
# laden → eigener Kontext-Block, vgl. haushalt_fuer_begriffe).

_MONATE = {"januar": 1, "februar": 2, "maerz": 3, "april": 4, "mai": 5,
           "juni": 6, "juli": 7, "august": 8, "september": 9, "oktober": 10,
           "november": 11, "dezember": 12}

# Numerische Daten stehen im ROHEN Fragetext — die Faltung wirft Punkte weg.
_DATUM_NUM_RE = re.compile(r"\b(\d{1,2})\.\s?(\d{1,2})\.(\d{4}|\d{2})?(?!\d)")
_DATUM_WORT_RE = re.compile(
    r"\b(\d{1,2})\.?\s+(januar|februar|m[aä]rz|april|mai|juni|juli|august|"
    r"september|oktober|november|dezember)(?:\s+(\d{4}))?\b", re.IGNORECASE)
# „seit dem 01.01.2024" ist eine ZEITSPANNE, kein Sitzungstermin.
_ZEITRAUM_PREP_RE = re.compile(
    r"\b(seit|bis|ab|vor|nach|zwischen)(\s+(dem|der|den|zum|zur))?\s*$", re.IGNORECASE)

# Relative Tagesangaben: „Um was geht es im Bauausschuss MORGEN?" ist eine
# Sitzungsfrage mit konkretem Datum — ohne diese Auflösung blieb sie eine
# Themen-Frage, und die Antwort strickte aus alten Beschlüssen verschiedener
# Jahre eine „voraussichtlich"-Prognose zusammen (Tims Befund 26.08., echte
# Frage am Vorabend einer echten Bauausschuss-Sitzung). „morgen" zählt nur
# als Tag, nicht als Tageszeit oder Gruß („Guten Morgen", „am Morgen früh").
_RELATIV_TAGE = {"vorgestern": -2, "gestern": -1, "heute": 0,
                 "morgen": 1, "uebermorgen": 2, "übermorgen": 2,
                 "vorgestrig": -2, "gestrig": -1, "heutig": 0,
                 "morgig": 1, "uebermorgig": 2, "übermorgig": 2}
# Substantive EXAKT („morgens" ist eine Tageszeit, kein Tag), Adjektive mit
# Endung: Die Frage-Analyse kondensiert „im Bauausschuss morgen" gern zu
# „am morgigen Tag" — ohne die Adjektiv-Formen fiel genau das durchs Raster
# (Tims Befund 26.08., zweiter Anlauf).
_RELATIV_RE = re.compile(
    r"\b(?:(vorgestern|gestern|heute|uebermorgen|übermorgen|morgen)|"
    r"(vorgestrig|gestrig|heutig|morgig|uebermorgig|übermorgig)\w*)\b",
    re.IGNORECASE)
_MORGEN_TAGESZEIT_RE = re.compile(
    r"\b(guten|am|jeden|den|diesen|des)\s*$", re.IGNORECASE)


def _datum_in_frage(question: str) -> tuple[str | None, str | None]:
    """(ISO-Datum, None) bei vollem Datum, (None, "-MM-DD") ohne Jahr,
    (None, None) ohne Fund. Eine Zeitraum-Präposition davor („seit dem …")
    disqualifiziert den Fund — das ist eine Spannen-, keine Terminangabe."""
    for m in list(_DATUM_NUM_RE.finditer(question)) + list(_DATUM_WORT_RE.finditer(question)):
        if _ZEITRAUM_PREP_RE.search(question[:m.start()]):
            continue
        tag, monat_raw = int(m.group(1)), m.group(2)
        monat = int(monat_raw) if monat_raw.isdigit() else _MONATE[_falte(monat_raw)]
        if not (1 <= tag <= 31 and 1 <= monat <= 12):
            continue
        if m.group(3):
            year = int(m.group(3))
            if year < 100:
                year += 2000
            return f"{year:04d}-{monat:02d}-{tag:02d}", None
        return None, f"-{monat:02d}-{tag:02d}"
    for m in _RELATIV_RE.finditer(question):
        if _ZEITRAUM_PREP_RE.search(question[:m.start()]):
            continue  # „bis heute", „seit gestern", „ab morgen" sind Spannen
        wort = (m.group(1) or m.group(2)).lower()
        if wort == "morgen" and _MORGEN_TAGESZEIT_RE.search(question[:m.start()]):
            continue  # „Guten Morgen …", „am Morgen" — Gruß/Tageszeit, kein Tag
        from datetime import date as _date, timedelta as _timedelta
        return (_date.today() + _timedelta(days=_RELATIV_TAGE[wort])).isoformat(), None
    return None, None


#: Gefaltete Kurzformen → gefaltetes Fragment des amtlichen Gremiumsnamens.
#: Fragmente statt Vollnamen, weil sich die amtlichen Namen über die Jahre
#: ändern („… Digitalisierung …" kam beim Wirtschaftsausschuss dazu) — das
#: Fragment matcht beide Fassungen in der Sitzungstabelle.
_GREMIUM_ALIASE = {
    "bauausschuss": "stadtplanung und bauen",
    "planungsausschuss": "stadtplanung und bauen",
    "stadtplanungsausschuss": "stadtplanung und bauen",
    "umweltausschuss": "stadtgruen umwelt und klima",
    "klimaausschuss": "stadtgruen umwelt und klima",
    "finanzausschuss": "finanzen und beteiligungen",
    "wirtschaftsausschuss": "wirtschaftsfoerderung",
    "digitalisierungsausschuss": "wirtschaftsfoerderung",
    "integrationsausschuss": "integration und migration",
    "migrationsausschuss": "integration und migration",
    "abfallausschuss": "abfallwirtschaftsbetrieb",
    "hochbauausschuss": "gebaeudewirtschaft",
    "bahnausschuss": "bahnangelegenheiten",
}


def _gremium_genannt(name_f: str, frage_f: str) -> bool:
    """Steht der gefaltete Name als eigene Wortfolge in der gefalteten Frage?
    Jedes Wort darf eine Genitiv-Endung tragen — „des VerkehrsausschussES",
    „des AusschussES für Stadtplanung und Bauen"."""
    muster = " " + " ".join(re.escape(t) + "(?:es|s)?" for t in name_f.split()) + " "
    return re.search(muster, frage_f) is not None


def _gremium_in_frage(store, question: str) -> str | None:
    """Gefaltetes Namens-Fragment des gefragten Gremiums, ``"rat"`` fürs
    Plenum, None ohne Gremium. Vollnamen kommen aus dem Bestand (sie ändern
    sich über die Jahre), Kurzformen („Bauausschuss") aus der Alias-Tabelle.
    „Rat"/„Stadtrat" allein ist bewusst NUR ein Gremium-Signal — den Ausschlag
    gibt erst das Datum bzw. die Sitzungs-Phrase (finde_sitzungen)."""
    frage_f = f" {_falte(question)} "
    beste: str | None = None
    try:
        namen = store.get_all_committee_names()
    except Exception:  # noqa: BLE001
        namen = []
    for name in namen:
        name_f = _falte(name)
        if name_f != "rat" and len(name_f) > len(beste or "") \
                and _gremium_genannt(name_f, frage_f):
            beste = name_f
    if beste:
        return beste
    for kurz, fragment in _GREMIUM_ALIASE.items():
        if _gremium_genannt(kurz, frage_f):
            return fragment
    if re.search(r" (stadt)?rat(s|es|ssitzung|sversammlung)? ", frage_f):
        return "rat"
    return None


def _gremium_passt(fragment: str, committee: str | None) -> bool:
    c = _falte(committee or "")
    # Das Plenum heißt schlicht „Rat" — als Substring träfe es jeden Ausschuss.
    return c == "rat" if fragment == "rat" else fragment in c


# Sitzungs-Anlass: Ein Datum allein macht noch keine Sitzungsfrage („Der
# Bericht vom 12.06. sagt …") — es braucht ein Gremium oder ein Sitzungswort.
_SITZUNG_ANLASS_RE = re.compile(
    r"\b(sitzung\w*|beschloss\w*|beschluss\w*|beschluesse\w*|entschied\w*|"
    r"entscheidung\w*|tagesordnung\w*|getagt|tagte?n?|beraten|abgestimmt|"
    r"ergebnis\w*)\b")
_SITZUNG_ZURUECK_RE = re.compile(
    r"\b(letzt\w*|juengst\w*|vergangen\w*|vorig\w*)\s+(rats)?sitzung\b|\bzuletzt\b")
_SITZUNG_VORAUS_RE = re.compile(
    r"\b(naechst\w*|kommend\w*)\s+((rats)?sitzung\w*|mal)\b|\bwann\s+tagt\b|"
    r"\btagesordnung\w*\b")

#: Mehr als 3 Sitzungen (ein Tag mit vollem Kalender) beantwortet niemand
#: sinnvoll in einer Antwort.
_SITZUNGEN_MAX = 3


def finde_sitzungen(store, question: str) -> list[dict]:
    """Sitzungs-Fragetyp: Nennt die Frage ein konkretes Sitzungsdatum („am
    17.06.2026", „17. Juni") oder die letzte/nächste Sitzung eines Gremiums?
    Liefert die gemeinten Sitzungen, jede mit ``beschluss_ids`` in
    Tagesordnungs-Reihenfolge und — solange es keine Beschlüsse gibt — der
    Tagesordnung. Deterministisch wie finde_person; leer bei Fehlern, der
    Sitzungs-Anker ist Zusatz, nie Blocker."""
    try:
        return _finde_sitzungen(store, question)
    except Exception:  # noqa: BLE001
        return []


def _finde_sitzungen(store, question: str) -> list[dict]:
    from datetime import date as _date
    heute = _date.today().isoformat()
    date, monat_tag = _datum_in_frage(question)
    committee = _gremium_in_frage(store, question)
    frage_f = _falte(question)
    rows: list[dict] = []
    if (date or monat_tag) and not committee and not _SITZUNG_ANLASS_RE.search(frage_f):
        return []
    if date:
        rows = [r for r in store.sessions_on(date)
                if committee is None or _gremium_passt(committee, r.get("committee"))]
    elif monat_tag:
        # Ohne Jahr: die jüngste vergangene Sitzung an diesem Monatstag —
        # gibt es nur künftige, die nächstliegende.
        alle = [r for r in store.sitzungen_am_monatstag(monat_tag)
                if committee is None or _gremium_passt(committee, r.get("committee"))]
        vergangene = [r for r in alle if str(r.get("session_date") or "") <= heute]
        rows = vergangene[:1] if vergangene else sorted(
            alle, key=lambda r: str(r.get("session_date") or ""))[:1]
        if rows and committee is None:
            # Datum ohne Gremium meint den TAG — alle Sitzungen dieses Tages.
            rows = store.sessions_on(rows[0]["session_date"])
    elif committee and _SITZUNG_ZURUECK_RE.search(frage_f):
        rows = [r for r in store.recent_sessions(limit=80)
                if _gremium_passt(committee, r.get("committee"))][:1]
        if rows and not store.decision_ids_der_sitzung(rows[0]["ksinr"]):
            # Trägt die jüngste Sitzung noch kein ausgewertetes Protokoll,
            # gehört die letzte MIT Beschlüssen dazu — die Antwort kann dann
            # beides ehrlich benennen statt stumm leer auszugehen.
            for r in store.recent_sessions(limit=80):
                if _gremium_passt(committee, r.get("committee")) \
                        and store.decision_ids_der_sitzung(r["ksinr"]):
                    rows.append(r)
                    break
    elif committee and _SITZUNG_VORAUS_RE.search(frage_f):
        rows = [r for r in store.upcoming_sessions(limit=40)
                if _gremium_passt(committee, r.get("committee"))][:1]
    out: list[dict] = []
    for r in rows[:_SITZUNGEN_MAX]:
        s = {"ksinr": r.get("ksinr"), "committee": r.get("committee"),
             "session_date": r.get("session_date"),
             "session_time": r.get("session_time"), "location": r.get("location"),
             "kuenftig": str(r.get("session_date") or "") > heute}
        # Terminierte Kalender-Einträge (upcoming) haben noch kein ksinr.
        s["beschluss_ids"] = (store.decision_ids_der_sitzung(s["ksinr"])
                              if s["ksinr"] else [])
        if not s["beschluss_ids"]:
            agenda = store.agenda_items(s["ksinr"]) if s["ksinr"] else []
            # Der Kartentext zuerst: Er entsteht aus Vorlage UND Anlagen und
            # sagt deshalb, WAS beantragt ist („110 Wohneinheiten auf 8,6
            # Hektar"). Die Kurzfassung kennt nur den Titel und formuliert ihn
            # um — als Antwortgrundlage ist das der schwächere Satz.
            s["agenda"] = [{"item_number": a.get("item_number"),
                            "title": a.get("title"),
                            "summary": a.get("social_text") or a.get("summary")}
                           for a in agenda]
        out.append(s)
    return out


#: Tagesordnungen großer Rats-Sitzungen haben >40 TOPs — mehr Zeilen braucht
#: der Block nicht, um die Frage nach dem Anstehenden zu beantworten.
_SITZUNG_AGENDA_MAX = 40


def _sitzungen_block(sitzungen: list[dict] | None) -> str:
    """Kontext-Absatz zur aufgelösten Sitzung (Sitzungs-Fragetyp): Termin, Ort
    und — solange kein Protokoll ausgewertet ist — die Tagesordnung. KEINE
    Beschlüsse: nie mit [id] zitieren, sondern „Laut Sitzungskalender …"."""
    if not sitzungen:
        return ""
    zeilen = []
    for s in sitzungen:
        kopf = (f"- {s.get('committee') or 'Sitzung'} am "
                f"{_datum_de(s['session_date']) if s.get('session_date') else '?'}")
        if s.get("session_time"):
            kopf += f" um {s['session_time']} Uhr"
        if s.get("location"):
            kopf += f" ({s['location']})"
        n = len(s.get("beschluss_ids") or [])
        if n:
            kopf += (f": Alle {n} Tagesordnungspunkte samt Ergebnis stehen oben "
                     "im Kontext, in der Reihenfolge der Sitzung.")
        elif s.get("kuenftig"):
            kopf += ": Diese Sitzung steht noch BEVOR — Beschlüsse gibt es noch nicht."
        else:
            # Der Verzug ist der NORMALFALL, kein Datenloch: Die Stadt
            # veröffentlicht Protokolle erst Wochen nach dem Termin (gemessen
            # 1–2 Monate). Wer nach einer vergangenen Sitzung fragt, erwartet
            # aber ein Protokoll — ohne die Erklärung liest sich das Fehlen
            # wie ein Fehler von Ratslotse (Tims Hinweis 26.08.).
            kopf += (": Zu dieser Sitzung liegt noch kein ausgewertetes "
                     "Protokoll vor — die Stadt veröffentlicht Protokolle in "
                     "der Regel erst einige Wochen bis ein, zwei Monate nach "
                     "dem Termin. Erkläre in der Antwort ausdrücklich, dass "
                     "das der normale Ablauf und kein Fehler ist.")
        zeilen.append(kopf)
        for a in (s.get("agenda") or [])[:_SITZUNG_AGENDA_MAX]:
            row = f"  · TOP {a.get('item_number') or '?'}: {(a.get('title') or '')[:160]}"
            if a.get("summary"):
                row += f" — {' '.join(a['summary'].split())[:200]}"
            zeilen.append(row)
    return ("\nZUR GEFRAGTEN SITZUNG (aus dem Sitzungskalender — Termin und "
            "Tagesordnung als „Laut Sitzungskalender …“ nennen, NIE mit [id]):\n"
            + "\n".join(zeilen) + "\n"
            "Liegen zur gefragten Sitzung noch keine Beschlüsse vor, sage das "
            "ehrlich als Erstes — Beschlüsse ANDERER Sitzungen aus dem Kontext "
            "sind dann NICHT die Antwort.\n")


def sitzungs_leer_text(sitzungen: list[dict]) -> str:
    """Ehrliche Antwort ohne LLM, wenn die gefragte Sitzung aufgelöst ist, aber
    weder Beschlüsse noch passende Kandidaten existieren — sonst bekäme eine
    Frage nach einer protokolllosen Sitzung das pauschale „nichts gefunden"."""
    s = sitzungen[0]
    name = s.get("committee") or "Das Gremium"
    date = _datum_de(s["session_date"]) if s.get("session_date") else "unbekanntem Datum"
    roh = [a for a in (s.get("agenda") or []) if (a.get("title") or "").strip()]
    try:
        # Der Anriss nennt INHALTE, keine Formalien (Beschlussfähigkeit,
        # Protokoll-Genehmigung) — derselbe Filter wie in der Wochenvorschau.
        from .store import CouncilStore
        inhalt = [a for a in roh if not CouncilStore._FORMALIE_RE.search(a["title"])]
    except Exception:  # noqa: BLE001 — Filter ist Zusatz, nie Blocker
        inhalt = roh
    tops = [f"„{a['title'].strip()}“" for a in (inhalt or roh)[:3]]
    to = f" Auf der Tagesordnung: {', '.join(tops)}." if tops else ""
    if s.get("kuenftig"):
        return (f"{name} tagt erst am {date} — Beschlüsse gibt es von dieser "
                f"Sitzung also noch nicht.{to}")
    return (f"{name} hat am {date} getagt, aber das Protokoll liegt noch "
            f"nicht vor — die Stadt veröffentlicht Protokolle in der Regel "
            f"erst einige Wochen bis ein, zwei Monate nach dem Termin. Das "
            f"ist der normale Ablauf, kein Fehler. Sobald das Protokoll da "
            f"ist, wertet Ratslotse es automatisch aus.{to}")


#: Ab wann gilt die Beleglage als tragfähig? Am Prod-Bestand gemessen und
#: nachjustiert: Entscheidend ist NICHT der Bestwert allein, sondern ob es
#: überhaupt Volltreffer gibt. „Straßenbahn" kommt auf sechs mittelmäßige
#: Treffer (bester 0,61) und ist trotzdem dünn; „Stadion" hat Volltreffer.
#: Erste Fassung ging über den Bestwert — die stufte die Straßenbahn-Frage
#: fälschlich als solide ein.
BELEG_STARK = 0.5        # zählt als brauchbarer Treffer
BELEG_VOLLTREFFER = 0.7  # zählt als klarer Treffer
BELEG_MIN_TREFFER = 3
BELEG_MIN_BESTWERT = 0.75  # ohne Volltreffer muss wenigstens einer nah dran sein


def beleglage(candidates: list[dict]) -> str:
    """„solide" oder „duenn" — wie tragfähig sind die gefundenen Beschlüsse?

    Rein deterministisch aus den Rerank-Scores. Der Zweck ist Ehrlichkeit: Das
    einzige Nutzer-👎 mit Begründung („Falschinfo", Giftmüll am Fliegerhorst)
    traf eine Frage mit genau dieser Signatur — wenige, schwache Treffer, aber
    eine Antwort im selben selbstbewussten Ton wie sonst.
    """
    werte = [c.get("score") or 0 for c in candidates]
    if not werte:
        return "duenn"
    stark = sum(1 for w in werte if w >= BELEG_STARK)
    volltreffer = sum(1 for w in werte if w >= BELEG_VOLLTREFFER)
    if stark < BELEG_MIN_TREFFER:
        return "duenn"
    if volltreffer == 0 and max(werte) < BELEG_MIN_BESTWERT:
        return "duenn"
    return "solide"


def _steckbrief_block(steckbriefe: list[dict] | None) -> str:
    """Hintergrundwissen zu den genannten Objekten — beantwortet „Was ist X?",
    ist aber KEIN Beschluss und darf deshalb nie eine [id] bekommen."""
    if not steckbriefe:
        return ""
    zeilen = "\n".join(
        f"- {s['name']}: {' '.join((s.get('description') or '').split())[:400]}"
        for s in steckbriefe[:2])
    return ("\nHINTERGRUND zu den genannten Objekten (aus den Ratsunterlagen "
            "zusammengefasst — nutze es, um zu erklären, WORUM es geht, wenn die "
            "Frage danach verlangt; NIE mit [id] zitieren, es ist kein "
            "Beschluss):\n" + zeilen + "\n")


def _vorlage_basis(nr: str | None) -> str | None:
    """„26/0100-1" → „26/0100": Revisionen hängen ein Zähler-Suffix an."""
    if not nr or not str(nr).strip():
        return None
    return re.sub(r"-\d+$", "", str(nr).strip())


def markiere_veraltete(store, candidates: list[dict],
                       kandidaten_ids: set[int] | None = None) -> None:
    """„Ältere Station"-Marker: Läuft dieselbe Vorlage (gleiches kvonr oder
    gleiche Revisions-Familie der Vorlagen-Nummer) später noch einmal durch
    ein Gremium, bekommt der ältere Kandidat ``neuere_station`` — der Kontext
    sagt dem Modell damit, was der geltende Stand ist, statt es raten zu
    lassen. Die jüngste Station selbst bleibt unmarkiert; die id des neueren
    Beschlusses steht nur dabei, wenn er selbst im Kandidatenset liegt (nur
    dann ist er als [id] zitierbar)."""
    if kandidaten_ids is None:
        kandidaten_ids = {c["id"] for c in candidates}
    kvonrs = [c.get("kvonr") for c in candidates if c.get("kvonr")]
    basen = [b for b in (_vorlage_basis(c.get("template_number")) for c in candidates) if b]
    if not kvonrs and not basen:
        return
    try:
        rows = store.neueste_stationen_fuer(kvonrs, basen)
    except Exception:  # noqa: BLE001 — Marker ist Zusatz, nie Blocker
        return
    for c in candidates:
        eigenes_datum = str(c.get("session_date") or "")
        if not eigenes_datum:
            continue
        gruppe = [r for r in rows if r["id"] != c["id"] and (
            (c.get("kvonr") and r.get("kvonr") == c.get("kvonr"))
            or (_vorlage_basis(c.get("template_number"))
                and _vorlage_basis(r.get("template_number")) == _vorlage_basis(c.get("template_number"))))]
        juengere = [r for r in gruppe if str(r.get("session_date") or "") > eigenes_datum]
        if not juengere:
            continue
        top = max(juengere, key=lambda r: str(r.get("session_date") or ""))
        c["neuere_station"] = {
            "id": top["id"] if top["id"] in kandidaten_ids else None,
            "date": top.get("session_date"), "committee": top.get("committee"),
        }


def _build_context(candidates: list[dict]) -> str:
    """Eine Zeile pro Beschluss: id, Titel, Gremium, Datum, Ergebnis + Kern des
    Beschlusstexts. 450 Zeichen statt 200 und die Metadaten machen die Antworten
    spürbar konkreter — bei ~20 Kandidaten immer noch nur wenige Cent. Wenn der
    Aufrufer einen Vorlagen-Auszug (Sachverhalt/Begründung) beigelegt hat, kommt
    der mit — das ist das *Warum* hinter dem Beschluss. Bei strittigen
    Abstimmungen kommt der Original-Abstimmungssatz (raw_result) dazu — dort
    stehen oft die Fraktionen der Gegenstimmen, womit „Wer stimmte dagegen?"
    beantwortbar wird. Der Tragweite-Score (RL-U16) wird als Hinweis angehängt,
    aber NUR an den Enden der Skala: „hoch" samt Begründung lässt die Antwort
    mit dem Folgenreichen führen, „gering" lässt sie Formalien (Berufungen,
    Kenntnisnahmen) überspringen — das Relevanz-Ranking selbst bleibt davon
    unberührt."""
    lines = []
    for c in candidates:
        # Datum deutsch: das Modell übernimmt Formate aus dem Kontext wörtlich,
        # ein ISO-Datum landet sonst als „am 2026-06-01" in der Antwort.
        date = _datum_de(c["session_date"]) if c.get("session_date") else None
        meta = " · ".join(p for p in (c.get("committee"), date, c.get("outcome")) if p)
        body = (c.get("summary") or c.get("official_text") or "").strip()[:450]
        vorlage = (c.get("vorlage_excerpt") or "").strip()
        suffix = f" — Aus der Vorlage: {vorlage}" if vorlage else ""
        applicants = _factions_of(c)
        if applicants:
            suffix += f" — Antrag von: {', '.join(applicants)}"
        strittig = (c.get("no_votes") or 0) > 0 or (c.get("abstentions") or 0) > 0 \
            or c.get("vote") == "majority" or c.get("outcome") == "rejected"
        raw_result = (c.get("raw_result") or "").strip()
        if strittig and raw_result:
            suffix += f" — Abstimmung: {raw_result[:180]}"
        if c.get("amount_eur"):
            suffix += f" — Volumen: {c['amount_eur']:,.0f} €".replace(",", ".")
        if c.get("beteiligung"):
            suffix += (f" — BÜRGERBETEILIGUNG LÄUFT: {c['beteiligung']} "
                       f"(Stellungnahme auf oldenburg.planungsbeteiligung.de möglich — "
                       f"erwähne das in der Antwort, wenn es zur Frage passt)")
        if c.get("office"):
            suffix += f" — Federführung: {c['office']}"
        # Bei Ortsfragen ist nicht nur wichtig, DASS ein Beschluss im
        # gefilterten Pool liegt, sondern WARUM. Die Fundstelle stammt aus dem
        # Beschluss/der Vorlage und macht die Zuordnung auch für das Modell
        # nachvollziehbar, statt den Ortsbezug aus dem Titel raten zu lassen.
        location_matches = c.get("location_matches") or []
        if location_matches:
            match = location_matches[0]
            ort_name = str(match.get("name") or "").strip()
            evidence = str(match.get("evidence") or "").strip()
            if ort_name:
                suffix += f" — Ortsbezug: {ort_name}"
                if evidence:
                    suffix += f"; Fundstelle: {evidence[:220]}"
        # Klima-Check nur bei „prüfungsrelevant: Ja" — die Nein-Floskeln würden
        # den Kontext füllen, ohne einer Antwort je zu helfen (Regex-Ernte).
        if ernte.klima_relevant(c.get("climate_impact")):
            suffix += f" — Klima-Check der Verwaltung: {c['climate_impact'][:200]}"
        if c.get("deviation") == "strong":
            suffix += " — Der Rat wich deutlich vom Beschlussvorschlag der Verwaltung ab"
        impact = c.get("impact")
        if impact is not None and impact >= 70:
            # NUR das Label, nie die Begründung: `impact_reason` ist ein von
            # uns erzeugter Bewertungssatz. Im Kontext gelesen, sah er aus wie
            # eine Feststellung aus dem Rathaus und landete als solche in einer
            # Antwort („Dieser Beschluss wird als weitreichend … eingestuft" —
            # Prüfung der Fliegerhorst-Antwort vom 10.08.26). Das Label lenkt
            # die Gewichtung genauso, ist aber kein zitierfähiger Satz.
            suffix += " — Tragweite: hoch"
        elif impact is not None and impact <= 15:
            suffix += " — Tragweite: gering (Formalie)"
        # Akkuratheits-Paket: dieselbe Vorlage lief SPÄTER noch einmal durch
        # ein Gremium — das Modell soll den älteren Stand nie als aktuell
        # verkaufen (markiere_veraltete setzt das Feld deterministisch).
        ns = c.get("neuere_station")
        if ns and ns.get("date"):
            verweis = f", siehe [{ns['id']}]" if ns.get("id") else ""
            committee = f" ({ns['committee']})" if ns.get("committee") else ""
            suffix += (f" — ⚠ ÄLTERE STATION: Zu dieser Vorlage gibt es eine NEUERE Station "
                       f"vom {_datum_de(ns['date'])}{committee}{verweis} — "
                       f"die neuere gilt als aktueller Stand")
        lines.append(f"[{c['id']}] {(c.get('title') or '').strip()} ({meta}): {body}{suffix}")
    return "\n".join(lines) or "(keine passenden Beschlüsse gefunden)"


def _factions_of(c: dict) -> list[str]:
    """Antragstellende Fraktionen eines Beschlusses (factions-Spalte, JSON-Array
    oder schon geparst) — leer bei Verwaltungsvorlagen."""
    raw = c.get("factions")
    if isinstance(raw, str) and raw.strip():
        try:
            raw = json.loads(raw)
        except ValueError:
            return []
    return [str(f).strip() for f in raw or [] if str(f).strip()]


def deep_zerlege(question: str, model: str = EXPAND_MODEL) -> list[dict]:
    """Deep Research (Task 34): Frage → 3-5 Recherche-Facetten
    [{name, frage, begriffe}]. Fallback: eine Facette = die Frage selbst."""
    fallback = [{"name": "Gesamtbild", "question": question, "terms": question}]
    extra = {"extra_body": {"reasoning": {"enabled": False}}} if "deepseek" in model else {}
    try:
        resp = llm.chat_complete(
            model=model, _feature="deep_decomposition", temperature=0, max_tokens=500,
            timeout=12.0, response_format={"type": "json_object"},
            messages=[{"role": "user", "content": prompts.render("deep_zerlegung",
                                                                 question=question.strip()[:300])}],
            **extra)
        data = json.loads(_strip_fences(resp.choices[0].message.content or ""))
        facetten = []
        for f in (data.get("facetten") or [])[:5]:
            if not isinstance(f, dict):
                continue
            fr = " ".join(str(f.get("question") or "").split())[:200]
            if not fr:
                continue
            facetten.append({
                "name": " ".join(str(f.get("name") or "Facette").split())[:40],
                "question": fr,
                "terms": " ".join(str(f.get("terms") or fr).split())[:200],
            })
        return facetten or fallback
    except Exception:  # noqa: BLE001
        return fallback


#: Wie viel einer Anlagen-Fundstelle in den Prompt darf.
#:
#: Stand bis 20.08.2026 auf 500 — unterhalb dessen, was die Suche überhaupt
#: liefert. Gemessen an „Mobilitätsplan Oldenburg 2030": Alle sechs
#: Fundstellen kamen mit rund 1.100 Zeichen und wurden allesamt gekappt, also
#: flog über die Hälfte des Materials weg, kurz bevor das Modell es sah.
#:
#: Das ist teuer, weil Anlagen die fachliche Substanz tragen (siehe unten) —
#: eine gewöhnliche Vorlage bekommt im selben Prompt 4.000 Zeichen. Sechs
#: Anlagen zu 1.200 sind 7.200 Zeichen neben rund 40.000 aus den Vorlagen.
ANLAGEN_ZEICHEN = 1200


def _anlagen_block(anlagen: list[dict] | None) -> str:
    """Fundstellen aus Anlagen (Gutachten, Konzepte, Stellungnahmen) — nur im
    Dokumentenkanal der schnellen oder gründlichen Recherche.

    Anlagen sind keine Beschlüsse und tragen deshalb keine [id]. Sie bekommen
    einen eigenen Marker ``[A<n>]``; ``n`` ist die Position in dieser Liste und
    kommt aus ``nr`` (der Deep-Job vergibt sie, damit Prompt und Karten-Liste im
    Frontend garantiert dieselbe Zählung benutzen). Das Frontend rendert daraus
    die kleinen Buchstaben-Fußnoten a, b, c … — vorher stand die Anlage nur als
    Prosa im Text und war von der Karte rechts nicht zu unterscheiden.
    """
    if not anlagen:
        return ""
    # Dieselbe Datei liegt im Bestand teils zweimal (getrennt hochgeladen,
    # eigene document_id, gleicher Titel). Ohne diese Prüfung verbraucht sie
    # zwei der sechs Plätze — am 20.08.2026 bei „Mobilitätsplan" passiert.
    gesehen: set[str] = set()
    frisch = []
    for a in anlagen:
        mark = " ".join(str(a.get("label") or "").split()).lower()[:60]
        if mark and mark in gesehen:
            continue
        gesehen.add(mark)
        frisch.append(a)
    zeilen = "\n".join(
        f"[A{a.get('nr') or i + 1}] {a.get('label') or 'Anlage'} "
        f"(zur Vorlage {a.get('template_number') or '?'}"
        f"{' — ' + a['vorlage_titel'][:80] if a.get('vorlage_titel') else ''}): "
        f"{(a.get('citation') or '').strip()[:ANLAGEN_ZEICHEN]}"
        for i, a in enumerate(frisch))
    return ("\nAUS DEN ANLAGEN (Gutachten, Konzepte, Stellungnahmen zu den Vorlagen —\n"
            "oft die fachliche Substanz hinter einem Beschluss). Nutze sie für Details\n"
            "und Zahlen und belege JEDE daraus übernommene Aussage mit dem Marker,\n"
            "der vor der Anlage steht ([A1], [A2] …) — NIE mit [id]:\n"
            f"{zeilen}\n")


def _planungen_block(planungen: list[dict] | None) -> str:
    """Geplante Beratungsstationen der zitierten Vorlagen — der „Wie es
    weitergeht"-Stoff des Berichts (Beratungsfolgen werden täglich gepflegt,
    tauchten in Antworten aber nie auf)."""
    if not planungen:
        return ""
    zeilen = "\n".join(
        f"- {p.get('vorlage_titel') or p.get('template_number')}: {p.get('committee')} am "
        f"{_datum_de(p.get('date'))}" for p in planungen[:8])
    return ("\nGEPLANTE NÄCHSTE STATIONEN (aus den Beratungsfolgen — für den Abschnitt "
            "„Wie es weitergeht“; als Termin nennen, NIE mit [id]):\n" + zeilen + "\n")


def deep_bericht_stream(question: str, candidates: list[dict],
                        presse: list[dict] | None = None,
                        debatten: list[dict] | None = None,
                        haushalt: list[dict] | None = None,
                        planungen: list[dict] | None = None,
                        anlagen: list[dict] | None = None,
                        model: str = MODEL,
                        taxes: list[dict] | None = None,
                        tax_capacity: dict | None = None,
                        geld: dict | None = None):
    """Der lange Deep-Research-Bericht als Token-Stream (Task 34).

    ``geld`` ist der vollständige Haushalts-Kontext aus ``geld_kontext``; die
    drei Einzel-Parameter bleiben als alter Aufrufweg bestehen — ohne ``geld``
    verhält sich der Aufruf exakt wie vorher.

    Seit dem 17.08. stehen hier auch die HAUSHALTS-REGELN, nicht nur die
    Zahlen. Sie hingen bis dahin allein am Antwort-Prompt von ``/ask``; der
    lange Bericht bekam die Beträge ohne die vier Regeln dazu (Jahr nennen,
    Plan ist nicht Ist, Quelle nennen, nicht rechnen). Sie stehen VOR den
    Zahlen, weil ihr eigener Wortlaut auf „eigene Abschnitte unten" verweist.
    """
    geld = _geld_vereinheitlichen(geld, haushalt, taxes, tax_capacity)
    zusatz = (_debatten_block(debatten) + _presse_block(presse)
              + geld_regeln(geld) + geld_block(geld) + _anlagen_block(anlagen))
    prompt = prompts.render("deep_bericht", question=question.strip()[:300],
                            context=_build_context(candidates),
                            zusatz=zusatz,
                            planungen=_planungen_block(planungen))
    extra = {"extra_body": {"reasoning": {"enabled": False}}} if "deepseek" in model else {}
    yield from llm.chat_stream(model=model, _feature="deep_report", temperature=0.2,
                               max_tokens=4000,
                               messages=[{"role": "user", "content": prompt}], **extra)


def _fraktions_label(raw: str | None) -> str | None:
    """Anzeige-Label einer Fraktion/Gruppe aus dem Protokoll-Feld: „Fraktion
    DIE LINKE." → „DIE LINKE". Gruppen („FDP/Volt", „Für Oldenburg") bleiben
    ungeteilt — normalize_party würde sie auf eine Einzelpartei kollabieren."""
    if not raw:
        return None
    label = " ".join(raw.strip().rstrip(".").split())
    # „Bündnis 90/ Die Grünen" vs „Bündnis 90/Die Grünen": Protokolle setzen
    # das Leerzeichen um den Slash uneinheitlich — sonst zwei „Fraktionen".
    label = re.sub(r"\s*/\s*", "/", label)
    if label.lower().startswith("fraktion "):
        label = label[9:]
    return label or None


# Die Ratsparteien und -gruppen in kanonischer Schreibweise, adressiert über
# den gefalteten Kern des Protokoll-Labels. Bewusst kuratiert: Die Anwesen-
# heitslisten führen auch Verbände (ADFC, BUND), Rollen („Elternvertreter",
# „Beratendes Mitglied") und kaputte Einzel-Label („BSW Für RH Dr. Onken") als
# „Partei" — in der Vollständigkeits-Zeile des Parteien-Bausteins haben die
# nichts verloren (Tims TestFlight-Feedback 11.08.).
_RATSPARTEIEN = {  # Schlüssel sind _falte()-Ergebnisse (Slash wird Leerzeichen)
    "spd": "SPD", "cdu": "CDU", "fdp": "FDP", "volt": "Volt", "afd": "AfD",
    "bsw": "BSW", "linke": "DIE LINKE", "die linke": "DIE LINKE",
    "buendnis 90 die gruenen": "Bündnis 90/Die Grünen",
    "gruene": "Bündnis 90/Die Grünen", "die gruenen": "Bündnis 90/Die Grünen",
    "fdp volt": "FDP/Volt", "fuer oldenburg": "Für Oldenburg",
    "piraten": "Piraten", "die partei": "Die PARTEI", "wfo": "WFO",
}


def ratspartei_label(raw: str | None) -> str | None:
    """Kanonisches Parteien-Label, oder None für alles, was keine Ratspartei
    ist. Faltet Schreibvarianten zusammen: „CDU-Fraktion" → CDU, „Die Grünen"
    → Bündnis 90/Die Grünen, „BSW Für RH Dr. Onken" → None."""
    label = _fraktions_label(raw)
    if not label:
        return None
    kern = re.sub(r"[-\s]+fraktion$", "", label, flags=re.IGNORECASE)
    return _RATSPARTEIEN.get(_falte(kern))


#: Wie viele Beiträge einer Fraktion in die Verdichtung gehen. Acht war zu
#: knapp: Zur Baumschutzsatzung hat allein die SPD zehn Mal geredet, die CDU
#: neun Mal — und Tims Anspruch an den Baustein ist, dass die Position aus
#: MÖGLICHST ALLEN Beiträgen entsteht, nicht aus einer Handvoll (21.08.2026).
#: Bei mehr als dem Deckel gewinnen die jüngsten: Die heutige Haltung trägt
#: den Baustein, die Vorgeschichte steht in der Antwort darüber.
MAX_BEITRAEGE_JE_PARTEI = 12


def _json_array_notfalls_gerettet(content: str) -> list | None:
    """JSON-Array einer Modellantwort — bei abgeschnittener Ausgabe bis zum
    letzten vollständigen Objekt gerettet. Ein Baustein mit fünf von acht
    Fraktionen ist besser als gar keiner. (Schwester von
    ``wortbeitraege._array_bergen``, dort für die Extraktion.)"""
    try:
        data = json.loads(content)
        return data if isinstance(data, list) else None
    except (json.JSONDecodeError, TypeError):
        pass
    cut = (content or "").rfind("},")
    if cut == -1:
        return None
    try:
        data = json.loads(content[:cut + 1] + "]")
    except (json.JSONDecodeError, TypeError):
        return None
    return data if isinstance(data, list) and data else None


def partei_meinungen(question: str, rows: list[dict], model: str = MODEL) -> list[dict] | None:
    """Baustein „Das sagen die Parteien" (Task 30): verdichtet Wortbeiträge je
    Fraktion zu Position + Kernaussage (+ „uneinheitlich"-Flag). None, wenn die
    Datenlage zu dünn ist (< 2 Fraktionen oder < 4 Beiträge) — der Baustein
    soll nur bei echten Debatten erscheinen."""
    gruppen: dict[str, list[dict]] = {}
    for r in rows:
        # Kanonisch gruppieren, wo es eine Ratspartei ist: Die Protokolle
        # schreiben mal „SPD", mal „SPD-Fraktion", mal „Die Grünen" — sonst
        # steht dieselbe Partei zweimal im Baustein und teilt sich ihre
        # Beiträge (an der Stadion-Frage gesehen: SPD 10 + SPD-Fraktion 1).
        # Gruppen („FDP/Volt", „Für Oldenburg") bleiben ungeteilt, alles
        # Unbekannte behält sein quellentreues Label.
        label = ratspartei_label(r.get("party")) or _fraktions_label(r.get("party"))
        if not label:
            continue  # Verwaltung, Einwohner, Referenten — keine Fraktionsmeinung
        gruppen.setdefault(label, []).append(r)
    # Ein einzelner Wortbeitrag macht aus einem Verband oder einem beratenden
    # Mitglied keine „Position": Seit die Beiträge über den Beschluss-Anker
    # kommen, stehen in den Debatten auch Gutachterbüros und Rollen-Label
    # („Institut für Partizipatives Gestalten", „Beratendes Mitglied"). Echte
    # Ratsfraktionen bleiben auch mit einem Beitrag drin — bei ihnen ist die
    # Zeile eine Aussage über den Rat, nicht Beifang.
    gruppen = {label: v for label, v in gruppen.items()
               if len(v) >= 2 or ratspartei_label(label)}
    if len(gruppen) < 2 or sum(len(v) for v in gruppen.values()) < 4:
        return None
    teile = []
    for label in gruppen:
        # Chronologisch (älteste zuerst): so kann die Verdichtung eine
        # Entwicklung benennen („anfangs skeptisch, zuletzt dafür") statt den
        # relevantesten Einzelbeitrag nachzuerzählen (Tims Befund 10.08.).
        # Der Deckel schneidet VORNE ab — nach Datum sortiert bleiben also die
        # jüngsten stehen, und die Chronologie im Prompt bleibt intakt.
        gruppen[label] = sorted(gruppen[label],
                                key=lambda b: b.get("session_date") or "")[-MAX_BEITRAEGE_JE_PARTEI:]
        zeilen = "\n".join(
            f"  - {b.get('speaker') or '?'} am {_datum_de(b.get('session_date'))}: "
            f"{(b.get('text') or '').strip()[:300]}"
            for b in gruppen[label])
        teile.append(f"{label} ({len(gruppen[label])} Beiträge):\n{zeilen}")
    prompt = prompts.render("partei_meinungen", question=question.strip()[:300],
                            beitraege="\n".join(teile))
    extra = {"extra_body": {"reasoning": {"enabled": False}}} if "deepseek" in model else {}
    # 2000 Token reichten nicht mehr: Mit dem Beschluss-Anker stehen bis zu 15
    # Fraktionen und Verbände im Prompt, die Antwort lief mitten in der AfD-
    # Position ins Limit („finish_reason: length", an der Baumschutz-Frage
    # gemessen) — und ein abgeschnittenes Array ließ den Baustein KOMPLETT
    # verschwinden. Erst Platz schaffen, dann trotzdem retten, was da ist.
    resp = llm.chat_complete(model=model, _feature="party_opinions", temperature=0,
                             max_tokens=6000, messages=[{"role": "user", "content": prompt}],
                             **extra)
    content = _strip_fences(resp.choices[0].message.content or "") if resp.choices else ""
    data = _json_array_notfalls_gerettet(content)
    if data is None:
        return None
    out = []
    for e in data:
        if not isinstance(e, dict) or e.get("party") not in gruppen:
            continue  # Halluzinations-Guard: nur Fraktionen aus dem Input
        kern = e.get("kernaussage") if isinstance(e.get("kernaussage"), dict) else None
        haltung = str(e.get("haltung") or "").strip().lower()
        out.append({
            "party": e["party"],
            "haltung": haltung if haltung in ("dafür", "dagegen", "offen", "gewandelt") else "offen",
            "position": str(e.get("position") or "").strip()[:400],
            "einig": bool(e.get("einig", True)),
            "note": (str(e.get("note")) or "").strip()[:200] or None if e.get("note") else None,
            "kernaussage": {
                "text": str(kern.get("text") or "").strip()[:300],
                "speaker": str(kern.get("speaker") or "").strip()[:80] or None,
                "date": str(kern.get("date") or "").strip()[:10] or None,
            } if kern and kern.get("text") else None,
            "beitraege": len(gruppen[e["party"]]),
            # Aufklappbare Zeile (Tims Wunsch): die verdichteten Beiträge im
            # Wortlaut — dieselben, die auch das LLM gesehen hat.
            "beitraege_liste": [{
                "speaker": b.get("speaker"),
                "date": _datum_de(b.get("session_date")),
                "art": b.get("kind"),
                "committee": b.get("committee"),
                "text": (b.get("text") or "").strip()[:2000],
            } for b in gruppen[e["party"]]],
        })
    return [e for e in out if e["position"]] or None


def _datum_de(iso: str | None) -> str:
    """ISO-Datum → deutsches Format für den Antwort-Kontext — sonst schreibt
    das Modell „Laut Pressemitteilung vom 2026-07-27" (Befund 10.08.)."""
    if iso and len(iso) >= 10:
        return f"{iso[8:10]}.{iso[5:7]}.{iso[0:4]}"
    return iso or "unbekannt"


def _presse_block(presse: list[dict] | None) -> str:
    """Kontext-Absatz „Aktuelles von der Stadt" — Pressemitteilungen sind KEINE
    Beschlüsse und werden nicht mit [id] zitiert; die Antwort nennt sie als
    „Laut Pressemitteilung vom …". Leer, wenn nichts Einschlägiges da ist."""
    if not presse:
        return ""
    zeilen = "\n".join(
        f"- {p.get('title', '')} (Pressemitteilung der Stadt vom {_datum_de(p.get('date'))}): "
        f"{(p.get('auszug') or '').strip()[:280]}"
        for p in presse)
    return ("\nAKTUELLES VON DER STADT (thematisch geprüfte Pressemitteilungen). Ergänze\n"
            "die Antwort um den aktuellen Stand der Verwaltung, wo die Mitteilungen\n"
            "Neues zur Sache tragen — als „Laut Pressemitteilung vom …“, NIE mit [id]:\n"
            f"{zeilen}\n")


def _debatten_block(debatten: list[dict] | None, eng: bool = False) -> str:
    """Kontext-Absatz „Aus den Ratsdebatten" — Wortbeiträge aus Protokollen
    (Reden, Anfragen, Einwohnerfragen, Zusagen). Das sind BERICHTE, keine
    Beschlüsse: nie mit [id] zitieren, sondern „Laut Protokoll sagte/fragte …"."""
    if not debatten:
        return ""
    art_label = {"inquiry": "Anfrage", "citizen_question": "Einwohnerfrage",
                 "pledge": "Zusage der Verwaltung", "speech": "Redebeitrag"}
    zeilen = []
    for d in debatten:
        wer = d.get("speaker") or "?"
        if d.get("party"):
            wer += f" ({d['party']})"
        kopf = f"{art_label.get(d.get('kind') or 'rede', 'Redebeitrag')} von {wer}"
        if d.get("session_date"):
            kopf += f" am {_datum_de(d['session_date'])}"
        if d.get("committee"):
            kopf += f" im Gremium „{d['committee']}“"
        if d.get("top"):
            kopf += f" zu „{d['top']}“"
        # Stations-Kopplung: Dieser Beitrag ist die Aussprache ZU einem der
        # Beschlüsse im Kontext — der Hinweis erlaubt dem Modell den Bezug
        # („In der Sitzung zu [20852] fragte …“), ohne den Beitrag selbst als
        # Beschluss zu zitieren.
        if d.get("zu_beschluss"):
            kopf += f" — Aussprache zum Beschluss [{d['zu_beschluss']}]"
        row = f"- {kopf}: {(d.get('text') or '').strip()[:400]}"
        if d.get("answer"):
            row += f" — Antwort der Verwaltung: {(d['answer'] or '').strip()[:300]}"
        zeilen.append(row)
    if eng:
        # Punktfrage: Die Wortbeiträge bleiben im Kontext (manchmal steckt die
        # gesuchte Tatsache genau dort), aber der Meinungsbild-Zwang entfällt —
        # sonst gewinnt er gegen die Kürze-Regel (im Test genau so passiert).
        kopf = ("\nAUS DEN RATSDEBATTEN (Wortbeiträge aus den Protokollen — Berichte,\n"
                "KEINE Beschlüsse). NUR verwenden, wenn die gesuchte Tatsache hier steht;\n"
                "KEIN Absatz zum Meinungsbild, die Frage will das nicht wissen.\n"
                "Wenn zitiert, dann als „Laut Protokoll sagte …“ und NIE mit [id]:\n")
        return kopf + "\n".join(zeilen) + "\n"
    return ("\nAUS DEN RATSDEBATTEN (thematisch geprüfte Wortbeiträge aus den\n"
            "Sitzungsprotokollen — Berichte, KEINE Beschlüsse). Ergänze die Antwort\n"
            "IMMER um einen kurzen Absatz Meinungsbild der Debatte (wer trug was vor,\n"
            "wo gab es Streit oder Zusagen) — auch wenn nur nach der Entscheidung\n"
            "gefragt ist: Die Debatte gehört zur Einordnung dazu. Klar markiert als\n"
            "„Laut Protokoll sagte/fragte …“ oder „In der Debatte betonte …“;\n"
            "NIE mit [id] zitieren.\n"
            "Steht dort eine ZUSAGE DER VERWALTUNG, nenne sie ausdrücklich und mit\n"
            "Datum („Die Verwaltung sagte am … zu, …“) — das ist eine\n"
            "Selbstverpflichtung und für die Leser*innen oft das Verwertbarste am\n"
            "ganzen Protokoll:\n"
            + "\n".join(zeilen) + "\n")


def _eur(v) -> str:
    return f"{v:,.0f} €".replace(",", ".") if v is not None else "–"


def _haushalt_block(zeilen: list[dict] | None) -> str:
    """Kontext-Absatz mit Plan-Zahlen aus dem Stadthaushalt (Geldfragen).
    KEINE Beschlüsse: nie mit [id] zitieren, sondern als „Laut Haushaltsplan
    JAHR …" nennen. Liegt der Bereich unter gleichem Namen auch im ältesten
    eingelesenen Jahr vor, steht die Entwicklung dabei."""
    if not zeilen:
        return ""
    teile = []
    for r in zeilen:
        s = (f"- {r['area']} ({r['year']}): Aufwendungen {_eur(r.get('expenses'))}, "
             f"Erträge {_eur(r.get('revenues'))}")
        if r.get("year_before"):
            s += (f" — {r['year_before']} waren es {_eur(r.get('expenses_before'))} "
                  f"Aufwendungen")
        teile.append(s)
    return ("\nSTADTHAUSHALT (GEPLANTE Zahlen aus dem beschlossenen Haushaltsplan; nur\n"
            "nutzen, wenn einschlägig — im Text als „Laut Haushaltsplan JAHR …“ nennen,\n"
            "NIE mit [id]):\n" + "\n".join(teile) + "\n")


def _steuern_block(zeilen: list[dict] | None) -> str:
    """Kontext-Absatz mit IST-Steuereinnahmen (Open-Data der Stadt).

    Strikt getrennt vom Haushalts-Block: Das sind abgerechnete Einnahmen, keine
    Planwerte. Die Regel steht ausdrücklich im Baustein, weil das Modell sonst
    Plan und Ist in einem Satz mischt („die Stadt nimmt 2026 222 Mio. ein“)."""
    if not zeilen:
        return ""
    teile = []
    for r in zeilen:
        name = "Steuereinnahmen insgesamt" if r["kind"] == "total" else r["kind"]
        s = f"- {name} ({r['year']}, tatsächlich eingenommen): {_eur(r.get('amount'))}"
        if r.get("year_before") and r.get("amount_before"):
            s += f" — {r['year_before']} waren es {_eur(r['amount_before'])}"
        teile.append(s)
    return ("\nSTEUEREINNAHMEN (IST-Zahlen der Stadt, NICHT der Haushaltsplan — nie mit\n"
            "den Plan-Zahlen oben vermischen; im Text als „tatsächlich eingenommen“\n"
            "kennzeichnen und das Jahr nennen, NIE mit [id]):\n" + "\n".join(teile) + "\n")


def _steuerkraft_block(k: dict | None) -> str:
    """Kontext-Absatz zur NFAG-Mechanik: mehr eigene Steuerkraft → weniger
    Schlüsselzuweisungen. Nur bei Hebesatz-/Mehreinnahme-Fragen einschlägig,
    dort aber entscheidend — sonst klingt jede Mehreinnahme nach vollem Plus."""
    if not k:
        return ""
    return (
        "\nFINANZAUSGLEICH (Hintergrund, nur nutzen, wenn nach Hebesätzen oder\n"
        "höheren Einnahmen gefragt wird; NIE mit [id]):\n"
        f"- Steuerkraftmesszahl {k['year']}: {_eur(k['tax_index'])} "
        f"(davor {k['year_before']}: {_eur(k['tax_index_before'])})\n"
        f"- Schlüsselzuweisungen des Landes {k['year']}: {_eur(k['allocations'])} "
        f"(davor {k['year_before']}: {_eur(k['zuweisungen_davor'])})\n"
        "- REGEL: Steigt die eigene Steuerkraft, sinken die Schlüsselzuweisungen des\n"
        "  Landes. Von einer Steuererhöhung bleibt der Stadt deshalb nur ein Teil —\n"
        "  sag das dazu, wenn du über mehr Einnahmen sprichst. Nenne keine\n"
        "  Prozentsätze oder Beträge, die hier nicht stehen.\n")


# ===========================================================================
# Geld-Facetten: welche Haushalts-Quelle beantwortet DIESE Frage?
# ===========================================================================
#
# Der Haushalts-Bestand hat neun Ebenen (Plan, Ist, Erläuterungen, Produkte,
# Prüfberichte, Konzern, Städtevergleich, Steuern, Finanzausgleich). Alle
# anzuhängen wäre die bequeme Lösung und die falsche: Jeder Baustein kostet
# Platz im Antwort-Prompt, und ein Kontext, in dem 377 Produkte und 257
# Prüffeststellungen stehen, verdrängt die Beschlüsse, nach denen gefragt war.
#
# ZWEI ENTSCHEIDUNGEN, DIE DEN UNTERSCHIED MACHEN:
#
# 1. DIE FACETTEN KOMMEN AUS DEM FRAGE-WORTLAUT, NICHT AUS DEM LLM-FRAGETYP.
#    Der Fragetyp (`analyse_query`) ist ein LLM-Urteil und lautet für „Was hat
#    das Rechnungsprüfungsamt beanstandet?" oder „Muss die Stadt das Theater
#    betreiben?" mit gutem Grund `topic` — es sind keine Betragsfragen. Hinge
#    der Haushalts-Kontext am Typ `money`, bekämen genau diese Fragen nichts.
#    Deterministische Erkennung am Wortlaut ist außerdem das Einzige, was sich
#    ohne API-Schlüssel messen lässt — und gemessen wird hier
#    (tests/test_qa_geldquellen.py).
#
# 2. DIE SUCHBEGRIFFE KOMMEN AUS DER EXPANSION, DIE FACETTEN NICHT.
#    Der Wortlaut entscheidet, OB eine Quelle gefragt wird; die expandierten
#    Begriffe entscheiden, WAS sie liefert. Andersherum wäre es ein Fehler:
#    Die Query-Expansion ist ausdrücklich angewiesen, eine Sachstands-Frage
#    zusätzlich als Finanzierungs-Frage zu formulieren — „Wie ist der Stand
#    beim Stadion?" trüge damit „Kosten" in den Begriffen und zöge den halben
#    Haushalt in eine Frage, die nichts davon wollte.
#
# Eine Facette, die feuert, kostet zunächst nur eine Datenbank-Abfrage. Die
# Store-Methoden liefern `None`, wenn nichts passt — der Prompt wächst also
# erst, wenn wirklich etwas Einschlägiges gefunden wurde.

#: Die Quellen, die eine Geldfrage beantworten können. Reihenfolge = Rang im
#: Kontext, wenn das Zeichenbudget nicht für alle reicht.
#:
#: Drei der vier Neuzugänge stehen VORN, und zwar nach Auslöse-Enge: Sie feuern
#: nur bei ihren eigenen, eindeutigen Wörtern. Wenn „schulden" erkannt wurde,
#: ist der Schuldenstand die Antwort und alles andere Beiwerk — er darf also
#: nicht derjenige sein, der bei knappem Budget herausfällt. Die zehn älteren
#: behalten ihre Reihenfolge untereinander unverändert.
#:
#: `antraege` steht bewusst NICHT vorn, obwohl es genauso eng auslöst: Der
#: Baustein ist mit Abstand der dickste (gemessen 1.379 Zeichen gegen 875–1.046
#: der anderen drei). Vorn gestellt fraß er zusammen mit ihnen das ganze Budget
#: — eine Frage, die alles zog, behielt danach von den zehn älteren Quellen
#: keine einzige. Hinter `produkte` kostet er nichts: Seine eigene Frage („Wer
#: wollte den Haushalt ändern?") zieht sonst nur `plan` und `ansatz`, und die
#: stehen beide dahinter.
#:
#: `gebaut` steht direkt hinter `investitionen`, und das ist kein Geschmack:
#: Die beiden ziehen dieselbe Frage („Was wird gebaut?") und sind Plan und Ist
#: desselben Themas. Fiele einer von beiden am Zeichenbudget heraus, während
#: der andere drinbliebe, stünde eine Investitionszahl ohne ihr Gegenstück im
#: Kontext — und die Regel „nie voneinander abziehen" hinge an einer Zahl, die
#: gar nicht da ist. Nebeneinander fallen sie zusammen oder gar nicht.
GELD_FACETTEN = ("schulden", "fees", "stellenplan", "investitionen", "gebaut",
                 "ist", "gruende", "pruefung", "produkte", "antraege",
                 "plan", "ansatz", "taxes", "ausgleich", "konzern", "vergleich",
                 # Die vier Schichten aus den Jahresabschlüssen (08/2026).
                 "bilanz", "kassensicht", "supplementary_approvals", "indicators")

#: Alle Muster arbeiten auf `_falte()`-Text: kleingeschrieben, Umlaute
#: ausgeschrieben, Satzzeichen zu Leerzeichen. Deshalb steht hier „pruef",
#: „kuerzen", „erhoeh" — und deshalb braucht keines der Muster
#: Schreibvarianten.
_F_PRUEFUNG = re.compile(
    r"rechnungspruef|pruefungsamt|\brpa\b|pruefbericht|schlussbericht|beanstand|"
    r"feststellung|geruegt|moniert|bemaengel|pruefer\b|testat|revision")
_F_KONZERN_WORT = re.compile(
    r"konzern|tochtergesellschaft|toechter|beteiligungsgesellschaft|eigenbetrieb|"
    r"gesamtabschluss|konsolidier|klinikum|stadtwerke")
_F_GANZ = re.compile(r"insgesamt|\bgesamt|zusammen|komplett|wirklich|alles|"
                     r"am ende|unterm strich|volle")
_F_VERGLEICH = re.compile(
    r"vergleich|verglichen|andere staedte|osnabrueck|wilhelmshaven|delmenhorst|"
    r"\bemden\b|salzgitter|wolfsburg|braunschweig|kreisfrei|landesdurchschnitt|"
    r"bundesweit|rangliste|besser oder schlechter|schlechter da|besser da")
_F_AUFGABE = re.compile(
    r"pflichtaufgab|pflichtleistung|pflichtig|freiwillig|muss die stadt|"
    r"muessen wir|muss oldenburg|rechtsgrundlage|gesetzlich|vorgeschrieben|"
    r"spielraum|streichen|kuerzen|sparen|einsparen|abschaffen|weglassen|"
    r"verzichten|betreiben|zustaendig")
# Zwei Befunde aus der Varianten-Messung (16.08.) stecken hier drin:
# * `\bteuer` statt `teuer` — ohne die Wortgrenze steckt es in
#   „GewerbesTEUER" und zog die halbe Produktebene in jede Steuerfrage.
# * „Was gibt die Stadt für X aus?" ist dieselbe Frage wie „Was kostet X?"
#   und muss dieselbe Quelle ziehen; sonst hängt die Produktebene an der
#   Laune der Formulierung.
# `kosten\b` NEBEN `\bkost`: Die Wortgrenze vorn trifft „kostet" und „Kosten",
# verfehlt aber jedes Kompositum — „Personalkosten", „Baukosten",
# „Betriebskosten" gingen leer aus, obwohl sie dieselbe Frage stellen. Die
# Endung fängt sie, ohne die Falle zu öffnen, die `\bteuer` schließt: Ein Wort
# wie „Kostüm" endet nicht auf „kosten".
_F_KOSTEN = re.compile(
    r"\bkost|kosten\b|\bteuer|\bpreis|gibt.{0,40}\baus\b|geben.{0,40}\baus\b|"
    r"ausgegeben fuer|ausgaben fuer|aufwend")
# Zwei Wörter sind hier am 17.08. HERAUSGEFALLEN, und beide waren gemessene
# Fehlleitungen — nicht Kosmetik:
# * „schulden" → zog den Ergebnishaushalt. Schulden sind ein BESTAND am
#   Stichtag; in der Ergebnisrechnung kommen sie überhaupt nicht vor. Sie
#   haben jetzt ihre eigene Quelle (`_F_SCHULDEN`).
# * „investit" → zog denselben Ergebnishaushalt, in dem keine einzige
#   Investition steht (ein Schulneubau taucht dort nur als Abschreibung auf).
#   Auch sie hat jetzt ihre eigene (`_F_INVEST`).
_F_PLAN = re.compile(
    r"haushalt|\betat\b|budget|\bansatz|\bkost|kosten\b|\bteuer|\bpreis|\bausga[bp]|ausgeb|"
    r"ausgeg|ausgib|gibt.{0,40}\baus\b|geben.{0,40}\baus\b|"
    r"aufwend|einnahm|ertrag|ertraeg|finanziert|zuschuss|foerder|"
    r"million|\bmio\b|\beuro\b|defizit|ueberschuss")
# Enger als `_F_PLAN`, und das mit Absicht: `ansatz_fuer_begriffe` fällt ohne
# Begriffs-Treffer auf die Summenzeilen des Gesamthaushalts zurück, liefert
# also IMMER etwas. An `_F_PLAN` gehängt, hätte damit „Was kostete der
# Stadionumbau?" den Gesamthaushalt der Stadt im Kontext gehabt — eine
# Beschluss-Betragsfrage, beantwortet mit 846 Mio. € Gesamtaufwand. Die
# Ertrags-/Aufwandsarten will nur, wer nach dem Haushalt als Ganzem fragt.
_F_ANSATZ = re.compile(
    r"haushalt|\betat\b|budget|\bansatz|einnahm|ertrag|ertraeg|aufwend|"
    r"nimmt.{0,20}\bein\b")
# Zwei Stufen, weil „geplant" allein nichts über Geld sagt: „Was ist am
# Fliegerhorst geplant?" zog sonst den Jahresabschluss in eine reine
# Planungsfrage. Die weichen Wörter brauchen deshalb einen Geld-Anker.
_F_IST_HART = re.compile(
    r"ausgegeben|jahresabschluss|income_statement|abgerechnet|rechnungsergebnis|"
    r"ueberschritten|fehlbetrag|\bdefizit|ueberschuss|\bbilanz")
_F_IST_WEICH = re.compile(
    r"tatsaechlich|wirklich|am ende|unterm strich|eingehalten|abweich|"
    r"geplant|\bplan\b|\bsoll\b|herausgekommen|geworden")
# `\bgrund\b` statt `\bgrund`: „GRUNDsteuer" ist kein Warum (gemessen 16.08.).
_F_GRUND = re.compile(r"\bwarum|weshalb|wieso|woran liegt|wie kommt|"
                      r"\bgrund\b|\bgruende\b|\bursach|erklaer.{0,12}(sich|das|warum)")
_F_STEUERN = re.compile(r"steuer|hebesatz|gewerbe|grundbesitz")
_F_GEBUEHREN = re.compile(
    r"gebuehr|gebuehrenbedarf|muellgebuehr|abfallgebuehr|"
    r"strassenreinigungsgebuehr|kehrgebuehr")
_F_AUSGLEICH = re.compile(
    r"hebesatz|schluesselzuweisung|finanzausgleich|steuerkraft|\bnfag\b|"
    r"zuweisung.{0,10}land|land.{0,15}zuweisung")
# --- Die vier Quellen, die die KI-Frage bis zum 17.08. nicht kannte ---------
# BÜRGSCHAFTEN GEHÖREN HIERHER, denn die 220,3 Mio. €, für die die Stadt
# geradesteht, stehen in KEINER der drei Schuldenreihen — „Wofür bürgt die
# Stadt?" bekam bis hierher den Ergebnishaushalt.
#
# Gesucht wird auf dem gefalteten Text (`_falte`: ü → ue), und das Muster ist
# eng aufgezählt statt kurz. Zwei Fallen, beide beim ersten Versuch
# hineingelaufen:
#
# * **„Oldenburg" enthält „burg".** Ein Muster `b[üu]rg` hätte an JEDER Frage
#   angeschlagen, in der die Stadt vorkommt — also an fast jeder.
# * **„Bürgerinnen" wird zu „buergerinnen"** und beginnt damit genauso wie
#   „buergschaft". Ein negativer Vorgriff auf „er" allein reicht nicht, weil
#   er die Bürger*innen zwar aussperrt, „Oldenburg" aber durchlässt.
_F_SCHULDEN = re.compile(
    r"schulden|verschuld|entschuld|schuldenstand|\bkredit|darlehen|tilgung|"
    r"\bbuergschaft|\bverbuergt|\bbuergt\b|\bbuergen\b|"
    r"eventualverbindlichkeit|geradesteh|geradezusteh")
# Gesucht wird auf dem GEFALTETEN Text (`_falte`: ä→ae, ö→oe, ü→ue, ß→ss) —
# deshalb stehen hier „ueberplanmaessig" und „anlagenintensitaet" und nicht
# die Schreibweisen mit Umlaut.
_F_BILANZ = re.compile(
    r"bilanz|eigenkapital|nettoposition|anlagevermoegen|sachvermoegen|"
    r"buchwert|abschreibung|was besitzt|was gehoert der stadt|"
    r"rueckstellung|zurueckgestellt|zurueckgelegt|pension|sonderposten|liquide")
# „auszahlung" steht bewusst NICHT drin: Das Wort gehört zu den Investitionen
# und zöge die Kassensicht in jede Bau-Frage.
_F_KASSE = re.compile(
    r"cash_flow_statement|kassensicht|kassenwirksam|liquide|liquiditaet|"
    r"zahlungsmittel|tatsaechlich geflossen|wirklich geflossen")
_F_NACHBEWILLIGUNG = re.compile(
    r"nachbewilli|ueberplanmaessig|ausserplanmaessig|117 nkomvg|"
    r"nachtraeglich bewilligt")
# Die dreizehn beim Namen — plus das Wort „Kennzahl" selbst. Bewusst ohne
# „quote" allein: Das steckt auch in „Impfquote" und „Abbruchquote".
_F_KENNZAHL = re.compile(
    r"kennzahl|eigenkapitalquote|anlagenintensitaet|infrastrukturquote|"
    r"steuerquote|personalintensitaet|reinvestitionsquote|"
    r"vermoegen je einwohner|vermoegen pro einwohner")
_F_INVEST = re.compile(
    r"investit|investier|investiv|\bgebaut\b|\bbauen\b|neubau|baumassnahm|"
    r"finanzhaushalt|auszahlung")
# „Stellen" ist im Deutschen zuerst ein Verb („Anträge stellen") und erst
# dann eine Planstelle. Das Wort allein reicht deshalb nicht — es zöge den
# Stellenplan in „Wie viele Anträge stellen die Fraktionen?". Also zwei
# Stufen wie bei `ist`: ein eindeutiges Stellenplan-Wort, oder eine Zählfrage
# rund um „Stellen", der kein Antrags-/Fragewort dazwischenfunkt.
_F_STELLEN_HART = re.compile(
    r"stellenplan|planstelle|stellenbesetzung|besetzungsgrad|unbesetzt|\bvakan|"
    # „personal" ohne den Ausweis: „Wo bekomme ich einen Personalausweis?" ist
    # keine Stellenplan-Frage und hätte ihn sonst im Kontext gehabt.
    r"personal(?!ausweis)|beschaeftigt|mitarbeiter|mitarbeitende|belegschaft|\bbeamt")
_F_STELLEN_ZAHL = re.compile(
    r"(?:viele|anzahl|zahl der|wie hoch)[^.?!]{0,30}\bstellen\b|"
    r"\bstellen\b[^.?!]{0,30}(?:besetzt|frei|gestrichen|geschaffen|abgebaut)")
_F_STELLEN_NICHT = re.compile(r"\bantrag|antraeg|anfrage|\bfragen\b|weichen")
# Die Änderungslisten: eigenständig bei ihrem eigenen Namen, sonst nur mit
# einem Haushalts-Anker. „Wie lief die Debatte um das Stadion?" trägt
# `\bdebatt`, meint aber keinen Haushaltsstreit.
_F_AENDERUNGSLISTE = re.compile(r"aenderungsliste|aenderungsantr|haushaltsantr")
_F_STREIT = re.compile(
    r"\baender|\bantrag|antraeg|beantragt|durchgesetz|durchkam|durchgekommen|"
    r"abgelehnt|angenommen|umstritten|\bstreit|gestritten|mehrheit|wer wollte|"
    # „debatt" ohne Wortgrenze, sonst verfehlt es „HaushaltsDEBATTE" — das
    # Kompositum ist die häufigere Schreibweise als „Debatte über den Haushalt".
    r"vorschlag|verabschied|kontrovers|debatt")
#: Ein Jahrgang aus dem Fragewortlaut — „Wer wollte den Haushalt 2024 ändern?".
_F_JAHRGANG = re.compile(r"\b(19[89]\d|20[0-4]\d)\b")


def haushaltsjahr(question: str) -> int | None:
    """Das Haushaltsjahr aus der Frage, falls eines darinsteht.

    Nur die Änderungslisten brauchen das: Sie liegen je Jahrgang vor, und
    „Wer wollte den Haushalt 2024 ändern?" meint 2024 und nicht den jüngsten
    Jahrgang. Steht keine Jahreszahl da, entscheidet die Quelle."""
    m = _F_JAHRGANG.search(question or "")
    return int(m.group(1)) if m else None


def geld_facetten(question: str, typ: str = "topic") -> set[str]:
    """Welche Haushalts-Quellen beantworten diese Frage? (Deterministisch.)

    Gemessen am ROHEN Fragewortlaut — nicht an den expandierten Suchbegriffen
    und nicht am LLM-Fragetyp (Begründung im Abschnittskopf oben). ``typ`` ist
    nur ein Auffangnetz: Sagt das Modell ``money`` und trifft trotzdem kein
    Muster, kommen die Plan-Zahlen — das ist genau das Verhalten von vor
    dieser Runde, das damit unverändert erhalten bleibt.

    Leere Menge heißt: Diese Frage bekommt **keinen** Haushalts-Kontext. Das
    ist der Normalfall — „Wie ist der Stand beim Stadion?" soll ihn nicht
    haben.
    """
    t = _falte(question or "")
    f: set[str] = set()
    if _F_PRUEFUNG.search(t):
        f.add("pruefung")
    if _F_VERGLEICH.search(t):
        f.add("vergleich")
    if _F_PLAN.search(t):
        f.add("plan")
    if _F_ANSATZ.search(t):
        f.add("ansatz")
    if _F_IST_HART.search(t) or (_F_IST_WEICH.search(t) and "plan" in f):
        f.add("ist")
    if _F_STEUERN.search(t):
        f.add("taxes")
    if _F_GEBUEHREN.search(t):
        f.add("fees")
    # „Was kostet X?" ist die Frage, die die Produktebene beantwortet — dort
    # steht eine Aufgabe mit ihren Kosten. Die Aufgaben-Wörter („muss die
    # Stadt …", „Rechtsgrundlage", „kürzen") ziehen sie auch ohne Kostenwort:
    # „Muss die Stadt das Theater betreiben?" fragt nach der Pflicht, nicht
    # nach dem Preis, und nur die Produktebene weiß die Antwort.
    if _F_KOSTEN.search(t) or _F_AUFGABE.search(t):
        f.add("produkte")
    # Das Warum steht im Jahresabschluss — ohne dessen Zahlen schwebt es.
    # Deshalb zieht `gruende` immer `ist` mit.
    if _F_GRUND.search(t) and (f & {"plan", "ist", "taxes"}):
        f.add("gruende")
        f.add("ist")
    # Der NFAG-Dämpfer: eigenständig bei Hebesatz-/Zuweisungs-Fragen, sonst
    # immer dann, wenn Steuern im Spiel sind (Verhalten von vor dieser Runde).
    if _F_AUSGLEICH.search(t) or "taxes" in f:
        f.add("ausgleich")
    # Der Konzern: bei seinen eigenen Wörtern — oder wenn jemand nach dem
    # GANZEN fragt („Was kostet die Stadt insgesamt?"). Der Kernhaushalt
    # antwortet darauf mit 799 Mio., der Konzern mit 1.242 Mio.
    if _F_KONZERN_WORT.search(t) or (_F_GANZ.search(t) and "plan" in f):
        f.add("konzern")
    # Schulden: ein Bestand, und deshalb ohne Plan-Beiwerk. „Wie hoch sind die
    # Schulden?" bekam bis hierher den Ergebnishaushalt und sonst nichts.
    if _F_SCHULDEN.search(t):
        f.add("schulden")
    # Die Bilanz zählt einen STICHTAG, keine Jahresbewegung — und ist deshalb
    # eine eigene Quelle, so wie die Schulden es sind.
    if _F_BILANZ.search(t):
        f.add("bilanz")
    # Die zweite Rechnung desselben Abschlusses. Sie kommt auch dann mit, wenn
    # jemand nach dem Ist fragt: Für 2024 weist die eine einen Überschuss aus
    # und die andere einen Fehlbetrag, und nur beide zusammen sind ehrlich.
    if _F_KASSE.search(t) or "ist" in f:
        f.add("kassensicht")
    if _F_NACHBEWILLIGUNG.search(t):
        f.add("supplementary_approvals")
    if _F_KENNZAHL.search(t):
        f.add("indicators")
    # Investitionen: der ANDERE Haushalt. Bewusst kein `plan` dazu — wer
    # fragt, was gebaut wird, soll keine Ergebnishaushalt-Zahl danebengelegt
    # bekommen. Fragt jemand nach beidem („Wie viel gibt die Stadt für
    # Investitionen aus?"), kommen beide, und der Baustein sagt, dass es zwei
    # Haushalte sind.
    # „Neubau" beschreibt auch bloß ein Thema („Was sagte die SPD zum
    # Stadionneubau?", „Wie entwickelte sich die Diskussion?"). Bei
    # Positions- und Verlaufsfragen ist das noch keine Haushaltsfrage; dort
    # braucht es zusätzlich einen ausdrücklichen Geld-Anker.
    if (_F_INVEST.search(t)
            and (typ not in ("party", "person", "history") or _F_PLAN.search(t))):
        # Immer beide: „Was wird gebaut?" hat einen Plan und ein Ist, und die
        # Frage sagt fast nie, welches von beidem gemeint ist. Nur den Plan zu
        # liefern hieße, jede Rückschau mit Absichtserklärungen zu beantworten;
        # nur das Ist, jede Frage nach dem laufenden Jahr mit Zahlen von
        # vorgestern.
        f.add("investitionen")
        f.add("gebaut")
    if _F_STELLEN_HART.search(t) or (_F_STELLEN_ZAHL.search(t)
                                     and not _F_STELLEN_NICHT.search(t)):
        f.add("stellenplan")
    if _F_AENDERUNGSLISTE.search(t) or (_F_STREIT.search(t) and (f & {"plan", "ansatz"})):
        f.add("antraege")
    if not f and typ == "money":
        f = {"plan"}   # das Verhalten von vor dieser Runde, unverändert
    return f


def _sicher(fn, *args, standard=None):
    """Eine Quelle abfragen — Zusatz, nie Blocker. Fällt die Tabelle (frische
    Datenbank ohne Ingest-Lauf), bleibt der Baustein leer statt die Antwort
    zu verlieren."""
    try:
        return fn(*args)
    except Exception:  # noqa: BLE001
        return standard


def geld_kontext(store, question: str, begriffe: str = "", typ: str = "topic") -> dict:
    """Alle einschlägigen Haushalts-Quellen zu einer Frage in EINEM Aufruf.

    Der Router ruft nur noch das hier; welche Store-Methoden dabei laufen,
    ist die Messgröße des Testkorpus (tests/test_qa_geldquellen.py). Der
    Rückgabewert trägt seine ``facetten`` mit — das Frontend zeigt sie im
    Quellen-Ereignis, und im Log ist damit ohne Rätselraten zu sehen, warum
    eine Antwort eine Zahl kannte oder eben nicht.
    """
    facetten = geld_facetten(question, typ)
    # Die Begriffe kommen aus der Expansion; ohne sie tut es die Frage selbst.
    woerter = [w for w in (begriffe or question or "").split() if w]
    aus: dict = {"facetten": sorted(facetten)}
    if "fees" in facetten:
        aus["fees"] = _sicher(store.gebuehren_fuer_begriffe, woerter)
    if "plan" in facetten:
        aus["haushalt"] = _sicher(store.haushalt_fuer_begriffe, woerter, standard=[])
    if "taxes" in facetten:
        aus["taxes"] = _sicher(store.steuern_fuer_begriffe, woerter, standard=[])
    if "ausgleich" in facetten:
        # Wie bisher: der Dämpfer nur, wenn es wirklich um Steuern geht —
        # sonst hinge er an jeder Zuweisungs-Frage ohne Bezug.
        if aus.get("taxes") or _F_AUSGLEICH.search(_falte(question or "")):
            aus["tax_capacity"] = _sicher(store.steuerkraft_kontext)
    if "ist" in facetten:
        aus["ist"] = _sicher(store.result_actual_for_terms, woerter)
    if "gruende" in facetten:
        aus["gruende"] = _sicher(store.abweichungsgruende_fuer_begriffe, woerter, standard=[])
    if "pruefung" in facetten:
        aus["pruefung"] = _sicher(store.pruefberichte_fuer_begriffe, woerter)
    if "produkte" in facetten:
        aus["produkte"] = _sicher(store.produkte_fuer_begriffe, woerter)
    if "konzern" in facetten:
        aus["konzern"] = _sicher(store.konzern_kontext)
    if "vergleich" in facetten:
        aus["vergleich"] = _sicher(store.staedtevergleich_kontext)
    if "ansatz" in facetten and not aus.get("haushalt"):
        # Der Ergebnishaushalt ist die feinere Plan-Quelle (Einnahmearten),
        # aber die gröbere ist die vertrautere: Solange `council_haushalt`
        # einen Teilhaushalt zur Frage hat, reicht der. Erst wenn er nichts
        # hergibt, lohnt der Ansatz die Zeichen.
        aus["ansatz"] = _sicher(store.ansatz_fuer_begriffe, woerter)
    if "schulden" in facetten:
        aus["schulden"] = _sicher(store.schulden_kontext)
    if "bilanz" in facetten:
        aus["bilanz"] = _sicher(store.bilanz_kontext)
    if "kassensicht" in facetten:
        aus["kassensicht"] = _sicher(store.kassensicht_kontext)
    if "supplementary_approvals" in facetten:
        aus["supplementary_approvals"] = _sicher(store.nachbewilligungen_kontext,
                                           haushaltsjahr(question))
    if "indicators" in facetten:
        aus["indicators"] = _sicher(store.kennzahlen_kontext)
    if "investitionen" in facetten:
        aus["investitionen"] = _sicher(store.investitionen_fuer_begriffe, woerter)
    if "gebaut" in facetten:
        aus["gebaut"] = _sicher(store.investitionen_ist_kontext)
    if "stellenplan" in facetten:
        aus["stellenplan"] = _sicher(store.stellenplan_kontext)
    if "antraege" in facetten:
        # Das Jahr aus der FRAGE, nicht aus den Begriffen: Die Expansion
        # streut Jahreszahlen ein, die niemand getippt hat.
        aus["antraege"] = _sicher(store.haushaltsantraege_kontext, haushaltsjahr(question))
    return aus


#: Quell-Label → Steckbrief-Slug von /haushalt/steuer. Nur die Arten, die
#: dort einen Steckbrief HABEN — für die übrigen (Getränke-, Vergnügungs-,
#: sonstige Steuern) führt der Link auf die Einnahmen-Übersicht, statt auf
#: einer Steckbrief-Seite im Fallback zu landen, die etwas anderes zeigt.
_STEUER_SLUGS = {
    "Gewerbesteuer (-umlage)": "gewerbesteuer",
    "Grundsteuer A+B": "grundsteuer",
    "Einkommensteueranteil": "einkommensteueranteil",
    "Gemeindeanteil an der Umsatzsteuer": "umsatzsteueranteil",
}


def _steuer_mehr(art: str) -> dict:
    """Das „Mehr dazu"-Ziel einer Steuerart — Steckbrief, sonst Übersicht."""
    slug = _STEUER_SLUGS.get(art)
    if slug:
        return {"href": f"/haushalt/steuer?art={slug}",
                "label": f"Der Steckbrief zur {art.split(' (')[0]}"}
    return {"href": "/haushalt/einnahmen",
            "label": "Woher das Geld der Stadt kommt"}


def geld_grafik(store, geld: dict) -> dict | None:
    """Die Grafik zur Antwort — Rohreihen aus dem Store, nie vom Modell.

    Der Chat kann neben dem Text strukturierte Blöcke zeigen (Debatten,
    Presse, Steckbriefe). Das hier ist der nächste: Wo eine Frage eine
    Zeitreihe berührt, bekommt die Antwort die Reihe als Bild dazu —
    gerendert vom Grafik-Baukasten des Haushalts-Bereichs, mit denselben
    Regeln (Ableseleiste, kein Tooltip, keine Bewertungsfarben).

    DIE EINE REGEL, AN DER ALLES HÄNGT: Die Daten kommen aus dem Store, mit
    denselben Zahlen, die auch in den Prompt gehen. Das Modell kann die
    Grafik weder erfinden noch verfälschen — es weiß nicht einmal, dass es
    sie gibt.

    KURATIERTE LISTE, KEIN AUTOMATISMUS. Eine Grafik gibt es nur, wo eine
    Reihe die Frage wirklich beantwortet — erste Ausbaustufe: Schulden
    (Bestand seit 1995) und Steuern (Ist-Einnahmen seit 1998). Für
    ``produkte`` oder ``pruefung`` erzwänge eine Reihe nichts. Höchstens
    EINE Grafik je Antwort: Bei „Wie hoch sind Schulden und Steuern?"
    gewinnt die Schulden-Reihe — sie ist die Bestandsfrage, und zwei
    Diagramme im Chat wären ein Dashboard, kein Gespräch.

    Auf Prod sind die Haushalts-Tabellen leer; dann kommt ``None``, und die
    Antwort sieht aus wie bisher — das Gate erledigt sich über die Daten.
    """
    if geld.get("schulden"):
        series = [{"year": r["year"], "value": round(r["total"] / 1e6, 1)}
                 for r in store.get_schulden() if r.get("total") is not None]
        if len(series) >= 2:
            s = geld["schulden"]
            return {
                "art": "schulden",
                "title": "Schuldenstand der Stadt",
                "unit": "Mio. €",
                "nachkomma": 1,
                "series": series,
                # Die Abgrenzung reist mit der Grafik wie mit jeder Zahl:
                # Ohne sie ist „337 Mio. €" eine von drei Zahlen, die alle
                # „die Schulden der Stadt" heißen.
                "note": s.get("abgrenzung"),
                "source": "Statistisches Jahrbuch der Stadt Oldenburg, Tabelle 1108",
                # Die Anschlussstelle in den Haushalts-Bereich — dieselbe
                # Bauart wie store.haushalts_anschluss: Der Server nennt das
                # Ziel, das Frontend entscheidet am Gate, ob es den Link
                # zeigt (auf Prod ist /haushalt ein 404).
                "mehr": {"href": "/haushalt/schulden",
                         "label": "Wie viel Schulden hat Oldenburg?"},
            }

    if geld.get("taxes"):
        # Die Art, die die Frage getroffen hat — `steuern_fuer_begriffe` hat
        # sie schon aufgelöst („gewinnt die erste": sie ist die, nach der
        # gefragt wurde; die weiteren sind Beifang der Synonyme).
        art = geld["taxes"][0]["kind"]
        series = [{"year": r["year"], "value": round(r["amount"] / 1e6, 1)}
                 for r in store.get_steuereinnahmen()
                 if r["kind"] == art and r.get("amount") is not None]
        if len(series) >= 2:
            title = ("Steuereinnahmen insgesamt" if art == "total"
                     else f"{art} — Ist-Einnahmen")
            return {
                "art": "taxes",
                "title": title,
                "unit": "Mio. €",
                "nachkomma": 1,
                "series": series,
                "note": ("Abrechnungszahlen der Stadt, keine Planwerte — "
                            "je Jahr das, was tatsächlich eingenommen wurde."),
                "source": "Statistisches Jahrbuch der Stadt Oldenburg, Ist-Steuereinnahmen",
                "mehr": _steuer_mehr(art),
            }
    return None


# --- Die Bausteine, die daraus im Prompt werden ----------------------------

def _beleg_text(b: dict | None) -> str:
    """„ — Beleg: Jahresabschluss 2024, Abschnitt 6.2 (Stand 31.12.2024)".

    Ohne Fundstelle keine Zahl: `council_herkunft` weiß zu jedem Datensatz,
    aus welchem Dokument und welchem Abschnitt er stammt, und der Prompt kann
    nur zitieren, was im Kontext steht."""
    if not b:
        return ""
    teile = [t for t in (b.get("label"), b.get("citation")) if t]
    if b.get("page"):
        teile.append(f"S. {b['page']}")
    if not teile:
        return ""
    as_of = f", Stand {b['as_of']}" if b.get("as_of") else ""
    return f" — Beleg: {', '.join(str(t) for t in teile)}{as_of}"


def _gebuehren_block(g: dict | None) -> str:
    """Geprüfte Gebührenkalkulationen, getrennt vom endgültigen Beschluss."""
    if not g or not g.get("bereiche"):
        return ""

    def geld(v, stellen=2):
        if v is None:
            return "–"
        return f"{v:,.{stellen}f} €".replace(",", "X").replace(".", ",").replace("X", ".")

    zeilen: list[str] = []
    for gruppe in g["bereiche"]:
        for r in gruppe.get("werte") or []:
            s = (f"- {r['area_name']} {r['year']}: Kostenkalkulation "
                 f"{_eur(r.get('cost_calculation'))}, Abzüge "
                 f"{_eur(r.get('deductions'))}, durch Gebühren zu decken "
                 f"{_eur(r.get('costs_to_cover'))}")
            if r.get("fee") is not None:
                unit = f" je {r['reference_unit']}" if r.get("reference_unit") else ""
                s += f"; errechnete Gebühr {geld(r['fee'], 3)}{unit}"
            else:
                s += ("; keine einzelne Gebühr ausgewiesen (Grundgebühr und "
                      "volumenabhängige Gebühr werden getrennt berechnet)")
            if r.get("fee_proposed") is not None:
                s += f"; gerundeter Gebührenvorschlag {geld(r['fee_proposed'])}"
            if r.get("template_number"):
                s += f"; Vorlage {r['template_number']}"
            s += _beleg_text(r.get("beleg"))
            zeilen.append(s)
    if not zeilen:
        return ""
    return (
        "\nGEBÜHRENBEDARFSBERECHNUNGEN (KALKULATION/VORSCHLAG, nicht automatisch "
        "der endgültig beschlossene Gebührensatz; Jahr und Quelle nennen, NIE mit [id]):\n"
        + "\n".join(zeilen)
        + "\n- REGEL: Erkläre Veränderungen nur aus den ausgewiesenen Größen. Die "
          "Gesamtkalkulation zeigt, DASS sich Kosten oder Abzüge geändert haben; sie "
          "belegt ohne einzelne Kostenpositionen nicht, WARUM. Ein Vorschlag wird erst "
          "durch einen passenden Ratsbeschluss zur beschlossenen Gebühr.\n"
    )


def _ist_block(ist: dict | None) -> str:
    """„Geplant und geworden" aus dem Jahresabschluss — die einzige Quelle,
    die sagt, ob ein Plan aufging."""
    if not ist or not ist.get("gesamt"):
        return ""
    g = ist["gesamt"]
    zeilen = [f"- Gesamt {ist['year']}: Aufwendungen geplant {_eur(g.get('expenses_planned'))}, "
              f"tatsächlich {_eur(g.get('expenses_actual'))}; Erträge geplant "
              f"{_eur(g.get('revenues_planned'))}, tatsächlich {_eur(g.get('revenues_actual'))}"]
    if g.get("plan_kind") and g["plan_kind"] != "budget":
        # 2018 ist die Bezugsgröße die Gesamtermächtigung, 2020 der Ansatz samt
        # Nachtrag (27 Mio. Unterschied). Ohne diesen Hinweis vergleicht die
        # Antwort in genau diesen Jahrgängen zwei verschiedene Dinge.
        zeilen.append(f"  (\"geplant\" ist in diesem Jahrgang der/die {g['plan_kind']}, "
                      f"nicht der nackte Haushaltsansatz — sag das dazu)")
    for b in ist.get("bereiche") or []:
        zeilen.append(f"- {b.get('name')} {ist['year']}: Aufwendungen geplant "
                      f"{_eur(b.get('expenses_planned'))}, tatsächlich "
                      f"{_eur(b.get('expenses_actual'))}")
    return ("\nGEPLANT UND TATSÄCHLICH (Jahresabschluss "
            f"{ist['year']} — ABGERECHNETE Zahlen, nicht der Haushaltsplan; nenne\n"
            "IMMER das Jahr dazu und nie mit [id] zitieren)"
            + _beleg_text(ist.get("beleg")) + ":\n" + "\n".join(zeilen) + "\n")


def _gruende_block(gruende: list[dict] | None) -> str:
    """Das *Warum* zu den Abweichungen, in den Worten der Verwaltung."""
    if not gruende:
        return ""
    zeilen = []
    for g in gruende:
        delta = f" ({g['delta_meur']:+.1f} Mio. €)" if g.get("delta_meur") is not None else ""
        zeilen.append(f"- {g['label']} {g['year']}{delta}: "
                      f"{' '.join((g.get('text') or '').split())[:400]}"
                      + _beleg_text(g.get("beleg")))
    return ("\nWARUM DER PLAN NICHT AUFGING (Erläuterungen der Verwaltung zum\n"
            "Jahresabschluss — das ist ihre Begründung, keine Feststellung von uns;\n"
            "gib sie als „Die Verwaltung begründet das damit, dass …“ wieder,\n"
            "NIE mit [id]):\n" + "\n".join(zeilen) + "\n")


def _pruefung_block(p: dict | None) -> str:
    """Feststellungen des Rechnungsprüfungsamts — die einzige regelmäßige,
    förmliche Kontrolle der Verwaltung durch eine eigene Stelle."""
    if not p or not p.get("feststellungen"):
        return ""
    zeilen = [f"- [{f['mark']} = {f['mark_name']}] Textziffer {f['text_number']} "
              f"„{f['section']}“"
              + (f", S. {f['page']}" if f.get("page") else "")
              + f": {' '.join((f.get('text') or '').split())[:350]}"
              for f in p["feststellungen"]]
    verteilung = ", ".join(f"{n}× {name}" for name, n in sorted(
        (p.get("nach_marke") or {}).items(), key=lambda kv: -kv[1]))
    return (f"\nRECHNUNGSPRÜFUNGSAMT, Schlussbericht zum Jahresabschluss {p['year']}\n"
            f"(total {p.get('gesamt')} Feststellungen"
            + (f": {verteilung}" if verteilung else "") + "). Unten eine AUSWAHL —\n"
            "sag, dass es eine Auswahl ist, nenne die Textziffer als Fundstelle und\n"
            "das geprüfte Jahr; NIE mit [id] zitieren"
            + _beleg_text(p.get("beleg")) + ":\n" + "\n".join(zeilen) + "\n")


def _produkte_block(p: dict | None) -> str:
    """Aufgaben der Stadt mit Kosten, Amt und Rechtsgrundlage — die einzige
    Quelle, die „Muss die Stadt das eigentlich?" beantworten kann."""
    if not p or not p.get("produkte"):
        return ""
    zeilen = []
    for r in p["produkte"]:
        s = f"- {r['product_name']} ({p['year']}"
        if r.get("office"):
            s += f", {r['office']}"
        s += f"): Aufwendungen {_eur(r.get('expenses'))}, Zuschussbedarf " \
             f"{_eur(abs(r['result']) if r.get('result') is not None else None)}"
        if r.get("legal_basis"):
            s += f" — Rechtsgrundlage laut Haushaltsplan: " \
                 f"{' '.join(r['legal_basis'].split())[:220]}"
        if r.get("controllability"):
            s += f" — Spielraum der Stadt (Selbstauskunft des Plans): {r['controllability']}"
        zeilen.append(s + _beleg_text(r.get("beleg")))
    return (f"\nAUFGABEN DER STADT MIT KOSTEN UND RECHTSGRUNDLAGE (Produktebene der\n"
            f"Teilhaushalts-Pläne, Stand {p['year']} — PLAN-Zahlen). Die\n"
            "„Rechtsgrundlage“ sagt, ob eine Aufgabe pflichtig oder freiwillig ist;\n"
            "sie ist die Selbstauskunft des Haushaltsplans, kein Rechtsgutachten —\n"
            "gib sie als solche wieder und NIE mit [id]:\n" + "\n".join(zeilen) + "\n")


def _konzern_block(k: dict | None) -> str:
    """Der Konzern Stadt — was der Kernhaushalt nicht zeigt."""
    if not k or k.get("expenses") is None:
        return ""
    zeilen = [f"- Konzern {k['year']}: Aufwendungen {_eur(k.get('expenses'))}, "
              f"Erträge {_eur(k.get('revenues'))}"]
    kern = k.get("kern") or {}
    if kern.get("expenses"):
        zeilen.append(f"- Davon Kernverwaltung (der „normale“ Haushalt) {k['year']}: "
                      f"Aufwendungen {_eur(kern['expenses'])} — die Differenz sind "
                      f"Eigenbetriebe und Beteiligungen")
    for t in (k.get("entity") or [])[:4]:
        zeilen.append(f"- {t['entity']}: {_eur((t.get('amount_keur') or 0) * 1000)} "
                      f"Aufwendungen (auf Tausend Euro exact, mehr gibt der Bericht nicht her)")
    return (f"\nDER KONZERN STADT OLDENBURG (konsolidierter Gesamtabschluss {k['year']} —\n"
            "Kernverwaltung PLUS Eigenbetriebe und Beteiligungen). Nutze das, wenn nach\n"
            "der Stadt ALS GANZES gefragt ist; die Zahlen sind mit denen des\n"
            "Kernhaushalts NICHT verrechenbar und NIE mit [id] zu zitieren"
            + _beleg_text(k.get("beleg")) + ":\n" + "\n".join(zeilen) + "\n")


def _vergleich_block(v: dict | None) -> str:
    """Die anderen kreisfreien Städte — Einordnung statt nackter Zahl."""
    if not v or not v.get("staedte"):
        return ""
    unit = f" {v['unit']}" if v.get("unit") else ""
    zeilen = [f"- {s['city']}: {s['value']:,.0f}{unit}".replace(",", ".")
              for s in v["staedte"][:8] if s.get("value") is not None]
    return (f"\nIM VERGLEICH ({v['indicator']}, {v['year']}, amtliche Statistik des\n"
            "Landesamts für Statistik Niedersachsen — alle kreisfreien Städte\n"
            "Niedersachsens). Für die Einordnung „wo steht Oldenburg?“; NIE mit [id]"
            + _beleg_text(v.get("beleg")) + ":\n" + "\n".join(zeilen) + "\n")


def _ansatz_block(a: dict | None) -> str:
    """Der Gesamtergebnishaushalt eines Planjahres — Einnahme- und
    Ausgabearten, wo `council_haushalt` nur Teilhaushalte kennt."""
    if not a or not a.get("posten"):
        return ""
    zeilen = [f"- {p['label']}: {_eur(p.get('amount'))}" for p in a["posten"]]
    return (f"\nHAUSHALTSANSATZ {a['year']} nach Ertrags- und Aufwandsarten (GEPLANT,\n"
            "aus dem Gesamtergebnishaushalt — der Stand der Einbringung, nicht\n"
            "zwingend der Beschluss des Rates; Jahr immer nennen, NIE mit [id])"
            + _beleg_text(a.get("beleg")) + ":\n" + "\n".join(zeilen) + "\n")


def _stellen(v) -> str:
    """„1.702,25" — Stellen sind Bruchzahlen (Teilzeit steht als Anteil)."""
    if v is None:
        return "–"
    return f"{v:,.2f}".replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def _bilanz_block(b: dict | None) -> str:
    """Was der Stadt gehört — ein STICHTAG, kein Jahr.

    Der Satz, den dieser Baustein verhindern soll: „Die Stadt hat 1,48 Mrd. €
    und gibt 799 Mio. € aus, also bleibt …". Bilanz und Ergebnisrechnung
    zählen Verschiedenes, und ihre Beträge sind nicht verrechenbar.
    """
    if not b or not b.get("bilanzsumme"):
        return ""
    namen = {
        "tangible_assets": "Sachvermögen (Grundstücke, Gebäude, Straßen, Fahrzeuge)",
        "infrastructure_assets": "davon Infrastruktur (Straßen, Wege, Brücken, Kanäle)",
        "financial_assets": "Finanzvermögen (Beteiligungen, Ausleihungen, Forderungen)",
        "cash_and_equivalents": "liquide Mittel",
        "net_position": "Nettoposition (das Eigenkapital der Stadt)",
        "special_items": "Sonderposten (erhaltene Zuschüsse, noch nicht aufgelöst)",
        "provisions": "Rückstellungen",
        "pension_provisions": "davon Pensionsrückstellungen",
        "liabilities": "Schulden und ähnliche Verbindlichkeiten",
    }
    zeilen = [f"- Bilanzsumme zum 31.12.{b['year']}: {_eur(b['bilanzsumme'])}"]
    for role, value in b.get("posten") or []:
        zeilen.append(f"  - {namen.get(role, role)}: {_eur(value)}")
    return ("\nBILANZ (Jahresabschluss, Abschnitt 2.1). Das ist ein STICHTAG "
            f"(31.12.{b['year']}),\nkein Haushaltsjahr: Diese Beträge NIE mit "
            "Erträgen, Aufwendungen oder dem\nDefizit eines Jahres verrechnen. Nie "
            "mit [id] zitieren"
            + _beleg_text(b.get("beleg")) + ":\n" + "\n".join(zeilen) + "\n")


def _kassensicht_block(k: dict | None) -> str:
    """Was tatsächlich geflossen ist — und warum das der Ergebnisrechnung
    scheinbar widerspricht."""
    if not k or not k.get("zeilen"):
        return ""
    zeilen = [f"- {name}: {_eur(value)}" for name, value, _rolle in k["zeilen"]]
    return (f"\nKASSENSICHT (Finanzrechnung {k['year']}, Abschnitt 4.1 desselben "
            "Jahresabschlusses).\nSie bucht, wenn GELD FLIESST — die "
            "Ergebnisrechnung bucht, wenn ein Anspruch\nentsteht. Deshalb können "
            "beide für dasselbe Jahr in verschiedene Richtungen\nzeigen (2024: dort "
            "ein Überschuss, hier ein Fehlbetrag an Finanzmitteln), und\nbeides "
            "stimmt. Sag dazu, welche der beiden du nennst. Nie mit [id] zitieren"
            + _beleg_text(k.get("beleg")) + ":\n" + "\n".join(zeilen) + "\n")


def _nachbewilligungen_block(n: dict | None) -> str:
    """Was beschlossen wurde, nachdem der Haushalt beschlossen war (§ 117 NKomVG)."""
    if not n or not n.get("gesamt"):
        return ""
    namen = {"rat": "vom Rat selbst beschlossen",
             "mayor": "vom Oberbürgermeister",
             "department_200": "vom Fachdienst Finanzen",
             "urgent_decision": "als Eilentscheidung"}
    zeilen = [f"- Nachbewilligt {n['year']} total: {_eur(n['gesamt'])} "
              f"(konsumtiv {_eur(n['konsumtiv'])}, investiv {_eur(n['investiv'])})"]
    for channel, kons, inv in n.get("channels") or []:
        summe = (kons or 0) + (inv or 0)
        if summe:
            anteil = f" — {summe / n['gesamt'] * 100:.0f} %" if n["gesamt"] else ""
            zeilen.append(f"  - {namen.get(channel, channel)}: {_eur(summe)}{anteil}")
    if n.get("commitments"):
        zeilen.append(f"- Verpflichtungsermächtigungen (binden KÜNFTIGE Jahre, "
                      f"gehören in KEINE Summe mit den Beträgen darüber): "
                      f"{_eur(n['commitments'])}")
    if n.get("probe_text"):
        zeilen.append(f"- Einschränkung der Quelle: {n['probe_text']}")
    return (f"\nNACHBEWILLIGUNGEN {n['year']} (§ 117 NKomVG, Rechenschaftsbericht "
            "Kapitel 3).\nGeld, das AUSSERHALB des beschlossenen Haushalts "
            "bewilligt wurde. Nicht mit\ndem Haushaltsplan verrechnen — es kommt "
            "obendrauf. Nie mit [id] zitieren"
            + _beleg_text(n.get("beleg")) + ":\n" + "\n".join(zeilen) + "\n")


def _kennzahlen_block(k: dict | None) -> str:
    """Die dreizehn Kennzahlen — mit dem Rechenweg, den die Stadt danebendruckt.

    Der einzige Block des Bereichs, der eine FORMEL mitliefert. Deshalb darf
    die Antwort eine Quote nennen, ohne sie zu erfinden — und deshalb steht
    dabei, wenn ein späterer Bericht eine Zahl still geändert hat.
    """
    if not k or not k.get("werte"):
        return ""
    def zeig(value: float, unit: str, stellen: int = 2) -> str:
        """Eine Kennzahl so schreiben, wie der Bericht sie druckt."""
        if unit == "percent":
            return f"{value:.{stellen}f} %".replace(".", ",")
        if unit == "count":
            return f"{value:,.0f}".replace(",", ".")
        return (f"{value:,.{stellen}f} €".replace(",", "\u0001")
                .replace(".", ",").replace("\u0001", "."))

    zeilen = []
    for name, value, unit, stellen, formula in k["werte"]:
        if unit == "percent":
            gezeigt = f"{value:.{stellen}f} %".replace(".", ",")
        elif unit == "count":
            gezeigt = f"{value:,.0f}".replace(",", ".")
        else:
            # Mit den GEDRUCKTEN Nachkommastellen, nicht mit `_eur`: Neben
            # „so rechnet die Stadt" stünde sonst eine gerundete Zahl (156 €
            # statt 156,43 €) und daneben der Rechenweg, der sie nicht ergibt.
            gezeigt = (f"{value:,.{stellen}f} €".replace(",", "\u0001")
                       .replace(".", ",").replace("\u0001", "."))
        row = f"- {name} {k['year']}: {gezeigt}"
        if formula:
            row += f" (so rechnet die Stadt: {formula})"
        zeilen.append(row)
    for name, year, alt, alt_b, neu, neu_b, unit in k.get("korrekturen") or []:
        zeilen.append(f"- ACHTUNG, später korrigiert: {name} {year} stand im Bericht "
                      f"{alt_b} noch bei {zeig(alt, unit)}, im Bericht {neu_b} bei "
                      f"{zeig(neu, unit)}. Nenne den jüngeren Wert und sag, dass "
                      f"korrigiert wurde.")
    return (f"\nKENNZAHLEN {k['year']} (Rechenschaftsbericht, Anlage "
            "„Kennzahlenübersicht und\nBerechnungsmethoden“). Die Rechenwege sind "
            "GEDRUCKT — zitiere sie, statt\neine Quote selbst zu bilden. Nie mit "
            "[id] zitieren"
            + _beleg_text(k.get("beleg")) + ":\n" + "\n".join(zeilen) + "\n")


def _schulden_block(s: dict | None) -> str:
    """Der Schuldenstand — ein Bestand am Stichtag.

    Der Baustein, der die schlichteste Frage des ganzen Bereichs beantwortet
    („Wie viel Schulden hat Oldenburg?") und bis zum 17.08. fehlte; sie wurde
    stattdessen vom Ergebnishaushalt beantwortet, in dem der Schuldenstand
    nicht vorkommt. Die Abgrenzung steht ausdrücklich dabei: Zwei Zahlen
    heißen „die Schulden der Stadt" und unterscheiden sich um ein Vielfaches.
    """
    if not s or s.get("total") is None:
        return ""
    kopf = f"- Schuldenstand am Jahresende {s['year']}: {_eur(s['total'])}"
    if s.get("per_capita"):
        kopf += f" — das sind {_eur(s['per_capita'])} je Einwohner*in"
    if s.get("revised"):
        kopf += " (von der Quelle als revidierter Wert gekennzeichnet)"
    zeilen = [kopf]
    if s.get("davor"):
        zeilen.append(f"- Ein Jahr davor ({s['davor']['year']}): "
                      f"{_eur(s['davor']['total'])}")
    if s.get("hoch"):
        zeilen.append(f"- Höchster Stand der Reihe (sie beginnt {s['reihe_ab']}): "
                      f"{s['hoch']['year']} mit {_eur(s['hoch']['total'])}")
    for title, amount in s.get("arten") or []:
        zeilen.append(f"  - davon {title}: {_eur(amount)}")
    if s.get("breakdown_rejected"):
        zeilen.append("  - Die Aufteilung nach Schuldenarten fehlt für dieses Jahr: "
                      "Sie ging in der Quelle selbst nicht auf und wurde deshalb "
                      "nicht übernommen. Die Gesamtsumme trägt eine eigene Probe.")
    zeilen.append(f"- Abgrenzung, gehört an jede dieser Zahlen: {s['abgrenzung']}")
    # DIE ANDEREN BEIDEN ZAHLEN. Ohne sie beantwortet die KI-Frage „Wie hoch
    # sind die Schulden?" mit einer von dreien, und welche es wird, entscheidet
    # der Zufall der Facette. Nebeneinander sind sie die ehrliche Antwort.
    for w in s.get("weitere") or []:
        zeilen.append(f"- Dieselbe Frage, andere Abgrenzung — {w['art']} "
                      f"{w['year']}: {_eur(w['amount'])} (Quelle: {w['source']})")
    if s.get("weitere"):
        zeilen.append("  Diese Zahlen NIE addieren: Die größere enthält die "
                      "kleinere. Wer nach „den Schulden“ fragt, bekommt die "
                      "Abgrenzung dazu, sonst ist die Zahl beliebig.")
    b = s.get("buergschaften")
    if b and b.get("balance") is not None:
        row = (f"- Zusätzlich verbürgt (KEINE Schuld, sondern ein Einstehen für "
                 f"fremde Kredite) {b['year']}: {_eur(b['balance'])}")
        if b.get("rueckstellung") is not None:
            row += (f"; davon hält die Stadt {_eur(b['rueckstellung'])} als "
                      f"Rückstellung für den erwarteten Ausfall vor")
        zeilen.append(row + _beleg_text(b.get("beleg")))
        if b.get("reason"):
            zeilen.append(f"  - Wofür: {b['reason']}")
        zeilen.append("  Eine Bürgschaft kostet nichts, solange sie nicht "
                      "gezogen wird — sie gehört in keine Schuldensumme.")
    return ("\nSCHULDENSTAND (Statistisches Jahrbuch der Stadt, Tabelle 1108). Das ist\n"
            "ein BESTAND am Stichtag, kein Jahresbetrag — nie mit Aufwendungen, "
            "Erträgen\noder dem Defizit eines Haushaltsjahres verrechnen und nie als "
            "„Ausgaben“\nbezeichnen. Nenne das Jahr und die Abgrenzung mit, NIE mit [id]"
            + _beleg_text(s.get("beleg")) + ":\n" + "\n".join(zeilen) + "\n")


def _investitionen_block(i: dict | None) -> str:
    """Was die Stadt bauen und kaufen will — mit der Warnung, dass der
    Ergebnishaushalt daneben ein anderes Zahlenwerk ist.

    Ohne diese Warnung ist der Baustein schädlicher als sein Fehlen: Zwei
    Millionenbeträge im selben Kontext, die nichts miteinander zu tun haben,
    addiert ein Sprachmodell bereitwillig."""
    if not i or not i.get("gesamt"):
        return ""
    g = i["gesamt"]
    zeilen = [f"- {g['label']} ({i['year']}): Auszahlungen "
              f"{_eur(g.get('outflows'))}, Einzahlungen {_eur(g.get('inflows'))}"]
    for r in i.get("teilhaushalte") or []:
        zeilen.append(f"  - {r['label']}: Auszahlungen {_eur(r.get('outflows'))}, "
                      f"Einzahlungen {_eur(r.get('inflows'))}")
    return (f"\nINVESTITIONEN (Finanzhaushalt des Haushaltsplans {i['year']} — GEPLANT).\n"
            "ES SIND ZWEI HAUSHALTE, NICHT EINER: Hier steht, was die Stadt bauen und\n"
            "kaufen will. Im Ergebnishaushalt (Aufwendungen und Erträge, eigener\n"
            "Abschnitt) steht davon keine einzige Investition — ein Schulneubau taucht\n"
            "dort nur als Abschreibung auf, verteilt über Jahrzehnte. Die Beträge der\n"
            "beiden nie addieren, nie voneinander abziehen, nie als Anteil "
            "gegeneinander\nrechnen. Und diese Zeilen nennen KEIN einzelnes Vorhaben: "
            "„Verkehr und\nStraßenbau: 10,5 Mio. €“ sagt nicht, welche Straße. NIE mit [id]"
            + _beleg_text(i.get("beleg")) + ":\n" + "\n".join(zeilen) + "\n")


def _gebaut_block(g: dict | None) -> str:
    """Was die Stadt wirklich investiert hat — das Ist zum Plan darüber.

    Die Regel im Kopf ist der ganze Grund für den eigenen Baustein: Plan und
    Ist stehen hier zum ersten Mal zusammen im Kontext, und die Rechnung
    „Ist ÷ Plan = Umsetzungsquote" liegt einem Sprachmodell am nächsten. Sie
    steht in keinem Dokument, und ihre beiden Hälften sind verschieden
    abgegrenzt — nach Teilhaushalten die eine, nach Auszahlungsarten und nur
    für die Kernverwaltung die andere.

    Die Lücke wird ausdrücklich genannt: Ohne sie liest ein Modell die Reihe
    als geschlossen und bildet Durchschnitte über ein Loch."""
    if not g or g.get("total") is None:
        return ""
    zeilen = [f"- Tatsächliche Investitions-Auszahlungen {g['year']}: "
              f"{_eur(g['total'])}"]
    if g.get("davor"):
        zeilen.append(f"- Ein Jahr davor ({g['davor']['year']}): "
                      f"{_eur(g['davor']['total'])}")
    if g.get("hoch"):
        zeilen.append(f"- Höchster Wert der Reihe (sie beginnt {g['reihe_ab']}): "
                      f"{g['hoch']['year']} mit {_eur(g['hoch']['total'])}")
    for title, amount in g.get("arten") or []:
        zeilen.append(f"  - davon {title}: {_eur(amount)}")
    if g.get("fehlend"):
        years = ", ".join(str(j) for j in g["fehlend"])
        zeilen.append(f"- NICHT im Bestand: {years}. Dort ergeben die "
                      "Auszahlungsarten in der Quelltabelle nicht die Summe "
                      "daneben; der Jahrgang wurde deshalb nicht übernommen. "
                      "Diese Jahre haben KEINEN Wert — weder null noch geschätzt.")
    zeilen.append(f"- Abgrenzung, gehört an jede dieser Zahlen: {g['abgrenzung']}")
    return ("\nINVESTITIONEN — TATSÄCHLICH ABGEFLOSSEN (Statistisches Jahrbuch der\n"
            "Stadt, Tabelle 1107-1). Das sind Rechnungsergebnisse, also das IST.\n"
            "NIE GEGEN DEN PLAN RECHNEN: Steht oben auch der Finanzhaushalt des\n"
            "Haushaltsplans, sind das zwei verschieden abgegrenzte Zahlenwerke — der\n"
            "Plan nach Teilhaushalten, dieses Ist nach Auszahlungsarten und nur für\n"
            "die Kernverwaltung. Keine Differenz bilden, keine „Umsetzungsquote“, "
            "keinen\nProzentsatz: Diese Rechnung steht in keinem Dokument. Nenne das "
            "Jahr und die\nAbgrenzung mit, NIE mit [id]"
            + _beleg_text(g.get("beleg")) + ":\n" + "\n".join(zeilen) + "\n")


def _stellenplan_block(s: dict | None) -> str:
    """Stellen statt Euro — die einzige Schicht des Haushalts, die Menschen
    zählt.

    Die Regel im Kopf ist der ganze Grund für diesen Baustein: „besetzt" und
    „nicht besetzt" gehören zur Vorjahresspalte. `Stellen − besetzt` mischt
    zwei Stichtage und ergibt eine Zahl, die in keinem Dokument steht — und
    genau diese Rechnung liegt einem Sprachmodell am nächsten."""
    if not s or not s.get("teile"):
        return ""
    zeilen = []
    for t in s["teile"]:
        zeilen.append(
            f"- Teil {t['part']} ({t['teil_name']}): {_stellen(t.get('positions_planned'))} "
            f"Stellen im Haushaltsjahr {s['budget_year']}. Im Vorjahr waren es "
            f"{_stellen(t.get('positions_prior_year'))} Stellen, davon "
            f"{_stellen(t.get('filled'))} besetzt und "
            f"{_stellen(t.get('vacant'))} nicht besetzt")
    if s.get("fehlend"):
        zeilen.append(f"- NICHT im Bestand: der Teil für {', '.join(s['fehlend'])}. "
                      "Die Zahlen oben sind deshalb nicht der ganze Stellenplan — "
                      "sag das dazu.")
    as_of_date = f", Stichtag {s['as_of_date']}" if s.get("as_of_date") else ""
    return (f"\nSTELLENPLAN {s['budget_year']} (Anlage des Haushaltsplans). Gezählt werden\n"
            "STELLEN, keine Köpfe — Teilzeit steht als Bruchteil —, und nur die\n"
            "Kernverwaltung: Klinikum, Bäder, Bus und Gebäudewirtschaft haben eigene\n"
            f"Wirtschaftspläne.\nSO IST ES ZU LESEN: „besetzt“ und „nicht besetzt“ "
            f"gehören zur VORJAHRESSPALTE{as_of_date}\n— geplant wird vorwärts, gezählt "
            "werden kann nur rückwärts. Rechne deshalb NIE\n„Stellen im Haushaltsjahr "
            "minus besetzt“: Das mischt zwei Stichtage und steht\nin keinem Dokument. "
            "Die unbesetzten Stellen stehen als eigene Angabe da.\nEine Zeile „Stellen "
            "insgesamt“ gibt es im Plan nicht; addiere die Teile nicht.\nNIE mit [id]"
            + _beleg_text(s.get("beleg")) + ":\n" + "\n".join(zeilen) + "\n")


def _antraege_block(a: dict | None) -> str:
    """Wer wollte am Haushalt etwas ändern — und kam damit durch?

    Die Grenze steht im Baustein und nicht nur in diesem Docstring: Die Quelle
    kennt Urheber und Ergebnis, aber **nicht den Inhalt** einer Änderungsliste
    (der liegt in Anlagen-PDFs ohne Volltext). Ohne den Satz füllt das Modell
    die Lücke mit Plausiblem — „die CDU wollte bei den Sozialausgaben kürzen"
    steht nirgends."""
    if not a or not a.get("stationen"):
        return ""
    zeilen = []
    for st in a["stationen"]:
        kopf = (f"- {st['committee']}, {_datum_de(st.get('date'))}: "
                f"{st['gesamt']} Änderungslisten zur Abstimmung")
        if st.get("verwaltung"):
            kopf += (f", davon {st['verwaltung']} der Verwaltung (Fortschreibung des "
                     "eigenen Entwurfs, kein Fraktionsantrag)")
        zeilen.append(kopf)
        for u in st.get("author") or []:
            zeilen.append(f"  - {u['name']}: {u['count']} — davon {u['accepted']} "
                          f"angenommen, {u['rejected']} abgelehnt")
        b = st.get("official_text") or {}
        if b.get("outcome"):
            from council import ergebnisse   # spät: ergebnisse zieht kern.notify
            zeilen.append(f"  - Schlussabstimmung über die Haushaltssatzung: "
                          f"{ergebnisse.ERGEBNIS_WORT.get(b['outcome'], b['outcome'])}"
                          + (f" ({ergebnisse.VOTE_WORT.get(b['vote'], b['vote'])})"
                             if b.get("vote") else ""))
    return (f"\nDER STREIT UM DEN HAUSHALT {a['year']} (Änderungslisten aus den "
            "Sitzungs-\nprotokollen; Jahreszahl = HAUSHALTSjahr, der Beschluss fällt "
            "oft im Jahr\ndavor).\nDIE GRENZE DIESER QUELLE GEHÖRT IN DIE ANTWORT: Sie "
            "sagt, WER etwas ändern\nwollte und ob es durchkam — nicht WAS genau. "
            "Welche Position um welchen Betrag\nsteht in den Anlagen der Vorlage und "
            "liegt uns nicht als Text vor; erfinde\nkeine Inhalte dazu und leite auch "
            "keine aus dem Titel ab. Gemeinsame Listen\nzählen für jede beteiligte "
            "Fraktion, die Zahlen sind deshalb nicht\naddierbar. NIE mit [id]:\n"
            + "\n".join(zeilen) + "\n")


#: Zeichenbudget für ALLE Geld-Bausteine zusammen. Der Antwort-Prompt trägt
#: schon 20 Beschlüsse à ~600 Zeichen, Debatten, Presse und Steckbriefe; was
#: hier dazukommt, geht davon ab. Reicht es nicht, fallen die hinteren
#: Facetten (Reihenfolge: GELD_FACETTEN) heraus — gemessen im Testkorpus.
GELD_MAX_CHARS = 4500

#: Baustein je Facette. Reihenfolge steckt in GELD_FACETTEN.
_GELD_BAUSTEINE = {
    "schulden": ("schulden", _schulden_block),
    "fees": ("fees", _gebuehren_block),
    "bilanz": ("bilanz", _bilanz_block),
    "kassensicht": ("kassensicht", _kassensicht_block),
    "supplementary_approvals": ("supplementary_approvals", _nachbewilligungen_block),
    "indicators": ("indicators", _kennzahlen_block),
    "stellenplan": ("stellenplan", _stellenplan_block),
    "investitionen": ("investitionen", _investitionen_block),
    "gebaut": ("gebaut", _gebaut_block),
    "ist": ("ist", _ist_block),
    "gruende": ("gruende", _gruende_block),
    "pruefung": ("pruefung", _pruefung_block),
    "produkte": ("produkte", _produkte_block),
    "antraege": ("antraege", _antraege_block),
    "plan": ("haushalt", _haushalt_block),
    "ansatz": ("ansatz", _ansatz_block),
    "taxes": ("taxes", _steuern_block),
    "ausgleich": ("tax_capacity", _steuerkraft_block),
    "konzern": ("konzern", _konzern_block),
    "vergleich": ("vergleich", _vergleich_block),
}


def _geld_vereinheitlichen(geld: dict | None, haushalt, taxes, tax_capacity) -> dict:
    """Alter Aufrufweg (haushalt=/steuern=/steuerkraft=) und neuer (geld=) auf
    eine Form bringen. Die Deep-Research-Pipeline reicht die drei Listen
    weiterhin einzeln durch; sie soll dafür nicht umgebaut werden müssen."""
    if geld:
        return geld
    return {"haushalt": haushalt, "taxes": taxes, "tax_capacity": tax_capacity}


def geld_block(geld: dict | None) -> str:
    """Alle vorhandenen Geld-Bausteine als EIN Prompt-Abschnitt, gedeckelt.

    Der Deckel ist keine Vorsichtsmaßnahme, sondern der Grund, warum die
    Facetten eine Reihenfolge haben: Wenn eine Frage sechs Quellen zieht,
    sollen die vorderen ganz drinstehen und die hinteren fehlen — nicht alle
    sechs in der Mitte abgeschnitten."""
    if not geld:
        return ""
    teile: list[str] = []
    laenge = 0
    for facette in GELD_FACETTEN:
        key, bauer = _GELD_BAUSTEINE[facette]
        text = bauer(geld.get(key))
        if not text:
            continue
        if laenge + len(text) > GELD_MAX_CHARS and teile:
            break
        teile.append(text)
        laenge += len(text)
    return "".join(teile)


def geld_regeln(geld: dict | None, eng: bool = False) -> str:
    """Antwort-Regeln für den Haushalts-Kontext — nur, wenn welcher da ist.

    Bewusst getrennt von ``EXTRA_REGELN["money"]``: Die Regel dort ist für
    BESCHLUSS-Beträge gebaut („Nenne die Summen aus den Beschlüssen, im
    Kontext als ‚Volumen: …‘ markiert") und war die einzige, die eine
    Geldfrage je zu sehen bekam. Für „Wie viel gibt Oldenburg für Soziales
    aus?" ist sie schlicht die falsche Anweisung; die Zahl steht nicht in
    einem Beschluss.
    """
    if not geld_block(geld):
        return ""
    # Punktfrage: Die Kürze-Regel gewinnt, es bleibt die Belegpflicht.
    if eng:
        return ("\n\nDie Haushaltszahl im Kontext bekommt IMMER ihr Jahr und ihre "
                "Quelle mit („laut Jahresabschluss 2024“) — sonst behauptet der "
                "eine Satz eine Aktualität, die die Daten nicht haben.")
    return (
        "\n\nZU DIESER FRAGE LIEGEN HAUSHALTSDATEN IM KONTEXT (eigene Abschnitte "
        "unten). Vier Regeln dafür:\n"
        "1. JAHR IMMER NENNEN. Die Quellen enden zu verschiedenen Zeitpunkten — "
        "Jahresabschlüsse, Produktebene, Prüfberichte und Konzern sind "
        "verschieden weit. Jede Zahl trägt das Jahr, aus dem sie stammt; ohne "
        "das behauptet die Antwort eine Aktualität, die die Daten nicht haben.\n"
        "2. PLAN IST NICHT IST. „Geplant“ (Haushaltsplan, Produktebene) und "
        "„tatsächlich“ (Jahresabschluss, Steuereinnahmen) nie in einem Satz "
        "vermischen und immer benennen, was von beidem gemeint ist.\n"
        "3. QUELLE NENNEN. Steht bei einer Zeile ein „Beleg:“, nenne das "
        "Dokument im Satz („laut Schlussbericht des Rechnungsprüfungsamts zum "
        "Jahresabschluss 2023“). Haushaltszahlen sind KEINE Beschlüsse und "
        "bekommen deshalb NIE eine [id].\n"
        "4. NICHT RECHNEN, WAS NICHT DASTEHT. Keine Summen über verschiedene "
        "Quellen, keine Prozentsätze, keine Pro-Kopf-Werte und keine "
        "Hochrechnungen auf andere Jahre — nur die Zahlen, die im Kontext "
        "stehen, und die Vergleiche, die dort ausdrücklich angelegt sind."
    )



# Zusatzregel für Themen mit langer Historie (Task 32): Der 4-8-Sätze-Deckel
# machte Antworten zu jahrelang diskutierten Vorhaben zwangsweise lückenhaft.
GROSS_REGEL = (
    "\nDies ist ein UMFANGREICHES Thema mit langer Beratungs-Historie. Antworte "
    "ausführlich (bis ~500 Wörter) und strukturiere die Antwort: Beginne mit GENAU "
    "EINER Zeile, die mit „**Kurz gesagt:** “ anfängt und in einem einzigen Satz "
    "sagt, wo die Sache heute steht — die Antwort auf die Frage, nicht eine "
    "Ankündigung dessen, was folgt. Gliedere danach mit 2-4 Zwischenüberschriften "
    "(Zeile, die mit „## “ beginnt, z. B. „## Finanzierung“) und nutze, wo es "
    "passt, kurze Spiegelstrich-Listen („- “). Die Fußnoten-Regeln gelten "
    "unverändert."
)


#: Fragen, deren Antwort NICHTS anderes sein kann als die Definition.
#: „Was ist die GSG?" — dort wiederholt jedes Fazit den Steckbrief. Fragen mit
#: eigenem Prädikat („Was ist beim Fliegerhorst GEPLANT?") sind ausgenommen:
#: Die zielen auf die Beschlusslage, nicht auf die Definition.
_DEFINITIONSFRAGE = re.compile(
    r"^\s*(was|wer)\s+(ist|sind|macht|machen|bedeutet|bedeuten)\b", re.IGNORECASE)
_EIGENES_PRAEDIKAT = re.compile(
    r"\b(geplant|beschlossen|entschieden|stand|kostet|kosten|passiert|gebaut|"
    r"gefordert|vorgesehen|zuletzt|wann)\b", re.IGNORECASE)


def steckbrief_karte_zeigen(question: str) -> bool:
    """Soll der Steckbrief als eigene Karte ÜBER der Antwort stehen?

    Der Hintergrund geht immer in den Prompt — er macht die Antwort besser.
    Sichtbar daneben gehört er aber nur, wenn die Antwort ihn nicht ohnehin
    wiederholt, und das hängt an der Frage (Tims Befund 12.08.):

    * „Wie ist der Stand bei der Cäcilienbrücke?" — der Steckbrief sagt, WAS
      die Brücke ist, die Antwort, wo der Ersatzneubau steht. Beide tragen.
    * „Was ist die GSG?" — hier IST die Antwort die Definition. Gemessen: die
      erste Antwortzeile überlappt zu 79 % mit dem Steckbrief. Zwei Wege haben
      dagegen nicht geholfen: das Modell bitten umzulenken (45 % → 44 %) und
      das „Kurz gesagt" streichen (die Definition rutschte in den ersten Satz).
      Also die Karte weglassen — die Antwort erklärt es selbst, und die hat
      obendrein Quellen unter jedem Satz.
    """
    if not _DEFINITIONSFRAGE.match(question or ""):
        return True
    return bool(_EIGENES_PRAEDIKAT.search(question or ""))

#: Wenige und schwache Treffer → der Ton muss mitgehen. Ohne diese Regel klingt
#: eine dünn belegte Antwort wie eine gut belegte; genau daran hing das einzige
#: begründete 👎 („Falschinfo").
DUENN_REGEL = (
    "\nACHTUNG, DÜNNE BELEGLAGE: Zu dieser Frage gibt es nur wenige und nur "
    "schwach passende Beschlüsse. Sage in EINEM ersten Satz ehrlich, dass die "
    "Ratsunterlagen dazu wenig hergeben, und referiere danach nur, was wirklich "
    "belegt ist. Erfinde keine Zusammenhänge und dehne Randtreffer nicht zu einer "
    "Antwort — lieber kurz und ehrlich als lang und geraten."
)


def _answer_messages(question: str, candidates: list[dict], typ: str = "topic",
                     model: str = MODEL, presse: list[dict] | None = None,
                     verlauf: list[dict] | None = None,
                     haushalt: list[dict] | None = None,
                     debatten: list[dict] | None = None,
                     anlagen: list[dict] | None = None,
                     gross: bool = False, steckbriefe: list[dict] | None = None,
                     duenn: bool = False, eng: bool = False,
                     taxes: list[dict] | None = None,
                     tax_capacity: dict | None = None,
                     geld: dict | None = None,
                     sitzungen: list[dict] | None = None,
                     ort: dict | None = None) -> tuple[list[dict], dict]:
    vtext = _verlauf_zeilen(verlauf)
    gespraech = (f"Dies ist eine Anschlussfrage in einem Gespräch. Bisher:\n{vtext}\n\n"
                 if vtext else "")
    geld = _geld_vereinheitlichen(geld, haushalt, taxes, tax_capacity)
    ortsregel = ""
    if ort:
        ortsregel = (
            f"\nORTSFILTER: Die Frage nennt den Katalogort „{ort.get('name', '')}“ "
            f"({ort.get('kind_label', 'Ort')}). Verwende nur Beschlüsse mit "
            "belegtem Bezug zu genau diesem Ort; die konkrete Fundstelle steht "
            "im Kontext als „Ortsbezug“. Verwechsle einen kleineren Ort nicht "
            "mit seinem größeren Ortsbereich und benenne eine dünne Datenlage ehrlich."
        )
    if latest_intent(question):
        latest = latest_real_decision(candidates)
        anker = ""
        if latest:
            anker = (
                f" Der ERSTE Kontext-Eintrag [{latest['id']}] vom "
                f"{latest.get('session_date') or 'unbekannten Datum'} ist die "
                f"deterministisch ermittelte neueste echte Entscheidung "
                f"(Ergebnis: {latest.get('outcome') or 'unbekannt'})."
            )
        ortsregel += (
            "\nCHRONOLOGIE: Die Frage verlangt ausdrücklich das Neueste. Die "
            "neueste echte Entscheidung steht im Kontext absichtlich an erster "
            "Stelle; die übrigen Vorgänge folgen neueste zuerst. Beginne den ERSTEN "
            "Satz zwingend mit dieser Entscheidung und ihrem Datum. Unterscheide "
            "angenommene/abgelehnte Beschlüsse klar von bloßen Berichten oder "
            f"Kenntnisnahmen.{anker}"
        )
    prompt = prompts.render("qa_antwort", question=question.strip()[:300],
                            context=_build_context(candidates),
                            # Die Haushalts-Regeln hängen am KONTEXT, nicht am
                            # Fragetyp: „Was hat das Rechnungsprüfungsamt
                            # beanstandet?" ist für das Analyse-Modell mit gutem
                            # Grund `topic` — die Feststellungen liegen trotzdem
                            # im Prompt und brauchen ihre Regeln.
                            extra_regeln=(ENG_REGEL if eng else EXTRA_REGELN.get(typ, ""))
                            + ortsregel
                            + ("" if eng else (GROSS_REGEL if gross else ""))
                            + (DUENN_REGEL if duenn else "")
                            + geld_regeln(geld, eng),
                            presse=_sitzungen_block(sitzungen)
                            + _steckbrief_block(steckbriefe) + _presse_block(presse)
                            + geld_block(geld) + _debatten_block(debatten, eng)
                            + _anlagen_block(anlagen),
                            gespraech=gespraech)
    # reasoning-Schalter am TATSÄCHLICH genutzten Modell festmachen — vorher
    # hing er an der Modul-Konstante und lief bei model=-Overrides ins Leere.
    extra = {"extra_body": {"reasoning": {"enabled": False}}} if "deepseek" in model else {}
    return [{"role": "user", "content": prompt}], extra


# --- „Einfacher erklären" (Befund Build 11) ---------------------------------
# Der Knopf schickte bisher nur den Satz „Erkläre das bitte einfacher, ohne
# Fachbegriffe." als normale Frage in dieselbe Pipeline. Damit stand der Wunsch
# als EINE beiläufige Zeile in einem Prompt, der zwei Dutzend Zeilen lang
# Genauigkeit, Zitate, Debatten-Absatz und Gliederung verlangt — und verlor.
# Ergebnis: dieselbe Antwort, nur anders sortiert, mit „Ausfallbürgschaften",
# „Teilfortschreibung des Nahverkehrsplans" und „VBN-Tarifgebiet 3" darin.
# Jetzt erkennt das Backend den Wunsch und nimmt einen EIGENEN Prompt
# („qa_einfach"), der die vorliegende Antwort umschreibt statt neu zu antworten.
_VEREINFACHEN_RE = re.compile(
    r"ohne\s+(fachbegriffe|fachw[oö]rter|fachchinesisch|fachsprache|amtsdeutsch|"
    r"beh[oö]rdendeutsch|fremdw[oö]rter)"
    r"|(einfacher|leichter|simpler|verst[aä]ndlicher)\s+(erkl|sag|formul|schreib|aus|zusammen)"
    r"|erkl[aä]r\w*[^.?!]{0,40}\b(einfacher|leichter|simpler|verst[aä]ndlicher)"
    r"|in\s+(ganz\s+)?(einfache[rmn]?|leichte[rmn]?)\s+(sprache|worten?|deutsch)"
    r"|laienverst[aä]ndlich|allgemeinverst[aä]ndlich"
    r"|^\s*(bitte\s+)?(einfacher|verst[aä]ndlicher)\b",
    re.IGNORECASE)


def will_vereinfachung(question: str) -> bool:
    """Bittet diese Frage darum, die vorige Antwort einfacher zu erklären?

    Deterministisch statt per LLM — der Knopf schickt immer denselben Satz, und
    wer ihn selbst tippt („erklär mir das mal einfacher", „ohne Fachbegriffe
    bitte"), meint dasselbe. Eine lange, inhaltliche Frage bleibt eine Frage,
    auch wenn irgendwo „einfacher" darin vorkommt.
    """
    text = " ".join((question or "").split())
    if len(text) > 160:
        return False
    return bool(_VEREINFACHEN_RE.search(text))


#: Die Ausgangsantwort im Prompt — länger braucht es nicht, und ein Deckel
#: hält die Kosten je Klick vorhersagbar.
VEREINFACHEN_MAX_CHARS = 6000


def _bisher_block(bisher: str | None) -> str:
    """Die zu vereinfachende Antwort — oder ein ehrlicher Hinweis, dass keine
    vorliegt. Ältere App-Versionen schicken sie nicht mit (das Feld gibt es erst
    seit dieser Runde); dann schreibt das Modell die einfache Fassung direkt aus
    den Beschlüssen, statt mit einem leeren Zitat-Block zu hantieren."""
    text = " ".join((bisher or "").split())
    if not text:
        return ("\nEs liegt keine frühere Antwort vor: Beantworte die Frage unten direkt "
                "in einfacher Sprache, nach denselben Regeln.\n\n")
    return ("\nDAS IST DIE ANTWORT, DIE DU VEREINFACHEN SOLLST (Inhalt und Belege bleiben, "
            "die Sprache wird einfach):\n---\n"
            f"{text[:VEREINFACHEN_MAX_CHARS]}\n---\n\n")


def vereinfachen_messages(question: str, bisher: str | None, candidates: list[dict],
                          model: str = MODEL) -> tuple[list[dict], dict]:
    """Prompt für den Vereinfachungs-Modus. Bewusst OHNE Presse-, Debatten- und
    Haushalts-Block: Deren Kontext-Anweisungen („ergänze IMMER einen Absatz zum
    Meinungsbild") arbeiten gegen die Kürze — genau daran ist die beiläufige
    Bitte im normalen Prompt schon gescheitert."""
    prompt = prompts.render("qa_einfach", question=question.strip()[:300],
                            bisher=_bisher_block(bisher),
                            context=_build_context(candidates))
    extra = {"extra_body": {"reasoning": {"enabled": False}}} if "deepseek" in model else {}
    return [{"role": "user", "content": prompt}], extra


#: Kurz ist das Ziel — das Budget ist die zweite Bremse neben der Prompt-Regel.
VEREINFACHEN_TOKENS = 700


def vereinfachen_stream(question: str, bisher: str | None, candidates: list[dict],
                        model: str = MODEL):
    """Die einfache Fassung als Token-Stream (wie answer_stream)."""
    messages, extra = vereinfachen_messages(question, bisher, candidates, model)
    yield from llm.chat_stream(model=model, _feature="qa_simple", temperature=0.2,
                               max_tokens=VEREINFACHEN_TOKENS, messages=messages, **extra)


def vereinfachen_question(question: str, bisher: str | None, candidates: list[dict],
                          model: str = MODEL):
    """One-shot-Variante für den Ersatzweg, wenn der Stream abreißt.
    Liefert ``(answer, cited_ids)`` wie answer_question."""
    messages, extra = vereinfachen_messages(question, bisher, candidates, model)
    resp = llm.chat_complete(model=model, _feature="qa_simple", temperature=0.2,
                             max_tokens=VEREINFACHEN_TOKENS, messages=messages, **extra)
    answer = (resp.choices[0].message.content or "").strip()
    return resolve_citations(answer, {c["id"] for c in candidates})


def _answer_tokens(typ: str, gross: bool = False, eng: bool = False) -> int:
    # Punktfrage: knappes Budget als zweite Bremse neben der Prompt-Regel.
    if eng:
        return 320
    # Seit dem Ratsgespräch dürfen breite Fragen strukturiert länger antworten
    # (Prompt regelt die Länge nach Frage; das Budget kappt nur den Ausreißer).
    # Große Themen (Task 32) bekommen Platz für die gegliederte Langfassung.
    if gross:
        return 2200
    if typ == "session":
        # Der Rückblick muss JEDEN Punkt der Sitzung erwähnen dürfen.
        return 1400
    return 1100 if typ == "history" else 1000


def answer_question(question: str, candidates: list[dict], model: str = MODEL, typ: str = "topic",
                    presse: list[dict] | None = None, verlauf: list[dict] | None = None,
                    haushalt: list[dict] | None = None, debatten: list[dict] | None = None,
                    anlagen: list[dict] | None = None,
                    gross: bool = False, steckbriefe: list[dict] | None = None,
                    duenn: bool = False, eng: bool = False,
                    taxes: list[dict] | None = None, tax_capacity: dict | None = None,
                    geld: dict | None = None, sitzungen: list[dict] | None = None,
                    ort: dict | None = None):
    """Synthesise an answer from retrieved candidates. Returns ``(answer, cited_ids)``."""
    messages, extra = _answer_messages(question, candidates, typ, model, presse, verlauf,
                                       haushalt, debatten, anlagen, gross, steckbriefe, duenn, eng,
                                       taxes, tax_capacity, geld, sitzungen, ort)
    resp = llm.chat_complete(model=model, _feature="qa_answer", temperature=0.2,
                             max_tokens=_answer_tokens(typ, gross, eng), messages=messages, **extra)
    answer = (resp.choices[0].message.content or "").strip()
    return resolve_citations(answer, {c["id"] for c in candidates})


def answer_stream(question: str, candidates: list[dict], model: str = MODEL, typ: str = "topic",
                  presse: list[dict] | None = None, verlauf: list[dict] | None = None,
                  haushalt: list[dict] | None = None, debatten: list[dict] | None = None,
                  anlagen: list[dict] | None = None,
                  gross: bool = False, steckbriefe: list[dict] | None = None,
                  duenn: bool = False, eng: bool = False,
                  taxes: list[dict] | None = None, tax_capacity: dict | None = None,
                  geld: dict | None = None, sitzungen: list[dict] | None = None,
                  ort: dict | None = None):
    """Stream the answer text deltas (same prompt/context as answer_question) so the
    UI can render the answer as it is written. Citation resolution is the caller's
    job once the full text is assembled (see resolve_citations)."""
    messages, extra = _answer_messages(question, candidates, typ, model, presse, verlauf,
                                       haushalt, debatten, anlagen, gross, steckbriefe, duenn, eng,
                                       taxes, tax_capacity, geld, sitzungen, ort)
    yield from llm.chat_stream(model=model, _feature="qa_answer", temperature=0.2,
                               max_tokens=_answer_tokens(typ, gross, eng), messages=messages, **extra)


# --- Folgefragen (Design 24a / RL-U06) --------------------------------------
# Das Antwort-LLM hängt seine Vorschläge als letzte Zeile an (siehe Prompt
# „qa_antwort"). Der Marker trennt sie vom Antworttext — der Router streamt
# alles davor als Token und schneidet ab hier ab.
FOLLOWUP_MARKER = "FOLGEFRAGEN:"
_MAX_FOLLOWUPS = 3
_MAX_FOLLOWUP_LEN = 90


def split_followups(text: str) -> tuple[str, list[str]]:
    """Antworttext und die vom Modell angehängten Folgefragen trennen.

    Robust gegen ein Modell, das den Marker weglässt oder kaputtes JSON liefert:
    dann kommt die Antwort unverändert zurück und die Fragenliste ist leer (der
    Aufrufer nimmt dann den deterministischen Fallback).
    """
    idx = text.find(FOLLOWUP_MARKER)
    if idx == -1:
        return text.strip(), []
    answer = text[:idx].strip()
    tail = text[idx + len(FOLLOWUP_MARKER):].strip()
    questions: list[str] = []
    try:
        start, end = tail.find("["), tail.rfind("]")
        if start != -1 and end > start:
            for item in json.loads(tail[start:end + 1]):
                q = str(item).strip()
                if q and len(q) <= _MAX_FOLLOWUP_LEN and q not in questions:
                    questions.append(q)
    except (ValueError, TypeError):
        pass
    if not questions:
        # Kein (brauchbares) JSON — zeilenweise als Notnagel (»- Frage?«).
        for line in tail.splitlines():
            q = line.strip().lstrip("-•*\" ").rstrip("\",")
            if q.endswith("?") and len(q) <= _MAX_FOLLOWUP_LEN and q not in questions:
                questions.append(q)
    return answer, questions[:_MAX_FOLLOWUPS]


def fallback_followups(candidates: list[dict]) -> list[str]:
    """Variante B: Folgefragen ohne LLM aus den gefundenen Beschlüssen ableiten.

    Greift, wenn das Modell keine brauchbare Liste geliefert hat. Per
    Konstruktion sackgassenfrei — jede Frage zielt auf etwas, das im gefundenen
    Bestand nachweislich vorkommt.
    """
    from .topics import POLICY_FIELDS

    out: list[str] = []

    def add(q: str) -> None:
        if q not in out and len(out) < _MAX_FOLLOWUPS:
            out.append(q)

    # 1) Umstritten? Dann ist die Abstimmung die naheliegendste Anschlussfrage.
    for c in candidates:
        if (c.get("no_votes") or 0) > 0 and (c.get("title") or "").strip():
            add(f"Wer stimmte gegen {_short_subject(c['title'])}?")
            break
    # 2) Themenfeld des Treffers — führt zu benachbarten Beschlüssen.
    for c in candidates:
        label = POLICY_FIELDS.get(c.get("policy_field") or "", ("",))[0]
        if label:
            add(f"Was wurde zuletzt zum Thema {label} beschlossen?")
            break
    # 3) Geld — nur wenn im Bestand tatsächlich ein Betrag steht.
    for c in candidates:
        if c.get("amount_eur"):
            label = POLICY_FIELDS.get(c.get("policy_field") or "", ("",))[0]
            add(f"Welche Beträge beschloss der Rat für {label or 'dieses Vorhaben'}?"
                if label else "Welche größeren Beträge hat der Rat zuletzt beschlossen?")
            break
    # 4) Gremium als letzter Auffüller.
    for c in candidates:
        if (c.get("committee") or "").strip():
            add(f"Was hat der {c['committee']} zuletzt entschieden?")
            break
    return out


def _short_subject(title: str) -> str:
    """Titel auf ein zitierfähiges Subjekt kürzen (vor dem ersten Gedankenstrich/
    Doppelpunkt), damit die Frage nicht zur Bandwurmzeile wird."""
    t = re.split(r"\s+[—–-]\s+|:\s+", title.strip())[0].strip()
    return (t[:60].rstrip() + "…") if len(t) > 60 else t


# Zitat-Klammern. Muss mit einer Ziffer beginnen, damit normaler Klammertext
# („[siehe oben]") unangetastet bleibt.
_CITE_RE = re.compile(r"\[(\d[^\]\n]{0,160})\]")


def citation_ids(inner: str) -> list[int]:
    """Beschluss-ids aus einem Klammerinhalt.

    Rein numerische Klammern listen mehrere Beschlüsse (``[12, 13]``). Steht
    noch etwas anderes drin, zählt NUR die führende Zahl: Das Modell hängt trotz
    Prompt-Regel gern Datum oder Tragweite an (``[8525, 2026-04-20, Tragweite:
    hoch]``) — würde man dort alle Zahlen lesen, entstünde aus „2026-04-20" die
    Geister-id 2026, die zufällig einen ganz anderen Beschluss treffen kann.

    Die Frontend-Fußnoten (``council-qa.tsx``) wenden dieselbe Regel an; beide
    müssen übereinstimmen, sonst laufen Nummerierung und ``cited`` auseinander.
    """
    if re.fullmatch(r"[\d,\s]+", inner):
        return [int(n) for n in re.findall(r"\d+", inner)]
    m = re.match(r"\s*(\d+)", inner)
    return [int(m.group(1))] if m else []


def zitierte_ids(text: str) -> list[int]:
    """Alle Beschluss-ids, die ein Antworttext zitiert — ohne Gültigkeitsprüfung.

    resolve_citations braucht das Kandidatenset, um Geister-ids zu streichen.
    Beim Vereinfachen ist es andersherum: Dort sind die ids aus der vorigen
    Antwort der Anlass, die zugehörigen Beschlüsse überhaupt nachzuladen.
    """
    out: list[int] = []
    for m in _CITE_RE.finditer(text or ""):
        for v in citation_ids(m.group(1)):
            if v not in out:
                out.append(v)
    return out


def resolve_citations(answer: str, valid: set[int]):
    """Parse `[id]` / `[id, id, …]` citations → ``(cleaned_answer, cited_ids)``.
    Keeps only ids we actually retrieved (``valid``), preserving order, and strips
    any invalid citation numbers from the text so no dangling [N] is shown."""
    cited: list[int] = []
    for m in _CITE_RE.finditer(answer):
        for v in citation_ids(m.group(1)):
            if v in valid and v not in cited:
                cited.append(v)

    def _clean(m: "re.Match") -> str:
        nums = [str(v) for v in citation_ids(m.group(1)) if v in valid]
        return f" [{', '.join(nums)}]" if nums else ""

    cleaned = re.sub(r"\s*" + _CITE_RE.pattern, _clean, answer).strip()
    return cleaned, cited
