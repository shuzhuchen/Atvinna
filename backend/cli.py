from __future__ import annotations

from backend.agent.pipeline import OUTPUT_PATH, PipelineFailure, run_pipeline


def _read_multiline_input(prompt: str) -> str:
    print(prompt)
    print("Finish with a line containing only END.")
    lines: list[str] = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line.strip() == "END":
            break
        lines.append(line)
    return "\n".join(lines).strip()


def main() -> None:
    job_description = _read_multiline_input("Paste the Job Description:")
    if not job_description:
        print("Pipeline could not start: Job Description cannot be empty.")
        return

    hiring_manager_notes = _read_multiline_input(
        "Paste optional Hiring Manager Notes, or enter END immediately:"
    )

    try:
        output = run_pipeline(job_description, hiring_manager_notes or None)
    except PipelineFailure as exc:
        print(f"Pipeline stopped gracefully: {exc}")
        print(f"Trace entries: {len(exc.trace)}")
        return
    except RuntimeError as exc:
        print(f"Pipeline could not start: {exc}")
        return

    print(f"Pipeline complete. Wrote {OUTPUT_PATH.name}.")
    print(f"Trace entries: {len(output.pipeline_trace)}")
    print("Candidate matches:")
    for match in output.candidate_matches:
        print(
            f"- {match.full_name}: Overall {match.match_score} "
            f"(JD {match.jd_match_score}, Hiring Manager +{match.hiring_manager_score})"
        )


if __name__ == "__main__":
    main()
