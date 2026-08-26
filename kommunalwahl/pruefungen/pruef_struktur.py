"""Strukturprüfung + Nachrechnen der abgeleiteten Werte in data.json."""
import json, os, itertools

BASE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
D = json.load(open(os.path.join(BASE, "data.json"), encoding="utf-8"))
THESEN = json.load(open(os.path.join(BASE, "thesen.json"), encoding="utf-8"))["thesen"]
IDS = [t["id"] for t in THESEN]
THEMA = {t["id"]: t["thema"] for t in THESEN}
SLUGS = D["reihenfolge"]

fehler, warn = [], []


def f(msg): fehler.append(msg)
def w(msg): warn.append(msg)


# ---- A: Thesenkatalog ------------------------------------------------------
if len(IDS) != len(set(IDS)):
    f(f"thesen.json: doppelte IDs {[i for i in IDS if IDS.count(i) > 1]}")
if len(IDS) != 44:
    f(f"thesen.json: {len(IDS)} Thesen statt 44")

# ---- B: Positionsdateien --------------------------------------------------
for slug in SLUGS:
    p = json.load(open(os.path.join(BASE, "positionen", f"{slug}.json"), encoding="utf-8"))
    if p.get("slug") != slug:
        f(f"{slug}: slug-Feld sagt {p.get('slug')!r}")
    pos = p["positionen"]
    fehlend = set(IDS) - set(pos)
    ueber = set(pos) - set(IDS)
    if fehlend: f(f"{slug}: fehlende Thesen {sorted(fehlend)}")
    if ueber:   f(f"{slug}: unbekannte Thesen {sorted(ueber)}")
    seitenlink = (D["quellen"].get(slug) or {}).get("seitenlink", False)
    for tid, v in pos.items():
        if v["pos"] not in (1, 0, -1, None):
            f(f"{slug}/{tid}: pos={v['pos']!r} unzulässig")
        if v["pos"] is None:
            if v.get("beleg"): f(f"{slug}/{tid}: pos=null, aber Beleg vorhanden")
            if v.get("seite"): f(f"{slug}/{tid}: pos=null, aber Seite {v['seite']}")
        else:
            if not v.get("beleg"): f(f"{slug}/{tid}: pos={v['pos']}, aber kein Beleg")
            if not seitenlink and v.get("seite") is not None:
                f(f"{slug}/{tid}: Seite {v['seite']} bei Quelle ohne Seitenbezug")
        # data.json muss identisch sein
        dj = D["positionen"][slug]["positionen"].get(tid)
        if dj != v:
            f(f"{slug}/{tid}: data.json weicht von positionen/{slug}.json ab")

# ---- C: Seitenzahlen im gültigen Bereich ----------------------------------
for slug in SLUGS:
    q = D["quellen"].get(slug) or {}
    n = q.get("seiten")
    if not n: continue
    for tid, v in D["positionen"][slug]["positionen"].items():
        s = v.get("seite")
        if s is not None and not (1 <= s <= n):
            f(f"{slug}/{tid}: Seite {s} außerhalb 1..{n}")
    for feld, blk in D["digests"][slug]["themen"].items():
        for s in (blk.get("seiten") or []):
            if not (1 <= s <= n):
                f(f"{slug}/digest/{feld}: Seite {s} außerhalb 1..{n}")

# ---- D: paare nachrechnen -------------------------------------------------
def uebereinstimmung(a, b):
    gem = [(x, y) for x, y in zip(a, b) if x is not None and y is not None]
    if not gem: return None, 0
    return round(sum(1 - abs(x - y) / 2 for x, y in gem) / len(gem) * 100), len(gem)

abw = 0
for a, b in itertools.combinations(SLUGS, 2):
    key = f"{a}|{b}"
    if key not in D["paare"]:
        f(f"paare: {key} fehlt"); continue
    pa = [D["positionen"][a]["positionen"][i]["pos"] for i in IDS]
    pb = [D["positionen"][b]["positionen"][i]["pos"] for i in IDS]
    wert, n = uebereinstimmung(pa, pb)
    got = D["paare"][key]
    if got["n"] != n: f(f"paare/{key}: n={got['n']} statt {n}")
    if got["wert"] != wert: f(f"paare/{key}: wert={got['wert']} statt {wert}"); abw += 1
    for feld in D["themen"]:
        ids = [i for i in IDS if THEMA[i] == feld]
        wa = [D["positionen"][a]["positionen"][i]["pos"] for i in ids]
        wb = [D["positionen"][b]["positionen"][i]["pos"] for i in ids]
        tw, tn = uebereinstimmung(wa, wb)
        g = got["themen"][feld]
        if g["n"] != tn or g["wert"] != tw:
            f(f"paare/{key}/{feld}: {g} statt wert={tw} n={tn}")

anzahl_erwartet = len(SLUGS) * (len(SLUGS) - 1) // 2
if len(D["paare"]) != anzahl_erwartet:
    f(f"paare: {len(D['paare'])} Einträge statt {anzahl_erwartet}")

# ---- E: thesen_stat nachrechnen -------------------------------------------
# Bezugsmenge sind die Vergleichslisten, nicht alle 16 — sonst zaehlen Listen
# ohne Programm in einer Verteilung mit, die neben einer 9-spaltigen Matrix
# steht (pruefbericht.md §4.1).
VERGLEICH = D.get("vergleich")
if not VERGLEICH:
    f("data.json: Feld `vergleich` fehlt — analyse.py ist aelter als die Korrektur")
    VERGLEICH = [s for s in SLUGS if D["quellenart"][s]["art"] in ("voll", "landes")]
if any(D["quellenart"][s]["art"] not in ("voll", "landes") for s in VERGLEICH):
    f("vergleich: enthaelt eine Liste ohne ausformuliertes Programm")

for st in D["thesen_stat"]:
    tid = st["id"]
    werte = [D["positionen"][s]["positionen"][tid]["pos"] for s in VERGLEICH]
    werte = [x for x in werte if x is not None]
    n, dafuer, teils, dagegen = len(werte), werte.count(1), werte.count(0), werte.count(-1)
    if (st["n"], st["dafuer"], st["teils"], st["dagegen"]) != (n, dafuer, teils, dagegen):
        f(f"thesen_stat/{tid}: {st['n']}/{st['dafuer']}/{st['teils']}/{st['dagegen']} "
          f"statt {n}/{dafuer}/{teils}/{dagegen}")
    if st.get("belastbar") != (n >= D["min_n"]):
        f(f"thesen_stat/{tid}: belastbar={st.get('belastbar')} bei n={n}")
    if st["thema"] != THEMA[tid]:
        f(f"thesen_stat/{tid}: thema {st['thema']} statt {THEMA[tid]}")

# ---- E2: themen_rang ebenfalls ueber die Vergleichsmenge ------------------
for r in D["themen_rang"]:
    k = r["key"]
    if r["erwaehnt"] != sum(1 for s in VERGLEICH if D["abdeckung"][s][k]["praegnanz"] >= 1):
        f(f"themen_rang/{k}: erwaehnt={r['erwaehnt']} nicht ueber die Vergleichsmenge gerechnet")
    if r["positionen_gesamt"] != sum(D["abdeckung"][s][k]["anzahl"] for s in VERGLEICH):
        f(f"themen_rang/{k}: positionen_gesamt nicht ueber die Vergleichsmenge gerechnet")

# ---- F: abdeckung gegen digests -------------------------------------------
for slug in SLUGS:
    for feld, blk in D["digests"][slug]["themen"].items():
        a = D["abdeckung"][slug][feld]
        n = len(blk.get("positionen") or [])
        if a["anzahl"] != n:
            f(f"abdeckung/{slug}/{feld}: anzahl={a['anzahl']} statt {n}")
        if a["praegnanz"] != blk.get("praegnanz"):
            f(f"abdeckung/{slug}/{feld}: praegnanz={a['praegnanz']} statt {blk.get('praegnanz')}")

# ---- G: Wahlfakten-Konsistenz ---------------------------------------------
wv = D["fakten"]["wahlvorschlaege"]
if [x["slug"] for x in wv] != SLUGS:
    w("reihenfolge weicht von fakten.wahlvorschlaege ab")
summe = sum(x["kandidaten"] for x in wv)
if summe != D["fakten"]["wahl"]["kandidierende"]:
    f(f"Kandidatensumme {summe} != fakten.wahl.kandidierende {D['fakten']['wahl']['kandidierende']}")
if len(wv) != D["fakten"]["wahl"]["wahlvorschlaege_anzahl"]:
    f(f"Anzahl Wahlvorschläge {len(wv)} != {D['fakten']['wahl']['wahlvorschlaege_anzahl']}")
be = D["fakten"]["buergerentscheid_baumschutz"]
if be["ja"] + be["nein"] != be["beteiligung"]:
    w(f"Bürgerentscheid: ja+nein={be['ja']+be['nein']} != beteiligung={be['beteiligung']}")
for slug in SLUGS:
    m = D["meta"].get(slug)
    if not m: f(f"meta: {slug} fehlt")
    if slug not in D["quellenart"]: f(f"quellenart: {slug} fehlt")
    if slug not in D["digests"]: f(f"digests: {slug} fehlt")

# ---- Ausgabe --------------------------------------------------------------
print(f"FEHLER ({len(fehler)}):")
for m in fehler: print("  ✗", m)
print(f"\nWARNUNGEN ({len(warn)}):")
for m in warn: print("  !", m)
if not fehler and not warn: print("  — nichts —")
