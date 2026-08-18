"""The repository must not be able to reach the machine it is sitting on.

`CLAUDE.md` states these rules for humans and agents. These tests are the version that
cannot be talked out of it.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

SOURCE_GLOBS = ("api/**/*.py",)
SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", "build", ".next"}


def source_files() -> list[Path]:
    found: list[Path] = []
    for pattern in SOURCE_GLOBS:
        for path in REPO_ROOT.glob(pattern):
            if not any(part in SKIP_DIRS for part in path.parts):
                found.append(path)
    return found


def test_repository_contains_no_symlinks() -> None:
    """A symlink is the easiest way to quietly point this application at a home directory."""
    offenders = [
        p.relative_to(REPO_ROOT)
        for p in REPO_ROOT.rglob("*")
        if not any(part in SKIP_DIRS for part in p.parts) and p.is_symlink()
    ]
    assert offenders == [], f"symlinks found: {offenders}"


def test_no_source_file_references_a_parent_path() -> None:
    """No `../`, no `~`, no absolute path outside the repository."""
    pattern = re.compile(r"""(\.\./\.\.|["']~/|["']/home/|["']/Users/|os\.path\.expanduser)""")

    offenders = []
    for path in source_files():
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if pattern.search(line) and "noqa: boundary" not in line:
                offenders.append(f"{path.relative_to(REPO_ROOT)}:{number}")

    assert offenders == [], f"paths reaching outside the repository: {offenders}"


def test_no_dangerous_module_is_imported() -> None:
    """Nothing here needs a subprocess, a socket, or an arbitrary HTTP client."""
    banned = re.compile(r"^\s*(?:import|from)\s+(subprocess|socket|requests|urllib|ftplib|telnetlib)\b")

    offenders = []
    for path in source_files():
        if path.name.startswith("test_"):
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if banned.match(line):
                offenders.append(f"{path.relative_to(REPO_ROOT)}:{number} — {line.strip()}")

    assert offenders == [], f"unnecessary capability imported: {offenders}"


def test_no_secret_shaped_string_in_source() -> None:
    from app.evidence.lint import PATTERN_RULES

    key_rules = [r for r in PATTERN_RULES if r.id in {"api-key-shape", "private-key-header"}]

    offenders = []
    for path in source_files():
        if path.name.startswith("test_") or path.name == "lint.py":
            continue
        text = path.read_text(encoding="utf-8")
        for rule in key_rules:
            if rule.pattern.search(text):
                offenders.append(f"{path.relative_to(REPO_ROOT)} — {rule.id}")

    assert offenders == [], offenders


def test_exclusion_list_is_not_committed() -> None:
    """The blocklist is as sensitive as the facts on it. It must stay out of git."""
    gitignore = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "security/exclusions.local.txt" in gitignore
