"""Konsistenzsonden über die Positionsbelege."""
import json, os, re, itertools

BASE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
D = json.load(open(os.path.join(BASE, "data.json"), encoding="utf-8"))
IDS = [t["id"] for t in D["thesen"]]
V = [s for s in D["reihenfolge"] if D["quellenart"][s]["art"] in ("voll", "landes")]
P = {s: D["positionen"][s]["positionen"] for s in V}
K = {s: D["meta"][s]["kurz"] for s in V}

# --- 1: Wie viele Thesen tragen überhaupt einen Vergleich? ---------------
print("── Tragfähigkeit der Thesen (nur die 9 Vergleichslisten) ──")
verteilung = {}
for i in IDS:
    n = sum(1 for s in V if P[s][i]["pos"] is not None)
    verteilung.setdefault(n, []).append(i)
for n in sorted(verteilung):
    print(f"   {n} Listen positioniert: {len(verteilung[n]):2} Thesen   {' '.join(verteilung[n])}")
tot = sum(len(v) for n, v in verteilung.items() if n >= 2)
print(f"\n   Thesen mit mindestens zwei Positionen (= vergleichbar): {tot} von 44")
print(f"   Thesen, die nur eine Liste beantwortet hat: {verteilung.get(1, [])}")
print(f"   Thesen ohne jede Position: {verteilung.get(0, [])}")

# --- 2: Einschränkungs-Sprache im Beleg vs. vergebene Note ---------------
print("\n── Belege mit Einschränkungssprache („nur…“, „ohne…“, „keine ausdrückliche…“) ──")
EIN = re.compile(r"\b(nur|lediglich|ohne .{0,40}(zu nennen|zu fordern|anzusprechen)|"
                 r"keine? (ausdrückliche|explizite|klare|generelle)|nicht (ausdrücklich|explizit|konkret)|"
                 r"schwächer|deutlich enger|allgemein)", re.I)
auff = []
for s in V:
    for i in IDS:
        v = P[s][i]
        if v["pos"] in (1, -1) and v["beleg"] and EIN.search(v["beleg"]):
            auff.append((i, K[s], v["pos"], v["beleg"]))
print(f"   {len(auff)} Fälle mit klarer Note (+1/-1) trotz Einschränkungssprache:")
for i, k, p, b in sorted(auff):
    print(f"   {'+1' if p == 1 else '-1'} {i} {k:<8} {b[:120]}")

# --- 3: Gleiches Stichwort, verschiedene Note ----------------------------
print("\n── Je These: Notenverteilung, wo Belege dasselbe Stichwort tragen ──")
def kern(b):
    return set(w.lower() for w in re.findall(r"[A-ZÄÖÜ][a-zäöüßA-ZÄÖÜ-]{7,}", b or ""))
for i in IDS:
    hab = [(s, P[s][i]) for s in V if P[s][i]["pos"] is not None]
    for (a, va), (b, vb) in itertools.combinations(hab, 2):
        if va["pos"] == vb["pos"]: continue
        gem = kern(va["beleg"]) & kern(vb["beleg"])
        if len(gem) >= 2 and abs(va["pos"] - vb["pos"]) == 2:
            print(f"   {i}: {K[a]} ({va['pos']:+d}) vs {K[b]} ({vb['pos']:+d}) — "
                  f"gemeinsame Begriffe: {', '.join(sorted(gem))}")

# --- 4: Wie stark trägt eine Liste zu ihren eigenen Werten bei? ----------
print("\n── Positionsdichte je Liste (wie viel Substanz steckt hinter den Prozenten) ──")
for s in V:
    n = sum(1 for i in IDS if P[s][i]["pos"] is not None)
    null = 44 - n
    print(f"   {K[s]:<10} {n:2} Positionen, {null:2} × keine Aussage "
          f"({n/44*100:3.0f} % Abdeckung)")
