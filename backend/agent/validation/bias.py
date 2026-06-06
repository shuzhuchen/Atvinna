from __future__ import annotations

import re
from typing import Any

from backend.agent.validation.common import normalize_text


BIAS_PATTERNS = {
    "age-coded term": (
        r"\byoung\b",
        r"\brecent grad only\b",
        r"\brecent graduate only\b",
        r"\benergetic\b",
        r"\bdigital native\b",
    ),
    "gender-coded term": (
        r"\baggressive\b",
        r"\bdominant\b",
        r"\bnurturing\b",
    ),
    "nationality/language issue": (
        r"\bnative english speaker\b",
        r"\bus-born\b",
        r"\bu\.s\.-born\b",
        r"\blocal only\b",
        r"\bus citizens only\b",
        r"\bu\.s\. citizens only\b",
    ),
    "school prestige filter": (
        r"\bivy league only\b",
        r"\btop school only\b",
        r"\btop-tier school only\b",
        r"\belite university only\b",
    ),
    "overly narrow company targeting": (
        r"\bfaang only\b",
        r"\bbig tech only\b",
        r"\bex-google only\b",
        r"\bex-meta only\b",
        r"\bex-apple only\b",
        r"\bex-amazon only\b",
        r"\bex-netflix only\b",
        r"\bfrom google only\b",
        r"\bfrom meta only\b",
        r"\bfrom apple only\b",
        r"\bfrom amazon only\b",
        r"\bfrom netflix only\b",
    ),
}
PRESTIGE_COMPANY_TERMS = (
    "google",
    "meta",
    "facebook",
    "apple",
    "amazon",
    "netflix",
    "microsoft",
    "openai",
    "anthropic",
)


def detect_recruiting_bias(
    job_description: str,
    boolean_query: str,
    search_strategy: Any,
    outreach_message: str,
) -> dict[str, Any]:
    """Detect non-blocking bias and sourcing-risk warnings across recruiting outputs."""
    warnings: list[str] = []
    fields = {
        "JD": job_description,
        "boolean_query": boolean_query,
        "search_strategy": _stringify_for_bias_scan(search_strategy),
        "outreach_message": outreach_message,
    }

    for field_name, text in fields.items():
        normalized_text = normalize_text(text)
        for category, patterns in BIAS_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, normalized_text, flags=re.IGNORECASE):
                    warnings.append(
                        f"{field_name} contains {category}: {_readable_pattern(pattern)}."
                    )

    target_companies = _extract_target_companies(search_strategy)
    prestige_targets = [
        company
        for company in target_companies
        if any(term in normalize_text(company) for term in PRESTIGE_COMPANY_TERMS)
    ]
    if 0 < len(target_companies) <= 2 and prestige_targets:
        warnings.append(
            "search_strategy may be overly narrow because target_companies only lists "
            f"{len(target_companies)} prestige/company-specific source(s): {', '.join(target_companies)}."
        )

    if warnings:
        recommended_action = (
            "Review and broaden sourcing language. Remove protected-class proxies, "
            "avoid prestige-only filters, and replace risky phrases with role-relevant "
            "skills, responsibilities, and business context."
        )
    else:
        recommended_action = "No recruiting bias warning detected; continue with normal reviewer judgment."

    return {
        "has_warning": len(warnings) > 0,
        "warnings": list(dict.fromkeys(warnings)),
        "recommended_action": recommended_action,
    }


def _stringify_for_bias_scan(value: Any) -> str:
    if hasattr(value, "model_dump"):
        return str(value.model_dump())
    return str(value)


def _readable_pattern(pattern: str) -> str:
    return pattern.replace(r"\b", "").replace("\\", "")


def _extract_target_companies(search_strategy: Any) -> list[str]:
    if hasattr(search_strategy, "target_companies"):
        companies = getattr(search_strategy, "target_companies")
        return [str(company) for company in companies]
    if isinstance(search_strategy, dict):
        companies = search_strategy.get("target_companies", [])
        if isinstance(companies, list):
            return [str(company) for company in companies]
    return []
