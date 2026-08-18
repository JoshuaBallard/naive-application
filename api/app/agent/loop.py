"""The agent loop.

A manual loop rather than the SDK's beta tool runner, for three reasons worth stating
because someone will ask. Per-call latency has to land in the viewer-visible trace. The
verify → repair → fail-closed sequence sits outside what the runner's hooks expose. And
the one component load-bearing for the security story should not depend on a beta.

There is no token streaming. The answer is a forced tool call, so there is no prose to
stream — what the viewer watches instead is the tool calls landing in the trace, which
is the more honest progress indicator anyway.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import anthropic

from app.agent import rubric, verifier
from app.agent.config import CONFIG, AgentConfig
from app.agent.prompt import (
    REPAIR_TEMPLATE,
    SYSTEM_PROMPT,
    UNTRUSTED_INPUT_TEMPLATE,
    build_evidence_index,
)
from app.agent.schemas import SUBMIT_ANSWER_TOOL, Answer
from app.agent.trace import Trace
from app.evidence.lint import Rule
from app.evidence.store import EvidenceStore
from app.tools.registry import InterviewSink, ToolError, build_registry

# Static text, which is what makes it provably safe: a message assembled from an
# answer that just failed the privacy filter could carry the same problem through.
#
# The privacy case gets a real answer rather than an error, because a viewer probing the
# boundary is the most likely adversarial interaction this application will have, and an
# error message would be the worst possible thing to show them at that moment.
FAIL_CLOSED_MESSAGES = {
    "privacy_violation": (
        "That asks for something outside this application's evidence boundary — private "
        "infrastructure, personal or family life, or a current employer's systems. I do "
        "not have access to any of it. There is no filesystem tool, no shell, no network "
        "access, no repository access, and no calendar; that is the design, not a "
        "restriction I am choosing to apply to you.\n\n"
        "What I do have is a curated set of public evidence records, and all of them are "
        "browsable — nothing I know is hidden from you. Ask me about the work instead."
    ),
    "default": (
        "I could not produce an answer that passed verification inside my evidence "
        "boundary, so I discarded it rather than show you something unverified. That is "
        "the intended behaviour, not a crash. Try rephrasing, or browse the evidence "
        "directly — it is all public."
    ),
}
FAIL_CLOSED_MESSAGE = FAIL_CLOSED_MESSAGES["default"]


@dataclass
class AgentResult:
    answer: dict[str, Any]
    trace: dict[str, Any]
    verification: str
    usage: dict[str, int]
    failed_closed: bool = False


class QuestionTooLong(ValueError):
    pass


class AgentRunner:
    def __init__(
        self,
        store: EvidenceStore,
        rules: tuple[Rule, ...],
        *,
        client: anthropic.Anthropic | None = None,
        config: AgentConfig = CONFIG,
    ) -> None:
        self._store = store
        self._rules = rules
        self._config = config
        self._client = client or anthropic.Anthropic()

        # Built once and cached in the request prefix. Stable across every turn, which
        # is what makes it nearly free after the first call.
        self._index = build_evidence_index(store)

        # Computed once. The model reports these; it does not get to choose them.
        assessment = rubric.evaluate(
            store.by_type("role_requirement"),
            store.by_type("gap"),
            {r["id"]: r for r in store.all_records()},
        )
        self._verdict = assessment.verdict
        self._confidence = assessment.confidence

    # -----------------------------------------------------------------------

    def run(self, question: str, *, interview_sink: InterviewSink) -> AgentResult:
        if len(question) > self._config.max_question_chars:
            raise QuestionTooLong(
                f"question is {len(question)} characters; the limit is "
                f"{self._config.max_question_chars}"
            )

        trace = Trace()
        registry = build_registry(self._store, interview_sink=interview_sink, trace=trace)
        tools = registry.schemas() + [SUBMIT_ANSWER_TOOL]

        messages: list[dict[str, Any]] = [
            {
                "role": "user",
                "content": UNTRUSTED_INPUT_TEMPLATE.format(question=question.strip()),
            }
        ]

        usage = {"input_tokens": 0, "output_tokens": 0, "cache_read_input_tokens": 0}
        tool_calls = 0
        repairs = 0

        for _ in range(self._config.max_iterations):
            response = self._client.messages.create(
                model=self._config.model,
                max_tokens=self._config.max_tokens,
                thinking={"type": "adaptive"},
                output_config={"effort": self._config.effort},
                # Stable prefix: tools, then system. The evidence-bearing tool schemas
                # and the prompt do not change between turns, so they cache.
                system=[
                    {"type": "text", "text": SYSTEM_PROMPT},
                    {
                        "type": "text",
                        "text": self._index,
                        "cache_control": {"type": "ephemeral"},
                    },
                ],
                tools=tools,
                messages=messages,
            )

            for key in usage:
                usage[key] += getattr(response.usage, key, 0) or 0

            if response.stop_reason == "refusal":
                return self._fail_closed(trace, usage, "model_refusal")

            messages.append({"role": "assistant", "content": response.content})

            submitted, submission_id = _find_submission(response)
            if submitted is not None and submission_id is not None:
                result = self._check(submitted, trace)

                if result.ok and result.answer is not None:
                    trace.verification = "passed" if not repairs else "passed_after_repair"
                    return AgentResult(
                        answer=verifier.to_public_dict(result.answer, self._store),
                        trace=trace.snapshot(),
                        verification=trace.verification,
                        usage=usage,
                    )

                if result.fatal:
                    return self._fail_closed(trace, usage, "privacy_violation")

                if repairs < self._config.repair_attempts:
                    repairs += 1
                    trace.rejected_claims.extend(result.rejected_claims)
                    # A tool_result, not a user message: submit_answer was a tool
                    # call, and every tool_use must be answered by a tool_result in the
                    # very next message or the API rejects the conversation.
                    messages.append(
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "tool_result",
                                    "tool_use_id": submission_id,
                                    "is_error": True,
                                    "content": REPAIR_TEMPLATE.format(
                                        violations=result.as_prompt()
                                    ),
                                }
                            ],
                        }
                    )
                    continue

                # Repair already spent. Salvage a weaker, true answer if the remaining
                # problems are about evidence rather than privacy.
                salvaged, changed = verifier.downgrade(submitted, self._store)
                recheck = self._check(salvaged, trace)
                if recheck.ok and recheck.answer is not None:
                    trace.verification = "passed_after_downgrade"
                    trace.rejected_claims.extend(changed)
                    return AgentResult(
                        answer=verifier.to_public_dict(recheck.answer, self._store),
                        trace=trace.snapshot(),
                        verification=trace.verification,
                        usage=usage,
                    )
                return self._fail_closed(trace, usage, "verification_failed")

            if response.stop_reason != "tool_use":
                # The model answered in prose instead of calling submit_answer. There is
                # no path for free text to reach a viewer, so this is a dead end.
                return self._fail_closed(trace, usage, "no_structured_answer")

            results, tool_calls = self._run_tools(response, registry, trace, tool_calls)
            if tool_calls > self._config.max_tool_calls:
                return self._fail_closed(trace, usage, "tool_call_limit")

            # Every tool_result for one assistant turn goes back in a single user
            # message. Splitting them teaches the model to stop calling tools in parallel.
            messages.append({"role": "user", "content": results})

        return self._fail_closed(trace, usage, "iteration_limit")

    # -----------------------------------------------------------------------

    def _check(self, answer: Answer, trace: Trace) -> verifier.VerificationResult:
        trace.classification = answer.classification
        return verifier.verify(
            answer,
            store=self._store,
            rules=self._rules,
            computed_verdict=self._verdict,
            computed_confidence=self._confidence,
        )

    def _run_tools(
        self,
        response: Any,
        registry: Any,
        trace: Trace,
        tool_calls: int,
    ) -> tuple[list[dict[str, Any]], int]:
        results: list[dict[str, Any]] = []

        for block in response.content:
            if getattr(block, "type", None) != "tool_use":
                continue

            tool_calls += 1
            started = time.perf_counter()
            try:
                payload = registry.call(block.name, dict(block.input))
                ok, error_class, content = True, None, _dump(payload)
            except ToolError as exc:
                ok, error_class, content = False, "ToolError", str(exc)
            except Exception as exc:  # noqa: BLE001 - the model must not see a traceback
                ok, error_class, content = False, type(exc).__name__, "tool failed"

            trace.record_call(
                block.name,
                dict(block.input),
                latency_ms=int((time.perf_counter() - started) * 1000),
                ok=ok,
                error_class=error_class,
            )
            results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": content,
                    **({"is_error": True} if not ok else {}),
                }
            )

        return results, tool_calls

    def _fail_closed(self, trace: Trace, usage: dict[str, int], reason: str) -> AgentResult:
        trace.verification = f"failed_closed:{reason}"
        return AgentResult(
            answer={
                "answer": FAIL_CLOSED_MESSAGES.get(reason, FAIL_CLOSED_MESSAGES["default"]),
                "classification": "PRIVATE_PROBE" if reason == "privacy_violation" else "IN_SCOPE",
                "verdict": "not_applicable",
                "confidence": "low",
                "confidence_basis": f"No answer survived verification ({reason}).",
                "claims": [],
                "gaps_acknowledged": [],
            },
            trace=trace.snapshot(),
            verification=trace.verification,
            usage=usage,
            failed_closed=True,
        )


def _find_submission(response: Any) -> tuple[Answer | None, str | None]:
    """Return the submitted answer and the id of the tool_use that carried it.

    The id matters: a rejection has to come back as a tool_result addressed to this
    exact call, or the conversation is malformed.
    """
    for block in response.content:
        if getattr(block, "type", None) == "tool_use" and block.name == "submit_answer":
            return Answer.model_validate(dict(block.input)), block.id
    return None, None


def _dump(payload: dict[str, Any]) -> str:
    import json

    return json.dumps(payload, separators=(",", ":"), default=str)
