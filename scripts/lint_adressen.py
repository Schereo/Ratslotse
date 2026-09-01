#!/usr/bin/env python3
"""Findet fremde E-Mail-Adressen in versionierten Dateien.

Warum es das gibt: Am 12.08.2026 stand die Adresse einer echten Nutzerin als
Beispielaufruf im Docstring von ``scripts/qa_verlauf.py`` — in einem
öffentlichen Repo. Sie herauszubekommen kostete einen History-Rewrite (alle
Commit-Hashes neu, 301 GPG-Signaturen verloren) und eine Anfrage beim
GitHub-Support, weil ein Force-Push die alten Objekte nicht entfernt.

Der Aufwand steht in keinem Verhältnis zu den zwei Sekunden, die dieser Check
braucht. Deshalb läuft er in der CI und blockt den PR.

Erlaubt sind nur Adressen auf den Domains in ``ERLAUBTE_DOMAINS``: die eigenen
(Kontakt, Absender) und die für Beispiele reservierten aus RFC 2606. Alles
andere ist im Zweifel die Adresse einer echten Person und hat hier nichts zu
suchen — auch nicht „nur als Beispiel".

Aufruf:
    python scripts/lint_adressen.py           # ganzes Repo
    python scripts/lint_adressen.py --diff    # nur geänderte Dateien vs. main
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

# RFC 2606 reserviert example.* ausdrücklich für Dokumentation — solche Adressen
# können niemandem gehören. Dazu die eigenen Domains: `timsigl.de` trägt die
# Kontaktadresse (Impressum, Datenschutz, Hilfe), `ratslotse.de` den Absender.
#
# `test.de` steht hier, weil die Suite es durchgängig als Fixture-Domain nutzt
# (rund 50 Stellen). Ein Freibrief ist das nicht: Gesucht wird die Adresse einer
# echten Person, und die steht nicht auf der Wegwerf-Domain der eigenen Tests,
# sondern bei einem Freemailer. Genau dort greift der Check.
ERLAUBTE_DOMAINS = {
    "example.com", "example.org", "example.net", "example.edu",
    "timsigl.de",
    "ratslotse.de",
    "test.de",
}

# Einzelne Fixture-Adressen auf Ein-Buchstaben-Domains. Bewusst vollständig
# aufgezählt statt die Domains freizugeben — `x.de` oder `b.de` gehören
# jemandem. Wer eine neue Fixture braucht, nimmt example.org; dann muss hier
# gar nichts nachgetragen werden.
ERLAUBTE_ADRESSEN = {
    "a@b.de", "b@b.de", "a@t.de", "b@t.de", "a@x.de", "b@x.de", "f@x.de",
    "still@b.de", "laut@b.de",
    # Kommunalwahl-Quelldaten (kommunalwahl/): publizierte Kontaktadressen aus
    # den Wahlprogrammen der Parteien bzw. der amtlichen Bekanntmachung der
    # Wahlvorschläge — Teil zitierter öffentlicher Dokumente, deren Wortlaut
    # wir belegbar halten (Maskieren hieße, die Quelle zu verändern). Bewusst
    # einzeln aufgezählt, nicht per Domain oder Verzeichnis: Jede weitere
    # Adresse soll wieder hier auflaufen und begründet werden müssen.
    # (Entscheidung Tim, 15.08.2026.)
    "info@pgm-partei.de",            # PGM, Impressum/Programm
    "info@gruene-oldenburg.de",      # Grüne, Programm
    "buero.oldenburg@spd.de",        # SPD, Programm
    "moin@bb-ol.org",                # Bürgerbündnis, Programm
    "moin@holger-wilkens.de",        # Bürgerbündnis, Kontakt lt. eigenem Programm
    "wahlbuero@stadt-oldenburg.de",  # Stadt, Bekanntmachung Wahlvorschläge
}

# Nicht von uns geschrieben und nicht von uns zu verantworten: Lockfiles tragen
# die Adressen von Paket-Autoren aus Upstream-Meldungen (npm-Deprecations).
# Der CHANGELOG steht bewusst NICHT hier — er ist unsere eigene Prosa und damit
# genauso ein möglicher Ort für eine verirrte Adresse wie jede andere Datei.
AUSGENOMMEN = {
    "web/frontend/package-lock.json",
    "docs-site/package-lock.json",
}

AUSGENOMMENE_ENDUNGEN = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico",
                        ".pdf", ".woff", ".woff2", ".ttf", ".zip", ".sqlite"}

ADRESSE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")


def maskieren(adresse: str) -> str:
    """Für die Ausgabe unkenntlich machen.

    CI-Logs eines öffentlichen Repos sind selbst öffentlich — eine Fundstelle
    im Klartext zu melden hieße, das Leck über den Umweg des Logs zu wiederholen.
    Datei und Zeile reichen zum Finden.
    """
    lokal, _, domain = adresse.partition("@")
    kopf = lokal[0] if lokal else "?"
    return f"{kopf}{'*' * max(len(lokal) - 1, 1)}@{domain}"


def dateien(nur_diff: bool) -> list[str]:
    if nur_diff:
        basis = subprocess.run(["git", "merge-base", "HEAD", "origin/main"],
                               capture_output=True, text=True).stdout.strip()
        if basis:
            roh = subprocess.run(["git", "diff", "--name-only", "--diff-filter=d", basis, "HEAD"],
                                 capture_output=True, text=True).stdout
            return [z for z in roh.splitlines() if z]
    roh = subprocess.run(["git", "ls-files"], capture_output=True, text=True).stdout
    return [z for z in roh.splitlines() if z]


def _ausgenommen(pfad: str) -> bool:
    """Trägt der Pfad einen der Ausnahme-Pfade am Ende?

    Der Aufrufer übergibt mal repo-relative Pfade (``git ls-files``), mal
    absolute (Tests). Ein reiner Gleichheitstest träfe dann nur den einen Fall —
    genau daran ist die erste Fassung durchgerutscht.
    """
    p = Path(pfad).as_posix()
    return any(p == a or p.endswith("/" + a) for a in AUSGENOMMEN)


def pruefen(pfade: list[str]) -> list[tuple[str, int, str]]:
    treffer: list[tuple[str, int, str]] = []
    for pfad in pfade:
        if _ausgenommen(pfad) or Path(pfad).suffix.lower() in AUSGENOMMENE_ENDUNGEN:
            continue
        try:
            text = Path(pfad).read_text(encoding="utf-8")
        except (UnicodeDecodeError, FileNotFoundError, IsADirectoryError):
            continue  # binär oder inzwischen weg — beides kein Fall für uns
        for nr, row in enumerate(text.splitlines(), start=1):
            for fund in ADRESSE.findall(row):
                if fund in ERLAUBTE_ADRESSEN:
                    continue
                if fund.rsplit("@", 1)[-1].lower() in ERLAUBTE_DOMAINS:
                    continue
                treffer.append((pfad, nr, fund))
    return treffer


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--diff", action="store_true",
                   help="nur Dateien prüfen, die sich gegenüber origin/main geändert haben")
    p.add_argument("pfade", nargs="*",
                   help="konkrete Dateien prüfen (nutzt der pre-commit-Hook für die "
                        "vorgemerkten Änderungen); ohne Angabe wird das ganze Repo geprüft")
    args = p.parse_args()

    treffer = pruefen(args.pfade or dateien(args.diff))
    if not treffer:
        print("Keine fremden E-Mail-Adressen gefunden.")
        return 0

    print("Fremde E-Mail-Adressen gefunden:\n", file=sys.stderr)
    for pfad, nr, fund in treffer:
        print(f"  {pfad}:{nr}  {maskieren(fund)}", file=sys.stderr)
    print(
        "\nEine echte Adresse gehört nicht ins Repo — auch nicht als Beispiel.\n"
        "Nimm eine Adresse auf example.org (RFC 2606, kann niemandem gehören).\n"
        "Ist die Adresse legitim (eigene Kontakt-/Absenderadresse), trag ihre\n"
        "Domain in ERLAUBTE_DOMAINS in scripts/lint_adressen.py ein.\n"
        "\nWichtig: Wird so etwas erst nach dem Push bemerkt, reicht ein Revert\n"
        "NICHT — die Adresse bleibt über den alten Commit abrufbar. Dann History-\n"
        "Rewrite und Anfrage beim GitHub-Support (siehe CLAUDE.md).",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
