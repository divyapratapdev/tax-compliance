import React from "react";

export const PageHeader = ({ title, subtitle, actions, testId }) => (
  <div className="flex items-start justify-between mb-8 gap-6" data-testid={testId}>
    <div>
      <h1 className="text-3xl font-heading font-semibold tracking-tight text-slate-900">{title}</h1>
      {subtitle && <p className="mt-1 text-sm text-slate-500">{subtitle}</p>}
    </div>
    {actions && <div className="flex items-center gap-3 flex-shrink-0">{actions}</div>}
  </div>
);

export default PageHeader;
