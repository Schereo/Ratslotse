"""Belege aus Oldenburg für ein Urteil über eine fremde Vorlage.

**Warum es diese Datei gibt.** Der Annotator ``fit`` beantwortet zwei Fragen:
„Hat Oldenburg genau dieses Instrument schon?" und „Lohnt ein Antrag?". Ein
Sprachmodell kann beides nur beantworten, wenn es weiß, was Oldenburg hat —
und es darf es nur beantworten, wenn es das an etwas festmacht. Deshalb geht
kein Urteil ohne Belege ins Modell und keins ohne Beleg-Kennung wieder heraus
(``council/cities/annotate.py`` verwirft erfundene Kennungen).

Das ist dieselbe Regel, die für Schicht 1 gilt („trägt keine Meinung"), eine
Ebene weiter gedacht: Eine Meinung darf gespeichert werden, aber nur mit
ihrer Grundlage daneben.

**Drei Quellen, in dieser Reihenfolge.** Die Nachbarschaft findet, was
inhaltlich nah liegt, auch wenn es anders heißt; die Volltextsuche findet,
was genau so heißt, auch wenn der Vektor es verfehlt (im Probelauf trug sie
den Befund „Zweckentfremdungssatzung: bisher nur politische Anträge, keine
Verabschiedung"); der Themenfeld-Rückblick sagt, was Oldenburg in dem Feld
gerade überhaupt beschäftigt.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from council.cities.store import CitiesStore

if TYPE_CHECKING:                       # nur für Typen — `council/` kennt den
    from council.store import CouncilStore   # Rats-Store zur Laufzeit lazy

#: Wie viele Nachbarn und Volltexttreffer je Papier höchstens mitgehen. Mehr
#: kostet Eingabe-Token, ohne das Urteil zu verbessern: Was auf Rang sechs
#: steht, hat mit der Sache meist nichts mehr zu tun.
MAX_NEIGHBORS = 5
MAX_FTS = 3

#: Unterhalb dieser Nähe ist ein Nachbar kein Beleg. Derselbe Wert wie in der
#: Anzeige, und aus demselben Grund: Der Median der Ähnlichkeit zweier
#: beliebiger deutscher Verwaltungstexte liegt bei 0,70 (gemessen). Was
#: darunter liegt, belegt nichts — es sieht nur so aus, weil es auf einer
#: Liste steht.
MIN_NEIGHBOR_SCORE = 0.70

EvidenceKind = Literal["neighbor", "fts", "recap"]

#: Was ein Modell über Oldenburg wissen muss, um „lohnt ein Antrag?" zu
#: beantworten. Ohne das hält es jede fremde Idee für übertragbar — und
#: schlägt Dinge vor, die dem Land, dem Landkreis oder einem Versorger
#: gehören.
#:
#: **Jede Zeile ist aus dem Bestand abgeleitet, nicht aus dem Gedächtnis:**
#: die Ausschüsse aus ``council_sessions`` (nach Sitzungszahl), die
#: Fraktionen aus ``council_decisions.factions``, die Eigenbetriebe und
#: Beteiligungen aus den Vorlagentiteln, die Zahl der Ortsbereiche aus
#: ``council_location_districts``. Die beiden Zeilen zu Rechtsrahmen und
#: Größe sind allgemein bekannt und von Tim gegengelesen (08.09.2026).
#:
#: **Wer ihn ändert, ändert jedes Urteil.** Der Steckbrief geht in den
#: System-Prompt von ``fit``; eine neue Zeile heißt neuer ``source_hash``
#: heißt: Der nächste Lauf urteilt alles neu. Das ist so gewollt, kostet aber
#: den vollen Preis (rund 5 $ über den Bestand).
OLDENBURG_STECKBRIEF = """Oldenburg (Oldb) ist eine kreisfreie Stadt in Niedersachsen mit rund 170.000 Einwohnern.

Rechtsrahmen: Niedersächsisches Kommunalverfassungsgesetz (NKomVG). Als kreisfreie Stadt nimmt sie auch die Aufgaben eines Landkreises wahr — anders als kreisangehörige Städte.

Der Rat tagt neben dem Verwaltungsausschuss in diesen Fachausschüssen: Finanzen und Beteiligungen, Stadtplanung und Bauen, Verkehr, Stadtgrün/Umwelt/Klima, Sport, Kultur, Soziales, Schule, Jugendhilfe, Integration und Migration, Wirtschaftsförderung/Digitalisierung/internationale Zusammenarbeit, Bahnangelegenheiten. Dazu die Betriebsausschüsse für den Eigenbetrieb Gebäudewirtschaft und Hochbau und für den Abfallwirtschaftsbetrieb.

Fraktionen und Gruppen im Rat (nach Zahl der eingebrachten Anträge): Bündnis 90/Die Grünen, SPD, CDU, BSW, FDP bzw. FDP/Volt, Gruppe DIE LINKE./Piratenpartei, Fossil Free, Für Oldenburg, WFO-LKR.

Eigenbetriebe der Stadt: Gebäudewirtschaft und Hochbau, Hafen, Abfallwirtschaftsbetrieb.

Nicht die Stadt selbst, sondern eigene Gesellschaften oder Dritte: Stadtwerke Oldenburg und EWE (Energie), Oldenburgisch-Ostfriesischer Wasserverband OOWV (Wasser), VWG (Nahverkehr), GSG Oldenburg (Wohnungsbau), Klinikum Oldenburg (Krankenhaus), Ems-Halle und Stadion Oldenburg GmbH (Sportstätten), Oldenburg Marketing und Tourismus GmbH. Der Rat kann diese Gesellschaften über seine Vertreter in Aufsichtsräten steuern, aber nicht unmittelbar beschließen, was dort geschieht.

Nicht kommunal: Schulrecht und Lehrpersonal, Polizei, Justiz, Steuerrecht, Sozialgesetzgebung, Fernstraßen und Schiene — das sind Land oder Bund. Die Stadt kann dazu Resolutionen fassen und sich an Land und Bund wenden, aber nichts anordnen.

Das Stadtgebiet gliedert sich in 31 statistische Bezirke und Stadtteile. Oldenburg ist Universitätsstadt (Carl von Ossietzky Universität, Jade Hochschule) und hat einen für deutsche Städte hohen Radverkehrsanteil."""

#: Was ein Modell über Oldenburg wissen muss, um „lohnt ein Antrag?" zu
#: beantworten. Ohne das hält es jede fremde Idee für übertragbar — und
#: schlägt Dinge vor, die dem Land, dem Landkreis oder einem Versorger
#: gehören.
#:
#: **Jede Zeile ist aus dem Bestand abgeleitet, nicht aus dem Gedächtnis:**
#: die Ausschüsse aus ``council_sessions`` (nach Sitzungszahl), die
#: Fraktionen aus ``council_decisions.factions``, die Eigenbetriebe und
#: Beteiligungen aus den Vorlagentiteln, die Zahl der Ortsbereiche aus
#: ``council_location_districts``. Die beiden Zeilen zu Rechtsrahmen und
#: Größe sind allgemein bekannt und von Tim gegengelesen (08.09.2026).
#:
#: **Wer ihn ändert, ändert jedes Urteil.** Der Steckbrief geht in den
#: System-Prompt von ``fit``; eine neue Zeile heißt neuer ``source_hash``
#: heißt: Der nächste Lauf urteilt alles neu. Das ist so gewollt, kostet aber
#: den vollen Preis (rund 5 $ über den Bestand).
OLDENBURG_STECKBRIEF = """Oldenburg (Oldb) ist eine kreisfreie Stadt in Niedersachsen mit rund 170.000 Einwohnern.

Rechtsrahmen: Niedersächsisches Kommunalverfassungsgesetz (NKomVG). Als kreisfreie Stadt nimmt sie auch die Aufgaben eines Landkreises wahr — anders als kreisangehörige Städte.

Der Rat tagt neben dem Verwaltungsausschuss in diesen Fachausschüssen: Finanzen und Beteiligungen, Stadtplanung und Bauen, Verkehr, Stadtgrün/Umwelt/Klima, Sport, Kultur, Soziales, Schule, Jugendhilfe, Integration und Migration, Wirtschaftsförderung/Digitalisierung/internationale Zusammenarbeit, Bahnangelegenheiten. Dazu die Betriebsausschüsse für den Eigenbetrieb Gebäudewirtschaft und Hochbau und für den Abfallwirtschaftsbetrieb.

Fraktionen und Gruppen im Rat (nach Zahl der eingebrachten Anträge): Bündnis 90/Die Grünen, SPD, CDU, BSW, FDP bzw. FDP/Volt, Gruppe DIE LINKE./Piratenpartei, Fossil Free, Für Oldenburg, WFO-LKR.

Eigenbetriebe der Stadt: Gebäudewirtschaft und Hochbau, Hafen, Abfallwirtschaftsbetrieb.

Nicht die Stadt selbst, sondern eigene Gesellschaften oder Dritte: Stadtwerke Oldenburg und EWE (Energie), Oldenburgisch-Ostfriesischer Wasserverband OOWV (Wasser), VWG (Nahverkehr), GSG Oldenburg (Wohnungsbau), Klinikum Oldenburg (Krankenhaus), Ems-Halle und Stadion Oldenburg GmbH (Sportstätten), Oldenburg Marketing und Tourismus GmbH. Der Rat kann diese Gesellschaften über seine Vertreter in Aufsichtsräten steuern, aber nicht unmittelbar beschließen, was dort geschieht.

Nicht kommunal: Schulrecht und Lehrpersonal, Polizei, Justiz, Steuerrecht, Sozialgesetzgebung, Fernstraßen und Schiene — das sind Land oder Bund. Die Stadt kann dazu Resolutionen fassen und sich an Land und Bund wenden, aber nichts anordnen.

Das Stadtgebiet gliedert sich in 31 statistische Bezirke und Stadtteile. Oldenburg ist Universitätsstadt (Carl von Ossietzky Universität, Jade Hochschule) und hat einen für deutsche Städte hohen Radverkehrsanteil."""


@dataclass(frozen=True)
class Evidence:
    """Ein Beleg aus Oldenburg, so wie er ins Modell geht und zurückkommt.

    ``id`` ist die Kennung, die das Modell zitieren muss: die Papier-Id aus
    dem Städte-Speicher (``oldenburg:paper:<kvonr>``) oder ``recap:<feld>``.
    Sie ist damit auch der Schlüssel, unter dem eine Oberfläche den Beleg
    später wieder auflöst.
    """
    kind: EvidenceKind
    id: str
    title: str
    date: str | None = None
    outcome: str | None = None
    text: str = ""
    score: float | None = None

    def as_prompt_line(self) -> str:
        """Wie der Beleg im Prompt steht.

        **Keine Positionsnummer.** Die erste Fassung nummerierte die Belege
        („[1] oldenburg:paper:4711: …"), und der Eval zeigte sofort, was das
        anrichtet: Das Modell zitierte in elf von vierzig Fällen die Nummer
        statt der Kennung. Jede dieser Antworten wäre im Betrieb verworfen
        worden — nicht weil das Urteil falsch war, sondern weil das Format
        zwei Griffe anbot und den falschen naheliegender machte.
        """
        teile = [t for t in (self.date, self.outcome) if t]
        kopf = self.id + (f" ({' · '.join(teile)})" if teile else "")
        zeilen = [f"- {kopf}: {self.title}"]
        if self.text:
            zeilen.append(f"    {self.text}")
        return "\n".join(zeilen)


def kvonr_aus(paper_id: str) -> int | None:
    """``oldenburg:paper:28119`` → ``28119``; alles andere → ``None``.

    Anträge aus Anlagen heißen ``oldenburg:paper:att:<document_id>`` und
    tragen keine Vorlagen-Id — für sie gibt es in der Rats-Datenbank keinen
    Beschluss zum Nachschlagen, ihr Titel muss als Beleg genügen.
    """
    teile = (paper_id or "").split(":")
    if len(teile) == 3 and teile[0] == "oldenburg" and teile[2].isdigit():
        return int(teile[2])
    return None


def _kurz(text: str | None, n: int = 500) -> str:
    sauber = " ".join((text or "").split())
    return sauber[:n]


def evidence_for(main: CitiesStore, rats: CouncilStore, paper: dict,
                 classification: dict, model: str,
                 k_neighbors: int = MAX_NEIGHBORS, k_fts: int = MAX_FTS,
                 min_score: float = MIN_NEIGHBOR_SCORE) -> list[Evidence]:
    """Was Oldenburg zu dieser fremden Vorlage hat — als Liste von Belegen.

    Dedupliziert nach ``id``; die Reihenfolge ist die Rangfolge, in der das
    Modell sie sieht (Nachbarn, dann Volltext, dann Rückblick).

    **Die Nachbarschaftstabelle ist gerichtet.** Für ein fremdes Papier sind
    Oldenburgs Papiere die „anderen Städte" — die Kanten, die der Index
    stadtübergreifend anlegt, zeigen also genau dorthin. Ein Filter auf
    ``oldenburg`` ist trotzdem nötig: Eine Braunschweiger Vorlage hat auch
    Osnabrücker Nachbarn, und die belegen nichts über Oldenburg.
    """
    belege: list[Evidence] = []
    gesehen: set[str] = set()

    def dazu(e: Evidence) -> None:
        if e.id not in gesehen:
            gesehen.add(e.id)
            belege.append(e)

    # 1. Die nächsten Oldenburger Papiere.
    for n in main.neighbors("paper", paper["id"], model, limit=k_neighbors * 4):
        if n.get("body_id") != "oldenburg" or float(n["score"]) < min_score:
            continue
        dazu(_aus_papier(rats, n["b_id"], n.get("name") or "", n.get("date"),
                         "neighbor", float(n["score"])))
        if sum(1 for e in belege if e.kind == "neighbor") >= k_neighbors:
            break

    # 2. Volltextsuche nach dem Instrument. Es ist die Kurzform der Idee,
    #    ohne Ortsnamen — genau das, was in einem Oldenburger Titel stünde.
    instrument = (classification.get("instrument") or "").strip()
    if instrument:
        for t in fts_treffer(main, instrument, k_fts * 3):
            dazu(_aus_papier(rats, t["paper_id"], t.get("name") or "", t.get("date"),
                             "fts", None))
            if sum(1 for e in belege if e.kind == "fts") >= k_fts:
                break

    # 3. Der Themenfeld-Rückblick — Kontext, kein Beleg im engeren Sinn.
    feld = (classification.get("field") or "").strip()
    if feld:
        rueckblick = rats.field_recaps_by_key().get(feld)
        if rueckblick and rueckblick.get("summary"):
            dazu(Evidence(kind="recap", id=f"recap:{feld}",
                          title=f"Was Oldenburg im Themenfeld {feld} beschäftigt",
                          text=_kurz(rueckblick["summary"])))
    return belege


def _woerter(instrument: str) -> list[str]:
    """Die tragenden Wörter eines Instruments, längste zuerst.

    Ein roher Satz mit Bindestrichen oder Klammern ist für FTS5 Syntax und
    wirft; ``fts_search`` fängt das ab und liefert nichts — was aussieht wie
    „Oldenburg hat dazu nichts". Deshalb hier zerlegen, nicht dort.

    Nach Länge sortiert, weil im Deutschen das lange Wort das spezifische ist:
    „Qualitätshandbuch" trennt, „einführen" nicht.
    """
    roh = [w.strip('"„“()[],.;:').strip() for w in
           instrument.replace("-", " ").replace("/", " ").split()]
    return sorted({w for w in roh if len(w) > 4}, key=len, reverse=True)[:8]


def fts_treffer(main: CitiesStore, instrument: str, limit: int) -> list[dict]:
    """Oldenburger Papiere zum Instrument — von streng nach nachsichtig.

    **Warum nicht einfach ODER.** Eine reine ODER-Anfrage findet jedes Papier,
    das EIN Wort teilt, und bm25 ordnet die dann nach Häufigkeit. Gemessen an
    einer Stichprobe von Kandidaten für das Golden Set kam dabei unter
    „Qualitätshandbuch und Fallanalysen für ASD einführen" die Oldenburger
    Vorlage „Warnung und Information der Bevölkerung" als Beleg heraus — sie
    teilt das Wort „einführen" und sonst nichts. Solche Belege kosten nicht nur
    Token, sie laden das Modell ein, „vorhanden" zu sagen, wo nichts ist.

    Deshalb drei Stufen: erst alle tragenden Wörter zusammen, dann die zwei
    spezifischsten, erst zuletzt das lose ODER. Die erste Stufe, die etwas
    findet, gewinnt — und was sie findet, teilt mehr als ein Allerweltswort.
    """
    woerter = _woerter(instrument)
    if not woerter:
        return []
    stufen = [" AND ".join(f'"{w}"' for w in woerter)]
    if len(woerter) > 2:
        stufen.append(" AND ".join(f'"{w}"' for w in woerter[:2]))
    stufen.append(" OR ".join(f'"{w}"' for w in woerter[:4]))
    for anfrage in stufen:
        treffer = main.fts_search(anfrage, body_id="oldenburg", limit=limit)
        if treffer:
            return treffer
    return []


def _aus_papier(rats: CouncilStore, paper_id: str, name: str, date: str | None,
                kind: EvidenceKind, score: float | None) -> Evidence:
    """Einen Oldenburger Beleg mit dem anreichern, was die Rats-Datenbank weiß.

    Zusammenfassung und Ergebnis stehen dort, nicht im Städte-Speicher: Der
    Oldenburg-Adapter trägt bewusst nur, was ein OParl-Objekt hergibt.

    Bewusst über zwei vorhandene Store-Methoden statt einer neuen: Der Weg
    Vorlage → Stationen → Beschluss ist getestet, und `CouncilStore` steht
    unter einer Sperrklinke für die Zahl seiner Methoden
    (`tests/test_store_groesse.py`). Zwei Abfragen je Beleg fallen nicht ins
    Gewicht — das hier ist ein Wochen-Cron, kein Request.
    """
    kvonr = kvonr_aus(paper_id)
    text, outcome, datum = "", None, date
    if kvonr is not None:
        stationen = rats.neueste_stationen_fuer([kvonr], [])
        # Die jüngste Station zuerst: Sie trägt das Ergebnis, das gilt.
        for station in sorted(stationen, key=lambda s: s.get("session_date") or "",
                              reverse=True):
            beschluss = rats.get_decision(station["id"])
            if not beschluss:
                continue
            outcome = outcome or beschluss.get("outcome")
            datum = datum or beschluss.get("session_date")
            text = _kurz(beschluss.get("simple_summary") or beschluss.get("summary")
                         or beschluss.get("official_text"))
            if text:
                break
        if not text:
            vorlage = rats.get_vorlage(kvonr)
            if vorlage:
                text = _kurz(vorlage.get("proposed_decision") or vorlage.get("raw_text"))
    return Evidence(kind=kind, id=paper_id, title=name, date=datum,
                    outcome=outcome, text=text, score=score)
