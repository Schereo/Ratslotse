"""Was der Ereignis-Strom sendet — und was die beiden Clients daraus lesen.

**Die Lücke.** ``/council/ask`` und die tiefe Recherche sind die einzigen
Nutzlasten, die der Vertrag ausdrücklich NICHT beschreibt: Sie gehen als
Server-Sent Events über die Leitung, und der Vertrag sagt zu ihnen nur, dass
``text/event-stream`` herauskommt (``KEIN_JSON`` in
``tests/test_api_vertrag.py``). Geparst werden sie zweimal von Hand — im Web
in ``council-qa.tsx``, in der App in ``QuestionsView.swift``.

Damit ist ausgerechnet das größte Feature die einzige Schicht ohne jede
Abgleich-Prüfung. Was dabei herauskommt, ließ sich am 02.09.2026 messen: #913
hatte den Tagesordnungs-Block im ``sources``-Rahmen von ``sitzungen`` in
``sessions`` umbenannt; die App zog nach, das Web nicht. Der Baustein
erschien danach weder im Strom noch in einem geladenen Gespräch noch als
frisches Beispiel auf der leeren Seite — an drei Stellen dasselbe Wort.

**Was hier verglichen wird.** Drei Seiten:

* der **Server**: die Rahmen aus ``_sse({…})`` (Frage) und ``_emit(…)``
  (Recherche), samt ihrer Schlüssel,
* das **Web**: jedes ``msg.<feld>`` in den beiden Strom-Blöcken,
* die **App**: jedes ``event.fields["<feld>"]`` und die ``CodingKeys`` des
  ``SSEEvent``.

Ein Client darf einen Rahmen ignorieren — nicht jede Ansicht zeigt alles.
Aber er darf kein Feld lesen, das niemand sendet: Das ist immer entweder eine
Umbenennung ohne Nachzug oder ein Rest.

Aufruf: ``python scripts/sse_vertrag.py`` — oder über ``tests/test_sse_vertrag.py``.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
FRAGE = WURZEL / "web" / "backend" / "app" / "routers" / "council.py"
RECHERCHE = WURZEL / "web" / "backend" / "app" / "deepresearch.py"
WEB = WURZEL / "web" / "frontend" / "components" / "council-qa.tsx"
APP = (WURZEL / "ios" / "Packages" / "RatslotseFeatures" / "Sources"
       / "RatslotseFeatures" / "QuestionsView.swift")
SSE_CLIENT = (WURZEL / "ios" / "Packages" / "RatslotseAPI" / "Sources"
              / "RatslotseAPI" / "SSEClient.swift")


def _dict_schluessel(knoten: ast.Dict) -> dict[str, ast.expr]:
    return {
        s.value: v
        for s, v in zip(knoten.keys, knoten.values)
        if isinstance(s, ast.Constant) and isinstance(s.value, str)
    }


def rahmen_der_frage() -> dict[str, set[str]]:
    """``{Rahmen-Typ: {Feld, …}}`` aus den ``_sse({…})``-Aufrufen."""
    aus: dict[str, set[str]] = {}
    for knoten in ast.walk(ast.parse(FRAGE.read_text())):
        if not (isinstance(knoten, ast.Call) and isinstance(knoten.func, ast.Name)
                and knoten.func.id == "_sse" and knoten.args
                and isinstance(knoten.args[0], ast.Dict)):
            continue
        felder = _dict_schluessel(knoten.args[0])
        typ = felder.get("type")
        if isinstance(typ, ast.Constant) and isinstance(typ.value, str):
            aus.setdefault(typ.value, set()).update(set(felder) - {"type"})
    return aus


def rahmen_der_recherche() -> dict[str, set[str]]:
    """``{Rahmen-Typ: {Feld, …}}`` aus den ``_emit(job, {…})``-Aufrufen.

    Andere Bauform als bei der Frage: Der Rahmen ist das ZWEITE Argument, das
    erste ist der Auftrag. Wer hier nur das erste liest, bekommt eine leere
    Liste — und der Test meldete dann jedes Recherche-Feld beider Clients als
    „sendet niemand". Genau das ist beim Bauen passiert.
    """
    aus: dict[str, set[str]] = {}
    for knoten in ast.walk(ast.parse(RECHERCHE.read_text())):
        if not (isinstance(knoten, ast.Call) and isinstance(knoten.func, ast.Name)
                and knoten.func.id == "_emit" and len(knoten.args) >= 2
                and isinstance(knoten.args[1], ast.Dict)):
            continue
        felder = _dict_schluessel(knoten.args[1])
        typ = felder.get("type")
        if isinstance(typ, ast.Constant) and isinstance(typ.value, str):
            aus.setdefault(typ.value, set()).update(set(felder) - {"type"})
    return aus


def gespeicherter_blob() -> set[str]:
    """Die Schlüssel, unter denen ein Gesprächs-Turn abgelegt wird.

    Ein EIGENES Format, kein Rahmen des Stroms: Es trägt zusätzlich, was ein
    geladenes Gespräch braucht (``context``, ``research``, ``cited``). Aber
    dasselbe Vokabular für die Bausteine — und genau darin stand der zweite
    von drei Fällen von ``sitzungen``.

    Geschrieben wird an ZWEI Stellen: die normale Frage und die tiefe
    Recherche. Die Recherche legt zusätzlich ``research``, ``documents_read``
    und ``period`` ab; wer nur den ersten Schreiber liest, hält die Felder
    eines geladenen Recherche-Gesprächs fälschlich für Leichen.

    Gelesen wird jeweils der Aufruf von ``qa_turn_speichern`` und darin das
    Wörterbuch, das nach JSON verwandelt wird — nicht die Umgebung. Ein zu
    weit geschnittener Ausschnitt sammelt die Rahmen des Stroms mit ein und
    macht die Prüfung stumpf.
    """
    aus: set[str] = set()
    for datei in (FRAGE, RECHERCHE):
        baum = ast.parse(datei.read_text())
        # Das Wörterbuch steht nicht im Aufruf, sondern in einer Variablen
        # davor (`quellen_json = json.dumps({…})`). Also erst den Namen aus
        # dem Aufruf holen, dann seine Zuweisung suchen.
        namen: set[str] = set()
        for knoten in ast.walk(baum):
            if (isinstance(knoten, ast.Call) and isinstance(knoten.func, ast.Attribute)
                    and knoten.func.attr == "qa_turn_speichern"):
                namen |= {a.id for a in knoten.args if isinstance(a, ast.Name)}
                for tiefer in ast.walk(knoten):
                    if isinstance(tiefer, ast.Dict):
                        aus |= set(_dict_schluessel(tiefer))
        for knoten in ast.walk(baum):
            if (isinstance(knoten, ast.Assign) and len(knoten.targets) == 1
                    and isinstance(knoten.targets[0], ast.Name)
                    and knoten.targets[0].id in namen):
                for tiefer in ast.walk(knoten.value):
                    if isinstance(tiefer, ast.Dict):
                        aus |= set(_dict_schluessel(tiefer))
    return aus


def gesendet() -> tuple[dict[str, set[str]], set[str]]:
    """``(Rahmen beider Ströme, alle gesendeten Feldnamen)``."""
    rahmen = {**rahmen_der_frage()}
    for typ, felder in rahmen_der_recherche().items():
        rahmen.setdefault(typ, set()).update(felder)
    # `type` trägt JEDER Rahmen — es steht nicht in den Feldlisten, weil es
    # den Rahmen benennt, aber ein Client, der es liest, liest nichts Falsches.
    felder = {f for menge in rahmen.values() for f in menge} | {"type"}
    return rahmen, felder


def _block(text: str, von: str, bis: str) -> str:
    a = text.find(von)
    if a < 0:
        return ""
    b = text.find(bis, a)
    return text[a:b if b > 0 else len(text)]


def web_gelesen() -> set[str]:
    """Jedes ``msg.<feld>`` aus den Strom-Blöcken."""
    return set(re.findall(r"\bmsg\.([a-z_]+)\b", WEB.read_text())) - {"type"}


def web_blob_gelesen() -> set[str]:
    """Jedes ``t.sources?.<feld>`` — was das Web aus einem geladenen Gespräch holt."""
    return set(re.findall(r"t\.sources\?\.([a-z_]+)", WEB.read_text()))


def app_gelesen() -> set[str]:
    """Jeden Feldzugriff der App — aus der Ansicht UND aus dem Client.

    Die bequemen Zugriffe (`event.text`, `event.conversationID`) stehen nicht
    in der Ansicht, sondern als abgeleitete Eigenschaften im `SSEEvent`. Wer
    nur die Ansicht liest, prüft die Hälfte.
    """
    aus = set(re.findall(r'event\.fields\["([a-z_]+)"\]', APP.read_text()))
    aus |= set(re.findall(r'fields\["([a-z_]+)"\]', SSE_CLIENT.read_text()))
    kodier = _block(SSE_CLIENT.read_text(), "enum CodingKeys", "\n    }")
    aus |= set(re.findall(r'=\s*"([a-z_]+)"', kodier))
    for zeile in kodier.splitlines():
        treffer = re.match(r"\s*case\s+([a-z]+(?:,\s*[a-z]+)*)\s*$", zeile)
        if treffer:
            aus |= {t.strip() for t in treffer.group(1).split(",")}
    return aus


def befunde() -> list[tuple[str, str, str]]:
    """``[(Client, Quelle, Feld)]`` — gelesen, aber von niemandem geschrieben."""
    _rahmen, felder = gesendet()
    blob = gespeicherter_blob()
    aus = [("Web", "Strom", f) for f in sorted(web_gelesen() - felder)]
    aus += [("Web", "Gesprächs-Blob", f) for f in sorted(web_blob_gelesen() - blob)]
    aus += [("App", "Strom", f) for f in sorted(app_gelesen() - felder)]
    return aus


if __name__ == "__main__":
    rahmen, felder = gesendet()
    print(f"{len(rahmen)} Rahmen, {len(felder)} Felder:\n")
    for typ in sorted(rahmen):
        print(f"  {typ:12s} {', '.join(sorted(rahmen[typ])) or '—'}")
    print(f"\nGesprächs-Blob: {', '.join(sorted(gespeicherter_blob()))}")
    gefunden = befunde()
    print(f"\n{len(gefunden)} Befund(e):")
    for client, quelle, feld in gefunden:
        print(f"  {client} ({quelle}): liest {feld!r}, geschrieben wird es nirgends")
