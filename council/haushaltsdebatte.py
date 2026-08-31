"""Der Streit ums Geld — die Haushaltsdebatte aus dem Ratsprotokoll.

Der Haushalts-Bereich zeigt neun Schichten Zahlen. Was keine davon zeigt: dass
über diese Zahlen gestritten wurde. Wer wollte was streichen, wer was
draufsetzen, wer hat wie abgestimmt. Die Zahlen stehen in jedem Open-Data-
Portal; die Auseinandersetzung steht nur im Protokoll.

Drei Schichten, drei Herkünfte
------------------------------
1. **Die Anträge** — ``council_decisions`` mit ``kind='subvote'``. Der
   Protokoll-Parser legt je Änderungsliste eine Zeile an; im ``title`` steht,
   wer sie eingebracht hat, in ``outcome``, ob sie durchkam. Das ist die
   belastbarste Schicht: Sie ist bereits geerntet und je Zeile abgestimmt.
   Was sie **nicht** hergibt, ist der *Inhalt* der Liste — welche Position um
   welchen Betrag verschoben werden sollte. Die Einzelpositionen stecken in
   den Anlagen-PDFs der Vorlage, die im Bestand nicht als Volltext liegen.
   Deshalb steht auf der Seite „welche Liste", nicht „welche Position".
2. **Die Debatte** — der Volltext aus ``council_protocols.raw_text``,
   absatzweise zerlegt. Ratsprotokolle referieren in indirekter Rede
   („Ratsherr X betont, dass …"); dieser Wortlaut ist die Quelle, nicht eine
   Zusammenfassung davon. Hier wird **nichts** durch ein Sprachmodell
   geschickt: Was auf der Seite steht, steht so im Protokoll, und der Weg
   dahin ist eine Regex, die jeder nachrechnen kann.
3. **Das Ergebnis** — die Beschlusszeile der Haushaltssatzung selbst.

Warum deterministisch statt LLM
-------------------------------
``council_wortbeitraege`` gibt es bereits — LLM-extrahiert, aber nur für eine
Handvoll Sitzungen. Diese Seite nimmt sie **nicht**: Wären die einen Jahrgänge
modellgelesen und die anderen regex-gelesen, hinge die Länge und Auswahl der
Zitate daran, welcher Jahrgang zufällig durch welches Verfahren lief — und
damit auch, welche Fraktion wie ausführlich zu Wort kommt. Ein Verfahren für
alle Jahrgänge ist hier keine Bequemlichkeit, sondern die Bedingung dafür,
dass die Auswahl niemanden bevorzugt.

Die Fraktionszuordnung
----------------------
Das Protokoll nennt Redner:innen ohne Fraktion („Ratsherr Baak führt aus …").
Die Fraktion kommt aus ``council_attendance`` **derselben Sitzung** — also aus
der Anwesenheitsliste, die im selben Dokument steht. Das ist wichtig, weil
Fraktionen wandern: Wer 2023 für Die Linke sprach, saß 2025 für das BSW.

Zwei Fallen sind hier eingebaut behandelt:

- **Gruppe ≠ Fraktion.** Das Label wird durch
  :func:`council.parties.faction_label` gereicht, nicht durch
  ``normalize_party`` — sonst würde „FDP/Volt" zu „FDP" kollabieren und
  Ratsherr Lükermann (Volt) als FDP-Mann erscheinen.
- **Namensvettern.** Kurt Bernhardt (Grüne) und Lidia Bernhardt (AfD) saßen
  gemeinsam im Rat, ebenso Michael und Rita Schilling sowie Dr. Georg Rohe
  (FDP/Volt) und Dr. Sebastian Rohe (Grüne). Steht im Protokoll nur der
  Nachname, wird **keine** Fraktion behauptet (``fraktion=None``,
  ``fraktion_unklar=True``) — lieber eine Lücke als eine falsche Zuordnung.
  Wo das Protokoll den Vornamen mitschreibt („Ratsherr Dr. Sebastian Rohe"),
  löst der die Namensgleichheit auf; wo die Anrede es tut („Ratsfrau
  Bernhardt" ist Lidia, „Ratsherr Bernhardt" ist Kurt), ebenfalls.
"""
from __future__ import annotations

import hashlib
import re
from collections import OrderedDict
from dataclasses import dataclass

from council.parties import faction_label

# ---------------------------------------------------------------- Protokolltext

# Seitenfuß des RIS-PDF. Steht mitten im Fließtext und zerschneidet sonst Sätze.
# Der Zeilenumbruch im PDF trennt gelegentlich das S ab („S eite: 8/23").
_SEITE = re.compile(r"^[ \t]*S[ \t]?eite:[ \t]*\d+[ \t]*/[ \t]*\d+[ \t]*$", re.M)

# Silbentrennung am Zeilenende: kleiner Folgebuchstabe → Trennstrich weg
# („Auszah-\nlung" → „Auszahlung"), großer → echter Bindestrich im Kompositum
# („Haushalts-\nMehrheit" → „Haushalts-Mehrheit").
_TRENN_KLEIN = re.compile(r"(\w)-[ \t]*\r?\n[ \t]*([a-zäöüß])")
_TRENN_GROSS = re.compile(r"(\w)-[ \t]*\r?\n[ \t]*([A-ZÄÖÜ])")


# Die PDF-Textextraktion setzt gelegentlich den ERSTEN Buchstaben eines
# Absatzes auf eine eigene Zeile („R\natsherr Prange verweist …"). Betrifft
# 2020 und 2024 spürbar, 2021/2023/2025 gar nicht — ohne diese Reparatur
# verlieren genau die beiden Jahrgänge ihre Reden, und zwar unterschiedlich
# viele je Fraktion. Das ist also keine Kosmetik, sondern Gleichbehandlung.
_ABGERISSEN = re.compile(r"(?m)^([A-ZÄÖÜ])[ \t]*\r?\n[ \t]*(?=[a-zäöüß])")

# Leerzeichen vor einem Bindestrich, der zwei Wortteile verbindet
# („Eilers -Dörfler", „FDP -Fraktion") — ebenfalls ein Extraktionsartefakt.
_BINDESTRICH = re.compile(r"(\w)[ \t]+-(?=[\wÄÖÜäöüß])")


def saeubern(text: str) -> str:
    """Seitenfüße raus, Silbentrennung und Extraktionsartefakte zurücknehmen.
    Zeilenumbrüche bleiben — die Absatzstruktur wird später gebraucht."""
    text = _SEITE.sub("", text)
    text = _ABGERISSEN.sub(r"\1", text)
    text = _TRENN_KLEIN.sub(r"\1\2", text)
    text = _TRENN_GROSS.sub(r"\1-\2", text)
    return _BINDESTRICH.sub(r"\1-", text)


def _glatt(text: str) -> str:
    """Ein Absatz als eine Zeile."""
    return re.sub(r"[ \t\r\n]+", " ", text).strip()


# --------------------------------------------------------------- TOP-Abschnitt

_TOP_ANKER = re.compile(r"(?:^|\n)[ \t]*zu[ \t]+([\d.]+)[ \t]")


def top_abschnitt(text: str, top: str, bis_unterpunkt: bool = False) -> str:
    """Der Protokollabschnitt zu einem Tagesordnungspunkt.

    Der Rat berät die Haushaltspunkte gemeinsam („Ratsvorsitzender Harms
    erinnert zunächst daran, dass die Tagesordnungspunkte 10.1 bis 10.6
    gemeinsam behandelt werden"). Daraus folgt der Zuschnitt:

    - Die **Debatte** steht unter dem Oberpunkt, vor dem ersten Unterpunkt —
      dafür ``bis_unterpunkt=True``.
    - Die **Abstimmungen** stehen in den Unterpunkten; wer sie braucht, nimmt
      den vollen Abschnitt.

    Der Schnitt vor dem ersten Unterpunkt ist nicht nur Ordnung: Ohne ihn
    landen die Abstimmungsblöcke („Änderungsliste der CDU-Fraktion —
    mehrheitlich abgelehnt") im letzten Redebeitrag und lesen sich dort wie
    seine Worte."""
    top = top.rstrip(".")
    start = None
    for m in _TOP_ANKER.finditer(text):
        if m.group(1).rstrip(".") == top:
            start = m.end()
            break
    if start is None:
        return ""
    ende = len(text)
    for m in _TOP_ANKER.finditer(text, start):
        nr = m.group(1).rstrip(".")
        if not nr.startswith(top + "."):
            ende = m.start()
            break
        if bis_unterpunkt:
            ende = m.start()
            break
    return text[start:ende]


# ------------------------------------------------------------------ Wortbeiträge

# Anreden, mit denen Oldenburger Protokolle Redner:innen einführen.
_ANREDEN = (
    "Ratsvorsitzender", "Ratsvorsitzende", "Ratsherr", "Ratsfrau",
    "Oberbürgermeisterin", "Oberbürgermeister", "Bürgermeisterin", "Bürgermeister",
    "Erster Stadtrat", "Erste Stadträtin", "Stadtkämmerin", "Stadtkämmerer",
    "Stadtbaurätin", "Stadtbaurat", "Stadträtin", "Stadtrat",
)
# Längere Anrede zuerst, sonst schluckt „Stadtrat" das „Erster Stadtrat".
_ANREDE_RE = re.compile(
    r"^[ \t]*(" + "|".join(sorted((re.escape(a) for a in _ANREDEN), key=len, reverse=True)) + r")[ \t]+",
    re.M,
)

# Rollen ohne Fraktion. Die Verwaltung sitzt nicht für eine Fraktion im Rat,
# und die Sitzungsleitung spricht als Leitung — beides ist keine fehlende
# Zuordnung, sondern die Rolle. Besonders wichtig bei der Leitung: Sie ruft
# jeden Punkt auf und kommt dadurch vielfach häufiger vor als jede Fraktion;
# ihre Beiträge deren Fraktion zuzurechnen, würde die Bilanz kippen (2020
# stellte die Sitzungsleitung allein 22 von 40 Wortmeldungen).
_LEITUNG = ("ratsvorsitzender", "ratsvorsitzende")
_VERWALTUNG = (
    "oberbürgermeister", "oberbürgermeisterin", "bürgermeister", "bürgermeisterin",
    "stadtkämmerer", "stadtkämmerin", "stadtbaurat", "stadtbaurätin",
    "stadtrat", "stadträtin", "erster stadtrat", "erste stadträtin",
)

# Zeilen, an denen ein Wortbeitrag endet: ab hier protokolliert das Dokument
# nicht mehr Rede, sondern Verfahren.
#
# Bewusst eng gefasst. Ein früherer Versuch stoppte auch auf „Abstimmung" und
# „Änderungsliste" ohne Doppelpunkt — beide Wörter stehen aber mitten in
# Reden („… die heute zur\nAbstimmung vorgelegt würden"), und weil der
# Zeilenumbruch im PDF beliebig fällt, schnitt das Rede ab: Der Beitrag der
# Grünen zum Haushalt 2024 schrumpfte so von rund 2.400 auf 314 Zeichen. Eine
# Abschneideregel, die je nach Wortwahl zuschlägt, kürzt Fraktionen
# unterschiedlich stark — deshalb hier nur, was ohne Zweifel Verfahren ist.
_STOPP = re.compile(
    r"^[ \t]*(?:Beschluss:|Abstimmung(?:sergebnis)?:|Die Ratsmitglieder signalisieren|"
    r"[-–][ \t]*(?:einstimmig|mehrheitlich)\b|Vorlage:[ \t]*\d)",
    re.M,
)

# Ein Wortbeitrag beginnt nach einem abgeschlossenen Satz oder am Absatzanfang.
# „…Ratsfrau Finke, Ratsherr Paul und dann Ratsherr Sander" ist die
# Rednerliste INNERHALB einer Rede — dort steht davor ein Komma, kein Punkt.
_SATZENDE = ".!?:)\"“”'’»"

# Mindestlänge eines Wortbeitrags. Kürzeres ist im Protokoll durchweg
# Verfahren („Ratsvorsitzender Harms lässt abstimmen."), keine Rede.
MIN_ZEICHEN = 180


_LEERZEILE_DAVOR = re.compile(r"\n[ \t]*\n[ \t]*\Z")


def _beginnt_beitrag(text: str, pos: int) -> bool:
    davor = text[:pos]
    if not davor.strip():
        return True
    if _LEERZEILE_DAVOR.search(davor):
        return True
    return davor.rstrip()[-1] in _SATZENDE


def _schluessel(name: str) -> str:
    """Vergleichsform eines Namens: ohne Titel, ohne Leerzeichen, ohne
    Bindestriche, klein. Fängt die Extraktionsartefakte des RIS-PDF ab, das
    mitten im Namen ein Leerzeichen setzt („Pi echotta", „P range") oder vor
    dem Bindestrich („Niewerth -Baumann")."""
    ohne_titel = re.sub(r"\b(?:Dr|Prof|h\.c)\.", " ", name)
    return re.sub(r"[^\wäöüßÄÖÜ]", "", ohne_titel).lower()


@dataclass
class Wortbeitrag:
    """Ein Redebeitrag, so wie das Protokoll ihn referiert."""

    anrede: str                     # „Ratsherr", „Oberbürgermeister" …
    name: str                       # Anzeigename (aus der Anwesenheitsliste, sonst wie im Protokoll)
    text: str                       # Wortlaut des Protokolls, geglättet
    fraktion: str | None = None
    fraktion_unklar: bool = False
    role: str = "rat"              # rat | verwaltung | leitung

    def als_dict(self) -> dict:
        return {
            "anrede": self.anrede,
            "name": self.name,
            "text": self.text,
            "fraktion": self.fraktion,
            "fraktion_unklar": self.fraktion_unklar,
            "role": self.role,
            "zeichen": len(self.text),
        }


def _personen_index(anwesende: list[dict]) -> dict[str, list[dict]]:
    """Vergleichsform eines Namens → Anwesende.

    Jede Person steht unter **allen Endstücken** ihres Namens: „Thorsten van
    Ellen" unter „vanellen" und „ellen", „Dr. Sebastian Rohe" unter „rohe"
    und „sebastianrohe". Das deckt beide Richtungen ab, in die Protokolle
    abweichen — Namenspartikel, die im Nordwesten häufig sind und die das
    Protokoll mitschreibt („Ratsherr van Ellen"), und Vornamen, die es nur
    dann mitschreibt, wenn es Namensvettern auseinanderhalten muss
    („Ratsherr Dr. Sebastian Rohe").

    Der volle Name ist der Schlüssel, der Namensvettern auflöst: „Sebastian
    Rohe" trifft genau einen, „Rohe" beide."""
    idx: dict[str, list[dict]] = {}
    for p in anwesende:
        name = (p.get("name") or "").strip()
        if not name:
            continue
        teile = [t for t in name.split() if not t.endswith(".")]
        if not teile:
            continue
        formen = {_schluessel(teile[-1].split("-")[-1])}
        for k in range(1, len(teile) + 1):
            formen.add(_schluessel(" ".join(teile[-k:])))
        for form in formen:
            if form:
                idx.setdefault(form, []).append(p)
    return idx


# Titel vor dem Namen („Ratsherr Dr. Onken", „Ratsfrau Prof. Dr. …").
_VORTITEL = re.compile(r"^(?:(?:Dr|Prof|h\.c)\.[ \t]*)+")
# So weit hinter der Anrede kann ein Name reichen.
_NAMENSFENSTER = 42


def _finde_person(rest: str, index: dict[str, list[dict]]) -> tuple[list[dict], str]:
    """Wer spricht? ``rest`` ist der Text direkt hinter der Anrede.

    Statt den Namen aus dem PDF zu raten, wird gegen die Anwesenheitsliste
    **derselben Sitzung** geprüft: Der Name steht unmittelbar hinter der
    Anrede, also wird genau dort der **längste passende** Eintrag gesucht.
    Weil die Vergleichsform Leerzeichen und Bindestriche wegwirft, findet
    „Pi echotta betont …" die Ratsfrau Piechotta und „Niewerth -Baumann" die
    Ratsfrau Niewerth-Baumann — beides Artefakte der PDF-Extraktion.

    Der Anker am Anfang ist wichtig: Ein Fenster, das irgendwo einen bekannten
    Namen sucht, findet in „Ratsherr Höpken dankt Stadtkämmerin Dr. Figura …"
    die Kämmerin und schreibt ihr die Rede zu.

    Rückgabe: (Kandidaten, im Protokoll gefundene Schreibweise)."""
    fenster = rest[:_NAMENSFENSTER]
    vorspann = _VORTITEL.match(fenster)
    ab = vorspann.end() if vorspann else 0
    treffer: tuple[int, list[dict], str] = (0, [], "")
    for ende in range(len(fenster), ab, -1):
        kand = _schluessel(fenster[ab:ende])
        if not kand or len(kand) <= treffer[0]:
            continue
        personen = index.get(kand)
        if personen:
            treffer = (len(kand), personen, fenster[ab:ende].strip())
            break
    return treffer[1], treffer[2]


def _vorname(name: str) -> str:
    teile = [t for t in name.split() if not t.endswith(".")]
    return teile[0] if teile else ""


_NOTNAME = re.compile(r"^((?:(?:Dr|Prof)\.[ \t]+)*[A-ZÄÖÜ][\wäöüß]*(?:-[A-ZÄÖÜ][\wäöüß]*)?)")


def debatte(section: str, anwesende: list[dict]) -> list[Wortbeitrag]:
    """Zerlegt einen Protokollabschnitt in Redebeiträge und hängt jedem die
    Fraktion aus der Anwesenheitsliste derselben Sitzung an.

    Der Schnitt läuft über die Anrede am Zeilenanfang, nicht über Leerzeilen:
    Die Protokolle bis 2020 setzen zwischen zwei Reden keine Leerzeile, die ab
    2021 schon. Bleibt eine Person mehrdeutig (Namensvettern im Rat), bleibt
    die Fraktion leer und ``fraktion_unklar`` steht auf ``True``."""
    index = _personen_index(anwesende)
    treffer = [m for m in _ANREDE_RE.finditer(section) if _beginnt_beitrag(section, m.start())]
    result: list[Wortbeitrag] = []
    for i, m in enumerate(treffer):
        ende = treffer[i + 1].start() if i + 1 < len(treffer) else len(section)
        roh = section[m.start():ende]
        stopp = _STOPP.search(roh, m.end() - m.start())
        if stopp:
            roh = roh[: stopp.start()]
        text = _glatt(roh)
        if len(text) < MIN_ZEICHEN:
            continue

        anrede = m.group(1)
        niedrig = anrede.lower()
        role = "leitung" if niedrig in _LEITUNG else "verwaltung" if niedrig in _VERWALTUNG else "rat"

        kandidaten, geschrieben = _finde_person(section[m.end():ende], index)
        if kandidaten:
            name = kandidaten[0]["name"] if len(kandidaten) == 1 else geschrieben
        else:
            notfall = _NOTNAME.match(_glatt(section[m.end():ende]))
            name = notfall.group(1) if notfall else geschrieben or "unbekannt"

        beitrag = Wortbeitrag(anrede=anrede, name=name, text=text, role=role)
        if role == "rat":
            if len(kandidaten) == 1:
                beitrag.fraktion = _fraktion_von(kandidaten[0])
            elif len(kandidaten) > 1:
                beitrag.fraktion_unklar = True
        result.append(beitrag)
    return result


#: Wie viele zerlegte Debatten gleichzeitig im Gedächtnis bleiben. Ein Aufruf
#: von ``/haushalt/streit`` fragt rund sechzehn (zwei Stationen je Jahrgang,
#: acht Jahrgänge); vierundsechzig lassen Luft für parallele Abfragen, ohne
#: dass der Web-Prozess nennenswert wächst — ein zerlegter Jahrgang sind ein
#: paar Dutzend Wortbeiträge, keine Protokolle.
_GEDAECHTNIS_MAX = 64
_gedaechtnis: OrderedDict[str, list[dict]] = OrderedDict()


def _gedaechtnis_schluessel(text: str, top: str, anwesende: list[dict]) -> str:
    """Ein Fingerabdruck über **alles**, was das Ergebnis bestimmt.

    Genau darauf beruht, dass dieses Gedächtnis nichts veralten lässt: Ändert
    sich das Protokoll, der Tagesordnungspunkt oder die Anwesenheitsliste,
    ändert sich der Schlüssel, und es wird neu gerechnet. Ein Eintrag, der
    nicht mehr stimmen kann, wird also nie gefunden — er muss nicht
    weggeräumt werden."""
    h = hashlib.sha256()
    h.update(text.encode("utf-8"))
    h.update(b"\x00")
    h.update(top.encode("utf-8"))
    for a in anwesende:
        h.update(b"\x00")
        h.update(f"{a.get('name')}\x1f{a.get('party')}\x1f{a.get('role')}"
                 .encode("utf-8"))
    return h.hexdigest()


def debatte_zu_top(text: str, top: str, anwesende: list[dict]) -> list[dict]:
    """Säubern, Abschnitt schneiden, zerlegen — die drei Schritte, die
    ``/haushalt/streit`` je Station braucht, mit Gedächtnis über den Inhalt.

    Die Seite rechnet bewusst **beim Lesen** und führt keinen eigenen
    Datenbestand: Damit kann sie nicht veralten, und ein nachgetragenes
    Protokoll erscheint ohne Backfill. Das ist richtig und bleibt so — nur
    kostete es bis 08/2026 bei **jedem** Aufruf rund sechzehn vollständige
    Ratsprotokolle: fünf Regex-Durchgänge über den ganzen Text, zwei Scans für
    den Abschnitt, dann die Zerlegung. Die teuerste Seite des Bereichs, und
    das Ergebnis war jedes Mal dasselbe.

    Ein Gedächtnis über den **Inhalt** löst das, ohne die Zusage aufzugeben:
    Der Schlüssel deckt Protokolltext, Tagesordnungspunkt und
    Anwesenheitsliste ab, also alles, woraus gerechnet wird. Ein Treffer ist
    damit dasselbe wie ein Neuberechnen — nur ohne die Arbeit. Kein Cron,
    keine Tabelle, kein Backfill und nichts, was ungültig werden könnte.

    Zurück kommen **Kopien**: Die Listen gehen in eine API-Antwort, und ein
    Aufrufer, der daran herumschreibt, änderte sonst den Eintrag für alle
    folgenden."""
    schluessel = _gedaechtnis_schluessel(text, top, anwesende)
    gemerkt = _gedaechtnis.get(schluessel)
    if gemerkt is None:
        section = top_abschnitt(saeubern(text), top, bis_unterpunkt=True)
        gemerkt = [b.als_dict() for b in debatte(section, anwesende)]
        _gedaechtnis[schluessel] = gemerkt
        while len(_gedaechtnis) > _GEDAECHTNIS_MAX:
            _gedaechtnis.popitem(last=False)
    else:
        _gedaechtnis.move_to_end(schluessel)
    return [dict(b) for b in gemerkt]


def gedaechtnis_leeren() -> None:
    """Das Debatten-Gedächtnis vergessen — für Tests, die den Rechenweg
    selbst prüfen wollen."""
    _gedaechtnis.clear()


def _fraktion_von(person: dict) -> str | None:
    """Gruppen-bewusstes Fraktionslabel einer Person.

    ``faction_label`` kennt die Fraktionen der laufenden und der letzten
    Wahlperiode; ältere (etwa WFO-LKR, 2016–2021) fallen dort durchs Raster
    und kämen ohne Label auf die Seite — ausgerechnet die kleinen. Deshalb
    fällt die Zuordnung auf das **rohe Anwesenheits-Label** zurück: Das steht
    so im selben Protokoll und ist damit belegt, auch wenn es keine
    kanonische Schreibweise hat."""
    roh = re.sub(r"\s+", " ", (person.get("party") or "").strip())
    label = faction_label(roh)
    if label == "parteilos":
        # Kein fehlender Wert: Ratsmitglieder ohne Fraktion gibt es wirklich.
        return "parteilos" if not roh else roh
    return label or roh or None


# ------------------------------------------------------------------- Anträge

# Die Verwaltung bringt eigene Änderungslisten ein („Änderungsliste Verwaltung I").
# Das ist kein Fraktionsantrag, sondern die Fortschreibung des Entwurfs, und
# gehört auf der Seite in eine eigene Zeile — sonst sieht es aus, als hätte
# eine Fraktion neun Anträge gestellt und alle gewonnen.
_VERWALTUNGSLISTE = re.compile(r"\bVerwaltung\b", re.I)
# Zeilen, die nicht ein Antrag sind, sondern die Schlussabstimmung darüber.
_SAMMELABSTIMMUNG = re.compile(
    r"^\s*(?:Abstimmung über den |So geänderte[rns]?\b|Der so geänderte)", re.I
)


@dataclass
class Antrag:
    """Eine Änderungsliste, so wie das Protokoll sie benennt und abstimmt."""

    titel: str
    outcome: str | None
    vote: str | None
    urheber: str | None       # gruppen-bewusstes Label, None bei Verwaltung
    ist_verwaltung: bool
    top: str | None
    ksinr: int

    def als_dict(self) -> dict:
        return {
            "titel": self.titel,
            "outcome": self.outcome,
            "vote": self.vote,
            "urheber": self.urheber,
            "ist_verwaltung": self.ist_verwaltung,
            "top": self.top,
            "ksinr": self.ksinr,
        }


# Fraktions-/Gruppennamen, wie sie in Änderungslisten-Titeln vorkommen.
# Reihenfolge: spezifisch vor allgemein („Gruppe FDP/Volt" vor „FDP").
_URHEBER_MUSTER: list[tuple[re.Pattern, str]] = [
    (re.compile(r"FDP\s*/\s*Volt", re.I), "FDP/Volt"),
    (re.compile(r"Linke\.?\s*/\s*Piraten|Linke\.?\s*und\s*Piraten", re.I), "Die Linke/Piraten"),
    (re.compile(r"Für\s+Oldenburg", re.I), "Für Oldenburg"),
    (re.compile(r"WFO[- ]?LKR", re.I), "WFO-LKR"),
    (re.compile(r"Bündnis\s*90\s*/?\s*Die\s+Grünen|Grüne[rn]?\b", re.I), "Grüne"),
    (re.compile(r"\bBSW\b", re.I), "BSW"),
    (re.compile(r"\bDie\s+Linke\b|\bLinke\b", re.I), "Die Linke"),
    (re.compile(r"\bPiraten", re.I), "Piraten"),
    (re.compile(r"\bAfD\b", re.I), "AfD"),
    (re.compile(r"\bSPD\b", re.I), "SPD"),
    (re.compile(r"\bCDU\b", re.I), "CDU"),
    (re.compile(r"\bFDP\b", re.I), "FDP"),
    (re.compile(r"\bVolt\b", re.I), "Volt"),
]


def urheber(titel: str) -> list[str]:
    """Alle Fraktionen/Gruppen, die eine Änderungsliste tragen — in der
    Reihenfolge, in der das Protokoll sie nennt.

    Gemeinsame Listen sind der Normalfall („Änderungsliste der Fraktionen SPD,
    CDU und FDP"); sie zählen für **alle** Beteiligten, nicht für die
    erstgenannte."""
    # Spezifische Muster zuerst: Wer „FDP/Volt" belegt hat, gibt die Stelle
    # nicht mehr für die Einzeltreffer „FDP" und „Volt" frei.
    belegt: list[tuple[int, int]] = []
    gefunden: list[tuple[int, str]] = []
    for muster, label in _URHEBER_MUSTER:
        for m in muster.finditer(titel):
            if any(m.start() < b and a < m.end() for a, b in belegt):
                continue
            belegt.append((m.start(), m.end()))
            gefunden.append((m.start(), label))
    raus: list[str] = []
    for _, label in sorted(gefunden):
        if label not in raus:
            raus.append(label)
    return raus


def antrag_aus_zeile(zeile: dict) -> Antrag | None:
    """Macht aus einer ``subvote``-Zeile einen Antrag — oder ``None``, wenn die
    Zeile die Schlussabstimmung über das Ganze ist."""
    titel = (zeile.get("title") or "").strip()
    if not titel or _SAMMELABSTIMMUNG.match(titel):
        return None
    ist_verw = bool(_VERWALTUNGSLISTE.search(titel))
    traeger = [] if ist_verw else urheber(titel)
    return Antrag(
        titel=titel,
        outcome=zeile.get("outcome"),
        vote=zeile.get("vote"),
        urheber=" / ".join(traeger) if traeger else None,
        ist_verwaltung=ist_verw,
        top=zeile.get("item_number"),
        ksinr=zeile.get("ksinr"),
    )
