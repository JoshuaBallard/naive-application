"""Server-side verification of a submitted answer.

The system prompt asks the model to be honest. This module is what makes it true. A
prompt is a preference; this runs on every answer, deterministically, before anything
reaches a browser.

One subtlety worth stating. When verification fails, the violations are sent back to
the model so it can repair the answer. Violations therefore never quote the offending
text — a privacy finding that echoed the string it caught would re-inject the leak into
the very context we are trying to keep it out of. Findings arrive masked, and they stay
masked.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.evidence.lint import Rule, blocking, scan
from app.evidence.store import EvidenceStore

from .schemas import Answer, Claim


@dataclass(frozen=True)
class Violation:
    code: str
    detail: str

    # Fatal: the answer is destroyed, no repair attempted. Privacy only.
    fatal: bool = False

    # Soft: worth one repair, never worth withholding an answer over. A missing
    # citation makes an answer weaker; refusing to show it makes the application
    # useless. Only the privacy rule gets to be absolute.
    soft: bool = False

    def __str__(self) -> str:
        return f"- [{self.code}] {self.detail}"


@dataclass
class VerificationResult:
    answer: Answer | None
    violations: list[Violation] = field(default_factory=list)
    downgraded: list[str] = field(default_factory=list)
    rejected_claims: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.violations

    @property
    def acceptable(self) -> bool:
        """Good enough to show after a repair has already been spent.

        Everything hard has been fixed or the answer has been downgraded; what is left
        is cosmetic. Showing a weaker true answer beats showing nothing.
        """
        return all(v.soft for v in self.violations)

    @property
    def fatal(self) -> bool:
        return any(v.fatal for v in self.violations)

    @property
    def status(self) -> str:
        if self.ok:
            return "passed"
        return "failed_closed" if self.fatal else "rejected"

    def as_prompt(self) -> str:
        return "\n".join(str(v) for v in self.violations)


def verify(
    answer: Answer,
    *,
    store: EvidenceStore,
    rules: tuple[Rule, ...],
    computed_verdict: str,
    computed_confidence: str = "",
) -> VerificationResult:
    """Check a submitted answer against the evidence it claims to rest on."""
    result = VerificationResult(answer=answer)
    known = store.ids()

    if not answer.answer.strip():
        result.violations.append(Violation("empty-answer", "The answer text is empty."))

    # --- privacy: fatal, and never repaired -------------------------------
    # A leak is not a mistake to be corrected in a second attempt. If the model
    # produced prohibited content once, the turn is over.
    surfaces: list[tuple[str, str]] = [("answer", answer.answer), ("basis", answer.confidence_basis)]
    surfaces += [(f"claims[{i}]", c.statement) for i, c in enumerate(answer.claims)]

    for location, text in surfaces:
        for finding in blocking(scan(text, location, rules)):
            result.violations.append(
                Violation(
                    "privacy-violation",
                    f"Output at {finding.location} matched rule {finding.rule_id} "
                    f"({finding.why}). The answer was discarded.",
                    fatal=True,
                )
            )

    # A substantive answer with no structured claims is prose pretending to be
    # evidence. Record ids written inline in a sentence are not citations: nothing
    # resolves them, nothing verifies them, and the reader cannot click them.
    if (
        answer.classification == "IN_SCOPE"
        and len(answer.answer.strip()) > 240
        and not answer.claims
    ):
        result.violations.append(
            Violation(
                "no-claims-made",
                "This answer asserts things about Josh but carries no claims. Every "
                "factual assertion belongs in the claims array with its support level "
                "and evidence ids. Writing record ids into the prose does not count — "
                "nothing resolves or verifies those.",
                soft=True,
            )
        )

    # --- evidence integrity -----------------------------------------------
    for index, claim in enumerate(answer.claims):
        unknown = [rid for rid in claim.evidence_ids if rid not in known]
        if unknown:
            result.violations.append(
                Violation(
                    "fabricated-evidence-id",
                    f"claims[{index}] cites {unknown!r}, which are not evidence record "
                    "ids. Cite only ids the tools returned.",
                )
            )
            result.rejected_claims.append(claim.statement)

        resolvable = [rid for rid in claim.evidence_ids if rid in known]
        if claim.support == "SUPPORTED" and not resolvable:
            result.violations.append(
                Violation(
                    "unsupported-claim",
                    f"claims[{index}] is marked SUPPORTED but names no evidence record "
                    "that exists. Lower it to INFERRED, or remove it.",
                )
            )
            result.rejected_claims.append(claim.statement)

        if claim.support == "UNKNOWN" and claim.evidence_ids:
            result.violations.append(
                Violation(
                    "contradictory-claim",
                    f"claims[{index}] is marked UNKNOWN but cites evidence. If a record "
                    "covers it, the support level is SUPPORTED or INFERRED.",
                )
            )

    # --- gaps must be real -------------------------------------------------
    gap_ids = {r["id"] for r in store.by_type("gap")}
    for gap_id in answer.gaps_acknowledged:
        if gap_id not in gap_ids:
            result.violations.append(
                Violation(
                    "unknown-gap-id",
                    f"gaps_acknowledged names {gap_id!r}, which is not a gap record.",
                )
            )

    # --- the verdict is the server's -------------------------------------
    if answer.verdict != "not_applicable":
        if answer.verdict != computed_verdict:
            result.violations.append(
                Violation(
                    "verdict-override",
                    f"You reported the verdict {answer.verdict!r}. The rubric computed "
                    f"{computed_verdict!r}. Report the computed verdict, or use "
                    "not_applicable if the question is not about fit.",
                )
            )
        # Confidence travels with the verdict. The rubric caps it deliberately —
        # most of the evidence is self-reported — and an answer that quotes the
        # verdict while upgrading its confidence has undone that cap.
        if computed_confidence and answer.confidence != computed_confidence:
            result.violations.append(
                Violation(
                    "confidence-override",
                    f"You reported the verdict, so confidence must be the computed "
                    f"{computed_confidence!r}, not {answer.confidence!r}. The rubric "
                    "caps it because most of the record is self-reported.",
                )
            )

    return result


def downgrade(answer: Answer, store: EvidenceStore) -> tuple[Answer, list[str]]:
    """Last-resort salvage: drop unresolvable ids and lower any claim left unsupported.

    Used only when a repair attempt has already failed and the remaining violations are
    all about evidence rather than privacy. Producing a weaker, true answer beats
    producing nothing, but it is never allowed to produce a stronger one.
    """
    known = store.ids()
    changed: list[str] = []
    claims: list[Claim] = []

    for claim in answer.claims:
        resolvable = [rid for rid in claim.evidence_ids if rid in known]
        support = claim.support

        if support == "SUPPORTED" and not resolvable:
            support = "INFERRED"
            changed.append(claim.statement)
        elif len(resolvable) != len(claim.evidence_ids):
            changed.append(claim.statement)

        claims.append(
            Claim(statement=claim.statement, support=support, evidence_ids=resolvable)
        )

    return answer.model_copy(update={"claims": claims}), changed


def to_public_dict(answer: Answer, store: EvidenceStore) -> dict[str, Any]:
    """Render a verified answer for the client, resolving citations to titles."""
    return {
        "answer": answer.answer,
        "classification": answer.classification,
        "verdict": answer.verdict,
        "confidence": answer.confidence,
        "confidence_basis": answer.confidence_basis,
        "claims": [
            {
                "statement": c.statement,
                "support": c.support,
                "citations": [
                    {"id": rid, "title": (store.get(rid) or {}).get("title", rid)}
                    for rid in c.evidence_ids
                ],
            }
            for c in answer.claims
        ],
        "gaps_acknowledged": [
            {"id": g, "title": (store.get(g) or {}).get("title", g)}
            for g in answer.gaps_acknowledged
        ],
    }
