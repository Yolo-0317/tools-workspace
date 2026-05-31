import type { PositionRow } from '../types/dashboard'

export function posCode(p: PositionRow): string {
  return String(p.ts_code ?? p.code ?? '')
}

export function posPrice(p: PositionRow): number | null {
  const v = p.market_price ?? p.current_price
  if (v === null || v === undefined) return null
  const n = Number(v)
  return Number.isNaN(n) ? null : n
}

export function posCost(p: PositionRow): number | null {
  const v = p.cost_price ?? p.cost
  if (v === null || v === undefined) return null
  const n = Number(v)
  return Number.isNaN(n) ? null : n
}

export function posPnl(p: PositionRow): number | null {
  const v = p.pnl_amount ?? p.pnl
  if (v === null || v === undefined) return null
  const n = Number(v)
  return Number.isNaN(n) ? null : n
}

export function posPnlPct(p: PositionRow): number | null {
  const v = p.pnl_pct
  if (v === null || v === undefined) return null
  const n = Number(v)
  return Number.isNaN(n) ? null : n
}
