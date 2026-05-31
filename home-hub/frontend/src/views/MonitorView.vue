<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import {
  fetchMonitorDates,
  fetchMonitorRules,
  fetchMonitorState,
} from '../api/dashboard'
import type { MonitorHistoryDay, MonitorRule, MonitorState } from '../types/dashboard'

const rules = ref<MonitorRule[]>([])
const history = ref<MonitorHistoryDay[]>([])
const selectedDate = ref('')
const state = ref<MonitorState | null>(null)
const error = ref('')
const loading = ref(false)

const today = new Date().toISOString().slice(0, 10)

const firedDetails = computed(() => state.value?.fired_details ?? [])

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
  loading.value = true
  error.value = ''
  try {
    state.value = await fetchMonitorState(selectedDate.value)
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
    state.value = null
  } finally {
    loading.value = false
  }
}

async function init() {
  error.value = ''
  try {
    const r = await fetchMonitorRules()
    rules.value = r.rules
    await loadHistory()
    await loadState()
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  }
}

watch(selectedDate, loadState)

onMounted(init)
</script>

<template>
  <div class="page">
    <div class="head">
      <h1>盘中监控</h1>
      <label>
        日期
        <select v-model="selectedDate">
          <option v-for="h in history" :key="h.date" :value="h.date">
            {{ h.date }}（{{ h.fired_count }} 条触发）
          </option>
          <option v-if="!history.length" :value="today">{{ today }}（今日）</option>
        </select>
      </label>
    </div>

    <p v-if="error" class="error">{{ error }}</p>
    <p v-if="loading" class="hint">加载中…</p>
    <p v-else-if="state" class="meta">
      {{ state.date }}
      · 已触发 {{ state.fired.length }} 条
      <span v-if="!state.exists" class="warn">（该日无状态文件）</span>
    </p>

    <section v-if="firedDetails.length" class="block fired">
      <h2>已触发</h2>
      <ul>
        <li v-for="item in firedDetails" :key="item.id">
          <code>{{ item.id }}</code>
          <span v-if="item.name"> · {{ item.name }}</span>
          <span v-if="item.ts_code">（{{ item.ts_code }}）</span>
          <span v-if="item.note" class="note"> — {{ item.note }}</span>
        </li>
      </ul>
    </section>
    <section v-else-if="state && !state.fired.length" class="block empty">
      <p class="hint">该日无触发记录</p>
    </section>

    <section v-if="history.length > 1" class="block history">
      <h2>历史摘要</h2>
      <div class="table-wrap">
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

    <div class="table-wrap rules">
      <h2>当前规则（{{ rules.length }}）</h2>
      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>代码</th>
            <th>名称</th>
            <th>类型</th>
            <th>说明</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="rule in rules" :key="String(rule.id)">
            <td class="mono">{{ rule.id }}</td>
            <td>{{ rule.code ?? rule.ts_code }}</td>
            <td>{{ rule.name }}</td>
            <td>{{ rule.type ?? rule.rule_type }}</td>
            <td class="note">{{ rule.message ?? rule.note }}</td>
          </tr>
        </tbody>
      </table>
    </div>
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

.head label {
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

.warn {
  color: #ffb4b4;
}

.block {
  margin-bottom: 16px;
  padding: 12px;
  border-radius: 12px;
  border: 1px solid #243041;
  background: #121820;
}

.block h2 {
  margin: 0 0 10px;
  font-size: 14px;
  color: #8b9cb3;
}

.fired {
  border-color: #4a3030;
  background: #1a1010;
}

.fired ul {
  margin: 0;
  padding-left: 18px;
  color: #ffb4b4;
  font-size: 13px;
}

.fired code {
  color: #ffd4a8;
}

.note {
  color: #8b9cb3;
}

.history tbody tr {
  cursor: pointer;
}

.history tbody tr:hover {
  background: #152033;
}

.history tbody tr.active {
  background: #1a2840;
}

.table-wrap {
  overflow-x: auto;
  border: 1px solid #243041;
  border-radius: 12px;
}

.rules {
  margin-top: 20px;
}

.rules h2 {
  margin: 0;
  padding: 12px 12px 0;
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
  padding: 10px 12px;
  border-bottom: 1px solid #243041;
  text-align: left;
}

th {
  color: #8b9cb3;
  background: #0b1016;
}

.ids {
  font-size: 12px;
  color: #dbe7ff;
  max-width: 360px;
}

.mono {
  font-family: ui-monospace, monospace;
  font-size: 12px;
}

.hint {
  color: #8b9cb3;
}

.error {
  color: #ff8f8f;
}
</style>
