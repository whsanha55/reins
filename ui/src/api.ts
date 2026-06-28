// API 클라이언트. token 은 localStorage(사용자 입력). vite proxy 가 /api → :21001.
const BASE = import.meta.env.VITE_API_BASE ?? "";
const TOKEN_KEY = "reins_token";
export const getToken = () => localStorage.getItem(TOKEN_KEY) ?? "";
export const setToken = (v: string) => localStorage.setItem(TOKEN_KEY, v);
export const clearToken = () => localStorage.removeItem(TOKEN_KEY);

export type TicketStatus = "todo" | "progressing" | "qa" | "done" | "cancel";
export type TicketType = "task" | "epic";
export type Sort = "created" | "updated" | "priority";
export type Group = "none" | "epic";
export type DecisionStatus = "pending" | "approved" | "rejected" | "changes";
export type Gate = "pr_open" | "merge" | "deploy" | "spec_ambiguous";
export type Resolution = "approved" | "rejected" | "changes";

export interface Project {
  id: number;
  name: string;
  color: string | null;
  created_at: string;
}

export interface Ticket {
  id: number;
  project_id: number;
  title: string;
  description: string | null;
  type: TicketType;
  parent_id: number | null;
  priority: number;
  status: TicketStatus;
  created_at: string;
  updated_at: string;
}

export interface TicketEvent {
  id: number;
  ticket_id: number;
  kind: string;
  payload: unknown;
  created_at: string;
}

export interface Comment {
  id: number;
  ticket_id: number;
  author: string;
  body: string;
  read_at: string | null;
  created_at: string;
}

export interface Decision {
  id: number;
  ticket_id: number;
  gate: Gate;
  summary: string;
  status: DecisionStatus;
  resolution_note: string | null;
  agent_run_id: number | null;
  created_at: string;
  resolved_at: string | null;
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json", ...(init?.headers as Record<string, string>) };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(`${BASE}${path}`, { ...init, headers });
  // ponytail: 401 → 토큰 폐기 + 게이트 복귀 이벤트. 틀린/만료 토큰 자동 감지.
  if (res.status === 401) {
    clearToken();
    window.dispatchEvent(new Event("reins:unauth"));
    throw new Error("401 Unauthorized");
  }
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText} ${text}`.trim());
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  projects: {
    list: () => req<Project[]>("/api/projects"),
    create: (name: string, color?: string) =>
      req<Project>("/api/projects", { method: "POST", body: JSON.stringify({ name, color }) }),
    remove: (id: number) => req<void>(`/api/projects/${id}`, { method: "DELETE" }),
  },
  tickets: {
    list: (params: {
      project_id?: number;
      status?: TicketStatus;
      sort?: Sort;
      parent_id?: number | null;
      type?: TicketType;
    }) => {
      const q = new URLSearchParams();
      if (params.project_id != null) q.set("project_id", String(params.project_id));
      if (params.status) q.set("status", params.status);
      if (params.sort) q.set("sort", params.sort);
      if (params.parent_id != null) q.set("parent_id", String(params.parent_id));
      if (params.type) q.set("type", params.type);
      return req<Ticket[]>(`/api/tickets?${q}`);
    },
    create: (body: {
      project_id: number;
      title: string;
      description?: string;
      type?: TicketType;
      parent_id?: number | null;
      priority?: number;
    }) => req<Ticket>("/api/tickets", { method: "POST", body: JSON.stringify(body) }),
    get: (id: number) => req<Ticket>(`/api/tickets/${id}`),
    update: (id: number, body: {
      title?: string;
      description?: string;
      priority?: number;
      parent_id?: number | null;
    }) => req<Ticket>(`/api/tickets/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
    transition: (id: number, to: TicketStatus, note?: string) =>
      req<{ from: string; to: string }>(`/api/tickets/${id}/transition`, {
        method: "POST",
        body: JSON.stringify({ to, note }),
      }),
    cancel: (id: number) => req<{ from: string; to: string }>(`/api/tickets/${id}/cancel`, { method: "POST" }),
    reopen: (id: number) => req<{ from: string; to: string }>(`/api/tickets/${id}/reopen`, { method: "POST" }),
    events: (id: number, cursor?: number) => {
      const q = new URLSearchParams({ limit: "50" });
      if (cursor) q.set("cursor", String(cursor));
      return req<{ items: TicketEvent[]; next_cursor: number | null }>(`/api/tickets/${id}/events?${q}`);
    },
  },
  comments: {
    list: (ticketId: number) => req<Comment[]>(`/api/tickets/${ticketId}/comments`),
    create: (ticketId: number, author: string, body: string) =>
      req<Comment>(`/api/tickets/${ticketId}/comments`, {
        method: "POST",
        body: JSON.stringify({ author, body }),
      }),
    markRead: (ticketId: number, cid: number) =>
      req<{ read: boolean }>(`/api/tickets/${ticketId}/comments/${cid}/read`, { method: "POST" }),
  },
  decisions: {
    list: (status?: DecisionStatus) => {
      const q = status ? `?status=${status}` : "";
      return req<Decision[]>(`/api/decisions${q}`);
    },
    resolve: (id: number, resolution: Resolution, note?: string) =>
      req<{ applied: boolean; status: string }>(`/api/decisions/${id}/resolve`, {
        method: "POST",
        body: JSON.stringify({ resolution, note }),
      }),
  },
};
