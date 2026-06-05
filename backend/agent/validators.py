from __future__ import annotations

import re

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


def _normalize_text(value: str) -> str:
    return " ".join(value.lower().split())


def _contains_close_exact_phrase(haystack: str, phrase: str) -> bool:
    normalized_haystack = _normalize_text(haystack)
    normalized_phrase = _normalize_text(phrase)
    if not normalized_phrase:
        return False

    return normalized_phrase in normalized_haystack


def validate_boolean_query(query: str) -> tuple[bool, str]:
    """Reject obvious protected-class filters before a sourcing query is returned."""
    normalized_query = _normalize_text(query)
    matches = [
        term
        for term in DISALLOWED_BOOLEAN_FILTERS
        if re.search(rf"\b{re.escape(term)}\b", normalized_query)
    ]
    if matches:
        return False, f"Boolean query contains disallowed filter(s): {', '.join(matches)}."
    return True, ""


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
