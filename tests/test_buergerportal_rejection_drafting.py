"""Human-controlled rejection drafting at the minimized provider boundary."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from types import SimpleNamespace
import sqlite3

import pytest


def _setup_report(tmp_path, text: str, *, blocked: bool = False):
    from buergerportal.reports import DraftContent, PrivateReportStore
    from kern.store import Store

    database = tmp_path / "ratslotse.sqlite"
    accounts = Store(database)
    owner_id = accounts.create_web_user(
        "meldeperson@example.org",
        "x",
        role="user",
        status="active",
        email_verified=True,
    )
    reviewer_id = accounts.create_web_user(
        "moderation@example.org",
        "x",
        role="moderator",
        status="active",
        email_verified=True,
    )
    accounts.close()
    store = PrivateReportStore(database)
    report_id = store.create_draft(
        reporter_id=owner_id,
        content=DraftContent(
            text="Fiktiver Entwurf",
            category="public_space",
            scope_kind="point",
            observed_on="2026-09-01",
            location_label="Vertraulicher Fantasieort",
            latitude=53.143,
            longitude=8.214,
        ),
    )
    submitted = store.submit_owned_draft(
        report_id,
        reporter_id=owner_id,
        confirmed_text=text,
        expected_revision=0,
    )
    screening = store.get_current_owned_screening(report_id, reporter_id=owner_id)
    assert screening is not None
    assert (screening.outcome == "manual_review_only") is blocked
    return database, store, submitted, reviewer_id


class RecordingEvaluator:
    def __init__(self):
        self.inputs = []

    def evaluate(self, drafting_input):
        from buergerportal.rejection_drafting import RejectionDraftEvaluatorResult

        self.inputs.append(drafting_input)
        return RejectionDraftEvaluatorResult(
            suggestion="Fiktiver bearbeitbarer Ablehnungsentwurf.",
            model_identifier="fiktives-modell-v1",
        )


def test_locally_blocked_drafting_sends_only_controlled_vocabulary(tmp_path):
    from buergerportal.rejection_drafting import draft_rejection_explanation

    private_text = (
        "Notruf 112 am vertraulichen Fantasieort; Kontakt: privat@example.org"
    )
    _, store, submitted, reviewer_id = _setup_report(
        tmp_path,
        private_text,
        blocked=True,
    )
    evaluator = RecordingEvaluator()

    first = draft_rejection_explanation(
        store,
        report_id=submitted.id,
        expected_revision=submitted.content_revision,
        reviewer_id=reviewer_id,
        evaluator=evaluator,
    )
    retry = draft_rejection_explanation(
        store,
        report_id=submitted.id,
        expected_revision=submitted.content_revision,
        reviewer_id=reviewer_id,
        evaluator=evaluator,
    )

    assert first is not None and retry == first
    assert len(evaluator.inputs) == 1
    drafting_input = evaluator.inputs[0]
    assert drafting_input.observation_texts == ()
    assert drafting_input.local_reason_codes == (
        "potential_emergency",
        "direct_contact_data",
    )
    assert drafting_input.category == "public_space"
    assert drafting_input.scope_kind == "point"
    assert drafting_input.ai_verdict is None
    assert drafting_input.ai_reason_code is None
    assert private_text not in repr(drafting_input)
    assert store._conn.execute(
        """SELECT reviewer_id FROM civic_report_rejection_draft_claims
           WHERE report_id = ? AND content_revision = ?""",
        (submitted.id, submitted.content_revision),
    ).fetchone()["reviewer_id"] is None
    with pytest.raises(sqlite3.IntegrityError, match="completed rejection draft claims are immutable"):
        store._conn.execute(
            """UPDATE civic_report_rejection_draft_claims
               SET reviewer_id = ? WHERE report_id = ? AND content_revision = ?""",
            (reviewer_id, submitted.id, submitted.content_revision),
        )
    store._conn.rollback()
    store.close()


def test_locally_cleared_drafting_uses_only_the_minimized_report_projection(tmp_path):
    from buergerportal.rejection_drafting import draft_rejection_explanation

    private_text = "Fiktive kommunale Beobachtung ohne Kontaktdaten."
    _, store, submitted, reviewer_id = _setup_report(tmp_path, private_text)
    candidate = store.claim_external_ai_screening(
        submitted.id,
        expected_revision=submitted.content_revision,
        assessment_version=1,
        claim_token="fiktiver-entwurfs-ki-claim",
    )
    assert candidate is not None
    assert store.start_claimed_external_ai_screening(candidate) is not None
    store.complete_external_ai_screening(
        candidate,
        verdict="suitable",
        reason_code="municipal_problem",
        model_identifier="fiktives-screening-modell",
    )
    evaluator = RecordingEvaluator()

    suggestion = draft_rejection_explanation(
        store,
        report_id=submitted.id,
        expected_revision=submitted.content_revision,
        reviewer_id=reviewer_id,
        evaluator=evaluator,
    )

    assert suggestion is not None
    assert evaluator.inputs[0].observation_texts == (private_text,)
    assert evaluator.inputs[0].local_reason_codes == ()
    assert evaluator.inputs[0].ai_verdict == "suitable"
    assert evaluator.inputs[0].ai_reason_code == "municipal_problem"
    assert {
        "report_id",
        "reviewer_id",
        "location_label",
        "latitude",
        "longitude",
        "observed_on",
    }.isdisjoint(evaluator.inputs[0].__dataclass_fields__)
    store.close()


def test_drafting_failure_is_retryable_and_logs_no_private_material(tmp_path, caplog):
    from buergerportal.rejection_drafting import draft_rejection_explanation

    private_text = "Fiktiver privater Text darf nicht ins Fehlerprotokoll 91aa."
    database, store, submitted, reviewer_id = _setup_report(tmp_path, private_text)

    class FailingEvaluator:
        def evaluate(self, _drafting_input):
            raise RuntimeError(f"provider echoed {private_text}")

    first = draft_rejection_explanation(
        store,
        report_id=submitted.id,
        expected_revision=submitted.content_revision,
        reviewer_id=reviewer_id,
        evaluator=FailingEvaluator(),
    )
    retry_evaluator = RecordingEvaluator()
    retry = draft_rejection_explanation(
        store,
        report_id=submitted.id,
        expected_revision=submitted.content_revision,
        reviewer_id=reviewer_id,
        evaluator=retry_evaluator,
    )

    assert first is None
    assert retry is not None
    assert len(retry_evaluator.inputs) == 1
    assert private_text not in caplog.text
    with store._conn:
        assert store._conn.execute(
            "SELECT COUNT(*) FROM civic_report_rejection_draft_claims"
        ).fetchone()[0] == 1
        assert store._conn.execute(
            "SELECT COUNT(*) FROM civic_report_rejection_drafts"
        ).fetchone()[0] == 1
    store.close()


def test_concurrent_drafting_performs_at_most_one_provider_call(tmp_path):
    from buergerportal.rejection_drafting import draft_rejection_explanation
    from buergerportal.reports import PrivateReportStore

    database, setup_store, submitted, reviewer_id = _setup_report(
        tmp_path,
        "Fiktive Beobachtung für einen konkurrierenden Entwurf.",
    )
    setup_store.close()
    evaluator = RecordingEvaluator()
    lock = Lock()

    class LockedEvaluator:
        def evaluate(self, drafting_input):
            with lock:
                return evaluator.evaluate(drafting_input)

    def request_draft(_index: int):
        store = PrivateReportStore(database)
        try:
            return draft_rejection_explanation(
                store,
                report_id=submitted.id,
                expected_revision=submitted.content_revision,
                reviewer_id=reviewer_id,
                evaluator=LockedEvaluator(),
            )
        finally:
            store.close()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(request_draft, (1, 2)))

    assert len(evaluator.inputs) == 1
    assert any(result is not None for result in results)
    store = PrivateReportStore(database)
    assert store.get_current_rejection_draft(
        submitted.id,
        reviewer_id=reviewer_id,
    ) is not None
    store.close()


def test_drafting_revalidates_reviewer_before_provider_dispatch(tmp_path):
    from buergerportal.reports import REJECTION_DRAFT_VERSION, ReviewerNotEligible
    from kern.store import Store

    database, store, submitted, reviewer_id = _setup_report(
        tmp_path,
        "Fiktive Beobachtung vor entzogenem Moderationsrecht.",
    )
    candidate = store.claim_rejection_draft(
        submitted.id,
        expected_revision=submitted.content_revision,
        reviewer_id=reviewer_id,
        drafting_version=REJECTION_DRAFT_VERSION,
        claim_token="fiktiver-reviewer-claim",
    )
    assert candidate is not None

    accounts = Store(database)
    other_reviewer_id = accounts.create_web_user(
        "zweite-moderation@example.org",
        "x",
        role="moderator",
        status="active",
        email_verified=True,
    )
    assert store.start_claimed_rejection_draft(
        candidate,
        reviewer_id=other_reviewer_id,
    ) is None
    accounts.set_web_user_role(reviewer_id, "user")
    accounts.close()

    with pytest.raises(ReviewerNotEligible):
        store.start_claimed_rejection_draft(candidate, reviewer_id=reviewer_id)
    store.close()


def test_database_rejects_a_draft_claim_from_an_ineligible_actor(tmp_path):
    from buergerportal.reports import REJECTION_DRAFT_VERSION
    from kern.store import Store

    database, store, submitted, _ = _setup_report(
        tmp_path,
        "Fiktive Beobachtung für den Datenbanktest.",
    )
    accounts = Store(database)
    owner_id = int(accounts.get_web_user_by_email("meldeperson@example.org")["id"])
    accounts.close()
    screening_id = int(
        store._conn.execute(
            """SELECT id FROM civic_report_local_screenings
               WHERE report_id = ? AND content_revision = ?""",
            (submitted.id, submitted.content_revision),
        ).fetchone()["id"]
    )

    with sqlite3.connect(database) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        with pytest.raises(sqlite3.IntegrityError, match="pending report and reviewer"):
            connection.execute(
                """INSERT INTO civic_report_rejection_draft_claims (
                       report_id, content_revision, local_screening_id,
                       reviewer_id, drafting_version, claim_token, lease_until
                   ) VALUES (?, ?, ?, ?, ?, 'fiktiver-direkter-claim',
                             '2099-09-05T08:00:00+00:00')""",
                (
                    submitted.id,
                    submitted.content_revision,
                    screening_id,
                    owner_id,
                    REJECTION_DRAFT_VERSION,
                ),
            )
    store.close()


def test_stale_revision_cannot_persist_a_drafting_suggestion(tmp_path):
    from buergerportal.rejection_drafting import (
        RejectionDraftEvaluatorResult,
        draft_rejection_explanation,
    )
    from buergerportal.reports import PrivateReportStore
    from kern.store import Store

    database, store, submitted, reviewer_id = _setup_report(
        tmp_path,
        "Fiktive erste Beobachtung vor einer Ergänzung.",
    )
    accounts = Store(database)
    owner_id = int(accounts.get_web_user_by_email("meldeperson@example.org")["id"])
    accounts.close()

    class RevisionChangingEvaluator:
        def evaluate(self, _drafting_input):
            concurrent = PrivateReportStore(database)
            updated = concurrent.append_owned_observation(
                submitted.id,
                reporter_id=owner_id,
                text="Fiktive neuere Beobachtung.",
                observed_on="2026-09-02",
            )
            concurrent.assess_owned_submission(
                submitted.id,
                reporter_id=owner_id,
                expected_revision=updated.content_revision,
            )
            concurrent.close()
            return RejectionDraftEvaluatorResult(
                suggestion="Dieser veraltete Entwurf darf nicht gespeichert werden.",
                model_identifier="fiktives-modell-v1",
            )

    result = draft_rejection_explanation(
        store,
        report_id=submitted.id,
        expected_revision=submitted.content_revision,
        reviewer_id=reviewer_id,
        evaluator=RevisionChangingEvaluator(),
    )

    assert result is None
    assert store.get_current_rejection_draft(
        submitted.id,
        reviewer_id=reviewer_id,
    ) is None
    assert store.get_report_for_moderation(
        submitted.id,
        reviewer_id=reviewer_id,
    ).content_revision == 2
    with store._conn:
        assert store._conn.execute(
            "SELECT COUNT(*) FROM civic_report_rejection_drafts"
        ).fetchone()[0] == 0
    store.close()


def test_openrouter_rejection_drafter_rejects_malformed_output(monkeypatch):
    from buergerportal.rejection_drafting import (
        InvalidRejectionDraftResponse,
        OpenRouterRejectionDraftEvaluator,
        RejectionDraftInput,
    )
    from kern import llm

    monkeypatch.setattr(
        llm,
        "chat_complete",
        lambda **_kwargs: SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content='{"extra":true}'))]
        ),
    )
    evaluator = OpenRouterRejectionDraftEvaluator(model="fiktives/modell-v1")
    with pytest.raises(InvalidRejectionDraftResponse):
        evaluator.evaluate(
            RejectionDraftInput(
                observation_texts=(),
                category="other",
                scope_kind="citywide",
                local_reason_codes=("potential_emergency",),
                ai_verdict=None,
                ai_reason_code=None,
            )
        )


def test_openrouter_rejection_drafter_uses_strict_private_contract(monkeypatch):
    from buergerportal.rejection_drafting import (
        OpenRouterRejectionDraftEvaluator,
        RejectionDraftInput,
    )
    from kern import llm

    captured = {}

    def fake_chat_complete(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=(
                            '{"suggestion":"Fiktiver deutscher Ablehnungsentwurf."}'
                        )
                    )
                )
            ]
        )

    monkeypatch.setattr(llm, "chat_complete", fake_chat_complete)
    evaluator = OpenRouterRejectionDraftEvaluator(model="fiktives/modell-v1")
    result = evaluator.evaluate(
        RejectionDraftInput(
            observation_texts=(),
            category="public_space",
            scope_kind="point",
            local_reason_codes=("direct_contact_data",),
            ai_verdict=None,
            ai_reason_code=None,
        )
    )

    assert result.suggestion == "Fiktiver deutscher Ablehnungsentwurf."
    assert captured["messages"][0]["content"]
    assert "civic_report_rejection_draft_system" not in captured["messages"][0]["content"]
    assert captured["response_format"]["json_schema"]["strict"] is True
    assert captured["extra_body"] == llm.strict_privacy_routing_extra_body()
    assert captured["_feature"] == "civic_report_rejection_drafting"
    assert captured["temperature"] == 0
    assert captured["max_tokens"] <= 400
