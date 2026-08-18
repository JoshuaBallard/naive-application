"""Evidence schema.

Every fact this application can state about Josh is one of these records, and every
record was read by a human before `approved` became true. There is no other source.

Two rules encoded here rather than remembered:

  - `extra="forbid"` — a typo'd field is a build failure, not a silently dropped one.
  - `approved` has no default — you cannot forget to think about it.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field, field_validator, model_validator

ID_PATTERN = r"^[a-z]+\.[a-z0-9-]+$"

SourceClass = Literal["self_authored", "public_artifact", "third_party"]

# How a single claim can be checked by someone who does not trust us.
Verification = Literal["public_artifact", "self_reported", "inferred"]

# How a requirement stands up against the evidence.
RequirementStatus = Literal["SUPPORTED", "PARTIAL", "INFERRED", "UNKNOWN", "GAP"]

RequirementCategory = Literal["must_have", "nice_to_have", "practical"]


class Strict(BaseModel):
    model_config = {"extra": "forbid", "frozen": True}


class Claim(Strict):
    """One checkable assertion.

    `public_artifact` means a stranger can verify it without asking Josh, and it must
    carry the URL that lets them. `self_reported` means they cannot. Keeping those
    apart is most of the point of this application.
    """

    claim: str
    verification: Verification
    evidence_url: str | None = None

    @model_validator(mode="after")
    def public_claims_need_a_url(self) -> Claim:
        if self.verification == "public_artifact" and not self.evidence_url:
            raise ValueError(
                f"claim is marked public_artifact but has no evidence_url: {self.claim!r}"
            )
        return self


class Link(Strict):
    label: str
    url: str
    what_it_shows: str


class Window(Strict):
    id: str = Field(pattern=r"^[a-z0-9-]+$")
    label: str
    timezone: str


class AlignmentPoint(Strict):
    point: str
    reasoning: str
    evidence_ids: list[str] = Field(default_factory=list)


class BaseRecord(Strict):
    id: str = Field(pattern=ID_PATTERN)
    approved: bool
    reviewed_on: date
    reviewed_by: str
    source_class: SourceClass
    title: str
    summary: str
    tags: list[str] = Field(default_factory=list)

    # If something was cut on the way in, say what. A bare boolean tells a reader
    # nothing and tells a future reviewer less.
    sensitive_details_removed: bool = False
    redaction_note: str | None = None

    @model_validator(mode="after")
    def redactions_are_documented(self) -> BaseRecord:
        if self.sensitive_details_removed and not self.redaction_note:
            raise ValueError(f"{self.id}: sensitive_details_removed is true but no redaction_note")
        return self

    @field_validator("summary")
    @classmethod
    def summary_is_quotable(cls, v: str) -> str:
        # The agent may repeat a summary close to verbatim, so it has to stand alone.
        if len(v.strip()) < 20:
            raise ValueError("summary is too short to be repeated on its own")
        return v.strip()


class ProfileRecord(BaseRecord):
    type: Literal["profile"]
    headline: str
    location: str
    current_status: str
    focus: list[str] = Field(default_factory=list)


class WorkHistoryRecord(BaseRecord):
    type: Literal["work_history"]
    organization: str
    role: str
    start: str
    end: str | None = None
    scope: str
    technologies: list[str] = Field(default_factory=list)

    # Work history is the one category a stranger cannot check. No commit log, no live
    # URL, no public artifact. The agent has to be able to say so, so the record says
    # so, rather than leaving it to be inferred from the absence of a link.
    verification: Verification = "self_reported"

    # Set when the organization is described rather than named, so the agent can
    # explain the omission instead of looking evasive about it.
    disclosure_note: str | None = None


class ProjectRecord(BaseRecord):
    type: Literal["project"]
    problem: str
    what_josh_built: str
    what_josh_learned: str
    technologies: list[str] = Field(default_factory=list)
    public_url: str | None = None
    public_repo: str | None = None
    verified_claims: list[Claim] = Field(default_factory=list)
    known_limitations: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def limitations_are_not_optional(self) -> ProjectRecord:
        if not self.known_limitations:
            raise ValueError(f"{self.id}: every project states at least one known limitation")
        return self


class RoleRequirementRecord(BaseRecord):
    type: Literal["role_requirement"]
    requirement: str
    category: RequirementCategory
    status: RequirementStatus
    reasoning: str
    evidence_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def supported_means_supported(self) -> RoleRequirementRecord:
        if self.status in ("SUPPORTED", "PARTIAL") and not self.evidence_ids:
            raise ValueError(f"{self.id}: status {self.status} requires at least one evidence_id")
        return self


class GapRecord(BaseRecord):
    type: Literal["gap"]
    gap: str
    why_it_matters: str
    honest_mitigation: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)


class BeliefRecord(BaseRecord):
    type: Literal["belief"]
    belief: str
    reasoning: str
    origin_ids: list[str] = Field(default_factory=list)


class FailureRecord(BaseRecord):
    type: Literal["failure"]
    what_happened: str
    what_it_taught: str
    fix: str
    evidence_url: str | None = None


class LinkRecord(BaseRecord):
    type: Literal["link"]
    links: list[Link]


class AvailabilityRecord(BaseRecord):
    type: Literal["availability"]
    windows: list[Window]
    booking_note: str


class AlignmentRecord(BaseRecord):
    type: Literal["alignment"]
    points: list[AlignmentPoint]


Record = Annotated[
    Union[
        ProfileRecord,
        WorkHistoryRecord,
        ProjectRecord,
        RoleRequirementRecord,
        GapRecord,
        BeliefRecord,
        FailureRecord,
        LinkRecord,
        AvailabilityRecord,
        AlignmentRecord,
    ],
    Field(discriminator="type"),
]


class RecordAdapter(BaseModel):
    """Wrapper so a single record can be validated through the discriminated union."""

    model_config = {"extra": "forbid"}
    record: Record
