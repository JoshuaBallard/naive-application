import Link from "next/link";

export default function NotFound() {
  return (
    <div className="mx-auto max-w-3xl px-5 py-24">
      <p className="label mb-4">404</p>
      <h1 className="mb-5 text-[clamp(1.5rem,4vw,2.25rem)]">Nothing here</h1>
      <p className="prose-serif mb-8 text-body">
        Which is most of this application, by design. The parts that do exist are the
        evidence, the fit assessment, and the agent that reads them.
      </p>
      <Link href="/" className="text-[15px] text-supported">
        Back to the start →
      </Link>
    </div>
  );
}
