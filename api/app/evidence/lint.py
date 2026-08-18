"""The privacy linter.

Runs in two places, which is the whole reason it is a library and not a script:

  1. At build time, over every approved evidence record. A finding fails the build.
  2. At request time, over everything the model produced before it reaches a browser.
     A finding means the answer is discarded, not edited.

Findings mask what they matched. A linter that prints the secret it found in order to
tell you it found a secret has moved the leak rather than stopped it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Literal

from .policy import (
    BLOCK_TERMS_STRUCTURAL,
    DOMAIN_ALLOWLIST,
    EMAIL_ALLOWLIST,
    WARN_TERMS,
    load_personal_exclusions,
)

Severity = Literal["block", "warn"]


@dataclass(frozen=True)
class Rule:
    id: str
    severity: Severity
    why: str
    pattern: re.Pattern[str]


@dataclass(frozen=True)
class Finding:
    rule_id: str
    severity: Severity
    why: str
    location: str
    masked: str

    def __str__(self) -> str:
        return f"[{self.severity}] {self.location}: {self.rule_id} — {self.why} ({self.masked})"


def mask(value: str) -> str:
    """Show enough to find it in the file, not enough to be the leak."""
    stripped = value.strip()
    if len(stripped) <= 4:
        return "*" * len(stripped)
    return f"{stripped[:2]}{'*' * min(len(stripped) - 4, 12)}{stripped[-2:]}"


def _term_rule(term: str, severity: Severity, why: str, rule_id: str) -> Rule:
    return Rule(
        id=rule_id,
        severity=severity,
        why=why,
        pattern=re.compile(rf"(?<!\w){re.escape(term)}(?!\w)", re.IGNORECASE),
    )


# --- Structural patterns -----------------------------------------------------

PATTERN_RULES: tuple[Rule, ...] = (
    Rule(
        id="ipv4-literal",
        severity="block",
        why="IPv4 address literal",
        pattern=re.compile(r"\b(?:(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\.){3}(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\b"),
    ),
    Rule(
        id="ipv6-ula",
        severity="block",
        why="IPv6 unique local address",
        pattern=re.compile(r"\bf[cd][0-9a-f]{2}:[0-9a-f:]{2,}\b", re.IGNORECASE),
    ),
    Rule(
        id="mac-address",
        severity="block",
        why="MAC address",
        pattern=re.compile(r"\b(?:[0-9a-f]{2}:){5}[0-9a-f]{2}\b", re.IGNORECASE),
    ),
    Rule(
        id="private-hostname",
        severity="block",
        why="private or internal hostname",
        pattern=re.compile(r"\b[a-z0-9\-]+\.(?:local|internal|lan|home|ts\.net)\b", re.IGNORECASE),
    ),
    Rule(
        id="private-key-header",
        severity="block",
        why="private key material",
        pattern=re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    ),
    Rule(
        id="api-key-shape",
        severity="block",
        why="string shaped like an API key or token",
        pattern=re.compile(
            r"\b(?:sk-ant-[A-Za-z0-9\-_]+|sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{20,}"
            r"|github_pat_[A-Za-z0-9_]{20,}|gho_[A-Za-z0-9]{20,}|glpat-[A-Za-z0-9\-_]{15,}"
            r"|A(?:KIA|SIA)[0-9A-Z]{16}|xox[baprs]-[A-Za-z0-9\-]{10,})\b"
        ),
    ),
    Rule(
        id="bearer-token",
        severity="block",
        why="bearer token in text",
        pattern=re.compile(r"\bBearer\s+[A-Za-z0-9._\-]{16,}", re.IGNORECASE),
    ),
    Rule(
        id="long-opaque-token",
        severity="block",
        why="long opaque string that may be a credential",
        pattern=re.compile(r"\b[A-Za-z0-9_\-]{40,}\b"),
    ),
    Rule(
        id="phone-number",
        severity="block",
        why="telephone number",
        pattern=re.compile(r"(?:\+?1[\s.\-])?\(?\d{3}\)?[\s.\-]\d{3}[\s.\-]\d{4}\b"),
    ),
)

EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")
URL_PATTERN = re.compile(r"https?://([A-Za-z0-9.\-]+)(?::\d+)?(?:/[^\s\"'<>)]*)?")


def build_rules(personal_terms: Iterable[str] | None = None) -> tuple[Rule, ...]:
    """Assemble the full rule set.

    Raises if the personal exclusion list is missing. Fail closed: a linter that
    cannot load its blocklist must not report a clean run.
    """
    terms = tuple(personal_terms) if personal_terms is not None else load_personal_exclusions()

    rules: list[Rule] = list(PATTERN_RULES)
    rules += [
        _term_rule(t, "block", "structurally prohibited term", "prohibited-term")
        for t in BLOCK_TERMS_STRUCTURAL
    ]
    rules += [
        # The term itself never appears in the finding, only the rule id.
        _term_rule(t, "block", "excluded personal term", "excluded-personal-term")
        for t in terms
    ]
    rules += [_term_rule(t, "warn", "word that needs a human read", "review-term") for t in WARN_TERMS]
    return tuple(rules)


def scan(text: str, location: str, rules: tuple[Rule, ...]) -> list[Finding]:
    """Scan one string. `location` is a human pointer such as `proj.quiet-wells:summary`."""
    findings: list[Finding] = []

    for rule in rules:
        for match in rule.pattern.finditer(text):
            findings.append(
                Finding(
                    rule_id=rule.id,
                    severity=rule.severity,
                    why=rule.why,
                    location=location,
                    masked=mask(match.group(0)),
                )
            )

    for match in EMAIL_PATTERN.finditer(text):
        if match.group(0).lower() not in EMAIL_ALLOWLIST:
            findings.append(
                Finding(
                    rule_id="email-not-allowlisted",
                    severity="block",
                    why="email address that is not on the approved list",
                    location=location,
                    masked=mask(match.group(0)),
                )
            )

    for match in URL_PATTERN.finditer(text):
        host = match.group(1).lower()
        if host not in DOMAIN_ALLOWLIST:
            findings.append(
                Finding(
                    rule_id="url-not-allowlisted",
                    severity="block",
                    why=f"URL host {host!r} is not on the approved domain list",
                    location=location,
                    masked=mask(match.group(0)),
                )
            )

    return findings


def blocking(findings: Iterable[Finding]) -> list[Finding]:
    return [f for f in findings if f.severity == "block"]
