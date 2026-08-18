"""Allowed-data and prohibited-data policy, as code.

`security/ALLOWED_DATA.md` and `security/PROHIBITED_DATA.md` describe this file in
prose. This is the version that runs. If the two disagree, this one wins and the prose
is the bug.

A note on why the personal exclusions are not in this file.

The first draft listed them here: the current employer, a clearance, a military unit,
a home town. Committing that list to a public repository would have published every
fact it was written to suppress, in one convenient place. A blocklist is exactly as
sensitive as the things on it.

So the specific terms live in `security/exclusions.local.txt`, which is gitignored and
supplied to CI as a secret. The build **fails closed** if that file is missing. A
missing blocklist is treated as a broken build, never as an empty one.
"""

from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]

EXCLUSIONS_PATH = Path(
    os.environ.get("EVIDENCE_EXCLUSIONS_FILE", REPO_ROOT / "security" / "exclusions.local.txt")
)


class MissingExclusionsFile(RuntimeError):
    """Raised when the personal exclusion list cannot be found.

    Fail closed. An absent blocklist means the linter is blind, and a blind linter
    that reports success is worse than no linter at all.
    """


# ---------------------------------------------------------------------------
# Allowlists. Nothing outside these may appear in evidence.
# ---------------------------------------------------------------------------

# Every URL in every evidence record must live on one of these hosts. An approved link
# cannot quietly become an arbitrary link because someone edited YAML in a hurry.
DOMAIN_ALLOWLIST: frozenset[str] = frozenset(
    {
        "github.com",
        "joshuaballard.github.io",
        "linkedin.com",
        "www.linkedin.com",
        "quietwells.com",
        "www.quietwells.com",
    }
)

# The only address that may appear in evidence. It is already public on the
# built-in-a-day site, which is what makes it approvable rather than just convenient.
EMAIL_ALLOWLIST: frozenset[str] = frozenset({"jbballard2@gmail.com"})


# ---------------------------------------------------------------------------
# Structural blocklist. Categories, not personal facts, so this is safe to publish.
# ---------------------------------------------------------------------------

BLOCK_TERMS_STRUCTURAL: tuple[str, ...] = (
    "tailscale",
    "tailnet",
    "wireguard",
    "authorized_keys",
    "id_rsa",
    "docker-compose.override",
    ".env",
    "sudo password",
    "root password",
)

# Words that are not automatically wrong but always earn a second read. These print a
# review report; they do not fail the build.
WARN_TERMS: tuple[str, ...] = (
    "wife",
    "husband",
    "son",
    "daughter",
    "child",
    "children",
    "family member",
    "address",
    "phone",
    "password",
    "clearance",
    "classified",
    "customer",
    "client",
    "employer",
    "colleague",
    "my manager",
    "reports to",
)


def load_personal_exclusions(path: Path | None = None) -> tuple[str, ...]:
    """Read the gitignored personal exclusion list.

    One term per line, `#` starts a comment, blank lines ignored. Matching is
    case-insensitive and happens on word boundaries in `lint.py`.
    """
    target = path or EXCLUSIONS_PATH
    if not target.exists():
        raise MissingExclusionsFile(
            f"personal exclusion list not found at {target}.\n"
            "Copy security/exclusions.example.txt to security/exclusions.local.txt and fill "
            "it in, or set EVIDENCE_EXCLUSIONS_FILE. The build will not run without it."
        )

    terms: list[str] = []
    for line in target.read_text(encoding="utf-8").splitlines():
        cleaned = line.split("#", 1)[0].strip()
        if cleaned:
            terms.append(cleaned)

    if not terms:
        raise MissingExclusionsFile(f"{target} exists but contains no terms. Refusing to run.")

    return tuple(terms)
