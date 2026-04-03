"use client";

import { useCallback, useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import {
  getRankingFields,
  getFieldRanking,
  getGlobalSchools,
  recommendSchools,
} from "@/lib/api";
import type { SchoolItem, RankingSchool } from "@/lib/types";

export type SearchMode = "field" | "overall" | "ai";

interface SchoolSelectorProps {
  mode: SearchMode;
  sessionId: string;
  onSchoolsChange: (schools: SchoolItem[]) => void;
}

/** Display row combining SchoolItem and optional ranking info. */
interface DisplaySchool extends SchoolItem {
  rank?: number;
  country?: string;
}

const COUNTRIES = [
  "",
  // North America
  "US", "CA",
  // Europe
  "UK", "DE", "FR", "NL", "CH", "SE", "IT", "ES", "BE", "AT", "DK", "NO", "FI", "IE", "PL", "CZ", "PT", "GR", "HU", "RO", "HR", "SI", "RS",
  // Asia-Pacific
  "CN", "HK", "TW", "JP", "KR", "SG", "IN", "AU", "NZ", "TH", "MY", "ID", "PH", "VN", "LK",
  // Middle East
  "IL", "SA", "AE", "QA", "TR", "IR", "LB", "JO",
  // Africa
  "ZA", "EG", "NG", "KE", "GH", "MA", "TN", "UG", "TZ", "ET",
  // Latin America
  "BR", "MX", "AR", "CL", "CO",
  // Central Asia
  "RU", "KZ",
];

export default function SchoolSelector({
  mode,
  sessionId,
  onSchoolsChange,
}: SchoolSelectorProps) {
  const t = useTranslations("label");

  // Mode 1 state
  const [fields, setFields] = useState<Record<string, string>>({});
  const [selectedField, setSelectedField] = useState("");
  const [selectedSource, setSelectedSource] = useState("");

  // Mode 2 state
  const [rankingType, setRankingType] = useState<"all" | "qs" | "the">("all");

  // Mode 3 state
  const [topN, setTopN] = useState(15);
  const [recommending, setRecommending] = useState(false);

  // Shared state
  const [country, setCountry] = useState("");
  const [schools, setSchools] = useState<DisplaySchool[]>([]);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [loading, setLoading] = useState(false);

  // Load ranking fields on mount (mode 1)
  useEffect(() => {
    if (mode === "field") {
      getRankingFields()
        .then(setFields)
        .catch(console.error);
    }
  }, [mode]);

  // Fetch schools when criteria change (modes 1 & 2)
  const fetchSchools = useCallback(async () => {
    setLoading(true);
    try {
      let result: DisplaySchool[] = [];
      if (mode === "field" && selectedField) {
        const { schools: ranked } = await getFieldRanking(
          selectedField,
          selectedSource || undefined,
          country || undefined,
        );
        result = ranked.map((s: RankingSchool) => ({
          name: s.name,
          domain: s.domain,
          rank: s.rank,
          country: s.country,
        }));
      } else if (mode === "overall") {
        const ranked = await getGlobalSchools(
          rankingType,
          country || undefined,
        );
        result = ranked.map((s: RankingSchool) => ({
          name: s.name,
          domain: s.domain,
          rank: s.rank,
          country: s.country,
        }));
      }
      setSchools(result);
      setSelected(new Set());
    } catch (err) {
      console.error("Failed to load schools", err);
    } finally {
      setLoading(false);
    }
  }, [mode, selectedField, selectedSource, country, rankingType]);

  useEffect(() => {
    if (mode === "field" && selectedField) {
      fetchSchools();
    } else if (mode === "overall") {
      fetchSchools();
    }
  }, [mode, selectedField, selectedSource, country, rankingType, fetchSchools]);

  // Mode 3: AI recommend
  const handleRecommend = useCallback(async () => {
    setRecommending(true);
    try {
      const result = await recommendSchools(sessionId, topN);
      const displayResult: DisplaySchool[] = result.map((s) => ({
        ...s,
      }));
      setSchools(displayResult);
      setSelected(new Set(displayResult.map((_: DisplaySchool, i: number) => i)));
    } catch (err) {
      console.error("AI recommend failed", err);
    } finally {
      setRecommending(false);
    }
  }, [sessionId, topN]);

  // Sync selected schools back to parent
  useEffect(() => {
    const selectedSchools: SchoolItem[] = schools
      .filter((_: DisplaySchool, i: number) => selected.has(i))
      .map((s) => ({ name: s.name, domain: s.domain, reason: s.reason }));
    onSchoolsChange(selectedSchools);
  }, [selected, schools, onSchoolsChange]);

  const toggleSchool = (idx: number) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(idx)) next.delete(idx);
      else next.add(idx);
      return next;
    });
  };

  const toggleAll = () => {
    if (selected.size === schools.length) {
      setSelected(new Set());
    } else {
      setSelected(new Set(schools.map((_: DisplaySchool, i: number) => i)));
    }
  };

  const fieldKeys = Object.keys(fields);

  return (
    <div className="space-y-4">
      {/* Mode 1: By Field Ranking */}
      {mode === "field" && (
        <div className="flex flex-wrap gap-3">
          <select
            value={selectedField}
            onChange={(e) => setSelectedField(e.target.value)}
            className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
          >
            <option value="">{t("field_select")}</option>
            {fieldKeys.map((key) => (
              <option key={key} value={key}>
                {fields[key]}
              </option>
            ))}
          </select>

          <select
            value={selectedSource}
            onChange={(e) => setSelectedSource(e.target.value)}
            className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
          >
            <option value="">Default</option>
          </select>

          <select
            value={country}
            onChange={(e) => setCountry(e.target.value)}
            className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
          >
            <option value="">{t("country_filter")}</option>
            {COUNTRIES.filter(Boolean).map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </div>
      )}

      {/* Mode 2: By Overall Ranking */}
      {mode === "overall" && (
        <div className="flex flex-wrap gap-3">
          <div className="flex gap-4">
            <label className="flex items-center gap-1.5 text-sm">
              <input
                type="radio"
                checked={rankingType === "all"}
                onChange={() => setRankingType("all")}
                className="text-blue-600"
              />
              All (619)
            </label>
            <label className="flex items-center gap-1.5 text-sm">
              <input
                type="radio"
                checked={rankingType === "the"}
                onChange={() => setRankingType("the")}
                className="text-blue-600"
              />
              THE
            </label>
            <label className="flex items-center gap-1.5 text-sm">
              <input
                type="radio"
                checked={rankingType === "qs"}
                onChange={() => setRankingType("qs")}
                className="text-blue-600"
              />
              QS
            </label>
          </div>

          <select
            value={country}
            onChange={(e) => setCountry(e.target.value)}
            className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
          >
            <option value="">{t("country_filter")}</option>
            {COUNTRIES.filter(Boolean).map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </div>
      )}

      {/* Mode 3: AI Recommend */}
      {mode === "ai" && (
        <div className="flex items-center gap-4">
          <label className="text-sm text-gray-700">
            {t("ai_topn")}:
            <input
              type="range"
              min={5}
              max={30}
              value={topN}
              onChange={(e) => setTopN(Number(e.target.value))}
              className="ml-2 w-32"
            />
            <span className="ml-2 font-medium">{topN}</span>
          </label>
          <button
            type="button"
            onClick={handleRecommend}
            disabled={recommending}
            className="rounded-lg bg-purple-600 px-4 py-2 text-sm font-medium text-white hover:bg-purple-700 disabled:opacity-50"
          >
            {recommending ? "..." : t("ai_schools")}
          </button>
        </div>
      )}

      {/* School list */}
      {loading && (
        <p className="text-sm text-gray-500">Loading...</p>
      )}

      {schools.length > 0 && (
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <p className="text-sm text-gray-600">
              {selected.size}/{schools.length} selected
            </p>
            <button
              type="button"
              onClick={toggleAll}
              className="text-xs text-blue-600 hover:text-blue-800"
            >
              {selected.size === schools.length
                ? "Deselect All"
                : "Select All"}
            </button>
          </div>

          <div className="max-h-64 overflow-y-auto rounded-lg border border-gray-200 bg-white">
            {schools.map((school, i) => (
              <label
                key={`${school.domain}-${i}`}
                className="flex items-center gap-2.5 border-b border-gray-100 px-3 py-2 last:border-b-0 hover:bg-gray-50"
              >
                <input
                  type="checkbox"
                  checked={selected.has(i)}
                  onChange={() => toggleSchool(i)}
                  className="rounded text-blue-600"
                />
                <span className="text-sm">
                  {school.rank != null && (
                    <span className="text-gray-400">#{school.rank} </span>
                  )}
                  <span className="font-medium">{school.name}</span>{" "}
                  <span className="text-gray-400">({school.domain})</span>
                  {school.country && (
                    <span className="ml-1 text-gray-400">
                      [{school.country}]
                    </span>
                  )}
                </span>
                {school.reason && (
                  <span className="ml-auto text-xs text-gray-400 truncate max-w-48">
                    {school.reason}
                  </span>
                )}
              </label>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
