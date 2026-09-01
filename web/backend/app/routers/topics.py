"""Topic management and committee subscriptions for the web account.

Ownership is keyed on the web account (owner_id = web_users.id); a linked
Telegram chat is only a delivery target, so these endpoints work for web-only
users too. Topics match against council decisions (semantic); the former NWZ
article matching was removed with the NWZ scraper.

**Eine Definition von „Beschlüsse zu diesem Thema"** — sie steht in
``council.topic_intel`` (Cross-Encoder ≥ ``SCHWELLE``, höchstens ``DECKEL``
Treffer, „gedeckelt" wird als „40+" ausgewiesen). Alles, was hier eine Zahl
ausliefert, bezieht sich darauf:

* ``GET /topics`` → ``decision_count`` (+ ``decision_count_capped``): die
  gespeicherten Treffer des letzten Matching-Laufs — die Zahl auf der Karte.
* ``GET /council/decisions?topic=…`` → dieselbe Menge als Liste. Sie darf nicht
  heimlich kleiner sein als die Karte; die Liste holt sich das Thema über
  ``get_topic_decision_matches``.
* ``POST /topics/describe`` → ``matches`` (+ ``matches_capped``): dieselbe
  Rechnung, aber live auf den Text im Bearbeiten-Blatt statt auf den
  gespeicherten Stand. Die beiden Zahlen dürfen auseinandergehen (der Text ist
  noch ungespeichert) — deshalb beschriftet das Blatt seine Zahl als Vorschau
  und nicht als Bestand.
* ``POST /topics`` und ``PUT /topics/{id}`` → dieselbe Rechnung, sofort und
  gespeichert (``_erstabgleich``). Bis zum 28.08.2026 schrieb nur der
  Wochenlauf Treffer, ein neues Thema stand also bis zu sieben Tage auf 0 —
  und die Karte machte daraus „Noch keine Treffer, wir melden uns, sobald der
  Rat dazu entscheidet". Bei „Schulbegleitung" (34 Beschlüsse seit 2018) war
  das keine fehlende Zahl, sondern eine falsche Aussage über den Rat.

Bis zum 16.08.2026 waren es drei verschiedene Rechnungen mit drei
verschiedenen Ergebnissen (Tim, Build 12: „40+" / „12 Beschlüsse" / 25 Treffer
zu ein und demselben Thema).
"""
from __future__ import annotations

import re
import logging
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from kern.store import Store
from council.store import CouncilStore

from ..antworten import (AboGeloescht, AboGesetzt, Abonnements, MarkierteTreffer, Ok,
                        ThemenBeschluesse, ThemenBeschreibung, ThemenTrefferListe,
                        ThemenVorschlaege, UngeleseneThemenTreffer)
from ..deps import get_council_store, get_store, require_active
from ..ratelimit import topic_describe_limiter, topic_match_limiter
from ..schemas import SubscriptionIn, TopicDescribeIn, TopicHitOut, TopicIn, TopicOut, TopicSeenIn

logger = logging.getLogger("ratslotse.web.topics")

router = APIRouter(prefix="/api/topics", tags=["topics"])


def _vor_sechs_monaten(heute: date | None = None) -> date:
    """Der Stichtag hinter „n in 6 Monaten" — gerechnet wird er in
    ``council.topic_intel``, weil seit dem 30.08.2026 auch der Wochenlauf
    daran misst, ob ein neuer Treffer eine Mail wert ist. Zwei Kopien wären
    zwei Grenzen, sobald eine davon jemand anfasst.

    Absichtlich erst im Aufruf importiert, wie jede andere Berührung mit
    ``topic_intel`` in dieser Datei: Das Modul zieht ``kern.llm`` und damit das
    openai-SDK nach, und das steht in ``requirements.txt``, nicht in
    ``web/backend/requirements.txt`` — ein Import auf Modulebene machte den
    API-Start davon abhängig.
    """
    from council.topic_intel import vor_sechs_monaten

    return vor_sechs_monaten(heute)


def _own_topic(store: Store, owner_id: int, topic_id: int):
    topic = store.get_topic_for_owner(owner_id, topic_id)
    if topic is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Thema nicht gefunden.")
    return topic


def _erstabgleich(store: Store, council: CouncilStore, topic, owner_id: int) -> tuple[int, bool, bool]:
    """Ein frisch angelegtes oder neu beschriebenes Thema sofort abgleichen —
    ``(count, gedeckelt, abgeglichen)``.

    Gerechnet wird mit ``topic_intel.treffer``, derselben Funktion wie im
    Wochenlauf: eine Definition, eine Zahl (s. Modul-Kopf). Gespeichert wird
    sie auch, denn eine Zahl ohne die zugehörigen Zeilen wäre die vierte
    Wahrheit — „alle ansehen" führte dann in eine leere Liste.

    Zwei Feinheiten sind nicht Geschmack, sondern Bedingung:

    ``als_neu=False`` — der Bestand ist keine Neuigkeit. Mit dem Zeitstempel
    von jetzt zöge ihn der Wochenüberblick (``council.abendmeldungen``, N6) in
    „Diese Woche: n Beschlüsse zu deinen Themen" und meldete sonntags
    Beschlüsse von 2019 als Nachricht der Woche. Genau das ist am 17.08.2026
    schon einmal passiert (s. ``Store.save_topic_decision_matches``).

    ``mark_topic_hits_seen`` — der ungelesen-Zähler hängt an ``topic_hits_seen``,
    nicht am Zeitstempel. Ohne den Aufruf trüge das neue Thema sofort ein
    „40 neu"-Abzeichen für Beschlüsse, die die Nutzer:in nie als neu erlebt
    hat: Sie sieht die Zahl ja gerade entstehen.

    Eine Meldung löst das nicht aus, und zwar aus demselben Grund wie im Cron:
    Der Erst-Abgleich eines Themas hat keinen Vorgänger, gegen den er sich als
    „neu" abheben könnte (``match_topics_decisions`` prüft dafür ``old_ids``).

    ``abgeglichen=False`` heißt „ließ sich hier gerade nicht rechnen" — dann
    bleibt es beim Wochenlauf, und die Karte sagt „wird noch gezählt" statt
    eine 0 zu behaupten.
    """
    from council import topic_intel

    name = (topic.name or "").strip()
    text = f"{name}. {(topic.description or '').strip()}".strip()
    try:
        # Dieselbe Vorprüfung wie in ``zaehle_treffer``: Ohne Embedding-Bestand
        # hätte auch der Wochenlauf nie etwas gespeichert, und der Aufruf würde
        # in Tests und frischen Umgebungen nur das ~1 GB große Reranker-Modell
        # nachladen — für ein Ergebnis, das feststeht.
        if not council.embeddings_version()[0]:
            return 0, False, False
        hits, gedeckelt, kandidaten = topic_intel.treffer(council, name, text)
    except Exception:  # noqa: BLE001
        # Kein Cross-Encoder, kein Embedding-Bestand, Modell-Download klemmt:
        # Daran darf das Anlegen nie scheitern. Fehlt hier etwas, ist es die
        # Zahl — nicht das Thema.
        logger.warning("Erstabgleich für Thema %s fehlgeschlagen", topic.id, exc_info=True)
        return 0, False, False
    store.save_topic_decision_matches(topic.id, owner_id, hits, gedeckelt=gedeckelt,
                                      kandidaten=kandidaten, als_neu=False)
    store.mark_topic_hits_seen(owner_id, topic.id)
    return len(hits), gedeckelt, True


@router.get("", response_model=list[TopicOut])
def list_topics(
    user: dict = Depends(require_active),
    store: Store = Depends(get_store),
    council: CouncilStore = Depends(get_council_store),
) -> list[TopicOut]:
    owner_id = user["id"]
    unseen = store.unseen_hit_counts(owner_id)
    topics = store.get_topics(owner_id)
    # Gezählt wird, was die Suche auch findet. Die gespeicherten Treffer liegen
    # in ratslotse.sqlite, die Beschlüsse in council.sqlite — verschwindet ein
    # Beschluss (Neu-Extraktion vergibt neue IDs), bleibt die Zeile hier stehen
    # und der Zähler versprach Treffer, die „alle ansehen" nicht liefern konnte
    # (Tims Befund 15.08.: „8 Einträge" → Suche sagt „nichts gefunden").
    # Deshalb erst nachschlagen, dann zählen.
    cand: dict[int, list[int]] = {t.id: [m["decision_id"] for m in store.get_topic_decision_matches(t.id)]
                                  for t in topics}
    all_ids = [d for ids in cand.values() for d in ids]
    by_id = {d["id"]: d for d in council.get_decisions_by_ids(all_ids)} if all_ids else {}
    dec_counts = {tid: sum(1 for d in ids if d in by_id) for tid, ids in cand.items()}
    # Ob der Matching-Lauf gedeckelt hat, weiß nur er selbst — die Zahl der
    # gespeicherten Zeilen sieht bei „genau 40 gefunden" und „bei 40 abgeschnitten"
    # gleich aus. Fehlt die Zeile (Bestand vor dem 15.08.2026), gilt: nicht gedeckelt.
    # Die Meta-Zeile entsteht bei JEDEM Abgleich, auch bei einem mit null
    # Treffern. Ihre bloße Anwesenheit beantwortet deshalb die Frage, an der
    # die Karte bisher scheiterte: „schon gerechnet?" — und trennt damit
    # „der Rat hat dazu nichts entschieden" von „die Zahl steht noch aus".
    capped = store.topic_match_caps(owner_id)
    # Welche Treffer ungelesen sind, nicht nur wie viele: Die Karte setzt seit
    # dem Umbau vom 28.08.2026 einen Punkt vor jede neue Zeile. Beides stammt
    # aus derselben Abfrage, damit Abzeichen und Punkte nie auseinandergehen.
    unseen_ids = store.unseen_hit_ids(owner_id)
    as_of_date = _vor_sechs_monaten().isoformat()
    out = []
    for t in topics:
        hits = sorted((by_id[d] for d in cand.get(t.id, []) if d in by_id),
                      key=lambda d: d.get("session_date") or "", reverse=True)
        last = hits[0] if hits else None
        neu = unseen_ids.get(t.id, set())
        out.append(
            TopicOut(
                id=t.id,
                name=t.name,
                description=t.description,
                created_at=t.created_at,
                decision_count=dec_counts.get(t.id, 0),
                decision_count_capped=capped.get(t.id, False),
                matched=t.id in capped,
                last_hit_id=last["id"] if last else None,
                last_hit_title=last["title"] if last else None,
                last_hit_date=last.get("session_date") if last else None,
                unread_count=unseen.get(t.id, 0),
                # Fünf reichen: Die Karte ist eine Vorschau, die ganze Menge
                # steht hinter „alle ansehen" — und zwar dieselbe, weil beide
                # aus `cand` stammen.
                recent_hits=[
                    TopicHitOut(
                        id=d["id"],
                        title=(d.get("title") or "").strip(),
                        committee=d.get("committee") or "",
                        session_date=d.get("session_date") or "",
                        outcome=d.get("outcome"),
                        is_new=d["id"] in neu,
                    )
                    for d in hits[:5]
                ],
                hits_6m=sum(1 for d in hits if (d.get("session_date") or "") >= as_of_date),
            )
        )
    return out


def _name_tokens(name: str) -> frozenset[str]:
    """Wort-Stämme eines Themen-/Entitätsnamens: Kleinbuchstaben, Wörter auf
    6 Zeichen gekürzt (fängt „Stadion"/„Stadionneubau"), Ziffern bleiben ganz
    (unterscheidet „Veloroute 4" von „Veloroute 2")."""
    # Zusammengeschriebenes vorher trennen: Im Ratsbestand steht „AlteFleiwa"
    # neben „Alte Fleiwa" — zwei Entitäten für dieselbe Sache, die im selben
    # Vorschlagsblock landeten, weil {altefl} und {alte, fleiwa} keine
    # Teilmenge voneinander sind. Getrennt wird nur an klein→GROSS, damit
    # „OLantis", „IQON" und „EWE ARENA" unangetastet bleiben.
    name = re.sub(r"(?<=[a-zäöüß])(?=[A-ZÄÖÜ])", " ", name)
    words = re.findall(r"\d+|[a-zäöüß]+", name.lower())
    return frozenset(w if w.isdigit() else w[:6] for w in words if w.isdigit() or len(w) >= 3)


def _similar_names(a: frozenset[str], b: frozenset[str]) -> bool:
    """Gleiches Interesse, wenn die Wortmenge des einen im anderen aufgeht."""
    return bool(a) and bool(b) and (a <= b or b <= a)


def _suggestion_context(name: str, candidate: dict) -> str | None:
    """Kurze menschliche Einordnung für Vorschlagskarten.

    Eine reine Plan-Nummer ist kein verständliches Interesse. Bei nummerierten
    Bebauungsplänen steht der konkrete Ortsbezug fast immer in Klammern im
    jüngsten Beschlusstitel; genau dieser Teil ist die hilfreichste zweite
    Zeile. Für andere Entitäten reicht die redaktionelle Kurzbeschreibung.
    """
    description = (candidate.get("description") or "").strip()
    latest_title = (candidate.get("latest_title") or "").strip()
    if re.search(r"\b(?:vorhabenbezogener\s+)?bebauungsplan\s+\d", name, re.I):
        parenthetical = re.search(r"\(([^()]{4,160})\)", latest_title)
        if parenthetical:
            return re.sub(r"\s*/\s*", " / ", parenthetical.group(1)).strip()
        remainder = re.sub(re.escape(name), "", latest_title, count=1, flags=re.I)
        remainder = re.sub(
            r"^[\s:–—-]+|\s+[–—-]\s+(?:Aufstellungs|Auslegungs|Satzungs|Feststellungs).*$",
            "", remainder, flags=re.I,
        ).strip()
        if remainder:
            return remainder[:160].rstrip(" ,;:–—-")
    if description:
        sentence = re.split(r"(?<=[.!?])\s+", description, maxsplit=1)[0].strip()
        return sentence[:160].rstrip()
    return None


def _vorschlaege_bauen(council: CouncilStore, candidates: list[dict],
                       existing_tokens: list, chosen_tokens: list, limit: int = 6) -> list[dict]:
    """Aus Roh-Entitäten anzeigbare Vorschläge machen.

    Eigene Funktion, seit es ZWEI Listen gibt (Stadtteil und stadtweit):
    ``chosen_tokens`` wird von beiden Aufrufen geteilt und dabei fortgeschrieben
    — deshalb taucht ein Vorschlag, der schon im Stadtteil steht, in der
    stadtweiten Liste nicht noch einmal auf. Ohne das gemeinsame Gedächtnis
    stünde dieselbe Baustelle zweimal untereinander.
    """
    from council import topic_intel

    out: list[dict] = []
    # 26a-Zusage: Was hier vorgeschlagen wird, hat die Vagheits-Prüfung bestanden.
    # Zwei Stufen, damit das bezahlbar bleibt: erst der kostenlose Gattungswort-
    # Filter, dann das gecachte LLM-Urteil (je Slug genau einmal).
    verdicts = council.topic_vagueness_verdicts([c.get("slug") or "" for c in candidates])
    for e in candidates:
        name = (e.get("name") or "").strip()
        if not name or topic_intel.looks_generic(name):
            continue
        # Ähnlichkeits-Dedupe statt exaktem Namensvergleich: „Stadion
        # Maastrichter Straße", „Stadionneubau Maastrichter Straße" und
        # „Maastrichter Straße" sind EIN Interesse — der aktivste Kandidat
        # gewinnt, und wer so ein Thema schon hat, sieht keine Variante mehr.
        tokens = _name_tokens(name)
        if any(_similar_names(tokens, other) for other in existing_tokens + chosen_tokens):
            continue
        desc = (e.get("description") or "").strip()
        if desc:
            # Auf ~220 Zeichen kürzen (an Satzgrenze), damit die
            # Watcher-Beschreibung fokussiert bleibt.
            if len(desc) > 220:
                cut = desc[:220]
                desc = (cut[: cut.rfind(".") + 1] or cut).strip()
            description = f"{desc} Neue Beschlüsse, Planungen und Maßnahmen dazu."
        else:
            description = (
                f"Neue Beschlüsse, Planungen und Maßnahmen des Oldenburger "
                f"Stadtrats rund um {name}."
            )
        slug = e.get("slug") or ""
        verdict = verdicts.get(slug)
        if verdict is None or verdict.get("name") != name:
            # Noch nie (oder unter anderem Namen) geprüft — jetzt einmal, dann
            # gemerkt. Fällt die Prüfung aus, gilt „nicht vage": lieber ein
            # Vorschlag zu viel als eine leere Liste, weil das LLM hakt.
            verdict = topic_intel.check_vagueness(name, description)
            try:
                council.save_topic_vagueness(slug, name, verdict)
            except Exception:  # noqa: BLE001 — Cache ist Beiwerk, nie blockierend
                logger.warning("Vagheits-Urteil für %s nicht speicherbar", slug, exc_info=True)
        if verdict.get("vague"):
            continue
        chosen_tokens.append(tokens)
        out.append({
            "name": name,
            "description": description,
            "context": _suggestion_context(name, e),
            "n": e["n_recent"],
        })
        if len(out) >= limit:
            break
    return out


#: Zeitfenster für die Stadtteil-Vorschläge, von eng nach weit. Ein FESTES Jahr
#: reichte nicht: Am Prod-Bestand (01.09.2026 nachgemessen) lieferten 6 der 31
#: Ortsbereiche darin gar nichts und 4 weitere ein bis zwei Vorschläge — wer
#: dort wohnt, sah einen leeren Block. Mit dem gleitenden Fenster steht überall
#: etwas. Erst die Zeit lockern und nicht die Qualitätsregeln: Ein zwei Jahre
#: alter echter Vorgang ist ein besserer Vorschlag als eine Adresse von gestern.
ORTS_FENSTER_TAGE = (365, 730, 1095)

#: Wie viele Nachbar-Ortsbereiche einen dünnen Stadtteil auffüllen dürfen. Drei
#: reichen: Damit kommen auf dem Prod-Bestand alle 31 auf sechs Vorschläge.
NACHBARN = 3


def _lokale_vorschlaege(council: CouncilStore, place, existing_tokens: list,
                        chosen_tokens: list) -> tuple[list[dict], list[dict], int]:
    """Vorschläge für einen Ortsbereich: eigene, nebenan, und wie weit zurück.

    Gibt zurück, WIE WEIT gesucht wurde (in Monaten): Die Oberfläche schreibt das
    dazu. „Aus Bornhorst" über einen drei Jahre alten Vorgang wäre sonst eine
    stille Behauptung von Aktualität — und die Designsprache verlangt bei Mengen
    ohnehin Zahl **und** Zeitraum.

    **Warum es „nebenan" gibt.** Am Prod-Bestand nachgemessen (01.09.2026):
    Selbst über drei Jahre kommen 15 der 31 Ortsbereiche nicht auf sechs
    Vorschläge, zwei auf gar keinen — im Dobbenviertel oder in Nordmoslesfehn
    hat der Rat schlicht kaum etwas verhandelt. Ein leerer Block wäre dort das
    Ergebnis, und zwar dauerhaft. Mit den drei nächstgelegenen Ortsbereichen
    füllen sich **alle 31** auf sechs.

    Getrennt zurückgegeben und in der Oberfläche getrennt beschriftet: Ein
    Vorgang aus Haarenesch unter der Überschrift „Aus Dobbenviertel" wäre
    schlicht falsch. Nebenan ist eine ehrliche Auskunft, verkleidet wäre es
    eine Behauptung.
    """
    letzte: list[dict] = []
    for tage in ORTS_FENSTER_TAGE:
        # `chosen_tokens` NICHT je Runde mitschreiben lassen: Ein Vorschlag, den
        # das enge Fenster schon verworfen hat, würde sich sonst im weiten selbst
        # blockieren. Erst das Ergebnis der gewählten Runde zählt.
        probe = list(chosen_tokens)
        gefunden = _vorschlaege_bauen(
            council, council.suggested_entity_topics(days_back=tage, limit=16, place_id=place.id),
            existing_tokens, probe, limit=6)
        letzte = gefunden
        if len(gefunden) >= 6:
            break
    for eintrag in letzte:
        chosen_tokens.append(_name_tokens(eintrag["name"]))

    nebenan: list[dict] = []
    if len(letzte) < 6:
        from council import geo

        for nachbar in geo.nachbar_ortsbereiche(place.name, NACHBARN):
            if len(letzte) + len(nebenan) >= 6:
                break
            nb = council.resolve_place(nachbar)
            if not nb:
                continue
            # Immer das weiteste Fenster: Nebenan ist ohnehin der Notnagel, da
            # zählt „gibt es überhaupt etwas" mehr als „ist es taufrisch".
            for eintrag in _vorschlaege_bauen(
                council,
                council.suggested_entity_topics(days_back=ORTS_FENSTER_TAGE[-1], limit=16,
                                                place_id=nb.id),
                existing_tokens, chosen_tokens, limit=6 - len(letzte) - len(nebenan),
            ):
                nebenan.append({**eintrag, "place": nb.name})
    return letzte, nebenan, round(tage / 30.4)


@router.get("/suggestions")
def topic_suggestions(
    district: Annotated[list[str], Query()] = [],  # noqa: B006 — FastAPI liest die Vorgabe nur
    user: dict = Depends(require_active),
    store: Store = Depends(get_store),
    council: CouncilStore = Depends(get_council_store),
) -> ThemenVorschlaege:
    """Anklickbare Themen-Vorschläge aus den echten Daten: konkrete Orte und
    Projekte mit jüngster Ratsaktivität (Entitäten) statt der häufigsten
    Schlagworte — die belohnten Verwaltungsvokabeln („Bericht", „Annahme").
    Die KI-Beschreibung der Entität wird zur Themen-Beschreibung und macht
    den Themen-Wächter treffsicherer als ein generischer Satz. Ohne Themen,
    die der Account schon angelegt hat; ein Klick legt direkt an.

    ``?district=<place_id>`` (mehrfach erlaubt) hängt je Ortsbereich eine
    **eigene** Liste davor: dieselbe Auswahl, auf diesen Ortsbereich
    eingeschränkt. Die Trennung ist der Punkt — „was ist in Osternburg los?"
    ist eine andere Frage als „was läuft gerade in der Stadt?", und wer beides
    getrennt sieht, kann wählen. Die Ortsbereiche stehen zuerst und in der
    Reihenfolge, in der sie gefragt wurden; was dort schon vorkommt,
    wiederholen weder die anderen Ortsbereiche noch die stadtweite Liste.
    """
    existing_tokens = [_name_tokens(t.name) for t in store.get_topics(user["id"])]
    chosen_tokens: list[frozenset[str]] = []

    gruppen = []
    for wunsch in dict.fromkeys(district):        # doppelt Gefragtes einmal
        place = council.resolve_place(wunsch)
        if not place:
            continue                              # geraten oder veraltet — still übergehen
        lokal, nebenan, fenster = _lokale_vorschlaege(
            council, place, existing_tokens, chosen_tokens)
        # Auch mit leerer Liste antworten: „In diesem Stadtteil war zuletzt
        # nichts" ist eine Auskunft. Ein weggelassener Block sähe aus wie ein
        # Fehler.
        gruppen.append({"place_id": place.id, "name": place.name,
                        "suggestions": lokal, "nearby": nebenan, "months": fenster})

    stadtweit = _vorschlaege_bauen(
        council, council.suggested_entity_topics(days_back=365, limit=16),
        existing_tokens, chosen_tokens, limit=6)
    return {"suggestions": stadtweit, "districts": gruppen}


@router.post("/describe")
def describe_topic(
    body: TopicDescribeIn,
    request: Request,
    user: dict = Depends(require_active),
    council: CouncilStore = Depends(get_council_store),
) -> ThemenBeschreibung:
    """Design 26a / RL-U17: aus einem Themen-*Namen* eine Beschreibung machen.

    Der Nutzer tippt nur „Cäcilienbrücke". Wir suchen die Beschlüsse dazu und
    lassen daraus einen präzisen Satz formulieren — das ist der Text, an dem der
    Themen-Wächter später jeden neuen Beschluss misst, also lohnt die Mühe.

    Nichts hier blockiert: Wer keinen Rats-Bezug hat oder zu vage schreibt,
    bekommt einen Hinweis und darf trotzdem speichern. Der Endpunkt urteilt,
    er verbietet nicht.

    Mit ``description`` im Body wird zusätzlich die (bis 26a brachliegende)
    Vagheits-Prüfung auf den selbst getippten Text angewandt.

    ``matches``/``matches_capped`` zählen nach derselben Definition wie die
    Themen-Karte (s. Modul-Kopf), nur eben auf den Text, der gerade im Feld
    steht: Wer die Beschreibung ändert, soll vorher sehen, was das mit der
    Trefferliste macht. Vorher lief hier eine eigene Suche mit eigener
    Schwelle und einem Deckel von 12 — daher stand unter jedem breiten Thema
    „12 Beschlüsse", während die Karte „40+" sagte.
    """
    topic_describe_limiter.check(request)
    from council import topic_intel

    name = body.name.strip()
    own = (body.description or "").strip()
    # Gezählt wird auf „Name. eigener Text" — ohne eigenen Text auf den Namen
    # allein. Kein zweiter Durchlauf auf die frisch erzeugte Beschreibung: Die
    # Bewertung des Cross-Encoders hängt am Namen (er ist die Rerank-Anfrage),
    # der Fließtext steuert nur die Kandidatenauswahl — ein zweiter Lauf kostete
    # einen weiteren LLM-Aufruf und verschöbe die Zahl kaum.
    result = topic_intel.analyse(council, name, own)
    # Vagheit nur für selbst geschriebene Texte: Was wir selbst erzeugt haben,
    # ist per Konstruktion aus Beschlüssen abgeleitet und damit konkret.
    check = topic_intel.check_vagueness(name, own) if own else {"vague": False, "hint": "", "suggestion": ""}
    return {
        "name": name,
        "description": result["description"],
        "matches": result["matches"],
        "matches_capped": result["matches_capped"],
        "examples": result["examples"],
        "verdict": result["verdict"],
        "is_council_topic": result["is_council_topic"],
        "reason": result["reason"],
        **check,
    }


@router.post("", response_model=TopicOut, status_code=status.HTTP_201_CREATED)
def add_topic(
    body: TopicIn,
    request: Request,
    user: dict = Depends(require_active),
    store: Store = Depends(get_store),
    council: CouncilStore = Depends(get_council_store),
) -> TopicOut:
    # Struktur-Prüfung auch hier, nicht nur im Formular: Die Themen-Beschreibung
    # wandert später in den Wächter-Prompt, ein als „Thema" getarnter Befehl wäre
    # also eine Prompt-Injection mit Umweg. Die Prüfung ist deterministisch und
    # braucht kein LLM — sie greift daher auch bei einem direkten API-Aufruf.
    from council import topic_intel

    if topic_intel.looks_like_instruction(body.name):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Ein Thema ist eine Sache, kein ganzer Satz — etwa „Cäcilienbrücke“ "
            "oder „Grundschule Krusenbusch“.",
        )
    # Erst die billige Struktur-Prüfung, dann die Bremse: Ein abgelehnter Satz
    # hat keine Rechnung ausgelöst und soll auch kein Kontingent kosten.
    topic_match_limiter.check(request)
    t = store.add_topic(user["id"], body.name, body.description)
    count, gedeckelt, abgeglichen = _erstabgleich(store, council, t, user["id"])
    return TopicOut(id=t.id, name=t.name, description=t.description, created_at=t.created_at,
                    decision_count=count, decision_count_capped=gedeckelt, matched=abgeglichen)


@router.delete("/{topic_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_topic(topic_id: int, user: dict = Depends(require_active), store: Store = Depends(get_store)) -> None:
    _own_topic(store, user["id"], topic_id)
    store.delete_topic(topic_id)


@router.put("/{topic_id}", response_model=TopicOut)
def update_topic(
    topic_id: int,
    body: TopicIn,
    request: Request,
    user: dict = Depends(require_active),
    store: Store = Depends(get_store),
    council: CouncilStore = Depends(get_council_store),
) -> TopicOut:
    owner_id = user["id"]
    _own_topic(store, owner_id, topic_id)
    topic_match_limiter.check(request)
    store.update_topic(topic_id, body.name, body.description)
    t = store.get_topic_for_owner(owner_id, topic_id)
    # Wer die Beschreibung ändert, ändert die Trefferliste — deshalb wird auch
    # hier sofort neu abgeglichen. Sonst zeigte das Blatt beim Tippen eine
    # Vorschau, und die Karte behielt bis Sonntag die Zahl zum alten Text.
    count, gedeckelt, abgeglichen = _erstabgleich(store, council, t, owner_id)
    caps = store.topic_match_caps(owner_id)
    if not abgeglichen:
        # Rechnung ausgefallen: Der gespeicherte Stand steht unberührt weiter
        # und wird gezählt wie in list_topics — inklusive Existenzprüfung, damit
        # die Karte keine Treffer verspricht, die „alle ansehen" nicht liefert.
        ids = [m["decision_id"] for m in store.get_topic_decision_matches(topic_id)]
        count = len(council.get_decisions_by_ids(ids)) if ids else 0
        gedeckelt = caps.get(topic_id, False)
    return TopicOut(
        id=t.id,
        name=t.name,
        description=t.description,
        created_at=t.created_at,
        decision_count=count,
        decision_count_capped=gedeckelt,
        matched=abgeglichen or topic_id in caps,
    )


@router.get("/unread-count")
def unread_count(user: dict = Depends(require_active), store: Store = Depends(get_store)) -> UngeleseneThemenTreffer:
    """RL-903: der Zähler an „Meine Themen" (Seitenleiste und Punkt in der
    Tab-Leiste) — Treffer, die seit dem letzten Blick auf die Übersicht
    dazugekommen sind. Die Bubble kündigt Neues an; wer nachgesehen hat, soll
    sie nicht erst durch Öffnen jedes einzelnen Themas loswerden (Tims Wunsch
    18.08.). Welches Thema neue Treffer hat, sagt weiter das „n neu" dort."""
    return {"total": store.neue_treffer_seit_uebersicht(user["id"])}


@router.post("/uebersicht-gesehen")
def uebersicht_gesehen(user: dict = Depends(require_active),
                       store: Store = Depends(get_store)) -> Ok:
    """Die Themen-Übersicht wurde geöffnet — ab jetzt zählt für die Bubble
    nur noch, was danach dazukommt. Ältere App-Versionen rufen das nie auf;
    für sie bleibt es beim bisherigen Verhalten."""
    store.topics_uebersicht_gesehen(user["id"])
    return {"ok": True}


@router.post("/{topic_id}/seen")
def mark_seen(
    topic_id: int,
    body: TopicSeenIn | None = None,
    user: dict = Depends(require_active),
    store: Store = Depends(get_store),
) -> MarkierteTreffer:
    """RL-903: Treffer eines Themas als gesehen markieren.

    Ohne ``decision_id`` alle — das ist der Weg über „alle ansehen" und über
    das „n neue"-Abzeichen, das sich selbst wegräumt. MIT ``decision_id`` nur
    dieser eine: Seit dem 28.08.2026 stehen die Treffer direkt auf der Karte,
    wer einen anklickt, hat genau den gelesen und keinen anderen — aus „2
    neue" wird dann „1 neuer" (Tims Wunsch).

    Der Body ist optional, damit ältere App-Versionen, die nur ``{}`` senden,
    unverändert alles markieren.
    """
    _own_topic(store, user["id"], topic_id)
    if body is not None and body.decision_id is not None:
        return {"marked": int(store.mark_topic_hit_seen(user["id"], topic_id, body.decision_id))}
    return {"marked": store.mark_topic_hits_seen(user["id"], topic_id)}


@router.get("/latest-hits")
def latest_hits(
    limit: int = Query(2, ge=1, le=10),
    user: dict = Depends(require_active),
    store: Store = Depends(get_store),
    council: CouncilStore = Depends(get_council_store),
) -> ThemenTrefferListe:
    """Die jüngsten Beschluss-Treffer über ALLE Themen des Kontos — für die
    „Neu zu deinen Themen"-Karte im Heute-Briefing (RL-401). Vor der
    {topic_id}-Route registriert, damit „latest-hits" nicht als ID parst."""
    pairs: list[tuple[str, int]] = []
    for t in store.get_topics(user["id"]):
        pairs += [(t.name, m["decision_id"]) for m in store.get_topic_decision_matches(t.id)[:10]]
    by_id = {d["id"]: d for d in council.get_decisions_by_ids([d_id for _, d_id in pairs])}
    rows = [
        {"topic_name": name, "id": d["id"], "title": d["title"],
         "committee": d["committee"], "session_date": d["session_date"]}
        for name, d_id in pairs if (d := by_id.get(d_id))
    ]
    rows.sort(key=lambda r: r["session_date"] or "", reverse=True)
    seen: set[int] = set()
    out = [r for r in rows if not (r["id"] in seen or seen.add(r["id"]))]
    return {"hits": out[:limit]}


@router.get("/{topic_id}/decisions")
def topic_decisions(
    topic_id: int,
    user: dict = Depends(require_active),
    store: Store = Depends(get_store),
    council: CouncilStore = Depends(get_council_store),
) -> ThemenBeschluesse:
    """Council decisions matched to this topic (semantic), best first.

    Dieselbe Menge, die die Karte zählt und ``/council/decisions?topic=…``
    anzeigt — ungefiltert und ohne eigenen Deckel. Wer hier filtert, baut die
    vierte Zahl.
    """
    owner_id = user["id"]
    _own_topic(store, owner_id, topic_id)
    matches = store.get_topic_decision_matches(topic_id)
    score_by = {m["decision_id"]: m["score"] for m in matches}
    decisions = council.get_decisions_by_ids([m["decision_id"] for m in matches])
    return {
        "decisions": [
            {
                "id": d["id"],
                "title": d["title"],
                "committee": d["committee"],
                "session_date": d["session_date"],
                "policy_field": d["policy_field"],
                "outcome": d["outcome"],
                "score": score_by.get(d["id"], 0.0),
            }
            for d in decisions
        ]
    }


# ---- committee subscriptions ----
sub_router = APIRouter(prefix="/api/subscriptions", tags=["subscriptions"])


@sub_router.get("")
def list_subscriptions(user: dict = Depends(require_active), store: Store = Depends(get_store)) -> Abonnements:
    return {"subscriptions": store.get_subscriptions(user["id"])}


@sub_router.post("", status_code=status.HTTP_201_CREATED)
def subscribe(body: SubscriptionIn, user: dict = Depends(require_active), store: Store = Depends(get_store)) -> AboGesetzt:
    ok = store.subscribe(user["id"], body.committee_name)
    return {"subscribed": ok, "committee_name": body.committee_name}


@sub_router.delete("")
def unsubscribe(body: SubscriptionIn, user: dict = Depends(require_active), store: Store = Depends(get_store)) -> AboGeloescht:
    ok = store.unsubscribe(user["id"], body.committee_name)
    return {"unsubscribed": ok, "committee_name": body.committee_name}
