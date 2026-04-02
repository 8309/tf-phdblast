"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { streamSSE } from "@/lib/sse";
import type { SSEEvent } from "@/lib/types";

type StreamStatus = "idle" | "streaming" | "done" | "error";

/**
 * React hook for consuming SSE from POST endpoints.
 * Stores both event type and data for each received event.
 */
export function useSSEStream<T = unknown>(
  url: string,
  body: object,
  enabled: boolean,
) {
  const [events, setEvents] = useState<SSEEvent<T>[]>([]);
  const [status, setStatus] = useState<StreamStatus>("idle");
  const [latestEvent, setLatestEvent] = useState<SSEEvent<T> | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const bodyJson = JSON.stringify(body);

  const consume = useCallback(async () => {
    setEvents([]);
    setLatestEvent(null);
    setStatus("streaming");

    try {
      for await (const sse of streamSSE<T>(url, JSON.parse(bodyJson))) {
        const ev: SSEEvent<T> = { event: sse.event, data: sse.data };
        setEvents((prev) => [...prev, ev]);
        setLatestEvent(ev);
      }
      setStatus("done");
    } catch (err) {
      console.error("SSE stream error:", err);
      setStatus("error");
    }
  }, [url, bodyJson]);

  useEffect(() => {
    if (!enabled) {
      setStatus("idle");
      return;
    }

    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    consume();

    return () => {
      controller.abort();
    };
  }, [enabled, consume]);

  return { events, status, latestEvent };
}
