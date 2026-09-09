"""Der Lauf des Annotators ``fit``: Hat Oldenburg das schon, und lohnt es sich?

**Warum ein eigenes Modul.** ``council/cities/annotate.py`` fragt Batches von
Vorlagen nach einem Etikett — sechs auf einmal, ohne Kontext, ohne Rückfrage
an eine zweite Datenbank. ``fit`` ist eine andere Sache: Jede Vorlage bekommt
ihre eigenen Belege aus Oldenburg, geht allein ins Modell, und was
zurückkommt, wird gegen die vorgelegten Belege geprüft. Das in den vorhandenen
Lauf zu falten hieße, ihn an fünf Stellen zu verzweigen.

**Ohne Beleg keine Frage, ohne Beleg-Kennung kein Urteil.** Findet
``evidence_for`` nichts aus Oldenburg, wird das Modell gar nicht erst gefragt —
die Antwort wäre eine Behauptung ins Leere. Und nennt es eine Kennung, die
ihm nicht vorlag, fliegt der ganze Eintrag raus. Beides wird gezählt, damit
ein Rückgang auffällt.

**Die Arbeiter fassen die Datenbank GAR NICHT an — auch nicht lesend.**
Bisher stand hier nur „geschrieben wird im Hauptthread", und genau die
Lücke hat am 09.09.2026 zugeschlagen: Der Prompt holte sich den
Vorlagentext mit ``text_for_paper`` aus dem Arbeiter. Bei vier Arbeitern
fiel das nie auf, bei vierzig warf SQLite ``InterfaceError: bad parameter
or other API misuse`` — dieselbe Verbindung, zwei Threads gleichzeitig. Der
Fehler wurde als „eine Vorlage gescheitert" gezählt und **verschluckt**: Der
Lauf lief weiter, die Stimme fehlte.

Alles, was aus der Datenbank kommt, wird deshalb VORHER eingesammelt —
Belege, Cluster-Zeile, Vorlagentext — und liegt als Dict bereit, wenn die
Arbeiter starten. Sie rechnen und rufen das Modell; sie lesen und schreiben
nichts. ``tests/test_cities_fit.py`` hält das fest.
"""
from __future__ import annotations

import hashlib
import logging
import os
import threading
import time
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING

from pydantic import ValidationError

from council.cities.annotate import parse_json
from council.cities.annotators import USABLE, Annotator, OldenburgStatus
from council.cities import evidence as beleg_modul
from council.cities.evidence import (
    OLDENBURG_STECKBRIEF, Evidence, cluster_zeile, evidence_for)
from council.cities.store import CitiesStore
from kern import llm, prompts

if TYPE_CHECKING:
    from council.store import CouncilStore

logger = logging.getLogger("council.cities.fit")

#: Wie viele Urteile gleichzeitig unterwegs sind. Vier ist der sichere Wert
#: für den Wochen-Cron; ein BACKFILL über den ganzen Bestand braucht mehr —
#: 9.675 Kandidaten mal drei Stimmen sind bei vier Arbeitern Tage statt
#: Stunden. Über die Umgebung, damit ein Nachlauf nicht Code ändern muss.
WORKERS = int(os.environ.get("CITIES_FIT_WORKERS", "4"))

#: Wie viele Suchwort-Aufrufe gleichzeitig unterwegs sind — und warum das
#: ein eigener Regler ist. Die Belegsammlung sieht nach Rechenarbeit aus
#: (20.936 Vektoren je Vorlage), ist aber fast nur Warten: Gemessen am
#: 09.09.2026 lief sie mit **2,2 Vorlagen je Sekunde**, und in jeder dieser
#: 0,45 Sekunden steckte EIN kleiner Modellaufruf für die Oldenburger
#: Suchwörter (``evidence.search_terms``). Über 9.688 Vorlagen sind das
#: **73 Minuten**, in denen ein Kern wartet und sonst nichts geschieht — vor
#: dem eigentlichen Lauf, der noch gar nicht begonnen hat.
#:
#: Parallel läuft deshalb **nur dieser Aufruf**. Er fasst keine Datenbank an;
#: alles Übrige (``neighbors``, FTS, die Oldenburger Beschlüsse) bleibt im
#: Hauptthread, weil eine SQLite-Verbindung nebenläufig zu benutzen genau der
#: Fehler ist, den der Modulkopf beschreibt. Die Wörter gehen als
#: ``begriffe`` in ``evidence_for`` — für genau diesen Fall gibt es den
#: Parameter, er ist nicht neu.
TERM_WORKERS = int(os.environ.get("CITIES_TERM_WORKERS", "16"))

#: Blockweise, nicht auf einen Schlag: 9.688 Aufträge gleichzeitig in einen
#: Pool zu werfen kostet nichts an Zeit, aber der Fortschritt stünde erst am
#: Ende in einer Zeile — und ein Lauf ohne sichtbaren Fortschritt sieht aus
#: wie ein hängender Lauf.
TERM_BLOCK = 200

#: Belege, die eine Aussage über Oldenburg tragen. Der Themenfeld-Rückblick
#: gehört nicht dazu: Er sagt, was die Stadt gerade beschäftigt, nicht ob sie
#: dieses eine Instrument hat. Ein Papier, für das es nur ihn gibt, wird
#: übersprungen.
TRAGENDE_ARTEN = ("cluster", "neighbor", "chunk", "fts", "decision")


def candidates_for(main: CitiesStore, body_id: str | None = None) -> list[dict]:
    """Die fremden Vorlagen, für die die Frage überhaupt Sinn ergibt.

    Nur was die Einordnung als übertragbar führt. Für einen Münsteraner
    Bebauungsplan ist „fehlt Oldenburg das?" keine sinnvolle Frage — er fehlt
    Oldenburg, und das ist richtig so.
    """
    einordnung = main.annotations_for("classify", "2")
    return [p for p in main.papers(body_id=body_id)
            if p["body_id"] != "oldenburg"
            and (einordnung.get(p["id"]) or {}).get("transfer") in USABLE]


def source_hash(paper: dict, classification: dict, belege: list[Evidence],
                ann: Annotator, cluster: str = "", effort: dict | None = None) -> str:
    """Woraus das Urteil entstanden ist — Vorlage UND Belege.

    Der Unterschied zu ``annotate.source_hash``: Dort hängt das Etikett allein
    an der fremden Vorlage. Hier hängt das Urteil auch daran, was Oldenburg
    hat — und das wächst. Kommt ein Oldenburger Nachbar dazu oder ändert sich
    der Themenfeld-Rückblick, ist das Urteil neu zu fällen, auch wenn die
    fremde Vorlage unverändert ist. Genau das merkt ``annotations_missing``.
    """
    teile = [
        paper.get("name") or "", paper.get("date") or "",
        classification.get("instrument") or "", classification.get("field") or "",
        "|".join(sorted(e.id for e in belege)),
        # Der Rückblick ändert sich wöchentlich; sein Text gehört mit hinein,
        # sonst bliebe ein Urteil stehen, dessen Kontext ein anderer ist.
        "|".join(e.text[:120] for e in belege if e.kind == "recap"),
        # Der Cluster wächst mit jeder geernteten Stadt, die Aufwandsklasse
        # kann sich mit einer neuen Fassung ändern — beides gehört in den
        # Hash, sonst bliebe ein Urteil stehen, dessen Grundlage eine andere
        # ist. Genau das merkt `annotations_missing`.
        cluster or "", str(sorted((effort or {}).items())),
        ann.version, prompts.get(ann.prompt_system)[:200],
    ]
    return hashlib.sha256("␟".join(teile).encode("utf-8")).hexdigest()


#: Die Aufwandsklassen im Klartext — dieselben Worte wie im effort-Prompt.
AUFWAND_TEXT = {
    "inquiry": "Anfrage (will wissen, nicht ändern)",
    "review": "Prüfauftrag an die Verwaltung",
    "resolution": "Resolution an Land oder Bund",
    "decision": "Beschluss mit unmittelbarer Wirkung",
    "budget": "Beschluss, der Geld bindet",
}


def paper_text(paper: dict, classification: dict, text: str | None,
               ann: Annotator, effort: dict | None = None) -> str:
    """Die fremde Vorlage, so wie sie im Prompt steht."""
    zeilen = [
        f"Stadt: {paper.get('body_id')}",
        f"Art: {paper.get('paper_type_raw') or paper.get('kind')}",
        f"Datum: {paper.get('date') or 'unbekannt'}",
        f"Titel: {paper.get('name')}",
    ]
    for schluessel, label in (("instrument", "Instrument"), ("field", "Themenfeld"),
                              ("competence", "Zuständigkeit"),
                              ("summary", "Zusammenfassung")):
        wert = classification.get(schluessel)
        if wert:
            zeilen.append(f"{label}: {wert}")
    # Aufwand und Adressat entscheiden zwei der drei „lohnt sich"-Bedingungen —
    # eine Resolution ist nie das Beste, was der Rat tun kann, und was die VWG
    # entscheidet, kann er nicht beschließen.
    if effort:
        klasse = effort.get("effort")
        if klasse:
            zeilen.append(f"Aufwand: {klasse} — {AUFWAND_TEXT.get(klasse, '')}")
        if effort.get("addressee"):
            zeilen.append(f"Adressat: {effort['addressee']} (nicht die Stadt selbst)")
    if text:
        zeilen.append("Text: " + " ".join(text.split())[:ann.input_chars])
    return "\n".join(zeilen)


def evidence_text(belege: list[Evidence]) -> str:
    return "\n".join(e.as_prompt_line() for e in belege)


def pruefe(nutzlast, erlaubte: set[str], tragende: set[str] | None = None) -> str | None:
    """``None``, wenn das Urteil steht — sonst der Grund, es zu verwerfen.

    Drei Prüfungen, die pydantic nicht leisten kann, weil sie die Belege
    kennen müssen:

    - **Erfundene Kennung.** Das Modell soll aus einer Liste zitieren. Nennt
      es etwas anderes, ist die Grundlage des Urteils unklar — und ein Urteil
      ohne klare Grundlage ist genau das, was hier nicht gespeichert werden
      soll.
    - **Behauptung ohne Beleg.** „Oldenburg hat das" ist eine Aussage über
      Oldenburg; sie braucht mindestens eine Kennung. Bei ``missing`` ist die
      leere Liste dagegen die Aussage.
    - **Behauptung nur auf den Rückblick.** Der Themenfeld-Rückblick sagt, was
      die Stadt gerade beschäftigt — nicht, ob sie dieses eine Instrument hat.
      Er darf ein Urteil begleiten, nicht tragen. Beim Bauen des Golden Sets
      war das der Fall, in dem ich selbst versucht war, aus „Oldenburg hat
      einen Brandbrief gegen Kürzungen geschrieben" ein „vorhanden" zu machen.
    """
    erfunden = [k for k in nutzlast.evidence if k not in erlaubte]
    if erfunden:
        return "hallucinated_evidence:" + ",".join(erfunden[:3])
    if not nutzlast.braucht_beleg:
        return None
    if not nutzlast.evidence:
        return "claim_without_evidence"
    if tragende is not None and not (set(nutzlast.evidence) & tragende):
        return "claim_only_on_recap"
    return None


#: Wie viele Stimmen je Vorlage. Die Eigenstreuung des Modells lag über fünf
#: Läufe bei 12 Punkten (60–72 % Status) — bei EINER Stimme entscheidet
#: zufällig, welche davon in der Datenbank landet.
VOTES = int(os.environ.get("CITIES_FIT_VOTES", "3"))

#: Vom Vorsichtigen zum Kühnen. Bei Gleichstand gewinnt der vordere Wert:
#: „Oldenburg hat das schon" nimmt eine Idee von der Liste und ist damit der
#: teurere Irrtum — dieselbe Asymmetrie, die der Prüfstand als harte Schranke
#: führt.
STATUS_ORDNUNG = ("missing", "partial", "present")


def _mehrheit(werte: list[str], ordnung: tuple[str, ...]) -> str:
    """Der häufigste Wert; bei Gleichstand der vorsichtigere."""
    zaehler: dict[str, int] = {}
    for w in werte:
        zaehler[w] = zaehler.get(w, 0) + 1
    hoechste = max(zaehler.values())
    gleichauf = [w for w, n in zaehler.items() if n == hoechste]
    return min(gleichauf, key=lambda w: ordnung.index(w) if w in ordnung else 99)


def majority(urteile: Sequence[OldenburgStatus]) -> tuple[OldenburgStatus, str]:
    """Aus mehreren Stimmen ein Urteil — und wie sicher es ist.

    Belege: nur die, die MINDESTENS ZWEI Stimmen nennen — eine Kennung, die
    nur ein Lauf gesehen hat, trägt kein Urteil. Bleibt danach keine übrig,
    obwohl der Status eine Behauptung ist, greift `pruefe` und verwirft.

    Die Begründung stammt aus der Stimme, die der Mehrheit entspricht und die
    höchste Zuversicht trägt — nicht aus einer zusammengesetzten.
    """
    if not urteile:
        raise ValueError("keine Stimmen")
    status = _mehrheit([u.status for u in urteile], STATUS_ORDNUNG)

    zaehler: dict[str, int] = {}
    for u in urteile:
        for k in u.evidence:
            zaehler[k] = zaehler.get(k, 0) + 1
    schwelle = 2 if len(urteile) > 1 else 1
    belege = [k for k, n in zaehler.items() if n >= schwelle][:3]

    rang = {"high": 0, "medium": 1, "low": 2}
    passend = [u for u in urteile if u.status == status] or urteile
    traeger = min(passend, key=lambda u: rang.get(u.confidence, 9))

    einig = sum(1 for u in urteile if u.status == status)
    if einig == len(urteile) and len(urteile) > 1:
        zuversicht = traeger.confidence
    elif einig * 2 > len(urteile):
        zuversicht = "medium" if traeger.confidence == "high" else traeger.confidence
    else:
        zuversicht = "low"

    ergebnis = traeger.model_copy(update={
        "status": status, "evidence": belege, "confidence": zuversicht})
    return ergebnis, f"{einig}/{len(urteile)}"


def run(main: CitiesStore, rats: CouncilStore, ann: Annotator,
        model: str, body_id: str | None = None, limit: int | None = None,
        workers: int = WORKERS) -> dict:
    """Jede übertragbare fremde Vorlage einmal gegen Oldenburg halten."""
    einordnung = main.annotations_for("classify", "2")
    aufwand = main.annotations_for("effort", "1")
    kandidaten = candidates_for(main, body_id)
    if not kandidaten:
        return _leer()

    # Belege zuerst, für alle: Sie gehen in den source_hash ein, und ohne den
    # wüssten wir nicht, was offen ist.
    logger.info("fit: Belege für %s Vorlagen sammeln", len(kandidaten))
    # Die Chunk-Matrix EINMAL: 34.000 Vektoren je Vorlage neu zu lesen wäre
    # der teuerste Teil des ganzen Laufs, und sie ändert sich dabei nicht.
    matrix = main.chunk_matrix(model, "oldenburg")
    # Und die PAPIER-Matrix, aus demselben Grund: Der Nachbar-Arm rechnet
    # seit 09.09.2026 selbst gegen sie, statt die Tabelle `neighbors` zu
    # lesen — die hält je Objekt nur die acht nächsten über ALLE Städte.
    papier_matrix = main.paper_matrix(model, "oldenburg")
    logger.info("fit: %s Oldenburger Textabschnitte, %s Vorlagen im Speicher",
                len(matrix[0]), len(papier_matrix[0]))
    belege_je: dict[str, list[Evidence]] = {}
    cluster_je: dict[str, str] = {}
    # Der Vorlagentext, hier und nicht im Arbeiter. Siehe `texte_je` unten.
    texte_je: dict[str, str | None] = {}
    hashes: dict[str, str] = {}
    for start in range(0, len(kandidaten), TERM_BLOCK):
        block = kandidaten[start:start + TERM_BLOCK]
        # Erst die Suchwörter für den ganzen Block — nebenläufig, weil nur
        # sie warten. Was danach kommt, rechnet und liest und bleibt hier.
        # Über das MODUL gerufen, nicht als importierter Name: `evidence_for`
        # tut es auch so, und ein Prüfstand, der `evidence.search_terms`
        # ersetzt, träfe eine hier festgehaltene Kopie sonst nicht.
        with ThreadPoolExecutor(max_workers=TERM_WORKERS) as pool:
            begriffe_je = list(pool.map(
                lambda p: beleg_modul.search_terms(einordnung.get(p["id"]) or {}, p),
                block))
        for p, begriffe in zip(block, begriffe_je):
            klasse = einordnung.get(p["id"]) or {}
            belege = evidence_for(main, rats, p, klasse, model,
                                  chunk_matrix=matrix, begriffe=begriffe,
                                  paper_matrix=papier_matrix)
            belege_je[p["id"]] = belege
            cluster_je[p["id"]] = cluster_zeile(main, p, model)
            texte_je[p["id"]] = main.text_for_paper(p["id"])
            hashes[p["id"]] = source_hash(p, klasse, belege, ann,
                                          cluster_je[p["id"]], aufwand.get(p["id"]))
        logger.info("  Belege %s/%s", min(start + TERM_BLOCK, len(kandidaten)),
                    len(kandidaten))

    offen = main.annotations_missing("paper", ann.key, ann.version, body_id=body_id,
                                     source_hashes=hashes)
    offen = [p for p in offen if p["id"] in belege_je]
    if limit:
        offen = offen[:limit]
    if not offen:
        return _leer()

    system = prompts.render(ann.prompt_system, steckbrief=OLDENBURG_STECKBRIEF)
    sperre = threading.Lock()
    stand = {"annotated": 0, "errors": 0, "skipped_no_evidence": 0,
             "hallucinated_evidence": 0, "claim_without_evidence": 0,
             "claim_only_on_recap": 0, "votes": 0, "incomplete_votes": 0,
             "split": 0,
             "cost_usd": 0.0, "prompt_tokens": 0, "completion_tokens": 0}
    t0 = time.time()

    def eine_stimme(p: dict, belege: list[Evidence], klasse: dict):
        """Ein Aufruf ans Modell — gibt die geprüfte Nutzlast oder ``None``."""
        try:
            extra = {"provider": {}} if ann.routing_free else {}
            antwort = llm.chat_complete(
                model=ann.model, response_format={"type": "json_object"},
                messages=[{"role": "system", "content": system},
                          {"role": "user", "content": prompts.render(
                              ann.prompt_user,
                              paper=paper_text(p, klasse, texte_je.get(p["id"]),
                                               ann, aufwand.get(p["id"])),
                              cluster=cluster_je.get(p["id"], ""),
                              evidence=evidence_text(belege))}],
                max_tokens=ann.max_tokens, temperature=ann.temperature,
                extra_body=extra, _feature=ann.feature)
            daten = parse_json(antwort.choices[0].message.content or "")
        except Exception as e:  # noqa: BLE001 — eine Vorlage, nicht der Lauf
            with sperre:
                stand["errors"] += 1
            logger.info("fit gescheitert (%s): %s: %s", p["id"], type(e).__name__,
                        str(e)[:120])
            return None

        verbrauch = getattr(antwort, "usage", None)
        kosten = float(getattr(verbrauch, "cost", 0) or 0) if verbrauch else 0.0
        with sperre:
            if verbrauch:
                stand["prompt_tokens"] += verbrauch.prompt_tokens or 0
                stand["completion_tokens"] += verbrauch.completion_tokens or 0
                stand["cost_usd"] += kosten
        try:
            nutzlast = ann.payload.model_validate(daten)
            if not isinstance(nutzlast, OldenburgStatus):
                # Kein Typ-Theater: `majority` liest `status`, `worth` und
                # `evidence`. Wer `fit` mit einer anderen Nutzlast registriert,
                # soll es HIER erfahren und nicht drei Zeilen später an einem
                # fehlenden Attribut.
                raise TypeError(
                    f"fit erwartet OldenburgStatus, bekam {type(nutzlast).__name__}")
        except ValidationError as e:
            with sperre:
                stand["errors"] += 1
            logger.info("Antwort passt nicht zur Form (%s): %s", p["id"], str(e)[:120])
            return None

        # Jede Stimme wird EINZELN geprüft. Eine, die sich einen Beleg
        # ausdenkt, zählt nicht mit — sonst trüge die Mehrheit die Erfindung
        # mit, weil zwei andere Stimmen sie überstimmen.
        grund = pruefe(nutzlast, {e.id for e in belege},
                       {e.id for e in belege if e.kind in TRAGENDE_ARTEN})
        if grund:
            with sperre:
                schluessel = grund.split(":")[0]
                stand[schluessel] = stand.get(schluessel, 0) + 1
            logger.info("Stimme verworfen (%s): %s", p["id"], grund)
            return None
        return nutzlast

    def eine(p: dict) -> tuple[str, dict, float] | None:
        """Ein Papier, mehrere Stimmen, ein Urteil — ohne die Datenbank."""
        belege = belege_je.get(p["id"]) or []
        if not any(e.kind in TRAGENDE_ARTEN for e in belege):
            with sperre:
                stand["skipped_no_evidence"] += 1
            return None
        klasse = einordnung.get(p["id"]) or {}
        vorher = stand["cost_usd"]
        stimmen = [x for x in (eine_stimme(p, belege, klasse) for _ in range(VOTES))
                   if x is not None]
        kosten = stand["cost_usd"] - vorher
        if not stimmen:
            return None
        ergebnis, einigkeit = majority(stimmen)
        with sperre:
            stand["votes"] = stand.get("votes", 0) + len(stimmen)
            if len(stimmen) < VOTES:
                stand["incomplete_votes"] = stand.get("incomplete_votes", 0) + 1
            if einigkeit.startswith("1/") and VOTES > 1:
                stand["split"] = stand.get("split", 0) + 1
        # Die Mehrheit kann Belege wegnehmen (nur was zwei Stimmen nennen) —
        # damit kann sie eine Behauptung ohne Beleg erzeugen, die keine
        # Einzelstimme war. Deshalb hier noch einmal prüfen.
        grund = pruefe(ergebnis, {e.id for e in belege},
                       {e.id for e in belege if e.kind in TRAGENDE_ARTEN})
        if grund:
            with sperre:
                schluessel = grund.split(":")[0]
                stand[schluessel] = stand.get(schluessel, 0) + 1
            logger.info("Mehrheit verworfen (%s): %s", p["id"], grund)
            return None
        return p["id"], ergebnis.model_dump(), kosten

    def schreiben(ergebnisse: list[tuple[str, dict, float]]) -> None:
        """Der EINE Schreiber — im Hauptthread, in einer Transaktion."""
        if not ergebnisse:
            return
        with main.transaction():
            for kennung, nutzlast, kosten in ergebnisse:
                main.put_annotation("paper", kennung, ann.key, ann.version, nutzlast,
                                    hashes.get(kennung, ""), model=ann.model,
                                    cost_usd=kosten)
        stand["annotated"] += len(ergebnisse)

    logger.info("fit/%s: %s Vorlagen zu beurteilen", ann.version, len(offen))
    puffer: list[tuple[str, dict, float]] = []
    with ThreadPoolExecutor(workers) as pool:
        for n, ergebnis in enumerate(pool.map(eine, offen), 1):
            if ergebnis:
                puffer.append(ergebnis)
            if len(puffer) >= 25:
                schreiben(puffer)
                puffer = []
            if n % 50 == 0:
                logger.info("  %s/%s · %.0fs · $%.4f", n, len(offen),
                            time.time() - t0, stand["cost_usd"])
    schreiben(puffer)

    stand["seconds"] = round(time.time() - t0)
    logger.info("fit fertig: %s Urteile, %s ohne Belege, %s verworfen, $%.4f, %ss",
                stand["annotated"], stand["skipped_no_evidence"],
                stand["hallucinated_evidence"] + stand["claim_without_evidence"],
                stand["cost_usd"], stand["seconds"])
    return stand


def _leer() -> dict:
    return {"annotated": 0, "errors": 0, "skipped_no_evidence": 0,
            "hallucinated_evidence": 0, "claim_without_evidence": 0,
            "claim_only_on_recap": 0, "votes": 0, "incomplete_votes": 0,
            "split": 0, "cost_usd": 0.0, "seconds": 0}
