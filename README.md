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
   missing information, and an exact JD detail for outreach.
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

Atvinna loads five structured candidate profiles from
`backend/data/candidates.json`. After Step 3, Atvinna locally scores all five
profiles against the JD signals and search strategy. This deterministic scoring
layer is not an LLM step, so the required five-step pipeline remains intact.

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
`Hiring Manager Preference` is a capped add-on from optional notes, such as
preferred industries, tools, or responsibilities. The add-on is capped so notes
can break ties without overpowering core JD requirements.

When hiring manager notes are present, JD Match is calibrated to leave a 20-point
preference band. This prevents strong JD matches from swallowing the preference
score at 100 and makes the manager signal visible in the dashboard.

## Step 4 Self-Correction

Step 4 validates outreach locally in Python:

- `len(outreach_message) < 300`
- `specific_detail` is non-empty
- `specific_detail` is grounded in the JD or extracted JD signals
- `outreach_message` includes that specific detail or a close exact phrase
- banned generic outreach phrases are not present
- the message opens with the selected candidate's first name
- the message ends with a simple low-pressure CTA

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
backgrounds, company types, and skills. `validate_boolean_query()` also rejects
obvious protected-class filters before a query is returned.

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

The repository includes `output.json` from this real Mistral run.

```json
{
  "candidate_search_strategy": {
    "target_backgrounds": [
      "Finance Business Partner",
      "FP&A Analyst",
      "Financial Planning & Analysis",
      "Corporate Finance",
      "Management Accounting"
    ],
    "target_companies": [
      "high-growth startups",
      "scale-ups",
      "mid-market companies",
      "private equity-backed firms",
      "venture-backed companies"
    ],
    "keywords": [
      "SQL",
      "Power BI",
      "Excel",
      "finance",
      "FP&A",
      "financial planning",
      "financial analysis",
      "business partnering",
      "financial modeling",
      "budgeting",
      "forecasting",
      "data visualization",
      "business intelligence"
    ],
    "seniority": "mid-to-senior (5+ years of finance experience)"
  },
  "boolean_query": "( ( \"Finance Business Partner\" OR \"FP&A Analyst\" OR \"Financial Planning & Analysis\" OR \"Corporate Finance\" OR \"Management Accounting\" ) AND ( \"high-growth startup*\" OR \"scale-up*\" OR \"mid-market company\" OR \"private equity-backed\" OR \"venture-backed\" ) ) AND ( ( \"SQL\" OR \"Power BI\" OR \"Excel\" ) AND ( finance OR \"FP&A\" OR \"financial planning\" OR \"financial analysis\" OR \"business partnering\" OR \"financial modeling\" OR budgeting OR forecasting OR \"data visualization\" OR \"business intelligence\" ) ) AND ( \"5+ years\" OR \"mid-to-senior\" OR \"senior finance\" )",
  "outreach_message": {
    "outreach_message": "Hi Sophia, your 6 years of FP&A in media caught my eye. We’re hiring a lead FP&A role for budget planning and LATAM business reviews. Worth a quick conversation?",
    "specific_detail": "lead FP&A",
    "character_count": 161,
    "attempts": 1
  },
  "candidate_summary": {
    "name": "Sophia Martinez",
    "current_company": "Warner Bros. Discovery",
    "key_skills": [
      "SQL",
      "Power BI",
      "Excel",
      "FP&A",
      "Financial Modeling"
    ],
    "fit_reason": "Sophia has 6 years of FP&A experience in media and digital content companies, including leading quarterly forecasting, annual budgeting, and financial modeling at Warner Bros. Discovery. She matches the core requirements with demonstrated skills in SQL, Power BI, and Excel, and has direct experience in budget planning and business reviews relevant to the role.",
    "concerns": "LATAM business reviews context should be confirmed in recruiter screen. While her media/digital content experience aligns well, the recruiter should verify her familiarity with the specific LATAM market dynamics and industry nuances."
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
      "note": "Seniority decision: mid-to-senior (5+ years of finance experience)"
    },
    {
      "step": 3,
      "action": "generate_boolean_query",
      "attempt": 1,
      "result": "pass",
      "note": "Generated one sourcing-style Boolean query."
    },
    {
      "step": 4,
      "action": "generate_outreach_message",
      "attempt": 1,
      "result": "pass",
      "note": "Outreach passed local validation for Sophia Martinez (local match score 100)."
    },
    {
      "step": 5,
      "action": "generate_candidate_summary",
      "attempt": 1,
      "result": "pass",
      "note": "Generated summary for locally selected candidate Sophia Martinez."
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
