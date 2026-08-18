"""Read-only access to the compiled artifact.

This object is the application's entire world. There is no second store, no fallback
lookup, and no path that reads a file at request time. Accessors return deep copies so
a tool cannot mutate the evidence it was given.
"""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_ARTIFACT = Path(
    os.environ.get("EVIDENCE_ARTIFACT_PATH", REPO_ROOT / "build" / "evidence.compiled.json")
)


class EvidenceStore:
    def __init__(self, artifact: dict[str, Any]) -> None:
        self._artifact = artifact
        self._records: dict[str, dict[str, Any]] = artifact["records"]

    @classmethod
    def load(cls, path: Path | None = None) -> EvidenceStore:
        target = path or DEFAULT_ARTIFACT
        if not target.exists():
            raise FileNotFoundError(
                f"no compiled evidence at {target}. Run: python -m app.evidence.compile"
            )
        return cls(json.loads(target.read_text(encoding="utf-8")))

    # --- identity -----------------------------------------------------------

    @property
    def content_hash(self) -> str:
        return self._artifact["content_hash"]

    @property
    def built_at(self) -> str:
        return self._artifact["built_at"]

    @property
    def record_count(self) -> int:
        return self._artifact["record_count"]

    # --- lookup -------------------------------------------------------------

    def ids(self) -> frozenset[str]:
        return frozenset(self._records)

    def exists(self, record_id: str) -> bool:
        return record_id in self._records

    def get(self, record_id: str) -> dict[str, Any] | None:
        found = self._records.get(record_id)
        return copy.deepcopy(found) if found else None

    def by_type(self, record_type: str) -> list[dict[str, Any]]:
        ids = self._artifact["index"]["by_type"].get(record_type, [])
        return [copy.deepcopy(self._records[i]) for i in ids]

    def all_records(self) -> list[dict[str, Any]]:
        return [copy.deepcopy(r) for r in self._records.values()]

    def resolve(self, record_ids: list[str]) -> list[dict[str, Any]]:
        """Resolve references, silently skipping unknown ids.

        The build gate already guarantees references resolve, so a miss here means the
        model invented an id. The verifier is what catches that; this just refuses to
        crash on it.
        """
        return [copy.deepcopy(self._records[i]) for i in record_ids if i in self._records]
