"""In-memory provider health, errors, and rate-limit cooldowns."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from config import AIProviderName


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class ProviderHealthSnapshot:
    provider: AIProviderName
    available: bool
    consecutive_failures: int
    last_error: str | None
    last_success_at: datetime | None
    cooldown_until: datetime | None


@dataclass
class _ProviderHealthRecord:
    consecutive_failures: int = 0
    last_error: str | None = None
    last_error_at: datetime | None = None
    last_success_at: datetime | None = None
    cooldown_until: datetime | None = None


class ProviderHealthTracker:
    """Tracks recent outcomes; does not assume multiple keys increase quota."""

    def __init__(self, *, default_cooldown_seconds: float = 60.0) -> None:
        self._default_cooldown = default_cooldown_seconds
        self._records: dict[AIProviderName, _ProviderHealthRecord] = {}

    def _record(self, provider: AIProviderName) -> _ProviderHealthRecord:
        if provider not in self._records:
            self._records[provider] = _ProviderHealthRecord()
        return self._records[provider]

    def is_available(self, provider: AIProviderName, *, now: datetime | None = None) -> bool:
        moment = now or _utcnow()
        rec = self._records.get(provider)
        if rec is None or rec.cooldown_until is None:
            return True
        return moment >= rec.cooldown_until

    def record_success(self, provider: AIProviderName, *, now: datetime | None = None) -> None:
        moment = now or _utcnow()
        rec = self._record(provider)
        rec.consecutive_failures = 0
        rec.last_success_at = moment
        rec.cooldown_until = None
        rec.last_error = None

    def record_failure(
        self,
        provider: AIProviderName,
        message: str,
        *,
        retry_after_seconds: float | None = None,
        now: datetime | None = None,
    ) -> None:
        moment = now or _utcnow()
        rec = self._record(provider)
        rec.consecutive_failures += 1
        rec.last_error = message[:500]
        rec.last_error_at = moment
        if retry_after_seconds is not None and retry_after_seconds > 0:
            cooldown = retry_after_seconds
        else:
            cooldown = min(
                self._default_cooldown * (2 ** (rec.consecutive_failures - 1)),
                300.0,
            )
        rec.cooldown_until = moment + timedelta(seconds=cooldown)

    def snapshot(self, provider: AIProviderName, *, now: datetime | None = None) -> ProviderHealthSnapshot:
        moment = now or _utcnow()
        rec = self._records.get(provider)
        if rec is None:
            return ProviderHealthSnapshot(
                provider=provider,
                available=True,
                consecutive_failures=0,
                last_error=None,
                last_success_at=None,
                cooldown_until=None,
            )
        return ProviderHealthSnapshot(
            provider=provider,
            available=self.is_available(provider, now=moment),
            consecutive_failures=rec.consecutive_failures,
            last_error=rec.last_error,
            last_success_at=rec.last_success_at,
            cooldown_until=rec.cooldown_until,
        )

    def all_snapshots(
        self, providers: list[AIProviderName], *, now: datetime | None = None
    ) -> list[ProviderHealthSnapshot]:
        return [self.snapshot(p, now=now) for p in providers]
