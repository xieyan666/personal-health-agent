import { create } from 'zustand'

export type UserRole = 'employee' | 'admin'
export interface UserState {
  userId: string
  username: string
  role: UserRole
  setUser: (user: Pick<UserState, 'userId' | 'username' | 'role'>) => void
  logout: () => void
}

export const useUserStore = create<UserState>((set) => ({
  userId: '', username: '', role: 'employee',
  setUser: (user) => set(user),
  logout: () => set({ userId: '', username: '', role: 'employee' }),
}))
