"""Die Geschäftsordnung des Rates — für Verfahrensfragen an „Frag den Rat" und Lotti.

**Wozu.** „Wie lange darf ein Ratsmitglied reden?", „Bis wann muss ich meine
Frage für die Einwohnerfragestunde einreichen?", „Was passiert bei
Stimmengleichheit?" — solche Fragen hat das Beschluss-Archiv nicht. Die
Antwort steht in der Geschäftsordnung, die sich der Rat für jede Wahlperiode
gibt (§ 69 NKomVG). Bis 10/2026 kannte Ratslotse sie nicht, und die Antwort
hing davon ab, ob zufällig ein „Geschäftsordnungsantrag auf Vertagung" unter
den Treffern stand.

**Woher der Text kommt.** Aus der Lesefassung, die die Stadt im Stadtrecht
unter Nr. 1.02 veröffentlicht — als ``rules_of_procedure.json`` im Repo,
erzeugt von ``scripts/fetch_rules_of_procedure.py``. Nicht in der Datenbank:
Der Wortlaut ändert sich einmal je Wahlperiode, und eine neue Fassung soll im
PR als Diff sichtbar sein. Satzungen sind amtliche Werke (§ 5 UrhG).

**Wann sie greift: an der FRAGE, deterministisch.** Wie beim Glossar und den
Erklärtexten (:mod:`kern.erklaerwissen`) entscheidet ein Wortfeld der Frage,
kein Sprachmodell. Der schwierige Teil sind die Fragen, die NICHT gemeint
sind: „Wie hat der Rat zum Stadion abgestimmt?" fragt nach einem Ergebnis,
„Wie wird im Rat abgestimmt?" nach der Regel. Deshalb sind die Auslöser eng,
und manche gelten nur, wenn die Frage zugleich den Rat, einen Ausschuss oder
eine Sitzung nennt (``_KONTEXT``). ``tests/test_rules_of_procedure.py`` hält
beide Richtungen fest.

**Was sie NICHT ist: ein Beschluss.** Der Wortlaut bekommt keine ``[id]``;
die Antwort nennt den Paragrafen. Und sie gilt für EINE Wahlperiode (§ 33) —
:func:`status` sagt, ob die gespeicherte Fassung noch die geltende ist.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path

DATA_FILE = Path(__file__).with_name("rules_of_procedure.json")

#: Höchstens so viele Paragrafen je Frage. Vier, weil eine Ausschuss-Frage
#: zur Rats-Regel den Verweis-Paragrafen braucht (§ 32: „gelten sinngemäß")
#: und eine Frage selten mehr als drei Regeln berührt — jeder weitere schiebt
#: die Beschlüsse im Prompt nach hinten.
MAX_SECTIONS = 4


@dataclass(frozen=True)
class Section:
    """Ein Paragraf, wie er in der Lesefassung steht."""
    number: str
    title: str
    #: Der Abschnitt: „Rat", „Verwaltungsausschuss", „Ratsausschüsse",
    #: „Schlussbestimmungen".
    part: str
    #: Seite im PDF — für den Sprung ``#page=`` aus der Quellenkarte.
    page: int
    text: str

    @property
    def label(self) -> str:
        return f"§ {self.number}"


@dataclass(frozen=True)
class RulesOfProcedure:
    title: str
    short_title: str
    version_date: str
    adopted_date: str | None
    adopted_template: str | None
    term_end: str | None
    source_url: str
    listing_url: str
    sections: tuple[Section, ...]

    def section(self, number: str) -> Section | None:
        return next((s for s in self.sections if s.number == number), None)

    def page_url(self, section: Section) -> str:
        return f"{self.source_url}#page={section.page}"


@lru_cache(maxsize=1)
def load() -> RulesOfProcedure:
    daten = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    adopted = daten.get("adopted") or {}
    return RulesOfProcedure(
        title=daten["title"], short_title=daten["short_title"],
        version_date=daten["version_date"], adopted_date=adopted.get("date"),
        adopted_template=adopted.get("template_number"), term_end=daten.get("term_end"),
        source_url=daten["source_url"], listing_url=daten["listing_url"],
        sections=tuple(Section(number=s["number"], title=s["title"], part=s["part"],
                               page=int(s["page"]), text=s["text"])
                       for s in daten["sections"]))


def fold(text: str) -> str:
    """Klein, ä → ae, Satzzeichen weg — dieselbe Faltung wie
    ``kern.erklaerwissen._falte``. Das „§" fällt dabei mit weg; Verweise auf
    Paragrafen liest :func:`_explicit_numbers` am ROHEN Text."""
    text = (text or "").lower()
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        text = text.replace(a, b)
    return " ".join(re.sub(r"[^a-z0-9 ]+", " ", text).split())


# ---- Wann die Geschäftsordnung gemeint ist ----------------------------------

#: Die Frage nennt die Geschäftsordnung selbst („GO-Antrag", „laut
#: Geschäftsordnung", „Geschäftsordnungsantrag").
_NENNT_GO = re.compile(r"\bgeschaeftsordnung|\bgo antr")
#: … aber die eines anderen Gremiums. Der Gestaltungsbeirat hat eine eigene
#: (Rat 27.06.2022), und deren Wortlaut haben wir nicht.
_ANDERE_GO = re.compile(
    r"geschaeftsordnung (?:des|der|fuer den|fuer die|fuer das) (?:\w+ )?"
    r"(?:\w*beirat|\w*beirates|\w*beirats|jugendparlament|bundestag|landtag|kreistag)")
#: Fragen über andere Parlamente. „Wie lange darf man im Bundestag reden?"
#: wäre sonst eine Frage an § 15 — nennt die Frage den Rat oder die
#: Geschäftsordnung zusätzlich, bleibt sie gemeint.
_ANDERES_PARLAMENT = re.compile(
    r"\b(?:bundestag|landtag|kreistag|europaparlament|bundesrat|bezirksrat\w*|"
    r"bezirksversammlung|abgeordnetenhaus|buergerschaft)")
#: Der Rat, ein Ausschuss, eine Sitzung, ein Ratsmitglied: Für die Auslöser,
#: die allein zu viel träfen („Einberufung", „Ladung", „wer darf reden"),
#: muss die Frage zusätzlich so etwas nennen.
_KONTEXT = re.compile(
    r"\b(?:rat|rates|rats\w+|stadtrat\w*|ausschu\w+|fraktion\w*|gremi\w+|"
    r"\w*sitzung\w*|politiker\w*|verwaltungsausschuss\w*)\b")

#: „Wie funktioniert der Rat?" — die Frage nach den Spielregeln überhaupt.
#: Sie bekommt das Inhaltsverzeichnis und die beiden Paragrafen, die den
#: Gang einer Sache beschreiben (§ 9 Ablauf, § 10 Vorbereitung).
_UEBERBLICK = re.compile(
    r"wie (?:funktioniert|arbeitet) (?:eigentlich |denn )?(?:der|ein|unser) (?:stadt)?rat\b"
    r"|welche regeln (?:gelten|gibt es) (?:im|fuer den|in einem) (?:stadt)?rat"
    r"|spielregeln (?:im|des|fuer den) (?:stadt)?rat"
    r"|(?:was|welche) sind die regeln (?:im|des|fuer den) (?:stadt)?rat")

#: Die Beispiele zur Frage nach dem Ganzen: Ablauf einer Sitzung, Redezeit,
#: Einwohnerfragestunde.
_BEISPIELE = ("9", "15", "23")

#: „Welche Rechte hat ein Ratsmitglied?" — kein einzelner Paragraf, sondern
#: das Verzeichnis plus die beiden, die Rechte des Einzelnen benennen: einen
#: Gegenstand auf die Tagesordnung setzen lassen (§ 3), Auskunft und
#: Akteneinsicht (§ 14).
_RECHTE = re.compile(
    r"welche rechte (?:hat|haben) (?:ein |eine |die |der )?(?:\w+ )?"
    r"(?:ratsmitglied|ratsfrau|ratsherr|fraktion)")


@dataclass(frozen=True)
class _Trigger:
    #: greift allein
    own: str = ""
    #: greift nur, wenn die Frage zugleich den Rat, eine Sitzung, einen
    #: Ausschuss … nennt (``_KONTEXT``) oder die Geschäftsordnung selbst
    with_context: str = ""


#: Je Paragraf die Wortfelder, an denen eine Frage ihn meint. Gefaltet (ä →
#: ae), ohne Satzzeichen. Die vordere Wortgrenze steht, die hintere fast nie:
#: Komposita verschieben sie (council/CLAUDE.md, „Deutsche Wörter in
#: Regexen"). Vergangenheit („wie wurde abgestimmt") meint ein Ergebnis, nicht
#: die Regel — die Auslöser stehen deshalb im Präsens.
TRIGGERS: dict[str, _Trigger] = {
    "1": _Trigger(
        own=r"\bsondersitzung|\bausserordentliche\w* (?:rats)?sitzung"
            r"|wer (?:beruft|laedt) (?:den )?(?:stadt)?rat",
        with_context=r"\beinberuf|wie oft (?:tagt|tagen|trifft|treffen)"),
    "2": _Trigger(
        own=r"\bladungsfrist",
        with_context=r"\bladung (?:zur|zu der|fuer die) \w*sitzung"
                     r"|\bladung\w* .{0,30}(?:frist|verschickt|zugestellt|zustellung|verkuerzt)"
                     r"|wie (?:frueh|lange vorher|kurzfristig) .{0,40}(?:eingeladen|geladen|einladung)"),
    "3": _Trigger(
        # „Wie kommt etwas auf die Tagesordnung?" ja — „Kommt das Stadion
        # wieder auf die Tagesordnung?" nein: Das fragt nach einem Termin.
        own=r"\bauf die tagesordnung (?:setzen|gesetzt|nehmen|aufgenommen)"
            r"|\btagesordnung (?:aufstellen|aufgestellt|festlegen|festgelegt|ergaenzen|ergaenzt)"
            r"|wer (?:stellt|legt|bestimmt|macht|entscheidet) .{0,40}tagesordnung"
            r"|wie (?:kommt|kommen|bringt|bringe|bringen|setzt|setze|setzen) .{0,40}auf die tagesordnung"
            r"|wer (?:kann|darf) .{0,40}auf die tagesordnung",
        with_context=r"\bantragsfrist|bis wann .{0,40}\bantr(?:ag|aege)\b"
                     r"|\bantr(?:ag|aege) .{0,30}(?:einreichen|eingereicht)"
                     r"|\b23 uhr|wie lange (?:dauert|dauern|geht|gehen) (?:eine |die )?ratssitzung"
                     r"|bis wann (?:dauert|geht|tagt|laeuft) (?:eine |die )?(?:rats)?sitzung"),
    "4": _Trigger(
        own=r"\bnicht ?oeffentlich|ausschluss der oeffentlichkeit|\bverschwiegenheit"
            r"|\boeffentlichkeit (?:der|von) (?:rats)?sitzung",
        with_context=r"\b(?:sind|ist) (?:die |eine )?(?:\w+ )?\w*sitzung\w* .{0,15}\boeffentlich"
                     r"|\bzuhoer|\bzuschau|\bpublikum"
                     r"|(?:kann|darf|koennen|duerfen) (?:ich|man|jeder|jede|buerger\w*|einwohner\w*) "
                     r".{0,50}(?:teilnehmen|zuhoeren|zuschauen|dabei sein|hingehen|besuchen)"),
    "5": _Trigger(
        own=r"\banwesenheitspflicht|\bteilnahmepflicht|\bfernbleiben"
            r"|(?:muss|muessen) (?:ein |eine |die |alle )?(?:ratsmitglied|ratsfrau|ratsherr|politiker)"
            r"\w* .{0,40}(?:teilnehmen|anwesend|da sein|erscheinen|\bkommen)",
        with_context=r"(?:muss|muessen) .{0,40}(?:teilnehmen|anwesend sein|da sein|erscheinen)"),
    "6": _Trigger(own=r"\bbefangen|\bmitwirkungsverbot|\binteresse\w*konflikt"),
    "7": _Trigger(
        own=r"\bratsvorsitz|\bhausrecht|wer leitet (?:die |eine )?(?:rats)?sitzung",
        with_context=r"\bsitzungsleitung"),
    "8": _Trigger(
        own=r"\bbeschlussfaehig|\bbeschlussunfaehig|\bquorum",
        with_context=r"wie viele .{0,40}(?:anwesend|da sein|dabei sein)"),
    "9": _Trigger(
        own=r"\bablauf (?:einer|von) (?:rats)?sitzung"
            r"|wie (?:laeuft|verlaeuft) (?:eine|so eine|denn eine|eigentlich eine) (?:rats)?sitzung"
            r"|wie laufen (?:die )?(?:rats)?sitzungen"
            r"|reihenfolge (?:der|auf der) tagesordnung"
            r"|in welcher reihenfolge .{0,30}tagesordnung"
            r"|tagesordnung .{0,20}(?:abgearbeitet|abgewickelt)"),
    "10": _Trigger(
        own=r"wie (?:entsteht|kommt es zu) (?:ein\w* )?(?:rats)?beschl"
            r"|welchen weg (?:geht|nimmt|gehen|nehmen) .{0,30}(?:antrag|antraege|vorlage|beschluss)"
            r"|weg (?:eines|einer|von) (?:antrags|antrages|vorlage|beschlusses)"
            r"|von der vorlage zum beschluss"
            r"|was (?:macht|tut|ist) (?:eigentlich |denn )?der verwaltungsausschuss"),
    "11": _Trigger(
        own=r"\bdringlichkeitsantr|\beilantr|nicht auf der tagesordnung",
        with_context=r"\bdringlichkeit"),
    "12": _Trigger(
        own=r"(?:was (?:ist|sind|bedeutet|heisst)|wie funktionier\w*|wie (?:stellt|stelle) "
            r"(?:man|ich)|wer (?:kann|darf)|bis wann) .{0,30}aenderungsantr"
            r"|aenderungsantr\w* .{0,40}(?:zuerst|reihenfolge|schriftlich|bis wann|"
            r"stellen\b|gestellt werden)"),
    "13": _Trigger(
        own=r"\bgeschaeftsordnungsantr|\bantr(?:ag|aege) zur geschaeftsordnung|\bgo antr"
            r"|\bredeliste|\brednerliste|\bnichtbefassung"
            r"|schluss der (?:debatte|beratung|aussprache)"
            r"|was (?:bedeutet|heisst) .{0,30}(?:vertag|als behandelt|nichtbefassung|verweisung)"
            r"|was ist (?:eine |die )?(?:vertagung|nichtbefassung)"
            r"|wie (?:wird|kann) .{0,30}vertagt|\bverweisung an einen ausschuss"),
    "14": _Trigger(
        own=r"\bakteneinsicht|\bauskunftsrecht|\bauskunftsanspruch",
        with_context=r"(?:darf|duerfen|kann|koennen) .{0,40}(?:akten|auskunft|auskuenfte) "
                     r".{0,20}(?:einsehen|verlangen|bekommen|anfordern|fordern)"),
    "15": _Trigger(
        own=r"\bredezeit|\brederecht|\bredeordnung|\bwortentzug"
            r"|das wort (?:erteil|entzieh|entzog|ergreif|bekomm)"
            r"|wie (?:lange|oft|viel) (?:darf|duerfen|kann|koennen) .{0,50}(?:reden|sprechen)",
        with_context=r"wer (?:darf|kann) .{0,30}(?:reden|sprechen|das wort)"),
    "16": _Trigger(own=r"\bpersoenliche\w* erklaerung"),
    "17": _Trigger(
        own=r"\bordnungsruf|\bordnungsmassnahm|\bungebuehr"
            r"|aus dem (?:sitzungs)?saal (?:verwiesen|geworfen|entfernt)"
            r"|ratsmitglied\w* .{0,40}(?:ausschliessen|ausgeschlossen|rauswerfen|rausgeworfen)"
            r"|(?:ausschliessen|ausschluss) (?:eines|von) ratsmitglied"
            r"|ratsmitglied\w* .{0,40}(?:daneben ?benimm|benimmt sich|stoert|beleidigt|geworfen)"
            r"|aus der sitzung (?:geworfen|ausgeschlossen|verwiesen)"),
    "18": _Trigger(
        own=r"\bnamentlich\w* (?:abstimm|abgestimmt)|\bstimmengleichheit|\bpatt\b"
            r"|\bhandzeichen|\bhandaufheben|\bhand heben|\bgesondert abstimm|\bgetrennt\w* abstimm"
            r"|\beinfache\w* mehrheit|wie (?:wird|werden) .{0,30}abgestimmt"
            r"|wie (?:stimmt|stimmen) (?:der rat|die ratsmitglieder|man) .{0,10}\bab\b"
            r"|welche mehrheit (?:braucht|benoetigt|ist noetig|ist erforderlich|reicht)"
            r"|mehrheit (?:braucht|benoetigt|noetig|erforderlich|reicht)"
            r"|enthaltung\w* .{0,30}(?:zaehl|gelten|gewertet|wirken)"
            r"|(?:zaehlen|gelten|zaehlt|gilt) .{0,20}enthaltung"),
    "19": _Trigger(
        own=r"\bgeheim\w* (?:wahl|abstimmung|gewaehlt|waehlen|abgestimmt)|\bwahlgang"
            r"|\bdurch zuruf|\bper zuruf|\blosentscheid|\blos (?:entscheidet|gezogen|ziehen)"
            r"|wie (?:wird|werden|waehlt) .{0,40}(?:im|vom|durch den) rat gewaehlt"
            r"|wie waehlt der rat|wahlen im rat"
            r"|\bwahl\w* .{0,30}\bgeheim|\bgeheim .{0,20}\bwahl"),
    "20": _Trigger(
        own=r"\bprotokoll\w* .{0,30}(?:genehmig|unterschrieb|unterzeichn|gefuehrt|angefertigt)"
            r"|wer (?:schreibt|fuehrt|erstellt|macht) (?:das |die )?(?:protokoll|niederschrift)"
            r"|\btonaufnahme|\btonaufzeichnung|\btontraeger"
            r"|was steht (?:alles )?im protokoll"
            r"|(?:muss|wird) .{0,30}im protokoll (?:stehen|festgehalten|vermerkt)"
            r"|(?:werden|wird) .{0,30}\w*sitzung\w* .{0,20}(?:aufgezeichnet|aufgenommen|mitgeschnitten)"),
    "21": _Trigger(
        own=r"unterschied .{0,40}fraktion\w* .{0,20}gruppe|unterschied .{0,40}gruppe\w* .{0,20}fraktion"
            r"|was (?:ist|sind|bedeutet) (?:eine |eigentlich eine )?(?:fraktion|gruppe|ratsgruppe)(?:en)?$"
            r"|wie (?:entsteht|bildet sich|gruendet man|gruenden) .{0,20}(?:fraktion|gruppe)"
            r"|(?:fraktion|gruppe) (?:bilden|gruenden|gebildet|gegruendet)|\bfraktionsstatus"),
    "22": _Trigger(
        with_context=r"\bsachverstaendig|\banhoerung|\banhoeren|\bangehoert"
                     r"|\bexperten .{0,20}(?:anhoeren|einladen|zu wort)"),
    "23": _Trigger(
        own=r"\beinwohnerfrage|\bbuergerfrage|\bfragestunde"
            r"|(?:kann|darf|koennen|duerfen) (?:ich|man|jeder|jede|buerger\w*|einwohner\w*) "
            r".{0,60}(?:fragen stellen|eine frage stellen|frage an den rat"
            r"|im rat (?:reden|sprechen|fragen|etwas sagen|was sagen)"
            r"|in der (?:rats)?sitzung (?:reden|sprechen|fragen|etwas sagen|was sagen))"),
    "24": _Trigger(own=r"\bbeigeordnete"),
    "25": _Trigger(own=r"\bverwaltungsausschuss|\bumlaufverfahren"),
    "26": _Trigger(),
    "27": _Trigger(
        own=r"(?:wozu|warum|wofuer) (?:gibt es|braucht (?:man|der rat)) .{0,20}ausschuesse"
            r"|was (?:sind|ist) (?:eigentlich )?(?:ein |die )?(?:rats|fach)?ausschu(?:ss|esse)$"
            r"|ausschussmitglied\w* .{0,40}(?:verhindert|vertret|krank)"),
    "28": _Trigger(
        own=r"wie lange (?:dauert|dauern|geht|gehen) (?:eine |die )?ausschusssitzung"
            r"|ausschusssitzung\w* .{0,40}(?:pause|stunden|dauer|enden)"),
    "28a": _Trigger(
        own=r"\b28 ?a\b|\bverweisungsantr"
            r"|(?:in|an) (?:einen |den )?(?:anderen |weiteren )?\w*ausschu\w* "
            r"(?:verwiesen|verweisen|ueberwiesen|ueberweisen)"),
    # Nicht „Ausschuss … öffentlich" in beliebigem Abstand: „Was hat der
    # Verkehrsausschuss zum öffentlichen Nahverkehr beschlossen?" meint keine
    # Sitzungsregel.
    "29": _Trigger(
        own=r"\bausschu\w* (?:sind|ist|tagen|tagt) .{0,20}(?:nicht ?)?oeffentlich"
            r"|(?:sind|ist) (?:die |eine )?\w*ausschusssitzung\w* .{0,15}(?:nicht ?)?oeffentlich"
            r"|\bnicht ?oeffentlich\w* .{0,30}ausschu"
            r"|(?:zuhoer|zuschau)\w* .{0,40}ausschu|\bausschu\w* .{0,40}(?:zuhoer|zuschau)"),
    "30": _Trigger(),
    "31": _Trigger(own=r"\bgemeinsame\w* (?:sitzung|beratung|ausschusssitzung)"
                       r"|\bgemeinsam (?:tagen|beraten|sitzen)"),
    "32": _Trigger(
        own=r"(?:wer|kann|darf|duerfen|koennen) .{0,40}(?:im|in einem|in den|in der) \w*ausschu\w* "
            r".{0,40}(?:reden|sprechen|das wort|mitreden|etwas sagen|was sagen)"
            r"|\bbeirat\w* .{0,40}(?:stellung|rederecht|reden|sprechen|vortragen)"),
    "33": _Trigger(),
}

#: Nur mit der Geschäftsordnung SELBST in der Frage (nicht dem
#: „Geschäftsordnungsantrag"): „Seit wann gilt die Geschäftsordnung?",
#: „Wurde die Geschäftsordnung geändert?" — dafür steht § 33 da.
_GO_SELBST = re.compile(r"\bgeschaeftsordnung\b")
_GELTUNG = re.compile(r"(?:seit wann|bis wann|wie lange) (?:gilt|gelten)|\bgilt\b|\bgueltig"
                      r"|in kraft|\bgeaendert|\baenderung|\bneue|\bbeschlossen|\bueberarbeit")

#: Die Regeln für den Rat gelten in Verwaltungsausschuss und Ratsausschüssen
#: „sinngemäß", mit Ausnahmen (§ 26, § 32). Wer nach der Redezeit IM
#: AUSSCHUSS fragt, braucht § 15 UND § 32 — sonst sagt die Antwort „nur
#: einmal reden", obwohl § 32 genau das für Ausschüsse aufhebt.
_IM_AUSSCHUSS = re.compile(r"\b\w*ausschu(?:ss|esse)\w*")
_RAT_ABSCHNITT = "Rat"

_COMPILED = {nr: (re.compile(t.own) if t.own else None,
                  re.compile(t.with_context) if t.with_context else None)
             for nr, t in TRIGGERS.items()}

#: „§ 15", „§28a", „§ 23 Abs. 3 GO" — am rohen Text, weil die Faltung das
#: „§" verschluckt.
_PARAGRAF_RE = re.compile(r"§§?\s*(\d{1,2}\s?[a-z]?)\b")
#: Was hinter der Nummer steht: ein anderes Gesetz („§ 62 NKomVG") heißt,
#: es ist nicht die Geschäftsordnung; „GO" oder „der Geschäftsordnung" heißt,
#: sie ist es — auch wenn die Frage das Wort sonst nicht nennt.
_ANDERES_GESETZ = re.compile(r"\s*(?:Abs(?:atz|\.)?\s*\d+\s*)?(?:S(?:atz|\.)\s*\d+\s*)?"
                             r"(?:NKomVG|NGO|BauGB|BGB|GG|NBauO|KomHKVO|VwVfG|StGB|[A-Z]\w*G)\b")
_DIESE_GO = re.compile(r"\s*(?:Abs(?:atz|\.)?\s*\d+\s*)?(?:S(?:atz|\.)\s*\d+\s*)?"
                       r"(?:der\s+)?(?:GO|Geschäftsordnung)\b")


@dataclass(frozen=True)
class Selection:
    """Was eine Frage aus der Geschäftsordnung braucht."""
    sections: tuple[Section, ...] = ()
    #: Das Inhaltsverzeichnis statt (oder neben) einzelner Paragrafen —
    #: „Was steht in der Geschäftsordnung?", „Wie funktioniert der Rat?".
    overview: bool = False

    def __bool__(self) -> bool:
        return bool(self.sections) or self.overview


def _explicit_numbers(roh: str, gefaltet: str) -> list[str]:
    """Paragrafen, die die Frage selbst nennt — nur, wenn sie dabei die
    Geschäftsordnung meint. Ein nacktes „§ 15" kann jedes Gesetz sein; § 28a
    gibt es nur hier (Anträge „nach §28a" stehen so im Ratsarchiv)."""
    known = {s.number for s in load().sections}
    nennt_go = bool(_NENNT_GO.search(gefaltet))
    out = []
    for m in _PARAGRAF_RE.finditer(roh or ""):
        nr = m.group(1).replace(" ", "")
        rest = (roh or "")[m.end():m.end() + 40]
        if nr not in known or nr in out or _ANDERES_GESETZ.match(rest):
            continue
        if nennt_go or _DIESE_GO.match(rest) or nr == "28a":
            out.append(nr)
    return out


def _matches(gefaltet: str) -> list[str]:
    mit_kontext = bool(_KONTEXT.search(gefaltet) or _NENNT_GO.search(gefaltet))
    out = []
    for nr, (own, ctx) in _COMPILED.items():
        if (own and own.search(gefaltet)) or (ctx and mit_kontext and ctx.search(gefaltet)):
            out.append(nr)
    return out


def find(*questions: str, max_n: int = MAX_SECTIONS) -> Selection:
    """Die Paragrafen, die diese Frage braucht — leer, wenn sie keine Regel meint.

    Mehrere Texte (die rohe Frage und ihre eigenständige Fassung aus der
    Analyse) werden zusammengelegt: Die Analyse macht aus „Und wie lange darf
    man da reden?" eine Frage mit Gegenstand, die rohe Fassung trägt dafür
    manchmal ein Wort, das die Umformulierung verschluckt hat.
    """
    doc = load()
    nummern: list[str] = []
    overview = False
    for frage in questions:
        gefaltet = fold(frage)
        if not gefaltet:
            continue
        nennt_go = bool(_NENNT_GO.search(gefaltet)) and not _ANDERE_GO.search(gefaltet)
        if (_ANDERES_PARLAMENT.search(gefaltet) and not nennt_go
                and not re.search(r"\boldenburg|\bstadtrat", gefaltet)):
            continue
        if _ANDERE_GO.search(gefaltet) and not _matches(gefaltet.replace("geschaeftsordnung", "")):
            continue
        treffer = _explicit_numbers(frage, gefaltet) + _matches(gefaltet)
        if nennt_go and _GO_SELBST.search(gefaltet) and _GELTUNG.search(gefaltet):
            treffer.append("33")
        if _UEBERBLICK.search(gefaltet):
            overview = True
            treffer += ["9", "10"]
        elif _RECHTE.search(gefaltet):
            overview = True
            treffer += ["3", "14"]
        elif nennt_go and not treffer:
            # „Was steht in der Geschäftsordnung?" — das Verzeichnis und die
            # drei Regeln, nach denen am meisten gefragt wird. Mit dem
            # Verzeichnis allein schrieb die Antwort „Der vorliegende Text
            # enthält eine Inhaltsübersicht, keine vollständigen Paragrafen"
            # (Messung 03.10.2026).
            overview = True
            treffer += list(_BEISPIELE)
        # Die Rats-Regel gilt im Ausschuss und im Verwaltungsausschuss nur
        # „sinngemäß" — mit dem Paragrafen, der die Ausnahmen nennt.
        rat_regel = any((s := doc.section(n)) and s.part == _RAT_ABSCHNITT for n in treffer)
        if rat_regel and "verwaltungsausschuss" in gefaltet:
            treffer.append("26")
        elif rat_regel and _IM_AUSSCHUSS.search(gefaltet):
            treffer.append("32")
            if "18" in treffer:
                treffer.append("30")
        for n in treffer:
            if n not in nummern:
                nummern.append(n)
    nummern = nummern[:max_n]
    sections = tuple(s for n in nummern if (s := doc.section(n)))
    return Selection(sections=sections, overview=overview)


# ---- Gilt die gespeicherte Fassung noch? ------------------------------------

#: Ratsbeschlüsse, die eine Geschäftsordnung des Rates beschließen oder
#: ändern. Die Titel im Bestand (gezählt 03.10.2026): „Geschäftsordnung für
#: den Rat, den Verwaltungsausschuss und die Ratsausschüsse - Beschluss"
#: (01.11.2021), „Änderung der Geschäftsordnung des Rates (SPD-Fraktion …)"
#: (19.07.2021), „Änderung der Geschäftsordnung für den Rat, …" (2018–2020).
#: NICHT: „Geschäftsordnungsantrag …" (ein Antrag NACH der Geschäftsordnung)
#: und „Geschäftsordnung des Gestaltungsbeirates".
ADOPTION_TITLE = re.compile(
    r"^(?:Satzung zur )?(?:Änderung der |Neufassung der )?Geschäftsordnung "
    r"(?:für den Rat|des Rates)", re.IGNORECASE)


def newer_adoptions(store, doc: RulesOfProcedure | None = None) -> list[dict]:
    """Ratsbeschlüsse zur Geschäftsordnung, die JÜNGER sind als die gespeicherte
    Fassung — angenommen, neueste zuerst. Leer heißt: Die Datei ist aktuell.

    Der Store liefert grob (Titel enthält „Geschäftsordnung", Gremium Rat),
    die Regel oben entscheidet fein. Fehler sind kein Blocker: Ohne Antwort
    gilt die Datei als aktuell, und die Antwort sagt trotzdem, für welche
    Wahlperiode die Fassung beschlossen wurde.
    """
    doc = doc or load()
    seit = doc.adopted_date or doc.version_date
    try:
        rows = store.rules_of_procedure_decisions(after=seit)
    except Exception:  # noqa: BLE001 — Zusatz, nie Blocker
        return []
    return [r for r in rows if ADOPTION_TITLE.match(r.get("title") or "")
            and (r.get("outcome") or "") == "accepted"]


def _datum(iso: str | None) -> str:
    if iso and len(iso) >= 10:
        return f"{iso[8:10]}.{iso[5:7]}.{iso[0:4]}"
    return iso or ""


def _wahlperiode(doc: RulesOfProcedure) -> str:
    """„2021–2026" aus Beschluss und Ende der Wahlperiode."""
    von = (doc.adopted_date or doc.version_date)[:4]
    bis = (doc.term_end or "")[:4]
    return f"{von}–{bis}" if bis else von


def status(today: date | None = None, newer: list[dict] | None = None) -> dict:
    """Wie es um die gespeicherte Fassung steht — für Prompt UND Karte.

    ``current``: Die Wahlperiode läuft, kein jüngerer Beschluss bekannt.
    ``term_ended``: Die Wahlperiode ist vorbei; der neue Rat gibt sich eine
    eigene Geschäftsordnung (§ 69 NKomVG), die hier noch nicht eingepflegt ist.
    ``superseded``: Im Archiv steht ein jüngerer Beschluss — wir haben ihn,
    aber nicht seinen Wortlaut.
    """
    doc = load()
    today = today or date.today()
    if newer:
        return {"state": "superseded", "decision_id": newer[0].get("id"),
                "decision_date": newer[0].get("session_date")}
    if doc.term_end and today.isoformat() > doc.term_end:
        return {"state": "term_ended"}
    return {"state": "current"}


def version_line(today: date | None = None, newer: list[dict] | None = None) -> str:
    """Eine Zeile für die Karte: welche Fassung, und ob sie noch gilt."""
    doc = load()
    st = status(today, newer)
    basis = f"Fassung vom {_datum(doc.version_date)}"
    if doc.adopted_date and doc.adopted_date != doc.version_date:
        basis += f", vom Rat am {_datum(doc.adopted_date)} bestätigt"
    if st["state"] == "superseded":
        return (f"{basis}. Der Rat hat am {_datum(st['decision_date'])} eine neuere "
                "Fassung beschlossen — deren Wortlaut liegt hier noch nicht vor.")
    if st["state"] == "term_ended":
        return (f"{basis}. Sie galt für die Wahlperiode {_wahlperiode(doc)}; die neue "
                "Fassung des neuen Rates liegt hier noch nicht vor.")
    return f"{basis} · gilt für die Wahlperiode {_wahlperiode(doc)}"


# ---- Für den Prompt ---------------------------------------------------------

def prompt_block(sel: Selection, today: date | None = None,
                 newer: list[dict] | None = None) -> str:
    """Der Kontext-Absatz „GESCHÄFTSORDNUNG DES RATES" — leer ohne Auswahl.

    Der Kopf trägt Fassung und Wahlperiode, weil die Antwort sonst eine
    Regel als ewig gültig ausgäbe. Steht im Archiv ein jüngerer Beschluss,
    sagt der Block das und nennt dessen id — der Router hat den Beschluss in
    die Kandidaten gelegt, die Antwort kann ihn zitieren.
    """
    if not sel:
        return ""
    doc = load()
    st = status(today, newer)
    kopf = (f"\nGESCHÄFTSORDNUNG DES RATES (Wortlaut der {doc.title}, Fassung vom "
            f"{_datum(doc.version_date)}")
    if doc.adopted_date and doc.adopted_date != doc.version_date:
        kopf += (f"; der Rat hat sie am {_datum(doc.adopted_date)} für die Wahlperiode "
                 f"{_wahlperiode(doc)} beschlossen")
    kopf += "). Das ist eine Regel, KEIN Beschluss — nie mit [id] zitieren:\n"
    teile = [kopf]
    if st["state"] == "superseded":
        teile.append(
            f"ACHTUNG: Der Rat hat am {_datum(st['decision_date'])} eine neuere "
            f"Geschäftsordnung beschlossen [{st['decision_id']}]. Ihr Wortlaut liegt nicht "
            "vor; der Text unten kann überholt sein. Sag das in einem Satz und zitiere "
            "diesen Beschluss.\n")
    elif st["state"] == "term_ended":
        teile.append(
            f"ACHTUNG: Diese Fassung galt für die Wahlperiode {_wahlperiode(doc)}, die am "
            f"{_datum(doc.term_end)} endete. Der neue Rat gibt sich eine eigene "
            "Geschäftsordnung (2021 bestätigte er die bisherige unverändert); ob die "
            "neue abweicht, liegt nicht vor. Sag das in einem Satz.\n")
    if sel.overview:
        inhalt = " · ".join(f"{s.label} {s.title}" for s in doc.sections)
        teile.append(f"Inhalt: {inhalt}\n")
        teile.append("Die Frage gilt dem Ganzen: Sag in wenigen Sätzen, was die "
                     "Geschäftsordnung regelt, mit zwei, drei Beispielen aus den Paragrafen "
                     "unten, und biete an, nach einer bestimmten Regel zu fragen. Sag nicht, "
                     "dass hier nur ein Verzeichnis oder ein Auszug vorliegt.\n")
    for s in sel.sections:
        teile.append(f"{s.label} {s.title} (Abschnitt {s.part}):\n{s.text}\n")
    return "".join(teile)


# ---- Für die Karte unter der Antwort ----------------------------------------

def card(sel: Selection, today: date | None = None,
         newer: list[dict] | None = None) -> dict | None:
    """Die Quellenkarte „Aus der Geschäftsordnung" — fertig für beide Clients.

    Der ganze Wortlaut reist mit: Die Karte ist ein Beleg, kein Link auf eine
    Startseite (Tims Regel, ``beleg-apparat-je-dokument``) — man soll die
    Regel lesen können, ohne das PDF zu öffnen. ``url`` springt auf die Seite.
    """
    if not sel:
        return None
    doc = load()
    st = status(today, newer)
    return {
        "title": doc.short_title,
        "full_title": doc.title,
        "version": version_line(today, newer),
        "state": st["state"],
        "url": doc.source_url,
        "sections": [{"number": s.number, "label": s.label, "title": s.title,
                      "part": s.part, "url": doc.page_url(s), "text": s.text}
                     for s in sel.sections],
        # Nur bei der Frage nach dem Ganzen: das Inhaltsverzeichnis.
        "contents": ([{"label": s.label, "title": s.title, "url": doc.page_url(s)}
                      for s in doc.sections] if sel.overview else []),
    }


def belege(sel: Selection | None) -> list[dict]:
    """``[{label, year, url}]`` — die Paragrafen als Beleg-Chips unter einer
    Lotti-Antwort (``council.assistant.kontext_belege``), dieselbe Form wie
    die Haushalts-Belege. Ohne Paragrafen das ganze PDF."""
    if not sel:
        return []
    doc = load()
    jahr = int(doc.version_date[:4])
    if not sel.sections:
        return [{"label": doc.short_title, "year": jahr, "url": doc.source_url}]
    return [{"label": f"{doc.short_title}, {s.label} {s.title}", "year": jahr,
             "url": doc.page_url(s)} for s in sel.sections]
