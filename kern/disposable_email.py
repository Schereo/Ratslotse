"""Wegwerf-E-Mail-Domains — der Riegel vor der Registrierung.

Am 12. und 13.09.2026 tauchten auf Prod zwei Konten auf, die nach nichts
aussahen: Anzeigename aus Tastaturgeklapper („Jsjsb", „Hfd"), Adresse bei
einem Wegwerf-Anbieter (94an.com, airhemp.com), Einrichtungs-Assistent in
unter 25 Sekunden durchgeklickt. Beide hatten den Bestätigungslink brav
geklickt — **die E-Mail-Bestätigung hält so etwas nicht ab**, ein
Wegwerf-Postfach empfängt den Link genauso. Was die beiden gemeinsam hatten,
war die Domain, und genau die steht auf einer öffentlich gepflegten Liste.

Die Liste liegt daneben als ``disposable_email_domains.txt`` (Quelle und
Lizenz im Kopf der Datei) und wird mit ``scripts/update_disposable_domains.py``
nachgezogen. Geprüft wird die Domain samt aller Eltern-Domains: Ein
``mail.94an.com`` ist genauso Wegwerf wie ``94an.com``.

``PROTECTED_DOMAINS`` sind Anbieter, die **nie** gesperrt werden — egal, was
ein Nachziehen der Liste hereinschwemmt. Apples Weiterleitungs-Domain steht
dabei, weil „E-Mail verbergen" genau so aussieht wie eine Wegwerf-Adresse,
aber zu einem echten Apple-Konto gehört. Der Riegel gilt nur für Adressen,
die jemand selbst eintippt (Registrierung, Adresswechsel); was Apple beim
Sign-in liefert, ist von Apple bestätigt und bleibt außen vor.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

LIST_PATH = Path(__file__).with_name("disposable_email_domains.txt")
UPSTREAM_URL = (
    "https://raw.githubusercontent.com/disposable-email-domains/"
    "disposable-email-domains/main/disposable_email_blocklist.conf"
)

#: Antworten an den Client — deutsch, weil Web und App den Text unverändert
#: zeigen, und **absichtlich ohne Grund** (Tim, 14.09.2026): Wer hier abgewiesen
#: wird, soll nicht erfahren, welche Prüfung angeschlagen hat — sonst probiert
#: er die nächste Domain. Der Grund steht stattdessen im Server-Log
#: (Logger der beiden Router, nur die Domain, nie die Adresse). Der Rest des
#: Repos ist öffentlich, geheim ist der Mechanismus also nicht — aber das
#: Formular gibt ihn nicht her.
REGISTER_REJECTED = "Die Registrierung konnte nicht abgeschlossen werden."
EMAIL_CHANGE_REJECTED = "Der Adresswechsel konnte nicht abgeschlossen werden."

#: Nie sperren, auch wenn die Liste sie eines Tages führen sollte. Die großen
#: Postfach-Anbieter, die regionalen (EWE), die Uni, die Stadt — und Apples
#: „E-Mail verbergen". ``tests/test_disposable_email.py`` hält zusätzlich fest,
#: dass keine davon in der Liste steht: Dann fällt ein Fehleintrag beim
#: Nachziehen auf, statt still von dieser Menge geschluckt zu werden.
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


@lru_cache(maxsize=1)
def blocked_domains() -> frozenset[str]:
    """Die Liste — einmal gelesen, dann im Prozess gehalten (~9.000 Einträge)."""
    return parse_list(LIST_PATH.read_text(encoding="utf-8"))


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
