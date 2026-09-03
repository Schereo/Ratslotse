"""Kredite und Zinsen: die Unterrichtungen des Rates nach der Kreditrichtlinie.

Liest aus dem eigenen Bestand — Vorlagen-Volltexte in ``council_templates``
(``check_protocols`` holt sie) —, nicht aus dem Netz. Je Vorlage eine
Unterrichtung mit Berichtszeitraum und Zinsersparnis, je nummeriertem Posten
Art, Schuldner, Betrag, Zinssatz, Zinsbindung (``council/loans.py``).

    python scripts/ingest_kredite.py [--trockenlauf] [--schrumpf-erlauben]
"""
import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from council import finanzquellen, herkunft as h, loans  # noqa: E402
from council.store import CouncilStore  # noqa: E402
from council.vorlagen import fetch_vorlage  # noqa: E402

COUNCIL_DB = ROOT / "data" / "council.sqlite"
LABEL = "Unterrichtung des Rates über Kreditaufnahmen, Derivatabschlüsse und Umschuldungen"


def _lauf_herkunft(result: dict) -> h.Herkunft:
    years = [n["year"] for n in result["notices"]]
    spanne = f"{min(years)}–{max(years)}" if years else "—"
    return h.Herkunft(
        kind="ris", url="https://buergerinfo.oldenburg.de/vo040.asp", label=LABEL,
        citation=loans.FUNDSTELLE, as_of=f"Berichtsjahre {spanne}",
        probe=[loans.ZEITRAUM, loans.POSTEN_BETRAG],
        probe_result=loans.probennachweis(result))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", type=Path, default=COUNCIL_DB)
    ap.add_argument("--trockenlauf", action="store_true")
    ap.add_argument("--schrumpf-erlauben", action="store_true")
    ap.add_argument("--kein-download", action="store_true",
                    help="fehlende Vorlagentexte nicht aus dem RIS nachladen")
    args = ap.parse_args()

    store = CouncilStore(args.db)
    try:
        zeilen = store.kreditunterrichtungen()
        # Die Unterrichtungen von 2018 bis 2022 liegen im Bestand OHNE Text:
        # `check_protocols` holt Vorlagen erst seit 2022 mit Volltext, und der
        # Vorlagen-Backfill kennt keine Datenart. Also holt dieser Lauf, was
        # ihm fehlt — einmal, danach steht der Text in `council_templates`.
        ohne_text = [z for z in zeilen
                     if loans.erkenne(z.get("title")) and not (z.get("raw_text") or "").strip()
                     and z.get("kvonr")]
        if ohne_text and not args.kein_download and not args.trockenlauf:
            geholt = 0
            for z in ohne_text:
                v = fetch_vorlage(int(z["kvonr"]))
                if v and (v.get("raw_text") or "").strip():
                    store.save_vorlage(v)
                    geholt += 1
            print(f"Vorlagentexte nachgeladen: {geholt} von {len(ohne_text)}", flush=True)
            zeilen = store.kreditunterrichtungen()
        elif ohne_text:
            print(f"{len(ohne_text)} Unterrichtung(en) ohne Volltext (Nachladen: ohne "
                  f"--kein-download/--trockenlauf)", flush=True)
        result = loans.lies(zeilen)
        notices, items = result["notices"], result["items"]
        print(f"Unterrichtungen: {len(notices)} ({sum(n['none_reported'] for n in notices)} ohne Vorgang), "
              f"Posten: {len(items)}, verworfen: {len(result['rejected'])}")
        for v in result["rejected"]:
            print(f"  verworfen: {v['template_number']} — {v['reason']}", file=sys.stderr)
        for n in notices:
            zins = [f"{i['rate_pct']:.2f} %" for i in items
                    if i["template_number"] == n["template_number"] and i.get("rate_pct") is not None]
            print(f"  {n['period_from']}..{n['period_to']}  {n['template_number']}  "
                  f"{n['items']} Posten" + (f"  Zins {', '.join(zins)}" if zins else "")
                  + (f"  Ersparnis {n['interest_saving']:,.0f} €" if n.get("interest_saving") else ""))
        if args.trockenlauf:
            print("Trockenlauf — nichts gespeichert.")
            return 0
        p = finanzquellen.Protokoll()
        if not finanzquellen.bestandsschutz(
                p, "Kreditunterrichtungen", len(store.get_loan_notices()), len(notices),
                schuetzen=not args.schrumpf_erlauben):
            for row in p.warnungen:
                print(row.strip(), file=sys.stderr)
            print("ABBRUCH: Der vorhandene Bestand bleibt unangetastet. Wenn das "
                  "Schrumpfen Absicht ist: --schrumpf-erlauben.", file=sys.stderr)
            return 1
        for n in notices:
            n["herkunft"] = h.Herkunft(
                kind="ris", document_id=n.get("document_id"),
                url=n.get("document_url") or "https://buergerinfo.oldenburg.de/vo040.asp",
                label=f"{LABEL} — Vorlage {n['template_number']}",
                citation=loans.FUNDSTELLE,
                as_of=f"Berichtszeitraum {n['period_from']} bis {n['period_to']}",
                probe=n["probes"],
                probe_result=(f"{n['items']} Posten mit Betrag in der Überschrift"
                              if n["items"] else "Berichtszeitraum ohne Vorgang"))
        n_ = store.save_loan_notices(notices, items, _lauf_herkunft(result))
        print(f"  gespeichert: {n_} Unterrichtungen, {len(items)} Posten")
        store.herkunft_aufraeumen()
        luecken = {t: k for t, k in store.herkunft_luecken().items() if t.startswith("council_loan")}
        if luecken:
            print(f"WARNUNG: Zeilen ohne Herkunft: {luecken}", file=sys.stderr)
    finally:
        store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
