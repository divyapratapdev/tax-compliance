import React from "react";
import { formatINRCompact } from "@/lib/format";

export const KPICard = ({ label, value, hint, tone = "neutral", icon: Icon, testId, isCurrency = false }) => {
  const toneStyles = {
    danger:  "border-t-red-600",
    warning: "border-t-amber-500",
    success: "border-t-green-600",
    info:    "border-t-sky-500",
    neutral: "border-t-navy-600",
  };
  const valueColor = {
    danger:  "text-red-700",
    warning: "text-amber-700",
    success: "text-green-700",
    info:    "text-sky-700",
    neutral: "text-slate-900",
  }[tone] || "text-slate-900";

  const displayValue = isCurrency && typeof value === "number" ? formatINRCompact(value) : value;

  return (
    <div
      className={`bg-white border border-slate-200 rounded-lg p-6 shadow-sm border-t-4 ${toneStyles[tone] || toneStyles.neutral} animate-fade-in`}
      data-testid={testId}
    >
      <div className="flex items-center justify-between mb-3">
        <span className="kpi-label">{label}</span>
        {Icon && <Icon className="h-5 w-5 text-slate-400" strokeWidth={2} />}
      </div>
      <div className={`font-mono font-bold text-3xl tracking-tight tabular-nums ${valueColor}`}>
        {displayValue}
      </div>
      {hint && <p className="mt-2 text-xs text-slate-500">{hint}</p>}
    </div>
  );
};

export default KPICard;
