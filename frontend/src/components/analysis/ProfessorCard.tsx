"use client";

import { useTranslations } from "next-intl";
import type { Professor } from "@/lib/types";

interface ProfessorCardProps {
  professor: Professor;
  rank: number;
}

/* ------------------------------------------------------------------ */
/*  Badge helpers                                                      */
/* ------------------------------------------------------------------ */

function AcceptingBadge({
  accepting,
  label,
}: {
  accepting: boolean | null | undefined;
  label: string;
}) {
  let cls = "bg-gray-100 text-gray-700"; // unknown
  if (accepting === true) cls = "bg-emerald-100 text-emerald-800";
  if (accepting === false) cls = "bg-red-100 text-red-800";

  return (
    <span
      className={`inline-block rounded-full px-3 py-1 text-xs font-semibold ${cls}`}
    >
      {label}
    </span>
  );
}

function RecruitingBadge({ likelihood }: { likelihood: string }) {
  const lower = (likelihood || "unknown").toLowerCase();

  const colorMap: Record<string, string> = {
    high: "bg-emerald-100 text-emerald-800",
    medium: "bg-yellow-100 text-yellow-800",
    low: "bg-red-100 text-red-800",
    unknown: "bg-gray-100 text-gray-700",
  };

  return (
    <span
      className={`inline-block rounded-full px-3 py-1 text-xs font-semibold ${
        colorMap[lower] ?? colorMap.unknown
      }`}
    >
      {lower.toUpperCase()}
    </span>
  );
}

/* ------------------------------------------------------------------ */
/*  Source link helper                                                  */
/* ------------------------------------------------------------------ */

function SourceLink({
  url,
  label,
}: {
  url?: string;
  label: string;
}) {
  if (!url) return null;
  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      className="ml-1.5 text-xs text-gray-400 hover:text-blue-500"
    >
      [link: {label}]
    </a>
  );
}

/* ------------------------------------------------------------------ */
/*  Main card                                                          */
/* ------------------------------------------------------------------ */

export default function ProfessorCard({ professor: p, rank }: ProfessorCardProps) {
  const t = useTranslations("card");

  // Accepting label
  const acceptingLabel =
    p.accepting_students === true
      ? t("accepting_yes")
      : p.accepting_students === false
        ? t("accepting_no")
        : t("accepting_unknown");

  return (
    <div className="group rounded-xl border border-gray-200 bg-white p-5 shadow-sm transition-shadow hover:shadow-md">
      {/* ---- Header ---- */}
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h3 className="text-lg font-semibold text-gray-900">
            <span className="text-gray-400">{rank}.</span>{" "}
            {p.profile_url ? (
              <a
                href={p.profile_url}
                target="_blank"
                rel="noopener noreferrer"
                className="hover:text-blue-600 hover:underline"
              >
                {p.name}
              </a>
            ) : (
              p.name
            )}
          </h3>

          <p className="mt-0.5 text-sm text-gray-500">
            {p.title && <>{p.title} &middot; </>}
            {p.university}
            {p.department && <> &middot; {p.department}</>}
          </p>

          {p.email && (
            <p className="mt-0.5 text-sm">
              <a
                href={`mailto:${p.email}`}
                className="text-blue-600 hover:underline"
              >
                {p.email}
              </a>
            </p>
          )}
        </div>

        {/* Badges */}
        <div className="flex flex-wrap gap-1.5">
          <AcceptingBadge accepting={p.accepting_students} label={acceptingLabel} />
          <RecruitingBadge likelihood={p.recruiting_likelihood ?? "unknown"} />
        </div>
      </div>

      {/* ---- Lab ---- */}
      {p.lab_name && (
        <div className="mt-3">
          <p className="text-sm font-medium text-gray-800">
            {t("lab_name_icon")} {p.lab_name}
            <SourceLink url={p.lab_url} label={t("lab_link")} />
          </p>
          {(p.lab_size != null || p.recent_graduates != null) && (
            <p className="mt-0.5 text-xs text-gray-500">
              {p.lab_size != null && (
                <span>{t("lab_size", { size: p.lab_size })}</span>
              )}
              {p.lab_size != null && p.recent_graduates != null && " | "}
              {p.recent_graduates != null && (
                <span>
                  {t("recent_grads", { count: p.recent_graduates })}
                </span>
              )}
            </p>
          )}
        </div>
      )}

      {/* ---- Research ---- */}
      {p.research_summary && (
        <div className="mt-3">
          <p className="text-sm text-gray-700">
            <span className="font-medium">{t("research_dir")}</span>{" "}
            {p.research_summary}
            <SourceLink url={p.profile_url} label={t("profile_link")} />
          </p>
        </div>
      )}

      {/* Research keywords */}
      {p.research_keywords && p.research_keywords.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {p.research_keywords.slice(0, 8).map((kw) => (
            <span
              key={kw}
              className="inline-block rounded-full bg-indigo-50 px-2 py-0.5 text-xs font-medium text-indigo-700"
            >
              {kw}
            </span>
          ))}
        </div>
      )}

      {/* ---- Open Positions ---- */}
      {p.open_positions && (
        <div className="mt-3 rounded-md border-l-[3px] border-blue-500 bg-blue-50 px-3 py-2">
          <p className="text-sm text-blue-900">
            <span className="font-semibold">{t("open_positions")}</span>{" "}
            {p.open_positions}
            <SourceLink url={p.profile_url} label={t("profile_link")} />
          </p>
        </div>
      )}

      {/* ---- Recruiting Signals ---- */}
      {p.recruiting_signals && p.recruiting_signals.length > 0 && (
        <div className="mt-3">
          <p className="text-sm font-medium text-gray-800">
            {t("recruiting_signals")}
          </p>
          <ul className="mt-1 ml-4 list-disc space-y-0.5 text-sm text-gray-600">
            {p.recruiting_signals.map((s, i) => (
              <li key={i}>
                {s}
                <SourceLink url={p.profile_url} label={t("profile_link")} />
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* ---- Funding ---- */}
      <div className="mt-3">
        <p className="text-sm font-medium text-gray-800">{t("funding")}</p>
        <ul className="mt-1 ml-4 list-disc space-y-0.5 text-sm text-gray-600">
          {p.funding && p.funding.length > 0 ? (
            p.funding.map((f, i) => (
              <li key={i}>
                {f}
                <SourceLink url={p.profile_url} label={t("profile_link")} />
              </li>
            ))
          ) : (
            <li className="text-gray-400">{t("no_info")}</li>
          )}
        </ul>
      </div>

      {/* ---- Papers ---- */}
      <div className="mt-3">
        <p className="text-sm font-medium text-gray-800">{t("papers")}</p>
        <ul className="mt-1 ml-4 list-disc space-y-0.5 text-sm text-gray-600">
          {p.recent_papers && p.recent_papers.length > 0 ? (
            p.recent_papers.slice(0, 5).map((paper, i) => (
              <li key={i}>
                {paper}
                <SourceLink
                  url={p.scholar_url ?? p.profile_url}
                  label={p.scholar_url ? t("scholar_link") : t("profile_link")}
                />
              </li>
            ))
          ) : (
            <li className="text-gray-400">{t("no_info")}</li>
          )}
        </ul>
      </div>

      {/* ---- Footer ---- */}
      <div className="mt-3 flex flex-wrap gap-3 border-t border-gray-100 pt-2 text-xs text-gray-400">
        {p.crawled_at && (
          <span>
            {t("crawled_at")}: {p.crawled_at}
          </span>
        )}
        {p.source && (
          <span>
            {t("data_source")}: {p.source}
          </span>
        )}
        {p.profile_url && (
          <a
            href={p.profile_url}
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-blue-500"
          >
            {t("profile_link")}
          </a>
        )}
        {p.lab_url && (
          <a
            href={p.lab_url}
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-blue-500"
          >
            {t("lab_link")}
          </a>
        )}
        {p.scholar_url && (
          <a
            href={p.scholar_url}
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-blue-500"
          >
            {t("scholar_link")}
          </a>
        )}
      </div>
    </div>
  );
}
