import type {
  ChatHealth,
  ChatMessage,
  ChatSession,
  StreamHandlers,
} from '../types/chat'

const API_BASE = import.meta.env.VITE_API_BASE ?? ''
const HUB_TOKEN = import.meta.env.VITE_HUB_TOKEN ?? ''

function headers(): HeadersInit {
  const h: Record<string, string> = {
    'Content-Type': 'application/json',
    Accept: 'text/event-stream',
  }
  if (HUB_TOKEN) h['X-Hub-Token'] = HUB_TOKEN
  return h
}

export async function fetchHealth(): Promise<ChatHealth> {
  const res = await fetch(`${API_BASE}/api/chat/health`, { headers: headers() })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function listSessions(): Promise<ChatSession[]> {
  const res = await fetch(`${API_BASE}/api/chat/sessions`, { headers: headers() })
  if (!res.ok) throw new Error(await res.text())
  const data = await res.json()
  return data.sessions as ChatSession[]
}

export async function createSession(title = '新对话'): Promise<ChatSession> {
  const res = await fetch(`${API_BASE}/api/chat/sessions`, {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify({ title }),
  })
  if (!res.ok) throw new Error(await res.text())
  const data = await res.json()
  return data.session as ChatSession
}

export async function deleteSession(sessionId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/chat/sessions/${sessionId}`, {
    method: 'DELETE',
    headers: headers(),
  })
  if (!res.ok) throw new Error(await res.text())
}

export async function listMessages(sessionId: string): Promise<ChatMessage[]> {
  const res = await fetch(`${API_BASE}/api/chat/sessions/${sessionId}/messages`, {
    headers: headers(),
  })
  if (!res.ok) throw new Error(await res.text())
  const data = await res.json()
  return data.messages as ChatMessage[]
}

/** 解析 SSE 字节流并分发事件 */
export async function streamMessage(
  sessionId: string,
  content: string,
  handlers: StreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch(`${API_BASE}/api/chat/sessions/${sessionId}/messages`, {
    method: 'POST',
    headers: headers(),
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
