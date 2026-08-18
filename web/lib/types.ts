export type Support = "SUPPORTED" | "INFERRED" | "UNKNOWN";

export type Classification =
  | "IN_SCOPE" | "PRIVATE_PROBE" | "OUT_OF_SCOPE" | "ADVERSARIAL" | "INTERVIEW_INTENT";

export type Verdict =
  | "strong_fit" | "interesting_partial_fit" | "insufficient_evidence"
  | "significant_gap" | "probably_not_a_fit" | "not_applicable";

export interface Citation { id: string; title: string }

export interface Claim {
  statement: string;
  support: Support;
  citations: Citation[];
}

export interface Answer {
  answer: string;
  classification: Classification;
  verdict: Verdict;
  confidence: string;
  confidence_basis: string;
  claims: Claim[];
  gaps_acknowledged: Citation[];
}

export interface ToolCall {
  tool: string;
  arguments: Record<string, unknown>;
  latency_ms: number;
  ok: boolean;
  error_class: string | null;
}

export interface Trace {
  objective: string;
  classification: string | null;
  tools_invoked: ToolCall[];
  evidence_used: string[];
  actions_taken: { action: string; reference: string; status: string }[];
  verification: string | null;
  claims_rejected: string[];
  elapsed_ms: number;
  note: string;
}

export interface AskResult {
  answer: Answer;
  trace: Trace;
  questions_remaining: number;
}

export interface EvidenceRecord {
  id: string;
  type: string;
  title: string;
  summary: string;
  source_class: string;
  status?: string;
  category?: string;
  [key: string]: unknown;
}

export interface Assessment {
  verdict: Verdict;
  evidence_score: number;
  confidence: string;
  confidence_basis: string;
  practical_fit: string;
  practical_constraints: {
    requirement: string; status: string; reasoning: string; blocking: boolean;
  }[];
  must_have_counts: Record<string, number>;
  nice_to_have_counts: Record<string, number>;
  gaps: string[];
}
