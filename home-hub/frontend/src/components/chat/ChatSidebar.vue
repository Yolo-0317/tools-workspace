<script setup lang="ts">
import type { ChatHealth, ChatSession } from '../../types/chat'

defineProps<{
  sessions: ChatSession[]
  activeId: string | null
  health: ChatHealth | null
  compact?: boolean
}>()

const emit = defineEmits<{
  select: [id: string]
  new: []
  delete: [id: string]
  close: []
}>()
</script>

<template>
  <aside class="sidebar" :class="{ compact }">
    <div class="brand">
      <strong>{{ compact ? '对话列表' : 'Home Hub' }}</strong>
      <div class="brand-actions">
        <button type="button" class="new-btn" @click="emit('new')">新对话</button>
        <button
          v-if="compact"
          type="button"
          class="close-btn"
          aria-label="关闭"
          @click="emit('close')"
        >
          ×
        </button>
      </div>
    </div>

    <ul class="session-list">
      <li
        v-for="s in sessions"
        :key="s.id"
        :class="{ active: s.id === activeId }"
      >
        <button type="button" class="session-btn" @click="emit('select', s.id)">
          <span class="title">{{ s.title }}</span>
          <span class="time">{{ s.updated_at.slice(0, 16).replace('T', ' ') }}</span>
        </button>
        <button
          type="button"
          class="del-btn"
          title="删除"
          @click.stop="emit('delete', s.id)"
        >
          ×
        </button>
      </li>
    </ul>

    <footer class="sidebar-foot">
      <p>模型 {{ health?.model ?? '—' }}</p>
      <p>{{ health?.ready ? 'Agent 已就绪' : '请先 agent login' }}</p>
    </footer>
  </aside>
</template>

<style scoped>
.sidebar {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  border-right: 1px solid #243041;
  background: #0b1016;
}

.brand {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 16px;
  border-bottom: 1px solid #243041;
}

.brand-actions {
  display: flex;
  align-items: center;
  gap: 6px;
}

.new-btn {
  border: 1px solid #314158;
  background: #121820;
  color: #dbe7ff;
  border-radius: 8px;
  padding: 6px 10px;
  cursor: pointer;
  font-size: 12px;
  white-space: nowrap;
}

.close-btn {
  border: none;
  background: transparent;
  color: #8b9cb3;
  font-size: 26px;
  line-height: 1;
  min-width: 36px;
  min-height: 36px;
  cursor: pointer;
  border-radius: 8px;
}

.close-btn:hover {
  background: #152033;
  color: #dbe7ff;
}

.session-list {
  list-style: none;
  margin: 0;
  padding: 8px;
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  overscroll-behavior: contain;
  -webkit-overflow-scrolling: touch;
}

.session-list li {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 4px;
  margin-bottom: 4px;
  border-radius: 10px;
}

.session-list li.active {
  background: #152033;
}

.session-btn {
  text-align: left;
  border: none;
  background: transparent;
  color: inherit;
  padding: 10px;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.title {
  font-size: 14px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.time {
  font-size: 11px;
  color: #7d8ea8;
}

.del-btn {
  border: none;
  background: transparent;
  color: #7d8ea8;
  font-size: 20px;
  line-height: 1;
  cursor: pointer;
  min-width: 40px;
  min-height: 40px;
  border-radius: 8px;
  align-self: center;
}

.del-btn:hover {
  color: #ff8f8f;
  background: rgba(255, 143, 143, 0.08);
}

.sidebar-foot {
  flex-shrink: 0;
  padding: 12px 16px;
  border-top: 1px solid #243041;
  font-size: 11px;
  color: #7d8ea8;
}

.sidebar-foot p {
  margin: 0 0 4px;
}

.sidebar.compact .brand {
  padding-top: max(16px, env(safe-area-inset-top));
}
</style>
