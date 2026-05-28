import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ShieldAlert, AlertCircle, CalendarClock, Users, ArrowRight, Receipt } from "lucide-react";
import { PageHeader } from "@/components/PageHeader";
import { KPICard } from "@/components/KPICard";
import { StatusBadge, complianceTone } from "@/components/StatusBadge";
import { EmptyState } from "@/components/EmptyState";
import { getDashboardSummary } from "@/lib/api";
import { formatINR, formatINRCompact, formatDate, formatRelativeDays } from "@/lib/format";

import { Skeleton } from "@/components/Skeleton";

export default function Dashboard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getDashboardSummary().then((d) => { setData(d); setLoading(false); }).catch(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="animate-fade-in space-y-8 pt-2" data-testid="dashboard-loading">
        <div className="space-y-2">
          <Skeleton className="h-8 w-64" />
          <Skeleton className="h-4 w-96" />
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-6">
          {[1,2,3,4].map(i => <Skeleton key={i} className="h-32 w-full rounded-xl" />)}
        </div>
        <div className="grid grid-cols-1 xl:grid-cols-12 gap-6">
          <Skeleton className="xl:col-span-7 h-96 w-full rounded-xl" />
          <Skeleton className="xl:col-span-5 h-96 w-full rounded-xl" />
        </div>
      </div>
    );
  }
  if (!data) return <EmptyState title="Could not load dashboard" hint="Check API connectivity." />;

  const k = data.kpis;
  const ch = data.client_health;

  return (
    <div data-testid="dashboard-page" className="animate-fade-in">
      <PageHeader
        title="Executive Dashboard"
        subtitle="Cross-client compliance snapshot. Last refreshed just now."
        testId="dashboard-header"
      />

      {/* KPI strip */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-6 mb-8">
        <KPICard
          label="Total Clients"
          value={k.total_clients}
          hint={`${ch.safe} safe · ${ch.at_risk} at risk · ${ch.critical} critical`}
          icon={Users}
          tone="neutral"
          testId="kpi-clients"
        />
        <KPICard
          label="ITC at Risk"
          value={k.itc_at_risk}
          isCurrency
          hint="Sum of mismatches not in GSTR-2A or amount-mismatched"
          icon={ShieldAlert}
          tone="danger"
          testId="kpi-itc-risk"
        />
        <KPICard
          label="Missed TDS"
          value={k.missed_tds}
          isCurrency
          hint={`Penalty estimate · ${formatINR(k.missed_penalty)}`}
          icon={Receipt}
          tone="warning"
          testId="kpi-missed-tds"
        />
        <KPICard
          label="Upcoming Compliance"
          value={k.upcoming_compliance}
          hint={`${k.overdue_compliance} overdue items need action`}
          icon={CalendarClock}
          tone={k.overdue_compliance > 0 ? "danger" : "info"}
          testId="kpi-compliance"
        />
      </div>

      {/* Two-column main area */}
      <div className="grid grid-cols-1 xl:grid-cols-12 gap-6">
        {/* Upcoming deadlines */}
        <section className="surface xl:col-span-7 p-6" data-testid="upcoming-deadlines-card">
          <div className="flex items-center justify-between mb-5">
            <div>
              <h2 className="text-lg font-semibold text-slate-900 font-heading">Upcoming Deadlines</h2>
              <p className="text-xs text-slate-500 mt-0.5">Next 7 days across all clients</p>
            </div>
            <Link to="/compliance" className="text-xs font-semibold text-navy-600 hover:text-navy-700 flex items-center gap-1" data-testid="dashboard-view-all-compliance">
              View calendar <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </div>

          {data.upcoming_deadlines.length === 0 ? (
            <EmptyState title="No deadlines in the next 7 days" />
          ) : (
            <table className="tp-table">
              <thead>
                <tr>
                  <th>Client</th>
                  <th>Item</th>
                  <th>Due</th>
                  <th className="text-right">Status</th>
                </tr>
              </thead>
              <tbody>
                {data.upcoming_deadlines.map((d) => (
                  <tr key={d.id} data-testid={`upcoming-row-${d.id}`}>
                    <td className="font-medium text-slate-800">{d.client_name}</td>
                    <td>
                      <div className="text-slate-800">{d.description}</div>
                      <div className="text-xs text-slate-500 font-mono">{d.type}</div>
                    </td>
                    <td className="num">{formatDate(d.due_date)}</td>
                    <td className="text-right">
                      <StatusBadge tone={complianceTone(d.status, d.days_to_due)}>
                        {formatRelativeDays(d.days_to_due)}
                      </StatusBadge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>

        {/* Top missed TDS */}
        <section className="surface-danger xl:col-span-5 p-6" data-testid="top-missed-tds-card">
          <div className="flex items-center justify-between mb-5">
            <div className="flex items-start gap-3">
              <AlertCircle className="h-5 w-5 text-red-600 mt-0.5" />
              <div>
                <h2 className="text-lg font-semibold text-slate-900 font-heading">Top Missed TDS</h2>
                <p className="text-xs text-slate-500 mt-0.5">Highest-penalty exposures</p>
              </div>
            </div>
            <Link to="/tds-alerts" className="text-xs font-semibold text-navy-600 hover:text-navy-700 flex items-center gap-1" data-testid="dashboard-view-all-tds">
              All alerts <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </div>

          {data.top_missed_tds.length === 0 ? (
            <EmptyState title="No missed TDS deductions" />
          ) : (
            <div className="space-y-3">
              {data.top_missed_tds.map((t) => (
                <div key={t.id} className="flex items-start justify-between gap-3 py-2 border-b border-slate-100 last:border-0" data-testid={`top-missed-row-${t.id}`}>
                  <div className="min-w-0">
                    <div className="text-sm font-semibold text-slate-800 truncate">{t.vendor_name}</div>
                    <div className="text-xs text-slate-500 mt-0.5">
                      <span className="font-mono">{t.tds_section}</span> · {t.client_name}
                    </div>
                  </div>
                  <div className="text-right flex-shrink-0">
                    <div className="font-mono font-semibold text-red-700 tabular-nums">{formatINR(t.tds_amount)}</div>
                    <div className="text-xs text-slate-500">+{formatINR(t.penalty_estimate || 0)} penalty</div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
