import { create } from 'zustand'
import { clearToken, getAccessToken, saveAccessToken, saveRefreshToken } from '../utils/token'
import { getMe } from '../api/auth'
export type AuthRole = 'employee' | 'admin' | 'company_admin' | 'system_admin'
export interface AuthUser { id: string; username: string; role: AuthRole; displayName?: string | null; avatarUrl?: string | null; company_id?: string | null }
type RawAuthUser = { id: string; username: string; role: AuthRole; display_name?: string | null; avatar_url?: string | null; company_id?: string | null }

const normalize = (user: RawAuthUser): AuthUser => ({
  id: user.id,
  username: user.username,
  role: user.role,
  displayName: user.display_name || user.username,
  avatarUrl: user.avatar_url || null,
  company_id: user.company_id,
})

interface AuthState { user: AuthUser | null; token: string | null; isAuthenticated: boolean; initialized: boolean; setSession: (user: RawAuthUser, access: string, refresh?: string) => void; hydrate: () => Promise<void>; setUser: (user: AuthUser) => void; logout: () => void }
export const useAuthStore = create<AuthState>((set) => ({
  user: null, token: getAccessToken(), isAuthenticated: Boolean(getAccessToken()), initialized: false,
  setSession: (user, access, refresh) => { saveAccessToken(access); if (refresh) saveRefreshToken(refresh); set({ user: normalize(user), token: access, isAuthenticated: true }) },
  hydrate: async () => { const token = getAccessToken(); if (!token) { set({ initialized: true }); return }; try { const user = await getMe(); set({ user: normalize(user), token, isAuthenticated: true, initialized: true }) } catch { clearToken(); set({ user: null, token: null, isAuthenticated: false, initialized: true }) } },
  setUser: (user) => set({ user }),
  logout: () => { clearToken(); set({ user: null, token: null, isAuthenticated: false }) },
}))
