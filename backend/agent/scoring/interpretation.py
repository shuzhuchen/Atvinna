from __future__ import annotations

import re


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
    cleaned_reason = remove_existing_match_guidance(fit_reason)
    if cleaned_reason.startswith(guidance):
        return cleaned_reason
    return f"{cleaned_reason} Recruiter guidance: {guidance}."


def remove_existing_match_guidance(fit_reason: str) -> str:
    cleaned = re.sub(r"\s*Match interpretation:\s*[^.]+\.?", "", fit_reason).strip()
    cleaned = re.sub(r"\s*Recruiter guidance:\s*[^.]+\.?", "", cleaned).strip()
    return cleaned
