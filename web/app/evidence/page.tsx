import { server, ApiUnavailable } from "@/lib/server";
import { Offline } from "@/components/offline";
import { StatusChip } from "@/components/status";
import type { EvidenceRecord } from "@/lib/types";

export const dynamic = "force-dynamic";

export const metadata = { title: "The whole world model" };

const ORDER: [string, string][] = [
  ["profile", "Profile"],
  ["work_history", "Work history"],
  ["project", "Projects"],
  ["role_requirement", "Role requirements"],
  ["gap", "Gaps"],
  ["belief", "Beliefs"],
  ["failure", "Failures"],
  ["alignment", "Why Naïve"],
  ["link", "Public links"],
  ["availability", "Availability"],
];

async function EvidenceBody() {
  const { records, count, build, built_at } = await server.evidence();
  const byType = new Map<string, EvidenceRecord[]>();
  for (const record of records) {
    byType.set(record.type, [...(byType.get(record.type) ?? []), record]);
  }

  const checkable = records.filter((r) => r.source_class === "public_artifact").length;

  return (
    <div className="mx-auto max-w-5xl px-5 pb-10 pt-14">
      <p className="label mb-5">Everything it knows</p>
      <h1 className="max-w-[22ch] text-[clamp(1.75rem,4.5vw,2.75rem)] leading-[1.1]">
        This is the agent&rsquo;s entire world model
      </h1>

      <p className="prose-serif mt-6 text-body">
        There is no second tier, no server-only evidence, and no hidden fields. Handing
        all of it to your browser is safe by construction: a record that could not be
        published could not have been compiled, so there is one definition of public here
        rather than two.
      </p>

      <dl className="mt-10 grid gap-px overflow-hidden rounded-[3px] border border-rule bg-rule sm:grid-cols-3">
        <Stat label="Records" value={String(count)} />
        <Stat label="Independently checkable" value={`${checkable} of ${count}`} />
        <Stat label="Build" value={build.slice(0, 12)} sub={built_at} />
      </dl>

      <p className="mt-4 max-w-[70ch] text-[14px] text-muted">
        The rest is Josh&rsquo;s word. Work history is the largest part of that, and it is
        marked <span className="font-mono text-[13px]">self_reported</span> on every
        record, because a résumé is not a commit log and the difference should not have to
        be inferred from a missing link.
      </p>

      {ORDER.map(([type, label]) => {
        const group = byType.get(type);
        if (!group) return null;
        return (
          <section key={type} className="mt-14">
            <div className="mb-5 flex items-baseline justify-between gap-4 border-b border-rule pb-3">
              <h2 className="text-[15px] font-semibold">{label}</h2>
              <p className="label">{group.length}</p>
            </div>
            <ul className="flex flex-col gap-px bg-rule">
              {group.map((record) => (
                <Record key={record.id} record={record} />
              ))}
            </ul>
          </section>
        );
      })}
    </div>
  );
}

function Stat({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="bg-surface p-5">
      <dt className="label mb-2">{label}</dt>
      <dd className="font-mono text-[17px] text-ink">{value}</dd>
      {sub && <dd className="mt-1 font-mono text-[11px] text-faint">{sub}</dd>}
    </div>
  );
}

function Record({ record }: { record: EvidenceRecord }) {
  const redacted = record.sensitive_details_removed === true;
  const claims = Array.isArray(record.verified_claims) ? record.verified_claims : [];
  const limits = Array.isArray(record.known_limitations) ? record.known_limitations : [];

  return (
    <li id={record.id} className="scroll-mt-20 bg-surface p-5">
      <div className="mb-2.5 flex flex-wrap items-center gap-2">
        <span className="font-mono text-[11.5px] text-faint">{record.id}</span>
        {typeof record.status === "string" && <StatusChip status={record.status} />}
        <span className="rounded-[3px] border border-rule-strong px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-[0.1em] text-muted">
          {String(record.source_class).replace(/_/g, " ")}
        </span>
        {record.verification === "self_reported" && (
          <span className="rounded-[3px] border border-unknown/25 bg-unknown/10 px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-[0.1em] text-unknown">
            self reported
          </span>
        )}
        {redacted && (
          <span className="rounded-[3px] border border-gap/25 bg-gap/10 px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-[0.1em] text-gap">
            redacted
          </span>
        )}
      </div>

      <h3 className="mb-2 text-[16px]">{record.title}</h3>
      <p className="max-w-[72ch] text-[14px] text-body">{record.summary}</p>

      {claims.length > 0 && (
        <ul className="mt-4 flex flex-col gap-2 border-l border-rule-strong pl-4">
          {(claims as { claim: string; verification: string; evidence_url?: string }[]).map(
            (claim, i) => (
              <li key={i} className="text-[13.5px] text-muted">
                {claim.claim}{" "}
                {claim.evidence_url ? (
                  <a
                    href={claim.evidence_url}
                    rel="noopener noreferrer nofollow"
                    className="font-mono text-[12px] text-supported"
                  >
                    check it
                  </a>
                ) : (
                  <span className="font-mono text-[11px] uppercase tracking-[0.1em] text-unknown">
                    self reported
                  </span>
                )}
              </li>
            ),
          )}
        </ul>
      )}

      {limits.length > 0 && (
        <div className="mt-4">
          <p className="label mb-1.5">Known limitations</p>
          <ul className="flex flex-col gap-1.5">
            {(limits as string[]).map((limit, i) => (
              <li key={i} className="max-w-[72ch] text-[13.5px] text-muted">
                — {limit}
              </li>
            ))}
          </ul>
        </div>
      )}

      {typeof record.redaction_note === "string" && (
        <p className="mt-4 max-w-[72ch] border-l-2 border-gap/40 pl-4 text-[13.5px] text-muted">
          <span className="label mr-2 text-gap">Removed on the way in</span>
          {record.redaction_note}
        </p>
      )}
    </li>
  );
}


export default async function Evidence() {
  try {
    return await EvidenceBody();
  } catch (error) {
    if (error instanceof ApiUnavailable) return <Offline what="evidence" />;
    throw error;
  }
}
