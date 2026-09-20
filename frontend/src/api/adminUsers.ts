import { request } from './request'
export interface ManagedUser { id: string; username: string; name: string; display_name?: string; employee_no?: string; department?: string; position?: string; department_id?: string; position_id?: string; role: string; status: string; company_id?: string }
export const listManagedUsers = (q?: string) => request.get<ManagedUser[]>('/admin/users', { params: q ? { keyword: q } : undefined }).then(r => r.data)
export const createManagedUser = (payload: Record<string, unknown>) => request.post<ManagedUser>('/admin/users', payload).then(r => r.data)
export const updateManagedRole = (id: string, role: string) => request.put(`/admin/users/${id}/role`, { role })
export const updateManagedUser = (id: string, payload: Record<string, unknown>) => request.put<ManagedUser>(`/admin/users/${id}`, payload).then(r => r.data)
export const deleteManagedUser = (id: string) => request.delete(`/admin/users/${id}`)
export const setManagedStatus = (id: string, status: string) => request.patch(`/admin/users/${id}/status`, { status })
export const resetManagedPassword = (id: string, password = '123456') => request.put(`/admin/users/${id}/reset-password`, { password })
export const listDepartments = () => request.get<{id:string;name:string}[]>('/admin/users/departments').then(r => r.data)
export const listPositions = (department_id: string) => request.get<{id:string;name:string}[]>('/admin/users/positions', { params: { department_id } }).then(r => r.data)
export const searchManagedUsers = (keyword: string) => request.get<ManagedUser[]>('/admin/users/search', { params: { keyword } }).then(r => r.data)
