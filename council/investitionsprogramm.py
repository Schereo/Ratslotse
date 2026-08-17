"""Das Investitionsprogramm — welche einzelnen Vorhaben im Haushalt stehen.

``council/investitionen.py`` beantwortet „wie viel investiert die Stadt?" je
Teilhaushalt: 80,8 Mio. € für 2025, verteilt auf dreizehn Bereiche. Was dort
fehlt, sagt der Modulkopf dieser Datei selbst — „Die Datei sagt ‚Verkehr und
Straßenbau: 10,5 Mio. €', nicht welche Straße." Hier steht die Ebene darunter:
die **einzelne Maßnahme**, mit Bezeichnung und Gesamtinvestitionssumme.

Die Quelle
----------
**Anlage 004 des Haushaltsplans**, seit acht Jahrgängen (2019–2026) im
Anlagenbestand (``council_anlagen``, mit Volltext). Ein PDF von 76–84 Seiten je
Jahrgang, aufgebaut wie folgt::

    Gesamtinvestitionsprogramm
    Investitionssummen je Teilhaushalt          <- Kopftabelle, eine Zeile je THH
      Personal- u. Verwaltungsmanagement  6.584.306  154.906  1.751.900  …
      …
      Gesamtsumme                       170.140.918 …

    THH02 Personal- u. Verwaltungsmanagement    <- ein Abschnitt je Teilhaushalt
      I10.070426.510 IuK: IT-Sicherheitsinfrastruktur, 2026   50.000  50.000
      I10.070426     IuK: IT-Sicherheitsinfrastruktur, 2026   50.000  50.000
      …
      Gesamtsumme                          6.584.306  154.906  1.751.900  …

Die drei Rechenproben
---------------------
Das Dokument rechnet sich auf drei Ebenen selbst vor, und alle drei gehen über
alle acht Jahrgänge **auf den Euro genau** auf (gemessen 17.08.2026):

1. :func:`probe_abschnitt` — die Maßnahmen eines Teilhaushalts ergeben die
   ``Gesamtsumme`` seines Abschnitts.
2. :func:`probe_wiederholung` — diese Abschnitts-Gesamtsumme steht ein zweites
   Mal in der Kopftabelle, rund siebzig Seiten früher. Das ist die stärkste der
   drei: Sie verbindet zwei Stellen des Dokuments, die unabhängig gesetzt sind.
3. :func:`probe_kopftabelle` — die Zeilen der Kopftabelle ergeben deren eigene
   ``Gesamtsumme``.

Warum nur die Gesamtinvestitionssumme
--------------------------------------
Die Tabelle führt neun Spalten: Gesamtinvestitionssumme, bisher bereitgestellt,
und je Planjahr einen Ansatz samt Verpflichtungsermächtigung. Übernommen wird
**nur die erste**.

Grund ist der Textextrakt: Leere Zellen fallen darin ersatzlos weg. Eine Zeile
mit sechs Zahlen kann die Spalten 1, 2, 3, 4, 6, 8 meinen oder 1, 2, 5, 7, 8, 9
— welche, steht nirgends. Die Spalten wären nur über die x-Koordinaten des PDFs
zu retten, und die trägt ``council_anlagen.raw_text`` nicht. Die erste Zahl
einer Zeile ist dagegen immer die Gesamtinvestitionssumme, weil sie die linke
Spalte ist und links nichts wegfallen kann. Eine Spalte, die trägt, ist mehr
wert als fünf, die an kollabierten Leerzellen hängen — die Jahresaufteilung
fehlt deshalb, und die Seite sagt das.

Drei Fallen im Textextrakt
---------------------------
Alle drei sind real aufgetreten und kosteten je einen Anlauf; jede hat ihren
Test in ``tests/test_investitionsprogramm.py``:

1. **Jede Maßnahme steht zweimal da.** Einmal als IPSP-Element
   (``I10.090126``), einmal als Sachkonto-Detailzeile (``I10.090126.525``) mit
   denselben Beträgen. Wer beide summiert, zählt doppelt; 31 Elternelemente
   haben zudem mehrere Detailzeilen. Gezählt wird ausschließlich das
   Elternelement.
2. **Namen brechen um**, und der Rest landet mal auf einer eigenen Zeile
   („Inklusion, Baukosten," / „2026" / „0 0"), mal vor den Beträgen derselben
   Zeile („Erwerb Sportgeräte," / „2027 110.000 110.000").
3. **Ziffern im Namen sind keine Beträge.** Fachdienst-Nummern
   („…, FD 102, 2026 135.000 135.000"), Bebauungsplan-Nummern („BPL 823") und
   die Seitenzahl am Blattfuß sehen wie Zahlen aus. Die erste Fassung las
   deshalb 102 statt 135.000 — dem Teilhaushalt 02 fehlten 134.898 €, und
   Probe 1 hat es gefunden.

Was diese Zahlen **nicht** hergeben
------------------------------------
1. **Plan, nicht Ist.** Das Investitionsprogramm ist Teil des Haushaltsplans.
   Was am Jahresende wirklich gebaut wurde, steht nicht darin — bei
   Investitionen ist der Abstand notorisch groß.
2. **Keine Schulgebäude.** Der Teilhaushalt „Schule und Bildung" führt
   Ausstattung (Hardware, Software, Inklusion) und die berufsbildenden Schulen
   namentlich; die allgemeinbildenden Schulen stehen nur als Sammelposten.
   Sanierung und Neubau von Schulgebäuden liegen beim **Eigenbetrieb
   Gebäudewirtschaft und Hochbau**, den dieses Dokument nur referenziert.
3. **Nicht deckungsgleich mit dem Finanzhaushalt.** Die Kopftabelle sagt es
   selbst: Ihre Gesamtsumme weicht von der Zeile 31 „Saldo aus
   Investitionstätigkeit" des Gesamtfinanzhaushaltes ab, weil zu aktivierende
   Eigenleistungen zwar ins Investitionsprogramm gehören, aber nicht
   zahlungswirksam sind. Ein Abgleich mit ``council_investitionen``
   (Datensatz 1101, Finanzhaushalt) ist deshalb **keine** Probe, sondern ein
   Unterschied, den beide Seiten korrekt so ausweisen.
"""
from __future__ import annotations

import re

#: Rundungstoleranz der Rechenproben in Euro — bewusst unter einem Euro.
#:
#: Dieselbe Begründung wie in ``council/investitionen.py``: Das Dokument führt
#: volle Euro, die kleinstmögliche Abweichung ist damit 1 €. Eine Toleranz von
#: 1 € wäre für genau den einzigen Fehler blind, den die Probe sehen könnte.
#: Gemessen gehen alle drei Proben in allen acht Jahrgängen auf **0 €** auf.
TOLERANZ_EUR = 0.5

#: So viele Maßnahmen muss ein Abschnitt mindestens tragen.
#:
#: **Eine**, und das ist eine gemessene Entscheidung, keine Nachlässigkeit: Der
#: Teilhaushalt „Verwaltungsführung" führt 2020 und 2021 genau eine Maßnahme,
#: 2019 genau zwei. Eine Schwelle von 2 warf deshalb zwei komplette Jahrgänge
#: weg — 1.085 Maßnahmen wegen eines Teilhaushalts, dessen Rechnung aufging.
#: Dass ein einzelner Posten seine Abschnittssumme trivial ergibt, ist
#: verkraftbar: Diese Summe muss zusätzlich in der Kopftabelle wiederkehren
#: (:func:`probe_wiederholung`) und dort in die Gesamtsumme aufgehen
#: (:func:`probe_kopftabelle`). Ein Abschnitt ohne jede Maßnahme fliegt weiter
#: auf.
MINDEST_MASSNAHMEN = 1

#: IPSP-Element. Gruppe 2 ist die Sachkonto-Endung — trägt sie etwas, ist die
#: Zeile eine Detailzeile und zählt nicht mit (Falle 1).
CODE = re.compile(r"^(I\d+\.\d+)(\.\d+)?\b")

#: Abschnittskopf „THH02 Personal- u. Verwaltungsmanagement".
THH = re.compile(r"^THH\s*(\d+)\s+(.*)$")

#: Ein Betrag trägt Tausenderpunkte („650.000", „-47.797.830") oder ist Null.
#: Eine nackte ein- bis vierstellige Zahl ist es nie (Falle 3).
BETRAGSTOKEN = re.compile(r"^-?(?:\d{1,3}(?:\.\d{3})+|0)$")

#: Irgendeine Zahl, auch „700" und „2026" — nur für die Frage, ob eine Zeile
#: GANZ aus Zahlen besteht.
NUMERISCH = re.compile(r"^-?\d+(?:\.\d{3})*$")

#: Seiten- und Spaltenkopf. Steht so nie in einem Maßnahmen-Namen.
MOEBEL = re.compile(
    r"^(www\.oldenburg\.de|Stadt Oldenburg|Investitionsmaßnahme|"
    r"Investitionen und Investitionsförderungs|-? ?Euro|Gesamt-$|"
    r"investitions-$|summe$|bisher$|bereitgestellt$|Ansatz \d|VE für |"
    r"Erläuterungen|Gesamtinvestitionsprogramm|Investitionssummen je|"
    r"Teilhaushalt\s*$)", re.I)

#: Überschrift der Kopftabelle — Beginn des Gesamtinvestitionsprogramms.
KOPFTABELLE = "Investitionssummen je Teilhaushalt"

#: Erste Ansatzspalte im Tabellenkopf — sie trägt den Jahrgang.
_ANSATZ = re.compile(r"Ansatz\s+(20\d\d)")

#: Woran ein Investitionsprogramm im Anlagenbestand zu erkennen ist. Alle acht
#: Jahrgänge tragen das Wort im Label; die Schreibweise davor schwankt
#: („004 Investitionsprogramm", „004 2023 Investitionsprogramm",
#: „2026 004 Vw Investitionsprogramm Haushalt 2026 Verwaltungsentwurf").
LABEL_MUSTER = "%Investitionsprogramm%"

#: Wie die Summenzeile heißt, auf jeder Ebene dieselbe.
GESAMTSUMME = "Gesamtsumme"


def _de(betrag: float, vorzeichen: bool = False) -> str:
    """Betrag in deutscher Schreibweise — „170.140.918,00".

    Wie in ``council/investitionen.py``: Der Rückgabewert von :func:`nachweis`
    landet als ``probe_ergebnis`` in der Herkunft und steht damit im Beleg
    neben der Zahl auf der Seite. Pythons ``{:,.2f}`` liefert dort englische
    Trennzeichen."""
    s = f"{abs(betrag):,.2f}".replace(",", "\x00").replace(".", ",").replace("\x00", ".")
    if vorzeichen:
        return ("+" if betrag >= 0 else "−") + s
    return ("−" if betrag < 0 else "") + s


def jahrgang(text: str | None) -> int | None:
    """Für welchen Haushaltsjahrgang ein Investitionsprogramm gilt.

    **Nicht aus dem Label.** Die vier ältesten der acht Anlagen heißen schlicht
    „004 Investitionsprogramm" und tragen gar keine Jahreszahl; die jüngeren
    tragen sie in wechselnder Schreibweise. Der Tabellenkopf dagegen nennt sie
    immer: Die erste Spalte „Ansatz JJJJ" ist der Jahrgang, die drei danach
    sind die mittelfristige Finanzplanung nach § 8 NKomVG.

    Dieselbe Regel wie bei den Teilhaushalts-Plänen
    (``finanzquellen.teilhaushalt_jahrgang``), und aus demselben Grund
    zuverlässig: Geprüft an allen acht Jahrgängen 2019–2026 trifft der erste
    ``Ansatz JJJJ`` im Dokumentkopf genau den Jahrgang."""
    m = _ANSATZ.search(text or "")
    return int(m.group(1)) if m else None


def betragslauf(zeile: str) -> tuple[str, int] | None:
    """Der Betragsblock einer Zeile → ``(Namensteil, Gesamtinvestitionssumme)``.

    ``None``, wenn die Zeile keine Beträge trägt. Zwei Gestalten, beide belegt:

    1. **Name und Beträge auf einer Zeile** („Medientechnik 7.000 7.000").
       Gelesen wird vom Zeilenende her, solange die Token Tausenderpunkte
       tragen oder Null sind. Vom Anfang her nach der ersten Zahl zu suchen
       wäre falsch — der Name trägt selbst Ziffern (Falle 3).
    2. **Beträge auf eigener Zeile** („6.100 4.000 700 700 700"). Dort stehen
       auch Beträge unter 1.000 ohne Punkt. Erkannt wird die Zeile daran, dass
       sie ganz aus Zahlen besteht, mindestens zwei davon, und mindestens eine
       einen Tausenderpunkt trägt. Die Mindestzahl hält die Seitenzahl am
       Blattfuß („214") und das allein stehende Jahr eines umbrochenen Namens
       („2026") heraus; der Tausenderpunkt hält die Spaltennummern-Zeile
       („2 5431") heraus.
    """
    token = zeile.split()
    if not token:
        return None
    if (len(token) >= 2 and all(NUMERISCH.match(t) for t in token)
            and any("." in t for t in token)):
        # Führende punktlose Token sind kein Betrag, sondern der Rest eines
        # umbrochenen Namens auf derselben Zeile — meist das Jahr
        # („Erwerb Sportgeräte," / „2027 110.000 110.000", Falle 2).
        k = next(i for i, t in enumerate(token) if "." in t)
        return " ".join(token[:k]), int(token[k].replace(".", ""))
    i = len(token)
    while i > 0 and BETRAGSTOKEN.match(token[i - 1]):
        i -= 1
    if i == len(token):
        return None
    return " ".join(token[:i]), int(token[i].replace(".", ""))


def _namen_fuegen(teile: list[str]) -> str:
    """Umbrochene Namensteile zu einem Namen — mit Rücksicht auf Bindestriche.

    Der Zeilenumbruch trennt Wörter mitten im Kompositum („IuK: IT-" +
    „Sicherheitsinfrastruktur"). Dort gehört kein Leerzeichen hin. Beim
    Ergänzungsstrich („Rad-" + „und Gehwege") dagegen schon — sonst stünde
    „Rad-und Gehwege" auf der Seite. Unterschieden wird am nächsten Zeichen:
    Großschreibung setzt das Kompositum fort, Kleinschreibung ist das zweite
    Glied einer Aufzählung."""
    s = ""
    for teil in teile:
        teil = teil.strip()
        if not teil:
            continue
        if not s:
            s = teil
        elif s.endswith("-") and teil[:1].isupper():
            s += teil
        else:
            s += " " + teil
    return " ".join(s.split())


def _name_und_betrag(blob: list[str]) -> tuple[str, int | None]:
    """``(Bezeichnung, Gesamtinvestitionssumme)`` aus den Zeilen eines Satzes."""
    teile: list[str] = []
    for zeile in blob:
        s = zeile.strip()
        if not s or MOEBEL.match(s):
            continue
        lauf = betragslauf(s)
        if lauf is not None:
            kopf, betrag = lauf
            if kopf:
                teile.append(kopf)
            return _namen_fuegen(teile), betrag
        teile.append(s)
    return _namen_fuegen(teile), None


def lies(text: str, jahr: int) -> dict:
    """Ein Investitionsprogramm auswerten.

    Liefert ``{jahr, kopftabelle, kopfsumme, abschnitte, bestanden, nachweis}``:

    * ``kopftabelle`` — ``[{bezeichnung, gesamtsumme}]`` je Teilhaushalt aus
      dem Gesamtinvestitionsprogramm.
    * ``kopfsumme`` — deren ausgewiesene ``Gesamtsumme``.
    * ``abschnitte`` — ``{thh_nr: {name, summe, massnahmen}}``; je Maßnahme
      ``{code, bezeichnung, gesamtsumme}``.
    * ``bestanden`` — ob **alle drei** Proben aufgehen. Ist sie ``False``, sind
      ``abschnitte`` und ``kopftabelle`` leer: Ein Jahrgang, dessen Rechnung
      nicht aufgeht, gibt keine halben Maßnahmen her.
    """
    zeilen = [z.rstrip() for z in (text or "").splitlines()]
    leer = {"jahr": jahr, "kopftabelle": [], "kopfsumme": None,
            "abschnitte": {}, "bestanden": False}
    if not any(KOPFTABELLE in z for z in zeilen):
        return {**leer, "nachweis": f"„{KOPFTABELLE}“ steht nicht im Dokument"}

    kopftabelle, kopfsumme = _lies_kopftabelle(zeilen)
    abschnitte = _lies_abschnitte(zeilen)

    ok, warum = pruefe(kopftabelle, kopfsumme, abschnitte)
    text_nachweis = nachweis(kopftabelle, kopfsumme, abschnitte, ok, warum)
    if not ok:
        return {**leer, "nachweis": text_nachweis}
    return {"jahr": jahr, "kopftabelle": kopftabelle, "kopfsumme": kopfsumme,
            "abschnitte": abschnitte, "bestanden": True,
            "nachweis": text_nachweis}


def _lies_kopftabelle(zeilen: list[str]) -> tuple[list[dict], int | None]:
    """Das Gesamtinvestitionsprogramm — eine Zeile je Teilhaushalt."""
    start = next((i for i, z in enumerate(zeilen) if KOPFTABELLE in z), None)
    if start is None:
        return [], None
    zeilenmenge: list[dict] = []
    summe: int | None = None
    blob: list[str] = []
    for z in zeilen[start + 1:]:
        s = z.strip()
        if s.startswith(GESAMTSUMME):
            lauf = betragslauf(s[len(GESAMTSUMME):])
            summe = lauf[1] if lauf else None
            break
        if not s or MOEBEL.match(s):
            continue
        blob.append(s)
        if betragslauf(s) is not None:
            name, betrag = _name_und_betrag(blob)
            if name and betrag is not None:
                zeilenmenge.append({"bezeichnung": name, "gesamtsumme": betrag})
            blob = []
    return zeilenmenge, summe


def _lies_abschnitte(zeilen: list[str]) -> dict[int, dict]:
    """Je Teilhaushalt seine Maßnahmen und seine ausgewiesene Gesamtsumme."""
    abschnitte: dict[int, dict] = {}
    akt: int | None = None
    code: str | None = None
    blob: list[str] = []

    def schliessen() -> None:
        nonlocal code, blob
        if code and akt is not None:
            name, betrag = _name_und_betrag(blob)
            if betrag is not None:
                abschnitte[akt]["massnahmen"].append(
                    {"code": code, "bezeichnung": name, "gesamtsumme": betrag})
        code, blob = None, []

    for z in zeilen:
        s = z.strip()
        kopf = THH.match(s)
        if kopf:
            schliessen()
            akt = int(kopf.group(1))
            abschnitte.setdefault(
                akt, {"name": " ".join(kopf.group(2).split()),
                      "summe": None, "massnahmen": []})
            continue
        if s.startswith(GESAMTSUMME) and akt is not None:
            schliessen()
            lauf = betragslauf(s[len(GESAMTSUMME):])
            if lauf:
                abschnitte[akt]["summe"] = lauf[1]
            akt = None
            continue
        if akt is None:
            continue
        treffer = CODE.match(s)
        if treffer:
            schliessen()
            if treffer.group(2):
                continue           # Detailzeile — Falle 1
            code, blob = treffer.group(1), [s[treffer.end():]]
            continue
        if code:
            blob.append(s)         # umbrochener Name — Falle 2
    schliessen()
    return abschnitte


def probe_abschnitt(abschnitt: dict, toleranz: float = TOLERANZ_EUR
                    ) -> tuple[bool, str]:
    """Ergeben die Maßnahmen eines Teilhaushalts seine ``Gesamtsumme``?"""
    if abschnitt["summe"] is None:
        return False, f"„{GESAMTSUMME}“ fehlt"
    if len(abschnitt["massnahmen"]) < MINDEST_MASSNAHMEN:
        return False, (f"nur {len(abschnitt['massnahmen'])} Maßnahmen gelesen "
                       f"(mindestens {MINDEST_MASSNAHMEN} erwartet)")
    gerechnet = sum(m["gesamtsumme"] for m in abschnitt["massnahmen"])
    rest = gerechnet - abschnitt["summe"]
    if abs(rest) > toleranz:
        return False, (f"{len(abschnitt['massnahmen'])} Maßnahmen ergeben "
                       f"{_de(gerechnet)} €, der Abschnitt weist "
                       f"{_de(abschnitt['summe'])} € aus "
                       f"({_de(rest, vorzeichen=True)} €)")
    return True, ""


def probe_wiederholung(kopftabelle: list[dict], abschnitte: dict,
                       toleranz: float = TOLERANZ_EUR) -> tuple[bool, str]:
    """Steht jede Abschnitts-Gesamtsumme so auch in der Kopftabelle?

    Die stärkste der drei Proben: Kopftabelle und Abschnitt liegen rund
    siebzig Seiten auseinander und sind unabhängig gesetzt. Verglichen wird
    über den **Betrag**, nicht über den Namen — die Kopftabelle schreibt
    „Klima/Umwelt/Mobilität/Bau/Grün/Fri edh.", der Abschnittskopf
    „Klima/Umwelt/Mobilität/Bau/Grün/Friedh."; über den Namen verglichen
    scheiterte die Probe an einem Zeilenumbruch statt an einer Zahl."""
    kopf = [z["gesamtsumme"] for z in kopftabelle]
    for nr, a in sorted(abschnitte.items()):
        if a["summe"] is None:
            return False, f"THH{nr:02d} weist keine „{GESAMTSUMME}“ aus"
        if not any(abs(a["summe"] - k) <= toleranz for k in kopf):
            return False, (f"THH{nr:02d} weist {_de(a['summe'])} € aus, "
                           f"die Kopftabelle führt diesen Betrag nicht")
    return True, ""


def probe_kopftabelle(kopftabelle: list[dict], kopfsumme: int | None,
                      toleranz: float = TOLERANZ_EUR) -> tuple[bool, str]:
    """Ergeben die Zeilen der Kopftabelle ihre eigene ``Gesamtsumme``?"""
    if kopfsumme is None:
        return False, f"die Kopftabelle weist keine „{GESAMTSUMME}“ aus"
    if not kopftabelle:
        return False, "die Kopftabelle ist leer"
    gerechnet = sum(z["gesamtsumme"] for z in kopftabelle)
    rest = gerechnet - kopfsumme
    if abs(rest) > toleranz:
        return False, (f"die {len(kopftabelle)} Teilhaushalte ergeben "
                       f"{_de(gerechnet)} €, die Kopftabelle nennt "
                       f"{_de(kopfsumme)} € ({_de(rest, vorzeichen=True)} €)")
    return True, ""


def pruefe(kopftabelle: list[dict], kopfsumme: int | None,
           abschnitte: dict) -> tuple[bool, str]:
    """Alle drei Proben. Reißt eine, fällt der ganze Jahrgang."""
    if not abschnitte:
        return False, "kein Teilhaushalts-Abschnitt gefunden"
    for nr, a in sorted(abschnitte.items()):
        ok, warum = probe_abschnitt(a)
        if not ok:
            return False, f"THH{nr:02d}: {warum}"
    ok, warum = probe_wiederholung(kopftabelle, abschnitte)
    if not ok:
        return False, warum
    return probe_kopftabelle(kopftabelle, kopfsumme)


def nachweis(kopftabelle: list[dict], kopfsumme: int | None, abschnitte: dict,
             ok: bool, warum: str) -> str:
    """Ein Satz für den Beleg-Chip — in Zahlen, nicht in Namen."""
    if not ok:
        return f"Rechenprobe gerissen — {warum}"
    n = sum(len(a["massnahmen"]) for a in abschnitte.values())
    return (f"{n} Maßnahmen ergeben die Gesamtsumme ihres Teilhaushalts, alle "
            f"{len(abschnitte)} Teilhaushaltssummen stehen ein zweites Mal im "
            f"Gesamtinvestitionsprogramm, und dort ergeben sie "
            f"{_de(kopfsumme or 0)} € — Restbetrag 0,00 € auf jeder Ebene")


def massnahmen(gelesen: dict) -> list[dict]:
    """Die Maßnahmen eines gelesenen Jahrgangs, flach und mit Teilhaushalt.

    Reihenfolge: Teilhaushalt aufsteigend, darin wie im Dokument — die ist
    nicht alphabetisch, sondern nach IPSP-Element, und trägt damit die
    Gliederung der Verwaltung."""
    return [{"thh_nr": nr, "thh_name": a["name"], **m}
            for nr, a in sorted(gelesen.get("abschnitte", {}).items())
            for m in a["massnahmen"]]
