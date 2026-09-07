"""Die Stufen: fetch → normalize → extract → annotate → index.

Jede Stufe liest die Tabellen der vorigen und schreibt ihre eigenen. Damit ist
jede für sich wiederholbar: neuer Extraktor → nur ``extract`` und alles
danach; neuer Prompt → nur ``annotate`` für diesen Annotator; neues
Embedding-Modell → nur ``index`` mit anderem Modellnamen. Keine Stufe außer
``fetch`` fasst die Rohablage an.

**Warum die Ernte in eine eigene Datei je Stadt schreibt.** Parallel laufen
darf nur, was verschiedene Hosts anspricht — die Hauptdatenbank hat genau
einen Schreiber. ``fetch`` füllt also ``data/cities-raw/<slug>.sqlite``,
``normalize`` liest daraus und schreibt die Hauptdatenbank, Stadt für Stadt.
"""
from __future__ import annotations

import logging
from pathlib import Path

from council.cities.adapters import get_adapter
from council.cities.model import Body
from council.cities.oparl import OParlClient, file_path
from council.cities.registry import BodySpec
from council.cities.store import CitiesStore
from council.cities.text import EXTRACTOR, VERSION, extract as extract_text

logger = logging.getLogger("council.cities.pipeline")

STAGES = ("fetch", "normalize", "extract", "annotate", "index")

#: Dateirollen, deren Bytes geholt werden. Anlagen (Lagepläne, Tabellen) sind
#: meist Bild-PDFs und tragen für die Auswertung nichts bei — sie bleiben als
#: Verweis stehen und lassen sich später nachladen.
FETCH_ROLES = ("main",)


def raw_path_for(raw_dir: str | Path, body_id: str) -> Path:
    return Path(raw_dir) / f"{body_id}.sqlite"


# ------------------------------------------------------------------- fetch

def fetch(spec: BodySpec, raw_dir: str | Path, files_dir: str | Path,
          since: str | None = None, with_files: bool = True,
          max_files: int | None = None) -> dict:
    """Alles Öffentliche einer Stadt holen und roh ablegen."""
    seit = since or spec.since
    adapter = get_adapter(spec.dialect)
    raw = CitiesStore(raw_path_for(raw_dir, spec.id))
    zahlen = {"organizations": 0, "meetings": 0, "papers": 0,
              "files_fetched": 0, "files_failed": 0, "requests": 0}
    try:
        client = OParlClient(raw, spec.id, files_dir)
        gefunden = adapter.discover(client, spec)
        body = gefunden["body"]
        raw.upsert_body(Body(spec.id, gefunden.get("name") or spec.name, spec.state,
                             spec.dialect, spec.system_url, gefunden.get("license")))

        for _ in adapter.iter_organizations(client, body):
            zahlen["organizations"] += 1
        logger.info("%s: %s Gremien", spec.id, zahlen["organizations"])

        for _ in adapter.iter_meetings(client, body, seit):
            zahlen["meetings"] += 1
        logger.info("%s: %s Sitzungen", spec.id, zahlen["meetings"])

        for _ in adapter.iter_papers(client, body, seit):
            zahlen["papers"] += 1
        logger.info("%s: %s Vorlagen", spec.id, zahlen["papers"])

        if with_files and spec.fetch_files:
            # Die Dateiliste steht erst nach dem Normalisieren fest; für die
            # Ernte reicht, was in den Rohobjekten steht.
            batch = adapter.normalize(spec.id, raw)
            raw.upsert_batch(batch)
            offen = raw.files_without_bytes(spec.id, FETCH_ROLES, limit=max_files)
            for i, datei in enumerate(offen, 1):
                antwort = client.get_file(datei["access_url"])
                if not antwort:
                    zahlen["files_failed"] += 1
                    raw.mark_stage("file", datei["id"], "fetch", "1", "error", "nicht abrufbar")
                    continue
                daten, mime = antwort
                sha = client.store_file(daten, mime)
                raw.set_file_sha(datei["id"], sha)
                zahlen["files_fetched"] += 1
                if i % 50 == 0:
                    logger.info("%s: %s/%s Dateien", spec.id, i, len(offen))
        zahlen["requests"] = client.requests_made
    finally:
        raw.close()
    return zahlen


# --------------------------------------------------------------- normalize

def normalize(spec: BodySpec, raw_dir: str | Path, main: CitiesStore) -> dict:
    """Rohablage der Stadt → normalisierte Schicht der Hauptdatenbank."""
    adapter = get_adapter(spec.dialect)
    pfad = raw_path_for(raw_dir, spec.id)
    if not pfad.exists():
        return {"papers": 0, "meetings": 0, "agenda_items": 0, "organizations": 0,
                "files": 0, "consultations": 0}
    raw = CitiesStore(pfad)
    try:
        gefunden = raw.body(spec.id)
        main.upsert_body(Body(
            spec.id, (gefunden or {}).get("name") or spec.name, spec.state, spec.dialect,
            spec.system_url, (gefunden or {}).get("license")))
        batch = adapter.normalize(spec.id, raw)
        zahlen = main.upsert_batch(batch)
        # Die geladenen Bytes stehen in der Rohdatei; die Hauptdatenbank
        # braucht den Verweis, damit `extract` sie findet.
        for datei in raw.raw_files():
            main.put_raw_file(datei["sha256"], datei["bytes"], datei["mime"],
                              datei["path"], datei["first_seen"])
        for file_id, sha in raw.file_shas(spec.id):
            main.set_file_sha(file_id, sha)
    finally:
        raw.close()
    return zahlen


# ----------------------------------------------------------------- extract

def extract(main: CitiesStore, files_dir: str | Path, body_id: str | None = None,
            limit: int | None = None) -> dict:
    """Aus den abgelegten Bytes Text machen — für alles, was noch keinen hat."""
    offen = main.files_without_text(EXTRACTOR, VERSION, body_id, limit)
    zahlen = {"ok": 0, "thin": 0, "empty": 0, "error": 0, "missing_bytes": 0}
    for i, datei in enumerate(offen, 1):
        pfad = file_path(files_dir, datei["sha256"])
        if not pfad.exists():
            zahlen["missing_bytes"] += 1
            continue
        text, seiten, qualitaet = extract_text(pfad.read_bytes())
        main.put_text(datei["id"], EXTRACTOR, VERSION, text, seiten, qualitaet)
        main.mark_stage("file", datei["id"], "extract", VERSION,
                        "done" if qualitaet in ("ok", "thin") else "error", qualitaet)
        zahlen[qualitaet] = zahlen.get(qualitaet, 0) + 1
        if i % 100 == 0:
            logger.info("Text: %s/%s", i, len(offen))
    return zahlen


def extract_inline(main: CitiesStore, spec: BodySpec, raw_dir: str | Path) -> int:
    """Texte übernehmen, die schon vorliegen — statt dieselben PDFs erneut zu holen.

    Zwei Fälle: **more! rubin** liefert den Volltext im Dateiobjekt mit, und
    für **Oldenburg** steht er längst geparst in der Rats-Datenbank.
    """
    if spec.dialect == "rubin":
        from council.cities.adapters.rubin import OPARL_TEXT, RubinAdapter
        adapter, extraktor = RubinAdapter(), OPARL_TEXT
    elif spec.dialect == "oldenburg":
        from council.cities.adapters.oldenburg import EXTRACTOR, OldenburgAdapter
        adapter, extraktor = OldenburgAdapter(), EXTRACTOR
    else:
        return 0

    pfad = raw_path_for(raw_dir, spec.id)
    if not pfad.exists():
        return 0
    raw = CitiesStore(pfad)
    try:
        n = 0
        with main.transaction():
            for file_id, text in adapter.inline_texts(raw, spec.id):
                main.put_text(file_id, extraktor, "1", text, None,
                              "ok" if len(text) > 200 else ("thin" if text else "empty"))
                n += 1
        return n
    finally:
        raw.close()


# --------------------------------------------------------------------- run

def run(spec: BodySpec, main: CitiesStore, raw_dir: str | Path, files_dir: str | Path,
        since: str | None = None, stages: tuple[str, ...] = ("fetch", "normalize", "extract"),
        max_files: int | None = None) -> dict:
    """Die Stufen einer Stadt der Reihe nach."""
    zahlen: dict[str, object] = {"body": spec.id}
    if "fetch" in stages:
        zahlen["fetch"] = fetch(spec, raw_dir, files_dir, since, max_files=max_files)
    if "normalize" in stages:
        zahlen["normalize"] = normalize(spec, raw_dir, main)
        inline = extract_inline(main, spec, raw_dir)
        if inline:
            zahlen["inline_texts"] = inline
    if "extract" in stages:
        zahlen["extract"] = extract(main, files_dir, spec.id)
    return zahlen
