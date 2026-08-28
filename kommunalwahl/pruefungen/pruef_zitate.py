"""Wörtliche Zitate prüfen — mit Rücksicht auf Auslassungen und Einschübe.

Ein Zitat gilt als belegt, wenn jedes seiner Bruchstücke (getrennt an …, [...], ...)
im Volltext vorkommt. Bruchstücke unter 3 Wörtern werden nur gezählt, nicht geprüft.
"""
import json, os, re, unicodedata

BASE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
D = json.load(open(os.path.join(BASE, "data.json"), encoding="utf-8"))
IDS = [t["id"] for t in D["thesen"]]

def norm(s):
    s = unicodedata.normalize("NFKC", s or "").replace("­", "")
    for a in '„“”‟«»‚‘’‹›"\'': s = s.replace(a, '"')
    for a in "–—−‐‑": s = s.replace(a, "-")
    s = s.replace(" ", " ").replace("ﬁ", "fi").replace("ﬂ", "fl")
    return re.sub(r"\s+", " ", s).lower().strip()

def entsilbe(s): return re.sub(r"(\w)- (\w)", r"\1\2", s)

def volltext(slug):
    p = os.path.join(BASE, "programme", f"{slug}.txt")
    if not os.path.exists(p): return None
    t = norm(open(p, encoding="utf-8", errors="ignore").read())
    return entsilbe(t) + " ||| " + t          # beide Lesarten durchsuchbar

def bruchstuecke(zit):
    """Zitat in prüfbare Stücke zerlegen."""
    z = norm(zit)
    z = re.sub(r"\[\s*\.{2,}\s*\]|\.{3,}|…", " ||| ", z)     # Auslassungen
    z = re.sub(r"\[(\w+)\]", r"\1", z)                       # [r] -> r  (Flexion)
    return [entsilbe(p).strip(' ".,;:!?') for p in z.split("|||")]

fehlt, teilweise, ok = [], [], 0
for slug in D["reihenfolge"]:
    txt = volltext(slug)
    if txt is None: continue
    for tid in IDS:
        v = D["positionen"][slug]["positionen"][tid]
        if v["pos"] is None: continue
        for zit in re.findall(r'[„"“]([^„“"]{15,})[“"”]', v["beleg"]):
            teile = [p for p in bruchstuecke(zit) if len(p.split()) >= 3]
            if not teile: continue
            treffer = [p in txt for p in teile]
            if all(treffer):
                ok += 1
            elif any(treffer):
                teilweise.append((slug, tid, zit, [p for p, t in zip(teile, treffer) if not t]))
            else:
                fehlt.append((slug, tid, zit, teile))

print(f"wörtliche Zitate vollständig im Volltext belegt: {ok}")
print(f"\n── teilweise belegt: {len(teilweise)}")
for slug, tid, zit, miss in teilweise:
    print(f"  ! {slug}/{tid}  „{zit[:110]}“")
    for m in miss: print(f"       nicht gefunden: „{m[:110]}“")
print(f"\n── gar nicht belegt: {len(fehlt)}")
for slug, tid, zit, teile in fehlt:
    print(f"  ✗ {slug}/{tid}  „{zit[:150]}“")
