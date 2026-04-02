import { redirect } from "@/i18n/routing";

export default async function LocaleIndex({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  redirect({ href: "/upload", locale });
}
