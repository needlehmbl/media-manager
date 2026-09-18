const BASE: string =
  (import.meta as unknown as { env?: Record<string, string | undefined> }).env?.VITE_API_URL ??
  "http://localhost:8000";

function headers(): Record<string, string> {
  const h: Record<string, string> = { "Content-Type": "application/json" };
  const key = localStorage.getItem("mm_api_key");
  if (key) h["X-API-Key"] = key;
  return h;
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { ...headers(), ...(init?.headers as Record<string, string> | undefined) },
  });
  if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
  return (await r.json()) as T;
}

export interface Job {
  id: number;
  url: string;
  source: string;
  status: string;
  progress: number;
  output_path?: string | null;
  destination?: string | null;
  title?: string | null;
  created_at: string;
  error?: string | null;
}

export interface LibraryItem {
  id: number;
  title: string;
  file_path: string;
  thumbnail_path?: string | null;
  source: string;
  downloaded_at: string;
  tags?: string | null;
}

export interface Channel {
  id: number;
  url: string;
  check_interval: number;
  last_checked?: string | null;
  active: boolean;
}

export const api = {
  base: BASE,
  fileUrl: (absPath: string) => {
    // Map absolute download path to /files served path when possible.
    // Backend serves DOWNLOAD_DIR at /files; best-effort: use filename.
    const parts = absPath.split("/");
    const idx = parts.lastIndexOf("downloads");
    const rel = idx >= 0 ? parts.slice(idx + 1).join("/") : parts.slice(-2).join("/");
    return `${BASE}/files/${encodeURI(rel)}`;
  },
  jobs: {
    list: (status?: string) => req<Job[]>(`/jobs${status ? `?status=${status}` : ""}`),
    create: (payload: { url?: string; urls?: string[]; source: string; destination?: string }) =>
      req<Job | Job[]>(`/jobs`, { method: "POST", body: JSON.stringify(payload) }),
    retry: (id: number) => req<Job>(`/jobs/${id}/retry`, { method: "POST" }),
    cancel: (id: number) => req(`/jobs/${id}/cancel`, { method: "POST" }),
    remove: (id: number) => req(`/jobs/${id}`, { method: "DELETE" }),
  },
  library: {
    list: (q?: string, source?: string) =>
      req<LibraryItem[]>(`/library${q || source ? `?${new URLSearchParams({ ...(q ? { q } : {}), ...(source ? { source } : {}) })}` : ""}`),
    remove: (id: number, deleteFile = false) =>
      req(`/library/${id}${deleteFile ? "?delete_file=true" : ""}`, { method: "DELETE" }),
  },
  channels: {
    list: () => req<Channel[]>(`/channels`),
    create: (payload: { url: string; check_interval: number; active: boolean }) =>
      req<Channel>(`/channels`, { method: "POST", body: JSON.stringify(payload) }),
    update: (id: number, payload: Partial<Channel>) =>
      req<Channel>(`/channels/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
    remove: (id: number) => req(`/channels/${id}`, { method: "DELETE" }),
    check: (id: number) => req(`/channels/${id}/check`, { method: "POST" }),
  },
  settings: () => req<{ download_dir: string; max_concurrent_jobs: number; auth_enabled: boolean }>(`/settings`),
};
