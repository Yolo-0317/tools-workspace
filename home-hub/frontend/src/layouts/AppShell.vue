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
const moreOpen = ref(false)

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
  if (!target?.closest('.nav-group') && !target?.closest('.bottom-invest')) {
    investOpen.value = false
  }
  if (!target?.closest('.bottom-more') && !target?.closest('.more-sheet')) {
    moreOpen.value = false
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
      'shell-has-bottom': true,
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

    <nav class="bottom-nav" aria-label="底部导航">
      <template v-if="shareOnly">
        <RouterLink
          to="/selection"
          class="bottom-link"
          exact-active-class="active"
        >
          选股
        </RouterLink>
      </template>
      <template v-else>
        <button
          type="button"
          class="bottom-link bottom-invest"
          :class="{ active: investActive || investOpen }"
          :aria-expanded="investOpen"
          @click.stop="toggleInvest"
        >
          投资
        </button>
        <RouterLink
          to="/chat"
          class="bottom-link"
          exact-active-class="active"
          @click="closeSheets"
        >
          聊天
        </RouterLink>
        <button
          type="button"
          class="bottom-link bottom-more"
          :class="{ active: moreOpen }"
          :aria-expanded="moreOpen"
          @click.stop="toggleMore"
        >
          更多
        </button>
      </template>
    </nav>

    <div
      v-if="investOpen && !shareOnly"
      class="sheet-mask"
      @click="closeSheets"
    />
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

    <div
      v-if="moreOpen && !shareOnly"
      class="sheet-mask"
      @click="closeSheets"
    />
    <div v-if="moreOpen && !shareOnly" class="sheet more-sheet" role="menu">
      <p class="sheet-title">更多</p>
      <RouterLink
        v-for="link in systemLinks.filter((l) => l.to !== '/chat')"
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
  flex-direction: column;
  gap: 10px;
  padding: 12px 20px;
  border-bottom: 1px solid #243041;
  background: #0b1016;
}

.topbar-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  width: 100%;
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
  width: 100%;
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

.bottom-nav,
.sheet-mask,
.sheet {
  display: none;
}

.user-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
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

.nav-link,
.bottom-link,
.sheet-item {
  color: #8b9cb3;
  text-decoration: none;
  border-radius: 8px;
  font-size: 14px;
  white-space: nowrap;
}

.nav-link {
  padding: 6px 12px;
}

.nav-link:hover,
.sheet-item:hover {
  color: #dbe7ff;
  background: #152033;
}

.nav-link.active,
.sheet-item.active {
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
  -webkit-overflow-scrolling: touch;
  --bottom-nav-h: 52px;
}

@media (min-width: 769px) {
  .topbar {
    flex-direction: row;
    flex-wrap: wrap;
    align-items: center;
    gap: 16px 24px;
  }

  .topbar-head {
    width: auto;
  }

  .nav {
    flex: 1;
    width: auto;
  }

  .user-bar {
    margin-left: auto;
  }
}

@media (max-width: 768px) {
  .topbar {
    padding: 10px 12px;
    padding-top: max(10px, env(safe-area-inset-top));
    padding-left: max(12px, env(safe-area-inset-left));
    padding-right: max(12px, env(safe-area-inset-right));
    gap: 0;
  }

  .nav-top {
    display: none;
  }

  .brand {
    font-size: 15px;
  }

  .shell-share .brand {
    font-size: 16px;
  }

  .user {
    display: none;
  }

  .logout {
    padding: 8px 12px;
    min-height: 36px;
  }

  .shell-has-bottom .content {
    padding: 12px;
    padding-bottom: calc(var(--bottom-nav-h) + env(safe-area-inset-bottom));
  }

  .shell-chat.shell-has-bottom .content {
    padding-bottom: calc(var(--bottom-nav-h) + env(safe-area-inset-bottom));
  }

  .bottom-nav {
    display: flex;
    position: fixed;
    left: 0;
    right: 0;
    bottom: 0;
    z-index: 300;
    align-items: stretch;
    border-top: 1px solid #243041;
    background: #0b1016;
    padding-bottom: env(safe-area-inset-bottom);
    box-shadow: 0 -4px 24px rgba(0, 0, 0, 0.35);
  }

  .bottom-link {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 52px;
    padding: 6px 4px;
    border: none;
    background: transparent;
    font: inherit;
    font-size: 13px;
    cursor: pointer;
    border-radius: 0;
  }

  .bottom-link.active {
    color: #93c5fd;
    background: transparent;
    box-shadow: inset 0 -2px 0 #2563eb;
  }

  .bottom-more.active {
    color: #dbe7ff;
    box-shadow: inset 0 -2px 0 #64748b;
  }

  .sheet-mask {
    display: block;
    position: fixed;
    inset: 0;
    z-index: 310;
    background: rgba(0, 0, 0, 0.45);
  }

  .sheet {
    display: flex;
    flex-direction: column;
    gap: 6px;
    position: fixed;
    left: 12px;
    right: 12px;
    bottom: calc(var(--bottom-nav-h) + env(safe-area-inset-bottom));
    z-index: 320;
    padding: 12px;
    border-radius: 14px;
    border: 1px solid #243041;
    background: #121820;
    box-shadow: 0 -8px 32px rgba(0, 0, 0, 0.4);
  }

  .sheet-title {
    margin: 0 4px 4px;
    font-size: 12px;
    font-weight: 600;
    color: #6b7c93;
    letter-spacing: 0.06em;
    text-transform: uppercase;
  }

  .sheet-item {
    display: block;
    padding: 14px 16px;
    font-size: 16px;
    text-align: center;
  }
}
</style>
