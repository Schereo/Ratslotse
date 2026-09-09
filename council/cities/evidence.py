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

import logging
import os
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Literal

from council.cities.store import CitiesStore
from kern import llm, prompts

if TYPE_CHECKING:                       # nur für Typen — `council/` kennt den
    from council.store import CouncilStore   # Rats-Store zur Laufzeit lazy

logger = logging.getLogger("council.cities.evidence")

#: Papier-Kennungen, Chunk-Nummern und die Vektoren am Stück — einmal je Lauf
#: geladen (``CitiesStore.chunk_matrix``), nicht je Vorlage.
ChunkMatrix = tuple[list[str], list[int], bytes]
#: Die Papier-Vektoren einer Stadt: Kennungen und Rohbytes.
PaperMatrix = tuple[list[str], bytes]

#: Das Modell für die Suchbegriffe. Dasselbe wie bei der Query-Expansion der
#: KI-Frage und aus demselben Grund: Die Aufgabe ist klein, die Antwort kurz,
#: und ein großes Modell kostet hier nur Zeit. Gemessen bei der KI-Frage:
#: 0,5 s statt 2–12 s.
TERMS_MODEL = os.environ.get("COUNCIL_QA_EXPAND_MODEL", "google/gemini-2.5-flash-lite")

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

EvidenceKind = Literal["cluster", "neighbor", "chunk", "fts", "decision", "recap"]

#: Wie die vier Arten im Prompt heißen. Deutsch, weil sie ein Modell liest,
#: das deutsche Verwaltungstexte beurteilt — und benannt, weil sie NICHT
#: gleich viel wert sind: Ein Beschluss trägt ein Abstimmungsergebnis, ein
#: Abschnitt ist eine Fundstelle aus einem Dokument, dessen Rest von etwas
#: anderem handeln kann.
ARTEN: dict[str, str] = {
    "cluster": "Oldenburgs Vorlage zur GLEICHEN Idee",
    "decision": "Beschluss",
    "neighbor": "Vorlage",
    "fts": "Vorlage",
    "chunk": "Fundstelle in einer Vorlage",
    "recap": "Rückblick aufs Themenfeld",
}

#: Wie viele Belege insgesamt ins Modell gehen. Vorher waren es 5 Nachbarn
#: plus 3 Volltexttreffer aus zwei getrennten Töpfen; jetzt ordnet die Fusion,
#: nicht die Quelle — ein Papier, das zwei Arme finden, gehört nach oben.
#:
#: **Zwanzig, seit alle fünf Arme wirklich liefern.** Zwölf reichten, solange
#: die Hälfte der Arme leer lief: Vor dem Index über den ganzen Bestand
#: (09.09.2026) hatten nur 3.000 der 24.728 fremden Vorlagen einen Vektor,
#: Cluster- und Nachbar-Arm fielen also meistens aus. Danach konkurrieren bis
#: zu sechzig Kandidaten um die Plätze — und der richtige Beleg wurde
#: HINAUSGEDRÄNGT, nicht etwa nicht gefunden. Im schärfsten gemessenen Fall
#: stand er auf **Rang 4 von 5.945** und stand trotzdem nicht auf der Liste.
#:
#: Gemessen gegen die 23 Handfälle mit Beleg, alle fünf Arme aktiv:
#:
#: | Plätze | erwarteter Beleg in der Liste |
#: |---|---|
#: | 12 | 18/23 |
#: | 16 | 21/23 |
#: | **20** | **22/23** |
#: | 24 | 22/23 |
#:
#: Bei 24 kommt nichts mehr dazu. Jeder Platz kostet rund 250 Eingabe-Token je
#: Urteil, acht Plätze also gut ein Drittel mehr — den Preis ist es wert, denn
#: was das Modell nie sieht, kann es nicht zitieren.
#:
#: Die vier neu gewonnenen Fälle stehen auf den Rängen 14, 15, 16 und 19; die
#: Reihenfolge der übrigen ändert sich NICHT (die Fusion ordnet unabhängig von
#: der Listenlänge, diese schneidet nur ab). Der Median bleibt deshalb bei 1.
MAX_EVIDENCE = 20

#: Wie viele Kandidaten jeder Arm liefert, bevor fusioniert wird.
POOL_JE_ARM = 12

#: Unterhalb dieser Nähe ist ein CHUNK kein Beleg — **gemessen**, nicht
#: geschätzt (``eval/run_cities_evidence.py --chunk-schwelle 0.55 0.62 0.70 0.78``):
#:
#: | Schwelle | Beleg gefunden | mittlerer Rang | zwei Arme einig (vorh./fehlt) |
#: |---|---|---|---|
#: | 0,55 | 23/23 | 2,04 | 92 % / 24 % |
#: | 0,62 | 23/23 | 2,04 | 92 % / 18 % |
#: | **0,70** | **23/23** | **1,87** | **92 % / 6 %** |
#: | 0,78 | 23/23 | 1,91 | 75 % / 6 % |
#:
#: Die Erwartung war, ein kurzer Abschnitt brauche eine NIEDRIGERE Schwelle als
#: zwei ganze Vorlagen. Sie war falsch: Derselbe Wert 0,70 trennt am schärfsten,
#: und darunter kommt nur Rauschen dazu, das die Einigkeit der Arme verwässert.
MIN_CHUNK_SCORE = 0.70

#: Reciprocal Rank Fusion — dieselbe Konstante wie in `store.py`, und aus
#: demselben Grund: Vier Arme liefern unvergleichbare Werte (Kosinus, bm25,
#: nichts), aber jeder liefert eine RANGFOLGE. Die lässt sich addieren.
RRF_K = 60

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
    #: Wie viele der vier Suchwege dieses Papier gefunden haben.
    #:
    #: **Das trennt schärfer als jeder Einzelwert.** Gemessen über die vierzig
    #: Prüffälle (08.09.2026): Wo Oldenburg das Instrument HAT, findet in 92 %
    #: der Fälle mindestens ein Papier den Weg über zwei oder mehr Arme; wo es
    #: fehlt, nur in 18 %. Nachbarschaft, Textabschnitt, Volltext und
    #: Beschluss irren auf verschiedene Weise — dass sie sich einig sind, ist
    #: deshalb eine Aussage, die kein einzelner Wert trifft.
    arme: int = 1

    def as_prompt_line(self) -> str:
        """Wie der Beleg im Prompt steht.

        **Keine Positionsnummer.** Die erste Fassung nummerierte die Belege
        („[1] oldenburg:paper:4711: …"), und der Eval zeigte sofort, was das
        anrichtet: Das Modell zitierte in elf von vierzig Fällen die Nummer
        statt der Kennung. Jede dieser Antworten wäre im Betrieb verworfen
        worden — nicht weil das Urteil falsch war, sondern weil das Format
        zwei Griffe anbot und den falschen naheliegender machte.
        """
        teile = [ARTEN[self.kind]]
        teile += [t for t in (self.date, self.outcome) if t]
        if self.arme > 1:
            teile.append(f"von {self.arme} Suchwegen gefunden")
        zeilen = [f"- {self.id} ({' · '.join(teile)}): {self.title}"]
        if self.text:
            zeilen.append(f"    {self.text}")
        return "\n".join(zeilen)


def kvonr_aus(paper_id: str) -> int | None:
    """``oldenburg:paper:28119`` → ``28119``; alles andere → ``None``.

    Anträge aus Anlagen heißen ``oldenburg:paper:att:<document_id>`` und
    tragen keine Vorlagen-Id — für sie gibt es in der Rats-Datenbank keinen
    Beschluss zum Nachschlagen, ihr Titel muss als Beleg genügen.

    **Die mittlere Stufe muss ``paper`` heißen.** Seit es Beschluss-Belege
    gibt (``oldenburg:decision:8525``), passt die bloße Form „drei Teile, das
    letzte eine Zahl" auf zwei verschiedene Räume — und eine Beschluss-Id als
    Vorlagennummer nachzuschlagen liefert eine fremde Vorlage oder nichts.
    """
    teile = (paper_id or "").split(":")
    if (len(teile) == 3 and teile[0] == "oldenburg" and teile[1] == "paper"
            and teile[2].isdigit()):
        return int(teile[2])
    return None


def _kurz(text: str | None, n: int = 500) -> str:
    sauber = " ".join((text or "").split())
    return sauber[:n]


def _kurz_ganzwortig(text: str | None, n: int = 500) -> str:
    """Wie ``_kurz``, aber ohne angeschnittenes erstes und letztes Wort.

    Chunks sind nach Zeichen geschnitten, nicht nach Sätzen — ein Beleg fing
    deshalb schon mal mit „en Nutzerinnen und Nutzer …" an. Für ein Modell ist
    das kein Fehler, aber es kostet Aufmerksamkeit an einer Stelle, an der sie
    dem Urteil fehlt.
    """
    sauber = " ".join((text or "").split())
    if not sauber:
        return ""
    # Vorn: ein angeschnittenes Wort wegwerfen, wenn es klein anfängt und kein
    # Satzanfang ist. Hinten: am letzten Leerzeichen abschneiden.
    kopf, _, rest = sauber.partition(" ")
    if rest and kopf[:1].islower() and len(kopf) < 12:
        sauber = rest
    if len(sauber) <= n:
        return sauber
    gekuerzt = sauber[:n]
    letzte = gekuerzt.rfind(" ")
    return (gekuerzt[:letzte] if letzte > n // 2 else gekuerzt) + " …"


def search_terms(classification: dict, paper: dict) -> list[str]:
    """Die Wörter, unter denen OLDENBURG dieselbe Sache führen würde.

    **Warum ein Modell und nicht die Wörter des Instruments.** Das Instrument
    ist die Sprache der fremden Stadt. „Außengastronomieflächen kontrollieren"
    steht in Oldenburg unter „Sondernutzungssatzung", „Lernbegleiter:innen"
    unter „Schulbegleitung". Wer wörtlich sucht, findet die Vorlage nicht, die
    da ist — und das Modell urteilt dann „fehlt" über etwas, das Oldenburg hat.
    Dieselbe Einsicht wie bei der KI-Frage (``council/qa.py::expand_query``),
    nur in die andere Richtung: dort Frage → Verwaltungsdeutsch, hier fremdes
    Verwaltungsdeutsch → Oldenburger Verwaltungsdeutsch.

    Fällt der Aufruf aus, bleiben die tragenden Wörter des Instruments — das
    ist der Stand vor diesem Ausbau und schlechter, aber nie schlechter als
    nichts.
    """
    instrument = (classification.get("instrument") or "").strip()
    if not instrument:
        return []
    try:
        antwort = llm.chat_complete(
            model=TERMS_MODEL, temperature=0, max_tokens=80, timeout=20.0,
            _feature="cities_evidence_terms",
            messages=[{"role": "user", "content": prompts.render(
                "cities_evidence_terms", instrument=instrument,
                summary=_kurz(classification.get("summary"), 300),
                title=_kurz(paper.get("name"), 200))}])
        begriffe = [w.strip('"„“(),.;:') for w in
                    (antwort.choices[0].message.content or "").split()]
        gefunden = [w for w in begriffe if len(w) > 3][:8]
        if gefunden:
            return gefunden
    except Exception as e:  # noqa: BLE001 — eine Vorlage, nicht der Lauf
        logger.info("Suchbegriffe gescheitert (%s): %s", paper.get("id"),
                    type(e).__name__)
    return _woerter(instrument)


def _rrf(raenge: list[list[str]]) -> dict[str, float]:
    """Reciprocal Rank Fusion über mehrere Ranglisten von Kennungen."""
    punkte: dict[str, float] = {}
    for liste in raenge:
        for rang, kennung in enumerate(liste, 1):
            punkte[kennung] = punkte.get(kennung, 0.0) + 1.0 / (RRF_K + rang)
    return punkte


def evidence_for(main: CitiesStore, rats: CouncilStore, paper: dict,
                 classification: dict, model: str,
                 k: int = MAX_EVIDENCE,
                 min_score: float = MIN_NEIGHBOR_SCORE,
                 chunk_matrix: ChunkMatrix | None = None,
                 begriffe: list[str] | None = None,
                 paper_matrix: PaperMatrix | None = None) -> list[Evidence]:
    """Was Oldenburg zu dieser fremden Vorlage hat — als Liste von Belegen.

    **Vier Arme, weil jeder etwas findet, das die anderen verfehlen:**

    1. ``neighbor`` — das nächste ganze Oldenburger Papier. Findet, was
       inhaltlich verwandt ist, auch wenn es anders heißt.
    2. ``chunk`` — der nächste Textabschnitt. Findet die Sache, die in einer
       großen Vorlage auf Seite elf steht; der Vektor des ganzen Papiers
       verdünnt sie bis zur Unkenntlichkeit.
    3. ``fts`` — der wörtliche Treffer auf die Oldenburger Begriffe aus
       ``search_terms``. Findet, was genau so heißt, auch wenn kein Vektor
       hinzeigt.
    4. ``decision`` — Oldenburgs eigene BESCHLÜSSE aus der Rats-Datenbank.
       Der Städte-Speicher trägt für Oldenburg nur, was ein OParl-Objekt
       hergibt; das Ergebnis der Abstimmung, die Fraktionen und die
       Kurzfassung stehen nur dort. Für die Frage „hat Oldenburg das schon?"
       ist ein Beschluss mit Ergebnis der stärkste Beleg, den es gibt.

    Zusammengeführt wird per Reciprocal Rank Fusion: Die Arme liefern
    unvergleichbare Werte (Kosinus, bm25, keinen), aber jeder liefert eine
    Rangfolge. Ein Papier, das zwei Arme finden, steht deshalb oben — und das
    ist genau das Papier, das ein Mensch als Beleg genommen hätte.

    Der Themenfeld-Rückblick kommt als fünfte Zeile dazu. Er trägt kein
    Urteil (``fit.TRAGENDE_ARTEN``) und steht deshalb außerhalb der Fusion.

    ``chunk_matrix`` und ``begriffe`` reicht der Aufrufer durch, wenn er über
    viele Vorlagen läuft: Die Matrix einmal zu laden statt zehntausendmal
    spart Minuten, und wer die Begriffe schon hat, ruft das Modell nicht neu.
    """
    quellen: dict[str, list[str]] = {}
    # Kennung → (Art, Titel, Datum, Nähe, Chunk-Nummer). Der erste Arm, der ein
    # Papier findet, bestimmt seine Art — die Fusion ordnet danach nur noch.
    daten: dict[str, tuple] = {}

    # 0. Oldenburger Mitglieder DESSELBEN Ideen-Clusters. Der genaueste Arm:
    #    Hier hat nicht ein Ähnlichkeitsmaß entschieden, dass zwei Texte
    #    verwandt sind, sondern die Gruppierung, dass sie DIESELBE Idee sind.
    #    Steht deshalb vorn — und trägt seine Art im Prompt, damit das Modell
    #    ein schlechtes Mitglied verwerfen kann (an vierzehn gelesenen Clustern
    #    waren drei falsch, immer nach dem Muster „gleiches Feld, anderes
    #    Instrument").
    quellen["cluster"] = _cluster_treffer(main, paper, model, daten)

    # Der Vektor DIESER Vorlage — EINMAL, für die beiden Vektor-Arme. Es ist
    # derselbe Text, den `index.py` einbettet; zwei getrennte Aufrufe wären
    # zweimal dasselbe Ergebnis für den doppelten Preis. Träge, damit ein
    # Aufrufer ohne Matrizen (und ohne fastembed) gar nicht erst einbettet.
    if paper_matrix is None:
        paper_matrix = main.paper_matrix(model, "oldenburg")
    frage = _Vektor(main, paper, classification)

    # 1. Die nächsten Oldenburger Papiere.
    quellen["neighbor"] = _nachbar_treffer(frage, paper_matrix, min_score, daten)

    if begriffe is None:
        begriffe = search_terms(classification, paper)

    # 2. Die nächsten Oldenburger Textabschnitte.
    quellen["chunk"] = _chunk_treffer(frage, chunk_matrix, daten)

    # 3. Volltext auf die Oldenburger Begriffe.
    volltext: list[str] = []
    for t in fts_treffer(main, begriffe, POOL_JE_ARM):
        volltext.append(t["paper_id"])
        daten.setdefault(t["paper_id"], ("fts", t.get("name") or "", t.get("date"),
                                         None, None))
    quellen["fts"] = volltext

    # 4. Oldenburgs eigene Beschlüsse — mit Ergebnis, das der Speicher nicht hat.
    quellen["decision"] = _beschluss_treffer(rats, begriffe, daten)

    punkte = _rrf(list(quellen.values()))
    arme_je = {kennung: sum(1 for liste in quellen.values() if kennung in liste)
               for kennung in punkte}
    belege: list[Evidence] = []
    for kennung in sorted(punkte, key=lambda x: -punkte[x])[:k]:
        eintrag = daten[kennung]
        art, name, datum, score = eintrag[:4]
        chunk_idx = eintrag[4] if len(eintrag) > 4 else None
        beleg = _beleg_bauen(rats, main, kennung, art, name, datum, score, chunk_idx)
        belege.append(replace(beleg, arme=arme_je[kennung]))

    # 5. Der Themenfeld-Rückblick — Kontext, kein Beleg im engeren Sinn.
    feld = (classification.get("field") or "").strip()
    if feld:
        rueckblick = rats.field_recaps_by_key().get(feld)
        if rueckblick and rueckblick.get("summary"):
            belege.append(Evidence(
                kind="recap", id=f"recap:{feld}",
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


def fts_treffer(main: CitiesStore, begriffe: list[str], limit: int) -> list[dict]:
    """Oldenburger Papiere zu den Begriffen — von streng nach nachsichtig.

    **Warum nicht einfach ODER.** Eine reine ODER-Anfrage findet jedes Papier,
    das EIN Wort teilt, und bm25 ordnet die dann nach Häufigkeit. Gemessen an
    einer Stichprobe von Kandidaten für das Golden Set kam dabei unter
    „Qualitätshandbuch und Fallanalysen für ASD einführen" die Oldenburger
    Vorlage „Warnung und Information der Bevölkerung" als Beleg heraus — sie
    teilt das Wort „einführen" und sonst nichts. Solche Belege kosten nicht nur
    Token, sie laden das Modell ein, „vorhanden" zu sagen, wo nichts ist.

    Deshalb drei Stufen: erst alle Begriffe zusammen, dann die zwei
    spezifischsten, erst zuletzt das lose ODER. Die erste Stufe, die etwas
    findet, gewinnt — und was sie findet, teilt mehr als ein Allerweltswort.
    """
    woerter = [w for w in begriffe if len(w) > 3][:8]
    if not woerter:
        return []
    lang = sorted(woerter, key=len, reverse=True)
    stufen = [" AND ".join(f'"{w}"' for w in lang)]
    if len(lang) > 2:
        stufen.append(" AND ".join(f'"{w}"' for w in lang[:2]))
    stufen.append(" OR ".join(f'"{w}"' for w in lang[:4]))
    for anfrage in stufen:
        treffer = main.fts_search(anfrage, body_id="oldenburg", limit=limit)
        if treffer:
            return treffer
    return []


def _cluster_treffer(main: CitiesStore, paper: dict, model: str,
                     daten: dict) -> list[str]:
    """Oldenburger Papiere, die im selben Ideen-Cluster liegen.

    Nur Oldenburger: Dass Osnabrück und Münster dasselbe tun, ist für die
    Frage „hat OLDENBURG das schon?" keine Antwort — es steht als eigene
    Zeile im Prompt (``cluster_zeile``), nicht als Beleg.
    """
    from council.cities.clusters import CLUSTER_VERSION

    treffer: list[str] = []
    for m in main.cluster_of(paper["id"], model, CLUSTER_VERSION):
        if m["body_id"] != "oldenburg":
            continue
        treffer.append(m["id"])
        daten.setdefault(m["id"], ("cluster", m.get("name") or "", m.get("date"),
                                   float(m.get("score") or 0.0), None))
    return treffer[:POOL_JE_ARM]


def cluster_zeile(main: CitiesStore, paper: dict, model: str) -> str:
    """Was die Cluster über diese Idee sagen — zwei Sätze für den Prompt.

    **Das ist die Aussage, die kein Einzelurteil treffen kann.** „Fünf von
    sechs Städten haben das, Oldenburg nicht" wiegt anders als ein einzelner
    fremder Antrag. Und die Gegenrichtung wiegt genauso: Wenn in 5.945
    Oldenburger Vorlagen seit 2018 keine mit dieser Idee liegt, ist das ein
    Befund und keine Lücke in der Suche.

    Die fremden Mitglieder werden NAMENTLICH genannt, nicht gezählt: An
    vierzehn gelesenen Clustern waren drei falsch gruppiert, und ein Modell,
    das die Titel sieht, kann das erkennen — eine bloße Zahl kann es nicht.
    """
    from council.cities.clusters import CLUSTER_VERSION

    mitglieder = main.cluster_of(paper["id"], model, CLUSTER_VERSION)
    if not mitglieder:
        return ("Ideen-Cluster: keiner — keine andere Stadt im Bestand hat "
                "etwas hinreichend Ähnliches. Das sagt nichts über Oldenburg.")
    fremde = [m for m in mitglieder
              if m["body_id"] not in ("oldenburg", paper.get("body_id"))]
    hat_oldenburg = any(m["body_id"] == "oldenburg" for m in mitglieder)
    staedte = {m["body_id"] for m in mitglieder if m["body_id"] != "oldenburg"}

    zeilen = [f"Gleiche Idee in {len(staedte)} anderen Städten:"]
    for m in fremde[:5]:
        ergebnis = (main.outcome_for_paper(m["id"]) or {}).get("outcome") or "offen"
        zeilen.append(f"  - {m['body_id']} {(m.get('date') or '')[:7]} "
                      f"({ergebnis}): {(m.get('name') or '')[:90]}")
    if hat_oldenburg:
        zeilen.append("In Oldenburg liegt eine Vorlage im selben Cluster — sie steht "
                      "unter den Belegen als „Oldenburgs Vorlage zur GLEICHEN Idee“. "
                      "Prüfe sie: Die Gruppierung irrt in etwa jedem fünften Fall, "
                      "und dann betrifft sie dasselbe Themenfeld, aber ein anderes "
                      "Instrument.")
    else:
        zeilen.append("In Oldenburgs 5.945 Vorlagen seit 2018 liegt KEINE im selben "
                      "Cluster.")
    return "\n".join(zeilen)


class _Vektor:
    """Der Vektor dieser Vorlage, erst gerechnet, wenn ihn jemand braucht.

    Beide Vektor-Arme fragen ihn; ohne Matrix fragt ihn keiner. Ein Fehler
    (kein fastembed, kein Modell) wird EINMAL gemeldet und macht beide Arme
    leer, statt den Lauf zu kippen.
    """

    def __init__(self, main: CitiesStore, paper: dict, classification: dict):
        self._main, self._paper, self._klasse = main, paper, classification
        self._wert = None
        self._gerechnet = False

    def hol(self):
        if not self._gerechnet:
            self._gerechnet = True
            try:
                from council.cities.index import object_text
                self._wert = _embed_eins(object_text(
                    self._paper, self._klasse,
                    self._main.text_for_paper(self._paper["id"])))
            except Exception as e:  # noqa: BLE001 — ohne fastembed bleiben die Arme leer
                logger.info("Vektor-Arme übersprungen (%s)", type(e).__name__)
        return self._wert


def _nachbar_treffer(frage: _Vektor, matrix: PaperMatrix | None,
                     min_score: float, daten: dict) -> list[str]:
    """Die nächsten OLDENBURGER Vorlagen — gegen Oldenburgs Matrix gerechnet.

    **Warum nicht aus ``neighbors``.** Die Tabelle hält je Objekt die acht
    nächsten über ALLE Städte. Solange nur Oldenburg Vektoren hatte, war das
    dasselbe wie „die acht nächsten Oldenburger". Seit dem Index über den
    ganzen Bestand (09.09.2026) ist es das nicht mehr: Nur ein Viertel der
    gespeicherten Nachbarschaften zeigt noch auf Oldenburg, und für eine
    einzelne fremde Vorlage sind es oft null von acht. Der Arm fiel dadurch
    stumm aus — der Prüfstand fand statt 23 von 23 erwarteten Belegen nur
    noch 17, ohne dass irgendetwas rot wurde.

    Ein tieferes ``NEIGHBOR_TOP_K`` verschöbe das nur bis zur nächsten Stadt.
    Deshalb dieselbe Bauform wie beim Chunk-Arm: eine Matrix, einmal geladen.
    """
    if matrix is None:
        return []
    papiere, vektoren = matrix
    if not papiere:
        return []
    vektor = frage.hol()
    if vektor is None:
        return []
    import numpy as np

    matrix_np = np.frombuffer(vektoren, dtype=np.float32).reshape(len(papiere), -1)
    naehe = matrix_np @ vektor
    rang = sorted(range(len(papiere)), key=lambda i: -naehe[i])[:POOL_JE_ARM]
    treffer: list[str] = []
    for i in rang:
        wert = float(naehe[i])
        if wert < min_score:
            break
        treffer.append(papiere[i])
        daten.setdefault(papiere[i], ("neighbor", "", None, wert, None))
    return treffer


def _chunk_treffer(frage: _Vektor, matrix: ChunkMatrix | None,
                   daten: dict) -> list[str]:
    """Die nächsten Oldenburger TEXTABSCHNITTE, auf ihr Papier abgebildet.

    Der Vektor eines ganzen Papiers mittelt über alles, was darin steht: In
    einer 40-seitigen Vorlage verschwindet der eine Absatz, um den es geht.
    Der Städte-Speicher hat die Chunks längst (85.000 Vektoren), nur hat sie
    bisher niemand für die Belege gelesen.

    **Je Papier zählt der beste Chunk**, nicht ihre Summe — sonst gewönne die
    längste Vorlage, weil sie die meisten Abschnitte hat. Dieselbe Lehre wie
    beim Nachbar-Arm der freien Suche (``store.search_ideas``).
    """
    if matrix is None:
        return []
    papiere, indizes, vektoren = matrix
    if not papiere:
        return []
    vektor = frage.hol()
    if vektor is None:
        return []
    import numpy as np

    matrix_np = np.frombuffer(vektoren, dtype=np.float32).reshape(len(papiere), -1)
    naehe = matrix_np @ vektor

    bestes: dict[str, tuple[float, int]] = {}
    for i, kennung in enumerate(papiere):
        wert = float(naehe[i])
        if wert < MIN_CHUNK_SCORE:
            continue
        if kennung not in bestes or wert > bestes[kennung][0]:
            bestes[kennung] = (wert, indizes[i])
    rang = sorted(bestes, key=lambda k: -bestes[k][0])[:POOL_JE_ARM]
    for kennung in rang:
        wert, chunk_idx = bestes[kennung]
        # Die Nummer des Abschnitts wandert mit: Der Beleg soll die STELLE
        # zitieren, die getroffen hat, nicht den Anfang der Vorlage. Ein
        # Haushaltsplan fängt bei jedem Thema gleich an.
        daten.setdefault(kennung, ("chunk", "", None, wert, chunk_idx))
    return rang


def _beschluss_treffer(rats: CouncilStore, begriffe: list[str], daten: dict) -> list[str]:
    """Oldenburgs eigene Beschlüsse — die einzige Quelle mit Abstimmungsergebnis.

    Der Städte-Speicher trägt für Oldenburg nur, was ein OParl-Objekt hergibt.
    Ob der Rat zugestimmt hat, wer den Antrag gestellt hat und was am Ende
    beschlossen wurde, steht ausschließlich in der Rats-Datenbank. Für die
    Frage „hat Oldenburg das schon?" ist genau das der stärkste Beleg — ein
    Antrag ohne Beschluss beantwortet sie nicht.
    """
    if not begriffe:
        return []
    # `search_decisions_fts` verknüpft die Begriffe mit ODER — richtig für die
    # KI-Frage, wo ein Reranker folgt, falsch hier, wo keiner folgt. Ohne
    # Nachfilter war dieser Arm die größte Rauschquelle: Unter „Live-Video im
    # Notruf einführen" lieferte er sieben Oldenburger Beschlüsse, von denen
    # keiner mit einem Notruf zu tun hatte (gemessen 08.09.2026).
    #
    # Deshalb dieselbe Strenge wie in `fts_treffer`: Ein Treffer zählt nur,
    # wenn er eines der SPEZIFISCHEN Wörter trägt — das sind im Deutschen die
    # langen. „Qualitätshandbuch" trennt, „einführen" nicht.
    spezifisch = [w.lower() for w in sorted(begriffe, key=len, reverse=True)[:3]]
    treffer: list[str] = []
    for beschluss_id, _rang, _stelle in rats.search_decisions_fts(
            " ".join(begriffe), limit=POOL_JE_ARM * 4):
        b = rats.get_decision(beschluss_id) or {}
        heuhaufen = f"{b.get('title') or ''} {b.get('simple_summary') or ''}".lower()
        if not any(w in heuhaufen for w in spezifisch):
            continue
        kennung = f"oldenburg:decision:{beschluss_id}"
        treffer.append(kennung)
        daten.setdefault(kennung, ("decision", "", None, None, None))
        if len(treffer) >= POOL_JE_ARM:
            break
    return treffer


def _embed_eins(text: str):
    from council.embeddings import embed
    return embed([text])[0]


def _beleg_bauen(rats: CouncilStore, main: CitiesStore, kennung: str,
                 art: EvidenceKind, name: str, datum: str | None,
                 score: float | None, chunk_idx: int | None = None) -> Evidence:
    """Aus einer Kennung den fertigen Beleg — je nach Quelle anders."""
    if kennung.startswith("oldenburg:decision:"):
        return _aus_beschluss(rats, kennung, score)
    beleg = _aus_papier(rats, kennung, name, datum, art, score)
    if not beleg.title:
        papier = main.paper(kennung)
        beleg = replace(beleg, title=(papier or {}).get("name") or kennung)
    if art == "chunk" and chunk_idx is not None:
        # Der Abschnitt, der den Treffer ausgelöst hat, ist der Beleg — nicht
        # der Anfang der Vorlage. Ein Haushaltsplan fängt bei jedem Thema
        # gleich an; erst die Fundstelle sagt, worum es geht.
        stelle = main.chunk_text(kennung, chunk_idx)
        if stelle:
            beleg = replace(beleg, text=_kurz_ganzwortig(stelle))
    return beleg


def _aus_beschluss(rats: CouncilStore, kennung: str, score: float | None) -> Evidence:
    """Ein Oldenburger Beschluss als Beleg — mit Ergebnis und Gremium."""
    beschluss_id = int(kennung.rsplit(":", 1)[1])
    b = rats.get_decision(beschluss_id) or {}
    return Evidence(
        kind="decision", id=kennung, title=b.get("title") or "",
        date=b.get("session_date"), outcome=b.get("outcome"),
        text=_kurz(b.get("simple_summary") or b.get("summary")
                   or b.get("official_text")),
        score=score)


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
