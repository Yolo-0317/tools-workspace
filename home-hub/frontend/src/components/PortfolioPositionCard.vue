<script setup lang="ts">
import type { PositionRow } from '../types/dashboard'
import {
  fmtNum,
} from '../api/dashboard'
import {
  posAction,
  posCode,
  posCost,
  posPnl,
  posPnlPct,
  posPrice,
  posStatus,
  posStatusTone,
} from '../utils/portfolio'

defineProps<{
  position: PositionRow
}>()

function fmtPct(v: number | null): string {
  if (v == null || Number.isNaN(v)) return '—'
  const pct = Math.abs(v) <= 1 ? v * 100 : v
  const sign = pct > 0 ? '+' : ''
  return `${sign}${pct.toFixed(1)}%`
}
</script>

<template>
  <article class="pos-card" :class="posStatusTone(position)">
    <div class="card-head">
      <div class="identity">
        <h3 class="name">{{ position.name ?? '—' }}</h3>
        <span class="code">{{ posCode(position) }}</span>
      </div>
      <span v-if="posStatus(position)" class="status-badge">{{ posStatus(position) }}</span>
    </div>

    <div class="metric-grid">
      <div class="metric">
        <span class="label">股数</span>
        <span class="value">{{ position.shares ?? '—' }}</span>
      </div>
      <div class="metric">
        <span class="label">成本</span>
        <span class="value">{{ fmtNum(posCost(position)) }}</span>
      </div>
      <div class="metric">
        <span class="label">现价</span>
        <span class="value">{{ fmtNum(posPrice(position)) }}</span>
      </div>
      <div class="metric">
        <span class="label">盈亏</span>
        <span
          class="value pnl"
          :class="{ up: Number(posPnl(position)) > 0, down: Number(posPnl(position)) < 0 }"
        >
          {{ fmtNum(posPnl(position)) }}
          <small v-if="posPnlPct(position) != null">({{ fmtPct(posPnlPct(position)) }})</small>
        </span>
      </div>
    </div>

    <p v-if="posAction(position) !== '—'" class="action-note">{{ posAction(position) }}</p>
  </article>
</template>

<style scoped>
.pos-card {
  padding: 14px;
  border-radius: 12px;
  background: #121820;
  border: 1px solid #243041;
}

.pos-card.good {
  border-color: #1f4a35;
}

.pos-card.bad {
  border-color: #5a2525;
}

.pos-card.warn {
  border-color: #4a3a18;
}

.card-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 12px;
}

.identity {
  min-width: 0;
}

.name {
  margin: 0;
  font-size: 17px;
  font-weight: 600;
  line-height: 1.25;
}

.code {
  display: block;
  margin-top: 2px;
  font-size: 12px;
  color: #7d8da6;
  font-variant-numeric: tabular-nums;
}

.status-badge {
  flex-shrink: 0;
  max-width: 42%;
  font-size: 11px;
  line-height: 1.35;
  padding: 4px 8px;
  border-radius: 999px;
  background: #1a2230;
  color: #b8c5d9;
  text-align: right;
}

.pos-card.good .status-badge {
  background: #10261c;
  color: #7dffb2;
}

.pos-card.bad .status-badge {
  background: #2a1212;
  color: #ffb4b4;
}

.pos-card.warn .status-badge {
  background: #2a2210;
  color: #ffd27d;
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px 14px;
}

.metric {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.label {
  font-size: 11px;
  color: #7d8da6;
  letter-spacing: 0.03em;
}

.value {
  font-size: 15px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.value.pnl small {
  font-size: 12px;
  font-weight: 500;
  margin-left: 2px;
}

.up {
  color: #7dffb2;
}

.down {
  color: #ff8f8f;
}

.action-note {
  margin: 12px 0 0;
  padding-top: 10px;
  border-top: 1px solid #243041;
  font-size: 13px;
  line-height: 1.45;
  color: #c5d4ea;
}
</style>
