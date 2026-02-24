from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional


class ScrapeRequest(BaseModel):
    college_name: str = Field(..., min_length=2)
    course_name: str = Field(..., min_length=2)


class CompareRequest(BaseModel):
    colleges: List[ScrapeRequest] = Field(..., min_length=2)


class ResolvedInstitute(BaseModel):
    slug: str
    primary_id: str
    url: str


class ResolvedCourse(BaseModel):
    course_id: str
    course_name: str
    score: float


class ParsedReview(BaseModel):
    rating: Optional[float] = None
    pros: Optional[str] = None
    cons: Optional[str] = None
    title: Optional[str] = None
    year: Optional[str] = None
    reviewer_type: Optional[str] = None


class ParsedData(BaseModel):
    reviews: List[ParsedReview] = Field(default_factory=list)
    fees: Dict[str, Any] = Field(default_factory=dict)
    placement: Dict[str, Any] = Field(default_factory=dict)
    cutoff: List[Dict[str, Any]] = Field(default_factory=list)
    infrastructure: Dict[str, Any] = Field(default_factory=dict)


class ScrapeResponse(BaseModel):
    institute: ResolvedInstitute
    course: ResolvedCourse
    storage_path: str
    pages: Dict[str, str]
    parsed: ParsedData
