"""Hat Oldenburg diese IDEE schon? — ein Urteil je Gruppe (Plan PR 48).

**Warum nicht die Einzelurteile zusammenzählen.** ``fit`` urteilt je Vorlage
und sieht dabei nur deren eigene Belege. Dieselbe Idee bekommt so in
Hannover „fehlt", in Münster „teilweise" und in Potsdam „vorhanden" — bei 61
von 81 Ideen aus drei und mehr Städten widersprachen sich die Einzelurteile
(gemessen 22.09.2026, Plan §2.3). Keine Mehrheitsregel trifft dann den
richtigen Stand, weil jede Stimme nur einen Ausschnitt kannte.

Hier sieht das Modell alle Vorlagen einer Idee und die VEREINIGUNG ihrer
Oldenburger Belege auf einmal, und die Einzelurteile nur als Hinweis.

**Woher die Belege kommen.** Drei Quellen, in dieser Reihenfolge:

1. Oldenburgs eigene Mitglieder der Gruppe — die Gruppierung hat sie
   DERSELBEN Idee zugeordnet.
2. Was die Einzelurteile als Beleg genannt haben, nach Häufigkeit — ein
   Papier, das drei Städte-Urteile tragen, steht vor einem, das eins trägt.
3. Die Beleg-Suche aus ``evidence.evidence_for`` für die typischsten
   Mitglieder. Ohne sie hätte eine Idee, die überall als „fehlt" beurteilt
   wurde, gar keine Belege — und damit nichts, was unter ``related`` stehen
   könnte.

Der Themenfeld-Rückblick fehlt absichtlich: Er trägt kein Urteil, und als
„verwandt" wäre er auf jeder Karte desselben Feldes derselbe Satz.
"""
from __future__ import annotations

import hashlib
import logging
import os
import threading
import time
from collections import Counter
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, cast

from pydantic import ValidationError

from council.cities import evidence as beleg_modul
from council.cities import fit
from council.cities.annotate import parse_json
from council.cities.annotators import LLM_TIMEOUT_S, Annotator, IdeaVerdict
from council.cities.annotators import get as get_annotator
from council.cities.clusters import CLUSTER_VERSION
from council.cities.evidence import (OLDENBURG_STECKBRIEF, Evidence, EvidenceKind,
                                     evidence_for)
from council.cities.store import CitiesStore
from kern import llm, prompts
from kern.stopp import Stopp

if TYPE_CHECKING:
    from council.store import CouncilStore

logger = logging.getLogger("council.cities.idea_fit")

#: Ab wie vielen Städten eine Idee beurteilt wird — dieselbe Grenze wie die
#: Liste der Bewegungen (Tims Entscheidung vom 22.09.2026: ab zwei Städten).
AB_STAEDTEN = 2

#: Höchstens so viele Belege gehen ins Modell. Zwölf wie bei ``fit``: mehr
#: heißt mehr abzuwägen, und ein Beleg auf Platz 20 trägt kein Urteil.
MAX_BELEGE = 12

#: Für so viele Mitglieder läuft die Beleg-Suche. Die typischsten reichen:
#: Die Suche findet für Mitglieder derselben Idee meist dieselben Papiere.
SUCHE_FUER = 3

WORKERS = int(os.environ.get("CITIES_IDEA_FIT_WORKERS", "4"))

#: Hängende Aufrufe abbrechen statt zehn Minuten warten (s. `annotators.LLM_TIMEOUT_S`).
TIMEOUT_S = LLM_TIMEOUT_S

#: Die Einzelurteile im Klartext, für die Hinweis-Zeilen.
_STATUS_TEXT = {"present": "vorhanden", "partial": "teilweise",
                "missing": "fehlt", "not_applicable": "nicht anwendbar"}


# ------------------------------------------------------------- Prüfung

def pruefe(nutzlast: IdeaVerdict, erlaubte: set[str]) -> str | None:
    """``None``, wenn das Urteil steht — sonst der Grund, es zu verwerfen.

    Dieselben Regeln wie ``fit.pruefe``, dazu ``related``: Auch dort darf nur
    stehen, was dem Modell vorlag. Eine erfundene Kennung unter „verwandt"
    ist eine Erfindung wie jede andere — die Karte zeigte einen Link ins
    Leere.
    """
    erfunden = [k for k in [*nutzlast.evidence, *nutzlast.related] if k not in erlaubte]
    if erfunden:
        return "hallucinated_evidence:" + ",".join(erfunden[:3])
    if nutzlast.braucht_beleg and not nutzlast.evidence:
        return "claim_without_evidence"
    return None


def bereinigen(nutzlast: IdeaVerdict) -> IdeaVerdict:
    """Was beide Listen nennen, bleibt Beleg; ohne Behauptung kein Beleg.

    Bei ``missing`` und ``not_applicable`` ist eine Kennung unter
    ``evidence`` ein Formfehler, kein falsches Urteil: Sie wandert nach
    ``related``, statt das Urteil zu verwerfen.
    """
    belege = list(dict.fromkeys(nutzlast.evidence))
    verwandt = [k for k in dict.fromkeys(nutzlast.related) if k not in belege]
    if not nutzlast.braucht_beleg:
        verwandt = list(dict.fromkeys([*belege, *verwandt]))[:3]
        belege = []
    return nutzlast.model_copy(update={"evidence": belege[:3], "related": verwandt[:3]})


def majority(stimmen: Sequence[IdeaVerdict]) -> tuple[IdeaVerdict, str]:
    """Aus drei Stimmen ein Urteil — Status und Belege wie bei ``fit``.

    ``related`` folgt derselben Regel wie ``evidence``: nur, was mindestens
    zwei Stimmen nennen. Eine Kennung, die nur ein Lauf gesehen hat, ist auch
    als Lesestoff ein Zufall.
    """
    # `fit.majority` liest nur status, evidence und confidence und kopiert
    # die Trägerstimme — die bleibt ein IdeaVerdict, auch wenn die Signatur
    # OldenburgStatus nennt.
    roh, einigkeit = fit.majority(stimmen)  # type: ignore[arg-type]
    ergebnis = cast(IdeaVerdict, roh)
    zaehler: Counter[str] = Counter(k for s in stimmen for k in s.related)
    schwelle = 2 if len(stimmen) > 1 else 1
    verwandt = [k for k, n in zaehler.most_common()
                if n >= schwelle and k not in ergebnis.evidence][:3]
    return bereinigen(ergebnis.model_copy(update={"related": verwandt})), einigkeit


# ------------------------------------------------------------- Vorlage

def belege_fuer(main: CitiesStore, rats: CouncilStore, mitglieder: list[dict],
                einordnung: dict[str, dict], model: str, *,
                chunk_matrix=None, paper_matrix=None,
                begriffe: dict[str, tuple[str, list[str]]] | None = None,
                suche: bool = True) -> list[Evidence]:
    """Die Oldenburger Belege einer Idee — vereinigt und dedupliziert."""
    import json

    reihe: list[tuple[str, EvidenceKind, str, str | None]] = []   # (kennung, art, titel, datum)
    for m in mitglieder:
        if m["body_id"] == "oldenburg":
            reihe.append((m["id"], "cluster", m.get("name") or "", m.get("date")))

    genannt: Counter[str] = Counter()
    for m in mitglieder:
        if m["body_id"] == "oldenburg" or not m.get("fit_json"):
            continue
        for k in json.loads(m["fit_json"]).get("evidence") or []:
            if str(k).startswith("oldenburg:"):
                genannt[str(k)] += 1
    for k, _n in genannt.most_common():
        art: EvidenceKind = "decision" if k.startswith("oldenburg:decision:") else "neighbor"
        reihe.append((k, art, "", None))

    je_mitglied: list[list[Evidence]] = []
    if suche:
        fremde = sorted((m for m in mitglieder if m["body_id"] != "oldenburg"),
                        key=lambda m: -(m.get("score") or 0.0))[:SUCHE_FUER]
        for m in fremde:
            papier = main.paper(m["id"]) or m
            klasse = einordnung.get(m["id"]) or {}
            gespeichert = (begriffe or {}).get(m["id"])
            woerter = None
            if gespeichert and gespeichert[0] == beleg_modul.terms_hash(klasse, papier):
                woerter = gespeichert[1]
            je_mitglied.append([e for e in evidence_for(
                main, rats, papier, klasse, model, chunk_matrix=chunk_matrix,
                begriffe=woerter, paper_matrix=paper_matrix) if e.kind != "recap"])

    fertig: dict[str, Evidence] = {}
    for kennung, art, titel, datum in reihe:
        if kennung in fertig or len(fertig) >= MAX_BELEGE:
            continue
        fertig[kennung] = beleg_modul._beleg_bauen(rats, main, kennung, art,  # noqa: SLF001
                                                   titel, datum, None)
    # Die gesuchten im Reißverschluss, damit nicht das erste Mitglied allein
    # die übrigen Plätze füllt.
    for rang in range(max((len(liste) for liste in je_mitglied), default=0)):
        for liste in je_mitglied:
            if rang < len(liste) and len(fertig) < MAX_BELEGE:
                fertig.setdefault(liste[rang].id, liste[rang])
    return [e for e in fertig.values() if e.title]


def vorlagen_text(mitglieder: list[dict], einordnung: dict[str, dict],
                  ann: Annotator) -> str:
    """Die fremden Vorlagen, eine Zeile je Vorlage, nach Datum."""
    zeilen = []
    for m in mitglieder:
        if m["body_id"] == "oldenburg":
            continue
        klasse = einordnung.get(m["id"]) or {}
        teile = [f"{m.get('body_name') or m['body_id']}", (m.get("date") or "")[:10],
                 m.get("kind") or ""]
        kopf = " · ".join(t for t in teile if t)
        zeile = f"- {kopf}: {klasse.get('instrument') or m.get('name') or ''}"
        zusammenfassung = (klasse.get("summary") or "").strip()
        if zusammenfassung:
            zeile += " — " + zusammenfassung[:ann.input_chars]
        zeilen.append(zeile)
    return "\n".join(zeilen)


def hinweise_text(mitglieder: list[dict]) -> str:
    """Die Einzelurteile — als Hinweis, nicht als Maßstab."""
    import json

    zeilen = []
    for m in mitglieder:
        if m["body_id"] == "oldenburg" or not m.get("fit_json"):
            continue
        urteil = json.loads(m["fit_json"])
        status = _STATUS_TEXT.get(urteil.get("status") or "", urteil.get("status") or "?")
        grund = (urteil.get("reason") or "").strip()
        zeilen.append(f"- {m.get('body_name') or m['body_id']}: {status}"
                      + (f" — {grund[:200]}" if grund else ""))
    return "\n".join(zeilen) or "(keine)"


def source_hash(gruppe: dict, mitglieder: list[dict], belege: list[Evidence],
                ann: Annotator) -> str:
    """Woraus das Urteil entstanden ist — Mitglieder, Belege, Fassung, Prompt.

    Kommt eine Stadt dazu oder ein Oldenburger Beschluss, ist die Idee neu zu
    beurteilen; bleibt alles gleich, kostet der Wochenlauf nichts.
    """
    teile = [
        gruppe.get("label") or "",
        "|".join(sorted(m["id"] for m in mitglieder)),
        "|".join(sorted(e.id for e in belege)),
        ann.version, prompts.get(ann.prompt_system)[:200],
    ]
    return hashlib.sha256("␟".join(teile).encode("utf-8")).hexdigest()


# ------------------------------------------------------------- Urteil

class Richter:
    """Drei Stimmen, eine Mehrheit, zweimal geprüft — ohne die Datenbank.

    Getrennt vom Lauf, damit der Prüfstand (``eval/run_cities_idea_fit.py``)
    GENAU diesen Weg misst und nicht eine Nachbildung davon. Schreiben tut
    nur ``run``.
    """

    def __init__(self, ann: Annotator, einordnung: dict[str, dict], stand: dict):
        self.ann = ann
        self.einordnung = einordnung
        self.stand = stand
        self.sperre = threading.Lock()
        self.system = prompts.render(ann.prompt_system, steckbrief=OLDENBURG_STECKBRIEF,
                                     regel_nicht_anwendbar=prompts.REGEL_NICHT_ANWENDBAR)

    def _zaehle(self, schluessel: str, n: int | float = 1) -> None:
        with self.sperre:
            self.stand[schluessel] = self.stand.get(schluessel, 0) + n

    def nutzer_text(self, g: dict, mitglieder: list[dict], belege: list[Evidence]) -> str:
        return prompts.render(
            self.ann.prompt_user, idee=g["label"],
            vorlagen=vorlagen_text(mitglieder, self.einordnung, self.ann),
            hinweise=hinweise_text(mitglieder),
            evidence=fit.evidence_text(belege) or "(keine)")

    def stimme(self, g: dict, mitglieder: list[dict], belege: list[Evidence],
               korb: list[float]) -> IdeaVerdict | None:
        """Ein Aufruf — die geprüfte Nutzlast oder ``None``."""
        ann = self.ann
        try:
            antwort = llm.chat_complete(
                model=ann.model, response_format={"type": "json_object"},
                messages=[{"role": "system", "content": self.system},
                          {"role": "user", "content": self.nutzer_text(g, mitglieder, belege)}],
                max_tokens=ann.max_tokens, temperature=ann.temperature,
                extra_body={"provider": {}} if ann.routing_free else {},
                timeout=TIMEOUT_S, _feature=ann.feature)
            daten = parse_json(antwort.choices[0].message.content or "")
        except Exception as e:  # noqa: BLE001 — eine Idee, nicht der Lauf
            self._zaehle("errors")
            logger.info("idea_fit gescheitert (%s): %s: %s", g.get("cluster_id"),
                        type(e).__name__, str(e)[:120])
            return None
        verbrauch = getattr(antwort, "usage", None)
        korb.append(float(getattr(verbrauch, "cost", 0) or 0) if verbrauch else 0.0)
        try:
            nutzlast = bereinigen(IdeaVerdict.model_validate(daten))
        except ValidationError as e:
            self._zaehle("errors")
            logger.info("Antwort passt nicht zur Form (%s): %s", g.get("cluster_id"),
                        str(e)[:120])
            return None
        # Jede Stimme EINZELN prüfen: Eine, die sich einen Beleg ausdenkt,
        # zählt nicht mit — sonst trüge die Mehrheit die Erfindung mit.
        grund = pruefe(nutzlast, {e.id for e in belege})
        if grund:
            self._zaehle(grund.split(":")[0])
            logger.info("Stimme verworfen (%s): %s", g.get("cluster_id"), grund)
            return None
        return nutzlast

    def urteil(self, g: dict, mitglieder: list[dict],
               belege: list[Evidence]) -> tuple[IdeaVerdict | None, float]:
        """``(urteil, kosten)`` — ``None``, wenn keine Mehrheit hält."""
        korb: list[float] = []
        stimmen = [s for s in (self.stimme(g, mitglieder, belege, korb)
                               for _ in range(fit.VOTES)) if s is not None]
        kosten = sum(korb)
        self._zaehle("cost_usd", kosten)
        self._zaehle("votes", len(stimmen))
        if len(stimmen) < fit.VOTES:
            self._zaehle("incomplete_votes")
        if not stimmen:
            return None, kosten
        ergebnis, einigkeit = majority(stimmen)
        if einigkeit.startswith("1/") and fit.VOTES > 1:
            self._zaehle("split")
        # Die Mehrheit kann Belege wegnehmen (nur, was zwei Stimmen nennen) —
        # und damit eine Behauptung ohne Beleg erzeugen. Noch einmal prüfen.
        grund = pruefe(ergebnis, {e.id for e in belege})
        if grund:
            self._zaehle(grund.split(":")[0])
            return None, kosten
        return ergebnis, kosten


# ------------------------------------------------------------- Lauf

def run(main: CitiesStore, rats: CouncilStore, model: str, *,
        limit: int | None = None, min_cities: int = AB_STAEDTEN,
        workers: int = WORKERS, stopp: Stopp | None = None,
        nur: Sequence[int] | None = None, suche: bool = True) -> dict:
    """Jede Idee ab ``min_cities`` Städten einmal gegen Oldenburg halten.

    ``nur`` beschränkt auf bestimmte Gruppen (Prüfstand, Nachurteilen).
    Geschrieben wird im Hauptthread, in Blöcken — derselbe eine Schreiber
    wie bei ``fit``.
    """
    ann = get_annotator("idea_fit")
    einordnung = main.annotations_for("classify", "2")
    gruppen, _ = main.idea_groups(model, CLUSTER_VERSION, min_cities=min_cities,
                                  limit=100_000)
    if nur is not None:
        gewollt = set(nur)
        gruppen = [g for g in gruppen if g["cluster_id"] in gewollt]
    stand = {"annotated": 0, "errors": 0, "hallucinated_evidence": 0, "claim_without_evidence": 0,
             "votes": 0, "incomplete_votes": 0, "split": 0, "unchanged": 0,
             "cost_usd": 0.0, "seconds": 0}
    if not gruppen:
        return stand
    t0 = time.time()

    matrix = main.chunk_matrix(model, "oldenburg") if suche else None
    papier_matrix = main.paper_matrix(model, "oldenburg") if suche else None
    begriffe = main.evidence_terms() if suche else None

    auftraege: list[tuple[dict, list[dict], list[Evidence], str]] = []
    for g in gruppen:
        mitglieder = main.idea_group_members(model, CLUSTER_VERSION, g["cluster_id"])
        belege = belege_fuer(main, rats, mitglieder, einordnung, model,
                             chunk_matrix=matrix, paper_matrix=papier_matrix,
                             begriffe=begriffe, suche=suche)
        quelle = source_hash(g, mitglieder, belege, ann)
        alt = main.annotation("cluster", f"{CLUSTER_VERSION}:{g['cluster_id']}",
                              ann.key, ann.version)
        if alt and alt.get("source_hash") == quelle:
            stand["unchanged"] += 1
            continue
        auftraege.append((g, mitglieder, belege, quelle))
        if limit and len(auftraege) >= limit:
            break
        abbruch = stopp.grund() if stopp else None
        if abbruch:
            stand[f"abgebrochen_{abbruch.schluessel}"] = 1
            return stand
    logger.info("idea_fit: %s Ideen zu beurteilen, %s unverändert",
                len(auftraege), stand["unchanged"])

    richter = Richter(ann, einordnung, stand)

    def eine(auftrag) -> tuple[int, dict, str, float] | None:
        g, mitglieder, belege, quelle = auftrag
        ergebnis, kosten = richter.urteil(g, mitglieder, belege)
        if ergebnis is None:
            return None
        return g["cluster_id"], ergebnis.model_dump(), quelle, kosten

    def schreiben(puffer: list[tuple[int, dict, str, float]]) -> None:
        if not puffer:
            return
        with main.transaction():
            for cid, nutzlast, quelle, kosten in puffer:
                main.put_annotation("cluster", f"{CLUSTER_VERSION}:{cid}", ann.key,
                                    ann.version, nutzlast, quelle, model=ann.model,
                                    cost_usd=kosten)
        stand["annotated"] += len(puffer)

    puffer: list[tuple[int, dict, str, float]] = []
    abbruch = None
    with ThreadPoolExecutor(workers) as pool:
        for n, ergebnis in enumerate(pool.map(eine, auftraege), 1):
            if ergebnis:
                puffer.append(ergebnis)
            if len(puffer) >= 10:
                schreiben(puffer)
                puffer = []
            if n % 20 == 0:
                logger.info("  %s/%s · %.0fs · $%.4f", n, len(auftraege),
                            time.time() - t0, stand["cost_usd"])
            abbruch = stopp.grund() if stopp else None
            if abbruch:
                pool.shutdown(wait=False, cancel_futures=True)
                break
    schreiben(puffer)
    if abbruch:
        stand[f"abgebrochen_{abbruch.schluessel}"] = 1
    stand["seconds"] = round(time.time() - t0)
    logger.info("idea_fit fertig: %s Urteile, %s verworfen, $%.4f, %ss",
                stand["annotated"],
                stand["hallucinated_evidence"] + stand["claim_without_evidence"],
                stand["cost_usd"], stand["seconds"])
    return stand
