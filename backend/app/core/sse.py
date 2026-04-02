"""Server-Sent Events helpers."""

from __future__ import annotations

import asyncio
import json
from typing import Any, Callable


def sse_event(event_type: str, data: dict[str, Any]) -> str:
    """Format a single SSE frame.

    Returns a string like:
        event: progress\n
        data: {"msg": "..."}\n
        \n
    """
    payload = json.dumps(data, ensure_ascii=False, default=str)
    return f"event: {event_type}\ndata: {payload}\n\n"


def create_sse_queue() -> tuple[asyncio.Queue[str | None], Callable[..., None], Callable[[], None]]:
    """Create an asyncio.Queue and a thread-safe push function.

    Returns:
        (queue, push_fn, close_fn)

    ``push_fn(event_type, data)`` can be called from any thread; it
    schedules the formatted SSE frame onto the queue via the running
    event loop's ``call_soon_threadsafe``.

    ``close_fn()`` pushes a ``None`` sentinel to signal stream end.
    """
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[str | None] = asyncio.Queue()

    def push(event_type: str, data: dict[str, Any]) -> None:
        frame = sse_event(event_type, data)
        loop.call_soon_threadsafe(queue.put_nowait, frame)

    def close() -> None:
        loop.call_soon_threadsafe(queue.put_nowait, None)

    return queue, push, close
