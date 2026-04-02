"use client";

import { useEffect, useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import { useSession } from "@/hooks/useSession";
import type { Professor } from "@/lib/types";
import ProfessorCard from "@/components/analysis/ProfessorCard";
import ExportButtons from "@/components/match/ExportButtons";

export default function DeepAnalysisPage() {
  const t = useTranslations();
  const { sessionId, loading: sessionLoading } = useSession();

  const [professors, setProfessors] = useState<Professor[]>([]);
  const [deepDone, setDeepDone] = useState(false);

  // Load deep results from sessionStorage if available
  useEffect(() => {
    if (!sessionId) return;
    const stored = sessionStorage.getItem(`phd_deep_professors_${sessionId}`);
    if (stored) {
      try {
        const parsed = JSON.parse(stored) as Professor[];
        setProfessors(parsed);
        setDeepDone(true);
      } catch {
        // ignore
      }
    }
  }, [sessionId]);

  // Summary stats
  const stats = useMemo(() => {
    const funding = professors.filter(
      (p) => p.funding && p.funding.length > 0,
    ).length;
    const accepting = professors.filter(
      (p) => p.accepting_students === true,
    ).length;
    return { funding, accepting };
  }, [professors]);

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
        <p>{t("md.deep_desc")}</p>
      </div>

      {/* Summary + export */}
      {deepDone && professors.length > 0 && (
        <>
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="text-sm text-gray-600 dark:text-gray-400">
              {t("status.deep_summary", {
                count: professors.length,
                funding: stats.funding,
                accepting: stats.accepting,
              })}
            </div>
            {sessionId && (
              <ExportButtons sessionId={sessionId} phase="deep" />
            )}
          </div>

          {/* Professor cards */}
          <div className="max-w-3xl mx-auto space-y-4">
            {professors.map((prof, i) => (
              <ProfessorCard
                key={`${prof.name}-${prof.university}`}
                professor={prof}
                rank={i + 1}
              />
            ))}
          </div>
        </>
      )}

      {/* Empty state */}
      {!deepDone && (
        <div className="flex items-center justify-center rounded-xl border border-dashed border-gray-300 py-20 text-sm text-gray-400 dark:border-gray-700">
          {t("empty.deep_results")}
        </div>
      )}
    </div>
  );
}
