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

The database currently contains six software-engineering candidates:

- Sophia Martinez: new grad frontend engineer
- Maya Chen: early-career AI software engineer
- Daniel Brooks: backend software engineer
- Priya Nair: AI / machine learning engineer
- Marcus Reed: senior software engineer
- Shuzhu Chen: AI/ML full-stack engineer

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

- Step 1 dynamically extracts `related_skill_aliases`, `adjacent_backgrounds`,
  and `seniority_level` from the current JD.
- The local scorer consumes those dynamic signals instead of relying on a fixed
  industry taxonomy.
- `jd_match_score` is based on coverage of JD signals and search strategy.
- Required skills contribute 50%.
- Target background and role fit contribute 25%.
- Keywords and tools contribute 15%.
- Seniority or context contributes 10%.
- Score caps prevent weak or adjacent candidates from reaching 90+.
- Hiring manager notes are treated as preferences, not hard requirements.
- Hiring manager preference can break ties but cannot push weak core JD matches
  into top-match range.
- Short terms are guarded so skills like `R` do not accidentally match `RAG`.

## Match Interpretation Layer

The existing scoring rubric remains unchanged. After the final score is
calculated, `interpret_match_score(score)` adds a recruiter-facing
interpretation:

```text
80-100 -> Recruiter Screen | Strong enough for recruiter outreach
65-79  -> Potential Match | Review before outreach
50-64  -> Consider | Possible fit with gaps
35-49  -> Low Match | Unlikely fit
<35    -> Not Recommended | Do not prioritize
```

The required `output.json` schema is not expanded. Instead, the interpretation
is included in `fit_reason` for candidate matches and appended as recruiter
guidance for the selected candidate summary. Candidate match explanations use
positive, balanced, low-fit, or reject language based on the score band, so
candidates below 50 are not described as matching the role. The CLI and
frontend display the score as a percentage and show only the `match_level`
label beside it to avoid duplicated recommendation copy.

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

## Step 3 Boolean Query Validator

Step 3 validates the generated Boolean query before downstream steps use it.

The structured validator returns:

```text
is_valid
warnings
suggestions
```

It checks balanced parentheses, at least one `AND` or `OR`, empty quotes,
one-keyword broad queries, repeated operators, and obvious protected-class
filters.

Invalid Step 3 output is retried up to two times. If the query is still invalid,
the pipeline continues with warnings recorded in `pipeline_trace` instead of
changing `output.json`.

## Bias Detection Guardrail

`detect_recruiting_bias()` lives in `backend/agent/validators.py`.

It scans:

- Job Description
- Search Strategy
- Boolean Query
- Outreach Message

It detects risky terms and patterns including age-coded language, gender-coded
language, nationality/language restrictions, school prestige filters, and overly
narrow company targeting.

The result shape is:

```text
has_warning
warnings
recommended_action
```

This guardrail does not change `output.json` top-level keys. It is added to the
Step 4 `pipeline_trace` note after outreach is generated. The CLI prints
guardrail warnings when `has_warning` is true.

## Step 4 Self-Correction

Step 4 is implemented in `backend/agent/pipeline.py`.

The retry prompt is in `backend/agent/prompts.py`.

The local validator is in `backend/agent/validators.py`.

Step 4 generates three outreach variants:

- `warm_direct`
- `startup_casual`
- `executive_brief`

Step 4 validates each variant:

- `len(outreach_message) < 300`
- `specific_detail` is non-empty
- `specific_detail` appears in the JD or extracted JD signals
- `outreach_message` includes the selected `specific_detail`
- banned generic phrases are not present
- the message has a low-pressure CTA
- when a selected candidate is available, the message opens with
  `Hi FirstName,`

The best passing variant becomes the required
`outreach_message.outreach_message`. All variants and the selected variant name
are stored only in the Step 4 `pipeline_trace` note and CLI output.

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
- Candidate matches are sorted by score
- Short skills do not create false matches
- Hiring manager notes create visible preference score
- Boolean query rejects protected-class filters
- Bias detection flags risky recruiting language
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
