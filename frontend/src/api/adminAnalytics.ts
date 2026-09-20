import { request } from './request'

export interface AnalyticsOverview {
  total_employees: number
  covered_employees: number
  coverage_rate: number
  attention_employees: number
  attention_rate: number
  abnormal_exam_employees: number
  plan_participants: number
  plan_participation_rate: number
}
export interface HealthDistributionItem { level: string; label: string; count: number; percent: number }
export interface RiskRankingItem { risk_type: string; label: string; count: number; percent: number }
export interface DepartmentStat { department: string; total: number; coverage_rate: number; healthy_rate: number; attention_count: number; attention_rate: number; top_risk: string | null; sample_too_small: boolean }
export interface TrendPoint { period: string; label: string; value: number; evaluated: number }
export interface HealthAnalyticsSummary {
  period: string
  department?: string | null
  overview: AnalyticsOverview
  health_distribution: HealthDistributionItem[]
  risk_ranking: RiskRankingItem[]
  department_stats: DepartmentStat[]
  risk_trend: TrendPoint[]
  available_departments: string[]
}

export const getHealthAnalyticsSummary = (period: string, department?: string | null) =>
  request.get<HealthAnalyticsSummary>('/admin/health-analytics/summary', { params: { period, department: department || undefined } }).then(r => r.data)
