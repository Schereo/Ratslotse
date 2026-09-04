"""Background scheduling boundary for private external AI pre-screening."""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from buergerportal.ai_screening import (
    ExternalAiEvaluator,
    OpenRouterCivicReportEvaluator,
    screen_report_with_external_ai,
)
from buergerportal.reports import PrivateReportStore

_LOGGER = logging.getLogger(__name__)


class BackgroundTaskQueue(Protocol):
    def add_task(
        self, function: Callable[..., object], *args: object, **kwargs: object
    ) -> None:
        """Queue work that starts after the response has been sent."""


class BackgroundExternalAiScreeningScheduler:
    """Schedule screening and give each background run its own DB connection."""

    def __init__(
        self,
        database: str | Path,
        *,
        evaluator_factory: Callable[
            [], ExternalAiEvaluator
        ] = OpenRouterCivicReportEvaluator,
    ):
        self._database = Path(database)
        self._evaluator_factory = evaluator_factory

    def schedule(
        self,
        background_tasks: BackgroundTaskQueue,
        *,
        report_id: int,
        expected_revision: int,
    ) -> None:
        background_tasks.add_task(
            self._run,
            report_id=report_id,
            expected_revision=expected_revision,
        )

    def _run(self, *, report_id: int, expected_revision: int) -> None:
        store: PrivateReportStore | None = None
        try:
            store = PrivateReportStore(self._database)
            screen_report_with_external_ai(
                store,
                report_id=report_id,
                expected_revision=expected_revision,
                evaluator=self._evaluator_factory(),
            )
        except Exception:  # noqa: BLE001 - private submission remains authoritative
            _LOGGER.warning("Background external AI pre-screening did not complete")
        finally:
            if store is not None:
                store.close()
