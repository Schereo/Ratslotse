"""„Kurs der Sitzung": Etappen, Art und Piktogramm je Tagesordnungspunkt.

Plan: ``docs/plan-sitzungsseite-kurs.md``, Schritt 1. Die Sitzungsseite zeigt
eine Sitzung als Linie mit Bojen — jede Boje ein Punkt, jedes Band eine
Etappe. Was davon *gilt* (welche Punkte eine Etappe bilden, was ein Punkt ist,
welches Zeichen er trägt), entscheidet der Server; Web und App zeichnen nur.

Alles hier ist rein: Eingabe sind die Zeilen der Tagesordnung und ein paar
vorberechnete Angaben aus dem Store, Ausgabe ein dict in der Form von
``SessionCourse`` (``web/backend/app/antworten.py``). Die Datenbank fasst
``CouncilStore.session_course`` an.

**Warum nur Rubriken eine Etappe eröffnen.** Der Plan sagte zuerst: Jeder
Oberpunkt ohne Vorlage mit Unterpunkten wird eine Etappe. Der Bauausschuss vom
27.08.2026 (ksinr 4607) trägt aber elf Überschriften der Art „Bauleitplanung
Meerweg" mit je zwei Unterpunkten — daraus wären elf Etappen mit zwei Bojen
geworden. Solche Überschriften benennen ein VORHABEN (``_ueberschriften`` im
Store unterscheidet das schon); ihre Punkte bleiben in „Beschlüsse und
Berichte" und tragen die Gruppe als ``group``. Eine Etappe eröffnen nur
Rubriken: „Anträge der Fraktionen …", die Ausschuss-Abschnitte im Rat und
Ähnliches.
"""
from __future__ import annotations

import re
from typing import Any

#: „Ö 11.3" → Präfix „Ö", Nummer „11.3" (dieselbe Form wie im Store).
NUMBER_RE = re.compile(r"^\s*([A-Za-zÖÄÜöäü]+)\s+([\d.]+?)\.?\s*$")

#: Das Ergebnis, das die Tagesordnung nach der Sitzung im Titel nachträgt.
RESULT_SUFFIX_RE = re.compile(r"\s*Beschluss:\s*(.+?)\s*$")

#: Formalien im engen Sinn: Sie bilden am Anfang EINE Zelle („Ö 1–3").
#: „Tagesordnung" allein reicht nicht — „Beratung von nichtöffentlichen
#: Tagesordnungspunkten im Verwaltungsausschuss" ist ein Bericht.
FORMALITY_RE = re.compile(
    r"Beschlussf[äa]higkeit|"
    r"(?:Genehmigung|Feststellung)\s+(?:der\s+|des\s+|von\s+)?(?:Tagesordnung|Protokoll)|"
    r"Eröffnung der Sitzung|Wahl der Schriftf[üu]hrung",
    re.IGNORECASE)

#: Rahmen der Sitzung: Formalien plus das, was in jeder Sitzung steht, aber
#: kein Beschlussgegenstand ist. Vor dem ersten Inhalt → „Zum Start", nach dem
#: letzten → „Zum Schluss", dazwischen bleibt es, wo es steht.
FRAME_RE = re.compile(
    FORMALITY_RE.pattern + r"|Einwohnerfragestunde|^\s*Mitteilung|Anfragen und Anregungen|"
    r"^\s*Verschiedenes|^\s*Berichte? der Verwaltung\s*$",
    re.IGNORECASE)

#: Was ohne jeden Inhalt trotzdem ans Ende gehört.
END_RE = re.compile(r"Anfragen und Anregungen|^\s*Verschiedenes", re.IGNORECASE)

QUESTION_TIME_RE = re.compile(r"Einwohnerfragestunde", re.IGNORECASE)
INQUIRIES_RE = re.compile(r"Anfragen und Anregungen|^\s*Verschiedenes", re.IGNORECASE)
ANNOUNCEMENT_RE = re.compile(r"^\s*Mitteilung|^\s*Berichte? der Verwaltung\s*$", re.IGNORECASE)

#: Ausschuss-Abschnitt in der Tagesordnung des Rats:
#: „Ausschuss für Stadtgrün, Umwelt und Klima vom 13.08.2026".
SECTION_RE = re.compile(r"^\s*(?P<committee>.*ausschuss.*?)\s+vom\s+\d{1,2}\.\s?\d{1,2}\.\d{2,4}\s*$",
                        re.IGNORECASE)
#: „Anträge der Fraktionen, Gruppen, Rats- und Ausschussmitglieder"
MOTIONS_RE = re.compile(r"^\s*Antr[äa]ge\b\s*(?P<rest>.*)$", re.IGNORECASE)

#: Ein Antrag erkennt sich am Absender in Klammern mit Datum oder am Zusatz.
MOTION_SUFFIX_RE = re.compile(r"[-–]\s*(?:\w*antrag)(?:\s+mit\b.*)?\s*$", re.IGNORECASE)
#: Wer einen Antrag stellen kann — damit „(Bericht vom 03.05.2026)" keiner wird.
MOTION_SENDER_RE = re.compile(r"Fraktion|Gruppe|Ratsherr|Ratsfrau|Mitglied", re.IGNORECASE)
APPLICANT_RE = re.compile(
    r"\(\s*(?:die\s+)?(?P<who>[^()]*?)(?P<date>\s+vom\s+\d{1,2}\.\s?\d{1,2}\.\d{2,4})?\s*\)")
#: „Dringlichkeitsantrag: festgestellte PAK-Belastung" — ein Zusatzpunkt.
DRINGLICH_RE = re.compile(r"^\s*Dringlichkeitsantrag\b", re.IGNORECASE)
DRINGLICH_PREFIX_RE = re.compile(r"^\s*Dringlichkeitsantrag\s*:\s*", re.IGNORECASE)
#: Datum eines Antrags im Titel — die Handhabe, einen Antrag ohne Vorlage in
#: einer früheren Sitzung wiederzufinden (s. ``postponed_counts``).
DATED_RE = re.compile(r"vom\s+\d{1,2}\.\s?\d{1,2}\.\d{2,4}")

DECISION_SUFFIX_RE = re.compile(r"[-–]\s*\S*beschluss\b|\b(?:Satzungs|Aufstellungs|Feststellungs)beschluss",
                                re.IGNORECASE)
REPORT_SUFFIX_RE = re.compile(r"\bBericht\b", re.IGNORECASE)

#: Wie die Art eines Punkts heißt, wenn sie angezeigt wird. Eine Stelle für
#: Web und App.
TYPE_LABELS: dict[str, str | None] = {
    "formality": "Formalie",
    "question_time": "Fragestunde",
    "inquiries": "Anfragen",
    "announcement": "Mitteilung",
    "motion": "Antrag",
    "decision": "Entscheidung",
    "preliminary": "Vorberatung",
    "report": "Bericht",
    "other": None,
}

#: Rahmen der Sitzung — kein Beschlussgegenstand. Sie zählen nicht als
#: inhaltlich („3 von 9") und tragen nie den gelben Punkt: „Genehmigung des
#: Protokolls … vom 08.06.2026" steht jedes Mal mit demselben Titel da.
FRAME_TYPES = frozenset({"formality", "question_time", "inquiries", "announcement"})

# ---------------------------------------------------------------------------
# Piktogramme (Plan, Anhang A). Die Tabelle dort und diese Liste gehören
# zusammen; ``tests/test_course.py`` hält beide gleich.

#: Schlüssel → Lucide-Name. Dazu fest: Anker für den Beginn, Schloss für
#: nichtöffentlich (zeichnet der Client ohne Schlüssel).
ICONS: dict[str, str] = {
    "formalities": "list-checks",
    "citizen_question": "message-circle-question",
    "inquiries": "messages-square",
    "announcement": "megaphone",
    "sign": "signpost",
    "bike": "bike",
    "bus": "bus",
    "ticket": "ticket",
    "speed": "gauge",
    "route": "route",
    "parking": "square-parking",
    "closure": "ban",
    "building": "building-2",
    "housing": "house",
    "plan": "map",
    "greenery": "leaf",
    "water": "droplets",
    "energy": "wind",
    "waste": "trash-2",
    "money": "euro",
    "environment": "flask-conical",
    "renovation": "wrench",
    "personnel": "user-plus",
    "statute": "file-text",
    "airfield": "plane",
    "school": "graduation-cap",
    "daycare": "baby",
    "sport": "trophy",
    "culture": "drama",
    "social": "heart-handshake",
    "report": "clipboard-list",
    "motion": "file-pen",
}

#: Regeln über den Titel, in dieser Reihenfolge. Am Bestand gemessen (letzte
#: 300 inhaltliche Punkte, 10.11.2026): 81 % treffen eine Regel. Die Reihenfolge
#: ist die eigentliche Arbeit — jede Zeile hier hat einen Fehltreffer hinter
#: sich, der weiter oben abgefangen wird:
#:
#: * Personalien zuerst, aber nur am Titelanfang: „Besetzung des
#:   Schulausschusses" ist keine Schule, „Entschädigung der Mitglieder" keine
#:   Personalie.
#: * Haushalts-Dokumente vor jedem Fachwort: „Jahresabschluss 2025 der
#:   Bäderbetriebsgesellschaft" ist Geld, nicht Sport; „Ausfallbürgschaft …
#:   Geschäftsbereich Wasser" kein Wasser.
#: * Bebauungspläne vor Straßen: „Bebauungsplan 435 (Etzhorner Weg/Ekernstraße)".
#: * Parken vor Radverkehr und Geld: „Parken auf Sicherheitstrennstreifen …
#:   Radwegen", „Verordnung über Parkgebühren".
#: * „schul" nur am Wortanfang: „Umschuldungen" ist keine Schule.
#: * Straße allein nur, wenn der ganze Titel ein Straßenname ist
#:   („Weißenmoorstraße"); „Gebäudegrundstück Paul-Klee-Straße" ist kein Weg.
ICON_RULES: list[tuple[str, re.Pattern[str]]] = [(key, re.compile(p, re.IGNORECASE)) for key, p in (
    ("personnel", r"^\s*(?:berufung|besetzung|umbesetzung|neubildung|bildung|wahl|bestellung|"
                  r"vereidigung|förmliche verpflichtung|zuteilung)\b|\bnachbesetzung\b"),
    ("money", r"jahresabschluss|wirtschaftsplan|bürgschaft|kreditaufnahm|haushaltssatzung|"
              r"nachtragshaushalt|budgetbericht|leistungsbericht|liquidität|überplanmäßig|"
              r"außerplanmäßig|zuwendungen|beteiligungsunternehmen|lagebericht"),
    ("airfield", r"fliegerhorst|flugplatz"),
    ("plan", r"bebauungsplan|flächennutzungsplan|bauleitplan|rahmenplan|städtebau|planverfahren|"
             r"sanierungsgebiet"),
    ("closure", r"einziehung|veränderungssperre|sperrung"),
    ("sign", r"widmung|benennung|umstufung|verkehrsführung|beschilder"),
    ("ticket", r"ticket|tarif"),
    ("bus", r"\bbus|\bvwg\b|nahverkehr|öpnv|haltestelle|\bvbn\b|linienverkehr"),
    ("parking", r"parken|park\s*&\s*ride|park and ride|p\s*\+\s*r\b|parkpl|parkhaus|parkraum|parkst|"
                r"parkausweis|parkgebühr|stellpl|anwohnerpark|quartiersgarage"),
    ("bike", r"radverkehr|radweg|radfahr|fahrrad|radstreifen|lastenrad|radschnell|radabstell|"
             r"radroute|\brad\b"),
    ("speed", r"tempo|geschwindigkeit|messgerät|blitzer|verkehrsberuhig"),
    # Bauwerke des Verkehrs vor den Themenwörtern: „Ersatzneubau Brücke
    # Tweelbäker See" ist kein Gewässer.
    ("route", r"brücke|bahnübergang|kreuzung|knotenpunkt|kreisel|vorbehaltsnetz"),
    ("daycare", r"\bkita|kindertages|krippe|kindergarten|tagespflege"),
    ("school", r"\bschul|schule|gymnas|\bigs\b"),
    ("sport", r"sport|turnhalle|schwimm|\bbad\b|bäder|stadion|spielfeld|bolzplatz|zweifeld"),
    ("culture", r"kultur|museum|theater|bibliothek|kunst|musik|denkmal|archiv|gedenk|erinnerung"),
    ("social", r"sozial|senior|pflege|obdach|wohnungslos|armut|teilhabe|inklusion|barriere|"
               r"jugend|kinder|familie|integration|migration|flücht|geflüchtet|asyl|"
               r"gleichstellung|gewalt"),
    ("housing", r"wohnen|wohnung|wohnraum|wohnbau|mietspiegel|mieten"),
    ("waste", r"abfall|müll|wertstoff|entsorgung|recycling"),
    ("water", r"starkregen|regenwasser|hitze|entwässerung|kanal|gewässer|bäke\b|hochwasser|"
              r"trinkwasser|regentonne"),
    ("energy", r"energie|wind|solar|photovoltaik|wärme|klimaschutz|klimaneutral|strom"),
    ("greenery", r"baum|bäume|grünfläche|stadtgrün|begrünung|parkanlage|friedhof|wald|"
                 r"kleingarten|natur|biotop|insekt|artenschutz|wallhecke"),
    ("environment", r"\bpak\b|belastung|gutachten|lärm|luftreinhalt|schadstoff|altlast|umwelt|klima"),
    ("building", r"bauvorhaben|neubau|innenentwicklung|bau-turbo|hochbau|gebäude|baumaßnahme|"
                 r"erweiterung|gewerbefläche|grundstück"),
    ("renovation", r"sanierung|pflaster|instandsetzung|modernisierung|handwerk|reparatur"),
    ("money", r"haushalt|steuer|gebühr|entgelt|beitr|zuschuss|finanz|kredit|kosten|förder|vermächtnis"),
    ("route", r"straßenraum|straßennetz|querschnitt|straßenbau|straßenausbau|verkehrsfläche|bahnhof|"
              r"^\S*stra(?:ß|ss)e$"),
    ("statute", r"satzung|richtlinie|geschäftsordnung|verordnung"),
)]

#: Politikfeld eines Beschlusses → Piktogramm. Greift erst nach der Sitzung
#: (vorher gibt es keinen Beschluss) und nur, wo der Titel nichts trifft.
POLICY_ICONS: dict[str, str] = {
    "finanzen": "money",
    "wirtschaft": "money",
    "bauen_wohnen": "building",
    "verkehr": "route",
    "klima_umwelt": "environment",
    "kultur_sport": "culture",
    "bildung": "school",
    "soziales_gesundheit": "social",
    "migration_integration": "social",
}

#: Rückfall nach Art — jeder Punkt trägt ein Zeichen.
FALLBACK_ICONS: dict[str, str] = {
    "formality": "formalities",
    "question_time": "citizen_question",
    "inquiries": "inquiries",
    "announcement": "announcement",
    "report": "report",
    "motion": "motion",
}


# ---------------------------------------------------------------------------
# Gremien: Kurzformen für die Etappen des Rats.

#: Amtlicher Name → Kurzform. Dieselbe Tabelle wie ``SHORT`` in
#: ``web/frontend/lib/committees.ts``; ``tests/test_course.py`` hält beide
#: gleich (die App führt eine eigene Abschrift).
COMMITTEE_SHORT: dict[str, str] = {
    "Rat": "Rat",
    "Rat der Stadt Oldenburg": "Rat",
    "Rat der Stadt Oldenburg (Oldb)": "Rat",
    "Verwaltungsausschuss": "Verwaltungsausschuss",
    "Ausschuss für Allgemeine Angelegenheiten": "Allgemeine Angelegenheiten",
    "Ausschuss für Finanzen und Beteiligungen": "Finanzen & Beteiligungen",
    "Ausschuss für Integration und Migration": "Integration & Migration",
    "Ausschuss für Stadtgrün, Umwelt und Klima": "Stadtgrün & Klima",
    "Ausschuss für Stadtplanung und Bauen": "Stadtplanung & Bauen",
    "Ausschuss für Wirtschaftsförderung, Digitalisierung und internationale Zusammenarbeit":
        "Wirtschaft & Digitales",
    "Betriebsausschuss Abfallwirtschaftsbetrieb": "Abfallwirtschaft",
    "Betriebsausschuss Eigenbetrieb Gebäudewirtschaft und Hochbau": "Betrieb Gebäudewirtschaft",
    "Jugendhilfeausschuss": "Jugendhilfe",
    "Kulturausschuss": "Kultur",
    "Schulausschuss": "Schule",
    "Sozialausschuss": "Soziales",
    "Ausschuss für Gesundheit und Soziales": "Gesundheit & Soziales",
    "Sportausschuss": "Sport",
    "Verkehrsausschuss": "Verkehr",
    "Ausschuss für Umwelt, Grünflächen und Klimaschutz": "Umwelt & Klima",
    "Ausschuss für Umwelt und Klimaschutz": "Umwelt & Klima",
    "Betriebsausschuss Gebäudewirtschaft und Hochbau": "Betrieb Gebäudewirtschaft",
    "Ausschuss für Wirtschaftsförderung und Digitalisierung": "Wirtschaft & Digitales",
}

#: Kurzform → (mittlere Form, knappste Form). Die Etappe im Kurs nimmt den
#: längsten Namen, der in ihre Zellen passt; auf dem Handy bleibt die knappste.
COMMITTEE_STAGE_NAMES: dict[str, tuple[str, str]] = {
    "Allgemeine Angelegenheiten": ("Allgemeines", "Allg."),
    "Finanzen & Beteiligungen": ("Finanzen", "Geld"),
    "Integration & Migration": ("Integration", "Integr."),
    "Stadtgrün & Klima": ("Stadtgrün", "Grün"),
    "Umwelt & Klima": ("Umwelt", "Umwelt"),
    "Stadtplanung & Bauen": ("Stadtplanung", "Bauen"),
    "Wirtschaft & Digitales": ("Wirtschaft", "Wirtsch."),
    "Abfallwirtschaft": ("Abfall", "Abfall"),
    "Betrieb Gebäudewirtschaft": ("Gebäude", "Gebäude"),
    "Jugendhilfe": ("Jugendhilfe", "Jugend"),
    "Kultur": ("Kultur", "Kultur"),
    "Schule": ("Schule", "Schule"),
    "Soziales": ("Soziales", "Soziales"),
    "Gesundheit & Soziales": ("Soziales", "Soziales"),
    "Sport": ("Sport", "Sport"),
    "Verkehr": ("Verkehr", "Verkehr"),
    "Verwaltungsausschuss": ("VA", "VA"),
    "Rat": ("Rat", "Rat"),
}


#: Wie der Rat einen Ausschuss in seiner Tagesordnung nennt, wenn es nicht
#: der amtliche Name ist („Betriebsausschuss des Abfallwirtschaftsbetriebes
#: der Stadt Oldenburg vom …"). Nur für die Abschnitte — die Sitzungen selbst
#: tragen den amtlichen Namen.
SECTION_ALIASES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"abfallwirtschaft", re.IGNORECASE), "Abfallwirtschaft"),
    (re.compile(r"gebäudewirtschaft", re.IGNORECASE), "Betrieb Gebäudewirtschaft"),
]


def section_committee(name: str) -> str:
    """Kurzform eines Ausschuss-Abschnitts im Rat."""
    if name.strip() in COMMITTEE_SHORT:
        return COMMITTEE_SHORT[name.strip()]
    for muster, kurz in SECTION_ALIASES:
        if muster.search(name):
            return kurz
    return short_committee(name)


def short_committee(name: str | None) -> str:
    """Amtlicher Gremienname → Kurzform, wie ``shortCommittee`` im Web."""
    if not name:
        return ""
    key = name.strip()
    if key in COMMITTEE_SHORT:
        return COMMITTEE_SHORT[key]
    s = re.sub(r"^Ausschuss für (den |die |das )?", "", key, flags=re.IGNORECASE)
    s = re.sub(r"^Betriebsausschuss (Eigenbetrieb )?", "", s, flags=re.IGNORECASE)
    if re.fullmatch(r"\S+ausschuss", s, flags=re.IGNORECASE):
        s = re.sub(r"s?ausschuss$", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\s+und\s+", " & ", s, flags=re.IGNORECASE).strip()
    return s if len(s) >= 2 else key


# ---------------------------------------------------------------------------
# Einzelne Punkte

def strip_result(title: str | None) -> str:
    """Titel ohne den Ergebnis-Zusatz, den das Ratsinfo nach der Sitzung anhängt."""
    t = title or ""
    m = RESULT_SUFFIX_RE.search(t)
    return (t[:m.start()] if m else t).strip()


def _applicant_match(title: str) -> re.Match[str] | None:
    """Die Klammer mit dem Absender: mit Datum („… vom 22.05.2026") oder mit
    einem, der Anträge stellen kann („(beratendes Mitglied Herr Lucks)").
    „(B-Plan S-745 A)" oder „(öffentlicher Teil)" sind keine."""
    for m in APPLICANT_RE.finditer(title):
        if m.group("date") or MOTION_SENDER_RE.search(m.group("who")):
            return m
    return None


def strip_applicant(title: str | None) -> str:
    """Absender samt Datum aus dem Titel: „Weißenmoorstraße (beratendes
    Mitglied Herr Pieper vom 22.05.2026)" → „Weißenmoorstraße". Der Absender
    steht als eigenes Feld daneben (``applicant``)."""
    t = title or ""
    m = _applicant_match(t)
    return (t[:m.start()] + t[m.end():]).strip() if m else t.strip()


def parse_number(item_number: str | None) -> tuple[str, tuple[int, ...]] | None:
    m = NUMBER_RE.match(item_number or "")
    if not m:
        return None
    teile = tuple(int(t) for t in m.group(2).split(".") if t.isdigit())
    return (m.group(1), teile) if teile else None


def parent_number(item_number: str | None) -> str | None:
    """„Ö 11.3" → „Ö 11"; ``None`` ohne Unterebene."""
    m = NUMBER_RE.match(item_number or "")
    if not m or "." not in m.group(2):
        return None
    return f"{m.group(1)} {m.group(2).rsplit('.', 1)[0]}"


def is_motion(title: str | None, under_motions: bool = False) -> bool:
    """Ein Antrag aus dem Rat: unter der Rubrik „Anträge …", mit Zusatz
    „- Beschlussantrag" oder mit Absender und Datum in Klammern."""
    t = strip_result(title)
    absender = _applicant_match(t)
    return bool(under_motions or MOTION_SUFFIX_RE.search(t) or DRINGLICH_RE.match(t)
                or (absender and MOTION_SENDER_RE.search(absender.group("who")))
                or re.match(r"^\s*(?:Änderungs|Ergänzungs|Zusatz)?antrag\s+(?:der|des|von)\b", t,
                            re.IGNORECASE))


def applicant(title: str | None) -> str | None:
    """„Weißenmoorstraße (beratendes Mitglied Herr Pieper vom 22.05.2026)" →
    „beratendes Mitglied Herr Pieper". Nur für Anträge sinnvoll."""
    t = strip_result(title)
    m = _applicant_match(t)
    if m:
        return " ".join(m.group("who").split()) or None
    m = re.match(r"^\s*(?:Änderungs|Ergänzungs|Zusatz)?antrag\s+(?:der|des|von)\s+(?P<who>.+?)\s+"
                 r"vom\s+\d", t, re.IGNORECASE)
    return " ".join(m.group("who").split()) if m else None


def item_type(title: str | None, template_kind: str | None, deliberation: str | None,
              *, formality: bool = False, motion: bool = False) -> str:
    """Was für ein Punkt ist das? Schlüssel aus ``TYPE_LABELS``.

    Ein Antrag bleibt ein Antrag, auch wenn die Verwaltung eine Berichtsvorlage
    dazu schreibt (4654, Ö 11.2). Eine Beschlussvorlage, die das Gremium nur
    vorberät oder zur Kenntnis bekommt, heißt „Vorberatung" — entscheiden tut
    ein anderes (die VBN-Tarifanpassung ist im Fachausschuss „Kenntnisnahme",
    weil der Rat beschließt)."""
    t = strip_result(title)
    if formality:
        return "formality"
    if QUESTION_TIME_RE.search(t):
        return "question_time"
    if INQUIRIES_RE.search(t):
        return "inquiries"
    if ANNOUNCEMENT_RE.search(t):
        return "announcement"
    if motion:
        return "motion"
    kind = (template_kind or "").lower()
    art = (deliberation or "").lower()
    if kind.startswith("beschluss"):
        return "decision" if (not art or "entscheid" in art) else "preliminary"
    if kind.startswith(("bericht", "personalbericht")):
        return "report"
    if DECISION_SUFFIX_RE.search(t):
        return "decision"
    if REPORT_SUFFIX_RE.search(t):
        return "report"
    return "other"


def icon(short_title: str | None, type_: str, policy_field: str | None = None) -> str:
    """Piktogramm-Schlüssel (``ICONS``). Rahmenpunkte tragen ihr festes
    Zeichen; sonst Titel-Regeln, dann Politikfeld, dann Rückfall nach Art."""
    if type_ in ("formality", "question_time", "inquiries", "announcement"):
        return FALLBACK_ICONS[type_]
    t = (short_title or "").strip()
    for key, muster in ICON_RULES:
        if muster.search(t):
            return key
    if policy_field and policy_field in POLICY_ICONS:
        return POLICY_ICONS[policy_field]
    return FALLBACK_ICONS.get(type_, "statute")


def icon_from_rule(short_title: str | None) -> str | None:
    """Der Treffer der Titel-Regeln allein — für die Messung (Plan: ≥ 70 %)."""
    t = (short_title or "").strip()
    return next((key for key, muster in ICON_RULES if muster.search(t)), None)


# ---------------------------------------------------------------------------
# Etappen

def _range(numbers: list[str]) -> str:
    """„Ö 5 – Ö 10"; eine Nummer allein steht allein."""
    if not numbers:
        return ""
    return numbers[0] if numbers[0] == numbers[-1] else f"{numbers[0]} – {numbers[-1]}"


def _compact_range(numbers: list[str]) -> str:
    """„Ö 1–3", „N 13–15": oberste Ebene, Präfix einmal."""
    erste, letzte = parse_number(numbers[0]), parse_number(numbers[-1])
    if not erste or not letzte:
        return _range(numbers)
    a, b = erste[1][0], letzte[1][0]
    return f"{erste[0]} {a}" if a == b else f"{erste[0]} {a}–{b}"


def _stage(kind: str, name: str, name_medium: str | None = None, name_short: str | None = None,
           subtitle: str | None = None, heading: str | None = None) -> dict[str, Any]:
    return {"kind": kind, "name": name, "name_medium": name_medium, "name_short": name_short,
            "subtitle": subtitle, "heading": heading, "rows": []}


def build_stages(rows: list[dict], project_headings: set[str], urgent: set[str]) -> list[dict]:
    """Die Etappen einer Tagesordnung.

    ``rows``: alle Zeilen in Tagesordnungs-Reihenfolge, je ``item_number``,
    ``title``, ``template_number``, ``is_public``. ``project_headings``: die
    Überschriften, die ein Vorhaben benennen (``_ueberschriften``), ``urgent``:
    die Dringlichkeitsanträge.

    Rückgabe: Etappen mit ``kind``, Namen, ``range``, ``count`` und ``cells``
    (je ``label``, ``title``, ``items``). Passt die Tagesordnung auf keine
    Regel, gibt es EINE Etappe „Tagesordnung" — lieber schlicht als falsch
    gegliedert.
    """
    oeffentlich = [r for r in rows if r.get("is_public") and r["item_number"] not in urgent]
    geschlossen = [r for r in rows if not r.get("is_public")]
    dringlich = [r for r in rows if r.get("is_public") and r["item_number"] in urgent]

    kinder: dict[str, int] = {}
    for r in rows:
        eltern = parent_number(r["item_number"])
        if eltern:
            kinder[eltern] = kinder.get(eltern, 0) + 1

    def kopf(r: dict) -> bool:
        return not (r.get("template_number") or "").strip() and kinder.get(r["item_number"], 0) > 0

    oeff_nr = {z[1] for r in oeffentlich if (z := parse_number(r["item_number"]))}
    schlicht = (any(parse_number(r["item_number"]) is None for r in oeffentlich)
                or _oeffentlich_nach_geschlossen(rows, urgent, oeff_nr))

    etappen: list[dict] = []
    if schlicht:
        haupt = _stage("agenda", "Tagesordnung", None, "Tagesordnung")
        haupt["rows"] = [r for r in oeffentlich if not kopf(r)]
        etappen.append(haupt)
    else:
        etappen = _gliedern(oeffentlich, kopf, project_headings)

    if dringlich:
        stufe = _stage("urgent", "Dringlich", None, "Dringl.")
        stufe["rows"] = dringlich
        # Direkt nach „Zum Start" — in der Tagesordnung stehen die Zusatzpunkte
        # am Ende, verhandelt werden sie vorn.
        pos = 1 if etappen and etappen[0]["kind"] == "start" else 0
        etappen.insert(pos, stufe)

    out = [_fertig(e) for e in etappen if e["rows"]]
    if geschlossen:
        # Gezählt wird jeder nichtöffentliche Punkt; der Bereich nennt den
        # Block am Ende. Ein einzelner gesperrter Unterpunkt unter einer
        # öffentlichen Rubrik („Ö 17 Anträge …" → „N 17.1", Finanzausschuss
        # 02.09.2026) steht mitten in der Tagesordnung und gehört nicht hinein.
        block = [r["item_number"] for r in geschlossen if not _unter_oeffentlichem(r, oeff_nr)]
        nummern = block or [r["item_number"] for r in geschlossen]
        out.append({
            "kind": "closed", "name": "Nichtöffentlicher Teil", "name_medium": "Nichtöffentlich",
            "name_short": None, "subtitle": None,
            "range": _range(nummern), "count": len(geschlossen),
            "cells": [{"label": _compact_range(nummern), "title": None, "items": []}],
        })
    return out


def _unter_oeffentlichem(r: dict, oeff_nr: set[tuple]) -> bool:
    """Hängt ein nichtöffentlicher Punkt unter einem öffentlichen? Verglichen
    wird die Nummer ohne Präfix: „N 17.1" gehört zu „Ö 17"."""
    eltern = parent_number(r["item_number"])
    zahl = parse_number(eltern) if eltern else None
    return bool(zahl and zahl[1] in oeff_nr)


def _oeffentlich_nach_geschlossen(rows: list[dict], urgent: set[str], oeff_nr: set[tuple]) -> bool:
    """Steht ein öffentlicher Punkt hinter dem nichtöffentlichen Teil? Dann
    stimmt die Linie „Anker bis Schloss" nicht mehr. Ein gesperrter
    Unterpunkt einer öffentlichen Rubrik eröffnet den Teil nicht."""
    seit_geschlossen = False
    for r in rows:
        if not r.get("is_public"):
            if not _unter_oeffentlichem(r, oeff_nr):
                seit_geschlossen = True
        elif seit_geschlossen and r["item_number"] not in urgent:
            return True
    return False


def _gliedern(oeffentlich: list[dict], kopf, project_headings: set[str]) -> list[dict]:
    """Start, Inhalt, Rubriken, Schluss — der Regelfall."""
    def formalie(r: dict) -> bool:
        if FORMALITY_RE.search(strip_result(r["title"])):
            return True
        eltern = parent_number(r["item_number"])
        return bool(eltern and eltern in formal_koepfe)

    def rubrik(r: dict) -> bool:
        # Ein Ausschuss-Abschnitt oder „Anträge …" ist immer eine Rubrik, auch
        # wenn die Wortprobe ihn zufällig für ein Vorhaben hielte.
        if not kopf(r) or formalie(r):
            return False
        titel = strip_result(r["title"])
        return bool(SECTION_RE.match(titel) or MOTIONS_RE.match(titel)
                    or r["item_number"] not in project_headings)

    formal_koepfe = {r["item_number"] for r in oeffentlich
                     if kopf(r) and FORMALITY_RE.search(strip_result(r["title"]))}
    rubrik_nr = {r["item_number"] for r in oeffentlich if rubrik(r)}

    def rahmen(r: dict) -> bool:
        return formalie(r) or bool(FRAME_RE.search(strip_result(r["title"])))

    def inhalt(r: dict) -> bool:
        # Ein Rubrik-Kopf zählt mit: Er eröffnet Inhalt, auch wenn er selbst keiner ist.
        return r["item_number"] in rubrik_nr or not (rahmen(r) or kopf(r))

    idx = [i for i, r in enumerate(oeffentlich) if inhalt(r)]
    erster, letzter = (idx[0], idx[-1]) if idx else (len(oeffentlich), -1)

    start = _stage("start", "Zum Start", None, "Start")
    schluss = _stage("end", "Zum Schluss", None, "Schluss")
    etappen: list[dict] = [start]
    aktuell: dict | None = None        # die laufende Inhalts- oder Rubrik-Etappe
    offene_rubrik: str | None = None

    for i, r in enumerate(oeffentlich):
        nr = r["item_number"]
        if nr in rubrik_nr:
            aktuell = _rubrik_etappe(r)
            etappen.append(aktuell)
            offene_rubrik = nr
            continue
        if kopf(r) and nr not in rubrik_nr and nr not in formal_koepfe:
            continue                     # Vorhaben: nur eine Zwischenzeile, kein Punkt
        if offene_rubrik and _gehoert_zu(nr, offene_rubrik):
            assert aktuell is not None
            aktuell["rows"].append(r)
            continue
        offene_rubrik = None
        if not idx:
            (schluss if END_RE.search(strip_result(r["title"])) else start)["rows"].append(r)
            continue
        if i < erster:
            start["rows"].append(r)
        elif i > letzter and rahmen(r):
            schluss["rows"].append(r)
        else:
            if aktuell is None or aktuell["kind"] != "content":
                aktuell = _stage("content", "Beschlüsse und Berichte", None, "Beschlüsse")
                etappen.append(aktuell)
            aktuell["rows"].append(r)
    etappen.append(schluss)
    for e in etappen:
        e["_formalie"] = {r["item_number"] for r in e["rows"] if formalie(r)}
    return etappen


def _gehoert_zu(nr: str, kopf_nr: str) -> bool:
    eltern = parent_number(nr)
    while eltern:
        if eltern == kopf_nr:
            return True
        eltern = parent_number(eltern)
    return False


def _rubrik_etappe(r: dict) -> dict:
    titel = strip_result(r["title"])
    m = SECTION_RE.match(titel)
    if m:
        kurz = section_committee(m.group("committee"))
        mittel, knapp = COMMITTEE_STAGE_NAMES.get(kurz, (None, None))
        return _stage("section", kurz, mittel, knapp, subtitle=titel, heading=r["item_number"])
    m = MOTIONS_RE.match(titel)
    if m:
        rest = m.group("rest").strip() or None
        return _stage("motions", "Anträge", None, "Anträge", subtitle=rest, heading=r["item_number"])
    knapp = titel if len(titel) <= 12 else None
    return _stage("section", titel, None, knapp, heading=r["item_number"])


def _fertig(e: dict) -> dict:
    """Zeilen → Zellen. Aufeinanderfolgende Formalien bilden EINE Zelle."""
    formal = e.pop("_formalie", set())
    zellen: list[dict] = []
    for r in e["rows"]:
        nr = r["item_number"]
        if nr in formal and zellen and zellen[-1]["title"] == "Formalien":
            zellen[-1]["items"].append(nr)
            continue
        zellen.append({"label": nr, "title": "Formalien" if nr in formal else None, "items": [nr]})
    for z in zellen:
        if len(z["items"]) > 1:
            z["label"] = _compact_range(z["items"])
    nummern = [r["item_number"] for r in e["rows"]]
    kopf = e.pop("heading")
    return {
        "kind": e["kind"], "name": e["name"], "name_medium": e["name_medium"],
        "name_short": e["name_short"], "subtitle": e["subtitle"],
        # Eine Rubrik nennt ihren Kopf („Ö 11 · 3 Anträge"), alle anderen den Bereich.
        "range": kopf or _range(nummern),
        "count": len(nummern),
        "cells": zellen,
    }


# ---------------------------------------------------------------------------
# Vertagt

def postponed_counts(current: list[dict], earlier: list[dict], postponed_decisions: set[tuple]) -> dict[str, int]:
    """Wie oft stand ein Punkt schon in diesem Gremium und wurde vertagt?

    ``current``: die Zeilen der Sitzung (``item_number``, ``title``,
    ``template_number``). ``earlier``: frühere Zeilen DESSELBEN Gremiums
    (dazu ``ksinr``). ``postponed_decisions``: (ksinr, Nummer ohne Präfix) der
    Beschlüsse mit Ergebnis „vertagt".

    Zwei Belege, die sich am Bestand gegenseitig bestätigen: der Zusatz
    „Beschluss: zurückgestellt/abgesetzt" im Titel des früheren Punkts (ohne
    Protokoll sofort da) und ein vertagter Beschluss. Zugeordnet wird über die
    Vorlage; ein Antrag ohne Vorlage nur, wenn sein Titel wörtlich gleich ist
    UND ein Datum trägt („… vom 22.05.2026") — ein geratener gelber Punkt ist
    schlimmer als keiner. Gezählt werden Sitzungen, nicht Zeilen.
    """
    def vertagt(r: dict) -> bool:
        m = RESULT_SUFFIX_RE.search(r.get("title") or "")
        if m and re.search(r"zurückgestellt|abgesetzt|vertagt", m.group(1), re.IGNORECASE):
            return True
        nummer = re.sub(r"^\s*[A-Za-zÖÄÜöäü]+\s+", "", r.get("item_number") or "").strip()
        return (r.get("ksinr"), nummer) in postponed_decisions

    nach_vorlage: dict[str, set] = {}
    nach_titel: dict[str, set] = {}
    for r in earlier:
        if not vertagt(r):
            continue
        tn = (r.get("template_number") or "").strip()
        if tn:
            nach_vorlage.setdefault(tn, set()).add(r.get("ksinr"))
        else:
            nach_titel.setdefault(strip_result(r.get("title")), set()).add(r.get("ksinr"))

    out: dict[str, int] = {}
    for r in current:
        tn = (r.get("template_number") or "").strip()
        if tn:
            n = len(nach_vorlage.get(tn, ()))
        else:
            titel = strip_result(r.get("title"))
            n = len(nach_titel.get(titel, ())) if DATED_RE.search(titel) else 0
        out[r["item_number"]] = n
    return out


# ---------------------------------------------------------------------------
# Ergebnis aus dem Titel und der Satz zur Sitzung

#: Was das Ratsinfo nach der Sitzung an den Titel hängt → Ergebnis-Schlüssel
#: der Beschlüsse. „an Fachausschuss verwiesen" ist kein Ergebnis im Sinne
#: der Farbgrammatik und bleibt ``None``.
_TITEL_ERGEBNIS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"zurückgestellt|abgesetzt|vertagt", re.IGNORECASE), "postponed"),
    (re.compile(r"abgelehnt", re.IGNORECASE), "rejected"),
    (re.compile(r"zur Kenntnis", re.IGNORECASE), "noted"),
    (re.compile(r"gilt als behandelt|erledigt", re.IGNORECASE), "settled"),
    (re.compile(r"beschlossen|angenommen|zugestimmt", re.IGNORECASE), "accepted"),
]


def outcome_from_title(title: str | None) -> str | None:
    m = RESULT_SUFFIX_RE.search(title or "")
    if not m:
        return None
    return next((k for muster, k in _TITEL_ERGEBNIS if muster.search(m.group(1))), None)


_ZAHLWORT = ["null", "ein", "zwei", "drei", "vier", "fünf", "sechs", "sieben", "acht", "neun",
             "zehn", "elf", "zwölf"]


def _zahl(n: int) -> str:
    return _ZAHLWORT[n] if 0 <= n < len(_ZAHLWORT) else str(n)


def _titel(t: str) -> str:
    """Ein Titel im Satz, in deutschen Anführungszeichen. Zitiert der Titel
    selbst („Teileinziehung der Straße "Junkerstraße"“), wird das innere Paar
    zu halben Zeichen — „… ‚Junkerstraße‘“, wie im Deutschen üblich."""
    t = re.sub(r'["„“]([^"„“]+)["“”]', r"‚\1‘", t.strip())
    return f"„{t}“"


def _aufzaehlen(teile: list[str]) -> str:
    return teile[0] if len(teile) == 1 else ", ".join(teile[:-1]) + " und " + teile[-1]


#: Die Arten im Plural — für „Dazu 12 Vorberatungen, 5 Anträge und 3 Berichte".
_ARTEN: dict[str, tuple[str, str]] = {
    "decision": ("Entscheidung", "Entscheidungen"),
    "preliminary": ("Vorberatung", "Vorberatungen"),
    "motion": ("Antrag", "Anträge"),
    "report": ("Bericht", "Berichte"),
    "other": ("weiterer Punkt", "weitere Punkte"),
}


def _zusammensetzung(punkte: list[dict]) -> str | None:
    """„12 Vorberatungen, 5 Anträge und 3 Berichte" — die häufigsten Arten
    zuerst, höchstens drei; der Rest als „N weitere Punkte"."""
    zahl: dict[str, int] = {}
    for it in punkte:
        art = it["type"] if it["type"] in _ARTEN else "other"
        zahl[art] = zahl.get(art, 0) + 1
    if not zahl:
        return None
    # „weitere Punkte" immer zuletzt — es ist der Rest, keine Art.
    reihe = sorted(zahl.items(), key=lambda kv: (kv[0] == "other", -kv[1]))
    teile = [f"{n} {_ARTEN[a][0 if n == 1 else 1]}" for a, n in reihe[:3]]
    rest = sum(n for _a, n in reihe[3:])
    if rest:
        teile.append(f"{rest} {'weiterer Punkt' if rest == 1 else 'weitere Punkte'}")
    return _aufzaehlen(teile)


def summary_sentence(items: dict[str, dict], outcomes: dict[str, str | None],
                     votes: dict[str, str | None], *, rat: bool, vorbei: bool = False) -> str | None:
    """Der Satz zur Sitzung — gerechnet, ohne Modell (Plan 3.1, Schritt 3.6).

    ``outcomes`` leer heißt: kein Protokoll. Dann sagt der Satz, WORUM es
    geht: die wichtigen Punkte beim Namen, danach, was sonst ansteht, nach
    Art gezählt („Im Mittelpunkt: Geschäftsordnung und Bildung des
    Verwaltungsausschusses. Dazu 12 Vorberatungen und 5 Anträge."). Bis
    11/2026 stand dort nur die Zahl („21 Punkte zur Beratung") — Tim: keine
    sinnvolle Information. ``vorbei``: Die Sitzung ist gewesen, das Protokoll
    fehlt noch; das sagt der Satz dann auch. Mit Protokoll sagt er, was
    herauskam: wie viele Beschlussvorlagen angenommen wurden, welche
    wichtigen darunter, was vertagt oder abgelehnt wurde. Eine Zählung, die
    null ergibt, entfällt.
    """
    inhalt = {nr: it for nr, it in items.items() if it["type"] not in FRAME_TYPES}
    if not inhalt:
        return None
    if not outcomes:
        # Höchstens zwei beim Namen; ein dritter wichtiger zählt beim Rest mit.
        # „… und ein weiterer wichtiger Punkt“ sagte nichts (Tim, 11.11.2026).
        wichtig = [it for it in inhalt.values() if it["important"]][:2]
        rest = [it for it in inhalt.values() if it not in wichtig]
        saetze: list[str] = []
        zusammen = _zusammensetzung(rest)
        if wichtig:
            # In Anführungszeichen: Die Titel tragen selbst Kommas und „und“
            # („Geschäftsordnung für den Rat, den Verwaltungsausschuss und die
            # Ratsausschüsse“) — ohne Zeichen verschwimmt die Aufzählung. Mehr
            # als zwei beim Namen werden zur Wand; die Karten darunter nennen sie.
            namen = [_titel(it["short_title"]) for it in wichtig]
            saetze.append(f"Im Mittelpunkt: {_aufzaehlen(namen)}.")
            if zusammen:
                saetze.append(f"Dazu {zusammen}.")
        elif zusammen:
            saetze.append(f"Auf der Tagesordnung: {zusammen}.")
        v = sum(1 for it in inhalt.values() if it["postponed"])
        if v:
            saetze.append(f"{'Einer stand' if v == 1 else _zahl(v).capitalize() + ' standen'} schon einmal "
                          f"hier und {'wurde' if v == 1 else 'wurden'} vertagt.")
        if vorbei:
            saetze.append("Das Protokoll liegt noch nicht vor.")
        return " ".join(saetze) or None

    wer = "Der Rat" if rat else "Der Ausschuss"
    vorlagen = [nr for nr, it in inhalt.items() if it["type"] in ("decision", "preliminary")]
    angenommen = [nr for nr in vorlagen if outcomes.get(nr) == "accepted"]
    saetze: list[str] = []
    if vorlagen and angenommen:
        einstimmig = all(votes.get(nr) == "unanimous" for nr in angenommen)
        # Zahlwörter nur, solange beide Zahlen eines haben — „zwölf von 13" liest sich schief.
        wort = _zahl if len(vorlagen) < len(_ZAHLWORT) else str
        menge = (f"alle {wort(len(vorlagen))} Beschlussvorlagen"
                 if len(angenommen) == len(vorlagen) and len(vorlagen) > 1
                 else f"{wort(len(angenommen))} von {wort(len(vorlagen))} Beschlussvorlagen"
                 if len(vorlagen) > 1 else "die Beschlussvorlage")
        satz = f"{wer} hat {menge}{' einstimmig' if einstimmig else ''} angenommen"
        wichtig = [_titel(inhalt[nr]["short_title"]) for nr in angenommen if inhalt[nr]["important"]][:2]
        if wichtig:
            satz += f", darunter {_aufzaehlen(wichtig)}"
        saetze.append(satz + ".")
    for schluessel, partizip in (("postponed", "vertagt"), ("rejected", "abgelehnt")):
        nrs = [nr for nr in inhalt if outcomes.get(nr) == schluessel]
        if not nrs:
            continue
        if len(nrs) <= 2:
            saetze.append(f"{'Vertagt' if schluessel == 'postponed' else 'Abgelehnt'} "
                          f"{'wurde' if len(nrs) == 1 else 'wurden'} {_aufzaehlen([_titel(inhalt[n]['short_title']) for n in nrs])}.")
        else:
            saetze.append(f"{_zahl(len(nrs)).capitalize()} Punkte wurden {partizip}.")
    return " ".join(saetze) or None
