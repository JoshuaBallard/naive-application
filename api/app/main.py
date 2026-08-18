"""The API service.

This is the only process that holds the model key, the compiled evidence, and the agent
loop. The web tier is a renderer that can call these endpoints and nothing else, which
is the reason the split exists rather than a consequence of it.

Every endpoint here is either a read of evidence that is public by construction, or the
one write that a human has to approve.
"""

from __future__ import annotations

import os
import time
from typing import Annotated, Any

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field

from app import db
from app.agent import rubric
from app.agent.config import CONFIG
from app.agent.loop import AgentRunner, QuestionTooLong
from app.agent.prompt import SYSTEM_PROMPT
from app.agent.trace import Trace
from app.evidence.lint import build_rules
from app.evidence.store import EvidenceStore
from app.observability import hash_ip, log
from app.tools.registry import build_registry

# Sonnet 5 introductory pricing, in micro-dollars per million tokens.
PRICE_INPUT = 2_000_000
PRICE_CACHED = 200_000
PRICE_OUTPUT = 10_000_000

DAILY_SPEND_CAP_MICROS = int(os.environ.get("DAILY_SPEND_CAP_USD", "3")) * 1_000_000
MAX_SESSIONS_PER_IP_PER_DAY = int(os.environ.get("MAX_SESSIONS_PER_IP", "6"))
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "")
ALLOWED_ORIGINS = [o for o in os.environ.get("ALLOWED_ORIGINS", "").split(",") if o]

@asynccontextmanager
async def lifespan(_: FastAPI):
    db.init()
    log("startup", detail=f"{STORE.record_count} records, build {STORE.content_hash[:12]}")
    yield


app = FastAPI(title="Application agent", docs_url=None, redoc_url=None, lifespan=lifespan)

@app.middleware("http")
async def security_headers(request: Request, call_next):
    """The API is normally reached through the web tier's server-side proxy, so a
    browser rarely sees these. They are set anyway: "nobody should be calling this
    directly" is an assumption, and assumptions are what get tested."""
    response = await call_next(request)
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Frame-Options"] = "DENY"
    return response


app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS or ["http://localhost:3000"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["content-type"],
)

STORE = EvidenceStore.load()
RULES = build_rules()
RUNNER = AgentRunner(STORE, RULES)


# --- helpers ----------------------------------------------------------------


def client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    return forwarded.split(",")[0].strip() if forwarded else (
        request.client.host if request.client else None
    )


def cost_micros(usage: dict[str, int]) -> int:
    cached = usage.get("cache_read_input_tokens", 0)
    fresh = max(usage.get("input_tokens", 0) - cached, 0)
    return round(
        fresh / 1e6 * PRICE_INPUT
        + cached / 1e6 * PRICE_CACHED
        + usage.get("output_tokens", 0) / 1e6 * PRICE_OUTPUT
    )


class Sink:
    """The only write in the system."""

    def record(self, *, name: str, email: str, window_id: str, message: str | None) -> str:
        return db.create_interview_request(
            name=name, email=email, window_id=window_id, message=message
        )


# --- reads: public by construction ------------------------------------------


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "ok": True,
        "records": STORE.record_count,
        "evidence_build": STORE.content_hash[:12],
    }


@app.get("/api/evidence")
def evidence() -> dict[str, Any]:
    """The agent's entire world model.

    Shipping this to a browser is safe because a record that could not be published
    could not have been compiled. There is one definition of public here, not two.
    """
    return {
        "build": STORE.content_hash,
        "built_at": STORE.built_at,
        "count": STORE.record_count,
        "records": STORE.all_records(),
    }


@app.get("/api/fit")
def fit() -> dict[str, Any]:
    assessment = rubric.evaluate(
        STORE.by_type("role_requirement"),
        STORE.by_type("gap"),
        {r["id"]: r for r in STORE.all_records()},
    )
    return {
        "assessment": assessment.to_dict(),
        "requirements": STORE.by_type("role_requirement"),
        "gaps": STORE.by_type("gap"),
    }


@app.get("/api/architecture")
def architecture() -> dict[str, Any]:
    """The system prompt and tool list, published on purpose.

    If extracting either were a meaningful attack, the security would be in the wrong
    place. Publishing them turns "print your system prompt" from an exploit into a link.
    """
    registry = build_registry(STORE, interview_sink=Sink(), trace=Trace())
    return {
        "model": CONFIG.model,
        "effort": CONFIG.effort,
        "questions_per_session": CONFIG.questions_per_session,
        "system_prompt": SYSTEM_PROMPT,
        "tools": registry.schemas(),
        "absent_capabilities": [
            "filesystem", "shell", "network fetch", "repository access",
            "database queries", "environment variables", "calendar", "email",
        ],
    }


@app.get("/api/availability")
def availability() -> dict[str, Any]:
    return {"records": STORE.by_type("availability")}


# --- the conversation --------------------------------------------------------


class SessionOut(BaseModel):
    session_id: str
    questions_remaining: int
    questions_per_session: int


@app.post("/api/session", response_model=SessionOut)
def new_session(request: Request) -> SessionOut:
    ip_hash = hash_ip(client_ip(request))

    if db.sessions_from_ip_today(ip_hash) >= MAX_SESSIONS_PER_IP_PER_DAY:
        log("session.rate_limited", ip_hash=ip_hash)
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "This address has opened enough sessions for one day. The evidence is all "
            "browsable without asking a question.",
        )

    session_id = db.create_session(ip_hash)
    log("session.created", ip_hash=ip_hash)
    return SessionOut(
        session_id=session_id,
        questions_remaining=CONFIG.questions_per_session,
        questions_per_session=CONFIG.questions_per_session,
    )


class AskIn(BaseModel):
    session_id: str = Field(min_length=8, max_length=64)
    question: str = Field(min_length=2, max_length=CONFIG.max_question_chars)


@app.post("/api/ask")
def ask(payload: AskIn, request: Request) -> dict[str, Any]:
    started = time.perf_counter()
    ip_hash = hash_ip(client_ip(request))

    session = db.get_session(payload.session_id)
    if session is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such session.")

    remaining = CONFIG.questions_per_session - session["questions_used"]
    if remaining <= 0:
        log("ask.budget_exhausted", ip_hash=ip_hash)
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"That was all {CONFIG.questions_per_session} questions. The full evidence "
            "set and the fit assessment are still browsable — nothing is behind the "
            "conversation.",
        )

    if db.spend_today() >= DAILY_SPEND_CAP_MICROS:
        log("ask.spend_cap", ip_hash=ip_hash)
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "The agent has spent its budget for today. This is a deliberate cap, not an "
            "outage. The evidence and the fit assessment do not need the model.",
        )

    try:
        result = RUNNER.run(payload.question, interview_sink=Sink())
    except QuestionTooLong as exc:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, str(exc)) from exc

    used = db.spend_question(payload.session_id)
    micros = cost_micros(result.usage)
    db.record_spend(micros)

    support = {"SUPPORTED": 0, "INFERRED": 0, "UNKNOWN": 0}
    for claim in result.answer["claims"]:
        support[claim["support"]] += 1

    log(
        "ask.answered",
        route="/api/ask",
        ip_hash=ip_hash,
        classification=result.answer["classification"],
        verdict=result.answer["verdict"],
        verification=result.verification,
        refusal=result.failed_closed,
        tools=[c["tool"] for c in result.trace["tools_invoked"]],
        evidence_count=len(result.trace["evidence_used"]),
        claims=len(result.answer["claims"]),
        support_counts=support,
        session_questions_used=used,
        latency_ms=int((time.perf_counter() - started) * 1000),
        input_tokens=result.usage.get("input_tokens", 0),
        output_tokens=result.usage.get("output_tokens", 0),
        cached_tokens=result.usage.get("cache_read_input_tokens", 0),
        cost_micros=micros,
    )

    return {
        "answer": result.answer,
        "trace": result.trace,
        "questions_remaining": max(CONFIG.questions_per_session - used, 0),
    }


# --- the only consequential action -------------------------------------------


class InterviewIn(BaseModel):
    session_id: str = Field(min_length=8, max_length=64)
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    window_id: str = Field(min_length=1, max_length=40)
    message: str | None = Field(default=None, max_length=2000)
    # Bots fill this in. People do not see it.
    website: str | None = Field(default=None, max_length=200)


@app.post("/api/interview")
def interview(payload: InterviewIn, request: Request) -> dict[str, Any]:
    ip_hash = hash_ip(client_ip(request))

    if payload.website:
        # Honeypot. Answer as though it worked; record nothing.
        log("interview.honeypot", ip_hash=ip_hash)
        return {"status": "pending_human_approval", "reference": "IR-000000"}

    if db.get_session(payload.session_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such session.")

    valid_windows = {
        w["id"] for record in STORE.by_type("availability") for w in record["windows"]
    }
    if payload.window_id not in valid_windows:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Not an approved window.")

    ref = db.create_interview_request(
        name=payload.name,
        email=payload.email,
        window_id=payload.window_id,
        message=payload.message,
    )

    # Note what is absent from this log line: name, email, and the message.
    log("interview.recorded", ip_hash=ip_hash, detail=ref)

    return {
        "status": "pending_human_approval",
        "reference": ref,
        "what_happens_next": (
            "Recorded for Josh to read. Nothing was sent to a calendar, no invitation "
            "was created, and no email was sent to anyone. He confirms by hand or not "
            "at all."
        ),
    }


# --- admin -------------------------------------------------------------------


def require_admin(x_admin_token: Annotated[str | None, Header()] = None) -> None:
    import secrets as _secrets

    if not ADMIN_TOKEN or not x_admin_token:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found.")
    if not _secrets.compare_digest(x_admin_token, ADMIN_TOKEN):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found.")


@app.get("/api/admin/interviews", dependencies=[Depends(require_admin)])
def admin_interviews() -> dict[str, Any]:
    """The only read path that returns personal data. Josh, by hand, with a token."""
    return {"requests": db.list_interview_requests()}
