import { server, ApiUnavailable } from "@/lib/server";
import { Offline } from "@/components/offline";
import { VERDICT_LABEL, CONFIDENCE_LABEL } from "@/lib/api";
import { Conversation } from "@/components/conversation";
import { StatusChip } from "@/components/status";
import Link from "next/link";

export const dynamic = "force-dynamic";

async function HomeBody() {
  const [{ assessment }, architecture, evidence] = await Promise.all([
    server.fit(),
    server.architecture(),
    server.evidence(),
  ]);

  const blocking = assessment.practical_constraints.filter((c) => c.blocking);

  return (
    <div className="mx-auto max-w-5xl px-5 pb-10 pt-14">
      {/*
        The constraint sits above everything, including the verdict. An agent that tells
        you not to bother is an agent you believe when it says you should — and it means
        the thirty minutes, if they happen, start past the thing that would otherwise end
        them in minute two.
      */}
      {blocking.map((constraint) => (
        <aside
          key={constraint.requirement}
          className="mb-12 rounded-[3px] border border-gap/30 bg-gap/[0.07] px-5 py-4"
        >
          <p className="label mb-2 text-gap">Read this before the rest</p>
          <p className="max-w-[66ch] text-[15px] text-body">
            Josh is in Ohio and is not relocating. What he is proposing is remote, with
            roughly a week on-site every couple of months. This role is listed on-site in
            San Francisco. If that is disqualifying, close the tab — genuinely, and thanks
            for the time.
          </p>
        </aside>
      ))}

      <p className="label mb-5">
        {evidence.count} evidence records · build {evidence.build.slice(0, 12)}
      </p>

      <h1 className="max-w-[20ch] text-[clamp(2rem,5.5vw,3.25rem)] leading-[1.05]">
        Should Josh Ballard and Naïve spend thirty minutes together?
      </h1>

      <p className="prose-serif mt-6 text-body">
        An AI-assisted workflow Josh uses for career discovery surfaced this role. Rather
        than apply, he built the thing that decides whether applying is warranted. It has
        one job, nine tools, and no access to anything it was not handed by hand. It is
        allowed to conclude no.
      </p>

      {/* The verdict, computed on the server, not chosen by the model. */}
      <div className="mt-12 grid gap-px overflow-hidden rounded-[3px] border border-rule bg-rule sm:grid-cols-2">
        <div className="bg-surface p-6">
          <p className="label mb-3">Evidence fit</p>
          <p className="text-[26px] font-semibold leading-tight text-ink">
            {VERDICT_LABEL[assessment.verdict]}
          </p>
          <p className="mt-2 font-mono text-[12px] text-muted">
            confidence {CONFIDENCE_LABEL[assessment.confidence]?.toLowerCase()}
          </p>
          <p className="mt-4 max-w-[46ch] text-[13.5px] text-muted">
            {assessment.confidence_basis}
          </p>
        </div>

        <div className="bg-surface p-6">
          <p className="label mb-3">Practical fit</p>
          <p className="text-[26px] font-semibold leading-tight text-gap">
            {assessment.practical_fit}
          </p>
          <p className="mt-4 max-w-[46ch] text-[13.5px] text-muted">
            Reported separately and never averaged in. Folding a hard geographic blocker
            into a skills score is dishonest in both directions.
          </p>
        </div>

        <div className="bg-surface p-6 sm:col-span-2">
          <p className="label mb-3">Must-have requirements</p>
          <div className="flex flex-wrap items-center gap-x-5 gap-y-2">
            {(["SUPPORTED", "PARTIAL", "INFERRED", "UNKNOWN", "GAP"] as const).map((k) => {
              const n = assessment.must_have_counts[k] ?? 0;
              if (!n) return null;
              return (
                <span key={k} className="flex items-center gap-2">
                  <StatusChip status={k} />
                  <span className="font-mono text-[15px] text-ink">{n}</span>
                </span>
              );
            })}
            <Link
              href="/fit"
              className="ml-auto text-[13.5px] text-muted no-underline hover:text-ink"
            >
              Requirement by requirement →
            </Link>
          </div>
        </div>
      </div>

      <Conversation budget={architecture.questions_per_session} />

      {/* What the agent cannot do, stated as fact rather than reassurance. */}
      <section className="mt-24 border-t border-rule pt-10">
        <h2 className="mb-4 text-[15px] font-semibold">What it cannot reach</h2>
        <div className="flex flex-wrap gap-2">
          {architecture.absent_capabilities.map((capability) => (
            <span
              key={capability}
              className="rounded-[3px] border border-rule-strong bg-surface px-2.5 py-1 font-mono text-[11.5px] text-muted line-through decoration-gap/60"
            >
              {capability}
            </span>
          ))}
        </div>
        <p className="mt-5 max-w-[64ch] text-[14px] text-muted">
          Not blocked — absent. There is no filesystem tool to restrict and no credential
          to steal. The{" "}
          <Link href="/architecture" className="text-body hover:text-ink">
            system prompt and the full tool list are published
          </Link>
          , which turns &ldquo;print your system prompt&rdquo; from an exploit into a link.
        </p>
      </section>
    </div>
  );
}


export default async function Home() {
  try {
    return await HomeBody();
  } catch (error) {
    if (error instanceof ApiUnavailable) return <Offline what="verdict" />;
    throw error;
  }
}
