import React, { useEffect, useMemo, useState } from "react";
import { Search, Plus, Edit2, Trash2, X, Loader2 } from "lucide-react";
import { PageHeader } from "@/components/PageHeader";
import { StatusBadge, healthTone } from "@/components/StatusBadge";
import { EmptyState } from "@/components/EmptyState";
import { Skeleton } from "@/components/Skeleton";
import { useClients } from "@/components/ClientContext";
import { listClients, createClient, updateClient, deleteClient } from "@/lib/api";
import { formatINR, formatDate } from "@/lib/format";
import { toast } from "sonner";
import * as Dialog from "@radix-ui/react-dialog";
import * as AlertDialog from "@radix-ui/react-alert-dialog";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";

const clientSchema = z.object({
  name: z.string().min(2, "Company name is required"),
  gstin: z.string().regex(/^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$/i, "Invalid GSTIN format"),
  pan: z.string().regex(/^[A-Z]{5}[0-9]{4}[A-Z]{1}$/i, "Invalid PAN format"),
  entity_type: z.string(),
});

export default function Clients() {
  const { refresh: refreshGlobalClients } = useClients();
  const [clients, setClients] = useState([]);
  const [totalClients, setTotalClients] = useState(0);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [healthFilter, setHealthFilter] = useState("");
  
  // Pagination
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 10;

  const [modalOpen, setModalOpen] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [deleteId, setDeleteId] = useState(null);

  const {
    register,
    handleSubmit,
    reset,
    setValue,
    setError,
    formState: { errors, isSubmitting },
  } = useForm({
    resolver: zodResolver(clientSchema),
    defaultValues: { entity_type: "Private Limited" },
  });

  const fetchClients = () => {
    setLoading(true);
    listClients({ search, health: healthFilter || undefined, skip: (currentPage - 1) * itemsPerPage, limit: itemsPerPage })
      .then((d) => {
        setClients(d.clients || []);
        setTotalClients(d.total || d.total_count || d.clients?.length || 0);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  };

  useEffect(() => {
    setCurrentPage(1);
  }, [search, healthFilter]);

  /* eslint-disable react-hooks/exhaustive-deps */
  useEffect(() => {
    fetchClients();
  }, [search, healthFilter, currentPage]);
  /* eslint-enable react-hooks/exhaustive-deps */

  const summary = useMemo(
    () => ({
      safe: clients.filter((c) => c.health === "safe").length,
      at_risk: clients.filter((c) => c.health === "at_risk").length,
      critical: clients.filter((c) => c.health === "critical").length,
    }),
    [clients]
  );

  const totalPages = Math.max(1, Math.ceil(totalClients / itemsPerPage));

  const handleOpenModal = (client = null) => {
    if (client) {
      setEditingId(client.id);
      setValue("name", client.name);
      setValue("gstin", client.gstin);
      setValue("pan", client.pan);
      setValue("entity_type", client.entity_type || "Private Limited");
    } else {
      setEditingId(null);
      reset({ name: "", gstin: "", pan: "", entity_type: "Private Limited" });
    }
    setModalOpen(true);
  };

  const onSubmit = async (data) => {
    try {
      if (editingId) {
        await updateClient(editingId, data);
        toast.success("Client updated successfully");
      } else {
        await createClient(data);
        toast.success("Client created successfully");
      }
      setModalOpen(false);
      fetchClients();
      refreshGlobalClients(); // Sync globally instantly
    } catch (err) {
      if (err.response?.status === 422 && err.response?.data?.detail) {
        const details = err.response.data.detail;
        if (Array.isArray(details)) {
          details.forEach((d) => {
            if (d.loc && d.loc.length > 1) {
              setError(d.loc[d.loc.length - 1], { type: "server", message: d.msg });
            }
          });
          return;
        }
      }
      toast.error(err.response?.data?.detail || "Action failed");
    }
  };

  const handleDelete = async () => {
    if (!deleteId) return;
    try {
      await deleteClient(deleteId);
      toast.success("Client deleted successfully");
      setDeleteId(null);
      fetchClients();
      refreshGlobalClients(); // Sync globally instantly
    } catch (err) {
      toast.error("Failed to delete client");
    }
  };

  return (
    <div data-testid="clients-page" className="animate-fade-in relative">
      <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4 mb-6">
        <PageHeader
          title="Clients"
          subtitle={`${clients.length} client${clients.length === 1 ? "" : "s"} under your firm`}
        />
        <button
          onClick={() => handleOpenModal()}
          className="flex items-center gap-2 bg-navy-600 text-white px-4 py-2 rounded-md shadow-sm hover:bg-navy-700 hover:shadow transition font-medium text-sm whitespace-nowrap"
        >
          <Plus className="h-4 w-4" /> Add Client
        </button>
      </div>

      <div className="flex flex-col md:flex-row md:items-center gap-3 mb-6">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by name, GSTIN, or PAN…"
            className="w-full pl-9 pr-3 py-2 border border-slate-200 rounded-md text-sm bg-white focus:outline-none focus:ring-2 focus:ring-navy-600/30 focus:border-navy-600 transition"
          />
        </div>
        <div className="flex gap-2 flex-wrap">
          {[
            { v: "", label: `All (${clients.length})` },
            { v: "safe", label: `Safe (${summary.safe})`, tone: "safe" },
            { v: "at_risk", label: `At risk (${summary.at_risk})`, tone: "warning" },
            { v: "critical", label: `Critical (${summary.critical})`, tone: "danger" },
          ].map((f) => (
            <button
              key={f.v}
              onClick={() => setHealthFilter(f.v)}
              className={`px-3 py-2 text-xs font-semibold rounded-md transition border ${
                healthFilter === f.v
                  ? "bg-navy-600 text-white border-navy-600"
                  : "bg-white text-slate-700 border-slate-200 hover:bg-slate-50"
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      <div className="surface overflow-x-auto">
        {loading ? (
          <div className="p-6 space-y-4">
            <div className="flex gap-4 border-b border-slate-100 pb-4">
              <Skeleton className="h-6 w-1/4" />
              <Skeleton className="h-6 w-1/4" />
              <Skeleton className="h-6 w-1/4" />
              <Skeleton className="h-6 w-1/4" />
            </div>
            {[1, 2, 3, 4, 5].map((i) => (
              <div key={i} className="flex gap-4">
                <Skeleton className="h-10 w-1/4" />
                <Skeleton className="h-10 w-1/4" />
                <Skeleton className="h-10 w-1/4" />
                <Skeleton className="h-10 w-1/4" />
              </div>
            ))}
          </div>
        ) : clients.length === 0 ? (
          <EmptyState title="No clients match" hint="Try clearing filters or add a new client." />
        ) : (
          <table className="tp-table w-full text-left">
            <thead>
              <tr>
                <th>Client</th>
                <th>GSTIN / PAN</th>
                <th>Type</th>
                <th>Health</th>
                <th className="text-right">Open mismatches</th>
                <th className="text-right">Missed TDS</th>
                <th className="text-right">Upcoming</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {clients.map((c) => (
                <tr key={c.id}>
                  <td>
                    <div className="font-semibold text-slate-900">{c.name}</div>
                    <div className="text-xs text-slate-500 mt-0.5">{c.industry || "—"}</div>
                  </td>
                  <td>
                    <div className="font-mono text-xs text-slate-800">{c.gstin}</div>
                    <div className="font-mono text-xs text-slate-500 mt-0.5">{c.pan}</div>
                  </td>
                  <td>
                    <span className="text-slate-700 text-sm capitalize">
                      {c.entity_type || c.registration_type || "—"}
                    </span>
                  </td>
                  <td>
                    <StatusBadge tone={healthTone(c.health)}>
                      {(c.health || "safe").replace("_", " ")}
                    </StatusBadge>
                  </td>
                  <td className="num">{c.open_mismatches || 0}</td>
                  <td className="num">{c.missed_tds > 0 ? formatINR(c.missed_tds) : "—"}</td>
                  <td className="num">{c.upcoming_compliance || 0}</td>
                  <td>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => handleOpenModal(c)}
                        className="p-1.5 text-slate-400 hover:text-blue-600 hover:bg-blue-50 rounded transition"
                        title="Edit Client"
                      >
                        <Edit2 className="h-4 w-4" />
                      </button>
                      <button
                        onClick={() => setDeleteId(c.id)}
                        className="p-1.5 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded transition"
                        title="Delete Client"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Pagination Controls */}
      {!loading && totalPages > 1 && (
        <div className="flex items-center justify-between mt-4">
          <div className="text-sm text-slate-500">
            Showing {(currentPage - 1) * itemsPerPage + 1} to {Math.min(currentPage * itemsPerPage, totalClients)} of {totalClients} clients
          </div>
          <div className="flex items-center gap-1">
            <button
              disabled={currentPage === 1}
              onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
              className="px-3 py-1 text-sm border border-slate-200 rounded-md bg-white text-slate-600 hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Previous
            </button>
            <span className="px-3 text-sm font-medium text-slate-700">
              Page {currentPage} of {totalPages}
            </span>
            <button
              disabled={currentPage === totalPages}
              onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
              className="px-3 py-1 text-sm border border-slate-200 rounded-md bg-white text-slate-600 hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Next
            </button>
          </div>
        </div>
      )}

      {/* Edit/Create Client Dialog */}
      <Dialog.Root open={modalOpen} onOpenChange={setModalOpen}>
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-sm data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0" />
          <Dialog.Content className="fixed left-[50%] top-[50%] z-50 w-full max-w-md translate-x-[-50%] translate-y-[-50%] bg-white rounded-xl shadow-2xl flex flex-col data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95 data-[state=closed]:slide-out-to-left-1/2 data-[state=closed]:slide-out-to-top-[48%] data-[state=open]:slide-in-from-left-1/2 data-[state=open]:slide-in-from-top-[48%]">
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100">
              <Dialog.Title className="font-heading font-semibold text-lg text-slate-900">
                {editingId ? "Edit Client" : "Add New Client"}
              </Dialog.Title>
              <Dialog.Close asChild>
                <button className="text-slate-400 hover:text-slate-600 outline-none focus:ring-2 focus:ring-navy-600 rounded-sm">
                  <X className="h-5 w-5" />
                </button>
              </Dialog.Close>
            </div>

            <form onSubmit={handleSubmit(onSubmit)} className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1.5">
                  Company / Individual Name *
                </label>
                <input
                  {...register("name")}
                  type="text"
                  className={`w-full px-3 py-2 border rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-navy-600/30 transition ${
                    errors.name ? "border-red-300 focus:border-red-500" : "border-slate-200 focus:border-navy-600"
                  }`}
                />
                {errors.name && <p className="mt-1 text-xs text-red-600">{errors.name.message}</p>}
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1.5">GSTIN *</label>
                <input
                  {...register("gstin")}
                  type="text"
                  className={`w-full px-3 py-2 border rounded-md text-sm uppercase focus:outline-none focus:ring-2 focus:ring-navy-600/30 transition ${
                    errors.gstin ? "border-red-300 focus:border-red-500" : "border-slate-200 focus:border-navy-600"
                  }`}
                />
                {errors.gstin && <p className="mt-1 text-xs text-red-600">{errors.gstin.message}</p>}
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1.5">PAN *</label>
                <input
                  {...register("pan")}
                  type="text"
                  className={`w-full px-3 py-2 border rounded-md text-sm uppercase focus:outline-none focus:ring-2 focus:ring-navy-600/30 transition ${
                    errors.pan ? "border-red-300 focus:border-red-500" : "border-slate-200 focus:border-navy-600"
                  }`}
                />
                {errors.pan && <p className="mt-1 text-xs text-red-600">{errors.pan.message}</p>}
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1.5">Entity Type</label>
                <select
                  {...register("entity_type")}
                  className="w-full px-3 py-2 border border-slate-200 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-navy-600/30 focus:border-navy-600 bg-white"
                >
                  <option value="Private Limited">Private Limited</option>
                  <option value="Proprietorship">Proprietorship</option>
                  <option value="Partnership">Partnership</option>
                  <option value="LLP">LLP</option>
                  <option value="HUF">HUF</option>
                  <option value="Trust">Trust</option>
                </select>
              </div>

              <div className="pt-4 flex justify-end gap-3">
                <Dialog.Close asChild>
                  <button
                    type="button"
                    className="px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50 rounded-md transition"
                  >
                    Cancel
                  </button>
                </Dialog.Close>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-navy-600 hover:bg-navy-700 rounded-md transition disabled:opacity-70"
                >
                  {isSubmitting && <Loader2 className="h-4 w-4 animate-spin" />}
                  {isSubmitting ? "Saving..." : "Save Client"}
                </button>
              </div>
            </form>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>

      {/* Delete Client Alert Dialog */}
      <AlertDialog.Root open={!!deleteId} onOpenChange={(open) => !open && setDeleteId(null)}>
        <AlertDialog.Portal>
          <AlertDialog.Overlay className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-sm data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0" />
          <AlertDialog.Content className="fixed left-[50%] top-[50%] z-50 w-full max-w-md translate-x-[-50%] translate-y-[-50%] bg-white rounded-xl shadow-2xl p-6 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95 data-[state=closed]:slide-out-to-left-1/2 data-[state=closed]:slide-out-to-top-[48%] data-[state=open]:slide-in-from-left-1/2 data-[state=open]:slide-in-from-top-[48%]">
            <AlertDialog.Title className="text-lg font-semibold text-slate-900 font-heading">
              Delete Client
            </AlertDialog.Title>
            <AlertDialog.Description className="mt-2 text-sm text-slate-500">
              Are you sure you want to delete this client? All associated GST mismatches, TDS alerts, and compliance data will be permanently removed. This action cannot be undone.
            </AlertDialog.Description>
            <div className="mt-6 flex justify-end gap-3">
              <AlertDialog.Cancel asChild>
                <button className="px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50 rounded-md transition">
                  Cancel
                </button>
              </AlertDialog.Cancel>
              <AlertDialog.Action asChild>
                <button
                  onClick={handleDelete}
                  className="px-4 py-2 text-sm font-medium text-white bg-red-600 hover:bg-red-700 rounded-md transition"
                >
                  Yes, delete client
                </button>
              </AlertDialog.Action>
            </div>
          </AlertDialog.Content>
        </AlertDialog.Portal>
      </AlertDialog.Root>
    </div>
  );
}
