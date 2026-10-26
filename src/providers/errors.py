"""HTTP / SDK error classification helpers."""

from __future__ import annotations

from providers.base import (
    ProviderAuthError,
    ProviderInvalidRequestError,
    ProviderModelNotFoundError,
    ProviderRateLimitError,
    ProviderTransientError,
)


def redact_secrets(message: str, *secrets: str) -> str:
    result = message
    for secret in secrets:
        if secret and len(secret) >= 8:
            result = result.replace(secret, "***")
    return result


def parse_retry_after(headers: dict[str, str] | None) -> float | None:
    if not headers:
        return None
    raw = headers.get("retry-after") or headers.get("Retry-After")
    if not raw:
        return None
    try:
        return float(raw.strip())
    except ValueError:
        return None


def _is_model_not_found(message: str, status_code: int | None) -> bool:
    lowered = message.lower()
    if status_code == 404 and any(
        token in lowered for token in ("model", "not_found", "does not exist", "no longer available")
    ):
        return True
    return any(
        token in lowered
        for token in (
            "model_not_found",
            "models/gemini",
            "is no longer available",
            "does not exist or you do not have access",
        )
    )


def classify_http_like_error(
    exc: Exception,
    *,
    api_key: str = "",
    status_code: int | None = None,
    headers: dict[str, str] | None = None,
) -> (
    ProviderAuthError
    | ProviderInvalidRequestError
    | ProviderModelNotFoundError
    | ProviderRateLimitError
    | ProviderTransientError
):
    message = redact_secrets(str(exc), api_key)
    response = getattr(exc, "response", None)
    code = status_code
    if code is None and response is not None:
        code = getattr(response, "status_code", None)

    if _is_model_not_found(message, code):
        return ProviderModelNotFoundError(
            _short_model_error(message) or "Model not found. Update GEMINI_MODEL or GROQ_MODEL in .env."
        )

    if code in (401, 403):
        return ProviderAuthError(message)
    if code == 429:
        retry_after = parse_retry_after(headers)
        if retry_after is None and response is not None:
            raw_headers = getattr(response, "headers", None)
            if raw_headers is not None:
                retry_after = parse_retry_after(dict(raw_headers))
        return ProviderRateLimitError(message, retry_after_seconds=retry_after)
    if code in (400, 404):
        return ProviderInvalidRequestError(message)

    lowered = message.lower()
    if any(token in lowered for token in ("401", "403", "unauthorized", "invalid api key")):
        return ProviderAuthError(message)
    if any(token in lowered for token in ("429", "rate limit", "quota", "resource exhausted")):
        retry_after = parse_retry_after(headers)
        return ProviderRateLimitError(message, retry_after_seconds=retry_after)
    if any(token in lowered for token in ("400", "invalid request", "malformed")):
        return ProviderInvalidRequestError(message)
    if any(token in lowered for token in ("timeout", "503", "502", "500", "unavailable")):
        return ProviderTransientError(message)
    return ProviderTransientError(message)


def _short_model_error(message: str) -> str:
    line = message.strip().splitlines()[0] if message.strip() else message
    if len(line) > 280:
        return line[:280] + "…"
    return line
