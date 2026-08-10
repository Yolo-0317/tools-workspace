<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import DashboardLoadingSkeleton from '../components/DashboardLoadingSkeleton.vue'
import MiniLineChart from '../components/MiniLineChart.vue'
import PortfolioPositionCard from '../components/PortfolioPositionCard.vue'
import PortfolioWorkbenchPanel from '../components/PortfolioWorkbenchPanel.vue'
import { usePlatformLayout } from '../composables/usePlatformLayout'
import {
  fetchDashboardSummary,
  fetchPortfolioHistory,
  fetchPortfolioSnapshot,
  fetchPortfolioWorkbench,
  fmtNum,
  fmtRatioPct,
} from '../api/dashboard'
import type {
  AccountSnapshot,
  PortfolioWorkbench,
  PositionRow,
  WorkbenchPosition,
} from '../types/dashboard'
import { posCode, posCost, posPnl, posPrice } from '../utils/portfolio'

const positions = ref<PositionRow[]>([])
const account = ref<Record<string, unknown>>({})
const series = ref<AccountSnapshot[]>([])
const snapshotDates = ref<string[]>([])
const LIVE_SNAP = '__live__'
const selectedSnapDate = ref(LIVE_SNAP)
const livePositions = ref<PositionRow[]>([])
const workbench = ref<PortfolioWorkbench | null>(null)
const selectedPosition = ref<WorkbenchPosition | null>(null)
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

function openOperationCard(position: WorkbenchPosition) {
  selectedPosition.value = position
}

function closeOperationCard() {
  selectedPosition.value = null
}

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

async function loadHistoryData() {
  try {
    const [summary, history] = await Promise.all([
      fetchDashboardSummary('eod', true),
      fetchPortfolioHistory(90),
    ])
    series.value = history.series.length ? history.series : summary.account_series
    const histDates = history.dates.length
      ? history.dates
      : summary.account_series.map((s) => String(s.snapshot_date)).reverse()
    snapshotDates.value = [LIVE_SNAP, ...histDates]
  } catch {}
}

onMounted(async () => {
  try {
    const workbenchRes = await fetchPortfolioWorkbench()
    workbench.value = workbenchRes
    account.value = {
      total_assets: workbenchRes.account.total_assets,
      available_cash: workbenchRes.account.available_cash,
      market_value: workbenchRes.account.market_value,
      position_ratio: workbenchRes.account.account_position_pct,
    }
    livePositions.value = workbenchRes.positions
    selectedSnapDate.value = LIVE_SNAP
    positions.value = livePositions.value
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    loading.value = false
  }
  void loadHistoryData()
})
</script>

<template>
  <div class="page" :class="{ mobile: isMobile }">
    <header class="head">
      <h1>持仓</h1>
      <p v-if="!loading && positionCount" class="sub">
        {{ positionCount }} 只
        <span v-if="selectedSnapDate === LIVE_SNAP"> · 当前执行卡</span>
        <span v-else-if="selectedSnapDate"> · 快照 {{ selectedSnapDate }}</span>
      </p>
    </header>

    <DashboardLoadingSkeleton v-if="loading" variant="portfolio" label="加载持仓" />
    <p v-if="error" class="error">{{ error }}</p>

    <PortfolioWorkbenchPanel v-if="!loading && workbench" :workbench="workbench" />

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
            {{ d === LIVE_SNAP ? '当前执行卡（券商页已核对）' : d }}
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

    <section v-if="workbench?.positions.length" class="diagnostic-section">
      <h2 class="section-title">持仓诊断</h2>
      <p class="hint">库存持仓与交易候选分开管理；收盘候选必须在盘中二次确认后才可试错。</p>
      <div class="diagnostic-grid">
        <button
          v-for="position in workbench.positions"
          :key="position.code"
          type="button"
          class="diagnostic-card"
          @click="openOperationCard(position)"
        >
          <div>
            <strong>{{ position.name }}</strong>
            <span>{{ position.code }} · {{ position.role }}</span>
          </div>
          <b>{{ position.decision }}</b>
          <p>交易预算 {{ position.trading_budget_weight_pct?.toFixed(1) ?? '—' }}% · {{ position.next_review }}</p>
          <small>点击查看操作详情</small>
        </button>
      </div>
    </section>

    <div v-if="selectedPosition" class="operation-overlay" @click.self="closeOperationCard">
      <section class="operation-dialog" role="dialog" aria-modal="true" :aria-label="`${selectedPosition.name} 操作详情`">
        <header>
          <div>
            <p>{{ selectedPosition.code }} · {{ selectedPosition.role }}</p>
            <h2>{{ selectedPosition.name }} 操作详情</h2>
          </div>
          <button type="button" class="close-button" aria-label="关闭操作详情" @click="closeOperationCard">关闭</button>
        </header>

        <div class="detail-summary">
          <span>{{ selectedPosition.decision }}</span>
          <strong>交易预算 {{ selectedPosition.trading_budget_weight_pct?.toFixed(1) ?? '—' }}%</strong>
        </div>
        <p class="review-copy">{{ selectedPosition.next_review }}</p>

        <template v-if="selectedPosition.operation_card">
          <section class="detail-block">
            <h3>持有逻辑</h3>
            <p>{{ selectedPosition.operation_card.holding_logic }}</p>
          </section>
          <section class="detail-block">
            <h3>交易档案</h3>
            <p><strong>类型：</strong>{{ selectedPosition.trade_profile }}</p>
            <p><strong>入场门槛：</strong>{{ selectedPosition.entry_gate }}</p>
            <p><strong>退出规则：</strong>{{ selectedPosition.exit_rule }}</p>
          </section>
          <section v-if="selectedPosition.confirmation_card" class="detail-block confirmation-card">
            <h3>盘中确认卡</h3>
            <p class="confirmation-status">{{ selectedPosition.confirmation_card.overall_status }}</p>
            <p><strong>规则：</strong>{{ selectedPosition.confirmation_card.rule }}</p>
            <p class="confirmation-source">数据来源：{{ selectedPosition.confirmation_card.source }} · 更新：{{ selectedPosition.confirmation_card.updated_at ?? '待采集' }}</p>
            <article v-for="item in selectedPosition.confirmation_card.items" :key="item.key">
              <strong>{{ item.label }} · {{ item.status }}</strong>
              <small>采集：{{ item.timing }}</small>
              <ul><li v-for="field in item.fields" :key="field">{{ field }}</li></ul>
            </article>
          </section>
          <section class="detail-block">
            <h3>盘中与收盘观察</h3>
            <ul><li v-for="item in selectedPosition.operation_card.market_watch" :key="item">{{ item }}</li></ul>
          </section>
          <section v-if="selectedPosition.operation_card.observation_plan?.length" class="detail-block observation-plan">
            <h3>下一交易日观察计划</h3>
            <article v-for="step in selectedPosition.operation_card.observation_plan" :key="step.time">
              <strong>{{ step.time }} · {{ step.focus }}</strong>
              <p>{{ step.check }}</p>
              <small>{{ step.meaning }}</small>
            </article>
            <p v-if="selectedPosition.operation_card.close_decision" class="close-decision">{{ selectedPosition.operation_card.close_decision }}</p>
          </section>
          <section v-if="selectedPosition.operation_card.trade_reference" class="detail-block trade-reference">
            <h3>买入与卖出参考</h3>
            <p><strong>买入：</strong>{{ selectedPosition.operation_card.trade_reference.buy }}</p>
            <article v-for="item in selectedPosition.operation_card.trade_reference.sell" :key="item.trigger">
              <strong>条件：{{ item.trigger }}</strong>
              <p>{{ item.reference_action }}</p>
            </article>
            <small>仅作条件化决策参考，不自动下单；盘中执行前须由用户确认。</small>
          </section>
          <section v-if="selectedPosition.operation_card.decision_paths?.length" class="detail-block decision-paths">
            <h3>两条决策路径</h3>
            <article v-for="path in selectedPosition.operation_card.decision_paths" :key="path.title">
              <strong>{{ path.title }}</strong>
              <p>{{ path.when }}</p>
              <small>{{ path.result }}</small>
            </article>
            <p v-if="selectedPosition.operation_card.position_guidance" class="position-guidance">{{ selectedPosition.operation_card.position_guidance }}</p>
          </section>
          <section class="detail-block risk">
            <h3>需要记录的风险信号</h3>
            <ul><li v-for="item in selectedPosition.operation_card.risk_signals" :key="item">{{ item }}</li></ul>
          </section>
          <section class="detail-block guardrail">
            <h3>操作约束</h3>
            <p>{{ selectedPosition.operation_card.guardrail }}</p>
          </section>
        </template>
        <p v-else class="hint">该标的的详情卡尚待补齐。</p>
      </section>
    </div>

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

.diagnostic-section {
  margin: 20px 0;
}

.diagnostic-section .hint {
  margin: -4px 0 10px;
  font-size: 13px;
}

.diagnostic-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 10px;
}

.diagnostic-card {
  appearance: none;
  width: 100%;
  text-align: left;
  padding: 12px;
  border-radius: 10px;
  border: 1px solid #243041;
  background: #121820;
  color: inherit;
  cursor: pointer;
  transition: border-color 0.16s ease, transform 0.16s ease;
}

.diagnostic-card:hover,
.diagnostic-card:focus-visible {
  border-color: #4d88be;
  outline: none;
  transform: translateY(-1px);
}

.diagnostic-card > div {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  align-items: baseline;
}

.diagnostic-card span {
  color: #8b9cb3;
  font-size: 11px;
  text-align: right;
}

.diagnostic-card b {
  display: inline-block;
  margin-top: 8px;
  color: #ffd27d;
  font-size: 12px;
}

.diagnostic-card p {
  margin: 6px 0 0;
  color: #c5d4ea;
  font-size: 12px;
  line-height: 1.45;
}

.diagnostic-card small {
  display: block;
  margin-top: 9px;
  color: #8fcbff;
  font-size: 11px;
}

.operation-overlay {
  position: fixed;
  z-index: 100;
  inset: 0;
  display: grid;
  place-items: center;
  padding: 20px;
  background: rgba(2, 7, 13, 0.74);
}

.operation-dialog {
  width: min(620px, 100%);
  max-height: min(760px, calc(100vh - 40px));
  overflow: auto;
  padding: 18px;
  border: 1px solid #31506f;
  border-radius: 14px;
  background: #121b26;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.4);
}

.operation-dialog header {
  display: flex;
  justify-content: space-between;
  gap: 14px;
  align-items: flex-start;
}

.operation-dialog header p,
.operation-dialog h2 { margin: 0; }
.operation-dialog header p { color: #8b9cb3; font-size: 12px; }
.operation-dialog h2 { margin-top: 4px; font-size: 18px; }
.close-button { padding: 6px 9px; border: 1px solid #3a4e66; border-radius: 7px; background: #192738; color: #dbe7ff; cursor: pointer; }
.detail-summary { display: flex; justify-content: space-between; gap: 12px; margin-top: 16px; padding: 10px; border-radius: 9px; background: #172535; color: #ffd27d; font-size: 13px; }.detail-summary strong { color: #dbe7ff; font-variant-numeric: tabular-nums; }
.review-copy { margin: 12px 0; color: #c5d4ea; font-size: 13px; line-height: 1.55; }
.detail-block { margin-top: 10px; padding: 12px; border: 1px solid #26384b; border-radius: 9px; background: #0e161f; }.detail-block h3 { margin: 0 0 7px; color: #9fc7ed; font-size: 13px; }.detail-block p, .detail-block ul { margin: 0; color: #d0dced; font-size: 13px; line-height: 1.55; }.detail-block ul { padding-left: 18px; }.detail-block.risk h3 { color: #ffd27d; }.detail-block.guardrail h3 { color: #9fe0bb; }.observation-plan article { margin-top: 9px; padding-top: 9px; border-top: 1px solid #26384b; }.observation-plan article:first-of-type { margin-top: 0; padding-top: 0; border-top: 0; }.observation-plan article strong { display: block; color: #dbe7ff; font-size: 12px; }.observation-plan article p { margin-top: 3px; }.observation-plan article small { display: block; margin-top: 3px; color: #8b9cb3; font-size: 12px; line-height: 1.45; }.close-decision { margin-top: 10px !important; padding: 8px; border-radius: 6px; background: #172535; color: #dbe7ff !important; }
.trade-reference { border-color: #5b4c2c; }.trade-reference h3 { color: #ffd27d; }.trade-reference article { margin-top: 9px; padding-top: 9px; border-top: 1px solid #3c3728; }.trade-reference article strong { color: #dbe7ff; font-size: 12px; }.trade-reference article p { margin-top: 3px; }.trade-reference > small { display: block; margin-top: 10px; color: #8b9cb3; font-size: 11px; line-height: 1.45; }
.confirmation-card { border-color: #5b4c2c; }.confirmation-card h3 { color: #ffd27d; }.confirmation-status { margin-bottom: 7px !important; color: #ffd27d !important; font-weight: 700; }.confirmation-source { margin-top: 7px !important; color: #8b9cb3 !important; font-size: 12px !important; }.confirmation-card article { margin-top: 9px; padding-top: 9px; border-top: 1px solid #3c3728; }.confirmation-card article strong { display: block; color: #dbe7ff; font-size: 12px; }.confirmation-card article small { display: block; margin-top: 3px; color: #8b9cb3; font-size: 11px; }.confirmation-card article ul { margin-top: 4px; }
.decision-paths article { margin-top: 9px; padding-top: 9px; border-top: 1px solid #26384b; }.decision-paths article:first-of-type { margin-top: 0; padding-top: 0; border-top: 0; }.decision-paths article strong { color: #dbe7ff; font-size: 12px; }.decision-paths article p { margin-top: 3px; }.decision-paths article small { display: block; margin-top: 3px; color: #8b9cb3; font-size: 12px; line-height: 1.45; }.position-guidance { margin-top: 10px !important; padding: 8px; border-radius: 6px; background: #172535; color: #dbe7ff !important; }

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
