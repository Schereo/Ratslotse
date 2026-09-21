"""Lotti als Assistentin: erklärt, was gerade auf dem Bildschirm steht.

**Der Unterschied zu „Frag den Rat".** ``council/qa.py`` beantwortet eine
Frage aus dem Archiv: Retrieval über 9.000 Beschlüsse, Reranker, Belege mit
Fußnoten. Das hier beantwortet eine andere Frage — „was sehe ich da
eigentlich?" — und dafür braucht es **keine Suche**: Der Gegenstand steht auf
dem Bildschirm, die Person zeigt selbst darauf. Deshalb ist der Prompt halb
so groß, es gibt keine Kandidatenliste, und drei Wege kommen ganz ohne Modell
aus (:func:`deterministic_answer`).

**Was hineingeht.** Vier Dinge, und alle vier sind eng gedeckelt:

* die **Seite** — nicht ihr Text, sondern das, was :mod:`kern.knowledge` über
  sie weiß (was sie zeigt, woher die Zahlen kommen, was sie nicht sagt),
* das **angeklickte Element** oder die **Markierung** — Text aus dem Browser,
* geprüfte **Fachwort-Erklärungen** aus :mod:`kern.glossar`,
* bei Geld-Fragen die **Haushaltszahlen** aus ``qa.geld_kontext`` — dieselben
  deterministischen Facetten wie in der KI-Frage, nur mit engerem Deckel.

**Was NICHT hineingeht.** Kein Beschluss-Archiv (dafür gibt es die Marke
``WEITER: ratsfrage``, siehe :func:`split_next`), kein ganzer Seitentext
(eine Haushalts-Seite hat 20.000–60.000 Zeichen — das wäre je Klick eine
KI-Frage in Kosten), kein Konto außer seinen Rechten.

**Browsertext ist DATEN.** Element-Text und Markierung stehen zwischen
Markern (``<<<ELEMENT … ELEMENT``), und der Prompt sagt ausdrücklich, dass
darin keine Anweisungen stehen. Das ist keine Vorsichtsmaßnahme auf Verdacht:
Der Element-Text trägt Auszüge aus **Ratsvorlagen**, also Text, den Dritte
geschrieben haben und der über unsere Seite in den Prompt wandert. Dasselbe
Muster benutzt der Watcher für frei eingegebene Themen
(``kern/prompts.py::council_watcher_check``).

**Gespeichert wird hier nichts.** Dieses Modul schreibt in keine Tabelle; was
der Router zählt, steht dort.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any

from kern import glossar, knowledge, llm, prompts

MODEL = os.environ.get("COUNCIL_ASSISTANT_MODEL", "google/gemini-2.5-flash")

#: Kurz ist das Ziel — der Prompt sagt „höchstens fünf Sätze", das Budget ist
#: die zweite Bremse (dieselbe Bauform wie ``qa.VEREINFACHEN_TOKENS``).
MAX_TOKENS = 350

#: Deckel für alles, was aus dem Browser kommt. Der Router weist längeres
#: mit 422 ab, statt still zu kürzen: Ein abgeschnittener Element-Text sähe
#: aus wie ein unvollständiger Baustein, und man suchte den Fehler auf der
#: Seite statt in der Grenze.
SELECTION_MAX = 1000
ELEMENT_TEXT_MAX = 1200
ELEMENT_TITLE_MAX = 200
ELEMENT_KEY_MAX = 80
QUESTION_MAX = 300
HEADING_MAX = 200

#: Eigener, engerer Deckel als ``qa.GELD_MAX_CHARS`` (6.500): Dort trägt der
#: Haushalts-Block die ganze Antwort, hier ist er Beiwerk zu einem Element,
#: auf das jemand gezeigt hat.
GELD_MAX = 3000

#: Höchstens so viele geprüfte Fachwort-Erklärungen — wie beim
#: „Einfacher erklären"-Prompt, aus demselben Grund: Ein erklärter Baustein
#: trägt mehr Fachwörter als eine Frage.
GLOSSAR_MAX = 5

#: Die letzte Zeile der Antwort, wenn die Frage ins Archiv gehört. Dieselbe
#: Mechanik wie ``qa.FOLLOWUP_MARKER``: Der Router streamt alles davor als
#: Token und schneidet ab hier ab.
NEXT_MARKER = "WEITER:"

#: Wohin weitergereicht werden darf. Eine Marke, die hier nicht steht, wird
#: verworfen — ein Modell, das sich etwas ausdenkt, soll nichts auslösen.
NEXT_ZIELE = frozenset({"ratsfrage"})

#: Wie viele Runden des laufenden Gesprächs in den Prompt gehen.
VERLAUF_MAX_RUNDEN = 3
_VERLAUF_FRAGE_MAX = 200
_VERLAUF_ANTWORT_MAX = 300


@dataclass(frozen=True)
class Screen:
    """Was die Person gerade vor sich hat — die ganze Eingabe des Browsers."""

    #: Normalisiert über ``kern.seitenaufrufe.normalisieren``, nie roh.
    route: str
    page_title: str = ""
    #: Überschriften-Pfad: „Schulden › Rate-Treppe".
    heading: str = ""
    #: Der ``data-erklaer``-Schlüssel des angeklickten Elements.
    element_key: str | None = None
    element_title: str = ""
    element_text: str = ""
    selection: str = ""
    #: Nur Kennungen, nie Inhalte: ``decision_id``, ``ksinr``, ``slug``,
    #: ``place_id``, ``year``, ``area``.
    refs: dict[str, Any] = field(default_factory=dict)

    @property
    def gegenstand(self) -> str:
        """Woran sich Glossar und Haushalts-Facetten orientieren.

        Die Frage allein taugt nicht: „Was sehe ich hier?" nennt keinen
        Gegenstand. Der Bildschirm nennt ihn.
        """
        return " ".join(t for t in (self.heading, self.element_title,
                                    self.element_text, self.selection) if t)


def falte(text: str) -> str:
    """Kleinschreibung ohne Umlaute — dieselbe Faltung wie in ``qa``."""
    text = (text or "").lower()
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        text = text.replace(a, b)
    return re.sub(r"[^a-z0-9 ]+", " ", text)


def kuerze(text: str, max_len: int) -> str:
    """Whitespace falten und hart schneiden — für alles, was in den Prompt geht."""
    sauber = " ".join((text or "").split())
    return sauber if len(sauber) <= max_len else sauber[:max_len].rstrip() + " …"


#: Fragen, die nichts Eigenes wollen, sondern nur „erklär mir das da".
#: Genau diese Fälle dürfen ohne Modell beantwortet werden — sie sind die
#: Chips des Fensters und die häufigste getippte Frage.
_GENERISCH_RE = re.compile(
    r"^(?:"
    r"was (?:sehe|seh) ich (?:hier|da)"
    r"|was (?:ist|heisst|bedeutet|soll) (?:das|dies|die seite)"
    r"|was zeigt (?:mir )?(?:das|die seite)"
    r"|erklaer(?:e|s|t)?(?: mir)?(?: das| dies| die seite)?"
    r"|worum geht(?:s| es)(?: hier)?"
    r"|hilfe|erklaerung"
    r")\b",
)


def generische_frage(question: str) -> bool:
    """Bittet diese Frage nur darum, das Gezeigte zu erklären?

    Leer zählt mit: Der Klick auf ein Erklär-Abzeichen schickt keine Frage.
    """
    gefaltet = " ".join(falte(question).split())
    return not gefaltet or bool(_GENERISCH_RE.match(gefaltet))


#: Fragen, die nur das Beschluss-Archiv beantworten kann — deterministisch am
#: Wortlaut erkannt, nicht dem Modell überlassen.
#:
#: **Warum nicht dem Modell.** Es SOLL die Marke ``WEITER: ratsfrage`` selbst
#: setzen, und meistens tut es das auch. Am 21.09.2026 über drei Läufe
#: gemessen: zweimal gesetzt, einmal vergessen — und beim dritten Mal stand da
#: „das kann ich dir nicht sagen" ohne jeden Weg weiter. Genau das ist die
#: Sackgasse, gegen die die Designsprache „Fehler/Limits: immer mit Ausweg"
#: schreibt. Die Regex entscheidet deshalb mit; das Modell kann die
#: Weiterreichung nur noch HINZUFÜGEN, nie wegnehmen.
_ARCHIV_RE = re.compile(
    r"\b("
    r"wer (?:hat|hatte|stimmte|war)"
    r"|welche (?:fraktion|partei|mehrheit)"
    r"|wie (?:hat|haben) (?:der rat|die|das|er|sie)"
    r"|(?:was|wann|warum|wieso|weshalb) (?:wurde|wurden|hat|haben|ist) .{0,30}"
    r"(?:beschlossen|entschieden|abgestimmt|beantragt|abgelehnt|zugestimmt)"
    r"|(?:beschlossen|abgestimmt|beantragt|abgelehnt) (?:worden|wurde)"
    r"|welcher beschluss|welche beschluesse"
    r"|seit wann|wann hat der rat|wann wurde"
    r"|gab es (?:dazu|dafuer|einen|eine)"
    r")",
)


def archivfrage(question: str) -> bool:
    """Braucht diese Frage das Beschluss-Archiv statt des Bildschirms?

    Bewusst großzügig: Eine Frage zu viel weiterzureichen kostet einen Chip,
    den niemand drücken muss. Eine zu wenig ist eine Sackgasse.
    """
    return bool(_ARCHIV_RE.search(" ".join(falte(question).split())))


#: Kennungen, die auf EINEN Gegenstand zeigen — dann erklärt Lotti den, nicht
#: die Seite. ``year`` und ``area`` gehören nicht dazu: Sie wählen einen
#: Ausschnitt derselben Seite, keinen anderen Gegenstand.
_GEGENSTAND_REFS = ("decision_id", "ksinr", "slug", "place_id")


def _hat_gegenstand(screen: Screen) -> bool:
    return any(screen.refs.get(k) for k in _GEGENSTAND_REFS)


def deterministic_answer(store, screen: Screen, question: str) -> tuple[str, str] | None:
    """Die drei Wege ohne Modell — ``(Text, Art)`` oder ``None``.

    **Warum überhaupt.** Diese drei Fälle sind zusammen der häufigste Klick,
    und für alle drei liegt die geprüfte Antwort schon im Haus: das Glossar
    (151 Begriffe, kuratiert), die Beschluss-Kurzfassung („Lotti erklärt's
    einfach", je Beschluss einmal erzeugt) und das Seiten-Wissen. Ein Modell
    daraufzusetzen kostet Geld und Zeit und kann die geprüfte Antwort nur
    verschlechtern.

    Die Reihenfolge ist die vom Genauen zum Allgemeinen: Markierung schlägt
    Beschluss schlägt Seite.
    """
    if not generische_frage(question):
        return None

    # 1. Eine Markierung, die GENAU EINEN Fachbegriff trifft. Zwei Treffer
    #    heißen, dass die Person einen Satz markiert hat — dann ist nicht
    #    klar, was sie wissen will, und das Modell entscheidet.
    if screen.selection:
        treffer = glossar.finde(screen.selection, max_n=2)
        if len(treffer) == 1:
            b = treffer[0]
            return f"**{b['begriff']}** — {b['erklaerung']}", "glossary"

    # 2. Eine Beschluss-Seite ohne Markierung: Die Kurzfassung ist genau die
    #    Antwort auf „Was sehe ich hier?" und steht bereits in der Datenbank.
    if not screen.selection and not screen.element_key:
        decision_id = screen.refs.get("decision_id")
        if decision_id:
            try:
                d = store.get_decision(int(decision_id)) or {}
            except Exception:  # noqa: BLE001 — ohne Beschluss antwortet das Modell
                d = {}
            kurz = (d.get("simple_summary") or "").strip()
            if kurz:
                titel = (d.get("title") or "").strip()
                kopf = f"**{titel}**\n\n" if titel else ""
                return kopf + kurz, "simple_summary"

    # 3. Eine bekannte Seite, auf die niemand gezeigt hat und die keinen
    #    einzelnen Gegenstand trägt: Das Seiten-Wissen ist die Antwort, und
    #    es ist geprüfter Text.
    #
    #    Die zweite Bedingung ist der Unterschied zwischen „was ist diese
    #    Seite?" und „was steht hier?": Auf einer Beschluss-Seite OHNE
    #    Kurzfassung wäre der allgemeine Seitentext die Antwort auf die
    #    falsche Frage — dort soll das Modell den konkreten Beschluss
    #    erklären, den es im Kontext bekommt.
    if not screen.selection and not screen.element_key and not _hat_gegenstand(screen):
        wissen = knowledge.fuer_route(screen.route)
        if wissen:
            return f"{wissen.what}\n\n{wissen.limits}", "page"

    return None


def _record_block(store, screen: Screen) -> str:
    """Der Gegenstand hinter den Kennungen — Beschluss, Sitzung oder Ort.

    Nur über die **Kennung** aus der Adresszeile, nie über eine Suche: Was
    die Seite zeigt, steht fest; es zu erraten wäre ein zweiter, schlechterer
    Weg neben dem, den die Seite schon gegangen ist.
    """
    refs = screen.refs or {}
    teile: list[str] = []

    decision_id = refs.get("decision_id")
    if decision_id:
        try:
            d = store.get_decision(int(decision_id))
        except Exception:  # noqa: BLE001 — ein fehlender Beleg ist kein Fehler
            d = None
        if d:
            kopf = " · ".join(str(x) for x in (d.get("committee"), d.get("session_date"),
                                               d.get("outcome")) if x)
            zeilen = [f"Der Beschluss auf dieser Seite: „{kuerze(d.get('title') or '', 200)}“"
                      + (f" ({kopf})" if kopf else "")]
            if d.get("simple_summary"):
                zeilen.append(f"  Kurzfassung: {kuerze(d['simple_summary'], 500)}")
            if d.get("official_text"):
                zeilen.append(f"  Amtlicher Wortlaut (Auszug): {kuerze(d['official_text'], 600)}")
            teile.append("\n".join(zeilen))

    ksinr = refs.get("ksinr")
    if ksinr:
        try:
            s = store.get_session(int(ksinr))
        except Exception:  # noqa: BLE001
            s = None
        if s:
            teile.append(f"Die Sitzung auf dieser Seite: {s.get('committee') or ''} "
                         f"am {s.get('session_date') or 'unbekanntem Datum'}")

    place_id = refs.get("place_id")
    if place_id:
        try:
            ort = store.resolve_place(str(place_id))
        except Exception:  # noqa: BLE001
            ort = None
        if ort:
            # `resolve_place` liefert ein `Place`-Objekt, kein dict — die
            # Beschreibung aus dem Ortskatalog ist hier der eigentliche Wert:
            # Sie ist kuratierter Text und sagt, was dieser Ort überhaupt ist.
            teile.append(f"Der Ort auf dieser Seite: {ort.name} ({ort.kind})"
                         + (f" — {kuerze(ort.description, 400)}" if ort.description else ""))

    if not teile:
        return ""
    return "Der Gegenstand der Seite:\n" + "\n".join(teile) + "\n"


def _glossar_block(begriffe: list[dict]) -> str:
    """Die geprüften Erklärungen — als Bausteine, nicht zum Abschreiben."""
    if not begriffe:
        return ""
    zeilen = "\n".join(f"  · {b['begriff']}: {b['erklaerung']}" for b in begriffe)
    return ("- SO sind die Fachwörter gemeint, die hier vorkommen (geprüfte Erklärungen\n"
            "  aus dem Ratslotse-Glossar — nicht wörtlich übernehmen, daraus einen\n"
            f"  kurzen Alltagssatz machen):\n{zeilen}\n")


def _screen_block(screen: Screen) -> str:
    """Was auf dem Bildschirm steht — jeder Fremdtext zwischen Markern.

    Leere Blöcke fallen weg, statt als leere Marker dazustehen: Ein
    ``<<<AUSWAHL AUSWAHL`` ohne Inhalt liest sich für das Modell wie eine
    leere Markierung, und es kommentiert sie.
    """
    kopf = f"Seite: {screen.route}"
    if screen.heading:
        kopf += f" — {kuerze(screen.heading, HEADING_MAX)}"
    teile = [kopf]
    if screen.element_text or screen.element_title:
        titel = kuerze(screen.element_title, ELEMENT_TITLE_MAX) or "Baustein"
        teile.append("<<<ELEMENT\n"
                     f"{titel}: {kuerze(screen.element_text, ELEMENT_TEXT_MAX)}\n"
                     "ELEMENT")
    if screen.selection:
        teile.append("<<<AUSWAHL\n"
                     f"{kuerze(screen.selection, SELECTION_MAX)}\n"
                     "AUSWAHL")
    return "\n".join(teile)


def _verlauf_block(verlauf: list[dict] | None) -> str:
    """Die letzten Runden — damit „und das da?" einen Bezug hat."""
    if not verlauf:
        return ""
    zeilen = []
    for runde in verlauf[-VERLAUF_MAX_RUNDEN:]:
        frage = kuerze(str(runde.get("question") or ""), _VERLAUF_FRAGE_MAX)
        antwort = kuerze(str(runde.get("answer") or ""), _VERLAUF_ANTWORT_MAX)
        if frage:
            zeilen.append(f"  Frage: {frage}\n  Antwort: {antwort}")
    if not zeilen:
        return ""
    return ("\nBISHER IN DIESEM GESPRÄCH (beantworte NUR, was die neue Frage\n"
            "zusätzlich wissen will — wiederhole dich nicht):\n"
            + "\n".join(zeilen) + "\n")


def screen_context(store, screen: Screen, question: str, *,
                   permissions: frozenset[str] | set[str] = frozenset()) -> dict:
    """Alles, was der Prompt bekommt — ohne einen einzigen Modellaufruf."""
    wissen = knowledge.fuer_route(screen.route)
    gegenstand = screen.gegenstand
    begriffe = glossar.finde(f"{gegenstand}\n{question}", max_n=GLOSSAR_MAX)

    # Haushaltszahlen: nur, wo sie hingehören. Der Auslöser ist derselbe wie
    # in der KI-Frage (der Wortlaut entscheidet, nicht der Seitentyp) — aber
    # gefragt wird mit dem BILDSCHIRM, nicht mit der Frage: „Was sehe ich
    # hier?" nennt keinen Gegenstand, die Rate-Treppe schon.
    geld: dict = {}
    if wissen and (wissen.requires == "budget" or screen.route.startswith("/haushalt")):
        from council import qa  # lokal: qa ist groß, und nicht jeder Aufruf braucht es
        try:
            geld = qa.geld_kontext(store, gegenstand or question, gegenstand, "money")
        except Exception:  # noqa: BLE001 — Zahlen sind Zusatz, nie Blocker
            geld = {}

    return {
        "knowledge": wissen,
        "record": _record_block(store, screen),
        "glossary": begriffe,
        "geld": geld,
        "permissions": frozenset(permissions),
    }


def _geld_block(geld: dict | None) -> str:
    """Die Haushaltszahlen samt ihrer Regeln, auf ``GELD_MAX`` gedeckelt."""
    if not geld:
        return ""
    from council import qa
    block = qa.geld_block(geld, max_chars=GELD_MAX)
    if not block:
        return ""
    return ("\nZAHLEN AUS DEM HAUSHALT (geprüft, mit Jahr und Beleg — nenne beides,\n"
            "wenn du eine Zahl verwendest):\n" + block + "\n")


def explain_messages(screen: Screen, question: str, ctx: dict,
                     verlauf: list[dict] | None = None,
                     model: str = MODEL) -> tuple[list[dict], dict]:
    """Der fertige Prompt — ``(messages, extra)`` wie in ``qa``."""
    prompt = prompts.render(
        "assistant_explain",
        knowledge=knowledge.block(ctx.get("knowledge")),
        record=ctx.get("record") or "",
        glossar=_glossar_block(ctx.get("glossary") or []),
        geld=_geld_block(ctx.get("geld")),
        screen=_screen_block(screen),
        question=kuerze(question, QUESTION_MAX) or "(keine eigene Frage — erklär das Gezeigte)",
        gespraech=_verlauf_block(verlauf),
    )
    extra = {"extra_body": {"reasoning": {"enabled": False}}} if "deepseek" in model else {}
    return [{"role": "user", "content": prompt}], extra


def explain_stream(store, screen: Screen, question: str, *,
                   ctx: dict | None = None,
                   verlauf: list[dict] | None = None,
                   permissions: frozenset[str] | set[str] = frozenset(),
                   model: str = MODEL):
    """Die Erklärung als Token-Strom (wie ``qa.answer_stream``)."""
    ctx = ctx if ctx is not None else screen_context(
        store, screen, question, permissions=permissions)
    messages, extra = explain_messages(screen, question, ctx, verlauf, model)
    yield from llm.chat_stream(model=model, _feature="assistant_explain", temperature=0.2,
                               max_tokens=MAX_TOKENS, messages=messages, **extra)


def explain_question(store, screen: Screen, question: str, *,
                     ctx: dict | None = None,
                     verlauf: list[dict] | None = None,
                     permissions: frozenset[str] | set[str] = frozenset(),
                     model: str = MODEL) -> str:
    """Einmal komplett — der Ersatzweg, wenn der Strom abreißt."""
    ctx = ctx if ctx is not None else screen_context(
        store, screen, question, permissions=permissions)
    messages, extra = explain_messages(screen, question, ctx, verlauf, model)
    resp = llm.chat_complete(model=model, _feature="assistant_explain", temperature=0.2,
                             max_tokens=MAX_TOKENS, messages=messages, **extra)
    return (resp.choices[0].message.content or "").strip()


def split_next(text: str) -> tuple[str, str | None]:
    """``(Antworttext ohne die Marken-Zeile, Ziel)``.

    Das Modell hängt bei einer Archiv-Frage ``WEITER: ratsfrage`` als letzte
    Zeile an. Ein Ziel, das :data:`NEXT_ZIELE` nicht kennt, wird verworfen —
    die Zeile verschwindet trotzdem aus dem Text, denn sie ist in keinem Fall
    für Leser*innen gedacht.
    """
    if NEXT_MARKER not in text:
        return text.strip(), None
    kopf, _, rest = text.rpartition(NEXT_MARKER)
    ziel = rest.strip().split()[0].strip(".,;:").lower() if rest.strip() else ""
    return kopf.strip(), (ziel if ziel in NEXT_ZIELE else None)
