import { apiUrl } from "../config/base";
import { API_FETCH_TIMEOUT_MS } from "../config/network";

export type AuthUser = {
  user_id: string;
  username: string;
  display_name: string;
};

export type WhoamiResponse = {
  authenticated: boolean;
  require_auth: boolean;
  user_id?: string;
  username?: string;
  display_name?: string;
};

export async function apiFetch(
  path: string,
  init?: RequestInit,
  timeoutMs = API_FETCH_TIMEOUT_MS,
): Promise<Response> {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(apiUrl(path), {
      credentials: "include",
      ...init,
      signal: init?.signal ?? controller.signal,
      headers: {
        ...(init?.headers ?? {}),
      },
    });
  } finally {
    window.clearTimeout(timer);
  }
}

export type AuthConfig = {
  require_auth: boolean;
  stt_enabled_for_me: boolean;
  stt_users: string[];
  free_chat_enabled_for_me: boolean;
  free_chat_users: string[];
};

export async function fetchAuthConfig(): Promise<AuthConfig> {
  const fallback: AuthConfig = {
    require_auth: true,
    stt_enabled_for_me: true,
    stt_users: [],
    free_chat_enabled_for_me: false,
    free_chat_users: [],
  };
  try {
    const r = await apiFetch("api/auth/config");
    if (!r.ok) return fallback;
    const data = (await r.json()) as Partial<AuthConfig>;
    return {
      require_auth: data.require_auth ?? true,
      stt_enabled_for_me: data.stt_enabled_for_me ?? true,
      stt_users: data.stt_users ?? [],
      free_chat_enabled_for_me: data.free_chat_enabled_for_me ?? false,
      free_chat_users: data.free_chat_users ?? [],
    };
  } catch {
    return fallback;
  }
}

export async function fetchWhoami(): Promise<WhoamiResponse> {
  const r = await apiFetch("api/auth/whoami");
  if (!r.ok) {
    return { authenticated: false, require_auth: true };
  }
  return r.json();
}

export async function login(
  username: string,
  password: string,
): Promise<AuthUser> {
  const r = await apiFetch("api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (!r.ok) {
    const err = await r.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail || "登录失败");
  }
  const data = (await r.json()) as AuthUser;
  return data;
}

export async function logout(): Promise<void> {
  await apiFetch("api/auth/logout", { method: "POST" });
}
