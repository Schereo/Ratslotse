"""Kandidatenregister zur Ratswahl aus der amtlichen Bekanntmachung.

Liest ``quellen/zulassung-wahlvorschlaege.pdf`` (Wahlausschuss, 23.07.2026)
und schreibt ``kandidaten.json``: je Wahlbereich und Wahlvorschlag die
Bewerber*innen mit Listenplatz, Name, Beruf, Jahrgang und Wohnort.

**Warum über die Koordinaten und nicht über den Text.** Die Textfassung
(``zulassung-wahlvorschlaege.txt``) setzt „Krämer, Anna Sarah
Klimaschutzmanagerin" in eine Zeile — wo der Name aufhört und der Beruf
anfängt, steht dort nirgends. Im PDF stehen die Felder in Spalten: Nummer bei
x≈76, Name ab 110, Beruf ab 253, Jahrgang ab 431, Wohnort ab 473. Der
``visitor_text`` von pypdf liefert diese Position zu jedem Textstück.

**Die Reihenfolge der Wahlvorschläge ist die des Stimmzettels** und damit
auch die der Spalten ``D1 … D16`` in den Open-Data-CSVs des Votemanagers —
geprüft am 06.09.2026: Die Höchstzahl an Bewerber*innen je Liste stimmt
Spalte für Spalte mit den CSV-Köpfen überein (``tests/test_wahlabend.py``).

    python3 kommunalwahl/kandidaten.py            # schreibt kandidaten.json
    python3 kommunalwahl/kandidaten.py --pruefen  # vergleicht nur
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HIER = Path(__file__).resolve().parent
PDF = HIER / "quellen" / "zulassung-wahlvorschlaege.pdf"
ZIEL = HIER / "kandidaten.json"

# Spaltenkanten (x in PDF-Punkten), gemessen an Seite 2 der Bekanntmachung.
X_NUMMER, X_NAME, X_BERUF, X_JAHR, X_ORT = 60, 100, 240, 420, 465

ROEMISCH = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6}


def _norm(s: str) -> str:
    """Vergleichsform: „DAVA - Niedersachsen" (PDF) = „DAVA-Niedersachsen" (Fakten)."""
    return re.sub(r"\s+", " ", re.sub(r"\s*-\s*", "-", s)).strip().lower()


def _zeilen(seite) -> list[list[tuple[float, str]]]:
    """Textstücke einer Seite, nach y gruppiert, je Zeile nach x sortiert."""
    stuecke: list[tuple[float, float, str]] = []

    def besuch(text, cm, tm, fd, fs):  # noqa: ANN001 — Signatur von pypdf
        if text.strip():
            stuecke.append((round(tm[5]), tm[4], text.strip()))

    seite.extract_text(visitor_text=besuch)
    zeilen: dict[float, list[tuple[float, str]]] = {}
    for y, x, t in stuecke:
        zeilen.setdefault(y, []).append((x, t))
    return [sorted(zeilen[y]) for y in sorted(zeilen, reverse=True)]


def _spalten(zeile: list[tuple[float, str]]) -> dict[str, str]:
    felder = {"nummer": [], "name": [], "beruf": [], "jahr": [], "ort": []}
    for x, t in zeile:
        if x < X_NAME:
            # pypdf liefert manche Zeilen als EIN Stück: „9      Hähnel, Dieter".
            m = re.fullmatch(r"(\d+)\s+(\S.*)", t)
            if m:
                felder["nummer"].append(m.group(1))
                felder["name"].append(m.group(2))
            else:
                felder["nummer"].append(t)
        elif x < X_BERUF:
            felder["name"].append(t)
        elif x < X_JAHR:
            felder["beruf"].append(t)
        elif x < X_ORT:
            felder["jahr"].append(t)
        else:
            felder["ort"].append(t)
    return {k: _glatt(" ".join(v)) for k, v in felder.items()}


def _glatt(s: str) -> str:
    """„Wittig - Aßmus" -> „Wittig-Aßmus", „S elbstständiger" -> „Selbstständiger"."""
    s = re.sub(r"\s*-\s*", "-", s)
    s = re.sub(r"\b([A-ZÄÖÜ]) (?=[a-zäöüß]{2,})", r"\1", s)
    return re.sub(r"\s+", " ", s).strip()


def lies(pdf: Path = PDF) -> dict:
    from pypdf import PdfReader

    fakten = json.loads((HIER / "wahl-fakten.json").read_text(encoding="utf-8"))
    slug_nach_amtlich = {_norm(v["amtlich"]): v["slug"] for v in fakten["wahlvorschlaege"]}
    kurz_nach_slug = {v["slug"]: v["kurz"] for v in fakten["wahlvorschlaege"]}
    typ_nach_slug = {v["slug"]: v["typ"] for v in fakten["wahlvorschlaege"]}
    wahlbereiche = [
        {"number": ROEMISCH[w.split(" – ")[0]], "roman": w.split(" – ")[0], "name": w.split(" – ")[1]}
        for w in fakten["wahl"]["wahlbereiche"]
    ]

    listen: dict[int, dict] = {}
    wb: int | None = None
    liste: int | None = None
    im_rat = False
    kopf_offen = False
    letzter: dict | None = None
    for seite in PdfReader(str(pdf)).pages:
        for zeile in _zeilen(seite):
            text = " ".join(t for _, t in zeile)
            if "Wahlvorschläge für die Wahl des Rats" in text:
                im_rat = True
                continue
            if not im_rat:
                continue
            m = re.match(r"Wahlbereich ([IVX]+) – (.+)", text)
            if m:
                wb = ROEMISCH[m.group(1)]
                liste = None
                continue
            m = re.match(r"\((\d+)\)\s+(.+?)\s*$", text)
            if m and wb is not None:
                liste = int(m.group(1))
                amtlich = re.sub(r"\s+", " ", m.group(2)).strip()
                eintrag = listen.setdefault(liste, {"index": liste, "official": amtlich, "areas": {}})
                if len(eintrag["official"]) < len(amtlich):
                    eintrag["official"] = amtlich
                eintrag["areas"].setdefault(wb, [])
                kopf_offen = amtlich.count("(") > amtlich.count(")")
                continue
            f = _spalten(zeile)
            if wb is None or liste is None:
                continue
            if kopf_offen and not f["nummer"] and not f["jahr"]:
                # Zweite Zeile eines langen Listennamens: „Niedersachsen)".
                voll = re.sub(r"\s+", " ", listen[liste]["official"] + " " + text).strip()
                if len(voll) > len(listen[liste]["official"]):
                    listen[liste]["official"] = voll
                kopf_offen = False
                continue
            kopf_offen = False
            if re.fullmatch(r"\d+", f["nummer"]):
                jahr = re.sub(r"\D", "", f["jahr"])
                letzter = {
                    "position": int(f["nummer"]),
                    "name": f["name"],
                    "occupation": f["beruf"] or None,
                    "born": int(jahr) if jahr else None,
                    "place": f["ort"] or None,
                }
                listen[liste]["areas"][wb].append(letzter)
            elif letzter is not None and (f["name"] or f["beruf"]) and not f["nummer"]:
                # Umbruch innerhalb einer Zelle: an den Vorgänger anhängen.
                if f["name"]:
                    letzter["name"] = f"{letzter['name']} {f['name']}".strip()
                if f["beruf"]:
                    letzter["occupation"] = f"{letzter['occupation'] or ''} {f['beruf']}".strip()

    aus = []
    for idx in sorted(listen):
        e = listen[idx]
        slug = slug_nach_amtlich.get(_norm(e["official"]))
        if slug is None:
            praefix = [s for a, s in slug_nach_amtlich.items() if a.startswith(_norm(e["official"])[:40])]
            slug = praefix[0] if len(praefix) == 1 else None
        if slug is None:
            # Einzelwahlvorschlag: „Einzelwahlvorschlag Stille" — Name des Bewerbers.
            passend = [s for a, s in slug_nach_amtlich.items() if a.split()[-1] in _norm(e["official"])]
            slug = passend[0] if len(passend) == 1 else None
        if slug is None:
            raise SystemExit(f"Kein Slug für Wahlvorschlag {idx}: {e['official']!r} — wahl-fakten.json prüfen")
        aus.append({
            "index": idx,
            "slug": slug,
            "short": kurz_nach_slug[slug],
            "official": e["official"],
            "kind": typ_nach_slug[slug],
            "areas": {str(k): v for k, v in sorted(e["areas"].items())},
        })
    return {
        "source": {
            "title": fakten["quelle"]["titel"],
            "url": fakten["quelle"]["url"],
            "file": "quellen/zulassung-wahlvorschlaege.pdf",
            "note": "Reihenfolge der Wahlvorschläge = Stimmzettel = Spalten D1…D16 der Votemanager-CSVs.",
        },
        "election": {"date": fakten["wahl"]["termin"], "seats": fakten["wahl"]["sitze"], "title": fakten["wahl"]["bezeichnung"]},
        "areas": wahlbereiche,
        "lists": aus,
    }


def main(argv: list[str]) -> int:
    daten = lies()
    n = sum(len(c) for l in daten["lists"] for c in l["areas"].values())
    text = json.dumps(daten, ensure_ascii=False, indent=1) + "\n"
    if "--pruefen" in argv:
        alt = ZIEL.read_text(encoding="utf-8") if ZIEL.exists() else ""
        print("unverändert" if alt == text else "ABWEICHUNG zu kandidaten.json")
        return 0 if alt == text else 1
    ZIEL.write_text(text, encoding="utf-8")
    print(f"{len(daten['lists'])} Wahlvorschläge, {n} Bewerber*innen -> {ZIEL.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
