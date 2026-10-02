"""Grundakten: je Vorgang eine Gruppe aus allem, was eindeutig zusammengehört.

Plan „Akte“ (``docs/plan-akte.md``), Phase 1. Eine Frage an „Frag den Rat“
betrifft fast immer einen Vorgang über Jahre — Antrag, Vorberatung,
Ratsbeschluss, Bericht, Protokollnotiz. Die Suche nach ähnlichem Text findet
davon nur, was der Frage ähnlich KLINGT: Die Aussage der Verwaltung zum
Schlossplatz-Spielplatz stand unter dem TOP „Spielleitplanung“ und lag auf
Vektor-Rang 310 (Gold-Test 01.10.2026). Eine Grundakte hält fest, was
zusammengehört, unabhängig davon, wie es klingt.

**Ohne Sprachmodell, nur über harte Schlüssel:**

1. **Vorlagennummer** — ``26/0396``, ``26/0396/1`` und ``26/0396/12`` sind
   eine Akte. Dazu gehören die Beschlüsse aller Gremien, die Beratungsfolge
   (``council_deliberations`` über ``kvonr``), die Tagesordnungspunkte und
   der Vorlagen-Text.
2. **Titelkern** — Anträge ohne Vorlagennummer („Antrag der Fraktion BSW:
   …“, „… (SPD-Fraktion vom 17.03.2026) - Bericht“). Antrag und Bericht
   tragen denselben Kern und landen zusammen. Trägt ein nummerierter
   Beschluss denselben Kern, geht der unnummerierte in dessen Akte.
3. **Teilabstimmungen** gehören zum Beschluss ihres TOPs (``parent_item``).
4. **Wortbeiträge und Protokollnotizen** über Sitzung und TOP an ihren
   Beschluss — dieselbe Regel wie ``wortbeitraege_zu_beschluessen``, einmal
   beim Aufbau statt bei jeder Frage, und ohne Deckel.
5. **Verweise** einer Vorlage auf eine andere werden als KANTE gespeichert,
   nicht zusammengelegt: „vgl. 22/1006“ kann Fortsetzung oder Seitenblick
   sein. Zusammenlegen ist Sache der Projekt-Entitäten (Phase 2).

Was nichts Eigenes ist — Formal-TOPs (Beschlussfähigkeit, Protokoll,
Einwohnerfragestunde), Sammel-TOPs der Wortbeiträge — bekommt keine Akte.

Die Grundakte ist **abgeleitet**: :func:`build` rechnet sie vollständig aus
den Rohdaten neu, schnell genug für jeden Ernte-Lauf (Grundakten rund eine
Sekunde, Entitäten und Erwähnungen rund 20 Sekunden — Phase 2). Die ``key``-Spalte ist
über Neuaufbauten stabil, damit es die ids auch sind.
"""
from __future__ import annotations

import logging
import re
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from collections.abc import Callable
from typing import Any

log = logging.getLogger("council.matters")

_VORLAGE = re.compile(r"\d{2}/\d{4}")
#: „(SPD-Fraktion vom 17.03.2026)“, „(Ratsherr Sander vom 22.08.2023)“
_ANTRAG = re.compile(r"\(([^()]*?)\s+vom\s+(\d{1,2})\.(\d{1,2})\.(\d{2,4})\)")
#: Zusätze, unter denen derselbe Punkt in verschiedenen Gremien läuft.
_ZUSATZ = re.compile(
    r"\s*[-–]\s*(antrag mit bericht der verwaltung|antrag mit bericht|bericht der verwaltung|"
    r"sachstandsbericht|bericht|beschluss|antrag|vorlage|sachstand)\s*$", re.IGNORECASE)
#: Wörter, die einen Titel nicht unterscheiden. Bleibt nach ihrem Abzug kein
#: Wort mit mindestens sechs Buchstaben übrig, ist der Titel zu allgemein für
#: einen Schlüssel („Bericht der Verwaltung“ wäre sonst EINE Akte über Jahre).
_ALLGEMEIN = {
    "antrag", "anträge", "antraege", "bericht", "berichte", "verwaltung", "sachstand",
    "sachstandsbericht", "mündlicher", "muendlicher", "aktuellen", "aktueller", "stand",
    "fraktion", "fraktionen", "gruppe", "stadt", "oldenburg", "beschluss", "vorlage",
    "information", "informationen", "anfrage", "anfragen", "mitteilung", "mitteilungen",
    "änderungsantrag", "aenderungsantrag", "ergänzungsantrag", "ergaenzungsantrag",
    "vorstellung", "planungen", "planung", "allgemeine", "angelegenheiten",
}
#: Zwei-Buchstaben-Präfix der Tagesordnung („Ö 7.5“, „N 3“) und Schmuck um die Nummer.
_TOP_NR = re.compile(r"^\s*(?:[öÖnN]\.?\s*)?(\d+(?:\.\d+)*)")


def vorlagen_basen(nr: str | None) -> list[str]:
    """„26/0396/1“ → ["26/0396"]; „26/0001, 26/0002“ → beide; leer → []."""
    return list(dict.fromkeys(_VORLAGE.findall(nr or "")))


def top_nummer(text: str | None) -> str:
    """„Ö 7.5“ / „7.5“ / „7.5 Titel“ → „7.5“; ohne Nummer leer."""
    m = _TOP_NR.match(text or "")
    return m.group(1) if m else ""


def titelkern(titel: str | None) -> str:
    """Der Teil eines Titels, der über Gremien und Zusätze gleich bleibt.

    Antragsteller und Datum („(SPD-Fraktion vom 17.03.2026)“) bleiben als
    Unterscheidung erhalten — zwei Anträge derselben Fraktion am selben Tag
    haben verschiedene Kerne, derselbe Antrag in zwei Gremien denselben. Leer,
    wenn der Titel zu allgemein ist.
    """
    t = " ".join((titel or "").split())
    antrag = _ANTRAG.search(t)
    zusatz = ""
    if antrag:
        jahr = antrag.group(4) if len(antrag.group(4)) == 4 else "20" + antrag.group(4)
        zusatz = (f"|{_norm(antrag.group(1))}"
                  f"|{jahr}-{int(antrag.group(3)):02d}-{int(antrag.group(2)):02d}")
        t = (t[:antrag.start()] + t[antrag.end():]).strip()
    for _ in range(2):  # „… - Antrag mit Bericht - Beschluss“
        t = _ZUSATZ.sub("", t).strip()
    # „Antrag der Fraktion X: Kern“ — Antragsteller vor dem Doppelpunkt ist
    # Rahmen, der Kern steht dahinter.
    if ":" in t and re.match(r"(?i)\s*(änderungs|ergänzungs)?antrag\b", t):
        vorn, _, hinten = t.partition(":")
        zusatz = zusatz or f"|{_norm(vorn)}"
        t = hinten
    kern = _norm(t)
    tragend = [w for w in kern.split() if len(w) >= 6 and w not in _ALLGEMEIN]
    return f"{kern}{zusatz}" if tragend else ""


def _norm(text: str) -> str:
    t = text.lower().replace("ß", "ss")
    return " ".join(re.sub(r"[^0-9a-zäöü]+", " ", t).split())


@dataclass
class _Aufbau:
    """Zwischenstand eines Aufbaus: Schlüssel je Zeile, Titel und Daten je Schlüssel."""
    zuordnung: dict[tuple[str, int], tuple[str, str]] = field(default_factory=dict)
    titel: dict[str, str] = field(default_factory=dict)
    daten: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))
    kanten: set[tuple[str, str, str]] = field(default_factory=set)

    def setze(self, art: str, item_id: int, key: str, quelle: str, datum: str | None = None,
              titel: str | None = None) -> None:
        self.zuordnung[(art, item_id)] = (key, quelle)
        if datum:
            self.daten[key].append(str(datum)[:10])
        if titel and key not in self.titel:
            self.titel[key] = titel


def _art_von(key: str) -> str:
    return {"v": "template", "t": "motion"}.get(key[:1], "single")


def zuordnen(store: Any, stopp: Callable[[], bool] | None = None) -> _Aufbau:
    """Rechnet die Zuordnung aus den Rohdaten — schreibt nichts."""
    a = _Aufbau()
    from council.store_sitzungen import SitzungenMixin
    formalie = SitzungenMixin._FORMALIE_RE

    # 1. Vorlagen: Text, Titel, Verweise.
    kvonr_basis: dict[int, str] = {}
    for kvonr, nr, titel, text in store.matter_templates():
        basen = vorlagen_basen(nr)
        if not basen:
            continue
        key = f"v:{basen[0]}"
        kvonr_basis[kvonr] = basen[0]
        a.setze("template", kvonr, key, "template_number", titel=titel)
        for anderer in vorlagen_basen(text):
            if anderer != basen[0]:
                a.kanten.add((key, f"v:{anderer}", "reference"))

    # 2. Beschlüsse — Titelkern nummerierter Beschlüsse merken, damit der
    # unnummerierte Antrag in die Akte seiner Vorlage findet.
    beschluesse = store.matter_decisions()
    kern_zu_vorlage: dict[str, set[str]] = defaultdict(set)
    for did, _ks, _nr, titel, vnr, kind, _p, _dat in beschluesse:
        basen = vorlagen_basen(vnr)
        kern = titelkern(titel)
        if basen and kern and kind != "subvote":
            kern_zu_vorlage[kern].add(basen[0])
    top_key: dict[tuple[int, str], str] = {}  # (ksinr, TOP-Nummer) → Akte
    for did, ksinr, nr, titel, vnr, kind, _p, datum in beschluesse:
        if kind == "subvote":
            continue
        basen = vorlagen_basen(vnr)
        kern = titelkern(titel)
        if basen:
            key, quelle = f"v:{basen[0]}", "template_number"
            for weitere in basen[1:]:
                a.kanten.add((key, f"v:{weitere}", "multi_number"))
        elif kern and len(kern_zu_vorlage.get(kern, ())) == 1:
            key, quelle = f"v:{next(iter(kern_zu_vorlage[kern]))}", "title"
        elif kern:
            key, quelle = f"t:{kern}", "title"
        else:
            key, quelle = f"d:{did}", "single"
        a.setze("decision", did, key, quelle, datum, titel)
        if top_nummer(nr):
            top_key.setdefault((ksinr, top_nummer(nr)), key)
    for did, ksinr, _nr, titel, _vnr, kind, parent, datum in beschluesse:
        if kind != "subvote":
            continue
        key = top_key.get((ksinr, top_nummer(parent))) or f"d:{did}"
        a.setze("decision", did, key, "parent_item" if key[:2] != "d:" else "single", datum, titel)
    if stopp and stopp():
        return a

    # 3. Beratungsfolge: jede Station hängt über kvonr an ihrer Vorlage.
    for bid, kvonr, datum in store.matter_deliberations():
        basis = kvonr_basis.get(kvonr)
        if basis:
            a.setze("deliberation", bid, f"v:{basis}", "template_number", datum)

    # 4. Tagesordnungspunkte (ohne Formalien).
    for gid, ksinr, nr, titel, vnr, kvonr, datum in store.matter_agenda_items():
        basen = vorlagen_basen(vnr) or ([kvonr_basis[kvonr]] if kvonr in kvonr_basis else [])
        if basen:
            a.setze("agenda_item", gid, f"v:{basen[0]}", "template_number", datum, titel)
            continue
        if formalie.search(titel or ""):
            continue
        key = top_key.get((ksinr, top_nummer(nr)))
        if key:
            a.setze("agenda_item", gid, key, "top", datum, titel)
            continue
        kern = titelkern(titel)
        if kern and len(kern_zu_vorlage.get(kern, ())) == 1:
            a.setze("agenda_item", gid, f"v:{next(iter(kern_zu_vorlage[kern]))}", "title", datum, titel)
        elif kern:
            a.setze("agenda_item", gid, f"t:{kern}", "title", datum, titel)
        else:
            a.setze("agenda_item", gid, f"g:{gid}", "single", datum, titel)
    if stopp and stopp():
        return a

    # 5. Wortbeiträge über Sitzung + TOP an ihren Beschluss.
    nach_sitzung: dict[int, list[int]] = defaultdict(list)
    for did, ksinr, *_ in beschluesse:
        nach_sitzung[ksinr].append(did)
    sitzungen = sorted(nach_sitzung)
    for i in range(0, len(sitzungen), 100):
        ids = [d for ks in sitzungen[i:i + 100] for d in nach_sitzung[ks]]
        decs = store.get_decisions_by_ids(ids)
        for w in store.wortbeitraege_zu_beschluessen(decs, max_gesamt=10**9, max_je_top=10**9):
            ziel = a.zuordnung.get(("decision", w["zu_beschluss"]))
            if ziel:
                a.setze("speech", w["id"], ziel[0], "top")
        if stopp and stopp():
            return a
    return a


# --------------------------------------------------------------------------- #
# Phase 2: Themen-Entitäten über Grundakten
# --------------------------------------------------------------------------- #
#
# Eine Grundakte ist EINE Vorlage; ein Vorgang wie das Stadion besteht aus
# vielen. Verklebt werden sie über die Themen-Entitäten — und zwar über die
# Grundakte, nicht über den einzelnen Beschluss: Hängt „Stadionneubau“ an einem
# Ausschussbeschluss, gehört die ganze Vorlage samt Ratsbeschluss dazu.
#
# Dazu kommen ERWÄHNUNGEN: Wortbeiträge und Pressemitteilungen, die den Namen
# einer Entität nennen. Nur so kommt die Aussage der Verwaltung zum
# Schlossplatz-Spielplatz in die Akte — sie steht unter TOP „Spielleitplanung“,
# einem anderen Vorgang. Gemessen am Gold-Set (eval/run_akten.py, 02.10.2026):
# Grundakte allein 55,7 % der Belege ohne Presse, mit Entitäten und
# Erwähnungen 90,8 %; Presse 0/34 → 24/34.

#: Kürzere Namen treffen zu viel („Markt“ in „Marktplatz“, „Rat“ überall).
NAME_MIN = 5
#: Gremien sind Organisationen, aber kein Thema: Ein Beitrag, der den
#: Schulausschuss nennt, handelt nicht vom Schulausschuss.
_GREMIUM = re.compile(r"(?i)(ausschuss\b|^rat$|^rat der stadt|^(stadt)?verwaltung$|ortsrat\b|"
                      r"^integration$)")
#: Ein EINWORT-Name, der in mehr Wortbeiträgen steht, ist ein Allerweltswort
#: oder ein Stadtteil-Rauschen („Innenstadt“ 627, „Markt“ 304, „Fliegerhorst“
#: 373). Mehrwort-Namen („Stadion Oldenburg“) bleiben: Sie sind lang genug, um
#: zu treffen, was sie meinen.
ALLGEMEIN_BEITRAEGE = 200
#: Von einer Pressemitteilung zählen Titel und Anfang. Der Fuß nennt Ort und
#: Zeit — „Kulturzentrum PFL, Peterstraße 3“ stand in 322 Mitteilungen und
#: hängte jede Ratseinladung an die Peterstraße. Mit Fuß 38 Mitteilungen je
#: Akte, ohne 10, bei 24 statt 26 Gold-Belegen.
PRESSE_ANFANG = 600
#: Ein Ort mit mehr verknüpften Beschlüssen ist ein Stadtteil, kein Vorgang
#: („Fliegerhorst“ 185): Er verklebt keine Akten. Gemessen: Abdeckung gleich,
#: mittlere Akte 62 → 28 Beschlüsse (60 und 100 messen gleich).
ORT_KLEBT_BIS = 60
#: Haushalts-Vorlagen BÜNDELN: 22/0025 trägt Haushalt, Wirtschaftspläne der
#: Eigenbetriebe und Stiftungshaushalte in einer Vorlage. Erbte eine Entität
#: die ganze Akte, hinge der Abfallwirtschaftsbetrieb an der Klävemann-Stiftung
#: (Stichprobe B7, 02.10.2026: 5 von 30 Vererbungen). Dasselbe beim
#: Stellenplan (der Hafen erbte „Stellenplan 2020“). Als Einstieg bleiben sie
#: erreichbar, nur verklebt wird über sie nicht.
_SAMMELAKTE = re.compile(r"(?i)^\s*(haushalt|stellenplan)")

_NICHT_DAVOR = r"(?<![0-9A-Za-zÄÖÜäöüß])"
_NICHT_DAHINTER = r"(?![0-9A-Za-zÄÖÜäöüß])"


def _namensmuster(namen: list[str]) -> re.Pattern[str]:
    """Ein Muster für viele Namen, längste zuerst.

    Vorn immer eine Wortgrenze. Hinten nur bei MEHRWORT-Namen: Einwort-Namen
    stecken in deutschen Komposita („Pferdemarktplanungen“, „Fliegerhorstes“),
    ein Mehrwort-Name nicht — „Oldenburg Pass“ traf sonst „zu Oldenburg
    passten“ (Stichprobe B7).
    """
    teile = [re.escape(n) + (_NICHT_DAHINTER if (" " in n or "-" in n) else "")
             for n in sorted(namen, key=len, reverse=True)]
    return re.compile(_NICHT_DAVOR + "(" + "|".join(teile) + ")", re.IGNORECASE)


def entitaeten_verknuepfen(store: Any) -> dict:
    """Entität ↔ Grundakte und Entität ↔ Erwähnung neu ableiten (ohne LLM)."""
    t0 = time.perf_counter()
    namen: dict[str, set[str]] = defaultdict(set)
    orte: set[str] = set()
    for slug, name, kind, _n in store.entity_name_variants():
        name = " ".join(name.split())
        if len(name) >= NAME_MIN and not _GREMIUM.search(name):
            namen[slug].add(name)
            if kind == "place":
                orte.add(slug)
    zu: dict[str, set[str]] = defaultdict(set)
    for slug, varianten in namen.items():
        for n in varianten:
            zu[n.lower()].add(slug)
    erwaehnungen: list[tuple] = []
    if zu:
        muster = _namensmuster(list(zu))
        beitraege: dict[str, int] = defaultdict(int)
        for wid, text in store.speech_texts():
            for slug in {s for m in muster.findall(text) for s in zu[m.lower()]}:
                erwaehnungen.append((slug, "speech", wid))
                beitraege[slug] += 1
        # Pressemitteilungen: Orte und Straßen nur im TITEL. Im Text sind sie
        # fast immer Veranstaltungsort („Am Dienstag tagt der Sozialausschuss
        # … Industriestraße 1d“, Kurse „im Alter Postweg“) — Stichprobe B7.
        for pid, titel, anfang in store.press_leads(PRESSE_ANFANG):
            im_titel = {s for m in muster.findall(titel) for s in zu[m.lower()]}
            im_text = {s for m in muster.findall(anfang) for s in zu[m.lower()]} - orte
            for slug in im_titel | im_text:
                erwaehnungen.append((slug, "press", pid))
        einwort = {s for s, v in namen.items() if all(" " not in n and "-" not in n for n in v)}
        allgemein = {s for s in einwort if beitraege[s] > ALLGEMEIN_BEITRAEGE}
        erwaehnungen = [e for e in erwaehnungen if e[0] not in allgemein]
    # Vererbung über die Grundakte — ohne Gremien und ohne Sammelakten.
    paare = {(slug, mid) for slug, name, mid, titel in store.entity_matter_pairs()
             if not _GREMIUM.search(name or "") and not _SAMMELAKTE.search(titel or "")}
    # Dazu: Akten ohne Beschluss über den TITEL ihrer Vorlage. Eine Vorlage
    # ohne Protokoll hat noch keinen Beschluss und damit kein Thema — ihre
    # angekündigten Stationen erreichten keine Akte (Klinikum: „Klinikum
    # Oldenburg AöR (KOL): Ausfallbürgschaft …“, im Rat am 28.09.2026; Phase 4,
    # lokale Probe 02.10.2026). Nur diese: Über ALLE Vorlagen hingen 740 Akten
    # mehr an Entitäten, „Innenstadt“ allein an 42 protokollierten.
    if zu:
        for mid, vorlage, aktentitel in store.open_matter_template_titles():
            if _SAMMELAKTE.search(aktentitel or ""):
                continue
            for slug in {s for m in muster.findall(vorlage or "") for s in zu[m.lower()]}:
                paare.add((slug, mid))
    paare = sorted(paare)
    store.replace_entity_akten(paare, erwaehnungen)
    return {"entitaet_akte": len(paare), "erwaehnungen": len(erwaehnungen),
            "sekunden": round(time.perf_counter() - t0, 1)}


#: Lesbare Namen der Zeilenarten — dieselben wie in eval/run_akten.py.
ART = {"decision": "beschluss", "speech": "debatte", "press": "presse",
       "template": "vorlage", "agenda_item": "beratung", "deliberation": "station"}


def akte_von(store: Any, decision_ids: list[int]) -> dict:
    """Die Akte zu einem Einstieg (Beschlüsse, die die Suche gefunden hat).

    1. Die Grundakten des Einstiegs.
    2. Die Entitäten dieser Grundakten — ohne große Orte (``ORT_KLEBT_BIS``)
       und ohne Allerweltsnamen — und alle Grundakten, an denen sie hängen.
    3. Alle Zeilen dieser Grundakten und die Erwähnungen der Entitäten.

    Gibt ``{"matters", "entities", "items"}`` zurück; ``items`` ist eine Menge
    aus (Art, id) mit den Arten aus ``ART``.
    """
    start = store.matters_of_decisions(list(decision_ids))
    entities = [e for e in store.entities_of_matters(sorted(start))
                if not (e["kind"] == "place" and (e["n"] or 0) > ORT_KLEBT_BIS)]
    slugs = sorted(e["slug"] for e in entities)
    matters = start | store.matters_of_entities(slugs)
    items = {(ART[t], i) for t, i in store.items_of_matters(sorted(matters)) if t in ART}
    items |= {(ART[t], i) for t, i in store.mentions_of_entities(slugs) if t in ART}
    return {"matters": matters, "entities": entities, "items": items}


def build(store: Any, stopp: Callable[[], bool] | None = None) -> dict:
    """Grundakten vollständig neu aufbauen. Idempotent; ids bleiben über ``key``
    stabil. Bricht ``stopp`` ab, bleibt der alte Stand stehen (nichts halb)."""
    t0 = time.perf_counter()
    a = zuordnen(store, stopp)
    if stopp and stopp():
        return {"abgebrochen": True}
    keys = sorted({k for k, _ in a.zuordnung.values()})
    meta = [(k, _art_von(k), a.titel.get(k),
             min(a.daten[k]) if a.daten.get(k) else None,
             max(a.daten[k]) if a.daten.get(k) else None) for k in keys]
    items = [(art, iid, k, quelle) for (art, iid), (k, quelle) in a.zuordnung.items()]
    store.replace_matters(meta, items, sorted(a.kanten),
                          datetime.now(timezone.utc).isoformat(timespec="seconds"))
    je_art: dict[str, int] = defaultdict(int)
    for art, _ in a.zuordnung:
        je_art[art] += 1
    entitaeten = entitaeten_verknuepfen(store)
    stats = {"akten": len(keys), "eintraege": len(a.zuordnung), "je_art": dict(je_art),
             "kanten": len(a.kanten), "entitaet_akte": entitaeten["entitaet_akte"],
             "erwaehnungen": entitaeten["erwaehnungen"],
             "sekunden": round(time.perf_counter() - t0, 1)}
    log.info("Grundakten: %s", stats)
    return stats
