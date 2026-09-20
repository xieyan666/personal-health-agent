import { request } from './request'
export interface HealthProfile { user_id: string; username: string; age?: number | null; gender?: string | null; height?: number | null; weight?: number | null; bmi?: number | null }
export const getHealthProfile = () => request.get<HealthProfile>('/health/profile').then(r => r.data)
export const updateHealthProfile = (payload: Omit<HealthProfile, 'user_id' | 'username' | 'bmi'>) => request.put<HealthProfile>('/health/profile', payload).then(r => r.data)
export interface HealthTrends { sleep: any[]; exercise: any[]; heart_rate: any[] }
export interface HealthSummary { profile: any; sleep: any; exercise: any; heart_rate: any }
export const getHealthTrends = (params?: { days?: number; start_date?: string; end_date?: string }) => request.get<HealthTrends>('/health/trends', { params }).then(r => r.data)
export const getHealthSummary = () => request.get<HealthSummary>('/health/summary').then(r => r.data)
export interface RiskAssessment { risk_type: string; level: string; description: string; recommendation: string; source: string }
export const getHealthRisk = () => request.get<RiskAssessment[]>('/health/risk').then(r => r.data)
export interface HealthRiskTrendPoint { period:string; start_date:string; end_date:string; score:number; level:string; factors:string[] }
export interface HealthRiskTrend { period:string; dimension:string; data:HealthRiskTrendPoint[] }
export const getHealthRiskTrend = () => request.get<HealthRiskTrend>('/health-risk/trend').then(r => r.data)
export interface HealthRiskHistoryRecord { id:string; date:string; period_start:string; period_end:string; score:number; level:string; factor:string; data_source:string }
export interface HealthRiskHistory { user_id:string; records:HealthRiskHistoryRecord[] }
export const getHealthRiskHistory = () => request.get<HealthRiskHistory>('/health-risk/history').then(r => r.data)
