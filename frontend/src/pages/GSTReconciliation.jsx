import React, { useEffect, useState } from "react";
import { ShieldCheck, ShieldAlert, ShieldQuestion, CheckCircle2, AlertCircle, FileText, ArrowRight, Loader2, Upload } from "lucide-react";
import { PageHeader } from "@/components/PageHeader";
import { StatusBadge, mismatchTone } from "@/components/StatusBadge";
import { EmptyState } from "@/components/EmptyState";
import { useClients } from "@/components/ClientContext";
import { getGSTSummary, listMismatches, resolveMismatch, importPurchaseRegister, importGSTR2B } from "@/lib/api";
import { formatINR, formatDate } from "@/lib/format";
import { toast } from "sonner";
import { KPICard } from "@/components/KPICard";
import { Skeleton } from "@/components/Skeleton";

const MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];

export default function GSTReconciliation() {
  const { clients, selected, setSelected } = useClients();
  const [month, setMonth] = useState(new Date().getMonth() + 1);
  const [year, setYear] = useState(new Date().getFullYear());
  const [loading, setLoading] = useState(true);
  const [summary, setSummary] = useState(null);
  const [mismatches, setMismatches] = useState([]);
  const [typeFilter, setTypeFilter] = useState("");
  const [resolvingId, setResolvingId] = useState(null);

  const activeClient = selected !== "all" ? selected : clients[0]?.id;

  useEffect(() => {
    if (!activeClient) return;
    loadData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeClient, month, year]);

  const loadData = () => {
    setLoading(true);
    Promise.all([
      getGSTSummary(activeClient, month, year),
      listMismatches({ client_id: activeClient, month, year, is_resolved: false }),
    ]).then(([s, m]) => {
      setSummary(s);
      setMismatches(m.mismatches || []);
      setLoading(false);
    }).catch(() => {
      toast.error("Failed to load reconciliation data");
      setLoading(false);
    });
  };

  const handleUploadPR = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const toastId = toast.loading("Uploading Purchase Register...");
    try {
      await importPurchaseRegister(activeClient, month, year, file);
      toast.success("Purchase Register imported successfully!", { id: toastId });
      loadData();
    } catch (err) {
      const details = err.response?.data?.detail;
      if (details?.errors && details.errors.length > 0) {
        toast.error(`Import failed: ${details.errors[0]}`, { id: toastId });
      } else {
        toast.error(err.response?.data?.detail || "Failed to import Purchase Register", { id: toastId });
      }
    } finally {
      e.target.value = "";
    }
  };

  const handleUpload2B = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const toastId = toast.loading("Uploading GSTR-2B...");
    try {
      await importGSTR2B(activeClient, month, year, file);
      toast.success("GSTR-2B imported successfully!", { id: toastId });
      loadData();
    } catch (err) {
      const details = err.response?.data?.detail;
      if (details?.errors && details.errors.length > 0) {
        toast.error(`Import failed: ${details.errors[0]}`, { id: toastId });
      } else {
        toast.error(err.response?.data?.detail || "Failed to import GSTR-2B", { id: toastId });
      }
    } finally {
      e.target.value = "";
    }
  };

  const filtered = typeFilter ? mismatches.filter((m) => m.type === typeFilter) : mismatches;

  const handleResolve = async (id) => {
    setResolvingId(id);
    try {
      await resolveMismatch(id, "Resolved by CA");
      toast.success("Mismatch resolved");
      setMismatches((prev) => prev.filter((m) => m.id !== id));
    } catch (e) {
      toast.error("Failed to resolve mismatch");
    } finally {
      setResolvingId(null);
    }
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
          <div className="flex flex-col gap-3 items-end" data-testid="gst-period-controls">
            <div className="flex items-center gap-2">
              <label className="cursor-pointer flex items-center gap-2 px-3 py-2 bg-slate-100 text-slate-700 rounded-md text-sm hover:bg-slate-200 transition font-medium border border-slate-200">
                <Upload className="h-4 w-4" />
                Upload Purchase Register
                <input type="file" className="hidden" accept=".csv" onChange={handleUploadPR} />
              </label>
              <label className="cursor-pointer flex items-center gap-2 px-3 py-2 bg-navy-600 text-white rounded-md text-sm hover:bg-navy-700 transition font-medium">
                <Upload className="h-4 w-4" />
                Upload GSTR-2B
                <input type="file" className="hidden" accept=".csv,.json" onChange={handleUpload2B} />
              </label>
            </div>
            <div className="flex items-center gap-2">
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
                className="bg-white border border-slate-200 text-sm font-medium pl-3 pr-8 py-2 rounded-md hover:bg-slate-50 focus:ring-2 focus:ring-navy-600/30"
                data-testid="gst-year-select"
              >
                {Array.from({length: 5}, (_, i) => new Date().getFullYear() - 2 + i).map((y) => (
                  <option key={y} value={y}>FY {y}-{String(y + 1).slice(2)}</option>
                ))}
              </select>
            </div>
          </div>
        }
      />

      {loading || !summary ? (
        <div className="space-y-6" data-testid="gst-loading">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {[1,2,3].map(i => <Skeleton key={i} className="h-32 w-full rounded-xl" />)}
          </div>
          <Skeleton className="h-64 w-full rounded-xl" />
        </div>
      ) : (
        <>
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

          <div className="surface overflow-hidden" data-testid="mismatch-table-card">
            {filtered.length === 0 ? (
              <EmptyState
                icon={CheckCircle2}
                title="All Good"
                hint={typeFilter ? "No mismatches match this filter. Try selecting 'All'." : "All invoices reconcile cleanly for this period."}
              />
            ) : (
              <div className="overflow-x-auto">
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
                        <td className="text-right">
                          <button
                            onClick={() => handleResolve(m.id)}
                            disabled={resolvingId === m.id}
                            data-testid={`mm-resolve-${m.id}`}
                            className="flex items-center gap-1 text-xs font-semibold text-navy-600 hover:text-navy-800 hover:underline disabled:opacity-50"
                          >{resolvingId === m.id ? <><Loader2 className="h-3 w-3 animate-spin" /> Resolving…</> : "Resolve"}</button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
