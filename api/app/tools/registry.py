"""The tool registry.

Nine tools. All pure reads over one in-memory JSON object, except `request_interview`,
which is the only write in the application and the only action with a consequence.

What is deliberately absent, and stays absent:

  no filesystem      no shell           no HTTP fetch      no GitHub API
  no SQL             no env access      no calendar        no email send

and no tool that accepts a free-form path, URL, hostname, or query string. Note that
`get_project` takes an **enum** built from the compiled evidence, not a string. There
is no argument a viewer can craft that reaches something unlisted, because unlisted
values fail schema validation before a handler ever runs.

`evaluations/test_tool_boundary.py` snapshots this file's surface. Adding a tenth tool
requires an intentional diff that a human has to approve.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Protocol

from app.evidence.store import EvidenceStore
from app.agent import rubric


class InterviewSink(Protocol):
    """Where an interview request goes. Never a calendar."""

    def record(self, *, name: str, email: str, window_id: str, message: str | None) -> str: ...


class ToolError(RuntimeError):
    """Raised for a call the schema allowed but the data cannot satisfy."""


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    input_schema: dict[str, Any]
    handler: Callable[..., dict[str, Any]]


class Registry:
    def __init__(self, tools: list[Tool]) -> None:
        self._tools = {t.name: t for t in tools}

    @property
    def names(self) -> list[str]:
        return sorted(self._tools)

    def schemas(self) -> list[dict[str, Any]]:
        """Anthropic tool definitions. This is exactly what the model can see."""
        return [
            {"name": t.name, "description": t.description, "input_schema": t.input_schema}
            for t in self._tools.values()
        ]

    def call(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        tool = self._tools.get(name)
        if tool is None:
            # Unreachable through the API, which only offers the schemas above. Kept
            # because "unreachable" is a claim, and this is what makes it true.
            raise ToolError(f"no such tool: {name}")
        return tool.handler(**arguments)


NO_ARGS: dict[str, Any] = {"type": "object", "properties": {}, "additionalProperties": False}


def build_registry(
    store: EvidenceStore,
    *,
    interview_sink: InterviewSink,
    trace: Any,
) -> Registry:
    """Build the registry for one request.

    Constructed per request so `get_project`'s enum comes from the artifact actually
    loaded, and so `get_agent_trace` can see this turn and no other.
    """

    project_ids = sorted(r["id"] for r in store.by_type("project"))
    window_ids = sorted(
        w["id"] for record in store.by_type("availability") for w in record["windows"]
    )

    def _cite(record_ids: list[str]) -> None:
        trace.note_evidence(record_ids)

    # --- reads ------------------------------------------------------------

    def get_profile() -> dict[str, Any]:
        records = store.by_type("profile") + store.by_type("work_history")
        _cite([r["id"] for r in records])
        return {"records": records}

    def get_role_fit() -> dict[str, Any]:
        requirements = store.by_type("role_requirement")
        gaps = store.by_type("gap")
        _cite([r["id"] for r in requirements + gaps])
        result = rubric.evaluate(
            requirements, gaps, {r["id"]: r for r in store.all_records()}
        )
        return {
            "computed_verdict": result.to_dict(),
            "requirements": requirements,
            "note": (
                "The verdict above was computed from the requirement records by a "
                "deterministic rubric on the server. Report it. Do not recalculate it, "
                "soften it, or substitute your own."
            ),
        }

    def get_project(project_id: str) -> dict[str, Any]:
        record = store.get(project_id)
        if record is None:
            raise ToolError(f"no approved project record: {project_id}")
        _cite([project_id])
        return {"record": record}

    def get_public_links() -> dict[str, Any]:
        records = store.by_type("link")
        _cite([r["id"] for r in records])
        return {"records": records}

    def get_known_gaps() -> dict[str, Any]:
        records = store.by_type("gap")
        _cite([r["id"] for r in records])
        return {
            "records": records,
            "note": (
                "These are gaps Josh wrote down himself. Report them plainly. Do not "
                "pair every gap with a reassurance."
            ),
        }

    def get_naive_alignment() -> dict[str, Any]:
        records = store.by_type("alignment") + store.by_type("belief")
        _cite([r["id"] for r in records])
        return {"records": records}

    def get_availability() -> dict[str, Any]:
        records = store.by_type("availability")
        _cite([r["id"] for r in records])
        return {
            "records": records,
            "note": (
                "Static windows Josh wrote down. This application has no calendar "
                "access and cannot tell whether any of them are actually free."
            ),
        }

    def get_agent_trace() -> dict[str, Any]:
        return trace.snapshot()

    # --- the only write ---------------------------------------------------

    def request_interview(
        name: str, email: str, window_id: str, message: str | None = None
    ) -> dict[str, Any]:
        reference = interview_sink.record(
            name=name, email=email, window_id=window_id, message=message
        )
        trace.note_action("request_interview", reference)
        return {
            "status": "pending_human_approval",
            "reference": reference,
            "what_happened": (
                "The request was recorded for Josh to read. Nothing was sent to a "
                "calendar, no invitation was created, and no email was sent to anyone "
                "but Josh. He confirms by hand or not at all."
            ),
        }

    return Registry(
        [
            Tool(
                name="get_profile",
                description=(
                    "Josh's sanitized professional summary and resume-level work history. "
                    "Use this first for any question about who he is or what he has done."
                ),
                input_schema=NO_ARGS,
                handler=get_profile,
            ),
            Tool(
                name="get_role_fit",
                description=(
                    "Every Naive MTS requirement mapped to evidence, plus the verdict "
                    "computed by the server-side rubric. Use this for any question about "
                    "fit, suitability, strengths, or whether a conversation is warranted."
                ),
                input_schema=NO_ARGS,
                handler=get_role_fit,
            ),
            Tool(
                name="get_project",
                description=(
                    "One approved project record: what the problem was, what Josh built, "
                    "what he learned, what is publicly checkable, and what its known "
                    "limitations are."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "project_id": {
                            "type": "string",
                            "enum": project_ids,
                            "description": "Must be one of the approved project ids.",
                        }
                    },
                    "required": ["project_id"],
                    "additionalProperties": False,
                },
                handler=get_project,
            ),
            Tool(
                name="get_public_links",
                description="The URLs Josh approved for publication. There are no others.",
                input_schema=NO_ARGS,
                handler=get_public_links,
            ),
            Tool(
                name="get_known_gaps",
                description=(
                    "Gaps Josh documented about himself, against this role. Use this "
                    "whenever someone asks what he has not done, what is weak, or what "
                    "the risks of hiring him are."
                ),
                input_schema=NO_ARGS,
                handler=get_known_gaps,
            ),
            Tool(
                name="get_naive_alignment",
                description=(
                    "Why this company and this role interest Josh, and what he believes "
                    "about agent systems, human review, and governance."
                ),
                input_schema=NO_ARGS,
                handler=get_naive_alignment,
            ),
            Tool(
                name="get_availability",
                description=(
                    "Interview windows Josh approved in advance. Static text, not calendar "
                    "data. Contains no events, no attendees, and no free/busy information."
                ),
                input_schema=NO_ARGS,
                handler=get_availability,
            ),
            Tool(
                name="request_interview",
                description=(
                    "Record a request for a conversation. This does NOT book anything, "
                    "send an invitation, or touch a calendar. It writes a row for Josh to "
                    "approve by hand. Only call this when the viewer has given a name, an "
                    "email, and chosen one of the approved windows."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "minLength": 1, "maxLength": 120},
                        "email": {"type": "string", "minLength": 3, "maxLength": 200},
                        "window_id": {
                            "type": "string",
                            "enum": window_ids,
                            "description": "One of the approved availability window ids.",
                        },
                        "message": {"type": "string", "maxLength": 2000},
                    },
                    "required": ["name", "email", "window_id"],
                    "additionalProperties": False,
                },
                handler=request_interview,
            ),
            Tool(
                name="get_agent_trace",
                description=(
                    "What this turn has done so far: tools called, evidence records read, "
                    "and the computed verdict. Safe to show the viewer. Contains no "
                    "reasoning tokens and no hidden state, because there is none."
                ),
                input_schema=NO_ARGS,
                handler=get_agent_trace,
            ),
        ]
    )
