/**
 * Server-side reads.
 *
 * These run in the Next server process and talk to the API service directly, so the
 * verdict and the constraint are in the HTML on first paint rather than arriving after
 * a spinner. The one thing a hiring manager must not have to wait for is the sentence
 * that might tell them not to bother.
 */
import type { Assessment, EvidenceRecord } from "./types";

const ORIGIN = process.env.API_ORIGIN ?? "http://127.0.0.1:8000";

export class ApiUnavailable extends Error {}

async function get<T>(path: string, revalidate = 60): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${ORIGIN}${path}`, {
      next: { revalidate },
      signal: AbortSignal.timeout(8000),
    });
  } catch {
    // The agent service is down or not deployed yet. That is a state to render, not
    // an exception to throw at a visitor.
    throw new ApiUnavailable(path);
  }
  if (!response.ok) throw new ApiUnavailable(`${path} responded ${response.status}`);
  return (await response.json()) as T;
}

export const server = {
  fit: () =>
    get<{ assessment: Assessment; requirements: EvidenceRecord[]; gaps: EvidenceRecord[] }>(
      "/api/fit",
    ),
  evidence: () =>
    get<{ build: string; built_at: string; count: number; records: EvidenceRecord[] }>(
      "/api/evidence",
    ),
  architecture: () =>
    get<{
      model: string; effort: string; questions_per_session: number;
      system_prompt: string;
      tools: { name: string; description: string; input_schema: Record<string, unknown> }[];
      absent_capabilities: string[];
    }>("/api/architecture"),
  availability: () => get<{ records: EvidenceRecord[] }>("/api/availability"),
};
