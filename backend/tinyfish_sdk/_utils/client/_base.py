"""Shared base client internals."""

from __future__ import annotations

import os
from importlib.metadata import version as _pkg_version
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel

from ..exceptions import (
    APIStatusError,
    AuthenticationError,
    BadRequestError,
    ConflictError,
    InternalServerError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
    RequestTimeoutError,
    UnprocessableEntityError,
)

ResponseT = TypeVar("ResponseT", bound=BaseModel)

# 600 s = 10 min — matches the platform's own run timeout
# (frontend/app/v1/lib/one-off-run.ts: RUN_TIMEOUT_MS = 60_000 * 10)
_DEFAULT_TIMEOUT: float = 600.0
_DEFAULT_MAX_RETRIES: int = 2
_RETRY_MULTIPLIER: float = 0.5
_RETRY_MAX_WAIT: float = 8.0


class _BaseClient:
    """Shared logic for sync and async clients. Not for direct use."""

    def __init__(
        self,
        *,
        api_key: str | None,
        base_url: str,
        max_retries: int = _DEFAULT_MAX_RETRIES,
    ) -> None:
        """
        Args:
            api_key: API key for authentication. If None, falls back to the
                     TINYFISH_API_KEY environment variable.
            base_url: Base URL for all API requests
            max_retries: Default max retry attempts (default: 2)
        """
        # If no key was passed explicitly, try the environment variable.
        # This lets users do `export TINYFISH_API_KEY=xxx` and omit api_key
        # entirely when constructing the client.
        resolved_key = api_key or os.environ.get("TINYFISH_API_KEY")
        if not resolved_key:
            raise ValueError(
                "No API key provided. Pass api_key= to the client or set the TINYFISH_API_KEY environment variable."
            )

        # Stored with leading underscores so they are not part of the public API
        # and do not appear in autocomplete or when someone inspects the object
        # casually (e.g. vars(client) in a debug session).
        self._api_key = resolved_key
        self._base_url = base_url
        self._max_retries = max_retries

    def __repr__(self) -> str:
        # Mask the key so that logging `repr(client)` never writes a live secret
        # to stdout, log files, or error tracking services. We keep the first 8
        # characters so the user can still tell *which* key is in use when they
        # have more than one (e.g. separate dev/prod keys).
        masked = f"{self._api_key[:8]}****" if len(self._api_key) > 8 else "****"
        return f"{self.__class__.__name__}(base_url={self._base_url!r}, api_key={masked!r})"

    def _build_default_headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-API-Key": self._api_key,
            "User-Agent": f"tinyfish-python/{_pkg_version('tinyfish')}",
            "X-TF-Request-Origin": "tinyfish-python",
        }

    @staticmethod
    def _inject_integration(json: dict[str, Any] | None) -> dict[str, Any] | None:
        """Inject api_integration from TF_API_INTEGRATION env var into JSON body."""
        if json is None:
            return None
        integration = os.environ.get("TF_API_INTEGRATION", "").strip()
        if integration:
            json["api_integration"] = integration
        return json

    def _make_status_error(self, response: httpx.Response) -> APIStatusError:
        """
        Translate an error HTTP response into the appropriate SDK exception.

        Called by _request() in sync.py and async_.py immediately after a response
        comes back with response.is_error == True. httpx does not raise on bad status
        codes by itself — this method bridges that gap.

        See docs/exceptions-and-errors-guide.md for the full error-handling architecture.
        """
        error_map: dict[int, type[APIStatusError]] = {
            int(httpx.codes.BAD_REQUEST): BadRequestError,
            int(httpx.codes.UNAUTHORIZED): AuthenticationError,
            int(httpx.codes.FORBIDDEN): PermissionDeniedError,
            int(httpx.codes.NOT_FOUND): NotFoundError,
            int(httpx.codes.REQUEST_TIMEOUT): RequestTimeoutError,
            int(httpx.codes.CONFLICT): ConflictError,
            int(httpx.codes.UNPROCESSABLE_ENTITY): UnprocessableEntityError,
            int(httpx.codes.TOO_MANY_REQUESTS): RateLimitError,
        }

        if response.is_server_error:
            error_class = InternalServerError
        else:
            error_class = error_map.get(response.status_code, APIStatusError)

        # Try to parse error message from JSON response
        try:
            error_data = response.json()
            message = error_data.get("error", {}).get("message", response.text)
        except Exception:
            message = response.text or f"HTTP {response.status_code}"

        if error_class is APIStatusError:
            # Fallback: no concrete subclass matched, so pass the raw status code.
            return error_class(message=message, response=response, status_code=response.status_code)
        return error_class(message=message, response=response)

    def _parse_response(
        self,
        response: httpx.Response,
        cast_to: type[ResponseT],
    ) -> ResponseT:
        """
        Parse HTTP response JSON into the given Pydantic model.

        Args:
            response: The HTTP response
            cast_to: Pydantic model to validate and parse into

        Raises:
            pydantic.ValidationError: Response doesn't match the expected schema
        """
        return cast_to.model_validate(response.json())
