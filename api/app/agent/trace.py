"""The trace the viewer is allowed to see.

This is decision structure, not reasoning tokens. It is built on the server from what
actually happened — the tool calls that ran, the records they returned, the verdict the
rubric computed — never from the model describing itself. A model narrating its own
process is writing fiction that happens to be about itself.

Arguments are allowlisted per tool. `request_interview` receives a name, an email, and
a free-text message; none of those appear here.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

# The only argument keys that may ever appear in a trace, per tool.
TRACE_SAFE_ARGS: dict[str, tuple[str, ...]] = {
    "get_project": ("project_id",),
    "request_interview": ("window_id",),
}


@dataclass
class ToolCall:
    name: str
    arguments: dict[str, Any]
    latency_ms: int
    ok: bool
    error_class: str | None = None


@dataclass
class Trace:
    objective: str = (
        "Determine whether a thirty-minute conversation between Josh Ballard and "
        "Naive is warranted, using only approved evidence."
    )
    classification: str | None = None
    calls: list[ToolCall] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)
    actions: list[dict[str, str]] = field(default_factory=list)
    verification: str | None = None
    rejected_claims: list[str] = field(default_factory=list)
    _started: float = field(default_factory=time.perf_counter)

    # --- recording ----------------------------------------------------------

    def note_evidence(self, record_ids: list[str]) -> None:
        for record_id in record_ids:
            if record_id not in self.evidence_ids:
                self.evidence_ids.append(record_id)

    def note_action(self, name: str, reference: str) -> None:
        self.actions.append(
            {"action": name, "reference": reference, "status": "pending_human_approval"}
        )

    def record_call(
        self,
        name: str,
        arguments: dict[str, Any],
        latency_ms: int,
        ok: bool,
        error_class: str | None = None,
    ) -> None:
        allowed = TRACE_SAFE_ARGS.get(name, ())
        self.calls.append(
            ToolCall(
                name=name,
                arguments={k: v for k, v in arguments.items() if k in allowed},
                latency_ms=latency_ms,
                ok=ok,
                error_class=error_class,
            )
        )

    # --- output -------------------------------------------------------------

    def snapshot(self) -> dict[str, Any]:
        return {
            "objective": self.objective,
            "classification": self.classification,
            "tools_invoked": [
                {
                    "tool": c.name,
                    "arguments": c.arguments,
                    "latency_ms": c.latency_ms,
                    "ok": c.ok,
                    "error_class": c.error_class,
                }
                for c in self.calls
            ],
            "evidence_used": list(self.evidence_ids),
            "actions_taken": list(self.actions),
            "verification": self.verification,
            "claims_rejected": list(self.rejected_claims),
            "elapsed_ms": int((time.perf_counter() - self._started) * 1000),
            "note": (
                "Everything above is server-recorded fact about this turn. No model "
                "reasoning tokens are shown here, because none are collected."
            ),
        }
