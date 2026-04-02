"use client";

import { useTranslations } from "next-intl";
import type { Profile } from "@/lib/types";

interface ProfileCardProps {
  profile: Profile;
}

export default function ProfileCard({ profile }: ProfileCardProps) {
  const t = useTranslations("label");

  const education = profile.education ?? [];
  const interests = profile.research_interests ?? [];
  const directions = profile.suggested_directions ?? [];
  const skills = profile.skills ?? [];
  const publications = profile.publications ?? [];

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
      {/* Name & email */}
      <h3 className="text-xl font-semibold text-gray-900">
        {profile.full_name}
      </h3>
      {profile.email && (
        <p className="mt-1 text-sm text-gray-500">{profile.email}</p>
      )}

      {/* Education */}
      {education.length > 0 && (
        <div className="mt-4 space-y-1 text-sm text-gray-700">
          {education.map((edu: string) => (
            <p key={edu}>{edu}</p>
          ))}
        </div>
      )}

      {/* Research interests */}
      {interests.length > 0 && (
        <div className="mt-4">
          <p className="text-sm font-medium text-gray-700">
            {t("research_interests")}
          </p>
          <div className="mt-1.5 flex flex-wrap gap-1.5">
            {interests.map((interest) => (
              <span
                key={interest}
                className="inline-block rounded-full bg-indigo-50 px-2.5 py-0.5 text-xs font-medium text-indigo-700"
              >
                {interest}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Suggested directions */}
      {directions.length > 0 && (
        <div className="mt-4">
          <p className="text-sm font-medium text-gray-700">
            {t("suggested_directions")}
          </p>
          <div className="mt-1.5 flex flex-wrap gap-1.5">
            {directions.map((dir) => (
              <span
                key={dir}
                className="inline-block rounded-full bg-emerald-50 px-2.5 py-0.5 text-xs font-medium text-emerald-700"
              >
                {dir}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Skills */}
      {skills.length > 0 && (
        <div className="mt-4">
          <p className="text-sm font-medium text-gray-700">{t("skills")}</p>
          <div className="mt-1.5 flex flex-wrap gap-1.5">
            {skills.map((skill) => (
              <span
                key={skill}
                className="inline-block rounded-full bg-gray-100 px-2.5 py-0.5 text-xs text-gray-600"
              >
                {skill}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Publications count */}
      {publications.length > 0 && (
        <p className="mt-4 text-xs text-gray-400">
          {t("publications_count", { count: publications.length })}
        </p>
      )}
    </div>
  );
}
