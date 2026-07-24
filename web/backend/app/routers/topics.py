"""Topic management and committee subscriptions for the web account.

Ownership is keyed on the web account (owner_id = web_users.id); a linked
Telegram chat is only a delivery target, so these endpoints work for web-only
users too. Topics match against council decisions (semantic); the former NWZ
article matching was removed with the NWZ scraper.
"""
from __future__ import annotations

import re
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from nwz.store import Store
from council.store import CouncilStore

from ..deps import get_council_store, get_store, require_active
from ..ratelimit import topic_describe_limiter
from ..schemas import SubscriptionIn, TopicDescribeIn, TopicIn, TopicOut

logger = logging.getLogger("nwz.web.topics")

router = APIRouter(prefix="/api/topics", tags=["topics"])


def _own_topic(store: Store, owner_id: int, topic_id: int):
    topic = store.get_topic_for_owner(owner_id, topic_id)
    if topic is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Thema nicht gefunden.")
    return topic


@router.get("", response_model=list[TopicOut])
def list_topics(
    user: dict = Depends(require_active),
    store: Store = Depends(get_store),
    council: CouncilStore = Depends(get_council_store),
) -> list[TopicOut]:
    owner_id = user["id"]
    dec_counts = store.topic_decision_counts(owner_id)
    unseen = store.unseen_hit_counts(owner_id)
    topics = store.get_topics(owner_id)
    # Jüngster Treffer je Thema (RL-701): Kandidaten je Thema sammeln, Beschlüsse
    # in EINEM Batch nachschlagen, dann pro Thema das neueste Sitzungsdatum wählen.
    cand: dict[int, list[int]] = {t.id: [m["decision_id"] for m in store.get_topic_decision_matches(t.id)[:10]]
                                  for t in topics}
    all_ids = [d for ids in cand.values() for d in ids]
    by_id = {d["id"]: d for d in council.get_decisions_by_ids(all_ids)} if all_ids else {}
    out = []
    for t in topics:
        hits = sorted((by_id[d] for d in cand.get(t.id, []) if d in by_id),
                      key=lambda d: d.get("session_date") or "", reverse=True)
        last = hits[0] if hits else None
        out.append(
            TopicOut(
                id=t.id,
                name=t.name,
                description=t.description,
                created_at=t.created_at,
                decision_count=dec_counts.get(t.id, 0),
                last_hit_id=last["id"] if last else None,
                last_hit_title=last["title"] if last else None,
                last_hit_date=last.get("session_date") if last else None,
                unread_count=unseen.get(t.id, 0),
            )
        )
    return out


def _name_tokens(name: str) -> frozenset[str]:
    """Wort-Stämme eines Themen-/Entitätsnamens: Kleinbuchstaben, Wörter auf
    6 Zeichen gekürzt (fängt „Stadion"/„Stadionneubau"), Ziffern bleiben ganz
    (unterscheidet „Veloroute 4" von „Veloroute 2")."""
    words = re.findall(r"\d+|[a-zäöüß]+", name.lower())
    return frozenset(w if w.isdigit() else w[:6] for w in words if w.isdigit() or len(w) >= 3)


def _similar_names(a: frozenset[str], b: frozenset[str]) -> bool:
    """Gleiches Interesse, wenn die Wortmenge des einen im anderen aufgeht."""
    return bool(a) and bool(b) and (a <= b or b <= a)


@router.get("/suggestions")
def topic_suggestions(
    user: dict = Depends(require_active),
    store: Store = Depends(get_store),
    council: CouncilStore = Depends(get_council_store),
) -> dict:
    """Anklickbare Themen-Vorschläge aus den echten Daten: konkrete Orte und
    Projekte mit jüngster Ratsaktivität (Entitäten) statt der häufigsten
    Schlagworte — die belohnten Verwaltungsvokabeln („Bericht", „Annahme").
    Die KI-Beschreibung der Entität wird zur Themen-Beschreibung und macht
    den Themen-Wächter treffsicherer als ein generischer Satz. Ohne Themen,
    die der Account schon angelegt hat; ein Klick legt direkt an."""
    from council import topic_intel

    existing_tokens = [_name_tokens(t.name) for t in store.get_topics(user["id"])]
    chosen_tokens: list[frozenset[str]] = []
    out = []
    candidates = council.suggested_entity_topics(days_back=365, limit=16)
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
        out.append({"name": name, "description": description, "n": e["n_recent"]})
        if len(out) >= 6:
            break
    return {"suggestions": out}


@router.post("/describe")
def describe_topic(
    body: TopicDescribeIn,
    request: Request,
    user: dict = Depends(require_active),
    council: CouncilStore = Depends(get_council_store),
) -> dict:
    """Design 26a / RL-U17: aus einem Themen-*Namen* eine Beschreibung machen.

    Der Nutzer tippt nur „Cäcilienbrücke". Wir suchen die Beschlüsse dazu und
    lassen daraus einen präzisen Satz formulieren — das ist der Text, an dem der
    Themen-Wächter später jeden neuen Beschluss misst, also lohnt die Mühe.

    Nichts hier blockiert: Wer keinen Rats-Bezug hat oder zu vage schreibt,
    bekommt einen Hinweis und darf trotzdem speichern. Der Endpunkt urteilt,
    er verbietet nicht.

    Mit ``description`` im Body wird zusätzlich die (bis 26a brachliegende)
    Vagheits-Prüfung auf den selbst getippten Text angewandt.
    """
    topic_describe_limiter.check(request)
    from council import topic_intel

    name = body.name.strip()
    own = (body.description or "").strip()
    result = topic_intel.analyse(council, name)
    # Vagheit nur für selbst geschriebene Texte: Was wir selbst erzeugt haben,
    # ist per Konstruktion aus Beschlüssen abgeleitet und damit konkret.
    check = topic_intel.check_vagueness(name, own) if own else {"vague": False, "hint": "", "suggestion": ""}
    return {
        "name": name,
        "description": result["description"],
        "matches": result["matches"],
        "examples": result["examples"],
        "is_council_topic": result["is_council_topic"],
        "reason": result["reason"],
        **check,
    }


@router.post("", response_model=TopicOut, status_code=status.HTTP_201_CREATED)
def add_topic(body: TopicIn, user: dict = Depends(require_active), store: Store = Depends(get_store)) -> TopicOut:
    t = store.add_topic(user["id"], body.name, body.description)
    return TopicOut(id=t.id, name=t.name, description=t.description, created_at=t.created_at, decision_count=0)


@router.delete("/{topic_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_topic(topic_id: int, user: dict = Depends(require_active), store: Store = Depends(get_store)) -> None:
    _own_topic(store, user["id"], topic_id)
    store.delete_topic(topic_id)


@router.put("/{topic_id}", response_model=TopicOut)
def update_topic(
    topic_id: int,
    body: TopicIn,
    user: dict = Depends(require_active),
    store: Store = Depends(get_store),
) -> TopicOut:
    owner_id = user["id"]
    _own_topic(store, owner_id, topic_id)
    store.update_topic(topic_id, body.name, body.description)
    t = store.get_topic_for_owner(owner_id, topic_id)
    return TopicOut(
        id=t.id,
        name=t.name,
        description=t.description,
        created_at=t.created_at,
        decision_count=len(store.get_topic_decision_matches(topic_id)),
    )


@router.get("/unread-count")
def unread_count(user: dict = Depends(require_active), store: Store = Depends(get_store)) -> dict:
    """RL-903: Gesamtzahl ungesehener Themen-Treffer — der Orange-Zähler an
    „Meine Themen" in der Seitenleiste."""
    return {"total": sum(store.unseen_hit_counts(user["id"]).values())}


@router.post("/{topic_id}/seen")
def mark_seen(topic_id: int, user: dict = Depends(require_active), store: Store = Depends(get_store)) -> dict:
    """RL-903: alle aktuellen Treffer eines Themas als gesehen markieren —
    das Frontend ruft das beim Öffnen der Beschlussliste des Themas."""
    _own_topic(store, user["id"], topic_id)
    return {"marked": store.mark_topic_hits_seen(user["id"], topic_id)}


@router.get("/latest-hits")
def latest_hits(
    limit: int = Query(2, ge=1, le=10),
    user: dict = Depends(require_active),
    store: Store = Depends(get_store),
    council: CouncilStore = Depends(get_council_store),
) -> dict:
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
) -> dict:
    """Council decisions matched to this topic (semantic), best first."""
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
def list_subscriptions(user: dict = Depends(require_active), store: Store = Depends(get_store)) -> dict:
    return {"subscriptions": store.get_subscriptions(user["id"])}


@sub_router.post("", status_code=status.HTTP_201_CREATED)
def subscribe(body: SubscriptionIn, user: dict = Depends(require_active), store: Store = Depends(get_store)) -> dict:
    ok = store.subscribe(user["id"], body.committee_name)
    return {"subscribed": ok, "committee_name": body.committee_name}


@sub_router.delete("")
def unsubscribe(body: SubscriptionIn, user: dict = Depends(require_active), store: Store = Depends(get_store)) -> dict:
    ok = store.unsubscribe(user["id"], body.committee_name)
    return {"unsubscribed": ok, "committee_name": body.committee_name}
