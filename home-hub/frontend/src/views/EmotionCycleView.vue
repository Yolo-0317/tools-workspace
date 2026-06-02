<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'
import { fetchEmotionCycle, fetchEmotionCycleDates, fmtNum } from '../api/dashboard'
import { usePlatformLayout } from '../composables/usePlatformLayout'
import { shanghaiToday } from '../utils/date'
import type {
  DragonExecutionCard,
  EmotionCycleHeader,
  EmotionCyclePayload,
  EmotionCycleRecord,
  EmotionDragonItem,
} from '../types/dashboard'

const data = ref<EmotionCyclePayload | null>(null)
const dates = ref<string[]>([])
const selectedDate = ref('')
const selectedSlot = ref<'pre_market' | 'intraday' | 'eod'>('intraday')
const loading = ref(true)
const error = ref('')
const isMobile = usePlatformLayout()

const today = shanghaiToday()

const activeRecord = computed((): EmotionCycleRecord | null => {
  if (!data.value) return null
  if (data.value.intraday || data.value.pre_market || data.value.eod) {
    if (selectedSlot.value === 'intraday') return data.value.intraday ?? null
    if (selectedSlot.value === 'eod') return data.value.eod ?? null
    return data.value.pre_market ?? null
  }
  return data.value.record
})

const header = computed((): EmotionCycleHeader | null => activeRecord.value?.header ?? null)
const dragons = computed((): EmotionDragonItem[] => activeRecord.value?.dragon_items ?? [])
const execCard = computed((): DragonExecutionCard | null => data.value?.dragon_execution_card ?? null)
const dataSource = computed(() => data.value?.data_source)

const hasAnySlot = computed(
  () =>
    Boolean(data.value?.intraday)
    || Boolean(data.value?.pre_market)
    || Boolean(data.value?.eod),
)

const phaseClass = computed(() => {
  const phase = header.value?.phase
  if (!phase) return 'phase-unknown'
  const map: Record<string, string> = {
    冰点: 'phase-ice',
    启动: 'phase-start',
    发酵: 'phase-grow',
    高潮: 'phase-peak',
    分歧: 'phase-split',
    退潮: 'phase-ebb',
  }
  return map[phase] ?? 'phase-unknown'
})

function boolLabel(v: unknown): string {
  if (v === 1 || v === true) return '是'
  if (v === 0 || v === false) return '否'
  return '—'
}

function pctLabel(v: unknown): string {
  if (v === null || v === undefined || v === '') return '—'
  const n = Number(v)
  if (Number.isNaN(n)) return String(v)
  return `${n.toFixed(2)}%`
}

async function loadDates() {
  const res = await fetchEmotionCycleDates()
  dates.value = res.dates
  if (!selectedDate.value) {
    selectedDate.value = res.default_date ?? res.dates[0] ?? today
  }
}

async function loadData() {
  if (!selectedDate.value) {
    data.value = null
    return
  }
  loading.value = true
  error.value = ''
  try {
    data.value = await fetchEmotionCycle(selectedDate.value)
    if (data.value.intraday) selectedSlot.value = 'intraday'
    else if (data.value.pre_market && !data.value.eod) selectedSlot.value = 'pre_market'
    else if (data.value.eod && !data.value.pre_market) selectedSlot.value = 'eod'
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
    data.value = null
  } finally {
    loading.value = false
  }
}

watch(selectedDate, () => {
  void loadData()
})

onMounted(async () => {
  try {
    await loadDates()
    await loadData()
    refreshTimer = window.setInterval(() => {
      if (selectedSlot.value === 'intraday' && selectedDate.value === today) {
        void loadData()
      }
    }, 5 * 60 * 1000)
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
    loading.value = false
  }
})

let refreshTimer: number | undefined

onUnmounted(() => {
  if (refreshTimer) window.clearInterval(refreshTimer)
})
</script>

<template>
  <div class="page" :class="{ mobile: isMobile }">
    <header class="page-head">
      <div>
        <h1>情绪周期 · 龙头执行卡</h1>
        <p class="sub">
          MySQL 定时入库 · 仿真 emquant；实盘见
          <RouterLink to="/portfolio" class="inline-link">持仓执行卡</RouterLink>
        </p>
      </div>
      <div class="toolbar">
        <select v-model="selectedDate" class="select" aria-label="交易日">
          <option v-if="!dates.length" :value="today">{{ today }}</option>
          <option v-for="d in dates" :key="d" :value="d">{{ d }}</option>
        </select>
        <div v-if="hasAnySlot" class="slot-tabs">
          <button
            type="button"
            class="slot-btn"
            :class="{ active: selectedSlot === 'intraday' }"
            @click="selectedSlot = 'intraday'"
          >
            盘中
          </button>
          <button
            type="button"
            class="slot-btn"
            :class="{ active: selectedSlot === 'pre_market' }"
            @click="selectedSlot = 'pre_market'"
          >
            盘前
          </button>
          <button
            type="button"
            class="slot-btn"
            :class="{ active: selectedSlot === 'eod' }"
            @click="selectedSlot = 'eod'"
          >
            收盘
          </button>
        </div>
        <button type="button" class="refresh-btn" :disabled="loading" @click="loadData">
          刷新
        </button>
      </div>
    </header>

    <p v-if="loading" class="hint">加载中…</p>
    <p v-if="error" class="error">{{ error }}</p>

    <template v-if="!loading && header">
      <section v-if="execCard" class="block exec-card">
        <div class="exec-head">
          <h2>{{ execCard.title }}</h2>
          <span class="tag sim">仅仿真下单</span>
        </div>
        <p v-if="dataSource" class="source-line">
          数据源 {{ dataSource.tables.join(' + ') }} · {{ dataSource.schedule }}
          <span v-if="header?.updated_at"> · 更新 {{ header.updated_at }}</span>
        </p>
        <p class="p0-line">{{ execCard.p0_gate }}</p>
        <dl class="exec-dl">
          <div>
            <dt>今日操作</dt>
            <dd class="emph">{{ execCard.operation ?? '—' }}</dd>
          </div>
          <div>
            <dt>游资轨上限</dt>
            <dd>{{ pctLabel(execCard.position_cap_pct) }}</dd>
          </div>
          <div>
            <dt>允许新开</dt>
            <dd>{{ boolLabel(execCard.allow_new_open) }}</dd>
          </div>
          <div>
            <dt>仿真可买</dt>
            <dd :class="execCard.allow_buy ? 'ok' : 'no'">
              {{ execCard.allow_buy ? '是' : '否' }}
            </dd>
          </div>
          <div>
            <dt>阶段强制清仓</dt>
            <dd>{{ execCard.force_exit ? '是' : '否' }}</dd>
          </div>
          <div>
            <dt>主线</dt>
            <dd>{{ execCard.main_theme || '—' }}</dd>
          </div>
        </dl>
        <p v-if="execCard.exclude_list" class="exclude">
          不做：{{ execCard.exclude_list }}
        </p>
        <p class="conflict">{{ execCard.conflict_note }}</p>
      </section>

      <section class="hero">
        <div class="phase-badge" :class="phaseClass">
          {{ header.phase ?? '未判定' }}
        </div>
        <div class="hero-meta">
          <p class="hero-action">{{ header.action_summary ?? '—' }}</p>
          <p class="hero-sub">
            游资轨上限 {{ pctLabel(header.position_cap_pct) }}
            · 较昨日 {{ header.phase_vs_yesterday ?? '—' }}
            · 允许新开 {{ boolLabel(header.allow_new_open) }}
          </p>
        </div>
      </section>

      <section class="cards">
        <article class="card">
          <h2>涨跌停</h2>
          <p class="big">{{ header.limit_up_count ?? '—' }} / {{ header.limit_down_count ?? '—' }}</p>
          <p class="sub">涨停 / 跌停</p>
        </article>
        <article class="card">
          <h2>连板高度</h2>
          <p class="big">{{ header.max_board_height ?? '—' }}</p>
          <p class="sub">空间龙（板）</p>
        </article>
        <article class="card">
          <h2>昨日溢价</h2>
          <p class="big">{{ pctLabel(header.limit_up_premium_pct) }}</p>
          <p class="sub">&lt;1% 不打板</p>
        </article>
        <article class="card">
          <h2>炸板率</h2>
          <p class="big">{{ pctLabel(header.explode_rate_pct) }}</p>
          <p class="sub">≥40% 不接力</p>
        </article>
        <article class="card">
          <h2>成交额</h2>
          <p class="big">{{ fmtNum(header.total_amount_yi, 0) }}</p>
          <p class="sub">全 A（亿）</p>
        </article>
        <article class="card">
          <h2>题材数</h2>
          <p class="big">{{ header.theme_count ?? '—' }}</p>
          <p class="sub">&gt;3 切换快</p>
        </article>
      </section>

      <section class="block">
        <h2>主线</h2>
        <p class="theme-line">
          <strong>{{ header.main_theme || '—' }}</strong>
          <span v-if="header.main_theme_is_new != null" class="tag">
            {{ boolLabel(header.main_theme_is_new) === '是' ? '新题材' : '老题材' }}
          </span>
          <span v-if="header.drain_market != null && boolLabel(header.drain_market) === '是'" class="tag warn">
            抽水行情
          </span>
        </p>
        <p v-if="header.up_down_ratio" class="sub-line">涨跌家数比 {{ header.up_down_ratio }}</p>
        <p v-if="header.exclude_list" class="exclude">不做：{{ header.exclude_list }}</p>
      </section>

      <section v-if="dragons.length" class="block">
        <h2>龙头观察池（Top3）</h2>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>#</th>
                <th>代码</th>
                <th>名称</th>
                <th>板</th>
                <th>主线</th>
                <th>确认</th>
                <th>备注</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in dragons" :key="`${row.ts_code}-${row.rank_no}`">
                <td>{{ row.rank_no ?? '—' }}</td>
                <td>{{ row.ts_code ?? '—' }}</td>
                <td>{{ row.name ?? '—' }}</td>
                <td>{{ row.board_height ?? '—' }}</td>
                <td>{{ row.main_theme ?? '—' }}</td>
                <td>{{ row.checklist_pass != null ? `${row.checklist_pass}/7` : '—' }}</td>
                <td>{{ row.notes ?? '—' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section v-if="header.tomorrow_phase || header.tomorrow_plan" class="block plan-block">
        <h2>明日预案</h2>
        <p v-if="header.tomorrow_phase">
          阶段 {{ header.tomorrow_phase }}
          <span v-if="header.tomorrow_position_cap_pct != null">
            · 上限 {{ pctLabel(header.tomorrow_position_cap_pct) }}
          </span>
        </p>
        <p v-if="header.tomorrow_plan" class="plan-text">{{ header.tomorrow_plan }}</p>
      </section>

      <section v-if="header.review_notes" class="block">
        <h2>复盘备注</h2>
        <p class="plan-text">{{ header.review_notes }}</p>
      </section>

      <p v-if="header.updated_at" class="meta">更新 {{ header.updated_at }}</p>
    </template>

    <section v-else-if="!loading && !error" class="empty">
      <p>该日暂无日检记录。</p>
      <p class="hint">
        写入：<code>uv run python -m scripts.tools.emotion_cycle_checklist save -f …</code>
      </p>
    </section>
  </div>
</template>

<style scoped>
.inline-link {
  color: #93c5fd;
  text-decoration: none;
}

.inline-link:hover {
  text-decoration: underline;
}

.exec-card {
  border-color: #334155;
  background: linear-gradient(180deg, #151c28 0%, #121820 100%);
}

.exec-head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.exec-head h2 {
  margin: 0;
}

.tag.sim {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 999px;
  background: #422006;
  color: #fdba74;
}

.source-line {
  margin: 0 0 10px;
  font-size: 12px;
  color: #6b7c93;
}

.p0-line {
  margin: 0 0 12px;
  font-size: 14px;
  font-weight: 600;
  color: #e7ecf3;
}

.exec-dl {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 10px 16px;
  margin: 0;
}

.exec-dl dt {
  margin: 0;
  font-size: 11px;
  color: #8b9cb3;
}

.exec-dl dd {
  margin: 4px 0 0;
  font-size: 15px;
  font-weight: 600;
}

.exec-dl dd.emph {
  font-size: 18px;
  color: #fbbf24;
}

.exec-dl dd.ok {
  color: #86efac;
}

.exec-dl dd.no {
  color: #fca5a5;
}

.conflict {
  margin: 12px 0 0;
  font-size: 12px;
  color: #8b9cb3;
}

.page h1 {
  margin: 0;
  font-size: 22px;
}

.page-head {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
}

.sub {
  margin: 4px 0 0;
  font-size: 13px;
  color: #8b9cb3;
}

.toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.select {
  border: 1px solid #314158;
  background: #121820;
  color: #e7ecf3;
  border-radius: 8px;
  padding: 8px 10px;
  font-size: 14px;
}

.slot-tabs {
  display: flex;
  border: 1px solid #314158;
  border-radius: 8px;
  overflow: hidden;
}

.slot-btn {
  border: none;
  background: transparent;
  color: #8b9cb3;
  padding: 8px 12px;
  font-size: 13px;
  cursor: pointer;
}

.slot-btn.active {
  background: #2563eb;
  color: #fff;
}

.refresh-btn {
  border: 1px solid #314158;
  background: #1a2332;
  color: #e7ecf3;
  border-radius: 8px;
  padding: 8px 12px;
  font-size: 13px;
  cursor: pointer;
}

.refresh-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.hint {
  color: #8b9cb3;
}

.error {
  color: #f87171;
}

.hero {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 16px;
  margin-bottom: 16px;
  padding: 16px;
  border-radius: 12px;
  border: 1px solid #243041;
  background: #121820;
}

.phase-badge {
  font-size: 20px;
  font-weight: 700;
  padding: 10px 16px;
  border-radius: 10px;
  min-width: 72px;
  text-align: center;
}

.phase-ice { background: #1e3a5f; color: #93c5fd; }
.phase-start { background: #14532d; color: #86efac; }
.phase-grow { background: #166534; color: #bbf7d0; }
.phase-peak { background: #7c2d12; color: #fdba74; }
.phase-split { background: #713f12; color: #fde047; }
.phase-ebb { background: #450a0a; color: #fca5a5; }
.phase-unknown { background: #1e293b; color: #cbd5e1; }

.hero-action {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
}

.hero-sub {
  margin: 6px 0 0;
  font-size: 13px;
  color: #8b9cb3;
}

.cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}

.card {
  background: #121820;
  border: 1px solid #243041;
  border-radius: 12px;
  padding: 14px;
}

.card h2 {
  margin: 0 0 8px;
  font-size: 12px;
  font-weight: 600;
  color: #8b9cb3;
}

.big {
  margin: 0;
  font-size: 22px;
  font-weight: 700;
}

.block {
  margin-bottom: 16px;
  padding: 16px;
  border-radius: 12px;
  border: 1px solid #243041;
  background: #121820;
}

.block h2 {
  margin: 0 0 10px;
  font-size: 15px;
}

.theme-line {
  margin: 0;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.tag {
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 999px;
  background: #1e3a5f;
  color: #93c5fd;
}

.tag.warn {
  background: #451a03;
  color: #fdba74;
}

.sub-line, .exclude {
  margin: 8px 0 0;
  font-size: 13px;
  color: #8b9cb3;
}

.exclude {
  color: #fca5a5;
}

.table-wrap {
  overflow-x: auto;
}

table {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
}

th, td {
  padding: 8px 10px;
  text-align: left;
  border-bottom: 1px solid #243041;
}

th {
  color: #8b9cb3;
  font-weight: 600;
  font-size: 12px;
}

.plan-text {
  margin: 0;
  white-space: pre-wrap;
  line-height: 1.5;
}

.plan-block p {
  margin: 0 0 8px;
}

.meta {
  font-size: 12px;
  color: #6b7c93;
}

.empty {
  padding: 24px;
  text-align: center;
  color: #8b9cb3;
}

.empty code {
  font-size: 12px;
  color: #cbd5e1;
}

.page.mobile .cards {
  grid-template-columns: repeat(2, 1fr);
}

.page.mobile .big {
  font-size: 18px;
}
</style>
