<script setup lang="ts">
withDefaults(
  defineProps<{
    variant?: 'home' | 'portfolio' | 'cards' | 'block'
    label?: string
  }>(),
  {
    variant: 'home',
    label: '加载中',
  },
)
</script>

<template>
  <div class="dash-loading" :class="[`variant-${variant}`]" aria-busy="true" aria-live="polite">
    <p class="dash-loading-label">
      <span class="dash-loading-spinner" aria-hidden="true" />
      {{ label }}<span class="dash-loading-dots" aria-hidden="true"><span>.</span><span>.</span><span>.</span></span>
    </p>

    <div v-if="variant === 'home'" class="skeleton-home">
      <div class="sk-advisor">
        <div class="sk-row">
          <span class="sk sk-badge" />
          <span class="sk sk-badge sk-badge-sm" />
          <span class="sk sk-badge sk-badge-sm" />
        </div>
        <span class="sk sk-line sk-line-wide" />
        <span class="sk sk-line sk-line-md" />
        <span class="sk sk-bar" />
        <span class="sk sk-line sk-line-sm" />
      </div>
      <div class="sk-cards">
        <article v-for="i in 4" :key="i" class="sk-card">
          <span class="sk sk-line sk-line-xs" />
          <span class="sk sk-line sk-line-lg" />
          <span class="sk sk-line sk-line-sm" />
        </article>
      </div>
      <div class="sk-block">
        <span class="sk sk-line sk-line-xs" />
        <span class="sk sk-chart" />
      </div>
    </div>

    <div v-else-if="variant === 'portfolio'" class="skeleton-portfolio">
      <div class="sk-advisor sk-advisor-compact">
        <div class="sk-row">
          <span class="sk sk-badge" />
          <span class="sk sk-badge sk-badge-sm" />
        </div>
        <span class="sk sk-line sk-line-wide" />
      </div>
      <div class="sk-stats">
        <article v-for="i in 4" :key="i" class="sk-stat">
          <span class="sk sk-line sk-line-xs" />
          <span class="sk sk-line sk-line-md" />
        </article>
      </div>
      <div class="sk-positions">
        <article v-for="i in 3" :key="i" class="sk-position">
          <span class="sk sk-line sk-line-md" />
          <span class="sk sk-line sk-line-sm" />
        </article>
      </div>
    </div>

    <div v-else-if="variant === 'cards'" class="sk-cards">
      <article v-for="i in 4" :key="i" class="sk-card">
        <span class="sk sk-line sk-line-xs" />
        <span class="sk sk-line sk-line-lg" />
        <span class="sk sk-line sk-line-sm" />
      </article>
    </div>

    <div v-else class="sk-block">
      <span class="sk sk-line sk-line-xs" />
      <span class="sk sk-line sk-line-wide" />
      <span class="sk sk-line sk-line-md" />
      <span class="sk sk-line sk-line-sm" />
    </div>
  </div>
</template>

<style scoped>
.dash-loading {
  margin-bottom: 16px;
}

.dash-loading-label {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0 0 14px;
  font-size: 13px;
  color: #8b9cb3;
}

.dash-loading-spinner {
  width: 14px;
  height: 14px;
  border: 2px solid rgba(125, 211, 252, 0.2);
  border-top-color: #7dd3fc;
  border-radius: 50%;
  animation: spin 0.75s linear infinite;
  flex-shrink: 0;
}

.dash-loading-dots span {
  animation: dotPulse 1.2s ease-in-out infinite;
}

.dash-loading-dots span:nth-child(2) {
  animation-delay: 0.15s;
}

.dash-loading-dots span:nth-child(3) {
  animation-delay: 0.3s;
}

.sk {
  display: block;
  background: linear-gradient(
    90deg,
    #151c26 0%,
    #1e2836 35%,
    #2a3648 50%,
    #1e2836 65%,
    #151c26 100%
  );
  background-size: 220% 100%;
  animation: shimmer 1.5s ease-in-out infinite;
  border-radius: 6px;
}

.sk-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 10px;
}

.sk-badge {
  width: 72px;
  height: 22px;
  border-radius: 4px;
}

.sk-badge-sm {
  width: 56px;
}

.sk-line {
  height: 12px;
  margin-bottom: 8px;
}

.sk-line-xs {
  width: 28%;
  height: 10px;
}

.sk-line-sm {
  width: 55%;
}

.sk-line-md {
  width: 72%;
}

.sk-line-lg {
  width: 48%;
  height: 22px;
}

.sk-line-wide {
  width: 92%;
}

.sk-bar {
  height: 8px;
  width: 100%;
  margin: 4px 0 10px;
  border-radius: 4px;
}

.sk-advisor {
  background: linear-gradient(135deg, #1a2332 0%, #15202b 100%);
  border: 1px solid #2d3a4d;
  border-radius: 10px;
  padding: 16px;
  margin-bottom: 14px;
}

.sk-advisor-compact {
  padding: 12px;
}

.sk-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 12px;
  margin-bottom: 14px;
}

.sk-card {
  background: #121820;
  border: 1px solid #243041;
  border-radius: 12px;
  padding: 16px;
}

.sk-block {
  background: #121820;
  border: 1px solid #243041;
  border-radius: 12px;
  padding: 16px;
}

.sk-chart {
  height: 120px;
  width: 100%;
  margin-top: 8px;
  border-radius: 8px;
}

.sk-stats {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 10px;
  margin-bottom: 14px;
}

.sk-stat {
  background: #121820;
  border: 1px solid #243041;
  border-radius: 10px;
  padding: 14px;
}

.sk-positions {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.sk-position {
  background: #121820;
  border: 1px solid #243041;
  border-radius: 10px;
  padding: 14px 16px;
}

.variant-block .sk-block {
  margin-top: 0;
}

@keyframes shimmer {
  0% {
    background-position: 120% 0;
  }
  100% {
    background-position: -120% 0;
  }
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

@keyframes dotPulse {
  0%,
  60%,
  100% {
    opacity: 0.25;
  }
  30% {
    opacity: 1;
  }
}
</style>
