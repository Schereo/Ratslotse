#!/usr/bin/env python3
"""Holt die Geschäftsordnung des Rates und schreibt sie als geprüfte Datei.

**Wozu.** „Frag den Rat" und Lotti beantworten Verfahrensfragen — Redezeit,
Einwohnerfragestunde, Anträge, Abstimmungen — aus dem Wortlaut der
Geschäftsordnung (:mod:`council.rules_of_procedure`). Der Wortlaut liegt als
``council/rules_of_procedure.json`` im Repo, nicht in der Datenbank: Er ändert
sich einmal je Wahlperiode, und eine neue Fassung soll im PR als Diff zu sehen
sein, nicht still per Cron einlaufen. Dieselbe Erwägung wie bei
``kern/glossar.py`` und ``kern/erklaerwissen.py``.

**Was er NICHT tut: entscheiden, ob eine neue Fassung gilt.** Er liest das PDF
der Stadt und schreibt den Text. Beschluss, Vorlage und Ende der Wahlperiode
kommen von Hand (``--adopted``, ``--template``, ``--term-end``) — wer eine neue
Fassung einspielt, schaut ohnehin in den Ratsbeschluss. Ohne Angabe bleiben
die Werte der vorhandenen Datei stehen.

Aufrufe::

    python scripts/fetch_rules_of_procedure.py            # PDF laden, Datei schreiben
    python scripts/fetch_rules_of_procedure.py --pdf x.pdf  # aus lokaler Datei
    python scripts/fetch_rules_of_procedure.py --check    # nur prüfen: neue Lesefassung?

``--check`` vergleicht den Link der Stadt-Seite „Satzungen – Stadtrecht" mit
dem gespeicherten. Die Dateinamen tragen das Datum der Fassung
(``1.02_20210719.pdf``); eine neue Fassung heißt also anders.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
from datetime import date
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
ZIEL = WURZEL / "council" / "rules_of_procedure.json"

PDF_URL = ("https://www.oldenburg.de/fileadmin/oldenburg/Benutzer/Dateien/"
           "22_Rechtsamt/1.02_20210719.pdf")
LISTING_URL = ("https://www.oldenburg.de/startseite/rathaus/politik-verwaltung/"
               "stadtverwaltung/satzungen-stadtrecht.html")
#: Unter dieser Nummer führt die Stadt die Geschäftsordnung im Stadtrecht.
ORTSRECHT_NR = "1.02"
UA = "Ratslotse/1.0 (+https://ratslotse.de)"
TIMEOUT = (5, 30)

_KOPF_RE = re.compile(r"^(?:1\.02|Seite \d+ von \d+)$")
_TEIL_RE = re.compile(r"^(I|II|III|IV|V)\.\s*Abschnitt:\s*(.+)$")
_PARAGRAF_RE = re.compile(r"^§\s*(\d+[a-z]?)$")
#: „a) Unterbrechung der Sitzung," — ein Listenpunkt, kein Satzrest, auch
#: wenn er klein anfängt (§ 13 Abs. 1 läuft so über den Seitenumbruch).
_AUFZAEHLUNG_RE = re.compile(r"^[a-z]\)\s")
#: Das Aufzählungszeichen der Vorlage (Wingdings, Privatbereich).
_PUNKT = ""
_SATZENDE = (".", ":", ";", "!", "?")


def _gesperrt(text: str) -> str:
    """„R a t s a u s s c h ü s s e" → „Ratsausschüsse".

    Die Überschriften der Abschnitte sind gesperrt gesetzt: einzelne
    Buchstaben mit einem Leerzeichen dazwischen, Wörter mit drei."""
    teile = re.split(r"\s{2,}", text.strip())
    if all(re.fullmatch(r"(?:\S )+\S", t) for t in teile):
        return " ".join(t.replace(" ", "") for t in teile)
    return " ".join(text.split())


def _zeilen_fuegen(zeilen: list[str]) -> str:
    """Zeilen eines Blocks zu einem Absatz — Trennstriche am Zeilenende auflösen.

    „einzuberu-" + „fen" wird „einzuberufen"; „E-" + „Mail-Adresse" bleibt
    „E-Mail-Adresse" (Großbuchstabe danach heißt: echter Bindestrich).
    """
    text = ""
    for zeile in zeilen:
        zeile = zeile.strip()
        if not zeile:
            continue
        if not text:
            text = zeile
        elif text.endswith("-") and not text.endswith(" -") and zeile[:1].islower() \
                and not re.match(r"(?:und|oder|bzw)\b", zeile):
            text = text[:-1] + zeile
        elif text.endswith("-") and not text.endswith(" -"):
            text += zeile
        else:
            text += " " + zeile
    return " ".join(text.split())


def parse(seiten: list[str]) -> tuple[dict, list[dict]]:
    """Seitentexte (wie PyMuPDF sie liefert) → Kopf und Paragrafen.

    Der Kopf kommt von Seite 1 (Titel, Datum der Fassung), die Paragrafen von
    allen folgenden. Ein Block ist, was zwischen zwei Leerzeilen steht; ein
    Block, der über einen Seitenumbruch läuft und klein weitergeht, wird
    wieder zusammengesetzt.
    """
    kopf_zeilen = [z.strip() for z in seiten[0].splitlines() if z.strip()]
    kopf_zeilen = [z for z in kopf_zeilen if not _KOPF_RE.match(z)]
    # „G e s c h ä f t s o r d n u n g" + „für den Rat, … der Stadt Oldenburg (Oldb)"
    titel = f"{_gesperrt(kopf_zeilen[0])} {' '.join(kopf_zeilen[1].split())}"
    m = re.match(r"vom (\d{1,2})\. (\w+) (\d{4})", kopf_zeilen[2])
    if not m:
        raise ValueError(f"Datum der Fassung nicht gefunden: {kopf_zeilen[2]!r}")
    monate = ["januar", "februar", "märz", "april", "mai", "juni", "juli",
              "august", "september", "oktober", "november", "dezember"]
    fassung = date(int(m.group(3)), monate.index(m.group(2).lower()) + 1,
                   int(m.group(1))).isoformat()

    # Alle Zeilen ab Seite 2 mit ihrer Seitennummer, Kopfzeilen raus. Eine
    # Leerzeile wird zu "" — sie trennt Blöcke.
    zeilen: list[tuple[int, str]] = []
    for nr, seite in enumerate(seiten[1:], start=2):
        roh = [z.strip() for z in seite.splitlines()]
        roh = [z for z in roh if not _KOPF_RE.match(z)]
        # Seitenumbruch mitten im Satz: kein Trenner, wenn die letzte
        # Textzeile davor nicht endet und die nächste klein anfängt.
        if zeilen:
            letzte = next((z for _, z in reversed(zeilen) if z), "")
            erste = next((z for z in roh if z), "")
            if (letzte and not letzte.endswith(_SATZENDE) and erste[:1].islower()
                    and not _AUFZAEHLUNG_RE.match(erste)):
                while zeilen and not zeilen[-1][1]:
                    zeilen.pop()
                while roh and not roh[0]:
                    roh.pop(0)
        zeilen += [(nr, z) for z in roh]

    paragrafen: list[dict] = []
    teil = ""
    aktuell: dict | None = None
    block: list[str] = []
    bloecke: list[str] = []

    def block_schliessen() -> None:
        nonlocal block
        if block:
            text = _zeilen_fuegen(block)
            if text:
                bloecke.append(text)
        block = []

    def paragraf_schliessen() -> None:
        nonlocal aktuell, bloecke
        block_schliessen()
        if aktuell is not None:
            aktuell["text"] = "\n".join(bloecke)
            paragrafen.append(aktuell)
        aktuell, bloecke = None, []

    i = 0
    while i < len(zeilen):
        seite, zeile = zeilen[i]
        if (m := _TEIL_RE.match(zeile)):
            paragraf_schliessen()
            teil = _gesperrt(m.group(2))
            i += 1
            continue
        if (m := _PARAGRAF_RE.match(zeile)):
            paragraf_schliessen()
            # Die Überschrift ist die nächste nichtleere Zeile.
            j = i + 1
            while j < len(zeilen) and not zeilen[j][1]:
                j += 1
            aktuell = {"number": m.group(1), "title": " ".join(zeilen[j][1].split()),
                       "part": teil, "page": seite}
            i = j + 1
            continue
        if aktuell is None:
            i += 1
            continue
        if not zeile:
            block_schliessen()
        elif zeile == _PUNKT:
            block_schliessen()
            block.append("–")
        elif _AUFZAEHLUNG_RE.match(zeile) or zeile.startswith("- "):
            # Listenpunkte stehen teils ohne Leerzeile untereinander (§ 15
            # Abs. 4, § 23 Abs. 2) — jeder bekommt trotzdem seine Zeile.
            block_schliessen()
            block.append("– " + zeile[2:] if zeile.startswith("- ") else zeile)
        else:
            block.append(zeile)
        i += 1
    paragraf_schliessen()
    return {"title": titel, "version_date": fassung}, paragrafen


def lade_pdf(quelle: str | None) -> bytes:
    if quelle:
        return Path(quelle).read_bytes()
    import requests
    antwort = requests.get(PDF_URL, headers={"User-Agent": UA}, timeout=TIMEOUT)
    antwort.raise_for_status()
    return antwort.content


def seiten_aus_pdf(daten: bytes) -> list[str]:
    import pymupdf
    with pymupdf.open(stream=daten, filetype="pdf") as doc:
        # `get_text()` ohne Art liefert Text; die Stubs kennen nur die Summe
        # aller Arten (Liste, Text, Wörterbuch).
        return [str(seite.get_text()) for seite in doc]


def aktueller_link() -> str | None:
    """Der Link der Stadt-Seite auf die aktuelle Lesefassung von Nr. 1.02."""
    import requests
    antwort = requests.get(LISTING_URL, headers={"User-Agent": UA}, timeout=TIMEOUT)
    antwort.raise_for_status()
    seite = antwort.text
    pos = seite.find(f"{ORTSRECHT_NR} Geschäftsordnung")
    if pos < 0:
        pos = html.unescape(seite).find(f"{ORTSRECHT_NR} Geschäftsordnung")
    m = re.search(r'href="([^"]*22_Rechtsamt/1\.02_[^"]+\.pdf)"', seite[max(pos, 0):])
    if not m:
        return None
    href = m.group(1)
    return href if href.startswith("http") else "https://www.oldenburg.de" + href


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    ap.add_argument("--pdf", help="lokale PDF-Datei statt Download")
    ap.add_argument("--check", action="store_true",
                    help="nur prüfen, ob die Stadt eine neue Lesefassung verlinkt")
    ap.add_argument("--adopted", help="Datum des Ratsbeschlusses (JJJJ-MM-TT)")
    ap.add_argument("--template", help="Vorlagen-Nr. des Ratsbeschlusses")
    ap.add_argument("--term-end", help="letzter Tag der Wahlperiode (JJJJ-MM-TT)")
    args = ap.parse_args(argv)

    alt = json.loads(ZIEL.read_text(encoding="utf-8")) if ZIEL.exists() else {}

    if args.check:
        link = aktueller_link()
        gespeichert = alt.get("source_url")
        if link is None:
            print(f"✗ Auf {LISTING_URL} keinen Link für Nr. {ORTSRECHT_NR} gefunden.")
            return 2
        if link != gespeichert:
            print(f"✗ Neue Lesefassung verlinkt:\n  {link}\n  gespeichert: {gespeichert}\n"
                  f"  → python scripts/fetch_rules_of_procedure.py --pdf <datei> "
                  f"--adopted … --template … --term-end …")
            return 1
        print(f"✓ Die Stadt verlinkt weiter {link}")
        return 0

    daten = lade_pdf(args.pdf)
    kopf, paragrafen = parse(seiten_aus_pdf(daten))
    adopted = alt.get("adopted") or {}
    out = {
        **kopf,
        "short_title": "Geschäftsordnung des Rates",
        "source_url": alt.get("source_url") if args.pdf and alt.get("source_url") else PDF_URL,
        "listing_url": LISTING_URL,
        "sha256": hashlib.sha256(daten).hexdigest(),
        "fetched": date.today().isoformat(),
        "adopted": {"date": args.adopted or adopted.get("date"),
                    "template_number": args.template or adopted.get("template_number")},
        "term_end": args.term_end or alt.get("term_end"),
        "sections": paragrafen,
    }
    ZIEL.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"✓ {len(paragrafen)} Paragrafen → {ZIEL.relative_to(WURZEL)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
