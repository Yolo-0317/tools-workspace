/** 投顾周复盘 Markdown → 结构化块（看板渲染，非 v-html 原文） */

export interface WeeklyTagline {
  label: string
  value: string
}

export interface WeeklyListItem {
  text: string
  sub?: string[]
}

export interface WeeklyReviewSection {
  title: string
  taglines?: WeeklyTagline[]
  bullets?: string[]
  ordered?: WeeklyListItem[]
  quote?: string
  paragraphs?: string[]
}

function stripNoise(lines: string[]): string[] {
  return lines.filter((line, idx) => {
    const t = line.trim()
    if (idx === 0 && /^#\s/.test(t)) return false
    if (/^\*\*复盘日\*\*/.test(t)) return false
    return true
  })
}

function parseTagline(line: string): WeeklyTagline | null {
  const m = line.trim().match(/^【([^】]+)】(.*)$/)
  if (!m) return null
  return { label: m[1], value: m[2].trim() }
}

function stripInlineMd(text: string): string {
  return text.replace(/\*\*(.+?)\*\*/g, '$1').trim()
}

function parseOrderedItem(line: string): WeeklyListItem | null {
  const m = line.trim().match(/^\d+\.\s+(.+)$/)
  if (!m) return null
  return { text: m[1].trim() }
}

function parseSectionBody(lines: string[]): Omit<WeeklyReviewSection, 'title'> {
  const taglines: WeeklyTagline[] = []
  const bullets: string[] = []
  const ordered: WeeklyListItem[] = []
  const paragraphs: string[] = []
  let quote = ''
  let current: WeeklyListItem | null = null

  for (const raw of lines) {
    const line = raw.trimEnd()
    const t = line.trim()
    if (!t) continue

    const tag = parseTagline(t)
    if (tag) {
      taglines.push(tag)
      current = null
      continue
    }

    if (t.startsWith('> ')) {
      quote = t.slice(2).trim()
      current = null
      continue
    }

    if (current && /^\s+- /.test(raw)) {
      const sub = raw.trim().replace(/^-\s+/, '')
      current.sub = current.sub ?? []
      current.sub.push(sub)
      continue
    }

    if (t.startsWith('- ')) {
      bullets.push(t.slice(2).trim())
      current = null
      continue
    }

    const ord = parseOrderedItem(t)
    if (ord) {
      ordered.push(ord)
      current = ord
      continue
    }

    paragraphs.push(t)
    current = null
  }

  const out: Omit<WeeklyReviewSection, 'title'> = {}
  if (taglines.length) out.taglines = taglines
  if (bullets.length) out.bullets = bullets
  if (ordered.length) out.ordered = ordered
  if (quote) out.quote = quote
  if (paragraphs.length) out.paragraphs = paragraphs
  return out
}

export function parseWeeklyReviewMarkdown(md: string): WeeklyReviewSection[] {
  const lines = stripNoise(md.replace(/\r\n/g, '\n').split('\n'))
  const sections: WeeklyReviewSection[] = []
  let currentTitle = ''
  let body: string[] = []

  const flush = () => {
    if (!currentTitle && body.length === 0) return
    if (!currentTitle) return
    sections.push({ title: currentTitle, ...parseSectionBody(body) })
    body = []
  }

  for (const line of lines) {
    const h2 = line.match(/^##\s+(.+)$/)
    if (h2) {
      flush()
      currentTitle = h2[1].trim()
      continue
    }
    if (currentTitle) body.push(line)
  }
  flush()
  return sections
}

export function splitInlineBold(text: string): Array<{ bold: boolean; text: string }> {
  const parts: Array<{ bold: boolean; text: string }> = []
  const re = /\*\*(.+?)\*\*/g
  let last = 0
  let m: RegExpExecArray | null
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) parts.push({ bold: false, text: text.slice(last, m.index) })
    parts.push({ bold: true, text: m[1] })
    last = m.index + m[0].length
  }
  if (last < text.length) parts.push({ bold: false, text: text.slice(last) })
  if (!parts.length) parts.push({ bold: false, text })
  return parts
}

export { stripInlineMd }
