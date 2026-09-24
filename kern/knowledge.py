"""Was jede Seite zeigt — in Menschentext, für Lottis Erklärungen.

**Wozu.** Die Assistentin erklärt, was jemand gerade vor sich hat. Dafür
braucht sie zweierlei: den Text des angeklickten Elements (den schickt der
Browser mit) und das Wissen, **wo** dieser Text steht — welche Frage die
Seite beantwortet, woher ihre Zahlen kommen und was sie ausdrücklich NICHT
sagt. Das Zweite steht nirgends im Bestand: Eine Route ist im Frontend ein
Verzeichnis, im Zähler eine Zeile und sonst nichts.

**Warum hier und nicht im Frontend.** Der Text geht in einen Prompt, und
Prompts sind in diesem Repo Code (``kern/prompts.py``) — im PR sichtbar, mit
Diff und Historie. Eine zweite Fassung im Frontend liefe auseinander, und die
Oberfläche braucht sie nicht: Sie zeigt die Seite selbst.

**Was hier NICHT hingehört.** Keine Zahl — Zahlen kommen aus den Daten und
veralten hier still. Keine Bewertung („zu wenig", „gut aufgestellt"). Kein
Fachwort ohne Erklärung im selben Satz; wer eins braucht, nimmt einen Eintrag
aus :mod:`kern.glossar`, den der Prompt ohnehin dazulegt. Und keine
redaktionellen Seitentexte in Kopie: Die stehen im Frontend
(``lib/haushalt-bereiche.ts`` und Geschwister) und erreichen den Prompt als
Text des angeklickten Elements.

**Die Liste ist vollständig, und ein Wächter hält das.** Jede Route aus
:data:`kern.seitenaufrufe.ROUTEN` steht in genau einer von drei Mengen:
:data:`OEFFENTLICH` (außerhalb der App-Hülle, dort gibt es keinen
Lotti-Knopf), :data:`PAGES` (erklärbar) oder :data:`OHNE_ERKLAERUNG` (mit
Grund gesperrt). ``tests/test_assistant.py`` prüft die Zerlegung in beide
Richtungen — eine neue Seite zwingt damit zu einer Entscheidung, statt still
als „kenne ich nicht" zu enden.
"""
from __future__ import annotations

from dataclasses import dataclass

from kern.seitenaufrufe import ANDERE, ROUTEN


@dataclass(frozen=True)
class PageKnowledge:
    """Was Lotti über eine Seite weiß."""

    #: Der Schlüssel aus ``kern.seitenaufrufe.ROUTEN``.
    route: str
    #: Wie die Seite heißt, wenn man von ihr spricht. Kurz.
    title: str
    #: Zwei bis vier Sätze: Was zeigt die Seite, und wie liest man sie?
    what: str
    #: Ein Satz: Woher kommen die Angaben?
    sources: str
    #: Ein Satz: Was sagt die Seite ausdrücklich NICHT? Der wichtigste von
    #: dreien — er verhindert, dass eine Erklärung mehr verspricht als die
    #: Seite hält.
    limits: str
    #: Recht, das die Seite verlangt (``kern.roles.PERMISSIONS``), oder
    #: ``None``. Ohne das Recht nennt eine Erklärung die Seite nicht als
    #: Ziel — ein Verweis auf eine gesperrte Seite ist ein Verweis ins 404.
    requires: str | None = None
    #: Darf Lotti hier von selbst anklopfen? Nur auf Seiten, auf denen man
    #: liest — nicht dort, wo man arbeitet oder ohnehin schon fragt.
    nudge: bool = False
    #: Zwei Fragen fürs LEERE Fenster (PR 25) — kuratiert, nicht geraten.
    #: Jede muss Lotti mit ihren heutigen Mitteln beantworten können:
    #: deterministisch (Glossar, Beschluss-Kurzfassung, Seiten-Wissen, der
    #: Gegenstands-Block aus ``refs``) oder über die Haushalts-Facetten aus
    #: ``council.qa.geld_facetten`` — nie eine Frage, die nur eine
    #: Seitenbeschreibung ergäbe (dafür gibt es „Was sehe ich hier?").
    #: ``tests/test_assistant.py`` hält Zahl, Länge, Eindeutigkeit und — auf
    #: Haushalts-Seiten — den Facetten-Treffer fest.
    starters: tuple[str, str] = ("", "")


def _p(route: str, title: str, what: str, sources: str, limits: str,
       *, requires: str | None = None, nudge: bool = False,
       starters: tuple[str, str]) -> tuple[str, PageKnowledge]:
    return route, PageKnowledge(route=route, title=title, what=what, sources=sources,
                                limits=limits, requires=requires, nudge=nudge,
                                starters=starters)


#: Der Haushalts-Bereich hat überall dieselbe Quelle und dieselbe Grenze.
_HH_QUELLE = ("Die Zahlen stammen aus den Haushaltsplänen, Jahresabschlüssen und "
              "Rechenschaftsberichten der Stadt; jede Angabe trägt auf der Seite "
              "einen Beleg-Chip, der zum Originaldokument führt.")
_HH_GRENZE = ("Die Seite bewertet nichts — sie zeigt, was in den Unterlagen steht, "
              "und sagt dazu, aus welchem Jahr die Zahl stammt.")


#: Jede Seite der App-Hülle, die Lotti erklären darf.
PAGES: dict[str, PageKnowledge] = dict([
    # ── Einstieg ────────────────────────────────────────────────────────
    _p("/dashboard", "Heute",
       "Die Startseite nach dem Anmelden. Sie stellt in Karten zusammen, was seit "
       "dem letzten Besuch dazugekommen ist, welche Sitzungen in dieser Woche "
       "anstehen und was in den eigenen Vierteln passiert.",
       "Alles kommt aus den Ratsunterlagen der Stadt und aus den eigenen "
       "Einstellungen dieses Kontos.",
       "Die Seite entscheidet nichts vor — sie sortiert nur, was ohnehin öffentlich ist.",
       starters=(
           "Werden auch meine eigenen Viertel berücksichtigt?",
           "Woher stammen die Angaben auf dieser Seite?",
       ),
    ),
    _p("/fragen", "Frag den Rat",
       "Hier stellt man eine Frage in eigenen Worten, und die Antwort entsteht aus "
       "den gefundenen Beschlüssen. Jede Aussage trägt eine Nummer in eckigen "
       "Klammern, die zu der Quelle führt, auf der sie beruht.",
       "Gesucht wird in allen erfassten Ratsbeschlüssen, Protokollen und "
       "Vorlagentexten der Stadt Oldenburg.",
       "Antworten kommen aus den Beschlüssen, nicht aus allgemeinem Wissen — was "
       "dort nicht steht, sagt die Antwort auch nicht.",
       starters=(
           "Was für Fragen kann ich hier stellen?",
           "Woher weiß ich, worauf eine Antwort beruht?",
       ),
    ),
    _p("/karte", "Stadtkarte",
       "Die Karte zeigt, wo in der Stadt etwas beschlossen wurde. Ein Klick auf "
       "ein Viertel öffnet die Vorhaben, die dort laufen, mit dem Stand der "
       "letzten Ratsberatung.",
       "Die Orte stammen aus einem gepflegten Ortsverzeichnis; ein Beschluss "
       "erscheint nur dort, wo sein Text den Ort wirklich nennt.",
       "Ein Vorhaben ohne benannten Ort taucht auf der Karte nicht auf — die "
       "Karte ist kein vollständiges Bild der Stadt.", nudge=True,
       starters=(
           "Wie finde ich Vorhaben in meinem Viertel?",
           "Woher weiß die Karte, wo etwas beschlossen wurde?",
       ),
    ),
    _p("/viertel", "Mein Viertel",
       "Die alte Adresse von „Mein Viertel“; sie führt heute auf die Stadtkarte, "
       "wo dieselben Vorhaben je Viertel stehen.",
       "Siehe Stadtkarte.",
       "Die Seite selbst zeigt nichts mehr an, sie leitet nur weiter.",
       starters=(
           "Wo finde ich die Vorhaben meines Viertels jetzt?",
           "Warum landet diese Seite auf der Stadtkarte?",
       ),
    ),
    _p("/topics", "Meine Themen",
       "Die eigenen Interessengebiete. Für jedes Thema sucht Ratslotse in neuen "
       "Tagesordnungen und Beschlüssen nach passenden Punkten und meldet sich, "
       "wenn etwas dazukommt.",
       "Die Treffer entstehen aus dem Abgleich der eigenen Beschreibung mit den "
       "Tagesordnungen und Vorlagentexten der Stadt.",
       "Ein Thema, das zu weit gefasst ist, trifft zu viel — die Seite sagt beim "
       "Anlegen, worauf ein Thema gerade zutrifft.",
       starters=(
           "Wie lege ich ein neues Thema an?",
           "Woher kommen die Treffer zu meinen Themen?",
       ),
    ),
    _p("/abos", "Abos",
       "Welche Gremien man abonniert hat und welche Benachrichtigungen dieses "
       "Konto bekommt — je Anlass einzeln einstellbar.",
       "Die Gremienliste kommt aus dem Ratsinformationssystem der Stadt.",
       "Die Seite verschickt nichts; sie legt fest, was künftig kommt.",
       starters=(
           "Welche Gremien kann ich abonnieren?",
           "Wie stelle ich Benachrichtigungen für ein Abo ein?",
       ),
    ),
    _p("/bookmarks", "Merkliste",
       "Gemerkte Beschlüsse und Sitzungen, auf Wunsch in eigenen Gruppen sortiert.",
       "Die Einträge sind die selbst gemerkten Ratsunterlagen dieses Kontos.",
       "Die Liste ist privat und wird mit niemandem geteilt.",
       starters=(
           "Wie merke ich mir einen Beschluss?",
           "Kann ich die Merkliste in Gruppen sortieren?",
       ),
    ),
    _p("/quiz", "Quiz",
       "Ein Spiel über die Stadt und ihre Beschlüsse: Jede Frage hat eine "
       "richtige Antwort, und die Auflösung nennt den Beschluss dahinter.",
       "Die Fragen entstehen aus echten Ratsunterlagen.",
       "Das Quiz ist zum Stöbern gedacht, nicht als Nachschlagewerk.",
       starters=(
           "Woher stammen die Fragen im Quiz?",
           "Sehe ich nach einer Frage den passenden Beschluss?",
       ),
    ),
    _p("/quiz/stats", "Quiz-Statistik",
       "Der eigene Spielstand: beantwortete Fragen, Trefferquote und die "
       "Gebiete, in denen man schon gespielt hat.",
       "Alle Zahlen stammen aus den eigenen Spielrunden.",
       "Die Zahlen sind privat; es gibt keine Rangliste mit anderen Konten.",
       starters=(
           "Woher kommen meine Quiz-Zahlen?",
           "In welchen Gebieten habe ich schon gespielt?",
       ),
    ),

    # ── Ratsinhalte ─────────────────────────────────────────────────────
    _p("/council", "Ratsinfo",
       "Der Einstieg in die Ratsunterlagen mit vier Registern: Suche, Sitzungen, "
       "Themenfelder und Auswertung.",
       "Alles stammt aus dem Ratsinformationssystem der Stadt Oldenburg.",
       "Was die Stadt nicht veröffentlicht — etwa nichtöffentliche Punkte — steht "
       "auch hier nicht.",
       starters=(
           "Was kann ich im Ratsinfo-Bereich finden?",
           "Woher stammen die Ratsunterlagen hier?",
       ),
    ),
    _p("/council?tab=decisions", "Ratsinfo · Suche",
       "Die Volltextsuche über alle erfassten Beschlüsse. Eingrenzen lässt sie "
       "sich nach Ergebnis, Themenfeld, Gremium, Ort und Zeitraum.",
       "Durchsucht werden Beschlusstexte, Titel und Vorlagentexte der Stadt.",
       "Die Suche findet Wörter, keine Bedeutungen — wer eine Frage hat, ist bei "
       "„Frag den Rat“ besser aufgehoben.", nudge=True,
       starters=(
           "Wie grenze ich die Suche nach Beschlüssen ein?",
           "Findet die Suche auch Wörter aus Vorlagentexten?",
       ),
    ),
    _p("/council?tab=sessions", "Ratsinfo · Sitzungen",
       "Alle Sitzungen des Rates und seiner Ausschüsse mit Tagesordnung, Ort und "
       "Zeit; zu vergangenen Sitzungen kommt das Protokoll dazu.",
       "Die Termine und Tagesordnungen kommen aus dem Ratsinformationssystem.",
       "Eine Tagesordnung kann sich bis zur Sitzung noch ändern.", nudge=True,
       starters=(
           "Wo finde ich das Protokoll einer Sitzung?",
           "Kann sich eine Tagesordnung noch ändern?",
       ),
    ),
    _p("/council?tab=themen", "Ratsinfo · Themenfelder",
       "Die Beschlüsse nach Sachgebieten sortiert — Bauen, Soziales, Verkehr und "
       "so weiter —, jeweils mit einem Rückblick auf die letzten Jahre.",
       "Die Zuordnung eines Beschlusses zu einem Themenfeld entsteht maschinell "
       "aus seinem Text.",
       "Ein Beschluss gehört oft zu mehreren Feldern; die Zuordnung ist eine "
       "Hilfe beim Stöbern, keine amtliche Einteilung.", nudge=True,
       starters=(
           "Wie wird ein Beschluss einem Themenfeld zugeordnet?",
           "Kann ein Beschluss zu mehreren Feldern gehören?",
       ),
    ),
    _p("/council?tab=analysis", "Ratsinfo · Auswertung",
       "Zahlen über die Ratsarbeit selbst: wie viele Beschlüsse in welchem "
       "Zeitraum gefasst wurden, wie sie ausgingen und welche Gremien wie oft "
       "getagt haben.",
       "Gezählt werden die erfassten Beschlüsse und Sitzungen der Stadt.",
       "Die Zahlen sagen etwas über Menge und Verlauf, nichts über Bedeutung.",
       nudge=True,
       starters=(
           "Sagen die Zahlen etwas über die Bedeutung der Beschlüsse?",
           "Was wird hier über die Ratsarbeit ausgewertet?",
       ),
    ),
    _p("/council/decision", "Beschluss",
       "Ein einzelner Beschluss: der amtliche Wortlaut, das Ergebnis der "
       "Abstimmung, das Gremium mit Datum, die Vorlage dahinter und die "
       "Beratungsfolge durch die übrigen Gremien. Oben steht eine kurze "
       "Fassung in Alltagssprache.",
       "Alles stammt aus der Vorlage und dem Sitzungsprotokoll der Stadt; die "
       "kurze Fassung ist unsere Übersetzung des Beschlusstextes.",
       "Die Seite sagt, was beschlossen wurde — nicht, ob es inzwischen "
       "umgesetzt ist.", nudge=True,
       starters=(
           "Was wurde beschlossen?",
           "Wie ging die Abstimmung aus?",
       ),
    ),
    _p("/council/sitzung", "Sitzung",
       "Eine einzelne Sitzung mit ihrer vollständigen Tagesordnung; zu jedem "
       "Punkt steht, was daraus geworden ist, sobald das Protokoll vorliegt.",
       "Tagesordnung und Ergebnisse stammen aus dem Ratsinformationssystem.",
       "Solange kein Protokoll vorliegt, steht bei den Punkten noch kein "
       "Ergebnis — das ist kein Fehler, sondern der Stand der Dinge.", nudge=True,
       starters=(
           "Wann findet diese Sitzung statt?",
           "Bekommt jeder Punkt sofort ein Ergebnis?",
       ),
    ),
    # Der Titel bleibt „Themenfeld“ (so heißt die Seite in Statistik und
    # Seitenaufrufen); der Text beschreibt seit 23.09.2026 aber, was sie
    # wirklich zeigt. `themaHref` führt auf `/council/entity/{slug}` — ein
    # Projekt, eine Organisation oder einen Ort mit allen Beschlüssen dazu.
    # Vorher stand hier ein Sachgebiet mit Rückblick, und Lotti erklärte auf
    # der Fliegerhorst-Seite einen Rückblick, den es dort nicht gibt.
    _p("/council/thema", "Themenfeld",
       "Ein Thema, das den Rat beschäftigt — ein Projekt, eine Organisation oder "
       "ein Ort — mit allen Beschlüssen dazu, neueste zuerst, einer kurzen "
       "Beschreibung, den darin erkannten Beträgen und verwandten Themen.",
       "Welche Beschlüsse zu einem Thema gehören, wird maschinell aus ihrem Text "
       "erkannt; die Beschreibung ist eine maschinelle Zusammenfassung.",
       "Die Zuordnung kann einen Beschluss übersehen oder einen zu viel "
       "zeigen; die erkannten Beträge sind keine Haushaltszahlen.", nudge=True,
       starters=(
           "Worum geht es bei diesem Thema?",
           "Wie kommen die Beschlüsse zu diesem Thema?",
       ),
    ),
    _p("/council/person", "Ratsmitglied",
       "Was eine Person im Rat gesagt und beantragt hat: Wortbeiträge aus den "
       "Protokollen, Mitgliedschaften in Gremien und die Anträge ihrer Fraktion.",
       "Die Angaben stammen aus den Anwesenheitslisten und Protokollen der Stadt.",
       "Ein Stimmverhalten gibt es hier nicht: Die Protokolle halten fest, wie "
       "abgestimmt wurde, nicht wer wie gestimmt hat.", nudge=True,
       starters=(
           "Was zeigen die Wortbeiträge einer Person?",
           "Woher stammen die Angaben zu einer Person?",
       ),
    ),
    _p("/council/neuer-rat", "Der neue Rat",
       "Wer nach der Ratswahl ab dem 1. November im Rat sitzt — nach Listen, mit "
       "Wahlbereich, Personenstimmen, Beruf und Jahrgang. Die Karten sagen, wer "
       "neu im Rat ist, wer schon im letzten Rat saß und wer nach einer Pause "
       "zurückkehrt.",
       "Die Sitze stammen aus dem Wahlergebnis der Stadt, Beruf und Jahrgang aus "
       "der Bekanntmachung der Wahlvorschläge, die Jahre im Rat aus den "
       "Protokollen und dem Ratsinformationssystem.",
       "Bis der Wahlausschuss das Ergebnis feststellt, ist es vorläufig; wer vor "
       "2018 im Rat saß und heute nicht mehr geführt wird, erscheint als neu.",
       starters=(
           "Wie kommt ein Sitz über Personenstimmen zustande?",
           "Was passiert, wenn jemand die Wahl ablehnt?",
       ),
    ),
    _p("/council/ort", "Ort",
       "Was an einem bestimmten Ort in der Stadt beschlossen wurde — ein "
       "Quartier, eine Straße, ein Gebäude —, neueste Entscheidung zuerst.",
       "Ein Beschluss erscheint hier nur, wenn sein Text den Ort belegt nennt; "
       "die Fundstelle steht an jedem Treffer.",
       "Zu kleinen Orten gibt es oft nur wenige und ältere Beschlüsse; wie alt "
       "der jüngste ist, steht auf der Seite.", nudge=True,
       starters=(
           "Was wurde an diesem Ort beschlossen?",
           "Warum stehen hier nur wenige Beschlüsse?",
       ),
    ),
    _p("/council/ideen", "Ideen aus anderen Städten",
       "Was andere Stadträte beschlossen haben und in Oldenburg fehlt — je "
       "Themenfeld, mit dem Weg zum Original im Ratsinformationssystem der "
       "jeweiligen Stadt.",
       "Die Vorlagen stammen aus den Ratsinformationssystemen anderer Kommunen; "
       "das Urteil „fehlt in Oldenburg“ entsteht maschinell und trägt Belege.",
       "Die Seite schlägt nichts vor und bewertet nicht, ob eine Idee zu "
       "Oldenburg passt.", nudge=True,
       starters=(
           "Wie wird eine fehlende Idee gefunden?",
           "Bewertet die Seite, ob eine Idee zu Oldenburg passt?",
       ),
    ),
    _p("/council/ideen/bewegung", "Eine Idee aus anderen Städten",
       "Eine Idee, die mehrere andere Räte beantragt oder beschlossen haben: "
       "je Stadt eine Zeitleiste, alle Vorlagen nach Datum mit Ergebnis und — "
       "wo die Niederschrift eine nennt — der Begründung, dazu ein Urteil, ob "
       "Oldenburg die Idee schon hat.",
       "Die Vorlagen stammen aus den Ratsinformationssystemen der Städte. Das "
       "Urteil über Oldenburg fällt ein Sprachmodell an Oldenburger "
       "Ratsunterlagen; die Belege stehen darunter, getrennt von bloß "
       "Verwandtem.",
       "Die Seite sagt nicht, ob sich ein Antrag lohnt. Ein Warum steht nur, wo "
       "die Niederschrift selbst eine Begründung nennt; manche Städte "
       "veröffentlichen ihre Niederschriften nicht.", nudge=True,
       starters=(
           "Woran erkennt die Seite, ob Oldenburg das schon hat?",
           "Warum steht bei manchen Vorlagen kein Warum?",
       ),
    ),

    # ── Haushalt ────────────────────────────────────────────────────────
    _p("/haushalt", "Haushalt — Übersicht",
       "Der Einstieg in den städtischen Haushalt: was die Stadt in einem Jahr "
       "einnimmt und ausgibt, und ein Wegweiser durch zwölf Schritte, die das "
       "der Reihe nach aufschlüsseln.",
       _HH_QUELLE, _HH_GRENZE, requires="budget", nudge=True,
       starters=(
           "Wie groß ist der Haushalt mit den Eigenbetrieben?",
           "Wofür gibt die Stadt am meisten aus?",
       ),
    ),
    _p("/haushalt/einnahmen", "Woher kommt das Geld?",
       "Die Einnahmequellen der Stadt — Steuern, Zuweisungen des Landes, "
       "Gebühren — und wie viel Einfluss der Rat auf ihre Höhe überhaupt hat.",
       _HH_QUELLE, _HH_GRENZE, requires="budget", nudge=True,
       starters=(
           "Wie viel Einfluss hat der Rat auf die Steuern?",
           "Wie viel Gebühren nimmt die Stadt ein?",
       ),
    ),
    _p("/haushalt/pflicht", "Muss oder kann?",
       "Welche Ausgaben die Stadt gesetzlich leisten muss und wo dem Rat "
       "tatsächlich eine Entscheidung bleibt.",
       _HH_QUELLE, _HH_GRENZE, requires="budget", nudge=True,
       starters=(
           "Was muss die Stadt gesetzlich bezahlen?",
           "Wo hat der Rat echten Entscheidungsspielraum?",
       ),
    ),
    _p("/haushalt/produkte", "Was kostet eigentlich …?",
       "Was einzelne Aufgaben kosten — Archiv, Feuerwehr, Schwimmbad — und "
       "welcher Auftrag dahintersteht. Oben stehen die zehn Teilhaushalte im "
       "Klartext, darunter die einzelnen Aufgaben.",
       _HH_QUELLE, _HH_GRENZE, requires="budget", nudge=True,
       starters=(
           "Was kostet die Feuerwehr im Jahr?",
           "Was kostet der Klimaschutz im Jahr?",
       ),
    ),
    _p("/haushalt/personal", "Wer macht die Arbeit?",
       "Wie viele Stellen die Stadt plant, wie viele besetzt sind und wo "
       "Personal fehlt.",
       _HH_QUELLE, _HH_GRENZE, requires="budget", nudge=True,
       starters=(
           "Wie viele Stellen sind unbesetzt?",
           "Wie viele Stellen plant die Stadt insgesamt?",
       ),
    ),
    _p("/haushalt/investitionen", "Was gebaut wird",
       "Welche Neubauten, Fahrzeuge und Grundstücke geplant sind — und wie viel "
       "davon tatsächlich umgesetzt wurde.",
       _HH_QUELLE, _HH_GRENZE, requires="budget", nudge=True,
       starters=(
           "Wie viel investiert die Stadt insgesamt?",
           "Wie viel wurde 2025 tatsächlich investiert?",
       ),
    ),
    _p("/haushalt/plan-ist", "Geplant und geworden",
       "Was die Verwaltung im laufenden Jahr erwartet, und wie weit Plan und "
       "Ergebnis in den Jahresabschlüssen auseinanderliegen.",
       _HH_QUELLE, _HH_GRENZE, requires="budget", nudge=True,
       starters=(
           "Wie stark wich das Ergebnis 2024 vom Ansatz ab?",
           "Wie viel hat die Stadt 2024 tatsächlich ausgegeben?",
       ),
    ),
    _p("/haushalt/pruefung", "Geprüft und zusammengefasst",
       "Was das Rechnungsprüfungsamt beanstandet hat und mit welchen dreizehn "
       "Kennzahlen die Stadt ihren Jahresabschluss zusammenfasst.",
       _HH_QUELLE, _HH_GRENZE, requires="budget", nudge=True,
       starters=(
           "Was hat das Rechnungsprüfungsamt beanstandet?",
           "Was sagen die dreizehn Kennzahlen?",
       ),
    ),
    _p("/haushalt/konzern", "Ist das die ganze Stadt?",
       "Welche städtischen Betriebe und Gesellschaften neben dem Kernhaushalt "
       "stehen — und warum ihre Schulden nicht in derselben Zahl auftauchen.",
       _HH_QUELLE, _HH_GRENZE, requires="budget", nudge=True,
       starters=(
           "Welche Betriebe gehören zum Konzern?",
           "Wie hoch sind die Aufwendungen des Klinikums?",
       ),
    ),
    _p("/haushalt/vergleich", "Steht Oldenburg besser da?",
       "Wie Oldenburg bei Steuerkraft und Hebesätzen im Vergleich zu ähnlichen "
       "Städten dasteht — und warum ein Vergleich der Ausgaben Grenzen hat.",
       _HH_QUELLE, _HH_GRENZE, requires="budget", nudge=True,
       starters=(
           "Wie steht Oldenburg bei der Steuerkraft da?",
           "Warum hat ein Ausgabenvergleich Grenzen?",
       ),
    ),
    _p("/haushalt/schulden", "Wie viel Schulden hat Oldenburg?",
       "Wie sich der Schuldenstand seit 1995 entwickelt hat, welche "
       "Verbindlichkeiten darin stecken und was jährlich an Zinsen und Tilgung "
       "fällig wird.",
       _HH_QUELLE, _HH_GRENZE, requires="budget", nudge=True,
       starters=(
           "Wie viel Schulden hat Oldenburg pro Kopf?",
           "Wie hoch ist der Schuldenstand des Kernhaushalts allein?",
       ),
    ),
    _p("/haushalt/mitreden", "Mitreden",
       "Wann der Haushalt beraten und beschlossen wird, welche Anträge die "
       "Fraktionen dazu gestellt haben und wie sie ausgingen.",
       _HH_QUELLE, _HH_GRENZE, requires="budget", nudge=True,
       starters=(
           "Welche Anträge gab es zum Haushalt?",
           "Wie gingen die Haushaltsanträge aus?",
       ),
    ),
    _p("/haushalt/labor", "Haushalts-Labor",
       "Ein Werkzeug zum Ausprobieren: Man verschiebt Einnahmen und Ausgaben "
       "und sieht sofort, wie sich das Ergebnis der Stadt ändert.",
       "Gerechnet wird auf den echten Zahlen des gewählten Jahres.",
       "Die Ergebnisse sind Gedankenspiele, keine Prognose und kein Vorschlag "
       "der Stadt.", requires="budget",
       starters=(
           "Mit welchem Jahresergebnis startet das Labor?",
           "Wie hoch ist der Ansatz, mit dem das Labor rechnet?",
       ),
    ),
    _p("/haushalt/bereich", "Bereichs-Steckbrief",
       "Ein einzelner Teilhaushalt im Detail: was er umfasst, was er kostet und "
       "welche Aufgaben darin stecken.",
       _HH_QUELLE, _HH_GRENZE, requires="budget", nudge=True,
       starters=(
           "Was kostet dieser Bereich im Jahr?",
           "Nimmt dieser Bereich auch eigene Einnahmen ein?",
       ),
    ),
    _p("/haushalt/steuer", "Steuer-Steckbrief",
       "Eine einzelne Steuer- oder Einnahmeart im Detail: wer sie zahlt, wonach "
       "sie sich bemisst, wer über ihre Höhe entscheidet und wie sie sich "
       "entwickelt hat.",
       _HH_QUELLE, _HH_GRENZE, requires="budget", nudge=True,
       starters=(
           "Wer zahlt diese Steuer?",
           "Wer entscheidet über die Höhe dieser Steuer?",
       ),
    ),
])


#: Routen der App-Hülle, auf denen es Lotti ausdrücklich NICHT gibt — mit dem
#: Grund. Der Knopf fehlt dort, und das Backend weist die Route zurück.
#:
#: Der Maßstab ist nicht „schwierig zu erklären", sondern: Steht auf der Seite
#: etwas, das nicht in einen Prompt gehört? Beim Admin-Panel sind das fremde
#: Konten, auf der Konto-Seite die eigene Adresse. Beides würde mit dem Text
#: des angeklickten Elements mitwandern.
OHNE_ERKLAERUNG: dict[str, str] = {
    "/admin": "Auf der Seite stehen fremde Konten und ihre Adressen.",
    "/account": "Auf der Seite stehen die eigene Adresse und Kontodaten.",
}


#: Alles außerhalb der App-Hülle: Startseite, Anmeldung, Rechtstexte, die
#: Wahl- und Tippspiel-Seiten. Dort gibt es keinen Lotti-Knopf, weil es dort
#: die App-Hülle nicht gibt — die Liste steht hier nur, damit der Wächter
#: JEDE Route aus ``seitenaufrufe.ROUTEN`` zuordnen kann.
OEFFENTLICH: frozenset[str] = frozenset({
    "/", "/login", "/register", "/forgot-password", "/reset-password",
    "/verify-email", "/hilfe", "/impressum", "/datenschutz",
    "/barrierefreiheit", "/changelog", "/g",
    "/kommunalwahl", "/kommunalwahl/check", "/kommunalwahl/methodik",
    "/kommunalwahl/naehe", "/kommunalwahl/liste/{slug}",
    "/kommunalwahl/thema/{slug}",
    "/wahlen", "/wahl", "/wahlabend", "/wahlabend/stichwahl",
    "/stichwahl/potenzial", "/tipp", "/tipp/live", "/tipp/admin",
    ANDERE,
})


def fuer_route(route: str) -> PageKnowledge | None:
    """Das Wissen zu einer normalisierten Route — oder ``None``.

    ``None`` heißt „darüber sage ich nichts": unbekannte Route, öffentliche
    Seite oder eine der gesperrten. Der Aufrufer unterscheidet die Fälle über
    :data:`OHNE_ERKLAERUNG`, weil nur dort ein Grund steht, den man zeigen kann.
    """
    return PAGES.get(route)


def block(wissen: PageKnowledge | None) -> str:
    """Der Prompt-Baustein zu einer Seite. Leer, wenn es keinen gibt."""
    if wissen is None:
        return "(Diese Seite kenne ich nicht näher.)"
    return (f"„{wissen.title}“ — {wissen.what}\n"
            f"  Woher die Angaben kommen: {wissen.sources}\n"
            f"  Was die Seite NICHT sagt: {wissen.limits}")


#: Der Haushalts-Bereich, an einer Stelle. Die Seiten darin gehören
#: zusammen: Eine Frage nach dem Geld landet oft auf der falschen von
#: fünfzehn, und nur hier lohnt der ausführliche Wegweiser (s.
#: :func:`wegweiser`).
HAUSHALT = "/haushalt"


def im_haushalt(route: str) -> bool:
    """Gehört diese Route zum Haushalts-Bereich?

    Über den Pfad UND nicht über ``requires``: Das Haushalts-Labor verlangt
    dasselbe Recht, ist aber ein Werkzeug — die Unterscheidung fällt an
    anderer Stelle (``wegweiser`` nimmt es mit, weil man dorthin verweisen
    darf).
    """
    return route == HAUSHALT or route.startswith(HAUSHALT + "/")


def erster_satz(text: str) -> str:
    """Der erste Satz eines ``what`` — für den Wegweiser.

    **Warum nur einer.** Alle fünfzehn Seiten vollständig wären rund 6.000
    Zeichen in jedem Aufruf; der erste Satz sagt bereits, WAS dort steht, und
    genau das soll Lotti wissen. Was im Einzelnen dort steht, weiß sie
    nicht — sie verweist, sie behauptet nicht.
    """
    sauber = " ".join((text or "").split())
    punkt = sauber.find(". ")
    return sauber if punkt < 0 else sauber[:punkt + 1]


def wegweiser(bereich: str, permissions: frozenset[str] | set[str]) -> list[PageKnowledge]:
    """Alle Seiten eines Bereichs, die dieses Konto erreichen kann.

    **Warum nicht** :func:`verwandte`. Die liefert sechs nackte Titel ohne ein
    Wort dazu, was dort steht — damit lässt sich nicht sagen, wo etwas
    nachzulesen ist, und sechs von fünfzehn Haushalts-Seiten sind eine
    Auswahl, die niemand getroffen hat. Sie bleibt trotzdem: Außerhalb des
    Haushalts tut sie weiter ihren Dienst, und dort ist die Liste kurz.

    Gemessen am 22.09.2026 für ``/haushalt``: 15 Seiten, 2.509 Zeichen, rund
    600 Tokens, etwa +0,015 Cent je Aufruf.
    """
    return [k for k in PAGES.values()
            if k.route == bereich or k.route.startswith(bereich + "/")
            if not (k.requires and k.requires not in permissions)]


def verwandte(wissen: PageKnowledge | None, permissions: frozenset[str] | set[str]) -> list[str]:
    """Seiten, auf die eine Erklärung verweisen darf — nur erreichbare.

    Ohne das Recht ``budget`` ist jeder Verweis auf eine Haushalts-Seite ein
    Verweis ins Nichts: Die Seite antwortet dort mit „nicht gefunden".
    """
    if wissen is None:
        return []
    aus = []
    for k in PAGES.values():
        if k.route == wissen.route:
            continue
        if k.requires and k.requires not in permissions:
            continue
        if wissen.route.startswith("/haushalt") and k.route.startswith("/haushalt"):
            aus.append(f"{k.title} ({k.route})")
    return aus[:6]


def alle_routen() -> frozenset[str]:
    """Jede Route, die irgendwo in diesem Modul vorkommt — für den Wächter."""
    return frozenset(PAGES) | frozenset(OHNE_ERKLAERUNG) | OEFFENTLICH


def fehlende_routen() -> frozenset[str]:
    """Routen aus ``seitenaufrufe.ROUTEN``, die hier keiner Menge angehören."""
    return frozenset(ROUTEN) - alle_routen()


def ueberzaehlige_routen() -> frozenset[str]:
    """Routen, die hier stehen, die es aber gar nicht (mehr) gibt."""
    return alle_routen() - frozenset(ROUTEN)
