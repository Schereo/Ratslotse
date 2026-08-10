"""„Gründliche Recherche" (RG-10, Task 34): server-seitige Recherche-Jobs.

Der Kern-Unterschied zum /ask-Stream: die Recherche läuft in einem
Hintergrund-Thread WEITER, wenn der Client die Verbindung verliert —
Tab-Wechsel, App-Navigation, zugeklappter Laptop. Clients klemmen sich per
SSE wieder an (Replay aller bisherigen Events + live weiter); der fertige
Bericht steht zusätzlich persistent in ``deep_research_jobs`` (nwz.sqlite)
und überlebt damit auch App- und Server-Neustarts.

Ablauf eines Jobs (Phasen wie im Design 8a):
zerlegen → je Facette suchen → Dokumente lesen (volle Vorlagen-Auszüge)
→ Bericht schreiben (Token-Stream) → done. „Abbrechen" stoppt sofort vor
dem nächsten LLM-/Suchschritt; fertige Facetten bleiben als Material für
einen Teilbericht erhalten (Design 8c⑥).
"""
from __future__ import annotations

import json
import logging
import math
import threading
from dataclasses import dataclass, field

from council.store import CouncilStore
from nwz.store import Store

_log = logging.getLogger(__name__)

# Wie viele Treffer je Facette in den Pool gehen und wie viele Beschlüsse der
# Bericht maximal liest. 28 Kandidaten × bis zu 4000 Zeichen Vorlagen-Auszug
# passen bequem in das Kontextfenster des Berichts-Modells.
JE_FACETTE = 14
MAX_KANDIDATEN = 28
VOLLTEXT_TOP = 10          # so viele Kandidaten mit großem Vorlagen-Auszug …
VOLLTEXT_ZEICHEN = 4000
KURZTEXT_ZEICHEN = 800     # … der Rest mit kompaktem
TOKEN_BUENDEL = 150        # Token-Deltas zu Events bündeln (Replay bleibt schlank)
MAX_PARALLEL = 4           # globaler Deckel gleichzeitiger Recherchen
TAGES_KONTINGENT = 5       # je Konto (RG-10: „noch n von 5 heute")

# Wie in council.py: Reranker-Logits → ehrliche absolute Relevanz.
RERANK_BIAS = 1.5


@dataclass
class DeepJob:
    """Ein laufender (oder gestoppter, Teilbericht-fähiger) Job im Speicher."""
    id: str
    user_id: int
    frage: str
    gespraech_id: int | None = None
    events: list[dict] = field(default_factory=list)
    cond: threading.Condition = field(default_factory=threading.Condition)
    done: bool = False
    stop: threading.Event = field(default_factory=threading.Event)
    # Nach einem Stopp: alles Nötige, um auf Wunsch noch den Teilbericht zu
    # schreiben (Design 8c⑥ „Teilbericht zeigen").
    material: dict | None = None
    facetten_fertig: int = 0
    facetten_gesamt: int = 0


_registry: dict[str, DeepJob] = {}
_reg_lock = threading.Lock()


def _emit(job: DeepJob, event: dict) -> None:
    with job.cond:
        job.events.append(event)
        job.cond.notify_all()


def _finish(job: DeepJob) -> None:
    with job.cond:
        job.done = True
        job.cond.notify_all()


def get_job(job_id: str) -> DeepJob | None:
    with _reg_lock:
        return _registry.get(job_id)


def laufende_jobs(user_id: int | None = None) -> int:
    with _reg_lock:
        return sum(1 for j in _registry.values()
                   if not j.done and (user_id is None or j.user_id == user_id))


def registry_aufraeumen(max_fertige: int = 50) -> None:
    """Fertige Jobs irgendwann aus dem Speicher werfen — die Wahrheit liegt
    ohnehin in der DB; hier geht es nur um den Replay laufender Sitzungen."""
    with _reg_lock:
        fertige = [k for k, j in _registry.items() if j.done]
        for k in fertige[:-max_fertige] if len(fertige) > max_fertige else []:
            del _registry[k]


def sse_events(job: DeepJob, ab: int = 0):
    """Alle Events ab Index ``ab`` — erst Replay, dann live bis zum Ende.
    Niemals unter gehaltenem Lock yielden (der Consumer kann beliebig
    langsam sein); Keepalive-Kommentare halten Proxies bei Laune."""
    i = max(0, ab)
    while True:
        with job.cond:
            while i >= len(job.events) and not job.done:
                if not job.cond.wait(timeout=15):
                    break  # Timeout → Keepalive senden
            batch = job.events[i:]
            i += len(batch)
            fertig = job.done and i >= len(job.events)
        if batch:
            for e in batch:
                yield "data: " + json.dumps(e, ensure_ascii=False) + "\n\n"
        elif not fertig:
            yield ": ping\n\n"
        if fertig:
            return


def start_job(job: DeepJob, nwz_db: str, council_db: str) -> None:
    """Job registrieren und den Recherche-Thread starten."""
    with _reg_lock:
        _registry[job.id] = job
    threading.Thread(target=_run, args=(job, nwz_db, council_db),
                     daemon=True, name=f"deep-{job.id}").start()


def teilbericht_starten(job: DeepJob, nwz_db: str, council_db: str) -> bool:
    """Nach einem Stopp: aus dem gesicherten Material doch noch den
    (Teil-)Bericht schreiben. False, wenn kein Material da ist."""
    if job.material is None or not job.material.get("candidates"):
        return False
    with job.cond:
        job.done = False
    job.stop.clear()
    threading.Thread(target=_schreiben_und_abschliessen,
                     args=(job, nwz_db, council_db, True),
                     daemon=True, name=f"deep-teil-{job.id}").start()
    return True


def _quellen_payload(m: dict, cited: list[int]) -> dict:
    """Der persistierte Quellen-Block — deckungsgleich mit dem sources-Event,
    damit der Client einen fertigen Job identisch rendern kann."""
    return {"sources": m["sources"], "presse": m["presse_kompakt"],
            "debatten": m["debatten_kompakt"], "planungen": m["planungen"],
            "anlagen": m.get("anlagen_kompakt", []),
            "facetten": m["facetten_namen"], "facetten_fertig": m["facetten_fertig"],
            "gelesen": m["gelesen"], "zeitraum": m["zeitraum"], "cited": cited}


def _run(job: DeepJob, nwz_db: str, council_db: str) -> None:
    """Der komplette Recherche-Ablauf. Läuft im eigenen Thread mit eigenen
    DB-Verbindungen (SQLite-Objekte sind nicht thread-übergreifend nutzbar)."""
    from council import qa
    # Runtime-Import statt Modul-Import: routers.council importiert dieses
    # Modul — zur Laufzeit ist der Router längst geladen, beim Modul-Import
    # wäre es ein Zirkel.
    from .routers.council import _qa_source

    store = CouncilStore(council_db)
    try:
        # ---- Phase 1: zerlegen -------------------------------------------
        _emit(job, {"type": "phase", "phase": "zerlegen"})
        facetten = qa.deep_zerlege(job.frage)
        job.facetten_gesamt = len(facetten)
        _emit(job, {"type": "facetten", "facetten": [f["name"] for f in facetten]})

        # ---- Phase 2: je Facette suchen ----------------------------------
        try:
            from council import embeddings as emb
        except Exception:  # noqa: BLE001 — ohne fastembed keine Recherche
            emb = None
        # Akkuratheits-Paket: Entitäts-Anker der HAUPTfrage in jede
        # Facetten-Suche, Frische-Bonus bei Sachstands-Formulierung.
        anker = qa.anker_ids_fuer(store, job.frage)
        frisch = qa.recency_intent(job.frage)
        beste: dict[int, float] = {}
        for f in facetten:
            if job.stop.is_set():
                _gestoppt(job, nwz_db)
                return
            hits: list[tuple[int, float]] = []
            if emb is not None:
                try:
                    hits = emb.hybrid_search(store, f["frage"], f["begriffe"],
                                             top_k=JE_FACETTE, pool=45,
                                             anker_ids=anker, recency=frisch)
                except Exception:  # noqa: BLE001 — eine kaputte Facette killt nicht den Job
                    _log.warning("deep %s: Facette %r ohne Treffer (Suche scheiterte)",
                                 job.id, f["name"], exc_info=True)
            neu = 0
            for did, s in hits:
                if did not in beste:
                    neu += 1
                    beste[did] = s
                elif s > beste[did]:
                    beste[did] = s
            job.facetten_fertig += 1
            _emit(job, {"type": "facette", "name": f["name"], "treffer": len(hits),
                        "neu": neu, "fertig": job.facetten_fertig,
                        "gesamt": job.facetten_gesamt})

        geordnet = sorted(beste.items(), key=lambda kv: -kv[1])[:MAX_KANDIDATEN]
        candidates = store.get_decisions_by_ids([did for did, _ in geordnet])
        qa.markiere_veraltete(store, candidates)
        score = dict(geordnet)
        for c in candidates:
            logit = score.get(c["id"])
            c["score"] = (round(1.0 / (1.0 + math.exp(-(logit + RERANK_BIAS))), 3)
                          if logit is not None else None)

        # Zusatzkanäle wie im /ask-Pfad — Debatten hier breiter (top_k=12),
        # der Bericht hat einen eigenen Debatten-Abschnitt.
        begriffe_alle = " ".join(dict.fromkeys(
            " ".join(f["begriffe"] for f in facetten).split()))[:300]
        presse_rows: list[dict] = []
        debatten_rows: list[dict] = []
        anlagen_rows: list[dict] = []
        if emb is not None:
            try:
                hits_p = emb.search_presse(store, job.frage, begriffe_alle)
                presse_rows = store.presse_by_ids([pid for pid, _ in hits_p])
            except Exception:  # noqa: BLE001 — Zusatz, nie Blocker
                pass
            try:
                hits_w = emb.search_wortbeitraege(store, job.frage, begriffe_alle, top_k=12)
                debatten_rows = store.wortbeitraege_by_ids([wid for wid, _ in hits_w])
            except Exception:  # noqa: BLE001
                pass
            try:
                # Task 33: Anlagen (Gutachten, Konzepte) — dieser Kanal existiert
                # NUR hier; die schnelle Frage lädt die Anlagen-Matrix nie.
                hits_a = emb.search_anlagen(store, job.frage, begriffe_alle, top_k=6)
                anlagen_rows = store.anlagen_by_ids([did for did, _, _ in hits_a])
                fundstellen = {did: fs for did, _, fs in hits_a}
                for a in anlagen_rows:
                    a["fundstelle"] = fundstellen.get(a["document_id"], "")
            except Exception:  # noqa: BLE001
                pass
        try:
            orte = store.orte_fuer_decisions([c["id"] for c in candidates])
            for c in candidates:
                c.update(orte.get(c["id"], {}))
        except Exception:  # noqa: BLE001
            pass
        try:
            planungen = store.geplante_beratungen_fuer(
                [c.get("kvonr") for c in candidates[:20]])
        except Exception:  # noqa: BLE001
            planungen = []
        haushalt_zeilen: list[dict] = []
        try:
            haushalt_zeilen = store.haushalt_fuer_begriffe(begriffe_alle.split())
        except Exception:  # noqa: BLE001
            pass

        jahre = sorted({str(c.get("session_date") or "")[:4]
                        for c in candidates if c.get("session_date")})
        zeitraum = f"{jahre[0]}–{jahre[-1]}" if len(jahre) > 1 else (jahre[0] if jahre else "")
        gelesen = (len(candidates) + len(debatten_rows) + len(presse_rows)
                   + len(anlagen_rows))

        job.material = {
            "candidates": candidates, "presse": presse_rows, "debatten": debatten_rows,
            "haushalt": haushalt_zeilen, "planungen": planungen, "anlagen": anlagen_rows,
            "facetten_namen": [f["name"] for f in facetten],
            "facetten_fertig": job.facetten_fertig, "gelesen": gelesen,
            "zeitraum": zeitraum,
            "sources": [_qa_source(c) for c in candidates],
            "presse_kompakt": [{"titel": p.get("titel"), "url": p.get("url"),
                                "datum": p.get("datum")} for p in presse_rows],
            "debatten_kompakt": [{"sprecher": d.get("sprecher"), "partei": d.get("partei"),
                                  "art": d.get("art"), "top": d.get("top"),
                                  "auszug": (d.get("text") or "")[:220],
                                  "committee": d.get("committee"),
                                  "datum": d.get("session_date")} for d in debatten_rows],
            "anlagen_kompakt": [{"label": a.get("label"), "url": a.get("url"),
                                 "vorlage_nr": a.get("vorlage_nr"),
                                 "vorlage_titel": a.get("vorlage_titel"),
                                 "auszug": (a.get("fundstelle") or "")[:220]}
                                for a in anlagen_rows],
        }
        m = job.material
        _emit(job, {"type": "sources", "mode": "recherche", "qtype": "deep",
                    "frage": job.frage, "sources": m["sources"],
                    "presse": m["presse_kompakt"], "debatten": m["debatten_kompakt"],
                    "anlagen": m["anlagen_kompakt"],
                    "planungen": m["planungen"], "gelesen": gelesen,
                    "zeitraum": zeitraum})

        if not candidates:
            # Ehrlich beenden statt einen leeren „Bericht" zu erfinden. Der
            # Job zählt trotzdem als gelaufen (er hat gesucht) — aber der
            # Text sagt klar, dass nichts da ist.
            text = ("Dazu habe ich in den Ratsunterlagen nichts Belastbares gefunden. "
                    "Versuche es mit einer konkreteren Frage — oder als schnelle Frage.")
            _emit(job, {"type": "token", "text": text})
            _emit(job, {"type": "done", "cited": [], "gelesen": gelesen,
                        "zeitraum": zeitraum, "gespraech_id": None})
            _db_update(nwz_db, job.id, "fertig", bericht=text,
                       quellen_json=json.dumps(_quellen_payload(m, []), ensure_ascii=False))
            _finish(job)
            return

        # ---- Phase 3: lesen (volle Vorlagen-Auszüge) ---------------------
        if job.stop.is_set():
            _gestoppt(job, nwz_db)
            return
        _emit(job, {"type": "phase", "phase": "lesen", "dokumente": gelesen})
        try:
            from council import vorlagen as vorlagen_mod
            texts = store.vorlage_texts_for([c.get("vorlage_nr") or "" for c in candidates])
            for i, c in enumerate(candidates):
                t = texts.get((c.get("vorlage_nr") or "").strip())
                if t:
                    grenze = VOLLTEXT_ZEICHEN if i < VOLLTEXT_TOP else KURZTEXT_ZEICHEN
                    c["vorlage_excerpt"] = vorlagen_mod.excerpt(t, grenze)
        except Exception:  # noqa: BLE001 — Auszüge sind Kür, nie Blocker
            pass

        # ---- Phase 4: schreiben ------------------------------------------
        _schreiben_und_abschliessen(job, nwz_db, council_db, False)
    except Exception:  # noqa: BLE001 — terminaler Fehler → ehrlich melden
        _log.exception("deep %s: Recherche fehlgeschlagen", job.id)
        _fehler(job, nwz_db)
    finally:
        store.close()


def _schreiben_und_abschliessen(job: DeepJob, nwz_db: str, council_db: str,
                                teilbericht: bool) -> None:
    """Phase „Bericht schreiben" + Persistenz + Gesprächs-Anhang. Läuft am Ende
    von ``_run`` — oder als eigener Thread für den Teilbericht nach Stopp."""
    from council import qa

    import time as time_mod

    m = job.material or {}
    candidates = m.get("candidates") or []
    try:
        _emit(job, {"type": "phase", "phase": "schreiben"})
        vermerk = ""
        if teilbericht:
            fehlend = m.get("facetten_namen", [])[m.get("facetten_fertig", 0):]
            vermerk = (f"**Teilbericht — {m.get('facetten_fertig', 0)} von "
                       f"{len(m.get('facetten_namen', []))} Facetten.**"
                       + (f" Nicht mehr untersucht: {', '.join(fehlend)}." if fehlend else "")
                       + "\n\n")
            if vermerk:
                _emit(job, {"type": "token", "text": vermerk})
        # Der Berichts-Stream darf reißen (Provider-Limits, Netz) — anders als
        # bei /ask wartet hier niemand auf Millisekunden: einfach mit Backoff
        # komplett neu generieren. Ein replace-Event räumt den Torso beim
        # Client weg, die Event-Liste bleibt für Replays konsistent.
        buf = ""
        for versuch in range(3):
            if versuch > 0:
                _emit(job, {"type": "replace", "text": vermerk})
            buf, gesendet = "", 0
            try:
                for delta in qa.deep_bericht_stream(job.frage, candidates,
                                                    presse=m.get("presse"),
                                                    debatten=m.get("debatten"),
                                                    haushalt=m.get("haushalt"),
                                                    planungen=m.get("planungen"),
                                                    anlagen=m.get("anlagen")):
                    if job.stop.is_set():
                        break
                    buf += delta
                    # Deltas bündeln: weniger, dafür tragfähige Events — der
                    # Replay nach einem Reconnect bleibt so klein.
                    if len(buf) - gesendet >= TOKEN_BUENDEL:
                        _emit(job, {"type": "token", "text": buf[gesendet:]})
                        gesendet = len(buf)
                if len(buf) > gesendet:
                    _emit(job, {"type": "token", "text": buf[gesendet:]})
                break
            except Exception:  # noqa: BLE001 — riss der Stream: neuer Anlauf
                if versuch == 2:
                    raise
                _log.warning("deep %s: Bericht-Stream riss (Versuch %d/3) — neuer Anlauf",
                             job.id, versuch + 1, exc_info=True)
                time_mod.sleep(5 * (versuch + 1))
                if job.stop.is_set():
                    break
        if job.stop.is_set() and not teilbericht:
            # Stopp mitten im Schreiben: Material bleibt gesichert, ein
            # „Teilbericht zeigen" generiert daraus einen sauberen Text.
            _gestoppt(job, nwz_db)
            return

        bericht = vermerk + buf
        _, cited = qa.resolve_citations(bericht, {c["id"] for c in candidates})

        nwz = Store(nwz_db)
        try:
            gespraech_id = _gespraech_anhaengen(nwz, job, bericht, m, cited)
            status = "teilbericht" if teilbericht else "fertig"
            nwz.deep_job_update(job.id, status, bericht=bericht,
                                quellen_json=json.dumps(_quellen_payload(m, cited),
                                                        ensure_ascii=False))
        finally:
            nwz.close()
        _emit(job, {"type": "done", "cited": cited, "gelesen": m.get("gelesen", 0),
                    "zeitraum": m.get("zeitraum", ""), "gespraech_id": gespraech_id,
                    "teilbericht": teilbericht})
        _finish(job)
        registry_aufraeumen()
    except Exception:  # noqa: BLE001
        _log.exception("deep %s: Bericht scheiterte", job.id)
        _fehler(job, nwz_db)


def _gespraech_anhaengen(nwz: Store, job: DeepJob, bericht: str,
                         m: dict, cited: list[int]) -> int | None:
    """„Bericht erscheint hier im Gespräch": mit Einwilligung (qa_speichern)
    den Bericht als Turn ins laufende Gespräch hängen — best-effort."""
    try:
        if nwz.get_qa_speichern(job.user_id) != 1:
            return None
        gespraech_id = job.gespraech_id
        neu = gespraech_id is None
        if neu:
            gespraech_id = nwz.qa_gespraech_start(job.user_id, job.frage)
            if gespraech_id is None:
                return None
        zitiert = set(cited)
        # Der volle Anzeige-Stoff gehört in den Gesprächs-Snapshot — ein
        # später geladener Recherche-Turn soll aussehen wie frisch erzeugt
        # (Presse, Debatten, Anlagen, Planungen, Meta-Zahlen; Tims Befund
        # 10.08. zu verschwindenden Blöcken in geladenen Gesprächen).
        quellen_json = json.dumps(
            {"sources": [s for s in m.get("sources", []) if s.get("id") in zitiert],
             "cited": cited, "recherche": True,
             "presse": m.get("presse_kompakt", []),
             "debatten": m.get("debatten_kompakt", []),
             "anlagen": m.get("anlagen_kompakt", []),
             "planungen": m.get("planungen", []),
             "gelesen": m.get("gelesen"), "zeitraum": m.get("zeitraum")},
            ensure_ascii=False)
        if not nwz.qa_turn_speichern(gespraech_id, job.user_id, job.frage,
                                     bericht, quellen_json):
            if neu:
                nwz.qa_gespraech_loeschen(gespraech_id, job.user_id)
            return None
        return gespraech_id
    except Exception:  # noqa: BLE001 — Speichern ist Zusatz, nie Blocker
        return None


def _db_update(nwz_db: str, job_id: str, status: str, bericht: str | None = None,
               quellen_json: str | None = None) -> None:
    """Kurzlebige eigene Verbindung — der Job-Thread darf keine Request-Stores
    teilen, und offene Handles sollen nicht liegen bleiben."""
    store = Store(nwz_db)
    try:
        store.deep_job_update(job_id, status, bericht=bericht, quellen_json=quellen_json)
    finally:
        store.close()


def _gestoppt(job: DeepJob, nwz_db: str) -> None:
    hat_material = bool(job.material and job.material.get("candidates"))
    _emit(job, {"type": "gestoppt", "facetten_fertig": job.facetten_fertig,
                "facetten_gesamt": job.facetten_gesamt,
                "teilbericht_moeglich": hat_material})
    try:
        _db_update(nwz_db, job.id, "gestoppt")
    except Exception:  # noqa: BLE001
        pass
    _finish(job)


def _fehler(job: DeepJob, nwz_db: str) -> None:
    _emit(job, {"type": "fehler"})
    try:
        _db_update(nwz_db, job.id, "fehler")
    except Exception:  # noqa: BLE001
        pass
    _finish(job)
