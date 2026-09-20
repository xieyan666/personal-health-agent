import { request } from './request'

export type NotificationType = 'system' | 'agent_error' | 'health_report' | 'health_risk' | 'health_plan' | 'mental_health' | 'health_service' | 'authorization'

export interface UserNotification {
  id: string
  type: NotificationType
  title: string
  content: string
  is_read: boolean
  target_path?: string | null
  created_at: string
}
export interface NotificationPreferences {
  system: boolean
  agent_error: boolean
  health_report: boolean
  health_risk: boolean
  health_plan: boolean
  mental_health: boolean
  health_service: boolean
  authorization: boolean
}

export const getNotifications = (limit = 6) => request.get<UserNotification[]>('/notifications', { params: { limit } }).then(r => r.data)
export const getNotificationUnreadCount = () => request.get<{ unread_count: number }>('/notifications/unread-count').then(r => r.data)
export const markNotificationRead = (id: string) => request.patch<UserNotification>(`/notifications/${id}/read`).then(r => r.data)
export const markAllNotificationsRead = () => request.post<{ unread_count: number }>('/notifications/read-all').then(r => r.data)
export const getNotificationPreferences = () => request.get<NotificationPreferences>('/user/notification-preferences').then(r => r.data)
export const updateNotificationPreferences = (data: Partial<NotificationPreferences>) => request.patch<NotificationPreferences>('/user/notification-preferences', data).then(r => r.data)
