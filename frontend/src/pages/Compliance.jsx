import React, { useEffect, useMemo, useState } from "react";
import { CalendarCheck, MessageCircle, Mail } from "lucide-react";
import { PageHeader } from "@/components/PageHeader";
import { StatusBadge, complianceTone } from "@/components/StatusBadge";
import { EmptyState } from "@/components/EmptyState";
import { useClients } from "@/components/ClientContext";
import { getComplianceCalendar, markFiled } from "@/lib/api";
import { formatDate, formatRelativeDays, formatINR } from "@/lib/format";

const TYPE_LABEL = {
  GSTR1: "GSTR-1",
  GSTR3B: "GSTR-3B",
  TDS_RETURN: "26Q",
  TDS_PAYMENT: "TDS Deposit",
  ADVANCE_TAX: "Advance Tax",
  ITR: "ITR",
  ROC: "ROC Annual",
};

export default function Compliance() {
  const { clients, selected } = useClients();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState("");

  const load = () => {
    setLoading(true);
    const params = selected !== "all" ? { client_id: selected } : {};
    if (statusFilter) params.status = statusFilter;
    getComplianceCalendar(params.client_id, params.status)
      .then((d) => { setItems(d.items || []); setLoading(false); })
      .catch(() => setLoading(false));
  };
  useEffect(load, [selected, statusFilter]);

  const grouped = useMemo(() => {
    const buckets = { overdue: [], today: [], thisWeek: [], next30: [], later: [], filed: [] };
    items.forEach((it) => {
      if (it.status === "filed") { buckets.filed.push(it); return; }
      if (it.status === "missed" || it.days_to_due < 0) buckets.overdue.push(it);
      else if (it.days_to_due === 0) buckets.today.push(it);
      else if (it.days_to_due <= 7) buckets.thisWeek.push(it);
      else if (it.days_to_due <= 30) buckets.next30.push(it);
      else buckets.later.push(it);
    });
    return buckets;
  }, [items]);

  const handleMarkFiled = async (id) => {
    if (!window.confirm("Mark this item as filed?")) return;
    await markFiled(id);
    load();
  };

  if (loading) return <div className="text-sm text-slate-500" data-testid="compliance-loading">Loading calendar…</div>;

  const sections = [
    { key: "overdue", title: "Overdue", tone: "danger", items: grouped.overdue },
    { key: "today", title: "Due today", tone: "danger", items: grouped.today },
    { key: "thisWeek", title: "This week (next 7 days)", tone: "warning", items: grouped.thisWeek },
    { key: "next30", title: "Next 30 days", tone: "info", items: grouped.next30 },
    { key: "later", title: "Later", tone: "neutral", items: grouped.later },
    { key: "filed", title: "Filed", tone: "success", items: grouped.filed },
  ];

  return (
    <div data-testid="compliance-page" className="animate-fade-in">
      <PageHeader
        title="Compliance Calendar"
        subtitle="Statutory deadlines with 7-day & 1-day automated reminders"
        actions={
          <div className="flex gap-2" data-testid="compliance-status-filters">
            {[
              { v: "", label: `All (${items.length})` },
              { v: "pending", label: "Pending" },
              { v: "missed", label: "Missed" },
              { v: "filed", label: "Filed" },
            ].map((s) => (
              <button
                key={s.v}
                onClick={() => setStatusFilter(s.v)}
                data-testid={`compliance-status-${s.v || "all"}`}
                className={`px-3 py-2 text-xs font-semibold rounded-md transition border ${
                  statusFilter === s.v ? "bg-navy-600 text-white border-navy-600" : "bg-white text-slate-700 border-slate-200 hover:bg-slate-50"
                }`}
              >{s.label}</button>
            ))}
          </div>
        }
      />

      <div className="space-y-8">
        {sections.filter((s) => s.items.length > 0).map((s) => (
          <section key={s.key} data-testid={`compliance-section-${s.key}`}>
            <div className="flex items-center gap-3 mb-3">
              <h2 className="text-base font-semibold text-slate-800 font-heading">{s.title}</h2>
              <StatusBadge tone={s.tone}>{s.items.length}</StatusBadge>
            </div>
            <div className="surface overflow-hidden">
              <table className="tp-table">
                <thead>
                  <tr>
                    <th>Item</th>
                    <th>Client</th>
                    <th>Type</th>
                    <th>Due date</th>
                    <th>Status</th>
                    <th>Reminders</th>
                    <th>Penalty</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {s.items.map((it) => (
                    <tr key={it.id} data-testid={`compliance-row-${it.id}`}>
                      <td>
                        <div className="font-semibold text-slate-900">{it.description}</div>
                        <div className="text-xs text-slate-500 mt-0.5">{it.penalty_description}</div>
                      </td>
                      <td className="text-slate-700">{it.client_name}</td>
                      <td><StatusBadge tone="neutral">{TYPE_LABEL[it.type] || it.type}</StatusBadge></td>
                      <td className="font-mono text-sm tabular-nums">
                        {formatDate(it.due_date)}
                        <div className="text-xs text-slate-500">{formatRelativeDays(it.days_to_due)}</div>
                      </td>
                      <td><StatusBadge tone={complianceTone(it.status, it.days_to_due)}>{it.status}</StatusBadge></td>
                      <td>
                        <div className="flex items-center gap-1.5" data-testid={`reminders-${it.id}`}>
                          <MessageCircle className={`h-4 w-4 ${it.reminder_7day_sent || it.reminder_1day_sent ? "text-green-600" : "text-slate-300"}`} />
                          <Mail className={`h-4 w-4 ${it.reminder_7day_sent || it.reminder_1day_sent ? "text-green-600" : "text-slate-300"}`} />
                          <span className="text-xs text-slate-500 ml-1">
                            {it.reminder_1day_sent ? "1-day sent" : it.reminder_7day_sent ? "7-day sent" : "scheduled"}
                          </span>
                        </div>
                      </td>
                      <td className="text-xs text-slate-500 font-mono">
                        {it.penalty_per_day ? `₹${it.penalty_per_day}/day` : "—"}
                      </td>
                      <td>
                        {it.status !== "filed" && (
                          <button
                            onClick={() => handleMarkFiled(it.id)}
                            data-testid={`mark-filed-${it.id}`}
                            className="flex items-center gap-1 text-xs font-semibold text-navy-600 hover:text-navy-800 hover:underline"
                          >
                            <CalendarCheck className="h-3.5 w-3.5" /> Mark filed
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        ))}

        {items.length === 0 && (
          <EmptyState title="No compliance items" hint="Generate a calendar for a client to begin tracking." />
        )}
      </div>
    </div>
  );
}
