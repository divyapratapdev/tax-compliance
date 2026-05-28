import React, { useEffect, useState } from "react";
import { AlertCircle, Download, Calculator, TrendingDown, Building2 } from "lucide-react";
import { PageHeader } from "@/components/PageHeader";
import { StatusBadge } from "@/components/StatusBadge";
import { EmptyState } from "@/components/EmptyState";
import { useClients } from "@/components/ClientContext";
import { getTDSSummary, getTDSMissed, getTDSVendors } from "@/lib/api";
import { formatINR, formatDate } from "@/lib/format";
import { toast } from "sonner";
import { Skeleton } from "@/components/Skeleton";

export default function TDSAlerts() {
  const { clients, selected, setSelected } = useClients();
  const [fy, setFy] = useState("2025-26");
  const [summary, setSummary] = useState(null);
  const [missed, setMissed] = useState([]);
  const [vendors, setVendors] = useState([]);
  const [loading, setLoading] = useState(false);

  const activeClient = selected !== "all" ? selected : null;
  useEffect(() => {
    setLoading(true);
    Promise.all([
      getTDSSummary(activeClient, fy),
      getTDSMissed(activeClient, fy),
      getTDSVendors(activeClient, fy),
    ]).then(([s, m, v]) => {
      setSummary(s);
      setMissed(m.entries || []);
      setVendors(v.vendors || []);
      setLoading(false);
    }).catch(() => { toast.error("Failed to load TDS data"); setLoading(false); });
  }, [selected, fy]);

  if (loading || !summary) return (
    <div className="animate-fade-in space-y-6" data-testid="tds-loading">
      <div className="space-y-2"><Skeleton className="h-8 w-48" /><Skeleton className="h-4 w-72" /></div>
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        <Skeleton className="h-48 rounded-xl" />
        <Skeleton className="xl:col-span-2 h-48 rounded-xl" />
      </div>
      <Skeleton className="h-64 w-full rounded-xl" />
    </div>
  );

  const ov = summary.overall;
  const has26q = ov.tds_deducted > 0;

  return (
    <div data-testid="tds-page" className="animate-fade-in">
      <PageHeader
        title="TDS Alerts"
        subtitle="Missed deductions, vendor cumulative tracking, and Form 26Q export"
        actions={
          <div className="flex items-center gap-2">
            <select
              value={selected}
              onChange={(e) => setSelected(e.target.value)}
              data-testid="tds-client-select"
              className="px-3 py-2 border border-slate-200 rounded-md text-sm bg-white font-mono"
            >
              <option value="all">Firm-wide</option>
              {clients.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
            <select
              value={fy}
              onChange={(e) => setFy(e.target.value)}
              className="bg-white border border-slate-200 text-sm font-medium pl-3 pr-8 py-2 rounded-md hover:bg-slate-50 focus:ring-2 focus:ring-navy-600/30"
              data-testid="tds-fy-select"
            >
              {(() => { const y = new Date().getFullYear(); return [`${y-1}-${String(y).slice(2)}`, `${y}-${String(y+1).slice(2)}`, `${y+1}-${String(y+2).slice(2)}`]; })().map((f) => (
                <option key={f} value={f}>FY {f}</option>
              ))}
            </select>
            <button
              data-testid="tds-generate-btn"
              className="flex items-center gap-2 px-4 py-2 bg-navy-600 text-white rounded-md text-sm font-semibold hover:bg-navy-700 transition"
              onClick={() => toast.info("Form 26Q XML generation coming soon")}
            >
              <Download className="h-4 w-4" /> Generate 26Q XML
            </button>
          </div>
        }
      />

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6 mb-8">
        <div className="xl:col-span-1 bg-red-50 border border-red-200 rounded-lg p-6" data-testid="tds-hero-missed">
          <div className="flex items-start gap-3 mb-4">
            <AlertCircle className="h-6 w-6 text-red-600 flex-shrink-0" />
            <div>
              <div className="kpi-label text-red-700">Total Missed TDS</div>
              <div className="kpi-value text-red-700 mt-1">{formatINR(ov.tds_missed)}</div>
              <div className="text-xs text-red-700/80 mt-2">
                across {ov.missed_count} payment{ov.missed_count === 1 ? "" : "s"}
              </div>
            </div>
          </div>
          <div className="border-t border-red-200 pt-4">
            <div className="kpi-label text-red-700">Estimated Penalty</div>
            <div className="font-mono font-bold text-2xl text-red-700 tabular-nums mt-1">{formatINR(ov.penalty_estimate)}</div>
            <div className="text-xs text-red-700/80 mt-1">@ 1% per month delayed</div>
          </div>
        </div>
        <div className="xl:col-span-2 grid grid-cols-2 gap-6">
          <div className="surface p-6" data-testid="tds-stat-computed">
            <div className="flex items-center justify-between mb-3">
              <span className="kpi-label">TDS Computed</span>
              <Calculator className="h-5 w-5 text-slate-400" />
            </div>
            <div className="kpi-value">{formatINR(ov.tds_computed)}</div>
            <p className="mt-2 text-xs text-slate-500">{ov.entries} entries in FY {fy}</p>
          </div>
          <div className="surface p-6" data-testid="tds-stat-deducted">
            <div className="flex items-center justify-between mb-3">
              <span className="kpi-label">TDS Deducted</span>
              <TrendingDown className="h-5 w-5 text-green-600" />
            </div>
            <div className="kpi-value text-green-700">{formatINR(ov.tds_deducted)}</div>
            <p className="mt-2 text-xs text-slate-500">Compliance rate · {ov.compliance_rate}%</p>
          </div>
          <div className="surface xl:col-span-2 flex flex-col">
            <div className="p-5 border-b border-slate-100 flex-shrink-0">
              <h3 className="text-sm font-bold text-slate-800 uppercase tracking-wider">Quarterly Deductions</h3>
            </div>
            <div className="p-5 flex-1 grid grid-cols-2 lg:grid-cols-4 gap-4">
              {["Q1","Q2","Q3","Q4"].map((q) => (
                <div key={q} data-testid={`tds-q-${q}`}>
                  <div className="text-xs text-slate-500">{q}</div>
                  <div className="font-mono text-lg font-semibold text-slate-800 mt-0.5">{formatINR(summary.quarterly[q]?.computed || 0)}</div>
                  <div className="text-xs text-slate-500">{summary.quarterly[q]?.entries || 0} entries</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      <div className="surface overflow-hidden mb-8" data-testid="tds-missed-card">
        <div className="px-6 py-4 border-b border-slate-200">
          <h2 className="text-lg font-heading font-semibold text-slate-900">Missed Deductions</h2>
          <p className="text-xs text-slate-500 mt-0.5">Highest penalty exposure first</p>
        </div>
        {missed.length === 0 ? (
          <EmptyState title="No missed deductions" hint="All applicable TDS has been deducted for this period." />
        ) : (
          <div className="overflow-x-auto">
            <table className="tp-table">
              <thead>
              <tr>
                <th>Vendor</th>
                <th>Section</th>
                <th>Client</th>
                <th>Payment date</th>
                <th className="text-right">Payment amt</th>
                <th className="text-right">TDS due</th>
                <th className="text-right">Penalty</th>
                <th>Q</th>
              </tr>
            </thead>
            <tbody>
              {missed.map((m) => (
                <tr key={m.id} data-testid={`tds-missed-row-${m.id}`}>
                  <td>
                    <div className="font-semibold text-slate-900">{m.vendor_name}</div>
                    <div className="font-mono text-xs text-slate-500">PAN {m.vendor_pan}</div>
                  </td>
                  <td><StatusBadge tone="info">{m.tds_section}</StatusBadge></td>
                  <td className="text-slate-700">{m.client_name}</td>
                  <td className="text-slate-500 text-sm">{formatDate(m.payment_date)}</td>
                  <td className="num">{formatINR(m.payment_amount)}</td>
                  <td className="num text-red-700 font-semibold">{formatINR(m.tds_amount)}</td>
                  <td className="num text-amber-700">{formatINR(m.penalty_estimate)}</td>
                  <td><StatusBadge tone="neutral">{m.quarter}</StatusBadge></td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
        )}
      </div>

      <div className="surface overflow-hidden" data-testid="tds-vendors-card">
        <div className="px-6 py-4 border-b border-slate-200 flex items-center gap-2">
          <Building2 className="h-4 w-4 text-navy-600" />
          <h2 className="text-lg font-heading font-semibold text-slate-900">Vendor Cumulative Tracking</h2>
        </div>
        {vendors.length === 0 ? (
          <EmptyState title="No vendor data" />
        ) : (
          <div className="overflow-x-auto">
            <table className="tp-table">
              <thead>
              <tr>
                <th>Vendor</th>
                <th>Section</th>
                <th className="text-right">Payments</th>
                <th className="text-right">TDS computed</th>
                <th className="text-right">TDS deducted</th>
                <th>Compliance</th>
                <th className="text-right">Payments cnt</th>
              </tr>
            </thead>
            <tbody>
              {vendors.map((v, i) => (
                <tr key={`${v.vendor_pan}-${v.tds_section}-${i}`} data-testid={`tds-vendor-row-${i}`}>
                  <td>
                    <div className="font-semibold text-slate-900">{v.vendor_name}</div>
                    <div className="font-mono text-xs text-slate-500">{v.vendor_pan}</div>
                  </td>
                  <td><StatusBadge tone="info">{v.tds_section}</StatusBadge></td>
                  <td className="num">{formatINR(v.total_payments)}</td>
                  <td className="num">{formatINR(v.total_tds_computed)}</td>
                  <td className="num">{formatINR(v.total_tds_deducted)}</td>
                  <td>
                    <StatusBadge tone={v.compliance_pct >= 100 ? "success" : v.compliance_pct >= 80 ? "warning" : "danger"}>
                      {v.compliance_pct}%
                    </StatusBadge>
                  </td>
                  <td className="num">{v.payment_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
        )}
      </div>
    </div>
  );
}
