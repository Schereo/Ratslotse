"""Wächter: Keine Haushaltszahl steht im Kontext unter einem fremden Jahr.

**Der Anlass (Faktencheck 23.09.2026, 14 Antworten von Lotti und Frag den
Rat).** Zwei Fehler lagen nicht am Modell, sondern am Kontext, den wir ihm
geben. Der Schulden-Baustein schrieb die Aufteilung nach Schuldenarten des
JÜNGSTEN Jahres eingerückt unter die Zeile „Ein Jahr davor (2024)“ — Frag den
Rat antwortete daraufhin „2024 … davon 41 Mio. € Kreditmarkt, 296 Mio. €
Eigenbetriebe“; das sind die Werte 2025. Der Investitions-Baustein hängte die
Auszahlungsarten 2025 unter „Höchster Wert der Reihe: 2020“, und Lotti nannte
„2020 … Sonstige Investitionstätigkeit rund 20 Mio. €“ (2020 waren es
34,3 Mio. €). Das Modell hat in beiden Fällen den Kontext wörtlich gelesen.

Eine eingerückte Zeile LIEST SICH wie die Aufschlüsselung der Zeile darüber.
Deshalb prüft dieser Wächter für jeden Baustein jeder Facette die Gliederung:

1. ``davon`` steht nie auf oberster Ebene — es hängt unter seiner Summe.
2. Eine ``davon``-Zeile trägt ihr Jahr selbst, und es ist das Jahr ihrer
   Summe.
3. Mehrere ``davon``-Zeilen unter einer Summe ergeben zusammen diese Summe
   (± Rundung); eine einzelne ist höchstens so groß wie sie.
4. Jede eingerückte Zeile mit einem Euro-Betrag nennt ihr Jahr selbst — ein
   Betrag, dessen Jahr man aus der Zeile darüber erschließen muss, wird unter
   der falschen Zeile zum falschen Jahr.
5. Nennt eine eingerückte Zeile mit Betrag ein Jahr, ist es eines der Zeile
   darüber — oder die Zeile darüber nennt gar keins (dann ist sie ein Kopf
   wie „- Abfallwirtschaftsbetrieb:“, und jede Zeile darunter trägt ihr
   eigenes Jahr).

**Woher die Daten kommen.** Zweimal, weil jede Quelle eine Lücke hat:

* ``tests/fixtures/geld_kontext_echt.json`` — die Store-Ausgaben ALLER
  Facetten für ein Fragenbündel, gezogen aus dem dev-Abzug. Echte Zahlen, und
  sie laufen in der CI. Neu schneiden (nach einer Änderung an einer
  Store-Methode oder einer neuen Facette)::

      .venv/bin/python -m tests.test_geld_gliederung --neu data/council.sqlite

* die lokale Datenbank (``RATSLOTSE_MESS_DB``, sonst ``data/council.sqlite``)
  — derselbe Durchlauf gegen den heutigen Bestand; ohne Abzug entfällt er.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

import pytest

from council import qa

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "geld_kontext_echt.json"
ECHTE_DB = Path(os.environ.get("RATSLOTSE_MESS_DB")
                or Path(__file__).resolve().parents[1] / "data" / "council.sqlite")

#: Das Fragenbündel für den Abzug: die Probefrage jeder Modul-Facette (steht
#: nicht hier, sondern kommt aus dem Register) plus die Fragen, die die alten
#: Facetten und ihre Jahrgangs-Varianten ziehen. Die Jahresfragen sind
#: gewollt: Ein gefragtes Jahr, das nicht das jüngste ist, baut andere Zeilen
#: (Lücke 2019 bei den Investitionen, fehlende Aufteilung 2022 bei den
#: Schulden) — genau dort saßen die Fehler.
FRAGEN = [
    "Wie hoch sind die Schulden der Stadt?",
    "Wie viele Schulden hatte die Stadt 2022?",
    "Wie hoch waren die Schulden 2024?",
    "Wofür gibt die Stadt bei den Investitionen am meisten aus?",
    "Was wurde 2020 investiert?",
    "Was wurde 2018 investiert?",
    "Was steht in der Bilanz?",
    "Wie viel wurde nachbewilligt?",
    "Wie hoch ist die Eigenkapitalquote laut Kennzahlen?",
    "Wie viele Stellen sind unbesetzt?",
    "Wer wollte den Haushalt ändern?",
    "Was ist im Jahresabschluss tatsächlich herausgekommen?",
    "Warum gab es ein Defizit?",
    "Was hat das Rechnungsprüfungsamt beanstandet?",
    "Was kostet die Feuerwehr?",
    "Was gibt die Stadt insgesamt aus, mit dem Konzern?",
    "Wie steht Oldenburg im Vergleich zu Osnabrück da?",
    "Wie viel Gewerbesteuer nimmt die Stadt ein?",
    "Wie hoch ist die Müllgebühr?",
    "Wie viel Geld ist tatsächlich geflossen, Kassensicht?",
    "Wie groß ist der Haushalt?",
    "Wie hat sich die Grundsteuer in Oldenburg entwickelt?",
    "Welche Eigenbetriebe gibt es und wie viel geben sie aus?",
    "Wie viel Geld hatte die Stadt 2024 auf dem Konto?",
    "Wie viele Betriebe zahlen Gewerbesteuer?",
    "Was steht im Wirtschaftsplan des Bäderbetriebs?",
]


# ---------------------------------------------------------------------------
# Die Prüfung
# ---------------------------------------------------------------------------

_JAHR = re.compile(r"(?<!\d)(19[5-9]\d|20[0-4]\d)(?!\d)")
_BETRAG = re.compile(r"(-?\d{1,3}(?:\.\d{3})*(?:,\d+)?|-?\d+(?:,\d+)?)\s*(Mio\. €|€)")
_ZEILE = re.compile(r"^( *)- (.*)$")


def _label(text: str) -> str:
    """Der Teil vor dem ersten Doppelpunkt — dort steht, WOVON die Zahl
    handelt. Im Wert dahinter stehen oft andere Jahre („2015 waren es …"),
    die die Zeile nicht datieren."""
    return text.split(": ", 1)[0]


def _jahre(text: str) -> set[str]:
    return set(_JAHR.findall(_label(text)))


def _betraege(text: str) -> list[tuple[float, float]]:
    """``[(Betrag, Rundungsspanne)]`` im WERT-Teil der Zeile, in Euro."""
    wert = text.split(": ", 1)[1] if ": " in text else text
    aus = []
    for zahl, einheit in _BETRAG.findall(wert):
        v = float(zahl.replace(".", "").replace(",", "."))
        if einheit.startswith("Mio"):
            aus.append((v * 1e6, 0.05e6))
        else:
            aus.append((v, 0.5))
    return aus


def gliederungsfehler(text: str) -> list[str]:
    """Alle Verstöße gegen die fünf Regeln im Modul-Docstring."""
    zeilen = []   # (Einrückung, Text, Index des Elternteils oder None)
    for roh in text.splitlines():
        m = _ZEILE.match(roh)
        if not m:
            continue
        tiefe, inhalt = len(m.group(1)), m.group(2)
        eltern = next((i for i in range(len(zeilen) - 1, -1, -1)
                       if zeilen[i][0] < tiefe), None)
        zeilen.append((tiefe, inhalt, eltern))

    fehler: list[str] = []
    gruppen: dict[int, list[str]] = {}
    for tiefe, inhalt, eltern in zeilen:
        ist_davon = inhalt.lower().startswith("davon ")
        if eltern is None:
            if ist_davon:
                fehler.append(f"„davon“ ohne Summe darüber: {inhalt[:90]}")
            continue
        oben = zeilen[eltern][1]
        j_oben, j_hier = _jahre(oben), _jahre(inhalt)
        if ist_davon:
            gruppen.setdefault(eltern, []).append(inhalt)
            if not j_hier:
                fehler.append(f"„davon“ ohne eigenes Jahr: {inhalt[:90]}  "
                              f"(unter: {oben[:70]})")
            elif not j_oben:
                fehler.append(f"„davon“ unter einer Zeile ohne Jahr: {inhalt[:90]}  "
                              f"(unter: {oben[:70]})")
        if _betraege(inhalt) and not j_hier:
            fehler.append(f"Betrag ohne eigenes Jahr: {inhalt[:90]}  (unter: {oben[:70]})")
        # Nur Zeilen mit Betrag: Ein Prosa-Satz darunter („der laufende
        # Betrieb liegt seit 2005 dort“) datiert keine Zahl.
        if _betraege(inhalt) and j_hier and j_oben and not j_hier <= j_oben:
            fehler.append(f"Jahr {sorted(j_hier)} unter fremdem Jahr {sorted(j_oben)}: "
                          f"{inhalt[:90]}  (unter: {oben[:70]})")
    for eltern, kinder in gruppen.items():
        oben = zeilen[eltern][1]
        summe = _betraege(oben)
        teile = [b[0] for b in (_betraege(k) for k in kinder) if b]
        spannen = [b[0][1] for b in (_betraege(k) for k in kinder) if b]
        if not summe:
            fehler.append(f"„davon“ unter einer Zeile ohne Betrag: {oben[:90]}")
            continue
        soll, spanne = summe[0]
        toleranz = spanne + sum(spannen) + abs(soll) * 0.002
        if len(teile) >= 2 and abs(sum(v for v, _ in teile) - soll) > toleranz:
            fehler.append(f"„davon“-Zeilen ergeben {sum(v for v, _ in teile):,.0f} €, "
                          f"die Summe darüber ist {soll:,.0f} €: {oben[:90]}")
        if len(teile) == 1 and abs(teile[0][0]) > abs(soll) + toleranz:
            fehler.append(f"„davon“ größer als seine Summe: {kinder[0][:90]}  "
                          f"(unter: {oben[:70]})")
    return fehler


# ---------------------------------------------------------------------------
# Die Prüfung prüft etwas (sonst ist jeder Lauf grün)
# ---------------------------------------------------------------------------

#: Der Schulden-Baustein im Stand vom 23.09.2026 — wörtlich, wie er im Prompt
#: von Frag den Rat stand.
_ALT_SCHULDEN = """
- Schuldenstand am Jahresende 2025: 336.994.000 € — das sind 1.908 € je Einwohner*in
- Ein Jahr davor (2024): 294.851.000 €
  - davon Schulden aus Kreditmarktmitteln: 40.804.000 €
  - davon Schulden der Eigenbetriebe einschließlich Kliniken und innere Darlehen: 296.190.000 €
"""

#: Der Investitions-Baustein desselben Tages — die Aufteilung 2025 unter 2020.
_ALT_GEBAUT = """
- Tatsächliche Investitions-Auszahlungen 2025: 60.773.000 €
- Höchster Wert der Reihe (sie beginnt 2010): 2020 mit 70.481.000 €
  - davon Baumaßnahmen: 16.208.000 €
  - davon Sonstige Investitionstätigkeit: 20.083.000 €
"""


def test_pruefung_faengt_die_beiden_gefundenen_fehler():
    assert any("ohne eigenes Jahr" in f for f in gliederungsfehler(_ALT_SCHULDEN))
    assert any("ergeben" in f for f in gliederungsfehler(_ALT_SCHULDEN))
    assert any("ohne eigenes Jahr" in f for f in gliederungsfehler(_ALT_GEBAUT))


def test_pruefung_laesst_die_richtige_form_durch():
    richtig = """
- Schuldenstand am Jahresende 2025: 336.994.000 €
  - davon Schulden aus Kreditmarktmitteln 2025: 40.804.000 €
  - davon Schulden der Eigenbetriebe 2025: 296.190.000 €
- Ein Jahr davor (2024): 294.851.000 €
"""
    assert gliederungsfehler(richtig) == []


def test_pruefung_faengt_ein_fremdes_jahr_und_ein_davon_ohne_summe():
    assert gliederungsfehler("- Tiefster Stand seit 2015: 1 €\n  - Ende März 2024: 2 €")
    assert gliederungsfehler("- davon Erwerb 2024: 3 €")
    assert gliederungsfehler("- Summe 2024: 10 €\n  - davon A 2024: 30 €")


# ---------------------------------------------------------------------------
# Jede Facette, echte Zahlen
# ---------------------------------------------------------------------------

def _fixture() -> dict[str, list]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _faelle(geld_je_schluessel: dict[str, list]) -> list[tuple[str, int, str]]:
    """``[(Facette, Nr., Bausteintext)]`` — jede Variante jeder Facette."""
    aus = []
    for facette in qa.GELD_FACETTEN:
        key, bauer = qa._GELD_BAUSTEINE[facette]
        for nr, daten in enumerate(geld_je_schluessel.get(key) or []):
            text = bauer(daten)
            if text:
                aus.append((facette, nr, text))
    return aus


def test_abzug_deckt_jede_facette():
    """Beide Richtungen: Jede Facette hat im Abzug mindestens einen Baustein
    — eine neue Facette fällt sonst durch den Wächter, ohne dass es jemand
    merkt —, und der Abzug trägt keinen Schlüssel, den es nicht mehr gibt."""
    daten = _fixture()
    gedeckt = {f for f, _nr, _t in _faelle(daten)}
    fehlt = [f for f in qa.GELD_FACETTEN if f not in gedeckt]
    schluessel = {qa._GELD_BAUSTEINE[f][0] for f in qa.GELD_FACETTEN}
    fremd = sorted(set(daten) - schluessel)
    assert not fehlt and not fremd, (
        f"Facetten ohne Baustein im Abzug: {fehlt}; Schlüssel ohne Facette: {fremd}. "
        "Frage ergänzen (FRAGEN hier im Modul) und neu schneiden: "
        ".venv/bin/python -m tests.test_geld_gliederung --neu data/council.sqlite")


@pytest.mark.parametrize("facette", qa.GELD_FACETTEN)
def test_keine_zahl_unter_fremdem_jahr(facette):
    fehler = [f"[{fac} #{nr}] {f}" for fac, nr, text in _faelle(_fixture())
              if fac == facette for f in gliederungsfehler(text)]
    assert not fehler, "\n".join(fehler)


@pytest.mark.skipif(not ECHTE_DB.exists(), reason="kein lokaler Abzug (scripts/lokale_daten.py)")
def test_keine_zahl_unter_fremdem_jahr_am_bestand(tmp_path):
    """Derselbe Durchlauf gegen die lokale Datenbank — was der Abzug oben
    noch nicht kennt (ein neuer Jahrgang, eine neue Zeile), fällt hier auf."""
    fehler = []
    for fac, nr, text in _faelle(_abziehen(ECHTE_DB)):
        fehler += [f"[{fac} #{nr}] {f}" for f in gliederungsfehler(text)]
    assert not fehler, "\n".join(fehler)


# ---------------------------------------------------------------------------
# Der Abzug
# ---------------------------------------------------------------------------

def _abziehen(pfad: Path) -> dict[str, list]:
    """Die Store-Ausgaben aller Facetten für :data:`FRAGEN`, je Schlüssel
    ohne Dubletten. Auf einer KOPIE: ``CouncilStore`` migriert beim Öffnen."""
    import shutil
    import tempfile

    from council import geld
    from council.store import CouncilStore

    with tempfile.TemporaryDirectory() as tmp:
        kopie = Path(tmp) / "c.sqlite"
        shutil.copyfile(pfad, kopie)
        store = CouncilStore(kopie)
        try:
            aus: dict[str, list] = {}
            gesehen: set[str] = set()
            for frage in [f.probefrage for f in geld.FACETTEN] + FRAGEN:
                g = qa.geld_kontext(store, frage, frage, "money")
                for key, daten in g.items():
                    if key == "facets" or not daten:
                        continue
                    kennung = key + json.dumps(daten, sort_keys=True, default=str)
                    if kennung in gesehen:
                        continue
                    gesehen.add(kennung)
                    # JSON-Rundreise: Tupel werden Listen — so, wie die
                    # Bausteine sie im Test auch aus dem Abzug bekommen.
                    aus.setdefault(key, []).append(
                        json.loads(json.dumps(daten, default=str)))
            return aus
        finally:
            store.close()


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] != "--neu":
        sys.exit("Aufruf: python -m tests.test_geld_gliederung --neu data/council.sqlite")
    daten = _abziehen(Path(sys.argv[2]))
    FIXTURE.write_text(json.dumps(daten, ensure_ascii=False, indent=1, sort_keys=True)
                       + "\n", encoding="utf-8")
    print(f"{FIXTURE}: {sum(len(v) for v in daten.values())} Bausteine, "
          f"{len(daten)} Schlüssel")
