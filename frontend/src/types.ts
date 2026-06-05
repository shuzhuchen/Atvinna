export interface CandidateSearchStrategy {
  target_backgrounds: string[];
  target_companies: string[];
  keywords: string[];
  seniority: string;
}

export interface OutreachOutput {
  outreach_message: string;
  specific_detail: string;
  character_count: number;
  attempts: number;
}

export interface CandidateSummary {
  name: string;
  current_company: string;
  key_skills: string[];
  fit_reason: string;
  concerns: string;
}

export interface CandidateMatch {
  full_name: string;
  current_company: string;
  match_score: number;
  jd_match_score: number;
  hiring_manager_score: number;
  matched_skills: string[];
  matched_manager_preferences: string[];
  fit_reason: string;
  concerns: string;
}

export interface TraceEntry {
  step: number;
  action: string;
  attempt: number;
  result: "pass" | "retry" | "fail";
  note: string;
}

export interface PipelineOutput {
  candidate_search_strategy: CandidateSearchStrategy;
  boolean_query: string;
  outreach_message: OutreachOutput;
  candidate_summary: CandidateSummary;
  pipeline_trace: TraceEntry[];
  candidate_matches: CandidateMatch[];
}

export function isPipelineOutput(value: unknown): value is PipelineOutput {
  if (!value || typeof value !== "object") {
    return false;
  }

  const output = value as Record<string, unknown>;
  const strategy = output.candidate_search_strategy as Record<string, unknown> | undefined;
  const outreach = output.outreach_message as Record<string, unknown> | undefined;
  const summary = output.candidate_summary as Record<string, unknown> | undefined;

  const candidateMatches = output.candidate_matches;

  return Boolean(
    strategy &&
      Array.isArray(strategy.target_backgrounds) &&
      Array.isArray(strategy.target_companies) &&
      Array.isArray(strategy.keywords) &&
      typeof strategy.seniority === "string" &&
      typeof output.boolean_query === "string" &&
      outreach &&
      typeof outreach.outreach_message === "string" &&
      typeof outreach.specific_detail === "string" &&
      typeof outreach.character_count === "number" &&
      typeof outreach.attempts === "number" &&
      summary &&
      typeof summary.name === "string" &&
      typeof summary.current_company === "string" &&
      Array.isArray(summary.key_skills) &&
      typeof summary.fit_reason === "string" &&
      typeof summary.concerns === "string" &&
      Array.isArray(output.pipeline_trace) &&
      Array.isArray(candidateMatches) &&
      candidateMatches.every((candidate) => {
        const match = candidate as Record<string, unknown>;
        return (
          typeof match.full_name === "string" &&
          typeof match.current_company === "string" &&
          typeof match.match_score === "number" &&
          typeof match.jd_match_score === "number" &&
          typeof match.hiring_manager_score === "number" &&
          Array.isArray(match.matched_skills) &&
          Array.isArray(match.matched_manager_preferences) &&
          typeof match.fit_reason === "string" &&
          typeof match.concerns === "string"
        );
      }),
  );
}
