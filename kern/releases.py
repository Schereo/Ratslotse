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
class Media:
    """Das Bild oder der Clip zu einem Highlight.

    **Zwei Fassungen, hell und dunkel.** Eine Aufnahme der Oberfläche ist
    immer in der Helligkeit gefangen, in der sie entstand; ein weißes Bild in
    der dunklen Karte blendet. Die Karte tauscht sie über die ``dark:``-Regel,
    ohne JavaScript.

    Die Dateien liegen unter ``web/frontend/public/neuigkeiten/<version>/``
    und wandern damit auch in den statischen Export der App.
    ``tests/test_releases.py`` prüft, dass jede genannte Datei existiert —
    ein Tippfehler im Pfad wäre sonst ein leeres Feld auf der Karte.
    """

    #: ``image`` (WebP) oder ``video`` (MP4, stumm, in Schleife).
    kind: str
    src: str
    src_dark: str
    #: Was zu sehen ist — für Screenreader und für den Fall, dass nichts lädt.
    alt: str
    #: Nur bei ``video``: das Standbild, bis der Clip läuft. Es ist zugleich
    #: das, was bei ``prefers-reduced-motion`` STATT des Clips steht.
    poster: str | None = None
    poster_dark: str | None = None


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
    #: Das Bild oder der Clip. **Entweder alle Highlights einer Ausgabe haben
    #: eins oder keines** (``tests/test_releases.py`` hält das): Die Karte
    #: zeigt sonst eine Bühne mit einem Loch darin. Ohne Medien fällt sie auf
    #: die Listenform zurück, die auch ohne Bilder lesbar ist.
    media: Media | None = None
    #: Dasselbe Feature, aber **aus der App aufgenommen** (Tims Wunsch
    #: 07.09.2026). Wer auf dem iPhone liest, soll das iPhone sehen: Ein
    #: Browserfenster mit Seitenleiste zeigt eine Oberfläche, die es dort gar
    #: nicht gibt, und wer danach sucht, sucht vergeblich.
    #:
    #: Auch hier gilt alles oder nichts, und zwar **je Ausgabe**: Fehlt einem
    #: Highlight die App-Fassung, bekommt die App für ALLE die Web-Bilder
    #: (``media_for``). Ein Wechsel mitten in der Bühne wäre schlimmer als eine
    #: durchgehend fremde Oberfläche.
    media_ios: Media | None = None


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
                media=Media(
                    kind="video",
                    src="/neuigkeiten/2.2.0/teilen.mp4", src_dark="/neuigkeiten/2.2.0/teilen-dunkel.mp4",
                    poster="/neuigkeiten/2.2.0/teilen.webp", poster_dark="/neuigkeiten/2.2.0/teilen-dunkel.webp",
                    alt="Eine aufgeklappte Tagesordnung; an jeder Zeile ein "
                        "Teilen-Knopf. Einer wird angetippt, es erscheint "
                        "„Link kopiert“.",
                ),
            ),
            Highlight(
                title="Deine Sitzungen im Kalender",
                text="Die Termine deiner abonnierten Gremien laufen jetzt in Apple "
                     "Kalender, Google oder Outlook mit — einmal abonniert, danach "
                     "aktualisiert sich alles von selbst.",
                url="/abos",
                media=Media(
                    kind="image",
                    src="/neuigkeiten/2.2.0/kalender.webp", src_dark="/neuigkeiten/2.2.0/kalender-dunkel.webp",
                    alt="Die Karte „Im Kalender abonnieren“ mit den Knöpfen "
                        "„Kalender abonnieren“ und „Link kopieren“.",
                ),
            ),
            Highlight(
                title="Der Rat erklärt seine Fachwörter",
                text="„Was ist eine Ausfallbürgschaft?“ beantwortet die KI-Frage "
                     "jetzt zuverlässig, und im Antworttext liegt unter jedem "
                     "Fachwort eine kurze Erklärung zum Antippen.",
                url="/fragen",
                media=Media(
                    kind="image",
                    src="/neuigkeiten/2.2.0/glossar.webp", src_dark="/neuigkeiten/2.2.0/glossar-dunkel.webp",
                    alt="Im Text ist „Messbetrag“ gepunktet unterstrichen; "
                        "darunter steht die Erklärung des Begriffs.",
                ),
            ),
            Highlight(
                title="Live: welcher Punkt gerade dran ist",
                text="Während einer Ratssitzung zeigt die Übersicht mit, welcher "
                     "Tagesordnungspunkt gerade läuft und wer spricht — aus der "
                     "Übertragung mitgelesen.",
                url="/dashboard",
                media=Media(
                    kind="image",
                    src="/neuigkeiten/2.2.0/live.webp", src_dark="/neuigkeiten/2.2.0/live-dunkel.webp",
                    alt="Die Live-Karte: „Der Stadtrat tagt gerade“, dazu "
                        "der laufende Tagesordnungspunkt und wer spricht.",
                ),
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


#: Wo die Medien im Repo liegen — von hier aus prüft der Wächter, ob eine
#: genannte Datei wirklich existiert, und von hier aus liefert Next.js sie aus.
MEDIA_ROOT = "web/frontend/public"


def has_media(release: Release) -> bool:
    """Trägt diese Ausgabe Bilder? (Alle oder keines, s. ``Highlight.media``.)"""
    return all(h.media is not None for h in release.highlights)


#: Clients, die die App-Fassung der Bilder bekommen sollen. Deckt sich mit
#: ``web.backend.app.clients.NATIVE_CLIENTS`` — hier noch einmal, weil ``kern``
#: nichts aus dem Backend importieren darf (s. tests/test_schichten.py).
NATIVE_CLIENTS = frozenset({"ios", "android", "app"})


def has_native_media(release: Release) -> bool:
    """Ist die App-Fassung dieser Ausgabe vollständig?"""
    return bool(release.highlights) and all(
        h.media_ios is not None for h in release.highlights)


def media_for(highlight: Highlight, client: str = "web") -> Media | None:
    """Welches Bild dieser Client sehen soll.

    Die Entscheidung fällt **serverseitig**, damit die Clients nicht zwei
    Felder auseinanderhalten müssen und eine dritte Plattform später nichts
    außer einem Registry-Feld braucht.
    """
    if client in NATIVE_CLIENTS and highlight.media_ios is not None:
        return highlight.media_ios
    return highlight.media


def as_dict(release: Release, client: str = "web") -> dict:
    """Die Antwortform der API — englische Feldnamen, deutsche Inhalte.

    ``client`` entscheidet, welche Fassung der Bilder mitgeht (``media_for``);
    unvollständige App-Fassungen fallen für die ganze Ausgabe auf Web zurück.
    """
    nativ = client in NATIVE_CLIENTS and has_native_media(release)

    def medium(m: Media | None) -> dict | None:
        if m is None:
            return None
        return {"kind": m.kind, "src": m.src, "src_dark": m.src_dark, "alt": m.alt,
                "poster": m.poster, "poster_dark": m.poster_dark}

    return {
        "version": release.version,
        "date": release.date,
        "title": release.title,
        "highlights": [
            {"title": h.title, "text": h.text, "url": h.url,
             "media": medium(h.media_ios if nativ else h.media)}
            for h in release.highlights
        ],
    }
