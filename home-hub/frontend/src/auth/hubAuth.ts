import { ref } from 'vue'
import { fetchWhoami, loginRequest, logoutRequest } from '../api/auth'

export type HubRole = 'admin' | 'share'

export interface HubAuthState {
  authenticated: boolean
  role: HubRole
  username: string | null
  shareOnly: boolean
}

const guest: HubAuthState = {
  authenticated: false,
  role: 'admin',
  username: null,
  shareOnly: false,
}

export const hubAuth = ref<HubAuthState>({ ...guest })

function applyPayload(data: Partial<HubAuthState> & { share_only?: boolean }) {
  hubAuth.value = {
    authenticated: Boolean(data.authenticated ?? true),
    role: data.share_only || data.shareOnly ? 'share' : (data.role ?? 'admin'),
    username: data.username ?? null,
    shareOnly: Boolean(data.share_only ?? data.shareOnly),
  }
}

export async function initHubAuth(): Promise<HubAuthState> {
  try {
    const data = await fetchWhoami()
    applyPayload({ ...data, authenticated: true })
  } catch {
    hubAuth.value = { ...guest }
  }
  return hubAuth.value
}

export function getHubAuth(): HubAuthState {
  return hubAuth.value
}

export function isShareMode(): boolean {
  return hubAuth.value.shareOnly
}

export function isAuthenticated(): boolean {
  return hubAuth.value.authenticated
}

export async function login(username: string, password: string): Promise<HubAuthState> {
  const data = await loginRequest(username, password)
  applyPayload({
    authenticated: true,
    username: data.username,
    role: data.role,
    share_only: data.share_only,
  })
  return hubAuth.value
}

export async function logout(): Promise<void> {
  try {
    await logoutRequest()
  } finally {
    hubAuth.value = { ...guest }
  }
}
