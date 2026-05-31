<script setup lang="ts">
import type { DisciplineAlert } from '../types/dashboard'

defineProps<{
  alerts: DisciplineAlert[]
  positionRatio?: number | null
  loading?: boolean
}>()

function levelClass(level: string) {
  if (level === 'danger') return 'danger'
  if (level === 'warn') return 'warn'
  return 'info'
}
</script>

<template>
  <section class="discipline">
    <h2>纪律 / 红线</h2>
    <p v-if="loading" class="hint">加载中…</p>
    <p v-else-if="positionRatio != null" class="ratio">
      当前仓位 <strong>{{ positionRatio.toFixed(1) }}%</strong>
      <span v-if="positionRatio >= 97" class="tag danger">≥97% 不宜新开仓</span>
    </p>
    <ul v-if="alerts.length">
      <li v-for="(a, i) in alerts" :key="i" :class="levelClass(a.level)">
        <span class="title">{{ a.title }}</span>
        <span class="msg">{{ a.message }}</span>
        <span v-if="a.code" class="code">{{ a.code }}</span>
      </li>
    </ul>
    <p v-else-if="!loading" class="hint">暂无触发项</p>
  </section>
</template>

<style scoped>
.discipline {
  background: #121820;
  border: 1px solid #243041;
  border-radius: 12px;
  padding: 16px;
}

h2 {
  margin: 0 0 10px;
  font-size: 14px;
  color: #8b9cb3;
}

.ratio {
  margin: 0 0 12px;
  font-size: 13px;
  color: #dbe7ff;
}

.tag {
  margin-left: 8px;
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 6px;
}

.tag.danger {
  background: #3a1515;
  color: #ffb4b4;
}

ul {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

li {
  padding: 10px 12px;
  border-radius: 8px;
  font-size: 13px;
  border: 1px solid #243041;
}

li.danger {
  border-color: #6b2a2a;
  background: #1a1010;
  color: #ffb4b4;
}

li.warn {
  border-color: #6b4f1f;
  background: #1a1608;
  color: #ffd27d;
}

li.info {
  border-color: #243041;
  background: #0f1419;
  color: #8b9cb3;
}

.title {
  font-weight: 600;
  margin-right: 6px;
}

.code {
  display: block;
  margin-top: 4px;
  font-size: 11px;
  opacity: 0.85;
}

.hint {
  margin: 0;
  color: #8b9cb3;
  font-size: 13px;
}
</style>
