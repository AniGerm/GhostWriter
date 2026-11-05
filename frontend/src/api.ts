const BASE = import.meta.env.VITE_API_BASE ?? "";

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, init);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || res.statusText);
  }
  return res.json() as Promise<T>;
}

export type Question = { number: number; text: string; keyword: string };

export type Project = {
  id: string;
  patient_label: string;
  reference: string;
  notes: string;
  draft_html: string;
  questions: Question[];
  documents: {
    id: string;
    role: "anfrage" | "befund";
    display_name: string;
    page_count: number;
    has_text: boolean;
    included: boolean;
  }[];
  cost: {
    page_count: number;
    flat_fee: number;
    copy_cost: number;
    postage: number;
    total: number;
  } | null;
};

export type Job = {
  id: string;
  phase: string;
  percent: number;
  message?: string;
  error?: string | null;
  project_id?: string;
};

export type ProjectSummary = {
  id: string;
  patient_label: string;
  reference: string;
  updated_at: string;
};

export type AppSettings = {
  ollama_base_url: string;
  ollama_model: string;
  ollama_num_ctx: number;
  flat_fee: number;
  copy_tier_up_to: number;
  copy_tier_price: number;
  after_last_tier_price: number;
  letterhead_html: string;
  signature_html: string;
  github_repo: string;
  postage: Record<string, number>;
  default_postage_key?: string;
  default_printer?: string;
};

export const api = {
  health: () =>
    req<{
      ok: boolean;
      version: string;
      ollama?: {
        reachable: boolean;
        model: string;
        model_available: boolean;
        models?: string[];
        error?: string;
      };
    }>("/api/health"),
  listProjects: () => req<ProjectSummary[]>("/api/projects"),
  createProject: (patient_label: string, reference = "") =>
    req<Project>("/api/projects", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ patient_label, reference }),
    }),
  getProject: (id: string) => req<Project>(`/api/projects/${id}`),
  deleteProject: (id: string) =>
    req<{ ok: boolean }>(`/api/projects/${id}`, { method: "DELETE" }),
  restoreProject: (id: string) =>
    req<Project>(`/api/projects/${id}/restore`, { method: "POST" }),
  setNotes: (id: string, notes: string) =>
    req<Project>(`/api/projects/${id}/notes`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ notes }),
    }),
  setDraft: (id: string, html: string) =>
    req<Project>(`/api/projects/${id}/draft`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ html }),
    }),
  setQuestions: (id: string, questions: Question[]) =>
    req<Project>(`/api/projects/${id}/questions`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ questions }),
    }),
  uploadDocument: async (id: string, role: "anfrage" | "befund", file: File) => {
    const body = new FormData();
    body.append("role", role);
    body.append("file", file);
    return req<Project & { document_id: string }>(`/api/projects/${id}/documents`, {
      method: "POST",
      body,
    });
  },
  setDocumentIncluded: (projectId: string, documentId: string, included: boolean) =>
    req<Project>(`/api/projects/${projectId}/documents/${documentId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ included }),
    }),
  deleteDocument: (projectId: string, documentId: string) =>
    req<Project>(`/api/projects/${projectId}/documents/${documentId}`, {
      method: "DELETE",
    }),
  analyze: (id: string) =>
    req<{ job_id: string }>(`/api/projects/${id}/analyze`, { method: "POST" }),
  regenerate: (id: string, revision_notes = "") =>
    req<{ job_id: string }>(`/api/projects/${id}/regenerate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ revision_notes }),
    }),
  getJob: (jobId: string) => req<Job>(`/api/jobs/${jobId}`),
  costs: (
    id: string,
    page_count: number,
    postage_key?: string | null,
    custom_postage?: number | null,
  ) =>
    req<{
      page_count: number;
      flat_fee: number;
      copy_cost: number;
      postage: number;
      total: number;
    }>(`/api/projects/${id}/costs`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ page_count, postage_key, custom_postage }),
    }),
  getSettings: () => req<AppSettings>("/api/settings"),
  putSettings: (patch: Partial<AppSettings>) =>
    req<AppSettings>("/api/settings", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(patch),
    }),
  documentUrl: (projectId: string, documentId: string) =>
    `${BASE}/api/projects/${projectId}/documents/${documentId}/file`,
  documentPageUrl: (projectId: string, documentId: string, pageNumber: number) =>
    `${BASE}/api/projects/${projectId}/documents/${documentId}/pages/${pageNumber}`,
  listPrinters: () =>
    req<{
      printers: { name: string; is_default: boolean }[];
      default_printer: string;
      system_default: string;
    }>("/api/printers"),
  inboxStatus: () =>
    req<{
      spool_dir: string;
      spool_exists: boolean;
      spool_is_dir: boolean;
      readable: boolean;
      list_error: string | null;
      entry_count: number;
      pdf_count: number;
      new_pdf_count: number;
      sample_names: string[];
      owner_hint: string | null;
      mode_hint: string | null;
      cups_running: boolean;
    }>("/api/inbox/status"),
  importInbox: (projectId: string, role: "anfrage" | "befund" = "befund") =>
    req<{
      imported: { id: string; display_name: string }[];
      errors: string[];
      project: Project;
    }>(`/api/projects/${projectId}/inbox/import`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ role }),
    }),
  listOllamaModels: (base_url?: string) => {
    const query = base_url ? `?base_url=${encodeURIComponent(base_url)}` : "";
    return req<{ models: string[]; base_url: string }>(`/api/ollama/models${query}`);
  },
  updateStatus: () =>
    req<{
      phase: string;
      current_version?: string | null;
      latest_version?: string | null;
      available?: boolean;
      download_percent?: number;
      error?: string | null;
      message?: string | null;
      deb_name?: string | null;
    }>("/api/updates"),
  checkUpdate: () =>
    req<{
      phase: string;
      current_version?: string | null;
      latest_version?: string | null;
      available?: boolean;
      error?: string | null;
      message?: string | null;
    }>("/api/updates/check", { method: "POST" }),
  downloadUpdate: () =>
    req<{
      phase: string;
      download_percent?: number;
      error?: string | null;
      available?: boolean;
      message?: string | null;
    }>("/api/updates/download", { method: "POST" }),
  installUpdate: () =>
    req<{
      phase: string;
      error?: string | null;
      message?: string | null;
      available?: boolean;
    }>("/api/updates/install", { method: "POST" }),
};
