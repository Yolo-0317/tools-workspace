<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  points: Array<{ x: string; y: number }>
  label?: string
  height?: number
}>()

const height = computed(() => props.height ?? 120)

const pathD = computed(() => {
  const pts = props.points.filter((p) => Number.isFinite(p.y))
  if (pts.length < 2) return ''
  const ys = pts.map((p) => p.y)
  const minY = Math.min(...ys)
  const maxY = Math.max(...ys)
  const span = maxY - minY || 1
  const w = 100
  const h = height.value - 24
  return pts
    .map((p, i) => {
      const x = (i / (pts.length - 1)) * w
      const y = h - ((p.y - minY) / span) * h + 12
      return `${i === 0 ? 'M' : 'L'}${x.toFixed(2)},${y.toFixed(2)}`
    })
    .join(' ')
})

const yRange = computed(() => {
  const ys = props.points.map((p) => p.y).filter(Number.isFinite)
  if (!ys.length) return { min: 0, max: 0 }
  return { min: Math.min(...ys), max: Math.max(...ys) }
})
</script>

<template>
  <div class="chart-wrap">
    <div v-if="label" class="label">{{ label }}</div>
    <svg
      v-if="pathD"
      viewBox="0 0 100 120"
      preserveAspectRatio="none"
      class="chart"
      :style="{ height: `${height}px` }"
    >
      <path :d="pathD" fill="none" stroke="#3b82f6" stroke-width="1.5" vector-effect="non-scaling-stroke" />
    </svg>
    <p v-else class="hint">数据不足，无法绘制曲线</p>
    <p v-if="points.length" class="range">
      {{ yRange.min.toLocaleString('zh-CN') }} ~ {{ yRange.max.toLocaleString('zh-CN') }}
    </p>
  </div>
</template>

<style scoped>
.chart-wrap {
  background: #0b1016;
  border-radius: 8px;
  padding: 10px;
}

.label {
  font-size: 12px;
  color: #8b9cb3;
  margin-bottom: 6px;
}

.chart {
  width: 100%;
  display: block;
}

.range {
  margin: 6px 0 0;
  font-size: 11px;
  color: #6b7c93;
}

.hint {
  margin: 0;
  font-size: 13px;
  color: #8b9cb3;
}
</style>
