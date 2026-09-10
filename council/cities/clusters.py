"""Dieselbe Idee in mehreren Städten — als Menge, nicht als Kantenpaar.

**Warum das der stärkste Befund ist, den der Speicher hergeben kann.** Ein
einzelnes „Osnabrück hat X beschlossen, Oldenburg nicht" ist eine Beobachtung.
„Vier von sechs Städten haben X, Oldenburg nicht" ist ein Argument — und es
filtert Lokalkolorit von selbst weg: Eine Initiative, die nur in
Sachsen-Anhalt existiert, findet keine zweite Stadt.

**Warum die Instrument-Texte dafür nicht reichen.** Sie sind Freitext, und
Freitext trifft sich nicht: Von 1.461 verschiedenen Instrument-Texten im
Bestand waren am 08.09.2026 **fünf** wortgleich in zwei Städten.
„Zweckentfremdungssatzung erlassen" steht siebenmal so da — und „Satzung gegen
Zweckentfremdung von Wohnraum" daneben, ungezählt. Es braucht also einen
Vektor, keinen Vergleich.

**Warum nicht der Papier-Vektor.** Der trägt den ganzen Text: Ortsnamen,
Datum, Antragsteller, Verwaltungsprosa. Für „ist das dieselbe Idee?" ist all
das Rauschen. Eingebettet wird deshalb nur, was die Einordnung als die IDEE
bezeichnet hat — Instrument plus Zusammenfassung, sonst nichts.

**Warum Oldenburg mitgeclustert wird.** Ein Cluster mit einem Oldenburger
Mitglied ist „hat Oldenburg das schon?" **strukturell** beantwortet — nicht
als Meinung eines Modells, sondern als Nachbarschaft im selben Raum. Das ist
der zweite, unabhängige Kanal zu ``fit``, und die beiden müssen übereinstimmen.
"""
from __future__ import annotations

import logging
import os
import time
from typing import TYPE_CHECKING

from council.cities.annotators import USABLE
from council.cities.index import EMBED_MODEL
from council.cities.store import CitiesStore, text_hash

if TYPE_CHECKING:
    import numpy as np

logger = logging.getLogger("council.cities.clusters")

#: Die Fassung der Cluster-Rechnung. Wie bei den Annotatoren: Eine zweite
#: Fassung liegt neben der ersten, bis die Messung entschieden hat.
CLUSTER_VERSION = "1"

#: Objektart im Vektor-Speicher. Ein IDEEN-Vektor ist etwas anderes als der
#: Vektor des Papiers, das sie trägt — deshalb ein eigener ``object_kind``
#: und keine zweite Tabelle.
IDEA_KIND = "idea"

#: Ab welcher Nähe zwei Ideen dieselbe sind. **Gemessen**, nicht geschätzt
#: (``scripts/cities_cluster_bericht.py --schwelle 0.74 0.78 0.82 0.86 0.90``,
#: 09.09.2026 über 5.187 Ideen):
#:
#: | Schwelle | Cluster | größter | ≥ 2 Städte | ohne Oldenburg |
#: |---|---:|---:|---:|---:|
#: | 0,74 | 367 | **2.607** | 108 | 46 |
#: | 0,78 | 546 | **1.247** | 157 | 56 |
#: | 0,82 | 606 | 190 | 163 | 60 |
#: | **0,86** | **536** | **18** | **108** | **31** |
#: | 0,90 | 335 | 12 | 37 | 9 |
#:
#: **Der größte Cluster ist der Präzisionstest.** Single linkage kettet: Unter
#: 0,82 wächst alles zu einem Klumpen zusammen — 2.607 „Ideen" in einer Menge
#: sind keine Idee mehr. Bei 0,86 ist der größte 18 Papiere groß und heißt
#: „Sportförderrichtlinien anpassen"; bei 0,90 zerfallen die Ketten, die
#: gerade das Interessante sind (die Verpackungssteuer läuft über fünf Städte
#: mit fünf verschiedenen Formulierungen).
#:
#: Höher als die 0,70 der Papier-Nachbarschaft, weil die Texte kürzer und
#: gleichförmiger sind: Zwei ganze Vorlagen erreichen 0,86 fast nie, zwei
#: Instrument-Sätze schon.
IDEA_THRESHOLD = 0.86

#: Kleiner als das ist kein Cluster, sondern ein Papier. Sie werden gar nicht
#: erst gespeichert — sonst stünden 5.000 Einzelmengen in der Tabelle und
#: jede Auswertung müsste sie wieder wegfiltern.
MIN_MITGLIEDER = 2


def idea_text(classification: dict) -> str:
    """Die Idee als Text — Instrument und Zusammenfassung, sonst nichts.

    Kein Titel, keine Stadt, kein Datum: Genau die trennen zwei Städte, die
    dasselbe tun.
    """
    instrument = (classification.get("instrument") or "").strip()
    if not instrument:
        return ""
    zusammenfassung = (classification.get("summary") or "").strip()
    return f"{instrument}. {zusammenfassung}".strip()


def embed_ideas(main: CitiesStore, model: str = EMBED_MODEL,
                batch: int = 256) -> int:
    """Ein Vektor je übertragbarer Idee — Oldenburg eingeschlossen.

    Übersprungen wird, was schon einen Vektor mit demselben Quell-Hash hat:
    Ändert die Einordnung ihr Instrument, wird neu gerechnet, sonst nicht.
    """
    from council.cities.index import _embed

    einordnung = main.annotations_for("classify", "2")
    bekannt = main.object_embedding_hashes(model, IDEA_KIND)
    offen: list[tuple[str, str, str]] = []
    for p in main.papers():
        klasse = einordnung.get(p["id"]) or {}
        if klasse.get("transfer") not in USABLE:
            continue
        text = idea_text(klasse)
        if not text:
            continue
        h = text_hash(text)
        if bekannt.get(p["id"]) == h:
            continue
        offen.append((p["id"], text, h))

    if not offen:
        return 0
    logger.info("%s Ideen einzubetten", len(offen))
    n = 0
    for start in range(0, len(offen), batch):
        block = offen[start:start + batch]
        vektoren = _embed([t for _id, t, _h in block])
        with main.transaction():
            for i, (kennung, _text, h) in enumerate(block):
                main.put_object_embedding(IDEA_KIND, kennung, model, h,
                                          vektoren[i].tobytes())
        n += len(block)
    return n


def _gruppen(naehe: np.ndarray, schwelle: float) -> list[list[int]]:
    """Zusammenhangskomponenten über der Schwelle — Union-Find.

    **Bewusst single linkage, nicht average.** Eine Idee wandert manchmal über
    eine Kette: Osnabrücks „Mehrwegsystem erproben" liegt nah an Münsters
    „Mehrwegpfand einführen", das nah an Potsdams „Verpackungssteuer prüfen"
    liegt — die beiden Enden aber nicht aneinander. Average linkage zerschnitte
    diese Kette; genau sie ist aber die Idee, die durch die Republik läuft.

    Der Preis ist bekannt und wird gemessen: Bei zu niedriger Schwelle wächst
    alles zu einem Riesencluster zusammen. Deshalb steht in
    ``scripts/cities_cluster_bericht.py`` die Größe des größten Clusters als
    Kennzahl neben der Trefferquote.
    """
    n = naehe.shape[0]
    eltern = list(range(n))

    def wurzel(x: int) -> int:
        while eltern[x] != x:
            eltern[x] = eltern[eltern[x]]
            x = eltern[x]
        return x

    import numpy as np_

    for i in range(n):
        # Nur die obere Dreiecksmatrix: (i,j) und (j,i) sind dieselbe Kante.
        nachbarn = np_.nonzero(naehe[i, i + 1:] >= schwelle)[0]
        for versatz in nachbarn:
            j = i + 1 + int(versatz)
            wi, wj = wurzel(i), wurzel(j)
            if wi != wj:
                eltern[wj] = wi

    gruppen: dict[int, list[int]] = {}
    for i in range(n):
        gruppen.setdefault(wurzel(i), []).append(i)
    return [g for g in gruppen.values() if len(g) >= MIN_MITGLIEDER]


def build_clusters(main: CitiesStore, model: str = EMBED_MODEL,
                   threshold: float = IDEA_THRESHOLD,
                   version: str = CLUSTER_VERSION) -> dict:
    """Ideen zu Clustern zusammenfassen und die Fassung ersetzen.

    **Einfach-Verknüpfung, und das bleibt so — gemessen.** Sie kettet: Cluster 1
    hat 72 Mitglieder von Sportstättensanierung über Baudenkmäler bis
    Spielstraßen (Kohäsion 0,79 gegen 0,91 im Median). Der naheliegende Fix —
    innerhalb jeder Kette streng nachclustern, mittlere oder vollständige
    Verknüpfung, ohne neue Schwelle — zerlegt ihn (72 → 6). Aber genauso die
    GUTEN großen Gruppen: Wärmeplanung 33 → 13, Verpackungssteuer 25 → 14,
    Parkgebühren 50 → 8; 247 von 1.180 Gruppen zerfielen (10.09.2026). Das
    Signal „in fünf Städten", der Kern des Features, bräche überall weg. Ein
    verketteter Cluster (3 % der Dubletten) ist der Preis für 246 richtige.
    Wer das anfasst, misst vorher die drei Genannten.

    Der Wert je Zeile ist die Nähe zum Cluster-Mittel — damit eine Oberfläche
    das typischste Mitglied zuerst zeigen kann und nicht das zufällig erste.
    """
    import numpy as np

    kennungen, hashes, roh = main.object_embeddings(model, IDEA_KIND)
    if len(kennungen) < MIN_MITGLIEDER:
        return {"ideas": len(kennungen), "clusters": 0, "members": 0}
    matrix = np.frombuffer(roh, dtype=np.float32).reshape(len(kennungen), -1)
    logger.info("%s Ideen, %s Dimensionen — Nähe rechnen", *matrix.shape)
    naehe = matrix @ matrix.T

    gruppen = _gruppen(naehe, threshold)
    logger.info("%s Cluster mit mindestens %s Mitgliedern", len(gruppen), MIN_MITGLIEDER)

    zeilen: list[tuple[str, str, int, str, float]] = []
    for cluster_id, gruppe in enumerate(sorted(gruppen, key=len, reverse=True), 1):
        mitte = matrix[gruppe].mean(axis=0)
        norm = float(np.linalg.norm(mitte)) or 1.0
        for i in gruppe:
            zeilen.append((model, version, cluster_id, kennungen[i],
                           float(matrix[i] @ mitte / norm)))
    main.replace_idea_clusters(model, version, zeilen)
    groesse = max((len(g) for g in gruppen), default=0)
    return {"ideas": len(kennungen), "clusters": len(gruppen),
            "members": len(zeilen), "largest": groesse}


def run(main: CitiesStore, model: str = EMBED_MODEL) -> dict:
    """Alle fünf Schritte — für den Wochen-Cron und den Backfill.

    Der Prüflauf gehört dazu und nicht daneben: Eine frisch gerechnete Gruppe
    ist ungeprüft, und ungeprüft steht sie auf der Karte als „auch in vier
    anderen Städten". Er kostet 0,3 $ über den ganzen Bestand und läuft nur
    für Gruppen, die noch kein Urteil haben.
    """
    eingebettet = embed_ideas(main, model)
    zahlen = build_clusters(main, model)
    zahlen["embedded"] = eingebettet
    for name, wert in check_clusters(main, model).items():
        zahlen[f"check_{name}"] = wert
    # Vierter Schritt, seit 10.09.2026: die Haltung je Vorlage. Sie hing bis
    # dahin an einem Handaufruf — der Cron hätte neue Vorlagen gruppiert und
    # geprüft, aber nie gefragt, ob der Rat die Sache wollte. Auf der Karte
    # stünde dann für alles Neue keine Zeile „In den anderen Räten".
    for name, wert in stance_all(main, model).items():
        zahlen[f"stance_{name}"] = wert
    # Fünfter Schritt (10.09.2026): der Mehrheits-Status je Stadt und Gruppe.
    # Er MUSS nach dem Gruppieren laufen und nach jedem `fit`-Lauf noch
    # einmal — `check_cities.py` ruft ihn deshalb auch dort.
    from council.cities.annotators import get as get_annotator
    zahlen["group_status"] = main.rebuild_group_status(
        model, CLUSTER_VERSION, get_annotator("fit").version)
    return zahlen


#: Ab wie vielen STÄDTEN eine Gruppe nach der Richtung gefragt wird. Bei zwei
#: Städten trägt die Angabe wenig — die Karte zeigt sie erst ab zwei ANDEREN
#: Räten, und dort ist die Gegenrichtung der interessante Fall.
STANCE_AB_STAEDTEN = 3

#: Wie viele Richtungs-Urteile gleichzeitig unterwegs sind. Dieselbe Lehre wie
#: bei `fit`: Die Arbeiter rufen das Modell, geschrieben wird im Hauptthread.
STANCE_WORKERS = int(os.environ.get("CITIES_STANCE_WORKERS", "12"))


def stance_all(main: CitiesStore, model: str = EMBED_MODEL,
               version: str = CLUSTER_VERSION, limit: int | None = None,
               workers: int = 0) -> dict:
    """Wohin will jede Vorlage die gemeinsame Sache ihrer Gruppe bewegen?

    **Warum das nicht in ``annotate.py`` läuft.** Der übliche Lauf fragt
    Batches von Vorlagen nach einem Etikett, das nur an ihnen selbst hängt.
    Die Richtung hängt am LABEL DER GRUPPE — „Straßenausbaubeiträge
    abschaffen" ist ``introduce``, wenn die Gruppe genau das will, und
    ``stop``, wenn sie das Gegenteil will. Sechs Vorlagen aus sechs Gruppen
    in einem Aufruf hieße sechs Bezugspunkte.

    Gefragt werden nur Gruppen ab ``STANCE_AB_STAEDTEN`` Städten, und nur
    solche mit einem Label aus ``cluster_check`` — ohne Bezugspunkt gibt es
    keine Richtung. Gemessen am 09.09.2026: 81 Gruppen, 838 Vorlagen.
    """
    import threading
    from concurrent.futures import ThreadPoolExecutor

    from council.cities.annotate import parse_json
    from council.cities.annotators import get as get_annotator
    from kern import llm, prompts

    ann = get_annotator("stance")
    gruppen = _gruppen_mit_mitgliedern(main, version)
    einordnung = main.annotations_for("classify", "2")
    auftraege: list[tuple[str, dict]] = []
    for cid, mitglieder in gruppen.items():
        if len({m["body_id"] for m in mitglieder}) < STANCE_AB_STAEDTEN:
            continue
        pruefung = main.annotation("cluster", f"{version}:{cid}",
                                   "cluster_check", "1")
        raus = set(((pruefung or {}).get("payload") or {}).get("drop") or [])
        bleibt = [m for m in mitglieder if m["paper_id"] not in raus]
        gruppe = _gruppen_text(bleibt, einordnung)
        if not gruppe:
            continue
        for m in bleibt:
            if main.annotation("paper", m["paper_id"], ann.key, ann.version):
                continue
            auftraege.append((gruppe, m))
    if limit:
        auftraege = auftraege[:limit]
    stand = {"annotated": 0, "errors": 0, "cost_usd": 0.0, "seconds": 0}
    if not auftraege:
        return stand

    logger.info("stance: %s Vorlagen in %s Gruppen", len(auftraege),
                len({m["cluster_id"] for _, m in auftraege}))
    system = prompts.get(ann.prompt_system)
    sperre = threading.Lock()
    t0 = time.time()

    def eine(auftrag: tuple[str, dict]):
        gruppe, m = auftrag
        klasse = einordnung.get(m["paper_id"]) or {}
        text = (f"Stadt: {m['body_id']}\n"
                f"Datum: {(m.get('date') or '')[:10]}\n"
                f"Titel: {m.get('name') or ''}\n"
                f"Instrument: {klasse.get('instrument') or ''}\n"
                f"Zusammenfassung: {klasse.get('summary') or ''}")
        try:
            antwort = llm.chat_complete(
                model=ann.model, response_format={"type": "json_object"},
                messages=[{"role": "system", "content": system},
                          {"role": "user", "content": prompts.render(
                              ann.prompt_user, gruppe=gruppe,
                              paper=text[:ann.input_chars * 4])}],
                max_tokens=ann.max_tokens, temperature=ann.temperature,
                extra_body={"provider": {}} if ann.routing_free else {},
                _feature=ann.feature)
            nutzlast = ann.payload.model_validate(
                parse_json(antwort.choices[0].message.content or ""))
        except Exception as e:  # noqa: BLE001 — eine Vorlage, nicht der Lauf
            with sperre:
                stand["errors"] += 1
            logger.info("stance gescheitert (%s): %s", m["paper_id"], type(e).__name__)
            return None
        verbrauch = getattr(antwort, "usage", None)
        kosten = float(getattr(verbrauch, "cost", 0) or 0) if verbrauch else 0.0
        return m["paper_id"], nutzlast.model_dump(), text_hash(gruppe + text), kosten

    # Geschrieben wird nur im Hauptthread (`council/cities/fit.py` erklärt,
    # warum: eine SQLite-Verbindung gehört dem Thread, der sie geöffnet hat).
    with ThreadPoolExecutor(workers or STANCE_WORKERS) as pool:
        puffer = []
        for ergebnis in pool.map(eine, auftraege):
            if ergebnis is None:
                continue
            puffer.append(ergebnis)
            stand["cost_usd"] += ergebnis[3]
            if len(puffer) >= 25:
                _stance_schreiben(main, ann, puffer)
                stand["annotated"] += len(puffer)
                puffer = []
        if puffer:
            _stance_schreiben(main, ann, puffer)
            stand["annotated"] += len(puffer)
    stand["seconds"] = round(time.time() - t0)
    logger.info("stance fertig: %s Urteile, %s Fehler, $%.4f, %ss",
                stand["annotated"], stand["errors"], stand["cost_usd"],
                stand["seconds"])
    return stand


def _gruppen_text(mitglieder: list[dict], einordnung: dict) -> str:
    """Die Gruppe als Liste ihrer Instrumente — der Bezugspunkt der Richtung.

    **Warum nicht das Label aus ``cluster_check``.** Es ist nicht verlässlich:
    Gemessen am 09.09.2026 trug Cluster 10 — achtzehn Mitglieder, alle
    „Straßenausbaubeiträge abschaffen", so homogen wie eine Gruppe nur sein
    kann — das Label „Integrationsfonds und -budget". Ein falscher
    Bezugspunkt macht die Richtungsfrage wertlos, und zwar unbemerkt: Die
    Antwort sieht dann genauso aus wie eine richtige.

    Die Mitglieder selbst sind die Wahrheit. Doppelte Instrumente fallen
    weg — dieselbe Formulierung fünfmal sagt nicht mehr als einmal, kostet
    aber Platz, den die übrigen Städte brauchen.
    """
    gesehen: list[str] = []
    for m in mitglieder:
        instr = ((einordnung.get(m["paper_id"]) or {}).get("instrument")
                 or m.get("name") or "").strip()
        if instr and instr not in gesehen:
            gesehen.append(instr)
        if len(gesehen) >= 8:
            break
    return "\n".join(f"- {x}" for x in gesehen)


def _stance_schreiben(main: CitiesStore, ann, puffer: list) -> None:
    with main.transaction():
        for kennung, nutzlast, quelle, kosten in puffer:
            main.put_annotation("paper", kennung, ann.key, ann.version,
                                nutzlast, quelle, model=ann.model,
                                cost_usd=kosten)


#: Ab dieser Größe wird eine Gruppe geprüft. Zwei Mitglieder können nicht
#: verkettet sein — sie wurden direkt miteinander verglichen.
CHECK_AB_MITGLIEDERN = 3


def check_clusters(main: CitiesStore, model: str = EMBED_MODEL,
                   version: str = CLUSTER_VERSION,
                   limit: int | None = None) -> dict:
    """Jede Gruppe ab drei Mitgliedern einmal gegenlesen lassen.

    **Warum überhaupt.** Die Gruppierung kettet (single linkage): Hält sie A
    und B für dieselbe Idee und B und C auch, landen A und C in einer Menge,
    ohne je verglichen worden zu sein. Gemessen an acht Stichproben
    (09.09.2026) war einer von acht Clustern so entstanden — er mischte
    „Lärmaktionsplan evaluieren" mit „Tempo-30-Anordnung prüfen". Eine höhere
    Schwelle behebt das nicht, sie zerreißt die Ketten, die den Wert
    ausmachen: Die Verpackungssteuer läuft über fünf Städte mit fünf
    Formulierungen.

    **Warum gerade jetzt.** Bis PR 22 war ein falscher Cluster eine Zahl in
    einem Bericht. Seitdem steht auf der Karte „auch in 4 anderen Städten" —
    ein falscher Cluster ist damit eine falsche öffentliche Aussage.

    **Was geschrieben wird und was nicht.** Die Gruppierung selbst bleibt
    unangetastet; das Urteil steht als Annotation daneben
    (``object_kind='cluster'``, Kennung ``<version>:<cluster_id>``). Schicht 1
    trägt keine Meinung — dieselbe Regel wie überall hier, und sie zahlt sich
    aus: Wer wissen will, warum ein Papier nicht mehr mitzählt, sieht beides
    nebeneinander.
    """
    from council.cities.annotate import parse_json
    from council.cities.annotators import get as get_annotator
    from kern import llm, prompts

    ann = get_annotator("cluster_check")
    gruppen = _gruppen_mit_mitgliedern(main, version)
    offen = [(cid, m) for cid, m in gruppen.items()
             if len(m) >= CHECK_AB_MITGLIEDERN
             and main.annotation("cluster", f"{version}:{cid}", ann.key, ann.version) is None]
    if limit:
        offen = offen[:limit]
    stand = {"checked": 0, "dropped": 0, "clusters_touched": 0,
             "zu_viel": 0, "errors": 0, "cost_usd": 0.0}
    if not offen:
        return stand

    logger.info("cluster_check: %s Gruppen zu prüfen", len(offen))
    system = prompts.get(ann.prompt_system)
    for cid, mitglieder in offen:
        zeilen = "\n".join(
            f"- {m['paper_id']} ({m['body_id']}, {(m.get('date') or '')[:7]}): "
            f"{m.get('instrument') or m.get('name') or ''}"
            for m in mitglieder)
        try:
            antwort = llm.chat_complete(
                model=ann.model, response_format={"type": "json_object"},
                messages=[{"role": "system", "content": system},
                          {"role": "user", "content": prompts.render(
                              ann.prompt_user, items=zeilen[:ann.input_chars * 4])}],
                max_tokens=ann.max_tokens, temperature=ann.temperature,
                extra_body={"provider": {}} if ann.routing_free else {},
                _feature=ann.feature)
            nutzlast = ann.payload.model_validate(
                parse_json(antwort.choices[0].message.content or ""))
        except Exception as e:  # noqa: BLE001 — eine Gruppe, nicht der Lauf
            stand["errors"] += 1
            logger.info("cluster_check gescheitert (%s): %s", cid, type(e).__name__)
            continue

        # Erfundene Kennungen fliegen raus — dieselbe Regel wie bei `fit`:
        # Was dem Modell nicht vorlag, kann es nicht entfernen.
        erlaubt = {m["paper_id"] for m in mitglieder}
        raus = [k for k in getattr(nutzlast, "drop", []) if k in erlaubt]
        # HÖCHSTENS EIN DRITTEL. Gemessen am ersten Lauf (09.09.2026) war das
        # die entscheidende Sicherung: Das Modell wählte für eine Gruppe das
        # zu enge Label „Klimaschutz-Berichtswesen" und warf danach 9 von 16
        # Mitgliedern hinaus — jedes, das „Konzept" oder „Maßnahmenplan" hieß,
        # obwohl das dieselbe Sache in einer anderen Stufe ist.
        #
        # Wer mehr als ein Drittel entfernen will, hat nicht die Gruppe
        # geputzt, sondern sie neu definiert. Das ist kein Putzen mehr, und
        # dann bleibt sie lieber, wie sie ist: Ein zu Unrecht entferntes
        # Mitglied nimmt einer Idee eine Stadt und macht die Aussage „auch in
        # vier anderen Städten" falsch.
        if len(raus) > len(mitglieder) // 3:
            logger.info("cluster_check: %s wollte %s von %s entfernen — zu viel, "
                        "die Gruppe bleibt", cid, len(raus), len(mitglieder))
            stand["zu_viel"] = stand.get("zu_viel", 0) + 1
            raus = []
        nutzlast = nutzlast.model_copy(update={"drop": raus})

        verbrauch = getattr(antwort, "usage", None)
        kosten = float(getattr(verbrauch, "cost", 0) or 0) if verbrauch else 0.0
        main.put_annotation("cluster", f"{version}:{cid}", ann.key, ann.version,
                            nutzlast.model_dump(), text_hash(zeilen),
                            model=ann.model, cost_usd=kosten)
        stand["checked"] += 1
        stand["cost_usd"] += kosten
        if raus:
            stand["dropped"] += len(raus)
            stand["clusters_touched"] += 1
    logger.info("cluster_check: %s geprüft, %s Mitglieder aus %s Gruppen entfernt, $%.4f",
                stand["checked"], stand["dropped"], stand["clusters_touched"],
                stand["cost_usd"])
    return stand


def _gruppen_mit_mitgliedern(main: CitiesStore, version: str) -> dict[int, list[dict]]:
    """Cluster-Id → Mitglieder mit Stadt, Datum und Instrument."""
    gruppen: dict[int, list[dict]] = {}
    for zeile in main.cluster_members(version):
        gruppen.setdefault(zeile["cluster_id"], []).append(zeile)
    return gruppen


# ---------------------------------------------------------------------------
# Was hier ABSICHTLICH fehlt
# ---------------------------------------------------------------------------
#
# **Kein Modell benennt die Cluster.** Der Plan sah dafür einen Annotator
# `cluster_label` vor. Beim Bauen zeigte sich, dass die Bezeichnung längst da
# ist: Das Instrument des typischsten Mitglieds — jenes mit der größten Nähe
# zum Cluster-Mittel — ist der Name, den die Daten selbst vergeben.
# „Verpackungssteuersatzung einführen" über fünf Städte, „Tempo-30-Zonen an
# Schulwegen" über drei: Beides sind Zeilen aus der Einordnung, kein zweites
# Modell nötig.
#
# Was ein Modell besser könnte: Ein Cluster, dessen Mitglieder die Sache sehr
# verschieden nennen, bekäme einen Namen, den keine der Städte so schreibt.
# Das ist ein echter, aber kleiner Gewinn — und er kostet einen Prompt, ein
# Golden Set und einen `annotations_missing`-Zweig für `object_kind='cluster'`.
# Lesen sich die Namen im Betrieb schlecht, ist das der Ort, an dem es
# nachzuholen ist.
