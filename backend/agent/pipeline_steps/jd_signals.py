from __future__ import annotations

from backend.agent.llm_client import LLMClient
from backend.agent.prompts import jd_signals_prompt
from backend.agent.schemas import JDSignals, TraceEntry
from backend.agent.pipeline_steps.trace import record


def extract_jd_signals(
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
    record(trace, 1, action, 1, "pass", "Extracted role signals and missing information.")
    return signals
