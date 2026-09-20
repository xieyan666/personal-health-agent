import { request } from './request'

export const ACTIVITY_TYPE_LABELS: Record<string, string> = {
  lecture: '健康讲座',
  exercise: '运动活动',
  nutrition: '营养课程',
  education: '健康教育',
  exam_promo: '体检宣教',
  other: '其他',
}

export const ACTIVITY_STATUS_LABELS: Record<string, { label: string; color: string }> = {
  draft: { label: '草稿', color: 'default' },
  registration_open: { label: '报名中', color: 'green' },
  registration_closed: { label: '报名截止', color: 'orange' },
  ongoing: { label: '进行中', color: 'processing' },
  finished: { label: '已结束', color: 'default' },
  cancelled: { label: '已取消', color: 'red' },
  active: { label: '进行中', color: 'processing' },
}

export interface AdminActivity {
  id: string
  name: string
  activity_type: string
  activity_type_label?: string
  description?: string | null
  start_date?: string | null
  end_date?: string | null
  start_time?: string | null
  end_time?: string | null
  registration_deadline?: string | null
  delivery_mode: 'online' | 'offline'
  location?: string | null
  scope: 'all' | 'department'
  target_department?: string | null
  organizer?: string | null
  contact_person?: string | null
  capacity?: number | null
  participants: number
  remaining?: number | null
  status: string
  display_status: string
  display_status_label?: string
  joined?: boolean
  created_at?: string | null
}

export interface ActivityParticipant {
  id: string
  user_id: string
  employee_no: string | null
  employee_name: string | null
  department: string | null
  joined_at: string | null
  status: string
}

export interface AdminActivitySummary {
  month_activity_count: number
  open_registration_count: number
  total_participants: number
  avg_participation_rate: number
}

export interface ActivityDynamic {
  id: string
  activity_id: string
  activity_name: string
  department: string | null
  employee_name: string | null
  action: 'joined' | 'cancelled'
  occurred_at: string | null
}

export type ActivityPayload = {
  name: string
  activity_type: string
  description?: string | null
  start_date?: string | null
  end_date?: string | null
  start_time?: string | null
  end_time?: string | null
  registration_deadline?: string | null
  delivery_mode: 'online' | 'offline'
  location?: string | null
  scope: 'all' | 'department'
  target_department?: string | null
  organizer?: string | null
  contact_person?: string | null
  capacity?: number | null
}

export const getAdminActivities = () => request.get<AdminActivity[]>('/admin/health-activities').then(r => r.data)
export const getAdminActivity = (id: string) => request.get<AdminActivity>(`/admin/health-activities/${id}`).then(r => r.data)
export const getAdminActivitySummary = () => request.get<AdminActivitySummary>('/admin/health-activities/summary').then(r => r.data)
export const getAdminActivityDynamics = (limit = 12) => request.get<ActivityDynamic[]>('/admin/health-activities/dynamics', { params: { limit } }).then(r => r.data)
export const createAdminActivity = (payload: ActivityPayload) => request.post<AdminActivity>('/admin/health-activities', payload).then(r => r.data)
export const updateAdminActivity = (id: string, payload: ActivityPayload) => request.patch<AdminActivity>(`/admin/health-activities/${id}`, payload).then(r => r.data)
export const publishAdminActivity = (id: string) => request.post<AdminActivity>(`/admin/health-activities/${id}/publish`).then(r => r.data)
export const cancelAdminActivity = (id: string) => request.post<AdminActivity>(`/admin/health-activities/${id}/cancel`).then(r => r.data)
export const finishAdminActivity = (id: string) => request.post<AdminActivity>(`/admin/health-activities/${id}/finish`).then(r => r.data)
export const getAdminActivityParticipants = (id: string) => request.get<ActivityParticipant[]>(`/admin/health-activities/${id}/participants`).then(r => r.data)
