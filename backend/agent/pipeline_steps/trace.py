from __future__ import annotations

import json

from backend.agent.schemas import TraceEntry


def record(
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


def json_note(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ": "))
