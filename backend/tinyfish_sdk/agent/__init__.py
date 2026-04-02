"""Browser automation resource."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Iterator
from typing import Any

from tinyfish._utils.resource import BaseAsyncAPIResource, BaseSyncAPIResource
from tinyfish._utils.sse_parser import async_parse_sse_line_stream, parse_sse_line_stream

from .types import (
    AgentRunAsyncResponse,
    AgentRunResponse,
    AgentRunWithStreamingResponse,
    BrowserProfile,
    CompleteEvent,
    HeartbeatEvent,
    ProgressEvent,
    ProxyConfig,
    StartedEvent,
    StreamingUrlEvent,
)


def _build_run_body(
    goal: str,
    url: str,
    browser_profile: BrowserProfile | None,
    proxy_config: ProxyConfig | None,
) -> dict[str, Any]:
    body: dict[str, Any] = {"goal": goal, "url": url}
    if browser_profile is not None:
        body["browser_profile"] = browser_profile
    if proxy_config is not None:
        body["proxy_config"] = proxy_config.model_dump(exclude_none=True)
    return body


class AgentStream:
    """Context manager for a synchronous streaming agent run.

    Use as::

        with (
            client.agent.stream(
                goal=...,
                url=...,
            ) as stream
        ):
            for (
                event
            ) in stream:
                ...
    """

    def __init__(self, iterator: Iterator[AgentRunWithStreamingResponse]) -> None:
        self._iterator = iterator

    def __enter__(self) -> AgentStream:
        return self

    def __exit__(self, *args: object) -> None:
        self._iterator.close()

    def __iter__(self) -> Iterator[AgentRunWithStreamingResponse]:
        return self._iterator


class AsyncAgentStream:
    """Context manager for an asynchronous streaming agent run.

    Use as::

        async with (
            client.agent.stream(
                goal=...,
                url=...,
            ) as stream
        ):
            async for (
                event
            ) in stream:
                ...
    """

    def __init__(self, iterator: AsyncIterator[AgentRunWithStreamingResponse]) -> None:
        self._iterator = iterator

    async def __aenter__(self) -> AsyncAgentStream:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self._iterator.aclose()

    def __aiter__(self) -> AsyncIterator[AgentRunWithStreamingResponse]:
        return self._iterator


class AgentResource(BaseSyncAPIResource):
    """Browser automation methods."""

    def run(
        self,
        *,
        goal: str,
        url: str,
        browser_profile: BrowserProfile | None = None,
        proxy_config: ProxyConfig | None = None,
    ) -> AgentRunResponse:
        """Run a browser automation and wait for it to finish.

        Blocks until the automation completes or fails. Use `queue()` instead
        if you want to kick off the run and check back later.

        Args:
            goal: Natural language description of what to do on the page.
            url: The URL to open the browser on.
            browser_profile: "lite" (default) or "stealth" (anti-detection).
            proxy_config: Optional proxy settings (enabled, country_code).

        Returns:
            AgentRunResponse with status, result, and timing info.

        Raises:
            AuthenticationError: Invalid API key.
            RateLimitError: Too many requests.
            InternalServerError: Something went wrong on the server.
        """
        body = _build_run_body(goal, url, browser_profile, proxy_config)
        return self._post("/v1/automation/run", json=body, cast_to=AgentRunResponse)

    def queue(
        self,
        *,
        goal: str,
        url: str,
        browser_profile: BrowserProfile | None = None,
        proxy_config: ProxyConfig | None = None,
    ) -> AgentRunAsyncResponse:
        """Queue a browser automation and return immediately.

        Does not wait for the run to complete — returns a run_id straight away.
        Use `client.runs.get(run_id)` to poll for the result.

        Args:
            goal: Natural language description of what to do on the page.
            url: The URL to open the browser on.
            browser_profile: "lite" (default) or "stealth" (anti-detection).
            proxy_config: Optional proxy settings (enabled, country_code).

        Returns:
            AgentRunAsyncResponse with the run_id to poll later.

        Raises:
            AuthenticationError: Invalid API key.
            RateLimitError: Too many requests.
            InternalServerError: Something went wrong on the server.
        """
        body = _build_run_body(goal, url, browser_profile, proxy_config)
        return self._post("/v1/automation/run-async", json=body, cast_to=AgentRunAsyncResponse)

    def stream(
        self,
        *,
        goal: str,
        url: str,
        browser_profile: BrowserProfile | None = None,
        proxy_config: ProxyConfig | None = None,
        on_started: Callable[[StartedEvent], None] | None = None,
        on_streaming_url: Callable[[StreamingUrlEvent], None] | None = None,
        on_progress: Callable[[ProgressEvent], None] | None = None,
        on_heartbeat: Callable[[HeartbeatEvent], None] | None = None,
        on_complete: Callable[[CompleteEvent], None] | None = None,
    ) -> AgentStream:
        """Stream live events from a browser automation run.

        Returns a context manager that yields SSE events in real time:
        STARTED → STREAMING_URL → PROGRESS (repeated) → COMPLETE.

        Use the on_* callbacks for a reactive style, or iterate over
        the stream for a sequential style::

            with (
                client.agent.stream(
                    goal=...,
                    url=...,
                ) as stream
            ):
                for (
                    event
                ) in stream:
                    if isinstance(
                        event,
                        ProgressEvent,
                    ):
                        print(
                            event.purpose
                        )

        Args:
            goal: Natural language description of what to do on the page.
            url: The URL to open the browser on.
            browser_profile: "lite" (default) or "stealth" (anti-detection).
            proxy_config: Optional proxy settings (enabled, country_code).
            on_started: Called when the run starts (receives StartedEvent).
            on_streaming_url: Called with the live browser stream URL (receives StreamingUrlEvent).
            on_progress: Called on each automation step (receives ProgressEvent).
            on_heartbeat: Called on keepalive pings (receives HeartbeatEvent).
            on_complete: Called when the run finishes (receives CompleteEvent).

        Returns:
            AgentStream context manager — iterate over it to receive events.

        Raises:
            AuthenticationError: Invalid API key.
            RateLimitError: Too many requests.
            InternalServerError: Something went wrong on the server.
        """
        body = _build_run_body(goal, url, browser_profile, proxy_config)

        def _generate() -> Iterator[AgentRunWithStreamingResponse]:
            lines = self._post_stream("/v1/automation/run-sse", json=body)
            for event_data in parse_sse_line_stream(lines):
                event_type = event_data.get("type")
                if event_type == "STARTED":
                    event = StartedEvent.model_validate(event_data)
                    if on_started:
                        on_started(event)
                    yield event
                elif event_type == "STREAMING_URL":
                    event = StreamingUrlEvent.model_validate(event_data)
                    if on_streaming_url:
                        on_streaming_url(event)
                    yield event
                elif event_type == "PROGRESS":
                    event = ProgressEvent.model_validate(event_data)
                    if on_progress:
                        on_progress(event)
                    yield event
                elif event_type == "HEARTBEAT":
                    event = HeartbeatEvent.model_validate(event_data)
                    if on_heartbeat:
                        on_heartbeat(event)
                    yield event
                elif event_type == "COMPLETE":
                    event = CompleteEvent.model_validate(event_data)
                    if on_complete:
                        on_complete(event)
                    yield event

        return AgentStream(_generate())


class AsyncAgentResource(BaseAsyncAPIResource):
    """Async browser automation methods."""

    async def run(
        self,
        *,
        goal: str,
        url: str,
        browser_profile: BrowserProfile | None = None,
        proxy_config: ProxyConfig | None = None,
    ) -> AgentRunResponse:
        """Run a browser automation and wait for it to finish.

        Async version of `AgentResource.run()`. Awaits until the automation
        completes or fails. Use `queue()` instead if you want to fire and poll.

        Args:
            goal: Natural language description of what to do on the page.
            url: The URL to open the browser on.
            browser_profile: "lite" (default) or "stealth" (anti-detection).
            proxy_config: Optional proxy settings (enabled, country_code).

        Returns:
            AgentRunResponse with status, result, and timing info.

        Raises:
            AuthenticationError: Invalid API key.
            RateLimitError: Too many requests.
            InternalServerError: Something went wrong on the server.
        """
        body = _build_run_body(goal, url, browser_profile, proxy_config)
        return await self._post("/v1/automation/run", json=body, cast_to=AgentRunResponse)

    async def queue(
        self,
        *,
        goal: str,
        url: str,
        browser_profile: BrowserProfile | None = None,
        proxy_config: ProxyConfig | None = None,
    ) -> AgentRunAsyncResponse:
        """Queue a browser automation and return immediately.

        Async version of `AgentResource.queue()`. Returns a run_id without
        waiting for completion. Use `client.runs.get(run_id)` to poll.

        Args:
            goal: Natural language description of what to do on the page.
            url: The URL to open the browser on.
            browser_profile: "lite" (default) or "stealth" (anti-detection).
            proxy_config: Optional proxy settings (enabled, country_code).

        Returns:
            AgentRunAsyncResponse with the run_id to poll later.

        Raises:
            AuthenticationError: Invalid API key.
            RateLimitError: Too many requests.
            InternalServerError: Something went wrong on the server.
        """
        body = _build_run_body(goal, url, browser_profile, proxy_config)
        return await self._post("/v1/automation/run-async", json=body, cast_to=AgentRunAsyncResponse)

    def stream(
        self,
        *,
        goal: str,
        url: str,
        browser_profile: BrowserProfile | None = None,
        proxy_config: ProxyConfig | None = None,
        on_started: Callable[[StartedEvent], None] | None = None,
        on_streaming_url: Callable[[StreamingUrlEvent], None] | None = None,
        on_progress: Callable[[ProgressEvent], None] | None = None,
        on_heartbeat: Callable[[HeartbeatEvent], None] | None = None,
        on_complete: Callable[[CompleteEvent], None] | None = None,
    ) -> AsyncAgentStream:
        """Stream live events from a browser automation run.

        Returns an async context manager that yields SSE events in real time:
        STARTED → STREAMING_URL → PROGRESS (repeated) → COMPLETE.

        Use the on_* callbacks for a reactive style, or iterate over
        the stream for a sequential style::

            async with (
                client.agent.stream(
                    goal=...,
                    url=...,
                ) as stream
            ):
                async for (
                    event
                ) in stream:
                    if isinstance(
                        event,
                        ProgressEvent,
                    ):
                        print(
                            event.purpose
                        )

        Args:
            goal: Natural language description of what to do on the page.
            url: The URL to open the browser on.
            browser_profile: "lite" (default) or "stealth" (anti-detection).
            proxy_config: Optional proxy settings (enabled, country_code).
            on_started: Called when the run starts (receives StartedEvent).
            on_streaming_url: Called with the live browser stream URL (receives StreamingUrlEvent).
            on_progress: Called on each automation step (receives ProgressEvent).
            on_heartbeat: Called on keepalive pings (receives HeartbeatEvent).
            on_complete: Called when the run finishes (receives CompleteEvent).

        Returns:
            AsyncAgentStream context manager — async-iterate over it to receive events.

        Raises:
            AuthenticationError: Invalid API key.
            RateLimitError: Too many requests.
            InternalServerError: Something went wrong on the server.
        """
        body = _build_run_body(goal, url, browser_profile, proxy_config)

        async def _generate() -> AsyncIterator[AgentRunWithStreamingResponse]:
            lines = self._post_stream("/v1/automation/run-sse", json=body)
            async for event_data in async_parse_sse_line_stream(lines):
                event_type = event_data.get("type")
                if event_type == "STARTED":
                    event = StartedEvent.model_validate(event_data)
                    if on_started:
                        on_started(event)
                    yield event
                elif event_type == "STREAMING_URL":
                    event = StreamingUrlEvent.model_validate(event_data)
                    if on_streaming_url:
                        on_streaming_url(event)
                    yield event
                elif event_type == "PROGRESS":
                    event = ProgressEvent.model_validate(event_data)
                    if on_progress:
                        on_progress(event)
                    yield event
                elif event_type == "HEARTBEAT":
                    event = HeartbeatEvent.model_validate(event_data)
                    if on_heartbeat:
                        on_heartbeat(event)
                    yield event
                elif event_type == "COMPLETE":
                    event = CompleteEvent.model_validate(event_data)
                    if on_complete:
                        on_complete(event)
                    yield event

        return AsyncAgentStream(_generate())
