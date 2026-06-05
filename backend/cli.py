from __future__ import annotations

import json

from backend.agent.candidate_scoring import interpret_match_score
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
        interpretation = interpret_match_score(match.match_score)
        manager_adjustment = (
            f", Hiring Manager +{match.hiring_manager_score}"
            if match.hiring_manager_score
            else ""
        )
        print(
            f"- {match.full_name}: Overall {match.match_score}% "
            f"(JD {match.jd_match_score}{manager_adjustment}) "
            f"- {interpretation['match_level']}"
        )
    _print_outreach_variants(output.pipeline_trace)
    _print_guardrail_warnings(output.pipeline_trace)


def _print_outreach_variants(pipeline_trace: list[object]) -> None:
    for entry in pipeline_trace:
        note = getattr(entry, "note", "")
        marker = "Outreach variants: "
        if marker not in note:
            continue

        raw_result = note.split(marker, 1)[1].split(" Bias detection: ", 1)[0]
        try:
            result = json.loads(raw_result)
        except json.JSONDecodeError:
            continue

        selected = result.get("selected", "")
        variants = result.get("variants", {})
        print("Outreach variants:")
        for variant_name in ("warm_direct", "startup_casual", "executive_brief"):
            message = variants.get(variant_name)
            if message:
                selected_marker = " [selected]" if variant_name == selected else ""
                print(f"- {variant_name}{selected_marker}: {message}")


def _print_guardrail_warnings(pipeline_trace: list[object]) -> None:
    for entry in pipeline_trace:
        note = getattr(entry, "note", "")
        marker = "Bias detection: "
        if marker not in note:
            continue
        raw_result = note.split(marker, 1)[1]
        try:
            result = json.loads(raw_result)
        except json.JSONDecodeError:
            continue
        if not result.get("has_warning"):
            continue

        print("Guardrail warnings:")
        for warning in result.get("warnings", []):
            print(f"- {warning}")
        recommended_action = result.get("recommended_action")
        if recommended_action:
            print(f"Recommended action: {recommended_action}")


if __name__ == "__main__":
    main()
