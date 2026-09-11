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
from datetime import date
from pathlib import Path

from council.cities.adapters import get_adapter
from council.cities.model import Body
from council.cities.oparl import OParlClient, file_path
from council.cities.registry import BodySpec
from council.cities.store import CitiesStore
from council.cities.text import (EXTRACTOR, MAX_CHARS, MAX_CHARS_PROTOKOLL, MAX_PAGES,
                                 MAX_PAGES_PROTOKOLL, VERSION, extract as extract_text)

logger = logging.getLogger("council.cities.pipeline")

STAGES = ("fetch", "normalize", "extract", "annotate", "index")

#: Dateirollen, deren Bytes geholt werden. Anlagen (Lagepläne, Tabellen) sind
#: meist Bild-PDFs und tragen für die Auswertung nichts bei — sie bleiben als
#: Verweis stehen und lassen sich später nachladen.
FETCH_ROLES = ("main",)

#: Die Niederschrift hängt an der **Sitzung**, nicht am Papier, und sie ist
#: das Einzige, worin steht, WARUM ein Rat so entschieden hat. Sie wird
#: getrennt geholt, weil zwei Dinge anders sind als bei der Vorlage: Es gibt
#: sie nur für ein Zeitfenster (s. ``PROTOCOL_MONTHS``), und eine Stadt kann
#: sie in ihrer Schnittstelle nennen, ohne sie auszuliefern (s.
#: ``PROTOCOL_NIETEN``).
PROTOCOL_ROLE = "protocol"

#: Wie weit zurück Niederschriften geholt werden. 24 Monate ist der Zeitraum,
#: in dem die Ideen auf der Karte liegen; alles davor kostet Abrufe und
#: Plattenplatz für Vergleiche, die niemand zieht.
PROTOCOL_MONTHS = 24

#: Nach so vielen Fehlschlägen in Folge hört der Lauf mit den Niederschriften
#: EINER Stadt auf. Magdeburg nennt 606 Protokoll-Adressen, von denen jede
#: einzelne mit 404 antwortet — das sind 606 sinnlose Abrufe bei einer Stadt,
#: die uns nichts getan hat. Die Registry weiß es, aber der Code soll es
#: messen und nicht wissen: Eine Stadt, die morgen repariert, wird morgen
#: wieder geholt.
PROTOCOL_NIETEN = 3


def raw_path_for(raw_dir: str | Path, body_id: str) -> Path:
    return Path(raw_dir) / f"{body_id}.sqlite"


def protokoll_fenster(monate: int = PROTOCOL_MONTHS, heute: date | None = None) -> str:
    """Ab welchem Sitzungsdatum Niederschriften geholt werden (``JJJJ-MM-TT``)."""
    tag = heute or date.today()
    jahre, monat = divmod(tag.month - 1 - monate, 12)
    return f"{tag.year + jahre:04d}-{monat + 1:02d}-01"


def _hole(client, raw: CitiesStore, body_id: str, offen: list[dict], zahlen: dict,
          was: str, nieten_max: int | None = None,
          schluessel: tuple[str, str] = ("files_fetched", "files_failed")) -> dict:
    """Bytes zu einer Arbeitsliste holen. Bricht nach ``nieten_max`` Nieten ab."""
    gut, schlecht = schluessel
    nieten = 0
    for i, datei in enumerate(offen, 1):
        antwort = client.get_file(datei["access_url"])
        if not antwort:
            zahlen[schlecht] = zahlen.get(schlecht, 0) + 1
            raw.mark_stage("file", datei["id"], "fetch", "1", "error", "nicht abrufbar")
            nieten += 1
            if nieten_max and nieten >= nieten_max:
                logger.warning("%s: %s nach %s Fehlschlägen in Folge abgebrochen "
                               "(%s von %s offen)", body_id, was, nieten,
                               len(offen) - i, len(offen))
                break
            continue
        nieten = 0
        daten, mime = antwort
        sha = client.store_file(daten, mime)
        raw.set_file_sha(datei["id"], sha)
        zahlen[gut] = zahlen.get(gut, 0) + 1
        if i % 50 == 0:
            logger.info("%s: %s/%s %s", body_id, i, len(offen), was)
    return zahlen


# ------------------------------------------------------------------- fetch

def fetch(spec: BodySpec, raw_dir: str | Path, files_dir: str | Path,
          since: str | None = None, with_files: bool = True,
          max_files: int | None = None) -> dict:
    """Alles Öffentliche einer Stadt holen und roh ablegen."""
    seit = since or spec.since
    adapter = get_adapter(spec.dialect)
    raw = CitiesStore(raw_path_for(raw_dir, spec.id))
    zahlen = {"organizations": 0, "meetings": 0, "papers": 0,
              "files_fetched": 0, "files_failed": 0,
              "protocols_fetched": 0, "protocols_failed": 0, "requests": 0}
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
            _hole(client, raw, spec.id, offen, zahlen, "Dateien")

            # Die Niederschriften bekommen ein EIGENES Budget, keinen Rest:
            # Vorlagen gibt es zehnmal so viele, und ein geteiltes Budget
            # hieße, dass ein gedrosselter Lauf nie zu den Protokollen kommt.
            protokolle = raw.files_without_bytes(
                spec.id, (PROTOCOL_ROLE,), limit=max_files,
                meeting_since=protokoll_fenster())
            _hole(client, raw, spec.id, protokolle, zahlen, "Niederschriften",
                  nieten_max=PROTOCOL_NIETEN,
                  schluessel=("protocols_fetched", "protocols_failed"))
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
        # Niederschriften bekommen die größeren Deckel: Was abgeschnitten
        # wird, sind die HINTEREN Tagesordnungspunkte (s. council/cities/text.py).
        protokoll = datei.get("role") == PROTOCOL_ROLE
        text, seiten, qualitaet = extract_text(
            pfad.read_bytes(),
            max_pages=MAX_PAGES_PROTOKOLL if protokoll else MAX_PAGES,
            max_chars=MAX_CHARS_PROTOKOLL if protokoll else MAX_CHARS)
        main.put_text(datei["id"], EXTRACTOR, VERSION, text, seiten, qualitaet)
        main.mark_stage("file", datei["id"], "extract", VERSION,
                        "done" if qualitaet in ("ok", "thin") else "error", qualitaet)
        zahlen[qualitaet] = zahlen.get(qualitaet, 0) + 1
        if i % 100 == 0:
            logger.info("Text: %s/%s", i, len(offen))
    return zahlen


def split_protocols(main: CitiesStore, body_id: str | None = None,
                    limit: int | None = None) -> dict:
    """Geholte Niederschriften in ihre Tagesordnungspunkte schneiden.

    Regelarbeit: kein Modell, kein Netz. Läuft direkt nach ``extract``, damit
    die Abschnitte dastehen, bevor jemand nach dem „Warum" fragt.
    """
    from council.cities.protocol import SPLITTER_VERSION, split_meeting

    offen = main.protocols_with_text(EXTRACTOR, VERSION, SPLITTER_VERSION,
                                     body_id, limit)
    zahlen = {"protocols": 0, "sections": 0, "empty": 0}
    for zeile in offen:
        n = split_meeting(main, zeile["meeting_id"], zeile["file_id"], zeile["text"])
        zahlen["protocols"] += 1
        zahlen["sections"] += n
        zahlen["empty"] += not n
    if zahlen["protocols"]:
        logger.info("%s: %s Niederschriften geschnitten, %s Abschnitte, "
                    "%s ohne Treffer", body_id or "alle", zahlen["protocols"],
                    zahlen["sections"], zahlen["empty"])
    return zahlen


def inline_sections(main: CitiesStore, spec: BodySpec, raw_dir: str | Path) -> int:
    """Abschnitte übernehmen, die schon getrennt vorliegen.

    **Nicht jede Stadt legt das „Warum" in eine Niederschrift.** ALLRIS
    classic gibt zu jedem beratenen Punkt einen eigenen „Auszug" heraus, mit
    Wortprotokoll, Beschluss und Abstimmungsergebnis — schon getrennt, als
    HTML, ohne PDF. Es gibt dort also nichts zu schneiden, und
    ``split_protocols`` fände nichts: Sie sucht Dateien mit der Rolle
    ``protocol``, und Hildesheim hat keine.

    Das Ergebnis ist dasselbe wie beim Schnitt — Zeilen in
    ``protocol_sections``, die der Annotator ``reason`` liest.
    """
    if spec.dialect != "allris_classic":
        return 0
    from council.cities.adapters.allris_classic import AllrisClassicAdapter
    from council.cities.protocol import SPLITTER_VERSION

    pfad = raw_path_for(raw_dir, spec.id)
    if not pfad.exists():
        return 0
    raw = CitiesStore(pfad)
    try:
        zeilen = AllrisClassicAdapter().auszug_abschnitte(raw, spec.id)
        if zeilen:
            main.put_protocol_sections(SPLITTER_VERSION, zeilen)
        logger.info("%s: %s Abschnitte aus Auszügen", spec.id, len(zeilen))
        return len(zeilen)
    finally:
        raw.close()


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


# ---------------------------------------------------------------- annotate

def annotate(main: CitiesStore, body_id: str | None = None,
             limit: int | None = None, nach_index: bool = False) -> dict:
    """Die Annotatoren laufen lassen, die an dieser Stelle dran sind.

    **Zwei Stellen, nicht eine.** ``classify`` gibt einer fremden Vorlage ihr
    Etikett und braucht dafür nur sie selbst — es läuft vor dem Index.
    ``fit`` urteilt über Oldenburg und braucht die Nachbarschaften als Belege;
    es läuft danach. Ein Annotator sagt über ``needs_index`` selbst, wohin er
    gehört, statt dass der Cron eine Liste pflegt, die auseinanderläuft.
    """
    from council.cities import annotate as annotate_modul
    from council.cities.annotators import active_annotators

    zahlen: dict[str, dict] = {}
    for ann in active_annotators("paper"):
        if ann.needs_index != nach_index:
            continue
        if ann.key == "fit":
            zahlen[f"{ann.key}/{ann.version}"] = _fit(main, ann, body_id, limit)
        else:
            zahlen[f"{ann.key}/{ann.version}"] = annotate_modul.run(
                main, ann, body_id, limit)
    return zahlen


def _fit(main: CitiesStore, ann, body_id: str | None, limit: int | None) -> dict:
    """``fit`` braucht die Rats-Datenbank für die Belege — als einziger.

    Sie wird hier geöffnet und wieder geschlossen, nicht durchgereicht: Der
    Rest der Pipeline hat mit ihr nichts zu tun, und eine Verbindung, die
    durch fünf Stufen wandert, wird irgendwann von der falschen benutzt.
    """
    import os

    from council.cities import ROOT
    from council.cities import fit as fit_modul
    from council.cities.index import EMBED_MODEL
    from council.store import CouncilStore

    pfad = Path(os.environ.get("COUNCIL_DB") or ROOT / "data" / "council.sqlite")
    if not pfad.exists():
        logger.warning("fit übersprungen: %s gibt es nicht", pfad)
        return {"annotated": 0, "errors": 0, "skipped_no_council_db": 1,
                "cost_usd": 0.0, "seconds": 0}
    rats = CouncilStore(pfad)
    try:
        return fit_modul.run(main, rats, ann, EMBED_MODEL, body_id, limit)
    finally:
        rats.close()


# ------------------------------------------------------------------- index

def cluster_all(main: CitiesStore) -> dict:
    """Ideen einbetten und zu Clustern zusammenfassen.

    Läuft NACH der Einordnung (sie sagt, was eine Idee ist) und braucht
    fastembed — deshalb lazy importiert wie der Index. Über ALLE Städte
    zusammen, denn ein Cluster über Stadtgrenzen ist der ganze Zweck.
    """
    from council.cities import clusters as cluster_modul
    return cluster_modul.run(main)


def index_all(main: CitiesStore, body_id: str | None = None) -> dict:
    """Chunks, Embeddings, Volltext und Nachbarschaften.

    Braucht fastembed — deshalb lazy importiert und nur vom Cron und von
    Ops-Skripten gerufen, nie vom Web-Dienst.
    """
    from council.cities import index as index_modul
    return index_modul.run(main, body_id)


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
        abschnitte = inline_sections(main, spec, raw_dir)
        if abschnitte:
            zahlen["inline_sections"] = abschnitte
    if "extract" in stages:
        zahlen["extract"] = extract(main, files_dir, spec.id)
    return zahlen
