"""Kontaktdaten aus dem Text nehmen, der in die Suche geht.

Der Bestand darf alles enthalten, was in den Dokumenten steht — die Parser
brauchen den vollen Text, und ein Beleg, der auf ein PDF zeigt, muss auch das
wiederfinden, was darin steht. Was **nicht** sein muss: dass „Frag den Rat"
eine Kontonummer, eine private Telefonnummer oder eine E-Mail-Adresse
zurückgibt, weil sie zufällig in einer Anlage stand.

Deshalb wird hier NICHT beim Speichern maskiert, sondern **an der
Index-Grenze**: `store.anlagen_missing_embeddings()` (Chunk-Vektoren) und
`store.rebuild_fts()` (Volltextindex) schicken ihren Text durch
:func:`maskieren`. `council_attachments.raw_text` bleibt vollständig.

DAS IST KEIN OCR-THEMA. Gemessen am Prod-Stand vom 16.08.2026 tragen **496
Anlagen** Kontaktdaten — 81 IBAN, 533 E-Mail-Adressen, 1.022 Telefon- und
Faxnummern — und sie stehen längst im Suchindex, ganz ohne Texterkennung. Die
gescannten Anlagen kommen nur dazu.

WAS BEWUSST NICHT MASKIERT WIRD:

* **Namen.** Der Bestand nennt 1.271 Ratsmitglieder namentlich, Protokolle
  führen jede Wortmeldung mit Namen, Vorlagen nennen Amtsleitungen. Namen
  herauszunehmen hieße, das halbe System unbrauchbar zu machen — und eine
  Namenserkennung in deutschem Fließtext übersieht ohnehin welche und schwärzt
  dafür andere falsch.
* **Straßennamen.** Das ist die gefährlichste Falle dieses Moduls. „Ausbau
  Bümmersteder Tredde", „Radweg Alexanderstraße", „Sanierung Donnerschweer
  Straße" — der halbe Investitionsbereich besteht aus Straßennamen. Wer eine
  Anschrift über das Muster „Straße + Hausnummer" erkennt, löscht das
  Investitionsprogramm. Maskiert wird deshalb die **Postleitzahl mit Ort** —
  sie ist eindeutig, steht in Briefköpfen und trägt keine Haushaltsbedeutung —
  und eine Straße nur dann, wenn unmittelbar dahinter eine solche Postleitzahl
  folgt. „Lindenallee 23, 26122 Oldenburg" ist damit weg, „Sanierung
  Butjadinger Straße 61" bleibt.

WAS DAS NICHT LEISTET: Eine Straße ohne Postleitzahl dahinter bleibt stehen,
auch wenn sie eine Wohnanschrift ist. Das ist der Preis dafür, dass das
Investitionsprogramm heil bleibt, und er ist bewusst so bezahlt.
"""
from __future__ import annotations

import re

#: Was an die Stelle der Angabe tritt. Ein sichtbarer Platzhalter und keine
#: Leerstelle: Wer den indexierten Text liest, soll sehen, DASS dort etwas
#: stand — sonst sieht ein Briefkopf aus wie ein Textfehler.
PLATZHALTER = "[Kontaktdaten entfernt]"

#: Deutsche IBAN. Das Heikelste im Bestand: 81 Stück, und eine Kontonummer
#: beantwortet keine einzige Frage über den Haushalt.
#: `\s*` und nicht `\s?`: Eine IBAN bricht im Textextrakt gern mitten
#: in der Ziffernfolge um, und dann steht dort ein Zeilenumbruch samt
#: Einrückung — mehr als ein Leerzeichen.
_IBAN = re.compile(r"\bDE\s*\d{2}(?:\s*\d{4}){4}\s*\d{2}\b")

#: BIC gleich mit — sie steht neben jeder IBAN und ist ohne sie wertlos.
_BIC = re.compile(r"\b[A-Z]{4}DE[A-Z0-9]{2}(?:[A-Z0-9]{3})?\b")

_MAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[A-Za-z]{2,}\b")

#: Telefon und Fax — NUR mit Schlüsselwort davor.
#:
#: Ohne das Schlüsselwort ist jede Ziffernfolge ein Kandidat, und der Bestand
#: ist voll davon: Ein erster Versuch ohne Anker traf „0844", „0001", „0951/1"
#: — Kostenträger- und Produktnummern. 3.093 angebliche Telefonnummern in den
#: Vorlagen waren nach der Prüfung 7 echte.
_TELEFON = re.compile(
    r"(?:Tel\.?|Telefon|Fon|Fax|Telefax|Mobil|Handy)[\s.:]*"
    r"(?:\+49|\(?0)[\d\s()/-]{6,20}\d", re.IGNORECASE)

#: Eine Anschrift — und zwar NUR als Ganzes oder als eigene Zeile.
#:
#: DIE ENGE IST TEUER ERKAUFT. Ein erstes Muster nahm jede fünfstellige Zahl
#: vor einem großgeschriebenen Wort für eine Postleitzahl. Damit fiel
#: „Produkt **11101 Verwaltungssteuerung**" — und der Haushalt besteht aus
#: solchen Zeilen. Auch „Tel. 16656 / Fax" traf es, weil der Zeilenumbruch als
#: Leerraum durchging. Beides hat der eigene Test gefunden, nicht der Betrieb.
#:
#: Zwei Formen bleiben, beide mit Kontext statt bloßem Muster.
_ORT = r"[A-ZÄÖÜ][a-zäöüß]+(?:[ -][A-ZÄÖÜ][a-zäöüß]+)?"
_STRASSE = (r"[A-ZÄÖÜ][\wäöüß.-]*(?:stra[ßs]e|str\.|allee|weg|platz|ring|damm|"
            r"gasse|ufer|chaussee|tredde)")

#: (1) Die ganze Anschrift am Stück: Straße, Hausnummer, Postleitzahl, Ort.
#:     Das ist der Briefkopf, und er ist eindeutig — „Sanierung Butjadinger
#:     Straße 61" hat keine Postleitzahl dahinter und bleibt stehen.
_ANSCHRIFT = re.compile(
    _STRASSE + r"\s*\d{1,4}\s*[a-zA-Z]?\s*[,·|]?\s*\d{5}\s+" + _ORT,
    re.IGNORECASE)

#: (2) Postleitzahl und Ort ALLEIN auf einer Zeile — die zweite Zeile jedes
#:     Briefkopfs und jedes Anschriftenfelds. Ein Produktschlüssel steht nie
#:     allein auf einer Zeile; er trägt immer seine Bezeichnung neben sich.
_PLZ_ZEILE = re.compile(r"^[ \t]*\d{5}\s+" + _ORT + r"[ \t]*$", re.MULTILINE)

#: Was **gar nicht erst gespeichert** wird (Tims Entscheidung 20.08.2026:
#: „IBANs und Adresse kannst du auch komplett rausnehmen").
#:
#: Diese beiden Arten braucht kein Parser des Bestands: Eine Kontonummer ist
#: nie eine Haushaltszahl, und eine vollständige Postanschrift auch nicht —
#: der Straßenname allein bleibt ja stehen, und der ist das Einzige, was das
#: Investitionsprogramm daraus braucht.
#:
#: Der Eingriff ist UNUMKEHRBAR ohne erneutes Laden des PDF. Deshalb steht
#: hier nur, was nachweislich niemand braucht — Telefon und E-Mail gehören
#: bewusst NICHT dazu: Sie stehen in Zuständigkeits- und Kontaktangaben, und
#: eine Rufnummer der Verwaltung kann für einen Beleg noch der Anker sein,
#: an dem jemand die Stelle im PDF wiederfindet.
HART = (_IBAN, _BIC, _ANSCHRIFT, _PLZ_ZEILE)

#: Was zusätzlich aus dem SUCHINDEX genommen wird, aber im Bestand bleibt.
NUR_INDEX = (_MAIL, _TELEFON)

#: Ein Trennstrich am Zeilenende, der ein Wort zerlegt.
#:
#: DER FALL, DER DAS ERZWUNGEN HAT (20.08.2026): Im Förderantrag der
#: Kirchenverwaltung steht die E-Mail-Adresse als
#:
#:     E-Mail: Finanzen.RDSAML-OLS@kirche-
#:     oldenburg.de
#:
#: Die Maskierung sah „…@kirche-" — keine gültige Adresse, kein Treffer. Dann
#: zog `embeddings.anlage_chunks()` die Zeilen zusammen (`vorlagen._entzeilen`
#: joint Silbentrennungen), und im fertigen Chunk stand die vollständige
#: Adresse. Neun solche Chunks fand die Schlussprüfung des Ops-Laufs.
#:
#: Die Reihenfolge war verkehrt herum: Maskiert werden muss die Fassung, die
#: der Index später SIEHT — also die zusammengezogene.
_TRENNSTRICH = re.compile(r"(?<=[A-Za-z0-9])-\s*\n\s*(?=[A-Za-z0-9])")

_MUSTER = HART + NUR_INDEX


def entfernen(text: str | None) -> str:
    """Kontonummern und Anschriften **aus dem Bestand** nehmen.

    Läuft beim SPEICHERN, nicht beim Indexieren — was hier herausfällt, ist
    ohne erneutes Laden des PDF weg. Deshalb nur :data:`HART`.
    """
    aus = _TRENNSTRICH.sub("", text or "")
    for muster in HART:
        aus = muster.sub(PLATZHALTER, aus)
    return aus


def maskieren(text: str | None) -> str:
    """Alle Kontaktdaten durch :data:`PLATZHALTER` ersetzen — für den INDEX.

    Umfasst :data:`HART` (das ist beim gespeicherten Text ohnehin schon weg,
    schadet aber nicht) und zusätzlich Telefon und E-Mail, die im Bestand
    bleiben dürfen.
    """
    # ZUERST die Trennstriche zusammenziehen, DANN maskieren: Der Index sieht
    # die zusammengezogene Fassung (s. `_TRENNSTRICH`), und was er sieht, muss
    # geprüft sein.
    aus = _TRENNSTRICH.sub("", text or "")
    for muster in _MUSTER:
        aus = muster.sub(PLATZHALTER, aus)
    return aus


def enthaelt_kontaktdaten(text: str | None) -> bool:
    """Ob überhaupt etwas zu maskieren wäre — für Berichte und Tests.

    Prüft dieselbe zusammengezogene Fassung wie :func:`maskieren`. Täte sie es
    nicht, meldete die Schlussprüfung eines Ops-Laufs etwas anderes, als die
    Maskierung zu sehen bekommt — und genau das ist am 20.08.2026 passiert.
    """
    flach = _TRENNSTRICH.sub("", text or "")
    return any(muster.search(flach) for muster in _MUSTER)


def zaehlen(text: str | None) -> dict[str, int]:
    """Was gefunden wurde, nach Art — für den Bestandsbericht der Ops-Läufe."""
    t = text or ""
    return {
        "iban": len(_IBAN.findall(t)),
        "bic": len(_BIC.findall(t)),
        "email": len(_MAIL.findall(t)),
        "telefon": len(_TELEFON.findall(t)),
        "anschrift": len(_ANSCHRIFT.findall(t)) + len(_PLZ_ZEILE.findall(t)),
    }
