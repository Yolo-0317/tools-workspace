import type { JellyfinMappings, ServicesCatalog } from '../types/services'
import { apiJson } from './http'

export async function fetchServicesCatalog(): Promise<ServicesCatalog> {
  return apiJson('/api/services/catalog')
}

export async function fetchJellyfinMappings(): Promise<JellyfinMappings> {
  return apiJson('/api/services/jellyfin')
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
