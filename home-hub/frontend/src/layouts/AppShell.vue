<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink, RouterView, useRouter } from 'vue-router'
import { hubAuth, logout } from '../auth/hubAuth'
import { NEWS_ENABLED } from '../config/features'

interface NavLink {
  to: string
  label: string
}

const router = useRouter()

const navLinks = computed<NavLink[]>(() => {
  const links: NavLink[] = [
    { to: '/advisor', label: '投顾' },
    { to: '/portfolio', label: '持仓' },
    { to: '/selection', label: '情报' },
    { to: '/monitor', label: '监控' },
  ]
  if (NEWS_ENABLED) links.push({ to: '/news', label: '财经' })
  links.push(
    { to: '/emotion', label: '龙头' },
    { to: '/jobs', label: '任务' },
    { to: '/services', label: '服务' },
  )
  return links
})

const shareOnly = computed(() => hubAuth.value.shareOnly)
const username = computed(() => hubAuth.value.username)
const authenticated = computed(() => hubAuth.value.authenticated)
const brand = computed(() => {
  if (!authenticated.value) return NEWS_ENABLED ? '财经快讯' : 'Home Hub'
  return shareOnly.value ? '选股分享' : 'Home Hub'
})

async function onLogout() {
  await logout()
  await router.replace('/login')
}
</script>

<template>
  <div class="shell" :class="{ 'shell-share': shareOnly }">
    <header class="topbar">
      <div class="topbar-head">
        <div class="brand">{{ brand }}</div>
        <div class="user-bar">
          <span v-if="username" class="user">{{ username }}</span>
          <RouterLink v-if="!authenticated" to="/login" class="login-link">登录</RouterLink>
          <button v-else type="button" class="logout" @click="onLogout">退出</button>
        </div>
      </div>

      <nav v-if="authenticated && !shareOnly" class="nav nav-top" aria-label="主导航">
        <RouterLink
          v-for="link in navLinks"
          :key="link.to"
          :to="link.to"
          class="nav-link"
          exact-active-class="active"
        >
          {{ link.label }}
        </RouterLink>
      </nav>
    </header>

    <main class="content hub-scrollbar">
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
  min-width: 0;
}

.brand {
  font-weight: 700;
  letter-spacing: 0.02em;
  flex-shrink: 0;
}

.nav {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  align-items: center;
  width: 100%;
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

.login-link {
  color: #dbe7ff;
  text-decoration: none;
  border: 1px solid #314158;
  border-radius: 8px;
  padding: 6px 12px;
  font-size: 13px;
}

.login-link:hover {
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
  min-width: 0;
  overflow-x: clip;
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
