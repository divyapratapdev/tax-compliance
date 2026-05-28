import React from "react";

export const StatusBadge = ({ tone = "neutral", children, testId }) => {
  const toneClasses = {
    safe:     "bg-green-100 text-green-800 border border-green-200",
    success:  "bg-green-100 text-green-800 border border-green-200",
    risk:     "bg-red-100 text-red-800 border border-red-200",
    danger:   "bg-red-100 text-red-800 border border-red-200",
    critical: "bg-red-100 text-red-800 border border-red-200",
    warning:  "bg-amber-100 text-amber-900 border border-amber-200",
    pending:  "bg-amber-100 text-amber-900 border border-amber-200",
    at_risk:  "bg-amber-100 text-amber-900 border border-amber-200",
    info:     "bg-sky-100 text-sky-800 border border-sky-200",
    neutral:  "bg-slate-100 text-slate-700 border border-slate-200",
    matched:  "bg-green-100 text-green-800 border border-green-200",
    resolved: "bg-slate-100 text-slate-700 border border-slate-200",
  };
  const cls = toneClasses[tone] || toneClasses.neutral;
  return (
    <span
      data-testid={testId}
      className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold tracking-wide uppercase ${cls}`}
    >
      {children}
    </span>
  );
};

export const mismatchTone = (type) => {
  switch (type) {
    case "matched": return "matched";
    case "missing_in_2a": return "danger";
    case "missing_in_books": return "warning";
    case "amount_mismatch": return "warning";
    case "gstin_mismatch": return "info";
    default: return "neutral";
  }
};

export const complianceTone = (status, daysToDue) => {
  if (status === "filed") return "success";
  if (status === "missed") return "danger";
  if (typeof daysToDue === "number" && daysToDue <= 1) return "danger";
  if (typeof daysToDue === "number" && daysToDue <= 7) return "warning";
  return "neutral";
};

export const healthTone = (h) => {
  if (h === "safe") return "safe";
  if (h === "at_risk") return "warning";
  if (h === "critical") return "danger";
  return "neutral";
};

export default StatusBadge;
