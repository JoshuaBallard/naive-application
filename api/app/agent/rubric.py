"""The verdict is computed, not narrated.

The model's job is to explain this result in plain English. It does not get to pick
it. A language model asked "is this candidate a fit" will drift toward yes, and the
one thing this application cannot afford is a flattering answer nobody can check.

Two axes, reported separately and never averaged together:

  EVIDENCE FIT    what the record supports about the work
  PRACTICAL FIT   constraints that can end the conversation regardless

Folding a hard geographic constraint into a skills score is dishonest in both
directions: it either drags a real assessment down, or it hides a blocker inside a
soft-sounding number.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

Verdict = Literal[
    "strong_fit",
    "interesting_partial_fit",
    "insufficient_evidence",
    "significant_gap",
    "probably_not_a_fit",
]

Confidence = Literal["low", "medium", "medium_high", "high"]

# What each status is worth against a requirement. INFERRED is deliberately closer to
# UNKNOWN than to PARTIAL: a reasonable inference is not evidence.
STATUS_WEIGHT: dict[str, float] = {
    "SUPPORTED": 1.0,
    "PARTIAL": 0.5,
    "INFERRED": 0.3,
    "UNKNOWN": 0.0,
    "GAP": 0.0,
}

MUST_HAVE_WEIGHT = 1.0
NICE_TO_HAVE_WEIGHT = 0.35


@dataclass(frozen=True)
class PracticalConstraint:
    requirement: str
    status: str
    reasoning: str
    blocking: bool


@dataclass(frozen=True)
class RubricResult:
    verdict: Verdict
    evidence_score: float
    confidence: Confidence
    confidence_basis: str
    must_have_counts: dict[str, int]
    nice_to_have_counts: dict[str, int]
    practical: list[PracticalConstraint] = field(default_factory=list)
    unknown_must_haves: list[str] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)

    @property
    def practical_summary(self) -> str:
        if any(c.blocking for c in self.practical):
            return "unresolved — potentially blocking"
        if any(c.status == "UNKNOWN" for c in self.practical):
            return "unresolved"
        return "no known blockers"

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "evidence_score": round(self.evidence_score, 3),
            "confidence": self.confidence,
            "confidence_basis": self.confidence_basis,
            "practical_fit": self.practical_summary,
            "practical_constraints": [
                {
                    "requirement": c.requirement,
                    "status": c.status,
                    "reasoning": c.reasoning,
                    "blocking": c.blocking,
                }
                for c in self.practical
            ],
            "must_have_counts": self.must_have_counts,
            "nice_to_have_counts": self.nice_to_have_counts,
            "unknown_must_haves": self.unknown_must_haves,
            "gaps": self.gaps,
        }


def _counts(records: list[dict[str, Any]]) -> dict[str, int]:
    tally = {status: 0 for status in STATUS_WEIGHT}
    for record in records:
        tally[record["status"]] += 1
    return tally


def evaluate(
    requirements: list[dict[str, Any]],
    gaps: list[dict[str, Any]],
    records_by_id: dict[str, dict[str, Any]] | None = None,
) -> RubricResult:
    must = [r for r in requirements if r["category"] == "must_have"]
    nice = [r for r in requirements if r["category"] == "nice_to_have"]
    practical_records = [r for r in requirements if r["category"] == "practical"]

    if not must:
        raise ValueError("cannot evaluate fit with no must_have requirements")

    earned = sum(STATUS_WEIGHT[r["status"]] * MUST_HAVE_WEIGHT for r in must)
    available = len(must) * MUST_HAVE_WEIGHT

    earned += sum(STATUS_WEIGHT[r["status"]] * NICE_TO_HAVE_WEIGHT for r in nice)
    available += len(nice) * NICE_TO_HAVE_WEIGHT

    score = earned / available

    unknown_must_haves = [r["requirement"] for r in must if r["status"] == "UNKNOWN"]

    # An evidence problem is not a fit problem. If too much of the must-have list is
    # simply unknown, the honest verdict is that we cannot tell yet.
    if len(unknown_must_haves) >= max(2, len(must) // 3):
        verdict: Verdict = "insufficient_evidence"
    elif score >= 0.80:
        verdict = "strong_fit"
    elif score >= 0.55:
        verdict = "interesting_partial_fit"
    elif score >= 0.35:
        verdict = "significant_gap"
    else:
        verdict = "probably_not_a_fit"

    practical = [
        PracticalConstraint(
            requirement=r["requirement"],
            status=r["status"],
            reasoning=r["reasoning"],
            blocking=r["status"] in ("GAP", "UNKNOWN"),
        )
        for r in practical_records
    ]

    confidence, basis = _confidence(must, nice, unknown_must_haves, records_by_id or {})

    return RubricResult(
        verdict=verdict,
        evidence_score=score,
        confidence=confidence,
        confidence_basis=basis,
        must_have_counts=_counts(must),
        nice_to_have_counts=_counts(nice),
        practical=practical,
        unknown_must_haves=unknown_must_haves,
        gaps=[g["gap"] for g in gaps],
    )


def _confidence(
    must: list[dict[str, Any]],
    nice: list[dict[str, Any]],
    unknown_must_haves: list[str],
    records_by_id: dict[str, dict[str, Any]],
) -> tuple[Confidence, str]:
    """Confidence is about how well-evidenced the answer is, not how good it is.

    A confident "probably not a fit" is a perfectly good output.

    Two inputs. Coverage: how many requirements point at a record at all. Verifiability:
    how much of that evidence a stranger could check without taking Josh's word for it.
    A resume is not verifiable and a commit log is, and an assessment resting mostly on
    the former has no business calling itself high confidence.
    """
    cited = sum(1 for r in must + nice if r.get("evidence_ids"))
    total = len(must) + len(nice)
    coverage = cited / total if total else 0.0

    referenced: set[str] = set()
    for requirement in must + nice:
        referenced.update(requirement.get("evidence_ids") or [])

    checkable = [
        rid
        for rid in referenced
        if (records_by_id.get(rid) or {}).get("source_class") == "public_artifact"
    ]
    verifiability = len(checkable) / len(referenced) if referenced else 0.0

    unknowns = len(unknown_must_haves)
    detail = (
        f"{cited} of {total} requirements map to a specific evidence record, and "
        f"{len(checkable)} of {len(referenced)} cited records are independently "
        f"checkable rather than self-reported."
    )

    if coverage < 0.5:
        return "low", (
            f"Most requirements ({total - cited} of {total}) have no supporting record. "
            "Treat this as a starting point, not an assessment."
        )
    if unknowns > 1 or coverage < 0.7:
        return "medium", f"{detail} {unknowns} must-have requirements are unresolved."

    # Ceiling. Without a majority of independently checkable evidence, the honest top of
    # the range is medium-high, however complete the mapping looks.
    if verifiability < 0.5:
        return "medium_high", (
            f"{detail} Most of the record is self-reported work history, which caps how "
            "confident this assessment can honestly be."
        )
    if coverage >= 0.85 and unknowns == 0:
        return "high", f"{detail} No must-have is unresolved."
    return "medium_high", f"{detail} {unknowns} must-have requirement is unresolved."
