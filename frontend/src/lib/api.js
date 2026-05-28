import axios from "axios";

const BASE = process.env.REACT_APP_BACKEND_URL || "http://localhost:8000";
export const API = `${BASE}/api`;

export const http = axios.create({
  baseURL: API,
  timeout: 20000,
});

// Add interceptor for auth token
http.interceptors.request.use((config) => {
  const token = localStorage.getItem("taxpilot_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Handle 401s
http.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response && error.response.status === 401) {
      localStorage.removeItem("taxpilot_token");
      window.location.href = "/login";
    }
    return Promise.reject(error);
  }
);

// ----- Auth -----
export const login = (data) => {
  const params = new URLSearchParams();
  params.append("username", data.email);
  params.append("password", data.password);
  return http.post("/auth/login", params, {
    headers: { "Content-Type": "application/x-www-form-urlencoded" }
  }).then((r) => r.data);
};

export const register = (data) => http.post("/auth/register", data).then((r) => r.data);

// ----- Profile -----
export const getProfile = () => http.get("/profile").then((r) => r.data);
export const updateProfile = (payload) => http.put("/settings/profile", payload).then((r) => r.data);
export const updateAlertPrefs = (prefs) => http.put("/settings/alerts", prefs).then((r) => r.data);

// ----- Dashboard -----
export const getDashboardSummary = () => http.get("/dashboard/summary").then((r) => r.data);

// ----- Clients -----
export const listClients = (params = {}) => http.get("/clients", { params }).then((r) => r.data);
export const getClient = (id) => http.get(`/clients/${id}`).then((r) => r.data);
export const createClient = (data) => http.post("/clients", data).then((r) => r.data);
export const updateClient = (id, data) => http.put(`/clients/${id}`, data).then((r) => r.data);
export const deleteClient = (id) => http.delete(`/clients/${id}`).then((r) => r.data);

// ----- Documents -----
export const listDocuments = (params = {}) => http.get("/documents", { params }).then((r) => r.data);
export const uploadDocument = (clientId, docType, file) => {
  const fd = new FormData();
  fd.append("client_id", clientId);
  fd.append("doc_type", docType);
  fd.append("file", file);
  return http
    .post("/documents/upload", fd, { headers: { "Content-Type": "multipart/form-data" } })
    .then((r) => r.data);
};

// ----- GST -----
export const getGSTSummary = (clientId, month, year) =>
  http.get("/gst/reconciliation/summary", { params: { client_id: clientId, month, year } }).then((r) => r.data);
export const listMismatches = (params = {}) => http.get("/gst/mismatches", { params }).then((r) => r.data);
export const resolveMismatch = (id, notes) =>
  http.post(`/gst/mismatches/${id}/resolve`, { notes, resolved_by: "ca_user" }).then((r) => r.data);

// ----- TDS -----
export const getTDSSummary = (clientId, fy = "2025-26") =>
  http.get("/tds/summary", { params: { client_id: clientId, fy } }).then((r) => r.data);
export const getTDSMissed = (clientId, fy = "2025-26") =>
  http.get("/tds/missed", { params: { client_id: clientId, fy } }).then((r) => r.data);
export const getTDSVendors = (clientId, fy = "2025-26") =>
  http.get("/tds/vendors", { params: { client_id: clientId, fy } }).then((r) => r.data);

// ----- Compliance -----
export const getComplianceCalendar = (clientId, status) =>
  http.get("/compliance/calendar", { params: { client_id: clientId, status } }).then((r) => r.data);
export const markFiled = (id, filedBy = "ca_user") =>
  http.post(`/compliance/${id}/mark-filed`, { filed_by: filedBy }).then((r) => r.data);
