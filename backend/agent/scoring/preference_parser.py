from __future__ import annotations

import re

from backend.agent.schemas import CandidateProfile
from backend.agent.scoring.text_match import normalize, term_matches_text, tokens


def extract_manager_preferences(
    hiring_manager_notes: str | None,
    candidates: list[CandidateProfile],
) -> list[str]:
    if not hiring_manager_notes or not hiring_manager_notes.strip():
        return []

    normalized_notes = normalize(hiring_manager_notes.replace("/", " "))
    preferences: list[str] = []

    for term in candidate_preference_vocabulary(candidates):
        if term_matches_text(term, normalized_notes):
            preferences.append(term)

    chunks = re.split(
        r"[,;/\n.]|\band\b|\bwith\b|\bwho\b|\bthat\b",
        hiring_manager_notes,
        flags=re.IGNORECASE,
    )
    for chunk in chunks:
        cleaned = clean_preference(chunk)
        if cleaned:
            preferences.append(cleaned)

    return list(dict.fromkeys(preferences))


def candidate_preference_vocabulary(candidates: list[CandidateProfile]) -> list[str]:
    terms: list[str] = []
    for candidate in candidates:
        terms.extend(candidate.candidate.summary.split("."))
        for experience in candidate.experience:
            terms.extend([experience.company, experience.title])
        for skills in candidate.skills.values():
            terms.extend(skills)

    cleaned_terms = [
        term.strip()
        for term in terms
        if term.strip() and len(tokens(term)) <= 4
    ]
    return list(dict.fromkeys(cleaned_terms))


def clean_preference(value: str) -> str:
    cleaned = re.sub(
        r"\b(prioritize|prefer|preferred|nice to have|must have|candidates?|people|profiles?|background|experience|skills?|strong|solid)\b",
        " ",
        value,
        flags=re.IGNORECASE,
    )
    cleaned = " ".join(cleaned.strip(" :-").split())
    if not cleaned:
        return ""

    clean_tokens = tokens(cleaned)
    if not clean_tokens:
        return ""
    if len(clean_tokens) == 1 and len(clean_tokens[0]) < 3:
        return ""
    if len(clean_tokens) > 5:
        return ""
    return cleaned
