<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
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

const sessions = ref<ChatSession[]>([])
const activeId = ref<string | null>(null)
const messages = ref<ChatMessage[]>([])
const draft = ref('')
const loading = ref(false)
const streaming = ref(false)
const streamText = ref('')
const statusText = ref('')
const errorText = ref('')
const health = ref<ChatHealth | null>(null)
const abortRef = ref<AbortController | null>(null)

function formatStreamError(message: string, code?: string): string {
  if (code === 'agent_busy') return message
  return `错误：${message}`
}

const activeSession = computed(() =>
  sessions.value.find((s) => s.id === activeId.value) ?? null,
)

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
}

async function onSelect(sessionId: string) {
  if (streaming.value) return
  activeId.value = sessionId
}

async function onDelete(sessionId: string) {
  if (streaming.value) return
  await deleteSession(sessionId)
  await refreshSessions()
  if (activeId.value === sessionId) {
    activeId.value = sessions.value[0]?.id ?? null
    messages.value = activeId.value ? await listMessages(activeId.value) : []
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
        },
        onThinkingDelta: () => {
          statusText.value = 'Agent 思考中…'
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
    if (sessionId) {
      await loadMessages(sessionId)
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
  } finally {
    loading.value = false
  }
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
  <div class="layout">
    <ChatSidebar
      :sessions="sessions"
      :active-id="activeId"
      :health="health"
      @select="onSelect"
      @new="onNewSession"
      @delete="onDelete"
    />

    <main class="panel">
      <header class="panel-header">
        <div>
          <h1>{{ activeSession?.title ?? '投资助手' }}</h1>
          <p class="meta">
            {{ health?.model ?? '—' }}
            · {{ health?.agent_cwd ?? '工作区未配置' }}
          </p>
        </div>
        <span v-if="health?.agent_lock?.busy" class="badge busy">Agent 占用中</span>
        <span v-else-if="health?.ready" class="badge ok">已连接</span>
        <span v-else class="badge warn">未就绪</span>
      </header>

      <section class="messages">
        <p v-if="loading" class="hint">加载历史…</p>
        <MessageBubble
          v-for="msg in messages"
          :key="msg.id"
          :role="msg.role"
          :content="msg.content"
        />
        <MessageBubble
          v-if="streamText"
          role="assistant"
          :content="streamText"
          streaming
        />
        <p v-if="statusText" class="hint">{{ statusText }}</p>
        <p v-if="errorText" class="error">{{ errorText }}</p>
      </section>

      <footer class="composer">
        <textarea
          v-model="draft"
          rows="3"
          placeholder="输入消息，Enter 发送，Shift+Enter 换行"
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
  min-height: calc(100vh - 52px);
  background: #0f1419;
  color: #e7ecf3;
}

.panel {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 16px 20px;
  border-bottom: 1px solid #243041;
}

.panel-header h1 {
  margin: 0;
  font-size: 18px;
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

.badge {
  font-size: 12px;
  padding: 4px 10px;
  border-radius: 999px;
  border: 1px solid transparent;
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
  overflow-y: auto;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.hint {
  color: #8b9cb3;
  font-size: 13px;
}

.error {
  color: #ff8f8f;
  font-size: 13px;
}

.composer {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 12px;
  padding: 16px 20px 20px;
  border-top: 1px solid #243041;
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
  }
}
</style>
