/** 选股 raw_json 中英文字段兼容 */

export function selCode(row: Record<string, unknown>): string {
  return String(row['代码'] ?? row.ts_code ?? row.code ?? '')
}

export function selName(row: Record<string, unknown>): string {
  return String(row['名称'] ?? row.name ?? '—')
}

/** SOP 审查条目：优先中文名，避免展示 6 位代码占位 */
export function sopName(item: Record<string, unknown>): string {
  const code = String(item.code ?? item.ts_code ?? '')
    .split('.')[0]
    .padStart(6, '0')
  const name = String(item.name ?? '').trim()
  if (name && name !== code && !/^\d{6}$/.test(name)) return name
  return selName(item)
}

export function selScore(row: Record<string, unknown>): string | number {
  const v = row['总分'] ?? row.score ?? row.total_score
  return v === null || v === undefined ? '—' : (v as string | number)
}

export function selPct(row: Record<string, unknown>): string {
  const v = row['涨幅%'] ?? row.pct_chg ?? row.change_pct
  if (v === null || v === undefined || v === '') return '—'
  const n = Number(v)
  if (Number.isNaN(n)) return String(v)
  return `${n.toFixed(2)}%`
}

export function selAction(row: Record<string, unknown>): string {
  return String(row['建议动作'] ?? row.action_hint ?? '')
}
