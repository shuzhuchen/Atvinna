import { useEffect, useState } from "react";
import { AlertCircle, CheckCircle2, ClipboardList, Download, RotateCcw } from "lucide-react";
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
  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-slate-500">Use this query in your sourcing platform.</p>
        <CopyButton value={result.boolean_query} label="Copy query" />
      </div>
      <pre className="overflow-x-auto whitespace-pre-wrap rounded-md border border-slate-200 bg-slate-50 p-4 font-mono text-xs leading-6 text-slate-800">
        {result.boolean_query}
      </pre>
    </div>
  );
}

function OutreachTab({ result }: { result: PipelineOutput }) {
  const [draft, setDraft] = useState(result.outreach_message.outreach_message);

  useEffect(() => {
    setDraft(result.outreach_message.outreach_message);
  }, [result.outreach_message.outreach_message]);

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-slate-500">Review and personalize the validated message before sending.</p>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setDraft(result.outreach_message.outreach_message)}
            title="Reset to generated message"
            disabled={draft === result.outreach_message.outreach_message}
            className="inline-flex h-9 items-center gap-2 rounded-md border border-slate-300 bg-white px-3 text-xs font-semibold text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:text-slate-300"
          >
            <RotateCcw className="h-3.5 w-3.5" />
            Reset
          </button>
          <CopyButton value={draft} label="Copy message" />
        </div>
      </div>
      <textarea
        value={draft}
        onChange={(event) => setDraft(event.target.value)}
        className="min-h-40 w-full resize-y rounded-md border border-slate-300 bg-white p-4 text-sm leading-7 text-slate-800 outline-none focus:border-slate-500 focus:ring-1 focus:ring-slate-500"
      />
      <p className={`mt-2 text-right text-xs ${draft.length < 300 ? "text-slate-400" : "text-red-600"}`}>
        {draft.length} / 299 characters
      </p>
      <div className="mt-5 grid gap-4 border-t border-slate-200 pt-5 sm:grid-cols-3">
        <div>
          <p className="text-xs font-semibold uppercase text-slate-500">Specific detail</p>
          <p className="mt-1 text-sm text-slate-700">{result.outreach_message.specific_detail}</p>
        </div>
        <div>
          <p className="text-xs font-semibold uppercase text-slate-500">Character count</p>
          <p className="mt-1 text-sm text-slate-700">{result.outreach_message.character_count}</p>
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
        <div className="divide-y divide-slate-200 border-y border-slate-200">
          {result.candidate_matches.map((match, index) => (
            <div key={match.full_name} className="grid gap-3 py-4 sm:grid-cols-[32px_1fr_auto]">
              <span className="text-sm font-semibold text-slate-400">#{index + 1}</span>
              <div>
                <p className="text-sm font-semibold text-slate-800">{match.full_name}</p>
                <p className="mt-0.5 text-xs text-slate-500">{match.current_company}</p>
                <div className="mt-2">
                  <TagList items={match.matched_skills} />
                </div>
                {match.matched_manager_preferences.length > 0 && (
                  <div className="mt-3">
                    <p className="mb-1 text-xs font-semibold uppercase text-slate-400">Manager preferences</p>
                    <TagList items={match.matched_manager_preferences} />
                  </div>
                )}
                <p className="mt-2 text-xs leading-5 text-slate-500">{match.fit_reason}</p>
              </div>
              <div className="text-right">
                <p className="text-lg font-semibold text-slate-900">{match.match_score}</p>
                <p className="text-xs text-slate-400">overall match</p>
                <div className="mt-3 space-y-1 text-xs text-slate-500">
                  <p>JD Match: {match.jd_match_score}</p>
                  <p>Hiring Manager: +{match.hiring_manager_score}</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function PipelineTraceTab({ result }: { result: PipelineOutput }) {
  return (
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
    <section className="flex min-h-96 items-center justify-center bg-white p-6">
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
  return (
    <section className="flex min-h-96 items-center justify-center bg-white p-6">
      <div className="max-w-sm text-center">
        <div className="mx-auto h-2 w-24 rounded-full bg-slate-300" />
        <p className="mt-4 text-sm font-medium text-slate-700">Running five pipeline steps...</p>
        <p className="mt-1 text-sm text-slate-500">Results will appear here when the workflow completes.</p>
      </div>
    </section>
  );
}
