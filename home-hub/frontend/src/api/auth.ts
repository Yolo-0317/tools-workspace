import { apiJson } from './http'
import type { HubRole } from '../auth/hubAuth'

interface WhoamiResponse {
  authenticated: boolean
  role: HubRole
  username: string | null
  share_only: boolean
}

interface LoginResponse {
  ok: boolean
  username: string
  role: HubRole
  share_only: boolean
}

export function fetchWhoami(): Promise<WhoamiResponse> {
  return apiJson('/api/auth/whoami')
}

export function loginRequest(username: string, password: string) {
  return apiJson<LoginResponse>('/api/auth/login', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  })
}

export function logoutRequest() {
  return apiJson<{ ok: boolean }>('/api/auth/logout', { method: 'POST' })
}
