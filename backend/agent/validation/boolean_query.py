from __future__ import annotations

import re
from typing import Any

from backend.agent.validation.common import normalize_text


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

    normalized_query = normalize_text(query)
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
