from __future__ import annotations

from backend.agent.schemas import (
    CandidateMatch,
    CandidateProfile,
    CandidateSearchStrategy,
    JDSignals,
)
from backend.agent.scoring.fit_reason import concerns, fit_reason
from backend.agent.scoring.preference_parser import extract_manager_preferences
from backend.agent.scoring.text_match import (
    alias_map,
    candidate_search_text,
    important_tokens,
    term_matches_text,
    term_or_alias_matches_text,
)


def score_candidates_locally(
    candidates: list[CandidateProfile],
    jd_signals: JDSignals,
    strategy: CandidateSearchStrategy,
    hiring_manager_notes: str | None = None,
) -> list[CandidateMatch]:
    manager_preferences = extract_manager_preferences(hiring_manager_notes, candidates)
    matches = [
        _score_candidate(candidate, jd_signals, strategy, manager_preferences)
        for candidate in candidates
    ]
    return sorted(matches, key=lambda match: match.match_score, reverse=True)


def _score_candidate(
    candidate: CandidateProfile,
    jd_signals: JDSignals,
    strategy: CandidateSearchStrategy,
    manager_preferences: list[str],
) -> CandidateMatch:
    candidate_text = candidate_search_text(candidate)
    aliases = alias_map(jd_signals)
    matched_skills = _matched_skills(jd_signals, strategy, candidate_text, aliases)
    matched_manager_preferences = [
        preference
        for preference in manager_preferences
        if term_matches_text(preference, candidate_text)
    ]

    required_skill_coverage = _coverage(jd_signals.required_skills, candidate_text, aliases)
    background_coverage = _background_coverage(
        candidate_text,
        jd_signals.role_type,
        strategy.target_backgrounds,
        jd_signals.adjacent_backgrounds,
    )
    keyword_coverage = _coverage(strategy.keywords, candidate_text, aliases)
    seniority_context = _seniority_context(candidate, jd_signals)

    raw_jd_score = round(
        required_skill_coverage * 50
        + background_coverage * 25
        + keyword_coverage * 15
        + seniority_context * 10
    )
    score_cap = _score_cap(required_skill_coverage, background_coverage, keyword_coverage)
    jd_score = max(0, min(score_cap, raw_jd_score))
    raw_hiring_manager_score = min(15, len(matched_manager_preferences) * 3)
    hiring_manager_score = min(raw_hiring_manager_score, score_cap - jd_score)
    score = min(score_cap, jd_score + hiring_manager_score)

    current_company = candidate.experience[0].company
    return CandidateMatch(
        full_name=candidate.candidate.full_name,
        current_company=current_company,
        match_score=score,
        jd_match_score=jd_score,
        hiring_manager_score=hiring_manager_score,
        matched_skills=matched_skills[:6],
        matched_manager_preferences=matched_manager_preferences[:5],
        fit_reason=fit_reason(
            candidate,
            matched_skills,
            matched_manager_preferences,
            jd_signals,
            score,
        ),
        concerns=concerns(matched_skills, jd_signals),
    )


def _matched_skills(
    jd_signals: JDSignals,
    strategy: CandidateSearchStrategy,
    candidate_text: str,
    aliases: dict[str, list[str]],
) -> list[str]:
    canonical_terms = [
        *jd_signals.required_skills,
        *strategy.keywords,
    ]
    matches = [
        term
        for term in canonical_terms
        if term_or_alias_matches_text(term, candidate_text, aliases)
    ]

    return list(dict.fromkeys(matches))


def _coverage(
    terms: list[str],
    candidate_text: str,
    aliases: dict[str, list[str]] | None = None,
) -> float:
    unique_terms = [term for term in dict.fromkeys(terms) if term.strip()]
    if not unique_terms:
        return 0.0
    hits = sum(
        1
        for term in unique_terms
        if term_or_alias_matches_text(term, candidate_text, aliases or {})
    )
    return hits / len(unique_terms)


def _background_coverage(
    candidate_text: str,
    role_type: str,
    target_backgrounds: list[str],
    adjacent_backgrounds: list[str],
) -> float:
    role_match = 1.0 if _background_matches_text(role_type, candidate_text) else 0.0
    target_match = _background_list_coverage(target_backgrounds, candidate_text)
    adjacent_match = _background_list_coverage(adjacent_backgrounds, candidate_text) * 0.8
    return max(role_match, target_match, adjacent_match)


def _background_list_coverage(backgrounds: list[str], candidate_text: str) -> float:
    unique_backgrounds = [background for background in dict.fromkeys(backgrounds) if background.strip()]
    if not unique_backgrounds:
        return 0.0
    hits = sum(1 for background in unique_backgrounds if _background_matches_text(background, candidate_text))
    return hits / len(unique_backgrounds)


def _background_matches_text(background: str, candidate_text: str) -> bool:
    if term_matches_text(background, candidate_text):
        return True

    tokens = important_tokens(background)
    if not tokens:
        return False
    overlap = sum(1 for token in tokens if token in candidate_text)
    return overlap / len(tokens) >= 0.6


def _score_cap(
    required_skill_coverage: float,
    background_coverage: float,
    keyword_coverage: float,
) -> int:
    if required_skill_coverage >= 0.9 and background_coverage >= 0.8 and keyword_coverage >= 0.7:
        return 100
    if required_skill_coverage >= 0.75 and background_coverage >= 0.6:
        return 89
    if required_skill_coverage >= 0.6 and background_coverage > 0:
        return 79
    if required_skill_coverage >= 0.4:
        return 69
    if required_skill_coverage >= 0.2:
        return 59
    return 45


def _seniority_context(candidate: CandidateProfile, jd_signals: JDSignals) -> float:
    seniority_text = " ".join(jd_signals.seniority_indicators).lower()
    text = candidate_search_text(candidate)
    level = jd_signals.seniority_level.lower()

    if level == "intern":
        has_student_or_recent_education = any(
            marker in text
            for marker in ("student", "intern", "internship", "graduation_year", "master of science", "bachelor")
        )
        has_project_or_entry_signal = any(
            marker in text
            for marker in ("project", "built", "developed", "github", "entry", "junior")
        )
        if has_student_or_recent_education and has_project_or_entry_signal:
            return 1.0
        if has_student_or_recent_education or has_project_or_entry_signal:
            return 0.75
        return 0.4

    if level == "early":
        has_early_signal = any(
            marker in text
            for marker in ("junior", "associate", "entry", "early career", "1 year", "2 years")
        )
        return 1.0 if has_early_signal else 0.6

    if level == "mid":
        has_mid_signal = any(
            marker in text
            for marker in ("mid", "specialist", "manager", "3 years", "4 years", "5 years", "present")
        )
        return 1.0 if has_mid_signal else 0.6

    wants_senior = any(
        marker in seniority_text
        for marker in ("senior", "5+", "5 years", "minimum 5", "lead")
    )
    if level != "senior" and not wants_senior:
        return 0.8

    has_senior_signal = any(
        marker in text
        for marker in ("senior", "lead", "principal", "staff", "manager", "6 years", "7 years", "8 years")
    )
    return 1.0 if has_senior_signal else 0.3
