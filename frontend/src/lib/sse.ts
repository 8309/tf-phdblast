/* ------------------------------------------------------------------ */
/*  SSE stream parser for POST endpoints                              */
/* ------------------------------------------------------------------ */

/**
 * Connect to an SSE endpoint via POST and yield parsed events.
 * Handles the ReadableStream line-by-line, extracting "event:" and "data:" fields.
 */
export async function* streamSSE<T = unknown>(
  url: string,
  body: object,
): AsyncGenerator<{ event: string; data: T }> {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`SSE ${res.status}: ${text}`);
  }

  const reader = res.body?.getReader();
  if (!reader) throw new Error("No response body");

  const decoder = new TextDecoder();
  let buffer = "";
  let currentEvent = "message";
  let currentData = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    // Keep the last incomplete line in the buffer
    buffer = lines.pop() ?? "";

    for (const line of lines) {
      if (line.startsWith("event:")) {
        currentEvent = line.slice(6).trim();
      } else if (line.startsWith("data:")) {
        currentData += line.slice(5).trim();
      } else if (line === "") {
        // Empty line marks end of an event
        if (currentData) {
          try {
            const parsed = JSON.parse(currentData) as T;
            yield { event: currentEvent, data: parsed };
          } catch {
            // If data is not JSON, yield it as a raw string
            yield { event: currentEvent, data: currentData as unknown as T };
          }
        }
        currentEvent = "message";
        currentData = "";
      }
    }
  }

  // Flush any remaining data
  if (currentData) {
    try {
      const parsed = JSON.parse(currentData) as T;
      yield { event: currentEvent, data: parsed };
    } catch {
      yield { event: currentEvent, data: currentData as unknown as T };
    }
  }
}
