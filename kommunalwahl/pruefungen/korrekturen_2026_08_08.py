"""Korrekturen aus der Schwarm-Prüfung vom 08.08.2026 (28 Sonnet-Finder + Skeptiker,
1 227 geprüfte Aussagen, 12 bestätigte Befunde — Protokoll: pruefbericht.md §8).

Idempotent: setzt Zielwerte. Danach analyse.py + pruef_struktur.py laufen lassen.
"""
import json
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def lade(pfad):
    with open(pfad, encoding="utf-8") as f:
        return json.load(f)


def schreibe(pfad, daten):
    with open(pfad, "w", encoding="utf-8") as f:
        json.dump(daten, f, ensure_ascii=False, indent=1)
        f.write("\n")


# ── Positionen ──────────────────────────────────────────────────────────────
POSITIONEN = {
    # AfD P1: Text fordert „verbindliche Bürgerbefragungen" ausdrücklich als
    # freiwilligen Ersatz für zu hoch gehürdete Bürgerbegehren — ein schwächeres
    # Instrument als der geforderte Bürgerentscheid. Volt bekam für dieselbe
    # Abstufung eine 0; Gleichbehandlung (Bauplan E4).
    ("afd", "P1"): {
        "pos": 0,
        "beleg": "Das Programm fordert 'verbindliche Bürgerbefragungen' bei weitreichenden "
                 "Entscheidungen wie kostspieligen Großprojekten — ausdrücklich als freiwilliger "
                 "Weg, weil die formalen Hürden für Bürgerbegehren als zu hoch gelten; ein "
                 "förmlicher Bürgerentscheid wird nicht gefordert.",
        "seite": 41,
    },
    # AfD V1: S. 12 trägt nur den 'Genehmigungsturbo'; 'Bau-Turbo' und
    # Genehmigungsfiktion stehen auf S. 36 — Hauptfundstelle dorthin, Beleg
    # nennt beide Seiten.
    ("afd", "V1"): {
        "beleg": "Das Programm fordert den 'Bau-Turbo' mit digitalen Bauanträgen und einer "
                 "Genehmigungsfiktion (automatische Genehmigung nach Fristablauf), dazu einen "
                 "'Genehmigungsturbo' für Bau- und Wirtschaftsanträge (S. 12).",
        "seite": 36,
    },
    # AfD C3: Der Text nennt „queere Aktivismus-Workshops", nicht
    # „soziokulturelle" — die Ersetzung verschob die Aussage.
    ("afd", "C3"): {
        "beleg": "Die Finanzierung von Staatstheater, Museen und Denkmalpflege soll nur "
                 "gesichert bleiben (keine Erhöhung); steuerfinanzierte Formate zu "
                 "'ideologischen Nischenthemen (wie etwa queere Aktivismus-Workshops)' werden "
                 "explizit abgelehnt.",
    },
    # Grüne S3: Streetworker-Teil steht auf S. 19 (Wohnungslosenhilfe), nicht
    # S. 31 — beide Fundstellen jetzt im Beleg ausgewiesen.
    ("gruene", "S3"): {
        "beleg": "Neben dem autonomen Frauen*haus gibt es seit Ende 2025 ein zweites "
                 "Frauen*haus; weiterer Handlungsbedarf bei Zufluchtsstätten wird gesehen "
                 "(S. 31), zudem Stärkung des Streetworkerteams statt eines Szeneplatzes (S. 19).",
        "seite": 31,
    },
    # BB-OL C3: „drei bis vier Wochen" ist die frühere Dauer des Kultursommers —
    # gefordert wird die Ausweitung auf drei Wochen.
    ("buergerbuendnis", "C3"): {
        "beleg": "Setzt sich dafür ein, den auf rund zehn Tage verkürzten Kultursommer wieder "
                 "auf drei Wochen auszuweiten (früher dauerte er drei bis vier Wochen).",
    },
}

# ── Digest-Texte ────────────────────────────────────────────────────────────
DIGEST_TEXTE = [
    # (slug, pfad-innerhalb-digest, alter Teilstring, neuer Text)
    ("buergerbuendnis", ("besonderes", 3),
     None,
     "Konkrete Forderung, den auf rund zehn Tage verkürzten Oldenburger Kultursommer "
     "wieder auf drei Wochen auszuweiten (die frühere Dauer lag bei drei bis vier Wochen)."),
    ("buergerbuendnis", ("themen", "kultur", "positionen", 2),
     None,
     "Ausweitung des Oldenburger Kultursommers von derzeit rund zehn Tagen zurück auf "
     "drei Wochen."),
    ("fdp", ("themen", "wohnen", "positionen", 1),
     None,
     "Guenstiger Wohnraum ueber die bestehende Wohnungsbaugesellschaft GSG (Gemeinnuetzige "
     "Siedlungsgesellschaft), an der die Stadt beteiligt ist, statt einer weiteren "
     "Wohnungsgesellschaft."),
    ("gruene", ("themen", "digitales", "positionen", 3),
     None,
     "Ausbau von Qualifizierungsangeboten, Schulungen und professionellem Changemanagement "
     "für die Beschäftigten der Stadtverwaltung — mit über 3.300 Mitarbeitenden eine der "
     "größten Arbeitgeberinnen Oldenburgs."),
]

# ── Seitenlisten der Themenfelder vervollständigen ──────────────────────────
# Fundstellen einzelner Bullets, die außerhalb der bisherigen Feld-Liste lagen.
SEITEN_ERGAENZUNGEN = {
    ("gruene", "beteiligung"): [20],
    ("linke", "beteiligung"): [7, 18],
    ("linke", "wirtschaft"): [7],
    ("linke", "kultur"): [16],
    ("linke", "sicherheit"): [25],
    ("volt", "sicherheit"): [60],
    ("spd", "mobilitaet"): [20],
}


def main():
    geaendert = 0

    nach_liste = {}
    for (slug, tid), neu in POSITIONEN.items():
        nach_liste.setdefault(slug, {})[tid] = neu
    for slug, aenderungen in nach_liste.items():
        pfad = os.path.join(BASE, "positionen", f"{slug}.json")
        d = lade(pfad)
        for tid, neu in aenderungen.items():
            alt = d["positionen"][tid]
            if all(alt.get(k) == v for k, v in neu.items()):
                continue
            print(f"  {slug}/{tid}: aktualisiert" + (f" (pos {alt['pos']!r} -> {neu['pos']!r})" if "pos" in neu and neu["pos"] != alt["pos"] else ""))
            alt.update(neu)
            geaendert += 1
        schreibe(pfad, d)

    for slug, pfad_teile, _, neu in DIGEST_TEXTE:
        pfad = os.path.join(BASE, "digests", f"{slug}.json")
        d = lade(pfad)
        ziel = d
        for teil in pfad_teile[:-1]:
            ziel = ziel[teil]
        idx = pfad_teile[-1]
        if ziel[idx] != neu:
            ziel[idx] = neu
            print(f"  digests/{slug}: {'.'.join(map(str, pfad_teile))} korrigiert")
            geaendert += 1
        schreibe(pfad, d)

    for (slug, feld), seiten in SEITEN_ERGAENZUNGEN.items():
        pfad = os.path.join(BASE, "digests", f"{slug}.json")
        d = lade(pfad)
        liste = d["themen"][feld]["seiten"]
        fuer = [s for s in seiten if s not in liste]
        if fuer:
            liste.extend(fuer)
            liste.sort()
            print(f"  digests/{slug}: themen.{feld}.seiten += {fuer}")
            geaendert += 1
        schreibe(pfad, d)

    print(f"\n{geaendert} Änderungen. Jetzt `python3 kommunalwahl/analyse.py` laufen lassen.")


if __name__ == "__main__":
    main()
