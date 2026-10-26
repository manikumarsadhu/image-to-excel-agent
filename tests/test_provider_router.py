"""Provider router: retries, Retry-After, and failover."""

from __future__ import annotations

import pytest

from config import AIProviderName, Settings
from models.document import (
    ExtractionFieldDefinition,
    ExtractionSchema,
    FieldReviewStatus,
    StructuredExtractionResult,
    ExtractedFieldValue,
)
from providers.base import (
    AIProvider,
    ProviderAuthError,
    ProviderInvalidRequestError,
    ProviderRateLimitError,
    ProviderTransientError,
    StructuringContext,
)
from providers.health import ProviderHealthTracker
from providers.router import ProviderRouter


class FlakyProvider(AIProvider):
    def __init__(
        self,
        name: str,
        outcomes: list[Exception | StructuredExtractionResult],
        *,
        provider_id: AIProviderName = AIProviderName.GEMINI,
    ) -> None:
        self.provider_id = provider_id
        self._name = name
        self._outcomes = outcomes
        self._index = 0

    @property
    def name(self) -> str:
        return self._name

    def structure(self, context: StructuringContext) -> StructuredExtractionResult:
        if self._index >= len(self._outcomes):
            raise ProviderTransientError("exhausted")
        outcome = self._outcomes[self._index]
        self._index += 1
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def _schema() -> ExtractionSchema:
    return ExtractionSchema(
        name="s",
        fields=[ExtractionFieldDefinition(key="a", label="A")],
    )


def _ok_result() -> StructuredExtractionResult:
    return StructuredExtractionResult(
        fields=[
            ExtractedFieldValue(
                key="a",
                label="A",
                value="1",
                review_status=FieldReviewStatus.CONFIRMED,
            )
        ]
    )


def _context() -> StructuringContext:
    return StructuringContext(ocr_text="hello", source_filename="x.png", schema=_schema())


def test_router_retries_transient_then_succeeds() -> None:
    sleeps: list[float] = []
    settings = Settings(_env_file=None, ai_max_attempts_per_provider=3)
    provider = FlakyProvider(
        "gemini/m",
        [ProviderTransientError("blip"), ProviderTransientError("blip"), _ok_result()],
    )
    router = ProviderRouter(settings, [provider], sleep_fn=sleeps.append)
    result = router.structure(_context())
    assert result.field_map()["a"].value == "1"
    assert router.last_used_provider == "gemini/m"
    assert len(sleeps) == 2


def test_router_honors_retry_after() -> None:
    sleeps: list[float] = []
    settings = Settings(_env_file=None, ai_max_attempts_per_provider=2)
    provider = FlakyProvider(
        "groq/m",
        [
            ProviderRateLimitError("limited", retry_after_seconds=7.5),
            _ok_result(),
        ],
    )
    router = ProviderRouter(settings, [provider], sleep_fn=sleeps.append)
    router.structure(_context())
    assert sleeps == [7.5]


def test_router_failover_after_exhausted_retries() -> None:
    settings = Settings(_env_file=None, ai_max_attempts_per_provider=2)
    first = FlakyProvider(
        "gemini/m",
        [ProviderTransientError("down"), ProviderTransientError("down")],
        provider_id=AIProviderName.GEMINI,
    )
    second = FlakyProvider(
        "groq/m",
        [_ok_result()],
        provider_id=AIProviderName.GROQ,
    )
    router = ProviderRouter(settings, [first, second], sleep_fn=lambda _: None)
    result = router.structure(_context())
    assert result.field_map()["a"].value == "1"
    assert router.last_used_provider == "groq/m"


def test_invalid_request_not_retried_or_failovered() -> None:
    settings = Settings(_env_file=None)
    first = FlakyProvider("gemini/m", [ProviderInvalidRequestError("bad input")])
    second = FlakyProvider("groq/m", [_ok_result()])
    router = ProviderRouter(settings, [first, second], sleep_fn=lambda _: None)
    with pytest.raises(ProviderInvalidRequestError):
        router.structure(_context())


def test_json_validation_error_failovers_to_next_provider() -> None:
    settings = Settings(_env_file=None)
    first = FlakyProvider(
        "gemini/m",
        [ProviderInvalidRequestError("Error code: 400 - json_validate_failed")],
    )
    second = FlakyProvider("groq/m", [_ok_result()])
    router = ProviderRouter(settings, [first, second], sleep_fn=lambda _: None)
    result = router.structure(_context())
    assert result.field_map()["a"].value == "1"
    assert router.last_used_provider == "groq/m"


def test_auth_error_failover_without_retrying_same_provider() -> None:
    settings = Settings(_env_file=None, ai_max_attempts_per_provider=3)
    calls = {"gemini": 0, "groq": 0}

    class CountingGemini(FlakyProvider):
        def structure(self, context: StructuringContext) -> StructuredExtractionResult:
            calls["gemini"] += 1
            raise ProviderAuthError("bad key")

    class CountingGroq(FlakyProvider):
        def structure(self, context: StructuringContext) -> StructuredExtractionResult:
            calls["groq"] += 1
            return _ok_result()

    router = ProviderRouter(
        settings,
        [
            CountingGemini("gemini/m", [], provider_id=AIProviderName.GEMINI),
            CountingGroq("groq/m", [], provider_id=AIProviderName.GROQ),
        ],
        sleep_fn=lambda _: None,
    )
    router.structure(_context())
    assert calls["gemini"] == 1
    assert calls["groq"] == 1


def test_health_cooldown_skips_provider() -> None:
    health = ProviderHealthTracker(default_cooldown_seconds=30.0)
    health.record_failure(AIProviderName.GEMINI, "rate limited", retry_after_seconds=3600)
    settings = Settings(_env_file=None)
    gemini = FlakyProvider(
        "gemini/m",
        [_ok_result()],
        provider_id=AIProviderName.GEMINI,
    )
    groq = FlakyProvider(
        "groq/m",
        [_ok_result()],
        provider_id=AIProviderName.GROQ,
    )
    router = ProviderRouter(settings, [gemini, groq], health=health, sleep_fn=lambda _: None)
    router.structure(_context())
    assert router.last_used_provider == "groq/m"
    assert gemini._index == 0
