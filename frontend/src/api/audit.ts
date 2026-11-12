import http from './http'

export interface AuditRow {
  id: string
  actor_email: string
  role: string
  action: string
  entity: string
  entity_id: string
  detail: string
  status_code: number
  created_at: string
}

export async function fetchAudit(limit = 30): Promise<{ total: number; items: AuditRow[] }> {
  const { data } = await http.get('/audit', { params: { limit } })
  return data
}
