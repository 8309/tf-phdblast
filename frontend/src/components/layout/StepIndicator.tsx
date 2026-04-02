"use client";

import { useTranslations } from "next-intl";
import { usePathname, Link } from "@/i18n/routing";

const steps = [
  { key: "upload", href: "/upload" },
  { key: "search", href: "/search" },
  { key: "deep", href: "/deep" },
  { key: "match", href: "/match" },
] as const;

export default function StepIndicator() {
  const t = useTranslations("tab");
  const pathname = usePathname();

  return (
    <nav className="flex items-center gap-1 overflow-x-auto">
      {steps.map((step, i) => {
        const isActive = pathname.startsWith(`/${step.key}`) || pathname === `/${step.href}`;
        return (
          <div key={step.key} className="flex items-center">
            {i > 0 && (
              <span className="mx-2 text-gray-400 dark:text-gray-500 select-none">
                &rarr;
              </span>
            )}
            <Link
              href={step.href}
              className={`whitespace-nowrap rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
                isActive
                  ? "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300"
                  : "text-gray-600 hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-gray-800"
              }`}
            >
              {t(step.key)}
            </Link>
          </div>
        );
      })}
    </nav>
  );
}
