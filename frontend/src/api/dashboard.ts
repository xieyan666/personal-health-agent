import { request } from './request'

export type DashboardTone = 'normal' | 'attention' | 'info'

export interface DashboardSummary {
  health_overview: { label: string; score?: number | null; assessed_at?: string | null }
  risk_summary: { attention_count: number; primary_factor?: string | null; status: 'normal' | 'attention' | 'high' | 'empty' }
  active_plan: { id?: string | null; name?: string | null; current_day?: number | null; duration_days?: number | null; completion_rate?: number | null; status: string }
  mental_today: { checked_in: boolean; mood?: string | null; stress_level?: number | null }
  recommendations: Array<{ id: string; title: string; description: string; source: string; target_path: string; tone: DashboardTone }>
  today_tasks: Array<{ id: string; title: string; source: string; target_path: string; status: 'pending' | 'completed'; detail?: string | null }>
  recent_activities: Array<{ id: string; title: string; occurred_at: string; target_path?: string | null; kind: string }>
}

export const getDashboardSummary = () => request.get<DashboardSummary>('/dashboard/summary').then((response) => response.data)
