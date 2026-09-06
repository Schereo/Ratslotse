#!/usr/bin/env python3
"""Merkt, wenn ein Cron-Job aufhört zu laufen — und wenn die Platte vollläuft.

**Die Lücke.** ``run_guarded`` meldet einen Job, der ABSTÜRZT. Ein Job, der
gar nicht mehr STARTET, stürzt nicht ab: Er fehlt einfach. Sichtbar war das
bisher nur als Ampel im Admin-Panel — wer nicht hinsieht, merkt monatelang
nicht, dass die Protokolle seit Wochen nicht mehr geholt werden. Genau so
lag ``hebesatz_probe`` still (s. ``kern/dbfehler.py``).

Dieser Lauf dreht es um: Einmal am Tag prüft er alle Jobs gegen ihren
erwarteten Takt (``kern/jobs.py``) und meldet, was fehlt.

**Und den Speicherplatz.** Läuft die Platte voll, schlagen SQLite-Schreibvorgänge
fehl — und zwar als ``OperationalError: attempt to write a readonly database``
oder ``disk I/O error``. Das sieht wie ein Anwendungsfehler aus, und man sucht
tagelang am falschen Ende. Eine Zahl im Blick zu haben, kostet nichts.

**Was er NICHT auffängt**, und das gehört dazu: Stirbt der Cron-Dienst als
GANZES, stirbt dieser Lauf mit. Er merkt, dass EIN Job schweigt, nicht dass
alle schweigen. Dafür bräuchte es eine Prüfung von außerhalb der Maschine —
ein Anpinger auf ``/api/health`` etwa. Der ist hier bewusst nicht gebaut: Er
gehört nicht ins Repo, sondern auf einen zweiten Rechner.

**Gemeldet wird höchstens einmal am Tag**, weil der Lauf einmal am Tag
stattfindet — eine eigene Dämpfung braucht es nicht. Meldet er nichts, hat er
nichts gefunden; die Kennzahlen stehen trotzdem im Admin-Panel.

Cron (als Nutzer tim auf dem App-Server):
  30 6 * * * /home/<user>/app/.venv/bin/python /home/<user>/app/scripts/check_herzschlag.py
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL))

from kern.jobs import JOBS, zustand  # noqa: E402

#: Ab hier wird der Platz knapp. 10 % klingt viel, sind auf einer 40-GB-Platte
#: aber 4 GB — und ein Datenbank-Backup samt WAL braucht davon einen guten Teil.
PLATZ_WARNUNG_PROZENT = 10
#: Ab hier ist es dringend: Ein Schreibvorgang kann jederzeit scheitern.
PLATZ_ALARM_PROZENT = 5


def platz(pfad: Path) -> dict:
    """Freier Platz auf der Platte, auf der ``pfad`` liegt."""
    gesamt, _, frei = shutil.disk_usage(pfad)
    return {
        "frei_gb": round(frei / 1024**3, 1),
        "gesamt_gb": round(gesamt / 1024**3, 1),
        "frei_prozent": round(frei / gesamt * 100, 1) if gesamt else 0.0,
    }


def schweigende(store) -> list[tuple[dict, str, float | None]]:
    """Die Jobs, die nicht laufen wie erwartet — mit ihrem Zustand."""
    runs = store.job_runs(limit=500)
    letzte: dict[str, dict] = {}
    for r in runs:                       # neueste zuerst
        letzte.setdefault(r["job"], r)
    aus = []
    for job in JOBS:
        # Der Herzschlag selbst zählt nicht mit: Er läuft ja gerade.
        if job["key"] == "check_herzschlag":
            continue
        st, alter = zustand(job, letzte.get(job["key"]))
        if st in ("stale", "unknown"):
            aus.append((job, st, alter))
    return aus


def main() -> dict:
    from kern.alerts import notify_admin
    from kern.store import Store

    db = Path(__import__("os").environ.get("RATSLOTSE_DB", WURZEL / "data" / "ratslotse.sqlite"))
    store = Store(db)
    try:
        stumm = schweigende(store)
    finally:
        store.close()

    p = platz(db.parent if db.parent.exists() else WURZEL)

    meldungen: list[str] = []
    if stumm:
        zeilen = []
        for job, st, alter in stumm:
            wann = f"zuletzt vor {alter} h" if alter is not None else "noch nie gelaufen"
            zeilen.append(f"• <b>{job['label']}</b> ({job['key']}) — {wann}, "
                          f"erwartet {job['schedule']}")
        meldungen.append("Diese Jobs laufen nicht wie erwartet:\n" + "\n".join(zeilen))
    if p["frei_prozent"] < PLATZ_ALARM_PROZENT:
        meldungen.append(f"<b>Die Platte ist fast voll</b>: noch {p['frei_gb']} GB "
                         f"({p['frei_prozent']} %) von {p['gesamt_gb']} GB. "
                         "Schreibvorgänge können jederzeit scheitern.")
    elif p["frei_prozent"] < PLATZ_WARNUNG_PROZENT:
        meldungen.append(f"Der Platz wird knapp: noch {p['frei_gb']} GB "
                         f"({p['frei_prozent']} %) von {p['gesamt_gb']} GB.")

    if meldungen:
        notify_admin(
            "\n\n".join(meldungen),
            betreff="Ratslotse – ein Job schweigt" if stumm else "Ratslotse – Platz wird knapp",
            fusszeile="Täglicher Herzschlag. Ein Job, der gar nicht startet, "
                      "stürzt auch nicht ab — deshalb diese Prüfung.")

    return {
        "jobs_geprueft": len([j for j in JOBS if j["key"] != "check_herzschlag"]),
        "jobs_stumm": len(stumm),
        "platz_frei_gb": p["frei_gb"],
        "platz_frei_prozent": p["frei_prozent"],
        "gemeldet": len(meldungen),
    }


if __name__ == "__main__":
    from kern.alerts import run_guarded

    run_guarded("check_herzschlag", main)
