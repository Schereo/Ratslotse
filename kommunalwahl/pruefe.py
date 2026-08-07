"""Konsistenzpruefung der Positionsdateien gegen den Thesenkatalog."""
import json
import os

BASE = os.path.dirname(os.path.abspath(__file__))
thesen = json.load(open(os.path.join(BASE, "thesen.json"), encoding="utf-8"))["thesen"]
ids = [t["id"] for t in thesen]
fakten = json.load(open(os.path.join(BASE, "wahl-fakten.json"), encoding="utf-8"))
reihenfolge = [w["slug"] for w in fakten["wahlvorschlaege"]]

print(f"{'Liste':<17}{'+1':>4}{'0':>4}{'-1':>4}{'null':>6}{'belegt':>8}   Probleme")
print("-" * 78)
gesamt_probleme = 0
for slug in reihenfolge:
    p = os.path.join(BASE, "positionen", f"{slug}.json")
    if not os.path.exists(p):
        print(f"{slug:<17}{'—':>4}{'—':>4}{'—':>4}{'—':>6}{'—':>8}   DATEI FEHLT")
        gesamt_probleme += 1
        continue
    d = json.load(open(p, encoding="utf-8"))
    pos = d.get("positionen", {})
    probleme = []

    fehlend = [i for i in ids if i not in pos]
    ueber = [i for i in pos if i not in ids]
    if fehlend:
        probleme.append(f"{len(fehlend)} IDs fehlen ({', '.join(fehlend[:4])})")
    if ueber:
        probleme.append(f"{len(ueber)} unbekannte IDs ({', '.join(ueber[:4])})")

    z = {1: 0, 0: 0, -1: 0, None: 0}
    ohne_beleg = []
    for i, v in pos.items():
        w = v.get("pos")
        if w not in (1, 0, -1, None):
            probleme.append(f"{i}: ungueltiger Wert {w!r}")
            continue
        z[w] += 1
        if w is not None and not v.get("beleg"):
            ohne_beleg.append(i)
    if ohne_beleg:
        probleme.append(f"{len(ohne_beleg)} Positionen ohne Beleg ({', '.join(ohne_beleg[:4])})")

    belegt = z[1] + z[0] + z[-1]
    gesamt_probleme += len(probleme)
    print(f"{slug:<17}{z[1]:>4}{z[0]:>4}{z[-1]:>4}{z[None]:>6}{belegt:>8}   {'; '.join(probleme) or 'ok'}")

print("-" * 78)
print("Alles konsistent." if gesamt_probleme == 0 else f"{gesamt_probleme} Problem(e) gefunden.")
