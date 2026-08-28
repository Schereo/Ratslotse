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
import math
import os
import re
from collections import Counter
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


def landkarte_koordinaten(paare, vergleich):
    """Die 36 Paarabstände als 2D-Karte (klassisches MDS, Torgerson).

    Distanz = 1 − Ähnlichkeit/100. Die beiden Hauptachsen entstehen per
    Potenziteration mit Deflation — bei einer 9×9-Matrix reicht das locker,
    und es bleibt reine Standardbibliothek. Die Achsen selbst BEDEUTEN nichts
    (die Seite darf sie nicht politisch beschriften); nur Abstände zählen.

    Orientierung deterministisch festgenagelt, damit die Karte nicht bei jedem
    Lauf gespiegelt herauskommt: linke links von afd, gruene oberhalb von cdu.
    """
    n = len(vergleich)
    idx = {s: i for i, s in enumerate(vergleich)}
    D2 = [[0.0] * n for _ in range(n)]
    for a, b in combinations(vergleich, 2):
        p = paare.get(f"{a}|{b}") or paare.get(f"{b}|{a}")
        d = 1.0 - (p["wert"] or 0) / 100.0
        D2[idx[a]][idx[b]] = D2[idx[b]][idx[a]] = d * d

    zeile = [sum(z) / n for z in D2]
    gesamt = sum(zeile) / n
    B = [[-0.5 * (D2[i][j] - zeile[i] - zeile[j] + gesamt) for j in range(n)] for i in range(n)]

    def normiert(v):
        l = math.sqrt(sum(x * x for x in v))
        return [x / l for x in v] if l > 1e-12 else v

    # B hat auch negative Eigenwerte (die Distanzen sind nicht exakt euklidisch),
    # und deren Betrag kann über der zweiten Achse liegen — die nackte
    # Potenziteration liefe dorthin. Deshalb um sigma verschoben (Gershgorin-
    # Schranke): B + sigma*I ist positiv, der größte Eigenwert bleibt der größte.
    sigma = max(sum(abs(x) for x in zeile_b) for zeile_b in B)
    achsen = []
    for a in range(2):
        v = normiert([math.cos(1.7 * i + a) for i in range(n)])  # fester Start
        lam = 0.0
        for _ in range(600):
            w = [sum(B[i][k] * v[k] for k in range(n)) + sigma * v[i] for i in range(n)]
            lam = sum(w[i] * v[i] for i in range(n)) - sigma
            v = normiert(w)
        achsen.append([x * math.sqrt(max(lam, 0.0)) for x in v])
        for i in range(n):          # Deflation: gefundene Achse herausrechnen
            for j in range(n):
                B[i][j] -= lam * v[i] * v[j]

    xs, ys = achsen
    if xs[idx["linke"]] > xs[idx["afd"]]:
        xs = [-x for x in xs]
    if ys[idx["gruene"]] < ys[idx["cdu"]]:
        ys = [-y for y in ys]
    skala = max(max(abs(x) for x in xs), max(abs(y) for y in ys)) or 1.0
    return [{"slug": s, "x": round(xs[idx[s]] / skala, 3), "y": round(ys[idx[s]] / skala, 3)}
            for s in vergleich]


def finde_alleinstellungen(flat, positionen, thesen, vergleich):
    """Positionen, mit denen eine Liste allein steht — die Überraschungs-Karten.

    Zwei Arten:
      allein_gegen_alle — die Liste hat +1/−1, KEINE andere teilt ihr Vorzeichen,
        und mindestens zwei andere stehen klar auf der Gegenseite. (So bleibt
        „einzige dafür, alle anderen nur teils" draußen — das ist keine
        Konfrontation, sondern Abstufung.)
      einzige_aussage — nur diese eine Liste äußert sich überhaupt zur These.
    """
    out = []
    for t in thesen:
        pos = {s: flat[s].get(t["id"]) for s in vergleich
               if flat[s].get(t["id"]) is not None}
        treffer = None
        if len(pos) == 1:
            s = next(iter(pos))
            treffer = (s, "einzige_aussage")
        elif len(pos) >= 4:
            for s, p in pos.items():
                if p == 0:
                    continue
                andere = [q for r, q in pos.items() if r != s]
                if all(q * p <= 0 for q in andere) and sum(1 for q in andere if q == -p) >= 2:
                    treffer = (s, "allein_gegen_alle")
                    break
        if not treffer:
            continue
        s, art = treffer
        v = positionen[s]["positionen"][t["id"]]
        andere_pos = {r: q for r, q in pos.items() if r != s}
        out.append({
            "art": art, "id": t["id"], "thema": t["thema"], "these": t["these"],
            "slug": s, "pos": pos[s], "beleg": v.get("beleg"), "seite": v.get("seite"),
            "n": len(pos),
            "dagegen": sorted(r for r, q in andere_pos.items() if q == -pos[s]),
            "teils": sorted(r for r, q in andere_pos.items() if q == 0),
        })
    # Konfrontationen zuerst, dann nach Breite der Gegenseite
    out.sort(key=lambda e: (e["art"] != "allein_gegen_alle", -len(e["dagegen"])))
    return out


# Häufige deutsche Funktionswörter plus Programm-Floskeln — was jedes
# Wahlprogramm sagt, unterscheidet keines.
_STOPP = set("""aber alle allem allen aller alles als also andere anderen anderer am an auch auf aus bei beim
besonders bereits bis dabei dadurch dafür damit dann darauf darf das dass dazu dem den denen denn der deren des
deshalb dessen die dies diese diesem diesen dieser dieses doch dort durch ein eine einem einen einer eines etwa
für gegen gibt haben hat hier ihre ihrem ihren ihrer ihres im in ins ist jede jedem jeden jeder jedes kann keine
können mehr mit muss müssen nach neben neue neuen neuer neues nicht noch nur oder ohne schon sein seine seinem
seinen seiner sich sie sind so sollen sollte sowie über um und uns unsere unserem unseren unserer unter viele
vielen vom von vor was weitere weiteren wenn werden wie wieder wir wird wollen wurde zu zudem zum zur zwischen
setzen fordern unterstützen stärken schaffen fördern ausbauen brauchen braucht gilt geht stehen steht
stadt städtische städtischen städtischer städtisches oldenburg oldenburger oldenburgs kommunale kommunalen
kommunaler kommunales kommune kommunen menschen bürger bürgerinnen innen jahren jahre jahr prozent euro
partei programm wahlprogramm kommunalwahlprogramm seite ziel ziele deshalb sowie insbesondere gemeinsam
möglich möglichkeiten bedarf angebote angebot bereich bereichen maßnahmen rahmen dürfen wollen sollen etwa
unserem unserer unsere unser ebenso hierfür hierzu darüber hinaus lehnen setzt fordert beziehungsweise
stadtrat stadtrats rats ratsperiode kreisverband stadtverband landesverband ortsverband positionspapier
mitgliederversammlung kandidatinnen kandidaten kürze ganzes volle auswählen bezeichnet
spd cdu grüne grünen gruene fdp afd volt bsw linke linken piraten bb-ol wfo dava
sozialdemokraten sozialdemokrat sozialdemokratinnen demokraten bündnis union wagenknecht sahra
januar februar märz april mai juni juli august september oktober november dezember
instagram facebook newsletter cookie cookies impressum datenschutz kontakt menü lesen
oiletten ahlprogramm ärzt jascha rohr holger wilkens prange boldt fröhlich butzin castur
html navigation suchen demokratischen alternativen primär sitzungen green erde""".split())


def sprachprofil(slug, alle_texte):
    """Länge, Satzlänge, Lesbarkeit (LIX) und die charakteristischsten Begriffe
    (TF-IDF gegen die anderen Programme) — Fakten über die Sprache, keine Wertung."""
    roh = alle_texte[slug]
    woerter = re.findall(r"[A-Za-zÄÖÜäöüß][A-Za-zÄÖÜäöüß-]{1,}", roh)
    saetze = [s for s in re.split(r"[.!?]+[\s\n]", roh) if len(s.split()) >= 3]
    n_w, n_s = len(woerter), max(len(saetze), 1)
    lang = sum(1 for w in woerter if len(w) > 6)
    lix = round(n_w / n_s + 100 * lang / max(n_w, 1))
    if lix < 40:
        lix_label = "leicht lesbar"
    elif lix < 50:
        lix_label = "mittel"
    elif lix < 60:
        lix_label = "anspruchsvoll"
    else:
        lix_label = "sehr anspruchsvoll"

    def tokens(text):
        return [w.lower().strip("-") for w in re.findall(r"[A-Za-zÄÖÜäöüß][A-Za-zÄÖÜäöüß-]{3,}", text)
                if w.lower().strip("-") not in _STOPP and len(w.strip("-")) >= 4]

    tf = Counter(tokens(roh))
    df = Counter()
    for s2, t2 in alle_texte.items():
        df.update(set(tokens(t2)))
    n_docs = len(alle_texte)
    # Kürzere Programme (FDP: 16 Seiten) erreichen hohe Zählwerte seltener —
    # die Mindesthäufigkeit wächst mit dem Umfang mit.
    mindest = 3 if n_w < 8000 else 4
    scores = {w: (1 + math.log(c)) * math.log(n_docs / df[w])
              for w, c in tf.items() if c >= mindest and df[w] < n_docs}
    top = sorted(scores.items(), key=lambda kv: -kv[1])[:8]
    maxs = top[0][1] if top else 1.0
    return {
        "woerter": n_w,
        "satzlaenge": round(n_w / n_s, 1),
        "lix": lix,
        "lix_label": lix_label,
        "begriffe": [{"wort": w, "haeufigkeit": tf[w], "gewicht": round(sc / maxs, 2)}
                     for w, sc in top],
    }


def main():
    digests = lade("digests")
    positionen = lade("positionen")
    with open(os.path.join(BASE, "wahl-fakten.json"), encoding="utf-8") as f:
        fakten = json.load(f)
    with open(os.path.join(BASE, "parteien-meta.json"), encoding="utf-8") as f:
        meta = json.load(f)

    # Klartext-Ebene (Bauplan §7.3): alltagssprachliche Texte, die die Programme
    # einordnen statt sie zu zitieren. Bewusst getrennt gehalten — sie sind das
    # Einzige in data.json, das nicht direkt aus einer Quelle stammt, und
    # brauchen deshalb ein eigenes „geprueft"-Flag.
    klartext = {"einzeiler": {}, "geprueft": False}
    kp = os.path.join(BASE, "klartext.json")
    if os.path.exists(kp):
        with open(kp, encoding="utf-8") as f:
            klartext = json.load(f)
    if not klartext.get("geprueft"):
        print("  ! klartext.json ist noch nicht redaktionell geprueft (geprueft: false)")

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

    # Die Vergleichsmenge: nur Listen mit ausformuliertem Programm plus BSW
    # (Landesrahmen, deshalb ueberall markiert). Alles, was auf der Seite als
    # Verteilung, Rang oder Streitgrad erscheint, wird ueber DIESE Menge
    # gerechnet — nicht ueber alle 16. Sonst zaehlen Listen mit, die gar kein
    # Programm haben, und die Zahlen neben einer 9-spaltigen Matrix stimmen
    # nicht mit dem ueberein, was danebensteht.
    vergleich = [s for s in reihenfolge
                 if QUELLENART.get(s, ("", ""))[0] in ("voll", "landes")]

    themen_rang = []
    for k, m in THEMEN.items():
        in_v = [s for s in vergleich if s in abdeckung]
        themen_rang.append({
            "key": k, "label": m["label"], "kurz": m["kurz"],
            "erwaehnt": sum(1 for s in in_v if abdeckung[s][k]["praegnanz"] >= 1),
            "mit_abschnitt": sum(1 for s in in_v if abdeckung[s][k]["praegnanz"] >= 2),
            "schwerpunkt": sum(1 for s in in_v if abdeckung[s][k]["praegnanz"] == 3),
            "positionen_gesamt": sum(abdeckung[s][k]["anzahl"] for s in in_v),
            "thesen": len(ids_thema[k]),
        })
    themen_rang.sort(key=lambda x: (-x["erwaehnt"], -x["positionen_gesamt"]))

    # Streitgrad je These: mittlerer paarweiser Abstand unter allen Listen, die sich
    # ueberhaupt aeussern. 0 = voellige Einigkeit, 1 = maximale Spaltung.
    #
    # `belastbar` haelt die MIN_N-Schranke einmal zentral fest, statt sie in jeder
    # Ansicht zu wiederholen: Ohne sie fuehrt eine These mit n=2 die Streitliste an,
    # weil zwei Listen sich zufaellig gegenueberstehen.
    thesen_stat = []
    for t in thesen:
        werte = [flat[s][t["id"]] for s in vergleich
                 if s in flat and flat[s].get(t["id"]) is not None]
        paar_abstaende = [abs(a - b) / 2 for i, a in enumerate(werte) for b in werte[i + 1:]]
        thesen_stat.append({
            "id": t["id"], "thema": t["thema"], "these": t["these"], "hinweis": t.get("hinweis"),
            "n": len(werte),
            "dafuer": sum(1 for w in werte if w == 1),
            "teils": sum(1 for w in werte if w == 0),
            "dagegen": sum(1 for w in werte if w == -1),
            "streit": round(sum(paar_abstaende) / len(paar_abstaende), 3) if paar_abstaende else None,
            "belastbar": len(werte) >= MIN_N,
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

    # ── Ausbau (08.08.): Landkarte, Alleinstellungen, Sprachprofile ──────────
    landkarte = landkarte_koordinaten(paare, vergleich)

    alleinstellungen = finde_alleinstellungen(flat, positionen, thesen, vergleich)

    alle_texte = {}
    for s in vergleich:
        tp2 = os.path.join(BASE, "programme", f"{s}.txt")
        if os.path.exists(tp2):
            with open(tp2, encoding="utf-8") as f:
                # Seitenmarker und URLs raus, sonst landen sie in der Statistik
                txt = re.sub(r"=====\s*\[[^\]]+\]\s*=====", " ", f.read())
                alle_texte[s] = re.sub(r"https?://\S+", " ", txt)
    sprache = {s: sprachprofil(s, alle_texte) for s in alle_texte}

    daten = {
        "fakten": fakten, "meta": meta, "themen": THEMEN, "themen_rang": themen_rang,
        "landkarte": landkarte, "alleinstellungen": alleinstellungen, "sprache": sprache,
        "quellenart": quellenart, "thesen_stat": thesen_stat, "quellen": quellen,
        "thesen": thesen, "digests": digests, "positionen": positionen,
        "paare": paare, "abdeckung": abdeckung,
        "min_n": MIN_N, "min_n_thema": MIN_N_THEMA, "reihenfolge": reihenfolge,
        "vergleich": vergleich, "klartext": klartext,
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
