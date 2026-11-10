from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class Severity(StrEnum):
    critical = "critical"
    high = "high"
    medium = "medium"
    low = "low"

    @property
    def rank(self) -> int:
        return list(Severity).index(self)


class Category(StrEnum):
    correctness = "correctness"
    security = "security"
    performance = "performance"


class RawFinding(BaseModel):
    """What a reviewer model returns. The agent stamps the category afterwards."""

    file: str = Field(description="Path of the file, exactly as shown in the diff header")
    line: int = Field(ge=1, description="Line number on the new side of the diff")
    severity: Severity
    title: str = Field(description="The defect in one short sentence")
    explanation: str = Field(description="Why the code is wrong")
    failure_scenario: str = Field(
        description="Concrete input or state that triggers the defect, and what goes wrong"
    )
    suggestion: str | None = Field(default=None, description="How to fix it, if clear")
    confidence: float = Field(ge=0, le=1, description="How sure you are the defect is real")


class ReviewerOutput(BaseModel):
    findings: list[RawFinding] = Field(default_factory=list)


class Finding(RawFinding):
    category: Category
    agent: str


class SkippedFile(BaseModel):
    path: str
    reason: str


class ReviewResult(BaseModel):
    model: str
    files_reviewed: list[str]
    skipped: list[SkippedFile]
    findings: list[Finding]
    dropped: int = Field(description="Findings discarded for pointing outside the diff")
