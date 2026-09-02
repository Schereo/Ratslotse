"""Prüft die handgeschriebenen Swift-Modelle gegen den OpenAPI-Vertrag.

**Warum es das gibt.** Von den drei Schichten hat nur die App keine erzeugten
Typen: Das Web leitet seine Formen seit #976 aus dem Vertrag ab, der Übersetzer
meckert dort also von selbst. Die App schreibt ihre ``struct``\\ s und
``CodingKeys`` von Hand — und eine Umbenennung im Backend erreicht sie auf
keinem Weg. So stand ``hits_30d`` weiter in der App, nachdem das Feld
``hits_6m`` hieß, und unter jedem Thema stand auf Prod eine 0.

**Warum das kein Namensvergleich ist.** ``tests/test_vertrag_deckung.py``
prüft, ob ein Feldname *irgendwo* im Vertrag vorkommt. Das ist eine grobe
Sperrklinke: ``id`` kommt überall vor. Hier wird die Bindung ausgerechnet —
aus der Aufrufstelle. Der Client ist generisch::

    async let heute: TodayCard = model.api.get("/api/council/heute")

Pfad und Zieltyp stehen in derselben Zeile. Damit ist bekannt, welches Schema
diese ``struct`` decodieren muss, und der Vergleich geht Feld für Feld.

**Die drei Fehlerklassen, die dabei herauskommen.**

1. *Feld, das der Vertrag nicht kennt* — der Fall ``hits_30d``. Die App liest
   ins Leere und setzt ihre Vorgabe ein. Keine Meldung, nur eine falsche Zahl.
2. *Nicht optional, obwohl der Vertrag es weglassen darf* — schlimmer, denn
   ``JSONDecoder`` wirft: Die Seite bleibt leer statt falsch.
3. *Typ passt nicht* — ``Int`` gegen einen String-Schlüssel. Ebenfalls ein
   Abbruch beim Decodieren; genau so war ``ResearchJobHead.id`` deklariert.

Aufruf: ``python scripts/ios_vertrag.py`` (nur Bericht) oder über
``tests/test_ios_vertrag.py``.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
IOS = WURZEL / "ios"
VERTRAG = WURZEL / "api" / "openapi.json"

#: Typen, die absichtlich nichts über ihren Inhalt behaupten. ``JSONValue`` ist
#: der offene Baum aus ``JSONValue.swift``; er decodiert jede Antwort und kann
#: deshalb per Bauart nicht driften.
UNDURCHSICHTIG = {"JSONValue", "Data", "String", "Bool", "Int", "Double"}

AUFRUF = re.compile(
    r":\s*([A-Za-z_][\w.]*(?:\[[^\]]+\])?\??)\s*=\s*(?:try\s+)?(?:await\s+)?"
    r"(?:\w+\.)*(?:api|client)\.(get|send|sendWithoutBody|sendVoid)\s*\("
    r"\s*\"([^\"]+)\"([^\n]*)",
    re.M,
)


# ---------------------------------------------------------------- Swift lesen

def _koerper(text: str, ab: int) -> str:
    """Der Rumpf einer ``struct`` ab der öffnenden Klammer, per Klammerzählung.

    Eine Zeilen-Heuristik reicht hier nicht: ``struct Response: Codable { let
    ok: Bool }`` steht komplett in einer Zeile, und die Datei geht danach mit
    ``let _: Response = try await …`` weiter — als Feld gelesen ergäbe das ein
    Wire-Feld namens ``_``.
    """
    start = text.find("{", ab)
    if start < 0:
        return ""
    tiefe = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            tiefe += 1
        elif text[i] == "}":
            tiefe -= 1
            if tiefe == 0:
                return text[start + 1 : i]
    return text[start + 1 :]


def swift_typen(dateien) -> tuple[dict[str, dict[str, tuple[str, bool]]], set[str]]:
    """``{Typname: {Wire-Name: (Swift-Typ, optional)}}`` aus allen Modellen.

    Ein Name, der mit **verschiedenen** Rümpfen mehrfach vorkommt, fällt raus:
    Dazu die Namen der Typen mit **eigenem** ``init(from decoder:)``: Die
    decodieren jedes Feld als ``decodeIfPresent`` mit Vorgabewert und können
    deshalb nicht abbrechen — für sie gilt die Optionalitäts-Prüfung nicht.

    Ein Name, der mit **verschiedenen** Rümpfen mehrfach vorkommt, fällt raus:
    ``Response`` ist im App-Code ein Wegwerf-Typ, den ein Dutzend Funktionen
    jeweils lokal für ihre eigene Antwort definiert. Welcher davon an einer
    Aufrufstelle gilt, entscheidet der Gültigkeitsbereich — das ist mehr, als
    ein Textleser wissen kann, und eine falsche Bindung wäre schlimmer als
    keine.
    """
    gesammelt: dict[str, list[dict[str, tuple[str, bool]]]] = {}
    eigener_decoder: set[str] = set()
    for datei in dateien:
        text = datei.read_text()
        for m in re.finditer(r"\bstruct (\w+)\b", text):
            koerper = _koerper(text, m.end())
            # ALLE verschachtelten Rümpfe weg, nicht nur die innerste Ebene:
            # Ein `struct Area { … }` innerhalb des Typs trägt eigene Felder,
            # und die gehören nicht dem äußeren Typ. Eine einzelne Runde lässt
            # bei zwei Ebenen genau diese Felder stehen.
            innen = koerper
            while True:
                gekuerzt = re.sub(r"\{[^{}]*\}", " ", innen)
                if gekuerzt == innen:
                    break
                innen = gekuerzt
            felder: dict[str, tuple[str, bool]] = {}
            # Der Abschluss steht als VORAUSBLICK da: Verbraucht der Ausdruck
            # den Zeilenumbruch, kann die nächste Zeile ihren eigenen
            # Zeilenanfang nicht mehr sehen — dann fällt jedes zweite Feld
            # lautlos aus dem Ergebnis.
            for f in re.finditer(
                r"^[ \t]*(?:public |private |internal )?(?:let|var) (\w+)"
                r"\s*:\s*([^\n=({]+?)[ \t]*(?==|$)",
                innen,
                re.M,
            ):
                typ = f.group(2).strip()
                if typ:
                    felder[f.group(1)] = (typ.rstrip("?"), typ.endswith("?"))
            # Berechnete Eigenschaften (`var id: String { key }`) reisen nicht
            # über die Leitung. Sie stehen hier vor allem für `Identifiable`,
            # und ohne diesen Schritt verlangt der Vergleich vom Vertrag ein
            # Feld `id`, das es nie gab.
            for f in re.finditer(
                r"^[ \t]*(?:public |private |internal )?var (\w+)\s*:\s*[^\n{]*\{",
                koerper,
                re.M,
            ):
                felder.pop(f.group(1), None)
            wire: dict[str, tuple[str, bool]] = {}
            schluessel = re.search(r"enum CodingKeys[^{]*", koerper)
            if schluessel:
                for zeile in _koerper(koerper, schluessel.end() - 1).splitlines():
                    zeile = zeile.strip()
                    if not zeile.startswith("case "):
                        continue
                    for stueck in zeile[5:].split(","):
                        stueck = stueck.strip()
                        if "=" in stueck:
                            sn, wn = (t.strip().strip('"') for t in stueck.split("=", 1))
                        else:
                            sn = wn = stueck
                        if sn in felder:
                            wire[wn] = felder[sn]
            else:
                wire = dict(felder)
            if "init(from decoder" in koerper:
                eigener_decoder.add(m.group(1))
            if wire:
                gesammelt.setdefault(m.group(1), []).append(wire)
    return {
        name: formen[0]
        for name, formen in gesammelt.items()
        if all(f == formen[0] for f in formen)
    }, eigener_decoder


def aufrufstellen(dateien) -> list[tuple[Path, str, str, str]]:
    """``[(Datei, Swift-Typ, HTTP-Methode, Pfadmuster)]`` aus dem App-Code."""
    aus = []
    for datei in dateien:
        for m in AUFRUF.finditer(datei.read_text()):
            typ, funktion, pfad, rest = m.groups()
            methode = "get" if funktion == "get" else "post"
            gesetzt = re.search(r"method:\s*\.(\w+)", rest)
            if gesetzt:
                methode = gesetzt.group(1).lower()
            muster = re.sub(r"\\\([^)]*\)", "{}", pfad).split("?")[0]
            aus.append((datei, typ.rstrip("?"), methode, muster))
    return aus


# --------------------------------------------------------------- Vertrag lesen

class Vertrag:
    def __init__(self, spec: dict) -> None:
        self.schemata = spec["components"]["schemas"]
        self.pfade: dict[str, dict] = {}
        for pfad, ops in spec["paths"].items():
            self.pfade.setdefault(re.sub(r"\{[^}]+\}", "{}", pfad), {}).update(ops)

    def _auf(self, s: dict) -> dict:
        return self.schemata[s["$ref"].rsplit("/", 1)[-1]] if "$ref" in s else s

    def antwortschema(self, muster: str, methode: str) -> dict | None:
        op = (self.pfade.get(muster) or {}).get(methode)
        if not op:
            return None
        for kode, antwort in (op.get("responses") or {}).items():
            if not kode.startswith("2"):
                continue
            inhalt = (antwort.get("content") or {}).get("application/json")
            if inhalt and inhalt.get("schema"):
                return inhalt["schema"]
        return None

    def entfalten(self, s: dict) -> tuple[dict, set[str], bool]:
        """``(Eigenschaften, Pflichtfelder, offen?)`` — über ``$ref``/``allOf``."""
        s = self._auf(s)
        props = dict(s.get("properties") or {})
        pflicht = set(s.get("required") or [])
        offen = s.get("additionalProperties") not in (False, None)
        for teil in s.get("allOf") or []:
            p, r, o = self.entfalten(teil)
            props |= p
            pflicht |= r
            offen = offen or o
        return props, pflicht, offen

    def grundtypen(self, s: dict) -> set[str]:
        """Alle JSON-Grundtypen, die dieses Feld annehmen darf."""
        s = self._auf(s)
        aus: set[str] = set()
        if "type" in s:
            t = s["type"]
            aus |= set(t) if isinstance(t, list) else {t}
        for schluessel in ("anyOf", "oneOf", "allOf"):
            for teil in s.get(schluessel) or []:
                aus |= self.grundtypen(teil)
        if "enum" in s:
            aus |= {
                "string" if isinstance(v, str) else "number"
                for v in s["enum"]
                if v is not None
            }
        return aus

    def elementschema(self, s: dict) -> tuple[dict, bool]:
        """Listen auspacken: ``(Schema, war es eine Liste?)``."""
        entfaltet = self._auf(s)
        if entfaltet.get("type") == "array" and entfaltet.get("items"):
            return entfaltet["items"], True
        return s, False

    def objektschema(self, s: dict) -> dict | None:
        """Das eine Objekt-Schema hinter Liste, ``anyOf`` und ``null`` — oder nichts.

        ``NotRequired[list[Foo] | None]`` steht im Vertrag als ``anyOf`` aus
        einer Liste und ``null``. Ohne dieses Auspacken endet der Vergleich an
        der ersten optionalen Verschachtelung, und das ist die Mehrzahl.
        """
        s, _ = self.elementschema(s)
        entfaltet = self._auf(s)
        kandidaten = [
            teil
            for schluessel in ("anyOf", "oneOf")
            for teil in entfaltet.get(schluessel) or []
            if self._auf(teil).get("type") != "null"
        ]
        if len(kandidaten) == 1:
            return self.objektschema(kandidaten[0])
        if kandidaten:
            return None
        return s if (self.entfalten(s)[0]) else None


#: Welche JSON-Grundtypen ein Swift-Typ decodieren kann.
SWIFT_JSON = {
    "String": {"string"},
    "Int": {"integer", "number"},
    "Int64": {"integer", "number"},
    "Double": {"number", "integer"},
    "Bool": {"boolean"},
    "Date": {"string", "number"},
    "URL": {"string"},
}


def swift_grundtypen(typ: str) -> set[str]:
    typ = typ.strip().rstrip("?")
    if typ.startswith("[") and typ.endswith("]"):
        return {"object"} if ":" in typ else {"array"}
    return SWIFT_JSON.get(typ, set())


def befunde(wurzel: Path = WURZEL) -> list[tuple[str, str, str, str]]:
    """``[(Swift-Typ, Schema, Feld, Beanstandung)]`` — leer heißt sauber."""
    dateien = sorted((wurzel / "ios").rglob("*.swift"))
    typen, eigener_decoder = swift_typen(dateien)
    vertrag = Vertrag(json.loads((wurzel / "api" / "openapi.json").read_text()))
    aus: list[tuple[str, str, str, str]] = []
    gesehen: set[tuple[str, int]] = set()

    # Arbeitsliste statt Rekursion: Der Vergleich steigt über verschachtelte
    # Typen ab, und Schemata verweisen im Kreis (eine Sitzung trägt Punkte,
    # ein Punkt seine Sitzung).
    offen: list[tuple[str, dict, str]] = []
    for _datei, swifttyp, methode, muster in aufrufstellen(dateien):
        innen = swifttyp.strip("[]")
        if innen in UNDURCHSICHTIG or innen not in typen:
            continue
        schema = vertrag.antwortschema(muster, methode)
        if schema is None:
            continue
        offen.append((innen, schema, muster))

    while offen:
        innen, schema, herkunft = offen.pop()
        objekt = vertrag.objektschema(schema)
        if objekt is None:
            continue
        marke = (innen, id(objekt))
        if marke in gesehen:
            continue
        gesehen.add(marke)

        name = objekt.get("$ref", "").rsplit("/", 1)[-1] or herkunft
        props, pflicht, offen_fuer_mehr = vertrag.entfalten(objekt)
        if not props:
            continue
        for wire, (typ, optional) in sorted(typen[innen].items()):
            if wire not in props:
                if not offen_fuer_mehr:
                    aus.append((innen, name, wire, "kennt der Vertrag nicht"))
                continue
            feld = props[wire]
            grund = vertrag.grundtypen(feld)
            if (
                not optional
                and innen not in eigener_decoder
                and ("null" in grund or wire not in pflicht)
            ):
                aus.append(
                    (innen, name, wire, "nicht optional, der Vertrag darf es weglassen")
                )
            erlaubt = grund - {"null"}
            kann = swift_grundtypen(typ)
            if erlaubt and kann and not (erlaubt & kann):
                aus.append((innen, name, wire, f"{typ} gegen {'/'.join(sorted(erlaubt))}"))
            kind = typ.strip("[]?")
            if kind in typen and kind not in UNDURCHSICHTIG:
                offen.append((kind, feld, f"{name}.{wire}"))
    return sorted(set(aus))


def ausgelieferter_stand(ref: str, ziel: Path) -> Path:
    """Den App-Code aus ``ref`` auspacken und den JETZIGEN Vertrag danebenlegen.

    Das ist die Release-Frage: Der Store trägt die App, die zu ``main`` gebaut
    wurde; nach dem Release antwortet der Server nach dem neuen Vertrag. Was
    die installierte App dann liest, sagt genau dieser Vergleich.
    """
    import subprocess

    # Auspacken über `tar` und nicht über `tarfile`: Dessen `filter=`-Angabe,
    # ohne die das Auspacken eine Warnung wirft, gibt es erst ab Python 3.12 —
    # und dieses Skript soll auch mit dem System-Python laufen.
    ziel.mkdir(parents=True, exist_ok=True)
    archiv = ziel / "stand.tar"
    with archiv.open("wb") as f:
        subprocess.run(["git", "archive", ref, "ios"], cwd=WURZEL, stdout=f, check=True)
    subprocess.run(["tar", "-xf", str(archiv), "-C", str(ziel)], check=True)
    archiv.unlink()
    (ziel / "api").mkdir(exist_ok=True)
    (ziel / "api" / "openapi.json").write_bytes(VERTRAG.read_bytes())
    return ziel


def _bericht(gefunden, typen, decoder) -> None:
    """Nach Swift-Typ gruppiert — ein Typ ist eine Ansicht in der App."""
    from collections import defaultdict

    hart: dict[str, set[str]] = defaultdict(set)
    weich: dict[str, set[str]] = defaultdict(set)
    for typ, _schema, feld, art in gefunden:
        if art != "kennt der Vertrag nicht":
            continue
        optional = typen[typ][feld][1] or typ in decoder
        (weich if optional else hart)[typ].add(feld)

    def zeigen(gruppen: dict[str, set[str]], titel: str) -> None:
        anzahl = sum(len(f) for f in gruppen.values())
        print(f"{titel} — {anzahl} Feld(er) in {len(gruppen)} Typ(en):")
        for typ in sorted(gruppen):
            felder = sorted(gruppen[typ])
            # Ein Typ, der ein ganzes Schema verfehlt, ist EINE Aussage und
            # keine zwanzig; ausgeschrieben verdeckt er den Rest.
            gezeigt = ", ".join(felder[:6])
            rest = f" … (+{len(felder) - 6})" if len(felder) > 6 else ""
            print(f"    {typ:26s} {gezeigt}{rest}")
        print()

    zeigen(hart, "ABBRUCH beim Decodieren, die Seite bleibt leer")
    zeigen(weich, "still leer, die Seite steht ohne das Feld")


if __name__ == "__main__":
    import argparse
    import tempfile

    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--ausgeliefert", metavar="REF", nargs="?", const="origin/main",
                   help="Statt des Arbeitsstands den App-Code aus REF gegen den "
                        "JETZIGEN Vertrag halten (Vorgabe: origin/main). "
                        "Beantwortet: Was bricht in der installierten App, "
                        "wenn dieser Stand nach main geht?")
    args = p.parse_args()

    if args.ausgeliefert:
        with tempfile.TemporaryDirectory() as tmp:
            wurzel = ausgelieferter_stand(args.ausgeliefert, Path(tmp))
            typen, decoder = swift_typen(sorted((wurzel / "ios").rglob("*.swift")))
            gefunden = befunde(wurzel)
            print(f"App-Stand {args.ausgeliefert} gegen den jetzigen Vertrag\n")
            _bericht(gefunden, typen, decoder)
        raise SystemExit(0)

    gefunden = befunde()
    for swifttyp, schema, feld, was in gefunden:
        print(f"{swifttyp:26s} {schema:26s} {feld:26s} {was}")
    print(f"\n{len(gefunden)} Befunde")
