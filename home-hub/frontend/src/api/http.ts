/** 带 Cookie 会话的 fetch 封装 */
import { apiUrl } from '../config/base'

const HUB_TOKEN = import.meta.env.VITE_HUB_TOKEN ?? ''

export function apiHeaders(extra: Record<string, string> = {}): HeadersInit {
  const h: Record<string, string> = {
    'X-Hub-Client': 'home-hub',
    ...extra,
  }
  if (HUB_TOKEN) h['X-Hub-Token'] = HUB_TOKEN
  return h
}

export async function apiFetch(
  path: string,
  init: RequestInit = {},
): Promise<Response> {
  const headers = new Headers(init.headers ?? {})
  if (!headers.has('X-Hub-Client')) headers.set('X-Hub-Client', 'home-hub')
  if (HUB_TOKEN) headers.set('X-Hub-Token', HUB_TOKEN)
  if (init.body && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }
  return fetch(apiUrl(path), {
    ...init,
    headers,
    credentials: 'include',
  })
}

export async function apiJson<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await apiFetch(path, init)
  if (!res.ok) {
    let detail = await res.text()
    try {
      detail = JSON.parse(detail).detail ?? detail
    } catch {
      /* plain text */
    }
    throw new Error(typeof detail === 'string' ? detail : `HTTP ${res.status}`)
  }
  return res.json() as Promise<T>
}
