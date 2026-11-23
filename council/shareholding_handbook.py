"""Das Handbuch Beteiligungen der Stadt Oldenburg — die Regeln, die sich die
Stadt für ihre Gesellschaften gegeben hat.

**Wozu.** „Wer bestimmt eigentlich beim Klinikum?", „Darf der Rat dem
Aufsichtsrat etwas vorschreiben?", „Was bekommt man als Aufsichtsrat?",
„Wann muss der Beteiligungsbericht da sein?" — solche Fragen hat weder das
Beschluss-Archiv noch der Beteiligungsbericht. Die Antwort steht im Handbuch
Beteiligungen: drei Richtlinien (Oldenburger Corporate Governance Kodex,
Beteiligungsmanagement, Korruptionsvorbeugung), vom Rat am 27.11.2023
beschlossen (Vorlage 23/0599/1), als Broschüre Stand Januar 2025.

**Was hier steht: belegte Kurzfassungen, kein Wortlaut.** Jede Regel ist auf
zwei bis vier Sätze gebracht und nennt ihre Seite der Broschüre. Nachgelesen
am 23.11.2026, Satz für Satz gegen das PDF — nichts aus dem Gedächtnis und
nichts aus dem NKomVG ergänzt, was das Handbuch nicht selbst sagt. Das
Handbuch ist auf die GmbH zugeschnitten (S. 10); für Anstalt und Eigenbetrieb
gilt es „sinngemäß", und genau so steht es in jedem Text, der darauf ankommt.

**Wann eine Regel greift: an der FRAGE, deterministisch** — wie die
Geschäftsordnung (:mod:`council.rules_of_procedure`) und die Erklärtexte
(:mod:`kern.erklaerwissen`). Allgemeine Wörter („öffentlich", „Vergütung",
„wann") ziehen nur zusammen mit einer Gesellschaft (dieselbe Erkennung wie
die Facette ``companies``); die Fachwörter („Aufsichtsrat",
„Gesellschafterversammlung") ziehen allein. ``tests/test_shareholding_handbook.py``
hält beide Richtungen fest.

**Was es NICHT ist: ein Prüfbericht.** Ob eine Gesellschaft die Vorgaben
einhält, steht hier nicht und lässt sich aus unseren Daten nicht ablesen —
ein fehlender Vergütungsbericht auf einer Website ist kein Beweis, dass es
ihn nicht gibt. Der Baustein sagt das dem Modell ausdrücklich.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from council import geld
from council.geld import companies

TITLE = "Handbuch Beteiligungen für die Stadt Oldenburg und ihre Beteiligungen"
SHORT_TITLE = "Handbuch Beteiligungen"
#: Stand der Broschüre (Impressum S. 2).
VERSION = "Januar 2025"
ADOPTED_DATE = "2023-11-27"
ADOPTED_TEMPLATE = "23/0599/1"
#: Ratsbeschluss in Ratslotse (dev und Prod teilen seit 11/2026 die ids).
ADOPTED_DECISION_ID = 18043
SOURCE_URL = ("https://www.oldenburg.de/fileadmin/oldenburg/Benutzer/Dateien/"
              "20_Controlling_und_Finanzen/Handbuch_Beteiligungen_DIN_A5_b.pdf")

#: Höchstens so viele Regeln je Frage. Zwei, weil eine Frage selten mehr als
#: zwei Regeln berührt und jeder weitere Text die Zahlen des Steckbriefs im
#: Prompt nach hinten schiebt (dieselbe Abwägung wie ``erklaerwissen``).
MAX_RULES = 2


@dataclass(frozen=True)
class Rule:
    """Eine Regel des Handbuchs: wann sie greift, was sie sagt, wo sie steht."""
    key: str
    title: str
    #: Greift allein — ein Fachwort, das nur hier gemeint sein kann.
    trigger: re.Pattern[str] | None
    #: Greift nur, wenn die Frage zugleich eine Gesellschaft meint.
    trigger_with_company: re.Pattern[str] | None
    text: str
    #: Seiten der Broschüre, z. B. „S. 14–15".
    pages: str


def _re(muster: str) -> re.Pattern[str]:
    return re.compile(muster)


#: Reihenfolge = Vorrang, wenn mehr als ``MAX_RULES`` greifen: das Engere
#: zuerst. „Was verdient ein Aufsichtsrat?" soll die Vergütung bekommen, nicht
#: die allgemeine Rolle des Aufsichtsrats.
RULES: tuple[Rule, ...] = (
    Rule(
        key="holding_management",
        title="Das Beteiligungsmanagement der Stadt",
        trigger=_re(r"beteiligungsmanagement|beteiligungscontrolling|mandatsbetreuung"),
        trigger_with_company=None,
        text=(
            "Das Beteiligungsmanagement der Stadt sitzt zwischen der Stadt als "
            "Gesellschafterin und ihren Unternehmen. Es umfasst das "
            "Beteiligungscontrolling (Wirtschaftspläne, Quartalsberichte, "
            "Jahresabschlüsse, Risikomanagement), die Betreuung der städtischen "
            "Mitglieder in den Gremien und die Beteiligungsverwaltung "
            "(Beteiligungsbericht, Verträge). Es nimmt in der Regel an den Sitzungen "
            "von Gesellschafterversammlung und Aufsichtsrat teil und erhält deren "
            "Unterlagen. Damit erfüllt die Stadt ihre Pflicht aus § 150 NKomVG."),
        pages="S. 14, 31–35"),
    Rule(
        key="audit",
        title="Wer die Jahresabschlüsse prüft",
        trigger=_re(r"bestaetigungsvermerk|feststellungsvermerk|abschlusspruef\w*|"
                    r"wirtschaftspruef\w*"),
        trigger_with_company=_re(r"wer prueft|rechnungspruefungsamt|gepruef|pruefung"),
        text=(
            "Jahresabschlüsse werden nach den gesetzlichen Vorschriften erstellt und "
            "geprüft. Zuständig ist grundsätzlich das Rechnungsprüfungsamt der Stadt "
            "(§§ 157, 158 NKomVG), wenn nicht ein anderes Gesetz die Prüfung "
            "vorschreibt. Beauftragt es eine Wirtschaftsprüfung, gehen deren "
            "Prüfungsbericht und Bestätigungsvermerk an das Rechnungsprüfungsamt; "
            "es ergänzt seine Bemerkungen (Feststellungsvermerk), und erst damit ist "
            "die Prüfung abgeschlossen. Gilt eine andere Vorschrift (etwa das "
            "Handelsgesetzbuch), wählt die Stadt eine Abschlussprüferin oder einen "
            "Abschlussprüfer."),
        pages="S. 32–33"),
    Rule(
        key="management_board",
        title="Die Geschäftsführung",
        trigger=_re(r"geschaeftsfuehr\w* [^?!.]{0,40}(?:bestell|abberuf|ernenn|amtszeit|"
                    r"wie lange|nebentaetig|nebenjob)|"
                    r"(?:wer|wie) (?:bestellt|ernennt|waehlt|bestimmt|setzt)[^?!.]{0,30}"
                    r"geschaeftsfuehr"),
        trigger_with_company=None,
        text=(
            "Die Geschäftsführung leitet das Unternehmen. Die Gesellschafterversammlung "
            "bestellt und beruft sie ab, sofern der Gesellschaftsvertrag nichts anderes "
            "regelt; die erste Bestellung gilt in der Regel für höchstens fünf Jahre, "
            "jede Verlängerung ebenso. Sie führt die Geschäfte nach Gesetz, "
            "Gesellschaftsvertrag sowie den Weisungen und Beschlüssen der "
            "Gesellschafterversammlung und gegebenenfalls des Aufsichtsrats und ist für "
            "Berichtswesen und Risikomanagement verantwortlich. Für Nebentätigkeiten braucht "
            "sie die Zustimmung von Gesellschafterversammlung oder Aufsichtsrat."),
        pages="S. 23–25"),
    Rule(
        key="compensation",
        title="Aufwandsentschädigung und Vergütung",
        trigger=_re(r"aufwandsentschaedigung[^?!.]{0,60}(?:aufsichtsr|gesellschafterversammlung)|"
                    r"(?:aufsichtsr|gesellschafterversammlung)\w*[^?!.]{0,60}"
                    r"(?:aufwandsentschaedigung|verguetung|verdien|sitzungsgeld|bezahlt|"
                    r"geld bekomm|bekommt man)|verguetungsbericht|"
                    r"(?:bekommt man|verdient man|verdienen|bezahlt|entschaedigt)[^?!.]{0,40}"
                    r"(?:aufsichtsr|gesellschafterversammlung)"),
        trigger_with_company=_re(r"aufwandsentschaedigung|verguetung|verdien\w*|"
                                 r"sitzungsgeld|gehalt|bezuege"),
        text=(
            "Wie hoch die jährliche Aufwandsentschädigung für die Vertreterinnen und "
            "Vertreter der Stadt in einer Gesellschafterversammlung oder einem "
            "Aufsichtsrat ist, regelt der Rat per Beschluss in öffentlicher Sitzung. "
            "Die Gesellschaften sollen diese Entschädigungen jedes Jahr im Bericht zur "
            "Unternehmensführung beim Jahresabschluss nennen (Vergütungsbericht) und "
            "auf ihrer Internetseite zugänglich machen. Die Vergütung der "
            "Geschäftsführung legen Gesellschafterversammlung oder Aufsichtsrat fest; "
            "sie soll feste und variable Teile haben und angemessen sein."),
        pages="S. 17, 22, 25, 27–28"),
    Rule(
        key="conflicts",
        title="Interessenkonflikte und Korruptionsvorbeugung",
        # Nur mit Gesellschaft oder Gremium („Aufsichtsrat" zählt dazu): Ein
        # Interessenkonflikt eines Ratsmitglieds im RAT regelt das NKomVG, nicht
        # dieses Handbuch.
        trigger=None,
        trigger_with_company=_re(r"interessenkonflikt|interessenskonflikt|befangen|"
                                 r"korruption|vier augen|compliance|eigene\w* interesse"),
        text=(
            "Wer für die Stadt in Gesellschafterversammlung oder Aufsichtsrat sitzt, "
            "darf keine persönlichen Interessen verfolgen und keine Geschäftschancen "
            "der Gesellschaft für sich nutzen. Interessenkonflikte sollen offengelegt "
            "werden; wesentliche und dauerhafte sollen zum Ende des Mandats führen. "
            "Berater- und Werkverträge eines Mitglieds mit der Gesellschaft brauchen "
            "die Zustimmung des Gremiums. Über die Entlastung eines Aufsichtsrats darf "
            "niemand mitbeschließen, der selbst darin sitzt. Die städtische "
            "Dienstanweisung zur Korruptionsvorbeugung gilt sinngemäß; in "
            "korruptionsanfälligen Bereichen gilt das Vier-Augen-Prinzip."),
        pages="S. 17, 22–23, 27, 38"),
    Rule(
        key="appointment",
        title="Wer die Stadt in den Gremien vertritt",
        trigger=_re(r"(?:aufsichtsr\w*|gesellschafterversammlung\w*)[^?!.]{0,60}"
                    r"(?:entsend|entsandt|bestell|benenn|gewaehlt|waehlt|besetz|"
                    r"ratsperiode|wahlperiode|nach der (?:kommunal)?wahl|neue\w* rat|"
                    r"oberbuergermeister|mandat)|"
                    r"(?:entsend|entsandt|bestell|benenn|waehlt|besetz|wer sitzt|wer kommt)"
                    r"[^?!.]{0,60}(?:aufsichtsr|gesellschafterversammlung)"),
        trigger_with_company=None,
        text=(
            "Die städtischen Mitglieder von Gesellschafterversammlung und Aufsichtsrat "
            "bestellt der Rat. Im Aufsichtsrat endet ihr Mandat mit Ablauf der "
            "Ratsperiode, in der Gesellschafterversammlung mit dem Ausscheiden aus dem "
            "Rat oder der Abberufung; die Nachfolge ist jeweils unverzüglich zu regeln. "
            "Sind mehrere Vertreter in einen Aufsichtsrat zu wählen, ist die "
            "Oberbürgermeisterin oder der Oberbürgermeister zu berücksichtigen, außer "
            "bei Verzicht; auf deren Vorschlag kann stattdessen eine andere Beschäftigte "
            "oder ein anderer Beschäftigter der Stadt benannt werden. In der Regel "
            "sollen nicht mehr als fünf Mandate gleichzeitig wahrgenommen werden."),
        pages="S. 16–17, 22"),
    Rule(
        key="supervisory_board",
        title="Was ein Aufsichtsrat tut",
        trigger=_re(r"aufsichtsr(?:at|aete|ats)\b"),
        trigger_with_company=None,
        text=(
            "Der Aufsichtsrat berät und überwacht die Geschäftsführung — ob ihre "
            "Entscheidungen ordnungsgemäß, zweckmäßig und wirtschaftlich sind. Welche "
            "Geschäfte seine vorherige Zustimmung brauchen, legt der "
            "Gesellschaftsvertrag fest; die grundlegenden Entscheidungen bleiben der "
            "Gesellschafterversammlung. Seine Mitglieder sind dem Wohl des Unternehmens "
            "verpflichtet und haften persönlich: Empfehlungen aus Rat und Ausschüssen "
            "müssen sie selbst prüfen, und sie folgen ihnen nicht, wenn sie dem "
            "Unternehmenswohl widersprechen. Er tagt mindestens zweimal im Jahr und "
            "nicht öffentlich; die Ratsmitglieder darin müssen den Rat aber über "
            "Angelegenheiten von besonderer Bedeutung frühzeitig unterrichten "
            "(§ 138 Abs. 4 NKomVG). Ohne Aufsichtsrat übernimmt die "
            "Gesellschafterversammlung seine Aufgaben."),
        pages="S. 15, 18–19, 23"),
    Rule(
        key="reporting",
        title="Welche Berichte wann fällig sind",
        trigger=_re(r"beteiligungsbericht[^?!.]{0,40}(?:wann|frist|erschein|kommt|"
                    r"veroeffentlich|wie lange)|(?:wann|bis wann)[^?!.]{0,40}"
                    r"beteiligungsbericht|quartalsbericht"),
        trigger_with_company=_re(r"(?:wirtschaftsplan|jahresabschluss|lagebericht|"
                                 r"risikobericht|hochrechnung|bericht)\w*[^?!.]{0,50}"
                                 r"(?:wann|frist|bis wann|wie oft|muss|pflicht|faellig)|"
                                 r"(?:wann|bis wann|wie oft)[^?!.]{0,50}"
                                 r"(?:wirtschaftsplan|jahresabschluss|bericht)"),
        text=(
            "Den Wirtschaftsplan — eine Planung über fünf Jahre für Erfolg, Vermögen, "
            "Investitionen und Liquidität samt Risikoeinschätzung — beschließt das "
            "Unternehmen spätestens einen Monat vor Ende des Geschäftsjahres. Zum "
            "30. Juni, 30. September und 31. Dezember berichtet die Geschäftsführung "
            "mit einem Soll-Ist-Vergleich (bisheriges Ist, Hochrechnung fürs Jahr, Plan, "
            "Abweichung), in der Regel spätestens drei Wochen danach an die Gremien und "
            "das Beteiligungsmanagement. Den Jahresabschluss stellt sie binnen drei "
            "Monaten auf, damit die Gesellschafterversammlung ihn binnen sechs Monaten "
            "feststellen kann. Die Zuarbeit für Beteiligungsbericht (§ 151 NKomVG) und "
            "Gesamtabschluss soll so rechtzeitig kommen, dass beide binnen sechs "
            "Monaten nach Ende des Haushaltsjahres entstehen können; der "
            "Beteiligungsbericht steht mindestens fünf Jahre auf oldenburg.de."),
        pages="S. 31–32, 34–35"),
    Rule(
        key="transparency",
        title="Was öffentlich ist",
        trigger=None,
        trigger_with_company=_re(r"oeffentlich|transparen|geheim|einsehen|einsicht|"
                                 r"veroeffentlich|nachlesen|internetseite|website"),
        text=(
            "Gesellschafterversammlung und Aufsichtsrat tagen nicht öffentlich. "
            "Öffentlich im Rat beschlossen werden die Jahresabschlüsse der "
            "Beteiligungsunternehmen, die Weisungen an die städtischen Vertreterinnen "
            "und Vertreter und der Rahmen ihrer Aufwandsentschädigungen. Auf ihrer "
            "Internetseite sollen die Unternehmen dauerhaft zugänglich machen: "
            "Jahresabschluss mit Anhang, Lagebericht samt Erklärung zur "
            "Unternehmensführung, den Bericht über die Entschädigungen der "
            "Gremienmitglieder, die Mitglieder des Aufsichtsrats mit Beruf und "
            "gegebenenfalls politischem Mandat sowie, soweit gesetzlich vorgeschrieben, "
            "das Hinweisgebersystem."),
        pages="S. 14, 18, 27–28"),
    Rule(
        key="governance",
        title="Wer bei einer städtischen Gesellschaft bestimmt",
        trigger=_re(r"gesellschafterversammlung"),
        trigger_with_company=_re(r"wer (?:bestimmt|entscheidet|steuert|kontrolliert|"
                                 r"ueberwacht|hat (?:das|was) (?:zu )?sagen)|"
                                 r"wie (?:steuert|kontrolliert|beaufsichtigt|lenkt)|"
                                 r"einfluss|weisung|mitbestimm|mitreden|"
                                 r"(?:darf|kann) (?:der rat|die stadt|die politik)|"
                                 r"(?:rat|stadt|politik)\w* [^?!.]{0,30}"
                                 r"(?:vorgeben|vorschreiben|anweisen|eingreifen)"),
        text=(
            "Die Stadt ist Gesellschafterin; ihre Rechte übt sie in der "
            "Gesellschafterversammlung aus, dem obersten Organ der Gesellschaft. Deren "
            "städtische Mitglieder bestellt der Rat. Die Gesellschafterversammlung kann "
            "der Geschäftsführung Weisungen erteilen und überwacht sie — ist ein "
            "Aufsichtsrat bestellt, überwacht vor allem er. Sie beschließt die "
            "strategischen Ziele der Gesellschaft (Eigentümerstrategie), in denen auch "
            "der öffentliche Auftrag messbar benannt sein soll. Grundlegende "
            "Eigentümerentscheidungen — Gesellschaftszweck, Rechtsform, Auflösung — "
            "bleiben dem Rat vorbehalten; Rechte von Mitgesellschaftern sind dabei zu "
            "beachten."),
        pages="S. 14–16"),
    Rule(
        key="scope",
        title="Für wen das Handbuch gilt",
        trigger=_re(r"handbuch beteiligung|corporate governance|governance kodex|\bocgk\b|"
                    r"entsprechenserklaerung|comply or explain"),
        trigger_with_company=_re(r"welche\w* regeln|regeln (?:fuer|gelten)|"
                                 r"(?:fuer|bei) welche\w* [^?!.]{0,30}gilt|\bkodex\b"),
        text=(
            "Verbindlich ist das Handbuch für die Unternehmen, an denen die Stadt mit "
            "mehr als 50 Prozent beteiligt ist; seine Regeln sollen dort in den "
            "Gesellschaftsvertrag aufgenommen werden, soweit Rechte Dritter, etwa von "
            "Mitgesellschaftern, nicht entgegenstehen. Bei 50 Prozent oder weniger und "
            "bei Tochterunternehmen städtischer Beteiligungen soll es sinngemäß "
            "angewendet werden. Es ist auf die GmbH zugeschnitten und gilt für andere "
            "Rechtsformen sinngemäß. Was mit „soll“ formuliert ist, ist eine Vorgabe: "
            "Abweichungen muss das Unternehmen jedes Jahr im Bericht zur "
            "Unternehmensführung begründen (Entsprechenserklärung). „Kann“ ist eine "
            "Empfehlung."),
        pages="S. 10, 13, 27"),
)


def fold(text: str) -> str:
    """Dieselbe Faltung wie die Geld-Facetten (``geld.falte``)."""
    return geld.falte(text)


#: „Beteiligung" heißt im Ratskontext meist etwas anderes: die Beteiligung der
#: Öffentlichkeit an einem Plan. Die Erkennung der Facette ``companies`` lässt
#: „Beteiligung der Öffentlichkeit" durch (nur das Kompositum
#: „Öffentlichkeitsbeteiligung" steht in ihrer Sperrliste) — und dann zöge
#: „öffentlich" hier die Regel „Was öffentlich ist" in eine Frage zum
#: Bebauungsplan.
_KEINE_GESELLSCHAFT = re.compile(
    r"beteiligung (?:der|von|fuer) (?:oeffentlichkeit|buerger|einwohner|kinder|jugend|"
    r"traeger)|bauleitplan|bebauungsplan|flaechennutzungsplan|planungsverfahren")


def _meint_gesellschaft(t: str) -> bool:
    return companies.recognize(t, "", set()) and not _KEINE_GESELLSCHAFT.search(t)


def find(question: str, max_n: int = MAX_RULES) -> list[Rule]:
    """Die Regeln, die diese FRAGE zieht — in der Vorrang-Reihenfolge oben."""
    t = fold(question)
    if not t:
        return []
    mit_gesellschaft = _meint_gesellschaft(t)
    treffer = [r for r in RULES
               if (r.trigger is not None and r.trigger.search(t))
               or (mit_gesellschaft and r.trigger_with_company is not None
                   and r.trigger_with_company.search(t))]
    return treffer[:max_n]


def source() -> dict:
    """Der Beleg — die Broschüre, mit Ratsbeschluss und Stand."""
    return {"label": f"{SHORT_TITLE} der Stadt Oldenburg",
            "citation": f"Ratsbeschluss {ADOPTED_TEMPLATE} vom 27.11.2023",
            "as_of": VERSION, "url": SOURCE_URL}


def context(question: str) -> dict | None:
    """Die Daten der Facette: ausgewählte Regeln und ihr Beleg."""
    rules = find(question)
    if not rules:
        return None
    return {"rules": [{"key": r.key, "title": r.title, "text": r.text, "pages": r.pages}
                      for r in rules],
            "beleg": source()}


def block(data: dict | None) -> str:
    """Der Prompt-Baustein: die Regeln mit Seite — und was sie NICHT sagen."""
    if not data or not data.get("rules"):
        return ""
    zeilen = "\n".join(f"- {r['title']} ({r['pages']}): {r['text']}" for r in data["rules"])
    return (f"\nHANDBUCH BETEILIGUNGEN DER STADT OLDENBURG (vom Rat am 27.11.2023 "
            f"beschlossen, Stand {VERSION}) — Regeln, die sich die Stadt für ihre "
            "Unternehmen gegeben hat.\nBeantworte Fragen dazu, wie die Stadt ihre "
            "Gesellschaften steuert, daraus: in eigenen, kurzen Worten, mit der Seite "
            "in Klammern („so steht es im Handbuch Beteiligungen, S. 22“). Gib nur "
            "wieder, was hier steht. Es sind Vorgaben, keine Prüfergebnisse: Ob eine "
            "Gesellschaft sie einhält, steht hier nicht — schließe nichts darüber und "
            "unterstelle niemandem einen Verstoß. Nie mit [id] zitieren"
            + geld.beleg_text(data.get("beleg")) + ":\n" + zeilen + "\n")


# ---- Ratsperiode: Wann eine Besetzung aus dem Bericht veraltet ist ----------

def council_term(d: date) -> tuple[date, date]:
    """Die Wahlperiode des Rates, in die ``d`` fällt.

    In Niedersachsen beginnt sie am 1. November nach der Kommunalwahl und
    dauert fünf Jahre (§ 47 NKomVG); in Oldenburg lief eine vom 01.11.2021 bis
    31.10.2026, die nächste seit 01.11.2026."""
    jahr = d.year if (d.month, d.day) >= (11, 1) else d.year - 1
    beginn = jahr - ((jahr - 2016) % 5)
    return date(beginn, 11, 1), date(beginn + 5, 10, 31)


def board_term_note(report_year: int, today: date | None = None) -> dict:
    """Aus welcher Ratsperiode die Besetzung im Bericht stammt — und ob sie
    seither abgelaufen ist.

    Der Beteiligungsbericht nennt die Gremien im BERICHTSJAHR. Die städtischen
    Sitze im Aufsichtsrat enden mit der Ratsperiode (Handbuch S. 22), und der
    Rat besetzt sie für jede Periode neu. Am 23.11.2026 zeigte der Steckbrief
    die Besetzung von 2024 ohne Hinweis — samt einem Oberbürgermeister im
    Vorsitz, der seit 01.11.2026 nicht mehr im Amt ist.
    """
    today = today or date.today()
    beginn, ende = council_term(date(report_year, 12, 31))
    return {"term_start": beginn.isoformat(), "term_end": ende.isoformat(),
            "term_label": f"{beginn.year}–{ende.year}",
            "term_ended": today > ende}
