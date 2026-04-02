"use client";

import { useTranslations } from "next-intl";
import { exportData } from "@/lib/api";
import type { ExportPhase } from "@/lib/types";

interface ExportButtonsProps {
  sessionId: string;
  phase: ExportPhase;
}

export default function ExportButtons({
  sessionId,
  phase,
}: ExportButtonsProps) {
  const t = useTranslations("btn");

  const handleExport = async (format: "csv" | "json") => {
    try {
      const blob = await exportData(sessionId, phase, format);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `phd_outreach_${phase}.${format}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error("Export failed", err);
    }
  };

  return (
    <div className="flex gap-2">
      <button
        type="button"
        onClick={() => handleExport("csv")}
        className="inline-flex items-center gap-1.5 rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 shadow-sm hover:bg-gray-50"
      >
        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
        </svg>
        {t("export_csv")}
      </button>
      <button
        type="button"
        onClick={() => handleExport("json")}
        className="inline-flex items-center gap-1.5 rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 shadow-sm hover:bg-gray-50"
      >
        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
        </svg>
        {t("export_json")}
      </button>
    </div>
  );
}
