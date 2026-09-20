import { request } from './request'

export interface ModelOverviewItem {
  id: string
  name: string
  model_name: string
  model_type: string
  model_type_label: string
  status: string
  is_default: boolean
  vector_dimension: number | null
  parameters: Record<string, unknown>
  provider_id: string
  provider_name: string
  provider_type: string
  used_by_agents: string[]
  used_by_knowledge_bases: string[]
  updated_at: string | null
}
export interface ProviderItem {
  id: string
  name: string
  provider_type: string
  status: string
  endpoint: string | null
  api_key_masked: string | null
  secret_ref: string | null
  model_count: number
  updated_at: string | null
}
export interface ModelOverview {
  models: ModelOverviewItem[]
  providers: ProviderItem[]
  defaults: { chat: string | null; embedding: string | null; reranker: string | null }
  warnings: { formal_embedding_missing: boolean; embedding_note: string }
}
export interface QdrantDimensionInfo {
  collections: { collection: string; dimension: number | null }[]
  default_embedding: { id: string | null; name: string | null; dimension: number | null; fake: boolean | null } | null
  mismatch: { collection: string; dimension: number | null }[]
}
export interface UsageInfo {
  chat: {
    total_runs: number
    today_runs: number
    success_rate: number
    prompt_tokens: number
    completion_tokens: number
    trend: { date: string; count: number }[]
    recent_errors: { id: string; status: string; error_code: string | null; error_message: string | null; created_at: string | null }[]
  }
  embedding: { indexed_documents: number; knowledge_bases: { knowledge_base: string; embedding_model_id: string | null }[] }
}
export interface TestResult {
  success: boolean
  model_id?: string
  model_name?: string
  dimension?: number
  duration_ms: number
  response?: string
  vector_head?: number[]
  fake?: boolean
}

export const modelApi = {
  overview: () => request.get<ModelOverview>('/admin/models/overview').then(r => r.data),
  qdrantDimension: () => request.get<QdrantDimensionInfo>('/admin/models/qdrant-dimension').then(r => r.data),
  usage: () => request.get<UsageInfo>('/admin/models/usage').then(r => r.data),
  testChat: (id: string) => request.post<TestResult>(`/admin/models/${id}/test-chat`).then(r => r.data),
  testEmbedding: (id: string, text: string) => request.post<TestResult>(`/admin/models/${id}/test-embedding`, { text }).then(r => r.data),
  setDefault: (id: string) => request.post<{ id: string; name: string; model_type: string; is_default: boolean; vector_dimension: number | null; qdrant_mismatch: { collection: string; dimension: number | null }[]; qdrant_dimensions: (number | null)[] }>(`/admin/models/${id}/set-default`).then(r => r.data),
  updateConfig: (id: string, body: { name?: string; model_name?: string; status?: string; is_default?: boolean; vector_dimension?: number | null; parameters?: Record<string, unknown> }) =>
    request.patch(`/admin/models/${id}`, body).then(r => r.data),
  createProvider: (body: { name: string; provider_type: string; endpoint?: string | null; api_key?: string | null; status?: string }) =>
    request.post<ProviderItem>('/admin/models/providers', body).then(r => r.data),
  updateProvider: (id: string, body: { name?: string; endpoint?: string | null; api_key?: string | null; status?: string }) =>
    request.patch<ProviderItem>(`/admin/models/providers/${id}`, body).then(r => r.data),
  testProvider: (id: string) => request.post<{ success: boolean; provider_type: string; duration_ms: number; detail: string }>(`/admin/models/providers/${id}/test`).then(r => r.data),
}
