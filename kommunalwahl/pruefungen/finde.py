"""finde.py <slug> <regex> [zeichen]  — Fundstellen im entsilbten Fließtext, ungekürzt."""
import os, re, sys, unicodedata

BASE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def norm(s):
    s = unicodedata.normalize("NFKC", s).replace("­", "")
    for a in "–—−‐‑": s = s.replace(a, "-")
    s = s.replace(" ", " ").replace("ﬁ", "fi").replace("ﬂ", "fl")
    return re.sub(r"[ \t]+", " ", s)

slug, muster = sys.argv[1], sys.argv[2]
breite = int(sys.argv[3]) if len(sys.argv) > 3 else 320
roh = open(os.path.join(BASE, "programme", f"{slug}.txt"), encoding="utf-8", errors="ignore").read()
teile = re.split(r"=====\s*\[Seite (\d+)\]\s*=====", roh)

bloecke = []
if len(teile) > 1:
    for i in range(1, len(teile), 2):
        bloecke.append((int(teile[i]), teile[i + 1]))
else:
    bloecke.append((None, roh))

for seite, txt in bloecke:
    # Fließtext: Zeilenumbrüche auflösen, Silbentrennung zusammenziehen
    t = norm(txt)
    t = re.sub(r"-\n(\w)", r"\1", t)
    t = re.sub(r"\s*\n\s*", " ", t)
    for m in re.finditer(muster, t, re.I):
        a, b = max(0, m.start() - breite // 2), min(len(t), m.end() + breite // 2)
        print(f"\n[{'S. ' + str(seite) if seite else 'web'}]  …{t[a:b].strip()}…")
