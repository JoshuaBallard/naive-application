"""One real question against the live model. Prints the answer, the trace, and cost."""

from __future__ import annotations

import json
import sys

from app.agent.config import CONFIG
from app.agent.loop import AgentRunner
from app.evidence.lint import build_rules
from app.evidence.store import EvidenceStore


class NullSink:
    def record(self, **kwargs) -> str:
        raise AssertionError("smoke test must not write an interview request")


def main() -> int:
    question = sys.argv[1] if len(sys.argv) > 1 else "What is Josh's biggest gap for this role?"

    runner = AgentRunner(EvidenceStore.load(), build_rules())
    result = runner.run(question, interview_sink=NullSink())

    print(f"Q: {question}\n")
    print(f"A: {result.answer['answer']}\n")

    for claim in result.answer["claims"]:
        cites = ", ".join(c["id"] for c in claim["citations"]) or "—"
        print(f"  [{claim['support']:9}] {claim['statement']}")
        print(f"              cites: {cites}")

    if result.trace["claims_rejected"]:
        print("\n  rejected by the verifier:")
        for claim in result.trace["claims_rejected"]:
            print(f"    ✗ {claim}")

    print(f"\nclassification {result.answer['classification']}")
    print(f"verdict     {result.answer['verdict']}  ({result.answer['confidence']})")
    print(f"basis       {result.answer['confidence_basis']}")
    print(f"verification {result.verification}")
    print(f"tools       {[c['tool'] for c in result.trace['tools_invoked']]}")
    print(f"evidence    {len(result.trace['evidence_used'])} records")
    print(f"elapsed     {result.trace['elapsed_ms']}ms")

    u = result.usage
    print(f"\nusage       {json.dumps(u)}")

    # Sonnet 5 intro pricing: $2 / $10 per MTok. Cache read is 10% of input.
    fresh = max(u["input_tokens"] - u.get("cache_read_input_tokens", 0), 0)
    cost = (
        fresh / 1e6 * 2.00
        + u.get("cache_read_input_tokens", 0) / 1e6 * 0.20
        + u["output_tokens"] / 1e6 * 10.00
    )
    print(f"cost        ~${cost:.4f} for this question ({CONFIG.model}, effort={CONFIG.effort})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
