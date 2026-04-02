"use client";

import { useCallback, useEffect, useState } from "react";
import { createSession, getSession } from "@/lib/api";
import type { Profile } from "@/lib/types";

const SESSION_KEY = "phd_outreach_session_id";

/**
 * Manage a persistent session id (stored in localStorage).
 * On mount: check localStorage for sessionId, if found call getSession(id).
 * If not found: call createSession(), save to localStorage.
 * Returns { sessionId, profile, professorCounts, loading, refresh }
 */
export function useSession() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [professorCounts, setProfessorCounts] = useState<
    Record<string, number>
  >({});
  const [loading, setLoading] = useState(true);

  const loadSession = useCallback(async (id: string) => {
    try {
      const session = await getSession(id);
      setSessionId(session.id);
      setProfile(session.profile);
      setProfessorCounts(session.professor_counts);
      localStorage.setItem(SESSION_KEY, session.id);
    } catch {
      // Session not found on backend -- create a new one
      const session = await createSession();
      setSessionId(session.id);
      setProfile(session.profile);
      setProfessorCounts(session.professor_counts);
      localStorage.setItem(SESSION_KEY, session.id);
    }
  }, []);

  useEffect(() => {
    const stored = localStorage.getItem(SESSION_KEY);
    if (stored) {
      loadSession(stored).finally(() => setLoading(false));
    } else {
      createSession()
        .then((session) => {
          setSessionId(session.id);
          setProfile(session.profile);
          setProfessorCounts(session.professor_counts);
          localStorage.setItem(SESSION_KEY, session.id);
        })
        .catch((err) => {
          console.error("Failed to create session", err);
        })
        .finally(() => setLoading(false));
    }
  }, [loadSession]);

  const refresh = useCallback(async () => {
    if (!sessionId) return;
    setLoading(true);
    try {
      await loadSession(sessionId);
    } finally {
      setLoading(false);
    }
  }, [sessionId, loadSession]);

  return { sessionId, profile, professorCounts, loading, refresh };
}
