from __future__ import annotations

import os
import tempfile
from pathlib import Path

from pydantic import ValidationError

from backend.agent.candidate_scoring import score_candidates_locally
from backend.agent.candidate_store import load_candidates
from backend.agent.llm_client import LLMClient
from backend.agent.prompts import (
    boolean_query_prompt,
    candidate_summary_prompt,
    jd_signals_prompt,
    outreach_self_correction_prompt,
    search_strategy_prompt,
)
from backend.agent.schemas import (
    BooleanQuery,
    CandidateMatch,
    CandidateProfile,
    CandidateSearchStrategy,
    CandidateSummary,
    JDSignals,
    OutreachMessage,
    OutreachOutput,
    PipelineApiResponse,
    PipelineOutput,
    TraceEntry,
)
from backend.agent.validators import outreach_quality_validator, validate_boolean_query


OUTPUT_PATH = Path(__file__).resolve().parents[2] / "output.json"


class PipelineFailure(RuntimeError):
    def __init__(self, message: str, trace: list[TraceEntry]) -> None:
        super().__init__(message)
        self.trace = trace


def run_pipeline(
    job_description: str,
    hiring_manager_notes: str | None = None,
) -> PipelineApiResponse:
    if not job_description.strip():
        raise ValueError("Job Description cannot be empty.")

    client = LLMClient()
    trace: list[TraceEntry] = []
    clean_jd = job_description.strip()

    jd_signals = _extract_jd_signals(client, trace, clean_jd, None)
    strategy = _generate_search_strategy(client, trace, jd_signals)
    boolean_query = _generate_boolean_query(client, trace, strategy)
    candidates = load_candidates()
    candidate_matches = score_candidates_locally(
        candidates,
        jd_signals,
        strategy,
        hiring_manager_notes,
    )
    selected_match = candidate_matches[0]
    selected_candidate = _find_candidate(candidates, selected_match.full_name)
    outreach = _generate_outreach_message_with_retry(
        client,
        trace,
        jd_signals,
        strategy,
        boolean_query,
        clean_jd,
        selected_candidate,
        selected_match,
    )
    candidate_summary = _generate_candidate_summary(
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


def _record(
    trace: list[TraceEntry],
    step: int,
    action: str,
    attempt: int,
    result: str,
    note: str = "",
) -> None:
    trace.append(
        TraceEntry(
            step=step,
            action=action,
            attempt=attempt,
            result=result,
            note=note,
        )
    )


def _extract_jd_signals(
    client: LLMClient,
    trace: list[TraceEntry],
    job_description: str,
    hiring_manager_notes: str | None,
) -> JDSignals:
    action = "extract_jd_signals"
    signals = client.call_json(
        action,
        jd_signals_prompt(job_description, hiring_manager_notes),
        JDSignals,
    )
    _record(trace, 1, action, 1, "pass", "Extracted role signals and missing information.")
    return signals


def _generate_search_strategy(
    client: LLMClient,
    trace: list[TraceEntry],
    jd_signals: JDSignals,
) -> CandidateSearchStrategy:
    action = "generate_search_strategy"
    strategy = client.call_json(
        action,
        search_strategy_prompt(jd_signals.model_dump_json()),
        CandidateSearchStrategy,
    )
    _record(trace, 2, action, 1, "pass", f"Seniority decision: {strategy.seniority}")
    return strategy


def _generate_boolean_query(
    client: LLMClient,
    trace: list[TraceEntry],
    strategy: CandidateSearchStrategy,
) -> BooleanQuery:
    action = "generate_boolean_query"
    result = client.call_json(
        action,
        boolean_query_prompt(strategy.model_dump_json()),
        BooleanQuery,
    )
    valid, warning = validate_boolean_query(result.boolean_query)
    if not valid:
        _record(trace, 3, action, 1, "fail", warning)
        raise PipelineFailure(warning, trace)
    _record(trace, 3, action, 1, "pass", "Generated one sourcing-style Boolean query.")
    return result


def _generate_outreach_message_with_retry(
    client: LLMClient,
    trace: list[TraceEntry],
    jd_signals: JDSignals,
    strategy: CandidateSearchStrategy,
    boolean_query: BooleanQuery,
    job_description: str,
    selected_candidate: CandidateProfile,
    selected_match: CandidateMatch,
) -> OutreachOutput:
    # Step 4 explicit self-correction loop and local evaluation.
    action = "generate_outreach_message"
    specific_detail = jd_signals.specific_detail.strip()
    failure_reason = ""

    for attempt in range(1, 4):
        try:
            response = client.call_json(
                action,
                outreach_self_correction_prompt(
                    job_description,
                    specific_detail,
                    strategy.model_dump_json(),
                    boolean_query.boolean_query,
                    selected_candidate.model_dump_json(),
                    selected_match.model_dump_json(),
                    failure_reason,
                ),
                OutreachMessage,
            )
        except ValidationError as exc:
            failure_reason = f"Invalid outreach JSON/schema: {exc}"
            if attempt == 3:
                _record(trace, 4, action, attempt, "fail", failure_reason)
                raise PipelineFailure(
                    f"Failed to generate a valid outreach message after 3 attempts. {failure_reason}",
                    trace,
                ) from exc
            _record(trace, 4, action, attempt, "retry", failure_reason)
            continue

        message = response.outreach_message.strip()
        valid, errors = outreach_quality_validator(
            message,
            response.specific_detail,
            job_description,
            jd_signals,
            _first_name(selected_candidate),
        )
        if response.specific_detail.strip() != specific_detail:
            errors.append(
                f"specific_detail must equal the Step 1 phrase {specific_detail!r}."
            )
            valid = False

        if valid:
            _record(
                trace,
                4,
                action,
                attempt,
                "pass",
                (
                    f"Outreach passed local validation for {selected_match.full_name} "
                    f"(local match score {selected_match.match_score})."
                ),
            )
            return OutreachOutput(
                outreach_message=message,
                specific_detail=specific_detail,
                character_count=len(message),
                attempts=attempt,
            )

        failure_reason = "; ".join(errors)
        if attempt == 3:
            error_message = (
                "Failed to generate a valid outreach message after 3 attempts. "
                f"Last validation error: {failure_reason}"
            )
            _record(trace, 4, action, attempt, "fail", error_message)
            raise PipelineFailure(error_message, trace)
        _record(trace, 4, action, attempt, "retry", failure_reason)

    raise PipelineFailure("Failed to generate a valid outreach message.", trace)


def _generate_candidate_summary(
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
    _record(
        trace,
        5,
        action,
        1,
        "pass",
        f"Generated summary for locally selected candidate {selected_match.full_name}.",
    )
    return summary


def _validate_candidate_summary(
    summary: CandidateSummary,
    selected_candidate: CandidateProfile,
    selected_match: CandidateMatch,
    trace: list[TraceEntry],
) -> None:
    if summary.name != selected_match.full_name:
        _record(trace, 5, "generate_candidate_summary", 1, "fail", "Summary name does not match local top candidate.")
        raise PipelineFailure("Step 5 candidate_summary does not match the locally selected candidate.", trace)

    if summary.current_company != selected_candidate.experience[0].company:
        _record(trace, 5, "generate_candidate_summary", 1, "fail", "Summary company does not match database.")
        raise PipelineFailure("Step 5 current_company does not match the candidate database.", trace)


def _find_candidate(candidates: list[CandidateProfile], full_name: str) -> CandidateProfile:
    for candidate in candidates:
        if candidate.candidate.full_name == full_name:
            return candidate
    raise ValueError(f"Selected candidate {full_name!r} is not in the candidate database.")


def _first_name(candidate: CandidateProfile) -> str:
    return candidate.candidate.full_name.split()[0]
