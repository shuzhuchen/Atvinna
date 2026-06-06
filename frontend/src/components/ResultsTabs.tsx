import { useEffect, useState } from "react";
import { AlertCircle, CheckCircle2, ClipboardList, Download, RotateCcw, ShieldCheck } from "lucide-react";
import { isPipelineOutput, type PipelineOutput } from "../types";
import { CopyButton } from "./CopyButton";

type TabId = "strategy" | "query" | "outreach" | "summary" | "trace";

const tabs: Array<{ id: TabId; label: string }> = [
  { id: "strategy", label: "Search Strategy" },
  { id: "query", label: "Boolean Query" },
  { id: "outreach", label: "Outreach Message" },
  { id: "summary", label: "Candidate Summary" },
  { id: "trace", label: "Pipeline Trace" },
];

const loadingStages = ["JD", "Search Strategy", "Boolean Query", "Outreach", "Candidate Summary"];

interface BooleanValidationResult {
  is_valid: boolean;
  warnings: string[];
  suggestions: string[];
}

interface BiasDetectionResult {
  has_warning: boolean;
  warnings: string[];
  recommended_action: string;
}

interface OutreachVariantsResult {
  variants: Record<string, string>;
  selected: string;
}

function interpretMatchScore(score: number): { matchLevel: string; recommendation: string } {
  if (score >= 80) {
    return {
      matchLevel: "Recruiter Screen",
      recommendation: "Strong enough for recruiter outreach",
    };
  }
  if (score >= 65) {
    return {
      matchLevel: "Potential Match",
      recommendation: "Review before outreach",
    };
  }
  if (score >= 50) {
    return {
      matchLevel: "Consider",
      recommendation: "Possible fit with gaps",
    };
  }
  if (score >= 35) {
    return {
      matchLevel: "Low Match",
      recommendation: "Unlikely fit",
    };
  }
  return {
    matchLevel: "Not Recommended",
    recommendation: "Do not prioritize",
  };
}

function conciseCandidateExplanation(fitReason: string, interpretation: { matchLevel: string; recommendation: string }) {
  return fitReason
    .replace(`${interpretation.matchLevel} - ${interpretation.recommendation}. `, "")
    .replace(`${interpretation.matchLevel}. `, "")
    .replace(`Recruiter guidance: ${interpretation.matchLevel} - ${interpretation.recommendation}.`, "")
    .replace(`Recruiter guidance: ${interpretation.matchLevel}.`, "")
    .replace(/Match interpretation:\s*[^.]+\.?/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

function parseJsonFromNote(note: string, marker: string, endMarker?: string): unknown | null {
  const markerIndex = note.indexOf(marker);
  if (markerIndex === -1) {
    return null;
  }

  const start = markerIndex + marker.length;
  const end = endMarker ? note.indexOf(endMarker, start) : -1;
  const jsonText = note.slice(start, end === -1 ? undefined : end).trim();

  try {
    return JSON.parse(jsonText);
  } catch {
    return null;
  }
}

function getStepNote(result: PipelineOutput, step: number): string {
  const entry = [...result.pipeline_trace].reverse().find((traceEntry) => traceEntry.step === step);
  return entry?.note ?? "";
}

function getBooleanValidation(result: PipelineOutput): BooleanValidationResult | null {
  const parsed = parseJsonFromNote(getStepNote(result, 3), "Boolean query validation: ");
  if (!parsed || typeof parsed !== "object") {
    return null;
  }

  const value = parsed as Partial<BooleanValidationResult>;
  if (typeof value.is_valid !== "boolean" || !Array.isArray(value.warnings) || !Array.isArray(value.suggestions)) {
    return null;
  }

  return {
    is_valid: value.is_valid,
    warnings: value.warnings,
    suggestions: value.suggestions,
  };
}

function getBiasDetection(result: PipelineOutput): BiasDetectionResult | null {
  const parsed = parseJsonFromNote(getStepNote(result, 4), "Bias detection: ");
  if (!parsed || typeof parsed !== "object") {
    return null;
  }

  const value = parsed as Partial<BiasDetectionResult>;
  if (
    typeof value.has_warning !== "boolean" ||
    !Array.isArray(value.warnings) ||
    typeof value.recommended_action !== "string"
  ) {
    return null;
  }

  return {
    has_warning: value.has_warning,
    warnings: value.warnings,
    recommended_action: value.recommended_action,
  };
}

function getOutreachVariants(result: PipelineOutput): OutreachVariantsResult | null {
  const parsed = parseJsonFromNote(getStepNote(result, 4), "Outreach variants: ", " Bias detection: ");
  if (!parsed || typeof parsed !== "object") {
    return null;
  }

  const value = parsed as Partial<OutreachVariantsResult>;
  if (!value.variants || typeof value.variants !== "object" || typeof value.selected !== "string") {
    return null;
  }

  return {
    variants: value.variants,
    selected: value.selected,
  };
}

function TagList({ items = [] }: { items?: string[] }) {
  return (
    <div className="flex flex-wrap gap-2">
      {items.map((item) => (
        <span
          key={item}
          className="rounded border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs font-medium text-slate-700"
        >
          {item}
        </span>
      ))}
    </div>
  );
}

function SearchStrategyTab({ result }: { result: PipelineOutput }) {
  const strategy = result.candidate_search_strategy;

  return (
    <div>
      <div className="grid gap-6 sm:grid-cols-2">
        <div>
          <p className="mb-2 text-xs font-semibold uppercase text-slate-500">Target backgrounds</p>
          <TagList items={strategy.target_backgrounds} />
        </div>
        <div>
          <p className="mb-2 text-xs font-semibold uppercase text-slate-500">Target companies</p>
          <TagList items={strategy.target_companies} />
        </div>
        <div>
          <p className="mb-2 text-xs font-semibold uppercase text-slate-500">Keywords</p>
          <TagList items={strategy.keywords} />
        </div>
        <div>
          <p className="mb-2 text-xs font-semibold uppercase text-slate-500">Seniority</p>
          <p className="text-sm leading-7 text-slate-700">{strategy.seniority}</p>
        </div>
      </div>
    </div>
  );
}

function BooleanQueryTab({ result }: { result: PipelineOutput }) {
  const validation = getBooleanValidation(result);

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-slate-500">Use this query in your sourcing platform.</p>
        <CopyButton value={result.boolean_query} label="Copy query" />
      </div>
      <pre className="overflow-x-auto whitespace-pre-wrap rounded-md border border-slate-200 bg-slate-50 p-4 font-mono text-xs leading-6 text-slate-800">
        {result.boolean_query}
      </pre>
      {validation && (
        <div className="mt-5 rounded-md border border-slate-200 bg-white p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-xs font-semibold uppercase text-slate-500">Boolean Query Validator</p>
            <span
              className={`text-xs font-semibold ${
                validation.is_valid ? "text-emerald-700" : "text-amber-700"
              }`}
            >
              {validation.is_valid ? "Valid" : "Warnings"}
            </span>
          </div>
          {validation.warnings.length > 0 ? (
            <div className="mt-3 text-sm leading-6 text-slate-700">
              <p className="font-medium text-slate-800">Warnings</p>
              <ul className="mt-1 list-inside list-disc text-slate-600">
                {validation.warnings.map((warning) => (
                  <li key={warning}>{warning}</li>
                ))}
              </ul>
            </div>
          ) : (
            <p className="mt-3 text-sm text-slate-600">No syntax or breadth warnings detected.</p>
          )}
          {validation.suggestions.length > 0 && (
            <div className="mt-3 text-sm leading-6 text-slate-700">
              <p className="font-medium text-slate-800">Suggestions</p>
              <ul className="mt-1 list-inside list-disc text-slate-600">
                {validation.suggestions.map((suggestion) => (
                  <li key={suggestion}>{suggestion}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function OutreachTab({ result }: { result: PipelineOutput }) {
  const [draft, setDraft] = useState(result.outreach_message.outreach_message);
  const outreachVariants = getOutreachVariants(result);
  const [selectedVariant, setSelectedVariant] = useState(outreachVariants?.selected ?? "");

  useEffect(() => {
    setDraft(result.outreach_message.outreach_message);
    setSelectedVariant(outreachVariants?.selected ?? "");
  }, [outreachVariants?.selected, result.outreach_message.outreach_message]);

  function selectVariant(variantName: string, message: string) {
    setSelectedVariant(variantName);
    setDraft(message);
  }

  function resetToGeneratedMessage() {
    setDraft(result.outreach_message.outreach_message);
    setSelectedVariant(outreachVariants?.selected ?? "");
  }

  const specificDetail = result.outreach_message.specific_detail;
  const detailIncluded = draft.toLowerCase().includes(specificDetail.toLowerCase());

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-slate-500">Review and personalize the validated message before sending.</p>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={resetToGeneratedMessage}
            title="Reset to generated message"
            disabled={draft === result.outreach_message.outreach_message && selectedVariant === (outreachVariants?.selected ?? "")}
            className="inline-flex h-9 items-center gap-2 rounded-md border border-slate-300 bg-white px-3 text-xs font-semibold text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:text-slate-300"
          >
            <RotateCcw className="h-3.5 w-3.5" />
            Reset
          </button>
          <CopyButton value={draft} label="Copy message" />
        </div>
      </div>
      {outreachVariants && (
        <div className="mb-5 rounded-md border border-slate-200 bg-white p-4">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <p className="text-xs font-semibold uppercase text-slate-500">A/B/C outreach variants</p>
            <span className="text-xs font-semibold text-slate-700">
              Selected: {selectedVariant ? selectedVariant.replace("_", " ") : "Custom draft"}
            </span>
          </div>
          <div className="grid gap-3">
            {(["warm_direct", "startup_casual", "executive_brief"] as const).map((variantName) => {
              const message = outreachVariants.variants[variantName];
              if (!message) {
                return null;
              }
              const selected = variantName === selectedVariant;

              return (
                <button
                  key={variantName}
                  type="button"
                  onClick={() => selectVariant(variantName, message)}
                  aria-pressed={selected}
                  className={`rounded-md border p-3 ${
                    selected ? "border-slate-900 bg-slate-50" : "border-slate-200 bg-white"
                  } text-left transition-colors hover:border-slate-400 hover:bg-slate-50`}
                >
                  <div className="mb-1 flex flex-wrap items-center justify-between gap-2">
                    <label className="flex cursor-pointer items-center gap-2 text-xs font-semibold uppercase text-slate-500">
                      <input
                        type="radio"
                        name="outreach-variant"
                        checked={selected}
                        onChange={() => selectVariant(variantName, message)}
                        className="h-3.5 w-3.5 accent-slate-900"
                      />
                      {variantName.replace("_", " ")}
                    </label>
                    {selected && <span className="text-xs font-semibold text-slate-900">Selected</span>}
                  </div>
                  <p className="text-sm leading-6 text-slate-700">{message}</p>
                  <p className="mt-1 text-right text-xs text-slate-400">{message.length} characters</p>
                </button>
              );
            })}
          </div>
        </div>
      )}
      <textarea
        value={draft}
        onChange={(event) => {
          setDraft(event.target.value);
          setSelectedVariant("");
        }}
        className="min-h-40 w-full resize-y rounded-md border border-slate-300 bg-white p-4 text-sm leading-7 text-slate-800 outline-none focus:border-slate-500 focus:ring-1 focus:ring-slate-500"
      />
      <p className={`mt-2 text-right text-xs ${draft.length < 300 ? "text-slate-400" : "text-red-600"}`}>
        {draft.length} / 299 characters
      </p>
      <div className="mt-5 grid gap-4 border-t border-slate-200 pt-5 sm:grid-cols-3">
        <div>
          <p className="text-xs font-semibold uppercase text-slate-500">Specific detail</p>
          <p className="mt-1 text-sm text-slate-700">{specificDetail}</p>
          <p className={`mt-1 text-xs ${detailIncluded ? "text-emerald-700" : "text-amber-700"}`}>
            {detailIncluded ? "Included in current message" : "Missing from current message"}
          </p>
        </div>
        <div>
          <p className="text-xs font-semibold uppercase text-slate-500">Character count</p>
          <p className="mt-1 text-sm text-slate-700">{draft.length}</p>
        </div>
        <div>
          <p className="text-xs font-semibold uppercase text-slate-500">Attempts</p>
          <p className="mt-1 text-sm text-slate-700">{result.outreach_message.attempts}</p>
        </div>
      </div>
    </div>
  );
}

function CandidateSummaryTab({ result }: { result: PipelineOutput }) {
  const showHiringManagerAdjustment = result.candidate_matches.some((match) => match.hiring_manager_score !== 0);

  return (
    <div>
      <p className="mb-3 text-xs font-semibold uppercase text-slate-500">Selected candidate summary</p>
      <div className="mb-6 grid gap-4 sm:grid-cols-2">
        <div>
          <p className="text-xs font-semibold uppercase text-slate-500">Name</p>
          <p className="mt-1 text-sm text-slate-700">{result.candidate_summary.name}</p>
        </div>
        <div>
          <p className="text-xs font-semibold uppercase text-slate-500">Current company</p>
          <p className="mt-1 text-sm text-slate-700">{result.candidate_summary.current_company}</p>
        </div>
      </div>
      <div>
        <p className="mb-2 text-xs font-semibold uppercase text-slate-500">Key skills</p>
        <TagList items={result.candidate_summary.key_skills} />
      </div>
      <div className="mt-6 grid gap-6 sm:grid-cols-2">
        <div>
          <p className="mb-3 text-xs font-semibold uppercase text-slate-500">Fit reason</p>
          <p className="flex gap-2 text-sm leading-7 text-slate-700">
            <CheckCircle2 className="mt-1 h-4 w-4 shrink-0 text-emerald-600" />
            <span>{result.candidate_summary.fit_reason}</span>
          </p>
        </div>
        <div>
          <p className="mb-3 text-xs font-semibold uppercase text-slate-500">Concerns</p>
          <p className="flex gap-2 text-sm leading-7 text-slate-700">
            <AlertCircle className="mt-1 h-4 w-4 shrink-0 text-amber-600" />
            <span>{result.candidate_summary.concerns}</span>
          </p>
        </div>
      </div>

      <div className="mt-8">
        <p className="mb-3 text-xs font-semibold uppercase text-slate-500">Candidate matches</p>
        <div className="grid gap-3">
          {result.candidate_matches.map((match, index) => {
            const interpretation = interpretMatchScore(match.match_score);
            const explanation = conciseCandidateExplanation(match.fit_reason, interpretation);

            return (
              <div key={match.full_name} className="rounded-md border border-slate-200 bg-white p-4">
                <div className="grid gap-4 sm:grid-cols-[1fr_auto]">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                      <p className="text-sm font-semibold text-slate-900">#{index + 1} {match.full_name}</p>
                      <p className="text-xs text-slate-500">{match.current_company}</p>
                    </div>
                    {match.matched_skills.length > 0 && (
                      <div className="mt-3">
                        <TagList items={match.matched_skills.slice(0, 5)} />
                      </div>
                    )}
                    {showHiringManagerAdjustment && match.matched_manager_preferences.length > 0 && (
                      <div className="mt-3">
                        <TagList items={match.matched_manager_preferences.slice(0, 3)} />
                      </div>
                    )}
                    <p className="mt-3 text-sm leading-6 text-slate-600">{explanation}</p>
                  </div>
                  <div className="sm:min-w-44 sm:text-right">
                    <p className="text-2xl font-semibold leading-none text-slate-950">{match.match_score}%</p>
                    <p className="mt-1 text-xs text-slate-400">overall match</p>
                    <p className="mt-3 text-sm font-semibold text-slate-900">{interpretation.matchLevel}</p>
                    {showHiringManagerAdjustment && (
                      <p className="mt-3 text-xs text-slate-500">Hiring Manager +{match.hiring_manager_score}</p>
                    )}
                    <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-slate-100">
                      <div className="h-full rounded-full bg-slate-900" style={{ width: `${match.match_score}%` }} />
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function PipelineTraceTab({ result }: { result: PipelineOutput }) {
  const biasDetection = getBiasDetection(result);
  const booleanValidation = getBooleanValidation(result);

  return (
    <div>
      <div className="mb-6 grid gap-4 lg:grid-cols-2">
        {booleanValidation && (
          <div className="rounded-md border border-slate-200 bg-white p-4">
            <div className="mb-2 flex items-center gap-2">
              <ShieldCheck className="h-4 w-4 text-slate-500" />
              <p className="text-xs font-semibold uppercase text-slate-500">Boolean Query Validator</p>
            </div>
            <p
              className={`text-sm font-semibold ${
                booleanValidation.is_valid ? "text-emerald-700" : "text-amber-700"
              }`}
            >
              {booleanValidation.is_valid ? "Passed" : `${booleanValidation.warnings.length} warning(s)`}
            </p>
            {booleanValidation.warnings.length > 0 && (
              <ul className="mt-2 list-inside list-disc text-xs leading-5 text-slate-600">
                {booleanValidation.warnings.map((warning) => (
                  <li key={warning}>{warning}</li>
                ))}
              </ul>
            )}
          </div>
        )}
        {biasDetection && (
          <div className="rounded-md border border-slate-200 bg-white p-4">
            <div className="mb-2 flex items-center gap-2">
              <ShieldCheck className="h-4 w-4 text-slate-500" />
              <p className="text-xs font-semibold uppercase text-slate-500">Bias Detection Guardrail</p>
            </div>
            <p className={`text-sm font-semibold ${biasDetection.has_warning ? "text-amber-700" : "text-emerald-700"}`}>
              {biasDetection.has_warning ? `${biasDetection.warnings.length} warning(s)` : "No warning detected"}
            </p>
            {biasDetection.warnings.length > 0 && (
              <ul className="mt-2 list-inside list-disc text-xs leading-5 text-slate-600">
                {biasDetection.warnings.map((warning) => (
                  <li key={warning}>{warning}</li>
                ))}
              </ul>
            )}
            <p className="mt-2 text-xs leading-5 text-slate-500">{biasDetection.recommended_action}</p>
          </div>
        )}
      </div>
      <div className="divide-y divide-slate-200 border-y border-slate-200">
        {result.pipeline_trace.map((entry, index) => (
          <div key={`${entry.step}-${entry.attempt}-${index}`} className="grid gap-2 py-4 sm:grid-cols-[1fr_auto]">
            <div>
              <p className="font-mono text-xs font-semibold text-slate-800">
                Step {entry.step}: {entry.action}
              </p>
              <p className="mt-1 text-xs text-slate-400">Attempt {entry.attempt}</p>
              {entry.note && <p className="mt-1 text-xs leading-5 text-slate-500">{entry.note}</p>}
            </div>
            <span
              className={`w-fit text-xs font-semibold ${
                entry.result === "pass" ? "text-emerald-700" : "text-amber-700"
              }`}
            >
              {entry.result}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

export function ResultsTabs({ result }: { result: PipelineOutput }) {
  const [activeTab, setActiveTab] = useState<TabId>("strategy");

  if (!isPipelineOutput(result)) {
    return (
      <section className="flex min-h-96 items-center justify-center bg-white p-6">
        <div className="max-w-md rounded-md border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
          The current result uses an outdated output schema. Restart the FastAPI server, refresh this page, and
          run the pipeline again.
        </div>
      </section>
    );
  }

  const retries = result.pipeline_trace.filter((entry) => entry.result === "retry").length;

  function downloadOutput() {
    const { candidate_matches: _candidateMatches, ...requiredOutput } = result;
    const blob = new Blob([JSON.stringify(requiredOutput, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "atvinna-output.json";
    link.click();
    URL.revokeObjectURL(url);
  }

  return (
    <section className="min-w-0 bg-white">
      <div className="border-b border-slate-200 px-5 pt-5 lg:px-7 lg:pt-6">
        <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-base font-semibold text-slate-900">Pipeline Results</h2>
            <p className="mt-1 text-sm text-slate-500">
              5 steps completed{retries > 0 ? ` with ${retries} ${retries === 1 ? "retry" : "retries"}` : ""}
            </p>
          </div>
          <button
            type="button"
            onClick={downloadOutput}
            title="Download pipeline output"
            className="inline-flex h-9 items-center gap-2 rounded-md border border-slate-300 bg-white px-3 text-xs font-semibold text-slate-700 hover:bg-slate-50"
          >
            <Download className="h-3.5 w-3.5" />
            Download JSON
          </button>
        </div>
        <div className="overflow-x-auto">
          <div className="flex min-w-max gap-6" role="tablist" aria-label="Pipeline results">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                type="button"
                role="tab"
                aria-selected={activeTab === tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`border-b-2 pb-3 text-sm font-medium ${
                  activeTab === tab.id
                    ? "border-slate-900 text-slate-900"
                    : "border-transparent text-slate-500 hover:text-slate-800"
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="p-5 lg:p-7" role="tabpanel">
        {activeTab === "strategy" && <SearchStrategyTab result={result} />}
        {activeTab === "query" && <BooleanQueryTab result={result} />}
        {activeTab === "outreach" && <OutreachTab result={result} />}
        {activeTab === "summary" && <CandidateSummaryTab result={result} />}
        {activeTab === "trace" && <PipelineTraceTab result={result} />}
      </div>
    </section>
  );
}

export function EmptyResults() {
  return (
    <section className="flex min-h-full items-center justify-center bg-white p-6">
      <div className="max-w-sm text-center">
        <ClipboardList className="mx-auto h-6 w-6 text-slate-400" />
        <p className="mt-3 text-sm font-medium text-slate-700">No pipeline results yet</p>
        <p className="mt-1 text-sm leading-6 text-slate-500">
          Run the pipeline to review sourcing strategy, outreach, candidate summary, and trace details.
        </p>
      </div>
    </section>
  );
}

export function LoadingResults() {
  const [stageIndex, setStageIndex] = useState(0);

  useEffect(() => {
    setStageIndex(0);
    const intervalId = window.setInterval(() => {
      setStageIndex((current) => Math.min(current + 1, loadingStages.length - 1));
    }, 1400);

    return () => window.clearInterval(intervalId);
  }, []);

  const progressPercent = Math.min(96, ((stageIndex + 1) / loadingStages.length) * 100);

  return (
    <section className="flex min-h-full items-center justify-center bg-white p-6">
      <div className="w-full max-w-md text-center">
        <div className="mx-auto h-2 w-full overflow-hidden rounded-full bg-slate-100">
          <div
            className="h-full rounded-full bg-slate-900 transition-all duration-700 ease-out"
            style={{ width: `${progressPercent}%` }}
          />
        </div>
        <p className="mt-4 text-sm font-medium text-slate-700">Running five pipeline steps...</p>
        <p className="mt-1 text-sm text-slate-500">{loadingStages[stageIndex]}</p>
        <div className="mt-5 grid gap-2 text-left">
          {loadingStages.map((stage, index) => {
            const complete = index <= stageIndex;
            return (
              <div key={stage} className="flex items-center gap-2 text-xs">
                <span
                  className={`flex h-4 w-4 items-center justify-center rounded-full border ${
                    complete ? "border-emerald-600 bg-emerald-600 text-white" : "border-slate-300 text-slate-400"
                  }`}
                >
                  {complete ? <CheckCircle2 className="h-3 w-3" /> : null}
                </span>
                <span className={complete ? "font-medium text-slate-800" : "text-slate-400"}>{stage}</span>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
