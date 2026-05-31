<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, shallowRef, watch } from 'vue'
import * as echarts from 'echarts/core'
import { CandlestickChart, LineChart } from 'echarts/charts'
import {
  AxisPointerComponent,
  GridComponent,
  LegendComponent,
  TooltipComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import type { EChartsOption } from 'echarts'
import type { EChartsType } from 'echarts/core'
import type { DailyBar } from '../types/dashboard'
import type { CallbackDataParams } from 'echarts/types/dist/shared'

echarts.use([
  CandlestickChart,
  LineChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  AxisPointerComponent,
  CanvasRenderer,
])

const props = defineProps<{
  bars: DailyBar[]
  loading?: boolean
  error?: string
  endDate?: string
}>()

const chartEl = ref<HTMLDivElement | null>(null)
const chartRef = shallowRef<EChartsType | null>(null)
let resizeObserver: ResizeObserver | null = null

const MA_CONFIG = [
  { period: 5, label: 'MA5', color: '#fbbf24' },
  { period: 10, label: 'MA10', color: '#a78bfa' },
  { period: 20, label: 'MA20', color: '#38bdf8' },
] as const

const validBarList = computed(() =>
  props.bars.filter(
    (b) =>
      b.open != null &&
      b.high != null &&
      b.low != null &&
      b.close != null &&
      Number(b.high) >= Number(b.low),
  ),
)

const canRender = computed(
  () => !props.loading && !props.error && validBarList.value.length > 0,
)

function movingAverage(closes: number[], period: number): (number | null)[] {
  return closes.map((_, i) => {
    if (i < period - 1) return null
    const slice = closes.slice(i - period + 1, i + 1)
    return slice.reduce((a, b) => a + b, 0) / period
  })
}

function fmtDate(d: string): string {
  const s = String(d).replace(/-/g, '')
  if (s.length === 8) return `${s.slice(4, 6)}-${s.slice(6, 8)}`
  return d
}

function fmtPrice(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(Number(v))) return '—'
  return Number(v).toFixed(2)
}

function fmtPct(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(Number(v))) return '—'
  const n = Number(v)
  return `${n >= 0 ? '+' : ''}${n.toFixed(2)}%`
}

function buildOption(bars: DailyBar[]): EChartsOption {
  const valid = bars.filter(
    (b) =>
      b.open != null &&
      b.high != null &&
      b.low != null &&
      b.close != null &&
      Number(b.high) >= Number(b.low),
  )

  const dates = valid.map((b) => fmtDate(b.trade_date))
  const ohlc = valid.map((b) => [
    Number(b.open),
    Number(b.close),
    Number(b.low),
    Number(b.high),
  ])
  const closes = valid.map((b) => Number(b.close))
  const mas = MA_CONFIG.map((cfg) => ({
    ...cfg,
    data: movingAverage(closes, cfg.period),
  }))

  return {
    backgroundColor: 'transparent',
    animation: false,
    legend: {
      top: 4,
      left: 8,
      itemWidth: 14,
      itemHeight: 8,
      textStyle: { color: '#8b9cb3', fontSize: 11 },
      data: ['K线', ...MA_CONFIG.map((m) => m.label)],
    },
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'cross',
        crossStyle: { color: '#475569' },
        lineStyle: { color: '#334155', type: 'dashed' },
      },
      backgroundColor: 'rgba(15, 20, 25, 0.96)',
      borderColor: '#243041',
      borderWidth: 1,
      padding: [10, 12],
      textStyle: { color: '#e7ecf3', fontSize: 12 },
      formatter(params: CallbackDataParams | CallbackDataParams[]) {
        const items = Array.isArray(params) ? params : [params]
        const idx = items[0]?.dataIndex
        if (idx == null || idx < 0) return ''
        const bar = valid[idx]
        const k = ohlc[idx]
        if (!bar || !k) return ''
        const lines = [
          `<div style="font-weight:600;margin-bottom:6px">${bar.trade_date}</div>`,
          `开 <span style="float:right;margin-left:12px">${fmtPrice(k[0])}</span>`,
          `高 <span style="float:right;margin-left:12px">${fmtPrice(k[3])}</span>`,
          `低 <span style="float:right;margin-left:12px">${fmtPrice(k[2])}</span>`,
          `收 <span style="float:right;margin-left:12px">${fmtPrice(k[1])}</span>`,
          `涨跌 <span style="float:right;margin-left:12px;color:${Number(bar.pct_chg) >= 0 ? '#f87171' : '#4ade80'}">${fmtPct(bar.pct_chg)}</span>`,
        ]
        for (const ma of mas) {
          const v = ma.data[idx]
          lines.push(
            `${ma.label} <span style="float:right;margin-left:12px;color:${ma.color}">${fmtPrice(v)}</span>`,
          )
        }
        return lines.join('<br/>')
      },
    },
    grid: {
      left: 52,
      right: 14,
      top: 36,
      bottom: 28,
    },
    xAxis: {
      type: 'category',
      data: dates,
      boundaryGap: true,
      axisLine: { lineStyle: { color: '#243041' } },
      axisTick: { show: false },
      axisLabel: { color: '#6b7c93', fontSize: 10, interval: 'auto' },
    },
    yAxis: {
      scale: true,
      splitLine: { lineStyle: { color: '#1a2433', type: 'dashed' } },
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: {
        color: '#6b7c93',
        fontSize: 10,
        formatter: (v: number) => (v >= 1000 ? `${(v / 1000).toFixed(1)}k` : String(v)),
      },
    },
    series: [
      {
        name: 'K线',
        type: 'candlestick',
        data: ohlc,
        itemStyle: {
          color: '#ef4444',
          color0: '#22c55e',
          borderColor: '#ef4444',
          borderColor0: '#22c55e',
        },
      },
      ...mas.map((ma) => ({
        name: ma.label,
        type: 'line' as const,
        data: ma.data,
        smooth: false,
        showSymbol: false,
        lineStyle: { width: 1.5, color: ma.color },
        connectNulls: false,
      })),
    ],
  }
}

function disposeChart() {
  chartRef.value?.dispose()
  chartRef.value = null
}

async function renderChart() {
  await nextTick()
  if (!chartEl.value) return

  if (!canRender.value) {
    disposeChart()
    return
  }

  if (!chartRef.value) {
    chartRef.value = echarts.init(chartEl.value, undefined, { renderer: 'canvas' })
  }

  chartRef.value.setOption(buildOption(validBarList.value), { notMerge: true, lazyUpdate: false })

  requestAnimationFrame(() => {
    chartRef.value?.resize()
  })
}

watch(canRender, () => {
  void renderChart()
})

watch(
  () => props.bars,
  () => {
    if (canRender.value) void renderChart()
  },
  { deep: true },
)

onMounted(() => {
  void renderChart()
  if (chartEl.value) {
    resizeObserver = new ResizeObserver(() => chartRef.value?.resize())
    resizeObserver.observe(chartEl.value)
  }
})

onUnmounted(() => {
  resizeObserver?.disconnect()
  resizeObserver = null
  disposeChart()
})
</script>

<template>
  <div class="kline-panel">
    <p v-if="error" class="error">{{ error }}</p>
    <template v-else>
      <div class="chart-shell">
        <div ref="chartEl" class="chart-el" aria-label="日K线图" />
        <p v-if="loading" class="overlay hint">K 线加载中…</p>
        <p v-else-if="!canRender" class="overlay hint">
          {{ bars.length ? 'K 线数据无效' : '暂无 K 线数据（检查 stock_daily 同步）' }}
        </p>
      </div>
      <p v-if="canRender" class="meta">
        {{ validBarList.length }} 个交易日
        <template v-if="endDate || validBarList.length">
          · 至 {{ endDate || validBarList[validBarList.length - 1]?.trade_date }}
        </template>
      </p>
    </template>
  </div>
</template>

<style scoped>
.kline-panel {
  padding: 4px 0;
  min-width: 280px;
}

.chart-shell {
  position: relative;
}

.chart-el {
  width: 100%;
  min-width: 260px;
  height: 220px;
  background: #0b1016;
  border: 1px solid #1e293b;
  border-radius: 8px;
}

.overlay {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0;
  background: rgba(11, 16, 22, 0.88);
  border-radius: 8px;
  pointer-events: none;
}

.meta {
  margin: 6px 0 0;
  font-size: 11px;
  color: #6b7c93;
}

.hint {
  color: #8b9cb3;
  font-size: 13px;
}

.error {
  color: #ff8f8f;
  margin: 0;
  font-size: 13px;
}

@media (max-width: 768px) {
  .kline-panel {
    min-width: 0;
  }

  .chart-el {
    min-width: 0;
    height: 240px;
  }
}
</style>
