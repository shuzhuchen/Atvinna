from __future__ import annotations

from backend.agent.schemas import CandidateProfile


def find_candidate(candidates: list[CandidateProfile], full_name: str) -> CandidateProfile:
    for candidate in candidates:
        if candidate.candidate.full_name == full_name:
            return candidate
    raise ValueError(f"Selected candidate {full_name!r} is not in the candidate database.")


def first_name(candidate: CandidateProfile) -> str:
    return candidate.candidate.full_name.split()[0]
