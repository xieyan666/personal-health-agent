import { request } from './request'

export interface MentalCheckin {
  id: string
  checkin_date: string
  mood: string
  stress_level: number
  energy_level: number
  sleep_feeling: string
  stress_sources: string[]
  note?: string | null
}
export interface MentalCheckinCreate {
  mood: string
  stress_level: number
  energy_level: number
  sleep_feeling: string
  stress_sources: string[]
  note?: string | null
}
export interface MentalTrendPoint { date: string; value: number }
export interface MentalTrend { type: 'mood' | 'stress' | 'energy'; period: number; average: number; change: number; data: MentalTrendPoint[] }
export interface StressSourceShare { name: string; percent: number }
export interface MentalWorkload {
  week_avg_stress: number
  high_stress_days: number
  avg_energy: number
  recovery_status: string
  stress_sources: StressSourceShare[]
  has_data: boolean
}
export interface MentalAssessment {
  id: string; assessment_type: string; assessment_version: string; score?: number | null
  raw_score?: number | null; percentage_score?: number | null; level?: string | null
  needs_follow_up?: boolean; safety_flag?: boolean; safety_reason?: string | null
  result_summary?: Record<string, unknown> | null; completed_at?: string | null
}
export interface MentalAssessmentOption { label: string; value: number }
export interface MentalAssessmentQuestion { id: string; order: number; text: string; required: boolean; options: MentalAssessmentOption[]; safety_sensitive?: boolean }
export interface MentalAssessmentDefinition {
  assessment_type: string
  version: string
  name: string
  title: string
  description: string
  question_count: number
  estimated_minutes: number
  estimated_duration?: string | null
  result_usage: string
  disclaimer: string
  questionnaire_status: 'configured' | 'questionnaire_not_configured'
  period?: string
  source?: { source_name?: string; source_version?: string; source_url?: string; license?: string }
  enabled?: boolean
  result_note?: string | null
  questions: MentalAssessmentQuestion[]
}
export interface MentalAssessmentAnswer { question_id: string; value: number }
export interface MentalAssessmentSubmit { assessment_type: string; assessment_version: string; answers: MentalAssessmentAnswer[] }

export const getTodayMentalCheckin = () => request.get<MentalCheckin | null>('/mental-health/checkins/today').then(r => r.data)
export const saveMentalCheckin = (data: MentalCheckinCreate) => request.post<MentalCheckin>('/mental-health/checkins', data).then(r => r.data)
export const getMentalTrend = (type: 'mood' | 'stress' | 'energy', days: number) => request.get<MentalTrend>('/mental-health/trends', { params: { type, days } }).then(r => r.data)
export const getMentalWorkload = () => request.get<MentalWorkload>('/mental-health/workload').then(r => r.data)
export const getMentalAssessments = () => request.get<MentalAssessment[]>('/mental-health/assessments').then(r => r.data)
export const getMentalAssessmentDefinitions = () => request.get<MentalAssessmentDefinition[]>('/mental-health/assessment-definitions').then(r => r.data)
export const submitMentalAssessment = (data: MentalAssessmentSubmit) => request.post<MentalAssessment>('/mental-health/assessments', data).then(r => r.data)
