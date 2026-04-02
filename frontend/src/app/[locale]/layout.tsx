import type { Metadata } from "next";
import { NextIntlClientProvider, useMessages } from "next-intl";
import { setRequestLocale } from "next-intl/server";
import { routing } from "@/i18n/routing";
import { Geist, Geist_Mono } from "next/font/google";
import "../globals.css";
import LanguageSwitcher from "@/components/layout/LanguageSwitcher";
import StepIndicator from "@/components/layout/StepIndicator";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "PhD Outreach",
  description: "PhD professor outreach automation tool",
};

export function generateStaticParams() {
  return routing.locales.map((locale) => ({ locale }));
}

export default async function LocaleLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);

  const messages = (await import(`../../../messages/${locale}.json`)).default;

  return (
    <html
      lang={locale}
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col bg-white dark:bg-gray-950">
        <NextIntlClientProvider locale={locale} messages={messages}>
          <header className="border-b border-gray-200 dark:border-gray-800">
            <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3">
              <div className="flex items-center gap-6">
                <h1 className="text-lg font-bold text-gray-900 dark:text-gray-100">
                  PhD Outreach
                </h1>
                <StepIndicator />
              </div>
              <LanguageSwitcher />
            </div>
          </header>
          <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6">
            {children}
          </main>
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
