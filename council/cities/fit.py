"""Der Lauf des Annotators ``fit``: Hat Oldenburg das schon, und lohnt es sich?

**Warum ein eigenes Modul.** ``council/cities/annotate.py`` fragt Batches von
Vorlagen nach einem Etikett — sechs auf einmal, ohne Kontext, ohne Rückfrage
an eine zweite Datenbank. ``fit`` ist eine andere Sache: Jede Vorlage bekommt
ihre eigenen Belege aus Oldenburg, geht allein ins Modell, und was
zurückkommt, wird gegen die vorgelegten Belege geprüft. Das in den vorhandenen
Lauf zu falten hieße, ihn an fünf Stellen zu verzweigen.

**Ohne Beleg keine Frage, ohne Beleg-Kennung kein Urteil.** Findet
``evidence_for`` nichts aus Oldenburg, wird das Modell gar nicht erst gefragt —
die Antwort wäre eine Behauptung ins Leere. Und nennt es eine Kennung, die
ihm nicht vorlag, fliegt der ganze Eintrag raus. Beides wird gezählt, damit
ein Rückgang auffällt.

**Geschrieben wird nur im Hauptthread.** Dieselbe Lehre wie in
``annotate.py``: Eine SQLite-Verbindung gehört dem Thread, der sie geöffnet
hat, und ein Schreibversuch von anderswo wirft. Die Arbeiter sammeln, der
Hauptthread schreibt.
"""
from __future__ import annotations

import hashlib
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING

from pydantic import ValidationError

from council.cities.annotate import parse_json
from council.cities.annotators import USABLE, Annotator
from council.cities.evidence import (
    OLDENBURG_STECKBRIEF, Evidence, evidence_for)
from council.cities.store import CitiesStore
from kern import llm, prompts

if TYPE_CHECKING:
    from council.store import CouncilStore

logger = logging.getLogger("council.cities.fit")

WORKERS = 4

#: Belege, die eine Aussage über Oldenburg tragen. Der Themenfeld-Rückblick
#: gehört nicht dazu: Er sagt, was die Stadt gerade beschäftigt, nicht ob sie
#: dieses eine Instrument hat. Ein Papier, für das es nur ihn gibt, wird
#: übersprungen.
TRAGENDE_ARTEN = ("neighbor", "chunk", "fts", "decision")


def candidates_for(main: CitiesStore, body_id: str | None = None) -> list[dict]:
    """Die fremden Vorlagen, für die die Frage überhaupt Sinn ergibt.

    Nur was die Einordnung als übertragbar führt. Für einen Münsteraner
    Bebauungsplan ist „fehlt Oldenburg das?" keine sinnvolle Frage — er fehlt
    Oldenburg, und das ist richtig so.
    """
    einordnung = main.annotations_for("classify", "2")
    return [p for p in main.papers(body_id=body_id)
            if p["body_id"] != "oldenburg"
            and (einordnung.get(p["id"]) or {}).get("transfer") in USABLE]


def source_hash(paper: dict, classification: dict, belege: list[Evidence],
                ann: Annotator) -> str:
    """Woraus das Urteil entstanden ist — Vorlage UND Belege.

    Der Unterschied zu ``annotate.source_hash``: Dort hängt das Etikett allein
    an der fremden Vorlage. Hier hängt das Urteil auch daran, was Oldenburg
    hat — und das wächst. Kommt ein Oldenburger Nachbar dazu oder ändert sich
    der Themenfeld-Rückblick, ist das Urteil neu zu fällen, auch wenn die
    fremde Vorlage unverändert ist. Genau das merkt ``annotations_missing``.
    """
    teile = [
        paper.get("name") or "", paper.get("date") or "",
        classification.get("instrument") or "", classification.get("field") or "",
        "|".join(sorted(e.id for e in belege)),
        # Der Rückblick ändert sich wöchentlich; sein Text gehört mit hinein,
        # sonst bliebe ein Urteil stehen, dessen Kontext ein anderer ist.
        "|".join(e.text[:120] for e in belege if e.kind == "recap"),
        ann.version, prompts.get(ann.prompt_system)[:200],
    ]
    return hashlib.sha256("␟".join(teile).encode("utf-8")).hexdigest()


def paper_text(paper: dict, classification: dict, text: str | None,
               ann: Annotator) -> str:
    """Die fremde Vorlage, so wie sie im Prompt steht."""
    zeilen = [
        f"Stadt: {paper.get('body_id')}",
        f"Art: {paper.get('paper_type_raw') or paper.get('kind')}",
        f"Datum: {paper.get('date') or 'unbekannt'}",
        f"Titel: {paper.get('name')}",
    ]
    for schluessel, label in (("instrument", "Instrument"), ("field", "Themenfeld"),
                              ("competence", "Zuständigkeit"),
                              ("summary", "Zusammenfassung")):
        wert = classification.get(schluessel)
        if wert:
            zeilen.append(f"{label}: {wert}")
    if text:
        zeilen.append("Text: " + " ".join(text.split())[:ann.input_chars])
    return "\n".join(zeilen)


def evidence_text(belege: list[Evidence]) -> str:
    return "\n".join(e.as_prompt_line() for e in belege)


def pruefe(nutzlast, erlaubte: set[str], tragende: set[str] | None = None) -> str | None:
    """``None``, wenn das Urteil steht — sonst der Grund, es zu verwerfen.

    Drei Prüfungen, die pydantic nicht leisten kann, weil sie die Belege
    kennen müssen:

    - **Erfundene Kennung.** Das Modell soll aus einer Liste zitieren. Nennt
      es etwas anderes, ist die Grundlage des Urteils unklar — und ein Urteil
      ohne klare Grundlage ist genau das, was hier nicht gespeichert werden
      soll.
    - **Behauptung ohne Beleg.** „Oldenburg hat das" ist eine Aussage über
      Oldenburg; sie braucht mindestens eine Kennung. Bei ``missing`` ist die
      leere Liste dagegen die Aussage.
    - **Behauptung nur auf den Rückblick.** Der Themenfeld-Rückblick sagt, was
      die Stadt gerade beschäftigt — nicht, ob sie dieses eine Instrument hat.
      Er darf ein Urteil begleiten, nicht tragen. Beim Bauen des Golden Sets
      war das der Fall, in dem ich selbst versucht war, aus „Oldenburg hat
      einen Brandbrief gegen Kürzungen geschrieben" ein „vorhanden" zu machen.
    """
    erfunden = [k for k in nutzlast.evidence if k not in erlaubte]
    if erfunden:
        return "hallucinated_evidence:" + ",".join(erfunden[:3])
    if not nutzlast.braucht_beleg:
        return None
    if not nutzlast.evidence:
        return "claim_without_evidence"
    if tragende is not None and not (set(nutzlast.evidence) & tragende):
        return "claim_only_on_recap"
    return None


def run(main: CitiesStore, rats: CouncilStore, ann: Annotator,
        model: str, body_id: str | None = None, limit: int | None = None,
        workers: int = WORKERS) -> dict:
    """Jede übertragbare fremde Vorlage einmal gegen Oldenburg halten."""
    einordnung = main.annotations_for("classify", "2")
    kandidaten = candidates_for(main, body_id)
    if not kandidaten:
        return _leer()

    # Belege zuerst, für alle: Sie gehen in den source_hash ein, und ohne den
    # wüssten wir nicht, was offen ist.
    logger.info("fit: Belege für %s Vorlagen sammeln", len(kandidaten))
    # Die Chunk-Matrix EINMAL: 34.000 Vektoren je Vorlage neu zu lesen wäre
    # der teuerste Teil des ganzen Laufs, und sie ändert sich dabei nicht.
    matrix = main.chunk_matrix(model, "oldenburg")
    logger.info("fit: %s Oldenburger Textabschnitte im Speicher", len(matrix[0]))
    belege_je: dict[str, list[Evidence]] = {}
    hashes: dict[str, str] = {}
    for n, p in enumerate(kandidaten, 1):
        klasse = einordnung.get(p["id"]) or {}
        belege = evidence_for(main, rats, p, klasse, model, chunk_matrix=matrix)
        belege_je[p["id"]] = belege
        hashes[p["id"]] = source_hash(p, klasse, belege, ann)
        if n % 200 == 0:
            logger.info("  Belege %s/%s", n, len(kandidaten))

    offen = main.annotations_missing("paper", ann.key, ann.version, body_id=body_id,
                                     source_hashes=hashes)
    offen = [p for p in offen if p["id"] in belege_je]
    if limit:
        offen = offen[:limit]
    if not offen:
        return _leer()

    system = prompts.render(ann.prompt_system, steckbrief=OLDENBURG_STECKBRIEF)
    sperre = threading.Lock()
    stand = {"annotated": 0, "errors": 0, "skipped_no_evidence": 0,
             "hallucinated_evidence": 0, "claim_without_evidence": 0,
             "claim_only_on_recap": 0,
             "cost_usd": 0.0, "prompt_tokens": 0, "completion_tokens": 0}
    t0 = time.time()

    def eine(p: dict) -> tuple[str, dict, float] | None:
        """Ein Papier ans Modell — **ohne** die Datenbank anzufassen."""
        belege = belege_je.get(p["id"]) or []
        if not any(e.kind in TRAGENDE_ARTEN for e in belege):
            with sperre:
                stand["skipped_no_evidence"] += 1
            return None
        klasse = einordnung.get(p["id"]) or {}
        try:
            extra = {"provider": {}} if ann.routing_free else {}
            antwort = llm.chat_complete(
                model=ann.model, response_format={"type": "json_object"},
                messages=[{"role": "system", "content": system},
                          {"role": "user", "content": prompts.render(
                              ann.prompt_user,
                              paper=paper_text(p, klasse, main.text_for_paper(p["id"]), ann),
                              evidence=evidence_text(belege))}],
                max_tokens=ann.max_tokens, temperature=ann.temperature,
                extra_body=extra, _feature=ann.feature)
            daten = parse_json(antwort.choices[0].message.content or "")
        except Exception as e:  # noqa: BLE001 — eine Vorlage, nicht der Lauf
            with sperre:
                stand["errors"] += 1
            logger.info("fit gescheitert (%s): %s: %s", p["id"], type(e).__name__,
                        str(e)[:120])
            return None

        verbrauch = getattr(antwort, "usage", None)
        kosten = float(getattr(verbrauch, "cost", 0) or 0) if verbrauch else 0.0
        with sperre:
            if verbrauch:
                stand["prompt_tokens"] += verbrauch.prompt_tokens or 0
                stand["completion_tokens"] += verbrauch.completion_tokens or 0
                stand["cost_usd"] += kosten
        try:
            nutzlast = ann.payload.model_validate(daten)
        except ValidationError as e:
            with sperre:
                stand["errors"] += 1
            logger.info("Antwort passt nicht zur Form (%s): %s", p["id"], str(e)[:120])
            return None

        grund = pruefe(nutzlast, {e.id for e in belege},
                       {e.id for e in belege if e.kind in TRAGENDE_ARTEN})
        if grund:
            with sperre:
                schluessel = grund.split(":")[0]
                stand[schluessel] = stand.get(schluessel, 0) + 1
            logger.info("Urteil verworfen (%s): %s", p["id"], grund)
            return None
        return p["id"], nutzlast.model_dump(), kosten

    def schreiben(ergebnisse: list[tuple[str, dict, float]]) -> None:
        """Der EINE Schreiber — im Hauptthread, in einer Transaktion."""
        if not ergebnisse:
            return
        with main.transaction():
            for kennung, nutzlast, kosten in ergebnisse:
                main.put_annotation("paper", kennung, ann.key, ann.version, nutzlast,
                                    hashes.get(kennung, ""), model=ann.model,
                                    cost_usd=kosten)
        stand["annotated"] += len(ergebnisse)

    logger.info("fit/%s: %s Vorlagen zu beurteilen", ann.version, len(offen))
    puffer: list[tuple[str, dict, float]] = []
    with ThreadPoolExecutor(workers) as pool:
        for n, ergebnis in enumerate(pool.map(eine, offen), 1):
            if ergebnis:
                puffer.append(ergebnis)
            if len(puffer) >= 25:
                schreiben(puffer)
                puffer = []
            if n % 50 == 0:
                logger.info("  %s/%s · %.0fs · $%.4f", n, len(offen),
                            time.time() - t0, stand["cost_usd"])
    schreiben(puffer)

    stand["seconds"] = round(time.time() - t0)
    logger.info("fit fertig: %s Urteile, %s ohne Belege, %s verworfen, $%.4f, %ss",
                stand["annotated"], stand["skipped_no_evidence"],
                stand["hallucinated_evidence"] + stand["claim_without_evidence"],
                stand["cost_usd"], stand["seconds"])
    return stand


def _leer() -> dict:
    return {"annotated": 0, "errors": 0, "skipped_no_evidence": 0,
            "hallucinated_evidence": 0, "claim_without_evidence": 0,
            "claim_only_on_recap": 0, "cost_usd": 0.0, "seconds": 0}
