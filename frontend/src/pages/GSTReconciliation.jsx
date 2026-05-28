import React, { useEffect, useState } from "react";
import { ShieldCheck, ShieldAlert, ShieldQuestion, GitCompareArrows } from "lucide-react";
import { PageHeader } from "@/components/PageHeader";
import { StatusBadge, mismatchTone } from "@/components/StatusBadge";
import { EmptyState } from "@/components/EmptyState";
import { useClients } from "@/components/ClientContext";
import { getGSTSummary, listMismatches, resolveMismatch } from "@/lib/api";
import { formatINR, formatDate } from "@/lib/format";

const MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];

export default function GSTReconciliation() {
  const { clients, selected, setSelected } = useClients();
  const [month, setMonth] = useState(4);
  const [year, setYear] = useState(2025);
  const [summary, setSummary] = useState(null);
  const [mismatches, setMismatches] = useState([]);
  const [typeFilter, setTypeFilter] = useState("");
  const [loading, setLoading] = useState(false);

  const activeClient = selected !== "all" ? selected : clients[0]?.id;

  useEffect(() => {
    if (!activeClient) return;
    setLoading(true);
    Promise.all([
      getGSTSummary(activeClient, month, year),
      listMismatches({ client_id: activeClient, is_resolved: false }),
    ]).then(([s, m]) => {
      setSummary(s);
      setMismatches(m.mismatches || []);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, [activeClient, month, year]);

  const filtered = typeFilter ? mismatches.filter((m) => m.type === typeFilter) : mismatches;

  const handleResolve = async (id) => {
    const notes = window.prompt("Resolution notes (optional):", "Followed up with supplier");
    if (notes === null) return;
    await resolveMismatch(id, notes);
    setMismatches((prev) => prev.filter((m) => m.id !== id));
  };

  if (!activeClient) {
    return <EmptyState title="No clients available" hint="Add a client to begin reconciliation." />;
  }

  return (
    <div data-testid="gst-page" className="animate-fade-in">
      <PageHeader
        title="GST Reconciliation"
        subtitle="3-pass matching: client books ↔ GSTR-2A/2B"
        actions={
          <div className="flex items-center gap-2" data-testid="gst-period-controls">
            <select
              value={activeClient}
              onChange={(e) => setSelected(e.target.value)}
              className="px-3 py-2 border border-slate-200 rounded-md text-sm bg-white font-mono"
              data-testid="gst-client-select"
            >
              {clients.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
            <select
              value={month}
              onChange={(e) => setMonth(parseInt(e.target.value))}
              className="px-3 py-2 border border-slate-200 rounded-md text-sm bg-white"
              data-testid="gst-month-select"
            >
              {MONTHS.map((m, i) => <option key={m} value={i+1}>{m}</option>)}
            </select>
            <select
              value={year}
              onChange={(e) => setYear(parseInt(e.target.value))}
              className="px-3 py-2 border border-slate-200 rounded-md text-sm bg-white"
              data-testid="gst-year-select"
            >
              {[2023, 2024, 2025, 2026].map((y) => <option key={y} value={y}>{y}</option>)}
            </select>
          </div>
        }
      />

      {loading || !summary ? (
        <div className="text-sm text-slate-500" data-testid="gst-loading">Loading reconciliation…</div>
      ) : (
        <>
          {/* ITC summary */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8" data-testid="itc-cards">
            <div className="surface-success p-6" data-testid="itc-safe-card">
              <div className="flex items-center justify-between mb-3">
                <span className="kpi-label">ITC Safe to Claim</span>
                <ShieldCheck className="h-5 w-5 text-green-600" />
              </div>
              <div className="kpi-value text-green-700">{formatINR(summary.itc_summary.safe_to_claim.amount)}</div>
              <p className="mt-2 text-xs text-slate-500">{summary.itc_summary.safe_to_claim.invoice_count} matched invoices · fully claimable</p>
            </div>
            <div className="surface-danger p-6" data-testid="itc-risk-card">
              <div className="flex items-center justify-between mb-3">
                <span className="kpi-label">ITC at Risk</span>
                <ShieldAlert className="h-5 w-5 text-red-600" />
              </div>
              <div className="kpi-value text-red-700">{formatINR(summary.itc_summary.at_risk.amount)}</div>
              <p className="mt-2 text-xs text-slate-500">{summary.itc_summary.at_risk.invoice_count} invoices · follow up with suppliers</p>
            </div>
            <div className="surface-warning p-6" data-testid="itc-missing-card">
              <div className="flex items-center justify-between mb-3">
                <span className="kpi-label">Missing in Books</span>
                <ShieldQuestion className="h-5 w-5 text-amber-600" />
              </div>
              <div className="kpi-value text-amber-700">{formatINR(summary.itc_summary.missing_in_books.amount)}</div>
              <p className="mt-2 text-xs text-slate-500">{summary.itc_summary.missing_in_books.invoice_count} invoices · add entries to books</p>
            </div>
          </div>

          {/* Type filter tabs */}
          <div className="flex flex-wrap gap-2 mb-4" data-testid="mismatch-type-filters">
            {[
              { v: "", label: `All (${mismatches.length})` },
              { v: "missing_in_2a", label: "Missing in 2A", tone: "danger" },
              { v: "amount_mismatch", label: "Amount mismatch", tone: "warning" },
              { v: "missing_in_books", label: "Missing in books", tone: "warning" },
              { v: "gstin_mismatch", label: "GSTIN mismatch", tone: "info" },
            ].map((t) => (
              <button
                key={t.v}
                onClick={() => setTypeFilter(t.v)}
                data-testid={`mm-filter-${t.v || "all"}`}
                className={`px-3 py-2 text-xs font-semibold rounded-md transition border ${
                  typeFilter === t.v
                    ? "bg-navy-600 text-white border-navy-600"
                    : "bg-white text-slate-700 border-slate-200 hover:bg-slate-50"
                }`}
              >{t.label}</button>
            ))}
          </div>

          {/* Mismatch table */}
          <div className="surface overflow-hidden" data-testid="mismatch-table-card">
            {filtered.length === 0 ? (
              <EmptyState title="No open mismatches" hint="All invoices reconcile cleanly for this period." icon={GitCompareArrows} />
            ) : (
              <table className="tp-table">
                <thead>
                  <tr>
                    <th>Supplier</th>
                    <th>Invoice</th>
                    <th>Type</th>
                    <th className="text-right">Books</th>
                    <th className="text-right">GSTR-2A</th>
                    <th className="text-right">Difference</th>
                    <th>Suggested action</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((m) => (
                    <tr key={m.id} data-testid={`mm-row-${m.id}`}>
                      <td>
                        <div className="font-semibold text-slate-900">{m.supplier_name}</div>
                        <div className="font-mono text-xs text-slate-500">{m.supplier_gstin}</div>
                      </td>
                      <td>
                        <div className="font-mono text-sm text-slate-800">{m.invoice_number}</div>
                        <div className="text-xs text-slate-500">{formatDate(m.invoice_date)}</div>
                      </td>
                      <td><StatusBadge tone={mismatchTone(m.type)}>{m.type.replace(/_/g," ")}</StatusBadge></td>
                      <td className="num">{m.books_amount != null ? formatINR(m.books_amount) : "—"}</td>
                      <td className="num">{m.gstr2a_amount != null ? formatINR(m.gstr2a_amount) : "—"}</td>
                      <td className="num">{m.difference != null ? formatINR(Math.abs(m.difference)) : "—"}</td>
                      <td className="text-xs text-slate-600 max-w-xs">{m.suggested_action}</td>
                      <td>
                        <button
                          onClick={() => handleResolve(m.id)}
                          data-testid={`mm-resolve-${m.id}`}
                          className="text-xs font-semibold text-navy-600 hover:text-navy-800 hover:underline"
                        >Resolve</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </>
      )}
    </div>
  );
}
