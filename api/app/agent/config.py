"""Runtime configuration. Every value is overridable by environment variable."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ[name])
    except (KeyError, ValueError):
        return default


@dataclass(frozen=True)
class AgentConfig:
    # Sonnet rather than Opus, deliberately. The server-side verifier is what makes
    # an answer trustworthy — a weaker model that fabricates gets caught and repaired
    # rather than believed. That turns model choice into a cost decision instead of a
    # safety one, which is the point of putting the guarantee in code.
    model: str = os.environ.get("AGENT_MODEL", "claude-sonnet-5")

    # Retrieval across ~forty small records plus one structured composition. Not a
    # reasoning problem. Raise with AGENT_EFFORT if answers get shallow.
    effort: str = os.environ.get("AGENT_EFFORT", "medium")

    max_tokens: int = _int("AGENT_MAX_TOKENS", 16000)

    # A turn that has not answered after this many model calls is looping.
    max_iterations: int = _int("AGENT_MAX_ITERATIONS", 6)

    # Evidence tools are cheap, but an unbounded caller is still an unbounded caller.
    max_tool_calls: int = _int("AGENT_MAX_TOOL_CALLS", 12)

    max_question_chars: int = _int("AGENT_MAX_QUESTION_CHARS", 1200)

    # One repair attempt. Two would be arguing with the verifier.
    repair_attempts: int = _int("AGENT_REPAIR_ATTEMPTS", 2)

    # A viewer gets a fixed number of questions, and is told so up front. This is a
    # cost control, and it is also the better interaction: a person with eight
    # questions asks better ones than a person with unlimited follow-ups. It mirrors
    # the thing being applied for — you do not get unlimited follow-ups in an
    # interview either.
    questions_per_session: int = _int("AGENT_QUESTIONS_PER_SESSION", 8)


CONFIG = AgentConfig()
