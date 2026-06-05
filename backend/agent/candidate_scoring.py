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


def interpret_match_score(score: int) -> dict[str, str]:
    if score >= 80:
        return {
            "match_level": "Recruiter Screen",
            "recommendation": "Strong enough for recruiter outreach",
        }
    if score >= 65:
        return {
            "match_level": "Potential Match",
            "recommendation": "Review before outreach",
        }
    if score >= 50:
        return {
            "match_level": "Consider",
            "recommendation": "Possible fit with gaps",
        }
    if score >= 35:
        return {
            "match_level": "Low Match",
            "recommendation": "Unlikely fit",
        }
    return {
        "match_level": "Not Recommended",
        "recommendation": "Do not prioritize",
    }


def append_match_interpretation(fit_reason: str, score: int) -> str:
    interpretation = interpret_match_score(score)
    guidance = interpretation["match_level"]
    cleaned_reason = _remove_existing_match_guidance(fit_reason)
    if cleaned_reason.startswith(guidance):
        return cleaned_reason
    return f"{cleaned_reason} Recruiter guidance: {guidance}."


def _score_candidate(
    candidate: CandidateProfile,
    jd_signals: JDSignals,
    strategy: CandidateSearchStrategy,
    manager_preferences: list[str],
) -> CandidateMatch:
    candidate_text = _candidate_search_text(candidate)
    alias_map = _alias_map(jd_signals)
    matched_skills = _matched_skills(jd_signals, strategy, candidate_text, alias_map)
    matched_manager_preferences = [
        preference
        for preference in manager_preferences
        if _term_matches_text(preference, candidate_text)
    ]

    required_skill_coverage = _coverage(jd_signals.required_skills, candidate_text, alias_map)
    background_coverage = _background_coverage(
        candidate_text,
        jd_signals.role_type,
        strategy.target_backgrounds,
        jd_signals.adjacent_backgrounds,
    )
    keyword_coverage = _coverage(strategy.keywords, candidate_text, alias_map)
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
    fit_reason = _fit_reason(
        candidate,
        matched_skills,
        matched_manager_preferences,
        jd_signals,
        score,
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


def _matched_skills(
    jd_signals: JDSignals,
    strategy: CandidateSearchStrategy,
    candidate_text: str,
    alias_map: dict[str, list[str]],
) -> list[str]:
    canonical_terms = [
        *jd_signals.required_skills,
        *strategy.keywords,
    ]
    matches = [
        term
        for term in canonical_terms
        if _term_or_alias_matches_text(term, candidate_text, alias_map)
    ]

    return list(dict.fromkeys(matches))


def _count_term_hits(terms: list[str], candidate_text: str) -> int:
    return sum(1 for term in terms if _term_matches_text(term, candidate_text))


def _coverage(
    terms: list[str],
    candidate_text: str,
    alias_map: dict[str, list[str]] | None = None,
) -> float:
    unique_terms = [term for term in dict.fromkeys(terms) if term.strip()]
    if not unique_terms:
        return 0.0
    hits = sum(
        1
        for term in unique_terms
        if _term_or_alias_matches_text(term, candidate_text, alias_map or {})
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
    if _term_matches_text(background, candidate_text):
        return True

    tokens = _important_tokens(background)
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


def _alias_map(jd_signals: JDSignals) -> dict[str, list[str]]:
    aliases: dict[str, list[str]] = {}
    for canonical, values in jd_signals.related_skill_aliases.items():
        normalized_key = _normalize(canonical)
        aliases[normalized_key] = [canonical, *values]
    return aliases


def _term_or_alias_matches_text(
    term: str,
    candidate_text: str,
    alias_map: dict[str, list[str]],
) -> bool:
    candidates = [term, *alias_map.get(_normalize(term), [])]
    return any(_term_matches_text(candidate, candidate_text) for candidate in candidates)


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


def _seniority_context(candidate: CandidateProfile, jd_signals: JDSignals) -> float:
    seniority_text = _normalize(" ".join(jd_signals.seniority_indicators))
    candidate_text = _candidate_search_text(candidate)
    level = _normalize(jd_signals.seniority_level)

    if level == "intern":
        has_student_or_recent_education = any(
            marker in candidate_text
            for marker in ("student", "intern", "internship", "graduation_year", "master of science", "bachelor")
        )
        has_project_or_entry_signal = any(
            marker in candidate_text
            for marker in ("project", "built", "developed", "github", "entry", "junior")
        )
        if has_student_or_recent_education and has_project_or_entry_signal:
            return 1.0
        if has_student_or_recent_education or has_project_or_entry_signal:
            return 0.75
        return 0.4

    if level == "early":
        has_early_signal = any(
            marker in candidate_text
            for marker in ("junior", "associate", "analyst", "software engineer", "developer", "1 year", "2 years")
        )
        return 1.0 if has_early_signal else 0.6

    if level == "mid":
        has_mid_signal = any(
            marker in candidate_text
            for marker in ("engineer", "analyst", "manager", "3 years", "4 years", "5 years", "present")
        )
        return 1.0 if has_mid_signal else 0.6

    wants_senior = any(
        marker in seniority_text
        for marker in ("senior", "5+", "5 years", "minimum 5", "lead")
    )
    if level != "senior" and not wants_senior:
        return 0.8

    has_senior_signal = any(
        marker in candidate_text
        for marker in ("senior", "lead", "manager", "6 years", "strategic planning")
    )
    return 1.0 if has_senior_signal else 0.3


def _fit_reason(
    candidate: CandidateProfile,
    matched_skills: list[str],
    matched_manager_preferences: list[str],
    jd_signals: JDSignals,
    score: int,
) -> str:
    current_experience = candidate.experience[0]
    strengths = _format_phrase_list(matched_skills[:3]) or "adjacent background"
    missing = _missing_required_skills(matched_skills, jd_signals)
    gaps = _format_phrase_list(missing[:3]) or "direct evidence for the highest-priority role scope"
    role = jd_signals.role_type

    if score >= 65:
        reason = (
            f"Strongest alignment comes from {strengths}, supported by recent "
            f"{current_experience.title} work at {current_experience.company}"
        )
        if matched_manager_preferences:
            preferences = _format_phrase_list(matched_manager_preferences[:2])
            reason += f" and manager-note overlap in {preferences}"
        if missing:
            reason += f". Gaps to confirm: {gaps}."
        else:
            reason += f". This covers the core {role} requirements; confirm scope and interest."
        return reason

    if score >= 50:
        reason = (
            f"Some relevant overlap in {strengths} from {current_experience.title} "
            f"work at {current_experience.company}. Review gaps around {gaps} before outreach."
        )
        if matched_manager_preferences:
            preferences = _format_phrase_list(matched_manager_preferences[:2])
            reason += f" Manager-note overlap includes {preferences}."
        return reason

    if score >= 35:
        reason = (
            f"Limited alignment: the profile shows {strengths} in "
            f"{current_experience.title} work at {current_experience.company}, "
            f"but lacks clear evidence of {gaps}."
        )
        if matched_manager_preferences:
            preferences = _format_phrase_list(matched_manager_preferences[:2])
            reason += f" Manager-note overlap exists for {preferences}, but core JD coverage is still limited."
        return reason

    reason = (
        f"Not recommended because overlap is limited to {strengths}; the profile lacks "
        f"the core {role} requirements around {gaps}."
    )
    if matched_manager_preferences:
        preferences = _format_phrase_list(matched_manager_preferences[:2])
        reason += f" Manager-note overlap includes {preferences}, but it is not enough to prioritize."
    return reason


def _missing_required_skills(matched_skills: list[str], jd_signals: JDSignals) -> list[str]:
    required = [skill for skill in jd_signals.required_skills if skill.strip()]
    return [
        skill
        for skill in required
        if not _term_matches_any(skill, matched_skills)
    ]


def _format_phrase_list(items: list[str]) -> str:
    clean_items = [item for item in dict.fromkeys(items) if item.strip()]
    if not clean_items:
        return ""
    if len(clean_items) == 1:
        return clean_items[0]
    if len(clean_items) == 2:
        return f"{clean_items[0]} and {clean_items[1]}"
    return f"{', '.join(clean_items[:-1])}, and {clean_items[-1]}"


def _remove_existing_match_guidance(fit_reason: str) -> str:
    cleaned = re.sub(r"\s*Match interpretation:\s*[^.]+\.?", "", fit_reason).strip()
    cleaned = re.sub(r"\s*Recruiter guidance:\s*[^.]+\.?", "", cleaned).strip()
    return cleaned


def _concerns(
    candidate: CandidateProfile,
    matched_skills: list[str],
    jd_signals: JDSignals,
) -> str:
    missing = _missing_required_skills(matched_skills, jd_signals)
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


def _important_tokens(value: str) -> list[str]:
    stopwords = {
        "and",
        "or",
        "the",
        "of",
        "for",
        "to",
        "in",
        "with",
        "intern",
        "internship",
        "role",
        "candidate",
    }
    return [token for token in _tokens(value) if token not in stopwords]


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
