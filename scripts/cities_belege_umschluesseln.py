#!/usr/bin/env python3
"""Beschluss-Belege von der Zeilennummer auf Sitzung und Punkt umschlüsseln.

**Der Befund (03.10.2026).** Ein Urteil über Oldenburg (``fit``, ``idea_fit``)
nennt seine Belege mit Kennung. Für Oldenburger Beschlüsse hieß die bis
10/2026 ``oldenburg:decision:<id>`` — und ``id`` ist die Zeile in
``council_decisions`` der Datenbank, in der das Urteil entstand: ein
dev-Abzug (Zeilen 322 bis 9.441). Prod zählt ab 10.983. Auf Prod war damit
KEIN einziger der 1.294 Beschluss-Belege auflösbar; 48 von 207 Ideen standen
ohne Beleg da, 8 davon ganz ohne, und „Oldenburg hat das" erschien ohne die
Zeile, die es zeigt (Lachgas, Bezahlkarte, Geschäftsordnung, Mietspiegel).

Die neue Kennung (``evidence.beschluss_kennung``) ist
``oldenburg:decision:<ksinr>:<TOP>`` — beides aus dem RIS und deshalb überall
gleich. Dieses Skript schreibt den Bestand um.

**Das Abbild kommt mit dem Code**, nicht vom Server: Welche Zeile auf dev
welcher Beschluss war, weiß nur ein dev-Abzug, und den gibt es auf Prod
nicht. ``--abbild-bauen`` liest einen oder mehrere dev-Abzüge und legt
``council/cities/beschluss_abbild.json`` an; auf Prod wird es nur
angewendet. Gebaut am 03.10.2026 aus fünf dev-Abzügen (17.09. bis 01.10.):
alle 863 Kennungen gefunden, keine widersprüchlich.

**Der Quell-Hash ist ein eigener Schritt** (``--hashes``). ``fit`` und
``idea_fit`` nehmen die Beleg-Kennungen in den Hash; umgeschlüsselt sähe für
einen Bestandslauf jedes Urteil mit Beschluss-Beleg „geändert" aus — rund
12.000 Urteile, 14 $. ``--hashes`` rechnet die Hashes so, wie der nächste
Lauf sie rechnen würde, und übernimmt sie in die bestehenden Urteile, ohne
eins neu zu fällen. Das kostet nur die Suchwörter (rund 0,03 $ je 1.000
Vorlagen) und gut eine Stunde. Der Wochenlauf braucht den Schritt NICHT —
er urteilt seit 10/2026 nur über Neues (``fit.run(schlank=True)``) —, ein
Bestandslauf von Hand schon.

**Reihenfolge auf Prod: ``--hashes-ideen`` erst NACH dem ersten
``check_cities.py --nur-oldenburg``.** Der Oldenburg-Lauf holt die neuen
Oldenburger Vorlagen samt Vektoren in den Speicher (nach der Pause am
01.10.2026: 519 Stück) — und genau die landen in den Beleg-Pools der Ideen.
Übernimmt man die Hashes vorher, stehen sie auf dem alten Pool, und der
erste Sonntag beurteilt trotzdem alle Ideen neu (~0,9 $, Stunden). Das Skript
prüft das selbst (``oldenburg_rueckstand``) und verweigert die Übernahme,
solange die Rats-Datenbank Vorlagen hat, die der Speicher nicht kennt;
``--trotzdem`` übergeht die Prüfung.

    python scripts/cities_belege_umschluesseln.py                 # zählen, nichts schreiben
    python scripts/cities_belege_umschluesseln.py --schreiben     # umschlüsseln
    python scripts/cities_belege_umschluesseln.py --hashes        # Quell-Hashes übernehmen
    python scripts/cities_belege_umschluesseln.py --hashes-ideen  # nur die der Ideen (Minuten)
    python scripts/cities_belege_umschluesseln.py --links         # Links ins RIS nachtragen
    python scripts/cities_belege_umschluesseln.py --gruppen       # Gruppen + idea_groups neu (ohne Modell)
    python scripts/cities_belege_umschluesseln.py --neu-einordnen <paper_id> …
    python scripts/cities_belege_umschluesseln.py --abbild-bauen data/dev1.sqlite …

Idempotent: Ein zweiter Lauf findet nichts mehr umzuschlüsseln.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from council.cities import default_paths  # noqa: E402
from council.cities.store import CitiesStore  # noqa: E402

ABBILD = ROOT / "council" / "cities" / "beschluss_abbild.json"


def _rats(pfad: str | None = None):
    from council.store import CouncilStore
    return CouncilStore(pfad or os.environ.get("COUNCIL_DB")
                        or str(ROOT / "data" / "council.sqlite"))


def alte_kennungen(s: CitiesStore) -> set[str]:
    """Alle Beschluss-Belege in alter Form (``oldenburg:decision:<Zahl>``)."""
    aus: set[str] = set()
    for annotator, version in (("fit", None), ("idea_fit", None)):
        for zeile in s.annotation_payloads(annotator, version):
            for k in (zeile.get("evidence") or []) + (zeile.get("related") or []):
                rest = str(k)[len("oldenburg:decision:"):]
                if str(k).startswith("oldenburg:decision:") and rest.isdigit():
                    aus.add(str(k))
    return aus


def abbild_bauen(s: CitiesStore, quellen: list[str]) -> dict:
    """Alte Kennung → neue, aus einem oder mehreren dev-Abzügen."""
    from council.cities.evidence import beschluss_kennung

    offen = alte_kennungen(s)
    abbild: dict[str, str] = {}
    widerspruch: list[str] = []
    for pfad in quellen:
        rats = _rats(pfad)
        try:
            for alt in sorted(offen):
                b = rats.get_decision(int(alt.rsplit(":", 1)[1]))
                if not b or b.get("kind", "decision") != "decision":
                    continue
                neu = beschluss_kennung(b, rats.get_decisions(int(b["ksinr"])))
                if alt in abbild and abbild[alt] != neu:
                    widerspruch.append(alt)
                    continue
                abbild.setdefault(alt, neu)
        finally:
            rats.close()
    for alt in widerspruch:
        abbild.pop(alt, None)
    print(f"{len(offen)} alte Kennungen, {len(abbild)} abgebildet, "
          f"{len(offen) - len(abbild) - len(widerspruch)} unbekannt, "
          f"{len(widerspruch)} widersprüchlich (weggelassen)")
    return {"stand": date.today().isoformat(),
            "quellen": [Path(q).name for q in quellen],
            "abbild": dict(sorted(abbild.items(), key=lambda kv: int(kv[0].rsplit(':', 1)[1])))}


def zaehlen(s: CitiesStore, rats) -> dict:
    """Wie viele Beschluss-Belege in DIESER Rats-Datenbank auflösen.

    Dieselbe Reihenfolge wie die Karte (``_belege_aufloesen``): erst der
    Beschluss, dann die Vorlage des Punkts.
    """
    from council.cities.annotators import get as get_annotator
    from council.cities.evidence import (BESCHLUSS_PRAEFIX, beschluss_zu, kvonr_aus,
                                         vorlage_hinter)

    def loest_auf(k: str) -> bool:
        if k.startswith(BESCHLUSS_PRAEFIX):
            if beschluss_zu(rats, k):
                return True
            kvonr, titel = vorlage_hinter(rats, k)
            return kvonr is not None or bool(titel)
        kvonr = kvonr_aus(k)
        return kvonr is not None and rats.get_vorlage(kvonr) is not None

    aus: dict[str, int] = {}
    for annotator, version, praefix in (("idea_fit", get_annotator("idea_fit").version, "idee"),
                                        ("fit", get_annotator("fit").version, "urteil")):
        zeilen = s.annotation_payloads(annotator, version)
        beschluss = [str(k) for z in zeilen for k in (z.get("evidence") or [])
                     if str(k).startswith(BESCHLUSS_PRAEFIX)]
        aus[f"{praefix}_beschluss_belege"] = len(beschluss)
        aus[f"{praefix}_beschluss_belege_aufloesbar"] = sum(1 for k in beschluss if loest_auf(k))
        mit_behauptung = [z for z in zeilen if z.get("status") in ("present", "partial")]
        ohne_jeden = 0
        mit_luecke = 0
        for z in mit_behauptung:
            belege = [str(k) for k in (z.get("evidence") or [])[:3]
                      if str(k).startswith("oldenburg:")]
            gut = sum(1 for k in belege if loest_auf(k))
            if belege and gut < len(belege):
                mit_luecke += 1
            if not gut:
                ohne_jeden += 1
        aus[f"{praefix}_vorhanden_oder_teilweise"] = len(mit_behauptung)
        aus[f"{praefix}_mit_unaufloesbarem_beleg"] = mit_luecke
        aus[f"{praefix}_ganz_ohne_beleg"] = ohne_jeden
    return aus


def oldenburg_rueckstand(s: CitiesStore, rats) -> int:
    """Wie viele Oldenburger Vorlagen der Städte-Speicher noch nicht kennt.

    Gemessen am Datum: Eine Vorlage datiert der Oldenburg-Adapter auf ihre
    früheste Beratung. Alles in der Rats-Datenbank, was jünger ist als die
    jüngste Oldenburger Vorlage im Speicher, ist seit dem letzten
    ``check_cities.py``-Lauf dazugekommen. Steht im Speicher noch gar keine,
    zählt alles.
    """
    juengste = s.papers("oldenburg", limit=1)
    seit = (juengste[0].get("date") if juengste else None) or ""
    zeile = rats._conn.execute(
        "SELECT COUNT(*) FROM (SELECT kvonr, MIN(date) AS d FROM council_deliberations "
        "GROUP BY kvonr) WHERE d > ?", (seit,)).fetchone()
    return int(zeile[0] or 0)


def hashes_uebernehmen(s: CitiesStore, nur_ideen: bool = False) -> dict:
    """Quell-Hashes von ``fit`` und ``idea_fit`` neu rechnen und übernehmen.

    ``nur_ideen``: nur ``idea_fit`` — Minuten statt einer Stunde. Das ist der
    Teil, den der Sonntagslauf sonst selbst nachholte: Er beurteilte alle
    rund 200 Ideen neu, weil ihre Belege umgeschlüsselt sind (lokal am
    03.10.2026 gemessen: 20 Ideen in 47 Minuten, 0,005 $ je Idee — der
    Rest wäre über mehrere Sonntage gelaufen).
    """
    from council.cities import fit as fit_modul
    from council.cities import idea_fit as idea_fit_modul
    from council.cities.annotators import get as get_annotator
    from council.cities.index import EMBED_MODEL

    rats = _rats()
    try:
        stand_fit = ({} if nur_ideen else fit_modul.run(
            s, rats, get_annotator("fit"), EMBED_MODEL, nur_hashes=True))
        stand_idee = idea_fit_modul.run(s, rats, EMBED_MODEL, nur_hashes=True)
    finally:
        rats.close()
    return {"fit_hashes": stand_fit.get("hashes_adopted", 0),
            "idea_fit_hashes": stand_idee.get("hashes_adopted", 0),
            "idea_fit_unchanged": stand_idee.get("unchanged", 0)}


def links_nachtragen(s: CitiesStore) -> int:
    """Vorlagen ohne Link ins RIS bekommen ihn, wo das Muster gemessen ist."""
    from council.cities.adapters.session import web_url_for
    paare = [(url, p["id"]) for p in s.papers_without_web()
             if (url := web_url_for(p["id"]))]
    return s.set_paper_web(paare)


def gruppen_neu(s: CitiesStore) -> dict:
    """Gruppen (feste Nummern, gleiche Überschriften vereint), Status, Ideen.

    Ohne Modell: Was eine Gruppe neu ist oder neue Mitglieder hat, prüft und
    beurteilt der nächste Sonntagslauf. Danach tragen die Zeitleisten auch
    wieder ihre Kurztitel (#1498) — auf Prod standen alle 863 Punkte leer,
    weil `idea_groups` dort vor #1498 gebaut war.
    """
    from council.cities import clusters
    from council.cities.annotators import get as get_annotator
    from council.cities.index import EMBED_MODEL

    zahlen = clusters.build_clusters(s, EMBED_MODEL)
    zahlen["group_status"] = s.rebuild_group_status(
        EMBED_MODEL, clusters.CLUSTER_VERSION, get_annotator("fit").version)
    zahlen["idea_groups"] = clusters.rebuild_idea_groups(s, EMBED_MODEL)
    return zahlen


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--schreiben", action="store_true", help="umschlüsseln (sonst nur zählen)")
    p.add_argument("--hashes", action="store_true",
                   help="Quell-Hashes von fit und idea_fit neu rechnen und übernehmen")
    p.add_argument("--hashes-ideen", action="store_true",
                   help="nur die Quell-Hashes von idea_fit (Minuten statt einer Stunde)")
    p.add_argument("--trotzdem", action="store_true",
                   help="Hashes übernehmen, obwohl Oldenburg im Speicher hinterherhinkt")
    p.add_argument("--links", action="store_true",
                   help="fehlende Links ins RIS nachtragen (Magdeburg, Münster)")
    p.add_argument("--gruppen", action="store_true",
                   help="Gruppen neu nummerieren/vereinen und idea_groups neu schreiben")
    p.add_argument("--neu-einordnen", nargs="+", metavar="PAPER_ID",
                   help="diese Vorlagen beim nächsten Lauf neu einordnen lassen")
    p.add_argument("--abbild-bauen", nargs="+", metavar="DEV_DB",
                   help="das Abbild aus dev-Abzügen der Rats-Datenbank bauen")
    p.add_argument("--db", help="Pfad zur cities.sqlite (Vorgabe: aus der Umgebung)")
    args = p.parse_args()

    with CitiesStore(args.db or default_paths()[0]) as s:
        if args.abbild_bauen:
            daten = abbild_bauen(s, args.abbild_bauen)
            ABBILD.write_text(json.dumps(daten, ensure_ascii=False, indent=1) + "\n")
            print(f"→ {ABBILD.relative_to(ROOT)}")
            return 0
        if args.gruppen:
            print(json.dumps(gruppen_neu(s), indent=1))
            return 0
        if args.neu_einordnen:
            # Den Quell-Hash der Einordnung ungültig machen: Der nächste Lauf
            # hält sie für „Eingabe geändert" und ordnet neu ein — auch mit
            # `nur_neu`. Gelöscht wird nichts.
            n = s.set_source_hashes("paper", "classify", "2",
                                    {pid: "neu-einordnen" for pid in args.neu_einordnen})
            print(f"{n} Vorlagen werden beim nächsten Lauf neu eingeordnet.")
            return 0
        if args.links:
            print(f"{links_nachtragen(s)} Links nachgetragen.")
            return 0
        if args.hashes or args.hashes_ideen:
            rats = _rats()
            try:
                fehlt = oldenburg_rueckstand(s, rats)
            finally:
                rats.close()
            if fehlt and not args.trotzdem:
                print(f"ABBRUCH: {fehlt} Oldenburger Vorlagen fehlen im Städte-Speicher. "
                      "Erst `scripts/check_cities.py --nur-oldenburg` laufen lassen, dann "
                      "die Hashes übernehmen — sonst stehen sie auf dem alten Beleg-Pool, "
                      "und der erste Sonntag beurteilt alle Ideen neu. "
                      "(`--trotzdem` übergeht die Prüfung.)", file=sys.stderr)
                return 2
            print(json.dumps(hashes_uebernehmen(s, nur_ideen=not args.hashes), indent=1))
            return 0
        rats = _rats()
        try:
            print("vorher:", json.dumps(zaehlen(s, rats), indent=1))
            abbild = json.loads(ABBILD.read_text())["abbild"]
            if not args.schreiben:
                offen = alte_kennungen(s)
                print(f"{len(offen)} alte Kennungen im Bestand, "
                      f"{len(offen & set(abbild))} davon im Abbild. "
                      "--schreiben schlüsselt um.")
                return 0
            print("umgeschlüsselt:", json.dumps(s.rekey_evidence(abbild)))
            print("nachher:", json.dumps(zaehlen(s, rats), indent=1))
        finally:
            rats.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
