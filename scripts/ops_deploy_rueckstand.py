"""Entscheidet, ob ein ausgefallener Prod-Deploy nachgeholt werden muss.

**Wozu.** Der Deploy-Alarm ist seit dem 20.09.2026 abgestuft: Bricht ein Lauf
VOR dem Cutover ab, bleibt es still (``scripts/alarm.py::betroffen``). Das ist
richtig — Prod ist in dem Fall nachweislich unverändert —, aber es macht ein
zweites Loch auf: Wenn niemand mehr eine Mail bekommt, merkt auch niemand, dass
seit Stunden nichts mehr deployt wird.

Genau das ist an jenem Tag passiert, damals noch MIT Mails. Sechs PRs wurden
gemergt, sechs Deploys brachen ab, und Prod lief 33 Stunden lang auf dem Stand
vom Vortag — mit sechs Mails im Postfach, die alle gleich aussahen und deshalb
alle wie die fünf harmlosen gelesen wurden. Der Stau selbst stand in keiner
einzigen.

Der Grund war fast immer derselbe: ``check_cities.py`` läuft sonntags ab 5 Uhr
und braucht bei einem Versionssprung des ``fit``-Annotators einen ganzen Tag.
Solange er läuft, blockiert die Vorflug-Prüfung jeden Deploy — folgenlos, aber
eben auch endlos, denn ein abgebrochener Lauf startet sich nicht von selbst neu.

**Was dieses Skript entscheidet.** Es bekommt vier Tatsachen und nennt eine von
vier Aktionen:

``aktuell``
    Der jüngste Commit auf ``main`` ist älter als der letzte geglückte Deploy.
    Nichts zu tun.
``nachholen``
    ``main`` ist voraus und auf dem Server läuft kein Cron — der Deploy kann
    sofort angestoßen werden.
``warten``
    ``main`` ist voraus, aber ein Lauf blockiert noch. Der nächste Takt fragt
    wieder. Kein Alarm: Das ist der Normalfall an einem Sonntagvormittag.
``melden``
    Der Rückstand hält zu lange an, oder die Nachhol-Versuche scheitern
    wiederholt. Dann ist es kein Warten mehr, sondern ein Stau — und der
    gehört gemeldet.

**Warum Zeitstempel und nicht Commit-Hashes.** Das ``deploy.yml`` hängt an
``pull_request: closed``; ``github.sha`` ist dort der Merge-Commit des
Pull Requests, NICHT der Squash-Commit, der auf ``main`` landet. Ein Vergleich
der beiden Hashes wäre also immer ungleich und meldete Dauer-Rückstand. Die
Zeitachse ist hier die ehrlichere Größe: Ist auf ``main`` etwas committet
worden, das der letzte geglückte Deploy noch nicht gesehen haben KANN?

**Zwei Eigenschaften sind Absicht:**

* **Die Nachhol-Versuche haben eine Obergrenze** (``max_versuche``). Ohne sie
  stieße ein Deploy, der aus einem ganz anderen Grund scheitert, sich alle
  dreißig Minuten selbst neu an — und die abgestufte Stille verschluckte einen
  echten Defekt bis in alle Ewigkeit.
* **Unklarheit meldet.** Ein unlesbarer Zeitstempel oder ein Server, der auf
  die Cron-Frage nicht antwortet, führt nicht zu ``nachholen`` (das könnte in
  einen laufenden Job hineindeployen) und nicht zu ``aktuell`` (das wäre
  Stille), sondern zu ``warten`` bzw. ``melden``.
"""
from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

#: Ab wann ein Rückstand kein Warten mehr ist. Ein Sonntagslauf von
#: ``check_cities.py`` dauerte am 20.09.2026 vierzehn Stunden; sechs Stunden
#: sind lang genug, um den Normalfall nicht zu melden, und kurz genug, dass
#: ein echter Stau noch am selben Tag auffällt.
MELDE_AB_STUNDEN = 6.0

#: Wie oft nachgeholt wird, bevor gemeldet statt gestartet wird.
MAX_VERSUCHE = 3

AKTUELL, NACHHOLEN, WARTEN, MELDEN = "aktuell", "nachholen", "warten", "melden"


@dataclass(frozen=True)
class Befund:
    aktion: str
    grund: str


def _zeit(wert: str | None) -> datetime | None:
    """Einen ISO-Zeitstempel von der GitHub-API lesen, ``None`` bei Unfug."""
    if not wert or not wert.strip():
        return None
    text = wert.strip().replace("Z", "+00:00")
    try:
        gelesen = datetime.fromisoformat(text)
    except ValueError:
        return None
    return gelesen if gelesen.tzinfo else gelesen.replace(tzinfo=timezone.utc)


def bewerten(main_commit: str, letzter_erfolg: str | None, jetzt: str,
             crons_frei: bool | None, fehlversuche: int = 0,
             melde_ab_stunden: float = MELDE_AB_STUNDEN,
             max_versuche: int = MAX_VERSUCHE) -> Befund:
    """Die Entscheidung — als reine Funktion, damit sie einen Test hat.

    ``crons_frei`` ist ``None``, wenn der Server die Frage nicht beantwortet
    hat. Das ist ausdrücklich NICHT „frei": In einen laufenden Job hinein zu
    deployen ist der Zustand, den die Vorflug-Prüfung verhindern soll.
    """
    commit = _zeit(main_commit)
    now = _zeit(jetzt)
    if commit is None or now is None:
        return Befund(MELDEN, "Der Zeitstempel kam unlesbar zurück; im Zweifel "
                              "wird gemeldet.")

    erfolg = _zeit(letzter_erfolg)
    if erfolg is not None and erfolg >= commit:
        return Befund(AKTUELL, "Der letzte geglückte Deploy ist jünger als der "
                               "jüngste Commit auf main.")

    stunden = max(0.0, (now - commit).total_seconds() / 3600)
    alter = (f"seit {stunden:.1f} h" if stunden >= 1
             else f"seit {int(stunden * 60)} min")
    woher = ("noch nie erfolgreich deployt" if erfolg is None
             else f"main ist dem letzten geglückten Deploy voraus, {alter}")

    if fehlversuche >= max_versuche:
        return Befund(MELDEN, f"{woher} — und {fehlversuche} Deploy-Versuche in "
                              "Folge sind gescheitert. Das holt sich nicht von "
                              "selbst ein.")
    if crons_frei is None:
        return Befund(MELDEN if stunden >= melde_ab_stunden else WARTEN,
                      f"{woher}, aber der Server beantwortet die Cron-Frage "
                      "nicht. Es wird nicht blind nachgeholt.")
    if not crons_frei:
        if stunden >= melde_ab_stunden:
            return Befund(MELDEN, f"{woher}, und ein Cron-/Ops-Lauf blockiert "
                                  "ihn länger als erwartet.")
        return Befund(WARTEN, f"{woher}, ein Cron-/Ops-Lauf blockiert gerade. "
                              "Der nächste Takt fragt wieder.")
    return Befund(NACHHOLEN, f"{woher}, und kein Cron läuft — der Deploy wird "
                             "nachgeholt.")


def _crons_frei(wert: str) -> bool | None:
    """Der Rückgabewert von ``verify_release_runtime.py --nur-crons``.

    ``0`` = frei, ``3`` = belegt, alles andere (auch ein abgebrochenes SSH)
    = unbekannt.
    """
    return {"0": True, "3": False}.get(wert.strip())


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--main-commit", required=True,
                   help="Zeitstempel des jüngsten Commits auf main (ISO)")
    p.add_argument("--letzter-erfolg", default="",
                   help="Start des letzten geglückten Deploy-Laufs (ISO); leer = "
                        "noch nie")
    p.add_argument("--jetzt", default="",
                   help="Jetzt (ISO); leer = die Uhr dieses Rechners")
    p.add_argument("--crons", default="",
                   help="Rückgabewert von --nur-crons: 0 frei, 3 belegt, sonst "
                        "unbekannt")
    p.add_argument("--fehlversuche", type=int, default=0,
                   help="gescheiterte Deploy-Läufe seit dem letzten geglückten")
    p.add_argument("--melde-ab-stunden", type=float, default=MELDE_AB_STUNDEN)
    p.add_argument("--max-versuche", type=int, default=MAX_VERSUCHE)
    a = p.parse_args(argv)

    jetzt = a.jetzt or datetime.now(timezone.utc).isoformat()
    befund = bewerten(a.main_commit, a.letzter_erfolg or None, jetzt,
                      _crons_frei(a.crons), a.fehlversuche,
                      a.melde_ab_stunden, a.max_versuche)
    print(f"{befund.aktion.upper()}: {befund.grund}")

    # Die Begründung geht über SSH durch eine einfach gequotete Shell-Zeile in
    # die Alarm-Mail. Ein Anführungszeichen darin zerlegte den Befehl,
    # Zeilenumbrüche das Ausgabeformat von GitHub Actions. Dieselbe Regel wie
    # in `ops_deploy_window.py`.
    grund = " ".join(befund.grund.replace("'", "").split())
    ziel = os.environ.get("GITHUB_OUTPUT")
    if ziel:
        with Path(ziel).open("a", encoding="utf-8") as fh:
            fh.write(f"aktion={befund.aktion}\n")
            fh.write(f"grund={grund}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
