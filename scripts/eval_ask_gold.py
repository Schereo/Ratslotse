#!/usr/bin/env python3
"""Gold-Fälle für „Frag den Rat“: dieselben Fälle wie die Gründliche Recherche.

``scripts/eval_deep_gold.py`` misst den langen Bericht; hier läuft dieselbe
Faktenliste (``eval/cases_deep_gold.json``) gegen die schnelle Antwort — über
den ECHTEN Weg: ``POST /api/council/ask`` am laufenden Dienst, wie
``scripts/frage_probe.py``. Die Suite ``ki-frage`` (``eval/run_qa.py``) baut
die Kandidaten dagegen selbst nach und prüft, ob Beschlüsse zitiert werden —
ob eine Aussage aus einer Debatte in der Antwort steht, sieht sie nicht. Genau
daran hing der Befund vom 30.09.2026 (Schlossplatz-Spielplatz).

Drei Stufen, damit ein Fehlschlag seine Ursache verrät:

1. **Material der Antwort** — lagen die Belegstellen im Kontext (Quellen,
   Debatten, Presse aus dem Quellen-Ereignis)?
2. **Material des Bausteins** — stehen sie wenigstens im nachgeladenen
   Debatten-Baustein unter der Antwort (``POST /api/council/debates``)?
3. **Antwort** — Pflichtfakten und verbotene Behauptungen, derselbe Richter
   wie beim Bericht.

Auf dem Server (Embeddings, echte Daten)::

    .venv/bin/python scripts/eval_ask_gold.py --label nach-1601
    .venv/bin/python scripts/eval_ask_gold.py --label x --nur stadion-stand

Das Token entsteht wie bei der Rauchprobe (``rauchprobe.token_bauen``); die
Fragen zählen als Fragen dieses Kontos. Ergebnis unter
``data/eval_gold/ask-<label>.json`` (``data/`` überlebt den Deploy).
"""
from __future__ import annotations

import argparse
import importlib
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL))
sys.path.insert(0, str(WURZEL / "scripts"))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(WURZEL / ".env")

from kern import llm  # noqa: E402

CASES = WURZEL / "eval" / "cases_deep_gold.json"
FRAGEN_JE_FENSTER = 9
FENSTER_S = 600
ZIEL = WURZEL / "data" / "eval_gold"


def _post(basis: str, token: str, pfad: str, body: dict, strom: bool = False):
    anfrage = urllib.request.Request(
        f"{basis}{pfad}", data=json.dumps(body).encode("utf-8"), method="POST",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json",
                 "Accept": "text/event-stream" if strom else "application/json"})
    return urllib.request.urlopen(anfrage, timeout=300)


def befreien(basis: str, token: str, info: str) -> bool:
    """Das Messkonto von den Rate-Limitern befreien (``web_users.limits_unlocked``).

    Tims Freigabe 02.10.2026: „die 10 Fragen in 10 Minuten kannst du zum
    Testen brechen“. Geht über denselben Admin-Endpunkt wie das Panel; das
    Recherche-Kontingent bleibt, wie es ist. Zurücknehmen: Admin-Panel →
    Web-Nutzer*innen. True, wenn das Konto danach befreit ist.
    """
    m = re.match(r"Konto (\d+)", info)
    if not m:
        return False
    uid = m.group(1)
    kopf = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    try:
        with urllib.request.urlopen(urllib.request.Request(
                f"{basis}/api/admin/users/{uid}", headers=kopf), timeout=30) as a:
            konto = json.loads(a.read().decode("utf-8"))
        if konto.get("limits_unlocked"):
            return True
        body = {"deep_limit": konto.get("deep_limit"), "limits_unlocked": True}
        with urllib.request.urlopen(urllib.request.Request(
                f"{basis}/api/admin/users/{uid}/limits", data=json.dumps(body).encode("utf-8"),
                headers=kopf, method="PUT"), timeout=30) as a:
            frei = bool(json.loads(a.read().decode("utf-8")).get("limits_unlocked"))
        print(f"Messkonto {uid} vom Rate-Limit befreit "
              "(zurücknehmen: Admin-Panel → Web-Nutzer*innen).", flush=True)
        return frei
    except urllib.error.HTTPError as exc:
        print(f"Befreien nicht möglich ({exc.code}) — der Lauf drosselt sich selbst.", flush=True)
        return False


def fragen(basis: str, token: str, frage: str) -> dict:
    """Eine Frage über den Ereignis-Strom → Antwort, Quellen-Ereignis, Dauer."""
    t0 = time.time()
    text: list[str] = []
    quellen: dict = {}
    zeiten: dict = {}
    with _post(basis, token, "/api/council/ask", {"question": frage, "history": []},
               strom=True) as antwort:
        for roh in antwort:
            zeile = roh.decode("utf-8", "replace").strip()
            if not zeile.startswith("data:"):
                continue
            try:
                e = json.loads(zeile[5:].strip())
            except ValueError:
                continue
            if e.get("type") == "token":
                text.append(e.get("text") or "")
            elif e.get("type") == "sources":
                quellen = e
            elif e.get("type") == "done":
                zeiten = e.get("timings") or {}
    return {"antwort": "".join(text), "quellen": quellen, "zeiten": zeiten,
            "dauer_s": round(time.time() - t0, 1)}


#: Die vier Ursachen eines verfehlten Pflichtfakts — je nachdem, ob das
#: Material dafür im Kontext der Antwort stand. Die Einteilung folgt der
#: Trennung von Suche und Antwort (Barnett et al. 2024: „missing content“ /
#: „not in context“ / „not extracted“; Leung et al. 2026, E4/E7 gegen E12).
URSACHEN = ("weggelassen", "abgeschnitten", "nicht_gefunden", "teilweise", "ohne_material")
URSACHE_TEXT = {
    "weggelassen": "Material im Prompt, Antwort lässt es weg",
    "abgeschnitten": "gefunden, aber hinter dem Prompt-Schnitt",
    "nicht_gefunden": "Material fehlt im Kontext",
    "teilweise": "Material nur teilweise im Kontext",
    "ohne_material": "kein Material im Gold-Fall hinterlegt",
}


def ursache(fakt_id: str, material: list[dict],
            gefunden: list[dict] | None = None) -> str:
    """Warum fehlt ein Pflichtfakt? Deterministisch aus der Materialprüfung.

    ``material`` prüft gegen den PROMPT, ``gefunden`` gegen alle Kandidaten
    der Suche. Lag alles bei den Kandidaten, aber nicht im Prompt, hat der
    Schnitt nach Rang 20 es weggeworfen — ein Fehler der Rangfolge (E7),
    nicht der Antwort."""
    ms = [m for m in material if fakt_id in (m.get("fuer") or [])]
    if not ms:
        return "ohne_material"
    da = [m["vorhanden"] for m in ms]
    if all(da):
        return "weggelassen"
    if gefunden is not None:
        gs = [m["vorhanden"] for m in gefunden if fakt_id in (m.get("fuer") or [])]
        if gs and all(gs):
            return "abgeschnitten"
    return "teilweise" if any(da) else "nicht_gefunden"


def kontext_recall(material: list[dict]) -> tuple[int, int]:
    """(Belege im Kontext, Belege insgesamt) — die Kennzahl der SUCHE.

    Sie braucht keinen Richter und streut deshalb nicht wie die Abdeckung:
    Am 17.10.2026 ergab derselbe Code einmal 51 %, einmal 45 % Abdeckung.
    Ob eine Änderung an der Suche hilft, zeigt diese Zahl."""
    return sum(1 for m in material if m["vorhanden"]), len(material)


def fehlerbild_zeilen(ergebnisse: list[dict], faelle: list[dict]) -> list[str]:
    """Kontext-Recall und die Ursachen der verfehlten Fakten, nach Gewicht."""
    gewicht = {(f["id"], p["id"]): p.get("gewicht", 1)
               for f in faelle for p in f.get("pflicht", [])}
    da = gesamt = 0
    n: dict[str, int] = dict.fromkeys(URSACHEN, 0)
    g: dict[str, int] = dict.fromkeys(URSACHEN, 0)
    for e in ergebnisse:
        a, b = kontext_recall(e["material"])
        da, gesamt = da + a, gesamt + b
        for fid in e["wertung"]["verfehlt"]:
            u = ursache(fid, e["material"], e.get("material_gefunden"))
            n[u] += 1
            g[u] += gewicht.get((e["id"], fid), 1)
    zeilen = [f"KONTEXT-RECALL: {da}/{gesamt} Belege im Kontext "
              f"({da / gesamt:.0%})" if gesamt else "KONTEXT-RECALL: –"]
    for u in URSACHEN:
        zeilen.append(f"  verfehlt, {URSACHE_TEXT[u]}: {n[u]} (Gewicht {g[u]})")
    return zeilen


def material_form(quellen: dict, debatten: list[dict] | None = None,
                  kontext_ids: list[int] | None = None,
                  debatten_ids: list[int] | None = None) -> dict:
    """Quellen-Ereignis (bzw. nachgeladene Debatten) in die Form, die
    ``eval_deep_gold._material_pruefen`` liest: Debatten tragen dort
    ``session_date``/``text``, im Web-Vertrag ``date``/``excerpt``.

    ``kontext_ids``: nur die Beschlüsse, die wirklich im Prompt standen
    (``timings.kontext_ids``). Das Quellen-Ereignis nennt alle Kandidaten,
    der Prompt bekommt 20 plus Akte."""
    deb = debatten if debatten is not None else (quellen.get("debates") or [])
    if debatten_ids is not None:
        # Kontext-Diät: Nur diese Wortbeiträge standen im Prompt.
        im_prompt = set(debatten_ids)
        deb = [d for d in deb if d.get("id") in im_prompt]
    quellen_liste = quellen.get("sources") or []
    if kontext_ids is not None:
        im = set(kontext_ids)
        quellen_liste = [c for c in quellen_liste if c.get("id") in im]
    return {
        "candidates": quellen_liste,
        "debates": [{"session_date": d.get("date") or d.get("session_date"),
                     "text": d.get("excerpt") or d.get("text") or "",
                     "speaker": d.get("speaker")} for d in deb],
        "press_releases": quellen.get("press_releases") or [],
        "attachments": quellen.get("attachments") or [],
        "chart": quellen.get("chart"),
        # Tagesordnungspunkte aus dem Sitzungs-Baustein — die einzige Stelle,
        # an der „Frag den Rat“ heute angekündigte Stationen zeigt.
        "agenda": [{"session_date": s.get("session_date"), "committee": s.get("committee"),
                    "title": a.get("title")}
                   for s in quellen.get("sessions") or [] for a in s.get("agenda") or []],
    }


def lauf(basis: str, label: str, nur: str | None, konto: str | None,
         frei_machen: bool = False) -> Path:
    from scripts import eval_deep_gold as gold

    rauchprobe = importlib.import_module("rauchprobe")
    token, info = rauchprobe.token_bauen(WURZEL, konto)
    if not token:
        raise SystemExit(f"Kein Token: {info}")
    frei = befreien(basis, token, info) if frei_machen else False
    cases = json.loads(CASES.read_text(encoding="utf-8"))
    cases = gold.faelle_waehlen(cases, "ask", nur)
    ergebnisse = []
    gestellt: list[float] = []
    for case in cases:
        # /ask erlaubt einem Konto 10 Fragen je 10 Minuten
        # (``ratelimit.qa_limiter``). Sieben Fälle passten hinein, zwanzig
        # nicht: Der Grundlinien-Lauf vom 02.10.2026 brach nach zehn Fällen mit
        # 429 ab. Statt das Messkonto zu befreien (eine Kontoänderung auf Prod)
        # hält sich der Lauf an neun je Fenster — eine bleibt für den Menschen,
        # dem das Konto gehört.
        if not frei and len(gestellt) >= FRAGEN_JE_FENSTER:
            warten = FENSTER_S - (time.time() - gestellt[-FRAGEN_JE_FENSTER]) + 5
            if warten > 0:
                print(f"  Rate-Limit: warte {warten:.0f} s", flush=True)
                time.sleep(warten)
        for versuch in range(3):
            # Das Token gilt fünf Minuten (rauchprobe.token_bauen) — je Fall
            # und nach jedem Warten neu.
            token, info = rauchprobe.token_bauen(WURZEL, konto)
            if not token:
                raise SystemExit(f"Kein Token: {info}")
            try:
                gestellt.append(time.time())
                r = fragen(basis, token, case["question"])
                break
            except urllib.error.HTTPError as exc:
                if exc.code != 429 or versuch == 2:
                    raise
                print(f"  429 — warte {FENSTER_S // 2} s", flush=True)
                time.sleep(FENSTER_S // 2)
        q = r["quellen"]
        zeiten = r.get("zeiten") or {}
        material = gold._material_pruefen(case, material_form(
            q, kontext_ids=zeiten.get("kontext_ids"), debatten_ids=zeiten.get("kontext_debatten_ids")))
        material_gefunden = gold._material_pruefen(case, material_form(q))
        baustein: list[dict] = []
        try:
            with _post(basis, token, "/api/council/debates", {
                    "question": case["question"],
                    "decision_ids": [s["id"] for s in (q.get("sources") or [])][:40]}) as a:
                baustein = json.loads(a.read().decode("utf-8")).get("debates") or []
        except Exception as exc:  # noqa: BLE001 — der Baustein ist Zusatz
            print(f"  Baustein nicht geladen: {exc}", flush=True)
        # Was die Antwort schon hatte, steht auch im Baustein (er hängt an).
        material_baustein = gold._material_pruefen(
            case, material_form(q, (q.get("debates") or []) + baustein))
        urteil = gold._judge(case, r["antwort"])
        wertung = gold._bewerten(case, urteil, punktregel=True)
        ergebnisse.append({
            "id": case["id"], "question": case["question"], "dauer_s": r["dauer_s"],
            "wertung": wertung, "material": material, "material_baustein": material_baustein,
            "material_gefunden": material_gefunden,
            "kontext_recall": list(kontext_recall(material)),
            "ursachen": {fid: ursache(fid, material, material_gefunden)
                         for fid in wertung["verfehlt"]},
            "urteil": urteil, "antwort": r["antwort"],
            "gelesen": {"fragetyp": q.get("qtype"),
                        "beschluesse": len(q.get("sources") or []),
                        "debatten": [f"{d.get('date')} · {d.get('speaker')}"
                                     for d in (q.get("debates") or [])],
                        "baustein": len(baustein),
                        # Was die Suche selbst getan hat: Nachrecherche
                        # (Anfragen, neue Funde) und ein gewählter Ort als
                        # Hinweis — ohne das lässt sich ein Gold-Unterschied
                        # keinem Schritt zuordnen (17.10.2026).
                        "nachrecherche": (r.get("zeiten") or {}).get("nachrecherche"),
                        "ort_hinweis": (r.get("zeiten") or {}).get("ort_hinweis")},
        })
        fehlt = [x["id"] for x in material if not x["vorhanden"]]
        fehlt_b = [x["id"] for x in material_baustein if not x["vorhanden"]]
        print(f"{case['id']}: Abdeckung {wertung['abdeckung']:.0%}, verfehlt {wertung['verfehlt']}, "
              f"Verstöße {wertung['verstoesse']}, Material fehlt {fehlt} (im Baustein: {fehlt_b}) → "
              f"{'BESTANDEN' if wertung['bestanden'] else 'NICHT bestanden'} ({r['dauer_s']} s)",
              flush=True)
    n = len(ergebnisse) or 1
    for zeile in fehlerbild_zeilen(ergebnisse, cases):
        print(zeile, flush=True)
    print(f"GESAMT: Abdeckung {sum(e['wertung']['abdeckung'] for e in ergebnisse) / n:.0%}, "
          f"bestanden {sum(e['wertung']['bestanden'] for e in ergebnisse)}/{len(ergebnisse)}, "
          f"Verstöße {sum(len(e['wertung']['verstoesse']) for e in ergebnisse)}, "
          f"Richter-Kosten ${llm.session_cost()['usd']:.3f}", flush=True)
    ZIEL.mkdir(parents=True, exist_ok=True)
    out = ZIEL / f"ask-{label}.json"
    out.write_text(json.dumps({"label": label, "judge": gold.JUDGE_MODEL, "cases": ergebnisse},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"→ {out}")
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Gold-Fälle für Frag den Rat")
    ap.add_argument("--label", required=True)
    ap.add_argument("--nur", default=None, help="nur diese Fälle (ids, durch Komma)")
    ap.add_argument("--basis", default="http://127.0.0.1:8000")
    ap.add_argument("--konto", default=None, help="Konto-Adresse fürs Token (Vorgabe wie Rauchprobe)")
    ap.add_argument("--befreien", action="store_true",
                    help="Messkonto von den Rate-Limitern befreien (Admin-Endpunkt)")
    a = ap.parse_args()
    lauf(a.basis, a.label, a.nur, a.konto, frei_machen=a.befreien)


if __name__ == "__main__":
    main()
