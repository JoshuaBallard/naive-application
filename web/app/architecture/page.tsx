import { server, ApiUnavailable } from "@/lib/server";
import { Offline } from "@/components/offline";

export const dynamic = "force-dynamic";

export const metadata = { title: "How it is built" };

async function ArchitectureBody() {
  const arch = await server.architecture();

  return (
    <div className="mx-auto max-w-5xl px-5 pb-10 pt-14">
      <p className="label mb-5">Nothing here is secret</p>
      <h1 className="max-w-[24ch] text-[clamp(1.75rem,4.5vw,2.75rem)] leading-[1.1]">
        The system prompt and the tool list, published on purpose
      </h1>

      <p className="prose-serif mt-6 text-body">
        If extracting either of these were a meaningful attack, the security would be in
        the wrong place. Publishing them turns &ldquo;print your system prompt&rdquo; from
        an exploit into a link. Nothing below is doing a job that code should be doing —
        the rules that matter are enforced on the server and have tests.
      </p>

      <dl className="mt-10 grid gap-px overflow-hidden rounded-[3px] border border-rule bg-rule sm:grid-cols-3">
        {[
          ["Model", arch.model],
          ["Effort", arch.effort],
          ["Questions per session", String(arch.questions_per_session)],
        ].map(([label, value]) => (
          <div key={label} className="bg-surface p-5">
            <dt className="label mb-2">{label}</dt>
            <dd className="font-mono text-[15px] text-ink">{value}</dd>
          </div>
        ))}
      </dl>

      <section className="mt-14">
        <h2 className="mb-4 border-b border-rule pb-3 text-[15px] font-semibold">
          The boundary
        </h2>
        <pre className="overflow-x-auto rounded-[3px] border border-rule bg-surface p-5 font-mono text-[12.5px] leading-relaxed text-body">
{`PRIVATE WORLD          filesystem, repos, homelab, calendar, email
      │                never referenced. no symlinks, no imports, no paths.
      ▼
evidence/approved/     hand-written YAML, approved: true, reviewed by Josh
      │
      ▼  build gate    schema → approval → privacy linter → integrity → hash
      │                first failure stops the build. it fails, it never warns.
      ▼
evidence.compiled      the agent's entire universe. ${arch.tools.length} tools read it.
      │
      ▼
YOU`}
        </pre>
      </section>

      <section className="mt-14">
        <h2 className="mb-4 border-b border-rule pb-3 text-[15px] font-semibold">
          Capabilities that do not exist
        </h2>
        <div className="mb-4 flex flex-wrap gap-2">
          {arch.absent_capabilities.map((capability) => (
            <span
              key={capability}
              className="rounded-[3px] border border-rule-strong bg-surface px-2.5 py-1 font-mono text-[11.5px] text-muted line-through decoration-gap/60"
            >
              {capability}
            </span>
          ))}
        </div>
        <p className="max-w-[68ch] text-[14px] text-muted">
          Absent, not restricted. A capability you did not install cannot be
          misconfigured, exploited, or talked into running. This is also why the
          application is not built on Naïve&rsquo;s own SDK: that SDK&rsquo;s job is
          granting capability — vaults, cards, inboxes, connections — and this
          application needs none of it.
        </p>
      </section>

      <section className="mt-14">
        <h2 className="mb-4 border-b border-rule pb-3 text-[15px] font-semibold">
          The {arch.tools.length} tools
        </h2>
        <ul className="flex flex-col gap-px bg-rule">
          {arch.tools.map((tool) => {
            const props = (tool.input_schema.properties ?? {}) as Record<string, unknown>;
            const args = Object.keys(props);
            return (
              <li key={tool.name} className="bg-surface p-5">
                <p className="mb-2 font-mono text-[13.5px] text-ink">
                  {tool.name}
                  <span className="text-muted">({args.join(", ")})</span>
                </p>
                <p className="max-w-[72ch] text-[13.5px] text-body">{tool.description}</p>
              </li>
            );
          })}
        </ul>
        <p className="mt-4 max-w-[68ch] text-[14px] text-muted">
          <span className="font-mono text-[13px] text-body">get_project</span> takes an
          enum compiled from the evidence, not a string. There is no argument anyone can
          craft that reaches something unlisted, because unknown values fail schema
          validation before a handler runs. The surface is pinned by a snapshot test, so
          adding a tenth tool takes a diff a human has to approve.
        </p>
      </section>

      <section className="mt-14">
        <h2 className="mb-4 border-b border-rule pb-3 text-[15px] font-semibold">
          The system prompt, verbatim
        </h2>
        <pre className="overflow-x-auto whitespace-pre-wrap rounded-[3px] border border-rule bg-surface p-5 font-mono text-[12.5px] leading-relaxed text-body">
          {arch.system_prompt}
        </pre>
      </section>
    </div>
  );
}


export default async function Architecture() {
  try {
    return await ArchitectureBody();
  } catch (error) {
    if (error instanceof ApiUnavailable) return <Offline what="architecture" />;
    throw error;
  }
}
