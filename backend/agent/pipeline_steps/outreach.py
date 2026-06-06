from __future__ import annotations

from pydantic import ValidationError

from backend.agent.llm_client import LLMClient
from backend.agent.pipeline_steps.errors import PipelineFailure
from backend.agent.pipeline_steps.selection import first_name
from backend.agent.pipeline_steps.trace import json_note, record
from backend.agent.prompts import outreach_self_correction_prompt
from backend.agent.schemas import (
    BooleanQuery,
    CandidateMatch,
    CandidateProfile,
    CandidateSearchStrategy,
    JDSignals,
    OutreachOutput,
    OutreachVariants,
    TraceEntry,
)
from backend.agent.validators import detect_recruiting_bias, outreach_quality_validator


def generate_outreach_message_with_retry(
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
                record(trace, 4, action, attempt, "fail", failure_reason)
                raise PipelineFailure(
                    f"Failed to generate a valid outreach message after 3 attempts. {failure_reason}",
                    trace,
                ) from exc
            record(trace, 4, action, attempt, "retry", failure_reason)
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
                first_name(selected_candidate),
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
            record(
                trace,
                4,
                action,
                attempt,
                "pass",
                (
                    f"Outreach passed local validation for {selected_match.full_name} "
                    f"(local match score {selected_match.match_score}). "
                    f"Selected outreach variant: {selected_variant}. "
                    f"Outreach variants: {json_note({'variants': variants, 'selected': selected_variant})} "
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
            record(trace, 4, action, attempt, "fail", error_message)
            raise PipelineFailure(error_message, trace)
        record(trace, 4, action, attempt, "retry", failure_reason)

    raise PipelineFailure("Failed to generate a valid outreach message.", trace)


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
    selected_first_name = first_name(selected_candidate).lower()
    evidence_terms = [
        *selected_match.matched_skills,
        *selected_match.matched_manager_preferences,
        selected_match.current_company,
    ]

    def score_variant(item: tuple[str, str]) -> tuple[int, int]:
        variant_name, message = item
        normalized_message = message.lower()
        evidence_hits = sum(1 for term in evidence_terms if term and term.lower() in normalized_message)
        starts_with_name = int(normalized_message.startswith(f"hi {selected_first_name},"))
        length_bonus = 1 if 120 <= len(message) <= 240 else 0
        style_bonus = {
            "warm_direct": 3,
            "executive_brief": 2,
            "startup_casual": 1,
        }.get(variant_name, 0)
        return (evidence_hits * 4 + starts_with_name * 2 + length_bonus + style_bonus, -len(message))

    return max(passing_variants, key=score_variant)


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
    return "Bias detection: " + json_note(result)
