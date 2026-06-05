import { ArrowRight, Check } from "lucide-react";

interface WorkflowProgressProps {
  hasJobDescription: boolean;
  hasResult: boolean;
  loading: boolean;
}

const stages = ["JD", "Search Strategy", "Boolean Query", "Outreach", "Candidate Summary"];

export function WorkflowProgress({ hasJobDescription, hasResult, loading }: WorkflowProgressProps) {
  return (
    <div className="mb-4 overflow-x-auto rounded-lg border border-slate-200 bg-white px-4 py-3 shadow-sm">
      <div className="flex min-w-max items-center gap-3">
        {stages.map((stage, index) => {
          const complete = hasResult || (index === 0 && hasJobDescription);
          const active = loading && index > 0;

          return (
            <div key={stage} className="flex items-center gap-3">
              <div className="flex items-center gap-2">
                <span
                  className={`flex h-5 w-5 items-center justify-center rounded-full border text-[10px] font-semibold ${
                    complete
                      ? "border-emerald-600 bg-emerald-600 text-white"
                      : active
                        ? "border-slate-500 bg-white text-slate-700"
                        : "border-slate-300 bg-white text-slate-400"
                  }`}
                >
                  {complete ? <Check className="h-3 w-3" /> : index + 1}
                </span>
                <span className={`text-xs font-medium ${complete ? "text-slate-800" : "text-slate-500"}`}>
                  {stage}
                </span>
              </div>
              {index < stages.length - 1 && <ArrowRight className="h-3.5 w-3.5 text-slate-300" />}
            </div>
          );
        })}
      </div>
    </div>
  );
}
