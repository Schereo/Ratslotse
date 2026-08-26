"""Wie belastbar sind die Ähnlichkeitswerte? Zwei Fragen:
   1. Wie viel der Übereinstimmung kommt aus 0–0-Paarungen (beide unentschieden)?
   2. Wie stark hängt das Ergebnis an der Thesenauswahl (Jackknife)?
"""
import json, os, itertools, statistics

BASE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
D = json.load(open(os.path.join(BASE, "data.json"), encoding="utf-8"))
IDS = [t["id"] for t in D["thesen"]]
V = [s for s in D["reihenfolge"] if D["quellenart"][s]["art"] in ("voll", "landes")]
P = {s: D["positionen"][s]["positionen"] for s in V}
KURZ = {s: D["meta"][s]["kurz"] for s in V}

def wert(a, b, ids=IDS):
    g = [(P[a][i]["pos"], P[b][i]["pos"]) for i in ids
         if P[a][i]["pos"] is not None and P[b][i]["pos"] is not None]
    if not g: return None, 0
    return sum(1 - abs(x - y) / 2 for x, y in g) / len(g) * 100, len(g)

# --- 1: Anteil der 0–0-Paarungen -----------------------------------------
print("── Wie viel Übereinstimmung stammt aus beidseitigem „teils/teils“? ──")
print(f"{'Paar':<24}{'Wert':>6}{'n':>5}{'0–0':>6}{'ohne 0–0':>10}{'Δ':>7}")
zeilen = []
for a, b in itertools.combinations(V, 2):
    w, n = wert(a, b)
    nn = sum(1 for i in IDS if P[a][i]["pos"] == 0 and P[b][i]["pos"] == 0)
    ids2 = [i for i in IDS if not (P[a][i]["pos"] == 0 and P[b][i]["pos"] == 0)]
    w2, n2 = wert(a, b, ids2)
    zeilen.append((nn, f"{KURZ[a]}–{KURZ[b]}", w, n, nn, w2, (w2 - w) if w2 else None))
for _, name, w, n, nn, w2, d in sorted(zeilen, reverse=True)[:10]:
    print(f"{name:<24}{w:6.0f}{n:5}{nn:6}{w2:10.0f}{d:+7.0f}")
gesamt0 = sum(z[4] for z in zeilen)
print(f"\n  0–0-Paarungen insgesamt: {gesamt0} von {sum(z[3] for z in zeilen)} gewerteten "
      f"({gesamt0/sum(z[3] for z in zeilen)*100:.0f} %)")

# --- 2: Jackknife über die Thesen ----------------------------------------
print("\n── Wie stark hängt der Wert an einzelnen Thesen? (jede These einzeln weglassen) ──")
schwank = []
for a, b in itertools.combinations(V, 2):
    w, n = wert(a, b)
    alt = [wert(a, b, [i for i in IDS if i != x])[0] for x in IDS]
    alt = [x for x in alt if x is not None]
    schwank.append((max(abs(x - w) for x in alt), f"{KURZ[a]}–{KURZ[b]}", w, n))
schwank.sort(reverse=True)
print(f"{'Paar':<24}{'Wert':>6}{'n':>5}{'max. Ausschlag':>16}")
for d, name, w, n in schwank[:6]:
    print(f"{name:<24}{w:6.0f}{n:5}{d:15.1f} Pkt")
print(f"  Median über alle {len(schwank)} Paare: {statistics.median(d for d,_,_,_ in schwank):.1f} Punkte")

# --- 3: Wie viele Thesen trägt jedes Themenfeld pro Paar? -----------------
print("\n── Themen-Teilwerte: auf wie wenigen Thesen stehen sie? ──")
from collections import Counter
c = Counter()
for k, v in D["paare"].items():
    if not all(s in V for s in k.split("|")): continue
    for feld, t in v["themen"].items():
        c[t["n"]] += 1
print("   n gemeinsamer Thesen im Themenfeld →  Anzahl Zellen")
for n in sorted(c):
    print(f"     n={n}: {c[n]:4}  {'█'*(c[n]//4)}")
unter2 = sum(v for k, v in c.items() if 0 < k < 2)
print(f"\n   Zellen mit n=1 (ein einziger Vergleichspunkt): {unter2} von {sum(c.values())}")
print(f"   Zellen ohne jeden Vergleichspunkt (n=0): {c[0]}")
