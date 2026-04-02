"use client";

import { useCallback, useState } from "react";
import { useTranslations } from "next-intl";
import { useSession } from "@/hooks/useSession";
import { parseCV } from "@/lib/api";
import type { Profile } from "@/lib/types";
import FileUpload from "@/components/cv/FileUpload";
import ProfileCard from "@/components/cv/ProfileCard";

export default function UploadPage() {
  const t = useTranslations();
  const { sessionId, profile: sessionProfile, loading: sessionLoading, refresh } = useSession();

  const [file, setFile] = useState<File | null>(null);
  const [direction, setDirection] = useState("");
  const [profile, setProfile] = useState<Profile | null>(null);
  const [parsing, setParsing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [directionConfirmed, setDirectionConfirmed] = useState(false);

  // Show session profile if no local parse result yet
  const displayProfile = profile ?? sessionProfile;

  const handleParse = useCallback(async () => {
    if (!file || !sessionId) return;
    setParsing(true);
    setError(null);
    try {
      const result = await parseCV(sessionId, file, direction || undefined);
      setProfile(result.profile);
      // Auto-fill research direction from parsed profile
      if (!direction && result.profile?.suggested_directions?.length) {
        setDirection(result.profile.suggested_directions.join(", "));
      }
      await refresh();
    } catch (err) {
      setError(
        t("status.parse_failed", {
          error: err instanceof Error ? err.message : String(err),
        }),
      );
    } finally {
      setParsing(false);
    }
  }, [file, sessionId, direction, t, refresh]);

  const handleConfirmDirection = useCallback(() => {
    setDirectionConfirmed(true);
  }, []);

  if (sessionLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-blue-600 border-t-transparent" />
      </div>
    );
  }

  return (
    <div className="grid gap-8 lg:grid-cols-2">
      {/* Left column: Upload + direction */}
      <div className="space-y-6">
        <div>
          <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
            {t("label.pdf_resume")}
          </h2>
          <div className="mt-3">
            <FileUpload onChange={setFile} />
          </div>
        </div>

        <div>
          <label
            htmlFor="direction"
            className="block text-sm font-medium text-gray-700 dark:text-gray-300"
          >
            {t("label.target_direction")}
          </label>
          <input
            id="direction"
            type="text"
            value={direction}
            onChange={(e) => {
              setDirection(e.target.value);
              setDirectionConfirmed(false);
            }}
            placeholder={t("placeholder.research_dir")}
            className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-200"
          />
        </div>

        <div className="flex flex-wrap gap-3">
          <button
            type="button"
            onClick={handleParse}
            disabled={!file || parsing}
            className="rounded-lg bg-blue-600 px-5 py-2 text-sm font-medium text-white shadow-sm hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {parsing ? (
              <span className="flex items-center gap-2">
                <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
                {t("btn.parse_resume")}...
              </span>
            ) : (
              t("btn.parse_resume")
            )}
          </button>

          {displayProfile && direction && (
            <button
              type="button"
              onClick={handleConfirmDirection}
              disabled={directionConfirmed}
              className={`rounded-lg px-5 py-2 text-sm font-medium shadow-sm ${
                directionConfirmed
                  ? "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200"
                  : "bg-emerald-600 text-white hover:bg-emerald-700"
              }`}
            >
              {t("btn.confirm_direction")}
            </button>
          )}
        </div>

        {error && (
          <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-800 dark:bg-red-950 dark:text-red-300">
            {error}
          </div>
        )}

        {directionConfirmed && direction && (
          <div className="rounded-lg border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-700 dark:border-green-800 dark:bg-green-950 dark:text-green-300">
            {t("status.direction_confirmed", { direction })}
          </div>
        )}
      </div>

      {/* Right column: Parsed profile */}
      <div>
        <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
          {t("label.parse_result")}
        </h2>
        <div className="mt-3">
          {parsing && (
            <div className="flex flex-col items-center justify-center rounded-xl border border-gray-200 bg-gray-50 py-16 dark:border-gray-700 dark:bg-gray-900">
              <div className="h-8 w-8 animate-spin rounded-full border-2 border-blue-600 border-t-transparent" />
              <p className="mt-3 text-sm text-gray-500">
                {t("btn.parse_resume")}...
              </p>
            </div>
          )}

          {!parsing && displayProfile && <ProfileCard profile={displayProfile} />}

          {!parsing && !displayProfile && (
            <div className="flex items-center justify-center rounded-xl border border-dashed border-gray-300 py-16 text-sm text-gray-400 dark:border-gray-700">
              {t("status.no_pdf")}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
