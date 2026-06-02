<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import {
  fetchSelectionDates,
  fetchSelectionHistory,
  fetchSelectionKline,
  requestSelectionSopAnalyze,
  type SelectionSopJob,
} from '../api/dashboard'
import SelectionStockCard from '../components/SelectionStockCard.vue'
import ConfirmDialog from '../components/ConfirmDialog.vue'
import SopReviewCard from '../components/SopReviewCard.vue'
import SopTaskPanel from '../components/SopTaskPanel.vue'
import StockKlinePanel from '../components/StockKlinePanel.vue'
import StockProfilePanel from '../components/StockProfilePanel.vue'
import { usePlatformLayout } from '../composables/usePlatformLayout'
import { isShareMode } from '../auth/hubAuth'
import type { DailyBar, SelectionHistory } from '../types/dashboard'
import {
  parseSelectionProfile,
  selAction,
  selCode,
  selConceptList,
  selIndustry,
  selName,
  selPct,
  selScore,
  selStrategy,
  sopName,
  strategyLabel,
} from '../utils/selection'

const dates = ref<string[]>([])
const selectedDate = ref('')
const data = ref<SelectionHistory | null>(null)
const expandedSop = ref<number | null>(null)
const expandedProfile = ref<string | null>(null)
const expandedKline = ref<string | null>(null)
const klineCache = ref<Record<string, DailyBar[]>>({})
const klineLoading = ref<string | null>(null)
const klineError = ref<Record<string, string>>({})
const klineMeta = ref<Record<string, string>>({})
const sopLoading = ref<Record<string, boolean>>({})
const sopHint = ref<Record<string, string>>({})
const sopConfirmTarget = ref<{ code: string; label: string; strategy: string } | null>(null)
const sopTaskPanelRef = ref<{ refresh: () => Promise<void> } | null>(null)
const error = ref('')
const loading = ref(false)

const isMobile = usePlatformLayout()
const KLINE_DAYS = 60

function rowKey(code: string, suffix = '', strategy = ''): string {
  const d = selectedDate.value || 'na'
  const strat = strategy ? `${strategy}:` : ''
  return `${d}:${strat}${code}${suffix}`
}

function selectionRowKey(row: Record<string, unknown>, suffix = ''): string {
  return rowKey(selCode(row), suffix, selStrategy(row))
}

const shareOnly = isShareMode()

function isHeld(code: string): boolean {
  if (shareOnly) return false
  const c = code.replace(/\D/g, '').slice(-6).padStart(6, '0')
  return (data.value?.holding_codes ?? []).includes(c)
}

async function loadDates() {
  const res = await fetchSelectionDates()
  dates.value = res.dates
  if (!selectedDate.value && dates.value.length > 0) {
    selectedDate.value = dates.value[0]
  } else if (selectedDate.value && !dates.value.includes(selectedDate.value)) {
    selectedDate.value = dates.value[0] ?? ''
  }
}

async function loadSelection() {
  if (!selectedDate.value) {
    data.value = null
    return
  }
  loading.value = true
  error.value = ''
  expandedKline.value = null
  expandedProfile.value = null
  klineCache.value = {}
  klineError.value = {}
  klineMeta.value = {}
  try {
    data.value = await fetchSelectionHistory(selectedDate.value)
    syncSopRowHintsFromJobs()
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
    data.value = null
  } finally {
    loading.value = false
  }
}

function toggleProfile(row: Record<string, unknown>) {
  const key = selectionRowKey(row, ':p')
  expandedProfile.value = expandedProfile.value === key ? null : key
  if (expandedProfile.value === key) {
    expandedKline.value = null
  }
}

function toggleSop(rank: number) {
  expandedSop.value = expandedSop.value === rank ? null : rank
}

async function toggleKline(rowOrCode: Record<string, unknown> | string, suffix = '') {
  const code = typeof rowOrCode === 'string' ? rowOrCode : selCode(rowOrCode)
  const strategy = typeof rowOrCode === 'string' ? '' : selStrategy(rowOrCode)
  const key = rowKey(code, suffix, strategy)
  if (expandedKline.value === key) {
    expandedKline.value = null
    return
  }
  expandedKline.value = key
  if (expandedKline.value === key) {
    expandedProfile.value = null
    expandedSop.value = null
  }
  if (!selectedDate.value) return

  klineLoading.value = key
  delete klineError.value[key]
  try {
    const res = await fetchSelectionKline(code, selectedDate.value, KLINE_DAYS)
    klineCache.value[key] = res.bars
    const last = res.bars[res.bars.length - 1]?.trade_date
    klineMeta.value[key] = res.kline_end_date ?? last ?? ''
  } catch (e) {
    klineError.value[key] = e instanceof Error ? e.message : String(e)
    klineCache.value[key] = []
  } finally {
    klineLoading.value = null
  }
}

function sopRowKey(tradeDate: string, code: string): string {
  return `${tradeDate}:${code}:sop`
}

function syncSopRowHintsFromJobs(jobs: SelectionSopJob[] = latestSopJobs) {
  if (shareOnly || !selectedDate.value) return
  for (const job of jobs) {
    if (job.trade_date !== selectedDate.value) continue
    const key = sopRowKey(job.trade_date, job.code)
    if (job.status === 'queued' || job.status === 'running') {
      sopLoading.value[key] = true
      sopHint.value[key] = job.message ?? '分析中…'
    } else if (job.status === 'done') {
      sopLoading.value[key] = false
      sopHint.value[key] = '✅ 已推送到微信'
    } else if (job.status === 'done_with_warning') {
      sopLoading.value[key] = false
      sopHint.value[key] = `⚠️ ${job.message ?? '微信推送异常'}`
    } else if (job.status === 'failed') {
      sopLoading.value[key] = false
      sopHint.value[key] = `❌ ${job.error ?? job.message ?? '分析失败'}`
    }
  }
}

let latestSopJobs: SelectionSopJob[] = []

function onSopJobsUpdate(jobs: SelectionSopJob[]) {
  latestSopJobs = jobs
  syncSopRowHintsFromJobs(jobs)
}

async function promptSopAnalysis(row: Record<string, unknown>) {
  if (shareOnly || !selectedDate.value) return
  const code = selCode(row)
  const key = selectionRowKey(row, ':sop')
  if (sopLoading.value[key]) return

  const name = selName(row)
  const strat = selStrategy(row)
  const label = name && name !== '—' ? `${name}（${code}）` : code
  sopConfirmTarget.value = { code, label, strategy: strat }
}

function cancelSopConfirm() {
  sopConfirmTarget.value = null
}

async function confirmSopAnalysis() {
  const target = sopConfirmTarget.value
  if (!target) return
  sopConfirmTarget.value = null
  await runSopAnalysis(target.code, target.strategy)
}

async function runSopAnalysis(code: string, strategy = 'combined') {
  if (shareOnly || !selectedDate.value) return
  const key = rowKey(code, ':sop', strategy)
  if (sopLoading.value[key]) return

  sopLoading.value[key] = true
  sopHint.value[key] = '已排队，OpenCLI 采集中…'

  try {
    const job = await requestSelectionSopAnalyze(code, selectedDate.value, strategy)
    if (!job.job_id) {
      sopHint.value[key] = '❌ 服务返回异常，请刷新后重试'
      sopLoading.value[key] = false
      return
    }
    sopHint.value[key] = job.message ?? '分析中，完成后推送到微信'
    await sopTaskPanelRef.value?.refresh()
  } catch (e) {
    sopHint.value[key] = e instanceof Error ? e.message : String(e)
    sopLoading.value[key] = false
  }
}

async function init() {
  error.value = ''
  try {
    await loadDates()
    await loadSelection()
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  }
}

watch(selectedDate, loadSelection)

onMounted(init)
</script>

<template>
  <div class="page" :class="{ mobile: isMobile }">
    <div class="head">
      <h1>选股结果</h1>
      <p v-if="data && !loading" class="summary">
        {{ data.trade_date }} · {{ data.count }} 条
      </p>
    </div>

    <div class="filter-bar">
      <label class="filter-field filter-field-grow">
        <span class="filter-label">交易日</span>
        <select v-model="selectedDate" class="filter-select" :disabled="!dates.length">
          <option v-if="!dates.length" value="">暂无历史</option>
          <option v-for="d in dates" :key="d" :value="d">{{ d }}</option>
        </select>
      </label>
    </div>

    <section
      v-if="!shareOnly && data?.execution_card_buys?.length"
      class="card-buys"
    >
      <h2 class="section-title">
        执行卡 · 当日选股候选
        <span v-if="data.account_position_pct != null" class="pos-tag">
          仓位 {{ Number(data.account_position_pct).toFixed(1) }}%
          <template v-if="Number(data.account_position_pct) > 75"> · A 防守（禁新开）</template>
          <template v-else-if="Number(data.account_position_pct) > 60"> · B 试探</template>
        </span>
      </h2>
      <table class="card-buys-table">
        <thead>
          <tr>
            <th>标的</th>
            <th>策略</th>
            <th>分</th>
            <th>建议</th>
            <th>条件</th>
            <th>动作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in data.execution_card_buys" :key="item.code + item.kind + (item.strategy ?? '')">
            <td>
              <strong>{{ item.code }}</strong>
              {{ item.name }}
              <span v-if="item.priority" class="mini-priority">{{ item.priority }}</span>
            </td>
            <td>
              <span v-if="item.kind === 'trim'" class="tag strategy">持仓</span>
              <span v-else-if="item.strategy" class="tag strategy">{{ strategyLabel(item.strategy) }}</span>
              <span v-else class="dash">—</span>
            </td>
            <td>{{ item.kind === 'trim' ? '—' : item.score ?? '—' }}</td>
            <td>{{ item.kind === 'trim' ? '减仓' : item.action || '—' }}</td>
            <td>{{ item.trigger }}</td>
            <td>
              <template v-if="item.kind === 'trim'">{{ item.action }}</template>
              <template v-else>{{ item.shares }} 股，止损 {{ item.stop }}</template>
            </td>
          </tr>
        </tbody>
      </table>
      <p class="card-buys-hint">
        试探买入来自<strong>当日选股列表</strong>（可买动作 / 执行卡标记 / md 队列交集，按分数 Top8，已持仓除外）；P1 减仓仍读 <code>持仓执行卡.md</code>。
        <template v-if="data.account_position_pct != null && Number(data.account_position_pct) > 75">
          当前 A 档（&gt;75%）：列表仅供观察，<strong>禁止纯新开仓</strong>。
        </template>
      </p>
    </section>

    <SopTaskPanel
      v-if="!shareOnly"
      ref="sopTaskPanelRef"
      @update="onSopJobsUpdate"
    />

    <p v-if="loading" class="hint">加载中…</p>
    <p v-if="error" class="error">{{ error }}</p>

    <!-- SOP 审查 -->
    <section v-if="data?.sop_review?.items?.length" class="section">
      <h2 class="section-title">SOP 审查</h2>

      <div v-if="isMobile" class="mobile-list">
        <SopReviewCard
          v-for="item in data.sop_review.items"
          :key="String(item.rank_no)"
          :item="item"
          :show-held="!shareOnly"
          :held="isHeld(String(item.code ?? item.ts_code))"
          :sop-open="expandedSop === Number(item.rank_no)"
          :kline-open="expandedKline === rowKey(String(item.code ?? item.ts_code), ':sop')"
          :kline-loading="klineLoading === rowKey(String(item.code ?? item.ts_code), ':sop')"
          :kline-bars="klineCache[rowKey(String(item.code ?? item.ts_code), ':sop')]"
          :kline-error="klineError[rowKey(String(item.code ?? item.ts_code), ':sop')]"
          :kline-end-date="klineMeta[rowKey(String(item.code ?? item.ts_code), ':sop')]"
          @toggle-sop="toggleSop(Number(item.rank_no))"
          @toggle-kline="toggleKline(String(item.code ?? item.ts_code), ':sop')"
        />
      </div>

      <div v-else class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>代码</th>
              <th>名称</th>
              <th>决策</th>
              <th>分</th>
              <th v-if="!shareOnly">持仓</th>
              <th></th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <template v-for="item in data.sop_review.items" :key="String(item.rank_no)">
              <tr>
                <td>{{ item.rank_no }}</td>
                <td>{{ item.code ?? item.ts_code }}</td>
                <td>{{ sopName(item) }}</td>
                <td>{{ item.decision }}</td>
                <td>{{ item.score }}</td>
                <td v-if="!shareOnly">
                  <span v-if="isHeld(String(item.code ?? item.ts_code))" class="tag held">已持有</span>
                  <span v-else class="tag new">新标的</span>
                </td>
                <td>
                  <button
                    v-if="item.review_md"
                    type="button"
                    class="link"
                    @click="toggleSop(Number(item.rank_no))"
                  >
                    {{ expandedSop === Number(item.rank_no) ? '收起' : '详情' }}
                  </button>
                </td>
                <td>
                  <button
                    type="button"
                    class="link"
                    @click="toggleKline(String(item.code ?? item.ts_code), ':sop')"
                  >
                    {{
                      expandedKline === rowKey(String(item.code ?? item.ts_code), ':sop')
                        ? '收起K线'
                        : 'K线'
                    }}
                  </button>
                </td>
              </tr>
              <tr v-if="expandedSop === Number(item.rank_no) && item.review_md" class="detail-row">
                <td :colspan="shareOnly ? 7 : 8">
                  <pre>{{ item.review_md }}</pre>
                </td>
              </tr>
              <tr
                v-if="expandedKline === rowKey(String(item.code ?? item.ts_code), ':sop')"
                class="detail-row"
              >
                <td :colspan="shareOnly ? 7 : 8" class="detail-cell">
                  <StockKlinePanel
                    :bars="klineCache[rowKey(String(item.code ?? item.ts_code), ':sop')] ?? []"
                    :loading="klineLoading === rowKey(String(item.code ?? item.ts_code), ':sop')"
                    :error="klineError[rowKey(String(item.code ?? item.ts_code), ':sop')]"
                    :end-date="klineMeta[rowKey(String(item.code ?? item.ts_code), ':sop')]"
                  />
                </td>
              </tr>
            </template>
          </tbody>
        </table>
      </div>
    </section>

    <!-- 全量列表 -->
    <section v-if="data?.rows?.length" class="section">
      <h2 class="section-title">全量列表（{{ data.rows.length }} 条）</h2>

      <div v-if="isMobile" class="mobile-list">
        <SelectionStockCard
          v-for="(row, i) in data.rows"
          :key="`${selStrategy(row)}:${selCode(row)}-${i}`"
          :row="row"
          :show-held="!shareOnly"
          :held="isHeld(selCode(row))"
          :show-sop="!shareOnly"
          :sop-loading="!!sopLoading[selectionRowKey(row, ':sop')]"
          :sop-hint="sopHint[selectionRowKey(row, ':sop')]"
          :profile-open="expandedProfile === selectionRowKey(row, ':p')"
          :kline-open="expandedKline === selectionRowKey(row)"
          :kline-loading="klineLoading === selectionRowKey(row)"
          :kline-bars="klineCache[selectionRowKey(row)]"
          :kline-error="klineError[selectionRowKey(row)]"
          :kline-end-date="klineMeta[selectionRowKey(row)]"
          @toggle-profile="toggleProfile(row)"
          @toggle-kline="toggleKline(row)"
          @run-sop="promptSopAnalysis(row)"
        />
      </div>

      <div v-else class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>代码</th>
              <th>名称</th>
              <th>策略</th>
              <th>行业</th>
              <th>概念</th>
              <th>分</th>
              <th>涨跌幅</th>
              <th>建议</th>
              <th v-if="!shareOnly">持仓</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <template v-for="(row, i) in data.rows" :key="`${selStrategy(row)}:${selCode(row)}-${i}`">
              <tr>
                <td>{{ selCode(row) }}</td>
                <td>{{ selName(row) }}</td>
                <td>
                  <span class="tag strategy">{{ strategyLabel(selStrategy(row)) }}</span>
                </td>
                <td>{{ selIndustry(row) }}</td>
                <td class="concepts">
                  <div v-if="selConceptList(row).length" class="concept-preview">
                    <span
                      v-for="tag in selConceptList(row).slice(0, 3)"
                      :key="tag"
                      class="mini-chip"
                    >
                      {{ tag }}
                    </span>
                    <span v-if="selConceptList(row).length > 3" class="mini-chip more">
                      +{{ selConceptList(row).length - 3 }}
                    </span>
                  </div>
                  <span v-else class="dash">—</span>
                </td>
                <td>{{ selScore(row) }}</td>
                <td>{{ selPct(row) }}</td>
                <td>{{ selAction(row) || '—' }}</td>
                <td v-if="!shareOnly">
                  <span v-if="isHeld(selCode(row))" class="tag held">已持有</span>
                </td>
                <td class="actions">
                  <button
                    v-if="parseSelectionProfile(row).hasContent"
                    type="button"
                    class="btn-pill"
                    :class="{ active: expandedProfile === selectionRowKey(row, ':p') }"
                    @click="toggleProfile(row)"
                  >
                    {{ expandedProfile === selectionRowKey(row, ':p') ? '收起概况' : '概况' }}
                  </button>
                  <button
                    type="button"
                    class="btn-pill"
                    :class="{ active: expandedKline === selectionRowKey(row) }"
                    @click="toggleKline(row)"
                  >
                    {{ expandedKline === selectionRowKey(row) ? '收起K线' : 'K线' }}
                  </button>
                  <button
                    v-if="!shareOnly"
                    type="button"
                    class="btn-pill sop"
                    :disabled="!!sopLoading[selectionRowKey(row, ':sop')]"
                    @click="promptSopAnalysis(row)"
                  >
                    {{ sopLoading[selectionRowKey(row, ':sop')] ? 'SOP中…' : '东财SOP' }}
                  </button>
                </td>
              </tr>
              <tr
                v-if="!shareOnly && sopHint[selectionRowKey(row, ':sop')]"
                class="detail-row"
              >
                <td :colspan="shareOnly ? 9 : 10" class="sop-status-cell">
                  {{ sopHint[selectionRowKey(row, ':sop')] }}
                </td>
              </tr>
              <tr v-if="expandedProfile === selectionRowKey(row, ':p')" class="detail-row">
                <td :colspan="shareOnly ? 9 : 10" class="detail-cell">
                  <StockProfilePanel :row="row" />
                </td>
              </tr>
              <tr v-if="expandedKline === selectionRowKey(row)" class="detail-row">
                <td :colspan="shareOnly ? 9 : 10" class="detail-cell">
                  <StockKlinePanel
                    :bars="klineCache[selectionRowKey(row)] ?? []"
                    :loading="klineLoading === selectionRowKey(row)"
                    :error="klineError[selectionRowKey(row)]"
                    :end-date="klineMeta[selectionRowKey(row)]"
                  />
                </td>
              </tr>
            </template>
          </tbody>
        </table>
      </div>
    </section>

    <p v-if="!loading && !error && selectedDate && !data?.rows?.length" class="hint">
      该日无选股记录
    </p>

    <ConfirmDialog
      :open="!!sopConfirmTarget"
      title="东财 SOP 深度分析"
      :message="
        sopConfirmTarget
          ? `对 ${sopConfirmTarget.label} 执行 8 维数据采集与 AI 终审。\n约需 2～5 分钟，完成后推送到微信。`
          : ''
      "
      confirm-label="开始分析"
      cancel-label="取消"
      tone="warning"
      @confirm="confirmSopAnalysis"
      @cancel="cancelSopConfirm"
    />
  </div>
</template>

<style scoped>
.page {
  --page-pad: 0;
}

.page h1 {
  margin: 0;
  font-size: 22px;
}

.head {
  margin-bottom: 12px;
}

.summary {
  margin: 4px 0 0;
  color: #8b9cb3;
  font-size: 13px;
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

.section {
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

.hint {
  color: #8b9cb3;
}

.table-wrap {
  overflow-x: auto;
  border: 1px solid #243041;
  border-radius: 12px;
  padding: 12px;
}

table {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
}

th,
td {
  padding: 8px 10px;
  border-bottom: 1px solid #243041;
  text-align: left;
  vertical-align: top;
}

th {
  color: #8b9cb3;
}

.tag {
  font-size: 11px;
  padding: 2px 6px;
  border-radius: 4px;
}

.tag.held {
  background: #10261c;
  color: #7dffb2;
}

.tag.strategy {
  background: #1a2840;
  color: #93c5fd;
}

.tag.new {
  background: #1a2840;
  color: #93c5fd;
}

.link {
  background: none;
  border: none;
  color: #60a5fa;
  cursor: pointer;
  font-size: 12px;
  padding: 0;
  white-space: nowrap;
}

.detail-row pre {
  margin: 0;
  font-size: 12px;
  white-space: pre-wrap;
  color: #dbe7ff;
  max-height: 280px;
  overflow-y: auto;
}

.detail-cell {
  padding: 10px 12px !important;
  background: #0a0e14;
}

.detail-row td {
  background: #0a0e14;
  border-bottom: 1px solid #243041;
}

.concepts {
  max-width: 200px;
}

.concept-preview {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.mini-chip {
  font-size: 10px;
  line-height: 1.3;
  padding: 2px 6px;
  border-radius: 4px;
  background: #1a2230;
  color: #b8c5d9;
  white-space: nowrap;
}

.mini-chip.more {
  color: #8b9cb3;
  background: transparent;
  border: 1px dashed #2a3548;
}

.dash {
  color: #5c6b80;
}

.actions {
  white-space: nowrap;
}

.btn-pill {
  background: #161e2a;
  border: 1px solid #2a3548;
  color: #93c5fd;
  cursor: pointer;
  font-size: 11px;
  padding: 4px 8px;
  border-radius: 6px;
  white-space: nowrap;
}

.btn-pill:hover {
  border-color: #3d5270;
  background: #1a2432;
}

.btn-pill.active {
  background: #152238;
  border-color: #3b82f6;
  color: #dbe7ff;
}

.btn-pill + .btn-pill {
  margin-left: 6px;
}

.btn-pill.sop {
  color: #fcd34d;
  border-color: #4a4020;
}

.btn-pill.sop:disabled {
  opacity: 0.55;
  cursor: wait;
}

.sop-status-cell {
  font-size: 12px;
  color: #93c5fd;
  padding: 8px 12px !important;
}

.error {
  color: #ff8f8f;
}

.card-buys {
  margin-bottom: 20px;
  padding: 14px 16px;
  border: 1px solid #2a3548;
  border-radius: 12px;
  background: #121820;
}

.card-buys .pos-tag {
  margin-left: 8px;
  font-size: 12px;
  font-weight: 500;
  color: #93c5fd;
}

.card-buys-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.card-buys-table th,
.card-buys-table td {
  padding: 8px 10px;
  text-align: left;
  border-bottom: 1px solid #1e2836;
}

.card-buys-hint {
  margin: 10px 0 0;
  font-size: 12px;
  color: #8b9cb3;
}

.mini-priority {
  display: inline-block;
  margin-left: 6px;
  font-size: 10px;
  color: #93c5fd;
}

.card-buys-table .tag.strategy {
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 4px;
  background: #1a2840;
  color: #93c5fd;
}

.card-buys-table .dash {
  color: #5c6b80;
}

/* H5 */
.page.mobile .head {
  margin-bottom: 10px;
}

.page.mobile h1 {
  font-size: 20px;
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
</style>
