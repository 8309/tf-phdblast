"use client";

import { useCallback, useState } from "react";
import { useTranslations } from "next-intl";
import { useSession } from "@/hooks/useSession";
import { matchProfessors } from "@/lib/api";
import type { Professor } from "@/lib/types";
import ExportButtons from "@/components/match/ExportButtons";

export default function MatchPage() {
  const t = useTranslations();
  const { sessionId, loading: sessionLoading } = useSession();

  const [results, setResults] = useState<Professor[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [scored, setScored] = useState(false);

  const handleRescore = useCallback(async () => {
    if (!sessionId) return;
    setLoading(true);
    setError(null);
    try {
      const data = await matchProfessors(sessionId);
      setResults(data);
      setScored(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, [sessionId]);

  // Badge helpers
  const acceptingBadge = (val: boolean | null | undefined) => {
    if (val === true)
      return (
        <span className="inline-block rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-800">
          {t("card.accepting_yes")}
        </span>
      );
    if (val === false)
      return (
        <span className="inline-block rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-800">
          {t("card.accepting_no")}
        </span>
      );
    return (
      <span className="inline-block rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-600">
        {t("card.accepting_unknown")}
      </span>
    );
  };

  const recruitingBadge = (val: string | undefined) => {
    const lower = (val || "unknown").toLowerCase();
    const colorMap: Record<string, string> = {
      high: "bg-emerald-100 text-emerald-800",
      medium: "bg-yellow-100 text-yellow-800",
      low: "bg-red-100 text-red-800",
      unknown: "bg-gray-100 text-gray-600",
    };
    return (
      <span
        className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${
          colorMap[lower] ?? colorMap.unknown
        }`}
      >
        {lower.toUpperCase()}
      </span>
    );
  };

  if (sessionLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-blue-600 border-t-transparent" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Description */}
      <div className="rounded-lg border border-gray-200 bg-gray-50 px-4 py-3 text-sm text-gray-600 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-400">
        <p>{t("md.final_desc")}</p>
      </div>

      {/* Re-score button */}
      <div className="flex flex-wrap items-center gap-4">
        <button
          type="button"
          onClick={handleRescore}
          disabled={loading}
          className="rounded-lg bg-blue-600 px-6 py-2.5 text-sm font-medium text-white shadow-sm hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {loading ? (
            <span className="flex items-center gap-2">
              <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
              {t("btn.rescore")}...
            </span>
          ) : (
            t("btn.rescore")
          )}
        </button>

        {scored && sessionId && (
          <ExportButtons sessionId={sessionId} phase="final" />
        )}
      </div>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-800 dark:bg-red-950 dark:text-red-300">
          {error}
        </div>
      )}

      {/* Results table */}
      {results.length > 0 && (
        <div className="overflow-x-auto rounded-lg border border-gray-200">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 dark:bg-gray-800">
              <tr>
                <th className="px-3 py-2 text-left font-medium text-gray-600 dark:text-gray-300">
                  #
                </th>
                <th className="px-3 py-2 text-left font-medium text-gray-600 dark:text-gray-300">
                  Score
                </th>
                <th className="px-3 py-2 text-left font-medium text-gray-600 dark:text-gray-300">
                  Name
                </th>
                <th className="px-3 py-2 text-left font-medium text-gray-600 dark:text-gray-300">
                  University
                </th>
                <th className="px-3 py-2 text-left font-medium text-gray-600 dark:text-gray-300">
                  Lab
                </th>
                <th className="px-3 py-2 text-left font-medium text-gray-600 dark:text-gray-300">
                  Accepting
                </th>
                <th className="px-3 py-2 text-left font-medium text-gray-600 dark:text-gray-300">
                  Recruiting
                </th>
                <th className="px-3 py-2 text-left font-medium text-gray-600 dark:text-gray-300">
                  Email
                </th>
                <th className="px-3 py-2 text-left font-medium text-gray-600 dark:text-gray-300">
                  Reason
                </th>
              </tr>
            </thead>
            <tbody>
              {results.map((r, i) => (
                <tr
                  key={`${r.name}-${r.university}`}
                  className="border-t border-gray-100 hover:bg-blue-50/40 dark:border-gray-800 dark:hover:bg-gray-800/40"
                >
                  <td className="px-3 py-2 text-gray-400">{i + 1}</td>
                  <td className="px-3 py-2">
                    <span className="font-semibold text-blue-700 dark:text-blue-400">
                      {r.final_score ?? r.preliminary_score ?? "-"}
                    </span>
                  </td>
                  <td className="px-3 py-2 font-medium text-gray-900 dark:text-gray-100">
                    {r.profile_url ? (
                      <a
                        href={r.profile_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-blue-600 hover:underline"
                      >
                        {r.name}
                      </a>
                    ) : (
                      r.name
                    )}
                  </td>
                  <td className="px-3 py-2 text-gray-600 dark:text-gray-400">
                    {r.university}
                  </td>
                  <td className="px-3 py-2 text-xs text-gray-600 dark:text-gray-400">
                    {r.lab_name ?? "-"}
                  </td>
                  <td className="px-3 py-2">
                    {acceptingBadge(r.accepting_students)}
                  </td>
                  <td className="px-3 py-2">
                    {recruitingBadge(r.recruiting_likelihood)}
                  </td>
                  <td className="px-3 py-2">
                    {r.email ? (
                      <a
                        href={`mailto:${r.email}`}
                        className="text-blue-600 hover:underline"
                      >
                        {r.email}
                      </a>
                    ) : (
                      <span className="text-gray-300">-</span>
                    )}
                  </td>
                  <td className="px-3 py-2 text-xs text-gray-500 dark:text-gray-400 max-w-xs">
                    {r.final_reason ?? r.preliminary_reason ?? ""}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {scored && results.length === 0 && !loading && (
        <div className="rounded-lg border border-yellow-200 bg-yellow-50 px-4 py-3 text-sm text-yellow-800 dark:border-yellow-800 dark:bg-yellow-950 dark:text-yellow-300">
          {t("status.tab3_not_complete")}
        </div>
      )}
    </div>
  );
}
