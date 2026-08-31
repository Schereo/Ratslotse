"""Ratsinformationssystem: browse and search sessions, agenda items, committees."""
from __future__ import annotations

import json
import logging
import math
import re
import time
import unicodedata
from collections import Counter, defaultdict
from datetime import date
from typing import Callable

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field, field_validator

from council.store import CouncilStore
from council.topics import POLICY_FIELDS
from council.goals import GOALS
from council.parties import faction_label, order_key
from council import ausgabenreihe as ausgabenreihe_mod
from council import kennzahlen as kennzahlen_mod
from council import nachbewilligungen as nachbewilligungen_mod
from council import spenden as spenden_mod
from council import steuertabellen
from council import gewerbesteuerstatistik as gewst
from council import beteiligungsbericht, qa
from council import ernte
from council import importance
from council import live as live_mod
from council import sitzungspause as pause_mod
from council import vorlagen as vorlagen_mod
from council import places

from kern.store import Store

from .. import deepresearch
from ..config import get_settings
from ..antworten import (AnalyseDaten, BeschlussDetail, BeschlussListe, DieseWoche,
                        EntitaetenKarte, Entitaeten, EntitaetsDetail, Finanzen,
                        FundstueckDesTages, GespraechDetail, GespraecheGeloescht,
                        GespraechEinstellung, GespraecheListe, Gremien,
                        HaushaltAenderungslisten, HaushaltBeteiligungen, HaushaltBilanz,
                        HaushaltDatenstand, HaushaltDokumente, HaushaltGebaut,
                        HaushaltInvestitionen, HaushaltInvestitionsprogramm,
                        HaushaltKonzern, HaushaltProdukte, HaushaltPruefberichte,
                        HaushaltSchulden, HaushaltStellenplan, HaushaltStreit,
                        HaushaltUebersicht, HaushaltVergleich, HaushaltWeg, HeuteBriefing,
                        Ok, OeffentlicheZahlen, OrtsDetail, OrtsKatalog, ParteienFilter,
                        ParteiMeinungen,
                        PersonenDetail, PersonenLexikon, QaBeispiele, QaShare,
                        QaShareToken, Ratsmitglieder, RechercheAktuell, RechercheGestartet,
                        RechercheGestoppt, RechercheSnapshot, SitzungsDetail,
                        SitzungsListe, Sitzungspause, Stadtteile, Themenfelder,
                        ThemenfeldRueckblicke, TrendDaten, VorlageEntfolgt, VorlageGefolgt,
                        VorlagenFolgen, Vorschau, WochenvorschauIntern, Wortbeitraege,
                        ZahlDerWoche, ZielDetail, Ziele)
from ..deps import get_council_store, get_store, optional_user, require_active
from ..ratelimit import (
    partei_meinungen_limiter,
    qa_feedback_limiter,
    qa_limiter,
    qa_share_limiter,
    qa_share_report_limiter,
)

router = APIRouter(prefix="/api/council", tags=["council"])

_log = logging.getLogger(__name__)

BASE_URL = "https://buergerinfo.oldenburg.de"


def _ratsinfo_url(ksinr: int) -> str:
    return f"{BASE_URL}/si0057.php?__ksinr={ksinr}"


def _vorlage_url(kvonr: int) -> str:
    return f"{BASE_URL}/vo0050.php?__kvonr={kvonr}"


@router.get("/committees")
def committees(_user: dict = Depends(require_active), store: CouncilStore = Depends(get_council_store)) -> Gremien:
    """Gremienliste — plus ``details`` für die Ausschuss-Abos.

    ``committees`` bleibt die reine Namensliste: Themen-Seite und
    Einrichtungs-Assistent lesen sie als String-Liste, ein Umbau auf Objekte
    bräche beide. Die Zusatzangaben stehen deshalb daneben in ``details``, in
    derselben Reihenfolge.

    Genau zwei zusätzliche Abfragen für die ganze Liste (nicht eine je
    Gremium) — die Seite lädt das bei jedem Aufruf.
    """
    names = store.get_all_committee_names()
    naechste = store.naechste_sitzung_je_gremium()
    seit_jahresbeginn = date(date.today().year, 1, 1).isoformat()
    beschluesse = store.beschlusszahl_je_gremium(seit_jahresbeginn)
    details = [
        {
            "name": name,
            "next_date": naechste.get(name, {}).get("session_date"),
            "next_time": naechste.get(name, {}).get("session_time"),
            "decisions_year": beschluesse.get(name, 0),
        }
        for name in names
    ]
    return {"committees": names, "details": details}


@router.get("/fields")
def fields(_user: dict = Depends(require_active), store: CouncilStore = Depends(get_council_store)) -> Themenfelder:
    """Policy fields that have at least one classified decision, with label + count."""
    counts = {r["field"]: r["count"] for r in store.policy_field_stats()}
    out = [
        {"key": key, "label": POLICY_FIELDS[key][0], "count": counts[key]}
        for key in POLICY_FIELDS if counts.get(key)
    ]
    out.sort(key=lambda f: f["count"], reverse=True)
    return {"fields": out}


@router.get("/parties")
def parties(
    _user: dict = Depends(require_active),
    store: CouncilStore = Depends(get_council_store),
) -> ParteienFilter:
    """Kanonische Antragsteller-Parteien für den Beschlussfilter.

    Die Werte kommen aus derselben normalisierten Auswertung wie der
    Parteienvergleich. So filtern Web und native App mit exakt den Labels, die
    ``decision_ids_for_party`` versteht, statt Schreibvarianten zu erfinden.
    """
    stats = store.party_analysis()["success_rates"]
    return {
        "parties": [
            {"key": row["party"], "label": row["party"], "count": row["motions"]}
            for row in sorted(stats, key=lambda row: order_key(row["party"]))
        ]
    }


@router.get("/districts")
def districts(
    _user: dict = Depends(require_active),
    store: CouncilStore = Depends(get_council_store),
) -> Stadtteile:
    """Belegte Ratslotse-Ortsbereiche für den Beschlussfilter."""
    rows = []
    for row in store.decision_location_place_stats():
        place = store.resolve_place(row["place_id"])
        if not place:
            continue
        rows.append({
            **row,
            "name": place.name,
            "place_id": place.id,
            "kind": place.kind,
            "kind_label": places.kind_label(place.kind),
            "aliases": list(place.aliases),
            "parent_ids": list(place.parent_ids),
            "description": place.description,
        })
    catalog = store.public_place_catalog()
    return {
        "catalog": {key: catalog[key] for key in (
            "schema_version", "id", "label", "singular", "plural",
            "definition", "kinds", "sources",
        )},
        "districts": rows,
    }


@router.get("/places")
def place_catalog(_user: dict = Depends(require_active),
                  store: CouncilStore = Depends(get_council_store)) -> OrtsKatalog:
    """Gemeinsamer Ortskatalog für Suche, Karten, Quiz und KI-Funktionen."""
    return store.public_place_catalog()


@router.get("/place/{place_id}")
def place_detail(
    place_id: str,
    store: CouncilStore = Depends(get_council_store),
) -> OrtsDetail:
    """Öffentliches Ortsprofil aus Katalogstammdaten und belegten Beschlüssen."""
    place = store.resolve_place(place_id)
    if not place:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ort nicht gefunden.")
    total = store.count_decisions(district=place.id)
    decisions = store.search_decisions(district=place.id, limit=50)
    matches = store.location_matches_for_decisions(
        [row["id"] for row in decisions], district=place.id)
    for row in decisions:
        row["location_matches"] = matches.get(row["id"], [])
    children = [store.public_place(child) for child in store.all_places()
                if place.id in child.parent_ids]
    return {
        "place": store.public_place(place),
        "children": children,
        "decision_count": total,
        "decisions": decisions,
    }


def _stamp_live_windows(rows: list[dict], store: CouncilStore) -> list[dict]:
    """Setzt ``live_until`` auf allen Zeilen von HEUTE (``council.live``).

    Nur heutige Sitzungen können laufen, also rechnet das auch nur für heute.
    Die Entscheidung selbst trifft der Client, weil nur er die Uhr der
    Nutzerin kennt — hier steht, WANN das Fenster zugeht, nicht ob es gerade
    offen ist. ``None`` bleibt es nur bei Terminen ohne Uhrzeit.
    """
    today = date.today().isoformat()
    heutige = [r for r in rows if str(r.get("session_date") or "")[:10] == today]
    if not heutige:
        return rows
    windows = store.live_windows(today)
    for r in heutige:
        start = r.get("session_time") or ""
        r["live_until"] = live_mod.window_end(r.get("committee"), start, windows.get(start))
    return rows


@router.get("/sessions")
def sessions(
    q: str = "",
    committee: str = "",
    date_from: str = "",
    date_to: str = "",
    scope: str = Query("all", pattern="^(all|upcoming|recent)$"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: dict = Depends(require_active),
    store: CouncilStore = Depends(get_council_store),
    nwz: Store = Depends(get_store),
) -> SitzungsListe:
    # `total` ist die GESAMTZAHL der passenden Sitzungen, `count` nur die dieser
    # Seite. Vorher gab es nur count — die Liste endete deshalb still bei der
    # Obergrenze, ohne dass irgendwo stand, dass es weitergeht (der Bestand
    # reicht bis 2018 zurück).
    if scope == "upcoming":
        rows = store.upcoming_sessions(limit=limit, offset=offset)
        total = store.count_upcoming_sessions()
    elif scope == "recent":
        rows = store.recent_sessions(limit=limit, offset=offset)
        total = store.count_recent_sessions()
    else:
        rows = store.search_sessions(q, committee, date_from, date_to, limit=limit, offset=offset)
        total = store.count_sessions(q, committee, date_from, date_to)

    # RL-902: „n TOPs zu deinen Themen" — Treffer der Tagesordnungs-
    # Klassifikation für die eingeloggte Nutzer*in (eine Batch-Abfrage).
    ksinrs = [r["ksinr"] for r in rows if r.get("ksinr")]
    mine = nwz.agenda_matches_for_owner(user["id"], ksinrs)
    for r in rows:
        matches = mine.get(r.get("ksinr") or 0)
        if matches:
            r["my_topic_items"] = matches

    return {"count": len(rows), "total": total, "sessions": _stamp_live_windows(rows, store)}


@router.get("/sitzungspause")
def sitzungspause(
    _user: dict = Depends(require_active),
    store: CouncilStore = Depends(get_council_store),
) -> Sitzungspause:
    """Läuft gerade eine Sitzungspause (Schulferien / Wahl-Übergang)?

    Der Rat pausiert laut Stadt in den Schulferien; die Übersicht zeigt dann
    ein Banner, damit sich niemand über ausbleibende neue Sitzungen wundert.
    """
    upcoming = store.upcoming_sessions(limit=1)
    next_date: date | None = None
    if upcoming:
        try:
            next_date = date.fromisoformat(str(upcoming[0]["session_date"])[:10])
        except ValueError:
            next_date = None
    return pause_mod.sitzungspause(date.today(), next_date)


# 15-Minuten-Cache für die öffentliche Heute-Leiste (RL-901) — ein Dict statt
# Infrastruktur: der Endpoint ist public und würde sonst je Landing-Aufruf
# Agenda-Zeilen lesen.
_HEUTE_CACHE: dict = {"at": 0.0, "data": None}


@router.get("/heute")
def heute(store: CouncilStore = Depends(get_council_store)) -> HeuteBriefing:
    """RL-901: „Heute im Rat" für die Landing — public (wie public-stats).
    Drei Zustände: Sitzung heute (``sessions``: alle des Tages, je mit 2
    Top-TOPs, Restzähler und ``live_until``) · nächste Sitzung ·
    Sitzungspause. Cache 15 min — die Uhr liest der Client selbst."""
    import time
    now = time.time()
    if _HEUTE_CACHE["data"] is not None and now - _HEUTE_CACHE["at"] < 900:
        return _HEUTE_CACHE["data"]

    today = date.today().isoformat()
    upcoming = store.upcoming_sessions(limit=10)
    sessions_today = [s for s in upcoming if str(s["session_date"])[:10] == today]
    if sessions_today:
        windows = store.live_windows(today)

        def eintrag(s: dict) -> dict:
            # Terminierte Sitzungen (aus dem Kalender) haben noch keinen ksinr.
            items = [i for i in store.agenda_items(s["ksinr"]) if i.get("is_public")] if s.get("ksinr") else []
            zeit = s.get("session_time") or ""
            return {
                "committee": s["committee"],
                "session_time": zeit,
                "live_until": live_mod.window_end(s["committee"], zeit, windows.get(zeit)),
                "tops": [str(i.get("title") or "")[:90] for i in items[:2]],
                "rest": max(len(items) - 2, 0),
            }

        # An Ratstagen sind es drei nacheinander (Ausschuss für Allgemeine
        # Angelegenheiten → Verwaltungsausschuss → Rat). Die Leiste schaltet
        # clientseitig auf die, die gerade läuft — deshalb kommt der ganze Tag
        # mit. Die Felder oben bleiben bei der ersten Sitzung, damit ältere
        # App-Installationen weiterlesen wie bisher.
        eintraege = [eintrag(s) for s in sessions_today]
        data = {
            "state": "heute",
            **eintraege[0],
            "n_sessions_today": len(sessions_today),
            "sessions": eintraege,
        }
    elif upcoming:
        s = upcoming[0]
        data = {
            "state": "naechste",
            "committee": s["committee"],
            "session_date": s["session_date"],
            "session_time": s.get("session_time") or "",
        }
    else:
        p = pause_mod.sitzungspause(date.today(), None)
        data = {"state": "pause", "label": p["label"], "until": p["until"]}

    _HEUTE_CACHE.update(at=now, data=data)
    return data


@router.get("/diese-woche")
def diese_woche(
    _user: dict = Depends(require_active),
    store: CouncilStore = Depends(get_council_store),
) -> DieseWoche:
    """RL-U15 (13a-A): interessantester Beschluss der letzten 7 Tage — die
    „Diese Woche im Rat"-Karte, wenn es keine persönlichen Treffer gibt.
    Der interest_reason-Satz ist die „Warum spannend"-Zeile."""
    d = store.most_interesting_recent(days_back=7)
    if not d:
        return {"found": False}
    return {
        "found": True,
        "decision_id": d["id"],
        "title": d["title"],
        "outcome": d["outcome"],
        "committee": d["committee"],
        "session_date": d["session_date"],
        "interest_reason": d.get("interest_reason") or "",
    }


@router.get("/wochenvorschau")
def wochenvorschau(
    user: dict = Depends(require_active),
    store: CouncilStore = Depends(get_council_store),
    nwz: Store = Depends(get_store),
) -> WochenvorschauIntern:
    """„Die Woche im Rat" (Design 14, davor 11d/12) — als VORSCHAU auf die
    kommenden Sitzungen, nicht als Rückblick auf Beschlüsse.

    Der Entwurf führt beide Blickrichtungen (Punkt 1 kündigt an, Punkt 4 blickt
    zurück); tragfähig ist nur die vordere: Beschlüsse erreichen uns erst mit
    dem Protokoll, im Median 119 Tage nach der Sitzung. Tagesordnungen liegen
    dagegen vor dem Termin vor.

    Seit Design 14 trägt die Antwort **jede** Sitzung der Woche und dazu die
    relevanten Punkte je Sitzung — die Karte ersetzt damit auch „Nächste
    Sitzungen". Die Themen-Treffer liegen in der anderen Datenbank (Konten und
    Themen), deshalb werden sie hier geholt und hineingereicht.
    """
    vorschau_ksinrs = [s["ksinr"] for s in store.sitzungen_im_fenster()]
    meine = nwz.agenda_matches_for_owner(user["id"], vorschau_ksinrs)
    return store.wochenvorschau(meine=meine)


@router.get("/fundstueck")
def fundstueck(
    _user: dict = Depends(require_active),
    store: CouncilStore = Depends(get_council_store),
) -> FundstueckDesTages:
    """RL-U11: Fundstück des Tages — kuratierter Archiv-Fund für die Übersicht
    (Pipeline: scripts/rate_interest.py + scripts/generate_fundstuecke.py).
    {"found": false} statt 404: ohne Karte des Tages lässt das Frontend die
    Kachel schlicht weg."""
    f = store.get_fundstueck(date.today().isoformat())
    if not f:
        return {"found": False}
    return {
        "found": True,
        "kicker": f["kicker"],
        "story": f["story"],
        "decision_id": f["decision_id"],
        "title": f["title"],
        "outcome": f["outcome"],
        "vote": f["vote"],
        "committee": f["committee"],
        "session_date": f["session_date"],
    }


@router.get("/zahl-der-woche")
def zahl_der_woche(
    _user: dict = Depends(require_active),
    store: CouncilStore = Depends(get_council_store),
) -> ZahlDerWoche:
    """RL-905: größter Beschluss-Betrag der letzten 7 Tage (Fallback 30);
    ganz ohne Treffer zählt die Karte die Beschlüsse der Woche. Die Satz-
    Formulierung übernimmt das Frontend — hier nur Rohdaten."""
    from datetime import timedelta
    today = date.today()
    for days in (7, 30):
        top = store.top_amount_since((today - timedelta(days=days)).isoformat())
        if top:
            return {"kind": "betrag", "amount_eur": top["amount_eur"],
                    "decision_id": top["id"], "title": top["title"],
                    "session_date": top["session_date"], "window_days": days}
    return {"kind": "anzahl",
            "count": store.count_decisions_since((today - timedelta(days=7)).isoformat()),
            "window_days": 7}


@router.get("/haushalt/produkte")
def haushalt_produkte(
    jahr: int,
    thh: int | None = None,
    q: str | None = None,
    amt: str | None = None,
    spielraum: str | None = None,
    nr: str | None = None,
    _user: dict = Depends(require_active),
    store: CouncilStore = Depends(get_council_store),
) -> HaushaltProdukte:
    """Produktebene eines Haushaltsjahres — was einzelne Aufgaben kosten,
    samt Steckbrief (Kurzbeschreibung, Rechtsgrundlage, Spielraum,
    Wirkungskreis, Zielgruppe) aus den Teilhaushalts-Plänen.

    Aus den Teilhaushalts-Plänen des Ratsinformationssystems. Die Abdeckung
    ist unvollständig (nicht jeder Teilhaushalt liegt für jedes Jahr als
    auslesbares Dokument vor); ``abdeckung_prozent`` sagt, wie viel der
    geplanten Aufwendungen die gefundenen Produkte erklären — damit die
    Oberfläche das nicht als Vollbild ausgeben kann.

    ``q``/``amt``/``spielraum`` filtern **serverseitig**: Mit dem Steckbrief
    trägt jede der knapp 400 Zeilen mehrere hundert Zeichen Fließtext, die
    niemand im Browser sortieren muss. ``nr`` holt zusätzlich ein einzelnes
    Produkt — die Steckbrief-Ansicht braucht es auch dann, wenn der gerade
    gesetzte Filter es aus der Liste nähme.

    ``facetten`` liefert die Filterwerte mit Anzahl und dazu, wie viele
    Produkte überhaupt welches Steckbrief-Feld tragen: Die Seite weist die
    Lücke aus, statt sie zu verschweigen.

    Jedes Produkt trägt zusätzlich ``jahre`` — die Jahrgänge, in denen es im
    Bestand steht. Gegen ``alle_jahre`` gehalten wird daraus das
    Abdeckungs-Badge der Trefferliste (H4-04): Ein Produkt, das erst ab 2021
    vorliegt, soll das sagen, statt wie eine durchgehende Reihe auszusehen."""
    produkte = store.get_produkte(jahr, thh, suche=q, amt=amt,
                                  beeinflussbarkeit=spielraum)
    abdeckung = store.produkt_abdeckung()
    for p in produkte:
        p["jahre"] = abdeckung.get(p["produkt_nr"], [])
    einzeln = store.produkt(jahr, nr) if nr else None
    if einzeln:
        einzeln["jahre"] = abdeckung.get(einzeln["produkt_nr"], [])
    summe = sum(p["aufwendungen"] or 0 for p in store.get_produkte(jahr))
    plan = next((z for z in store.get_haushalt(jahr) if z["is_summe"]), None)
    quote = round(summe / plan["aufwendungen"] * 100, 1) if plan and plan["aufwendungen"] else None
    return {"jahr": jahr, "produkte": produkte, "abdeckung_prozent": quote,
            "plan_aufwendungen": plan["aufwendungen"] if plan else None,
            "treffer": len(produkte),
            "alle_jahre": store.produkte_jahre(),
            "facetten": store.produkt_facetten(jahr),
            "produkt": einzeln}


@router.get("/haushalt/stellenplan")
def haushalt_stellenplan(
    jahrgang: int | None = None,
    _user: dict = Depends(require_active),
    store: CouncilStore = Depends(get_council_store),
) -> HaushaltStellenplan:
    """Der Stellenplan: wie viele Stellen die Stadt vorhält und wie viele
    davon nicht besetzt sind.

    Die einzige Schicht des Haushalts-Bereichs, die nicht in Euro rechnet.
    Personal ist der größte Ausgabenblock; hier stehen die Menschen dahinter —
    und die Lücke zwischen geplanten und tatsächlich besetzten Stellen.

    - ``jahrgaenge``: Haushaltsjahre mit eingelesenem Plan,
    - ``summen``: je Jahrgang und Teil die Gesamtzeile des Dokuments (Stellen
      im Haushaltsjahr, Stellen im Vorjahr, besetzt, nicht besetzt) samt
      Stichtag der Besetzung,
    - ``gruppen``: dieselben Zahlen je Laufbahn- bzw. Beschäftigtengruppe,
    - ``zeilen``: die Einzelposten — nur mit ``jahrgang``, weil das rund 190
      Zeilen je Jahrgang sind,
    - ``fehlend``: welche ``(Jahrgang, Teil)`` **nicht** vorliegen, obwohl der
      Jahrgang eingelesen ist. Ohne diese Liste sähe ein Jahrgang mit nur
      einem Teil aus wie ein vollständiger,
    - ``herkunft``: je ``herkunft_id`` Dokument, Fundstelle, bestandene Probe
      samt Messwert und Stichtag. Teil A und Teil B eines Jahrgangs tragen
      **verschiedene** IDs: verschiedene Tabellen, verschiedene Proben.

    Zwei Dinge, die die Zahlen nicht hergeben und die eine Seite dazusagen
    muss: Der Plan zählt **Stellen**, keine Köpfe (Teilzeit steht als
    Bruchteil), und er zählt nur die **Kernverwaltung** — Klinikum, Bäder,
    Bus und Gebäudewirtschaft haben eigene Wirtschaftspläne.

    Und die Besetzungszahlen gehören zur **Vorjahresspalte**, nicht zum
    Haushaltsjahr: Geplant wird vorwärts, gezählt werden kann nur rückwärts.
    ``stichtag`` sagt, auf welchen Tag sie sich beziehen."""
    summen = store.get_stellenplan(art="gesamt")
    gruppen = store.get_stellenplan(art="gruppe")
    zeilen = (store.get_stellenplan(art="posten", jahrgang=jahrgang)
              if jahrgang is not None else [])
    jahrgaenge = sorted({z["jahrgang"] for z in summen})

    # Was fehlt, und in welchem Jahrgang: Ein Jahrgang steht mit einem Teil in
    # der Tabelle, wenn der andere seine Probe nicht bestanden hat oder im
    # PDF unlesbar war (Stellenplan 2026, Teil B). Die Oberfläche muss das
    # zeigen können, statt die Lücke als Null darzustellen.
    from council import stellenplan as _sp

    da = store.stellenplan_einheiten()
    fehlend = [{"jahrgang": j, "teil": t, "name": _sp.TEIL_NAMEN[t]}
               for j in jahrgaenge for t in sorted(_sp.TEIL_SPALTEN)
               if (j, t) not in da]

    ids = sorted({z["herkunft_id"] for z in (*summen, *gruppen, *zeilen)
                  if z["herkunft_id"] is not None})
    return {
        "jahrgaenge": jahrgaenge,
        "teile": _sp.TEIL_NAMEN,
        "summen": summen,
        "gruppen": gruppen,
        "zeilen": zeilen,
        "fehlend": fehlend,
        "herkunft": {str(h["id"]): h for h in store.get_herkunft(ids)},
    }


@router.get("/haushalt/pruefberichte")
def haushalt_pruefberichte(
    marke: str | None = Query(None, pattern="^(B|WB|H|K)$"),
    _user: dict = Depends(require_active),
    store: CouncilStore = Depends(get_council_store),
) -> HaushaltPruefberichte:
    """Prüfungsfeststellungen des Rechnungsprüfungsamts, alle Jahrgänge.

    Bewusst alles auf einmal statt je Jahr: Die Aussage dieses Bestands liegt
    nicht im einzelnen Jahrgang, sondern in der Wiederholung — eine
    „Wiederholte Beanstandung" ist erst dann etwas wert, wenn daneben steht,
    seit wann sie dort steht. Dafür braucht die Seite alle Jahre gleichzeitig.

    - ``feststellungen``: eine Zeile je Randmarke, mit Textziffer, Seite und
      Deeplink auf das Quelldokument,
    - ``legende``: die Bedeutung der Marken, wie der Bericht sie selbst
      erklärt (jüngster Jahrgang, der die Marke noch führt),
    - ``ohne_bericht``: Jahre, für die ein Jahresabschluss ausgelesen ist, ein
      Schlussbericht aber nicht — die Lücke gehört sichtbar, nicht kaschiert.

    ``marke`` grenzt auf eine Randmarke ein. Gedacht für den Hinweis auf
    ``/haushalt/plan-ist``, der nur die Kette der wiederholten Beanstandungen
    braucht: Der volle Bestand ist eine Viertel-Megabyte Prosa und hat auf
    einer Seite nichts zu suchen, die ihn gar nicht anzeigt. ``jahre`` und
    ``legende`` bleiben dabei die des Gesamtbestands — sonst stünde in der
    Fußzeile eine Jahresliste, die vom Filter abhängt.
    """
    zeilen = store.get_pruefberichte()
    jahre = store.pruefbericht_jahre()
    legende: dict[str, dict] = {}
    for z in zeilen:  # aufsteigend sortiert — der letzte Eintrag gewinnt
        legende[z["marke"]] = {"name": z["marke_name"],
                               "erlaeuterung": z["marke_erlaeuterung"]}
    return {
        "jahre": jahre,
        "legende": legende,
        "feststellungen": [z for z in zeilen if marke is None or z["marke"] == marke],
        "ohne_bericht": [j for j in store.ergebnisrechnung_jahre() if j not in jahre],
    }


@router.get("/haushalt/konzern")
def haushalt_konzern(
    _user: dict = Depends(require_active),
    store: CouncilStore = Depends(get_council_store),
) -> HaushaltKonzern:
    """Der Konzern Stadt Oldenburg — was der Kernhaushalt **nicht** zeigt.

    Alles auf einmal, weil die Aussage dieser Seite eine Differenz ist: Eine
    Konzernzahl allein sagt nichts, sie sagt erst etwas neben der
    Kernverwaltung im selben Jahr.

    - ``jahre``: Jahrgänge mit eingelesenem Gesamtabschluss,
    - ``konzern``: je Jahrgang die Summen des Konzerns (Erträge,
      Aufwendungen, ordentliches Ergebnis, Gesamtjahresergebnis, Zins- und
      Personalaufwand) samt bestandener Rechenprobe und Fundstelle,
    - ``traeger``: wer den Konzern ausmacht — je Jahrgang und Aufstellung eine
      Zeile pro Aufgabenträger, Beträge in **Euro** (der Bericht rundet sie
      auf Tausend, daher die glatten Endziffern),
    - ``posten``: die vollständige Gesamtergebnisrechnung je Jahrgang,
    - ``gegenprobe``: dieselbe Kernverwaltungs-Zahl aus zwei unabhängigen
      Dokumenten — der Trägerzeile des Gesamtabschlusses und dem
      Jahresabschluss, den wir getrennt eingelesen haben,
    - ``herkunft``: je ``herkunft_id`` Dokument, Fundstelle, bestandene Probe
      samt Messwert und Stichtag. Die beiden Ebenen eines Jahrgangs tragen
      **verschiedene** IDs: Sie stehen in verschiedenen Abschnitten des
      Berichts und sind durch verschiedene Proben gedeckt.

    Der Gesamtabschluss ist **kein Haushalt**: Er wird rund zwei Jahre später
    aufgestellt, folgt handelsrechtlichen Regeln und ist mit den Planzahlen
    auf ``/haushalt`` nicht verrechenbar. Die Seite sagt das; die API liefert
    deshalb auch keine gemischten Summen, sondern beide Reihen getrennt."""
    posten = store.get_konzern_posten()
    traeger = store.get_konzern_traeger()
    kern = store.kernverwaltung_ist()

    je_jahr: dict[int, dict] = {}
    for p in posten:
        eintrag = je_jahr.setdefault(
            p["jahr"], {"jahr": p["jahr"], "herkunft_id": p["herkunft_id"]})
        if p["rolle"]:
            eintrag[p["rolle"]] = p["betrag"]

    # Gegenprobe: Trägerzeile „Stadt Oldenburg" (TEUR) gegen unseren
    # Jahresabschluss (Euro). Abgeglichen wird auf Tausend genau — feiner
    # kann es nicht sein, der Bericht rundet dort.
    gegenprobe = []
    for t in traeger:
        if t["traeger_key"] != "stadt":
            continue
        ist = (kern.get(t["jahr"]) or {}).get(t["art"])
        if ist is None:
            continue
        gegenprobe.append({
            "jahr": t["jahr"], "art": t["art"],
            "konzern": t["betrag_teur"] * 1000.0, "jahresabschluss": ist,
            "ok": abs(t["betrag_teur"] - ist / 1000.0) <= 1.0,
        })

    ids = sorted({z["herkunft_id"] for z in (*posten, *traeger)
                  if z["herkunft_id"] is not None})
    return {
        "jahre": store.konzern_jahre(),
        "konzern": [je_jahr[j] for j in sorted(je_jahr)],
        "traeger": [{**t, "betrag": t["betrag_teur"] * 1000.0,
                     "vorjahr": (t["vorjahr_teur"] * 1000.0
                                 if t["vorjahr_teur"] is not None else None)}
                    for t in traeger],
        "posten": posten,
        "gegenprobe": gegenprobe,
        "herkunft": {str(h["id"]): h for h in store.get_herkunft(ids)},
    }


def _lexikon_zuordnung(store: CouncilStore,
                       personen: list[dict]) -> dict[str, dict]:
    """Namen aus dem Beteiligungsbericht → Personen-Seite und Partei.

    Die Zuordnung gehört **hierher** und nicht in die Datenbank: Das Lexikon
    entsteht aus Verzeichnis und Anwesenheitslisten und ändert sich mit jedem
    Protokoll. Als Fremdschlüssel eingefroren, zeigte ein Steckbrief von 2022
    nächstes Jahr auf eine Person, die inzwischen anders geführt wird — der
    Beteiligungsbericht wird aber nur alle paar Wochen neu eingelesen.

    **Eindeutig oder gar nicht.** Zugeordnet wird über Vor- UND Nachnamen, und
    nur, wenn genau ein Lexikon-Eintrag passt. Der Bäderbetrieb führt 2024
    „Dr. Sebastian Rohe" und „Dr. Georg Rohe" nebeneinander; wer auf den
    Nachnamen zuordnet, hängt einem der beiden die Personen-Seite des anderen
    an. Ein fehlender Link ist ein fehlender Link; ein falscher ist eine
    Falschaussage über einen Menschen.

    Namen **ohne** Vornamen bekommen deshalb nie einen Treffer — und die rund
    30 Prozent, die leer ausgehen, sind zum großen Teil gar keine
    Ratspersonen: Aufsichtsräte entsenden auch Banken, Hochschulen und
    Mitgesellschafter, und die TGO Besitz benennt statt Personen ihre
    Entsendungsrechte („Vertreter/in der Landessparkasse").

    **Verlinkt wird nur, wer eine Seite hat** — und das sind allein die
    Ratsmitglieder (``art == "rat"``). Das Lexikon führt daneben
    Verwaltungsleute und, seit Tims Auftrag vom 17.08., die Aufsichtsorgane
    selbst; ``/council/person/{slug}`` kennt beide nicht und antwortet mit
    404. Bis hierher zeigte der Steckbrief sechs solcher Links ins Leere,
    darunter den des Oberbürgermeisters — er sitzt qua Amt in fast jedem
    Aufsichtsrat, taucht in den Anwesenheitslisten aber als Verwaltung auf
    und hat deshalb kein Mandats-Profil. Ein toter Link ist schlimmer als
    kein Link.

    Die Funktion aus dem Bericht kommt mit, weil sie die Tippfehler-Heilung
    trägt (:meth:`CouncilStore.tippfehler_ratsmitglied`): Wo der Bericht
    „Ratsmitglied" behauptet und sich nur um einen Buchstaben vertippt hat,
    findet die Person ihre Seite trotzdem."""
    def ganz(anzeige: str) -> tuple[str, ...]:
        """Alle Namensteile gefaltet — für den Stichentscheid unten."""
        return tuple(sorted(CouncilStore._falte_namen(t)
                            for t in anzeige.replace(".", " ").split()
                            if t.lower().rstrip(".") not in CouncilStore._HONORIFICS))

    nach_paar: dict[tuple[str, str], list[dict]] = {}
    for e in store.personen_lexikon():
        # Blocker tragen keinen Namen, nur einen Nachnamen — sie sind für die
        # Badge-Logik da (Gäste dürfen keinen Treffer erzeugen) und haben hier
        # nichts zu suchen: Ohne Vornamen können sie ohnehin nicht passen.
        if e.get("art") == "blocker" or not e.get("vorname"):
            continue
        nach_paar.setdefault((e["vorname"], e["nachname"]), []).append(e)

    # Je Name die häufigste Funktion des Berichts — Eingang der Heilung unten.
    funktionen: dict[str, Counter] = defaultdict(Counter)
    for p in personen:
        if p.get("funktion"):
            funktionen[p["name"]][p["funktion"]] += 1

    aus: dict[str, dict] = {}
    for name in {p["name"] for p in personen}:
        vor, nach = CouncilStore.namensteile(name)
        treffer = nach_paar.get((vor, nach), []) if vor and nach else []
        if len(treffer) > 1:
            # Gleicher Vor- und Nachname, zwei Einträge. Wo dieselbe Person
            # unter zwei Namensformen in den Quellen steht, führt das
            # Verzeichnis sie längst als **einen** Eintrag zusammen
            # (`council.namensformen`) — hier bleiben also die Fälle, die
            # niemand geprüft hat. Dann entscheidet der **ganze** Name: Wer
            # genau so heißt, wie der Bericht ihn druckt, gewinnt. Passen null
            # oder zwei genau, bleibt es beim Verzicht — zwei echte
            # Namensvettern sind hier nicht auseinanderzuhalten.
            treffer = [e for e in treffer if ganz(e["name"] or "") == ganz(name)]
        eintrag = treffer[0] if len(treffer) == 1 else None
        if eintrag is None:
            fn = funktionen[name].most_common(1)
            eintrag = CouncilStore.tippfehler_ratsmitglied(
                vor, nach, fn[0][0] if fn else None, nach_paar)
        verlinkbar = bool(eintrag) and eintrag.get("art") == "rat"
        aus[name] = {"slug": eintrag["slug"] if verlinkbar else None,
                     "partei": eintrag["partei"] if eintrag else None}
    return aus


@router.get("/haushalt/beteiligungen")
def haushalt_beteiligungen(
    _user: dict = Depends(require_active),
    store: CouncilStore = Depends(get_council_store),
) -> HaushaltBeteiligungen:
    """Die städtischen Gesellschaften — was sie tun, wer sie beaufsichtigt.

    Die Ergänzung zum Gesamtabschluss (``/haushalt/konzern``): Der sagt, wie
    viel die Betriebe bewegen, diese Seite, was sie damit machen.

    - ``gesellschaften``: je Gesellschaft Name, Gliederungsnummer und Seite im
      jüngsten Bericht, dazu ``konzern_key``, wo der Gesamtabschluss sie als
      eigenen Träger führt,
    - ``texte``: die beschreibenden Abschnitte (Gegenstand, Eigentümer,
      Aufsichtsorgane, eigene Beteiligungen, Auswirkungen auf den Haushalt) —
      alle ausdrücklich **ungeprüft**, denn Fließtext lässt sich gegen nichts
      rechnen,
    - ``personen``: die Aufsichtsorgane, Person für Person, mit Gremium,
      Vorsitz, Amtszeit-Hinweis und — wo das Verzeichnis die Person
      eindeutig kennt — ``slug`` und ``partei`` für die Personen-Seite.
      ``funktion`` steht nur da, wo die Spaltenprobe gehalten hat; siehe
      ``funktionen_zuordenbar`` an der Gesellschaft. Zwei der fünf Abschnitte
      sind nämlich keine Prosa, sondern Tabellen, die der PDF-Extrakt
      spaltenweise ausgibt (``council/beteiligungsbericht.py``),
    - ``eigentuemer``: wem die Gesellschaft gehört, mit Betrag und Anteil.
      **Ohne** die Stammkapital-Zeile — die ist die Summe und kein
      Gesellschafter. Gesellschaften, deren Anteile sich nicht auf das
      ausgewiesene Stammkapital summieren, erscheinen hier gar nicht; ihr
      Rohtext steht weiter in ``texte``,
    - ``kennzahlen``: die Zeitreihe je Gesellschaft (Jahresergebnis,
      Bilanzsumme, Eigenkapitalquote). ``berichte`` sagt, wie viele Berichte
      denselben Wert nennen — 1 heißt „durch eine Probe im Dokument gedeckt",
      mehr heißt zusätzlich „von einer zweiten Veröffentlichung bestätigt",
    - ``konzernvergleich``: für die Gesellschaften, die auch im
      Gesamtabschluss stehen, beide Zahlen desselben Jahres nebeneinander.
      **Keine Probe** — die beiden Rechnungen unterscheiden sich systematisch,
      und zwei Betriebe weisen wegen Ergebnisabführung 0 € aus, obwohl sie
      etwas erwirtschaftet haben. Eine Einordnung, kein Urteil,
    - ``berichtsjahre`` / ``jahre``: welche Berichte gelesen sind und welche
      Bezugsjahre die Kennzahlen abdecken (sie reichen weiter zurück als die
      Berichte — jeder führt vier bis fünf Jahre mit),
    - ``herkunft``: je ``herkunft_id`` Dokument, Fundstelle, Seite und Probe.

    Gelesen werden die Berichte ab 2022; davor ist das Dokument anders
    aufgebaut und nicht maschinenlesbar (``council/beteiligungsbericht.py``)."""
    berichtsjahre = store.beteiligungsbericht_jahre()
    gesellschaften = store.get_gesellschaften()
    kennzahlen = store.get_gesellschaft_kennzahlen()
    texte = [t for g in gesellschaften
             for t in store.get_gesellschaft_texte(g["gesellschaft"])]
    personen = store.get_gesellschaft_personen()
    eigentuemer = store.get_gesellschaft_eigentuemer()
    vergleich = (beteiligungsbericht.konzernvergleich(store, berichtsjahre[-1])
                 if berichtsjahre else [])

    # Die Probe steht an jeder Personenzeile und gilt je Gesellschaft; hier
    # wird sie einmal an die Gesellschaft gehängt, damit die Seite sie zeigen
    # kann, ohne die Personen durchzugehen. Wer gar keine Personen hat, hat
    # auch nichts falsch zuzuordnen.
    gerissen = {p["gesellschaft"] for p in personen if not p["funktionen_zuordenbar"]}
    verzeichnis = _lexikon_zuordnung(store, personen)

    ids = sorted({z["herkunft_id"]
                  for z in (*gesellschaften, *texte, *kennzahlen, *personen,
                            *eigentuemer)
                  if z["herkunft_id"] is not None})
    return {
        "berichtsjahre": berichtsjahre,
        "jahre": sorted({z["jahr"] for z in kennzahlen}),
        "gesellschaften": [{**g, "funktionen_zuordenbar":
                            g["gesellschaft"] not in gerissen}
                           for g in gesellschaften],
        "texte": texte,
        "personen": [{**p, "funktionen_zuordenbar":
                      bool(p["funktionen_zuordenbar"]),
                      **verzeichnis[p["name"]]} for p in personen],
        "eigentuemer": eigentuemer,
        "kennzahlen": kennzahlen,
        "konzernvergleich": vergleich,
        "herkunft": {str(h["id"]): h for h in store.get_herkunft(ids)},
    }


@router.get("/haushalt/investitionen")
def haushalt_investitionen(
    _user: dict = Depends(require_active),
    store: CouncilStore = Depends(get_council_store),
) -> HaushaltInvestitionen:
    """Was die Stadt bauen und kaufen will — die Investitionen des
    Finanzhaushalts, je Teilhaushalt.

    Die andere Hälfte des Haushaltsplans: Im Ergebnishaushalt, den der Rest des
    Bereichs zeigt, steht keine einzige Investition (ein Schulneubau taucht dort
    nur als Abschreibung auf, verteilt über Jahrzehnte).

    - ``jahre``: Haushaltsjahre, für die Investitionen vorliegen,
    - ``teilhaushalte``: je Jahr und Teilhaushalt Ein- und Auszahlungen aus
      Investitionstätigkeit,
    - ``gesamt``: je Jahr die Summenzeile der Datei — das **Ziel der
      Rechenprobe**, nicht unsere Addition,
    - ``finanzhaushalt``: je Jahr der Gesamtbetrag aller Ein- und Auszahlungen,
      also samt laufender Verwaltungstätigkeit. Die Bezugsgröße, die aus
      „80,8 Mio. €" erst eine Aussage macht — und die einzige Zahl hier ohne
      Rechenprobe (eigene ``herkunft_id`` mit ``ungeprueft``, s. u.),
    - ``herkunft``: je ``herkunft_id`` Dokument, Fundstelle, bestandene Probe
      samt Messwert. Die geprüften Zeilen und die Bezugsgröße tragen
      **verschiedene** IDs; sie stehen in derselben Datei, aber nur die einen
      sind durch deren Summenzeile gedeckt.

    Zwei Grenzen, die die Seite nennt und die API deshalb nicht verwischt:
    Diese Zahlen sind **Plan**, nicht Ist, und sie nennen **kein einzelnes
    Vorhaben** — „Verkehr und Straßenbau: 10,5 Mio. €" sagt nicht, welche
    Straße."""
    zeilen = store.get_investitionen()
    ids = sorted({z["herkunft_id"] for z in zeilen if z["herkunft_id"] is not None})
    return {
        "jahre": store.investitionen_jahre(),
        "teilhaushalte": [z for z in zeilen if z["ebene"] == "teilhaushalt"],
        "gesamt": [z for z in zeilen if z["ebene"] == "investitionen"],
        "finanzhaushalt": [z for z in zeilen if z["ebene"] == "finanzhaushalt"],
        "herkunft": {str(h["id"]): h for h in store.get_herkunft(ids)},
    }


@router.get("/haushalt/investitionsprogramm")
def haushalt_investitionsprogramm(
    _user: dict = Depends(require_active),
    store: CouncilStore = Depends(get_council_store),
) -> HaushaltInvestitionsprogramm:
    """Die einzelnen Vorhaben — die Ebene unter ``/haushalt/investitionen``.

    Aus Anlage 004 des Haushaltsplans: nicht „Schule und Bildung: 8,3 Mio. €",
    sondern „BBS Haarentor: Ausstattung". Acht Jahrgänge, rund 4.500 Vorhaben.

    - ``jahre``: Jahrgänge, für die ein Programm vorliegt,
    - ``massnahmen``: je Vorhaben Teilhaushalt, IPSP-Element, Bezeichnung und
      **Gesamtinvestitionssumme**,
    - ``teilhaushalte``: je Teilhaushalt die Gesamtsumme, die das Dokument am
      Ende seines Abschnitts ausweist — das **Ziel der Rechenprobe**, nicht
      unsere Addition,
    - ``gesamt``: je Jahrgang die Gesamtsumme des Investitionsprogramms,
    - ``herkunft``: Dokument, Fundstelle und die drei bestandenen Proben.

    Drei Grenzen, die die Seite nennt und die API deshalb nicht verwischt:

    1. **Nur die Gesamtinvestitionssumme**, keine Jahresraten — im Textextrakt
       fallen leere Zellen ersatzlos weg, die Spaltenzuordnung wäre geraten.
    2. **Plan, nicht Ist.** Was am Jahresende wirklich gebaut wurde, steht
       nicht darin.
    3. **Nicht deckungsgleich mit** ``/haushalt/investitionen``. Beide Zahlen
       stimmen und zählen Verschiedenes: Das Investitionsprogramm führt die
       Gesamtkosten eines Vorhabens über alle Jahre, der Finanzhaushalt die
       Zahlungen eines Jahres — und die zu aktivierenden Eigenleistungen
       gehören nur ins Programm. Das Dokument sagt das in einer Fußnote selbst.
    """
    zeilen = store.get_investitionsmassnahmen()
    ids = sorted({z["herkunft_id"] for z in zeilen if z["herkunft_id"] is not None})
    return {
        "jahre": store.investitionsprogramm_jahre(),
        "massnahmen": [z for z in zeilen if z["ebene"] == "massnahme"],
        "teilhaushalte": [z for z in zeilen if z["ebene"] == "teilhaushalt"],
        "gesamt": [z for z in zeilen if z["ebene"] == "gesamt"],
        "herkunft": {str(h["id"]): h for h in store.get_herkunft(ids)},
    }


@router.get("/haushalt/datenstand")
def haushalt_datenstand(
    _user: dict = Depends(require_active),
    store: CouncilStore = Depends(get_council_store),
) -> HaushaltDatenstand:
    """Bis wann die Zahlen reichen — je Datenschicht ein Jahrgangs-Stand.

    Beantwortet die Frage, die sonst auf jeder Unterseite von ``/haushalt``
    einzeln erklärt werden müsste: „Warum steht hier 2024 und nicht 2025?"
    Der Bereich trägt die Schichten aus ``finanzquellen.REIHENFOLGE``, und
    die haben **verschiedene** Takte: Der Plan liegt im Oktober vor seinem
    Haushaltsjahr, die Abrechnung samt Prüfberichten im September danach,
    der Gesamtabschluss (Konzern Stadt) rund zwei Jahre danach — er entsteht
    erst, wenn alle einbezogenen Jahresabschlüsse geprüft sind. Die beiden
    Reihen des Städtevergleichs hängen an einem ganz anderen Haus: Sie kommen
    vom Landesamt für Statistik, einmal im Jahr. Für einen Jahrgang liegt
    deshalb fast nie alles gleichzeitig vor; das ist der Normalfall, nicht
    die Störung.

    Je Schicht: die vorhandenen Jahrgänge, Lücken darin, der nächste
    erwartete Jahrgang samt Datum, und ob er schon überfällig ist. Die Werte
    kommen aus dem Bestand, nicht aus einer gepflegten Liste — eine Angabe,
    die jemand von Hand nachziehen müsste, wäre genau die, die veraltet.
    Gefüllt wird der Bestand vom Cron ``scripts/check_finanzdaten.py``."""
    from council import finanzquellen

    zeilen = finanzquellen.datenstand(store)
    for z in zeilen:
        z["monat"] = finanzquellen.MONATE[z["erwarteter_monat"]]
    return {"heute": date.today().isoformat(), "schichten": zeilen}


@router.get("/haushalt/dokumente")
def haushalt_dokumente(
    _user: dict = Depends(require_active),
    store: CouncilStore = Depends(get_council_store),
) -> HaushaltDokumente:
    """Je Quelle des Haushalts-Bereichs das **Dokument** — Jahrgang für Jahrgang.

    Das Quellenverzeichnis am Fuß jeder Haushalts-Seite beschreibt eine Quelle
    als Ganzes („Die Jahresabschlüsse der Stadt Oldenburg, 2017–2024"). Diese
    Beschreibung ist redaktionell und kennt keine Jahrgänge — ihr „Dokument
    öffnen" führte deshalb auf die Startseite des Ratsinformationssystems, wo
    man wieder selbst suchen darf. Hier steht, welches PDF zu welchem Jahr
    gehört, damit der Link das Dokument des **gezeigten** Jahres öffnet.

    ``{"dokumente": {"<quellenschluessel>": [{jahr, url, label, fundstelle,
    seite}, …]}}`` — aufsteigend nach Jahr. Ein Schlüssel fehlt, wo wir kein
    Dokument haben; die Oberfläche fällt dann auf die statische Adresse
    zurück und sagt dazu, wohin sie führt.

    Ein Jahrgang kann mehrere Dokumente tragen: Die Produktebene verteilt sich
    auf rund neun Teilhaushalts-Anlagen. Die Liste nennt sie alle statt eine
    auszuwählen — welche gemeint ist, entscheidet die Seite, nicht die API.

    Die Fundstelle kommt aus ``council_herkunft`` und ist der eigentliche
    Gewinn: „Abschnitt 3.2" macht aus einem 300-Seiten-PDF eine nachschlagbare
    Stelle.

    ``jahrgaenge`` kommt aus derselben Antwort statt aus einem eigenen Aufruf:
    Es beantwortet die Nachbarfrage („welche Jahrgänge deckt diese Quelle
    ab?"), wird an derselben Stelle gebraucht — im Quellenverzeichnis — und
    ist eine Abfrage je Quelle, keine je Zeile. Zwei Endpunkte dafür hießen
    zwei Rundreisen für einen Seitenfuß."""
    return {"dokumente": store.haushalt_dokumente(),
            "jahrgaenge": store.haushalt_jahrgaenge()}


@router.get("/haushalt")
def haushalt_uebersicht(
    felder: str | None = None,
    thh_posten: str | None = None,
    _user: dict = Depends(require_active),
    store: CouncilStore = Depends(get_council_store),
) -> HaushaltUebersicht:
    """Datenfundament des Haushalts-Bereichs, in einem Aufruf:

    - ``jahre``: Ergebnishaushalt je Planjahr (Teilhaushalte + Summenzeile,
      Quelle je Zeile — Haushaltsplan-PDF bzw. Open-Data-CSV der Stadt),
    - ``steuern``: Ist-Steuereinnahmen je Steuerart seit 1998 (Langformat),
    - ``steuerkraft``: Steuerkraftmesszahl + Schlüsselzuweisungen je
      Ausgleichsjahr seit 1993 (die Jahreszahl der Quelle ist beim Einlesen
      um ein Jahr korrigiert, s. ``council/haushalt._STEUERKRAFT_VERSATZ``;
      die ``*_je_ew``-Felder sind deshalb leer),
    - ``einwohner``: jüngste Einwohnerzahl (Bezugsgröße für Pro-Kopf-Angaben),
    - ``ergebnisrechnung``: Ansatz, Plan und Ergebnis je Posten aus den
      Jahresabschlüssen — Grundlage für „geplant gegen tatsächlich",
    - ``finanzrechnung``: die Kassensicht aus demselben Jahresabschluss
      (Abschnitt 4.1) — nicht was gebucht, sondern was **gezahlt** wurde.
      Jede Zeile trägt neben der Nummer des Dokuments eine ``rolle``
      (``saldo_verwaltung``, ``saldo_investition``, ``finanzmittel``, …);
      **an der Rolle hängen, nicht an der Nummer**: Die Tabelle hat
      2017–2020 eine Zeile mehr als ab 2021, alle Nummern ab 08
      verschieben sich dadurch. ``ermaechtigung`` ist das aus Vorjahren
      übertragene Geld und ``NULL``, wo der Jahrgang die Spalte nicht führt,
    - ``ergebnishaushalt``: dieselben Posten für Jahre **ohne**
      Jahresabschluss, aus dem Gesamtergebnishaushalt der Haushaltspläne.
      Jede Zeile trägt ``art`` (``ansatz`` = das Jahr, für das dieser Plan
      der Haushalt ist; ``finanzplanung`` = mittelfristige Vorausschau nach
      § 8 NKomVG) und ``plan_jahrgang`` (aus welchem Haushalt sie stammt).
      **Beides gehört an jede Anzeige**: Der Plan nennt alle fünf Spalten
      „Ansatz", der Haushalt ist aber nur eines der Jahre, und die
      Finanzplanung schreibt jeder neue Haushalt neu. Die Zahlen stammen aus
      der Einbringungs-Vorlage, sind also der **Entwurf** der Verwaltung —
      der Beleg (``herkunft.stand``) sagt das, die Anzeige sollte es
      anschreiben,
    - ``ansatz_jahre``: die Jahre mit einem Haushaltsansatz — die Liste, aus
      der ein Jahr-Umschalter bestehen darf (ohne die Finanzplanungsjahre),
    - ``wirtschaftsplaene``: die Wirtschaftspläne der Eigenbetriebe und
      städtischen Gesellschaften, je ``betrieb`` und ``jahr``. **Nicht mit dem
      Kernhaushalt addierbar** — der Eigenbetrieb Gebäudewirtschaft vermietet
      der Stadt ihre eigenen Gebäude, seine Erträge sind zu großen Teilen
      Aufwand des Kernhaushalts; herausgerechnet wird das erst im
      Gesamtabschluss. ``ertraege``/``aufwendungen`` sind ``null``, wo die
      Quelle nur das Ergebnis nennt, und ``proben`` sagt, welche Rechenprobe
      für die Zeile gelaufen ist,
    - ``abweichungsgruende``: warum ein Posten vom Plan abwich, in den Worten
      der Verwaltung (Abschnitt 6.3.1 des Jahresabschlusses),
    - ``pruefberichte``: Fundstelle des RPA-Schlussberichts je Jahrgang,
    - ``herkunft``: je ``herkunft_id`` das Dokument, die Fundstelle darin, die
      bestandene Rechenprobe samt Messwert und der Stichtag — nachschlagbar
      über die ``herkunft_id`` der einzelnen Datenzeilen,
    - ``produkt_jahre``: Jahre, für die die Produktebene vorliegt,
    - ``plan_ist_jahre``: Jahre mit „geplant gegen tatsächlich" je Teilhaushalt,
    - ``ausgabenreihe``: die lange Reihe aus Datensatz 1102 — ein Betrag je
      Jahr seit 1972. ``zeilen`` trägt je Jahrgang ``regelwerk`` (die Naht
      2009/2010), die bestandenen ``proben`` und, wo die beiden Quellen sich
      widersprechen, den Betrag der unterlegenen (``konflikt_betrag``).
      ``regelwerke`` nennt zu jedem Regelwerk den Titel der Quelle und ihre
      Abgrenzung — **beide gehören an jede Anzeige**: Links der Naht steht das
      Anordnungssoll des Verwaltungshaushalts, rechts die ordentlichen
      Aufwendungen der Gesamtergebnisrechnung, und über den Schnitt darf keine
      Linie laufen. Eine Einwohnerzahl liefert dieser Block bewusst nicht
      (Begründung an der Tabelle in ``council/store.py``).
    - ``spenden``: was die Stadt an Zuwendungen annimmt, aus den
      Ratsbeschlüssen. ``jahre`` ist die Reihe (Betrag, Zahl der Vorlagen,
      Aufteilung Rat/Verwaltungsausschuss), ``vorlagen`` die einzelnen
      Beschlüsse mit ihrer Vorlagen-Nummer, ``ohne_beleg`` die Zeilen, die
      ihre Zweitstelle **nicht** tragen — samt dem Satz, warum. Die
      ``schwellen`` sagen, wer über welche Zuwendung entscheidet.
      **Die Namen der Gebenden liefert dieser Block nicht**, und das ist
      keine Lücke, die sich schließt: Sie stehen nur in der Anlage
      „Zuwendungsliste", die nicht im Bestand ist (``council/spenden.py``).
    - ``steuerplan``: je Steuerart und Jahr der Ansatz des Haushaltsplans neben
      dem Rechnungsergebnis (Jahrbuch-Tabelle 1103). ``vorlaeufig`` ist die
      Angabe der Quelle über sich selbst — die jüngste Spalte heißt dort
      „vorläufiges Rechnungsergebnis". Die ``art``-Werte sind **dieselben** wie
      in ``steuern``; daran hängt die Prüfung der Jahresbeschriftung.
    - ``hebesaetze``: die Realsteuer-Hebesätze je **Änderungsjahr** seit 1980
      (Tabelle 1105). Die Jahre dazwischen fehlen nicht, sie ändern nichts —
      ein Satz gilt bis zur nächsten Änderung. Wer die Reihe zeichnet, zeichnet
      eine Treppe und interpoliert nicht. ``bemessung_neu`` nennt die Jahre, in
      denen sich die Bemessungsgrundlage mitänderte; **ohne diese Angabe darf
      kein Hebesatz-Sprung angezeigt werden**, denn 2025 stieg der Satz um
      21 %, während das Aufkommen um 4,6 % sank.
    - ``gewerbesteuerstatistik``: wie viele Betriebe und Betriebsstätten in
      Oldenburg erfasst sind, wie viele davon überhaupt einen Steuermessbetrag
      haben, und wie sich dieser auf reine Festsetzungen und Zerlegungen
      verteilt (Landesamt für Statistik, Bericht L IV 13). **Das ist die
      Veranlagung, nicht das Aufkommen**: Messbetrag mal Hebesatz ergibt nicht
      die Zahl aus ``steuern`` — in den drei prüfbaren Jahren lagen beide
      zwischen 13 % darunter und 27 % darüber. ``abgrenzung`` sagt das im
      Klartext und reist deshalb mit den Zahlen mit.

    Fehlende Jahre (Datenlücken) fehlen schlicht in ``jahre`` — das Frontend
    zeigt Lücken ehrlich, statt zu interpolieren.

    ``felder`` schneidet die Antwort auf das zu, was die aufrufende Seite
    wirklich rendert (kommagetrennt, z. B. ``?felder=jahre,produkt_jahre``).
    ``thh_posten`` schneidet zusätzlich INNERHALB der Ergebnisrechnung — sie
    ist der größte Block, und ihre Teilhaushalts-Ebene braucht fast niemand
    vollständig (s. :func:`_ergebnisrechnung`).
    Ohne den Parameter kommt alles — der Vertrag von vorher gilt unverändert
    weiter. Die Werte sind hier bewusst **Bauanweisungen** und keine fertigen
    Listen: Ein nicht angefordertes Feld soll nicht nur ungesendet bleiben,
    sondern gar nicht erst aus der Datenbank gelesen werden.
    """
    bausteine: dict[str, Callable[[], object]] = {
        "jahre": lambda: {str(y): store.get_haushalt(y) for y in store.haushalt_years()},
        "steuern": store.get_steuereinnahmen,
        "steuerkraft": store.get_steuerkraft,
        # Die Zeile darüber ist unvollständig, und zwar systematisch: Der
        # Open-Data-Datensatz 1106 führt nur zwei der drei Komponenten des
        # Finanzausgleichs (Gemeinde- und Kreisaufgaben). Die dritte —
        # Zuweisungen für Aufgaben des übertragenen Wirkungskreises, rund 13 %
        # der Summe — steht nur beim Land. Sie kommt hier als eigenes Feld
        # dazu, in **Tausend Euro** und mit der Jahresangabe des Landes
        # (Ausgleichsjahr). Näheres in council/steuerkraft.py.
        "finanzausgleich": store.get_finanzausgleich,
        "einwohner": store.einwohner_aktuell,
        # Aus den Jahresabschlüssen (RIS-Anlagen): Ansatz UND Ergebnis je
        # Posten — „geplant gegen tatsächlich" und die Erträge nach Arten.
        # `plan` ist die Bezugsgröße der Abweichung, `ansatz` der
        # ursprüngliche Haushaltsansatz; `plan_art` sagt, welche gemeint ist.
        "ergebnisrechnung": lambda: _ergebnisrechnung(store, thh_posten),
        # Dieselben Dokumente, Abschnitt 4.1: was tatsächlich geflossen ist.
        # Die Ergebnisrechnung darüber weist für 2024 einen Überschuss aus,
        # diese Tabelle im selben Heft einen Finanzmittel-Fehlbetrag — beides
        # stimmt, und ohne die zweite Zahl entsteht ein falscher Eindruck.
        "finanzrechnung": store.get_finanzrechnung,
        # Die Planjahre: dieselbe Postengliederung für Jahre, die noch keinen
        # Abschluss haben. `art` trennt den Haushaltsansatz von der
        # mittelfristigen Finanzplanung — ohne diese Angabe darf keine Zahl
        # aus dieser Liste angezeigt werden.
        "ergebnishaushalt": store.get_ergebnishaushalt,
        # Überschussrücklage aus der Bilanz: Position 1.2.1 plus das am
        # Stichtag noch separat ausgewiesene Jahresergebnis. Keine Konstante.
        "ruecklage": store.get_ruecklagen,
        "ansatz_jahre": store.ansatz_jahre,
        # Die Wirtschaftspläne der Eigenbetriebe und städtischen Gesellschaften
        # — der Haushalt NEBEN dem Haushalt. Klein genug für die Übersicht (29
        # Zeilen), deshalb kein eigener Endpunkt.
        #
        # `ertraege` und `aufwendungen` sind oft NULL, und das ist die Auskunft
        # und keine Lücke: Nur zwei der sechs Betriebe nennen in einer prüfbaren
        # Form ein Erträge/Aufwendungen-Paar, die übrigen nur das beschlossene
        # Jahresergebnis. Wer die Spalten anzeigt, muss die Leerstellen
        # anschreiben, statt eine 0 zu zeichnen.
        # Die Gebührenbedarfsberechnung — woraus die Abfall- und
        # Straßenreinigungsgebühren entstehen.
        #
        # `gebuehr` und `bezugsmenge` sind bei der Abfallsammlung NULL, und das
        # ist die Auskunft: Sie erhebt eine Grundgebühr UND eine Gebühr je
        # Liter, dort gibt es keine einzelne Division. Wer die Spalte anzeigt,
        # schreibt die Leerstelle an, statt eine 0 zu zeichnen.
        "gebuehren": store.get_gebuehren,
        "gebuehrensaetze": store.get_gebuehrensaetze,
        # Die Haushaltssatzung — der Rahmen um den Plan (Kreditermächtigung,
        # Dispo-Höchstbetrag, Verpflichtungsermächtigungen, Finanzhaushalt).
        #
        # `fassung` GEHÖRT AN JEDE ANZEIGE. Im Ratsinformationssystem liegen
        # ausschließlich Verwaltungsentwürfe; die beschlossene Satzung
        # erscheint im Amtsblatt. Wer das Feld wegblendet, macht aus einem
        # Vorschlag der Verwaltung einen Ratsbeschluss.
        "haushaltssatzung": store.get_haushaltssatzungen,
        "wirtschaftsplaene": store.get_wirtschaftsplaene,
        "abweichungsgruende": store.get_abweichungsgruende,
        "pruefbericht_quellen": store.get_pruefbericht_quellen,
        "produkt_jahre": store.produkte_jahre,
        # Jahre mit Teilhaushalts-Ist — füttert den Jahr-Umschalter auf
        # /haushalt/plan-ist, ohne dass das Frontend die Liste durchsucht.
        "plan_ist_jahre": store.plan_ist_jahre,
        # Die lange Reihe seit 1972. Die Begriffe reisen mit den Zahlen, statt
        # im Frontend zu stehen: Sie sind Angaben der Quelle wie der Betrag
        # selbst, und eine Legende, die es in zwei Sprachen gibt, driftet.
        "ausgabenreihe": lambda: {
            "zeilen": store.get_ausgabenreihe(),
            "naht_ab": ausgabenreihe_mod.NAHT_AB,
            "regelwerke": {
                r: {"label": ausgabenreihe_mod.REGELWERK[r],
                    "titel": ausgabenreihe_mod.TITEL[r],
                    "abgrenzung": ausgabenreihe_mod.ABGRENZUNG[r]}
                for r in ausgabenreihe_mod.REGELWERK
            },
        },
        # Die dreizehn Kennzahlen des Rechenschaftsberichts. Drei Listen, und
        # jede hat ihren eigenen Grund:
        #
        # `reihe` ist die Anzeigereihe — je Kennzahl und Jahr der Wert aus dem
        # JÜNGSTEN Bericht, der ihn druckt. `staende` ist die Belegkette: alle
        # Stände aller sechs Berichte, aus denen sich `reihe` ergibt. Ohne die
        # zweite Liste könnte niemand nachvollziehen, dass die Steuerquote
        # 2021 einmal 49,05 % hieß.
        #
        # `formeln` sind die von der Stadt GEDRUCKTEN Rechenwege, im Wortlaut.
        # Sie tragen `fassung`: Wechselt die Nummer zwischen zwei Berichten,
        # darf über die Stelle keine Linie laufen.
        #
        # `funde` sind die Unterschiede zwischen zwei Berichten, eingeteilt in
        # Korrektur, Definitionswechsel und bloße Umbenennung — gemessen, nicht
        # angenommen (council/kennzahlen.py).
        "kennzahlen": lambda: _kennzahlen(store),
        # Nachbewilligungen nach § 117 NKomVG — was beschlossen wurde,
        # nachdem der Haushalt beschlossen war. Zwei Listen, die **nicht**
        # ineinander gerechnet werden dürfen:
        #
        # `serie` ist unser Bestand aus dem Ratsinformationssystem, je Vorlage
        # eine Zeile (nicht je Beschlusszeile — Finanzausschuss und Rat
        # entscheiden dieselbe Sache, und 131 der 287 Zeilen sind Dubletten).
        # `beschluss_id` zeigt auf die vorhandene Beschluss-Seite.
        #
        # `jahre` ist Kapitel 3 des Rechenschaftsberichts mit seinen **vier
        # Entscheidungswegen**. Nur dort steht die Gesamtsumme; der Rat ist
        # eine Teilmenge davon, und sie schrumpft (88 → 73 %). Eine Anzeige,
        # die nur `serie` zeigt, muss das dazusagen.
        #
        # `verpflichtungen_betrag` steht bewusst getrennt und gehört in
        # **keine** Summe: Eine Verpflichtungsermächtigung bindet künftige
        # Jahre, sie fließt nicht in diesem. Der Bericht zählt sie ebenso
        # getrennt.
        "nachbewilligungen": lambda: {
            "serie": store.get_nachbewilligungen(),
            "jahre": store.get_nachbewilligung_jahre(),
            "kanaele": nachbewilligungen_mod.KANAELE,
        },
        # Zuwendungen an die Stadt. `ohne_beleg` reist mit den Zahlen mit,
        # damit die Seite die Lücke anschreiben kann, statt sie stillschweigend
        # aus der Summe zu lassen — sechs Zeilen, jede mit ihrem Grund.
        "spenden": lambda: {
            "jahre": _spenden_jahre(store.get_spenden()),
            "vorlagen": store.get_spenden(),
            "ohne_beleg": store.get_spenden_verworfen(),
            "schwellen": [{"gremium": g, "ab": unten, "bis": oben}
                          for g, unten, oben in spenden_mod.SCHWELLEN],
        },
        # Die beiden Steuertabellen des Jahrbuchs (council/steuertabellen.py).
        # Sie gehören zusammen in EINEN Block, weil sie auf derselben Seite
        # zusammen gelesen werden: Ein Hebesatz ohne das Aufkommen daneben ist
        # irreführend (2025: Satz +21 %, Aufkommen −4,6 %).
        #
        # `abgrenzung` reist mit den Zahlen, nicht im Frontend — dieselbe Regel
        # wie bei `ausgabenreihe.regelwerke`: Eine Legende, die es in zwei
        # Sprachen gibt, driftet.
        "steuerplan": lambda: {
            "zeilen": store.get_steuerplan(),
            "abgrenzung": steuertabellen.ABGRENZUNG_1103,
        },
        "hebesaetze": lambda: {
            # NUR die Änderungsjahre — die Jahre dazwischen fehlen nicht,
            # sondern haben nichts geändert. Wer diese Reihe zeichnet, zeichnet
            # eine TREPPE: Ein Satz gilt bis zur nächsten Änderung, und
            # zwischen zwei Stufen wird nicht interpoliert.
            "zeilen": store.get_hebesaetze(),
            "abgrenzung": steuertabellen.ABGRENZUNG_1105,
            # Jahre, in denen sich die BEMESSUNGSGRUNDLAGE mitänderte. Ohne
            # diese Angabe liest sich „Hebesatz +21 %" als „alle zahlen 21 %
            # mehr", und das war 2025 nachweislich falsch.
            "bemessung_neu": steuertabellen.BEMESSUNG_NEU,
        },
        # Der Nenner zur Gewerbesteuer: wie viele Betriebe sie aufbringen.
        # Nur Oldenburg, obwohl die Tabelle alle acht kreisfreien Städte führt
        # — diese Seite ist ein Steckbrief und kein Vergleich, und die sieben
        # anderen Städte wären hier Ballast, den niemand rendert.
        "gewerbesteuerstatistik": lambda: {
            "zeilen": store.get_gewerbesteuerstatistik(gewst.OLDENBURG),
            # Zwei Fassungen: `abgrenzung_kurz` ist der eine Satz, ohne den die
            # Zahlen irreführen, und steht auf der Seite immer; `abgrenzung`
            # setzt ihn fort und darf eingeklappt sein. Warum die Aufteilung
            # hier liegt und nicht im Frontend, steht im Modulkopf.
            "abgrenzung_kurz": gewst.ABGRENZUNG_KURZ,
            "abgrenzung": gewst.ABGRENZUNG,
        },
    }

    gewuenscht = {f.strip() for f in (felder or "").split(",") if f.strip()}
    unbekannt = sorted(gewuenscht - set(bausteine) - {"herkunft"})
    if unbekannt:
        # Lieber ein lauter Fehler als eine Seite, der still ein Block fehlt:
        # Ein Tippfehler im `felder`-Wert wäre sonst nicht von „dieses Feld ist
        # eben leer" zu unterscheiden — und leere Blöcke sind in diesem Bereich
        # eine Aussage über die Daten, keine über den Aufruf.
        raise HTTPException(400, f"Unbekannte Felder: {', '.join(unbekannt)}")

    daten = {name: bau() for name, bau in bausteine.items()
             if not gewuenscht or name in gewuenscht}
    # Woher jede dieser Zeilen stammt: je Dokument-und-Abschnitt ein Eintrag
    # mit Fundstelle, bestandener Rechenprobe und der stabilen `document_id`.
    # Die Datenzeilen verweisen per `herkunft_id` darauf. Als eigene Liste
    # statt an jede Zeile gehängt: Ein Jahrgang teilt sich eine Herkunft über
    # rund 200 Posten.
    #
    # Es reisen NUR die Einträge mit, auf die eine gesendete Zeile zeigt. Bis
    # 08/2026 ging die vollständige Tabelle mit — bei 937 Einträgen waren das
    # 753 KB, von denen 643 Einträge (69 %) zu Zeilen gehörten, die dieser
    # Endpunkt gar nicht liefert; sie stammen aus den neun Unter-Endpunkten,
    # die ihre Herkunft längst so einschränken. Unsichtbar ist das, weil die
    # Karte nirgends durchlaufen, sondern ausschließlich per `herkunft_id`
    # nachgeschlagen wird (`lib/herkunft.ts`).
    #
    # Ohne `felder` bleibt sie drin, weil der Vertrag von vorher weitergilt.
    #
    # ZWEI WEGE ZUM SELBEN ZWECK, und beide werden gebraucht. Der ältere hängt
    # am Quellen-SCHLÜSSEL: `/haushalt/dokumente` liefert je Quellenart und
    # Jahrgang das Dokument, und daran hängt der nummerierte Beleg-Chip. Das
    # genügt, solange ein Jahrgang ein Papier hat.
    #
    # Wo er das nicht tut, genügt es nicht — und `/haushalt/betriebe` ist
    # dieser Fall: Ein Jahrgang Wirtschaftsplan besteht aus bis zu sieben
    # Plänen von sieben Betrieben, jeder ein eigenes Papier. Der Chip zeigte
    # dort auf „irgendeines davon", und im Verzeichnis stand eine einzige
    # Quelle für 33 Dokumente (Tim, 21.08.2026). Deshalb fordert diese Seite
    # seit dem 21.08. `herkunft` an und belegt jede Karte mit der Zeile, aus
    # der sie stammt (`components/haushalt/quelle.tsx: Dokumentbeleg`).
    #
    # Die Karte reist dabei nicht als Ganzes: Es gehen nur die Einträge mit,
    # auf die eine gesendete Zeile zeigt — bei `felder=wirtschaftsplaene`
    # sind das keine 40.
    if not gewuenscht or "herkunft" in gewuenscht:
        daten["herkunft"] = {str(h["id"]): h
                             for h in store.get_herkunft(sorted(_herkunft_ids(daten)))}
    return daten


def _kennzahlen(store: CouncilStore) -> dict:
    """Die Kennzahlen als Anzeigereihe, Rechenwege und Funde.

    Die Einteilung der Funde entsteht **hier** und nicht im Frontend: Sie
    hängt an der gedruckten Genauigkeit und an der Fassungsnummer, also an
    zwei Angaben, die mit den Daten kommen. Eine zweite Fassung derselben
    Regel im Browser wäre eine, die driftet.

    ZUR NUTZLAST. Roh sind es 136 KB — 365 Stände, jeder mit Label, Einheit
    und Zeitstempel, dazu 69 Rechenwege (sechs Berichte mal zwölf). Gesendet
    werden 25 KB, und zwar ohne dass etwas fehlt:

    * Die Label stehen **einmal** in ``label`` statt 365-mal in den Zeilen.
    * Die Rechenwege werden zu ihren Fassungen zusammengezogen: Sechs
      Berichte drucken denselben Satz sechsmal. Eine Fassung mit „gilt vom
      Bericht X bis Y" sagt mehr als sechs gleiche Zeilen.
    * Die älteren **Stände** entfallen. Was sie beweisen, steht vollständig
      in ``funde``: jeder Unterschied zwischen zwei Berichten, mit beiden
      Werten und beiden Berichtsjahren. Wer alle Stände braucht, liest
      ``council_kennzahlen`` — die Tabelle behält sie.
    """
    staende = store.get_kennzahlen()
    _, funde = kennzahlen_mod.ueberlappungsprobe(staende)

    fassungen: dict[tuple[str, int], dict] = {}
    for f in store.get_kennzahl_formeln():
        schluessel = (f["kennzahl"], f["fassung"])
        eintrag = fassungen.get(schluessel)
        if eintrag is None:
            fassungen[schluessel] = {
                "kennzahl": f["kennzahl"], "fassung": f["fassung"],
                "ueberschrift": f["ueberschrift"], "formel": f["formel"],
                "von_bericht": f["bericht_jahr"], "bis_bericht": f["bericht_jahr"],
                "herkunft_id": f["herkunft_id"]}
        elif f["bericht_jahr"] > eintrag["bis_bericht"]:
            # Der jüngste Bericht gibt Wortlaut und Beleg — er ist der, den
            # jemand aufschlägt, wenn er nachsehen will.
            eintrag.update(bis_bericht=f["bericht_jahr"], formel=f["formel"],
                           ueberschrift=f["ueberschrift"],
                           herkunft_id=f["herkunft_id"])
        else:
            eintrag["von_bericht"] = min(eintrag["von_bericht"], f["bericht_jahr"])

    return {
        "label": {k.key: k.label for k in kennzahlen_mod.KENNZAHLEN},
        "einheit": {k.key: k.einheit for k in kennzahlen_mod.KENNZAHLEN},
        "reihe": [{"kennzahl": z["kennzahl"], "jahr": z["jahr"], "wert": z["wert"],
                   "stellen": z["stellen"], "fassung": z["fassung"],
                   "bericht_jahr": z["bericht_jahr"], "herkunft_id": z["herkunft_id"]}
                  for z in kennzahlen_mod.neueste(staende)],
        "formeln": sorted(fassungen.values(),
                          key=lambda f: (f["kennzahl"], f["fassung"])),
        "funde": funde,
    }


def _ergebnisrechnung(store: CouncilStore, thh_posten: str | None) -> list[dict]:
    """Die Ergebnisrechnung, auf Wunsch ohne den Teilhaushalts-Ballast.

    Die Tabelle führt zwei Ebenen in einer Liste: die Kernverwaltung
    (``thh_nr`` = ``NULL``) und darunter dieselben Posten je Teilhaushalt. Die
    zweite Ebene ist der Brocken — 1.381 von 1.566 Zeilen, 664 der 751 KB.

    ``thh_posten`` sagt, welche Posten von der **Teilhaushalts-Ebene** gebraucht
    werden; die Kernverwaltung kommt immer vollständig:

    * ohne Angabe — alles, wie bisher (``/haushalt/plan-ist`` braucht es),
    * ``keine`` — nur die Kernverwaltung (185 Zeilen, 87 KB),
    * ``20`` oder ``12,20`` — nur diese Posten je Teilhaushalt.

    Der letzte Fall ist der wichtigste: Das Flussbild der Übersicht zeichnet
    rechts die Aufwendungen je Teilhaushalt, also **einen** Posten (Nr. 20).
    Es braucht die Ebene, aber nicht ihre 170 Zeilen je Jahr — mit
    ``thh_posten=20`` sind es 134 statt 751 KB, und das Bild ist dasselbe.

    Der Parameter benennt bewusst DATEN und keine Ansicht („fluss", „labor"):
    Eine Seite, die morgen einen zweiten Posten zeichnet, ändert eine Zahl in
    ihrer Feldliste — nicht den Endpunkt.
    """
    zeilen = store.get_ergebnisrechnung()
    if thh_posten is None:
        return zeilen
    if thh_posten.strip().lower() in {"keine", "kein", ""}:
        erlaubt: set[int] = set()
    else:
        try:
            erlaubt = {int(p) for p in thh_posten.split(",") if p.strip()}
        except ValueError:
            raise HTTPException(400, f"thh_posten erwartet Postennummern: {thh_posten}") from None
    return [z for z in zeilen
            if z.get("thh_nr") is None or z.get("nr") in erlaubt]


def _herkunft_ids(obj: object) -> set[int]:
    """Jede ``herkunft_id``, die irgendwo in einer Antwort steckt.

    Rekursiv und nicht als Aufzählung der bekannten Blöcke: Die Übersicht führt
    19 davon, teils zwei Ebenen tief (``nachbewilligungen.jahre[].kanaele[]``).
    Eine Liste zum Nachpflegen wäre die Sorte Code, die beim nächsten Block
    vergessen wird — und der Fehler fiele erst auf, wenn irgendwo ein
    Beleg-Chip fehlt. ``herkunft_id`` ist repo-weit der einzige Feldname, der
    auf diese Tabelle zeigt (geprüft), also findet der Lauf alles."""
    if isinstance(obj, dict):
        gefunden: set[int] = set()
        for schluessel, wert in obj.items():
            if schluessel == "herkunft_id":
                if wert is not None:
                    gefunden.add(int(wert))
            else:
                gefunden |= _herkunft_ids(wert)
        return gefunden
    if isinstance(obj, (list, tuple)):
        return set().union(*(_herkunft_ids(x) for x in obj)) if obj else set()
    return set()


def _spenden_jahre(vorlagen: list[dict]) -> list[dict]:
    """Die Jahresreihe aus den Vorlagen — im Backend, nicht in der Tabelle.

    Gespeichert ist je Vorlage eine Zeile; die Jahressumme daraus zu bilden
    ist billig und hält die Tabelle frei von einer abgeleiteten Größe, die bei
    jedem Lauf neu stimmen müsste."""
    jahre: dict[int, dict] = {}
    for v in vorlagen:
        e = jahre.setdefault(v["jahr"], {"jahr": v["jahr"], "betrag": 0.0, "vorlagen": 0,
                                         "rat": 0, "verwaltungsausschuss": 0})
        e["betrag"] += v["betrag"]
        e["vorlagen"] += 1
        if v.get("gremium") == "Rat":
            e["rat"] += 1
        elif v.get("gremium") == "Verwaltungsausschuss":
            e["verwaltungsausschuss"] += 1
    for e in jahre.values():
        e["betrag"] = round(e["betrag"], 2)
    return [jahre[j] for j in sorted(jahre)]


@router.get("/haushalt/weg")
def haushalt_weg(
    jahr: int | None = None,
    _user: dict = Depends(require_active),
    store: CouncilStore = Depends(get_council_store),
) -> HaushaltWeg:
    """Der Weg eines Haushalts durch den Rat — wann welche Station war.

    Anders als der Rest des Haushalts-Bereichs kommt hier nichts aus einem
    Finanzdokument, sondern alles aus den Ratsdaten: Beratungsfolge,
    Tagesordnung und Protokoll-Beschluss. Je Haushaltsjahr eine ``runde`` mit
    ``einbringung``, ``fachausschuesse`` (Zeitraum und Gremien) und
    ``stationen`` bis zur Entscheidung im Rat; jede Station trägt ``ksinr``
    und ``top``, ist also auf ihre Sitzung verlinkbar.

    **Ohne ``jahr`` kommen alle Jahrgänge.** Das ist Absicht: Die Aussage
    dieser Seite liegt nicht im einzelnen Jahr, sondern in der Streuung — dass
    der Entwurf verlässlich im Oktober kommt, die Entscheidung aber zwischen
    Dezember und Februar wandert, sieht man erst über acht Jahrgänge. Eine
    Seite, die das behaupten will, braucht sie alle gleichzeitig; ein
    Jahres-Umschalter, der je Klick nachlädt, wäre acht Anfragen für 30 Zeilen.
    ``jahr`` grenzt trotzdem ein, wenn jemand nur eine Runde braucht.

    Was hier **nicht** steht: die Termine der laufenden Runde.
    ``council_scheduled_sessions`` kennt keine Tagesordnung — wir können nicht
    sagen, welche der kommenden Sitzungen die Haushaltssitzung wird, und raten
    es auch nicht."""
    return {"runden": store.haushalt_weg(jahr)}


@router.get("/haushalt/streit")
def haushalt_streit(
    jahr: int | None = None,
    _user: dict = Depends(require_active),
    store: CouncilStore = Depends(get_council_store),
) -> HaushaltStreit:
    """Der Streit ums Geld — die Auseinandersetzung um jeden Haushaltsjahrgang.

    Je Haushaltsjahr eine ``runde`` mit ihren Stationen (Finanzausschuss und
    Rat), und je Station die Änderungslisten, die Debatte und die
    Schlussabstimmung. Alles kommt aus den Ratsdaten: Beschlusszeilen,
    Anwesenheitsliste und Protokoll-Volltext derselben Sitzung.

    **Ohne ``jahr`` kommen alle Jahrgänge** — wie bei ``/haushalt/weg``, und
    aus demselben Grund: Dass sich die Mehrheiten verschieben, sieht man erst
    über die Jahre. Die Antwort ist entsprechend groß (rund ein halbes MB);
    die Seite lädt sie einmal und schaltet danach ohne Netz zwischen den
    Jahrgängen um.

    Was hier **nicht** steht: der Inhalt der Änderungslisten — den liefert
    seit 08/2026 ``/haushalt/aenderungslisten`` (direkt darunter), Position
    für Position aus den gelesenen EHH-Dokumenten. Hier bleibt die
    Verfahrens-Ebene: **wer** was einbrachte und **ob** es durchkam."""
    return {"runden": store.haushalt_streit(jahr)}


@router.get("/haushalt/aenderungslisten")
def haushalt_aenderungslisten(
    _user: dict = Depends(require_active),
    store: CouncilStore = Depends(get_council_store),
) -> HaushaltAenderungslisten:
    """Der Inhalt der Änderungslisten — die Ebene unter ``/haushalt/streit``.

    Dort steht, WER eine Liste einbrachte und ob sie durchkam; hier steht,
    was drinstand: je Dokument (Verw. I–III und die Beschluss-Datei des
    Finanzausschusses) die Einzelpositionen samt der „Zusammenstellung der
    Veränderungen", gegen die jede Positionsliste beim Einlesen bewiesen
    wurde (``council/aenderungslisten.py``).

    - ``zeilen``: NUR die Positionen des Haushaltsjahrgangs selbst
      (``jahr == jahrgang``). Dieselbe Maßnahme steht im Dokument je
      Finanzplanungsjahr noch einmal — für die Streit-Erzählung zählt das
      Jahr, um das gestritten wurde; die Folgejahre stecken kompakt in den
      Summen. ``urheber`` trägt, WER die Position vorschlug — gefüllt nur
      beim Jahrgang 2021, dessen Beschluss-Datei als einzige eine Spalte
      „Vorschlag von“ führt; sonst ``null``.
    - ``summen``: die Zusammenstellungen ALLER Planjahre, inklusive der
      Zeilen, die es nur dort gibt: die politisch beschlossene Änderung mit
      Urheber-Label („SPD/CDU/FDP …“) aus den AFB-Dateien — der einzige
      digitale Beleg der Fraktionslisten, die selbst Tischvorlagen blieben.
    - ``herkunft``: je ``herkunft_id`` das Papier, aus dem eine Zeile stammt.
    """
    d = store.get_haushalt_aenderungen()
    zeilen = [z for z in d["zeilen"] if z["jahr"] == z["jahrgang"]]
    ids = sorted({z["herkunft_id"] for z in zeilen if z["herkunft_id"] is not None}
                 | {s["herkunft_id"] for s in d["summen"] if s["herkunft_id"] is not None})
    return {"zeilen": zeilen, "summen": d["summen"],
            "herkunft": {str(h["id"]): h for h in store.get_herkunft(ids)}}


# Ohne Anmeldung lesbar (s. `decision_detail`) — die Beschluss-Seite zieht die
# Sitzung nach, um Gremium und Datum zu benennen.
@router.get("/session/{ksinr}")
def session_detail(
    ksinr: int,
    store: CouncilStore = Depends(get_council_store),
) -> SitzungsDetail:
    session = store.get_session(ksinr)
    if not session:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Sitzung nicht gefunden.")
    session["agenda_items"] = store.agenda_items(ksinr)
    # Past sessions may have a parsed protocol → enrich with decisions + attendance.
    session["decisions"] = store.get_decisions(ksinr)
    session["attendance"] = store.get_attendance(ksinr)
    session["has_protocol"] = store.has_protocol(ksinr)
    session["url"] = _ratsinfo_url(ksinr)
    # „Zuletzt geändert" (Tims Wunsch 18.08.): Die Push zur Änderungsmeldung
    # sagt nur noch den Satz — die Einzelheiten stehen hier, aus der Chronik.
    session["aenderungen"] = _agenda_aenderungen(store, ksinr)
    return session


def _agenda_aenderungen(store: CouncilStore, ksinr: int) -> list[dict]:
    from council.agenda_diff import diff_satz, diff_zeilen

    out: list[dict] = []
    try:
        for c in store.agenda_changes(ksinr, limit=3):
            zeilen = diff_zeilen(c["diff"])
            if zeilen:
                out.append({"changed_at": c["changed_at"],
                            "satz": diff_satz(c["diff"]), "zeilen": zeilen})
    except Exception:  # noqa: BLE001 — Chronik ist Zusatz, nie 404/500 der Sitzung
        _log.exception("agenda_aenderungen fehlgeschlagen für %s", ksinr)
    return out


@router.get("/decisions")
def decisions(
    q: str = "",
    committee: str = "",
    outcome: str = Query("", pattern="^(|angenommen|abgelehnt|vertagt|zur_kenntnis|kein_beschluss)$"),
    faction: str = "",
    date_from: str = "",
    date_to: str = "",
    kind: str = Query("", pattern="^(|decision|subvote)$"),
    category: str = Query("", pattern="^(|vote|report)$"),
    sort: str = Query("date_desc", pattern="^(date_desc|date_asc|faction|importance|interest)$"),
    field: str = "",
    party: str = "",
    district: str = Query("", max_length=100),
    location: str = Query("", max_length=120),
    # Design 23a: Standard blendet Änderungsanträge (subvotes) aus der Trefferliste
    # aus — sie hängen als Kontext am Ursprungsbeschluss. Rechercheure können sie
    # per Filter „Änderungsanträge einzeln zeigen" wieder einblenden.
    include_subvotes: bool = Query(False),
    # Design 28a/S4: Auf die Treffer EINES eigenen Themas einschränken. Damit
    # ersetzt die richtige Suchseite (Filter, Sortierung, Seiten, teilbare URL)
    # den früheren Trefferdialog, der nichts davon konnte.
    topic: int | None = Query(None, ge=1),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: dict = Depends(require_active),
    store: CouncilStore = Depends(get_council_store),
    nwz: Store = Depends(get_store),
) -> BeschlussListe:
    if district:
        place = store.resolve_place(district)
        if not place:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unbekannter Ort.")
        district = place.id
    location_row = store.location_by_slug(location) if location else None
    if location and not location_row:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unbekannter Beschlussort.")
    only_ids: list[int] | None = None
    if topic is not None:
        # Nur eigene Themen — sonst ließe sich über eine fremde id deren
        # Trefferliste abfragen.
        if not nwz.get_topic_for_owner(user["id"], topic):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Thema nicht gefunden.")
        only_ids = [m["decision_id"] for m in nwz.get_topic_decision_matches(topic)]
    total = store.count_decisions(
        q, committee, outcome, faction, date_from, date_to, kind, category, field, party,
        include_subvotes=include_subvotes, only_ids=only_ids, district=district,
        location_slug=location,
    )
    rows = store.search_decisions(q, committee, outcome, faction, date_from, date_to, kind, category,
                                  sort=sort, field=field, party=party, limit=limit, offset=offset,
                                  include_subvotes=include_subvotes, only_ids=only_ids,
                                  district=district, location_slug=location)
    location_matches = store.location_matches_for_decisions(
        [row["id"] for row in rows], district=district, location_slug=location
    )
    # Design 23a: je Beschluss die kompakte Änderungsantrags-Zusammenfassung
    # anhängen (Anzahl · Fraktion · Ergebnis) für die Karten-Unterzeile.
    pairs = [(r["ksinr"], r["item_number"]) for r in rows
             if r.get("kind") == "decision" and r.get("item_number")]
    summaries = store.subvote_summaries(pairs)
    for r in rows:
        if district or location:
            r["location_matches"] = location_matches.get(r["id"], [])
        s = summaries.get((r.get("ksinr"), r.get("item_number")))
        if s:
            r["subvote_summary"] = s
    return {"total": total, "decisions": rows}


@router.get("/decision/{decision_id}")
def decision_detail(
    decision_id: int,
    user: dict | None = Depends(optional_user),
    store: CouncilStore = Depends(get_council_store),
    nwz: Store = Depends(get_store),
) -> BeschlussDetail:
    """Ein Beschluss mit allem Drum und Dran — **ohne Anmeldung lesbar**.

    Teilen ist die Kernhandlung der App, aber wer einen weitergereichten Link
    öffnete, sah zuerst das Registrierungsformular. Das schreckt genau die
    Leute ab, die man gewinnen will: Sie haben noch gar nicht gesehen, wofür
    sich ein Konto lohnen würde.

    Was hier steht, stammt vollständig aus dem amtlichen
    Ratsinformationssystem und ist dort ohnehin für alle einsehbar — es
    entsteht keine neue Öffentlichkeit, nur eine lesbare (dieselbe Abwägung
    wie bei `preview`). Persönliches bleibt draußen: ``follow`` kommt nur
    dazu, wenn wirklich jemand angemeldet ist.
    """
    d = store.get_decision(decision_id)
    if not d:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Beschluss nicht gefunden.")
    attendance = store.get_attendance(d["ksinr"])
    # Anwesende Stimmberechtigte — für den Hinweis „einstimmig → diese
    # Fraktionen waren da". `faction_label` statt `normalize_party`: Letzteres
    # kollabiert Rats-GRUPPEN auf eine ihrer Parteien und behauptet damit etwas
    # Falsches über reale Personen — „FDP/Volt" wurde zu „FDP" (Volt fiel weg),
    # „Gruppe DIE LINKE./Piratenpartei" zu „Die Linke" (Piraten fielen weg).
    present = {faction_label(a["party"]) for a in attendance
               if (a.get("role") or "mitglied") in ("vorsitz", "mitglied")}
    present.discard("parteilos")   # keine Fraktion, gehört nicht in die Reihe
    out: dict = {
        "decision": d,
        "attendance": attendance,
        "present_parties": sorted((p for p in present if p), key=order_key),
        "ratsinfo_url": _ratsinfo_url(d["ksinr"]),
        "sub_votes": [],
        "vorlage_journey": [],
        "similar": store.get_similar(decision_id, limit=5),
        "entities": store.entities_for_decision(decision_id),
    }
    # Läuft zu diesem Bauleitplan GERADE eine Beteiligung? Dann gehört der
    # Hinweis samt Frist an den Beschluss — Stellungnahme ist eine der wenigen
    # Handlungen, die Bürger*innen JETZT offenstehen (Stufe 3b).
    try:
        from council import beteiligung as bet_mod
        out["beteiligung"] = next(
            ({"titel": b["titel"], "schritt": b["schritt"], "von": b["von"],
              "bis": b["bis"], "url": b["url"], "status": b.get("status") or "laufend",
              "beendet_am": b.get("beendet_am")}
             # Auch beendete: Sie sind der einzige Ort, an dem eine
             # abgelaufene Beteiligung überhaupt noch dokumentiert ist.
             for b in store.list_beteiligungen(nur_laufende=False)
             if bet_mod.passt_zu_titel(b["plan_nrs"], d.get("title") or "")), None)
    except Exception:  # noqa: BLE001 — Zusatzinfo, nie Blocker
        out["beteiligung"] = None
    # Wichtigkeits-Aufschlüsselung (welche Signale trieben den Score) — erklärt
    # transparent, warum ein Beschluss als wichtig gilt.
    n_ber = len(store.get_beratungen(d["kvonr"])) if d.get("kvonr") else None
    out["importance_breakdown"] = importance.importance_breakdown(d, n_beratungen=n_ber)
    # RL-U16: gleiche 50/50-Mischung wie beim persistierten Wichtig-Wert —
    # sonst zeigten Liste (DB) und Detail (Live-Heuristik) verschiedene Zahlen.
    # `base_score` (Heuristik) und `impact` bleiben einzeln erhalten, damit die
    # Beschluss-Seite die Rechnung offenlegen kann: die vier Signal-Balken
    # erklären nur die Heuristik-Hälfte, nicht den gemischten Endwert.
    # impact_reason erklärt die Tragweite („Warum wichtig: …", Design 13a-B).
    bd = out["importance_breakdown"]
    bd["base_score"] = bd["score"]
    if d.get("impact") is not None:
        bd["impact"] = int(d["impact"])
        bd["score"] = round((bd["base_score"] + bd["impact"]) / 2)
        if d.get("impact_reason"):
            bd["impact_reason"] = d["impact_reason"]
    if d.get("kind") == "decision" and d.get("item_number"):
        out["sub_votes"] = store.get_subvotes(d["ksinr"], d["item_number"])
    if d.get("vorlage_nr"):
        out["vorlage_journey"] = store.vorlage_journey(d["vorlage_nr"])
        out["vorlage_url"] = _vorlage_url(d["kvonr"]) if d.get("kvonr") else None
        # Ingested Vorlage text (Sachverhalt/Begründung) — the why behind the
        # decision. Also our only kvonr source: protocols never carry one.
        v = store.get_vorlage_by_nr(d["vorlage_nr"])
        if v:
            out["vorlage"] = {
                "vorlage_nr": v.get("vorlage_nr"), "title": v.get("title"),
                "art": v.get("art"), "document_url": v.get("document_url"),
                "n_pages": v.get("n_pages"),
                "excerpt": vorlagen_mod.excerpt(v.get("raw_text") or "", 2600) or None,
                # Regex-Ernte: federführendes Amt + Klima-Check der Verwaltung.
                "amt": v.get("amt"),
                "klima_check": v.get("klima_check"),
                "klima_relevant": ernte.klima_relevant(v.get("klima_check")),
                # „Finanzielle Auswirkungen" der Verwaltung — dieselbe
                # Regex-Ernte wie der Klima-Check, auf der Beschluss-Seite als
                # „Was kostet das?" (Design H-21). Amtlicher Wortlaut, deshalb
                # unverändert und als Zitat gekennzeichnet.
                "finanz_check": v.get("finanz_check"),
            }
            if not out["vorlage_url"] and v.get("kvonr"):
                out["vorlage_url"] = _vorlage_url(v["kvonr"])
        out["anlagen"] = store.anlagen_for_vorlage_nr(d["vorlage_nr"])
        # Wo dieser Beschluss im Haushalts-Bereich wieder auftaucht — belegt
        # über eine echte Verknüpfung, nicht über eine Textsuche. `None` heißt
        # „nirgends nachweisbar", und die Seite lässt die Karte dann weg.
        out["haushalts_anschluss"] = store.haushalts_anschluss(
            d["id"], d.get("vorlage_nr"))
        # P1: gerenderte Planzeichnung (scripts/render_plaene.py) — B-Plan-
        # Beschlüsse leben vom Bild, nicht vom Anlagen-Download. Echte
        # Planzeichnungen vor Mischdokumenten: „Begründung mit Leitplan" hat
        # auch bild=1, zeigt auf Seite 1 aber Begründungstext — alphabetisch
        # gewann „B…" vor „P…" (Review-Befund P3, kvonr 16438/17168).
        def _plan_rang(a: dict) -> int:
            label = (a.get("label") or "").lower()
            return 0 if ("planzeichnung" in label or "plandarstellung" in label) else 1

        bilder = sorted((a for a in out["anlagen"] if a.get("bild") == 1), key=_plan_rang)
        out["plan_bild"] = bilder[0]["document_id"] if bilder else None
        # Offizielle Beratungsfolge aus dem Ratsinfo — reicher als die aus
        # unseren Tagesordnungen abgeleitete Journey (Ergebnis je Station,
        # geplante künftige Beratungen). Die Journey bleibt der Fallback.
        kv = d.get("kvonr") or (v.get("kvonr") if v else None)
        if kv:
            today = date.today().isoformat()
            out["beratungsfolge"] = [
                {**b, "future": bool(b["datum"] and b["datum"] > today)}
                for b in store.get_beratungen(kv)
            ]
            # Design 28a/W1: Folgt dieses Konto dem Vorgang schon? Die kvonr
            # gehört zur Antwort, weil nur sie den Vorgang eindeutig benennt —
            # die Vorlagen-Nummer wird im Ratsinfo wiederverwendet.
            # Ohne Anmeldung fehlt der Schlüssel ganz: Das Frontend blendet den
            # Verfolgen-Knopf über `data.follow &&` aus, ohne etwas zu wissen.
            if user:
                out["follow"] = {"kvonr": kv, "following": nwz.is_following_vorlage(user["id"], kv)}
    return out


# ---- „Meine Gespräche" (5a/I-04 + Design 6a) --------------------------------


class GespraechEinstellungBody(BaseModel):
    an: bool


@router.get("/gespraeche")
def gespraeche_liste(limit: int = Query(30, ge=0, le=100),
                     offset: int = Query(0, ge=0),
                     q: str | None = Query(None, max_length=120),
                     user: dict = Depends(require_active),
                     nwz: Store = Depends(get_store)) -> GespraecheListe:
    """Einwilligungs-Stand + eine Seite der gespeicherten Gespräche.
    `einstellung` ist null, solange die Erstnutzungs-Frage (6a①) nie
    beantwortet wurde.

    Drei Zahlen, weil sie drei Dinge bedeuten: `gesamt` ist der Bestand des
    Kontos (die Anzeige „n gespeichert" und der Zähler am Kopf-Knopf hängen
    daran, nicht an der Seitenlänge), `treffer` gilt zur aktuellen Suche, und
    `weitere` sagt, ob „Ältere anzeigen" noch etwas nachliefert. `limit=0`
    holt nur die Zahlen — so fragt die Konto-Einstellung.
    """
    seite = nwz.qa_gespraeche(user["id"], limit=limit, offset=offset, suche=q)
    treffer = nwz.qa_gespraeche_anzahl(user["id"], suche=q)
    gesamt = nwz.qa_gespraeche_anzahl(user["id"]) if q else treffer
    return {"einstellung": nwz.get_qa_speichern(user["id"]),
            "gespraeche": seite,
            "gesamt": gesamt,
            "treffer": treffer,
            "weitere": offset + len(seite) < treffer}


@router.post("/gespraeche/einstellung")
def gespraeche_einstellung(body: GespraechEinstellungBody,
                           user: dict = Depends(require_active),
                           nwz: Store = Depends(get_store)) -> GespraechEinstellung:
    """6a②: Schalter setzen. Löscht nichts — das entscheidet der Dialog
    über DELETE /gespraeche getrennt."""
    nwz.set_qa_speichern(user["id"], body.an)
    return {"einstellung": 1 if body.an else 0}


@router.get("/gespraeche/{gespraech_id}")
def gespraech_detail(gespraech_id: int, user: dict = Depends(require_active),
                     nwz: Store = Depends(get_store)) -> GespraechDetail:
    g = nwz.qa_gespraech(gespraech_id, user["id"])
    if not g:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Gespräch nicht gefunden.")
    for t in g["turns"]:
        try:
            t["quellen"] = json.loads(t["quellen"]) if t["quellen"] else None
        except ValueError:
            t["quellen"] = None
    return g


class GespraechUmbenennenBody(BaseModel):
    titel: str = Field(min_length=1, max_length=120)


@router.patch("/gespraeche/{gespraech_id}")
def gespraech_umbenennen(gespraech_id: int, body: GespraechUmbenennenBody,
                         user: dict = Depends(require_active),
                         nwz: Store = Depends(get_store)) -> Ok:
    """Design 9a②: Umbenennen aus dem Gespräche-Sheet (Wisch nach links)."""
    if not nwz.qa_gespraech_umbenennen(gespraech_id, user["id"], body.titel):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Gespräch nicht gefunden.")
    return {"ok": True}


@router.delete("/gespraeche/{gespraech_id}")
def gespraech_loeschen(gespraech_id: int, user: dict = Depends(require_active),
                       nwz: Store = Depends(get_store)) -> Ok:
    if not nwz.qa_gespraech_loeschen(gespraech_id, user["id"]):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Gespräch nicht gefunden.")
    return {"ok": True}


@router.delete("/gespraeche")
def gespraeche_alle_loeschen(user: dict = Depends(require_active),
                             nwz: Store = Depends(get_store)) -> GespraecheGeloescht:
    return {"geloescht": nwz.qa_gespraeche_loeschen(user["id"])}


class QaFeedbackBody(BaseModel):
    frage: str = Field(min_length=1, max_length=300)
    antwort_auszug: str | None = Field(default=None, max_length=500)
    bewertung: str = Field(pattern="^(up|down)$")
    grund: str | None = Field(default=None, max_length=500)


@router.post("/qa-feedback", status_code=status.HTTP_201_CREATED)
def qa_feedback(
    body: QaFeedbackBody,
    request: Request,
    user: dict | None = Depends(optional_user),
    store: CouncilStore = Depends(get_council_store),
) -> Ok:
    """Daumen hoch/runter zu einer KI-Antwort (5a/I-03) — der einzige
    Qualitätsmesser außerhalb der Eval-Gold-Fälle. Anonym erlaubt (die
    KI-Frage selbst ist es auch); die Feldlängen begrenzt das Schema, das
    Rate-Limit hält Skript-Flutung von Tabelle und Backups fern."""
    qa_feedback_limiter.check(request)
    store.save_qa_feedback(body.frage, body.antwort_auszug, body.bewertung,
                           body.grund, user_id=(user or {}).get("id"))
    return {"ok": True}


class ParteiMeinungenBody(BaseModel):
    frage: str = Field(min_length=3, max_length=300)
    #: Die Beschlüsse, auf denen die Antwort steht (Reihenfolge = Relevanz).
    #: Über sie kommt die Aussprache dazu, die ZU diesen Stationen gehört —
    #: siehe Kommentar im Endpoint. Leer (ältere Clients) → nur Vektor-Kanal.
    beschluss_ids: list[int] = Field(default_factory=list, max_length=20)


@router.post("/partei-meinungen")
def partei_meinungen_endpoint(
    body: ParteiMeinungenBody,
    request: Request,
    user: dict = Depends(require_active),
    store: CouncilStore = Depends(get_council_store),
) -> ParteiMeinungen:
    """Baustein „Das sagen die Parteien" (Task 30): Wird vom Frontend NACH der
    gestreamten Antwort geladen (kostet die Hauptantwort keine Latenz). Sammelt
    aus ZWEI Kanälen — fraktions-bewusste Ähnlichkeitssuche (Cross-Encoder-
    geprüft) und die Aussprache zu den belegten Beschlüssen — und verdichtet
    das per LLM je Fraktion. Leer ({parteien: []}), wenn die Datenlage zu dünn
    ist — der Baustein erscheint dann nicht."""
    if not user.get("limits_frei"):
        partei_meinungen_limiter.check(request)
    try:
        import hashlib

        from council import embeddings as emb
        # Fraktions-bewusst sammeln (je Fraktion bis 5 Beiträge) — das globale
        # Top-24 bestand zur Hälfte aus Verwaltungs-Beiträgen ohne Fraktion,
        # die „Parteimeinung" war real eine Einzel-Paraphrase (Befund 10.08.).
        hits = emb.search_wortbeitraege_je_fraktion(store, body.frage, body.frage)
        # ZWEITER KANAL: die Aussprache, die zu den belegten Beschlüssen GEHÖRT.
        # Der Vektor-Kanal sucht nach Ähnlichkeit zur Frage und findet damit
        # das Wortfeld — nicht zwingend die Debatte zur Sache. Auf „Was ist die
        # Baumschutzsatzung …?" zeigte die Quellenspalte (die diesen Kanal
        # schon hatte) neun CDU- und zehn SPD-Beiträge, während der Baustein
        # daneben „keine passenden Wortbeiträge von CDU" behauptete (Tims
        # Befund 21.08.2026). Zugehörigkeit ist hier das bessere Signal als
        # Ähnlichkeit — deshalb OHNE Torwächter: Die Station ist ja belegt.
        anker: list[dict] = []
        if body.beschluss_ids:
            try:
                anker = store.wortbeitraege_zu_beschluessen(
                    store.get_decisions_by_ids(body.beschluss_ids[:10]),
                    max_gesamt=60, max_je_top=12)
            except Exception:  # noqa: BLE001 — Anker ist Zusatz, nie Blocker
                anker = []
        # Cache über den Hash der Beitrags-IDs: verschieden formulierte Fragen
        # zum selben Thema (Stadion!) sammeln dieselben Beiträge ein → Treffer
        # ohne LLM-Call; ein neuer Beitrag ändert den Hash → Nachverdichtung.
        # „v3": seit dem Beschluss-Anker — die alten Einträge kennen nur den
        # Vektor-Kanal und sollen nicht 14 Tage weiterleben.
        alle_ids = sorted({wid for wid, _ in hits} | {r["id"] for r in anker})
        schluessel = "v3:" + hashlib.sha1(
            ",".join(str(wid) for wid in alle_ids).encode()).hexdigest()
        meinungen = store.partei_meinungen_cache_get(schluessel) if alle_ids else None
        if meinungen is None and alle_ids:
            vektor = store.wortbeitraege_by_ids([wid for wid, _ in hits])
            schon = {r["id"] for r in vektor}
            rows = vektor + [r for r in anker if r["id"] not in schon]
            # FDP/Volt über die Personen-Stammdaten in Einzel-Parteien
            # auflösen (Tims Standing-Punkt) — der Baustein führt die beiden
            # danach getrennt, statt sie in einen Gruppen-Eimer zu werfen.
            qa.parteien_aufloesen(store, rows)
            meinungen = qa.partei_meinungen(body.frage, rows)
            if meinungen:
                store.partei_meinungen_cache_set(schluessel, body.frage, meinungen)
        # Vollständigkeits-Ehrlichkeit (Tims Direktive 10.08.): Fraktionen, die
        # im Rat aktiv sind, aber ohne passende Wortbeiträge zum Thema — der
        # Baustein sagt das, statt sie stillschweigend wegzulassen. Die
        # FDP/Volt-Gruppe zählt dabei als ihre beiden Einzel-Parteien.
        ohne: list[str] = []
        if meinungen:
            # Beide Seiten durch dieselbe Kanonisierung: Die Anwesenheits-
            # Labels führen auch Verbände, Rollen und kaputte Einzel-Label als
            # „Partei" („ADFC", „Elternvertreter", „BSW Für RH Dr. Onken") —
            # in der Ehrlichkeits-Zeile stehen nur echte Ratsparteien (Tims
            # TestFlight-Feedback 11.08.), und „CDU-Fraktion" dedupliziert
            # gegen „CDU" statt daneben zu erscheinen.
            vertreten = {qa.ratspartei_label(e["partei"]) or qa._fraktions_label(e["partei"])
                         for e in meinungen}
            aktive: list[str] = []
            for x in store.aktive_fraktionen():
                label = qa.ratspartei_label(x)
                # FDP und Volt sitzen diese Ratsperiode als EINE Gruppe: taucht
                # eine der beiden (oder das Gruppen-Label) auf, sind beide
                # aktiv — die Protokolle labeln uneinheitlich mal Gruppe, mal
                # Einzelpartei, und Volt fiele sonst still aus der
                # Ehrlichkeits-Zeile.
                if label in ("FDP/Volt", "FDP", "Volt"):
                    aktive += ["FDP", "Volt"]
                elif label:
                    aktive.append(label)
            gesehen_aktiv: set[str] = set()
            aktive = [f for f in aktive if not (f in gesehen_aktiv or gesehen_aktiv.add(f))]
            ohne = [f for f in aktive if f not in vertreten]
    except Exception:  # noqa: BLE001 — Zusatzbaustein, nie 500 im Gespräch
        _log.exception("partei_meinungen fehlgeschlagen")
        meinungen = None
        ohne = []
    return {"parteien": meinungen or [], "ohne_beitraege": ohne}


class QaShareQuelle(BaseModel):
    id: int
    title: str = Field(max_length=300)
    session_date: str | None = Field(default=None, max_length=10)
    committee: str | None = Field(default=None, max_length=120)
    outcome: str | None = Field(default=None, max_length=40)


class QaShareDebatte(BaseModel):
    sprecher: str | None = Field(default=None, max_length=120)
    partei: str | None = Field(default=None, max_length=60)
    art: str = Field(default="rede", max_length=30)
    top: str | None = Field(default=None, max_length=300)
    auszug: str = Field(default="", max_length=2000)
    committee: str | None = Field(default=None, max_length=120)
    datum: str | None = Field(default=None, max_length=10)
    protokoll_url: str | None = Field(default=None, max_length=500)
    protokoll_seite: int | None = Field(default=None, ge=1, le=9999)

    @field_validator("protokoll_url")
    @classmethod
    def _nur_ratsinfo(cls, v: str | None) -> str | None:
        # Der Snapshot ist öffentlich und der Client liefert die URL mit —
        # als „Protokoll" verlinken wir deshalb ausschließlich das
        # Ratsinfo-System, sonst ließe sich hier Beliebiges unterschieben.
        if v and not v.startswith(f"{BASE_URL}/"):
            return None
        return v


class QaSharePresse(BaseModel):
    titel: str = Field(max_length=300)
    url: str = Field(max_length=500)
    datum: str | None = Field(default=None, max_length=10)


class QaShareAnlage(BaseModel):
    # Beleg-Nummer des Recherche-Berichts („[A1]") — ohne sie findet der
    # Marker im geteilten Text seine Anlage nicht.
    nr: int | None = Field(default=None, ge=1, le=99)
    label: str | None = Field(default=None, max_length=300)
    url: str | None = Field(default=None, max_length=500)
    vorlage_nr: str | None = Field(default=None, max_length=60)
    vorlage_titel: str | None = Field(default=None, max_length=300)
    auszug: str = Field(default="", max_length=600)


class QaShareKernaussage(BaseModel):
    text: str = Field(default="", max_length=600)
    sprecher: str | None = Field(default=None, max_length=120)
    datum: str | None = Field(default=None, max_length=10)


class QaSharePartei(BaseModel):
    partei: str = Field(max_length=60)
    haltung: str | None = Field(default=None, max_length=20)
    position: str = Field(default="", max_length=800)
    einig: bool = True
    hinweis: str | None = Field(default=None, max_length=300)
    kernaussage: QaShareKernaussage | None = None
    beitraege: int = Field(default=0, ge=0)


class QaShareBody(BaseModel):
    frage: str = Field(min_length=1, max_length=300)
    antwort: str = Field(min_length=1, max_length=8000)
    quellen: list[QaShareQuelle] = Field(default_factory=list, max_length=40)
    # Bausteine neben den Beschlüssen: ohne sie zeigte die geteilte Seite
    # weniger als das Gespräch, aus dem sie stammt (Tims Befund 10.08.).
    debatten: list[QaShareDebatte] = Field(default_factory=list, max_length=20)
    presse: list[QaSharePresse] = Field(default_factory=list, max_length=10)
    anlagen: list[QaShareAnlage] = Field(default_factory=list, max_length=10)
    parteien: list[QaSharePartei] = Field(default_factory=list, max_length=12)
    # Die Grafik zur Antwort (council/qa.py, geld_grafik) — als loses dict,
    # weil der Client sie unverändert zurückreicht: Sie stammt aus DIESEM
    # Backend, und ein zweites Schema hier wäre eine Kopie, die driftet.
    # Begrenzt wird trotzdem: höchstens 60 Punkte, nur bekannte Felder.
    grafik: dict | None = None


_SHARE_BLOCKED_PHRASES = (
    "heil hitler",
    "sieg heil",
    "kinderporno",
    "child porn",
    "kill yourself",
    "bring dich um",
)


def _share_text_is_objectionable(text: str) -> bool:
    """Enges Vorab-Filter für absichtlich öffentlich gemachte Snapshots.

    Das Ratsgespräch selbst darf schwierige politische Themen behandeln. Für
    den öffentlichen Link blocken wir deshalb nur sehr eindeutige
    Missbrauchsphrasen sowie eingebettete Web-/Script-Ziele. Amtliche Links
    kommen strukturiert aus den validierten Quellenfeldern, nie aus diesem
    freien Text. Meldung und menschliche Moderation bleiben das zweite Netz.
    """
    folded = unicodedata.normalize("NFKC", text).casefold()
    folded = re.sub(r"\s+", " ", folded)
    if any(phrase in folded for phrase in _SHARE_BLOCKED_PHRASES):
        return True
    return bool(re.search(r"(?:https?://|javascript:|data:text/|<\s*script\b)", folded))


def _grafik_pruefen(g: dict | None) -> dict | None:
    """Nur durchlassen, was eine Grafik aus `geld_grafik` sein kann.

    Der Snapshot ist öffentlich abrufbar, und `grafik` kommt als loses dict
    vom Client — ungeprüft übernommen könnte dort beliebiger Inhalt landen
    und über die Share-Seite ausgeliefert werden. Deshalb: feste Felder,
    feste Typen, begrenzte Längen, alles andere fällt weg.
    """
    if not isinstance(g, dict):
        return None
    try:
        reihe = [{"jahr": int(p["jahr"]), "wert": float(p["wert"])}
                 for p in (g.get("reihe") or [])[:60]]
    except (KeyError, TypeError, ValueError):
        return None
    if len(reihe) < 2:
        return None
    # Der „Mehr dazu"-Link: NUR relative Ziele in den Haushalts-Bereich.
    # Der Snapshot ist öffentlich — ein durchgereichtes href wäre sonst ein
    # Link-Baukasten für beliebige Ziele unter unserem Absender.
    mehr = g.get("mehr")
    if (isinstance(mehr, dict) and isinstance(mehr.get("href"), str)
            and mehr["href"].startswith("/haushalt")):
        mehr = {"href": mehr["href"][:120], "label": str(mehr.get("label") or "")[:120]}
    else:
        mehr = None
    return {"art": str(g.get("art") or "")[:30],
            "titel": str(g.get("titel") or "")[:120],
            "einheit": str(g.get("einheit") or "")[:20],
            "nachkomma": max(0, min(int(g.get("nachkomma") or 0), 3)),
            "reihe": reihe,
            "hinweis": (str(g["hinweis"])[:500] if g.get("hinweis") else None),
            "quelle": (str(g["quelle"])[:200] if g.get("quelle") else None),
            "mehr": mehr}


@router.post("/qa-share", status_code=status.HTTP_201_CREATED)
def qa_share_anlegen(
    body: QaShareBody,
    request: Request,
    user: dict = Depends(require_active),
    nwz: Store = Depends(get_store),
) -> QaShareToken:
    """Teilen mit Substanz (Task 31): speichert die KONKRETE Antwort als
    Snapshot — der alte ?q=-Link ließ Empfänger die Frage neu würfeln und
    eine andere Antwort sehen. Bewusste Einzel-Veröffentlichung per Klick."""
    if _share_text_is_objectionable(body.frage) or _share_text_is_objectionable(body.antwort):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Dieser Inhalt kann nicht als öffentlicher Link geteilt werden.",
        )
    if not user.get("limits_frei"):
        qa_share_limiter.check(request)
    extras = {
        "debatten": [d.model_dump() for d in body.debatten],
        "presse": [p.model_dump() for p in body.presse],
        "anlagen": [a.model_dump() for a in body.anlagen],
        "parteien": [p.model_dump() for p in body.parteien],
        "grafik": _grafik_pruefen(body.grafik),
    }
    token = nwz.qa_share_anlegen(user["id"], body.frage, body.antwort,
                                 [q.model_dump() for q in body.quellen],
                                 extras if any(extras.values()) else None)
    return {"token": token}


@router.get("/qa-share/{token}")
def qa_share_lesen(token: str, nwz: Store = Depends(get_store)) -> QaShare:
    """Öffentliche Snapshot-Ansicht — bewusst OHNE Login (der Link soll auch
    Menschen ohne Konto erreichen); enthält nie Konto-Daten."""
    if len(token) > 64:
        raise HTTPException(status_code=404, detail="Nicht gefunden.")
    share = nwz.qa_share_get(token)
    if not share:
        raise HTTPException(status_code=404, detail="Nicht gefunden.")
    return share


class QaShareReportBody(BaseModel):
    reason: str = Field(
        default="other",
        pattern="^(inappropriate|misleading|privacy|other)$",
    )


@router.post("/qa-share/{token}/report", status_code=status.HTTP_202_ACCEPTED)
def qa_share_melden(
    token: str,
    body: QaShareReportBody,
    request: Request,
    nwz: Store = Depends(get_store),
) -> Ok:
    """Öffentlicher Meldeweg für geteilte Inhalte (App Review 1.2).

    Eine Meldung darf kein Konto verlangen: Empfänger*innen eines Links sind
    gerade häufig nicht angemeldet. Der interne Eigentümerbezug ermöglicht
    Moderation und bei Missbrauch eine Kontosperre, wird aber niemals an den
    meldenden Client zurückgegeben.
    """
    if len(token) > 64:
        raise HTTPException(status_code=404, detail="Nicht gefunden.")
    owner_id = nwz.qa_share_owner_id(token)
    if owner_id is None:
        raise HTTPException(status_code=404, detail="Nicht gefunden.")
    qa_share_report_limiter.check(request)
    labels = {
        "inappropriate": "Unangemessener Inhalt",
        "misleading": "Irreführende oder falsche Antwort",
        "privacy": "Privatsphäre / personenbezogene Daten",
        "other": "Anderer Grund",
    }
    nwz.add_feedback(
        0,
        None,
        "qa_share",
        f"{labels[body.reason]}\nShare-Token: {token}\nInhaber-ID: {owner_id}",
    )
    return {"ok": True}


class AskRunde(BaseModel):
    """Eine frühere Gesprächsrunde (Chat): Frage + gekürzte Antwort."""
    frage: str = Field(max_length=300)
    antwort: str = Field(default="", max_length=600)


# ---- „Gründliche Recherche" (RG-10, Task 34) -------------------------------
# Kein Request-gebundener Stream wie /ask: der Job läuft in einem Backend-
# Thread weiter, wenn der Client wegnavigiert (Tims Kernanforderung). POST
# startet, GET …/events klemmt sich an (Replay + live), GET …/{id} liefert
# den persistierten Endzustand — auch nach App- oder Server-Neustart.


class DeepResearchBody(BaseModel):
    frage: str = Field(min_length=4, max_length=300)
    # Wie bei /ask: die letzten Runden lösen Rückbezüge auf. Ohne sie
    # zerlegte der Job eine Anschlussfrage wörtlich („Nochmal bitte
    # ausführlich") — und recherchierte am Thema vorbei.
    verlauf: list[AskRunde] = Field(default_factory=list, max_length=4)
    # „Meine Gespräche": läuft ein Gespräch, wird der fertige Bericht dort
    # angehängt — auch wenn die App längst zu ist.
    gespraech_id: int | None = Field(default=None, ge=1)


def _deep_limit(user: dict) -> int | None:
    """Tageslimit des Kontos: Admin-Override aus web_users.deep_limit —
    None = unbegrenzt (Wert 0), sonst eigener Wert bzw. Standard."""
    override = user.get("deep_limit")
    if override == 0:
        return None
    return override if override is not None else deepresearch.TAGES_KONTINGENT


def _deep_frei(nwz: Store, user: dict) -> int | None:
    limit = _deep_limit(user)
    if limit is None:
        return None  # unbegrenzt — der Client zeigt dann keinen Zähler
    return max(0, limit - nwz.deep_jobs_heute(user["id"]))


@router.post("/deep-research", status_code=status.HTTP_201_CREATED)
def deep_research_start(body: DeepResearchBody, user: dict = Depends(require_active),
                        nwz: Store = Depends(get_store)) -> RechercheGestartet:
    """Recherche-Job starten. Kontingent: 5/Tag je KONTO aus der DB (nicht
    IP — übersteht Neustarts, und Abbruch/Fehler kosten laut Design nichts,
    was ein Fenster-Zähler nicht abbilden kann). Admins können das Limit je
    Konto erhöhen oder ausschalten (web_users.deep_limit)."""
    limit = _deep_limit(user)
    if limit is not None and nwz.deep_jobs_heute(user["id"]) >= limit:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS,
                            "Deine Recherchen für heute sind aufgebraucht — ab morgen geht es weiter.")
    if deepresearch.laufende_jobs(user["id"]) >= 1:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "Es läuft bereits eine Recherche — warte kurz, bis sie fertig ist.")
    if deepresearch.laufende_jobs() >= deepresearch.MAX_PARALLEL:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                            "Gerade laufen viele Recherchen — bitte versuche es gleich nochmal.")
    nwz.record_activity(user["id"], "recherche")
    frage = body.frage.strip()
    job_id = nwz.deep_job_anlegen(user["id"], frage)
    settings = get_settings()
    job = deepresearch.DeepJob(id=job_id, user_id=user["id"], frage=frage,
                               gespraech_id=body.gespraech_id,
                               verlauf=[r.model_dump() for r in body.verlauf])
    deepresearch.start_job(job, settings.nwz_db, settings.council_db)
    return {"job_id": job_id, "frei": _deep_frei(nwz, user)}


@router.get("/deep-research/aktuell")
def deep_research_aktuell(user: dict = Depends(require_active),
                          nwz: Store = Depends(get_store)) -> RechercheAktuell:
    """Der jüngste Job des Kontos + Rest-Kontingent — damit der Client nach
    Navigation/App-Neustart einen laufenden Job oder ungesehenen Bericht
    wiederfindet, ohne sich die ID gemerkt zu haben."""
    return {"job": nwz.deep_job_aktuell(user["id"]),
            "frei": _deep_frei(nwz, user)}


@router.get("/deep-research/{job_id}")
def deep_research_snapshot(job_id: str, user: dict = Depends(require_active),
                           nwz: Store = Depends(get_store)) -> RechercheSnapshot:
    """Persistierter Stand des Jobs (Bericht + Quellen bei fertig/teilbericht)."""
    if len(job_id) > 64:
        raise HTTPException(status_code=404, detail="Nicht gefunden.")
    row = nwz.deep_job_get(job_id, user["id"])
    if not row:
        raise HTTPException(status_code=404, detail="Nicht gefunden.")
    # Läuft laut DB, aber kein Thread mehr da (Server-Neustart, Deploy):
    # ehrlich als Fehler ausweisen, sonst wartete der Client ewig.
    if row["status"] == "laeuft" and deepresearch.get_job(job_id) is None:
        nwz.deep_job_update(job_id, "fehler")
        row["status"] = "fehler"
    try:
        row["quellen"] = json.loads(row["quellen"]) if row.get("quellen") else None
    except (ValueError, TypeError):
        row["quellen"] = None
    return row


@router.get("/deep-research/{job_id}/events")
def deep_research_events(job_id: str, ab: int = Query(default=0, ge=0),
                         user: dict = Depends(require_active),
                         nwz: Store = Depends(get_store)) -> StreamingResponse:
    """SSE-Anschluss an einen laufenden Job: Replay aller Events ab ``ab``,
    dann live weiter. Ein Verbindungsabriss ist folgenlos — der Job läuft
    im Backend weiter, der Client verbindet sich einfach neu."""
    row = nwz.deep_job_get(job_id, user["id"])
    if not row:
        raise HTTPException(status_code=404, detail="Nicht gefunden.")
    job = deepresearch.get_job(job_id)
    if job is None:
        # Kein lebender Job (fertig + aus dem Speicher geräumt, oder Neustart)
        # → der Client holt den Endzustand über den Snapshot-Endpoint.
        raise HTTPException(status.HTTP_410_GONE, "Recherche nicht mehr aktiv — Snapshot laden.")
    return StreamingResponse(
        deepresearch.sse_events(job, ab=ab), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/deep-research/{job_id}/stop")
def deep_research_stop(job_id: str, user: dict = Depends(require_active),
                       nwz: Store = Depends(get_store)) -> RechercheGestoppt:
    """Abbrechen (Design 8c⑥): stoppt vor dem nächsten Such-/LLM-Schritt.
    Fertige Facetten bleiben als Material — die Antwort sagt, ob sich ein
    Teilbericht lohnt. Kostet kein Kontingent."""
    if not nwz.deep_job_get(job_id, user["id"]):
        raise HTTPException(status_code=404, detail="Nicht gefunden.")
    job = deepresearch.get_job(job_id)
    if job is None or job.done:
        raise HTTPException(status.HTTP_409_CONFLICT, "Recherche läuft nicht mehr.")
    job.stop.set()
    with job.cond:
        job.cond.notify_all()
    return {"facetten_fertig": job.facetten_fertig,
            "facetten_gesamt": job.facetten_gesamt,
            "teilbericht_moeglich": bool(job.material and job.material.get("candidates"))}


@router.post("/deep-research/{job_id}/teilbericht")
def deep_research_teilbericht(job_id: str, user: dict = Depends(require_active),
                              nwz: Store = Depends(get_store)) -> Ok:
    """Nach einem Stopp: aus den fertigen Facetten doch noch einen Bericht
    schreiben („Teilbericht zeigen"). Zählt nicht gegen das Kontingent."""
    row = nwz.deep_job_get(job_id, user["id"])
    if not row:
        raise HTTPException(status_code=404, detail="Nicht gefunden.")
    job = deepresearch.get_job(job_id)
    if job is None or row["status"] != "gestoppt":
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "Kein Teilbericht möglich — die Recherche ist nicht gestoppt.")
    if not (job.material and job.material.get("candidates")):
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "Kein Material gesichert — bitte neu recherchieren.")
    # Status VOR dem Thread-Start zurück auf laeuft — andersherum könnte der
    # (schnelle) Thread sein „teilbericht" schreiben und würde überschrieben.
    nwz.deep_job_update(job_id, "laeuft")
    settings = get_settings()
    deepresearch.teilbericht_starten(job, settings.nwz_db, settings.council_db)
    return {"ok": True}


@router.post("/deep-research/{job_id}/gesehen")
def deep_research_gesehen(job_id: str, user: dict = Depends(require_active),
                          nwz: Store = Depends(get_store)) -> Ok:
    """Client hat den fertigen Bericht gerendert — nicht erneut einblenden."""
    nwz.deep_job_gesehen(job_id, user["id"])
    return {"ok": True}


@router.get("/qa-beispiele")
def qa_beispiele(store: CouncilStore = Depends(get_council_store)) -> QaBeispiele:
    """Frische Beispiel-Anlässe für den Empty State der KI-Frage (5a/I-07):
    die jüngsten Sitzungen mit Beschlüssen — das Frontend formuliert daraus
    „Was hat der <Ausschuss> am <Datum> beschlossen?"."""
    return {"sitzungen": store.juengste_sitzungen_mit_beschluessen(limit=2)}


@router.get("/plan-bild/{document_id}")
def plan_bild(document_id: int, thumb: bool = False) -> FileResponse:
    """Gerenderte Planzeichnung einer Anlage (P1) — öffentlich wie die
    Beschluss-Seite selbst; das PDF dahinter ist ohnehin frei abrufbar.
    Dateien schreibt scripts/render_plaene.py nach ``data/plaene/``."""
    from pathlib import Path

    from ..config import get_settings

    name = f"{int(document_id)}{'.thumb' if thumb else ''}.jpg"
    pfad = Path(get_settings().council_db).parent / "plaene" / name
    if not pfad.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Kein Bild zu dieser Anlage.")
    # Ein gerendertes Blatt ändert sich nie — aggressiv cachen.
    return FileResponse(pfad, media_type="image/jpeg",
                        headers={"Cache-Control": "public, max-age=2592000, immutable"})


# ---- Vorgänge verfolgen (Design 28a/W1) ----

def _stations_signature(rows: list[dict]) -> str:
    """Vergleichbarer Fingerabdruck der Beratungsfolge.

    Datum, Gremium und Ergebnis — mehr braucht der Vergleich nicht, und weniger
    wäre zu grob: Eine Station gilt auch dann als neu, wenn nur das Ergebnis
    nachgetragen wurde. Genau das ist die Nachricht, auf die man wartet.
    """
    return json.dumps(
        [f"{r.get('datum') or ''}|{r.get('gremium') or ''}|{r.get('ergebnis') or ''}" for r in rows],
        ensure_ascii=False,
    )


@router.get("/follows")
def list_follows(
    user: dict = Depends(require_active),
    store: CouncilStore = Depends(get_council_store),
    nwz: Store = Depends(get_store),
) -> VorlagenFolgen:
    """Verfolgte Vorgänge mit ihrem aktuellen Stand — die Beratungsfolge liegt
    in der anderen Datenbank, deshalb hier je Follow eine Abfrage (die Zahl
    ist nutzergemacht und klein)."""
    today = date.today().isoformat()
    out = []
    for f in nwz.get_vorlage_follows(user["id"]):
        stations = store.get_beratungen(f["kvonr"])
        naechste = next((b for b in stations if b.get("datum") and b["datum"] > today), None)
        letzte = next((b for b in reversed(stations) if b.get("datum") and b["datum"] <= today), None)
        out.append({
            **f,
            "url": _vorlage_url(f["kvonr"]),
            "n_stationen": len(stations),
            "naechste": naechste,
            "letzte": letzte,
        })
    return {"follows": out}


@router.post("/vorlage/{kvonr}/follow", status_code=status.HTTP_201_CREATED)
def follow_vorlage(
    kvonr: int,
    user: dict = Depends(require_active),
    store: CouncilStore = Depends(get_council_store),
    nwz: Store = Depends(get_store),
) -> VorlageGefolgt:
    v = store.get_vorlage(kvonr)
    if not v:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Vorlage nicht gefunden.")
    # Den heutigen Stand mitschreiben: Was schon dasteht, ist keine Neuigkeit.
    nwz.follow_vorlage(
        user["id"], kvonr,
        vorlage_nr=v.get("vorlage_nr") or "", title=v.get("title") or "",
        stations=_stations_signature(store.get_beratungen(kvonr)),
    )
    return {"kvonr": kvonr, "following": True}


@router.delete("/vorlage/{kvonr}/follow")
def unfollow_vorlage(
    kvonr: int,
    user: dict = Depends(require_active),
    nwz: Store = Depends(get_store),
) -> VorlageEntfolgt:
    nwz.unfollow_vorlage(user["id"], kvonr)
    return {"kvonr": kvonr, "following": False}


@router.get("/analysis")
def analysis(_user: dict = Depends(require_active), store: CouncilStore = Depends(get_council_store)) -> AnalyseDaten:
    """Party behaviour: topic heatmap, success rates, contention, alliances —
    plus Erfolgsquoten der eingereichten Fraktions-Anträge (aus den Anlagen)."""
    data = store.party_analysis()
    data["field_labels"] = {k: POLICY_FIELDS[k][0] for k in data["topic_matrix"]["fields"]}
    data["antrag_stats"] = store.antrag_stats()
    return data


@router.get("/finance")
def finance(_user: dict = Depends(require_active), store: CouncilStore = Depends(get_council_store)) -> Finanzen:
    """Largest € decisions + recognised volume per policy field (excl. accounting reports)."""
    by_field = store.money_by_field()
    return {
        "decisions": store.largest_financial_decisions(limit=25),
        "by_field": by_field,
        "field_labels": {r["field"]: POLICY_FIELDS[r["field"]][0] for r in by_field},
    }


@router.get("/trends")
def trends(_user: dict = Depends(require_active), store: CouncilStore = Depends(get_council_store)) -> TrendDaten:
    """Council activity over time: decisions + € volume per quarter by field, emerging tags."""
    data = store.activity_trends()
    data["field_labels"] = {k: POLICY_FIELDS[k][0] for k in data["fields"]}
    return data


@router.get("/field-recaps")
def field_recaps(_user: dict = Depends(require_active), store: CouncilStore = Depends(get_council_store)) -> ThemenfeldRueckblicke:
    """Auto-generated plain-language recaps per policy field ("Was bewegte den Rat im Bereich X?")."""
    recaps = store.get_field_recaps()
    for r in recaps:
        r["field_label"] = POLICY_FIELDS.get(r["policy_field"], (r["policy_field"],))[0]
    return {"recaps": recaps}


@router.get("/entities")
def entities_list(kind: str = "", _user: dict = Depends(require_active),
                  store: CouncilStore = Depends(get_council_store)) -> Entitaeten:
    """Directory of named entities (projects/places/organizations), most-referenced first."""
    return {"entities": store.list_entities(limit=400, kind=kind)}


@router.get("/entities-map")
def entities_map(_user: dict = Depends(require_active),
                 store: CouncilStore = Depends(get_council_store)) -> EntitaetenKarte:
    """Geocodierte Themen und belastbare Beschlussorte für die Stadtkarte."""
    return {"entities": store.city_map_points()}


@router.get("/public-stats")
def public_stats(store: CouncilStore = Depends(get_council_store)) -> OeffentlicheZahlen:
    """Aggregate headline counts for the public landing page — no auth, no content."""
    return store.public_stats()


# Personen-Lexikon für die Badges im Antwort-Text (Tims Wunsch 12.08.).
# Public wie public-stats: Die geteilten Antwort-Seiten (app/g) brauchen es
# ohne Konto, und der Inhalt sind amtliche RIS-Daten. Prozess-Cache mit
# Tages-TTL — die Quelle ändert sich höchstens mit dem täglichen Import.
_PERSONEN_LEXIKON_CACHE: dict = {"stand": 0.0, "daten": None}


@router.get("/personen-lexikon")
def personen_lexikon(response: Response,
                     store: CouncilStore = Depends(get_council_store)) -> PersonenLexikon:
    import time as _time
    if _PERSONEN_LEXIKON_CACHE["daten"] is None or \
            _time.time() - _PERSONEN_LEXIKON_CACHE["stand"] > 6 * 3600:
        _PERSONEN_LEXIKON_CACHE["daten"] = store.personen_lexikon()
        _PERSONEN_LEXIKON_CACHE["stand"] = _time.time()
    response.headers["Cache-Control"] = "public, max-age=21600"
    return {"personen": _PERSONEN_LEXIKON_CACHE["daten"]}


# ---- Link-Vorschau (Design 29a, P1) ----
# Wortlaut der Ergebnisse für die eine Zeile, die WhatsApp & Co. anzeigen.
_PREVIEW_OUTCOME = {
    "angenommen": "angenommen",
    "abgelehnt": "abgelehnt",
    "vertagt": "vertagt",
    "zur_kenntnis": "zur Kenntnis genommen",
    "kein_beschluss": "ohne Beschluss",
}


def _preview_datum(iso: str | None) -> str:
    """„2026-06-01" → „01.06.2026"; leer bleibt leer."""
    teile = str(iso or "")[:10].split("-")
    return f"{teile[2]}.{teile[1]}.{teile[0]}" if len(teile) == 3 else ""


def _kuerzen(text: str, grenze: int) -> str:
    """Auf Wortgrenze kürzen, mit Auslassungszeichen.

    Beschlusstitel aus dem Ratsinformationssystem werden sehr lang — der volle
    Amtstitel eines Bebauungsplans kommt auf über 250 Zeichen. Messenger und
    Suchmaschinen zeigen aber nur die ersten rund 60–90; ungekürzt sieht die
    Vorschaukarte aus wie ein Fehler.
    """
    text = text.strip()
    if len(text) <= grenze:
        return text
    schnitt = text[:grenze].rsplit(" ", 1)[0].rstrip(" ,;:–-")
    return f"{schnitt or text[:grenze].rstrip()}…"


@router.get("/preview/{kind}/{key:path}")
def preview(kind: str, key: str, store: CouncilStore = Depends(get_council_store)) -> Vorschau:
    """Titel + Kurzfassung für die Link-Vorschau — **ohne Anmeldung**.

    Teilen ist die Kernhandlung der App, aber bislang zeigte jeder geteilte Link
    denselben Werbetext: In einer Elterngruppe landeten fünf Beschlüsse als fünf
    identische Kacheln. Die Vorschau baut `generateMetadata` im Frontend aus
    diesen zwei Feldern.

    Bewusst öffentlich und bewusst schmal: Zurückgegeben wird genau die Zeile,
    die Messenger und Suchmaschinen ohnehin anzeigen — Titel, Ergebnis, Gremium,
    Datum. Alles davon steht so im amtlichen Ratsinformationssystem; es entsteht
    keine neue Öffentlichkeit, nur eine lesbare. Persönliche Daten (Themen,
    Fortschritt, Konten) sind hier prinzipiell nicht erreichbar.
    """
    if kind == "decision":
        d = store.get_decision(int(key)) if key.isdigit() else None
        if not d:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Beschluss nicht gefunden.")
        titel = (d.get("title") or "Beschluss des Oldenburger Stadtrats").strip()
        ergebnis = _PREVIEW_OUTCOME.get(d.get("outcome") or "")
        kopf = " · ".join(x for x in (d.get("committee"), _preview_datum(d.get("session_date"))) if x)
        satz = (d.get("simple_summary") or d.get("summary") or d.get("beschluss") or "").strip()
        # Erst kürzen, dann das Ergebnis anhängen: Es ist die wertvollste
        # Information der Karte und darf nie dem Rotstift zum Opfer fallen.
        titel = _kuerzen(titel, 90)
        # Ohne Beschlusstext blieb hier „Gremium · Datum." stehen — ein Satz,
        # der mitten im Nichts endet. Dann lieber sagen, was die Seite bietet.
        if not satz:
            satz = "Tagesordnungspunkt, Ergebnis und Zusammenhang im Ratslotse."
        return {
            "title": f"{titel} — {ergebnis}" if ergebnis else titel,
            "description": " ".join(x for x in (f"{kopf}." if kopf else "", satz) if x)[:300],
        }

    if kind == "person":
        p = store.member_detail(key)
        if not p:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Ratsmitglied nicht gefunden.")
        partei = p.get("party")
        gremien = len(p.get("committees") or [])
        return {
            "title": f"{p['name']} ({partei})" if partei else p["name"],
            "description": (
                f"Ratsmitglied in Oldenburg · {p.get('sessions', 0)} Sitzungen"
                + (f" · {gremien} Gremien" if gremien else "")
                + ". Anwesenheit und Beschlüsse im Ratslotse."
            ),
        }

    if kind == "ort":
        place = places.resolve(key)
        if not place:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Ort nicht gefunden.")
        n = store.count_decisions(district=place.id)
        return {
            "title": f"{place.name} – {places.kind_label(place.kind)}",
            "description": (
                f"{place.description or 'Ort im Ratslotse-Ortskatalog.'} "
                f"{n} {'Beschluss' if n == 1 else 'Beschlüsse'} mit belegtem Ortsbezug."
            )[:300],
        }

    if kind == "thema":
        e = store.entity_detail(key)
        if not e:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Thema nicht gefunden.")
        ent = e["entity"]
        n = ent.get("n") or 0
        return {
            "title": f"{ent['name']} — {n} {'Beschluss' if n == 1 else 'Beschlüsse'}",
            "description": (
                f"Was der Oldenburger Stadtrat zu „{ent['name']}“ entschieden hat — "
                "alle Beschlüsse auf einer Seite, verständlich zusammengefasst."
            ),
        }

    if kind == "sitzung":
        s = store.get_session(int(key)) if key.isdigit() else None
        if not s:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Sitzung nicht gefunden.")
        datum = _preview_datum(s.get("session_date"))
        return {
            "title": f"{s['committee']} am {datum}" if datum else s["committee"],
            "description": (
                "Tagesordnung und Beschlüsse der Sitzung"
                + (f" am {datum}" if datum else "")
                + f" ({s['committee']}) — im Ratslotse verständlich aufbereitet."
            ),
        }

    raise HTTPException(status.HTTP_404_NOT_FOUND, "Unbekannte Vorschau-Art.")


@router.get("/entity/{slug}")
def entity(slug: str, store: CouncilStore = Depends(get_council_store)) -> EntitaetsDetail:
    """An entity ('Themen-') page: all its decisions plus money/parties/field aggregates.

    Ohne Anmeldung lesbar — es ist eine der geteilten Detailseiten, und alles
    hier ist eine Aggregation öffentlicher Ratsdaten (s. `decision_detail`).
    """
    data = store.entity_detail(slug)
    if not data:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Thema nicht gefunden.")
    data["field_labels"] = {f["field"]: POLICY_FIELDS[f["field"]][0]
                            for f in data["fields"] if f["field"] in POLICY_FIELDS}
    # Verwandte Themen (council.related, vorberechnet). Nach dem kanonischen Slug
    # nachschlagen — bei einem zusammengeführten Alias hängen die Nachbarn am Kanon.
    data["related"] = store.related_entities(data["entity"]["slug"])
    return data


@router.get("/members")
def members(_user: dict = Depends(require_active),
            store: CouncilStore = Depends(get_council_store)) -> Ratsmitglieder:
    """Directory of council members (from attendance): party, sessions, committees."""
    return {"members": store.list_members()}


@router.get("/person/{slug}")
def person(slug: str, store: CouncilStore = Depends(get_council_store)) -> PersonenDetail:
    """Das Profil einer Person — Ratsmitglied oder Verwaltung mit erkanntem
    Amt (Tims Wunsch 19.08.): party/sessions/committees/Gantt bei einem
    Mandat, ein schmaler Steckbrief (Amt + Erwähnungszeitraum) bei einem Amt.
    `typ` im Ergebnis unterscheidet ("rat" | "verwaltung") — das Frontend
    rendert danach zwei verschiedene Ansichten.

    Ohne Anmeldung lesbar (s. `decision_detail`). Es geht ausschließlich um
    Mandatsträger:innen bzw. Amtsträger:innen in ihrer öffentlichen Funktion,
    und die Angaben stammen aus den Anwesenheitslisten der amtlichen
    Protokolle — keine Privatperson wird hier auffindbar, die es nicht
    ohnehin schon ist.
    """
    data = store.member_detail(slug)
    if data:
        data["typ"] = "rat"
        return data
    data = store.verwaltung_detail(slug)
    if data:
        return data
    raise HTTPException(status.HTTP_404_NOT_FOUND, "Person nicht gefunden.")


@router.get("/person/{slug}/wortbeitraege")
def person_wortbeitraege(slug: str, gremium: str | None = None,
                         offset: int = Query(default=0, ge=0),
                         limit: int = Query(default=20, ge=1, le=100),
                         store: CouncilStore = Depends(get_council_store)) -> Wortbeitraege:
    """Wortbeiträge einer Person, seitenweise und nach Gremium filterbar.

    Öffentlich wie die Personen-Seite selbst — es ist derselbe Bestand, nur
    vollständig statt auf die jüngsten zehn gekürzt. Gilt für Ratsmitglieder
    UND Verwaltung mit Steckbrief.
    """
    name = store.member_name(slug) or store.verwaltung_name(slug)
    if not name:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Person nicht gefunden.")
    return store.wortbeitraege_person(name, gremium=gremium, offset=offset, limit=limit)


_EMPTY_GOAL = {"voran": 0, "bremst": 0, "neutral": 0, "total": 0}


@router.get("/goals")
def goals(_user: dict = Depends(require_active), store: CouncilStore = Depends(get_council_store)) -> Ziele:
    """City goals with how many decisions advance / hinder / are neutral toward them."""
    summary = store.goal_summary()
    out = [{"key": key, "label": g["label"], "description": g["description"],
            **summary.get(key, _EMPTY_GOAL)} for key, g in GOALS.items()]
    return {"goals": out}


@router.get("/goal/{key}")
def goal_detail(key: str, _user: dict = Depends(require_active),
                store: CouncilStore = Depends(get_council_store)) -> ZielDetail:
    g = GOALS.get(key)
    if not g:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ziel nicht gefunden.")
    return {
        "key": key, "label": g["label"], "description": g["description"],
        "summary": store.goal_summary().get(key, _EMPTY_GOAL),
        "decisions": store.goal_detail(key),
    }


class AskBody(BaseModel):
    question: str
    # Chat-Modus (Paket A): die letzten Runden erlauben Anschlussfragen wie
    # „Und was kostet das?" — die Analyse kondensiert daraus eine eigenständige
    # Suchfrage. Ohne Verlauf verhält sich /ask exakt wie bisher.
    verlauf: list[AskRunde] = Field(default_factory=list, max_length=4)
    # „Meine Gespräche" (6a): laufendes Gespräch, an das der Turn gehängt wird —
    # nur wirksam, wenn das Konto qa_speichern = 1 gesetzt hat.
    gespraech_id: int | None = Field(default=None, ge=1)
    # „Einfacher erklären": die zuletzt angezeigte Antwort im VOLLTEXT — genau
    # die soll umgeschrieben werden. Der `verlauf` taugt dafür nicht, dort ist
    # jede Antwort auf 600 Zeichen gekappt (er dient dem Auflösen von
    # Rückbezügen, nicht dem Zitieren). Wird nur benutzt, wenn die Frage
    # tatsächlich um eine einfachere Fassung bittet; alte App-Versionen senden
    # das Feld nicht und bekommen die einfache Fassung aus den Beschlüssen.
    vorherige_antwort: str = Field(default="", max_length=8000)


# Q&A sizing: show up to QA_TOP_K reranked decisions as sources, feed the most
# relevant QA_ANSWER_N to the LLM for a focused, cited answer. QA_MIN_SCORE drops
# the near-irrelevant tail from the displayed sources (sigmoid relevance).
QA_TOP_K = 40
QA_ANSWER_N = 20
QA_MIN_SCORE = 0.2
# Sitzungs-Fragetyp: der Antwort-Kontext trägt die GANZE Sitzung — der Deckel
# schützt nur vor Ausreißern (größte Rats-Tagesordnung im Bestand: 47 TOPs).
QA_SITZUNG_N = 60
# jina-reranker-v2 logits are negative-centred (a clearly relevant match still scores
# below 0), so a raw sigmoid under-sells good hits (~50 % for the top result). Shift by
# a fixed bias so a relevant decision reads as a high-but-honest relevance.
QA_RERANK_BIAS = 1.5


def _qa_retrieve(store: CouncilStore, q: str, expanded: str,
                 timings: dict | None = None,
                 varianten: list[str] | None = None,
                 place_ids: list[int] | None = None) -> tuple[list[dict], str]:
    """Hybrid retrieval + cross-encoder rerank → candidates in relevance order, each
    with an *absolute* relevance score: the sigmoid of the reranker logit, NOT a
    min-max normalisation (which forced the weakest hit to a misleading 0 %). Falls
    back to keyword retrieval when embeddings/the reranker are unavailable."""
    try:
        from council import embeddings as emb
        # Akkuratheits-Paket: deterministische Signale neben der Semantik —
        # Entitäts-Anker (benannte Objekte der Frage) in den Rerank-Pool,
        # Frische-Bonus bei Sachstands-Formulierungen.
        entity_anchors = qa.anker_ids_fuer(store, q)
        anchors = list(dict.fromkeys([*entity_anchors, *(place_ids or [])]))
        hits = emb.hybrid_search(store, q, expanded, top_k=QA_TOP_K, pool=55, timings=timings,
                                 varianten=varianten,
                                 anker_ids=anchors,
                                 allowed_ids=place_ids,
                                 recency=qa.recency_intent(q))
        if hits:
            candidates = store.get_decisions_by_ids([h[0] for h in hits])  # preserves order
            score = {h[0]: h[1] for h in hits}
            for c in candidates:
                logit = score.get(c["id"])
                c["score"] = round(1.0 / (1.0 + math.exp(-(logit + QA_RERANK_BIAS))), 3) if logit is not None else None
            # „Ältere Station"-Marker: überholte Zwischenstände derselben
            # Vorlage werden im Kontext als solche ausgewiesen.
            qa.markiere_veraltete(store, candidates)
            return [c for c in candidates if (c.get("score") or 0) >= QA_MIN_SCORE] or candidates, "semantisch"
    except Exception:  # noqa: BLE001 — fastembed missing/any failure → keyword fallback
        pass
    cands = store.get_goal_candidates(qa.extract_keywords(q), limit=QA_TOP_K)
    ids = [c["id"] for c in cands]
    if place_ids is not None:
        allowed = set(place_ids)
        ids = [decision_id for decision_id in ids if decision_id in allowed]
        if not ids:
            ids = place_ids[:QA_TOP_K]
    return store.get_decisions_by_ids(ids), "keyword"


def _sse(obj: dict) -> str:
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


def _qa_source(c: dict) -> dict:
    # amount_eur + factions tragen die Fragetyp-Bausteine des Ratsgesprächs
    # (Geld-Betrag, Antragsteller-Tag) — deterministisch aus den Quellen,
    # nie vom Sprachmodell (Design RG-04/RG-05).
    return {
        "id": c["id"], "title": c.get("title"), "summary": c.get("summary"),
        "policy_field": c.get("policy_field"), "outcome": c.get("outcome"),
        "session_date": c.get("session_date"), "committee": c.get("committee"),
        "score": c.get("score"), "amount_eur": c.get("amount_eur"),
        # Kostenentwicklung (10.08.26): Familien-Erkennung (gleiche Vorlage)
        # für das ehrliche Delta im Geld-Baustein — nur dort ist „gestiegen
        # von X auf Y" belegbar, alles andere wäre ein Äpfel/Birnen-Vergleich.
        "vorlage_nr": c.get("vorlage_nr"),
        "factions": qa._factions_of(c),
        # Bei einem expliziten Ortsfilter: exakte Zuordnung samt Fundstelle.
        # So bleibt im UI prüfbar, weshalb dieser Beschluss zum Ort gehört.
        "location_matches": c.get("location_matches") or [],
        # 5a/I-10: verortete Entität für die Mini-Karte unter der Antwort.
        "ort_name": c.get("ort_name"), "lat": c.get("lat"), "lon": c.get("lon"),
    }


def _presse_kompakt(rows: list[dict]) -> list[dict]:
    """Anzeige-Form der Presse-Treffer — identisch im sources-Event und im
    Gesprächs-Snapshot, damit ein geladenes Gespräch nichts verliert."""
    return [{"titel": p.get("titel"), "url": p.get("url"),
             "datum": p.get("datum")} for p in rows]


def _sitzungen_kompakt(sitzungen: list[dict]) -> list[dict]:
    """Anzeige-Form der aufgelösten Sitzungen (Sitzungs-Fragetyp) für den
    Tagesordnungs-Baustein im Chat — identisch im sources-Event und im
    Gesprächs-Snapshot, damit ein geladenes Gespräch nichts verliert. Die
    Tagesordnung wird auf wenige TOPs angerissen; ``n_agenda`` trägt die
    Gesamtzahl für die „+ n weitere"-Zeile."""
    out = []
    for s in sitzungen:
        agenda = s.get("agenda") or []
        # Der Anriss zeigt INHALTE, keine Formalien: Beschlussfähigkeit,
        # Protokoll-Genehmigung & Co. stehen in jeder Sitzung vorn und füllten
        # alle sechs Plätze der Rats-Karte (dev-Probe 26.08.). Derselbe Filter
        # wie in der Wochenvorschau; nur wenn NUR Formalien da sind, bleiben
        # sie als ehrlicher Rest stehen.
        inhalt = [a for a in agenda
                  if not CouncilStore._FORMALIE_RE.search(a.get("title") or "")]
        out.append({
            "ksinr": s.get("ksinr"), "committee": s.get("committee"),
            "session_date": s.get("session_date"),
            "session_time": s.get("session_time"), "location": s.get("location"),
            "kuenftig": bool(s.get("kuenftig")),
            "n_beschluesse": len(s.get("beschluss_ids") or []),
            "agenda": [{"item_number": a.get("item_number"),
                        "title": a.get("title")} for a in (inhalt or agenda)[:6]],
            "n_agenda": len(agenda),
        })
    return out


def _debatten_kompakt(rows: list[dict]) -> list[dict]:
    return [{"sprecher": d.get("sprecher"), "partei": d.get("partei"),
             "art": d.get("art"), "top": d.get("top"),
             "auszug": (d.get("text") or "")[:2000],
             "committee": d.get("committee"),
             "datum": d.get("session_date"),
             "protokoll_url": d.get("protokoll_url"),
             # PDF-Seite der Fundstelle (Sprecher-Anker); None = Link ohne #page.
             "protokoll_seite": d.get("seite")} for d in rows]


def _anlagen_kompakt(rows: list[dict]) -> list[dict]:
    """Anzeige- und Snapshot-Form der gefundenen Gutachten/Anlagen.

    ``nr`` verbindet den Marker [A1] im Antworttext stabil mit der Karte. Der
    längere Fundstellen-Text bleibt nur im Modellkontext; die Oberfläche zeigt
    einen kurzen, prüfbaren Anriss und verlinkt auf das Originaldokument.
    """
    return [{"nr": a.get("nr"), "label": a.get("label"), "url": a.get("url"),
             "vorlage_nr": a.get("vorlage_nr"),
             "vorlage_titel": a.get("vorlage_titel"),
             "auszug": (a.get("fundstelle") or "")[:220]} for a in rows]


def _turn_speichern(nwz: Store, user: dict, body: AskBody, q_suche: str,
                    answer_text: str, candidates: list[dict],
                    cited: list[int],
                    presse_rows: list[dict] | None = None,
                    debatten_rows: list[dict] | None = None,
                    anlagen_rows: list[dict] | None = None,
                    planungen: list[dict] | None = None,
                    grafik: dict | None = None,
                    sitzungen: list[dict] | None = None) -> int | None:
    """„Meine Gespräche" (6a): Turn ins laufende Gespräch hängen (oder eines
    eröffnen) — nur mit ausdrücklicher Einwilligung, nie als Blocker.

    Nur wenn der Client das Feld ``gespraech_id`` überhaupt kennt: Alte
    App-Versionen senden es nie und können die zurückgegebene id nicht
    weiterreichen — jede Frage würde sonst ein 1-Turn-Fragment eröffnen und
    die Gespräche-Liste fluten (Review-Befund B5). Ein frisch eröffnetes
    Gespräch wird wieder gelöscht, wenn der Turn-Insert scheitert — sonst
    bliebe ein leerer Eintrag in der Liste zurück (Befund B2)."""
    try:
        if "gespraech_id" not in body.model_fields_set:
            return None
        if not answer_text.strip() or nwz.get_qa_speichern(user["id"]) != 1:
            return None
        gespraech_id = body.gespraech_id
        neu = gespraech_id is None
        if neu:
            gespraech_id = nwz.qa_gespraech_start(user["id"], q_suche or body.question)
            if gespraech_id is None:
                return None
        zitiert = set(cited)
        # Presse + Debatten gehören MIT in den Snapshot: Ohne sie öffnete ein
        # gespeichertes Gespräch ohne den „Aktuelles von der Stadt"-Block und
        # ohne Debatten — und damit auch ohne den Parteien-Baustein, der am
        # Debatten-Gate hängt (Tims Befund 10.08.).
        quellen_json = json.dumps(
            {"sources": [_qa_source(c) for c in candidates if c["id"] in zitiert],
             "cited": cited,
             # Die KONDENSIERTE Frage mit in den Snapshot: „Und was kostet
             # das?" wird beim Antworten zu einer eigenständigen Frage
             # verdichtet, und Bausteine, die danach nachladen (der
             # Parteien-Baustein), schlüsseln darauf. Ohne sie baute ein
             # wiederhergestelltes Gespräch den Turn mit der Originalfrage auf
             # — anderer Schlüssel, also lud der Baustein beim Zurückwechseln
             # auf den Fragen-Tab komplett neu und fragte dabei mit der
             # kontextlosen Frage (Tims Befund 21.08.2026).
             "kontext": q_suche,
             "presse": _presse_kompakt(presse_rows or []),
             "debatten": _debatten_kompakt(debatten_rows or []),
             "anlagen": _anlagen_kompakt(anlagen_rows or []),
             # Der Ausblick gehört wie Presse und Debatten in den Snapshot,
             # sonst öffnet ein gespeichertes Gespräch ohne „Wie es weitergeht".
             "planungen": planungen or [],
             # Und die Grafik aus demselben Grund: Ein gespeichertes Gespräch
             # soll aussehen wie das Gespräch, aus dem es stammt.
             "grafik": grafik,
             # Der Tagesordnungs-Baustein ebenso (Sitzungs-Fragetyp).
             "sitzungen": _sitzungen_kompakt(sitzungen or [])}, ensure_ascii=False)
        if not nwz.qa_turn_speichern(gespraech_id, user["id"],
                                     body.question, answer_text, quellen_json):
            if neu:
                nwz.qa_gespraech_loeschen(gespraech_id, user["id"])
            return None
        return gespraech_id
    except Exception:  # noqa: BLE001 — Speichern ist Zusatz, nie Blocker
        return None


@router.post("/ask")
def ask(body: AskBody, request: Request, user: dict = Depends(require_active),
        store: CouncilStore = Depends(get_council_store),
        nwz: Store = Depends(get_store)) -> StreamingResponse:
    """Answer a free-text question from the decisions, streamed as Server-Sent Events:
    progress steps → the ranked source decisions (the moment retrieval+rerank finish)
    → the answer token-by-token → a final event with the cited ids. Streaming makes
    the wait feel far shorter (sources show in ~2 s) and degrades gracefully if a
    proxy buffers it (the client then renders the same final state at once)."""
    if not user.get("limits_frei"):  # Admin kann Konten befreien (web_users.limits_frei)
        # Mobilfunkanbieter bündeln viele Geräte hinter derselben öffentlichen
        # Adresse. Das Konto ist hier bereits sicher authentifiziert und damit
        # der faire, stabile Schlüssel für das Kosten-Limit.
        qa_limiter.check(request, subject=user["id"])
    nwz.record_activity(user["id"], "ki_frage")  # Admin-Statistik (20a)
    q = body.question.strip()
    if len(q) < 4:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Bitte eine etwas längere Frage stellen.")

    def gen():
        try:
            # Latenz je Schritt (ms) — geloggt und im done-Event mitgeschickt,
            # damit Prod-Fragen dieselben Kennzahlen liefern wie eval/run_qa.py.
            # (expand_ms misst seit dem Fragetyp-Routing den EINEN Analyse-Call
            # — Begriffe + Typ —, der Schlüssel bleibt für Vergleichbarkeit.)
            zeiten: dict = {}
            verlauf = [r.model_dump() for r in body.verlauf]
            yield _sse({"type": "step", "step": "expand"})
            t0 = time.perf_counter()
            analyse = qa.analyse_query(q, verlauf=verlauf)
            expanded, typ = analyse["begriffe"], analyse["typ"]
            # Punktfrage (Datum/Zahl/Name)? Dann antwortet das Modell knapp —
            # der Befund kam aus einer echten Nutzer-Frage, der nach dem
            # gesuchten Datum noch fünf Redebeiträge folgten (12.08.).
            eng = bool(analyse.get("eng"))
            # „Einfacher erklären" (Befund Build 11): Der Wunsch nach einfacher
            # Sprache ist KEINE neue Frage — er verlangt dieselbe Auskunft in
            # anderer Sprache. Deshalb ein eigener Prompt statt einer weiteren
            # Zeile im Antwort-Prompt, wo er gegen zwei Dutzend Präzisions-
            # Regeln verlor. Erkennung am ROHEN Fragetext: die kondensierte
            # Fassung aus der Analyse hat den Wunsch schon wegübersetzt.
            einfach = qa.will_vereinfachung(q)
            if einfach:
                eng = False  # „kurz und knapp" und „einfach" sind zwei Register
            # Retrieval + Reranker arbeiten mit der EIGENSTÄNDIGEN Fassung der
            # Frage — „Und was kostet das?" sucht sonst nach nichts.
            q_suche = analyse["frage"]
            zeiten["expand_ms"] = round((time.perf_counter() - t0) * 1000)
            # Personen-Fragetyp (10.08.26): nennt die Frage eine Ratsperson,
            # antworten wir aus DEREN Wortbeiträgen — deterministisch erkannt,
            # schlägt thema/verlauf (nicht aber partei/geld).
            person = qa.finde_person(store, q_suche)
            if person and typ not in ("partei", "geld"):
                typ = "person"
            # Orts-Fragetyp: dieselbe deterministische Stammdaten-Erkennung wie
            # bei Personen. Ein Alias wie „Donnerschwee-Kaserne“ wird dabei auf
            # die stabile Orts-ID ``neu-donnerschwee`` aufgelöst.
            ort = qa.finde_ort(q_suche, store) or qa.finde_ort(q, store)
            # Der Ort ist grundsätzlich ein Filter, kein exklusiver Fragetyp:
            # Geld-, Partei-, Verlaufs-, Personen- und Sitzungsfragen behalten
            # ihre Spezialregeln. Nur eine allgemeine Themenfrage wird zur
            # reinen Ortsfrage.
            if ort and typ == "thema" and not person:
                typ = "ort"
            # Sitzungs-Fragetyp (25.08.26): Nennt die Frage ein konkretes
            # Sitzungsdatum oder die letzte/nächste Sitzung eines Gremiums,
            # wird die Sitzung deterministisch aufgelöst und ihre Beschlüsse
            # kommen VOLLSTÄNDIG in den Kontext. Die Ähnlichkeitssuche allein
            # ließ beim Rückblick auf den Jugendhilfeausschuss vom 17.06.2026
            # drei der sechs TOPs weg, darunter einen echten Beschluss (echte
            # Nutzerfrage 25.08.). partei/geld/person behalten Vorrang.
            # Erkennung auf der kondensierten UND der rohen Frage: Die Analyse
            # schreibt „im Bauausschuss morgen" gern zu „am morgigen Tag" um —
            # was die Kondensierung an Signalwörtern verschluckt, trägt die
            # Original-Frage noch (Tims Befund 26.08., zweiter Anlauf).
            sitzungen = [] if person else (qa.finde_sitzungen(store, q_suche)
                                           or qa.finde_sitzungen(store, q))
            sitzung_ids = [i for s in sitzungen for i in s.get("beschluss_ids") or []]
            if sitzungen and typ not in ("partei", "geld"):
                typ = "sitzung"
            latest_place = bool(ort and typ == "ort"
                                and (qa.latest_intent(q_suche) or qa.latest_intent(q)))
            shadow_plan = qa.research_plan_with_mandatory(
                analyse.get("rechercheplan") or {}, typ=typ, question=q_suche,
                person=bool(person), place=bool(ort), sessions=bool(sitzungen),
                latest_decision=latest_place)
            yield _sse({"type": "step", "step": "search"})
            t0 = time.perf_counter()
            place_ids = (store.decision_ids_for_place(ort["id"], limit=120)
                         if ort else None)
            allowed_place_ids = set(place_ids or []) if ort else None
            if latest_place:
                # Bei einer reinen Ortsfrage nach dem „zuletzt“ ist das Datum
                # die Antwort. Der Reranker schob in der Produktionsprobe einen
                # Beschluss von Dezember 2025 vor einen angenommenen Beschluss
                # von April 2026. Die Orts-IDs sind bereits neueste zuerst und
                # exakt belegt — hier braucht es keine Semantik.
                candidates = store.get_decisions_by_ids((place_ids or [])[:QA_TOP_K])
                mode = "chronologisch"
            else:
                candidates, mode = _qa_retrieve(store, q_suche, expanded, timings=zeiten,
                                                varianten=analyse.get("varianten"),
                                                place_ids=place_ids)
            partei_ids: set[int] = set()
            if typ == "partei" and analyse.get("partei"):
                # Anträge der gefragten Fraktion zum Thema in den Pool — die
                # semantische Suche kennt den Antragsteller-Filter nicht.
                try:
                    extra_ids = store.antrag_decision_ids(analyse["partei"], expanded)
                    if allowed_place_ids is not None:
                        extra_ids = [i for i in extra_ids if i in allowed_place_ids]
                    partei_ids = set(extra_ids)
                    have = {c["id"] for c in candidates}
                    candidates += store.get_decisions_by_ids([i for i in extra_ids if i not in have])
                except Exception:  # noqa: BLE001 — Anreicherung ist best-effort
                    pass
            if sitzung_ids:
                # Die aufgelöste Sitzung VOLLSTÄNDIG in den Kandidatenpool —
                # beim Sitzungs-Fragetyp in Tagesordnungs-Reihenfolge nach
                # vorn, denn daran hängen das Aussprache-Nachladen
                # (candidates[:8]) und der Antwort-Kontext.
                have = {c["id"] for c in candidates}
                effective_sitzung_ids = ([i for i in sitzung_ids if i in allowed_place_ids]
                                         if allowed_place_ids is not None else sitzung_ids)
                nachgeladen = store.get_decisions_by_ids(
                    [i for i in effective_sitzung_ids if i not in have])
                if typ == "sitzung":
                    pos = {i: n for n, i in enumerate(effective_sitzung_ids)}
                    eigene = sorted(
                        [c for c in candidates if c["id"] in pos] + nachgeladen,
                        key=lambda c: pos[c["id"]])
                    candidates = eigene + [c for c in candidates if c["id"] not in pos]
                else:
                    candidates += nachgeladen
            # Letzte harte Schranke nach allen Anreicherungen: Kein später
            # nachgeladener Partei- oder Sitzungsbeschluss darf den expliziten
            # Ortsfilter umgehen.
            if allowed_place_ids is not None:
                candidates = [c for c in candidates if c["id"] in allowed_place_ids]
            # Beim Vereinfachen zählen die Belege der VORIGEN Antwort: Ihre ids
            # müssen im Kandidatenset stehen, sonst streicht resolve_citations
            # genau die Fußnoten weg, die die einfache Fassung übernehmen soll —
            # die Antwort verlöre beim Vereinfachen ihre Quellen.
            vorher_ids: list[int] = []
            if einfach and body.vorherige_antwort.strip():
                try:
                    zitiert = qa.zitierte_ids(body.vorherige_antwort)
                    have = {c["id"] for c in candidates}
                    fehlend = [i for i in zitiert if i not in have]
                    if fehlend:
                        candidates += store.get_decisions_by_ids(fehlend)
                        have = {c["id"] for c in candidates}
                    vorher_ids = [i for i in zitiert if i in have]
                except Exception:  # noqa: BLE001 — Nachladen ist Zusatz, nie Blocker
                    vorher_ids = []
            anlagen_rows: list[dict] = []
            # Vorlagenauszüge gab es schon vor dem Planer und bleiben bei
            # Providerfehlern als sicherer Fallback erhalten. Die deutlich
            # teurere Anlagenmatrix ist neu und läuft ohne validen Plan nicht.
            documents_enabled = qa.research_channel_enabled(shadow_plan, "documents")
            anlagen_enabled = qa.research_channel_enabled(
                shadow_plan, "documents", fallback=False)
            if anlagen_enabled and not einfach:
                try:
                    # Fachliche Details stecken oft nicht im Beschluss, sondern
                    # in Gutachten, Konzepten und Stellungnahmen. Die schnelle
                    # Frage nutzt dafür jetzt denselben semantischen Kanal wie
                    # die gründliche Recherche — aber nur bei dokumentiertem
                    # Bedarf im validierten Rechercheplan.
                    from council import embeddings as emb
                    hits_a = emb.search_anlagen(store, q_suche, expanded, top_k=4)
                    anlagen_rows = store.anlagen_by_ids([did for did, _, _ in hits_a])
                    fundstellen = {did: fs for did, _, fs in hits_a}
                    for i, a in enumerate(anlagen_rows):
                        a["fundstelle"] = fundstellen.get(a["document_id"], "")
                        a["nr"] = i + 1

                    # Ein Anlagenfund bekommt seinen entscheidungsbezogenen
                    # Quellenanker dazu. Bei explizitem Ortsfilter darf auch
                    # dieser Nachladeweg den belegten Ort nicht umgehen.
                    by_vorlage = store.decision_ids_for_vorlagen(
                        [a.get("vorlage_nr") for a in anlagen_rows])
                    if allowed_place_ids is not None:
                        erlaubte_nrn = {nr for nr, ids in by_vorlage.items()
                                       if any(i in allowed_place_ids for i in ids)}
                        anlagen_rows = [a for a in anlagen_rows
                                        if a.get("vorlage_nr") in erlaubte_nrn]
                    related_ids: list[int] = []
                    for a in anlagen_rows:
                        ids = by_vorlage.get(a.get("vorlage_nr") or "", [])
                        if allowed_place_ids is not None:
                            ids = [i for i in ids if i in allowed_place_ids]
                        related_ids.extend(ids[:2])
                    have = {c["id"] for c in candidates}
                    candidates += store.get_decisions_by_ids(
                        [i for i in dict.fromkeys(related_ids) if i not in have])
                except Exception:  # noqa: BLE001 — Dokumente sind Zusatz, nie Blocker
                    anlagen_rows = []
            presse_rows: list[dict] = []
            press_enabled = qa.research_channel_enabled(shadow_plan, "press")
            if press_enabled:
                try:
                    # Eigener Kanal neben den Beschlüssen: „Aktuelles von der
                    # Stadt" (Pressemitteilungen) — nur wenn der validierte
                    # Rechercheplan einen offiziellen aktuellen Stand braucht.
                    from council import embeddings as emb
                    hits_p = emb.search_presse(store, q_suche, expanded)
                    presse_rows = store.presse_by_ids([pid for pid, _ in hits_p])
                except Exception:  # noqa: BLE001 — Presse ist Zusatz, nie Blocker
                    pass
            debatten_rows: list[dict] = []
            # Kommende oder protokolllose Sitzung: Es KANN noch keine Debatte
            # dieser Sitzung geben — die Ähnlichkeitssuche fände nur Beiträge
            # aus ALTEN Sitzungen, und die stünden als „Aus den Ratsdebatten"
            # irreführend neben der Zukunfts-Antwort; am Debatten-Gate hinge
            # obendrein der Parteien-Baustein (Tims Befund 26.08.). Fragen zur
            # „letzten Sitzung" behalten ihre Debatten: Dort ist die Sitzung
            # MIT Beschlüssen mit aufgelöst (sitzung_ids gefüllt).
            # Erster kontrolliert aktivierter Rechercheplan-Kanal: Debatten
            # nur suchen, wenn der validierte und konsistent vervollständigte
            # Plan sie braucht. 24 klare Produktionsfragen trennten damit
            # argumentativ/personenbezogen von Fakten/Terminen 24/24 korrekt.
            # Bei einem ungültigen Plan gilt als sicherer Fallback weiterhin
            # das alte Verhalten. Enge neueste Ortsfragen bleiben unabhängig
            # davon deterministisch ohne Debatten.
            debates_enabled = qa.research_channel_enabled(shadow_plan, "debates")
            if (not latest_place and debates_enabled
                    and (typ != "sitzung" or sitzung_ids)):
                try:
                    # Task 16: Wortbeiträge aus den Protokollen (Reden, Anfragen,
                    # Einwohnerfragen, Zusagen) — die Substanz, die nicht in den
                    # Beschlusstexten steht. Strenge Schwelle, oft leer. Beim
                    # Personen-Fragetyp stattdessen die Beiträge DIESER Person.
                    from council import embeddings as emb
                    if person and ort:
                        # Personen-Suche und Ortsfilter müssen über denselben
                        # Beschlussanker laufen. Die freie Personen-Suche trägt
                        # kein ``zu_beschluss``-Feld und wurde vom Orts-Guard
                        # deshalb bisher vollständig entfernt — selbst wenn es
                        # belegte Beiträge gab (Produktionsprobe Ellberg).
                        # Nicht nur die semantisch gerankten Beschlüsse prüfen:
                        # Der Personenname steht typischerweise ausschließlich
                        # im Protokoll, nicht im Beschlusstitel. Deshalb dienen
                        # ALLE Ortsbeschlüsse (gedeckelt durch ``place_ids``)
                        # als Anker; tatsächlich verknüpfte Beschlüsse werden
                        # anschließend in den sichtbaren Quellen nachgeladen.
                        orts_candidates = store.get_decisions_by_ids(place_ids or [])
                        debatten_rows = store.wortbeitraege_zu_beschluessen(
                            orts_candidates, max_gesamt=10, max_je_top=4,
                            sprecher=person["nachname"])
                        linked_ids = list(dict.fromkeys(
                            row["zu_beschluss"] for row in debatten_rows))
                        have = {c["id"] for c in candidates}
                        linked_by_id = {c["id"]: c for c in orts_candidates}
                        linked = [linked_by_id[i] for i in linked_ids
                                  if i not in have and i in linked_by_id]
                        if linked:
                            candidates = linked + candidates
                    elif person:
                        debatten_rows = emb.search_wortbeitraege_von_person(
                            store, q_suche, person["nachname"])
                    else:
                        hits_w = emb.search_wortbeitraege(store, q_suche, expanded)
                        debatten_rows = store.wortbeitraege_by_ids([wid for wid, _ in hits_w])
                        # … plus die Aussprache ZU den gefundenen Beschlüssen:
                        # Fachsprache (Vinylchlorid, Messpunkte) liegt außerhalb
                        # des Frage-Wortfelds und fällt durch die Ähnlichkeits-
                        # suche — Zugehörigkeit trägt hier weiter (Befund 10.08.).
                        have = {d["id"] for d in debatten_rows}
                        debatten_rows += [w for w in store.wortbeitraege_zu_beschluessen(
                            candidates[:8]) if w["id"] not in have]
                    # Zusagen der Verwaltung als EIGENER Kanal: Im allgemeinen
                    # Debatten-Ranking gingen sie unter (1 von 19 Belegen; selbst
                    # auf „Was hat die Verwaltung zugesagt?" kam keine), weil sie
                    # kurz und nüchtern formuliert sind. Dabei sind sie der
                    # besondere Stoff — eine Selbstverpflichtung mit Datum.
                    if not person:
                        try:
                            hits_z = emb.search_zusagen(store, q_suche, expanded)
                            schon = {r["id"] for r in debatten_rows}
                            debatten_rows += [r for r in store.wortbeitraege_by_ids(
                                [wid for wid, _ in hits_z]) if r["id"] not in schon]
                        except Exception:  # noqa: BLE001 — Zusatz, nie Blocker
                            pass
                    # FDP/Volt-Beiträge in die Einzel-Partei auflösen (Stammdaten).
                    qa.parteien_aufloesen(store, debatten_rows)
                except Exception:  # noqa: BLE001 — Debatten sind Zusatz, nie Blocker
                    pass
            if ort and debatten_rows:
                # Wortbeiträge besitzen selbst noch keinen belastbaren
                # Ortskatalog. Bei einer Ortsfrage zeigen wir deshalb nur die,
                # die deterministisch an einen gefilterten Beschluss gekoppelt
                # sind; freie semantische Treffer könnten sonst aus einem ganz
                # anderen Stadtgebiet stammen.
                candidate_ids = {c["id"] for c in candidates}
                debatten_rows = [d for d in debatten_rows
                                  if d.get("zu_beschluss") in candidate_ids]
            # Beleg nachlesbar machen: jeder Beitrag bekommt die PDF-URL
            # seines Protokolls (Tims Wunsch 18.08.).
            qa.protokolle_verlinken(store, debatten_rows)
            # 5a/I-10: Orts-Pins für die Mini-Karte — deterministisch aus den
            # geocodierten Entitäten, nie vom Sprachmodell.
            try:
                orte = store.orte_fuer_decisions([c["id"] for c in candidates])
                for c in candidates:
                    c.update(orte.get(c["id"], {}))
            except Exception:  # noqa: BLE001 — Karte ist Zusatz, nie Blocker
                pass
            if ort:
                try:
                    matches = store.location_matches_for_decisions(
                        [c["id"] for c in candidates], district=ort["id"])
                    for c in candidates:
                        exact = matches.get(c["id"], [])
                        c["location_matches"] = exact
                        # Die Mini-Karte soll bei Mehrfach-Orten den tatsächlich
                        # gefragten Ort zeigen, nicht irgendeinen anderen Pin.
                        pin = next((m for m in exact
                                    if m.get("lat") is not None and m.get("lon") is not None), None)
                        if pin:
                            c.update({"ort_name": pin["name"], "lat": pin["lat"], "lon": pin["lon"]})
                except Exception:  # noqa: BLE001 — Nachweis ist Zusatz, nie Blocker
                    pass
            # „Wie es weitergeht" (Paket 1): künftige Beratungsstationen der
            # gefundenen Vorlagen. Bisher gab es den Blick nach vorn NUR in der
            # Gründlichen Recherche — dabei sind Sachstands-Fragen („Wie ist
            # der aktuelle Stand zum Stadion?") der häufigste Fragetyp
            # überhaupt, und die Termine stehen längst gepflegt in der DB.
            planungen: list[dict] = []
            future_enabled = qa.research_channel_enabled(shadow_plan, "future_agenda")
            if future_enabled:
                try:
                    planungen = store.geplante_beratungen_fuer(
                        [c.get("kvonr") for c in candidates[:20]])
                    # Zweiter Weg, weil der erste systematisch leer läuft: Auf
                    # der Tagesordnung stehen noch NICHT entschiedene Vorlagen.
                    gesehen = {p["kvonr"] for p in planungen}
                    planungen += [p for p in store.kommende_beratungen(expanded.split())
                                  if p["kvonr"] not in gesehen]
                except Exception:  # noqa: BLE001 — Ausblick ist Zusatz, nie Blocker
                    pass
            # Hintergrund zu den genannten Objekten („Was ist die GSG?").
            steckbriefe = qa.steckbriefe_fuer(store, q_suche)
            if ort and ort.get("description"):
                steckbriefe = [{"name": ort["name"],
                                "description": ort["description"]}, *steckbriefe]
            # Wie tragfähig ist der Fund? Deterministisch aus den Scores.
            lage = qa.beleglage(candidates)
            if anlagen_rows and not candidates:
                # Ein konkreter Gutachten-/Anlagenfund ist ein direkter Beleg,
                # auch wenn keine verknüpfte Beschlussstation vorhanden ist.
                lage = "solide"
            if latest_place:
                # Keine Rerank-Scores im chronologischen Modus; der Ortsbezug
                # ist dennoch deterministisch. Nur ein Mini-Bestand bleibt
                # bewusst als dünn markiert.
                lage = "solide" if len(candidates) >= 3 else "duenn"
            if person and ort and debatten_rows:
                # Sitzung + TOP + Sprecher + kuratierter Ortsbezug sind harte
                # Beziehungen, keine Ähnlichkeitsschätzung.
                lage = "solide"
            if typ == "sitzung" and sitzungen:
                # Die Sitzung ist deterministisch aufgelöst, kein Ähnlichkeits-
                # Raten — die Dünn-Regel hätte hier nichts zu bremsen. Gilt
                # auch OHNE Beschlüsse (kommender Termin, Protokoll-Verzug):
                # Da antwortet der Sitzungskalender, und der „mit Vorsicht"-
                # Hinweis stünde falsch neben der Tagesordnungs-Karte.
                lage = "solide"
            zeiten["retrieve_ms"] = round((time.perf_counter() - t0) * 1000)
            # Haushalts-Kontext: welche der zehn Geld-Quellen diese Frage
            # beantworten, entscheidet `qa.geld_facetten` deterministisch am
            # FRAGE-WORTLAUT — nicht am LLM-Fragetyp. Der Grund steht im
            # Abschnittskopf von council/qa.py: Fragen wie „Was hat das
            # Rechnungsprüfungsamt beanstandet?" oder „Muss die Stadt das
            # Theater betreiben?" sind mit gutem Grund `thema` und bekämen an
            # einem Typ-Gate nie ihre Daten. `typ` bleibt als Auffangnetz drin
            # (siehe geld_facetten) — der bisherige Weg „typ=geld → Plan-Zahlen"
            # ist damit unverändert erhalten.
            #
            # Gesucht wird mit `q_suche` (der eigenständigen Fassung), nicht mit
            # `expanded`: Die Expansion ist ausdrücklich angewiesen, eine
            # Sachstands-Frage zusätzlich als Finanzierungs-Frage zu
            # formulieren, und trüge damit „Kosten" in jede Stadion-Frage.
            #
            # Beim Vereinfachen gar nicht erst fragen: Der Knopf schreibt die
            # VORIGE Antwort um (eigener Prompt ohne Zusatz-Bausteine), die
            # Abfragen wären sicher umsonst.
            geld = {} if einfach else qa.geld_kontext(store, q_suche, expanded, typ)
            # Die Grafik zur Antwort — Rohreihen aus dem Store, nie vom
            # Modell (council/qa.py, geld_grafik). Das Modell weiß nicht
            # einmal, dass es sie gibt: Sie hängt am Ereignis, nicht am
            # Prompt.
            grafik = qa.geld_grafik(store, geld) if geld else None
            # 5a/I-06: die kondensierte Frage mitschicken — der Kontext-Chip im
            # Frontend zeigt, worauf sich Anschlussfragen beziehen.
            yield _sse({"type": "sources", "mode": mode, "qtype": typ,
                        "frage": q_suche,
                        "sources": [_qa_source(c) for c in candidates],
                        "presse": _presse_kompakt(presse_rows),
                        "debatten": _debatten_kompakt(debatten_rows),
                        "anlagen": _anlagen_kompakt(anlagen_rows),
                        "planungen": planungen,
                        # Tagesordnungs-Baustein: die aufgelösten Sitzungen des
                        # Sitzungs-Fragetyps — deterministisch, nie vom Modell.
                        "sitzungen": _sitzungen_kompakt(sitzungen),
                        "beleglage": lage,
                        # Welche Haushalts-Quellen diese Frage gezogen hat.
                        # Steht im Ereignis, damit im Log ohne Rätselraten zu
                        # sehen ist, warum eine Antwort eine Zahl kannte —
                        # oder eben nicht.
                        "geldquellen": geld.get("facetten") or [],
                        "grafik": grafik,
                        # Der Hintergrund geht IMMER in die Antwort; als eigene
                        # Karte erscheint er nur, wenn die Antwort ihn nicht
                        # ohnehin wiederholt (Definitionsfragen, Tims Befund).
                        "steckbriefe": [{"name": s["name"], "slug": s["slug"],
                                         "beschreibung": s["description"]}
                                        for s in steckbriefe]
                        if qa.steckbrief_karte_zeigen(q_suche) else []})
            yield _sse({"type": "step", "step": "answer"})
            if not candidates and not anlagen_rows:
                leer_text = "Dazu habe ich keine passenden Beschlüsse gefunden."
                if sitzungen and ort:
                    leer_text = (f"In der gefragten Sitzung habe ich keine Beschlüsse mit "
                                 f"belegtem Bezug zu {ort['name']} gefunden.")
                elif sitzungen:
                    # Die gefragte Sitzung IST aufgelöst — sie hat nur (noch)
                    # keine Beschlüsse: künftiger Termin oder Protokoll-Verzug.
                    # Das pauschale „nichts gefunden" wäre hier die falsche
                    # Auskunft.
                    leer_text = qa.sitzungs_leer_text(sitzungen)
                elif debatten_rows:
                    # Die Debatten-Treffer stehen bereits sichtbar in den
                    # Belegen — ein hartes „nichts gefunden" daneben wäre
                    # gelogen (Review-Befund zu #387).
                    leer_text = ("Dazu habe ich keine passenden Beschlüsse gefunden — "
                                 "aber Wortbeiträge aus den Ratsdebatten, siehe Belege.")
                yield _sse({"type": "token", "text": leer_text})
                # Auch der Kein-Treffer-Turn gehört ins gespeicherte Gespräch —
                # sonst klafft im Transkript eine Lücke (Review-Befund B4).
                gespraech_id = _turn_speichern(nwz, user, body, q_suche, leer_text, [], [],
                                               debatten_rows=debatten_rows,
                                               sitzungen=sitzungen)
                yield _sse({"type": "done", "cited": [], "gespraech_id": gespraech_id})
                return
            # Task 32: Themengröße deterministisch — viele Treffer über eine
            # lange Zeitspanne (Stadion: 8 Jahre) heißt lange Historie, die
            # Antwort darf dann ausführlich gegliedert sein (GROSS_REGEL).
            daten = sorted(str(c.get("session_date") or "")[:4]
                           for c in candidates[:20] if c.get("session_date"))
            spanne = (int(daten[-1]) - int(daten[0])) if len(daten) >= 2 and daten[0].isdigit() else 0
            # Beim Vereinfachen NIE die Langfassungs-Regel: „umfangreiches Thema"
            # verlangt ~500 Wörter mit Zwischenüberschriften — das ist das
            # Gegenteil von dem, was der Knopf verspricht.
            gross = (len(candidates) >= 25 or spanne >= 3) and not einfach
            if typ == "sitzung":
                # Länge nach Sitzungsgröße statt Kandidatenzahl — die zählt
                # nach dem Voll-Merge der Sitzung immer hoch.
                gross = len(sitzung_ids) >= 12 and not einfach
            ctx = candidates[:QA_ANSWER_N]
            if latest_place:
                # Das Quellenband bleibt streng chronologisch. Für das Modell
                # steht die jüngste echte Entscheidung zusätzlich ganz vorn:
                # Die bloße Prompt-Regel reichte in der Produktionsprobe nicht
                # aus — es sprang sonst zum älteren Titel mit dem wörtlichen
                # Ortsnamen statt zum jüngeren geokodierten Straßenbeschluss.
                latest_real = qa.latest_real_decision(ctx)
                if latest_real:
                    ctx = [latest_real] + [c for c in ctx
                                           if c["id"] != latest_real["id"]]
            if vorher_ids:
                # Beim Vereinfachen sieht das Modell NUR die Beschlüsse, die die
                # vorige Antwort belegt haben. Das ist keine Sparmaßnahme,
                # sondern die Fußnoten-Garantie: Mit den übrigen 30 Kandidaten
                # im Kontext hängte das Modell im Test eine fremde Nummer an ein
                # Debatten-Zitat, das in der Ausgangsantwort bewusst ohne Beleg
                # stand. Was es nicht sieht, kann es nicht danebensetzen.
                ctx = [c for c in candidates if c["id"] in set(vorher_ids)][:QA_ANSWER_N]
            if partei_ids and not einfach:
                # Mindestens die besten Partei-Anträge in den Antwort-Kontext,
                # auch wenn sie im Relevanz-Ranking hinter Platz 20 liegen.
                fehlend = [c for c in candidates[QA_ANSWER_N:] if c["id"] in partei_ids][:6]
                if fehlend:
                    ctx = ctx[:QA_ANSWER_N - len(fehlend)] + fehlend
            if typ == "verlauf":
                ctx = qa.sort_verlauf(ctx)
            if typ == "sitzung" and sitzung_ids and not einfach:
                # ALLE Beschlüsse der Sitzung in den Antwort-Kontext — der
                # QA_ANSWER_N-Deckel würde große Sitzungen wieder anschneiden,
                # und genau das Anschneiden ist der Anlass dieses Fragetyps.
                im_set = set(sitzung_ids)
                ctx = [c for c in candidates if c["id"] in im_set][:QA_SITZUNG_N]
            if documents_enabled and not einfach:
                try:  # Vorlagen-Auszüge (Sachverhalt) beilegen — best-effort
                    texts = store.vorlage_texts_for([c.get("vorlage_nr") or "" for c in ctx])
                    for c in ctx:
                        t = texts.get((c.get("vorlage_nr") or "").strip())
                        if t:
                            c["vorlage_excerpt"] = vorlagen_mod.excerpt(t, 350)
                except Exception:  # noqa: BLE001
                    pass
            try:  # Läuft zu einem Kandidaten gerade eine Bauleitplan-Beteiligung?
                from council import beteiligung as bet_mod
                bets = store.list_beteiligungen()
                for c in ctx if bets else []:
                    b = next((b for b in bets
                              if bet_mod.passt_zu_titel(b["plan_nrs"], c.get("title") or "")), None)
                    if b:
                        frist = f" bis {b['bis']}" if b.get("bis") else ""
                        c["beteiligung"] = f"{b['schritt']}{frist}"
            except Exception:  # noqa: BLE001 — Zusatzsignal, nie Blocker
                pass
            # Rechercheplaner zunächst ausschließlich beobachten: Die Antwort
            # benutzt weiterhin exakt die bewährte Pipeline. Der JSON-Logeintrag
            # zeigt später, welche Kanäle das Modell gewählt hätte, welche durch
            # harte Entitäten zwingend waren und wo heutige Kanäle tatsächlich
            # Material fanden — ohne den Fragetext zu speichern.
            try:
                observed = {
                    "decisions": len(candidates),
                    "debates": len(debatten_rows),
                    "budget": sum(len(value) if isinstance(value, list) else int(bool(value))
                                  for key, value in geld.items() if key != "facetten"),
                    "press": len(presse_rows),
                    "sessions": len(sitzungen),
                    "future_agenda": len(planungen),
                    "places": sum(bool(c.get("location_matches")) for c in candidates),
                    "documents": (len(anlagen_rows)
                                  + sum(bool(c.get("vorlage_excerpt")) for c in ctx)),
                }
                _log.info("qa_research_plan_shadow %s", json.dumps(
                    qa.research_plan_log_record(q_suche, shadow_plan, typ, observed),
                    ensure_ascii=False, separators=(",", ":")))
            except Exception:  # noqa: BLE001 — Telemetrie darf nie antwortkritisch sein
                pass
            # Der Antworttext wird live gestreamt, die angehängten Folgefragen
            # (24a) dürfen dabei NICHT als Text erscheinen. Deshalb halten wir
            # stets die letzten len(MARKER) Zeichen zurück: so kann ein über
            # mehrere Deltas verteilter Marker nie durchrutschen.
            marker = qa.FOLLOWUP_MARKER
            buf, sent = "", 0
            t0 = time.perf_counter()
            # Worum es ging, steht in der kondensierten Fassung der Analyse.
            # Fällt die aus, ist q_suche der Knopftext selbst — dann trägt die
            # letzte echte Frage aus dem Verlauf das Thema.
            frage_thema = q_suche
            if einfach and frage_thema.strip() == q and verlauf:
                frage_thema = verlauf[-1].get("frage") or q
            if latest_place and not einfach:
                # Bei „zuletzt beschlossen“ ist das Ergebnis vollständig aus
                # Datum + Abstimmung ableitbar. Die Produktionsprobe zeigte,
                # dass selbst ein expliziter Prompt-Anker vom Modell zugunsten
                # eines älteren Titels ignoriert werden kann. Deshalb kommt
                # diese enge Faktenantwort ohne generative Auswahl aus.
                strom = iter([qa.latest_place_answer(candidates[:QA_ANSWER_N])])
            else:
                strom = (qa.vereinfachen_stream(frage_thema, body.vorherige_antwort, ctx)
                         if einfach else
                         qa.answer_stream(q, ctx, typ=typ, presse=presse_rows, verlauf=verlauf,
                                          geld=geld, debatten=debatten_rows,
                                          anlagen=anlagen_rows,
                                          gross=gross, steckbriefe=steckbriefe,
                                          duenn=(lage == "duenn"), eng=eng,
                                          sitzungen=sitzungen, ort=ort))
            try:
                for delta in strom:
                    if not buf and delta:
                        zeiten["ttft_ms"] = round((time.perf_counter() - t0) * 1000)
                    buf += delta
                    cut = buf.find(marker)
                    # Vor dem Marker: senden. Ab dem Marker: nur noch sammeln
                    # (die Vorschläge stehen dahinter — nicht abbrechen).
                    limit = cut if cut != -1 else max(0, len(buf) - len(marker))
                    if limit > sent:
                        yield _sse({"type": "token", "text": buf[sent:limit]})
                        sent = limit
                # Ohne Marker bleibt der zurückgehaltene Rest übrig.
                if marker not in buf and len(buf) > sent:
                    yield _sse({"type": "token", "text": buf[sent:]})
                    sent = len(buf)
            except Exception:  # noqa: BLE001 — Stream riss mitten in der Antwort
                # Vorher wurde der Fehler nur bei LEEREM Puffer repariert — ein
                # Abriss nach den ersten Sätzen ließ still einen Antwort-Torso
                # stehen (Tims „mitten im Wort zu Ende"-Befund 10.08.). Jetzt:
                # immer einmal komplett neu generieren; der Client ersetzt den
                # Torso per replace-Event. Scheitert auch das, wird der Turn
                # ehrlich als abgebrochen markiert.
                _log.warning("answer_stream brach nach %d Zeichen ab — one-shot Ersatz",
                             len(buf), exc_info=True)
                try:
                    ans, _ = (qa.vereinfachen_question(frage_thema, body.vorherige_antwort, ctx)
                              if einfach else
                              qa.answer_question(q, ctx, typ=typ, presse=presse_rows, verlauf=verlauf,
                                                 geld=geld, debatten=debatten_rows,
                                                 anlagen=anlagen_rows,
                                                 gross=gross, steckbriefe=steckbriefe,
                                                 duenn=(lage == "duenn"), eng=eng,
                                                 sitzungen=sitzungen, ort=ort))
                    buf = ans
                    yield _sse({"type": "replace", "text": qa.split_followups(ans)[0]})
                    sent = len(ans)
                except Exception:  # noqa: BLE001
                    _log.exception("one-shot Ersatz scheiterte ebenfalls")
                    if not buf:
                        raise  # nichts gesendet → Netz-Fehlerpfad des Clients
                    yield _sse({"type": "abbruch"})
            answer_text, followups = qa.split_followups(buf)
            if not followups:
                followups = qa.fallback_followups(ctx)
            if followups:
                yield _sse({"type": "suggestions", "questions": followups})
            _, cited = qa.resolve_citations(answer_text, {c["id"] for c in candidates})
            zeiten["antwort_ms"] = round((time.perf_counter() - t0) * 1000)
            zeiten["total_ms"] = (zeiten.get("expand_ms", 0) + zeiten.get("retrieve_ms", 0)
                                  + zeiten.get("antwort_ms", 0))
            _log.info("qa_timings mode=%s typ=%s %s", mode, typ,
                      " ".join(f"{k}={v}" for k, v in sorted(zeiten.items())))
            gespraech_id = _turn_speichern(nwz, user, body, q_suche, answer_text,
                                           candidates, cited,
                                           presse_rows=presse_rows,
                                           debatten_rows=debatten_rows,
                                           anlagen_rows=anlagen_rows,
                                           planungen=planungen,
                                           grafik=grafik,
                                           sitzungen=sitzungen)
            yield _sse({"type": "done", "cited": cited, "timings": zeiten,
                        "gespraech_id": gespraech_id})
        except Exception:  # noqa: BLE001 — surface a terminal error to the client
            _log.exception("KI-Frage fehlgeschlagen")
            yield _sse({"type": "error", "message": "Frage fehlgeschlagen."})

    return StreamingResponse(
        gen(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# Die Ratsvorlage, mit der die Stadt Oldenburg den Städtevergleich selbst
# angestellt und im selben Dokument entwertet hat. Sie ist der Beleg für die
# Erklärseite und wird über die **Vorlagennummer** aufgelöst, nicht über eine
# gespeicherte Beschluss-id: Die Nummer ist auf jeder Kopie der Datenbank
# dieselbe, die AUTOINCREMENT-id nicht.
VERGLEICH_BELEG_VORLAGE = "18/0911"
VERGLEICH_BELEG_KVONR = 17170


@router.get("/haushalt/vergleich")
def haushalt_vergleich(
    _user: dict = Depends(require_active),
    store: CouncilStore = Depends(get_council_store),
) -> HaushaltVergleich:
    """Was sich zwischen Städten vergleichen lässt — und der Beleg, warum das
    meiste sich **nicht** vergleichen lässt.

    Zwei Teile, und der zweite ist der wichtigere:

    - ``werte``/``staedte``/``jahre``: Steuerkraft und Hebesätze der acht
      kreisfreien Städte Niedersachsens aus den beiden Tabellen des
      Landesamts für Statistik. Dieselbe Kennzahl, dieselbe Stelle, dieselbe
      Abgrenzung für alle — der Auslagerungsgrad einer Stadt greift hier
      nicht, weil Steuern nie ein Eigenbetrieb erhebt.
    - ``beleg``: die Ratsvorlage 18/0911, in der die Stadt Oldenburg 2018 auf
      Antrag der FDP-Fraktion sieben Städte verglichen und im selben Dokument
      festgestellt hat, dass dieser Vergleich nichts aussagt. Aufgelöst wird
      sie über die Vorlagennummer; ``beschluss_id`` zeigt auf den Eintrag in
      unserem eigenen Bestand (der Ausschuss hat den Bericht zur Kenntnis
      genommen), ``anlagen`` auf Antrag und Antwort im Original.

    **Was diese Antwort bewusst nicht tut:** Sie mischt die LSN-Steuerkraft
    nicht mit ``council_steuerkraft`` (Datensatz 1106). Beide führen dieselben
    Beträge, aber unter einer um ein Jahr verschobenen Jahresangabe; welche
    stimmt, ist ungeklärt. Zusammengelegt ergäbe das eine Reihe, in der zwei
    verschiedene Jahre dasselbe zu meinen scheinen.
    """
    # Lokal importiert, damit dieser Endpunkt ein zusammenhängender Block am
    # Dateiende bleibt (mehrere Aufträge arbeiten parallel in dieser Datei) —
    # dieselbe Bauart wie `from council import herkunft as _h` im Store.
    import sqlite3

    from council import staedtevergleich as sv

    werte = store.get_staedtevergleich()
    jahre: dict[str, list[int]] = {}
    for w in werte:
        jahre.setdefault(w["reihe"], [])
        if w["jahr"] not in jahre[w["reihe"]]:
            jahre[w["reihe"]].append(w["jahr"])
    for liste in jahre.values():
        liste.sort()

    staedte = [{
        "schluessel": key,
        "name": name,
        "ist_oldenburg": key == sv.OLDENBURG,
        # Unter 100.000 Einwohnern rechnet das NFAG die Steuerkraftmesszahl
        # mit anderen Nivellierungshebesätzen. Das gehört an den Wert, sonst
        # vergleicht die Seite still zwei Rechenvorschriften.
        "unter_100k": key in sv.UNTER_100K,
    } for key, name in sv.KREISFREIE_STAEDTE.items()]

    beleg: dict = {"vorlage_nr": VERGLEICH_BELEG_VORLAGE,
                   "kvonr": VERGLEICH_BELEG_KVONR,
                   "vorlage_url": _vorlage_url(VERGLEICH_BELEG_KVONR),
                   "beschluss_id": None, "titel": None, "anlagen": []}
    try:
        ids = store.find_decision_ids(vorlage_nr=VERGLEICH_BELEG_VORLAGE)
        beleg["beschluss_id"] = ids[0] if ids else None
        vorlage = store.get_vorlage_by_nr(VERGLEICH_BELEG_VORLAGE)
        if vorlage:
            beleg["titel"] = vorlage.get("title")
        beleg["anlagen"] = [
            {"document_id": a["document_id"], "label": a["label"],
             "url": a["url"], "is_antrag": a.get("is_antrag", 0)}
            for a in store.anlagen_for_vorlage_nr(VERGLEICH_BELEG_VORLAGE)]
    except sqlite3.OperationalError:
        # Eine Datenbank ohne Vorlagen-Bestand (etwa im Test) soll die Seite
        # nicht umbringen — der Erklärtext trägt auch ohne die Verweise.
        pass

    ids = sorted({w["herkunft_id"] for w in werte if w["herkunft_id"] is not None})
    return {
        "staedte": staedte,
        "werte": werte,
        "jahre": jahre,
        "beleg": beleg,
        "herkunft": {str(h["id"]): h for h in store.get_herkunft(ids)},
    }


@router.get("/haushalt/gebaut")
def haushalt_gebaut(
    _user: dict = Depends(require_active),
    store: CouncilStore = Depends(get_council_store),
) -> HaushaltGebaut:
    """Was die Stadt wirklich investiert hat — Tabellen 1107/1107-1 des
    Statistischen Jahrbuchs.

    Das **Ist** zu den Planzahlen von ``/haushalt/investitionen``. Beide
    Endpunkte bleiben getrennt, und zwar nicht aus Bequemlichkeit: Der Plan ist
    nach Teilhaushalten gegliedert, das Ist nach Auszahlungsarten und
    ausdrücklich auf die Kernverwaltung begrenzt. Kein Dokument stellt die
    beiden Summen nebeneinander; eine gemeinsame Antwort lüde dazu ein, sie
    voneinander abzuziehen und das Ergebnis „Umsetzungsquote" zu nennen — eine
    Zahl, die in keiner Quelle steht (``council/investitionen_ist.py``).

    ``regelwerk`` trennt die beiden Tabellen, und das ist die tragende Angabe
    dieser Antwort: Zum 01.01.2010 stellte die Stadt von kameraler auf
    doppische Buchführung um. Das Dokument trennt seine Reihen genau dort und
    begründet es in einer Fußnote. Wer über diesen Schnitt hinweg eine Linie
    zieht, behauptet eine Vergleichbarkeit, die die Quelle bestreitet.

    ``fehlend`` nennt die Jahre, die **innerhalb** einer Reihe fehlen, weil
    ihre Zeilensumme im Dokument selbst nicht aufgeht. Anders als bei den
    Schulden gibt es hier keine zweite, unabhängige Probe, die wenigstens die
    Summe trüge — also fällt der ganze Jahrgang, und die Oberfläche kann die
    Lücke **benennen**, statt sie als Null zu zeichnen oder still zu
    überspringen.

    Je Lücke steht dort neben dem Jahr die gemessene ``differenz`` in Euro
    (Auszahlungsarten minus ausgewiesene Summe, vorzeichenbehaftet) — die
    Zahl, die der Ingest-Lauf beim Verwerfen gemessen hat
    (``council_investitionen_ist_verworfen``). Sie ist der Unterschied
    zwischen „2019 fehlt" und „2019 fehlt, weil 1,3 Mio. € auseinanderlagen".
    ``null``, wo der Bestand keine Messung führt: ein Jahrgang, der vor dem
    Ausbau dieser Schicht verworfen wurde, oder eine Zeile, die sich gar
    nicht erst zerlegen ließ. Dann bleibt der Betrag auf der Seite weg — er
    wird nirgends geschätzt.
    """
    from council import anlagenspiegel as anlagenspiegel_mod
    from council import investitionen_ist as _ii

    reihe = store.get_investitionen_ist()
    anlagen = store.get_anlagenspiegel()
    gruppen = store.get_vermoegensgruppen()
    ids = sorted({z["herkunft_id"] for z in (*reihe, *anlagen, *gruppen)
                  if z["herkunft_id"] is not None})
    gemessen = {(v["regelwerk"], v["jahr"]): v.get("differenz")
                for v in store.get_investitionen_ist_verworfen()}

    # Lücken je Regelwerk: Was zwischen dem ersten und dem letzten belegten
    # Jahrgang einer Reihe fehlt, fehlt nachweislich — dafür braucht es die
    # Spanne aus dem Titel nicht. (Fiele der JÜNGSTE angekündigte Jahrgang
    # durch, sähe man ihn hier nicht; das steht dann im Beleg-Messwert der
    # Herkunft, den derselbe Lauf schreibt.)
    fehlend: dict[str, list[dict]] = {}
    for regelwerk in _ii.REGELWERK:
        jahre = sorted(z["jahr"] for z in reihe if z["regelwerk"] == regelwerk)
        if len(jahre) < 2:
            continue
        luecke = [{"jahr": j, "differenz": gemessen.get((regelwerk, j))}
                  for j in range(jahre[0], jahre[-1] + 1) if j not in set(jahre)]
        if luecke:
            fehlend[regelwerk] = luecke

    return {
        "reihe": reihe,
        "jahre": [z["jahr"] for z in reihe],
        "abgrenzung": _ii.ABGRENZUNG,
        # Wie die beiden Rechnungswesen heißen — damit die Beschriftung nicht
        # in zwei Sprachen existiert (dieselbe Entscheidung wie bei `arten`
        # in /haushalt/schulden).
        "regelwerke": [{"schluessel": k, "titel": t}
                       for k, t in _ii.REGELWERK.items()],
        "fehlend": fehlend,
        # DIE ANDERE HÄLFTE DER GESCHICHTE. Bis hierher zeigt die Seite, was
        # die Stadt gebaut hat. Der Anlagenspiegel zeigt, was daraus wurde —
        # und dass es trotzdem schrumpft: Was im Jahr zugeht, steht neben dem,
        # was im selben Jahr abgeschrieben wird.
        #
        # `gruppen` ist die Untergliederung des Infrastrukturvermögens
        # (Straßen, Brücken, Gleisanlagen). Sie steht in einer ANDEREN Tabelle
        # desselben Dokuments und gibt es erst ab 2022 — deshalb ein eigener
        # Block und keine Spalte: Wer sie als Teil der Reihe ausgäbe, machte
        # aus einer Quellenlücke eine Datenlücke.
        "anlagen": {
            "reihe": anlagen,
            "jahre": sorted({z["jahr"] for z in anlagen}),
            "gruppen": gruppen,
            "gruppen_jahre": sorted({g["jahr"] for g in gruppen}),
            "proben": anlagenspiegel_mod.PROBEN,
        },
        "herkunft": {str(h["id"]): h for h in store.get_herkunft(ids)},
    }


@router.get("/haushalt/bilanz")
def haushalt_bilanz(
    _user: dict = Depends(require_active),
    store: CouncilStore = Depends(get_council_store),
) -> HaushaltBilanz:
    """Die Bilanz der Stadt — Abschnitt 2.1 der Jahresabschlüsse.

    Die Gegenseite zu ``/haushalt/schulden``: nicht was die Stadt schuldet,
    sondern was sie **hat** und was davon schon vergeben ist.

    ``posten`` ist eine flache Liste über alle Stichtage. **An ``rolle``
    hängen, nicht an ``nr``**: Die Gliederungsnummer der Bilanz ist bis 2020
    römisch, ab 2021 arabisch, und ab 2021 gibt es jede Nummer auf beiden
    Seiten — „1.1" ist auf der Aktivseite etwas anderes als auf der
    Passivseite. ``seite`` (``aktiva``/``passiva``) und ``ebene`` (1 = die
    neun Hauptposten, aus denen die Bilanzsumme besteht) sind die stabilen
    Achsen.

    Zwei Rollen heißen fast gleich und meinen Verschiedenes — wer sie
    verwechselt, schreibt eine falsche Schlagzeile:

    * ``pensionen_gesamt`` — Bilanzposition 3.1 „Pensionsrückstellungen und
      ähnliche Verpflichtungen", **einschließlich Beihilfe** (31.12.2024:
      311,79 Mio. €),
    * ``pensionsrueckstellungen`` — Position 3.1.1, die Pensionen **allein**
      (266,26 Mio. €); der Rest ist ``beihilferueckstellungen`` (45,53).

    Die beiden ältesten Stichtage führen die Aufschlüsselung nicht — die
    Bilanz wies damals nur den Sammelposten aus. Sie fehlen dort schlicht;
    eine Anzeige zeigt die Lücke, statt sie zu füllen.

    ``erlaeuterungen`` ist **keine Zugabe, sondern eine Auflage.** Die
    Schulden springen 2024 von 84,4 auf 207,1 Mio. €, und das ist kein
    Schuldenmachen, sondern eine Bilanzverlängerung aus dem Cash-Pooling
    (138,2 Mio. €, mit Gegenposten auf der Aktivseite). Der Anhang erklärt es
    unter ``rolle="schulden"`` selbst. **Die Zahl darf ohne diesen Text nicht
    angezeigt werden** — dieselbe Bauart wie ``abweichungsgruende`` für die
    Ergebnisrechnung.
    """
    posten = store.get_bilanz()
    erlaeuterungen = store.get_bilanz_erlaeuterungen()
    ids = sorted({z["herkunft_id"] for z in posten + erlaeuterungen
                  if z["herkunft_id"] is not None})
    return {
        "jahre": store.bilanz_jahre(),
        "posten": posten,
        "erlaeuterungen": erlaeuterungen,
        "herkunft": {str(h["id"]): h for h in store.get_herkunft(ids)},
    }


@router.get("/haushalt/schulden")
def haushalt_schulden(
    _user: dict = Depends(require_active),
    store: CouncilStore = Depends(get_council_store),
) -> HaushaltSchulden:
    """Der Schuldenstand der Stadt seit 1995 — Tabelle 1108 des Statistischen
    Jahrbuchs.

    ``abgrenzung`` ist kein Beiwerk, sondern die Bedingung dafür, dass die
    Zahlen etwas bedeuten: Bei Kommunalschulden gibt es zwei Werte, die beide
    „die Schulden der Stadt" heißen und sich um ein Vielfaches unterscheiden.
    Diese Reihe zählt die Stadt als **Rechtsträger** — Kernhaushalt und
    Eigenbetriebe, ohne die rechtlich selbstständigen Beteiligungen. Der Wert
    kommt aus ``council/schulden.py`` und nicht aus dem Frontend, damit beide
    Seiten dieselbe Auskunft geben.

    ``je_einwohner`` ist die Angabe **der Quelle**, nicht unsere Rechnung. Sie
    kommt so aus der Tabelle; dass sie zur Einwohnerzahl aus dem Open-Data-
    Datensatz passt, ist die Probe, die den Wert überhaupt hereingelassen hat
    (``herkunft[…].proben``).

    Wo ``aufteilung_verworfen`` gesetzt ist, fehlen die vier Artenspalten:
    Dort ergeben sie im Dokument selbst nicht die ausgewiesene Summe. Die
    Summe steht trotzdem — sie hängt an der unabhängigen Pro-Kopf-Probe. Die
    Oberfläche kann den fehlenden Balken damit **erklären**, statt ihn als
    Null zu zeichnen oder still zu überspringen.
    """
    from council import buergschaften as _b
    from council import integrierte_schulden as _i
    from council import schulden as _s

    zeilen = store.get_schulden()
    ids = sorted({z["herkunft_id"] for z in zeilen if z["herkunft_id"] is not None})

    # Was die Schulden im Jahr KOSTEN — Posten 17 der Ergebnisrechnung
    # („Zinsen und ähnliche Aufwendungen"), also Ist aus dem geprüften
    # Jahresabschluss, nicht aus dem Jahrbuch.
    #
    # Bewusst nur die Zinsen: Die TILGUNG steht im Finanzhaushalt und nicht in
    # der Ergebnisrechnung — sie mindert den Schuldenstand, ist aber kein
    # Aufwand. Beides in einer Zahl zusammenzuziehen wäre die häufigste
    # Verwechslung im Thema, und sie stünde in keinem Dokument.
    zins: list[dict] = []
    try:
        for jahr in store.ergebnisrechnung_jahre():
            for posten in store.get_ergebnisrechnung(jahr):
                if posten["nr"] != _s.POSTEN_ZINSAUFWAND:
                    continue
                # NUR die Gesamtrechnung (`thh_nr IS NULL`). Der Jahresabschluss
                # führt denselben Posten 17 noch einmal je Teilhaushalt; ohne
                # diesen Filter kämen je Jahr mehrere „Zinslasten" heraus, und
                # die Seite zeigte je nach Sortierung mal die Kernverwaltung,
                # mal einen einzelnen Teilhaushalt unter derselben Überschrift.
                if posten.get("thh_nr") is not None:
                    continue
                if posten.get("ergebnis") is None:
                    continue          # ein Jahrgang ohne Ist trägt hier nichts
                zins.append({
                    "jahr": jahr,
                    "aufwand": posten["ergebnis"],
                    "herkunft_id": posten.get("herkunft_id"),
                })
    except Exception:  # noqa: BLE001 — Zusatzangabe, nie Blocker für die Seite
        zins = []

    # Wofür die Stadt geradesteht — die zweite, größere Zahl auf dieser Seite.
    # Sie ist KEINE Schuld: 2024 stehen 220,3 Mio. € Bürgschaften 43,7 Mio. €
    # eigenen Geldschulden gegenüber, und die Stadt rechnet davon mit 1,3 Mio. €
    # Ausfall (Bilanzposten 3.7). Alle drei Zahlen reisen zusammen, weil jede
    # einzelne für sich irreführt: das Volumen als drohende Zahlung gelesen,
    # die Rückstellung als Gesamtrisiko.
    # Die dritte Schuldenzahl: was der ganze „Konzern Stadt" anteilig schuldet
    # (740,3 Mio. € zum 31.12.2024 gegen 294,9 Mio. € der Reihe oben). Sie
    # reist mit ihren beiden Warnsätzen, nicht ohne: Der größere Teil stammt
    # aus Beteiligungen unter 50 %, für die die Stadt nicht haftet, und eine
    # Zeitreihe daraus zu bauen verbietet die Quelle selbst.
    integriert = store.get_integrierte_schulden()
    juengste = integriert[-1] if integriert else None
    buerg = store.get_buergschaften()
    rueckstellung = store.get_bilanz_posten(_b.RUECKSTELLUNG_ROLLE) if buerg else []
    geldschulden = store.get_bilanz_posten(_b.GELDSCHULDEN_ROLLE) if buerg else []
    ids = sorted(set(ids) | {z["herkunft_id"] for z in (*zins, *buerg, *integriert,
                                                        *rueckstellung, *geldschulden)
                             if z.get("herkunft_id") is not None})

    return {
        "reihe": zeilen,
        "jahre": [z["jahr"] for z in zeilen],
        "abgrenzung": _s.ABGRENZUNG,
        # `genau` und `aus_folgejahr` sind Angaben über den BELEG, nicht über
        # die Zahl: 2019/2020 stehen auf den Cent im Dokument, ab 2022 rundet
        # die Quelle selbst auf Zehntel-Millionen, und 2021 steht überhaupt
        # nur im Abschluss des Folgejahres. Wer alle sechs gleich formatiert,
        # behauptet eine Genauigkeit, die es für vier davon nicht gibt.
        "buergschaften": {
            "reihe": buerg,
            "rueckstellung": rueckstellung,
            "geldschulden": geldschulden,
            "abgrenzung": _b.ABGRENZUNG,
            # Die Ratsbeschlüsse dahinter — als GESCHICHTE, nicht als Summe.
            # Unter den Vorlagen sind Verlängerungen und Anpassungen derselben
            # Bürgschaft; addiert zählte man dieselbe Zusage mehrfach. Was der
            # Bestand ist, sagt allein der Jahresabschluss (`reihe`).
            "vorlagen": store.buergschafts_vorlagen(),
        },
        # Die dritte Zahl — nur der jüngste Stichtag, und ausdrücklich ohne
        # Reihe. `anteil_unter_50` wird hier gerechnet und nicht im Frontend:
        # Er entscheidet, wie die Zahl gelesen werden darf, und er ändert sich
        # mit jeder Ausgabe.
        "integrierte_schulden": {
            "stichtag": juengste,
            "anteil_unter_50": _i.anteil_unter_50(juengste) if juengste else None,
            "abgrenzung": _i.ABGRENZUNG,
            "keine_reihe": _i.KEINE_REIHE,
        } if juengste else None,
        # Leer, solange kein Jahresabschluss eingelesen ist — die Seite lässt
        # den Block dann weg, statt eine Null zu zeigen.
        "zinslast": zins,
        # Die Spaltenüberschriften der Quelle, in ihrer Reihenfolge — damit die
        # Legende nicht in zwei Sprachen existiert.
        "arten": [{"feld": feld, "titel": titel}
                  for feld, titel in _s.SPALTEN[:4]],
        "herkunft": {str(h["id"]): h for h in store.get_herkunft(ids)},
    }
