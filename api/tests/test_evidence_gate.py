"""The build gate must fail. That is its whole job.

These tests never touch `security/exclusions.local.txt` — they pass their own term
list. Real exclusions do not belong in a committed test file, for the same reason
they do not belong in `policy.py`.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from app.evidence.compile import CompileError, compile_evidence
from app.evidence.policy import MissingExclusionsFile, load_personal_exclusions

# Invented terms. Real exclusions do not belong in a committed test file, for the
# same reason they do not belong in policy.py or the evaluation corpus.
TEST_TERMS = ("Acme Defense", "Anytown, Ohio", "Zeta Clearance")

VALID = """
    id: proj.example
    type: project
    approved: true
    reviewed_on: 2026-08-17
    reviewed_by: josh
    source_class: public_artifact
    title: Example
    summary: A project record that exists so the other tests have something valid to break.
    problem: Something needed doing.
    what_josh_built: A thing that does it.
    what_josh_learned: That the thing was harder than it looked.
    technologies: [python]
    known_limitations:
      - It is an example.
"""


def write(directory: Path, name: str, body: str) -> Path:
    path = directory / f"{name}.yaml"
    path.write_text(textwrap.dedent(body).strip() + "\n", encoding="utf-8")
    return path


def build(directory: Path):
    return compile_evidence(directory, personal_terms=TEST_TERMS)


def test_valid_record_compiles(tmp_path: Path) -> None:
    write(tmp_path, "proj.example", VALID)
    artifact, dropped, warnings = build(tmp_path)

    assert artifact["record_count"] == 1
    assert artifact["records"]["proj.example"]["title"] == "Example"
    assert dropped == []
    assert warnings == []


def test_hash_is_deterministic(tmp_path: Path) -> None:
    write(tmp_path, "proj.example", VALID)
    first, _, _ = build(tmp_path)
    second, _, _ = build(tmp_path)
    assert first["content_hash"] == second["content_hash"]


# --- Gate 2: approval -------------------------------------------------------


def test_unapproved_record_is_dropped_not_compiled(tmp_path: Path) -> None:
    write(tmp_path, "proj.example", VALID)
    write(tmp_path, "proj.secret", VALID.replace("approved: true", "approved: false").replace(
        "id: proj.example", "id: proj.secret"
    ))

    artifact, dropped, _ = build(tmp_path)

    assert "proj.secret" not in artifact["records"]
    assert dropped == ["proj.secret.yaml"]


def test_missing_approved_field_is_dropped(tmp_path: Path) -> None:
    write(tmp_path, "proj.example", VALID)
    write(tmp_path, "proj.forgot", VALID.replace("    approved: true\n", "").replace(
        "id: proj.example", "id: proj.forgot"
    ))

    artifact, dropped, _ = build(tmp_path)

    assert "proj.forgot" not in artifact["records"]
    assert dropped == ["proj.forgot.yaml"]


def test_empty_evidence_set_refuses_to_build(tmp_path: Path) -> None:
    with pytest.raises(CompileError, match="empty world model"):
        build(tmp_path)


# --- Gate 3: privacy --------------------------------------------------------


@pytest.mark.parametrize(
    ("label", "leak"),
    [
        ("private ipv4", "The service listened on 192.168.1.40 inside the network."),
        ("public ipv4", "Traffic arrived from 203.0.113.14 during the test."),
        ("ipv6 ula", "The container resolved to fd7a:115c:a1e0::1 instead."),
        ("mac address", "The interface reported de:ad:be:ef:00:01 at boot."),
        ("private hostname", "It was reachable at atlas.internal from the host."),
        ("tailnet host", "Reachable over josh-laptop.ts.net when away from home."),
        ("api key", "The token was sk-ant-api03-AAAABBBBCCCCDDDDEEEEFFFF for one afternoon."),
        ("github token", "It printed ghp_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa to the log."),
        ("private key", "It contained -----BEGIN RSA PRIVATE KEY----- in the clear."),
        ("phone number", "He can be reached on 513-555-0142 most days."),
        ("bearer token", "The header was Bearer abcdefghijklmnopqrstuvwxyz012345 throughout."),
        ("structural term", "Remote access ran over Tailscale between the two sites."),
        ("unapproved email", "Reach him at josh.private@example.com for details."),
        ("unapproved url", "The dashboard lives at https://internal.example.com/atlas today."),
    ],
)
def test_privacy_linter_blocks(tmp_path: Path, label: str, leak: str) -> None:
    write(tmp_path, "proj.example", VALID.replace("Something needed doing.", leak))

    with pytest.raises(CompileError) as exc:
        build(tmp_path)

    assert "evidence build failed" in str(exc.value), label


@pytest.mark.parametrize("term", TEST_TERMS)
def test_personal_exclusions_block(tmp_path: Path, term: str) -> None:
    write(tmp_path, "proj.example", VALID.replace("Something needed doing.", f"He worked at {term} for a while."))

    with pytest.raises(CompileError, match="excluded-personal-term"):
        build(tmp_path)


def test_findings_never_print_what_they_matched(tmp_path: Path) -> None:
    """A linter that echoes the secret to report the secret has moved the leak."""
    secret = "ghp_zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz"
    write(tmp_path, "proj.example", VALID.replace("Something needed doing.", f"Token {secret} leaked."))

    with pytest.raises(CompileError) as exc:
        build(tmp_path)

    assert secret not in str(exc.value)
    assert "api-key-shape" in str(exc.value)


def test_warn_terms_report_but_do_not_fail(tmp_path: Path) -> None:
    write(tmp_path, "proj.example", VALID.replace(
        "Something needed doing.", "A customer asked for it, so it needed doing."
    ))

    artifact, _, warnings = build(tmp_path)

    assert artifact["record_count"] == 1
    assert any(f.rule_id == "review-term" for f in warnings)


def test_approved_email_and_domains_pass(tmp_path: Path) -> None:
    write(tmp_path, "proj.example", VALID.replace(
        "Something needed doing.",
        "Written up at https://github.com/JoshuaBallard/built-in-a-day and jbballard2@gmail.com.",
    ))

    artifact, _, _ = build(tmp_path)
    assert artifact["record_count"] == 1


# --- Gate 1: schema ---------------------------------------------------------


def test_unknown_field_is_a_build_failure(tmp_path: Path) -> None:
    write(tmp_path, "proj.example", VALID + "    secret_notes: for internal use only\n")

    with pytest.raises(CompileError, match="schema"):
        build(tmp_path)


def test_project_must_state_a_limitation(tmp_path: Path) -> None:
    body = VALID.replace("    known_limitations:\n      - It is an example.\n", "    known_limitations: []\n")
    write(tmp_path, "proj.example", body)

    with pytest.raises(CompileError, match="known limitation"):
        build(tmp_path)


def test_public_claim_without_a_url_is_rejected(tmp_path: Path) -> None:
    body = VALID + (
        "    verified_claims:\n"
        "      - claim: Something a stranger could check, if only there were a link.\n"
        "        verification: public_artifact\n"
    )
    write(tmp_path, "proj.example", body)

    with pytest.raises(CompileError, match="no evidence_url"):
        build(tmp_path)


def test_self_reported_claim_needs_no_url(tmp_path: Path) -> None:
    body = VALID + (
        "    verified_claims:\n"
        "      - claim: Josh spent about four hours on the first version of this.\n"
        "        verification: self_reported\n"
    )
    write(tmp_path, "proj.example", body)

    artifact, _, _ = build(tmp_path)
    claim = artifact["records"]["proj.example"]["verified_claims"][0]
    assert claim["verification"] == "self_reported"


def test_redaction_must_be_documented(tmp_path: Path) -> None:
    write(tmp_path, "proj.example", VALID + "    sensitive_details_removed: true\n")

    with pytest.raises(CompileError, match="redaction_note"):
        build(tmp_path)


def test_duplicate_ids_are_rejected(tmp_path: Path) -> None:
    write(tmp_path, "a", VALID)
    write(tmp_path, "b", VALID)

    with pytest.raises(CompileError, match="duplicate record id"):
        build(tmp_path)


# --- Gate 4: integrity ------------------------------------------------------


def test_dangling_reference_is_rejected(tmp_path: Path) -> None:
    write(tmp_path, "proj.example", VALID)
    write(
        tmp_path,
        "req.example",
        """
            id: req.example
            type: role_requirement
            approved: true
            reviewed_on: 2026-08-17
            reviewed_by: josh
            source_class: self_authored
            title: Example requirement
            summary: A requirement record pointing at evidence that does not exist.
            requirement: Must have done the thing
            category: must_have
            status: SUPPORTED
            reasoning: It points somewhere that is not there.
            evidence_ids: [proj.does-not-exist]
        """,
    )

    with pytest.raises(CompileError, match="not an approved record"):
        build(tmp_path)


def test_supported_status_requires_evidence(tmp_path: Path) -> None:
    write(tmp_path, "proj.example", VALID)
    write(
        tmp_path,
        "req.empty",
        """
            id: req.empty
            type: role_requirement
            approved: true
            reviewed_on: 2026-08-17
            reviewed_by: josh
            source_class: self_authored
            title: Example requirement
            summary: A supported requirement that cites nothing at all, which is not allowed.
            requirement: Must have done the thing
            category: must_have
            status: SUPPORTED
            reasoning: Trust me.
            evidence_ids: []
        """,
    )

    with pytest.raises(CompileError, match="requires at least one evidence_id"):
        build(tmp_path)


# --- Fail closed ------------------------------------------------------------


def test_missing_exclusions_file_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(MissingExclusionsFile):
        load_personal_exclusions(tmp_path / "nope.txt")


def test_empty_exclusions_file_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / "empty.txt"
    path.write_text("# only comments\n\n", encoding="utf-8")

    with pytest.raises(MissingExclusionsFile):
        load_personal_exclusions(path)
