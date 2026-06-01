<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import DisciplinePanel from '../components/DisciplinePanel.vue'
import MiniLineChart from '../components/MiniLineChart.vue'
import { usePlatformLayout } from '../composables/usePlatformLayout'
import {
  fetchDashboardSummary,
  fetchDiscipline,
  fetchSnapshotAlerts,
  fmtNum,
} from '../api/dashboard'
import type { DashboardPayload, DisciplinePayload } from '../types/dashboard'
import { selCode, selName, selScore } from '../utils/selection'

const data = ref<DashboardPayload | null>(null)
const discipline = ref<DisciplinePayload | null>(null)
const alerts = ref<string[]>([])
const error = ref('')
const loading = ref(true)
const isMobile = usePlatformLayout()

const assetChart = computed(() =>
  (data.value?.account_series ?? [])
    .filter((s) => s.total_assets != null)
    .map((s) => ({
      x: String(s.snapshot_date),
      y: Number(s.total_assets),
    })),
)

onMounted(async () => {
  try {
    const [summary, alertRes, disc] = await Promise.all([
      fetchDashboardSummary(),
      fetchSnapshotAlerts(10),
      fetchDiscipline(),
    ])
    data.value = summary
    alerts.value = alertRes.lines
    discipline.value = disc
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="page" :class="{ mobile: isMobile }">
    <h1>投资总览</h1>
    <p v-if="loading" class="hint">加载中…</p>
    <p v-if="error" class="error">{{ error }}</p>

    <DisciplinePanel
      v-if="discipline"
      class="disc-block"
      :alerts="discipline.alerts"
      :position-ratio="discipline.position_ratio"
    />

    <section v-if="data" class="cards">
      <article class="card">
        <h2>账户（{{ data.snapshot_slot }}）</h2>
        <template v-if="data.account_series.length">
          <p class="big">
            ¥{{ fmtNum(data.account_series.at(-1)?.total_assets, 2) }}
          </p>
          <p class="sub">
            市值 {{ fmtNum(data.account_series.at(-1)?.market_value) }}
            · 浮盈 {{ fmtNum(data.account_series.at(-1)?.holding_pnl) }}
          </p>
        </template>
        <p v-else class="hint">暂无快照</p>
      </article>

      <article class="card">
        <h2>持仓</h2>
        <p class="big">{{ data.positions_latest.length }} 只</p>
        <p class="sub">最新快照日 {{ data.account_series.at(-1)?.snapshot_date ?? '—' }}</p>
      </article>

      <article class="card">
        <h2>选股 {{ data.strategy }}</h2>
        <p class="big">{{ data.selection_latest.count }} 条</p>
        <p class="sub">交易日 {{ data.selection_latest.trade_date ?? '—' }}</p>
      </article>

      <article class="card">
        <h2>SOP 审查</h2>
        <p class="big">{{ data.sop_review?.items?.length ?? 0 }} 项</p>
        <p class="sub">{{ data.sop_review?.header?.trade_date ?? '无记录' }}</p>
      </article>
    </section>

    <section v-if="assetChart.length >= 2" class="block">
      <h2>总资产趋势</h2>
      <MiniLineChart :points="assetChart" label="总资产（元）" />
    </section>

    <section v-if="data?.selection_resolve?.top5?.length" class="block">
      <h2>Top5 摘要</h2>
      <ul>
        <li v-for="(row, i) in data.selection_resolve.top5" :key="i">
          {{ selCode(row) }}
          <span v-if="selName(row) !== '—'"> {{ selName(row) }}</span>
          <span v-if="selScore(row) !== '—'"> · 分 {{ selScore(row) }}</span>
        </li>
      </ul>
    </section>

    <section v-if="alerts.length" class="block warn-block">
      <h2>快照告警</h2>
      <pre>{{ alerts.join('\n') }}</pre>
    </section>

    <p class="meta" v-if="data">更新 {{ data.generated_at }}</p>
  </div>
</template>

<style scoped>
.page h1 {
  margin: 0 0 16px;
  font-size: 22px;
}

.disc-block {
  margin-bottom: 16px;
}

.cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 12px;
}

.card {
  background: #121820;
  border: 1px solid #243041;
  border-radius: 12px;
  padding: 16px;
}

.card h2 {
  margin: 0 0 8px;
  font-size: 13px;
  color: #8b9cb3;
  font-weight: 600;
}

.big {
  margin: 0;
  font-size: 24px;
  font-weight: 700;
}

.sub,
.meta,
.hint {
  color: #8b9cb3;
  font-size: 13px;
}

.sub {
  margin: 6px 0 0;
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

.block ul {
  margin: 0;
  padding-left: 18px;
}

.warn-block pre {
  margin: 0;
  font-size: 12px;
  white-space: pre-wrap;
  color: #ffb4b4;
}

.error {
  color: #ff8f8f;
}

.page.mobile h1 {
  font-size: 20px;
  margin-bottom: 12px;
}

.page.mobile .cards {
  grid-template-columns: 1fr;
}

.page.mobile .big {
  font-size: 22px;
}

.page.mobile .block {
  padding: 14px;
}
</style>
