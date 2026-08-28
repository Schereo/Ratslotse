"""These C1 (Stadion) trennscharf machen — Neuformulierung samt Einstufungen.

**Das Problem.** C1 lautete: „Ein Stadion-Neubau soll nicht aus Steuermitteln
finanziert werden." Das trennt nicht, weil es zwei verschiedene Fragen in einen
Satz packt — *ob überhaupt* Steuergeld fließt und *wie viel*. In Oldenburg
streitet aber niemand über die erste Frage. Die Programme bilden drei Lager:

1. **Die Stadt zahlt den Bau** (mit Deckel bzw. Controlling): CDU, SPD
2. **Die Stadt zahlt einen gedeckelten Anteil, Private müssen verbindlich mit**:
   Grüne, Bürger Bündnis
3. **Gar kein Steuergeld**: Volt, Michael Stille

Gegen den alten Wortlaut fiel Lager 2 zwangsläufig auf 0 („teils/teils") — und
zwar uneinheitlich: Die Grünen standen auf 0, das Bürger Bündnis auf +1, obwohl
beide dasselbe sagen (gedeckelter städtischer Anteil, verbindliche Beteiligung
Dritter). Das war ein Fehler in der Gleichbehandlung, kein Grenzfall.

**Die Lösung.** Der neue Wortlaut fragt nach dem *Anteil*, nicht nach dem
Ob-überhaupt. Damit fällt Lager 1 auf +1 und die Lager 2 und 3 gemeinsam auf -1
— jede der sechs Einstufungen ist am Wortlaut des jeweiligen Programms
nachweisbar, keine landet auf 0.

Dass das die Polarität dreht (Zustimmung hieß vorher „kein Steuergeld", jetzt
„Stadt zahlt allein"), ist unkritisch: Es gibt bewusst keine aggregierte
Ampel-Bilanz je Partei, und mehrere Thesen sind ohnehin invers formuliert.

Belege: alle wörtlichen Bruchstücke gegen kommunalwahl/programme/*.txt geprüft.
Seitenzahlen aus den „===== [Seite n] ====="-Marken; CDU und Stille haben keine
(CDU-Programm ohne Marken, Stille ist ein Presseartikel statt eines Programms).
⚠️ Für das Bürger-Bündnis-Positionspapier gibt es KEINE Seitenzahl — es hängt
als Webquelle hinter dem PDF im selben Volltext, die letzte Seitenmarke davor
(11) gehört noch zum PDF. Zitiert wird deshalb mit Seite 5 aus dem Hauptprogramm.

Idempotent: setzt Zielwerte. Danach analyse.py + build.py + pruefungen laufen lassen.
"""
import json
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

THESE_ID = "C1"

THESE_NEU = {
    "these": "Die Stadt soll den Stadion-Neubau nahezu vollständig selbst bezahlen.",
    "hinweis": "Geplanter Neubau an der Maastrichter Straße, mindestens 60 Mio. Euro. "
               "Die Streitfrage ist nicht die Kostenobergrenze — die fordern beide Seiten —, "
               "sondern ob Private einen nennenswerten Teil der Baukosten tragen müssen.",
}

POSITIONEN = {
    # Lager 1: Die Stadt baut und zahlt. Private nur im Betrieb bzw. gar nicht.
    "cdu": {
        "pos": 1,
        "beleg": "Die CDU „bekennt sich klar zum Bau eines neuen Stadions an der Maastrichter "
                 "Straße“. Die auf ihre Initiative beschlossene Kostenobergrenze begrenzt die "
                 "Summe, nicht den städtischen Anteil; private Partner sollen ausdrücklich nur "
                 "„die wirtschaftliche Betreibung des neuen Stadions gewährleisten“ — also den "
                 "Betrieb tragen, nicht den Bau.",
        "seite": None,
    },
    "spd": {
        "pos": 1,
        "beleg": "Zum Ratsbeschluss über den Neubau: „Wir stehen zu dieser Entscheidung.“ "
                 "Für die kommende Ratsperiode will die SPD den Bau eng begleiten und dabei "
                 "„insbesondere auf ein striktes Kostencontrolling setzen“, damit die Kosten "
                 "im Rahmen des Ratsbeschlusses bleiben. Eine Beteiligung Privater an den "
                 "Baukosten kommt im Programm nicht vor.",
        "seite": 36,
    },
    # Lager 2: gedeckelter städtischer Anteil, Private müssen verbindlich mittragen.
    "gruene": {
        "pos": -1,
        "beleg": "Die Grünen sprechen sich „für eine anteilige, gedeckelte Finanzierung des "
                 "Stadions“ aus und fordern „eine verbindliche Beteiligung des VfB Oldenburg "
                 "und von Sponsoren“ statt einseitiger städtischer Risikoübernahme. Statt "
                 "„einseitig Millionen in Bau und Betrieb für Jahrzehnte zu binden“, soll "
                 "vorrangig in die Sanierung bestehender Sportstätten investiert werden (S. 29).",
        "seite": 15,
    },
    "buergerbuendnis": {
        "pos": -1,
        "beleg": "Das Bündnis „lehnt eine vollständige Steuerfinanzierung des Projekts ab“ und "
                 "will das Gesamtvorhaben samt der vorgesehenen 100-prozentigen Finanzierung "
                 "durch die Stadt neu bewerten. Gefordert werden die „Deckelung des städtischen "
                 "Finanzierungsanteils“ mit Ausstiegsklausel sowie die „Beteiligung des Nutzers "
                 "und privater Investoren“; das Positionspapier vom 4. August 2026 verlangt "
                 "zusätzlich die „Einbindung von Investoren mit üblichem Eigenanteil“.",
        "seite": 5,
    },
    # Lager 3: gar kein Steuergeld.
    "volt": {
        "pos": -1,
        "beleg": "„Wir lehnen einen aus Steuermitteln finanzierten Stadionneubau ab.“ Volt "
                 "spricht sich darüber hinaus gegen den Neubau überhaupt aus und zieht „eine "
                 "klare Grenze zwischen kommunaler Daseinsvorsorge“ und der Unterstützung des "
                 "Profifußballs (S. 46).",
        "seite": 42,
    },
    "stille": {
        "pos": -1,
        "beleg": "Fordert eine private Stadionfinanzierung statt Ausgaben aus dem städtischen "
                 "Haushalt: „Beim Stadion hätte er sich für eine private Finanzierung "
                 "eingesetzt.“",
        "seite": None,
    },
}


def lade(pfad):
    with open(pfad, encoding="utf-8") as f:
        return json.load(f)


def schreibe(pfad, daten):
    with open(pfad, "w", encoding="utf-8") as f:
        json.dump(daten, f, ensure_ascii=False, indent=1)
        f.write("\n")


def main():
    geaendert = 0

    pfad = os.path.join(BASE, "thesen.json")
    d = lade(pfad)
    treffer = [t for t in d["thesen"] if t["id"] == THESE_ID]
    if len(treffer) != 1:
        raise SystemExit(f"These {THESE_ID}: {len(treffer)} Treffer statt genau einem — "
                         f"Abbruch, nichts geschrieben.")
    t = treffer[0]
    if not all(t.get(k) == v for k, v in THESE_NEU.items()):
        t.update(THESE_NEU)
        print(f"  thesen/{THESE_ID}: neu formuliert")
        print(f"    → {THESE_NEU['these']}")
        geaendert += 1
        schreibe(pfad, d)

    for slug, neu in POSITIONEN.items():
        pfad = os.path.join(BASE, "positionen", f"{slug}.json")
        d = lade(pfad)
        alt = d["positionen"][THESE_ID]
        if all(alt.get(k) == v for k, v in neu.items()):
            continue
        vorher = alt.get("pos")
        alt.update(neu)
        schreibe(pfad, d)
        pfeil = f" (pos {vorher!r} -> {neu['pos']!r})" if vorher != neu["pos"] else ""
        print(f"  {slug}/{THESE_ID}: aktualisiert{pfeil}")
        geaendert += 1

    # Wer nichts zum Stadion sagt, sagt weiterhin nichts — aber das soll geprüft
    # sein und nicht bloß so geblieben: Die übrigen zehn Listen erwähnen weder
    # „Stadion" noch „VfB", „Maastrichter" oder „Marschweg" in ihrem Programm.
    unberuehrt = []
    for datei in sorted(os.listdir(os.path.join(BASE, "positionen"))):
        slug = datei[:-5]
        if slug in POSITIONEN:
            continue
        d = lade(os.path.join(BASE, "positionen", datei))
        if d["positionen"][THESE_ID]["pos"] is not None:
            unberuehrt.append(slug)
    if unberuehrt:
        raise SystemExit(f"Unerwartete Einstufung bei: {unberuehrt} — bitte prüfen.")

    print(f"\n{geaendert} Änderungen. Jetzt `python3 kommunalwahl/analyse.py` "
          f"und `python3 kommunalwahl/build.py` laufen lassen.")


if __name__ == "__main__":
    main()
