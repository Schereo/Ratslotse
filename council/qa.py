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

from nwz import llm, prompts
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
# „person" liefert die LLM-Analyse nie — der Typ wird deterministisch gesetzt,
# wenn finde_person eine Ratsperson in der Frage erkennt (Router).
QUERY_TYPES = ("thema", "verlauf", "partei", "geld", "person")
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
                "varianten": []}
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
        if typ not in QUERY_TYPES or typ == "person":
            # „person" setzt ausschließlich der Router (deterministische
            # Erkennung) — behauptet das Modell den Typ, fehlt die Person.
            typ = "thema"
        if typ != "partei":
            partei = None
        out = {"frage": frage or question, "begriffe": begriffe or question,
               "typ": typ, "partei": partei, "varianten": varianten}
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


def recency_intent(frage: str) -> bool:
    """Fragt jemand nach dem HEUTIGEN Stand? Wortliste statt LLM-Feld —
    deterministisch, kostenlos, testbar. Eine konkrete Jahreszahl in der
    Frage schaltet den Bonus ab (wer nach 2019 fragt, will 2019)."""
    return bool(_RECENCY_RE.search(frage)) and not _HISTORISCH_RE.search(frage)


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
    zeilen = "\n".join(
        f"[A{a.get('nr') or i + 1}] {a.get('label') or 'Anlage'} "
        f"(zur Vorlage {a.get('vorlage_nr') or '?'}"
        f"{' — ' + a['vorlage_titel'][:80] if a.get('vorlage_titel') else ''}): "
        f"{(a.get('fundstelle') or '').strip()[:500]}"
        for i, a in enumerate(anlagen))
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


def partei_meinungen(question: str, rows: list[dict], model: str = MODEL) -> list[dict] | None:
    """Baustein „Das sagen die Parteien" (Task 30): verdichtet Wortbeiträge je
    Fraktion zu Position + Kernaussage (+ „uneinheitlich"-Flag). None, wenn die
    Datenlage zu dünn ist (< 2 Fraktionen oder < 4 Beiträge) — der Baustein
    soll nur bei echten Debatten erscheinen."""
    gruppen: dict[str, list[dict]] = {}
    for r in rows:
        label = _fraktions_label(r.get("partei"))
        if not label:
            continue  # Verwaltung, Einwohner, Referenten — keine Fraktionsmeinung
        gruppen.setdefault(label, []).append(r)
    if len(gruppen) < 2 or sum(len(v) for v in gruppen.values()) < 4:
        return None
    teile = []
    for label in gruppen:
        # Chronologisch (älteste zuerst): so kann die Verdichtung eine
        # Entwicklung benennen („anfangs skeptisch, zuletzt dafür") statt den
        # relevantesten Einzelbeitrag nachzuerzählen (Tims Befund 10.08.).
        gruppen[label] = sorted(gruppen[label], key=lambda b: b.get("session_date") or "")
        zeilen = "\n".join(
            f"  - {b.get('sprecher') or '?'} am {_datum_de(b.get('session_date'))}: "
            f"{(b.get('text') or '').strip()[:300]}"
            for b in gruppen[label][:8])
        teile.append(f"{label} ({len(gruppen[label])} Beiträge):\n{zeilen}")
    prompt = prompts.render("partei_meinungen", frage=question.strip()[:300],
                            beitraege="\n".join(teile))
    extra = {"extra_body": {"reasoning": {"enabled": False}}} if "deepseek" in model else {}
    resp = llm.chat_complete(model=model, _feature="partei_meinungen", temperature=0,
                             max_tokens=2000, messages=[{"role": "user", "content": prompt}],
                             **extra)
    content = _strip_fences(resp.choices[0].message.content or "") if resp.choices else ""
    try:
        data = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(data, list):
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
            } for b in gruppen[e["partei"]][:8]],
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


def _debatten_block(debatten: list[dict] | None) -> str:
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
    return ("\nAUS DEN RATSDEBATTEN (thematisch geprüfte Wortbeiträge aus den\n"
            "Sitzungsprotokollen — Berichte, KEINE Beschlüsse). Ergänze die Antwort\n"
            "IMMER um einen kurzen Absatz Meinungsbild der Debatte (wer trug was vor,\n"
            "wo gab es Streit oder Zusagen) — auch wenn nur nach der Entscheidung\n"
            "gefragt ist: Die Debatte gehört zur Einordnung dazu. Klar markiert als\n"
            "„Laut Protokoll sagte/fragte …“ oder „In der Debatte betonte …“;\n"
            "NIE mit [id] zitieren:\n"
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
                     duenn: bool = False) -> tuple[list[dict], dict]:
    vtext = _verlauf_zeilen(verlauf)
    gespraech = (f"Dies ist eine Anschlussfrage in einem Gespräch. Bisher:\n{vtext}\n\n"
                 if vtext else "")
    prompt = prompts.render("qa_antwort", question=question.strip()[:300],
                            context=_build_context(candidates),
                            extra_regeln=EXTRA_REGELN.get(typ, "")
                            + (GROSS_REGEL if gross else "") + (DUENN_REGEL if duenn else ""),
                            presse=_steckbrief_block(steckbriefe) + _presse_block(presse)
                            + _haushalt_block(haushalt) + _debatten_block(debatten),
                            gespraech=gespraech)
    # reasoning-Schalter am TATSÄCHLICH genutzten Modell festmachen — vorher
    # hing er an der Modul-Konstante und lief bei model=-Overrides ins Leere.
    extra = {"extra_body": {"reasoning": {"enabled": False}}} if "deepseek" in model else {}
    return [{"role": "user", "content": prompt}], extra


def _answer_tokens(typ: str, gross: bool = False) -> int:
    # Seit dem Ratsgespräch dürfen breite Fragen strukturiert länger antworten
    # (Prompt regelt die Länge nach Frage; das Budget kappt nur den Ausreißer).
    # Große Themen (Task 32) bekommen Platz für die gegliederte Langfassung.
    if gross:
        return 2200
    return 1100 if typ == "verlauf" else 1000


def answer_question(question: str, candidates: list[dict], model: str = MODEL, typ: str = "thema",
                    presse: list[dict] | None = None, verlauf: list[dict] | None = None,
                    haushalt: list[dict] | None = None, debatten: list[dict] | None = None,
                    gross: bool = False, steckbriefe: list[dict] | None = None,
                    duenn: bool = False):
    """Synthesise an answer from retrieved candidates. Returns ``(answer, cited_ids)``."""
    messages, extra = _answer_messages(question, candidates, typ, model, presse, verlauf,
                                       haushalt, debatten, gross, steckbriefe, duenn)
    resp = llm.chat_complete(model=model, _feature="qa_antwort", temperature=0.2,
                             max_tokens=_answer_tokens(typ, gross), messages=messages, **extra)
    answer = (resp.choices[0].message.content or "").strip()
    return resolve_citations(answer, {c["id"] for c in candidates})


def answer_stream(question: str, candidates: list[dict], model: str = MODEL, typ: str = "thema",
                  presse: list[dict] | None = None, verlauf: list[dict] | None = None,
                  haushalt: list[dict] | None = None, debatten: list[dict] | None = None,
                  gross: bool = False, steckbriefe: list[dict] | None = None,
                  duenn: bool = False):
    """Stream the answer text deltas (same prompt/context as answer_question) so the
    UI can render the answer as it is written. Citation resolution is the caller's
    job once the full text is assembled (see resolve_citations)."""
    messages, extra = _answer_messages(question, candidates, typ, model, presse, verlauf,
                                       haushalt, debatten, gross, steckbriefe, duenn)
    yield from llm.chat_stream(model=model, _feature="qa_antwort", temperature=0.2,
                               max_tokens=_answer_tokens(typ, gross), messages=messages, **extra)


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
