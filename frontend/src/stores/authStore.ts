import { defineStore } from 'pinia'
import { fetchMe, login as apiLogin, logout as apiLogout } from '../api/auth'
import type { User } from '../types/user'
import type { UserRole } from '../constants/roles'
import { roleCan } from '../constants/roles'
import { TOKEN_KEY } from '../utils/request'

interface AuthState {
  token: string
  user: User | null
  loading: boolean
  error: string
}

export const useAuthStore = defineStore('auth', {
  state: (): AuthState => ({
    token: localStorage.getItem(TOKEN_KEY) ?? '',
    user: null,
    loading: false,
    error: '',
  }),
  getters: {
    isAuthenticated: (state): boolean => Boolean(state.token),
    role: (state): UserRole => (state.user?.role ?? 'viewer') as UserRole,
    displayName: (state): string => state.user?.display_name ?? '',
    email: (state): string => state.user?.email ?? '',
    channelScope: (state): string | null => state.user?.channel_scope ?? null,
    can: (state) => (action: string): boolean => Boolean(state.user?.permissions?.includes(action)) || roleCan(state.user?.role as UserRole, action),
  },
  actions: {
    async login(email: string, password: string) {
      this.loading = true
      this.error = ''
      try {
        const result = await apiLogin(email, password)
        this.token = result.token
        this.user = result.user
        localStorage.setItem(TOKEN_KEY, result.token)
        return result
      } catch (error) {
        this.error = (error as { message?: string }).message ?? '登录失败'
        throw error
      } finally {
        this.loading = false
      }
    },
    async restore() {
      if (!this.token) return
      try {
        const result = await fetchMe()
        this.user = result.user
      } catch {
        this.logout()
      }
    },
    async logout() {
      try {
        if (this.token) await apiLogout()
      } catch {
        /* 退出失败也清本地态 */
      }
      this.token = ''
      this.user = null
      localStorage.removeItem(TOKEN_KEY)
    },
  },
})
