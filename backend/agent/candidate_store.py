from __future__ import annotations

import json
from pathlib import Path

from backend.agent.schemas import CandidateProfile


CANDIDATE_DATABASE_PATH = Path(__file__).resolve().parents[1] / "data" / "candidates.json"


def load_candidates() -> list[CandidateProfile]:
    data = json.loads(CANDIDATE_DATABASE_PATH.read_text(encoding="utf-8"))
    candidates = [CandidateProfile.model_validate(item) for item in data]
    if len(candidates) < 5:
        raise ValueError(f"Candidate database must contain at least 5 profiles; found {len(candidates)}.")
    return candidates
