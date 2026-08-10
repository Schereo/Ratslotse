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
QUERY_TYPES = ("thema", "verlauf", "partei", "geld")
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
        if typ not in QUERY_TYPES:
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
        "Einordnung, wofür das Geld ist."
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
        meta = " · ".join(p for p in (c.get("committee"), c.get("session_date"), c.get("outcome")) if p)
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
            reason = (c.get("impact_reason") or "").strip()
            suffix += f" — Tragweite: hoch{f' ({reason})' if reason else ''}"
        elif impact is not None and impact <= 15:
            suffix += " — Tragweite: gering (Formalie)"
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
                "text": (b.get("text") or "").strip()[:300],
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
            kopf += f" am {d['session_date']}"
        if d.get("committee"):
            kopf += f" im Gremium „{d['committee']}“"
        if d.get("top"):
            kopf += f" zu „{d['top']}“"
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
    "ausführlich (bis ~500 Wörter) und strukturiere die Antwort: Beginne mit 1-2 "
    "Sätzen Überblick, gliedere danach mit 2-4 Zwischenüberschriften (Zeile, die "
    "mit „## “ beginnt, z. B. „## Finanzierung“) und nutze, wo es passt, kurze "
    "Spiegelstrich-Listen („- “). Die Fußnoten-Regeln gelten unverändert."
)


def _answer_messages(question: str, candidates: list[dict], typ: str = "thema",
                     model: str = MODEL, presse: list[dict] | None = None,
                     verlauf: list[dict] | None = None,
                     haushalt: list[dict] | None = None,
                     debatten: list[dict] | None = None,
                     gross: bool = False) -> tuple[list[dict], dict]:
    vtext = _verlauf_zeilen(verlauf)
    gespraech = (f"Dies ist eine Anschlussfrage in einem Gespräch. Bisher:\n{vtext}\n\n"
                 if vtext else "")
    prompt = prompts.render("qa_antwort", question=question.strip()[:300],
                            context=_build_context(candidates),
                            extra_regeln=EXTRA_REGELN.get(typ, "") + (GROSS_REGEL if gross else ""),
                            presse=_presse_block(presse) + _haushalt_block(haushalt)
                            + _debatten_block(debatten),
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
                    gross: bool = False):
    """Synthesise an answer from retrieved candidates. Returns ``(answer, cited_ids)``."""
    messages, extra = _answer_messages(question, candidates, typ, model, presse, verlauf,
                                       haushalt, debatten, gross)
    resp = llm.chat_complete(model=model, _feature="qa_antwort", temperature=0.2,
                             max_tokens=_answer_tokens(typ, gross), messages=messages, **extra)
    answer = (resp.choices[0].message.content or "").strip()
    return resolve_citations(answer, {c["id"] for c in candidates})


def answer_stream(question: str, candidates: list[dict], model: str = MODEL, typ: str = "thema",
                  presse: list[dict] | None = None, verlauf: list[dict] | None = None,
                  haushalt: list[dict] | None = None, debatten: list[dict] | None = None,
                  gross: bool = False):
    """Stream the answer text deltas (same prompt/context as answer_question) so the
    UI can render the answer as it is written. Citation resolution is the caller's
    job once the full text is assembled (see resolve_citations)."""
    messages, extra = _answer_messages(question, candidates, typ, model, presse, verlauf,
                                       haushalt, debatten, gross)
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
