"""Proof of Concept „Mein Viertel": Was ändert sich in den nächsten Jahren?

Tims Frage (05.09.2026): Trägt ein Viertel-Feature, wenn es fast 100 %
präzise sein muss — und wird es interessant, wenn wir statt „Beschlüsse aus
deinem Viertel" ableiten, WAS sich dort in den kommenden Jahren ändert?

Drei Stufen, drei Unterbefehle:

    sammeln   — Kandidaten je Ortsbereich aus der Orts-Pipeline (streng und weit),
                samt Vorlagentext, plus B-Plan-Umringe der Stadt, Baustellen und
                Investitionsprogramm-Vorhaben mit Straßennamen
    bewerten  — zweite Stufe per LLM: gehört der Beschluss WIRKLICH ins Viertel,
                ändert sich etwas, was, wann (mit Cache je Beschluss)
    bericht   — Markdown je Viertel: Zeitleiste „Was ändert sich bis 2030"
                plus Kennzahlen zur Präzision

Alles landet in einem Arbeitsverzeichnis (``--ziel``), nichts in der DB.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from council import geo  # noqa: E402
from council.impact import vorlagen_kern  # noqa: E402
from council.locations import affects_whole_city  # noqa: E402

MODEL = os.environ.get("VIERTEL_POC_MODEL", "openai/gpt-5.6-luna")
BATCH = 5
STRENGE_METHODEN = {"district_list", "place_catalog"}


def _slug(name: str) -> str:
    return (name.lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue")
            .replace("ß", "ss").replace(" ", "-"))


# ---------------------------------------------------------------- sammeln

def _conn(db: Path) -> sqlite3.Connection:
    c = sqlite3.connect(db)
    c.row_factory = sqlite3.Row
    return c


def kandidaten(conn: sqlite3.Connection, viertel: str, seit: str, min_anteil: float) -> list[dict]:
    """Beschlüsse, deren Orte (nach der Pipeline) im Viertel liegen.

    ``streng`` = Ort aus dem Titel oder aus Stadtteil-/Katalog-Treffer; das
    war in der Vormessung die Menge mit ~85–90 % Präzision. ``weit`` nimmt
    alle Methoden dazu (Vorlagentext per LLM/Regex) — mehr Treffer, ~50 %
    Rauschen. Beide gehen durch dieselbe zweite Stufe.
    """
    rows = conn.execute(
        """
        SELECT d.id, d.title, d.summary, d.official_text, d.outcome, d.kind, d.amount_eur,
               d.importance, d.kvonr, d.policy_field,
               se.session_date, se.committee,
               dl.location_slug, dl.source, dl.method, dl.confidence, dl.evidence,
               l.name AS ort, l.kind AS ortart, ld.share
        FROM council_decision_locations dl
        JOIN council_locations l ON l.slug = dl.location_slug
        JOIN council_location_districts ld ON ld.location_slug = dl.location_slug
        JOIN council_decisions d ON d.id = dl.decision_id
        JOIN council_sessions se ON se.ksinr = d.ksinr
        WHERE ld.district = ? AND se.session_date >= ? AND ld.share >= ?
        ORDER BY se.session_date DESC
        """, (viertel, seit, min_anteil)).fetchall()
    je_beschluss: dict[int, dict] = {}
    for r in rows:
        d = je_beschluss.setdefault(r["id"], {
            "id": r["id"], "title": r["title"], "summary": r["summary"],
            "official_text": r["official_text"], "outcome": r["outcome"], "kind": r["kind"],
            "amount_eur": r["amount_eur"], "importance": r["importance"], "kvonr": r["kvonr"],
            "policy_field": r["policy_field"], "date": r["session_date"],
            "committee": r["committee"], "orte": [], "streng": False,
        })
        streng = r["source"] == "title" or r["method"] in STRENGE_METHODEN
        d["orte"].append({
            "name": r["ort"], "art": r["ortart"], "anteil": round(r["share"], 2),
            "quelle": r["source"], "methode": r["method"], "konfidenz": r["confidence"],
            "beleg": (r["evidence"] or "")[:160], "streng": streng,
        })
        d["streng"] = d["streng"] or streng
    out = []
    for d in je_beschluss.values():
        if affects_whole_city(d["title"]):
            d["stadtweit_regel"] = True
        # weitere Ortsbereiche derselben Orte — eine Straße durch drei Viertel
        andere = conn.execute(
            "SELECT DISTINCT ld.district FROM council_decision_locations dl "
            "JOIN council_location_districts ld ON ld.location_slug = dl.location_slug "
            "WHERE dl.decision_id = ? AND ld.district != ?", (d["id"], viertel)).fetchall()
        d["andere_viertel"] = [a[0] for a in andere]
        if d["kvonr"]:
            t = conn.execute(
                "SELECT raw_text, proposed_decision, financial_impact FROM council_templates "
                "WHERE kvonr = ?", (d["kvonr"],)).fetchone()
            if t:
                d["vorlage"] = vorlagen_kern(t["raw_text"])[:2600] if t["raw_text"] else None
                d["beschlussvorschlag"] = (t["proposed_decision"] or "")[:600] or None
                d["finanzen"] = (t["financial_impact"] or "")[:300] or None
        out.append(d)
    return out


def bplaene(pfad: Path, viertel: str) -> list[dict]:
    """B-Plan-Umringe der Stadt (openGEOdata, dl-de/zero), per Geometrie dem
    Ortsbereich zugeordnet. Der Datensatz führt nur RECHTSVERBINDLICHE Pläne —
    laufende Verfahren stehen nicht darin (gemessen 05.09.2026: 0 Pläne mit
    Aufstellungs- aber ohne Satzungsbeschluss)."""
    if not pfad.exists():
        return []
    d = json.load(open(pfad, encoding="utf-8"))
    out = []
    for f in d["features"]:
        p = f["properties"]
        st = geo.ortsbereiche_der_geometrie(f["geometry"])
        tot = sum(st.values()) or 1
        anteil = st.get(viertel, 0) / tot
        if anteil < 0.3:
            continue
        rv = (p.get("rechtsverbindlich") or "")[:10]
        out.append({
            "nr": p.get("Planverfahren"), "name": p.get("Name"), "anteil": round(anteil, 2),
            "aufstellung": (p.get("Aufstellungsbeschluss_Rat_VA") or "")[:10],
            "satzung": (p.get("Satzungsbeschluss_Rat_VA") or "")[:10],
            "rechtsverbindlich": rv, "flaeche_m2": int(p.get("Shape__Area") or 0),
            "link_stol": p.get("Link_StOL"),
        })
    return sorted(out, key=lambda r: r["rechtsverbindlich"], reverse=True)


def strassen_im_viertel(conn: sqlite3.Connection, viertel: str, min_anteil: float = 0.5) -> list[str]:
    rows = conn.execute(
        "SELECT l.name FROM council_locations l JOIN council_location_districts ld "
        "ON ld.location_slug = l.slug WHERE ld.district = ? AND ld.share >= ? "
        "AND l.kind IN ('street','square','building','area','other')", (viertel, min_anteil)).fetchall()
    return sorted({r[0] for r in rows}, key=len, reverse=True)


def investitionen(conn: sqlite3.Connection, strassen: list[str]) -> list[dict]:
    """Vorhaben des jüngsten Investitionsprogramms, deren Bezeichnung einen
    Ort des Viertels nennt. Gesamtbetrag über alle Jahre des Programms."""
    jahr = conn.execute("SELECT MAX(year) FROM council_investment_measures").fetchone()[0]
    if not jahr:
        return []
    rows = conn.execute(
        "SELECT code, label, grand_total, details FROM council_investment_measures "
        "WHERE year = ? AND level = 'measure'", (jahr,)).fetchall()
    out = []
    for r in rows:
        label = r["label"] or ""
        for s in strassen:
            if len(s) < 6:
                continue
            if re.search(re.escape(s) + r"(?![a-zäöüß])", label, re.IGNORECASE):
                out.append({"programm": jahr, "code": r["code"], "label": label,
                            "betrag": r["grand_total"], "ort": s})
                break
    return out


BAUSTELLEN_SEITEN = {
    # Straße auf der Baustellen-Seite der Stadt → Unterseite (Stand 04.09.2026)
    "Alexanderstraße": "alexanderstrasse", "Donnerschweer Straße": "asphalterneuerung-in-der-donnerschweer-strasse",
    "Tirpitzstraße": "ausbau-der-tirpitzstrasse", "Ziegelhofstraße": "ausbau-der-ziegelhofstrasse",
    "Sandweg": "ausbau-sandweg", "Peterstraße": "ausbau-wichtiger-kabeltrasse",
    "Butjadinger Straße": "butjadinger-strasse", "Huntebrücke": "huntebruecke",
    "Cäcilienbrücke": "neubau-caecilienbruecke", "Tweelbäker Tredde": "tweelbaeker-tredde",
}


def baustellen(conn: sqlite3.Connection, viertel: str, seiten_dir: Path | None) -> list[dict]:
    """Größere Baumaßnahmen von oldenburg.de, dem Viertel über die Orts-Tabelle
    zugeordnet (Straße → Ortsbereich mit Mehrheitsanteil)."""
    out = []
    for strasse, seite in BAUSTELLEN_SEITEN.items():
        row = conn.execute(
            "SELECT ld.district, ld.share FROM council_locations l JOIN council_location_districts ld "
            "ON ld.location_slug = l.slug WHERE l.name = ? ORDER BY ld.share DESC LIMIT 1",
            (strasse,)).fetchone()
        if not row or row["district"] != viertel:
            continue
        text = None
        if seiten_dir and (seiten_dir / f"bau_{seite}.html").exists():
            import html as _html
            h = open(seiten_dir / f"bau_{seite}.html", encoding="utf-8", errors="replace").read()
            m = re.search(r"<main.*?</main>", h, re.S)
            body = m.group(0) if m else h
            body = re.sub(r"<(script|style|nav|footer|header).*?</\1>", "", body, flags=re.S)
            text = re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", " ", body))).strip()
            text = text.split("Kontaktformular .", 1)[-1].strip()[:900]
        out.append({"ort": strasse, "anteil": round(row["share"], 2),
                    "url": f"https://www.oldenburg.de/startseite/stadtraum/verkehr-mobilitaet/baustellen/{seite}.html",
                    "text": text})
    return out


def cmd_sammeln(a: argparse.Namespace) -> None:
    conn = _conn(a.db)
    seit = (date.today() - timedelta(days=30 * a.monate)).isoformat()
    ziel = Path(a.ziel)
    ziel.mkdir(parents=True, exist_ok=True)
    for v in a.viertel:
        kand = kandidaten(conn, v, seit, a.min_anteil)
        strassen = strassen_im_viertel(conn, v)
        daten = {
            "viertel": v, "seit": seit, "stand": date.today().isoformat(),
            "kandidaten": kand,
            "bplaene": bplaene(Path(a.bplan), v) if a.bplan else [],
            "investitionen": investitionen(conn, strassen),
            "baustellen": baustellen(conn, v, Path(a.baustellen) if a.baustellen else None),
        }
        pfad = ziel / f"{_slug(v)}.json"
        json.dump(daten, open(pfad, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        streng = sum(1 for k in kand if k["streng"])
        mit_vorlage = sum(1 for k in kand if k.get("vorlage"))
        print(f"{v}: {len(kand)} Kandidaten ({streng} streng, {mit_vorlage} mit Vorlagentext), "
              f"{len(daten['bplaene'])} B-Pläne, {len(daten['investitionen'])} Investitionen, "
              f"{len(daten['baustellen'])} Baustellen → {pfad}")


# ---------------------------------------------------------------- bewerten

SYSTEM = """Du prüfst für die Bürger-App Ratslotse, ob ein Beschluss des Oldenburger Stadtrats für die Bewohner*innen EINES bestimmten Ortsbereichs (kurz: Viertel) etwas konkret verändert.

Die Zuordnung zum Viertel stammt aus einer automatischen Ortserkennung und ist manchmal falsch. Sei streng: Ein fremdes Vorhaben im Viertel-Feed zerstört das Vertrauen; ein ausgelassener Treffer ist verschmerzbar. Erfinde nichts, was nicht im Text steht.

Bewerte je Beschluss:
- "bezug":
  "viertel" = der Gegenstand liegt (überwiegend) in diesem Viertel und betrifft dessen Bewohner*innen spürbar: Bau, Umbau, Abriss, Sperrung, neue oder geschlossene Einrichtung, Straßen-/Radwegumbau, Bebauungsplan, Park, Schule, Kita, Spielplatz, Verkehrsregelung, Wohnungsbau.
  "stadtweit" = gilt für die ganze Stadt oder eine Institution mit stadtweiter Wirkung (Klinikum, Verwaltung, Theater, Netzbetreiber, Buslinien-Netz), das Viertel ist nur Standort oder Beispiel.
  "anderswo" = der konkrete Abschnitt/Ort liegt in einem anderen Viertel (z. B. eine lange Straße, der genannte Abschnitt ist woanders) oder der Ort wurde falsch erkannt.
  "nur_erwaehnt" = der Ortsname ist Namensbestandteil (Gedenkstätte, Firma, Sitzungsort, Vereinsname), historischer Bezug oder Vergleich — vor Ort ändert sich nichts.
- "aendert_sich": true nur, wenn für Bewohner*innen etwas Sichtbares oder Praktisches passiert oder fest geplant ist. Berichte, Kenntnisnahmen, Sachstände ohne Entscheidung, Widmungen/Einziehungen, Personalien, Anfragen, reine Vergaben ohne neue Wirkung, Ablehnungen ohne Folge → false.
- "was": genau ein Satz, höchstens 160 Zeichen, Alltagssprache, beginnt mit dem Gegenstand (z. B. "Der Sandweg wird bis Juli 2027 mit neuen Leitungen und neuer Fahrbahn ausgebaut."). Keine Ratsfloskeln ("Der Rat beschließt"), keine Vorlagen-Nummern. Bei aendert_sich=false: kurz, was der Beschluss ist.
- "wann": Jahr oder Zeitraum als Text ("2027", "2026–2028", "Sommer 2027"), NUR wenn der Text es hergibt, sonst null.
- "stand": "geplant" | "beschlossen" | "in_bau" | "fertig" | "abgelehnt" | "bericht".
- "kategorie": "wohnen_bauen" | "verkehr" | "schule_kita" | "gruen_umwelt" | "kultur_sport_soziales" | "sonstiges".
- "sicher": 0–100, wie sicher du bist, dass bezug UND aendert_sich stimmen.
- "grund": ein knapper Halbsatz, warum.

Antworte als JSON: {"bewertungen": [{"id": …, "bezug": …, "aendert_sich": …, "was": …, "wann": …, "stand": …, "kategorie": …, "sicher": …, "grund": …}, …]} — genau ein Eintrag je id."""


def _beschluss_text(k: dict) -> str:
    orte = ", ".join(f"{o['name']} ({o['art']}, Anteil im Viertel {o['anteil']}, "
                     f"erkannt aus {o['quelle']}/{o['methode']})" for o in k["orte"])
    andere = ", ".join(k.get("andere_viertel") or []) or "keine"
    teile = [
        f"id {k['id']}: {k['title']}",
        f"  Sitzung: {k['date']} · {k['committee']} · Ergebnis: {k.get('outcome') or '?'} · Art: {k.get('kind')}",
        f"  Erkannte Orte: {orte}",
        f"  Dieselben Orte berühren auch: {andere}",
    ]
    if k.get("summary"):
        teile.append(f"  Kurzfassung: {k['summary'][:700]}")
    if k.get("official_text"):
        teile.append(f"  Beschlusstext: {k['official_text'][:900]}")
    if k.get("beschlussvorschlag"):
        teile.append(f"  Beschlussvorschlag: {k['beschlussvorschlag']}")
    if k.get("finanzen"):
        teile.append(f"  Finanzen: {k['finanzen']}")
    if k.get("vorlage"):
        teile.append(f"  Vorlage (Auszug): {k['vorlage']}")
    return "\n".join(teile)


def bewerte_batch(viertel: str, batch: list[dict]) -> dict[int, dict]:
    from kern import llm
    user = (f"Viertel: {viertel} (Ortsbereich der Stadt Oldenburg)\n\n"
            + "\n\n".join(_beschluss_text(k) for k in batch))
    resp = llm.chat_complete(
        model=MODEL,
        response_format={"type": "json_object"},
        messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}],
        max_tokens=3000, temperature=0,
        extra_body={"reasoning": {"effort": "low"}},
        _feature="impact_rating",  # PoC: Kostenzählung mit dem Nachbarn teilen
    )
    data = json.loads(resp.choices[0].message.content or "{}")
    out: dict[int, dict] = {}
    for b in data.get("bewertungen") or []:
        try:
            out[int(b["id"])] = b
        except (KeyError, TypeError, ValueError):
            continue
    return out


def cmd_bewerten(a: argparse.Namespace) -> None:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    if a.env:
        load_dotenv(a.env, override=False)
    ziel = Path(a.ziel)
    cache_pfad = ziel / "bewertungen_cache.json"
    cache: dict[str, dict] = json.load(open(cache_pfad)) if cache_pfad.exists() else {}
    for v in a.viertel:
        pfad = ziel / f"{_slug(v)}.json"
        daten = json.load(open(pfad, encoding="utf-8"))
        offen = [k for k in daten["kandidaten"] if f"{v}:{k['id']}" not in cache or a.neu]
        print(f"{v}: {len(offen)} zu bewerten ({len(daten['kandidaten']) - len(offen)} aus Cache)")
        for i in range(0, len(offen), BATCH):
            batch = offen[i:i + BATCH]
            try:
                erg = bewerte_batch(v, batch)
            except Exception as exc:  # noqa: BLE001
                print(f"  ⚠️ Batch {i // BATCH + 1} fehlgeschlagen: {exc!r}")
                continue
            for k in batch:
                if k["id"] in erg:
                    cache[f"{v}:{k['id']}"] = erg[k["id"]]
            print(f"  Batch {i // BATCH + 1}/{(len(offen) + BATCH - 1) // BATCH}: {len(erg)}/{len(batch)}")
            json.dump(cache, open(cache_pfad, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        for k in daten["kandidaten"]:
            k["bewertung"] = cache.get(f"{v}:{k['id']}")
        json.dump(daten, open(pfad, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


# ---------------------------------------------------------------- bericht

KATEGORIE_LABEL = {
    "wohnen_bauen": "Wohnen & Bauen", "verkehr": "Verkehr", "schule_kita": "Schule & Kita",
    "gruen_umwelt": "Grün & Umwelt", "kultur_sport_soziales": "Kultur, Sport & Soziales",
    "sonstiges": "Sonstiges",
}


def _jahr(wann: str | None, fallback: str) -> str:
    if not wann:
        return "ohne Termin"
    m = re.findall(r"20\d\d", wann)
    return m[0] if m else "ohne Termin"


def _euro(x: float | None) -> str:
    if not x:
        return ""
    return f"{x / 1e6:.2f} Mio. €".replace(".", ",") if x >= 1e6 else f"{x:,.0f} €".replace(",", ".")


def cmd_bericht(a: argparse.Namespace) -> None:
    ziel = Path(a.ziel)
    md: list[str] = ["# PoC „Mein Viertel“ — Was ändert sich bis 2030?", "",
                     f"Stand {date.today().isoformat()}, Datenbasis: dev-Abzug, Beschlüsse der letzten 24 Monate, "
                     f"Modell `{MODEL}`.", ""]
    gesamt = Counter()
    for v in a.viertel:
        daten = json.load(open(ziel / f"{_slug(v)}.json", encoding="utf-8"))
        kand = daten["kandidaten"]
        bew = [k for k in kand if k.get("bewertung")]
        treffer = [k for k in bew if k["bewertung"].get("bezug") == "viertel"
                   and k["bewertung"].get("aendert_sich") and int(k["bewertung"].get("sicher") or 0) >= a.min_sicher]
        md += [f"## {v}", ""]
        c = Counter((k["bewertung"].get("bezug"), bool(k["bewertung"].get("aendert_sich"))) for k in bew)
        streng_c = Counter((k["bewertung"].get("bezug"), bool(k["bewertung"].get("aendert_sich")))
                           for k in bew if k["streng"])
        md += [f"Kandidaten: {len(kand)} (streng {sum(1 for k in kand if k['streng'])}), bewertet {len(bew)}, "
               f"**Treffer (Viertel + ändert sich, ≥ {a.min_sicher} sicher): {len(treffer)}**", "",
               "| Urteil | alle | davon streng |", "|---|---:|---:|"]
        for (bezug, aend), n in sorted(c.items(), key=lambda kv: -kv[1]):
            md.append(f"| {bezug} · {'ändert sich' if aend else 'ändert nichts'} | {n} | {streng_c.get((bezug, aend), 0)} |")
        gesamt.update(c)
        md.append("")
        # Zeitleiste
        md += ["### Zeitleiste aus Beschlüssen", ""]
        nach_jahr: dict[str, list[dict]] = defaultdict(list)
        for k in treffer:
            nach_jahr[_jahr(k["bewertung"].get("wann"), k["date"])].append(k)
        for jahr in sorted(nach_jahr, key=lambda j: (j == "ohne Termin", j)):
            md.append(f"**{jahr}**")
            md.append("")
            for k in sorted(nach_jahr[jahr], key=lambda k: k["date"], reverse=True):
                b = k["bewertung"]
                md.append(f"- {b.get('was')}  ")
                md.append(f"  <sub>{KATEGORIE_LABEL.get(b.get('kategorie'), b.get('kategorie'))} · "
                          f"{b.get('stand')} · {b.get('wann') or '–'} · sicher {b.get('sicher')} · "
                          f"Beschluss {k['id']} vom {k['date']} ({k['committee']}) · "
                          f"Orte: {', '.join(o['name'] for o in k['orte'])} · "
                          f"{'streng' if k['streng'] else 'weit'} · „{k['title'][:90]}“</sub>")
            md.append("")
        # Aussortiert
        md += ["<details><summary>Aussortiert (zum Gegenprüfen)</summary>", ""]
        for k in sorted(bew, key=lambda k: k["date"], reverse=True):
            b = k["bewertung"]
            if k in treffer:
                continue
            md.append(f"- **{b.get('bezug')}/{'ändert' if b.get('aendert_sich') else 'nichts'}** "
                      f"(sicher {b.get('sicher')}) {k['title'][:100]} — <sub>{b.get('grund')} · "
                      f"Orte: {', '.join(o['name'] for o in k['orte'])} · {'streng' if k['streng'] else 'weit'} · "
                      f"{k['id']}</sub>")
        md += ["", "</details>", ""]
        # Weitere Quellen
        if daten["baustellen"]:
            md += ["### Größere Baustellen (oldenburg.de)", ""]
            for b in daten["baustellen"]:
                md.append(f"- **{b['ort']}** — {(b.get('text') or '')[:260]}… [{b['url']}]({b['url']})")
            md.append("")
        if daten["investitionen"]:
            md += [f"### Investitionsprogramm {daten['investitionen'][0]['programm']} — Vorhaben mit Ortsbezug", ""]
            for i in daten["investitionen"]:
                md.append(f"- {i['label']} — {_euro(i['betrag'])} <sub>({i['ort']})</sub>")
            md.append("")
        if daten["bplaene"]:
            neu = [b for b in daten["bplaene"] if b["rechtsverbindlich"] >= "2020"]
            md += [f"### Bebauungspläne (Stadt-Geodaten): {len(daten['bplaene'])} im Viertel, "
                   f"{len(neu)} seit 2020 rechtsverbindlich", ""]
            for b in neu:
                md.append(f"- B-Plan {b['nr']} „{b['name']}“ — rechtsverbindlich seit {b['rechtsverbindlich']} "
                          f"(Aufstellung {b['aufstellung'] or '?'}), {b['flaeche_m2'] // 10000} ha")
            md.append("")
    md += ["## Summe über alle Viertel", "", "| Urteil | n |", "|---|---:|"]
    for (bezug, aend), n in sorted(gesamt.items(), key=lambda kv: -kv[1]):
        md.append(f"| {bezug} · {'ändert sich' if aend else 'ändert nichts'} | {n} |")
    out = ziel / "bericht.md"
    out.write_text("\n".join(md), encoding="utf-8")
    print(f"→ {out}")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--ziel", default="data/viertel_poc", help="Arbeitsverzeichnis")
    p.add_argument("--viertel", nargs="+", default=["Kreyenbrück", "Osternburg", "Eversten"])
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sammeln")
    s.add_argument("--db", type=Path, default=ROOT / "data" / "council.sqlite")
    s.add_argument("--monate", type=int, default=24)
    s.add_argument("--min-anteil", type=float, default=0.5)
    s.add_argument("--bplan", help="GeoJSON der B-Plan-Umringe (openGEOdata)")
    s.add_argument("--baustellen", help="Verzeichnis mit bau_*.html von oldenburg.de")
    s.set_defaults(fn=cmd_sammeln)
    b = sub.add_parser("bewerten")
    b.add_argument("--env", help="zusätzliche .env (z. B. Haupt-Checkout)")
    b.add_argument("--neu", action="store_true", help="Cache ignorieren")
    b.set_defaults(fn=cmd_bewerten)
    r = sub.add_parser("bericht")
    r.add_argument("--min-sicher", type=int, default=70)
    r.set_defaults(fn=cmd_bericht)
    vh = sub.add_parser("vorhaben")
    vh.add_argument("--env")
    vh.add_argument("--min-sicher", type=int, default=70)
    vh.set_defaults(fn=cmd_vorhaben)
    a = p.parse_args()
    a.fn(a)


# ---------------------------------------------------------------- vorhaben

VORHABEN_SYSTEM = """Du fasst für die Bürger-App Ratslotse Beschlüsse des Oldenburger Stadtrats, die alle EIN Viertel (Ortsbereich) betreffen, zu VORHABEN zusammen.

Ein Vorhaben ist eine Sache, die sich vor Ort verändert oder verändern soll: ein Neubau, ein Umbau, ein Bebauungsplan, eine Straßenmaßnahme, eine neue oder geänderte Einrichtung. Mehrere Beschlüsse (Ausschuss und Rat, Aufstellungsbeschluss und Satzungsbeschluss, Bericht und Antrag) gehören zum selben Vorhaben, wenn sie denselben Gegenstand haben. Berichte und Sachstände zählen mit: Sie sagen, wo das Vorhaben steht.

Nicht aufnehmen: reine Formalakte (Widmung, Einziehung ohne spürbare Folge, Straßenbenennung ohne Neubau), Jahresabschlüsse, stadtweite Themen, Personalien, Gedenken/Historisches ohne bauliche Folge.

Je Vorhaben:
- "name": kurz, konkret, Alltagssprache (z. B. "Neubau Grundschule Kreyenbrück"), höchstens 60 Zeichen
- "was": 1–2 Sätze, was sich für Bewohner*innen ändert; nur aus den Texten, nichts erfinden
- "stand": "idee" (Antrag/Prüfauftrag) | "planung" (Bericht, Aufstellungsbeschluss, Machbarkeit) | "beschlossen" | "in_bau" | "fertig" | "abgelehnt"
- "wann": Jahr oder Zeitraum als Text, NUR wenn ein Text es hergibt, sonst null
- "kategorie": "wohnen_bauen" | "verkehr" | "schule_kita" | "gruen_umwelt" | "kultur_sport_soziales" | "sonstiges"
- "beschluss_ids": alle zugehörigen ids
- "sicher": 0–100, wie sicher das Vorhaben wirklich in diesem Viertel liegt und richtig beschrieben ist

Antworte als JSON: {"vorhaben": [ … ]}, wichtigstes zuerst."""


def cmd_vorhaben(a: argparse.Namespace) -> None:
    from dotenv import load_dotenv
    from kern import llm
    load_dotenv(ROOT / ".env")
    if a.env:
        load_dotenv(a.env, override=False)
    ziel = Path(a.ziel)
    for v in a.viertel:
        pfad = ziel / f"{_slug(v)}.json"
        daten = json.load(open(pfad, encoding="utf-8"))
        im_viertel = [k for k in daten["kandidaten"] if (k.get("bewertung") or {}).get("bezug") == "viertel"
                      and int(k["bewertung"].get("sicher") or 0) >= a.min_sicher]
        zeilen = []
        for k in sorted(im_viertel, key=lambda k: k["date"]):
            b = k["bewertung"]
            zeilen.append(f"id {k['id']} · {k['date']} · {k['committee']} · Ergebnis {k.get('outcome') or '?'}\n"
                          f"  Titel: {k['title']}\n  Kurz: {b.get('was')} (Stand: {b.get('stand')}, wann: {b.get('wann')})\n"
                          f"  Zusammenfassung: {(k.get('summary') or '')[:400]}")
        user = f"Viertel: {v}\n\nBeschlüsse ({len(zeilen)}):\n\n" + "\n\n".join(zeilen)
        resp = llm.chat_complete(
            model=MODEL, response_format={"type": "json_object"},
            messages=[{"role": "system", "content": VORHABEN_SYSTEM}, {"role": "user", "content": user}],
            max_tokens=4000, temperature=0, extra_body={"reasoning": {"effort": "low"}},
            _feature="impact_rating")
        data = json.loads(resp.choices[0].message.content or "{}")
        daten["vorhaben"] = data.get("vorhaben") or []
        json.dump(daten, open(pfad, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"{v}: {len(im_viertel)} Beschlüsse → {len(daten['vorhaben'])} Vorhaben")
        for x in daten["vorhaben"]:
            print(f"  [{x.get('stand')}|{x.get('wann') or '–'}|{x.get('sicher')}] {x.get('name')} — {x.get('was')}  ids={x.get('beschluss_ids')}")


if __name__ == "__main__":
    main()
