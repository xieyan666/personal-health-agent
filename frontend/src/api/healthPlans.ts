import { request } from './request'

export interface HealthPlanTask {
  id: string
  plan_id: string
  day_index: number
  task_date?: string | null
  task_type: string
  title: string
  description?: string | null
  target_value?: string | null
  actual_value?: string | null
  completion_status: 'pending' | 'completed' | 'skipped'
  completion_source: 'manual' | 'wearable' | 'health_profile' | 'mental_checkin'
  completed_at?: string | null
}
export interface HealthPlanStats {
  executed_days: number
  total_days: number
  task_completion_rate: number
  streak_days: number
  completed_tasks: number
  total_tasks: number
}
export interface HealthPlan {
  id: string
  plan_name: string
  plan_type: string
  goal?: string | null
  duration_days: number
  start_date: string
  end_date: string
  status: 'draft' | 'active' | 'paused' | 'completed' | 'cancelled' | 'none'
  source_agent: string
  created_at: string
  updated_at: string
  tasks: HealthPlanTask[]
  stats?: HealthPlanStats | null
  current_day?: number | null
}
export interface HealthPlanSummary {
  id: string
  plan_name: string
  plan_type: string
  goal?: string | null
  duration_days: number
  start_date: string
  end_date: string
  status: string
  source_agent: string
  created_at: string
  stats?: HealthPlanStats | null
}

export const getCurrentHealthPlan = () => request.get<HealthPlan>('/health-plans/current').then(r => r.data)
export const getHealthPlans = () => request.get<HealthPlanSummary[]>('/health-plans').then(r => r.data)
export const getHealthPlan = (id: string) => request.get<HealthPlan>(`/health-plans/${id}`).then(r => r.data)
export const getHealthPlanTasks = (id: string) => request.get<HealthPlanTask[]>(`/health-plans/${id}/tasks`).then(r => r.data)
export const completeHealthPlanTask = (taskId: string) => request.patch<HealthPlanTask>(`/health-plan-tasks/${taskId}/complete`).then(r => r.data)
export const uncompleteHealthPlanTask = (taskId: string) => request.patch<HealthPlanTask>(`/health-plan-tasks/${taskId}/uncomplete`).then(r => r.data)
export const pauseHealthPlan = (id: string) => request.patch<HealthPlan>(`/health-plans/${id}/pause`).then(r => r.data)
export const resumeHealthPlan = (id: string) => request.patch<HealthPlan>(`/health-plans/${id}/resume`).then(r => r.data)
export const completeHealthPlan = (id: string) => request.patch<HealthPlan>(`/health-plans/${id}/complete`).then(r => r.data)
