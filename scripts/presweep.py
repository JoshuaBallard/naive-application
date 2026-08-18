"""Check a git ref for anything that must not be published.

Written after the repository was made public for about two minutes with the exclusion
list still present on main. The sweep at the time was correct and pointed at the working
tree, while the thing being published was a ref four commits behind it.

So this reads blobs out of the ref itself with `git show`, never from disk. What you are
about to publish is what gets checked.

    python scripts/presweep.py            # checks origin/main
    python scripts/presweep.py HEAD
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXCLUSIONS = ROOT / "security" / "exclusions.local.txt"

# Four octets. An earlier version of this check matched ">=10.13.0" in a lockfile,
# because 10.x with three components is a version number, not an address.
PRIVATE_IPV4 = re.compile(
    r"\b(?:"
    r"10\.\d{1,3}\.\d{1,3}\.\d{1,3}"
    r"|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}"
    r"|192\.168\.\d{1,3}\.\d{1,3}"
    r")\b"
)

# The trailing (?!\.) keeps this off filenames. "exclusions.local.txt" is not a host,
# and an earlier version of this check flagged nine files including its own source.
PRIVATE_HOST = re.compile(
    r"\b[a-z0-9-]+\.(?:ts\.net|local|internal|lan)\b(?!\.)", re.IGNORECASE
)
SECRET = re.compile(
    r"sk-ant-[A-Za-z0-9]{20}|ghp_[A-Za-z0-9]{20}|github_pat_[A-Za-z0-9_]{20}"
    r"|FlyV1 fm2_|BEGIN [A-Z ]*PRIVATE KEY|AKIA[0-9A-Z]{16}"
)
SECRET_FILE = re.compile(r"(^|/)(\.env|exclusions\.local\.txt|.*\.pem|.*\.key)$")

# Files that legitimately contain the shapes above: the linter's own rules, and the
# deliberate known-bad inputs that prove it fires.
ALLOWED = {"api/app/evidence/lint.py", "scripts/presweep.py"}
ALLOWED_PREFIXES = ("api/tests/",)


def blob(ref: str, path: str) -> str:
    out = subprocess.run(["git", "show", f"{ref}:{path}"], capture_output=True)
    return out.stdout.decode("utf-8", errors="ignore")


def main() -> int:
    ref = sys.argv[1] if len(sys.argv) > 1 else "origin/main"

    if not EXCLUSIONS.exists():
        print(f"✗ no exclusion list at {EXCLUSIONS}. Refusing to certify anything.")
        return 1

    terms = [t.split("#")[0].strip() for t in EXCLUSIONS.read_text().splitlines()]
    terms = [t for t in terms if t]

    listing = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", ref], capture_output=True, text=True
    )
    if listing.returncode != 0:
        print(f"✗ cannot read {ref}: {listing.stderr.strip()}")
        return 1

    paths = [p for p in listing.stdout.split("\n") if p]
    problems: list[str] = []

    for path in paths:
        if SECRET_FILE.search(path) and not path.endswith(".example.txt"):
            problems.append(f"{path} :: a secret file is tracked")

        exempt = path in ALLOWED or path.startswith(ALLOWED_PREFIXES)
        text = blob(ref, path)

        for term in terms:
            if re.search(rf"(?<!\w){re.escape(term)}(?!\w)", text, re.IGNORECASE):
                problems.append(f"{path} :: excluded personal term")

        if exempt:
            continue
        if SECRET.search(text):
            problems.append(f"{path} :: secret-shaped string")
        if PRIVATE_IPV4.search(text):
            problems.append(f"{path} :: private network address")
        if PRIVATE_HOST.search(text):
            problems.append(f"{path} :: private hostname")

    print(f"swept {len(paths)} blobs in {ref}")
    if problems:
        print("\n✗ NOT SAFE TO PUBLISH\n")
        for p in sorted(set(problems)):
            print(f"    {p}")
        return 1

    print(f"\n✓ clean — {len(terms)} exclusion terms, secret shapes, private addresses "
          "and hostnames, tracked secret files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
