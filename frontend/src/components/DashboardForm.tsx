import { AlertCircle, Play } from "lucide-react";

interface DashboardFormProps {
  jobDescription: string;
  notes: string;
  loading: boolean;
  error: string;
  onJobDescriptionChange: (value: string) => void;
  onNotesChange: (value: string) => void;
  onSubmit: () => void;
}

export function DashboardForm({
  jobDescription,
  notes,
  loading,
  error,
  onJobDescriptionChange,
  onNotesChange,
  onSubmit,
}: DashboardFormProps) {
  return (
    <aside className="h-full border-b border-slate-200 bg-white p-5 lg:border-b-0 lg:border-r lg:p-6">
      <div className="mb-6">
        <h2 className="text-base font-semibold text-slate-900">Role context</h2>
        <p className="mt-1 text-sm leading-6 text-slate-500">
          Add the job description and any sourcing priorities.
        </p>
      </div>

      <label className="mb-2 block text-sm font-medium text-slate-700" htmlFor="job-description">
        Job Description
      </label>
      <textarea
        id="job-description"
        value={jobDescription}
        onChange={(event) => onJobDescriptionChange(event.target.value)}
        placeholder="Paste the job description here."
        className="min-h-72 w-full resize-y rounded-md border border-slate-300 bg-white p-3 text-sm leading-6 text-slate-800 outline-none focus:border-slate-500 focus:ring-1 focus:ring-slate-500"
      />
      <p className="mt-1 text-right text-xs text-slate-400">{jobDescription.length.toLocaleString()} characters</p>

      <label className="mb-2 mt-5 block text-sm font-medium text-slate-700" htmlFor="manager-notes">
        Hiring Manager Notes <span className="font-normal text-slate-400">Optional</span>
      </label>
      <textarea
        id="manager-notes"
        value={notes}
        onChange={(event) => onNotesChange(event.target.value)}
        placeholder="Add priorities, constraints, or candidate profile details."
        className="min-h-32 w-full resize-y rounded-md border border-slate-300 bg-white p-3 text-sm leading-6 text-slate-800 outline-none placeholder:text-slate-400 focus:border-slate-500 focus:ring-1 focus:ring-slate-500"
      />
      <p className="mt-1 text-right text-xs text-slate-400">{notes.length.toLocaleString()} characters</p>

      <button
        type="button"
        onClick={onSubmit}
        disabled={loading || !jobDescription.trim()}
        className="mt-5 flex h-11 w-full items-center justify-center gap-2 rounded-md bg-slate-900 px-4 text-sm font-semibold text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-300"
      >
        <Play className="h-4 w-4" />
        {loading ? "Running Pipeline..." : "Run Pipeline"}
      </button>

      {error && (
        <div className="mt-4 flex gap-2 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}
    </aside>
  );
}
