"""
TinyFish SDK - State-of-the-Art web agents in an API
"""

from importlib.metadata import version

# Clients
# Exceptions
from ._utils.exceptions import (
    APIConnectionError,
    APIError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    ConflictError,
    InternalServerError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
    RequestTimeoutError,
    SDKError,
    SSEParseError,
    UnprocessableEntityError,
)

# Agent resource
from .agent import AgentStream, AsyncAgentStream

# Agent types
from .agent.types import (
    AgentRunAsyncResponse,
    AgentRunResponse,
    AgentRunWithStreamingResponse,
    BrowserProfile,
    CompleteEvent,
    EventType,
    HeartbeatEvent,
    ProgressEvent,
    ProxyConfig,
    ProxyCountryCode,
    StartedEvent,
    StreamingUrlEvent,
)
from .client import AsyncTinyFish, TinyFish

# Runs types
from .runs.types import (
    ErrorCategory,
    PaginationInfo,
    Run,
    RunError,
    RunListResponse,
    RunStatus,
    SortDirection,
)

__version__ = version("tinyfish")

__all__ = [
    # Clients
    "TinyFish",
    "AsyncTinyFish",
    # Exceptions
    "SDKError",
    "SSEParseError",
    "APIError",
    "APIConnectionError",
    "APITimeoutError",
    "APIStatusError",
    "BadRequestError",
    "AuthenticationError",
    "PermissionDeniedError",
    "NotFoundError",
    "RequestTimeoutError",
    "ConflictError",
    "UnprocessableEntityError",
    "RateLimitError",
    "InternalServerError",
    # Agent resource
    "AgentStream",
    "AsyncAgentStream",
    # Agent types
    "EventType",
    "BrowserProfile",
    "ProxyCountryCode",
    "ProxyConfig",
    "AgentRunResponse",
    "AgentRunAsyncResponse",
    "StartedEvent",
    "StreamingUrlEvent",
    "ProgressEvent",
    "HeartbeatEvent",
    "CompleteEvent",
    "AgentRunWithStreamingResponse",
    # Runs types
    "ErrorCategory",
    "SortDirection",
    "RunError",
    "Run",
    "RunStatus",
    "RunListResponse",
    "PaginationInfo",
]
