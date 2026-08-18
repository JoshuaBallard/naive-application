"use client";

import { useEffect, useState } from "react";
import { api, ApiError } from "./api";

/**
 * One session per visitor per day, shared across pages.
 *
 * Every component used to mint its own on mount, so opening the home page and then the
 * talk page burned two, and a couple of reloads hit the per-address daily limit. The
 * first person to trip it was Josh, testing his own site.
 *
 * The id is kept in localStorage with the day it was issued, so a reload or a walk
 * between pages reuses it and a new day starts fresh.
 */
const KEY = "naive-application.session";

interface Stored {
  id: string;
  day: string;
  remaining: number;
}

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

function read(): Stored | null {
  try {
    const raw = window.localStorage.getItem(KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Stored;
    return parsed.day === today() && parsed.id ? parsed : null;
  } catch {
    return null;
  }
}

function write(value: Stored): void {
  try {
    window.localStorage.setItem(KEY, JSON.stringify(value));
  } catch {
    // Private browsing, or storage disabled. The session still works for this page.
  }
}

export interface SessionState {
  sessionId: string | null;
  remaining: number;
  error: string | null;
  spend: (left: number) => void;
}

export function useSession(budget: number): SessionState {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [remaining, setRemaining] = useState(budget);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const existing = read();
    if (existing) {
      setSessionId(existing.id);
      setRemaining(existing.remaining);
      return;
    }

    let cancelled = false;
    api
      .startSession()
      .then((s) => {
        if (cancelled) return;
        setSessionId(s.session_id);
        setRemaining(s.questions_remaining);
        write({ id: s.session_id, day: today(), remaining: s.questions_remaining });
      })
      .catch((e: unknown) => {
        if (cancelled) return;
        setError(
          e instanceof ApiError
            ? e.message
            : "Could not reach the agent service. The evidence and the fit assessment do not need it.",
        );
      });

    return () => {
      cancelled = true;
    };
  }, [budget]);

  const spend = (left: number) => {
    setRemaining(left);
    const existing = read();
    if (existing) write({ ...existing, remaining: left });
  };

  return { sessionId, remaining, error, spend };
}
