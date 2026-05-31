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
  SelectionKline,
} from '../types/dashboard'
import { apiJson } from './http'

export function fetchDashboardSummary(slot = 'eod'): Promise<DashboardPayload> {
  return apiJson(`/api/dashboard/summary?slot=${encodeURIComponent(slot)}`)
}

export function fetchDiscipline() {
  return apiJson<DisciplinePayload>('/api/dashboard/discipline')
}

export function fetchPortfolioHistory(days = 90, slot = 'eod') {
  return apiJson<PortfolioHistory>(
    `/api/dashboard/portfolio/history?days=${days}&slot=${encodeURIComponent(slot)}`,
  )
}

export function fetchPortfolioSnapshot(date: string, slot = 'eod') {
  return apiJson<{ snapshot_date: string; positions: PositionRow[] }>(
    `/api/dashboard/portfolio/snapshot?date=${encodeURIComponent(date)}&slot=${encodeURIComponent(slot)}`,
  )
}

export function fetchSelectionStrategies() {
  return apiJson<{ strategies: string[] }>('/api/dashboard/selection/strategies')
}

export function fetchPortfolioCurrent() {
  return apiJson<{
    account: Record<string, unknown>
    positions: Record<string, unknown>[]
    alert_rules: MonitorRule[]
  }>('/api/dashboard/portfolio')
}

export function fetchMonitorRules() {
  return apiJson<{ rules: MonitorRule[] }>('/api/dashboard/monitor/rules')
}

export function fetchMonitorState(date?: string) {
  const q = date ? `?date=${encodeURIComponent(date)}` : ''
  return apiJson<MonitorState>(`/api/dashboard/monitor/state${q}`)
}

export function fetchMonitorDates(limit = 90) {
  return apiJson<{ dates: MonitorHistoryDay[] }>(
    `/api/dashboard/monitor/dates?limit=${limit}`,
  )
}

export function fetchSelectionDates(strategy = 'combined') {
  return apiJson<{ strategy: string; dates: string[] }>(
    `/api/dashboard/selection/dates?strategy=${encodeURIComponent(strategy)}`,
  )
}

export function fetchSelectionHistory(tradeDate: string, strategy = 'combined') {
  return apiJson<SelectionHistory>(
    `/api/dashboard/selection?trade_date=${encodeURIComponent(tradeDate)}&strategy=${encodeURIComponent(strategy)}`,
  )
}

export function fetchSelectionKline(
  code: string,
  tradeDate: string,
  days = 60,
) {
  return apiJson<SelectionKline>(
    `/api/dashboard/selection/kline?code=${encodeURIComponent(code)}&trade_date=${encodeURIComponent(tradeDate)}&days=${days}`,
  )
}

export function fetchSnapshotAlerts(limit = 30) {
  return apiJson<{ lines: string[] }>(`/api/dashboard/alerts/snapshot?limit=${limit}`)
}

export function fetchJobs() {
  return apiJson<{ jobs: LaunchdJob[] }>('/api/dashboard/jobs')
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
