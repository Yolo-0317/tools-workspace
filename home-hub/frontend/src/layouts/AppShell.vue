<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router'
import { hubAuth, logout } from '../auth/hubAuth'

interface NavLink {
  to: string
  label: string
}

const router = useRouter()
const route = useRoute()

const investOpen = ref(false)

const investLinks: NavLink[] = [
  { to: '/', label: '总览' },
  { to: '/portfolio', label: '持仓' },
  { to: '/selection', label: '选股' },
  { to: '/monitor', label: '监控' },
]

const systemLinks: NavLink[] = [
  { to: '/jobs', label: '任务' },
  { to: '/services', label: '服务' },
  { to: '/chat', label: '聊天' },
]

const investRouteNames = new Set(['home', 'portfolio', 'selection', 'monitor'])

const shareOnly = computed(() => hubAuth.value.shareOnly)
const username = computed(() => hubAuth.value.username)

const investActive = computed(() => {
  if (shareOnly.value) return route.path === '/selection'
  return investRouteNames.has(String(route.name ?? ''))
})

const brand = computed(() => (shareOnly.value ? '选股分享' : 'Home Hub'))

function closeSheets() {
  investOpen.value = false
}

function toggleInvest() {
  investOpen.value = !investOpen.value
}

function onDocClick(event: MouseEvent) {
  const target = event.target as HTMLElement | null
  if (!target?.closest('.nav-group')) {
    investOpen.value = false
  }
}

onMounted(() => document.addEventListener('click', onDocClick))
onUnmounted(() => document.removeEventListener('click', onDocClick))

async function onLogout() {
  await logout()
  await router.replace('/login')
}
</script>

<template>
  <div
    class="shell"
    :class="{
      'shell-chat': route.name === 'chat',
      'shell-share': shareOnly,
    }"
  >
    <header class="topbar">
      <div class="topbar-head">
        <div class="brand">{{ brand }}</div>
        <div class="user-bar">
          <span v-if="username" class="user">{{ username }}</span>
          <button type="button" class="logout" @click="onLogout">退出</button>
        </div>
      </div>

      <nav v-if="!shareOnly" class="nav nav-top" aria-label="主导航">
        <div class="nav-group" :class="{ open: investOpen, active: investActive }">
          <button
            type="button"
            class="nav-link nav-group-trigger"
            :aria-expanded="investOpen"
            @click.stop="toggleInvest"
          >
            投资
            <span class="chev" aria-hidden="true">▾</span>
          </button>
          <div class="nav-dropdown" role="menu">
            <RouterLink
              v-for="link in investLinks"
              :key="link.to"
              :to="link.to"
              class="nav-link nav-sub"
              exact-active-class="active"
              role="menuitem"
              @click="closeSheets"
            >
              {{ link.label }}
            </RouterLink>
          </div>
        </div>
        <RouterLink
          v-for="link in systemLinks"
          :key="link.to"
          :to="link.to"
          class="nav-link"
          exact-active-class="active"
        >
          {{ link.label }}
        </RouterLink>
      </nav>
    </header>

    <main class="content">
      <RouterView />
    </main>
  </div>
</template>

<style scoped>
.shell {
  height: 100vh;
  height: 100dvh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: #0f1419;
  color: #e7ecf3;
}

.shell-chat .content {
  padding: 0;
  max-width: none;
  overflow: hidden;
}

.topbar {
  flex-shrink: 0;
  z-index: 200;
  display: flex;
  flex-direction: row;
  flex-wrap: wrap;
  align-items: center;
  gap: 16px 24px;
  padding: 12px 20px;
  border-bottom: 1px solid #243041;
  background: #0b1016;
}

.topbar-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  min-width: 0;
}

.brand {
  font-weight: 700;
  letter-spacing: 0.02em;
  flex-shrink: 0;
}

.nav {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
  flex: 1;
  min-width: 0;
}

.nav-group {
  position: relative;
}

.nav-group-trigger {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  cursor: pointer;
  border: none;
  font: inherit;
}

.nav-group-trigger .chev {
  font-size: 10px;
  opacity: 0.7;
  transition: transform 0.15s ease;
}

.nav-group.open .nav-group-trigger .chev,
.nav-group:hover .nav-group-trigger .chev {
  transform: rotate(180deg);
}

.nav-dropdown {
  display: none;
  position: absolute;
  top: calc(100% + 6px);
  left: 0;
  min-width: 132px;
  padding: 6px;
  border-radius: 12px;
  border: 1px solid #243041;
  background: #121820;
  box-shadow: 0 12px 32px rgba(0, 0, 0, 0.35);
  z-index: 220;
}

.nav-group.open .nav-dropdown,
.nav-group:hover .nav-dropdown {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.nav-sub {
  display: block;
  width: 100%;
  text-align: left;
}

.nav-group.active > .nav-group-trigger {
  color: #fff;
  background: #2563eb;
}

.user-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
  margin-left: auto;
}

.user {
  font-size: 13px;
  color: #8b9cb3;
}

.logout {
  border: 1px solid #314158;
  background: transparent;
  color: #dbe7ff;
  border-radius: 8px;
  padding: 6px 12px;
  font-size: 13px;
  cursor: pointer;
}

.logout:hover {
  background: #152033;
}

.nav-link {
  color: #8b9cb3;
  text-decoration: none;
  border-radius: 8px;
  font-size: 14px;
  white-space: nowrap;
  padding: 6px 12px;
}

.nav-link:hover {
  color: #dbe7ff;
  background: #152033;
}

.nav-link.active {
  color: #fff;
  background: #2563eb;
}

.content {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  overscroll-behavior: contain;
  padding: 20px;
  padding-bottom: max(20px, env(safe-area-inset-bottom));
  max-width: 1200px;
  width: 100%;
  margin: 0 auto;
  box-sizing: border-box;
}
</style>
