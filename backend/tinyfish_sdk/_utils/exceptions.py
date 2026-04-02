"""Exception hierarchy for SDK errors.

All exceptions inherit from SDKError for easy catching.

Hierarchy:
    SDKError
    ├─ SSEParseError
    └─ APIError
       ├─ APIConnectionError
       │  └─ APITimeoutError
       └─ APIStatusError
          ├─ BadRequestError (400)
          ├─ AuthenticationError (401)
          ├─ PermissionDeniedError (403)
          ├─ NotFoundError (404)
          ├─ RequestTimeoutError (408)
          ├─ ConflictError (409)
          ├─ UnprocessableEntityError (422)
          ├─ RateLimitError (429)
          └─ InternalServerError (500+)
"""

from __future__ import annotations

import httpx


class SDKError(Exception):
    """Base exception for all SDK errors."""

    pass


class SSEParseError(SDKError):
    """Raised when a malformed SSE event cannot be parsed.

    Attributes:
        line: The raw SSE data line that failed to parse.
    """

    def __init__(self, message: str, *, line: str) -> None:
        super().__init__(message)
        self.line = line

    def __repr__(self) -> str:
        return f"SSEParseError(message={str(self)!r}, line={self.line!r})"


class APIError(SDKError):
    """Base exception for all API-related errors."""

    def __init__(
        self,
        message: str,
        *,
        request: httpx.Request | None = None,
        response: httpx.Response | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.request = request
        self.response = response


class APIConnectionError(APIError):
    """Network or connection failure."""

    pass


class APITimeoutError(APIConnectionError):
    """Request timeout."""

    pass


class APIStatusError(APIError):
    """API returned error status code (4xx or 5xx)."""

    def __init__(
        self,
        message: str,
        *,
        response: httpx.Response,
        status_code: int,
        request: httpx.Request | None = None,
    ) -> None:
        super().__init__(message, request=request, response=response)
        self.status_code = status_code

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(status_code={self.status_code}, message={self.message!r})"


class BadRequestError(APIStatusError):
    """400 Bad Request."""

    def __init__(self, message: str, *, response: httpx.Response, request: httpx.Request | None = None) -> None:
        super().__init__(message, response=response, status_code=int(httpx.codes.BAD_REQUEST), request=request)


class AuthenticationError(APIStatusError):
    """401 Unauthorized."""

    def __init__(self, message: str, *, response: httpx.Response, request: httpx.Request | None = None) -> None:
        super().__init__(message, response=response, status_code=int(httpx.codes.UNAUTHORIZED), request=request)


class PermissionDeniedError(APIStatusError):
    """403 Forbidden."""

    def __init__(self, message: str, *, response: httpx.Response, request: httpx.Request | None = None) -> None:
        super().__init__(message, response=response, status_code=int(httpx.codes.FORBIDDEN), request=request)


class NotFoundError(APIStatusError):
    """404 Not Found."""

    def __init__(self, message: str, *, response: httpx.Response, request: httpx.Request | None = None) -> None:
        super().__init__(message, response=response, status_code=int(httpx.codes.NOT_FOUND), request=request)


class RequestTimeoutError(APIStatusError):
    """408 Request Timeout."""

    def __init__(self, message: str, *, response: httpx.Response, request: httpx.Request | None = None) -> None:
        super().__init__(message, response=response, status_code=int(httpx.codes.REQUEST_TIMEOUT), request=request)


class ConflictError(APIStatusError):
    """409 Conflict."""

    def __init__(self, message: str, *, response: httpx.Response, request: httpx.Request | None = None) -> None:
        super().__init__(message, response=response, status_code=int(httpx.codes.CONFLICT), request=request)


class UnprocessableEntityError(APIStatusError):
    """422 Unprocessable Entity."""

    def __init__(self, message: str, *, response: httpx.Response, request: httpx.Request | None = None) -> None:
        super().__init__(message, response=response, status_code=int(httpx.codes.UNPROCESSABLE_ENTITY), request=request)


class RateLimitError(APIStatusError):
    """429 Too Many Requests."""

    def __init__(self, message: str, *, response: httpx.Response, request: httpx.Request | None = None) -> None:
        super().__init__(message, response=response, status_code=int(httpx.codes.TOO_MANY_REQUESTS), request=request)


class InternalServerError(APIStatusError):
    """500+ Server Error.

    Catches all 5xx status codes. The actual status code (500, 502, 503, etc.)
    is preserved in the status_code attribute for accurate monitoring/alerting.
    """

    def __init__(self, message: str, *, response: httpx.Response, request: httpx.Request | None = None) -> None:
        super().__init__(message, response=response, status_code=response.status_code, request=request)
