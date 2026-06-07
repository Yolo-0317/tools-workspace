/** Vite `base` — production `/english/`, local dev `/`. */
export const APP_BASE = import.meta.env.BASE_URL || "/";

export function apiUrl(path: string): string {
  const base = APP_BASE.endsWith("/") ? APP_BASE : `${APP_BASE}/`;
  const p = path.startsWith("/") ? path.slice(1) : path;
  return `${base}${p}`;
}

export function wsCallUrl(): string {
  const proto = location.protocol === "https:" ? "wss:" : "ws:";
  const base = APP_BASE.replace(/\/$/, "");
  return `${proto}//${location.host}${base}/ws/call`;
}
