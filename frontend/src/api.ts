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
  analyze: (id: string) =>
    req<{ job_id: string }>(`/api/projects/${id}/analyze`, { method: "POST" }),
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
};
