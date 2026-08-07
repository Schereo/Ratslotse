"""Einmalige Korrekturen aus pruefbericht.md §2 und §3.

Idempotent: setzt Zielwerte, statt zu rechnen. Nach dem Lauf `analyse.py` neu
laufen lassen — Paar- und Streitwerte ändern sich dadurch.

Belegt ist jede Änderung in ../pruefbericht.md. Kurzfassung:
  C1 gruene  Grüne und BB-OL vertreten dieselbe Position (anteilig + gedeckelt +
             verbindliche private Beteiligung), standen aber auf -1 und +1.
  W3 bsw     Wie die SPD nur ein Instrument von dreien — SPD hatte dafür 0.
  M3 volt    Beleg spricht über Stellplätze, nicht über Gebührenhöhe; die
             Behauptung „P+R in Innenstadtnähe schließen" steht nicht im Programm.
  I4 cdu     „Bund und Land sollen zahlen" ist keine Absage an eigenes Engagement.
  P2 spd     Nennt keines der drei Rechte, nach denen die These fragt.
  C3 spd     Rückschau auf Erreichtes plus „bei Bedarf" trägt kein volles Ja.
"""
import json, os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

POSITIONEN = {
    ("gruene", "C1"): {
        "pos": 0,
        "beleg": "Spricht sich für eine „anteilige, gedeckelte Finanzierung des Stadions“ aus "
                 "und fordert eine verbindliche Beteiligung des VfB Oldenburg und von Sponsoren "
                 "– Steuermittel also anteilig ja, aber nicht allein und nicht unbegrenzt.",
        "seite": 15,
    },
    ("bsw", "W3"): {
        "pos": 0,
        "beleg": "Nennt allein die Zweckentfremdungssatzung: „Durch die Einführung kommunaler "
                 "Zweckentfremdungssatzungen können Städte und Gemeinden wirksam gegen Leerstand“ "
                 "vorgehen – Leerstandsabgabe und Enteignung kommen im Programm nicht vor.",
        "seite": 27,
    },
    ("volt", "M3"): {"pos": None, "beleg": None, "seite": None},
    ("cdu", "I4"): {"pos": None, "beleg": None, "seite": None},
    ("spd", "P2"): {
        "pos": 0,
        "beleg": "Fordert ein „dauerhaftes, demokratisch legitimiertes Kinder- und "
                 "Jugendparlament“ mit „verbindlicher und transparenter Mitbestimmung“, "
                 "benennt aber weder Rede- noch Antragsrecht noch ein eigenes Budget.",
        "seite": 25,
    },
    ("spd", "C3"): {
        "pos": 0,
        "beleg": "Nennt überwiegend Erreichtes (Vergnügungssteuer für Clubs abgeschafft, "
                 "Beauftragte für Nachtkultur) und will die MachIWerk-Förderung fortsetzen und "
                 "„bei Bedarf“ ausweiten – keine klare Zusage für insgesamt mehr Mittel.",
        "seite": 35,
    },
    # Fundstelle steht auf S. 11, die Seitenzahl fehlte (pruefbericht.md §2.8)
    ("buergerbuendnis", "M4"): {"seite": 11},
    ("buergerbuendnis", "P2"): {"seite": 11},
}

# pruefbericht.md §3: Prämissen, die ohne Hinweis in die Irre führen
HINWEISE = {
    "W1": "Der Stadtrat hat die Gründung 2025 bereits beschlossen. Strittig ist deshalb "
          "nicht mehr das Ob, sondern ob die neue Gesellschaft ausgebaut oder "
          "zurückgedreht wird.",
    "B2": "Nur zwei der neun Listen äußern sich dazu — der Kindergartenbeitrag ab drei "
          "Jahren ist in Niedersachsen landesrechtlich beitragsfrei, kommunal bleibt vor "
          "allem die Krippe.",
}

# pruefbericht.md §2.8: Zusatz steht nicht im Programm („wieder Sirenen aufstellen“)
BESONDERES = {
    "spd": [("Wiederaufstellung von Warnsirenen mit regelmäßigen Probealarmen – erstmals seit über 30 Jahren.",
             "Wiederaufstellung von Warnsirenen mit regelmäßigen Probealarmen, abgestimmt mit dem Land.")],
}


def schreibe(pfad, daten):
    with open(pfad, "w", encoding="utf-8") as f:
        json.dump(daten, f, ensure_ascii=False, indent=1)
        f.write("\n")


def main():
    geaendert = 0

    nach_liste = {}
    for (slug, tid), neu in POSITIONEN.items():
        nach_liste.setdefault(slug, {})[tid] = neu
    for slug, aenderungen in nach_liste.items():
        pfad = os.path.join(BASE, "positionen", f"{slug}.json")
        d = json.load(open(pfad, encoding="utf-8"))
        for tid, neu in aenderungen.items():
            alt = d["positionen"][tid]
            if all(alt.get(k) == v for k, v in neu.items()):
                continue
            print(f"  {slug}/{tid}: pos {alt['pos']!r} -> {neu.get('pos', alt['pos'])!r}")
            alt.update(neu)
            geaendert += 1
        schreibe(pfad, d)

    pfad = os.path.join(BASE, "thesen.json")
    d = json.load(open(pfad, encoding="utf-8"))
    for t in d["thesen"]:
        if t["id"] in HINWEISE and t.get("hinweis") != HINWEISE[t["id"]]:
            print(f"  thesen/{t['id']}: hinweis gesetzt")
            t["hinweis"] = HINWEISE[t["id"]]
            geaendert += 1
    schreibe(pfad, d)

    for slug, paare in BESONDERES.items():
        pfad = os.path.join(BASE, "digests", f"{slug}.json")
        d = json.load(open(pfad, encoding="utf-8"))
        for altText, neuText in paare:
            b = d.get("besonderes") or []
            if altText in b:
                b[b.index(altText)] = neuText
                print(f"  digests/{slug}: besonderes korrigiert")
                geaendert += 1
        schreibe(pfad, d)

    print(f"\n{geaendert} Änderungen. Jetzt `python3 kommunalwahl/analyse.py` laufen lassen.")


if __name__ == "__main__":
    main()
