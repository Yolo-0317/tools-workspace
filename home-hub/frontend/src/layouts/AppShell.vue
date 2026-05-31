<script setup lang="ts">
import { RouterLink, RouterView } from 'vue-router'

const links = [
  { to: '/', label: '总览' },
  { to: '/portfolio', label: '持仓' },
  { to: '/selection', label: '选股' },
  { to: '/monitor', label: '监控' },
  { to: '/jobs', label: '任务' },
  { to: '/services', label: '服务' },
  { to: '/chat', label: '聊天' },
]
</script>

<template>
  <div class="shell" :class="{ 'shell-chat': $route.name === 'chat' }">
    <header class="topbar">
      <div class="brand">Home Hub</div>
      <nav class="nav">
        <RouterLink
          v-for="link in links"
          :key="link.to"
          :to="link.to"
          class="nav-link"
          active-class="active"
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
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  background: #0f1419;
  color: #e7ecf3;
}

.shell-chat .content {
  padding: 0;
  max-width: none;
}

.topbar {
  display: flex;
  align-items: center;
  gap: 24px;
  padding: 12px 20px;
  border-bottom: 1px solid #243041;
  background: #0b1016;
  flex-wrap: wrap;
}

.brand {
  font-weight: 700;
  letter-spacing: 0.02em;
}

.nav {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.nav-link {
  color: #8b9cb3;
  text-decoration: none;
  padding: 6px 12px;
  border-radius: 8px;
  font-size: 14px;
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
  padding: 20px;
  max-width: 1200px;
  width: 100%;
  margin: 0 auto;
  box-sizing: border-box;
}
</style>
