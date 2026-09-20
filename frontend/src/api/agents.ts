import { request } from './request'

export interface AgentItem {
  id: string
  name: string
  slug: string
  type: 'Supervisor' | 'Specialist'
  status: 'enabled' | 'disabled'
  enabled: boolean
  domain: string
  description: string
  model: string
  model_name: string | null
  knowledgeBases: { id: string; name: string; status: string }[]
  tools: { id: string; name: string; status: string }[]
  todayRuns: number
  weekRuns: number
  exceptions: number
  successRate: number | null
  latency: number | null
  toolCalls: number | null
  hitRate: number | null
  createdAt: string | null
  updatedAt: string | null
  responsibilities: string[]
  capabilities: { route: boolean; tool: boolean; knowledge: boolean; output: boolean }
  config: Record<string, unknown>
}
export interface AgentSummary {
  total: number
  enabled: number
  todayRuns: number
  recentExceptions: number
}
export interface AgentRunItem {
  id: string
  time: string | null
  input: string
  status: string
  latency: number | null
  error: string | null
}

export const agentAdminApi = {
  list: () => request.get<{ items: AgentItem[] }>('/admin/agents').then(r => r.data.items),
  summary: () => request.get<AgentSummary>('/admin/agents/summary').then(r => r.data),
  detail: (id: string) => request.get<AgentItem>(`/admin/agents/${id}`).then(r => r.data),
  runs: (id: string, days = 7) => request.get<{ items: AgentRunItem[] }>(`/admin/agents/${id}/runs`, { params: { days } }).then(r => r.data.items),
  updateStatus: (id: string, status: string) => request.patch<AgentItem>(`/admin/agents/${id}/status`, { status }).then(r => r.data),
  test: (id: string, content: string) => request.post<{ status: string; run_id: string; assistant_content: string; steps: { name: string; status: string }[] }>(`/admin/agents/${id}/test`, { content }).then(r => r.data),
}
