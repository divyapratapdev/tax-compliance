import React from "react";
import { Inbox } from "lucide-react";

export const EmptyState = ({ icon: Icon = Inbox, title, hint, testId }) => (
  <div className="flex flex-col items-center justify-center py-12 px-6 text-center" data-testid={testId}>
    <div className="h-14 w-14 rounded-full bg-slate-100 flex items-center justify-center mb-4">
      <Icon className="h-7 w-7 text-slate-400" />
    </div>
    <div className="text-base font-semibold text-slate-700">{title}</div>
    {hint && <div className="mt-1 text-sm text-slate-500 max-w-md">{hint}</div>}
  </div>
);

export default EmptyState;
