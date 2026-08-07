"""Seitenzahlen exakt prüfen: Wo ein wörtliches Zitatstück im Text auffindbar ist,
muss die angegebene Seite die Fundseite sein (oder deren Nachbarin, wegen Umbruch)."""
import json, os, re, unicodedata

BASE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
D = json.load(open(os.path.join(BASE, "data.json"), encoding="utf-8"))
IDS = [t["id"] for t in D["thesen"]]

def norm(s):
    s = unicodedata.normalize("NFKC", s or "").replace("­", "")
    for a in '„“”‟«»‚‘’‹›"\'': s = s.replace(a, "")
    for a in "–—−‐‑": s = s.replace(a, "-")
    s = s.replace(" ", " ").replace("ﬁ", "fi").replace("ﬂ", "fl")
    return re.sub(r"\s+", " ", s).lower().strip()

def kompakt(s):
    """Härteste Normalform: nur Buchstaben/Ziffern. Übersteht jeden
    Extraktionsschmutz (getrennte Wörter, verlorene Bindestriche, Sperrsatz)."""
    return re.sub(r"[^a-zäöüß0-9]", "", norm(s))

def seiten(slug):
    p = os.path.join(BASE, "programme", f"{slug}.txt")
    if not os.path.exists(p): return None
    roh = open(p, encoding="utf-8", errors="ignore").read()
    t = re.split(r"=====\s*\[Seite (\d+)\]\s*=====", roh)
    if len(t) < 2: return None
    return {int(t[i]): kompakt(t[i + 1]) for i in range(1, len(t), 2)}

def stuecke(zit):
    z = re.sub(r"\[\s*\.{2,}\s*\]|\.{3,}|…", "|", norm(zit))
    z = re.sub(r"\[(\w+)\]", r"\1", z)
    return [kompakt(p) for p in z.split("|")]

falsch, ohne, gepruft = [], [], 0
for slug in D["reihenfolge"]:
    sn = seiten(slug)
    if not sn: continue
    for tid in IDS:
        v = D["positionen"][slug]["positionen"][tid]
        if v["pos"] is None: continue
        if v["seite"] is None:
            ohne.append((slug, tid, v["beleg"][:80])); continue
        frag = []
        for zit in re.findall(r'[„"“]([^„“"]{15,})[“"”]', v["beleg"]):
            frag += [p for p in stuecke(zit) if len(p) >= 30]
        if not frag: continue
        gepruft += 1
        fund = sorted({s for s, t in sn.items() if any(f in t for f in frag)})
        if not fund: continue                      # Zitat nirgends -> anderer Prüfer
        if v["seite"] not in fund and not any(abs(v["seite"] - s) <= 1 for s in fund):
            falsch.append((slug, tid, v["seite"], fund, v["beleg"][:100]))

print(f"Positionen mit auffindbarem Zitatstück: {gepruft}\n")
print(f"── Seitenzahl passt nicht zur Fundstelle: {len(falsch)}")
for slug, tid, s, fund, b in falsch:
    print(f"  ✗ {slug}/{tid}: angegeben S.{s}, gefunden auf S.{fund}")
    print(f"     {b}")
print(f"\n── Position ohne Seitenzahl trotz PDF-Quelle: {len(ohne)}")
for slug, tid, b in ohne:
    print(f"  ! {slug}/{tid}: {b}")
