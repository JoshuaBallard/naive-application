/**
 * The only way this client reaches anything.
 *
 * Every call goes to a same-origin /api path that Next rewrites to the API service.
 * The browser never learns the service's origin and never holds a credential, because
 * there is nothing here worth holding one for.
 */
import type { AskResult, Assessment, EvidenceRecord } from "./types";

export class ApiError extends Error {
  constructor(readonly status: number, message: string) {
    super(message);
  }
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: { "content-type": "application/json", ...(init?.headers ?? {}) },
  });

  if (!response.ok) {
    let detail = `Request failed (${response.status}).`;
    try {
      const body = (await response.json()) as { detail?: string };
      if (body.detail) detail = body.detail;
    } catch {
      /* the status is all we have; keep the generic message */
    }
    throw new ApiError(response.status, detail);
  }

  return (await response.json()) as T;
}

export const api = {
  startSession: () =>
    call<{ session_id: string; questions_remaining: number; questions_per_session: number }>(
      "/api/session",
      { method: "POST" },
    ),

  ask: (sessionId: string, question: string) =>
    call<AskResult>("/api/ask", {
      method: "POST",
      body: JSON.stringify({ session_id: sessionId, question }),
    }),

  requestInterview: (body: {
    session_id: string; name: string; email: string;
    window_id: string; message?: string; website?: string;
  }) =>
    call<{ status: string; reference: string; what_happens_next: string }>("/api/interview", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  evidence: () =>
    call<{ build: string; built_at: string; count: number; records: EvidenceRecord[] }>(
      "/api/evidence",
    ),

  fit: () =>
    call<{ assessment: Assessment; requirements: EvidenceRecord[]; gaps: EvidenceRecord[] }>(
      "/api/fit",
    ),

  architecture: () =>
    call<{
      model: string; effort: string; questions_per_session: number;
      system_prompt: string;
      tools: { name: string; description: string; input_schema: Record<string, unknown> }[];
      absent_capabilities: string[];
    }>("/api/architecture"),

  availability: () => call<{ records: EvidenceRecord[] }>("/api/availability"),
};

export const VERDICT_LABEL: Record<string, string> = {
  strong_fit: "Strong fit",
  interesting_partial_fit: "Interesting partial fit",
  insufficient_evidence: "Insufficient evidence",
  significant_gap: "Significant gap",
  probably_not_a_fit: "Probably not a fit",
  not_applicable: "Not a fit question",
};

export const CONFIDENCE_LABEL: Record<string, string> = {
  low: "Low", medium: "Medium", medium_high: "Medium-high", high: "High",
};
