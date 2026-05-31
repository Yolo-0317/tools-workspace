import type {
  DashboardPayload,
  DisciplinePayload,
  LaunchdJob,
  MonitorHistoryDay,
  MonitorRule,
  MonitorState,
  PortfolioHistory,
  PositionRow,
  SelectionHistory,
} from '../types/dashboard'

const API_BASE = import.meta.env.VITE_API_BASE ?? ''
const HUB_TOKEN = import.meta.env.VITE_HUB_TOKEN ?? ''

function headers(): HeadersInit {
  const h: Record<string, string> = {}
  if (HUB_TOKEN) h['X-Hub-Token'] = HUB_TOKEN
  return h
}

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { headers: headers() })
  if (!res.ok) throw new Error(await res.text())
  return res.json() as Promise<T>
}

export function fetchDashboardSummary(slot = 'eod'): Promise<DashboardPayload> {
  return getJson(`/api/dashboard/summary?slot=${encodeURIComponent(slot)}`)
}

export function fetchDiscipline() {
  return getJson<DisciplinePayload>('/api/dashboard/discipline')
}

export function fetchPortfolioHistory(days = 90, slot = 'eod') {
  return getJson<PortfolioHistory>(
    `/api/dashboard/portfolio/history?days=${days}&slot=${encodeURIComponent(slot)}`,
  )
}

export function fetchPortfolioSnapshot(date: string, slot = 'eod') {
  return getJson<{ snapshot_date: string; positions: PositionRow[] }>(
    `/api/dashboard/portfolio/snapshot?date=${encodeURIComponent(date)}&slot=${encodeURIComponent(slot)}`,
  )
}

export function fetchSelectionStrategies() {
  return getJson<{ strategies: string[] }>('/api/dashboard/selection/strategies')
}

export function fetchPortfolioCurrent() {
  return getJson<{
    account: Record<string, unknown>
    positions: Record<string, unknown>[]
    alert_rules: MonitorRule[]
  }>('/api/dashboard/portfolio')
}

export function fetchMonitorRules() {
  return getJson<{ rules: MonitorRule[] }>('/api/dashboard/monitor/rules')
}

export function fetchMonitorState(date?: string) {
  const q = date ? `?date=${encodeURIComponent(date)}` : ''
  return getJson<MonitorState>(`/api/dashboard/monitor/state${q}`)
}

export function fetchMonitorDates(limit = 90) {
  return getJson<{ dates: MonitorHistoryDay[] }>(
    `/api/dashboard/monitor/dates?limit=${limit}`,
  )
}

export function fetchSelectionDates(strategy = 'combined') {
  return getJson<{ strategy: string; dates: string[] }>(
    `/api/dashboard/selection/dates?strategy=${encodeURIComponent(strategy)}`,
  )
}

export function fetchSelectionHistory(tradeDate: string, strategy = 'combined') {
  return getJson<SelectionHistory>(
    `/api/dashboard/selection?trade_date=${encodeURIComponent(tradeDate)}&strategy=${encodeURIComponent(strategy)}`,
  )
}

export function fetchSnapshotAlerts(limit = 30) {
  return getJson<{ lines: string[] }>(`/api/dashboard/alerts/snapshot?limit=${limit}`)
}

export function fetchJobs() {
  return getJson<{ jobs: LaunchdJob[] }>('/api/dashboard/jobs')
}

export function fmtNum(v: unknown, digits = 2): string {
  if (v === null || v === undefined || v === '') return '—'
  const n = Number(v)
  if (Number.isNaN(n)) return String(v)
  return n.toLocaleString('zh-CN', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })
}

export function fmtRatioPct(v: unknown): string {
  if (v === null || v === undefined || v === '') return '—'
  let n = Number(v)
  if (Number.isNaN(n)) return String(v)
  if (n <= 1.5) n *= 100
  return `${n.toFixed(1)}%`
}

export function fmtPct(v: unknown): string {
  if (v === null || v === undefined || v === '') return '—'
  const n = Number(v)
  if (Number.isNaN(n)) return String(v)
  return `${(n * (Math.abs(n) <= 1 ? 100 : 1)).toFixed(2)}%`
}
