from __future__ import annotations


def normalize_text(value: str) -> str:
    return " ".join(value.lower().split())


def contains_close_exact_phrase(haystack: str, phrase: str) -> bool:
    normalized_haystack = normalize_text(haystack)
    normalized_phrase = normalize_text(phrase)
    if not normalized_phrase:
        return False

    return normalized_phrase in normalized_haystack
