import { request } from './request'

export interface HealthService {
  id: string
  name: string
  category: 'medical_exam' | 'medical_consult' | 'nutrition' | 'exercise' | 'course'
  description?: string | null
  duration_minutes?: number | null
  delivery_mode: 'online' | 'offline'
  suitability?: string | null
  is_annual_check: boolean
}
export interface Recommendation {
  service: HealthService
  reason: string
}
export interface ServiceRecommendationItem {
  service_id: string
  service_name: string
  category: string
  priority: number
  reason: string
  sources: string[]
  ai_generated: boolean
}
export interface ServiceRecommendationList {
  recommendations: ServiceRecommendationItem[]
  ai_status: 'ok' | 'fallback' | 'empty'
}
export interface HealthActivity {
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
  schedule?: string | null
  duration_minutes?: number | null
  capacity?: number | null
  participants: number
  remaining?: number | null
  status: string
  display_status: string
  display_status_label?: string
  joined: boolean
}
export interface MyHealthActivity {
  id: string
  activity_id: string
  group: 'upcoming' | 'finished' | 'cancelled'
  status: string
  activity: HealthActivity
  joined_at: string | null
}
export interface HealthServiceBooking {
  id: string
  service_id: string
  service_name: string
  category: string
  booking_date: string
  booking_time: string
  status: 'pending' | 'confirmed' | 'in_progress' | 'completed' | 'cancelled'
  provider?: string | null
}
export interface EmployeeHealthBenefit {
  id: string
  benefit_type: string
  benefit_name: string
  annual_quota: number
  used_quota: number
  remaining_quota: number
}

export const getHealthServices = () => request.get<HealthService[]>('/health-services').then(r => r.data)
export const getHealthServiceRecommendations = () => request.get<ServiceRecommendationList>('/health-services/recommendations').then(r => r.data)
export const getHealthActivities = () => request.get<HealthActivity[]>('/health-activities').then(r => r.data)
export const getHealthActivity = (id: string) => request.get<HealthActivity>(`/health-activities/${id}`).then(r => r.data)
export const joinHealthActivity = (id: string) => request.post<HealthActivity>(`/health-activities/${id}/join`).then(r => r.data)
export const cancelHealthActivity = (id: string) => request.post<HealthActivity>(`/health-activities/${id}/cancel`).then(r => r.data)
export const getMyHealthActivities = () => request.get<MyHealthActivity[]>('/my-health-activities').then(r => r.data)
export const getHealthServiceBookings = () => request.get<HealthServiceBooking[]>('/health-service-bookings').then(r => r.data)
export const createHealthServiceBooking = (data: { service_id: string; booking_date: string; booking_time: string; approval_id?: string }) => request.post<HealthServiceBooking>('/health-service-bookings', data).then(r => r.data)
export const cancelHealthServiceBooking = (id: string) => request.patch<HealthServiceBooking>(`/health-service-bookings/${id}/cancel`).then(r => r.data)
export const getHealthBenefits = () => request.get<EmployeeHealthBenefit[]>('/health-benefits').then(r => r.data)
