<script setup lang="ts">
import type { ChatHealth, ChatSession } from '../../types/chat'

defineProps<{
  sessions: ChatSession[]
  activeId: string | null
  health: ChatHealth | null
}>()

const emit = defineEmits<{
  select: [id: string]
  new: []
  delete: [id: string]
}>()
</script>

<template>
  <aside class="sidebar">
    <div class="brand">
      <strong>Home Hub</strong>
      <button type="button" class="new-btn" @click="emit('new')">新对话</button>
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
  border-right: 1px solid #243041;
  background: #0b1016;
  min-height: calc(100vh - 52px);
}

.brand {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px;
  border-bottom: 1px solid #243041;
}

.new-btn {
  border: 1px solid #314158;
  background: #121820;
  color: #dbe7ff;
  border-radius: 8px;
  padding: 6px 10px;
  cursor: pointer;
  font-size: 12px;
}

.session-list {
  list-style: none;
  margin: 0;
  padding: 8px;
  flex: 1;
  overflow-y: auto;
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
  font-size: 18px;
  cursor: pointer;
  padding: 0 8px;
}

.del-btn:hover {
  color: #ff8f8f;
}

.sidebar-foot {
  padding: 12px 16px;
  border-top: 1px solid #243041;
  font-size: 11px;
  color: #7d8ea8;
}

.sidebar-foot p {
  margin: 0 0 4px;
}
</style>
