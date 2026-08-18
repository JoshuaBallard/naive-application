"""Storage. Three tables, one of which holds the only personal data in the system.

Interview requests are deliberately isolated: no foreign keys into them, no join from
anything else, and no read path that returns them except the token-protected admin
endpoint. Nothing about a request is ever logged, and nothing is ever sent to a third
party — there is no email provider in this system, which means the requester's address
never leaves the disk it was written to.
"""

from __future__ import annotations

import os
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Iterator

DB_PATH = Path(os.environ.get("DATABASE_PATH", "/data/application.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id              TEXT PRIMARY KEY,
    created_at      TEXT NOT NULL,
    questions_used  INTEGER NOT NULL DEFAULT 0,
    ip_hash         TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS interview_requests (
    ref         TEXT PRIMARY KEY,
    created_at  TEXT NOT NULL,
    name        TEXT NOT NULL,
    email       TEXT NOT NULL,
    window_id   TEXT NOT NULL,
    message     TEXT,
    status      TEXT NOT NULL DEFAULT 'pending_human_approval'
);

CREATE TABLE IF NOT EXISTS daily_usage (
    day             TEXT PRIMARY KEY,
    questions       INTEGER NOT NULL DEFAULT 0,
    cost_micros     INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_sessions_ip ON sessions(ip_hash, created_at);
"""


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def cursor() -> Iterator[sqlite3.Cursor]:
    conn = connect()
    try:
        yield conn.cursor()
    finally:
        conn.close()


def init() -> None:
    with cursor() as cur:
        cur.executescript(SCHEMA)


# --- sessions ---------------------------------------------------------------


def create_session(ip_hash: str) -> str:
    session_id = secrets.token_urlsafe(24)
    with cursor() as cur:
        cur.execute(
            "INSERT INTO sessions (id, created_at, questions_used, ip_hash) VALUES (?,?,0,?)",
            (session_id, datetime.now(UTC).isoformat(timespec="seconds"), ip_hash),
        )
    return session_id


def get_session(session_id: str) -> dict[str, Any] | None:
    with cursor() as cur:
        row = cur.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
    return dict(row) if row else None


def spend_question(session_id: str) -> int:
    with cursor() as cur:
        cur.execute(
            "UPDATE sessions SET questions_used = questions_used + 1 WHERE id = ?",
            (session_id,),
        )
        row = cur.execute(
            "SELECT questions_used FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()
    return row["questions_used"] if row else 0


def sessions_from_ip_today(ip_hash: str) -> int:
    with cursor() as cur:
        row = cur.execute(
            "SELECT COUNT(*) AS n FROM sessions WHERE ip_hash = ? AND created_at >= ?",
            (ip_hash, date.today().isoformat()),
        ).fetchone()
    return row["n"] if row else 0


# --- spend ------------------------------------------------------------------


def record_spend(cost_micros: int) -> dict[str, int]:
    today = date.today().isoformat()
    with cursor() as cur:
        cur.execute(
            "INSERT INTO daily_usage (day, questions, cost_micros) VALUES (?, 1, ?) "
            "ON CONFLICT(day) DO UPDATE SET questions = questions + 1, "
            "cost_micros = cost_micros + excluded.cost_micros",
            (today, cost_micros),
        )
        row = cur.execute("SELECT * FROM daily_usage WHERE day = ?", (today,)).fetchone()
    return dict(row)


def spend_today() -> int:
    with cursor() as cur:
        row = cur.execute(
            "SELECT cost_micros FROM daily_usage WHERE day = ?", (date.today().isoformat(),)
        ).fetchone()
    return row["cost_micros"] if row else 0


# --- interview requests -----------------------------------------------------


def create_interview_request(
    *, name: str, email: str, window_id: str, message: str | None
) -> str:
    ref = "IR-" + secrets.token_hex(3).upper()
    with cursor() as cur:
        cur.execute(
            "INSERT INTO interview_requests (ref, created_at, name, email, window_id, message) "
            "VALUES (?,?,?,?,?,?)",
            (
                ref,
                datetime.now(UTC).isoformat(timespec="seconds"),
                name,
                email,
                window_id,
                message,
            ),
        )
    return ref


def list_interview_requests() -> list[dict[str, Any]]:
    """Only the admin endpoint calls this. Nothing else may read this table."""
    with cursor() as cur:
        rows = cur.execute(
            "SELECT * FROM interview_requests ORDER BY created_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]
