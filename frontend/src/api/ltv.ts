import http from './http'
import type { LtvReport, LtvReportSummary, SensitivityPayload } from '../types/domain'

export interface RunPayload {
  name: string
  observed_months?: number | null
  lambda_min?: number | null
  lambda_max?: number | null
  margin_rate?: number | null
  forecast_months?: number | null
  channel_cac?: Record<string, number>
  note?: string
}

export async function fetchReports(): Promise<{ total: number; items: LtvReportSummary[] }> {
  const { data } = await http.get('/ltv/reports')
  return data
}

export async function fetchReport(reportId: string): Promise<LtvReport> {
  const { data } = await http.get<LtvReport>(`/ltv/reports/${reportId}`)
  return data
}

export async function runReport(payload: RunPayload): Promise<LtvReport> {
  const { data } = await http.post<LtvReport>('/ltv/reports', payload)
  return data
}

export async function publishReport(reportId: string): Promise<LtvReport> {
  const { data } = await http.post<LtvReport>(`/ltv/reports/${reportId}/publish`)
  return data
}

export async function recomputeReport(reportId: string): Promise<LtvReport> {
  const { data } = await http.post<LtvReport>(`/ltv/reports/${reportId}/recompute`)
  return data
}

export async function fetchSensitivity(reportId: string, delta = 0.03): Promise<SensitivityPayload> {
  const { data } = await http.get<SensitivityPayload>(`/ltv/reports/${reportId}/sensitivity`, {
    params: { delta },
  })
  return data
}
