import { request } from './request'

export interface RiskCaseStats { pending: number; high_priority: number; processing: number; closed_this_month: number }
export interface RiskCaseItem {
  id: string
  risk_assessment_id: string
  user_id: string
  risk_type: string
  risk_level: string
  source: string | null
  department: string | null
  status: string
  assigned_plan_id: string | null
  assigned_service_id: string | null
  next_review_at: string | null
  created_at: string
  updated_at: string
  confirmed_at: string | null
  resolved_at: string | null
}
export interface RiskCaseAction { id: string; actor_user_id: string | null; actor_name: string | null; action: string; note: string | null; created_at: string }
export interface RiskCaseDetail extends RiskCaseItem {
  resolution_note: string | null
  ignore_reason: string | null
  risk_summary: string | null
  actions: RiskCaseAction[]
}
export interface RiskCaseListResponse { stats: RiskCaseStats; items: RiskCaseItem[]; departments: string[] }
export interface ServiceOption { id: string; name: string; category: string; description: string | null; delivery_mode: string }
export interface PlanOption { id: string; plan_name: string; plan_type: string; status: string }
export interface RiskCaseOptions { services: ServiceOption[]; plans: PlanOption[] }

export const getRiskCases = (params: { period?: string; department?: string; level?: string; source?: string; status?: string } = {}) =>
  request.get<RiskCaseListResponse>('/admin/risk-cases', { params }).then(r => r.data)
export const getRiskCase = (id: string) => request.get<RiskCaseDetail>(`/admin/risk-cases/${id}`).then(r => r.data)
export const getRiskCaseOptions = (caseId: string) => request.get<RiskCaseOptions>('/admin/risk-cases/options', { params: { case_id: caseId } }).then(r => r.data)
export const updateRiskCaseStatus = (id: string, payload: { action: string; note?: string; ignore_reason?: string; next_review_days?: number }) =>
  request.patch<RiskCaseDetail>(`/admin/risk-cases/${id}/status`, payload).then(r => r.data)
export const linkRiskCasePlan = (id: string, planId: string) =>
  request.post<RiskCaseDetail>(`/admin/risk-cases/${id}/link-plan`, { plan_id: planId }).then(r => r.data)
export const linkRiskCaseService = (id: string, serviceId: string) =>
  request.post<RiskCaseDetail>(`/admin/risk-cases/${id}/link-service`, { service_id: serviceId }).then(r => r.data)
