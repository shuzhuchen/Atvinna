from __future__ import annotations

import re

from backend.agent.schemas import CandidateProfile, JDSignals


def candidate_search_text(candidate: CandidateProfile) -> str:
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
    return normalize(" ".join(parts))


def alias_map(jd_signals: JDSignals) -> dict[str, list[str]]:
    aliases: dict[str, list[str]] = {}
    for canonical, values in jd_signals.related_skill_aliases.items():
        normalized_key = normalize(canonical)
        aliases[normalized_key] = [canonical, *values]
    return aliases


def term_or_alias_matches_text(
    term: str,
    candidate_text: str,
    aliases: dict[str, list[str]],
) -> bool:
    candidates = [term, *aliases.get(normalize(term), [])]
    return any(term_matches_text(candidate, candidate_text) for candidate in candidates)


def term_matches_any(term: str, targets: list[str]) -> bool:
    normalized_term = normalize(term)
    if not normalized_term:
        return False

    if len(normalized_term) <= 2:
        return any(normalized_term == normalize(target) for target in targets)

    return any(
        normalized_term in normalize(target) or normalize(target) in normalized_term
        for target in targets
        if normalize(target)
    )


def term_matches_text(term: str, text: str) -> bool:
    normalized_term = normalize(term)
    if not normalized_term:
        return False
    if len(normalized_term) <= 2:
        return re.search(rf"\b{re.escape(normalized_term)}\b", text) is not None
    if normalized_term in text:
        return True

    term_tokens = tokens(normalized_term)
    if len(term_tokens) <= 1:
        return False
    return all(token in text for token in term_tokens)


def normalize(value: str) -> str:
    return " ".join(value.lower().replace("&", " and ").split())


def tokens(value: str) -> list[str]:
    return [
        token
        for token in re.findall(r"[a-z0-9]+", value.lower())
        if len(token) > 1
    ]


def important_tokens(value: str) -> list[str]:
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
    return [token for token in tokens(value) if token not in stopwords]
