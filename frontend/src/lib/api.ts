/* ------------------------------------------------------------------ */
/*  API client -- talks to the FastAPI backend                        */
/* ------------------------------------------------------------------ */

import type {
  Profile,
  Session,
  SchoolItem,
  RankingSchool,
  Professor,
  ExportFormat,
  ExportPhase,
} from "./types";
import { streamSSE } from "./sse";

export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api";

async function request<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

/* ---- Session ---- */

export function createSession(): Promise<Session> {
  return request("/session", { method: "POST" });
}

export function getSession(id: string): Promise<Session> {
  return request(`/session?session_id=${encodeURIComponent(id)}`);
}

/* ---- CV ---- */

export async function parseCV(
  sessionId: string,
  file: File,
  researchDirection?: string,
): Promise<{ profile: Profile }> {
  const form = new FormData();
  form.append("file", file);
  form.append("session_id", sessionId);
  if (researchDirection) {
    form.append("research_direction", researchDirection);
  }
  const res = await fetch(`${API_BASE}/cv/parse`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) throw new Error(`API ${res.status}`);
  return res.json() as Promise<{ profile: Profile }>;
}

/* ---- School search (SSE) ---- */

export function searchSchools(
  sessionId: string,
  schools: SchoolItem[],
  keywords: string[],
  stealth: boolean,
) {
  return streamSSE(`${API_BASE}/schools/search`, {
    session_id: sessionId,
    schools,
    keywords,
    stealth,
  });
}

/* ---- School recommendations ---- */

export function recommendSchools(
  sessionId: string,
  topN: number,
): Promise<SchoolItem[]> {
  return request("/schools/recommend", {
    method: "POST",
    body: JSON.stringify({ session_id: sessionId, top_n: topN }),
  });
}

/* ---- Deep crawl (SSE) ---- */

export function deepCrawl(
  sessionId: string,
  professorIds: number[],
  stealth: boolean,
) {
  return streamSSE(`${API_BASE}/professors/deep-crawl`, {
    session_id: sessionId,
    professor_ids: professorIds,
    stealth,
  });
}

/* ---- Match ---- */

export function matchProfessors(sessionId: string): Promise<Professor[]> {
  return request("/professors/match", {
    method: "POST",
    body: JSON.stringify({ session_id: sessionId }),
  });
}

/* ---- Rankings ---- */

export function getRankingFields(): Promise<Record<string, string>> {
  return request("/rankings/fields");
}

export function getFieldRanking(
  field: string,
  source?: string,
  country?: string,
): Promise<{ schools: RankingSchool[]; source_url: string }> {
  const params = new URLSearchParams();
  if (source) params.set("source", source);
  if (country) params.set("country", country);
  const qs = params.toString();
  return request(`/rankings/${field}${qs ? `?${qs}` : ""}`);
}

export async function getGlobalSchools(
  source: string,
  country?: string,
): Promise<RankingSchool[]> {
  const params = new URLSearchParams();
  if (country) params.set("country", country);
  const qs = params.toString();
  const res = await request<{ schools: RankingSchool[]; source_url: string }>(
    `/rankings/global/${source}${qs ? `?${qs}` : ""}`,
  );
  return res.schools;
}

/* ---- Export ---- */

export async function exportData(
  sessionId: string,
  phase: ExportPhase,
  format: ExportFormat,
): Promise<Blob> {
  const params = new URLSearchParams({
    session_id: sessionId,
    phase,
  });
  const res = await fetch(
    `${API_BASE}/export/${format}?${params}`,
  );
  if (!res.ok) throw new Error(`Export failed: ${res.status}`);
  return res.blob();
}
