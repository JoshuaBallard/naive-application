"use client";

import { useState } from "react";
import { api, ApiError } from "@/lib/api";
import { useSession } from "@/lib/session";

interface Window {
  id: string;
  label: string;
  timezone: string;
}

export function InterviewForm({ windows }: { windows: Window[] }) {
  const { sessionId, error: sessionError } = useSession(8);
  const [windowId, setWindowId] = useState(windows[0]?.id ?? "");
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState<{ reference: string; what_happens_next: string } | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const error = submitError ?? sessionError;

  if (done) {
    return (
      <div className="mt-10 rounded-[3px] border border-supported/30 bg-supported/[0.06] p-6">
        <p className="label mb-3 text-supported">Recorded · pending human approval</p>
        <p className="mb-4 font-mono text-[20px] text-ink">{done.reference}</p>
        <p className="max-w-[62ch] text-[14.5px] text-body">{done.what_happens_next}</p>
      </div>
    );
  }

  return (
    <form
      className="mt-10 flex flex-col gap-5"
      onSubmit={async (e) => {
        e.preventDefault();
        if (!sessionId || submitting) return;

        const form = new FormData(e.currentTarget);
        setSubmitting(true);
        setSubmitError(null);

        try {
          const result = await api.requestInterview({
            session_id: sessionId,
            name: String(form.get("name") ?? ""),
            email: String(form.get("email") ?? ""),
            window_id: windowId,
            message: String(form.get("message") ?? "") || undefined,
            website: String(form.get("website") ?? "") || undefined,
          });
          setDone(result);
        } catch (err: unknown) {
          setSubmitError(err instanceof ApiError ? err.message : "That did not go through.");
        } finally {
          setSubmitting(false);
        }
      }}
    >
      <Field label="Your name">
        <input name="name" required maxLength={120} className={INPUT} />
      </Field>

      <Field label="Email" hint="Used to reply to you and nothing else. Never logged.">
        <input name="email" type="email" required maxLength={200} className={INPUT} />
      </Field>

      <fieldset>
        <legend className="label mb-3">Which window suits</legend>
        <div className="flex flex-col gap-2">
          {windows.map((w) => (
            <label
              key={w.id}
              className={`flex cursor-pointer items-center gap-3 rounded-[3px] border px-4 py-3 text-[14.5px] transition-colors ${
                windowId === w.id
                  ? "border-supported/40 bg-supported/[0.06] text-ink"
                  : "border-rule-strong bg-surface text-body hover:border-rule-strong"
              }`}
            >
              <input
                type="radio"
                name="window"
                value={w.id}
                checked={windowId === w.id}
                onChange={() => setWindowId(w.id)}
                className="accent-[var(--supported)]"
              />
              {w.label}
              <span className="ml-auto font-mono text-[11.5px] text-faint">{w.timezone}</span>
            </label>
          ))}
        </div>
        <p className="mt-2.5 text-[13px] text-muted">
          Static windows Josh wrote down. This is not calendar availability — the
          application cannot see whether any of them are actually free.
        </p>
      </fieldset>

      <Field label="Anything you want him to know" hint="Optional.">
        <textarea name="message" rows={4} maxLength={2000} className={INPUT} />
      </Field>

      {/* Bots fill this in. People never see it. */}
      <div aria-hidden className="absolute left-[-9999px]">
        <label>
          Website
          <input name="website" tabIndex={-1} autoComplete="off" />
        </label>
      </div>

      {error && (
        <p className="rounded-[3px] border border-gap/25 bg-gap/10 px-4 py-3 text-[14px] text-gap">
          {error}
        </p>
      )}

      <button
        type="submit"
        disabled={!sessionId || submitting}
        className="self-start rounded-[3px] border border-rule-strong bg-raised px-6 py-3 text-[14.5px] font-medium text-ink transition-colors hover:border-supported/40 disabled:opacity-40"
      >
        {submitting ? "Recording…" : "Record the request"}
      </button>
    </form>
  );
}

const INPUT =
  "w-full rounded-[3px] border border-rule-strong bg-surface px-4 py-3 text-[15px] text-ink placeholder:text-faint focus:border-supported/50 focus:outline-none";

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="flex flex-col gap-2">
      <span className="label">{label}</span>
      {children}
      {hint && <span className="text-[13px] text-muted">{hint}</span>}
    </label>
  );
}
