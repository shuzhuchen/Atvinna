from __future__ import annotations

from backend.agent.llm_client import LLMClient
from backend.agent.pipeline_steps.errors import PipelineFailure
from backend.agent.pipeline_steps.trace import json_note, record
from backend.agent.prompts import boolean_query_prompt
from backend.agent.schemas import BooleanQuery, CandidateSearchStrategy, TraceEntry
from backend.agent.validators import validate_boolean_query


def generate_boolean_query(
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
        note = boolean_validation_note(validation)

        if validation["is_valid"]:
            record(trace, 3, action, attempt, "pass", note)
            return result

        last_result = result
        last_validation = validation
        validation_feedback = note

        if attempt < 3:
            record(trace, 3, action, attempt, "retry", note)
            continue

        record(
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

    record(
        trace,
        3,
        action,
        3,
        "pass",
        f"Continuing with Boolean query warnings. {boolean_validation_note(last_validation or {})}",
    )
    return last_result


def boolean_validation_note(validation: dict[str, object]) -> str:
    return "Boolean query validation: " + json_note(validation)
