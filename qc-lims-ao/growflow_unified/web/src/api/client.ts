/* ============================================================================
   Planner API client. Base http://127.0.0.1:8765 (override via VITE_PLANNER_API).
   Auth: JWT bearer (per-user login). The token is held in memory + mirrored to
   localStorage so a refresh keeps the session. 401 responses clear it and bubble
   up so the shell can show the login.
   ============================================================================ */

const BASE =
  (import.meta as { env?: Record<string, string> }).env?.VITE_PLANNER_API ?? "http://127.0.0.1:8765";
const STORAGE_KEY = "planner_token";

let token: string | null =
  typeof localStorage !== "undefined" ? localStorage.getItem(STORAGE_KEY) : null;

export function setToken(t: string | null): void {
  token = t;
  if (typeof localStorage === "undefined") return;
  if (t) localStorage.setItem(STORAGE_KEY, t);
  else localStorage.removeItem(STORAGE_KEY);
}

export function getToken(): string | null {
  return token;
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

function authHeaders(): Record<string, string> {
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function handle<T>(r: Response, path: string): Promise<T> {
  if (r.status === 401) {
    setToken(null);
    throw new ApiError(401, `${path} → 401 (unauthorized)`);
  }
  if (!r.ok) throw new ApiError(r.status, `${path} → ${r.status}`);
  if (r.status === 204) return undefined as T;
  return (await r.json()) as T;
}

export async function apiGet<T>(path: string): Promise<T> {
  return handle<T>(await fetch(`${BASE}${path}`, { headers: authHeaders() }), path);
}

export async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  return handle<T>(
    await fetch(`${BASE}${path}`, {
      method: "POST",
      headers: { ...authHeaders(), "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    }),
    path,
  );
}

export async function apiPatch<T>(path: string, body: unknown): Promise<T> {
  return handle<T>(
    await fetch(`${BASE}${path}`, {
      method: "PATCH",
      headers: { ...authHeaders(), "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
    path,
  );
}

export async function apiPut<T>(path: string, body: unknown): Promise<T> {
  return handle<T>(
    await fetch(`${BASE}${path}`, {
      method: "PUT",
      headers: { ...authHeaders(), "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
    path,
  );
}

export async function apiDelete(path: string): Promise<void> {
  await handle<void>(await fetch(`${BASE}${path}`, { method: "DELETE", headers: authHeaders() }), path);
}
