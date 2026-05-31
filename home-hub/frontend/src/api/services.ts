import type { JellyfinMappings, ServicesCatalog } from '../types/services'

const API_BASE = import.meta.env.VITE_API_BASE ?? ''
const HUB_TOKEN = import.meta.env.VITE_HUB_TOKEN ?? ''

function headers(): HeadersInit {
  const h: Record<string, string> = {}
  if (HUB_TOKEN) h['X-Hub-Token'] = HUB_TOKEN
  return h
}

export async function fetchServicesCatalog(): Promise<ServicesCatalog> {
  const res = await fetch(`${API_BASE}/api/services/catalog`, { headers: headers() })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function fetchJellyfinMappings(): Promise<JellyfinMappings> {
  const res = await fetch(`${API_BASE}/api/services/jellyfin`, { headers: headers() })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export function healthLabel(status?: string): string {
  if (status === 'up') return '正常'
  if (status === 'down') return '不可用'
  return '未知'
}

export function healthClass(status?: string): string {
  if (status === 'up') return 'ok'
  if (status === 'down') return 'down'
  return 'unknown'
}
