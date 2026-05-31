export interface AccountSnapshot {
  snapshot_date: string
  total_assets?: number | null
  market_value?: number | null
  holding_pnl?: number | null
  available_cash?: number | null
  position_ratio?: number | null
}

export interface PositionRow {
  code?: string
  ts_code?: string
  name?: string
  shares?: number
  cost?: number
  cost_price?: number
  current_price?: number | null
  market_price?: number | null
  market_value?: number | null
  pnl?: number | null
  pnl_amount?: number | null
  pnl_pct?: number | null
  status?: string
  action?: string
  status_note?: string
  action_note?: string
}

export interface DashboardPayload {
  generated_at: string
  snapshot_slot: string
  strategy: string
  account_series: AccountSnapshot[]
  positions_latest: PositionRow[]
  selection_latest: {
    trade_date: string | null
    count: number
    rows: Record<string, unknown>[]
  }
  selection_resolve: {
    trade_date?: string
    source?: string
    count?: number
    top5?: Record<string, unknown>[]
    error?: string
  }
  sop_review: {
    header: Record<string, unknown>
    items: Record<string, unknown>[]
  } | null
}

export interface MonitorRule {
  id: string | number
  source?: string
  ts_code?: string
  code?: string
  name?: string
  rule_type?: string
  type?: string
  threshold?: number
  note?: string
  message?: string
  enabled?: boolean | number
}

export interface MonitorFiredDetail {
  id: string
  name?: string
  ts_code?: string
  source?: string
  rule_type?: string
  note?: string
}

export interface MonitorState {
  date: string
  fired: string[]
  fired_details?: MonitorFiredDetail[]
  exists?: boolean
}

export interface MonitorHistoryDay {
  date: string
  fired_count: number
  fired: string[]
}

export interface DisciplineAlert {
  level: 'danger' | 'warn' | 'info'
  title: string
  message: string
  code?: string | null
}

export interface DisciplinePayload {
  position_ratio: number | null
  alerts: DisciplineAlert[]
  positions_count: number
  as_of: string
}

export interface PortfolioHistory {
  snapshot_slot: string
  series: AccountSnapshot[]
  dates: string[]
}

export interface DailyBar {
  trade_date: string
  open?: number | null
  high?: number | null
  low?: number | null
  close?: number | null
  pct_chg?: number | null
  vol?: number | null
  amount?: number | null
}

export interface SelectionKline {
  code: string
  trade_date: string
  kline_end_date?: string
  days: number
  count: number
  bars: DailyBar[]
}

export interface SelectionHistory {
  strategy: string
  trade_date: string
  count: number
  rows: Record<string, unknown>[]
  sop_review: {
    header: Record<string, unknown>
    items: Record<string, unknown>[]
  } | null
  holding_codes?: string[]
}

export interface LaunchdJob {
  label: string
  entry: string
  schedule: string
  loaded: boolean
  stdout?: string
  stderr?: string
}
