import ssl
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from random import uniform
from typing import Any, Self

import httpx

from .budget import RequestBudget


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 3
    base_delay_seconds: float = 1.0
    max_delay_seconds: float = 10.0

    def __post_init__(self):
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")

        if self.base_delay_seconds <= 0:
            raise ValueError("base_delay_seconds must be positive")

        if self.max_delay_seconds <= 0:
            raise ValueError("max_delay_seconds must be positive")

        if self.base_delay_seconds > self.max_delay_seconds:
            raise ValueError("base_delay_seconds cannot be greater than max_delay_seconds")


RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})


class SourceResponseError(ValueError):
    """API returned an unexpected JSON response."""


def raise_for_status_with_detail(response: httpx.Response) -> None:
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        body_preview = exc.response.text.strip()
        if len(body_preview) > 500:
            body_preview = body_preview[:500] + "... [truncated]"
        message = (
            f"Muasamcong HTTP {exc.response.status_code} Error: "
            f"{body_preview or '<empty response body>'} "
            f"(URL: {exc.request.url})"
        )
        raise httpx.HTTPStatusError(
            message,
            request=exc.request,
            response=exc.response,
        ) from exc


def parse_retry_after(value: str | None) -> float | None:
    if value is None:
        return None

    # Retry-After: 5
    try:
        return max(0.0, float(value))
    except ValueError:
        pass

    # Retry-After: Wed, 21 Oct 2026 07:28:00 GMT
    try:
        retry_at = parsedate_to_datetime(value)

        if retry_at.tzinfo is None:
            retry_at = retry_at.replace(tzinfo=UTC)

        return max(
            0.0,
            (retry_at - datetime.now(UTC)).total_seconds(),
        )
    except (ValueError, TypeError, OverflowError):
        return None


def create_default_ssl_context() -> ssl.SSLContext:
    """Create an SSL context compatible with Muasamcong's legacy DH key size."""
    context = ssl.create_default_context()
    context.set_ciphers("DEFAULT:@SECLEVEL=1")
    return context


class MuasamcongClient:
    def __init__(
        self,
        *,
        base_url: str,
        token: str,
        timeout: httpx.Timeout,
        retry_policy: RetryPolicy,
        max_connections: int = 10,
        max_keepalive_connections: int = 5,
        verify: ssl.SSLContext | bool | str | None = None,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        budget: RequestBudget | None = None,
    ) -> None:
        if not base_url.strip() or not token.strip():
            raise ValueError("base_url and token are required")

        if max_connections < 1 or not 0 <= max_keepalive_connections <= max_connections:
            raise ValueError("Invalid connection limits")

        self._token = token
        self._retry_policy = retry_policy
        self._sleep = sleep
        self._budget = (
            budget if budget is not None else RequestBudget(max_inflight=3, min_interval=0.05)
        )

        ssl_verify = verify if verify is not None else create_default_ssl_context()

        self._client = httpx.Client(
            base_url=base_url,
            timeout=timeout,
            limits=httpx.Limits(
                max_connections=max_connections,
                max_keepalive_connections=max_keepalive_connections,
            ),
            verify=ssl_verify,
            transport=transport,
            headers={
                "Accept": "application/json, text/plain, */*",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            },
        )

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    @property
    def budget(self) -> RequestBudget:
        return self._budget

    def _backoff(self, failed_attempt: int) -> float:
        """Calculate the backoff time for a failed attempt."""
        cap = min(
            self._retry_policy.max_delay_seconds,
            self._retry_policy.base_delay_seconds * 2 ** (failed_attempt - 1),
        )

        return uniform(0.0, cap)

    def _post_raw(
        self,
        path: str,
        body: Any,
    ) -> Any:
        for attempt in range(
            1,
            self._retry_policy.max_attempts + 1,
        ):
            try:
                with self._budget.request():
                    response = self._client.post(
                        path,
                        params={"token": self._token},
                        json=body,
                    )

            except (
                httpx.TimeoutException,
                httpx.NetworkError,
                httpx.RemoteProtocolError,
            ):
                if attempt == self._retry_policy.max_attempts:
                    raise

                self._sleep(self._backoff(attempt))
                continue

            is_waf_html_block = response.status_code == 400 and b"<html" in response.content.lower()
            if (
                response.status_code in RETRYABLE_STATUS_CODES or is_waf_html_block
            ) and attempt < self._retry_policy.max_attempts:
                server_delay = parse_retry_after(response.headers.get("Retry-After"))

                cooldown = max(self._retry_policy.base_delay_seconds, 1.5)
                self._budget.defer(server_delay if server_delay is not None else cooldown)

                delay = max(
                    self._backoff(attempt),
                    server_delay or cooldown,
                )

                self._sleep(delay)
                continue

            raise_for_status_with_detail(response)

            content = response.content.strip()
            if not content:
                return None

            try:
                return response.json()
            except ValueError as exc:
                if attempt < self._retry_policy.max_attempts:
                    cooldown = max(self._retry_policy.base_delay_seconds, 1.5)
                    self._budget.defer(cooldown)
                    delay = max(self._backoff(attempt), cooldown)
                    self._sleep(delay)
                    continue

                raise SourceResponseError("API returned invalid JSON") from exc

        raise RuntimeError("Unexpected retry state")

    def post(
        self,
        path: str,
        body: Any,
    ) -> dict[str, Any]:
        payload = self._post_raw(path, body)
        if payload is None:
            return {}
        if not isinstance(payload, dict):
            raise SourceResponseError("API JSON response must be an object")
        return payload

    def post_array(
        self,
        path: str,
        body: Any,
    ) -> list[Any]:
        payload = self._post_raw(path, body)
        if payload is None:
            return []
        if not isinstance(payload, list):
            raise SourceResponseError("API JSON response must be a list")
        return payload
