/**
 * What a visitor sees when the agent service is unreachable.
 *
 * Rendered instead of an error page, for the same reason the daily spend cap has a
 * written explanation rather than a 503: a system that claims to think carefully about
 * failure should not fall over with a stack trace when it does fail.
 */
export function Offline({ what }: { what: string }) {
  return (
    <div className="mx-auto max-w-3xl px-5 py-24">
      <p className="label mb-4">Agent service unreachable</p>
      <h1 className="mb-5 text-[clamp(1.5rem,4vw,2.25rem)]">
        The {what} lives on the other side of a boundary, and that side is not answering
      </h1>
      <p className="prose-serif text-body">
        This page is served by a renderer that holds no evidence, no model key, and no
        credentials. Everything it displays comes from a separate service, and right now
        that service is not responding — either it is between deploys, or it has stopped.
      </p>
      <p className="prose-serif mt-4 text-body">
        The split is the point, so this is the split being visible. Try again shortly.
      </p>
    </div>
  );
}
