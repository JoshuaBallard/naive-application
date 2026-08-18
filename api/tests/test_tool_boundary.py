"""The tool surface is a security boundary, so it is pinned.

If a change makes one of these fail, the change is either a mistake or a decision
someone needs to sign off on. There is no third case.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from app.agent.trace import Trace
from app.evidence.store import EvidenceStore
from app.tools.registry import ToolError, build_registry

# The complete, intended tool surface. Adding a name here is a deliberate act.
EXPECTED_TOOLS = frozenset(
    {
        "get_agent_trace",
        "get_availability",
        "get_known_gaps",
        "get_naive_alignment",
        "get_profile",
        "get_project",
        "get_public_links",
        "get_role_fit",
        "request_interview",
    }
)

# Argument names that would turn a narrow tool into a general-purpose one.
FORBIDDEN_ARG_NAMES = {
    "path", "file", "filename", "dir", "directory", "url", "uri", "host", "hostname",
    "command", "cmd", "shell", "query", "sql", "code", "script", "endpoint", "key",
    "token", "secret", "env",
}


class RefusingSink:
    """An interview sink that fails loudly if a read-only test writes anything."""

    def record(self, **kwargs: Any) -> str:  # noqa: ANN401
        raise AssertionError("a read-only test attempted to write an interview request")


@pytest.fixture
def registry():
    store = EvidenceStore.load()
    return build_registry(store, interview_sink=RefusingSink(), trace=Trace())


def test_tool_surface_is_exactly_nine_named_tools(registry) -> None:
    assert set(registry.names) == EXPECTED_TOOLS
    assert len(registry.names) == 9


def test_no_tool_accepts_a_free_form_resource_argument(registry) -> None:
    for schema in registry.schemas():
        for arg in schema["input_schema"].get("properties", {}):
            assert arg.lower() not in FORBIDDEN_ARG_NAMES, (
                f"{schema['name']} exposes an argument named {arg!r}, which is the "
                "shape of a general-purpose tool"
            )


def test_every_tool_forbids_unexpected_arguments(registry) -> None:
    for schema in registry.schemas():
        assert schema["input_schema"]["additionalProperties"] is False, schema["name"]


def test_string_arguments_are_enums_or_bounded(registry) -> None:
    """A free string argument is a place to hide an instruction. Every one is capped."""
    for schema in registry.schemas():
        for name, spec in schema["input_schema"].get("properties", {}).items():
            if spec.get("type") == "string":
                assert "enum" in spec or "maxLength" in spec, f"{schema['name']}.{name}"


def test_project_lookup_is_an_enum_not_a_string(registry) -> None:
    project = next(s for s in registry.schemas() if s["name"] == "get_project")
    enum = project["input_schema"]["properties"]["project_id"]["enum"]

    assert enum, "the enum is empty, so no project is reachable"
    assert all(pid.startswith("proj.") for pid in enum)


def test_unknown_project_id_is_refused(registry) -> None:
    with pytest.raises(ToolError):
        registry.call("get_project", {"project_id": "proj.does-not-exist"})


def test_unknown_tool_name_is_refused(registry) -> None:
    with pytest.raises(ToolError):
        registry.call("read_file", {"path": "/etc/passwd"})


def test_reads_do_not_mutate_the_store(registry) -> None:
    first = registry.call("get_availability", {})
    first["records"][0]["windows"].append({"id": "injected", "label": "x", "timezone": "y"})
    second = registry.call("get_availability", {})

    assert len(second["records"][0]["windows"]) < len(first["records"][0]["windows"])


def test_trace_never_carries_personal_arguments() -> None:
    trace = Trace()
    trace.record_call(
        "request_interview",
        {"name": "Sean", "email": "sean@example.com", "window_id": "thu-midday-et",
         "message": "call me on 513-555-0142"},
        latency_ms=3,
        ok=True,
    )

    rendered = json.dumps(trace.snapshot())

    assert "sean@example.com" not in rendered
    assert "Sean" not in rendered
    assert "513-555-0142" not in rendered
    assert "thu-midday-et" in rendered


def test_compiled_artifact_contains_no_unapproved_records() -> None:
    """Belt and braces: the shipped artifact is checked directly, not just the builder."""
    artifact = json.loads(
        (Path(__file__).resolve().parents[2] / "build" / "evidence.compiled.json").read_text()
    )
    for record in artifact["records"].values():
        assert record["approved"] is True, record["id"]
