"""Was ein Release den Nutzer*innen gebracht hat — kuratiert, als Code.

**Wozu.** Ratslotse liefert laufend aus; wer die Seite alle paar Wochen öffnet,
merkt von einem neuen Feature nichts. Der Changelog steht zwar öffentlich, ist
aber ein Protokoll und keine Ankündigung: Der Abschnitt zu 2.2.0 trägt allein
unter „Hinzugefügt" sechs Einträge mit je über hundert Wörtern.

Hier steht die **kurze** Fassung: je Release drei bis vier Sätze, jeder mit
einem Ziel in der App. Daraus baut die Oberfläche die Karte „Neu bei
Ratslotse", und derselbe Text geht auf Wunsch als Mail und Push raus.

**Nur die großen Sachen** (Tims Regel 07.09.2026). Ein Fix, eine schnellere
Abfrage, ein aufgeräumtes Layout gehören in den Changelog und nicht auf die
Karte. Drei Schranken halten das, statt es zu erbitten — ``tests/test_releases.py``
prüft alle drei:

1. **Nur Minor- und Major-Versionen.** Ein Eintrag für ``2.3.1`` fliegt raus:
   Ein Patch-Release ist definitionsgemäß Reparatur.
2. **Höchstens vier Highlights.** Wer ein fünftes will, streicht ein anderes.
   Ein Release ganz ohne Eintrag ist erlaubt und der Normalfall für kleine.
3. **Jedes Highlight braucht ein Ziel in der App.** Was man sich nirgends
   ansehen kann, ist keine Karte wert — das sortiert Optimierungen von selbst
   aus.

**Warum als Code und nicht in der Datenbank.** Dieselbe Begründung wie bei den
Prompts (``kern/prompts.py``): im Pull Request sichtbar, mit Diff und
Historie, und niemand tippt einen Ankündigungstext aus der Hüfte ins
Admin-Panel. Ein Editor dort wäre außerdem eine zweite Wahrheit neben dem
Changelog.

**Alte Einträge bleiben stehen.** Die Liste ist eine Geschichte, kein
Aushang: Wer ein halbes Jahr nicht da war, soll sehen, was er verpasst hat
(``pending_for``). Wer nach einem Release dazugekommen ist, sieht es nie —
für ihn ist alles neu.

**Beim Versionsschnitt** schlägt ``scripts/changelog_schnitt.py --highlights``
einen Entwurf aus den Fragmenten vor; die Auswahl trifft ein Mensch.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

#: Eine Version, wie sie im Changelog steht: genau drei Zahlen.
VERSION = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")

#: So viele Releases zeigt die Karte höchstens auf einmal. Alles Ältere wird
#: gezählt und verweist auf den Changelog — sonst wächst die Karte mit der
#: Abwesenheit, und ausgerechnet wer lange weg war, bekäme die längste Wand.
CARD_LIMIT = 3

#: Mehr als vier Zeilen liest niemand auf einer Karte. Die Zahl ist zugleich
#: die Bremse gegen „nehmen wir alles mit".
MAX_HIGHLIGHTS = 4


@dataclass(frozen=True)
class Highlight:
    """Ein Feature in einem Satz, mit einem Ort, an dem man es sieht."""

    #: Kurz und konkret, ohne Punkt am Ende („Sitzungen teilen").
    title: str
    #: Ein bis zwei Sätze: Was kann man jetzt, was vorher nicht ging.
    text: str
    #: Wohin es führt. **App-Pfad** (mit ``/`` beginnend), denn derselbe Link
    #: steht in der nativen App — eine externe Adresse ließe den Tipp dort
    #: wortlos ins Leere laufen (dieselbe Regel wie ``kern/notify.py``).
    url: str


@dataclass(frozen=True)
class Release:
    """Ein Release, wie die Karte es zeigt."""

    #: ``x.y.0`` — dieselbe Zahl wie im Changelog und im Git-Tag.
    version: str
    #: Erscheinungsdatum, ISO. Es entscheidet, wer die Karte sieht: Ein Konto,
    #: das jünger ist, hat das Feature von Anfang an gehabt.
    date: str
    #: Die Überschrift der Karte — ein Halbsatz, der die Ausgabe zusammenfasst.
    title: str
    highlights: tuple[Highlight, ...]


#: Alle Releases mit Karte, **neueste zuerst**.
#:
#: Wer hier einträgt, tut es im Release-PR (``dev`` → ``main``), zusammen mit
#: dem Versionsschnitt: Changelog, App-Version und diese Liste gehören in
#: denselben Commit.
RELEASES: tuple[Release, ...] = (
    Release(
        version="2.2.0",
        date="2026-09-06",
        title="Teilen, Kalender-Abo und ein Rat, der Fachwörter erklärt",
        highlights=(
            Highlight(
                title="Sitzungen teilen — auch einzelne Punkte",
                text="An jeder Sitzung und an jeder Zeile der Tagesordnung steht "
                     "jetzt ein Teilen-Knopf. Wer den Link bekommt, liest die "
                     "Sitzung ohne Konto und landet direkt bei dem gemeinten Punkt.",
                url="/council?tab=sessions",
            ),
            Highlight(
                title="Deine Sitzungen im Kalender",
                text="Die Termine deiner abonnierten Gremien laufen jetzt in Apple "
                     "Kalender, Google oder Outlook mit — einmal abonniert, danach "
                     "aktualisiert sich alles von selbst.",
                url="/abos",
            ),
            Highlight(
                title="Der Rat erklärt seine Fachwörter",
                text="„Was ist eine Ausfallbürgschaft?“ beantwortet die KI-Frage "
                     "jetzt zuverlässig, und im Antworttext liegt unter jedem "
                     "Fachwort eine kurze Erklärung zum Antippen.",
                url="/fragen",
            ),
            Highlight(
                title="Live: welcher Punkt gerade dran ist",
                text="Während einer Ratssitzung zeigt die Übersicht mit, welcher "
                     "Tagesordnungspunkt gerade läuft und wer spricht — aus der "
                     "Übertragung mitgelesen.",
                url="/dashboard",
            ),
        ),
    ),
)


def version_key(version: str) -> tuple[int, int, int]:
    """``"2.10.0"`` → ``(2, 10, 0)``, damit Versionen der Reihe nach vergleichbar
    sind.

    Als Zeichenkette verglichen stünde ``"2.10.0"`` vor ``"2.9.0"`` — genau der
    Vergleich, den die Hochwassermarke eines Kontos braucht. Deshalb wird
    **nirgends** in SQL nach Versionen sortiert, sondern immer hierüber.
    """
    m = VERSION.match(version.strip())
    if not m:
        raise ValueError(f"Keine Version im Format x.y.z: {version!r}")
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


def is_feature_release(version: str) -> bool:
    """Darf diese Version eine Karte haben? Nur ``x.y.0``."""
    try:
        return version_key(version)[2] == 0
    except ValueError:
        return False


def latest() -> Release | None:
    """Das jüngste Release mit Karte."""
    return RELEASES[0] if RELEASES else None


def get(version: str) -> Release | None:
    for release in RELEASES:
        if release.version == version:
            return release
    return None


def pending_for(seen_version: str | None,
                account_created: str | None) -> tuple[list[Release], int]:
    """Was dieses Konto noch nicht gesehen hat: ``(zu zeigen, weitere)``.

    Zwei Bedingungen, und beide sind nötig:

    * **jünger als die Hochwassermarke** — ``seen_version`` ist die höchste
      weggeklickte Version, nicht die zuletzt gesehene. Wer zwei Releases
      verpasst hat, bekommt beide; wer eine Karte wegklickt, bekommt keine
      davon je wieder.
    * **älter als das Konto nicht** — wer sich nach dem Release angemeldet hat,
      hatte das Feature von der ersten Minute an. Für ihn ist es keine
      Neuigkeit, sondern die App.

    Zurück kommen höchstens ``CARD_LIMIT`` Releases (neueste zuerst) und die
    Zahl der übrigen. Die Karte zeigt das erste voll und die anderen als
    Zeilen; was darüber hinausgeht, steht im Changelog.
    """
    marke = version_key(seen_version) if seen_version else None
    # Nur das Datum vergleichen: ``created_at`` trägt eine Uhrzeit, ``date``
    # nicht. Wer am Release-Tag dazugekommen ist, zählt als „war schon da" —
    # der mildere Irrtum, denn eine Karte zu viel ist ein Wisch, eine
    # verpasste Ankündigung ist weg.
    erstellt = (account_created or "")[:10]

    offen = [
        r for r in RELEASES
        if (marke is None or version_key(r.version) > marke)
        and (not erstellt or erstellt <= r.date)
    ]
    offen.sort(key=lambda r: version_key(r.version), reverse=True)
    return offen[:CARD_LIMIT], max(0, len(offen) - CARD_LIMIT)


def as_dict(release: Release) -> dict:
    """Die Antwortform der API — englische Feldnamen, deutsche Inhalte."""
    return {
        "version": release.version,
        "date": release.date,
        "title": release.title,
        "highlights": [
            {"title": h.title, "text": h.text, "url": h.url} for h in release.highlights
        ],
    }
