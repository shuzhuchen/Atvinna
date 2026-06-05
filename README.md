# Atvinna Recruiting Copilot

Atvinna is an AI recruiting copilot. It accepts a Job Description and optional hiring manager notes,
runs five distinct sequential LLM calls, self-validates outreach, and writes a
complete recruiting workflow to `output.json`.

The React dashboard is an optional workflow UI. The required one-command CLI
entrypoint remains:

```bash
python main.py
```

## Required Pipeline

1. `extract_jd_signals`  
   Extracts role type, required skills, seniority indicators, company stage,
   dynamic skill aliases, adjacent backgrounds, seniority level, missing
   information, and an exact JD detail for outreach.
2. `generate_search_strategy`  
   Uses Step 1 output to generate target backgrounds, target companies,
   keywords, and a seniority recommendation.
3. `generate_boolean_query`  
   Uses Step 2 output to generate one sourcing-style Boolean query.
4. `generate_outreach_message`  
   Generates personalized startup-oriented outreach, validates it locally, and
   retries up to three times.
5. `generate_candidate_summary`  
   Uses all prior pipeline context and the locally selected candidate to
   generate a candidate summary card.

Each step makes its own LLM API call. The steps are not collapsed into one
prompt.

## Setup On A Clean Machine

```bash
git clone <repo-url>
cd Atvinna
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create a root `.env` file:

```bash
MISTRAL_API_KEY=your_mistral_api_key_here
MISTRAL_MODEL=mistral-small-latest
```

Run the required CLI and paste the JD when prompted:

```bash
python main.py
```

Finish each multiline input with a line containing only `END`.

The command uses the recruiter-provided JD, makes five real Mistral API calls,
and writes `output.json` in the repository root.

`MISTRAL_API_KEY` is required. The production pipeline does not use hardcoded
mock responses because the assignment requires every step to make a real LLM
API call.

## Optional Dashboard

Start the FastAPI backend:

```bash
uvicorn backend.main:app --reload
```

Start the React frontend in a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

The dashboard sends `POST /api/run-pipeline` with:

```json
{
  "job_description": "Your JD text",
  "hiring_manager_notes": "Optional notes"
}
```

The dashboard does not prefill a JD. Recruiters must paste the Job Description
they want the pipeline to process.

## Candidate Database

Atvinna loads six structured candidate profiles from
`backend/data/candidates.json`. After Step 3, Atvinna locally scores all six
profiles against the JD signals and search strategy. This deterministic scoring
layer is not an LLM step, so the required five-step pipeline remains intact.

The current database is software-engineering focused:

- Sophia Martinez: new grad frontend engineer
- Maya Chen: early-career AI software engineer
- Daniel Brooks: backend software engineer
- Priya Nair: AI / machine learning engineer
- Marcus Reed: senior software engineer
- Shuzhu Chen: AI/ML full-stack engineer

The locally selected top candidate is then passed into Step 4 so the outreach
can start with the candidate's first name and reference real profile evidence.
Step 5 summarizes that same selected candidate.

The API response includes `candidate_matches` for the dashboard. The required
`output.json` remains unchanged and contains only the assignment's five required
top-level keys.

Each dashboard candidate match shows one combined score plus the breakdown
underneath:

```text
Overall Match: 86
JD Match: 70
Hiring Manager Preference: +16
```

`JD Match` is the base fit against the extracted JD signals and search strategy.
Step 1 dynamically extracts JD-specific `related_skill_aliases`,
`adjacent_backgrounds`, and `seniority_level`. The local scorer then uses those
signals deterministically instead of relying on a fixed industry taxonomy.

The score uses coverage rather than loose keyword accumulation:

- required skills: 50%
- target background / role fit: 25%
- keywords and tools: 15%
- seniority or context: 10%

Score caps keep the result honest. A candidate must satisfy most required
skills and target background signals to reach the 90-100 range. Candidates with
partial skill coverage or adjacent backgrounds are capped lower, even when they
match several keywords.

`Hiring Manager Preference` is a small capped add-on from optional notes, such
as preferred industries, tools, or responsibilities. It can break ties but
cannot push a candidate with weak core JD coverage into a top-match score.

## Score Interpretation

Atvinna keeps the scoring rubric unchanged, then applies a separate match
interpretation layer after the final score is calculated:

```text
80-100: Recruiter Screen | Strong enough for recruiter outreach
65-79:  Potential Match  | Review before outreach
50-64:  Consider         | Possible fit with gaps
35-49:  Low Match        | Unlikely fit
Below 35: Not Recommended | Do not prioritize
```

Because the assignment output schema should not gain new top-level keys, the
interpretation is included in `fit_reason` for candidate matches and appended
as recruiter guidance in the selected candidate summary. Candidate match
explanations change tone by score band, so lower-scoring candidates are not
described as matching the role. The dashboard displays the numeric score as a
percentage and shows only the `match_level` label to avoid repetitive UI copy.

## Bonus: Boolean Query Validator

Step 3 validates the generated `boolean_query` locally before `output.json` is
written.

`validate_boolean_query(boolean_query: str)` returns:

```json
{
  "is_valid": true,
  "warnings": [],
  "suggestions": []
}
```

The validator checks:

- balanced parentheses
- at least one `AND` or `OR`
- no empty quotes
- enough searchable terms to avoid a one-keyword broad query
- no repeated operators such as `AND AND` or `OR OR`
- no obvious protected-class filters

If validation fails, Step 3 retries up to two times with the validation feedback
included in the next LLM prompt. If the query is still invalid after those
retries, the pipeline continues with warnings recorded in `pipeline_trace`
instead of changing the required output schema.

## Step 4 Self-Correction

Step 4 generates three outreach variants in one LLM call:

- `warm_direct`
- `startup_casual`
- `executive_brief`

Each variant is validated locally in Python:

- `len(outreach_message) < 300`
- `specific_detail` is non-empty
- `specific_detail` is grounded in the JD or extracted JD signals
- `outreach_message` includes that specific detail or a close exact phrase
- banned generic outreach phrases are not present
- the message opens with the selected candidate's first name
- the message ends with a simple low-pressure CTA

The best passing variant is selected as the required
`outreach_message.outreach_message`. The other variants are stored only in
`pipeline_trace` and printed in the CLI; they are not added as new top-level
keys.

If validation fails, the failure reason is logged as `result: "retry"` and is
included in the next LLM prompt. After three failed attempts, the trace records
`result: "fail"` and the pipeline exits gracefully.

Run the local guardrail validator tests:

```bash
python -m unittest backend/tests/test_validators.py
```

## Ambiguous Seniority

When a JD does not contain a clear seniority signal, Atvinna does not invent
one. Step 1 records the missing signal, and Step 2 recommends a conservative
range based on the available evidence. For example, an ambiguous individual
contributor role may be sourced as junior-to-mid rather than silently treated
as senior. This decision is written into the strategy and pipeline trace.

## Guardrails

Boolean queries can cause harm when they encode demographic proxies,
protected-class filters, or prestige-only assumptions. The Step 2 and Step 3
prompts explicitly restrict the strategy and query to job-relevant
backgrounds, company types, and skills. `validate_boolean_query()` also checks
syntax, breadth, repeated operators, empty quotes, and protected-class filters
before the final output is written.

### Bias Detection Guardrail

Atvinna also runs `detect_recruiting_bias()` before finalizing `output.json`.
This check scans the JD, search strategy, Boolean query, and outreach message
for risky recruiting language.

It detects warnings such as:

- age-coded terms like `young`, `recent grad only`, `energetic`, or
  `digital native`
- gender-coded terms like `aggressive`, `dominant`, or `nurturing`
- nationality or language issues like `native English speaker`, `US-born`, or
  `local only`
- school prestige filters like `Ivy League only` or `top school only`
- overly narrow company targeting like `FAANG only` or `ex-Google only`

The guardrail is non-blocking by default. It records warnings in
`pipeline_trace` and prints them in the CLI so a recruiter or reviewer can
broaden the language before using the output.

Generic outreach can damage employer brand. Step 4 requires a concrete phrase
from the JD and rejects messages that do not include it.

## Sample Run

```text
$ python main.py
Paste the Job Description:
Finish with a line containing only END.
Paste optional Hiring Manager Notes, or enter END immediately:
Finish with a line containing only END.
Pipeline complete. Wrote output.json.
Trace entries: 5
```

The repository includes `output.json` from this software-engineering Mistral run.

```json
{
  "candidate_search_strategy": {
    "target_backgrounds": [
      "backend development",
      "distributed systems engineering",
      "software architecture",
      "reliability engineering",
      "performance engineering",
      "machine learning engineering",
      "data engineering",
      "product engineering",
      "growth engineering",
      "AI platform engineering"
    ],
    "target_companies": [
      "high-growth tech companies",
      "AI-first startups",
      "scalable infrastructure companies",
      "content optimization platforms",
      "search and discovery companies",
      "experimentation platforms",
      "workflow automation companies",
      "LLM application companies",
      "agent framework companies"
    ],
    "keywords": [
      "backend engineer",
      "distributed systems",
      "system design",
      "Go",
      "Golang",
      "Python",
      "Java",
      "C++",
      "scalable systems",
      "reliability engineering",
      "AIGC",
      "generative AI",
      "LLM applications",
      "agent frameworks",
      "workflow automation",
      "experimentation platforms",
      "user-facing products",
      "search and discovery systems"
    ],
    "seniority": "senior"
  },
  "boolean_query": "(backend engineer OR distributed systems OR system design OR Go OR Golang OR Python OR Java OR C++) AND (scalable systems OR reliability engineering OR AIGC OR generative AI OR LLM applications OR agent frameworks OR workflow automation OR experimentation platforms OR user-facing products OR search and discovery systems) AND (senior)",
  "outreach_message": {
    "outreach_message": "Hi Shuzhu, your Python, Java, and microservices background stands out. We’re hiring for a backend role building the next generation of growth and content optimization systems. Worth a quick conversation?",
    "specific_detail": "next generation of growth and content optimization systems",
    "character_count": 203,
    "attempts": 2
  },
  "candidate_summary": {
    "name": "Shuzhu Chen",
    "current_company": "Kismet XYZ Inc.",
    "key_skills": [
      "Python",
      "Java",
      "Microservices",
      "AI/ML Applications",
      "Distributed Systems"
    ],
    "fit_reason": "Shuzhu has strong backend engineering experience with Python and Java, including microservices and distributed systems design at Kismet XYZ Inc., where they built scalable event-driven data pipelines and RESTful APIs. Their AI/ML focus aligns with the AIGC and LLM applications mentioned in the JD. Recruiter guidance: Consider.",
    "concerns": "Go proficiency is not evident in the profile and should be confirmed in the recruiter screen. Scalability and reliability engineering experience at scale should also be verified."
  },
  "pipeline_trace": [
    {
      "step": 1,
      "action": "extract_jd_signals",
      "attempt": 1,
      "result": "pass",
      "note": "Extracted role signals and missing information."
    },
    {
      "step": 2,
      "action": "generate_search_strategy",
      "attempt": 1,
      "result": "pass",
      "note": "Seniority decision: senior"
    },
    {
      "step": 3,
      "action": "generate_boolean_query",
      "attempt": 1,
      "result": "pass",
      "note": "Boolean query validation: {\"is_valid\": true,\"warnings\": [],\"suggestions\": []}"
    },
    {
      "step": 4,
      "action": "generate_outreach_message",
      "attempt": 1,
      "result": "retry",
      "note": "Invalid outreach JSON/schema: missing specific_detail"
    },
    {
      "step": 4,
      "action": "generate_outreach_message",
      "attempt": 2,
      "result": "pass",
      "note": "Outreach passed local validation for Shuzhu Chen (local match score 53). Selected outreach variant: startup_casual."
    },
    {
      "step": 5,
      "action": "generate_candidate_summary",
      "attempt": 1,
      "result": "pass",
      "note": "Generated summary for locally selected candidate Shuzhu Chen. Applied match interpretation to candidate_summary.fit_reason."
    }
  ]
}
```

## Brief Write-Up

**What would I improve with another week?**  
I would add stronger malformed-response recovery for every LLM step, platform-
specific Boolean query validation, candidate database upload/import support,
and run history for comparing strategy iterations.

**What did I notice that was not explicitly stated?**  
The trace is not just logging; it is evidence that the pipeline really executed
in sequence. The intermediate schemas also create trust because a reviewer can
see where an unsupported assumption entered the workflow.

**Why five steps instead of one? What breaks if Steps 1 and 2 are collapsed?**  
Each step has a different success criterion and can be inspected independently.
If Steps 1 and 2 are collapsed, the search strategy can quietly skip missing
information, invent seniority, or mix raw JD facts with sourcing assumptions.

**Which parts used AI and which required human judgment?**  
AI generates JD signals, strategy, Boolean query, outreach, and candidate
summary. Human judgment defines the schemas, prompt boundaries, seniority
policy, bias guardrail, local outreach validation, retry limit, and graceful
failure behavior.

## Verification

```bash
python main.py
python -m unittest backend/tests/test_validators.py
cd frontend && npm run build
```
