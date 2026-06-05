from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend.agent.pipeline import run_pipeline
from backend.agent.schemas import PipelineApiResponse


class RunPipelineRequest(BaseModel):
    job_description: str = Field(min_length=1)
    hiring_manager_notes: str | None = None


app = FastAPI(
    title="atvinna Recruiting Copilot API",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/run-pipeline", response_model=PipelineApiResponse)
def run_recruiting_pipeline(request: RunPipelineRequest) -> PipelineApiResponse:
    try:
        return run_pipeline(
            job_description=request.job_description,
            hiring_manager_notes=request.hiring_manager_notes,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Pipeline failed: {exc}") from exc
