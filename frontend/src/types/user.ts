import type { UserRole } from '../constants/roles'

export interface User {
  id: string
  email: string
  display_name: string
  role: UserRole
  role_label: string
  channel_scope: string | null
  permissions: string[]
}

export interface LoginResult {
  token: string
  refresh_token: string
  token_type: string
  user: User
}
