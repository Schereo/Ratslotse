#!/usr/bin/env python3
"""Die beiden Steuertabellen des Jahrbuchs einlesen — 1103 und 1105.

* **1103** — je Steuerart der Haushaltsplan neben dem Rechnungsergebnis.
  Die einzige Stelle, an der wir die Plan-Seite je Steuerart bekommen.
* **1105** — die Realsteuer-Hebesätze seit 1980, nur die Änderungsjahre.

Beide landen auf dem Steuer-Steckbrief (``/haushalt/steuer?art=…``); was sie
enthalten und woran sie geprüft werden, steht im Kopf von
``council/steuertabellen.py``.

Warum dieser Lauf das Archiv liest — und nicht nur die Live-Datei
------------------------------------------------------------------
**Tabelle 1103 führt nur drei Jahrgänge.** Erscheint die Ausgabe 2026, fällt
2023 heraus, und die Stadt führt kein Jahrbuch-Archiv: Die alte Adresse ist
dann ein 404, und das Internet Archive hat vom Statistik-Verzeichnis null
Schnappschüsse. Wer nur live liest, hat für immer drei Jahre.

Seit #603 sichert ``scripts/archive_statistik.py`` täglich jede Ausgabe. Weil
der Dateiname den Jahrgang trägt (``1103-2025-AZ.pdf``), ist jede Ausgabe ein
eigener Ordner — die alten bleiben stehen. Dieser Lauf liest **alle**, älteste
zuerst, und legt ihre Jahrgänge zusammen. Die Reihe wächst damit um einen
Jahrgang pro Jahr, statt bei dreien zu bleiben.

Bei gleichem Jahrgang gewinnt die **jüngere** Ausgabe. Das ist die richtige
Richtung: Sie trägt das abgerechnete Ergebnis, wo die ältere noch ein
vorläufiges auswies.

Jede Ausgabe bekommt ihre **eigene Herkunft** — sie ist ein eigenes Dokument
mit eigener Adresse. Wer im Beleg nachschlägt, soll das Heft finden, in dem
seine Zahl wirklich steht, nicht das neueste.

Was ohne Archiv passiert
-------------------------
Nichts Schlimmes: Der Lauf lädt die Live-Datei und liest sie allein. Er sagt
dann, dass er das tut. Auf einer frisch geklonten Maschine und in der CI ist
das der Normalfall.

Warum von Hand und nicht per Cron
----------------------------------
Wie bei den Tabellen 1102, 1107 und 1108: Die Dateien erscheinen einmal
jährlich und tragen den Jahrgang im Namen, in einer Schreibweise, die sich
nicht vorhersagen lässt. Deshalb sucht dieser Lauf die Links auf der
Jahrbuch-Übersichtsseite, statt eine Adresse hochzuzählen. Der Web-Dienst lädt
zu keinem Zeitpunkt etwas nach; er liest, was hier gespeichert wurde.

Aufruf::

    python scripts/ingest_steuertabellen.py                  # Archiv + Live
    python scripts/ingest_steuertabellen.py --nur-archiv     # ohne Netz
    python scripts/ingest_steuertabellen.py --pdf-1103 a.pdf --pdf-1105 b.pdf
    python scripts/ingest_steuertabellen.py --trockenlauf    # nur zeigen
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path
from urllib.parse import urljoin

import requests
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from council import archiv  # noqa: E402
from council import finanzquellen  # noqa: E402
from council import herkunft as h  # noqa: E402
from council import steuertabellen as stt  # noqa: E402
from council.store import CouncilStore  # noqa: E402

COUNCIL_DB = Path(os.environ.get("COUNCIL_DB") or ROOT / "data" / "council.sqlite")
_UA = {"User-Agent": "Ratslotse/1.0 (ratslotse.de; Haushalts-Bereich)"}

#: Die Steuerart, an der die Sprungjahr-Probe hängt (council/steuertabellen.py).
GRUNDSTEUER = "Grundsteuer A+B"


def pdf_text(pfad: Path) -> str:
    """Volltext aller Seiten. Beide Tabellen stehen je auf einer."""
    return "\n".join((s.extract_text() or "") for s in PdfReader(str(pfad)).pages)


def link_suchen(muster) -> str | None:
    """Den aktuellen Link auf eine Tabelle von der Jahrbuch-Seite holen.

    ``None``, wenn die Seite ihn nicht (mehr) führt — dann greift die
    hinterlegte Adresse, und der Lauf sagt, dass er das tut."""
    antwort = requests.get(stt.JAHRBUCH_URL, headers=_UA, timeout=120)
    antwort.raise_for_status()
    treffer = muster.search(antwort.text)
    return urljoin(stt.JAHRBUCH_URL, treffer.group(1)) if treffer else None


def ist_reihe(store: CouncilStore) -> tuple[dict, dict]:
    """``council_steuern`` in die beiden Formen bringen, die die Proben brauchen.

    ``({jahr: {art: euro}}, {jahr: grundsteuer_euro})`` — die erste für den
    Ist-Abgleich von 1103, die zweite für die Sprungjahr-Probe von 1105."""
    alle: dict[int, dict[str, float]] = {}
    for zeile in store.get_steuereinnahmen():
        if zeile.get("betrag") is None:
            continue
        alle.setdefault(zeile["jahr"], {})[zeile["art"]] = float(zeile["betrag"])
    grundsteuer = {j: w[GRUNDSTEUER] for j, w in alle.items() if GRUNDSTEUER in w}
    return alle, grundsteuer


def _ausgaben(bereich_muster: str, live_url: str | None, live_text: str | None,
              archiv_pfad, sagen) -> list[tuple[str, str]]:
    """Alle Fassungen einer Tabelle als ``[(quellenname, text)]``, älteste zuerst.

    Erst das Archiv (je Ausgabe ihre neueste Fassung), dann die Live-Datei —
    damit die jüngste Auskunft am Ende steht und beim Zusammenlegen gewinnt.
    """
    aus: list[tuple[str, str]] = []
    for pfad in archiv.neueste_je_datei(archiv_pfad, "jahrbuch", bereich_muster):
        # Der Ordnername ist der Dateiname der Quelle — er trägt den Jahrgang.
        name = pfad.parent.name
        try:
            aus.append((name, pdf_text(pfad)))
        except Exception as exc:                            # noqa: BLE001
            sagen(f"  Archiv-Fassung {name} nicht lesbar: {exc}")
    if aus:
        sagen(f"  Archiv: {len(aus)} Ausgabe(n) — "
              f"{', '.join(n for n, _ in aus)}")
    else:
        sagen("  Archiv: keine Ausgabe gesichert (das ist kein Fehler — "
              "auf einer frischen Maschine ist das der Normalfall)")
    if live_text is not None:
        name = archiv.dateiname(live_url) if live_url else "Live-Datei"
        # Die Live-Datei ersetzt eine gleichnamige Archiv-Fassung, statt
        # danebenzustehen: Sie ist dieselbe Adresse, nur womöglich frischer.
        aus = [(n, t) for n, t in aus if n != name]
        aus.append((name, live_text))
        sagen(f"  Live: {name}")
    return aus


def _herkunft_1103(name: str, url: str | None, jahre: list[int],
                   proben: list[str], nachweis: str) -> h.Herkunft:
    spanne = (f"{jahre[0]}–{jahre[-1]}" if len(jahre) > 1 else str(jahre[0]))
    return h.Herkunft(
        art="stadt",
        url=url or stt.TABELLE_1103_URL,
        label=f"Statistisches Jahrbuch der Stadt Oldenburg, Tabelle 1103 ({name})",
        fundstelle=(
            "Kapitel 11 „Verwaltung und Finanzen“, Tabelle 1103 „Steuern und "
            "steuerähnliche Erträge sowie allgemeine Finanzzuweisungen und "
            "Umlagen“ — je Steuerart und Jahr zwei Spalten: der Ansatz nach dem "
            "Haushaltsplan und das Rechnungsergebnis. Jede Ausgabe der Tabelle "
            "führt nur drei Jahrgänge"),
        stand=f"Haushaltsjahre {spanne} · {stt.ABGRENZUNG_1103}",
        probe=proben,
        probe_ergebnis=nachweis)


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Steuertabellen 1103 und 1105 des Jahrbuchs einlesen")
    ap.add_argument("--db", default=str(COUNCIL_DB))
    ap.add_argument("--archiv", default=None,
                    help="Archivordner (Vorgabe: ARCHIV_DIR oder data/archiv)")
    ap.add_argument("--pdf-1103", help="lokale Datei statt Download")
    ap.add_argument("--pdf-1105", help="lokale Datei statt Download")
    ap.add_argument("--nur-archiv", action="store_true",
                    help="nichts laden, nur gesicherte Ausgaben lesen")
    ap.add_argument("--trockenlauf", action="store_true",
                    help="alles rechnen und zeigen, nichts speichern")
    ap.add_argument("--schrumpf-erlauben", action="store_true",
                    help="einen deutlich kleineren Jahrgangssatz trotzdem "
                         "speichern (bewusster Handgriff, s. bestandsschutz)")
    args = ap.parse_args()

    def sagen(text: str) -> None:
        print(text)

    store = CouncilStore(Path(args.db))
    try:
        alle_ist, grundsteuer = ist_reihe(store)
        if not alle_ist:
            print("ABBRUCH: `council_steuern` ist leer. Beide Tabellen hängen "
                  "für die Prüfung ihrer Jahresbeschriftung an dieser Reihe — "
                  "ohne sie käme nichts Geprüftes herein. Erst "
                  "scripts/ingest_finanzen_opendata.py laufen lassen.",
                  file=sys.stderr)
            return 1
        print(f"Ist-Reihe (Tabelle 1104): {min(alle_ist)}–{max(alle_ist)}, "
              f"{len(grundsteuer)} Jahre mit Grundsteuer")

        with tempfile.TemporaryDirectory() as tmp:
            def live(kennung: str, muster, vorgabe: str,
                     lokal: str | None) -> tuple[str | None, str | None]:
                """Die Live-Fassung holen — oder ehrlich melden, dass nicht."""
                if lokal:
                    return None, pdf_text(Path(lokal))
                if args.nur_archiv:
                    return None, None
                try:
                    url = link_suchen(muster)
                    if url:
                        print(f"  Link von der Jahrbuch-Seite: {url}")
                    else:
                        url = vorgabe
                        print(f"  HINWEIS: Die Übersichtsseite führt keinen "
                              f"Link auf {kennung} mehr — es gilt die "
                              f"hinterlegte Adresse: {url}")
                    antwort = requests.get(url, headers=_UA, timeout=120)
                    antwort.raise_for_status()
                    pfad = Path(tmp) / f"{kennung}.pdf"
                    pfad.write_bytes(antwort.content)
                    return url, pdf_text(pfad)
                except Exception as exc:                    # noqa: BLE001
                    print(f"  Live-Abruf für {kennung} gescheitert ({exc}) — "
                          f"es gilt allein, was im Archiv liegt.",
                          file=sys.stderr)
                    return None, None

            # ---------------- Tabelle 1103 ------------------------------
            print("\nTabelle 1103 — Plan neben Ist je Steuerart")
            url_1103, text_1103 = live("1103", stt.LINK_1103,
                                       stt.TABELLE_1103_URL, args.pdf_1103)
            ausgaben = _ausgaben(stt.ARCHIV_1103, url_1103, text_1103,
                                 args.archiv, sagen)
            if not ausgaben:
                print("ABBRUCH: keine einzige Ausgabe von 1103 verfügbar — "
                      "weder im Archiv noch live.", file=sys.stderr)
                return 1

            gelesen: list[tuple[str, list[dict]]] = []
            proben_je_ausgabe: dict[str, list[str]] = {}
            urls: dict[str, str | None] = {}
            for name, text in ausgaben:
                ergebnis = stt.lies_1103(text, alle_ist)
                if ergebnis["abbruch"]:
                    print(f"  {name}: {ergebnis['abbruch']}", file=sys.stderr)
                    continue
                for v in ergebnis["verworfen"]:
                    print(f"  {name}: VERWORFEN {v['jahr']} — {v['grund']}",
                          file=sys.stderr)
                if not ergebnis["zeilen"]:
                    continue
                gelesen.append((name, ergebnis["zeilen"]))
                proben_je_ausgabe[name] = ergebnis["proben"]
                urls[name] = url_1103 if text is text_1103 else None
                print(f"  {name}: {len(ergebnis['zeilen'])} Zeilen, "
                      f"Jahrgänge {ergebnis['jahre']}")

            zeilen_1103 = stt.zusammenlegen(
                gelesen, lambda z: (z["jahr"], z["art"]))
            jahre_1103 = sorted({z["jahr"] for z in zeilen_1103})
            print(f"  zusammengelegt: {len(zeilen_1103)} Zeilen · "
                  f"Jahrgänge {jahre_1103}")

            # ---------------- Tabelle 1105 ------------------------------
            print("\nTabelle 1105 — Hebesätze seit 1980")
            url_1105, text_1105 = live("1104-1105", stt.LINK_1105,
                                       stt.TABELLE_1105_URL, args.pdf_1105)
            ausgaben5 = _ausgaben(stt.ARCHIV_1105, url_1105, text_1105,
                                  args.archiv, sagen)
            gelesen5: list[tuple[str, list[dict]]] = []
            proben_1105: list[str] = []
            sprung = {"bestanden": [], "gerissen": [], "nicht_pruefbar": []}
            for name, text in ausgaben5:
                ergebnis = stt.lies_1105(text, grundsteuer)
                if ergebnis["abbruch"]:
                    print(f"  {name}: {ergebnis['abbruch']}", file=sys.stderr)
                    continue
                gelesen5.append((name, ergebnis["zeilen"]))
                proben_1105 = ergebnis["proben"]
                sprung = ergebnis["sprungjahre"]
                print(f"  {name}: {len(ergebnis['zeilen'])} Zeilen")
            zeilen_1105 = stt.zusammenlegen(
                gelesen5, lambda z: (z["jahr"], z["art"]))
            jahre_1105 = sorted({z["jahr"] for z in zeilen_1105})
            if zeilen_1105:
                print(f"  zusammengelegt: {len(zeilen_1105)} Zeilen · "
                      f"{len(jahre_1105)} Änderungsjahre {jahre_1105}")
                for e in sprung["bestanden"]:
                    print(f"    Sprungjahr {e['jahr']}: Hebesatz "
                          f"{e['hebesatz_vorher']}→{e['hebesatz_nachher']}, "
                          f"Aufkommen im Jahr {e['im_jahr'] * 100:+.2f} %, "
                          f"danach {e['danach'] * 100:+.2f} %")
                for e in sprung["nicht_pruefbar"]:
                    print(f"    nicht prüfbar {e['jahr']}: {e['grund']}")

            if not zeilen_1103 and not zeilen_1105:
                print("ABBRUCH: keine der beiden Tabellen hat eine Probe "
                      "bestanden.", file=sys.stderr)
                return 1

            if args.trockenlauf:
                print("\nTrockenlauf — nichts gespeichert.")
                return 0

            # ---------------- Bestandsschutz ----------------------------
            p = finanzquellen.Protokoll()
            heil = True
            if zeilen_1103:
                heil &= finanzquellen.bestandsschutz(
                    p, "Steuerplan (1103)", len(store.steuerplan_jahre()),
                    len(jahre_1103), schuetzen=not args.schrumpf_erlauben)
            if zeilen_1105:
                heil &= finanzquellen.bestandsschutz(
                    p, "Hebesätze (1105)", len(store.hebesatz_jahre()),
                    len(jahre_1105), schuetzen=not args.schrumpf_erlauben)
            for zeile in p.zeilen:
                print(zeile.strip())
            if not heil:
                for zeile in p.warnungen:
                    print(zeile.strip(), file=sys.stderr)
                print("ABBRUCH: Der vorhandene Bestand bleibt unangetastet. "
                      "Wenn das Schrumpfen Absicht ist: --schrumpf-erlauben.",
                      file=sys.stderr)
                return 1

            # ---------------- Schreiben ---------------------------------
            #
            # Je AUSGABE eine Herkunft. Sie sind verschiedene Hefte mit
            # verschiedenen Adressen; wer im Beleg nachschlägt, soll das Heft
            # finden, in dem seine Zahl steht.
            geschrieben = 0
            nach_ausgabe: dict[str, list[dict]] = {}
            for zeile in zeilen_1103:
                nach_ausgabe.setdefault(zeile["ausgabe"], []).append(zeile)
            for name, teil in sorted(nach_ausgabe.items()):
                jahre = sorted({z["jahr"] for z in teil})
                proben = proben_je_ausgabe.get(name) or ["steuerplan_summenzeile"]
                nachweis = (
                    f"{len(jahre)} Jahrgänge ({jahre[0]}–{jahre[-1]}), "
                    f"bestanden: "
                    + ", ".join(stt.PROBEN_KURZ.get(n, n) for n in proben))
                geschrieben += store.save_steuerplan(
                    teil, _herkunft_1103(name, urls.get(name), jahre,
                                         proben, nachweis))
                print(f"  1103 {name}: {len(teil)} Zeilen, "
                      f"Jahrgänge {jahre[0]}–{jahre[-1]}")

            if zeilen_1105:
                gemessen = ", ".join(
                    f"{e['jahr']} ({e['im_jahr'] * 100:+.1f} % im Jahr gegen "
                    f"{e['danach'] * 100:+.1f} % danach)"
                    for e in sprung["bestanden"])
                nachweis5 = (
                    f"{len(jahre_1105)} Änderungsjahre "
                    f"({jahre_1105[0]}–{jahre_1105[-1]}), bestanden: "
                    + ", ".join(stt.PROBEN_KURZ.get(n, n) for n in proben_1105)
                    + (f"; Sprungjahr-Probe an der Aufkommensreihe für "
                       f"{gemessen}" if gemessen else "")
                    + (f"; nicht prüfbar: "
                       + ", ".join(str(e["jahr"])
                                   for e in sprung["nicht_pruefbar"])
                       if sprung["nicht_pruefbar"] else ""))
                letzte_ausgabe = zeilen_1105[-1]["ausgabe"]
                geschrieben += store.save_hebesaetze(zeilen_1105, h.Herkunft(
                    art="stadt",
                    url=url_1105 or stt.TABELLE_1105_URL,
                    label="Statistisches Jahrbuch der Stadt Oldenburg, "
                          f"Tabelle 1105 ({letzte_ausgabe})",
                    fundstelle=(
                        "Kapitel 11 „Verwaltung und Finanzen“, Tabelle 1105 "
                        "„Realsteuer-Hebesätze in Prozent seit 1980“ — je "
                        "Änderungsjahr die Hebesätze für Grundsteuer A, "
                        "Grundsteuer B und Gewerbesteuer. Die Tabelle führt "
                        "nach eigener Fußnote nur die Jahre, in denen sich ein "
                        "Satz geändert hat"),
                    stand=f"Änderungsjahre {jahre_1105[0]}–{jahre_1105[-1]} · "
                          f"{stt.ABGRENZUNG_1105}",
                    probe=proben_1105,
                    probe_ergebnis=nachweis5))
                print(f"  1105: {len(zeilen_1105)} Zeilen")

            print(f"\ngespeichert: {geschrieben} Zeilen")

        store.herkunft_aufraeumen()
        luecken = {t: n for t, n in store.herkunft_luecken().items()
                   if t in ("council_steuerplan", "council_hebesaetze")}
        if luecken:
            print(f"WARNUNG: Zeilen ohne Herkunft: {luecken}", file=sys.stderr)
    finally:
        store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
