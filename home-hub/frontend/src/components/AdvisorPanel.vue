<script setup lang="ts">
import { computed } from 'vue'
import type { AdvisorPayload } from '../types/dashboard'
import { fmtNum } from '../api/dashboard'

const props = defineProps<{
  advisor: AdvisorPayload | null | undefined
  compact?: boolean
}>()

const a = computed(() => props.advisor)
const progressWidth = computed(() => {
  const p = a.value?.progress_pct ?? 0
  return `${Math.min(100, Math.max(0, p))}%`
})

const tierClass = computed(() => {
  const t = a.value?.position_tier ?? ''
  if (t === 'A') return 'tier-a'
  if (t === 'B') return 'tier-b'
  return 'tier-c'
})

const healthClass = computed(() => {
  const s = a.value?.diagnosis?.health_score ?? 0
  if (s >= 75) return 'health-good'
  if (s >= 55) return 'health-mid'
  return 'health-low'
})
</script>

<template>
  <section v-if="a && !a.error" class="advisor" :class="{ compact }">
    <header class="advisor-head">
      <span class="phase-badge">{{ a.phase_label }}</span>
      <span class="tier" :class="tierClass">仓位 {{ a.position_tier }} 档</span>
      <span v-if="a.selection?.mode_label" class="sel-mode">{{ a.selection.mode_label }}</span>
      <span v-if="a.diagnosis" class="health-badge" :class="healthClass">
        健康 {{ a.diagnosis.health_score }} · {{ a.diagnosis.health_label }}
      </span>
    </header>

    <p v-if="a.banner" class="banner">{{ a.banner }}</p>

    <div v-if="!compact" class="recovery">
      <div class="recovery-labels">
        <span>回本进度</span>
        <span class="recovery-nums">
          ¥{{ fmtNum(a.total_assets, 0) }} / {{ fmtNum(a.principal_cny, 0) }}
          <template v-if="a.gap_to_principal > 0">
            · 还差约 ¥{{ fmtNum(a.gap_to_principal, 0) }}
          </template>
        </span>
      </div>
      <div class="bar-track" role="progressbar" :aria-valuenow="a.progress_pct">
        <div class="bar-fill" :style="{ width: progressWidth }" />
      </div>
      <p class="recovery-sub">
        完成度 {{ a.progress_pct?.toFixed(1) }}%
        <template v-if="a.need_return_pct > 0">
          · 尚需约 +{{ a.need_return_pct?.toFixed(1) }}%（相对现净资产）
        </template>
        <template v-if="a.position_ratio_pct != null">
          · 仓位 {{ a.position_ratio_pct?.toFixed(1) }}%
        </template>
      </p>
    </div>

    <div v-if="a.diagnosis && !compact" class="block diagnosis">
      <h3>账户诊断</h3>
      <ul v-if="a.diagnosis.issues?.length" class="diag-list">
        <li
          v-for="(issue, i) in a.diagnosis.issues.slice(0, 4)"
          :key="i"
          :class="issue.severity"
        >
          <strong>{{ issue.title }}</strong> — {{ issue.detail }}
        </li>
      </ul>
      <p v-if="a.diagnosis.rebalance_priority?.length" class="rebalance">
        再平衡：{{ a.diagnosis.rebalance_priority.join(' → ') }}
      </p>
      <p v-if="a.diagnosis.education_tip" class="edu-tip">{{ a.diagnosis.education_tip }}</p>
    </div>
    <p v-else-if="a.diagnosis && compact && a.diagnosis.rebalance_priority?.length" class="hint">
      再平衡：{{ a.diagnosis.rebalance_priority.slice(0, 2).join(' → ') }}
    </p>

    <div v-if="a.weekly_must_do?.length" class="block">
      <h3>本周必做（投顾）</h3>
      <ol class="tasks">
        <li v-for="(t, i) in a.weekly_must_do" :key="i">
          <strong>{{ t.title }}</strong>
          <span v-if="t.detail"> — {{ t.detail }}</span>
        </li>
      </ol>
    </div>

    <div v-if="!compact && a.weekly_forbidden?.length" class="block forbid">
      <h3>本周不做</h3>
      <ul>
        <li v-for="(f, i) in a.weekly_forbidden" :key="i">{{ f }}</li>
      </ul>
    </div>

    <p v-if="a.selection && !a.selection.sop_top5_enabled" class="hint">
      阶段 0：Top5 不跑 SOP、不写选股监控；列表仅供观察。
    </p>
  </section>
  <p v-else-if="a?.error" class="advisor-error">投顾数据加载失败：{{ a.error }}</p>
</template>

<style scoped>
.advisor {
  background: linear-gradient(135deg, #1a2332 0%, #15202b 100%);
  border: 1px solid #2d3a4d;
  border-radius: 10px;
  padding: 1rem 1.1rem;
  margin-bottom: 1.25rem;
}

.advisor.compact {
  padding: 0.75rem 0.9rem;
  margin-bottom: 0.75rem;
}

.advisor-head {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem 0.75rem;
  align-items: center;
  margin-bottom: 0.5rem;
}

.phase-badge {
  font-weight: 700;
  font-size: 0.95rem;
  color: #7dd3fc;
}

.tier {
  font-size: 0.8rem;
  padding: 0.15rem 0.5rem;
  border-radius: 4px;
  background: #243044;
}

.tier-a {
  color: #fca5a5;
  border: 1px solid #7f1d1d;
}

.tier-b {
  color: #fcd34d;
  border: 1px solid #78350f;
}

.tier-c {
  color: #86efac;
  border: 1px solid #14532d;
}

.sel-mode {
  font-size: 0.8rem;
  color: #94a3b8;
}

.health-badge {
  font-size: 0.75rem;
  padding: 0.15rem 0.45rem;
  border-radius: 4px;
  border: 1px solid #334155;
}

.health-good {
  color: #86efac;
  border-color: #14532d;
}

.health-mid {
  color: #fcd34d;
  border-color: #78350f;
}

.health-low {
  color: #fca5a5;
  border-color: #7f1d1d;
}

.diagnosis .diag-list {
  margin: 0;
  padding-left: 1.1rem;
  font-size: 0.82rem;
  line-height: 1.45;
}

.diagnosis .diag-list li.high {
  color: #fca5a5;
}

.diagnosis .diag-list li.warn {
  color: #fde68a;
}

.rebalance,
.edu-tip {
  margin: 0.5rem 0 0;
  font-size: 0.78rem;
  color: #94a3b8;
  line-height: 1.45;
}

.edu-tip {
  color: #cbd5e1;
  font-style: italic;
}

.banner {
  font-size: 0.85rem;
  color: #cbd5e1;
  margin: 0 0 0.75rem;
  line-height: 1.45;
}

.recovery {
  margin-bottom: 0.85rem;
}

.recovery-labels {
  display: flex;
  justify-content: space-between;
  flex-wrap: wrap;
  font-size: 0.85rem;
  margin-bottom: 0.35rem;
}

.recovery-nums {
  color: #e2e8f0;
}

.bar-track {
  height: 8px;
  background: #0f172a;
  border-radius: 4px;
  overflow: hidden;
}

.bar-fill {
  height: 100%;
  background: linear-gradient(90deg, #0369a1, #22d3ee);
  transition: width 0.3s ease;
}

.recovery-sub {
  font-size: 0.78rem;
  color: #94a3b8;
  margin: 0.35rem 0 0;
}

.block h3 {
  font-size: 0.85rem;
  margin: 0 0 0.4rem;
  color: #94a3b8;
  font-weight: 600;
}

.tasks {
  margin: 0;
  padding-left: 1.2rem;
  font-size: 0.88rem;
  line-height: 1.5;
}

.tasks strong {
  color: #f1f5f9;
}

.forbid ul {
  margin: 0;
  padding-left: 1.1rem;
  font-size: 0.82rem;
  color: #fca5a5;
}

.hint {
  font-size: 0.78rem;
  color: #64748b;
  margin: 0.5rem 0 0;
}

.advisor-error {
  color: #f87171;
  font-size: 0.85rem;
}
</style>
