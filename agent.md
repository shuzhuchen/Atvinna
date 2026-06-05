# Atvinna Agent Notes

This file summarizes the current Atvinna implementation and the decisions made
for the OCBridge Engineering Intern assignment.

## Overview

Atvinna is a recruiting copilot agent named `atvinna`.

It supports:

- Required CLI entrypoint: `python main.py`
- FastAPI backend: `POST /api/run-pipeline`
- React + TypeScript + Vite + TailwindCSS recruiter dashboard
- Five sequential Mistral LLM calls
- Local candidate database scoring
- Step 4 outreach self-correction
- Atomic `output.json` writes

The frontend and CLI both call the same backend pipeline. The frontend only
exposes the agent through a recruiter dashboard; it does not replace or bypass
the pipeline.

## Current Structure

```text
Atvinna/
├── main.py
├── requirements.txt
├── output.json
├── README.md
├── agent.md
├── backend/
│   ├── main.py
│   ├── cli.py
│   ├── agent/
│   │   ├── pipeline.py
│   │   ├── llm_client.py
│   │   ├── prompts.py
│   │   ├── schemas.py
│   │   ├── validators.py
│   │   ├── candidate_store.py
│   │   └── candidate_scoring.py
│   ├── data/
│   │   └── candidates.json
│   └── tests/
│       └── test_validators.py
└── frontend/
    └── src/
        ├── App.tsx
        ├── types.ts
        └── components/
```

## Inputs

The recruiter provides:

- Job Description
- Optional Hiring Manager Notes

There is no default JD in the frontend. The user must paste the JD into the
dashboard or CLI.

The API request shape is:

```json
{
  "job_description": "Required JD text",
  "hiring_manager_notes": "Optional notes"
}
```

## Five LLM Steps

The production pipeline still has exactly five LLM steps:

1. `extract_jd_signals`
2. `generate_search_strategy`
3. `generate_boolean_query`
4. `generate_outreach_message`
5. `generate_candidate_summary`

Each step makes its own Mistral API call through `LLMClient.call_json()`.
There is no mock LLM response path in production.

Current flow:

```text
Recruiter JD
→ Step 1: JD Signals
→ Step 2: Search Strategy
→ Step 3: Boolean Query
→ Local Candidate Scoring
→ Step 4: Outreach Message
→ Step 5: Candidate Summary
→ output.json
```

Local candidate scoring happens between Step 3 and Step 4. It is not an LLM
step, so it does not violate the five-step requirement.

## Candidate Database

Candidates live in `backend/data/candidates.json`.

The database currently contains at least five candidates and includes:

- Sophia Martinez
- Maya Chen
- Daniel Brooks
- Priya Nair
- Marcus Reed
- Shuzhu Chen

Each profile follows the shared `CandidateProfile` schema:

- Candidate identity
- Education
- Experience
- Skills grouped by category

`backend/agent/candidate_store.py` validates that the database contains at
least five candidates.

## Local Candidate Scoring

`backend/agent/candidate_scoring.py` scores all candidates locally after Step 3.

The selected top candidate is passed into:

- Step 4, so outreach can start with `Hi FirstName,`
- Step 5, so the summary is for the same selected candidate

The API response includes `candidate_matches` for the dashboard. The required
root `output.json` does not include `candidate_matches`, because the assignment
requires exactly five top-level keys.

## Match Score Breakdown

Recruiters see one combined score with a breakdown:

```text
Overall Match: 86
JD Match: 70
Hiring Manager Preference: +16
```

Backend fields:

```text
match_score
jd_match_score
hiring_manager_score
matched_manager_preferences
```

Scoring behavior:

- `jd_match_score` is based on JD signals and search strategy.
- `hiring_manager_score` is based on optional manager notes.
- Hiring manager notes are treated as preferences, not hard requirements.
- When notes are present, JD Match is calibrated to leave a visible 20-point
  preference band.
- Short terms are guarded so skills like `R` do not accidentally match `RAG`.

Example preference notes for testing:

```text
Prioritize candidates with AI full-stack experience, React, Node.js, Python,
AWS, Kafka, Redis, MongoDB, microservices, LangChain, RAG, and Tailwind CSS.
Strong preference for candidates who have built real-time dashboards, RESTful
APIs, data pipelines, and agentic AI applications.
```

## Required output.json Schema

`output.json` contains exactly these top-level keys:

```text
candidate_search_strategy
boolean_query
outreach_message
candidate_summary
pipeline_trace
```

No extra top-level keys are written to `output.json`.

The API response may include extra dashboard-only fields, such as
`candidate_matches`, but the downloaded assignment JSON strips those extras.

## Step 4 Self-Correction

Step 4 is implemented in `backend/agent/pipeline.py`.

The retry prompt is in `backend/agent/prompts.py`.

The local validator is in `backend/agent/validators.py`.

Step 4 validates:

- `len(outreach_message) < 300`
- `specific_detail` is non-empty
- `specific_detail` appears in the JD or extracted JD signals
- `outreach_message` includes the selected `specific_detail`
- banned generic phrases are not present
- the message has a low-pressure CTA
- when a selected candidate is available, the message opens with
  `Hi FirstName,`

If validation fails:

1. The attempt is appended to `pipeline_trace` with `result="retry"`.
2. The exact failure reason is included in the next prompt.
3. The LLM retries up to three attempts.
4. If all attempts fail, the trace records `result="fail"` and the pipeline
   exits gracefully with `PipelineFailure`.

## Pipeline Trace

`pipeline_trace` records each real LLM step and each Step 4 retry attempt.

Step names remain exactly:

```text
extract_jd_signals
generate_search_strategy
generate_boolean_query
generate_outreach_message
generate_candidate_summary
```

A normal successful run has five trace entries. A run with Step 4 retries has
additional Step 4 entries.

## Frontend

The dashboard includes:

- Job Description textarea
- Hiring Manager Notes textarea
- Run Pipeline button
- Loading and error states
- Workflow progress indicator
- Tabs for Search Strategy, Boolean Query, Outreach Message, Candidate Summary,
  and Pipeline Trace
- Editable outreach draft
- Copy buttons
- JSON download

In the Candidate Summary tab, the order is:

1. Selected Candidate Summary
2. Candidate Matches

Candidate Matches display:

- Overall Match
- JD Match
- Hiring Manager Preference
- Matched skills
- Matched manager preferences
- Fit reason

## Backend

FastAPI endpoint:

```text
POST /api/run-pipeline
```

The backend:

- Executes all five pipeline steps
- Scores all database candidates locally
- Saves `output.json`
- Returns JSON to the frontend

`output.json` is written atomically only after all five steps succeed.

## Tests

`backend/tests/test_validators.py` is a local guardrail test file. It does not
call Mistral.

It currently checks:

- Candidate database has at least five unique candidates
- `Shuzhu Chen` exists in the candidate database
- Candidate matches are sorted by score
- Finance JD ranks Sophia Martinez first
- Short skills do not create false matches
- Hiring manager notes create visible preference score
- Boolean query rejects protected-class filters
- Outreach validator rejects missing details and generic phrases
- Outreach validator requires `Hi FirstName,` when candidate context exists

## Verification

Useful commands:

```bash
python main.py
python -m unittest backend/tests/test_validators.py
python -m compileall backend main.py
cd frontend && npm run build
```

The production pipeline requires:

```text
MISTRAL_API_KEY
```

The project uses Mistral, not OpenAI, for production LLM calls.
