"""Sind die „besonderes“- und „kernpunkte“-Aussagen im Programmtext verankert?

Heuristik: markante Substantive/Zahlen aus der Aussage im Volltext suchen.
Alles unter 50 % Deckung wird zur Handprüfung ausgeworfen.
"""
import json, os, re, sys, unicodedata

BASE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
D = json.load(open(os.path.join(BASE, "data.json"), encoding="utf-8"))
V = [s for s in D["reihenfolge"] if D["quellenart"][s]["art"] in ("voll", "landes")]

STOPP = set("""werden wollen sollen sollten durch nicht auch eine einen einem einer eines
oldenburg stadt städtische städtischen städtischer oldenburger programm fordert fordern
statt mehr aller allen jede jeden diese dieser sowie dabei damit ihrer ihren gegen ohne
kommunale kommunalen kommunaler bereich bereichen anspruch explizite explizit""".split())

def norm(s):
    s = unicodedata.normalize("NFKC", s or "").replace("­", "")
    for a in '„“”‟«»‚‘’‹›"\'': s = s.replace(a, " ")
    for a in "–—−‐‑": s = s.replace(a, "-")
    return re.sub(r"\s+", " ", s.replace(" ", " ")).lower()

def kompakt(s): return re.sub(r"[^a-zäöüß0-9]", "", norm(s))

def marker(s):
    return {t for t in re.findall(r"[a-zäöüß]{6,}|\d{2,}", norm(s)) if t not in STOPP}

grenze = float(sys.argv[1]) if len(sys.argv) > 1 else 0.5
for slug in V:
    p = os.path.join(BASE, "programme", f"{slug}.txt")
    if not os.path.exists(p): continue
    txt = kompakt(open(p, encoding="utf-8", errors="ignore").read())
    g = D["digests"][slug]
    for feld, items in (("besonderes", g.get("besonderes") or []),
                        ("kernpunkte", g.get("kernpunkte") or [])):
        for it in items:
            mk = marker(it)
            if len(mk) < 3: continue
            d = sum(1 for m in mk if kompakt(m) in txt) / len(mk)
            if d < grenze:
                fehlt = [m for m in sorted(mk) if kompakt(m) not in txt]
                print(f"\n  {D['meta'][slug]['kurz']:<8} [{feld}] Deckung {d:.0%}")
                print(f"     {it[:190]}")
                print(f"     nicht im Text: {', '.join(fehlt[:8])}")
