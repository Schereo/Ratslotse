"""Baut aus Digests + Thesen-Positionen die Datenbasis data.json für die Vergleichsseite.

Ähnlichkeitsmodell (Wahl-O-Mat-Logik, symmetrisch zwischen zwei Listen):
  Position je These: +1 Zustimmung, 0 neutral/teils-teils, -1 Ablehnung, None = keine Aussage.
  Nur Thesen, zu denen BEIDE Seiten eine Position haben, gehen in die Wertung ein.
  Übereinstimmung je These = 1 - |a-b|/2   ->  gleich 1.0, halb 0.5, gegensätzlich 0.0
  Ähnlichkeit = Mittelwert x 100, gerundet.
  n = Zahl der gemeinsam bewerteten Thesen. Unter MIN_N gilt der Wert als nicht belastbar
  und wird auf der Seite als solcher markiert statt beschönigt.
"""

import json
import os
from itertools import combinations

BASE = os.path.dirname(os.path.abspath(__file__))
MIN_N = 5          # weniger gemeinsame Thesen -> Wert nicht belastbar
MIN_N_THEMA = 2    # je Themenfeld

# Art der Quelle je Liste. Bewusst explizit statt per Textheuristik geraten —
# die Einstufung entscheidet, wie die Seite die Datenlage darstellt, und muss
# nachvollziehbar sein. Begruendung jeweils aus der Programmrecherche.
QUELLENART = {
    "spd":             ("voll",   "Eigenes Kommunalwahlprogramm, 54 Seiten"),
    "cdu":             ("voll",   "Eigenes Kommunalwahlprogramm als Website mit 10 Themenkapiteln"),
    "gruene":          ("voll",   "Eigenes Kommunalwahlprogramm, 40 Seiten"),
    "linke":           ("voll",   "Eigenes Kommunalwahlprogramm, 32 Seiten"),
    "fdp":             ("voll",   "Eigenes Kommunalwahlprogramm, 16 Seiten"),
    "afd":             ("voll",   "Eigenes Kommunalwahlprogramm, 48 Seiten"),
    "volt":            ("voll",   "Eigenes Kommunalwahlprogramm, 71 Seiten"),
    "buergerbuendnis": ("voll",   "Eigenes Kommunalwahlprogramm, 11 Seiten, plus Positionspapiere"),
    "bsw":             ("landes", "Landesweites Rahmenprogramm fuer alle niedersaechsischen Kommunalwahlen; nennt Oldenburg an keiner Stelle"),
    "fuer-oldenburg":  ("kurz",   "Kein Langprogramm, nur sieben knappe Schwerpunkte auf der Website"),
    "echt-oldenburg":  ("kurz",   "Kampagnenwebsite mit Kandidatenportraits; Programm soll laut eigener Ankuendigung erst per Buergerumfrage entstehen"),
    "dava":            ("kurz",   "Kein Kommunalprogramm; ausgewertet wurden ein Zeitungsportraet des OB-Kandidaten und generische Landesverbandsaussagen"),
    "stille":          ("kurz",   "Kein Programm; ausgewertet wurde ein Zeitungsportraet zur OB-Kandidatur"),
    "piraten":         ("keins",  "Kein Wahlprogramm und keine dokumentierten Kernforderungen auffindbar"),
    "partei":          ("keins",  "Kein Wahlprogramm und keine dokumentierten Kernforderungen auffindbar"),
    "pgm":             ("keins",  "Kein kommunales Wahlprogramm auffindbar; Partei erst im Mai 2026 in Oldenburg gegruendet"),
}

THEMEN = {
    "wohnen":      {"label": "Wohnen & Stadtentwicklung", "kurz": "Wohnen"},
    "mobilitaet":  {"label": "Mobilität & Verkehr", "kurz": "Mobilität"},
    "klima":       {"label": "Klima, Energie & Umwelt", "kurz": "Klima"},
    "wirtschaft":  {"label": "Wirtschaft & Innenstadt", "kurz": "Wirtschaft"},
    "bildung":     {"label": "Bildung & Betreuung", "kurz": "Bildung"},
    "soziales":    {"label": "Soziales & Gesundheit", "kurz": "Soziales"},
    "kultur":      {"label": "Kultur, Sport & Freizeit", "kurz": "Kultur"},
    "sicherheit":  {"label": "Sicherheit & Ordnung", "kurz": "Sicherheit"},
    "digitales":   {"label": "Digitales & Verwaltung", "kurz": "Digitales"},
    "finanzen":    {"label": "Haushalt & Finanzen", "kurz": "Finanzen"},
    "beteiligung": {"label": "Beteiligung & Demokratie", "kurz": "Beteiligung"},
    "integration": {"label": "Integration & Vielfalt", "kurz": "Integration"},
}


def lade(ordner):
    out = {}
    d = os.path.join(BASE, ordner)
    if not os.path.isdir(d):
        return out
    for fn in sorted(os.listdir(d)):
        if fn.endswith(".json"):
            try:
                with open(os.path.join(d, fn), encoding="utf-8") as f:
                    out[fn[:-5]] = json.load(f)
            except json.JSONDecodeError as e:
                print(f"  !! {ordner}/{fn}: ungueltiges JSON ({e})")
    return out


def aehnlichkeit(pa, pb, ids):
    """(prozent, n); prozent None wenn keine gemeinsame Basis."""
    s = []
    for t in ids:
        a, b = pa.get(t), pb.get(t)
        if a is None or b is None:
            continue
        s.append(1 - abs(a - b) / 2)
    if not s:
        return None, 0
    return round(100 * sum(s) / len(s)), len(s)


def main():
    digests = lade("digests")
    positionen = lade("positionen")
    with open(os.path.join(BASE, "wahl-fakten.json"), encoding="utf-8") as f:
        fakten = json.load(f)
    with open(os.path.join(BASE, "parteien-meta.json"), encoding="utf-8") as f:
        meta = json.load(f)

    thesen = []
    tp = os.path.join(BASE, "thesen.json")
    if os.path.exists(tp):
        with open(tp, encoding="utf-8") as f:
            thesen = json.load(f)["thesen"]

    reihenfolge = [w["slug"] for w in fakten["wahlvorschlaege"]]
    print(f"Digests {len(digests)}/{len(reihenfolge)} · Positionen {len(positionen)} · Thesen {len(thesen)}")
    fehlend = [s for s in reihenfolge if s not in digests]
    if fehlend:
        print("  fehlende Digests:", ", ".join(fehlend))

    flat = {s: {k: v.get("pos") for k, v in p.get("positionen", {}).items()}
            for s, p in positionen.items()}

    alle_ids = [t["id"] for t in thesen]
    ids_thema = {k: [t["id"] for t in thesen if t["thema"] == k] for k in THEMEN}

    paare = {}
    for a, b in combinations([s for s in reihenfolge if s in flat], 2):
        w, n = aehnlichkeit(flat[a], flat[b], alle_ids)
        paare[f"{a}|{b}"] = {
            "wert": w, "n": n,
            "themen": {k: dict(zip(("wert", "n"), aehnlichkeit(flat[a], flat[b], ids)))
                       for k, ids in ids_thema.items()},
        }

    abdeckung = {
        s: {k: {"praegnanz": (d.get("themen", {}).get(k) or {}).get("praegnanz", 0),
                "anzahl": len((d.get("themen", {}).get(k) or {}).get("positionen", []) or [])}
            for k in THEMEN}
        for s, d in digests.items()
    }

    themen_rang = []
    for k, m in THEMEN.items():
        themen_rang.append({
            "key": k, "label": m["label"], "kurz": m["kurz"],
            "erwaehnt": sum(1 for s in abdeckung if abdeckung[s][k]["praegnanz"] >= 1),
            "mit_abschnitt": sum(1 for s in abdeckung if abdeckung[s][k]["praegnanz"] >= 2),
            "schwerpunkt": sum(1 for s in abdeckung if abdeckung[s][k]["praegnanz"] == 3),
            "positionen_gesamt": sum(abdeckung[s][k]["anzahl"] for s in abdeckung),
            "thesen": len(ids_thema[k]),
        })
    themen_rang.sort(key=lambda x: (-x["erwaehnt"], -x["positionen_gesamt"]))

    # Streitgrad je These: mittlerer paarweiser Abstand unter allen Listen, die sich
    # ueberhaupt aeussern. 0 = voellige Einigkeit, 1 = maximale Spaltung.
    thesen_stat = []
    for t in thesen:
        werte = [flat[s][t["id"]] for s in reihenfolge
                 if s in flat and flat[s].get(t["id"]) is not None]
        paar_abstaende = [abs(a - b) / 2 for i, a in enumerate(werte) for b in werte[i + 1:]]
        thesen_stat.append({
            "id": t["id"], "thema": t["thema"], "these": t["these"], "hinweis": t.get("hinweis"),
            "n": len(werte),
            "dafuer": sum(1 for w in werte if w == 1),
            "teils": sum(1 for w in werte if w == 0),
            "dagegen": sum(1 for w in werte if w == -1),
            "streit": round(sum(paar_abstaende) / len(paar_abstaende), 3) if paar_abstaende else None,
        })

    # Belegkette je Liste: Original-URL, archivierte Kopie, Seitenlink-Muster.
    # Damit laesst sich jede einzelne Position bis zur Seite im Originalprogramm
    # zurueckverfolgen — der Punkt, an dem sich Auswertung von Behauptung unterscheidet.
    quellen = {}
    for s in reihenfolge:
        d = digests.get(s, {})
        pr = d.get("programm", {}) or {}
        pdf = os.path.join(BASE, "programme", f"{s}.pdf")
        txt = os.path.join(BASE, "programme", f"{s}.txt")
        quellen[s] = {
            "url": pr.get("url"),
            "titel": pr.get("titel"),
            "format": pr.get("format"),
            "seiten": pr.get("seiten"),
            "stand": pr.get("stand"),
            "archiv_pdf": f"programme/{s}.pdf" if os.path.exists(pdf) else None,
            "archiv_txt": f"programme/{s}.txt" if os.path.exists(txt) else None,
            # PDF-Viewer springen mit #page=N direkt an die Belegstelle
            "seitenlink": bool(pr.get("url") and pr.get("format") == "pdf"),
        }

    quellenart = {s: {"art": QUELLENART[s][0], "begruendung": QUELLENART[s][1]}
                  for s in reihenfolge if s in QUELLENART}
    fehlt = [s for s in reihenfolge if s not in QUELLENART]
    if fehlt:
        print("  !! ohne Quellenart-Einstufung:", ", ".join(fehlt))

    daten = {
        "fakten": fakten, "meta": meta, "themen": THEMEN, "themen_rang": themen_rang,
        "quellenart": quellenart, "thesen_stat": thesen_stat, "quellen": quellen,
        "thesen": thesen, "digests": digests, "positionen": positionen,
        "paare": paare, "abdeckung": abdeckung,
        "min_n": MIN_N, "min_n_thema": MIN_N_THEMA, "reihenfolge": reihenfolge,
    }
    ziel = os.path.join(BASE, "data.json")
    with open(ziel, "w", encoding="utf-8") as f:
        json.dump(daten, f, ensure_ascii=False, separators=(",", ":"))
    print(f"-> {ziel} ({os.path.getsize(ziel)/1024:.0f} KB)")

    if paare:
        srt = sorted(((v["wert"], k, v["n"]) for k, v in paare.items() if v["wert"] is not None), reverse=True)
        print("\nAehnlichste Paare:")
        for w, k, n in srt[:8]:
            print(f"   {w:>3}%  n={n:<3} {k}")
        print("Entfernteste Paare:")
        for w, k, n in srt[-8:]:
            print(f"   {w:>3}%  n={n:<3} {k}")


if __name__ == "__main__":
    main()
