from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from pydantic import ValidationError

from backend.agent.candidate_scoring import append_match_interpretation, score_candidates_locally
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
    OutreachVariants,
    PipelineApiResponse,
    PipelineOutput,
    TraceEntry,
)
from backend.agent.validators import (
    detect_recruiting_bias,
    outreach_quality_validator,
    validate_boolean_query,
)


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
    validation_feedback = ""
    last_result: BooleanQuery | None = None
    last_validation: dict[str, object] | None = None

    for attempt in range(1, 4):
        result = client.call_json(
            action,
            boolean_query_prompt(strategy.model_dump_json(), validation_feedback),
            BooleanQuery,
        )
        validation = validate_boolean_query(result.boolean_query)
        note = _boolean_validation_note(validation)

        if validation["is_valid"]:
            _record(trace, 3, action, attempt, "pass", note)
            return result

        last_result = result
        last_validation = validation
        validation_feedback = note

        if attempt < 3:
            _record(trace, 3, action, attempt, "retry", note)
            continue

        _record(
            trace,
            3,
            action,
            attempt,
            "pass",
            f"Continuing after 2 retries with Boolean query warnings. {note}",
        )
        return result

    if last_result is None:
        raise PipelineFailure("Failed to generate a Boolean query.", trace)

    _record(
        trace,
        3,
        action,
        3,
        "pass",
        f"Continuing with Boolean query warnings. {_boolean_validation_note(last_validation or {})}",
    )
    return last_result


def _boolean_validation_note(validation: dict[str, object]) -> str:
    return "Boolean query validation: " + json.dumps(
        validation,
        ensure_ascii=False,
        separators=(",", ": "),
    )


def _bias_detection_note(
    job_description: str,
    strategy: CandidateSearchStrategy,
    boolean_query: BooleanQuery,
    outreach_message: str,
) -> str:
    result = detect_recruiting_bias(
        job_description=job_description,
        boolean_query=boolean_query.boolean_query,
        search_strategy=strategy,
        outreach_message=outreach_message,
    )
    return "Bias detection: " + json.dumps(
        result,
        ensure_ascii=False,
        separators=(",", ": "),
    )


def _json_note(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ": "))


def _outreach_variants_dict(response: OutreachVariants) -> dict[str, str]:
    return {
        "warm_direct": response.warm_direct,
        "startup_casual": response.startup_casual,
        "executive_brief": response.executive_brief,
    }


def _select_best_outreach_variant(
    passing_variants: list[tuple[str, str]],
    selected_candidate: CandidateProfile,
    selected_match: CandidateMatch,
) -> tuple[str, str]:
    first_name = _first_name(selected_candidate).lower()
    evidence_terms = [
        *selected_match.matched_skills,
        *selected_match.matched_manager_preferences,
        selected_match.current_company,
    ]

    def score_variant(item: tuple[str, str]) -> tuple[int, int]:
        variant_name, message = item
        normalized_message = message.lower()
        evidence_hits = sum(1 for term in evidence_terms if term and term.lower() in normalized_message)
        starts_with_name = int(normalized_message.startswith(f"hi {first_name},"))
        length_bonus = 1 if 120 <= len(message) <= 240 else 0
        style_bonus = {
            "warm_direct": 3,
            "executive_brief": 2,
            "startup_casual": 1,
        }.get(variant_name, 0)
        return (evidence_hits * 4 + starts_with_name * 2 + length_bonus + style_bonus, -len(message))

    return max(passing_variants, key=score_variant)


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
                OutreachVariants,
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

        variants = _outreach_variants_dict(response)
        passing_variants: list[tuple[str, str]] = []
        validation_errors: list[str] = []
        for variant_name, variant_message in variants.items():
            message = variant_message.strip()
            valid, errors = outreach_quality_validator(
                message,
                response.specific_detail,
                job_description,
                jd_signals,
                _first_name(selected_candidate),
            )
            if valid:
                passing_variants.append((variant_name, message))
            else:
                validation_errors.append(f"{variant_name}: {'; '.join(errors)}")

        if response.specific_detail.strip() != specific_detail:
            validation_errors.append(
                f"specific_detail must equal the Step 1 phrase {specific_detail!r}."
            )

        if passing_variants and response.specific_detail.strip() == specific_detail:
            selected_variant, message = _select_best_outreach_variant(
                passing_variants,
                selected_candidate,
                selected_match,
            )
            _record(
                trace,
                4,
                action,
                attempt,
                "pass",
                (
                    f"Outreach passed local validation for {selected_match.full_name} "
                    f"(local match score {selected_match.match_score}). "
                    f"Selected outreach variant: {selected_variant}. "
                    f"Outreach variants: {_json_note({'variants': variants, 'selected': selected_variant})} "
                    f"{_bias_detection_note(job_description, strategy, boolean_query, message)}"
                ),
            )
            return OutreachOutput(
                outreach_message=message,
                specific_detail=specific_detail,
                character_count=len(message),
                attempts=attempt,
            )

        failure_reason = "; ".join(validation_errors)
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
    summary.fit_reason = append_match_interpretation(summary.fit_reason, selected_match.match_score)
    _record(
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
