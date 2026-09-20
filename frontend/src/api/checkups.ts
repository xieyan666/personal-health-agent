import { request } from './request'

export interface CheckupStats { total_reports: number; parsed_count: number; pending_review_reports: number; abnormal_reports: number }
export interface CheckupListItem {
  id: string
  employee_name: string | null
  employee_no: string | null
  department: string | null
  report_name: string
  hospital: string | null
  report_date: string | null
  uploaded_at: string
  parse_method: string | null
  parse_mode: string | null
  indicator_count: number
  abnormal_count: number
  parse_status: string
  display_status: string
  pending_review: boolean
  ocr_used: boolean
  parse_error: string | null
}
export interface CheckupIndicator {
  id: string
  item_name: string
  value: number
  value_text: string | null
  unit: string | null
  reference_text: string | null
  flag: string
  source_type: string
  confidence: number | null
  review_status: string | null
  reviewed_value: number | null
  review_note: string | null
}
export interface CheckupDetail extends CheckupListItem {
  parse_warnings: Record<string, unknown> | null
  parsed_at: string | null
  items: CheckupIndicator[]
}
export interface DistributionItem { label: string; count: number; percent: number }
export interface CheckupSummary {
  stats: CheckupStats
  status_distribution: DistributionItem[]
  method_distribution: DistributionItem[]
  departments: string[]
}

export const getCheckupSummary = (period: string) => request.get<CheckupSummary>('/admin/checkups/summary', { params: { period } }).then(r => r.data)
export const getCheckups = (params: { period?: string; department?: string; status?: string; method?: string } = {}) =>
  request.get<CheckupListItem[]>('/admin/checkups', { params }).then(r => r.data)
export const getCheckup = (id: string) => request.get<CheckupDetail>(`/admin/checkups/${id}`).then(r => r.data)
export const reparseCheckup = (id: string) => request.post<CheckupDetail>(`/admin/checkups/${id}/reparse`).then(r => r.data)
export const reviewIndicator = (indicatorId: string, payload: { action: string; reviewed_value?: number; note?: string }) =>
  request.patch<CheckupIndicator>(`/admin/checkups/indicators/${indicatorId}/review`, payload).then(r => r.data)
