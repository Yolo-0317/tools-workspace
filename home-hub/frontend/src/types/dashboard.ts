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

export interface AdvisorWeeklyTask {
  title: string
  detail: string
}

export interface AdvisorDiagnosisIssue {
  severity: string
  title: string
  detail: string
}

export interface AdvisorDiagnosis {
  health_score: number
  health_label: string
  issues?: AdvisorDiagnosisIssue[]
  concentration?: {
    holding_count?: number
    max_single_code?: string | null
    max_single_name?: string | null
    max_single_pct?: number | null
    power_sector_pct?: number
    top3?: { code: string; name: string; weight_pct: number; pnl?: number | null }[]
  }
  allocation_gap?: {
    phase?: number
    current_position_pct?: number
    target_position_pct?: number
    position_gap_pp?: number
    current_cash_pct?: number
    target_cash_pct_min?: number
  }
  risk_budget?: {
    max_loss_per_trade_pct?: number
    max_loss_per_trade_cny?: number
    worst_holding_code?: string | null
    worst_holding_loss_cny?: number
    within_budget?: boolean
  }
  education_tip?: string
  rebalance_priority?: string[]
}

export interface AdvisorPayload {
  principal_cny: number
  phase: number
  phase_label: string
  banner: string
  market_tier: string
  position_tier: string
  total_assets: number | null
  position_ratio_pct: number | null
  holding_pnl: number | null
  available_cash: number | null
  gap_to_principal: number
  progress_pct: number
  need_return_pct: number
  selection: {
    mode: string
    mode_label: string
    sop_top5_enabled: boolean
    watch_sync_enabled: boolean
  }
  weekly_must_do: AdvisorWeeklyTask[]
  weekly_forbidden: string[]
  focus_codes: { code: string; name: string; priority: string }[]
  diagnosis?: AdvisorDiagnosis
  delivery_template?: string
  weekly_review_latest?: AdvisorWeeklyReview | null
  error?: string
}

export interface AdvisorWeeklyReview {
  week_end_date: string
  phase: number
  title: string
  health_score: number | null
  report_md: string
  week_stats?: Record<string, unknown> | null
  ai_summary?: string | null
  created_at?: string | null
}

export interface DashboardPayload {
  generated_at: string
  snapshot_slot: string
  strategy: string
  advisor?: AdvisorPayload | null
  account_series: AccountSnapshot[]
  /** MySQL portfolio_account 当前态（优先于 eod 快照展示） */
  account_current?: AccountSnapshot | null
  positions_live?: PositionRow[]
  positions_source?: string
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
  threshold?: number | string
  note?: string
  message?: string
  enabled?: boolean | number
  current_price?: number | null
  change_pct?: number | null
  triggered_now?: boolean | null
  fired_today?: boolean
  fired_message?: string
  fired_at?: string
  fired_price?: number | null
  note_live?: string
}

export interface MonitorFiredDetail {
  id: string
  name?: string
  ts_code?: string
  source?: string
  rule_type?: string
  note?: string
  fired_at?: string
  fired_price?: number | null
  change_pct?: number | null
  suspect?: boolean
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

export interface ExecutionCardBuyHint {
  code: string
  name: string
  kind: 'probe_buy' | 'trim'
  priority?: string
  trigger?: string
  shares?: string
  stop?: string
  action?: string
  strategy?: string
  score?: string
  status?: string
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
  account_position_pct?: number | null
  execution_card_buys?: ExecutionCardBuyHint[]
  advisor?: AdvisorPayload | null
}

export interface LaunchdJob {
  label: string
  /** 看板短标题（中文） */
  title?: string
  /** 一句话说明 */
  description?: string
  entry: string
  schedule: string
  loaded: boolean
  stdout?: string
  stderr?: string
}

export type NewsSentiment = 'bullish' | 'bearish' | 'neutral'

export interface NewsItem {
  id: number
  href: string
  title: string
  summary: string
  news_time: string
  published_at: string | null
  category: 'geo' | 'domestic' | 'other'
  sentiment: NewsSentiment
  source: string
  fetched_at: string | null
  last_seen_at: string | null
}

export interface NewsMeta {
  ok: boolean
  date?: string
  total_today?: number
  counts?: Record<string, number>
  sentiment_counts?: Record<string, number>
  last_fetch?: {
    started_at: string | null
    finished_at: string | null
    item_count: number
    new_count: number
    ok: boolean
    error_msg: string | null
  }
  error?: string
}

export interface BriefingSnapshot {
  briefing_date: string
  slot: string
  title: string
  raw_text: string
  ai_summary: string
  created_at: string | null
}

export interface EmotionCycleHeader {
  trade_date?: string
  checklist_slot?: string
  limit_up_count?: number | null
  limit_down_count?: number | null
  up_down_ratio?: string | null
  max_board_height?: number | null
  limit_up_premium_pct?: number | null
  explode_rate_pct?: number | null
  total_amount_yi?: number | null
  theme_count?: number | null
  phase?: string | null
  phase_vs_yesterday?: string | null
  position_cap_pct?: number | null
  allow_new_open?: number | boolean | null
  main_theme?: string | null
  main_theme_is_new?: number | boolean | null
  drain_market?: number | boolean | null
  action_summary?: string | null
  tomorrow_phase?: string | null
  tomorrow_position_cap_pct?: number | null
  tomorrow_plan?: string | null
  exclude_list?: string | null
  review_notes?: string | null
  updated_at?: string | null
}

export interface EmotionDragonItem {
  rank_no?: number
  ts_code?: string
  name?: string
  board_height?: number | null
  main_theme?: string | null
  checklist_pass?: number | null
  notes?: string | null
}

export interface EmotionCycleRecord {
  header: EmotionCycleHeader
  dragon_items: EmotionDragonItem[]
}

export interface EmotionCyclePayload {
  dates: string[]
  default_date?: string | null
  trade_date: string | null
  checklist_slot?: string | null
  record: EmotionCycleRecord | null
  pre_market?: EmotionCycleRecord | null
  intraday?: EmotionCycleRecord | null
  eod?: EmotionCycleRecord | null
  data_source?: {
    kind: string
    tables: string[]
    schedule: string
  }
  dragon_execution_card?: DragonExecutionCard | null
}

export interface DragonExecutionCard {
  scope: string
  title: string
  mysql_tables: string[]
  schedule: string
  p0_gate: string
  operation?: string | null
  position_cap_pct?: number | null
  allow_new_open?: boolean
  allow_buy?: boolean
  force_exit?: boolean
  exclude_list?: string | null
  main_theme?: string | null
  conflict_note?: string
}
