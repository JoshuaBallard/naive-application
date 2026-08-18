"""The service's guards.

Everything here is about what happens when someone is not using the application the way
it was meant to be used, which is the only interesting case.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app import db, main
from app.agent.loop import AgentResult


class FakeRunner:
    def __init__(self) -> None:
        self.calls = 0

    def run(self, question: str, *, interview_sink: Any) -> AgentResult:
        self.calls += 1
        return AgentResult(
            answer={
                "answer": "A verified answer.",
                "classification": "IN_SCOPE",
                "verdict": "not_applicable",
                "confidence": "medium",
                "confidence_basis": "fixture",
                "claims": [{"statement": "x", "support": "SUPPORTED", "citations": []}],
                "gaps_acknowledged": [],
            },
            trace={"tools_invoked": [{"tool": "get_profile"}], "evidence_used": ["profile.josh"]},
            verification="passed",
            usage={"input_tokens": 100, "output_tokens": 50, "cache_read_input_tokens": 90},
        )


ADMIN = "test-admin-token"


@pytest.fixture
def client(monkeypatch, tmp_path):
    # Pinned explicitly rather than read from the environment. These used to come from
    # os.environ.setdefault in conftest, which silently stopped working the moment a
    # real ADMIN_TOKEN appeared in .env — a test that depends on ambient environment
    # passes for the wrong reason right up until it fails for one.
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "api.db")
    monkeypatch.setattr(main, "ADMIN_TOKEN", ADMIN)
    monkeypatch.setattr(main, "RUNNER", FakeRunner())
    db.init()
    with TestClient(main.app) as c:
        yield c


def session(client) -> str:
    return client.post("/api/session").json()["session_id"]


# --- reads ------------------------------------------------------------------


def test_health_reports_the_evidence_build(client) -> None:
    body = client.get("/health").json()
    assert body["ok"] is True
    assert body["records"] > 40


def test_evidence_endpoint_returns_only_approved_records(client) -> None:
    body = client.get("/api/evidence").json()
    assert body["count"] == len(body["records"])
    assert all(r["approved"] is True for r in body["records"])


def test_architecture_publishes_the_prompt_and_tools(client) -> None:
    """Extracting the system prompt should be a link, not an exploit."""
    body = client.get("/api/architecture").json()

    assert "Your objective" in body["system_prompt"]
    assert len(body["tools"]) == 9
    assert "filesystem" in body["absent_capabilities"]


def test_fit_endpoint_reports_the_computed_verdict(client) -> None:
    body = client.get("/api/fit").json()
    assert body["assessment"]["verdict"] == "interesting_partial_fit"
    assert body["assessment"]["practical_fit"].startswith("unresolved")


# --- the question budget ----------------------------------------------------


def test_a_session_gets_exactly_its_budget_and_then_stops(client) -> None:
    sid = session(client)

    for expected in range(main.CONFIG.questions_per_session - 1, -1, -1):
        body = client.post("/api/ask", json={"session_id": sid, "question": "why?"}).json()
        assert body["questions_remaining"] == expected

    spent = client.post("/api/ask", json={"session_id": sid, "question": "one more?"})
    assert spent.status_code == 429
    assert "still browsable" in spent.json()["detail"]


def test_an_unknown_session_cannot_ask(client) -> None:
    assert client.post("/api/ask", json={"session_id": "nope-nope-nope", "question": "hi"}).status_code == 404


def test_an_overlong_question_is_rejected_by_validation(client) -> None:
    sid = session(client)
    r = client.post("/api/ask", json={"session_id": sid, "question": "x" * 5000})
    assert r.status_code == 422


def test_sessions_per_address_are_capped(client, monkeypatch) -> None:
    monkeypatch.setattr(main, "MAX_SESSIONS_PER_IP_PER_DAY", 2)
    assert client.post("/api/session").status_code == 200
    assert client.post("/api/session").status_code == 200
    assert client.post("/api/session").status_code == 429


def test_the_daily_spend_cap_degrades_gracefully(client, monkeypatch) -> None:
    """Out of budget is a designed state with an explanation, not a 500."""
    sid = session(client)
    monkeypatch.setattr(main, "DAILY_SPEND_CAP_MICROS", 1)
    db.record_spend(10_000)

    r = client.post("/api/ask", json={"session_id": sid, "question": "why?"})

    assert r.status_code == 503
    assert "deliberate cap, not an outage" in r.json()["detail"]


# --- the only write ---------------------------------------------------------


def test_an_interview_request_is_recorded_as_pending(client) -> None:
    sid = session(client)
    body = client.post("/api/interview", json={
        "session_id": sid, "name": "Sean", "email": "sean@example.com",
        "window_id": "thu-midday-et", "message": "Let's talk.",
    }).json()

    assert body["status"] == "pending_human_approval"
    assert body["reference"].startswith("IR-")
    assert "no invitation was created" in body["what_happens_next"]


def test_an_unapproved_window_is_refused(client) -> None:
    sid = session(client)
    r = client.post("/api/interview", json={
        "session_id": sid, "name": "Sean", "email": "sean@example.com",
        "window_id": "whenever-i-like",
    })
    assert r.status_code == 400


def test_the_honeypot_answers_normally_and_stores_nothing(client) -> None:
    sid = session(client)
    body = client.post("/api/interview", json={
        "session_id": sid, "name": "Bot", "email": "bot@example.com",
        "window_id": "thu-midday-et", "website": "http://spam.example",
    }).json()

    assert body["status"] == "pending_human_approval"
    assert db.list_interview_requests() == []


def test_personal_data_is_never_returned_by_a_public_endpoint(client) -> None:
    sid = session(client)
    client.post("/api/interview", json={
        "session_id": sid, "name": "Sean", "email": "sean@example.com",
        "window_id": "thu-midday-et", "message": "private note",
    })

    for path in ("/api/evidence", "/api/fit", "/api/architecture", "/api/availability", "/health"):
        body = client.get(path).text
        assert "sean@example.com" not in body
        assert "private note" not in body


# --- admin ------------------------------------------------------------------


def test_admin_is_invisible_without_a_token(client) -> None:
    """404, not 401. An endpoint that admits it exists is an endpoint worth attacking."""
    assert client.get("/api/admin/interviews").status_code == 404
    assert client.get("/api/admin/interviews", headers={"x-admin-token": "wrong"}).status_code == 404


def test_admin_returns_requests_with_the_right_token(client) -> None:
    sid = session(client)
    client.post("/api/interview", json={
        "session_id": sid, "name": "Sean", "email": "sean@example.com",
        "window_id": "fri-midday-et",
    })

    body = client.get(
        "/api/admin/interviews", headers={"x-admin-token": ADMIN}
    ).json()

    assert body["requests"][0]["email"] == "sean@example.com"
    assert body["requests"][0]["status"] == "pending_human_approval"


# --- logging ----------------------------------------------------------------


def test_the_logger_drops_a_line_carrying_a_forbidden_field(caplog) -> None:
    from app.observability import log

    with caplog.at_level("ERROR", logger="naive-application"):
        log("ask.answered", question="what is his home address?", verdict="x")

    assert "logging.forbidden_field" in caplog.text
    assert "home address" not in caplog.text


def test_the_logger_drops_unknown_fields_silently(caplog) -> None:
    from app.observability import log

    with caplog.at_level("INFO", logger="naive-application"):
        log("ask.answered", verdict="strong_fit", some_new_field="not on the allowlist")

    line = json.loads(caplog.records[-1].message)
    assert line["verdict"] == "strong_fit"
    assert "some_new_field" not in line


def test_ip_hashes_are_salted_and_short(monkeypatch) -> None:
    from app.observability import hash_ip

    hashed = hash_ip("203.0.113.14")
    assert "203.0.113.14" not in hashed
    assert len(hashed) == 16


def test_no_raw_address_reaches_the_logs(client, caplog) -> None:
    """DISCLOSURE.md promises addresses are only ever stored hashed. uvicorn's default
    access log breaks that promise, which is why the container disables it."""
    from app.observability import log

    with caplog.at_level("INFO", logger="naive-application"):
        client.post("/api/session")
        log("session.created", ip_hash="deadbeefdeadbeef")

    assert "testclient" not in caplog.text
    assert "127.0.0.1" not in caplog.text
    assert "deadbeefdeadbeef" in caplog.text
