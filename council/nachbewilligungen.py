"""Was der Rat nachbewilligt hat, nachdem der Haushalt beschlossen war.

§ 117 NKomVG verlangt für jede Ausgabe, die im beschlossenen Haushalt nicht
oder nicht in dieser Höhe steht, eine eigene Bewilligung. Im
Ratsinformationssystem sind das seit 2018 lückenlos **161 Vorlagen**, und der
Betrag steht meistens schon im Titel:

    18/0258  Überplanmäßige Bewilligung in Höhe von 250.000 EUR für den
             Teilhaushalt 04
    23/0617  Überplanmäßige Bewilligung für Mehraufwendungen in Höhe von
             11.716.000 Euro …

Ein Wort zur Einordnung, das auf jede Seite gehört, die diese Zahlen zeigt:
**„außerplanmäßig" heißt gedeckt-aber-umgewidmet, nicht ungedeckt.** Jede
dieser Vorlagen nennt in ihrem Beschlussvorschlag, woher das Geld kommt
(„Zur Deckung stehen Minderauszahlungen bei … zur Verfügung"). Tarifabschlüsse
und Baukostensteigerungen sind der Normalfall, nicht der Ausnahmefall — eine
Nachbewilligung ist kein Skandal.

Zwei Quellen, zwei verschiedene Fragen
---------------------------------------
Diese Datei liest **zwei** Bestände, und es ist wichtig, sie nicht zu
verwechseln:

1. :func:`aus_vorlagen` — **die Rats-Serie aus dem RIS.** Was der Rat
   beschlossen hat, Vorlage für Vorlage, mit Link auf die Beschluss-Seite.
   Reicht von 2018 bis heute.
2. :func:`kapitel3` — **der Rechenschaftsbericht, Kapitel 3.** Nach § 128
   NKomVG legt die Stadt ihn jedem Jahresabschluss bei; sein Kapitel 3 heißt
   „Über- und außerplanmäßige Aufwendungen und Auszahlungen" und zählt **vier
   Entscheidungskanäle** — Rat, Oberbürgermeister, Fachdienst 200 per
   Haushaltsvermerk, Eilentscheidungen. Vorhanden für 2022, 2023, 2024.

Der Grund, warum beides gebraucht wird, steht in den Zahlen des zweiten
Bestands: Die Gesamtsumme stieg von 26,97 (2022) über 40,24 (2023) auf
**57,49 Mio. €** (2024), der Anteil mit Ratsbeschluss fiel von 88 auf **73 %**.
Wer nur die Ratsbeschlüsse zeigt, zeigt eine schrumpfende Teilmenge, als wäre
sie das Ganze.

Die zweistufige Extraktion
---------------------------
Stufe 1 ist der Titel (:data:`_TITEL_BETRAG`), Stufe 2 der
Beschlussvorschlag der Vorlage (:func:`_betrag_aus_vorschlag`). Gemessen am
Bestand vom 18.08.2026:

* 145 von 152 Einzelvorlagen tragen ihren Betrag im Titel — **95,4 %**.
* Die restlichen 7 schließt der Beschlussvorschlag **vollständig**: 23/0258,
  23/0811, 23/0893, 24/0520, 24/0834, 24/0836, 25/0606. Zweistufig also
  **152 von 152**.

Zwei der sieben schreiben nicht „in Höhe von", sondern „eine Mehrauszahlung
**von** 7,3 Millionen Euro" — das Muster braucht beide Wege.

**Die Deckungsvorschlags-Falle.** Der Beschlussvorschlag nennt nach der
Bewilligung fast immer die Deckung, und zwar mit demselben Wortlaut: „Zur
Deckung stehen Minderauszahlungen **in Höhe von** 105.000 Euro … zur
Verfügung". Wer hier den größten Betrag nimmt (so macht es ``council/money.py``
für den Grobwert einer Beschlusszeile), nimmt bei einer nur teilweise
gedeckten Bewilligung den falschen. Deshalb wird der Block **vor** dem
Deckungssatz abgeschnitten (:data:`_DECKUNG`) und der **erste** Betrag
genommen, nicht der größte.

Woher der Beschlussvorschlag kommt
-----------------------------------
``council_vorlagen.beschlussvorschlag`` ist die richtige Spalte dafür — aber
im Bestand ist sie fast leer (7 von 5019 Zeilen, alle Jahrgang 2026): Gefüllt
wird sie erst seit ``council/ernte.py`` und nur beim Neu-Einlesen einer
Vorlage. Deshalb nimmt :func:`betrag` sie, **wenn** sie steht, und erntet
sonst aus ``raw_text`` mit derselben Funktion, die auch die Spalte füllt.
Damit hängt die Trefferquote nicht daran, wann eine Vorlage zuletzt geholt
wurde.

Drei Fallen, alle vermessen
----------------------------
1. **Verpflichtungsermächtigungen gehören nicht in die Summe.** Eine VE ist
   die Erlaubnis, künftige Jahre zu binden — kein Geld, das dieses Jahr
   fließt. Der Rechenschaftsbericht zählt sie ausdrücklich getrennt („Darüber
   hinaus wurden … sechs über- bzw. außerplanmäßige
   Verpflichtungsermächtigungen in Höhe von insgesamt 4.870.000,00 Euro
   bewilligt"). 19 Vorlagen im Bestand tragen sie im Titel; sie bekommen
   :data:`ART_VERPFLICHTUNG` und werden nie mitaddiert.
2. **Sitzungsdatum ≠ Haushaltsjahr.** Das Kapitel 3 des Berichts für 2022
   führt die Vorlage 23/0010, das für 2023 die 24/0029, das für 2024 die
   25/0002 — Januar-Vorlagen, die zum Vorjahr zählen. Maßgeblich ist deshalb
   der **Jahrgang der Vorlagen-Nummer**, nicht das Sitzungsdatum
   (:func:`haushaltsjahr`).
3. **Die Sammelberichte tragen Schwellenwerte, keine Beträge.** „Über- und
   außerplanmäßige Auszahlungen … **bis zu 50.000 Euro** in der Zeit vom
   01.01.2024 bis 31.12.2024" ist die Grenze, unter der der Rat gar nicht
   entscheidet — nicht die Summe dessen, was darunter anfiel. Neun solche
   Vorlagen im Bestand; sie bekommen :data:`ART_SCHWELLE` und **keinen**
   Betrag. (``council_decisions.amount_eur`` trägt für sie heute 50000; diese
   Datei fasst die Spalte nicht an, sie liest sie auch nicht.)

Die Zähleinheit ist die Vorlage, nicht die Beschlusszeile
----------------------------------------------------------
287 Beschlusszeilen stehen über nur 156 Vorlagen — **131 Dubletten**, weil
Finanzausschuss **und** Rat über dieselbe Vorlage abstimmen. Wer Zeilen
summiert, zählt fast jeden Betrag doppelt. Gezählt wird deshalb je Vorlage
einmal; die Beschlusszeilen bleiben als Belege daran hängen.

Was die Proben gezeigt haben
-----------------------------
* **Probe 1** (:func:`probe_volltext`, intern): Der Betrag aus dem Titel steht
  im Volltext derselben Vorlage noch einmal — **145 von 145**.
* **Probe 2** (:func:`probe_ratsabgleich`, extern und die harte): Der
  Rechenschaftsbericht nennt dieselben Fälle **mit Vorlagen-Nummern**. 2023
  und 2024 stimmt die Fallliste exakt (26/26 und 21/21). Gemessene
  Abweichungen der Summen: 2022 **+1,31 %**, 2023 **+100 €**
  (0,0003 %), 2024 **+2,19 %**. Die Ursachen stehen bei
  :func:`probe_ratsabgleich` und werden **benannt statt geglättet**.
* **Probe 3** (:func:`probe_tabelle`, im Dokument): Die Spalten des Kapitels
  addieren sich auf seine eigene Summenzeile, und beide Spalten zusammen auf
  die Gesamtsumme im Fließtext. **2024 geht auf den Cent auf. 2022 und 2023
  nicht** — und beide Male ist der Widerspruch echt, siehe dort.

Die Proben reißen absichtlich laut: Was sie finden, wird **angezeigt, nicht
repariert**.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from council import ernte, herkunft

#: Eine Bewilligung, die dieses Jahr Geld kostet — zählt in die Jahressumme.
ART_BEWILLIGUNG = "bewilligung"
#: Eine Verpflichtungsermächtigung — bindet künftige Jahre, zählt **nie** mit.
ART_VERPFLICHTUNG = "verpflichtungsermaechtigung"
#: Ein Sammelbericht über die Fälle unter der Wertgrenze. Der Betrag im Titel
#: ist die Grenze, nicht die Summe — deshalb trägt so eine Zeile keinen.
ART_SCHWELLE = "schwelle"

#: Die vier Wege, auf denen in Oldenburg eine Nachbewilligung zustande kommt.
#: Reihenfolge und Wortlaut stammen aus der Übersichtstabelle des
#: Rechenschaftsberichts; der Schlüssel ist unser Kürzel, der Wert das Label
#: der Stadt.
KANAELE: dict[str, str] = {
    "rat": "Beschluss des Rates",
    "oberbuergermeister": "Vom Oberbürgermeister entschieden",
    "fachdienst200": "Gemäß Haushaltsvermerk durch den Fachdienst 200",
    "eilentscheidung": "Eilentscheidungen",
}

_NUM = r"(?:\d{1,3}(?:\.\d{3})+|\d+)(?:,\d+)?"
# „EU" ist kein Tippfehler unsererseits: 19/0839 schreibt „341.000 EU".
_WAEHRUNG = r"(?:EURO|EUR|EU|Euro|€)"
_SKALA = r"(?:Mio\.?|Millionen|Million|Mrd\.?|Milliarden?)"

#: Stufe 1 — der Titel. „in Höhe von [insgesamt] 250.000 EUR", auch
#: „1 Million EUR", „450.000,00 €" und „99.000,- Euro".
_TITEL_BETRAG = re.compile(
    rf"in\s+H(?:ö|oe)he\s+von\s+(?:insgesamt\s+)?(?P<zahl>{_NUM})\s*"
    rf"(?P<skala>{_SKALA})?\s*(?:,-)?\s*{_WAEHRUNG}", re.IGNORECASE)

#: Stufe 2 — der Beschlussvorschlag. Dasselbe, plus die Schreibweise ohne
#: „in Höhe": „überplanmäßig eine Mehrauszahlung **von** 7,3 Millionen Euro".
_TEXT_BETRAG = re.compile(
    rf"(?:in\s+H(?:ö|oe)he\s+von|"
    rf"Mehr(?:auszahlung|aufwand|aufwendungen|einzahlung)\s+von)\s+"
    rf"(?:insgesamt\s+)?(?P<zahl>{_NUM})\s*(?P<skala>{_SKALA})?\s*(?:,-)?\s*"
    rf"{_WAEHRUNG}", re.IGNORECASE)

#: Ab hier redet der Beschlussvorschlag über die **Deckung**, nicht mehr über
#: die Bewilligung. Alles dahinter ist für den Betrag tabu.
_DECKUNG = re.compile(
    r"(?:Zur\s+Deckung|Als\s+Deckungsmittel|Der\s+Mehrbedarf\s+wird|"
    r"Die\s+Deckung\s+erfolgt|gedeckt\s+durch|Deckung\s+steht)", re.IGNORECASE)

#: Ein Sammelbericht erkennt man an seiner Wertgrenze, nicht am Wort
#: „Bericht": Es gibt auch Einzel-Unterrichtungen mit echtem Betrag
#: („Unterrichtung des Rates über eine überplanmäßige Bewilligung in Höhe von
#: 206.000 EUR für den Waffenplatz").
_SCHWELLE = re.compile(
    rf"(?:unter|bis\s+zu)\s+[\d.]+\s*{_WAEHRUNG}", re.IGNORECASE)

_VERPFLICHTUNG = re.compile(r"Verpflichtungserm(?:ä|ae)chtigung", re.IGNORECASE)

#: Der Titel-Filter, der eine Vorlage überhaupt erst zu einer Nachbewilligung
#: macht. Bewusst breit — „überplanmäßig" **oder** „außerplanmäßig" irgendwo im
#: Titel —, weil die Wortstellung wechselt: mal „Überplanmäßige Bewilligung
#: …", mal „Stadion Marschweg/Ausbau technische Infrastruktur —
#: Außerplanmäßige Verpflichtungsermächtigung …".
_EINSCHLAG = re.compile(r"(?:über|ueber|außer|ausser)planmäßig", re.IGNORECASE)


def ist_nachbewilligung(titel: str) -> bool:
    """Trägt dieser Vorlagentitel eine Nachbewilligung nach § 117 NKomVG?"""
    return bool(_EINSCHLAG.search(titel or ""))


def de_betrag(wert: float, vorzeichen: bool = False) -> str:
    """Ein Betrag in deutscher Schreibweise: ``288.000,00``.

    Diese Texte landen über ``probe_ergebnis`` im Beleg-Chip und damit vor
    Leser*innen; ein englisch formatiertes ``288000.00`` stünde dort mitten in
    einem deutschen Satz."""
    s = f"{abs(wert):,.2f}".replace(",", "␟").replace(".", ",").replace("␟", ".")
    if vorzeichen:
        return ("+" if wert >= 0 else "−") + s
    return ("−" if wert < 0 else "") + s


def _zahl(zahl: str, skala: str | None) -> float:
    """„1.500.000,50" + „Mio." → float. Deutsche Schreibweise, ohne Fallstrick:
    der Punkt ist Tausender-, das Komma Dezimaltrennzeichen."""
    wert = float(zahl.replace(".", "").replace(",", "."))
    s = (skala or "").lower()
    if s.startswith(("mio", "mill")):
        return wert * 1e6
    if s.startswith(("mrd", "milliard")):
        return wert * 1e9
    return wert


def art(titel: str) -> str:
    """Welche der drei Sorten ist das? Reihenfolge zählt.

    Die Schwelle wird **zuerst** geprüft: Der Sammelbericht 21/0023 heißt
    „Über- und außerplanmäßige Auszahlungen, Aufwendungen **und
    Verpflichtungsermächtigungen** bis zu 50.000 Euro …" und träfe sonst auf
    die VE-Regel — mit dem Ergebnis, dass eine Schwelle als
    Verpflichtungsermächtigung im Bestand stünde."""
    t = titel or ""
    if _SCHWELLE.search(t):
        return ART_SCHWELLE
    if _VERPFLICHTUNG.search(t):
        return ART_VERPFLICHTUNG
    return ART_BEWILLIGUNG


#: Die verkürzte Doppelnennung: „Über- und außerplanmäßige Auszahlungen",
#: „über- bzw. außerplanmäßige Verpflichtungsermächtigungen". Der erste Teil
#: trägt sein „planmäßig" gar nicht selbst — wer nur nach „überplanmäßig"
#: sucht, liest hier ausschließlich „außerplanmäßig" und stuft neun
#: Sammelberichte falsch ein.
_BEIDES = re.compile(
    r"(?:über|ueber)-\s*(?:und|bzw\.?|oder)\s*(?:außer|ausser)planmäßig",
    re.IGNORECASE)


def kategorie(titel: str) -> str:
    """``ueberplanmaessig`` | ``ausserplanmaessig`` | ``beides``.

    Der Unterschied ist kein Detail: **überplanmäßig** heißt, der Posten stand
    im Haushalt, das Geld reicht nicht; **außerplanmäßig** heißt, den Posten
    gab es gar nicht. Gedeckt sind beide — „außerplanmäßig" ist kein
    ungedeckter Griff in die Kasse, sondern eine Umwidmung, und jede Vorlage
    nennt die Deckung."""
    t = titel or ""
    if _BEIDES.search(t):
        return "beides"
    ueber = bool(re.search(r"(?:über|ueber)planmäßig", t, re.IGNORECASE))
    ausser = bool(re.search(r"(?:außer|ausser)planmäßig", t, re.IGNORECASE))
    if ueber and ausser:
        return "beides"
    return "ueberplanmaessig" if ueber else "ausserplanmaessig"


def haushaltsjahr(vorlage_nr: str) -> int | None:
    """Für welches Haushaltsjahr wurde bewilligt — aus der Vorlagen-Nummer.

    ``24/0834`` → 2024. Bewusst **nicht** aus dem Sitzungsdatum: Eine Vorlage
    aus dem Dezember kann im Januar beschlossen werden, und der
    Rechenschaftsbericht rechnet sie trotzdem dem alten Jahr zu — er führt in
    seinem Kapitel für 2024 die Vorlage 25/0002. Naiv nach Sitzungsjahr
    summiert liegt man 20 bis 27 Prozent daneben (gemessen 2024:
    30,90 statt 43,10 Mio. €).

    Der Preis der Regel ist klein und benannt: Die neun Sammelberichte
    tragen die Nummer des **Folgejahres** ihres Berichtszeitraums (25/0002
    berichtet über 2024). Sie tragen aber ohnehin keinen Betrag
    (:data:`ART_SCHWELLE`), fallen also in keine Summe."""
    m = re.match(r"\s*(\d{2})/", vorlage_nr or "")
    return 2000 + int(m.group(1)) if m else None


def _betrag_aus_vorschlag(vorschlag: str | None) -> float | None:
    """Der bewilligte Betrag aus einem Beschlussvorschlag — der **erste**.

    Nicht der größte: Nach der Bewilligung nennt derselbe Absatz die Deckung,
    und zwar mit denselben Worten. Bei einer nur teilweise gedeckten
    Bewilligung gewönne der größte Betrag die falsche Zahl."""
    if not vorschlag:
        return None
    block = vorschlag[:2500]
    ende = _DECKUNG.search(block)
    if ende:
        block = block[:ende.start()]
    m = _TEXT_BETRAG.search(block)
    return _zahl(m.group("zahl"), m.group("skala")) if m else None


@dataclass(frozen=True)
class Bewilligung:
    """Eine Nachbewilligung, so wie das RIS sie führt — je Vorlage eine."""

    vorlage_nr: str
    titel: str
    #: :data:`ART_BEWILLIGUNG` | :data:`ART_VERPFLICHTUNG` | :data:`ART_SCHWELLE`
    art: str
    kategorie: str
    jahr: int | None
    #: ``None`` bei :data:`ART_SCHWELLE` — dort ist der Titelbetrag die Grenze.
    betrag: float | None
    #: ``titel`` | ``beschlussvorschlag`` | ``None`` — welche Stufe traf.
    betrag_quelle: str | None
    #: Wie die Vorlage durch die Gremien lief; leer, wenn nur beantragt.
    beschluesse: tuple[dict, ...] = field(default_factory=tuple)

    @property
    def beschlossen(self) -> bool:
        """Wurde die Bewilligung wirklich erteilt?

        Fünf der 161 Vorlagen tragen **gar keine** Beschlusszeile (19/0528,
        22/0925, 25/0734, 26/0365, 26/0515) — eingebracht, aber im Bestand
        ohne Ergebnis. Sie zu summieren hieße, Beantragtes als Bewilligtes
        auszugeben; allein 22/0925 verschöbe das Jahr 2022 um 1,4 Mio. €."""
        return any(b.get("outcome") == "angenommen" for b in self.beschluesse)

    @property
    def nur_kenntnis(self) -> bool:
        """Der Rat wurde nur **unterrichtet** — entschieden hat ein anderer.

        Das ist keine Formalie, sondern der Punkt der ganzen Seite: „Bericht"
        heißt Eilentscheidung oder Entscheidung des Oberbürgermeisters. Auch
        das RIS kennt die vier Kanäle also, es sagt sie nur nicht so deutlich
        wie der Rechenschaftsbericht."""
        return bool(self.beschluesse) and not self.beschlossen

    @property
    def zaehlt_in_summe(self) -> bool:
        """Nur erteilte Bewilligungen mit Betrag gehen in eine Jahressumme."""
        return (self.art == ART_BEWILLIGUNG and self.betrag is not None
                and self.beschlossen)

    @property
    def im_rat(self) -> bool:
        """Hat der Rat selbst darüber abgestimmt?"""
        return any(str(b.get("committee", "")).startswith("Rat")
                   and b.get("outcome") == "angenommen"
                   for b in self.beschluesse)


def betrag(titel: str, vorschlag: str | None = None,
           volltext: str | None = None) -> tuple[float | None, str | None]:
    """Der Betrag einer Nachbewilligung, zweistufig.

    → ``(betrag, quelle)`` mit ``quelle`` aus ``titel`` |
    ``beschlussvorschlag`` | ``None``. **Die Reihenfolge des Tupels ist
    (Wert, Herkunft)** — nicht umgekehrt.

    ``vorschlag`` ist ``council_vorlagen.beschlussvorschlag``, falls gefüllt;
    ``volltext`` der ``raw_text`` derselben Vorlage. Steht der Vorschlag nicht
    in der Spalte, wird er aus dem Volltext geerntet — mit derselben Funktion,
    die auch die Spalte füllt (``council.ernte.beschlussvorschlag``), damit
    beide Wege dasselbe finden.

    Bei :data:`ART_SCHWELLE` gibt es bewusst **nichts** zurück: Der Betrag im
    Titel eines Sammelberichts ist die Wertgrenze."""
    if art(titel) == ART_SCHWELLE:
        return None, None
    m = _TITEL_BETRAG.search(titel or "")
    if m:
        return _zahl(m.group("zahl"), m.group("skala")), "titel"
    text = vorschlag or ernte.beschlussvorschlag(volltext or "")
    wert = _betrag_aus_vorschlag(text)
    return (wert, "beschlussvorschlag") if wert is not None else (None, None)


def aus_vorlagen(vorlagen: list[dict],
                 beschluesse: dict[str, list[dict]] | None = None,
                 ) -> list[Bewilligung]:
    """Die Rats-Serie aus dem RIS — je **Vorlage** eine :class:`Bewilligung`.

    ``vorlagen`` sind Zeilen aus ``council_vorlagen`` (``vorlage_nr``,
    ``title``, optional ``beschlussvorschlag`` und ``raw_text``);
    ``beschluesse`` bildet ``vorlage_nr`` auf die zugehörigen Zeilen aus
    ``council_decisions`` ab (mit ``committee``, ``session_date``,
    ``outcome``).

    Warum je Vorlage und nicht je Beschlusszeile: 287 Zeilen stehen über 156
    Vorlagen — Finanzausschuss und Rat entscheiden dieselbe Sache. Je Zeile
    gezählt wäre fast jeder Betrag doppelt in der Summe.

    Sortiert nach Vorlagen-Nummer, also chronologisch."""
    beschluesse = beschluesse or {}
    out: list[Bewilligung] = []
    for v in vorlagen:
        titel = v.get("title") or ""
        if not ist_nachbewilligung(titel):
            continue
        nr = v.get("vorlage_nr") or ""
        wert, quelle = betrag(titel, v.get("beschlussvorschlag"),
                              v.get("raw_text"))
        out.append(Bewilligung(
            vorlage_nr=nr, titel=titel, art=art(titel),
            kategorie=kategorie(titel), jahr=haushaltsjahr(nr),
            betrag=wert, betrag_quelle=quelle,
            beschluesse=tuple(beschluesse.get(nr, ()))))
    return sorted(out, key=lambda b: b.vorlage_nr)


def jahressummen(bewilligungen: list[Bewilligung],
                 nur_rat: bool = False) -> dict[int, dict]:
    """Je Haushaltsjahr: Summe, Fallzahl und was ausdrücklich draußen blieb.

    ``nur_rat=True`` zählt nur Vorlagen, über die der Rat selbst abgestimmt
    hat. Die Verpflichtungsermächtigungen stehen **getrennt** daneben
    (``verpflichtungen``/``verpflichtungen_betrag``) und sind in ``summe``
    nicht enthalten — dieselbe Trennung, die der Rechenschaftsbericht zieht."""
    jahre: dict[int, dict] = {}

    def eintrag(jahr: int) -> dict:
        return jahre.setdefault(jahr, {
            "jahr": jahr, "summe": 0.0, "faelle": 0,
            "verpflichtungen": 0, "verpflichtungen_betrag": 0.0,
            "sammelberichte": 0})

    for b in bewilligungen:
        if b.jahr is None or (nur_rat and not b.im_rat):
            continue
        # Der Eintrag entsteht erst, wenn wirklich etwas hineinfällt: Eine
        # nur beantragte Vorlage darf kein Jahr mit lauter Nullen erzeugen —
        # das sähe aus wie „2022 gab es nichts" statt „hier ist nichts
        # beschlossen worden".
        if b.art == ART_SCHWELLE:
            eintrag(b.jahr)["sammelberichte"] += 1
        elif b.art == ART_VERPFLICHTUNG and b.beschlossen:
            e = eintrag(b.jahr)
            e["verpflichtungen"] += 1
            e["verpflichtungen_betrag"] += b.betrag or 0.0
        elif b.zaehlt_in_summe:
            e = eintrag(b.jahr)
            e["summe"] += b.betrag
            e["faelle"] += 1
    return dict(sorted(jahre.items()))


# --- Probe 1: der Titelbetrag steht im Volltext noch einmal -----------------

def probe_volltext(bewilligung: Bewilligung, volltext: str | None) -> bool:
    """Steht der Betrag aus dem Titel im Volltext derselben Vorlage wieder?

    Die billigste Probe des Bereichs und trotzdem eine echte: Sie schlägt an,
    wenn der Titel-Regex eine Jahreszahl, eine Teilhaushaltsnummer oder den
    Deckungsbetrag erwischt hätte. Gemessen 145 von 145.

    Ohne Titelbetrag ist nichts zu prüfen — dann ist die Antwort ``False``,
    nicht ``True``: „nicht geprüft" darf nicht wie „bestanden" aussehen."""
    if bewilligung.betrag_quelle != "titel" or bewilligung.betrag is None:
        return False
    return any(abs(_zahl(m.group("zahl"), m.group("skala")) - bewilligung.betrag)
               < 0.005 for m in _TEXT_BETRAG.finditer(volltext or ""))


# --- Rechenschaftsbericht, Kapitel 3 ---------------------------------------

#: Die Überschrift des Kapitels. Sie steht **zweimal** im Dokument — einmal im
#: Inhaltsverzeichnis (mit „RB 45" dahinter), einmal über dem Kapitel selbst.
#: Genommen wird die letzte Fundstelle.
_KAP3 = re.compile(
    r"(?m)^\s*3\s+[ÜU]ber-?\s*und\s+au[ßs]erplanm[äa][ßs]ige\s+"
    r"Aufwendungen\s+und")
_KAP4 = re.compile(r"(?m)^\s*4\s+Erm[äa]chtigungs[üu]bertragungen")

_GESAMT = re.compile(
    rf"Aufwendungen\s+und\s+Auszahlungen\s+von\s+insgesamt\s+({_NUM})\s*Euro",
    re.IGNORECASE | re.DOTALL)
_AUFTEILUNG = re.compile(
    rf"Davon\s+entfielen\s+({_NUM})\s*Euro\s+auf\s+investive\s+und\s+"
    rf"({_NUM})\s*Euro\s+auf\s+konsumtive", re.IGNORECASE | re.DOTALL)
#: Die Verpflichtungsermächtigungen des Jahres — im Fließtext, hinter
#: „Darüber hinaus", und ausdrücklich **nicht** in der Gesamtsumme.
#:
#: Der Zwischenraum ist ``[\s\S]{0,200}?`` und nicht ``[^.]*?``: Zwischen
#: „Darüber hinaus" und dem Wort steht „sechs über- **bzw.**
#: außerplanmäßige …", und ein Punkt-Verbot bricht an dieser Abkürzung ab.
_VE_TEXT = re.compile(
    rf"Dar[üu]ber\s+hinaus\s+wurden?[\s\S]{{0,200}}?"
    rf"Verpflichtungserm[äa]chtigung(?:en)?\s+in\s+H[öo]he\s+von\s+"
    rf"(?:insgesamt\s+)?({_NUM})\s*Euro", re.IGNORECASE)
_SUMMENZEILE = re.compile(rf"(?m)^\s*Summe\s+({_NUM})\s+({_NUM})\s*$")

#: Der Kopf der Übersichtstabelle — und die Grenze, ab der die Kanalnamen
#: Tabellenzeilen bedeuten und nicht Fließtext.
#:
#: Ohne diese Grenze verschwand ein Kanal: Der einleitende Satz des Kapitels
#: lautet „… wurde er über **Eilentscheidungen** und die vom Oberbürgermeister
#: … unterrichtet". Wer den Kanal per ``search`` sucht, landet dort statt in
#: der Tabelle — und liest hinter der Prosa keine Zellen mehr. 2022 fehlten so
#: die 180.000 € der einen Eilentscheidung, was prompt die Spaltenprobe riss.
_TABELLENKOPF = re.compile(r"Anzahl\s+Konsumtive")

#: Die vier Kanalzeilen der Übersichtstabelle. Der Textextrakt bricht sie
#: über mehrere Zeilen um („Vom Oberbürgermeister\nentschieden\n3 42.467,80"),
#: deshalb wird nach dem Label über Zeilengrenzen hinweg gelesen.
_KANAL_LABEL: dict[str, str] = {
    "rat": r"Beschluss\s+des\s+Rates",
    "oberbuergermeister": r"Vom\s+Oberb[üu]rgermeister\s+entschieden",
    "fachdienst200": r"Gem[äa][ßs]\s+Haushaltsvermerk\s+durch\s+den\s+"
                     r"Fachdienst\s+200",
    "eilentscheidung": r"Eilentscheidungen",
}
#: Eine Tabellenzelle **auf ihrer eigenen Zeile**: erst die Anzahl, dann der
#: Betrag — und der darf fehlen („Eilentscheidungen 0" hat gar keinen).
#:
#: Zeilenweise und mit ``$`` verankert, weil es anders nicht geht: Ein Muster
#: ``(\d+)\s+(BETRAG)?`` über den ganzen Block gelesen frisst bei „0\n1
#: 180.000,00" den Zeilenumbruch und nimmt die **1 der nächsten Zeile** als
#: Betrag der vorigen. Genau das hat die Eilentscheidungen 2022 auf „36 Fälle,
#: 0 €" gebracht statt auf „1 Fall, 180.000 €".
_ZELLE = re.compile(rf"^\s*(\d+)(?:\s+({_NUM}))?\s*$")


@dataclass(frozen=True)
class Kanal:
    """Ein Entscheidungskanal mit seinen beiden Spalten."""

    schluessel: str
    label: str
    anzahl_konsumtiv: int
    betrag_konsumtiv: float
    anzahl_investiv: int
    betrag_investiv: float

    @property
    def anzahl(self) -> int:
        return self.anzahl_konsumtiv + self.anzahl_investiv

    @property
    def betrag(self) -> float:
        return self.betrag_konsumtiv + self.betrag_investiv


@dataclass(frozen=True)
class Kapitel3:
    """Kapitel 3 eines Rechenschaftsberichts — ein Haushaltsjahr."""

    jahr: int
    kanaele: tuple[Kanal, ...]
    #: Was die Summenzeile der Tabelle selbst ausweist.
    summe_konsumtiv: float
    summe_investiv: float
    #: Was der Fließtext darüber behauptet.
    text_gesamt: float | None
    text_konsumtiv: float | None
    text_investiv: float | None
    #: Verpflichtungsermächtigungen — separat, nie in einer Summe.
    verpflichtungen_betrag: float | None

    @property
    def gesamt(self) -> float:
        """Die Summe, für die das Dokument selbst geradesteht."""
        return self.summe_konsumtiv + self.summe_investiv

    def kanal(self, schluessel: str) -> Kanal | None:
        return next((k for k in self.kanaele if k.schluessel == schluessel), None)

    @property
    def rats_anteil(self) -> float | None:
        """Wie viel Prozent der Nachbewilligungen der Rat selbst beschloss.

        Die Zahl, um die es geht: 88 % (2022), 84 % (2023), **73 %** (2024)."""
        rat = self.kanal("rat")
        return (rat.betrag / self.gesamt * 100) if rat and self.gesamt else None


def _kapitel3_text(volltext: str) -> str | None:
    """Der Fließtext-Abschnitt 3, ohne den Inhaltsverzeichnis-Eintrag."""
    treffer = list(_KAP3.finditer(volltext or ""))
    if not treffer:
        return None
    start = treffer[-1].start()
    rest = volltext[start:]
    ende = _KAP4.search(rest)
    return rest[:ende.start()] if ende else rest[:120_000]


def _kanal(text: str, schluessel: str, muster: str) -> Kanal | None:
    """Eine Kanalzeile lesen: zwei Paare aus Anzahl und (optional) Betrag.

    Das erste Paar ist die konsumtive Spalte, das zweite die investive — so
    setzt der Textextrakt die zweizeilige Tabellenzelle um. Gelesen wird nur
    das Stück bis zur nächsten Kanalüberschrift, damit kein Kanal die Zahlen
    seines Nachbarn erbt."""
    m = re.search(muster, text)
    if not m:
        return None
    rest = text[m.end():]
    grenzen = [t.start() for t in
               (re.compile(v).search(rest) for k, v in _KANAL_LABEL.items()
                if k != schluessel) if t]
    summe = re.search(r"(?m)^\s*Summe\s", rest)
    if summe:
        grenzen.append(summe.start())
    if grenzen:
        rest = rest[:min(grenzen)]
    zellen: list[tuple[int, float]] = []
    for zeile in rest.splitlines():
        z = _ZELLE.match(zeile)
        if z:
            zellen.append((int(z.group(1)),
                           _zahl(z.group(2), None) if z.group(2) else 0.0))
        if len(zellen) == 2:
            break
    if len(zellen) < 2:
        return None
    (ak, bk), (ai, bi) = zellen
    return Kanal(schluessel=schluessel, label=KANAELE[schluessel],
                 anzahl_konsumtiv=ak, betrag_konsumtiv=bk,
                 anzahl_investiv=ai, betrag_investiv=bi)


def kapitel3(volltext: str, jahr: int) -> Kapitel3 | None:
    """Kapitel 3 eines Rechenschaftsberichts lesen.

    → ``None``, wenn das Kapitel oder seine Summenzeile fehlt; ein Kapitel
    ohne Summenzeile ließe sich nicht prüfen, und ungeprüft kommt hier nichts
    herein."""
    text = _kapitel3_text(volltext)
    if not text:
        return None
    summe = _SUMMENZEILE.search(text)
    if not summe:
        return None
    kopf = _TABELLENKOPF.search(text)
    tabelle = text[kopf.end():summe.end()] if kopf else text[:summe.end()]
    kanaele = tuple(k for k in (_kanal(tabelle, s, m)
                                for s, m in _KANAL_LABEL.items()) if k)
    gesamt = _GESAMT.search(text)
    auft = _AUFTEILUNG.search(text)
    ve = _VE_TEXT.search(text)
    return Kapitel3(
        jahr=jahr, kanaele=kanaele,
        summe_konsumtiv=_zahl(summe.group(1), None),
        summe_investiv=_zahl(summe.group(2), None),
        text_gesamt=_zahl(gesamt.group(1), None) if gesamt else None,
        # Reihenfolge im Satz: erst investiv, dann konsumtiv.
        text_investiv=_zahl(auft.group(1), None) if auft else None,
        text_konsumtiv=_zahl(auft.group(2), None) if auft else None,
        verpflichtungen_betrag=_zahl(ve.group(1), None) if ve else None)


# --- Probe 3: das Dokument gegen sich selbst -------------------------------

@dataclass(frozen=True)
class Tabellenprobe:
    """Was Probe 3 gefunden hat — und was davon ein Widerspruch ist."""

    spalten_ok: bool
    #: Differenz Kanalzeilen − Summenzeile, je Spalte (0.0 = geht auf).
    abweichung_konsumtiv: float
    abweichung_investiv: float
    gesamt_ok: bool
    #: Differenz Summenzeile − Fließtext-Gesamtsumme.
    abweichung_gesamt: float

    @property
    def bestanden(self) -> bool:
        return self.spalten_ok and self.gesamt_ok

    def als_text(self) -> str:
        """Ein Satz fürs ``probe_ergebnis`` der Herkunft."""
        if self.bestanden:
            return "Spalten und Gesamtsumme gehen auf den Cent auf."
        teile = []
        if not self.spalten_ok:
            teile.append(
                f"Die Einzelzeilen ergeben nicht die Summenzeile des "
                f"Dokuments (konsumtiv "
                f"{de_betrag(self.abweichung_konsumtiv, vorzeichen=True)} €, "
                f"investiv "
                f"{de_betrag(self.abweichung_investiv, vorzeichen=True)} €)")
        if not self.gesamt_ok:
            richtung = "mehr" if self.abweichung_gesamt > 0 else "weniger"
            teile.append(
                f"Der Fließtext nennt {de_betrag(abs(self.abweichung_gesamt))} € "
                f"{richtung} als die Tabelle darunter")
        return "; ".join(teile) + "."


def probe_tabelle(kap: Kapitel3, toleranz: float = 0.005) -> Tabellenprobe:
    """Rechnet das Kapitel sich selbst vor?

    Zwei Fragen: Ergeben die vier Kanalzeilen die Summenzeile (je Spalte)?
    Und ergeben beide Spalten zusammen die Gesamtsumme aus dem Fließtext?

    **Was die Probe an den drei Jahrgängen gefunden hat:**

    * **2024** — beides geht auf den Cent auf.
    * **2022** — die Spalten stimmen, der Fließtext nicht: Er nennt
      26.969.523,30 €, die eigene Tabelle ergibt 26.681.523,30 €.
      **288.000 € Unterschied.** Der Fließtext widerspricht dabei sich selbst,
      denn seine beiden Teilbeträge (10.032.086,30 investiv + 16.649.437,00
      konsumtiv) ergeben die Tabellensumme, nicht seine eigene Gesamtzahl.
    * **2023** — die konsumtive Spalte stimmt, die investive nicht: In der
      Zeile „Fachdienst 200" steht Anzahl **0** und trotzdem ein Betrag von
      1.051.184,65 € — auf den Cent derselbe Wert wie im Vorjahr an derselben
      Stelle. Die Summenzeile rechnet ihn nicht mit (8.470.300,00 +
      365.007,05 = 8.835.307,05 genau), und die Gesamtsumme des Fließtextes
      auch nicht. Alles spricht für einen Übernahmerest aus der Vorjahres-
      tabelle.

    In beiden Fällen wird der Widerspruch **gemeldet, nicht geglättet**: Was
    hier zurückkommt, landet als ``probe_ergebnis`` an der Herkunft und von
    dort auf der Seite."""
    ak = sum(k.betrag_konsumtiv for k in kap.kanaele) - kap.summe_konsumtiv
    ai = sum(k.betrag_investiv for k in kap.kanaele) - kap.summe_investiv
    if kap.text_gesamt is None:
        gesamt_ok, ag = True, 0.0
    else:
        ag = kap.text_gesamt - kap.gesamt
        gesamt_ok = abs(ag) < toleranz
    return Tabellenprobe(
        spalten_ok=abs(ak) < toleranz and abs(ai) < toleranz,
        abweichung_konsumtiv=ak, abweichung_investiv=ai,
        gesamt_ok=gesamt_ok, abweichung_gesamt=ag)


# --- Probe 2: unsere Serie gegen den Rechenschaftsbericht ------------------

@dataclass(frozen=True)
class Ratsabgleich:
    """Unsere Rats-Serie gegen die Zeile „Beschluss des Rates" des Berichts."""

    jahr: int
    unsere_summe: float
    unsere_faelle: int
    bericht_summe: float
    bericht_faelle: int
    #: Vorlagen-Nummern, die der Bericht nennt und wir nicht — und umgekehrt.
    nur_im_bericht: tuple[str, ...] = ()
    nur_bei_uns: tuple[str, ...] = ()

    @property
    def abweichung(self) -> float:
        return self.unsere_summe - self.bericht_summe

    @property
    def abweichung_prozent(self) -> float | None:
        if not self.bericht_summe:
            return None
        return self.abweichung / self.bericht_summe * 100

    def als_text(self) -> str:
        p = self.abweichung_prozent
        if abs(self.abweichung) < 0.005:
            return (f"{self.jahr}: identisch mit dem Rechenschaftsbericht "
                    f"({self.bericht_faelle} Fälle).")
        prozent = ""
        if p is not None:
            prozent = (" (unter 0,01 %)" if abs(p) < 0.01
                       else f" ({de_betrag(p, vorzeichen=True)} %)")
        return (f"{self.jahr}: {de_betrag(self.abweichung, vorzeichen=True)} € "
                f"gegenüber dem Rechenschaftsbericht{prozent}, "
                f"{self.unsere_faelle} gegen {self.bericht_faelle} Fälle.")


#: Vorlagen-Nummern haben die Form ``24/0834``.
_VORLAGE_NR = re.compile(r"\b(\d{2}/\d{4})\b")


def vorlagen_im_kapitel(volltext: str) -> set[str]:
    """Alle Vorlagen-Nummern, die Kapitel 3 nennt — der Join-Schlüssel.

    Das ist der Grund, warum diese Probe die härteste im Bereich ist: Der
    Bericht nennt nicht nur Summen, sondern **dieselben Fälle mit ihren
    Nummern**. Gemessen: 2023 und 2024 decken sich die Listen vollständig
    (26/26 und 21/21, je zuzüglich des Sammelberichts fürs Vorjahr)."""
    text = _kapitel3_text(volltext)
    return set(_VORLAGE_NR.findall(text or ""))


def probe_ratsabgleich(bewilligungen: list[Bewilligung], kap: Kapitel3,
                       kapitel_nummern: set[str] | None = None) -> Ratsabgleich:
    """Unsere Serie gegen die Zeile „Beschluss des Rates" desselben Jahres.

    **Die gemessenen Abweichungen, mit ihren Ursachen — sie werden benannt
    statt geglättet:**

    * **2023: +100 € auf 33,87 Mio.** (0,0003 %), Fallliste identisch (26/26).
      Eine Rundung in einer einzelnen Position.
    * **2024: +2,19 %** (43.096.100,00 gegen 42.171.646,29), Fallliste
      ebenfalls identisch (21/21) — der Unterschied steckt also **nicht** in
      fehlenden Fällen, sondern in den Beträgen. Er hat einen erkennbaren
      Grund: Unsere Zahl ist der Betrag, den die **Vorlage beantragt**, die des
      Berichts der Betrag, der am Ende **je Haushaltsposition gebucht** wurde.
      Dass die Berichtszahl auf ,29 endet und jede unserer Zahlen glatt ist,
      zeigt es unmittelbar.
    * **2022: +1,31 %** (24.136.742,00 gegen 23.825.742,00). Hier liegt es an
      zwei Vorlagen: 22/0544 (180.000 €) führt der Bericht mit dem Vermerk
      „1 und BM", also als Entscheidung des **Oberbürgermeisters**, obwohl das
      RIS eine Rats-Beschlusszeile dazu führt; 22/0914 (131.000 €) nennt der
      Bericht gar nicht. Zusammen genau die Differenz.

    Die dahinterliegende Grenze gehört auf die Seite: **Wir zählen Vorlagen,
    der Bericht zählt Haushaltspositionen** — eine Vorlage kann mehrere
    Positionen tragen, und wer eine Bewilligung rechtlich erteilt hat, steht
    im Bericht, nicht im Sitzungsprotokoll."""
    rat = kap.kanal("rat")
    passend = [b for b in bewilligungen
               if b.jahr == kap.jahr and b.zaehlt_in_summe]
    unsere = {b.vorlage_nr for b in passend}
    nur_bericht: tuple[str, ...] = ()
    nur_uns: tuple[str, ...] = ()
    if kapitel_nummern is not None:
        # Der Sammelbericht des Folgejahres steht immer mit im Kapitel; er ist
        # kein Fall, sondern die Meldung über die Fälle unter der Wertgrenze.
        bericht = {n for n in kapitel_nummern
                   if haushaltsjahr(n) == kap.jahr}
        nur_bericht = tuple(sorted(bericht - unsere))
        nur_uns = tuple(sorted(unsere - bericht))
    return Ratsabgleich(
        jahr=kap.jahr,
        unsere_summe=sum(b.betrag or 0.0 for b in passend),
        unsere_faelle=len(passend),
        bericht_summe=rat.betrag if rat else 0.0,
        bericht_faelle=rat.anzahl if rat else 0,
        nur_im_bericht=nur_bericht, nur_bei_uns=nur_uns)


#: Die Proben dieser Schicht, wie sie in ``council/herkunft.PROBEN`` stehen.
PROBE_VOLLTEXT = "nachbewilligung_volltext"
PROBE_TABELLE = "nachbewilligung_tabellenprobe"
PROBE_RAT = "nachbewilligung_ratsabgleich"

assert PROBE_VOLLTEXT in herkunft.PROBEN
assert PROBE_TABELLE in herkunft.PROBEN
assert PROBE_RAT in herkunft.PROBEN
