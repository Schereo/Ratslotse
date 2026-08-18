"""Euro-Beträge aus Beschlusstexten lesen — heuristisch, ohne LLM.

Konservativ: Erkannt wird nur eine Zahl **neben einem Währungswort** (€ / EUR /
Euro), damit weder Datum noch Stückzahl hereinfällt. Deutsche Schreibweise
(1.500.000,50) und Mio./Mrd. inklusive. Der Betrag eines Beschlusses ist der
größte gefundene Wert — ein Größenordnungs-Anhalt, kein Haushaltsbetrag.

Wovon der Wert getragen wird
----------------------------
``amount_eur`` speist vier Lesewege: ``money_by_field()``,
``largest_financial_decisions()``, ``activity_trends()`` und das Geld-Signal
des Wichtig-Werts. Ein Fehlgriff ist deshalb nie nur eine falsche Zahl auf
einer Seite — er hebt einen Beschluss in Ranglisten, in die er nicht gehört.

Zwei Sorten Zahl, die **nicht** der Betrag eines Beschlusses sind
-----------------------------------------------------------------
1. **Stückpreise.** „Jahreskarte 324,00 €", „Spontanessen 3,90 €", „ein
   1 Euro-Tagesticket": Der Beschluss setzt einen *Preis* fest. Sein Volumen
   steht dort gar nicht — wer den Preis als Volumen nimmt, behauptet, die
   Stadt habe über 3,90 € entschieden. Erkannt wird das am Umfeld: ein
   Tarifwort davor (Karte, Ticket, Gebühr, Entgelt, Preis …) oder eine
   Mengenangabe davor bzw. dahinter (pro/je Tag, Monat, Person, m² …).
2. **Schwellen.** „… Auszahlungen und Aufwendungen **unter** 50.000 EUR",
   „Wertgrenzen … **überschreiten**: 400.000 Euro": Die Zahl beschreibt die
   Grenze, ab der berichtet wird, nicht das, worüber berichtet wird. Ein
   Sammelbericht über hundert Kleinbeträge trüge sonst die Schwelle als
   Betrag.

Beide Filter arbeiten am **Fundort**, nicht am ganzen Text: Ein Beschluss darf
neben einem Stückpreis sehr wohl ein echtes Volumen nennen, und dann soll das
Volumen gewinnen. Deshalb wird je Fundstelle entschieden und erst danach das
Maximum gebildet.

Was bewusst **nicht** gefiltert wird
------------------------------------
Der Deckungsvorschlag („Als Deckungsmittel stehen … 1.600.000 € zur
Verfügung") sieht wie ein Kandidat aus, ist aber keiner: In den gemessenen
Texten ist die Deckungssumme regelmäßig **derselbe** Betrag wie die
Bewilligung, und wo sie es nicht ist, steht sie für dieselbe Entscheidung.
Ein Filter darauf verlöre echte Beträge, um eine Ungenauigkeit zu heilen, die
sich nicht messen ließ. Er gehört in eine zweistufige Extraktion (Titel zuerst),
nicht in dieses Blatt-Modul.
"""
from __future__ import annotations

import re

_NUM = r"(?:\d{1,3}(?:\.\d{3})+|\d+)(?:,\d+)?"
_CUR = r"(?:€|EUR|Euro)"
# "1,2 Mio. €" / "3 Millionen Euro" / "1,5 Mrd"
_SCALED = re.compile(rf"({_NUM})\s*(Mio\.?|Mrd\.?|Mill?\.?|Millionen|Milliarden)\s*{_CUR}?", re.IGNORECASE)
# "250.000 €" / "12.500,00 EUR" — Nicht-Buchstabe als Vorschau (nicht \b, das
# scheitert nach €).
_PLAIN = re.compile(rf"({_NUM})\s*{_CUR}(?![a-zA-Z])", re.IGNORECASE)

_MAX = 5_000_000_000  # Plausibilitätsdeckel (Oldenburgs Haushalt liegt bei ~1 Mrd.)

#: So weit wird um einen Fundort herum gelesen. 70 Zeichen davor reichen für
#: „… maximale Parkgebühr pro Tag sollte bei 6 € liegen", ohne den halben Satz
#: davor mitzunehmen; 40 dahinter für „324,00 € pro Monat" und „€/m²".
_VOR, _NACH = 70, 40

#: Einheiten, die eine Zahl zum **Stückpreis** machen: zählbare Dinge, Personen
#: und Messgrößen. Zeiträume stehen hier bewusst **nicht** — „jährlich
#: 80.000 Euro Zuschuss" ist das Volumen des Beschlusses und kein Stückpreis;
#: ein Haushalt ist von Natur aus jährlich. Diese Trennung ist der Unterschied
#: zwischen „3,90 € je Essen" (kein Volumen) und „13.739,52 EUR jährlich"
#: (Volumen).
_EINHEIT = (r"m²|m2|qm|quadratmeter|kwh|stück|stk|einwohner|kopf|person|kind|"
            r"schüler|teilnehmer|mitglied|verein|fachkraft|fall|antrag|platz|"
            r"fahrt|essen|mahlzeit|nutzung|ausweis|karte|ticket|tonne|liter|"
            r"km|kilometer")

#: Tarifwörter im Umfeld **vor** der Zahl: „Jahreskarte 324,00 €", „maximale
#: Parkgebühr pro Tag sollte bei 6 € liegen".
#:
#: Kein ``\b`` vor dem Wortstamm — deutsche Komposita kleben: „Parkgebühr",
#: „Nutzungsentgelt", „Monatskarte". Eine Wortgrenze zu verlangen hieße, genau
#: die Formen zu verpassen, in denen der Bestand diese Wörter schreibt.
#:
#: Das bloße Wort „Preis" fehlt mit Absicht: Der **Kaufpreis** eines
#: Grundstücks ist genau das Volumen des Beschlusses (390.585 Euro für die
#: VHS-Anteile). Aufgenommen sind deshalb nur die Zusammensetzungen, die je
#: Einheit rechnen — qm-Preis, Stückpreis, Stundensatz.
_TARIF_DAVOR = re.compile(
    r"\w*(?:karte|ticket|gebühr|entgelt|tarif|eintritt)(?:en|e|s|es)?\b"
    r"|\b(?:qm|quadratmeter|stück|einzel)-?preis(?:e|es)?\b"
    r"|\b(?:stunden|kilometer|tages)satz(?:es)?\b",
    re.IGNORECASE)

#: Tarifwörter, die **unmittelbar** vor der Zahl stehen müssen, weil sie als
#: Teilwort zu häufig sind, um in einem 70-Zeichen-Fenster verlässlich zu sein:
#: „Spontanessen 3,90 €" ist ein Preis, „im Interesse … 500.000 €" nicht.
_TARIF_DIREKT = re.compile(
    r"\w*(?:essen|abonnement|verpflegung)\s*:?\s*$", re.IGNORECASE)

#: Mengenangabe **vor** der Zahl: „pro eingestellter Fachkraft einen
#: monatlichen Zuschuss von 250,00 Euro", „eine Tonne CO² … 195,00 €".
_MENGE_DAVOR = re.compile(
    rf"(?:pro|je)\s+(?:\w+\s+){{0,3}}(?:{_EINHEIT})\w*\b"
    rf"|\beine[nrs]?\s+(?:{_EINHEIT})\w*\b",
    re.IGNORECASE)

#: Einheit **hinter** der Zahl: „275 €/m²", „12 € pro Einwohner", „1 Euro-
#: Tagesticket". Der Bindestrich-Fall braucht den Kompositum-Vorlauf: Im
#: Bestand steht „-Tagestickets", nicht „-Ticket".
_MENGE_DANACH = re.compile(
    rf"^\s*(?:/|-|pro\s+|je\s+)\s*(?:\w*?(?:karte|ticket)|{_EINHEIT})\w*",
    re.IGNORECASE)

#: Schwellenwörter vor der Zahl — „unter 50.000 EUR", „Wertgrenzen …
#: überschreiten: 400.000 Euro". „über" fehlt bewusst: „Bericht über
#: 50.000 EUR" wäre damit keine Schwelle, sondern ein Fehlgriff in die
#: Gegenrichtung.
_SCHWELLE = re.compile(
    r"\b(?:unter|unterhalb|oberhalb)\s+(?:von\s+)?$"
    r"|\b(?:über|unter)schreiten\b",
    re.IGNORECASE)

#: „Wertgrenze" gilt für den ganzen Beschluss, nicht nur fürs Fenster — s.
#: :func:`_ist_schwelle`.
_WERTGRENZE = re.compile(r"\bwertgrenzen?\b", re.IGNORECASE)

#: Ein Titel, der eine **Preisentscheidung** ankündigt: „Änderung der
#: Parkgebühren", „Festsetzung der Entgelte Fahrradsammelgarage". Solche
#: Beschlüsse haben kein Volumen — sie setzen Preise, und ihre Zahlen sind
#: Tarife. Der Tarif-Filter am Fundort erwischt davon nur die erste Zeile
#: einer Tariftabelle; ab der zweiten („Zone 1 … ab 01.01.2024 0,70 €, ab
#: 01.01.2025 0,90 €") ist das Tarifwort aus dem Fenster gewandert.
#:
#: Gemessen (18.08.2026, Bestand 7.705 Beschlüsse): 226 Beschlüsse tragen ein
#: solches Titelwort, **fünf** davon nach allen übrigen Filtern noch einen
#: Betrag — und alle fünf sind Preise (2× 540,00 € Bewohnerparkausweis,
#: 1,30 € Parkgebühr, 2× 3,70 € Schulessen). Die Regel kostet keinen echten
#: Betrag.
#:
#: Gegenprobe, die dieselbe Regel am **ganzen Text** verwarf: Dort träfe sie
#: acht Beschlüsse und kostete fünf echte Beträge, darunter einen über
#: 20 Mio. € („Rettungsschirm für die Kommunen", in dem „Gebühren" beiläufig
#: vorkommt). Der Titel weiß, worum es geht; der Fließtext nicht.
_TARIF_TITEL = re.compile(
    r"\w*(?:gebühr|entgelt|tarif|eintrittspreis|fahrpreis|verpflegung)\w*",
    re.IGNORECASE)

#: Der **Sammelbericht**: „Über- und außerplanmäßige Auszahlungen, Aufwendungen
#: und Verpflichtungsermächtigungen bis zu 50.000 Euro in der Zeit vom
#: 01.01.2025 bis 30.06.2025". Er berichtet über *alles unterhalb* einer
#: Grenze — die 50.000 sind die Meldeschwelle, nicht die Summe. Was wirklich
#: bewilligt wurde, steht nur in der Anlage. Siebzehn solcher Zeilen liegen im
#: Bestand, jede trug bisher ihre Schwelle als Beschlussbetrag.
#:
#: **Warum am Titel und nicht am Fundort.** „bis zu" allein trägt nicht.
#: Gemessen (18.08.2026): 26 Beträge stehen hinter einem „bis zu" — 14 sind
#: diese Berichtsgrenze, die anderen **12 sind echte Volumen**
#: („Ausfallbürgschaft … in Höhe von bis zu 116,5 Millionen Euro",
#: „Unterstützung bis zu 1,5 Mio. Euro für den BTB"). Eine Regel auf „bis zu"
#: kostete zwölf echte Beträge, um vierzehn Grenzen zu treffen — der schlechte
#: Tausch, den dieses Modul gerade vermeiden soll.
#:
#: Die Berichtsform dagegen ist eindeutig und verlangt alle drei Teile:
#: Gegenstand im Plural (Auszahlungen/Aufwendungen), eine Grenze, ein
#: Berichtszeitraum. Die drei zusammen treffen im Bestand genau die 17 Zeilen
#: und keine andere.
_SAMMELBERICHT_TITEL = re.compile(
    r"planmäßige\w*\s+(?:auszahlungen|aufwendungen)"   # der Gegenstand, im Plural
    r".{0,120}?\b(?:unter|bis\s+zu)\b"                 # die Grenze
    r".{0,60}?\bin\s+der\s+Zeit\s+vom\b",              # der Berichtszeitraum
    re.IGNORECASE | re.DOTALL)


def _to_float(num: str) -> float | None:
    num = num.strip()
    num = num.replace(".", "").replace(",", ".") if "," in num else num.replace(".", "")
    try:
        return float(num)
    except ValueError:
        return None


def _scale(unit: str) -> float:
    u = unit.lower()
    return 1e9 if (u.startswith("mrd") or "milliard" in u) else 1e6


def _ist_stueckpreis(vor: str, nach: str) -> bool:
    """Beschreibt diese Fundstelle einen Preis je Einheit statt eines Volumens?"""
    return bool(_TARIF_DAVOR.search(vor) or _TARIF_DIREKT.search(vor)
                or _MENGE_DAVOR.search(vor) or _MENGE_DANACH.match(nach))


def _ist_schwelle(vor: str, ganzer_text: str) -> bool:
    """Steht die Zahl für eine Berichtsgrenze statt für einen Betrag?

    ``Wertgrenze`` wird am **ganzen** Text geprüft, nicht am Fenster: Ein
    Beschluss, der Wertgrenzen festsetzt, zählt sie in einer Aufzählung auf
    („400.000 Euro bei Auftragsvergaben • 75.000 Euro bei Planungsleistungen •
    125.000 Euro …"). Ab dem dritten Aufzählungspunkt ist das auslösende Wort
    aus jedem Fenster gewandert — die Zahlen bleiben trotzdem Grenzen."""
    return bool(_SCHWELLE.search(vor) or _WERTGRENZE.search(ganzer_text))


def ist_preisbeschluss(titel: str | None) -> bool:
    """Kündigt der Titel eine Preisentscheidung an (Gebühren, Entgelte, Tarife)?

    Dann hat der Beschluss kein Volumen, und jede Zahl darin ist ein Preis."""
    return bool(_TARIF_TITEL.search(titel or ""))


def ist_sammelbericht(titel: str | None) -> bool:
    """Berichtet der Beschluss über alles *unterhalb* einer Meldeschwelle?

    Dann ist die genannte Zahl die Grenze, nicht die Summe — die tatsächlich
    bewilligten Beträge stehen nur in der Anlage."""
    return bool(_SAMMELBERICHT_TITEL.search(titel or ""))


def extract_amounts(text: str, titel: str | None = None) -> list[float]:
    """Alle Euro-Beträge des Textes, die ein Beschlussvolumen sein können.

    Stückpreise und Schwellenwerte fallen am Fundort heraus (s. Modul-Kopf).
    ``titel`` ist optional und trägt die zwei Entscheidungen, die der Fließtext
    nicht hergibt: ob der ganze Beschluss über Preise geht, und ob er ein
    Sammelbericht unterhalb einer Meldeschwelle ist."""
    if not text or ist_preisbeschluss(titel) or ist_sammelbericht(titel):
        return []
    out: list[float] = []
    for rx, skaliert in ((_SCALED, True), (_PLAIN, False)):
        for m in rx.finditer(text):
            v = _to_float(m.group(1))
            if v is None:
                continue
            if skaliert:
                v *= _scale(m.group(2))
            vor = text[max(0, m.start() - _VOR):m.start()]
            nach = text[m.end():m.end() + _NACH]
            if _ist_stueckpreis(vor, nach) or _ist_schwelle(vor, text):
                continue
            out.append(v)
    return [a for a in out if 0 < a < _MAX]


def largest_amount(text: str, titel: str | None = None) -> float | None:
    """Der größte Euro-Betrag im Text (das finanzielle Gewicht eines Beschlusses)."""
    amounts = extract_amounts(text, titel)
    return max(amounts) if amounts else None
