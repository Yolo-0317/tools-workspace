<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import {
  createSession,
  deleteSession,
  fetchHealth,
  listMessages,
  listSessions,
  streamMessage,
} from '../api/chat'
import type { ChatHealth, ChatMessage, ChatSession } from '../types/chat'
import ChatSidebar from '../components/chat/ChatSidebar.vue'
import MessageBubble from '../components/chat/MessageBubble.vue'
import { MOBILE_QUERY, useMediaQuery } from '../composables/useMediaQuery'

const sessions = ref<ChatSession[]>([])
const activeId = ref<string | null>(null)
const messages = ref<ChatMessage[]>([])
const draft = ref('')
const loading = ref(false)
const streaming = ref(false)
const streamText = ref('')
const streamThinking = ref('')
const statusText = ref('')
const errorText = ref('')
const health = ref<ChatHealth | null>(null)
const abortRef = ref<AbortController | null>(null)
const messagesEl = ref<HTMLElement | null>(null)
const sidebarOpen = ref(false)

const isMobile = useMediaQuery(MOBILE_QUERY)

function formatStreamError(message: string, code?: string): string {
  if (code === 'agent_busy') return message
  return `错误：${message}`
}

const activeSession = computed(() =>
  sessions.value.find((s) => s.id === activeId.value) ?? null,
)

const statusLabel = computed(() => {
  if (health.value?.agent_lock?.busy) return '占用中'
  if (health.value?.ready) return '已连接'
  return '未就绪'
})

const statusClass = computed(() => {
  if (health.value?.agent_lock?.busy) return 'busy'
  if (health.value?.ready) return 'ok'
  return 'warn'
})

function closeSidebar() {
  sidebarOpen.value = false
}

function openSidebar() {
  sidebarOpen.value = true
}

async function scrollMessagesToBottom(behavior: ScrollBehavior = 'smooth') {
  await nextTick()
  const el = messagesEl.value
  if (!el) return
  el.scrollTo({ top: el.scrollHeight, behavior })
}

async function refreshSessions(selectLatest = false) {
  sessions.value = await listSessions()
  if (selectLatest && sessions.value.length > 0) {
    activeId.value = sessions.value[0].id
  }
}

async function loadMessages(sessionId: string) {
  messages.value = await listMessages(sessionId)
}

async function onNewSession() {
  const session = await createSession()
  await refreshSessions()
  activeId.value = session.id
  messages.value = []
  closeSidebar()
}

async function onSelect(sessionId: string) {
  if (streaming.value) return
  activeId.value = sessionId
  closeSidebar()
}

async function onDelete(sessionId: string) {
  if (!window.confirm('确定删除此对话？删除后无法恢复。')) return

  if (streaming.value && activeId.value === sessionId) {
    abortRef.value?.abort()
    streaming.value = false
    streamText.value = ''
    statusText.value = ''
  }

  errorText.value = ''
  try {
    await deleteSession(sessionId)
    const wasActive = activeId.value === sessionId
    await refreshSessions()
    if (wasActive) {
      if (sessions.value.length > 0) {
        activeId.value = sessions.value[0].id
      } else {
        await onNewSession()
      }
    }
  } catch (e) {
    errorText.value = formatStreamError(e instanceof Error ? e.message : String(e))
    await refreshSessions()
  }
}

function pushErrorBubble(message: string) {
  if (!activeId.value || !message.trim()) return
  messages.value.push({
    id: `err-${Date.now()}`,
    session_id: activeId.value,
    role: 'system',
    content: message,
    created_at: new Date().toISOString(),
  })
}

async function send() {
  const text = draft.value.trim()
  if (!text || !activeId.value || streaming.value) return

  errorText.value = ''
  statusText.value = 'Agent 思考中…'
  draft.value = ''
  streaming.value = true
  streamText.value = ''
  streamThinking.value = ''

  const userMsg: ChatMessage = {
    id: `local-${Date.now()}`,
    session_id: activeId.value,
    role: 'user',
    content: text,
    created_at: new Date().toISOString(),
  }
  messages.value.push(userMsg)

  const controller = new AbortController()
  abortRef.value = controller
  const sessionId = activeId.value
  let pendingError: { message: string; code?: string } | null = null

  try {
    await streamMessage(
      sessionId,
      text,
      {
        onStatus: (data) => {
          const phase = String(data.phase ?? '')
          if (phase === 'retry') {
            statusText.value = String(
              data.message ?? '会话异常，正在新建 Agent 会话重试…',
            )
            return
          }
          statusText.value = 'Agent 思考中…'
        },
        onTextDelta: (chunk) => {
          streamText.value += chunk
          statusText.value = ''
          scrollMessagesToBottom('auto')
        },
        onThinkingDelta: (chunk) => {
          streamThinking.value += chunk
          statusText.value = 'Agent 思考中…'
          scrollMessagesToBottom('auto')
        },
        onToolStart: (data) => {
          statusText.value = `调用工具：${String(data.tool ?? 'tool')}`
        },
        onDone: async (data) => {
          const streamed = streamText.value.trim()
          const finalText = streamed || String(data.text ?? '').trim()

          if (!streamed && finalText) {
            streamText.value = finalText
          }

          const doneError = String(data.error ?? '').trim()
          const doneCode = String(data.code ?? pendingError?.code ?? '')
          const doneStatus = String(data.status ?? '')

          if (doneError) {
            errorText.value = formatStreamError(doneError, doneCode || undefined)
            pushErrorBubble(errorText.value)
          } else if (pendingError) {
            errorText.value = formatStreamError(
              pendingError.message,
              pendingError.code,
            )
            pushErrorBubble(errorText.value)
          } else if (doneStatus === 'empty' && !finalText) {
            errorText.value =
              'Agent 未返回内容（可能超时、MCP 连接失败，或 agent 被其他会话占用）'
            pushErrorBubble(errorText.value)
          }

          streamText.value = ''
          streamThinking.value = ''
          statusText.value = ''
          pendingError = null
          await loadMessages(sessionId)
          await refreshSessions()
        },
        onError: (msg, code) => {
          pendingError = { message: msg, code }
          errorText.value = formatStreamError(msg, code)
          statusText.value = ''
        },
      },
      controller.signal,
    )
  } finally {
    streaming.value = false
    abortRef.value = null
    if (sessionId && sessions.value.some((s) => s.id === sessionId)) {
      try {
        await loadMessages(sessionId)
      } catch {
        /* 会话可能已被删除 */
      }
    }
  }
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    send()
  }
}

watch(activeId, async (id) => {
  if (!id) {
    messages.value = []
    return
  }
  loading.value = true
  try {
    await loadMessages(id)
    await scrollMessagesToBottom('auto')
  } finally {
    loading.value = false
  }
})

watch(
  () => messages.value.length,
  () => {
    scrollMessagesToBottom('auto')
  },
)

watch(isMobile, (mobile) => {
  if (!mobile) sidebarOpen.value = false
})

onMounted(async () => {
  try {
    health.value = await fetchHealth()
  } catch {
    health.value = null
  }
  await refreshSessions(true)
  if (!activeId.value) {
    await onNewSession()
  }
})
</script>

<template>
  <div
    class="layout"
    :class="{ mobile: isMobile, 'sidebar-open': sidebarOpen && isMobile }"
  >
    <div
      v-if="isMobile && sidebarOpen"
      class="sidebar-mask"
      aria-hidden="true"
      @click="closeSidebar"
    />

    <aside class="sidebar-drawer" :class="{ open: !isMobile || sidebarOpen }">
      <ChatSidebar
        :sessions="sessions"
        :active-id="activeId"
        :health="health"
        :compact="isMobile"
        @select="onSelect"
        @new="onNewSession"
        @delete="onDelete"
        @close="closeSidebar"
      />
    </aside>

    <main class="panel">
      <header class="panel-header">
        <div class="header-main">
          <button
            v-if="isMobile"
            type="button"
            class="icon-btn"
            aria-label="打开对话列表"
            @click="openSidebar"
          >
            ☰
          </button>
          <div class="title-block">
            <h1>{{ activeSession?.title ?? '投资助手' }}</h1>
            <p v-if="!isMobile" class="meta">
              {{ health?.model ?? '—' }}
              · {{ health?.agent_cwd ?? '工作区未配置' }}
            </p>
          </div>
        </div>
        <div class="header-actions">
          <button
            v-if="isMobile"
            type="button"
            class="icon-btn new-chat-btn"
            aria-label="新对话"
            @click="onNewSession"
          >
            ＋
          </button>
          <span class="badge" :class="statusClass">{{ statusLabel }}</span>
        </div>
      </header>

      <section ref="messagesEl" class="messages">
        <p v-if="loading" class="hint">加载历史…</p>
        <p v-else-if="!messages.length && !streamText" class="empty-hint">
          问我持仓、个股或今日计划
        </p>
        <MessageBubble
          v-for="msg in messages"
          :key="msg.id"
          :role="msg.role"
          :content="msg.content"
        />
        <MessageBubble
          v-if="streamThinking"
          role="thinking"
          :content="streamThinking"
          streaming
        />
        <MessageBubble
          v-if="streamText"
          role="assistant"
          :content="streamText"
          streaming
        />
        <p v-if="statusText" class="hint status-hint">{{ statusText }}</p>
        <p v-if="errorText" class="error">{{ errorText }}</p>
      </section>

      <footer class="composer">
        <textarea
          v-model="draft"
          :rows="isMobile ? 2 : 3"
          :placeholder="isMobile ? '输入问题…' : '输入消息，Enter 发送，Shift+Enter 换行'"
          :disabled="streaming || !activeId"
          @keydown="onKeydown"
        />
        <button type="button" :disabled="streaming || !draft.trim() || !activeId" @click="send">
          {{ streaming ? '回复中…' : '发送' }}
        </button>
      </footer>
    </main>
  </div>
</template>

<style scoped>
.layout {
  display: grid;
  grid-template-columns: 280px 1fr;
  height: 100%;
  min-height: 0;
  background: #0f1419;
  color: #e7ecf3;
}

.sidebar-drawer {
  min-height: 0;
  height: 100%;
  overflow: hidden;
}

.sidebar-mask {
  display: none;
}

.panel {
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  height: 100%;
}

.panel-header {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 16px 20px;
  border-bottom: 1px solid #243041;
  background: #0f1419;
}

.header-main {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
  flex: 1;
}

.title-block {
  min-width: 0;
}

.panel-header h1 {
  margin: 0;
  font-size: 18px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.meta {
  margin: 4px 0 0;
  font-size: 12px;
  color: #8b9cb3;
  max-width: 60vw;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.icon-btn {
  border: 1px solid #314158;
  background: #121820;
  color: #dbe7ff;
  border-radius: 10px;
  min-width: 40px;
  min-height: 40px;
  padding: 0;
  font-size: 18px;
  line-height: 1;
  cursor: pointer;
}

.new-chat-btn {
  font-size: 22px;
  font-weight: 300;
}

.badge {
  font-size: 12px;
  padding: 4px 10px;
  border-radius: 999px;
  border: 1px solid transparent;
  white-space: nowrap;
}

.badge.ok {
  color: #7dffb2;
  border-color: #1f6b47;
  background: #10261c;
}

.badge.warn {
  color: #ffd27d;
  border-color: #6b4f1f;
  background: #261c10;
}

.badge.busy {
  color: #ffb4b4;
  border-color: #6b2a2a;
  background: #261010;
}

.messages {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  overscroll-behavior: contain;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  -webkit-overflow-scrolling: touch;
}

.empty-hint {
  margin: auto 0;
  text-align: center;
  color: #6b7c93;
  font-size: 14px;
  padding: 24px 12px;
}

.hint {
  color: #8b9cb3;
  font-size: 13px;
}

.status-hint {
  align-self: center;
  padding: 6px 12px;
  border-radius: 999px;
  background: rgba(21, 32, 51, 0.9);
}

.error {
  color: #ff8f8f;
  font-size: 13px;
}

.composer {
  flex-shrink: 0;
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 12px;
  padding: 16px 20px 20px;
  border-top: 1px solid #243041;
  background: #0f1419;
}

textarea {
  resize: vertical;
  min-height: 72px;
  border-radius: 12px;
  border: 1px solid #314158;
  background: #121820;
  color: #e7ecf3;
  padding: 12px 14px;
  font: inherit;
}

textarea:focus {
  outline: 2px solid #3b82f6;
  border-color: transparent;
}

button {
  align-self: end;
  border: none;
  border-radius: 10px;
  padding: 10px 18px;
  background: #2563eb;
  color: white;
  font-weight: 600;
  cursor: pointer;
}

button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

@media (max-width: 768px) {
  .layout {
    grid-template-columns: 1fr;
    position: relative;
  }

  .sidebar-drawer {
    position: fixed;
    z-index: 400;
    top: 0;
    left: 0;
    bottom: calc(52px + env(safe-area-inset-bottom));
    width: min(88vw, 320px);
    transform: translateX(-105%);
    transition: transform 0.22s ease;
    box-shadow: 8px 0 32px rgba(0, 0, 0, 0.35);
  }

  .sidebar-drawer.open {
    transform: translateX(0);
  }

  .sidebar-mask {
    display: block;
    position: fixed;
    z-index: 390;
    inset: 0;
    bottom: calc(52px + env(safe-area-inset-bottom));
    background: rgba(0, 0, 0, 0.48);
  }

  .panel-header {
    padding: 10px 12px;
  }

  .panel-header h1 {
    font-size: 16px;
  }

  .badge {
    font-size: 11px;
    padding: 4px 8px;
  }

  .messages {
    padding: 12px;
    gap: 10px;
  }

  .composer {
    grid-template-columns: 1fr;
    gap: 10px;
    padding: 10px 12px 12px;
    background: #0b1016;
  }

  textarea {
    min-height: 44px;
    max-height: 120px;
    font-size: 16px;
    padding: 10px 12px;
  }

  .composer button {
    width: 100%;
    min-height: 44px;
    align-self: stretch;
  }
}
</style>
