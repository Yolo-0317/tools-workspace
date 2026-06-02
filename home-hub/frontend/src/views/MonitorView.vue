<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import {
  fetchMonitorDates,
  fetchMonitorRules,
  fetchMonitorState,
} from '../api/dashboard'
import { usePlatformLayout } from '../composables/usePlatformLayout'
import { shanghaiToday } from '../utils/date'
import type {
  MonitorFiredDetail,
  MonitorHistoryDay,
  MonitorRule,
  MonitorState,
} from '../types/dashboard'

const rules = ref<MonitorRule[]>([])
const quoteSource = ref('')
const quotesAsOf = ref('')
const history = ref<MonitorHistoryDay[]>([])
const selectedDate = ref('')
const state = ref<MonitorState | null>(null)
const error = ref('')
const pageLoading = ref(true)
const stateLoading = ref(false)
const quotesLoading = ref(false)
const isMobile = usePlatformLayout()

const today = shanghaiToday()

const firedDetails = computed(() => state.value?.fired_details ?? [])
const firedCount = computed(() => state.value?.fired.length ?? 0)

function ruleCode(rule: MonitorRule): string {
  return String(rule.code ?? rule.ts_code ?? '—')
}

function ruleDesc(rule: MonitorRule): string {
  if (rule.fired_today && rule.fired_message) return String(rule.fired_message)
  if (rule.triggered_now && rule.note_live) return String(rule.note_live)
  return String(rule.note ?? rule.message ?? '')
}

function rulePrice(rule: MonitorRule): string {
  if (rule.current_price == null) return '—'
  const pct =
    rule.change_pct != null
      ? ` (${rule.change_pct >= 0 ? '+' : ''}${rule.change_pct.toFixed(2)}%)`
      : ''
  return `${Number(rule.current_price).toFixed(2)}${pct}`
}

function ruleStatus(rule: MonitorRule): string {
  if (rule.triggered_now) return rule.fired_today ? '已触发·仍满足' : '现满足条件'
  if (rule.fired_today) return '今日已触发（已恢复）'
  return '未触发'
}

function firedMeta(item: MonitorFiredDetail): string {
  const parts: string[] = []
  if (item.fired_at) parts.push(`触发 ${item.fired_at}`)
  if (item.fired_price != null) parts.push(`触发价 ${Number(item.fired_price).toFixed(2)}`)
  if (item.change_pct != null) {
    const pct = Number(item.change_pct)
    parts.push(`涨跌 ${pct >= 0 ? '+' : ''}${pct.toFixed(2)}%`)
  }
  return parts.join(' · ')
}

async function loadRules() {
  quotesLoading.value = true
  try {
    const r = await fetchMonitorRules(true)
    rules.value = r.rules
    quoteSource.value = r.quote_source ?? ''
    quotesAsOf.value = r.quotes_as_of ?? ''
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    quotesLoading.value = false
  }
}

async function refreshAll() {
  error.value = ''
  await Promise.all([loadRules(), loadState()])
}

function firedTitle(item: MonitorFiredDetail): string {
  return item.name || item.id
}

async function loadHistory() {
  const res = await fetchMonitorDates(90)
  history.value = res.dates
  if (!selectedDate.value) {
    const hasToday = history.value.some((h) => h.date === today)
    selectedDate.value = hasToday
      ? today
      : history.value[0]?.date ?? today
  }
}

async function loadState() {
  if (!selectedDate.value) return
  stateLoading.value = true
  error.value = ''
  try {
    state.value = await fetchMonitorState(selectedDate.value)
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
    state.value = null
  } finally {
    stateLoading.value = false
  }
}

async function init() {
  pageLoading.value = true
  error.value = ''
  try {
    await loadRules()
    await loadHistory()
    await loadState()
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    pageLoading.value = false
  }
}

watch(selectedDate, loadState)

onMounted(init)
</script>

<template>
  <div class="page" :class="{ mobile: isMobile }">
    <header class="page-head">
      <div class="head-row">
        <div>
          <h1>盘中监控</h1>
          <p class="sub">
            持仓告警规则 · 触发记录
            <span v-if="quotesAsOf" class="quote-meta">
              · 现价 {{ quotesAsOf }}
              {{
                quoteSource === 'mysql'
                  ? '（每 5 分钟更新）'
                  : quoteSource === 'opencli'
                    ? '（东财实时）'
                    : '（库内快照）'
              }}
            </span>
          </p>
        </div>
        <button
          type="button"
          class="refresh-btn"
          :disabled="pageLoading || quotesLoading || stateLoading"
          @click="refreshAll"
        >
          {{ quotesLoading ? '刷新中…' : '刷新' }}
        </button>
      </div>
    </header>

    <label class="date-field">
      <span class="date-label">查看日期</span>
      <select v-model="selectedDate" class="date-select" :disabled="pageLoading">
        <option v-for="h in history" :key="h.date" :value="h.date">
          {{ h.date }}（{{ h.fired_count }} 条触发）
        </option>
        <option v-if="!history.length" :value="today">{{ today }}（今日）</option>
      </select>
    </label>

    <p v-if="error" class="error">{{ error }}</p>
    <p v-if="pageLoading" class="hint">加载中…</p>
    <p v-else-if="stateLoading" class="hint">切换日期…</p>

    <template v-if="!pageLoading && state && !stateLoading">
      <div class="summary">
        <span class="pill" :class="firedCount ? 'pill-warn' : 'pill-muted'">
          已触发 {{ firedCount }} 条
        </span>
        <span class="pill pill-muted">规则 {{ rules.length }} 条</span>
        <span v-if="!state.exists" class="pill pill-empty">无状态文件</span>
      </div>

      <section v-if="firedDetails.length" class="section">
        <h2 class="section-title">已触发</h2>
        <ul class="fired-list">
          <li v-for="item in firedDetails" :key="item.id" class="fired-card" :class="{ suspect: item.suspect }">
            <div class="fired-head">
              <span class="fired-name">{{ firedTitle(item) }}</span>
              <span v-if="item.ts_code" class="code-badge">{{ item.ts_code }}</span>
            </div>
            <p v-if="item.rule_type" class="fired-type">{{ item.rule_type }}</p>
            <p v-if="firedMeta(item)" class="fired-meta">{{ firedMeta(item) }}</p>
            <p v-if="item.note" class="fired-note">{{ item.note }}</p>
          </li>
        </ul>
      </section>
      <section v-else class="section section-empty">
        <p class="empty-text">该日无触发记录</p>
      </section>

      <section v-if="history.length > 1" class="section">
        <h2 class="section-title">历史摘要</h2>
        <ul v-if="isMobile" class="history-list">
          <li
            v-for="h in history"
            :key="h.date"
            class="history-card"
            :class="{ active: h.date === selectedDate }"
            @click="selectedDate = h.date"
          >
            <div class="history-head">
              <span class="history-date">{{ h.date }}</span>
              <span class="history-count" :class="{ hot: h.fired_count > 0 }">
                {{ h.fired_count }} 条
              </span>
            </div>
            <p v-if="h.fired.length" class="history-ids">{{ h.fired.join('、') }}</p>
            <p v-else class="history-ids muted">无触发</p>
          </li>
        </ul>
        <div v-else class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>日期</th>
                <th>触发数</th>
                <th>规则 ID</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="h in history"
                :key="h.date"
                :class="{ active: h.date === selectedDate }"
                @click="selectedDate = h.date"
              >
                <td>{{ h.date }}</td>
                <td>{{ h.fired_count }}</td>
                <td class="ids">{{ h.fired.join('、') || '—' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section class="section">
        <h2 class="section-title">当前规则（{{ rules.length }}）</h2>
        <ul v-if="isMobile" class="rule-list">
          <li v-for="rule in rules" :key="String(rule.id)" class="rule-card">
            <div class="rule-head">
              <div class="rule-title">
                <span class="rule-name">{{ rule.name || '—' }}</span>
                <span class="code-badge">{{ ruleCode(rule) }}</span>
              </div>
              <span class="type-badge" :class="{ hot: rule.triggered_now }">{{ ruleStatus(rule) }}</span>
            </div>
            <p class="rule-price">现价 {{ rulePrice(rule) }} · 阈值 {{ rule.threshold ?? '—' }}</p>
            <p v-if="ruleDesc(rule)" class="rule-desc">{{ ruleDesc(rule) }}</p>
            <p class="rule-id mono">{{ rule.id }}</p>
          </li>
        </ul>
        <div v-else class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>代码</th>
                <th>名称</th>
                <th>现价</th>
                <th>阈值</th>
                <th>状态</th>
                <th>说明</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="rule in rules" :key="String(rule.id)" :class="{ 'row-hot': rule.triggered_now }">
                <td>{{ ruleCode(rule) }}</td>
                <td>{{ rule.name }}</td>
                <td class="mono">{{ rulePrice(rule) }}</td>
                <td class="mono">{{ rule.threshold ?? '—' }}</td>
                <td>{{ ruleStatus(rule) }}</td>
                <td class="note">{{ ruleDesc(rule) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </template>
  </div>
</template>

<style scoped>
.page-head {
  margin-bottom: 14px;
}

.head-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  min-width: 0;
}

.head-row > div:first-child {
  flex: 1;
  min-width: 0;
}

.refresh-btn {
  flex-shrink: 0;
  font-size: 13px;
  font-weight: 600;
  padding: 8px 14px;
  border-radius: 10px;
  border: 1px solid #3d5a80;
  background: #1a2433;
  color: #e7ecf3;
  cursor: pointer;
}

.refresh-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.quote-meta {
  color: #6b7d94;
}

.rule-price {
  margin: 6px 0 0;
  font-size: 13px;
  color: #9ec5ff;
  font-variant-numeric: tabular-nums;
}

.type-badge.hot {
  color: #ffb4b4;
  border-color: #4a3030;
  background: #261010;
}

.row-hot {
  background: rgba(38, 16, 16, 0.35);
}

.page-head h1 {
  margin: 0;
  font-size: 22px;
}

.sub {
  margin: 6px 0 0;
  font-size: 13px;
  color: #8b9cb3;
}

.date-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 14px;
}

.date-label {
  font-size: 12px;
  font-weight: 600;
  color: #6b7d94;
  letter-spacing: 0.02em;
}

.date-select {
  width: 100%;
  background: #121820;
  color: #e7ecf3;
  border: 1px solid #243041;
  border-radius: 10px;
  padding: 12px 14px;
  font-size: 15px;
  appearance: none;
}

.summary {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 16px;
}

.pill {
  font-size: 12px;
  font-weight: 600;
  padding: 4px 12px;
  border-radius: 999px;
}

.pill-warn {
  color: #ffb4b4;
  background: #261010;
  border: 1px solid #4a3030;
}

.pill-muted {
  color: #8b9cb3;
  background: #121820;
  border: 1px solid #243041;
}

.pill-empty {
  color: #ffd27d;
  background: #1a1a10;
  border: 1px solid #3d3520;
}

.section {
  margin-bottom: 16px;
}

.section-title {
  margin: 0 0 10px;
  font-size: 13px;
  font-weight: 600;
  color: #8b9cb3;
  letter-spacing: 0.02em;
}

.section-empty {
  padding: 20px 14px;
  border-radius: 12px;
  border: 1px dashed #243041;
  background: #121820;
  text-align: center;
}

.empty-text {
  margin: 0;
  font-size: 14px;
  color: #6b7d94;
}

.fired-list,
.history-list,
.rule-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.fired-card.suspect {
  border-color: #3d3520;
  background: linear-gradient(135deg, #1a1810 0%, #121820 100%);
}

.fired-card {
  padding: 14px;
  border-radius: 12px;
  border: 1px solid #4a3030;
  background: linear-gradient(135deg, #1a1010 0%, #121820 100%);
}

.fired-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 6px;
}

.fired-name {
  font-size: 16px;
  font-weight: 600;
  color: #ffd4a8;
  line-height: 1.3;
}

.code-badge {
  flex-shrink: 0;
  font-size: 11px;
  font-weight: 600;
  padding: 3px 8px;
  border-radius: 6px;
  color: #93c5fd;
  background: #152238;
  border: 1px solid #2a4060;
}

.fired-type {
  margin: 0 0 4px;
  font-size: 12px;
  color: #ffb4b4;
}

.fired-meta {
  margin: 0 0 4px;
  font-size: 12px;
  color: #9ec5ff;
  font-variant-numeric: tabular-nums;
}

.fired-note {
  margin: 0 0 8px;
  font-size: 13px;
  color: #dbe7ff;
  line-height: 1.45;
}

.fired-id {
  margin: 0;
  padding-top: 8px;
  border-top: 1px solid #3d2828;
  font-size: 11px;
  color: #6b7d94;
  word-break: break-all;
}

.history-card {
  padding: 12px 14px;
  border-radius: 12px;
  border: 1px solid #243041;
  background: #121820;
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
}

.history-card.active {
  border-color: #2563eb;
  background: #152033;
  box-shadow: inset 0 -2px 0 #2563eb;
}

.history-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 4px;
}

.history-date {
  font-size: 15px;
  font-weight: 600;
  color: #e7ecf3;
}

.history-count {
  font-size: 12px;
  font-weight: 600;
  color: #6b7d94;
}

.history-count.hot {
  color: #ffb4b4;
}

.history-ids {
  margin: 0;
  font-size: 12px;
  color: #8b9cb3;
  line-height: 1.4;
  word-break: break-word;
}

.history-ids.muted {
  color: #6b7d94;
}

.rule-card {
  padding: 14px;
  border-radius: 12px;
  border: 1px solid #243041;
  background: #121820;
}

.rule-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 8px;
}

.rule-title {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.rule-name {
  font-size: 15px;
  font-weight: 600;
  color: #e7ecf3;
}

.type-badge {
  flex-shrink: 0;
  font-size: 10px;
  font-weight: 600;
  padding: 3px 8px;
  border-radius: 999px;
  color: #7dffb2;
  background: #10261c;
  border: 1px solid #1e3d2e;
}

.rule-desc {
  margin: 0 0 8px;
  font-size: 13px;
  color: #8b9cb3;
  line-height: 1.45;
}

.rule-id {
  margin: 0;
  padding-top: 8px;
  border-top: 1px solid #243041;
  font-size: 11px;
  color: #6b7d94;
  word-break: break-all;
}

.table-wrap {
  overflow-x: auto;
  border: 1px solid #243041;
  border-radius: 12px;
}

table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

th,
td {
  padding: 10px 12px;
  border-bottom: 1px solid #243041;
  text-align: left;
  vertical-align: top;
}

th {
  color: #8b9cb3;
  background: #0b1016;
}

tbody tr {
  cursor: pointer;
}

tbody tr:hover {
  background: #152033;
}

tbody tr.active {
  background: #1a2840;
}

.ids,
.note {
  font-size: 12px;
  color: #8b9cb3;
  max-width: 360px;
  word-break: break-word;
}

.mono {
  font-family: ui-monospace, monospace;
  font-size: 11px;
}

.hint,
.error {
  font-size: 14px;
}

.hint {
  color: #8b9cb3;
}

.error {
  color: #ff8f8f;
}

.page.mobile .page-head h1 {
  font-size: 20px;
}

.page.mobile .date-select {
  min-height: 48px;
}
</style>
