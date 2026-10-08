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

1. **Nur Major-Versionen.** Ein Eintrag für ``2.3.1`` fliegt raus — ein
   Patch-Release ist definitionsgemäß Reparatur — und seit 09/2026 auch einer
   für ``2.7.0``: Die Karte galt bis dahin für jede Minor, und **gehalten hat
   sich das nicht**. 2.3.0 bis 2.7.0 gingen alle ohne Karte raus, weil die
   Kuratierung Handarbeit ist und die Clips eine eigene Runde brauchen; die
   Regel stand also fünf Releases lang als Vorwurf im Raum, statt etwas zu
   bewirken. Tims Entscheidung 21.09.2026: lieber vier Karten im Jahr, die
   jemand gemacht hat.
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

#: Werte von ``Highlight.only`` — für welche Oberfläche ein Highlight gilt.
NUR_WEB = "web"
NUR_NATIVE = "native"

#: Werte von ``Highlight.color`` — die Farbe einer Video-Kachel auf der Karte.
#:
#: **Namen, keine Farbwerte.** Die Werte selbst stehen in der Designsprache
#: (``web/frontend/DESIGNSPRACHE.md``, „Neuigkeiten-Kacheln") und je einmal in
#: Web und App; hier steht nur, welche der drei eine Kachel trägt. Ein
#: Hex-Wert in der Registry wäre eine Farbe, die keine Designsprache kennt —
#: und im Dunkelmodus niemand nachzieht.
#:
#: * ``signal`` — Signal-Orange, die KI-Farbe (Funken, Marker). Für das, was
#:   Lotti tut.
#: * ``primary`` — Hafenblau, der Rat selbst: Beschlüsse, Vorgänge, Räte.
#: * ``green`` — das Grün der Bebauungspläne auf der Stadtkarte (#15803d,
#:   zugleich „Angenommen"). Für das, was auf der Karte liegt.
TILE_COLORS: frozenset[str] = frozenset({"signal", "primary", "green"})


@dataclass(frozen=True)
class Media:
    """Das Bild oder der Clip zu einem Highlight.

    **Immer in der hellen Fassung aufgenommen** (Tims Entscheidung
    07.09.2026). Vorher gab es jede Aufnahme zweimal, hell und dunkel, und die
    Karte tauschte sie über die ``dark:``-Regel. Das war doppelte Arbeit bei
    jeder Ausgabe und doppelte Ablage für einen Unterschied, den ein Bild in
    einem gerahmten Kasten ohnehin verträgt: Es liest sich als Abbildung, nicht
    als Loch in der Oberfläche.

    Die Dateien liegen unter ``web/frontend/public/neuigkeiten/<version>/``
    und wandern damit auch in den statischen Export der App.
    ``tests/test_releases.py`` prüft, dass jede genannte Datei existiert —
    ein Tippfehler im Pfad wäre sonst ein leeres Feld auf der Karte.
    """

    #: ``image`` (WebP) oder ``video`` (MP4, stumm, in Schleife).
    kind: str
    src: str
    #: Was zu sehen ist — für Screenreader und für den Fall, dass nichts lädt.
    alt: str
    #: Das Seitenverhältnis als CSS-Wert (``"16/9"``, ``"9/16"``). Die Bühne
    #: baut ihren Rahmen daraus, statt ihn zu raten: Im Browser sind die
    #: Aufnahmen querformatige Fenster, in der App **hochkant** — ein
    #: Telefon-Bildschirm in einem 16:9-Kasten stünde als schmaler Streifen
    #: zwischen zwei leeren Flächen (Tims Befund 07.09.2026).
    #:
    #: Alle Medien einer Ausgabe teilen sich EIN Verhältnis, sonst springt der
    #: Kasten beim Blättern (``tests/test_releases.py``).
    aspect: str = "16/9"
    #: Nur bei ``video``: das Standbild, bis der Clip läuft. Es ist zugleich
    #: das, was bei ``prefers-reduced-motion`` STATT des Clips steht.
    poster: str | None = None
    #: Das **Titelbild** der Video-Kachel (seit 3.0.0, Tims Befund
    #: 07.10.2026: „die Karte fühlt sich langweilig an … mehr Bilder, mehr
    #: Anreiz"). Hochformat, füllt die Kachel randlos; der Titel steht weiß
    #: darauf. Das Standbild (``poster``) ist dafür das falsche Bild: Es ist
    #: der erste Frame des Clips — ein querformatiges Browserfenster, auf
    #: dem man in einer Kachel nichts erkennt. Gerendert wird das Titelbild
    #: als ``<name>-titel.webp`` (1080×1200) aus derselben Pipeline wie die
    #: Clips. Ohne Titelbild nimmt die Kachel das Standbild.
    cover: str | None = None
    #: Die Länge des Clips in Sekunden — die Kachel zeigt sie („▶ 0:24"),
    #: weil „wie lange dauert das?" die Frage vor dem Tipp ist. Gemessen
    #: (``ffprobe``), nicht geschätzt; ``tests/test_releases.py`` hält die
    #: Zahl gegen die Datei, wenn ``ffprobe`` da ist.
    duration: float | None = None


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
    #: Dasselbe Feature **im Browser am Telefon** aufgenommen — hochkant und
    #: randlos (Drehbuch mit ``mobil``, ``web/clips/src/HochClip.tsx``). Der
    #: Spieler im schmalen Browser nimmt diese Fassung: Der 16:9-Clip vom
    #: Schreibtisch stand dort 340 px breit, seine Untertitel ~11 px hoch
    #: (gemessen 07.10.2026). Alles oder nichts je Ausgabe, wie bei der
    #: App-Fassung (``has_narrow_media``) — die Kachel zeigt weiter ``cover``.
    media_narrow: Media | None = None
    #: Für welche Oberfläche dieses Highlight überhaupt gilt: ``None``
    #: (überall), ``"web"`` oder ``"native"``.
    #:
    #: Features unterscheiden sich wirklich zwischen Web und App — 2.2.0 hat
    #: das Glossar nur im Browser, und die App-Fassungen der iOS-Ausgabe haben
    #: umgekehrt kein Gegenstück im Web. Ein Highlight anzukündigen, das man
    #: auf dem eigenen Gerät nicht finden kann, ist schlimmer als eines
    #: weniger (Tims Entscheidung 07.09.2026).
    only: str | None = None
    #: Die Farbe der Video-Kachel (``TILE_COLORS``). Sie trägt die Kachel,
    #: den Fortschrittsbalken im Spieler und den Knopf „… ausprobieren", damit
    #: man im Spieler weiß, aus welcher Kachel man kam. Ohne Wert: Hafenblau.
    color: str | None = None
    #: **Nebenbei** statt Kachel: Das Highlight steht als schmale Zeile
    #: „Außerdem: …" unter den Kacheln (3.0.0: „Frag den Rat liest den ganzen
    #: Vorgang"). Für eine Neuerung, die zu klein für eine eigene Bühne ist,
    #: aber zu groß, um sie wegzulassen. Es zählt nicht zum Fortschritt
    #: „1 von 3 angesehen" und nicht zur Abfolge im Spieler — sonst müsste
    #: man es durchsehen, um die Karte abzuschließen.
    aside: bool = False
    #: Eine Zeile unter dem Titel der Kachel („Was sich vor deiner Haustür
    #: tut."). ``text`` ist dafür zu lang — zwei Sätze, die erst im Spieler
    #: unter dem Clip Platz haben. Ohne Zeile zeigt die Kachel den Anfang
    #: von ``text``.
    tagline: str | None = None
    #: Die Beschriftung des Knopfs im Spieler, der zum Feature führt
    #: („Mein Viertel ausprobieren"). Ein Verb, kein Etikett — der Titel
    #: eines Highlights ist oft ein ganzer Satz, „Lotti erklärt dir, was du
    #: siehst ausprobieren" wäre keiner. Ohne Wert: „Ausprobieren".
    action: str | None = None


@dataclass(frozen=True)
class Release:
    """Ein Release, wie die Karte es zeigt."""

    #: ``x.y.0`` — dieselbe Zahl wie im Changelog und im Git-Tag.
    version: str
    #: Erscheinungsdatum, ISO. Es entscheidet, wer die Karte sieht: Ein Konto,
    #: das jünger ist, hat das Feature von Anfang an gehabt.
    date: str
    #: Die Überschrift der Karte — ein Name nach dem Hauptfeature.
    title: str
    highlights: tuple[Highlight, ...]
    #: Eine Zeile unter dem Titel, die sagt, was einen erwartet („Drei neue
    #: Wege durch den Rat — je ein kurzes Video."). Sie beantwortet die Frage,
    #: ob sich das Durchklicken lohnt, bevor jemand klickt.
    teaser: str | None = None


#: Alle Releases mit Karte, **neueste zuerst**.
#:
#: Wer hier einträgt, tut es im Release-PR (``dev`` → ``main``), zusammen mit
#: dem Versionsschnitt: Changelog, App-Version und diese Liste gehören in
#: denselben Commit.
RELEASES: tuple[Release, ...] = (
    Release(
        version="3.0.0",
        # Vorläufig: der Tag, an dem die Karte entstand. Der Versionsschnitt
        # im Release-PR setzt den echten Release-Tag — das Datum entscheidet,
        # wer die Karte sieht (``pending_for``).
        date="2026-10-06",
        title="Das Lotti-Update",
        teaser="Drei neue Wege durch den Rat — je ein kurzes Video.",
        highlights=(
            Highlight(
                title="Lotti erklärt dir, was du siehst",
                # „Markieren“ nur als Zusatz für den Browser: Die App kennt
                # keine Textauswahl (ios/…/AssistantSheet.swift, „Was in v1
                # fehlt“) — der Satz muss auf beiden Geräten stimmen.
                text="Tipp auf Lotti unten rechts und frag, was du zur Seite wissen "
                     "willst; im Browser erklärt sie auch ein markiertes Wort. Für "
                     "die Antwort schlägt sie selbst in Sitzungen und Beschlüssen "
                     "nach.",
                url="/council/decision?id=21966",
                tagline="Tipp auf die Möwe — sie schlägt selbst nach.",
                action="Lotti ausprobieren",
                # Signal-Orange ist die Farbe der KI (Funken, Tipp-Anzeige):
                # Was Lotti tut, trägt sie.
                color="signal",
                # Titelbild und Länge: Das Titelbild kommt aus der
                # Clip-Pipeline (``<name>-titel.webp``, ohne Text) und gilt für
                # Web UND App — das Standbild der App-Aufnahme zeigte oben
                # Uhrzeit und Dynamic Island. Die Längen sind mit ``ffprobe``
                # gemessen.
                media=Media(
                    kind="video",
                    src="/neuigkeiten/3.0.0/lotti.mp4",
                    poster="/neuigkeiten/3.0.0/lotti.webp",
                    cover="/neuigkeiten/3.0.0/lotti-titel.webp",
                    duration=28.8,
                    alt="Eine Beschluss-Seite: Ein Klick auf Lotti unten rechts "
                        "öffnet ihr Fenster, auf „Wie viele haben dagegen "
                        "gestimmt?“ antwortet sie „16“. Danach wird "
                        "„Öffentlichkeitsbeteiligung“ markiert, ein Klick auf "
                        "„Lotti fragen“ erklärt das Wort.",
                ),
                media_narrow=Media(
                    kind="video", aspect="6/13",
                    src="/neuigkeiten/3.0.0/lotti-mobil.mp4", poster="/neuigkeiten/3.0.0/lotti-mobil.webp",
                    cover="/neuigkeiten/3.0.0/lotti-titel.webp", duration=20.0,
                    alt="Dieselbe Beschluss-Seite am Telefon: Ein Tipp auf Lotti unten "
                        "rechts öffnet ihr Fenster; auf „Wie viele haben dagegen "
                        "gestimmt?“ antwortet sie mit den Zahlen aus dem Protokoll, "
                        "danach erklärt sie „Öffentlichkeitsbeteiligung“.",
                ),
                media_ios=Media(
                    kind="video", aspect="1080/2350",
                    src="/neuigkeiten/3.0.0/lotti-ios.mp4", poster="/neuigkeiten/3.0.0/lotti-ios.webp",
                    cover="/neuigkeiten/3.0.0/lotti-titel.webp", duration=16.6,
                    alt="Eine Beschluss-Seite in der App: Ein Tipp auf Lotti unten rechts "
                        "öffnet ihr Blatt; auf „Wie viele haben dagegen gestimmt?“ "
                        "antwortet sie „Dagegen gestimmt haben 16 Ratsmitglieder.“",
                ),
            ),
            Highlight(
                title="Mein Viertel",
                text="Gib deine Straße oder deinen Stadtteil ein und sieh, was der "
                     "Rat dort beschlossen hat — jedes Vorhaben von der Idee bis "
                     "zum Bau, mit Bebauungsplänen und den Beschlüssen dazu.",
                url="/karte",
                tagline="Was sich vor deiner Haustür tut.",
                action="Mein Viertel ausprobieren",
                # Das Grün der Bebauungspläne auf der Stadtkarte — dort
                # spielt das Feature.
                color="green",
                media=Media(
                    kind="video",
                    src="/neuigkeiten/3.0.0/viertel.mp4",
                    poster="/neuigkeiten/3.0.0/viertel.webp",
                    cover="/neuigkeiten/3.0.0/viertel-titel.webp",
                    duration=28.2,
                    alt="Von „Heute“ über „Mein Viertel“ in der Seitenleiste in den "
                        "eigenen Stadtteil Fliegerhorst: Ein Klick auf „Neue "
                        "Grundschule und Dreifeldhalle“ zeigt den Stand des Vorhabens "
                        "und die Beschlüsse dazu, „Stadt zeigen“ führt in jedes "
                        "andere Viertel.",
                ),
                media_narrow=Media(
                    kind="video", aspect="6/13",
                    src="/neuigkeiten/3.0.0/viertel-mobil.mp4", poster="/neuigkeiten/3.0.0/viertel-mobil.webp",
                    cover="/neuigkeiten/3.0.0/viertel-titel.webp", duration=20.6,
                    alt="Am Telefon: „Mehr“, dann „Mein Viertel“ — der eigene Stadtteil "
                        "Fliegerhorst mit Karte und Liste; ein Tipp auf „Neue "
                        "Grundschule und Dreifeldhalle“ zeigt Stand, Zeitplan und die "
                        "Beschlüsse.",
                ),
                media_ios=Media(
                    kind="video", aspect="1080/2350",
                    src="/neuigkeiten/3.0.0/viertel-ios.mp4", poster="/neuigkeiten/3.0.0/viertel-ios.webp",
                    cover="/neuigkeiten/3.0.0/viertel-titel.webp", duration=23.4,
                    alt="In der App: „Mehr“, dann „Mein Viertel“ — die Stadtkarte mit allen "
                        "Vorhaben. Ein Tipp auf Fliegerhorst zeigt seine Vorhaben, ein Tipp "
                        "auf „Wohnen am Offizierskasino“ Stand, Bebauungsplan und Beschlüsse.",
                ),
            ),
            Highlight(
                title="Ideen aus anderen Städten",
                text="Was haben Hannover, Münster oder Potsdam schon beantragt oder "
                     "beschlossen, das Oldenburg noch fehlt? Je Idee siehst du, wie "
                     "sie durch die Räte lief — und mit Belegen, was es in "
                     "Oldenburg dazu schon gibt.",
                url="/council/ideen",
                tagline="Was andere Räte schon beschlossen haben.",
                action="Ideen entdecken",
                # Hafenblau: der Rat selbst, hier die Räte der anderen Städte.
                color="primary",
                media=Media(
                    kind="video",
                    src="/neuigkeiten/3.0.0/ideen.mp4",
                    poster="/neuigkeiten/3.0.0/ideen.webp",
                    cover="/neuigkeiten/3.0.0/ideen-titel.webp",
                    duration=29.2,
                    alt="Über „Analyse“ zu „Ideen aus anderen Städten“: Ein Klick auf "
                        "„Hitzeaktionsplan aufstellen“ zeigt unter „Und in "
                        "Oldenburg?“, was es hier schon gibt; die Zeitleiste zeigt, "
                        "wann Potsdam und Magdeburg darüber beraten haben.",
                ),
                media_narrow=Media(
                    kind="video", aspect="6/13",
                    src="/neuigkeiten/3.0.0/ideen-mobil.mp4", poster="/neuigkeiten/3.0.0/ideen-mobil.webp",
                    cover="/neuigkeiten/3.0.0/ideen-titel.webp", duration=25.7,
                    alt="Am Telefon: „Mehr“, „Analyse“, Reiter „Ideen aus anderen "
                        "Städten“; ein Tipp auf „Hitzeaktionsplan aufstellen“ zeigt, "
                        "was es in Oldenburg schon gibt, und die Zeitleiste durch die "
                        "Räte.",
                ),
                media_ios=Media(
                    kind="video", aspect="1080/2350",
                    src="/neuigkeiten/3.0.0/ideen-ios.mp4", poster="/neuigkeiten/3.0.0/ideen-ios.webp",
                    cover="/neuigkeiten/3.0.0/ideen-titel.webp", duration=24.4,
                    alt="In der App: „Mehr“, dann „Ideen aus anderen Städten“; ein Tipp auf "
                        "„Hitzeaktionsplan aufstellen“ zeigt unter „Und in Oldenburg?“, was "
                        "es hier schon gibt, und die Zeitleiste durch die Räte.",
                ),
            ),
            Highlight(
                title="Frag den Rat liest den ganzen Vorgang",
                text="Fragst du nach einem Vorhaben, stehen unter der Antwort jetzt "
                     "sein Verlauf als Zeitleiste und die Eckdaten.",
                url="/fragen",
                tagline="Zeitleiste und Eckdaten unter jeder Antwort.",
                action="Frag den Rat ausprobieren",
                color="primary",
                # Nebenbei: zu klein für eine eigene Kachel neben den drei
                # großen, zu groß zum Weglassen — eine Zeile „Außerdem: …"
                # unter den Kacheln, der Clip öffnet sich auf Tipp.
                aside=True,
                media=Media(
                    kind="video",
                    src="/neuigkeiten/3.0.0/akte.mp4",
                    poster="/neuigkeiten/3.0.0/akte.webp",
                    cover="/neuigkeiten/3.0.0/akte-titel.webp",
                    duration=28.8,
                    alt="Frag den Rat: Auf die Frage nach dem neuen Fußballstadion "
                        "stehen unter der Antwort „Kurz gesagt“, die Eckdaten — 16 "
                        "Gegenstimmen, 57,3 Mio. € — und der Verlauf bis zum "
                        "aktuellen Stand.",
                ),
                media_narrow=Media(
                    kind="video", aspect="6/13",
                    src="/neuigkeiten/3.0.0/akte-mobil.mp4", poster="/neuigkeiten/3.0.0/akte-mobil.webp",
                    cover="/neuigkeiten/3.0.0/akte-titel.webp", duration=25.9,
                    alt="Am Telefon: Unter „Fragen“ die Frage nach dem neuen "
                        "Fußballstadion; unter der Antwort „Kurz gesagt“, die Eckdaten "
                        "und der Verlauf bis zum aktuellen Stand.",
                ),
                # Nur im Browser: Die App zeigt unter einer Antwort weder
                # Zeitleiste noch Eckdaten (in ``ios/`` kommt ``key_facts``
                # nicht vor). Angekündigt wird nur, was man auf dem eigenen
                # Gerät auch findet — wie 2.2.0 beim Glossar.
                only=NUR_WEB,
            ),
        ),
    ),
    Release(
        version="2.2.0",
        date="2026-09-06",
        title="Das Teilen-Update",
        highlights=(
            Highlight(
                title="Sitzungen teilen — auch einzelne Punkte",
                text="An jeder Sitzung und an jeder Zeile der Tagesordnung steht "
                     "jetzt ein Teilen-Knopf. Wer den Link bekommt, liest die "
                     "Sitzung ohne Konto und landet direkt bei dem gemeinten Punkt.",
                url="/council?tab=sessions",
                media=Media(
                    kind="video",
                    src="/neuigkeiten/2.2.0/teilen.mp4",
                    poster="/neuigkeiten/2.2.0/teilen.webp",
                    alt="Eine aufgeklappte Tagesordnung; an jeder Zeile ein "
                        "Teilen-Knopf. Einer wird angetippt, es erscheint "
                        "„Link kopiert“.",
                ),
                media_ios=Media(
                    kind="video", aspect="1206/2622",
                    src="/neuigkeiten/2.2.0/teilen-ios.mp4", poster="/neuigkeiten/2.2.0/teilen-ios.webp",
                    alt="Dieselbe Tagesordnung auf dem iPhone: ein Tipp auf das "
                        "Teilen-Zeichen an einem Punkt öffnet das Teilen-Blatt "
                        "von iOS, ein Tipp auf „Erinnerungen“ legt den Link "
                        "dort als neue Erinnerung ab.",
                ),
            ),
            Highlight(
                title="Deine Sitzungen im Kalender",
                text="Die Termine deiner abonnierten Gremien laufen jetzt in Apple "
                     "Kalender, Google oder Outlook mit — einmal abonniert, danach "
                     "aktualisiert sich alles von selbst.",
                url="/abos",
                media=Media(
                    kind="video",
                    src="/neuigkeiten/2.2.0/kalender.mp4",
                    poster="/neuigkeiten/2.2.0/kalender.webp",
                    alt="Die Seite „Ausschuss-Abos“: Ein Klick auf „Im Kalender "
                        "abonnieren“ klappt die Karte auf, ein Klick auf "
                        "„Link kopieren“ zeigt „Link kopiert“.",
                ),
                media_ios=Media(
                    kind="video", aspect="1206/2622",
                    src="/neuigkeiten/2.2.0/kalender-ios.mp4", poster="/neuigkeiten/2.2.0/kalender-ios.webp",
                    alt="Der Bildschirm „Ausschuss-Abos“ auf dem iPhone: Ein Tipp "
                        "klappt „Im Kalender abonnieren“ auf, ein Tipp auf "
                        "„Kalender abonnieren“ öffnet die Kalender-App mit dem "
                        "Abo-Dialog.",
                ),
            ),
            Highlight(
                title="Der Rat erklärt seine Fachwörter",
                text="„Was ist eine Ausfallbürgschaft?“ beantwortet die KI-Frage "
                     "jetzt zuverlässig, und im Antworttext liegt unter jedem "
                     "Fachwort eine kurze Erklärung zum Antippen.",
                url="/fragen",
                media=Media(
                    kind="video",
                    src="/neuigkeiten/2.2.0/glossar.mp4",
                    poster="/neuigkeiten/2.2.0/glossar.webp",
                    alt="Die KI-Frage „Was ist eine Veränderungssperre?“ wird "
                        "beantwortet; im Antworttext ist der Begriff gepunktet "
                        "unterstrichen, beim Überfahren erscheint die Erklärung.",
                ),
                # Nur im Browser: Im ganzen ``ios/``-Baum kommt „glossar" nicht
                # vor. Ein Feature anzukündigen, das man auf dem eigenen Gerät
                # nicht finden kann, ist schlimmer als eines weniger.
                only=NUR_WEB,
            ),
            Highlight(
                title="Live: welcher Punkt gerade dran ist",
                text="Während einer Ratssitzung zeigt die Übersicht mit, welcher "
                     "Tagesordnungspunkt gerade läuft und wer spricht — aus der "
                     "Übertragung mitgelesen.",
                url="/dashboard",
                media=Media(
                    kind="video",
                    src="/neuigkeiten/2.2.0/live.mp4",
                    poster="/neuigkeiten/2.2.0/live.webp",
                    alt="Die Live-Karte „Der Stadtrat tagt gerade“ mit dem "
                        "laufenden Punkt; ein Klick auf „Tagesordnung“ öffnet "
                        "die Sitzung, der Punkt trägt „Läuft gerade“.",
                ),
                media_ios=Media(
                    kind="video", aspect="1206/2622",
                    src="/neuigkeiten/2.2.0/live-ios.mp4", poster="/neuigkeiten/2.2.0/live-ios.webp",
                    alt="Die Startseite der App mit der Live-Karte „Der Stadtrat "
                        "tagt gerade“; ein Tipp auf „Tagesordnung“ öffnet die "
                        "Sitzung, der laufende Punkt trägt „Läuft gerade“.",
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


#: Der Bestand aus der Zeit, als jede Minor eine Karte bekam. Diese Einträge
#: bleiben stehen: Die Karte stand auf Prod, Leute haben sie gesehen, und die
#: Liste ist eine Geschichte und kein Aushang (siehe „Alte Einträge bleiben
#: stehen" oben). Die Liste wächst nicht — ein neuer Eintrag hier wäre eine
#: Ausnahme von einer Regel, die gerade erst aufgeräumt wurde.
KARTE_BESTAND: frozenset[str] = frozenset({"2.2.0"})


def is_feature_release(version: str) -> bool:
    """Darf diese Version eine Karte haben? Nur ``x.0.0`` — plus der Bestand.

    Die engere Regel seit 09/2026 (vorher: jedes ``x.y.0``) steht im
    Modul-Docstring unter Schranke 1. Sie hier zu prüfen statt im Review
    daran zu erinnern, ist der Unterschied zwischen einer Regel und einer
    Bitte — die Minor-Fassung war eine Bitte und wurde fünf Mal übergangen.
    """
    if version in KARTE_BESTAND:
        return True
    try:
        major, minor, patch = version_key(version)
    except ValueError:
        return False
    return minor == 0 and patch == 0


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


def highlights_for(release: Release, client: str = "web") -> tuple[Highlight, ...]:
    """Die Highlights, die auf DIESER Oberfläche etwas zu suchen haben."""
    nativ = client in NATIVE_CLIENTS
    return tuple(
        h for h in release.highlights
        if h.only is None or h.only == (NUR_NATIVE if nativ else NUR_WEB)
    )


def has_native_media(release: Release) -> bool:
    """Ist die App-Fassung dieser Ausgabe vollständig?

    Gemessen an den Highlights, die die App überhaupt zeigt — ein rein
    webseitiges braucht dort kein Bild, weil es dort gar nicht erscheint.
    """
    sichtbar = highlights_for(release, "ios")
    return bool(sichtbar) and all(h.media_ios is not None for h in sichtbar)


def has_narrow_media(release: Release) -> bool:
    """Ist die Telefon-Fassung fürs Web vollständig? (Alles oder nichts.)"""
    sichtbar = highlights_for(release, "web")
    return bool(sichtbar) and all(h.media_narrow is not None for h in sichtbar)


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
    schmal = client not in NATIVE_CLIENTS and has_narrow_media(release)

    def medium(m: Media | None) -> dict | None:
        if m is None:
            return None
        return {"kind": m.kind, "src": m.src, "alt": m.alt,
                "aspect": m.aspect, "poster": m.poster,
                "cover": cover_for(m), "duration": m.duration}

    return {
        "version": release.version,
        "date": release.date,
        "title": release.title,
        "teaser": release.teaser,
        "highlights": [
            {"title": h.title, "text": h.text, "url": h.url,
             "media": medium(h.media_ios if nativ else h.media),
             "media_narrow": medium(h.media_narrow) if schmal else None,
             "color": h.color or DEFAULT_TILE_COLOR,
             "aside": h.aside,
             "tagline": h.tagline,
             "action": h.action or DEFAULT_ACTION}
            for h in highlights_for(release, client)
        ],
    }


#: Ohne eigene Farbe trägt eine Kachel Hafenblau — die Farbe des Rats.
DEFAULT_TILE_COLOR = "primary"

#: Ohne eigene Beschriftung heißt der Knopf im Spieler schlicht so.
DEFAULT_ACTION = "Ausprobieren"


def cover_for(media: Media) -> str:
    """Das Bild für die Kachel: Titelbild, sonst Standbild, sonst das Bild.

    Die Wahl fällt hier und nicht in den Clients (dieselbe Regel wie bei
    ``media_for``): Web und App zeigen damit dieselbe Kachel, und eine Ausgabe
    ohne Titelbilder sieht trotzdem nicht leer aus.
    """
    if media.cover:
        return media.cover
    if media.kind == "video" and media.poster:
        return media.poster
    return media.src


def tiles_for(release: Release, client: str = "web") -> tuple[Highlight, ...]:
    """Die Highlights, die eine KACHEL bekommen — ohne die nebenbei genannten.

    Sie bilden die Abfolge im Spieler und den Fortschritt „1 von 3 angesehen".
    """
    return tuple(h for h in highlights_for(release, client) if not h.aside)
