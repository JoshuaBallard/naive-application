"""Copy the evaluation results into the web app so /red-team can render them.

Run after an eval run. The results are committed on purpose — publishing the failures
is the point, and a suite you only show when it is green is marketing.

One thing this refuses to copy: the answer text of any case that failed *because the
output leaked*. That answer contains the leak, and publishing it would turn the
transparency into the vulnerability.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "evaluations" / "results" / "latest.json"
TARGET = ROOT / "web" / "data" / "eval-results.json"

WITHHELD = "[withheld: this answer failed the privacy linter, so it is recorded as a failure but not reproduced here]"


def main() -> int:
    if not SOURCE.exists():
        print(f"no results at {SOURCE}. Run evaluations/run.py first.", file=sys.stderr)
        return 1

    data = json.loads(SOURCE.read_text(encoding="utf-8"))

    leaked = 0
    for case in data["cases"]:
        if any(f.startswith("privacy:") for f in case["failures"]):
            case["answer"] = WITHHELD
            leaked += 1

    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    print(f"published {data['passed']}/{data['total']} to {TARGET.relative_to(ROOT)}")
    if leaked:
        print(f"  withheld {leaked} answer(s) that failed the privacy linter")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
