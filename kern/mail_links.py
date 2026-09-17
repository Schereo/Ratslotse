"""Links in E-Mails markieren — damit sichtbar wird, ob jemand sie benutzt.

**Die Frage dahinter.** Ratslotse verschickt Tagesordnungen, Themen-Treffer
und Ergebnisse. Ob daraufhin jemand die Seite öffnet — oder ob die Leute
ohnehin von sich aus vorbeikommen und die Mail nur im Postfach liegt —, war
bis 09/2026 nicht zu beantworten. Der Plan vom 08.09. hatte dafür bereits die
richtige Diagnose: ``?zeig=`` markiert eben KEINE Mail-Links, es steht an
genau zwei Stellen; alle übrigen Knöpfe in den Mails sehen aus wie
App-Links.

**Wie es hier gelöst ist.** Jeder Link auf die eigene Domäne bekommt beim
Rendern der Mail einen Parameter angehängt: ``?von=n2_thema``. Das Frontend
meldet diesen Wert beim Seitenaufruf, und ``mail_returns`` zählt ihn je Tag
und Anlass.

**Warum nicht die Klick-Zählung von Resend.** Die baut jeden Link auf eine
Umleitung um, die je Empfänger*in eindeutig ist — damit wäre für jede Mail
nachvollziehbar, wer wann worauf geklickt hat, und die Adresse ginge samt
Klickzeitpunkt durch ein fremdes System. Dieselbe Begründung wie bei
``kern/seitenaufrufe.py`` und ``kern/fehler.py``: lieber die gröbere eigene
Zahl als die genauere fremde.

**Was der Parameter verrät.** Nichts über eine Person: Er ist für alle
Empfänger*innen derselben Mailsorte identisch und steht sichtbar in der
Adresszeile. Wer ihn löscht, wird nicht gezählt — mehr ist dagegen nicht
nötig.

**Nur eigene Links.** Ein Ratsinfo-Link zum Originaldokument bleibt
unangetastet; eine fremde Seite bekommt weder unseren Parameter noch das
Wissen, dass sie aus einer Mail heraus geöffnet wurde.
"""
from __future__ import annotations

import re

#: Der Parametername. Kurz, deutsch, und (anders als ``q``) an keiner Stelle
#: schon mit einer anderen Bedeutung belegt.
PARAM = "von"

#: ``href="…"`` oder ``href='…'`` — nur der Inhalt interessiert.
_HREF = re.compile(r"""href=(["'])(.*?)\1""", re.IGNORECASE | re.DOTALL)


def markiere_link(url: str, anlass: str, basis: str) -> str:
    """Einen einzelnen Link markieren, sofern er auf die eigene Domäne zeigt.

    Unangetastet bleiben: fremde Adressen, ``mailto:``, Anker und alles, was
    den Parameter schon trägt (ein Link, der zweimal durch die Hülle läuft,
    soll nicht ``?von=x&von=x`` werden).
    """
    ziel = (url or "").strip()
    if not ziel or not basis:
        return url
    if not ziel.startswith(basis):
        return url
    if re.search(rf"[?&]{PARAM}=", ziel):
        return url
    rest, _, fragment = ziel.partition("#")
    trenner = "&" if "?" in rest else "?"
    marke = f"{trenner}{PARAM}={anlass}"
    return f"{rest}{marke}" + (f"#{fragment}" if fragment else "")


def markiere(html: str, anlass: str | None, basis: str) -> str:
    """Alle eigenen Links in einer fertigen Mail markieren.

    Läuft über das gerenderte HTML statt über jede Stelle, an der ein Link
    entsteht: Ein neuer Meldeanlass bringt die Markierung damit automatisch
    mit, statt sie vergessen zu können.
    """
    if not anlass or not html:
        return html
    return _HREF.sub(
        lambda m: f'href={m.group(1)}{markiere_link(m.group(2), anlass, basis)}{m.group(1)}',
        html,
    )
