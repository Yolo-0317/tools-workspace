<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import DashboardLoadingSkeleton from '../components/DashboardLoadingSkeleton.vue'
import MiniLineChart from '../components/MiniLineChart.vue'
import PortfolioWorkbenchPanel from '../components/PortfolioWorkbenchPanel.vue'
import { usePlatformLayout } from '../composables/usePlatformLayout'
import {
  fetchDashboardSummary,
  fetchPortfolioWorkbench,
  fetchSnapshotAlerts,
  fmtNum,
} from '../api/dashboard'
import type { DashboardPayload, PortfolioWorkbench } from '../types/dashboard'
import { selCode, selName, selScore, strategyLabel } from '../utils/selection'

const data = ref<DashboardPayload | null>(null)
const workbench = ref<PortfolioWorkbench | null>(null)
const alerts = ref<string[]>([])
const error = ref('')
const loading = ref(true)
const isMobile = usePlatformLayout()

const latestAccount = computed(() => {
  if (workbench.value?.account.total_assets != null) {
    return {
      total_assets: workbench.value.account.total_assets,
      market_value: workbench.value.account.market_value,
      holding_pnl: workbench.value.account.holding_pnl,
      snapshot_date: workbench.value.as_of,
    }
  }
  const cur = data.value?.account_current
  if (cur?.total_assets != null) return cur
  return data.value?.account_series.at(-1) ?? null
})

const assetChart = computed(() =>
  (data.value?.account_series ?? [])
    .filter((s) => s.total_assets != null)
    .map((s) => ({
      x: String(s.snapshot_date),
      y: Number(s.total_assets),
    })),
)

async function loadSecondaryData() {
  try {
    const [summary, alertRes] = await Promise.all([
      fetchDashboardSummary(),
      fetchSnapshotAlerts(10),
    ])
    data.value = summary
    alerts.value = alertRes.lines
  } catch {}
}

onMounted(async () => {
  try {
    workbench.value = await fetchPortfolioWorkbench()
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    loading.value = false
  }
  void loadSecondaryData()
})
</script>

<template>
  <div class="page" :class="{ mobile: isMobile }">
    <h1>投顾总览</h1>
    <DashboardLoadingSkeleton v-if="loading" variant="home" />
    <p v-if="error" class="error">{{ error }}</p>

    <PortfolioWorkbenchPanel v-if="!loading && workbench" :workbench="workbench" />

    <section v-if="data" class="cards">
      <article class="card">
        <h2>账户（实时）</h2>
        <template v-if="latestAccount">
          <p class="big">¥{{ fmtNum(latestAccount.total_assets, 2) }}</p>
          <p class="sub">
            市值 {{ fmtNum(latestAccount.market_value) }}
            · 浮盈 {{ fmtNum(latestAccount.holding_pnl) }}
            · {{ latestAccount.snapshot_date ?? '—' }}
          </p>
        </template>
        <p v-else class="hint">暂无账户数据</p>
      </article>

      <article class="card">
        <h2>持仓</h2>
        <p class="big">{{ workbench?.positions.length ?? data.positions_latest.length }} 只</p>
        <p class="sub">
          {{ workbench ? '执行卡快照（券商页已核对）' : 'MySQL 同步数据' }}
        </p>
      </article>

      <article class="card">
        <h2>选股 {{ strategyLabel(data.strategy) }}</h2>
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
      <h2>选股情报 Top5</h2>
      <p class="hint block-hint">选股逻辑尚待按新版账户框架重构，当前仅作情报参考。</p>
      <ul>
        <li v-for="(row, i) in data.selection_resolve.top5" :key="i">
          {{ selCode(row) }}
          <span v-if="selName(row) !== '—'"> {{ selName(row) }}</span>
          <span v-if="selScore(row) !== '—'"> · 分 {{ selScore(row) }}</span>
          <span v-if="row['建议动作']"> · {{ row['建议动作'] }}</span>
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
