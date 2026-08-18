"""The verifier is the reason "never fabricate" is a guarantee and not a request.

Every test here is a way a plausible, well-written, confident answer gets stopped.
"""

from __future__ import annotations

import pytest

from app.agent.schemas import Answer, Claim
from app.agent.verifier import downgrade, to_public_dict, verify
from app.evidence.lint import build_rules
from app.evidence.store import EvidenceStore

TEST_TERMS = ("Acme Defense", "Anytown, Ohio")
COMPUTED = "interesting_partial_fit"


@pytest.fixture(scope="module")
def store():
    return EvidenceStore.load()


@pytest.fixture(scope="module")
def rules():
    return build_rules(TEST_TERMS)


def answer(**overrides) -> Answer:
    base = {
        "classification": "IN_SCOPE",
        "answer": "Josh shipped Built in a Day in a single day.",
        "claims": [
            Claim(
                statement="48 commits, all on 2026-08-05.",
                support="SUPPORTED",
                evidence_ids=["proj.built-in-a-day"],
            )
        ],
        "verdict": "not_applicable",
        "gaps_acknowledged": [],
        "confidence": "medium_high",
        "confidence_basis": "Public commit history.",
    }
    base.update(overrides)
    return Answer(**base)


def check(a: Answer, store, rules, computed: str = COMPUTED):
    return verify(a, store=store, rules=rules, computed_verdict=computed)


def test_a_well_formed_answer_passes(store, rules) -> None:
    result = check(answer(), store, rules)
    assert result.ok
    assert result.status == "passed"


def test_invented_evidence_id_is_rejected(store, rules) -> None:
    """The single most likely failure: a confident claim citing a record that isn't there."""
    a = answer(claims=[Claim(
        statement="Josh led a team of forty engineers.",
        support="SUPPORTED",
        evidence_ids=["work.google"],
    )])

    result = check(a, store, rules)

    assert not result.ok
    assert any(v.code == "fabricated-evidence-id" for v in result.violations)
    assert "Josh led a team of forty engineers." in result.rejected_claims


def test_supported_claim_with_no_evidence_is_rejected(store, rules) -> None:
    a = answer(claims=[Claim(
        statement="Josh is an exceptional systems architect.",
        support="SUPPORTED",
        evidence_ids=[],
    )])

    result = check(a, store, rules)

    assert any(v.code == "unsupported-claim" for v in result.violations)


def test_inferred_claim_with_no_evidence_is_allowed(store, rules) -> None:
    """Marking something as your own read is honest. It is only dishonest to call it evidence."""
    a = answer(claims=[Claim(
        statement="He would probably enjoy the governance side of this role.",
        support="INFERRED",
        evidence_ids=[],
    )])

    assert check(a, store, rules).ok


def test_unknown_claim_citing_evidence_is_contradictory(store, rules) -> None:
    a = answer(claims=[Claim(
        statement="Nothing is known about this.",
        support="UNKNOWN",
        evidence_ids=["proj.built-in-a-day"],
    )])

    assert any(v.code == "contradictory-claim" for v in check(a, store, rules).violations)


def test_verdict_cannot_be_upgraded(store, rules) -> None:
    """The rubric said partial fit. The model does not get to say strong fit."""
    result = check(answer(verdict="strong_fit"), store, rules)

    assert any(v.code == "verdict-override" for v in result.violations)


def test_verdict_may_be_reported_or_omitted(store, rules) -> None:
    assert check(answer(verdict=COMPUTED), store, rules).ok
    assert check(answer(verdict="not_applicable"), store, rules).ok


def test_invented_gap_id_is_rejected(store, rules) -> None:
    result = check(answer(gaps_acknowledged=["gap.imaginary"]), store, rules)
    assert any(v.code == "unknown-gap-id" for v in result.violations)


def test_empty_answer_is_rejected(store, rules) -> None:
    assert any(v.code == "empty-answer" for v in check(answer(answer="   "), store, rules).violations)


# --- privacy is fatal, and never echoed ------------------------------------


@pytest.mark.parametrize(
    "leak",
    [
        "His homelab is reachable at 192.168.1.40 on the internal network.",
        "The token was ghp_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa at the time.",
        "He worked at Acme Defense before this.",
        "Reachable at josh-box.ts.net when he is away.",
    ],
)
def test_prohibited_output_fails_closed(store, rules, leak: str) -> None:
    result = check(answer(answer=leak), store, rules)

    assert not result.ok
    assert result.fatal
    assert result.status == "failed_closed"


def test_violation_text_never_repeats_the_leak(store, rules) -> None:
    """Violations are fed back to the model. They must not carry the thing we caught."""
    secret = "ghp_bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
    result = check(answer(answer=f"The token was {secret} briefly."), store, rules)

    assert secret not in result.as_prompt()
    assert "api-key-shape" in result.as_prompt()


# --- salvage ---------------------------------------------------------------


def test_downgrade_weakens_but_never_strengthens(store) -> None:
    a = answer(claims=[
        Claim(statement="Real.", support="SUPPORTED", evidence_ids=["proj.built-in-a-day"]),
        Claim(statement="Invented.", support="SUPPORTED", evidence_ids=["work.google"]),
    ])

    salvaged, changed = downgrade(a, store)

    assert salvaged.claims[0].support == "SUPPORTED"
    assert salvaged.claims[1].support == "INFERRED"
    assert salvaged.claims[1].evidence_ids == []
    assert changed == ["Invented."]


def test_downgraded_answer_then_passes_verification(store, rules) -> None:
    a = answer(claims=[Claim(statement="Invented.", support="SUPPORTED", evidence_ids=["nope.x"])])
    salvaged, _ = downgrade(a, store)

    assert check(salvaged, store, rules).ok


def test_public_dict_resolves_citations_to_titles(store) -> None:
    rendered = to_public_dict(answer(), store)
    citation = rendered["claims"][0]["citations"][0]

    assert citation["id"] == "proj.built-in-a-day"
    assert citation["title"] == "Built in a Day"


def test_confidence_cannot_be_upgraded_alongside_the_verdict(store, rules) -> None:
    """Quoting the rubric's verdict while inflating its confidence undoes the cap."""
    a = answer(verdict=COMPUTED, confidence="high")

    result = verify(
        a, store=store, rules=rules,
        computed_verdict=COMPUTED, computed_confidence="medium_high",
    )

    assert any(v.code == "confidence-override" for v in result.violations)


def test_confidence_is_free_when_no_verdict_is_reported(store, rules) -> None:
    """A question that is not about fit carries no rubric confidence to honour."""
    result = verify(
        answer(verdict="not_applicable", confidence="high"),
        store=store, rules=rules,
        computed_verdict=COMPUTED, computed_confidence="medium_high",
    )
    assert result.ok
