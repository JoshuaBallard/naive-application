"""The build gate.

Turns `evidence/approved/*.yaml` into one JSON artifact. Everything the application
can ever say comes out of this file, and nothing reaches this file without passing
every check below.

    python -m app.evidence.compile              # build it
    python -m app.evidence.compile --check      # verify without writing (CI)

Five gates, in order. The first failure stops the build.

  1. Schema      — Pydantic, extra fields forbidden.
  2. Approval    — `approved: true` or the record is dropped, loudly.
  3. Privacy     — every string in every record, through the linter.
  4. Integrity   — every `evidence_ids` reference resolves to a real record.
  5. Hash        — deterministic content hash, so a diff is visible in one line.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator

import yaml
from pydantic import ValidationError

from .lint import Finding, blocking, build_rules, scan
from .schema import RecordAdapter

REPO_ROOT = Path(__file__).resolve().parents[3]
APPROVED_DIR = REPO_ROOT / "evidence" / "approved"
BUILD_DIR = REPO_ROOT / "build"
ARTIFACT_PATH = BUILD_DIR / "evidence.compiled.json"

SCHEMA_VERSION = 1

# Fields that carry references to other records.
REFERENCE_FIELDS = ("evidence_ids", "origin_ids")


class CompileError(RuntimeError):
    pass


def walk_strings(value: Any, path: str = "") -> Iterator[tuple[str, str]]:
    """Yield (dotted_path, string) for every string anywhere in a record."""
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from walk_strings(item, f"{path}.{key}" if path else str(key))
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            yield from walk_strings(item, f"{path}[{index}]")


def collect_references(record: dict[str, Any]) -> set[str]:
    found: set[str] = set()
    for field in REFERENCE_FIELDS:
        found.update(record.get(field) or [])
    for point in record.get("points") or []:
        if isinstance(point, dict):
            found.update(point.get("evidence_ids") or [])
    return found


def load_source_files(directory: Path) -> list[tuple[Path, dict[str, Any]]]:
    if not directory.exists():
        raise CompileError(f"no evidence directory at {directory}")

    loaded: list[tuple[Path, dict[str, Any]]] = []
    for path in sorted(directory.glob("*.yaml")):
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        if raw is None:
            raise CompileError(f"{path.name} is empty")
        if not isinstance(raw, dict):
            raise CompileError(f"{path.name} must contain a single record mapping")
        loaded.append((path, raw))
    return loaded


def compile_evidence(
    directory: Path = APPROVED_DIR,
    *,
    personal_terms: tuple[str, ...] | None = None,
) -> tuple[dict[str, Any], list[str], list[Finding]]:
    """Compile approved evidence.

    Returns (artifact, dropped_filenames, warnings). Raises CompileError on any
    blocking problem.
    """
    rules = build_rules(personal_terms)
    sources = load_source_files(directory)

    records: dict[str, dict[str, Any]] = {}
    dropped: list[str] = []
    warnings: list[Finding] = []
    problems: list[str] = []

    for path, raw in sources:
        # Gate 2 first: an unapproved record is not validated, not linted, not read.
        if raw.get("approved") is not True:
            dropped.append(path.name)
            continue

        # Gate 1: schema.
        try:
            record = RecordAdapter(record=raw).record
        except ValidationError as exc:
            problems.append(f"{path.name}: schema — {exc.error_count()} problem(s)\n{exc}")
            continue

        data = record.model_dump(mode="json")

        if data["id"] in records:
            problems.append(f"{path.name}: duplicate record id {data['id']!r}")
            continue

        # Gate 3: privacy.
        for field_path, text in walk_strings(data):
            findings = scan(text, f"{data['id']}:{field_path}", rules)
            problems.extend(str(f) for f in blocking(findings))
            warnings.extend(f for f in findings if f.severity == "warn")

        records[data["id"]] = data

    # Gate 4: integrity.
    for record_id, data in records.items():
        for reference in sorted(collect_references(data)):
            if reference not in records:
                problems.append(
                    f"{record_id}: references {reference!r}, which is not an approved record"
                )

    if problems:
        raise CompileError(
            "evidence build failed:\n  " + "\n  ".join(problems)
        )

    if not records:
        raise CompileError("no approved records. Refusing to build an empty world model.")

    ordered = {rid: records[rid] for rid in sorted(records)}

    # Gate 5: deterministic hash over content only, so rebuilds without edits are noise-free.
    payload = json.dumps(ordered, sort_keys=True, separators=(",", ":")).encode("utf-8")
    content_hash = hashlib.sha256(payload).hexdigest()

    by_type: dict[str, list[str]] = {}
    for rid, data in ordered.items():
        by_type.setdefault(data["type"], []).append(rid)

    artifact = {
        "schema_version": SCHEMA_VERSION,
        "built_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "content_hash": content_hash,
        "record_count": len(ordered),
        "index": {"by_type": by_type},
        "records": ordered,
    }
    return artifact, dropped, warnings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compile approved evidence.")
    parser.add_argument("--check", action="store_true", help="verify without writing")
    args = parser.parse_args(argv)

    try:
        artifact, dropped, warnings = compile_evidence()
    except CompileError as exc:
        print(f"\n✗ {exc}\n", file=sys.stderr)
        return 1

    for name in dropped:
        print(f"  dropped (approved is not true): {name}")
    for finding in warnings:
        print(f"  {finding}")

    print(
        f"\n✓ {artifact['record_count']} records · "
        f"hash {artifact['content_hash'][:12]} · "
        f"{len(dropped)} dropped · {len(warnings)} to review"
    )

    if args.check:
        return 0

    BUILD_DIR.mkdir(exist_ok=True)
    ARTIFACT_PATH.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    print(f"  wrote {ARTIFACT_PATH.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
