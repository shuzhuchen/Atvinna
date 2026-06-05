from __future__ import annotations

import re

from backend.agent.schemas import (
    CandidateMatch,
    CandidateProfile,
    CandidateSearchStrategy,
    JDSignals,
)


def score_candidates_locally(
    candidates: list[CandidateProfile],
    jd_signals: JDSignals,
    strategy: CandidateSearchStrategy,
    hiring_manager_notes: str | None = None,
) -> list[CandidateMatch]:
    manager_preferences = _extract_manager_preferences(hiring_manager_notes, candidates)
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
    candidate_text = _candidate_search_text(candidate)
    skill_values = _candidate_skills(candidate)
    matched_skills = _matched_skills(skill_values, jd_signals, strategy, candidate_text)
    matched_manager_preferences = [
        preference
        for preference in manager_preferences
        if _term_matches_text(preference, candidate_text)
    ]

    required_hits = _count_term_hits(jd_signals.required_skills, candidate_text)
    keyword_hits = _count_term_hits(strategy.keywords, candidate_text)
    background_hits = _count_term_hits(strategy.target_backgrounds, candidate_text)
    company_hits = _count_term_hits(strategy.target_companies, candidate_text)
    role_hits = _count_term_hits([jd_signals.role_type], candidate_text)
    seniority_bonus = _seniority_bonus(candidate, jd_signals)

    raw_score = (
        required_hits * 11
        + keyword_hits * 5
        + background_hits * 9
        + company_hits * 4
        + role_hits * 7
        + seniority_bonus
        + min(len(matched_skills), 6) * 3
    )
    jd_score_cap = 80 if manager_preferences else 100
    jd_score = max(0, min(jd_score_cap, 35 + raw_score))
    raw_hiring_manager_score = min(20, len(matched_manager_preferences) * 4)
    hiring_manager_score = min(raw_hiring_manager_score, 100 - jd_score)
    score = min(100, jd_score + hiring_manager_score)

    current_company = candidate.experience[0].company
    fit_reason = _fit_reason(
        candidate,
        matched_skills,
        matched_manager_preferences,
        jd_signals,
    )
    concerns = _concerns(candidate, matched_skills, jd_signals)

    return CandidateMatch(
        full_name=candidate.candidate.full_name,
        current_company=current_company,
        match_score=score,
        jd_match_score=jd_score,
        hiring_manager_score=hiring_manager_score,
        matched_skills=matched_skills[:6],
        matched_manager_preferences=matched_manager_preferences[:5],
        fit_reason=fit_reason,
        concerns=concerns,
    )


def _candidate_search_text(candidate: CandidateProfile) -> str:
    parts: list[str] = [
        candidate.candidate.full_name,
        candidate.candidate.location,
        candidate.candidate.summary,
    ]
    for education in candidate.education:
        parts.extend([education.degree, education.major, education.school])
    for experience in candidate.experience:
        parts.extend(
            [
                experience.company,
                experience.title,
                experience.location,
                *experience.responsibilities,
            ]
        )
    for skills in candidate.skills.values():
        parts.extend(skills)
    return _normalize(" ".join(parts))


def _candidate_skills(candidate: CandidateProfile) -> list[str]:
    skills: list[str] = []
    for values in candidate.skills.values():
        skills.extend(values)
    return list(dict.fromkeys(skills))


def _matched_skills(
    skills: list[str],
    jd_signals: JDSignals,
    strategy: CandidateSearchStrategy,
    candidate_text: str,
) -> list[str]:
    target_terms = [
        *jd_signals.required_skills,
        *strategy.keywords,
        jd_signals.role_type,
        *strategy.target_backgrounds,
    ]
    matches = [
        skill
        for skill in skills
        if _term_matches_any(skill, target_terms)
    ]

    for term in [*jd_signals.required_skills, *strategy.keywords]:
        if _term_matches_text(term, candidate_text):
            matches.append(term)

    return list(dict.fromkeys(matches))


def _count_term_hits(terms: list[str], candidate_text: str) -> int:
    return sum(1 for term in terms if _term_matches_text(term, candidate_text))


def _term_matches_any(term: str, targets: list[str]) -> bool:
    normalized_term = _normalize(term)
    if not normalized_term:
        return False

    if len(normalized_term) <= 2:
        return any(normalized_term == _normalize(target) for target in targets)

    return any(
        normalized_term in _normalize(target) or _normalize(target) in normalized_term
        for target in targets
        if _normalize(target)
    )


def _term_matches_text(term: str, text: str) -> bool:
    normalized_term = _normalize(term)
    if not normalized_term:
        return False
    if len(normalized_term) <= 2:
        return re.search(rf"\b{re.escape(normalized_term)}\b", text) is not None
    if normalized_term in text:
        return True

    tokens = _tokens(normalized_term)
    if len(tokens) <= 1:
        return False
    return all(token in text for token in tokens)


def _seniority_bonus(candidate: CandidateProfile, jd_signals: JDSignals) -> int:
    seniority_text = _normalize(" ".join(jd_signals.seniority_indicators))
    candidate_text = _candidate_search_text(candidate)
    wants_senior = any(
        marker in seniority_text
        for marker in ("senior", "5+", "5 years", "minimum 5", "lead")
    )
    has_senior_signal = any(
        marker in candidate_text
        for marker in ("senior", "lead", "manager", "6 years", "strategic planning")
    )
    return 8 if wants_senior and has_senior_signal else 0


def _fit_reason(
    candidate: CandidateProfile,
    matched_skills: list[str],
    matched_manager_preferences: list[str],
    jd_signals: JDSignals,
) -> str:
    top_skills = ", ".join(matched_skills[:3]) if matched_skills else "adjacent experience"
    reason = (
        f"{candidate.candidate.full_name} matches the {jd_signals.role_type} need through "
        f"{top_skills} and relevant recent experience at {candidate.experience[0].company}."
    )
    if matched_manager_preferences:
        preferences = ", ".join(matched_manager_preferences[:3])
        reason += f" Also matches hiring manager preference(s): {preferences}."
    return reason


def _concerns(
    candidate: CandidateProfile,
    matched_skills: list[str],
    jd_signals: JDSignals,
) -> str:
    required = [skill for skill in jd_signals.required_skills if skill.strip()]
    missing = [
        skill
        for skill in required
        if not _term_matches_any(skill, matched_skills)
    ]
    if missing:
        return f"Needs confirmation on {', '.join(missing[:2])}."
    return "No major concern from the database profile; confirm scope, level, and interest in recruiter screen."


def _normalize(value: str) -> str:
    return " ".join(value.lower().replace("&", " and ").split())


def _tokens(value: str) -> list[str]:
    return [
        token
        for token in re.findall(r"[a-z0-9]+", value.lower())
        if len(token) > 1
    ]


def _extract_manager_preferences(
    hiring_manager_notes: str | None,
    candidates: list[CandidateProfile],
) -> list[str]:
    if not hiring_manager_notes or not hiring_manager_notes.strip():
        return []

    normalized_notes = _normalize(hiring_manager_notes.replace("/", " "))
    preferences: list[str] = []

    for term in _candidate_preference_vocabulary(candidates):
        if _term_matches_text(term, normalized_notes):
            preferences.append(term)

    chunks = re.split(
        r"[,;/\n.]|\band\b|\bwith\b|\bwho\b|\bthat\b",
        hiring_manager_notes,
        flags=re.IGNORECASE,
    )
    for chunk in chunks:
        cleaned = _clean_preference(chunk)
        if cleaned:
            preferences.append(cleaned)

    return list(dict.fromkeys(preferences))


def _candidate_preference_vocabulary(candidates: list[CandidateProfile]) -> list[str]:
    terms: list[str] = [
        "AI",
        "AI/ML",
        "Agentic AI",
        "AWS",
        "cloud",
        "data pipelines",
        "digital content",
        "FP&A",
        "full-stack",
        "Kafka",
        "LATAM",
        "media",
        "microservices",
        "MongoDB",
        "Power BI",
        "RAG",
        "React",
        "Redis",
        "startup",
        "Tailwind CSS",
    ]
    for candidate in candidates:
        terms.extend(candidate.candidate.summary.split("."))
        for experience in candidate.experience:
            terms.extend([experience.company, experience.title])
        for skills in candidate.skills.values():
            terms.extend(skills)

    cleaned_terms = [
        term.strip()
        for term in terms
        if term.strip() and len(_tokens(term)) <= 4
    ]
    return list(dict.fromkeys(cleaned_terms))


def _clean_preference(value: str) -> str:
    cleaned = re.sub(
        r"\b(prioritize|prefer|preferred|nice to have|must have|candidates?|people|profiles?|background|experience|skills?|strong|solid)\b",
        " ",
        value,
        flags=re.IGNORECASE,
    )
    cleaned = " ".join(cleaned.strip(" :-").split())
    if not cleaned:
        return ""

    tokens = _tokens(cleaned)
    if not tokens:
        return ""
    if len(tokens) == 1 and len(tokens[0]) < 3:
        return ""
    if len(tokens) > 5:
        return ""
    return cleaned
