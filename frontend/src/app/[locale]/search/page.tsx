"use client";

import { useCallback, useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import { useSession } from "@/hooks/useSession";
import { useSSEStream } from "@/hooks/useSSEStream";
import type { Professor, SchoolItem } from "@/lib/types";
import SchoolSelector, {
  type SearchMode,
} from "@/components/search/SchoolSelector";
import CrawlProgress from "@/components/search/CrawlProgress";
import ProfessorTable from "@/components/search/ProfessorTable";
import ExportButtons from "@/components/match/ExportButtons";
import { API_BASE } from "@/lib/api";

export default function SearchPage() {
  const t = useTranslations();
  const { sessionId, profile, loading: sessionLoading } = useSession();

  // Mode selector
  const [mode, setMode] = useState<SearchMode>("field");

  // Schools selected from SchoolSelector
  const [selectedSchools, setSelectedSchools] = useState<SchoolItem[]>([]);

  // Search options
  const [customKeywords, setCustomKeywords] = useState("");
  const [stealth, setStealth] = useState(false);

  // SSE stream control
  const [crawlEnabled, setCrawlEnabled] = useState(false);
  const [crawlBody, setCrawlBody] = useState<object>({});

  // SSE stream for pass-1 crawl
  const crawlStream = useSSEStream<Record<string, unknown>>(
    `${API_BASE}/schools/search`,
    crawlBody,
    crawlEnabled,
  );

  // Preliminary scoring
  const [scoreEnabled, setScoreEnabled] = useState(false);
  const [scoreBody, setScoreBody] = useState<object>({});

  const scoreStream = useSSEStream<Record<string, unknown>>(
    `${API_BASE}/professors/score-preliminary`,
    scoreBody,
    scoreEnabled,
  );

  // Selected professor indices for deep crawl
  const [selectedProfIndices, setSelectedProfIndices] = useState<number[]>([]);

  // Derive professors from SSE events (no side effects)
  // Prefer scored results from scoreStream, fallback to unscored from crawlStream
  const professors = useMemo<Professor[]>(() => {
    // 1. If scoring is done, use scored professors
    for (const ev of scoreStream.events) {
      if (ev.event === "done") {
        const d = ev.data as Record<string, unknown>;
        if (d.professors && Array.isArray(d.professors)) {
          return d.professors as Professor[];
        }
      }
    }
    // 2. Otherwise use crawl results (unscored)
    if (crawlStream.events.length === 0) return [];
    for (const ev of crawlStream.events) {
      if (ev.event === "done" || ev.event === "error") {
        const d = ev.data as Record<string, unknown>;
        if (d.professors && Array.isArray(d.professors)) {
          return d.professors as Professor[];
        }
      }
    }
    const profs: Professor[] = [];
    for (const ev of crawlStream.events) {
      if (ev.event === "professor") {
        profs.push(ev.data as unknown as Professor);
      }
    }
    return profs;
  }, [crawlStream.events, scoreStream.events]);

  const crawlDone =
    crawlStream.status === "done" || crawlStream.status === "error";

  // Start crawl
  const handleSearch = useCallback(() => {
    if (!sessionId || selectedSchools.length === 0) return;
    setSelectedProfIndices([]);

    const keywords = customKeywords
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);

    setCrawlBody({
      session_id: sessionId,
      schools: selectedSchools,
      keywords: keywords.length > 0 ? keywords : [],
      stealth,
    });
    setCrawlEnabled(true);
  }, [sessionId, selectedSchools, customKeywords, stealth]);

  const handleScore = useCallback(() => {
    if (!sessionId) return;
    setScoreBody({ session_id: sessionId });
    setScoreEnabled(true);
  }, [sessionId]);

  // Deep crawl
  const [deepEnabled, setDeepEnabled] = useState(false);
  const [deepBody, setDeepBody] = useState<object>({});

  const deepStream = useSSEStream<Record<string, unknown>>(
    `${API_BASE}/professors/deep-crawl`,
    deepBody,
    deepEnabled,
  );

  const handleDeepCrawl = useCallback(() => {
    if (!sessionId || selectedProfIndices.length === 0) return;
    // Convert array indices to actual professor DB IDs
    const ids = selectedProfIndices
      .map((i) => professors[i]?.id)
      .filter((id): id is number => id != null);
    setDeepBody({
      session_id: sessionId,
      professor_ids: ids,
      stealth,
    });
    setDeepEnabled(true);
  }, [sessionId, selectedProfIndices, professors, stealth]);

  if (sessionLoading || !sessionId) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-blue-600 border-t-transparent" />
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* No-profile hint */}
      {!profile && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-300">
          {t("status.no_profile_hint")}
        </div>
      )}

      {/* Mode selector */}
      <div>
        <p className="mb-2 text-sm font-medium text-gray-700 dark:text-gray-300">
          {t("label.school_mode")}
        </p>
        <div className="flex flex-wrap gap-4">
          {(
            [
              { value: "field", label: t("mode.field_ranking") },
              { value: "overall", label: t("mode.overall_ranking") },
              { value: "ai", label: t("mode.ai_recommend") },
            ] as const
          ).map((opt) => (
            <label
              key={opt.value}
              className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300"
            >
              <input
                type="radio"
                name="mode"
                checked={mode === opt.value}
                onChange={() => setMode(opt.value)}
                className="text-blue-600"
              />
              {opt.label}
            </label>
          ))}
        </div>
      </div>

      {/* School selector */}
      <SchoolSelector
        mode={mode}
        sessionId={sessionId}
        onSchoolsChange={setSelectedSchools}
      />

      {/* Custom keywords + stealth */}
      <div className="flex flex-wrap items-end gap-4">
        <div className="flex-1 min-w-[200px]">
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
            {t("label.custom_keywords")}
          </label>
          <input
            type="text"
            value={customKeywords}
            onChange={(e) => setCustomKeywords(e.target.value)}
            placeholder={t("placeholder.custom_kw")}
            className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-200"
          />
        </div>
        <label className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300">
          <input
            type="checkbox"
            checked={stealth}
            onChange={(e) => setStealth(e.target.checked)}
            className="rounded text-blue-600"
          />
          {t("label.stealth_mode")}
        </label>
      </div>

      {/* Search button */}
      <button
        type="button"
        onClick={handleSearch}
        disabled={
          selectedSchools.length === 0 || crawlStream.status === "streaming"
        }
        className="rounded-lg bg-blue-600 px-6 py-2.5 text-sm font-medium text-white shadow-sm hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {crawlStream.status === "streaming" ? (
          <span className="flex items-center gap-2">
            <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
            {t("btn.search_rank")}...
          </span>
        ) : (
          t("btn.search_rank")
        )}
      </button>

      {/* Crawl progress — events now have proper event types */}
      {crawlStream.events.length > 0 && (
        <CrawlProgress events={crawlStream.events} phase="search" />
      )}

      {crawlStream.status === "error" && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-800 dark:bg-red-950 dark:text-red-300">
          SSE stream error
        </div>
      )}

      {/* Professor results table */}
      {crawlDone && professors.length > 0 && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
              {t("label.preliminary_ranking")}
            </h3>
            <ExportButtons sessionId={sessionId} phase="preliminary" />
          </div>

          {/* Score + Deep crawl buttons */}
          <div className="flex items-center gap-4">
            <button
              type="button"
              onClick={handleScore}
              disabled={
                scoreStream.status === "streaming" ||
                scoreStream.status === "done"
              }
              className="rounded-lg bg-purple-600 px-5 py-2 text-sm font-medium text-white shadow-sm hover:bg-purple-700 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {scoreStream.status === "streaming" ? (
                <span className="flex items-center gap-2">
                  <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
                  Scoring...
                </span>
              ) : scoreStream.status === "done" ? (
                "Scored"
              ) : (
                `Score (${professors.length})`
              )}
            </button>

            <button
              type="button"
              onClick={handleDeepCrawl}
              disabled={
                selectedProfIndices.length === 0 ||
                deepStream.status === "streaming"
              }
              className="rounded-lg bg-emerald-600 px-5 py-2 text-sm font-medium text-white shadow-sm hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {deepStream.status === "streaming" ? (
                <span className="flex items-center gap-2">
                  <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
                  {t("btn.start_deep_crawl")}...
                </span>
              ) : (
                <>
                  {t("btn.start_deep_crawl")} ({selectedProfIndices.length})
                </>
              )}
            </button>
          </div>

          {/* Scoring progress */}
          {scoreStream.events.length > 0 && (
            <CrawlProgress events={scoreStream.events} phase="search" />
          )}

          <ProfessorTable
            professors={professors}
            onSelectionChange={setSelectedProfIndices}
          />

          {/* Deep crawl progress */}
          {deepStream.events.length > 0 && (
            <CrawlProgress events={deepStream.events} phase="deep" />
          )}
        </div>
      )}

      {crawlDone && professors.length === 0 && (
        <div className="rounded-lg border border-yellow-200 bg-yellow-50 px-4 py-3 text-sm text-yellow-800 dark:border-yellow-800 dark:bg-yellow-950 dark:text-yellow-300">
          {t("status.no_professors")}
        </div>
      )}
    </div>
  );
}
