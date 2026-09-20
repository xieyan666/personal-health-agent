import { request } from './request'

export interface ServiceHealth {
  key: string
  name: string
  status: 'ok' | 'error' | 'unconfigured'
  latency_ms: number
  detail: string
}
export interface SystemOverview {
  overall_status: 'normal' | 'partial' | 'critical'
  services: ServiceHealth[]
  services_available: string
  resources: { available: boolean; note?: string; cpu_percent?: number; memory_percent?: number; memory_used_gb?: number; memory_total_gb?: number; disk_percent?: number; uptime_hours?: number }
  api: {
    today: { total: number; errors: number; success_rate: number | null; avg_duration_ms: number | null }
    trend: { hour: { label: string; count: number }[]; day: { label: string; count: number }[]; week: { label: string; count: number }[] }
    slow_endpoints: { path: string; method: string; avg_ms: number; calls: number; error_rate: number }[]
  }
  agents: {
    today_runs: number
    today_success_rate: number | null
    avg_latency_ms: number | null
    exceptions: number
    recent_errors: { id: string; agent: string; error_code: string | null; error_message: string | null; trace_id: string | null; created_at: string | null }[]
  }
  tasks: { running: number; waiting: number; completed_today: number; failed: number; tasks: SystemTask[] }
  alerts: { open: number; today_total: number }
  checked_at: string
}
export interface SystemTask {
  id: string
  name: string
  task_type: string
  source: string
  created_at: string | null
  updated_at: string | null
  status: 'pending' | 'running' | 'success' | 'failed'
  error: string | null
  related: string
}
export interface SystemAlert {
  id: string
  source: string
  level: string
  error_code: string | null
  message: string
  trace_id: string | null
  details: string | null
  status: string
  created_at: string | null
  resolved_at: string | null
}
export interface SystemLog {
  id: string
  time: string | null
  service: string
  level: string
  message: string
  trace_id: string | null
  action: string
  resource_type: string
  outcome: string
  details: Record<string, unknown>
}

export const monitorApi = {
  overview: () => request.get<SystemOverview>('/admin/system-monitor/overview').then(r => r.data),
  tasks: () => request.get<{ running: number; waiting: number; completed_today: number; failed: number; tasks: SystemTask[] }>('/admin/system-monitor/tasks').then(r => r.data),
  alerts: (limit = 50) => request.get<SystemAlert[]>('/admin/system-monitor/alerts', { params: { limit } }).then(r => r.data),
  updateAlertStatus: (id: string, status: string) => request.post(`/admin/system-monitor/alerts/${id}/status`, { status }).then(r => r.data),
  logs: (params: { source?: string; level?: string; trace_id?: string; limit?: number }) => request.get<SystemLog[]>('/admin/system-monitor/logs', { params }).then(r => r.data),
}
