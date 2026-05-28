import React, { useCallback, useEffect, useRef, useState } from "react";
import { Upload, FileText, Loader2, CheckCircle2, XCircle, AlertCircle } from "lucide-react";
import { PageHeader } from "@/components/PageHeader";
import { StatusBadge } from "@/components/StatusBadge";
import { EmptyState } from "@/components/EmptyState";
import { Skeleton } from "@/components/Skeleton";
import { useClients } from "@/components/ClientContext";
import { listDocuments, uploadDocument } from "@/lib/api";
import { formatDate } from "@/lib/format";
import { toast } from "sonner";

const STATUS_TONE = { completed: "success", processing: "pending", failed: "danger" };
const STATUS_ICON = { completed: CheckCircle2, processing: Loader2, failed: XCircle };

export default function Documents() {
  const { clients, selected } = useClients();
  const [docs, setDocs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [uploadClient, setUploadClient] = useState("");
  const [docType, setDocType] = useState("bank_statement");
  const fileRef = useRef(null);
  
  // Pagination
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 8;

  const load = useCallback(() => {
    setLoading(true);
    const params = selected !== "all" ? { client_id: selected } : {};
    listDocuments(params).then((d) => { 
      setDocs(d.documents || []); 
      setLoading(false); 
      setCurrentPage(1);
    }).catch(() => setLoading(false));
  }, [selected]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    if (!uploadClient && clients.length) setUploadClient(clients[0].id);
  }, [clients, uploadClient]);

  const handleFiles = async (files) => {
    if (!files || files.length === 0) return;
    if (!uploadClient) {
      toast.error("Please select a client before uploading");
      return;
    }
    setUploading(true);
    let successCount = 0;
    let failCount = 0;
    for (const file of Array.from(files)) {
      if (file.size > 10 * 1024 * 1024) {
        toast.error(`${file.name} exceeds 10MB limit`);
        failCount++;
        continue;
      }
      try {
        await uploadDocument(uploadClient, docType, file);
        successCount++;
      } catch (e) {
        toast.error(`Failed to upload ${file.name}`);
        failCount++;
      }
    }
    if (successCount > 0) toast.success(`Successfully uploaded ${successCount} document${successCount > 1 ? "s" : ""}`);
    setUploading(false);
    if (fileRef.current) fileRef.current.value = "";
    load();
  };

  const onDrop = (e) => {
    e.preventDefault();
    setDrag(false);
    handleFiles(e.dataTransfer.files);
  };

  const totalPages = Math.ceil(docs.length / itemsPerPage);
  const paginatedDocs = docs.slice((currentPage - 1) * itemsPerPage, currentPage * itemsPerPage);

  return (
    <div data-testid="documents-page" className="animate-fade-in">
      <PageHeader title="Documents" subtitle="Bank statements, GST invoices, and GSTR-2A uploads" />

      <div className="grid grid-cols-1 xl:grid-cols-12 gap-6">
        {/* Upload */}
        <section className="surface xl:col-span-4 p-6" data-testid="upload-card">
          <h2 className="text-lg font-semibold text-slate-900 font-heading mb-4">Upload</h2>

          <label className="label-section block mb-1">Client</label>
          <select
            data-testid="upload-client-select"
            value={uploadClient}
            onChange={(e) => setUploadClient(e.target.value)}
            className="w-full mb-4 px-3 py-2 border border-slate-200 rounded-md text-sm bg-white focus:outline-none focus:ring-2 focus:ring-navy-600/30 focus:border-navy-600"
          >
            {clients.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>

          <label className="label-section block mb-1">Type</label>
          <div className="grid grid-cols-3 gap-2 mb-5" data-testid="upload-type-tabs">
            {[
              { v: "bank_statement", label: "Bank stmt" },
              { v: "invoice", label: "Invoice" },
              { v: "gstr2a", label: "GSTR-2A" },
            ].map((t) => (
              <button
                key={t.v}
                onClick={() => setDocType(t.v)}
                data-testid={`upload-type-${t.v}`}
                className={`px-3 py-2 text-xs font-semibold rounded-md border transition ${
                  docType === t.v
                    ? "bg-navy-600 text-white border-navy-600"
                    : "bg-white text-slate-700 border-slate-200 hover:bg-slate-50"
                }`}
              >{t.label}</button>
            ))}
          </div>

          <div
            onDrop={onDrop}
            onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
            onDragLeave={() => setDrag(false)}
            className={`border-2 border-dashed rounded-lg p-8 text-center transition cursor-pointer ${drag ? "border-navy-600 bg-navy-50" : "border-slate-300"}`}
            onClick={() => fileRef.current?.click()}
            data-testid="upload-dropzone"
          >
            <Upload className="h-10 w-10 text-slate-400 mx-auto mb-3" />
            <div className="text-sm font-semibold text-slate-700">
              {uploading ? "Uploading…" : "Drop files or click to browse"}
            </div>
            <div className="text-xs text-slate-500 mt-1">PDF, Excel, CSV, JPG, PNG · max 10 MB</div>
            <input
              ref={fileRef}
              type="file"
              multiple
              hidden
              accept=".pdf,.png,.jpg,.jpeg,.zip,.xlsx,.csv"
              onChange={(e) => handleFiles(e.target.files)}
              data-testid="upload-file-input"
            />
          </div>

          {process.env.NODE_ENV === "development" && (
            <div className="mt-8 bg-amber-50 border border-amber-200 rounded-xl p-4 flex gap-3 text-amber-800">
              <AlertCircle className="h-5 w-5 flex-shrink-0" />
              <div className="text-sm">
                <strong>Demo Mode:</strong> The local OCR server (<code>local_ocr.py</code>) processes PDFs and images locally. 
                No documents are sent to external APIs. In a production build, this would use AWS Textract or GCP Document AI.
              </div>
            </div>
          )}
        </section>

        {/* Processing queue */}
        <section className="surface xl:col-span-8 overflow-hidden" data-testid="documents-queue">
          <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between">
            <h2 className="text-lg font-semibold text-slate-900 font-heading">Processing Queue</h2>
            <div className="text-xs text-slate-500">{docs.length} item{docs.length === 1 ? "" : "s"}</div>
          </div>
          {loading ? (
            <div className="p-6 space-y-4">
              <div className="flex gap-4 border-b border-slate-100 pb-4">
                <Skeleton className="h-6 w-1/4" />
                <Skeleton className="h-6 w-1/4" />
                <Skeleton className="h-6 w-1/4" />
                <Skeleton className="h-6 w-1/4" />
              </div>
              {[1, 2, 3].map((i) => (
                <div key={i} className="flex gap-4">
                  <Skeleton className="h-10 w-1/4" />
                  <Skeleton className="h-10 w-1/4" />
                  <Skeleton className="h-10 w-1/4" />
                  <Skeleton className="h-10 w-1/4" />
                </div>
              ))}
            </div>
          ) : docs.length === 0 ? (
            <EmptyState title="No documents yet" hint="Upload a bank statement or invoice to get started." icon={FileText} />
          ) : (
            <table className="tp-table">
              <thead>
                <tr>
                  <th>File</th>
                  <th>Client</th>
                  <th>Type</th>
                  <th>Uploaded</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {paginatedDocs.map((d) => {
                  const Icon = STATUS_ICON[d.ocr_status] || FileText;
                  return (
                    <tr key={d.id} data-testid={`doc-row-${d.id}`}>
                      <td>
                        <div className="flex items-start gap-2.5">
                          <Icon className={`h-4 w-4 mt-0.5 flex-shrink-0 ${
                            d.ocr_status === "completed" ? "text-green-600" :
                            d.ocr_status === "failed" ? "text-red-600" :
                            d.ocr_status === "processing" ? "text-amber-600 animate-spin" : "text-slate-400"
                          }`} />
                          <div className="min-w-0">
                            <div className="text-slate-900 font-medium truncate max-w-xs">{d.original_filename}</div>
                            {d.ocr_error && <div className="text-xs text-red-600 mt-0.5">{d.ocr_error}</div>}
                            {d.extracted_count != null && <div className="text-xs text-slate-500 mt-0.5">{d.extracted_count} {d.type === "bank_statement" ? "transactions" : "invoices"} extracted</div>}
                          </div>
                        </div>
                      </td>
                      <td className="text-slate-700">{d.client_name}</td>
                      <td><span className="font-mono text-xs text-slate-600">{d.type}</span></td>
                      <td className="text-slate-500 text-sm">{formatDate(d.uploaded_at)}</td>
                      <td><StatusBadge tone={STATUS_TONE[d.ocr_status] || "neutral"}>{d.ocr_status}</StatusBadge></td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </section>

        {/* Pagination Controls */}
        {!loading && totalPages > 1 && (
          <div className="xl:col-span-8 xl:col-start-5 flex items-center justify-between">
            <div className="text-sm text-slate-500">
              Showing {(currentPage - 1) * itemsPerPage + 1} to {Math.min(currentPage * itemsPerPage, docs.length)} of {docs.length} documents
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
      </div>
    </div>
  );
}
