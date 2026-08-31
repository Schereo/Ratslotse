"""Der Stellenplan: wie viele Menschen hinter dem größten Ausgabenblock stehen.

Der Haushalts-Bereich zeigt bisher Euro. Personal ist der größte Posten darin,
und der Haushaltsplan trägt dafür eine eigene Anlage — den **Stellenplan**
(Nr. 21 bzw. 22 im Anlagenverzeichnis, § 5 GemHKVO). Er ist kein Text über
Personal, sondern eine Tabelle mit Summenzeilen, und deshalb überhaupt
verwendbar.

Was er sagt, und was nicht
--------------------------
Er zählt **Stellen**, keine Köpfe: Eine halbe Stelle steht als ``0,50``, zwei
Menschen in Teilzeit auf einer Stelle stehen als ``1,00``. Und er zählt nur
die Kernverwaltung („00100 Stadt Oldenburg") — Klinikum, Bäder, Bus und
Gebäudewirtschaft haben eigene Wirtschaftspläne und tauchen hier nicht auf.
Wer die Zahl neben die Konzernzahlen legt, legt zwei verschiedene Städte
nebeneinander.

Zwei Teile, zwei Tabellen
-------------------------
* **Teil A — Beamtinnen und Beamte.** Neun Spalten. Die Besetzung ist
  dreigeteilt: mit Beamt*innen, mit Tarifbeschäftigten (eine Beamtenstelle
  darf so besetzt werden) und nicht besetzt.
* **Teil B — Arbeitnehmerinnen und Arbeitnehmer.** Acht Spalten, die Besetzung
  ist eine Zahl.

Beide Tabellen schreiben ihre Spaltennummern als eigene Zeile unter den Kopf
(``1 2 3 4 5 6 7 8 9``). Das ist die **Spaltenprobe** und zugleich das
Eintrittsbillett: Ein Teil, dessen Nummernzeile fehlt oder eine andere Zahl
nennt, wird nicht gelesen. Ohne sie hinge die Bedeutung jeder Spalte an einer
Reihenfolge-Annahme — und die fällt erst auf, wenn eine Zahl schon auf der
Seite steht.

Die eigentliche Nachricht: die unbesetzten Stellen
--------------------------------------------------
Die Besetzungsspalten beziehen sich **nicht** auf das Haushaltsjahr, sondern
auf den Stichtag im Vorjahr („davon am 30.6.2025") — geplant wird vorwärts,
gezählt werden kann nur rückwärts. Sie gehören deshalb zur Vorjahresspalte und
werden auch gegen sie geprüft. Wer sie gegen die Planspalte rechnet, erfindet
eine Lücke, die es nicht gibt.

Was dort steht, erklärt eine Zeile im Jahresabschluss, die sonst wie ein
Erfolg aussieht: Bleiben die Personalaufwendungen unter dem Plan, hat die
Stadt nicht gespart, sondern niemanden gefunden. Die Zahl ist damit weder gut
noch schlecht, sondern erklärungsbedürftig — die Oberfläche zeigt sie deshalb
ohne Bewertungsfarbe.

Die Rechenproben
----------------
Das Dokument rechnet sich selbst vor. Genau das sind die Proben; nichts davon
ist unsere Plausibilitätsannahme:

1. **Spaltenprobe** (:func:`_spaltenzeile`) — die Tabelle nummeriert ihre
   Spalten selbst, auf jeder Seite neu, und nennt überall dieselbe Zahl. Sie
   ist das Eintrittsbillett: Ohne sie hinge die Bedeutung jeder Spalte an
   einer Reihenfolge-Annahme.
2. **Gruppensummen** (:func:`gruppenprobe`) — die Einzelzeilen zwischen zwei
   Summenzeilen ergeben die Summenzeile, in *jeder* Wertespalte („Summe
   Laufbahngruppe 2", „Summe Beschäftigte TVöD").
3. **Besetzungsprobe** (:func:`besetzungsprobe`) — besetzt + nicht besetzt =
   Stellen im Vorjahr, in jeder Summenzeile. Sie ist die Probe darauf, dass
   die Besetzungsspalten zur Vorjahres- und nicht zur Planspalte gehören.
4. **Gesamtsumme** (:func:`gesamtprobe`) — die Gruppensummen ergeben die
   Gesamtzeile, ebenfalls in jeder Spalte. Teil A führt sie zweimal („Summe
   Stadt Oldenburg" und noch einmal „Summe"); beide müssen stimmen.

Teil B trägt **keine** vierte Stufe: Er hat genau eine Gruppe, deren Summe
zugleich die Gesamtsumme ist. Eine Probe zu behaupten, die nur eine andere
wiederholt, wäre eine Probe zu viel — Teil B speichert deshalb drei
Probennamen, Teil A vier.

Gemessen an allen vier Jahrgängen gehen alle Summen auf **0,00 Stellen** auf.
Auf **Einzelzeilen** weicht die Besetzungsprobe um bis zu 0,01 ab, weil das
Dokument auf zwei Nachkommastellen rundet (``0,88 + 0,13 = 1,01`` bei einer
Stelle). :data:`TOLERANZ` gibt dafür 0,05 — das Fünffache der größten
gemessenen Rundungsabweichung und immer noch weniger als eine Zwanzigstelstelle.

Zwei Zeilen im Bestand widersprechen sich darüber hinaus um eine ganze Stelle
(Stellenplan 2023, Teil B). Sie werden gekennzeichnet statt verworfen; warum,
steht bei :func:`besetzungsprobe`.

Was hier nicht gelesen wird
---------------------------
* **Die „Aufteilung nach der Verwaltungsgliederung"** (Teil A je Amt, 15
  Besoldungsspalten quer). Sie ließe sich lesen, beantwortet aber eine andere
  Frage („welches Amt hat wie viele A-13-Stellen?") und trägt im Textextrakt
  keine eigene Rechenprobe je Zeile.
* **„Dienstkräfte in der Ausbildungszeit"** — Auszubildende, Anwärter*innen
  und Freiwilligendienste. Diese Tabelle hat sechs Spalten, keine
  Besetzungsangabe und keine Summenzeile im Textextrakt. Sie steht in
  denselben Dokumenten, und ihre Zeilen sähen einer Stellenzeile ähnlich
  genug — die Spaltenprobe hält sie draußen, und die Regel „was keine
  Summenzeile deckt, wird nicht gespeichert" fängt den Rest.

Welche Jahrgänge es überhaupt gibt
-----------------------------------
Erst ab dem Haushaltsplan **2023** hängt der Stellenplan als eigene Anlage an
der Einbringungs-Vorlage; die Pläne 2019–2022 enden im Anlagenverzeichnis bei
„021 Wirtschaftsplan EGH". Für 2020 liegt zwar ein „Geänderter Stellenplan
Teil B" aus einer späteren Vorlage vor, der seine Proben sogar besteht — er
bleibt trotzdem draußen: Er ist eine *Änderung* des Plans statt der
eingebrachte Plan, und er trägt nur Teil B. Ein Jahr, das nur die Tarifhälfte
zeigt, läse sich wie ein Jahr ohne Beamtenstellen.

Wie beim Gesamtergebnishaushalt gilt: Es ist der **Verwaltungsentwurf**. Was
der Rat in den Beratungen daran ändert, steht nicht darin; die Herkunft sagt
das über ``stand``.
"""
from __future__ import annotations

import re

#: Wie viele Wertespalten ein Teil trägt und was sie bedeuten — die einzige
#: Stelle, an der die Zuordnung steht. Der Schlüssel ist die **vom Dokument
#: selbst genannte** Spaltenzahl (die Nummernzeile unter dem Kopf), nicht eine
#: Position, die wir uns merken.
#:
#: Teil A (9 Spalten): Lfd.Nr. · Amtsbezeichnung · Bes.-Gruppe · Stellen im
#: Haushaltsjahr · Stellen im Vorjahr · besetzt mit Beamt*innen · besetzt mit
#: Arbeitnehmer*innen · nicht besetzt · Vermerke.
#: Teil B (8 Spalten): dasselbe ohne die Aufteilung der Besetzung.
LAYOUT: dict[int, tuple[str, ...]] = {
    9: ("positions_planned", "positions_prior_year", "filled_by_officials",
        "filled_by_employees", "vacant"),
    8: ("positions_planned", "positions_prior_year", "filled", "vacant"),
}

#: Welcher Teil welche Spaltenzahl haben muss. Ein Teil A mit acht Spalten ist
#: kein Teil A mit einer Spalte weniger, sondern ein anderes Dokument.
TEIL_SPALTEN: dict[str, int] = {"A": 9, "B": 8}

#: Alle Zahlenfelder, die eine gespeicherte Zeile tragen kann — in fester
#: Reihenfolge, damit Summen und Spaltenvergleiche reproduzierbar sind.
#: ``filled`` ist die einzige Angabe, die nicht in der Tabelle steht: In
#: Teil B ist sie die Besetzungsspalte selbst, in Teil A die Summe der beiden
#: Besetzungsarten. Sie ist damit die einzige Zahl, die **wir** rechnen — und
#: sie ist es wert, weil sonst jede Auswertung beide Teile verschieden
#: behandeln müsste.
ALLE_WERTFELDER: tuple[str, ...] = (
    "positions_planned", "positions_prior_year", "filled_by_officials",
    "filled_by_employees", "filled", "vacant")

#: Wie die Teile für Leser*innen heißen. „Tarifbeschäftigte" ist das Wort, das
#: die Oberfläche benutzt; das Dokument selbst schreibt „Arbeitnehmerinnen und
#: Arbeitnehmer", und beim Namen der Fundstelle bleibt es dabei.
TEIL_NAMEN: dict[str, str] = {
    "A": "Beamtinnen und Beamte",
    "B": "Arbeitnehmerinnen und Arbeitnehmer",
}

#: Rundungstoleranz in Stellen. Begründung und Messwerte im Modulkopf.
TOLERANZ = 0.05

#: Ein Betrag der Tabelle: immer zwei Nachkommastellen, gelegentlich negativ
#: (ist eine Gruppe überbesetzt, steht bei „nicht besetzt" ein Minus).
_WERT = r"-?\d{1,4},\d\d"

#: „Teil A:" / „Teil B:" — der Kopf jeder Tabellenseite. Die Aufteilung nach
#: der Verwaltungsgliederung heißt ebenfalls „Teil A: …" und ist ausgenommen.
_TEIL = re.compile(r"Teil\s+([AB]):")

#: Für welches Jahr geplant wird, und auf welchen Tag sich die Besetzung
#: bezieht. Beide stehen im Tabellenkopf jeder Seite.
_HAUSHALTSJAHR = re.compile(r"Haushaltsjahr\s+(20\d\d)")
_STICHTAG = re.compile(r"davon\s+am\s+(\d{1,2})\.(\d{1,2})\.(20\d\d)")

#: Die Bes.-Gruppe am Ende der Bezeichnung — „A 13", „B 8" (Teil A) bzw. „15",
#: „S 08 a", „09 b" (Teil B). Trifft sie nicht, bleibt sie leer und die
#: Bezeichnung behält den Text: geraten wird nichts.
_GRUPPE_A = re.compile(r"\s([AB]\s*\d{1,2})$")
_GRUPPE_B = re.compile(r"\s((?:S\s*)?\d{1,2}(?:\s*[a-z])?)$")

#: Beginnt hier eine neue Zeile der Tabelle? Eine laufende Nummer, dann ein
#: Zwischenraum. Ein umgebrochener Vermerk („2,00* KW nach Ende …") beginnt
#: mit einer Zahl UND einem Komma und fällt deshalb nicht darunter.
_NEUE_ZEILE = re.compile(r"^\d{1,3}\s")

#: Eine Summenzeile. Was hinter „Summe" steht, ist der Name der Gruppe —
#: leer bei der Gesamtzeile, die nur „Summe" heißt.
_SUMME = re.compile(r"^Summe\b")

#: Textstellen, an denen ein Teil sicher zu Ende ist. Sie stehen als
#: Überschrift einer anderen Tabelle im selben PDF; ohne diesen Schnitt liefe
#: der Zeilenleser in die Ausbildungs-Tabelle weiter. (Zweiter Schutz: Was
#: keine Summenzeile deckt, wird ohnehin verworfen.)
_ENDE = ("Dienstkräfte in der Ausbildungszeit", "Übersicht zum Stellenplan",
         "Aufteilung nach der Verwaltungsgliederung")

#: Glyphen statt Buchstaben: Trägt ein PDF keine Zeichenzuordnung, gibt pypdf
#: die Glyphen-Nummern aus („/0 /1 /2 /3"). Im Stellenplan 2026 betrifft das
#: genau die Seiten von Teil B — er ist dort nicht lesbar, und das ist etwas
#: anderes als „gibt es nicht".
_GLYPHEN = re.compile(r"(?:/(?:\d{1,3}|i\d{1,3})\s*){12,}")


def _wert(s: str) -> float:
    return float(s.replace(".", "").replace(",", "."))


def _spaltenzeile(zeile: str) -> int | None:
    """Die Nummernzeile unter dem Tabellenkopf → wie viele Spalten die Tabelle
    hat, sonst ``None``.

    Verglichen wird die Ziffernfolge ohne Zwischenräume: Im Stellenplan 2026
    klebt pypdf die ersten beiden Nummern zusammen („12 3 4 5 6"), und eine
    Regex über die Zwischenräume hielte diese Zeile für Daten."""
    ziffern = re.sub(r"\s+", "", zeile)
    if not ziffern.isdigit() or len(ziffern) < 4:
        return None
    return len(ziffern) if ziffern == "123456789"[:len(ziffern)] else None


def _zeilenregex(spalten: int) -> re.Pattern:
    n = len(LAYOUT[spalten])
    return re.compile(r"^(\d{1,3})\s+(.+?)\s+" + r"\s+".join([f"({_WERT})"] * n)
                      + r"(?:\s|$)")


def _summenregex(spalten: int) -> re.Pattern:
    n = len(LAYOUT[spalten])
    return re.compile(r"^Summe\b\s*(.*?)\s*" + r"\s+".join([f"({_WERT})"] * n)
                      + r"\s*$")


def _werte(spalten: int, roh: tuple) -> dict:
    """Die gelesenen Zahlen unter ihre Namen — plus ``filled`` als Summe der
    Besetzungsarten, damit beide Teile dieselbe Frage gleich beantworten."""
    field = dict(zip(LAYOUT[spalten], (_wert(g) for g in roh)))
    if "filled" not in field:
        field["filled"] = field["filled_by_officials"] + field["filled_by_employees"]
    return field


def _bezeichnung(text: str, part: str) -> tuple[str, str | None]:
    """Amts-/Funktionsbezeichnung und Besoldungs- bzw. Entgeltgruppe trennen.

    Trifft das Muster nicht, bleibt die Gruppe leer und der ganze Text steht
    als Bezeichnung — eine halb geratene Besoldungsgruppe wäre schlechter als
    keine."""
    text = re.sub(r"\s+", " ", text).strip()
    m = (_GRUPPE_A if part == "A" else _GRUPPE_B).search(text)
    if not m:
        return text, None
    return text[:m.start()].strip(), re.sub(r"\s+", " ", m.group(1)).strip()


def _kopfangaben(kopf: str) -> tuple[int | None, str | None]:
    """Haushaltsjahr und Stichtag der Besetzung aus einem Tabellenkopf."""
    j = _HAUSHALTSJAHR.search(kopf)
    s = _STICHTAG.search(kopf)
    return (int(j.group(1)) if j else None,
            f"{s.group(3)}-{int(s.group(2)):02d}-{int(s.group(1)):02d}" if s else None)


def budget_year(text: str | None) -> int | None:
    """Für welches Haushaltsjahr dieser Stellenplan gilt.

    Aus dem **Tabellenkopf**, nicht aus dem Label: Die vier Dokumente heißen
    „022 2023 Stellenplan", „2024 021 IVw Stellenplan", „2025 022 Vw
    Stellenplan Haushalt 2025 Verwaltungsentwurf" — drei Schreibweisen, und
    die von 2024 trägt zwei Jahreszahlen an verschiedenen Stellen. Der Kopf
    sagt es einmal und eindeutig."""
    year, _ = _kopfangaben((text or "")[:4000])
    return year


def _teile_lesen(text: str) -> dict[str, dict]:
    """Rohe Zeilen und Summenzeilen je Teil — ohne jede Prüfung.

    Ein Zustandsautomat statt eines Regex-Laufs über den ganzen Text: Der Kopf
    wiederholt sich auf jeder Seite, Bezeichnungen brechen über zwei Zeilen um
    („Lebensmittelkontrollamtsinspektor/-in ⏎ mit AZ ⏎ A 09 …"), und Vermerke
    laufen hinter den Zahlen noch eine Zeile weiter. Wer das flach zieht,
    verliert die Grenze zwischen zwei Datensätzen."""
    teile: dict[str, dict] = {}
    part: str | None = None
    im_kopf = False
    kopf: list[str] = []
    puffer = ""

    for roh in text.split("\n"):
        z = roh.strip()
        if not z:
            continue

        m = _TEIL.search(z)
        if m and "Aufteilung" not in z:
            part = m.group(1)
            teile.setdefault(part, {"zeilen": [], "summen": [], "spalten": None,
                                    "years": set(), "stichtage": set(),
                                    "spaltenstreit": set(), "unlesbar": []})
            im_kopf, kopf, puffer = True, [z], ""
            continue
        if part is None:
            continue
        t = teile[part]

        if im_kopf:
            kopf.append(z)
            spalten = _spaltenzeile(z)
            if spalten is None:
                continue
            # Der Kopf ist zu Ende: Was er über Jahr, Stichtag und Spaltenzahl
            # sagt, wird eingesammelt. Er steht auf jeder Seite noch einmal —
            # widerspricht er sich, fällt das hier auf und nicht später.
            year, as_of_date = _kopfangaben(" ".join(kopf))
            if year:
                t["years"].add(year)
            if as_of_date:
                t["stichtage"].add(as_of_date)
            if t["spalten"] is None:
                t["spalten"] = spalten
            elif t["spalten"] != spalten:
                t["spaltenstreit"].add(spalten)
            im_kopf = False
            continue

        if any(e in z for e in _ENDE):
            part, puffer = None, ""
            continue
        if t["spalten"] not in LAYOUT:
            continue
        # Eine Nummernzeile mit anderer Spaltenzahl: Hier beginnt eine andere
        # Tabelle (die Ausbildungs-Übersicht hat sechs Spalten).
        andere = _spaltenzeile(z)
        if andere is not None and andere != t["spalten"]:
            part, puffer = None, ""
            continue

        if _SUMME.match(z):
            puffer = ""
            m = _summenregex(t["spalten"]).match(z)
            if m:
                t["summen"].append({"name": m.group(1).strip(),
                                    "werte": _werte(t["spalten"], m.groups()[1:]),
                                    "bis": len(t["zeilen"])})
            else:
                t["unlesbar"].append(z)
            continue

        if _NEUE_ZEILE.match(z):
            puffer = z
        elif puffer:
            puffer = f"{puffer} {z}"
        else:
            continue
        m = _zeilenregex(t["spalten"]).match(puffer)
        if not m:
            continue
        bez, gruppe = _bezeichnung(m.group(2), part)
        t["zeilen"].append({"seq_no": int(m.group(1)), "label": bez,
                            "pay_grade": gruppe,
                            **_werte(t["spalten"], m.groups()[2:])})
        puffer = ""

    return teile


def _besetzungsrest(satz: dict) -> float:
    """besetzt + nicht besetzt − Stellen im Vorjahr."""
    return satz["filled"] + satz["vacant"] - satz["positions_prior_year"]


def besetzungstoleranz(zeilen: int) -> float:
    """Wie weit eine **Summenzeile** bei der Besetzungsprobe abweichen darf.

    Anders als die Spaltenvergleiche hat diese Probe eine Toleranz, die mit
    der Zahl der Zeilen wächst — und das ist keine Nachgiebigkeit, sondern
    eine Ableitung. Der Plan gibt jede Zeile auf zwei Nachkommastellen an;
    eine halbe Stelle im Schichtdienst steht als ``0,88`` und ``0,13`` statt
    ``0,875`` und ``0,125``. Je Zeile bleibt dabei höchstens **0,01** übrig
    (gemessen: nie mehr), und diese Reste addieren sich in die Summenzeile.

    Ein fester Wert wäre deshalb genau falsch herum streng: Er ginge bei einer
    Tabelle mit vier Zeilen durch und schlüge bei einer mit 143 zu — obwohl
    die zweite nichts falscher macht, sondern nur mehr davon. Gemessen sind
    es im schlechtesten Fall 8 gerundete Zeilen und damit 0,08 Stellen auf
    1.486; die Schranke lässt hier 1,43 zu.

    Was die Probe trotzdem fängt, ist ihr eigentlicher Zweck: Läse man die
    Besetzung gegen die Planspalte statt gegen die Vorjahresspalte, läge sie
    um 19 bis 41 Stellen daneben — eine Größenordnung über jeder Rundung."""
    return max(TOLERANZ, 0.01 * zeilen)


def besetzungsprobe(summen: list[dict]) -> tuple[bool, str]:
    """Die Besetzung geht in jeder **Summenzeile** auf: besetzt + nicht besetzt
    = Stellen im Vorjahr.

    Die Besetzungsspalten gehören zur **Vorjahres**-Spalte, nicht zur
    Planspalte (Modulkopf). Genau das prüft diese Probe mit: Ginge sie gegen
    das Haushaltsjahr auf, hätten wir die falsche Spalte gelesen.

    Geprüft wird sie auf den Summenzeilen, nicht als Gate auf jeder
    Einzelzeile — und das hat einen gemessenen Grund. Der Stellenplan 2023
    widerspricht sich in Teil B in genau zwei Zeilen: Bei „Dipl.-Ingenieur/-in
    E 11" ist die Besetzung um eine Stelle zu hoch, bei „Verw.-Angest. E 11"
    um eine zu niedrig — die Stadt hat eine Stelle in der falschen Zeile
    verbucht. In der Gruppensumme heben sich beide auf, und alle vier Spalten
    der Summenzeile stimmen auf 0,00.

    Als Gate über jede Einzelzeile fiele dafür ein ganzer Teil mit 140 Zeilen
    und 1.643 Stellen — wegen eines Übertrags, den das Dokument an anderer
    Stelle selbst wieder geraderückt. Die abweichenden Zeilen werden deshalb
    **markiert und gezählt** (:func:`unstimmige_zeilen`, Spalte ``consistent``),
    nicht verworfen: Gespeichert steht dort, was im Plan steht.

    Was ein Gate auf Einzelzeilen abfangen sollte — eine verrutschte Spalte —
    fangen die Spaltenvergleiche ohnehin ab: Sie prüfen jede Spalte einzeln,
    und eine verschobene Spalte reißt sie sofort.

    Erwartet je Eintrag die Summenwerte plus ``name`` und ``zeilen`` (wie
    viele Einzelzeilen darunterstehen — daraus kommt die Toleranz)."""
    if not summen:
        return False, "keine Summenzeile gelesen"
    for s in summen:
        rest = _besetzungsrest(s)
        toleranz = besetzungstoleranz(s["zeilen"])
        if abs(rest) > toleranz:
            return False, (f"„{s.get('name') or 'Summe'}“: besetzt "
                           f"{s['filled']:.2f} + nicht besetzt "
                           f"{s['vacant']:.2f} ergeben nicht die "
                           f"{s['positions_prior_year']:.2f} Stellen des Vorjahres "
                           f"({rest:+.2f}, erlaubt sind {toleranz:.2f} bei "
                           f"{s['zeilen']} Zeilen)")
    return True, ""


def unstimmige_zeilen(zeilen: list[dict],
                      toleranz: float = TOLERANZ) -> list[dict]:
    """Einzelzeilen, in denen sich das Dokument selbst widerspricht.

    Über alle vier Jahrgänge sind das zwei Zeilen (Stellenplan 2023, Teil B).
    Steigt die Zahl, hat sich am Dokument etwas geändert — dann gehört es
    angesehen, nicht die Toleranz erhöht."""
    return [z for z in zeilen if abs(_besetzungsrest(z)) > toleranz]


def _summenvergleich(gerechnet: dict, genannt: dict, wo: str,
                     toleranz: float) -> str:
    """Zwei Wertesätze spaltenweise vergleichen → Fehlertext oder ``""``."""
    for field, wert in genannt.items():
        rest = gerechnet.get(field, 0.0) - wert
        if abs(rest) > toleranz:
            return (f"{wo}: {field} ergibt {gerechnet.get(field, 0.0):.2f}, "
                    f"die Summenzeile nennt {wert:.2f} ({rest:+.2f})")
    return ""


def _addieren(saetze: list[dict], felder: tuple[str, ...]) -> dict:
    return {f: sum(s[f] for s in saetze) for f in felder}


def _wertfelder(satz: dict) -> tuple[str, ...]:
    """Welche Felder eines Satzes Zahlen sind — die Spalten dieses Teils.

    Aus dem Satz selbst und nicht aus einer festen Liste: Ein Teil A trägt
    fünf Wertespalten, ein Teil B vier, und beide führen zusätzlich das
    gerechnete ``filled``. Wer hier eine feste Liste nähme, addierte bei
    Teil B irgendwann eine Spalte, die es dort nicht gibt."""
    return tuple(f for f in ALLE_WERTFELDER if f in satz)


def gruppenprobe(gruppen: list[dict], toleranz: float = TOLERANZ) -> tuple[bool, str]:
    """Stufe 2: Die Einzelzeilen einer Gruppe ergeben ihre Summenzeile.

    In *jeder* Wertespalte, nicht nur in der Planspalte — eine verrutschte
    Spalte ginge sonst durch, solange die erste stimmt."""
    if not gruppen:
        return False, "keine Summenzeile gefunden"
    for g in gruppen:
        if not g["zeilen"]:
            return False, f"Gruppe „{g['name']}“ hat keine Einzelzeilen"
        felder = _wertfelder(g["summe"])
        warum = _summenvergleich(_addieren(g["zeilen"], felder), g["summe"],
                                 f"Gruppe „{g['name']}“", toleranz)
        if warum:
            return False, warum
    return True, ""


def gesamtprobe(gruppen: list[dict], gesamt: list[dict],
                toleranz: float = TOLERANZ) -> tuple[bool, str]:
    """Stufe 3: Die Gruppensummen ergeben die Gesamtzeile des Teils.

    Teil A führt sie zweimal („Summe Stadt Oldenburg" und noch einmal
    „Summe"); geprüft werden beide. Teil B hat keine — dort gibt es nur eine
    Gruppe, deren Summe die Gesamtsumme ist, und diese Stufe entfällt (sie
    wiederholte sonst Stufe 2 unter neuem Namen)."""
    if not gesamt:
        return False, "keine Gesamtzeile im Dokument"
    if not gruppen:
        return False, "Gesamtzeile ohne Gruppensummen"
    summen = [g["summe"] for g in gruppen]
    gerechnet = _addieren(summen, _wertfelder(summen[0]))
    for g in gesamt:
        warum = _summenvergleich(gerechnet, g["werte"],
                                 f"Gesamtzeile „Summe {g['name']}“".replace(
                                     " „Summe “", " „Summe“"), toleranz)
        if warum:
            return False, warum
    return True, ""


def _gliedern(t: dict) -> tuple[list[dict], list[dict], int]:
    """Rohzeilen in Gruppen schneiden — an den Summenzeilen des Dokuments.

    Gibt ``(gruppen, gesamtzeilen, ungedeckt)`` zurück. **Ungedeckt** sind
    Zeilen hinter der letzten Summenzeile: Sie stehen unter keiner Probe und
    werden verworfen, nicht gespeichert. In der Praxis sind das die ersten
    Zeilen der Ausbildungs-Tabelle, wenn deren Nummernzeile im Textextrakt
    verunglückt ist."""
    gruppen: list[dict] = []
    gesamt: list[dict] = []
    vorher = 0
    for s in t["summen"]:
        block = t["zeilen"][vorher:s["bis"]]
        if block:
            gruppen.append({"name": s["name"], "zeilen": block, "summe": s["werte"]})
            vorher = s["bis"]
        else:
            # Eine Summenzeile ohne eigene Zeilen fasst zusammen, was schon
            # zusammengefasst ist — das ist die Gesamtzeile des Teils.
            gesamt.append(s)
    return gruppen, gesamt, len(t["zeilen"]) - vorher


def _zeilen_bauen(gruppen: list[dict], gesamt: list[dict],
                  unstimmig: list[dict]) -> list[dict]:
    """Was gespeichert wird: Einzelposten, Gruppensummen, Gesamtsumme.

    Die Summenzeilen kommen **aus dem Dokument** in die Tabelle statt aus
    unserer Addition. Auf der Seite steht damit die Zahl, die die Stadt
    ausweist, und nicht eine, die wir nachgerechnet haben — auch wenn beide
    (nachgemessen) identisch sind.

    ``consistent`` sagt je Zeile, ob dort besetzt + nicht besetzt die Stellen des
    Vorjahres ergeben. ``0`` heißt nicht „falsch gelesen", sondern „so steht
    es im Plan, und dort geht es nicht auf" (s. :func:`besetzungsprobe`)."""
    schief = {id(z) for z in unstimmig}
    aus: list[dict] = []
    for g in gruppen:
        for z in g["zeilen"]:
            aus.append({"art": "posten", "gruppe": g["name"],
                        "consistent": 0 if id(z) in schief else 1, **z})
        aus.append({"art": "gruppe", "gruppe": g["name"], "seq_no": None,
                    "label": f"Summe {g['name']}", "pay_grade": None,
                    "consistent": 1, **g["summe"]})
    # Führt ein Teil die Gesamtzeile zweimal, wird sie einmal gespeichert:
    # Die zweite ist die Probe, nicht ein zweiter Wert.
    if gesamt:
        aus.append({"art": "gesamt", "gruppe": None, "seq_no": None,
                    "label": "Summe", "pay_grade": None, "consistent": 1,
                    **gesamt[0]["werte"]})
    elif len(gruppen) == 1:
        aus.append({"art": "gesamt", "gruppe": None, "seq_no": None,
                    "label": "Summe", "pay_grade": None, "consistent": 1,
                    **gruppen[0]["summe"]})
    return aus


def lies(text: str) -> dict:
    """Einen Stellenplan auswerten.

    Liefert ``{budget_year, teile, glyphen}``. ``teile`` ist eine Liste — je Teil
    ein dict mit ``part`` (``A``/``B``), ``as_of_date``, ``zeilen``, ``probes``,
    ``bestanden``, ``nachweis`` und ``verworfen``. Ein Teil, dessen Proben
    nicht aufgehen, hat **keine** ``zeilen``: Eine Tabelle, die sich nicht
    selbst bestätigt, gibt keine halben Zahlen her.

    ``glyphen`` sagt, ob im Dokument Seiten stehen, die statt Buchstaben
    Glyphen-Nummern liefern. Das ist der Unterschied zwischen „Teil B gibt es
    in diesem Jahrgang nicht" und „Teil B ist in diesem PDF nicht lesbar" —
    ohne diese Angabe stünde beides gleich da."""
    roh = _teile_lesen(text)
    result: list[dict] = []
    years: set[int] = set()

    for name in sorted(roh):
        t = roh[name]
        soll = TEIL_SPALTEN[name]
        probes: list[dict] = []
        verworfen = 0

        if t["spalten"] != soll or t["spaltenstreit"]:
            gesehen = sorted({t["spalten"], *t["spaltenstreit"]} - {None})
            result.append({
                "part": name, "as_of_date": None, "year": None, "zeilen": [],
                "probes": [], "bestanden": False, "verworfen": len(t["zeilen"]),
                "nachweis": f"Teil {name} nennt {gesehen or 'keine'} Spalten "
                            f"statt {soll} — nicht gelesen"})
            continue
        if len(t["years"]) != 1 or len(t["stichtage"]) > 1:
            result.append({
                "part": name, "as_of_date": None, "year": None, "zeilen": [],
                "probes": [], "bestanden": False, "verworfen": len(t["zeilen"]),
                "nachweis": f"Teil {name}: der Tabellenkopf nennt "
                            f"{sorted(t['years']) or 'kein'} Haushaltsjahr und "
                            f"{sorted(t['stichtage']) or 'keinen'} Stichtag"})
            continue

        gruppen, gesamt, ungedeckt = _gliedern(t)
        verworfen += ungedeckt + len(t["unlesbar"])
        einzeln = [z for g in gruppen for z in g["zeilen"]]
        # Je Summenzeile auch, über wie vielen Einzelzeilen sie steht — die
        # Besetzungsprobe leitet ihre Toleranz daraus ab.
        alle_summen = (
            [{**g["summe"], "name": g["name"], "zeilen": len(g["zeilen"])}
             for g in gruppen]
            + [{**g["werte"], "name": g["name"], "zeilen": len(einzeln)}
               for g in gesamt])

        # Die Spaltenprobe ist an dieser Stelle schon bestanden (sonst wären
        # wir oben ausgestiegen) — sie steht trotzdem in der Liste, weil sie
        # die Aussage trägt, dass die Spalten bedeuten, was wir ihnen
        # zuschreiben. Eine bestandene Probe zu verschweigen, weil sie ein
        # Vorfilter ist, hieße den Beleg um sein Fundament zu kürzen.
        probes.append({"probe": "stellenplan_spaltenprobe", "ok": True,
                       "warum": ""})
        for name_probe, result_probe in (
            ("stellenplan_gruppensummen", gruppenprobe(gruppen)),
            ("stellenplan_besetzung", besetzungsprobe(alle_summen)),
            # Die dritte Stufe nur, wo das Dokument eine eigene Gesamtzeile
            # führt (Teil A). Teil B hat eine Gruppe, deren Summe zugleich die
            # Gesamtsumme ist — dort wiederholte sie bloß die zweite Stufe.
            *((("stellenplan_gesamtsumme", gesamtprobe(gruppen, gesamt)),)
              if gesamt else ()),
        ):
            probes.append({"probe": name_probe, "ok": result_probe[0],
                           "warum": result_probe[1]})

        bestanden = all(p["ok"] for p in probes)
        unstimmig = unstimmige_zeilen(einzeln)
        year = next(iter(t["years"]))
        if bestanden:
            years.add(year)
        result.append({
            "part": name, "year": year,
            "as_of_date": next(iter(t["stichtage"]), None),
            "zeilen": (_zeilen_bauen(gruppen, gesamt, unstimmig)
                       if bestanden else []),
            "probes": probes, "bestanden": bestanden, "verworfen": verworfen,
            "unstimmig": [{"seq_no": z["seq_no"], "label": z["label"],
                           "deviation": round(_besetzungsrest(z), 2)}
                          for z in unstimmig],
            "nachweis": nachweis(gruppen, gesamt, einzeln, unstimmig, probes)})

    return {"budget_year": budget_year(text), "teile": result,
            "glyphen": bool(_GLYPHEN.search(text or "")),
            "years": sorted(years)}


def nachweis(gruppen: list[dict], gesamt: list[dict], zeilen: list[dict],
             unstimmig: list[dict], probes: list[dict]) -> str:
    """Ein Satz für den Beleg-Chip: was gerechnet wurde und wie es ausging.

    In Zahlen statt in Probennamen — „140 Zeilen unter 1 Gruppensumme" ist
    nachvollziehbar, „gruppenprobe ok" nicht."""
    gerissen = [p["warum"] for p in probes if not p["ok"]]
    if gerissen:
        return "; ".join(gerissen)
    stufen = (f"{len(zeilen)} Zeilen unter {len(gruppen)} Gruppensumme"
              f"{'n' if len(gruppen) != 1 else ''}")
    if gesamt:
        stufen += f" und {len(gesamt)} Gesamtzeile{'n' if len(gesamt) != 1 else ''}"
    satz = f"{stufen}, alle Spalten aufgegangen (Toleranz {TOLERANZ:.2f} Stellen)"
    if unstimmig:
        satz += (f" · {len(unstimmig)} Zeile"
                 f"{'n' if len(unstimmig) != 1 else ''}, in "
                 f"{'denen' if len(unstimmig) != 1 else 'der'} sich der Plan "
                 f"selbst widerspricht, {'sind' if len(unstimmig) != 1 else 'ist'} "
                 f"als solche gekennzeichnet")
    return satz
