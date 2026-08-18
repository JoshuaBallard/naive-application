import { server } from "@/lib/server";
import { VERDICT_LABEL, CONFIDENCE_LABEL } from "@/lib/api";
import { StatusChip, Cite } from "@/components/status";
import type { EvidenceRecord } from "@/lib/types";

export const revalidate = 300;

export const metadata = { title: "Fit, requirement by requirement" };

const GROUPS = [
  { key: "must_have", label: "Must-haves", note: "From the posting's requirements list." },
  { key: "nice_to_have", label: "Nice-to-haves", note: "Weighted at roughly a third of a must-have." },
  { key: "practical", label: "Practical constraints", note: "Reported separately. Never folded into the score." },
] as const;

export default async function Fit() {
  const { assessment, requirements, gaps } = await server.fit();

  return (
    <div className="mx-auto max-w-5xl px-5 pb-10 pt-14">
      <p className="label mb-5">The rubric</p>
      <h1 className="max-w-[24ch] text-[clamp(1.75rem,4.5vw,2.75rem)] leading-[1.1]">
        Every requirement, mapped to evidence or marked missing
      </h1>

      <p className="prose-serif mt-6 text-body">
        The verdict below was computed by a deterministic rubric over these records, on
        the server. The agent reports it and cannot pick it — a model asked whether a
        candidate is a fit drifts toward yes, and a flattering answer nobody can check is
        the one thing this cannot afford.
      </p>

      <div className="mt-10 flex flex-wrap items-baseline gap-x-8 gap-y-3 border-y border-rule py-5">
        <span>
          <span className="label mr-3">Verdict</span>
          <span className="text-[17px] font-semibold text-ink">
            {VERDICT_LABEL[assessment.verdict]}
          </span>
        </span>
        <span>
          <span className="label mr-3">Score</span>
          <span className="font-mono text-[15px] text-ink">
            {assessment.evidence_score.toFixed(2)}
          </span>
        </span>
        <span>
          <span className="label mr-3">Confidence</span>
          <span className="font-mono text-[15px] text-ink">
            {CONFIDENCE_LABEL[assessment.confidence]}
          </span>
        </span>
      </div>
      <p className="mt-4 max-w-[70ch] text-[14px] text-muted">{assessment.confidence_basis}</p>

      {GROUPS.map((group) => {
        const rows = requirements.filter((r) => r.category === group.key);
        if (rows.length === 0) return null;
        return (
          <section key={group.key} className="mt-14">
            <div className="mb-1 flex items-baseline justify-between gap-4 border-b border-rule pb-3">
              <h2 className="text-[15px] font-semibold">{group.label}</h2>
              <p className="label">{rows.length}</p>
            </div>
            <p className="mb-5 text-[13.5px] text-muted">{group.note}</p>
            <ul className="flex flex-col gap-px bg-rule">
              {rows.map((row) => (
                <RequirementRow key={row.id} row={row} />
              ))}
            </ul>
          </section>
        );
      })}

      <section className="mt-16">
        <div className="mb-5 flex items-baseline justify-between gap-4 border-b border-rule pb-3">
          <h2 className="text-[15px] font-semibold">Documented gaps</h2>
          <p className="label">{gaps.length}</p>
        </div>
        <p className="mb-6 max-w-[66ch] text-[14px] text-muted">
          Written by Josh, not discovered by the agent. It cannot claim a gap does not
          exist; it can only report these, plus UNKNOWN for anything unmapped.
        </p>
        <ul className="flex flex-col gap-px bg-rule">
          {gaps.map((gap) => (
            <li key={gap.id} className="bg-surface p-5" id={gap.id}>
              <div className="mb-2 flex flex-wrap items-center gap-3">
                <StatusChip status="GAP" />
                <span className="font-mono text-[11.5px] text-faint">{gap.id}</span>
              </div>
              <h3 className="mb-2 text-[16px]">{gap.title}</h3>
              <p className="max-w-[70ch] text-[14px] text-body">{String(gap.gap ?? "")}</p>
              {typeof gap.honest_mitigation === "string" && (
                <p className="mt-3 max-w-[70ch] border-l border-rule-strong pl-4 text-[13.5px] text-muted">
                  {gap.honest_mitigation}
                </p>
              )}
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

function RequirementRow({ row }: { row: EvidenceRecord }) {
  const ids = Array.isArray(row.evidence_ids) ? (row.evidence_ids as string[]) : [];
  return (
    <li className="bg-surface p-5" id={row.id}>
      <div className="mb-2.5 flex flex-wrap items-center gap-3">
        <StatusChip status={String(row.status)} />
        <span className="font-mono text-[11.5px] text-faint">{row.id}</span>
      </div>
      <h3 className="mb-2 max-w-[62ch] text-[16px]">{String(row.requirement ?? row.title)}</h3>
      <p className="max-w-[72ch] text-[14px] text-body">{String(row.reasoning ?? "")}</p>
      {ids.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1">
          {ids.map((id) => (
            <Cite key={id} id={id} title={id} />
          ))}
        </div>
      )}
    </li>
  );
}
