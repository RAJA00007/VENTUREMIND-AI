"""
Base Agent

Every agent in the system inherits from this. It is the single place
where cross-cutting concerns live, so individual agents only ever
implement their domain logic in `run()`:

1. LOGGING: start/end + duration, so slow agents are visible in logs.
2. ERROR ISOLATION: if `run()` raises, `execute()` catches it and
   returns a valid `AgentScoreResult` with status="failed" instead of
   propagating the exception. This is critical for a multi-agent
   pipeline run in parallel (e.g. asyncio.gather / LangGraph) — one
   agent's crash (LLM timeout, search API down, bad JSON) must never
   take down the entire evaluation.
3. RETRY: transient failures (network blips, rate limits) are retried
   with exponential backoff before giving up.
4. OUTPUT CONTRACT: `run()` is expected to return an AgentScoreResult
   (see schemas/scoring.py). This replaces the old pattern where every
   agent returned a differently-shaped dict, which forced the Committee
   Agent to index into a list positionally (input_data[0], [1], [2]...)
   — a single reordering would silently break everything.
"""

import time
from abc import ABC, abstractmethod
from typing import Any

from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from core.constants import MAX_RETRIES
from core.logging import app_logger
from schemas.scoring import AgentScoreResult, make_failed_result


class AgentExecutionError(Exception):
    """Raised internally when an agent's run() fails after all retries.

    Caught by execute() — should never escape to the caller.
    """
    pass


class BaseAgent(ABC):

    def __init__(self, name: str, role: str):
        self.name = name
        self.role = role

    async def execute(self, input_data: Any) -> AgentScoreResult:
        """
        Public entry point. Always returns a valid AgentScoreResult,
        even on failure — callers (orchestrator, committee) never need
        to try/except this.
        """
        start = time.monotonic()
        app_logger.info(f"[{self.name}] started")

        try:
            result = await self._run_with_retry(input_data)
            duration = time.monotonic() - start
            app_logger.info(
                f"[{self.name}] finished in {duration:.2f}s "
                f"(score={result.score}, confidence={result.confidence}, status={result.status})"
            )
            return result

        except Exception as exc:
            duration = time.monotonic() - start
            app_logger.error(
                f"[{self.name}] failed after {duration:.2f}s: {exc}"
            )
            # Error isolation: return a degraded-but-valid result rather
            # than letting the exception propagate and kill the whole
            # pipeline (e.g. asyncio.gather would cancel sibling agents).
            return make_failed_result(self.name, str(exc))

    @retry(
        stop=stop_after_attempt(MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((TimeoutError, ConnectionError)),
        reraise=True,
    )
    async def _run_with_retry(self, input_data: Any) -> AgentScoreResult:
        """
        Only retries on transient errors (timeouts, connection issues).
        Programming errors (KeyError, ValidationError, etc.) fail fast
        instead of wasting MAX_RETRIES attempts on something that will
        never succeed.
        """
        result = await self.run(input_data)

        if not isinstance(result, AgentScoreResult):
            raise TypeError(
                f"{self.name}.run() must return an AgentScoreResult, "
                f"got {type(result).__name__}. Fix the agent implementation."
            )

        return result

    @abstractmethod
    async def run(self, input_data: Any) -> AgentScoreResult:
        """
        Implement domain logic here. Must return AgentScoreResult.

        Use `schemas.scoring.make_no_data_result()` if the agent ran
        successfully but found nothing to score (e.g. empty search
        results for an obscure company) — this is different from a
        failure and should be treated differently downstream.
        """
        pass
