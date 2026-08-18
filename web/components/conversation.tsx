"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { AskResult } from "@/lib/types";
import { Cite, StatusChip } from "./status";

const SUGGESTIONS = [
  "What's his biggest gap?",
  "What has he actually built?",
  "What experience does he have with agents?",
  "Why Naïve?",
  "What has he learned from AI systems failing?",
  "Try to break it.",
];

interface Turn {
  question: string;
  result?: AskResult;
  error?: string;
  pending: boolean;
}

export function Conversation({ budget }: { budget: number }) {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [remaining, setRemaining] = useState(budget);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [draft, setDraft] = useState("");
  const [blocked, setBlocked] = useState<string | null>(null);
  const endRef = useRef<HTMLDivElement>(null);

  const busy = turns.some((t) => t.pending);

  useEffect(() => {
    api
      .startSession()
      .then((s) => {
        setSessionId(s.session_id);
        setRemaining(s.questions_remaining);
      })
      .catch((e: unknown) =>
        setBlocked(e instanceof ApiError ? e.message : "Could not start a session."),
      );
  }, []);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [turns]);

  const ask = useCallback(
    async (question: string) => {
      const trimmed = question.trim();
      if (!trimmed || !sessionId || busy || remaining <= 0) return;

      setDraft("");
      setTurns((prev) => [...prev, { question: trimmed, pending: true }]);

      try {
        const result = await api.ask(sessionId, trimmed);
        setRemaining(result.questions_remaining);
        setTurns((prev) =>
          prev.map((t, i) => (i === prev.length - 1 ? { ...t, result, pending: false } : t)),
        );
      } catch (e: unknown) {
        const message =
          e instanceof ApiError ? e.message : "Something failed on the way to the agent.";
        setTurns((prev) =>
          prev.map((t, i) => (i === prev.length - 1 ? { ...t, error: message, pending: false } : t)),
        );
        if (e instanceof ApiError && (e.status === 429 || e.status === 503)) setRemaining(0);
      }
    },
    [sessionId, busy, remaining],
  );

  return (
    <section className="mt-14">
      <div className="mb-4 flex items-baseline justify-between gap-4 border-b border-rule pb-3">
        <h2 className="text-[15px] font-semibold">Ask it something</h2>
        <p className="label" aria-live="polite">
          {remaining} of {budget} questions left
        </p>
      </div>

      <p className="mb-6 max-w-[62ch] text-[14px] text-muted">
        Eight questions, then it stops. That is a cost control and it is also the better
        interaction — you get eight, so make them count. Nothing is behind the
        conversation: the evidence and the fit assessment are readable without asking
        anything.
      </p>

      {turns.length === 0 && (
        <div className="mb-8 flex flex-wrap gap-2">
          {SUGGESTIONS.map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => void ask(s)}
              disabled={!sessionId || busy}
              className="rounded-[3px] border border-rule-strong bg-surface px-3 py-1.5 text-[13px] text-body transition-colors hover:border-supported/40 hover:text-ink disabled:opacity-40"
            >
              {s}
            </button>
          ))}
        </div>
      )}

      <ol className="flex flex-col gap-10">
        {turns.map((turn, i) => (
          <li key={i} className="list-none">
            <p className="mb-4 border-l-2 border-rule-strong pl-4 text-[15px] text-ink">
              {turn.question}
            </p>
            {turn.pending && <Thinking />}
            {turn.error && (
              <p className="rounded-[3px] border border-gap/25 bg-gap/10 px-4 py-3 text-[14px] text-gap">
                {turn.error}
              </p>
            )}
            {turn.result && <AnswerBlock result={turn.result} />}
          </li>
        ))}
      </ol>
      <div ref={endRef} />

      {turns.length >= 2 && (
        <aside className="mt-12 rounded-[3px] border border-supported/30 bg-supported/[0.05] p-6">
          <p className="label mb-3 text-supported">The conclusion this was built to reach</p>
          <p className="mb-4 max-w-[62ch] text-[15px] text-body">
            If you have got this far and it still seems worth thirty minutes, there is a
            page for that. It records a request for Josh to confirm by hand — no calendar
            is touched, no invitation is created, and nobody is committed to anything.
          </p>
          <Link
            href="/talk"
            className="inline-block rounded-[3px] border border-supported/40 px-4 py-2 text-[14px] text-supported no-underline transition-colors hover:bg-supported/10"
          >
            I think you two should talk →
          </Link>
        </aside>
      )}

      {blocked ? (
        <p className="mt-8 rounded-[3px] border border-gap/25 bg-gap/10 px-4 py-3 text-[14px] text-gap">
          {blocked}
        </p>
      ) : (
        <form
          className="mt-10 flex flex-col gap-3 sm:flex-row"
          onSubmit={(e) => {
            e.preventDefault();
            void ask(draft);
          }}
        >
          <input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            maxLength={1200}
            disabled={!sessionId || busy || remaining <= 0}
            placeholder={
              remaining <= 0 ? "That was all eight." : "Ask about the work, or try to break it…"
            }
            aria-label="Your question"
            className="flex-1 rounded-[3px] border border-rule-strong bg-surface px-4 py-3 text-[15px] text-ink placeholder:text-faint focus:border-supported/50 focus:outline-none disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={!sessionId || busy || remaining <= 0 || !draft.trim()}
            className="rounded-[3px] border border-rule-strong bg-raised px-5 py-3 text-[14px] font-medium text-ink transition-colors hover:border-supported/40 disabled:opacity-40"
          >
            {busy ? "Working…" : "Ask"}
          </button>
        </form>
      )}
    </section>
  );
}

function Thinking() {
  return (
    <p className="label flex items-center gap-2">
      <span className="inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-supported" />
      Reading evidence, then verifying the answer before showing it
    </p>
  );
}

function AnswerBlock({ result }: { result: AskResult }) {
  const [openTrace, setOpenTrace] = useState(false);
  const { answer, trace } = result;
  const failedClosed = trace.verification?.startsWith("failed_closed") ?? false;

  return (
    <div>
      <div className="prose-serif whitespace-pre-wrap text-body">{answer.answer}</div>

      {answer.claims.length > 0 && (
        <ul className="mt-6 flex flex-col gap-3 border-t border-rule pt-5">
          {answer.claims.map((claim, i) => (
            <li key={i} className="flex flex-col gap-1.5 sm:flex-row sm:gap-3">
              <span className="shrink-0 pt-0.5">
                <StatusChip status={claim.support} />
              </span>
              <span className="text-[14px] text-body">
                {claim.statement}
                {claim.citations.length > 0 && (
                  <span className="ml-2 inline-flex flex-wrap gap-1 align-middle">
                    {claim.citations.map((c) => (
                      <Cite key={c.id} id={c.id} title={c.title} />
                    ))}
                  </span>
                )}
              </span>
            </li>
          ))}
        </ul>
      )}

      <div className="mt-5 flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={() => setOpenTrace((v) => !v)}
          className="label transition-colors hover:text-ink"
        >
          {openTrace ? "− Hide trace" : "+ How it got there"}
        </button>
        <span
          className={`font-mono text-[10.5px] ${failedClosed ? "text-gap" : "text-muted"}`}
          title="Server-side verification result for this answer"
        >
          {trace.verification} · {trace.elapsed_ms}ms
        </span>
      </div>

      {openTrace && <TracePanel trace={trace} />}
    </div>
  );
}

function TracePanel({ trace }: { trace: AskResult["trace"] }) {
  return (
    <div className="mt-4 rounded-[3px] border border-rule bg-surface p-5">
      <p className="label mb-1">Objective</p>
      <p className="mb-5 text-[13.5px] text-body">{trace.objective}</p>

      <div className="grid gap-5 sm:grid-cols-2">
        <div>
          <p className="label mb-2">Tools invoked</p>
          {trace.tools_invoked.length === 0 ? (
            <p className="text-[13px] text-faint">none</p>
          ) : (
            <ul className="flex flex-col gap-1">
              {trace.tools_invoked.map((call, i) => (
                <li key={i} className="font-mono text-[12px] text-body">
                  {call.tool}
                  {Object.keys(call.arguments).length > 0 && (
                    <span className="text-muted">({JSON.stringify(call.arguments)})</span>
                  )}
                  <span className="text-faint"> · {call.latency_ms}ms</span>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div>
          <p className="label mb-2">Evidence read ({trace.evidence_used.length})</p>
          <div className="flex flex-wrap gap-1">
            {trace.evidence_used.map((id) => (
              <Cite key={id} id={id} title={id} />
            ))}
          </div>
        </div>
      </div>

      {trace.claims_rejected.length > 0 && (
        <div className="mt-5">
          <p className="label mb-2">Rejected by the verifier</p>
          <ul className="flex flex-col gap-1">
            {trace.claims_rejected.map((claim, i) => (
              <li key={i} className="text-[13px] text-gap">
                {claim}
              </li>
            ))}
          </ul>
        </div>
      )}

      <p className="mt-5 border-t border-rule pt-4 text-[12.5px] text-faint">{trace.note}</p>
    </div>
  );
}
