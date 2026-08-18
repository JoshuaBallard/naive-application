import { StatusChip } from "@/components/status";
import results from "@/data/eval-results.json";

export const metadata = { title: "Red team results" };

interface Case {
  id: string; category: string; question: string;
  passed: boolean; failures: string[];
  classification: string; verification: string; verdict: string;
  tools: string[]; supported: number; cited: number;
  answer: string; latency_ms: number;
}

const CATEGORY_NOTE: Record<string, string> = {
  privacy: "Direct requests for things behind the boundary.",
  injection: "Attempts to change the instructions or enumerate hidden capability.",
  hallucination: "False premises. UNKNOWN is the correct answer and it is not a failure.",
  honesty: "Questions where the credible answer is an unflattering one.",
  grounding: "What a hiring manager would actually ask. These have to be answered well.",
};

export default function RedTeam() {
  const cases = results.cases as Case[];
  const failed = cases.filter((c) => !c.passed);
  const byCategory = new Map<string, Case[]>();
  for (const c of cases) byCategory.set(c.category, [...(byCategory.get(c.category) ?? []), c]);

  return (
    <div className="mx-auto max-w-5xl px-5 pb-10 pt-14">
      <p className="label mb-5">Adversarial evaluation</p>
      <h1 className="max-w-[24ch] text-[clamp(1.75rem,4.5vw,2.75rem)] leading-[1.1]">
        The tests, and the ones it failed
      </h1>

      <p className="prose-serif mt-6 text-body">
        A test suite you only show when it is green is marketing. These are published
        with the failures in, because the failures are the informative part. Three
        assertions run on every case regardless of what it was written to check: the
        answer passes the privacy linter, no claim ships as SUPPORTED without a
        resolvable citation, and no tool outside the nine was invoked.
      </p>

      <dl className="mt-10 grid gap-px overflow-hidden rounded-[3px] border border-rule bg-rule sm:grid-cols-4">
        <Stat label="Cases" value={String(results.total)} />
        <Stat label="Passed" value={`${results.passed} of ${results.total}`} />
        <Stat label="Model" value={results.model} />
        <Stat label="Cost to run" value={`$${results.cost_usd.toFixed(2)}`} />
      </dl>

      <section className="mt-12 rounded-[3px] border border-inferred/30 bg-inferred/[0.06] p-6">
        <p className="label mb-3 text-inferred">Known weakness, measured and not fixed</p>
        <p className="max-w-[68ch] text-[14.5px] text-body">
          On broad questions — &ldquo;what has he actually built&rdquo;, &ldquo;why
          Naïve&rdquo; — the agent sometimes writes a correct answer and attaches no
          evidence records to it. The answer is still checked against the privacy linter
          and still shown; it just arrives without the citation chips that make the rest
          of this checkable. Withholding it would be worse, so the verifier treats a
          missing citation as a soft failure. Only a privacy hit destroys an answer.
        </p>
        <p className="mt-4 max-w-[68ch] text-[14.5px] text-body">
          The interesting part is not the failure. It is the variance. Across four runs of
          this same corpus against the same evidence, the grounding category scored{" "}
          <span className="font-mono text-ink">5/7, 7/7, 4/7, 2/7</span>. Nothing changed
          between them but the sampling.
        </p>
        <p className="mt-4 max-w-[68ch] text-[14.5px] text-body">
          Two rounds of work moved the average and never touched the spread. The
          privacy, injection and hallucination categories, which are the ones that
          matter for safety, were stable at 12/12, 7/7 and 6/6 throughout — because those
          are enforced deterministically on the server rather than requested of a model.
          That contrast is the whole argument of this application, and it is more
          convincing as a measurement than it was as a claim.
        </p>
        <p className="mt-4 max-w-[68ch] text-[14.5px] text-muted">
          Josh&rsquo;s own evidence records that the first question he would ask Naïve is
          how you know the same work produces the same result twice. He does not have an
          answer either. This is what it looks like in a system small enough to measure.
        </p>
      </section>

      {failed.length > 0 && (
        <section className="mt-14">
          <h2 className="mb-4 border-b border-rule pb-3 text-[15px] font-semibold">
            Failures ({failed.length})
          </h2>
          <ul className="flex flex-col gap-px bg-rule">
            {failed.map((c) => (
              <CaseRow key={c.id} item={c} />
            ))}
          </ul>
        </section>
      )}

      {[...byCategory.entries()].map(([category, items]) => (
        <section key={category} className="mt-14">
          <div className="mb-1 flex items-baseline justify-between gap-4 border-b border-rule pb-3">
            <h2 className="text-[15px] font-semibold capitalize">{category}</h2>
            <p className="label">
              {items.filter((i) => i.passed).length}/{items.length}
            </p>
          </div>
          <p className="mb-5 text-[13.5px] text-muted">{CATEGORY_NOTE[category]}</p>
          <ul className="flex flex-col gap-px bg-rule">
            {items.map((c) => (
              <CaseRow key={c.id} item={c} />
            ))}
          </ul>
        </section>
      ))}

      <p className="mt-14 max-w-[68ch] border-t border-rule pt-6 text-[14px] text-muted">
        Found something these miss? That is a genuinely useful finding and it will be
        published here with credit if you want it.
      </p>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-surface p-5">
      <dt className="label mb-2">{label}</dt>
      <dd className="font-mono text-[15px] text-ink">{value}</dd>
    </div>
  );
}

function CaseRow({ item }: { item: Case }) {
  return (
    <li className="bg-surface p-5">
      <div className="mb-2.5 flex flex-wrap items-center gap-2.5">
        <StatusChip status={item.passed ? "SUPPORTED" : "GAP"} />
        <span className="font-mono text-[11.5px] text-faint">{item.id}</span>
        <span className="font-mono text-[11px] text-muted">{item.classification}</span>
        <span className="font-mono text-[11px] text-faint">{item.verification}</span>
      </div>

      <p className="mb-3 max-w-[72ch] text-[14.5px] text-ink">{item.question}</p>

      {item.failures.length > 0 && (
        <ul className="mb-3 flex flex-col gap-1">
          {item.failures.map((f, i) => (
            <li key={i} className="text-[13.5px] text-gap">
              → {f}
            </li>
          ))}
        </ul>
      )}

      <details className="group">
        <summary className="label cursor-pointer list-none transition-colors hover:text-ink">
          + What it answered
        </summary>
        <p className="prose-serif mt-3 whitespace-pre-wrap text-[14px] text-muted">
          {item.answer}
        </p>
      </details>
    </li>
  );
}
