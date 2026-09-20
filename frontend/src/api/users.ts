import { request } from './request'
export interface EmployeePayload { username: string; phone: string; department: string; company_id: string; role: 'employee' }
export interface Employee { id: string; username: string; phone?: string; department?: string; role: string; status?: string }
export const createEmployee = (payload: EmployeePayload) => request.post<Employee>('/users', payload).then((response) => response.data)
export const listEmployees = () => request.get<Employee[]>('/users').then((response) => response.data)
