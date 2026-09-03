"""Liquiditätsstand: die monatlichen Grafiken als Zahlenreihe.

Liest die Anlagen der Vorlagen „Liquiditätsstand" (``council/liquidity.py``).
Anlagen ohne Textauszug lädt der Lauf selbst — bis 2021 heißen sie nur
„Anlage", der Volltext-Lauf mit Label-Mustern findet sie nicht — und legt den
Text in ``council_attachments`` ab, damit er beim nächsten Mal da ist.

    python scripts/ingest_liquiditaet.py [--trockenlauf] [--schrumpf-erlauben] [--kein-download]
"""
import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from council import finanzquellen, herkunft as h, liquidity  # noqa: E402
from council.store import CouncilStore  # noqa: E402
from council.vorlagen import _pdf_text  # noqa: E402

COUNCIL_DB = ROOT / "data" / "council.sqlite"
LABEL = "Grafik „Liquiditätsstand zum Monatsende“ (Anlage der Vorlage Liquiditätsstand)"


def _lauf_herkunft(result: dict) -> h.Herkunft:
    rows = result["rows"]
    spanne = f"{rows[0]['month']} bis {rows[-1]['month']}" if rows else "—"
    return h.Herkunft(
        kind="ris", url="https://buergerinfo.oldenburg.de/vo040.asp", label=LABEL,
        citation=liquidity.FUNDSTELLE, as_of=f"Monate {spanne}",
        probe=[liquidity.WERTZAHL, liquidity.UEBERLAPPUNG],
        probe_result=liquidity.probennachweis(result))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", type=Path, default=COUNCIL_DB)
    ap.add_argument("--trockenlauf", action="store_true")
    ap.add_argument("--schrumpf-erlauben", action="store_true")
    ap.add_argument("--kein-download", action="store_true",
                    help="nur vorhandene Textauszüge lesen, keine Anlagen laden")
    args = ap.parse_args()

    store = CouncilStore(args.db)
    try:
        anlagen = store.liquiditaetsanlagen()
        geladen = 0
        if not args.kein_download:
            for a in anlagen:
                if (a.get("raw_text") or "").strip() or not a.get("url"):
                    continue
                try:
                    text, n = _pdf_text(a["url"])
                except Exception as fehler:  # noqa: BLE001 — ein PDF, nicht der Lauf
                    print(f"  nicht geladen: {a['template_number']} ({a['document_id']}): {fehler}",
                          file=sys.stderr)
                    continue
                a["raw_text"] = text
                geladen += 1
                if not args.trockenlauf:
                    store.anlagentext_nachtragen(a["document_id"], text, n)
        result = liquidity.lies(anlagen)
        rows = result["rows"]
        print(f"Anlagen: {len(anlagen)} (davon {geladen} jetzt geladen), Grafiken gelesen: "
              f"{result['probes']['grafiken']}, Monate: {len(rows)}, "
              f"verworfen: {len(result['rejected'])}, strittig: {len(result['strittig'])}")
        for s in result["strittig"]:
            print(f"  korrigiert: {s['month']} — {s['values']} (jüngster Wert gilt)", file=sys.stderr)
        if rows:
            print(f"  {rows[0]['month']} … {rows[-1]['month']}; zuletzt "
                  f"{rows[-1]['amount'] / 1e6:.1f} Mio. € (Stichtag {rows[-1]['as_of']})")
        if args.trockenlauf:
            print("Trockenlauf — nichts gespeichert.")
            return 0
        p = finanzquellen.Protokoll()
        if not finanzquellen.bestandsschutz(
                p, "Liquiditätsmonate", len(store.get_liquidity()), len(rows),
                schuetzen=not args.schrumpf_erlauben):
            for row in p.warnungen:
                print(row.strip(), file=sys.stderr)
            print("ABBRUCH: Der vorhandene Bestand bleibt unangetastet. Wenn das "
                  "Schrumpfen Absicht ist: --schrumpf-erlauben.", file=sys.stderr)
            return 1
        for r in rows:
            r["herkunft"] = h.Herkunft(
                kind="ris", document_id=r.get("document_id"),
                url=r.get("url") or "https://buergerinfo.oldenburg.de/vo040.asp",
                label=f"{LABEL} — Vorlage {r['template_number']}",
                citation=liquidity.FUNDSTELLE, as_of=f"Stichtag {r['as_of']}",
                probe=r["probes"],
                probe_result=(f"von der Verwaltung korrigiert: früher {r['revised_from'] / 1e6:.1f} Mio. €"
                              if r.get("revised_from") is not None
                              else f"Wert in {r['confirmations']} Grafiken gleich"
                              if r["confirmations"] > 1 else "Wertzahl der Grafik ging auf"))
        n_ = store.save_liquidity(rows, _lauf_herkunft(result))
        print(f"  gespeichert: {n_} Monate")
        store.herkunft_aufraeumen()
        luecken = {t: k for t, k in store.herkunft_luecken().items() if t == "council_liquidity"}
        if luecken:
            print(f"WARNUNG: Zeilen ohne Herkunft: {luecken}", file=sys.stderr)
    finally:
        store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
