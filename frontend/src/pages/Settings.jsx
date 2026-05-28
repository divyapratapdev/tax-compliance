import React, { useState, useEffect } from "react";
import { Save, ShieldCheck } from "lucide-react";
import { PageHeader } from "@/components/PageHeader";
import { StatusBadge } from "@/components/StatusBadge";
import { updateProfile, updateAlertPrefs } from "@/lib/api";
import { useAuth } from "@/components/AuthContext";
import { toast } from "sonner";
import { Skeleton } from "@/components/Skeleton";

export default function Settings() {
  const { user: firm, setUser: onUpdate } = useAuth();
  const [form, setForm] = useState(firm || {});
  const [initialForm, setInitialForm] = useState(firm || {});
  const [prefs, setPrefs] = useState(firm?.alert_preferences || {});
  const [initialPrefs, setInitialPrefs] = useState(firm?.alert_preferences || {});
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (firm) { 
      setForm(firm); setInitialForm(firm); 
      setPrefs(firm.alert_preferences || {}); setInitialPrefs(firm.alert_preferences || {}); 
    }
  }, [firm]);

  const isDirty = JSON.stringify(form) !== JSON.stringify(initialForm) || JSON.stringify(prefs) !== JSON.stringify(initialPrefs);

  const save = async () => {
    setSaving(true);
    try {
      const updated = await updateProfile({
        name: form.name,
        registration_number: form.registration_number,
        email: form.email,
        plan: form.plan,
      });
      const withPrefs = await updateAlertPrefs(prefs);
      onUpdate && onUpdate(withPrefs);
      toast.success("Settings saved successfully");
    } catch (e) {
      toast.error("Failed to save settings");
    } finally {
      setSaving(false);
    }
  };

  if (!firm) return (
    <div className="animate-fade-in max-w-4xl space-y-6">
      <div className="space-y-2"><Skeleton className="h-8 w-48" /><Skeleton className="h-4 w-72" /></div>
      <Skeleton className="h-64 w-full rounded-xl" />
      <Skeleton className="h-48 w-full rounded-xl" />
    </div>
  );

  return (
    <div data-testid="settings-page" className="animate-fade-in max-w-4xl">
      <PageHeader title="Settings" subtitle="Firm profile and alert preferences" />

      <div className="space-y-6">
        {/* Firm */}
        <section className="surface p-6" data-testid="settings-firm-card">
          <h2 className="text-lg font-heading font-semibold text-slate-900 mb-1">Firm Profile</h2>
          <p className="text-xs text-slate-500 mb-6">Appears in generated PDFs and on client-facing exports.</p>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Field label="Firm name" testId="settings-firm-name">
              <input
                value={form.name || ""}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                data-testid="settings-input-name"
                className={inputCls}
              />
            </Field>
            <Field label="ICAI Registration Number" testId="settings-firm-registration">
              <input
                value={form.registration_number || ""}
                onChange={(e) => setForm({ ...form, registration_number: e.target.value })}
                data-testid="settings-input-registration"
                className={`${inputCls} font-mono`}
              />
            </Field>
            <Field label="Contact email" testId="settings-firm-email">
              <input
                type="email"
                value={form.email || ""}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
                data-testid="settings-input-email"
                className={inputCls}
              />
            </Field>
            <Field label="Subscription plan">
              <select
                value={form.plan || "starter"}
                onChange={(e) => setForm({ ...form, plan: e.target.value })}
                data-testid="settings-input-plan"
                className={inputCls}
              >
                <option value="starter">Starter — ₹2,999/mo</option>
                <option value="growth">Growth — ₹9,999/mo</option>
                <option value="scale">Scale — ₹24,999/mo</option>
              </select>
            </Field>
          </div>
        </section>

        {/* Alerts */}
        <section className="surface p-6" data-testid="settings-alerts-card">
          <h2 className="text-lg font-heading font-semibold text-slate-900 mb-1">Alert Preferences</h2>
          <p className="text-xs text-slate-500 mb-6">Compliance reminders via WhatsApp Business API and email.</p>

          <div className="space-y-3">
            {[
              { k: "whatsapp_enabled", label: "WhatsApp alerts enabled" },
              { k: "email_enabled", label: "Email alerts enabled" },
              { k: "reminder_7day", label: "Send 7-day reminder before due date" },
              { k: "reminder_1day", label: "Send 1-day reminder before due date" },
              { k: "escalation_on_missed", label: "Send escalation when item is missed" },
            ].map((p) => (
              <label key={p.k} className="flex items-center justify-between py-2 border-b border-slate-100 last:border-0" data-testid={`pref-${p.k}`}>
                <span className="text-sm text-slate-700">{p.label}</span>
                <button
                  type="button"
                  role="switch"
                  aria-checked={!!prefs[p.k]}
                  onClick={() => setPrefs({ ...prefs, [p.k]: !prefs[p.k] })}
                  data-testid={`toggle-${p.k}`}
                  className={`relative inline-flex h-6 w-11 items-center rounded-full transition ${prefs[p.k] ? "bg-navy-600" : "bg-slate-300"}`}
                >
                  <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition ${prefs[p.k] ? "translate-x-6" : "translate-x-1"}`} />
                </button>
              </label>
            ))}
          </div>
        </section>

        {/* Security card (info-only) */}
        <section className="surface p-6 border-l-4 border-l-green-500" data-testid="settings-security-card">
          <div className="flex items-start gap-3">
            <ShieldCheck className="h-6 w-6 text-green-600 flex-shrink-0" />
            <div>
              <h3 className="font-heading font-semibold text-slate-900">Security & Compliance</h3>
              <p className="text-sm text-slate-600 mt-1">
                All data is encrypted at rest. DPDP Act 2023 compliant data handling. Audit log of every CA action.
              </p>
              <div className="flex gap-2 mt-3">
                <StatusBadge tone="success">DPDP-ready</StatusBadge>
                <StatusBadge tone="success">AES-256 at rest</StatusBadge>
                <StatusBadge tone="info">SOC2 in progress</StatusBadge>
              </div>
            </div>
          </div>
        </section>

        <div className="flex items-center justify-end gap-3">
          <button
            onClick={save}
            disabled={saving || !isDirty}
            data-testid="settings-save-btn"
            className="flex items-center gap-2 px-5 py-2 bg-navy-600 text-white rounded-md text-sm font-semibold hover:bg-navy-700 transition disabled:opacity-60"
          >
            <Save className="h-4 w-4" /> {saving ? "Saving…" : "Save changes"}
          </button>
        </div>
      </div>
    </div>
  );
}

const inputCls = "w-full px-3 py-2 border border-slate-200 rounded-md text-sm bg-white focus:outline-none focus:ring-2 focus:ring-navy-600/30 focus:border-navy-600 transition";

const Field = ({ label, children, testId }) => (
  <div data-testid={testId}>
    <label className="label-section block mb-1.5">{label}</label>
    {children}
  </div>
);
