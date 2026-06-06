from __future__ import annotations

from backend.agent.schemas import CandidateProfile, JDSignals
from backend.agent.scoring.text_match import term_matches_any


def fit_reason(
    candidate: CandidateProfile,
    matched_skills: list[str],
    matched_manager_preferences: list[str],
    jd_signals: JDSignals,
    score: int,
) -> str:
    current_experience = candidate.experience[0]
    strengths = format_phrase_list(matched_skills[:3]) or "adjacent background"
    missing = missing_required_skills(matched_skills, jd_signals)
    gaps = format_phrase_list(missing[:3]) or "direct evidence for the highest-priority role scope"
    role = jd_signals.role_type

    if score >= 65:
        reason = (
            f"Strongest alignment comes from {strengths}, supported by recent "
            f"{current_experience.title} work at {current_experience.company}"
        )
        if matched_manager_preferences:
            preferences = format_phrase_list(matched_manager_preferences[:2])
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
            preferences = format_phrase_list(matched_manager_preferences[:2])
            reason += f" Manager-note overlap includes {preferences}."
        return reason

    if score >= 35:
        reason = (
            f"Limited alignment: the profile shows {strengths} in "
            f"{current_experience.title} work at {current_experience.company}, "
            f"but lacks clear evidence of {gaps}."
        )
        if matched_manager_preferences:
            preferences = format_phrase_list(matched_manager_preferences[:2])
            reason += f" Manager-note overlap exists for {preferences}, but core JD coverage is still limited."
        return reason

    reason = (
        f"Not recommended because overlap is limited to {strengths}; the profile lacks "
        f"the core {role} requirements around {gaps}."
    )
    if matched_manager_preferences:
        preferences = format_phrase_list(matched_manager_preferences[:2])
        reason += f" Manager-note overlap includes {preferences}, but it is not enough to prioritize."
    return reason


def concerns(
    matched_skills: list[str],
    jd_signals: JDSignals,
) -> str:
    missing = missing_required_skills(matched_skills, jd_signals)
    if missing:
        return f"Needs confirmation on {', '.join(missing[:2])}."
    return "No major concern from the database profile; confirm scope, level, and interest in recruiter screen."


def missing_required_skills(matched_skills: list[str], jd_signals: JDSignals) -> list[str]:
    required = [skill for skill in jd_signals.required_skills if skill.strip()]
    return [
        skill
        for skill in required
        if not term_matches_any(skill, matched_skills)
    ]


def format_phrase_list(items: list[str]) -> str:
    clean_items = [item for item in dict.fromkeys(items) if item.strip()]
    if not clean_items:
        return ""
    if len(clean_items) == 1:
        return clean_items[0]
    if len(clean_items) == 2:
        return f"{clean_items[0]} and {clean_items[1]}"
    return f"{', '.join(clean_items[:-1])}, and {clean_items[-1]}"
