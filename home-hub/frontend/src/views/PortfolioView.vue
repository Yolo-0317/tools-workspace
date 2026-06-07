<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import AdvisorPanel from '../components/AdvisorPanel.vue'
import DashboardLoadingSkeleton from '../components/DashboardLoadingSkeleton.vue'
import DisciplinePanel from '../components/DisciplinePanel.vue'
import MiniLineChart from '../components/MiniLineChart.vue'
import PortfolioPositionCard from '../components/PortfolioPositionCard.vue'
import { usePlatformLayout } from '../composables/usePlatformLayout'
import {
  fetchDashboardSummary,
  fetchDiscipline,
  fetchPortfolioHistory,
  fetchPortfolioSnapshot,
  fmtNum,
  fmtRatioPct,
} from '../api/dashboard'
import type {
  AccountSnapshot,
  AdvisorPayload,
  DisciplinePayload,
  PositionRow,
} from '../types/dashboard'
import { posCode, posCost, posPnl, posPrice } from '../utils/portfolio'

const positions = ref<PositionRow[]>([])
const account = ref<Record<string, unknown>>({})
const series = ref<AccountSnapshot[]>([])
const snapshotDates = ref<string[]>([])
const LIVE_SNAP = '__live__'
const selectedSnapDate = ref(LIVE_SNAP)
const livePositions = ref<PositionRow[]>([])
const discipline = ref<DisciplinePayload | null>(null)
const advisor = ref<AdvisorPayload | null>(null)
const error = ref('')
const loading = ref(true)

const isMobile = usePlatformLayout()

const assetChart = computed(() =>
  series.value
    .filter((s) => s.total_assets != null)
    .map((s) => ({ x: String(s.snapshot_date), y: Number(s.total_assets) })),
)

const pnlChart = computed(() =>
  series.value
    .filter((s) => s.holding_pnl != null)
    .map((s) => ({ x: String(s.snapshot_date), y: Number(s.holding_pnl) })),
)

const positionCount = computed(() => positions.value.length)

async function loadSnapshot(date: string) {
  if (!date) return
  if (date === LIVE_SNAP) {
    positions.value = livePositions.value
    return
  }
  try {
    const snap = await fetchPortfolioSnapshot(date)
    positions.value = snap.positions
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  }
}

watch(selectedSnapDate, (d) => {
  if (d) loadSnapshot(d)
})

onMounted(async () => {
  try {
    const [summary, history, disc] = await Promise.all([
      fetchDashboardSummary('eod', true),
      fetchPortfolioHistory(90),
      fetchDiscipline(),
    ])
    account.value = (summary.account_current ?? {}) as Record<string, unknown>
    livePositions.value = (summary.positions_live ?? []) as PositionRow[]
    advisor.value = summary.advisor ?? null
    discipline.value = disc
    series.value = history.series.length ? history.series : summary.account_series
    const histDates = history.dates.length
      ? history.dates
      : summary.account_series.map((s) => String(s.snapshot_date)).reverse()
    snapshotDates.value = [LIVE_SNAP, ...histDates]

    selectedSnapDate.value = LIVE_SNAP
    positions.value = livePositions.value
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="page" :class="{ mobile: isMobile }">
    <header class="head">
      <h1>持仓</h1>
      <p v-if="!loading && positionCount" class="sub">
        {{ positionCount }} 只
        <span v-if="selectedSnapDate === LIVE_SNAP"> · 实时</span>
        <span v-else-if="selectedSnapDate"> · 快照 {{ selectedSnapDate }}</span>
      </p>
    </header>

    <DashboardLoadingSkeleton v-if="loading" variant="portfolio" label="加载持仓" />
    <p v-if="error" class="error">{{ error }}</p>

    <AdvisorPanel v-if="!loading && advisor" :advisor="advisor" compact />

    <DisciplinePanel
      v-if="discipline"
      class="disc-block"
      :alerts="discipline.alerts"
      :position-ratio="discipline.position_ratio"
    />

    <section v-if="account.total_assets != null" class="stats-grid">
      <article class="stat-card highlight">
        <span class="stat-label">总资产</span>
        <span class="stat-value">¥{{ fmtNum(account.total_assets) }}</span>
      </article>
      <article class="stat-card">
        <span class="stat-label">可用资金</span>
        <span class="stat-value">¥{{ fmtNum(account.available_cash) }}</span>
      </article>
      <article class="stat-card">
        <span class="stat-label">仓位</span>
        <span class="stat-value">{{ fmtRatioPct(account.position_ratio) }}</span>
      </article>
      <article class="stat-card">
        <span class="stat-label">证券市值</span>
        <span class="stat-value">¥{{ fmtNum(account.market_value) }}</span>
      </article>
    </section>

    <div v-if="snapshotDates.length" class="filter-bar">
      <label class="filter-field filter-field-grow">
        <span class="filter-label">快照日期</span>
        <select v-model="selectedSnapDate" class="filter-select">
          <option v-for="d in snapshotDates" :key="d" :value="d">
            {{ d === LIVE_SNAP ? '实时（MySQL）' : d }}
          </option>
        </select>
      </label>
    </div>

    <section v-if="positionCount" class="positions-section">
      <h2 class="section-title">持仓明细</h2>

      <div v-if="isMobile" class="mobile-list">
        <PortfolioPositionCard
          v-for="(p, i) in positions"
          :key="`${posCode(p)}-${i}`"
          :position="p"
        />
      </div>

      <div v-else class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>代码</th>
              <th>名称</th>
              <th>股数</th>
              <th>成本</th>
              <th>现价</th>
              <th>盈亏</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(p, i) in positions" :key="i">
              <td>{{ posCode(p) }}</td>
              <td>{{ p.name }}</td>
              <td>{{ p.shares }}</td>
              <td>{{ fmtNum(posCost(p)) }}</td>
              <td>{{ fmtNum(posPrice(p)) }}</td>
              <td :class="{ up: Number(posPnl(p)) > 0, down: Number(posPnl(p)) < 0 }">
                {{ fmtNum(posPnl(p)) }}
              </td>
              <td class="action">{{ p.action ?? p.action_note ?? '—' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <p v-else-if="!loading && !error" class="hint">暂无持仓数据</p>

    <section v-if="assetChart.length >= 2" class="block">
      <h2>总资产趋势（{{ series.length }} 天）</h2>
      <MiniLineChart :points="assetChart" label="总资产（元）" />
    </section>

    <section v-if="pnlChart.length >= 2" class="block">
      <h2>持仓浮盈趋势</h2>
      <MiniLineChart :points="pnlChart" label="浮盈（元）" />
    </section>
  </div>
</template>

<style scoped>
.page h1 {
  margin: 0;
  font-size: 22px;
}

.head {
  margin-bottom: 12px;
}

.sub {
  margin: 4px 0 0;
  color: #8b9cb3;
  font-size: 13px;
}

.disc-block {
  margin-bottom: 16px;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin-bottom: 16px;
}

.stat-card {
  padding: 12px 14px;
  border-radius: 12px;
  background: #121820;
  border: 1px solid #243041;
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.stat-card.highlight {
  border-color: #1e3a5f;
  background: linear-gradient(145deg, #121820 0%, #152238 100%);
}

.stat-label {
  font-size: 11px;
  color: #7d8da6;
  letter-spacing: 0.04em;
}

.stat-value {
  font-size: 17px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  line-height: 1.2;
}

.filter-bar {
  display: flex;
  gap: 10px;
  margin-bottom: 16px;
  padding: 12px;
  border-radius: 12px;
  background: #121820;
  border: 1px solid #243041;
}

.filter-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}

.filter-field-grow {
  flex: 1;
}

.filter-label {
  font-size: 11px;
  color: #7d8da6;
  letter-spacing: 0.04em;
}

.filter-select {
  width: 100%;
  background: #0f1419;
  color: #e7ecf3;
  border: 1px solid #243041;
  border-radius: 8px;
  padding: 10px 12px;
  font-size: 15px;
  min-height: 44px;
}

.positions-section {
  margin-bottom: 20px;
}

.section-title {
  margin: 0 0 12px;
  font-size: 14px;
  color: #8b9cb3;
  font-weight: 600;
}

.mobile-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.table-wrap {
  overflow-x: auto;
  border: 1px solid #243041;
  border-radius: 12px;
}

table {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
}

th,
td {
  padding: 10px 12px;
  border-bottom: 1px solid #243041;
  text-align: left;
}

th {
  color: #8b9cb3;
  font-weight: 600;
  background: #0b1016;
}

.up {
  color: #7dffb2;
}

.down {
  color: #ff8f8f;
}

.action {
  max-width: 220px;
  font-size: 12px;
  color: #dbe7ff;
}

.block {
  margin-top: 20px;
  background: #121820;
  border: 1px solid #243041;
  border-radius: 12px;
  padding: 16px;
}

.block h2 {
  margin: 0 0 12px;
  font-size: 14px;
  color: #8b9cb3;
}

.hint {
  color: #8b9cb3;
}

.error {
  color: #ff8f8f;
}

/* H5 */
.page.mobile .head {
  margin-bottom: 10px;
}

.page.mobile h1 {
  font-size: 20px;
}

.page.mobile .stats-grid {
  gap: 8px;
  margin-bottom: 14px;
}

.page.mobile .stat-card {
  padding: 10px 12px;
}

.page.mobile .stat-value {
  font-size: 16px;
}

.page.mobile .filter-bar {
  position: sticky;
  top: 0;
  z-index: 20;
  margin-bottom: 14px;
  padding: 10px;
  background: rgba(18, 24, 32, 0.96);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
}

.page.mobile .filter-select {
  font-size: 16px;
}

.page.mobile .section-title {
  font-size: 13px;
  margin-bottom: 10px;
}

.page.mobile .block {
  padding: 12px;
  margin-top: 16px;
}

@media (min-width: 900px) {
  .stats-grid {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }
}
</style>
