<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import DisciplinePanel from '../components/DisciplinePanel.vue'
import MiniLineChart from '../components/MiniLineChart.vue'
import {
  fetchDashboardSummary,
  fetchDiscipline,
  fetchPortfolioCurrent,
  fetchPortfolioHistory,
  fetchPortfolioSnapshot,
  fmtNum,
  fmtRatioPct,
} from '../api/dashboard'
import type { AccountSnapshot, DisciplinePayload, PositionRow } from '../types/dashboard'
import { posCode, posCost, posPnl, posPrice } from '../utils/portfolio'

const positions = ref<PositionRow[]>([])
const account = ref<Record<string, unknown>>({})
const series = ref<AccountSnapshot[]>([])
const snapshotDates = ref<string[]>([])
const selectedSnapDate = ref('')
const discipline = ref<DisciplinePayload | null>(null)
const error = ref('')
const loading = ref(true)

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

async function loadSnapshot(date: string) {
  if (!date) return
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
    const [current, summary, history, disc] = await Promise.all([
      fetchPortfolioCurrent(),
      fetchDashboardSummary(),
      fetchPortfolioHistory(90),
      fetchDiscipline(),
    ])
    account.value = current.account
    discipline.value = disc
    series.value = history.series.length ? history.series : summary.account_series
    snapshotDates.value = history.dates.length
      ? history.dates
      : summary.account_series.map((s) => String(s.snapshot_date)).reverse()

    selectedSnapDate.value = snapshotDates.value[0] ?? ''
    if (selectedSnapDate.value) {
      await loadSnapshot(selectedSnapDate.value)
    } else if (summary.positions_latest.length > 0) {
      positions.value = summary.positions_latest
    } else {
      positions.value = current.positions as PositionRow[]
    }
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="page">
    <h1>持仓</h1>
    <p v-if="loading" class="hint">加载中…</p>
    <p v-if="error" class="error">{{ error }}</p>

    <DisciplinePanel
      v-if="discipline"
      class="disc-block"
      :alerts="discipline.alerts"
      :position-ratio="discipline.position_ratio"
    />

    <section v-if="account.total_assets != null" class="summary">
      总资产 ¥{{ fmtNum(account.total_assets) }}
      · 可用 {{ fmtNum(account.available_cash) }}
      · 仓位 {{ fmtRatioPct(account.position_ratio) }}
    </section>

    <div class="head">
      <label v-if="snapshotDates.length">
        快照日
        <select v-model="selectedSnapDate">
          <option v-for="d in snapshotDates" :key="d" :value="d">{{ d }}</option>
        </select>
      </label>
    </div>

    <div class="table-wrap">
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

    <section v-if="assetChart.length >= 2" class="block">
      <h2>总资产趋势（{{ series.length }} 天）</h2>
      <MiniLineChart :points="assetChart" />
    </section>

    <section v-if="pnlChart.length >= 2" class="block">
      <h2>持仓浮盈趋势</h2>
      <MiniLineChart :points="pnlChart" />
    </section>
  </div>
</template>

<style scoped>
.page h1 {
  margin: 0 0 12px;
}

.disc-block {
  margin-bottom: 16px;
}

.summary {
  margin-bottom: 16px;
  color: #8b9cb3;
  font-size: 14px;
}

.head {
  margin-bottom: 12px;
}

.head label {
  font-size: 13px;
  color: #8b9cb3;
  display: flex;
  align-items: center;
  gap: 8px;
}

select {
  background: #121820;
  color: #e7ecf3;
  border: 1px solid #243041;
  border-radius: 8px;
  padding: 6px 10px;
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
</style>
