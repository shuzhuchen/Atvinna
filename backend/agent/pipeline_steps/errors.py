from __future__ import annotations

from backend.agent.schemas import TraceEntry


class PipelineFailure(RuntimeError):
    def __init__(self, message: str, trace: list[TraceEntry]) -> None:
        super().__init__(message)
        self.trace = trace
