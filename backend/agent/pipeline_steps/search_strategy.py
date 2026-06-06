from __future__ import annotations

from backend.agent.llm_client import LLMClient
from backend.agent.prompts import search_strategy_prompt
from backend.agent.schemas import CandidateSearchStrategy, JDSignals, TraceEntry
from backend.agent.pipeline_steps.trace import record


def generate_search_strategy(
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
    record(trace, 2, action, 1, "pass", f"Seniority decision: {strategy.seniority}")
    return strategy
