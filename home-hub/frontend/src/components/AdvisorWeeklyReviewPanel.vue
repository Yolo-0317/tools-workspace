<script setup lang="ts">
import { computed, ref } from 'vue'
import type { AdvisorWeeklyReview } from '../types/dashboard'
import {
  parseWeeklyReviewMarkdown,
  splitInlineBold,
  type WeeklyReviewSection,
} from '../utils/advisorWeeklyMarkdown'

const props = defineProps<{
  review: AdvisorWeeklyReview | null | undefined
  compact?: boolean
}>()

const expanded = ref(false)
const PREVIEW_SECTIONS = 2

const statsLine = computed(() => {
  const s = props.review?.week_stats
  if (!s || typeof s !== 'object' || s.note) return ''
  const delta = s.assets_delta
  const pct = s.assets_delta_pct
  if (delta == null) return ''
  const sign = Number(delta) >= 0 ? '+' : ''
  return `本周资产 ${sign}${delta} 元（${sign}${pct}%）`
})

const sections = computed(() => {
  const md = props.review?.report_md?.trim() ?? ''
  return md ? parseWeeklyReviewMarkdown(md) : []
})

const visibleSections = computed(() => {
  if (expanded.value) return sections.value
  return sections.value.slice(0, PREVIEW_SECTIONS)
})

const hasMore = computed(() => sections.value.length > PREVIEW_SECTIONS)

function sectionClass(sec: WeeklyReviewSection): string {
  if (sec.title.includes('交付摘要')) return 'delivery'
  if (sec.title.includes('必做对照')) return 'checklist'
  if (sec.title.includes('账户变化')) return 'stats-block'
  return ''
}
</script>

<template>
  <section v-if="review" class="weekly" :class="{ compact }">
    <header class="weekly-head">
      <div>
        <h2>周五周复盘</h2>
        <p class="meta">
          {{ review.week_end_date }}
          <span v-if="review.created_at"> · 生成 {{ review.created_at }}</span>
        </p>
      </div>
      <span v-if="review.health_score != null" class="health">
        健康 {{ review.health_score }}
      </span>
    </header>

    <p class="title">{{ review.title }}</p>
    <p v-if="statsLine" class="stats">{{ statsLine }}</p>

    <div v-if="review.ai_summary" class="ai-box">
      <p class="ai-label">投后陪伴</p>
      <p class="ai-body">{{ review.ai_summary }}</p>
    </div>

    <div v-if="visibleSections.length" class="report-body">
      <article
        v-for="(sec, si) in visibleSections"
        :key="si"
        class="report-section"
        :class="sectionClass(sec)"
      >
        <h3 class="sec-title">{{ sec.title }}</h3>

        <dl v-if="sec.taglines?.length" class="taglines">
          <div v-for="(row, ti) in sec.taglines" :key="ti" class="tagline-row">
            <dt>{{ row.label }}</dt>
            <dd>
              <template v-for="(p, pi) in splitInlineBold(row.value)" :key="pi">
                <strong v-if="p.bold">{{ p.text }}</strong>
                <template v-else>{{ p.text }}</template>
              </template>
            </dd>
          </div>
        </dl>

        <ul v-if="sec.bullets?.length" class="bullets">
          <li v-for="(b, bi) in sec.bullets" :key="bi">
            <template v-for="(p, pi) in splitInlineBold(b)" :key="pi">
              <strong v-if="p.bold">{{ p.text }}</strong>
              <template v-else>{{ p.text }}</template>
            </template>
          </li>
        </ul>

        <ol v-if="sec.ordered?.length" class="ordered">
          <li v-for="(item, oi) in sec.ordered" :key="oi">
            <p class="ord-main">
              <template v-for="(p, pi) in splitInlineBold(item.text)" :key="pi">
                <strong v-if="p.bold">{{ p.text }}</strong>
                <template v-else>{{ p.text }}</template>
              </template>
            </p>
            <ul v-if="item.sub?.length" class="ord-sub">
              <li v-for="(sub, sj) in item.sub" :key="sj">{{ sub }}</li>
            </ul>
          </li>
        </ol>

        <blockquote v-if="sec.quote" class="quote">{{ sec.quote }}</blockquote>

        <p v-for="(para, pi) in sec.paragraphs" :key="'p' + pi" class="para">
          <template v-for="(p, pj) in splitInlineBold(para)" :key="pj">
            <strong v-if="p.bold">{{ p.text }}</strong>
            <template v-else>{{ p.text }}</template>
          </template>
        </p>
      </article>
    </div>

    <button v-if="hasMore" type="button" class="toggle" @click="expanded = !expanded">
      {{ expanded ? '收起' : '展开全文' }}
    </button>
  </section>
</template>

<style scoped>
.weekly {
  margin-top: 16px;
  background: #121820;
  border: 1px solid #243041;
  border-radius: 12px;
  padding: 16px;
}

.weekly.compact {
  padding: 12px;
}

.weekly-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}

.weekly-head h2 {
  margin: 0;
  font-size: 14px;
  color: #8b9cb3;
  font-weight: 600;
}

.meta {
  margin: 4px 0 0;
  font-size: 12px;
  color: #6b7c93;
}

.health {
  flex-shrink: 0;
  font-size: 12px;
  font-weight: 600;
  color: #7dd3fc;
  background: rgba(56, 189, 248, 0.12);
  border-radius: 999px;
  padding: 4px 10px;
}

.title {
  margin: 12px 0 0;
  font-size: 15px;
  font-weight: 600;
}

.stats {
  margin: 6px 0 0;
  font-size: 13px;
  color: #a8b8cc;
}

.ai-box {
  margin-top: 12px;
  padding: 12px;
  border-radius: 8px;
  background: rgba(56, 189, 248, 0.06);
  border: 1px solid rgba(56, 189, 248, 0.15);
}

.ai-label {
  margin: 0 0 6px;
  font-size: 12px;
  color: #7dd3fc;
  font-weight: 600;
}

.ai-body {
  margin: 0;
  font-size: 14px;
  line-height: 1.6;
  white-space: pre-wrap;
}

.report-body {
  margin-top: 14px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.report-section {
  padding: 12px 14px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid #243041;
}

.report-section.delivery {
  background: linear-gradient(135deg, rgba(26, 35, 50, 0.9) 0%, rgba(21, 32, 43, 0.95) 100%);
  border-color: #2d3a4d;
}

.report-section.stats-block .bullets li {
  color: #d4deea;
}

.report-section.checklist .ordered {
  margin-top: 4px;
}

.sec-title {
  margin: 0 0 10px;
  font-size: 13px;
  font-weight: 600;
  color: #8b9cb3;
}

.taglines {
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.tagline-row {
  display: grid;
  grid-template-columns: minmax(88px, auto) 1fr;
  gap: 8px 12px;
  align-items: baseline;
  font-size: 13px;
  line-height: 1.5;
}

.tagline-row dt {
  margin: 0;
  color: #7dd3fc;
  font-weight: 600;
}

.tagline-row dd {
  margin: 0;
  color: #c5d0de;
}

.bullets,
.ordered,
.ord-sub {
  margin: 0;
  padding-left: 1.25rem;
}

.bullets li,
.ordered li {
  margin: 6px 0;
  font-size: 13px;
  line-height: 1.55;
  color: #c5d0de;
}

.ord-main {
  margin: 0;
}

.ord-sub {
  margin-top: 4px;
  list-style: disc;
  color: #8b9cb3;
  font-size: 12px;
}

.quote {
  margin: 10px 0 0;
  padding: 8px 12px;
  border-left: 3px solid #3d5166;
  background: rgba(0, 0, 0, 0.15);
  color: #8b9cb3;
  font-size: 12px;
  line-height: 1.5;
}

.para {
  margin: 8px 0 0;
  font-size: 13px;
  line-height: 1.55;
  color: #c5d0de;
}

.toggle {
  margin-top: 12px;
  padding: 0;
  border: none;
  background: none;
  color: #7dd3fc;
  font-size: 13px;
  cursor: pointer;
}
</style>
