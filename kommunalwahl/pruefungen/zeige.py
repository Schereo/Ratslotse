"""zeige.py <themenkey|thesen-id...>  — Positionen aller Vergleichslisten je These."""
import json, os, sys, textwrap

BASE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
D = json.load(open(os.path.join(BASE, "data.json"), encoding="utf-8"))
VERGLEICH = [s for s in D["reihenfolge"] if D["quellenart"][s]["art"] in ("voll", "landes")]
SYM = {1: "  JA  ", 0: " teils", -1: " NEIN ", None: "   ·  "}

ziel = sys.argv[1:]
for t in D["thesen"]:
    if not (t["id"] in ziel or t["thema"] in ziel or "alle" in ziel):
        continue
    st = next(s for s in D["thesen_stat"] if s["id"] == t["id"])
    print(f"\n{'═'*100}\n{t['id']}  [{t['thema']}]  n={st['n']}  +{st['dafuer']} / 0:{st['teils']} / -{st['dagegen']}"
          f"  streit={st['streit']}")
    print(textwrap.fill(t["these"], 96, initial_indent="  ", subsequent_indent="  "))
    if t["hinweis"]:
        print(textwrap.fill("Hinweis: " + t["hinweis"], 96, initial_indent="  › ", subsequent_indent="    "))
    print("─" * 100)
    for slug in VERGLEICH:
        v = D["positionen"][slug]["positionen"][t["id"]]
        kopf = f"{SYM[v['pos']]} {D['meta'][slug]['kurz']:<12}"
        if v["pos"] is None:
            print(f"{kopf} —")
            continue
        s = f"S.{v['seite']}" if v["seite"] else "web"
        print(textwrap.fill(v["beleg"], 96, initial_indent=f"{kopf} ({s}) ",
                            subsequent_indent=" " * 22))
