#!/usr/bin/env python3
"""Den Städtevergleich aus den beiden LSN-Tabellen einlesen.

Zwei Veröffentlichungen des Landesamts für Statistik Niedersachsen, beide
ohne Anmeldung abrufbar:

- **Kommunaler Finanzausgleich** (Blatt ``ST_KR_MESS_VGL``) — die
  Steuerkraftmesszahl je Gemeinde. Gebraucht werden **zwei** Jahrgänge: Der
  jüngere trägt die Zahlen, der ältere ist die Rechenprobe (jede Datei nennt
  zwei Jahre nebeneinander, und das ältere muss die Hauptspalte des
  Vorjahrgangs wiederholen).
- **Realsteuervergleich** (Blätter ``2_1`` und ``5_1``) — Hebesätze,
  Ist-Aufkommen je Einwohner und die Steuereinnahmekraft über drei Jahre.

Warum von Hand und nicht per Cron
---------------------------------
Beide Quellen erscheinen **einmal jährlich** (der Finanzausgleich endgültig
im Frühjahr, der Realsteuervergleich im Folgejahr des Berichtsjahres). Ein
täglicher Lauf holte 364-mal dieselbe Datei. Dazu kommt, dass die
Download-Adressen des LSN undurchsichtige Nummern tragen
(``/download/227086``) und die Nummer des nächsten Jahrgangs nicht
vorhersagbar ist — sie steht auf der Übersichtsseite und wird hier beim
jährlichen Lauf mitgegeben. Der Web-Dienst lädt zu keinem Zeitpunkt etwas
nach; er liest, was hier in die Datenbank geschrieben wurde.

Aufruf::

    # Dateien vorher laden (Nummern von der LSN-Übersichtsseite)
    python scripts/ingest_staedtevergleich.py \\
        --kfa kfa2026.xlsx --kfa-vorjahr kfa2025.xlsx \\
        --realsteuer realsteuer2025.xlsx

    # oder direkt von der Adresse holen
    python scripts/ingest_staedtevergleich.py \\
        --kfa https://www.statistik.niedersachsen.de/download/227086 \\
        --kfa-vorjahr https://www.statistik.niedersachsen.de/download/216492 \\
        --realsteuer https://www.statistik.niedersachsen.de/download/230730

Die Übersichtsseiten, auf denen die jeweils neuen Nummern stehen:

- ``statistik.niedersachsen.de/kommunaler-finanzausgleich/…-tabellen-214575.html``
- ``statistik.niedersachsen.de/…/realsteuervergleich_in_niedersachsen/…-197957.html``
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from council import herkunft as h  # noqa: E402
from council import staedtevergleich as sv  # noqa: E402
from council.store import CouncilStore  # noqa: E402

COUNCIL_DB = Path(os.environ.get("COUNCIL_DB") or ROOT / "data" / "council.sqlite")

#: Die Adressen, aus denen der Bestand vom 16.08.2026 stammt. Sie stehen hier
#: als Beleg, welche Ausgabe eingelesen wurde — **nicht** als Vorgabe für den
#: nächsten Jahrgang: Die Nummer ändert sich jedes Jahr und lässt sich nicht
#: hochzählen.
QUELLEN_STAND = {
    "kfa2026": "https://www.statistik.niedersachsen.de/download/227086",
    "kfa2025": "https://www.statistik.niedersachsen.de/download/216492",
    "realsteuer2025": "https://www.statistik.niedersachsen.de/download/230730",
}


def _holen(ort: str, ablage: Path) -> tuple[Path, str | None]:
    """Pfad oder Adresse → lokale Datei und (falls geladen) die Quell-Adresse.

    Der Content-Type des LSN ist irreführend (``application/vnd.ms-excel`` bei
    echten xlsx) — er wird deshalb nicht ausgewertet. Ob die Datei taugt,
    entscheidet der Parser.
    """
    if not ort.lower().startswith(("http://", "https://")):
        return Path(ort), None
    import requests

    antwort = requests.get(ort, timeout=120)
    antwort.raise_for_status()
    ziel = ablage / (ort.rstrip("/").rsplit("/", 1)[-1] + ".xlsx")
    ziel.write_bytes(antwort.content)
    print(f"  geladen: {ort} ({len(antwort.content):,} Bytes)".replace(",", "."))
    return ziel, ort


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Städtevergleich aus den LSN-Tabellen einlesen")
    ap.add_argument("--db", default=str(COUNCIL_DB))
    ap.add_argument("--kfa", required=True,
                    help="Kommunaler Finanzausgleich, JÜNGERER Jahrgang (Datei oder Adresse)")
    ap.add_argument("--kfa-vorjahr", required=True,
                    help="derselbe Bericht ein Jahr früher — die Gegenprobe")
    ap.add_argument("--realsteuer", required=True,
                    help="Realsteuervergleich (Datei oder Adresse)")
    args = ap.parse_args()

    store = CouncilStore(Path(args.db))
    geschrieben = {"steuerkraft": 0, "realsteuern": 0}
    try:
        with tempfile.TemporaryDirectory() as tmp:
            ablage = Path(tmp)

            # --- Steuerkraft: zwei Jahrgänge, weil die Probe zwei braucht ---
            print("Kommunaler Finanzausgleich:")
            pfad_neu, url_neu = _holen(args.kfa, ablage)
            pfad_alt, _ = _holen(args.kfa_vorjahr, ablage)
            neu = sv.lies_kfa(str(pfad_neu))
            alt = sv.lies_kfa(str(pfad_alt))
            print(f"  Ausgleichsjahr {neu.jahr} (Vorjahresspalte {neu.vorjahr}), "
                  f"{len(neu.staedte)} Gemeinden, Stand {neu.stand}")

            probe = sv.probe_ueberlappung(alt, neu)
            print(f"  Zwei-Jahres-Überlappung: {probe['ergebnis']}")
            if not probe["ok"]:
                for a in probe["abweichungen"][:10]:
                    print(f"    ABWEICHUNG {a['schluessel']} {a['stadt']}: "
                          f"{a['alt']} gegen {a['neu']}")
                print("  ABBRUCH: Die beiden Jahrgänge widersprechen sich. Es wird "
                      "nichts geschrieben — lieber keine Zahlen als falsche.")
                return 1

            zeilen = sv.zeilen_steuerkraft(neu)
            geschrieben["steuerkraft"] = store.save_staedtevergleich(
                "steuerkraft", zeilen,
                h.Herkunft(
                    art="lsn", probe="lsn_zweijahresueberlappung",
                    label=f"Kommunaler Finanzausgleich {neu.jahr}, endgültig — "
                          f"Ergebnis- und Vergleichstabellen",
                    url=url_neu or QUELLEN_STAND.get(f"kfa{neu.jahr}"),
                    fundstelle="Blatt „ST_KR_MESS_VGL“ — Steuerkraftmesszahlen "
                               "je Gemeinde, zwei Ausgleichsjahre nebeneinander",
                    probe_ergebnis=probe["ergebnis"],
                    stand=neu.stand))
            print(f"  gespeichert: {geschrieben['steuerkraft']} Werte "
                  f"({len(sv.KREISFREIE_STAEDTE)} kreisfreie Städte)")

            # --- Realsteuervergleich ---
            print("Realsteuervergleich:")
            pfad_rs, url_rs = _holen(args.realsteuer, ablage)
            rs = sv.lies_realsteuervergleich(str(pfad_rs))
            print(f"  Berichtsjahr {rs.jahr}, Stand {rs.stand or 'Erstausgabe'}")

            zeilen, verworfen = sv.zeilen_realsteuern(rs)
            for v in verworfen:
                print(f"    VERWORFEN {v['stadt']}: {v['grund']} — {v['ergebnis']}")
            if not zeilen:
                print("  ABBRUCH: keine einzige Stadt hat ihre Probe bestanden.")
                return 1
            geschrieben["realsteuern"] = store.save_staedtevergleich(
                "realsteuern", zeilen,
                h.Herkunft(
                    art="lsn", probe=["lsn_hebesatzprobe", "lsn_dreijahresmittel"],
                    label=f"Realsteuervergleich {rs.jahr} (Statistischer Bericht "
                          f"L II 7 / L II 9)",
                    url=url_rs or QUELLEN_STAND.get(f"realsteuer{rs.jahr}"),
                    fundstelle="Blatt 2.1 — Grundbeträge, Hebesätze und "
                               "Ist-Aufkommen je kreisfreier Stadt; Blatt 5.1 — "
                               "durchschnittliche Steuereinnahmekraft, drei Jahre",
                    probe_ergebnis=(f"{len(sv.KREISFREIE_STAEDTE) - len(verworfen)} "
                                    f"von {len(sv.KREISFREIE_STAEDTE)} Städten "
                                    f"vollständig geprüft"),
                    stand=rs.stand))
            print(f"  gespeichert: {geschrieben['realsteuern']} Werte, "
                  f"{len(verworfen)} verworfen")

        store.herkunft_aufraeumen()
        luecken = {t: n for t, n in store.herkunft_luecken().items()
                   if t == "council_staedtevergleich"}
        if luecken:
            print(f"WARNUNG: Zeilen ohne Herkunft: {luecken}")
    finally:
        store.close()

    print(f"Fertig: {geschrieben}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
