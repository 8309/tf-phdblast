"use client";

import { useMemo } from "react";
import { useTranslations } from "next-intl";
import type { SSEEvent, SchoolProgress } from "@/lib/types";

interface CrawlProgressProps {
  events: SSEEvent[];
  /** "search" for pass-1, "deep" for pass-2 */
  phase: "search" | "deep";
}

export default function CrawlProgress({ events, phase }: CrawlProgressProps) {
  const t = useTranslations("status");

  // Derive school progress and log lines from events
  const { schoolProgress, logs, totalProfs } = useMemo(() => {
    const map = new Map<string, SchoolProgress>();
    const logLines: string[] = [];
    let profs = 0;

    for (const ev of events) {
      const d = ev.data as Record<string, unknown> | undefined;
      if (!d) continue;

      if (ev.event === "info") {
        const msg = (d.message as string) ?? "";
        if (msg) logLines.push(msg);
      } else if (ev.event === "progress") {
        // Backend sends { school, message } for pass-1 progress
        const school = (d.school as string) ?? (d.professor as string) ?? (d.name as string) ?? "";
        const msg = (d.message as string) ?? "";
        if (school && !map.has(school)) {
          map.set(school, {
            name: school,
            domain: (d.domain as string) ?? "",
            status: "crawling",
            professorCount: 0,
          });
        }
        if (msg) logLines.push(msg);
      } else if (ev.event === "school_done") {
        const school = (d.school as string) ?? (d.name as string) ?? "";
        const count = (d.count as number) ?? 0;
        profs += count;
        if (school) {
          map.set(school, {
            name: school,
            domain: (d.domain as string) ?? "",
            status: d.error ? `error: ${d.error}` : "done",
            professorCount: count,
          });
        }
        logLines.push(`${school}: ${count} professors found`);
      } else if (ev.event === "prof_done") {
        const prof = (d.professor as string) ?? "";
        if (prof) {
          map.set(prof, {
            name: prof,
            domain: "",
            status: "done",
            professorCount: 0,
          });
        }
      } else if (ev.event === "pass1_done" || ev.event === "pass2_done") {
        logLines.push(`Crawl complete. Total: ${d.total ?? 0}`);
      } else if (ev.event === "scoring_progress") {
        logLines.push(`Scoring: ${d.done}/${d.total}`);
      } else if (ev.event === "done") {
        logLines.push((d.message as string) ?? "Done");
      } else if (ev.event === "error") {
        logLines.push(`ERROR: ${(d.message as string) ?? "Unknown error"}`);
      }
    }

    return {
      schoolProgress: Array.from(map.values()),
      logs: logLines,
      totalProfs: profs,
    };
  }, [events]);

  const done = schoolProgress.filter(
    (s) => s.status === "done" || s.status.startsWith("done") || s.status.startsWith("error"),
  ).length;

  return (
    <div className="space-y-4">
      {/* Summary bar */}
      <div className="flex items-center gap-3">
        <div className="h-2 flex-1 rounded-full bg-gray-200">
          <div
            className="h-2 rounded-full bg-blue-500 transition-all"
            style={{
              width:
                schoolProgress.length > 0
                  ? `${(done / schoolProgress.length) * 100}%`
                  : "0%",
            }}
          />
        </div>
        <span className="text-sm text-gray-600">
          {done}/{schoolProgress.length}
          {phase === "search" && totalProfs > 0 && (
            <span className="ml-2 text-green-600">({totalProfs} profs)</span>
          )}
        </span>
      </div>

      {/* Progress table */}
      {schoolProgress.length > 0 && (
        <div className="overflow-x-auto rounded-lg border border-gray-200">
          <table className="w-full text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-3 py-2 text-left font-medium text-gray-600">
                  #
                </th>
                <th className="px-3 py-2 text-left font-medium text-gray-600">
                  {phase === "search" ? t("school") : t("professor")}
                </th>
                <th className="px-3 py-2 text-left font-medium text-gray-600">
                  {t("crawl_status")}
                </th>
                {phase === "search" && (
                  <th className="px-3 py-2 text-left font-medium text-gray-600">
                    {t("professors_found")}
                  </th>
                )}
              </tr>
            </thead>
            <tbody>
              {schoolProgress.map((s, i) => (
                <tr
                  key={s.name || i}
                  className="border-t border-gray-100"
                >
                  <td className="px-3 py-1.5 text-gray-400">{i + 1}</td>
                  <td className="px-3 py-1.5 font-medium">{s.name}</td>
                  <td className="px-3 py-1.5">
                    <StatusBadge status={s.status} />
                  </td>
                  {phase === "search" && (
                    <td className="px-3 py-1.5 text-gray-600">
                      {s.professorCount}
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Live logs */}
      {logs.length > 0 && (
        <div className="rounded-lg border border-gray-200 bg-gray-900 p-3">
          <p className="mb-1 text-xs font-medium text-gray-400">
            {t("live_logs")}
          </p>
          <pre className="max-h-48 overflow-y-auto text-xs leading-5 text-green-400">
            {logs.slice(-30).join("\n")}
          </pre>
        </div>
      )}
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const lower = status.toLowerCase();

  let color = "bg-gray-100 text-gray-600";
  if (lower.includes("crawl") || lower === "crawling") {
    color = "bg-yellow-100 text-yellow-800";
  } else if (lower.includes("done") || lower.includes("complete")) {
    color = "bg-green-100 text-green-800";
  } else if (lower.includes("fail") || lower.includes("error")) {
    color = "bg-red-100 text-red-800";
  }

  return (
    <span
      className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${color}`}
    >
      {status}
    </span>
  );
}
