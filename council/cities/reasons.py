"""Das „Warum" aus den Niederschriften — je Tagesordnungspunkt.

**Warum das nicht in ``annotate.py`` läuft.** Der übliche Lauf fragt Batches
von **Vorlagen** nach einem Etikett und erwartet vom Modell eine Liste
``results``. Hier ist das Objekt ein **Tagesordnungspunkt**, die Quelle ein
Abschnitt der Niederschrift statt des Vorlagentexts, und die Antwort gilt
genau einem Punkt. Dieselbe Trennung wie bei ``clusters.stance_all`` und
``fit.py``.

**Die Grenze, die dieses Modul nicht überschreitet.** Ein Sprachmodell darf
wiedergeben, was in einem Protokoll steht. Es darf nicht erschließen, warum
ein Rat entschieden hat. Der Prompt sagt das, die Nutzlast trägt ``grounded``
als Selbstauskunft, und die Oberfläche zeigt nichts, wo ``grounded`` falsch
ist. Ein erfundenes „Warum" wäre die schädlichste Ausgabe dieses ganzen
Features — es sähe aus wie die wertvollste.
"""
from __future__ import annotations

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from council.cities.protocol import SPLITTER_VERSION
from council.cities.store import CitiesStore, text_hash

logger = logging.getLogger("council.cities.reasons")

#: Gleichzeitige Aufrufe. Wie bei ``stance``: Ein Abschnitt je Aufruf, und die
#: Wartezeit dominiert.
REASON_WORKERS = 6

#: So viele Ergebnisse sammeln, bevor geschrieben wird. Geschrieben wird
#: ausschließlich im Hauptthread — eine SQLite-Verbindung gehört dem Thread,
#: der sie geöffnet hat (die Lehre aus ``fit.py``).
BLOCK = 25


def run(main: CitiesStore, body_id: str | None = None, limit: int | None = None,
        workers: int = 0, nur_mit_gruppe: bool = True) -> dict:
    """Für jeden geschnittenen Abschnitt wiedergeben, was dort steht."""
    from council.cities.annotate import parse_json
    from council.cities.annotators import get as get_annotator
    from kern import llm, prompts
    from council.cities.registry import BODIES

    ann = get_annotator("reason")
    auftraege = main.agenda_items_for_reason(
        ann.key, ann.version, SPLITTER_VERSION, body_id=body_id,
        limit=limit, nur_mit_gruppe=nur_mit_gruppe)
    stand = {"annotated": 0, "grounded": 0, "errors": 0, "cost_usd": 0.0, "seconds": 0}
    if not auftraege:
        return stand

    logger.info("reason: %s Abschnitte", len(auftraege))
    system = prompts.get(ann.prompt_system)
    sperre = threading.Lock()
    t0 = time.time()

    def einer(a: dict):
        stadt = BODIES[a["body_id"]].name if a["body_id"] in BODIES else a["body_id"]
        abschnitt = (a["text"] or "")[:ann.input_chars]
        try:
            antwort = llm.chat_complete(
                model=ann.model, response_format={"type": "json_object"},
                messages=[{"role": "system", "content": system},
                          {"role": "user", "content": prompts.render(
                              ann.prompt_user, stadt=stadt,
                              gremium=a.get("organization_name") or a.get("meeting_name") or "",
                              datum=(a.get("start") or "")[:10],
                              punkt=f"{a.get('number') or ''} {a.get('title') or ''}".strip(),
                              abschnitt=abschnitt)}],
                max_tokens=ann.max_tokens, temperature=ann.temperature,
                extra_body={"provider": {}} if ann.routing_free else {},
                _feature=ann.feature)
            nutzlast = ann.payload.model_validate(
                parse_json(antwort.choices[0].message.content or ""))
        except Exception as e:  # noqa: BLE001 — ein Abschnitt, nicht der Lauf
            with sperre:
                stand["errors"] += 1
            logger.info("reason gescheitert (%s): %s", a["agenda_item_id"], type(e).__name__)
            return None
        # Eine behauptete Begründung ohne Text ist keine. Das Modell antwortet
        # gelegentlich so, und die Karte zeigte dann eine Begründung aus null
        # Zeichen. Über `model_dump` statt über die Felder, weil der
        # Nutzlast-Typ am Annotator hängt und die Typprüfung ihn nur als
        # `BaseModel` kennt.
        daten = nutzlast.model_dump()
        if daten.get("grounded") and not str(daten.get("why") or "").strip():
            daten["grounded"] = False
        verbrauch = getattr(antwort, "usage", None)
        kosten = float(getattr(verbrauch, "cost", 0) or 0) if verbrauch else 0.0
        return a["agenda_item_id"], daten, text_hash(abschnitt), kosten

    with ThreadPoolExecutor(workers or REASON_WORKERS) as pool:
        puffer: list[tuple] = []
        for ergebnis in pool.map(einer, auftraege):
            if ergebnis is None:
                continue
            puffer.append(ergebnis)
            stand["cost_usd"] += ergebnis[3]
            stand["grounded"] += bool(ergebnis[1].get("grounded"))
            if len(puffer) >= BLOCK:
                _schreiben(main, ann, puffer)
                stand["annotated"] += len(puffer)
                puffer = []
        if puffer:
            _schreiben(main, ann, puffer)
            stand["annotated"] += len(puffer)

    stand["seconds"] = round(time.time() - t0)
    logger.info("reason fertig: %s Abschnitte, davon %s mit Begründung, "
                "%s Fehler, $%.4f, %ss", stand["annotated"], stand["grounded"],
                stand["errors"], stand["cost_usd"], stand["seconds"])
    return stand


def _schreiben(main: CitiesStore, ann, puffer: list[tuple]) -> None:
    with main.transaction():
        for kennung, nutzlast, quelle, kosten in puffer:
            main.put_annotation("agenda_item", kennung, ann.key, ann.version,
                                nutzlast, quelle, model=ann.model, cost_usd=kosten)
