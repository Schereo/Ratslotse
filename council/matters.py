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
den Rohdaten neu, schnell genug für jeden Ernte-Lauf. Die ``key``-Spalte ist
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
    stats = {"akten": len(keys), "eintraege": len(a.zuordnung), "je_art": dict(je_art),
             "kanten": len(a.kanten), "sekunden": round(time.perf_counter() - t0, 1)}
    log.info("Grundakten: %s", stats)
    return stats
