import { request } from './request'
import type { AuthUser } from '../store/authStore'
export interface LoginResponse { access_token: string; refresh_token: string; user: AuthUser }
export const login = (username: string, password: string) => request.post<LoginResponse>('/auth/login', { username, password }).then((response) => response.data)
export const getMe = () => request.get<AuthUser>('/auth/me').then((response) => response.data)
