import { request } from './request'

export type DataScope = { code: string; name: string; category: 'health' | 'wearable' | 'mental' | 'service'; sensitive?: boolean }
export type DataConsent = { id: string; grantee_type: 'agent' | 'service' | 'enterprise'; grantee_id: string; scope: string; purpose: string; status: 'active' | 'revoked' | 'expired'; granted_at: string; expires_at?: string | null; revoked_at?: string | null }
export type AuthorizationOverview = { active_consent_count: number; active_scope_count: number; ai_consent_count: number; service_consent_count: number; mental_scope_enabled: boolean; last_access_at?: string | null; pending_approval_count: number }
export type AuthorizationAccessLog = { id: string; actor_type: string; actor_id?: string | null; scope?: string | null; purpose?: string | null; action: string; outcome: string; created_at: string }
export type AgentApproval = { id: string; action_type: string; action_payload: Record<string, unknown>; status: string; requested_at: string; decided_at?: string | null; expires_at?: string | null }

export const getAuthorizationOverview = () => request.get<AuthorizationOverview>('/data-authorizations/overview').then((r) => r.data)
export const getAuthorizationScopes = () => request.get<{ scopes: DataScope[] }>('/data-authorizations/scopes').then((r) => r.data.scopes)
export const getDataConsents = () => request.get<DataConsent[]>('/data-authorizations/consents').then((r) => r.data)
export const createDataConsent = (data: Omit<DataConsent, 'id' | 'status' | 'granted_at' | 'revoked_at'>) => request.post<DataConsent>('/data-authorizations/consents', data).then((r) => r.data)
export const revokeDataConsent = (id: string) => request.post<DataConsent>(`/data-authorizations/consents/${id}/revoke`).then((r) => r.data)
export const getAuthorizationAccessLogs = () => request.get<AuthorizationAccessLog[]>('/data-authorizations/access-logs').then((r) => r.data)
export const getAgentApprovals = () => request.get<AgentApproval[]>('/data-authorizations/approvals').then((r) => r.data)
export const createAgentApproval = (data: { action_type: string; action_payload: Record<string, unknown>; expires_at?: string | null }) => request.post<AgentApproval>('/data-authorizations/approvals', data).then((r) => r.data)
export const approveAgentApproval = (id: string, decision_note?: string) => request.post<AgentApproval>(`/data-authorizations/approvals/${id}/approve`, { decision_note }).then((r) => r.data)
