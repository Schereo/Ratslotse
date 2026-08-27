"""Question answering over council decisions ("Frag den Stadtrat").

Retrieval is keyword-based (German nouns from the question), then the LLM answers
*only* from the retrieved decisions and cites them by id. Honest by construction:
if the retrieved decisions don't answer the question, the model says so. Semantic
embedding retrieval is the planned upgrade (see council-ai-roadmap).
"""
from __future__ import annotations

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


# Die Prompt-Templates leben in nwz/prompts.py („qa_antwort" / „qa_suchbegriffe")
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
QUERY_TYPES = ("thema", "verlauf", "partei", "geld", "person", "sitzung", "ort")
_ANALYSE_CACHE: dict[str, dict] = {}


# Wie viel Gespräch die Analyse/Antwort sieht: die letzten Runden reichen —
# ältere Bezüge löst niemand mehr per „dazu" auf.
VERLAUF_MAX_RUNDEN = 3
_VERLAUF_FRAGE_MAX = 250
_VERLAUF_ANTWORT_MAX = 400


def _verlauf_zeilen(verlauf: list[dict] | None) -> str:
    """Gesprächsverlauf als kompakte Zeilen (leer ohne Verlauf)."""
    zeilen = []
    for runde in (verlauf or [])[-VERLAUF_MAX_RUNDEN:]:
        frage = " ".join(str(runde.get("frage") or "").split())[:_VERLAUF_FRAGE_MAX]
        antwort = " ".join(str(runde.get("antwort") or "").split())[:_VERLAUF_ANTWORT_MAX]
        if frage:
            zeilen.append(f"- Frage: {frage}" + (f" — Antwort (gekürzt): {antwort}" if antwort else ""))
    return "\n".join(zeilen)


def analyse_query(question: str, model: str = EXPAND_MODEL,
                  verlauf: list[dict] | None = None) -> dict:
    """{"frage", "begriffe", "typ", "partei"} zur Frage. ``frage`` ist die
    EIGENSTÄNDIGE Fassung: Bei mitgegebenem Gesprächsverlauf (Chat) löst die
    Analyse Rückbezüge auf („Und was kostet das?" → „Was kostet der Neubau der
    Cäcilienbrücke?"), sonst bleibt sie die Original-Frage. Retrieval UND
    Reranker arbeiten mit dieser Fassung. Robust: bei kaputtem JSON oder
    LLM-Fehler kommt das Verhalten von vor dem Routing zurück."""
    fallback = {"frage": question, "begriffe": question, "typ": "thema", "partei": None,
                "varianten": [], "eng": False}
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
            model=model, _feature="qa_analyse", temperature=0, max_tokens=320,
            timeout=8.0, response_format={"type": "json_object"},
            messages=[{"role": "user", "content": prompt}], **extra,
        )
        data = json.loads(_strip_fences(resp.choices[0].message.content or ""))
        frage = " ".join(str(data.get("frage") or "").split())[:300]
        begriffe = " ".join(str(data.get("begriffe") or "").split())
        typ = str(data.get("typ") or "").strip().lower()
        partei = (str(data.get("partei")).strip() or None) if data.get("partei") else None
        # Multi-Query (Task 32): Perspektiv-Umformulierungen füllen Lücken,
        # die die eine Expansion verfehlt („Wie ist der Stand?" findet keine
        # Finanzierungs-Beschlüsse). Kandidaten-Union passiert in hybrid_search.
        varianten = [" ".join(str(v).split())[:120]
                     for v in (data.get("varianten") or []) if isinstance(v, str) and str(v).strip()][:2]
        # Punktfrage? („Wann wurde X beschlossen?") — dann antwortet das Modell
        # knapp statt mit Verlauf + Debatten-Absatz. Reist im ohnehin laufenden
        # Analyse-Call mit, kostet also keine zusätzliche Latenz.
        eng = bool(data.get("eng") is True)
        if typ not in QUERY_TYPES or typ in ("person", "sitzung", "ort"):
            # „person"/„sitzung"/„ort" setzt ausschließlich der Router
            # (deterministische Erkennung) — behauptet das Modell den Typ,
            # fehlt die Person bzw. die aufgelöste Sitzung.
            typ = "thema"
        if typ != "partei":
            partei = None
        out = {"frage": frage or question, "begriffe": begriffe or question,
               "typ": typ, "partei": partei, "varianten": varianten, "eng": eng}
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
    "thema": "",
    "verlauf": (
        "Diese Frage zielt auf den VERLAUF: Erzähle chronologisch (die Beschlüsse "
        "stehen bereits älteste zuerst), nenne zu jeder Station das Datum — die "
        "Datums-Regel oben gilt für diese Frage NICHT — und ende mit dem aktuellen "
        "Stand. 4–8 Sätze sind hier angemessen."
    ),
    "partei": (
        "Diese Frage zielt auf eine Fraktion/Gruppe: Stütze dich auf deren Anträge "
        "und Änderungsanträge (im Kontext als „Antrag von: …“ markiert) und auf "
        "ausdrücklich protokollierte Abstimmungssätze. WICHTIG: Das Ratsinfo kennt "
        "kein Stimmverhalten einzelner Fraktionen — behaupte NIE, wie eine Fraktion "
        "gestimmt hat, wenn es nicht wörtlich im Abstimmungssatz steht; sage dann, "
        "dass die Protokolle das nicht hergeben."
    ),
    "geld": (
        "Diese Frage zielt auf Beträge: Nenne die konkreten Summen aus den "
        "Beschlüssen (im Kontext als „Volumen: …“ markiert), gerundet und mit "
        "Einordnung, wofür das Geld ist. Tauchen zum selben Vorhaben mehrere "
        "Summen aus verschiedenen Jahren auf, benenne die Entwicklung mit "
        "Ausgangs- und Endwert samt Datum und zitiere beide Beschlüsse."
    ),
    "ort": (
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
    "sitzung": (
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


def recency_intent(frage: str) -> bool:
    """Fragt jemand nach dem HEUTIGEN Stand? Wortliste statt LLM-Feld —
    deterministisch, kostenlos, testbar. Eine konkrete Jahreszahl in der
    Frage schaltet den Bonus ab (wer nach 2019 fragt, will 2019)."""
    return bool(_RECENCY_RE.search(frage)) and not _HISTORISCH_RE.search(frage)


def latest_intent(frage: str) -> bool:
    """Will die Frage ausdrücklich die zeitlich neuesten Entscheidungen?

    Enger als :func:`recency_intent`: Ein allgemeiner „aktueller Stand“ braucht
    weiterhin die fachlich relevantesten Stationen. Bei „zuletzt beschlossen“
    ist dagegen das Datum die eigentliche Antwort und darf nicht gegen den
    semantisch ähnlichsten älteren Titel verlieren.
    """
    return bool(_LATEST_RE.search(frage or "")) and not _HISTORISCH_RE.search(frage or "")


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


def finde_entitaeten(store, frage: str, max_n: int = 2) -> list[dict]:
    """Deterministischer Frage-Anker: welche bekannten Entitäten (Themen-
    Seiten) nennt die Frage wörtlich? Matcht ganze Wörter auf gefalteten
    Namen UND den kuratierten Glossar-Aliassen (council_entity_aliases,
    source='glossar' — dieselbe Tabelle wie die Themen-Dubletten). Längere
    (spezifischere) Treffer zuerst, dann nach Beschlusszahl."""
    frage_f = f" {_falte(frage)} "
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
    Stammdaten kennen die Partei. Mutiert ``partei`` in-place; ohne
    Stammdaten-Treffer bleibt das quellentreue Gruppen-Label stehen.
    Zeitlich bleibt alles korrekt — die Protokoll-Labels selbst sind die
    zeitrichtige Quelle (Höpken stand damals als Linke im Protokoll), hier
    wird nur INNERHALB einer bestehenden Gruppe verfeinert."""
    betroffen = [r for r in rows
                 if _fraktions_label(r.get("partei")) in _AUFLOESBARE_GRUPPEN]
    if not betroffen:
        return
    try:
        mapping = {}
        for name, partei in store.personen_suchindex():
            nn = _nachname_gefaltet(name)
            if nn:
                mapping[nn] = partei
    except Exception:  # noqa: BLE001 — Auflösung ist Zusatz, nie Blocker
        return
    for r in betroffen:
        toks = _falte(r.get("sprecher") or "").split()
        partei = next((mapping[t] for t in reversed(toks) if t in mapping), None)
        if partei:
            r["partei"] = partei


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


def finde_person(store, frage: str) -> dict | None:
    """Personen-Fragetyp: Nennt die Frage eine Ratsperson (Voll- oder
    Nachname, umlaut-gefaltet, ganze Wörter)? Liefert
    {name, partei, nachname} — deterministisch, kostenlos."""
    try:
        index = store.personen_suchindex()
    except Exception:  # noqa: BLE001
        return None
    frage_f = f" {_falte(frage)} "
    treffer: list[tuple[int, dict]] = []
    for name, partei in index:
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
        treffer.append((laenge, {"name": name, "partei": partei, "nachname": original}))
    if not treffer:
        return None
    return max(treffer, key=lambda t: t[0])[1]


def finde_ort(frage: str, store=None) -> dict | None:
    """Katalogort in einer Frage deterministisch erkennen.

    Längere Aliase gewinnen, sodass „Neu-Donnerschwee“ nicht zusätzlich als
    allgemeines „Donnerschwee“ behandelt wird.
    """
    from council import places

    catalog_places = store.all_places() if store is not None else None
    found = places.find_mentions(frage, max_n=1, catalog_places=catalog_places)
    if not found:
        return None
    place = found[0]
    return {"id": place.id, "name": place.name, "kind": place.kind,
            "kind_label": places.kind_label(place.kind),
            "description": place.description}


def anker_ids_fuer(store, frage: str) -> list[int]:
    """Bequemer Einzeiler für alle Aufrufer (Router, Deep-Research, Evals):
    erkannte Entitäten → deren Beschluss-ids, neueste zuerst. Leer bei
    Fehlern — der Anker ist Zusatz, nie Blocker."""
    try:
        ent = finde_entitaeten(store, frage)
        return store.decision_ids_for_entities([e["id"] for e in ent]) if ent else []
    except Exception:  # noqa: BLE001
        return []


def steckbriefe_fuer(store, frage: str, max_n: int = 2) -> list[dict]:
    """Kurzbeschreibungen der in der Frage genannten Entitäten.

    „Was ist die GSG, was macht sie?" (echte Nutzerfrage 11.08.) lässt sich aus
    Beschlüssen kaum beantworten — die dokumentieren Entscheidungen, nicht
    Hintergrund. Die Beschreibung dazu liegt fertig in ``council_entity_meta``.
    Leer bei Fehlern: Hintergrund ist Zusatz, nie Blocker.
    """
    try:
        ent = finde_entitaeten(store, frage, max_n=max_n)
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


def _datum_in_frage(frage: str) -> tuple[str | None, str | None]:
    """(ISO-Datum, None) bei vollem Datum, (None, "-MM-DD") ohne Jahr,
    (None, None) ohne Fund. Eine Zeitraum-Präposition davor („seit dem …")
    disqualifiziert den Fund — das ist eine Spannen-, keine Terminangabe."""
    for m in list(_DATUM_NUM_RE.finditer(frage)) + list(_DATUM_WORT_RE.finditer(frage)):
        if _ZEITRAUM_PREP_RE.search(frage[:m.start()]):
            continue
        tag, monat_raw = int(m.group(1)), m.group(2)
        monat = int(monat_raw) if monat_raw.isdigit() else _MONATE[_falte(monat_raw)]
        if not (1 <= tag <= 31 and 1 <= monat <= 12):
            continue
        if m.group(3):
            jahr = int(m.group(3))
            if jahr < 100:
                jahr += 2000
            return f"{jahr:04d}-{monat:02d}-{tag:02d}", None
        return None, f"-{monat:02d}-{tag:02d}"
    for m in _RELATIV_RE.finditer(frage):
        if _ZEITRAUM_PREP_RE.search(frage[:m.start()]):
            continue  # „bis heute", „seit gestern", „ab morgen" sind Spannen
        wort = (m.group(1) or m.group(2)).lower()
        if wort == "morgen" and _MORGEN_TAGESZEIT_RE.search(frage[:m.start()]):
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


def _gremium_in_frage(store, frage: str) -> str | None:
    """Gefaltetes Namens-Fragment des gefragten Gremiums, ``"rat"`` fürs
    Plenum, None ohne Gremium. Vollnamen kommen aus dem Bestand (sie ändern
    sich über die Jahre), Kurzformen („Bauausschuss") aus der Alias-Tabelle.
    „Rat"/„Stadtrat" allein ist bewusst NUR ein Gremium-Signal — den Ausschlag
    gibt erst das Datum bzw. die Sitzungs-Phrase (finde_sitzungen)."""
    frage_f = f" {_falte(frage)} "
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


def finde_sitzungen(store, frage: str) -> list[dict]:
    """Sitzungs-Fragetyp: Nennt die Frage ein konkretes Sitzungsdatum („am
    17.06.2026", „17. Juni") oder die letzte/nächste Sitzung eines Gremiums?
    Liefert die gemeinten Sitzungen, jede mit ``beschluss_ids`` in
    Tagesordnungs-Reihenfolge und — solange es keine Beschlüsse gibt — der
    Tagesordnung. Deterministisch wie finde_person; leer bei Fehlern, der
    Sitzungs-Anker ist Zusatz, nie Blocker."""
    try:
        return _finde_sitzungen(store, frage)
    except Exception:  # noqa: BLE001
        return []


def _finde_sitzungen(store, frage: str) -> list[dict]:
    from datetime import date as _date
    heute = _date.today().isoformat()
    datum, monat_tag = _datum_in_frage(frage)
    gremium = _gremium_in_frage(store, frage)
    frage_f = _falte(frage)
    rows: list[dict] = []
    if (datum or monat_tag) and not gremium and not _SITZUNG_ANLASS_RE.search(frage_f):
        return []
    if datum:
        rows = [r for r in store.sessions_on(datum)
                if gremium is None or _gremium_passt(gremium, r.get("committee"))]
    elif monat_tag:
        # Ohne Jahr: die jüngste vergangene Sitzung an diesem Monatstag —
        # gibt es nur künftige, die nächstliegende.
        alle = [r for r in store.sitzungen_am_monatstag(monat_tag)
                if gremium is None or _gremium_passt(gremium, r.get("committee"))]
        vergangene = [r for r in alle if str(r.get("session_date") or "") <= heute]
        rows = vergangene[:1] if vergangene else sorted(
            alle, key=lambda r: str(r.get("session_date") or ""))[:1]
        if rows and gremium is None:
            # Datum ohne Gremium meint den TAG — alle Sitzungen dieses Tages.
            rows = store.sessions_on(rows[0]["session_date"])
    elif gremium and _SITZUNG_ZURUECK_RE.search(frage_f):
        rows = [r for r in store.recent_sessions(limit=80)
                if _gremium_passt(gremium, r.get("committee"))][:1]
        if rows and not store.decision_ids_der_sitzung(rows[0]["ksinr"]):
            # Trägt die jüngste Sitzung noch kein ausgewertetes Protokoll,
            # gehört die letzte MIT Beschlüssen dazu — die Antwort kann dann
            # beides ehrlich benennen statt stumm leer auszugehen.
            for r in store.recent_sessions(limit=80):
                if _gremium_passt(gremium, r.get("committee")) \
                        and store.decision_ids_der_sitzung(r["ksinr"]):
                    rows.append(r)
                    break
    elif gremium and _SITZUNG_VORAUS_RE.search(frage_f):
        rows = [r for r in store.upcoming_sessions(limit=40)
                if _gremium_passt(gremium, r.get("committee"))][:1]
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
            s["agenda"] = [{"item_number": a.get("item_number"),
                            "title": a.get("title"), "summary": a.get("summary")}
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
            zeile = f"  · TOP {a.get('item_number') or '?'}: {(a.get('title') or '')[:160]}"
            if a.get("summary"):
                zeile += f" — {' '.join(a['summary'].split())[:200]}"
            zeilen.append(zeile)
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
    datum = _datum_de(s["session_date"]) if s.get("session_date") else "unbekanntem Datum"
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
        return (f"{name} tagt erst am {datum} — Beschlüsse gibt es von dieser "
                f"Sitzung also noch nicht.{to}")
    return (f"{name} hat am {datum} getagt, aber das Protokoll liegt noch "
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
    basen = [b for b in (_vorlage_basis(c.get("vorlage_nr")) for c in candidates) if b]
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
            or (_vorlage_basis(c.get("vorlage_nr"))
                and _vorlage_basis(r.get("vorlage_nr")) == _vorlage_basis(c.get("vorlage_nr"))))]
        juengere = [r for r in gruppe if str(r.get("session_date") or "") > eigenes_datum]
        if not juengere:
            continue
        top = max(juengere, key=lambda r: str(r.get("session_date") or ""))
        c["neuere_station"] = {
            "id": top["id"] if top["id"] in kandidaten_ids else None,
            "datum": top.get("session_date"), "committee": top.get("committee"),
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
        datum = _datum_de(c["session_date"]) if c.get("session_date") else None
        meta = " · ".join(p for p in (c.get("committee"), datum, c.get("outcome")) if p)
        body = (c.get("summary") or c.get("beschluss") or "").strip()[:450]
        vorlage = (c.get("vorlage_excerpt") or "").strip()
        suffix = f" — Aus der Vorlage: {vorlage}" if vorlage else ""
        antragsteller = _factions_of(c)
        if antragsteller:
            suffix += f" — Antrag von: {', '.join(antragsteller)}"
        strittig = (c.get("gegenstimmen") or 0) > 0 or (c.get("enthaltungen") or 0) > 0 \
            or c.get("vote") == "mehrheitlich" or c.get("outcome") == "abgelehnt"
        raw_result = (c.get("raw_result") or "").strip()
        if strittig and raw_result:
            suffix += f" — Abstimmung: {raw_result[:180]}"
        if c.get("amount_eur"):
            suffix += f" — Volumen: {c['amount_eur']:,.0f} €".replace(",", ".")
        if c.get("beteiligung"):
            suffix += (f" — BÜRGERBETEILIGUNG LÄUFT: {c['beteiligung']} "
                       f"(Stellungnahme auf oldenburg.planungsbeteiligung.de möglich — "
                       f"erwähne das in der Antwort, wenn es zur Frage passt)")
        if c.get("amt"):
            suffix += f" — Federführung: {c['amt']}"
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
        if ernte.klima_relevant(c.get("klima_check")):
            suffix += f" — Klima-Check der Verwaltung: {c['klima_check'][:200]}"
        if c.get("abweichung") == "stark":
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
        if ns and ns.get("datum"):
            verweis = f", siehe [{ns['id']}]" if ns.get("id") else ""
            gremium = f" ({ns['committee']})" if ns.get("committee") else ""
            suffix += (f" — ⚠ ÄLTERE STATION: Zu dieser Vorlage gibt es eine NEUERE Station "
                       f"vom {_datum_de(ns['datum'])}{gremium}{verweis} — "
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


def deep_zerlege(frage: str, model: str = EXPAND_MODEL) -> list[dict]:
    """Deep Research (Task 34): Frage → 3-5 Recherche-Facetten
    [{name, frage, begriffe}]. Fallback: eine Facette = die Frage selbst."""
    fallback = [{"name": "Gesamtbild", "frage": frage, "begriffe": frage}]
    extra = {"extra_body": {"reasoning": {"enabled": False}}} if "deepseek" in model else {}
    try:
        resp = llm.chat_complete(
            model=model, _feature="deep_zerlegung", temperature=0, max_tokens=500,
            timeout=12.0, response_format={"type": "json_object"},
            messages=[{"role": "user", "content": prompts.render("deep_zerlegung",
                                                                 frage=frage.strip()[:300])}],
            **extra)
        data = json.loads(_strip_fences(resp.choices[0].message.content or ""))
        facetten = []
        for f in (data.get("facetten") or [])[:5]:
            if not isinstance(f, dict):
                continue
            fr = " ".join(str(f.get("frage") or "").split())[:200]
            if not fr:
                continue
            facetten.append({
                "name": " ".join(str(f.get("name") or "Facette").split())[:40],
                "frage": fr,
                "begriffe": " ".join(str(f.get("begriffe") or fr).split())[:200],
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
    Deep-Research-Kontext.

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
        marke = " ".join(str(a.get("label") or "").split()).lower()[:60]
        if marke and marke in gesehen:
            continue
        gesehen.add(marke)
        frisch.append(a)
    zeilen = "\n".join(
        f"[A{a.get('nr') or i + 1}] {a.get('label') or 'Anlage'} "
        f"(zur Vorlage {a.get('vorlage_nr') or '?'}"
        f"{' — ' + a['vorlage_titel'][:80] if a.get('vorlage_titel') else ''}): "
        f"{(a.get('fundstelle') or '').strip()[:ANLAGEN_ZEICHEN]}"
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
        f"- {p.get('vorlage_titel') or p.get('vorlage_nr')}: {p.get('gremium')} am "
        f"{_datum_de(p.get('datum'))}" for p in planungen[:8])
    return ("\nGEPLANTE NÄCHSTE STATIONEN (aus den Beratungsfolgen — für den Abschnitt "
            "„Wie es weitergeht“; als Termin nennen, NIE mit [id]):\n" + zeilen + "\n")


def deep_bericht_stream(frage: str, candidates: list[dict],
                        presse: list[dict] | None = None,
                        debatten: list[dict] | None = None,
                        haushalt: list[dict] | None = None,
                        planungen: list[dict] | None = None,
                        anlagen: list[dict] | None = None,
                        model: str = MODEL):
    """Der lange Deep-Research-Bericht als Token-Stream (Task 34)."""
    zusatz = (_debatten_block(debatten) + _presse_block(presse)
              + _haushalt_block(haushalt) + _anlagen_block(anlagen))
    prompt = prompts.render("deep_bericht", frage=frage.strip()[:300],
                            context=_build_context(candidates),
                            zusatz=zusatz,
                            planungen=_planungen_block(planungen))
    extra = {"extra_body": {"reasoning": {"enabled": False}}} if "deepseek" in model else {}
    yield from llm.chat_stream(model=model, _feature="deep_bericht", temperature=0.2,
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
        label = ratspartei_label(r.get("partei")) or _fraktions_label(r.get("partei"))
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
            f"  - {b.get('sprecher') or '?'} am {_datum_de(b.get('session_date'))}: "
            f"{(b.get('text') or '').strip()[:300]}"
            for b in gruppen[label])
        teile.append(f"{label} ({len(gruppen[label])} Beiträge):\n{zeilen}")
    prompt = prompts.render("partei_meinungen", frage=question.strip()[:300],
                            beitraege="\n".join(teile))
    extra = {"extra_body": {"reasoning": {"enabled": False}}} if "deepseek" in model else {}
    # 2000 Token reichten nicht mehr: Mit dem Beschluss-Anker stehen bis zu 15
    # Fraktionen und Verbände im Prompt, die Antwort lief mitten in der AfD-
    # Position ins Limit („finish_reason: length", an der Baumschutz-Frage
    # gemessen) — und ein abgeschnittenes Array ließ den Baustein KOMPLETT
    # verschwinden. Erst Platz schaffen, dann trotzdem retten, was da ist.
    resp = llm.chat_complete(model=model, _feature="partei_meinungen", temperature=0,
                             max_tokens=6000, messages=[{"role": "user", "content": prompt}],
                             **extra)
    content = _strip_fences(resp.choices[0].message.content or "") if resp.choices else ""
    data = _json_array_notfalls_gerettet(content)
    if data is None:
        return None
    out = []
    for e in data:
        if not isinstance(e, dict) or e.get("partei") not in gruppen:
            continue  # Halluzinations-Guard: nur Fraktionen aus dem Input
        kern = e.get("kernaussage") if isinstance(e.get("kernaussage"), dict) else None
        haltung = str(e.get("haltung") or "").strip().lower()
        out.append({
            "partei": e["partei"],
            "haltung": haltung if haltung in ("dafür", "dagegen", "offen", "gewandelt") else "offen",
            "position": str(e.get("position") or "").strip()[:400],
            "einig": bool(e.get("einig", True)),
            "hinweis": (str(e.get("hinweis")) or "").strip()[:200] or None if e.get("hinweis") else None,
            "kernaussage": {
                "text": str(kern.get("text") or "").strip()[:300],
                "sprecher": str(kern.get("sprecher") or "").strip()[:80] or None,
                "datum": str(kern.get("datum") or "").strip()[:10] or None,
            } if kern and kern.get("text") else None,
            "beitraege": len(gruppen[e["partei"]]),
            # Aufklappbare Zeile (Tims Wunsch): die verdichteten Beiträge im
            # Wortlaut — dieselben, die auch das LLM gesehen hat.
            "beitraege_liste": [{
                "sprecher": b.get("sprecher"),
                "datum": _datum_de(b.get("session_date")),
                "art": b.get("art"),
                "gremium": b.get("committee"),
                "text": (b.get("text") or "").strip()[:2000],
            } for b in gruppen[e["partei"]]],
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
        f"- {p.get('titel', '')} (Pressemitteilung der Stadt vom {_datum_de(p.get('datum'))}): "
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
    art_label = {"anfrage": "Anfrage", "einwohnerfrage": "Einwohnerfrage",
                 "zusage": "Zusage der Verwaltung", "rede": "Redebeitrag"}
    zeilen = []
    for d in debatten:
        wer = d.get("sprecher") or "?"
        if d.get("partei"):
            wer += f" ({d['partei']})"
        kopf = f"{art_label.get(d.get('art') or 'rede', 'Redebeitrag')} von {wer}"
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
        zeile = f"- {kopf}: {(d.get('text') or '').strip()[:400]}"
        if d.get("antwort"):
            zeile += f" — Antwort der Verwaltung: {(d['antwort'] or '').strip()[:300]}"
        zeilen.append(zeile)
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
            "Selbstverpflichtung und für die Leserin oft das Verwertbarste am\n"
            "ganzen Protokoll:\n"
            + "\n".join(zeilen) + "\n")


def _haushalt_block(zeilen: list[dict] | None) -> str:
    """Kontext-Absatz mit Plan-Zahlen aus dem Stadthaushalt (Geldfragen).
    KEINE Beschlüsse: nie mit [id] zitieren, sondern als „Laut Haushaltsplan
    JAHR …" nennen."""
    if not zeilen:
        return ""
    def eur(v):
        return f"{v:,.0f} €".replace(",", ".") if v is not None else "–"
    z = "\n".join(
        f"- {r['bereich']} ({r['year']}): Aufwendungen {eur(r.get('aufwendungen'))}, "
        f"Erträge {eur(r.get('ertraege'))}"
        for r in zeilen)
    return ("\nSTADTHAUSHALT (Plan-Zahlen; nur nutzen, wenn einschlägig — im Text als\n"
            "„Laut Haushaltsplan JAHR …“ nennen, NIE mit [id]):\n" f"{z}\n")


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


def steckbrief_karte_zeigen(frage: str) -> bool:
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
    if not _DEFINITIONSFRAGE.match(frage or ""):
        return True
    return bool(_EIGENES_PRAEDIKAT.search(frage or ""))

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


def _answer_messages(question: str, candidates: list[dict], typ: str = "thema",
                     model: str = MODEL, presse: list[dict] | None = None,
                     verlauf: list[dict] | None = None,
                     haushalt: list[dict] | None = None,
                     debatten: list[dict] | None = None,
                     gross: bool = False, steckbriefe: list[dict] | None = None,
                     duenn: bool = False, eng: bool = False,
                     sitzungen: list[dict] | None = None,
                     ort: dict | None = None) -> tuple[list[dict], dict]:
    vtext = _verlauf_zeilen(verlauf)
    gespraech = (f"Dies ist eine Anschlussfrage in einem Gespräch. Bisher:\n{vtext}\n\n"
                 if vtext else "")
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
        ortsregel += (
            "\nCHRONOLOGIE: Die Frage verlangt ausdrücklich das Neueste. Die "
            "Beschlüsse stehen neueste zuerst. Beginne mit der zeitlich neuesten "
            "echten Entscheidung; unterscheide angenommene/abgelehnte Beschlüsse "
            "klar von bloßen Berichten oder Kenntnisnahmen."
        )
    prompt = prompts.render("qa_antwort", question=question.strip()[:300],
                            context=_build_context(candidates),
                            extra_regeln=(ENG_REGEL if eng else EXTRA_REGELN.get(typ, ""))
                            + ortsregel
                            + ("" if eng else (GROSS_REGEL if gross else ""))
                            + (DUENN_REGEL if duenn else ""),
                            presse=_sitzungen_block(sitzungen)
                            + _steckbrief_block(steckbriefe) + _presse_block(presse)
                            + _haushalt_block(haushalt) + _debatten_block(debatten, eng),
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


def will_vereinfachung(frage: str) -> bool:
    """Bittet diese Frage darum, die vorige Antwort einfacher zu erklären?

    Deterministisch statt per LLM — der Knopf schickt immer denselben Satz, und
    wer ihn selbst tippt („erklär mir das mal einfacher", „ohne Fachbegriffe
    bitte"), meint dasselbe. Eine lange, inhaltliche Frage bleibt eine Frage,
    auch wenn irgendwo „einfacher" darin vorkommt.
    """
    text = " ".join((frage or "").split())
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


def vereinfachen_messages(frage: str, bisher: str | None, candidates: list[dict],
                          model: str = MODEL) -> tuple[list[dict], dict]:
    """Prompt für den Vereinfachungs-Modus. Bewusst OHNE Presse-, Debatten- und
    Haushalts-Block: Deren Kontext-Anweisungen („ergänze IMMER einen Absatz zum
    Meinungsbild") arbeiten gegen die Kürze — genau daran ist die beiläufige
    Bitte im normalen Prompt schon gescheitert."""
    prompt = prompts.render("qa_einfach", frage=frage.strip()[:300],
                            bisher=_bisher_block(bisher),
                            context=_build_context(candidates))
    extra = {"extra_body": {"reasoning": {"enabled": False}}} if "deepseek" in model else {}
    return [{"role": "user", "content": prompt}], extra


#: Kurz ist das Ziel — das Budget ist die zweite Bremse neben der Prompt-Regel.
VEREINFACHEN_TOKENS = 700


def vereinfachen_stream(frage: str, bisher: str | None, candidates: list[dict],
                        model: str = MODEL):
    """Die einfache Fassung als Token-Stream (wie answer_stream)."""
    messages, extra = vereinfachen_messages(frage, bisher, candidates, model)
    yield from llm.chat_stream(model=model, _feature="qa_einfach", temperature=0.2,
                               max_tokens=VEREINFACHEN_TOKENS, messages=messages, **extra)


def vereinfachen_question(frage: str, bisher: str | None, candidates: list[dict],
                          model: str = MODEL):
    """One-shot-Variante für den Ersatzweg, wenn der Stream abreißt.
    Liefert ``(antwort, cited_ids)`` wie answer_question."""
    messages, extra = vereinfachen_messages(frage, bisher, candidates, model)
    resp = llm.chat_complete(model=model, _feature="qa_einfach", temperature=0.2,
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
    if typ == "sitzung":
        # Der Rückblick muss JEDEN Punkt der Sitzung erwähnen dürfen.
        return 1400
    return 1100 if typ == "verlauf" else 1000


def answer_question(question: str, candidates: list[dict], model: str = MODEL, typ: str = "thema",
                    presse: list[dict] | None = None, verlauf: list[dict] | None = None,
                    haushalt: list[dict] | None = None, debatten: list[dict] | None = None,
                    gross: bool = False, steckbriefe: list[dict] | None = None,
                    duenn: bool = False, eng: bool = False,
                    sitzungen: list[dict] | None = None,
                    ort: dict | None = None):
    """Synthesise an answer from retrieved candidates. Returns ``(answer, cited_ids)``."""
    messages, extra = _answer_messages(question, candidates, typ, model, presse, verlauf,
                                       haushalt, debatten, gross, steckbriefe, duenn, eng,
                                       sitzungen, ort)
    resp = llm.chat_complete(model=model, _feature="qa_antwort", temperature=0.2,
                             max_tokens=_answer_tokens(typ, gross, eng), messages=messages, **extra)
    answer = (resp.choices[0].message.content or "").strip()
    return resolve_citations(answer, {c["id"] for c in candidates})


def answer_stream(question: str, candidates: list[dict], model: str = MODEL, typ: str = "thema",
                  presse: list[dict] | None = None, verlauf: list[dict] | None = None,
                  haushalt: list[dict] | None = None, debatten: list[dict] | None = None,
                  gross: bool = False, steckbriefe: list[dict] | None = None,
                  duenn: bool = False, eng: bool = False,
                  sitzungen: list[dict] | None = None,
                  ort: dict | None = None):
    """Stream the answer text deltas (same prompt/context as answer_question) so the
    UI can render the answer as it is written. Citation resolution is the caller's
    job once the full text is assembled (see resolve_citations)."""
    messages, extra = _answer_messages(question, candidates, typ, model, presse, verlauf,
                                       haushalt, debatten, gross, steckbriefe, duenn, eng,
                                       sitzungen, ort)
    yield from llm.chat_stream(model=model, _feature="qa_antwort", temperature=0.2,
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
        if (c.get("gegenstimmen") or 0) > 0 and (c.get("title") or "").strip():
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
