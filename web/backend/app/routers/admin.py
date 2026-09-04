"""Admin: manage web users, moderation and the Telegram whitelist.

Die LLM-Prompts stehen NICHT mehr hier: Sie leben seit 08/2026 nur noch als
Code in `kern/prompts.py`, versioniert und im Pull Request les- und
diskutierbar. Ein Prompt aus der Hüfte zu ändern war zu leicht und die
Wirkung zu schwer abzuschätzen (Tims Entscheidung, 31.08.2026).
"""
from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status

from council.store import CouncilStore
from kern.digest_email import knopf, render_html_email
from kern.email import send_email
from kern import roles as rollen
from kern.store import Store

from ..config import get_settings
from ..antworten import (AdminAliasDeleted, AdminAliasList, AdminFeedbackList, AdminFeedbackRead,
                         AdminGrowth, AdminJob, AdminLimits, AdminLlmUsage, AdminPlaceCandidate,
                         AdminPlaceCandidates, AdminQuizStats, AdminUnread, AdminUserDetail,
                         AdminUserRow, Ok)
from ..deps import get_council_store, get_store, require_admin
from ..schemas import (EntityAliasIn, EntityAliasOut, LimitsUpdate, PlaceReviewIn,
                       RoleInfo, RolesUpdate, RoleUpdate, StatusUpdate, WebUserOut)

logger = logging.getLogger("ratslotse.web.admin")

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _send_activation_email(email: str) -> None:
    """Best-effort: tell a user their account was approved (status pending → active)."""
    settings = get_settings()
    if not settings.resend_api_key or not email:
        return
    login = f"{settings.app_base_url.rstrip('/')}/login"
    body = render_html_email(
        "Konto freigeschaltet",
        "<p style='margin:0'>Gute Nachrichten: Dein Konto wurde freigeschaltet — "
        "du kannst dich jetzt anmelden und loslegen.</p>"
        + knopf(login, "Jetzt anmelden"),
        held="freigeschaltet",
        kicker="Dein Konto",
        title="Du bist freigeschaltet!",
        fusszeile="Fragen oder Feedback? Antworte einfach auf diese E-Mail.",
    )
    text = (
        "Dein Ratslotse-Konto wurde freigeschaltet.\n\n"
        f"Jetzt anmelden: {login}\n\n"
        "Fragen oder Feedback? Antworte einfach auf diese E-Mail.\n"
    )
    try:
        send_email(
            email, "Ratslotse – dein Konto ist freigeschaltet", body, text=text,
            reply_to=settings.feedback_email or settings.web_admin_email or None,
            api_key=settings.resend_api_key, sender=settings.email_from,
        )
    except Exception:  # noqa: BLE001 — approval must not fail on a mail hiccup
        logger.exception("activation email failed for %s", email)


# ---- stats ----
_RANGE_DAYS = {"30d": 30, "90d": 90, "12m": 365, "all": None}


@router.get("/stats/growth")
def stats_growth(
    range: str = "90d",
    _admin: dict = Depends(require_admin),
    store: Store = Depends(get_store),
    council: CouncilStore = Depends(get_council_store),
) -> AdminGrowth:
    """Wachstums-Verläufe + WAU + Ratsinfo-Import für den Statistik-Tab (20a)."""
    days = _RANGE_DAYS.get(range, 90)
    data = store.admin_growth(days)
    data["council"] = council.admin_stats()
    return data


@router.get("/quiz/stats")
def quiz_stats(
    _admin: dict = Depends(require_admin),
    store: Store = Depends(get_store),
    council: CouncilStore = Depends(get_council_store),
) -> AdminQuizStats:
    """Quiz-Kennzahlen für den Admin-Tab (Design 21a): aktive Fragen, ⌀
    Trefferquote, Meldungen + Gebiete mit wenigen offenen Fragen („bald leer“,
    aufsteigend — Generierung anstoßen)."""
    total = council.quiz_stats_total()
    k = store.quiz_admin_kennzahlen()
    low = council.quiz_counts_below(5)  # < 5 aktive Fragen = bald leer
    gebiete = sorted(
        ({"area_type": at, "area_key": ak, "n": n} for (at, ak), n in low.items()),
        key=lambda g: g["n"],
    )
    return {
        "questions_active": total["fragen"],
        "avg_accuracy": k["avg_accuracy"],
        "reported": k["gemeldet"],
        "weak_categories": gebiete,
    }


@router.get("/jobs")
def jobs(_admin: dict = Depends(require_admin), store: Store = Depends(get_store)) -> list[AdminJob]:
    """Cron-Übersicht: je Job der letzte Lauf (Status, Dauer, Kennzahlen) plus
    kurze Historie. Der Zustand vergleicht das Alter des letzten Laufs mit dem
    erwarteten Takt aus der Registry (kern/jobs.py) — so fällt ein stiller
    Ausfall auf, auch wenn keine Fehler-Mail kam (Job lief ja gar nicht)."""
    from datetime import datetime

    from kern.jobs import JOBS

    runs = store.job_runs(limit=500)
    by_job: dict[str, list[dict]] = {}
    for r in runs:
        by_job.setdefault(r["job"], []).append(r)

    now = datetime.utcnow()
    out = []
    for job in JOBS:
        history = by_job.get(job["key"], [])  # neueste zuerst
        last = history[0] if history else None
        state = "unknown"
        age_h = None
        if last:
            try:
                age_h = round((now - datetime.fromisoformat(last["started_at"])).total_seconds() / 3600, 1)
            except (ValueError, TypeError):
                age_h = None
            if last["status"] == "error":
                state = "error"
            elif age_h is not None and age_h > job["max_age_h"]:
                state = "stale"
            else:
                state = "ok"
        out.append({
            **{k: job[k] for k in ("key", "label", "description", "schedule")},
            "state": state,
            "age_h": age_h,
            "last": last,
            # Älteste zuerst, damit der Verlauf links→rechts in der Zeit läuft.
            "history": [
                {"started_at": h["started_at"], "status": h["status"], "duration_s": h["duration_s"]}
                for h in reversed(history[:12])
            ],
        })
    return out


@router.get("/llm-usage")
def llm_usage(_admin: dict = Depends(require_admin)) -> AdminLlmUsage:
    """LLM-Kosten-Dashboard (Design 21a): per-Feature-Aggregat + 30-Tage-Verlauf,
    Monatskosten mit Hochrechnung und Budget-Ampel (aus llm_usage in ratslotse.sqlite)."""
    from kern import usage
    return usage.dashboard(budget_monthly=get_settings().llm_budget_monthly)


# ---- Feedback ----
@router.get("/feedback")
def list_feedback(
    only_unread: bool = False,
    limit: int = Query(100, ge=1, le=500),
    _admin: dict = Depends(require_admin),
    store: Store = Depends(get_store),
) -> AdminFeedbackList:
    """Eingegangenes Nutzer-Feedback, neueste zuerst — plus die Zahl der
    offenen Einträge für das Zeichen in der Navigation."""
    return {
        "items": store.list_feedback(limit=limit, only_unread=only_unread),
        "unread": store.count_unread_feedback(),
    }


@router.get("/feedback/unread-count")
def feedback_unread_count(
    _admin: dict = Depends(require_admin),
    store: Store = Depends(get_store),
) -> AdminUnread:
    """Schlanker Endpunkt allein für das Zeichen in der Navigation — die
    Sidebar liegt auf jeder Seite an und soll dafür nicht die ganze Liste holen."""
    return {"total": store.count_unread_feedback()}


@router.post("/feedback/{feedback_id}/read")
def mark_feedback_read(
    feedback_id: int,
    read: bool = True,
    _admin: dict = Depends(require_admin),
    store: Store = Depends(get_store),
) -> AdminFeedbackRead:
    """Als erledigt markieren — `?read=false` macht es wieder rückgängig."""
    if not store.set_feedback_read(feedback_id, read):
        raise HTTPException(status_code=404, detail="Feedback nicht gefunden.")
    return {"ok": True, "unread": store.count_unread_feedback()}


@router.delete("/qa-shares/{token}", status_code=status.HTTP_204_NO_CONTENT)
def delete_reported_qa_share(
    token: str,
    _admin: dict = Depends(require_admin),
    store: Store = Depends(get_store),
) -> None:
    """Gemeldeten Share entfernen; das öffentliche GET liefert danach 404."""
    if len(token) > 64 or not store.qa_share_delete(token):
        raise HTTPException(status_code=404, detail="Geteilte Antwort nicht gefunden.")


# ---- web users ----
@router.get("/users")
def list_users(_admin: dict = Depends(require_admin), store: Store = Depends(get_store)) -> list[AdminUserRow]:
    """Nutzer-Liste mit Aktivitätssignalen (Design 20a): Themen-/Abo-/Quiz-/
    KI-Frage-Zahl + letzter Aktivitätstag je Konto."""
    return store.admin_user_rows()


@router.get("/users/{user_id}")
def user_detail(user_id: int, _admin: dict = Depends(require_admin), store: Store = Depends(get_store)) -> AdminUserDetail:
    """Nutzer-Detail (Design 20a): Feature-Nutzung, Angelegtes, 30-Tage-Verlauf."""
    detail = store.admin_user_detail(user_id)
    if not detail:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Nutzer*in nicht gefunden.")
    return detail


@router.get("/roles")
def list_roles(_admin: dict = Depends(require_admin)) -> list[RoleInfo]:
    """Der Rollen-Katalog: welche Rollen es gibt und was sie dürfen.

    Beide Frontends bauen ihre Auswahl daraus, statt Rollennamen und
    Beschriftungen abzuschreiben — eine neue Rolle in ``kern/roles.py``
    erscheint damit im Admin-Panel, ohne dass jemand das Frontend anfasst.
    """
    return [RoleInfo(**r) for r in rollen.catalog()]


def _rollen_setzen(store: Store, admin: dict, user_id: int, gewuenscht: list[str]) -> WebUserOut:
    """Gemeinsamer Kern beider Schreibwege (eine Rolle / die ganze Liste).

    Die beiden Sperren dahinter sind der Grund, warum es die Funktion gibt:
    Sie dürfen nicht an einem der beiden Wege hängen, sonst führt der andere
    daran vorbei.
    """
    unbekannt = [r for r in gewuenscht if r not in rollen.ROLES]
    if unbekannt:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Unbekannte Rolle(n): {', '.join(sorted(set(unbekannt)))}. "
            f"Bekannt: {', '.join(rollen.ROLE_ORDER)}.")
    target = store.get_web_user_by_id(user_id)
    if not target:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Nutzer*in nicht gefunden.")
    # Sich selbst auszusperren ist der eine Fehler, den kein Undo mehr
    # aufhebt: Danach kommt niemand mehr ins Panel, und die Reparatur ist ein
    # SSH-Zugang plus `scripts/grant_admin.py`.
    if target["id"] == admin["id"] and "admin" not in gewuenscht:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            "Du kannst dir nicht selbst die Adminrechte entziehen.")
    store.set_web_user_roles(user_id, gewuenscht, granted_by=admin["id"])
    return WebUserOut(**store.get_web_user_by_id(user_id))


@router.put("/users/{user_id}/role", response_model=WebUserOut)
def set_role(
    user_id: int,
    body: RoleUpdate,
    admin: dict = Depends(require_admin),
    store: Store = Depends(get_store),
) -> WebUserOut:
    """Alt-Weg: EINE Rolle setzen — sie ersetzt alle anderen.

    Bleibt bestehen, weil die im App Store ausgelieferte iOS-App genau diesen
    Aufruf schickt (`AdminView.swift`). Ihn zu entfernen hieße dort ein
    Knopf, der wortlos nichts tut. Neue Clients nehmen ``PUT …/roles``.
    """
    return _rollen_setzen(store, admin, user_id,
                          [] if body.role == rollen.DEFAULT_ROLE else [body.role])


@router.put("/users/{user_id}/roles", response_model=WebUserOut)
def set_roles(
    user_id: int,
    body: RolesUpdate,
    admin: dict = Depends(require_admin),
    store: Store = Depends(get_store),
) -> WebUserOut:
    """Die Rollen eines Kontos setzen — die vollständige Liste.

    ``[]`` heißt „nur noch die Standardrolle": Sie hat jedes Konto ohnehin und
    steht deshalb nie in der Liste (siehe ``kern/roles.py``).
    """
    return _rollen_setzen(store, admin, user_id,
                          [r for r in body.roles if r != rollen.DEFAULT_ROLE])


@router.put("/users/{user_id}/status", response_model=WebUserOut)
def set_status(
    user_id: int,
    body: StatusUpdate,
    background: BackgroundTasks,
    admin: dict = Depends(require_admin),
    store: Store = Depends(get_store),
) -> WebUserOut:
    """Approve ('active') or suspend ('pending') a web account. Emails the user on first approval."""
    if body.status not in ("active", "pending"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Status muss 'active' oder 'pending' sein.")
    target = store.get_web_user_by_id(user_id)
    if not target:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Nutzer*in nicht gefunden.")
    if target["id"] == admin["id"] and body.status != "active":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Du kannst dich nicht selbst sperren.")
    store.set_web_user_status(user_id, body.status)
    # Notify the user only on the pending → active transition (not on re-saves/no-ops).
    if body.status == "active" and target.get("status") != "active":
        background.add_task(_send_activation_email, target.get("email", ""))
    return WebUserOut(**store.get_web_user_by_id(user_id))


@router.put("/users/{user_id}/limits")
def set_limits(
    user_id: int,
    body: LimitsUpdate,
    _admin: dict = Depends(require_admin),
    store: Store = Depends(get_store),
) -> AdminLimits:
    """Frage-Limits je Konto (Tims Wunsch 10.08.): Recherche-Tageskontingent
    (None = Standard, 0 = unbegrenzt, N = eigenes Limit) und Befreiung von den
    Rate-Limitern der Frage-Endpoints — z. B. für Power-Nutzer oder Tests."""
    if not store.get_web_user_by_id(user_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Nutzer*in nicht gefunden.")
    store.set_web_user_limits(user_id, body.deep_limit, body.limits_unlocked)
    u = store.get_web_user_by_id(user_id)
    return {"deep_limit": u.get("deep_limit"), "limits_unlocked": bool(u.get("limits_unlocked"))}


# ---- Themen-Dubletten (council.aliases) ----
@router.get("/entity-aliases")
def list_entity_aliases(
    _admin: dict = Depends(require_admin),
    store: CouncilStore = Depends(get_council_store),
) -> AdminAliasList:
    """Zusammengeführte Themen mit Quelle und Begründung, für die Durchsicht."""
    return {"aliases": store.list_entity_aliases()}


@router.post("/entity-aliases", response_model=EntityAliasOut)
def set_entity_alias(
    body: EntityAliasIn,
    _admin: dict = Depends(require_admin),
    store: CouncilStore = Depends(get_council_store),
) -> EntityAliasOut:
    """Zwei Themen von Hand zusammenführen.

    Von Hand gesetzte Zuordnungen überschreibt der automatische Lauf nicht mehr.
    Die Themen werden sofort neu abgeleitet, damit die Wirkung sichtbar ist.
    """
    if body.slug == body.canonical_slug:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            "Ein Thema kann nicht auf sich selbst zeigen.")
    known = store.known_entity_slugs()
    for slug in (body.slug, body.canonical_slug):
        if slug not in known:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unbekanntes Thema: {slug}")
    # Erst schreiben, dann auf Zyklen prüfen — resolve_chains verwirft sie, was
    # hier ein stiller Datenverlust wäre.
    store.delete_entity_alias(body.slug)
    store.save_entity_aliases([(body.slug, body.canonical_slug, "manuell",
                                (body.reason or "").strip()[:200],
                                datetime.now().isoformat(timespec="seconds"))])
    if body.slug not in store.entity_aliases():
        store.delete_entity_alias(body.slug)
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            "Das ergäbe einen Ringschluss zwischen Themen.")
    store.rebuild_entities_from_obs()
    row = next((r for r in store.list_entity_aliases() if r["slug"] == body.slug), None)
    if not row:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Zuordnung nicht gespeichert.")
    return EntityAliasOut(**row)


@router.delete("/entity-aliases/{slug}")
def delete_entity_alias(
    slug: str,
    _admin: dict = Depends(require_admin),
    store: CouncilStore = Depends(get_council_store),
) -> AdminAliasDeleted:
    """Eine Zusammenführung aufheben — das Thema erscheint wieder eigenständig.

    Möglich, weil die Roh-Beobachtungen unangetastet bleiben und die Themen
    daraus neu abgeleitet werden.
    """
    if not store.delete_entity_alias(slug):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Zuordnung nicht gefunden.")
    n_entities, _ = store.rebuild_entities_from_obs()
    return {"ok": True, "entities": n_entities}


# ---- Ortskandidaten ---------------------------------------------------------

@router.get("/place-candidates")
def place_candidates(
    review_status: str = Query("pending", alias="status",
                               pattern="^(pending|concrete|approved|alias|rejected|all)$"),
    limit: int = Query(200, ge=1, le=500),
    min_decisions: int = Query(3, ge=1, le=100),
    _admin: dict = Depends(require_admin),
    store: CouncilStore = Depends(get_council_store),
) -> AdminPlaceCandidates:
    """Automatisch gefundene, noch nicht statisch katalogisierte Orte prüfen."""
    items = store.location_candidates(
        review_status, limit=limit, min_decisions=min_decisions)
    return {"candidates": items, "status": review_status}


@router.put("/place-candidates/{location_slug}")
def review_place_candidate(
    location_slug: str,
    body: PlaceReviewIn,
    admin: dict = Depends(require_admin),
    store: CouncilStore = Depends(get_council_store),
) -> AdminPlaceCandidate:
    try:
        return store.review_location_candidate(
            location_slug, status=body.status, place_id=body.place_id,
            name=body.name, kind=body.kind, parent_id=body.parent_id,
            aliases=body.aliases, description=body.description,
            source_url=body.source_url, quiz_enabled=body.quiz_enabled,
            canonical_place_id=body.canonical_place_id, note=body.note,
            updated_by=admin.get("email"),
        )
    except KeyError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND,
                            "Ortskandidat nicht gefunden.") from exc
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


@router.delete("/place-candidates/{location_slug}")
def reopen_place_candidate(
    location_slug: str,
    _admin: dict = Depends(require_admin),
    store: CouncilStore = Depends(get_council_store),
) -> Ok:
    if not store.delete_location_review(location_slug):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Prüfung nicht gefunden.")
    return {"ok": True}
