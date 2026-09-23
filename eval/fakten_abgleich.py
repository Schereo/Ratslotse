"""Der Abgleich der Fakten-Eval — reine Funktionen, ohne Modell und ohne Netz.

**Wozu.** Tims Satz vom 23.09.2026: „Wenn wir im Kontext schon Mist haben,
kann das beste Modell ja nichts Gutes draus machen.“ Die Eval misst deshalb
je Fall ZWEI Dinge getrennt (Spezifikation: ``spez-fakten-eval``, übernommen
in ``docs/fakten-eval.md``):

1. **Stand der Goldfakt im Prompt?** Und zwar unter dem RICHTIGEN Jahr. Der
   Faktencheck vom 23.09. fand genau diesen Fehler: Die „davon“-Zeilen des
   Schuldenstands 2025 standen eingerückt unter „Ein Jahr davor (2024)“ —
   die Zahl war da, las sich aber wie die Aufschlüsselung von 2024. Ein
   reiner Vorkommenstest hätte das als „Kontext in Ordnung“ gezählt.
2. **Nennt die Antwort ihn?** Mit Rundung („rund 337 Millionen“ =
   336.994.000), ohne Vorjahreswert als aktuellen, ohne erfundene Zahl.

Nur wenn (1) stimmt, ist ein Fehler in (2) ein **Modellfehler**. Die
Einteilung steht in :func:`bewerten`.

**Kein Modell als Richter** — aus demselben Grund wie in
``eval/run_assistant.py``: Ein Richter-Modell ist bei jedem Lauf woanders,
und die Frage hier ist buchstäblich prüfbar (Zahl mit Jahr, Wort, Kennung).

**Wie ein Jahr einer Zahl zugeordnet wird** (:func:`jahre_der_zahl`). Der
Kontext ist zeilenweise gebaut: Kopfzeile, Spiegelstriche, eingerückte
„davon“-Zeilen. Eine Zahl gehört zum Jahr, das in ihrer Zeile VOR ihr steht
(„Ein Jahr davor (2024): 294.851.000 €“), sonst zum Jahr gleich dahinter
(„337 Mio. € (2025)“), sonst zum Jahr der übergeordneten Zeile — der
nächsten darüber mit geringerer Einrückung, bis zur Leerzeile. Genau so
liest ein Mensch (und ein Modell) die Liste. Nennt die Elternzeile mehrere
Jahre („Stand 1995 bis 2025“), gelten alle als möglich: Das ist keine
falsche Zuordnung, nur eine unscharfe.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from itertools import combinations
from typing import Any

# --------------------------------------------------------------------------- #
# Zahlen lesen
# --------------------------------------------------------------------------- #

_MULT = {
    "mrd": 1e9, "milliarde": 1e9, "milliarden": 1e9,
    "mio": 1e6, "million": 1e6, "millionen": 1e6,
    "tsd": 1e3, "tausend": 1e3, "t€": 1e3, "teur": 1e3,
}

#: Eine Zahl im deutschen Format, mit optionalem Vielfachen und Einheit.
#: „336.994.000 €“, „336,9 Mio. €“, „rund 337 Millionen Euro“, „1.908 €“,
#: „20,4 %“, „0,3 Mrd.“, „72.600 TEUR“. Das Minus nur direkt vor der Ziffer
#: und nie nach einer Ziffer: „2010–2025“ ist ein Zeitraum, keine −2025.
_ZAHL = re.compile(
    r"(?:(?<![\w.,\-−–])(?P<vz>[-−]))?"
    r"(?<![\w.,])"
    r"(?P<num>\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:,\d+)?)"
    r"(?![\d])(?!\.\d)"
    r"(?:\s?(?P<mult>Mrd\.?|Milliarden?|Mio\.?|Millionen?|Tsd\.?|Tausend|T€|TEUR)(?![a-zäöü]))?"
    r"(?:\s?(?P<einheit>€|Euro\b|EUR\b|%|Prozent\b|v\.\s?H\.))?",
    re.IGNORECASE,
)
#: Ein Datum („31.12.2025“, „1. Juni 2026“ lässt die Zahl als Zahl stehen):
#: Tag und Monat sind keine Beträge. Übrig bleibt das Jahr.
_DATUM = re.compile(r"\b\d{1,2}\.\d{1,2}\.(?=(?:19|20)\d\d\b)")
#: Ein Jahr: vierstellig, 1990–2049, nicht Teil einer größeren Zahl.
_JAHR = re.compile(r"(?<![\d.,])(?:19[89]\d|20[0-4]\d)(?![.,]?\d)")


@dataclass(frozen=True)
class Zahl:
    """Eine gelesene Zahl."""

    wert: float
    #: ``€`` (Euro oder ein Vielfaches wie „Mio.“), ``%``, ``jahr`` oder ``""``.
    art: str
    #: Die Auflösung der Angabe: „336,9 Mio.“ → 100.000, „337 Mio.“ → 1 Mio.,
    #: „336.994.000“ → 1 000 (Nullen am Ende gelten als gerundet).
    aufloesung: float
    pos: int
    ende: int
    text: str


def _aufloesung(ziffern: str, mult: float) -> float:
    """Die kleinste Stelle, die die Angabe noch trägt."""
    if "," in ziffern:
        return 10 ** -len(ziffern.split(",", 1)[1]) * mult
    rein = ziffern.replace(".", "")
    nullen = len(rein) - len(rein.rstrip("0")) if rein.strip("0") else 0
    return 10 ** nullen * mult


def zahlen(text: str, *, woerter: bool = False) -> list[Zahl]:
    """Alle Zahlen eines Textes, Datumsangaben ohne Tag und Monat.

    ``woerter=True`` (nur für Antworten) liest auch „fünf“, „neun“ als Zahl.
    Im Kontext nicht: Dort stehen die Zahlen aus unserem Code als Ziffern,
    und ein „neun“ aus einem fremden Protokollsatz fände sonst den Goldfakt
    im falschen Beschluss.
    """
    maskiert = _DATUM.sub(lambda m: " " * len(m.group(0)), text or "")
    aus: list[Zahl] = []
    for m in _ZAHL.finditer(maskiert):
        ziffern = m.group("num")
        mult_roh = (m.group("mult") or "").lower().rstrip(".")
        mult = _MULT.get(mult_roh, 1.0)
        einheit = (m.group("einheit") or "").lower()
        basis = float(ziffern.replace(".", "").replace(",", "."))
        wert = basis * mult * (-1 if m.group("vz") else 1)
        if einheit in ("%", "prozent") or einheit.startswith("v."):
            art = "%"
        elif einheit or m.group("mult"):
            art = "€"
        elif (_JAHR.fullmatch(ziffern)) is not None:
            art = "jahr"
        else:
            art = ""
        aus.append(Zahl(wert, art, _aufloesung(ziffern, mult), m.start(), m.end(),
                        text[m.start():m.end()]))
    # Kleine Zahlen schreibt man aus: „es gab fünf Gegenstimmen“, „bei neun
    # Enthaltungen“ — GPT-6 Luna am 23.09.2026, zweimal als Auslassung
    # gezählt. Erst ab „zwei“: „ein/eine“ ist meist ein Artikel. Als Zahl ohne
    # Einheit, also nie ein Betrag (``_bedeutsam`` prüft sie nicht).
    for m in (_ZAHLWORT.finditer(text or "") if woerter else ()):
        aus.append(Zahl(float(_ZAHLWOERTER[m.group(1).lower()]), "", 1.0, m.start(), m.end(),
                        m.group(0)))
    aus.sort(key=lambda z: z.pos)
    # „von 50 auf höchstens 79 Millionen Euro“: Das Vielfache steht einmal,
    # es gilt für beide (GPT-6 Luna, 23.09.2026 — die 50 Mio. € zählten als
    # ausgelassen). Die nackte Zahl bekommt das Vielfache der nächsten, wenn
    # nur ein Bindewort dazwischen steht.
    for i, z in enumerate(aus[:-1]):
        nach = aus[i + 1]
        if z.art != "" or nach.art != "€" or not _BINDEWORT.fullmatch(text[z.ende:nach.pos]):
            continue
        m_nach = _ZAHL.match(nach.text)
        mult = _MULT.get(((m_nach and m_nach.group("mult")) or "").lower().rstrip("."), 1.0)
        if mult > 1:
            aus[i] = Zahl(z.wert * mult, "€", z.aufloesung * mult, z.pos, z.ende, z.text)
    return aus


_BINDEWORT = re.compile(r"\s*(?:auf|bis|und|oder|bzw\.|–|-)\s*"
                        r"(?:(?:höchstens|maximal|rund|knapp|etwa|über|gut)\s*)?", re.IGNORECASE)


_ZAHLWOERTER = {w: i for i, w in enumerate(
    ("null", "eins", "zwei", "drei", "vier", "fünf", "sechs", "sieben", "acht", "neun",
     "zehn", "elf", "zwölf", "dreizehn", "vierzehn", "fünfzehn", "sechzehn", "siebzehn",
     "achtzehn", "neunzehn", "zwanzig")) if i >= 2}
_ZAHLWORT = re.compile(r"(?<![\wäöüß])(" + "|".join(
    sorted(_ZAHLWOERTER, key=len, reverse=True)) + r")(?![\wäöüß])", re.IGNORECASE)


#: Bis wohin eine gerundete Angabe als dieselbe Zahl gilt. „0,3 Mrd.“ für
#: 294,9 Mio. (1,7 %) ist eine Rundung, „rund 2 Millionen“ für 2,36 Mio.
#: Baunebenkosten auch (15 %, GPT-6 Luna am 23.09. — bei 5 % galt es als
#: erfunden); „1 Mrd.“ für 740 Mio. (35 %) nicht mehr.
RUNDUNG_MAX = 0.2
#: Ohne Angabe im Fall: So weit darf eine GENAUE Angabe abweichen — zwei
#: Quellen derselben Zahl liegen so nah beieinander (Jahrbuch und Abschluss
#: 2024: 764.745.000 und 764.416.064 €, 0,04 %). Enger als eine Rundung,
#: und das mit Grund: Bei 0,5 % galt „70.481.000 € (Rekord 2020)“ als der
#: Investitionsplan 2026 von 70.273.312 € — zwei verschiedene Zahlen.
TOLERANZ_STANDARD = 0.001


def passt(z: Zahl, gold: float, toleranz: float = TOLERANZ_STANDARD,
          rundung_max: float = RUNDUNG_MAX) -> bool:
    """Ist die gelesene Zahl der Goldwert — genau, im Rahmen oder gerundet?

    Verglichen wird der BETRAG: Ein Defizit heißt im Text „Fehlbetrag von
    12 Mio.“, nicht „−12 Mio.“. Das Vorzeichen ist Sache der Wörter drumherum.
    """
    g, w = abs(gold), abs(z.wert)
    if g == 0:
        return w == 0
    rel = abs(w - g) / g
    stufe = z.aufloesung or 1.0
    # Eine GENAUE Angabe (Auflösung deutlich feiner als die Toleranz) darf
    # im Rahmen der Toleranz abweichen. Eine gerundete muss richtig gerundet
    # sein: „338 Mio.“ für 336,99 Mio. liegt zwar nur 0,3 % daneben, ist aber
    # keine Rundung, sondern eine andere Zahl.
    if rel <= toleranz + 1e-12 and stufe <= toleranz * g / 10:
        return True
    if rel > rundung_max:
        return False
    # Gerundet oder abgeschnitten („über 336 Mio.“) — beides ist ehrlich.
    # Kaufmännisch gerundet, nicht mit Pythons `round`: Das rundet die Hälfte
    # zur GERADEN Ziffer, und „35,9 Mio. €“ für 35.850.000 € (das größte
    # Vorhaben 2025) galt damit als falsch — `round(358.5)` ist 358
    # (Fund vom 23.09.2026). Die kleine Zugabe fängt die Binärdarstellung ab
    # (35.850.000 / 100.000 ist nicht genau 358,5).
    def kaufmaennisch(x: float) -> float:
        return math.floor(x + 0.5 + 1e-9)
    return any(math.isclose(f(g / stufe) * stufe, w, rel_tol=1e-9, abs_tol=stufe * 1e-6)
               for f in (round, kaufmaennisch, math.floor))


def einheit_passt(z: Zahl, einheit: str | None) -> bool:
    """Ein Prozentsatz ist kein Eurobetrag und ein Jahr keins von beidem."""
    e = (einheit or "").strip()
    if z.art == "jahr":
        return e == "jahr"
    if e == "%":
        return z.art in ("%", "")
    if e in ("€", "eur", "euro"):
        return z.art in ("€", "")
    return z.art != "%"


# --------------------------------------------------------------------------- #
# Zeilen, Einrückung, Jahre
# --------------------------------------------------------------------------- #

_AUFZAEHLUNG = re.compile(r"^(\s*)([-*•·]|\d+[.)])\s+")


@dataclass
class Zeile:
    start: int
    ende: int
    text: str
    ebene: int
    eltern: int | None  # Index der übergeordneten Zeile
    jahre: list[tuple[int, int]] = field(default_factory=list)  # (Position in der Zeile, Jahr)


def zeilen(text: str) -> list[Zeile]:
    """Zerlegt einen Text in Zeilen mit Einrückungsebene und Elternzeile.

    Ebene = führende Leerzeichen mal zwei, plus eins für einen Spiegelstrich:
    „- x“ ganz links steht UNTER einer Kopfzeile ganz links, „  - davon …“
    unter „- …“. Eine Leerzeile beendet den Block.
    """
    aus: list[Zeile] = []
    pos = 0
    for roh in (text or "").split("\n"):
        start, ende = pos, pos + len(roh)
        pos = ende + 1
        if not roh.strip():
            aus.append(Zeile(start, ende, roh, -1, None))
            continue
        m = _AUFZAEHLUNG.match(roh)
        einzug = len(roh) - len(roh.lstrip(" \t"))
        ebene = einzug * 2 + (1 if m else 0)
        eltern = None
        for i in range(len(aus) - 1, -1, -1):
            if aus[i].ebene < 0:
                break
            if aus[i].ebene < ebene:
                eltern = i
                break
        masked = _DATUM.sub(lambda mm: " " * len(mm.group(0)), roh)
        jahre = [(j.start(), int(j.group(0))) for j in _JAHR.finditer(masked)
                 if not _ist_betrag(masked, j.end())]
        aus.append(Zeile(start, ende, roh, ebene, eltern, jahre))
    return aus


def _ist_betrag(text: str, ende: int) -> bool:
    """„2025 €“ ist ein Betrag, kein Jahr."""
    return bool(re.match(r"\s?(€|euro\b|eur\b|%|mio|mrd|tsd)", text[ende:ende + 6], re.I))


def _zeile_zu(zeilen_: list[Zeile], pos: int) -> int:
    for i, z in enumerate(zeilen_):
        if z.start <= pos <= z.ende:
            return i
    return len(zeilen_) - 1


#: Wie weit HINTER einer Zahl ein Jahr noch zu ihr gehört: „337 Mio. € (2025)“
#: ja, „337 Mio. € — 2024 waren es noch 295“ nicht.
_JAHR_DAHINTER_MAX = 14
_ANGEHAENGT = re.compile(r"\s*(\(|im jahr|jahr|für|fuer|in|zum|ende|stand)\s*", re.I)


def jahre_der_zahl(zeilen_: list[Zeile], z: Zahl, *, satz: bool = False) -> set[int]:
    """Welche Jahre die Zahl nach Aufbau des Textes trägt (leer = keins).

    ``satz=True`` (für Antworten): In der eigenen Zeile zählt nur der Satz, in
    dem die Zahl steht — Fließtext reiht mehrere Jahre in eine Zeile.
    """
    i = _zeile_zu(zeilen_, z.pos)
    zeile = zeilen_[i]
    p, q = z.pos - zeile.start, z.ende - zeile.start
    von, bis = 0, len(zeile.text)
    # In Antworten auch das Komma: „Ende 2025 lag er bei 337 Mio. €, 2024
    # waren es 295 Mio. €“ — und „ist 2026 gestiegen, von 3,74 € auf 4,04 €“
    # nennt für 3,74 € gar kein Jahr (gemessen 23.09., Gemini).
    grenze = r"[.!?;](?=\s)|\n" + (r"|,(?=\s)" if satz else "")
    for m in re.finditer(grenze, zeile.text):
        if m.end() <= p:
            von = m.end()
        elif m.start() >= q and bis == len(zeile.text):
            bis = m.start()
    # „stieg 2026 um 8 Prozent: von 3,74 € auf 4,04 €“ — der Ausgangswert
    # einer Veränderung trägt das Jahr davor, nicht das genannte.
    if satz and re.search(r"\bvon\s*$", zeile.text[von:p]) and \
            re.match(r"[^.!?;]{0,25}\bauf\b", zeile.text[q:bis]):
        return set()
    # Erst der Satz — auch im Kontext: Die Beschluss-Zeilen von Frag den Rat
    # sind ein Absatz aus Titel, Datum, Vorlagentext; das letzte Jahr davor
    # in der ganzen Zeile gehört oft zu einem anderen Satz.
    eigen = _jahr_in_zeile(zeile, p, q, von, bis)
    if eigen is None and not satz:
        eigen = _jahr_in_zeile(zeile, p, q)
    if eigen is not None:
        return {eigen}
    return _jahre_der_eltern(zeilen_, zeile.eltern)


def _jahr_in_zeile(zeile: Zeile, p: int, q: int, von: int = 0, bis: int | None = None) -> int | None:
    bis = len(zeile.text) if bis is None else bis
    # Ein Jahr, das die Zahl ausdrücklich anhängt, geht vor: „von 588,2 Mio. €
    # im Jahr 2020 auf 850,2 Mio. € im Jahr 2025“ — 850,2 gehört zu 2025,
    # nicht zum 2020 davor.
    for s, j in zeile.jahre:
        if q <= s < min(bis, q + _JAHR_DAHINTER_MAX) and _ANGEHAENGT.fullmatch(zeile.text[q:s]):
            return j
    vorher = [j for (s, j) in zeile.jahre if von <= s < p]
    if vorher:
        return vorher[-1]
    dahinter = [j for (s, j) in zeile.jahre if q <= s < min(bis, q + _JAHR_DAHINTER_MAX)]
    return dahinter[0] if dahinter else None


def _jahre_der_eltern(zeilen_: list[Zeile], k: int | None) -> set[int]:
    """Das Jahr, unter dem eine Elternzeile steht.

    Trägt die Elternzeile selbst einen Betrag („Höchster Wert der Reihe (sie
    beginnt 2010): 2020 mit 70.481.000 €“), gilt das Jahr ihres ERSTEN
    Betrags — so liest man die eingerückten „davon“-Zeilen darunter. Der
    erste, nicht der letzte: „Wirtschaftsplan 2026: Ergebnis 711.250 €; im
    Plan 2025 waren es 627.511 €“ handelt von 2026, der Nachsatz ist
    Vergleich. Sonst (eine Kopfzeile) alle ihre Jahre, und ohne Jahre die
    nächste Ebene darüber.
    """
    while k is not None:
        eltern = zeilen_[k]
        if eltern.jahre:
            betraege = [z for z in zahlen(eltern.text) if z.art in ("€", "%")]
            if betraege:
                z = betraege[0]
                j = _jahr_in_zeile(eltern, z.pos, z.ende)
                if j is not None:
                    return {j}
            return {j for (_, j) in eltern.jahre}
        k = eltern.eltern
    return set()


def kette(zeilen_: list[Zeile], i: int) -> str:
    """Die Zeile samt allen übergeordneten — für den Bezeichnungs-Test."""
    teile = []
    k: int | None = i
    while k is not None:
        teile.append(zeilen_[k].text)
        k = zeilen_[k].eltern
    return "\n".join(teile)


# --------------------------------------------------------------------------- #
# Text
# --------------------------------------------------------------------------- #

def falte(text: str) -> str:
    t = (text or "").lower()
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss"), ("­", ""),
                 ("*innen", "innen"), (":innen", "innen")):
        t = t.replace(a, b)
    return re.sub(r"\s+", " ", t)


def _alternativen(eintrag: Any) -> list[str]:
    return [str(x) for x in eintrag] if isinstance(eintrag, list) else [str(eintrag)]


def text_findet(text: str, muss: list[Any]) -> list[str]:
    """Die Einträge von ``muss``, die im Text FEHLEN (leer = alle da).

    Ein Eintrag ist ein Wort oder eine Liste gleichwertiger Wörter.
    """
    t = falte(text)
    return [" | ".join(_alternativen(e)) for e in muss
            if not any(falte(a) in t for a in _alternativen(e))]


# --------------------------------------------------------------------------- #
# Verweigerung
# --------------------------------------------------------------------------- #

_VERWEIGERT = re.compile("|".join([
    r"(liegt|liegen|habe|haben|hab|steht|stehen|finde|kenne|sind|ist|gibt es)\b[^.!?\n]{0,60}"
    r"\b(nicht|keine|keinen|kein)\b[^.!?\n]{0,60}"
    r"\b(vor|daten|angaben|zahlen|zahl|informationen|kontext|unterlagen|werte|vergleich\w*|bestand)",
    r"\b(nicht|keine|keinen|kein)\b[^.!?\n]{0,40}\b(daten|angaben|zahlen|informationen|werte|"
    r"vergleichsdaten|vergleichszahlen)\b[^.!?\n]{0,40}\b(vor|vorhanden|enthalten|verfuegbar|"
    r"im bestand|dabei|genannt)",
    r"kann ich (dir |ihnen |euch )?(leider |daher |deshalb |hier |so )?(nicht|keine|kein)",
    r"laesst sich (mit|aus) [^.!?\n]{0,60}nicht",
    r"nicht (beantworten|sagen|nennen|beurteilen|einordnen|vergleichen)",
    r"(daten|angaben|unterlagen|zahlen) (geben|sagen|nennen|enthalten) (das|dazu|darueber|hierzu) "
    r"(nicht|nichts|keine)",
    r"(dazu|darueber|hierzu) (habe|liegen|stehen|finde) (ich )?(keine|nicht|nichts)",
    r"\bnicht im bestand\b|\bnicht in den (daten|unterlagen|angaben)\b",
    # „Die Unterlagen nennen keinen Schuldenstand für Osnabrück“ (GPT-6 Luna, 23.09.)
    # „Die Ratsunterlagen geben keine Auskunft über …“ — Geminis Standardsatz
    r"\bkeine (direkte |genaue |konkrete )?auskunft\b",
    r"\b(seite|daten|unterlagen|angaben|quelle)\b[^.!?\n]{0,20}\bsagt?\b[^.!?\n]{0,10}\bnicht",
    r"\b(steht|stehen) bei uns nicht\b",
    r"\bnoch keine (ergebnisse|beschluesse|daten|zahlen|angaben)\b",
    r"(unterlagen|daten|angaben|quellen|zahlen|uebersicht|bestand|tabelle)\w*\b[^.!?\n]{0,60}"
    r"\b(nennen|enthalten|zeigen|haben|fuehren|liefern|weisen)\b[^.!?\n]{0,12}"
    r"\b(keine|keinen|kein|nichts)\b",
    # „ist in den vorliegenden Angaben nicht aufgeschlüsselt“
    # „… ist in den hier vorliegenden Angaben nicht genannt“ (GPT-6 Luna, 23.09.)
    r"\bnicht (aufgeschluesselt|ausgewiesen|enthalten|angegeben|verfuegbar|vorhanden|genannt)\b",
    # GPT-6 Luna nach dem Kontext-Nachzug (23.09.2026): „Die Hundesteuer ist
    # nicht einzeln ausgewiesen“, „Ein Schuldenvergleich … ist anhand der
    # vorliegenden Zahlen nicht möglich“ — beides richtige Absagen.
    r"\bnicht einzeln (aufgeschluesselt|ausgewiesen|aufgefuehrt|genannt)\b",
    r"\banhand der\b[^.!?\n]{0,60}\bnicht moeglich\b",
    # GPT-6 Luna, 23.09.: „geben dazu wenig her“, „lässt sich nicht feststellen“,
    # „geht aus den Unterlagen nicht hervor“, „ist nicht belegt“, „steht kein
    # Gehalt“, „ein Wolfsburger Vergleichswert fehlt“
    r"\bwenig her\b",
    r"laesst sich (daraus |damit |hier )?(nicht|kein|keine|keinen)\b",
    r"\bgeht\b[^.!?\n]{0,60}\bnicht hervor\b|\bnicht hervor\b",
    r"\bnicht belegt\b|\bbelegen (sie |die unterlagen )?nicht\b",
    r"\b(steht|stehen)\b[^.!?\n]{0,50}\b(nicht|kein|keine|keinen)\b",
    r"\b(vergleichswert|vergleichszahl|angaben|daten|zahlen|werte?)\w*\b[^.!?\n]{0,40}"
    r"\bfehl(t|en)\b",
]))


def verweigert(antwort: str) -> bool:
    """Sagt die Antwort, dass die Daten das nicht hergeben?"""
    return bool(_VERWEIGERT.search(falte(antwort)))


# --------------------------------------------------------------------------- #
# Kontext und Antwort gegen die Goldfakten
# --------------------------------------------------------------------------- #

@dataclass
class Befund:
    """Ein Goldfakt gegen einen Text: gefunden, wo, unter welchem Jahr."""

    status: str  # ok | fehlt | falsch_zugeordnet
    fundstellen: list[str] = field(default_factory=list)
    jahre: list[list[int]] = field(default_factory=list)

    def als_dict(self) -> dict:
        return {"status": self.status, "fundstellen": self.fundstellen[:3],
                "jahre": self.jahre[:3]}


def _auszug(text: str, z: Zahl, zeilen_: list[Zeile]) -> str:
    i = _zeile_zu(zeilen_, z.pos)
    return zeilen_[i].text.strip()[:220]


_RANG = {"ok": 0, "falsch_zugeordnet": 1, "fehlt": 2}


def zahl_im_text(gold: dict, text: str, *, satz: bool = False,
                 zahlen_: list[Zahl] | None = None,
                 zeilen_: list[Zeile] | None = None) -> Befund:
    """Steht die Goldzahl im Text — und unter ihrem Jahr (und ihrer Bezeichnung)?

    Zwei Erweiterungen des Fallformats, beide aus echten Fragen:

    * ``oder`` — gleichwertige Antworten mit eigenem Wert und Jahr. „Wie
      hoch sind die Schulden des Kernhaushalts?“ beantworten die Bilanz 2024
      (43,7 Mio. €) und die Kreditmarktschulden 2025 (40,8 Mio. €) beide
      richtig; eine Fall-Datei, die nur eine gelten lässt, mäße Geschmack.
    * ``teile`` — die Werte, aus denen sich der Goldwert rechnet und die
      genügen: Der Stellenplan nennt Beamte und Beschäftigte getrennt; wer
      beide nennt, hat die Summe genannt. Ebenso Plan und Ist für „wie weit
      lag es über dem Plan?“.
    """
    zs = zahlen_ if zahlen_ is not None else zahlen(text, woerter=satz)
    zl = zeilen_ if zeilen_ is not None else zeilen(text)
    kandidaten = [gold] + [{**gold, "oder": None, "teile": None, **alt}
                           for alt in (gold.get("oder") or [])]
    befunde = [_eine_zahl(g, text, satz, zs, zl) for g in kandidaten]
    bester = min(befunde, key=lambda b: _RANG[b.status])
    if bester.status != "ok" and gold.get("teile"):
        teile = [_eine_zahl({**gold, "wert": t, "oder": None, "teile": None}, text, satz, zs, zl)
                 for t in gold["teile"]]
        schlechtester = max(teile, key=lambda b: _RANG[b.status])
        if _RANG[schlechtester.status] < _RANG[bester.status]:
            return Befund(schlechtester.status,
                          [s for b in teile for s in b.fundstellen],
                          [j for b in teile for j in b.jahre])
    return bester


def _eine_zahl(gold: dict, text: str, satz: bool, zs: list[Zahl], zl: list[Zeile]) -> Befund:
    toleranz = float(gold.get("toleranz") or TOLERANZ_STANDARD)
    treffer = [z for z in zs if einheit_passt(z, gold.get("einheit"))
               and passt(z, float(gold["wert"]), toleranz)]
    if not treffer:
        return Befund("fehlt")
    jahr = gold.get("jahr")
    label = [falte(x) for x in (gold.get("label") or [])]
    ok_stellen, falsch = [], []
    for z in treffer:
        jahre = jahre_der_zahl(zl, z, satz=satz)
        passt_jahr = jahr is None or not jahre or int(jahr) in jahre
        passt_label = not label or any(
            lab in falte(kette(zl, _zeile_zu(zl, z.pos))) for lab in label)
        (ok_stellen if passt_jahr and passt_label else falsch).append((z, sorted(jahre)))
    if ok_stellen:
        return Befund("ok", [_auszug(text, z, zl) for z, _ in ok_stellen],
                      [j for _, j in ok_stellen])
    return Befund("falsch_zugeordnet", [_auszug(text, z, zl) for z, _ in falsch],
                  [j for _, j in falsch])


def id_im_text(gold: dict, text: str) -> Befund:
    wert = str(int(gold["wert"]))
    return Befund("ok" if re.search(rf"(?<!\d){wert}(?!\d)", text or "") else "fehlt")


def gold_im_text(gold: dict, text: str, *, satz: bool = False,
                 zahlen_: list[Zahl] | None = None,
                 zeilen_: list[Zeile] | None = None) -> Befund:
    art = gold.get("art")
    if art == "zahl":
        return zahl_im_text(gold, text, satz=satz, zahlen_=zahlen_, zeilen_=zeilen_)
    if art == "id":
        return id_im_text(gold, text)
    if art == "text":
        muss = gold.get("muss") or []
        # ``antwort_auch``: weitere Schreibweisen, die nur in der ANTWORT
        # gelten — „Juni 2026“ für den 01.06.2026, wo die Frage nicht nach dem
        # Tag fragt (``build_fakten_rat.monat_reicht``). Im Kontext muss das
        # genaue Datum stehen; sonst reichte irgendein Beschluss aus dem Juni.
        if satz and gold.get("antwort_auch"):
            muss = [_alternativen(m) + [str(a) for a in gold["antwort_auch"]] for m in muss]
        fehlt = text_findet(text, muss)
        return Befund("fehlt" if fehlt else "ok", fehlt)
    raise ValueError(f"unbekannte Goldart {art!r}")


#: Ein Satzende: Punkt vor einem Großbuchstaben — aber nicht nach einer
#: Abkürzung. „von 50 Mio. Euro auf 79 Mio. Euro“ ist EIN Satz.
_SATZENDE = re.compile(
    r"(?<!Mio)(?<!Mrd)(?<!Tsd)(?<!Nr)(?<!bzw)(?<!ca)(?<!rd)(?<!\d)[.!?](?=\s+[A-ZÄÖÜ*#\[(„\"])|\n")


def _satz_um(text: str, z: Zahl) -> str:
    """Der Satz, in dem die Zahl steht."""
    von, bis = 0, len(text)
    for m in _SATZENDE.finditer(text):
        if m.end() <= z.pos:
            von = m.end()
        elif m.start() >= z.ende:
            bis = m.start()
            break
    return text[von:bis]


def verboten_im_text(verbot: dict, antwort: str, zahlen_: list[Zahl],
                     zeilen_: list[Zeile]) -> str | None:
    """Die Verwechslung, falls die Antwort sie begeht — sonst ``None``.

    ``als_jahr`` macht aus dem Verbot eine Zuordnungsfrage: Die Vorjahres-
    zahl DARF in der Antwort stehen („2024 waren es 295 Mio.“), nur nicht
    als Wert des gefragten Jahres.
    """
    if verbot.get("art") == "text":
        t = falte(antwort)
        hit = [a for a in _alternativen(verbot.get("text") or verbot.get("muss") or [])
               if falte(a) in t]
        return f"„{hit[0]}“ — {verbot.get('grund', '')}" if hit else None
    toleranz = float(verbot.get("toleranz") or TOLERANZ_STANDARD)
    als_jahr = verbot.get("als_jahr")
    ausser = [falte(w) for w in verbot.get("ausser_im_satz_mit") or []]
    for z in zahlen_:
        if not einheit_passt(z, verbot.get("einheit")) or not passt(z, float(verbot["wert"]), toleranz):
            continue
        # ``ausser_im_satz_mit``: Die Zahl ist nur als DAS verboten, womit
        # sie verwechselt wird. Die Ausfallbürgschaft von 79 Mio. € als
        # Baupreis der Kongresshalle ist falsch, als Bürgschaft genannt
        # richtig — und traf bis 23.09.2026 beides (Gemini, zweimal).
        if ausser and any(w in falte(_satz_um(antwort, z)) for w in ausser):
            continue
        if als_jahr is not None:
            jahre = jahre_der_zahl(zeilen_, z, satz=True)
            if int(als_jahr) not in jahre:
                continue
        return f"{z.text} — {verbot.get('grund', '')}"
    return None


# --------------------------------------------------------------------------- #
# Erfundene Zahlen
# --------------------------------------------------------------------------- #

#: Abgeleitete Zahlen (Summe, Differenz, Anteil) gelten als gedeckt, wenn sie
#: so nah an einer Rechnung aus zwei Kontextzahlen liegen. Enger als
#: ``RUNDUNG_MAX``: Bei Hunderten von Paaren trifft eine grobe Angabe sonst
#: zufällig irgendeine Rechnung.
ABLEITUNG_MAX = 0.02
#: Mehr Kontextzahlen als das werden für die Ableitungen nicht gepaart — ein
#: Prompt von Frag den Rat trägt Hunderte, die meisten Kennungen und Seiten.
ABLEITUNG_ZAHLEN_MAX = 250


def _bedeutsam(z: Zahl) -> bool:
    """Welche Zahlen einer Antwort überhaupt erfunden sein können."""
    if z.art == "%":
        return True
    return z.art == "€" and abs(z.wert) >= 1


def erfundene_zahlen(antwort: str, kontext: str, frage: str = "") -> list[str]:
    """Beträge und Prozentsätze der Antwort, die weder im Kontext stehen noch
    sich aus zwei Kontextzahlen ableiten lassen."""
    kz = [z for z in zahlen(kontext) if z.art != "jahr"]
    fz = zahlen(frage)
    kandidaten = [z for z in zahlen(antwort) if _bedeutsam(z)]
    offen = [z for z in kandidaten
             if not any(passt(k, z.wert) or passt(z, k.wert) for k in kz)
             and not any(passt(f, z.wert) for f in fz)]
    if not offen:
        return []
    werte = sorted({abs(k.wert) for k in kz if k.wert}, reverse=True)[:ABLEITUNG_ZAHLEN_MAX]
    abgeleitet: list[float] = []
    for a, b in combinations(werte, 2):
        abgeleitet += [a + b, a - b, a / b, b / a, a / b * 100, b / a * 100,
                       (a - b) / b * 100, (a - b) / a * 100]
    abgeleitet.sort()
    aus = []
    import bisect
    for z in offen:
        w = abs(z.wert)
        lo = bisect.bisect_left(abgeleitet, w * (1 - ABLEITUNG_MAX))
        hi = bisect.bisect_right(abgeleitet, w * (1 + ABLEITUNG_MAX))
        if hi > lo:
            continue
        aus.append(z.text)
    return aus


# --------------------------------------------------------------------------- #
# Die Einteilung
# --------------------------------------------------------------------------- #

FEHLERARTEN = ("ok", "kontext_fehlt", "kontext_falsch_zugeordnet", "modell_ausgelassen",
               "modell_falsch", "modell_erfunden", "modell_verweigert_zu_unrecht")


def _ohne_frage(kontext: str, frage: str) -> str:
    """Die Frage selbst zählt nicht als Kontext — sonst stünde jedes Wort,
    nach dem gefragt wird, schon „im Prompt“."""
    return kontext.replace(frage, " ") if frage else kontext


def bewerten(fall: dict, kontext: str | None, antwort: str) -> dict:
    """Ein Fall: Kontext-Abdeckung, Antwort-Genauigkeit, Fehlerart.

    ``kontext=None`` heißt: Es gab keinen Modellaufruf (Lottis Wege ohne
    Modell) — dann trug der Codepfad keinen einzigen Fakt, und ein Fall mit
    Goldfakten ist ein Kontextfehler.
    """
    frage = fall.get("frage", "")
    gold = fall.get("gold") or []
    in_daten = fall.get("antwort_in_daten", True)
    kt = _ohne_frage(kontext or "", frage)
    kz, kl = zahlen(kt), zeilen(kt)
    az, al = zahlen(antwort, woerter=True), zeilen(antwort)

    kontext_befunde = [gold_im_text(g, kt, zahlen_=kz, zeilen_=kl) for g in gold]
    antwort_befunde = [gold_im_text(g, antwort, satz=True, zahlen_=az, zeilen_=al) for g in gold]
    verstoesse = [v for v in (verboten_im_text(vb, antwort, az, al)
                              for vb in fall.get("verboten") or []) if v]
    erfunden = erfundene_zahlen(antwort, kontext or "", frage) if kontext is not None else []
    abgelehnt = verweigert(antwort)

    k_fehlt = [i for i, b in enumerate(kontext_befunde) if b.status == "fehlt"]
    k_falsch = [i for i, b in enumerate(kontext_befunde) if b.status == "falsch_zugeordnet"]
    kontext_ok = kontext is not None and not k_fehlt and not k_falsch
    if kontext is None and not gold:
        kontext_ok = True

    pflicht = [i for i, g in enumerate(gold) if g.get("pflicht", True)]
    a_fehlt = [i for i in pflicht if antwort_befunde[i].status == "fehlt"]
    a_falsch = [i for i in pflicht if antwort_befunde[i].status == "falsch_zugeordnet"]

    if not in_daten:
        antwort_ok = abgelehnt and not verstoesse and not erfunden
    else:
        antwort_ok = not a_fehlt and not a_falsch and not verstoesse and not erfunden

    if k_fehlt or (kontext is None and gold):
        art = "kontext_fehlt"
    elif k_falsch:
        art = "kontext_falsch_zugeordnet"
    elif not in_daten:
        if antwort_ok:
            art = "ok"
        elif erfunden or verstoesse:
            art = "modell_erfunden"
        else:
            art = "modell_falsch"
    elif verstoesse or a_falsch:
        art = "modell_falsch"
    elif erfunden:
        art = "modell_erfunden"
    # „Zu Unrecht verweigert“ nur, wenn die Antwort KEINEN Pflichtfakt nennt —
    # wer das Datum nennt und dann sagt, Beschlüsse gebe es noch keine, hat
    # die Uhrzeit ausgelassen, nicht die Frage abgelehnt.
    elif a_fehlt and abgelehnt and len(a_fehlt) == len(pflicht):
        art = "modell_verweigert_zu_unrecht"
    elif a_fehlt:
        art = "modell_ausgelassen"
    else:
        art = "ok"

    def kurz(g: dict) -> str:
        if g.get("art") == "zahl":
            return f"{g.get('bezeichnung', '')} {g.get('jahr') or ''}: {g['wert']}".strip()
        if g.get("art") == "id":
            return f"Beschluss {g['wert']}"
        return " + ".join(" | ".join(_alternativen(e)) for e in g.get("muss") or [])

    return {
        "kontext_ok": kontext_ok,
        "antwort_ok": antwort_ok,
        "fehlerart": art,
        "gold": [{"fakt": kurz(g), "pflicht": g.get("pflicht", True),
                  "kontext": kb.als_dict(), "antwort": ab.als_dict()}
                 for g, kb, ab in zip(gold, kontext_befunde, antwort_befunde)],
        "verstoesse": verstoesse,
        "erfunden": erfunden,
        "verweigert": abgelehnt,
    }
