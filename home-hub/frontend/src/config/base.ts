/** Vite `base` — production `/hub/`，本地 dev 默认同 base */
export const APP_BASE = import.meta.env.BASE_URL || '/'

export function apiUrl(path: string): string {
  const base = APP_BASE.endsWith('/') ? APP_BASE : `${APP_BASE}/`
  const p = path.startsWith('/') ? path.slice(1) : path
  return `${base}${p}`
}
