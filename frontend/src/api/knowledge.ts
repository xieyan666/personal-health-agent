import { request } from './request'

export type KnowledgeBase = {
  id: string
  name: string
  domain: string
  description?: string | null
  status: string
  document_count: number
  chunk_count: number
  vector_progress: number
  updated_at: string
  agents: { id: string; name: string; code: string }[]
}
export type KnowledgeDocument = {
  id: string
  name: string
  status: string
  size_bytes?: number | null
  mime_type?: string | null
  error_message?: string | null
  metadata?: Record<string, unknown> | null
  created_at: string
  updated_at?: string
}
export type KnowledgeChunk = {
  id: string
  document_id: string
  document_name: string
  chunk_index: number
  char_count: number
  content: string
}
export type RagStatus = {
  components: Record<string, { name: string; status: 'ok' | 'degraded' }>
  stats: { pending_documents: number; index_failures: number; total_chunks: number; last_indexed_at: string | null }
  recent: { id: string; document_name: string; status: string; chunk_count: number; updated_at: string; error_message: string | null }[]
}
export type RetrieveItem = {
  score: number
  content: string
  document_id: string
  document_name: string
  chunk_index: number
  source: string
}

export const knowledgeApi = {
  list: () => request.get<KnowledgeBase[]>('/admin/knowledge-bases').then(r => r.data),
  create: (body: { name: string; domain: string; description?: string; enabled: boolean; agent_ids: string[] }) =>
    request.post<KnowledgeBase>('/admin/knowledge-bases', body).then(r => r.data),
  agents: () => request.get<{ id: string; name: string; code: string; category: string }[]>('/admin/knowledge-bases/agents').then(r => r.data),
  ragStatus: () => request.get<RagStatus>('/admin/knowledge-bases/rag-status').then(r => r.data),
  documents: (id: string) => request.get<KnowledgeDocument[]>(`/admin/knowledge-bases/${id}/documents`).then(r => r.data),
  chunks: (id: string) => request.get<KnowledgeChunk[]>(`/admin/knowledge-bases/${id}/chunks`).then(r => r.data),
  upload: (id: string, file: File) => {
    const data = new FormData()
    data.append('file', file)
    return request.post<KnowledgeDocument>(`/admin/knowledge-bases/${id}/documents`, data).then(r => r.data)
  },
  retry: (id: string, documentId: string) => request.post<KnowledgeDocument>(`/admin/knowledge-bases/${id}/documents/${documentId}/retry`).then(r => r.data),
  deleteDocument: (id: string, documentId: string) => request.delete(`/admin/knowledge-bases/${id}/documents/${documentId}`),
  deleteBase: (id: string) => request.delete(`/admin/knowledge-bases/${id}`),
  retrieve: (id: string, query: string, top_k: number) =>
    request.post<{ items: RetrieveItem[] }>(`/admin/knowledge-bases/${id}/retrieve`, { query, top_k }).then(r => r.data),
  bindAgents: (id: string, agent_ids: string[]) =>
    request.put<KnowledgeBase>(`/admin/knowledge-bases/${id}/agents`, { agent_ids }).then(r => r.data),
}
