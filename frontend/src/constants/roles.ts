/** RBAC 角色与能力矩阵（与 backend/src/constants/roles.py 保持一致）。 */
export const ROLE_ADMIN = 'admin'
export const ROLE_ANALYST = 'analyst'
export const ROLE_VIEWER = 'viewer'

export type UserRole = typeof ROLE_ADMIN | typeof ROLE_ANALYST | typeof ROLE_VIEWER

export const ALL_ROLES: UserRole[] = [ROLE_ADMIN, ROLE_ANALYST, ROLE_VIEWER]

export const ROLE_LABELS: Record<UserRole, string> = {
  admin: '增长负责人',
  analyst: '增长分析师',
  viewer: '渠道与门店（只读）',
}

export const PERMISSIONS: Record<string, UserRole[]> = {
  'matrix:read': ALL_ROLES,
  'matrix:rebuild': [ROLE_ADMIN, ROLE_ANALYST],
  'cohorts:read': ALL_ROLES,
  'orders:read': ALL_ROLES,
  'orders:import': [ROLE_ADMIN, ROLE_ANALYST],
  'versions:read': ALL_ROLES,
  'ltv:read': ALL_ROLES,
  'ltv:run': [ROLE_ADMIN, ROLE_ANALYST],
  'ltv:recompute': [ROLE_ADMIN, ROLE_ANALYST],
  'ltv:sensitivity': [ROLE_ADMIN, ROLE_ANALYST],
  'ltv:publish': [ROLE_ADMIN],
  'channels:read': ALL_ROLES,
  'channels:export': [ROLE_ADMIN, ROLE_ANALYST],
  'audit:read': [ROLE_ADMIN],
}

export function roleCan(role: UserRole | undefined, action: string): boolean {
  if (!role) return false
  return (PERMISSIONS[action] ?? []).includes(role)
}
