<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import {
  fetchSelectionDates,
  fetchSelectionHistory,
  fetchSelectionStrategies,
} from '../api/dashboard'
import type { SelectionHistory } from '../types/dashboard'
import { selAction, selCode, selName, selPct, selScore } from '../utils/selection'

const strategies = ref<string[]>(['combined'])
const strategy = ref('combined')
const dates = ref<string[]>([])
const selectedDate = ref('')
const data = ref<SelectionHistory | null>(null)
const expandedSop = ref<number | null>(null)
const error = ref('')
const loading = ref(false)

function isHeld(code: string): boolean {
  const c = code.replace(/\D/g, '').slice(-6).padStart(6, '0')
  return (data.value?.holding_codes ?? []).includes(c)
}

async function loadDates() {
  const res = await fetchSelectionDates(strategy.value)
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
  try {
    data.value = await fetchSelectionHistory(selectedDate.value, strategy.value)
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
    data.value = null
  } finally {
    loading.value = false
  }
}

async function init() {
  error.value = ''
  try {
    const s = await fetchSelectionStrategies()
    strategies.value = s.strategies.length ? s.strategies : ['combined']
    if (!strategies.value.includes(strategy.value)) {
      strategy.value = strategies.value[0] ?? 'combined'
    }
    await loadDates()
    await loadSelection()
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  }
}

watch(selectedDate, loadSelection)

watch(strategy, async () => {
  selectedDate.value = ''
  await loadDates()
  await loadSelection()
})

onMounted(init)
</script>

<template>
  <div class="page">
    <div class="head">
      <h1>选股结果</h1>
      <div class="controls">
        <label>
          策略
          <select v-model="strategy">
            <option v-for="s in strategies" :key="s" :value="s">{{ s }}</option>
          </select>
        </label>
        <label>
          交易日
          <select v-model="selectedDate" :disabled="!dates.length">
            <option v-if="!dates.length" value="">暂无历史</option>
            <option v-for="d in dates" :key="d" :value="d">{{ d }}</option>
          </select>
        </label>
        <span class="meta">{{ strategy }} · 共 {{ dates.length }} 天</span>
      </div>
    </div>

    <p v-if="loading" class="hint">加载中…</p>
    <p v-if="error" class="error">{{ error }}</p>
    <p v-if="data && !loading" class="meta">
      {{ data.strategy }} · {{ data.trade_date }} · {{ data.count }} 条
    </p>

    <div v-if="data?.sop_review?.items?.length" class="table-wrap">
      <h2>SOP 审查</h2>
      <table>
        <thead>
          <tr>
            <th>#</th>
            <th>代码</th>
            <th>名称</th>
            <th>决策</th>
            <th>分</th>
            <th>持仓</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <template v-for="item in data.sop_review.items" :key="String(item.rank_no)">
            <tr>
              <td>{{ item.rank_no }}</td>
              <td>{{ item.code ?? item.ts_code }}</td>
              <td>{{ item.name }}</td>
              <td>{{ item.decision }}</td>
              <td>{{ item.score }}</td>
              <td>
                <span v-if="isHeld(String(item.code ?? item.ts_code))" class="tag held">已持有</span>
                <span v-else class="tag new">新标的</span>
              </td>
              <td>
                <button
                  v-if="item.review_md"
                  type="button"
                  class="link"
                  @click="expandedSop = expandedSop === Number(item.rank_no) ? null : Number(item.rank_no)"
                >
                  {{ expandedSop === Number(item.rank_no) ? '收起' : '详情' }}
                </button>
              </td>
            </tr>
            <tr v-if="expandedSop === Number(item.rank_no) && item.review_md" class="detail-row">
              <td colspan="7">
                <pre>{{ item.review_md }}</pre>
              </td>
            </tr>
          </template>
        </tbody>
      </table>
    </div>

    <div v-if="data?.rows?.length" class="table-wrap">
      <h2>全量列表（{{ data.rows.length }} 条）</h2>
      <table>
        <thead>
          <tr>
            <th>代码</th>
            <th>名称</th>
            <th>分</th>
            <th>涨跌幅</th>
            <th>建议</th>
            <th>持仓</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(row, i) in data.rows" :key="i">
            <td>{{ selCode(row) }}</td>
            <td>{{ selName(row) }}</td>
            <td>{{ selScore(row) }}</td>
            <td>{{ selPct(row) }}</td>
            <td>{{ selAction(row) || '—' }}</td>
            <td>
              <span v-if="isHeld(selCode(row))" class="tag held">已持有</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <p v-if="!loading && !error && selectedDate && !data?.rows?.length" class="hint">
      该日无选股记录
    </p>
  </div>
</template>

<style scoped>
.page h1 {
  margin: 0;
  font-size: 22px;
}

.head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.controls {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.controls label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: #8b9cb3;
}

select {
  background: #121820;
  color: #e7ecf3;
  border: 1px solid #243041;
  border-radius: 8px;
  padding: 6px 10px;
  font-size: 14px;
}

.meta {
  color: #8b9cb3;
  font-size: 13px;
  margin-bottom: 16px;
}

.hint {
  color: #8b9cb3;
}

.table-wrap {
  margin-bottom: 20px;
  overflow-x: auto;
  border: 1px solid #243041;
  border-radius: 12px;
  padding: 12px;
}

.table-wrap h2 {
  margin: 0 0 10px;
  font-size: 14px;
  color: #8b9cb3;
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
}

.detail-row pre {
  margin: 0;
  font-size: 12px;
  white-space: pre-wrap;
  color: #dbe7ff;
  max-height: 280px;
  overflow-y: auto;
}

.error {
  color: #ff8f8f;
}
</style>
