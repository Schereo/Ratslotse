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
        --kfa kfa2026.xlsx --kfa-prior_year kfa2025.xlsx \\
        --realsteuer realsteuer2025.xlsx

    # oder direkt von der Adresse holen
    python scripts/ingest_staedtevergleich.py \\
        --kfa https://www.statistik.niedersachsen.de/download/227086 \\
        --kfa-prior_year https://www.statistik.niedersachsen.de/download/216492 \\
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
from council import steuerkraft as sk  # noqa: E402
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
    ap.add_argument("--kfa-prior_year", required=True,
                    help="derselbe Bericht ein Jahr früher — die Gegenprobe")
    ap.add_argument("--realsteuer", required=True,
                    help="Realsteuervergleich (Datei oder Adresse)")
    ap.add_argument("--jahrbuch-1103", default=None, metavar="JAHR:TEUR",
                    help="Gegenprobe: die Zeile „Finanzzuweisungen“ aus Tabelle "
                         "1103 des Statistischen Jahrbuchs, z. B. 2025:79787. "
                         "Weicht sie um mehr als 0,5 %% ab, wird nichts "
                         "geschrieben.")
    args = ap.parse_args()

    store = CouncilStore(Path(args.db))
    geschrieben = {"steuerkraft": 0, "realsteuern": 0, "finanzausgleich": 0}
    try:
        with tempfile.TemporaryDirectory() as tmp:
            ablage = Path(tmp)

            # --- Steuerkraft: zwei Jahrgänge, weil die Probe zwei braucht ---
            print("Kommunaler Finanzausgleich:")
            pfad_neu, url_neu = _holen(args.kfa, ablage)
            pfad_alt, _ = _holen(args.kfa_prior_year, ablage)
            neu = sv.lies_kfa(str(pfad_neu))
            alt = sv.lies_kfa(str(pfad_alt))
            print(f"  Ausgleichsjahr {neu.year} (Vorjahresspalte {neu.prior_year}), "
                  f"{len(neu.staedte)} Gemeinden, Stand {neu.stand}")

            probe = sv.probe_ueberlappung(alt, neu)
            print(f"  Zwei-Jahres-Überlappung: {probe['result']}")
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
                    label=f"Kommunaler Finanzausgleich {neu.year}, endgültig — "
                          f"Ergebnis- und Vergleichstabellen",
                    url=url_neu or QUELLEN_STAND.get(f"kfa{neu.year}"),
                    fundstelle="Blatt „ST_KR_MESS_VGL“ — Steuerkraftmesszahlen "
                               "je Gemeinde, zwei Ausgleichsjahre nebeneinander",
                    probe_result=probe["result"],
                    stand=neu.stand))
            print(f"  gespeichert: {geschrieben['steuerkraft']} Werte "
                  f"({len(sv.KREISFREIE_STAEDTE)} kreisfreie Städte)")

            # --- Die drei Komponenten der Zuweisung (Blatt 9a) --------------
            # Dieselbe Datei, zweites Blatt. Sie trägt die Komponente, die in
            # unserem Open-Data-Bestand fehlt: „Zuweisungen für Aufgaben des
            # übertragenen Wirkungskreises" (s. council/steuerkraft.py).
            print("Finanzausgleich, Komponenten (Blatt 9a):")
            zeilen_fa: list[dict] = []
            proben: list[str] = []
            for jahrgang in sk.lies_zuweisungen(str(pfad_neu)):
                probe_k = sk.probe_komponenten(jahrgang)
                print(f"  {probe_k['result']}")
                if not probe_k["ok"]:
                    for abw in probe_k["abweichungen"][:8]:
                        print(f"    ABWEICHUNG {abw['stadt']}: {abw['grund']}")
                    print("  ÜBERSPRUNGEN: Was seine Probe reißt, kommt nicht "
                          "in die Datenbank.")
                    continue
                zeilen_fa += sk.zeilen_finanzausgleich(jahrgang)
                proben.append(probe_k["result"])
                if args.jahrbuch_1103:
                    jahr_s, _, wert_s = args.jahrbuch_1103.partition(":")
                    if jahr_s.strip().isdigit() and int(jahr_s) == jahrgang.year:
                        probe_j = sk.probe_gegen_jahrbuch(jahrgang, float(wert_s))
                        print(f"  {probe_j['result']} "
                              f"— {'geht auf' if probe_j['ok'] else 'REISST'}")
                        if not probe_j["ok"]:
                            print("  ABBRUCH: Land und Stadt widersprechen sich.")
                            return 1
                        proben.append(probe_j["result"])
            if zeilen_fa:
                geschrieben["finanzausgleich"] = store.save_staedtevergleich(
                    "finanzausgleich", zeilen_fa,
                    h.Herkunft(
                        art="lsn",
                        probe=["kfa_komponentenprobe", "kfa_jahrbuchabgleich"],
                        label=f"Kommunaler Finanzausgleich {neu.year}, endgültig — "
                              f"Ergebnis- und Vergleichstabellen",
                        url=url_neu or QUELLEN_STAND.get(f"kfa{neu.year}"),
                        fundstelle="Blatt „9a“ — Schlüsselzuweisungen für "
                                   "Gemeinde- und Kreisaufgaben, Zuweisungen für "
                                   "Aufgaben des übertragenen Wirkungskreises und "
                                   "Finanzausgleichsumlage je kreisfreier Stadt",
                        probe_result=" · ".join(proben),
                        stand=neu.stand))
                print(f"  gespeichert: {geschrieben['finanzausgleich']} Werte")

            # --- Realsteuervergleich ---
            print("Realsteuervergleich:")
            pfad_rs, url_rs = _holen(args.realsteuer, ablage)
            rs = sv.lies_realsteuervergleich(str(pfad_rs))
            print(f"  Berichtsjahr {rs.year}, Stand {rs.stand or 'Erstausgabe'}")

            zeilen, verworfen = sv.zeilen_realsteuern(rs)
            for v in verworfen:
                print(f"    VERWORFEN {v['stadt']}: {v['grund']} — {v['result']}")
            if not zeilen:
                print("  ABBRUCH: keine einzige Stadt hat ihre Probe bestanden.")
                return 1
            geschrieben["realsteuern"] = store.save_staedtevergleich(
                "realsteuern", zeilen,
                h.Herkunft(
                    art="lsn", probe=["lsn_hebesatzprobe", "lsn_dreijahresmittel"],
                    label=f"Realsteuervergleich {rs.year} (Statistischer Bericht "
                          f"L II 7 / L II 9)",
                    url=url_rs or QUELLEN_STAND.get(f"realsteuer{rs.year}"),
                    fundstelle="Blatt 2.1 — Grundbeträge, Hebesätze und "
                               "Ist-Aufkommen je kreisfreier Stadt; Blatt 5.1 — "
                               "durchschnittliche Steuereinnahmekraft, drei Jahre",
                    probe_result=(f"{len(sv.KREISFREIE_STAEDTE) - len(verworfen)} "
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
