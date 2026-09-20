import { request } from './request'
import { getAccessToken } from '../utils/token'

export interface HealthChatRequest {
  message: string
  conversation_id: string | null
  source_context?: {
    source: 'mental_assessment'
    assessment_id: string
    assessment_type: string
  } | null
}

export interface HealthChatResponse {
  answer: string
  conversation_id?: string | null
}

export const chatHealth = (payload: HealthChatRequest) => request.post<HealthChatResponse>('/health-agent/chat', payload).then(response => response.data)

export interface ConversationSummary { id: string; title?: string | null; created_at: string; updated_at: string; last_message_at?: string | null }
export interface ConversationMessage { id: string; conversation_id: string; role: 'user' | 'assistant' | 'system' | 'tool'; content: string; created_at: string }
export const listConversations = () => request.get<ConversationSummary[]>('/conversations').then(response => response.data)
export const createConversation = (title: string) => request.post<ConversationSummary>('/conversations', { title }).then(response => response.data)
export const listConversationMessages = (id: string) => request.get<ConversationMessage[]>('/messages', { params: { conversation_id: id } }).then(response => response.data)

export async function streamHealth(payload: HealthChatRequest, onChunk: (content: string, conversationId?: string) => void) {
  const base = import.meta.env.VITE_API_BASE_URL ?? '/api/v1'
  const response = await fetch(`${base}/health-agent/chat/stream`, { method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${getAccessToken() ?? ''}` }, body: JSON.stringify(payload) })
  if (!response.ok || !response.body) throw new Error('stream request failed')
  const reader = response.body.getReader(); const decoder = new TextDecoder(); let buffer = ''
  while (true) {
    const { value, done } = await reader.read(); if (done) break
    buffer += decoder.decode(value, { stream: true })
    const events = buffer.split('\n\n'); buffer = events.pop() ?? ''
    for (const event of events) {
      const line = event.split('\n').find(item => item.startsWith('data:'))
      if (!line) continue
      const data = JSON.parse(line.slice(5).trim()) as { content?: string; conversation_id?: string; detail?: string }
      if (data.content) onChunk(data.content, data.conversation_id)
      if (event.startsWith('event: error')) throw new Error(data.detail || 'stream failed')
    }
  }
}
