"""Geprüfte Erklärtexte für die Grundfragen, die Laien zum Haushalt stellen —
„Warum macht die Stadt überhaupt Schulden?", „Hat die Stadt genug Geld?",
„Kann ich mitbestimmen, wofür das Geld ausgegeben wird?".

**Warum es das gibt.** 36 echte Laienfragen durch Lottis Fenster (Befund
24.09.2026): rund die Hälfte endete mit „geht aus den Angaben nicht hervor",
obwohl die Frage eine Antwort hat — nur keine Oldenburger ZAHL, sondern eine
Regel. Warum Städte Kredite aufnehmen, steht im Kommunalverfassungsgesetz,
nicht im Haushaltsplan. Tim, 24.09.2026: „Die meisten, die hier Fragen
stellen, werden keine richtig technischen Fragen stellen. Und trotzdem müssen
wir gute Antworten geben."

**Warum eine eigene Datei und nicht das Glossar** (:mod:`kern.glossar`).
Beide sind gepflegtes Wissen als Code, im PR sichtbar. Aber sie unterscheiden
sich in allem, worauf es ankommt:

* **Der Auslöser.** Ein Glossar-Begriff greift, wenn das FACHWORT im Text
  steht („Ausfallbürgschaft"). Die Grundfragen kommen ohne Fachwort: „warum
  macht die stadt überhaupt schulden" nennt weder „Investitionskredit" noch
  „§ 120". Hier löst ein WORTFELD der Frage aus, und nur die Frage — nie der
  Bildschirm, auf dem „Schulden" in jeder Überschrift steht.
* **Die Quelle.** Eine Glossar-Erklärung ist allgemeinsprachlich und ohne
  Beleg. Jeder Text hier trägt die Rechtsnorm mit Paragraf oder die
  städtische Unterlage, aus der er stammt — Lotti nennt sie mit.
* **Die Länge und der Ort.** Das Glossar erscheint im Frontend als
  Unterringelung jedes Fachworts (``scripts/glossar_ts.py`` erzeugt die
  TypeScript-Fassung, ``pruefe.py`` hält beide gleich). Zwei bis vier Sätze
  über Liquiditätskredite unter einem unterringelten Wort wären falsch am
  Platz; diese Texte gehen NUR in Lottis Prompt.

**Regeln für einen neuen Eintrag.** Jede Aussage muss mit der genannten
Quelle belegbar sein — nachgelesen, nicht erinnert (die Paragrafen unten
sind am 24.09.2026 gegen NI-VORIS geprüft). Keine Oldenburger Zahl: Die
kommen aus den Haushaltsdaten und tragen dort Jahr und Beleg. Keine Wertung.
Der Auslöser arbeitet auf gefaltetem Text (klein, ä → ae, Satzzeichen weg),
und er muss eng genug sein, dass eine Frage, die ihn nicht meint, ihn nicht
zieht — jede Regel im Prompt kostet die Fälle, für die sie nicht gilt
(gemessen in PR 21, s. ``kern/prompts.py::WEGWEISER_REGEL``).
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Erklaerung:
    """Ein Erklärtext: wann er greift, was er sagt, woher das stammt."""
    key: str
    titel: str
    ausloeser: re.Pattern[str]
    text: str
    quelle: str


ERKLAERUNGEN: tuple[Erklaerung, ...] = (
    Erklaerung(
        key="kredite",
        titel="Warum Städte Kredite aufnehmen",
        # „warum … schulden", „schulden machen", „darf die stadt kredite …".
        # NICHT „wie viele schulden" oder „wann sind die schulden weg": Das
        # sind Fragen an die Zahl, und die hat der Schulden-Baustein.
        ausloeser=re.compile(
            r"\b(?:warum|wieso|weshalb|wozu|wofuer)\b[^?!.]{0,50}"
            r"(?:schulden|kredit|darlehen|verschuld|leihen|geliehen)"
            r"|(?:schulden|kredite?|darlehen) (?:machen|aufnehmen|aufgenommen|gemacht)"
            r"|\bdarf\b[^?!.]{0,40}(?:schulden|kredit)"
            r"|liquiditaetskredit|kassenkredit|investitionskredit"),
        text=(
            "Eine Kommune in Niedersachsen darf Kredite nur für Investitionen "
            "(etwa Gebäude, Straßen, Fahrzeuge), für die Förderung von Investitionen "
            "anderer und zum Umschulden aufnehmen — und nur, wenn eine andere "
            "Finanzierung nicht möglich ist oder wirtschaftlich unzweckmäßig wäre. "
            "Laufende Ausgaben wie Gehälter oder Sozialleistungen dürfen so nicht "
            "bezahlt werden. Den Gesamtbetrag der geplanten Kredite muss jedes Jahr "
            "die Kommunalaufsicht des Landes genehmigen. Davon getrennt gibt es "
            "Liquiditätskredite: einen kurzfristigen Rahmen, damit die Stadtkasse "
            "Rechnungen pünktlich bezahlen kann, wenn Einnahmen erst später eingehen; "
            "seine Höhe legt die Haushaltssatzung fest."),
        quelle=("§ 120 Abs. 1 und 2 NKomVG (Kredite), § 111 Abs. 6 NKomVG (Vorrang "
                "anderer Finanzierung), § 122 NKomVG (Liquiditätskredite)"),
    ),
    Erklaerung(
        key="genug_geld",
        titel="Was „genug Geld“ im Haushalt einer Stadt heißt",
        # Die Alltagsfassungen: „genug geld", „pleite", „kein geld mehr",
        # „wie steht die stadt finanziell". Bewusst NICHT „leisten": „Kann
        # sich die Stadt das Stadion leisten?" fragt nach einem Vorhaben, und
        # die Antwort steht im Ratsarchiv, nicht in dieser Regel.
        ausloeser=re.compile(
            r"genug geld|\bpleite\b|bankrott|zahlungsunfaehig|kein geld mehr|"
            r"geld (?:reicht|fehlt)|reicht (?:das|ihr|ihm|der stadt) (?:das )?geld|"
            r"knapp bei kasse|\bklamm\b|finanzlage|ueberschuld|"
            r"(?:steht|geht es)\b[^?!.]{0,30}finanziell|finanziell (?:gut|schlecht)"),
        text=(
            "„Genug Geld“ sind im Haushalt einer Stadt drei verschiedene Fragen: ob "
            "die Erträge eines Jahres die Aufwendungen decken (sonst entsteht ein "
            "Fehlbetrag), ob genug Geld in der Kasse ist, um Rechnungen pünktlich zu "
            "zahlen (Liquidität), und wie viel Kredit die Stadt insgesamt aufgenommen "
            "hat (Schulden — ein Bestand an einem Stichtag, keine Jahreszahl). Das "
            "Gesetz verlangt, dass der Haushalt ausgeglichen ist und daneben die "
            "Liquidität und die Finanzierung der Investitionen gesichert sind. Gelingt "
            "der Ausgleich nicht, muss die Stadt ein Haushaltssicherungskonzept "
            "beschließen, das festlegt, bis wann und mit welchen Maßnahmen sie ihn "
            "wieder erreicht."),
        quelle=("§ 110 Abs. 4 NKomVG (Haushaltsausgleich, Liquidität, Finanzierung der "
                "Investitionen), § 110 Abs. 8 NKomVG (Haushaltssicherungskonzept)"),
    ),
    Erklaerung(
        key="pflicht",
        titel="Pflichtaufgaben und freiwillige Aufgaben",
        # „muss die stadt … bezahlen", „theater streichen", „wo kann die stadt
        # sparen" — alles Fragen danach, was der Rat überhaupt weglassen darf.
        ausloeser=re.compile(
            r"pflichtaufgab|pflichtleistung|\bfreiwillig|"
            r"\b(?:muss|muessen)\b[^?!.]{0,30}\b(?:bezahlen|zahlen|leisten|uebernehmen|"
            r"anbieten|machen)\b|"
            r"\bstreichen\b|\bgestrichen\b|abschaffen|dichtmachen|"
            r"\bsparen\b|einsparen|\bkuerzen\b"),
        text=(
            "Manche Aufgaben muss die Stadt erfüllen, weil ein Gesetz sie ihr als "
            "Pflichtaufgabe zuweist; bei staatlichen Aufgaben, die ihr das Land "
            "übertragen hat, arbeitet sie zudem nach dessen Weisungen. Andere "
            "übernimmt sie freiwillig: Soziale, kulturelle, sportliche und "
            "wirtschaftliche Einrichtungen stellt sie „in den Grenzen ihrer "
            "Leistungsfähigkeit“ bereit — hier entscheidet der Rat, ob und in welchem "
            "Umfang. Wie viel Spielraum sie bei einer einzelnen Aufgabe hat, stuft "
            "die Stadt Oldenburg im Haushaltsplan selbst ein; das ist ihre "
            "Einschätzung, keine rechtliche Prüfung."),
        quelle=("§ 4 NKomVG (Aufgabenerfüllung, freiwillige Einrichtungen), § 5 Abs. 1 "
                "Nr. 4 NKomVG (Pflichtaufgaben), § 6 NKomVG (übertragener "
                "Wirkungskreis); Haushaltsplan 2026 der Stadt Oldenburg, Einstufung "
                "des Spielraums je Produkt"),
    ),
    Erklaerung(
        key="mitreden",
        titel="Wie man beim Haushalt in Oldenburg mitreden kann",
        # „kann ich mitbestimmen", „wie kann man sich beteiligen" — aber
        # NICHT „Beteiligungen" (die städtischen Gesellschaften, Konzern-Seite).
        #
        # Belegt für Oldenburg, gezählt am 24.09.2026 in council.sqlite: Der
        # Tagesordnungspunkt „Einwohnerfragestunde" steht 82-mal beim Rat und
        # 87-mal beim Ausschuss für Finanzen und Beteiligungen; der Haushalt
        # 2026 lief dort als öffentlicher Punkt (Ö 9.5) und im Rat (Ö 6.5).
        # Die Zahlen stehen bewusst NICHT im Text — sie veralten, und Lotti
        # schriebe sie ab.
        ausloeser=re.compile(
            r"mitbestimm|mitreden|mitentscheid|mitsprache|mitwirk|mitmachen|"
            r"\bbeteiligen\b|buergerbeteiligung|buergerhaushalt|beteiligungshaushalt|"
            r"einwohnerfragestunde|buergerbegehren|"
            r"einfluss (?:nehmen|haben)|was kann ich (?:dagegen |da )?tun|"
            r"\bkann (?:ich|man)\b[^?!.]{0,40}(?:vorschlagen|beantragen|einbringen|"
            r"fragen stellen|mitreden)"),
        text=(
            "Den Haushalt beschließt der Rat als Satzung; vorher wird er öffentlich "
            "im Ausschuss für Finanzen und Beteiligungen beraten. Auf den "
            "Tagesordnungen des Rats und dieses Ausschusses steht in Oldenburg "
            "regelmäßig eine Einwohnerfragestunde, in der man Fragen stellen kann. "
            "Anträge — auch Änderungsanträge zum Haushalt — stellen die "
            "Ratsmitglieder und Fraktionen; wer etwas ändern möchte, kann sie "
            "ansprechen, und jede Person kann sich schriftlich mit einer Anregung "
            "oder Beschwerde an den Rat wenden. Ein Bürgerbegehren über die "
            "Haushaltssatzung ist dagegen gesetzlich ausgeschlossen."),
        quelle=("§ 58 Abs. 1 Nr. 9 NKomVG (Rat beschließt die Haushaltssatzung), § 62 "
                "NKomVG (Einwohnerfragestunde), § 56 NKomVG (Antragsrecht der "
                "Ratsmitglieder), § 34 NKomVG (Anregungen und Beschwerden), § 32 Abs. 2 "
                "Satz 2 Nr. 3 NKomVG (kein Bürgerbegehren über die Haushaltssatzung); "
                "Tagesordnungen im Ratsinformationssystem der Stadt Oldenburg — "
                "Haushalt 2026 öffentlich im Ausschuss für Finanzen und Beteiligungen "
                "am 03.12.2025 und 04.02.2026, beschlossen im Rat am 09.02.2026; "
                "Einwohnerfragestunde als Tagesordnungspunkt des Rats und des "
                "Finanzausschusses; Änderungslisten der Fraktionen zum Haushalt"),
    ),
    Erklaerung(
        key="defizit",
        titel="Defizit und Überschuss",
        # „mehr ausgegeben als eingenommen" — aber nicht „mehr ausgegeben als
        # GEPLANT": Das ist die Frage an den Plan-Ist-Vergleich.
        ausloeser=re.compile(
            r"defizit|fehlbetrag|ueberschuss|\bim minus\b|roten zahlen|schwarze null|"
            r"ausgeglichen|haushaltsausgleich|haushaltssicherung|"
            r"mehr (?:aus als (?:sie |es )?ein|ausgegeben als (?:sie |es )?eingenommen)"),
        text=(
            "Ein Defizit — im Haushaltsrecht „Fehlbetrag“ — heißt: In einem Jahr sind "
            "die Aufwendungen höher als die Erträge; ein Überschuss ist das "
            "Gegenteil. Gerechnet wird das im Ergebnishaushalt, der auch den "
            "Wertverlust von Gebäuden und Anlagen (Abschreibungen) zählt; was "
            "tatsächlich in die Kasse ein- und aus ihr herausfließt, zählt getrennt "
            "davon der Finanzhaushalt — deshalb kann dasselbe Jahr in der einen "
            "Rechnung einen Überschuss und in der anderen einen Fehlbetrag zeigen. "
            "Der Haushalt soll jedes Jahr ausgeglichen sein; ein Fehlbetrag darf mit "
            "Überschüssen aus früheren Jahren (Rücklagen) verrechnet werden."),
        quelle=("§ 2 KomHKVO (Ergebnishaushalt), § 3 KomHKVO (Finanzhaushalt), § 110 "
                "Abs. 4 und 5 NKomVG (Haushaltsausgleich, Verrechnung mit "
                "Überschussrücklagen)"),
    ),
)

#: Höchstens so viele je Frage. Zwei, weil die Fragen, die mehr ziehen, eine
#: Mischung sind („warum ist die stadt pleite, obwohl sie überschuss hat") —
#: und jeder weitere Text die Oldenburger Zahlen weiter nach hinten schiebt.
MAX_JE_FRAGE = 2


def _falte(text: str) -> str:
    """Dieselbe Faltung wie ``council.assistant.falte`` — hier nachgebaut, weil
    ``kern`` nicht aus ``council`` importieren darf (tests/test_schichten.py)."""
    text = (text or "").lower()
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        text = text.replace(a, b)
    return " ".join(re.sub(r"[^a-z0-9 ]+", " ", text).split())


def finde(frage: str, max_n: int = MAX_JE_FRAGE) -> list[Erklaerung]:
    """Die Erklärtexte, die diese FRAGE auslöst — in der Reihenfolge oben.

    Nur die Frage, nie der Bildschirm: Auf der Schulden-Seite steht „Schulden"
    in jeder Überschrift, und „Wann sind die Schulden weg?" soll deshalb
    keinen Text über Kreditrecht bekommen.
    """
    t = _falte(frage)
    if not t:
        return []
    return [e for e in ERKLAERUNGEN if e.ausloeser.search(t)][:max_n]
