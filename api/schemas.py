"""Pydantic v2 request and response models."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from authentication import USERNAME_PATTERN, validate_new_account
from src.data.complaints import DISTRICTS

DISTRICT_LOOKUP = {district.casefold(): district for district in DISTRICTS}
Role = Literal["citizen", "partner", "admin"]
Severity = Literal["unknown", "low", "medium", "high", "critical"]
ComplaintStatus = Literal["pending", "clustered", "merged", "rejected"]
ChallengeStatus = Literal["draft", "under_review", "published", "archived"]
MatchStatus = Literal["suggested", "confirmed", "declined", "expressed_interest"]


def _clean_username(value: str) -> str:
    value = value.strip()
    if not USERNAME_PATTERN.fullmatch(value):
        raise ValueError(
            "Username must be 3-32 characters, start with a letter or number, "
            "and use only letters, numbers, dots, underscores, or hyphens."
        )
    return value


EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")


def _clean_email(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    if len(value) > 254 or not EMAIL_PATTERN.fullmatch(value):
        raise ValueError("email must be a valid address, for example name@example.com.")
    return value


def _clean_district(value: str | None) -> str | None:
    if value is None:
        return None
    district = DISTRICT_LOOKUP.get(str(value).strip().casefold())
    if district is None:
        raise ValueError("district must be one of the 24 Jharkhand districts.")
    return district


def _collapse(value: str) -> str:
    return " ".join(value.split())


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=12, max_length=128)
    password_confirmation: str = Field(min_length=12, max_length=128)
    full_name: str = Field(default="", max_length=120)
    email: str = Field(min_length=3, max_length=254)
    district: str | None = None

    @field_validator("username")
    @classmethod
    def username_is_valid(cls, value: str) -> str:
        return _clean_username(value)

    @field_validator("email")
    @classmethod
    def email_is_valid(cls, value: str) -> str:
        cleaned = _clean_email(value)
        if cleaned is None:
            raise ValueError("An email address is required.")
        return cleaned

    @field_validator("district")
    @classmethod
    def district_is_known(cls, value: str | None) -> str | None:
        return _clean_district(value)

    @field_validator("password_confirmation")
    @classmethod
    def passwords_match(cls, value: str, info) -> str:
        password = info.data.get("password")
        if password is not None and value != password:
            raise ValueError("The password confirmation does not match.")
        return value


class PartnerRegisterRequest(RegisterRequest):
    organization_name: str = Field(min_length=1, max_length=160)
    job_title: str = Field(min_length=1, max_length=120)

    @field_validator("organization_name", "job_title")
    @classmethod
    def details_are_not_blank(cls, value: str) -> str:
        normalized = _collapse(value)
        if not normalized:
            raise ValueError("This field must not be blank.")
        return normalized


class UserResponse(BaseModel):
    id: int
    username: str
    full_name: str = ""
    email: str | None = None
    role: Role
    district: str | None = None
    organization_id: int | None = None


class PartnerRegistrationResponse(BaseModel):
    message: str


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)
    role: Role

    @field_validator("email")
    @classmethod
    def email_is_valid(cls, value: str) -> str:
        cleaned = _clean_email(value)
        if cleaned is None:
            raise ValueError("An email address is required.")
        return cleaned


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int


class LoginResponse(TokenPair):
    user: UserResponse


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class ComplaintCreate(BaseModel):
    district: str = Field(min_length=1, max_length=80)
    place: str = Field(default="", max_length=200)
    report_text: str = Field(min_length=1, max_length=10_000)
    language: str = Field(default="unknown", max_length=20)
    severity: Severity = "unknown"
    affected_population: int | None = Field(default=None, ge=0, le=10_000_000)

    @field_validator("district")
    @classmethod
    def district_is_known(cls, value: str) -> str:
        district = _clean_district(value)
        assert district is not None  # a required field cannot resolve to None
        return district

    @field_validator("place")
    @classmethod
    def collapse_place_whitespace(cls, value: str) -> str:
        return _collapse(value)

    @field_validator("report_text")
    @classmethod
    def collapse_report_whitespace(cls, value: str) -> str:
        normalized = _collapse(value)
        if not normalized:
            raise ValueError("This field must not be blank.")
        return normalized


class DuplicateCandidate(BaseModel):
    report_id: str
    similarity: float
    district: str
    report_text: str


class ComplaintResponse(BaseModel):
    report_id: str
    district: str
    place: str
    report_text: str
    language: str
    severity: Severity
    affected_population: int | None
    status: ComplaintStatus
    duplicate_of: str | None
    reported_at: str
    created_at: str
    source: str
    is_synthetic: int
    staff_response_status: Literal[
        "acknowledged", "in_progress", "resolved", "unable_to_resolve"
    ] | None = None
    staff_response_text: str | None = None
    staff_responded_at: str | None = None


class ComplaintSubmitResponse(ComplaintResponse):
    duplicate_candidates: list[DuplicateCandidate] = []


class MergeRequest(BaseModel):
    keep_report_id: str = Field(min_length=1, max_length=64)


class FeedbackCreate(BaseModel):
    status: Literal["Not solved", "Partially solved", "Solved"]
    feedback_text: str = Field(default="", max_length=2000)

    @field_validator("feedback_text")
    @classmethod
    def collapse_whitespace(cls, value: str) -> str:
        return _collapse(value)


class FeedbackResponse(BaseModel):
    feedback_id: int
    report_id: str
    status: Literal["Not solved", "Partially solved", "Solved"]
    feedback_text: str
    submitted_at: str


class StaffResponseCreate(BaseModel):
    status: Literal["acknowledged", "in_progress", "resolved", "unable_to_resolve"]
    response_text: str = Field(min_length=1, max_length=2000)

    @field_validator("response_text")
    @classmethod
    def response_is_not_blank(cls, value: str) -> str:
        value = _collapse(value)
        if not value:
            raise ValueError("A response is required.")
        return value


class StaffResponse(BaseModel):
    response_id: int
    report_id: str
    status: Literal["acknowledged", "in_progress", "resolved", "unable_to_resolve"]
    response_text: str
    created_at: str


class ChallengeResponse(BaseModel):
    id: int
    slug: str
    title: str
    summary: str
    domain: str
    complaint_count: int
    affected_total: int
    severity_score: float
    severity: str = "unknown"
    tags: list[str] = []
    priority_score: float
    priority_breakdown: dict
    status: ChallengeStatus
    published_at: str | None
    district_count: int = 0
    district_names: list[str] = []
    first_reported_at: str | None = None
    last_reported_at: str | None = None


class ChallengeDistrict(BaseModel):
    district: str
    complaints: int


class ChallengeEvidence(BaseModel):
    quote: str
    district: str
    reported_at: str
    language: str


class ChallengeTrend(BaseModel):
    month: str
    complaints: int


class ChallengeDetailResponse(ChallengeResponse):
    """A challenge plus the report-derived content its brief renders."""

    districts: list[ChallengeDistrict] = []
    evidence: list[ChallengeEvidence] = []
    timeline: list[ChallengeTrend] = []


class ChallengeUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=160)
    summary: str | None = Field(default=None, max_length=2000)
    domain: str | None = Field(default=None, max_length=80)


class MatchResponse(BaseModel):
    id: int
    challenge_slug: str
    challenge_title: str
    organization_id: int
    organization_name: str
    organization_type: str = ""
    organization_districts: list[str] = []
    score: float
    breakdown: dict
    status: MatchStatus


class MatchDecision(BaseModel):
    action: Literal["confirm", "decline"]


class PartnerResponse(BaseModel):
    id: int
    name: str
    org_type: str
    capability_tags: list[str]
    districts: list[str]
    capacity: float
    contact_email: str


class AdminUserResponse(BaseModel):
    id: int
    username: str
    full_name: str = ""
    email: str | None = None
    role: Role
    district: str | None = None
    organization_id: int | None = None
    organization_name: str | None = None
    job_title: str = ""
    approval_pending: bool = False
    is_active: bool
    created_at: str


class AdminUserUpdate(BaseModel):
    """Fields an administrator may change on another account.

    ``exclude_unset`` in the router keeps omission distinct from an explicit
    null, so a district or organisation link can be cleared without a
    separate endpoint.
    """

    role: Role | None = None
    is_active: bool | None = None
    email: str | None = Field(default=None, min_length=3, max_length=254)
    district: str | None = Field(default=None, max_length=80)
    organization_id: int | None = Field(default=None, ge=1)

    @field_validator("district")
    @classmethod
    def district_is_known(cls, value: str | None) -> str | None:
        return _clean_district(value)

    @field_validator("email", mode="before")
    @classmethod
    def email_is_valid(cls, value: str | None) -> str | None:
        cleaned = _clean_email(value)
        if cleaned is None:
            raise ValueError("An email address is required and cannot be cleared.")
        return cleaned


class AdminUserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=12, max_length=128)
    role: Role = "partner"
    full_name: str = Field(default="", max_length=120)
    email: str = Field(min_length=3, max_length=254)
    district: str | None = None
    organization_id: int | None = Field(default=None, ge=1)

    @field_validator("username")
    @classmethod
    def username_is_valid(cls, value: str) -> str:
        return _clean_username(value)

    @field_validator("district")
    @classmethod
    def district_is_known(cls, value: str | None) -> str | None:
        return _clean_district(value)

    @field_validator("email")
    @classmethod
    def email_is_valid(cls, value: str) -> str:
        cleaned = _clean_email(value)
        if cleaned is None:
            raise ValueError("An email address is required.")
        return cleaned

    def validated(self) -> None:
        validate_new_account(self.username, self.password, self.password)


class ReclusterRequest(BaseModel):
    clusters: int | None = Field(default=None, ge=2, le=40)


class ReclusterResponse(BaseModel):
    challenges_created: int
    complaints_clustered: int
    matches_created: int


class DistrictStat(BaseModel):
    district: str
    complaints: int
    severity_mean: float


class TrendPoint(BaseModel):
    month: str
    domain: str
    complaints: int


class StatsResponse(BaseModel):
    users: int
    complaints: int
    pending: int
    clustered: int
    merged: int
    challenges: int
    published: int
    matches: int
    feedback: int


class HealthResponse(BaseModel):
    status: Literal["ok"]
    database: Literal["ok"]
    version: str
