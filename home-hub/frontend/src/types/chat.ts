export interface ChatSession {
  id: string
  title: string
  cursor_agent_id: string | null
  created_at: string
  updated_at: string
}

export interface ChatMessage {
  id: string
  session_id: string
  role: 'user' | 'assistant' | 'system' | 'thinking'
  content: string
  created_at: string
}

export interface ChatHealth {
  ready: boolean
  model: string
  agent_cwd: string
  forward_thoughts: boolean
  agent_lock: {
    busy: boolean
    holder: string | null
    since: string | null
  }
}

export type StreamEventType =
  | 'status'
  | 'text_delta'
  | 'thinking_delta'
  | 'tool_start'
  | 'tool_end'
  | 'done'
  | 'error'

export interface StreamHandlers {
  onStatus?: (data: Record<string, unknown>) => void
  onTextDelta?: (text: string) => void
  onThinkingDelta?: (text: string) => void
  onToolStart?: (data: Record<string, unknown>) => void
  onToolEnd?: (data: Record<string, unknown>) => void
  onDone?: (data: Record<string, unknown>) => void
  onError?: (message: string, code?: string) => void
}
