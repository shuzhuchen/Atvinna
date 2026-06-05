import { useEffect, useState } from "react";
import { ArrowRight, Check } from "lucide-react";

interface WorkflowProgressProps {
  hasJobDescription: boolean;
  hasResult: boolean;
  loading: boolean;
}

const stages = ["JD", "Search Strategy", "Boolean Query", "Outreach", "Candidate Summary"];

export function WorkflowProgress({ hasJobDescription, hasResult, loading }: WorkflowProgressProps) {
  const [runningStage, setRunningStage] = useState(0);

  useEffect(() => {
    if (!loading) {
      setRunningStage(hasResult ? stages.length - 1 : 0);
      return;
    }

    setRunningStage(0);
    const intervalId = window.setInterval(() => {
      setRunningStage((current) => Math.min(current + 1, stages.length - 1));
    }, 1400);

    return () => window.clearInterval(intervalId);
  }, [hasResult, loading]);

  const progressPercent = hasResult
    ? 100
    : loading
      ? Math.min(96, ((runningStage + 1) / stages.length) * 100)
      : hasJobDescription
        ? 20
        : 0;

  return (
    <div className="mb-4 overflow-x-auto rounded-lg border border-slate-200 bg-white px-4 py-3 shadow-sm">
      <div className="mb-3 h-1.5 overflow-hidden rounded-full bg-slate-100">
        <div
          className="h-full rounded-full bg-slate-900 transition-all duration-700 ease-out"
          style={{ width: `${progressPercent}%` }}
        />
      </div>
      <div className="flex min-w-max items-center gap-3">
        {stages.map((stage, index) => {
          const complete = hasResult || (index === 0 && hasJobDescription) || (loading && index <= runningStage);
          const active = loading && index === Math.min(runningStage + 1, stages.length - 1);

          return (
            <div key={stage} className="flex items-center gap-3">
              <div className="flex items-center gap-2">
                <span
                  className={`flex h-5 w-5 items-center justify-center rounded-full border text-[10px] font-semibold ${
                    complete
                      ? "border-emerald-600 bg-emerald-600 text-white"
                      : active
                        ? "border-slate-900 bg-white text-slate-900"
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
