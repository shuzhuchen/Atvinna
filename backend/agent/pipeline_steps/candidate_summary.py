from __future__ import annotations

from backend.agent.candidate_scoring import append_match_interpretation
from backend.agent.llm_client import LLMClient
from backend.agent.pipeline_steps.errors import PipelineFailure
from backend.agent.pipeline_steps.trace import record
from backend.agent.prompts import candidate_summary_prompt
from backend.agent.schemas import (
    BooleanQuery,
    CandidateMatch,
    CandidateProfile,
    CandidateSearchStrategy,
    CandidateSummary,
    JDSignals,
    OutreachOutput,
    TraceEntry,
)


def generate_candidate_summary(
    client: LLMClient,
    trace: list[TraceEntry],
    job_description: str,
    jd_signals: JDSignals,
    strategy: CandidateSearchStrategy,
    boolean_query: BooleanQuery,
    outreach: OutreachOutput,
    selected_candidate: CandidateProfile,
    selected_match: CandidateMatch,
) -> CandidateSummary:
    action = "generate_candidate_summary"
    summary = client.call_json(
        action,
        candidate_summary_prompt(
            job_description,
            jd_signals.model_dump_json(),
            strategy.model_dump_json(),
            boolean_query.boolean_query,
            outreach.model_dump_json(),
            selected_candidate.model_dump_json(),
            selected_match.model_dump_json(),
        ),
        CandidateSummary,
    )
    _validate_candidate_summary(summary, selected_candidate, selected_match, trace)
    summary.fit_reason = append_match_interpretation(summary.fit_reason, selected_match.match_score)
    record(
        trace,
        5,
        action,
        1,
        "pass",
        (
            f"Generated summary for locally selected candidate {selected_match.full_name}. "
            f"Applied match interpretation to candidate_summary.fit_reason."
        ),
    )
    return summary


def _validate_candidate_summary(
    summary: CandidateSummary,
    selected_candidate: CandidateProfile,
    selected_match: CandidateMatch,
    trace: list[TraceEntry],
) -> None:
    if summary.name != selected_match.full_name:
        record(trace, 5, "generate_candidate_summary", 1, "fail", "Summary name does not match local top candidate.")
        raise PipelineFailure("Step 5 candidate_summary does not match the locally selected candidate.", trace)

    if summary.current_company != selected_candidate.experience[0].company:
        record(trace, 5, "generate_candidate_summary", 1, "fail", "Summary company does not match database.")
        raise PipelineFailure("Step 5 current_company does not match the candidate database.", trace)
