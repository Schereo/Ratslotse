#!/usr/bin/env python3
"""Merkt, wenn ein Cron-Job aufhört zu laufen — und wenn die Platte vollläuft.

**Die Lücke.** ``run_guarded`` meldet einen Job, der ABSTÜRZT. Ein Job, der
gar nicht mehr STARTET, stürzt nicht ab: Er fehlt einfach. Sichtbar war das
bisher nur als Ampel im Admin-Panel — wer nicht hinsieht, merkt monatelang
nicht, dass die Protokolle seit Wochen nicht mehr geholt werden. Genau so
lag ``hebesatz_probe`` still (s. ``kern/dbfehler.py``).

Dieser Lauf dreht es um: Einmal am Tag prüft er alle Jobs gegen ihren
erwarteten Takt (``kern/jobs.py``) und meldet, was fehlt.

**Und die Registrierungen.** Dieselbe Lücke eine Etage höher: Die FYI-Mail an
die Admins geht erst raus, wenn jemand seine Adresse BESTÄTIGT hat. Ein Skript,
das tausend Konten anlegt und nie einen Link klickt, löst damit keine einzige
Mail aus. Der Herzschlag zählt deshalb einmal am Tag, wie viele Konten in 24
Stunden dazugekommen sind, wie viele davon unbestätigt blieben und wie oft die
Bremse oder der Wegwerf-Riegel zugeschlagen hat.

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

#: Ab wie vielen neuen Konten in 24 Stunden es gemeldet wird. Gemessen auf Prod
#: (09/2026): etwa **eines pro Tag**, Spitze drei. Zehn liegt weit vom Alltag
#: weg und nah genug dran, dass eine Welle noch am selben Tag auffällt.
#:
#: Warum es das braucht: Die FYI-Mail an die Admins geht erst raus, wenn jemand
#: seine Adresse BESTÄTIGT hat. Ein Skript, das tausend Konten anlegt und nie
#: einen Link klickt, löst damit keine einzige Mail aus — es hinterlässt nur
#: tausend Zeilen, die niemand ansieht.
ANMELDUNGEN_ALARM = 10
#: Dieselbe Zahl für die unbestätigten darunter. Getrennt, weil genau sie den
#: Unterschied macht: 12 neue Konten nach einem Zeitungsartikel sind eine gute
#: Nachricht, 12 unbestätigte in derselben Nacht sind keine.
UNBESTAETIGT_ALARM = 10
#: Abgewiesene Registrierungen (Bremse + Wegwerf-Riegel) über gestern und
#: heute. Höher angesetzt: Hier abzuprallen ist folgenlos, die Zahl darf also
#: erst auffallen, wenn sie nach System aussieht. `duplicate_email` zählt
#: NICHT mit — wer sein Konto vergessen hat, ist kein Angriff.
ABWEISUNGEN_ALARM = 20
#: Welche Gründe als Angriff zählen (s. `kern/store.SIGNUP_REJECTION_REASONS`).
ABWEISUNGSGRUENDE = ("rate_limit", "disposable_email")
#: Nur für die Mail — die Kennzahlen bleiben englisch.
ABWEISUNGS_LABEL = {
    "rate_limit": "Bremse",
    "disposable_email": "Wegwerf-Adresse",
    "duplicate_email": "Adresse schon vergeben",
}


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


def anmeldungen(store) -> dict:
    """Die Registrierungs-Signale des letzten Tages.

    ``created``/``unverified`` über die letzten 24 Stunden (Zeitstempel),
    ``abgewiesen`` über **gestern und heute** — die Abweisungen liegen nur als
    Tagessumme vor, ein 24-Stunden-Fenster gibt es dafür nicht. Die beiden
    Fenster sind also verschieden groß; die Mail sagt das auch so.
    """
    from datetime import timedelta

    from kern.store import today_utc

    frisch = store.signup_recent(24)
    # Der UTC-Tag, weil die Abweisungen so gezählt werden (kern.store.today_utc).
    gruende = store.signup_rejections_since((today_utc() - timedelta(days=1)).isoformat())
    return {
        "created": frisch["created"],
        "unverified": frisch["unverified"],
        "abgewiesen": sum(gruende.get(g, 0) for g in ABWEISUNGSGRUENDE),
        "abgewiesen_je_grund": gruende,
    }


def main() -> dict:
    from kern.alerts import notify_admin
    from kern.store import Store

    db = Path(__import__("os").environ.get("RATSLOTSE_DB", WURZEL / "data" / "ratslotse.sqlite"))
    store = Store(db)
    try:
        stumm = schweigende(store)
        konten = anmeldungen(store)
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

    auffaellig = False
    if konten["created"] >= ANMELDUNGEN_ALARM:
        auffaellig = True
        meldungen.append(
            f"<b>Ungewöhnlich viele neue Konten</b>: {konten['created']} in den letzten "
            f"24 Stunden, davon {konten['unverified']} ohne bestätigte Adresse. "
            f"Normal sind hier ein bis drei am Tag. "
            "Im Admin-Panel unter <i>Statistik → Registrierungen</i> steht der Verlauf.")
    elif konten["unverified"] >= UNBESTAETIGT_ALARM:
        auffaellig = True
        meldungen.append(
            f"<b>Viele unbestätigte Konten</b>: {konten['unverified']} der "
            f"{konten['created']} neuen Konten der letzten 24 Stunden haben ihre "
            "Adresse nicht bestätigt. Genau diese lösen sonst keine Mail aus.")
    if konten["abgewiesen"] >= ABWEISUNGEN_ALARM:
        auffaellig = True
        je_grund = ", ".join(f"{ABWEISUNGS_LABEL.get(g, g)}: {n}"
                             for g, n in sorted(konten["abgewiesen_je_grund"].items())
                             if g in ABWEISUNGSGRUENDE and n)
        meldungen.append(
            f"<b>Viele abgewiesene Registrierungen</b>: {konten['abgewiesen']} gestern "
            f"und heute ({je_grund}). Die Bremse und der Wegwerf-Riegel haben also "
            "gehalten — aber jemand hat es oft versucht.")

    if meldungen:
        if stumm:
            betreff = "Ratslotse – ein Job schweigt"
        elif auffaellig:
            betreff = "Ratslotse – auffällige Registrierungen"
        else:
            betreff = "Ratslotse – Platz wird knapp"
        notify_admin(
            "\n\n".join(meldungen),
            betreff=betreff,
            fusszeile="Täglicher Herzschlag. Ein Job, der gar nicht startet, "
                      "stürzt auch nicht ab — deshalb diese Prüfung.")

    return {
        "jobs_geprueft": len([j for j in JOBS if j["key"] != "check_herzschlag"]),
        "jobs_stumm": len(stumm),
        "platz_frei_gb": p["frei_gb"],
        "platz_frei_prozent": p["frei_prozent"],
        "konten_24h": konten["created"],
        "konten_24h_unbestaetigt": konten["unverified"],
        "registrierungen_abgewiesen": konten["abgewiesen"],
        "gemeldet": len(meldungen),
    }


if __name__ == "__main__":
    from kern.alerts import run_guarded

    run_guarded("check_herzschlag", main)
