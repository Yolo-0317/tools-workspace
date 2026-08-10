<script setup lang="ts">
import type { PortfolioWorkbench } from '../types/dashboard'
import { fmtNum } from '../api/dashboard'

defineProps<{ workbench: PortfolioWorkbench }>()

function signed(value: number | null | undefined): string {
  if (value == null) return '—'
  return `${value > 0 ? '+' : ''}${fmtNum(value)}`
}
</script>

<template>
  <section class="workbench">
    <header class="head">
      <div>
        <p class="eyebrow">账户操作台</p>
        <h2>{{ workbench.phase_label }}</h2>
      </div>
      <p class="source">{{ workbench.source }} · {{ workbench.as_of ?? '待更新' }}</p>
    </header>

    <div class="account-grid">
      <article><span>{{ workbench.account.principal_label }}</span><strong>¥{{ fmtNum(workbench.account.arrived_principal, 0) }}</strong></article>
      <article><span>科创资格目标</span><strong>¥{{ fmtNum(workbench.account.qualification_assets_target, 0) }}</strong></article>
      <article><span>实投交易预算</span><strong>¥{{ fmtNum(workbench.account.trading_budget, 0) }}</strong></article>
      <article><span>累计损益</span><strong :class="{ down: (workbench.account.cumulative_pnl ?? 0) < 0, up: (workbench.account.cumulative_pnl ?? 0) > 0 }">{{ signed(workbench.account.cumulative_pnl) }}</strong></article>
      <article><span>持仓浮盈</span><strong :class="{ down: (workbench.account.holding_pnl ?? 0) < 0, up: (workbench.account.holding_pnl ?? 0) > 0 }">{{ signed(workbench.account.holding_pnl) }}</strong></article>
    </div>

    <div class="ratio-grid">
      <p><span>账户内仓位</span><strong>{{ workbench.account.account_position_pct?.toFixed(1) ?? '—' }}%</strong><small>证券市值 / 当前总资产</small></p>
      <p><span>交易预算暴露</span><strong>{{ workbench.account.trading_budget_exposure_pct?.toFixed(1) ?? '—' }}%</strong><small>证券市值 / 10 万实投预算</small></p>
      <p><span>资格目标进度</span><strong>{{ workbench.account.plan_arrived_pct?.toFixed(1) ?? '—' }}%</strong><small>已到位本金 / 55 万资格目标</small></p>
    </div>

    <div class="section-grid">
      <section>
        <h3>行动队列</h3>
        <article v-for="action in workbench.actions" :key="action.title" class="action-card">
          <span class="level">{{ action.level }}</span>
          <strong>{{ action.title }}</strong>
          <p>{{ action.detail }}</p>
          <small>条件：{{ action.condition }}</small>
        </article>
      </section>
      <section>
        <h3>主题暴露</h3>
        <article v-for="theme in workbench.themes" :key="theme.name" class="theme-row">
          <div><strong>{{ theme.name }}</strong><small>¥{{ fmtNum(theme.market_value, 0) }}</small></div>
          <div class="theme-pct" :class="{ over: theme.over_limit }">
            {{ theme.weight_pct.toFixed(1) }}%
            <small v-if="theme.target_max_pct != null">上限 {{ theme.target_max_pct }}%</small>
          </div>
        </article>
      </section>
    </div>
  </section>
</template>

<style scoped>
.workbench { margin-bottom: 16px; padding: 16px; border: 1px solid #2d3a4d; border-radius: 12px; background: linear-gradient(135deg, #152334, #121820); }
.head { display: flex; justify-content: space-between; gap: 12px; align-items: start; margin-bottom: 14px; }.eyebrow, .source, small { color: #8b9cb3; font-size: 12px; }.eyebrow { margin: 0 0 3px; }.head h2 { margin: 0; font-size: 17px; }.source { margin: 2px 0 0; text-align: right; }
.account-grid, .ratio-grid, .section-grid { display: grid; gap: 10px; }.account-grid { grid-template-columns: repeat(5, minmax(0, 1fr)); }.account-grid article, .ratio-grid p, .action-card, .theme-row { margin: 0; padding: 11px; border: 1px solid #243041; border-radius: 9px; background: #111923; }.account-grid span, .ratio-grid span { display: block; color: #8b9cb3; font-size: 11px; }.account-grid strong { display: block; margin-top: 4px; font-size: 16px; font-variant-numeric: tabular-nums; }
.ratio-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); margin-top: 10px; }.ratio-grid strong { display: block; margin: 3px 0; font-size: 18px; }.ratio-grid small { display: block; }.section-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); margin-top: 16px; }.section-grid section h3 { margin: 0 0 8px; color: #8b9cb3; font-size: 13px; }.action-card { margin-bottom: 8px; }.action-card:last-child { margin-bottom: 0; }.action-card strong { display: block; font-size: 14px; }.action-card p { margin: 6px 0; color: #c5d4ea; font-size: 13px; line-height: 1.45; }.level { display: inline-block; margin-bottom: 5px; padding: 2px 6px; color: #8fcbff; border: 1px solid #285076; border-radius: 999px; font-size: 11px; }.theme-row { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }.theme-row:last-child { margin-bottom: 0; }.theme-row strong, .theme-row small { display: block; }.theme-pct { text-align: right; color: #b8c5d9; font-variant-numeric: tabular-nums; }.theme-pct.over { color: #ffd27d; }.down { color: #ff9c9c; }.up { color: #7dffb2; }
@media (max-width: 720px) { .head { display: block; }.source { margin-top: 8px; text-align: left; }.account-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }.ratio-grid, .section-grid { grid-template-columns: 1fr; } }
</style>
