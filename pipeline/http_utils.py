"""HTTP request helpers for resilient external API calls."""

from __future__ import annotations

import logging
import time
from typing import Callable

import requests

_MAX_ATTEMPTS = 3
_BACKOFF_SECONDS = (1, 2, 4)


def request_with_retries(
    requester: Callable[[], requests.Response],
    *,
    service: str,
    operation: str,
    logger: logging.Logger,
) -> requests.Response | None:
    """Run an HTTP request with retry/backoff for transient failures."""

    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            response = requester()
        except (requests.Timeout, requests.ConnectionError) as exc:
            if _should_retry_attempt(attempt):
                _sleep_before_retry(
                    logger,
                    service=service,
                    operation=operation,
                    attempt=attempt,
                    reason=str(exc) or exc.__class__.__name__,
                )
                continue
            logger.error(
                "%s request failed for %s after %d attempts: %s",
                service,
                operation,
                _MAX_ATTEMPTS,
                exc,
            )
            return None
        except requests.RequestException as exc:
            logger.error("%s request failed for %s: %s", service, operation, exc)
            return None

        status_code = response.status_code
        if status_code == 401:
            logger.error("API key invalid or expired for %s.", service)
            return None

        if status_code == 429 or 500 <= status_code < 600:
            if _should_retry_attempt(attempt):
                retry_after = response.headers.get("Retry-After")
                reason = f"status {status_code}"
                if retry_after:
                    reason = f"{reason} (retry-after={retry_after})"
                _sleep_before_retry(
                    logger,
                    service=service,
                    operation=operation,
                    attempt=attempt,
                    reason=reason,
                )
                continue
            logger.error(
                "%s returned %d for %s after %d attempts: %s",
                service,
                status_code,
                operation,
                _MAX_ATTEMPTS,
                response.text[:200],
            )
            return None

        if status_code >= 400:
            logger.error(
                "%s returned %d for %s: %s",
                service,
                status_code,
                operation,
                response.text[:200],
            )
            return None

        return response

    return None


def _should_retry_attempt(attempt: int) -> bool:
    """Return whether another retry remains after this attempt."""

    return attempt < _MAX_ATTEMPTS


def _sleep_before_retry(
    logger: logging.Logger,
    *,
    service: str,
    operation: str,
    attempt: int,
    reason: str,
) -> None:
    """Log a retry event and sleep using exponential backoff."""

    delay = _BACKOFF_SECONDS[attempt - 1]
    logger.warning(
        "%s transient failure for %s on attempt %d/%d (%s); retrying in %ds.",
        service,
        operation,
        attempt,
        _MAX_ATTEMPTS,
        reason,
        delay,
    )
    time.sleep(delay)
