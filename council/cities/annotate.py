"""Einen Annotator über den Bestand laufen lassen.

Drei Dinge, die der Probelauf gelehrt hat und die hier fest eingebaut sind:

1. **Modelle lassen in Batches Einträge aus.** Ein Lauf über 45 Vorlagen
   lieferte 33. Deshalb gibt es einen Nachlauf, der die Ausgelassenen einzeln
   nachreicht.
2. **Antworten kommen nicht immer als reines JSON.** Mal mit ```json-Zaun, mal
   mit führendem Leerzeichen, mal mit Vorrede. Der Parser probiert drei Wege,
   bevor er aufgibt.
3. **Eine leere Antwort ist kein Fehler des Servers, sondern ein zu knappes
   Token-Budget.** Sie kommt mit Status 200. Ein Batch, der so scheitert, darf
   den Lauf nicht abbrechen — er landet im Nachlauf.

Geschrieben wird aus **einem** Thread: Die Aufrufe laufen parallel, die
Datenbank sieht genau einen Schreiber.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import threading
import time
from collections.abc import Iterator, Sequence
from concurrent.futures import ThreadPoolExecutor

from pydantic import ValidationError

from council.cities.annotators import Annotator
from council.cities.store import CitiesStore
from council.topics import POLICY_FIELDS
from kern import llm, prompts

logger = logging.getLogger("council.cities.annotate")

#: Wie viele Aufrufe gleichzeitig unterwegs sind. Zwölf waren im Probelauf der
#: Punkt, an dem OpenRouter nicht mehr schneller wurde.
WORKERS = 8


def field_list() -> str:
    """Die Themenfelder für den Prompt — dieselben wie in Oldenburg.

    Eine eigene Liste für fremde Städte wäre der sichere Weg, den Vergleich
    unmöglich zu machen.
    """
    return "\n".join(f'- {k}: {label} — {desc}' for k, (label, desc) in POLICY_FIELDS.items())


def parse_json(content: str) -> dict:
    """Modellantwort zu einem dict — auch wenn sie nicht sauber ankommt.

    Gibt **immer** ein Objekt zurück oder wirft. Eine Liste an der Wurzel ist
    gültiges JSON und wäre bis hierher durchgerutscht; der Aufrufer greift
    danach mit ``.get`` zu und stürbe an einer Stelle, die nichts mehr über
    die Ursache weiß.
    """
    text = (content or "").strip()
    if not text:
        raise ValueError("leere Antwort (meist: Token-Budget beim Denken verbraucht)")
    for kandidat in _kandidaten(text):
        try:
            daten = json.loads(kandidat)
        except ValueError:
            continue
        if isinstance(daten, dict):
            return daten
    raise ValueError(f"unlesbare Antwort: {text[:120]!r}")


def _kandidaten(text: str) -> Iterator[str]:
    """Der Text selbst, ohne Zaun, und der erste geschweifte Block darin."""
    yield text
    if text.startswith("```"):
        ohne = text.strip("`").strip()
        if ohne[:4].lower() == "json":
            ohne = ohne[4:].strip()
        yield ohne
    treffer = re.search(r"\{.*\}", text, re.S)
    if treffer:
        yield treffer.group(0)


def source_hash(paper: dict, text: str | None, ann: Annotator) -> str:
    """Woraus die Annotation entstanden ist.

    Ändert sich einer der Bestandteile — Titel, Datum, Art, Textanfang, die
    Fassung des Annotators oder sein Prompt —, gilt die alte Annotation als
    veraltet und der nächste Lauf rechnet sie neu. Alles andere bleibt liegen;
    genau das macht einen Wochenlauf billig.
    """
    teile = [
        paper.get("name") or "", paper.get("date") or "", paper.get("paper_type_raw") or "",
        (text or "")[:ann.input_chars], ann.version,
        prompts.get(ann.prompt_system)[:200],
    ]
    return hashlib.sha256("␟".join(teile).encode("utf-8")).hexdigest()


def batch_text(rows: Sequence[dict], texte: dict[str, str], ann: Annotator) -> str:
    zeilen = []
    for r in rows:
        text = (texte.get(r["id"]) or "").replace("\n", " ")[:ann.input_chars]
        zeilen.append(
            f"id {r['id']}\n"
            f"  Stadt: {r['body_id']}\n"
            f"  Art: {r.get('paper_type_raw') or r.get('kind')}\n"
            f"  Datum: {r.get('date') or 'unbekannt'}\n"
            f"  Titel: {r.get('name')}\n"
            f"  Text: {text}")
    return "\n\n".join(zeilen)


def run(main: CitiesStore, ann: Annotator, body_id: str | None = None,
        limit: int | None = None, workers: int = WORKERS) -> dict:
    """Alles annotieren, was noch keine oder eine veraltete Annotation hat."""
    kandidaten = main.papers(body_id=body_id)
    texte = {p["id"]: (main.text_for_paper(p["id"]) or "") for p in kandidaten}
    hashes = {p["id"]: source_hash(p, texte.get(p["id"]), ann) for p in kandidaten}

    offen = main.annotations_missing("paper", ann.key, ann.version, body_id=body_id,
                                     source_hashes=hashes)
    if limit:
        offen = offen[:limit]
    if not offen:
        return {"annotated": 0, "errors": 0, "cost_usd": 0.0, "seconds": 0}

    logger.info("%s/%s: %s Vorlagen einzuordnen", ann.key, ann.version, len(offen))
    system = prompts.render(ann.prompt_system, fields=field_list())
    sperre = threading.Lock()
    stand = {"annotated": 0, "errors": 0, "cost_usd": 0.0,
             "prompt_tokens": 0, "completion_tokens": 0}
    t0 = time.time()

    def einen_batch(chunk: list[dict]) -> tuple[list[tuple[str, dict, float]], list[str], str | None]:
        """Ein Batch ans Modell — **ohne** die Datenbank anzufassen.

        Gibt zurück: die geprüften Ergebnisse, die ausgelassenen ids und einen
        Fehlertext. Geschrieben wird ausschließlich im Hauptthread: Eine
        SQLite-Verbindung gehört dem Thread, der sie geöffnet hat, und ein
        Schreibversuch von anderswo wirft — was die Tests hier gefunden haben.
        """
        erwartet = {r["id"] for r in chunk}
        try:
            extra = {"provider": {}} if ann.routing_free else {}
            antwort = llm.chat_complete(
                model=ann.model, response_format={"type": "json_object"},
                messages=[{"role": "system", "content": system},
                          {"role": "user", "content":
                              prompts.render(ann.prompt_user,
                                             items=batch_text(chunk, texte, ann))}],
                max_tokens=ann.max_tokens, temperature=ann.temperature,
                extra_body=extra, _feature=ann.feature)
            daten = parse_json(antwort.choices[0].message.content or "")
        except Exception as e:  # noqa: BLE001 — ein Batch, nicht der Lauf
            return [], sorted(erwartet), f"{type(e).__name__}: {str(e)[:120]}"

        verbrauch = getattr(antwort, "usage", None)
        kosten = float(getattr(verbrauch, "cost", 0) or 0) if verbrauch else 0.0
        with sperre:
            if verbrauch:
                stand["prompt_tokens"] += verbrauch.prompt_tokens or 0
                stand["completion_tokens"] += verbrauch.completion_tokens or 0
                stand["cost_usd"] += kosten

        fertig: list[tuple[str, dict, float]] = []
        ergebnisse = daten.get("results")
        for eintrag in ergebnisse if isinstance(ergebnisse, list) else []:
            # Gemessen am Bestandslauf: Ein Batch kam als Liste von Strings
            # zurück statt als Liste von Objekten. Der Zugriff warf im
            # Arbeitsthread, `pool.map` reichte das weiter — und riss den
            # ganzen Lauf um, nach 520 von 619 Batches.
            if not isinstance(eintrag, dict):
                continue
            kennung = str(eintrag.get("id", ""))
            if kennung not in erwartet:
                continue      # halluzinierte id — verwerfen
            try:
                nutzlast = ann.payload.model_validate(
                    {k: v for k, v in eintrag.items() if k != "id"})
            except ValidationError as e:
                logger.info("Antwort passt nicht zur Form (%s): %s", kennung, str(e)[:120])
                continue
            fertig.append((kennung, nutzlast.model_dump(), kosten / max(len(chunk), 1)))
        return fertig, sorted(erwartet - {k for k, _, _ in fertig}), None

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

    chunks = [offen[i:i + ann.batch_size] for i in range(0, len(offen), ann.batch_size)]
    ausgelassen: list[str] = []
    with ThreadPoolExecutor(workers) as pool:
        for n, (fertig, fehlend, fehler) in enumerate(pool.map(einen_batch, chunks), 1):
            schreiben(fertig)
            ausgelassen += fehlend
            if fehler:
                stand["errors"] += 1
                logger.info("Batch gescheitert: %s", fehler)
            if n % 20 == 0:
                logger.info("  %s/%s Batches · %.0fs · $%.4f",
                            n, len(chunks), time.time() - t0, stand["cost_usd"])

    # Nachlauf: Was das Modell ausgelassen hat, einzeln nachreichen. Im
    # Probelauf betraf das bis zu einem Viertel der Einträge.
    if ausgelassen:
        logger.info("Nachlauf für %s ausgelassene", len(ausgelassen))
        nach_id = {p["id"]: p for p in offen}
        einzeln = [[nach_id[i]] for i in ausgelassen if i in nach_id]
        with ThreadPoolExecutor(workers) as pool:
            for fertig, _fehlend, _fehler in pool.map(einen_batch, einzeln):
                schreiben(fertig)

    stand["seconds"] = round(time.time() - t0)
    stand["skipped"] = len(ausgelassen)
    logger.info("%s fertig: %s Stück, $%.4f, %ss",
                ann.key, stand["annotated"], stand["cost_usd"], stand["seconds"])
    return stand
