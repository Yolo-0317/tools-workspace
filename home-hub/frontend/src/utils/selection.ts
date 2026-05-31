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
  return `${n >= 0 ? '+' : ''}${n.toFixed(2)}%`
}

export function selPctTone(row: Record<string, unknown>): 'up' | 'down' | 'flat' {
  const v = row['涨幅%'] ?? row.pct_chg ?? row.change_pct
  const n = Number(v)
  if (Number.isNaN(n) || v === null || v === undefined || v === '') return 'flat'
  if (n > 0) return 'up'
  if (n < 0) return 'down'
  return 'flat'
}

export function selAction(row: Record<string, unknown>): string {
  return String(row['建议动作'] ?? row.action_hint ?? '')
}

export function selIndustry(row: Record<string, unknown>): string {
  const v = row['所属行业'] ?? row.industry
  if (v === null || v === undefined || v === '') return '—'
  return String(v)
}

export function selConcepts(row: Record<string, unknown>): string {
  const concepts = row['概念板块']
  if (Array.isArray(concepts) && concepts.length) {
    return concepts.map(String).join('、')
  }
  const text = row['概念板块文本']
  if (text) return String(text)
  return '—'
}

export function selProfile(row: Record<string, unknown>): string {
  return String(row['公司简介'] ?? row.profile_text ?? '')
}

export function selConceptList(row: Record<string, unknown>): string[] {
  const concepts = row['概念板块']
  if (Array.isArray(concepts) && concepts.length) {
    return concepts.map(String).filter(Boolean)
  }
  const text = row['概念板块文本']
  if (text) {
    return String(text)
      .split(/[、,，]/)
      .map((s) => s.trim())
      .filter(Boolean)
  }
  return []
}

export interface SelectionProfileView {
  industryBackground: string
  coreCompetence: string
  sectorPath: string[]
  region: string
  selectionReason: string
  businessScope: string
  mainBusiness: string
  conceptTags: string[]
  hasContent: boolean
}

function extractLabeledSection(text: string, label: string): string {
  const re = new RegExp(`${label}[：:]\\s*([\\s\\S]*?)(?=\\n\\n|$)`)
  const m = text.match(re)
  if (!m) return ''
  return m[1].trim().replace(/\n+/g, ' ')
}

function parseSectorBlock(text: string): { path: string[]; region: string } {
  const idx = text.indexOf('所属板块')
  const block = idx >= 0 ? text.slice(idx, idx + 600) : text
  const path: string[] = []
  for (const level of ['一级', '二级', '三级']) {
    const re = new RegExp(`${level}\\s*\\n\\s*([^\\n]+)`)
    const m = block.match(re)
    if (m?.[1]) path.push(m[1].trim())
  }
  const regionMatch = block.match(/地区\s*\n\s*([^\n]+)/)
  return { path, region: regionMatch?.[1]?.trim() ?? '' }
}

export function splitCommaItems(text: string): string[] {
  if (!text) return []
  return text
    .split(/[,，、]/)
    .map((s) => s.trim())
    .filter((s) => s.length >= 2 && s.length <= 48)
}

export function parseSelectionProfile(row: Record<string, unknown>): SelectionProfileView {
  const raw = selProfile(row)
  const { path, region } = parseSectorBlock(raw)
  const industryBackground =
    extractLabeledSection(raw, '行业背景') || (selIndustry(row) !== '—' ? selIndustry(row) : '')
  const coreCompetence = extractLabeledSection(raw, '核心竞争力')
  const selectionReason = extractLabeledSection(raw, '入选理由')
  const businessScope = extractLabeledSection(raw, '经营范围')
  const mainBusiness = extractLabeledSection(raw, '主营业务')
  const conceptTags = selConceptList(row)

  const hasContent = Boolean(
    industryBackground ||
      coreCompetence ||
      path.length ||
      region ||
      selectionReason ||
      businessScope ||
      mainBusiness ||
      conceptTags.length,
  )

  return {
    industryBackground,
    coreCompetence,
    sectorPath: path,
    region,
    selectionReason,
    businessScope,
    mainBusiness,
    conceptTags,
    hasContent,
  }
}
