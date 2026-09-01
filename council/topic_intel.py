"""Themen-Intelligenz (Design 26a / RL-U17): aus einem Themen-*Namen* eine
brauchbare Themen-*Beschreibung* machen — und vorher prüfen, ob der Rat mit der
Sache überhaupt zu tun hat.

Warum überhaupt: Die Beschreibung ist kein Deko-Text, sondern das, woran der
Themen-Wächter später jeden Beschluss misst (`match_topics_decisions`). Ein
Nutzer, der „Cäcilienbrücke" eintippt und das Feld leer lässt, bekam bisher
einen generischen Satz — und damit unscharfe Treffer. Hier entsteht die
Beschreibung stattdessen aus den Beschlüssen, die zum Namen wirklich existieren.

Ablauf (bewusst ein einziger LLM-Aufruf):

1. **Belege sammeln** — semantische Suche über die vorhandenen Embeddings,
   Keyword-Suche als Rückfallebene, wenn fastembed fehlt.
2. **Beurteilen + beschreiben** — die Treffer gehen als Kontext ans Modell, das
   in einem Rutsch sagt, ob das ein Ratsthema ist, und einen präzisen Satz
   formuliert. Ohne Belege wird gar nicht erst gefragt.

Alles ist ausfallsicher: Fehlt fastembed, fällt die Suche auf Volltext zurück;
antwortet das Modell nicht oder unbrauchbar, kommt ein deterministischer Satz.
Ein Themen-Anlegen darf nie daran scheitern, dass ein LLM gerade hakt.
"""
from __future__ import annotations

import calendar
import json
import logging
import os
import re
from datetime import date

from kern import llm, prompts

logger = logging.getLogger("council.topic_intel")

MODEL = os.environ.get("TOPIC_INTEL_MODEL", "deepseek/deepseek-v4-pro")

# Ab wie vielen belastbaren Treffern gilt eine Sache als „im Rat behandelt".
# Zwei statt einem: Ein einzelner Zufallstreffer (ein Name fällt in einem
# Nebensatz) macht noch kein Thema, das sich zu abonnieren lohnt.
MIN_MATCHES = 2
# Kosinus-Schwelle der BELEG-Suche (nicht der Trefferdefinition, s. u.).
# Darunter ist die Ähnlichkeit Rauschen — „mein Hund" landet sonst über
# irgendeinem Tierheim-Beschluss.
MIN_SCORE = 0.42
_MAX_CONTEXT = 12
_MAX_DESC = 240


# --- DIE Definition von „Beschlüsse zu diesem Thema" ------------------------
#
# Sie steht ab dem 16.08.2026 genau hier, weil sie vorher an drei Stellen
# unabhängig voneinander getroffen wurde und drei verschiedene Zahlen ergab
# (Tims Befund, Build 12: Karte „40+", Blatt „12 Beschlüsse", Trefferliste
# „25" — dasselbe Thema „Fliegerhorststraße"):
#
#   Karte        gespeicherte Treffer  (Cross-Encoder ≥ −1,0, Deckel 40)
#   Blatt        eigene Suche          (Bi-Encoder-Cosinus ≥ 0,42, Deckel 12)
#   Trefferliste gespeicherte Treffer, aber durch den Voreinstellungs-Filter
#                „nur Beschlüsse" um alle Berichte gekürzt
#
# Ein Beschluss gehört zu einem Thema, wenn der Cross-Encoder ihn gegen
# „Name. Beschreibung" mit mindestens ``SCHWELLE`` bewertet. Mehr als
# ``DECKEL`` Treffer werden nicht gespeichert und nicht gezählt; dass
# abgeschnitten wurde, ist ein eigenes Signal (``gedeckelt``) und wird überall
# als „40+" ausgewiesen — nie als glatte Endzahl.
#
#: Relevanzschwelle auf den Cross-Encoder-Logits. Am Bestand kalibriert
#: (15.08.2026, 32 echte Themen): −1,0 ist genau der Bruch zwischen dem
#: letzten offensichtlich richtigen und dem ersten offensichtlich falschen
#: Treffer des Problem-Themas „Wohnheim Tegelbusch" — die Bebauungsplan-Kette
#: „Am Tegelbusch" reicht bis −0,90 hinunter, der erste Fremdkörper
#: („Unterbringung von Asylbewerberinnen und Asylbewerbern") liegt bei −1,03.
#: Strenger (−0,5) verlöre die Veränderungssperre „Am Tegelbusch" (−0,70),
#: lockerer (−1,25) holte die Asyl-Berichte zurück. Der Wert liegt damit
#: zwischen den beiden schon vorhandenen Toren der KI-Frage: −1,5 für
#: Zusatzkanäle, −0,5 für Zusagen.
SCHWELLE = -1.0
#: So viele Treffer je Thema werden höchstens gespeichert bzw. gezählt.
DECKEL = 40
#: So viele Kandidaten je Quelle (Vektor und BM25) gehen in die Bewertung.
POOL = 45
#: Ab wann ein Treffer „aktuell" heißt — die Zahl hinter „n in 6 Monaten" auf
#: der Themen-Karte UND die Grenze, ab der eine N3-Mail verschickt wird.
AKTUELL_MONATE = 6


def vor_sechs_monaten(heute: date | None = None) -> date:
    """Der Stichtag hinter „n in 6 Monaten" — und hinter der Ergebnis-Mail.

    Ursprünglich waren es 30 Tage — dabei stand bei fast jedem Thema eine 0,
    auch bei sehr lebendigen: Die Gremien tagen monatlich, im Sommer gar nicht,
    und Protokolle kommen mit ein bis zwei Monaten Verzug. „0 in 30 Tagen" las
    sich damit wie ein totes Thema, obwohl der Rat gerade erst entschieden
    hatte (Tims Befund 28.08.2026 an „Schulbegleitung": „40+ gesamt · 0 in 30
    Tagen"). Ein halbes Jahr umfasst mehrere Sitzungsrunden und trennt
    dadurch wirklich Laufendes von Ruhendem.

    Seit dem 30.08.2026 hängt auch der Mail-Versand daran (Tim: „über die Mail
    würde ich immer nur über aktuelle Beschlüsse informieren"), deshalb steht
    die Rechnung hier statt im Web-Router: Karte und Meldung sollen dieselbe
    Grenze meinen, nicht zwei zufällig gleich große.

    Kalendarisch gerechnet statt „minus 183 Tage": Der Wert steht als „6
    Monate" auf der Karte, also soll er auch ein halbes Jahr meinen. Am 31.
    August wird daraus der 28./29. Februar — der letzte Tag, den es im
    Zielmonat gibt.
    """
    heute = heute or date.today()
    monat = heute.month - AKTUELL_MONATE
    year = heute.year + (monat - 1) // 12
    monat = (monat - 1) % 12 + 1
    return date(year, monat, min(heute.day, calendar.monthrange(year, monat)[1]))


def treffer(store, name: str, text: str, *, deckel: int = DECKEL,
            schwelle: float = SCHWELLE) -> tuple[list[tuple[int, float]], bool, int]:
    """Relevante Beschlüsse zu einem Thema → ``(treffer, gedeckelt, kandidaten)``.

    Die eine Quelle für alle drei Anzeigen: Der Cron-Lauf
    (``scripts/match_topics_decisions.py``) schreibt damit, was gespeichert
    wird; das Bearbeiten-Blatt zeigt damit vorab, was ein geänderter Text
    fände. Wer hier etwas ändert, ändert es an allen Stellen gleichzeitig —
    genau das ist der Zweck.

    Der Cross-Encoder ist nicht Kür, sondern der ganze Punkt: Ohne ihn fällt
    ``hybrid_search`` still auf die Vektor-Reihenfolge zurück und liefert
    Cosinus-Werte (0,4…0,9) — die lägen alle über der Logit-Schwelle, und der
    Aufrufer bekäme genau das Rauschen, das die Schwelle verhindern soll.
    Deshalb prüfen wir, ob der Reranker wirklich lief, und werfen sonst:
    Beim Cron heißt das „die Treffer von letzter Woche bleiben stehen", im
    Web „lieber keine Zahl als eine falsche".
    """
    from council import embeddings

    zeiten: dict = {}
    # deckel + 1 anfragen: Nur so lässt sich „genau 40 gefunden" von „bei 40
    # abgeschnitten" unterscheiden — die Zahl der Zeilen sieht sonst gleich aus.
    roh = embeddings.hybrid_search(store, name, text, top_k=deckel + 1,
                                   pool=POOL, timings=zeiten)
    if "rerank_ms" not in zeiten:
        raise RuntimeError(
            "Cross-Encoder nicht verfügbar (COUNCIL_RERANK_MODEL) — ohne ihn "
            "wäre jede Relevanzschwelle wirkungslos.")
    ueber = [(int(did), float(s)) for did, s in roh if s >= schwelle]
    return ueber[:deckel], len(ueber) > deckel, zeiten.get("paare", 0)


def zaehle_treffer(store, name: str, text: str) -> tuple[int, bool] | None:
    """``(count, gedeckelt)`` nach derselben Definition — oder ``None``.

    Die ausfallsichere Fassung für den Web-Request: ``None`` heißt „lässt sich
    hier gerade nicht nach der einen Definition bestimmen" (kein fastembed,
    kein Reranker, noch kein Embedding-Bestand). Der Aufrufer darf dann keine
    Zahl behaupten, die er mit einem anderen Maß gemessen hat — genau daraus
    entstanden die widersprüchlichen Zahlen.

    Ohne Embedding-Bestand wird gar nicht erst gesucht: Dann hat der Matching-
    Lauf ohnehin nie etwas gespeichert, und der Aufruf würde in Tests und
    frischen Umgebungen nur das ~1 GB große Reranker-Modell nachladen.
    """
    try:
        if not store.embeddings_version()[0]:
            return None
        hits, gedeckelt, _ = treffer(store, name, text)
    except Exception:  # noqa: BLE001 — fastembed fehlt, Modell hakt, Store leer
        return None
    return len(hits), gedeckelt


def find_matches(store, name: str, limit: int = _MAX_CONTEXT) -> list[dict]:
    """BELEGE für die Beschreibung — nicht die Trefferzahl (die macht ``treffer``).

    Diese Liste geht als Kontext in den Prompt und liefert die zwei, drei
    Beispieltitel, die im Blatt unter der Zahl stehen. Sie ist deshalb bewusst
    kurz und billig (Bi-Encoder statt Cross-Encoder) — und darf gerade **nicht**
    als Zähler benutzt werden: Ihre 12 waren bis zum 16.08.2026 die „12
    Beschlüsse" im Bearbeiten-Blatt, also schlicht die Länge des Prompt-Kontexts.

    Semantisch, wenn fastembed da ist (fängt „Radweg" ↔ „Veloroute"), sonst
    Volltext. Die Rückfallebene ist wichtig: Das Web-Backend läuft auch ohne
    das ONNX-Modell, und dann soll das Anlegen trotzdem funktionieren.
    """
    query = (name or "").strip()
    if len(query) < 3:
        return []
    ids: list[int] = []
    try:
        from council import embeddings as emb

        ids = [i for i, _ in emb.search(store, query, top_k=limit, min_score=MIN_SCORE)]
    except Exception:  # noqa: BLE001 — fastembed fehlt/Modell lädt nicht
        ids = []
    if not ids:
        try:
            ids = [i for i, *_ in store.search_decisions_fts(query, limit=limit)]
        except Exception:  # noqa: BLE001
            return []
    if not ids:
        return []
    rows = store.get_decisions_by_ids(ids)  # behält die Reihenfolge
    return rows[:limit]


# Wörter, die in einem Themen-*Namen* nichts verloren haben: Anrede und
# Befehlsformen. Ein Thema ist eine Sache („Cäcilienbrücke"), kein Satz an mich.
_INSTRUCTION_WORDS = {
    "ignoriere", "ignorier", "vergiss", "vergesse", "vergessen", "beachte",
    "antworte", "schreibe", "zeige", "zeig", "gib", "gebe", "liste", "nenne",
    "erkläre", "sage", "sag", "mach", "mache", "tue", "musst", "sollst",
    "darfst", "bist", "system", "prompt", "anweisung", "anweisungen",
    "instruction", "instructions", "ignore", "forget", "you", "your",
}
_MAX_NAME_WORDS = 8


def looks_like_instruction(name: str) -> bool:
    """Sieht der „Name" nach einem Satz oder einer Anweisung aus?

    Rein strukturell und ohne LLM — deshalb auch dann verlässlich, wenn das
    Modell gerade hakt. Zwei Signale genügen: Länge (echte Themen sind kurze
    Substantiv-Fügungen; „Ausbau der Grundschule Auf der Wunderburg" sind sechs
    Wörter) und Anrede-/Befehlswörter.
    """
    text = (name or "").strip()
    if not text:
        return False
    words = re.findall(r"[\wÄÖÜäöüß-]+", text.lower())
    if len(words) > _MAX_NAME_WORDS:
        return True
    return bool(_INSTRUCTION_WORDS & set(words))


def _context(matches: list[dict]) -> str:
    lines = []
    for m in matches:
        meta = " · ".join(p for p in (m.get("committee"), m.get("session_date")) if p)
        body = (m.get("summary") or m.get("official_text") or "").strip()[:220]
        lines.append(f"- {(m.get('title') or '').strip()} ({meta}): {body}")
    return "\n".join(lines)


def _fallback_description(name: str, matches: list[dict]) -> str:
    """Ohne (brauchbare) LLM-Antwort: ein Satz aus dem, was wir sicher wissen.
    Nennt das Themenfeld, wenn die Treffer sich einig sind — das schärft den
    Wächter immer noch mehr als reines „alles rund um X"."""
    from council.topics import POLICY_FIELDS

    fields = [m.get("policy_field") for m in matches if m.get("policy_field")]
    label = ""
    if fields:
        top = max(set(fields), key=fields.count)
        if fields.count(top) >= max(2, len(fields) // 3):
            label = POLICY_FIELDS.get(top, ("",))[0]
    zusatz = f" im Themenfeld {label}" if label else ""
    return (f"Beschlüsse, Planungen und Maßnahmen des Oldenburger Stadtrats "
            f"rund um {name.strip()}{zusatz}.")


def _parse(raw: str) -> dict | None:
    """JSON aus der Modellantwort schälen (auch wenn Text drumherum steht)."""
    if not raw:
        return None
    txt = raw.strip()
    start, end = txt.find("{"), txt.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        obj = json.loads(txt[start:end + 1])
    except ValueError:
        return None
    return obj if isinstance(obj, dict) else None


def _call_model(name: str, matches: list[dict]) -> dict | None:
    """Der eine LLM-Aufruf — als eigene Funktion, damit Tests ihn ersetzen können
    (die Suite darf nie ein echtes Modell rufen). ``None`` bei jedem Fehler:
    Ein hakendes Modell darf ein Thema weder anlegen noch verhindern.

    Beide Fehlerwege loggen, weil ``None`` hier stumm in
    ``_fallback_description`` mündet: Die Nutzer:in bekommt dann die Schablone
    „Beschlüsse, Planungen und Maßnahmen … rund um X" statt eines echten Satzes,
    und von außen war nicht zu sehen, wie oft das passiert — man konnte es nur
    hinterher an den gespeicherten Beschreibungen ablesen (Tims Frage
    28.08.2026: „wird immer dasselbe Template verwendet?"). Der Themen-Name
    steht mit im Satz, damit ein wiederkehrender Ausreißer auffällt.
    """
    try:
        prompt = prompts.render("topic_auto_beschreibung", name=name[:120], context=_context(matches))
        extra = {"extra_body": {"reasoning": {"enabled": False}}} if "deepseek" in MODEL else {}
        resp = llm.chat_complete(
            model=MODEL, _feature="topic_auto_description", temperature=0.2, max_tokens=300,
            messages=[{"role": "user", "content": prompt}], **extra,
        )
        obj = _parse(resp.choices[0].message.content or "")
        if obj is None:
            logger.warning("Themen-Beschreibung für %r: Modellantwort nicht lesbar — Schablone greift",
                           name[:80])
        return obj
    except Exception:  # noqa: BLE001 — LLM aus/Timeout
        logger.warning("Themen-Beschreibung für %r: Modell nicht erreichbar — Schablone greift",
                       name[:80], exc_info=True)
        return None


VERDICTS = ("belegt", "plausibel", "ungeeignet")


def analyse(store, name: str, description: str = "") -> dict:
    """Ein Themen-Name → Einordnung + Beschreibung.

    Drei Zustände, weil zwei zu grob sind. „Grundschule Krusenbusch" ist eine
    echte Oldenburger Schule — der Rat hat über sie nur noch nichts beschlossen.
    Das ist etwas völlig anderes als „Vergiss deine Anweisungen": das eine darf
    man anlegen (und wird benachrichtigt, sobald es so weit ist), das andere nicht.

      ``verdict``          — "belegt" | "plausibel" | "ungeeignet"
      ``is_council_topic`` — alles außer "ungeeignet" (Altlast, Frontend nutzt verdict)
      ``description``      — ein Satz, direkt als Themen-Beschreibung nutzbar
      ``matches``          — Beschlüsse zu diesem Thema nach der EINEN Definition
                             (s. ``treffer``); 0, wenn nur plausibel
      ``matches_capped``   — die Zahl ist der Deckel, nicht das Ergebnis → „40+"
      ``examples``         — bis zu 3 Titel als sichtbarer Beleg
      ``reason``           — kurze Begründung, wenn es kein Ratsthema ist

    ``description`` ist der Text, der beim Speichern im Thema stünde. Er geht
    mit in die Zählung, weil der Matching-Lauf genauso zählt („Name.
    Beschreibung") — nur so zeigt das Bearbeiten-Blatt vorab wirklich das, was
    danach auf der Karte steht, statt einer zweiten Wahrheit.

    Gefragt wird immer — auch ohne Suchtreffer. Ohne die Frage könnten wir
    „plausibel" gar nicht von „ungeeignet" unterscheiden, und genau diese
    Unterscheidung ist der Punkt.
    """
    clean = (name or "").strip()
    belege = find_matches(store, clean)
    examples = [(m.get("title") or "").strip() for m in belege[:3] if m.get("title")]

    # Freie Vorprüfung: Ein Themen-Name ist eine Sache, kein Satz. Was wie eine
    # Anweisung aussieht, geht gar nicht erst ans Modell — das spart den Aufruf
    # und nimmt Prompt-Injection den Weg über den Umweg „Themen-Beschreibung",
    # die später in den Wächter-Prompt wandert.
    if looks_like_instruction(clean):
        return {
            "verdict": "ungeeignet", "is_council_topic": False, "description": "",
            "matches": 0, "matches_capped": False, "examples": [],
            "reason": ("Das liest sich wie ein ganzer Satz. Ein Thema ist eine Sache — "
                       "etwa „Cäcilienbrücke\" oder „Grundschule Krusenbusch\"."),
        }

    # Die eine Definition, angewandt auf den Text, der gespeichert würde.
    # Fällt sie aus (kein Reranker, kein Embedding-Bestand), zählen ersatzweise
    # die Belege — dann ist die Zahl grob, aber wenigstens nicht aus einer
    # zweiten, dauerhaft danebenliegenden Quelle.
    gezaehlt = zaehle_treffer(store, clean, f"{clean}. {(description or '').strip()}".strip())
    count, gedeckelt = gezaehlt if gezaehlt is not None else (len(belege), False)

    obj = _call_model(clean, belege)

    if not obj:
        # Modell weg: Wir dürfen weder fälschlich anlegen noch grundlos ablehnen.
        # Belege entscheiden — mit genug Treffern gilt es als belegt, sonst als
        # plausibel. „Ungeeignet" behaupten wir ohne Urteil nie.
        belegt = count >= MIN_MATCHES
        return {"verdict": "belegt" if belegt else "plausibel", "is_council_topic": True,
                "description": _fallback_description(clean, belege),
                "matches": count if belegt else 0,
                "matches_capped": gedeckelt if belegt else False,
                "examples": examples if belegt else [], "reason": ""}

    desc = str(obj.get("beschreibung") or "").strip()[:_MAX_DESC]
    verdict = str(obj.get("einordnung") or "").strip().lower()
    if verdict not in VERDICTS:
        verdict = "belegt" if count >= MIN_MATCHES else "plausibel"
    # Das Modell darf nur nach unten korrigieren: Es sieht die Beschlüsse und
    # erkennt, dass „Grundschule Krusenbusch" von der Wunderburg-Schule handelt —
    # eine Trefferzahl allein kann das nicht.
    if verdict == "belegt" and count < MIN_MATCHES:
        verdict = "plausibel"
    belegt = verdict == "belegt"
    return {
        "verdict": verdict,
        "is_council_topic": verdict != "ungeeignet",
        "description": "" if verdict == "ungeeignet" else (desc or _fallback_description(clean, belege)),
        # Nur belegte Treffer zählen: Sonst stünde „12 Beschlüsse passen dazu"
        # unter einem Thema, zu dem das Modell gerade das Gegenteil gesagt hat.
        "matches": count if belegt else 0,
        "matches_capped": gedeckelt if belegt else False,
        "examples": examples if belegt else [],
        "reason": str(obj.get("begruendung") or "").strip()[:200] if verdict == "ungeeignet" else "",
    }


def check_vagueness(name: str, description: str) -> dict:
    """Die bestehende Vagheits-Prüfung — bis 26a lag sie brach: Der Prompt war
    seit jeher als Vorlage hinterlegt, aber es gab keinen einzigen Aufruf.

    Rückgabe ``{vague, hint, suggestion}``. Bei jedem Fehler „nicht vage": Eine
    kaputte Prüfung darf niemanden am Anlegen hindern.
    """
    text = (description or "").strip()
    if not text:
        return {"vague": False, "hint": "", "suggestion": ""}
    try:
        system = prompts.get("vagueness_check_system")
        extra = {"extra_body": {"reasoning": {"enabled": False}}} if "deepseek" in MODEL else {}
        resp = llm.chat_complete(
            model=MODEL, _feature="vagueness_check", temperature=0, max_tokens=300,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": f"Thema: {(name or '').strip()[:120]}\nBeschreibung: {text[:600]}"},
            ], **extra,
        )
        obj = _parse(resp.choices[0].message.content or "") or {}
    except Exception:  # noqa: BLE001
        return {"vague": False, "hint": "", "suggestion": ""}
    return {
        "vague": bool(obj.get("vague")),
        "hint": str(obj.get("hint") or "").strip()[:300],
        "suggestion": str(obj.get("suggestion") or "").strip()[:_MAX_DESC],
    }


_GENERIC = {
    # Gattungsbegriffe, die als Themen-Name nichts eingrenzen. Sie kommen aus
    # der Entitäten-Erkennung durch und würden als Vorschlag Beschlüsse quer
    # durch die Stadt einsammeln.
    "bericht", "berichte", "antrag", "anträge", "beschluss", "beschlüsse",
    "haushalt", "stadt", "oldenburg", "rat", "verwaltung", "ausschuss",
    "sitzung", "vorlage", "projekt", "maßnahme", "planung", "konzept",
    "innenstadt", "klima", "wohnen", "schule", "schulen", "verkehr", "umwelt",
    "kultur", "sport", "soziales", "digitalisierung", "sicherheit",
}


def looks_generic(name: str) -> bool:
    """Billiger Vorfilter für Vorschläge: ein einzelnes Gattungswort.

    Bewusst deterministisch — er läuft über jeden Vorschlagskandidaten und darf
    nichts kosten. Die teure Vagheits-Prüfung urteilt danach und nur einmal je
    Kandidat (Ergebnis wird gecacht).
    """
    n = re.sub(r"[^\wäöüß\s-]", "", (name or "").strip().lower())
    if not n:
        return True
    words = [w for w in n.split() if w]
    return len(words) == 1 and words[0] in _GENERIC
