from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class CandidateIdentity(BaseModel):
    full_name: str
    location: str
    email: str
    phone: str
    linkedin_url: str
    summary: str


class EducationRecord(BaseModel):
    degree: str
    major: str
    school: str
    graduation_year: int


class ExperienceRecord(BaseModel):
    company: str
    title: str
    location: str
    start_date: str
    end_date: str
    responsibilities: list[str] = Field(min_length=1)


class CandidateProfile(BaseModel):
    candidate: CandidateIdentity
    education: list[EducationRecord] = Field(min_length=1)
    experience: list[ExperienceRecord] = Field(min_length=1)
    skills: dict[str, list[str]]


class JDSignals(BaseModel):
    role_type: str
    required_skills: list[str] = Field(min_length=1)
    related_skill_aliases: dict[str, list[str]] = Field(default_factory=dict)
    adjacent_backgrounds: list[str] = Field(default_factory=list)
    seniority_indicators: list[str] = Field(default_factory=list)
    seniority_level: str = "unspecified"
    company_stage: str
    missing_information: list[str] = Field(default_factory=list)
    specific_detail: str

    @field_validator("company_stage", mode="before")
    @classmethod
    def coerce_missing_company_stage(cls, value: Any) -> str:
        if value is None or value == "":
            return "Not stated"
        return value

    @field_validator("related_skill_aliases", mode="before")
    @classmethod
    def coerce_related_skill_aliases(cls, value: Any) -> dict[str, list[str]]:
        if value is None:
            return {}
        if not isinstance(value, dict):
            return {}

        aliases: dict[str, list[str]] = {}
        for key, raw_aliases in value.items():
            canonical = str(key).strip()
            if not canonical:
                continue
            if isinstance(raw_aliases, list):
                aliases[canonical] = [str(alias) for alias in raw_aliases if str(alias).strip()]
            elif isinstance(raw_aliases, str):
                aliases[canonical] = [raw_aliases]
            else:
                aliases[canonical] = [str(raw_aliases)]
        return aliases


class CandidateSearchStrategy(BaseModel):
    target_backgrounds: list[str] = Field(min_length=1)
    target_companies: list[str] = Field(min_length=1)
    keywords: list[str] = Field(min_length=1)
    seniority: str

    @field_validator("target_backgrounds", "target_companies", "keywords", mode="before")
    @classmethod
    def coerce_string_list(cls, value: Any) -> list[str]:
        if isinstance(value, list):
            if not value:
                return ["Not specified"]
            return [item if isinstance(item, str) else json.dumps(item) for item in value]
        if isinstance(value, str):
            return [value]
        if isinstance(value, dict):
            return [json.dumps(value)]
        return value


class BooleanQuery(BaseModel):
    boolean_query: str


class OutreachMessage(BaseModel):
    outreach_message: str
    specific_detail: str


class OutreachVariants(BaseModel):
    warm_direct: str
    startup_casual: str
    executive_brief: str
    specific_detail: str


class OutreachOutput(BaseModel):
    outreach_message: str
    specific_detail: str
    character_count: int
    attempts: int


class CandidateSummary(BaseModel):
    name: str
    current_company: str
    key_skills: list[str] = Field(min_length=3, max_length=5)
    fit_reason: str
    concerns: str


class CandidateMatch(BaseModel):
    full_name: str
    current_company: str
    match_score: int = Field(ge=0, le=100)
    jd_match_score: int = Field(ge=0, le=100)
    hiring_manager_score: int = Field(ge=0, le=20)
    matched_skills: list[str] = Field(default_factory=list)
    matched_manager_preferences: list[str] = Field(default_factory=list)
    fit_reason: str
    concerns: str


class TraceEntry(BaseModel):
    step: int = Field(ge=1, le=5)
    action: str
    attempt: int = Field(ge=1)
    result: Literal["pass", "retry", "fail"]
    note: str = ""


class PipelineOutput(BaseModel):
    candidate_search_strategy: CandidateSearchStrategy
    boolean_query: str
    outreach_message: OutreachOutput
    candidate_summary: CandidateSummary
    pipeline_trace: list[TraceEntry]


class PipelineApiResponse(PipelineOutput):
    candidate_matches: list[CandidateMatch]
