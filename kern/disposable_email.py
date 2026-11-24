"""Wegwerf-E-Mail-Domains — erkannt, still behandelt, im Admin-Panel markiert.

Am 12. und 13.09.2026 tauchten auf Prod zwei Konten auf, die nach nichts
aussahen: Anzeigename aus Tastaturgeklapper („Jsjsb", „Hfd"), Adresse bei
einem Wegwerf-Anbieter (94an.com, airhemp.com), Einrichtungs-Assistent in
unter 25 Sekunden durchgeklickt. Beide hatten den Bestätigungslink brav
geklickt — **die E-Mail-Bestätigung hält so etwas nicht ab**, ein
Wegwerf-Postfach empfängt den Link genauso. Was die beiden gemeinsam hatten,
war die Domain, und genau die steht auf einer öffentlich gepflegten Liste.

**Still statt abweisen** (Tim, 24.11.2026). Bis dahin antworteten
Registrierung und Adresswechsel mit 400 — ohne Grund, aber eine Abweisung
ist selbst ein Signal: Wer sie sieht, probiert die nächste Domain. Seitdem
läuft alles wie gewohnt, nur geht **keine Mail an eine Wegwerf-Adresse**
(``kern.email.send_email`` lässt sie fallen). Das Konto bleibt damit
unbestätigt, und wer es angelegt hat, glaubt, die Mail sei nicht angekommen.
Das Admin-Panel zeigt das Konto als „Wegwerf-Adresse" — auf dev, wo jedes
Konto freigeschaltet werden muss, ist das die Stelle, an der es auffällt.

Warum der Versand und nicht nur die Registrierung: „Passwort vergessen"
bestätigt die Adresse mit (wer den Link bekommt, hat das Postfach). Ein still
angelegtes Konto käme darüber doch noch herein.

**Die Liste.** Sie liegt daneben als ``disposable_email_domains.txt`` (Quelle
und Lizenz im Kopf der Datei). Bis 11/2026 wurde sie nur von Hand nachgezogen
— und stand zwei Monate still: Das Konto vom 23.11.2026 kam über kranove.com
herein, das upstream längst geführt wurde. Seitdem zieht der tägliche
Herzschlag (``scripts/check_herzschlag.py``) sie wöchentlich selbst nach, in
eine Kopie unter ``data/`` (die der Deploy nicht überschreibt). Gelesen wird
die NEUERE der beiden Fassungen nach ihrem ``# Stand:``-Kopf — so wirkt auch
eine Domain, die upstream wieder herausgenommen wurde, und ein Commit mit
frischer Liste gewinnt gegen eine ältere Kopie. Geprüft wird die Domain samt
aller Eltern-Domains: Ein ``mail.94an.com`` ist genauso Wegwerf wie
``94an.com``.

``PROTECTED_DOMAINS`` sind Anbieter, die **nie** als Wegwerf gelten — egal,
was ein Nachziehen der Liste hereinschwemmt. Apples Weiterleitungs-Domain
steht dabei, weil „E-Mail verbergen" genau so aussieht wie eine
Wegwerf-Adresse, aber zu einem echten Apple-Konto gehört.
"""
from __future__ import annotations

import os
import re
import urllib.request
from collections.abc import Callable
from datetime import date
from pathlib import Path

LIST_PATH = Path(__file__).with_name("disposable_email_domains.txt")
UPSTREAM_URL = (
    "https://raw.githubusercontent.com/disposable-email-domains/"
    "disposable-email-domains/main/disposable_email_blocklist.conf"
)
#: Dateiname der nachgezogenen Kopie — neben der Konten-Datenbank in ``data/``.
KOPIE_NAME = "disposable_email_domains.txt"

#: Nie als Wegwerf werten, auch wenn die Liste sie eines Tages führen sollte.
#: Die großen Postfach-Anbieter, die regionalen (EWE), die Uni, die Stadt — und
#: Apples „E-Mail verbergen". ``tests/test_disposable_email.py`` hält
#: zusätzlich fest, dass keine davon in der Liste steht, und ``pruefe`` lässt
#: ein Nachziehen, das eine davon mitbringt, gar nicht erst durch.
PROTECTED_DOMAINS: frozenset[str] = frozenset({
    "gmail.com", "googlemail.com",
    "hotmail.com", "hotmail.de", "outlook.com", "outlook.de", "live.com", "live.de",
    "web.de", "gmx.de", "gmx.net", "t-online.de", "freenet.de", "arcor.de",
    "posteo.de", "mailbox.org", "protonmail.com", "proton.me", "tutanota.com", "tuta.io",
    "icloud.com", "me.com", "yahoo.com", "yahoo.de",
    "ewe.net", "ewetel.net",
    "oldenburg.de", "uni-oldenburg.de", "uol.de",
    "privaterelay.appleid.com",
})

_DOMAIN = re.compile(r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)+$")
_STAND = re.compile(r"^#\s*Stand:\s*(\d{4}-\d{2}-\d{2})\s*$", re.M)
#: Mehr Schwund lässt ``pruefe`` nicht durch: Ein Upstream, der gerade umbaut,
#: soll nicht tausende Anbieter bei uns freischalten.
MAX_SCHWUND = 0.10


def domain_of(email: str) -> str:
    """Der Domain-Teil einer Adresse, kleingeschrieben — ``""`` ohne ``@``."""
    _, at, domain = email.strip().lower().rpartition("@")
    return domain if at else ""


def parse_list(text: str) -> frozenset[str]:
    """Eine Domain je Zeile; Leerzeilen und ``#``-Kommentare werden überlesen."""
    return frozenset(
        line.strip().lower()
        for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )


def render(domains: frozenset[str], stand: date) -> str:
    """Die Datei samt Kopf — dieselbe Form im Repo und in der Kopie."""
    kopf = (
        "# Wegwerf-E-Mail-Domains — gelesen von kern/disposable_email.py.\n"
        "# Quelle: https://github.com/disposable-email-domains/disposable-email-domains\n"
        "#         (disposable_email_blocklist.conf), Lizenz CC0 1.0 (Public Domain).\n"
        "# Nachziehen: .venv/bin/python scripts/update_disposable_domains.py --schreiben\n"
        f"# Stand: {stand.isoformat()}\n"
        "# Eine Domain je Zeile, kleingeschrieben; Zeilen mit # werden überlesen.\n"
    )
    return kopf + "\n".join(sorted(domains)) + "\n"


def pruefe(neu: frozenset[str], alt: frozenset[str]) -> list[str]:
    """Gründe, eine nachgezogene Liste NICHT zu übernehmen — leer heißt: in Ordnung.

    * Zeilen, die keine Domain sind — eine Liste, die plötzlich anders
      aussieht, ist eher ein geänderter Upstream als ein neuer Anbieter;
    * Schwund über ``MAX_SCHWUND``;
    * ein Eintrag aus ``PROTECTED_DOMAINS`` — wirkungslos (die Menge gewinnt),
      aber ein Zeichen, dass die Liste jemanden Echtes erwischt hat.
    """
    gruende: list[str] = []
    kaputt = sorted(d for d in neu if not _DOMAIN.match(d))
    if kaputt:
        gruende.append(f"{len(kaputt)} Zeilen sind keine Domain, z. B. {kaputt[:3]}")
    if alt and len(neu) < len(alt) * (1 - MAX_SCHWUND):
        gruende.append(f"Liste geschrumpft: {len(alt)} → {len(neu)} Einträge")
    geschuetzt = sorted(neu & PROTECTED_DOMAINS)
    if geschuetzt:
        gruende.append(f"geschützte Anbieter in der Liste: {geschuetzt}")
    return gruende


def kopie_pfad() -> Path:
    """Wo die nachgezogene Kopie liegt: neben der Konten-Datenbank.

    ``RATSLOTSE_DB`` setzen Server, Tests und ``scripts/dev.py`` gleichermaßen
    — die Kopie folgt der Datenbank also in jede Umgebung, auch in die
    Wegwerf-Verzeichnisse der Tests.
    """
    db = os.environ.get("RATSLOTSE_DB") or str(Path(__file__).resolve().parents[1] / "data" / "ratslotse.sqlite")
    return Path(db).parent / KOPIE_NAME


def stand_von(text: str) -> date | None:
    """Das Datum aus dem ``# Stand:``-Kopf — ``None`` ohne lesbaren Kopf."""
    treffer = _STAND.search(text[:2000])
    if not treffer:
        return None
    try:
        return date.fromisoformat(treffer.group(1))
    except ValueError:
        return None


def _quelle() -> Path:
    """Die neuere der beiden Fassungen. Bei gleichem Stand gewinnt das Repo:
    Ein Commit ist durchgesehen, die Kopie nur geprüft."""
    kopie = kopie_pfad()
    try:
        stand_kopie = stand_von(kopie.read_text(encoding="utf-8"))
    except OSError:
        return LIST_PATH
    stand_repo = stand_von(LIST_PATH.read_text(encoding="utf-8"))
    if stand_kopie and (stand_repo is None or stand_kopie > stand_repo):
        return kopie
    return LIST_PATH


_cache: tuple[tuple[str, float], frozenset[str]] | None = None


def blocked_domains() -> frozenset[str]:
    """Die geltende Liste (~10.000 Einträge) — gelesen, wenn sich die Quelle
    oder ihre Datei geändert hat, sonst aus dem Prozess. Ein Web-Dienst, der
    seit Wochen läuft, sieht so die Kopie, die der Herzschlag heute früh
    geschrieben hat, ohne Neustart."""
    global _cache
    quelle = _quelle()
    schluessel = (str(quelle), quelle.stat().st_mtime)
    if _cache is None or _cache[0] != schluessel:
        _cache = (schluessel, parse_list(quelle.read_text(encoding="utf-8")))
    return _cache[1]


def stand() -> date | None:
    """Stand der geltenden Liste — für den Herzschlag."""
    return stand_von(_quelle().read_text(encoding="utf-8"))


def _candidates(domain: str) -> list[str]:
    """``a.b.c`` → ``["a.b.c", "b.c"]`` — die Domain und jede Eltern-Domain,
    die noch aus zwei Teilen besteht (die TLD allein steht auf keiner Liste)."""
    labels = domain.split(".")
    return [".".join(labels[i:]) for i in range(len(labels) - 1)]


def is_disposable(email: str) -> bool:
    """Gehört die Adresse zu einem Wegwerf-Anbieter?

    Ohne ``@`` oder mit einer geschützten Domain immer ``False`` — die
    Formprüfung der Adresse ist Sache von ``EmailStr``, nicht dieser Funktion.
    """
    domain = domain_of(email)
    if not domain:
        return False
    candidates = _candidates(domain)
    if any(c in PROTECTED_DOMAINS for c in candidates):
        return False
    blocked = blocked_domains()
    return any(c in blocked for c in candidates)


def abrufen(url: str = UPSTREAM_URL) -> str:
    with urllib.request.urlopen(url, timeout=30) as antwort:  # noqa: S310 — feste https-URL
        return antwort.read().decode("utf-8")


def nachziehen(heute: date, abruf: Callable[[], str] | None = None) -> dict:
    """Upstream holen, prüfen und als Kopie nach ``data/`` schreiben.

    Gibt die Kennzahlen zurück (``eintraege``, ``dazu``, ``weg``) oder —
    wenn ``pruefe`` etwas hat — ``gruende`` und schreibt nichts. Ein
    gescheiterter Abruf wirft (``OSError``/``URLError``); der Aufrufer
    entscheidet, ob das eine Meldung wert ist.
    """
    # Erst beim Aufruf auflösen, nicht als Vorgabewert: Der würde beim Import
    # festgelegt, und ein Test, der ``abrufen`` ersetzt, fragte doch ins Netz.
    neu = parse_list((abruf or abrufen)())
    alt = blocked_domains()
    gruende = pruefe(neu, alt)
    if gruende:
        return {"gruende": gruende}
    ziel = kopie_pfad()
    ziel.parent.mkdir(parents=True, exist_ok=True)
    vorlaeufig = ziel.with_suffix(".tmp")
    vorlaeufig.write_text(render(neu, heute), encoding="utf-8")
    vorlaeufig.replace(ziel)   # atomar: Ein Web-Dienst liest nie eine halbe Datei
    return {"eintraege": len(neu), "dazu": len(neu - alt), "weg": len(alt - neu)}
