"use client";

/**
 * Renders a raw_deep_json object as a human-readable card.
 * Auto-detects value types and picks the best display for each.
 */

const LABEL_MAP: Record<string, string> = {
  lab_name: "Lab",
  lab_url: "Lab Website",
  lab_size: "Lab Size",
  scholar_url: "Google Scholar",
  research_summary: "Research Summary",
  research_keywords: "Research Keywords",
  recent_papers: "Recent Papers",
  open_positions: "Open Positions",
  accepting_students: "Accepting Students",
  recruiting_signals: "Recruiting Signals",
  recruiting_likelihood: "Recruiting Likelihood",
  recent_graduates: "Recent Graduates",
  funding: "Funding",
  sources: "Sources",
};

/** Keys to skip (already shown in card header). */
const SKIP_KEYS = new Set(["name", "email", "title", "department", "university"]);

/** Order for display — unlisted keys appear at the end. */
const KEY_ORDER = [
  "research_summary",
  "research_keywords",
  "lab_name",
  "lab_url",
  "lab_size",
  "recent_graduates",
  "accepting_students",
  "recruiting_likelihood",
  "open_positions",
  "recruiting_signals",
  "recent_papers",
  "funding",
  "scholar_url",
  "sources",
];

function formatLabel(key: string): string {
  return (
    LABEL_MAP[key] ??
    key
      .replace(/_/g, " ")
      .replace(/\b\w/g, (c) => c.toUpperCase())
  );
}

function isUrl(s: string): boolean {
  return /^https?:\/\//i.test(s);
}

function isEmpty(v: unknown): boolean {
  if (v == null) return true;
  if (v === "") return true;
  if (v === "unknown") return true;
  if (Array.isArray(v) && v.length === 0) return true;
  return false;
}

function RenderValue({ k, v }: { k: string; v: unknown }) {
  // Sources: array of {url, label}
  if (k === "sources" && Array.isArray(v)) {
    return (
      <div className="flex flex-wrap gap-2">
        {v.map((s: { url?: string; label?: string }, i: number) =>
          s.url ? (
            <a
              key={i}
              href={s.url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 rounded-md border border-gray-200 bg-white px-2.5 py-1 text-xs text-blue-600 shadow-sm transition-colors hover:bg-blue-50 hover:text-blue-700 dark:border-gray-600 dark:bg-gray-700 dark:text-blue-400 dark:hover:bg-gray-600"
            >
              <svg
                className="h-3 w-3 shrink-0"
                fill="none"
                viewBox="0 0 24 24"
                strokeWidth={2}
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M13.5 6H5.25A2.25 2.25 0 003 8.25v10.5A2.25 2.25 0 005.25 21h10.5A2.25 2.25 0 0018 18.75V10.5m-4.5-4.5h6m0 0v6m0-6L9.75 14.25"
                />
              </svg>
              {s.label || new URL(s.url).hostname}
            </a>
          ) : null,
        )}
      </div>
    );
  }

  // Boolean
  if (typeof v === "boolean") {
    return (
      <span
        className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium ${
          v
            ? "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300"
            : "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300"
        }`}
      >
        {v ? "Yes" : "No"}
      </span>
    );
  }

  // Number
  if (typeof v === "number") {
    return (
      <span className="text-sm font-medium text-gray-900 dark:text-gray-100">
        {v}
      </span>
    );
  }

  // String array
  if (Array.isArray(v) && v.every((x) => typeof x === "string")) {
    const items = v as string[];
    // Short items → pills
    const avgLen = items.reduce((s, x) => s + x.length, 0) / items.length;
    if (avgLen < 40) {
      return (
        <div className="flex flex-wrap gap-1.5">
          {items.map((item, i) => (
            <span
              key={i}
              className="rounded-full bg-blue-50 px-2.5 py-0.5 text-xs text-blue-700 dark:bg-blue-900/30 dark:text-blue-300"
            >
              {item}
            </span>
          ))}
        </div>
      );
    }
    // Long items → numbered list
    return (
      <ol className="list-inside list-decimal space-y-1 text-sm text-gray-700 dark:text-gray-300">
        {items.map((item, i) => (
          <li key={i}>{item}</li>
        ))}
      </ol>
    );
  }

  // Single URL string
  if (typeof v === "string" && isUrl(v)) {
    return (
      <a
        href={v}
        target="_blank"
        rel="noopener noreferrer"
        className="text-sm text-blue-600 hover:underline dark:text-blue-400"
      >
        {v}
      </a>
    );
  }

  // Recruiting likelihood
  if (k === "recruiting_likelihood" && typeof v === "string") {
    const color =
      v === "high"
        ? "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300"
        : v === "medium"
          ? "bg-yellow-100 text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300"
          : "bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300";
    return (
      <span
        className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium capitalize ${color}`}
      >
        {v}
      </span>
    );
  }

  // Plain string (paragraph)
  if (typeof v === "string") {
    return (
      <p className="text-sm leading-relaxed text-gray-700 dark:text-gray-300">
        {v}
      </p>
    );
  }

  // Fallback: JSON
  return (
    <pre className="text-xs text-gray-600 dark:text-gray-400">
      {JSON.stringify(v, null, 2)}
    </pre>
  );
}

export default function RawDeepDisplay({
  data,
}: {
  data: Record<string, unknown>;
}) {
  // Sort keys by KEY_ORDER, unlisted keys at end
  const keys = Object.keys(data)
    .filter((k) => !SKIP_KEYS.has(k) && !isEmpty(data[k]))
    .sort((a, b) => {
      const ia = KEY_ORDER.indexOf(a);
      const ib = KEY_ORDER.indexOf(b);
      return (ia === -1 ? 999 : ia) - (ib === -1 ? 999 : ib);
    });

  if (keys.length === 0) return null;

  return (
    <div className="mt-3 space-y-3">
      {keys.map((key) => (
        <div key={key}>
          <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-gray-400 dark:text-gray-500">
            {formatLabel(key)}
          </p>
          <RenderValue k={key} v={data[key]} />
        </div>
      ))}
    </div>
  );
}
