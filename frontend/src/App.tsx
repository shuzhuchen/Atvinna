import { useState } from "react";
import { BriefcaseBusiness } from "lucide-react";
import { DashboardForm } from "./components/DashboardForm";
import { EmptyResults, LoadingResults, ResultsTabs } from "./components/ResultsTabs";
import { WorkflowProgress } from "./components/WorkflowProgress";
import { isPipelineOutput, type PipelineOutput } from "./types";

export default function App() {
  const [jobDescription, setJobDescription] = useState("");
  const [notes, setNotes] = useState("");
  const [result, setResult] = useState<PipelineOutput | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function runPipeline() {
    setLoading(true);
    setError("");
    setResult(null);

    try {
      const response = await fetch("/api/run-pipeline", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          job_description: jobDescription,
          hiring_manager_notes: notes || null,
        }),
      });

      if (!response.ok) {
        const body = (await response.json()) as { detail?: string };
        throw new Error(body.detail || "Pipeline request failed.");
      }

      const responseBody: unknown = await response.json();
      if (!isPipelineOutput(responseBody)) {
        throw new Error(
          "The API returned an outdated or invalid output schema. Restart the FastAPI server and run the pipeline again.",
        );
      }

      setResult(responseBody);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Pipeline request failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-[1500px] items-center justify-between px-5 py-4 lg:px-8">
          <div className="flex items-center gap-3">
            <div className="flex h-8 w-8 items-center justify-center rounded-md bg-slate-900 text-white">
              <BriefcaseBusiness className="h-4 w-4" />
            </div>
            <div>
              <h1 className="text-base font-semibold text-slate-900">Atvinna</h1>
              <p className="text-xs text-slate-500">Recruiter Dashboard</p>
            </div>
          </div>
          <span className="hidden text-xs font-medium text-slate-500 sm:block">AI Recruiting Copilot</span>
        </div>
      </header>

      <main className="mx-auto max-w-[1500px] p-4 sm:p-5 lg:p-8">
        <WorkflowProgress
          hasJobDescription={Boolean(jobDescription.trim())}
          hasResult={Boolean(result)}
          loading={loading}
        />
        <div className="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm lg:grid lg:grid-cols-[420px_minmax(0,1fr)]">
          <DashboardForm
            jobDescription={jobDescription}
            notes={notes}
            loading={loading}
            error={error}
            onJobDescriptionChange={setJobDescription}
            onNotesChange={setNotes}
            onSubmit={runPipeline}
          />

          {loading && <LoadingResults />}
          {!loading && result && <ResultsTabs result={result} />}
          {!loading && !result && <EmptyResults />}
        </div>
      </main>
    </div>
  );
}
