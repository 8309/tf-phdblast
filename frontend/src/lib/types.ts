/* ------------------------------------------------------------------ */
/*  Shared types for the PhD Outreach v2 frontend                     */
/* ------------------------------------------------------------------ */

/** Parsed CV / applicant profile returned by the backend. */
export interface Profile {
  full_name: string;
  email: string;
  research_interests: string[];
  education: string[];
  skills: string[];
  publications: string[];
  suggested_field: string;
  suggested_directions: string[];
  target_direction: string[];
}

/** Backend session object. */
export interface Session {
  id: string;
  profile: Profile | null;
  created_at: string;
  professor_counts: Record<string, number>;
}

/** SSE event envelope. */
export interface SSEEvent<T = unknown> {
  event: string;
  data: T;
}

/** A single school entry (search / recommend results). */
export interface SchoolItem {
  name: string;
  domain: string;
  /** Only present in AI-recommend mode. */
  reason?: string;
}

/** School entry from ranking endpoints. */
export interface RankingSchool {
  rank: number;
  name: string;
  domain: string;
  country: string;
}

/** Professor record -- mirrors the backend Professor dataclass. */
export interface Professor {
  name: string;
  university: string;
  department?: string;
  title?: string;
  email?: string;
  profile_url?: string;
  lab_url?: string;
  scholar_url?: string;
  lab_name?: string;
  lab_size?: number | null;
  recent_graduates?: number | null;
  research_summary?: string;
  research_keywords?: string[];
  funding?: string[];
  accepting_students?: boolean | null;
  recruiting_likelihood?: string;
  recruiting_signals?: string[];
  open_positions?: string;
  recent_papers?: string[];
  crawled_at?: string;
  source?: string;
  /** Added after preliminary AI scoring. */
  preliminary_score?: number;
  preliminary_reason?: string;
  /** Added after final matching. */
  final_score?: number;
  final_reason?: string;
}

/** Crawl progress entry for one school. */
export interface SchoolProgress {
  name: string;
  domain: string;
  status: string;
  professorCount: number;
}

/** Export format. */
export type ExportFormat = "csv" | "json";

/** Export phase. */
export type ExportPhase = "preliminary" | "deep" | "final";
