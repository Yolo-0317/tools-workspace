<script setup lang="ts">
import StockKlinePanel from './StockKlinePanel.vue'
import type { DailyBar } from '../types/dashboard'
import { sopName } from '../utils/selection'

defineProps<{
  item: Record<string, unknown>
  held?: boolean
  showHeld?: boolean
  sopOpen?: boolean
  klineOpen?: boolean
  klineLoading?: boolean
  klineBars?: DailyBar[]
  klineError?: string
  klineEndDate?: string
}>()

defineEmits<{
  toggleSop: []
  toggleKline: []
}>()
</script>

<template>
  <article class="sop-card">
    <div class="card-head">
      <span class="rank">#{{ item.rank_no }}</span>
      <div class="identity">
        <h3 class="name">{{ sopName(item) }}</h3>
        <span class="code">{{ item.code ?? item.ts_code }}</span>
      </div>
      <div class="score-badge">{{ item.score }}</div>
    </div>

    <div class="card-meta">
      <span class="decision">{{ item.decision }}</span>
      <span v-if="showHeld && held" class="tag held">已持有</span>
      <span v-else-if="showHeld" class="tag new">新标的</span>
    </div>

    <div class="card-actions">
      <button
        v-if="item.review_md"
        type="button"
        class="action-btn"
        :class="{ active: sopOpen }"
        @click="$emit('toggleSop')"
      >
        {{ sopOpen ? '收起详情' : 'SOP详情' }}
      </button>
      <button
        type="button"
        class="action-btn"
        :class="{ active: klineOpen }"
        @click="$emit('toggleKline')"
      >
        {{ klineOpen ? '收起K线' : 'K线' }}
      </button>
    </div>

    <div v-if="sopOpen && item.review_md" class="card-expand">
      <pre class="review-md">{{ item.review_md }}</pre>
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
.sop-card {
  padding: 14px;
  border-radius: 12px;
  background: linear-gradient(145deg, #141c28 0%, #121820 100%);
  border: 1px solid #2a4060;
}

.card-head {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  margin-bottom: 8px;
}

.rank {
  flex-shrink: 0;
  font-size: 12px;
  font-weight: 700;
  color: #60a5fa;
  padding-top: 2px;
}

.identity {
  flex: 1;
  min-width: 0;
}

.name {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: #f0f4fa;
}

.code {
  font-size: 11px;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  color: #7d8da6;
}

.score-badge {
  flex-shrink: 0;
  font-size: 14px;
  font-weight: 700;
  color: #93c5fd;
}

.card-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.decision {
  font-size: 13px;
  color: #dbe7ff;
}

.card-actions {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.action-btn {
  min-height: 40px;
  border: 1px solid #2a3548;
  border-radius: 10px;
  background: #161e2a;
  color: #93c5fd;
  font-size: 13px;
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
}

.action-btn.active {
  background: #152238;
  border-color: #3b82f6;
  color: #dbe7ff;
}

.card-expand {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #243041;
}

.review-md {
  margin: 0;
  font-size: 12px;
  line-height: 1.6;
  white-space: pre-wrap;
  color: #dbe7ff;
  max-height: 50vh;
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
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

.tag.new {
  background: #1a2840;
  color: #93c5fd;
}
</style>
