from __future__ import annotations

import re
from typing import Any

from backend.agent.schemas import JDSignals


MAX_OUTREACH_CHARS = 300
BANNED_OUTREACH_PHRASES = (
    "i came across your profile",
    "came across your profile",
    "impressed by your background",
    "impressive profile",
    "exciting opportunity",
    "fast-growing company",
    "perfect fit",
    "great fit",
    "amazing opportunity",
    "revolutionary opportunity",
    "dream opportunity",
)
REQUIRED_CTA_PATTERNS = (
    "open to a quick chat?",
    "worth a quick conversation?",
    "would you be open to learning more?",
    "open to learning more?",
    "would you be open to a quick chat?",
    "worth a quick chat?",
    "open to a quick conversation?",
)
TOO_FORMAL_OR_SALESY_PHRASES = (
    "dear ",
    "to whom it may concern",
    "i hope this message finds you well",
    "i am reaching out to inform you",
    "we are thrilled to announce",
    "unparalleled",
    "world-class",
    "once-in-a-lifetime",
    "cutting-edge opportunity",
    "transform your career",
    "join us on this journey",
)
DISALLOWED_BOOLEAN_FILTERS = (
    "age",
    "gender",
    "race",
    "ethnicity",
    "nationality",
    "religion",
    "marital status",
    "disability",
)
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


def _normalize_text(value: str) -> str:
    return " ".join(value.lower().split())


def _contains_close_exact_phrase(haystack: str, phrase: str) -> bool:
    normalized_haystack = _normalize_text(haystack)
    normalized_phrase = _normalize_text(phrase)
    if not normalized_phrase:
        return False

    return normalized_phrase in normalized_haystack


def validate_boolean_query(boolean_query: str) -> dict[str, Any]:
    """Validate Step 3 Boolean query syntax and sourcing guardrails."""
    warnings: list[str] = []
    suggestions: list[str] = []
    query = boolean_query.strip()

    if not query:
        warnings.append("Boolean query is empty.")
        suggestions.append("Generate a non-empty query using role titles, skills, and company/background terms.")

    if not _has_balanced_parentheses(query):
        warnings.append("Parentheses are not balanced.")
        suggestions.append("Make sure every opening parenthesis has a matching closing parenthesis.")

    if not re.search(r"\b(AND|OR)\b", query, flags=re.IGNORECASE):
        warnings.append("Boolean query must contain at least one AND or OR operator.")
        suggestions.append("Combine at least two role-relevant terms with AND or OR.")

    if re.search(r'"\s*"|\'\s*\'|“\s*”|‘\s*’', query):
        warnings.append("Boolean query contains empty quotes.")
        suggestions.append("Remove empty quoted phrases or replace them with real role-relevant keywords.")

    repeated_operator = re.search(r"\b(AND|OR)\s+\1\b", query, flags=re.IGNORECASE)
    if repeated_operator:
        warnings.append(f"Boolean query contains repeated operator: {repeated_operator.group(0)}.")
        suggestions.append("Remove repeated Boolean operators such as AND AND or OR OR.")

    searchable_terms = _extract_searchable_terms(query)
    if len(searchable_terms) < 2:
        warnings.append("Boolean query is too broad; it appears to contain fewer than two searchable terms.")
        suggestions.append("Add at least one additional role title, required skill, or target background.")

    normalized_query = _normalize_text(query)
    matches = [
        term
        for term in DISALLOWED_BOOLEAN_FILTERS
        if re.search(rf"\b{re.escape(term)}\b", normalized_query)
    ]
    if matches:
        warnings.append(f"Boolean query contains disallowed filter(s): {', '.join(matches)}.")
        suggestions.append("Remove protected-class filters and use only role-relevant skills, backgrounds, or company types.")

    return {
        "is_valid": len(warnings) == 0,
        "warnings": warnings,
        "suggestions": list(dict.fromkeys(suggestions)),
    }


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
        normalized_text = _normalize_text(text)
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
        if any(term in _normalize_text(company) for term in PRESTIGE_COMPANY_TERMS)
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


def _has_balanced_parentheses(value: str) -> bool:
    depth = 0
    in_quote = False
    quote_char = ""

    for char in value:
        if char in {'"', "'"}:
            if in_quote and char == quote_char:
                in_quote = False
                quote_char = ""
            elif not in_quote:
                in_quote = True
                quote_char = char
            continue

        if in_quote:
            continue

        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth < 0:
                return False

    return depth == 0


def _extract_searchable_terms(query: str) -> set[str]:
    quoted_terms = {
        match.strip().lower()
        for match in re.findall(r'"([^"]+)"|\'([^\']+)\'', query)
        for match in match
        if match.strip()
    }
    bare_terms = {
        token.lower()
        for token in re.findall(r"\b[a-zA-Z][a-zA-Z0-9+#.&/-]*\b", query)
        if token.upper() not in {"AND", "OR", "NOT"}
    }
    return quoted_terms | bare_terms


def validate_outreach_message(
    message: str,
    specific_detail: str,
    job_description: str,
    jd_signals: JDSignals,
    candidate_first_name: str | None = None,
) -> tuple[bool, list[str]]:
    return outreach_quality_validator(
        message,
        specific_detail,
        job_description,
        jd_signals,
        candidate_first_name,
    )


def outreach_quality_validator(
    message: str,
    specific_detail: str,
    job_description: str,
    jd_signals: JDSignals,
    candidate_first_name: str | None = None,
) -> tuple[bool, list[str]]:
    # Step 4 local validation and recruiter-style quality rules.
    errors: list[str] = []
    normalized_message = _normalize_text(message)

    if len(message) >= MAX_OUTREACH_CHARS:
        errors.append(f"outreach_message is {len(message)} characters; it must be under {MAX_OUTREACH_CHARS}.")

    if candidate_first_name:
        expected_prefix = f"hi {_normalize_text(candidate_first_name)},"
        if not normalized_message.startswith(expected_prefix):
            errors.append(
                f"outreach_message must open with the selected candidate's first name: "
                f"'Hi {candidate_first_name},'."
            )

    if not specific_detail.strip():
        errors.append("specific_detail is empty.")
    else:
        signal_text = " ".join(
            [
                jd_signals.role_type,
                *jd_signals.required_skills,
                *jd_signals.seniority_indicators,
                jd_signals.company_stage,
                *jd_signals.missing_information,
                jd_signals.specific_detail,
            ]
        )
        detail_is_grounded = _contains_close_exact_phrase(
            f"{job_description} {signal_text}",
            specific_detail,
        )
        if not detail_is_grounded:
            errors.append(
                f"specific_detail {specific_detail!r} must appear in the JD or extracted JD signals."
            )

        if not _contains_close_exact_phrase(message, specific_detail):
            errors.append(
                f"outreach_message must include the specific_detail or close exact phrase: {specific_detail!r}."
            )

    banned_matches = [phrase for phrase in BANNED_OUTREACH_PHRASES if phrase in normalized_message]
    if banned_matches:
        errors.append(f"outreach_message contains banned generic phrase(s): {', '.join(banned_matches)}.")

    if not any(pattern in normalized_message for pattern in REQUIRED_CTA_PATTERNS):
        errors.append(
            "outreach_message must end with a simple low-pressure CTA such as "
            "'Open to a quick chat?', 'Worth a quick conversation?', or "
            "'Would you be open to learning more?'."
        )

    salesy_matches = [phrase for phrase in TOO_FORMAL_OR_SALESY_PHRASES if phrase in normalized_message]
    if salesy_matches:
        errors.append(f"outreach_message is too formal or salesy: {', '.join(salesy_matches)}.")

    sentence_count = len([part for part in re.split(r"[.!?]+", message) if part.strip()])
    if sentence_count > 3:
        errors.append("outreach_message should be concise, ideally 2 to 3 short sentences.")

    exclamation_count = message.count("!")
    if exclamation_count > 1:
        errors.append("outreach_message is too salesy; use at most one exclamation mark.")

    if len(message.split()) < 12:
        errors.append("outreach_message is too short to explain why the role may be relevant.")

    return len(errors) == 0, errors
