import type {
  ChatHealth,
  ChatMessage,
  ChatSession,
  StreamHandlers,
} from '../types/chat'
import { apiFetch, apiHeaders } from './http'

export async function fetchHealth(): Promise<ChatHealth> {
  return apiFetch('/api/chat/health', { headers: apiHeaders({ Accept: 'application/json' }) }).then(
    async (res) => {
      if (!res.ok) throw new Error(await res.text())
      return res.json()
    },
  )
}

export async function listSessions(): Promise<ChatSession[]> {
  const data = await apiFetch('/api/chat/sessions').then(async (res) => {
    if (!res.ok) throw new Error(await res.text())
    return res.json()
  })
  return data.sessions as ChatSession[]
}

export async function createSession(title = '新对话'): Promise<ChatSession> {
  const data = await apiFetch('/api/chat/sessions', {
    method: 'POST',
    body: JSON.stringify({ title }),
  }).then(async (res) => {
    if (!res.ok) throw new Error(await res.text())
    return res.json()
  })
  return data.session as ChatSession
}

export async function deleteSession(sessionId: string): Promise<void> {
  const res = await apiFetch(`/api/chat/sessions/${sessionId}`, { method: 'DELETE' })
  if (!res.ok) throw new Error(await res.text())
}

export async function listMessages(sessionId: string): Promise<ChatMessage[]> {
  const data = await apiFetch(`/api/chat/sessions/${sessionId}/messages`).then(async (res) => {
    if (!res.ok) throw new Error(await res.text())
    return res.json()
  })
  return data.messages as ChatMessage[]
}

/** 解析 SSE 字节流并分发事件 */
export async function streamMessage(
  sessionId: string,
  content: string,
  handlers: StreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const res = await apiFetch(`/api/chat/sessions/${sessionId}/messages`, {
    method: 'POST',
    headers: apiHeaders({ Accept: 'text/event-stream' }),
    body: JSON.stringify({ content }),
    signal,
  })

  if (!res.ok) {
    const text = await res.text()
    handlers.onError?.(text || `HTTP ${res.status}`, 'http')
    return
  }

  const reader = res.body?.getReader()
  if (!reader) {
    handlers.onError?.('无法读取响应流')
    return
  }

  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    buffer = consumeSseBuffer(buffer, handlers)
  }
  consumeSseBuffer(buffer + '\n\n', handlers)
}

function consumeSseBuffer(buffer: string, handlers: StreamHandlers): string {
  const parts = buffer.split('\n\n')
  const rest = parts.pop() ?? ''

  for (const block of parts) {
    if (!block.trim()) continue
    let event = 'message'
    let data = ''
    for (const line of block.split('\n')) {
      if (line.startsWith('event:')) event = line.slice(6).trim()
      if (line.startsWith('data:')) data += line.slice(5).trim()
    }
    if (!data) continue
    dispatchEvent(event, data, handlers)
  }
  return rest
}

function dispatchEvent(event: string, raw: string, handlers: StreamHandlers) {
  let payload: Record<string, unknown> = {}
  try {
    payload = JSON.parse(raw)
  } catch {
    payload = { message: raw }
  }

  switch (event) {
    case 'status':
      handlers.onStatus?.(payload)
      break
    case 'text_delta':
      handlers.onTextDelta?.(String(payload.text ?? ''))
      break
    case 'thinking_delta':
      handlers.onThinkingDelta?.(String(payload.text ?? ''))
      break
    case 'tool_start':
      handlers.onToolStart?.(payload)
      break
    case 'tool_end':
      handlers.onToolEnd?.(payload)
      break
    case 'done':
      handlers.onDone?.(payload)
      break
    case 'error':
      handlers.onError?.(String(payload.message ?? '未知错误'), String(payload.code ?? ''))
      break
  }
}
