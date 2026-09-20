import { request } from './request'

export interface UserProfile {
  id: string
  username: string
  display_name: string
  email?: string | null
  phone?: string | null
  department?: string | null
  job_title?: string | null
  office_location?: string | null
  bio?: string | null
  avatar_url?: string | null
  role: string
  status: string
}
export interface UserProfileUpdate {
  display_name?: string
  email?: string | null
  phone?: string | null
  department?: string | null
  job_title?: string | null
  office_location?: string | null
  bio?: string | null
}

export const getUserProfile = () => request.get<UserProfile>('/users/me/profile').then(r => r.data)
export const updateUserProfile = (data: UserProfileUpdate) => request.patch<UserProfile>('/users/me/profile', data).then(r => r.data)
export const uploadUserAvatar = (file: File) => {
  const data = new FormData()
  data.append('file', file)
  return request.put<UserProfile>('/users/me/avatar', data).then(r => r.data)
}
export const getUserAvatar = () => request.get<Blob>('/users/me/avatar', { responseType: 'blob' }).then(r => r.data)
export const changeMyPassword = (currentPassword: string, newPassword: string) =>
  request.post<{ status: string }>('/users/me/change-password', {
    current_password: currentPassword,
    new_password: newPassword,
  }).then(r => r.data)
