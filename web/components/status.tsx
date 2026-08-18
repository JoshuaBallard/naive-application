/**
 * Status marks.
 *
 * The only coloured things in this interface. Colour means epistemic status here and
 * nothing else — if it appeared for decoration it would stop carrying meaning where it
 * matters.
 */
const TONE: Record<string, { fg: string; bg: string; border: string }> = {
  SUPPORTED: { fg: "text-supported", bg: "bg-supported/10", border: "border-supported/25" },
  PARTIAL: { fg: "text-inferred", bg: "bg-inferred/10", border: "border-inferred/25" },
  INFERRED: { fg: "text-inferred", bg: "bg-inferred/10", border: "border-inferred/25" },
  UNKNOWN: { fg: "text-unknown", bg: "bg-unknown/10", border: "border-unknown/25" },
  GAP: { fg: "text-gap", bg: "bg-gap/10", border: "border-gap/25" },
};

export function StatusChip({ status, title }: { status: string; title?: string }) {
  const tone = TONE[status] ?? TONE.UNKNOWN!;
  return (
    <span
      title={title}
      className={`inline-block whitespace-nowrap rounded-[3px] border px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-[0.1em] ${tone.fg} ${tone.bg} ${tone.border}`}
    >
      {status}
    </span>
  );
}

export function Cite({ id, title }: { id: string; title: string }) {
  return (
    <a
      href={`/evidence#${id}`}
      title={title}
      className="inline-block rounded-[3px] border border-rule-strong bg-raised px-1.5 py-0.5 font-mono text-[10.5px] text-muted no-underline transition-colors hover:border-supported/40 hover:text-ink"
    >
      {id}
    </a>
  );
}
