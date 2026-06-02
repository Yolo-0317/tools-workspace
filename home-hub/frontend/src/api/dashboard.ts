import type {
  DashboardPayload,
  DisciplinePayload,
  EmotionCyclePayload,
  LaunchdJob,
  MonitorHistoryDay,
  MonitorRule,
  MonitorState,
  NewsItem,
  NewsMeta,
  BriefingSnapshot,
  PortfolioHistory,
  PositionRow,
  SelectionHistory,
  SelectionKline,
} from '../types/dashboard'
import { apiJson } from './http'

export function fetchDashboardSummary(slot = 'eod', live = false) {
  const q = new URLSearchParams({ slot })
  if (live) q.set('live', 'true')
  return apiJson<DashboardPayload>(`/api/dashboard/summary?${q}`)
}

export function fetchMonitorRules(live = true) {
  return apiJson<{
    rules: MonitorRule[]
    quote_source?: string
    quotes_as_of?: string
  }>(`/api/dashboard/monitor/rules?live=${live ? 'true' : 'false'}`)
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


export function fetchMonitorState(date?: string) {
  const q = date ? `?date=${encodeURIComponent(date)}` : ''
  return apiJson<MonitorState>(`/api/dashboard/monitor/state${q}`)
}

export function fetchMonitorDates(limit = 90) {
  return apiJson<{ dates: MonitorHistoryDay[] }>(
    `/api/dashboard/monitor/dates?limit=${limit}`,
  )
}

export function fetchSelectionDates(strategy = 'all') {
  return apiJson<{ strategy: string; dates: string[] }>(
    `/api/dashboard/selection/dates?strategy=${encodeURIComponent(strategy)}`,
  )
}

export function fetchSelectionHistory(tradeDate: string, strategy = 'all') {
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

export interface SelectionSopJob {
  job_id: string
  status: 'queued' | 'running' | 'done' | 'done_with_warning' | 'failed'
  code: string
  name?: string
  trade_date: string
  strategy?: string
  message?: string
  error?: string
  created_at?: string
  started_at?: string
  finished_at?: string
}

export function requestSelectionSopAnalyze(
  code: string,
  tradeDate: string,
  strategy = 'combined',
) {
  return apiJson<SelectionSopJob>('/api/dashboard/selection/sop-analyze', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ code, trade_date: tradeDate, strategy }),
  })
}

export function fetchSelectionSopJob(jobId: string) {
  return apiJson<SelectionSopJob>(`/api/dashboard/selection/sop-jobs/${encodeURIComponent(jobId)}`)
}

export function fetchSelectionSopJobs(activeOnly = false, limit = 30) {
  const q = new URLSearchParams({
    active_only: activeOnly ? 'true' : 'false',
    limit: String(limit),
  })
  return apiJson<{ jobs: SelectionSopJob[]; active_count: number }>(
    `/api/dashboard/selection/sop-jobs?${q}`,
  )
}

export function fetchSnapshotAlerts(limit = 30) {
  return apiJson<{ lines: string[] }>(`/api/dashboard/alerts/snapshot?limit=${limit}`)
}

export function fetchJobs() {
  return apiJson<{ jobs: LaunchdJob[] }>('/api/dashboard/jobs')
}

export function fetchNewsMeta(date?: string) {
  const q = date ? `?date=${encodeURIComponent(date)}` : ''
  return apiJson<NewsMeta>(`/api/dashboard/news/meta${q}`)
}

export function fetchNewsItems(params?: {
  date?: string
  category?: string
  sentiment?: string
  limit?: number
}) {
  const q = new URLSearchParams()
  if (params?.date) q.set('date', params.date)
  if (params?.category) q.set('category', params.category)
  if (params?.sentiment) q.set('sentiment', params.sentiment)
  if (params?.limit) q.set('limit', String(params.limit))
  const qs = q.toString()
  return apiJson<{
    date: string
    category: string | null
    sentiment: string | null
    items: NewsItem[]
  }>(`/api/dashboard/news/items${qs ? `?${qs}` : ''}`)
}

export function fetchNewsBriefings(date?: string) {
  const q = date ? `?date=${encodeURIComponent(date)}` : ''
  return apiJson<{ date: string; briefings: BriefingSnapshot[] }>(
    `/api/dashboard/news/briefings${q}`,
  )
}

export function fetchLatestBriefing() {
  return apiJson<{ briefing: BriefingSnapshot | null }>(
    '/api/dashboard/news/briefings/latest',
  )
}

export function fetchEmotionCycleDates() {
  return apiJson<{ dates: string[]; default_date?: string | null }>(
    '/api/dashboard/emotion/dates',
  )
}

export function fetchEmotionCycle(tradeDate?: string, slot?: string) {
  const q = new URLSearchParams()
  if (tradeDate) q.set('trade_date', tradeDate)
  if (slot) q.set('slot', slot)
  const qs = q.toString()
  return apiJson<EmotionCyclePayload>(`/api/dashboard/emotion${qs ? `?${qs}` : ''}`)
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
