from __future__ import annotations

import os
import tempfile
from pathlib import Path

from backend.agent.candidate_scoring import score_candidates_locally
from backend.agent.candidate_store import load_candidates
from backend.agent.llm_client import LLMClient
from backend.agent.pipeline_steps import (
    PipelineFailure,
    extract_jd_signals,
    find_candidate,
    generate_boolean_query,
    generate_candidate_summary,
    generate_outreach_message_with_retry,
    generate_search_strategy,
)
from backend.agent.schemas import PipelineApiResponse, PipelineOutput, TraceEntry


OUTPUT_PATH = Path(__file__).resolve().parents[2] / "output.json"


def run_pipeline(
    job_description: str,
    hiring_manager_notes: str | None = None,
) -> PipelineApiResponse:
    if not job_description.strip():
        raise ValueError("Job Description cannot be empty.")

    client = LLMClient()
    trace: list[TraceEntry] = []
    clean_jd = job_description.strip()

    jd_signals = extract_jd_signals(client, trace, clean_jd, None)
    strategy = generate_search_strategy(client, trace, jd_signals)
    boolean_query = generate_boolean_query(client, trace, strategy)

    candidates = load_candidates()
    candidate_matches = score_candidates_locally(
        candidates,
        jd_signals,
        strategy,
        hiring_manager_notes,
    )
    selected_match = candidate_matches[0]
    selected_candidate = find_candidate(candidates, selected_match.full_name)

    outreach = generate_outreach_message_with_retry(
        client,
        trace,
        jd_signals,
        strategy,
        boolean_query,
        clean_jd,
        selected_candidate,
        selected_match,
    )
    candidate_summary = generate_candidate_summary(
        client,
        trace,
        clean_jd,
        jd_signals,
        strategy,
        boolean_query,
        outreach,
        selected_candidate,
        selected_match,
    )

    output = PipelineOutput(
        candidate_search_strategy=strategy,
        boolean_query=boolean_query.boolean_query,
        outreach_message=outreach,
        candidate_summary=candidate_summary,
        pipeline_trace=trace,
    )
    _write_output_atomically(output)
    return PipelineApiResponse(
        **output.model_dump(),
        candidate_matches=candidate_matches,
    )


def _write_output_atomically(output: PipelineOutput) -> None:
    """Replace output.json only after all five pipeline steps have passed."""
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=OUTPUT_PATH.parent,
        prefix=".output-",
        suffix=".json.tmp",
        delete=False,
    ) as temp_file:
        temp_file.write(output.model_dump_json(indent=2))
        temp_path = Path(temp_file.name)

    os.replace(temp_path, OUTPUT_PATH)


__all__ = ["OUTPUT_PATH", "PipelineFailure", "run_pipeline"]
