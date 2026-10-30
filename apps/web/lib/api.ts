import type {
  Asset,
  EngineSettings,
  EngineStatus,
  Generation,
  Health,
  Project,
} from "./types";

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE?.replace(/\/$/, "") || "http://127.0.0.1:8787";

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: {
        ...(init?.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
        ...(init?.headers || {}),
      },
      cache: "no-store",
    });
  } catch {
    throw new ApiError("تعذّر الاتصال بالخادم المحلي. تأكد أن خدمات API تعمل على 8787.", 0);
  }

  if (!res.ok) {
    let detail = `فشل الطلب (${res.status})`;
    try {
      const body = await res.json();
      if (typeof body.detail === "string") detail = body.detail;
      else if (Array.isArray(body.detail)) detail = body.detail[0]?.msg || detail;
      else if (body.message) detail = body.message;
    } catch {
      /* ignore */
    }
    throw new ApiError(detail, res.status);
  }
  if (res.status === 204) return {} as T;
  return (await res.json()) as T;
}

export const api = {
  health: () => request<Health>("/api/health"),

  projects: {
    list: () => request<Project[]>("/api/projects"),
    create: (payload: {
      name: string;
      description?: string;
      aspect_ratio?: string;
      style_preset?: string;
    }) =>
      request<Project>("/api/projects", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    get: (id: string) =>
      request<Project & { generations: Generation[]; assets: Asset[] }>(`/api/projects/${id}`),
    update: (id: string, payload: Partial<Project>) =>
      request<Project>(`/api/projects/${id}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      }),
    remove: (id: string) => request<{ message: string }>(`/api/projects/${id}`, { method: "DELETE" }),
  },

  generations: {
    list: (projectId?: string, limit = 30) => {
      const query = new URLSearchParams();
      if (projectId) query.set("project_id", projectId);
      query.set("limit", String(limit));
      return request<Generation[]>(`/api/generations?${query.toString()}`);
    },
    create: (payload: {
      project_id: string;
      type: string;
      prompt: string;
      negative_prompt?: string;
      engine_id?: string;
      params: Record<string, unknown>;
    }) =>
      request<Generation>("/api/generations", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    get: (id: string) => request<Generation>(`/api/generations/${id}`),
    cancel: (id: string) =>
      request<{ message: string }>(`/api/generations/${id}/cancel`, { method: "POST" }),
    retry: (id: string) =>
      request<Generation>(`/api/generations/${id}/retry`, { method: "POST" }),
  },

  assets: {
    list: (projectId?: string, kind?: string, limit = 60) => {
      const query = new URLSearchParams();
      if (projectId) query.set("project_id", projectId);
      if (kind) query.set("kind", kind);
      query.set("limit", String(limit));
      return request<Asset[]>(`/api/assets?${query.toString()}`);
    },
    upload: (projectId: string, file: File, kind = "image") => {
      const form = new FormData();
      form.append("project_id", projectId);
      form.append("kind", kind);
      form.append("file", file);
      return request<Asset>("/api/assets/upload", { method: "POST", body: form });
    },
    remove: (id: string) => request<{ message: string }>(`/api/assets/${id}`, { method: "DELETE" }),
  },

  engines: {
    list: () => request<import("./types").EngineInfo[]>("/api/engines"),
    status: () => request<EngineStatus[]>("/api/engines/status"),
    test: (engineId: string) =>
      request<EngineStatus>("/api/engines/test", {
        method: "POST",
        body: JSON.stringify({ engine_id: engineId }),
      }),
    hfAccount: () =>
      request<{
        connected: boolean;
        name?: string;
        fullname?: string;
        plan?: string;
        email_verified?: boolean;
        detail: string;
      }>("/api/engines/hfspace/account"),
  },

  settings: {
    get: () => request<EngineSettings>("/api/settings"),
    update: (payload: Partial<EngineSettings>) =>
      request<EngineSettings>("/api/settings", {
        method: "PUT",
        body: JSON.stringify(payload),
      }),
  },

  prompts: {
    enhance: (prompt: string, style: string) =>
      request<{ prompt: string; negative_prompt: string; tips: string[] }>(
        "/api/prompts/enhance",
        { method: "POST", body: JSON.stringify({ prompt, style }) },
      ),
  },

  exports: {
    create: (payload: { asset_ids: string[]; aspect_ratio: string; filename: string }) =>
      request<Asset>("/api/exports", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
  },
};

export function mediaUrl(path: string): string {
  if (!path) return "";
  if (path.startsWith("http")) return path;
  return `${API_BASE}${path}`;
}

export function eventsUrl(generationId: string): string {
  return `${API_BASE}/api/generations/${generationId}/events`;
}
