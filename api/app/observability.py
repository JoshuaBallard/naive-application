"""Structured logging with a field allowlist.

Logs are the classic way a careful application leaks anyway: someone logs the request
body to debug something at 2am and the transcript of every question a hiring manager
asked is now in a log aggregator forever.

So this logger cannot log a message body. There is no parameter for one. Fields are
enumerated below and anything else is dropped, rather than being a convention people
are asked to remember.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import sys
from datetime import UTC, date, datetime
from typing import Any

# The complete set of fields that may ever be logged.
ALLOWED_FIELDS = frozenset(
    {
        "ts", "event", "request_id", "route", "status",
        "classification", "verdict", "verification", "refusal",
        "tools", "evidence_count", "claims", "support_counts",
        "latency_ms", "input_tokens", "output_tokens", "cached_tokens", "cost_micros",
        "session_questions_used", "ip_hash", "error_class", "reason", "detail",
    }
)

# Never logged, under any circumstance. Present as a tripwire: if one of these ever
# appears in a call, the log line is dropped and a loud error is emitted instead.
FORBIDDEN_FIELDS = frozenset(
    {"question", "answer", "message", "email", "name", "body", "headers", "ip", "prompt"}
)

_logger = logging.getLogger("naive-application")
_handler = logging.StreamHandler(sys.stdout)
_handler.setFormatter(logging.Formatter("%(message)s"))
_logger.addHandler(_handler)
_logger.setLevel(logging.INFO)

_SALT = os.environ.get("IP_HASH_SALT", "")


def hash_ip(ip: str | None) -> str:
    """A rotating, salted hash. Enough to rate-limit; not enough to identify.

    The salt rotates daily, so yesterday's hashes cannot be correlated with today's
    even by someone holding the whole log.
    """
    if not ip:
        return "unknown"
    material = f"{_SALT}:{date.today().isoformat()}:{ip}".encode()
    return hashlib.sha256(material).hexdigest()[:16]


def log(event: str, **fields: Any) -> None:
    leaked = FORBIDDEN_FIELDS & set(fields)
    if leaked:
        _logger.error(
            json.dumps(
                {
                    "ts": datetime.now(UTC).isoformat(timespec="seconds"),
                    "event": "logging.forbidden_field",
                    "detail": f"dropped a log line that carried {sorted(leaked)}",
                }
            )
        )
        return

    line = {
        "ts": datetime.now(UTC).isoformat(timespec="seconds"),
        "event": event,
        **{k: v for k, v in fields.items() if k in ALLOWED_FIELDS},
    }
    _logger.info(json.dumps(line, default=str))
