<script setup lang="ts">
import { computed, inject, onMounted, onUnmounted, ref } from 'vue'
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router'
import { hubAuth, logout } from '../auth/hubAuth'
import { isStandaloneDisplay } from '../utils/standalone'

interface NavLink {
  to: string
  label: string
}

const router = useRouter()
const route = useRoute()
const openPwaInstall = inject<() => void>('openPwaInstall', () => {})

const investOpen = ref(false)
const moreOpen = ref(false)
const standalone = ref(isStandaloneDisplay())
const refreshing = ref(false)

const investLinks: NavLink[] = [
  { to: '/m/portfolio', label: '持仓' },
  { to: '/m/selection', label: '选股' },
  { to: '/m/monitor', label: '监控' },
  { to: '/m/news', label: '财经' },
  { to: '/m/emotion', label: '龙头' },
]

const moreLinks: NavLink[] = [
  { to: '/m/jobs', label: '任务' },
  { to: '/m/services', label: '服务' },
]

const investRouteNames = new Set(['m-portfolio', 'm-selection', 'm-monitor', 'm-news', 'm-emotion'])

const shareOnly = computed(() => hubAuth.value.shareOnly)
const username = computed(() => hubAuth.value.username)
const authenticated = computed(() => hubAuth.value.authenticated)
const brand = computed(() => {
  if (!authenticated.value) return '财经快讯'
  return shareOnly.value ? '选股分享' : 'Home Hub'
})

const homeActive = computed(
  () => route.path === '/m' || route.name === 'm-home',
)

const investActive = computed(() => {
  if (shareOnly.value) return route.path === '/m/selection'
  if (homeActive.value) return false
  return investRouteNames.has(String(route.name ?? ''))
})
const moreActive = computed(() => moreLinks.some((link) => route.path === link.to))

function closeSheets() {
  investOpen.value = false
  moreOpen.value = false
}

function toggleInvest() {
  moreOpen.value = false
  investOpen.value = !investOpen.value
}

function toggleMore() {
  investOpen.value = false
  moreOpen.value = !moreOpen.value
}

function onDocClick(event: MouseEvent) {
  const target = event.target as HTMLElement | null
  if (!target?.closest('.bottom-invest')) {
    investOpen.value = false
  }
  if (!target?.closest('.bottom-more') && !target?.closest('.more-sheet')) {
    moreOpen.value = false
  }
}

onMounted(() => {
  document.documentElement.classList.add('h5-shell')
  document.body.classList.add('h5-shell')
  document.addEventListener('click', onDocClick)
})
onUnmounted(() => {
  document.documentElement.classList.remove('h5-shell')
  document.body.classList.remove('h5-shell')
  document.removeEventListener('click', onDocClick)
})

async function onRefresh() {
  if (refreshing.value) return
  refreshing.value = true
  try {
    if ('serviceWorker' in navigator) {
      const reg = await navigator.serviceWorker.getRegistration()
      await reg?.update()
    }
  } catch {
    /* ignore */
  }
  window.location.reload()
}

async function onLogout() {
  await logout()
  await router.replace('/login')
}
</script>

<template>
  <div
    class="shell"
    :class="{
      'shell-share': shareOnly,
      'shell-standalone': standalone,
      'shell-guest': !authenticated,
    }"
  >
    <header class="topbar">
      <div class="brand">{{ brand }}</div>
      <div class="user-bar">
        <button
          v-if="!standalone"
          type="button"
          class="install-app"
          @click="openPwaInstall()"
        >
          安装
        </button>
        <button
          type="button"
          class="refresh-app"
          :disabled="refreshing"
          aria-label="刷新页面"
          @click="onRefresh"
        >
          {{ refreshing ? '…' : '刷新' }}
        </button>
        <span v-if="username" class="user">{{ username }}</span>
        <RouterLink v-if="!authenticated" to="/login" class="login-link">登录</RouterLink>
        <button v-else type="button" class="logout" @click="onLogout">退出</button>
      </div>
    </header>

    <main class="content hub-scrollbar">
      <RouterView />
    </main>

    <nav v-if="authenticated" class="bottom-nav" aria-label="H5 底部导航">
      <template v-if="shareOnly">
        <RouterLink to="/m/selection" class="bottom-link" exact-active-class="active">
          <svg class="tab-icon" viewBox="0 0 24 24" aria-hidden="true">
            <path
              fill="currentColor"
              d="M4 6h16v2H4V6zm0 5h16v2H4v-2zm0 5h10v2H4v-2z"
            />
          </svg>
          <span class="tab-text">选股</span>
        </RouterLink>
      </template>
      <template v-else>
        <RouterLink
          to="/m"
          class="bottom-link"
          active-class=""
          exact-active-class=""
          :class="{ active: homeActive }"
          @click="closeSheets"
        >
          <svg class="tab-icon" viewBox="0 0 24 24" aria-hidden="true">
            <path
              fill="currentColor"
              d="M12 3l9 8h-3v9h-5v-6H11v6H6v-9H3l9-8z"
            />
          </svg>
          <span class="tab-text">首页</span>
        </RouterLink>
        <button
          type="button"
          class="bottom-link bottom-invest"
          :class="{ active: investActive || investOpen }"
          :aria-expanded="investOpen"
          @click.stop="toggleInvest"
        >
          <svg class="tab-icon" viewBox="0 0 24 24" aria-hidden="true">
            <path
              fill="currentColor"
              d="M3 17h2v4H3v-4zm4-6h2v10H7V11zm4-4h2v14h-2V7zm4 3h2v11h-2V10zm4-6h2v17h-2V4z"
            />
          </svg>
          <span class="tab-text">投资</span>
        </button>
        <button
          type="button"
          class="bottom-link bottom-more"
          :class="{ active: moreActive || moreOpen }"
          :aria-expanded="moreOpen"
          @click.stop="toggleMore"
        >
          <svg class="tab-icon" viewBox="0 0 24 24" aria-hidden="true">
            <path
              fill="currentColor"
              d="M4 8h16v2H4V8zm0 5h16v2H4v-2zm0 5h16v2H4v-2z"
            />
          </svg>
          <span class="tab-text">更多</span>
        </button>
      </template>
    </nav>

    <div v-if="investOpen && !shareOnly" class="sheet-mask" @click="closeSheets" />
    <div v-if="investOpen && !shareOnly" class="sheet invest-sheet" role="menu">
      <p class="sheet-title">投资</p>
      <RouterLink
        v-for="link in investLinks"
        :key="link.to"
        :to="link.to"
        class="sheet-item"
        exact-active-class="active"
        role="menuitem"
        @click="closeSheets"
      >
        {{ link.label }}
      </RouterLink>
    </div>

    <div v-if="moreOpen && !shareOnly" class="sheet-mask" @click="closeSheets" />
    <div v-if="moreOpen && !shareOnly" class="sheet more-sheet" role="menu">
      <p class="sheet-title">更多</p>
      <RouterLink
        v-for="link in moreLinks"
        :key="link.to"
        :to="link.to"
        class="sheet-item"
        exact-active-class="active"
        role="menuitem"
        @click="closeSheets"
      >
        {{ link.label }}
      </RouterLink>
    </div>
  </div>
</template>

<style scoped>
.shell {
  --tab-bar-h: 50px;

  position: fixed;
  inset: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: #0b1016;
  color: #e7ecf3;
}

.topbar {
  flex-shrink: 0;
  z-index: 200;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  min-width: 0;
  max-width: 100%;
  overflow: hidden;
  padding: 10px 12px;
  padding-top: max(10px, env(safe-area-inset-top));
  padding-left: max(12px, env(safe-area-inset-left));
  padding-right: max(12px, env(safe-area-inset-right));
  border-bottom: 1px solid #243041;
  background: #0b1016;
}

.shell-standalone .topbar {
  padding-top: max(12px, env(safe-area-inset-top));
}

.brand {
  font-weight: 700;
  font-size: 15px;
  letter-spacing: 0.02em;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.shell-share .brand {
  font-size: 16px;
}

.user-bar {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
  max-width: 62%;
}

.user {
  display: none;
}

.install-app {
  border: 1px solid #2a4060;
  background: #152238;
  color: #93c5fd;
  border-radius: 8px;
  padding: 8px 8px;
  font-size: 11px;
  font-weight: 600;
  cursor: pointer;
  white-space: nowrap;
  flex-shrink: 0;
}

.refresh-app {
  border: 1px solid #314158;
  background: transparent;
  color: #dbe7ff;
  border-radius: 8px;
  padding: 8px 8px;
  min-height: 36px;
  font-size: 11px;
  font-weight: 600;
  cursor: pointer;
  white-space: nowrap;
  flex-shrink: 0;
}

.refresh-app:disabled {
  opacity: 0.6;
  cursor: wait;
}

.shell-guest .content {
  padding-bottom: max(12px, env(safe-area-inset-bottom));
}

.login-link {
  color: #dbe7ff;
  text-decoration: none;
  border: 1px solid #314158;
  border-radius: 8px;
  padding: 8px 10px;
  min-height: 36px;
  font-size: 12px;
  display: inline-flex;
  align-items: center;
  white-space: nowrap;
  flex-shrink: 0;
}

.logout {
  border: 1px solid #314158;
  background: transparent;
  color: #dbe7ff;
  border-radius: 8px;
  padding: 8px 10px;
  min-height: 36px;
  font-size: 12px;
  cursor: pointer;
  white-space: nowrap;
  flex-shrink: 0;
}

.content {
  flex: 1;
  min-height: 0;
  min-width: 0;
  width: 100%;
  max-width: 100%;
  overflow-x: hidden;
  overflow-y: auto;
  overscroll-behavior-x: none;
  overscroll-behavior-y: contain;
  touch-action: pan-y;
  padding: 12px;
  padding-bottom: calc(12px + var(--tab-bar-h));
  padding-left: max(12px, env(safe-area-inset-left));
  padding-right: max(12px, env(safe-area-inset-right));
  box-sizing: border-box;
  -webkit-overflow-scrolling: touch;
  background: #0f1419;
}

.content :deep(> *) {
  max-width: 100%;
  min-width: 0;
  box-sizing: border-box;
}

.bottom-nav {
  flex-shrink: 0;
  display: flex;
  align-items: stretch;
  width: 100%;
  height: var(--tab-bar-h);
  border-top: 1px solid #243041;
  background: #0b1016;
}

.bottom-link {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2px;
  height: 100%;
  margin: 0;
  padding: 0 4px;
  border: none;
  background: transparent;
  font: inherit;
  cursor: pointer;
  color: #6b7c93;
  text-decoration: none;
  -webkit-tap-highlight-color: transparent;
}

.bottom-link:active {
  opacity: 0.85;
}

.tab-icon {
  width: 22px;
  height: 22px;
  flex-shrink: 0;
}

.tab-text {
  font-size: 10px;
  font-weight: 600;
  line-height: 1.1;
}

.bottom-link.active {
  color: #93c5fd;
  box-shadow: inset 0 -2px 0 #2563eb;
}

.bottom-invest.active {
  color: #93c5fd;
  box-shadow: inset 0 -2px 0 #2563eb;
}

.bottom-more.active {
  color: #dbe7ff;
  box-shadow: inset 0 -2px 0 #64748b;
}

.sheet-mask {
  position: fixed;
  inset: 0;
  z-index: 310;
  background: rgba(0, 0, 0, 0.48);
}

.sheet {
  display: flex;
  flex-direction: column;
  gap: 6px;
  position: fixed;
  left: 12px;
  right: 12px;
  bottom: var(--tab-bar-h);
  z-index: 320;
  padding: 12px;
  border-radius: 18px;
  border: 1px solid #243041;
  background: #121820;
  box-shadow: 0 -8px 32px rgba(0, 0, 0, 0.4);
}

.sheet-title {
  margin: 0 4px 4px;
  font-size: 11px;
  font-weight: 600;
  color: #6b7c93;
  letter-spacing: 0.06em;
}

.sheet-item {
  display: block;
  padding: 14px 16px;
  font-size: 16px;
  text-align: center;
  color: #8b9cb3;
  text-decoration: none;
  border-radius: 12px;
  min-height: 48px;
}

.sheet-item:hover {
  color: #dbe7ff;
  background: #152033;
}

.sheet-item.active {
  color: #fff;
  background: #2563eb;
}
</style>
