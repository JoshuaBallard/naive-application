"""The verdict is computed, so it can be tested. That is the point of computing it.

A model asked "is this candidate a fit" drifts toward yes. These tests are what stop
the answer from drifting with it.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.agent import rubric
from app.evidence.store import EvidenceStore


def req(
    rid: str,
    category: str,
    status: str,
    evidence: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "id": rid,
        "requirement": rid,
        "category": category,
        "status": status,
        "reasoning": "fixture",
        "evidence_ids": evidence if evidence is not None else ["proj.x"],
    }


PUBLIC = {"proj.x": {"id": "proj.x", "source_class": "public_artifact"}}
PRIVATE = {"proj.x": {"id": "proj.x", "source_class": "self_authored"}}


def test_all_supported_is_a_strong_fit() -> None:
    result = rubric.evaluate([req(f"r{i}", "must_have", "SUPPORTED") for i in range(6)], [], PUBLIC)
    assert result.verdict == "strong_fit"


def test_all_gaps_is_probably_not_a_fit() -> None:
    result = rubric.evaluate(
        [req(f"r{i}", "must_have", "GAP", []) for i in range(6)], [], PUBLIC
    )
    assert result.verdict == "probably_not_a_fit"


def test_half_the_must_haves_missing_is_a_significant_gap() -> None:
    requirements = [req(f"r{i}", "must_have", "SUPPORTED") for i in range(3)]
    requirements += [req(f"g{i}", "must_have", "GAP", []) for i in range(3)]

    result = rubric.evaluate(requirements, [], PUBLIC)

    assert result.verdict == "significant_gap"
    assert result.evidence_score == 0.5


def test_widespread_unknowns_report_insufficient_evidence_not_a_bad_fit() -> None:
    """Not knowing is a different failure from not fitting, and it reads differently."""
    requirements = [req(f"r{i}", "must_have", "SUPPORTED") for i in range(3)]
    requirements += [req(f"u{i}", "must_have", "UNKNOWN", []) for i in range(3)]

    result = rubric.evaluate(requirements, [], PUBLIC)

    assert result.verdict == "insufficient_evidence"
    assert len(result.unknown_must_haves) == 3


def test_nice_to_haves_cannot_rescue_failed_must_haves() -> None:
    requirements = [req(f"r{i}", "must_have", "GAP", []) for i in range(6)]
    requirements += [req(f"n{i}", "nice_to_have", "SUPPORTED") for i in range(8)]

    assert rubric.evaluate(requirements, [], PUBLIC).verdict == "probably_not_a_fit"


def test_practical_constraints_never_move_the_evidence_score() -> None:
    """A blocking constraint is reported beside the verdict, never folded into it."""
    base = [req(f"r{i}", "must_have", "SUPPORTED") for i in range(6)]

    without = rubric.evaluate(base, [], PUBLIC)
    with_block = rubric.evaluate(base + [req("loc", "practical", "GAP", [])], [], PUBLIC)

    assert with_block.evidence_score == without.evidence_score
    assert with_block.verdict == without.verdict
    assert with_block.practical_summary == "unresolved — potentially blocking"
    assert without.practical_summary == "no known blockers"


def test_self_reported_evidence_caps_confidence() -> None:
    """Complete mapping over unverifiable evidence is not high confidence."""
    requirements = [req(f"r{i}", "must_have", "SUPPORTED") for i in range(6)]

    assert rubric.evaluate(requirements, [], PUBLIC).confidence == "high"
    assert rubric.evaluate(requirements, [], PRIVATE).confidence == "medium_high"


def test_evaluate_refuses_with_no_must_haves() -> None:
    with pytest.raises(ValueError, match="no must_have"):
        rubric.evaluate([req("n", "nice_to_have", "SUPPORTED")], [], PUBLIC)


# --- the real evidence ------------------------------------------------------


@pytest.fixture
def live():
    store = EvidenceStore.load()
    return rubric.evaluate(
        store.by_type("role_requirement"),
        store.by_type("gap"),
        {r["id"]: r for r in store.all_records()},
    )


def test_live_verdict_is_an_honest_partial_fit(live) -> None:
    """If this ever reads strong_fit, someone has been grading generously."""
    assert live.verdict == "interesting_partial_fit"
    assert 0.60 <= live.evidence_score <= 0.78


def test_live_confidence_is_capped_by_self_reporting(live) -> None:
    assert live.confidence == "medium_high"
    assert "self-reported" in live.confidence_basis


def test_live_location_is_reported_as_blocking(live) -> None:
    assert live.practical_summary == "unresolved — potentially blocking"
    assert any("San Francisco" in c.requirement for c in live.practical)


def test_live_gaps_are_not_empty(live) -> None:
    """An application with no documented gaps is not an honest application."""
    assert len(live.gaps) >= 4
