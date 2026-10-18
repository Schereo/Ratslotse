#!/usr/bin/env python3
"""Den Bestand mit PyMuPDF neu lesen — VORGABE: Trockenlauf.

Seit #1722 liest ``council/anlagentext.py::pdf_seiten`` neue PDFs mit PyMuPDF
statt pypdf; pypdf hatte Leerzeichen mitten ins Wort gesetzt („de r“,
„R atsherr“). Was VORHER gelesen wurde, trägt die Risse weiter. Dieses Skript
holt die PDFs von Vorlagen, Protokollen und Anlagen noch einmal und liest sie
neu — Haushalts-Anlagen ausgenommen, deren Parser auf pypdf abgestimmt sind
(``anlagentext.extraktor_fuer``).

Ohne ``--ausfuehren`` wird NICHTS geschrieben: Der Lauf lädt, liest, vergleicht
mit dem gespeicherten Text und berichtet. Mit ``--ausfuehren`` schreibt er je
Dokument sofort (stapelweise, nicht am Ende) und merkt sich, was erledigt ist —
ein zweiter Lauf setzt dort fort.

**Was nie geschrieben wird, auch mit ``--ausfuehren``:**

- Protokolle, deren Seitenzahl sich ändert — an den Seiten hängen
  ``page_offsets`` und die Fundstellen der Wortbeiträge.
- Protokolle, deren Abschnitte der TOP-Schnitt mit dem neuen Text SELTENER
  findet als mit dem alten (``haushaltsdebatte.top_abschnitt``).
- Dokumente, die mit dem neuen Text leer würden, obwohl der alte etwas trug.
- Dokumente, deren WÖRTER gleich bleiben und nur anders umbrochen sind —
  das brächte keine Lesbarkeit, kostete aber ein neues Embedding.
- Anlagen, die per OCR gelesen wurden (``ocr_model``) — ihr Text kommt nicht
  aus der Textebene.

Höflich: mindestens ``--abstand`` Sekunden (Vorgabe 1,2) zwischen zwei
Downloads, ein Download zur Zeit. Tritt dem Deploy zur Seite (``kern/stopp``).

    python scripts/pdf_neu_lesen.py --limit 50            # Stichprobe je Art, trocken
    python scripts/pdf_neu_lesen.py --art protokolle      # alle Protokolle, trocken
    python scripts/pdf_neu_lesen.py --ausfuehren          # alles, schreibend
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import re
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from council import anlagentext, finanzquellen  # noqa: E402
from council.haushaltsdebatte import saeubern, top_abschnitt  # noqa: E402
from council.protocols import page_offsets  # noqa: E402
from council.store import CouncilStore  # noqa: E402
from council.vorlagen import _session  # noqa: E402
from kern.stopp import Stopp  # noqa: E402

COUNCIL_DB = Path(os.environ.get("COUNCIL_DB") or ROOT / "data" / "council.sqlite")
ARTEN = ("vorlagen", "protokolle", "anlagen")
#: Was schon neu gelesen ist — nur mit ``--ausfuehren`` geführt.
FORTSCHRITT = ".pdf_neu_lesen.json"

_WORT = re.compile(r"[A-Za-zÄÖÜäöüß]+")


def wortrisse(a: str, b: str) -> int:
    """Wortpaare in ``a``, die in ``b`` als EIN Wort stehen und dort getrennt
    nicht vorkommen — „de r“ in a, „der“ in b. Dieselbe Zählung wie die
    Messung in ``council/anlagentext.py``."""
    tb = collections.Counter(_WORT.findall(b))
    ta = _WORT.findall(a)
    return sum(1 for x, y in zip(ta, ta[1:])
               if len(x + y) > 3 and tb[x + y] and (not tb[x] or not tb[y]))


def _top_treffer(store: CouncilStore, ksinr: int, text: str) -> int:
    tops = [r[0] for r in store._conn.execute(  # noqa: SLF001
        "SELECT item_number FROM council_decisions WHERE ksinr = ? AND kind = 'decision' "
        "AND item_number IS NOT NULL", (ksinr,))]
    s = saeubern(text)
    return sum(1 for nr in tops if top_abschnitt(s, re.sub(r"^Ö\s*", "", nr)).strip())


def kandidaten(store: CouncilStore, art: str) -> list[dict]:
    """Neueste zuerst — die werden am meisten gelesen."""
    c = store._conn  # noqa: SLF001
    if art == "vorlagen":
        sql = ("SELECT kvonr AS id, document_url AS url, raw_text, n_pages FROM council_templates "
               "WHERE status = 'ok' AND document_url IS NOT NULL ORDER BY kvonr DESC")
        return [dict(r) for r in c.execute(sql)]
    if art == "protokolle":
        sql = ("SELECT ksinr AS id, document_url AS url, raw_text, n_pages FROM council_protocols "
               "WHERE document_url IS NOT NULL AND raw_text IS NOT NULL ORDER BY ksinr DESC")
        return [dict(r) for r in c.execute(sql)]
    wo, werte = finanzquellen.finanz_anlagen_where()
    zeilen = [dict(r) for r in c.execute(
        "SELECT document_id AS id, url, raw_text, n_pages, label, "
        "(SELECT t.title FROM council_templates t WHERE t.kvonr = council_attachments.kvonr "
        " LIMIT 1) AS vorlagentitel FROM council_attachments "
        f"WHERE status = 'ok' AND ocr_model IS NULL AND url IS NOT NULL AND NOT {wo} "
        "ORDER BY document_id DESC", werte)]
    # Doppelt hält besser: dieselbe Regel, mit der der Backfill den Extraktor wählt.
    return [z for z in zeilen
            if anlagentext.extraktor_fuer(z["label"], z["vorlagentitel"]) == anlagentext.PYMUPDF]


def pruefen(store: CouncilStore, art: str, z: dict, daten: bytes) -> dict:
    """Neu lesen und gegen den Bestand halten. Liefert, was geschrieben würde
    (``neu``), oder warum nicht (``gesperrt``)."""
    seiten = anlagentext.pdf_seiten(daten, anlagentext.PYMUPDF)
    neu = "\n".join(seiten)
    if art == "anlagen":
        neu = anlagentext.beurteilen(neu)
    alt = z["raw_text"] or ""
    # Die Offsets gelten für GENAU diesen Text — aus denselben Seiten.
    e = {"seiten": len(seiten), "offsets": page_offsets(seiten), "neu": neu,
         "risse_vorher": wortrisse(alt, neu),
         "risse_nachher": wortrisse(neu, alt), "zeichen_alt": len(alt), "zeichen_neu": len(neu),
         "gesperrt": None}
    if neu == alt:
        e["gesperrt"] = "unverändert"
    elif neu.split() == alt.split():
        # Dieselben Wörter, nur anders umbrochen: kein Gewinn an Lesbarkeit,
        # aber ein neues Embedding und ein neuer Volltext-Hash. Gemessen an den
        # 20 neuesten Vorlagen (17.10.2026): alle 20 so. Ein Riss („de r“ →
        # „der“) ändert dagegen die WÖRTER und wird geschrieben.
        e["gesperrt"] = "unverändert (nur Leerraum)"
    elif alt.strip() and not neu.strip():
        e["gesperrt"] = "würde leer"
    elif art == "protokolle":
        if z["n_pages"] and len(seiten) != z["n_pages"]:
            e["gesperrt"] = f"Seitenzahl {z['n_pages']} → {len(seiten)}"
        else:
            vorher, nachher = _top_treffer(store, z["id"], alt), _top_treffer(store, z["id"], neu)
            e["tops"] = (vorher, nachher)
            if nachher < vorher:
                e["gesperrt"] = f"TOP-Schnitt {vorher} → {nachher}"
    return e


def schreiben(store: CouncilStore, art: str, z: dict, e: dict) -> None:
    if art == "vorlagen":
        store.vorlagentext_ersetzen(z["id"], e["neu"], e["seiten"])
    elif art == "protokolle":
        store.replace_protocol_text(z["id"], e["neu"], e["seiten"], e["offsets"])
    else:
        store.anlagentext_nachtragen(z["id"], e["neu"], e["seiten"])


def _fortschritt_lesen(pfad: Path) -> dict[str, set]:
    try:
        roh = json.loads(pfad.read_text())
    except (OSError, ValueError):
        return {a: set() for a in ARTEN}
    return {a: set(roh.get(a, [])) for a in ARTEN}


def _fortschritt_schreiben(pfad: Path, erledigt: dict[str, set]) -> None:
    pfad.write_text(json.dumps({a: sorted(v) for a, v in erledigt.items()}))


def main(argv: list[str] | None = None) -> dict:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--db", type=Path, default=COUNCIL_DB)
    ap.add_argument("--art", choices=(*ARTEN, "alle"), default="alle")
    ap.add_argument("--limit", type=int, default=0, help="höchstens so viele je Art (0 = alle)")
    ap.add_argument("--abstand", type=float, default=1.2, help="Sekunden zwischen Downloads")
    ap.add_argument("--ausfuehren", action="store_true",
                    help="wirklich schreiben (Vorgabe: Trockenlauf)")
    args = ap.parse_args(argv)

    try:
        import pymupdf  # noqa: F401, PLC0415 — ohne es läse der Lauf mit pypdf NEU, sinnlos
    except ImportError:
        print("PyMuPDF fehlt in diesem venv — Abbruch. pip install pymupdf -c constraints.txt",
              file=sys.stderr)
        return {"abgebrochen": "pymupdf fehlt"}

    daten_dir = args.db.parent
    stopp = Stopp(daten_dir)
    fortschritt_pfad = daten_dir / FORTSCHRITT
    erledigt = _fortschritt_lesen(fortschritt_pfad)
    arten = ARTEN if args.art == "alle" else (args.art,)
    print(("AUSFÜHREN — es wird geschrieben" if args.ausfuehren else
           "TROCKENLAUF — es wird nichts geschrieben") + f" ({args.db})", flush=True)

    store = CouncilStore(args.db)
    bericht: dict = {}
    beispiele: dict[str, list] = collections.defaultdict(list)
    try:
        for art in arten:
            alle = kandidaten(store, art)
            offen = [z for z in alle if str(z["id"]) not in erledigt[art]]
            liste = offen[:args.limit] if args.limit else offen
            k = collections.Counter(bestand=len(alle), offen=len(offen))
            t0 = time.monotonic()
            print(f"== {art}: {len(alle)} im Bestand, {len(offen)} offen, prüfe {len(liste)}",
                  flush=True)
            for i, z in enumerate(liste):
                grund = stopp.grund()
                if grund:
                    print(f"   Halt: {grund.text}", flush=True)
                    k["angehalten"] = 1
                    break
                try:
                    antwort = _session.get(z["url"], timeout=90)
                    antwort.raise_for_status()
                    e = pruefen(store, art, z, antwort.content)
                except Exception as fehler:  # noqa: BLE001 — ein PDF, nicht der Lauf
                    k["fehler"] += 1
                    if len(beispiele[f"{art}:fehler"]) < 5:
                        beispiele[f"{art}:fehler"].append(f"{z['id']}: {fehler}"[:160])
                    time.sleep(args.abstand)
                    continue
                k["geprueft"] += 1
                k["risse_vorher"] += e["risse_vorher"]
                k["risse_nachher"] += e["risse_nachher"]
                if e["gesperrt"] and e["gesperrt"].startswith("unverändert"):
                    k["unveraendert" if e["gesperrt"] == "unverändert" else "nur_leerraum"] += 1
                elif e["gesperrt"]:
                    k["gesperrt"] += 1
                    schluessel = e["gesperrt"].split(" ")[0]
                    k[f"gesperrt:{schluessel}"] += 1
                    if len(beispiele[f"{art}:gesperrt"]) < 8:
                        beispiele[f"{art}:gesperrt"].append(f"{z['id']}: {e['gesperrt']}")
                else:
                    k["wuerde_geaendert" if not args.ausfuehren else "geschrieben"] += 1
                    if args.ausfuehren:
                        schreiben(store, art, z, e)
                if args.ausfuehren:
                    # Auch Unverändertes und Gesperrtes gilt als erledigt — sonst
                    # lüde jeder Folgelauf sie erneut. Die Gesperrten stehen im
                    # Bericht; wer sie nachholen will, löscht die Fortschrittsdatei.
                    erledigt[art].add(str(z["id"]))
                    _fortschritt_schreiben(fortschritt_pfad, erledigt)
                if (i + 1) % 25 == 0:
                    print(f"   {i + 1}/{len(liste)}: {dict(k)}", flush=True)
                time.sleep(args.abstand)
            dauer = time.monotonic() - t0
            k["sekunden"] = round(dauer)
            zahlen: dict = dict(k)
            if k["geprueft"]:
                je_dokument = dauer / max(1, k["geprueft"] + k["fehler"])
                zahlen["hochrechnung_offen_stunden"] = round(je_dokument * len(offen) / 3600, 1)
            bericht[art] = zahlen
            print(f"   {art}: {zahlen}", flush=True)
        if args.ausfuehren and any(b.get("geschrieben") for b in bericht.values()):
            n = store.rebuild_fts()
            print(f"Suchindex neu gebaut: {n} Beschlüsse", flush=True)
    finally:
        store.close()
    for name, liste in beispiele.items():
        print(f"-- {name}: {liste}")
    print(json.dumps(bericht, ensure_ascii=False))
    return bericht


if __name__ == "__main__":
    main()
