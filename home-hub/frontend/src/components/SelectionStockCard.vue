<script setup lang="ts">
import StockKlinePanel from './StockKlinePanel.vue'
import StockProfilePanel from './StockProfilePanel.vue'
import type { DailyBar } from '../types/dashboard'
import {
  parseSelectionProfile,
  selAction,
  selExecutionCardNote,
  selCode,
  selConceptList,
  selIndustry,
  selName,
  selPct,
  selPctTone,
  selScore,
  selStrategy,
  strategyLabel,
} from '../utils/selection'

defineProps<{
  row: Record<string, unknown>
  held?: boolean
  showHeld?: boolean
  showSop?: boolean
  sopLoading?: boolean
  sopHint?: string
  profileOpen?: boolean
  klineOpen?: boolean
  klineLoading?: boolean
  klineBars?: DailyBar[]
  klineError?: string
  klineEndDate?: string
}>()

defineEmits<{
  toggleProfile: []
  toggleKline: []
  runSop: []
}>()
</script>

<template>
  <article class="stock-card">
    <div class="card-head">
      <div class="identity">
        <h3 class="name">{{ selName(row) }}</h3>
        <span class="code">{{ selCode(row) }}</span>
        <span class="tag strategy">{{ strategyLabel(selStrategy(row)) }}</span>
        <span v-if="showHeld && held" class="tag held">已持有</span>
      </div>
      <div class="score-badge">{{ selScore(row) }}</div>
    </div>

    <div class="card-stats">
      <span v-if="selIndustry(row) !== '—'" class="industry-pill">{{ selIndustry(row) }}</span>
      <span class="pct" :class="selPctTone(row)">{{ selPct(row) }}</span>
      <span v-if="selAction(row)" class="action-hint">{{ selAction(row) }}</span>
    </div>
    <p v-if="selExecutionCardNote(row)" class="exec-card-note">
      {{ selExecutionCardNote(row) }}
    </p>

    <div v-if="selConceptList(row).length" class="concept-row">
      <span v-for="tag in selConceptList(row).slice(0, 5)" :key="tag" class="chip">{{ tag }}</span>
      <span v-if="selConceptList(row).length > 5" class="chip muted">
        +{{ selConceptList(row).length - 5 }}
      </span>
    </div>

    <div class="card-actions" :class="{ 'with-sop': showSop }">
      <button
        v-if="parseSelectionProfile(row).hasContent"
        type="button"
        class="action-btn"
        :class="{ active: profileOpen }"
        @click="$emit('toggleProfile')"
      >
        {{ profileOpen ? '收起概况' : '概况' }}
      </button>
      <button
        type="button"
        class="action-btn"
        :class="{ active: klineOpen }"
        @click="$emit('toggleKline')"
      >
        {{ klineOpen ? '收起K线' : 'K线' }}
      </button>
      <button
        v-if="showSop"
        type="button"
        class="action-btn sop-btn"
        :disabled="sopLoading"
        @click="$emit('runSop')"
      >
        {{ sopLoading ? 'SOP中…' : '东财SOP' }}
      </button>
    </div>
    <p v-if="sopHint" class="sop-hint">{{ sopHint }}</p>

    <div v-if="profileOpen" class="card-expand">
      <StockProfilePanel :row="row" />
    </div>
    <div v-if="klineOpen" class="card-expand">
      <StockKlinePanel
        :bars="klineBars ?? []"
        :loading="klineLoading"
        :error="klineError"
        :end-date="klineEndDate"
      />
    </div>
  </article>
</template>

<style scoped>
.stock-card {
  padding: 14px;
  border-radius: 12px;
  background: #121820;
  border: 1px solid #243041;
}

.card-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 10px;
}

.identity {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 8px;
  min-width: 0;
}

.name {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #f0f4fa;
  line-height: 1.3;
}

.code {
  font-size: 12px;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  color: #7d8da6;
}

.score-badge {
  flex-shrink: 0;
  min-width: 36px;
  text-align: center;
  font-size: 15px;
  font-weight: 700;
  color: #93c5fd;
  padding: 4px 10px;
  border-radius: 8px;
  background: #152238;
  border: 1px solid #2a4060;
}

.card-stats {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}

.industry-pill {
  font-size: 11px;
  padding: 3px 8px;
  border-radius: 999px;
  background: #1a2230;
  color: #b8c5d9;
  border: 1px solid #2a3548;
}

.pct {
  font-size: 14px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.pct.up {
  color: #ff6b6b;
}

.pct.down {
  color: #7dffb2;
}

.pct.flat {
  color: #8b9cb3;
}

.action-hint {
  font-size: 12px;
  color: #8b9cb3;
  margin-left: auto;
}

.exec-card-note {
  margin: 0 0 10px;
  font-size: 12px;
  line-height: 1.45;
  color: #a8b8d0;
}

.concept-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 12px;
}

.chip {
  font-size: 10px;
  padding: 3px 7px;
  border-radius: 999px;
  background: #1a2230;
  color: #b8c5d9;
  border: 1px solid #2a3548;
}

.chip.muted {
  color: #8b9cb3;
  border-style: dashed;
  background: transparent;
}

.card-actions {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.card-actions.with-sop {
  grid-template-columns: repeat(3, 1fr);
}

.action-btn {
  min-height: 40px;
  border: 1px solid #2a3548;
  border-radius: 10px;
  background: #161e2a;
  color: #93c5fd;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
}

.action-btn:active {
  transform: scale(0.98);
}

.action-btn.active {
  background: #152238;
  border-color: #3b82f6;
  color: #dbe7ff;
}

.action-btn.sop-btn {
  color: #fcd34d;
  border-color: #4a4020;
  background: #1a1808;
}

.action-btn.sop-btn:disabled {
  opacity: 0.55;
  cursor: wait;
}

.sop-hint {
  margin: 8px 0 0;
  font-size: 12px;
  line-height: 1.4;
  color: #93c5fd;
}

.card-expand {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #243041;
}

.tag {
  font-size: 10px;
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
</style>
