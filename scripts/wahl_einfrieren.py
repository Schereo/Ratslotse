"""Eine gelaufene Wahl einfrieren: die Quelle sichern, die Referenz schreiben.

Der Votemanager der Stadt liefert die Open-Data-CSVs unter einer Adresse, die
den Wahltag trägt (``…/20260913/03403000/…``). Sie bleiben dort nicht ewig,
und die Ergebnisdarstellung der OB-Wahl hat gar keine CSV — sie lebt nur als
JSON hinter einer Wahl-Id. Wer 2031 eine Hochrechnung bauen will, braucht
beides, und zwar so, wie es am Abend dastand.

Genau dieses Loch hat ``kommunalwahl/referenz-2021/`` schon einmal gestopft
(dort von Hand, am 06.09.2026). Dieses Skript macht daraus einen Befehl:

    python scripts/wahl_einfrieren.py --ziel kommunalwahl/referenz-2026

Was entsteht (``<p>`` = ``--praefix``, Vorgabe ``ratswahl-2026``):

===============================  ===================================
``<p>-stadt.csv``                die drei Open-Data-CSVs, unverändert
``<p>-wahlbereiche.csv``
``<p>-wahlbezirke.csv``
``<p>.json``                     die Referenz-Meta (Schema wie 2021)
``praesentation-ratswahl.json``  Stadt-Ebene der Ergebnisdarstellung
``praesentation-ob.json``        die OB-Wahl — sie hat keine CSV
``termin.json``                  die Wahl-Ids des Termins
``verlauf.json``                 der Minutenverlauf (per ``--verlauf``)
===============================  ===================================

**Die Sitzverteilung wird nachgerechnet, nicht abgeschrieben.** Sie entsteht
aus den gerade geholten CSVs über denselben Weg wie am Wahlabend
(``election.service.compose`` → ``seats.allocate``, NKWG §§ 36/37). Das ist
kein Kunstgriff, sondern der einzige Weg, der die Namen und die Art des
Mandats („direkt" / „Listenplatz n") mitliefert; die Gegenprobe steht in
derselben Datei unter ``sitze_votemanager`` — die Sitze, wie der Votemanager
sie selbst ausweist. Weichen beide ab, sagt das Skript es und schreibt nichts.

**Warum das Skript ``votemanager._header_of`` und ``_official_seats`` benutzt,
statt eigene Prüfungen zu schreiben:** Es sind genau die Proben, die am
Wahlabend über jeden Abruf laufen. Eine zweite Fassung davon wäre eine zweite
Wahrheit — und die stille Sorte, die erst auffällt, wenn eine Referenz schon
falsch im Repo liegt.

**Vorläufig ist nicht amtlich.** ``--stand vorlaeufig`` (Vorgabe) vermerkt in
der Quelle, dass das Ergebnis noch nicht vom Wahlausschuss festgestellt ist.
Nach der Feststellung denselben Befehl mit ``--stand amtlich`` erneut laufen
lassen — er überschreibt, was er findet.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import requests

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL / "web" / "backend"))

from app.election import elections, mayor, presentation, register, service, votemanager  # noqa: E402
from app.election import reference as referenz  # noqa: E402
from app.election.votemanager import Snapshot  # noqa: E402


def _hol(session: requests.Session, url: str) -> bytes:
    resp = session.get(url, timeout=(5, 30))
    resp.raise_for_status()
    return resp.content


def _csvs(session: requests.Session, basis: str, ziel: Path, praefix: str) -> dict[str, str]:
    """Die drei Open-Data-CSVs, unverändert auf die Platte — aber nur, wenn
    sie welche sind: ``_header_of`` weist eine HTML-Wartungsseite ab, die mit
    Status 200 kommt und als leere Tabelle durchginge."""
    texte: dict[str, str] = {}
    for schluessel, pfad in votemanager.files().items():
        roh = _hol(session, basis + pfad)
        text = roh.decode("utf-8-sig")
        votemanager._header_of(text)  # wirft bei HTML, leer oder ohne D<n>-Spalten
        name = {"city": "stadt", "areas": "wahlbereiche", "districts": "wahlbezirke"}[schluessel]
        datei = ziel / f"{praefix}-{name}.csv"
        datei.write_bytes(roh)
        texte[schluessel] = text
        print(f"  {datei.name}  ({len(roh):,} Bytes)".replace(",", "."))
    return texte


def _json_sichern(session: requests.Session, url: str, datei: Path) -> Any | None:
    """Ein JSON der Ergebnisdarstellung sichern — fehlt es, ist das ein
    Hinweis, kein Abbruch: Die CSVs sind der Pflichtteil."""
    try:
        payload = json.loads(_hol(session, url))
    except (requests.RequestException, ValueError) as exc:
        print(f"  ! {datei.name} nicht zu holen ({type(exc).__name__}: {exc})")
        return None
    datei.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"  {datei.name}")
    return payload


def _darstellung(session: requests.Session, basis: str, ziel: Path) -> Any | None:
    """Termin, Ratswahl-Stadtebene und OB-Wahl aus der Ergebnisdarstellung.

    Diese Dateien tragen **keine** Jahreszahl im Namen: Der Ordner heißt schon
    ``referenz-2026``, und ``<name>-<jahr>.json`` ist die Meta-Datei —
    ``reference.meta_path`` fände sonst drei davon.
    """
    _json_sichern(session, basis + mayor.TERMIN_PATH, ziel / "termin.json")
    stadt_id, _ = presentation.resolve_ids(session, basis)
    ratswahl = _json_sichern(session, f"{basis}{elections.active().source.api_path()}/ergebnis_{stadt_id}_0.json",
                             ziel / "praesentation-ratswahl.json")
    ob_id = mayor.resolve_ids(session, basis)
    _json_sichern(session, f"{basis}{mayor.wahl().source.api_path()}/ergebnis_{ob_id}_0.json",
                  ziel / "praesentation-ob.json")
    return ratswahl


def _nachgerechnet(texte: dict[str, str]) -> tuple[list[dict], dict[str, int]]:
    """Sitzverteilung und Sitze je Liste aus den frisch geholten CSVs.

    Derselbe Weg wie am Wahlabend, nur ohne Netz und ohne Zugaben: Die
    Hochrechnung ist bei einem fertig ausgezählten Ergebnis gegenstandslos,
    die Abstände („wie viele Stimmen bis zum Sitz") sind es für eine Referenz
    ebenso.
    """
    reg = register.load()
    schnapp = Snapshot(
        city=votemanager.parse(texte["city"]),
        areas=votemanager.parse(texte["areas"]),
        districts=votemanager.parse(texte["districts"]),
        fetched_at=datetime.now(timezone.utc), last_modified=None, ok=True, error=None,
    )
    nacht = service.compose(reg, referenz.load(), schnapp, "live", margins=False, projection=False)
    if nacht["phase"] != "complete":
        raise SystemExit(f"Abbruch: Die Wahl ist nicht fertig ausgezählt "
                         f"({nacht['progress']['districts_counted']}/{nacht['progress']['districts_total']} "
                         f"Wahlbezirke). Eine halbe Auszählung ist keine Referenz.")
    kurz = {p.slug: p.short for p in reg.parties}
    verteilung = []
    for m in nacht["mandates"]:
        verteilung.append({
            "party": kurz.get(m["slug"], m["slug"]),
            "name": m["name"],
            "district": m["area"],
            "kind": _art(m["kind"], m["position"]),
            "votes": m["votes"],
        })
    sitze = {p["slug"]: p["seats"] or 0 for p in nacht["parties"] if p["seats"]}
    return verteilung, sitze


def _art(kind: str, position: int | None) -> str:
    """Die Mandatsart in der Schreibweise der Referenz von 2021."""
    if kind == "direct":
        return "direkt"
    if kind == "list":
        return f"Listenplatz {position}" if position is not None else "Listenplatz"
    if kind == "transfer":
        return "Übergang"
    return "unbekannt"


def _gegenprobe(nachgerechnet: dict[str, int], payload: Any | None) -> dict[str, int] | None:
    """Die Sitze, wie der Votemanager sie selbst ausweist — und der Vergleich.

    Die Gegenprobe ist der Punkt, an dem das Einfrieren scheitern DARF: Eine
    Referenz mit falscher Sitzverteilung fällt erst in fünf Jahren auf, und
    dann ist die Quelle weg.
    """
    if payload is None:
        print("  ! keine Gegenprobe möglich (Ergebnisdarstellung fehlt)")
        return None
    amtlich = votemanager._official_seats(payload)
    if not amtlich:
        print("  ! die Ergebnisdarstellung weist keine Sitze aus — keine Gegenprobe")
        return None
    abweichung = {s: (nachgerechnet.get(s, 0), n) for s, n in amtlich.items() if nachgerechnet.get(s, 0) != n}
    if abweichung:
        zeilen = ", ".join(f"{s}: gerechnet {a}, Votemanager {b}" for s, (a, b) in sorted(abweichung.items()))
        raise SystemExit(f"Abbruch: Die nachgerechnete Sitzverteilung weicht ab — {zeilen}")
    print(f"  Gegenprobe: {sum(amtlich.values())} Sitze, deckungsgleich mit dem Votemanager")
    return amtlich


def _meta(basis: str, stand: str, verteilung: list[dict], votemanager_sitze: dict[str, int] | None) -> dict:
    reg = register.load()
    return {
        "quelle": {
            "titel": f"{reg.title}, {reg.date} — Open Data des Votemanagers",
            "url": basis + votemanager.PRESENTATION_PATH.rstrip("/") + "/opendata.html",
            "abgerufen": date.today().isoformat(),
            "stand": stand,
            "nachgerechnet": "Sitzverteilung aus den Open-Data-CSVs, NKWG §§ 36/37 "
                             "(scripts/wahl_einfrieren.py)",
        },
        "sitze_gesamt": reg.seats,
        # ``slug`` ist der Slug DIESER Wahl. Wird die Referenz für eine spätere
        # Wahl benutzt, trägt er dort den Slug der Nachfolgerliste — genauso
        # wie ``referenz-2021`` heute die Slugs von 2026 nennt.
        "parteien": [{"index": p.index, "label": p.short, "slug": p.slug} for p in reg.parties],
        "sitze_votemanager": votemanager_sitze,
        "sitzverteilung": verteilung,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--basis", default=votemanager.base_url(), help="Basis-URL des Votemanagers")
    ap.add_argument("--ziel", default="kommunalwahl/referenz-2026", help="Zielordner (relativ zur Repo-Wurzel)")
    ap.add_argument("--praefix", default="ratswahl-2026", help="Dateipräfix, z. B. „ratswahl-2026“")
    ap.add_argument("--stand", choices=("vorlaeufig", "amtlich"), default="vorlaeufig",
                    help="Ist das Ergebnis vom Wahlausschuss festgestellt?")
    ap.add_argument("--verlauf", help="Datei mit dem Minutenverlauf des Abends (data/wahlabend-verlauf.json)")
    args = ap.parse_args()

    # Dieselbe Regel, nach der ``reference.load`` die Meta-Datei findet — nicht
    # nachgebaut, sondern von dort geholt: zwei Fassungen liefen auseinander.
    if not referenz.META_NAME.fullmatch(f"{args.praefix}.json"):
        raise SystemExit(f"Abbruch: „{args.praefix}“ passt nicht auf <name>-<jahr> — "
                         "reference.load findet die Meta-Datei sonst nicht.")
    basis = args.basis.rstrip("/")
    ziel = (WURZEL / args.ziel).resolve()
    ziel.mkdir(parents=True, exist_ok=True)
    print(f"Quelle: {basis}\nZiel:   {ziel}\n")

    with requests.Session() as session:
        session.headers.update({"User-Agent": votemanager.UA})
        print("Open Data (CSV):")
        texte = _csvs(session, basis, ziel, args.praefix)
        print("\nErgebnisdarstellung (JSON):")
        ratswahl_json = _darstellung(session, basis, ziel)

    print("\nNachrechnen:")
    verteilung, sitze = _nachgerechnet(texte)
    print(f"  {len(verteilung)} Mandate aus {len(sitze)} Listen")
    amtlich = _gegenprobe(sitze, ratswahl_json)

    if args.verlauf:
        quelle = Path(args.verlauf)
        if not quelle.is_file():
            raise SystemExit(f"Abbruch: {quelle} gibt es nicht.")
        shutil.copyfile(quelle, ziel / "verlauf.json")
        punkte = len(json.loads(quelle.read_text(encoding="utf-8")))
        print(f"\nVerlauf:\n  verlauf.json ({punkte} Punkte)")

    meta = ziel / f"{args.praefix}.json"
    meta.write_text(json.dumps(_meta(basis, args.stand, verteilung, amtlich), ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
    print(f"\nReferenz:\n  {meta.name}  (Stand: {args.stand})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
